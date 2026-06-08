---
phase: 94-pwa-chatscreen-wiring
plan: "02"
subsystem: client-pwa
tags: [messaging, chat, pixel-perfect-port, websocket, attachments, eslint-graduation, pwa]
dependency_graph:
  requires:
    - "94-01: useClientMessages / useSendMessage / useUploadAttachment / useMarkMessagesRead (@/data)"
    - "94-01: UIContext.unreadChat / setUnreadChat"
    - "94-01: App-level WS singleton + window.__chatReadReceipt / window.__chatTyping bridge"
  provides:
    - "Rendered pixel-perfect ChatScreen (list + thread) wired to the single «Администрация / Мой зал» thread"
    - "ChatScreen graduated from the D-71-09 placeholder ESLint zone (grep-returns-0)"
    - "Photo picker (camera + gallery) + two-step upload->send + full-screen overlay (PWA-03)"
    - "Read-tick watermark, typing dots, unread-badge feed, day separators, unread divider, PTR refetch"
  affects:
    - apps/client-pwa/eslint.config.js
    - apps/client-pwa/src/screens/ChatScreen.jsx
tech_stack:
  added: []
  patterns:
    - "Scoped const CSS string under .chat-root / .chat-root.dark (NotificationsSheet analog)"
    - "Theme follows PWA data-theme via MutationObserver + reactive tweaks prop (NOT prototype Tweaks)"
    - "Optimistic send/upload with rollback; WS new_message -> refetch replaces optimistic message"
    - "WS read-receipt watermark (own sentAt <= readAt -> double-check) NOT a read clock"
    - "window.__chat* bridge register/clear on mount/unmount"
key_files:
  created:
    - apps/client-pwa/src/screens/ChatScreen.delist.test.ts
  modified:
    - apps/client-pwa/eslint.config.js
    - apps/client-pwa/src/screens/ChatScreen.jsx
decisions:
  - "Tasks 2 and 3 committed as ONE atomic commit (92e93b84) — they live in a single file and the Task-3 photo seam was filled in the same write; an artificial diff split was avoided. The full verify gate (tsc + lint + 210 tests + build) was run before committing."
  - "eslint comment blocks reworded to avoid the literal token 'ChatScreen' so the grep-returns-0 gate passes (the comment 'the chat screen graduated' is used instead)."
  - "isEmptyConv day-separator/divider logic operates on combined server+optimistic messages; optimistic entries are dropped once a server message lands (WS invalidation -> refetch)."
  - "mute/archive/delete/mark-unread operate on local UI state only (no v2.5 backend) exactly as the prototype does; archive/delete remove the single conv locally + toast."
metrics:
  duration: "~12 minutes"
  completed_date: "2026-06-08"
  tasks_completed: 3
  tasks_total: 3
  files_created: 1
  files_modified: 2
---

# Phase 94 Plan 02: PWA ChatScreen Pixel-Perfect Port Summary

**One-liner:** Pixel-perfect port of the 1398-line reference ChatScreen into `apps/client-pwa`, graduated out of the D-71-09 ESLint zone and wired to the Plan 94-01 messaging REST + WS + attachment layer (text, real photos, read ticks, typing, unread badge), with prototype chrome stripped and future-mock features retained-but-hidden.

## Objective

Replace the `ComingSoon` placeholder with the reference chat UI transferred verbatim (CSS, icons, components, animations, gestures), swapping only the data layer (mock → real), stripping prototype chrome, scoping the CSS under `.chat-root`, hiding future-mock features, and de-listing from the D-71-09 placeholder zone. Delivers PWA-01 (rendered, de-listed, `@/data` import) and PWA-03 (photo picker + full-screen view).

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | De-list ChatScreen from D-71-09 + assertion test | 6625f909 | eslint.config.js, ChatScreen.delist.test.ts |
| 2 | Port pixel-perfect screen — scoped CSS, list+thread, data wiring, read ticks, typing, unread | 92e93b84 | ChatScreen.jsx |
| 3 | Photo picker (camera+gallery) + two-step upload→send + full-screen overlay (PWA-03) | 92e93b84 | ChatScreen.jsx |

> Tasks 2 and 3 share a single file; both were written together and committed atomically as `92e93b84` after the full verify gate passed. See Deviations.

