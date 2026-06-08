---
phase: 94-pwa-chatscreen-wiring
verified: 2026-06-08T05:04:50Z
status: human_needed
score: 3/3 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Pixel-perfect visual parity: render the ChatScreen in a real browser (dev login + reseed + hard-reload to clear stale SW cache); compare list view + thread view, animations (screen-push/pop, msg-in, typing-bounce, scene-in), gestures (swipe-to-mute 450ms long-press, pull-to-refresh, composer auto-grow, Enter-to-send, scroll-down FAB) against 94-REFERENCE-ChatScreen.jsx in both light and dark mode."
    expected: "ChatScreen is visually pixel-perfect; every animation plays; dark mode toggles correctly via MutationObserver; prototype chrome (.device/.island/.status-bar/.tabbar) is absent; unread divider, day separators, and empty state appear correctly."
    why_human: "Visual layout and animation fidelity cannot be verified by grep or tsc; requires a real browser render."
  - test: "Live WS round-trip: from the PWA send a text message → verify the staff-side Telegram bot receives it → reply from Telegram → verify the reply appears in the PWA thread in real time; confirm typing dots appear when staff is typing; confirm read ticks flip from single (✓) to double (✓✓) after staff reads; confirm Chat-tab unread badge updates from any screen (not just when ChatScreen is open)."
    expected: "Full bidirectional real-time messaging cycle works end-to-end; read-receipt watermark (sentAt <= readAt) correctly drives the ✓/✓✓ toggle; badge is live from the Home and Book tabs."
    why_human: "Requires a running backend (FastAPI + Redis + ARQ + Telegram bot) with dev credentials; cannot be verified statically."
  - test: "Photo flow on a real device: (a) tap camera button → device camera opens (capture=environment); tap gallery button → photo library opens (accept=image/jpeg,image/png,image/webp); (b) select a valid photo → optimistic preview bubble appears immediately; (c) observe upload + send completing (WS new_message → refetch replaces optimistic bubble with real attachment URL); (d) tap the real photo bubble → full-screen overlay opens (rgba(0,0,0,0.9) background, contain fit); tap anywhere → overlay closes; (e) verify client-side validation: file > 5 MB shows toast 'Файл слишком большой (макс. 5 МБ)'; non-image file shows 'Неподдерживаемый формат'."
    expected: "Photo picker opens correct picker type; optimistic preview shows immediately; server photo URL renders after round-trip; full-screen overlay works; validation toasts fire correctly."
    why_human: "Requires a real device with camera/gallery access and a running backend with /client/messages/attachments endpoint; file picker behavior differs by browser."
---

# Phase 94: PWA ChatScreen Wiring Verification Report

**Phase Goal:** ChatScreen graduated from the ComingSoon placeholder + de-listed from the D-71-09 ESLint zone; client chats with the gym in real time from the PWA — pixel-perfect port of the reference design — with read statuses, typing indicator, photos, and an unread badge.
**Verified:** 2026-06-08T05:04:50Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | ChatScreen renders thread history (client-right/staff-left bubbles, Europe/Moscow HH:MM) and is fully de-listed from D-71-09 (3 spots, `grep -c ChatScreen eslint.config.js` returns 0, imports via @/data) | ✓ VERIFIED | `grep -c ChatScreen eslint.config.js` = 0 confirmed; `grep -c ReferralSheet` = 3 (regression guard passes); `ChatScreen.jsx` line 27 imports `from '@/data'`; `adaptMessage()` uses `Intl.DateTimeFormat('ru-RU', { timeZone: 'Europe/Moscow' })`; file is 1405 lines (well above 700 min); `from 'me'`/`from 'them'` bubble mapping verified |
| 2 | The Chat-tab unread badge reflects the real unreadCount in real time via WS, with a 30s React Query poll fallback when WS disconnected | ✓ VERIFIED | `useClientMessages` at line 979 of `clientQueries.ts` has `refetchInterval: 30_000` (AND `staleTime: 30_000`); test `clientQueries.messaging.test.ts` line 123 asserts `refetchInterval === 30_000` (regression guard); `App.jsx` line 217-232 mounts `useClientMessagingWS` gated on `status === 'authed'` calling `qc.invalidateQueries` on `new_message`; `UIContext.jsx` line 29 has `const [unreadChat, setUnreadChat] = useState(0)`; `App.jsx` line 478 has `ui.unreadChat > 99 ? '99+' : (ui.unreadChat || 0)` (99+ cap); `ChatScreen.jsx` line 768 has `ui.setUnreadChat(serverData.unreadCount)` in effect |
| 3 | Client can pick a photo (gallery/camera), see a preview thumbnail in the thread, send it, and view previously-sent photos full-screen on tap | ✓ VERIFIED | `ChatScreen.jsx` line 1225: `<input ref={cameraInputRef} type="file" accept="image/*" capture="environment" ...>`; line 1226: `<input ref={galleryInputRef} type="file" accept="image/jpeg,image/png,image/webp" ...>`; lines 913-946: two-step upload→send with `URL.createObjectURL` optimistic preview + `URL.revokeObjectURL` after real message lands + `useUploadAttachment().mutateAsync` + `useSendMessage().mutateAsync({attachmentId, idempotencyKey: crypto.randomUUID()})`; rollback on error; `photo-overlay` CSS at lines 419-423: `position: fixed; inset: 0; background: rgba(0,0,0,0.9); z-index: 200; display: flex; align-items: center; justify-content: center`; lines 1398-1402: overlay rendered on tap with close-on-click |

