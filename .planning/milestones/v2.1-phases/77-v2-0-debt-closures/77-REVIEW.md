---
phase: 77-v2-0-debt-closures
reviewed: 2026-06-02T22:25:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx
  - apps/client-pwa/src/screens/sheets/BookingManageSheet.cancel.test.jsx
  - apps/client-pwa/src/routes/PaymentReturnScreen.jsx
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
---

# Phase 77: Code Review Report

**Reviewed:** 2026-06-02T22:25:00Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

FIX-01 correctly wires the cancel-confirm button to `useCancelBooking().mutateAsync({ bookingId })`
with proper try/catch sequencing: `done-cancel` is reached only on resolve, the button is
disabled while `isPending`, and the error mapping reads `err.code` (which matches the `ApiError.code`
contract surfaced by `clientFetcher.ts` → `parseErrorBody`). The 409 `cancel_window_expired` code
matches the canonical backend code (`schema.d.ts:599`, milestone v1.5 BOOK-06). FIX-02 to
`PaymentReturnScreen.jsx` is genuinely a one-line comment addition — no behavioral, JSX, or logic change (verified against diff).

However, the wiring is functionally inert in production: the only caller (`App.jsx:306`) never
passes a `booking` prop, so `bookingId` always resolves to the hardcoded mock id `'b-next'`. The
real cancel mutation will always hit the backend's IDOR 404-collapse and never cancel a real
booking. The test suite passes a fixture booking, which masks this gap rather than catching it.
Several test assertions are also weaker than they appear.

## Critical Issues

### CR-01: Production caller never passes a `booking` prop — cancel always targets the mock id `'b-next'`

**File:** `apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx:16,154` (defect at call site `apps/client-pwa/src/App.jsx:306-312`)
**Issue:**
The component computes the cancel target as `const b = booking || UPCOMING_BOOKING;` (line 16) and
then calls `cancelMutation.mutateAsync({ bookingId: b.id })` (line 154). The sole production caller
in `App.jsx` renders the sheet with no `booking` prop:

```jsx
<BookingManageSheet
  onClose={() => ui.setManageOpen(false)}
  onCancelled={...}
  ... /* no `booking={...}` */
/>
```

`ui.manageOpen` is a plain boolean (`UIContext.jsx:13`); no booking object is ever threaded into
the sheet from any setter. Therefore `b` always falls back to the mock `UPCOMING_BOOKING`, whose
`id` is the hardcoded string `'b-next'` (`data/booking.js:21`). The real `useCancelBooking` mutation
will always POST `/api/v1/client/booking/b-next/cancel`, which the backend collapses to a
404 `booking_not_found` (IDOR anti-oracle, T-71-28). The user can never actually cancel their real
booking through this UI — every attempt shows the generic error fallback. FIX-01 wired the mutation
but the data that makes it correct (the real booking id) is not supplied.

**Fix:** Thread the real booking (from `useClientBookings()` / home state) through to the sheet so
`b.id` is a real UUID. Either pass it from the caller:

```jsx
// App.jsx — derive the upcoming booking from the wired hook and pass it down
<BookingManageSheet
  booking={upcomingBooking}   // real booking object with server id
  onClose={() => ui.setManageOpen(false)}
  ...
/>
```

or have the sheet itself read the real booking from `useClientBookings()` instead of falling back
to the mock. Until a real id reaches `mutateAsync`, the cancel flow cannot succeed against the
backend. Add a guard so the confirm button is disabled / errors clearly when `b.id` is the mock
sentinel rather than silently POSTing a non-existent id.

## Warnings

### WR-01: Cancel test masks CR-01 by injecting a fixture id the production caller never provides

