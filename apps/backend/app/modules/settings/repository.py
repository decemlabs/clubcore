"""Settings repository — single point of access to settings singleton ORM models (Phase 108).

This is the ONLY module that imports the settings ORM models. Service layer
calls these module-level async helpers and never executes select(BookingConfig)
etc. directly.

Transaction control (D-03): NO session.commit() and NO session.flush() here.
Caller (service.py) owns the transactional moment.

Deterministic PKs (from migration 0071_seed_settings):
  BookingConfig PK:            00000000-0000-0000-0000-000000000003
  WorkingHoursConfig PK:       00000000-0000-0000-0000-000000000004
  NotificationPrefsConfig PK:  00000000-0000-0000-0000-000000000005
"""

from __future__ import annotations

import uuid as _uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.settings.models import BookingConfig, NotificationPrefsConfig, WorkingHoursConfig
from app.modules.settings.schemas import (
    BookingConfigUpdateRequest,
    NotificationPrefsUpdateRequest,
    WorkingHoursUpdateRequest,
)

_BOOKING_CONFIG_PK = "00000000-0000-0000-0000-000000000003"
_WORKING_HOURS_CONFIG_PK = "00000000-0000-0000-0000-000000000004"
_NOTIFICATION_PREFS_CONFIG_PK = "00000000-0000-0000-0000-000000000005"


# ---------------------------------------------------------------------------
# WorkingHoursConfig
# ---------------------------------------------------------------------------


async def get_working_hours(session: AsyncSession) -> WorkingHoursConfig | None:
    """Return the singleton working-hours config row, or None if seed not yet run."""
    stmt = select(WorkingHoursConfig).limit(1)
    result: WorkingHoursConfig | None = await session.scalar(stmt)
    return result


async def upsert_working_hours(
    session: AsyncSession,
    data: WorkingHoursUpdateRequest,
) -> WorkingHoursConfig:
    """Update the singleton working-hours row in-place. Caller owns flush+commit (D-03).

    Applies exclude_unset model_dump so partial payloads only touch supplied fields.
    Defensive guard: if the seed row is missing, constructs a new WorkingHoursConfig.
    """
    config = await get_working_hours(session)
    if config is None:
        # Defensive path — should not occur after migration 0071 seed.
        # WR-05: assign the deterministic singleton PK so enforcement reads
        # via _read_working_hours_config (WHERE id = '...000004') can find
        # this row. A random UUID would be invisible to the raw-SQL reads.
        config = WorkingHoursConfig(id=_uuid.UUID(_WORKING_HOURS_CONFIG_PK))
        session.add(config)
    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(config, key, value)
    return config


# ---------------------------------------------------------------------------
# BookingConfig
# ---------------------------------------------------------------------------


async def get_booking_config(session: AsyncSession) -> BookingConfig | None:
    """Return the singleton booking-config row, or None if seed not yet run."""
    stmt = select(BookingConfig).limit(1)
    result: BookingConfig | None = await session.scalar(stmt)
    return result


async def upsert_booking_config(
    session: AsyncSession,
    data: BookingConfigUpdateRequest,
) -> BookingConfig:
    """Update the singleton booking-config row in-place. Caller owns flush+commit (D-03).

    Applies exclude_unset model_dump so partial payloads only touch supplied fields.
    Defensive guard: if the seed row is missing, constructs a new BookingConfig.
    """
    config = await get_booking_config(session)
    if config is None:
        # Defensive path — should not occur after migration 0071 seed.
        # WR-05: assign the deterministic singleton PK so enforcement reads
        # via _read_booking_config (WHERE id = '...000003') can find this row.
        config = BookingConfig(id=_uuid.UUID(_BOOKING_CONFIG_PK))
        session.add(config)
    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(config, key, value)
    return config


# ---------------------------------------------------------------------------
# NotificationPrefsConfig
# ---------------------------------------------------------------------------


async def get_notification_prefs(session: AsyncSession) -> NotificationPrefsConfig | None:
    """Return the singleton notification-prefs config row, or None if seed not yet run."""
    stmt = select(NotificationPrefsConfig).limit(1)
    result: NotificationPrefsConfig | None = await session.scalar(stmt)
    return result


async def upsert_notification_prefs(
    session: AsyncSession,
    data: NotificationPrefsUpdateRequest,
) -> NotificationPrefsConfig:
    """Update the singleton notification-prefs row in-place. Caller owns flush+commit (D-03).

    Applies exclude_unset model_dump so partial payloads only touch supplied fields.
    Defensive guard: if the seed row is missing, constructs a new NotificationPrefsConfig.
    """
    config = await get_notification_prefs(session)
    if config is None:
        # Defensive path — should not occur after migration 0071 seed.
        # WR-05: assign the deterministic singleton PK so GET reads (LIMIT 1
        # fallback) and any future keyed reads both find the same row.
        config = NotificationPrefsConfig(id=_uuid.UUID(_NOTIFICATION_PREFS_CONFIG_PK))
        session.add(config)
    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(config, key, value)
    return config
