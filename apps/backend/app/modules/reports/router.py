"""Reports router — owner-only aggregate endpoints (Phase 55 REV-01..05; Phase 56 AUD-01..06).

All reports endpoints are owner-only via
``Depends(require_permission(Action.VIEW, Resource.REPORTS))``
(``(VIEW, REPORTS)`` is in ``OWNER_ONLY`` per D-54-03 / permissions.py:65).

Audit-log endpoints (audit_log_router) use
``Depends(require_permission(Action.LIST, Resource.AUDIT_LOG))``
((LIST, AUDIT_LOG) is in OWNER_ONLY per permissions.py:128-129).

JSON responses return ``ResponseEnvelope[...]`` via ``envelope(...)``.
CSV routes return ``StreamingResponse`` directly — NO ResponseEnvelope, NO envelope() call,
NO response_model (EXP-01..04, D-11, D-12).

No try/except in route handlers — AppError subclasses bubble to the
registered ``_app_error_handler`` (core/exceptions.py:register_exception_handlers).

Design note: ``from``/``to`` date params are declared as route-level
``Query(alias="from")``/``Query(alias="to")`` (live-verified: Field(alias=...) on a
Depends() model field does NOT bind ``?from=`` on this FastAPI+Pydantic v2 stack).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission
from app.core.pagination import PaginatedData
from app.core.permissions import Action, Resource
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.reports import csv_export, service
from app.modules.reports.constants import (
    CSV_AUDIT_LOG_HEADERS,
    CSV_CLIENTS_HEADERS,
    CSV_REVENUE_HEADERS,
    CSV_TRAINER_USAGE_HEADERS,
    CSV_VISITS_HEADERS,
)
from app.modules.reports.schemas import (
    AtRiskMembersResponse,
    AuditLogItem,
    AuditLogQuery,
    ClientsReportQuery,
    ClientsReportResponse,
    CohortRetentionQuery,
    CohortRetentionResponse,
    LoadNowResponse,
    RevenueReportQuery,
    RevenueReportResponse,
    TrainerUsageReportQuery,
    TrainerUsageReportResponse,
    VisitAnomalyQuery,
    VisitAnomalyResponse,
    VisitsReportQuery,
    VisitsReportResponse,
)

router = APIRouter(tags=["Reports"])

# Second router for audit-log (D-02): mounted at /audit-log prefix in api/v1/router.py.
audit_log_router = APIRouter(tags=["Audit-log"])


@router.get(
    "/revenue",
    response_model=ResponseEnvelope[RevenueReportResponse],
    summary="Revenue by period (day|month) from payments ledger (owner-only; REV-01..05)",
)
async def get_revenue_report(
    query: Annotated[RevenueReportQuery, Depends()],
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.REPORTS))],
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
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.REPORTS))],
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
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.REPORTS))],
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


# ---------------------------------------------------------------------------
# CSV export routes — Phase 56 EXP-01, EXP-03, EXP-04
# Return StreamingResponse directly — NO ResponseEnvelope, NO response_model.
# RBAC: same require_permission as JSON siblings ((VIEW, REPORTS) ∈ OWNER_ONLY).
# ---------------------------------------------------------------------------


@router.get(
    "/revenue.csv",
    response_class=StreamingResponse,
    summary="Revenue CSV download — period buckets with ruble amounts (owner-only; EXP-01)",
)
async def get_revenue_csv(
    query: Annotated[RevenueReportQuery, Depends()],
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.REPORTS))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    """Stream revenue report as UTF-8 BOM + RFC-4180 CSV.

    Same query params as GET /reports/revenue (EXP-03, SC#5).
    Money columns are period-decimal rubles (D-13); header row = CSV_REVENUE_HEADERS.

    Owner-only: (VIEW, REPORTS) ∈ OWNER_ONLY; reception → 403.
    Range validation: to<from → 422; range>366 days → 422.
    No try/except — errors bubble to _app_error_handler.
    """
    rows = await service.revenue_csv_rows(session, query)
    return csv_export.make_csv_streaming_response(iter(rows), CSV_REVENUE_HEADERS, "revenue.csv")


@router.get(
    "/clients.csv",
    response_class=StreamingResponse,
    summary="Clients snapshot CSV download — single summary row (owner-only; EXP-03)",
)
async def get_clients_csv(
    query: Annotated[ClientsReportQuery, Depends()],
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.REPORTS))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    """Stream clients snapshot as UTF-8 BOM + RFC-4180 CSV (single data row).

    Same query params as GET /reports/clients (EXP-03, SC#5).
    Header row = CSV_CLIENTS_HEADERS; single summary row.

    Owner-only: (VIEW, REPORTS) ∈ OWNER_ONLY; reception → 403.
    """
    rows = await service.clients_csv_rows(session, query)
    return csv_export.make_csv_streaming_response(iter(rows), CSV_CLIENTS_HEADERS, "clients.csv")


@router.get(
    "/visits.csv",
    response_class=StreamingResponse,
    summary="Visits daily CSV download — one row per day with visit count (owner-only; EXP-03)",
)
async def get_visits_csv(
    query: Annotated[VisitsReportQuery, Depends()],
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.REPORTS))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    """Stream visits daily series as UTF-8 BOM + RFC-4180 CSV.

    Same query params as GET /reports/visits (EXP-03, SC#5).
    Daily-only (date, count); hourly section deferred (D-15 discretion).
    Header row = CSV_VISITS_HEADERS.

    Owner-only: (VIEW, REPORTS) ∈ OWNER_ONLY; reception → 403.
    """
    rows = await service.visits_csv_rows(session, query)
    return csv_export.make_csv_streaming_response(iter(rows), CSV_VISITS_HEADERS, "visits.csv")


@router.get(
    "/trainers",
    response_model=ResponseEnvelope[TrainerUsageReportResponse],
    summary="Trainer-usage report (owner-only; RPT-01..02, RPT-04)",
    description=(
        "Per-trainer aggregate for [fromDate, toDate] MSK: session counts, hours, "
        "unique clients, utilization %, revenue, accrued vs paid compensation. "
        "Revenue is attributed to the trainer assigned at PT-package sale time. "
        "Range cap: 366 days (D-06); toDate<fromDate → 422; reception → 403."
    ),
    tags=["reports"],
    responses={
        403: {"description": "reception forbidden — (VIEW, REPORTS) ∈ OWNER_ONLY"},
        422: {"description": "invalid period — toDate<fromDate or range>366 days"},
    },
)
async def get_trainers_report(
    query: Annotated[TrainerUsageReportQuery, Depends()],
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.REPORTS))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[TrainerUsageReportResponse]:
    """Per-trainer usage aggregate for the given period (RPT-01..02, RPT-04).

    Returns TrainerUsageReportResponse with a list of TrainerUsageRow entries,
    one per trainer who had at least one session in the period.

    Owner-only: (VIEW, REPORTS) ∈ OWNER_ONLY; reception → 403.
    Range cap: 366 days (D-06); toDate<fromDate → 422.
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.get_trainer_usage_report(session, query)
    return envelope(result)


@router.get(
    "/trainers.csv",
    response_class=StreamingResponse,
    summary="Trainer-usage CSV download (owner-only; RPT-03)",
    description=(
        "Stream trainer-usage report as UTF-8 BOM + RFC-4180 CSV. "
        "Same query params as GET /reports/trainers. "
        "One row per trainer; money columns in period-decimal rubles; "
        "None/NULL cells render as empty string. "
        "Filename: trainer-usage-YYYY-MM-DD-YYYY-MM-DD.csv (EXP-01 precedent). "
        "Owner-only; reception → 403."
    ),
    tags=["reports"],
)
async def get_trainers_csv(
    query: Annotated[TrainerUsageReportQuery, Depends()],
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.REPORTS))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    """Stream trainer-usage report as UTF-8 BOM + RFC-4180 CSV (RPT-03).

    Same query params as GET /reports/trainers (EXP-01 precedent, SC#5).
    One row per trainer; header row = CSV_TRAINER_USAGE_HEADERS.
    Money columns are period-decimal rubles (D-13); None → empty cell (D-60-11).
    Filename: trainer-usage-{from_date.isoformat()}-{to_date.isoformat()}.csv

    Owner-only: (VIEW, REPORTS) ∈ OWNER_ONLY; reception → 403.
    Range cap: 366 days (D-06); toDate<fromDate → 422.
    No try/except — AppError bubbles to _app_error_handler.
    """
    filename = f"trainer-usage-{query.from_date.isoformat()}-{query.to_date.isoformat()}.csv"
    rows = await service.trainer_usage_csv_rows(session, query)
    return csv_export.make_csv_streaming_response(iter(rows), CSV_TRAINER_USAGE_HEADERS, filename)


# ---------------------------------------------------------------------------
# Advanced analytics routes (Phase 115 ANL-02..04)
# All owner-only via require_permission(Action.VIEW, Resource.REPORTS).
# No try/except — AppError bubbles to _app_error_handler.
# TODO Phase 117: the four advanced-analytics paths (/reports/cohort | /reports/anomaly
#   | /reports/at-risk | /reports/load/now) already exist in packages/api-client/src/
#   schema.d.ts, but with untyped (content: unknown) response bodies. Remaining work is
#   to regen typed response bodies + _v32Checks for these paths.
# ---------------------------------------------------------------------------


@router.get(
    "/cohort",
    response_model=ResponseEnvelope[CohortRetentionResponse],
    summary="Cohort retention grid (owner-only; ANL-02)",
    description=(
        "Cohort = membership-start month; retention = % of cohort with ≥1 visit "
        "per subsequent month. Query param: ?cohortMonths=6 (default 6, max 12). "
        "Owner-only: (VIEW, REPORTS) ∈ OWNER_ONLY; reception → 403."
    ),
)
async def get_cohort_report(
    query: Annotated[CohortRetentionQuery, Depends()],
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.REPORTS))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[CohortRetentionResponse]:
    """Cohort retention grid for owner analytics dashboard (ANL-02).

    Returns nested { cohorts: [{ cohortMonth, label, months: [{ offset, retentionPct }] }],
    maxOffset } — matches UI-SPEC CohortRetentionSchema.

    Owner-only: (VIEW, REPORTS) ∈ OWNER_ONLY; reception → 403.
    cohort_months validated 1..12 → 422 on out-of-range.
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.get_cohort_retention(session, query)
    return envelope(result)


@router.get(
    "/anomaly",
    response_model=ResponseEnvelope[VisitAnomalyResponse],
    summary="Visit-anomaly daily series with >2-sigma spike/drop flags (owner-only; ANL-02)",
    description=(
        "Daily visit counts flagged when count deviates > 2 sigma from a trailing "
        "14-day rolling mean. Optional date range: ?fromDate=...&toDate=... "
        "(default: last 90 days MSK). Owner-only: (VIEW, REPORTS) ∈ OWNER_ONLY; reception → 403."
    ),
)
async def get_anomaly_report(
    query: Annotated[VisitAnomalyQuery, Depends()],
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.REPORTS))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[VisitAnomalyResponse]:
    """Visit-anomaly detection for owner analytics dashboard (ANL-02).

    Returns contiguous daily series with is_anomaly/direction flags.
    Gap days (no visits) are filled with count=0; std==0 → no anomaly (guarded).

    Owner-only: (VIEW, REPORTS) ∈ OWNER_ONLY; reception → 403.
    to < from → 422; range > 366 days → 422.
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.get_visit_anomaly(session, query)
    return envelope(result)


@router.get(
    "/at-risk",
    response_model=ResponseEnvelope[AtRiskMembersResponse],
    summary="At-risk member list: active membership + last visit >14 days ago (owner-only; ANL-02)",
    description=(
        "Returns clients with an active membership whose last visit was >14 days ago "
        "(or who have never visited). Capped at 50 items. "
        "Owner-only: (VIEW, REPORTS) ∈ OWNER_ONLY; reception → 403."
    ),
)
async def get_at_risk_report(
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.REPORTS))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[AtRiskMembersResponse]:
    """At-risk member list for owner churn-prevention dashboard (ANL-02).

    Returns { count, items: [AtRiskMember], thresholdDays }.
    Never-visited clients are included (lastVisitDate=null).

    Owner-only: (VIEW, REPORTS) ∈ OWNER_ONLY; reception → 403.
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.get_at_risk_members(session)
    return envelope(result)


@router.get(
    "/load/now",
    response_model=ResponseEnvelope[LoadNowResponse],
    summary="Live gym headcount — rolling-window approximation (owner-only; ANL-03)",
    description=(
        "Distinct clients with checked_in_at in the last 120 minutes. "
        "Approximation: no checkout column on Visit; window ≈ average session. "
        "Returns { count, asOf, windowMinutes }. "
        "Owner-only: (VIEW, REPORTS) ∈ OWNER_ONLY; reception → 403."
    ),
)
async def get_load_now(
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.REPORTS))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[LoadNowResponse]:
    """Live in-gym headcount counter for the Load page (ANL-03).

    Returns { count, asOf, windowMinutes } — point-in-time snapshot.
    count = 0 when no clients checked in within the rolling window.

    Owner-only: (VIEW, REPORTS) ∈ OWNER_ONLY; reception → 403.
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.get_load_now(session)
    return envelope(result)


