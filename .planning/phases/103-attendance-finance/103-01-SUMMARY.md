---
phase: 103-attendance-finance
plan: "01"
subsystem: admin-app/features
tags: [visits, payments, reports, tdd, zod, tanstack-query, optimistic-ui]
dependency_graph:
  requires: [101-04]
  provides: [useVisitsList, useGymMeta, useCheckIn, usePaymentsLedger, useVisitsReport, useRevenueReport, fillHourlyBuckets, fillDailyBuckets, fillRevenueBuckets]
  affects: [103-02, 103-03, 103-04]
tech_stack:
  added: []
  patterns: [optimistic-prepend-rollback, owner-gated-enabled, sparse-bucket-zero-fill, tdd-red-green]
key_files:
  created:
    - apps/admin-app/src/features/reports/schemas.ts
    - apps/admin-app/src/features/reports/keys.ts
    - apps/admin-app/src/features/reports/utils.ts
    - apps/admin-app/src/features/reports/utils.test.ts
  modified:
    - apps/admin-app/src/features/visits/schemas.ts
    - apps/admin-app/src/features/visits/schemas.test.ts
    - apps/admin-app/src/features/visits/api.ts
    - apps/admin-app/src/features/payments/schemas.ts
    - apps/admin-app/src/features/payments/api.ts
    - apps/admin-app/src/features/reports/api.ts
decisions:
  - "D-103-01-SESSION-FROM-CALLER: useCheckIn receives currentUserId as a mutation var (from caller) rather than calling useSession() internally — avoids Rules of Hooks violation in mutationFn and keeps the hook context-free"
  - "D-103-01-LEGACY-USERECPORTS: useReports() + reportsKeys preserved in reports/api.ts so ReportsPage (Phase 104 scope) builds without modification; reportsQueryKeys uses ['reports-data'] root to avoid collision"
  - "D-103-01-NOSESSION-VISITS: visits/api.ts does NOT import useSession — currentUserId passed by caller via CheckInVars; payments/api.ts accepts role as explicit parameter from caller"
metrics:
  duration: "5m"
  completed: "2026-06-13"
  tasks_completed: 3
  tasks_total: 3
  files_created: 4
  files_modified: 6
---

# Phase 103 Plan 01: Shared Contract + Data Layer Summary

**One-liner:** Zod-validated, owner-gated data layer for visits (list/check-in/meta), payments (global ledger), and reports (visits+revenue) with TDD-tested sparse-bucket zero-fill utilities.

## What Was Built

### Task 1: Schema contract extensions

Extended `features/visits/schemas.ts` with:
- `VisitsListQuerySchema` — optional from/to/clientId/page/pageSize params
- `GymMetaSchema` — data-wrapped gym hours shape
- `CheckInInputSchema` — clientId with Russian validation message «Клиент обязателен»

Extended `features/payments/schemas.ts` with:
- `PaymentsLedgerQuerySchema` — optional receivedFrom/receivedTo/method(cash|online)/page/pageSize
- `DailyTotal` type — {date,totalKopecks} for client-side cashbox aggregation

Extended `features/visits/schemas.test.ts` with 3 new describe blocks (12 new tests).

### Task 2: NEW reports domain

Created `features/reports/schemas.ts`:
- `VisitsReportDailyBucketSchema` / `VisitsReportHourlyBucketSchema` / `VisitsReportSchema`
- `RevenueBucketSchema` (period, signed netKopecks, byMethod, bySubjectKind)
- `RevenueReportSchema` with groupBy enum
- Plain TS query types `VisitsReportQuery` / `RevenueReportQuery`

Created `features/reports/keys.ts`:
- `reportsQueryKeys` rooted at `['reports-data']` (avoids collision with legacy `['reports']`)

