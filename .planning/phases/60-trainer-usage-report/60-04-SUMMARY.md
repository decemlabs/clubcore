---
phase: 60-trainer-usage-report
plan: "04"
subsystem: reports
tags: [backend, reports, trainer-usage, integration-tests, pitfall-goldens, rbac]
dependency_graph:
  requires: [60-01, 60-02, 60-03]
  provides: [20 integration test goldens for RPT-01..04 + PITFALL 6/10/11/12]
  affects:
    - apps/backend/tests/integration/reports/test_reports_trainers.py
    - apps/backend/ruff.toml
tech_stack:
  added: []
  patterns:
    - "SAVEPOINT-isolated async fixtures (pytest-asyncio + db_session)"
    - "local factory fixtures pattern (D-60-13: no new conftest — keep in test file)"
    - "module-level pathlib REPORTS_DIR with is_dir() import-time assertion (PITFALL 10 vacuous-pass guard)"
    - "subprocess.run uv run lint-imports as in-test ship gate (mirrors test_importlinter_negative_fixture.py)"
key_files:
  created:
    - apps/backend/tests/integration/reports/test_reports_trainers.py
  modified:
    - apps/backend/ruff.toml
decisions:
  - "Local factory fixtures (make_trainer, make_pt_package_plan, make_pt_package_with_trainer, make_pt_session, make_slot, make_accrual_row) kept in test file per D-60-13 — not added to conftest"
  - "source_refund_payment_id is FK to payments.id (NOT a free UUID) — clawback test requires make_payment_ledger to create a real refund payment row with subject_kind='refund'"
  - "lint-imports subprocess uses ['uv', 'run', 'lint-imports'] (not bare 'lint-imports') to find venv binary — mirrors test_importlinter_negative_fixture.py pattern"
  - "REPORTS_DIR.parents[2] = apps/backend/ (REPORTS_DIR = .../app/modules/reports; parents[0]=modules, parents[1]=app, parents[2]=backend)"
  - "PITFALL 10 test is sync def (not async) to avoid ASYNC221 (blocking subprocess.run in async context)"
  - "ruff.toml per-file-ignores: RUF001/RUF002/RUF003 for Cyrillic trainer names + ASYNC221/S603/S607 for subprocess ship gate"
metrics:
  duration: "resumed from previous agent context (2026-05-25)"
  completed: "2026-05-25"
  tasks_completed: 3
  files_created: 1
  files_modified: 1
requirements: [RPT-01, RPT-02, RPT-03, RPT-04]
---

# Phase 60 Plan 04: Trainer-Usage Integration Test Suite Summary

**One-liner:** 20 pytest-asyncio integration goldens covering RPT-01..04 + PITFALL 6/10/11/12 + CSV assertions + ordering tie-break + in-test `uv run lint-imports` ship gate — all 88 reports tests pass, all CI gates green.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1+2 | Create test file + populate all 20 test bodies | 1412eb5f | apps/backend/tests/integration/reports/test_reports_trainers.py, apps/backend/ruff.toml |
| 3 | Phase-level CI verification (all gates green) | — (verification only, no new files) | — |

## What Was Built

### test_reports_trainers.py — 20 test functions

