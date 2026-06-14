---
phase: 102-schedule-trainers
plan: "02"
subsystem: ui
tags: [react, tanstack-query, zod, trainers, crud, http]

# Dependency graph
requires:
  - phase: 102-schedule-trainers/01
    provides: schedule http layer pattern (staffRequest, ApiError, key factory, Idempotency-Key)
provides:
  - Trainers HTTP layer: TrainerSchema, TrainersListResponseSchema, TrainerCreate/UpdateSchema (Zod)
  - Query key factory (trainersKeys) for cache coordination
  - useTrainers / useTrainer TanStack Query hooks against real /api/v1/trainers
  - useCreateTrainer / useUpdateTrainer / useDeleteTrainer mutations with 409-aware error handling
  - Reduced TrainersPage: Load/Requests/Earnings sections removed; Roster wired to real data; owner CRUD affordances
  - TrainerHero / TrainerKpis / OverviewTab wired to real TrainerData; TrainerFormModal wired to PATCH/POST
  - Booking-safe OverviewTab today-schedule stub with dependency contract for Plan 102-03
affects: [102-03, 102-04, 104]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Explicit query Record build inside queryFn to satisfy staffRequest's index-signature constraint"
    - "phone_exists 409 suppressed at mutation level; caller renders inline Callout (no toast)"
    - "trainer_in_use 409 → toast.error from mutation onError"
    - "Wave-1 stub: OverviewTab imports no non-existent hook; shows EmptyState + TODO(102-03) comment"
    - "PayoutsTab / HistoryTab kept on mock trainerDetail; wiring deferred to Plan 102-04 / Phase 104"
    - "TrainerKpis returns null; no aggregate KPI endpoint in Phase 102 (TODO Phase 104)"
    - "TrainerHero owns local editOpen state; TrainersPage manages formTrainer + deleteTarget state"
    - "HireCard, LoadHeatmap, RequestsCard, EarningsCard, TrainersKpis, TrainerFilterTabs removed"
    - "ApiError re-exported from features/trainers/api.ts for ESLint import-boundary compliance (D-100-03)"

key-files:
  created:
    - apps/admin-app/src/features/trainers/schemas.ts
    - apps/admin-app/src/features/trainers/keys.ts
    - apps/admin-app/src/features/trainers/api.test.ts
  modified:
    - apps/admin-app/src/features/trainers/api.ts
    - apps/admin-app/src/pages/trainers/TrainersPage.tsx
    - apps/admin-app/src/pages/trainers/components/RosterCard.tsx
    - apps/admin-app/src/pages/trainers/components/TrainerFilterTabs.tsx
    - apps/admin-app/src/pages/trainers/components/columns.tsx
    - apps/admin-app/src/pages/trainer/TrainerPage.tsx
    - apps/admin-app/src/pages/trainer/components/TrainerHero.tsx
    - apps/admin-app/src/pages/trainer/components/OverviewTab.tsx
    - apps/admin-app/src/pages/trainer/components/TrainerKpis.tsx
    - apps/admin-app/src/components/modals/TrainerFormModal.tsx
    - apps/admin-app/src/components/modals/ModalsProvider.tsx
    - apps/admin-app/src/components/icons/index.tsx

key-decisions:
  - "TrainersPage manages formTrainer (TrainerData | null) + deleteTarget (TrainerData | null) locally — no global modals store needed for CRUD"
  - "TrainerHero owns local editOpen state — avoids prop-drilling from TrainerPage"
  - "ModalsProvider passes trainer={undefined} to TrainerFormModal (create mode via global key); primary CRUD flows managed page-locally"
  - "TrainerFilterTabs returns null — single visible tab after Load/Requests/Earnings removal is noise per UI-SPEC §6.1"
  - "TrainerKpis returns null — aggregate KPI endpoint absent in Phase 102, deferred to Phase 104"
  - "useTrainers({active:true}) called on TrainersPage; filter applied as query param via explicit Record build"
  - "Trainer mutations carry no Idempotency-Key (not required by backend contract for trainers)"

patterns-established:
  - "Record<string, string | number | boolean> built explicitly inside queryFn — do not pass typed filter directly to staffRequest query"
  - "409 suppression split: mutation swallows phone_exists (caller shows Callout); mutation toasts trainer_in_use"
  - "Wave dependency stub pattern: accept prop for future hook, void it, show EmptyState, leave TODO(wave-plan) comment"