Created `features/reports/utils.ts` (pure, zero React deps):
- `fillHourlyBuckets` — always 24 points (0–23), missing → count:0
- `fillDailyBuckets` — every calendar day in [fromDate,toDate], missing → count:0
- `fillRevenueBuckets` — day or month enumeration via `eachDayOfInterval`/`eachMonthOfInterval`; month branch FULLY implemented (not stubbed)

Created `features/reports/utils.test.ts` — 18 tests covering all cases including empty-array no-NaN and month branch.

### Task 3: Data hooks wired

Extended `features/visits/api.ts`:
- `visitsKeys.lists()` / `.list(filter)` / `.meta()` added to key factory
- `useVisitsList(filter)` — paginated GET /api/v1/visits with optional query params
- `useGymMeta()` — GET /api/v1/visits/_meta with 5-min staleTime
- `useCheckIn()` — POST /api/v1/visits with optimistic prepend + rollback; does NOT toast 409 codes (caller maps ApiError.code)

Extended `features/payments/api.ts`:
- `paymentsKeys.lists()` / `.list(filter)` added to key factory
- `usePaymentsLedger(filter, role)` — global GET /api/v1/payments, enabled only when `can(role,'view','payments')`

Replaced `features/reports/api.ts` (preserving legacy mock):
- `useVisitsReport(query)` — GET /api/v1/reports/visits, owner-gated
- `useRevenueReport(query)` — GET /api/v1/reports/revenue, owner-gated
- Legacy `useReports()` + `reportsKeys` preserved for Phase 104 ReportsPage build compatibility

## Commits

| Hash | Description |
|------|-------------|
| 64f92c38 | feat(103-01): extend visits + payments contract layers (schemas) |
| 28914efc | feat(103-01): NEW features/reports domain — schemas, keys, zero-fill utils (TDD) |
| b49bb5f4 | feat(103-01): wire data hooks — visits (list/meta/check-in), payments (ledger), reports (owner-gated) |

## Verification Results

- `pnpm -F @clubcore/admin-app typecheck` — exit 0
- `pnpm -F @clubcore/admin-app lint` — exit 0
- `pnpm -F @clubcore/admin-app test` — 303 tests across 22 files, all pass
- `pnpm -F @clubcore/admin-app build` — built in 3.21s, no errors
- No new packages added to admin-app/package.json

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused `session` import and variable from visits/api.ts**
- **Found during:** Task 3 — typecheck phase
- **Issue:** `useSession()` was imported and called in `useCheckIn()` but the session value was never used; `currentUserId` is passed as a mutation var by the caller
- **Fix:** Removed `useSession` import and `const session = useSession()` from `useCheckIn`; currentUserId remains a caller-provided `CheckInVars` field (cleaner hook design)
- **Files modified:** `features/visits/api.ts`
- **Commit:** b49bb5f4

**2. [Rule 1 - Bug] Removed unused `_data/_vars/_ctx` params from `onSuccess`**
- **Found during:** Task 3 — lint phase
- **Issue:** `onSuccess: (_data, _vars, _ctx)` prefixed-underscore params triggered `@typescript-eslint/no-unused-vars` lint errors
- **Fix:** Changed to `onSuccess: ()` with no params (body only uses `qc.invalidateQueries`)
- **Files modified:** `features/visits/api.ts`
- **Commit:** b49bb5f4

## Known Stubs

None. All hooks wire to real endpoints. `useReports()` is intentionally kept on mock — it is not a stub introduced by this plan; it is the Phase 104 scope target preserved for build compatibility (documented decision D-103-01-LEGACY-USERECPORTS).

## Threat Surface Scan

No new security surface beyond what is in the plan's threat_model. All three RBAC gates are implemented:
- `usePaymentsLedger`: `enabled: can(role,'view','payments')` — reception makes zero calls
- `useVisitsReport` / `useRevenueReport`: `enabled: can(role,'view','reports')` — reception makes zero calls
- `useCheckIn`: 409 codes re-thrown raw to caller (no bypass/swallow)

## Self-Check: PASSED

All key files exist on disk. All 3 task commits verified in git log.
