---
status: partial
phase: 94-pwa-chatscreen-wiring
source: [94-VERIFICATION.md]
started: 2026-06-08
updated: 2026-06-08
browser_verified: 2026-06-08 (Claude, chrome-devtools, localhost:5174 + docker stack)
---

## Current Test

[browser-verified 2026-06-08 — 2 blocker bugs found + fixed during verification (28c53de7 .sheet collision, 865d412d dev WS connectivity); 1 follow-up logged (typing render → v2.6)]

## Tests

### 1. Pixel-perfect visual parity (vs 94-REFERENCE-ChatScreen.jsx)
expected: The ported ChatScreen looks пиксель-в-пiксель like the reference — list cards, bubbles, composer, animations, gestures, empty states, day separators, unread divider — light theme. No layout/spacing/typography/color drift.
result: PASSED (after fix 28c53de7). Initially BLANK — the `.sheet` class collided with the PWA's global `styles.css .sheet { animation: sheet-in both }`, pinning the closed action sheets over the whole chat. After the `animation:none` fix: list view (header, search, Все·1/Новые segmented, «Администрация / Мой зал» card with green ✓ verified badge, footer hint), thread view (МЗ avatar + online dot + «✓ верифицирован», client-right green bubbles / staff-left white bubbles, Europe/Moscow HH:MM timestamps, day separator, branded "spot" empty-state illustration, composer) all render pixel-perfect. Dark theme not exercised (light only).

### 2. Live WS round-trip (PWA ↔ backend ↔ Telegram)
expected: WS delivers staff messages + read receipts + typing live; unread badge updates; 30s poll fallback when WS down.
result: PARTIAL. WS now connects (after fix 865d412d — was silently failing in dev). Verified live over WS: `new_message` delivery (staff bubble appeared without reload), `read_receipt` ✓→✓✓ flip, unread badge (TabBar "Чат · 1 непрочитанных" + card badge), unread divider "НОВЫЕ СООБЩЕНИЯ", mark-read-on-open (badge clears). Text send works (optimistic + REST persist). **Typing indicator: NOT rendered** — WS frame delivered + bridge handler fires (handlerCalls=1) but `setTyping(true)` doesn't surface the dots (see Gaps → v2.6 follow-up). Full Telegram leg (staff replies FROM Telegram) NOT exercised — staff reply was simulated server-side via record_staff_message (STAFF_TELEGRAM_CHAT_ID unset locally → bridge no-op); remains operator-pending.

### 3. Photo flow
expected: gallery/camera pickers (image/*, ≤5MB), upload → send → real image bubble → full-screen on tap.
result: PASSED. Attach sheet shows only Камера + Фото из галереи (Документ/Голосовое correctly hidden per reconciliation). Camera input `image/*` capture=environment; gallery input `image/jpeg,image/png,image/webp` (matches backend allowlist). Uploaded a test PNG → real image bubble rendered from the authenticated IDOR-safe serve endpoint (`/api/v1/client/messages/attachments/{id}`, img loaded naturalWidth>0) → tap opened the full-screen overlay (fixed, z-index 200, rgba(0,0,0,0.9)). Not tested on a physical device / real camera; oversized-reject not exercised.

## Setup notes
- Dev login + reseed; hard-reload / bump SW cache (stale service worker can mask new code — see client-pwa-browser-verify gotchas).
- Dev proxy `/api` → localhost:8000; backend stack (`docker compose up postgres redis`) + ARQ worker + Telegram bot for the WS/Telegram round-trip.

## Summary

total: 3
passed: 2
issues: 1
pending: 0
skipped: 0
blocked: 0
notes: 2 blocker bugs found + fixed in-browser (28c53de7, 865d412d); 1 follow-up (typing render → v2.6); dark theme + physical-device camera + full Telegram leg not exercised.

## Gaps

1. **Typing indicator does not render (→ v2.6).** WS `typing` frame is delivered and the `window.__chatTyping` bridge handler fires (`handlerCalls=1`), but `setTypingFn(true) → setTyping(true)` doesn't surface the dots / «печатает…» in the open thread (single instance, render code correct on inspection). Likely the `window.__chat*` bridge updates a non-rendering path. Dormant in v2.5 (RCPT-02 producer is v2.6-deferred — nothing emits typing frames in prod yet); read-receipt liveness is masked by the data/poll path so functionally fine. Needs a `/gsd:debug` session with React DevTools when the v2.6 typing producer lands.
2. Not exercised: dark theme, physical-device camera capture, client-side oversized/non-image reject, and the full Telegram round-trip (staff replying FROM Telegram — operator-pending, needs STAFF_TELEGRAM_CHAT_ID + a real bot/chat).