requirements-completed: [TRN-01]

# Metrics
duration: 90min
completed: 2026-06-13
---

# Phase 102 Plan 02: Trainers HTTP Layer + Roster/Detail Wiring Summary

**Trainers catalog wired end-to-end: real HTTP layer (Zod schemas + TanStack Query + CRUD mutations), TrainersPage reduced to Roster-only with owner affordances, TrainerHero/OverviewTab wired to real TrainerData, TrainerFormModal wired to PATCH/POST with 409-aware error handling**

## Performance

- **Duration:** ~90 min
- **Started:** 2026-06-13T12:00:00Z
- **Completed:** 2026-06-13T14:23:50Z
- **Tasks:** 3
- **Files modified:** 16

## Accomplishments

- Full HTTP layer for trainers: TrainerSchema (Zod), key factory, useTrainers/useTrainer queries, useCreateTrainer/useUpdateTrainer/useDeleteTrainer mutations with 409-code handling
- TrainersPage reduced: Load/Requests/Earnings/HireCard/TrainersKpis removed; Roster wired to real data; owner-only create/edit/delete affordances; 241/241 tests passing, typecheck clean, build green
- Trainer detail page wired: TrainerHero renders real fullName/specialization/photoUrl/isActive/bio/phone; OverviewTab today-schedule safe stub (no import of non-existent Plan 102-03 hook) with dependency contract comment

## Task Commits

1. **Task 1: HTTP layer** - `644a0d14` (feat) — schemas.ts, keys.ts, api.ts (http), api.test.ts (19 tests)
2. **Task 2: TrainersPage + TrainerFormModal** - `2b2b8d02` (feat) — TrainersPage, RosterCard, columns, TrainerFormModal, ModalsProvider, icons/index
3. **Task 3: Trainer detail wiring** - `c48bc3ee` (feat) — TrainerHero, TrainerKpis, OverviewTab, TrainerPage

## Files Created/Modified

- `apps/admin-app/src/features/trainers/schemas.ts` — TrainerSchema, TrainersListResponseSchema, TrainerUpdateSchema, TrainerCreateSchema
- `apps/admin-app/src/features/trainers/keys.ts` — trainersKeys factory (all/lists/list/details/detail)
- `apps/admin-app/src/features/trainers/api.ts` — useTrainers, useTrainer, useCreateTrainer, useUpdateTrainer, useDeleteTrainer; ApiError re-export
- `apps/admin-app/src/features/trainers/api.test.ts` — 19 schema/mutation-contract tests (no network)
- `apps/admin-app/src/pages/trainers/TrainersPage.tsx` — Roster-only, owner CRUD, TrainerFormModal + ConfirmModal state
- `apps/admin-app/src/pages/trainers/components/RosterCard.tsx` — TrainerData props, photoUrl/initials, active dot, owner Pencil/Trash2
- `apps/admin-app/src/pages/trainers/components/columns.tsx` — trainerColumns factory with conditional action column
- `apps/admin-app/src/pages/trainers/components/TrainerFilterTabs.tsx` — returns null (single tab, noise removed)
- `apps/admin-app/src/pages/trainer/TrainerPage.tsx` — useTrainer(), TrainerHero real data, PayoutsTab/HistoryTab still on mock trainerDetail
- `apps/admin-app/src/pages/trainer/components/TrainerHero.tsx` — real TrainerData, photoUrl/initials, isActive badge, local edit state
- `apps/admin-app/src/pages/trainer/components/TrainerKpis.tsx` — returns null (aggregate endpoint absent)
- `apps/admin-app/src/pages/trainer/components/OverviewTab.tsx` — trainerId prop accepted; today-schedule EmptyState stub; regulars on mock
- `apps/admin-app/src/components/modals/TrainerFormModal.tsx` — trainer?: TrainerData, trainerToFormState(), PATCH sends only changed fields, phone_exists Callout
- `apps/admin-app/src/components/modals/ModalsProvider.tsx` — trainer={undefined} (create mode)
- `apps/admin-app/src/components/icons/index.tsx` — added Pencil re-export

## Decisions Made

