"""Client-portal router — read endpoints for authenticated clients (Phase 69).

Phase 69 CHOME-01..03, CHIST-01..03, CPLAN-01..03.

All handlers gated via Depends(require_client()).
No CSRF dep on GET endpoints (safe methods). POST/PATCH endpoints add
Depends(verify_client_csrf) after require_client() per RBAC-04 ordering.

D-69-03: Empty states are 200 with null/[] — never 404 for own scope.
D-20-IDOR: Every owned resource read has mandatory client_id filter in repo layer.
D-20-OPENAPI: Client-Portal tag; client_ operationId prefix.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import ClientPrincipal, require_client
from app.core.pagination import PageQuery, PaginatedData
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.client_portal import service
from app.modules.client_portal.schemas import (
    ClientCatalogPlanResponse,
    ClientCatalogPtPackageResponse,
    ClientCatalogTrainerResponse,
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
