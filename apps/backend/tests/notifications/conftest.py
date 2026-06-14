"""Test fixtures for notifications service tests (Phase 87 INBOX-01..04).

Re-exports the make_client and make_user fixtures from the client_portal conftest
so tests in this directory can use the same DB-direct client factory.

Phase 111 fix: adds permissive_booking_config autouse fixture so that
test_notifications_event_hooks.py (which calls bookings_service.create_booking
with arbitrary slot times) doesn't fail on the working_hours_config enforcement
added in Phase 108.
"""

from __future__ import annotations

import json

import sqlalchemy as sa
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from tests.modules.client_portal.conftest import make_client, make_user

__all__ = ["make_client", "make_user"]

# Deterministic singleton PKs from migration 0071_seed_settings.
_BOOKING_CONFIG_ID = "00000000-0000-0000-0000-000000000003"
_WORKING_HOURS_CONFIG_ID = "00000000-0000-0000-0000-000000000004"

# All-day schedule for all 7 weekdays — no slot time is blocked.
_ALL_DAYS_OPEN = [
    {"day_of_week": dow, "open_time": "00:00", "close_time": "23:59"}
    for dow in range(0, 7)
]


@pytest_asyncio.fixture(autouse=True)
async def permissive_booking_config(db_session: AsyncSession) -> None:
    """Reset booking_config and working_hours_config to permissive values.

    Phase 108 working_hours enforcement in bookings/service.py breaks tests that
    create bookings with arbitrary slot times (e.g. now+2h at midnight = outside
    08:00-22:00 Moscow working hours).
    """
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
