---
quick_id: 260616-2lx
slug: staff-inbox-route
description: Make the v3.2 staff chat inbox reachable (mount route + nav)
created: 2026-06-16
mode: quick
source: .planning/v3.2-UAT-BROWSER-AUDIT.md (Gap, test 15 — blocker)
---

# Quick Task: Mount the staff chat inbox route + nav

## Problem
v3.2 Phase 116 wired `apps/admin-app/src/pages/messages/MessagesPage.tsx` to the real
`/api/v1/messages` hooks (useThreads/useThread/useSendReply/useMarkThreadRead) and the
backend works (GET /messages/threads → 200), but the page is **unreachable**:
- `src/app/router.tsx` maps `ROUTES.messages` to `<ComingSoon/>` (FND-04 hide-for-future block).
- `src/layouts/AppLayout/nav-items.ts` deliberately omits «Сообщения» from the sidebar.

Browser UAT (.planning/v3.2-UAT-BROWSER-AUDIT.md test 15) confirmed `/messages` renders
«Раздел в разработке». MSG-01/MSG-02 are therefore inaccessible to staff.

## Changes (admin-app frontend only — no backend)

### Task 1 — router.tsx: mount the real page
- Remove `{ path: ROUTES.messages, element: <ComingSoon /> }` from the "Отложенные маршруты
  (FND-04 hide-for-future)" block.
- Add an active route mirroring the lazy shape used by every other page:
  `{ path: ROUTES.messages, lazy: async () => ({ Component: (await import('@/pages/messages/MessagesPage')).MessagesPage }) }`
  placed in the active-routes section (e.g. right after the `audit` route).
- Export verified: `export function MessagesPage()` at MessagesPage.tsx:89.

### Task 2 — nav-items.ts: re-add «Сообщения»
- Import a messages icon from lucide (`MessageSquare`).
- Add `{ label: 'Сообщения', to: ROUTES.messages, icon: MessageSquare }` to the «Управление»
  section (after «Тренеры»). NO `ownerOnly` → visible to BOTH owner and reception
  (reception is read-only; the reply composer is already gated owner-only via
  `can(role,'create','messages')` inside MessagesPage).
- Update the FND-04 comment (line ~22) so it no longer lists «Сообщения» as removed.

## Gates
- `pnpm -F @clubcore/admin-app typecheck` clean
- `pnpm -F @clubcore/admin-app lint` clean
- `pnpm -F @clubcore/admin-app test` (router-smoke renders every route, incl. /messages)
- Browser re-verify: owner inbox lists 2 threads + reply works; reception sees inbox but no composer.
