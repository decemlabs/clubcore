---
status: partial
phase: 71-client-checkout-full-pwa-screen-wiring
source: [71-VERIFICATION.md, 71-REVIEW.md]
started: 2026-05-30T00:00:00Z
updated: 2026-05-31T00:00:00Z
method: live Chrome DevTools walkthrough (dev stack — docker backend + vite :5174)
---

## Current Test

[gap closure landed (71-08/09/10) — both blocker gaps fixed at code level and confirmed by code inspection (71-VERIFICATION.md: 14/14 statically-verifiable truths). Tests 1 & 2 reset to PENDING for a live-browser re-test; test 3 still passing.]

## Tests

### 1. ЮKassa membership purchase round-trip (anti-oracle poll)
expected: Login → Plans → "Перейти к оплате" opens CheckoutSheet → confirm → redirect to ЮKassa → /payment/return shows only "Ожидаем подтверждение..." while pending, never active until webhook; abandoned → 30s timeout exit.
result: pending
severity: blocker
resolution: |
  Gap closed by 71-09: PlansSheet/PlanConfirm/CheckoutSheet adapters now read the
  camelCase contract (priceKopecks/durationDays/sessionCount) — grep confirms zero
  residual snake_case reads; seed_demo_data now seeds membership_plans + pt_package_plans
  so the catalog is non-empty. Awaiting live re-test: confirm prices/durations render
  as numbers and the ЮKassa redirect leg (needs sandbox shop creds).
reported: |
  CR-02 wiring VERIFIED working end-to-end: login (+79999999999/111111) → Plans →
  "Перейти к оплате" → CheckoutSheet opens → "Оплатить" fires
  POST /api/v1/client/checkout/memberships/{plan_id} with correct x-csrf-token.
  Email-required (422 client_email_required_for_online_payment) is surfaced as a
  clean "Нужен email (54-ФЗ)" dialog. After setting client email, checkout reaches
  ЮKassa creation → 502 yookassa_permanent_error (placeholder shop_id=000000 — real
  redirect leg needs sandbox creds; matches verification why_human).
  BLOCKER found: every price/duration renders "не число" (NaN) and "undefined дней"
  in PlansSheet, PlanConfirm and CheckoutSheet — adapters read snake_case
  (p.price_kopecks / p.duration_days) but the API serializes camelCase
  (priceKopecks / durationDays). The same snake_case adapter is used by HomeScreen
  membership card (days_until_end, plan_name_snapshot, start_date, end_date), so a
  real membership would also misrender.
  Also: no membership plans are seeded by seed_demo_data, so the catalog is empty
  out of the box (had to insert a membership_plans row to test).

