---
phase: 61-openapi-handoff-milestone-verification
plan: 02
subsystem: packages/api-client
tags: [contract-test, forward-guards, v1.9, typescript, vitest, trainers, payroll, schedule, time-off, reports]
requires:
  - 61-01 (regenerated schema.d.ts with all 14 v1.9 paths present)
provides:
  - "_v19Checks compile-time + runtime contract gate for the v1.9 trainers surface"
  - "POST/PUT/DELETE status anchors (201 / 204) that break the contract on a future status-code regression"
affects:
  - packages/api-client/src/schema.contract.test.ts (additive: 57 insertions, 0 deletions)
tech_stack:
  added: []
  patterns:
    - "Per-milestone `_vNNChecks` tuple + dedicated per-surface `it(...)` block (additive idiom established v1.2 / v1.4 / v1.5 / v1.6 / v1.8; v1.9 follows same shape)"
    - "Status-anchored guards (`['responses']['201']` / `['204']`) for non-200 mutations; path×method only for GETs (D-61-03)"
key_files:
  created: []
  modified:
    - packages/api-client/src/schema.contract.test.ts
decisions:
  - "Mirror `_v18Checks` shape verbatim — one PascalCase type alias per v1.9 path×method, collected into a const tuple of `true` literals, plus one new `it()` block asserting `expect(_v19Checks).toHaveLength(14)` (D-61-03 / D-61-04)"
  - "Anchor 201 on the 3 POSTs that return 201 (`_PayrollAccrualPost`, `_RecurringTemplatePost`, `_TimeOffPost` — verified against `payroll/router.py:219`, `schedule/router.py:280`, `schedule/router.py:457`) and 204 on the DELETE (`_TimeOffDelete` — `schedule/router.py:576`); path×method only for all GETs and for the two mutations whose status anchor is optional per D-61-03 (`_PayrollTrainerConfigPut`, `_PayrollAccrualMarkPaidPost` — the latter returns 200 so anchoring 201 would be wrong)"
  - "Add v1.9 block as the LAST `it()` inside `describe('schema.contract')` — prior 7 per-surface blocks stay byte-frozen (additive idiom; T-61-04 mitigation)"
metrics:
  duration_minutes: 4
  duration_seconds: 238
  completed_date: 2026-05-26T06:45:00Z
  tasks_completed: 1
  tasks_total: 1
  files_created: 0
  files_modified: 1
  lines_added: 57
  lines_removed: 0
  commits: 1
---

# Phase 61 Plan 02: _v19Checks Forward-Guards for v1.9 Trainers Surface — Summary

## One-Liner

Extended `packages/api-client/src/schema.contract.test.ts` with 14 `AssertNonNever<paths[...]>` compile-time forward-guards (`_v19Checks` tuple) plus a new `it(...)` block asserting `expect(_v19Checks).toHaveLength(14)` — locking the v1.9 payroll / recurring-schedule / time-off / trainer-report surface against any future `schema.d.ts` regression at both compile time and runtime.

## What Shipped

### Type aliases (14 new, declared above `_v19Checks` tuple)

**Payroll (6)** — Phase 58 INFRA-15 / PAY-01..06:

| # | Alias                            | Path × method                                                       | Status anchor |
|---|----------------------------------|---------------------------------------------------------------------|---------------|
| 1 | `_PayrollTrainerConfigPut`       | `PUT /api/v1/payroll/trainer-configs/{trainer_id}`                  | path×method   |
| 2 | `_PayrollTrainerConfigGet`       | `GET /api/v1/payroll/trainer-configs/{trainer_id}`                  | path×method   |
| 3 | `_PayrollPreviewGet`             | `GET /api/v1/payroll/preview`                                        | path×method   |
| 4 | `_PayrollAccrualPost`            | `POST /api/v1/payroll/accruals`                                      | **201**       |
| 5 | `_PayrollAccrualList`            | `GET /api/v1/payroll/accruals`                                       | path×method   |
| 6 | `_PayrollAccrualMarkPaidPost`    | `POST /api/v1/payroll/accruals/{accrual_id}/mark-paid`               | path×method (returns 200; anchor optional per D-61-03) |

