"""VER-01 — P102 booking lifecycle end-to-end verification (Phase 110 Plan 02).

Exercises the MOUNTED HTTP routes (not the service layer directly) to match
the v3.0 walkthrough intent:

  Test A — create → cancel on one booking:
    POST /api/v1/bookings → 201 confirmed; slot flips active→booked.
    POST /api/v1/bookings/{id}/cancel → 200; booking 'cancelled'; slot restored.

  Test B — complete via pt-session on a separate booking:
    POST /api/v1/bookings → 201 confirmed (fresh slot).
    POST /api/v1/pt-sessions {ptPackageId, performedAt, bookingId} → 201;
    booking flips to 'completed' in the same UoW; sessions_remaining decrements.

  Race test (BOOK-TEST-01-P102) — slot already taken → clear 409:
    2 parallel POST /api/v1/bookings with DISTINCT Idempotency-Keys against the
    SAME slot → exactly [201, 409]; all 409 codes == 'slot_already_booked'.
    Uses `db_session_real_commit` (real BEGIN/COMMIT) because SAVEPOINT
    isolation interferes with concurrent UPDATE serialisation.

Closes the P102 `data-setup-blocked` deferral for VER-01.

Prerequisites:
  - authed_client_owner fixture from bookings/conftest.py (session-overridden
    SAVEPOINT mode; login plants clubcore_csrf cookie for X-CSRF-Token).
  - make_trainer / make_client / make_pt_package_plan / make_pt_package /
    make_slot factories from bookings/conftest.py.
  - permissive_booking_config autouse (all tests reset booking_config +
    working_hours_config to permissive values so timing guards don't block).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.audit_models import AuditLog
from app.core.config import get_settings
from app.core.permissions import Role
from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.bookings.models import Booking
from app.modules.clients.models import Client
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.schedule.models import TrainerAvailabilitySlot
from app.modules.trainers.models import Trainer

# ---------------------------------------------------------------------------
# Helpers shared across A/B tests
# ---------------------------------------------------------------------------

_MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def _csrf_headers(
    client: AsyncClient,
    *,
    idempotency_key: str | None = None,
) -> dict[str, str]:
    """Build X-CSRF-Token + optional Idempotency-Key header dict."""
    headers: dict[str, str] = {
        "X-CSRF-Token": client.cookies.get("clubcore_csrf", "") or ""
    }
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def _next_monday_10_msk() -> datetime:
    """Return the next Monday 10:00 Europe/Moscow as an aware UTC datetime.

    Mirrors the next-Monday math in test_booking_race.py so the slot always
    falls inside the seeded Mon-Fri 00:00-23:59 working-hours window (permissive
    booking config resets the schedule to all-day-open; still need a future slot).
    """
    now_msk = datetime.now(_MOSCOW_TZ)
    days_ahead = (7 - now_msk.weekday()) % 7 or 7  # always ≥ 1 day ahead
    slot_msk = now_msk.replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(
        days=days_ahead
    )
    return slot_msk.astimezone(UTC)


# ---------------------------------------------------------------------------
# Task 1 / Test A — create → cancel lifecycle (HTTP)
# ---------------------------------------------------------------------------


async def test_booking_lifecycle_create_then_cancel(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_trainer: Any,
    make_client: Any,
    make_pt_package_plan: Any,
    make_pt_package: Any,
    make_slot: Any,
) -> None:
    """VER-01 Test A — POST /bookings → 201 confirmed; slot 'booked'.
    Then POST /bookings/{id}/cancel → 200; booking 'cancelled'; slot restored 'active'.

    Slot is seeded 48h ahead so the 24h cancel-window (cancel_window_hours=24
    from permissive_booking_config autouse) is satisfied by the owner role
    (owner cancels anytime; reception needs > 24h — slot > 24h satisfies both).
    """
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    # NULL trainer_id on PtPackage ⇒ "any trainer" guard (C-08); no trainer_id needed.
    pkg = await make_pt_package(
        client_id=client.id,
        plan=plan,
        sessions_remaining=5,
    )
    slot_start = datetime.now(UTC) + timedelta(hours=48)
    slot = await make_slot(
        trainer_id=trainer.id,
        start_time=slot_start,
        end_time=slot_start + timedelta(hours=1),
    )

    # --- CREATE ---
    r_create = await authed_client_owner.post(
        "/api/v1/bookings",
        json={
            "slotId": str(slot.id),
            "clientId": str(client.id),
            "ptPackageId": str(pkg.id),
        },
        headers=_csrf_headers(
            authed_client_owner,
            idempotency_key=f"p102-lifecycle-create-a-{uuid4().hex}",
        ),
    )
    assert r_create.status_code == 201, r_create.text
    data_create = r_create.json()["data"]
    assert data_create["status"] == "confirmed"
    booking_id: str = data_create["id"]

    # DB: slot must be 'booked' after create.
    await db_session.refresh(slot, attribute_names=["status"])
    assert slot.status == "booked", f"Expected slot 'booked', got '{slot.status}'"

    # --- CANCEL ---
    r_cancel = await authed_client_owner.post(
        f"/api/v1/bookings/{booking_id}/cancel",
        json={"reason": "VER-01 test cancel"},
        headers=_csrf_headers(
            authed_client_owner,
            idempotency_key=f"p102-lifecycle-cancel-a-{uuid4().hex}",
        ),
    )
    assert r_cancel.status_code == 200, r_cancel.text
    data_cancel = r_cancel.json()["data"]
    assert data_cancel["status"] == "cancelled"

    # DB: booking 'cancelled', slot restored 'active'.
    await db_session.refresh(slot, attribute_names=["status"])
    assert slot.status == "active", f"Expected slot 'active' after cancel, got '{slot.status}'"

    # Verify booking row directly.
    booking_row = await db_session.scalar(
        select(Booking).where(Booking.id == data_create["id"])
    )
    assert booking_row is not None
    assert booking_row.status == "cancelled"
    assert booking_row.cancelled_at is not None


# ---------------------------------------------------------------------------
# Task 1 / Test B — complete via pt-session (HTTP)
# ---------------------------------------------------------------------------


async def test_booking_lifecycle_complete_via_pt_session(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_trainer: Any,
    make_client: Any,
    make_pt_package_plan: Any,
    make_pt_package: Any,
    make_slot: Any,
) -> None:
    """VER-01 Test B — POST /bookings → 201; POST /pt-sessions {bookingId} → 201.
    Booking flips to 'completed'; sessions_remaining decrements by 1.

    A SEPARATE slot (fresh from make_slot) is used so this test is independent
    of Test A and can run in any order without slot-state contamination.
    """
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(
        client_id=client.id,
        plan=plan,
        sessions_remaining=5,
    )
    slot_start = datetime.now(UTC) + timedelta(hours=48)
    slot = await make_slot(
        trainer_id=trainer.id,
        start_time=slot_start,
        end_time=slot_start + timedelta(hours=1),
    )

    # --- CREATE the booking ---
    r_create = await authed_client_owner.post(
        "/api/v1/bookings",
        json={
            "slotId": str(slot.id),
            "clientId": str(client.id),
            "ptPackageId": str(pkg.id),
        },
        headers=_csrf_headers(
            authed_client_owner,
            idempotency_key=f"p102-lifecycle-create-b-{uuid4().hex}",
        ),
    )
    assert r_create.status_code == 201, r_create.text
    booking_id: str = r_create.json()["data"]["id"]

    # Capture sessions_remaining BEFORE pt-session completes the booking.
    await db_session.refresh(pkg)
    sessions_before = pkg.sessions_remaining

    # --- POST /pt-sessions with bookingId link ---
    performed_at = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    r_pts = await authed_client_owner.post(
        "/api/v1/pt-sessions",
        json={
            "ptPackageId": str(pkg.id),
            "trainerId": str(trainer.id),
            "performedAt": performed_at,
            "bookingId": booking_id,
        },
        headers=_csrf_headers(
            authed_client_owner,
            idempotency_key=f"p102-lifecycle-pts-b-{uuid4().hex}",
        ),
    )
    assert r_pts.status_code == 201, r_pts.text

    # DB: booking must be 'completed' (complete_booking_by_pt_session same UoW).
    booking_row = await db_session.scalar(
        select(Booking).where(Booking.id == booking_id)
    )
    assert booking_row is not None, "Booking row not found after pt-session"
    assert booking_row.status == "completed", (
        f"Expected booking 'completed', got '{booking_row.status}'"
    )
    assert booking_row.completed_at is not None, "completed_at not set after pt-session link"

    # DB: sessions_remaining must have decremented by 1.
    await db_session.refresh(pkg)
    assert pkg.sessions_remaining == sessions_before - 1, (
        f"Expected sessions_remaining={sessions_before - 1}, got {pkg.sessions_remaining}"
    )


# ---------------------------------------------------------------------------
# Task 2 — Race conflict: slot already taken → clear 409 slot_already_booked
# ---------------------------------------------------------------------------

_RACE_OWNER_EMAIL_P102 = "p102-race-owner@example.com"
_RACE_OWNER_PASSWORD_P102 = "hunter22hunter22"  # noqa: S105


@pytest_asyncio.fixture
async def db_session_real_commit_p102() -> AsyncIterator[AsyncSession]:
    """Real BEGIN/COMMIT — used ONLY by the P102 race test.

    Mirrors `test_booking_race.py:db_session_real_commit` exactly (same
    connectivity-probe skip, same TRUNCATE-on-teardown cleanup).
    Uses DISTINCT fixture name (_p102) to avoid collision when both files
    run in the same pytest session.
    """
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)

    try:
        async with engine.connect() as probe:
            await probe.execute(text("select 1"))
    except Exception as exc:  # broad: skip on any connectivity failure
        await engine.dispose()
        pytest.skip(
            f"DATABASE_URL not reachable for P102 race test; "
            f"run `docker compose up postgres` first ({exc!r})"
        )

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    # WR-03: Scoped cleanup — delete only the rows seeded by THIS test, identified
    # by the deterministic owner email constant.  Deleting globally via TRUNCATE
    # would wipe data seeded by other integration tests running in the same session.
    # FK-safe delete order: audit_log / bookings (leaves) → slots / packages /
    # clients → plans / trainers → user (roots).
    async with engine.begin() as conn:
        # 1. audit_log rows emitted by this test's owner.
        await conn.execute(
            text(
                "DELETE FROM audit_log WHERE actor_user_id = "
                "(SELECT id FROM users WHERE email = :email)"
            ),
            {"email": _RACE_OWNER_EMAIL_P102},
        )
        # 2. bookings for slots created by this test's owner.
        await conn.execute(
            text(
                "DELETE FROM bookings WHERE slot_id IN ("
                "  SELECT id FROM trainer_availability_slots"
                "  WHERE created_by_user_id = (SELECT id FROM users WHERE email = :email)"
                ")"
            ),
            {"email": _RACE_OWNER_EMAIL_P102},
        )
        # 3. trainer_availability_slots created by this test's owner.
        await conn.execute(
            text(
                "DELETE FROM trainer_availability_slots"
                " WHERE created_by_user_id = (SELECT id FROM users WHERE email = :email)"
            ),
            {"email": _RACE_OWNER_EMAIL_P102},
        )
        # 4. pt_packages for clients seeded by this test.
        await conn.execute(
            text(
                "DELETE FROM pt_packages WHERE client_id IN ("
                "  SELECT id FROM clients"
                "  WHERE created_by_user_id = (SELECT id FROM users WHERE email = :email)"
                ")"
            ),
            {"email": _RACE_OWNER_EMAIL_P102},
        )
        # 5. clients seeded by this test.
        await conn.execute(
            text(
                "DELETE FROM clients"
                " WHERE created_by_user_id = (SELECT id FROM users WHERE email = :email)"
            ),
            {"email": _RACE_OWNER_EMAIL_P102},
        )
        # 6. pt_package_plans seeded by this test (identified by name prefix).
        await conn.execute(
            text("DELETE FROM pt_package_plans WHERE name LIKE 'P102RacePlan-%'"),
        )
        # 7. trainers seeded by this test (identified by name prefix).
        await conn.execute(
            text("DELETE FROM trainers WHERE full_name LIKE 'P102RaceTrainer-%'"),
        )
        # 8. the owner user (root — deleted last).
        await conn.execute(
            text("DELETE FROM users WHERE email = :email"),
            {"email": _RACE_OWNER_EMAIL_P102},
        )
    await engine.dispose()


async def _build_authed_race_client(app: FastAPI) -> AsyncClient:
    """Authenticate against the REAL app (no SAVEPOINT override) for race test."""
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://testserver")
    r = await client.post(
        "/api/v1/auth/login",
        json={
            "email": _RACE_OWNER_EMAIL_P102,
            "password": _RACE_OWNER_PASSWORD_P102,
        },
    )
    assert r.status_code == 200, f"P102 race login failed: {r.text}"
    return client


async def test_concurrent_create_booking_slot_already_booked_clear_409(
    db_session_real_commit_p102: AsyncSession,
    app: FastAPI,
) -> None:
    """BOOK-TEST-01-P102: 2 parallel POST /api/v1/bookings against the SAME slot
    with DISTINCT Idempotency-Keys → exactly [201, 409] slot_already_booked.

    Verifies the partial UNIQUE `uq_bookings_slot_confirmed` is the
    source-of-truth winner (not a crash) and the DB reaches a deterministic
    clean state: 1 confirmed booking + slot 'booked' + 1 booking_created audit.

    Uses real-commit transactions (db_session_real_commit_p102) because SAVEPOINT
    isolation cannot observe concurrent UPDATE serialisation (mirroring
    test_booking_race.py:test_concurrent_create_booking_partial_unique_at_db_layer).
    """
    session = db_session_real_commit_p102

    # Seed owner.
    hashed = await hash_password(_RACE_OWNER_PASSWORD_P102)
    owner = User(
        email=_RACE_OWNER_EMAIL_P102,
        password_hash=hashed,
        role=Role.OWNER,
        full_name="P102 Race Owner",
    )
    session.add(owner)
    await session.commit()
    await session.refresh(owner)
    owner_id = owner.id

    # Seed plan.
    plan = PtPackagePlan(
        name=f"P102RacePlan-{uuid4().hex[:6]}",
        session_count=10,
        price_kopecks=500000,
        validity_days=90,
    )
    session.add(plan)
    await session.commit()
    await session.refresh(plan)

    # Seed client.
    phone_suffix = uuid4().int % 10**7
    client_obj = Client(
        last_name=f"P102RaceClient-{uuid4().hex[:6]}",
        first_name="Test",
        phone=f"+7907{phone_suffix:07d}",
        created_by_user_id=owner_id,
    )
    session.add(client_obj)
    await session.commit()
    await session.refresh(client_obj)

    # Seed pt_package (sessions_remaining=10; race is at the slot layer).
    today = datetime.now(tz=UTC).date()
    validity_days = plan.validity_days
    assert validity_days is not None
    pt_package = PtPackage(
        client_id=client_obj.id,
        plan_id=plan.id,
        plan_name_snapshot=plan.name,
        session_count_snapshot=plan.session_count,
        price_kopecks_snapshot=plan.price_kopecks,
        validity_days_snapshot=validity_days,
        sessions_remaining=10,
        status="active",
        start_date=today,
        end_date=today + timedelta(days=validity_days - 1),
    )
    session.add(pt_package)
    await session.commit()
    await session.refresh(pt_package)
    pt_package_id = pt_package.id

    # Seed trainer.
    trainer = Trainer(
        full_name=f"P102RaceTrainer-{uuid4().hex[:6]}",
        is_active=True,
    )
    session.add(trainer)
    await session.commit()
    await session.refresh(trainer)

    # Seed the race-target slot: next Monday 10:00 MSK (falls inside
    # Mon-Fri 00:00-23:59 working-hours window seeded by migration 0071).
    slot_start = _next_monday_10_msk()
    slot = TrainerAvailabilitySlot(
        trainer_id=trainer.id,
        start_time=slot_start,
        end_time=slot_start + timedelta(hours=1),
        status="active",
        created_by_user_id=owner_id,
    )
    session.add(slot)
    await session.commit()
    await session.refresh(slot)
    slot_id = slot.id

    # Flush Redis so idempotency keys from prior tests don't replay.
    await app.state.redis.flushdb()

    authed = await _build_authed_race_client(app)
    csrf_token = authed.cookies.get("clubcore_csrf") or ""

    async def _post(idx: int) -> Any:
        return await authed.post(
            "/api/v1/bookings",
            json={
                "slotId": str(slot_id),
                "clientId": str(client_obj.id),
                "ptPackageId": str(pt_package_id),
            },
            headers={
                "X-CSRF-Token": csrf_token,
                # DISTINCT keys so race surfaces at DB partial UNIQUE,
                # not at Redis idempotency replay cache.
                "Idempotency-Key": f"p102-race-slot-{idx}-{uuid4().hex}",
            },
        )

    # 2 parallel POST requests against the same slot.
    responses = await asyncio.gather(*[_post(i) for i in range(2)])
    await authed.aclose()

    statuses = sorted(r.status_code for r in responses)
    assert statuses == [201, 409], (
        f"P102-race: expected [201, 409], got {statuses}; "
        f"bodies: {[r.text for r in responses]}"
    )

    bodies_409 = [r.json() for r in responses if r.status_code == 409]
    codes = [b.get("code") for b in bodies_409]
    assert all(c == "slot_already_booked" for c in codes), (
        f"P102-race: unexpected 409 codes (expected all 'slot_already_booked'): {codes}"
    )

    # DB invariants: exactly 1 confirmed booking + slot 'booked'.
    session.expire_all()
    confirmed_count = await session.scalar(
        select(func.count())
        .select_from(Booking)
        .where(
            Booking.slot_id == slot_id,
            Booking.status == "confirmed",
        )
    )
    assert confirmed_count == 1, (
        f"P102-race: expected exactly 1 confirmed booking, got {confirmed_count}"
    )

    refreshed_slot = await session.scalar(
        select(TrainerAvailabilitySlot).where(TrainerAvailabilitySlot.id == slot_id)
    )
    assert refreshed_slot is not None
    assert refreshed_slot.status == "booked", (
        f"P102-race: expected slot 'booked', got '{refreshed_slot.status}'"
    )

    # Audit invariant: exactly 1 booking_created for THIS slot (loser rolled back
    # before audit emit).  Scoped by resource_id == slot_id so a stale audit row
    # from a prior run (or another test) cannot cause a false negative.
    created_count = await session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.action == "booking_created",
            AuditLog.resource_id == slot_id,  # WR-04: scope to this slot's bookings only
        )
    )
    assert created_count == 1, (
        f"P102-race: expected exactly 1 booking_created audit row for slot {slot_id}, "
        f"got {created_count}"
    )