| Test | Coverage |
|------|----------|
| `test_owner_gets_trainer_usage_report` | RPT-01..04 happy path — 200 + envelope shape + revenueAttributionNote |
| `test_reception_forbidden_on_trainers_json` | RPT-01 reception 403 + code: "forbidden" |
| `test_reception_forbidden_on_trainers_csv` | RPT-03 reception 403 + code: "forbidden" |
| `test_to_date_before_from_date_returns_422` | RPT-01 validation (to < from) |
| `test_range_over_366_days_returns_report_range_too_large` | D-06 range cap 422 + code: "report_range_too_large" |
| `test_pitfall_11_deactivated_trainer_appears_in_report` | PITFALL 11 / D-60-03: is_active=False trainer with sessions included |
| `test_pitfall_12_session_on_to_date_included_session_after_excluded` | PITFALL 12 / VER-02: AT TIME ZONE boundary inclusivity |
| `test_pitfall_6_revenue_attributed_to_assigned_trainer_not_conducting` | PITFALL 6 / D-58-21: revenue follows pt_packages.trainer_id |
| `test_trainers_ordered_by_session_count_desc_then_name` | RPT-01 / D-60-03: deliberate tie (5,5,3,0) asserts exact order |
| `test_utilization_pct_null_when_zero_active_slots` | D-60-06 null sentinel (0 slots → JSON null) |
| `test_utilization_pct_zero_when_slots_but_no_bookings` | D-60-06 zero sentinel (active slots, 0 bookings → 0.0) |
| `test_walkin_session_contributes_zero_hours` | D-60-04: booking_id=NULL → sessionCount=1, totalHours=0.0 |
| `test_rpt04_clawback_nets_in_total_accrued` | RPT-04 / D-58-03: +50000 + (-30000) → totalAccruedKopecks=20000 |
| `test_rpt04_payroll_overlap_includes_straddling_periods` | D-60-05: period straddles window → full 75000 kopecks (non-prorated) |
| `test_trainers_csv_bom_and_content_type` | RPT-03 / EXP-04: U+FEFF BOM first char, text/csv content-type |
| `test_trainers_csv_header_row_matches_constant` | RPT-03: first row == list(CSV_TRAINER_USAGE_HEADERS) |
| `test_trainers_csv_cyrillic_trainer_name_round_trip` | RPT-03 / EXP-04: "Иван Петров" verbatim in decoded body |
| `test_trainers_csv_formula_injection_sanitized` | T-56-07 / CR-01: "=cmd..." → "\'=cmd..." (apostrophe prefix) |
| `test_trainers_csv_utilization_null_renders_empty_cell` | D-60-11: utilizationPct=NULL → "" not "None"/"NULL" |
| `test_pitfall_10_no_orm_imports_in_reports_module` | PITFALL 10 / D-60-01 / RPT-04 ship gate: grep + uv run lint-imports |

### Local factory fixtures (D-60-13: not in conftest)

- `make_trainer(db_session)` → inserts `Trainer`, supports `is_active=False`
- `make_pt_package_plan(db_session)` → inserts `PtPackagePlan`
- `make_pt_package_with_trainer(db_session)` → inserts `PtPackage` with `trainer_id` (assigned-at-sale — D-58-21)
- `make_pt_session(db_session, seeded_owner)` → inserts `PtSession`; `booking_id=None` for walk-ins (D-60-04)
- `make_slot(db_session)` → inserts `TrainerAvailabilitySlot` for utilization tests
- `make_accrual_row(db_session)` → inserts `TrainerCompConfig` + `TrainerPayrollAccrual` pair

### ruff.toml additions

Per-file-ignores for `tests/integration/reports/test_reports_trainers.py`:
- `RUF001/RUF002/RUF003`: Cyrillic trainer names in test seed data (А Алексеев, Б Борисов, etc.)
- `ASYNC221`: blocking `subprocess.run` in pitfall_10 (sync def, not async)
- `S603/S607`: subprocess with list argv from trusted test constants

## CI Gate Results (Task 3)

| Gate | Command | Result |
|------|---------|--------|
| 1. ruff reports/ | `ruff check app/modules/reports/` | exit 0 |
| 2. mypy strict reports/ | `mypy --strict app/modules/reports/` | exit 0 (8 files) |
| 3. lint-imports | `uv run lint-imports` | exit 0 (3 kept, 0 broken) |
| 4. .importlinter diff | `git diff --exit-code .importlinter` | exit 0 (unchanged) |
| 5. permissions.py diff | `git diff --exit-code apps/backend/app/core/permissions.py` | exit 0 (unchanged) |
| 6. admin-web frozen | `git diff --exit-code apps/admin-web/src/shared/session/{can,registry}.ts` | exit 0 (unchanged) |
| 7. PITFALL 10 grep | `! grep -rE "from app.modules.*.models" apps/backend/app/modules/reports/` | no matches (PASS) |
| 8. 20 new tests | `pytest tests/integration/reports/test_reports_trainers.py -x` | 20 passed |
| 9. route introspection | `pytest tests/integration/test_route_introspection.py::test_every_protected_route_declares_a_gate` | 1 passed |
| 10. all reports tests | `pytest tests/integration/reports/ -x` | 88 passed |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed `client.id` reference after UNIQUE constraint refactor in ordering test**
- **Found during:** Task 2 execution — `test_trainers_ordered_by_session_count_desc_then_name`
- **Issue:** Three PT packages created for same client violated `uq_pt_packages_active_per_client` UNIQUE constraint. Previous agent partially refactored to use `client_a/client_b/client_v` but the `make_pt_session` calls still referenced undefined `client.id`
- **Fix:** Updated all three session-creation loops to use `client_a.id`, `client_b.id`, `client_v.id` respectively
- **Files modified:** `apps/backend/tests/integration/reports/test_reports_trainers.py`
- **Commit:** 1412eb5f

