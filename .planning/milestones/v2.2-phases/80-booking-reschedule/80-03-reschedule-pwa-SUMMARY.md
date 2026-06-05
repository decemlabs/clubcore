---
phase: 80-booking-reschedule
plan: "03"
subsystem: client-pwa
tags: [booking, reschedule, pwa, react, vitest, tanstack-query, idempotency]
dependency_graph:
  requires:
    - phase: 80-01
      provides: reschedule-endpoint-contract
    - phase: 80-02
      provides: reschedule-booking-endpoint (POST /client/booking/{id}/reschedule)
  provides:
    - useRescheduleBooking-mutation-hook
    - real-slot-reschedule-view
    - reschedule-vitest-suite-7-tests
  affects: [client-pwa, clientQueries, BookingManageSheet]
tech_stack:
  added: []
  patterns:
    - tanstack-query-mutation-with-idempotency-key
    - real-slots-trainer-filter-ux-only
    - error-code-to-copy-mapping
    - vi-mock-at-data-barrel
key_files:
  created:
    - apps/client-pwa/src/screens/sheets/BookingManageSheet.reschedule.test.jsx
  modified:
    - apps/client-pwa/src/lib/clientQueries.ts
    - apps/client-pwa/src/data/index.js
    - apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx
    - apps/client-pwa/src/screens/sheets/BookingManageSheet.cancel.test.jsx
key_decisions:
  - "Filter slots by trainerName (not trainerId) because BookingResponse/BookingItem have trainerName but not trainerId; both share trainerName field"
  - "Client trainer filter is UX-only (T-80-16); authoritative guard is server-side slot_trainer_mismatch"
  - "Flat slot list replaces two-step date+time mock UI; real slots each have a single startTime so grouping adds no value over a list"
  - "Cancel test stubs extended to include useRescheduleBooking + useClientAvailableSlots stubs to avoid QueryClientProvider errors in jsdom (Rule 1 auto-fix)"
requirements-completed: [RESCH-03]
duration: 15min
completed: "2026-06-03"
---

# Phase 80 Plan 03: Reschedule PWA Wiring Summary

**useRescheduleBooking TanStack mutation hook + real-slot BookingManageSheet reschedule view wired to POST /client/booking/{id}/reschedule with Idempotency-Key; mock CALENDAR/TIME_SLOTS/BUSY_SLOTS removed; 7-test vitest suite green.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-06-03T17:40:00Z
- **Completed:** 2026-06-03T17:55:00Z
- **Tasks:** 3
- **Files modified:** 4
- **Files created:** 1

## Accomplishments

- `useRescheduleBooking()` in `clientQueries.ts`: useMutation with `{ bookingId, newSlotId, idempotencyKey }` args, `POST /api/v1/client/booking/{booking_id}/reschedule` with Idempotency-Key header, onSettled invalidates both `bookings()` and `availableSlots()` cache keys
- `data/index.js`: `useRescheduleBooking` added to re-export group alongside `useCancelBooking`
- `BookingManageSheet.jsx`: CALENDAR/TIME_SLOTS/BUSY_SLOTS mock imports fully removed; real `useClientAvailableSlots` data filtered by `trainerName` to same trainer; reschedule confirm handler calls `rescheduleMutation.mutateAsync` with crypto.randomUUID idempotency key; three 409 error codes mapped to distinct Russian copy; button disabled while isPending; done-reschedule state shows real slot startTime in Europe/Moscow locale
- `BookingManageSheet.reschedule.test.jsx`: 7 vitest tests covering all plan behaviors
- `BookingManageSheet.cancel.test.jsx`: extended `@/data` mock to stub the two new hooks to prevent QueryClientProvider errors in jsdom

## Task Commits

1. **Task 1: useRescheduleBooking hook + data/index.js export** — `438edf85` (feat)
2. **Task 2: Wire BookingManageSheet reschedule to real slots + endpoint** — `6ae2b8b3` (feat)
3. **Task 3: Vitest reschedule wiring suite** — `dff600cb` (test)

## Files Created/Modified

