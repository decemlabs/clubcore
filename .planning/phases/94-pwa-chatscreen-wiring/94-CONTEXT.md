# Phase 94: PWA ChatScreen Wiring - Context

**Gathered:** 2026-06-08
**Status:** Ready for planning
**Mode:** Smart discuss (autonomous) — 4 grey areas surfaced, all recommendations accepted

<domain>
## Phase Boundary

Graduate `apps/client-pwa/src/screens/ChatScreen.jsx` from the `ComingSoon` placeholder to a real, live chat wired to the backend messaging surface built in phases 90–93. Delivers PWA-01/02/03:
- ChatScreen renders thread history (client-right / staff-left bubbles, Europe/Moscow HH:MM timestamps), fully de-listed from the D-71-09 ESLint placeholder zone (3 spots removed → `grep` returns 0; data imported via `@/data`).
- The Chat-tab unread badge reflects the real `unreadCount` in real time over WS, with a 30-second React Query poll fallback when the WS is disconnected.
- Client can pick a photo (gallery or camera), preview a thumbnail in the thread/composer, and send it; previously sent photos open full-screen on tap.

Out of scope: admin-web (frozen until v2.6), File/Voice attachment kinds (no v2.5 backend support), new backend endpoints (all consumed surface already shipped in 90–93).

</domain>

<decisions>
## Implementation Decisions

### Realtime / WebSocket architecture
- **App-level singleton WS** mounted at the app root via a provider (not screen-scoped) so the Chat-tab unread badge updates in real time from ANY screen, and the live thread is driven when ChatScreen is open.
- **30-second React Query poll fallback** activates only while the WS is disconnected (success criterion 2). When WS is healthy, no poll.
- **Reconnect** with exponential backoff (capped); on reconnect, **catch up via the REST `?after=` cursor** to fetch any messages missed while disconnected (matches the backend DB-first / id-only-frame design).
- Auth rides the same-origin httpOnly `cc_client_access` cookie (browser auto-sends on WS upgrade); no URL token. New hook (e.g. `useClientMessagingWS`) lives alongside `clientQueries.ts`.

### Attachments
- Wire **Photo (gallery) + Camera** only: `<input type=file accept="image/*">` for gallery, `capture="environment"` for camera.
- **Hide/disable File + Voice** in `ChatAttachSheet` as explicitly out of v2.5 scope (backend accepts images only).
- **Client-side validation before upload**: image type + ≤5MB (mirror the backend cap from Phase 92); surface a friendly error (toast/inline) on reject. Magic-byte validation remains authoritative server-side.

### Photo send UX
- **Preview-then-send**: after pick, show a thumbnail preview in the composer with a remove control (and optional text caption) before sending.
- On confirm, run the backend **two-step flow**: upload attachment → send message with `attachment_id` (Phase 92 contract).
- Tapping a photo in the thread opens a **lightweight full-screen image overlay** (success criterion 3).

### Status UI (read receipts + typing)
- **Checkmarks** on the client's own bubbles: ✓ = sent, ✓✓ = read (driven by Phase 91 read_receipt WS frames / reply-as-read).
- **Animated typing-dots bubble** on the staff side while a staff typing event is active (Phase 91 ephemeral typing; auto-dismiss on its TTL).

### Claude's Discretion (defaults — not separately confirmed)
- **Pagination/scroll**: initial load = latest page; scroll-up loads older messages via the `?after=`/cursor; auto-scroll to bottom on send and on inbound message when the user is already near the bottom.
- **Mark-as-read trigger**: call `PATCH /messages/read` when ChatScreen is opened/focused and on inbound message while the screen is focused → badge clears.
- **Unread source**: use the `unreadCount` returned by `GET /messages`, kept fresh via WS new_message/read frames; badge displayed via the existing `TabBar` `badge` prop (currently hardcoded `unreadChat={0}`). Cap display at `99+`.
- **Empty state**: friendly Russian prompt (e.g. «Напишите залу — мы на связи»).
- **Loading/error**: skeleton on first load, error fallback with retry — same pattern as TrainerDetailSheet/NotificationsSheet.
- All Russian-only copy; timestamps via `Intl.DateTimeFormat` pinned to `Europe/Moscow` (existing convention).

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/lib/clientFetcher.ts` — `clientRequest(method, path, init?)`: typed fetch wrapper with httpOnly `cc_client_access` auth, single-flight refresh on 401, client CSRF cookie `clubcore_client_csrf`. Reuse for all REST message ops.
- `src/lib/clientQueries.ts` — React Query hooks + `clientPortalKeys` key factory (per-feature namespacing); global `staleTime: 30_000`, `refetchOnWindowFocus: false`. New messaging hooks + WS hook go here.
- `src/data/index.js` — the swap-seam barrel (D-71-07): graduated screens import hooks from `@/data`, NOT directly from `clientQueries.ts`.
- `src/components/TabBar.jsx` — already supports a `badge` prop on the Chat tab (lines 8, 25-34). `App.jsx:454` passes `unreadChat={0}` (hardcoded — to be wired).
- `src/screens/sheets/flows.jsx:1167-1215` — `ChatAttachSheet` (Photo/Camera/File/Voice grid) UI skeleton; `onPick(kind)` via `window.__attachPick`.
- Graduation precedents: `NotificationsSheet.jsx` (P87) and `TrainerDetailSheet.jsx` (P88) — the proven `@/data` hook + loading/error/refresh recipe.

### Established Patterns
- JS/JSX screens (allowJs ramp D-69-06); new utilities/hooks should be `.ts`. No Tailwind — inline styles + CSS token variables in `styles.css`; complex UI uses a scoped `const CSS = \`...\`` string.
- State: React Query (data) + React Context (UIContext/TweaksContext/AuthContext) + local `useState`. No Zustand/Redux.
- Service worker: `/api/*` is network-only (never cached). Dev proxies `/api` → `localhost:8000`.

### Integration Points
- De-list ChatScreen from the **D-71-09 ESLint zone** in `apps/client-pwa/eslint.config.js` — 3 spots: the `!src/screens/ChatScreen.jsx` ignore-negation (~line 28), the `files:` block target (~lines 68-70), and the `no-restricted-paths` zone `target` (~lines 91-93). After removal, `grep` for the ChatScreen entry must return 0 and the screen imports via `@/data`.
- Route: ChatScreen lazy-loaded `App.jsx:37`, mounted at `/chat` via `ChatRoute()` (App.jsx:143-154) behind `<RequireAuth>`.
- WS endpoint: backend `/api/v1/client/ws/messages` (cookie auth, Origin-checked); REST under `/api/v1/client/messages` (+ `?after=` cursor, `PATCH /messages/read`).

</code_context>

<specifics>
## Specific Ideas

- Follow the WhatsApp-style messenger idiom (✓/✓✓, typing dots, right/left bubbles) — kept compact and token-styled, not a heavy custom chrome.
- Reuse the existing `ChatAttachSheet` grid; just disable the non-image kinds rather than building a new picker.
- Browser-verify note (from prior PWA phases): a stale service worker can mask new code — hard-reload / bump SW cache; use the dev login + reseed flow; confirm `/api` calls are network-only in the SW tab.

</specifics>

<deferred>
## Deferred Ideas

- File + Voice attachment kinds (need backend support → not v2.5).
- Staff identity / avatars in the thread (v2.5 staff is anonymous role='staff'; full identity → v2.6 admin-web inbox).
- Message search / thread list (single-gym v2.5 has one thread per client).

</deferred>
