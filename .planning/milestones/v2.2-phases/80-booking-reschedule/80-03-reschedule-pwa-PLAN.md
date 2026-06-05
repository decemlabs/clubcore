---
phase: 80-booking-reschedule
plan: 03
type: execute
wave: 2
depends_on: ["80-01"]
files_modified:
  - apps/client-pwa/src/lib/clientQueries.ts
  - apps/client-pwa/src/data/index.js
  - apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx
  - apps/client-pwa/src/screens/sheets/BookingManageSheet.reschedule.test.jsx
autonomous: true
requirements: [RESCH-03]
must_haves:
  truths:
    - "BookingManageSheet reschedule view lists REAL available slots filtered to the booking's trainer (mock calendar removed)"
    - "Confirming a reschedule calls POST /client/booking/{id}/reschedule via useRescheduleBooking with an Idempotency-Key"
    - "Backend error codes (reschedule_window_expired / slot_already_booked / slot_trainer_mismatch) surface as user-facing copy"
    - "On success the view transitions to a done state and the bookings + availableSlots caches invalidate"
  artifacts:
    - path: "apps/client-pwa/src/lib/clientQueries.ts"
      provides: "useRescheduleBooking mutation hook"
      contains: "useRescheduleBooking"
    - path: "apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx"
      provides: "real-slot reschedule view wired to useRescheduleBooking; mock calendar imports removed"
      contains: "useRescheduleBooking"
    - path: "apps/client-pwa/src/screens/sheets/BookingManageSheet.reschedule.test.jsx"
      provides: "reschedule wiring vitest suite"
      contains: "useRescheduleBooking"
  key_links:
    - from: "apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx"
      to: "useRescheduleBooking (POST /client/booking/{id}/reschedule)"
      via: "mutateAsync({ bookingId, newSlotId, idempotencyKey })"
      pattern: "useRescheduleBooking"
    - from: "apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx"
      to: "useClientAvailableSlots (real slots)"
      via: "filtered to booking trainer_id"
      pattern: "useClientAvailableSlots"
---

<objective>
Wire the existing `BookingManageSheet` reschedule view to real data: add the `useRescheduleBooking`
mutation to `clientQueries.ts`, export it from `data/index.js`, replace the mock calendar
(`CALENDAR`/`TIME_SLOTS`/`BUSY_SLOTS`) with real `useClientAvailableSlots` data filtered to the
booking's trainer, call the new reschedule endpoint with an Idempotency-Key, surface backend error
codes as copy, and add a vitest wiring test.

Purpose: Delivers RESCH-03 — the client can now reschedule from the PWA against the real backend
endpoint (built in Plan 02). This plan depends only on the documented endpoint contract from Plan 01,
so it runs in Wave 2 parallel to Plan 02 (no shared files).

Output: useRescheduleBooking hook + real-slot reschedule view + vitest suite; mock calendar removed.
</objective>

<execution_context>
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/workflows/execute-plan.md
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/80-booking-reschedule/80-CONTEXT.md
@.planning/phases/80-booking-reschedule/80-PATTERNS.md

<interfaces>
<!-- Endpoint contract (from Plan 02, documented in PATTERNS.md) — the PWA targets this shape. -->
POST /api/v1/client/booking/{booking_id}/reschedule
  body: { new_slot_id: string }
  headers: { 'Idempotency-Key': <uuid> }
  200 → { data: BookingResponse }
  409 codes: reschedule_window_expired | slot_already_booked | slot_trainer_mismatch
  404: booking_not_found (IDOR)