## Artifacts Delivered

### 1. eslint.config.js — D-71-09 graduation (PWA-01)

ChatScreen removed from all 3 spots: the ignore-negation line, the `files:` target block, and the `no-restricted-paths` zone `target`. `ReferralSheet` retained in all 3 (regression guard). A Phase-94 graduation note added mirroring the Phase 86/87/88 style. `grep -c ChatScreen eslint.config.js` → **0**; `grep -c ReferralSheet` → **3**.

### 2. ChatScreen.delist.test.ts — grep-returns-0 gate

Reads `eslint.config.js` via `node:fs` from `process.cwd()`; asserts zero `ChatScreen` substrings AND `ReferralSheet` retained.

### 3. ChatScreen.jsx — pixel-perfect port (1405 lines)

**Verbatim transfer:** `const CSS`, the `ICON` map, and `Ico` / `Avatar` / `ReadTick` / `PhotoBubble` / `MessageRow` / `ConvCard` components, list+thread markup, all animations (screen-push/pop, msg-in, typing-bounce, scene-in, spot-float, ptr-spin, sheet slide, toast, fade-up) and gestures (swipe-to-mute, 450ms long-press, pull-to-refresh, composer auto-grow, Enter-to-send, scroll-down FAB).

**CSS scoping:** `:root` → `.chat-root`; `body.dark` → `.chat-root.dark`; `html, body` globals stripped (font/bg set on `.chat-root`). Chrome selectors stripped entirely. Keyframes namespaced `chat-*` to avoid global collisions.

**Chrome stripped:** `.device/.island/.status-bar/.home-indicator/.stage`, the prototype `.tabbar`, the `Tweaks` panel + `TWEAK_DEFAULTS/ACCENTS/applyAccent/applyTweaks/setTweak`, the `window.parent.postMessage` edit-mode protocol, the `data-go/data-toast` document click handler, and the `myzal_theme` localStorage/storage sync.

**Single real conversation:** `ADMIN_CONV` («Администрация / Мой зал», `isOfficial`, `МЗ`) hydrated from backend `unreadCount` + last-message preview (`📷 Фото` for photos). `c2/c3/c4` removed.

**Hide-for-future (retained, not rendered):** voice (mic icon shown, tap no-ops), document/voice attach rows (attach sheet shows only Камера + Фото из галереи), `PHOTO_PRESETS`/`PhotoBubble` (kept, eslint-disabled unused), `MessageRow` system/cancel branches (kept, unreachable), bot autoreply removed, quick-reply chips (`showQuick = false`).

**Data wiring:** `useClientMessages` drives loading skeleton / error (`isError && !isFetching` → "Потяните вниз, чтобы повторить.") / content. `adaptMessage` maps backend → reference shape (`role` → `from`, `Europe/Moscow` HH:MM `time`, `readAt != null` → `read`, `attachment` → `kind:'photo'`, keeps `sentAt`). Day separators via Europe/Moscow day-key (Сегодня/Вчера/day-month). Unread divider above first unread staff message on open. `ui.setUnreadChat(unreadCount)` in an effect on query resolve (PWA-02 badge feed). Send = optimistic client bubble + `useSendMessage` with fresh `crypto.randomUUID()` idempotency key + rollback/toast on error. Read ticks: `readAt != null` plus WS watermark (own `sentAt <= readAt` → ✓✓), never rendered as "прочитано в HH:MM". Typing: `window.__chatTyping` → dots + 5s auto-dismiss. Mark-read: `useMarkMessagesRead().mutate()` on open + inbound-while-open, optimistic `setUnreadChat(0)`. WS bridge registered/cleared on mount/unmount. PTR → `messagesQuery.refetch().finally(toast('Обновлено'))`. mute/archive/delete/mark-unread = local UI state + toast.

### 4. PWA-03 — photo flow

Hidden camera (`accept="image/*" capture="environment"`) + gallery (`accept="image/jpeg,image/png,image/webp"`) inputs. Attach rows trigger `input.click()`. Client-side validation: type in jpeg/png/webp else "Неподдерживаемый формат"; size ≤ 5 MB else "Файл слишком большой (макс. 5 МБ)". Two-step: optimistic objectURL preview bubble → `useUploadAttachment` → `useSendMessage({attachmentId})` → WS refetch replaces optimistic → `URL.revokeObjectURL`. Real photo bubble renders `<img src={attachment.url}>` (220×140, objectFit cover, padding 4). Tap → fixed full-screen `photoOverlay` (`rgba(0,0,0,0.9)`, zIndex 200, contain); tap anywhere closes.

