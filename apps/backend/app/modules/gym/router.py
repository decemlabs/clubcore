"""Gym-info router — client read + owner write endpoints (Phase 86 GYM-01/GYM-02).

Two APIRouter instances in one file:
  client_router: GET /api/v1/client/gym   — require_client gate (GYM-01)
  owner_router:  PUT /api/v1/gym          — require_permission(EDIT, GYM) + verify_csrf (GYM-02)

RBAC-04 ordering: in owner_update_gym_info, require_permission is declared BEFORE
verify_csrf so reception fails at 403 before reaching the CSRF check.

No try/except — AppError subclasses (including GymInfoNotFoundError) bubble to
_app_error_handler in app/main.py.

Gym is a singleton: every authenticated client sees the same facility info.
D-20-IDOR: not applicable here — no per-client data; the gym row is shared facility
content visible to all authenticated clients by design (T-86-08 accepted).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import ClientPrincipal, CurrentUser, require_client, require_permission, verify_csrf
from app.core.permissions import Action, Resource
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.gym import service
from app.modules.gym.schemas import GymInfoResponse, GymInfoUpdateRequest

client_router = APIRouter(tags=["Client-Portal"])


@client_router.get(
    "/gym",
    response_model=ResponseEnvelope[GymInfoResponse],
    operation_id="client_get_gym_info",
    summary="Gym facility info for the authenticated client (GYM-01)",
)
async def client_get_gym_info(
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[GymInfoResponse]:
    """Return the singleton gym-info row.

    require_client() gate: unauthenticated requests → 401; non-client tokens → 403.
    Gym is a singleton — every authenticated client sees the same row (T-86-08 accepted).
    GymInfoNotFoundError (404) surfaces when the seed migration has not been run.
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.get_gym_info(session)
    return envelope(result)


owner_router = APIRouter(tags=["Gym"])


@owner_router.put(
    "",
    response_model=ResponseEnvelope[GymInfoResponse],
    operation_id="owner_update_gym_info",
    summary="Update gym facility info (owner-only; GYM-02)",
)
async def owner_update_gym_info(
    payload: GymInfoUpdateRequest,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.EDIT, Resource.GYM))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[GymInfoResponse]:
    """Partial upsert of the singleton gym-info row.

    RBAC-04 ordering: require_permission(EDIT, GYM) declared BEFORE verify_csrf.
    Reception role → 403 from require_permission before reaching CSRF check (T-86-04).
    T-86-06: verify_csrf guards against cross-site forgery on the owner mutation.
    T-86-07: GymInfoUpdateRequest extra='forbid' → 422 on unknown keys.
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.update_gym_info(session, actor, payload)
    return envelope(result)