Existing hooks (already in clientQueries.ts):
  useClientAvailableSlots(page=1) → useQuery of PaginatedResult<AvailableSlotItem> from GET /api/v1/client/slots
  useCancelBooking() → useMutation (template for shape + onSettled invalidation)
  useCreateBooking() → useMutation passing { slotId, idempotencyKey } with 'Idempotency-Key' header (template for the idempotency-key header)
  clientPortalKeys.bookings() / clientPortalKeys.availableSlots() → invalidation keys
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add useRescheduleBooking hook + data/index.js export</name>
  <files>apps/client-pwa/src/lib/clientQueries.ts, apps/client-pwa/src/data/index.js</files>
  <read_first>
    - apps/client-pwa/src/lib/clientQueries.ts — useCancelBooking (~lines 474-489), useCreateBooking (~lines 440-470, for the Idempotency-Key header pattern), clientPortalKeys (~lines 23-38), clientRequest + BookingResponse type
    - apps/client-pwa/src/data/index.js — the useCancelBooking re-export (~line 41) and the mock calendar re-export (~line 56)
  </read_first>
  <action>
    In clientQueries.ts add `export function useRescheduleBooking()` mirroring `useCancelBooking`'s
    structure: `useMutation` with `mutationFn` taking `{ bookingId, newSlotId, idempotencyKey }`
    (all `string`), calling `clientRequest('post', '/api/v1/client/booking/{booking_id}/reschedule',
    { params: { booking_id: bookingId }, body: { new_slot_id: newSlotId }, headers: { 'Idempotency-Key':
    idempotencyKey } })`, returning `(res as { data: BookingResponse }).data`. `onSettled` invalidates
    BOTH `clientPortalKeys.bookings()` and `clientPortalKeys.availableSlots()`. Add a JSDoc header noting
    RESCH-01 + Idempotency-Key (D-70-02) + IDOR 404-collapse. In data/index.js add `useRescheduleBooking`
    to the existing `useCancelBooking` re-export group.
  </action>
  <verify>
    <automated>cd apps/client-pwa && pnpm exec tsc --noEmit -p tsconfig.json && pnpm exec eslint src/lib/clientQueries.ts src/data/index.js</automated>
  </verify>
  <acceptance_criteria>
    - `useRescheduleBooking` exported from clientQueries.ts with `{ bookingId, newSlotId, idempotencyKey }` mutationFn args
    - onSettled invalidates both bookings() and availableSlots() keys
    - `useRescheduleBooking` re-exported from data/index.js
    - `tsc --noEmit` exits 0; eslint exits 0 on both files
  </acceptance_criteria>
  <done>Reschedule mutation hook available via @/data, typecheck + lint clean.</done>
</task>

<task type="auto">
  <name>Task 2: Wire BookingManageSheet reschedule view to real slots + endpoint; remove mock calendar</name>
  <files>apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx</files>
  <read_first>
    - apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx — line 6 imports (CALENDAR/TIME_SLOTS/BUSY_SLOTS + useCancelBooking + UPCOMING_BOOKING); cancel-flow wiring (~lines 13-14, 150-173); error-banner pattern (~lines 102-132); the reschedule view usages CALENDAR.find (~line 37), CALENDAR.slice(1).map (~line 207), TIME_SLOTS.filter (~line 237), BUSY_SLOTS[trainerKey] (~lines 183-184)
    - apps/client-pwa/src/data/index.js (the @/data barrel the sheet imports from)
  </read_first>
  <action>
    Update the line-6 import: drop `CALENDAR, TIME_SLOTS, BUSY_SLOTS`; add `useRescheduleBooking,
    useClientAvailableSlots`. (First grep that no OTHER consumer needs the mock re-export on
    data/index.js line 56; if none, leave line 56 as-is — the sheet just stops importing it.) Add
    `const rescheduleMutation = useRescheduleBooking()` and `const { data: slotsPage } =
    useClientAvailableSlots()`. Derive the candidate slots by filtering `slotsPage.items` to the
    booking's `trainer_id` and future start times; render the slot picker from this real list instead
    of `CALENDAR`/`TIME_SLOTS`, and drop the `BUSY_SLOTS` busy-marking (real slots are already
    availability-filtered server-side). In the reschedule confirm handler call
    `rescheduleMutation.mutateAsync({ bookingId: b.id, newSlotId: selectedSlot.slot_id, idempotencyKey:
    <generated uuid, same gen used by the cancel/create flow> })`; on success `setView('done-reschedule')`;
    on rejection read `err.code` and map: `reschedule_window_expired` → "Окно переноса истекло —
    обратитесь на ресепшн"; `slot_already_booked` → "Этот слот уже занят. Выберите другое время.";
    `slot_trainer_mismatch` → "Слот другого тренера — перенос только к тому же тренеру."; else generic
    "Не удалось перенести запись. Попробуйте ещё раз." into `rescheduleError`, surfaced via the existing
    error-banner pattern. Disable the confirm button while `rescheduleMutation.isPending`.
  </action>
  <verify>
    <automated>cd apps/client-pwa && pnpm exec tsc --noEmit -p tsconfig.json && pnpm exec eslint src/screens/sheets/BookingManageSheet.jsx</automated>
  </verify>
  <acceptance_criteria>
    - `CALENDAR`, `TIME_SLOTS`, `BUSY_SLOTS` no longer imported in BookingManageSheet.jsx (grep returns 0 matches in the file)
    - reschedule view renders slots from `useClientAvailableSlots` filtered to the booking's trainer
    - confirm handler calls `useRescheduleBooking().mutateAsync` with `{ bookingId, newSlotId, idempotencyKey }`
    - all three backend codes mapped to distinct user copy; button disabled while pending
    - `tsc --noEmit` + eslint exit 0
  </acceptance_criteria>
  <done>Reschedule view runs on real slots + real endpoint; mock calendar removed from the sheet.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Vitest reschedule wiring suite</name>
  <files>apps/client-pwa/src/screens/sheets/BookingManageSheet.reschedule.test.jsx</files>
  <read_first>
    - apps/client-pwa/src/screens/sheets/BookingManageSheet.cancel.test.jsx (full file — EXACT structural template: vi.mock('@/data'), idleMutation stub, beforeEach reset, describe blocks)
    - apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx (the wired component under test)
  </read_first>
  <behavior>
    - selecting a real slot + confirming calls useRescheduleBooking().mutateAsync with { bookingId, newSlotId }
    - while the mutation isPending the confirm button is disabled
    - on resolve the view transitions to done-reschedule
    - on reject with code 'reschedule_window_expired' the window-expired copy is shown and the view stays on reschedule
    - on reject with code 'slot_already_booked' the slot-taken copy is shown
    - on reject with code 'slot_trainer_mismatch' the cross-trainer copy is shown
    - the slot list rendered comes from the stubbed useClientAvailableSlots (mock CALENDAR not referenced)
  </behavior>
  <action>
    Create `BookingManageSheet.reschedule.test.jsx` mirroring `BookingManageSheet.cancel.test.jsx`:
    `vi.mock('@/data', ...)` stubbing `useRescheduleBooking` and `useClientAvailableSlots` (return a
    paginated page with two same-trainer slots), an `idleMutation = { mutateAsync:
    vi.fn().mockResolvedValue({}), isPending: false }`, `beforeEach` resetting + setting the return
    values. Add `describe`/`it` cases covering the behaviors above: mutateAsync called with
    `{ bookingId, newSlotId }`; pending disables the button; success → done-reschedule; each of the
    three error codes renders its specific copy and keeps the reschedule view. Use the project's
    standard render helper (same one cancel.test.jsx uses).
  </action>
  <verify>
    <automated>cd apps/client-pwa && pnpm exec vitest run src/screens/sheets/BookingManageSheet.reschedule.test.jsx</automated>
  </verify>
  <acceptance_criteria>
    - All cases pass; vitest run exits 0
    - test asserts mutateAsync called with `{ bookingId, newSlotId }` (idempotencyKey may be any string)
    - test asserts each of the three backend codes renders distinct copy and stays on the reschedule view
    - test asserts success transitions to done-reschedule
  </acceptance_criteria>
  <done>Reschedule wiring vitest suite green, mirroring the cancel-flow test structure.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| PWA → backend reschedule endpoint | client UI sends booking_id + new_slot_id; all authz enforced server-side (Plan 02) |
