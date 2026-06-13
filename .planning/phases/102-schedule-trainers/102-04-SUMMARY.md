---
phase: 102-schedule-trainers
plan: "04"
subsystem: ui
tags: [react, tanstack-query, zod, payroll, owner-only, rbac, money]

# Dependency graph
requires:
  - phase: 102-schedule-trainers/02
    provides: useTrainer hook; TrainerData type; TrainerPage mounts PayoutsTab
provides:
  - Payroll HTTP layer: PayrollConfigSchema/Input, AccrualPreviewSchema, AccrualSchema, AccrualsListResponseSchema, RunAccrualSchema (Zod)
  - Query key factory (payrollKeys) for cache coordination
  - usePayrollConfig / useAccrualPreview / useAccruals TanStack Query hooks (owner-only, enabled-gated)
  - useSetPayrollConfig / useRunAccrual / useMarkAccrualPaid mutations with 409-aware error handling
  - Wired PayoutsTab: reception Lock gate + comp-config editor + preview→run + accruals list + mark-paid
  - TRN-02 requirement delivered
affects: [103, 104]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Payroll hooks enabled-gated via can(role,'view','payroll') — ZERO API calls for reception"
    - "Reception gate rendered BEFORE OwnerPayoutsTab sub-component mounts (hooks never instantiated)"
    - "useAccrualPreview: staleTime:0 + retry:false — 422 comp_config_missing surfaces immediately"
    - "useMarkAccrualPaid: 409 already_paid → toast + invalidateQueries accruals (refetch on error)"
    - "Comp-config editor: display=kopecks/100 / bps/100; send=Math.round(rubles*100) / Math.round(pct*100)"
    - "Period picker: type=month inputs; periodStart=YYYY-MM-01; periodEnd=last day of month"
    - "Preview state managed locally: previewEnabled flag + useAccrualPreview(enabled=previewEnabled)"
    - "PayoutsTab test mocks @/features/payroll/api (not @/api/client) — ESLint pages/ import-boundary"
    - "ApiError re-exported from features/payroll/api.ts for ESLint import-boundary compliance"

key-files:
  created:
    - apps/admin-app/src/features/payroll/schemas.ts
    - apps/admin-app/src/features/payroll/keys.ts
    - apps/admin-app/src/features/payroll/api.ts
    - apps/admin-app/src/features/payroll/api.test.tsx
    - apps/admin-app/src/pages/trainer/components/PayoutsTab.test.tsx
  modified:
    - apps/admin-app/src/pages/trainer/components/PayoutsTab.tsx
    - apps/admin-app/src/pages/trainer/TrainerPage.tsx

key-decisions:
  - "PayoutsTab props changed from { trainer: TrainerDetail } to { trainerId: string } — cleaner contract; TrainerPage passes trainer.id (from useTrainer)"
  - "Reception gate is a React early-return before OwnerPayoutsTab sub-component — hooks in OwnerPayoutsTab never instantiate for reception (belt-and-suspenders with enabled: can() in hooks)"
  - "useAccrualPreview triggered on-demand via enabled=previewEnabled flag; staleTime=0 so each 'Просмотр' click fetches fresh data"
  - "Period picker uses type=month inputs; component derives first-of-month (periodStart) and last-of-month (periodEnd) from YYYY-MM string"
  - "mark-paid onError for 409 already_paid also calls invalidateQueries to sync accruals list (belt-and-suspenders)"
  - "PayoutsTab test mocks @/features/payroll/api entirely (not transport layer) to comply with ESLint pages/ import-boundary rule"
  - "ConfirmModal tone='default' for mark-paid (non-destructive, primary CTA)"

patterns-established:
  - "Owner-only tab: can() early-return guard + sub-component isolation to prevent hooks from firing for reception"
  - "On-demand query via enabled flag + manual refetch (alternative to refetchOnMount=always)"
  - "Test pattern for pages/ layer: mock @/features/*/api instead of @/api/client (ESLint boundary)"

