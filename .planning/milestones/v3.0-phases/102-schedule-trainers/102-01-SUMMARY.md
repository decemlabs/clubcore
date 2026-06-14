---
phase: 102-schedule-trainers
plan: "01"
subsystem: schedule-write-layer
tags: [schedule, tdd, mutations, idempotency, force-override, owner-only]
dependency_graph:
  requires: []
  provides:
    - features/schedule/schemas.ts (Zod wire schemas + mutation input schemas)
    - features/schedule/keys.ts (scheduleKeys query-key factory)
    - features/schedule/api.ts (TanStack Query mutations + queries, real HTTP)
    - components/modals/ScheduleManagementModal.tsx (owner-only 3-tab schedule UI)
  affects:
    - pages/schedule/SchedulePage.tsx (useSchedule() mock interim hook, no api/client import)
    - components/icons/index.tsx (CalendarPlus, CalendarX added)
tech_stack:
  added: []
  patterns:
    - TDD RED→GREEN per task
    - Idempotency-Key via crypto.randomUUID() inside mutationFn (per-attempt)
    - 409 force-override flow (conflict state in modal, danger re-submit with force=true)
    - React Rules of Hooks (all hooks before early return)
    - ESLint import-boundary: ApiError re-exported from features/schedule/api
key_files:
  created:
    - apps/admin-app/src/features/schedule/schemas.ts
    - apps/admin-app/src/features/schedule/schemas.test.ts
    - apps/admin-app/src/features/schedule/keys.ts
    - apps/admin-app/src/features/schedule/api.test.tsx
    - apps/admin-app/src/components/modals/ScheduleManagementModal.tsx
    - apps/admin-app/src/components/modals/ScheduleManagementModal.test.tsx
  modified:
    - apps/admin-app/src/features/schedule/api.ts
    - apps/admin-app/src/pages/schedule/SchedulePage.tsx
    - apps/admin-app/src/components/icons/index.tsx
decisions:
  - "D-102-01-TRAINERSHAPE: useTrainers() return shape cast defensively (pre-102-02 compat) — items read via unknown cast"
  - "D-102-01-SCHEDULEPAGE: SchedulePage.tsx uses plain Promise+setTimeout mock (no @/api/client import in page) until 102-03 real read layer"
  - "D-102-01-APIERROR: ApiError re-exported from features/schedule/api so modal/pages don't import @/api/client directly"
  - "D-102-01-FORCEPATH: force=true path never default — always requires user to see conflict state and click danger button"
metrics:
  duration: "~2h (multi-session, context compacted)"
  completed: "2026-06-13"
  tasks_completed: 3
  files_count: 9
---

# Phase 102 Plan 01: Schedule Write Layer Summary

**One-liner:** Zod wire schemas + TanStack Query mutations with per-attempt Idempotency-Key + owner-only AdaptiveModal with 3 tabs and 409 force-override conflict flow, all TDD-driven.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Schedule schemas + keys | `8f05763c` | schemas.ts, schemas.test.ts, keys.ts |
| 2 | TanStack Query hooks (write layer) | `1888945a` | api.ts (replaced mock), api.test.tsx |
| 3 | ScheduleManagementModal | `f9a4cdb8` | ScheduleManagementModal.tsx, .test.tsx, icons/index.tsx, SchedulePage.tsx |

## Verification

- `pnpm -F @clubcore/admin-app lint` — clean (no errors)
- `pnpm -F @clubcore/admin-app typecheck` — clean
- `pnpm vitest run` — 222 tests pass (15 test files)
- `pnpm -F @clubcore/admin-app build` — success

## Must-Haves Verified