### 2. Service worker never caches /api/* at runtime
expected: No /api/* entries in any SW cache; navigateFallbackDenylist excludes /api/, runtimeCaching empty; /api/* always hits network.
result: pending
severity: blocker
resolution: |
  Gap closed by 71-08: public/sw.js now has a url.pathname.startsWith('/api/')
  network-only guard placed before the navigation and cache-first branches (zero
  cache.put for /api/*), and VERSION bumped to gym-v3 so the activate handler evicts
  the stale gym-v2 cache that held the authed /api/* entries. Awaiting live re-test:
  load the app, confirm active worker is gym-v3, Cache Storage holds zero /api/* keys,
  every /api/* request is "(from network)", and offline shell fallback still works.
reported: |
  FAIL. Registered SW is the hand-written apps/client-pwa/public/sw.js (cache
  "gym-v2"), registered by services/pwa.js → registerPwa() in main.jsx:11 — NOT the
  VitePWA/workbox SW. sw.js is cache-FIRST for all non-navigation GETs and caches any
  same-origin res.ok response, including /api/*. Cache "gym-v2" was observed holding:
  /api/v1/client/me, /api/v1/client/home, /api/v1/client/plans,
  /api/v1/client/pt-packages, /api/v1/client/history/visits?page=1 — i.e. authed,
  per-client data. It served a STALE empty /api/v1/client/plans ([]) even after the
  catalog changed; a cache-busting no-store fetch returned the real plan. The
  vite.config VitePWA navigateFallbackDenylist + empty runtimeCaching (what
  71-VERIFICATION checked statically) is DEAD CONFIG — that worker is never the one
  registered.

### 3. Net-new screens make zero backend calls
expected: Chat, Referral, TrainerDetail, Notifications, GymInfo render "В разработке" ComingSoon; no /api/* requests.
result: pass
reported: |
  Chat ("Сообщения / В разработке") and GymInfo ("Информация о зале / В разработке")
  verified rendering ComingSoon; navigating through them fired zero /api/* requests
  (only HomeScreen's own /client/home on tab return). Remaining three sheets share
  the same ComingSoon component and the ESLint data-layer boundary (D-71-09) forbids
  these screens from importing @/data.

## Summary

total: 3
passed: 1
issues: 0
pending: 2
skipped: 0
blocked: 0
note: 2 blocker gaps fixed at code level by 71-08/09/10 (VERIFICATION 14/14 static truths); reset to pending for live re-test

## Gaps

- truth: "Service worker must never cache /api/* (PWA-07)"
  status: resolved
  resolved_by: 71-08
  severity: blocker
  test: 2
  root_cause: "App registers hand-written public/sw.js (cache 'gym-v2') via registerPwa() in main.jsx:11. sw.js fetch handler is cache-first for all non-navigation GETs and caches any same-origin res.ok response, so /api/* (same-origin via dev proxy) gets cached, including authed /me + /home. The VitePWA workbox config with the /api denylist is generated but never registered."
  artifacts:
    - path: "apps/client-pwa/public/sw.js"
      issue: "Lines 50-62: cache-first + caches any same-origin res.ok GET, including /api/*. No /api exclusion."
    - path: "apps/client-pwa/src/services/pwa.js"
      issue: "registerPwa() registers /sw.js (the hand-written public/sw.js), bypassing VitePWA."
    - path: "apps/client-pwa/src/main.jsx"
      issue: "Line 11 imports registerPwa; registration activates the non-compliant SW."
  missing:
    - "Either delete public/sw.js + register the VitePWA-generated workbox SW, OR rewrite sw.js to NEVER cache /api/* (network-only for /api) and bump cache version to evict gym-v2."
    - "An activate-time purge that deletes any existing /api/* entries from old caches on the client."

- truth: "Plan/membership prices and durations display correctly in the checkout flow"
  status: resolved
  resolved_by: 71-09
  severity: blocker
  test: 1
  root_cause: "Frontend adapters read snake_case fields (price_kopecks, duration_days, days_until_end, plan_name_snapshot, start_date, end_date) but the API serializes camelCase (priceKopecks, durationDays, ...). undefined / 100 = NaN → toLocaleString('ru-RU') renders 'не число'; durationDays undefined → 'undefined дней'."
  artifacts:
    - path: "apps/client-pwa/src/screens/sheets/PlansSheet.jsx"
      issue: "toMembershipCard (lines 9-24) reads p.price_kopecks / p.duration_days; toPtCard reads p.session_count / p.price_kopecks. API is camelCase."
    - path: "apps/client-pwa/src/screens/HomeScreen.jsx"
      issue: "toSubInfo (lines 28-45) reads membership.days_until_end / plan_name_snapshot / start_date / end_date (snake_case); latent NaN/empty when a real membership exists."
  missing:
    - "Decide canonical casing (api-client schema.d.ts) and align the adapters to camelCase (or convert at the fetcher boundary)."

- truth: "Wired screens display the logged-in client's real identity and membership (full PWA screen wiring)"
  status: resolved
  resolved_by: 71-10
  severity: major
  test: 1
  root_cause: "HomeScreen userName is hardcoded to tweaks.userName || 'Саша' (never bound to /client/me); when /client/home returns membership=null the code falls back to demo getSubInfo(tweaks.subState) (HomeScreen.jsx:97-99,106) so a no-membership client sees a fake active 'Годовой, 47 дней' instead of the toSubInfo(null) 'Нет абонемента' state. ProfileScreen renders fully mock identity ('Саша Морозов / sasha@example.com / Годовой / 42 000 ₽') that does not match /client/me (Клиент Тестовый, no email, no membership) despite calling /client/me. Confirmed with the service worker cleared, so this is code-level, not stale cache."
  artifacts:
    - path: "apps/client-pwa/src/screens/HomeScreen.jsx"
      issue: "Line 106 userName from tweaks; lines 97-99 membership-null → demo fallback instead of real empty state."
    - path: "apps/client-pwa/src/screens/ProfileScreen.jsx"
      issue: "Identity/membership header shows hardcoded mock, not /client/me data."
  missing:
    - "Confirm whether Home/Profile identity+membership binding was in Phase 71 scope; if so, bind to /client/me and use toSubInfo(null) for the no-membership state."

## Environment changes made during this UAT (dev only, uncommitted)
- apps/backend/.env: added DEV_OTP_PIN_ENABLED=true (required after WR-06 to use the 111111 dev OTP).
- Recreated the backend container with `docker compose up -d --no-deps backend` (the migrate sidecar image is stale — DB already at head 0045; started backend bypassing the migrate gate).
- Seeded: owner (seed_demo_data), dev client +79999999999 (seed_dev_client), set that client's email, inserted one membership_plans row ("Месяц безлимит").
- Browser: unregistered the gym-v2 service worker and cleared its cache.
