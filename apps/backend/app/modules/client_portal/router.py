"""Client-portal router — read + write endpoints for authenticated clients (Phase 69/70).

Phase 69 CHOME-01..03, CHIST-01..03, CPLAN-01..03.
Phase 70 CBOOK-02..05 — client booking POST (idempotent), cancel, and slots-read.

All handlers gated via Depends(require_client()).
No CSRF dep on GET endpoints (safe methods). POST/DELETE endpoints add
Depends(verify_client_csrf) after require_client() per RBAC-04 ordering.
Booking POST additionally adds Depends(verify_client_idempotency) per D-70-02.

D-69-03: Empty states are 200 with null/[] — never 404 for own scope.
D-20-IDOR: Every owned resource read has mandatory client_id filter in repo layer.
D-20-OPENAPI: Client-Portal tag; client_ operationId prefix.
D-20-MODULE: Write delegates via Protocol slots only — no app.modules.bookings import.
"""

from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import ClientPrincipal, require_client, verify_client_csrf
from app.core.idempotency import idempotent_execute, verify_client_idempotency
from app.core.pagination import PageQuery, PaginatedData
from app.core.redis import get_redis
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.client_portal import service
from app.modules.client_portal.schemas import (
    ClientAvailableSlotItem,
    ClientBookingResponse,
    ClientCatalogPlanResponse,
    ClientCatalogPtPackageResponse,
    ClientCatalogTrainerResponse,
    ClientCreateBookingRequest,
    ClientHomeResponse,
    ClientMembershipResponse,
    ClientNextBookingResponse,
    ClientPaymentItem,
    ClientPtSessionItem,
    ClientVisitItem,
)

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
        "422 cancel_window_expired if outside client cancel window)"
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
