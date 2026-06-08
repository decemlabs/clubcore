"""Phase 97 Plan 97-03 — Referral crediting integration tests (REFER-04).

Proves all REFER-04 invariants via the real-commit engine + respx YooKassa mock:

  1. Happy path — first membership payment.succeeded for a referee with a capture →
     exactly 2 referral_accrual loyalty_ledger rows (referrer + referee) with
     config-sourced amounts, plus 2 referral_bonus_accrued audit_log rows.
  2. Replay (idempotency) — re-deliver the same webhook → totals stay at 2+2
     (partial UNIQUE + RETURNING-gate prevents double insertion).
  3. Second purchase — second succeeded membership payment for the same referee →
     no new accrual rows; first-purchase gate holds.
  4. No capture — payment for a client with no referral_captures row → 0 accrual rows.
  5. Referrer soft-deleted — referrer.deleted_at set before webhook → 0 accrual rows
     (entire accrual voided, referee NOT credited).
  6. PT-package — pt_package payment.succeeded → 0 accrual rows (membership-only guard).
  7. Config missing — no seeded config (or config amounts == 0) → 0 accrual rows
     (graceful no-op).

Harness: real-commit sessions + ASGITransport (httpx, no real network — CLAUDE.md).
respx mocks YooKassa GET /v3/payments/{id} responses.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
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
# Constants
# ---------------------------------------------------------------------------

_YOOKASSA_BASE_URL = "https://api.yookassa.ru"

# referral_config is NOT in this list — the seed row must survive across cases.
# referral_captures + referral_codes ARE truncated per test isolation.
_TRUNCATE_TABLES = (
    "audit_log",
    "loyalty_ledger",
    "referral_captures",
    "referral_codes",
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

# Deterministic singleton PK seeded by migration 0068 for referral_config.
_REFERRAL_CONFIG_ID = "00000000-0000-0000-0000-000000000002"

# ---------------------------------------------------------------------------
# Real-commit DB engine + session fixtures (mirror test_loyalty_redemption.py)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def _credit_engine() -> AsyncIterator[Any]:
    """Real-commit engine shared by seed + webhook route calls.

    TRUNCATE runs in teardown so each test module run starts clean.
    referral_config is excluded from truncation — the seed row must persist.
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
async def _credit_session(
    _credit_engine: Any,
) -> AsyncIterator[AsyncSession]:
    """Real BEGIN/COMMIT session for seeding + verification queries."""
    factory = async_sessionmaker(_credit_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def _webhook_client(
    app: FastAPI,
    _credit_engine: Any,
) -> AsyncIterator[AsyncClient]:
    """Anonymous ASGITransport webhook client using the real-commit DB engine."""
    factory = async_sessionmaker(_credit_engine, expire_on_commit=False)

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
# YooKassa mock helpers
# ---------------------------------------------------------------------------


def _mock_yookassa_succeeded(yk_id: str) -> respx.MockRouter:
    """Mock GET /v3/payments/{id} → 200 succeeded."""
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
    soft_delete: bool = False,
) -> tuple[UUID, UUID]:
    """Insert one owner User + one Client. Returns (user_id, client_id)."""
    from app.core.permissions import Role
    from app.core.security import hash_password
    from app.modules.auth.models import User
    from app.modules.clients.models import Client

    user = User(
        email=f"ref-cred-owner-{nonce}@example.com",
        password_hash=await hash_password("hunter22hunter22"),
        role=Role.OWNER,
        full_name="Ref Cred Test Owner",
    )
    session.add(user)
    await session.flush()

    client = Client(
        last_name="Реф",
        first_name="Тест",
        phone=f"+7912{abs(hash(nonce)) % 10_000_000:07d}",
        email=f"ref-cred-{nonce}@example.com",
        created_by_user_id=user.id,
    )
    if soft_delete:
        client.deleted_at = datetime.now(UTC)
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
        name=f"Ref-Plan-{uuid4().hex[:6]}",
        duration_days=30,
        price_kopecks=price_kopecks,
        freeze_days_limit=7,
        active=True,
    )
    session.add(plan)
    await session.flush()
    return plan.id