## Verification Gates

- `grep -c ChatScreen eslint.config.js` → **0**; `ReferralSheet` retained — PASS
- `pnpm exec tsc -b --noEmit` — clean (EXIT 0)
- `pnpm lint` — clean (EXIT 0)
- `pnpm vitest run` — **210/210 tests, 29 files** (incl. delist test) — PASS
- `pnpm build` — production build succeeds; `ChatScreen-*.js` chunk emitted (43.83 kB / gzip 12.22 kB)
- Grep contract: `from '@/data'` ✓, `setUnreadChat` ✓, `Europe/Moscow` ✓, `chat-root` ✓, `useUploadAttachment` ✓, `capture="environment"` ✓, `photoOverlay` ✓

## Deviations from Plan

### Process note

**1. Tasks 2 and 3 committed together (atomic).** The plan suggested running the verify gate after Task 2 before Task 3. Both tasks edit the same file and the Task-3 photo seam (`<img>` bubble, file inputs, overlay) was filled in the same write. The full gate (tsc + lint + 210 tests + build) was run BEFORE committing, satisfying the "catch regressions early" intent. Committed as `92e93b84`. No artificial diff split was fabricated.

### Auto-fixed Issues

**2. [Rule 3 - Blocking] grep-returns-0 gate vs comment text.** The Phase-94 graduation comment initially contained the literal word "ChatScreen", making `grep -c ChatScreen` return 2 instead of 0. Reworded the two comment blocks to "the chat screen graduated" so the gate passes while preserving the graduation-note intent.
- **Files modified:** apps/client-pwa/eslint.config.js
- **Commit:** 6625f909

### Environment note (non-code)

**3. Claude tmp filesystem ENOSPC.** Early `Bash` calls failed with `ENOSPC` on the harness temp dir; mitigated by keeping command output compact. No code impact; main disk had ample space.

## Known Stubs

None that block the plan goal. `PHOTO_PRESETS` / `PhotoBubble` are intentionally retained-but-unused (hide-for-future per CONTEXT D-3); `MessageRow` system/cancel branches are intentionally unreachable by wired data. These are documented hide-for-future code, not data stubs — they will be re-enabled when backend support lands (per 94-CONTEXT "Deferred Ideas").

## Threat Flags

None. No new network surface beyond the Plan 94-01 hooks; photo `<img src>` uses only the server-returned `attachment.url` (T-94-06 mitigation), the overlay shows only the already-fetched URL (T-94-07), per-send `crypto.randomUUID()` idempotency keys dedupe double-send (T-94-08), client-side file validation is UX-only with authoritative server-side magic-byte validation (T-94-05), and no new packages were installed (T-94-SC).

## Human Verification (deferred HUMAN-UAT — does NOT gate automated checks)

Browser/live-WS/pixel-perfect parity must be verified on a real device/browser:
- Pixel-perfect parity vs `94-REFERENCE-ChatScreen.jsx` (list + thread, animations, gestures, empty/typing states) in light + dark
- Live WS round-trip: PWA text → staff Telegram reply arrives; typing dots; read ticks flip to ✓✓; Chat-tab badge updates real-time
- Photo: pick from gallery + camera, preview, send, tap to view full-screen
- Setup: dev login + reseed; hard-reload / bump SW cache (stale SW masks new code; `/api/*` is network-only); dev proxy `/api` → localhost:8000

## Self-Check: PASSED

- [x] `apps/client-pwa/src/screens/ChatScreen.jsx` — exists, contains `from '@/data'`, `chat-root`, `useUploadAttachment`, `photoOverlay`
- [x] `apps/client-pwa/src/screens/ChatScreen.delist.test.ts` — exists, contains `ChatScreen`
- [x] `apps/client-pwa/eslint.config.js` — exists, `grep -c ChatScreen` = 0, `ReferralSheet` retained
- [x] Commit 6625f909 (Task 1) — present in git log
- [x] Commit 92e93b84 (Tasks 2+3) — present in git log
