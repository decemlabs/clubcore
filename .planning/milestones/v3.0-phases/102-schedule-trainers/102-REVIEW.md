---
phase: 102-schedule-trainers
reviewed: 2026-06-13T10:30:00Z
depth: standard
files_reviewed: 40
files_reviewed_list:
  - apps/admin-app/src/features/schedule/api.ts
  - apps/admin-app/src/features/schedule/schemas.ts
  - apps/admin-app/src/features/schedule/keys.ts
  - apps/admin-app/src/features/schedule/schemas.test.ts
  - apps/admin-app/src/features/schedule/api.test.tsx
  - apps/admin-app/src/features/bookings/api.ts
  - apps/admin-app/src/features/bookings/schemas.ts
  - apps/admin-app/src/features/bookings/keys.ts
  - apps/admin-app/src/features/bookings/api.test.tsx
  - apps/admin-app/src/features/trainers/api.ts
  - apps/admin-app/src/features/trainers/schemas.ts
  - apps/admin-app/src/features/trainers/keys.ts
  - apps/admin-app/src/features/trainers/api.test.ts
  - apps/admin-app/src/features/payroll/api.ts
  - apps/admin-app/src/features/payroll/schemas.ts
  - apps/admin-app/src/features/payroll/keys.ts
  - apps/admin-app/src/features/payroll/api.test.tsx
  - apps/admin-app/src/components/modals/ScheduleManagementModal.tsx
  - apps/admin-app/src/components/modals/ScheduleManagementModal.test.tsx
  - apps/admin-app/src/components/modals/BookingModal.tsx
  - apps/admin-app/src/components/modals/BookingModal.test.tsx
  - apps/admin-app/src/components/modals/BookModal.reset.test.tsx
  - apps/admin-app/src/components/modals/BookingDetailModal.tsx
  - apps/admin-app/src/components/modals/TrainerFormModal.tsx
  - apps/admin-app/src/components/modals/ModalsProvider.tsx
  - apps/admin-app/src/pages/schedule/SchedulePage.tsx
  - apps/admin-app/src/pages/schedule/components/WeekCalendar.tsx
  - apps/admin-app/src/pages/schedule/components/EventBlock.tsx
  - apps/admin-app/src/pages/schedule/components/calendar-utils.ts
  - apps/admin-app/src/pages/schedule/components/calendar-utils.test.ts
  - apps/admin-app/src/pages/schedule/components/BookingDetailLoader.tsx
  - apps/admin-app/src/pages/schedule/components/ScheduleToolbar.tsx
  - apps/admin-app/src/pages/schedule/components/SchedulePageHead.tsx
  - apps/admin-app/src/pages/trainers/TrainersPage.tsx
  - apps/admin-app/src/pages/trainers/components/RosterCard.tsx
  - apps/admin-app/src/pages/trainers/components/columns.tsx
  - apps/admin-app/src/pages/trainer/TrainerPage.tsx
  - apps/admin-app/src/pages/trainer/components/OverviewTab.tsx
  - apps/admin-app/src/pages/trainer/components/PayoutsTab.tsx
  - apps/admin-app/src/pages/trainer/components/PayoutsTab.test.tsx
  - apps/admin-app/src/pages/trainer/components/TrainerHero.tsx
  - apps/admin-app/src/pages/trainer/components/TrainerKpis.tsx
  - apps/admin-app/src/components/icons/index.tsx
findings:
  critical: 2
  warning: 4
  info: 3
  total: 9
status: issues_found
---

# Phase 102: Code Review Report

**Reviewed:** 2026-06-13T10:30:00Z
**Depth:** standard
**Files Reviewed:** 40
**Status:** issues_found

## Summary

Phase 102 wires the Schedule + Trainers pages to real API endpoints. The idempotency-key
placement, race-safe booking (409 inline handling), force-override flow, payroll RBAC
(reception gate BEFORE hooks via sub-component split), and pt-sessions body shape are all
correctly implemented. The critical-path security items from the focus areas pass review.

Two bugs are confirmed: a JavaScript operator precedence error in the calendar merge
discriminator that causes slots whose bookings were cancelled/completed/no_show to render
as `type='booked'` instead of `type='available'`; and a double-toast when a time-off block
is successfully created via the normal (non-force) path. Four warnings cover an unguarded
edit button on TrainerHero (reception sees the button), a React side-effect called during
render in BookingDetailLoader, a session-loading flash on the PayoutsTab lock screen, and
an inconsistent semicolon style in the payroll domain files.