async def _seed_pt_package_plan(session: AsyncSession) -> UUID:
    from app.modules.pt_packages.models import PtPackagePlan

    plan = PtPackagePlan(
        name=f"PT-Plan-{uuid4().hex[:6]}",
        session_count=10,
        price_kopecks=50_000,
    )
    session.add(plan)
    await session.flush()
    return plan.id


async def _seed_referral_code(
    session: AsyncSession,
    *,
    client_id: UUID,
) -> UUID:
    """Insert a referral_codes row for client_id. Returns the row id."""
    from app.modules.referrals.models import ReferralCode

    code_str = f"REF{uuid4().hex[:8].upper()}"
    rc = ReferralCode(client_id=client_id, code=code_str)
    session.add(rc)
    await session.flush()
    return rc.id


async def _seed_referral_capture(
    session: AsyncSession,
    *,
    referee_client_id: UUID,
    referrer_client_id: UUID,
    referral_code_id: UUID,
) -> UUID:
    """Insert a referral_captures row binding referee → referrer. Returns the row id."""
    from app.modules.referrals.models import ReferralCapture

    capture = ReferralCapture(
        referee_client_id=referee_client_id,
        referrer_client_id=referrer_client_id,
        referral_code_id=referral_code_id,
    )
    session.add(capture)
    await session.flush()
    return capture.id


async def _ensure_referral_config(
    session: AsyncSession,
    *,
    referrer_bonus_kopecks: int = 50_000,
    referee_welcome_kopecks: int = 30_000,
) -> None:
    """Upsert the referral_config singleton to the given amounts.

    Uses raw SQL so the referral_config table structure is not assumed to have
    any particular ORM hooks.
    """
    existing = (
        await session.execute(
            text("SELECT id FROM referral_config WHERE id = :id"),
            {"id": _REFERRAL_CONFIG_ID},
        )
    ).fetchone()
    if existing is None:
        await session.execute(
            text(
                "INSERT INTO referral_config (id, referrer_bonus_kopecks, referee_welcome_kopecks) "
                "VALUES (:id, :ref_bonus, :ref_welcome)"
            ),
            {
                "id": _REFERRAL_CONFIG_ID,
                "ref_bonus": referrer_bonus_kopecks,
                "ref_welcome": referee_welcome_kopecks,
            },
        )
    else:
        await session.execute(
            text(
                "UPDATE referral_config SET referrer_bonus_kopecks = :ref_bonus, "
                "referee_welcome_kopecks = :ref_welcome WHERE id = :id"
            ),
            {
                "id": _REFERRAL_CONFIG_ID,
                "ref_bonus": referrer_bonus_kopecks,
                "ref_welcome": referee_welcome_kopecks,
            },
        )


async def _seed_online_payment_membership(
    session: AsyncSession,
    *,
    client_id: UUID,
    membership_plan_id: UUID,
    amount_kopecks: int = 100_000,
    status: str = STATUS_PENDING,
) -> tuple[str, UUID]:
    """Seed a membership OnlinePayment. Returns (yookassa_payment_id, online_payment_id)."""
    yk_id = f"yk-ref-{uuid4().hex[:20]}"
    op = OnlinePayment(
        client_id=client_id,
        membership_plan_id=membership_plan_id,
        pt_package_plan_id=None,
        yookassa_payment_id=yk_id,
        idempotency_key=uuid4().hex,
        amount_kopecks=amount_kopecks,
        status=status,
        confirmation_url="https://example.com/confirm",
        confirmation_type=CONFIRMATION_TYPE_REDIRECT,
        audit_correlation_id=uuid4(),
    )
    session.add(op)
    await session.flush()
    return yk_id, op.id