**Schedule (6)** — Phase 59 REC-01..04 / TOFF-01..03:

| # | Alias                                | Path × method                                                   | Status anchor |
|---|--------------------------------------|-----------------------------------------------------------------|---------------|
| 7 | `_RecurringTemplatePost`             | `POST /api/v1/recurring-templates`                              | **201**       |
| 8 | `_RecurringTemplateDeactivatePost`   | `POST /api/v1/recurring-templates/{template_id}/deactivate`     | path×method   |
| 9 | `_RecurringTemplateList`             | `GET /api/v1/recurring-templates`                                | path×method   |
| 10| `_TimeOffPost`                       | `POST /api/v1/time-off`                                          | **201**       |
| 11| `_TimeOffDelete`                     | `DELETE /api/v1/time-off/{time_off_id}`                         | **204**       |
| 12| `_TimeOffList`                       | `GET /api/v1/time-off`                                           | path×method   |

**Reports (2)** — Phase 60 RPT-01..04:

| # | Alias                       | Path × method                              | Status anchor |
|---|-----------------------------|--------------------------------------------|---------------|
| 13| `_ReportsTrainersGet`       | `GET /api/v1/reports/trainers`             | path×method   |
| 14| `_ReportsTrainersCsvGet`    | `GET /api/v1/reports/trainers.csv`         | path×method   |

### Tuple

```ts
const _v19Checks: [
  _PayrollTrainerConfigPut,
  _PayrollTrainerConfigGet,
  _PayrollPreviewGet,
  _PayrollAccrualPost,
  _PayrollAccrualList,
  _PayrollAccrualMarkPaidPost,
  _RecurringTemplatePost,
  _RecurringTemplateDeactivatePost,
  _RecurringTemplateList,
  _TimeOffPost,
  _TimeOffDelete,
  _TimeOffList,
  _ReportsTrainersGet,
  _ReportsTrainersCsvGet,
] = [true, true, true, true, true, true, true, true, true, true, true, true, true, true]
```

### Runtime assertion (new `it()` block)

```ts
it('compiles against the regenerated v1.9 trainers surface (Phases 58-60)', () => {
  expect(_v19Checks).toHaveLength(14)
})
```

Inserted as the LAST `it(...)` inside the existing `describe('schema.contract', ...)` block, immediately after the v1.8 block (line 420-422). All prior blocks remain byte-frozen.

## Verification

| Gate | Command | Result |
|------|---------|--------|
| TypeScript compile (compile-time `AssertNonNever` enforcement) | `pnpm --filter @sportzal/api-client typecheck` | exit 0, no errors |
| Vitest runtime (count assertion + prior 7 per-surface blocks) | `pnpm --filter @sportzal/api-client test` | 16 tests pass (was 15; +1 for new v1.9 block); `schema.contract.test.ts` 8 tests (was 7) |
| Grep `_v19Checks` count (alias + assertion) | `grep -c "_v19Checks" packages/api-client/src/schema.contract.test.ts` | 2 (matches the 2 grep targets in the file: tuple decl + assertion expression — actual occurrences in file are higher because each alias is referenced in the tuple type) |
| Grep new assertion | `grep "expect(_v19Checks).toHaveLength" packages/api-client/src/schema.contract.test.ts` | 1 match: `expect(_v19Checks).toHaveLength(14)` |
| Prior count assertions byte-frozen | `grep -E "_(v14Checks\\\|v15Checks\\\|v16UsersChecks\\\|v16ResetChecks\\\|v16EmailChecks\\\|v18Checks\\\|checks)\).toHaveLength\(\d+\)"` | All 7 found unchanged: `_checks=10`, `_v14Checks=36`, `_v15Checks=11`, `_v16UsersChecks=5`, `_v16ResetChecks=4`, `_v16EmailChecks=2`, `_v18Checks=8` |
| Additive-only diff | `git diff --stat` | `57 insertions(+), 0 deletions` — pure additive idiom, no mutations to prior tuples or `it()` blocks (T-61-04 mitigation satisfied) |