**Score:** 3/3 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/client-pwa/src/lib/clientQueries.ts` | 4 messaging hooks + interfaces + messages key factory | ✓ VERIFIED | Lines 921-1067: `MessageAttachmentItem`, `MessageItem`, `MessageListData`, `AttachmentUploadResult` interfaces; `useClientMessages` (staleTime+refetchInterval 30_000), `useSendMessage` (Idempotency-Key header, onSettled invalidation), `useUploadAttachment` (FormData, no Content-Type), `useMarkMessagesRead` (PATCH, onSettled invalidation); key factory `messages(after?)` at line 46 |
| `apps/client-pwa/src/lib/useClientMessagingWS.ts` | App-level WS hook with frame dispatch + capped backoff reconnect | ✓ VERIFIED | 143 lines; `new WebSocket` at line 82; `BASE_DELAY=1_000`, `MAX_DELAY=30_000`; `new_message`/`read_receipt`/`typing`/`ping` dispatch; destroyed-flag teardown on cleanup; `ws://`/`wss://` per `location.protocol` |
| `apps/client-pwa/src/data/index.js` | Barrel re-export of the 4 messaging hooks | ✓ VERIFIED | Lines 67-71: `useClientMessages`, `useSendMessage`, `useUploadAttachment`, `useMarkMessagesRead` exported under `// Phase-94 PWA-01: messaging hooks` comment |
| `apps/client-pwa/src/context/UIContext.jsx` | `unreadChat` / `setUnreadChat` state on UI context | ✓ VERIFIED | Line 29: `const [unreadChat, setUnreadChat] = useState(0)`; line 93-94: exposed in `value` useMemo with comment; line 118: `unreadChat` in dependency array |
| `apps/client-pwa/src/App.jsx` | App-level WS mount + TabBar unreadChat badge (99+ cap) | ✓ VERIFIED | Line 19-20: imports `useClientMessagingWS` and `clientPortalKeys`; lines 217-232: WS hook called gated on `status === 'authed'`; line 478: TabBar badge with 99+ cap |
| `apps/client-pwa/eslint.config.js` | D-71-09 zone with ChatScreen removed from all 3 spots | ✓ VERIFIED | `grep -c ChatScreen eslint.config.js` = 0; graduation note added at line 26-29 mirroring Phase 86/87/88 style; `ReferralSheet` retained in all 3 spots (grep count = 3) |
| `apps/client-pwa/src/screens/ChatScreen.jsx` | Pixel-perfect ported screen wired to messaging hooks + WS bridge + photo flow | ✓ VERIFIED | 1405 lines; `from '@/data'` at line 27; scoped `.chat-root` CSS; `ReadTick` component (single ✓ = `var(--text-3)`, double ✓✓ = `var(--accent-deep)`); `typing-dots` bubble; `__chatReadReceipt`/`__chatTyping` bridge registered/cleared on mount/unmount; `adaptMessage()` with `Europe/Moscow` timestamps; `setUnreadChat` called in effect on query resolve and on mark-read |
| `apps/client-pwa/src/screens/ChatScreen.delist.test.ts` | Assertion that D-71-09 grep returns 0 for ChatScreen | ✓ VERIFIED | 26 lines; reads `eslint.config.js` via `node:fs`; asserts 0 occurrences of `ChatScreen` AND `ReferralSheet` retained; runs as part of 210-test suite |
| `apps/client-pwa/src/lib/clientQueries.messaging.test.ts` | Hooks test including refetchInterval:30_000 regression guard | ✓ VERIFIED | Line 115-123: asserts `opts.refetchInterval === 30_000`; 17 tests covering key factory, method+path, send body, Idempotency-Key, FormData field, onSettled invalidation |
| `apps/client-pwa/src/lib/useClientMessagingWS.test.ts` | WS hook: URL, frame dispatch, enabled gate, unmount close, backoff | ✓ VERIFIED | 11 tests covering all behaviors listed in plan; uses `FakeWebSocket` on `globalThis`; `renderHook` from `@testing-library/react` |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `clientQueries.ts` | `/api/v1/client/messages` (GET/POST/PATCH) | `clientRequest` cast | ✓ WIRED | Lines 973, 1008, 1060: correct method + path strings; `after` query param passed only when defined |
| `App.jsx` | `useClientMessagingWS` | hook called in `App()` body gated on `status === 'authed'` | ✓ WIRED | Lines 217-232: correct gating + callbacks |
| `App.jsx` | TabBar `unreadChat` prop | `ui.unreadChat > 99 ? '99+' : (ui.unreadChat || 0)` | ✓ WIRED | Line 478 |
| `ChatScreen.jsx` | `@/data` messaging hooks | `import { useClientMessages, useSendMessage, useUploadAttachment, useMarkMessagesRead } from '@/data'` | ✓ WIRED | Lines 22-27 |
| `ChatScreen.jsx` | `ui.setUnreadChat` | Effect on `serverData` resolve + mark-read calls | ✓ WIRED | Lines 768, 808, 877 |
| `ChatScreen.jsx` | `window.__chatReadReceipt` / `window.__chatTyping` | useEffect register/clear on mount/unmount | ✓ WIRED | Lines 856-870; bridge resets to `undefined` on cleanup |
| `App.jsx` | `window.__chatReadReceipt` / `window.__chatTyping` | Optional-chain calls in WS callbacks | ✓ WIRED | Lines 225-231: `window.__chatReadReceipt?.(readAt)`, `window.__chatTyping?.()` |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `ChatScreen.jsx` | `serverData` (from `useClientMessages`) | `useClientMessages()` → `clientRequest('get', '/api/v1/client/messages')` → unwraps `res.data` | Yes — real REST fetch with credentials, `refetchInterval: 30_000` | ✓ FLOWING |
| `ChatScreen.jsx` | `ui.unreadChat` badge | `ui.setUnreadChat(serverData.unreadCount)` in effect; also updated via WS invalidation path | Yes — `unreadCount` from backend response | ✓ FLOWING |
| `ChatScreen.jsx` | `readWatermark` (WS read-receipt) | `window.__chatReadReceipt` → `setReadWatermark` | Yes — real WS frame; applied over REST `readAt` | ✓ FLOWING |
| `ChatScreen.jsx` | `optimistic` photo bubble | `URL.createObjectURL(file)` → replaced by `attachment.url` from server response after upload | Real `attachment.url` replaces objectURL on WS new_message refetch | ✓ FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `grep -c ChatScreen eslint.config.js` returns 0 | `grep -c ChatScreen apps/client-pwa/eslint.config.js` | 0 | ✓ PASS |
| `grep -c ReferralSheet eslint.config.js` returns 3 (regression guard) | `grep -c ReferralSheet apps/client-pwa/eslint.config.js` | 3 | ✓ PASS |
| TypeScript type check clean | `pnpm exec tsc -b --noEmit` (from `apps/client-pwa`) | exit 0, no output | ✓ PASS |
| ESLint clean | `pnpm lint` (from `apps/client-pwa`) | exit 0, no output | ✓ PASS |
| Full test suite passes | `pnpm test` (from `apps/client-pwa`) | 210/210 tests, 29 files — PASS | ✓ PASS |
| ChatScreen imports via `@/data` | `grep -q "from '@/data'" src/screens/ChatScreen.jsx` | found at line 27 | ✓ PASS |
| `refetchInterval:30_000` on `useClientMessages` | `grep -n "refetchInterval: 30_000" src/lib/clientQueries.ts` | line 979 | ✓ PASS |
| `setUnreadChat` wired in ChatScreen | `grep -q "setUnreadChat" src/screens/ChatScreen.jsx` | lines 768, 808, 877 | ✓ PASS |
| `Europe/Moscow` timezone used | `grep -c "Europe/Moscow" src/screens/ChatScreen.jsx` | 3 occurrences | ✓ PASS |
| `.chat-root` scoped CSS | `grep -q "chat-root" src/screens/ChatScreen.jsx` | found; CSS wrapped under `.chat-root` | ✓ PASS |
| `useUploadAttachment` in ChatScreen | `grep -q "useUploadAttachment" src/screens/ChatScreen.jsx` | found at line 25 and 636 | ✓ PASS |
| Camera capture input | `grep -q 'capture="environment"' src/screens/ChatScreen.jsx` | found at line 1225 | ✓ PASS |
| `photoOverlay` state and overlay render | `grep -c "photoOverlay" src/screens/ChatScreen.jsx` | 7 occurrences (state, setter, overlay div) | ✓ PASS |

