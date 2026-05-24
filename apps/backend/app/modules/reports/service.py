"""Reports service — read-only aggregator (Phase 55 REV/CLR/VIS-R; Phase 56 AUD-01..06).

Read-only aggregator role: orchestrates calls to repository.py which reads
cross-module data via raw SQL ``text()`` SELECTs (D-54-08 / D-49-03 precedent).
Phase 56 adds the audit-log ORM read path (repository uses ORM select(AuditLog),
not raw SQL — see CONTEXT.md D-04 for why ORM is appropriate here).

INVARIANTS (locked):
- ZERO INSERT / UPDATE / DELETE on any business table.
- SVC001 commit-gate does NOT apply (no write paths, no ``session.commit``).
- Never imports another module's ORM model — reads go through repository.py
  raw SQL readers exclusively. (app.core.* is a free import target; AuditLog
  is imported by repository.py, not here.)
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import date
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import LOCKED_AUDIT_EVENTS
from app.core.exceptions import ValidationAppError
from app.core.pagination import PaginatedData
from app.modules.reports import csv_export, repository
from app.modules.reports.constants import GRAIN_MONTH
from app.modules.reports.schemas import (
    AuditLogItem,
    AuditLogQuery,
    ClientsReportQuery,
    ClientsReportResponse,
    RevenueBucket,
    RevenueBucketByMethod,
    RevenueBucketBySubjectKind,
    RevenueReportQuery,
    RevenueReportResponse,
    VisitsDailyBucket,
    VisitsHourlyBucket,
    VisitsReportQuery,
    VisitsReportResponse,
)

# ---------------------------------------------------------------------------
# Audit-log filter validation sets (Phase 56 AUD-03, D-05)
# Derived once at module load from LOCKED_AUDIT_EVENTS (69 pairs).
# ---------------------------------------------------------------------------
VALID_ACTIONS: frozenset[str] = frozenset(e for e, _ in LOCKED_AUDIT_EVENTS)
VALID_RESOURCE_TYPES: frozenset[str] = frozenset(r for _, r in LOCKED_AUDIT_EVENTS)


class ReportRangeTooLargeError(ValidationAppError):
    """Date range exceeds 366-day cap (D-06). Code LOCKED per CONTEXT.md."""

    code = "report_range_too_large"
    status_code = 422


class AuditFilterInvalidError(ValidationAppError):
    """Unknown action or resource_type filter value (AUD-03, D-05). Code LOCKED."""

    code = "audit_filter_invalid"
    status_code = 422


def _validate_date_range(from_date: date, to_date: date) -> None:
    """Raise ValidationAppError when range is invalid.

    Raises:
        ValidationAppError: when to_date < from_date (D-05).
        ReportRangeTooLargeError: when (to_date - from_date).days > 366 (D-06).
    """
    if to_date < from_date:
        raise ValidationAppError("to must be >= from")
    if (to_date - from_date).days > 366:
        raise ReportRangeTooLargeError("Date range exceeds 366-day limit")


def _pivot_revenue_buckets(
    rows: list[dict[str, object]],
    query: RevenueReportQuery,
) -> RevenueReportResponse:
    """Pivot raw aggregate rows into the nested RevenueReportResponse shape.

    Row columns: period (date), method (str), subject_kind (str), total_kopecks (int).

    Pivot logic (D-01):
    - net_kopecks accumulates signed total_kopecks for ALL rows in the period,
      including refunds (subject_kind='refund', negative amount). This ensures
      REV-04: sale + same-period refund nets to zero.
    - by_method accumulates by method ('cash' / 'online') for ALL rows.
    - by_subject_kind accumulates ONLY for 'membership' and 'pt_package' rows;
      refund rows are excluded from the breakdown (D-01).
    """
    # Use dict to maintain insertion order (Python 3.7+); order follows SQL ORDER BY period.
    buckets: dict[str, tuple[int, RevenueBucketByMethod, RevenueBucketBySubjectKind]] = {}

    for row in rows:
        period_raw = row["period"]
        # period_raw is a Python date object from Postgres (both day + month date_trunc).
        # day -> "YYYY-MM-DD"; month date_trunc returns month-start date -> "YYYY-MM".
        period_str = (
            str(period_raw)[:7] if query.group_by == GRAIN_MONTH else str(period_raw)
        )

        if period_str not in buckets:
            buckets[period_str] = (
                0,
                RevenueBucketByMethod(),
                RevenueBucketBySubjectKind(),
            )

        net, by_method, by_subject_kind = buckets[period_str]
        total = int(row["total_kopecks"])  # type: ignore[call-overload]
        net += total

        method = str(row["method"])
        if method == "cash":
            by_method = RevenueBucketByMethod(
                cash=by_method.cash + total,
                online=by_method.online,
            )
        elif method == "online":
            by_method = RevenueBucketByMethod(
                cash=by_method.cash,
                online=by_method.online + total,
            )

        subject_kind = str(row["subject_kind"])
        if subject_kind == "membership":
            by_subject_kind = RevenueBucketBySubjectKind(
                membership=by_subject_kind.membership + total,
                pt_package=by_subject_kind.pt_package,
            )
        elif subject_kind == "pt_package":
            by_subject_kind = RevenueBucketBySubjectKind(
                membership=by_subject_kind.membership,
                pt_package=by_subject_kind.pt_package + total,
            )
        # 'refund' subject_kind: fold into net only, skip by_subject_kind (D-01)

        buckets[period_str] = (net, by_method, by_subject_kind)

    bucket_list = [
        RevenueBucket(
            period=period_str,
            net_kopecks=net,
            by_method=by_method,
            by_subject_kind=by_subject_kind,
        )
        for period_str, (net, by_method, by_subject_kind) in buckets.items()
    ]

    return RevenueReportResponse(
        buckets=bucket_list,
        from_date=query.from_date,
        to_date=query.to_date,
        group_by=query.group_by,
    )


async def get_revenue_report(
    session: AsyncSession,
    query: RevenueReportQuery,
) -> RevenueReportResponse:
    """Aggregate payments ledger by period bucket (REV-01..05).

    Read-only: NO session.commit(), NO session.flush().
    """
    _validate_date_range(query.from_date, query.to_date)
    rows = await repository.fetch_revenue_buckets(session, query)
    return _pivot_revenue_buckets(rows, query)


async def get_clients_report(
    session: AsyncSession,
    query: ClientsReportQuery,
) -> ClientsReportResponse:
    """Clients snapshot report (CLR-01..04).

    Validates the date range (for the new-clients window; D-05, D-06).
    Validates `within` bounds 1..30 (D-07) — raised as ValidationAppError for
    consistent 422 codes (schema layer stores `within` without ge/le to keep
    error code consistent with other report validations).

    Active/expiring counts are as-of-now (point-in-time, D-05).
    New clients count is scoped to [from_date, to_date] MSK (CLR-03).
    All counters exclude soft-deleted clients (CLR-04).

    Read-only: NO session.commit(), NO session.flush().
    """
    _validate_date_range(query.from_date, query.to_date)
    if query.within < 1 or query.within > 30:
        raise ValidationAppError(
            f"within must be between 1 and 30, got {query.within}"
        )

    active = await repository.fetch_active_memberships_count(session)
    expiring = await repository.fetch_expiring_memberships_count(session, query.within)
    new_clients = await repository.fetch_new_clients_count(
        session, query.from_date, query.to_date
    )

    return ClientsReportResponse(
        active_count=active,
        expiring_count=expiring,
        new_clients_count=new_clients,
        within_days=query.within,
    )


async def get_visits_report(
    session: AsyncSession,
    query: VisitsReportQuery,
) -> VisitsReportResponse:
    """Visits report — daily + hourly + averagePerDay (VIS-R-01..04, D-09).

    averagePerDay = total visits in range / calendar days in range (inclusive D-10).
    Calendar days = (to_date - from_date).days + 1 (counts from_date AND to_date).
    Returned as a float rounded to 2 decimal places (researcher discretion per D-10).

    Sparse buckets (D-08): only days/hours with visits appear.
    Daily groups by gym_date directly — no secondary TZ conversion (VIS-R-04, D-04).
    Hourly groups by MSK hour-of-day across the whole range (VIS-R-02).

    Read-only: NO session.commit(), NO session.flush().
    """
    _validate_date_range(query.from_date, query.to_date)

    daily_rows = await repository.fetch_visits_daily(
        session, query.from_date, query.to_date
    )
    hourly_rows = await repository.fetch_visits_hourly(
        session, query.from_date, query.to_date
    )

    total = sum(int(r["count"]) for r in daily_rows)  # type: ignore[call-overload]
    calendar_days = (query.to_date - query.from_date).days + 1
    average_per_day = round(total / calendar_days, 2)

    return VisitsReportResponse(
        daily=[
            VisitsDailyBucket(
                date=cast(date, r["date"]),
                count=int(r["count"]),  # type: ignore[call-overload]
            )
            for r in daily_rows
        ],
        hourly=[
            VisitsHourlyBucket(
                hour=int(r["hour"]),  # type: ignore[call-overload]
                count=int(r["count"]),  # type: ignore[call-overload]
            )
            for r in hourly_rows
        ],
        average_per_day=average_per_day,
        from_date=query.from_date,
        to_date=query.to_date,
    )


def _validate_audit_filters(
    query: AuditLogQuery,
    *,
    from_: date | None = None,
    to: date | None = None,
) -> None:
    """Validate audit-log filter params; raise 422 on invalid values (AUD-03, D-05, D-06).

    Shared by list_audit_log (JSON) and audit_log_csv_rows (CSV) so both endpoints
    reject identical bad input (SC#5, EXP-02).

    Raises:
        AuditFilterInvalidError: unknown action or resource_type value.
        ValidationAppError: to < from_ date window inversion.
    """
    if query.action is not None and query.action not in VALID_ACTIONS:
        raise AuditFilterInvalidError(
            f"Unknown action '{query.action}'. Must be one of the 69 LOCKED_AUDIT_EVENTS."
        )

    if query.resource_type is not None and query.resource_type not in VALID_RESOURCE_TYPES:
        raise AuditFilterInvalidError(
            f"Unknown resource_type '{query.resource_type}'."
            " Must be one of the LOCKED_AUDIT_EVENTS resource types."
        )

    if from_ is not None and to is not None and to < from_:
        raise ValidationAppError("to must be >= from")


async def list_audit_log(
    session: AsyncSession,
    query: AuditLogQuery,
    *,
    from_: date | None = None,
    to: date | None = None,
) -> PaginatedData[AuditLogItem]:
    """Paginated audit-log listing with filter validation (AUD-01..06).

    Validates action/resource_type filters against LOCKED_AUDIT_EVENTS (AUD-03, D-05).
    Validates to < from_ → 422 ValidationAppError (D-06).
    No 366-day range cap (D-06 — pagination bounds by pageSize).

    from_/to are keyword-only args supplied by the route handler via route-level
    Query(alias="from")/Query(alias="to") params (NOT model fields on AuditLogQuery).

    Read-only: NO session.commit(), NO session.flush().
    """
    _validate_audit_filters(query, from_=from_, to=to)

    page = await repository.fetch_audit_log_page(session, query, from_=from_, to=to)

    # Convert ORM rows to AuditLogItem DTOs (from_attributes=True on ContractModel).
    return PaginatedData(
        items=[AuditLogItem.model_validate(row) for row in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )


# ---------------------------------------------------------------------------
# CSV row-builder helpers (Phase 56 EXP-01..04, D-15)
# These REUSE the existing Phase 55 aggregation functions (single source of truth).
# ---------------------------------------------------------------------------


async def revenue_csv_rows(
    session: AsyncSession,
    query: RevenueReportQuery,
) -> list[list[object]]:
    """Build revenue CSV data rows by reusing get_revenue_report (D-15).

    Each row corresponds to one period bucket with money formatted as rubles (D-13).
    Caller should validate date range before calling this function.

    Returns list of [period, netRubles, cashRubles, onlineRubles, membershipRubles,
    ptPackageRubles].
    """
    r = await get_revenue_report(session, query)
    return [
        [
            b.period,
            csv_export.format_kopecks_as_rubles(b.net_kopecks),
            csv_export.format_kopecks_as_rubles(b.by_method.cash),
            csv_export.format_kopecks_as_rubles(b.by_method.online),
            csv_export.format_kopecks_as_rubles(b.by_subject_kind.membership),
            csv_export.format_kopecks_as_rubles(b.by_subject_kind.pt_package),
        ]
        for b in r.buckets
    ]


async def clients_csv_rows(
    session: AsyncSession,
    query: ClientsReportQuery,
) -> list[list[object]]:
    """Build clients CSV data rows by reusing get_clients_report (D-15).

    Single summary row: [fromDate, toDate, within, activeMemberships, expiringWithinN, newClients].
    Caller should validate date range before calling this function.
    """
    r = await get_clients_report(session, query)
    return [
        [
            query.from_date.isoformat(),
            query.to_date.isoformat(),
            r.within_days,
            r.active_count,
            r.expiring_count,
            r.new_clients_count,
        ]
    ]


async def visits_csv_rows(
    session: AsyncSession,
    query: VisitsReportQuery,
) -> list[list[object]]:
    """Build visits CSV data rows by reusing get_visits_report (D-15).

    One row per daily bucket: [date, count].
    Daily-only (D-15 discretion: hourly section deferred, daily is primary series).
    Caller should validate date range before calling this function.
    """
    r = await get_visits_report(session, query)
    return [
        [d.date.isoformat(), d.count]
        for d in r.daily
    ]


async def audit_log_csv_rows(
    session: AsyncSession,
    query: AuditLogQuery,
    *,
    from_: date | None = None,
    to: date | None = None,
) -> AsyncIterator[list[object]]:
    """Async generator yielding audit-log CSV rows for all matching rows (EXP-02, D-16).

    Streams ALL filtered rows (no pagination) row-by-row via stream_scalars — memory
    is bounded regardless of result set size (T-56-08, D-16).

    Validates filters using the SAME _validate_audit_filters as list_audit_log so
    JSON and CSV reject identical bad input (SC#5, EXP-02).

    from_/to are keyword-only args from route-level Query(alias=...) params (not model
    fields on AuditLogQuery — live-verified pattern from Plan 01).

    Each row: [createdAt(MSK), actorUserId, actorEmailSnapshot, action, resourceType,
               resourceId, payload(compact JSON)].

    Yields:
        list[object]: One row per AuditLog entry in created_at DESC, id DESC order.

    Read-only: NO session.commit(), NO session.flush().
    """
    _validate_audit_filters(query, from_=from_, to=to)

    async for row in repository.stream_audit_log_rows(session, query, from_=from_, to=to):
        yield [
            csv_export.format_datetime_msk(row.created_at),
            str(row.actor_user_id) if row.actor_user_id is not None else "",
            row.actor_email_snapshot or "",
            row.action,
            row.resource_type,
            str(row.resource_id) if row.resource_id is not None else "",
            json.dumps(row.payload, ensure_ascii=False, separators=(",", ":")),
        ]
