---
phase: 60-trainer-usage-report
plan: "03"
subsystem: reports
tags: [backend, reports, trainer-usage, csv-export, rbac]
dependency_graph:
  requires: [60-01, 60-02]
  provides: [GET /api/v1/reports/trainers, GET /api/v1/reports/trainers.csv]
  affects: [apps/backend/app/modules/reports/service.py, apps/backend/app/modules/reports/router.py]
tech_stack:
  added: []
  patterns:
    - "thin orchestrator service pattern (validate → fetch → assemble)"
    - "CSV row-builder reusing orchestrator (D-15 reuse precedent)"
    - "StreamingResponse with UTF-8 BOM via make_csv_streaming_response"
key_files:
  created: []
  modified:
    - apps/backend/app/modules/reports/service.py
    - apps/backend/app/modules/reports/router.py
decisions:
  - "Handler function named get_trainers_report (not get_trainer_usage_report) to avoid namespace shadowing with service symbol"
  - "sanitize_csv_text applied ONLY to trainer_name_snapshot; numeric/money columns unsanitized per D-60-11"
  - "None/NULL utilization_pct and avg_revenue_per_session render as empty string (not 'None')"
  - "CSV filename: trainer-usage-{from_date.isoformat()}-{to_date.isoformat()}.csv per EXP-01 precedent"
metrics:
  duration: "resumed from prior agent (cherry-pick + Task 2)"
  completed: "2026-05-25"
  tasks_completed: 2
  files_modified: 2
requirements: [RPT-01, RPT-02, RPT-03]
---

# Phase 60 Plan 03: Trainer-Usage Service + Router Summary

**One-liner:** JWT-gated GET /trainers JSON and GET /trainers.csv endpoints wired to trainer-usage orchestrator via existing (VIEW, REPORTS) OWNER_ONLY dependency — zero new RBAC tuples, ruff + mypy strict green.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add get_trainer_usage_report + trainer_usage_csv_rows to service.py | 9c4dbfcc (cherry-picked from worktree-agent-a2c13f5014c8cd54a) | apps/backend/app/modules/reports/service.py |
| 2 | Add GET /trainers JSON + GET /trainers.csv routes to router.py | 3e4daa31 | apps/backend/app/modules/reports/router.py |

## What Was Built

### service.py additions

**`get_trainer_usage_report(session, query: TrainerUsageReportQuery) -> TrainerUsageReportResponse`**
- Calls `_validate_date_range(query.from_date, query.to_date)` — raises ValidationAppError (to<from) or ReportRangeTooLargeError (range>366d)
- Calls `await repository.fetch_trainer_usage(session, from_date, to_date)` (Plan 02 CTE reader)
- Assembles `TrainerUsageReportResponse(trainers=[TrainerUsageRow.model_validate(row) for row in rows], ...)` with TRAINER_REPORT_REVENUE_NOTE from constants
- Read-only invariant: zero session.commit() / session.flush()

**`trainer_usage_csv_rows(session, query: TrainerUsageReportQuery) -> list[list[object]]`**
- Reuses `get_trainer_usage_report` (D-15 reuse precedent)
- Maps each `TrainerUsageRow` to 10-element list matching `CSV_TRAINER_USAGE_HEADERS` column order
- `sanitize_csv_text(row.trainer_name_snapshot)` — formula-injection guard, ONLY on the free-text column (D-60-11)
- `None` → empty string for `utilization_pct` and `avg_revenue_per_session` (D-60-11)
- `format_kopecks_as_rubles(...)` for all kopeck columns — signed for clawbacks, not sanitized (D-60-11)

### router.py additions

**`GET /trainers` (JSON)**
- Handler: `get_trainers_report` (name differs from service symbol to avoid shadowing)
- `response_model=ResponseEnvelope[TrainerUsageReportResponse]`
- `tags=["reports"]`, full OpenAPI `summary`, `description`, `responses={403, 422}` (D-60-12)
- Body: `result = await service.get_trainer_usage_report(session, query); return envelope(result)`

**`GET /trainers.csv` (CSV)**
- Handler: `get_trainers_csv`
- `response_class=StreamingResponse`, no `response_model`
- Full OpenAPI `summary`, `description`, `tags=["reports"]`
- Filename computed in handler: `trainer-usage-{query.from_date.isoformat()}-{query.to_date.isoformat()}.csv`
- Body: `rows = await service.trainer_usage_csv_rows(session, query); return csv_export.make_csv_streaming_response(iter(rows), CSV_TRAINER_USAGE_HEADERS, filename)`

Both endpoints:
- `dependencies=[require_permission(Action.VIEW, Resource.REPORTS)]` — pre-existing OWNER_ONLY pair at permissions.py:65
- Mounted on `router = APIRouter()` (NOT `audit_log_router`)
- No try/except — AppError bubbles to registered handler

## Verification Results

- `ruff check apps/backend/app/modules/reports/router.py` — exit 0
- `uv run mypy --strict app/modules/reports/router.py` — exit 0 (no issues)
- Route introspection (via Python import of reports router): `/trainers` and `/trainers.csv` both registered
- `lint-imports` — exit 0 (3 contracts kept, 0 broken)

## Protected Files Verification

| File | Status |
|------|--------|
| `apps/backend/.importlinter` | UNCHANGED (git diff exit 0) |
| `apps/backend/app/core/permissions.py` | UNCHANGED (git diff exit 0) |
| `apps/admin-web/src/shared/session/can.ts` | UNCHANGED (git diff exit 0) |
| `apps/admin-web/src/shared/session/registry.ts` | UNCHANGED (git diff exit 0) |

## OpenAPI Metadata (Phase 61 HND-01 Reference)

**GET /trainers**
- summary: `"Trainer-usage report (owner-only; RPT-01..02, RPT-04)"`
- description: Per-trainer aggregate for [fromDate, toDate] MSK: session counts, hours, unique clients, utilization %, revenue, accrued vs paid compensation...

**GET /trainers.csv**
- summary: `"Trainer-usage CSV download (owner-only; RPT-03)"`
- description: Stream trainer-usage report as UTF-8 BOM + RFC-4180 CSV...

**CSV Filename Template:** `trainer-usage-{from_date.isoformat()}-{to_date.isoformat()}.csv`
Example: `trainer-usage-2025-01-01-2025-01-31.csv`

## Deviations from Plan

None — plan executed exactly as written. The cherry-pick of `2a9c6e86` recovered Task 1 cleanly; Task 2 implemented per spec with no rule triggers.

**Execution note:** This was a resume execution. The previous agent (worktree-agent-a2c13f5014c8cd54a) completed Task 1 (commit 2a9c6e86) before being interrupted by an API certificate error. Task 1's work was recovered via `git cherry-pick 2a9c6e86` into this worktree.

## Known Stubs

None — all service calls are wired through real repository/CSV functions; no hardcoded empty values or placeholders.

## Threat Flags

None — both endpoints are gated by the pre-existing OWNER_ONLY (VIEW, REPORTS) pair. No new network surface beyond the two planned routes.

## Self-Check: PASSED

- `apps/backend/app/modules/reports/service.py` — modified (cherry-picked, commit 9c4dbfcc)
- `apps/backend/app/modules/reports/router.py` — modified (commit 3e4daa31)
- Commits verified: `git log --oneline | grep -E "(9c4dbfcc|3e4daa31)"` — both present
- Protected files: .importlinter, permissions.py, can.ts, registry.ts — all unchanged
