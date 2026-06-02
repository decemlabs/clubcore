---
status: complete
phase: 71-client-checkout-full-pwa-screen-wiring
source: [71-VERIFICATION.md, 71-REVIEW.md]
started: 2026-05-30T00:00:00Z
updated: 2026-05-31T08:05:00Z
method: live Chrome DevTools walkthrough (dev stack — docker backend + vite :5174)
---

## Current Test

[testing complete]

## Tests

### 1. ЮKassa membership purchase round-trip (anti-oracle poll)
expected: Login → Plans → "Перейти к оплате" opens CheckoutSheet → confirm → redirect to ЮKassa → /payment/return shows only "Ожидаем подтверждение..." while pending, never active until webhook; abandoned → 30s timeout exit.
result: pass
severity: blocker
reverified_full_roundtrip: |
  2026-05-31 — FULL live round-trip completed end-to-end with REAL ЮKassa test-shop
  creds (shop 1372271), Claude-driven via Chrome DevTools. PWA login → Plans (prices
  render: 5 000 ₽ / 15 000 ₽) → "Оплатить" → POST /client/checkout/memberships/{id}
  → 201 + confirmationUrl → redirect to the real ЮKassa test page → paid with test
  card 5555 5555 5555 4477 + 3-DS → ЮKassa status=succeeded → payment.succeeded webhook
  (fired to localhost; SANDBOX bypasses IP allowlist) → membership ACTIVATED. Home now
  shows "Месяц безлимит · активен · 29 дней · до 2026-06-29". Anti-oracle held: the
  status endpoint returned only {id,status} (pending→succeeded); no membership existed
  until the webhook. This closes the creds-blocked redirect leg noted below.

  BLOCKER FOUND + FIXED during this run: the client checkout endpoints flushed the
  online_payments INSERT but had no commit owner (get_db rolls back on close), so the
  row never persisted — replay/idempotency broke and the webhook had no row to activate
  (entire CPAY round-trip non-functional). Phase-71 integration tests passed only
  because the SAVEPOINT harness + mocked ЮKassa masked the missing commit. Fixed in
  commit f122b52c (await session.commit() in both endpoints) + 2 real-commit regression
  tests; resolved debug session at .planning/debug/resolved/client-checkout-no-commit.md.
reverified: |
  2026-05-31 live Chrome DevTools re-test (Claude-driven) after re-seeding a freshly
  wiped dev DB (seed_demo_data + seed_dev_client + client email). The 71-09 blocker is
  GONE: prices/durations render as real numbers end-to-end —
  • PlansSheet: "Месяц безлимит · 30 дней · 5 000 ₽" and "5 тренировок · 5 занятий ·
    3 000 ₽/занятие · 15 000 ₽" (no "не число", no "undefined дней").
  • PlanConfirm/CheckoutSheet: "К ОПЛАТЕ 5 000 ₽ · Месяц безлимит · 1 мес · 5 000 ₽/мес".
  • HomeScreen (71-10): greets the real client ("Доброе утро, Клиент") and shows the
    real no-membership state ("Нет абонемента / истёк / 0 дней"), NOT the old demo
    "Годовой, 47 дней" fallback.
  "Оплатить · 5 000 ₽" fired POST /api/v1/client/checkout/memberships/{id} authenticated
  with correct x-csrf-token → 502 yookassa_permanent_error (placeholder shop creds),
  surfaced as a clean "Не получилось списать — Банк отклонил платёж" screen. The real
  ЮKassa redirect leg still needs sandbox shop creds (matches verification why_human) —
  not a regression. seed_demo_data confirmed to seed the catalog (1 membership + 1 PT).
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
result: pass
severity: blocker
reverified: |
  2026-05-31 live Chrome DevTools re-test (Claude-driven). Runtime inspection via
  navigator.serviceWorker.getRegistrations() + caches API:
  • Active SW: http://localhost:5174/sw.js, state "activated".
  • caches.keys() === ["gym-v3"] — the stale "gym-v2" cache is GONE (evicted on activate).
  • gym-v3 holds ZERO /api/* entries (only static shell: /, index.html, offline.html,
    manifest.json, icons, JS modules).
  • After 6 live /api/* calls this session (/me ×2, /home, /plans, /pt-packages,
    checkout/memberships), none were cached; /plans served the FRESH seeded catalog
    (no stale empty []). 71-08 network-only guard + cache bump confirmed working.
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
passed: 3
issues: 0
pending: 0
skipped: 0
blocked: 0
note: 2 blocker gaps (71-08 SW /api caching, 71-09 camelCase prices) + 71-10 real identity all re-verified LIVE on 2026-05-31 via Chrome DevTools after re-seeding a wiped dev DB. The FULL ЮKassa round-trip is now ALSO verified live with real test-shop creds (test card 5555 5555 5555 4477 → 3-DS → webhook → membership activated) — the previously creds-blocked redirect leg is CLOSED. One blocker was found and fixed during this run: client checkout never committed the online_payments row (commit f122b52c + regression tests).

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

## Environment changes made during the 2026-05-31 re-test (dev only, uncommitted)
- The dev DB had been wiped since the 2026-05-30 session (0 users/clients/plans, still at head 0045). Re-seeded from host to re-test:
  - `SEED_OWNER_EMAIL=owner@example.com SEED_OWNER_PASSWORD=ownerpass123 uv run python -m scripts.seed_demo_data` → owner + 1 membership plan ("Месяц безлимит" 5000₽/30д) + 1 PT-package ("5 тренировок" 15000₽/5).
  - `uv run python -m scripts.seed_dev_client` → client +79999999999 (telegram_user_id=999999999).
  - `UPDATE clients SET email='sasha@example.com'` for the 54-ФЗ online-payment gate.
- Browser: a fresh /login load registered the 71-08 gym-v3 SW automatically (no manual unregister needed this time).

## Environment changes made during the 2026-05-30 UAT (dev only, uncommitted)
- apps/backend/.env: added DEV_OTP_PIN_ENABLED=true (required after WR-06 to use the 111111 dev OTP).
- Recreated the backend container with `docker compose up -d --no-deps backend` (the migrate sidecar image is stale — DB already at head 0045; started backend bypassing the migrate gate).
- Seeded: owner (seed_demo_data), dev client +79999999999 (seed_dev_client), set that client's email, inserted one membership_plans row ("Месяц безлимит").
- Browser: unregistered the gym-v2 service worker and cleared its cache.
