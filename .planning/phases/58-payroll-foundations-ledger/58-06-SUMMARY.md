---
phase: 58-payroll-foundations-ledger
plan: "06"
subsystem: payroll
tags: [payroll, preview, raw-sql, tdd, integer-math]
dependency_graph:
  requires: [58-04, 58-05]
  provides: [PAY-02]
  affects: [payroll-module, pt_sessions-cross-read, pt_packages-cross-read, payments-cross-read]
tech_stack:
  added: []
  patterns:
    - raw-SQL cross-module reader in payroll/repository.py (mirrors reports/repository.py pattern)
    - compute_accrual_components shared helper (single source of truth for PAY-02 and PAY-03)
    - router-layer 422 remap for CompConfigMissingError (one error class, two HTTP status codes)
    - TDD RED/GREEN for GET /preview endpoint
key_files:
  created:
    - apps/backend/tests/integration/payroll/test_payroll_preview.py
  modified:
    - apps/backend/app/modules/payroll/repository.py
    - apps/backend/app/modules/payroll/service.py
    - apps/backend/app/modules/payroll/router.py
decisions:
  - "Router-layer remap: CompConfigMissingError (404) → _CompConfigMissing422Error (422) in preview endpoint; GET trainer-configs keeps 404"
  - "compute_accrual_components is the single source of truth; PAY-03 will reuse it verbatim to prevent recompute drift (PITFALL 1)"
  - "Integer-only math.ceil for commission; no float() in computation path (D-58-04 / T-58-25)"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-25T12:25:00Z"
  tasks_completed: 3
  files_modified: 4
---

# Phase 58 Plan 06: PAY-02 Payroll Preview Summary

PAY-02 delivered: GET /api/v1/payroll/preview returns {session_count, fixed_kopecks, commission_kopecks, total_kopecks} for an owner-specified trainer + inclusive MSK period with zero rows persisted.

## What Was Built

### Task 1: fetch_trainer_session_revenue cross-module reader (repository.py)

Added `fetch_trainer_session_revenue(session, trainer_id, period_start, period_end) -> tuple[int, int]` to `payroll/repository.py`. Uses `from sqlalchemy import text` only — zero ORM imports from `pt_sessions`, `pt_packages`, or `payments` (D-58-19 cross-module discipline).

Returns `(commission_revenue_kopecks, conducting_session_count)`:
- Commission revenue: SUM of net payments (sale + refund via `refund_of`) for packages where `pt_packages.trainer_id = :trainer_id` AND the package has >= 1 non-cancelled session in the MSK-inclusive period. SQL carries `-- attribution: assigned-at-sale` comment (D-58-21).
- Session count: COUNT of non-cancelled `pt_sessions` where `pt_sessions.trainer_id = :trainer_id` in the period. SQL carries `-- attribution: conducting` comment (D-58-21).
- Period bounds: `(performed_at AT TIME ZONE 'Europe/Moscow')::date BETWEEN :period_start AND :period_end` (D-58-05).
- import-linter: 3 contracts KEPT (zero new ignore_imports edges). mypy: clean.

### Task 2: compute_accrual_components + preview_accrual (service.py)

Added two functions to `payroll/service.py`:

**`compute_accrual_components(session, trainer_id, period_start, period_end) -> tuple[int, int, int, int, TrainerCompConfig]`**

The SINGLE source of truth for payroll computation reused by PAY-03 (PITFALL 1 recompute-drift mitigation). Algorithm:
1. Resolve config via `repository.resolve_active_comp_config(..., as_of_date=period_end)`. Both-NULL → raise `CompConfigMissingError`.
2. Fetch `(revenue_kopecks, session_count)` from `repository.fetch_trainer_session_revenue`.
3. `commission_kopecks = math.ceil(revenue_kopecks * bps / 10000)` if bps is non-NULL else 0. Integer-only arithmetic via Python's arbitrary-precision integers; no `float()` (D-58-04 / T-58-25).
4. `fixed_kopecks = (session_fee_kopecks or 0) * session_count`.
5. `total_kopecks = commission_kopecks + fixed_kopecks`.
Returns `(session_count, fixed_kopecks, commission_kopecks, total_kopecks, config)`.

