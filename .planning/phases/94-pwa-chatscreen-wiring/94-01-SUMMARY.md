---
phase: 94-pwa-chatscreen-wiring
plan: "01"
subsystem: client-pwa
tags: [messaging, react-query, websocket, badge, pwa]
dependency_graph:
  requires: []
  provides:
    - useClientMessages (GET /client/messages, staleTime+refetchInterval 30s)
    - useSendMessage (POST /client/messages, Idempotency-Key)
    - useUploadAttachment (multipart FormData POST /client/messages/attachments)
    - useMarkMessagesRead (PATCH /client/messages/read, 204)
    - useClientMessagingWS (first WS hook, capped backoff, frame dispatch)
    - UIContext.unreadChat / setUnreadChat
    - App-level WS singleton + TabBar 99+-capped badge wiring
  affects:
    - apps/client-pwa/src/App.jsx
    - apps/client-pwa/src/context/UIContext.jsx
    - apps/client-pwa/src/data/index.js
tech_stack:
  added: []
  patterns:
    - React Query useQuery with refetchInterval poll fallback
    - First WebSocket hook with capped exponential backoff reconnect
    - App-level WS singleton (badge updates from any screen)
    - window.__chat* bridge for ChatScreen read-receipt/typing delegation
key_files:
  created:
    - apps/client-pwa/src/lib/useClientMessagingWS.ts
    - apps/client-pwa/src/lib/clientQueries.messaging.test.ts
    - apps/client-pwa/src/lib/useClientMessagingWS.test.ts
  modified:
    - apps/client-pwa/src/lib/clientQueries.ts
    - apps/client-pwa/src/data/index.js
    - apps/client-pwa/src/context/UIContext.jsx
    - apps/client-pwa/src/App.jsx
decisions:
  - "Path type cast via `clientRequest as unknown as (method, path, init?) => Promise<unknown>` for messaging paths absent from schema.d.ts until Phase 95 OpenAPI handoff"
  - "refetchInterval:30_000 set on useClientMessages (not App.jsx) as the sole 30s poll fallback — staleTime alone does not poll"
  - "App-level WS singleton in App() body (not ChatRoute) so badge updates from any screen"
  - "window.__chatReadReceipt / window.__chatTyping bridge pattern chosen for ChatScreen delegation (Plan 02 registers/clears these)"
metrics:
  duration: "8 minutes"
  completed_date: "2026-06-08"
  tasks_completed: 3
  tasks_total: 3
  files_created: 3
  files_modified: 4
---

# Phase 94 Plan 01: PWA ChatScreen Data Layer Summary

**One-liner:** 4 messaging React Query hooks + first WS hook with capped backoff + UIContext badge plumbing, all TDD-tested with 28 new tests green.

## Objective

Build the messaging data layer (REST hooks + WebSocket singleton + barrel exports + unread badge plumbing) that Plan 94-02 (ChatScreen port) will consume. Interface-first — no visual changes in this plan.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Messaging React Query hooks + key factory | a57331ac | clientQueries.ts, clientQueries.messaging.test.ts |
| 2 | useClientMessagingWS + test | 83fc8666 | useClientMessagingWS.ts, useClientMessagingWS.test.ts |
| 3 | Barrel exports + UIContext + App WS mount + badge | 2ffd33ff | data/index.js, UIContext.jsx, App.jsx |

## Artifacts Delivered

### 1. clientQueries.ts — extended with messaging surface

**Key factory:** `clientPortalKeys.messages(after?)` returns `[..., 'messages', after ?? '']`.

**Interfaces:** `MessageAttachmentItem`, `MessageItem`, `MessageListData`, `AttachmentUploadResult` — all camelCase matching backend `alias_generator=to_camel`.

**Hooks:**
- `useClientMessages(after?)` — staleTime 30_000 AND refetchInterval 30_000 (ROADMAP criterion 2 poll fallback — keeps badge fresh when WS is disconnected)
- `useSendMessage()` — POST + Idempotency-Key header, onSettled invalidation
- `useUploadAttachment()` — FormData POST, no Content-Type (browser sets boundary)
- `useMarkMessagesRead()` — PATCH 204, onSettled invalidation

**Type note:** Messaging paths (`/api/v1/client/messages*`) are not yet in `schema.d.ts` (added in Phase 95 OpenAPI handoff). Calls cast `clientRequest as unknown as (method, path, init?) => Promise<unknown>` to bypass the path constraint without changing runtime behavior.

### 2. useClientMessagingWS.ts — first WebSocket hook

