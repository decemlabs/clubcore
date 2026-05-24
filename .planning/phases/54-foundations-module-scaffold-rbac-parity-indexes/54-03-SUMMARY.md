---
phase: 54
plan: "03"
subsystem: backend-reports-module
tags: [scaffold, reports, import-linter, architecture]
dependency_graph:
  requires: []
  provides: [app.modules.reports scaffold, .importlinter registration]
  affects: [apps/backend/app/modules/reports/, apps/backend/.importlinter]
tech_stack:
  added: []
  patterns: [raw-SQL cross-module read (text()), modules-independent contract preemptive registration]
key_files:
  created:
    - apps/backend/app/modules/reports/__init__.py
    - apps/backend/app/modules/reports/permissions.py
    - apps/backend/app/modules/reports/constants.py
    - apps/backend/app/modules/reports/router.py
    - apps/backend/app/modules/reports/service.py
    - apps/backend/app/modules/reports/repository.py
    - apps/backend/app/modules/reports/schemas.py
  modified:
    - apps/backend/.importlinter
decisions:
  - "D-54-07: reports module is strictly read-only — no INSERT/UPDATE/DELETE on business tables; SVC001 commit-gate does not apply"
  - "D-54-08: cross-module reads use raw SQL text() SELECTs exclusively; no foreign ORM model imports; zero new ignore_imports edges"
  - "D-54-09: app.modules.reports registered in .importlinter modules-independent preemptively before Phase 55 bodies land (INFRA-15 discipline)"
metrics:
  duration_minutes: 8
  completed_date: "2026-05-24"
  tasks_completed: 2
  tasks_total: 2
  files_created: 7
  files_modified: 1
---

# Phase 54 Plan 03: Reports Module Scaffold + Import-Linter Registration Summary

Slim read-only `app/modules/reports/` scaffold (7 files) created and `app.modules.reports` registered in `.importlinter` modules-independent contract — `lint-imports` passes 3 kept / 0 broken with zero new `ignore_imports` edges.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create slim reports module scaffold (read-only stubs) | b879b31 | 7 new files under apps/backend/app/modules/reports/ |
| 2 | Register app.modules.reports in .importlinter and verify lint-imports | 04fd7df | apps/backend/.importlinter |

## What Was Built

**Task 1 — Reports module scaffold:**

7 stub files created under `apps/backend/app/modules/reports/`:

- `__init__.py` — module docstring asserting Phase 54 INFRA-41, read-only discipline (D-54-07), raw-SQL text() cross-module reads (D-54-08), no models.py / no email_templates.py, bodies deferred to Phase 55
- `router.py` — `APIRouter` scaffold with no endpoint bodies; documents planned Phase 55 surface (revenue/clients/visits GET + CSV export endpoints)
- `repository.py` — raw-SQL text() discipline documented with verbatim example from `online_payments/service.py:116-142` precedent; `sqlalchemy.text` imported for pattern documentation
- `service.py` — read-only aggregator role docstring; no executable bodies; SVC001 does not apply
- `constants.py` — `__all__: tuple[str, ...] = ()` stub; Phase 55 will add grain constants
- `schemas.py` — schema conventions documented (extends PageQuery / BackendSchemaBase, camelCase wire, kopecks money); no concrete DTOs yet
- `permissions.py` — owner-only chokepoint via `require_permission(Action.VIEW, Resource.REPORTS)` documented; no custom factory needed in Phase 54

No `models.py` (reports own no tables) and no `email_templates.py` (no notifications) created — per D-06.

**Task 2 — .importlinter registration:**

`app.modules.reports` added to the `modules =` list in `[importlinter:contract:modules-independent]` after `app.modules.users`, with comment explaining preemptive registration per INFRA-15 / D-54-09. Zero `ignore_imports` edges added for reports — raw-SQL discipline in repository.py avoids all ORM cross-imports.

## Verification Results

```
cd apps/backend && uv run lint-imports
Contracts: 3 kept, 0 broken.
```

- 7 files exist and import cleanly: `uv run python -c "import app.modules.reports.router, ..." → OK`
- models.py and email_templates.py are absent (confirmed)
- No write paths in module (session.add / session.commit / INSERT / UPDATE / DELETE = 0 actual code occurrences)
- router.py contains `APIRouter` (confirmed)
- repository.py references `text` from sqlalchemy (confirmed)
- `.importlinter` contains `app.modules.reports` (confirmed)
- Zero `reports ->` or `-> app.modules.reports` edges in `ignore_imports` (confirmed)
- 2 pre-existing warnings (unmatched online_payments ignore edges) are unchanged

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

All 7 files are intentional Phase 54 stubs. Phase 55 will add endpoint bodies and query logic. Stubs are expected per INFRA-41 scope:

| File | Stub | Reason |
|------|------|--------|
| router.py | No endpoint functions | Phase 54 scaffold only; bodies land in Phase 55 |
| repository.py | No executable query functions | Phase 54 scaffold; raw-SQL readers for revenue/clients/visits deferred to Phase 55 |
| service.py | No callable functions | Phase 54 scaffold; aggregator functions deferred to Phase 55 |
| schemas.py | No concrete DTO classes | Phase 54 scaffold; RevenueReportQuery etc. deferred to Phase 55 |
| constants.py | `__all__ = ()` | Phase 54 scaffold; grain/metric constants deferred to Phase 55 |

These stubs are intentional and do not prevent the plan's goal (INFRA-41: module exists + contract registered + lint-imports green). Phase 55 resolves all stubs.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries introduced in this plan. The router is empty (no routes mounted). No threat flags.

## Self-Check: PASSED

- `apps/backend/app/modules/reports/__init__.py` — FOUND
- `apps/backend/app/modules/reports/router.py` — FOUND
- `apps/backend/app/modules/reports/repository.py` — FOUND
- `apps/backend/app/modules/reports/service.py` — FOUND
- `apps/backend/app/modules/reports/schemas.py` — FOUND
- `apps/backend/app/modules/reports/constants.py` — FOUND
- `apps/backend/app/modules/reports/permissions.py` — FOUND
- `apps/backend/.importlinter` contains `app.modules.reports` — CONFIRMED
- Commit b879b31 — FOUND (Task 1)
- Commit 04fd7df — FOUND (Task 2)
- lint-imports: 3 kept, 0 broken — CONFIRMED
