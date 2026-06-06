---
status: partial
phase: 88-trainer-detail-bio
source: [88-VERIFICATION.md, 88-03-PLAN.md Task 3]
started: 2026-06-06
updated: 2026-06-06
---

## Current Test

[awaiting human testing — deferred during autonomous run per operator-pending-verify-autodefer; this is Plan 88-03 Task 3, a checkpoint:human-verify gate]

## Tests

### 1. Browser: TrainerDetailSheet renders live trainer profile
steps: Start Docker backend + PWA dev server; dev-login + reseed (unregister stale SW first per client-pwa-browser-verify-gotchas); open trainers list (Home/trainers) and tap a trainer
expected: Real name + specialization + БИОГРАФИЯ bio render (not ComingSoon/placeholder); Avatar shows initials (seed leaves photo_url NULL); "Записаться" CTA closes sheet + opens book tab; chevron-back closes sheet
result: [pending]

### 2. Owner photo_url + error/empty states
steps: Owner PATCH a trainer photo_url to a valid https image; reopen sheet; also throttle to offline to see error copy
expected: Photo renders from https URL (falls back to Avatar on bad/empty); error state shows "Не удалось загрузить профиль тренера. Потяните вниз, чтобы повторить."; null bio shows "Информация скоро появится."
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