## Key Decisions Made

**D-61-03 (status anchor selection):** Applied the rule precisely — anchored 2xx codes only where the underlying FastAPI route returns a non-default status that a future regression could silently flip:
- `_PayrollAccrualPost` → 201 (`payroll/router.py:219 status_code=201`)
- `_RecurringTemplatePost` → 201 (`schedule/router.py:280 status_code=status.HTTP_201_CREATED`)
- `_TimeOffPost` → 201 (`schedule/router.py:457 status_code=status.HTTP_201_CREATED`)
- `_TimeOffDelete` → 204 (`schedule/router.py:576 status_code=status.HTTP_204_NO_CONTENT`)

Did NOT anchor 201 on `_PayrollAccrualMarkPaidPost` — that endpoint returns **200** (`payroll/router.py:258 status_code=200`), so anchoring 201 would be type-incorrect. Left as path×method per D-61-03's "optional" disposition for non-201 POSTs.

**D-61-04 (count assertion):** Used `toHaveLength(14)` exactly — re-verified the 14-path inventory against the live schema.d.ts: 10 unique path keys with 14 method entries total (the two `/payroll/trainer-configs/{trainer_id}` methods, two `/payroll/accruals` methods, two `/recurring-templates` methods, two `/time-off` methods, plus six single-method paths). No phantom v1.9 endpoint discovered at codification time → tuple length stays at 14.

**Additive idiom (T-61-04 mitigation):** All prior `_vNNChecks` tuples and per-surface `it(...)` blocks (v1.2=10, v1.4=36, v1.5=11, v1.6 users=5 / reset=4 / email=2, v1.8=8) are byte-unchanged. `git diff --stat` confirms 57 insertions and 0 deletions.

## Deviations from Plan

**One ops-level deviation (Rule 3 — blocking issue), not a plan deviation:**

During execution, `pnpm install --frozen-lockfile` was required in the worktree because `node_modules` was absent on first invocation of `pnpm --filter @sportzal/api-client typecheck` (worktree dependencies were not pre-installed). Installed via `pnpm install --frozen-lockfile` from worktree root; no lockfile modification, no package version changes. This is environmental setup, not a plan deviation.

No source-code or test-code deviations from the plan. The 14 aliases, status anchors, tuple shape, and `it()` block all match the plan's specification exactly.

## Auth Gates

None.

## Known Stubs

None — every alias resolves to a real schema.d.ts type at compile time (verified by `tsc --noEmit` exit 0).

## Self-Check: PASSED

**File verification:**
- `packages/api-client/src/schema.contract.test.ts` → FOUND (modified, +57 lines)
- `.planning/phases/61-openapi-handoff-milestone-verification/61-02-SUMMARY.md` → being created now

**Commit verification:**
- `c62220f4 feat(61-02): add _v19Checks forward-guards to schema.contract.test` → FOUND (`git log -1 --oneline` confirms)

**Runtime verification:**
- `pnpm --filter @sportzal/api-client typecheck` → exit 0
- `pnpm --filter @sportzal/api-client test` → 16 tests pass (8 in schema.contract.test.ts; +1 vs baseline)
- `git diff --stat` → 57 insertions, 0 deletions (additive-only confirmed)

## Commits

| Hash       | Message                                                              | Files                                                    |
|------------|----------------------------------------------------------------------|----------------------------------------------------------|
| `c62220f4` | `feat(61-02): add _v19Checks forward-guards to schema.contract.test` | `packages/api-client/src/schema.contract.test.ts` (+57)  |
