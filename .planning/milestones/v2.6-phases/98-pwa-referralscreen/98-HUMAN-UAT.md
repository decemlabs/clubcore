---
status: partial
phase: 98-pwa-referralscreen
source: [98-VERIFICATION.md]
started: 2026-06-08
updated: 2026-06-08
---

## Current Test

[awaiting human testing — browser-only items; auto-deferred during autonomous run]

## Tests

### 1. Pixel-perfect visual parity (light + dark)
expected: The graduated ReferralSheet renders pixel-identical to `.planning/refs/v2.6-REFERENCE-ReferFriendScreen.jsx` in both light and dark themes (hero, reward rows, code box + copy, share chips, "Как это работает" steps, invited-friends list). Code audit scored 24/24 from byte-faithful CSS transcription; sub-pixel/animation/dark-mode font metrics need a rendered check.
result: [pending]

### 2. Live deep-link → join → invitees/accrued round-trip (two sessions)
expected: Opening `…/i/<code>` shows the landing (referrer first name + bonus preview), stores the pending code, and after the friend completes onboarding the binding is captured (POST /client/referral/capture). After the friend's first membership purchase (payment.succeeded), the referrer's ReferralSheet shows the friend as "Присоединился +bonus" and "Уже накоплено" reflects the real referral_accrual sum. Requires a live backend + two client sessions.
result: [pending]

### 3. Share / copy chips
expected: Copy copies the code; Telegram / WhatsApp / native share each carry the server-built `shareUrl` (never a client-built URL). Verify on a device with the native share sheet.
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps

- **Auto-deferred** during the autonomous v2.6 run (browser/device + live-backend required; cannot be exercised headlessly). Re-run `/gsd:verify-work 98` after a clean dev-DB re-migrate (see STATE.md blocker).
- **Phase-99 follow-up:** `ReferralLandingScreen.formatBonusPreview` renders a static "14 дней в подарок" (TODO Phase 99) — the resolver exposes `welcomeBonusKopecks`, not days; decide whether to surface the kopecks figure or add a `welcomeBonusDays` field server-side.
