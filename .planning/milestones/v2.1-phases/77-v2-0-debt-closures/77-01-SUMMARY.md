---
phase: 77-v2-0-debt-closures
plan: "01"
subsystem: client-pwa
tags: [booking, cancel, mutation, testing, FIX-01]
dependency_graph:
  requires: []
  provides: [cancel-booking-wiring]
  affects: [BookingManageSheet, useCancelBooking]
tech_stack:
  added: []
  patterns: [mutateAsync-try/catch, isPending-loading-state, inline-error-banner, vi.importActual-selective-mock]
key_files:
  created:
    - apps/client-pwa/src/screens/sheets/BookingManageSheet.cancel.test.jsx
  modified:
    - apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx
decisions:
  - "D-77-01: useCancelBooking instantiated at component top; mutateAsync({ bookingId: b.id }) in cancel-confirm handler"
  - "D-77-02: confirm button disabled + 'Отмена…' label while isPending"
  - "D-77-03: catch branch sets cancelError; cancel_window_expired → window-expired copy; generic fallback otherwise; setView not called"
  - "D-77-04: setView('done-cancel') called only inside try after resolve; hook's onSettled bookings() invalidation handles list refresh"
  - "Error detection: ApiError.code === 'cancel_window_expired' (fetcher parses backend error body into code field; no status property needed)"
  - "Inline error positioned absolute bottom: 102px above the confirm button area, aria-live='polite', semantic var(--danger-soft)/var(--danger) tokens only"
metrics:
  duration: "~18 minutes"
  completed: "2026-06-02T19:16:18Z"
  tasks: 2
  files: 2
---

# Phase 77 Plan 01: Cancel-Booking Wiring Summary

**One-liner:** Cancel-confirm "Отменить запись" button in BookingManageSheet wired to useCancelBooking().mutateAsync with isPending loading, inline 409 error mapping, and transition-on-resolve (WARNING-1 / FIX-01 closed).

## What Was Built

### Task 1: Wire cancel-confirm button to useCancelBooking (commit: 4b530970)

Modified `apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx`:

- Added `useCancelBooking` to the `@/data` import
- Instantiated `cancelMutation = useCancelBooking()` and added `cancelError` state at component top
- Replaced the trivial `onClick={() => setView('done-cancel')}` cancel button with an async handler:
  - Clears prior `cancelError`, then `await cancelMutation.mutateAsync({ bookingId: b.id })`
  - On resolve: `setView('done-cancel')` (hook's `onSettled` invalidates `clientPortalKeys.bookings()`)
  - On catch: detects `err.code === 'cancel_window_expired'` → sets "Окно отмены истекло — обратитесь на ресепшн"; generic fallback "Не удалось отменить запись. Попробуйте ещё раз."
- Confirm button: `disabled={cancelMutation.isPending}`, label `{cancelMutation.isPending ? 'Отмена…' : 'Отменить запись'}`, `opacity: 0.7` while pending
- Inline error banner in cancel view: `position: absolute`, bottom 102px, `aria-live="polite"`, `aria-atomic="true"`, semantic tokens `var(--danger-soft)` / `var(--danger)` only (no raw palette)

### Task 2: Add Vitest coverage (commit: 119d7b2c)

Created `apps/client-pwa/src/screens/sheets/BookingManageSheet.cancel.test.jsx` (5 tests):

1. `mutateAsync` called with `{ bookingId: 'bk-123' }` from the `booking.id` prop
2. `isPending=true` → confirm button disabled + "Отмена…" label
3. `mutateAsync` resolves → done-cancel view renders "Запись отменена"
4. Generic rejection → stays on cancel-confirm + "Не удалось отменить запись. Попробуйте ещё раз."
5. `{ code: 'cancel_window_expired' }` rejection → "Окно отмены истекло — обратитесь на ресепшн"

Mock strategy: `vi.mock('@/data', async () => ({ ...await vi.importActual('@/data'), useCancelBooking: stub }))` — real `CALENDAR`, `TIME_SLOTS`, `BUSY_SLOTS`, `UPCOMING_BOOKING` preserved; only `useCancelBooking` stubbed.

## Verification

- `pnpm exec tsc -b` — exit 0 (no type errors)
- `pnpm lint` — exit 0 (no raw-palette / import-boundary violations)
- `pnpm exec vitest run src/screens/sheets/BookingManageSheet.cancel.test.jsx` — 5/5 passed
- `pnpm exec vitest run` — 82/82 passed (14 test files, 0 regressions)
- `pnpm build` — exit 0 (BookingManageSheet-CZ3Utnzh.js built at 13.70 kB)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — the cancel button now calls the real backend hook; no stubs introduced.

## Threat Flags

None — no new network endpoints, auth paths, or schema changes introduced. The cancel wiring uses the existing `useCancelBooking` hook targeting the already-shipped `POST /api/v1/client/booking/{id}/cancel` endpoint (IDOR-safe, session-scoped, T-77-01..SC reviewed).

## Self-Check: PASSED

- FOUND: apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx
- FOUND: apps/client-pwa/src/screens/sheets/BookingManageSheet.cancel.test.jsx
- FOUND: .planning/phases/77-v2-0-debt-closures/77-01-SUMMARY.md
- FOUND: commit 4b530970 (Task 1 — feat)
- FOUND: commit 119d7b2c (Task 2 — test)
