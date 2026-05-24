# Phase 56: Audit Log Read API + CSV Export — Pattern Map

**Mapped:** 2026-05-24
**Files analyzed:** 7 new/modified files
**Analogs found:** 6 / 7 (1 greenfield: `csv_export.py`)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/backend/app/modules/reports/schemas.py` | model (DTOs) | request-response | `apps/backend/app/modules/reports/schemas.py` (extend) | exact — add to existing file |
| `apps/backend/app/modules/reports/constants.py` | config | — | `apps/backend/app/modules/reports/constants.py` (extend) | exact — add to existing file |
| `apps/backend/app/modules/reports/repository.py` | repository | CRUD (read-only ORM) | `apps/backend/app/modules/clients/repository.py` | exact — ORM `select()` + paginated keyset ordering |
| `apps/backend/app/modules/reports/service.py` | service | CRUD (read-only) | `apps/backend/app/modules/reports/service.py` (extend) | exact — add audit-log read path |
| `apps/backend/app/modules/reports/router.py` | controller/router | request-response | `apps/backend/app/modules/reports/router.py` (extend) | exact — add audit-log router + CSV routes |
| `apps/backend/app/modules/reports/csv_export.py` | utility | streaming / file-I/O | *(no analog — greenfield)* | none |
| `apps/backend/app/api/v1/router.py` | config/route-mount | request-response | `apps/backend/app/api/v1/router.py` (extend) | exact — add one `include_router` call |
| `tests/integration/reports/test_audit_log.py` | test | CRUD | `tests/integration/reports/test_reports_revenue.py` | exact — owner/reception/422/filter pattern |

---

## Pattern Assignments

### `apps/backend/app/modules/reports/schemas.py` — add `AuditLogItem` + `AuditLogQuery`

**Analog:** same file (`apps/backend/app/modules/reports/schemas.py`)

**Imports pattern** (lines 34–39):
```python
from __future__ import annotations

from datetime import date
from typing import Literal

from app.core.schemas import BackendSchemaBase, ResponseData
```

**Query DTO pattern** — extend `PageQuery` like `ClientListQuery`
(`apps/backend/app/modules/clients/schemas.py` lines 209–223):
```python
class AuditLogQuery(PageQuery):
    """GET /api/v1/audit-log query params (D-05, D-06, D-07).

    Inherits page + page_size from PageQuery (defaults: page=1, pageSize=20, max 100).
    Wire: ?actorUserId=...&actorEmailSnapshot=...&resourceType=...&action=...&from=...&to=...
    (alias_generator=to_camel inherited via PageQuery -> BackendSchemaBase -> ContractModel)
    """
    actor_user_id: UUID | None = None
    actor_email_snapshot: str | None = None
    resource_type: str | None = None
    action: str | None = None
    from_: date | None = Field(default=None, alias="from")   # 'from' is a Python keyword — needs alias
    to: date | None = None
```

**Response DTO pattern** — like `RevenueBucket(ResponseData)` but for audit rows
(`apps/backend/app/modules/reports/schemas.py` lines 76–92):
```python
class AuditLogItem(ResponseData):
    """Single audit-log row (D-09). Owner sees full payload including JSONB."""
    id: UUID
    created_at: datetime          # wire: createdAt (ISO-8601 with tz offset)
    actor_user_id: UUID | None
    actor_email_snapshot: str | None
    action: str
    resource_type: str
    resource_id: UUID | None
    payload: dict[str, Any]
