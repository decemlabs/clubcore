# Phase 54: Foundations — Module Scaffold + RBAC Parity + Indexes - Pattern Map

**Mapped:** 2026-05-24
**Files analyzed:** 12 (7 scaffold + 5 modified)
**Analogs found:** 12 / 12

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/modules/reports/__init__.py` | module-doc | n/a | `app/modules/payments/__init__.py` | exact |
| `app/modules/reports/permissions.py` | rbac-factory | request-response | `app/modules/payments/permissions.py` | exact |
| `app/modules/reports/constants.py` | constants | n/a | `app/modules/payments/constants.py` | exact |
| `app/modules/reports/router.py` | route | request-response | `app/modules/payments/router.py` | exact |
| `app/modules/reports/service.py` | service | transform/read-aggregate | `app/modules/online_payments/service.py` (raw-SQL readers) | role-match |
| `app/modules/reports/repository.py` | repository | read (raw SQL) | `app/modules/online_payments/service.py:116-171` + `app/modules/payments/repository.py` | role-match |
| `app/modules/reports/schemas.py` | schema | request-response | `app/modules/payments/schemas.py` | exact |
| `app/core/permissions.py` (MODIFY) | core-rbac | n/a | self (in-place extension) | exact |
| `apps/admin-web/.../session/can.ts` (MODIFY) | rbac-mirror | n/a | self (in-place extension) | exact |
| `apps/admin-web/.../session/registry.ts` (MODIFY) | rbac-mirror | n/a | self (in-place extension) | exact |
| `tests/integration/test_rbac_parity.py` (MODIFY) | test | static-analysis | self (count bump) | exact |
| `app/core/audit_models.py` (MODIFY) | model | n/a | `app/modules/payments/models.py:112-121` (`__table_args__`) | exact |
| `alembic/versions/0040_*.py` (NEW) | migration | n/a | `alembic/versions/0037_online_refunds.py` | role-match |
| `apps/backend/.importlinter` (MODIFY) | config | n/a | self (existing `modules =` list) | exact |
| `app/api/v1/router.py` (MODIFY, optional) | route-aggregation | n/a | self (`v1.include_router` pattern) | exact |

> Note on `service.py`/`repository.py`: D-06 lists both as scaffold stubs. In Phase 54 these are read-only stubs (no endpoint bodies — Phase 55). The repository is where the raw-SQL `text()` cross-module read pattern (D-08) is documented for Phase 55.

## Pattern Assignments

### `app/modules/reports/__init__.py` (module-doc)

**Analog:** `app/modules/payments/__init__.py` (full file, 14 lines)

Module docstring only — states phase reference, read-only discipline, and what is deferred. Mirror the payments shape but assert reports-specific invariants:

```python
"""Reports module — Phase 54 INFRA-41 scaffold (bodies land Phase 55).

Read-only aggregator (D-54-07): performs ZERO INSERT/UPDATE/DELETE on
business tables. The SVC001 commit-gate does not apply (no write paths).

Cross-module data is read via raw SQL `text()` SELECTs in repository.py
(D-54-08, Phase 49 D-49-03 precedent) — NOT by importing other modules'
ORM models. This keeps `modules-independent` clean with zero new
`ignore_imports` edges.

No models.py (reports own no tables); no email_templates.py (no notifications).
Endpoint bodies + query logic deferred to Phase 55.
"""
```

---

### `app/modules/reports/permissions.py` (rbac-factory, request-response)

**Analog:** `app/modules/payments/permissions.py` (full file, 64 lines)

REPORTS is owner-only via `(VIEW, REPORTS)` already in `OWNER_ONLY` (D-03), so the router can use the plain `require_permission(Action.VIEW, Resource.REPORTS)` chokepoint and may NOT need a custom factory. If a scoped reception-admitting factory is desired later (mirroring `require_payments_view_for_subject`), the import block + `audit.emit` denial shape is the template:

**Imports + factory shape** (`payments/permissions.py:15-61`):
```python
from __future__ import annotations
from collections.abc import Awaitable, Callable
from typing import Annotated
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core import audit
from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user
from app.core.exceptions import ForbiddenError
from app.core.permissions import Role
```

In Phase 54 the simplest compliant stub is a docstring-only module (the `require_permission` chokepoint covers VIEW/REPORTS at the router). Keep it minimal per D-Discretion.

---

### `app/modules/reports/constants.py` (constants)

**Analog:** `app/modules/payments/constants.py` (full file, 23 lines)

Literal string constants with an `__all__` tuple. Mirror the shape:
```python
"""Reports module literal constants (Phase 54 INFRA-41)."""