# ---------------------------------------------------------------------------
# Audit-log router (Phase 56 AUD-01..06)
# ---------------------------------------------------------------------------


@audit_log_router.get(
    "",
    response_model=ResponseEnvelope[PaginatedData[AuditLogItem]],
    summary="Paginated audit-log listing (owner-only; AUD-01..06)",
)
async def list_audit_log(
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: Annotated[date | None, Query(alias="to")] = None,
    query: Annotated[AuditLogQuery, Depends()] = ...,  # type: ignore[assignment]
    _actor: Annotated[
        CurrentUser, Depends(require_permission(Action.LIST, Resource.AUDIT_LOG))
    ] = ...,  # type: ignore[assignment]
    session: Annotated[AsyncSession, Depends(get_db)] = ...,  # type: ignore[assignment]
) -> ResponseEnvelope[PaginatedData[AuditLogItem]]:
    """Paginated audit-log listing with optional AND-combined filters (AUD-01..06).

    Results ordered created_at DESC, id DESC (stable pagination, AUD-06, D-08).
    Filter params: ?actorUserId=...&actorEmailSnapshot=...&resourceType=...&action=...
    Date window (inclusive MSK day bounds): ?from=YYYY-MM-DD&to=YYYY-MM-DD
    Pagination: ?page=1&pageSize=20 (max pageSize=100).

    ``from``/``to`` are route-level Query(alias=...) params (NOT AuditLogQuery fields) —
    live-verified: Field(alias="from") on a Depends() model does NOT bind ``?from=`` on
    this FastAPI + Pydantic v2 stack.

    Owner-only: (LIST, AUDIT_LOG) in OWNER_ONLY; reception -> 403 (AUD-05, SC#1).
    Unknown action/resource_type -> 422 audit_filter_invalid (AUD-03, D-05).
    to < from -> 422 (D-06).
    No try/except -- AppError bubbles to _app_error_handler.
    """
    result = await service.list_audit_log(session, query, from_=from_, to=to)
    return envelope(result)


