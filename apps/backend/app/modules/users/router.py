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

from fastapi import APIRouter, Depends, Query, Response, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission, verify_csrf
from app.core.pagination import PaginatedData
from app.core.permissions import Action, Resource
from app.core.redis import get_redis
from app.core.schemas import ResponseEnvelope, envelope
from app.core.security import issue_session_cookies
from app.modules.auth import password_reset_service
from app.modules.auth.models import User
from app.modules.auth.schemas import LoginResponse, UserPublic
from app.modules.auth.service import issue_tokens
from app.modules.users import service
from app.modules.users.schemas import (
    InvitationAcceptRequest,
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


# ---------------------------------------------------------------------------
# Phase 44 — Invitation accept anonymous endpoint
# (RESET-04 / D-44-18 / D-44-21 / D-44-34).
#
# UNAUTHENTICATED — no require_authenticated, no verify_csrf, no
# require_permission (D-44-34). Cross-module delegate into auth bedrock:
#   - password_reset_service.accept_invitation   — atomic-consume + UPDATE
#   - auth.service.issue_tokens                  — (access, refresh, csrf)
#   - core.security.issue_session_cookies        — Set-Cookie matrix
# The endpoint mirrors /auth/login VERBATIM (auth/router.py:72-92): same
# call order, same kwargs (access_token=/refresh_token=/csrf_token=/secure=),
# same LoginResponse(user=UserPublic.model_validate(user)) construction,
# and no explicit session.commit() between issue_tokens and the cookie
# write (the inner accept_invitation owns its own commit per SVC001).
# ---------------------------------------------------------------------------


@router.post(
    "/invitations/accept",
    response_model=ResponseEnvelope[LoginResponse],
    status_code=status.HTTP_200_OK,
    summary="Accept a pending invitation: set password + log in (RESET-04)",
)
async def accept_invitation_endpoint(
    body: InvitationAcceptRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[LoginResponse]:
    """RESET-04 anonymous endpoint.

    No CSRF, no RBAC (D-44-34). Cross-module delegate to
    ``auth.password_reset_service.accept_invitation`` (D-44-18 — atomic
    consume + UPDATE-only password set lives in auth bedrock). On
    success, issues session cookies via the SAME verbatim sequence
    /auth/login uses (see auth/router.py:72-92).

    Canonical ordering — DO NOT deviate:
      1. service.accept_invitation owns its own commit (SVC001).
      2. Re-load User row by id for UserPublic.model_validate.
      3. issue_tokens(session, redis, user) — 3-tuple (access, refresh, csrf).
      4. issue_session_cookies(response, access_token=, refresh_token=,
         csrf_token=, secure=) — kwargs match /auth/login verbatim.
      5. NO explicit session.commit() between (3) and (4) — mirrors /auth/login.
      6. envelope(LoginResponse(user=UserPublic.model_validate(user))).
    """
    settings = get_settings()

    # Step 1: delegate to service (owns its own commit per SVC001).
    # The 3 extra primitives in the tuple (email/role/full_name) are
    # unused at LoginResponse construction time — UserPublic.model_validate
    # reads them from the re-loaded ORM row in step 2. They remain in the
    # service return shape for parity with future call sites + audit-replay
    # debugging.
    user_id, _email, _role, _full_name = await password_reset_service.accept_invitation(
        session,
        raw_token=body.token,
        new_password=body.password,
        full_name=body.full_name,
    )

    # Step 2: re-load the User row for UserPublic.model_validate.
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one()

    # Step 3: mint tokens — 3-tuple (access, refresh, csrf). Mirrors
    # /auth/login at apps/backend/app/modules/auth/router.py:84.
    access, refresh, csrf = await issue_tokens(session, redis, user)

    # Step 4: write cookies. Kwargs are access_token=/refresh_token=/
    # csrf_token=/secure=, NOT access=/refresh=. Mirrors /auth/login at
    # apps/backend/app/modules/auth/router.py:85-91.
    issue_session_cookies(
        response,
        access_token=access,
        refresh_token=refresh,
        csrf_token=csrf,
        secure=settings.cookie_secure,
    )

    # Step 5: NO explicit session.commit() between issue_tokens and
    # issue_session_cookies. /auth/login does not commit between them;
    # the request-scoped session dependency handles the implicit final
    # flush at request teardown. Mirroring this avoids drift across the
    # two cookie-issuing sites (RESET-04 and AUTH-EP-01).

    # Step 6: envelope shape — LoginResponse wraps a UserPublic
    # (matches /auth/login at apps/backend/app/modules/auth/router.py:92).
    return envelope(LoginResponse(user=UserPublic.model_validate(user)))