# e.g. period-grain / metric-key literals for Phase 55 query bodies
__all__: tuple[str, ...] = ()
```

---

### `app/modules/reports/router.py` (route, request-response)

**Analog:** `app/modules/payments/router.py` (full file, 109 lines)

**Imports + owner-only permission chokepoint** (`payments/router.py:18-47`):
```python
from __future__ import annotations
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission
from app.core.pagination import PaginatedData
from app.core.permissions import Action, Resource
from app.core.schemas import ResponseEnvelope, envelope

router = APIRouter()
```

**Owner-only endpoint guard** (`payments/router.py:43-47`) — REPORTS uses `(VIEW, REPORTS)`:
```python
_actor: Annotated[
    CurrentUser, Depends(require_permission(Action.VIEW, Resource.REPORTS))
],
```

In Phase 54 ship `router = APIRouter()` with no/stub endpoints (bodies = Phase 55). All real responses must return `ResponseEnvelope[...]` via `envelope(...)` (per payments).

---

### `app/modules/reports/repository.py` + `service.py` (raw-SQL read aggregator)

**Analog (raw-SQL cross-module read — THE D-08 precedent):** `app/modules/online_payments/service.py:116-171`

This is the canonical "read another module's table without importing its ORM" pattern. Copy it verbatim into `reports/repository.py` for Phase 55 bodies:

```python
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
```

Key invariants from this analog (must hold for reports):
- `from sqlalchemy import text` — never import the foreign ORM model.
- Bind params via `:name` + a dict; cast UUIDs to `str`.
- `.mappings().one_or_none()` for single-row reads; `.mappings().all()` for aggregates.
- Each raw reader carries a docstring listing the verified columns + source file/line of the foreign table (e.g. `app/modules/payments/models.py`, `app/core/audit_models.py`).

**ORM-based read analog (for pagination shape only):** `app/modules/online_payments/repository.py:61-69` shows the `select(...).where(...)` + `session.scalar(stmt)` form — use ONLY for `reports`-owned tables (there are none), so reports uses raw SQL exclusively.

In Phase 54 these are stubs: a module docstring asserting read-only + the raw-SQL discipline, no executable query bodies.

---

### `app/modules/reports/schemas.py` (schema, request-response)

**Analog:** `app/modules/payments/schemas.py` (full file)

**Imports + base** (`payments/schemas.py:14-22`):
```python
from __future__ import annotations
from pydantic import Field
from app.core.pagination import PageQuery
from app.core.schemas import BackendSchemaBase, ResponseData
```
- Query DTOs extend `PageQuery`; response DTOs extend `BackendSchemaBase` (inherits `extra='forbid'`).
- Wire form is camelCase; Python is snake_case (`subject_kind` ↔ `subjectKind`).

Phase 54: stub with module docstring + zero or placeholder schemas.

---

### `app/core/permissions.py` (MODIFY — core-rbac)

**Analog:** self, in-place. Source of truth for the three-way parity.

**Add to `Resource` StrEnum** (after `permissions.py:56`, mirroring the kebab multi-word convention of `OWNER_AREA`/`SCHEDULE_SLOTS`):
```python
    AUDIT_LOG = "audit-log"  # NEW Phase 54 INFRA-42 — kebab on wire (multi-word)
```

**Add to `OWNER_ONLY` frozenset** (D-04, two pairs; `Action.READ` NOT introduced — reuse VIEW + LIST per D-02):
```python
        # v1.8 (Phase 54 INFRA-42 / D-54-04) — audit-log read API is owner-only.
        # Reception has ZERO audit perms (403). Reuses Action.VIEW (filterable read)
        # + Action.LIST (paginated listing); no new Action value.
        (Action.VIEW, Resource.AUDIT_LOG),
        (Action.LIST, Resource.AUDIT_LOG),
```

`can()` body is unchanged (`permissions.py:128-137`). `Resource.REPORTS` + `(VIEW, REPORTS)` already shipped — do NOT re-add.

---

### `apps/admin-web/src/shared/session/can.ts` (MODIFY — rbac-mirror)

**Analog:** self, in-place. **Byte-for-byte mirror** of the backend OWNER_ONLY addition.

**Add to the `OWNER_ONLY` array** (after `can.ts:62`):
```typescript
  // v1.8 (Phase 54 INFRA-42 — audit-log read; reception has zero audit perms per D-54-04).
  // Reuses 'view' (filterable read) + 'list' (paginated listing); no new action value.
  { action: 'view', resource: 'audit-log' },
  { action: 'list', resource: 'audit-log' },
