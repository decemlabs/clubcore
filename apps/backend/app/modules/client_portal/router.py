"""Client-portal router — read + write endpoints for authenticated clients (Phase 69/70).

Phase 69 CHOME-01..03, CHIST-01..03, CPLAN-01..03.
Phase 70 CBOOK-02..05 — client booking POST (idempotent), cancel, and slots-read.
Phase 70 CCHK-01..03 — QR token issuance + token-as-credential self check-in.

All handlers gated via Depends(require_client()) EXCEPT POST /check-in, which is a
token-as-credential endpoint (the signed QR token is the sole credential — D-70-11).

No CSRF dep on GET endpoints (safe methods). POST/DELETE endpoints add
Depends(verify_client_csrf) after require_client() per RBAC-04 ordering.
Booking POST additionally adds Depends(verify_client_idempotency) per D-70-02.

Rate-limiting (T-70-18 / CCHK-03):
  Both /client/qr-token (authenticated) and /client/check-in (unauthenticated) carry
  a per-IP Redis fixed-window rate limit (20 req/min for qr-token; 60 req/min for
  check-in to accommodate multi-scanner gyms) using the INCR+EXPIRE pattern from
  app/modules/auth/reset_rate_limit.py. RateLimited(429) bubbles to _app_error_handler.
  Decision rationale: /check-in is unauthenticated — without this control it invites
  brute-force QR token scanning floods. /qr-token is authenticated (require_client)
  but a compromised session could spam token minting; the 20 req/min window is well
  above legitimate use (a client refreshes once every ~50s).

D-69-03: Empty states are 200 with null/[] — never 404 for own scope.
D-20-IDOR: Every owned resource read has mandatory client_id filter in repo layer.
D-20-OPENAPI: Client-Portal tag; client_ operationId prefix.
D-20-MODULE: Write delegates via Protocol slots only — no app.modules.bookings/visits import.
"""

from __future__ import annotations

import json
from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import ClientPrincipal, require_client, verify_client_csrf
from app.core.exceptions import RateLimited
from app.core.idempotency import idempotent_execute, verify_client_idempotency
from app.core.pagination import PageQuery, PaginatedData
from app.core.redis import get_redis
from app.core.schemas import ResponseEnvelope, envelope
from app.integrations.yookassa.settings import YooKassaSettings, get_yookassa_settings
from app.modules.client_portal import service
from app.modules.client_portal.schemas import (
    ClientAvailableSlotItem,
    ClientBookingResponse,
    ClientCatalogPlanResponse,
    ClientCatalogPtPackageResponse,
    ClientCatalogTrainerResponse,
    ClientCheckInRequest,
    ClientCheckInResponse,
    ClientCheckoutRequest,
    ClientCheckoutResponse,
    ClientCreateBookingRequest,
    ClientHomeResponse,
    ClientMembershipResponse,
    ClientNextBookingResponse,
    ClientPaymentItem,
    ClientPaymentStatusResponse,
    ClientPtSessionItem,
    ClientQrTokenResponse,
    ClientVisitItem,
)

# ---------------------------------------------------------------------------
# Rate-limit constants for QR endpoints (T-70-18 — D-70-11 abuse control)
# ---------------------------------------------------------------------------

_QR_TOKEN_IP_LIMIT: Final[int] = 20  # req/min (authenticated; high legitimacy threshold)
_QR_TOKEN_IP_WINDOW: Final[int] = 60  # seconds
_CHECK_IN_IP_LIMIT: Final[int] = 60  # req/min (unauthenticated; gym may have multiple scanners)
_CHECK_IN_IP_WINDOW: Final[int] = 60  # seconds


def _qr_token_rate_key(ip: str) -> str:
    return f"ratelimit:qr_token:ip:{ip}"


def _check_in_rate_key(ip: str) -> str:
    return f"ratelimit:check_in:ip:{ip}"