- URL: `ws://${location.host}/api/v1/client/ws/messages` (https → wss)
- Frame dispatch: `new_message → onNewMessage(messageId)`, `read_receipt → onReadReceipt(readAt)`, `typing → onTyping()`, `ping → no-op`
- Malformed JSON: swallowed silently (T-94-02 mitigation)
- Reconnect: capped exponential backoff ×2 to 30s via destroyed-flag teardown (T-94-03 mitigation)
- Auth: same-origin httpOnly cookie on upgrade (no URL token, T-94-01)

### 3. data/index.js — 4 new re-exports

Added under `// Phase-94 PWA-01: messaging hooks` after the Phase-88 TRNR-04 block.

### 4. UIContext.jsx — unreadChat state

`const [unreadChat, setUnreadChat] = useState(0)` added in the chat/book flow group with `unreadChat` in the useMemo value and dependency array. `setUnreadChat` is referentially stable (from useState) so excluded from deps.

### 5. App.jsx — WS singleton + badge

- Imports: `useQueryClient` from `@tanstack/react-query`, `useClientMessagingWS` + `clientPortalKeys` from lib
- `useClientMessagingWS` called in `App()` body gated on `status === 'authed'` — NOT inside ChatRoute so badge updates from any screen
- `onNewMessage`: invalidates `[...clientPortalKeys.all, 'messages']` → triggers refetch → Plan 02 Task 2 reads `data.unreadCount` and calls `ui.setUnreadChat()`
- `onReadReceipt`/`onTyping`: delegate via `window.__chatReadReceipt?.(readAt)` / `window.__chatTyping?.()` bridges (Plan 02 registers/clears these)
- TabBar: `unreadChat={ui.unreadChat > 99 ? '99+' : (ui.unreadChat || 0)}` (PWA-02, 99+ cap)

## Test Results

| Test file | Tests | Status |
|-----------|-------|--------|
| clientQueries.messaging.test.ts | 17 | PASS |
| useClientMessagingWS.test.ts | 11 | PASS |
| Full suite (28 files) | 208 | PASS |

Critical regression guard: test asserts `refetchInterval === 30_000` on the `useQuery` options object — prevents the 30s poll fallback from being accidentally removed.

## Verification Gates

- `pnpm test` — 208/208 tests green (28 files)
- `pnpm exec tsc -b --noEmit` — clean
- `pnpm lint` — clean
- Grep gates: `useClientMessages` in src/data/index.js ✓, `unreadChat` in UIContext.jsx ✓, `useClientMessagingWS` in App.jsx ✓

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Path type constraint for new messaging endpoints**
- **Found during:** Task 1 tsc verification
- **Issue:** `clientRequest<P extends keyof paths>` requires paths to exist in `schema.d.ts`. Messaging paths are absent (Phase 95 OpenAPI handoff adds them).
- **Fix:** Cast `clientRequest` through `unknown` to a plain `(method, path, init?) => Promise<unknown>` type at the 4 call sites. Runtime behavior is identical; type safety restored at Phase 95 when the paths are added to schema.d.ts.
- **Files modified:** `apps/client-pwa/src/lib/clientQueries.ts`
- **Commit:** a57331ac

**2. [Rule 1 - Bug] Test TypeScript errors — `mock.calls[n]` is possibly undefined**
- **Found during:** Task 1 tsc verification
- **Issue:** `vi.fn().mock.calls[n]` has type `unknown[] | undefined` in strict mode.
- **Fix:** Cast `mock.calls[n]` to `unknown[]` at 3 access sites in the test file.
- **Files modified:** `apps/client-pwa/src/lib/clientQueries.messaging.test.ts`
- **Commit:** a57331ac

## Known Stubs

None — this plan creates only data layer hooks and wiring. No placeholder text, empty arrays, or fake data introduced. The `ui.setUnreadChat` is called in Plan 02 Task 2 when the messages query resolves; the badge shows 0 until then, which is correct initial state.

## Threat Flags

None — all new network surface (REST endpoints, WS connection) matches the threat model defined in the plan's `<threat_model>` block. No unexpected endpoints introduced.

## Self-Check: PASSED

- [x] `apps/client-pwa/src/lib/clientQueries.ts` — exists, contains `export function useClientMessages`
- [x] `apps/client-pwa/src/lib/useClientMessagingWS.ts` — exists, contains `new WebSocket`
- [x] `apps/client-pwa/src/data/index.js` — exists, contains `useClientMessages`
- [x] `apps/client-pwa/src/context/UIContext.jsx` — exists, contains `unreadChat`
- [x] `apps/client-pwa/src/App.jsx` — exists, contains `useClientMessagingWS`
- [x] Commits a57331ac, 83fc8666, 2ffd33ff — all present in git log