**`preview_accrual(...) -> PayrollPreviewResponse`**

Maps first four ints to `PayrollPreviewResponse`. ZERO writes: no `session.commit()`, no `audit.emit()`, no `session.add()` (D-58-12).

### Task 3: GET /preview endpoint + PAY-02 integration tests (TDD)

Added `GET /preview` to `payroll/router.py`:
- Query params: `trainerId: UUID`, `periodStart: date`, `periodEnd: date` (camelCase aliases via `Query(alias=...)`)
- Permission: `require_permission(Action.LIST, Resource.PAYROLL)` — `(LIST, PAYROLL) ∈ OWNER_ONLY` (pre-registered Plan 58-01)
- Router-layer 422 remap: `CompConfigMissingError` (404) → `_CompConfigMissing422Error(ValidationAppError)` with same `comp_config_missing` code at HTTP 422 (D-58-07 / D-58-09). GET trainer-configs path keeps its 404.
- Returns `ResponseEnvelope[PayrollPreviewResponse]` via `envelope()`.

**Integration tests** (`test_payroll_preview.py`): 8 tests, all pass.
- `test_preview_pure_pct_golden` — revenue 100000, bps 1500 → commission 15000
- `test_preview_ceil_in_favor_golden` — revenue 10001, bps 1500 → 1500.15 → ceil 1501 (proves no float truncation)
- `test_preview_pure_fixed_golden` — session_fee 50000, 3 sessions → fixed 150000
- `test_preview_hybrid_golden` — pct 1000 bps + fixed 30000/session, 2 sessions, revenue 200000 → commission 20000 + fixed 60000 = total 80000
- `test_preview_no_config_returns_422` — 422 comp_config_missing
- `test_preview_both_null_config_returns_422` — both-NULL config → 422 comp_config_missing
- `test_preview_reception_forbidden` — 403 forbidden (T-58-22)
- `test_preview_zero_persistence` — accrual row count unchanged before/after preview

## TDD Gate Compliance

| Gate | Status |
|------|--------|
| RED commit (`test(58-06)`) | `18849056` — tests failing with 404 (endpoint absent) |
| GREEN commit (`feat(58-06)`) | `7db1d2fd` — all 8 tests pass |
| REFACTOR | Not needed — code is clean |

## Deviations from Plan

None - plan executed exactly as written. The router-remap approach for 422 was the selected strategy as specified in Task 2/3 guidance.

## Commits

| Task | Hash | Message |
|------|------|---------|
| Task 1: repository reader | `1af7cff` | feat(58-06): add fetch_trainer_session_revenue raw-SQL cross-module reader |
| Task 2: service helper | `b5884df` | feat(58-06): add compute_accrual_components + preview_accrual to service.py |
| Task 3 RED: failing tests | `18849056` | test(58-06): add failing PAY-02 integration tests (RED phase) |
| Task 3 GREEN: endpoint | `7db1d2fd` | feat(58-06): add GET /preview endpoint to payroll router (GREEN phase) |

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes outside the plan's threat model. The `GET /preview` endpoint is within the planned threat surface (T-58-22 through T-58-25 all mitigated as planned).

## Known Stubs

None — all four response fields (session_count, fixed_kopecks, commission_kopecks, total_kopecks) are computed from real DB data.

## Self-Check: PASSED

Files exist:
- `apps/backend/app/modules/payroll/repository.py` — contains `fetch_trainer_session_revenue` ✓
- `apps/backend/app/modules/payroll/service.py` — contains `compute_accrual_components` and `preview_accrual` ✓
- `apps/backend/app/modules/payroll/router.py` — contains `/preview` endpoint ✓
- `apps/backend/tests/integration/payroll/test_payroll_preview.py` — 8 tests, all pass ✓

Commits verified: 1af7cff, b5884df, 18849056, 7db1d2fd — all present in git log.
