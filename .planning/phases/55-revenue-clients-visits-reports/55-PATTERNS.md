# Phase 55: Revenue + Clients + Visits Reports — Pattern Map

**Mapped:** 2026-05-24
**Files analyzed:** 9 new/modified files
**Analogs found:** 9 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/backend/app/modules/reports/router.py` | controller | request-response | `apps/backend/app/modules/payments/router.py` | exact |
| `apps/backend/app/modules/reports/service.py` | service | batch (read-only aggregation) | `apps/backend/app/modules/payments/service.py` | role-match (read shape differs) |
| `apps/backend/app/modules/reports/repository.py` | service | batch (raw-SQL aggregate) | `apps/backend/app/modules/online_payments/service.py:116-142` | exact (raw-SQL cross-module reader) |
| `apps/backend/app/modules/reports/schemas.py` | model | request-response | `apps/backend/app/modules/payments/schemas.py` | role-match |
| `apps/backend/app/modules/reports/constants.py` | utility | — | `apps/backend/app/modules/payments/constants.py` | exact |
| `apps/backend/app/api/v1/router.py` | route | request-response | itself (add one `include_router` call) | exact |
| `apps/backend/alembic/versions/0041_revenue_composite_index.py` | migration | — | `apps/backend/alembic/versions/0040_audit_log_report_indexes.py` | exact |
| `apps/backend/tests/integration/reports/conftest.py` | test | — | `apps/backend/tests/integration/payments/conftest.py` | role-match |
| `apps/backend/tests/integration/reports/test_reports_*.py` | test | request-response | `apps/backend/tests/integration/payments/test_payments_list.py` | exact |

---

## Pattern Assignments

### `apps/backend/app/modules/reports/router.py` (controller, request-response)

**Analog:** `apps/backend/app/modules/payments/router.py`

**Imports pattern** (lines 1-34 of payments/router.py):
```python
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
    RevenueReportQuery,
    RevenueReportResponse,
    ClientsReportQuery,
    ClientsReportResponse,
    VisitsReportQuery,
    VisitsReportResponse,
)

router = APIRouter()
```

**RBAC / auth pattern** (payments/router.py lines 38-57 — identical chokepoint for reports):
```python
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
    result = await service.get_revenue_report(session, query)
    return envelope(result)
```

Note: `_actor` convention (underscore-prefixed) signals the dependency is used for its side-effect (RBAC gate) not its return value — copy this exactly from payments/router.py line 45-47.

**Core route pattern** — three routes follow the same shape:
- `GET /revenue` — `RevenueReportQuery`, `RevenueReportResponse`, `(Action.VIEW, Resource.REPORTS)`
- `GET /clients` — `ClientsReportQuery`, `ClientsReportResponse`, same RBAC
- `GET /visits` — `VisitsReportQuery`, `VisitsReportResponse`, same RBAC

All three return `ResponseEnvelope[<ReportResponse>]`, NOT `ResponseEnvelope[PaginatedData[T]]` (aggregates, not lists — D-11).

**Error handling** — no try/except in route handlers; FastAPI's `_app_error_handler` (registered in `create_app`) converts `ValidationAppError` subclasses to 422 and `ForbiddenError` to 403 automatically. Validation errors from Pydantic query parsing (invalid `from`/`to`, `groupBy`, `within`) are raised as HTTP 422 by FastAPI natively. Custom 422 for business rules (`to < from`, range > 366 days, `within` out of 1..30) should be `ValidationAppError` subclasses raised from `service.py`.

---

### `apps/backend/app/modules/reports/repository.py` (service, batch raw-SQL aggregate)

**Analog:** `apps/backend/app/modules/online_payments/service.py` lines 116-142

**The canonical raw-SQL cross-module reader pattern** (online_payments/service.py:116-142):
```python
async def _read_membership_plan_or_raise(
    session: AsyncSession, plan_id: UUID
) -> tuple[int, str]:
    """Return (price_kopecks, name) for an alive membership_plans row.

    BLOCKER #3 — raw SQL `text()` SELECT against the membership_plans
    table (NO ORM import of MembershipPlan; preserves D-49-03 invariant
    and the .importlinter contract Plan 49-02 ships).

    Verified columns (apps/backend/app/modules/memberships/models.py:58-90):
      - id            PgUUID
      - name          varchar(120)
      - price_kopecks BigInteger
      - deleted_at    nullable timestamptz
    """
    row = (
        await session.execute(
            text(
                "SELECT id, price_kopecks, name FROM membership_plans "
                "WHERE id = :id AND deleted_at IS NULL"
            ),
            {"id": str(plan_id)},
        )
    ).mappings().one_or_none()
    if row is None:
        raise NotFoundError("membership_plan_not_found")
    return int(row["price_kopecks"]), str(row["name"])
