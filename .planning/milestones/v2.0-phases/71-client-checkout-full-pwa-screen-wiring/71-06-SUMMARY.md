---
phase: 71-client-checkout-full-pwa-screen-wiring
plan: "06"
subsystem: ui
tags: [react-query, pwa, booking, qr, qrcode-react, client-portal, phase-70]

# Dependency graph
requires:
  - phase: 71-04
    provides: clientPortalKeys factory, clientRequest transport, data/index.js swap seam
  - phase: 70-client-bookings-qr-self-check-in
    provides: GET /client/bookings, GET /client/slots, POST /client/booking, POST /client/booking/{id}/cancel, GET /client/qr-token

provides:
  - useClientBookings: GET /api/v1/client/bookings (Phase-70 CBOOK-01)
  - useClientAvailableSlots: GET /api/v1/client/slots (Phase-70 CBOOK-02)
  - useCreateBooking: POST /api/v1/client/booking with Idempotency-Key (CBOOK-03, T-71-27)
  - useCancelBooking: POST /api/v1/client/booking/{id}/cancel (CBOOK-05)
  - useClientQrToken: GET /api/v1/client/qr-token; staleTime:0, refetchInterval:50s (CCHK-01, T-71-26)
  - BookScreen wired to real available slots; booking create/cancel; no_active_pt_package redirect
  - QRSheet renders real signed JWT as scannable QRCodeSVG (qrcode.react v4.2.0)
  - All 6 PWA-05 screens now on real backend (Home/Profile/Plans/Checkout from Plan 05 + Book/QR here)

affects:
  - Phase 72 (E2E verification of booking flow + QR self check-in)

# Tech tracking
tech-stack:
  added:
    - "qrcode.react ^4.2.0 added to apps/client-pwa (scannable QR rendering)"
  patterns:
    - "Slot-derived calendar: dates, trainers, and time periods built dynamically from ClientAvailableSlotItem API response"
    - "no_active_pt_package 422 redirect: caught by ApiError.code check in BookScreen confirm handler; routes to Plans via onOpenPlans() prop"
    - "QR token refresh: refetchInterval:50_000ms to refresh before ~60s TTL; loading/error guard when fetch fails"
    - "TweaksRoot TRAINERS + BookingManageSheet calendar mocks retained as dev/legacy constants; BookScreen wired exclusively to real hooks"

key-files:
  created: []
  modified:
    - apps/client-pwa/src/lib/clientQueries.ts
    - apps/client-pwa/src/data/index.js
    - apps/client-pwa/src/screens/BookScreen.jsx
    - apps/client-pwa/src/screens/sheets/QRSheet.jsx
    - apps/client-pwa/src/App.jsx
    - apps/client-pwa/package.json
    - pnpm-lock.yaml

key-decisions:
  - "qrcode.react installed for real QR rendering — the existing QRPattern component is explicitly decorative (pseudo-random SVG), not a scannable QR encoder; gym scanner requires real encoded data"
  - "CALENDAR/TIME_SLOTS/BUSY_SLOTS retained in data/index.js for BookingManageSheet.jsx (reschedule UI uses mock calendar); not in Plan 06 files_modified scope"
  - "TRAINERS retained in data/index.js for TweaksRoot.jsx dev-panel trainer-detail tweak button"
  - "ApiError re-exported through data/index.js swap seam so BookScreen can do instanceof ApiError.code checks without importing from lib directly"
  - "onOpenPlans prop added to BookScreen + BookRoute in App.jsx to route no_active_pt_package errors to Plans sheet"

requirements-completed: [PWA-05]

# Metrics
duration: 7min
completed: "2026-05-30"
---

# Phase 71 Plan 06: Book/QR Screen Wiring Summary

**Phase-70 client booking + QR-token endpoints wired to BookScreen (real slots, idempotent create/cancel, no_active_pt_package redirect) and QRSheet (scannable QRCodeSVG from real signed JWT, 50s auto-refresh); qrcode.react installed; all 6 PWA-05 screens now on the real backend.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-30T16:00:34Z
- **Completed:** 2026-05-30T16:08:01Z
- **Tasks:** 2 (Task 1: hooks + seam; Task 2: screen wiring)
- **Files modified:** 7

## Accomplishments

- Added 5 Book/QR hooks to `clientQueries.ts`: `useClientBookings`, `useClientAvailableSlots`, `useCreateBooking` (Idempotency-Key per-intent), `useCancelBooking`, `useClientQrToken` (staleTime:0, refetchInterval:50s)
- Wired BookScreen to real available slots; calendar days/trainers/time periods derived from `ClientAvailableSlotItem` API response; 422 `no_active_pt_package` routes to Plans sheet (T-71-29 mitigation)
- Wired QRSheet to `useClientQrToken`; renders `QRCodeSVG` from real signed JWT token; loading/error guards; idle→scanning→success chrome retained
- Installed `qrcode.react v4.2.0` — the existing `QRPattern` is decorative-only, not a real QR encoder
- BookingManageSheet/HistorySheets still build (CALENDAR/TIME_SLOTS/BUSY_SLOTS retained for their legacy consumers)

## Task Commits

1. **Task 1: Add Book/QR hooks to clientQueries.ts + re-export via data/index.js** - `06aa4731` (feat)
2. **Task 2: Wire BookScreen + QRSheet to real backend; install qrcode.react** - `cc85a300` (feat)

## Files Created/Modified