---

### Probe Execution

Step 7c: SKIPPED — no `scripts/*/tests/probe-*.sh` declared in this phase's plans or summaries. This is a frontend-only phase; behavioral spot-checks (Step 7b) cover the runnable gates.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|------------|------------|-------------|--------|----------|
| PWA-01 | 94-01, 94-02 | ChatScreen connected to real API + WS; graduated from D-71-09 placeholder zone (3 spots) + imports via `@/data` | ✓ SATISFIED | `grep -c ChatScreen eslint.config.js` = 0; `from '@/data'` at line 27; all 4 hooks wired; 1405-line implementation |
| PWA-02 | 94-01 | Unread badge in PWA (tab/icon) reflects real `unreadCount` | ✓ SATISFIED | `refetchInterval: 30_000` on `useClientMessages`; WS `new_message` → `invalidateQueries`; `ui.setUnreadChat(serverData.unreadCount)` in ChatScreen effect; TabBar badge with 99+ cap |
| PWA-03 | 94-02 | Photo picker on send + attachment viewing (preview/full) in thread | ✓ SATISFIED | Camera + gallery hidden inputs; 5MB/type validation; two-step `useUploadAttachment` + `useSendMessage`; objectURL optimistic bubble; `URL.revokeObjectURL` after real message; full-screen `photoOverlay` overlay |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `ChatScreen.jsx` | 484 | `PHOTO_PRESETS` constant retained but unused; `PhotoBubble` component defined but not called | INFO | Intentional hide-for-future per 94-CONTEXT "Hidden for future" — documented in SUMMARY as known non-blocking stub; `// eslint-disable` comments present; not data stubs |
| `ChatScreen.jsx` | Various | `MessageRow` system/cancel branches retained but unreachable by wired data | INFO | Intentional hide-for-future; real data never produces `system` or `cancel` kind |
| `App.jsx` | 236-238 | `// eslint-disable-next-line react-hooks/exhaustive-deps` on the push-kind effect | INFO | Pre-existing pattern in this file; not introduced by Phase 94 |