```

The parity regex `_PAIR_RE` requires the exact `{ action: '...', resource: '...' }` literal shape (single quotes) — match it precisely.

---

### `apps/admin-web/src/shared/session/registry.ts` (MODIFY — rbac-mirror)

**Analog:** self, in-place.

**Add to the `Resource` union** (after `registry.ts:24`, before the blank line that precedes `export type Action`):
```typescript
  | 'audit-log' // NEW Phase 54 INFRA-42 — mirror Resource.AUDIT_LOG.value; no sidebar entry in v1.8
```

`Action` union is UNCHANGED (no new action — D-02/D-05). Do NOT add a `routeRegistry` entry (audit-log has no sidebar surface in v1.8).

---

### `tests/integration/test_rbac_parity.py` (MODIFY — test)

**Analog:** self. The count assertion + docstrings bump 33 → 35.

**Rename/retarget the count test** (`test_rbac_parity.py:141-149`):
```python
def test_owner_only_count_is_thirty_five() -> None:
    """Sanity belt — `OWNER_ONLY` is exactly 35 entries.

    Breakdown: 9 v1.1 + 6 v1.2 + 11 v1.4 - 1 D-34-09a + 4 v1.5 + 4 v1.6
    + 2 v1.8 Phase 54 INFRA-42 (VIEW|LIST on AUDIT_LOG).
    """
    assert len(OWNER_ONLY) == 35
    assert len(_parse_owner_only_pairs()) == 35
```

Also update the module-header docstring counts (`test_rbac_parity.py:3-7`: "33 entries" → "35 entries" + add the v1.8 breakdown term). The three set-equality tests (`test_owner_only_pairs_match`, `test_resource_values_match`, `test_action_values_match`) need NO code change — they auto-pick the new enum/array members; only their inline docstring counts (e.g. ":115" "all 11 Resource") are stale comments that may be refreshed for accuracy.

---

### `app/core/audit_models.py` (MODIFY — model `__table_args__`)

**Analog (index-in-`__table_args__` with literal names + DESC via `text()`):** `app/modules/payments/models.py:112-121`

```python
Index("ix_payments_subject", "subject_kind", "subject_id"),
Index("ix_payments_received_by_user_id", "received_by_user_id"),
Index("ix_payments_received_at", text("received_at DESC")),
```

**Extend `AuditLog.__table_args__`** (`audit_models.py:66-72`) to add the 3 D-11 indexes (literal names, DESC via `text()`, single-column btree for filters):
```python
    __table_args__ = (
        Index(
            "ix_audit_log_actor_user_id_created_at",
            "actor_user_id",
            "created_at",
        ),
        # Phase 54 INFRA-43 / D-54-11 — report + Phase-56 pagination support.
        # Composite (created_at DESC, id DESC) fully covers the stable ordering.
        Index(
            "ix_audit_log_created_at",
            text("created_at DESC"),
            text("id DESC"),
        ),
        Index("ix_audit_log_action", "action"),
        Index("ix_audit_log_resource_type", "resource_type"),
    )
```
`text` is already imported (`audit_models.py:24`). The `__table_args__` MUST match the migration exactly so `alembic check` round-trips with no drift (D-12).

---

### `alembic/versions/0040_audit_log_report_indexes.py` (NEW — migration)

**Analog:** `alembic/versions/0037_online_refunds.py` (revision/down_revision discipline, literal index names, `text()` predicates)

**Confirmed current head:** `0039_payment_notifications` (verified: `ls alembic/versions/` shows 0035–0039; 0039 docstring confirms it is the latest). Set `down_revision = "0039_payment_notifications"`.

**Revision header pattern** (`0037:31-44`):
```python
from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from sqlalchemy import text
from alembic import op

revision: str = "0040_audit_log_report_indexes"
down_revision: str | None = "0039_payment_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**Literal index name + `text()` predicate pattern** (`0037:131-137` — `op.create_index` uses literal names, NOT `op.f()`):
```python
def upgrade() -> None:
    op.create_index(
        "ix_audit_log_created_at",
        "audit_log",
        [sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_resource_type", "audit_log", ["resource_type"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_resource_type", table_name="audit_log")
    op.drop_index("ix_audit_log_action", table_name="audit_log")
    op.drop_index("ix_audit_log_created_at", table_name="audit_log")
```
Do NOT touch `payments(received_at)` — `ix_payments_received_at` already exists (D-10).

