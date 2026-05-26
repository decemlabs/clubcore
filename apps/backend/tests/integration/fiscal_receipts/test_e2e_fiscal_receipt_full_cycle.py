"""Phase 51 Plan 51-10 Task 2 — E2E fiscal receipt lifecycle test.

Composition tested:
  - Phase 50 handle_payment_succeeded (inserts fiscal_receipts row + post-commit enqueue)
  - 51-06 _post_commit_enqueue fiscal-dispatch branch (the ARQ enqueue gate)
  - 51-05 dispatch_fiscal_receipt ARQ task (FISCAL-05 + FISCAL-07)
  - 51-07 handle_receipt_succeeded webhook handler (sent → succeeded FSM)
  - 51-07 handle_receipt_canceled webhook handler (sent → failed FSM)
  - 51-03 YooKassaClient.create_receipt + settings.tax_system_code (FISCAL-07)
  - 51-09 monitor_stale_fiscal_receipts cron safety net

Real-commit engine pattern (same as tests/integration/webhook_yookassa/conftest.py):
Both the payment.succeeded webhook handler AND handle_receipt_succeeded use
``async with session.begin():`` which cannot compose with the SAVEPOINT-based
root db_session.  We use a single e2e_fiscal_engine so the webhook client and
the dispatch task share the same DB connection pool and see each other's
committed rows.

SC coverage:
  - SC#1: receipt.succeeded flips fiscal_receipts.status to 'succeeded'
  - SC#2: dispatch_fiscal_receipt POSTs to ЮKassa and writes yookassa_receipt_id
  - SC#3: monitor_stale_fiscal_receipts catches stale-pending and marks failed
  - FISCAL-07: tax_system_code flows from settings (not hardcoded)
"""

from __future__ import annotations

import json as _json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.audit_models import AuditLog
from app.core.config import get_settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.integrations.yookassa.factory import build_yookassa_client
from app.integrations.yookassa.settings import YooKassaSettings
from app.modules.fiscal_receipts.constants import (
    KIND_PAYMENT,
    STATUS_FAILED,
    STATUS_SENT,
)
from app.modules.fiscal_receipts.models import FiscalReceipt
from app.modules.fiscal_receipts.tasks import dispatch_fiscal_receipt
from app.modules.online_payments.constants import (
    CONFIRMATION_TYPE_REDIRECT,
    STATUS_PENDING,
)
from app.modules.online_payments.models import OnlinePayment

pytestmark = pytest.mark.asyncio

# Tables touched by the payment-succeeded UoW + dispatch + fiscal webhooks.
_TRUNCATE_TABLES = (
    "audit_log",
    "fiscal_receipts",
    "payments",
    "memberships",
    "pt_packages",
    "online_payments",
    "membership_plans",
    "pt_package_plans",
    "clients",
    "users",
)


# ---------------------------------------------------------------------------
# Real-commit engine + session fixtures (shared across webhook + task).
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def e2e_fiscal_engine() -> AsyncIterator[Any]:
    """Real-commit engine shared by webhook client + dispatch task.

    Using a SINGLE engine ensures the webhook handler's committed rows are
    visible to the dispatch task's session factory and vice versa.
    """
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)
    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text(f"TRUNCATE {', '.join(_TRUNCATE_TABLES)} RESTART IDENTITY CASCADE")
            )
        await engine.dispose()


