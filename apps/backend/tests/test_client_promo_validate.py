"""Phase 999.4 Plan 02 — promo code validate endpoint + D-11 receipt_url integration tests.

Covers:
- POST /api/v1/client/promo/validate: valid percentage, valid fixed-cap, all 6 D-09 error codes
- Auth gate (unauthenticated → 401/403), CSRF gate (missing header → 403)
- D-11: payment-status GET with a succeeded fiscal_receipts row → receiptUrl present
- D-11: payment-status GET with NO succeeded fiscal receipt → receiptUrl null/absent

Test harness: httpx ASGITransport + pytest-asyncio + SAVEPOINT-based db_session.
Auth: same _auth_as_client helper pattern as test_checkout.py.
ЮKassa: not called (validate is read-only; no respx needed for these tests).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.permissions import Role
from app.core.security import generate_otp_code, hash_password
from app.modules.auth.models import OtpCode, User
from app.modules.clients.models import Client
from app.modules.memberships.models import MembershipPlan
from app.modules.promo_codes.models import PromoCode

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Redis clean fixture — flush between tests to reset rate-limit keys
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def redis_clean(app: FastAPI) -> Redis:
    """Flush Redis between tests so OTP rate-limit keys don't bleed across tests."""
    redis: Redis = app.state.redis
    await redis.flushdb()
    return redis

# ---------------------------------------------------------------------------
# Auth helper (mirrors test_checkout.py:_auth_as_client)
# ---------------------------------------------------------------------------


async def _auth_as_client(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client: Client,
) -> None:
    """Request OTP → patch code → verify. After this call, async_client has auth cookies."""
    req = await async_client.post(
        "/api/v1/client/otp/request",
        json={"phone": client.phone},
    )
    assert req.status_code == 202, f"OTP request failed: {req.text}"

    otp_row = await db_session.scalar(
        select(OtpCode).where(
            OtpCode.client_id == client.id,
            OtpCode.consumed_at.is_(None),
        )
    )
    assert otp_row is not None, f"OtpCode row not found for client {client.id}"

    settings = get_settings()
    raw_code, code_hash = generate_otp_code()
    otp_row.code_hash = code_hash
    otp_row.expires_at = datetime.now(tz=UTC) + timedelta(seconds=settings.otp_code_ttl_seconds)
    await db_session.commit()

    verify = await async_client.post(
        "/api/v1/client/otp/verify",
        json={"phone": client.phone, "code": raw_code},
    )
    assert verify.status_code == 200, f"OTP verify failed: {verify.text}"


