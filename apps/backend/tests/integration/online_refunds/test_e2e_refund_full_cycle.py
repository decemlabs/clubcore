"""Phase 51 Plan 51-10 — E2E refund full-cycle test.

Composition tested:
  - 51-08 POST /memberships/{id}/refund endpoint
  - 51-07 handle_refund_succeeded webhook handler
  - 51-06 _post_commit_enqueue with fiscal_receipt_id branch
  - 51-05 dispatch_fiscal_receipt ARQ task (for the kind='refund' receipt)
  - 51-03 YooKassaClient.create_receipt + create_refund

Real-commit engine pattern (D-13 / Phase 50 webhook conftest precedent):
Both POST /refund AND the webhook handler use ``async with session.begin():``
which cannot compose with the SAVEPOINT-based root db_session. Tests here
use the same engine-per-test + TRUNCATE approach as
``tests/integration/webhook_yookassa/conftest.py``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
import respx
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
from app.core.permissions import Role
from app.core.redis import get_redis
from app.core.security import hash_password
from app.modules.clients.models import Client
from app.modules.fiscal_receipts.models import FiscalReceipt
from app.modules.memberships.constants import CANCELLATION_REASON_REFUNDED
from app.modules.memberships.models import Membership, MembershipPlan
from app.modules.online_payments.models import OnlinePayment
from app.modules.online_refunds.models import OnlineRefund
from app.modules.payments.constants import (
    SUBJECT_KIND_MEMBERSHIP,
    SUBJECT_KIND_PT_PACKAGE,
)
from app.modules.payments.models import Payment
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from tests.integrations.yookassa.conftest import (  # noqa: F401
    _YOOKASSA_BASE_URL,
    yookassa_create_receipt_ok,
    yookassa_create_refund_success,
)

pytestmark = pytest.mark.asyncio

# Tables touched by the refund UoW + fiscal side.
_TRUNCATE_TABLES = (
    "audit_log",
    "fiscal_receipts",
    "online_refunds",
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
# yookassa_get_refund_succeeded — local fixture (not in Phase 48 base conftest;
# the canonical definition lives in test_handle_refund_succeeded.py but is
# local there; we recreate it here to avoid cross-test-file imports).
# ---------------------------------------------------------------------------


@pytest.fixture
def yookassa_get_refund_succeeded() -> Any:
    """GET /v3/refunds/{id} → 200 with status='succeeded'."""
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.get(url__regex=r"^https://api\.yookassa\.ru/v3/refunds/[\w-]+$").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "rfnd-e2e-test-0000",
                    "payment_id": "pay-e2e-test-0000",
                    "status": "succeeded",
                    "amount": {"value": "1990.00", "currency": "RUB"},
                },
            )
        )
        yield router


# ---------------------------------------------------------------------------
# Real-commit engine + session fixtures.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def e2e_engine() -> AsyncIterator[Any]:
    """Real-commit engine; TRUNCATEs all touched tables on teardown."""
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
async def e2e_session_factory(e2e_engine: Any) -> async_sessionmaker[AsyncSession]:
    """Session factory shared by seeding + the HTTP client override."""
    return async_sessionmaker(e2e_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def e2e_db_session(
    e2e_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Real-commit session for test setup (seeding rows)."""
    async with e2e_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def e2e_client(
    app: FastAPI,
    e2e_engine: Any,
) -> AsyncIterator[AsyncClient]:
    """Authenticated owner client with real-commit session override.

    The override creates a FRESH per-request session (same engine) on every
    request, matching the pattern that allows both the POST /refund endpoint
    and the webhook handler to open their own ``session.begin()`` blocks.
    """
    session_factory = async_sessionmaker(e2e_engine, expire_on_commit=False)

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


async def _seed_owner(session: AsyncSession, *, nonce: str) -> Any:
    """Seed an owner user and return the ORM row."""
    from app.core.models import User

    owner = User(
        email=f"e2e-refund-owner-{nonce}@example.com",
        password_hash=await hash_password("hunter22hunter22"),
        role=Role.OWNER,
        full_name="E2E Refund Owner",
    )
    session.add(owner)
    await session.flush()
    await session.commit()
    return owner


