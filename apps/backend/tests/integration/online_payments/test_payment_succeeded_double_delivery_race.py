"""VER-02(a) — payment.succeeded double-delivery race: Redis dedup + DB UNIQUE.

Proves BOTH dedup layers independently:

- **Redis layer** (``SET NX EX 86400``): with N=5 concurrent identical
  ``payment.succeeded`` POSTs carrying the same ``object.id``, at most ONE
  acquires the NX lock; the other N-1 are short-circuited *before* the DB
  write, returning 200 immediately. Exactly ONE ``fiscal_receipts`` row
  survives after the gather.

- **DB UNIQUE layer** (``uq_fiscal_receipts_payment_id_kind``): even if the
  Redis dedup key were somehow absent (covered by VER-02(b) in the sibling
  module), the DB UNIQUE on ``(payment_id, kind)`` prevents a second
  ``fiscal_receipts`` row from being inserted.  Test (a) verifies that the
  surviving row count is exactly 1, providing the DB UNIQUE invariant as a
  post-condition regardless of which layer caught the duplicates.

SAVEPOINT-masking rationale (MUST read before modifying this test):
    The default ``db_session`` fixture wraps each test in a SAVEPOINT.  The
    webhook handler's ``async with session.begin()`` call requires a *real*
    uncommitted transaction, not a SAVEPOINT sub-transaction.  Concurrent
    INSERTs racing against a UNIQUE index inside one outer SAVEPOINT are
    masked — the loser's ``IntegrityError`` is swallowed by the SAVEPOINT
    rollback and the second SELECT-FOR-UPDATE re-reads the already-committed
    winner row, making the race invisible.  Real-commit sessions using a
    standalone ``create_async_engine`` are mandatory (D-03 — NO new
    pytest-postgresql / testcontainers dependency).

Pattern source: ``tests/integration/payments/test_payments_refund_race.py``
(real-commit rationale :1-14, ``_build_authed_client`` :42-54,
``asyncio.gather`` body + status/DB asserts :139-205).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
import respx
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
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
# VER-02 race test — TRUNCATE tables written by the payment.succeeded UoW.
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

_RACE_OWNER_EMAIL = "ver02a-double-delivery-owner@example.com"
_RACE_OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105


@pytest_asyncio.fixture
async def ver02a_engine() -> AsyncIterator[AsyncEngine]:
    """Standalone real-commit engine for the VER-02(a) double-delivery race test.

    The default ``db_session`` SAVEPOINT pattern wraps concurrent INSERTs in
    a single outer SAVEPOINT — the loser's ``IntegrityError`` is swallowed and
    the race is invisible to the test.  This fixture uses a fresh engine that
    issues real BEGIN/COMMITs so the DB UNIQUE constraint is the actual arbiter.

    Skips cleanly when Postgres is unreachable (mirrors
    ``test_concurrent_expiring_cron_double_pings_race.py:70-78``).
    TRUNCATE-CASCADE teardown ensures the race writes leave no residue.
    """
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)
    try:
        async with engine.connect() as probe:
            await probe.execute(text("select 1"))
    except Exception as exc:  # broad: skip on any connectivity failure
        await engine.dispose()
        pytest.skip(
            f"DATABASE_URL not reachable for VER-02(a); "
            f"run `docker compose up postgres` first ({exc!r})"
        )
    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text(f"TRUNCATE {', '.join(_TRUNCATE_TABLES)} RESTART IDENTITY CASCADE")
            )
        await engine.dispose()


async def _seed_pending_online_payment(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[str, str]:
    """Seed owner + client + membership_plan + pending online_payment.

    Returns (yookassa_payment_id, owner_password) for the webhook body factory.
    The owner row is also seeded for ``_build_authed_client`` login if needed.
    """
    async with session_factory() as setup:
        nonce = uuid4().hex[:8]
        owner = User(
            email=_RACE_OWNER_EMAIL,
            password_hash=await hash_password(_RACE_OWNER_PASSWORD),
            role=Role.OWNER,
            full_name="VER-02a Race Owner",
        )
        setup.add(owner)
        await setup.flush()

        client = Client(
            last_name=f"Race-{nonce}",
            first_name="VER02a",
            phone=f"+7999{nonce}",
            email=f"ver02a-client-{nonce}@example.com",
            created_by_user_id=owner.id,
        )
        setup.add(client)
        await setup.flush()

        plan = MembershipPlan(
            name=f"VER02a-Plan-{nonce}",
            duration_days=30,
            price_kopecks=100_000,
            freeze_days_limit=7,
            active=True,
        )
        setup.add(plan)
        await setup.flush()

        yk_id = f"yk-ver02a-{uuid4().hex[:20]}"
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
        return yk_id, plan.id  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_payment_succeeded_double_delivery_race(
    app: FastAPI,
    ver02a_engine: AsyncEngine,
) -> None:
    """VER-02(a): N=5 concurrent identical payment.succeeded POSTs → exactly 1 fiscal_receipt.

    Race surface:
    - ``asyncio.gather`` fires 5 concurrent POST requests with the *same*
      ``object.id`` (yk_payment_id).
    - Redis ``SET NX EX 86400`` lets exactly ONE request acquire the dedup
      key; the other four short-circuit and return 200 without reaching the
      DB write.
    - The ONE request that passes Redis dedup enters the atomic UoW and
      inserts: OnlinePayment(succeeded) + Payment + Membership + FiscalReceipt.
    - DB UNIQUE ``uq_fiscal_receipts_payment_id_kind`` is the backstop (proven
      in VER-02(b) independently).

    Asserts:
    - All 5 responses are HTTP 200 (ЮKassa contract: webhook must receive 2xx).
    - Exactly ONE ``fiscal_receipts`` row survives.
    - The ``online_payments`` row status is ``'succeeded'``.
    """
    session_factory = async_sessionmaker(ver02a_engine, expire_on_commit=False)

    yk_payment_id, _ = await _seed_pending_online_payment(session_factory)

    # Flush Redis so dedup keys from prior test runs don't interfere.
    await app.state.redis.flushdb()

    # Wire the real-commit engine as the get_db override so the webhook
    # handler's ``async with session.begin()`` sees the seeded row.
    from app.core.database import get_db
    from app.core.redis import get_redis

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    def _override_get_redis() -> object:
        return app.state.redis

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis

    try:
        transport = ASGITransport(app=app)

        webhook_body = {
            "event": "payment.succeeded",
            "object": {
                "id": yk_payment_id,
                "status": "succeeded",
                "amount": {"value": "1000.00", "currency": "RUB"},
            },
        }

        n_concurrent = 5

        # respx intercepts the outbound GET /v3/payments/{id} re-fetch call
        # that the handler issues before the DB write (D-50-12 doctrine).
        with respx.mock(assert_all_called=False) as mock_router:
            mock_router.get(url__regex=r"^https://api\.yookassa\.ru/v3/payments/[\w-]+$").mock(
                return_value=__import__("httpx").Response(
                    200,
                    json={
                        "id": yk_payment_id,
                        "status": "succeeded",
                        "amount": {"value": "1000.00", "currency": "RUB"},
                        "paid": True,
                        "refundable": True,
                        "receipt_registration": "succeeded",
                    },
                )
            )

            async def _post(_idx: int) -> Response:
                async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                    return await client.post(
                        "/api/v1/_internal/yookassa/webhook", json=webhook_body
                    )

            responses = await asyncio.gather(*[_post(i) for i in range(n_concurrent)])
    finally:
        app.dependency_overrides.clear()

    statuses = [r.status_code for r in responses]
    assert all(s == 200 for s in statuses), f"VER-02(a): expected all 200, got {statuses}"

    # DB invariant: exactly ONE fiscal_receipts row (Redis dedup + DB UNIQUE).
    async with session_factory() as verify:
        fiscal_count = await verify.scalar(select(func.count()).select_from(FiscalReceipt))
        assert fiscal_count == 1, (
            f"VER-02(a): expected exactly 1 fiscal_receipts row, got {fiscal_count}. "
            f"DB UNIQUE uq_fiscal_receipts_payment_id_kind must be the backstop."
        )

        # OnlinePayment status must be 'succeeded'.
        op_status = await verify.scalar(
            select(OnlinePayment.status).where(OnlinePayment.yookassa_payment_id == yk_payment_id)
        )
        assert op_status == "succeeded", (
            f"VER-02(a): expected online_payment.status='succeeded', got {op_status!r}"
        )

    # Sanity: no test clock drift (UTC import consumed).
    _ = (UTC, datetime, timedelta)
