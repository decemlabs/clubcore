"""Phase 80 RESCH-01 / CR-01 / CR-02 — client reschedule endpoint integration tests.

Covers the idempotency-envelope contract from the code review:

  - CR-01 / D-39-09: a post-commit DM-send failure (network exception raised
    AFTER the authoritative reschedule commit) MUST NOT fail the HTTP request —
    the endpoint still returns 200 and the reschedule is durable.
  - CR-02: because the post-commit work is strictly best-effort and cannot raise,
    `idempotent_execute` records the correct success envelope, so a retry with
    the same Idempotency-Key replays the original 200 verbatim (it does NOT
    re-run the reschedule against the already-cancelled old booking, which would
    surface 409 invalid_transition).

Auth mirrors test_client_booking.py:_auth_as_client (OTP request → patch hash →
verify → cookies). The bookings.service Telegram sender is monkeypatched to raise
so the post-commit fire-and-forget block fails on every reschedule.
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
# Fixtures — dependency overrides + authed http_client (mirror test_client_booking)
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


@pytest.fixture(autouse=True)
def fail_reschedule_dm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the post-commit reschedule DM to RAISE (CR-01 / CR-02 contract).

    The fire-and-forget envelope in reschedule_booking_for_client must swallow
    this so the endpoint still returns 200 and the idempotency envelope records
    success.
    """
    from types import SimpleNamespace

    async def _raising_send_text_dm(bot: object, chat_id: int, text: str) -> Any:
        raise RuntimeError("simulated telegram failure after commit")

    monkeypatch.setattr(
        "app.modules.bookings.service.telegram_sender",
        SimpleNamespace(send_text_dm=_raising_send_text_dm),
    )
    monkeypatch.setattr("app.modules.bookings.service.build_bot", lambda *, token: object())


# ---------------------------------------------------------------------------
# Auth helper — mirrors test_client_booking.py:_auth_as_client verbatim
# ---------------------------------------------------------------------------


async def _auth_as_client(
    http_client: AsyncClient,
    db_session: AsyncSession,
    client: Client,
) -> None:
    """Request OTP → patch hash → verify. After this call http_client holds all cookies."""
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


# ---------------------------------------------------------------------------
# DB seed helpers
# ---------------------------------------------------------------------------


async def _seed_staff(db_session: AsyncSession) -> User:
    user = User(
        email=f"reschedule-staff-{uuid4().hex[:6]}@example.com",
        password_hash=await hash_password("secure-test-password-123"),
        role=Role.RECEPTION,
        full_name="Reschedule Test Staff",
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _seed_client(db_session: AsyncSession, staff: User, *, phone: str) -> Client:
    client = Client(
        first_name="ReschedTest",
        last_name=f"Client-{uuid4().hex[:4]}",
        phone=phone,
        telegram_user_id=abs(hash(phone)) % (10**10),
        created_by_user_id=staff.id,
    )
    db_session.add(client)
    await db_session.commit()
    return client


async def _seed_trainer(db_session: AsyncSession) -> Trainer:
    trainer = Trainer(full_name=f"ReschedTrainer-{uuid4().hex[:4]}", is_active=True)
    db_session.add(trainer)
    await db_session.commit()
    return trainer


async def _seed_pt_package(
    db_session: AsyncSession,
    client_id: UUID,
    trainer_id: UUID,
) -> PtPackage:
    plan = PtPackagePlan(
        name=f"ReschedPlan-{uuid4().hex[:4]}",
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
    return pkg


async def _seed_slot(
    db_session: AsyncSession,
    trainer_id: UUID,
    staff_id: UUID,
    *,
    start_offset: timedelta,
    status: str = "active",
) -> TrainerAvailabilitySlot:
    start = datetime.now(tz=UTC) + start_offset
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


async def _seed_confirmed_booking(
    db_session: AsyncSession,
    *,
    client_id: UUID,
    slot: TrainerAvailabilitySlot,
    pt_package_id: UUID,
) -> Booking:
    booking = Booking(
        slot_id=slot.id,
        client_id=client_id,
        pt_package_id=pt_package_id,
        status="confirmed",
    )
    db_session.add(booking)
    slot.status = "booked"
    await db_session.commit()
    await db_session.refresh(booking)
    return booking


# ---------------------------------------------------------------------------
# CR-01 / CR-02 — post-commit DM failure + idempotency replay
# ---------------------------------------------------------------------------


async def test_reschedule_dm_failure_returns_200_and_idempotent_replay(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """CR-01: a post-commit DM exception does NOT fail the request (200, durable).
    CR-02: the same Idempotency-Key replays the original 200 verbatim — it does
    NOT re-run the reschedule against the cancelled old booking (409
    invalid_transition)."""
    await app.state.redis.flushdb()
    staff = await _seed_staff(db_session)
    client = await _seed_client(db_session, staff, phone="+79002220001")
    trainer = await _seed_trainer(db_session)
    pkg = await _seed_pt_package(db_session, client.id, trainer.id)

    old_slot = await _seed_slot(db_session, trainer.id, staff.id, start_offset=timedelta(hours=48))
    new_slot = await _seed_slot(db_session, trainer.id, staff.id, start_offset=timedelta(hours=72))
    booking = await _seed_confirmed_booking(
        db_session, client_id=client.id, slot=old_slot, pt_package_id=pkg.id
    )

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""
    idem_key = f"test-reschedule-idem-{uuid4().hex}"

    async def _post() -> Any:
        return await http_client.post(
            f"/api/v1/client/booking/{booking.id}/reschedule",
            json={"newSlotId": str(new_slot.id)},
            headers={"X-CSRF-Token": csrf_token, "Idempotency-Key": idem_key},
        )

    # CR-01: first call — DM raises post-commit but is swallowed → 200.
    r1 = await _post()
    assert r1.status_code == 200, r1.text
    body1 = r1.json()["data"]
    assert body1["status"] == "confirmed"
    assert body1["slotId"] == str(new_slot.id)

    # Reschedule is durable: old booking cancelled, new booking confirmed.
    await db_session.refresh(booking)
    assert booking.status == "cancelled"
    new_booking_row = await db_session.scalar(
        select(Booking).where(Booking.slot_id == new_slot.id, Booking.status == "confirmed")
    )
    assert new_booking_row is not None

    # CR-02: replay with the SAME key — original 200 verbatim, not a 409
    # invalid_transition from re-running against the cancelled old booking.
    r2 = await _post()
    assert r2.status_code == 200, r2.text
    assert r2.json()["data"] == body1  # byte-identical replay envelope

    # Still exactly one confirmed booking on the new slot (no double reschedule).
    confirmed_count = len(
        (
            await db_session.execute(
                select(Booking).where(Booking.slot_id == new_slot.id, Booking.status == "confirmed")
            )
        )
        .scalars()
        .all()
    )
    assert confirmed_count == 1
