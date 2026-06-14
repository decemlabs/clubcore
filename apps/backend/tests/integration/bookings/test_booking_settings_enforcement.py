"""Integration tests for booking-settings enforcement (Phase 108 CFG-02/03).

Tests the create_booking guards added in Plan 03 Task 1:
  - Booking-ahead window exceeded → 409 booking_ahead_window_exceeded.
  - Booking-ahead window OK → success.
  - Cutoff window passed → 409 booking_cutoff_passed.
  - Cutoff window OK → success.
  - Slot on closure date → 409 outside_working_hours.
  - Slot on open day/time → success.
  - Cancel window from config (present): custom cancel_window_hours respected.
  - Cancel window fallback (config row absent): falls back to CANCEL_WINDOW_HOURS_RECEPTION (24h) without erroring.
  - Working-hours fail-open: absent/empty schedule does NOT block booking.

Config seeded via direct DB writes against deterministic PKs (no Plan-02 PUT
dependency — self-contained on Plan 01 per 108-03-PLAN.md).

PKs from migration 0071_seed_settings:
  booking_config:        00000000-0000-0000-0000-000000000003
  working_hours_config:  00000000-0000-0000-0000-000000000004
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from zoneinfo import ZoneInfo

from app.modules.auth.models import User
from app.modules.bookings import service as booking_service
from app.modules.bookings.constants import CANCEL_WINDOW_HOURS_RECEPTION
from app.modules.bookings.service import (
    BookingAheadWindowError,
    BookingCutoffError,
    CancelWindowExpiredError,
    OutsideWorkingHoursError,
)
from app.modules.bookings.schemas import (
    BookingCancelRequest,
    BookingCreateRequest,
)
from app.modules.clients.models import Client
from app.modules.pt_packages.models import PtPackage
from app.modules.schedule.models import TrainerAvailabilitySlot

MOSCOW_TZ = ZoneInfo("Europe/Moscow")

# Deterministic singleton PKs from migration 0071_seed_settings.
_BOOKING_CONFIG_ID = "00000000-0000-0000-0000-000000000003"
_WORKING_HOURS_CONFIG_ID = "00000000-0000-0000-0000-000000000004"

# Permissive schedule covering all 7 days, 00:00 - 23:59.
# day_of_week: 0=Monday … 6=Sunday (CR-01 fix: 0-based convention, matches seed/frontend).
_ALL_DAYS_OPEN: list[Any] = [
    {"day_of_week": dow, "open_time": "00:00", "close_time": "23:59"}
    for dow in range(0, 7)
]


# ---------------------------------------------------------------------------
# Helpers — direct DB config manipulation via raw SQL against known PKs.
# ---------------------------------------------------------------------------


async def _set_booking_config(
    session: AsyncSession,
    *,
    booking_ahead_days: int | None = None,
    cutoff_minutes: int | None = None,
    cancel_window_hours: int | None = None,
) -> None:
    """Update booking_config singleton fields directly (not via Plan-02 endpoint)."""
    updates: list[str] = []
    params: dict[str, object] = {"id": _BOOKING_CONFIG_ID}
    if booking_ahead_days is not None:
        updates.append("booking_ahead_days = :booking_ahead_days")
        params["booking_ahead_days"] = booking_ahead_days
    if cutoff_minutes is not None:
        updates.append("cutoff_minutes = :cutoff_minutes")
        params["cutoff_minutes"] = cutoff_minutes
    if cancel_window_hours is not None:
        updates.append("cancel_window_hours = :cancel_window_hours")
        params["cancel_window_hours"] = cancel_window_hours
    if not updates:
        return
    sql = (
        "UPDATE booking_config SET "
        + ", ".join(updates)
        + " WHERE id = CAST(:id AS uuid)"
    )
    await session.execute(sa.text(sql), params)
    await session.flush()


async def _set_working_hours(
    session: AsyncSession,
    *,
    schedule: list[Any],
    closures: list[Any] | None = None,
) -> None:
    """Update working_hours_config singleton schedule/closures directly."""
    params: dict[str, object] = {
        "id": _WORKING_HOURS_CONFIG_ID,
        "schedule": json.dumps(schedule),
        "closures": json.dumps(closures if closures is not None else []),
    }
    await session.execute(
        sa.text(
            "UPDATE working_hours_config "
            "SET schedule = CAST(:schedule AS jsonb), "
            "    closures = CAST(:closures AS jsonb) "
            "WHERE id = CAST(:id AS uuid)"
        ),
        params,
    )
    await session.flush()


async def _set_permissive_config(session: AsyncSession) -> None:
    """Set booking_config and working_hours_config to fully permissive defaults.

    Use this in tests that focus on a specific guard and don't want other
    guards to interfere.
    """
    await _set_booking_config(
        session,
        booking_ahead_days=365,
        cutoff_minutes=0,
        cancel_window_hours=1,
    )
    await _set_working_hours(session, schedule=_ALL_DAYS_OPEN, closures=[])


async def _delete_booking_config_row(session: AsyncSession) -> None:
    """DELETE the booking_config singleton (tests absent-config fallback path)."""
    await session.execute(
        sa.text("DELETE FROM booking_config WHERE id = CAST(:id AS uuid)"),
        {"id": _BOOKING_CONFIG_ID},
    )
    await session.flush()


# ---------------------------------------------------------------------------
# Shared setup helper.
# ---------------------------------------------------------------------------


async def _seed_booking_prerequisites(
    session: AsyncSession,
    actor: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
    *,
    slot_start: datetime | None = None,
) -> tuple[PtPackage, TrainerAvailabilitySlot, Client]:
    """Seed trainer/client/plan/pkg/slot; return (pkg, slot, client)."""
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(client_id=client.id, plan=plan, sessions_remaining=5)
    if slot_start is None:
        slot_start = datetime.now(UTC) + timedelta(hours=48)
    slot = await make_slot(
        trainer_id=trainer.id,
        start_time=slot_start,
        end_time=slot_start + timedelta(hours=1),
    )
    return pkg, slot, client


# ===========================================================================
# GUARD 1: Booking-ahead window enforcement (booking_ahead_days)
# ===========================================================================


@pytest.mark.asyncio
async def test_booking_ahead_window_exceeded_rejected(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """Slot > booking_ahead_days in future → 409 booking_ahead_window_exceeded."""
    # Set booking_ahead_days to 1 day, cutoff=0, all-day working hours.
    await _set_booking_config(db_session, booking_ahead_days=1, cutoff_minutes=0)
    await _set_working_hours(db_session, schedule=_ALL_DAYS_OPEN)

    slot_start = datetime.now(UTC) + timedelta(hours=48)  # 2 days in future
    pkg, slot, client = await _seed_booking_prerequisites(
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
        await booking_service.create_booking(
            db_session,
            seeded_owner,
            BookingCreateRequest(
                slot_id=slot.id,
                client_id=client.id,
                pt_package_id=pkg.id,
            ),
        )


@pytest.mark.asyncio
async def test_booking_ahead_window_within_limit_ok(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """Slot <= booking_ahead_days in future → booking succeeds."""
    await _set_booking_config(db_session, booking_ahead_days=30, cutoff_minutes=0)
    await _set_working_hours(db_session, schedule=_ALL_DAYS_OPEN)

    slot_start = datetime.now(UTC) + timedelta(hours=48)
    pkg, slot, client = await _seed_booking_prerequisites(
        db_session,
        seeded_owner,
        make_trainer,
        make_client,
        make_pt_package_plan,
        make_pt_package,
        make_slot,
        slot_start=slot_start,
    )

    response = await booking_service.create_booking(
        db_session,
        seeded_owner,
        BookingCreateRequest(
            slot_id=slot.id,
            client_id=client.id,
            pt_package_id=pkg.id,
        ),
    )
    assert response.status.value == "confirmed"


# ===========================================================================
# GUARD 2: Cutoff window enforcement (cutoff_minutes)
# ===========================================================================


@pytest.mark.asyncio
async def test_booking_cutoff_passed_rejected(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """Slot within cutoff_minutes → 409 booking_cutoff_passed."""
    # cutoff=120min; slot is 30min in the future → inside cutoff → blocked.
    await _set_booking_config(db_session, booking_ahead_days=30, cutoff_minutes=120)
    await _set_working_hours(db_session, schedule=_ALL_DAYS_OPEN)

    slot_start = datetime.now(UTC) + timedelta(minutes=30)
    pkg, slot, client = await _seed_booking_prerequisites(
        db_session,
        seeded_owner,
        make_trainer,
        make_client,
        make_pt_package_plan,
        make_pt_package,
        make_slot,
        slot_start=slot_start,
    )

    with pytest.raises(BookingCutoffError):
        await booking_service.create_booking(
            db_session,
            seeded_owner,
            BookingCreateRequest(
                slot_id=slot.id,
                client_id=client.id,
                pt_package_id=pkg.id,
            ),
        )


@pytest.mark.asyncio
async def test_booking_cutoff_ok_when_slot_beyond_cutoff(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """Slot well beyond cutoff_minutes → succeeds."""
    await _set_booking_config(db_session, booking_ahead_days=30, cutoff_minutes=60)
    await _set_working_hours(db_session, schedule=_ALL_DAYS_OPEN)

    slot_start = datetime.now(UTC) + timedelta(hours=48)
    pkg, slot, client = await _seed_booking_prerequisites(
        db_session,
        seeded_owner,
        make_trainer,
        make_client,
        make_pt_package_plan,
        make_pt_package,
        make_slot,
        slot_start=slot_start,
    )

    response = await booking_service.create_booking(
        db_session,
        seeded_owner,
        BookingCreateRequest(
            slot_id=slot.id,
            client_id=client.id,
            pt_package_id=pkg.id,
        ),
    )
    assert response.status.value == "confirmed"


# ===========================================================================
# GUARD 3: Closure / working-hours enforcement
# ===========================================================================


@pytest.mark.asyncio
async def test_closure_date_blocks_booking(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """Slot on a closure date → 409 outside_working_hours."""
    await _set_booking_config(db_session, booking_ahead_days=30, cutoff_minutes=0)

    slot_start_utc = datetime.now(UTC) + timedelta(hours=48)
    slot_date_msk = slot_start_utc.astimezone(MOSCOW_TZ).date().isoformat()

    # Empty schedule (fail-open per se) but closure contains the slot's date → blocked.
    await _set_working_hours(
        db_session,
        schedule=[],
        closures=[slot_date_msk],
    )

    pkg, slot, client = await _seed_booking_prerequisites(
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


@pytest.mark.asyncio
async def test_open_day_allows_booking(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """Slot within working hours on a non-closure day → booking succeeds."""
    await _set_booking_config(db_session, booking_ahead_days=30, cutoff_minutes=0)

    slot_start_utc = datetime.now(UTC) + timedelta(hours=48)
    # CR-01 fix: use 0-based weekday() to match the enforcement code convention.
    zero_weekday = slot_start_utc.astimezone(MOSCOW_TZ).weekday()  # 0=Mon, 6=Sun

    await _set_working_hours(
        db_session,
        schedule=[
            {
                "day_of_week": zero_weekday,
                "open_time": "00:00",
                "close_time": "23:59",
            }
        ],
        closures=[],
    )

    pkg, slot, client = await _seed_booking_prerequisites(
        db_session,
        seeded_owner,
        make_trainer,
        make_client,
        make_pt_package_plan,
        make_pt_package,
        make_slot,
        slot_start=slot_start_utc,
    )

    response = await booking_service.create_booking(
        db_session,
        seeded_owner,
        BookingCreateRequest(
            slot_id=slot.id,
            client_id=client.id,
            pt_package_id=pkg.id,
        ),
    )
    assert response.status.value == "confirmed"


# ===========================================================================
# GUARD 4: Cancel window — config present (custom cancel_window_hours)
# ===========================================================================


@pytest.mark.asyncio
async def test_cancel_window_config_present_allows_cancel(
    db_session: AsyncSession,
    seeded_owner: User,
    seeded_reception: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """Config present: cancel_window_hours = 2 allows a cancel 5h before slot."""
    # Set cancel window to 2h; slot is 5h away → outside window → ALLOWED.
    await _set_permissive_config(db_session)
    await _set_booking_config(db_session, cancel_window_hours=2)

    slot_start = datetime.now(UTC) + timedelta(hours=5)
    pkg, slot, client = await _seed_booking_prerequisites(
        db_session,
        seeded_owner,
        make_trainer,
        make_client,
        make_pt_package_plan,
        make_pt_package,
        make_slot,
        slot_start=slot_start,
    )
    created = await booking_service.create_booking(
        db_session,
        seeded_owner,
        BookingCreateRequest(
            slot_id=slot.id,
            client_id=client.id,
            pt_package_id=pkg.id,
        ),
    )

    # Reception cancels 5h before slot; 2h window → 5h > 2h → OK.
    result = await booking_service.cancel_booking(
        db_session,
        seeded_reception,
        created.id,
        BookingCancelRequest(reason="test cancel"),
    )
    assert result.status.value == "cancelled"


@pytest.mark.asyncio
async def test_cancel_window_config_present_blocks_too_close(
    db_session: AsyncSession,
    seeded_owner: User,
    seeded_reception: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """Config present: cancel_window_hours = 100 blocks a cancel 48h before slot."""
    # Set cancel window to 100h; slot is 48h away → inside window → BLOCKED.
    await _set_permissive_config(db_session)
    await _set_booking_config(db_session, cancel_window_hours=100)

    slot_start = datetime.now(UTC) + timedelta(hours=48)
    pkg, slot, client = await _seed_booking_prerequisites(
        db_session,
        seeded_owner,
        make_trainer,
        make_client,
        make_pt_package_plan,
        make_pt_package,
        make_slot,
        slot_start=slot_start,
    )
    created = await booking_service.create_booking(
        db_session,
        seeded_owner,
        BookingCreateRequest(
            slot_id=slot.id,
            client_id=client.id,
            pt_package_id=pkg.id,
        ),
    )

    with pytest.raises(CancelWindowExpiredError):
        await booking_service.cancel_booking(
            db_session,
            seeded_reception,
            created.id,
            BookingCancelRequest(reason="test cancel"),
        )


# ===========================================================================
# GUARD 5: Cancel window — config ABSENT (fallback to CANCEL_WINDOW_HOURS_RECEPTION)
# ===========================================================================


@pytest.mark.asyncio
async def test_cancel_window_absent_config_fallback_succeeds(
    db_session: AsyncSession,
    seeded_owner: User,
    seeded_reception: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """DELETE booking_config row → cancel falls back to 24h constant without erroring.

    T-108-11 fail-open: absent config MUST NOT raise/500.
    Fallback = CANCEL_WINDOW_HOURS_RECEPTION (24h). Slot 48h away → allowed.
    """
    # Start permissive so we can create the booking, then delete the row.
    await _set_permissive_config(db_session)

    slot_start = datetime.now(UTC) + timedelta(hours=48)
    pkg, slot, client = await _seed_booking_prerequisites(
        db_session,
        seeded_owner,
        make_trainer,
        make_client,
        make_pt_package_plan,
        make_pt_package,
        make_slot,
        slot_start=slot_start,
    )
    created = await booking_service.create_booking(
        db_session,
        seeded_owner,
        BookingCreateRequest(
            slot_id=slot.id,
            client_id=client.id,
            pt_package_id=pkg.id,
        ),
    )

    # DELETE the booking_config row → simulate absent config.
    await _delete_booking_config_row(db_session)

    # Slot is 48h in the future; fallback = 24h → 48 > 24 → cancel succeeds.
    result = await booking_service.cancel_booking(
        db_session,
        seeded_reception,
        created.id,
        BookingCancelRequest(reason="absent config fallback test"),
    )
    assert result.status.value == "cancelled"


@pytest.mark.asyncio
async def test_cancel_window_absent_config_blocks_within_fallback(
    db_session: AsyncSession,
    seeded_owner: User,
    seeded_reception: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """DELETE booking_config row → fallback 24h still blocks a cancel 5h before slot.

    Confirms the fallback constant (CANCEL_WINDOW_HOURS_RECEPTION = 24) is
    active, not a permissive 0. No exception should come from missing config.
    """
    await _set_permissive_config(db_session)

    slot_start = datetime.now(UTC) + timedelta(hours=5)
    pkg, slot, client = await _seed_booking_prerequisites(
        db_session,
        seeded_owner,
        make_trainer,
        make_client,
        make_pt_package_plan,
        make_pt_package,
        make_slot,
        slot_start=slot_start,
    )
    created = await booking_service.create_booking(
        db_session,
        seeded_owner,
        BookingCreateRequest(
            slot_id=slot.id,
            client_id=client.id,
            pt_package_id=pkg.id,
        ),
    )

    # DELETE booking_config row → fallback to CANCEL_WINDOW_HOURS_RECEPTION (24h).
    await _delete_booking_config_row(db_session)

    # Slot is 5h away; 5 < 24 → blocked by fallback constant.
    with pytest.raises(CancelWindowExpiredError):
        await booking_service.cancel_booking(
            db_session,
            seeded_reception,
            created.id,
            BookingCancelRequest(reason="fallback blocks test"),
        )

    # Verify the fallback constant is still 24h as documented.
    assert CANCEL_WINDOW_HOURS_RECEPTION == 24


# ===========================================================================
# GUARD 6: Defensive fail-open — empty/absent working hours schedule
# ===========================================================================


@pytest.mark.asyncio
async def test_empty_working_hours_schedule_does_not_block(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """Empty schedule in working_hours_config → booking is NOT blocked (fail-open).

    T-108-11: misconfigured/empty schedule must never brick the booking flow.
    """
    await _set_booking_config(db_session, booking_ahead_days=30, cutoff_minutes=0)
    # Empty schedule, no closures → fail-open → booking allowed.
    await _set_working_hours(db_session, schedule=[], closures=[])

    slot_start = datetime.now(UTC) + timedelta(hours=48)
    pkg, slot, client = await _seed_booking_prerequisites(
        db_session,
        seeded_owner,
        make_trainer,
        make_client,
        make_pt_package_plan,
        make_pt_package,
        make_slot,
        slot_start=slot_start,
    )

    response = await booking_service.create_booking(
        db_session,
        seeded_owner,
        BookingCreateRequest(
            slot_id=slot.id,
            client_id=client.id,
            pt_package_id=pkg.id,
        ),
    )
    assert response.status.value == "confirmed"