- `apps/client-pwa/src/lib/clientQueries.ts` — Added `useRescheduleBooking` export function after `useCancelBooking`
- `apps/client-pwa/src/data/index.js` — Added `useRescheduleBooking` to re-export list
- `apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx` — Removed CALENDAR/TIME_SLOTS/BUSY_SLOTS; added useRescheduleBooking + useClientAvailableSlots; wired reschedule flow end-to-end
- `apps/client-pwa/src/screens/sheets/BookingManageSheet.reschedule.test.jsx` — 7 reschedule wiring tests (new file)
- `apps/client-pwa/src/screens/sheets/BookingManageSheet.cancel.test.jsx` — Extended @/data mock stubs for the two new hooks

## Decisions Made

- **Filter by trainerName not trainerId**: `BookingResponse` and `BookingItem` both have `trainerName` but not `trainerId`. Filtering by `trainerName` is sufficient since `AvailableSlotItem` also exposes `trainerName`. The server-side `slot_trainer_mismatch` 409 is the authoritative guard regardless.
- **Flat slot list UI**: The mock used a two-step date-strip + time-grid flow backed by static data. Real slots from `useClientAvailableSlots` each carry a full `startTime` ISO string — a flat list grouped by nothing is the simplest and most correct representation. The date-strip step had no UX value without static CALENDAR entries.
- **Cancel test stubs extended**: After Task 2, `BookingManageSheet` calls all three hooks unconditionally. The existing cancel test only stubbed `useCancelBooking`. Without stubs for the two new hooks, the cancel test threw `No QueryClient set`. This is a correctness fix, not a scope change.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Cancel test broke after Task 2 added unconditional hook calls**
- **Found during:** Task 3 (running cancel.test.jsx before creating reschedule test)
- **Issue:** `BookingManageSheet` now calls `useRescheduleBooking()` and `useClientAvailableSlots()` unconditionally in the component body. The existing cancel test only mocked `useCancelBooking`. The two new hooks require `QueryClientProvider` which the jsdom test environment does not provide.
- **Fix:** Extended the `vi.mock('@/data')` factory in `cancel.test.jsx` to also stub `useRescheduleBooking` (returns idle mutation) and `useClientAvailableSlots` (returns empty items page).
- **Files modified:** `apps/client-pwa/src/screens/sheets/BookingManageSheet.cancel.test.jsx`
- **Commit:** dff600cb

---

**Total deviations:** 1 auto-fixed (Rule 1 - test regression from Task 2)
**Impact on plan:** Necessary correctness fix. Cancel test suite back to green (5/5). No scope creep.

## Issues Encountered

None beyond the auto-fixed deviation above.

## Known Stubs

None — all functionality is fully implemented. Slot data comes from real `useClientAvailableSlots` query; reschedule calls real `useRescheduleBooking` mutation.

## Threat Flags

No new threat surface beyond what the plan's threat model covers:
- T-80-14 (error banner): only fixed Russian copy per known code; no raw backend message in DOM ✓
- T-80-15 (replay): crypto.randomUUID() per-intent idempotency key ✓
- T-80-16 (client trainer filter): UX-only filter acknowledged; server-side guard is authoritative ✓

## Verification Results

- `pnpm exec tsc --noEmit`: exits 0 (no TypeScript errors)
- `pnpm exec eslint src/lib/clientQueries.ts`: exits 0
- `pnpm exec eslint src/screens/sheets/BookingManageSheet.jsx`: exits 0 (jsx in ignored pattern — warning only, no errors)
- `pnpm --filter client-pwa test`: 99 tests passed across 17 test files including:
  - BookingManageSheet.reschedule.test.jsx: 7 passed
  - BookingManageSheet.cancel.test.jsx: 5 passed
- Mock CALENDAR/TIME_SLOTS/BUSY_SLOTS: 0 references in BookingManageSheet.jsx (grep count = 0)

## Self-Check: PASSED

Files verified to exist:
- apps/client-pwa/src/lib/clientQueries.ts: FOUND (useRescheduleBooking present)
- apps/client-pwa/src/data/index.js: FOUND (useRescheduleBooking re-export present)
- apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx: FOUND (useRescheduleBooking + useClientAvailableSlots imports present; CALENDAR/TIME_SLOTS/BUSY_SLOTS absent)
- apps/client-pwa/src/screens/sheets/BookingManageSheet.reschedule.test.jsx: FOUND

Commits verified:
- 438edf85: FOUND (Task 1 feat)
- 6ae2b8b3: FOUND (Task 2 feat)
- dff600cb: FOUND (Task 3 test)

---
*Phase: 80-booking-reschedule*
*Completed: 2026-06-03*
