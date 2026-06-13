---
phase: 102-schedule-trainers
plan: "03"
subsystem: admin-app/schedule
tags: [bookings, calendar-merge, slot-click-routing, pt-sessions, race-safe, tdd]
dependency_graph:
  requires:
    - 102-01 (useTrainerSlots, scheduleKeys, ScheduleManagementModal)
    - 102-02 (useTrainers, TrainerData schema)
    - 100 (staffRequest transport, ApiError)
    - 101 (usePtPackagesByClient, useClients)
  provides:
    - features/bookings/{schemas,keys,api}.ts — booking http layer (queries + mutations)
    - BookingModal.tsx — race-safe booking create from available calendar slot
    - BookingDetailModal.tsx — booking detail + cancel (24h-window) + complete via pt-sessions
    - BookingDetailLoader.tsx — thin loader wrapper for slot click → detail modal
    - SchedulePage.tsx — real calendar merge (slots+bookings) + slot-click routing + owner FAB
    - WeekCalendar.tsx — accepts CalendarEvent[] (decoupled from mock ScheduleData)
    - EventBlock.tsx — booked badge + time-off diagonal-stripe visual states
    - ScheduleToolbar.tsx — real Тренер filter + wired week navigator (Зал+Тип removed)
    - calendar-utils.ts — CalendarEvent type + mergeSlotBookings() pure function
    - OverviewTab.tsx — wired to useBookingsByTrainer today-schedule
  affects:
    - WeekCalendar (now accepts CalendarEvent[] not mock ScheduleData)
    - SchedulePageHead (decoupled to ScheduleHeadData minimal interface)
    - ScheduleToolbar (ScheduleData dependency removed)
    - EventBlock (new visual states for booked/time-off)
tech_stack:
  added: []
  patterns:
    - "mergeSlotBookings() pure function: slots+bookings → CalendarEvent[] with type discriminator"
    - "Idempotency-Key: crypto.randomUUID() INSIDE mutationFn (per-attempt, T-102-BK-IDEM)"
    - "409 race handling: slot_already_booked → inline Callout + scheduleKeys invalidate (T-102-BK-RACE)"
    - "useCompleteBooking: POST /api/v1/pt-sessions {ptPackageId,trainerId,performedAt,bookingId} — NO clientId (T-102-BK-COMPLETE)"
    - "BookingDetailLoader: thin React component that fetches booking then renders modal (avoids conditional hook)"
    - "Trainer color: deterministic palette indexed by position in useTrainers({active:true}) list"
key_files:
  created:
    - apps/admin-app/src/features/bookings/schemas.ts
    - apps/admin-app/src/features/bookings/keys.ts
    - apps/admin-app/src/features/bookings/api.ts
    - apps/admin-app/src/features/bookings/api.test.tsx
    - apps/admin-app/src/components/modals/BookingModal.tsx
    - apps/admin-app/src/components/modals/BookingModal.test.tsx
    - apps/admin-app/src/components/modals/BookingDetailModal.tsx
    - apps/admin-app/src/pages/schedule/components/BookingDetailLoader.tsx
    - apps/admin-app/src/pages/schedule/components/calendar-utils.test.ts
  modified:
    - apps/admin-app/src/pages/schedule/SchedulePage.tsx
    - apps/admin-app/src/pages/schedule/components/WeekCalendar.tsx
    - apps/admin-app/src/pages/schedule/components/EventBlock.tsx
    - apps/admin-app/src/pages/schedule/components/ScheduleToolbar.tsx
    - apps/admin-app/src/pages/schedule/components/SchedulePageHead.tsx
    - apps/admin-app/src/pages/schedule/components/calendar-utils.ts
    - apps/admin-app/src/pages/trainer/components/OverviewTab.tsx
    - apps/admin-app/src/components/icons/index.tsx