- **CRUD state is page-local, not global modals store:** TrainersPage manages `formTrainer` + `deleteTarget` directly; no global open(key) needed for within-page CRUD flows
- **TrainerHero owns editOpen:** self-contained edit entry point without prop-drilling from TrainerPage
- **Trainer mutations carry no Idempotency-Key:** backend contract does not require it for PATCH/POST/DELETE /trainers
- **phone_exists 409:** mutation returns silently; TrainerFormModal sets phoneExistsError state → inline Callout (no toast). Enforced by api.test.ts invariant
- **trainer_in_use 409:** mutation toasts `toast.error('Нельзя удалить', { description: '…' })` from onError
- **TrainerFilterTabs returns null:** single visible tab after Load/Requests/Earnings removal is noise (UI-SPEC §6.1)
- **TrainerKpis returns null:** no aggregate endpoint in Phase 102; deferred Phase 104

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `staffRequest` query param type mismatch**
- **Found during:** Task 1 (HTTP layer)
- **Issue:** TypeScript rejected `TrainersListQuery` passed directly to `staffRequest({ query })` — the transport expects `Record<string, string | number | boolean>` but `{ active?: boolean }` lacks an index signature
- **Fix:** Build explicit `Record<string, string | number | boolean>` inside queryFn, copy fields conditionally
- **Files modified:** `apps/admin-app/src/features/trainers/api.ts`
- **Verification:** typecheck passes
- **Committed in:** `644a0d14` (Task 1)

**2. [Rule 3 - Blocking] `Pencil` not exported from `@/components/icons`**
- **Found during:** Task 2 (RosterCard)
- **Issue:** `RosterCard.tsx` imported `Pencil` from `@/components/icons`; icon was not in the re-export index
- **Fix:** Added `Pencil` to `apps/admin-app/src/components/icons/index.tsx`
- **Files modified:** `apps/admin-app/src/components/icons/index.tsx`
- **Verification:** typecheck passes; icon renders
- **Committed in:** `2b2b8d02` (Task 2)

**3. [Rule 3 - Blocking] `ModalsProvider` API mismatch after TrainerFormModal signature change**
- **Found during:** Task 2 (TrainerFormModal rewrite)
- **Issue:** `ModalsProvider` was passing `payload={state?.options?.trainerForm}` to the rewritten `TrainerFormModal`; new API expects `trainer?: TrainerData`
- **Fix:** Changed to `trainer={undefined}` in ModalsProvider (create mode path preserved)
- **Files modified:** `apps/admin-app/src/components/modals/ModalsProvider.tsx`
- **Verification:** typecheck passes
- **Committed in:** `2b2b8d02` (Task 2)

---

**Total deviations:** 3 auto-fixed (3 blocking)
**Impact on plan:** All three were compile-time type errors blocking task completion. No scope creep.

## Known Stubs

| Stub | File | Line | Reason |
|------|------|------|--------|
| Today-schedule EmptyState | `apps/admin-app/src/pages/trainer/components/OverviewTab.tsx` | 50–55 | `useBookingsByTrainer` lands in Plan 102-03 (wave 2); interim EmptyState with `// TODO(102-03)` |
| Regulars from mock `trainerDetail` | `apps/admin-app/src/pages/trainer/components/OverviewTab.tsx` | 36 | No regulars endpoint in Phase 102; `// TODO Phase 104` |
| `PayoutsTab` on mock `trainerDetail` | `apps/admin-app/src/pages/trainer/TrainerPage.tsx` | 59 | Plan 102-04 owns payroll wiring |
| `HistoryTab` on mock `trainerDetail` | `apps/admin-app/src/pages/trainer/TrainerPage.tsx` | 62 | No history endpoint in Phase 102; `// TODO Phase 104` |
| `TrainerKpis` returns null | `apps/admin-app/src/pages/trainer/components/TrainerKpis.tsx` | 9–11 | No aggregate KPI endpoint in Phase 102; `// TODO Phase 104` |

All stubs are intentional and deferred to documented future plans. Plan objective (Roster + Hero wired to real data, owner CRUD shipped) is fully achieved.

## Issues Encountered

None beyond the 3 type-blocking deviations already documented above.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 102-03 (bookings hooks) can now call `trainersKeys.detail(id)` for cache invalidation and pass `trainerId` to the existing `OverviewTab` prop without any API changes
- Plan 102-04 (payouts wiring) receives `trainerDetail` mock shape unchanged — no breaking changes
- `TrainerData` type is exported from `features/trainers/schemas` and stable for downstream consumers

---
*Phase: 102-schedule-trainers*
*Completed: 2026-06-13*