No `TBD`, `FIXME`, or `XXX` debt markers found in Phase-94-modified files.

---

### Human Verification Required

All automated gates are green (tsc, lint, 210 tests, grep gates). The following items require browser + backend verification and are explicitly deferred to HUMAN-UAT per 94-02-PLAN.md `<human_verification>` block:

#### 1. Pixel-Perfect Visual Parity

**Test:** Boot the dev stack (docker compose + backend + client-pwa dev server); dev login + reseed; hard-reload / bump SW cache (`/api/*` is network-only so stale SW masks new code). Open the Chat tab. Compare list view and thread view against `94-REFERENCE-ChatScreen.jsx` in both light and dark mode. Verify: all animations (screen-push/pop, msg-in, typing-bounce, scene-in, spot-float, ptr-spin, sheet slide, toast, fade-up), gestures (swipe-to-mute, 450ms long-press, pull-to-refresh, composer auto-grow, Enter-to-send, scroll-down FAB), prototype chrome absent (no `.device`, `.island`, `.status-bar`, `.home-indicator`, prototype `.tabbar`), empty state and unread divider render correctly.
**Expected:** Visual output matches reference pixel-perfectly; dark mode follows the PWA's existing `data-theme` attribute via MutationObserver (not `body.dark`).
**Why human:** Visual layout and animation fidelity cannot be verified by grep, tsc, or unit tests.

