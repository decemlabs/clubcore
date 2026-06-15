"""Reports module DTOs (Phase 55 REV-01..05, CLR-01..04, VIS-R-01..04; Phase 56 AUD-01..06).

Schema conventions:
  - Query DTOs extend ``BackendSchemaBase`` (extra='forbid', alias_generator=to_camel,
    validate_by_name + validate_by_alias). NOT PageQuery — reports are aggregates,
    not paginated lists (D-11).
  - Exception: AuditLogQuery extends PageQuery (D-07) — audit-log is a paginated list.
  - Response DTOs extend ``ResponseData`` (ContractModel, permissive outbound).
  - Wire form is camelCase; Python is snake_case.
  - Money stays integer kopecks in all API responses (REV-05).
  - All date bucketing is deterministic in Europe/Moscow.

Wire format for query params (FastAPI + Pydantic v2 alias_generator=to_camel behavior):
  - ``from_date`` -> ``?fromDate=YYYY-MM-DD``
  - ``to_date``   -> ``?toDate=YYYY-MM-DD``
  - ``group_by``  -> ``?groupBy=day|month``
  - ``within``    -> ``?within=N`` (no camelCase needed, single word)

  Note: ``alias="from"`` + ``Field(alias=...)`` does NOT work with FastAPI ``Depends()``
  for query params — FastAPI uses field names / alias_generator for param names, not
  explicit aliases. Using BackendSchemaBase (alias_generator=to_camel) causes
  ``from_date`` -> ``fromDate`` as the query param name.

  For AuditLogQuery, the ``from``/``to`` date params are NOT model fields at all —
  they are declared as route-level ``Query(alias="from")``/``Query(alias="to")``
  parameters (live-verified; Field(alias=...) does not bind ?from= via Depends()).

Decisions implemented:
  D-01: Nested bucket shape (byMethod, bySubjectKind). refundKopecks NOT added —
        net-only per D-01 default; refunds fold into netKopecks via signed sums.
  D-03: group_by Literal["day","month"], default "day".
  D-05: from_date/to_date required for revenue and visits; within optional default 7.
  D-07: within validated ge=1, le=30, default 7.
  D-09: Visits response is composite (daily + hourly + averagePerDay).
  D-10: averagePerDay is a float (raw ratio — frontend owns formatting).
  D-11: Aggregates, not lists — no PaginatedData/PageQuery (revenue/clients/visits).
  D-07 (AUD): AuditLogQuery extends PageQuery; page=1, pageSize=20, max 100.
  D-09 (AUD): AuditLogItem exposes full payload JSONB (owner-only resource).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from app.core.pagination import PageQuery
from app.core.schemas import BackendSchemaBase, ResponseData
from app.modules.reports.constants import (
    COHORT_DEFAULT_MONTHS,
    TRAINER_REPORT_REVENUE_NOTE,
)

# ---------------------------------------------------------------------------
# Revenue report DTOs (REV-01..05)
# ---------------------------------------------------------------------------


class RevenueReportQuery(BackendSchemaBase):
    """GET /api/v1/reports/revenue query parameters (REV-01..05).

    Wire: ?fromDate=2026-01-01&toDate=2026-05-31&groupBy=day
    (alias_generator=to_camel maps from_date->fromDate, to_date->toDate)
    """

    from_date: date
    to_date: date
    group_by: Literal["day", "month"] = "day"


class RevenueBucketByMethod(ResponseData):
    """Net kopecks split by payment method for a single period bucket."""

    cash: int = 0
    online: int = 0


class RevenueBucketBySubjectKind(ResponseData):
    """Net kopecks split by subject kind for a single period bucket.

    Only positive sale kinds appear here. Refunds are folded into
    netKopecks on the parent RevenueBucket but not broken out here (D-01).
    """

    membership: int = 0
    pt_package: int = 0


class RevenueBucket(ResponseData):
    """Aggregated revenue for a single period (day or month)."""

    period: str  # "2026-05-01" (groupBy=day) or "2026-05" (groupBy=month)
    net_kopecks: int  # signed sum including refunds (REV-04)
    by_method: RevenueBucketByMethod
    by_subject_kind: RevenueBucketBySubjectKind


class RevenueReportResponse(ResponseData):
    """Revenue report payload wrapped by ResponseEnvelope[RevenueReportResponse]."""

    buckets: list[RevenueBucket]
    from_date: date
    to_date: date
    group_by: Literal["day", "month"]


# ---------------------------------------------------------------------------
# Clients report DTOs (CLR-01..04)
# ---------------------------------------------------------------------------


class ClientsReportQuery(BackendSchemaBase):
    """GET /api/v1/reports/clients query parameters (CLR-01..04).

    Wire: ?fromDate=2026-01-01&toDate=2026-05-31&within=7
    from_date/to_date scope the new-clients counter (CLR-03) only.
    Active/expiring counters are as-of-now (D-05).
    """

    from_date: date
    to_date: date
    within: int = 7  # D-07: 1..30, default 7; validated in service layer

    # Note: Pydantic ge/le on 'within' validated at service layer to return 422
    # via ValidationAppError (consistent with other report validations).


class ClientsReportResponse(ResponseData):
    """Clients report payload — flat counters (CLR-01..04)."""

    active_count: int  # active memberships, live clients (CLR-01)
    expiring_count: int  # expiring within `within` days (CLR-02)
    new_clients_count: int  # created_at in [from_date, to_date] (CLR-03)
    within_days: int  # echo of the `within` param


# ---------------------------------------------------------------------------
# Visits report DTOs (VIS-R-01..04)
# ---------------------------------------------------------------------------


class VisitsReportQuery(BackendSchemaBase):
    """GET /api/v1/reports/visits query parameters (VIS-R-01..04).

    Wire: ?fromDate=2026-01-01&toDate=2026-05-31
    """

    from_date: date
    to_date: date


class VisitsDailyBucket(ResponseData):
    """Visit count for a single gym_date (MSK)."""

    date: date
    count: int


class VisitsHourlyBucket(ResponseData):
    """Visit count for a single hour-of-day (0..23 MSK) across the full range."""

    hour: int
    count: int


class VisitsReportResponse(ResponseData):
    """Visits report payload — composite (daily + hourly + averagePerDay) (D-09)."""

    daily: list[VisitsDailyBucket]
    hourly: list[VisitsHourlyBucket]
    average_per_day: float  # total / calendar_days (D-10); raw float, frontend formats
    from_date: date
    to_date: date


# ---------------------------------------------------------------------------
# Audit-log DTOs (Phase 56 AUD-01..06)
# ---------------------------------------------------------------------------


class AuditLogQuery(PageQuery):
    """GET /api/v1/audit-log query params (D-05, D-07).

    Inherits page + page_size from PageQuery (defaults: page=1, pageSize=20, max 100).
    Wire: ?actorUserId=...&actorEmailSnapshot=...&resourceType=...&action=...&page=...&pageSize=...
    (alias_generator=to_camel inherited via PageQuery -> BackendSchemaBase -> ContractModel)

    IMPORTANT: ``from`` / ``to`` date bounds are NOT fields on this model.
    They are declared as explicit route-level ``Query(alias="from")`` /
    ``Query(alias="to")`` parameters on the handler (live-verified: Field(alias="from")
    on a Depends() model field does NOT bind the ``?from=`` query param on this
    FastAPI + Pydantic v2 stack). The service and repository receive them as
    keyword-only arguments (from_=..., to=...).
    """

    actor_user_id: UUID | None = None
    # max_length 254 = RFC 5321 max email length — bounds the ILIKE substring scan
    # cost on an owner-authenticated request (WR-02); pairs with WR-01 escaping.
    actor_email_snapshot: str | None = Field(default=None, max_length=254)
    resource_type: str | None = None
    action: str | None = None


class AuditLogItem(ResponseData):
    """Single audit-log row (D-09). Owner sees full payload including JSONB.

    Fields mirror AuditLog ORM columns (app.core.audit_models.AuditLog).
    Wire keys are camelCase via alias_generator=to_camel (ResponseData -> ContractModel).
    created_at serializes as ISO-8601 with timezone offset.
    """

    id: UUID
    created_at: datetime  # wire: createdAt (ISO-8601 with tz offset)
    actor_user_id: UUID | None  # wire: actorUserId
    actor_email_snapshot: str | None  # wire: actorEmailSnapshot
    action: str
    resource_type: str  # wire: resourceType
    resource_id: UUID | None  # wire: resourceId
    payload: dict[str, Any]


# ---------------------------------------------------------------------------
# Trainer-usage report DTOs (Phase 60 RPT-01..04)
# ---------------------------------------------------------------------------


class TrainerUsageReportQuery(BackendSchemaBase):
    """GET /api/v1/reports/trainers query parameters (RPT-01..04).

    Wire: ?fromDate=YYYY-MM-DD&toDate=YYYY-MM-DD
    (alias_generator=to_camel maps from_date->fromDate, to_date->toDate)

    Both fields are required — no defaults (period is always explicit per RPT-01).
    BackendSchemaBase provides extra='forbid' + alias_generator=to_camel.
    Do NOT use Field(alias=...) — incompatible with FastAPI Depends() for query params
    (schemas.py L18-22).
    """

    from_date: date
    to_date: date


class TrainerUsageRow(ResponseData):
    """Per-trainer aggregate row in the trainer-usage report (RPT-01..04).

    Field order mirrors CSV_TRAINER_USAGE_HEADERS for diffability (D-60-11).
    Money fields are integer kopecks (REV-05 / D-11).
    utilization_pct is None when 0 active|booked slots in the period (D-60-06).
    avg_revenue_per_session is None when session_count == 0.
    total_accrued_kopecks is signed to net clawbacks automatically (D-58-03 / D-60-05).
    trainer_name_snapshot: from trainers.full_name (NO is_active filter — PITFALL 11).
    """

    trainer_id: UUID  # wire: trainerId
    trainer_name_snapshot: str  # wire: trainerNameSnapshot
    session_count: int  # wire: sessionCount (non-cancelled pt_sessions)
    cancelled_session_count: int  # wire: cancelledSessionCount
    total_hours: float  # wire: totalHours; 0.0 when no booking-linked sessions (D-60-04)
    unique_client_count: int  # wire: uniqueClientCount (COUNT DISTINCT pt_packages.client_id)
    utilization_pct: float | None  # wire: utilizationPct; None = 0 active|booked slots (D-60-06)
    revenue_kopecks: int  # wire: revenueKopecks; attributed via pt_packages.trainer_id (D-58-21)
    avg_revenue_per_session: int | None  # wire: avgRevenuePerSession; None when session_count==0
    total_accrued_kopecks: int  # wire: totalAccruedKopecks; signed (D-58-03 clawbacks net out)
    total_paid_kopecks: int  # wire: totalPaidKopecks


class TrainerUsageReportResponse(ResponseData):
    """Trainer-usage report envelope (RPT-01..04).

    Non-paginated: single gym has O(10) trainers; no page/pageSize (D-60-09).
    revenue_attribution_note: sourced from constants.TRAINER_REPORT_REVENUE_NOTE
    (D-60-07 single source of truth for the double-count disclosure wording).
    """

    trainers: list[TrainerUsageRow]
    from_date: date
    to_date: date
    revenue_attribution_note: str = TRAINER_REPORT_REVENUE_NOTE


# ---------------------------------------------------------------------------
# Live gym-load DTOs (Phase 115 ANL-03, ANL-04)
# GET /api/v1/reports/load/now
# Wire: { count, asOf, windowMinutes }
# ---------------------------------------------------------------------------


class LoadNowResponse(ResponseData):
    """GET /api/v1/reports/load/now payload — rolling-window in-gym headcount (ANL-03).

    count: distinct clients with checked_in_at in the last window_minutes.
    as_of: server UTC timestamp of the query (wire: asOf).
    window_minutes: rolling window length used (wire: windowMinutes).

    Approximation: Visit model has only checked_in_at (no checkout column).
    Window = LOAD_NOW_WINDOW_MINUTES (≈ average session length).
    """

    count: int  # wire: count — non-negative distinct client count
    as_of: datetime  # wire: asOf — UTC server timestamp at query time
    window_minutes: int  # wire: windowMinutes — rolling window length in minutes


# ---------------------------------------------------------------------------
# Cohort retention DTOs (Phase 115 ANL-02)
# GET /api/v1/reports/cohort
# Wire: { cohorts: [{ cohortMonth, label, months: [{ offset, retentionPct }] }], maxOffset }
# ---------------------------------------------------------------------------


class CohortRetentionQuery(BackendSchemaBase):
    """GET /api/v1/reports/cohort query params (ANL-02).

    Wire: ?cohortMonths=6  (alias_generator=to_camel maps cohort_months -> cohortMonths)
    Service validates: 1 <= cohort_months <= COHORT_MAX_MONTHS.
    """

    cohort_months: int = COHORT_DEFAULT_MONTHS  # wire: cohortMonths


class CohortMonthEntry(ResponseData):
    """Per-offset retention point within a cohort (ANL-02).

    offset: months after cohort start (0 = cohort month itself).
    retention_pct: % of cohort with ≥1 visit in that month offset;
                   None when cohort_size == 0 (never div-by-zero).
    Wire: { offset, retentionPct }
    """

    offset: int  # wire: offset
    retention_pct: float | None  # wire: retentionPct


class CohortEntry(ResponseData):
    """Single cohort row — membership-start month + per-month retention points (ANL-02).

    cohort_month: 'YYYY-MM' — truncated membership start month (Europe/Moscow).
    label: short Russian label (e.g. 'янв 2026') for chart axes.
    months: ordered list of retention points, offset 0..N.
    Wire: { cohortMonth, label, months: [CohortMonthEntry] }
    """

    cohort_month: str  # wire: cohortMonth — 'YYYY-MM'
    label: str  # wire: label — short ru month label
    months: list[CohortMonthEntry]  # wire: months


class CohortRetentionResponse(ResponseData):
    """GET /api/v1/reports/cohort payload (ANL-02).

    cohorts: one entry per cohort month, ordered chronologically.
    max_offset: maximum months_since seen across all cohorts (0 when empty).
    Wire: { cohorts, maxOffset }
    """

    cohorts: list[CohortEntry]  # wire: cohorts
    max_offset: int  # wire: maxOffset


# ---------------------------------------------------------------------------
# Visit anomaly DTOs (Phase 115 ANL-02)
# GET /api/v1/reports/anomaly
# Wire: { points: [...VisitAnomalyPoint], windowDays, sigmaThreshold, anomalyCount }
# ---------------------------------------------------------------------------


class VisitAnomalyQuery(BackendSchemaBase):
    """GET /api/v1/reports/anomaly query params (ANL-02).

    Wire: ?fromDate=YYYY-MM-DD&toDate=YYYY-MM-DD
    Both default to None — service fills in last ANOMALY_LOOKBACK_DAYS MSK days.
    alias_generator=to_camel: from_date -> fromDate, to_date -> toDate.
    """

    from_date: date | None = None  # wire: fromDate
    to_date: date | None = None  # wire: toDate


class VisitAnomalyPoint(ResponseData):
    """Single daily observation in the anomaly series (ANL-02).

    date: 'YYYY-MM-DD' gym_date (MSK).
    count: visit count for that day.
    is_anomaly: True when |count - trailing_mean| > ANOMALY_SIGMA * trailing_std.
    direction: 'spike' (above mean) | 'drop' (below mean) | None (not anomalous).
    label: short Russian label (e.g. '12 июн') for chart tooltips.
    Wire: { date, count, isAnomaly, direction, label }
    """

    date: str  # wire: date — 'YYYY-MM-DD'
    count: int  # wire: count
    is_anomaly: bool  # wire: isAnomaly
    direction: Literal["spike", "drop"] | None  # wire: direction
    label: str  # wire: label — short ru day label


class VisitAnomalyResponse(ResponseData):
    """GET /api/v1/reports/anomaly payload (ANL-02).

    points: gap-filled daily series (contiguous, no missing days).
    window_days: trailing mean window used (ANOMALY_WINDOW_DAYS constant).
    sigma_threshold: sigma threshold used (ANOMALY_SIGMA constant).
    anomaly_count: number of flagged points in the series.
    Wire: { points, windowDays, sigmaThreshold, anomalyCount }
    """

    points: list[VisitAnomalyPoint]  # wire: points
    window_days: int  # wire: windowDays
    sigma_threshold: float  # wire: sigmaThreshold
    anomaly_count: int  # wire: anomalyCount


# ---------------------------------------------------------------------------
# At-risk members DTOs (Phase 115 ANL-02)
# GET /api/v1/reports/at-risk
# Wire: { count, items: [...AtRiskMember], thresholdDays }
# ---------------------------------------------------------------------------


class AtRiskMember(ResponseData):
    """Single at-risk member entry (ANL-02).

    client_id: UUID string (wire: clientId).
    name: full_name from clients table (wire: name).
    membership_type: membership plan name (wire: membershipType).
    last_visit_date: 'YYYY-MM-DD' of last check-in, None if never visited (wire: lastVisitDate).
    days_since_visit: integer days since last visit; AT_RISK_THRESHOLD_DAYS+1 used for
                      never-visited (service fills; wire: daysSinceVisit).
    last_visit_label: pre-formatted Russian string, e.g. '18 дней назад' or 'не посещал'
                      (wire: lastVisitLabel).
    Wire: { clientId, name, membershipType, lastVisitDate, daysSinceVisit, lastVisitLabel }
    """

    client_id: str  # wire: clientId
    name: str  # wire: name
    membership_type: str  # wire: membershipType
    last_visit_date: str | None  # wire: lastVisitDate — 'YYYY-MM-DD' or null
    days_since_visit: int  # wire: daysSinceVisit
    last_visit_label: str  # wire: lastVisitLabel — pre-formatted ru label


class AtRiskMembersResponse(ResponseData):
    """GET /api/v1/reports/at-risk payload (ANL-02).

    count: total at-risk clients (may exceed items if capped by AT_RISK_MAX_ITEMS).
    items: at-risk member list (capped at AT_RISK_MAX_ITEMS).
    threshold_days: threshold used (AT_RISK_THRESHOLD_DAYS constant).
    Wire: { count, items, thresholdDays }
    """

    count: int  # wire: count
    items: list[AtRiskMember]  # wire: items
    threshold_days: int  # wire: thresholdDays
