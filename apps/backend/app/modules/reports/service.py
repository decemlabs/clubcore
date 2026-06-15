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
import math
from collections import defaultdict
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from typing import Literal, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import LOCKED_AUDIT_EVENTS
from app.core.exceptions import ValidationAppError
from app.core.pagination import PaginatedData
from app.modules.reports import csv_export, repository
from app.modules.reports.constants import (
    ANOMALY_LOOKBACK_DAYS,
    ANOMALY_SIGMA,
    ANOMALY_WINDOW_DAYS,
    AT_RISK_MAX_ITEMS,
    AT_RISK_THRESHOLD_DAYS,
    COHORT_MAX_MONTHS,
    GRAIN_MONTH,
    LOAD_NOW_WINDOW_MINUTES,
    TRAINER_REPORT_REVENUE_NOTE,
)
from app.modules.reports.schemas import (
    AtRiskMember,
    AtRiskMembersResponse,
    AuditLogItem,
    AuditLogQuery,
    ClientsReportQuery,
    ClientsReportResponse,
    CohortEntry,
    CohortMonthEntry,
    CohortRetentionQuery,
    CohortRetentionResponse,
    LoadNowResponse,
    RevenueBucket,
    RevenueBucketByMethod,
    RevenueBucketBySubjectKind,
    RevenueReportQuery,
    RevenueReportResponse,
    TrainerUsageReportQuery,
    TrainerUsageReportResponse,
    TrainerUsageRow,
    VisitAnomalyPoint,
    VisitAnomalyQuery,
    VisitAnomalyResponse,
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
        period_str = str(period_raw)[:7] if query.group_by == GRAIN_MONTH else str(period_raw)

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
        raise ValidationAppError(f"within must be between 1 and 30, got {query.within}")

    active = await repository.fetch_active_memberships_count(session)
    expiring = await repository.fetch_expiring_memberships_count(session, query.within)
    new_clients = await repository.fetch_new_clients_count(session, query.from_date, query.to_date)

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

    daily_rows = await repository.fetch_visits_daily(session, query.from_date, query.to_date)
    hourly_rows = await repository.fetch_visits_hourly(session, query.from_date, query.to_date)

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


def validate_audit_filters(
    query: AuditLogQuery,
    *,
    from_: date | None = None,
    to: date | None = None,
) -> None:
    """Validate audit-log filter params; raise 422 on invalid values (AUD-03, D-05, D-06).

    Shared by list_audit_log (JSON) and audit_log_csv_rows (CSV) so both endpoints
    reject identical bad input (SC#5, EXP-02).

    Called EAGERLY in route handlers (before StreamingResponse) so that validation
    errors are raised in the request-response phase where the exception handler can
    intercept them (not inside an async generator body after headers are sent).

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


# Keep private alias for internal callers that pre-dated the public name.
_validate_audit_filters = validate_audit_filters


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
    return [[d.date.isoformat(), d.count] for d in r.daily]


async def get_trainer_usage_report(
    session: AsyncSession,
    query: TrainerUsageReportQuery,
) -> TrainerUsageReportResponse:
    """Trainer-usage aggregate for [from_date, to_date] MSK (RPT-01..04).

    Thin orchestrator: validate date range -> fetch per-trainer rows ->
    assemble TrainerUsageReportResponse with revenue_attribution_note from constants.

    Read-only: NO session.commit(), NO session.flush().
    """
    _validate_date_range(query.from_date, query.to_date)
    rows = await repository.fetch_trainer_usage(session, query.from_date, query.to_date)
    return TrainerUsageReportResponse(
        trainers=[TrainerUsageRow.model_validate(row) for row in rows],
        from_date=query.from_date,
        to_date=query.to_date,
        revenue_attribution_note=TRAINER_REPORT_REVENUE_NOTE,
    )


async def trainer_usage_csv_rows(
    session: AsyncSession,
    query: TrainerUsageReportQuery,
) -> list[list[object]]:
    """Build trainer-usage CSV data rows by reusing get_trainer_usage_report (D-15).

    Column order mirrors CSV_TRAINER_USAGE_HEADERS (D-60-11):
      trainerNameSnapshot, sessionCount, cancelledSessionCount, totalHours,
      uniqueClientCount, utilizationPct, revenueRubles, avgRevenuePerSessionRubles,
      totalAccruedRubles, totalPaidRubles.

    sanitize_csv_text applied ONLY to trainer_name_snapshot (free-text, T-60-08).
    Numeric/money columns are NOT sanitized — a leading '-' on clawback accruals is a
    legitimate signed number, not a formula trigger (csv_export.py:32-35).

    utilization_pct = None -> empty CSV cell (NOT "None"/"NULL") (D-60-11).
    avg_revenue_per_session = None -> empty CSV cell (D-60-11).

    Read-only: NO session.commit(), NO session.flush().
    """
    r = await get_trainer_usage_report(session, query)
    return [
        [
            csv_export.sanitize_csv_text(row.trainer_name_snapshot),
            row.session_count,
            row.cancelled_session_count,
            f"{row.total_hours:.2f}",
            row.unique_client_count,
            "" if row.utilization_pct is None else f"{row.utilization_pct:.2f}",
            csv_export.format_kopecks_as_rubles(row.revenue_kopecks),
            (
                ""
                if row.avg_revenue_per_session is None
                else csv_export.format_kopecks_as_rubles(row.avg_revenue_per_session)
            ),
            csv_export.format_kopecks_as_rubles(row.total_accrued_kopecks),
            csv_export.format_kopecks_as_rubles(row.total_paid_kopecks),
        ]
        for row in r.trainers
    ]


# ---------------------------------------------------------------------------
# Payments CSV export (Phase 116 EXP-01)
# ---------------------------------------------------------------------------


async def payments_csv_rows(
    session: AsyncSession,
    *,
    from_date: date,
    to_date: date,
) -> list[list[object]]:
    """Build payments CSV data rows from the ledger (Phase 116 EXP-01).

    Thin orchestrator: validate date range -> fetch raw ledger rows ->
    format each field into CSV_PAYMENTS_HEADERS column order.

    Column order (CSV_PAYMENTS_HEADERS):
      date, clientName, amountRubles, method, subjectKind, refundOf, operatorEmail

    Formula-injection guard (CR-01 / T-116-08):
      - clientName: wrapped in sanitize_csv_text (user-derived free text).
      - operatorEmail: wrapped in sanitize_csv_text (user-derived free text).
      - amountRubles: NOT sanitized — signed ruble values legitimately start with '-'
        for refunds (csv_export.py:32-35 documenting the exclusion).

    Money formatting: format_kopecks_as_rubles (D-13; period decimal, no grouping).
    refundOf: str(uuid) for refund rows, empty string otherwise.

    Read-only: NO session.commit(), NO session.flush() (caller-owns-txn).
    """
    _validate_date_range(from_date, to_date)
    raw_rows = await repository.fetch_payments_for_csv(session, from_date, to_date)
    return [
        [
            row["received_at_msk"],
            csv_export.sanitize_csv_text(str(row["client_name"] or "")),
            csv_export.format_kopecks_as_rubles(int(row["amount_kopecks"])),
            row["method"],
            row["subject_kind"],
            str(row["refund_of"]) if row["refund_of"] else "",
            csv_export.sanitize_csv_text(str(row["operator_email"] or "")),
        ]
        for row in raw_rows
    ]


# ---------------------------------------------------------------------------
# Advanced analytics service functions (Phase 115 ANL-02..04)
# ---------------------------------------------------------------------------

# Russian month abbreviations for chart labels (MSK-pinned, no runtime locale switching).
_RU_MONTH_ABBR: tuple[str, ...] = (
    "янв", "фев", "мар", "апр", "май", "июн",
    "июл", "авг", "сен", "окт", "ноя", "дек",
)


def _ru_month_label(month_start: date) -> str:
    """Short Russian month label for a given month-start date, e.g. 'янв 2026'."""
    return f"{_RU_MONTH_ABBR[month_start.month - 1]} {month_start.year}"


def _ru_day_label(d: date) -> str:
    """Short Russian day label for a given date, e.g. '12 июн'."""
    return f"{d.day} {_RU_MONTH_ABBR[d.month - 1]}"


def _msk_today() -> date:
    """Current date in Europe/Moscow (UTC+3 fixed offset — no DST in MSK since 2014)."""
    # MSK = UTC+3; use fixed-offset calculation consistent with DB 'Europe/Moscow'.
    return (datetime.now(UTC) + timedelta(hours=3)).date()


def _compute_anomaly(
    daily_points: list[dict[str, int]],
    window_days: int,
    sigma: float,
) -> list[dict[str, object]]:
    """Flag anomalous days using a trailing rolling mean + population std (ANL-02).

    Args:
        daily_points: list of {'date': date, 'count': int}, contiguous, sorted ascending.
        window_days: number of preceding days used for rolling mean/std computation.
        sigma: deviation threshold (e.g. 2.0 → flag if |x - mean| > 2 * std).

    Returns:
        Same points enriched with is_anomaly (bool), direction (str|None), label (str).

    Guards:
        - std == 0 or nan → no anomaly (avoid div-by-zero / NaN propagation, T-115-02).
        - Fewer than window_days preceding points → no anomaly (insufficient baseline).
        - Empty input → [] (no error).

    Pure Python — no stdlib statistics import needed; uses only arithmetic.
    """
    result: list[dict[str, object]] = []
    for i, pt in enumerate(daily_points):
        d = pt["date"]
        count = pt["count"]
        label = _ru_day_label(d) if isinstance(d, date) else str(d)

        # Collect the trailing window (up to window_days preceding points).
        window = daily_points[max(0, i - window_days) : i]
        is_anomaly = False
        direction: str | None = None

        if len(window) >= window_days:
            counts = [w["count"] for w in window]
            mean = sum(counts) / len(counts)
            variance = sum((c - mean) ** 2 for c in counts) / len(counts)
            std = math.sqrt(variance)
            # std == 0 means all window values are identical → no anomaly
            if std > 0 and not (math.isnan(std) or math.isinf(std)):
                deviation = abs(count - mean)
                if deviation > sigma * std:
                    is_anomaly = True
                    direction = "spike" if count > mean else "drop"

        result.append(
            {
                "date": d.isoformat() if isinstance(d, date) else str(d),
                "count": count,
                "is_anomaly": is_anomaly,
                "direction": direction,
                "label": label,
            }
        )
    return result


async def get_load_now(session: AsyncSession) -> LoadNowResponse:
    """Live gym headcount — rolling-window approximation (ANL-03/ANL-04).

    Window length: LOAD_NOW_WINDOW_MINUTES (≈ average session; no checkout column on Visit).
    count = distinct clients with checked_in_at >= now() - window_minutes.

    Read-only: NO session.commit(), NO session.flush().
    Empty (no recent visits) → count=0.
    """
    count = await repository.fetch_load_now_count(session, LOAD_NOW_WINDOW_MINUTES)
    return LoadNowResponse(
        count=count,
        as_of=datetime.now(UTC),
        window_minutes=LOAD_NOW_WINDOW_MINUTES,
    )


async def get_at_risk_members(session: AsyncSession) -> AtRiskMembersResponse:
    """At-risk members: active membership + last visit > AT_RISK_THRESHOLD_DAYS ago (ANL-02).

    Includes never-visited clients (last_visit_date=None) — treated as maximally at-risk.
    Items are capped at AT_RISK_MAX_ITEMS (DoS guard, T-115-05).
    last_visit_label is pre-formatted in Russian.

    Read-only: NO session.commit(), NO session.flush().
    Empty (no active memberships or all visited recently) → count=0, items=[].
    """
    rows = await repository.fetch_at_risk_members(
        session, AT_RISK_THRESHOLD_DAYS, AT_RISK_MAX_ITEMS
    )
    # IN-02: count is the TRUE uncapped total (may exceed len(items) when the list is
    # capped at AT_RISK_MAX_ITEMS), so the FE "И ещё N клиентов" overflow line is correct.
    total_count = await repository.fetch_at_risk_count(session, AT_RISK_THRESHOLD_DAYS)
    items: list[AtRiskMember] = []
    for row in rows:
        last_visit_date_raw = row.get("last_visit_date")
        last_visit_date_str: str | None = None
        if last_visit_date_raw is not None:
            d = last_visit_date_raw
            last_visit_date_str = d.isoformat() if isinstance(d, date) else str(d)

        days = int(row["days_since_visit"])  # type: ignore[call-overload]

        # Russian label: 'N дней назад' or 'не посещал' for never-visited.
        if last_visit_date_str is None:
            label = "не посещал"
        else:
            # Simple plural form for дней/день/дня
            if days % 100 in range(11, 20):
                day_form = "дней"
            elif days % 10 == 1:
                day_form = "день"
            elif days % 10 in (2, 3, 4):
                day_form = "дня"
            else:
                day_form = "дней"
            label = f"{days} {day_form} назад"

        items.append(
            AtRiskMember(
                client_id=str(row["client_id"]),
                name=str(row["name"]),
                membership_type=str(row["membership_type"]),
                last_visit_date=last_visit_date_str,
                days_since_visit=days,
                last_visit_label=label,
            )
        )

    return AtRiskMembersResponse(
        count=total_count,
        items=items,
        threshold_days=AT_RISK_THRESHOLD_DAYS,
    )


async def get_cohort_retention(
    session: AsyncSession,
    query: CohortRetentionQuery,
) -> CohortRetentionResponse:
    """Cohort retention grid: membership-start month x months_since retention (ANL-02).

    cohort_months validated 1..COHORT_MAX_MONTHS → ValidationAppError otherwise.
    retention_pct = retained_count / cohort_size * 100 (guarded: cohort_size==0 → None).
    labels in Russian short format (e.g. 'янв 2026').
    max_offset = maximum months_since seen across all cohorts (0 if empty).

    Read-only: NO session.commit(), NO session.flush().
    Empty (no eligible memberships) → cohorts=[], max_offset=0.
    """
    if query.cohort_months < 1 or query.cohort_months > COHORT_MAX_MONTHS:
        raise ValidationAppError(
            f"cohort_months must be between 1 and {COHORT_MAX_MONTHS}, "
            f"got {query.cohort_months}"
        )

    rows = await repository.fetch_cohort_retention(session, query.cohort_months)

    if not rows:
        return CohortRetentionResponse(cohorts=[], max_offset=0)

    # Group flat rows into nested CohortEntry list.
    # Key: cohort_month (date object from Postgres date_trunc result).
    grouped: dict[date, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        cohort_month_raw = row["cohort_month"]
        cohort_month: date = (
            cohort_month_raw
            if isinstance(cohort_month_raw, date)
            else date.fromisoformat(str(cohort_month_raw))
        )
        grouped[cohort_month].append(row)

    cohort_entries: list[CohortEntry] = []
    max_offset = 0

    for cohort_month in sorted(grouped.keys()):
        month_rows = grouped[cohort_month]
        month_entries: list[CohortMonthEntry] = []

        for row in month_rows:
            offset = int(row["months_since"])  # type: ignore[call-overload]
            cohort_size = int(row["cohort_size"])  # type: ignore[call-overload]
            retained_count = int(row["retained_count"])  # type: ignore[call-overload]

            if offset > max_offset:
                max_offset = offset

            # Guard: cohort_size == 0 → retention_pct = None (never div-by-zero).
            retention_pct: float | None
            if cohort_size > 0:
                retention_pct = round(retained_count / cohort_size * 100, 1)
            else:
                retention_pct = None

            month_entries.append(CohortMonthEntry(offset=offset, retention_pct=retention_pct))

        cohort_entries.append(
            CohortEntry(
                cohort_month=cohort_month.strftime("%Y-%m"),
                label=_ru_month_label(cohort_month),
                months=sorted(month_entries, key=lambda e: e.offset),
            )
        )

    return CohortRetentionResponse(cohorts=cohort_entries, max_offset=max_offset)


async def get_visit_anomaly(
    session: AsyncSession,
    query: VisitAnomalyQuery,
) -> VisitAnomalyResponse:
    """Visit-anomaly daily series with >sigma deviation flagging (ANL-02).

    Date range defaults to last ANOMALY_LOOKBACK_DAYS days (MSK today) when
    from_date/to_date are None.  Range validated: to >= from.
    Gap-fills sparse repo output into a contiguous daily series (count=0 for missing days).
    _compute_anomaly flags days deviating > ANOMALY_SIGMA from the trailing
    ANOMALY_WINDOW_DAYS rolling mean.  std==0 → no anomaly (guarded).

    Read-only: NO session.commit(), NO session.flush().
    Empty range or no visits → points=[], anomaly_count=0.
    Fewer than ANOMALY_WINDOW_DAYS preceding points → no anomalies (insufficient baseline).
    """
    today = _msk_today()

    # Resolve date range.
    from_date: date = query.from_date if query.from_date is not None else (
        today - timedelta(days=ANOMALY_LOOKBACK_DAYS - 1)
    )
    to_date: date = query.to_date if query.to_date is not None else today

    _validate_date_range(from_date, to_date)

    # Fetch sparse daily counts from repository.
    raw_rows = await repository.fetch_visit_anomaly_daily(session, from_date, to_date)

    # Build lookup: date → count.
    count_map: dict[date, int] = {}
    for row in raw_rows:
        d_raw = row["d"]
        d: date = d_raw if isinstance(d_raw, date) else date.fromisoformat(str(d_raw))
        count_map[d] = int(row["cnt"])  # type: ignore[call-overload]

    # Gap-fill contiguous daily series.
    daily: list[dict[str, int]] = []
    cur = from_date
    while cur <= to_date:
        daily.append({"date": cur, "count": count_map.get(cur, 0)})  # type: ignore[dict-item]
        cur += timedelta(days=1)

    # Compute anomaly flags.
    flagged = _compute_anomaly(daily, ANOMALY_WINDOW_DAYS, ANOMALY_SIGMA)
    anomaly_count = sum(1 for p in flagged if p["is_anomaly"])

    points = [
        VisitAnomalyPoint(
            date=str(p["date"]),
            count=cast(int, p["count"]),
            is_anomaly=bool(p["is_anomaly"]),
            direction=cast("Literal['spike', 'drop'] | None", p["direction"]),
            label=str(p["label"]),
        )
        for p in flagged
    ]

    return VisitAnomalyResponse(
        points=points,
        window_days=ANOMALY_WINDOW_DAYS,
        sigma_threshold=ANOMALY_SIGMA,
        anomaly_count=anomaly_count,
    )


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

    IMPORTANT: filters must be validated BEFORE calling this generator (by the route
    handler via validate_audit_filters). Validation cannot live inside the generator body
    because async generator bodies only execute on first iteration — after headers are
    already sent in the StreamingResponse phase, too late for exception handlers.

    from_/to are keyword-only args from route-level Query(alias=...) params (not model
    fields on AuditLogQuery — live-verified pattern from Plan 01).

    Each row: [createdAt(MSK), actorUserId, actorEmailSnapshot, action, resourceType,
               resourceId, payload(compact JSON)].

    Yields:
        list[object]: One row per AuditLog entry in created_at DESC, id DESC order.

    Read-only: NO session.commit(), NO session.flush().
    """
    async for row in repository.stream_audit_log_rows(session, query, from_=from_, to=to):
        # actor_email_snapshot and payload are attacker-influenced free text — guard
        # against spreadsheet formula injection (CR-01). action/resource_type are
        # LOCKED_AUDIT_EVENTS enum values and UUIDs/dates are machine-formatted, so
        # they need no sanitization.
        yield [
            csv_export.format_datetime_msk(row.created_at),
            str(row.actor_user_id) if row.actor_user_id is not None else "",
            csv_export.sanitize_csv_text(row.actor_email_snapshot or ""),
            row.action,
            row.resource_type,
            str(row.resource_id) if row.resource_id is not None else "",
            csv_export.sanitize_csv_text(
                json.dumps(row.payload, ensure_ascii=False, separators=(",", ":"))
            ),
        ]
