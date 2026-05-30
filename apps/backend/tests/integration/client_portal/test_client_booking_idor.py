"""Phase 70 criterion #3 — client booking IDOR 404-collapse + cancel-window tests.

Uses the SAVEPOINT db_session + ASGITransport async_client from root conftest.

Tests:
  1. Client A attempts to cancel client B's booking → 404 booking_not_found
     (anti-oracle — never 403 or existence leak; T-70-09 mitigation).
  2. Client B's booking remains confirmed after client A's failed cancel attempt.
  3. Own-cancel within the cancel window → 409 cancel_window_expired.
  4. Successful own-cancel (outside window) restores slot to 'active'.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.permissions import Role
from app.core.redis import get_redis
from app.core.security import generate_otp_code, hash_password
from app.modules.auth.models import OtpCode, User
from app.modules.bookings.constants import CANCEL_WINDOW_HOURS_CLIENT
from app.modules.bookings.models import Booking
from app.modules.clients.models import Client
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.schedule.models import TrainerAvailabilitySlot
from app.modules.trainers.models import Trainer

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def _overridden_app(
    app: FastAPI,
    db_session: AsyncSession,
) -> AsyncIterator[FastAPI]:
    """SAVEPOINT session + Redis override on the app."""

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = lambda: app.state.redis
    try:
        yield app
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def http_client(_overridden_app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Shared AsyncClient for IDOR tests (cookie jar persists across requests)."""
    transport = ASGITransport(app=_overridden_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.fixture(autouse=True)
def stub_otp_sender(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace real OTP sender with no-op."""
    _ = app
    from app.modules.client_auth import service as client_auth_service

    async def _noop(chat_id: int, code: str) -> None:
        pass

    monkeypatch.setattr(client_auth_service, "_client_otp_sender", _noop)


# ---------------------------------------------------------------------------
# Auth helper — mirrors test_idor_sweep.py:_auth_as_client verbatim
# ---------------------------------------------------------------------------


async def _auth_as_client(
    http_client: AsyncClient,
    db_session: AsyncSession,
    client: Client,
) -> None:
    """Request OTP → patch hash → verify. After this, http_client holds cookies."""
    req = await http_client.post(
        "/api/v1/client/otp/request",
        json={"phone": client.phone},
    )
    assert req.status_code == 202, f"OTP request failed for {client.phone}: {req.text}"

    otp_row = await db_session.scalar(
        select(OtpCode).where(
            OtpCode.client_id == client.id,
            OtpCode.consumed_at.is_(None),
        )
    )
    assert otp_row is not None

    settings = get_settings()
    raw_code, code_hash = generate_otp_code()
    otp_row.code_hash = code_hash
    otp_row.expires_at = datetime.now(tz=UTC) + timedelta(seconds=settings.otp_code_ttl_seconds)
    await db_session.commit()

    verify = await http_client.post(
        "/api/v1/client/otp/verify",
        json={"phone": client.phone, "code": raw_code},
    )
    assert verify.status_code == 200, f"OTP verify failed for {client.phone}: {verify.text}"
    # Cookies stored in http_client.cookies automatically


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _seed_staff(db_session: AsyncSession) -> User:
    user = User(
        email=f"idor-staff-{uuid4().hex[:6]}@example.com",
        password_hash=await hash_password("secure-idor-test-password-123"),
        role=Role.RECEPTION,
        full_name="IDOR Test Staff",
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _seed_client(db_session: AsyncSession, staff: User, *, phone: str) -> Client:
    client = Client(
        first_name="IDORTest",
        last_name=f"Client-{uuid4().hex[:4]}",
        phone=phone,
        telegram_user_id=abs(hash(phone)) % (10**10),
        created_by_user_id=staff.id,
    )
    db_session.add(client)
    await db_session.commit()
    return client


async def _seed_trainer(db_session: AsyncSession) -> Trainer:
    trainer = Trainer(full_name=f"IDORTrainer-{uuid4().hex[:4]}", is_active=True)
    db_session.add(trainer)
    await db_session.commit()
    return trainer


async def _seed_pt_package(
    db_session: AsyncSession,
    client_id: UUID,
    trainer_id: UUID,
) -> tuple[PtPackagePlan, PtPackage]:
    plan = PtPackagePlan(
        name=f"IDORPlan-{uuid4().hex[:4]}",
        session_count=10,
        price_kopecks=100_000,
        validity_days=90,
    )
    db_session.add(plan)
    await db_session.flush()

    today = datetime.now(tz=UTC).date()
    pkg = PtPackage(
        client_id=client_id,
        plan_id=plan.id,
        plan_name_snapshot=plan.name,
        session_count_snapshot=plan.session_count,
        price_kopecks_snapshot=plan.price_kopecks,
        validity_days_snapshot=plan.validity_days,
        sessions_remaining=5,
        status="active",
        start_date=today,
        end_date=today + timedelta(days=89),
        trainer_id=trainer_id,
    )
    db_session.add(pkg)
    await db_session.commit()
    return plan, pkg


async def _seed_slot(
    db_session: AsyncSession,
    trainer_id: UUID,
    staff_id: UUID,
    *,
    hours_from_now: int = 48,
) -> TrainerAvailabilitySlot:
    start = datetime.now(tz=UTC) + timedelta(hours=hours_from_now)
    slot = TrainerAvailabilitySlot(
        trainer_id=trainer_id,
        start_time=start,
        end_time=start + timedelta(hours=1),
        status="active",
        created_by_user_id=staff_id,
    )
    db_session.add(slot)
    await db_session.commit()
    return slot


async def _create_booking_via_http(
    http_client: AsyncClient,
    *,
    slot_id: UUID,
    pkg_id: UUID,
    csrf_token: str,
) -> str:
    """Create a booking via POST /client/booking and return the booking id."""
    r = await http_client.post(
        "/api/v1/client/booking",
        json={"slotId": str(slot_id), "ptPackageId": str(pkg_id)},
        headers={
            "X-CSRF-Token": csrf_token,
            "Idempotency-Key": f"idor-test-{uuid4().hex}",
        },
    )
    assert r.status_code == 201, f"Booking creation failed: {r.text}"
    return r.json()["data"]["id"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_client_a_cannot_cancel_client_b_booking_404(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """T-70-09: client A cancelling client B's booking → 404 booking_not_found.

    Anti-oracle: the response MUST be 404, not 403. Client A gets no information
    about whether client B's booking exists (IDOR 404-collapse per D-20-IDOR).
    Client B's booking remains confirmed after the failed attempt.
    """
    await app.state.redis.flushdb()
    staff = await _seed_staff(db_session)
    trainer = await _seed_trainer(db_session)

    client_a = await _seed_client(db_session, staff, phone="+79110000001")
    client_b = await _seed_client(db_session, staff, phone="+79110000002")

    _, pkg_b = await _seed_pt_package(db_session, client_b.id, trainer.id)
    slot_b = await _seed_slot(db_session, trainer.id, staff.id)

    # Seed a separate slot + PT-package for client A (so A can auth)
    _, _pkg_a = await _seed_pt_package(db_session, client_a.id, trainer.id)

    # Auth as client B and create a booking
    await _auth_as_client(http_client, db_session, client_b)
    csrf_b = http_client.cookies.get("clubcore_client_csrf") or ""
    booking_b_id = await _create_booking_via_http(
        http_client,
        slot_id=slot_b.id,
        pkg_id=pkg_b.id,
        csrf_token=csrf_b,
    )

    # Auth as client A using a fresh http_client to avoid cookie collision with B's session.
    # The _overridden_app fixture already sets get_db override, so ASGITransport(app=app)
    # (not _overridden_app) would bypass the SAVEPOINT — use app directly since
    # _overridden_app is already the app fixture with overrides applied.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        # But app is already overridden by _overridden_app fixture
        await _auth_as_client(c, db_session, client_a)
        csrf_a = c.cookies.get("clubcore_client_csrf") or ""

        # Client A attempts to cancel client B's booking
        r = await c.post(
            f"/api/v1/client/booking/{booking_b_id}/cancel",
            headers={"X-CSRF-Token": csrf_a},
        )

    assert r.status_code == 404, (
        f"Expected 404 booking_not_found for IDOR attempt, got {r.status_code}: {r.text}"
    )
    assert r.json()["code"] == "booking_not_found", (
        f"Expected 'booking_not_found' code, got: {r.json().get('code')}"
    )

    # Client B's booking should still be confirmed (not cancelled)
    booking_b = await db_session.scalar(
        select(Booking).where(Booking.id == booking_b_id)
    )
    assert booking_b is not None
    assert booking_b.status == "confirmed", (
        f"Client B's booking was mutated by client A's IDOR attempt: status={booking_b.status}"
    )


async def test_client_cancel_within_window_returns_cancel_window_expired(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """CBOOK-05: cancelling within CANCEL_WINDOW_HOURS_CLIENT → 409 cancel_window_expired."""
    await app.state.redis.flushdb()
    staff = await _seed_staff(db_session)
    trainer = await _seed_trainer(db_session)
    client = await _seed_client(db_session, staff, phone="+79110000003")
    _, pkg = await _seed_pt_package(db_session, client.id, trainer.id)

    # Slot starts within the cancel window (< CANCEL_WINDOW_HOURS_CLIENT from now)
    # Use a slot 1 hour from now — well within the 24h window.
    slot = await _seed_slot(db_session, trainer.id, staff.id, hours_from_now=1)

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""

    # Create the booking
    booking_id = await _create_booking_via_http(
        http_client,
        slot_id=slot.id,
        pkg_id=pkg.id,
        csrf_token=csrf_token,
    )

    # Try to cancel — within the cancel window → 409 cancel_window_expired
    r = await http_client.post(
        f"/api/v1/client/booking/{booking_id}/cancel",
        headers={"X-CSRF-Token": csrf_token},
    )
    # cancel_window_expired is a ConflictError (409) in the bookings domain
    # (CancelWindowExpiredError inherits ConflictError, status_code=409)
    assert r.status_code == 409, (
        f"Expected 409 for cancel_window_expired, got {r.status_code}: {r.text}"
    )
    assert r.json()["code"] == "cancel_window_expired", (
        f"Expected 'cancel_window_expired', got: {r.json().get('code')}"
    )


async def test_successful_own_cancel_restores_slot(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """CBOOK-05: successful own-cancel (outside cancel window) restores slot to 'active'."""
    await app.state.redis.flushdb()
    staff = await _seed_staff(db_session)
    trainer = await _seed_trainer(db_session)
    client = await _seed_client(db_session, staff, phone="+79110000004")
    _, pkg = await _seed_pt_package(db_session, client.id, trainer.id)

    # Slot starts outside the cancel window (> CANCEL_WINDOW_HOURS_CLIENT hours away)
    outside_window_hours = CANCEL_WINDOW_HOURS_CLIENT + 25  # well outside
    slot = await _seed_slot(db_session, trainer.id, staff.id, hours_from_now=outside_window_hours)

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""

    # Create booking
    booking_id = await _create_booking_via_http(
        http_client,
        slot_id=slot.id,
        pkg_id=pkg.id,
        csrf_token=csrf_token,
    )

    # Verify slot is 'booked'
    await db_session.refresh(slot)
    assert slot.status == "booked"

    # Cancel it (outside window → should succeed)
    r = await http_client.post(
        f"/api/v1/client/booking/{booking_id}/cancel",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "cancelled"

    # Slot should be restored to 'active'
    await db_session.refresh(slot)
    assert slot.status == "active", (
        f"Expected slot to be restored to 'active' after cancel, got: {slot.status}"
    )

    # Booking should be 'cancelled'
    booking = await db_session.scalar(select(Booking).where(Booking.id == booking_id))
    assert booking is not None
    assert booking.status == "cancelled"
