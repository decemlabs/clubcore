---
phase: 58-payroll-foundations-ledger
plan: "09"
subsystem: payroll
tags: [payroll, clawback, pt-packages, protocol-slot, tdd, append-only-ledger]
dependency_graph:
  requires: [58-07, 58-08]
  provides: [PAY-06]
  affects: [pt_packages.service.refund_pt_package, payroll.service, payroll.repository, app.core.dependencies]
tech_stack:
  added: []
  patterns:
    - PayrollClawbackRecorder Protocol slot (seventeenth composition-root carve-out)
    - Caller-owns-txn slot pattern (mirrors PaymentRefunder)
    - Append-only negative clawback row (D-58-03 immutability)
    - Assigned-at-sale attribution (pt_package.trainer_id passed by caller, D-58-21)
key_files:
  created:
    - apps/backend/tests/integration/payroll/test_payroll_clawback.py
  modified:
    - apps/backend/app/core/dependencies.py
    - apps/backend/app/modules/payroll/repository.py
    - apps/backend/app/modules/payroll/service.py
    - apps/backend/app/main.py
    - apps/backend/app/modules/pt_packages/service.py
decisions:
  - "Clawback amount = abs(original.accrual_kopecks) — full-package reversal in v1.9; partial deferred to B-02"
  - "find_paid_accrual_covering_refund selects the most recent (by accrued_at DESC) paid regular accrual whose period covers any non-cancelled session MSK-date of the refunded package"
  - "Tests wire real slot via register_payroll_clawback_recorder in conftest _client_app_overrides, mirroring production main.py"
metrics:
  duration: "~35 minutes"
  completed: "2026-05-25"
  tasks_completed: 5
  tasks_total: 5
  files_created: 1
  files_modified: 5
---

# Phase 58 Plan 09: PAY-06 PT-Package Refund → Payroll Clawback Hook Summary

**One-liner:** PayrollClawbackRecorder Protocol slot wires a same-UoW negative clawback accrual INSERT into the PT-package refund flow — append-only, audit-logged, zero new import-linter edges.

## What Was Built

PAY-06 delivers financial integrity: when a PT-package refund occurs after the trainer's accrual period has been marked paid, a NEGATIVE clawback row is appended to `trainer_payroll_accruals` in the same UoW as the refund. The original paid accrual is never mutated (D-58-03 immutability). The full implementation spans 5 files:

1. **`app/core/dependencies.py`** — `PayrollClawbackRecorder` Protocol + `register_payroll_clawback_recorder` + `get_payroll_clawback_recorder` (seventeenth composition-root carve-out, mirroring `PaymentRefunder` exactly).

2. **`app/modules/payroll/repository.py`** — two new helpers:
   - `find_paid_accrual_covering_refund(session, *, trainer_id, pt_package_id) -> TrainerPayrollAccrual | None` — raw SQL text() cross-module read returning the most recent status='paid' regular accrual whose period covers a non-cancelled session MSK-date of the package (no ORM imports from other modules).
   - `insert_clawback_accrual(session, *, original_accrual, refund_payment_id, clawback_kopecks) -> UUID` — INSERT negative row reusing original snapshot columns; flush (no commit — caller owns UoW); paired FK CHECK satisfied.

3. **`app/modules/payroll/service.py`** — `record_clawback_for_pt_package_refund` slot implementation matching the Protocol signature. Returns None for NULL `pt_package_trainer_id` (non-commissionable, D-58-21) or when no paid accrual covers the package. Emits `payroll_clawback_recorded` audit before the caller's commit (D-58-17).

4. **`app/main.py`** — `register_payroll_clawback_recorder(payroll_service.record_clawback_for_pt_package_refund)` added alongside `register_payment_refunder` (HTTP-only single-wire per D-32-14 discipline).

5. **`app/modules/pt_packages/service.py`** — `get_payroll_clawback_recorder()` called at step 6b (between `pt_package_refunded` audit emit and `session.commit()`). Imports only `get_payroll_clawback_recorder` from `app.core.dependencies` — zero `app.modules.payroll` imports.

## Tests

`tests/integration/payroll/test_payroll_clawback.py` — 5 new tests (TDD RED→GREEN):

1. **Full flow**: sell PT-package + seed paid accrual + refund → clawback row with correct FKs and negative `accrual_kopecks`.
2. **Immutability**: original paid accrual unchanged (`status`, `accrual_kopecks`, `clawback_of_accrual_id` all assert stable).
3. **No paid accrual**: refund with no covering accrual → zero clawback rows.
4. **NULL trainer_id**: non-commissionable package → zero clawback rows.
5. **Audit**: `payroll_clawback_recorded` row emitted in the same transaction.