---

### `apps/backend/.importlinter` (MODIFY — config)

**Analog:** self — the existing `modules =` list (`.importlinter:13-31`) under `[importlinter:contract:modules-independent]`.

**Add `app.modules.reports`** to the `modules =` list (alphabetical/grouped, preemptively per D-09 "contract before body"):
```ini
    app.modules.reports
    # Phase 54 INFRA-41 / D-54-09 — reports module registered preemptively
    # (INFRA-15 discipline, mirrors Phases 47/51). Read-only aggregator reads
    # cross-module data via raw SQL text() SELECTs (D-54-08 / Phase 49 D-49-03),
    # so it needs ZERO ignore_imports edges. unmatched_ignore_imports_alerting = warn
    # already cushions any timing gap before Phase 55 bodies land.
```
Add NO `ignore_imports` edges (D-08 — raw SQL means zero ORM cross-imports). `unmatched_ignore_imports_alerting = warn` is already set (`.importlinter:148`).

---

### `app/api/v1/router.py` (MODIFY — optional, route aggregation)

**Analog:** self — the `payments_router` import + `include_router` mount (`router.py:22, 50`).

If a `reports` router is mounted in Phase 54 (likely deferred to Phase 55 since there are no endpoints), the pattern is:
```python
from app.modules.reports.router import router as reports_router
...
v1.include_router(reports_router, prefix="/reports", tags=["reports"])
```
Phase 54 may leave this unmounted (empty router has no routes). Planner decides per scaffold-only scope.

## Shared Patterns

### Raw-SQL cross-module read (the load-bearing pattern for reports)
**Source:** `app/modules/online_payments/service.py:116-171`
**Apply to:** `reports/repository.py` (all cross-module reads against `payments`, `clients`, `visits`, `audit_log`, etc.)
- `from sqlalchemy import text`; never import the foreign module's ORM model.
- Bind params via `:name` placeholders + dict, UUIDs cast to `str`.
- `.mappings().one_or_none()` / `.mappings().all()`.
- Docstring each reader with verified columns + source file:line of the foreign table.
- Result: zero new `ignore_imports` edges, `modules-independent` stays GREEN.

### Index declaration (literal name + DESC)
**Source:** `app/modules/payments/models.py:120` + `alembic/versions/0037_online_refunds.py:131-137`
**Apply to:** `audit_models.py` `__table_args__` AND the new `0040` migration
- Literal string index names (NOT `op.f()`) for `op.create_index` / ORM `Index(...)`.
- DESC expressed via `text("col DESC")` / `sa.text("col DESC")`.
- ORM `__table_args__` and migration must agree so `alembic check` round-trips clean.

### Three-way RBAC parity (byte-for-byte mirror)
**Source:** `app/core/permissions.py` ⇔ `can.ts` ⇔ `registry.ts`, asserted by `tests/integration/test_rbac_parity.py`
**Apply to:** every RBAC change in this phase
- Backend `Resource`/`OWNER_ONLY` is the source of truth; `can.ts` (pairs) + `registry.ts` (unions) must mirror exactly.
- The parity regex requires the literal `{ action: '...', resource: '...' }` shape (single quotes).
- Bump the count assertion + docstrings whenever `OWNER_ONLY` size changes (33 → 35).

### FastAPI permission chokepoint
**Source:** `app/modules/payments/router.py:43-47`
**Apply to:** reports router endpoints (Phase 55)
- Owner-only reads use `Depends(require_permission(Action.VIEW, Resource.<X>))`.
- All responses wrapped in `ResponseEnvelope[...]` via `envelope(...)`; lists use `PaginatedData[T]`.

## No Analog Found

None. Every file in this phase maps to an existing analog (the project has 17 modules and 39 migrations; the slim-scaffold + raw-SQL-read + parity + index patterns are all well established).

## Metadata

**Analog search scope:** `apps/backend/app/modules/` (payments, online_payments, online_refunds), `apps/backend/app/core/`, `apps/backend/alembic/versions/`, `apps/backend/.importlinter`, `apps/backend/app/api/v1/`, `apps/admin-web/src/shared/session/`
**Files scanned:** ~14 read + targeted greps across modules/migrations
**Pattern extraction date:** 2026-05-24
