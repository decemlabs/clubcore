---
phase: 94-pwa-chatscreen-wiring
reviewed: 2026-06-08T08:21:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - apps/client-pwa/src/lib/clientQueries.ts
  - apps/client-pwa/src/lib/useClientMessagingWS.ts
  - apps/client-pwa/src/lib/uuid.ts
  - apps/client-pwa/src/data/index.js
  - apps/client-pwa/src/context/UIContext.jsx
  - apps/client-pwa/src/App.jsx
  - apps/client-pwa/src/screens/ChatScreen.jsx
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
status: clean
---

# Phase 94: Code Review Report (Iteration 2)

**Reviewed:** 2026-06-08T08:21:00Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** clean (no blockers; 2 minor WARNINGs + 3 INFO)

## Summary

Iteration-2 re-review of the PWA ChatScreen wiring after the prior pass found 2 BLOCKER + 8 WARNING, fixed across c90a21fa / dd6256b2 / a613956b / b152777a.

**Verdict: all previously-found blockers and the re-checked warnings are genuinely resolved, and the fixes introduced NO new blocker.** The 19 regression/unit tests for the WS hook and the read-tick comparison pass, and the changed TS files typecheck clean. Two minor residual WARNINGs and three INFO items remain — none block shipping.

### Confirmation of prior issues

- **CR-01 (WS reconnect churn / stale closures) — RESOLVED.** `useClientMessagingWS.ts:90,178` the connect effect depends only on `[enabled]`. Callbacks live in `cbRef` (`:87-88`), reassigned every render and read at dispatch time (`:110,125,127,129`), so the latest callback is always invoked without re-running the effect. Two dedicated regression tests confirm both halves: no socket reopen on callback-identity change (`useClientMessagingWS.test.ts:218-240`) and latest-callback dispatch after re-render (`:242-261`).
- **CR-02 (read-tick epoch-ms compare) — RESOLVED.** Every sentAt/readAt comparison uses `Date.parse`: the watermark base (`ChatScreen.jsx:741`), the per-message mark (`:744` `Date.parse(a.sentAt) <= wmMs`), and the monotonic watermark update (`:889-891` `Date.parse(readAt) > Date.parse(prev)`). No lexicographic ISO compare remains at any read-tick site. `ChatScreen.readtick.test.ts` pins the mixed-offset (`Z` vs `+03:00`) cases.
- **WR-01 (reconnect REST catch-up) — RESOLVED.** `onReconnect` fires only after `hasConnectedOnce` on a reopen, not the initial connect (`useClientMessagingWS.ts:95-112`); `App.jsx:232-238` invalidates the messages query in response. No double-fetch: the initial connect does not fire it, and the 30s `refetchInterval` poll (`clientQueries.ts:979`) is an independent fallback. Regression test `useClientMessagingWS.test.ts:289-319`.
- **WR-02 (objectURL revoke timing) — RESOLVED.** The success/error send paths deliberately do NOT revoke (`ChatScreen.jsx:1009-1018`). A dedicated collector effect revokes only URLs no longer referenced by either a pending optimistic message or the open overlay (`:915-927`), plus an unmount sweep (`:930-936`). No revoked-URL can be referenced by preview or full-screen overlay.
- **WR-05 (single reconnect timer) — RESOLVED.** `scheduleReconnect` clears any pending timer and nulls the ref before scheduling, and nulls the ref inside the fired callback (`useClientMessagingWS.ts:145-162`). Racing-close regression test confirms exactly one reconnect socket (`useClientMessagingWS.test.ts:264-286`).
- **Bridge-ownership / ref-dispatch regression sweep — CLEAN.** The `window.__chatReadReceipt` / `window.__chatTyping` bridge (`ChatScreen.jsx:877-910`) saves the previous handler and restores it on cleanup only when the current handler is still its own — correct guard against double-mount (StrictMode / tab churn) clobbering a newer instance's handler. Effect dep is `[setTypingFn]`, and `setTypingFn` is a stable `useCallback([])` (`:869-874`), so the bridge registers once. App-level WS singleton is gated on `status === 'authed'` (`App.jsx:217`). No dep-array or ownership regression found.

## Warnings

### WR-01: mark-read effect can repeat-PATCH under backend eventual-consistency lag