---

## Critical Issues

### CR-01: Operator-precedence bug in `mergeSlotBookings` — `type='booked'` mis-assigned for slots with non-confirmed bookings

**File:** `apps/admin-app/src/pages/schedule/components/calendar-utils.ts:91`

**Issue:** The discriminator expression `booking ?? slot.status === 'booked'` is parsed by
JavaScript as `booking ?? (slot.status === 'booked')` — not as the intended
`(booking != null) || (slot.status === 'booked')`. Operator precedence: `??` (nullish
coalescing, precedence 4) has lower precedence than `===` (equality, precedence 10), so
`slot.status === 'booked'` is evaluated first, yielding a boolean, and then `??` picks it
as the right-hand fallback when `booking` is `undefined`.

Consequence for each slot:

| `booking` | `slot.status` | Current result | Correct result |
|---|---|---|---|
| `undefined` | `'active'` | `undefined ?? false` → `false` → `available` ✅ | `available` |
| `{…}` | `'active'` | `{…} ?? false` → `{…}` (truthy) → `booked` ✅ | `booked` |
| `undefined` | `'booked'` | `undefined ?? true` → `true` → **`booked`** ❌ | `available` |

The third case is the bug: when a slot carries `status='booked'` on the wire (backend
marks it booked) but the corresponding booking is not `confirmed` (it is `cancelled`,
`completed`, or `no_show` — all of which are excluded from `confirmedBySlot` at line 63),
the slot is rendered as `type='booked'`. Clicking it opens `BookingDetailLoader` which
then calls `useBooking(undefined)` — `bookingId` is `undefined` because `booking?.id` is
`undefined` — causing `enabled: !!id` to be `false`, leaving the loader spinning forever
with no way to dismiss it (the `isError` / `!booking` close path never fires because
`isPending` stays truthy).

Additionally, the test suite does not cover this case: the test "marks a slot with a
non-confirmed booking as type=available" uses `slot.status = 'active'` (not `'booked'`),
so the operator-precedence path is never exercised.

**Fix:**
```typescript
// calendar-utils.ts line 91 — use explicit boolean logic
} else if (booking != null || slot.status === 'booked') {
  type = 'booked';
} else {
  type = 'available';
}
```

Add a test case for `slot.status='booked'` with no confirmed booking:
```typescript
it('marks a booked-status slot with no confirmed booking as type=available', () => {
  const slotBooked: TrainerSlotData = {
    ...SLOT_MON,
    id: 'slot-booked-status',
    status: 'booked', // backend reports booked status
  };
  // No confirmed booking in the bookings array
  const events = mergeSlotBookings(
    [slotBooked],
    [], // booking was cancelled, so it is not in the array
    trainerColorMap,
    trainerNameMap,
    WEEK_START,
  );
  expect(events[0]!.type).toBe('available');
});
```

---

### CR-02: Double toast when creating a time-off block on the normal (non-force) path

**File:** `apps/admin-app/src/components/modals/ScheduleManagementModal.tsx:375–376` and
`apps/admin-app/src/features/schedule/api.ts:234–238`

**Issue:** When `TimeOffTab.handleSubmit` succeeds, it calls `toast.success('Период
заблокирован')` directly at line 376 **and** the `useCreateTimeOff` hook's `onSuccess`
callback also fires `toast.success('Период заблокирован')` at line 235 of `api.ts`. Two
identical toasts appear to the user on every successful normal time-off creation.

The force path (`handleForce`) does not double-toast because it calls its own
`toast.success('Период заблокирован', { description: … })` (line 394) and the hook's
`onSuccess` fires the plain `'Период заблокирован'` toast — so the force path actually
emits two different toasts, one with a description and one without.

**Fix — option A (recommended):** Remove the inline `toast.success` from `TimeOffTab`
and let the hook own the toast. The hook already toasts on both the normal and force
paths:
```typescript
// ScheduleManagementModal.tsx — TimeOffTab.handleSubmit, remove line 376
try {
  await createTimeOff.mutateAsync({ body: buildBody() })
  // toast moved to hook onSuccess
  onSuccess()
} catch (err) { … }
```

**Fix — option B:** Remove the `onSuccess` toast from the hook and keep toasts in the
modal layer. The hook must also differentiate force vs. normal copy, which the vars object
already supports.

---

## Warnings

