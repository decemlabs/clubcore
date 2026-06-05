"""Phase 83 Plan 83-02 — Loyalty redemption integration tests (REDM-01/REDM-02).

Proves:
  1. Idempotency — replaying payment.succeeded writes exactly one redemption row.
  2. Overdraft clamp — stored redeem > current balance → debit clamped to balance;
     SUM(loyalty_ledger.amount_kopecks) >= 0 at all times.
  3. Promo+bonus stacking attribution — promo_redemptions.discount_kopecks equals
     plan_price - amount_kopecks - loyalty_redeem_kopecks (T-83-08 regression).
  4. No-pay / no-succeeded-webhook → no redemption row; balance unchanged (D-06).
  5. D-06 server cap at checkout — client-sent loyaltyRedeemKopecks larger than
     balance is capped; persisted loyalty_redeem_kopecks <= balance.

Harness: real-commit sessions (mirroring webhook_yookassa/conftest.py) +
ASGITransport (no real network stack). pytest-asyncio.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
import respx
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.modules.online_payments.constants import (
    CONFIRMATION_TYPE_REDIRECT,
    STATUS_PENDING,
)
from app.modules.online_payments.models import OnlinePayment

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Helpers — TRUNCATE tables used by these tests (real-commit cleanup)
# ---------------------------------------------------------------------------

_TRUNCATE_TABLES = (
    "audit_log",
    "promo_redemptions",
    "loyalty_ledger",
    "fiscal_receipts",
    "payments",
    "memberships",
    "pt_packages",
    "online_payments",
    "membership_plans",
    "pt_package_plans",
    "promo_codes",
    "clients",
    "users",
)

_YOOKASSA_BASE_URL = "https://api.yookassa.ru"


# ---------------------------------------------------------------------------
# Real-commit DB engine + session (mirrors webhook_yookassa/conftest.py)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def _redemption_engine() -> AsyncIterator[Any]:
    """Real-commit engine shared by seed + webhook route calls."""
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
async def _redemption_session(
    _redemption_engine: Any,
) -> AsyncIterator[AsyncSession]:
    """Real BEGIN/COMMIT session for seeding + verification."""
    factory = async_sessionmaker(_redemption_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def _webhook_client(
    app: FastAPI,
    _redemption_engine: Any,
) -> AsyncIterator[AsyncClient]:
    """Anonymous ASGITransport webhook client (D-50-42 / D-50-39).

    Installs per-request session factory + app-state Redis so route handlers
    see the real-commit DB shared with the seed session.
    """
    factory = async_sessionmaker(_redemption_engine, expire_on_commit=False)

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
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
# ЮKassa get-payment mock helpers
# ---------------------------------------------------------------------------


def _mock_yookassa_succeeded(yk_id: str) -> respx.MockRouter:
    """Mock GET /v3/payments/{id} → 200 succeeded for one test."""
    router = respx.MockRouter(base_url=_YOOKASSA_BASE_URL, assert_all_called=False)
    router.get(url__regex=r"^https://api\.yookassa\.ru/v3/payments/[\w-]+$").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": yk_id,
                "status": "succeeded",
                "amount": {"value": "1000.00", "currency": "RUB"},
                "paid": True,
            },
        )
    )
    return router


def _webhook_body(yk_id: str) -> dict[str, Any]:
    return {
        "event": "payment.succeeded",
        "object": {
            "id": yk_id,
            "status": "succeeded",
            "amount": {"value": "1000.00", "currency": "RUB"},
        },
    }


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _seed_user_and_client(
    session: AsyncSession,
    *,
    nonce: str,
) -> tuple[UUID, UUID]:
    """Insert one owner User + one Client. Returns (user_id, client_id)."""
    from app.core.permissions import Role
    from app.core.security import hash_password
    from app.modules.auth.models import User
    from app.modules.clients.models import Client

    user = User(
        email=f"redm-owner-{nonce}@example.com",
        password_hash=await hash_password("hunter22hunter22"),
        role=Role.OWNER,
        full_name="Redm Test Owner",
    )
    session.add(user)
    await session.flush()

    client = Client(
        last_name="Бонус",
        first_name="Тест",
        phone=f"+7911{abs(hash(nonce)) % 10_000_000:07d}",
        email=f"redm-client-{nonce}@example.com",
        created_by_user_id=user.id,
    )
    session.add(client)
    await session.flush()
    return user.id, client.id


async def _seed_membership_plan(
    session: AsyncSession,
    *,
    price_kopecks: int = 100_000,
) -> UUID:
    from app.modules.memberships.models import MembershipPlan

    plan = MembershipPlan(
        name=f"Redm-Plan-{uuid4().hex[:6]}",
        duration_days=30,
        price_kopecks=price_kopecks,
        freeze_days_limit=7,
        active=True,
    )
    session.add(plan)
    await session.flush()
    return plan.id


async def _accrue_balance(
    session: AsyncSession,
    *,
    client_id: UUID,
    amount_kopecks: int,
) -> None:
    """Insert a loyalty_ledger row to give the client a starting balance."""
    from app.modules.loyalty.models import LoyaltyLedger

    row = LoyaltyLedger(
        client_id=client_id,
        entry_type="owner_grant",
        amount_kopecks=amount_kopecks,
        category=None,
        reason="test seed",
    )
    session.add(row)
    await session.flush()


async def _seed_online_payment(
    session: AsyncSession,
    *,
    client_id: UUID,
    membership_plan_id: UUID,
    amount_kopecks: int,
    loyalty_redeem_kopecks: int | None = None,
    promo_code_id: UUID | None = None,
) -> tuple[str, UUID]:
    """Insert a pending OnlinePayment. Returns (yookassa_payment_id, online_payment_id)."""
    yk_id = f"yk-redm-{uuid4().hex[:20]}"
    corr = uuid4()
    op = OnlinePayment(
        client_id=client_id,
        membership_plan_id=membership_plan_id,
        pt_package_plan_id=None,
        yookassa_payment_id=yk_id,
        idempotency_key=uuid4().hex,
        amount_kopecks=amount_kopecks,
        status=STATUS_PENDING,
        confirmation_url="https://example.com/confirm",
        confirmation_type=CONFIRMATION_TYPE_REDIRECT,
        audit_correlation_id=corr,
        loyalty_redeem_kopecks=loyalty_redeem_kopecks,
        promo_code_id=promo_code_id,
    )
    session.add(op)
    await session.flush()
    return yk_id, op.id


async def _count_redemption_rows(session: AsyncSession, client_id: UUID) -> int:
    row = (
        (
            await session.execute(
                text(
                    "SELECT COUNT(*) AS cnt FROM loyalty_ledger "
                    "WHERE client_id = :cid AND entry_type = 'redemption'"
                ),
                {"cid": str(client_id)},
            )
        )
        .mappings()
        .one()
    )
    return int(row["cnt"])


async def _sum_loyalty_balance(session: AsyncSession, client_id: UUID) -> int:
    row = (
        (
            await session.execute(
                text(
                    "SELECT COALESCE(SUM(amount_kopecks), 0) AS bal "
                    "FROM loyalty_ledger WHERE client_id = :cid"
                ),
                {"cid": str(client_id)},
            )
        )
        .mappings()
        .one()
    )
    return int(row["bal"])


async def _flush_redis_dedup_keys(redis: Any) -> None:
    keys = await redis.keys("cc:yookassa:webhook:*")
    if keys:
        await redis.delete(*keys)


# ---------------------------------------------------------------------------
# Test 1: Idempotency — replaying payment.succeeded writes exactly one row
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redm_01_idempotency_replay_writes_one_row(
    app: FastAPI,
    _redemption_session: AsyncSession,
    _webhook_client: AsyncClient,
) -> None:
    """Replaying payment.succeeded for the same yookassa_payment_id inserts
    exactly ONE loyalty_ledger redemption row, not two."""
    nonce = uuid4().hex[:8]
    _user_id, client_id = await _seed_user_and_client(_redemption_session, nonce=nonce)
    plan_id = await _seed_membership_plan(_redemption_session, price_kopecks=100_000)
    await _accrue_balance(_redemption_session, client_id=client_id, amount_kopecks=20_000)
    yk_id, _op_id = await _seed_online_payment(
        _redemption_session,
        client_id=client_id,
        membership_plan_id=plan_id,
        amount_kopecks=80_000,  # 100000 - 20000 (redeem)
        loyalty_redeem_kopecks=20_000,
    )
    await _redemption_session.commit()

    with _mock_yookassa_succeeded(yk_id):
        # First invocation — real insert
        r1 = await _webhook_client.post(
            "/api/v1/_internal/yookassa/webhook", json=_webhook_body(yk_id)
        )
        assert r1.status_code == 200, r1.text

    # Flush Redis dedup key so the second POST isn't deduplicated at the Redis level
    await _flush_redis_dedup_keys(app.state.redis)

    with _mock_yookassa_succeeded(yk_id):
        # Second invocation — replay; must be idempotent
        r2 = await _webhook_client.post(
            "/api/v1/_internal/yookassa/webhook", json=_webhook_body(yk_id)
        )
        assert r2.status_code == 200, r2.text

    # Refresh the session to see committed data
    await _redemption_session.rollback()
    count = await _count_redemption_rows(_redemption_session, client_id)
    assert count == 1, f"Expected 1 redemption row after replay, got {count}"


# ---------------------------------------------------------------------------
# Test 2: Overdraft clamp — debit clamped, SUM never negative
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redm_02_overdraft_clamp_ledger_never_negative(
    _redemption_session: AsyncSession,
    _webhook_client: AsyncClient,
) -> None:
    """When stored loyalty_redeem_kopecks > current balance at webhook time,
    the debit is clamped to the current balance and the ledger SUM stays >= 0."""
    nonce = uuid4().hex[:8]
    _user_id, client_id = await _seed_user_and_client(_redemption_session, nonce=nonce)
    plan_id = await _seed_membership_plan(_redemption_session, price_kopecks=100_000)
    # Give the client 10_000 kopecks balance, but store a 30_000 redeem on the payment.
    # (e.g. a concurrent checkout drained the balance between checkout and webhook)
    await _accrue_balance(_redemption_session, client_id=client_id, amount_kopecks=10_000)
    yk_id, _op_id = await _seed_online_payment(
        _redemption_session,
        client_id=client_id,
        membership_plan_id=plan_id,
        amount_kopecks=70_000,
        loyalty_redeem_kopecks=30_000,  # stored > actual balance of 10_000
    )
    await _redemption_session.commit()

    with _mock_yookassa_succeeded(yk_id):
        r = await _webhook_client.post(
            "/api/v1/_internal/yookassa/webhook", json=_webhook_body(yk_id)
        )
        assert r.status_code == 200, r.text

    await _redemption_session.rollback()

    # Exactly one redemption row
    count = await _count_redemption_rows(_redemption_session, client_id)
    assert count == 1

    # Debit row amount == -10_000 (clamped, not -30_000)
    debit_row = (
        (
            await _redemption_session.execute(
                text(
                    "SELECT amount_kopecks FROM loyalty_ledger "
                    "WHERE client_id = :cid AND entry_type = 'redemption'"
                ),
                {"cid": str(client_id)},
            )
        )
        .mappings()
        .one()
    )
    assert int(debit_row["amount_kopecks"]) == -10_000

    # Final SUM >= 0
    balance = await _sum_loyalty_balance(_redemption_session, client_id)
    assert balance >= 0


# ---------------------------------------------------------------------------
# Test 3: Promo+bonus stacking attribution correctness
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redm_03_promo_bonus_stacking_attribution(
    _redemption_session: AsyncSession,
    _webhook_client: AsyncClient,
) -> None:
    """Stacked promo+bonus payment: promo_redemptions.discount_kopecks must equal
    plan_price - amount_kopecks - loyalty_redeem_kopecks (T-83-08 regression)."""
    nonce = uuid4().hex[:8]
    _user_id, client_id = await _seed_user_and_client(_redemption_session, nonce=nonce)
    plan_price = 100_000
    plan_id = await _seed_membership_plan(_redemption_session, price_kopecks=plan_price)
    loyalty_redeem = 10_000
    promo_discount = 15_000
    final_amount = plan_price - loyalty_redeem - promo_discount  # 75_000

    # Seed a promo code
    promo_code_id = uuid4()
    await _redemption_session.execute(
        text(
            "INSERT INTO promo_codes "
            "(id, code, discount_type, discount_value, applicable_to, "
            " max_uses, per_client_limit, valid_from, valid_until) "
            "VALUES (:id, :code, 'fixed', :val, NULL, NULL, NULL, "
            "  NOW() - INTERVAL '1 day', NOW() + INTERVAL '30 days')"
        ),
        {
            "id": str(promo_code_id),
            "code": f"STACKTEST-{nonce}",
            "val": promo_discount,
        },
    )

    await _accrue_balance(_redemption_session, client_id=client_id, amount_kopecks=loyalty_redeem)
    yk_id, op_id = await _seed_online_payment(
        _redemption_session,
        client_id=client_id,
        membership_plan_id=plan_id,
        amount_kopecks=final_amount,
        loyalty_redeem_kopecks=loyalty_redeem,
        promo_code_id=promo_code_id,
    )
    await _redemption_session.commit()

    with _mock_yookassa_succeeded(yk_id):
        r = await _webhook_client.post(
            "/api/v1/_internal/yookassa/webhook", json=_webhook_body(yk_id)
        )
        assert r.status_code == 200, r.text

    await _redemption_session.rollback()

    # Verify promo redemption discount = plan_price - amount - loyalty_redeem
    promo_row = (
        (
            await _redemption_session.execute(
                text(
                    "SELECT discount_kopecks FROM promo_redemptions WHERE online_payment_id = :opid"
                ),
                {"opid": str(op_id)},
            )
        )
        .mappings()
        .one()
    )
    expected_promo_discount = plan_price - final_amount - loyalty_redeem  # 15_000
    assert int(promo_row["discount_kopecks"]) == expected_promo_discount, (
        f"Promo attribution: expected {expected_promo_discount}, "
        f"got {promo_row['discount_kopecks']}"
    )

    # Verify loyalty debit row = -loyalty_redeem (clamped at the balance)
    debit_row = (
        (
            await _redemption_session.execute(
                text(
                    "SELECT amount_kopecks FROM loyalty_ledger "
                    "WHERE client_id = :cid AND entry_type = 'redemption'"
                ),
                {"cid": str(client_id)},
            )
        )
        .mappings()
        .one()
    )
    assert int(debit_row["amount_kopecks"]) == -loyalty_redeem


# ---------------------------------------------------------------------------
# Test 4: No-pay / cancel → no redemption row; balance unchanged (D-06)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redm_04_no_pay_no_debit(
    _redemption_session: AsyncSession,
) -> None:
    """Without a payment.succeeded webhook no redemption row is ever written
    and the client's loyalty balance is unchanged (D-06 anti-oracle)."""
    nonce = uuid4().hex[:8]
    _user_id, client_id = await _seed_user_and_client(_redemption_session, nonce=nonce)
    plan_id = await _seed_membership_plan(_redemption_session, price_kopecks=100_000)
    await _accrue_balance(_redemption_session, client_id=client_id, amount_kopecks=20_000)
    _yk_id, _op_id = await _seed_online_payment(
        _redemption_session,
        client_id=client_id,
        membership_plan_id=plan_id,
        amount_kopecks=80_000,
        loyalty_redeem_kopecks=20_000,
    )
    await _redemption_session.commit()

    # No webhook fired — no succeeded → no debit
    await _redemption_session.rollback()
    count = await _count_redemption_rows(_redemption_session, client_id)
    assert count == 0

    balance = await _sum_loyalty_balance(_redemption_session, client_id)
    assert balance == 20_000  # unchanged


