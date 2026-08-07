"""Additional integration tests for booking-settings enforcement (Phase 108 CR-01/CR-02).

CR-01: validates that the weekday convention fix (0-based weekday() replacing
       1-based isoweekday()) causes working-hours enforcement to fire correctly.
       Tests a Monday slot outside seeded Monday hours — was a no-op before the fix.

CR-02: validates that create_booking_for_client applies the same Step 4b guards
       (booking-ahead window, cutoff, working-hours/closures) that create_booking
       (staff path) applies. Both were missing from the client path before CR-02.

PKs from migration 0071_seed_settings:
  booking_config:        00000000-0000-0000-0000-000000000003
  working_hours_config:  00000000-0000-0000-0000-000000000004
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.bookings import service as booking_service
from app.modules.bookings.schemas import BookingCreateRequest
from app.modules.bookings.service import (
    BookingAheadWindowError,
    OutsideWorkingHoursError,
)

MOSCOW_TZ = ZoneInfo("Europe/Moscow")

_BOOKING_CONFIG_ID = "00000000-0000-0000-0000-000000000003"
_WORKING_HOURS_CONFIG_ID = "00000000-0000-0000-0000-000000000004"

# Permissive all-day schedule (0-based, CR-01 convention).
_ALL_DAYS_OPEN: list[Any] = [
    {"day_of_week": dow, "open_time": "00:00", "close_time": "23:59"} for dow in range(0, 7)
]


async def _set_booking_config(
    session: AsyncSession,
    *,
    booking_ahead_days: int,
    cutoff_minutes: int,
) -> None:
    await session.execute(
        sa.text(
            "UPDATE booking_config "
            "SET booking_ahead_days = :ahead, cutoff_minutes = :cutoff "
            "WHERE id = CAST(:id AS uuid)"
        ),
        {"ahead": booking_ahead_days, "cutoff": cutoff_minutes, "id": _BOOKING_CONFIG_ID},
    )
    await session.flush()


async def _set_working_hours(
    session: AsyncSession,
    *,
    schedule: list[Any],
    closures: list[Any] | None = None,
) -> None:
    await session.execute(
        sa.text(
            "UPDATE working_hours_config "
            "SET schedule = CAST(:schedule AS jsonb), "
            "    closures = CAST(:closures AS jsonb) "
            "WHERE id = CAST(:id AS uuid)"
        ),
        {
            "schedule": json.dumps(schedule),
            "closures": json.dumps(closures if closures is not None else []),
            "id": _WORKING_HOURS_CONFIG_ID,
        },
    )
    await session.flush()


async def _seed_prerequisites(
    session: AsyncSession,
    actor: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
    *,
    slot_start: datetime,
):  # type: ignore[return]
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(client_id=client.id, plan=plan, sessions_remaining=5)
    slot = await make_slot(
        trainer_id=trainer.id,
        start_time=slot_start,
        end_time=slot_start + timedelta(hours=1),
    )
    return pkg, slot, client


# ---------------------------------------------------------------------------
# CR-01: Weekday convention — 0-based weekday() fires correctly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_monday_slot_outside_seeded_monday_hours_is_blocked(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """CR-01 regression: Monday slot outside Monday-only window is rejected.

    Seeds schedule with Monday (day_of_week=0) open 09:00-10:00 MSK only.
    Creates a slot on the next Monday at 23:00 MSK → outside window → blocked.

    Before CR-01, isoweekday() returned 1 for Monday but the stored entry had
    day_of_week=0 → no match → fail-open → booking allowed (wrong behaviour).
    """
    await _set_booking_config(db_session, booking_ahead_days=30, cutoff_minutes=0)

    # Next Monday at 23:00 MSK (always within 14-day booking window, always outside
    # the narrow 09:00-10:00 window seeded below).
    _now_msk = datetime.now(UTC).astimezone(MOSCOW_TZ)
    days_to_next_monday = (7 - _now_msk.weekday()) % 7 or 7  # always ≥ 1 day ahead
    next_monday_msk = _now_msk.replace(hour=23, minute=0, second=0, microsecond=0) + timedelta(
        days=days_to_next_monday
    )
    slot_start_utc = next_monday_msk.astimezone(UTC)

    await _set_working_hours(
        db_session,
        schedule=[
            {"day_of_week": 0, "open_time": "09:00", "close_time": "10:00"},  # Monday, 0-based
        ],
        closures=[],
    )

    pkg, slot, client = await _seed_prerequisites(
        db_session,
        seeded_owner,
        make_trainer,
        make_client,
        make_pt_package_plan,
        make_pt_package,
        make_slot,
        slot_start=slot_start_utc,
    )

    with pytest.raises(OutsideWorkingHoursError):
        await booking_service.create_booking(
            db_session,
            seeded_owner,
            BookingCreateRequest(
                slot_id=slot.id,
                client_id=client.id,
                pt_package_id=pkg.id,
            ),
        )


# ---------------------------------------------------------------------------
# CR-02: Client self-service path enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_booking_ahead_window_enforced(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """CR-02: create_booking_for_client enforces booking_ahead_days.

    booking_ahead_days=1; slot is 48 h in the future → window exceeded → 409.
    Before CR-02, the client path had no Step 4b → booking was allowed.
    """
    await _set_booking_config(db_session, booking_ahead_days=1, cutoff_minutes=0)
    await _set_working_hours(db_session, schedule=_ALL_DAYS_OPEN, closures=[])

    slot_start = datetime.now(UTC) + timedelta(hours=48)
    pkg, slot, client = await _seed_prerequisites(
        db_session,
        seeded_owner,
        make_trainer,
        make_client,
        make_pt_package_plan,
        make_pt_package,
        make_slot,
        slot_start=slot_start,
    )

    with pytest.raises(BookingAheadWindowError):
        await booking_service.create_booking_for_client(
            db_session,
            client_id=client.id,
            slot_id=slot.id,
            pt_package_id=pkg.id,
        )


@pytest.mark.asyncio
async def test_client_booking_closure_date_enforced(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """CR-02: create_booking_for_client enforces closures (working-hours gate).

    Slot on a closure date → OutsideWorkingHoursError, even via the client path.
    Before CR-02, the client path had no Step 4b → closure was ignored → booking
    allowed (wrong behaviour).
    """
    await _set_booking_config(db_session, booking_ahead_days=30, cutoff_minutes=0)

    slot_start_utc = datetime.now(UTC) + timedelta(hours=48)
    slot_date_msk = slot_start_utc.astimezone(MOSCOW_TZ).date().isoformat()

    # Empty schedule + closure on the slot's Moscow date → blocked.
    await _set_working_hours(
        db_session,
        schedule=[],
        closures=[slot_date_msk],
    )

    pkg, slot, client = await _seed_prerequisites(
        db_session,
        seeded_owner,
        make_trainer,
        make_client,
        make_pt_package_plan,
        make_pt_package,
        make_slot,
        slot_start=slot_start_utc,
    )

    with pytest.raises(OutsideWorkingHoursError):
        await booking_service.create_booking_for_client(
            db_session,
            client_id=client.id,
            slot_id=slot.id,
            pt_package_id=pkg.id,
        )