async def _enforce_qr_token_rate_limit(redis: Redis, ip: str) -> None:
    """Per-IP fixed-window rate limit for GET /client/qr-token (T-70-18).

    20 req/min per IP. Legitimate clients refresh once every ~50s; threshold
    is well above normal use. Atomic INCR-first pattern: INCR returns the new
    value atomically; EXPIRE with nx=True only sets the TTL on the first
    increment so the window is anchored to the first request, not reset on
    each one. This eliminates the TOCTOU race in the old GET-then-INCR pattern.
    """
    key = _qr_token_rate_key(ip)
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, _QR_TOKEN_IP_WINDOW, nx=True)
    results = await pipe.execute()
    count = results[0]
    if count > _QR_TOKEN_IP_LIMIT:
        raise RateLimited("rate_limited")


async def _enforce_check_in_rate_limit(redis: Redis, ip: str) -> None:
    """Per-IP fixed-window rate limit for POST /client/check-in (T-70-18).

    60 req/min per IP. Accommodates multi-scanner gym reception desks while
    bounding brute-force QR token flood attacks on the unauthenticated endpoint.
    Atomic INCR-first pattern: INCR returns the new value atomically; EXPIRE
    with nx=True only sets the TTL on the first increment so the window is
    anchored to the first request, not reset on each one. This eliminates the
    TOCTOU race in the old GET-then-INCR pattern.
    """
    key = _check_in_rate_key(ip)
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, _CHECK_IN_IP_WINDOW, nx=True)
    results = await pipe.execute()
    count = results[0]
    if count > _CHECK_IN_IP_LIMIT:
        raise RateLimited("rate_limited")

router = APIRouter(tags=["Client-Portal"])


# ---------------------------------------------------------------------------
# Home & Membership (CHOME-01..03)
# ---------------------------------------------------------------------------


@router.get(
    "/membership",
    response_model=ResponseEnvelope[ClientMembershipResponse | None],
    operation_id="client_get_membership",
    summary="Active membership for the authenticated client (CHOME-01/03; 200 null if none)",
)
async def client_get_membership(
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientMembershipResponse | None]:
    """Return active membership with server-derived days_until_end + expiring_soon (D-69-02).

    D-69-03: no active membership → 200 with null, not 404.
    D-20-IDOR: client_id injected from cookie principal, not URL param.
    No CSRF dep — GET is safe.
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.get_client_membership(session, client.id)
    return envelope(result)


@router.get(
    "/home",
    response_model=ResponseEnvelope[ClientHomeResponse],
    operation_id="client_get_home",
    summary="Home screen composite: membership + nextBooking + expiringSoon (CHOME-01..03)",
)
async def client_get_home(
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientHomeResponse]:
    """Server-side fan-out: reuses the same query functions as the granular endpoints.

    Null slots for missing data (D-69-03).
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.get_client_home(session, client.id)
    return envelope(result)


@router.get(
    "/bookings",
    response_model=ResponseEnvelope[PaginatedData[ClientNextBookingResponse]],
    operation_id="client_list_bookings",
    summary="Upcoming bookings for the authenticated client (CHOME-02, granular reuse D-69-01)",
)
async def client_list_bookings(
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
    query: Annotated[PageQuery, Depends()],
) -> ResponseEnvelope[PaginatedData[ClientNextBookingResponse]]:
    """Granular upcoming-bookings endpoint — reused by the future Book screen (D-69-01).

    /home consumes the next booking internally via the same service function.
    No try/except — AppError bubbles to _app_error_handler.
    """
    # For Phase 69: expose the single next booking in paginated form.
    # Full paginated booking list is Phase 70 scope (CBOOK-01).
    single = await service._get_client_next_booking(session, client.id)
    items = [single] if single is not None else []
    page = PaginatedData(
        items=items,
        total=len(items),
        page=query.page,
        page_size=query.page_size,
    )
    return envelope(page)


# ---------------------------------------------------------------------------
# History (CHIST-01..03)
# ---------------------------------------------------------------------------


@router.get(
    "/history/visits",
    response_model=ResponseEnvelope[PaginatedData[ClientVisitItem]],
    operation_id="client_list_visit_history",
    summary="Paginated visit history for the authenticated client (CHIST-01)",
)
async def client_list_visit_history(
    query: Annotated[PageQuery, Depends()],
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[ClientVisitItem]]:
    """CHIST-01 — own visit history, IDOR-safe via mandatory client_id repo filter.

    No try/except — AppError bubbles to _app_error_handler.
    """
    page = await service.list_client_visits(session, client.id, query)
    return envelope(page)