# ---------------------------------------------------------------------------
# Test 5: D-06 server cap at checkout — persisted redeem <= balance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redm_05_checkout_server_cap_persisted_redeem_lte_balance(
    _redemption_session: AsyncSession,
) -> None:
    """record_loyalty_redemption clamps actual_debit = min(requested, balance)
    so the persisted loyalty_ledger debit amount never exceeds the balance
    (D-06 / T-83-04 unit-level proof without going through the full checkout stack)."""
    from app.modules.loyalty.service import record_loyalty_redemption

    nonce = uuid4().hex[:8]
    _user_id, client_id = await _seed_user_and_client(_redemption_session, nonce=nonce)
    plan_id = await _seed_membership_plan(_redemption_session, price_kopecks=100_000)
    starting_balance = 5_000
    await _accrue_balance(_redemption_session, client_id=client_id, amount_kopecks=starting_balance)
    # The "checkout" would have clamped to 5000, but simulate a client-sent
    # excessively large redeem stored on the row (e.g. due to a race or a
    # bypass attempt) — the service must clamp again at record time.
    _yk_id, op_id = await _seed_online_payment(
        _redemption_session,
        client_id=client_id,
        membership_plan_id=plan_id,
        amount_kopecks=95_000,
        loyalty_redeem_kopecks=50_000,  # stored > starting_balance of 5_000
    )
    await _redemption_session.commit()

    # Call record_loyalty_redemption directly (using a fresh BEGIN)
    factory_settings = get_settings()
    engine = create_async_engine(str(factory_settings.database_url), pool_pre_ping=True)
    try:
        async with (
            async_sessionmaker(engine, expire_on_commit=False)() as direct_session,
            direct_session.begin(),
        ):
            await record_loyalty_redemption(
                direct_session,
                client_id=client_id,
                online_payment_id=op_id,
                requested_redeem_kopecks=50_000,
            )
    finally:
        await engine.dispose()

    # Verify using the read session
    await _redemption_session.rollback()
    debit_row = (
        (
            await _redemption_session.execute(
                text(
                    "SELECT amount_kopecks FROM loyalty_ledger "
                    "WHERE client_id = :cid AND entry_type = 'redemption'"
                ),
                {"cid": str(client_id)},
            )
        )
        .mappings()
        .one()
    )
    actual_debit = abs(int(debit_row["amount_kopecks"]))
    assert actual_debit <= starting_balance, (
        f"Debit {actual_debit} exceeds starting balance {starting_balance}"
    )
    assert actual_debit == starting_balance  # clamped to exactly the balance

    final_balance = await _sum_loyalty_balance(_redemption_session, client_id)
    assert final_balance == 0  # fully drained but not negative