#### 2. Live WS Round-Trip + Read Ticks + Typing + Badge from Any Screen

**Test:** With the running stack, send a text message from the PWA; verify it appears in the staff Telegram bot. Reply from Telegram. Verify: reply arrives in the PWA thread in real time (no manual refresh); typing dots appear when staff starts typing and auto-dismiss after 5s of inactivity; read ticks flip from single (✓, `var(--text-3)`) to double (✓✓, `var(--accent-deep)`) after staff reads; navigate to Home or Book tab and then receive a new message — Chat-tab badge increments without the thread being open.
**Expected:** Full bidirectional real-time cycle works. WS read-receipt watermark (`sentAt <= readAt`) correctly drives ✓ → ✓✓ without rendering "прочитано в HH:MM". Badge updates from any tab.
**Why human:** Requires running backend (FastAPI + Redis + ARQ + Telegram bot) with dev credentials. WS round-trip timing and live badge update cannot be simulated in unit tests.

#### 3. Photo Picker (Camera + Gallery) + Send + Full-Screen View

**Test:** In the PWA thread, tap the attach button: (a) tap "Камера" — device camera opens (`capture="environment"`); (b) tap "Фото из галереи" — photo library opens (JPEG/PNG/WebP filter). Select a valid photo: optimistic preview bubble appears immediately with objectURL. Observe upload + send completing (WS new_message → refetch replaces optimistic bubble with real `attachment.url`). Tap the photo bubble → full-screen overlay opens (dark background, contain fit). Tap anywhere → overlay closes. Test validation: attempt to send a file > 5 MB → toast "Файл слишком большой (макс. 5 МБ)"; attempt non-image file → "Неподдерживаемый формат".
**Expected:** All picker, upload, preview, and overlay behaviors work correctly on a real device. Server re-validates by magic bytes (Phase 92) so client check is UX-only.
**Why human:** File picker behavior is device-dependent. Camera requires real hardware. Upload round-trip requires a running backend with `/client/messages/attachments`.

---

### Gaps Summary

No automated-gate gaps found. All three roadmap success criteria are fully verified in the codebase:

1. **SC-1 (ChatScreen de-listed + rendered via @/data):** `grep -c ChatScreen eslint.config.js` = 0, ReferralSheet retained (3 spots). `ChatScreen.jsx` (1405 lines) imports `from '@/data'`, uses `Europe/Moscow` HH:MM timestamps, scoped `.chat-root` CSS, `ReadTick` component, typed bridge registration. All 5 commits documented in SUMMARY.md confirmed present in git log (a57331ac, 83fc8666, 2ffd33ff, 6625f909, 92e93b84).

2. **SC-2 (30s poll fallback + WS unread badge):** `refetchInterval: 30_000` present at `clientQueries.ts:979`; test assertion at `clientQueries.messaging.test.ts:123` is the regression guard; WS singleton in `App.jsx` invalidates on `new_message`; `ui.setUnreadChat` wired in ChatScreen; 99+ cap in TabBar.

3. **SC-3 (Photo picker + preview + full-screen):** Camera input with `capture="environment"`, gallery input, two-step upload→send with `crypto.randomUUID()` idempotency keys, `URL.createObjectURL` optimistic preview, `URL.revokeObjectURL` cleanup, `photoOverlay` state + fixed overlay CSS.

The `human_needed` status reflects 3 human-UAT items (visual parity, live WS round-trip, photo flow on device) explicitly deferred in the plan — not any automated failure.

---

_Verified: 2026-06-08T05:04:50Z_
_Verifier: Claude (gsd-verifier)_
