---
phase: 94-pwa-chatscreen-wiring
fixed_at: 2026-06-08T08:19:00Z
review_path: .planning/phases/94-pwa-chatscreen-wiring/94-REVIEW.md
iteration: 1
findings_in_scope: 10
fixed: 10
skipped: 0
status: all_fixed
---

# Phase 94: Code Review Fix Report

**Fixed at:** 2026-06-08T08:19:00Z
**Source review:** .planning/phases/94-pwa-chatscreen-wiring/94-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 10 (CR-01, CR-02, WR-01..WR-08)
- Fixed: 10
- Skipped: 0
- Info findings (IN-01..IN-04): out of scope (critical_warning), not addressed.

All gates verified green from `apps/client-pwa` after fixes:
`pnpm typecheck` (clean), `pnpm lint` (clean), `pnpm test` (222/222, up from 210 — 12 new
regression tests added). The pixel-perfect visual port was preserved: every change is to
logic/wiring only (WS lifecycle, effect deps, timestamp comparison, objectUrl lifecycle,
mark-read guard, reconnect timer, bridge ownership, uuid guard). No markup/CSS/animation/copy
was altered.

## Fixed Issues

### CR-01: App-level WebSocket reconnects on every App re-render (inline callback deps)

**Files modified:** `apps/client-pwa/src/lib/useClientMessagingWS.ts`
**Commit:** c90a21fa
**Applied fix:** Introduced a `cbRef` ref holding `{ onNewMessage, onReadReceipt, onTyping, onReconnect }`,
updated every render. The connect `useEffect` now depends ONLY on `[enabled]` (was
`[enabled, onNewMessage, onReadReceipt, onTyping]`), and the `onmessage` dispatcher calls
`cbRef.current.*`. App()'s fresh inline closures no longer tear down + reopen the singleton
socket on every re-render (sheet toggles, push toasts, and the `setUnreadChat` badge feed).
Regression test asserts the socket is not reopened/closed across re-renders and that the
latest callback is always dispatched to (ref-backed).

### CR-02: Read-tick watermark + dedup used lexicographic ISO-string comparison

**Files modified:** `apps/client-pwa/src/screens/ChatScreen.jsx`
**Commit:** a613956b
**Applied fix:** Both comparison sites now use epoch milliseconds via `Date.parse(...)` instead
of raw ISO-string `<=` / `>`. At ~line 732 the watermark check is `Date.parse(a.sentAt) <= wmMs`
(with `wmMs = Date.parse(readWatermark)` hoisted once). At ~line 859 the watermark-monotonic
update is `Date.parse(readAt) > Date.parse(prev)`. This makes mixed offset formats (`Z` vs
`+03:00`) and fractional-second differences compare by true instant. Regression test
(`ChatScreen.readtick.test.ts`) pins the predicate semantics and demonstrates a case where the
old string comparison would have wrongly marked a later message as read.
**Note:** classified as a logic/semantic correctness fix — recommend human spot-check that the
PWA-02 ✓✓ tick behaves as intended end-to-end, though the regression test covers the ordering.

### WR-01: Documented `?after=` reconnect catch-up was never invoked

**Files modified:** `apps/client-pwa/src/lib/useClientMessagingWS.ts`, `apps/client-pwa/src/App.jsx`
**Commit:** dd6256b2
**Applied fix:** Wired the intended catch-up (preferred over deleting the dead path). Added an
optional `onReconnect` callback to the hook, fired on the first `onopen` AFTER a disconnect
(tracked via a `hasConnectedOnce` flag so the initial connect does not fire it). App() supplies
`onReconnect` that invalidates the messages query, so messages that arrived during the WS gap
are picked up via a REST refetch instead of waiting for the 30s poll. The `after` cursor on
`useClientMessages` remains available; the practical catch-up is the invalidation/refetch.
Hook header doc updated to reflect the wiring. Regression test asserts `onReconnect` fires on
reopen but not on the initial connect.

