# Phase 60: Trainer-Usage Report — Pattern Map

**Mapped:** 2026-05-25
**Files analyzed:** 7 (6 module files + 1 test file)
**Analogs found:** 7/7 (all exact role+data-flow matches inside `apps/backend/app/modules/reports/`)

> All analogs verified by `Read` on the working tree. Every new symbol in
> Phase 60 has a 1:1 sibling in the existing reports module (Phase 55 REV +
> Phase 56 AUD/EXP). This phase is an EXTENSION — no greenfield idioms.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/backend/app/modules/reports/repository.py` (ADD `fetch_trainer_usage`) | repository (raw-SQL reader) | request-response, read-only aggregate | `fetch_revenue_buckets` (L56–93) + `fetch_audit_log_page` (L293–337) | exact (same module, same discipline) |
| `apps/backend/app/modules/reports/schemas.py` (ADD `TrainerUsageRow` + `TrainerUsageReportResponse`) | DTO / schema | request-response | `RevenueReportQuery` (L57–66) + `RevenueReportResponse` (L96–102) | exact |
| `apps/backend/app/modules/reports/service.py` (ADD `get_trainer_usage_report`) | service orchestrator | request-response, read-only | `get_revenue_report` (L164–174) + `get_clients_report` (L177–211) | exact |
| `apps/backend/app/modules/reports/router.py` (ADD `GET /trainers` + `GET /trainers.csv`) | router (FastAPI endpoint) | request-response (JSON) + streaming (CSV) | `get_revenue_report` route (L61–82) + `get_revenue_csv` route (L143–165) | exact |
| `apps/backend/app/modules/reports/csv_export.py` (ADD per-row trainer-usage builder OR keep in `service.trainer_usage_csv_rows`) | utility (CSV row builder) | streaming | `revenue_csv_rows` in `service.py` (L339–362) — note: row builders live in `service.py`, NOT `csv_export.py` | exact (clarifies CONTEXT mis-placement) |
| `apps/backend/app/modules/reports/constants.py` (ADD `TRAINER_REPORT_REVENUE_NOTE` + `CSV_TRAINER_USAGE_HEADERS`) | config / constants | n/a | `CSV_REVENUE_HEADERS` (L30–37) | exact |
| `apps/backend/tests/integration/reports/test_trainer_usage.py` (NEW) | test (integration) | request-response | `test_reports_revenue.py` (full file) + CSV portions of `test_csv_export.py` (L58–105, L239–256, L473–501) | exact |

> **Important reclassification (vs. CONTEXT.md):** CONTEXT lists
> `csv_export.py` as gaining the per-row builder, but the working tree shows
> the row builders live in `service.py` (`revenue_csv_rows`,
> `clients_csv_rows`, `visits_csv_rows` — see `service.py:339-401`).
> `csv_export.py` only contains the generic streaming helpers + formatters
> (`make_csv_streaming_response`, `format_kopecks_as_rubles`,
> `sanitize_csv_text`). The new function SHOULD land as
> `trainer_usage_csv_rows` in `service.py` to match the established
> precedent. `csv_export.py` itself does NOT need edits.

> **Test filename:** CONTEXT shows `test_trainer_usage.py` — existing tests
> use the `test_reports_*` prefix (`test_reports_revenue.py`,
> `test_reports_clients.py`, `test_reports_visits.py`). Recommend
> `test_reports_trainers.py` for consistency. Either name works; planner
> picks. CSV-specific tests may either live in this file or be added to
> `test_csv_export.py` (which already centralizes all four CSV endpoints).

---

## Pattern Assignments

### 1. `repository.py` — ADD `fetch_trainer_usage`

**Role:** repository (raw-SQL cross-module reader)
**Data flow:** request-response, read-only aggregate
**Primary analog:** `fetch_revenue_buckets` at `apps/backend/app/modules/reports/repository.py:56-93`
**Secondary analog (CTE-with-comments shape, scalar consumption):** `fetch_audit_log_page` at `apps/backend/app/modules/reports/repository.py:293-337`

**Imports pattern** (file header, L29–53):
```python
from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from typing import Any

from sqlalchemy import and_, cast, func, select, text, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import Date