```

**Note on `from` alias:** `BackendSchemaBase` uses `alias_generator=to_camel` +
`validate_by_name=True` + `validate_by_alias=True`. For the `from` param (Python keyword),
use `Field(default=None, alias="from")` and declare the Python attribute as `from_`.
FastAPI `Depends()` will match the `alias="from"` as the query param name.

---

### `apps/backend/app/modules/reports/constants.py` — add CSV column name constants

**Analog:** `apps/backend/app/modules/reports/constants.py` (lines 1–17)

Extend the existing module by appending column-name tuples, following the same
`UPPER_SNAKE_CASE` naming already used for `GRAIN_DAY` / `GRAIN_MONTH`:

```python
# CSV column header constants (Phase 56 EXP-01..04, D-15)
CSV_AUDIT_LOG_HEADERS: tuple[str, ...] = (
    "createdAt", "actorUserId", "actorEmailSnapshot",
    "action", "resourceType", "resourceId", "payload",
)
CSV_REVENUE_HEADERS: tuple[str, ...] = (
    "period", "netRubles", "cashRubles", "onlineRubles",
    "membershipRubles", "ptPackageRubles",
)
CSV_CLIENTS_HEADERS: tuple[str, ...] = (
    "fromDate", "toDate", "within", "activeMemberships",
    "expiringWithinN", "newClients",
)
CSV_VISITS_HEADERS: tuple[str, ...] = ("date", "count")
```

---

### `apps/backend/app/modules/reports/repository.py` — add `fetch_audit_log_page` + `stream_audit_log_rows`

**Analog for ORM paginated list with keyset ordering:**
`apps/backend/app/modules/clients/repository.py` (lines 57–139)

**ORM select + filter composition + COUNT + keyset ORDER + offset/limit pattern** (lines 74–139):
```python
from sqlalchemy import Select, and_, func, or_, select, text
from app.core.pagination import PaginatedData
# ...

async def list_alive(session, query) -> PaginatedData[Client]:
    predicates: list[Any] = [Client.deleted_at.is_(None)]

    if query.q is not None:
        escaped_q = escape_like_pattern(query.q.lower())
        like_pattern = f"%{escaped_q}%"
        # ... ILIKE predicate appended

    # Total count — same predicate list, no ORDER/LIMIT.
    total_stmt = select(func.count()).select_from(Client).where(and_(*predicates))
    total = await session.scalar(total_stmt) or 0

    stmt: Select[tuple[Client]] = select(Client).where(and_(*predicates))
    stmt = stmt.order_by(Client.created_at.desc(), Client.id.desc())  # keyset ORDER

    offset = (query.page - 1) * query.page_size
    stmt = stmt.offset(offset).limit(query.page_size)

    rows = (await session.scalars(stmt)).all()

    return PaginatedData.model_construct(
        items=list(rows),
        total=total,
        page=query.page,
        page_size=query.page_size,
    )
```

**Apply to audit-log listing:**
- Replace `Client` → `AuditLog` (from `app.core.audit_models`).
- Replace `deleted_at.is_(None)` guard with optional filters (actor_user_id, actor_email_snapshot ILIKE, resource_type, action, date window AT TIME ZONE 'Europe/Moscow').
- Keep `order_by(AuditLog.created_at.desc(), AuditLog.id.desc())` — covers `ix_audit_log_created_at`.
- `PaginatedData.model_construct(...)` — same as clients; ORM rows are not Pydantic models.

**ILIKE pattern** (from clients/repository.py lines 78–93) — for `actor_email_snapshot`:
```python
if query.actor_email_snapshot is not None:
    like_pattern = f"%{query.actor_email_snapshot}%"
    predicates.append(AuditLog.actor_email_snapshot.ilike(like_pattern))
```

**Date window pattern** (mirror of `fetch_revenue_buckets` AT TIME ZONE usage in
`apps/backend/app/modules/reports/repository.py` lines 58–76, but applied ORM-side):
```python
# D-06: inclusive MSK day bounds on created_at
from sqlalchemy import cast, func
from sqlalchemy.types import Date
msk_date = cast(
    func.timezone("Europe/Moscow", AuditLog.created_at),
    Date,
)
if query.from_ is not None:
    predicates.append(msk_date >= query.from_)
if query.to is not None:
    predicates.append(msk_date <= query.to)