decisions:
  - "D-102-03-TRAINER-COLOR: Trainer colors assigned deterministically from fixed TRAINER_PALETTE by index position in useTrainers({active:true}) list. Backend TrainerData has no color field — UI owns the display palette."
  - "D-102-03-BOOKING-DETAIL-LOADER: BookingDetailLoader as thin wrapper fetches booking by id before opening BookingDetailModal, avoiding conditional hook violations (React rules). Shows a backdrop spinner while loading."
  - "D-102-03-SCHEDULE-DATA-DECOUPLED: WeekCalendar, ScheduleToolbar, SchedulePageHead all decoupled from mock ScheduleData; WeekCalendar now accepts (days, events: CalendarEvent[], nowLabel, trainerColorMap); SchedulePageHead uses ScheduleHeadData minimal interface."
  - "D-102-03-TIMEZONE-WEEK: Week bounds (fromTime/toTime) computed from ISO week (startOfISOWeek/endOfISOWeek from date-fns). Day headers built from local time; nowLabel from local time. Moscow clock displayed correctly since local time matches RU production."
  - "D-102-03-EMPTY-STATE: Two EmptyState variants for slots.length===0: owner (CalendarPlus + «Управление расписанием» CTA) vs reception (CalendarX + no CTA), gated by can(role,'create','schedule-slots')."
metrics:
  duration: "~90 minutes (context-resumed from prior session)"
  completed: "2026-06-13"
  tasks_completed: 3
  tasks_total: 3
  files_created: 9
  files_modified: 7
---

# Phase 102 Plan 03: Booking Lifecycle + Calendar Merge Summary

**One-liner:** Booking http layer (schemas/keys/queries/mutations), race-safe BookingModal + BookingDetailModal (cancel 24h-window + complete via pt-sessions), calendar merge (slots+bookings → CalendarEvent[] with type discriminator), slot-click routing, owner-only management FAB, OverviewTab today-schedule wired.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Bookings http layer (TDD) | `38e44b9d` | features/bookings/{schemas,keys,api,api.test}.ts |
| 2 | BookingModal + BookingDetailModal (TDD) | `96f47fe3` | modals/BookingModal{,.test}.tsx, modals/BookingDetailModal.tsx |
| 3 | Calendar merge + slot-click routing + OverviewTab | `9b4537f9` | SchedulePage.tsx, WeekCalendar.tsx, EventBlock.tsx, ScheduleToolbar.tsx, SchedulePageHead.tsx, calendar-utils.{ts,test.ts}, BookingDetailLoader.tsx, OverviewTab.tsx |

## What Was Built

### features/bookings/ (Task 1)

- `schemas.ts`: `BookingSchema` (id/slotId/clientId/ptPackageId/status/slot?/ptPackage?/clientFullName?), `BookingsListResponseSchema`, `BookingCreateSchema`, `CancelBookingSchema`, `CompletePtSessionSchema` ({ptPackageId,trainerId,performedAt,bookingId} — NO clientId per T-102-BK-COMPLETE)
- `keys.ts`: `bookingsKeys` factory (all/lists()/list(filter)/detail(id)/byWeek(params)/byTrainer(trainerId,range))
- `api.ts`: `useBookingsByWeek`, `useBookingsByTrainer`, `useBooking`, `useCreateBooking` (no onError toast for slot conflicts — caller inline), `useCancelBooking` (cancel_window_expired special-cased), `useCompleteBooking` (POST /api/v1/pt-sessions), `ApiError` re-exported (D-100-03-APIERROR-REEXPORT)
- `api.test.tsx`: 6 tests — T-102-BK-IDEM (fresh UUID per attempt), T-102-BK-RACE (slot_already_booked not toasted), T-102-BK-COMPLETE (no clientId in complete body)

### Modals (Task 2)

- `BookingModal.tsx`: Client search (debounced 300ms) + PT-package PlanCards; PT-package section hidden until client selected; primary disabled until both selected; `handleBook` catches ApiError: slot conflicts → inline Callout «Слот уже занят/недоступен» + `scheduleKeys.all` invalidate + modal stays open; suppress-close while pending
- `BookingModal.test.tsx`: 4 tests using document.body.textContent (Dialog portal workaround); tests PT-package visibility, primary disabled, mount without crash
- `BookingDetailModal.tsx`: StatRow detail view; footer per status+role (owner: Отмена+Завершить+Закрыть; reception >24h: Отмена+Закрыть; reception ≤24h: Закрыть only; terminal: Закрыть only); cancel opens ConfirmModal → useCancelBooking; complete → useCompleteBooking

