---
phase: 87-notification-inbox
plan: "04"
subsystem: client-pwa
tags: [notifications, inbox, eslint-graduation, swap-seam, vitest, bell-badge]
dependency_graph:
  requires: ["87-02"]
  provides: ["INBOX-05"]
  affects: [client-pwa-notifications-sheet, client-pwa-home-bell]
tech_stack:
  added: []
  patterns:
    - useQuery paginated accumulation (page state + dedup-by-id)
    - optimistic mutation with rollback (mark-all readAt)
    - mark-on-open debounced fire-and-forget (800ms)
    - local in-sheet toast (no global Sonner in PWA — mirror ProfileExtraSheets)
    - feature flag kill-switch anchor (NOTIFICATIONS_FEATURE_FLAGS)
key_files:
  created:
    - apps/client-pwa/src/screens/sheets/NotificationsSheet.test.jsx
  modified:
    - apps/client-pwa/eslint.config.js
    - apps/client-pwa/src/data/index.js
    - apps/client-pwa/src/lib/clientQueries.ts
    - packages/api-client/src/schema.d.ts
    - apps/client-pwa/src/screens/sheets/NotificationsSheet.jsx
    - apps/client-pwa/src/screens/HomeScreen.jsx
decisions:
  - "Local in-sheet toast used instead of sonner (sonner not installed in client-pwa)"
  - "Schema.d.ts manually updated with notification paths/operations (endpoints not yet in auto-generated schema)"
  - "Intl-only formatRelativeTime per D-82-01 precedent (no date-fns)"
metrics:
  duration: "~25 minutes"
  completed: "2026-06-06T08:39:40Z"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 7
  files_created: 1
---

# Phase 87 Plan 04: NotificationsSheet PWA Wiring Summary

**One-liner:** Graduate NotificationsSheet from ComingSoon placeholder to real paginated inbox via useClientNotifications hook, with bell badge, mark-all/mark-single optimistic updates, and D-71-09 ESLint de-list.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | ESLint de-list + clientQueries hooks + @/data swap-seam | dfcc5aaf | eslint.config.js, clientQueries.ts, data/index.js, schema.d.ts |
| 2 | NotificationsSheet rewrite + Home bell badge + vitest | 73f9e37e | NotificationsSheet.jsx, HomeScreen.jsx, NotificationsSheet.test.jsx |

## Verification

- `grep -c "NotificationsSheet" apps/client-pwa/eslint.config.js` → **0** (de-list confirmed)
- `pnpm eslint src/screens/sheets/` → **exit 0**
- `pnpm eslint src/screens/` → **exit 0**
- `pnpm tsc -b --noEmit` → **clean** (no errors)
- `pnpm vitest run src/screens/sheets/NotificationsSheet.test.jsx` → **9/9 tests pass**

## D-71-09 De-list (3 spots)

All three NotificationsSheet entries removed from `apps/client-pwa/eslint.config.js`:
1. Negated ignore exception (`!src/screens/sheets/NotificationsSheet.jsx`) — REMOVED
2. D-71-09 files array entry — REMOVED
3. `no-restricted-paths` zone target — REMOVED

Comment updated to document Phase 87 graduation (mirrors GymInfoSheet Phase 86 pattern).

## Feature Flag

```js
const NOTIFICATIONS_FEATURE_FLAGS = {
  notificationsInbox: true, // INBOX-05 (Phase 87): wired to GET /client/notifications
}
```

Set to `true` from day one (ships complete). Kill-switch pattern consistent with `PROFILE_FEATURE_FLAGS.clubBonuses` and `CHECKOUT_FEATURE_FLAGS.clubBonuses`.

## Schema.d.ts Update

Added notification paths and operations to `packages/api-client/src/schema.d.ts`:
- `"/api/v1/client/notifications"` → `client_list_notifications`
- `"/api/v1/client/notifications/{notification_id}/read"` → `client_mark_notification_read`
- `"/api/v1/client/notifications/read-all"` → `client_mark_all_notifications_read`

Required because the auto-generated schema had not been regenerated with the Phase 87 backend routes.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] sonner not installed in client-pwa**
- **Found during:** Task 2 vitest run
- **Issue:** `import { toast } from 'sonner'` failed — sonner is installed in admin-web, NOT client-pwa. Client-pwa uses local in-sheet toast state (confirmed by grep of ProfileExtraSheets.jsx, SettingsScreen.jsx).
- **Fix:** Replaced `sonner` import with local `[toastMsg, setToastMsg]` state + `showToast()` helper, matching the ProfileExtraSheets pattern exactly. In-sheet error toast rendered absolutely positioned at bottom of sheet.
- **Files modified:** `NotificationsSheet.jsx` (toast import removed, local state added)
- **Commit:** 73f9e37e

**2. [Rule 2 - Missing critical functionality] Schema paths for notification endpoints**
- **Found during:** Task 1 tsc check
- **Issue:** `clientRequest()` is typed against `keyof paths` from `@clubcore/api-client/src/schema.d.ts`. Notification endpoints were not in the schema, causing TS2345 errors.
- **Fix:** Added paths (`/api/v1/client/notifications`, `/{notification_id}/read`, `/read-all`) and corresponding operations to schema.d.ts. Used same structure as loyalty/gym paths.
- **Files modified:** `packages/api-client/src/schema.d.ts`
- **Commit:** dfcc5aaf

## Deferred Items

- Live browser verification of the sheet (open → GET loads data, mark-all calls PATCH, bell dot reflects unreadCount) — auto-deferred per operator-pending-verify-autodefer memory (live YooKassa/operator-cred human-verify items auto-defer during autonomous runs).

## Known Stubs

None. All data is wired to real endpoints. The feature flag `NOTIFICATIONS_FEATURE_FLAGS.notificationsInbox = true` means the sheet is always active.

## Threat Surface Scan

No new threat surface beyond the plan's `<threat_model>`:
- T-87-14: CSRF carried by `clientRequest('patch',...)` transport — verified pattern reused
- T-87-15: Server-side IDOR scoping (client_id from principal) — no client_id in request params
- T-87-16: `pnpm eslint src/screens/sheets/` exit 0 confirmed — swap-seam boundary enforced

## Self-Check: PASSED

- [x] `apps/client-pwa/eslint.config.js` — exists, NotificationsSheet grep count = 0
- [x] `apps/client-pwa/src/lib/clientQueries.ts` — exports `useClientNotifications`, `useMarkNotificationRead`, `useMarkAllNotificationsRead`, `clientPortalKeys.notifications`
- [x] `apps/client-pwa/src/data/index.js` — re-exports all 3 hooks
- [x] `apps/client-pwa/src/screens/sheets/NotificationsSheet.jsx` — imports from `@/data`, contains `useClientNotifications`
- [x] `apps/client-pwa/src/screens/sheets/NotificationsSheet.test.jsx` — exists, 9 tests
- [x] `apps/client-pwa/src/screens/HomeScreen.jsx` — no longer hardcodes `unread = 0`
- [x] Commits: dfcc5aaf (task 1), 73f9e37e (task 2) — verified in git log
