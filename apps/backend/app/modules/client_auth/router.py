"""Client auth router — /otp/request, /otp/verify, /session/refresh, /session/logout, /me.

Phase 68 — isolated client principal (D-08/D-09).

All handlers return ResponseEnvelope[X] per Phase 4 D-14 — no middleware wrapping.

Dependency ordering (RBAC-04 / D-22):
  - /session/logout and PATCH /me declare require_client() FIRST so an unauthenticated
    caller 401s before any CSRF branch fires (401 before 403 invariant).

Public endpoints (no auth dep):
  - POST /otp/request   — pre-auth, always 202 anti-oracle (CAUTH-02)
  - POST /otp/verify    — pre-auth, consumes OTP + issues session cookies

Cookie discipline (D-10):
  - issue_client_session_cookies / clear_client_session_cookies use cc_client_* names
    scoped to /api/v1/client — no collision with staff cc_* on the same origin.

Security decisions implemented:
  T-68-22  — /otp/request always returns 202 ResponseEnvelope[None] (no oracle)
  T-68-23  — PHONE_REGEX validated in schema (422 before any lookup)
  T-68-24  — require_client() decodes via decode_client_token (aud assertion — 401 on staff token)
  T-68-25  — /session/logout + PATCH /me: auth dep before CSRF dep (RBAC-04)
  T-68-27  — /me response is ClientMeResponse (core identity only)
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import ClientPrincipal, require_client, verify_client_csrf
from app.core.exceptions import InvalidAccessToken
from app.core.redis import get_redis
from app.core.schemas import ResponseEnvelope, envelope
from app.core.security import (
    clear_client_session_cookies,
    issue_client_session_cookies,
)
from app.modules.client_auth import service
from app.modules.client_auth.schemas import (
    ClientMePatchRequest,
    ClientMeResponse,
    ClientOtpRequestBody,
    ClientOtpVerifyBody,
)

router = APIRouter(tags=["Client-Portal"])


@router.post(
    "/otp/request",
    response_model=ResponseEnvelope[None],
    status_code=202,
    operation_id="client_otp_request",
)
async def client_otp_request(
    payload: ClientOtpRequestBody,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[None]:
    """Trigger an OTP DM to the client's linked Telegram account (CAUTH-01/02/03).

    Always returns 202 with a fixed ResponseEnvelope[None] body — the response
    is byte-identical for every phone (known/unknown/unlinked) so callers cannot
    infer phone existence (T-68-22 / CAUTH-02 anti-oracle invariant).
    """
    ip = request.client.host if request.client is not None else None
    await service.request_client_otp(session, redis, payload.phone, ip=ip)
    return envelope(None)


@router.post(
    "/otp/verify",
    response_model=ResponseEnvelope[None],
    operation_id="client_otp_verify",
)
async def client_otp_verify(
    payload: ClientOtpVerifyBody,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[None]:
    """Consume a client OTP and issue cc_client_* session cookies (CAUTH-01/04).

    On success, sets three cookies via issue_client_session_cookies:
      cc_client_access   — httpOnly, Path=/
      cc_client_refresh  — httpOnly, Path=/api/v1/client
      clubcore_client_csrf — non-httpOnly, Path=/
    """
    settings = get_settings()
    access, raw_refresh, csrf = await service.verify_client_otp(
        session, redis, payload.phone, payload.code
    )
    issue_client_session_cookies(
        response,
        access_token=access,
        refresh_token=raw_refresh,
        csrf_token=csrf,
        secure=settings.cookie_secure,
    )
    return envelope(None)


@router.post(
    "/session/refresh",
    response_model=ResponseEnvelope[None],
    operation_id="client_session_refresh",
)
async def client_session_refresh(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[None]:
    """Rotate the client refresh token and reissue all three cookies (CAUTH-04).

    Reads cc_client_refresh cookie directly — NOT via the auth dep so an
    expired access token does not block a rotation call. CSRF dep exempt
    (mirrors /auth/refresh D-09 reasoning — identity lives in the cookie).
    """
    settings = get_settings()
    presented = request.cookies.get("cc_client_refresh")
    if presented is None:
        raise InvalidAccessToken("missing_refresh_cookie")
    access, raw_refresh, csrf = await service.rotate_client_refresh(
        session, redis, presented
    )
    issue_client_session_cookies(
        response,
        access_token=access,
        refresh_token=raw_refresh,
        csrf_token=csrf,
        secure=settings.cookie_secure,
    )
    return envelope(None)


@router.post(
    "/session/logout",
    response_model=ResponseEnvelope[None],
    operation_id="client_session_logout",
)
async def client_session_logout(
    request: Request,
    response: Response,
    # RBAC-04 ordering: auth dep FIRST so unauthenticated callers 401 before CSRF 403.
    # FastAPI resolves signature deps in declaration order (T-68-25).
    _client: Annotated[ClientPrincipal, Depends(require_client())],
    _csrf: Annotated[None, Depends(verify_client_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[None]:
    """Revoke the client session family and clear all cc_client_* cookies.

    Idempotent: if cc_client_refresh is absent or already revoked, the cookie
    clear still runs so the browser ends in a clean state.
    """
    settings = get_settings()
    presented = request.cookies.get("cc_client_refresh")
    if presented is not None:
        await service.revoke_client_session(session, redis, presented)
    clear_client_session_cookies(response, secure=settings.cookie_secure)
    return envelope(None)


@router.get(
    "/me",
    response_model=ResponseEnvelope[ClientMeResponse],
    operation_id="client_get_me",
)
async def get_client_me(
    client: Annotated[ClientPrincipal, Depends(require_client())],
) -> ResponseEnvelope[ClientMeResponse]:
    """Return the authenticated client's core identity (D-05, T-68-27).

    No CSRF check — GET is safe (D-09). Response excludes staff-internal fields
    (notes, tags, created_by_user_id, emergency_contact) and all membership data.
    """
    return envelope(ClientMeResponse.model_validate(client, from_attributes=True))


@router.patch(
    "/me",
    response_model=ResponseEnvelope[ClientMeResponse],
    operation_id="client_patch_me",
)
async def patch_client_me(
    payload: ClientMePatchRequest,
    # RBAC-04 ordering: auth dep FIRST (T-68-25).
    client: Annotated[ClientPrincipal, Depends(require_client())],
    _csrf: Annotated[None, Depends(verify_client_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientMeResponse]:
    """Update the authenticated client's email (D-04).

    Returns 409 with code 'email_unavailable' on duplicate email (D-06).
    Non-enumerating: no indication of which account holds the address.
    """
    updated = await service.update_client_me(session, client.id, payload.email)
    return envelope(ClientMeResponse.model_validate(updated, from_attributes=True))
