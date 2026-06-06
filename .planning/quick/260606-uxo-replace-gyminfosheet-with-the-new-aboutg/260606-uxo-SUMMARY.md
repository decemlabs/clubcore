---
quick_id: 260606-uxo
slug: replace-gyminfosheet-with-the-new-aboutg
date: 2026-06-06
status: complete
---

# Summary — 260606-uxo: Replace GymInfoSheet with the new «О зале» design (hybrid)

**One-liner:** Rewrote the wired `GymInfoSheet.jsx` with the user's «О зале» (AboutGymScreen)
design — no device frame, shared tokens, bespoke CSS scoped under `.aboutgym` — wired to the
real `GET /client/gym` (name/tagline/address/metro/hours/amenities/rules/contacts/social +
live open-closed status), with live occupancy + «Сегодня в зале» staff kept as decor. Gates
green, browser-verified.

## What was done

- **`GymInfoSheet.jsx` rewritten** keeping the export name `GymInfoSheet` and the `{ onClose }`
  contract (App.jsx SheetGate untouched). Still an absolute-inset sheet (`zIndex 220`) with
  `<StatusBar/>` + `<PullToRefresh>` (refetch); appbar back button → `onClose`.
- **Real data** via `useClientGymInfo()`: name, tagline, address, city, metro, phone, email,
  hours, amenities, rules, social. **Live open/closed + today index** derived from hours +
  Europe/Moscow clock (`getMoscowNow`). Hours subtitle: «Сейчас открыто · до HH:MM» /
  «Закрыто · сегодня HH:MM–HH:MM». Amenities (2-col tiles), rules accordion, contacts
  (tel/mailto), social (t.me/instagram, rel=noopener) — all real.
- **Working actions:** Маршрут → Yandex Maps (`city, address`), Позвонить → `tel:`,
  Адрес → clipboard copy (with «Скопировано» + banner feedback).
- **Decor (kept, fabricated — per user "оставить как декор"):** live-occupancy widget
  (count-up to 23 / 45% bar + pulse), «Сегодня в зале» staff block (admin «Маша» / trainers 4
  / classes 6 — static info rows), decorative SVG map (pin/route/«5 мин пешком»/floating chips).
- **CSS:** injected the mockup's bespoke classes scoped under `.aboutgym` (map, qa, sec, occ-*,
  live-pulse, reveal/amen/mchip/route-time) with keyframes renamed `ag-*` so nothing clobbers
  globals; reused global `.card`/`.press`/`.fade-up`/`.t-*`. Dropped the design's
  `:root`/`body.dark`/`html,body`/device/`.status-bar`/`.screen` rules. Used the app `Icon`
  (has every needed name) instead of the mockup's inline `Ico`. Removed the mockup's
  `localStorage` theme effect (app manages dark mode).
- Rewrote `GymInfoSheet.test.jsx` for the new structure (8 tests).

## Key files

key-files:
  modified:
    - apps/client-pwa/src/screens/sheets/GymInfoSheet.jsx — new «О зале» design, real /client/gym + decor
    - apps/client-pwa/src/screens/sheets/GymInfoSheet.test.jsx — rewritten for the new UI (8 tests)

## Verification

- `pnpm tsc -b --noEmit`: PASS (exit 0).
- `pnpm eslint src/screens/sheets/GymInfoSheet.jsx GymInfoSheet.test.jsx`: exit 0 (global `.jsx`
  ignore, D-69-06; GymInfoSheet graduated from D-71-09 zone in Phase 86 — no eslint-config change).
- `pnpm vitest run`: **180/180 pass** (incl. 8 GymInfoSheet tests; no regressions).
- **Browser (client-pwa :5175, dev client, SW/caches cleared):** Home → «Мой зал» opens the new
  sheet — decorative map (Тверская, 18 label, pin, route, «5 мин пешком»); tagline «КРУГЛОСУТОЧНЫЙ
  КЛУБ В ЦЕНТРЕ», name «Мой зал · Тверская», address+metro; Маршрут/Позвонить/Адрес; decor
  occupancy «23 / 45%»; «Часы работы · Закрыто · сегодня 09:00–22:00» (real hours, live MSK
  status); amenities Парковка/Wi-Fi/Душ/Сауна (real); «Сегодня в зале» staff (decor).
  Screenshots: `12-gyminfo-new.png` (map), `13-gyminfo-content.png` (content).

## Not done (out of scope — per user "decor" decisions)

- No backend for live occupancy or staff-on-shift — these stay fabricated. A real version needs
  occupancy + shift endpoints. The map is a stylised illustration (no real tiles/geo distance).

## Self-Check: PASSED