from app.core.audit_models import AuditLog  # core is free import target (D-04 / Phase 56)
from app.core.pagination import PaginatedData
from app.modules.reports.constants import GRAIN_DAY
from app.modules.reports.schemas import AuditLogQuery, RevenueReportQuery
```
**What to mimic:** Only `text` + `AsyncSession` are needed for the new
reader. Do NOT add a new `from app.modules.<other>...` import — that would
trigger PITFALL 10 (D-60-01). Add `fetch_trainer_usage` to `__all__`.

**Core pattern — raw-SQL CTE reader** (L56–93):
```python
async def fetch_revenue_buckets(
    session: AsyncSession,
    query: RevenueReportQuery,
) -> list[dict[str, object]]:
    """Aggregate payments by period bucket, method, subject_kind.

    CROSS-MODULE READ — raw SQL text() only; NO ORM import of Payment.
    Verified columns (apps/backend/app/modules/payments/models.py:52-64):
      - amount_kopecks  Integer (signed; negative for subject_kind='refund')
      - method          Text ('cash' | 'online')
      - subject_kind    Text ('membership' | 'pt_package' | 'refund')
      - received_at     DateTime(timezone=True)  <- sole temporal column

    Security (T-55-02): period_expr is chosen from an internal branch keyed on
    the validated Literal["day","month"] enum — NEVER from a raw user string.
    All user values (from_date, to_date) go through :from_date / :to_date bind
    params only. No f-string interpolation of user input.
    """
    period_expr = (
        "(received_at AT TIME ZONE 'Europe/Moscow')::date"
        if query.group_by == GRAIN_DAY
        else "date_trunc('month', (received_at AT TIME ZONE 'Europe/Moscow')::date)"
    )
    rows = (
        await session.execute(
            text(
                f"SELECT {period_expr} AS period, method, subject_kind, "  # noqa: S608 ...
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

**What to mimic:**
- `async def fetch_trainer_usage(session: AsyncSession, from_date: date, to_date: date) -> list[dict[str, object]]:` (positional date params, NOT a query object — matches `fetch_new_clients_count` (L150–175) / `fetch_visits_daily` (L178–203) precedent; `RevenueReportQuery` is passed only when the query also carries `group_by`).
- Single `await session.execute(text("..."), {"from_date": ..., "to_date": ...})`.
- `.mappings().all()` then `[dict(r) for r in rows]` return shape.
- Docstring header MUST enumerate every foreign table + verified column with file:line, mirroring L62–73 — required by D-54-08.

**Period-filter idiom** (verbatim, from L84–86):
```python
"WHERE (received_at AT TIME ZONE 'Europe/Moscow')::date "
"    BETWEEN :from_date AND :to_date "
```
Use the same `AT TIME ZONE 'Europe/Moscow'` truncation for `ps.performed_at`, `s.start_time`, and `p.paid_at`. PITFALL 12 (period-boundary inclusivity) is satisfied by `BETWEEN :from_date AND :to_date` (inclusive on both ends).

**Per-D-60 caveats specific to `fetch_trainer_usage`:**
- **PITFALL 10:** NEVER import `from app.modules.pt_sessions.models import …`, `from app.modules.payroll.models import …`, etc. Only `text()`. The plan MUST include a grep guard.
- **PITFALL 11:** `LEFT JOIN trainers t … ORDER BY session_count DESC, t.full_name ASC` — NO `WHERE t.is_active` filter, NO `WHERE t.deleted_at IS NULL` filter. Deactivated trainers with historical sessions MUST appear in the report.
- **PITFALL 6:** Revenue CTE attribution key is `pt_packages.trainer_id` (assigned-at-sale, D-58-21), NOT `pt_sessions.trainer_id` (conducting). Document this with an inline SQL comment.
- **D-60-04 total_hours:** `LEFT JOIN bookings b ON b.id = ps.booking_id` and `LEFT JOIN trainer_availability_slots s ON s.id = b.slot_id` — sessions without a `booking_id` get `0.0` hours via `COALESCE(SUM(...), 0.0)` (the `EXTRACT(EPOCH FROM (NULL - NULL))` collapses to NULL which `SUM` ignores; documented behavior, not fabricated).
- **D-60-05 payroll overlap:** `WHERE period_start <= :to_date AND period_end >= :from_date` — signed `SUM(accrual_kopecks)` nets RPT-04 clawbacks automatically (no `WHERE accrual_kopecks > 0`).
- **D-60-06 utilization_pct:** `CASE WHEN COALESCE(sla.published_slot_count, 0) = 0 THEN NULL ELSE … END` — explicit NULL when no `active|booked` slots in the period; `0.0` when slots exist but none are booked.

---

### 2. `schemas.py` — ADD `TrainerUsageRow` + `TrainerUsageReportResponse`

**Role:** DTO / schema (Pydantic v2)
**Data flow:** request-response
**Primary analog:** `RevenueReportQuery` + `RevenueReportResponse` at `apps/backend/app/modules/reports/schemas.py:57-102`

**Imports pattern** (file header, L41–50):
```python
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from app.core.pagination import PageQuery
from app.core.schemas import BackendSchemaBase, ResponseData
```

**Query DTO pattern** (L57–66):
```python
class RevenueReportQuery(BackendSchemaBase):
    """GET /api/v1/reports/revenue query parameters (REV-01..05).

    Wire: ?fromDate=2026-01-01&toDate=2026-05-31&groupBy=day
    (alias_generator=to_camel maps from_date->fromDate, to_date->toDate)
    """

    from_date: date
    to_date: date
    group_by: Literal["day", "month"] = "day"
```

**Response DTO pattern** (L87–102):
```python
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
```

**What to mimic:**
- Query DTO extends `BackendSchemaBase` (gives `extra='forbid'` + `alias_generator=to_camel`).
- Row + envelope DTOs extend `ResponseData`.
- Snake_case fields → camelCase wire form is automatic via `alias_generator=to_camel`. NO explicit `Field(alias=...)` per the schemas.py L18–22 note ("Field(alias=...) does NOT work with FastAPI Depends() for query params").
- Money fields stay `int` kopecks (REV-05 / D-11 — server-side rubles ONLY in CSV).
- The note string lives on the envelope as a typed field with a Pydantic default sourced from `constants.TRAINER_REPORT_REVENUE_NOTE` (D-60-07).

**New shape (D-60-07, D-60-03):**
```python
class TrainerUsageReportQuery(BackendSchemaBase):
    from_date: date
    to_date: date


class TrainerUsageRow(ResponseData):
    trainer_id: UUID
    trainer_name_snapshot: str       # from trainers.full_name (NOT t.is_active filtered)
    session_count: int
    cancelled_session_count: int
    total_hours: float               # 0.0 when no booking-linked sessions (D-60-04)
    unique_client_count: int
    utilization_pct: float | None    # None when 0 active|booked slots (D-60-06)
    revenue_kopecks: int             # attributed via pt_packages.trainer_id (D-58-21)
    avg_revenue_per_session: int | None  # None when session_count == 0
    total_accrued_kopecks: int       # signed (D-58-03 / D-60-05)
    total_paid_kopecks: int


class TrainerUsageReportResponse(ResponseData):
    trainers: list[TrainerUsageRow]
    from_date: date
    to_date: date
    revenue_attribution_note: str    # from constants.TRAINER_REPORT_REVENUE_NOTE
    # Optional per D-60 Claude's-discretion: methodology_note: str, payroll_period_match_note: str
```

**Per-D-60 caveats:**
- `utilization_pct: float | None` — Pydantic must serialize `None` as JSON `null`, NOT as `0`. Confirm with a golden test.
- `avg_revenue_per_session: int | None` — int (kopecks), not float; `None` when session_count == 0 (D-60-03 SQL: `CASE WHEN session_count = 0 THEN NULL ELSE ... END`).
- NO `total_count`/`page`/`pageSize` envelope — single-shot non-paginated (D-60-09 / matches `RevenueReportResponse` precedent).
- The `revenue_attribution_note` default value MUST be sourced from
  `app.modules.reports.constants.TRAINER_REPORT_REVENUE_NOTE` (NOT a string
  literal inline) so the constant is the single source of truth (D-60-07).

---

### 3. `service.py` — ADD `get_trainer_usage_report` + `trainer_usage_csv_rows`

**Role:** service orchestrator
**Data flow:** request-response, read-only
**Primary analog:** `get_revenue_report` at `apps/backend/app/modules/reports/service.py:164-174` (thin orchestrator) + `revenue_csv_rows` at `service.py:339-362` (CSV row builder)

**Imports pattern** (file header, L16–44):
```python
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
    # ... AuditLogItem, AuditLogQuery, ClientsReportQuery, ClientsReportResponse,
    # RevenueBucket, RevenueBucketByMethod, RevenueBucketBySubjectKind,
    # RevenueReportQuery, RevenueReportResponse,
    # VisitsDailyBucket, VisitsHourlyBucket, VisitsReportQuery, VisitsReportResponse,
)
```

**Validation helper pattern** (L54–78):
```python
class ReportRangeTooLargeError(ValidationAppError):
    """Date range exceeds 366-day cap (D-06). Code LOCKED per CONTEXT.md."""

    code = "report_range_too_large"
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
```

**Thin orchestrator pattern** (L164–174):
```python
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
```

**CSV row-builder pattern** (L339–362):
```python
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
```

**What to mimic for new functions:**
- `get_trainer_usage_report` is a 3-line orchestrator: `_validate_date_range(...)` → `await repository.fetch_trainer_usage(session, query.from_date, query.to_date)` → assemble `TrainerUsageReportResponse(trainers=[TrainerUsageRow(**row) for row in rows], from_date=..., to_date=..., revenue_attribution_note=TRAINER_REPORT_REVENUE_NOTE)`.
- `trainer_usage_csv_rows` is a thin wrapper that calls `get_trainer_usage_report` then maps each row to a `list[object]`.
- NO `session.commit()`, NO `session.flush()`. Read-only invariant.

**Per-D-60 caveats specific to CSV row builder:**
- **Money formatting:** `csv_export.format_kopecks_as_rubles(...)` produces `'%.2f'` rubles (`'2500.00'`, signed for negatives — see `csv_export.py:147-161`). Apply to `revenue_kopecks`, `avg_revenue_per_session`, `total_accrued_kopecks`, `total_paid_kopecks`.
- **`utilization_pct` NULL → empty cell:** When `row["utilization_pct"]` is `None`, emit `""` (Python empty string), NOT `"None"` or `"NULL"`. The stdlib `csv.writer` writes the empty string as a delimiter-delimiter pair (`,,`) — confirmed by `csv_export.py` `_row_to_csv_line` behavior. Add a tiny helper inline: `("" if v is None else f"{v:.2f}")`.
- **`avg_revenue_per_session` NULL:** Same empty-cell rule.
- **`trainer_name_snapshot` IS the only free-text column:** wrap with `csv_export.sanitize_csv_text(row["trainer_name_snapshot"])` (formula-injection guard). Numeric columns are NOT sanitized — a negative `total_accrued_kopecks` is a legitimate signed clawback, not a formula trigger (per the explicit docstring comment in `csv_export.py:32-35`).
- **D-60-07 attribution note:** lives on the JSON envelope, NOT in the CSV body (CSV is tabular rows; notes are wire-level metadata).

---

### 4. `router.py` — ADD `GET /trainers` JSON + `GET /trainers.csv`

**Role:** router (FastAPI endpoint)
**Data flow:** JSON request-response + CSV streaming
**Primary analog (JSON):** `get_revenue_report` route at `router.py:61-82`
**Primary analog (CSV):** `get_revenue_csv` route at `router.py:143-165`

**Imports pattern** (file header, L23–53):
```python
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
    CSV_VISITS_HEADERS,
)
from app.modules.reports.schemas import (
    # ... add TrainerUsageReportQuery, TrainerUsageReportResponse
)

router = APIRouter()
```

**JSON endpoint pattern** (L61–82):
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
    """Aggregate payments ledger into period buckets with method/subject_kind breakdown.

    Refunds (subject_kind='refund', negative amount_kopecks) net into netKopecks
    only — they do NOT appear in bySubjectKind (D-01, REV-04).

    Owner-only: ``(VIEW, REPORTS)`` is in ``OWNER_ONLY``; reception → 403.
    Range cap: 366 days (D-06); to<from → 422.
    """
    result = await service.get_revenue_report(session, query)
    return envelope(result)
```

**CSV endpoint pattern** (L143–165):
```python
@router.get(
    "/revenue.csv",
    response_class=StreamingResponse,
    summary="Revenue CSV download — period buckets with ruble amounts (owner-only; EXP-01)",
)
async def get_revenue_csv(
    query: Annotated[RevenueReportQuery, Depends()],
    _actor: Annotated[
        CurrentUser, Depends(require_permission(Action.VIEW, Resource.REPORTS))
    ],
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
```

**What to mimic for the two new routes:**
- Mount on the EXISTING `router = APIRouter()` instance (L55), NOT
  `audit_log_router` (D-60-12).
- JSON path: `"/trainers"`. CSV path: `"/trainers.csv"`.
- RBAC: `Depends(require_permission(Action.VIEW, Resource.REPORTS))`
  (permissions.py:65 — pre-existing OWNER_ONLY pair; D-60-08 — NO new
  permission tuples).
- JSON returns `ResponseEnvelope[TrainerUsageReportResponse]` via `envelope(result)`.
- CSV returns `csv_export.make_csv_streaming_response(iter(rows), CSV_TRAINER_USAGE_HEADERS, f"trainer-usage-{query.from_date.isoformat()}-{query.to_date.isoformat()}.csv")`.
- NO `try/except` — `AppError` bubbles to the registered handler (router.py:15–16 docstring).
- `summary` strings include the requirement tag (e.g., `"Trainer-usage report (owner-only; RPT-01..04)"`, `"Trainer-usage CSV download (owner-only; RPT-03)"`).

**Per-D-60 caveats:**
- **Filename:** `trainer-usage-{from_date.isoformat()}-{to_date.isoformat()}.csv` — D-60-11 + Phase 56 EXP-01 precedent. Compute INSIDE the handler before calling `make_csv_streaming_response` (date params are guaranteed present after Pydantic validation).
- **No new RBAC tuple:** Three-way RBAC parity test stays invariant; admin-web frozen (D-60-08).
- **No domain audit event:** Read-only GETs emit only the request-level structlog access log (D-60-10); `LOCKED_AUDIT_EVENTS` delta = 0 for Phase 60.
- **OpenAPI metadata:** Both endpoints declare full `summary`, `response_model` (or `response_class`), `description` so Phase 61 HND-01 captures them byte-stably.

---

### 5. `csv_export.py` — NO EDITS REQUIRED (helpers are reused as-is)

**Role:** utility (CSV primitives)
**Data flow:** streaming

**Reusable assets (verbatim, no changes):**

- `BOM = "\ufeff"` constant (L28) — D-11 ("U+FEFF as Python escape, never literal glyph in source"). PITFALL-coverage: the byte sequence `\xef\xbb\xbf` MUST be the first three bytes of every `.csv` response body.
- `sanitize_csv_text(value)` (L38–59) — formula-injection guard:
  ```python
  _CSV_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")

  def sanitize_csv_text(value: str) -> str:
      """Neutralize spreadsheet formula injection in an untrusted free-text cell.
      ...
      Apply ONLY to user-controlled text columns — never to numeric/money cells,
      which legitimately begin with '-'.
      """
      if value and value[0] in _CSV_FORMULA_TRIGGERS:
          return f"'{value}"
      return value
  ```
- `make_csv_streaming_response(rows, headers, filename)` (L80–111) — emits BOM + header row + each data row, sets `Content-Disposition: attachment; filename="<name>"`.
- `format_kopecks_as_rubles(kopecks)` (L147–161) — `f"{kopecks / 100:.2f}"`, period decimal, no grouping, signed.

**Per-D-60 caveats:**
- DO NOT add a trainer-specific helper here. The row builder lives in `service.py` (see file 3 above) — that's where every existing report's CSV row builder lives. Adding one to `csv_export.py` breaks the established split.
- `sanitize_csv_text` applies ONLY to `trainer_name_snapshot` in the new CSV. Money/percent/count columns are NOT sanitized — `csv_export.py:32-35` documents this rule explicitly ("a negative `total_accrued_kopecks` is a legitimate signed clawback, not a formula trigger").

---

### 6. `constants.py` — ADD `CSV_TRAINER_USAGE_HEADERS` + `TRAINER_REPORT_REVENUE_NOTE`

**Role:** config / constants
**Primary analog:** `CSV_REVENUE_HEADERS` at `constants.py:30-37`

**Existing pattern** (L30–48):
```python
CSV_REVENUE_HEADERS: tuple[str, ...] = (
    "period",
    "netRubles",
    "cashRubles",
    "onlineRubles",
    "membershipRubles",
    "ptPackageRubles",
)

CSV_CLIENTS_HEADERS: tuple[str, ...] = (
    "fromDate",
    "toDate",
    "within",
    "activeMemberships",
    "expiringWithinN",
    "newClients",
)

CSV_VISITS_HEADERS: tuple[str, ...] = ("date", "count")
```

**What to mimic:**
- `tuple[str, ...]` type annotation, UPPER_SNAKE_CASE name.
- Header strings are camelCase wire labels (matches `alias_generator=to_camel` discipline across the codebase — `netRubles`, not `net_rubles`, not Russian-locale strings).
- Add to `__all__` at the bottom of the file.

**New constants to add:**
```python
CSV_TRAINER_USAGE_HEADERS: tuple[str, ...] = (
    "trainerNameSnapshot",
    "sessionCount",
    "cancelledSessionCount",
    "totalHours",
    "uniqueClientCount",
    "utilizationPct",
    "revenueRubles",
    "avgRevenuePerSessionRubles",
    "totalAccruedRubles",
    "totalPaidRubles",
)

TRAINER_REPORT_REVENUE_NOTE: str = (
    "Revenue is attributed to pt_packages.trainer_id (assigned at sale). "
    "Packages currently have a single assigned trainer, so per-trainer revenue "
    "is unambiguous; if a package is reassigned during its lifecycle, revenue "
    "accrues to the trainer assigned at sale time. Summing revenue across "
    "trainers may not equal the global PT-package revenue total."
)
```

**Per-D-60 caveats:**
- **Header naming clarification:** CONTEXT.md L401–403 floats Russian column titles (e.g., `"Тренер, Сессий, ..."`). BUT the working tree shows ALL existing CSV headers are camelCase English (`"netRubles"`, `"cashRubles"`, `"fromDate"`). The codified precedent wins — use camelCase English for diffability and Phase 61 OpenAPI byte-stability. (If owner UI eventually wants Russian labels, that's an FE concern.)
- Note constant lives at module scope per D-60-07 (single source of truth for the response envelope default).
- D-60 Claude's-discretion: planner may also add `TRAINER_REPORT_METHODOLOGY_NOTE` (for D-60-04 walk-in-session 0-hours behavior) and/or `TRAINER_REPORT_PAYROLL_OVERLAP_NOTE` (for D-60-05 non-prorated overlap). Recommended: keep ONE `TRAINER_REPORT_REVENUE_NOTE` plus a generic `TRAINER_REPORT_METHODOLOGY_NOTE` to keep envelope surface flat.

---

### 7. `tests/integration/reports/test_trainer_usage.py` — NEW

**Role:** integration test
**Data flow:** request-response
**Primary analog:** `tests/integration/reports/test_reports_revenue.py` (entire file, 223 lines)
**Secondary analog (CSV portions):** `tests/integration/reports/test_csv_export.py` L58–105 (BOM + content-type), L239–256 (Cyrillic round-trip), L264–288 (RFC-4180 escaping), L473–501 (formula injection)

**File header pattern** (test_reports_revenue.py L1–23):
```python
"""Integration tests for GET /api/v1/reports/revenue (Phase 55 REV-01..05).

Coverage:
  - Owner receives 200 with correct ResponseEnvelope[RevenueReportResponse] shape.
  - Reception receives 403 ((VIEW, REPORTS) ∈ OWNER_ONLY — owner-only; SC#4).
  - Net revenue reconciles: sale + refund in same period = 0 (REV-04 canonical assertion).
  - groupBy=day buckets by MSK date; groupBy=month truncates to YYYY-MM (REV-02).
  - byMethod carries only positive sale amounts; refund does not appear in bySubjectKind (D-01).
  - toDate < fromDate → 422.
  - range > 366 days → 422 report_range_too_large (D-06).
  - missing fromDate or toDate → 422.

Wire format: ?fromDate=YYYY-MM-DD&toDate=YYYY-MM-DD&groupBy=day|month
(BackendSchemaBase alias_generator=to_camel maps from_date->fromDate, to_date->toDate)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from httpx import AsyncClient
```

**Owner happy-path pattern** (L27–40):
```python
async def test_owner_gets_revenue_report(
    authed_client_owner: AsyncClient,
) -> None:
    """Owner GET /reports/revenue?fromDate=...&toDate=... returns 200 with buckets list (REV-01)."""
    r = await authed_client_owner.get(
        "/api/v1/reports/revenue",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31", "groupBy": "day"},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert isinstance(body["buckets"], list)
    assert body["fromDate"] == "2026-05-01"
    assert body["toDate"] == "2026-05-31"
    assert body["groupBy"] == "day"
```

**Reception 403 pattern** (L43–52):
```python
async def test_reception_forbidden(
    authed_client_reception: AsyncClient,
) -> None:
    """(VIEW, REPORTS) ∈ OWNER_ONLY → reception receives 403 (SC#4)."""
    r = await authed_client_reception.get(
        "/api/v1/reports/revenue",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"
```

**Domain-golden pattern (REV-04 reconcile + factory usage)** (L55–91):
```python
async def test_net_revenue_zero_after_full_refund(
    authed_client_owner: AsyncClient,
    make_payment_ledger: Any,
    seeded_owner: Any,
    make_client: Any,
    make_membership: Any,
    make_plan: Any,
) -> None:
    """Sale + same-period refund must net to zero (REV-04 canonical assertion)."""
    plan = await make_plan(name="NetZeroTest")
    cli = await make_client()
    mem = await make_membership(client_id=cli.id, plan=plan)
    msk_ts = datetime(2026, 5, 15, 10, 0, 0, tzinfo=UTC)  # well within test window
    await make_payment_ledger(
        subject_id=mem.id,
        amount_kopecks=250000,
        method="cash",
        received_at=msk_ts,
        received_by_user_id=seeded_owner.id,
    )
    ...
    r = await authed_client_owner.get(
        "/api/v1/reports/revenue",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 200, r.text
    buckets = r.json()["data"]["buckets"]
    day_bucket = next((b for b in buckets if b["period"] == "2026-05-15"), None)
    assert day_bucket is not None, f"Expected 2026-05-15 bucket in {buckets}"
    assert day_bucket["netKopecks"] == 0
```

**CSV BOM golden pattern** (test_csv_export.py L58–69):
```python
async def test_revenue_csv_bom_and_content_type(
    authed_client_owner: AsyncClient,
) -> None:
    """Owner GET /reports/revenue.csv → 200; text/csv; body starts with UTF-8 BOM."""
    r = await authed_client_owner.get(
        "/api/v1/reports/revenue.csv",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31", "groupBy": "day"},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    assert r.text[0] == BOM, f"Expected BOM as first char, got {r.text[0]!r}"
    assert ord(r.text[0]) == 0xFEFF, f"BOM must be U+FEFF, got U+{ord(r.text[0]):04X}"
```

**Cyrillic round-trip pattern** (test_csv_export.py L239–256):
```python
async def test_audit_log_csv_cyrillic_round_trip(
    authed_client_owner: AsyncClient,
    make_audit_log_row: Any,
) -> None:
    """Cyrillic actor_email_snapshot appears verbatim in audit-log.csv after BOM (EXP-04)."""
    cyrillic_email = "иван@почта.рф"
    await make_audit_log_row(
        action="login_success",
        resource_type="session",
        created_at=datetime(2026, 5, 20, 10, 0, tzinfo=UTC),
        actor_email_snapshot=cyrillic_email,
    )
    r = await authed_client_owner.get(
        "/api/v1/audit-log.csv",
        params={"action": "login_success"},
    )
    assert r.status_code == 200, r.text
    assert cyrillic_email in r.text, "Cyrillic email must appear verbatim in CSV output"
```

**Formula-injection golden pattern** (test_csv_export.py L473–501):
```python
async def test_audit_log_csv_formula_injection_sanitized(
    authed_client_owner: AsyncClient,
    make_audit_log_row: Any,
) -> None:
    """A formula-trigger actor_email_snapshot is neutralized in audit-log.csv (CR-01)."""
    malicious = "=cmd|'/C calc'!A0"
    await make_audit_log_row(
        action="login_success",
        resource_type="session",
        created_at=datetime(2026, 5, 21, 9, 0, tzinfo=UTC),
        actor_email_snapshot=malicious,
    )
    r = await authed_client_owner.get(
        "/api/v1/audit-log.csv",
        params={"action": "login_success"},
    )
    assert r.status_code == 200, r.text
    rows = parse_csv_text(r.text)
    email_col = list(CSV_AUDIT_LOG_HEADERS).index("actorEmailSnapshot")
    target = [row for row in rows[1:] if row and malicious in row[email_col]]
    assert target, "audited row with the malicious email must be present"
    cell = target[0][email_col]
    assert cell == f"'{malicious}", f"formula cell must be quote-prefixed, got {cell!r}"
    assert not cell.startswith("="), "sanitized cell must not start with a formula trigger"
```

**Fixture imports (test_reports_revenue.py only imports `httpx.AsyncClient` — the fixtures arrive via `tests/integration/reports/conftest.py`):**
```python
# conftest.py L18-30 re-exports owner/reception clients + factories from memberships tests:
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
```

**What to mimic for `test_trainer_usage.py`:**
- File-header docstring enumerating each pitfall/coverage point with the
  RPT/D-60 tag (PITFALL 6, PITFALL 10, PITFALL 11, PITFALL 12, RPT-04
  clawback netting, reception 403, CSV BOM+Cyrillic+formula-injection).
- One test function per pitfall/golden — each function's docstring cites
  the pitfall number (e.g., `"""PITFALL 11: deactivated trainer with historical sessions appears in report."""`).
- Use `authed_client_owner` + `authed_client_reception` fixtures (already
  in conftest — no new fixtures needed per D-60-13).
- Reuse existing factory builders for the seed: `make_client`,
  `make_payment_ledger` (already in `reports/conftest.py`). New factories
  for `pt_sessions`, `pt_packages`, `trainer_availability_slots`,
  `trainer_payroll_accruals` should already exist from Phase 58/59 — verify
  at planning time and ONLY add new fixtures if grep shows them missing.

**Mandatory acceptance tests per D-60-13:**

| Test | Asserts | Source pitfall |
|------|---------|----------------|
| `test_owner_gets_trainer_usage_report` | 200 + envelope shape (`trainers: list`, `revenueAttributionNote: str`) | RPT-01..04 happy path |
| `test_reception_forbidden_on_trainers_json` | 403 + `code: "forbidden"` | RPT-01 reception 403 |
| `test_reception_forbidden_on_trainers_csv` | 403 + `code: "forbidden"` | RPT-03 reception 403 |
| `test_deactivated_trainer_appears_in_report` | trainer with `is_active=False` + historical sessions present in `trainers[]` | PITFALL 11 (D-60-03 / D-60-13) |
| `test_session_on_to_date_included_session_after_excluded` | session on `to_date` counted; session on `to_date + 1 day` NOT counted | PITFALL 12 (mirrors VER-02 from Phase 57) |
| `test_revenue_attributed_to_assigned_trainer_not_conducting` | `revenue_kopecks` follows `pt_packages.trainer_id`, NOT `pt_sessions.trainer_id` | PITFALL 6 (D-58-21 / D-60-07) |
| `test_utilization_null_when_zero_slots` | trainer with 0 active slots → `utilizationPct: null` (NOT 0) | D-60-06 |
| `test_utilization_zero_when_slots_but_no_bookings` | trainer with active slots + 0 bookings → `utilizationPct: 0.0` | D-60-06 |
| `test_clawback_nets_in_total_accrued` | positive accrual + negative clawback → `totalAccruedKopecks` = net | RPT-04 / D-58-03 |
| `test_trainers_csv_bom_and_content_type` | body[0] == U+FEFF; `text/csv; charset=utf-8` | RPT-03 / EXP-04 |
| `test_trainers_csv_header_row` | row 0 == `list(CSV_TRAINER_USAGE_HEADERS)` | RPT-03 |
| `test_trainers_csv_cyrillic_trainer_name` | Cyrillic `full_name` appears verbatim after BOM | RPT-03 |
| `test_trainers_csv_formula_injection_sanitized` | `trainer_name_snapshot` = `"=cmd|'/C calc'!A0"` → cell prefixed with `'` | T-56-07 / CR-01 |
| `test_trainers_csv_utilization_null_renders_empty_cell` | utilization NULL → empty CSV cell (`,,`), NOT `"None"` / `"NULL"` | D-60-11 |

**Plus a non-test acceptance check** (CI / plan-step grep guard per D-60-13):
```bash
! grep -rE "from app.modules.(pt_sessions|trainers|payments|payroll|schedule|bookings|pt_packages).models" apps/backend/app/modules/reports/
# AND
lint-imports && git diff --exit-code .importlinter
```

**Per-D-60 caveats:**
- Tests must use the SAVEPOINT-isolated `db_session` fixture (already
  set up — `reports/conftest.py:35` uses `db_session: AsyncSession` for
  factory inserts; teardown rolls back).
- Reception 403 is also verified automatically by the Phase 56 route-introspection guard (CONTEXT canonical_refs). No need to duplicate beyond the two explicit golden tests above (one per endpoint), but having them in-file is the established pattern (test_reports_revenue.py L43–52 + test_csv_export.py L167–199 both keep per-endpoint reception-403 tests).

---

## Shared Patterns

### Authentication / Authorization (RBAC)

**Source:** `apps/backend/app/core/permissions.py:62-129`
**Apply to:** Both new routes in `router.py`.

```python
# permissions.py:62-69 — pre-existing OWNER_ONLY frozenset
OWNER_ONLY: frozenset[tuple[Action, Resource]] = frozenset(
    (
        (Action.VIEW, Resource.FINANCE),
        (Action.VIEW, Resource.REPORTS),     # <-- L65, gates Phase 60 endpoints
        (Action.VIEW, Resource.PAYROLL),
        (Action.VIEW, Resource.COMPENSATION),
        (Action.VIEW, Resource.SETTINGS),
        (Action.VIEW, Resource.OWNER_AREA),
        ...
    )
)
```

```python
# router.py:67-71 — dependency injection wiring (mirror for /trainers + /trainers.csv)
_actor: Annotated[
    CurrentUser, Depends(require_permission(Action.VIEW, Resource.REPORTS))
],
```

**Caveats:**
- ZERO new RBAC tuples (D-60-08). Three-way parity test (backend/admin-web `can.ts`/`registry.ts`) stays invariant.
- Reception → 403 auto-verified by Phase 56 route-introspection guard.

---

### Error handling

**Source:** `service.py:54-78` (validation helper + exception classes) + `router.py:14-17` (file-header comment)
**Apply to:** New service function `get_trainer_usage_report`.

```python
# service.py:54-78
class ReportRangeTooLargeError(ValidationAppError):
    """Date range exceeds 366-day cap (D-06). Code LOCKED per CONTEXT.md."""
    code = "report_range_too_large"
    status_code = 422


def _validate_date_range(from_date: date, to_date: date) -> None:
    if to_date < from_date:
        raise ValidationAppError("to must be >= from")
    if (to_date - from_date).days > 366:
        raise ReportRangeTooLargeError("Date range exceeds 366-day limit")
```

```python
# router.py:14-17 (file header note — applies to all routes)
# No try/except in route handlers — AppError subclasses bubble to the
# registered ``_app_error_handler`` (core/exceptions.py:register_exception_handlers).
```

**Caveats:**
- Reuse `_validate_date_range` as-is (already module-private but it's the established helper — call from `get_trainer_usage_report`).
- NO new error codes introduced for Phase 60. `to_date < from_date` → reuse existing `ValidationAppError`; `range > 366d` → reuse `ReportRangeTooLargeError`.
- NO `try/except` in router handlers.

---

### CSV-export discipline (BOM / RFC-4180 / formula-injection / money)

**Source:** `csv_export.py` (entire file) + `service.py:339-401` (existing row builders)
**Apply to:** New `trainer_usage_csv_rows` in `service.py` + new `GET /trainers.csv` route in `router.py`.

| Concern | Source | What to apply |
|---------|--------|---------------|
| BOM (U+FEFF first byte) | `csv_export.py:28` `BOM = "\ufeff"` + `make_csv_streaming_response` L101–110 | Use `make_csv_streaming_response` — it emits BOM automatically. |
| RFC-4180 escaping | `csv_export.py:62-77` `_row_to_csv_line` (excel dialect, `\r\n`, `QUOTE_MINIMAL`) | `make_csv_streaming_response` calls this per row — no client code needed. |
| Money → rubles | `csv_export.py:147-161` `format_kopecks_as_rubles` | Apply to every kopecks column in `trainer_usage_csv_rows` row builder. Signed (negative clawback → `"-12.34"` is correct). |
| Free-text sanitization | `csv_export.py:38-59` `sanitize_csv_text` | Apply ONLY to `trainer_name_snapshot`. NOT to numeric cells. |
| NULL → empty cell | `csv_export.py:75` `csv.writer` writes `""` as `,,` (delimiter-delimiter) | For `utilization_pct` / `avg_revenue_per_session` NULL: emit `""` in the row list. Confirm with a golden test. |
| Filename | `router.py:165` `csv_export.make_csv_streaming_response(iter(rows), CSV_REVENUE_HEADERS, "revenue.csv")` | `f"trainer-usage-{q.from_date.isoformat()}-{q.to_date.isoformat()}.csv"` per Phase 56 EXP-01 precedent. |
| Content-Disposition | `csv_export.py:110` `headers={"Content-Disposition": f'attachment; filename="{filename}"'}` | Automatic via `make_csv_streaming_response`. |

---

### Read-only cross-module discipline (D-54-08 / D-REPORT-READONLY / PITFALL 10)

**Source:** `repository.py:1-27` (file-header doctrine block)
**Apply to:** New `fetch_trainer_usage` reader.

```python
# repository.py:1-27
"""Reports repository — raw-SQL read aggregator + ORM audit-log reader.
...
CROSS-MODULE READ DISCIPLINE (D-54-08 / Phase 49 D-49-03 precedent):
  - ``from sqlalchemy import text`` — NEVER import another module's ORM model.
  - Bind params via ``:name`` placeholders + a dict; cast UUIDs to ``str``.
  - ``.mappings().all()`` for aggregate/list reads.
  - ``.mappings().one()`` for scalar count reads.
  - Each reader documents verified columns + source file:line of the foreign table.

INVARIANTS:
  - ZERO INSERT / UPDATE / DELETE in this file.
  - ORM model imports from other modules (app.modules.*): FORBIDDEN.
  - ORM model imports from app.core.*: ALLOWED (see exception above).
"""
```

**Caveats:**
- The `fetch_trainer_usage` docstring MUST list every cross-module table + the verified columns referenced, with file:line. Sample columns to enumerate:
  - `pt_sessions` (`apps/backend/app/modules/pt_sessions/models.py:52-103`): `trainer_id`, `pt_package_id`, `performed_at`, `cancelled_at`, `booking_id`, `trainer_name_snapshot` (B-05, NOT NULL).
  - `pt_packages` (`apps/backend/app/modules/pt_packages/models.py:105-186`): `id`, `client_id`, `trainer_id` (nullable, FK to trainers ON DELETE RESTRICT).
  - `payments` (`apps/backend/app/modules/payments/models.py`): `subject_id`, `subject_kind`, `amount_kopecks`, `paid_at`/`received_at` (verify which is the canonical temporal column — CONTEXT uses `paid_at`, but `fetch_revenue_buckets` uses `received_at`; resolve at planning time by reading `payments/models.py`).
  - `trainer_availability_slots` (`apps/backend/app/modules/schedule/models.py:69+`): `trainer_id`, `status`, `start_time`, `end_time`. CHECK: `status IN ('active', 'booked', 'cancelled')`.
  - `trainer_payroll_accruals` (`apps/backend/app/modules/payroll/models.py:117-`): `trainer_id`, `period_start`, `period_end`, `status` (`'pending' | 'paid'`), `accrual_kopecks` (signed, D-58-03), `clawback_of_accrual_id`.
  - `bookings` (`apps/backend/app/modules/bookings/models.py`): `id`, `slot_id`.
  - `trainers`: `id`, `full_name`, `is_active`.
- ZERO `INSERT / UPDATE / DELETE`. ZERO `session.commit()` / `session.flush()` in the new service function.

---

## No Analog Found

None. Every Phase 60 file has an exact in-module analog. The phase is a 1:1
extension of the Phase 55 + Phase 56 patterns, with the trainer-specific
domain logic landing inside the established repository → service → router
pipeline.

---

## Metadata

**Analog search scope:**
- `apps/backend/app/modules/reports/` (all 7 source files — `__init__.py`, `constants.py`, `csv_export.py`, `permissions.py`, `repository.py`, `router.py`, `schemas.py`, `service.py`)
- `apps/backend/tests/integration/reports/` (all test files — `conftest.py`, `test_audit_log.py`, `test_csv_export.py`, `test_reports_clients.py`, `test_reports_dst.py`, `test_reports_revenue.py`, `test_reports_visits.py`)
- `apps/backend/app/core/permissions.py` (RBAC pair verification)

**Files scanned:** 15
**Pattern extraction date:** 2026-05-25