@router.get(
    "/history/pt-sessions",
    response_model=ResponseEnvelope[PaginatedData[ClientPtSessionItem]],
    operation_id="client_list_pt_session_history",
    summary="Paginated PT-session history for the authenticated client (CHIST-02)",
)
async def client_list_pt_session_history(
    query: Annotated[PageQuery, Depends()],
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[ClientPtSessionItem]]:
    """CHIST-02 — PT-session history ownership resolved via pt_packages.client_id JOIN.

    No try/except — AppError bubbles to _app_error_handler.
    """
    page = await service.list_client_pt_sessions(session, client.id, query)
    return envelope(page)


@router.get(
    "/history/payments",
    response_model=ResponseEnvelope[PaginatedData[ClientPaymentItem]],
    operation_id="client_list_payment_history",
    summary="Paginated payment + refund history for the authenticated client (CHIST-03)",
)
async def client_list_payment_history(
    query: Annotated[PageQuery, Depends()],
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[ClientPaymentItem]]:
    """CHIST-03 — payment + refund history (signed-amount ledger). IDOR-safe.

    No try/except — AppError bubbles to _app_error_handler.
    """
    page = await service.list_client_payments(session, client.id, query)
    return envelope(page)


# ---------------------------------------------------------------------------
# Catalogs (CPLAN-01..03) — authed clients only, but non-owned reads
# ---------------------------------------------------------------------------


