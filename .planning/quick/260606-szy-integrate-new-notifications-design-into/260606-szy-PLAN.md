---
quick_id: 260606-szy
slug: integrate-new-notifications-design-into
date: 2026-06-06
type: quick
---

# Quick Task 260606-szy: Integrate new Notifications design into the wired sheet

## Description

Take the ported design (`NotificationsScreen.jsx`, quick 260606-sqb) and **integrate** it as the
real notifications experience: remove the standalone device frame, use the app's shared colour
tokens, and wire it to the live API — replacing the contents of the bell-opened
`apps/client-pwa/src/screens/sheets/NotificationsSheet.jsx`.

User constraints: «интегрировать. рамка не нужна, цветовые токены использовать общие.»
Gesture decision (no delete / mark-unread endpoints exist): swipe + long-press + tap → **mark read**.

## Task

### Task 1: Integrate design into NotificationsSheet.jsx
- action:
  - Rewrite `NotificationsSheet.jsx` with the ported design (segmented Все/Новые, grouped
    Сегодня/Вчера/Ранее, cards, swipe + long-press, pull-to-refresh, toast, empty state).
  - Remove device frame (`.stage`/`.device`/`.island`/`.status-bar`/`.home-indicator`).
  - Remove the component's `:root`/`body.dark` token blocks → use the app's shared tokens; scope all
    CSS under `.notif-screen` so it never clobbers the app's global `.card`/`.seg`/`.press`/`.t-*`.
  - Wire real API via `@/data`: `useClientNotifications` (feed + unreadCount), `useMarkNotificationRead`,
    `useMarkAllNotificationsRead`. Group + relative time derived from `createdAt` (Europe/Moscow, Intl).
  - Map gestures to supported API: header «Прочитать» → mark-all; card tap → mark read; swipe-left →
    mark read (accent «Прочитать» action); long-press → «Отметить прочитанным». Drop delete/mark-unread.
  - Keep props `{ onClose }` (bell wiring in App.jsx unchanged). Remove superseded standalone
    `NotificationsScreen.jsx`. Update `NotificationsSheet.test.jsx` for the new UI.
- files: NotificationsSheet.jsx, NotificationsSheet.test.jsx, (removed) screens/NotificationsScreen.jsx
- verify: `pnpm tsc -b --noEmit` exit 0; `pnpm eslint src/screens/sheets/` exit 0; `pnpm vitest run NotificationsSheet.test.jsx` green; browser: bell opens new sheet, real data, mark-all clears badge + persists.
- done: integrated sheet live, gates green, browser-verified.

## Notes

- No backend delete/mark-unread endpoints — destructive/unread affordances intentionally dropped;
  swipe/long-press/tap all map to the persistent mark-read API. A real delete would be a separate
  backend follow-up (new endpoint + openapi/forward-guard regen).