async def _seed_online_payment_pt(
    session: AsyncSession,
    *,
    client_id: UUID,
    pt_package_plan_id: UUID,
    amount_kopecks: int = 50_000,
) -> tuple[str, UUID]:
    """Seed a PT-package OnlinePayment (not membership). Returns (yk_id, op_id)."""
    yk_id = f"yk-pt-{uuid4().hex[:20]}"
    op = OnlinePayment(
        client_id=client_id,
        membership_plan_id=None,
        pt_package_plan_id=pt_package_plan_id,
        yookassa_payment_id=yk_id,
        idempotency_key=uuid4().hex,
        amount_kopecks=amount_kopecks,
        status=STATUS_PENDING,
        confirmation_url="https://example.com/confirm",
        confirmation_type=CONFIRMATION_TYPE_REDIRECT,
        audit_correlation_id=uuid4(),
    )
    session.add(op)
    await session.flush()
    return yk_id, op.id


async def _flush_redis_dedup_keys(redis: Any) -> None:
    keys = await redis.keys("cc:yookassa:webhook:*")
    if keys:
        await redis.delete(*keys)


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


async def _count_referral_accrual_rows(
    session: AsyncSession,
) -> int:
    """Count all referral_accrual rows in loyalty_ledger."""
    row = (
        (
            await session.execute(
                text(
                    "SELECT COUNT(*) AS cnt FROM loyalty_ledger "
                    "WHERE entry_type = 'referral_accrual'"
                )
            )
        )
        .mappings()
        .one()
    )
    return int(row["cnt"])


async def _count_referral_bonus_accrued_audit_rows(
    session: AsyncSession,
) -> int:
    """Count audit_log rows with action='referral_bonus_accrued'."""
    row = (
        (
            await session.execute(
                text(
                    "SELECT COUNT(*) AS cnt FROM audit_log "
                    "WHERE action = 'referral_bonus_accrued'"
                )
            )
        )
        .mappings()
        .one()
    )
    return int(row["cnt"])


# ---------------------------------------------------------------------------
# Case 1: Happy path — first membership payment for a captured referee
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ref_cred_01_happy_path_dual_credit(
    app: FastAPI,
    _credit_session: AsyncSession,
    _webhook_client: AsyncClient,
) -> None:
    """First membership payment.succeeded for a captured referee:
    exactly 2 referral_accrual loyalty_ledger rows (one referrer, one referee)
    with amounts equal to the seeded config values, plus 2 referral_bonus_accrued
    audit_log rows. Atomicity: count is 2, never 1."""
    nonce_r = uuid4().hex[:8]
    nonce_e = uuid4().hex[:8]
    _u_r, referrer_id = await _seed_user_and_client(_credit_session, nonce=nonce_r)
    _u_e, referee_id = await _seed_user_and_client(_credit_session, nonce=nonce_e)
    plan_id = await _seed_membership_plan(_credit_session)

    # Seed config with known amounts
    referrer_bonus = 50_000
    referee_welcome = 30_000
    await _ensure_referral_config(
        _credit_session,
        referrer_bonus_kopecks=referrer_bonus,
        referee_welcome_kopecks=referee_welcome,
    )

    # Wire referee → referrer via capture
    code_id = await _seed_referral_code(_credit_session, client_id=referrer_id)
    await _seed_referral_capture(
        _credit_session,
        referee_client_id=referee_id,
        referrer_client_id=referrer_id,
        referral_code_id=code_id,
    )

    yk_id, _op_id = await _seed_online_payment_membership(
        _credit_session,
        client_id=referee_id,
        membership_plan_id=plan_id,
    )
    await _credit_session.commit()

    with _mock_yookassa_succeeded(yk_id):
        r = await _webhook_client.post(
            "/api/v1/_internal/yookassa/webhook", json=_webhook_body(yk_id)
        )
    assert r.status_code == 200, r.text

    # Refresh session to see committed data
    await _credit_session.rollback()

    accrual_count = await _count_referral_accrual_rows(_credit_session)
    assert accrual_count == 2, f"Expected 2 referral_accrual rows, got {accrual_count}"

    audit_count = await _count_referral_bonus_accrued_audit_rows(_credit_session)
    assert audit_count == 2, f"Expected 2 referral_bonus_accrued audit rows, got {audit_count}"

    # Assert amounts match config values (not hardcoded)
    rows = (
        (
            await _credit_session.execute(
                text(
                    "SELECT client_id, amount_kopecks FROM loyalty_ledger "
                    "WHERE entry_type = 'referral_accrual' ORDER BY amount_kopecks DESC"
                )
            )
        )
        .mappings()
        .all()
    )
    amounts = {int(r["amount_kopecks"]) for r in rows}
    assert referrer_bonus in amounts, (
        f"referrer_bonus {referrer_bonus} not in accrual amounts {amounts}"
    )
    assert referee_welcome in amounts, (
        f"referee_welcome {referee_welcome} not in accrual amounts {amounts}"
    )

    client_ids = {str(r["client_id"]) for r in rows}
    assert str(referrer_id) in client_ids
    assert str(referee_id) in client_ids


