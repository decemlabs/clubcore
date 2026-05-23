"""VER-02(b) — webhook after Redis-restart gap: DB UNIQUE as sole catcher.

Simulates the Redis-restart failure mode: a ``payment.succeeded`` webhook is
delivered once successfully (Redis dedup key written), then the dedup key is
explicitly deleted (``redis.delete``) to model the restart gap, and the SAME
webhook ``object.id`` is re-delivered.

The DB UNIQUE constraint on ``fiscal_receipts(payment_id, kind)``
(``uq_fiscal_receipts_payment_id_kind``) is the SOLE catcher when Redis is
absent — the handler re-enters the atomic UoW, the SELECT-FOR-UPDATE finds
the OnlinePayment already in ``'succeeded'`` status, the FSM guard raises
``InvalidTransitionError``, and the handler returns 200 with
``idempotency_outcome='illegal_transition'`` (D-50-17) — no second DB write
occurs.  Exactly ONE ``online_payments`` status transition + ONE
``fiscal_receipts`` row survive across both deliveries.

SAVEPOINT-masking rationale (see test_payment_succeeded_double_delivery_race.py):
    Real-commit sessions (standalone ``create_async_engine``) are mandatory
    for this test — ``db_session`` SAVEPOINT mode makes the FSM guard invisible
    to the second delivery. D-03 — NO new pytest-postgresql / testcontainers
    dependency.

Pattern source:
  - ``tests/integration/test_concurrent_expiring_cron_double_pings_race.py``
    (inline real-commit engine + ``pytest.skip`` guard).
  - ``tests/integration/payments/test_payments_refund_race.py``
    (``asyncio.gather`` + DB invariant pattern).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
import respx
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.models import User
from app.core.permissions import Role
from app.core.security import hash_password
from app.modules.clients.models import Client
from app.modules.fiscal_receipts.models import FiscalReceipt
from app.modules.memberships.models import MembershipPlan
from app.modules.online_payments.constants import (
    CONFIRMATION_TYPE_REDIRECT,
    STATUS_PENDING,
)
from app.modules.online_payments.models import OnlinePayment

# ---------------------------------------------------------------------------
# VER-02(b) race test — TRUNCATE tables written by the payment.succeeded UoW.
# CASCADE handles FK chains.
# ---------------------------------------------------------------------------
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

_RACE_OWNER_EMAIL = "ver02b-redis-restart-owner@example.com"
_RACE_OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105

# Redis dedup key prefix (mirrors router.py:56).
_WEBHOOK_DEDUP_KEY_PREFIX = "sz:yookassa:webhook:"


@pytest_asyncio.fixture
async def ver02b_engine() -> AsyncIterator[AsyncEngine]:
    """Standalone real-commit engine for the VER-02(b) Redis-restart race test.

    Mirrors ``test_concurrent_expiring_cron_double_pings_race.py:51-91``:
    probes Postgres at fixture entry (skip on unreachable), yields the engine,
    TRUNCATE-CASCADE teardown at exit.  D-03 — NO new dependency.
    """
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)
    try:
        async with engine.connect() as probe:
            await probe.execute(text("select 1"))
    except Exception as exc:  # broad: skip on any connectivity failure
        await engine.dispose()
        pytest.skip(
            f"DATABASE_URL not reachable for VER-02(b); "
            f"run `docker compose up postgres` first ({exc!r})"
        )
    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    f"TRUNCATE {', '.join(_TRUNCATE_TABLES)} RESTART IDENTITY CASCADE"
                )
            )
        await engine.dispose()


async def _seed_pending_online_payment(
    session_factory: async_sessionmaker[AsyncSession],
) -> str:
    """Seed owner + client + membership_plan + pending online_payment.

    Returns the ``yookassa_payment_id`` for the webhook body factory.
    """
    async with session_factory() as setup:
        nonce = uuid4().hex[:8]
        owner = User(
            email=_RACE_OWNER_EMAIL,
            password_hash=await hash_password(_RACE_OWNER_PASSWORD),
            role=Role.OWNER,
            full_name="VER-02b Race Owner",
        )
        setup.add(owner)
        await setup.flush()

        client = Client(
            last_name=f"Restart-{nonce}",
            first_name="VER02b",
            phone=f"+7998{nonce}",
            email=f"ver02b-client-{nonce}@example.com",
            created_by_user_id=owner.id,
        )
        setup.add(client)
        await setup.flush()

        plan = MembershipPlan(
            name=f"VER02b-Plan-{nonce}",
            duration_days=30,
            price_kopecks=100_000,
            freeze_days_limit=7,
            active=True,
        )
        setup.add(plan)
        await setup.flush()

        yk_id = f"yk-ver02b-{uuid4().hex[:20]}"
        op = OnlinePayment(
            client_id=client.id,
            membership_plan_id=plan.id,
            pt_package_plan_id=None,
            yookassa_payment_id=yk_id,
            idempotency_key=uuid4().hex,
            amount_kopecks=100_000,
            status=STATUS_PENDING,
            confirmation_url="https://example.com/confirm",
            confirmation_type=CONFIRMATION_TYPE_REDIRECT,
            audit_correlation_id=uuid4(),
        )
        setup.add(op)
        await setup.flush()
        await setup.commit()
        return yk_id


@pytest.mark.asyncio
async def test_webhook_after_redis_restart_db_unique_is_sole_catcher(
    app: FastAPI,
    ver02b_engine: AsyncEngine,
) -> None:
    """VER-02(b): Redis dedup key flushed between two identical webhook deliveries.

    Sequence:
    1. Deliver ``payment.succeeded`` (1st) → succeeds, writes DB rows, sets
       Redis dedup key ``sz:yookassa:webhook:payment.succeeded:{yk_id}``.
    2. Explicitly DELETE the dedup key (simulates Redis restart gap — key
       evicted / flushed).
    3. Re-deliver the SAME ``payment.succeeded`` webhook (2nd).
    4. The handler re-enters the UoW; SELECT-FOR-UPDATE finds
       ``OnlinePayment.status='succeeded'``; FSM guard raises
       ``InvalidTransitionError`` → handler returns 200 with
       ``idempotency_outcome='illegal_transition'`` (D-50-17).
    5. **No second DB write** — exactly ONE ``fiscal_receipts`` row
       and ONE ``online_payments.status='succeeded'`` transition survive.

    The DB UNIQUE ``uq_fiscal_receipts_payment_id_kind`` is the SOLE catcher
    in this scenario.  Without it, a second INSERT would succeed and corrupt
    the fiscal ledger.
    """
    session_factory = async_sessionmaker(ver02b_engine, expire_on_commit=False)
    yk_payment_id = await _seed_pending_online_payment(session_factory)

    # Flush Redis so dedup keys from prior tests don't interfere.
    await app.state.redis.flushdb()

    from app.core.database import get_db
    from app.core.redis import get_redis

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    def _override_get_redis() -> object:
        return app.state.redis

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis

    webhook_body = {
        "event": "payment.succeeded",
        "object": {
            "id": yk_payment_id,
            "status": "succeeded",
            "amount": {"value": "1000.00", "currency": "RUB"},
        },
    }

    succeeded_refetch = {
        "id": yk_payment_id,
        "status": "succeeded",
        "amount": {"value": "1000.00", "currency": "RUB"},
        "paid": True,
        "refundable": True,
        "receipt_registration": "succeeded",
    }

    try:
        transport = ASGITransport(app=app)

        # ── Step 1: First delivery ───────────────────────────────────────────
        with respx.mock(assert_all_called=False) as mock_router:
            mock_router.get(
                url__regex=r"^https://api\.yookassa\.ru/v3/payments/[\w-]+$"
            ).mock(
                return_value=__import__("httpx").Response(
                    200, json=succeeded_refetch
                )
            )
            async with AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                r1 = await client.post(
                    "/api/v1/_internal/yookassa/webhook", json=webhook_body
                )

        assert r1.status_code == 200, f"1st delivery failed: {r1.text}"

        # ── Step 2: Delete the dedup key to model the Redis restart gap ──────
        dedup_key = f"{_WEBHOOK_DEDUP_KEY_PREFIX}payment.succeeded:{yk_payment_id}"
        deleted = await app.state.redis.delete(dedup_key)
        # The key must have been set by the 1st delivery; deleting it proves
        # the 2nd delivery runs the handler again (gap test, not skip test).
        assert deleted == 1, (
            f"VER-02(b): dedup key '{dedup_key}' was not set by the 1st delivery "
            f"(deleted={deleted}).  Redis dedup must have run."
        )

        # ── Step 3: Re-deliver the identical webhook (restart gap simulated) ─
        with respx.mock(assert_all_called=False) as mock_router2:
            mock_router2.get(
                url__regex=r"^https://api\.yookassa\.ru/v3/payments/[\w-]+$"
            ).mock(
                return_value=__import__("httpx").Response(
                    200, json=succeeded_refetch
                )
            )
            async with AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client2:
                r2 = await client2.post(
                    "/api/v1/_internal/yookassa/webhook", json=webhook_body
                )

        # ЮKassa contract: webhook must receive 2xx.
        assert r2.status_code == 200, f"2nd delivery failed: {r2.text}"

    finally:
        app.dependency_overrides.clear()

    # ── DB invariant: exactly ONE fiscal_receipts row after both deliveries ─
    async with session_factory() as verify:
        fiscal_count = await verify.scalar(
            select(func.count()).select_from(FiscalReceipt)
        )
        assert fiscal_count == 1, (
            f"VER-02(b): expected exactly 1 fiscal_receipts row after 2 deliveries "
            f"(Redis dedup key was absent for the 2nd delivery), got {fiscal_count}. "
            f"DB UNIQUE uq_fiscal_receipts_payment_id_kind is the sole catcher."
        )

        # The OnlinePayment must be 'succeeded' exactly once.
        op_status = await verify.scalar(
            select(OnlinePayment.status).where(
                OnlinePayment.yookassa_payment_id == yk_payment_id
            )
        )
        assert op_status == "succeeded", (
            f"VER-02(b): expected online_payment.status='succeeded', got {op_status!r}"
        )

        # Exactly ONE 'online_payment_succeeded' audit row (no double-emit).
        from app.core.audit_models import AuditLog

        audit_count = await verify.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action == "online_payment_succeeded")
        )
        assert audit_count == 1, (
            f"VER-02(b): expected exactly 1 'online_payment_succeeded' audit row, "
            f"got {audit_count}"
        )

    # VER-02(b) is sequential-not-concurrent by design: the race window is the
    # dedup-key absence between two sequential deliveries, so the DB UNIQUE is
    # the sole catcher (no asyncio.gather needed here).