def _promo_headers(client: AsyncClient) -> dict[str, str]:
    """Return {"X-CSRF-Token": <clubcore_client_csrf>} for POST /promo/validate."""
    return {"X-CSRF-Token": client.cookies.get("clubcore_client_csrf") or ""}


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _seed_client(db_session: AsyncSession, *, phone: str | None = None) -> Client:
    """Seed a client with email and telegram_user_id (required for OTP flow)."""
    suffix = uuid4().hex[:8]
    phone = phone or f"+7916{uuid4().int % 10_000_000:07d}"
    tg_id = uuid4().int % 2_000_000_000 + 800_000_000

    staff = User(
        email=f"staff-promo-{suffix}@example.com",
        password_hash=await hash_password("test-staff-pw-123"),
        role=Role.RECEPTION,
        full_name=f"Staff Promo {suffix}",
    )
    db_session.add(staff)
    await db_session.flush()

    client = Client(
        first_name="PromoTest",
        last_name=f"Client-{suffix}",
        phone=phone,
        email=f"promo-client-{suffix}@example.com",
        telegram_user_id=tg_id,
        created_by_user_id=staff.id,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


async def _seed_membership_plan(
    db_session: AsyncSession, *, price_kopecks: int = 100_000
) -> MembershipPlan:
    """Insert an active MembershipPlan."""
    plan = MembershipPlan(
        name=f"PromoPlan {uuid4().hex[:6]}",
        duration_days=30,
        price_kopecks=price_kopecks,
        freeze_days_limit=7,
        active=True,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    return plan


async def _seed_promo_code(
    db_session: AsyncSession,
    *,
    code: str,
    discount_type: str = "percentage",
    discount_value: int = 1000,  # 10% → 1000 (percent*100)
    max_uses: int | None = None,
    per_client_limit: int | None = None,
    is_active: bool = True,
    valid_from: datetime | None = None,
    valid_until: datetime | None = None,
    applicable_to: str | None = None,
) -> PromoCode:
    """Insert a PromoCode row with the given parameters."""
    promo = PromoCode(
        code=code,
        discount_type=discount_type,
        discount_value=discount_value,
        max_uses=max_uses,
        per_client_limit=per_client_limit,
        is_active=is_active,
        valid_from=valid_from,
        valid_until=valid_until,
        applicable_to=applicable_to,
    )
    db_session.add(promo)
    await db_session.commit()
    await db_session.refresh(promo)
    return promo


# ---------------------------------------------------------------------------
# Task 1 tests: validate_promo_code core logic (called via HTTP endpoint in Task 2)
# These tests assert end-to-end behavior through the HTTP endpoint.
# ---------------------------------------------------------------------------


async def test_valid_percentage_discount(
    async_client: AsyncClient,
    db_session: AsyncSession,
    redis_clean: Redis,
) -> None:
    """Active 10% code on a 1_000_00-kopeck plan → discountKopecks=10000, newAmountKopecks=90000."""
    client = await _seed_client(db_session)
    plan = await _seed_membership_plan(db_session, price_kopecks=100_000)  # 1000 RUB
    await _seed_promo_code(db_session, code="TEST10PCT", discount_type="percentage", discount_value=1000)

    await _auth_as_client(async_client, db_session, client)

    r = await async_client.post(
        "/api/v1/client/promo/validate",
        headers=_promo_headers(async_client),
        json={"code": "TEST10PCT", "kind": "sub", "planId": str(plan.id)},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["discountKopecks"] == 10_000, f"Expected 10000, got {data['discountKopecks']}"
    assert data["newAmountKopecks"] == 90_000, f"Expected 90000, got {data['newAmountKopecks']}"
    assert data["discountType"] == "percentage"


async def test_valid_fixed_discount_caps_at_price(
    async_client: AsyncClient,
    db_session: AsyncSession,
    redis_clean: Redis,
) -> None:
    """Fixed 500_00-kopeck code where plan price=300_00 → discount caps at price; newAmount=0."""
    client = await _seed_client(db_session)
    plan = await _seed_membership_plan(db_session, price_kopecks=30_000)  # 300 RUB
    # discount_value=50000 (500 RUB fixed) > plan price (300 RUB) → caps at price
    await _seed_promo_code(
        db_session, code="TESTFIXED500", discount_type="fixed", discount_value=50_000
    )

    await _auth_as_client(async_client, db_session, client)

    r = await async_client.post(
        "/api/v1/client/promo/validate",
        headers=_promo_headers(async_client),
        json={"code": "TESTFIXED500", "kind": "sub", "planId": str(plan.id)},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["discountKopecks"] == 30_000, f"Expected 30000 (capped at price), got {data['discountKopecks']}"
    assert data["newAmountKopecks"] == 0, f"Expected 0, got {data['newAmountKopecks']}"
    assert data["discountType"] == "fixed"


async def test_percentage_floor_division(
    async_client: AsyncClient,
    db_session: AsyncSession,
    redis_clean: Redis,
) -> None:
    """10% on a 33_333-kopeck plan → floor(33333 * 1000 / 100 / 100) = 3333 (floor, not 3333.3)."""
    client = await _seed_client(db_session)
    plan = await _seed_membership_plan(db_session, price_kopecks=33_333)
    await _seed_promo_code(db_session, code="TESTFLOOR10", discount_type="percentage", discount_value=1000)

    await _auth_as_client(async_client, db_session, client)

    r = await async_client.post(
        "/api/v1/client/promo/validate",
        headers=_promo_headers(async_client),
        json={"code": "TESTFLOOR10", "kind": "sub", "planId": str(plan.id)},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    # 10% of 33333 = 3333.3 → floor → 3333
    assert data["discountKopecks"] == 3333, f"Expected 3333 (floor), got {data['discountKopecks']}"
    assert data["newAmountKopecks"] == 30_000, f"Expected 30000, got {data['newAmountKopecks']}"


# ---------------------------------------------------------------------------
# D-09 Error code tests (6 distinct reasons)
# ---------------------------------------------------------------------------


async def test_promo_not_found(
    async_client: AsyncClient,
    db_session: AsyncSession,
    redis_clean: Redis,
) -> None:
    """Unknown code → HTTP 422, error code 'not_found'."""
    client = await _seed_client(db_session)
    plan = await _seed_membership_plan(db_session)
    await _auth_as_client(async_client, db_session, client)

    r = await async_client.post(
        "/api/v1/client/promo/validate",
        headers=_promo_headers(async_client),
        json={"code": "DOESNOTEXIST99", "kind": "sub", "planId": str(plan.id)},
    )
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["code"] == "not_found", f"Expected 'not_found', got {body.get('code')!r}"


async def test_promo_inactive(
    async_client: AsyncClient,
    db_session: AsyncSession,
    redis_clean: Redis,
) -> None:
    """is_active=False → error code 'inactive'."""
    client = await _seed_client(db_session)
    plan = await _seed_membership_plan(db_session)
    await _seed_promo_code(db_session, code="TESTINACTIVE", is_active=False)
    await _auth_as_client(async_client, db_session, client)

    r = await async_client.post(
        "/api/v1/client/promo/validate",
        headers=_promo_headers(async_client),
        json={"code": "TESTINACTIVE", "kind": "sub", "planId": str(plan.id)},
    )
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["code"] == "inactive", f"Expected 'inactive', got {body.get('code')!r}"


async def test_promo_expired(
    async_client: AsyncClient,
    db_session: AsyncSession,
    redis_clean: Redis,
) -> None:
    """now > valid_until → error code 'expired'."""
    client = await _seed_client(db_session)
    plan = await _seed_membership_plan(db_session)
    past = datetime.now(UTC) - timedelta(days=1)
    await _seed_promo_code(
        db_session, code="TESTEXPIRED", valid_until=past
    )
    await _auth_as_client(async_client, db_session, client)

    r = await async_client.post(
        "/api/v1/client/promo/validate",
        headers=_promo_headers(async_client),
        json={"code": "TESTEXPIRED", "kind": "sub", "planId": str(plan.id)},
    )
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["code"] == "expired", f"Expected 'expired', got {body.get('code')!r}"


async def test_promo_not_yet_active(
    async_client: AsyncClient,
    db_session: AsyncSession,
    redis_clean: Redis,
) -> None:
    """now < valid_from → error code 'not_yet_active'."""
    client = await _seed_client(db_session)
    plan = await _seed_membership_plan(db_session)
    future = datetime.now(UTC) + timedelta(days=10)
    await _seed_promo_code(
        db_session, code="TESTFUTURE", valid_from=future
    )
    await _auth_as_client(async_client, db_session, client)

    r = await async_client.post(
        "/api/v1/client/promo/validate",
        headers=_promo_headers(async_client),
        json={"code": "TESTFUTURE", "kind": "sub", "planId": str(plan.id)},
    )
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["code"] == "not_yet_active", f"Expected 'not_yet_active', got {body.get('code')!r}"


async def test_promo_not_applicable(
    async_client: AsyncClient,
    db_session: AsyncSession,
    redis_clean: Redis,
) -> None:
    """applicable_to='pt_package' but kind='sub' → error code 'not_applicable'."""
    client = await _seed_client(db_session)
    plan = await _seed_membership_plan(db_session)
    await _seed_promo_code(
        db_session, code="TESTPTONLY", applicable_to="pt_package"
    )
    await _auth_as_client(async_client, db_session, client)

    r = await async_client.post(
        "/api/v1/client/promo/validate",
        headers=_promo_headers(async_client),
        json={"code": "TESTPTONLY", "kind": "sub", "planId": str(plan.id)},
    )
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["code"] == "not_applicable", f"Expected 'not_applicable', got {body.get('code')!r}"


async def test_promo_used_up_per_client_limit(
    async_client: AsyncClient,
    db_session: AsyncSession,
    redis_clean: Redis,
) -> None:
    """per_client_limit=1 with one prior redemption by this client → error code 'used_up'."""
    client = await _seed_client(db_session)
    plan = await _seed_membership_plan(db_session)
    promo = await _seed_promo_code(
        db_session, code="TESTUSEDPERCLIENT", per_client_limit=1
    )
    await _auth_as_client(async_client, db_session, client)

    # Seed an existing redemption for this client
    # We need an online_payment_id FK — use a fake UUID that satisfies the CHECK
    # but skip the FK by using a raw INSERT that bypasses FK (we use a real online_payment row)
    # For simplicity: insert a minimal online_payments row, then a promo_redemption.
    # Actually, promo_redemptions has FK online_payment_id → online_payments.id (RESTRICT).
    # We need a real online_payments row. Let's use raw SQL to seed safely.
    # However, for this test we only need the COUNT to exceed per_client_limit.
    # We seed an online_payments row first (minimal required fields).

    # Seed minimal online_payments row to satisfy the FK
    op_id = uuid4()
    membership_plan = plan
    await db_session.execute(
        text(
            "INSERT INTO online_payments (id, client_id, membership_plan_id, amount_kopecks, "
            "idempotency_key, yookassa_payment_id, status, confirmation_type, audit_correlation_id) "
            "VALUES (:id, :client_id, :plan_id, :amount, :ikey, :yk_id, 'succeeded', 'redirect', gen_random_uuid())"
        ),
        {
            "id": str(op_id),
            "client_id": str(client.id),
            "plan_id": str(membership_plan.id),
            "amount": 100_000,
            "ikey": f"ikey-{uuid4().hex[:16]}",
            "yk_id": f"yk-{uuid4().hex[:24]}",
        },
    )

    # Seed a promo_redemption for this client against the above online_payment
    await db_session.execute(
        text(
            "INSERT INTO promo_redemptions (id, promo_code_id, client_id, online_payment_id, discount_kopecks) "
            "VALUES (:id, :promo_id, :client_id, :op_id, :discount)"
        ),
        {
            "id": str(uuid4()),
            "promo_id": str(promo.id),
            "client_id": str(client.id),
            "op_id": str(op_id),
            "discount": 10_000,
        },
    )
    await db_session.commit()

    r = await async_client.post(
        "/api/v1/client/promo/validate",
        headers=_promo_headers(async_client),
        json={"code": "TESTUSEDPERCLIENT", "kind": "sub", "planId": str(plan.id)},
    )
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["code"] == "used_up", f"Expected 'used_up', got {body.get('code')!r}"


async def test_promo_used_up_global(
    async_client: AsyncClient,
    db_session: AsyncSession,
    redis_clean: Redis,
) -> None:
    """max_uses=1 globally reached → error code 'used_up'."""
    client1 = await _seed_client(db_session)
    client2 = await _seed_client(db_session)
    plan = await _seed_membership_plan(db_session)
    promo = await _seed_promo_code(
        db_session, code="TESTUSEDGLOBAL", max_uses=1
    )
    await _auth_as_client(async_client, db_session, client2)

    # Seed one global redemption (from client1)
    op_id = uuid4()
    await db_session.execute(
        text(
            "INSERT INTO online_payments (id, client_id, membership_plan_id, amount_kopecks, "
            "idempotency_key, yookassa_payment_id, status, confirmation_type, audit_correlation_id) "
            "VALUES (:id, :client_id, :plan_id, :amount, :ikey, :yk_id, 'succeeded', 'redirect', gen_random_uuid())"
        ),
        {
            "id": str(op_id),
            "client_id": str(client1.id),
            "plan_id": str(plan.id),
            "amount": 100_000,
            "ikey": f"ikey-{uuid4().hex[:16]}",
            "yk_id": f"yk-{uuid4().hex[:24]}",
        },
    )
    await db_session.execute(
        text(
            "INSERT INTO promo_redemptions (id, promo_code_id, client_id, online_payment_id, discount_kopecks) "
            "VALUES (:id, :promo_id, :client_id, :op_id, :discount)"
        ),
        {
            "id": str(uuid4()),
            "promo_id": str(promo.id),
            "client_id": str(client1.id),
            "op_id": str(op_id),
            "discount": 10_000,
        },
    )
    await db_session.commit()

    # client2 tries to use same code → global max_uses=1 already reached
    r = await async_client.post(
        "/api/v1/client/promo/validate",
        headers=_promo_headers(async_client),
        json={"code": "TESTUSEDGLOBAL", "kind": "sub", "planId": str(plan.id)},
    )
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["code"] == "used_up", f"Expected 'used_up', got {body.get('code')!r}"


# ---------------------------------------------------------------------------
# Auth gate + CSRF gate tests
# ---------------------------------------------------------------------------


async def test_promo_validate_requires_auth(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Unauthenticated POST → 401 or 403 (no valid cc_client_access cookie)."""
    plan = await _seed_membership_plan(db_session)

    # No auth cookies in async_client
    r = await async_client.post(
        "/api/v1/client/promo/validate",
        headers={"X-CSRF-Token": "fake-csrf"},
        json={"code": "ANYCODE", "kind": "sub", "planId": str(plan.id)},
    )
    assert r.status_code in (401, 403), f"Expected 401 or 403, got {r.status_code}: {r.text}"


async def test_promo_validate_requires_csrf(
    async_client: AsyncClient,
    db_session: AsyncSession,
    redis_clean: Redis,
) -> None:
    """Authenticated POST without X-CSRF-Token → 403 csrf_mismatch."""
    client = await _seed_client(db_session)
    plan = await _seed_membership_plan(db_session)
    await _seed_promo_code(db_session, code="TESTCSRF")
    await _auth_as_client(async_client, db_session, client)

    # No CSRF header
    r = await async_client.post(
        "/api/v1/client/promo/validate",
        headers={},
        json={"code": "TESTCSRF", "kind": "sub", "planId": str(plan.id)},
    )
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
    assert r.json().get("code") == "csrf_mismatch"


# ---------------------------------------------------------------------------
# D-11: receipt_url on payment-status endpoint
# ---------------------------------------------------------------------------


async def test_payment_status_includes_receipt_url_when_succeeded_fiscal_receipt_exists(
    async_client: AsyncClient,
    db_session: AsyncSession,
    redis_clean: Redis,
) -> None:
    """GET /payments/{id}/status for a succeeded payment WITH a succeeded fiscal receipt
    returns receiptUrl = 'https://yookassa.ru/my/receipt/{yookassa_receipt_id}' (D-11).
    """
    client = await _seed_client(db_session)
    plan = await _seed_membership_plan(db_session)
    await _auth_as_client(async_client, db_session, client)

    # Seed an online_payments row (status=succeeded)
    op_id = uuid4()
    await db_session.execute(
        text(
            "INSERT INTO online_payments (id, client_id, membership_plan_id, amount_kopecks, "
            "idempotency_key, yookassa_payment_id, status, confirmation_type, audit_correlation_id) "
            "VALUES (:id, :client_id, :plan_id, :amount, :ikey, :yk_id, 'succeeded', 'redirect', gen_random_uuid())"
        ),
        {
            "id": str(op_id),
            "client_id": str(client.id),
            "plan_id": str(plan.id),
            "amount": 100_000,
            "ikey": f"ikey-{uuid4().hex[:16]}",
            "yk_id": f"yk-{uuid4().hex[:24]}",
        },
    )

    # Seed a payments ledger row (method=online) linked to a membership
    # For the fiscal receipt join we need: payments.id → fiscal_receipts.payment_id
    # We create a payments row with subject_kind='membership' (subject_id = some UUID).
    # The join in get_client_payment_status will go: online_payments → memberships →
    # payments → fiscal_receipts. For the test, we directly seed using the known
    # payments.id so the fiscal_receipts row links correctly.
    payment_id = uuid4()
    # We need a membership row to satisfy the payments.subject_id constraint.
    # Use raw SQL to insert membership (bypasses ORM constraints for test speed).
    membership_id = uuid4()
    await db_session.execute(
        text(
            "INSERT INTO memberships "
            "(id, client_id, plan_id, plan_name_snapshot, duration_days_snapshot, "
            " price_kopecks_snapshot, freeze_days_limit_snapshot, start_date, end_date, "
            " status, activation_policy) "
            "VALUES (:id, :client_id, :plan_id, 'TestPlan', 30, 100000, 0, "
            "        CURRENT_DATE, CURRENT_DATE + 30, 'active', 'purchase_date')"
        ),
        {
            "id": str(membership_id),
            "client_id": str(client.id),
            "plan_id": str(plan.id),
        },
    )
    await db_session.execute(
        text(
            "INSERT INTO payments (id, subject_kind, subject_id, amount_kopecks, method) "
            "VALUES (:id, 'membership', :subject_id, :amount, 'online')"
        ),
        {
            "id": str(payment_id),
            "subject_id": str(membership_id),
            "amount": 100_000,
        },
    )

    # Seed a fiscal_receipts row with status=succeeded and a known yookassa_receipt_id
    receipt_id = "test-receipt-" + uuid4().hex[:12]
    await db_session.execute(
        text(
            "INSERT INTO fiscal_receipts (id, payment_id, kind, status, yookassa_receipt_id, customer_email) "
            "VALUES (:id, :payment_id, 'payment', 'succeeded', :receipt_id, :email)"
        ),
        {
            "id": str(uuid4()),
            "payment_id": str(payment_id),
            "receipt_id": receipt_id,
            "email": f"test-{uuid4().hex[:8]}@example.com",
        },
    )
    await db_session.commit()

    r = await async_client.get(
        f"/api/v1/client/payments/{op_id}/status",
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    expected_url = f"https://yookassa.ru/my/receipt/{receipt_id}"
    assert data.get("receiptUrl") == expected_url, (
        f"Expected receiptUrl={expected_url!r}, got {data.get('receiptUrl')!r}"
    )


async def test_payment_status_receipt_url_null_when_no_succeeded_fiscal_receipt(
    async_client: AsyncClient,
    db_session: AsyncSession,
    redis_clean: Redis,
) -> None:
    """GET /payments/{id}/status for a payment with NO succeeded fiscal receipt
    → receiptUrl is null/absent (D-11 — honest, never fabricated).
    """
    client = await _seed_client(db_session)
    plan = await _seed_membership_plan(db_session)
    await _auth_as_client(async_client, db_session, client)

    # Seed an online_payments row (pending — no fiscal receipt yet)
    op_id = uuid4()
    await db_session.execute(
        text(
            "INSERT INTO online_payments (id, client_id, membership_plan_id, amount_kopecks, "
            "idempotency_key, yookassa_payment_id, status, confirmation_type, audit_correlation_id) "
            "VALUES (:id, :client_id, :plan_id, :amount, :ikey, :yk_id, 'pending', 'redirect', gen_random_uuid())"
        ),
        {
            "id": str(op_id),
            "client_id": str(client.id),
            "plan_id": str(plan.id),
            "amount": 100_000,
            "ikey": f"ikey-{uuid4().hex[:16]}",
            "yk_id": f"yk-{uuid4().hex[:24]}",
        },
    )
    await db_session.commit()

    r = await async_client.get(
        f"/api/v1/client/payments/{op_id}/status",
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    # receiptUrl should be null or absent (D-11: never fabricated)
    receipt_url = data.get("receiptUrl")
    assert receipt_url is None, f"Expected null receiptUrl, got {receipt_url!r}"


async def test_payment_status_receipt_url_null_when_fiscal_receipt_pending(
    async_client: AsyncClient,
    db_session: AsyncSession,
    redis_clean: Redis,
) -> None:
    """GET /payments/{id}/status: a fiscal_receipts row with status='pending' (not succeeded)
    → receiptUrl is null (D-11: only succeeded receipts produce a URL).
    """
    client = await _seed_client(db_session)
    plan = await _seed_membership_plan(db_session)
    await _auth_as_client(async_client, db_session, client)

    op_id = uuid4()
    await db_session.execute(
        text(
            "INSERT INTO online_payments (id, client_id, membership_plan_id, amount_kopecks, "
            "idempotency_key, yookassa_payment_id, status, confirmation_type, audit_correlation_id) "
            "VALUES (:id, :client_id, :plan_id, :amount, :ikey, :yk_id, 'succeeded', 'redirect', gen_random_uuid())"
        ),
        {
            "id": str(op_id),
            "client_id": str(client.id),
            "plan_id": str(plan.id),
            "amount": 100_000,
            "ikey": f"ikey-{uuid4().hex[:16]}",
            "yk_id": f"yk-{uuid4().hex[:24]}",
        },
    )

    # Seed a payments + membership row
    payment_id = uuid4()
    membership_id = uuid4()
    await db_session.execute(
        text(
            "INSERT INTO memberships "
            "(id, client_id, plan_id, plan_name_snapshot, duration_days_snapshot, "
            " price_kopecks_snapshot, freeze_days_limit_snapshot, start_date, end_date, "
            " status, activation_policy) "
            "VALUES (:id, :client_id, :plan_id, 'TestPlan', 30, 100000, 0, "
            "        CURRENT_DATE, CURRENT_DATE + 30, 'active', 'purchase_date')"
        ),
        {"id": str(membership_id), "client_id": str(client.id), "plan_id": str(plan.id)},
    )
    await db_session.execute(
        text(
            "INSERT INTO payments (id, subject_kind, subject_id, amount_kopecks, method) "
            "VALUES (:id, 'membership', :subject_id, :amount, 'online')"
        ),
        {"id": str(payment_id), "subject_id": str(membership_id), "amount": 100_000},
    )

    # Seed a PENDING fiscal receipt (not succeeded) → no URL
    await db_session.execute(
        text(
            "INSERT INTO fiscal_receipts (id, payment_id, kind, status, customer_email) "
            "VALUES (:id, :payment_id, 'payment', 'pending', :email)"
        ),
        {
            "id": str(uuid4()),
            "payment_id": str(payment_id),
            "email": f"test-pending-{uuid4().hex[:8]}@example.com",
        },
    )
    await db_session.commit()

    r = await async_client.get(
        f"/api/v1/client/payments/{op_id}/status",
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data.get("receiptUrl") is None, (
        f"Expected null receiptUrl for pending fiscal receipt, got {data.get('receiptUrl')!r}"
    )