All 42 payroll integration tests pass. `test_audit_taxonomy.py` still asserts count == 89. Existing pt_packages refund tests (14) all pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ruff UP037 — quoted type annotations in repository.py**
- **Found during:** Task 3 (ruff check after implementation)
- **Issue:** `find_paid_accrual_covering_refund` return type was `"TrainerPayrollAccrual | None"` (quoted); `insert_clawback_accrual` parameter `original_accrual` was `"TrainerPayrollAccrual"` (quoted). UP037 requires unquoted with `from __future__ import annotations` present.
- **Fix:** Removed quotes from both annotations.
- **Files modified:** `apps/backend/app/modules/payroll/repository.py`
- **Commit:** 67bd7092

**2. [Rule 1 - Bug] Ruff E501 — line too long in service.py**
- **Found during:** Task 3 (ruff check)
- **Issue:** Two lines exceeded 100 chars in `record_clawback_for_pt_package_refund` docstring and inline comment.
- **Fix:** Shortened docstring title line and inline comment.
- **Files modified:** `apps/backend/app/modules/payroll/service.py`
- **Commit:** 67bd7092

### TDD Note

Task 3 followed the RED→GREEN order mandated by the plan. The RED commit (`ca7a668f`) came first (tests fail because the slot didn't exist); Task 4 wiring was required to complete GREEN (`67bd7092 + 8cbea6f9`) because the conftest fixture calls `register_payroll_clawback_recorder` before the slot is wired in `refund_pt_package`. All 5 tests are green after both Task 3 and Task 4 are landed.

## SC#5 Reconciliation

**Projected:** ROADMAP SC#5 ("Success Criteria #5") projected **6 new LOCKED_AUDIT_EVENTS** for Phase 58.

**Delivered:** **4 events** — pre-registered in plan 58-01:
1. `trainer_comp_config_set` / `trainer_comp_config` (PAY-01)
2. `payroll_accrual_created` / `payroll_accrual` (PAY-03)
3. `payroll_accrual_paid` / `payroll_accrual` (PAY-04)
4. `payroll_clawback_recorded` / `payroll_accrual` (PAY-06 — this plan)

**Why 4 not 6:** The 2 unallocated events were a roadmap over-estimate from the initial design phase. The projected events were `(EDIT, COMPENSATION)` and one more unnamed event, which were superseded when 58-01 collapsed the event design to `(CREATE, COMPENSATION)` = `trainer_comp_config_set` only. Preview (PAY-02) and list (PAY-05) emit nothing (read-only). Mark-paid reuses `payroll_accrual_paid`; clawback reuses `payroll_clawback_recorded`. D-58-16 explicitly allows "≤6" events, so 4 is within spec.

**Action for milestone verifier (Phase 61):** ROADMAP SC#5 "6 new LOCKED_AUDIT_EVENTS" should read "4" or carry a footnote: "2 projected events were not needed — preview + list are zero-emit, mark-paid + clawback reuse the accrual event namespace." `test_audit_taxonomy.py` count == 89 is correct; no dead events were invented.

## Verification Results

```
pytest tests/integration/payroll/test_payroll_clawback.py tests/unit/test_audit_taxonomy.py  → 12 passed
pytest tests/integration/payroll/                                                              → 42 passed
pytest tests/integration/pt_packages/test_pt_package_refund.py test_pt_package_refund_race.py → 14 passed
lint-imports --config .importlinter                                                            → all KEPT (0 broken)
mypy app/core/dependencies.py app/modules/payroll/ app/modules/pt_packages/service.py         → clean
grep "from app.modules.payroll" app/modules/pt_packages/service.py                            → (empty — zero direct imports)
```

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 0a7d70ca | feat(58-09): PayrollClawbackRecorder Protocol slot in dependencies.py |
| 2 | c71c5899 | feat(58-09): clawback repository helpers in payroll/repository.py |
| 3 RED | ca7a668f | test(58-09): add failing PAY-06 clawback integration tests (RED) |
| 4 | 8cbea6f9 | feat(58-09): register slot in main.py + wire hook in refund_pt_package |
| 3 GREEN | 67bd7092 | feat(58-09): implement record_clawback_for_pt_package_refund slot + fix ruff |

## Self-Check: PASSED

- [x] `apps/backend/tests/integration/payroll/test_payroll_clawback.py` — exists
- [x] `apps/backend/app/core/dependencies.py` — contains `PayrollClawbackRecorder`
- [x] `apps/backend/app/modules/payroll/service.py` — contains `record_clawback_for_pt_package_refund`
- [x] `apps/backend/app/modules/payroll/repository.py` — contains `insert_clawback_accrual`
- [x] `apps/backend/app/main.py` — contains `register_payroll_clawback_recorder`
- [x] `apps/backend/app/modules/pt_packages/service.py` — contains `get_payroll_clawback_recorder`
- [x] Commits 0a7d70ca, c71c5899, ca7a668f, 8cbea6f9, 67bd7092 verified in git log
