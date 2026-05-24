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
from app.modules.reports.schemas import RevenueReportQuery, RevenueReportResponse

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
