---
quick_id: 260606-uxo
slug: replace-gyminfosheet-with-the-new-aboutg
date: 2026-06-06
type: quick
---

# Quick Task 260606-uxo: Replace GymInfoSheet with the new «О зале» design (hybrid)

## Description

Put the user-provided `AboutGymScreen.jsx` («О зале») design **in place of** the wired
`GymInfoSheet.jsx` (Phase 86, `GET /client/gym`, opened from Home/Profile via
`onOpenGymInfo` → SheetGate with `onClose`). Same hybrid approach as BookScreen (u22).

**User decisions (this session):**
- Replace GymInfoSheet directly (no standalone verbatim port step).
- Live occupancy («23 чел / 45%») + «Сегодня в зале» staff (admin/trainers/classes) →
  **decor** (no API). Map illustration + Маршрут/Позвонить/Адрес buttons stay (working).

## Task

### Task 1: Rewrite GymInfoSheet.jsx with the AboutGymScreen design, wired to real data
- action:
  - Rewrite `apps/client-pwa/src/screens/sheets/GymInfoSheet.jsx` keeping the export name
    `GymInfoSheet` and the `{ onClose }` contract (App.jsx SheetGate untouched).
  - **Visual:** reproduce the mockup (appbar back → onClose, decorative SVG map + pin +
    route + «5 мин пешком» + address label, quick-action tiles, live-occupancy card, hours
    accordion, amenities grid, «Сегодня в зале» staff card, contacts, rules accordion).
    No device frame / fake status bar / home indicator. Render as the existing sheet
    (`position:absolute; inset:0; zIndex:220`) + `<StatusBar/>` + `<PullToRefresh>`.
  - **CSS:** inject the mockup's bespoke classes scoped under `.aboutgym` (map, qa, sec,
    occ-*, live-pulse, reveal/amen/mchip/route-time, keyframes renamed `ag-*`) so they never
    clobber globals; reuse global `.card`/`.press`/`.fade-up`/`.t-*`. Drop `:root`/`body.dark`/
    device/`html,body`/`.status-bar`/`.screen` rules. Use the app `Icon` (has every needed
    name) instead of the mockup's inline `Ico`.
  - **Real data** via `useClientGymInfo()`: name, tagline, address, city, metro, phone, email,
    hours, amenities, rules, social. Live **open/closed + today index** derived from hours +
    Europe/Moscow clock (reuse getMoscowNow). Quick actions: Маршрут → Yandex Maps
    (city+address), Позвонить → `tel:`, Адрес → clipboard copy. Contacts/social → real
    `tel:`/`mailto:`/`t.me`/`instagram` (rel=noopener). Loading → skeleton; error → error card;
    PullToRefresh → refetch.
  - **Decor (kept, fabricated):** live-occupancy widget (count-up to 23 / 45% bar) and the
    «Сегодня в зале» staff block (admin «Маша» / trainers 4 / classes 6) — static info,
    no navigation. Map SVG + «5 мин пешком» decorative.
  - Update/keep `GymInfoSheet.test.jsx` for the new structure.
- files: GymInfoSheet.jsx (rewrite), GymInfoSheet.test.jsx (update)
- verify: `pnpm tsc -b --noEmit` exit 0; `pnpm eslint src/screens/sheets/` exit 0; vitest green;
  browser: gym-info sheet opens with new design, real name/hours/amenities/rules/contacts,
  working Маршрут/Позвонить/Адрес, decor occupancy/staff, close works.
- done: new «О зале» design live in place of GymInfoSheet, real data wired, gates green, browser-verified.

## Notes

- `.jsx` files are in the global eslint ignore (D-69-06 allowJs ramp); GymInfoSheet graduated
  out of the D-71-09 placeholder zone in Phase 86 — no eslint-config change needed.
- Occupancy/staff numbers are intentionally fake per the user's "оставить как декор" choice.
