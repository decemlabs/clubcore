---
phase: 94-pwa-chatscreen-wiring
reviewed: 2026-06-08T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - apps/client-pwa/src/lib/clientQueries.ts
  - apps/client-pwa/src/lib/useClientMessagingWS.ts
  - apps/client-pwa/src/data/index.js
  - apps/client-pwa/src/context/UIContext.jsx
  - apps/client-pwa/src/App.jsx
  - apps/client-pwa/src/screens/ChatScreen.jsx
  - apps/client-pwa/eslint.config.js
  - apps/client-pwa/src/lib/clientQueries.messaging.test.ts
  - apps/client-pwa/src/lib/useClientMessagingWS.test.ts
  - apps/client-pwa/src/screens/ChatScreen.delist.test.ts
findings:
  critical: 2
  warning: 8
  info: 4
  total: 14
status: issues_found
---

# Phase 94: Code Review Report

**Reviewed:** 2026-06-08
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Reviewed the Phase 94 chat-screen port: the `useClientMessagingWS` hook, the messaging
query/mutation hooks, the optimistic send + two-step photo upload, the read-tick watermark,
the unread-badge feed, the `window.__chat*` bridge, and the scoped CSS.

The tests pass and surface-level structure is sound, but the review found two correctness
defects that defeat the real-time design goals of the phase:

1. The App-level WebSocket is torn down and re-opened on **every App re-render** because the
   four callbacks passed to `useClientMessagingWS` are inline closures that change identity
   each render and are in the effect dependency array (CR-01). This causes a connect/close
   churn (and a reconnect-storm interaction) instead of one stable singleton socket.
2. The read-tick watermark and the duplicate-suppression both rely on **lexicographic string
   comparison of ISO timestamps from two different sources** (server `sentAt`, WS `readAt`).
   Mixed offset formats (`Z` vs `+03:00`) make `<=`/`>` give wrong results, so own-message
   ticks can be marked read incorrectly or never (CR-02).

Additional issues: the documented `?after=` reconnect catch-up is wired into the hook but
never used by the consumer (dead path / unmet ROADMAP behavior); the photo `objectUrl` is
revoked while it may still be rendered (broken image / flicker, and a revoked URL can be
handed to the full-screen overlay); a mark-read effect can self-trigger a mutation loop; and
the WS reconnect path leaks the pending timer reference. Details below.

## Critical Issues

### CR-01: App-level WebSocket reconnects on every App re-render (inline callback deps)

**File:** `apps/client-pwa/src/App.jsx:217-232`, `apps/client-pwa/src/lib/useClientMessagingWS.ts:142`
**Issue:**
`App()` passes four freshly-allocated closures (`onNewMessage`, `onReadReceipt`, `onTyping`
and the options object) to `useClientMessagingWS` on every render. The hook's effect depends
on all three callbacks:

```js
}, [enabled, onNewMessage, onReadReceipt, onTyping])
```