@audit_log_router.get(
    ".csv",
    response_class=StreamingResponse,
    summary="Audit-log CSV download — all matching rows (owner-only; EXP-02)",
)
async def get_audit_log_csv(
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: Annotated[date | None, Query(alias="to")] = None,
    query: Annotated[AuditLogQuery, Depends()] = ...,  # type: ignore[assignment]
    _actor: Annotated[
        CurrentUser, Depends(require_permission(Action.LIST, Resource.AUDIT_LOG))
    ] = ...,  # type: ignore[assignment]
    session: Annotated[AsyncSession, Depends(get_db)] = ...,  # type: ignore[assignment]
) -> StreamingResponse:
    """Stream audit-log as UTF-8 BOM + RFC-4180 CSV (all matching rows, D-16).

    Same filters as GET /audit-log JSON endpoint (EXP-02, SC#5):
      ?action=...&resourceType=...&actorUserId=...&actorEmailSnapshot=...
      ?from=YYYY-MM-DD&to=YYYY-MM-DD (route-level Query(alias=...) params)

    Streams ALL matching rows (no pagination) row-by-row — memory bounded by
    stream_scalars cursor (T-56-08, D-16).

    createdAt formatted as 'YYYY-MM-DD HH:MM:SS' Europe/Moscow (D-14).
    payload serialized as compact JSON string (ensure_ascii=False, Cyrillic literal).

    ``from``/``to`` are route-level Query(alias=...) params (NOT AuditLogQuery fields) —
    mirrors the JSON handler pattern (live-verified: Field(alias="from") on Depends()
    model does NOT bind ``?from=`` on this FastAPI + Pydantic v2 stack).

    Owner-only: (LIST, AUDIT_LOG) ∈ OWNER_ONLY; reception → 403 (T-56-06).
    Unknown action/resource_type → 422 audit_filter_invalid (T-56-10, SC#5).
    to < from → 422.
    No try/except — AppError bubbles to _app_error_handler.

    IMPORTANT: validate_audit_filters is called EAGERLY here (before StreamingResponse)
    so validation errors are raised in the request-response phase where _app_error_handler
    can intercept them. If validation lived inside the async generator body it would fire
    after headers are sent (inside StreamingResponse) and could not be intercepted.
    """
    # Validate filters eagerly in the request phase — must happen before StreamingResponse
    # is constructed so AuditFilterInvalidError / ValidationAppError are caught by the
    # registered exception handler (Rule 1 fix: async generator body fires too late).
    service.validate_audit_filters(query, from_=from_, to=to)

    rows = service.audit_log_csv_rows(session, query, from_=from_, to=to)
    return csv_export.make_async_csv_streaming_response(
        rows, CSV_AUDIT_LOG_HEADERS, "audit-log.csv"
    )