### Calendar merge (Task 3)

- `calendar-utils.ts`: `CalendarEventType = 'available'|'booked'|'cancelled'|'time-off'`; `CalendarEvent extends SessionEvent` with type discriminator + slotId/bookingId/trainerId/trainerFullName/trainerColor; `mergeSlotBookings(slots, bookings, colorMap, nameMap, weekStart)` pure function; color pre-resolved at merge time
- `calendar-utils.test.ts`: 6 tests covering all discriminators (available/booked/cancelled/non-confirmed=available/multi-slot/outside-week-excluded)
- `EventBlock.tsx`: booked → «занято» badge; time-off → diagonal-stripe bg + «недоступно» label; time-off not clickable; existing live/cancelled treatments preserved
- `WeekCalendar.tsx`: accepts `(days, events: CalendarEvent[], nowLabel, trainerColorMap)` — decoupled from mock ScheduleData
- `ScheduleToolbar.tsx`: Зал + Тип filters removed; real Тренер from `useTrainers({active:true})`; week navigator prev/next/today wired; trainer legend from real data + trainerColorMap
- `SchedulePageHead.tsx`: decoupled to `ScheduleHeadData {rangeLabel, sessionsWeek, plannedToday}`
- `BookingDetailLoader.tsx`: thin wrapper that fetches booking by id (useBooking) then renders BookingDetailModal; shows backdrop spinner while loading
- `SchedulePage.tsx`: weekOffset state → fromTime/toTime ISO bounds; useTrainerSlots + useBookingsByWeek in parallel; trainerColorMap (fixed TRAINER_PALETTE indexed by position); mergeSlotBookings; slot-click routing (available→BookingModal, booked→BookingDetailLoader, else no-op); owner-only management FAB (can(role,'create','schedule-slots')); PageLoading/PageError/EmptyState data-states
- `OverviewTab.tsx`: `useBookingsByTrainer(trainerId, todayRange, 'confirmed')`; Skeleton loading; «Нет записей на сегодня» EmptyState; booking rows with client name/time/ptPackage label

## Verification

Gate: `pnpm -F @clubcore/admin-app typecheck && pnpm -F @clubcore/admin-app lint && pnpm -F @clubcore/admin-app test && pnpm -F @clubcore/admin-app build`

- Typecheck: PASSED (0 errors)
- Lint: PASSED (0 errors, 0 warnings)
- Tests: PASSED (257/257)
- Build: PASSED (2.56s)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed unused variable errors from initial implementation**
- **Found during:** Task 3 verification
- **Issue:** `trainerColor` (calendar-utils.ts), `isAvailable` (EventBlock.tsx), `addDays` (OverviewTab.tsx) declared but never read — noUnusedLocals/noUnusedParameters violation
- **Fix:** Removed `isAvailable` unused variable; moved `trainerColor` to populate `CalendarEvent.trainerColor` field (correct design — color pre-resolved at merge time); removed `addDays` import
- **Files modified:** calendar-utils.ts, EventBlock.tsx, OverviewTab.tsx
- **Commit:** `9b4537f9`

**2. [Rule 2 - Missing] Added CalendarEvent.trainerColor field populated at merge time**
- **Found during:** Task 3 implementation
- **Issue:** `trainerColorMap` parameter in `mergeSlotBookings` was unused (after removing the local variable). Correct design: store the resolved color in the CalendarEvent so WeekCalendar doesn't need a separate lookup for each event
- **Fix:** Added `trainerColor?: string` to `CalendarEvent` interface; populated it from `trainerColorMap.get(slot.trainerId)` in merge function; WeekCalendar uses `calEv.trainerColor` with fallback to map lookup
- **Files modified:** calendar-utils.ts, WeekCalendar.tsx
- **Commit:** `9b4537f9`