Because the callbacks are new function objects each render, the effect's cleanup runs and
`connect()` re-runs on every App re-render. `App()` re-renders whenever `useUI()` value
changes — i.e. every sheet open/close, push toast, and crucially every `setUnreadChat(...)`
from the badge feed. The result is a continuous teardown/reopen of the "mounted once"
singleton socket the design explicitly intended (`useClientMessagingWS.ts:9` "Mounted ONCE
at app root"). Each teardown calls `ws.close()`; the in-flight `onclose` is suppressed by the
new `destroyed` flag, but a fresh socket is opened immediately, producing connect churn,
dropped frames during the gap, and extra server upgrade load (the very DoS surface T-94-03
tried to bound). It also interacts badly with the badge effect: a `new_message` → invalidate
→ refetch → `setUnreadChat` → App re-render → socket reconnect cascade.

**Fix:** Stabilize the callbacks with `useCallback` (deps: `qc`), or store them in refs inside
the hook so the effect can depend only on `[enabled]`. Ref approach (hook-side, also fixes any
future consumer):

```ts
export function useClientMessagingWS({ enabled = true, onNewMessage, onReadReceipt, onTyping }) {
  const cbRef = useRef({ onNewMessage, onReadReceipt, onTyping })
  cbRef.current = { onNewMessage, onReadReceipt, onTyping }
  useEffect(() => {
    if (!enabled) return
    // ...inside onmessage, call cbRef.current.onNewMessage(...), etc.
  }, [enabled]) // callbacks no longer in deps
}
```

### CR-02: Read-tick watermark + dedup use lexicographic ISO-string comparison across two sources

**File:** `apps/client-pwa/src/screens/ChatScreen.jsx:732`, `859`
**Issue:**
The watermark logic compares ISO timestamp strings directly:

```js
if (a.from === 'me' && !a.read && readWatermark && a.sentAt <= readWatermark) { a.read = true }   // 732
setReadWatermark((prev) => (prev == null || readAt > prev ? readAt : prev))                       // 859
```

`a.sentAt` is the server message's `sentAt` (whatever format the messaging API emits), and
`readWatermark`/`readAt` is the WS `read_receipt` payload (a separate producer). Lexicographic
`<=`/`>` on ISO strings is only correct when both strings use the identical, zero-padded,
same-offset format. If one side emits `2024-01-01T12:00:00Z` and the other
`2024-01-01T15:00:00+03:00` (same instant), or one carries fractional seconds and the other
does not, the string comparison disagrees with the real instant ordering. Consequences:
own messages get marked ✓✓ that the staff has not read (false read receipt), or never get
the ✓✓ they earned (watermark boundary off). This is the core PWA-02 semantic and it is not
robust. The hook doc at `useClientMessagingWS.ts:29-31` describes the intended `sentAt <= readAt`
semantics but the implementation does not normalize the operands.

**Fix:** Compare epoch milliseconds, not strings:

```js
const wmMs = readWatermark ? Date.parse(readWatermark) : null
// ...
if (a.from === 'me' && !a.read && wmMs != null && Date.parse(a.sentAt) <= wmMs) a.read = true
// watermark update:
setReadWatermark((prev) =>
  prev == null || Date.parse(readAt) > Date.parse(prev) ? readAt : prev,
)
```

## Warnings

### WR-01: Documented `?after=` reconnect catch-up is never invoked (dead path / unmet behavior)

**File:** `apps/client-pwa/src/lib/clientQueries.ts:962`, `apps/client-pwa/src/screens/ChatScreen.jsx:634`, `apps/client-pwa/src/lib/useClientMessagingWS.ts:14`
**Issue:** `useClientMessages(after?)` exposes the cursor and the hook header advertises
"REST catch-up on reconnect (DB-first)" with "`?after=` catch-up", but ChatScreen calls
`useClientMessages()` with no argument and the WS `onclose`/reconnect path does no catch-up at
all — it only resets/doubles backoff. The reconnect simply relies on the 30s `refetchInterval`
poll and on `new_message` invalidation. The advertised after-cursor catch-up is therefore a
dead code path; any messages that arrived during a disconnect are only picked up on the next
poll/new_message, not via the cursor. Either wire the catch-up (refetch with `after=lastSeenId`
on reconnect) or remove the `after` plumbing and the comments so the contract matches reality.
**Fix:** On WS `onopen` after a reconnect (delay > BASE_DELAY), invalidate/refetch messages; or
delete the unused `after` parameter and its doc claims.

### WR-02: Photo objectUrl revoked while still referenced (broken image / flicker + overlay)

**File:** `apps/client-pwa/src/screens/ChatScreen.jsx:920`, `937-945`, `1202`/`1399-1401`
**Issue:** `sendPhoto` creates `objectUrl` for the optimistic bubble, then in `finally`
unconditionally calls `URL.revokeObjectURL(objectUrl)`. On the success path the optimistic
message is removed (`setOptimistic(...filter)`) before `finally`, but the server refetch that
replaces it is async and may not have landed — for the window between optimistic-removal and
refetch-arrival there is no photo, then it pops in (flicker). Worse, the optimistic `<img>`
`src` is the object URL; if the user taps it (`onPhotoTap` → `setPhotoOverlay(objectUrl)`,
lines 545/1202/1399) before/around revoke, the full-screen overlay shows a revoked (blank)
blob. On the error path the bubble is also removed and revoked, which is fine, but the
success-path early-revoke is the defect.
**Fix:** Revoke the object URL only after the server message has actually replaced the
optimistic one (e.g. track the URL and revoke in the refetch/cleanup once `serverIds` contains
the confirmed id), or keep the optimistic bubble until the refetch lands and revoke in an
effect cleanup. At minimum do not revoke in `finally` on the success path.

### WR-03: Mark-read effect can self-trigger a mutation loop

**File:** `apps/client-pwa/src/screens/ChatScreen.jsx:874-880`
**Issue:**
```js
useEffect(() => {
  if (openIdRef.current != null && unreadCount > 0) { markReadM.mutate(); ui.setUnreadChat(0); }
}, [unreadCount])
```
`markReadM` `onSettled` invalidates the messages key → refetch. If the backend has not yet
flipped `readAt`/`unreadCount` to 0 for that fetch (eventual consistency, or a message arriving
between mutate and refetch), the refetched `unreadCount` is still > 0, the effect fires again,
and another `markReadM.mutate()` is issued — a PATCH storm bounded only by how fast the server
converges. There is no in-flight guard.
**Fix:** Guard on `markReadM.isPending` and/or only fire when `unreadCount` transitions from 0,
e.g. track the last marked count or check `!markReadM.isPending` before mutating.

### WR-04: `setUnreadChat` badge effect depends on `ui`, runs on every UI state change

**File:** `apps/client-pwa/src/screens/ChatScreen.jsx:767-769`
**Issue:**
```js
useEffect(() => { if (serverData) ui.setUnreadChat(serverData.unreadCount) }, [serverData, ui])
```
The `useUI()` value is rebuilt by `useMemo` whenever any of its ~30 dependencies change
(`UIContext.jsx:112-119`), so `ui` changes identity on every sheet open/close, push, etc. This
effect therefore re-runs on unrelated UI changes and re-pushes `setUnreadChat`. Combined with
CR-01 this is part of the reconnect cascade. While `setUnreadChat` to the same value won't
re-render, the effect churn is unnecessary and couples chat-badge updates to global UI state.
**Fix:** Depend only on the value: `useEffect(() => { if (serverData) ui.setUnreadChat(serverData.unreadCount) }, [serverData?.unreadCount])` (capture `ui.setUnreadChat` once, or pull the setter out of the memoized object). Setters from `useState` are stable and safe to omit.

### WR-05: WS reconnect path leaks the pending timer reference / no clear before reschedule

**File:** `apps/client-pwa/src/lib/useClientMessagingWS.ts:120-126`, `109-112`
**Issue:** `scheduleReconnect` assigns `reconnectTimer.current = setTimeout(...)` but never
clears a previously pending timer first, and the timer callback that runs `connect()` does not
null out `reconnectTimer.current`. If two `onclose` events race (e.g. an `onerror`→`close`
plus a server close), two timers can be scheduled and only the last is tracked in the ref;
the earlier one is orphaned and will still fire `connect()`, potentially opening a second
socket that escapes the single-socket invariant. Cleanup only clears the last ref.
**Fix:** Clear any existing timer at the top of `scheduleReconnect`, and reset
`reconnectTimer.current = null` inside the timeout callback before calling `connect()`:
```ts
function scheduleReconnect() {
  if (reconnectTimer.current !== null) clearTimeout(reconnectTimer.current)
  reconnectTimer.current = setTimeout(() => {
    reconnectTimer.current = null
    reconnectDelay.current = Math.min(reconnectDelay.current * 2, MAX_DELAY)
    connect()
  }, reconnectDelay.current)
}
```

### WR-06: `window.__chat*` bridge has no ownership guard — last-mounted-wins / stale clear

**File:** `apps/client-pwa/src/screens/ChatScreen.jsx:855-871`, `apps/client-pwa/src/App.jsx:224-231`
**Issue:** ChatScreen registers `window.__chatReadReceipt` / `window.__chatTyping` on mount and
sets them to `undefined` on cleanup. Because ChatScreen is route-mounted (lazy) and can be
unmounted/remounted on tab changes, and the App-level WS calls `window.__chatReadReceipt?.(...)`,
the contract depends on exactly one ChatScreen being mounted. If a transition double-mounts (or
React 18 StrictMode dev double-invoke), the cleanup of the unmounting instance can `undefined`
the handler the newly-mounted instance just installed, silently dropping read-receipt/typing
frames. The bridge also has no identity check (any code can overwrite it).
**Fix:** Capture-and-restore the previous handler in cleanup (only clear if still ours), or move
the read-receipt/typing state to a shared store/context the App WS writes to directly instead of
a global function bridge.

### WR-07: `crypto.randomUUID()` assumed available without guard (non-secure-context failure)

**File:** `apps/client-pwa/src/screens/ChatScreen.jsx:904`, `938`
**Issue:** Idempotency keys are generated with `crypto.randomUUID()`. `crypto.randomUUID` is
only defined in secure contexts (HTTPS/localhost). A PWA served over plain HTTP on a LAN IP for
device testing, or an older WebView, will throw `TypeError: crypto.randomUUID is not a function`
inside `sendTextMessage`/`sendPhoto`; the `catch` then shows "Не удалось отправить" and the user
can never send — a silent hard failure that looks like a backend error. Other PWA code paths
(e.g. checkout idempotency) should be checked for the same assumption.
**Fix:** Use a guarded UUID helper (`crypto.randomUUID?.() ?? fallbackUuidV4()`) shared across
the PWA, or document/enforce the secure-context requirement.

### WR-08: `serverData?.unreadCount ?? 0` badge ignores `locallyUnread`/mute, and `adminUnread` can desync

**File:** `apps/client-pwa/src/screens/ChatScreen.jsx:727`, `753`, `766-769`
**Issue:** The card badge uses `adminUnread = locallyUnread ? 1 : unreadCount`, but the TabBar
badge feed (`ui.setUnreadChat(serverData.unreadCount)`, line 768) always pushes the raw server
`unreadCount`, ignoring the local "Не прочитано" toggle and ignoring the optimistic `setUnreadChat(0)`
done in `openThread`. So immediately after opening the thread (which sets the tab badge to 0),
the next `serverData` reference (e.g. from the 30s poll, or any refetch where the server has not
yet flipped `readAt`) re-pushes the old `unreadCount`, making the tab badge flicker back to a
non-zero value while the thread is open. The card-level and tab-level unread counts are derived
from two different rules and can disagree.
**Fix:** Drive the tab badge from the same source of truth as the card (`adminUnread`) and skip
re-pushing when the thread is open: e.g. `ui.setUnreadChat(openIdRef.current != null ? 0 : adminUnread)`.

## Info

### IN-01: `closeThread` does not clear `optimistic` / `readWatermark` (stale carry-over)

**File:** `apps/client-pwa/src/screens/ChatScreen.jsx:816-825`
**Issue:** Closing and reopening the thread keeps any leftover `optimistic` entries and the
`readWatermark`. Pending-failed-then-reopened states could show stale optimistic bubbles until
the next refetch reconciles them. Low impact given dedup by `serverIds`, but worth resetting on
close for predictability.
**Fix:** Reset `setOptimistic([])` (or only the resolved ones) on thread close if appropriate.

### IN-02: Unread-divider relies on staff `read` flag whose semantics are ambiguous

**File:** `apps/client-pwa/src/screens/ChatScreen.jsx:800`, `625`
**Issue:** `openThread` computes the "Новые сообщения" divider from
`threadMessages.filter(m => m.from === 'them' && !m.read)`, where `read = m.readAt != null`
(line 625). For incoming (staff) messages, `readAt` semantics ("who read it") are not clearly
defined by the wire shape; if `readAt` on staff messages means the staff-read time rather than
the client-read time, the divider can be placed incorrectly. Confirm the backend contract for
`readAt` on `role: 'staff'` messages.
**Fix:** Document/verify the `readAt` meaning per role and adjust the divider predicate if needed.

### IN-03: `dangerouslySetInnerHTML` for icons — safe today, fragile pattern

**File:** `apps/client-pwa/src/screens/ChatScreen.jsx:454`
**Issue:** `Ico` injects `ICON[name]` via `dangerouslySetInnerHTML`. All `name` values come from
the in-file constant `ICON` map (no user data), so there is no XSS today. Flagged only as a
fragility note: if a future change ever lets `name`/icon content derive from server or user
input, this becomes an injection sink. Message bodies and attachment URLs are rendered through
JSX text/`src` (not innerHTML), which is correct.
**Fix:** Keep `ICON` strictly static, or render fixed SVG components instead of HTML strings.

### IN-04: `data-go`/document pointer handlers attached at `document` level

**File:** `apps/client-pwa/src/screens/ChatScreen.jsx:1014-1021`
**Issue:** The card-gesture handlers are added on `document` (`pointermove`/`up`/`cancel`). They
are correctly removed in cleanup, but because the effect deps include `toggleMute, openThread,
openSheet` (and `openThread` depends on `threadMessages`), the listeners are detached/reattached
frequently as messages change. Functionally fine, but a churn worth noting; consider stabilizing
`openThread` (it currently lists `threadMessages` in deps via the divider calc) so the
document-level listeners are installed once.
**Fix:** Compute the divider lazily inside `openThread` from a ref instead of depending on
`threadMessages`, so the gesture effect deps stay stable.

---

_Reviewed: 2026-06-08_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
