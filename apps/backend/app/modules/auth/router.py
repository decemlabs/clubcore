"""Auth router — /login, /refresh, /logout, /logout-all, /me (Phase 5 + Phase 6).

Endpoints declare ResponseEnvelope[X] as their response_model per Phase 4 D-14
— no envelope-wrapping middleware. `/login` and `/refresh` are CSRF-exempt at
the server level (Phase 6 D-09: identity is in the body / cc_refresh cookie).

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

Phase 109 wiring (PROF-01 / PROF-02):
  - `PATCH /me` — authenticated + CSRF-gated; partial profile update (full_name,
    email); returns MeResponse echo.  Duplicate email → 409 field error (D-109-01).
  - `POST /change-password` — authenticated + CSRF-gated; Argon2id re-hash;
    revokes OTHER sessions while keeping current alive (T-109-10); returns 204.
    Both declare auth dep FIRST then verify_csrf to preserve RBAC-04 (401 before 403).
"""

import hashlib
from typing import Annotated, cast
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_authenticated, verify_csrf
from app.core.exceptions import InvalidAccessToken, NotFoundError, ValidationAppError
from app.core.pagination import PageQuery, PaginatedData
from app.core.redis import get_redis
from app.core.schemas import ResponseEnvelope, envelope
from app.core.security import (
    clear_session_cookies,
    issue_session_cookies,
)
from app.modules.auth import password_reset_service, telegram_service
from app.modules.auth.exceptions import BotNotStarted
from app.modules.auth.models import RefreshToken, User
from app.modules.auth.schemas import (
    ActiveSessionItem,
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    MeResponse,
    OtpRequestBody,
    PasswordResetConfirmBody,
    PasswordResetRequestBody,
    ProfileUpdateRequest,
    TelegramStartResponse,
    TelegramStatusResponse,
    TelegramVerifyRequest,
    UserPublic,
)
from app.modules.auth.service import (
    authenticate,
    change_password,
    issue_tokens,
    list_user_sessions,
    request_otp_email,
    request_otp_telegram,
    revoke_all_sessions,
    revoke_family,
    revoke_session,
    rotate_refresh,
    update_profile,
)

_log = structlog.get_logger(__name__)

