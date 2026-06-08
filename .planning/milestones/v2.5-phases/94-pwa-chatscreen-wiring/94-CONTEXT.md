# Phase 94: PWA ChatScreen Wiring - Context

**Gathered:** 2026-06-08
**Status:** Ready for planning
**Mode:** Smart discuss (autonomous) + user-directed pixel-perfect port

<domain>
## Phase Boundary

Graduate `apps/client-pwa/src/screens/ChatScreen.jsx` from the `ComingSoon` placeholder to a real, live chat wired to the messaging REST + WebSocket backend built in phases 90–93. Delivers PWA-01/02/03.

**OVERRIDING DIRECTIVE (user, 2026-06-08): pixel-perfect port of an existing design.**
A finished chat UI already exists at `/Users/andre/Workspace/Development/clubcore-client-pwa/src/screens/ChatScreen.jsx` (preserved in this phase dir as `94-REFERENCE-ChatScreen.jsx`, 1398 lines, self-contained — only React hooks). The implemented screen must look and behave **пиксель-в-пиксель** like the reference: visual design, structure, sizes, spacing, typography, colors, element states, animations, and user behavior are transferred **without changes**. The reference's `const CSS` block, icon set, bubble/list/composer markup, animations (screen-push/pop, msg-in, typing-bounce, scene-in, spot-float, pull-to-refresh, sheet slide, toast), empty states (branded "spot" illustration), day separators, unread divider, scroll-down FAB, swipe/long-press gestures, and pull-to-refresh are the locked contract.

Out of scope: admin-web (frozen until v2.6); new backend endpoints (all consumed surface shipped in 90–93).

</domain>

<decisions>
## Implementation Decisions

### Reference reconciliation (user-confirmed 2026-06-08)

**1. Structure — port BOTH views, one real conversation.**
- Transfer the reference's LIST view (conversation cards, search, segmented all/unread filter, swipe-to-mute, long-press action sheet) AND the THREAD view (bubbles, composer, attach sheet, scroll-down FAB, empty state) **pixel-perfect**.
- The list contains exactly **one real conversation** — «Администрация / Мой зал» (the reference `c1`, `isOfficial`, verified-✓ badge) — wired to the backend single client↔gym thread. The other 3 mock conversations (`c2` тренер, `c3` уведомления, `c4` ресепшен) are removed.
- Preserve list/thread **user behavior unchanged**: swipe-to-mute, long-press sheet (mark read/mute/archive/delete), pull-to-refresh, search, all/unread filter, scroll-down FAB, composer auto-grow, Enter-to-send, view push/pop transitions. Where a list action has no v2.5 backend (mute/archive/delete of the single conv), it operates on **local UI state** exactly as the prototype does.

**2. Chrome — strip the prototype shell, mount inside the real PWA shell.**
- REMOVE: simulated iPhone `.device`/`.device-inner`/`.island` frame, `.status-bar`, `.home-indicator`, the prototype's own `.tabbar` (Главная/Запись/Чат/Профиль with `data-go` to `*.html`), the `Tweaks` panel, and the edit-mode `postMessage`/`window.parent` protocol + the global `data-go`/`data-toast` document click handler + the `myzal_theme` localStorage/storage theme sync.
- KEEP only the chat screen content; mount it inside the existing `apps/client-pwa` App shell + routing (`/chat` via `ChatRoute`), and let the **existing PWA `TabBar`** own the bottom nav. The Chat-tab **unread badge** is fed from the real `unreadCount` (App.jsx currently passes `unreadChat={0}`).
- CSS: preserve the reference visual tokens/styles **exactly**, but **scope** them to the chat screen (wrap in a root container; do NOT let the reference `:root`/`html,body`/`body.dark` global overrides leak into and re-theme the rest of the PWA). Theme (light/dark) follows the existing PWA theme, not the prototype Tweaks panel.