### WR-01: `TrainerHero` edit button shown to reception role with no `can()` gate

**File:** `apps/admin-app/src/pages/trainer/components/TrainerHero.tsx:103`

**Issue:** The "Редактировать" button calls `setEditOpen(true)` which opens
`TrainerFormModal` (wired to `PATCH /api/v1/trainers/{id}`). There is no `can(role,
'edit', 'trainers')` check on the button. Reception users who navigate to the trainer
detail page (which is accessible to both roles) see the edit button and can open the form.
The `useUpdateTrainer` hook has no `enabled` gate; submission will reach the server and
receive a 403. The server enforces RBAC but the UI presents an action the user cannot
complete, which is a UX violation.

The `TrainerHero` component receives a `trainer: TrainerData` prop but no `role` prop —
role is not threaded down from `TrainerPage`.

**Fix:**
```typescript
// TrainerPage.tsx: pass role to TrainerHero
<TrainerHero trainer={trainer} role={role} />

// TrainerHero.tsx: add role prop and gate the button
export function TrainerHero({ trainer: t, role }: { trainer: TrainerData; role: Role }) {
  // ...
  {can(role, 'edit', 'trainers') && (
    <Button className={HERO_BTN} onClick={() => setEditOpen(true)}>
      <SquarePen className="size-[14px]" />
      <span className="max-sm:hidden">Редактировать</span>
    </Button>
  )}
}
```

---

### WR-02: Side effect called during render in `BookingDetailLoader`

**File:** `apps/admin-app/src/pages/schedule/components/BookingDetailLoader.tsx:39`

**Issue:** `onOpenChange(false)` is called directly in the render body when `isError ||
!booking`:

```typescript
if (isError || !booking) {
  onOpenChange(false);   // ← state setter called during render
  return null;
}
```

