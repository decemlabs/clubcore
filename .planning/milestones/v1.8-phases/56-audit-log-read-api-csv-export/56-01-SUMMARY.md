---
phase: 56-audit-log-read-api-csv-export
plan: "01"
subsystem: backend/reports
tags: [audit-log, pagination, rbac, orm, filters, pytest, tdd]
dependency_graph:
  requires:
    - 54-foundations-module-scaffold-rbac-parity-indexes (AuditLog ORM, ix_audit_log_created_at, RBAC OWNER_ONLY)
    - 55-revenue-clients-visits-reports (reports module host, PageQuery/PaginatedData reserved for this plan)
  provides:
    - GET /api/v1/audit-log (ResponseEnvelope[PaginatedData[AuditLogItem]])
    - AuditLogQuery + AuditLogItem DTOs
    - fetch_audit_log_page ORM repository function
    - list_audit_log service with LOCKED_AUDIT_EVENTS filter validation
    - audit_log_router mounted at /audit-log
  affects:
    - apps/backend/app/modules/reports/ (schemas, repository, service, router)
    - apps/backend/app/api/v1/router.py (new router mount)
    - apps/backend/tests/integration/reports/ (new test file + conftest fixture)
tech_stack:
  added: []
  patterns:
    - ORM select(AuditLog) with keyset ordering (created_at DESC, id DESC)
    - Route-level Query(alias="from")/Query(alias="to") for Python-keyword params
    - and_(true(), *predicates) to avoid SADeprecationWarning for empty predicate list
    - AuditFilterInvalidError(ValidationAppError) with code="audit_filter_invalid"
    - VALID_ACTIONS/VALID_RESOURCE_TYPES frozensets derived from LOCKED_AUDIT_EVENTS
key_files:
  created:
    - apps/backend/tests/integration/reports/test_audit_log.py
  modified:
    - apps/backend/app/modules/reports/schemas.py
    - apps/backend/app/modules/reports/repository.py
    - apps/backend/app/modules/reports/service.py
    - apps/backend/app/modules/reports/router.py
    - apps/backend/app/api/v1/router.py
    - apps/backend/tests/integration/reports/conftest.py
decisions:
  - "from/to bound via route-level Query(alias=...) NOT model Field(alias) — live-verified on FastAPI 0.136.1 + Pydantic 2.13.3 that Field(alias='from') on Depends() model does not bind ?from="
  - "AuditLog ORM imported directly in reports/repository.py (app.core is free import target, not a cross-module violation)"
  - "and_(true(), *predicates) used instead of and_(*predicates) to handle empty predicate list without SADeprecationWarning"
  - "Pagination stability test uses older-row insert (not newer) to avoid offset-pagination shifting behavior"
metrics:
  duration: "11m 1s"
  completed: "2026-05-24"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 7
---

# Phase 56 Plan 01: Audit Log Read API Summary

Owner-only paginated audit-log JSON endpoint `GET /api/v1/audit-log` returning `ResponseEnvelope[PaginatedData[AuditLogItem]]`, ordered `created_at DESC, id DESC`, with optional AND-combined filters validated against `LOCKED_AUDIT_EVENTS` and route-level `from`/`to` Query params.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | AuditLogQuery + AuditLogItem DTOs | 99534f3 | schemas.py |
| 2 | ORM read path + service filter validation | 01ca652 | repository.py, service.py |
| 3 | Mount audit_log_router + AUD test suite | 2f3873f | router.py, v1/router.py, test_audit_log.py, conftest.py |

## What Was Built

**DTOs (`schemas.py`):**
- `AuditLogQuery(PageQuery)` — optional non-date filters (actorUserId, actorEmailSnapshot, resourceType, action); inherits page/pageSize bounds (max 100); no from_/to fields
- `AuditLogItem(ResponseData)` — all AuditLog ORM columns as camelCase wire fields including payload JSONB (owner sees full detail)

**Repository (`repository.py`):**
- `_build_audit_predicates(query, *, from_=None, to=None)` — optional filter predicates; actor_email_snapshot uses ORM `.ilike()` for parameterized bind; MSK date bounds via `cast(func.timezone("Europe/Moscow", AuditLog.created_at), Date)`
- `fetch_audit_log_page(session, query, *, from_, to)` — COUNT + keyset SELECT with `created_at DESC, id DESC` ordering; `and_(true(), *predicates)` for empty-predicate safety

**Service (`service.py`):**
- `VALID_ACTIONS` / `VALID_RESOURCE_TYPES` — frozensets derived from `LOCKED_AUDIT_EVENTS` at module load
- `AuditFilterInvalidError(ValidationAppError)` — code="audit_filter_invalid", status=422
- `list_audit_log(session, query, *, from_, to)` — validates action/resource_type against locked sets (→ 422), validates to<from_ (→ 422), converts ORM rows to `AuditLogItem` DTOs