**2. [Rule 1 - Bug] Fixed `source_refund_payment_id` FK violation in clawback test**
- **Found during:** Task 2 test run — `test_rpt04_clawback_nets_in_total_accrued` ForeignKeyViolationError
- **Issue:** Code passed `accrual.id` as `source_refund_payment_id`, but this field is FK to `payments.id` (not a free UUID). CheckConstraint `clawback_fks_paired` requires both `clawback_of_accrual_id` and `source_refund_payment_id` to be non-NULL together.
- **Fix:** Added `make_payment_ledger` fixture call to create a real refund payment row (`subject_kind="refund"`, `amount_kopecks=-30000`) and used its `.id` as `source_refund_payment_id`
- **Files modified:** `apps/backend/tests/integration/reports/test_reports_trainers.py`
- **Commit:** 1412eb5f

**3. [Rule 1 - Bug] Fixed lint-imports subprocess cwd — `REPORTS_DIR.parents[2]` not `parents[3]`**
- **Found during:** Task 2 test run — `test_pitfall_10_no_orm_imports_in_reports_module`
- **Issue:** Code used `REPORTS_DIR.parents[3]` as cwd for `lint-imports` subprocess, but `REPORTS_DIR.parents[3]` is `apps/` not `apps/backend/`. Parent depth: REPORTS_DIR=`.../app/modules/reports`; `parents[0]=modules`, `parents[1]=app`, `parents[2]=apps/backend`, `parents[3]=apps/`.
- **Fix:** Changed to `REPORTS_DIR.parents[2]` with corrected comment
- **Files modified:** `apps/backend/tests/integration/reports/test_reports_trainers.py`
- **Commit:** 1412eb5f

**4. [Rule 1 - Bug] Fixed lint-imports subprocess command — `["uv", "run", "lint-imports"]`**
- **Found during:** Task 2 test run — `test_pitfall_10_no_orm_imports_in_reports_module`
- **Issue:** Bare `["lint-imports"]` command couldn't find the binary since the subprocess doesn't inherit the venv activation. The existing `test_importlinter_negative_fixture.py` uses `["uv", "run", "lint-imports"]` for this reason.
- **Fix:** Changed to `["uv", "run", "lint-imports"]` — mirrors established project pattern
- **Files modified:** `apps/backend/tests/integration/reports/test_reports_trainers.py`
- **Commit:** 1412eb5f

## Protected Files Verification

| File | Status |
|------|--------|
| `apps/backend/.importlinter` | UNCHANGED (git diff exit 0) |
| `apps/backend/app/core/permissions.py` | UNCHANGED (git diff exit 0) |
| `apps/admin-web/src/shared/session/can.ts` | UNCHANGED (git diff exit 0) |
| `apps/admin-web/src/shared/session/registry.ts` | UNCHANGED (git diff exit 0) |

## Phase 60 Closure Note

Plans 01-04 complete. RPT-01..04 are fully proven:
- RPT-01: GET /trainers JSON (200 + envelope) — tested
- RPT-02: Reception 403 on JSON — tested
- RPT-03: GET /trainers.csv (BOM, headers, Cyrillic, formula-injection, NULL→empty) — tested
- RPT-04: Clawback netting, payroll overlap, PITFALL 10 ship gate — tested

## Known Stubs

None — all 20 tests pass against real DB data via SAVEPOINT isolation.

## Threat Flags

None — test file only creates synthetic seed data (factory-generated UUIDs, kopeck integers, made-up Russian names). No new network surface. The `subprocess.run` calls invoke trusted binaries (`grep`, `uv`) with absolute path arguments.

## Self-Check: PASSED

- `apps/backend/tests/integration/reports/test_reports_trainers.py` — created (1123 insertions)
- `apps/backend/ruff.toml` — modified (per-file-ignores entry added)
- Commit verified: `git log --oneline | grep 1412eb5f` — present
- 20 tests pass: `pytest tests/integration/reports/test_reports_trainers.py` — 20 passed
- 88 reports tests pass (no regression): `pytest tests/integration/reports/` — 88 passed
- All CI gates: ruff, mypy, lint-imports, git diff guards, grep guard — all exit 0