```

**Imports pattern** for repository.py:
```python
from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reports.schemas import (
    RevenueReportQuery,
    ClientsReportQuery,
    VisitsReportQuery,
)
```

**Revenue aggregate reader** — adapt the `text()` + `.mappings().all()` pattern:
```python
async def fetch_revenue_buckets(
    session: AsyncSession,
    query: RevenueReportQuery,
) -> list[dict]:
    """Aggregate payments by period bucket, method, subject_kind.

    CROSS-MODULE READ — raw SQL text() only; NO ORM import of Payment.
    Verified columns (apps/backend/app/modules/payments/models.py:52-64):
      - amount_kopecks  Integer (signed; negative for subject_kind='refund')
      - method          Text ('cash' | 'online')
      - subject_kind    Text ('membership' | 'pt_package' | 'refund')
      - received_at     DateTime(timezone=True)  ← sole temporal column
    """
    period_expr = (
        "(received_at AT TIME ZONE 'Europe/Moscow')::date"
        if query.group_by == GRAIN_DAY
        else "date_trunc('month', (received_at AT TIME ZONE 'Europe/Moscow')::date)"
    )
    rows = (
        await session.execute(
            text(
                f"SELECT {period_expr} AS period, method, subject_kind, "
                "SUM(amount_kopecks) AS total_kopecks "
                "FROM payments "
                "WHERE (received_at AT TIME ZONE 'Europe/Moscow')::date "
                "    BETWEEN :from_date AND :to_date "
                "GROUP BY period, method, subject_kind "
                "ORDER BY period"
            ),
            {"from_date": query.from_date, "to_date": query.to_date},
        )
    ).mappings().all()
    return [dict(r) for r in rows]