**File:** `apps/client-pwa/src/screens/ChatScreen.jsx:942-948`
**Issue:** The WR-03 fix correctly guards against *concurrent* PATCH with `!markReadM.isPending`, but it does not bound *repeated* PATCH. Flow: effect fires → `mutate()` → `isPending=true` (effect blocked) → `onSettled` invalidates `messages` → refetch. If the backend has not yet converged (read-receipt write lag / eventual consistency) the refetched `unreadCount` is still `> 0`; once `isPending` flips back to `false` the effect re-evaluates `[unreadCount, markReadM.isPending]` and fires another PATCH. This is a self-sustaining PATCH→invalidate→refetch→PATCH cycle that only terminates when the server finally returns `unreadCount === 0`. Concurrent storms are prevented, but a serial storm against a lagging backend is not.
**Fix:** Latch a mark-read per open-thread session so the PATCH fires at most once per open until a genuinely new unread arrives:
```js
const markedForOpenRef = useRef(false);
// reset in openThread(): markedForOpenRef.current = false;
useEffect(() => {
  if (openIdRef.current != null && unreadCount > 0 && !markReadM.isPending && !markedForOpenRef.current) {
    markedForOpenRef.current = true;
    markReadM.mutate();
    ui.setUnreadChat(0);
  }
}, [unreadCount, markReadM.isPending]);
```
This keeps the optimistic badge-clear while making the PATCH idempotent per open.

### WR-02: setState after await in send paths can run after unmount

**File:** `apps/client-pwa/src/screens/ChatScreen.jsx:967-978` (text) and `:1002-1018` (photo)
**Issue:** `sendTextMessage` / `sendPhoto` call `setOptimistic(...)` (and `toast(...)`) after `await ...mutateAsync(...)`. ChatScreen is `lazy`-routed and unmounts on tab switch; if the user navigates away while a send is in flight, the resolution/`catch` runs `setState` on an unmounted component. In React 18 this is a benign no-op (no crash), so this is a WARNING, not a blocker — but it produces console noise and the optimistic cleanup is silently lost. The objectURL is still safely reclaimed by the unmount sweep (`:930-936`), so there is no leak.
**Fix:** Guard with a mounted ref:
```js
const mountedRef = useRef(true);
useEffect(() => () => { mountedRef.current = false; }, []);
// then: if (mountedRef.current) setOptimistic(...);
```

## Info

### IN-01: hard-coded mock conversation id `'c2'` used as deep-link trigger

**File:** `apps/client-pwa/src/App.jsx:257,342`
**Issue:** `setTimeout(() => ui.setPendingChat('c2'), 360)` passes the legacy mock conv id `'c2'`. ChatScreen's deep-link effect only checks `initialConv` truthiness and always opens `ADMIN_CONV.id` (`ChatScreen.jsx:850-856`), so `'c2'` works only incidentally as a truthy flag. The literal is now meaningless (single real `admin` conversation) and is a latent trap if the deep-link effect ever starts honoring the passed id.
**Fix:** Pass a self-documenting truthy value (e.g. `ui.setPendingChat(true)` or `ADMIN_CONV.id`) and drop the stale `'c2'`.

### IN-02: `optimistic`/server dedup relies solely on post-resolve filter, not id match

**File:** `apps/client-pwa/src/screens/ChatScreen.jsx:752-754`
**Issue:** `serverIds.has(o.id)` can never be true — optimistic ids are `'opt-...'` / `'opt-photo-...'` while server ids are real UUIDs — so the `Set` filter at `:753` is effectively dead; dedup depends entirely on the explicit `setOptimistic(prev => prev.filter(...))` after `mutateAsync` resolves (`:974,1008`). This works, but leaves a brief window where the refetched server copy and the not-yet-removed optimistic copy can both render. Not a regression (pre-existing design) and not user-visible in practice, but the `serverIds` guard reads as defensive code that does nothing.
**Fix:** Remove the dead `serverIds` filter, or dedup on the idempotency key echoed back by the server so the server copy deterministically replaces the optimistic one.

### IN-03: `MessageRow` photo-body sentinel check is brittle

**File:** `apps/client-pwa/src/screens/ChatScreen.jsx:549`
**Issue:** `m.body && !m.body.startsWith('photo:')` carries forward a prototype `photo:` sentinel convention that no wired code path produces (real photo messages set `body: ''` at `:994`). Harmless near-dead guard, but it obscures intent.
**Fix:** Drop the `startsWith('photo:')` check; render `m.body` when present.

---

_Reviewed: 2026-06-08T08:21:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
