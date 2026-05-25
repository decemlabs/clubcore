---
phase: 60-trainer-usage-report
plan: "02"
subsystem: reports/repository
tags: [reports, raw-sql, trainer-usage, cte, phase-60]
dependency_graph:
  requires: []
  provides: [fetch_trainer_usage]
  affects: [apps/backend/app/modules/reports/repository.py]
tech_stack:
  added: []
  patterns: [raw-sql text(), AT TIME ZONE Europe/Moscow, .mappings().all(), LEFT JOIN trainers no-is_active-filter]
key_files:
  created: []
  modified:
    - apps/backend/app/modules/reports/repository.py
decisions:
  - "Payment temporal column resolved as received_at (apps/backend/app/modules/payments/models.py:64) — CONTEXT.md L218 paid_at was a typo; codebase reality wins"
  - "Four CTE shape locked: session_agg, slot_agg, revenue_agg, payroll_agg with single top-level SELECT"
  - "revenue_agg groups by pt_packages.trainer_id (D-58-21 assigned-at-sale), not pt_sessions.trainer_id"
  - "payroll_agg uses period overlap (period_start <= :to_date AND period_end >= :from_date) with signed SUM"
  - "utilization_pct = NULL when published_slot_count = 0; 0.0 when slots exist but none booked"
metrics:
  duration: "7m 47s"
  completed: "2026-05-25"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 1
---

# Phase 60 Plan 02: fetch_trainer_usage Raw-SQL CTE Reader Summary

Single `async def fetch_trainer_usage(session, from_date, to_date)` added to the reports repository as a four-CTE raw-SQL reader over seven cross-module tables, with `received_at` as the payments temporal column and PITFALL 6/10/11/12 invariants locked in SQL.

## What Was Built

`fetch_trainer_usage` in `apps/backend/app/modules/reports/repository.py` (lines 97-269 post-edit). The function:

- Executes ONE SQL statement with four CTEs (`session_agg`, `slot_agg`, `revenue_agg`, `payroll_agg`) and a top-level `SELECT ... FROM trainers t LEFT JOIN ...`
- Returns `list[dict[str, object]]` with keys matching Plan 01's `TrainerUsageRow` field names verbatim
- Uses only `sqlalchemy.text()` — zero ORM imports from cross-module models
- Added to `__all__` alongside the existing readers

### SQL Location

`apps/backend/app/modules/reports/repository.py`, lines approximately 171–267 (the `text("""...""")` block).

CTE summary:
| CTE | Groups on | Period filter |
|-----|-----------|---------------|
| `session_agg` | `ps.trainer_id` | `(ps.performed_at AT TIME ZONE 'Europe/Moscow')::date BETWEEN :from_date AND :to_date` |
| `slot_agg` | `trainer_id` | `(start_time AT TIME ZONE 'Europe/Moscow')::date BETWEEN :from_date AND :to_date` |
| `revenue_agg` | `pkg.trainer_id` | `(p.received_at AT TIME ZONE 'Europe/Moscow')::date BETWEEN :from_date AND :to_date` |
| `payroll_agg` | `trainer_id` | `period_start <= :to_date AND period_end >= :from_date` |

Top-level SELECT joins `trainers t LEFT JOIN session_agg LEFT JOIN slot_agg LEFT JOIN revenue_agg LEFT JOIN payroll_agg` with no `is_active` filter.

### Docstring File:Line Enumeration

The function docstring enumerates every cross-module table with verified column file:line citations:

| Table | Source file | Lines cited |
|-------|-------------|-------------|
| `pt_sessions` | `apps/backend/app/modules/pt_sessions/models.py` | 52-111 |
| `pt_packages` | `apps/backend/app/modules/pt_packages/models.py` | 104-187 |
| `bookings` | `apps/backend/app/modules/bookings/models.py` | — |
| `trainer_availability_slots` | `apps/backend/app/modules/schedule/models.py` | 64-152 |
| `payments` | `apps/backend/app/modules/payments/models.py` | 44-121 |
| `trainer_payroll_accruals` | `apps/backend/app/modules/payroll/models.py` | 108-256 |
| `trainers` | `apps/backend/app/modules/trainers/models.py` | 23-43 |

### Payments Temporal Column Resolution

**`received_at`** — confirmed at `apps/backend/app/modules/payments/models.py:64-68`.

The CONTEXT.md L218 example uses `p.paid_at` — this is a typo in the illustrative SQL sketch. The binding fact is the v1.8 `fetch_revenue_buckets` discipline at `repository.py:75/77/85` which uses `received_at` in three SQL positions. The new `revenue_agg` CTE uses `received_at` verbatim. Post-edit `received_at` count in `repository.py` is **6** (pre-edit was 4: L67 docstring, L75, L77, L85; the new function docstring and revenue_agg CTE add 2 more).

### .importlinter Diff

Zero. Verified by `git diff --exit-code .importlinter` — the file is byte-stable.

## Acceptance Criteria Results

| Check | Result |
|-------|--------|
| `grep -c 'async def fetch_trainer_usage'` | 1 |
| `grep -c 'session_agg'` | 2 (CTE def + JOIN) |
| `grep -c 'slot_agg'` | 2 |
| `grep -c 'revenue_agg'` | 2 |
| `grep -c 'payroll_agg'` | 2 |
| `grep -c "AT TIME ZONE 'Europe/Moscow'"` | 11 (3 existing + 3 new in fetch_trainer_usage + 5 other functions) |
| `grep -c 'received_at'` | 6 (>= 5 required) |
| `grep -c 'period_start <= :to_date AND period_end >= :from_date'` | 1 |
| `grep -cE 'assigned.*at.*sale\|D-58-21'` | 3 |
| `grep -cE 'ORDER BY session_count DESC'` | 1 |
| `paid_at` in non-comment function body | 0 |
| `grep -E "WHERE.*t\.is_active\|WHERE.*t\.deleted_at"` | empty (PASS) |
| ORM cross-module imports | none (PASS) |
| `fetch_trainer_usage` in `__all__` | yes |
| `ruff check` | All checks passed |
| `mypy --strict` | Success: no issues |
| `lint-imports` | 3 kept, 0 broken (exit 0) |
| `git diff --exit-code .importlinter` | exit 0 (no changes) |

## Deviations from Plan

None — plan executed exactly as written.

The only minor adjustment: removed an unused `# noqa: S608` comment from the `text(` call (ruff correctly identified it as unused since the SQL template is a static triple-quoted string with no f-string interpolation — unlike `fetch_revenue_buckets` which uses an f-string for `period_expr`).

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. This plan adds only a repository function (read-only SQL). Threat mitigations T-60-04, T-60-05, T-60-06 are satisfied:

- T-60-04 (SQL injection): static template + bind params only; no f-string interpolation of user input.
- T-60-05 (information disclosure): read-only function; no INSERT/UPDATE/DELETE; no PII beyond `full_name` display field.
- T-60-06 (import-linter bypass): zero `from app.modules.*.models import`; `lint-imports` green.

## Self-Check: PASSED

- `apps/backend/app/modules/reports/repository.py` present in worktree: confirmed
- Commit `b75b560b` exists: confirmed
- `fetch_trainer_usage` in `__all__`: confirmed
- All grep acceptance criteria met: confirmed
- ruff + mypy strict + lint-imports all green: confirmed
- `.importlinter` unchanged: confirmed
