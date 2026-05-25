---
phase: 58-payroll-foundations-ledger
plan: "07"
subsystem: payroll
tags: [payroll, accrual, mark-paid, append-only, on-conflict, for-update, tdd, audit]
dependency_graph:
  requires: [58-06]
  provides: [PAY-03, PAY-04]
  affects: [payroll-module, trainer_payroll_accruals-table, audit_log]
tech_stack:
  added: []
  patterns:
    - INSERT ON CONFLICT DO NOTHING RETURNING (DB-wins-the-race idempotency, D-58-06)
    - SELECT FOR UPDATE row-lock for single-transition lifecycle (D-58-08)
    - compute_accrual_components reuse (PITFALL 1 prevention — no recompute drift)
    - router-layer 422 remap for CompConfigMissingError (same pattern as 58-06 preview)
    - audit-before-commit (D-58-17 atomic chain in both orchestrators)
    - TDD RED/GREEN for PAY-03/04 endpoints
key_files:
  created:
    - apps/backend/tests/integration/payroll/test_payroll_accruals.py
  modified:
    - apps/backend/app/modules/payroll/repository.py
    - apps/backend/app/modules/payroll/service.py
    - apps/backend/app/modules/payroll/router.py
decisions:
  - "ON CONFLICT DO NOTHING RETURNING on partial UNIQUE uq_trainer_payroll_accruals_period_alive — DB wins the race, no SELECT-then-INSERT (T-58-27 / D-58-06)"
  - "run_payroll_period calls fetch_trainer_session_revenue a second time to get revenue_kopecks for snapshot; this is a cheap read-only cross-module query and avoids breaking compute_accrual_components API (which does not expose revenue_kopecks separately)"
  - "router-layer 422 remap: CompConfigMissingError (404) → _CompConfigMissing422Error (422) on POST /accruals, same pattern as GET /preview (D-58-07 / D-58-09)"
  - "AlreadyPaidError and PayrollPeriodAlreadyRunError propagate through AppError handler to 409; no explicit router-level catch needed"
  - "mark_accrual_paid uses datetime.now(_MSK) for paid_at (project MSK timezone discipline)"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-25T12:38:00Z"
  tasks_completed: 3
  files_modified: 4
---

# Phase 58 Plan 07: PAY-03 + PAY-04 Accrual Record + Mark-Paid Summary

PAY-03 and PAY-04 delivered: append-only payroll ledger with run-time-snapshotted rate/config; duplicate-period 409; pending→paid single-transition lifecycle with row-lock; atomic audit trail before commit.

## What Was Built

### Task 1: insert_accrual_on_conflict + select_accrual_for_update (repository.py)

Added two functions to `payroll/repository.py`:

**`insert_accrual_on_conflict(...) -> UUID | None`**

Uses `pg_insert(TrainerPayrollAccrual).values(...).on_conflict_do_nothing(index_elements=[trainer_id, period_start, period_end], index_where=TrainerPayrollAccrual.clawback_of_accrual_id.is_(None)).returning(TrainerPayrollAccrual.id)`.

- `index_where` exactly matches the partial UNIQUE constraint `uq_trainer_payroll_accruals_period_alive` — covers only live (non-clawback) rows.
- Returns `UUID` on successful insert, `None` when ON CONFLICT suppresses the insert (DB-wins-the-race, D-58-06).
- No pre-flight SELECT before INSERT (T-58-27 / no TOCTOU).
- Does NOT commit — caller owns transaction (SVC001).

**`select_accrual_for_update(session, accrual_id) -> TrainerPayrollAccrual | None`**

Standard `select(TrainerPayrollAccrual).where(id=accrual_id).with_for_update()` — own-module ORM read for the mark-paid row-lock path (D-58-08 / T-58-30).

### Task 2: run_payroll_period + mark_accrual_paid + exception classes (service.py)

Added three exception classes:
- `PayrollPeriodAlreadyRunError(ConflictError)` — code `payroll_period_already_run`, HTTP 409 (D-58-06)
- `AlreadyPaidError(ConflictError)` — code `already_paid`, HTTP 409 (D-58-08)
- `AccrualNotFoundError(NotFoundError)` — code `not_found`, HTTP 404 (D-58-08)

**`run_payroll_period(session, actor, body) -> TrainerPayrollAccrual`** (PAY-03 / D-58-03):
1. `compute_accrual_components(...)` — PITFALL 1 reuse (byte-identical numbers to preview; T-58-23). Raises `CompConfigMissingError` on no/both-NULL config → router remaps to 422.
2. `repository.fetch_trainer_session_revenue(...)` — second call to get `revenue_kopecks` for snapshot (read-only, cheap).
3. `repository.insert_accrual_on_conflict(...)` — snapshot columns frozen at INSERT time (D-58-03); if None → `PayrollPeriodAlreadyRunError`.
4. `session.get(TrainerPayrollAccrual, accrual_id)` — fetch full row.
5. `audit.emit("payroll_accrual_created", ...)` BEFORE commit — literal strings pass INFRA-11 AST gate; UUIDs str()-cast (58-05 lesson).
6. `session.commit()` (SVC001).

**`mark_accrual_paid(session, actor, accrual_id) -> TrainerPayrollAccrual`** (PAY-04 / D-58-08):
1. `repository.select_accrual_for_update(...)` — row lock; None → `AccrualNotFoundError` (404).
2. Status guard: `status == 'paid'` → `AlreadyPaidError` (409 already_paid).
3. Mutate: `status = 'paid'`, `paid_at = datetime.now(_MSK)`, `paid_by_user_id = actor.id`; flush.
4. `audit.emit("payroll_accrual_paid", ...)` BEFORE commit — literal strings (INFRA-11).
5. `session.commit()` (SVC001). NO unpay function.

