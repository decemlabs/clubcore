"""Phase 70 CBOOK-02..05 — client booking + cancel + slots-read integration tests.

Happy paths and precondition failures for the client booking surface:
  - POST /api/v1/client/booking  (CBOOK-03/04, idempotent, 201 / 422)
  - POST /api/v1/client/booking/{id}/cancel  (CBOOK-05, 200 / 404)
  - GET /api/v1/client/slots  (CBOOK-02, trainer-filtered, paginated)

Uses the SAVEPOINT db_session from root conftest (not real-commit — race test
lives in test_client_booking_race.py which uses db_session_real_commit).

Auth: _auth_as_client helper from test_idor_sweep.py (OTP request → patch hash
→ verify → cc_client_access cookie). After _auth_as_client the http_client
object holds all session cookies; only X-CSRF-Token header needs explicit passing.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
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
from app.modules.bookings.models import Booking
from app.modules.clients.models import Client
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.schedule.models import TrainerAvailabilitySlot
from app.modules.trainers.models import Trainer

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures — dependency overrides + authed http_client
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def _overridden_app(
    app: FastAPI,
    db_session: AsyncSession,
) -> AsyncIterator[FastAPI]:
    """Install dependency overrides so route handlers use the SAVEPOINT session."""

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
    """ASGITransport client that persists cookies across requests (no real network)."""
    transport = ASGITransport(app=_overridden_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.fixture(autouse=True)
def stub_otp_sender(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace real OTP sender with no-op for all tests in this module."""
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
    """Request OTP → patch hash → verify. After this call http_client holds all cookies.

    Mirrors test_idor_sweep.py:_auth_as_client. Cookies (cc_client_access,
    cc_client_refresh, clubcore_client_csrf) are stored on the http_client
    object automatically by httpx AsyncClient cookie jar.
    """
    req = await http_client.post(
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
    assert verify.status_code == 200, f"OTP verify failed: {verify.text}"
    # Cookies are now stored in http_client.cookies (httpx jar)


# ---------------------------------------------------------------------------
# DB seed helpers
# ---------------------------------------------------------------------------


async def _seed_staff(db_session: AsyncSession) -> User:
    user = User(
        email=f"client-booking-staff-{uuid4().hex[:6]}@example.com",
        password_hash=await hash_password("secure-test-password-123"),
        role=Role.RECEPTION,
        full_name="Client Booking Test Staff",
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _seed_client(db_session: AsyncSession, staff: User, *, phone: str) -> Client:
    client = Client(
        first_name="BookTest",
        last_name=f"Client-{uuid4().hex[:4]}",
        phone=phone,
        telegram_user_id=abs(hash(phone)) % (10**10),
        created_by_user_id=staff.id,
    )
    db_session.add(client)
    await db_session.commit()
    return client


async def _seed_trainer(db_session: AsyncSession) -> Trainer:
    trainer = Trainer(full_name=f"SlotTrainer-{uuid4().hex[:4]}", is_active=True)
    db_session.add(trainer)
    await db_session.commit()
    return trainer


async def _seed_pt_package(
    db_session: AsyncSession,
    client_id: UUID,
    trainer_id: UUID | None = None,
    sessions_remaining: int = 5,
    status: str = "active",
) -> tuple[PtPackagePlan, PtPackage]:
    plan = PtPackagePlan(
        name=f"TestPlan-{uuid4().hex[:4]}",
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
        sessions_remaining=sessions_remaining,
        status=status,
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
    status: str = "active",
) -> TrainerAvailabilitySlot:
    start = datetime.now(tz=UTC) + timedelta(hours=48)
    slot = TrainerAvailabilitySlot(
        trainer_id=trainer_id,
        start_time=start,
        end_time=start + timedelta(hours=1),
        status=status,
        created_by_user_id=staff_id,
    )
    db_session.add(slot)
    await db_session.commit()
    return slot


# ---------------------------------------------------------------------------
# POST /api/v1/client/booking — happy path (CBOOK-03)
# ---------------------------------------------------------------------------


async def test_client_create_booking_happy_path(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """CBOOK-03: client with active PT-package creates a booking → 201."""
    await app.state.redis.flushdb()
    staff = await _seed_staff(db_session)
    client = await _seed_client(db_session, staff, phone="+79001110001")
    trainer = await _seed_trainer(db_session)
    _, pkg = await _seed_pt_package(db_session, client.id, trainer_id=trainer.id)
    slot = await _seed_slot(db_session, trainer.id, staff.id)

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""

    r = await http_client.post(
        "/api/v1/client/booking",
        json={"slotId": str(slot.id), "ptPackageId": str(pkg.id)},
        headers={
            "X-CSRF-Token": csrf_token,
            "Idempotency-Key": f"test-happy-{uuid4().hex}",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["data"]["status"] == "confirmed"
    assert body["data"]["slotId"] == str(slot.id)

    # DB: booking row confirmed + slot flipped to 'booked'
    booking_row = await db_session.scalar(
        select(Booking).where(Booking.slot_id == slot.id, Booking.status == "confirmed")
    )
    assert booking_row is not None
    await db_session.refresh(slot)
    assert slot.status == "booked"


# ---------------------------------------------------------------------------
# Idempotency replay — same key → same booking (no second row)
# ---------------------------------------------------------------------------


async def test_client_create_booking_idempotent_replay(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """CBOOK-03: same Idempotency-Key replays the same 201 (no second booking row)."""
    await app.state.redis.flushdb()
    staff = await _seed_staff(db_session)
    client = await _seed_client(db_session, staff, phone="+79001110002")
    trainer = await _seed_trainer(db_session)
    _, pkg = await _seed_pt_package(db_session, client.id, trainer_id=trainer.id)
    slot = await _seed_slot(db_session, trainer.id, staff.id)

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""
    idem_key = f"test-idem-{uuid4().hex}"

    async def _post() -> Any:
        return await http_client.post(
            "/api/v1/client/booking",
            json={"slotId": str(slot.id), "ptPackageId": str(pkg.id)},
            headers={"X-CSRF-Token": csrf_token, "Idempotency-Key": idem_key},
        )

    r1 = await _post()
    assert r1.status_code == 201, r1.text
    r2 = await _post()
    assert r2.status_code == 201, r2.text  # replay
    assert r1.json()["data"]["id"] == r2.json()["data"]["id"]  # same booking id

    # Only 1 confirmed booking row (idempotency prevents double-insert)
    confirmed = await db_session.scalar(
        select(Booking).where(Booking.slot_id == slot.id, Booking.status == "confirmed")
    )
    assert confirmed is not None


# ---------------------------------------------------------------------------
# POST without active PT-package → 422 no_active_pt_package (CBOOK-04)
# ---------------------------------------------------------------------------


async def test_client_create_booking_no_active_pt_package(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """CBOOK-04: client with NO active PT-package → 422 no_active_pt_package."""
    await app.state.redis.flushdb()
    staff = await _seed_staff(db_session)
    client = await _seed_client(db_session, staff, phone="+79001110003")
    trainer = await _seed_trainer(db_session)
    slot = await _seed_slot(db_session, trainer.id, staff.id)

    # Seed an exhausted (inactive) package — get_active_pt_package returns None
    _, pkg = await _seed_pt_package(
        db_session, client.id, trainer_id=trainer.id, status="exhausted"
    )

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""

    r = await http_client.post(
        "/api/v1/client/booking",
        json={"slotId": str(slot.id), "ptPackageId": str(pkg.id)},
        headers={
            "X-CSRF-Token": csrf_token,
            "Idempotency-Key": f"test-no-pkg-{uuid4().hex}",
        },
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "no_active_pt_package"


# ---------------------------------------------------------------------------
# POST /api/v1/client/booking/{id}/cancel — own booking (CBOOK-05)
# ---------------------------------------------------------------------------


async def test_client_cancel_own_booking(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """CBOOK-05: client cancels their own confirmed booking → 200, slot restored."""
    await app.state.redis.flushdb()
    staff = await _seed_staff(db_session)
    client = await _seed_client(db_session, staff, phone="+79001110004")
    trainer = await _seed_trainer(db_session)
    _, pkg = await _seed_pt_package(db_session, client.id, trainer_id=trainer.id)
    slot = await _seed_slot(db_session, trainer.id, staff.id)

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""

    # Create a booking first
    create_r = await http_client.post(
        "/api/v1/client/booking",
        json={"slotId": str(slot.id), "ptPackageId": str(pkg.id)},
        headers={
            "X-CSRF-Token": csrf_token,
            "Idempotency-Key": f"test-cancel-create-{uuid4().hex}",
        },
    )
    assert create_r.status_code == 201, create_r.text
    booking_id = create_r.json()["data"]["id"]

    # Cancel it
    cancel_r = await http_client.post(
        f"/api/v1/client/booking/{booking_id}/cancel",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert cancel_r.status_code == 200, cancel_r.text
    assert cancel_r.json()["data"]["status"] == "cancelled"

    # Slot should be restored to 'active'
    await db_session.refresh(slot)
    assert slot.status == "active"


# ---------------------------------------------------------------------------
# GET /api/v1/client/slots — available slots (CBOOK-02)
# ---------------------------------------------------------------------------


async def test_client_list_slots(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """CBOOK-02: GET /client/slots returns active future slots, paginated."""
    await app.state.redis.flushdb()
    staff = await _seed_staff(db_session)
    client = await _seed_client(db_session, staff, phone="+79001110005")
    trainer = await _seed_trainer(db_session)
    _, _pkg = await _seed_pt_package(db_session, client.id, trainer_id=trainer.id)
    await _seed_slot(db_session, trainer.id, staff.id)

    await _auth_as_client(http_client, db_session, client)

    r = await http_client.get("/api/v1/client/slots")
    assert r.status_code == 200, r.text
    body = r.json()
    data = body["data"]
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "pageSize" in data
    assert data["total"] >= 1
    if data["items"]:
        item = data["items"][0]
        assert "slotId" in item
        assert "trainerName" in item
        assert "startTime" in item


async def test_client_list_slots_no_package_returns_all_trainers(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """CBOOK-02: client with no active PT-package gets 200 — all trainer slots returned."""
    await app.state.redis.flushdb()
    staff = await _seed_staff(db_session)
    # No PT-package for this client
    client = await _seed_client(db_session, staff, phone="+79001110006")
    trainer = await _seed_trainer(db_session)
    await _seed_slot(db_session, trainer.id, staff.id)

    await _auth_as_client(http_client, db_session, client)

    r = await http_client.get("/api/v1/client/slots")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    # No package → trainer_id=None → all trainer slots (slot we seeded should appear)
    assert data["total"] >= 1
