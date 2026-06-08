"""Referral routers — public deep-link resolver + client portal + owner config (Phase 96).

Three APIRouter instances in one file:
  public_router:  GET /api/v1/i/{code}                — NO auth (unauthenticated)
  client_router:  GET /api/v1/client/referral/code   — require_client gate
                  POST /api/v1/client/referral/capture — require_client gate
  owner_router:   GET /api/v1/referral/config         — require_permission(EDIT, GYM)
                  PUT /api/v1/referral/config          — require_permission(EDIT, GYM) + verify_csrf

RBAC-04 ordering: in owner_update_referral_config, require_permission is declared BEFORE
verify_csrf so reception fails at 403 before reaching the CSRF check (T-96-07).

IDOR safety: client_capture_referral takes the referee id from the require_client()
principal — the body carries only {code} (T-96-05 mitigate).

No try/except — AppError subclasses bubble to _app_error_handler in app/main.py.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.dependencies import (
    ClientPrincipal,
    CurrentUser,
    require_client,
    require_permission,
    verify_csrf,
)
from app.core.permissions import Action, Resource
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.referrals import service
from app.modules.referrals.schemas import (
    ReferralCaptureRequest,
    ReferralCodeResponse,
    ReferralConfigResponse,
    ReferralConfigUpdateRequest,
    ReferralResolveResponse,
    ReferralSummaryResponse,
)

# ---------------------------------------------------------------------------
# Public router — unauthenticated deep-link resolver
# ---------------------------------------------------------------------------

public_router = APIRouter(tags=["Referral"])


@public_router.get(
    "/i/{code}",
    response_model=ResponseEnvelope[ReferralResolveResponse],
    operation_id="public_resolve_referral_code",
    summary="Public deep-link resolver — always 200, valid:false for unknown codes (REFER-02)",
)
async def public_resolve_referral_code(
    code: Annotated[str, Path(min_length=1, max_length=16)],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResponseEnvelope[ReferralResolveResponse]:
    """Resolve a referral deep-link code for the PWA landing page.

    No auth gate — unauthenticated callers (T-96-06 PII guard: first name only,
    no client_id, no last name). Unknown code returns valid:false with 200 status
    (anti-enumeration: no 404 oracle for code existence).
    max_length=16 (column width) rather than 8 so 9-16 char strings resolve to
    valid=False rather than 422, avoiding a detectable response-shape difference
    (IN-01 fix).
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.resolve_public_code(session, code, settings)
    return envelope(result)


# ---------------------------------------------------------------------------
# Client router — authenticated client portal
# ---------------------------------------------------------------------------

client_router = APIRouter(tags=["Referral"])


@client_router.get(
    "/referral/code",
    response_model=ResponseEnvelope[ReferralCodeResponse],
    operation_id="client_get_referral_code",
    summary="Get (or mint) the stable referral code for the authenticated client (REFER-01)",
)
async def client_get_referral_code(
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResponseEnvelope[ReferralCodeResponse]:
    """Return the stable referral code + shareUrl for the principal.

    Idempotent: calling this endpoint multiple times always returns the same
    code — a new code is minted only on the first call. No duplicate audit
    event is emitted on idempotent returns (INFRA-15).
    D-20-IDOR: client_id from require_client() principal only.
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.get_or_create_referral_code(session, client.id, settings)
    return envelope(result)


@client_router.get(
    "/referral/summary",
    response_model=ResponseEnvelope[ReferralSummaryResponse],
    operation_id="client_get_referral_summary",
    summary="Aggregate referral summary for the authenticated client (REFER-06; IDOR-safe)",
)
async def client_get_referral_summary(
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResponseEnvelope[ReferralSummaryResponse]:
    """Return code, shareUrl, accruedKopecks, and invitees[] for the principal.

    One round-trip for the PWA ReferralScreen. client_id is sourced from
    require_client() principal only — never a path/query/body param (T-98-02 IDOR-safe).
    accruedKopecks = SUM of own referral_accrual ledger rows (not total balance, T-98-04).
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.get_referral_summary(session, client.id, settings)
    return envelope(result)


@client_router.post(
    "/referral/capture",
    response_model=ResponseEnvelope[None],
    operation_id="client_capture_referral",
    summary="Bind a referrer to the authenticated client via a referral code (REFER-03)",
)
async def client_capture_referral(
    payload: ReferralCaptureRequest,
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[None]:
    """Capture a referral — binds the referrer identified by payload.code to the principal.

    The referee identity comes ONLY from the require_client() principal (client.id),
    never from the request body (T-96-05 IDOR mitigate). payload carries only {code}.

    Idempotent: second call for the same referee is a 200 no-op (first binding wins).
    Self-referral (principal is the referrer of payload.code) → 422 SelfReferralError.
    Unknown code → 404 ReferralCodeNotFoundError.
    No try/except — AppError bubbles to _app_error_handler.
    """
    await service.capture_referral(session, client.id, payload.code)
    return envelope(None)


# ---------------------------------------------------------------------------
# Owner router — admin config read/write (RBAC-04 ordering enforced)
# ---------------------------------------------------------------------------

owner_router = APIRouter(tags=["Referral"])


@owner_router.get(
    "/config",
    response_model=ResponseEnvelope[ReferralConfigResponse],
    operation_id="owner_get_referral_config",
    summary="Owner-only: read referral bonus config (REFER-07)",
)
async def owner_get_referral_config(
    actor: Annotated[CurrentUser, Depends(require_permission(Action.EDIT, Resource.GYM))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ReferralConfigResponse]:
    """Return the singleton referral config (referrerBonusKopecks, refereeWelcomeKopecks).

    Gated by require_permission(EDIT, GYM) — reception → 403.
    Reuses Resource.GYM per planner decision (no new Resource to avoid breaking
    CISO-01 byte-parity guard + parity test). T-96-07.
    No try/except — AppError bubbles to _app_error_handler.
    """
    _ = actor  # permission check only; actor not used in read path
    result = await service.get_referral_config(session)
    return envelope(result)


@owner_router.put(
    "/config",
    response_model=ResponseEnvelope[ReferralConfigResponse],
    operation_id="owner_update_referral_config",
    summary="Owner-only: update referral bonus config (REFER-07)",
)
async def owner_update_referral_config(
    payload: ReferralConfigUpdateRequest,
    # RBAC-04 ordering: require_permission BEFORE verify_csrf — reception fails 403 first
    actor: Annotated[CurrentUser, Depends(require_permission(Action.EDIT, Resource.GYM))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ReferralConfigResponse]:
    """Upsert the singleton referral config.

    RBAC-04: require_permission declared BEFORE verify_csrf → reception fails at 403
    before reaching the CSRF check (T-96-07 mitigate).
    verify_csrf guards against cross-site forgery on the owner mutation.
    ReferralConfigUpdateRequest extra='forbid' → 422 on unknown keys.
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.update_referral_config(session, actor, payload)
    return envelope(result)
