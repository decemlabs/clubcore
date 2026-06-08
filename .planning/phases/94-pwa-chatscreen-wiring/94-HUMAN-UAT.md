---
status: partial
phase: 94-pwa-chatscreen-wiring
source: [94-VERIFICATION.md]
started: 2026-06-08
updated: 2026-06-08
---

## Current Test

[awaiting human testing — deferred during autonomous run; all automated gates green + 3/3 must-haves verified in code]

## Tests

### 1. Pixel-perfect visual parity (vs 94-REFERENCE-ChatScreen.jsx)
expected: The ported ChatScreen looks пиксель-в-пиксель like the reference — list cards, bubbles, composer, animations (screen push/pop, msg-in, typing-bounce, pull-to-refresh spin, sheet slide, toast, spot illustration), gestures (swipe-to-mute, long-press sheet, scroll-down FAB), empty states, day separators, unread divider — in BOTH light and dark theme. No layout/spacing/typography/color drift.
result: [pending]

### 2. Live WS round-trip (PWA ↔ backend ↔ Telegram)
expected: With backend + Telegram bot running and dev login + reseed: sending a message from the PWA appears once; a staff Telegram reply arrives in the PWA in real time over WS; typing dots show while staff types; read tick flips ✓→✓✓ on reply-as-read; the Chat-tab unread badge updates from any tab (and via the 30s poll when WS is forced down).
result: [pending]

### 3. Photo flow on a real device
expected: Camera + gallery pickers open; an oversized/non-image file is rejected client-side (≤5MB, image/*); a valid photo shows an optimistic preview bubble, uploads, and sends; the real image renders in the thread; tapping a photo opens the full-screen overlay; closing returns to the thread.
result: [pending]

## Setup notes
- Dev login + reseed; hard-reload / bump SW cache (stale service worker can mask new code — see client-pwa-browser-verify gotchas).
- Dev proxy `/api` → localhost:8000; backend stack (`docker compose up postgres redis`) + ARQ worker + Telegram bot for the WS/Telegram round-trip.

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps

None at the code level — every behavior is wired and verified by automated gates + code inspection (see 94-VERIFICATION.md). These 3 items require a real browser/device + running backend, deferred per the autonomous-run auto-defer convention.
