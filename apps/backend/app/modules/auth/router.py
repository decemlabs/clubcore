"""Auth router — /login, /refresh, /logout, /logout-all, /me (Phase 5 + Phase 6).

Endpoints declare ResponseEnvelope[X] as their response_model per Phase 4 D-14
— no envelope-wrapping middleware. `/login` and `/refresh` are CSRF-exempt at
the server level (Phase 6 D-09: identity is in the body / sz_refresh cookie).

Phase 6 wiring (D-02, D-09):
  - `/me`, `/logout`, `/logout-all` declare the `require_authenticated()`
    factory dep (the bare core-level identity loader is banned for
    protected routes per D-03; the introspection test fails the build
    if it appears).
  - `/logout` and `/logout-all` declare `verify_csrf` as a SIGNATURE dep
    AFTER the auth dep so the RBAC-04 invariant (401 before 403) is
    preserved — FastAPI resolves signature deps in declaration order.
  - `/me` does NOT declare `verify_csrf` (GET — would short-circuit anyway).

`require_permission` is NOT used here — Phase 6 wires it onto every other
business route (RBAC-02..05). Auth endpoints don't need RBAC because login
grants the role; logout/me are role-agnostic.
"""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_authenticated, verify_csrf
from app.core.exceptions import InvalidAccessToken
from app.core.redis import get_redis
from app.core.schemas import ResponseEnvelope, envelope
from app.core.security import (
    clear_session_cookies,
    issue_session_cookies,
)
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    UserPublic,
)
from app.modules.auth.service import (
    authenticate,
    issue_tokens,
    revoke_all_sessions,
    revoke_session,
    rotate_refresh,
)

router = APIRouter()


@router.post("/login", response_model=ResponseEnvelope[LoginResponse])
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[LoginResponse]:
    """Authenticate email+password; issue cookies + envelope (AUTH-EP-01..02, AUTH-EP-05)."""
    settings = get_settings()
    ip = request.client.host if request.client is not None else None
    user = await authenticate(session, redis, payload.email, payload.password, ip=ip)
    access, refresh, csrf = await issue_tokens(session, redis, user)
    issue_session_cookies(
        response,
        access_token=access,
        refresh_token=refresh,
        csrf_token=csrf,
        secure=settings.cookie_secure,
    )
    return envelope(LoginResponse(user=UserPublic.model_validate(user)))


@router.post("/refresh", response_model=ResponseEnvelope[None])
async def refresh(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[None]:
    """Rotate the refresh token; reissue all three cookies (AUTH-05/06).

    Reads `sz_refresh` cookie directly (NOT via the auth dep — an expired
    access token must NOT block a refresh call). The body is empty on
    success: the new tokens travel in cookies. CSRF dep is exempt (Phase 6
    CSRF-02 / D-09 list).
    """
    settings = get_settings()
    presented = request.cookies.get("sz_refresh")
    if presented is None:
        raise InvalidAccessToken("missing_refresh_cookie")

    access, refresh_token, csrf = await rotate_refresh(session, redis, presented)
    issue_session_cookies(
        response,
        access_token=access,
        refresh_token=refresh_token,
        csrf_token=csrf,
        secure=settings.cookie_secure,
    )
    return envelope(None)


@router.post("/logout", response_model=ResponseEnvelope[None])
async def logout(
    request: Request,
    response: Response,
    # CurrentUser ensures the access cookie is valid; otherwise 401 short-circuits.
    # verify_csrf is a SIGNATURE dep AFTER require_authenticated so RBAC-04 (D-22)
    # is preserved: unauth caller → 401 invalid_token (auth fires first), not 403
    # csrf_mismatch. FastAPI resolves signature deps in declaration order.
    _user: Annotated[CurrentUser, Depends(require_authenticated())],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[None]:
    """Revoke current family + clear cookies (AUTH-LO-01).

    Idempotent: if the refresh cookie is absent or already revoked, the cookie
    clear still runs so the browser ends in a clean state.
    """
    settings = get_settings()
    presented = request.cookies.get("sz_refresh")
    if presented is not None:
        await revoke_session(session, redis, presented)
    clear_session_cookies(response, secure=settings.cookie_secure)
    return envelope(None)


@router.post("/logout-all", response_model=ResponseEnvelope[None])
async def logout_all(
    response: Response,
    user: Annotated[CurrentUser, Depends(require_authenticated())],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[None]:
    """Revoke ALL alive families for the user + clear caller's cookies (AUTH-LO-02)."""
    settings = get_settings()
    await revoke_all_sessions(session, redis, user.id)
    clear_session_cookies(response, secure=settings.cookie_secure)
    return envelope(None)


@router.get("/me", response_model=ResponseEnvelope[MeResponse])
async def me(
    user: Annotated[CurrentUser, Depends(require_authenticated())],
) -> ResponseEnvelope[MeResponse]:
    """Return the authenticated user's profile (AUTH-LO-04).

    `CurrentUser` is a Protocol with `id` + `role` only. The route knows the
    runtime instance is the SA `User` model (registered via register_user_loader
    in app.main.create_app), so we cast for access to email / full_name /
    telegram_chat_id. The cast is safe because the loader is fixed at composition.
    """
    u = cast(User, user)
    return envelope(
        MeResponse(
            id=u.id,
            role=u.role,
            full_name=u.full_name,
            email=u.email,
            has_telegram=u.telegram_chat_id is not None,
        )
    )
