---
phase: 102-schedule-trainers
fixed_at: 2026-06-13T18:22:00Z
review_path: .planning/phases/102-schedule-trainers/102-REVIEW.md
iteration: 1
findings_in_scope: 8
fixed: 8
skipped: 0
status: all_fixed
---

# Phase 102: Code Review Fix Report

**Fixed at:** 2026-06-13T18:22:00Z
**Source review:** `.planning/phases/102-schedule-trainers/102-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 8 (CR-01, CR-02, WR-01, WR-02, WR-03, WR-04, IN-01, IN-03)
- Fixed: 8
- Skipped: 0

All four gate checks pass after fixes: `typecheck` ✓, `lint` ✓, `test` (275/275) ✓, `build` ✓.
The executor had 274 tests passing; fixes added 1 new test case (net +1).

---

## Fixed Issues

### CR-01: Operator-precedence bug in `mergeSlotBookings`

**Files modified:** `apps/admin-app/src/pages/schedule/components/calendar-utils.ts`, `apps/admin-app/src/pages/schedule/components/calendar-utils.test.ts`
**Commit:** `68b6fabb`
**Applied fix:** Changed `booking ?? slot.status === 'booked'` to `booking != null || slot.status === 'booked'`. The old expression was parsed as `booking ?? (slot.status === 'booked')` due to JS operator precedence — `===` (precedence 10) binds tighter than `??` (precedence 4), producing a boolean that was then used as the `??` fallback. The fix uses explicit boolean OR. The click handler in `SchedulePage` (`ev.type === 'booked' && ev.bookingId`) and the render guard (`{selectedBookingId && ...}`) already prevent `bookingId=undefined` from reaching `BookingDetailLoader` — no additional change needed there. Added one new test case covering the `slot.status='booked'` + no-confirmed-booking path (CR-01 table row 3).

---

### CR-02 + IN-01: Double toast on time-off creation / dead if/else branch

**Files modified:** `apps/admin-app/src/features/schedule/api.ts`, `apps/admin-app/src/components/modals/ScheduleManagementModal.tsx`
**Commit:** `9199d2e4`
**Applied fix (CR-02):** Removed the inline `toast.success('Период заблокирован')` from `TimeOffTab.handleSubmit` in `ScheduleManagementModal.tsx`. The hook's `onSuccess` now owns the normal-path toast. For the force path: `onSuccess` skips its toast when `vars.force === true` so the modal's descriptive toast (`Период заблокирован` + `Отменено бронирований: N` description) in `handleForce` remains the sole notification. Result: exactly one toast per submit path.
**Applied fix (IN-01):** Collapsed the dead identical `if (vars.force) { ... } else { ... }` branches in `useCreateTimeOff.onSuccess` into a single conditional: toast only when `!vars.force`.

---

### WR-01: `TrainerHero` edit button unguarded for reception

**Files modified:** `apps/admin-app/src/pages/trainer/components/TrainerHero.tsx`, `apps/admin-app/src/pages/trainer/TrainerPage.tsx`
**Commit:** `4e793601`
**Applied fix:** Added `role: Role` prop to `TrainerHero`. In `TrainerPage`, imported `useSession` from `@/features/auth/api`, derived `role = sessionQuery.data?.role ?? 'reception'`, and threaded it as `<TrainerHero trainer={trainer} role={role} />`. In `TrainerHero`, imported `can` from `@/shared/session/can` and `Role` type, then wrapped the Редактировать button in `{can(role, 'edit', 'trainers') && ...}`. Reception users no longer see the edit button.

---

### WR-02: Side effect called during render in `BookingDetailLoader`

**Files modified:** `apps/admin-app/src/pages/schedule/components/BookingDetailLoader.tsx`
**Commit:** `ad586331`
**Applied fix:** Added `import { useEffect } from 'react'`. Moved the `onOpenChange(false)` call out of the render body into a `useEffect` that triggers when `!isPending && (isError || !booking)`. The render body on the error path now just returns `null` (the effect handles closing). This eliminates the "Cannot update a component while rendering a different component" React strict-mode warning.

---

### WR-03: PayoutsTab Lock flash during session load

**Files modified:** `apps/admin-app/src/pages/trainer/components/PayoutsTab.tsx`
**Commit:** `d93580ab`
**Applied fix:** Added a `session.isPending` guard at the top of `PayoutsTab` that returns `null` while the session query is loading. The `role` derivation and `can()` gate now only execute once `session.isPending` is false. Owner users no longer see the Lock EmptyState for the ~50–200 ms session-fetch window.

---

### WR-04: Inconsistent semicolons across Phase 102 files

**Files modified:** 23 Phase 102 source and test files (features/schedule, features/bookings, features/trainers, pages/schedule, pages/trainer, components/modals — see commit for full list)
**Commit:** `b02cb1df`
**Applied fix:** Read `.prettierrc` (`semi: true`, `singleQuote: true`, `trailingComma: all`, `printWidth: 100`). Ran `npx prettier --write` over all 23 Phase 102 files that were missing semicolons. The payroll domain files (already had semicolons) were left unchanged. All 23 files now conform to the `semi: true` config. `lint` re-confirmed clean after formatting.

---

### IN-03: Remove `as unknown` cast on `trainersQuery.data` in `ScheduleManagementModal`

**Files modified:** `apps/admin-app/src/components/modals/ScheduleManagementModal.tsx`
**Commit:** `89e10bff`
**Applied fix:** Replaced the triple-cast expression:
```typescript
(trainersQuery.data as unknown as { items?: ... } | undefined)?.items ?? []
```
with the direct type-safe access:
```typescript
trainersQuery.data?.items ?? []
```
Phase 102-02 is complete and `useTrainers()` returns `{ items: TrainerData[]; total; page; pageSize }` as typed by `TrainersListResponseSchema`. The `D-102-01-TRAINERSHAPE` comment was updated to note the guard is resolved. TypeScript typecheck confirmed no errors after this change.

---

## Skipped Issues

None — all 8 in-scope findings were fixed.

---

_Fixed: 2026-06-13T18:22:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
