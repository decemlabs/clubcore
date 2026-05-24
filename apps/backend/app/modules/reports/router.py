"""Reports router — owner-only aggregate endpoints (Phase 55 REV-01..05).

All reports endpoints are owner-only via
``Depends(require_permission(Action.VIEW, Resource.REPORTS))``
(``(VIEW, REPORTS)`` is in ``OWNER_ONLY`` per D-54-03 / permissions.py:65).

All responses return ``ResponseEnvelope[...]`` via ``envelope(...)``
(per payments/router.py pattern). Reports are aggregates, not lists —
they do NOT use PaginatedData (D-11).

No try/except in route handlers — AppError subclasses bubble to the
registered ``_app_error_handler`` (core/exceptions.py:register_exception_handlers).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission
from app.core.permissions import Action, Resource
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.reports import service
from app.modules.reports.schemas import (
    ClientsReportQuery,
    ClientsReportResponse,
    RevenueReportQuery,
    RevenueReportResponse,
    VisitsReportQuery,
    VisitsReportResponse,
)

router = APIRouter()


@router.get(
    "/revenue",
    response_model=ResponseEnvelope[RevenueReportResponse],
    summary="Revenue by period (day|month) from payments ledger (owner-only; REV-01..05)",
)
async def get_revenue_report(
    query: Annotated[RevenueReportQuery, Depends()],
    _actor: Annotated[
        CurrentUser, Depends(require_permission(Action.VIEW, Resource.REPORTS))
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[RevenueReportResponse]:
    """Aggregate payments ledger into period buckets with method/subject_kind breakdown.

    Refunds (subject_kind='refund', negative amount_kopecks) net into netKopecks
    only — they do NOT appear in bySubjectKind (D-01, REV-04).

    Owner-only: ``(VIEW, REPORTS)`` is in ``OWNER_ONLY``; reception → 403.
    Range cap: 366 days (D-06); to<from → 422.
    """
    result = await service.get_revenue_report(session, query)
    return envelope(result)


@router.get(
    "/clients",
    response_model=ResponseEnvelope[ClientsReportResponse],
    summary="Active/expiring/new clients summary (owner-only; CLR-01..04)",
)
async def get_clients_report(
    query: Annotated[ClientsReportQuery, Depends()],
    _actor: Annotated[
        CurrentUser, Depends(require_permission(Action.VIEW, Resource.REPORTS))
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientsReportResponse]:
    """Clients snapshot: active memberships, expiring-within-N count, new-clients in range.

    All counters exclude soft-deleted clients (CLR-04).
    `within` defaults to 7, range 1..30 (D-07); out-of-range → 422.
    Active/expiring are as-of-now (D-05); new-clients scoped to fromDate..toDate (CLR-03).

    Owner-only: ``(VIEW, REPORTS)`` is in ``OWNER_ONLY``; reception → 403.
    Range cap: 366 days (D-06); toDate<fromDate → 422.
    """
    result = await service.get_clients_report(session, query)
    return envelope(result)


@router.get(
    "/visits",
    response_model=ResponseEnvelope[VisitsReportResponse],
    summary="Visits by day/hour + average (owner-only; VIS-R-01..04)",
)
async def get_visits_report(
    query: Annotated[VisitsReportQuery, Depends()],
    _actor: Annotated[
        CurrentUser, Depends(require_permission(Action.VIEW, Resource.REPORTS))
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[VisitsReportResponse]:
    """Visits composite report: daily counts, hourly distribution, averagePerDay.

    Daily groups by gym_date (MSK STORED column — no secondary TZ conversion, VIS-R-04).
    Hourly groups by hour-of-day across the full range (VIS-R-02).
    averagePerDay = total visits / calendar days in range inclusive (D-10).
    Sparse buckets: only days/hours with visits appear (D-08).

    Owner-only: ``(VIEW, REPORTS)`` is in ``OWNER_ONLY``; reception → 403.
    Range cap: 366 days (D-06); toDate<fromDate → 422.
    """
    result = await service.get_visits_report(session, query)
    return envelope(result)