### WR-02: Photo objectUrl revoked while still referenced

**Files modified:** `apps/client-pwa/src/screens/ChatScreen.jsx`
**Commit:** a613956b
**Applied fix:** Removed the unconditional `URL.revokeObjectURL(objectUrl)` from the `finally`
block of `sendPhoto`. Created object URLs are now tracked in a `photoObjectUrlsRef` Set. A new
garbage-collector effect (deps `[optimistic, photoOverlay]`) revokes a tracked URL only once it
is no longer referenced by any optimistic message AND is not the currently-open full-screen
overlay. A second mount-cleanup effect revokes any remaining URLs on unmount as a safety net.
This eliminates the flicker/blank-blob window on both the optimistic bubble and the overlay.

### WR-03: Mark-read effect could self-trigger a PATCH loop

**Files modified:** `apps/client-pwa/src/screens/ChatScreen.jsx`
**Commit:** a613956b
**Applied fix:** Added an in-flight guard to the unread→mark-read effect: it now fires only when
`!markReadM.isPending`, and `markReadM.isPending` was added to the dep array. If the backend has
not yet converged `unreadCount` to 0 after the invalidation/refetch, no new mutation is issued
while one is pending, bounding the PATCH storm.

### WR-04: `setUnreadChat` badge effect depended on `ui`

**Files modified:** `apps/client-pwa/src/screens/ChatScreen.jsx`
**Commit:** a613956b
**Applied fix:** The badge-feed effect no longer depends on the memoized `ui` object (whose
identity changes on any UI state change). The stable `setUnreadChat` setter is captured in a
ref (`setUnreadChatRef`), and the effect depends on `[serverData, adminUnread]`. (Combined with
WR-08 below in the same effect.)

### WR-06: `window.__chat*` bridge had no ownership guard

**Files modified:** `apps/client-pwa/src/screens/ChatScreen.jsx`
**Commit:** a613956b
**Applied fix:** The bridge-registration effect now captures the previous
`window.__chatReadReceipt` / `window.__chatTyping` handlers, installs named handler references,
and on cleanup restores the previous handlers ONLY if the current global still equals our own
handler (`window.__chatReadReceipt === readReceiptHandler`). A double-mount / StrictMode
double-invoke no longer lets an unmounting instance clobber a freshly-mounted instance's
handlers.

### WR-07: `crypto.randomUUID()` assumed available without guard

**Files modified:** `apps/client-pwa/src/screens/ChatScreen.jsx`, `apps/client-pwa/src/lib/uuid.ts` (new)
**Commit:** a613956b
**Applied fix:** Added a shared, secure-context-safe `uuidV4()` helper
(`crypto.randomUUID?.()` → `crypto.getRandomValues` RFC-4122 v4 → `Math.random` fallback,
strict-mode-safe). Replaced both `crypto.randomUUID()` idempotency-key call sites in
`sendTextMessage` and `sendPhoto`. Prevents a hard send-failure on plain-HTTP LAN testing /
older WebViews. Unit test (`uuid.test.ts`) covers the native path, both fallback paths
(no `randomUUID`, no `crypto`) and uniqueness.
**Note:** the review also flagged checking other PWA paths (e.g. checkout idempotency) for the
same assumption — that audit is outside this finding's scope and was not performed here.

### WR-08: Tab badge ignored `locallyUnread`/mute and could desync with the card

**Files modified:** `apps/client-pwa/src/screens/ChatScreen.jsx`
**Commit:** a613956b
**Applied fix:** The badge feed now drives the TabBar from the same source of truth as the card
(`adminUnread`) and pushes `0` while the thread is open
(`setUnreadChatRef.current(openIdRef.current != null ? 0 : adminUnread)`), so the tab badge no
longer flickers back to a stale non-zero value from a poll/refetch while the thread is open.

## Skipped Issues

None — all in-scope findings were fixed.

---

_Fixed: 2026-06-08T08:19:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