### Task 3: POST /accruals + POST /accruals/{id}/mark-paid + PAY-03/04 tests

Added to `payroll/router.py`:
- `POST /accruals` — `require_permission(Action.CREATE, Resource.PAYROLL)`, returns 201 `ResponseEnvelope[PayrollAccrualResponse]`. CompConfigMissingError → _CompConfigMissing422Error router remap.
- `POST /accruals/{accrual_id}/mark-paid` — `require_permission(Action.EDIT, Resource.PAYROLL)`, returns 200 `ResponseEnvelope[PayrollAccrualResponse]`.

**Integration tests** (`test_payroll_accruals.py`): 12 tests, all pass.

| Test | Coverage |
|------|----------|
| `test_post_accrual_happy_path` | 201 + snapshotted fields + status 'pending' |
| `test_post_accrual_duplicate_period_returns_409` | 409 payroll_period_already_run |
| `test_post_accrual_no_config_returns_422` | 422 comp_config_missing |
| `test_post_accrual_both_null_config_returns_422` | both-NULL config → 422 |
| `test_post_accrual_snapshot_immutability` | config edit after accrual → snapshots unchanged (D-58-03) |
| `test_post_accrual_reception_forbidden` | 403 (T-58-26) |
| `test_post_accrual_audit_row_created` | payroll_accrual_created audit row via SQL SELECT |
| `test_mark_paid_happy_path` | 200 + status 'paid' + paid_at + paid_by_user_id |
| `test_mark_paid_second_attempt_returns_409` | 409 already_paid (D-58-08 / T-58-30) |
| `test_mark_paid_reception_forbidden` | 403 (T-58-26) |
| `test_mark_paid_nonexistent_accrual_returns_404` | 404 not_found |
| `test_mark_paid_audit_row_created` | payroll_accrual_paid audit row via SQL SELECT |

## TDD Gate Compliance

| Gate | Status |
|------|--------|
| RED commit (`test(58-07)`) | `40af9e36` — 12 tests failing with 404 (endpoints absent) |
| GREEN commit (`feat(58-07)`) | `f9d07d67` — all 12 tests pass |
| REFACTOR | Not needed — code is clean after ruff autofix during GREEN |

## Deviations from Plan

**1. [Rule 1 - Bug] Unused variable names in run_payroll_period**
- **Found during:** Task 2 GREEN implementation (ruff check)
- **Issue:** `fixed_kopecks` and `commission_kopecks` from `compute_accrual_components` tuple unpack were not used
- **Fix:** Prefixed with underscore (`_fixed_kopecks`, `_commission_kopecks`)
- **Files modified:** `app/modules/payroll/service.py`
- **Impact:** None — total_kopecks is the sum already computed by the helper

**2. [Rule 1 - Bug] Redundant local `datetime` import in two functions**
- **Found during:** Task 2 GREEN implementation (ruff check)
- **Issue:** `from datetime import datetime` inside functions was redundant after adding `from datetime import date, datetime` at module level
- **Fix:** Moved to module-level import; removed local imports
- **Files modified:** `app/modules/payroll/service.py`

**3. [Rule 1 - Bug] Test used `data["accrued_at"]` instead of camelCase `data["accruedAt"]`**
- **Found during:** Task 2 GREEN phase first test run
- **Issue:** `BackendSchemaBase` emits camelCase wire format; test assertion used snake_case key
- **Fix:** Changed assertion to `data.get("accruedAt") is not None`
- **Files modified:** `tests/integration/payroll/test_payroll_accruals.py`

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes outside the plan's threat model. Both POST endpoints are within the planned threat surface (T-58-26 through T-58-30 all mitigated as planned):
- T-58-26: `require_permission` OWNER_ONLY — reception 403 tests confirm
- T-58-27: ON CONFLICT DO NOTHING RETURNING — no TOCTOU; 409 on duplicate
- T-58-28: Snapshot immutability test passes
- T-58-29: audit_log row assertions for both events
- T-58-30: SELECT FOR UPDATE + second attempt 409 test passes

## Known Stubs

None — all response fields are populated from real DB data.

## Self-Check: PASSED

Files exist:
- `apps/backend/app/modules/payroll/repository.py` — contains `insert_accrual_on_conflict` and `select_accrual_for_update` ✓
- `apps/backend/app/modules/payroll/service.py` — contains `run_payroll_period` and `mark_accrual_paid` ✓
- `apps/backend/app/modules/payroll/router.py` — contains `/accruals` and `/accruals/{accrual_id}/mark-paid` ✓
- `apps/backend/tests/integration/payroll/test_payroll_accruals.py` — 12 tests, all pass ✓

Commits verified: 4349b67f, 40af9e36, f9d07d67 — all present in git log.

## Commits

| Task | Hash | Message |
|------|------|---------|
| Task 1: repository writers | `4349b67f` | feat(58-07): add insert_accrual_on_conflict + select_accrual_for_update to repository.py |
| Task 2 RED: failing tests | `40af9e36` | test(58-07): add failing PAY-03/04 integration tests (RED phase) |
| Task 2+3 GREEN: service + router + tests pass | `f9d07d67` | feat(58-07): add run_payroll_period + mark_accrual_paid + PAY-03/04 endpoints (GREEN phase) |
