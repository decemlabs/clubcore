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

from app.core.pagination import PageQuery
from app.core.schemas import BackendSchemaBase, ResponseData

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
    actor_email_snapshot: str | None = None
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