async def _login_client(client: AsyncClient, *, email: str) -> None:
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "hunter22hunter22"},
    )
    assert r.status_code == 200, f"Login failed: {r.text}"


async def _seed_membership_chain(
    session: AsyncSession,
    *,
    owner_email: str,
) -> tuple[Client, MembershipPlan, Membership, OnlinePayment, Payment]:
    """Seed Client + MembershipPlan + Membership + succeeded OnlinePayment + positive Payment."""
    from app.core.models import User

    nonce = uuid4().hex[:8]
    owner = User(
        email=owner_email,
        password_hash=await hash_password("hunter22hunter22"),
        role=Role.OWNER,
        full_name="E2E Chain Owner",
    )
    session.add(owner)
    await session.flush()

    client = Client(
        last_name="Иванов",
        first_name="Иван",
        phone=f"+7999{nonce}",
        email=f"e2e-client-{nonce}@example.com",
        created_by_user_id=owner.id,
    )
    session.add(client)
    await session.flush()

    plan = MembershipPlan(
        name=f"E2E-Plan-{nonce}",
        duration_days=30,
        price_kopecks=199_00,
        freeze_days_limit=7,
        active=True,
    )
    session.add(plan)
    await session.flush()

    today = date.today()
    membership = Membership(
        client_id=client.id,
        plan_id=plan.id,
        plan_name_snapshot=plan.name,
        duration_days_snapshot=plan.duration_days,
        price_kopecks_snapshot=plan.price_kopecks,
        freeze_days_limit_snapshot=plan.freeze_days_limit,
        start_date=today,
        end_date=today + timedelta(days=plan.duration_days - 1),
        status="active",
    )
    session.add(membership)
    await session.flush()

    op = OnlinePayment(
        client_id=client.id,
        membership_plan_id=plan.id,
        pt_package_plan_id=None,
        yookassa_payment_id=f"yk-e2e-{nonce}",
        idempotency_key=f"idem-e2e-{nonce}",
        amount_kopecks=plan.price_kopecks,
        status="succeeded",
        confirmation_url=None,
        confirmation_type="redirect",
        succeeded_at=datetime.now(UTC),
        audit_correlation_id=uuid4(),
    )
    session.add(op)
    await session.flush()

    payment = Payment(
        subject_kind=SUBJECT_KIND_MEMBERSHIP,
        subject_id=plan.id,
        amount_kopecks=plan.price_kopecks,
        method="online",
        received_by_user_id=None,
    )
    session.add(payment)
    await session.flush()
    await session.commit()
    return client, plan, membership, op, payment


async def _seed_pt_package_chain(
    session: AsyncSession,
    *,
    owner_email: str,
) -> tuple[Client, PtPackagePlan, PtPackage, OnlinePayment, Payment]:
    """Seed Client + PtPackagePlan + PtPackage + succeeded OnlinePayment + positive Payment."""
    from app.core.models import User

    nonce = uuid4().hex[:8]
    owner = User(
        email=owner_email,
        password_hash=await hash_password("hunter22hunter22"),
        role=Role.OWNER,
        full_name="E2E PT Chain Owner",
    )
    session.add(owner)
    await session.flush()

    client = Client(
        last_name="Петров",
        first_name="Пётр",
        phone=f"+7888{nonce}",
        email=f"e2e-pt-client-{nonce}@example.com",
        created_by_user_id=owner.id,
    )
    session.add(client)
    await session.flush()

    plan = PtPackagePlan(
        name=f"E2E-PT-Plan-{nonce}",
        session_count=10,
        price_kopecks=199_00,
        validity_days=90,
    )
    session.add(plan)
    await session.flush()

    today = date.today()
    pt_package = PtPackage(
        client_id=client.id,
        plan_id=plan.id,
        trainer_id=None,
        plan_name_snapshot=plan.name,
        session_count_snapshot=plan.session_count,
        sessions_remaining=plan.session_count,
        price_kopecks_snapshot=plan.price_kopecks,
        validity_days_snapshot=plan.validity_days,
        start_date=today,
        end_date=today + timedelta(days=plan.validity_days - 1),
        status="active",
    )
    session.add(pt_package)
    await session.flush()

    op = OnlinePayment(
        client_id=client.id,
        membership_plan_id=None,
        pt_package_plan_id=plan.id,
        yookassa_payment_id=f"yk-e2e-pt-{nonce}",
        idempotency_key=f"idem-e2e-pt-{nonce}",
        amount_kopecks=plan.price_kopecks,
        status="succeeded",
        confirmation_url=None,
        confirmation_type="redirect",
        succeeded_at=datetime.now(UTC),
        audit_correlation_id=uuid4(),
    )
    session.add(op)
    await session.flush()

    payment = Payment(
        subject_kind=SUBJECT_KIND_PT_PACKAGE,
        subject_id=plan.id,
        amount_kopecks=plan.price_kopecks,
        method="online",
        received_by_user_id=None,
    )
    session.add(payment)
    await session.flush()
    await session.commit()
    return client, plan, pt_package, op, payment