# ---------------------------------------------------------------------------
# Case 2: Replay (idempotency) — same webhook re-delivered
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ref_cred_02_replay_is_idempotent(
    app: FastAPI,
    _credit_session: AsyncSession,
    _webhook_client: AsyncClient,
) -> None:
    """Re-delivering the same yookassa webhook (same online_payment_id) must remain
    at exactly 2 referral_accrual rows and 2 audit rows — partial UNIQUE + RETURNING
    gate ensures the second delivery inserts nothing and emits nothing."""
    nonce_r = uuid4().hex[:8]
    nonce_e = uuid4().hex[:8]
    _u_r, referrer_id = await _seed_user_and_client(_credit_session, nonce=nonce_r)
    _u_e, referee_id = await _seed_user_and_client(_credit_session, nonce=nonce_e)
    plan_id = await _seed_membership_plan(_credit_session)

    await _ensure_referral_config(_credit_session)

    code_id = await _seed_referral_code(_credit_session, client_id=referrer_id)
    await _seed_referral_capture(
        _credit_session,
        referee_client_id=referee_id,
        referrer_client_id=referrer_id,
        referral_code_id=code_id,
    )

    yk_id, _op_id = await _seed_online_payment_membership(
        _credit_session,
        client_id=referee_id,
        membership_plan_id=plan_id,
    )
    await _credit_session.commit()

    # First delivery
    with _mock_yookassa_succeeded(yk_id):
        r1 = await _webhook_client.post(
            "/api/v1/_internal/yookassa/webhook", json=_webhook_body(yk_id)
        )
    assert r1.status_code == 200, r1.text

    # Flush Redis dedup key so the second POST is not short-circuited at Redis level
    await _flush_redis_dedup_keys(app.state.redis)

    # Second delivery (replay)
    with _mock_yookassa_succeeded(yk_id):
        r2 = await _webhook_client.post(
            "/api/v1/_internal/yookassa/webhook", json=_webhook_body(yk_id)
        )
    assert r2.status_code == 200, r2.text

    await _credit_session.rollback()

    accrual_count = await _count_referral_accrual_rows(_credit_session)
    assert accrual_count == 2, (
        f"After replay: expected still 2 referral_accrual rows, got {accrual_count}"
    )

    audit_count = await _count_referral_bonus_accrued_audit_rows(_credit_session)
    assert audit_count == 2, (
        f"After replay: expected still 2 audit rows, got {audit_count}"
    )


