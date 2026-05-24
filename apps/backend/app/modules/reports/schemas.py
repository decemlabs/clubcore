"""Reports module DTOs (Phase 55 REV-01..05, CLR-01..04, VIS-R-01..04).

Schema conventions:
  - Query DTOs extend ``BackendSchemaBase`` (extra='forbid', camelCase alias,
    validate_by_name + validate_by_alias). NOT PageQuery — reports are aggregates,
    not paginated lists (D-11).
  - Response DTOs extend ``ResponseData`` (ContractModel, permissive outbound).
  - Wire form is camelCase; Python is snake_case.
  - Money stays integer kopecks in all API responses (REV-05).
  - All date bucketing is deterministic in Europe/Moscow.

Decisions implemented:
  D-01: Nested bucket shape (byMethod, bySubjectKind). refundKopecks NOT added —
        net-only per D-01 default; refunds fold into netKopecks via signed sums.
  D-03: group_by Literal["day","month"], default "day".
  D-05: from/to required for revenue and visits; within optional with default 7.
  D-07: within validated ge=1, le=30, default 7.
  D-09: Visits response is composite (daily + hourly + averagePerDay).
  D-10: averagePerDay is a float (raw ratio — frontend owns formatting).
  D-11: Aggregates, not lists — no PaginatedData/PageQuery.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field

from app.core.schemas import BackendSchemaBase, ResponseData

# ---------------------------------------------------------------------------
# Revenue report DTOs (REV-01..05)
# ---------------------------------------------------------------------------


class RevenueReportQuery(BackendSchemaBase):
    """GET /api/v1/reports/revenue query parameters (REV-01..05).

    Wire: ?from=2026-01-01&to=2026-05-31&groupBy=day
    """

    from_date: date = Field(alias="from")
    to_date: date = Field(alias="to")
    group_by: Literal["day", "month"] = Field(default="day", alias="groupBy")


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

    Wire: ?from=2026-01-01&to=2026-05-31&within=7
    from/to scope the new-clients counter (CLR-03) only.
    Active/expiring counters are as-of-now (D-05).
    """

    from_date: date = Field(alias="from")
    to_date: date = Field(alias="to")
    within: int = Field(default=7, ge=1, le=30)  # D-07: 1..30, default 7


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

    Wire: ?from=2026-01-01&to=2026-05-31
    """

    from_date: date = Field(alias="from")
    to_date: date = Field(alias="to")


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