requirements-completed: [TRN-02]

# Metrics
duration: 9min
completed: 2026-06-13
---

# Phase 102 Plan 04: Payroll HTTP Layer + PayoutsTab Wiring Summary

**Payroll feature built end-to-end: Zod schemas + TanStack Query hooks (owner-only, enabled-gated) + wired PayoutsTab with reception Lock gate, comp-config editor (INSERT-only versioned, kopecks/bps conversion), preview→run flow, accruals list, and mark-paid confirm**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-06-13T17:51:01Z
- **Completed:** 2026-06-13T18:00:XX Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Full payroll HTTP layer: PayrollConfigSchema/Input/Preview/Accrual/AccrualsList/RunAccrual Zod schemas; payrollKeys factory; 6 TanStack Query hooks/mutations all owner-only and enabled-gated
- All threat mitigations landed: T-102-PAY-RBAC (reception gate before hooks fire), T-102-PAY-MONEY (integer kopecks/bps schemas + conversion), T-102-PAY-VERSION (INSERT-only PUT config), T-102-PAY-TERMINAL (409 handled calmly), T-102-PAY-PII (fixed Russian copy), T-102-PAY-SC (no new deps)
- PayoutsTab fully wired: reception Lock EmptyState (zero API calls), owner comp-config editor, preview→run with period picker + 422 Callout, accruals list with status badges, mark-paid ConfirmModal with 409 already_paid handling
- Admin-app gate: 274/274 tests, typecheck clean, lint clean, build green

## Task Commits

1. **Task 1 RED** - `b007be1a` (test) — api.test.tsx (9 failing tests)
2. **Task 1 GREEN** - `7773470b` (feat) — schemas.ts, keys.ts, api.ts (9/9 passing)
3. **Task 2 RED** - `628b0f67` (test) — PayoutsTab.test.tsx (failing)
4. **Task 2 GREEN** - `39bedb18` (feat) — PayoutsTab.tsx wired, TrainerPage.tsx updated (8/8 passing)

## Files Created/Modified

- `apps/admin-app/src/features/payroll/schemas.ts` — PayrollConfigSchema/Input, AccrualPreviewSchema, AccrualSchema (status enum), AccrualsListResponseSchema, RunAccrualSchema
- `apps/admin-app/src/features/payroll/keys.ts` — payrollKeys factory (all/configs/config/previews/preview/accrualsList/accruals)
- `apps/admin-app/src/features/payroll/api.ts` — 6 hooks: usePayrollConfig/useAccrualPreview/useAccruals/useSetPayrollConfig/useRunAccrual/useMarkAccrualPaid; ApiError re-export
- `apps/admin-app/src/features/payroll/api.test.tsx` — 9 tests (schema validation, RBAC disabled-for-reception, 409 calm handling, paginated envelope parse)
- `apps/admin-app/src/pages/trainer/components/PayoutsTab.tsx` — fully wired (reception Lock gate, comp-config editor, preview→run, accruals list, mark-paid)
- `apps/admin-app/src/pages/trainer/components/PayoutsTab.test.tsx` — 8 tests (reception Lock gate, hooks never called, 404 warn Callout, schema conversion round-trips)
- `apps/admin-app/src/pages/trainer/TrainerPage.tsx` — updated: `<PayoutsTab trainerId={trainerId} />` (was `trainer={trainerDetail}`)

## Key Implementation Decisions

### PayoutsTab Mount Contract
- **trainerId source:** `TrainerPage` passes `trainer.id` (from `useTrainer(trainerId)`) as `trainerId` prop
- **Props changed:** from `{ trainer: TrainerDetail }` (mock) to `{ trainerId: string }` (real)

### PUT Config Body Shape
```json
{ "commissionPctBps": 1000, "sessionFeeKopecks": 50000, "effectiveFrom": "2026-01-01" }
```
All integers. Display/send conversion: `sessionFeeKopecks = Math.round(rubles * 100)`, `commissionPctBps = Math.round(pct * 100)`.