# ---------------------------------------------------------------------------
# Case 3: Second purchase — first-purchase gate holds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ref_cred_03_second_purchase_no_new_accrual(
    app: FastAPI,
    _credit_session: AsyncSession,
    _webhook_client: AsyncClient,
) -> None:
    """A second succeeded membership payment for the same referee must produce
    no new referral_accrual rows beyond the first purchase's 2."""
    nonce_r = uuid4().hex[:8]
    nonce_e = uuid4().hex[:8]
    _u_r, referrer_id = await _seed_user_and_client(_credit_session, nonce=nonce_r)
    _u_e, referee_id = await _seed_user_and_client(_credit_session, nonce=nonce_e)
    plan_id = await _seed_membership_plan(_credit_session)

    await _ensure_referral_config(_credit_session)

    code_id = await _seed_referral_code(_credit_session, client_id=referrer_id)
    await _seed_referral_capture(
        _credit_session,
        referee_client_id=referee_id,
        referrer_client_id=referrer_id,
        referral_code_id=code_id,
    )

    # First payment
    yk_id1, _op_id1 = await _seed_online_payment_membership(
        _credit_session,
        client_id=referee_id,
        membership_plan_id=plan_id,
    )
    await _credit_session.commit()

    with _mock_yookassa_succeeded(yk_id1):
        r1 = await _webhook_client.post(
            "/api/v1/_internal/yookassa/webhook", json=_webhook_body(yk_id1)
        )
    assert r1.status_code == 200, r1.text

    await _credit_session.rollback()
    after_first = await _count_referral_accrual_rows(_credit_session)
    assert after_first == 2

    # Second payment — a new yookassa_id, different membership plan to avoid
    # the uq_online_payments_membership_double_tap UNIQUE constraint (same client+plan+date).
    await _flush_redis_dedup_keys(app.state.redis)
    plan_id2 = await _seed_membership_plan(_credit_session)
    yk_id2, _op_id2 = await _seed_online_payment_membership(
        _credit_session,
        client_id=referee_id,
        membership_plan_id=plan_id2,
    )
    await _credit_session.commit()

    with _mock_yookassa_succeeded(yk_id2):
        r2 = await _webhook_client.post(
            "/api/v1/_internal/yookassa/webhook", json=_webhook_body(yk_id2)
        )
    assert r2.status_code == 200, r2.text

    await _credit_session.rollback()
    after_second = await _count_referral_accrual_rows(_credit_session)
    assert after_second == 2, (
        f"After second purchase: expected still 2 referral_accrual rows, got {after_second}"
    )


# ---------------------------------------------------------------------------
# Case 4: No capture — referee has no referral_captures row
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ref_cred_04_no_capture_no_accrual(
    _credit_session: AsyncSession,
    _webhook_client: AsyncClient,
) -> None:
    """Payment for a client who was never captured → 0 referral_accrual rows."""
    nonce = uuid4().hex[:8]
    _u, client_id = await _seed_user_and_client(_credit_session, nonce=nonce)
    plan_id = await _seed_membership_plan(_credit_session)
    await _ensure_referral_config(_credit_session)

    yk_id, _op_id = await _seed_online_payment_membership(
        _credit_session,
        client_id=client_id,
        membership_plan_id=plan_id,
    )
    await _credit_session.commit()

    with _mock_yookassa_succeeded(yk_id):
        r = await _webhook_client.post(
            "/api/v1/_internal/yookassa/webhook", json=_webhook_body(yk_id)
        )
    assert r.status_code == 200, r.text

    await _credit_session.rollback()
    accrual_count = await _count_referral_accrual_rows(_credit_session)
    assert accrual_count == 0, f"Expected 0 rows (no capture), got {accrual_count}"


# ---------------------------------------------------------------------------
# Case 5: Referrer soft-deleted — entire accrual voided
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ref_cred_05_referrer_deleted_voids_accrual(
    _credit_session: AsyncSession,
    _webhook_client: AsyncClient,
) -> None:
    """When the referrer is soft-deleted at webhook time, the entire accrual is
    voided — neither the referrer nor the referee receives a bonus."""
    nonce_r = uuid4().hex[:8]
    nonce_e = uuid4().hex[:8]
    # Create referrer as soft-deleted
    _u_r, referrer_id = await _seed_user_and_client(
        _credit_session, nonce=nonce_r, soft_delete=True
    )
    _u_e, referee_id = await _seed_user_and_client(_credit_session, nonce=nonce_e)
    plan_id = await _seed_membership_plan(_credit_session)
    await _ensure_referral_config(_credit_session)

    code_id = await _seed_referral_code(_credit_session, client_id=referrer_id)
    await _seed_referral_capture(
        _credit_session,
        referee_client_id=referee_id,
        referrer_client_id=referrer_id,
        referral_code_id=code_id,
    )

    yk_id, _op_id = await _seed_online_payment_membership(
        _credit_session,
        client_id=referee_id,
        membership_plan_id=plan_id,
    )
    await _credit_session.commit()

    with _mock_yookassa_succeeded(yk_id):
        r = await _webhook_client.post(
            "/api/v1/_internal/yookassa/webhook", json=_webhook_body(yk_id)
        )
    assert r.status_code == 200, r.text

    await _credit_session.rollback()
    accrual_count = await _count_referral_accrual_rows(_credit_session)
    assert accrual_count == 0, (
        f"Expected 0 rows (referrer deleted — entire accrual voided), got {accrual_count}"
    )


