---
quick_id: 260606-szy
slug: integrate-new-notifications-design-into
date: 2026-06-06
status: complete
---

# Summary — 260606-szy: Integrate new Notifications design into the wired sheet

**One-liner:** Rewrote the bell-opened `NotificationsSheet.jsx` with the user's notification design —
no device frame, shared colour tokens (scoped under `.notif-screen`), wired to the real
`useClientNotifications` / mark-read / mark-all API; gestures map to mark-read. Gates green + browser-verified.

## What was done

- **Design integrated** into `apps/client-pwa/src/screens/sheets/NotificationsSheet.jsx` (the component
  the Home bell opens via App.jsx SheetGate, props `{ onClose }` unchanged): segmented Все/Новые filter,
  grouped Сегодня/Вчера/Ранее, cards with kind icon/tone + unread dot, swipe + long-press gestures,
  pull-to-refresh, toast, empty state, entry/fade animations.
- **No frame:** removed the standalone device frame (`.stage`/`.device`/`.island`/`.status-bar`/`.home-indicator`)
  and the global `html,body` restyle — the sheet lives in the app shell.
- **Shared tokens:** removed the component's own `:root`/`body.dark` token blocks → consumes the app's
  `styles.css` tokens. All component CSS scoped under `.notif-screen` so it never clobbers the app's
  global `.card`/`.seg`/`.press`/`.scroller`/`.t-*` classes. Scoped keyframes (`nfx-*`) avoid name collisions.
- **Real data:** `useClientNotifications(1)` (items + unreadCount), `useMarkNotificationRead`,
  `useMarkAllNotificationsRead` via `@/data`. Group bucket + relative time derived from `createdAt`
  (Europe/Moscow, Intl-only — D-82-01 / D-86-03-INTL precedent). Kind→icon/tone map for the 7 INBOX-03 kinds.
- **Gestures → mark-read** (no delete/mark-unread API): header «Прочитать» → mark-all (disabled at 0 unread);
  card tap → mark read; swipe-left → mark read (accent «Прочитать» action, optimistic, snaps back — no removal);
  long-press → «Отметить прочитанным». Optimistic read state with onError rollback; pull-to-refresh → real refetch.
- Removed the superseded standalone `apps/client-pwa/src/screens/NotificationsScreen.jsx` (git history keeps it).
- Updated `NotificationsSheet.test.jsx` for the new UI (header «Прочитать» via role, Все/Новые filter,
  empty «Всё прочитано», error copy, mark-all optimistic + rollback).

## Key files

key-files:
  modified:
    - apps/client-pwa/src/screens/sheets/NotificationsSheet.jsx — integrated design (scoped, shared tokens, real API)
    - apps/client-pwa/src/screens/sheets/NotificationsSheet.test.jsx — updated for new UI (9 tests)
  removed:
    - apps/client-pwa/src/screens/NotificationsScreen.jsx — superseded standalone mockup

## Verification

- `pnpm tsc -b --noEmit`: PASS.
- `pnpm eslint src/screens/sheets/`: exit 0.
- `pnpm vitest run src/screens/sheets/NotificationsSheet.test.jsx`: 9/9 pass.
- **Browser (client-pwa :5175, dev client, SW cleared):** bell «· 2 непрочитанных» opens the new sheet —
  «Все · 3 / Новые · 2», groups «Сегодня · 2 · 2 нов.» + «Вчера · 1», MSK times (19:49/16:51/19:51),
  2 unread dots. DOM-verified: no `.device` frame; `.notif-screen` scope; unread card bg = `--surface`
  (#fff), dot = `--accent` (#2dd4a4) — shared tokens resolved; swipe action label «Прочитать».
  Mark-all («Прочитать») → dots→0, button auto-disabled, **DB persisted unread=0**.

## Not done (out of scope — no backend)

- Real notification **delete** and **mark-unread** — no API endpoints; gestures map to mark-read instead.
  A true delete/unread needs a backend follow-up (DELETE /client/notifications/{id} + mark-unread, then
  openapi/schema.d.ts regen + `_v2xChecks` forward-guard).
- Pagination "load more": design has no load-more; page 1 only (feed shows newest 20 + «Конец списка»).
- Screenshot capture flaked (devtools protocol timeout under entry animations); verified via a11y snapshot
  + DOM assertions instead.

## Self-Check: PASSED