@router.get(
    "/plans",
    response_model=ResponseEnvelope[list[ClientCatalogPlanResponse]],
    operation_id="client_list_plans",
    summary="Active membership plans catalog for the authenticated client (CPLAN-01)",
)
async def client_list_plans(
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[list[ClientCatalogPlanResponse]]:
    """CPLAN-01 — client-safe membership plans (no freeze_days_limit, no audit fields).

    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.list_membership_plans(session)
    return envelope(result)


@router.get(
    "/pt-packages",
    response_model=ResponseEnvelope[list[ClientCatalogPtPackageResponse]],
    operation_id="client_list_pt_packages",
    summary="Active PT-package plans catalog for the authenticated client (CPLAN-02)",
)
async def client_list_pt_packages(
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[list[ClientCatalogPtPackageResponse]]:
    """CPLAN-02 — client-safe PT-package plans (no rate internals, no audit fields).

    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.list_pt_packages(session)
    return envelope(result)


@router.get(
    "/trainers",
    response_model=ResponseEnvelope[list[ClientCatalogTrainerResponse]],
    operation_id="client_list_trainers",
    summary="Active trainers catalog for the authenticated client (CPLAN-03)",
)
async def client_list_trainers(
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[list[ClientCatalogTrainerResponse]]:
    """CPLAN-03 — client-safe trainer catalog (name only; no phone, no is_active, no rates).

    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.list_trainers(session)
    return envelope(result)


# ---------------------------------------------------------------------------
# Phase 70 CBOOK-02..05 — booking write + cancel + available-slots
# ---------------------------------------------------------------------------


@router.post(
    "/booking",
    response_model=ResponseEnvelope[ClientBookingResponse],
    status_code=status.HTTP_201_CREATED,
    operation_id="client_create_booking",
    summary=(
        "Create a confirmed booking for the authenticated client (CBOOK-03/04; "
        "201 on success; 422 no_active_pt_package if no active PT-package; "
        "409 slot_already_booked on race; requires Idempotency-Key — D-70-02)"
    ),
)
async def client_create_booking(
    payload: ClientCreateBookingRequest,
    request: Request,
    client: Annotated[ClientPrincipal, Depends(require_client())],
    _csrf: Annotated[None, Depends(verify_client_csrf)],
    idempotency_key: Annotated[str, Depends(verify_client_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Create a confirmed booking for the authenticated client (Phase 70 CBOOK-03/04).

    RBAC-04 ordering: require_client() → verify_client_csrf → verify_client_idempotency
    → get_db / get_redis.

    client.id is the IDOR-safe source (T-70-11): NO client_id in the body
    (ClientCreateBookingRequest has no client_id field).

    CBOOK-04: PtPackageNotActiveError is mapped to 422 no_active_pt_package in the
    service delegate (service.create_booking_for_client_request) so the PWA can
    route the user to Plans/Checkout (D-70-03).

    CBOOK-03: SlotAlreadyBookedError from the partial-UNIQUE race bubbles as 409
    slot_already_booked. Two requests with DISTINCT Idempotency-Keys surface the
    race at the DB partial UNIQUE (uq_bookings_slot_confirmed); same key replays.

    Two-phase Redis idempotency (D-70-02 / D-66-LIFECYCLE-HELPER): mirrors staff
    POST /bookings (bookings/router.py:116-128) with verify_client_idempotency
    instead of verify_idempotency.

    No try/except — AppError bubbles to _app_error_handler.
    """
    incoming_body = await request.body()
    client_id = client.id

    async def _runner() -> tuple[int, bytes]:
        booking = await service.create_booking_for_client_request(
            session,
            client_id=client_id,
            slot_id=payload.slot_id,
            pt_package_id=payload.pt_package_id,
        )
        body_bytes = json.dumps(
            envelope(booking).model_dump(mode="json", by_alias=True),
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return status.HTTP_201_CREATED, body_bytes

    return await idempotent_execute(redis, idempotency_key, incoming_body, runner=_runner)


@router.post(
    "/booking/{booking_id}/cancel",
    response_model=ResponseEnvelope[ClientBookingResponse],
    status_code=status.HTTP_200_OK,
    operation_id="client_cancel_booking",
    summary=(
        "Cancel the authenticated client's own confirmed booking (CBOOK-05; "
        "404 booking_not_found on non-owned booking — IDOR anti-oracle; "
        "409 cancel_window_expired if outside client cancel window)"
    ),
)
async def client_cancel_booking(
    booking_id: UUID,
    client: Annotated[ClientPrincipal, Depends(require_client())],
    _csrf: Annotated[None, Depends(verify_client_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientBookingResponse]:
    """Cancel the authenticated client's own confirmed booking (Phase 70 CBOOK-05).

    RBAC-04 ordering: require_client() → verify_client_csrf → get_db.

    IDOR 404-collapse (T-70-09 / D-20-IDOR): client.id is the ONLY ownership
    source. Cancelling another client's booking returns 404 booking_not_found
    (anti-oracle — never 403 or an existence signal per D-70-09). Ownership
    check is inside bookings.service.cancel_booking_for_client.

    Slot restored to 'active' by the cancel delegate (CBOOK-05 slot-restore).
    No credit action (D-70-06 — credit is at pt_sessions level).
    No try/except — AppError bubbles to _app_error_handler.
    """
    booking = await service.cancel_client_booking(
        session,
        client_id=client.id,
        booking_id=booking_id,
    )
    return envelope(booking)


@router.get(
    "/slots",
    response_model=ResponseEnvelope[PaginatedData[ClientAvailableSlotItem]],
    operation_id="client_list_slots",
    summary=(
        "Bookable active future slots filtered by the client's active PT-package "
        "trainer pin (CBOOK-02; client-safe projection; paginated)"
    ),
)
async def client_list_slots(
    query: Annotated[PageQuery, Depends()],
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[ClientAvailableSlotItem]]:
    """Available bookable slots for the authenticated client (Phase 70 CBOOK-02).

    Trainer-pin: if the client's active PT-package pins a trainer, only that
    trainer's active future slots are returned; else all trainers' slots.

    Client-safe projection (T-70-13): trainer name + times only — no owner-only
    economics, no internal status details (D-69-05 catalog discipline).

    No CSRF dep — GET is safe.
    No try/except — AppError bubbles to _app_error_handler.
    """
    page = await service.list_available_slots(
        session,
        client_id=client.id,
        page=query.page,
        page_size=query.page_size,
    )
    return envelope(page)


# ---------------------------------------------------------------------------
# Phase 70 CCHK-01..03 — QR token issuance + self check-in
# ---------------------------------------------------------------------------


@router.get(
    "/qr-token",
    response_model=ResponseEnvelope[ClientQrTokenResponse],
    operation_id="client_get_qr_token",
    summary=(
        "Mint a short-lived (~60s) signed QR self check-in token for the "
        "authenticated client (CCHK-01; no membership pre-check)"
    ),
)
async def client_get_qr_token(
    request: Request,
    client: Annotated[ClientPrincipal, Depends(require_client())],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[ClientQrTokenResponse]:
    """Issue a signed QR self check-in JWT (Phase 70 CCHK-01 / D-70-09).

    RBAC-04: require_client() gates this endpoint — the client must be
    authenticated (D-70-09). No CSRF dep — GET is safe.

    NO membership pre-check (D-70-09): gating on active membership happens
    at scan time inside _create_visit_with_anti_fraud. The PWA can display a
    QR code even before the client has an active membership, allowing the
    reception to activate one on their behalf while they wait.

    Rate-limit (T-70-18): 20 req/min per IP (per _enforce_qr_token_rate_limit).
    Legitimate use: one refresh per ~50s. RateLimited(429) bubbles.

    No try/except — AppError bubbles to _app_error_handler.
    """
    ip = request.client.host if request.client is not None else "unknown"
    await _enforce_qr_token_rate_limit(redis, ip)
    result = service.issue_qr_token(client.id)
    return envelope(result)


@router.post(
    "/check-in",
    response_model=ResponseEnvelope[ClientCheckInResponse],
    status_code=status.HTTP_200_OK,
    operation_id="client_check_in",
    summary=(
        "QR self check-in: validate the signed token and create a visit "
        "(CCHK-02; token-as-credential — no require_client; client_id from sub only)"
    ),
)
async def client_check_in(
    payload: ClientCheckInRequest,
    request: Request,
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientCheckInResponse]:
    """QR self check-in endpoint (Phase 70 CCHK-02 / D-70-11).

    DELIBERATELY NO require_client() — the signed QR token is the sole credential
    (gym scanner / turnstile is the caller, D-70-11). There is NO client_id parameter
    in the body, path, or query: cross-client check-in is structurally impossible
    (T-70-17 / criterion #5). client_id derives ONLY from the verified sub claim
    inside service.check_in_via_qr → decode_qr_token(token).sub.

    Token validation (D-70-08):
      - decode_qr_token asserts typ='qr_checkin' AND aud='qr'
      - an access/refresh token → 401 wrong_token_type or wrong_audience
      - an expired token → 401 token_expired
      - InvalidAccessToken bubbles to _app_error_handler → 401

    Same-day replay (criterion #5): _create_visit_with_anti_fraud collapses
    to DuplicateCheckinError('duplicate_checkin') via uq_visits_client_id_gym_date.

    Rate-limit (T-70-18): 60 req/min per IP (per _enforce_check_in_rate_limit).
    Accommodates multi-scanner gym reception while bounding flood attacks.
    RateLimited(429) bubbles to _app_error_handler.

    No try/except for domain errors — AppError bubbles to _app_error_handler.
    """
    ip = request.client.host if request.client is not None else "unknown"
    await _enforce_check_in_rate_limit(redis, ip)
    result = await service.check_in_via_qr(session, token=payload.token)
    return envelope(result)


# ---------------------------------------------------------------------------
# Phase 71 CPAY-01..05 — client checkout + payment status
# ---------------------------------------------------------------------------


@router.post(
    "/checkout/memberships/{plan_id}",
    response_model=ResponseEnvelope[ClientCheckoutResponse],
    status_code=status.HTTP_201_CREATED,
    operation_id="client_checkout_membership",
    summary=(
        "Client-initiated membership checkout via ЮKassa redirect (CPAY-01); "
        "server-derived per-day idempotency key (D-71-04); "
        "422 client_email_required_for_online_payment if email missing (CPAY-04)"
    ),
)
async def client_checkout_membership(
    plan_id: UUID,
    payload: ClientCheckoutRequest,
    client: Annotated[ClientPrincipal, Depends(require_client())],
    _csrf: Annotated[None, Depends(verify_client_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
    yookassa_settings: Annotated[YooKassaSettings, Depends(get_yookassa_settings)],
) -> ResponseEnvelope[ClientCheckoutResponse]:
    """CPAY-01. Client-initiated membership checkout (Phase 71).

    RBAC-04 ordering: require_client() → verify_client_csrf → get_db.
    Server-derived membership idempotency key (D-71-04): same-day repeat returns
    the same confirmation_url (replay check in the core, CPAY-05).
    actor_user_id=None (D-71-02: client-initiated; online_payments.created_by_user_id nullable).
    422 email gate enforced inside _sell_subject_core (CPAY-04, 54-ФЗ).
    No try/except — AppError bubbles to _app_error_handler.
    No CSRF applied to GET methods; CSRF dep required on this POST (T-71-09).
    Commit owner: caller-owns-txn (D-32-10/D-49-19); service only flushes.
    """
    result = await service.client_checkout_membership(
        session, plan_id=plan_id, client=client, yookassa_settings=yookassa_settings
    )
    await session.commit()
    return envelope(result)


@router.post(
    "/checkout/pt-packages/{plan_id}",
    response_model=ResponseEnvelope[ClientCheckoutResponse],
    status_code=status.HTTP_201_CREATED,
    operation_id="client_checkout_pt_package",
    summary=(
        "Client-initiated PT-package checkout via ЮKassa redirect (CPAY-02); "
        "client-supplied Idempotency-Key header (D-71-04); "
        "422 client_email_required_for_online_payment if email missing (CPAY-04)"
    ),
)
async def client_checkout_pt_package(
    plan_id: UUID,
    payload: ClientCheckoutRequest,
    client: Annotated[ClientPrincipal, Depends(require_client())],
    _csrf: Annotated[None, Depends(verify_client_csrf)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    session: Annotated[AsyncSession, Depends(get_db)],
    yookassa_settings: Annotated[YooKassaSettings, Depends(get_yookassa_settings)],
) -> ResponseEnvelope[ClientCheckoutResponse]:
    """CPAY-02. Client-initiated PT-package checkout (Phase 71).

    RBAC-04 ordering: require_client() → verify_client_csrf → get_db.
    Client-supplied Idempotency-Key header (D-71-04): PT allows same-day repurchase;
    PWA generates UUID per checkout intent, reuses on retry.
    actor_user_id=None (D-71-02: client-initiated).
    422 email gate enforced inside _sell_subject_core (CPAY-04, 54-ФЗ).
    No try/except — AppError bubbles to _app_error_handler.
    No CSRF applied to GET methods; CSRF dep required on this POST (T-71-09).
    Commit owner: caller-owns-txn (D-32-10/D-49-19); service only flushes.
    """
    result = await service.client_checkout_pt_package(
        session,
        plan_id=plan_id,
        client=client,
        idempotency_key=idempotency_key,
        yookassa_settings=yookassa_settings,
    )
    await session.commit()
    return envelope(result)


@router.get(
    "/payments/{payment_id}/status",
    response_model=ResponseEnvelope[ClientPaymentStatusResponse],
    operation_id="client_get_payment_status",
    summary=(
        "Coarse payment status for the authenticated client (CPAY-03 anti-oracle); "
        "returns only pending|succeeded|canceled; "
        "404 payment_not_found on non-owned payment (D-20-IDOR 404-collapse)"
    ),
)
async def client_get_payment_status(
    payment_id: UUID,
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientPaymentStatusResponse]:
    """CPAY-03. Coarse payment status (Phase 71).

    Anti-oracle: returns only 'pending' | 'succeeded' | 'canceled' — never exposes
    membership activation details or plan internals (T-71-05).
    D-20-IDOR: mandatory client_id filter in repository layer; None → NotFoundError → 404.
    A non-owned payment_id is indistinguishable from a non-existent one (404-collapse).
    No CSRF dep — GET is safe (T-71-09: CSRF only on state-changing POST).
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.get_client_payment_status(session, payment_id, client.id)
    return envelope(result)