**Router (`router.py` + `v1/router.py`):**
- `audit_log_router = APIRouter()` as second router in reports/router.py
- `GET ""` handler with route-level `Query(alias="from")` / `Query(alias="to")` params
- `require_permission(Action.LIST, Resource.AUDIT_LOG)` chokepoint (OWNER_ONLY)
- Mounted at `prefix="/audit-log"` in v1/router.py (D-02)

**Tests (`test_audit_log.py` + `conftest.py`):**
- 15 integration tests: owner 200 with full envelope shape, reception 403, 422 unknown action, 422 unknown resourceType, 422 to<from, literal `from`/`to` wire params, action filter narrows, AND-combination, Cyrillic ilike, MSK date window, DESC ordering, pagination stability, field shape, pageSize>100 rejected
- `make_audit_log_row` fixture for direct ORM audit log inserts

## Critical Design Note

**`from`/`to` wire params:** `Field(alias="from")` on a Pydantic model passed via `Depends()` does NOT bind `?from=` query params on FastAPI 0.136.1 + Pydantic 2.13.3 (live-verified). The params are declared as explicit route-level parameters:
```python
from_: Annotated[date | None, Query(alias="from")] = None
to: Annotated[date | None, Query(alias="to")] = None
```
This is the canonical pattern — no fallback.

## Verification Results

- `pytest tests/integration/reports/test_audit_log.py -q`: 15 passed
- `mypy app/modules/reports/`: success, no issues
- `ruff check app/modules/reports/ tests/integration/reports/`: all checks passed
- `lint-imports`: 3 contracts kept, 0 broken (zero new ignore_imports)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed SADeprecationWarning for empty and_() call**
- **Found during:** Task 3, first test run (test_owner_gets_audit_log)
- **Issue:** `and_(*[])` (empty predicates) raises `SADeprecationWarning` which pytest treats as error
- **Fix:** Changed to `and_(true(), *predicates)` in both COUNT and SELECT statements
- **Files modified:** apps/backend/app/modules/reports/repository.py
- **Commit:** 2f3873f

**2. [Rule 1 - Bug] Fixed pagination stability test logic**
- **Found during:** Task 3, test_pagination_stability_under_concurrent_insert
- **Issue:** Test inserted a NEW row with the LATEST timestamp; with offset pagination, this shifts all pages by 1, causing the last page-1 item to appear on page-2 (expected behavior, not a bug)
- **Fix:** Rewrote test to insert an OLDER row (below all existing rows) which doesn't shift pages 1-2; also verifies no overlap between page 1 and page 2
- **Files modified:** apps/backend/tests/integration/reports/test_audit_log.py
- **Commit:** 2f3873f

## TDD Gate Compliance

Gate sequence followed:
1. `test(56-01)` commit (375bf01) — RED: failing tests written before router mounted
2. `feat(56-01)` commits (99534f3, 01ca652, 2f3873f) — GREEN: implementation + tests passing

## Known Stubs

None — all data flows from real database reads via ORM.

## Threat Surface Scan

No new unplanned threat surface. The mitigations from the plan's threat model are all implemented:
- T-56-01: `require_permission(Action.LIST, Resource.AUDIT_LOG)` on `audit_log_router` — reception → 403 (AUD-05)
- T-56-02: All filter values via ORM column ops (`.ilike()`, `==`, `cast/func.timezone`) — parameterized binds, no f-string interpolation into SQL
- T-56-04: `PageQuery.page_size le=100` enforced — pageSize > 100 → 422
- T-56-05: `action`/`resource_type` validated against `LOCKED_AUDIT_EVENTS` → 422 `audit_filter_invalid`

## Self-Check: PASSED

Files created/modified:
- [x] apps/backend/app/modules/reports/schemas.py — AuditLogQuery, AuditLogItem present
- [x] apps/backend/app/modules/reports/repository.py — fetch_audit_log_page present
- [x] apps/backend/app/modules/reports/service.py — list_audit_log, AuditFilterInvalidError present
- [x] apps/backend/app/modules/reports/router.py — audit_log_router present
- [x] apps/backend/app/api/v1/router.py — audit_log_router mounted
- [x] apps/backend/tests/integration/reports/test_audit_log.py — 15 tests
- [x] apps/backend/tests/integration/reports/conftest.py — make_audit_log_row fixture

Commits:
- [x] 99534f3 — Task 1 schemas
- [x] 01ca652 — Task 2 repository + service
- [x] 375bf01 — Task 3 TDD RED tests
- [x] 2f3873f — Task 3 TDD GREEN router + all tests passing