```

**Streaming iterator for CSV export (D-16)** — use `AsyncSession.stream_scalars`:
```python
async def stream_audit_log_rows(
    session: AsyncSession,
    query: AuditLogQuery,
) -> AsyncIterator[AuditLog]:
    """Yield AuditLog rows one-by-one for CSV streaming (D-16, no pagination)."""
    predicates = _build_predicates(query)
    stmt = (
        select(AuditLog)
        .where(and_(*predicates))
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    )
    result = await session.stream_scalars(stmt)
    async for row in result:
        yield row
```

**CROSS-MODULE DISCIPLINE NOTE:** `AuditLog` lives in `app.core.audit_models` and is
freely importable by `app.modules.reports` (no violation — only module↔module ORM imports
are banned). Import as:
```python
from app.core.audit_models import AuditLog
```

---

### `apps/backend/app/modules/reports/service.py` — add audit-log read functions

**Analog:** `apps/backend/app/modules/reports/service.py` (whole file, lines 1–238)

**Service function signature and validation pattern** (lines 141–151):
```python
async def get_revenue_report(
    session: AsyncSession,
    query: RevenueReportQuery,
) -> RevenueReportResponse:
    """... Read-only: NO session.commit(), NO session.flush()."""
    _validate_date_range(query.from_date, query.to_date)
    rows = await repository.fetch_revenue_buckets(session, query)
    return _pivot_revenue_buckets(rows, query)
```

**Custom ValidationAppError subclass pattern** (lines 38–55):
```python
class ReportRangeTooLargeError(ValidationAppError):
    """Date range exceeds 366-day cap. Code LOCKED per CONTEXT.md."""
    code = "report_range_too_large"
    status_code = 422


def _validate_date_range(from_date: date, to_date: date) -> None:
    if to_date < from_date:
        raise ValidationAppError("to must be >= from")
    if (to_date - from_date).days > 366:
        raise ReportRangeTooLargeError("Date range exceeds 366-day limit")
```

**Apply to audit-log service:**
- `AuditFilterInvalidError(ValidationAppError)` with `code = "audit_filter_invalid"` / `status_code = 422`.
- Validate `query.action` against the set of valid event names derived from `LOCKED_AUDIT_EVENTS`.
- Validate `query.resource_type` against the set of valid resource types from `LOCKED_AUDIT_EVENTS`.
- Validate `query.to < query.from_` → `ValidationAppError("to must be >= from")`.
- No 366-day cap on JSON endpoint (D-06 comment).
- Return `PaginatedData[AuditLogItem]` — convert ORM rows via `AuditLogItem.model_validate(row)`.

**LOCKED_AUDIT_EVENTS validation set derivation**
(`apps/backend/app/core/audit.py` lines 244+):
```python
from app.core.audit import LOCKED_AUDIT_EVENTS

