"""Phase 75 Plan 02 — FIT15 seed migration + validate-endpoint integration tests.

Covers PROMO-01:
- Test A: FIT15 row exists in promo_codes with correct attributes after migrations
  (discount_type='percentage', discount_value=1500, per_client_limit=1,
   is_active=True, deleted_at=None).
- Test B: Re-executing the 0051 upgrade INSERT is a no-op — exactly one alive
  FIT15 row exists after the re-run (T-75-05 idempotency).
- Test C: POST /api/v1/client/promo/validate with code 'FIT15' (authenticated
  client + CSRF) returns 200 with a valid percentage discount response.

Test harness: httpx ASGITransport + pytest-asyncio + SAVEPOINT-based db_session.
Auth: mirrors test_client_promo_validate.py _auth_as_client / _promo_headers.
The FIT15 row is seeded by migration 0051_seed_fit15_promo — NOT re-seeded here.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
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
# Auth helper (mirrors test_client_promo_validate.py)
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
# Seed helpers (mirrors test_client_promo_validate.py)
# ---------------------------------------------------------------------------


async def _seed_client(db_session: AsyncSession, *, phone: str | None = None) -> Client:
    """Seed a client with email and telegram_user_id (required for OTP flow)."""
    suffix = uuid4().hex[:8]
    phone = phone or f"+7916{uuid4().int % 10_000_000:07d}"
    tg_id = uuid4().int % 2_000_000_000 + 800_000_000

    staff = User(
        email=f"staff-fit15-{suffix}@example.com",
        password_hash=await hash_password("test-staff-pw-123"),
        role=Role.RECEPTION,
        full_name=f"Staff Fit15 {suffix}",
    )
    db_session.add(staff)
    await db_session.flush()

    client = Client(
        first_name="Fit15Test",
        last_name=f"Client-{suffix}",
        phone=phone,
        email=f"fit15-client-{suffix}@example.com",
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
        name=f"Fit15Plan {uuid4().hex[:6]}",
        duration_days=30,
        price_kopecks=price_kopecks,
        freeze_days_limit=7,
        active=True,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    return plan


# ---------------------------------------------------------------------------
# Test A: FIT15 row existence and attribute assertions
# ---------------------------------------------------------------------------


async def test_fit15_row_exists_with_correct_attributes(
    db_session: AsyncSession,
) -> None:
    """Migration 0051 seeds FIT15 with percentage/1500/per_client_limit=1/is_active/no expiry."""
    row = await db_session.scalar(
        select(PromoCode).where(
            PromoCode.code == "FIT15",
            PromoCode.deleted_at.is_(None),
        )
    )
    assert row is not None, "FIT15 promo_codes row not found — migration 0051 may not have run"
    assert row.discount_type == "percentage", (
        f"Expected discount_type='percentage', got {row.discount_type!r}"
    )
    assert row.discount_value == 1500, (
        f"Expected discount_value=1500 (15% x 100), got {row.discount_value}"
    )
    assert row.per_client_limit == 1, f"Expected per_client_limit=1, got {row.per_client_limit}"
    assert row.is_active is True, f"Expected is_active=True, got {row.is_active}"
    assert row.deleted_at is None, f"Expected deleted_at=None, got {row.deleted_at}"
    assert row.applicable_to is None, (
        f"Expected applicable_to=None (both membership+PT eligible), got {row.applicable_to!r}"
    )
    assert row.max_uses is None, (
        f"Expected max_uses=None (globally uncapped D-09), got {row.max_uses}"
    )
    assert row.valid_from is None, (
        f"Expected valid_from=None (no expiry window D-09), got {row.valid_from}"
    )
    assert row.valid_until is None, (
        f"Expected valid_until=None (no expiry window D-09), got {row.valid_until}"
    )


# ---------------------------------------------------------------------------
# Test B: Re-run idempotency — exactly one alive FIT15 row after re-insert
# ---------------------------------------------------------------------------


async def test_fit15_seed_insert_is_idempotent(
    db_session: AsyncSession,
) -> None:
    """Re-executing the 0051 upgrade INSERT leaves exactly one alive FIT15 row (T-75-05)."""
    # WR-75-04: establish the baseline so the post-reinsert count proves ON CONFLICT
    # actually suppressed a duplicate — not merely that no prior row existed.
    baseline = await db_session.scalar(
        text("SELECT count(*) FROM promo_codes WHERE upper(code) = 'FIT15' AND deleted_at IS NULL")
    )
    assert baseline == 1, (
        f"Expected exactly 1 alive FIT15 row from migration 0051 before re-run, got {baseline}"
    )

    # Re-run the exact SQL from migration 0051 upgrade()
    await db_session.execute(
        text(
            "INSERT INTO promo_codes "
            "(code, discount_type, discount_value, per_client_limit, max_uses, "
            " valid_from, valid_until, is_active, applicable_to) "
            "VALUES ('FIT15', 'percentage', 1500, 1, NULL, NULL, NULL, TRUE, NULL) "
            "ON CONFLICT (upper(code)) WHERE deleted_at IS NULL DO NOTHING"
        )
    )
    await db_session.commit()

    count_result = await db_session.scalar(
        text("SELECT count(*) FROM promo_codes WHERE upper(code) = 'FIT15' AND deleted_at IS NULL")
    )
    assert count_result == 1, (
        f"Expected exactly 1 alive FIT15 row after re-run, got {count_result} "
        "(ON CONFLICT idempotency failure — T-75-05)"
    )


# ---------------------------------------------------------------------------
# Test C: POST /client/promo/validate with FIT15 returns 200 + percentage discount
# ---------------------------------------------------------------------------


async def test_fit15_validate_returns_percentage_discount(
    async_client: AsyncClient,
    db_session: AsyncSession,
    redis_clean: Redis,
) -> None:
    """FIT15 on a 100_000-kopeck plan → 200, discountType=percentage, 15% applied.

    FIT15 is discount_value=1500 (15% encoded as percent*100).
    100_000 kopecks x 15% = 15_000 kopecks discount -> newAmount = 85_000.
    """
    client = await _seed_client(db_session)
    plan = await _seed_membership_plan(db_session, price_kopecks=100_000)
    await _auth_as_client(async_client, db_session, client)

    r = await async_client.post(
        "/api/v1/client/promo/validate",
        headers=_promo_headers(async_client),
        json={"code": "FIT15", "kind": "sub", "planId": str(plan.id)},
    )
    assert r.status_code == 200, f"Expected 200 for FIT15 validate, got {r.status_code}: {r.text}"
    data = r.json()["data"]
    assert data["discountType"] == "percentage", (
        f"Expected discountType='percentage', got {data.get('discountType')!r}"
    )
    # 15% of 100_000 kopecks: discount_value=1500 → 100_000 * 1500 / 100 / 100 = 15_000
    assert data["discountKopecks"] == 15_000, (
        f"Expected discountKopecks=15000 (15% of 100000), got {data.get('discountKopecks')}"
    )
    assert data["newAmountKopecks"] == 85_000, (
        f"Expected newAmountKopecks=85000, got {data.get('newAmountKopecks')}"
    )