```

**Visits aggregate readers** — two queries in one call (D-09 single payload):
```python
async def fetch_visits_daily(session: AsyncSession, from_date: date, to_date: date) -> list[dict]:
    """Daily visit counts from visits.gym_date (STORED MSK — filter directly, D-54).

    Verified columns (apps/backend/app/modules/visits/models.py:77-84):
      - gym_date      Date STORED GENERATED (checked_in_at AT TIME ZONE 'Europe/Moscow')::date
      - checked_in_at DateTime(timezone=True)
    """
    rows = (
        await session.execute(
            text(
                "SELECT gym_date AS date, COUNT(*) AS count "
                "FROM visits "
                "WHERE gym_date BETWEEN :from_date AND :to_date "
                "GROUP BY gym_date ORDER BY gym_date"
            ),
            {"from_date": from_date, "to_date": to_date},
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def fetch_visits_hourly(session: AsyncSession, from_date: date, to_date: date) -> list[dict]:
    """Hour-of-day visit distribution (Europe/Moscow) across the full range."""
    rows = (
        await session.execute(
            text(
                "SELECT EXTRACT(HOUR FROM checked_in_at AT TIME ZONE 'Europe/Moscow')::int AS hour, "
                "COUNT(*) AS count "
                "FROM visits "
                "WHERE gym_date BETWEEN :from_date AND :to_date "
                "GROUP BY hour ORDER BY hour"
            ),
            {"from_date": from_date, "to_date": to_date},
        )
    ).mappings().all()
    return [dict(r) for r in rows]
```

**Clients aggregate readers** — three counters use separate focused queries:
```python
async def fetch_active_memberships_count(session: AsyncSession) -> int:
    """Count active memberships excluding soft-deleted clients (CLR-01).

    Verified columns (apps/backend/app/modules/memberships/models.py:134):
      - status Text ('active' | 'expired' | 'cancelled' | 'frozen')
      - end_date Date
    Verified columns (apps/backend/app/modules/clients/models.py:58):
      - deleted_at nullable timestamptz (SoftDeleteMixin)
    """
    row = (
        await session.execute(
            text(
                "SELECT COUNT(*) AS cnt FROM memberships m "
                "JOIN clients c ON c.id = m.client_id "
                "WHERE m.status = 'active' AND c.deleted_at IS NULL"
            )
        )
    ).mappings().one()
    return int(row["cnt"])
```

**INVARIANTS enforced in this file (copy from scaffold docstring):**
- ZERO INSERT / UPDATE / DELETE in this file.
- NO ORM model imports from other modules.
- Each reader documents verified columns + source `file:line`.
- `.mappings().all()` for multi-row, `.mappings().one_or_none()` or `.mappings().one()` for scalars.

---

### `apps/backend/app/modules/reports/service.py` (service, read-only aggregation)

**Analog:** `apps/backend/app/modules/payments/service.py` (structure only — reports is read-only)

**Imports pattern:**
```python
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationAppError
from app.modules.reports import repository
from app.modules.reports.constants import GRAIN_DAY, GRAIN_MONTH
from app.modules.reports.schemas import (
    RevenueReportQuery,
    RevenueReportResponse,
    ClientsReportQuery,
    ClientsReportResponse,
    VisitsReportQuery,
    VisitsReportResponse,
)
```

**Validation guard pattern** (D-05, D-06, D-07) — raise `ValidationAppError` subclass:
```python
class ReportRangeTooLargeError(ValidationAppError):
    """Date range exceeds 366-day cap (D-06). Code locked by CONTEXT.md."""
    code = "report_range_too_large"
    status_code = 422


def _validate_date_range(from_date: date, to_date: date) -> None:
    if to_date < from_date:
        raise ValidationAppError("to must be >= from")
    if (to_date - from_date).days > 366:
        raise ReportRangeTooLargeError("Date range exceeds 366-day limit")
```

**Service function pattern** (read-only, no commit):
```python
async def get_revenue_report(
    session: AsyncSession,
    query: RevenueReportQuery,
) -> RevenueReportResponse:
    """Aggregate payments ledger by period bucket.

    Read-only: NO session.commit(), NO session.flush() (SVC001 gate does not apply).
    """
    _validate_date_range(query.from_date, query.to_date)
    rows = await repository.fetch_revenue_buckets(session, query)
    return _pivot_revenue_buckets(rows, query)
```

**No `session.commit()` anywhere in this file.** The SVC001 gate (AST walker at `tests/unit/test_service_commit_gate.py`) must never trigger on reports — no `# noqa: SVC001` marker needed, just genuinely no commits.

---

### `apps/backend/app/modules/reports/schemas.py` (model, request-response)

**Analog:** `apps/backend/app/modules/payments/schemas.py`

**Imports pattern** (payments/schemas.py lines 1-21):
```python
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field

from app.core.schemas import BackendSchemaBase, ResponseData
```

Note: reports query DTOs extend `BackendSchemaBase` directly (NOT `PageQuery` — D-11; aggregates have no pagination). Response DTOs extend `ResponseData`.

**Query DTO pattern** (adapt from PaymentListQuery):
```python
class RevenueReportQuery(BackendSchemaBase):
    """GET /api/v1/reports/revenue query parameters (REV-01..05).

    Wire: ?from=2026-01-01&to=2026-05-31&groupBy=day
    """
    from_date: date = Field(alias="from")
    to_date: date = Field(alias="to")
    group_by: Literal["day", "month"] = Field(default="day", alias="groupBy")
```

Note: `alias="from"` is needed because `from` is a Python keyword. `BackendSchemaBase` has `validate_by_name=True, validate_by_alias=True` so both `from_date` and `from` work as input.

**Response DTO pattern** — nested objects per D-01:
```python
class RevenueBucketByMethod(ResponseData):
    cash: int = 0        # net kopecks from method='cash' rows
    online: int = 0      # net kopecks from method='online' rows

class RevenueBucketBySubjectKind(ResponseData):
    membership: int = 0    # sum of subject_kind='membership' rows
    pt_package: int = 0    # sum of subject_kind='pt_package' rows

class RevenueBucket(ResponseData):
    period: str           # "2026-05-01" (day) or "2026-05" (month)
    net_kopecks: int      # signed sum including refunds
    by_method: RevenueBucketByMethod
    by_subject_kind: RevenueBucketBySubjectKind

class RevenueReportResponse(ResponseData):
    buckets: list[RevenueBucket]
    from_date: date
    to_date: date
    group_by: Literal["day", "month"]
```

Wire names (camelCase via `BackendSchemaBase.alias_generator=to_camel`):
- `net_kopecks` → `netKopecks`
- `by_method` → `byMethod`
- `by_subject_kind` → `bySubjectKind`
- `pt_package` → `ptPackage`
- `from_date` → `fromDate`
- `to_date` → `toDate`
- `group_by` → `groupBy`

**Clients response** — flat counters, no list:
```python
class ClientsReportQuery(BackendSchemaBase):
    from_date: date = Field(alias="from")
    to_date: date = Field(alias="to")
    within: int = Field(default=7, ge=1, le=30)  # D-07: 1..30, default 7

class ClientsReportResponse(ResponseData):
    active_count: int           # active memberships, live clients
    expiring_count: int         # expiring within `within` days
    new_clients_count: int      # created_at in [from_date, to_date]
    within_days: int            # echo of the `within` param
```

**Visits response** — composite (D-09):
```python
class VisitsDailyBucket(ResponseData):
    date: date
    count: int

class VisitsHourlyBucket(ResponseData):
    hour: int   # 0..23 MSK
    count: int

class VisitsReportQuery(BackendSchemaBase):
    from_date: date = Field(alias="from")
    to_date: date = Field(alias="to")

class VisitsReportResponse(ResponseData):
    daily: list[VisitsDailyBucket]
    hourly: list[VisitsHourlyBucket]
    average_per_day: float   # total_visits / calendar_days (D-10); 2dp or raw float
    from_date: date
    to_date: date
```

---

### `apps/backend/app/modules/reports/constants.py` (utility)

**Analog:** `apps/backend/app/modules/payments/constants.py`

**Pattern** (payments/constants.py lines 1-22):
```python
"""Reports module literal constants (Phase 55 REV-01..05, D-03).

Period-grain and subject-kind literals mirror D-03 and the payments
CHECK constraint ck_payments_subject_kind.
"""

GRAIN_DAY = "day"
GRAIN_MONTH = "month"
GRAIN_VALUES: tuple[str, ...] = (GRAIN_DAY, GRAIN_MONTH)

__all__ = (
    "GRAIN_DAY",
    "GRAIN_MONTH",
    "GRAIN_VALUES",
)
```

Planner should also add `SUBJECT_KIND_*` references if the pivot logic in service.py benefits — or import them directly from `reports.constants` by redefining them to avoid a cross-module ORM import.

---

### `apps/backend/app/api/v1/router.py` (route mount, modification)

**Analog:** itself — add one import + one `include_router` call.

**Import to add** (follow alphabetical import order, after `visits_router`):
```python
from app.modules.reports.router import router as reports_router
```

**Mount to add** (after the `visits_router` mount at line 76, before the `_internal` block):
```python
v1.include_router(reports_router, prefix="/reports", tags=["reports"])
```

**Full mount pattern context** (router.py lines 74-77 as reference):
```python
v1.include_router(trainers_router, prefix="/trainers", tags=["trainers"])
v1.include_router(users_router, prefix="/users", tags=["users"])
v1.include_router(visits_router, prefix="/visits", tags=["visits"])
# NEW Phase 55:
v1.include_router(reports_router, prefix="/reports", tags=["reports"])
```

---

### `apps/backend/alembic/versions/0041_revenue_composite_index.py` (migration, conditional)

**Only create this file if `EXPLAIN ANALYZE` on realistic fixture data shows a seq scan on the revenue aggregate that the existing `ix_payments_received_at` does not cover (D-13). Default = no new migration.**

**Analog:** `apps/backend/alembic/versions/0040_audit_log_report_indexes.py` (exact pattern)

**Pattern** (0040 lines 1-60):
```python
"""revenue composite index (Phase 55 D-13 EXPLAIN evidence).

Revision ID: 0041_revenue_composite_index
Revises: 0040_audit_log_report_indexes
Create Date: 2026-05-24 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0041_revenue_composite_index"
down_revision: str | None = "0040_audit_log_report_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Composite covering revenue aggregate GROUP BY (received_at, method, subject_kind).
    # Literal name + sa.text() for DESC column per 0034/0037/0040 precedent.
    op.create_index(
        "ix_payments_revenue_composite",
        "payments",
        [sa.text("received_at DESC"), "method", "subject_kind"],
    )


def downgrade() -> None:
    op.drop_index("ix_payments_revenue_composite", table_name="payments")
```

Key migration conventions (from 0040 + 0037):
- `revision` and `down_revision` are **literal strings**, not `op.f()`.
- DESC expressed via `sa.text("col DESC")` inside the column list.
- `down_revision` points at `0040_audit_log_report_indexes` (current Phase 54 head).
- `branch_labels = None`, `depends_on = None` (standard for sequential revisions).

---

### `apps/backend/tests/integration/reports/conftest.py` (test fixture)

**Analog:** `apps/backend/tests/integration/payments/conftest.py`

**Pattern** (payments/conftest.py lines 1-77):
```python
"""Shared fixtures for reports integration tests (Phase 55 REV/CLR/VIS-R)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payments.models import Payment
from app.modules.visits.models import Visit

# Re-export memberships package fixtures (owner / reception clients, factories).
from tests.integration.memberships.conftest import (  # noqa: F401
    _client_app_overrides,
    authed_client_owner,
    authed_client_reception,
    db_session_real_commit,
    make_client,
    make_membership,
    make_plan,
    make_user,
    redis_clean,
    seeded_owner,
    seeded_reception,
)


@pytest_asyncio.fixture
async def make_payment_ledger(db_session: AsyncSession) -> Callable[..., Awaitable[Payment]]:
    """Insert a Payment row with explicit received_at for deterministic date-window tests."""

    async def _make(
        *,
        subject_id: UUID,
        received_by_user_id: UUID,
        amount_kopecks: int,
        method: str = "cash",
        subject_kind: str = "membership",
        received_at: datetime,
    ) -> Payment:
        payment = Payment(
            subject_kind=subject_kind,
            subject_id=subject_id,
            amount_kopecks=amount_kopecks,
            method=method,
            received_by_user_id=received_by_user_id,
        )
        payment.received_at = received_at
        db_session.add(payment)
        await db_session.commit()
        await db_session.refresh(payment)
        return payment

    return _make
```

Note: must also provide a `make_visit` fixture inserting `visits` rows with explicit `checked_in_at` (timestamptz) for VIS-R tests. `gym_date` is STORED GENERATED so it is computed automatically by Postgres from `checked_in_at`.

---

### `apps/backend/tests/integration/reports/test_reports_*.py` (test files)

**Analog:** `apps/backend/tests/integration/payments/test_payments_list.py`

**Test file structure pattern** (test_payments_list.py lines 1-68):
```python
"""Integration tests for GET /api/v1/reports/revenue (Phase 55 REV-01..05).

Coverage:
  - Owner receives 200 with correct ResponseEnvelope[RevenueReportResponse] shape.
  - Reception receives 403 ((VIEW, REPORTS) ∈ OWNER_ONLY — owner-only).
  - Net revenue reconciles: sale + refund in same period = 0 (REV-04 canonical assertion).
  - groupBy=day buckets by MSK date; groupBy=month truncates to YYYY-MM.
  - to < from → 422.
  - range > 366 days → 422 report_range_too_large.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from httpx import AsyncClient

# ...

async def test_owner_gets_revenue_report(
    authed_client_owner: AsyncClient,
    ...
) -> None:
    r = await authed_client_owner.get(
        "/api/v1/reports/revenue",
        params={"from": "2026-05-01", "to": "2026-05-31", "groupBy": "day"},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert isinstance(body["buckets"], list)


async def test_reception_forbidden(authed_client_reception: AsyncClient) -> None:
    """(VIEW, REPORTS) ∈ OWNER_ONLY → reception receives 403."""
    r = await authed_client_reception.get(
        "/api/v1/reports/revenue",
        params={"from": "2026-05-01", "to": "2026-05-31"},
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"
```

**Canonical REV-04 correctness assertion** (net-of-refund, from CONTEXT specifics):
```python
async def test_net_revenue_zero_after_full_refund(
    authed_client_owner: AsyncClient,
    make_payment_ledger: Any,
    seeded_owner: Any,
    make_client: Any,
    make_membership: Any,
    make_plan: Any,
) -> None:
    """Sale + same-period refund must net to zero (REV-04)."""
    plan = await make_plan(name="NetZeroTest")
    cli = await make_client()
    mem = await make_membership(client_id=cli.id, plan=plan)
    msk_ts = datetime(2026, 5, 15, 10, 0, 0, tzinfo=UTC)  # well within test window
    await make_payment_ledger(
        subject_id=mem.id, amount_kopecks=250000, method="cash",
        received_at=msk_ts, received_by_user_id=seeded_owner.id,
    )
    await make_payment_ledger(
        subject_id=mem.id, amount_kopecks=-250000, method="cash",
        subject_kind="refund",
        received_at=msk_ts, received_by_user_id=seeded_owner.id,
    )
    r = await authed_client_owner.get(
        "/api/v1/reports/revenue",
        params={"from": "2026-05-01", "to": "2026-05-31"},
    )
    assert r.status_code == 200
    buckets = r.json()["data"]["buckets"]
    day_bucket = next(b for b in buckets if b["period"] == "2026-05-15")
    assert day_bucket["netKopecks"] == 0
```

---

## Shared Patterns

### Authentication / RBAC Gate
**Source:** `apps/backend/app/core/dependencies.py` + `apps/backend/app/core/permissions.py`
**Apply to:** `reports/router.py` — all three route handlers
```python
_actor: Annotated[
    CurrentUser, Depends(require_permission(Action.VIEW, Resource.REPORTS))
]
```
`(Action.VIEW, Resource.REPORTS)` is already in `OWNER_ONLY` (permissions.py line 65). Reception → 403 automatically. No new RBAC work this phase.

### Response Envelope
**Source:** `apps/backend/app/core/schemas.py` lines 60-82
**Apply to:** All three router handlers and their response_model declarations
```python
from app.core.schemas import ResponseEnvelope, envelope

# In route handler:
return envelope(result)  # wraps payload in ResponseEnvelope(data=result)
```
Reports use `ResponseEnvelope[<ReportResponseType>]`, NOT `ResponseEnvelope[PaginatedData[T]]`.

### BackendSchemaBase for Query DTOs
**Source:** `apps/backend/app/core/schemas.py` lines 36-53
**Apply to:** `RevenueReportQuery`, `ClientsReportQuery`, `VisitsReportQuery`
```python
class BackendSchemaBase(ContractModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        extra="forbid",
    )
```
All query DTOs inherit `extra='forbid'` (unknown query params → 422) and auto-camelCase wire. Use `Field(alias="from")` for the `from` param since it is a Python keyword.

### ResponseData for Response DTOs
**Source:** `apps/backend/app/core/schemas.py` lines 56-57
**Apply to:** All `*Response` and nested bucket DTOs
```python
class ResponseData(ContractModel):
    """Payload inside ResponseEnvelope. Subclassed by every domain response DTO."""
```
`ContractModel` has `extra="ignore"` (permissive outbound), `from_attributes=True` (ORM-compatible), camelCase alias.

### Raw-SQL Cross-Module Read Discipline
**Source:** `apps/backend/app/modules/online_payments/service.py` lines 116-142
**Apply to:** All reader functions in `reports/repository.py`
Rules:
1. `from sqlalchemy import text` — only import; zero ORM model imports from other modules.
2. Bind params via `:name` placeholders + a plain dict (no f-string interpolation of user values).
3. `.mappings().all()` for multi-row aggregate results; `.mappings().one()` for scalar counts.
4. Each function docstring documents `Verified columns (path/to/models.py:line_range)`.
5. Zero INSERT / UPDATE / DELETE anywhere in the file.

### Error Handling
**Source:** `apps/backend/app/core/exceptions.py` lines 7-51
**Apply to:** `reports/service.py` — input validation guards
```python
from app.core.exceptions import ValidationAppError

class ReportRangeTooLargeError(ValidationAppError):
    code = "report_range_too_large"  # LOCKED per CONTEXT.md D-06
    status_code = 422
```
No try/except in router handlers — AppError subclasses bubble to the registered `_app_error_handler`.

### `from __future__ import annotations`
**Source:** All backend module files (universal project pattern)
**Apply to:** All new Python files — first line after module docstring.

### Integer Kopecks End-to-End
**Source:** CLAUDE.md money convention + payments/schemas.py
**Apply to:** `RevenueReportResponse` — all monetary fields are `int` (kopecks), never `float`.
The `SUM(amount_kopecks)` from the SQL aggregate is cast with `int(row["total_kopecks"])` in Python.

### Europe/Moscow Date Discipline
**Source:** `apps/backend/app/modules/visits/models.py` lines 77-84 + CONTEXT.md D-04
**Apply to:** All SQL in `reports/repository.py`
- `visits.gym_date` is STORED MSK: filter directly via `gym_date BETWEEN :from_date AND :to_date`.
- `payments.received_at` is timestamptz: convert in SQL via `(received_at AT TIME ZONE 'Europe/Moscow')::date`.
- `checked_in_at` hour extraction: `EXTRACT(HOUR FROM checked_in_at AT TIME ZONE 'Europe/Moscow')`.
- Never do TZ math in Python for these conversions — always in SQL.

---

## Source Table Column Reference (for repository.py docstrings)

### `payments` table
**Source:** `apps/backend/app/modules/payments/models.py` lines 44-121
| Column | Type | Notes |
|---|---|---|
| `id` | PgUUID | PK |
| `subject_kind` | Text | `'membership'` \| `'pt_package'` \| `'refund'` (CHECK) |
| `subject_id` | PgUUID | FK to subject row |
| `amount_kopecks` | Integer | signed (negative for refund, positive for sale — CHECK) |
| `method` | Text | `'cash'` \| `'online'` |
| `received_at` | DateTime(timezone=True) | sole temporal column (D-32-01..04) |
| `ix_payments_received_at` | Index | `received_at DESC` — already exists, used by revenue query |

### `visits` table
**Source:** `apps/backend/app/modules/visits/models.py` lines 43-113
| Column | Type | Notes |
|---|---|---|
| `id` | PgUUID | PK |
| `client_id` | PgUUID | FK clients |
| `gym_date` | Date | STORED GENERATED `(checked_in_at AT TIME ZONE 'Europe/Moscow')::date` |
| `checked_in_at` | DateTime(timezone=True) | raw timestamptz; use for hour extraction |
| `ix_visits_client_id_checked_in_at` | Index | — |

### `memberships` table
**Source:** `apps/backend/app/modules/memberships/models.py` lines 107-185
| Column | Type | Notes |
|---|---|---|
| `client_id` | PgUUID | FK clients |
| `status` | String(16) | `'active'` \| `'expired'` \| `'cancelled'` \| `'frozen'` |
| `end_date` | Date | inclusive end; CLR-02 expiring filter: `end_date BETWEEN now()::date AND now()::date + N` |
| `ix_memberships_client_id_status_end_date` | Index | covers active/expiring queries |

### `clients` table
**Source:** `apps/backend/app/modules/clients/models.py` lines 58-120
| Column | Type | Notes |
|---|---|---|
| `id` | PgUUID | PK |
| `created_at` | DateTime(timezone=True) | from TimestampMixin — used for CLR-03 new-clients count |
| `deleted_at` | nullable DateTime(timezone=True) | from SoftDeleteMixin — CLR-04: exclude `deleted_at IS NOT NULL` |

---

## No Analog Found

All files have close analogs. No entries in this section.

---

## Metadata

**Analog search scope:** `apps/backend/app/modules/`, `apps/backend/app/core/`, `apps/backend/app/api/`, `apps/backend/alembic/versions/`, `apps/backend/tests/integration/`
**Files scanned:** 18
**Pattern extraction date:** 2026-05-24