VALID_ACTIONS: frozenset[str] = frozenset(e for e, _ in LOCKED_AUDIT_EVENTS)
VALID_RESOURCE_TYPES: frozenset[str] = frozenset(r for _, r in LOCKED_AUDIT_EVENTS)
```

---

### `apps/backend/app/modules/reports/router.py` — add audit_log_router + CSV routes

**Analog:** `apps/backend/app/modules/reports/router.py` (whole file, lines 1–112)

**Router instantiation pattern** (line 36):
```python
router = APIRouter()
```
For the new audit-log router, add a second `APIRouter()` in the same file:
```python
audit_log_router = APIRouter()
```

**GET endpoint with `Depends()` query + RBAC + session pattern** (lines 39–60):
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

**Apply to audit-log JSON listing:**
```python
@audit_log_router.get(
    "",
    response_model=ResponseEnvelope[PaginatedData[AuditLogItem]],
    summary="Paginated audit-log listing (owner-only; AUD-01..06)",
)
async def list_audit_log(
    query: Annotated[AuditLogQuery, Depends()],
    _actor: Annotated[
        CurrentUser, Depends(require_permission(Action.LIST, Resource.AUDIT_LOG))
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[AuditLogItem]]:
    result = await service.list_audit_log(session, query)
    return envelope(result)
```

**RBAC import** (line 23):
```python
from app.core.permissions import Action, Resource
```

**For CSV routes** — `StreamingResponse` is returned directly (not `ResponseEnvelope`),
so omit `response_model` or set `response_class=StreamingResponse`. No `envelope()` call.
The RBAC + session dependency wiring is identical to the JSON siblings.

**Imports to add** for pagination support:
```python
from app.core.pagination import PaginatedData
```

---

### `apps/backend/app/modules/reports/csv_export.py` — GREENFIELD utility

**No analog in the codebase.** No existing `StreamingResponse` or `csv` usage found in `apps/backend/`.

**Establish new module. Key API contract (D-11, D-12):**

```python
"""CSV export helper — BOM + RFC-4180 + StreamingResponse (Phase 56 EXP-01..04, D-11..12).

Single source of truth for:
  - UTF-8 BOM first yield (U+FEFF) for Excel Cyrillic detection (EXP-04).
  - stdlib csv.writer with QUOTE_MINIMAL + ',' delimiter + '\r\n' terminator (RFC 4180).
  - StreamingResponse with media_type='text/csv; charset=utf-8' +
    Content-Disposition: attachment; filename='<name>.csv'.
  - Money formatting: kopecks -> rubles as '%.2f' (period decimal, no grouping) (D-13).
  - Date formatting: date -> 'YYYY-MM-DD'; datetime -> 'YYYY-MM-DD HH:MM:SS' MSK (D-14).
"""

import csv
import io
from collections.abc import AsyncIterator, Iterator
from datetime import timezone

from fastapi.responses import StreamingResponse

_MSK = timezone(timedelta(hours=3), name="MSK")

BOM = "\ufeff"  # UTF-8 BOM: U+FEFF


def _row_to_csv_line(row: list[object]) -> str:
    """Write a single row to a CSV string via csv.writer (RFC-4180 escaping)."""
    buf = io.StringIO()
    writer = csv.writer(buf, dialect="excel")  # excel dialect: comma + \r\n + QUOTE_MINIMAL
    writer.writerow(row)
    return buf.getvalue()


def make_csv_streaming_response(
    rows: Iterator[list[object]],         # sync generator for report CSVs
    headers: tuple[str, ...],
    filename: str,
) -> StreamingResponse:
    """Wrap a sync row-iterator in a StreamingResponse with BOM + headers row."""

    def _generate() -> Iterator[str]:
        yield BOM
        yield _row_to_csv_line(list(headers))
        for row in rows:
            yield _row_to_csv_line(row)

    return StreamingResponse(
        _generate(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def make_async_csv_streaming_response(
    rows: AsyncIterator[list[object]],    # async generator for audit-log CSV
    headers: tuple[str, ...],
    filename: str,
) -> StreamingResponse:
    """Wrap an async row-iterator in a StreamingResponse (for audit-log CSV, D-16)."""

    async def _generate() -> AsyncIterator[str]:
        yield BOM
        yield _row_to_csv_line(list(headers))
        async for row in rows:
            yield _row_to_csv_line(row)

    return StreamingResponse(
        _generate(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def format_kopecks_as_rubles(kopecks: int) -> str:
    """Format signed kopecks as rubles with 2 decimals, period separator (D-13).

    Examples: 250000 -> '2500.00', -100 -> '-1.00'.
    """
    return f"{kopecks / 100:.2f}"


def format_datetime_msk(dt: datetime) -> str:
    """Convert aware datetime to MSK and format as 'YYYY-MM-DD HH:MM:SS' (D-14)."""
    msk_dt = dt.astimezone(_MSK)
    return msk_dt.strftime("%Y-%m-%d %H:%M:%S")
```

**No prior pattern to copy from — this file is the new pattern for all CSV work in the project.**

---

### `apps/backend/app/api/v1/router.py` — add `audit_log_router` mount

**Analog:** same file (lines 35–99)

**Existing reports mount pattern** (lines 35 + 78):
```python
from app.modules.reports.router import router as reports_router
# ...
v1.include_router(reports_router, prefix="/reports", tags=["reports"])
```

**Add alongside** (D-02):
```python
from app.modules.reports.router import audit_log_router
# ...
v1.include_router(audit_log_router, prefix="/audit-log", tags=["audit-log"])
```

Place the new import on line 36 (adjacent to `reports_router` import) and the
`include_router` call immediately after the reports mount at line 79.

---

### `tests/integration/reports/test_audit_log.py` — new integration test file

**Analog:** `tests/integration/reports/test_reports_revenue.py` (lines 1–120)

**Test file structure pattern** (revenue test, lines 27–52):
```python
async def test_owner_gets_revenue_report(
    authed_client_owner: AsyncClient,
) -> None:
    r = await authed_client_owner.get(
        "/api/v1/reports/revenue",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31", "groupBy": "day"},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert isinstance(body["buckets"], list)


async def test_reception_forbidden(
    authed_client_reception: AsyncClient,
) -> None:
    r = await authed_client_reception.get(
        "/api/v1/reports/revenue",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"
```

**Conftest fixture reuse pattern** (`tests/integration/reports/conftest.py` lines 16–28):
```python
from tests.integration.memberships.conftest import (  # noqa: F401
    authed_client_owner,
    authed_client_reception,
    db_session_real_commit,
    make_client,
    ...
)
```

**Apply to audit-log tests:**
- `GET /api/v1/audit-log` → 200 + `data.items` list shape (AUD-01).
- Reception → 403 `forbidden` (AUD-05, SC#1).
- `?action=unknown_event` → 422 `audit_filter_invalid` (D-05 / AUD-03).
- `?to=2026-01-01&from=2026-05-01` → 422 (to < from).
- Pagination stability: insert a row mid-pagination, assert page-1 does not shift (SC#3).
- `GET /api/v1/audit-log.csv` → 200, `Content-Type: text/csv`, body starts with UTF-8 BOM (EXP-04).
- Cyrillic value round-trips through CSV (`actor_email_snapshot` with Cyrillic chars).
- Report CSV endpoints (`/reports/revenue.csv`, etc.) → 200 + correct headers + BOM.

**Fixture for audit-log rows** — direct ORM insert of `AuditLog` rows
(mirrors `make_payment_ledger` / `make_visit` fixture pattern in
`tests/integration/reports/conftest.py` lines 31–63):
```python
@pytest_asyncio.fixture
async def make_audit_log_row(db_session: AsyncSession) -> Callable[..., Awaitable[AuditLog]]:
    async def _make(*, action: str, resource_type: str, created_at: datetime, ...) -> AuditLog:
        row = AuditLog(action=action, resource_type=resource_type, ...)
        row.created_at = created_at
        db_session.add(row)
        await db_session.commit()
        await db_session.refresh(row)
        return row
    return _make
```

---

## Shared Patterns

### RBAC Chokepoint
**Source:** `apps/backend/app/core/dependencies.py` lines 812–865
`apps/backend/app/core/permissions.py` lines 125–130

**Apply to:** All new route handlers in `reports/router.py`

```python
_actor: Annotated[
    CurrentUser, Depends(require_permission(Action.LIST, Resource.AUDIT_LOG))
]
# or for report CSVs:
_actor: Annotated[
    CurrentUser, Depends(require_permission(Action.VIEW, Resource.REPORTS))
]
```

`(LIST, AUDIT_LOG)` and `(VIEW, AUDIT_LOG)` are already in `OWNER_ONLY`
(`permissions.py` lines 128–129). No new permissions.py work needed.

### Response Envelope
**Source:** `apps/backend/app/core/schemas.py` lines 60–82

**Apply to:** JSON list endpoint only. CSV routes return `StreamingResponse` directly —
no `envelope()` call, no `response_model`.

```python
return envelope(result)                    # JSON
return make_csv_streaming_response(...)    # CSV — no envelope
```

### Validation Error Pattern
**Source:** `apps/backend/app/core/exceptions.py` lines 48–51
`apps/backend/app/modules/reports/service.py` lines 38–55

**Apply to:** `reports/service.py` audit-log service functions

```python
class AuditFilterInvalidError(ValidationAppError):
    code = "audit_filter_invalid"
    status_code = 422
```
Raised for unknown `action` or `resource_type` filter values (D-05).
Raised for `to < from` date window (generic `ValidationAppError`).
**No try/except in route handlers** — these bubble to `_app_error_handler`.

### PaginatedData Construction
**Source:** `apps/backend/app/modules/clients/repository.py` lines 134–139

**Apply to:** `reports/repository.py` audit-log fetch function

```python
return PaginatedData.model_construct(
    items=list(rows),       # ORM rows, not Pydantic models yet
    total=total,
    page=query.page,
    page_size=query.page_size,
)
```
Use `model_construct` (skip validation) at the repository layer; `AuditLogItem.model_validate(row)` conversion happens in the service layer.

### Europe/Moscow Date Window
**Source:** `apps/backend/app/modules/reports/repository.py` lines 58–75

Raw-SQL pattern used for date filtering in repository; the ORM equivalent for
audit-log (cast + func.timezone) follows the same discipline:
```python
# Raw SQL reference (repository.py line 69):
"WHERE (received_at AT TIME ZONE 'Europe/Moscow')::date BETWEEN :from_date AND :to_date"

# ORM equivalent for AuditLog:
from sqlalchemy import cast, func
from sqlalchemy.types import Date
msk_date = cast(func.timezone("Europe/Moscow", AuditLog.created_at), Date)
predicates.append(msk_date >= query.from_)
predicates.append(msk_date <= query.to)
```

### `from __future__ import annotations`
**Apply to:** all new `.py` files in `reports/` that use PEP 695 generics or
forward references. Required in `repository.py` (return type annotation uses
`PaginatedData[AuditLog]` before Client is defined as Pydantic).

---

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `apps/backend/app/modules/reports/csv_export.py` | utility | streaming / file-I/O | No `StreamingResponse` or `csv` usage exists anywhere in `apps/backend/`. This is the first streaming response in the project — establish new pattern here. |

---

## Metadata

**Analog search scope:**
- `apps/backend/app/modules/reports/` (primary host)
- `apps/backend/app/modules/clients/` (ORM paginated list pattern)
- `apps/backend/app/core/` (pagination, schemas, exceptions, audit_models, permissions, dependencies)
- `apps/backend/app/api/v1/router.py` (mount conventions)
- `apps/backend/tests/integration/reports/` (test structure)

**Files scanned:** 14

**Key architectural notes:**
1. `AuditLog` is importable from `app.core.audit_models` by reports module — not a cross-module ORM violation (core is a free import target).
2. The `from` query param conflicts with a Python keyword — use `Field(alias="from")` on a `from_: date | None` attribute.
3. All CSV routes return `StreamingResponse` directly — skip `ResponseEnvelope`, skip `response_model`, skip `envelope()`.
4. Audit CSV uses `AsyncSession.stream_scalars()` (async streaming, bounded memory); report CSVs can use synchronous generator from already-fetched in-memory data (single-gym volume is small).
5. `PaginatedData.model_construct` (not `PaginatedData[T](...)`) is the validated pattern at the repository layer to avoid `PydanticSchemaGenerationError` when items are ORM rows.