**3. Feature mapping — wire real, hide-for-future (keep code, don't show).**
- **Wired to backend (real):** text send/receive (REST `POST /messages` + WS `new_message`), real **photo attachment** (Camera + Gallery → validate image/≤5MB client-side → two-step upload→send → render the real image in a bubble; tap → full-screen overlay), **read receipts** (✓ sent / ✓✓ read from Phase 91), **typing indicator** (staff typing dots from Phase 91 ephemeral events), **unread count + badge**, **pull-to-refresh** (real refetch + `?after=` catch-up).
- **Kept but HIDDEN (code retained for future, not rendered):** voice messages, document attach, fake photo-preset gradient bubbles (`PHOTO_PRESETS`/`PhotoBubble`), `system`/`cancel` message kinds. The attach sheet shows only **Camera + Фото из галереи**; Документ + Голосовое are hidden (kept in source, commented/feature-flagged off).
- **Not wired (prototype-only behavior):** bot autoresponder (`botReplies`) and its quick-reply chips — real staff replies arrive via WS, so the fake bot is disabled; quick-reply chips hidden (bot-coupled).

### Realtime / WebSocket architecture
- **App-level singleton WS** (mounted at app root via a provider) so the Chat-tab unread badge updates in real time from any screen; the open thread is driven when ChatScreen is mounted. **30s React Query poll fallback** only while WS is disconnected. Reconnect with capped exponential backoff; on reconnect, catch up via the REST `?after=` cursor. Auth via same-origin httpOnly `cc_client_access` cookie on WS upgrade.

### Data adaptation (reference mock → real)
- `INITIAL_CONVS` mock → one conversation object hydrated from backend: thread metadata + message list. Message shape maps `{from:'me'|'them', body, time, read, kind, photo}` → real message `{role:'client'|'staff', body, sentAt, readAt, attachment}`. `time` rendered via `Intl.DateTimeFormat` Europe/Moscow HH:MM. `from:'me'` ⇔ role client; `'them'` ⇔ role staff. `read` ⇔ `readAt != null`. Photo bubble renders the real authenticated attachment image (Phase 92 IDOR-safe serve) instead of the gradient preset.
- Graduation recipe (de-list 3 D-71-09 ESLint spots + import data via `@/data`) per the Phase 87/88 precedent.

### Claude's Discretion (defaults)
- Pagination: initial latest page; scroll-up loads older via cursor; autoscroll-to-bottom on send / inbound-when-near-bottom (matches reference `stickRef` behavior).
- Mark-as-read on thread open + inbound-while-open → clears badge (reference already zeroes `unread` on `openThread`).
- Unread badge cap display `99+`.
- Russian-only copy; preserve all reference Russian strings verbatim.

</decisions>

<code_context>
## Existing Code Insights

### Reference (source of truth — pixel-perfect)
- `.planning/phases/94-pwa-chatscreen-wiring/94-REFERENCE-ChatScreen.jsx` — the full design (CSS block, `Ico`/`Avatar`/`ReadTick`/`PhotoBubble`/`MessageRow`/`ConvCard` components, list+thread render, gestures, animations). Visual contract = this file verbatim (minus stripped chrome + hidden features).

### Reusable PWA assets
- `src/lib/clientFetcher.ts` — `clientRequest()` fetch wrapper (httpOnly `cc_client_access`, single-flight refresh, client CSRF `clubcore_client_csrf`). Reuse for REST message ops + the two-step photo upload.
- `src/lib/clientQueries.ts` — React Query hooks + `clientPortalKeys`; new messaging hooks + `useClientMessagingWS` live here.
- `src/data/index.js` — swap-seam barrel (D-71-07): graduated screens import from `@/data`.
- `src/components/TabBar.jsx` — has a `badge` prop on the Chat tab (App.jsx:454 `unreadChat={0}` → wire to real unread).
- Graduation precedents: `NotificationsSheet.jsx` (P87), `TrainerDetailSheet.jsx` (P88) — loading/error/refresh patterns.

### Established Patterns
- JS/JSX screens (allowJs ramp D-69-06); new hooks/utilities `.ts`. No Tailwind — inline styles + CSS tokens; complex UI via scoped `const CSS` string (exactly what the reference already does).
- State: React Query (data) + React Context (UI/Tweaks/Auth) + local `useState`. Service worker: `/api/*` network-only; dev proxies `/api` → `localhost:8000`.

### Integration Points
- De-list ChatScreen from the **D-71-09 ESLint zone** in `apps/client-pwa/eslint.config.js` — 3 spots: the `!src/screens/ChatScreen.jsx` ignore-negation (~line 28), the `files:` target block (~lines 68-70), and the `no-restricted-paths` zone `target` (~lines 91-93). After removal `grep` for the ChatScreen entry returns 0 and the screen imports via `@/data`.
- Route: ChatScreen lazy `App.jsx:37`, mounted `/chat` via `ChatRoute()` (App.jsx:143-154) behind `<RequireAuth>`.
- Backend: WS `/api/v1/client/ws/messages` (cookie auth, Origin-checked); REST `/api/v1/client/messages` (+ `?after=` cursor, `PATCH /messages/read`); attachments upload + IDOR-safe serve from Phase 92.

</code_context>

<specifics>
## Specific Ideas

- The reference IS the design — do not redesign. Transfer CSS, markup, icons, animations, gestures verbatim; only swap the data layer (mock → real), strip prototype chrome, and hide the future-mock features.
- Scope the reference CSS so its `:root`/`body`/`body.dark` rules don't re-theme the rest of the PWA.
- Browser-verify note (prior PWA phases): a stale service worker can mask new code — hard-reload / bump SW cache; use the dev login + reseed flow; confirm `/api` calls are network-only.

</specifics>

<deferred>
## Deferred Ideas

- Re-enable hidden features when backend support lands: voice messages, document attachments, multi-conversation list (тренер/уведомления/ресепшен), system/cancel message kinds, quick-reply chips, bot/auto-reply.
- Staff identity / avatars beyond the single official «Мой зал» conversation (v2.5 staff anonymous; full identity → v2.6 admin-web).

</deferred>