@pytest_asyncio.fixture
async def e2e_fiscal_session_factory(
    e2e_fiscal_engine: Any,
) -> async_sessionmaker[AsyncSession]:
    """Session factory shared by both the HTTP client and the dispatch task."""
    return async_sessionmaker(e2e_fiscal_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def e2e_fiscal_db_session(
    e2e_fiscal_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Real-commit session for test setup (seeding rows)."""
    async with e2e_fiscal_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def e2e_fiscal_client(
    app: FastAPI,
    e2e_fiscal_engine: Any,
) -> AsyncIterator[AsyncClient]:
    """Anonymous webhook client with real-commit per-request session override.

    The override creates a FRESH per-request session on every request,
    matching the pattern that allows both the payment.succeeded handler and
    the receipt.succeeded handler to open their own ``session.begin()`` blocks.
    The webhook endpoint is anonymous-by-design (D-50-39/42).
    """
    session_factory = async_sessionmaker(e2e_fiscal_engine, expire_on_commit=False)

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    def _override_get_redis() -> Any:
        return app.state.redis

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Seed helpers.
# ---------------------------------------------------------------------------


async def _seed_pending_online_payment(
    session: AsyncSession,
) -> tuple[str, UUID, str]:
    """Seed Client + MembershipPlan + OnlinePayment(status='pending').

    Returns (yookassa_payment_id, online_payment_id, client_email).
    """
    from app.core.models import User
    from app.core.permissions import Role
    from app.core.security import hash_password
    from app.modules.clients.models import Client
    from app.modules.memberships.models import MembershipPlan

    nonce = uuid4().hex[:8]
    owner = User(
        email=f"e2e-fiscal-owner-{nonce}@example.com",
        password_hash=await hash_password("hunter22hunter22"),
        role=Role.OWNER,
        full_name="E2E Fiscal Owner",
    )
    session.add(owner)
    await session.flush()

    client = Client(
        last_name="Иванов",
        first_name="Иван",
        phone=f"+7999{nonce}",
        email=f"e2e-fiscal-client-{nonce}@example.com",
        created_by_user_id=owner.id,
    )
    session.add(client)
    await session.flush()

    plan = MembershipPlan(
        name=f"E2E-Fiscal-Plan-{nonce}",
        duration_days=30,
        price_kopecks=100_000,
        freeze_days_limit=7,
        active=True,
    )
    session.add(plan)
    await session.flush()

    yk_payment_id = f"yk-e2e-fiscal-{nonce}"
    op = OnlinePayment(
        client_id=client.id,
        membership_plan_id=plan.id,
        pt_package_plan_id=None,
        yookassa_payment_id=yk_payment_id,
        idempotency_key=uuid4().hex,
        amount_kopecks=100_000,
        status=STATUS_PENDING,
        confirmation_url="https://example.com/confirm",
        confirmation_type=CONFIRMATION_TYPE_REDIRECT,
        audit_correlation_id=uuid4(),
    )
    session.add(op)
    await session.flush()
    await session.commit()
    return yk_payment_id, op.id, client.email or ""


async def _flush_webhook_dedup_keys(app: FastAPI) -> None:
    """Flush Redis webhook dedup keys to prevent test pollution."""
    redis = app.state.redis
    keys = await redis.keys("cc:yookassa:webhook:*")
    if keys:
        await redis.delete(*keys)


# ---------------------------------------------------------------------------
# Tests.
# ---------------------------------------------------------------------------


async def test_e2e_fiscal_receipt_full_cycle_payment_succeeded_to_receipt_succeeded(
    app: FastAPI,
    e2e_fiscal_db_session: AsyncSession,
    e2e_fiscal_session_factory: async_sessionmaker[AsyncSession],
    e2e_fiscal_client: AsyncClient,
    yookassa_get_payment_succeeded: Any,
    yookassa_create_receipt_ok: Any,
) -> None:
    """SC#1 + SC#2 — payment.succeeded → dispatch → receipt.succeeded.

    Full chain:
    1. payment.succeeded webhook delivery → atomic UoW (Phase 50):
       - OnlinePayment.status='succeeded'
       - Payment ledger row
       - Membership activation
       - FiscalReceipt(kind='payment', status='sent')
       - 4 audit rows
    2. dispatch_fiscal_receipt ARQ task → POSTs to ЮKassa → yookassa_receipt_id set.
    3. receipt.succeeded webhook delivery → FiscalReceipt.status='succeeded'.

    FISCAL-07 verified: the respx-recorded create_receipt request body carries
    tax_system_code == YooKassaSettings().tax_system_code.
    """
    yk_payment_id, online_payment_id, _client_email = await _seed_pending_online_payment(
        e2e_fiscal_db_session
    )
    await _flush_webhook_dedup_keys(app)

    # Step 1: Deliver payment.succeeded webhook.
    webhook_body = {
        "event": "payment.succeeded",
        "object": {
            "id": yk_payment_id,
            "status": "succeeded",
            "amount": {"value": "1000.00", "currency": "RUB"},
        },
    }
    response = await e2e_fiscal_client.post("/api/v1/_internal/yookassa/webhook", json=webhook_body)
    assert response.status_code == 200, response.text

    # Phase 50 UoW result: FiscalReceipt(kind='payment', status='sent') inserted.
    async with e2e_fiscal_session_factory() as verify_session:
        op = await verify_session.get(OnlinePayment, online_payment_id)
        assert op is not None
        assert op.status == "succeeded"

        fr = await verify_session.scalar(
            select(FiscalReceipt)
            .where(
                FiscalReceipt.kind == KIND_PAYMENT,
            )
            .order_by(FiscalReceipt.id.desc())
            .limit(1)
        )
        assert fr is not None
        assert fr.status == STATUS_SENT
        assert fr.yookassa_receipt_id is None  # not yet dispatched
        fr_id = fr.id

    # Step 2: Run dispatch_fiscal_receipt ARQ task directly (FISCAL-05).
    yookassa_client = await build_yookassa_client(settings=YooKassaSettings())
    try:
        arq_ctx = {
            "sessionmaker": e2e_fiscal_session_factory,
            "yookassa_client": yookassa_client,
            "redis": app.state.redis,
            "job_try": 1,
        }
        result = await dispatch_fiscal_receipt(arq_ctx, str(fr_id))
        assert result == "sent"  # task returns "sent" on success (D-51-13 step 5)
    finally:
        await yookassa_client.aclose()

    # After dispatch: yookassa_receipt_id set; status still 'sent'.
    async with e2e_fiscal_session_factory() as verify_session:
        fr_after = await verify_session.get(FiscalReceipt, fr_id)
        assert fr_after is not None
        assert fr_after.yookassa_receipt_id is not None
        assert fr_after.status == STATUS_SENT

        # FISCAL-07: assert tax_system_code came from settings, not hardcoded.
        routes = list(yookassa_create_receipt_ok.routes)
        receipts_route = next(r for r in routes if "receipts" in str(r.pattern))
        assert receipts_route.call_count >= 1
        request = receipts_route.calls.last.request
        body = _json.loads(request.content)
        expected_tax = int(YooKassaSettings().tax_system_code)
        assert body["tax_system_code"] == expected_tax, (
            f"FISCAL-07 violation: tax_system_code={body['tax_system_code']!r} "
            f"does not match settings ({expected_tax})"
        )

        yookassa_receipt_id = fr_after.yookassa_receipt_id

    # Step 3: Deliver receipt.succeeded webhook (SC#1).
    await _flush_webhook_dedup_keys(app)
    receipt_body = {
        "event": "receipt.succeeded",
        "object": {
            "id": yookassa_receipt_id,
            "type": "payment",
            "status": "succeeded",
        },
    }
    response = await e2e_fiscal_client.post("/api/v1/_internal/yookassa/webhook", json=receipt_body)
    assert response.status_code == 200, response.text

    # Step 4: Verify status flipped to 'succeeded' (SC#1).
    async with e2e_fiscal_session_factory() as verify_session:
        fr_final = await verify_session.get(FiscalReceipt, fr_id)
        assert fr_final is not None
        assert fr_final.status == "succeeded"
        assert fr_final.succeeded_at is not None

        # Audit: fiscal_receipt_dispatched exists.
        dispatched_row = await verify_session.scalar(
            select(AuditLog).where(
                AuditLog.action == "fiscal_receipt_dispatched",
                AuditLog.resource_id == fr_id,
            )
        )
        assert dispatched_row is not None, "fiscal_receipt_dispatched audit row missing"

        # Audit: fiscal_receipt_succeeded exists.
        succeeded_row = await verify_session.scalar(
            select(AuditLog).where(
                AuditLog.action == "fiscal_receipt_succeeded",
                AuditLog.resource_id == fr_id,
            )
        )
        assert succeeded_row is not None, "fiscal_receipt_succeeded audit row missing"


async def test_e2e_fiscal_receipt_dispatch_failure_path_transitions_status_failed(
    app: FastAPI,
    e2e_fiscal_db_session: AsyncSession,
    e2e_fiscal_session_factory: async_sessionmaker[AsyncSession],
    e2e_fiscal_client: AsyncClient,
    yookassa_get_payment_succeeded: Any,
    yookassa_create_receipt_429: Any,
) -> None:
    """FISCAL-05 failure path — 429 permanent_error → status='failed'.

    1. payment.succeeded webhook creates FiscalReceipt(status='sent').
    2. dispatch_fiscal_receipt with 429 → permanent_error → status='failed'.
    3. No receipt.succeeded (nothing to flip).
    """
    yk_payment_id, _online_payment_id, _email = await _seed_pending_online_payment(
        e2e_fiscal_db_session
    )
    await _flush_webhook_dedup_keys(app)

    # Deliver payment.succeeded.
    response = await e2e_fiscal_client.post(
        "/api/v1/_internal/yookassa/webhook",
        json={
            "event": "payment.succeeded",
            "object": {
                "id": yk_payment_id,
                "status": "succeeded",
                "amount": {"value": "1000.00", "currency": "RUB"},
            },
        },
    )
    assert response.status_code == 200, response.text

    # Locate the fiscal_receipt row.
    async with e2e_fiscal_session_factory() as verify_session:
        fr = await verify_session.scalar(
            select(FiscalReceipt)
            .where(FiscalReceipt.kind == KIND_PAYMENT)
            .order_by(FiscalReceipt.id.desc())
            .limit(1)
        )
        assert fr is not None
        fr_id = fr.id

    # Dispatch with 429 → permanent_error.
    yookassa_client = await build_yookassa_client(settings=YooKassaSettings())
    try:
        # Phase 52 (52-05): the failure path enqueues a best-effort
        # dispatch_payment_notification owner alert via ctx['redis']. In the
        # real ARQ worker ctx['redis'] is an ArqRedis (has enqueue_job); the
        # lifespan redis is a plain Redis. Wrap so circuit-breaker ops still
        # hit the real redis while enqueue_job is a no-op AsyncMock.
        class _ArqRedisProxy:
            def __init__(self, redis: Any) -> None:
                self._redis = redis
                self.enqueue_job = AsyncMock()

            def __getattr__(self, name: str) -> Any:
                return getattr(self._redis, name)

        arq_ctx = {
            "sessionmaker": e2e_fiscal_session_factory,
            "yookassa_client": yookassa_client,
            "redis": _ArqRedisProxy(app.state.redis),
            "job_try": 1,
        }
        result = await dispatch_fiscal_receipt(arq_ctx, str(fr_id))
        assert result == "failed"
    finally:
        await yookassa_client.aclose()

    # Verify status='failed'.
    async with e2e_fiscal_session_factory() as verify_session:
        fr_after = await verify_session.get(FiscalReceipt, fr_id)
        assert fr_after is not None
        assert fr_after.status == STATUS_FAILED
        assert fr_after.failed_at is not None
        assert fr_after.failure_reason is not None
        assert fr_after.failure_reason.startswith("permanent_error:")

        # Audit: fiscal_receipt_failed exists.
        failed_row = await verify_session.scalar(
            select(AuditLog).where(
                AuditLog.action == "fiscal_receipt_failed",
                AuditLog.resource_id == fr_id,
            )
        )
        assert failed_row is not None, "fiscal_receipt_failed audit row missing"


async def test_e2e_fiscal_receipt_monitor_stale_cron_catches_pending_row(
    e2e_fiscal_db_session: AsyncSession,
    e2e_fiscal_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """SC#3 — monitor_stale_fiscal_receipts catches stale-pending row.

    Manually insert a FiscalReceipt(status='pending', created_at=now-100s),
    run the cron, assert status='failed' + failure_reason='stale_pending_no_dispatch'.
    """
    from app.modules.payments.constants import SUBJECT_KIND_MEMBERSHIP
    from app.modules.payments.models import Payment
    from app.workers.scheduled.monitor_stale_fiscal_receipts import (
        monitor_stale_fiscal_receipts,
    )

    # Seed a minimal Payment row (no online chain needed for the cron test).
    payment = Payment(
        subject_kind=SUBJECT_KIND_MEMBERSHIP,
        subject_id=uuid4(),
        amount_kopecks=10_000,
        method="online",
        received_by_user_id=None,
    )
    e2e_fiscal_db_session.add(payment)
    await e2e_fiscal_db_session.flush()

    fr = FiscalReceipt(
        payment_id=payment.id,
        kind=KIND_PAYMENT,
        status="pending",  # NOTE: status='pending' not 'sent'
        customer_email=f"e2e-stale-{uuid4().hex[:6]}@example.com",
        audit_correlation_id=uuid4(),
    )
    e2e_fiscal_db_session.add(fr)
    await e2e_fiscal_db_session.flush()

    # Force created_at to 100s in the past (cron threshold is 90s).
    await e2e_fiscal_db_session.execute(
        text("UPDATE fiscal_receipts SET created_at = :ts WHERE id = :id"),
        {
            "ts": datetime.now(UTC) - timedelta(seconds=100),
            "id": fr.id,
        },
    )
    await e2e_fiscal_db_session.commit()
    fr_id = fr.id

    # Run the cron.
    cron_ctx = {"sessionmaker": e2e_fiscal_session_factory}
    count = await monitor_stale_fiscal_receipts(cron_ctx)
    assert count >= 1

    # Verify status='failed'.
    async with e2e_fiscal_session_factory() as verify_session:
        row = await verify_session.get(FiscalReceipt, fr_id)
        assert row is not None
        assert row.status == STATUS_FAILED
        assert row.failed_at is not None
        assert row.failure_reason == "stale_pending_no_dispatch"

        audit_row = await verify_session.scalar(
            select(AuditLog).where(
                AuditLog.action == "fiscal_receipt_failed",
                AuditLog.resource_id == fr_id,
            )
        )
        assert audit_row is not None
        assert audit_row.payload["failure_reason"] == "stale_pending_no_dispatch"


async def test_e2e_fiscal_receipt_canceled_webhook_transitions_to_failed(
    app: FastAPI,
    e2e_fiscal_db_session: AsyncSession,
    e2e_fiscal_session_factory: async_sessionmaker[AsyncSession],
    e2e_fiscal_client: AsyncClient,
    yookassa_get_payment_succeeded: Any,
    yookassa_create_receipt_ok: Any,
) -> None:
    """D-51-22 cancel path — receipt.canceled webhook transitions sent→failed.

    1. payment.succeeded webhook creates FiscalReceipt(status='sent').
    2. dispatch_fiscal_receipt → yookassa_receipt_id set.
    3. receipt.canceled webhook → status='failed', failure_reason set.
    """
    yk_payment_id, _op_id, _email = await _seed_pending_online_payment(e2e_fiscal_db_session)
    await _flush_webhook_dedup_keys(app)

    # Step 1: Deliver payment.succeeded.
    response = await e2e_fiscal_client.post(
        "/api/v1/_internal/yookassa/webhook",
        json={
            "event": "payment.succeeded",
            "object": {
                "id": yk_payment_id,
                "status": "succeeded",
                "amount": {"value": "1000.00", "currency": "RUB"},
            },
        },
    )
    assert response.status_code == 200, response.text

    # Locate fiscal_receipt.
    async with e2e_fiscal_session_factory() as verify_session:
        fr = await verify_session.scalar(
            select(FiscalReceipt)
            .where(FiscalReceipt.kind == KIND_PAYMENT)
            .order_by(FiscalReceipt.id.desc())
            .limit(1)
        )
        assert fr is not None
        fr_id = fr.id

    # Step 2: Dispatch (sets yookassa_receipt_id).
    yookassa_client = await build_yookassa_client(settings=YooKassaSettings())
    try:
        arq_ctx = {
            "sessionmaker": e2e_fiscal_session_factory,
            "yookassa_client": yookassa_client,
            "redis": app.state.redis,
            "job_try": 1,
        }
        result = await dispatch_fiscal_receipt(arq_ctx, str(fr_id))
        assert result == "sent"
    finally:
        await yookassa_client.aclose()

    async with e2e_fiscal_session_factory() as verify_session:
        fr_dispatched = await verify_session.get(FiscalReceipt, fr_id)
        assert fr_dispatched is not None
        yookassa_receipt_id = fr_dispatched.yookassa_receipt_id
        assert yookassa_receipt_id is not None

    # Step 3: Deliver receipt.canceled webhook.
    await _flush_webhook_dedup_keys(app)
    canceled_body = {
        "event": "receipt.canceled",
        "object": {
            "id": yookassa_receipt_id,
            "type": "payment",
            "status": "canceled",
            "cancellation_details": {
                "party": "tax",
                "reason": "rejected_by_timeout",
            },
        },
    }
    response = await e2e_fiscal_client.post(
        "/api/v1/_internal/yookassa/webhook", json=canceled_body
    )
    assert response.status_code == 200, response.text

    # Verify status flipped to 'failed'.
    async with e2e_fiscal_session_factory() as verify_session:
        fr_final = await verify_session.get(FiscalReceipt, fr_id)
        assert fr_final is not None
        assert fr_final.status == STATUS_FAILED
        assert fr_final.failed_at is not None
        assert fr_final.failure_reason is not None
        # Verify the cancellation reason is captured.
        assert "rejected_by_timeout" in fr_final.failure_reason