router = APIRouter(tags=["Auth"])


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

    Reads `cc_refresh` cookie directly (NOT via the auth dep — an expired
    access token must NOT block a refresh call). The body is empty on
    success: the new tokens travel in cookies. CSRF dep is exempt (Phase 6
    CSRF-02 / D-09 list).
    """
    settings = get_settings()
    presented = request.cookies.get("cc_refresh")
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
    presented = request.cookies.get("cc_refresh")
    if presented is not None:
        await revoke_session(session, redis, presented)
    clear_session_cookies(response, secure=settings.cookie_secure)
    return envelope(None)


@router.get(
    "/sessions",
    response_model=ResponseEnvelope[PaginatedData[ActiveSessionItem]],
    summary="List the current user's active session families",
)
async def list_sessions(
    request: Request,
    user: Annotated[CurrentUser, Depends(require_authenticated())],
    query: Annotated[PageQuery, Depends()],
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[PaginatedData[ActiveSessionItem]]:
    """Return the authenticated user's active session families (HYG-03, D-23-1..D-23-4).

    GET is CSRF-exempt (Phase 6 D-09). No RBAC check — every authenticated user
    manages their own sessions. is_current resolved server-side via sha256(cc_refresh)
    token_hash lookup (D-23-3).
    """
    presented = request.cookies.get("cc_refresh")
    data = await list_user_sessions(
        session,
        redis,
        user_id=user.id,
        page=query.page,
        page_size=query.page_size,
        presented_refresh_token=presented,
    )
    return envelope(data)


@router.post(
    "/sessions/{family_id}/revoke",
    response_model=ResponseEnvelope[None],
    summary="Revoke a single session family (idempotent)",
)
async def revoke_session_family(
    family_id: UUID,
    request: Request,
    response: Response,
    # RBAC-04 ordering: auth dep FIRST so unauthenticated callers get 401 before 403.
    user: Annotated[CurrentUser, Depends(require_authenticated())],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[None]:
    """Revoke a single session family (CSRF-gated, HYG-03, D-23-5..D-23-10).

    - 404-collapse on unknown family OR family belonging to another user (D-23-6).
    - Idempotent: already-revoked family returns 200 (D-23-7).
    - Self-revoke: if the revoked family matches THIS request's cc_refresh family,
      clear the cookie matrix identical to /logout (D-23-8).
    - Audit: session_revoked with resource_type='auth_session' (D-23-10).
    """
    result = await revoke_family(
        session,
        redis,
        user_id=user.id,
        family_id=family_id,
    )
    if result == "not_found":
        raise NotFoundError("not_found")

    # Self-revoke detection (D-23-8): if the revoked family_id matches the family bound
    # to THIS request's cc_refresh, clear the cookie matrix (same as /logout).
    presented = request.cookies.get("cc_refresh")
    if presented is not None and result == "revoked":
        presented_hash = hashlib.sha256(presented.encode("utf-8")).hexdigest()
        current_row = await session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == presented_hash)
        )
        if current_row is not None and current_row.family_id == family_id:
            settings = get_settings()
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


# ---------------------------------------------------------------------------
# Phase 109 — Profile edit (PROF-01) + self password-change (PROF-02).
#
# Both endpoints are SELF-SERVICE (no Resource permission check — every
# authenticated staff member can update their own profile / change their own
# password).  Auth dep FIRST, verify_csrf SECOND → RBAC-04 (401 before 403)
# preserved identical to /logout and /sessions/{id}/revoke (D-22).
# ---------------------------------------------------------------------------


@router.patch("/me", response_model=ResponseEnvelope[MeResponse])
async def update_me(
    payload: ProfileUpdateRequest,
    # RBAC-04 ordering: auth FIRST so unauthenticated callers get 401 before 403.
    user: Annotated[CurrentUser, Depends(require_authenticated())],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[MeResponse]:
    """Partially update the authenticated user's own profile (PROF-01).

    Accepts an optional subset of {full_name, email}; at least one field must
    be non-None (all-None body → 422, client bug).  Duplicate email → 409 with
    fields.email (D-109-01-CONFLICT).  Returns the updated MeResponse echo.

    CSRF-gated (T-109-07); auth required (T-109-08).
    """
    if payload.full_name is None and payload.email is None:
        raise ValidationAppError(
            "at_least_one_field_required",
            fields={"_": "Provide full_name or email"},
        )

    updated_user = await update_profile(
        session,
        user_id=user.id,
        full_name=payload.full_name,
        email=payload.email,
    )
    return envelope(
        MeResponse(
            id=updated_user.id,
            role=updated_user.role,
            full_name=updated_user.full_name,
            email=updated_user.email,
            has_telegram=updated_user.telegram_chat_id is not None,
        )
    )


@router.post(
    "/change-password",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def change_password_endpoint(
    payload: ChangePasswordRequest,
    request: Request,
    # RBAC-04 ordering: auth FIRST so unauthenticated callers get 401 before 403.
    user: Annotated[CurrentUser, Depends(require_authenticated())],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> None:
    """Self-service password change (PROF-02).

    Verifies the current password, rehashes with Argon2id, revokes all OTHER
    session families (T-109-10 — current device stays logged in), and returns
    204 No Content.  Wrong current password → 401 invalid_credentials
    (InvalidPassword handler).

    Resolves the current refresh-token family from the cc_refresh cookie so
    that the calling device's session is excluded from revocation.  If the
    cookie is absent or unresolvable, current_family_id falls back to a nil
    UUID (revoke-all fallback — extremely unlikely while access token was valid).

    CSRF-gated (T-109-07); auth required (T-109-08).
    """
    # Resolve current family_id from the cc_refresh cookie (reuses the
    # sha256 → token_hash → RefreshToken.family_id lookup from
    # revoke_session_family lines 217-223).
    current_family_id: UUID | None = None
    presented = request.cookies.get("cc_refresh")
    if presented is not None:
        presented_hash = hashlib.sha256(presented.encode("utf-8")).hexdigest()
        current_row = await session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == presented_hash)
        )
        if current_row is not None:
            current_family_id = current_row.family_id

    # If resolution failed (no cc_refresh cookie or hash not found in DB),
    # use a nil UUID — this means no family is excluded and all alive sessions
    # are revoked.  The authenticated access-cookie was valid so this is an
    # extremely rare edge case (cookie cleared mid-request, etc.).
    # WR-01: emit a structured warning so operators can observe the degraded path.
    # When the fallback fires the caller's session will also be revoked (all
    # families are hit by the nil-UUID exclusion predicate), so this is logged
    # at WARNING level for operational visibility.
    if current_family_id is None:
        _log.warning(
            "change_password.family_id_unresolved",
            user_id=str(user.id),
            note=(
                "cc_refresh cookie absent or hash not found in DB; "
                "nil-UUID fallback: ALL sessions (including caller's) will be revoked"
            ),
        )
    effective_family_id: UUID = (
        current_family_id if current_family_id is not None else UUID(int=0)
    )

    await change_password(
        session,
        redis,
        user_id=user.id,
        current_password=payload.current_password,
        new_password=payload.new_password,
        current_family_id=effective_family_id,
    )
    # 204 No Content — no response body.


# ---------------------------------------------------------------------------
# Phase 7 — Telegram OTP channel (AUTH-TG-01, AUTH-TG-03, AUTH-TG-04, AUTH-TG-06).
#
# All three endpoints are UNAUTHENTICATED. Per Phase 6 D-04 + D-09 they are
# pre-listed in the TEST-07 introspection exclusion AND carry NO verify_csrf
# (identity is in the body, not in cookies).
# ---------------------------------------------------------------------------


def _build_deep_link_url(token: str) -> str:
    """Compose the canonical t.me deep-link URL for a raw deep-link token."""
    settings = get_settings()
    return f"https://t.me/{settings.telegram_bot_username}?start={token}"


@router.post(
    "/telegram/start",
    response_model=ResponseEnvelope[TelegramStartResponse],
)
async def telegram_start(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[TelegramStartResponse]:
    """Mint a deep-link token (AUTH-TG-01).

    Returns the deep-link URL the FE shows to the operator. The OtpCode row
    is created with code_hash=NULL — the bot will fill it after /start <token>.
    """
    raw_token, _hash = await telegram_service.start_deep_link(session)
    return envelope(
        TelegramStartResponse(
            deep_link_url=_build_deep_link_url(raw_token),
            deep_link_token=raw_token,
        )
    )


@router.get(
    "/telegram/status",
    response_model=ResponseEnvelope[TelegramStatusResponse],
)
async def telegram_status(
    token: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[TelegramStatusResponse]:
    """Poll: has the bot DMed the code yet? (AUTH-TG-03).

    Per D-19: never raises; unknown / expired / consumed all return bound=False
    (do NOT leak token validity).
    """
    bound = await telegram_service.get_status(session, token)
    return envelope(TelegramStatusResponse(bound=bound))


@router.post(
    "/telegram/verify",
    response_model=ResponseEnvelope[LoginResponse],
)
async def telegram_verify(
    payload: TelegramVerifyRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[LoginResponse]:
    """Verify the 6-digit OTP and issue session cookies (AUTH-TG-04, AUTH-TG-06).

    On success: mints tokens + cookies identical to /login, then emits
    `login_success` with `channel='telegram'` (D-14). Distinct error codes
    per D-13 ride the AppError envelope handler. BotNotStarted is re-raised
    with `fields={'deepLinkUrl': ...}` so the FE can re-display the deep-link
    button (D-13 row 1).
    """
    settings = get_settings()
    try:
        user = await telegram_service.consume(session, payload.deep_link_token, payload.code)
    except BotNotStarted as exc:
        raise BotNotStarted(
            exc.message,
            fields={"deepLinkUrl": _build_deep_link_url(payload.deep_link_token)},
        ) from exc

    access, refresh, csrf = await issue_tokens(session, redis, user)
    issue_session_cookies(
        response,
        access_token=access,
        refresh_token=refresh,
        csrf_token=csrf,
        secure=settings.cookie_secure,
    )
    ip = request.client.host if request.client is not None else None
    await audit.emit(
        session,
        "login_success",
        actor_user_id=user.id,
        resource_type="session",
        resource_id=None,
        ip=ip,
        channel="telegram",
    )
    return envelope(LoginResponse(user=UserPublic.model_validate(user)))


# ---------------------------------------------------------------------------
# Phase 42 — Unified OTP request entry (AUTH-EM-02 / D-42-22).
#
# Returns 202 with IDENTICAL envelope shape across BOTH branches (telegram
# facade + email) and across all sub-cases (known/unknown/unverified/cooldown)
# so the response shape cannot be used as an oracle. UNAUTHENTICATED. The
# existing POST /auth/telegram/start endpoint remains in place for any FE
# callers that need the deep-link URL directly — this endpoint is the new
# unified surface that hides the channel discrimination behind a single
# shape.
# ---------------------------------------------------------------------------


@router.post(
    "/otp/request",
    response_model=ResponseEnvelope[None],
    status_code=202,
)
async def otp_request(
    payload: OtpRequestBody,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[None]:
    """Request an OTP via the configured channel (AUTH-EM-02 / D-42-22).

    Always returns 202 with IDENTICAL body shape regardless of channel,
    success/silent-drop branch, or known/unknown user. The Pydantic body
    validator enforces ``email`` presence when ``channel='email'`` (returns
    422 BEFORE the route fires — not an anti-oracle leak because invalid
    body SHAPE is not a success-vs-unknown discriminator).
    """
    ip = request.client.host if request.client is not None else None
    if payload.channel == "email":
        assert payload.email is not None  # narrowed by model_validator
        await request_otp_email(session, redis, payload.email, ip=ip)
    else:
        # channel='telegram' (default) — delegates to the new
        # service.request_otp_telegram facade which itself delegates to
        # the existing telegram_service.start_deep_link. Both branches
        # return the same envelope; the deep-link URL is suppressed here
        # (clients that need it continue using /auth/telegram/start).
        await request_otp_telegram(session, redis, ip=ip)
    return envelope(None)


# ---------------------------------------------------------------------------
# Phase 44 — Password reset request/confirm anonymous endpoints
# (RESET-01 / RESET-02 / D-44-34).
#
# Both endpoints are UNAUTHENTICATED — no `require_authenticated`, no
# `verify_csrf`, no `require_permission` (D-44-34). The router is a thin
# delegate: all anti-oracle / atomic-consume / audit / rate-limit policy
# lives in `password_reset_service`.
# ---------------------------------------------------------------------------


@router.post(
    "/password-reset/request",
    response_model=ResponseEnvelope[None],
    status_code=202,
    summary="Request a password-reset email (anti-oracle, rate-limited)",
)
async def password_reset_request_endpoint(
    body: PasswordResetRequestBody,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[None]:
    """RESET-01 anonymous endpoint.

    No CSRF, no RBAC (D-44-34). Anti-oracle: response is byte-identical
    across all 4 cases (active / deactivated / owner / nonexistent) AND
    across the rate-limit-hit branch. 500ms wall-clock floor + audit emit
    in BOTH known/unknown branches live entirely inside the service layer.
    """
    # D-44-12 — X-Forwarded-For first hop, fall back to request.client.host.
    # "0.0.0.0" is a final fallback when ASGI provides no client (test transport
    # without explicit client) — it is a sentinel string, never bound to a port.
    xff = request.headers.get("x-forwarded-for")
    client_ip = (
        xff.split(",")[0].strip() if xff else (request.client.host if request.client else "0.0.0.0")  # noqa: S104
    )
    await password_reset_service.request_password_reset(
        session, redis, email=body.email, client_ip=client_ip
    )
    return envelope(None)


@router.post(
    "/password-reset/confirm",
    response_model=ResponseEnvelope[None],
    status_code=200,
    summary="Confirm password reset (atomic-consume + revoke-all)",
)
async def password_reset_confirm_endpoint(
    body: PasswordResetConfirmBody,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[None]:
    """RESET-02 anonymous endpoint.

    No CSRF, no RBAC (D-44-34). Atomic-consume + Argon2 rehash +
    revoke-all sessions + audit emit live in the service layer.
    Returns 200 envelope(None) on success; 410 invalid_or_expired_token /
    422 weak_password on failure (translated by the global AppError handler).
    """
    await password_reset_service.confirm_password_reset(
        session, raw_token=body.token, new_password=body.new_password
    )
    return envelope(None)
