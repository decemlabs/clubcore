---
quick_id: 260606-toj
slug: pixel-perfect-verbatim-port-of-the-user-
date: 2026-06-06
status: complete
---

# Summary — 260606-toj: Verbatim port of BookingScreen.jsx (Запись)

**One-liner:** Copied the user's «Запись» booking screen into the project **byte-for-byte**
(`apps/client-pwa/src/screens/BookingScreen.jsx`) — pixel-perfect, no changes. Standalone
self-contained component (own CSS/device frame/mock data + pick→confirm→done flow). Gates green.

## What was done

- **Byte-for-byte copy** of the source `BookingScreen.jsx` into
  `apps/client-pwa/src/screens/BookingScreen.jsx`. Verified identical via SHA-256:
  `f877762b313781881649887be3daf40e4c03c7210f762b1087dc2dea1fcb5476` (source == target).
- The component is self-contained and untouched: scoped `:root`/`body.dark` token CSS,
  iPhone device frame, mock data (6 trainers, 21-day calendar, 10 time slots, busy
  reasons, 3 durations, bios), and the full interactive flow:
  - `pick → confirm → done` step machine.
  - Trainer list with search + filter chips (Все / ★ Топ / До 2200 ₽) and empty state.
  - Trainer-detail bottom sheet (bio, rating/exp/price chips, nearest free windows).
  - Time-slot picker grouped by Утро/День/Вечер with busy-slot shake + reason tooltip,
    fully-booked day card with "nearest window" jump, duration toggle + live price.
  - Floating CTA booking summary, toast, delegated `data-go`/`data-toast` tab-bar nav.
- **Not wired** into `App.jsx`/routing (standalone, mirrors the NotificationsScreen sqb
  port). The existing wired `BookScreen.jsx` was left untouched.

## Key files

key-files:
  added:
    - apps/client-pwa/src/screens/BookingScreen.jsx — verbatim port (byte-identical to source)

## Verification

- `shasum -a 256` source vs target: **identical** (byte-for-byte).
- `pnpm tsc -b --noEmit`: **PASS** (exit 0).
- eslint: file matches the global `src/**/*.jsx` ignore (D-69-06 allowJs ramp); it is not a
  D-71-09 placeholder screen, so no eslint-config change was needed. `eslint` exit 0 (ignored).
- No existing files modified → no regression surface; the new file is not imported anywhere yet.

## Not done (out of scope — verbatim port only)

- **Integration** into the live app: removing the device frame, switching to the shared
  `styles.css` design tokens, and wiring real trainers/availability/booking APIs — same
  two-step pattern as Notifications (sqb verbatim → szy integrate). Awaiting user go-ahead.
- Tests: none added — a verbatim, unwired mockup has no app-facing behavior to assert yet
  (tests come with integration, as they did for NotificationsSheet).

## Self-Check: PASSED