- `apps/client-pwa/src/lib/clientQueries.ts` — 5 new hooks; `availableSlots` + `qrToken` keys added to clientPortalKeys
- `apps/client-pwa/src/data/index.js` — re-exports Book/QR hooks + ApiError; CALENDAR/TIME_SLOTS/BUSY_SLOTS retained for legacy consumers
- `apps/client-pwa/src/screens/BookScreen.jsx` — wired to real slots; slot-derived calendar; loading/error states; no_active_pt_package redirect; onOpenPlans prop
- `apps/client-pwa/src/screens/sheets/QRSheet.jsx` — real QRCodeSVG from token; staleTime:0 + 50s refresh; loading/error guard; animation chrome retained
- `apps/client-pwa/src/App.jsx` — BookRoute passes `onOpenPlans={() => ui.setPlansOpen(true)}`
- `apps/client-pwa/package.json` — added qrcode.react ^4.2.0
- `pnpm-lock.yaml` — lockfile updated

## Decisions Made

- `qrcode.react` installed — the existing `QRPattern` component is a deterministic pseudo-random SVG (decorative), not a real QR encoder. A gym scanner must read the actual JWT, so a proper QR library is required.
- CALENDAR/TIME_SLOTS/BUSY_SLOTS and TRAINERS retained in data/index.js: these are still consumed by `BookingManageSheet.jsx` (reschedule calendar) and `TweaksRoot.jsx` (dev panel). They are not BookScreen's concern now that it's wired to real slots.
- `ApiError` added to data/index.js exports: BookScreen needs it for `code` comparison on the no_active_pt_package 422 branch without bypassing the swap seam.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] TweaksRoot.jsx imports TRAINERS from @/data — removed in initial data/index.js clean**
- **Found during:** Task 1 (first build after removing TRAINERS from data/index.js)
- **Issue:** Build failed: `"TRAINERS" is not exported by "src/data/index.js"` — TweaksRoot.jsx dev panel uses `TRAINERS[0]` for the trainer-detail tweak button
- **Fix:** Retained `export { TRAINERS }` in data/index.js with comment
- **Files modified:** apps/client-pwa/src/data/index.js
- **Committed in:** 06aa4731 (Task 1 commit)

**2. [Rule 1 - Bug] BookingManageSheet.jsx imports CALENDAR/TIME_SLOTS/BUSY_SLOTS from @/data — removed in Task 2 clean**
- **Found during:** Task 2 (build after removing calendar mocks from data/index.js)
- **Issue:** Build failed: `"CALENDAR" is not exported by "src/data/index.js"` — BookingManageSheet uses the mock calendar for its reschedule UI
- **Fix:** Retained `export { CALENDAR, TIME_SLOTS, BUSY_SLOTS }` with comment noting BookingManageSheet dependency
- **Files modified:** apps/client-pwa/src/data/index.js
- **Committed in:** cc85a300 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs — build dependency breaks)
**Impact on plan:** Both fixes necessary to maintain build integrity. No scope creep — both retained mock constants are explicitly for non-BookScreen consumers (BookingManageSheet reschedule, TweaksRoot dev panel).

## Known Stubs

None — all wired screens use real backend hooks. BookingManageSheet retains mock calendar but it was outside this plan's scope.

## Threat Flags

No new threat surfaces beyond the plan's threat model:
- T-71-26 (QR token replay): staleTime:0 + 50s refetch ensures displayed QR rotates before 60s TTL; anti-replay enforced server-side
- T-71-27 (double-book): useCreateBooking sends per-intent crypto.randomUUID() Idempotency-Key; server UNIQUE arbiter returns 409 on race
- T-71-28 (cross-client IDOR): cancel endpoint is IDOR-safe server-side; PWA sends only bookingId
- T-71-29 (booking without PT-package): 422 no_active_pt_package caught; user routed to Plans/Checkout

## Self-Check

Files exist:
- `/Users/andre/Workspace/Development/clubcore/apps/client-pwa/src/lib/clientQueries.ts` ✓ (contains `useClientBookings`, `useClientQrToken`)
- `/Users/andre/Workspace/Development/clubcore/apps/client-pwa/src/data/index.js` ✓ (re-exports all 5 new hooks)
- `/Users/andre/Workspace/Development/clubcore/apps/client-pwa/src/screens/BookScreen.jsx` ✓ (contains `useClientAvailableSlots`, no CALENDAR import)
- `/Users/andre/Workspace/Development/clubcore/apps/client-pwa/src/screens/sheets/QRSheet.jsx` ✓ (contains `QRCodeSVG`, `useClientQrToken`)

Commits exist:
- `06aa4731` ✓ feat(71-06): add Book/QR hooks to clientQueries.ts
- `cc85a300` ✓ feat(71-06): wire BookScreen + QRSheet

Build/lint/typecheck: all pass ✓

## Self-Check: PASSED

## Issues Encountered

None beyond the 2 auto-fixed build dependency breaks (retained mock constants for non-BookScreen consumers).

## User Setup Required

None - no external service configuration required for this plan.

## Next Phase Readiness

- All 6 PWA-05 screens are now on the real backend (Home/Profile/Plans/Checkout from Plan 05 + Book/QR here)
- Phase 72 (OpenAPI handoff + CI + E2E) can proceed: client-portal tag freeze, _v20Checks guards, live E2E runbook
- QR flow ready for live scanner testing in Phase 72 E2E

---
*Phase: 71-client-checkout-full-pwa-screen-wiring*
*Completed: 2026-05-30*
