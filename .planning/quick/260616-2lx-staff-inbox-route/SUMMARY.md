---
quick_id: 260616-2lx
slug: staff-inbox-route
status: complete
created: 2026-06-16
completed: 2026-06-16
mode: quick
commit: 160d9d88
files_changed: 2
---

# Quick Task Summary: Mount the staff chat inbox route + nav

## What was done
Made the v3.2 Phase 116 staff chat inbox (MessagesPage) reachable. It was fully wired to
the real `/api/v1/messages` hooks and the backend worked, but the page was unreachable —
`/messages` rendered the FND-04 `<ComingSoon/>` stub and «Сообщения» was absent from the
sidebar. Found during the v3.2 browser UAT (.planning/v3.2-UAT-BROWSER-AUDIT.md, test 15 — blocker).

## Changes (admin-app frontend only)
1. **`src/app/router.tsx`** — `ROUTES.messages` now lazy-loads `MessagesPage`
   (`(await import('@/pages/messages/MessagesPage')).MessagesPage`), moved out of the
   "Отложенные маршруты (FND-04 hide-for-future)" block into the active routes.
2. **`src/layouts/AppLayout/nav-items.ts`** — re-added `{ label: 'Сообщения', to: ROUTES.messages,
   icon: MessageSquare }` to the «Управление» section. No `ownerOnly` → visible to BOTH roles;
   reception is read-only (reply composer already gated owner-only inside MessagesPage via
   `can(role,'create','messages')`). Updated the FND-04 comment accordingly.

## Verification
- `pnpm -F @clubcore/admin-app typecheck` — clean
- `pnpm -F @clubcore/admin-app lint` — clean
- `pnpm -F @clubcore/admin-app test` — 410 passed (35 files; router-smoke renders every route)
- **Browser re-verify (real backend):**
  - Owner: «Сообщения» in nav → inbox lists both real threads + «3 непрочитанных диалогов»; opened a
    thread (real history, unread cleared 3→1); sent a reply → appended to thread + list shows «Вы: …».
  - Reception: inbox + thread history visible, but NO reply composer / «Отправить» (read-only). Correct.
  - Zero console errors in both contexts.

UAT test 15 (was blocker) + 16 + 17 now pass. v3.2 UAT: 20 pass / 0 open issues / 1 skip (contract-level).

## Self-check: PASSED
Both files changed and committed (160d9d88). Gates green. Feature verified reachable + functional in the browser.