# ---------------------------------------------------------------------------
# Case 6: PT-package payment — subject_kind guard excludes PT
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ref_cred_06_pt_package_no_accrual(
    _credit_session: AsyncSession,
    _webhook_client: AsyncClient,
) -> None:
    """A PT-package payment.succeeded must produce 0 referral_accrual rows —
    the membership-only guard in handle_payment_succeeded excludes PT-package."""
    nonce_r = uuid4().hex[:8]
    nonce_e = uuid4().hex[:8]
    _u_r, referrer_id = await _seed_user_and_client(_credit_session, nonce=nonce_r)
    _u_e, referee_id = await _seed_user_and_client(_credit_session, nonce=nonce_e)
    pt_plan_id = await _seed_pt_package_plan(_credit_session)
    await _ensure_referral_config(_credit_session)

    code_id = await _seed_referral_code(_credit_session, client_id=referrer_id)
    await _seed_referral_capture(
        _credit_session,
        referee_client_id=referee_id,
        referrer_client_id=referrer_id,
        referral_code_id=code_id,
    )

    yk_id, _op_id = await _seed_online_payment_pt(
        _credit_session,
        client_id=referee_id,
        pt_package_plan_id=pt_plan_id,
    )
    await _credit_session.commit()

    with _mock_yookassa_succeeded(yk_id):
        r = await _webhook_client.post(
            "/api/v1/_internal/yookassa/webhook", json=_webhook_body(yk_id)
        )
    assert r.status_code == 200, r.text

    await _credit_session.rollback()
    accrual_count = await _count_referral_accrual_rows(_credit_session)
    assert accrual_count == 0, f"Expected 0 rows (PT-package excluded), got {accrual_count}"


# ---------------------------------------------------------------------------
# Case 7: Config missing or zero amounts — graceful no-op
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ref_cred_07_config_zero_amounts_no_accrual(
    _credit_session: AsyncSession,
    _webhook_client: AsyncClient,
) -> None:
    """When referral_config amounts are zero (or config is absent), the handler
    skips both accrue_referral_bonus calls — graceful no-op, 0 accrual rows."""
    nonce_r = uuid4().hex[:8]
    nonce_e = uuid4().hex[:8]
    _u_r, referrer_id = await _seed_user_and_client(_credit_session, nonce=nonce_r)
    _u_e, referee_id = await _seed_user_and_client(_credit_session, nonce=nonce_e)
    plan_id = await _seed_membership_plan(_credit_session)

    # Seed config with ZERO amounts — both credit calls are skipped
    await _ensure_referral_config(
        _credit_session,
        referrer_bonus_kopecks=0,
        referee_welcome_kopecks=0,
    )

    code_id = await _seed_referral_code(_credit_session, client_id=referrer_id)
    await _seed_referral_capture(
        _credit_session,
        referee_client_id=referee_id,
        referrer_client_id=referrer_id,
        referral_code_id=code_id,
    )

    yk_id, _op_id = await _seed_online_payment_membership(
        _credit_session,
        client_id=referee_id,
        membership_plan_id=plan_id,
    )
    await _credit_session.commit()

    with _mock_yookassa_succeeded(yk_id):
        r = await _webhook_client.post(
            "/api/v1/_internal/yookassa/webhook", json=_webhook_body(yk_id)
        )
    assert r.status_code == 200, r.text

    await _credit_session.rollback()
    accrual_count = await _count_referral_accrual_rows(_credit_session)
    assert accrual_count == 0, (
        f"Expected 0 rows (zero config amounts), got {accrual_count}"
    )