Calling a parent state setter (`setSelectedBookingId(null)` in `SchedulePage`) during a
child's render violates React's rules: state updates during render cause React to
re-render the parent synchronously during the current render cycle, which can trigger
cascading updates and warnings in strict mode. React 18 defers such updates but logs a
console error ("Cannot update a component (`SchedulePage`) while rendering a different
component (`BookingDetailLoader`)").

**Fix:** Use a `useEffect` to perform the close after render:
```typescript
import { useEffect } from 'react';

export function BookingDetailLoader({ bookingId, role, open, onOpenChange }: Props) {
  const { data: booking, isPending, isError } = useBooking(bookingId);

  useEffect(() => {
    if (!isPending && (isError || !booking)) {
      onOpenChange(false);
    }
  }, [isPending, isError, booking, onOpenChange]);

  if (isPending) { /* spinner */ }
  if (isError || !booking) return null;

  return <BookingDetailModal … />;
}
```

---

### WR-03: PayoutsTab shows Lock EmptyState to owner during session loading (false positive flash)

**File:** `apps/admin-app/src/pages/trainer/components/PayoutsTab.tsx:57–68`

**Issue:** `useSession()` is an async TanStack Query call to `GET /api/v1/auth/me`. While
it is pending, `session.data` is `undefined` and `role` defaults to `'reception'` (line
57). The RBAC gate at line 60 then evaluates `!can('reception', 'view', 'payroll')` →
`true` → renders the Lock EmptyState. An owner who navigates directly to the "Выплаты"
tab will see "Недостаточно прав" for the duration of the session fetch (typically
50–200ms) before the lock disappears and the correct content loads. The T-102-PAY-RBAC
test mocks `useSession` with a resolved value and does not observe this loading window.

Note: this is a UX flash, not a security bypass — the lock resolves correctly once the
session loads.

**Fix:** Guard the gate with session loading state:
```typescript
export function PayoutsTab({ trainerId }: PayoutsTabProps) {
  const session = useSession();

  // While session is loading, show nothing (TrainerPage is already behind PageLoading
  // for the trainer data, so this window is narrow — but avoid a false lock flash).
  if (session.isPending) return null;

  const role = session.data?.role ?? 'reception';

  if (!can(role, 'view', 'payroll')) {
    return (
      <EmptyState
        icon={Lock}
        title="Недостаточно прав"
        message="Раздел выплат доступен только владельцу."
      />
    );
  }

  return <OwnerPayoutsTab trainerId={trainerId} role={role} />;
}
```

---

### WR-04: Inconsistent semicolon style — payroll domain files diverge from project convention

**Files:**
- `apps/admin-app/src/features/payroll/api.ts` (all statements terminated with `;`)
- `apps/admin-app/src/features/payroll/schemas.ts` (all statements terminated with `;`)
- `apps/admin-app/src/features/payroll/keys.ts` (all statements terminated with `;`)
- `apps/admin-app/src/pages/trainer/components/PayoutsTab.tsx` (all statements terminated with `;`)
- `apps/admin-app/src/pages/trainer/components/PayoutsTab.test.tsx` (all statements terminated with `;`)

**Issue:** The project `.prettierrc` specifies `"semi": true`. However, all
**other Phase 102 files** — `features/schedule/api.ts`, `features/bookings/api.ts`,
`features/trainers/api.ts`, `features/schedule/schemas.ts`, `features/bookings/schemas.ts`,
`features/trainers/schemas.ts`, pages, modals — omit statement-terminating semicolons
everywhere (only inline type annotations contain semicolons). This creates a systematic
inconsistency across the 102 deliverables.

Prettier with `semi: true` should format all files with semicolons. Running
`pnpm -F @clubcore/admin-app lint --fix` or `prettier --write` on the non-payroll files
would add them. Alternatively, if the project intends `semi: false` (the CLAUDE.md
top-level stack section says "No semicolons (ASI relied on)"), the `.prettierrc` should
be reconciled.

**Fix:** Run `pnpm -F @clubcore/admin-app lint --fix` to auto-format. If the project
canonical style is `semi: false`, update `.prettierrc` accordingly and reformat payroll
files to match. The critical requirement is that all files agree.

---

## Info

### IN-01: `useCreateTimeOff.onSuccess` duplicate toast branch — dead `if/else` with identical copy

**File:** `apps/admin-app/src/features/schedule/api.ts:232–238`

**Issue:** The `onSuccess` handler contains an `if (vars.force)` branch where both
branches emit identical copy:
```typescript
onSuccess: (_data, vars) => {
  if (vars.force) {
    toast.success('Период заблокирован')   // same copy
  } else {
    toast.success('Период заблокирован')   // same copy
  }
```
The `if/else` is entirely dead — the two branches are identical. This was presumably
scaffolded for different copy on force vs. normal paths but was never differentiated.
Combined with CR-02 (the double-toast), this should be simplified.

**Fix:**
```typescript
onSuccess: () => {
  toast.success('Период заблокирован');
  void qc.invalidateQueries({ queryKey: scheduleKeys.all });
},
```

---

### IN-02: `TrainerHero` imports `useNavigate` from `react-router-dom` (not TanStack Router)

**File:** `apps/admin-app/src/pages/trainer/components/TrainerHero.tsx:9`

**Issue:** `import { Link, useNavigate } from 'react-router-dom'` — the app uses
`react-router-dom` v6 (declared in `package.json`) rather than `@tanstack/react-router`,
so this import is technically correct for this codebase. However, other Phase 102 pages
(`SchedulePage`, `TrainersPage`) import nothing from `react-router-dom` and use
TanStack Router's typed navigation primitives instead. The `useNavigate` call on line 99
navigates to `ROUTES.messages` — this works because `react-router-dom` is present — but
it bypasses TanStack Router's typed search params and route context.

**Fix:** No immediate action required; this is a pre-existing architecture choice.
Note for future cleanup: align `TrainerHero` navigation to whichever router the app
standardises on.

---

### IN-03: `ScheduleManagementModal` reads trainer data with a runtime `as unknown` cast to work around a pre-102-02 shape mismatch

**File:** `apps/admin-app/src/components/modals/ScheduleManagementModal.tsx:534–537`

**Issue:**
```typescript
const trainers: { id: string; fullName: string }[] =
  (
    (trainersQuery.data as unknown as { items?: { id: string; fullName: string }[] } | undefined)
      ?.items
  ) ?? []
```
The comment (D-102-01-TRAINERSHAPE) says this was a guard for the pre-102-02 shape.
Since Phase 102-02 is now complete and `useTrainers()` returns `{ items: TrainerData[] }`
directly as typed by `TrainersListResponseSchema`, the cast is no longer necessary.
`trainersQuery.data` has type `{ items: TrainerData[]; total: number; page: number;
pageSize: number }` — accessing `.items` directly is type-safe without the cast.

**Fix:**
```typescript
const trainers: { id: string; fullName: string }[] =
  trainersQuery.data?.items ?? [];
```

---

_Reviewed: 2026-06-13T10:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
