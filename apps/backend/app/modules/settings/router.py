"""Settings router — owner-only GET + PUT endpoints (Phase 108 CFG-02/03/04).

owner_router: GET + PUT /api/v1/settings/hours        — CFG-02 working hours
              GET + PUT /api/v1/settings/booking      — CFG-03 booking rules
              GET + PUT /api/v1/settings/notifications — CFG-04 notification matrix

RBAC-04 ordering: require_permission declared BEFORE verify_csrf on every PUT
so reception fails at 403 before reaching the CSRF check (mirrors gym/router.py T-86-04).

GET endpoints are also owner-only (gated on require_permission(VIEW, SETTINGS) which is
already in OWNER_ONLY per Plan 01) so reception cannot read settings values.

No try/except — AppError subclasses bubble to _app_error_handler in app/main.py.
No Idempotency-Key — upserts are idempotent by design (same key, same effect).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission, verify_csrf
from app.core.permissions import Action, Resource
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.settings import service
from app.modules.settings.schemas import (
    BookingConfigResponse,
    BookingConfigUpdateRequest,
    NotificationPrefsResponse,
    NotificationPrefsUpdateRequest,
    WorkingHoursResponse,
    WorkingHoursUpdateRequest,
)

owner_router = APIRouter(tags=["Settings"])


# ---------------------------------------------------------------------------
# CFG-02: Working hours / breaks / closures
# ---------------------------------------------------------------------------


@owner_router.get(
    "/hours",
    response_model=ResponseEnvelope[WorkingHoursResponse],
    operation_id="owner_get_working_hours",
    summary="Get working hours / breaks / closures (owner-only; CFG-02)",
)
async def owner_get_working_hours(
    actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.SETTINGS))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[WorkingHoursResponse]:
    """Return the singleton working-hours config.

    require_permission(VIEW, SETTINGS) gate: reception → 403 (VIEW is in OWNER_ONLY per Plan 01).
    SettingsNotFoundError (404) surfaces when seed migration has not been run.
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.get_working_hours(session)
    return envelope(result)


@owner_router.put(
    "/hours",
    response_model=ResponseEnvelope[WorkingHoursResponse],
    operation_id="owner_update_working_hours",
    summary="Update working hours / breaks / closures (owner-only; CFG-02)",
)
async def owner_update_working_hours(
    payload: WorkingHoursUpdateRequest,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.EDIT, Resource.SETTINGS))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[WorkingHoursResponse]:
    """Partial upsert of the singleton working-hours config.

    RBAC-04 ordering: require_permission(EDIT, SETTINGS) declared BEFORE verify_csrf.
    Reception → 403 from require_permission before reaching CSRF check (T-108-06).
    T-108-07: verify_csrf guards against cross-site forgery.
    T-108-05: WorkingHoursUpdateRequest extra='forbid' → 422 on unknown keys.
    T-108-08: working_hours_updated audit event emitted in service layer.
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.update_working_hours(session, actor, payload)
    return envelope(result)


# ---------------------------------------------------------------------------
# CFG-03: Booking rules
# ---------------------------------------------------------------------------


@owner_router.get(
    "/booking",
    response_model=ResponseEnvelope[BookingConfigResponse],
    operation_id="owner_get_booking_config",
    summary="Get booking configuration (owner-only; CFG-03)",
)
async def owner_get_booking_config(
    actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.SETTINGS))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[BookingConfigResponse]:
    """Return the singleton booking-config.

    require_permission(VIEW, SETTINGS) gate: reception → 403.
    SettingsNotFoundError (404) surfaces when seed migration has not been run.
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.get_booking_config(session)
    return envelope(result)


@owner_router.put(
    "/booking",
    response_model=ResponseEnvelope[BookingConfigResponse],
    operation_id="owner_update_booking_config",
    summary="Update booking configuration (owner-only; CFG-03)",
)
async def owner_update_booking_config(
    payload: BookingConfigUpdateRequest,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.EDIT, Resource.SETTINGS))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[BookingConfigResponse]:
    """Partial upsert of the singleton booking-config.

    RBAC-04 ordering: require_permission(EDIT, SETTINGS) declared BEFORE verify_csrf.
    Reception → 403 from require_permission before reaching CSRF check (T-108-06).
    T-108-07: verify_csrf guards against cross-site forgery.
    T-108-05: BookingConfigUpdateRequest extra='forbid' + numeric bounds → 422 on invalid input.
    T-108-08: booking_config_updated audit event emitted in service layer.
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.update_booking_config(session, actor, payload)
    return envelope(result)


# ---------------------------------------------------------------------------
# CFG-04: Notification preferences
# ---------------------------------------------------------------------------


@owner_router.get(
    "/notifications",
    response_model=ResponseEnvelope[NotificationPrefsResponse],
    operation_id="owner_get_notification_prefs",
    summary="Get notification preferences (owner-only; CFG-04)",
)
async def owner_get_notification_prefs(
    actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.SETTINGS))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[NotificationPrefsResponse]:
    """Return the singleton notification-prefs config.

    require_permission(VIEW, SETTINGS) gate: reception → 403.
    SettingsNotFoundError (404) surfaces when seed migration has not been run.
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.get_notification_prefs(session)
    return envelope(result)


@owner_router.put(
    "/notifications",
    response_model=ResponseEnvelope[NotificationPrefsResponse],
    operation_id="owner_update_notification_prefs",
    summary="Update notification preferences (owner-only; CFG-04)",
)
async def owner_update_notification_prefs(
    payload: NotificationPrefsUpdateRequest,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.EDIT, Resource.SETTINGS))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[NotificationPrefsResponse]:
    """Partial upsert of the singleton notification-prefs config.

    RBAC-04 ordering: require_permission(EDIT, SETTINGS) declared BEFORE verify_csrf.
    Reception → 403 from require_permission before reaching CSRF check (T-108-06).
    T-108-07: verify_csrf guards against cross-site forgery.
    T-108-05: NotificationPrefsUpdateRequest extra='forbid' + field bounds → 422 on invalid input.
    T-108-08: notification_prefs_updated audit event emitted in service layer.
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.update_notification_prefs(session, actor, payload)
    return envelope(result)
