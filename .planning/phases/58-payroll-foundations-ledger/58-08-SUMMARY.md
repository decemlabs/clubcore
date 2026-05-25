---
phase: 58-payroll-foundations-ledger
plan: "08"
subsystem: payroll
tags: [payroll, accruals, pagination, owner-only, list-endpoint]
dependency_graph:
  requires: [58-07]
  provides: [PAY-05-list-accruals-endpoint]
  affects: [payroll-module, payroll-repository, payroll-service, payroll-router]
tech_stack:
  added: []
  patterns:
    - PaginatedData[PayrollAccrualResponse] pagination envelope
    - PageQuery (page/pageSize with le=100 bound) for resource exhaustion protection
    - Two-query pattern (list + count) for paginated list with total
key_files:
  created:
    - apps/backend/tests/integration/payroll/test_payroll_list.py
  modified:
    - apps/backend/app/modules/payroll/repository.py
    - apps/backend/app/modules/payroll/service.py
    - apps/backend/app/modules/payroll/router.py
    - apps/backend/tests/integration/payroll/conftest.py
decisions:
  - "PageQuery reused (page/pageSize, max 100) — no custom pagination validator needed (T-58-32 mitigated)"
  - "No status/period filter params added — explicitly deferred per D-58-14"
  - "accrued_at param added to make_accrual fixture for deterministic ordering in tests"
metrics:
  duration: "9 minutes"
  completed: "2026-05-25T12:49:06Z"
  tasks_completed: 3
  files_changed: 5
---

# Phase 58 Plan 08: PAY-05 Paginated Accrual List Summary

**One-liner:** Owner-only GET /api/v1/payroll/accruals with PaginatedData[PayrollAccrualResponse] envelope, accrued_at DESC ordering, trainer_id scoping, clawback row visibility, and PageQuery-bounded pagination.

## What Was Built

PAY-05 (D-58-14): paginated listing of a trainer's payroll accruals, ordered accrued_at DESC, returning the project-standard `{items, total, page, pageSize}` envelope. Both regular (positive) and clawback (negative accrual_kopecks) rows surface alongside paid/pending rows with their status visible. Owner-only (LIST, PAYROLL) — reception receives 403.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | list_accruals_for_trainer + count_accruals in repository.py | 35a9997d | repository.py |
| 2 | list_accruals service + GET /accruals endpoint | 72470b40 | service.py, router.py |
| 3 | PAY-05 integration tests | 8ceeee15 | test_payroll_list.py, conftest.py |

## Implementation Details

### Repository (Task 1)
- `list_accruals_for_trainer(session, trainer_id, *, page, page_size)`: paginated ORM SELECT with `ORDER BY accrued_at DESC`, `LIMIT page_size OFFSET (page-1)*page_size`. Hits `ix_trainer_payroll_accruals_trainer_accrued` composite index. No clawback_of_accrual_id filter — all rows included.
- `count_accruals(session, trainer_id)`: `SELECT COUNT(*)` for unpaginated total. Pure reads; no commit.
- Added `func` to sqlalchemy imports.

### Service (Task 2)
- `list_accruals(session, trainer_id, *, page, page_size) -> tuple[list[TrainerPayrollAccrual], int]`: calls the two repository readers, returns (rows, total). Pure read — zero writes, zero audit.emit().

### Router (Task 2)
- `GET /accruals`: `trainerId` (required UUID query param), `PageQuery` dependency (page/pageSize with le=100 bound). Permission guard: `require_permission(Action.LIST, Resource.PAYROLL)`. Response: `ResponseEnvelope[PaginatedData[PayrollAccrualResponse]]`. No status/period filters (deferred per D-58-14).

### Tests (Task 3, TDD)
8 integration tests covering:
- `accrued_at DESC` ordering with explicit staggered timestamps (deterministic)
- Envelope keys: items, total, page, pageSize
- Pagination math: pageSize=2 over 5 rows → page 1 has 2 items, page 3 has 1
- Clawback row (negative accrual_kopecks) appears in list
- Paid and pending rows both surface with correct status + paidAt
- Reception → 403 (T-58-31)
- trainer_id scoping (cross-trainer isolation, T-58-33)
- Empty list for trainer with no accruals (boundary case)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical test infrastructure] Added accrued_at param to make_accrual fixture**
- **Found during:** Task 3 — ordering test would be non-deterministic if rows inserted in same DB clock tick get same `now()` default
- **Fix:** Added optional `accrued_at: datetime | None = None` param to `make_accrual` in conftest.py; when set, overrides the ORM column before INSERT
- **Files modified:** tests/integration/payroll/conftest.py
- **Commit:** 8ceeee15

**2. [Rule 1 - Bug] Fixed clawback test: source_refund_payment_id FK requires real payment row**
- **Found during:** Task 3 — FK constraint `fk_trainer_payroll_accruals_source_refund_payment_id` rejected uuid4() fake ID
- **Fix:** Seed a real `Payment(subject_kind='refund', amount_kopecks=-100000)` row before inserting the clawback accrual; use the real payment ID for `source_refund_payment_id`
- **Files modified:** tests/integration/payroll/test_payroll_list.py
- **Commit:** 8ceeee15

## Threat Model Coverage

| Threat | Mitigation | Status |
|--------|-----------|--------|
| T-58-31 Elevation of Privilege | require_permission(LIST, PAYROLL); reception 403 test | Mitigated |
| T-58-32 Unbounded page size | PageQuery Field(le=100) | Mitigated |
| T-58-33 Cross-trainer leakage | trainer_id bound WHERE param; scoping test | Mitigated |

## Known Stubs

None — all data is read from real DB rows; no hardcoded/placeholder values in response paths.

## Self-Check: PASSED

- FOUND: apps/backend/app/modules/payroll/repository.py
- FOUND: apps/backend/app/modules/payroll/service.py
- FOUND: apps/backend/app/modules/payroll/router.py
- FOUND: apps/backend/tests/integration/payroll/test_payroll_list.py
- FOUND: .planning/phases/58-payroll-foundations-ledger/58-08-SUMMARY.md
- FOUND commits: 35a9997d, 72470b40, 8ceeee15
