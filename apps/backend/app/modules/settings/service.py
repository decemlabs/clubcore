"""Settings service — orchestration between router and repository (Phase 108 CFG-02/03/04).

Read path: get_* raises SettingsNotFoundError (404) if the seed row is absent.
Write path: update_* upserts the singleton, emits LOCKED audit event, flushes and commits.

D-03 caller-owns-txn: flush + commit live HERE (service layer), not in repository.

LOCKED audit events (pre-registered in audit.py v2.7 block):
  working_hours_updated  — CFG-02 working hours
  booking_config_updated — CFG-03 booking rules
  notification_prefs_updated — CFG-04 notification matrix
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.dependencies import CurrentUser
from app.core.exceptions import NotFoundError
from app.modules.settings import repository
from app.modules.settings.schemas import (
    BookingConfigResponse,
    BookingConfigUpdateRequest,
    NotificationPrefsResponse,
    NotificationPrefsUpdateRequest,
    WorkingHoursResponse,
    WorkingHoursUpdateRequest,
)


class SettingsNotFoundError(NotFoundError):
    """Raised when get_singleton returns None (seed migration not yet run).

    HTTP 404. Code 'settings_not_found' surfaces to the client so the FE
    can show an appropriate placeholder rather than a generic error.
    """

    code = "settings_not_found"
    status_code = 404


# ---------------------------------------------------------------------------
# CFG-02: Working hours
# ---------------------------------------------------------------------------


async def get_working_hours(session: AsyncSession) -> WorkingHoursResponse:
    """Return singleton working-hours config. 404 via SettingsNotFoundError if seed missing."""
    config = await repository.get_working_hours(session)
    if config is None:
        raise SettingsNotFoundError("settings_not_found")
    return WorkingHoursResponse.model_validate(config)


async def update_working_hours(
    session: AsyncSession,
    actor: CurrentUser,
    data: WorkingHoursUpdateRequest,
) -> WorkingHoursResponse:
    """Upsert working-hours singleton. Emits LOCKED audit event + caller-owns-txn (D-03)."""
    config = await repository.upsert_working_hours(session, data)
    await audit.emit(
        session,
        "working_hours_updated",
        actor_user_id=actor.id,
        resource_type="settings",
        changed_fields=list(data.model_dump(exclude_unset=True).keys()),
    )
    await session.flush()
    await session.commit()
    return WorkingHoursResponse.model_validate(config)


# ---------------------------------------------------------------------------
# CFG-03: Booking rules
# ---------------------------------------------------------------------------


async def get_booking_config(session: AsyncSession) -> BookingConfigResponse:
    """Return singleton booking-config. 404 via SettingsNotFoundError if seed missing."""
    config = await repository.get_booking_config(session)
    if config is None:
        raise SettingsNotFoundError("settings_not_found")
    return BookingConfigResponse.model_validate(config)


async def update_booking_config(
    session: AsyncSession,
    actor: CurrentUser,
    data: BookingConfigUpdateRequest,
) -> BookingConfigResponse:
    """Upsert booking-config singleton. Emits LOCKED audit event + caller-owns-txn (D-03)."""
    config = await repository.upsert_booking_config(session, data)
    await audit.emit(
        session,
        "booking_config_updated",
        actor_user_id=actor.id,
        resource_type="settings",
        changed_fields=list(data.model_dump(exclude_unset=True).keys()),
    )
    await session.flush()
    await session.commit()
    return BookingConfigResponse.model_validate(config)


# ---------------------------------------------------------------------------
# CFG-04: Notification preferences
# ---------------------------------------------------------------------------


async def get_notification_prefs(session: AsyncSession) -> NotificationPrefsResponse:
    """Return singleton notification-prefs config. 404 via SettingsNotFoundError if seed missing."""
    config = await repository.get_notification_prefs(session)
    if config is None:
        raise SettingsNotFoundError("settings_not_found")
    return NotificationPrefsResponse.model_validate(config)


async def update_notification_prefs(
    session: AsyncSession,
    actor: CurrentUser,
    data: NotificationPrefsUpdateRequest,
) -> NotificationPrefsResponse:
    """Upsert notification-prefs singleton. Emits LOCKED audit event + caller-owns-txn (D-03)."""
    config = await repository.upsert_notification_prefs(session, data)
    await audit.emit(
        session,
        "notification_prefs_updated",
        actor_user_id=actor.id,
        resource_type="settings",
        changed_fields=list(data.model_dump(exclude_unset=True).keys()),
    )
    await session.flush()
    await session.commit()
    return NotificationPrefsResponse.model_validate(config)