**File:** `apps/client-pwa/src/screens/sheets/BookingManageSheet.cancel.test.jsx:28-51,92`
**Issue:**
`baseProps` always passes `booking: TEST_BOOKING` with `id: 'bk-123'`, and the test asserts
`mutateAsync` was called with `{ bookingId: 'bk-123' }`. This proves arg-passing in isolation but
gives false confidence: the production caller (`App.jsx`) passes no booking, so the assertion can
never fail for the bug that actually ships (CR-01). The test that "proves" the integration works is
the one hiding the integration gap.
**Fix:** Add a test that renders the sheet exactly as the app does (no `booking` prop) and asserts
the cancel button is disabled / does not POST the mock id, or — preferably after fixing CR-01 — add
an integration-level test covering the real `App.jsx` wiring so the missing prop is caught.

### WR-02: `done-cancel` refund copy is computed from the mock booking, can show a wrong/misleading refund

**File:** `apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx:17-19,29-31`
**Issue:**
`freeCancel`, `refundPct`, and `refundAmount` are derived from `b.hoursTo` / `b.price`. With CR-01
unresolved, `b` is always the mock (`hoursTo: 9`, `price: 2200`), so the success screen unconditionally
claims "Деньги вернутся… в течение 1–3 рабочих дней" (100%) regardless of the real booking's actual
cancel window or price. Even after CR-01 is fixed, the refund amount/percentage shown is computed
client-side from the display prop, not from the server's authoritative cancel response — the server
may apply a different refund (e.g. 50% penalty inside the window). This risks telling the user the
wrong refund figure (a trust/financial-messaging issue).
**Fix:** Drive the refund copy from the server response returned by `mutateAsync` (`BookingResponse`)
rather than re-deriving it from the local display prop. If the response lacks refund detail, soften
the copy to avoid asserting a specific amount/percentage.

### WR-03: No guard against the brief double-submit window before `isPending` propagates

**File:** `apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx:149-164`
**Issue:**
The button is disabled via `cancelMutation.isPending`, but `isPending` only becomes `true` after the
mutation hook re-renders the component. The onClick calls `mutateAsync` directly; between the click
and the re-render a fast second tap could fire `mutateAsync` twice. The endpoint is idempotency-keyed
server-side (D-38-14), but `useCancelBooking` (`clientQueries.ts:464-479`) does NOT set an
`Idempotency-Key` header for the cancel call (unlike `useCreateBooking` at line 449), so the
double-submit protection the architecture assumes is absent for cancel.
**Fix:** Either add a synchronous local in-flight guard (`if (submitting) return;` set before the
await), or add an `Idempotency-Key` header to the cancel `clientRequest` in `useCancelBooking` to
match `useCreateBooking` and make a duplicate POST a safe no-op.

## Info

### IN-01: `@/data` re-exports `BUSY_SLOTS`/`CALENDAR`/`TIME_SLOTS` that its own header comment says were removed

**File:** `apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx:6` (re-export `apps/client-pwa/src/data/index.js:11,56`)
**Issue:**
`data/index.js:11` documents these mock constants as "REMOVED in Plan 06", yet line 56 still
re-exports them and `BookingManageSheet.jsx:6` still imports all three for the reschedule UI. The
comment and the code disagree, which is misleading for the next reader (and the reschedule view at
line 180+ is still entirely mock-driven, in contrast to the now-wired cancel path).
**Fix:** Reconcile the comment with reality (the reschedule UI is still on mocks), or finish wiring
reschedule and drop the mock exports.

### IN-02: Pending-state test does not wrap the click in `act` and asserts only the disabled+label state

**File:** `apps/client-pwa/src/screens/sheets/BookingManageSheet.cancel.test.jsx:95-105`
**Issue:**
The `isPending=true` test clicks the overview row with a bare `fireEvent.click` (no `act`), unlike
the other tests. It passes today because `isPending` is forced `true` from initial render so no
async state settles, but it is stylistically inconsistent and could emit `act` warnings if the
view-transition logic changes. It also does not assert that `mutateAsync` is NOT called while
disabled (the disabled attribute is verified, but not the no-op behavior).
**Fix:** Wrap the click in `act` for consistency, and optionally assert `mutateAsync` was not invoked.

---

_Reviewed: 2026-06-02T22:25:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