### Preview Trigger
`useAccrualPreview` is an on-demand query: `enabled: previewEnabled && !!periodStart && !!periodEnd`. User clicks «Просмотр» → `setPreviewEnabled(true)` + `previewQuery.refetch()`. `staleTime: 0` ensures every click fetches fresh data.

### Period Picker → periodStart/periodEnd Mapping
- `type=month` inputs produce `YYYY-MM` values
- `periodStart = YYYY-MM-01` (first day)
- `periodEnd = YYYY-MM-{lastDay}` (computed via `new Date(year, month, 0).getDate()`)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ApiError constructor signature mismatch**
- **Found during:** Task 1 typecheck
- **Issue:** Test used `new ApiError('code', 'message', 409)` — constructor is `(code, message, fields?, options?)` so `409` was assigned to `fields: Record<string, unknown>`, failing typecheck
- **Fix:** Removed the third argument: `new ApiError('code', 'message')`
- **Files modified:** `features/payroll/api.test.tsx`
- **Committed in:** `7773470b` (Task 1 GREEN)

**2. [Rule 3 - Blocking] PayoutsTab test `.ts` extension rejected JSX**
- **Found during:** Task 1 initial RED test run
- **Issue:** Created test as `.test.ts` but contained JSX; Vite/esbuild rejected it
- **Fix:** Renamed to `.test.tsx`
- **Files modified:** `features/payroll/api.test.tsx`
- **Committed in:** RED commit (renamed)

**3. [Rule 2 - ESLint boundary] PayoutsTab test in pages/ cannot import @/api/client**
- **Found during:** Task 2 lint
- **Issue:** Initial test mock used `import { staffRequest } from '@/api/client'` — ESLint restricts this in `src/pages/**`
- **Fix:** Refactored test to mock `@/features/payroll/api` module instead; imports `ApiError` from the re-export; removed direct `staffRequest` reference
- **Files modified:** `pages/trainer/components/PayoutsTab.test.tsx`
- **Committed in:** `39bedb18` (Task 2 GREEN)

**4. [Rule 1 - Bug] UseMutationResult type incompatibility in test mocks**
- **Found during:** Task 2 typecheck
- **Issue:** Partial mutation mock objects typed as `ReturnType<typeof useMutation>` failed TS strict checks
- **Fix:** Cast via `as unknown as ReturnType<typeof hookName>` pattern (standard test mock approach)
- **Files modified:** `pages/trainer/components/PayoutsTab.test.tsx`
- **Committed in:** `39bedb18` (Task 2 GREEN)

**Total deviations:** 4 auto-fixed. All were compile-time or ESLint errors; no scope creep.

## Known Stubs

None — all plan artifacts produce real functionality. The only remaining stub in the trainer domain is:
- `HistoryTab` on mock `trainerDetail` in `TrainerPage.tsx` (pre-existing stub, documented in 102-02 SUMMARY; no history endpoint in Phase 102)

## Threat Flags

None — all payroll endpoints are owner-only; no new trust boundaries introduced beyond what the plan's threat model registered.

## Self-Check: PASSED

All created files verified on disk. All task commits verified in git log.

| Item | Status |
|------|--------|
| `features/payroll/schemas.ts` | FOUND |
| `features/payroll/keys.ts` | FOUND |
| `features/payroll/api.ts` | FOUND |
| `features/payroll/api.test.tsx` | FOUND |
| `pages/trainer/components/PayoutsTab.test.tsx` | FOUND |
| `102-04-SUMMARY.md` | FOUND |
| Commit b007be1a (test RED 1) | FOUND |
| Commit 7773470b (feat GREEN 1) | FOUND |
| Commit 628b0f67 (test RED 2) | FOUND |
| Commit 39bedb18 (feat GREEN 2) | FOUND |
