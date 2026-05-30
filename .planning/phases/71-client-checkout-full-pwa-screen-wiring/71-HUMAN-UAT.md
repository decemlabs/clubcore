---
status: partial
phase: 71-client-checkout-full-pwa-screen-wiring
source: [71-VERIFICATION.md]
started: 2026-05-30T00:00:00Z
updated: 2026-05-30T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. ЮKassa redirect round-trip (anti-oracle poll, criterion #1)
expected: Initiate a membership purchase from the PWA → land on the ЮKassa hosted page → complete/cancel → ЮKassa redirects back to `/payment/return?payment_id=<id>`; the screen shows ONLY "Ожидаем подтверждение..." while pending, never showing the membership as active until the `payment.succeeded` webhook fires and the status endpoint reports `succeeded`. Repeat for a PT-package purchase (return_url also carries `idempotency_key`).
result: [pending]

### 2. Service worker never caches /api/* at runtime
expected: With the PWA installed/loaded, open DevTools → Application → Cache Storage. No `/api/*` requests appear in any Workbox cache; the SW `navigateFallbackDenylist` excludes `/^\/api\//` and `runtimeCaching` is empty. Network tab confirms `/api/*` calls always hit the network, never the SW cache.
result: [pending]

### 3. Net-new screens make zero backend calls
expected: Open Chat, Referral, TrainerDetail, Notifications, and GymInfo screens. Each renders the shared "В разработке" ComingSoon placeholder. DevTools Network tab shows NO `/api/*` requests originating from any of these five screens.
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