- Owner publishes a trainer slot from ScheduleManagementModal via real POST /api/v1/trainer-slots
- Owner creates recurring template (POST /api/v1/trainer-slots/templates) and time-off block (POST /api/v1/trainer-slots/time-off)
- Time-off 409 `time_off_booked_conflict` transitions modal to conflict Callout + force-override button (modal stays open)
- All schedule mutations carry a fresh per-attempt Idempotency-Key (`crypto.randomUUID()` INSIDE mutationFn)
- Reception cannot reach the management modal (`can(role,'create','schedule-slots')` returns null before render)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] api.test.tsx JSX in .ts file**
- Found during: Task 2 GREEN
- Issue: `renderHook` with `<QueryClientProvider>` JSX in a `.ts` file caused parse error
- Fix: Renamed `api.test.ts` to `api.test.tsx`
- Files modified: `src/features/schedule/api.test.tsx`
- Commit: `1888945a`

**2. [Rule 1 - Bug] React Rules of Hooks violation in ScheduleManagementModal**
- Found during: Task 3 lint
- Issue: `useState`, `useEffect`, `useTrainers` called after `if (!can(...)) return null` (conditional hooks)
- Fix: Moved all hook calls before the `can()` early return; early return now follows all hooks
- Files modified: `src/components/modals/ScheduleManagementModal.tsx`
- Commit: `f9a4cdb8`

**3. [Rule 2 - Import boundary] SchedulePage.tsx imported @/api/client directly**
- Found during: Task 3 lint
- Issue: `mockResponse` imported from `@/api/client` in a page file — violates ESLint import restriction
- Fix: Replaced `mockResponse()` call with a plain `new Promise<ScheduleData>(resolve => setTimeout(resolve, 120))` inline in queryFn
- Files modified: `src/pages/schedule/SchedulePage.tsx`
- Commit: `f9a4cdb8`

**4. [Rule 1 - Bug] api.test.tsx `import()` type annotation ESLint warning**
- Found during: Task 3 lint (api.test.tsx cleanup)
- Issue: `importOriginal<typeof import('@/api/client')>()` triggers `@typescript-eslint/no-import-type-side-effects` style warning
- Fix: Changed to `importOriginal<{ staffRequest: unknown; ApiError: unknown }>()`
- Files modified: `src/features/schedule/api.test.tsx`
- Commit: `f9a4cdb8`

**5. [Rule 2 - Missing] CalendarPlus/CalendarX missing from icon barrel**
- Found during: Task 3 implementation (ScheduleManagementModal references these icons)
- Issue: `@/components/icons` did not export `CalendarPlus` or `CalendarX`
- Fix: Added both to `components/icons/index.tsx` exports
- Commit: `f9a4cdb8`

**6. [Rule 3 - Compat] useTrainers() signature mismatch**
- Found during: Task 3 implementation
- Issue: Pre-102-02 `useTrainers()` accepts 0 args; plan says pass `{ active: true }`. Shape differs from expected `{ items }`.
- Fix: Called `useTrainers()` with no args, added defensive cast via `unknown as { items?: ...[] }` to handle both pre- and post-102-02 shapes
- Files modified: `src/components/modals/ScheduleManagementModal.tsx`
- Commit: `f9a4cdb8`

## TDD Gate Compliance

- Task 1: `test(102-01)` commit (RED) → `feat(102-01)` commit (GREEN) — schema tests (23) written before implementation
- Task 2: `test(102-01)` commit (RED) → `feat(102-01)` commit (GREEN) — hook tests (3) written before implementation
- Task 3: `test(102-01)` commit (RED) → `feat(102-01)` commit (GREEN) — modal tests (6) written before implementation

All TDD gate commits present in git log.

## Known Stubs

- `SchedulePage.tsx` `useSchedule()` function: Uses `Promise+setTimeout` with static `scheduleData` mock. Will be replaced with `useTrainerSlots` in Phase 102-03 (calendar read-merge layer). Intentional stub per plan.

## Threat Flags

None — no new network endpoints, auth paths, or trust-boundary schema changes introduced. ScheduleManagementModal only creates UI; backend authority enforced at API level. `can()` gate is defense-in-depth (T-102-IDOR).

## Self-Check: PASSED