async def _flush_webhook_dedup_keys(app: FastAPI) -> None:
    """Flush Redis webhook dedup keys so replay tests don't get dedup'd."""
    redis = app.state.redis
    keys = await redis.keys("sz:yookassa:webhook:*")
    if keys:
        await redis.delete(*keys)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_e2e_refund_full_cycle_membership(
    app: FastAPI,
    e2e_db_session: AsyncSession,
    e2e_session_factory: async_sessionmaker[AsyncSession],
    e2e_client: AsyncClient,
    yookassa_create_refund_success: Any,
    yookassa_get_refund_succeeded: Any,
    yookassa_create_receipt_ok: Any,
) -> None:
    """SC#4 + SC#5 + REFUND-01 — POST /memberships/{id}/refund → webhook → fiscal dispatch.

    Full chain:
    1. POST /memberships/{id}/refund → 202 + pending OnlineRefund
    2. refund.succeeded webhook delivery → atomic UoW:
       - OnlineRefund.status='succeeded'
       - negative Payment(refund_of=original.id)
       - Membership.status='cancelled' with CANCELLATION_REASON_REFUNDED
       - FiscalReceipt(kind='refund', status='sent')
       - 3 child audits + yookassa_webhook_received root
    3. dispatch_fiscal_receipt ARQ task executed directly → yookassa_receipt_id set
    """
    # Seed the membership chain.
    nonce = uuid4().hex[:6]
    _client, plan, membership, op, original_payment = await _seed_membership_chain(
        e2e_db_session,
        owner_email=f"e2e-mbr-owner-{nonce}@example.com",
    )

    # Flush any pre-existing dedup keys.
    await _flush_webhook_dedup_keys(app)

    # Login and get CSRF cookie.
    await e2e_client.post(
        "/api/v1/auth/login",
        json={"email": f"e2e-mbr-owner-{nonce}@example.com", "password": "hunter22hunter22"},
    )
    csrf = e2e_client.cookies.get("sportzal_csrf") or ""

    # Step 1: POST /refund.
    idem_key = str(uuid4())
    resp = await e2e_client.post(
        f"/api/v1/online-payments/memberships/{membership.id}/refund",
        json={"idempotencyKey": idem_key, "reason": "customer request"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    data = body["data"]
    online_refund_id = UUID(data["onlineRefundId"])
    yookassa_refund_id = data["yookassaRefundId"]
    assert data["status"] == "pending"

    # Verify DB state after POST.
    async with e2e_session_factory() as verify_session:
        refund_row = await verify_session.get(OnlineRefund, online_refund_id)
        assert refund_row is not None
        assert refund_row.status == "pending"
        assert refund_row.yookassa_refund_id == yookassa_refund_id

    # Step 2: Deliver refund.succeeded webhook.
    # Flush dedup keys so this webhook is treated as first delivery.
    await _flush_webhook_dedup_keys(app)
    webhook_body = {
        "event": "refund.succeeded",
        "object": {
            "id": yookassa_refund_id,
            "status": "succeeded",
            "amount": {"value": "19.90", "currency": "RUB"},
        },
    }
    webhook_resp = await e2e_client.post(
        "/api/v1/_internal/yookassa/webhook",
        json=webhook_body,
    )
    assert webhook_resp.status_code == 200, webhook_resp.text

    # Step 3: Verify atomic UoW results (SC#5).
    async with e2e_session_factory() as verify_session:
        # OnlineRefund flipped.
        refund_row = await verify_session.get(OnlineRefund, online_refund_id)
        assert refund_row is not None
        assert refund_row.status == "succeeded"
        assert refund_row.succeeded_at is not None

        # Negative Payment row (refund_of=original).
        refund_payment = await verify_session.scalar(
            select(Payment).where(
                Payment.refund_of == original_payment.id,
            )
        )
        assert refund_payment is not None
        assert refund_payment.amount_kopecks < 0
        assert refund_payment.amount_kopecks == -original_payment.amount_kopecks

        # Membership cancelled.
        fresh_membership = await verify_session.get(Membership, membership.id)
        assert fresh_membership is not None
        assert fresh_membership.status == "cancelled"
        assert fresh_membership.cancellation_reason == CANCELLATION_REASON_REFUNDED

        # FiscalReceipt(kind='refund', status='sent') inserted.
        refund_fr = await verify_session.scalar(
            select(FiscalReceipt).where(
                FiscalReceipt.payment_id == refund_payment.id,
                FiscalReceipt.kind == "refund",
            )
        )
        assert refund_fr is not None
        assert refund_fr.status == "sent"

        # Audit chain: yookassa_webhook_received row + child events.
        # yookassa_webhook_received is emitted last; online_payment_refunded
        # resource_id is op.id; membership_refunded resource_id is membership.id.
        # Query each event type by its known resource_id shape.
        wh_row = await verify_session.scalar(
            select(AuditLog).where(
                AuditLog.action == "yookassa_webhook_received",
                AuditLog.resource_type == "yookassa_webhook",
            ).order_by(AuditLog.created_at.desc()).limit(1)
        )
        assert wh_row is not None, "yookassa_webhook_received audit row missing"

        refunded_row = await verify_session.scalar(
            select(AuditLog).where(
                AuditLog.action == "online_payment_refunded",
                AuditLog.resource_id == op.id,
            )
        )
        assert refunded_row is not None, "online_payment_refunded audit row missing"

        mbr_refunded_row = await verify_session.scalar(
            select(AuditLog).where(
                AuditLog.action == "membership_refunded",
                AuditLog.resource_id == membership.id,
            )
        )
        assert mbr_refunded_row is not None, "membership_refunded audit row missing"

    # Step 4: Run dispatch_fiscal_receipt ARQ task directly.
    assert refund_fr is not None
    from app.integrations.yookassa.factory import build_yookassa_client
    from app.integrations.yookassa.settings import YooKassaSettings
    from app.modules.fiscal_receipts.tasks import dispatch_fiscal_receipt

    yookassa_client = await build_yookassa_client(settings=YooKassaSettings())
    try:
        arq_ctx = {
            "sessionmaker": e2e_session_factory,
            "yookassa_client": yookassa_client,
            "redis": app.state.redis,
            "job_try": 1,
        }
        result = await dispatch_fiscal_receipt(arq_ctx, str(refund_fr.id))
        assert result == "sent"  # task returns "sent" on success (status stays 'sent' until receipt.succeeded webhook)
    finally:
        await yookassa_client.aclose()

    # Step 5: Verify yookassa_receipt_id was written back.
    async with e2e_session_factory() as verify_session:
        fr_after = await verify_session.get(FiscalReceipt, refund_fr.id)
        assert fr_after is not None
        assert fr_after.yookassa_receipt_id is not None
        # Status stays 'sent' — flips to 'succeeded' only via receipt.succeeded webhook.
        assert fr_after.status == "sent"


async def test_e2e_refund_full_cycle_idempotent_replay_returns_same_refund_id(
    app: FastAPI,
    e2e_db_session: AsyncSession,
    e2e_session_factory: async_sessionmaker[AsyncSession],
    e2e_client: AsyncClient,
    yookassa_create_refund_success: Any,
) -> None:
    """REFUND-03 idempotency — same idempotency_key → same OnlineRefund row, single DB insert.

    POST twice with the same idempotency_key; assert both responses have the
    same online_refund_id and only one OnlineRefund row exists in the DB.
    """
    nonce = uuid4().hex[:6]
    _client, plan, membership, op, original_payment = await _seed_membership_chain(
        e2e_db_session,
        owner_email=f"e2e-idem-owner-{nonce}@example.com",
    )

    await _flush_webhook_dedup_keys(app)

    await e2e_client.post(
        "/api/v1/auth/login",
        json={"email": f"e2e-idem-owner-{nonce}@example.com", "password": "hunter22hunter22"},
    )
    csrf = e2e_client.cookies.get("sportzal_csrf") or ""
    idem_key = str(uuid4())

    # First POST.
    resp1 = await e2e_client.post(
        f"/api/v1/online-payments/memberships/{membership.id}/refund",
        json={"idempotencyKey": idem_key, "reason": "cancel"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp1.status_code == 202, resp1.text
    refund_id_1 = resp1.json()["data"]["onlineRefundId"]

    # Second POST — same idempotency_key, same membership.
    resp2 = await e2e_client.post(
        f"/api/v1/online-payments/memberships/{membership.id}/refund",
        json={"idempotencyKey": idem_key, "reason": "cancel"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp2.status_code == 202, resp2.text
    refund_id_2 = resp2.json()["data"]["onlineRefundId"]

    # Both responses carry the same online_refund_id.
    assert refund_id_1 == refund_id_2

    # Only one OnlineRefund row in the DB.
    async with e2e_session_factory() as verify_session:
        all_refunds = (
            await verify_session.execute(
                select(OnlineRefund).where(
                    OnlineRefund.online_payment_id == op.id
                )
            )
        ).scalars().all()
        assert len(all_refunds) == 1


async def test_e2e_refund_full_cycle_webhook_replay_returns_200_silently(
    app: FastAPI,
    e2e_db_session: AsyncSession,
    e2e_session_factory: async_sessionmaker[AsyncSession],
    e2e_client: AsyncClient,
    yookassa_create_refund_success: Any,
    yookassa_get_refund_succeeded: Any,
    yookassa_create_receipt_ok: Any,
) -> None:
    """REFUND-03 — webhook replay returns 200 silently (Redis dedup OR DB partial-UNIQUE backstop).

    Delivers refund.succeeded twice; the second delivery is either Redis-dedup'd
    or hits the DB partial-UNIQUE constraint and returns 200 without mutation.
    """
    nonce = uuid4().hex[:6]
    _client, plan, membership, op, original_payment = await _seed_membership_chain(
        e2e_db_session,
        owner_email=f"e2e-wh-replay-owner-{nonce}@example.com",
    )

    await _flush_webhook_dedup_keys(app)

    await e2e_client.post(
        "/api/v1/auth/login",
        json={"email": f"e2e-wh-replay-owner-{nonce}@example.com", "password": "hunter22hunter22"},
    )
    csrf = e2e_client.cookies.get("sportzal_csrf") or ""

    resp = await e2e_client.post(
        f"/api/v1/online-payments/memberships/{membership.id}/refund",
        json={"idempotencyKey": str(uuid4()), "reason": "cancel"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 202, resp.text
    yookassa_refund_id = resp.json()["data"]["yookassaRefundId"]

    webhook_body = {
        "event": "refund.succeeded",
        "object": {
            "id": yookassa_refund_id,
            "status": "succeeded",
            "amount": {"value": "19.90", "currency": "RUB"},
        },
    }

    # First delivery — flush dedup first.
    await _flush_webhook_dedup_keys(app)
    r1 = await e2e_client.post("/api/v1/_internal/yookassa/webhook", json=webhook_body)
    assert r1.status_code == 200, r1.text

    # Second delivery — should return 200 silently (dedup or DB backstop).
    r2 = await e2e_client.post("/api/v1/_internal/yookassa/webhook", json=webhook_body)
    assert r2.status_code == 200, r2.text

    # Only one negative Payment row should exist.
    async with e2e_session_factory() as verify_session:
        neg_payments = (
            await verify_session.execute(
                select(Payment).where(Payment.refund_of == original_payment.id)
            )
        ).scalars().all()
        assert len(neg_payments) == 1


async def test_e2e_refund_full_cycle_pt_package(
    app: FastAPI,
    e2e_db_session: AsyncSession,
    e2e_session_factory: async_sessionmaker[AsyncSession],
    e2e_client: AsyncClient,
    yookassa_create_refund_success: Any,
    yookassa_get_refund_succeeded: Any,
    yookassa_create_receipt_ok: Any,
) -> None:
    """SC#4 + SC#5 mirror for PT-packages (REFUND-01 PT-package branch).

    Verifies:
    - POST /pt-packages/{id}/refund → 202
    - refund.succeeded webhook → pt_package status='cancelled' + FiscalReceipt(kind='refund')
    """
    from app.modules.pt_packages.constants import (
        CANCELLATION_REASON_REFUNDED as PT_CANCELLATION_REASON_REFUNDED,
    )

    nonce = uuid4().hex[:6]
    _client, plan, pt_package, op, original_payment = await _seed_pt_package_chain(
        e2e_db_session,
        owner_email=f"e2e-pt-owner-{nonce}@example.com",
    )

    await _flush_webhook_dedup_keys(app)

    await e2e_client.post(
        "/api/v1/auth/login",
        json={"email": f"e2e-pt-owner-{nonce}@example.com", "password": "hunter22hunter22"},
    )
    csrf = e2e_client.cookies.get("sportzal_csrf") or ""

    # Step 1: POST /pt-packages/{id}/refund.
    idem_key = str(uuid4())
    resp = await e2e_client.post(
        f"/api/v1/online-payments/pt-packages/{pt_package.id}/refund",
        json={"idempotencyKey": idem_key, "reason": "customer request"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 202, resp.text
    data = resp.json()["data"]
    online_refund_id = UUID(data["onlineRefundId"])
    yookassa_refund_id = data["yookassaRefundId"]

    # Step 2: Deliver refund.succeeded webhook.
    await _flush_webhook_dedup_keys(app)
    webhook_body = {
        "event": "refund.succeeded",
        "object": {
            "id": yookassa_refund_id,
            "status": "succeeded",
            "amount": {"value": "19.90", "currency": "RUB"},
        },
    }
    webhook_resp = await e2e_client.post(
        "/api/v1/_internal/yookassa/webhook",
        json=webhook_body,
    )
    assert webhook_resp.status_code == 200, webhook_resp.text

    # Step 3: Verify PT-package cancelled + FiscalReceipt inserted.
    async with e2e_session_factory() as verify_session:
        refund_row = await verify_session.get(OnlineRefund, online_refund_id)
        assert refund_row is not None
        assert refund_row.status == "succeeded"

        refund_payment = await verify_session.scalar(
            select(Payment).where(Payment.refund_of == original_payment.id)
        )
        assert refund_payment is not None
        assert refund_payment.amount_kopecks < 0

        fresh_pt_package = await verify_session.get(PtPackage, pt_package.id)
        assert fresh_pt_package is not None
        assert fresh_pt_package.status == "cancelled"
        assert fresh_pt_package.cancellation_reason == PT_CANCELLATION_REASON_REFUNDED

        refund_fr = await verify_session.scalar(
            select(FiscalReceipt).where(
                FiscalReceipt.payment_id == refund_payment.id,
                FiscalReceipt.kind == "refund",
            )
        )
        assert refund_fr is not None
        assert refund_fr.status == "sent"

        # Query audit events by action + resource_id.
        wh_row = await verify_session.scalar(
            select(AuditLog).where(
                AuditLog.action == "yookassa_webhook_received",
                AuditLog.resource_type == "yookassa_webhook",
            ).order_by(AuditLog.created_at.desc()).limit(1)
        )
        assert wh_row is not None, "yookassa_webhook_received audit row missing"

        pt_refunded_row = await verify_session.scalar(
            select(AuditLog).where(
                AuditLog.action == "pt_package_refunded",
                AuditLog.resource_id == pt_package.id,
            )
        )
        assert pt_refunded_row is not None, "pt_package_refunded audit row missing"
