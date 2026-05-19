"""Phase 43 users module router (USERS-01..05 — D-43-09 / D-43-29).

Endpoint surface (6 routes):
  - GET    /api/v1/users                              — paginated list (USERS-02)
  - POST   /api/v1/users                              — create + invite (USERS-03)
  - PATCH  /api/v1/users/{user_id}/deactivate         — deactivate (USERS-04)
  - PATCH  /api/v1/users/{user_id}/reactivate         — reactivate (USERS-04)
  - DELETE /api/v1/users/{user_id}                    — soft-delete (USERS-05)
  - POST   /api/v1/users/invitations/{token_id}/revoke — revoke invitation (USERS-03)

Permission mapping (D-41-22 / D-43-11):
  - GET                                  → require_permission(LIST,   USERS)
  - POST /                               → require_permission(CREATE, USERS) + CSRF
  - PATCH /{id}/deactivate               → require_permission(UPDATE, USERS) + CSRF
  - PATCH /{id}/reactivate               → require_permission(UPDATE, USERS) + CSRF
  - DELETE /{id}                         → require_permission(DELETE, USERS) + CSRF
  - POST /invitations/{token_id}/revoke  → require_permission(UPDATE, USERS) + CSRF

RBAC-04 ordering (D-43-29 / clients/router.py:16-19): in every mutation endpoint,
`Depends(require_permission(...))` is declared BEFORE `Depends(verify_csrf)` in the
function signature. FastAPI resolves signature dependencies in declaration order, so
401 (auth) fires before 403 (rbac/csrf), preserving the invariant that an
unauthenticated caller never sees a CSRF error. All (Action.{LIST,CREATE,UPDATE,DELETE},
Resource.USERS) pairs are in OWNER_ONLY (core/permissions.py:120-123), so reception
gets 403 from require_permission on every endpoint here.

Wire format (D-43-13 / D-43-15):
  - GET            → ResponseEnvelope[PaginatedData[UserListItemResponse]] (200)
  - POST /         → ResponseEnvelope[UserCreateResponse] (201)
  - PATCH/DELETE/revoke → 204 No Content (no body)

Exception handling (D-12/D-13): all service-layer exceptions
(`UserNotFoundError`, `EmailAlreadyActiveError`, `CannotDeactivateLastOwnerError`, ...)
extend `AppError` and are mapped to JSON responses by the global handler registered
in `app.core.exceptions.register_exception_handlers` — no per-endpoint try/except
needed (mirrors clients/router.py:101 — `ClientNotFoundError` flows uncaught).

Service layer is the single mutation entry point — this router never imports the User
ORM model (D-43-09 architectural boundary maintained transitively via service.py).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission, verify_csrf
from app.core.pagination import PaginatedData
from app.core.permissions import Action, Resource
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.users import service
from app.modules.users.schemas import (
    InvitationRevokeRequest,
    UserCreateRequest,
    UserCreateResponse,
    UserListItemResponse,
    UserListQuery,
)

router = APIRouter()


@router.get(
    "",
    response_model=ResponseEnvelope[PaginatedData[UserListItemResponse]],
    summary="List users with optional active/deleted filters and pagination",
)
async def list_users_endpoint(
    query: Annotated[UserListQuery, Depends()],
    _actor: Annotated[
        CurrentUser, Depends(require_permission(Action.LIST, Resource.USERS))
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[UserListItemResponse]]:
    """USERS-02 — paginated list (D-43-15). LIST permission required; no CSRF (read)."""
    page = await service.list_users(session, query)
    return envelope(page)


@router.post(
    "",
    response_model=ResponseEnvelope[UserCreateResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create user + send invitation (idempotent re-invite; 409 on active email)",
)
async def create_user_endpoint(
    payload: UserCreateRequest,
    actor: Annotated[
        CurrentUser, Depends(require_permission(Action.CREATE, Resource.USERS))
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
    include_invite_link: Annotated[
        bool,
        Query(
            description=(
                "When true, the response carries the raw invitation URL "
                "(D-43-14). Audited via link_copied=true."
            ),
        ),
    ] = False,
) -> ResponseEnvelope[UserCreateResponse]:
    """USERS-03 / D-43-13 — create user + invite. CREATE permission + CSRF required."""
    result = await service.create_user(session, actor, payload, include_invite_link)
    return envelope(result)


@router.patch(
    "/{user_id}/deactivate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate user (atomic session-revoke; 409 on self / last-owner / already-inactive)",
)
async def deactivate_user_endpoint(
    user_id: UUID,
    actor: Annotated[
        CurrentUser, Depends(require_permission(Action.UPDATE, Resource.USERS))
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """USERS-04 / D-43-16 — self + last-owner guards; UPDATE permission + CSRF required."""
    await service.deactivate_user(session, actor, user_id)
    return None


@router.patch(
    "/{user_id}/reactivate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reactivate a previously-deactivated user (404 missing, 409 if already active)",
)
async def reactivate_user_endpoint(
    user_id: UUID,
    actor: Annotated[
        CurrentUser, Depends(require_permission(Action.UPDATE, Resource.USERS))
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """USERS-04 / D-43-17 — flip back to active; UPDATE permission + CSRF required."""
    await service.reactivate_user(session, actor, user_id)
    return None


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete user (session revoke + invitation cascade; 409 on self / last-owner)",
)
async def soft_delete_user_endpoint(
    user_id: UUID,
    actor: Annotated[
        CurrentUser, Depends(require_permission(Action.DELETE, Resource.USERS))
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """USERS-05 / D-43-18 — soft-delete + session revoke + invitation cascade.

    DELETE permission + CSRF required. `(Action.DELETE, Resource.USERS)` is in
    `OWNER_ONLY`, so reception → 403 from `require_permission`.
    """
    await service.soft_delete_user(session, actor, user_id)
    return None


@router.post(
    "/invitations/{token_id}/revoke",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a pending invitation by token row id (404 missing, 409 already accepted)",
)
async def revoke_invitation_endpoint(
    token_id: UUID,
    payload: InvitationRevokeRequest,
    actor: Annotated[
        CurrentUser, Depends(require_permission(Action.UPDATE, Resource.USERS))
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """USERS-03 / D-43-19 — atomic-consume invitation token by row UUID (NOT raw token)."""
    await service.revoke_invitation(session, actor, token_id, payload.reason)
    return None