| PWA error display | backend error codes rendered as fixed copy; no raw error echoed to DOM |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-80-14 | Information Disclosure | reschedule error banner | mitigate | only fixed Russian copy rendered per known code; raw backend message never injected into DOM |
| T-80-15 | Tampering (replay) | reschedule mutation | mitigate | per-intent Idempotency-Key header generated client-side (mirrors useCreateBooking); server enforces replay protection |
| T-80-16 | Authorization (relies on server) | client-side trainer filter | accept | UI filters slots to the booking trainer for UX only; the authoritative slot_trainer_mismatch guard is server-side (Plan 02 T-80-08) — client filter is not a security control |
| T-80-SC | Tampering | npm/pnpm installs | mitigate | no new packages; block on slopcheck human checkpoint if any install appears |

No HIGH-severity unmitigated threat remains (authz is server-side; client is presentation only).
</threat_model>

<verification>
- `pnpm exec tsc --noEmit` exits 0
- `pnpm exec eslint` exits 0 on modified files
- `pnpm exec vitest run src/screens/sheets/BookingManageSheet.reschedule.test.jsx` exits 0
- ROADMAP success criterion 4 satisfied: BookingManageSheet shows real available slots and reschedules via the new endpoint; mock calendar removed
</verification>

<success_criteria>
RESCH-03 delivered: the PWA reschedule view consumes real available slots filtered to the booking's
trainer and performs the reschedule via the new endpoint with an Idempotency-Key; mock calendar
removed from the sheet; error codes surfaced as copy. ROADMAP success criterion 4 proven by vitest.
</success_criteria>

<output>
Create `.planning/phases/80-booking-reschedule/80-03-SUMMARY.md` when done.
</output>
