---
status: passed
phase: 87-notification-inbox
source: [87-VERIFICATION.md]
started: 2026-06-06
updated: 2026-06-06
verified_in_browser: 2026-06-06 (client-pwa :5175, dev client +79999999999, SW/cache cleared)
---

## Current Test

[✅ VERIFIED in browser 2026-06-06 — feed render + bell badge + mark-all all confirmed live]

## Tests

### 1. Live feed rendering (INBOX-01/05)
steps: Home bell «Уведомления» → NotificationsSheet (3 seeded rows: booking_confirmed unread, payment_succeeded unread, autopay_charge_failed read)
expected: paginated newest-first feed, unread dots on unread rows, relative timestamps, source-typed icons
result: ✅ PASS — 3 rows newest-first: «Бронь подтверждена» (green calendar icon, «4 мин. назад», unread dot), «Оплата прошла» (green card icon, «3 ч. назад», unread dot), «Не удалось списать автоплатёж» (red/danger icon, «вчера», no dot). No console errors except the fabricated trainer photo_url 404 (Phase 88, expected). Screenshot: /tmp/v24-verify/02-notifications-feed.png

### 2. System-event kinds render with correct copy (INBOX-03 surface)
steps: seeded one row per representative kind (booking_confirmed / payment_succeeded / autopay_charge_failed)
expected: correct Russian title/body + source-type icon/colour per kind; anti-oracle (no payment_canceled client rows)
result: ✅ PASS — all three kinds render with correct copy and styling (danger styling on autopay failure). NOTE: rows were DB-seeded for the browser surface check; the actual event→create_notification hooks (7 call sites, anti-oracle, webhook dedup) are covered by 9 integration tests in 87-03. A real end-to-end booking→inbox event round-trip remains the one un-exercised path here (logic green in tests).

### 3. Mark-all → bell badge (INBOX-02)
steps: with 2 unread, tap «Всё прочитано»
expected: PATCH /client/notifications/read-all; bell badge → 0; unread dots clear; persisted
result: ✅ PASS — bell changed from «Уведомления · 2 непрочитанных» → «Уведомления» (badge cleared), «Всё прочитано» button disappeared (only shows when unreadCount>0), unread dots gone. DB confirmed: unread=0, total=3 (persisted, not just optimistic).

### 4. Unread badge on bell (INBOX-01)
steps: Home with 2 unread
expected: bell shows unread indicator/count = 2
result: ✅ PASS — bell button labelled «Уведомления · 2 непрочитанных», unread dot visible. Screenshot: /tmp/v24-verify/01-home-bell-badge.png

## Summary

total: 4
passed: 4
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

None blocking. Browser surfaces (feed/badge/mark-all) all verified live. Real event→inbox hook round-trip was exercised via DB-seeded rows for the UI surface + integration tests for the server hooks (not a live booking event in this session).
