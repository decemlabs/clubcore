---
quick_id: 260606-toj
slug: pixel-perfect-verbatim-port-of-the-user-
date: 2026-06-06
type: quick
---

# Quick Task 260606-toj: Verbatim port of BookingScreen.jsx (Запись)

## Description

Port the user-provided `BookingScreen.jsx` (the «Запись» / individual-training booking
screen) into the project **byte-for-byte**, preserving the visual design, structure,
sizes, paddings, typography, colors, element states, animations and UX behavior with
**no changes** — pixel-perfect to the original.

Source: `/Users/andre/Workspace/Development/clubcore-client-pwa/src/screens/BookingScreen.jsx`
Target: `apps/client-pwa/src/screens/BookingScreen.jsx`

It is a self-contained component: own scoped CSS (`:root`/`body.dark` tokens, device
frame), mock data (trainers, calendar, time slots, busy reasons, durations, bios),
and all interactive logic — the `pick → confirm → done` flow, trainer-detail bottom
sheet, time-slot picker with busy tooltips/shake, duration toggle, toast, and the
delegated `data-go`/`data-toast` tab-bar navigation.

User constraints (verbatim): «максимально точно перенести экран, сохранив визуальный
дизайн, структуру, размеры, отступы, типографику, цвета, состояния элементов, анимации
и пользовательское поведение без каких-либо изменений. Итоговый интерфейс должен
выглядеть пиксель-в-пиксель как оригинал.»

This is the standalone-port step (mirrors quick 260606-sqb for NotificationsScreen).
Integration (remove frame, shared tokens, wire to real API) is a separate follow-up if
the user requests it — same two-step pattern as Notifications (sqb → szy).

## Task

### Task 1: Copy BookingScreen.jsx byte-for-byte into the project
- action:
  - Copy the source file verbatim to `apps/client-pwa/src/screens/BookingScreen.jsx`
    (no paraphrasing, no reformatting — a byte-identical copy guarantees pixel fidelity).
  - Do NOT wire it into `App.jsx` / routing yet (standalone, like the NotificationsScreen
    sqb port). Do NOT touch the existing wired `BookScreen.jsx`.
- files: apps/client-pwa/src/screens/BookingScreen.jsx (new)
- verify:
  - `shasum -a 256` of source and target match (byte-for-byte).
  - `pnpm tsc -b --noEmit` exit 0.
  - eslint: file is in the global `src/**/*.jsx` ignore (D-69-06 allowJs ramp) — not a
    D-71-09 placeholder, so no eslint-config change needed.
- done: BookingScreen.jsx present in the project, byte-identical to the original, gates green.

## Notes

- The port is self-contained — no `@/data` imports, so it does not trip the D-71-09
  placeholder import-boundary zone (which now lists only ChatScreen + ReferralSheet).
- `target: ES2022`, allowJs ramp — `.jsx` screens type-check via `tsc -b` but are not linted.
- Integration into the live app (device frame removed, shared `styles.css` tokens, real
  trainers/booking API) is intentionally OUT of scope for this verbatim port.
