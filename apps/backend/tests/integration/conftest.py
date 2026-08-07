"""Shared autouse fixtures for ALL integration tests.

Phase 111 fix: Phase 108 added working_hours_config and booking_config enforcement
to bookings/service.py. The seeded defaults from migration 0071 (Mon-Fri 08:00-22:00,
60-minute cutoff) break any integration test that calls create_booking with a slot
time close in time or outside normal working hours.

This autouse fixture resets config to permissive values for every integration test.
It mirrors the same fixture in tests/integration/bookings/conftest.py (which covers
the bookings subdirectory); this top-level version covers all other integration test
directories (schedule, telegram_bot, client_portal, root test_booking_email_fallback,
etc.).

Having the fixture run twice for bookings tests (parent + child conftest) is safe —
the UPDATE is idempotent and each test is SAVEPOINT-isolated.
"""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

# Deterministic singleton PKs from migration 0071_seed_settings.
_BOOKING_CONFIG_ID = "00000000-0000-0000-0000-000000000003"
_WORKING_HOURS_CONFIG_ID = "00000000-0000-0000-0000-000000000004"

# All-day schedule for all 7 weekdays — no slot time is blocked.
_ALL_DAYS_OPEN = [
    {"day_of_week": dow, "open_time": "00:00", "close_time": "23:59"} for dow in range(0, 7)
]


@pytest_asyncio.fixture(autouse=True)
async def permissive_booking_config(
    request: pytest.FixtureRequest,
    db_session: AsyncSession,
) -> None:
    """Reset booking_config and working_hours_config to permissive values.

    Phase 108 Plan 03 added enforcement guards in bookings/service.py that read
    booking_config and working_hours_config from the DB. Tests that exercise
    cancel/reschedule/booking behavior seed slots with arbitrary timing (including
    slots close in time or outside normal working hours); they break when the seeded
    config values from migration 0071 enforce a 60-minute cutoff or Mon-Fri schedule.

    Resets to:
      booking_ahead_days=365  (allow up to a year ahead)
      cutoff_minutes=0        (no cutoff — any future slot accepted)
      cancel_window_hours=24  (preserves migration 0071 default)
      working_hours: all 7 days 00:00–23:59 (never blocked by schedule)
      closures: [] (no closure dates)

    DEADLOCK GUARD (debug session pytest-isolation-deadlock): this fixture issues
    an UNCOMMITTED ``UPDATE working_hours_config`` on the SAVEPOINT-mode
    ``db_session``. Under SAVEPOINT isolation that UPDATE never commits, so it holds
    a row lock on the working_hours_config singleton for the entire test. Tests that
    spawn ``alembic downgrade`` in a SUBPROCESS (separate connection) — the migration
    round-trip tests — execute the 0071 downgrade ``DELETE FROM working_hours_config``
    and the 0070 ``DROP TABLE working_hours_config``, which block forever on that row
    lock while the test body is blocked waiting on the subprocess (circular
    self-deadlock; no lock_timeout, no pytest-timeout => hangs at 0% CPU). Such tests
    mark themselves with ``@pytest.mark.no_permissive_booking_config`` so this fixture
    early-returns and holds no contended lock. They use their own real-commit engine
    session and never read booking/working-hours config, so skipping is safe.
    """  # noqa: RUF002
    if request.node.get_closest_marker("no_permissive_booking_config") is not None:
        return
    await db_session.execute(
        sa.text(  # noqa: TABLE_REF
            "UPDATE booking_config "
            "SET booking_ahead_days = :ahead, cutoff_minutes = :cutoff, "
            "    cancel_window_hours = :cancel_h "
            "WHERE id = CAST(:id AS uuid)"
        ),
        {
            "ahead": 365,
            "cutoff": 0,
            "cancel_h": 24,
            "id": _BOOKING_CONFIG_ID,
        },
    )
    await db_session.execute(
        sa.text(  # noqa: TABLE_REF
            "UPDATE working_hours_config "
            "SET schedule = CAST(:schedule AS jsonb), closures = CAST(:closures AS jsonb) "
            "WHERE id = CAST(:id AS uuid)"
        ),
        {
            "schedule": json.dumps(_ALL_DAYS_OPEN),
            "closures": json.dumps([]),
            "id": _WORKING_HOURS_CONFIG_ID,
        },
    )