**3. [Rule 2 - Missing] SchedulePageHead decoupled from mock ScheduleData**
- **Found during:** Task 3 implementation
- **Issue:** SchedulePageHead imported full `ScheduleData` type (mock type from types.ts) but only used 3 fields. After SchedulePage no longer builds a full ScheduleData, the prop type would be incompatible.
- **Fix:** Introduced `ScheduleHeadData {rangeLabel, sessionsWeek, plannedToday}` minimal interface; SchedulePageHead accepts this instead of full ScheduleData
- **Files modified:** SchedulePageHead.tsx
- **Commit:** `9b4537f9`

**4. [Rule 1 - Bug] ClientData has firstName/lastName not fullName**
- **Found during:** Task 2 implementation (BookingModal)
- **Issue:** Plan spec assumed `client.fullName` but ClientData schema has `firstName`/`lastName` separate fields
- **Fix:** Added `clientFullName(c: {firstName, lastName})` helper function in BookingModal that joins them
- **Files modified:** BookingModal.tsx
- **Commit:** `96f47fe3`

**5. [Rule 1 - Bug] vi.mock with require() fails in ESM test environment**
- **Found during:** Task 2 TDD RED phase (BookingModal.test.tsx)
- **Issue:** `const { ApiError } = require('@/api/client')` inside vi.mock factory fails because require is not available in ESM
- **Fix:** Defined inline `FakeApiError` class inside the mock factory instead of importing from production code
- **Files modified:** BookingModal.test.tsx
- **Commit:** `96f47fe3`

**6. [Rule 2 - Missing] Added BookingDetailLoader for slot-click → BookingDetailModal routing**
- **Found during:** Task 3 implementation
- **Issue:** Plan specified opening BookingDetailModal on booked slot click, but BookingDetailModal needs `BookingData` (fetched by id). Fetching inside SchedulePage with conditional useBooking would violate React hooks rules.
- **Fix:** Created `BookingDetailLoader` thin component that always calls `useBooking(id)` and renders the modal when data arrives; shows a backdrop spinner while loading
- **Files created:** BookingDetailLoader.tsx
- **Commit:** `9b4537f9`

**7. [Rule 1 - Bug] react-hooks/exhaustive-deps lint warning on trainers `?? []`**
- **Found during:** Task 3 lint gate
- **Issue:** `const trainers = trainersQuery.data?.items ?? []` — the `?? []` creates a new array on every render, causing useMemo dependencies to see a changed reference on every render
- **Fix:** Wrapped `trainers` itself in useMemo with `[trainersQuery.data]` dependency
- **Files modified:** SchedulePage.tsx
- **Commit:** `9b4537f9`

## Known Stubs

None — all plan goals achieved. The OverviewTab Regulars section intentionally stays on mock data per `// TODO Phase 104` plan note.

## Threat Flags

No new security-relevant surface beyond the plan's threat model. The booking lifecycle endpoints (`/api/v1/bookings`, `/api/v1/pt-sessions`) were already in the plan's trust boundary table. All T-102-BK-* threats mitigated as designed.

## Self-Check: PASSED

Files created/modified exist:
- apps/admin-app/src/features/bookings/schemas.ts — FOUND
- apps/admin-app/src/features/bookings/keys.ts — FOUND
- apps/admin-app/src/features/bookings/api.ts — FOUND
- apps/admin-app/src/features/bookings/api.test.tsx — FOUND
- apps/admin-app/src/components/modals/BookingModal.tsx — FOUND
- apps/admin-app/src/components/modals/BookingModal.test.tsx — FOUND
- apps/admin-app/src/components/modals/BookingDetailModal.tsx — FOUND
- apps/admin-app/src/pages/schedule/components/BookingDetailLoader.tsx — FOUND
- apps/admin-app/src/pages/schedule/components/calendar-utils.test.ts — FOUND
- apps/admin-app/src/pages/schedule/SchedulePage.tsx — FOUND (modified)

Commits:
- 38e44b9d — Task 1 feat(102-03): bookings http layer — FOUND
- 96f47fe3 — Task 2 feat(102-03): BookingModal + BookingDetailModal — FOUND
- 9b4537f9 — Task 3 feat(102-03): calendar merge + slot-click routing — FOUND
