---
phase: 71-client-checkout-full-pwa-screen-wiring
verified: 2026-05-31T00:00:00Z
status: passed
score: 9/9 must-haves verified (gap-closure: 14/14 statically-verifiable truths VERIFIED); full ЮKassa round-trip verified LIVE 2026-05-31
live_roundtrip_verification:
  date: 2026-05-31
  scope: "All 3 human_verification items below are now CLOSED via live Chrome DevTools + real ЮKassa test-shop creds (shop 1372271)."
  results:
    - "SW /api Cache-Storage: gym-v3 active, gym-v2 evicted, zero /api/* keys, all /api/* from network — confirmed live."
    - "Real-data rendering: real identity + numeric plan prices (5 000 ₽ / 15 000 ₽) + real empty→active membership — confirmed live."
    - "ЮKassa round-trip: checkout → real ЮKassa test page → test card 5555 5555 5555 4477 + 3-DS → status=succeeded → payment.succeeded webhook → membership ACTIVATED (Home: 'Месяц безлимит · активен · 29 дней'). Anti-oracle held (status endpoint only {id,status}; no membership until webhook)."
  blocker_found_and_fixed:
    summary: "Client checkout endpoints flushed the online_payments INSERT but had no commit owner (get_db rolls back on close) → row never persisted → webhook had no row to activate → entire CPAY round-trip was non-functional. Phase-71 integration tests passed only because the SAVEPOINT harness + mocked ЮKassa masked the missing commit. THIS PHASE'S 'verified' STATUS WAS BASED ON BROKEN CODE until 2026-05-31."
    fix: "commit f122b52c — await session.commit() in client_checkout_membership + client_checkout_pt_package; + 2 real-commit regression tests (test_*_checkout_row_committed_to_db) that fail on the unfixed code."
    debug_session: ".planning/debug/resolved/client-checkout-no-commit.md"
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 9/9
  scope: "gap-closure re-verification of plans 71-08, 71-09, 71-10 (live-UAT blockers from 71-HUMAN-UAT.md)"
  gaps_closed:
    - "BLOCKER (UAT test 2): service worker cached /api/* (gym-v2 cache-first). 71-08 added a network-only /api guard in public/sw.js and bumped cache to gym-v3 — statically verified; SW guard placement precedes navigation branch, no gym-v2 literal remains."
    - "BLOCKER (UAT test 1): plan prices/durations rendered 'не число'/'undefined дней' — adapters read snake_case but API is camelCase. 71-09 aligned PlansSheet/HomeScreen/ProfileScreen adapters to camelCase (zero residual snake_case field reads) and seeded membership_plans + pt_package_plans rows."
    - "MAJOR (UAT test 1 identity): Home/Profile showed mock identity + fake active membership. 71-10 bound greeting + identity header to /client/me and routed membership=null to the real toSubInfo(null) 'Нет абонемента' empty state; all mock literals removed."
  gaps_remaining: []
  regressions:
    - "ADVISORY (WR-01, not a gap-plan must-have): App.jsx:260 still passes legacy slugs ('annual'/'monthly') as currentPlanId while PlansSheet now matches on real plan UUID (p.id = String(plan.id)). Slugs can never equal a UUID, so the 'current plan' badge (isCurrent / 'сейчас активен' / 'Текущий тариф') is dead. Cosmetic only — does not block any gap-plan truth. Surfaced for follow-up."
human_verification:
  - test: "Service worker /api Cache-Storage runtime inspection. Build/run dev stack, log in (+79999999999 / 111111). DevTools → Application → Service Workers: confirm active worker is gym-v3. Cache Storage: confirm NO gym-v2 cache exists and gym-v3 holds only shell + static assets — ZERO /api/* keys. Network tab: Home → Plans → Profile, every /api/* shows '(from network)'. Offline: reload renders /offline.html / cached shell."
    expected: "gym-v3 active; no gym-v2 cache; zero /api/* entries in Cache Storage; all /api/* served from network; offline shell still renders. (Re-runs 71-HUMAN-UAT test 2.)"
    why_human: "Cache-Storage population is runtime browser behavior. Code inspection confirms the network-only /api guard precedes the cache-first branch and the version bump evicts gym-v2 on activate, but actual eviction + zero-cache state can only be confirmed in a live browser."
  - test: "Live real-data rendering. Log in as the dev client (+79999999999, real /client/me, no membership, email set). Home: greeting shows the real first name (not 'Саша'); with no membership the card shows 'Нет абонемента' + 'Выбрать тариф' CTA (no fake active 'Годовой 47 дней'). Profile: identity header shows real name/phone/email (em-dash if absent, not 'Саша Морозов / sasha@example.com'); membership block shows no-membership state with no '42 000 ₽' renewal. Plans: each card shows a numeric price ('5 000 ₽') and 'N дней' (no 'не число'/'undefined дней'). After a dev purchase, Home+Profile reflect real plan name/days-left/until-date."
    expected: "Real identity + real (or genuinely empty) membership render; plan prices/durations are numeric. (Re-runs 71-HUMAN-UAT test 1 + identity.)"
    why_human: "Requires a live backend + seeded catalog + logged-in session to render real /client/me + /client/home + /client/plans data. Field-name correctness is statically verified (zero snake_case reads, camelCase keys present); end-to-end rendered output needs the live stack."
  - test: "End-to-end ЮKassa membership/PT purchase round-trip (carried forward from prior verification, still pending sandbox creds): log in, Plans → checkout → ЮKassa redirect → /payment/return shows only 'Ожидаем подтверждение...' while pending; active only after payment.succeeded webhook."
    expected: "PaymentReturnScreen shows waiting copy while polling; Home shows active membership only after webhook; no premature activation."
    why_human: "Requires a live/sandboxed ЮKassa account (placeholder shop_id=000000 returns 502 yookassa_permanent_error in dev)."
---

# Phase 71: Client Checkout + Full PWA Screen Wiring — Verification Report (Gap-Closure Re-verification)

**Phase Goal:** A client can initiate a ЮKassa membership/PT-package purchase entirely from the PWA; payment activation webhook-only; server-side authoritative price; 54-ФЗ email gate; all core PWA screens (Home, Profile, Book, Plans, Checkout, QR) wired to the real backend.
**Verified:** 2026-05-31
**Status:** passed (full ЮKassa round-trip verified live 2026-05-31; see `live_roundtrip_verification` in frontmatter)
**Re-verification:** Yes — gap-closure pass over plans 71-08, 71-09, 71-10 (live-UAT blockers), THEN a full live round-trip with real test-shop creds that found + fixed a commit-ownership blocker (f122b52c).

> ⚠️ **Post-verification correction (2026-05-31):** the original `human_needed` verification was based on code where client checkout never committed the `online_payments` row — the CPAY round-trip could not complete. Found during the live round-trip and fixed (commit f122b52c + real-commit regression tests). The phase is now genuinely round-trip-verified live.

---

## Re-verification Scope

This pass focuses on the THREE gap-closure plans (71-08, 71-09, 71-10) that closed the live-UAT blockers documented in 71-HUMAN-UAT.md. Plans 71-01 through 71-07 were verified previously (9/9 roadmap truths). The gap-plan must-haves split cleanly into two buckets:

- **Statically verifiable from source** (this report VERIFIES): camelCase field reads, hardcoded-string removal, empty-state wiring, SW /api guard placement + version bump, seed columns.
- **Inherently runtime / live-backend** (routed to human_verification): SW Cache-Storage eviction state, and end-to-end real-data rendering with a logged-in session.

All statically-verifiable gap-plan truths are VERIFIED. The remaining items are runtime confirmations that the original UAT method (live Chrome DevTools) must close.

---

## Goal Achievement — Gap-Closure Must-Haves

### 71-08 — Service Worker /api Cache Hardening (PWA-05 / PWA-07)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | No /api/* response is ever written to any SW cache at runtime | VERIFIED (code) | `public/sw.js:40-43` — `if (url.pathname.startsWith('/api/')) { event.respondWith(fetch(req)); return }` with zero cache.put; guard precedes both navigation (line 46) and cache-first (line 60) branches. Runtime Cache-Storage state → human. |
| 2 | Every /api/* GET goes to the network (network-only) | VERIFIED (code) | Same guard returns `fetch(req)` directly; no `caches.match` on the /api path. |
| 3 | Old gym-v2 /api/* cache entries purged on activate (existing installs) | VERIFIED (code) | `VERSION = 'gym-v3'` (line 4); activate handler deletes every key `!== VERSION` (lines 24-26); no `gym-v2` literal remains. Actual eviction on a real install → human. |
| 4 | Static shell + offline fallback still works | VERIFIED (code) | SHELL precache (lines 5-13) and navigation network-first → cached shell → `/offline.html` (lines 46-57) unchanged. Offline reload behavior → human. |

Registration unchanged: `pwa.js:14` still `register('/sw.js')`; PWA-07 regression-guard comment present (`pwa.js:12-13`).

### 71-09 — camelCase Adapter Alignment + Catalog Seed (PWA-05 / CPAY-01 / CPAY-02)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Plan prices/durations render as numbers, never 'не число'/'undefined дней' | VERIFIED (code) | `PlansSheet.jsx:10,11` read `p.priceKopecks`/`p.durationDays`; `:33` reads `p.sessionCount`. grep: 0 residual `price_kopecks\|duration_days\|session_count`. Rendered output → human. |
| 2 | PT-package cards render session count + per-session price | VERIFIED (code) | `toPtCard` (PlansSheet.jsx:27-41) uses `sessionCount` for tagline, divisor, period, popular check; `priceKopecks/100` for price. |
| 3 | Real membership card renders days-left/name/until/progress from API | VERIFIED (code) | `toSubInfo` (HomeScreen.jsx:27-44, ProfileScreen.jsx:18-35) reads `daysUntilEnd/expiringSoon/startDate/endDate/planNameSnapshot`; WR-03 UTC-midnight `subTotalDays`. grep: 0 residual snake_case. |
| 4 | Next-booking card renders trainer + time from API | VERIFIED (code) | `homeData?.nextBooking` (HomeScreen.jsx:135); `UpcomingCard` reads `booking.trainerName/startTime` (:549-554); `HomeMinimal` reads `nextBooking.startTime/trainerName` (:442-445). |
| 5 | Visit/PT/payment history rows render dates/names/amounts from API | VERIFIED (code) | ProfileScreen `VisitsList` `v.gymDate/v.checkedInAt` (:320-326); `TrainingsList` `t.trainerNameSnapshot/performedAt/cancelledAt` (:410-417); `PurchaseRow` `p.amountKopecks/subjectKind/receivedAt/method` (:653-666). |
| 6 | seed_demo_data seeds ≥1 membership plan + ≥1 PT-package | VERIFIED (code) | `_seed_catalog` (seed_demo_data.py:45-85) inserts `MembershipPlan(name,duration_days=30,price_kopecks=500_000,freeze_days_limit=14,active=True)` + `PtPackagePlan(name,session_count=5,price_kopecks=1_500_000,validity_days=90)`, idempotent ON CONFLICT DO NOTHING on lower(name) alive index. Columns match ORM models exactly. `ast.parse` OK. |

### 71-10 — Real /client/me Identity Binding (PWA-05)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Home greeting shows real first name from /client/me (not 'Саша') | VERIFIED (code) | `useClientMe` imported (HomeScreen.jsx:10); `const { data: me } = useClientMe()` (:94); `userName = me?.firstName || tweaks.userName || ''` (:103). grep 'Саша' → 0. |
| 2 | membership=null → real 'Нет абонемента' empty state (not fake active card) | VERIFIED (code) | `sub = toSubInfo(homeData?.membership ?? null)` (HomeScreen.jsx:98); `getSubInfo(tweaks.subState)` count = 0; `toSubInfo(null)` returns `label:'Нет абонемента', tone:'danger'`, driving ExpiredAlert + 'Выбрать тариф'. |
| 3 | Profile identity header shows real /client/me name/phone/email (graceful em-dash) | VERIFIED (code) | `useClientMe` (ProfileScreen.jsx:9,52); `fullName` from `me?.firstName/lastName` (:60); `phone = me?.phone ?? '—'`, `email = me?.email ?? '—'` (:62-63); rendered :80-82. grep `sasha@example.com\|916) 482-09-14` → 0. |
| 4 | Profile membership block uses real state, no hardcoded renewal amounts | VERIFIED (code) | Renewal line shows `sub.until` date only (ProfileScreen.jsx:121-128); grep `42 000 ₽\|4 900 ₽` → 0. 'Карта •••• 4821' is demo card chrome on the danger branch (not presented as live financial data). |

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/client-pwa/public/sw.js` | gym-v3, /api network-only guard before nav branch | VERIFIED | guard at :40-43, VERSION gym-v3 at :4, no gym-v2 literal |
| `apps/client-pwa/src/services/pwa.js` | register('/sw.js') + PWA-07 guard comment | VERIFIED | :14 register, :12-13 comment |
| `apps/client-pwa/src/screens/sheets/PlansSheet.jsx` | priceKopecks/durationDays/sessionCount | VERIFIED | 0 snake_case reads |
| `apps/client-pwa/src/screens/HomeScreen.jsx` | useClientMe, daysUntilEnd, nextBooking, no getSubInfo fallback | VERIFIED | wired, 0 snake_case, 0 'Саша' |
| `apps/client-pwa/src/screens/ProfileScreen.jsx` | useClientMe, amountKopecks/gymDate/performedAt, no mock literals | VERIFIED | wired, 0 snake_case, 0 mock literals |
| `apps/backend/scripts/seed_demo_data.py` | seeds membership_plans + pt_package_plans | VERIFIED | parses, columns match models, idempotent |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| sw.js fetch handler | /api/* requests | early `pathname.startsWith('/api/')` network-only return | WIRED | precedes navigation + cache-first branches |
| PlansSheet adapters | ClientCatalog*Response (camelCase) | p.priceKopecks/durationDays/sessionCount | WIRED | useClientPlans/useClientPtPackages → toMembershipCard/toPtCard |
| HomeScreen userName + sub | /client/me + /client/home | useClientMe().firstName + toSubInfo(homeData.membership ?? null) | WIRED | both hooks consumed |
| ProfileScreen identity header | ClientMeResponse | useClientMe() firstName/lastName/phone/email | WIRED | rendered at :80-82 |
| seed_catalog | membership_plans / pt_package_plans | pg_insert + ON CONFLICT DO NOTHING | WIRED | called from _run (:143) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| PlansSheet | membershipPlans/ptPackages | useClientPlans/useClientPtPackages (GET /client/plans, /pt-packages) | catalog now seeded by 71-09 | FLOWING (code) — live render → human |
| HomeScreen | me, homeData | useClientMe / useClientHome | real /client/me + /client/home | FLOWING (code) — live render → human |
| ProfileScreen | me, homeData, visit/pt/payment | useClientMe/Home + history hooks | real backend | FLOWING (code) — live render → human |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| PWA-05 | 71-08/09/10 | Home/Profile/Book/Plans/Checkout/QR on real backend | SATISFIED (code) | camelCase adapters + /client/me identity + seeded catalog; live render → human |
| PWA-07 | 71-08 | SW never caches /api/* | SATISFIED (code) | network-only /api guard + gym-v3 eviction; Cache-Storage state → human |
| CPAY-01 | 71-09 | Membership purchase via ЮKassa | SATISFIED (price render fix + seed) | priceKopecks alignment unblocks numeric checkout totals; round-trip → human (sandbox) |
| CPAY-02 | 71-09 | PT-package purchase via ЮKassa | SATISFIED (price render fix + seed) | sessionCount/priceKopecks alignment; round-trip → human (sandbox) |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| apps/client-pwa/src/App.jsx | 260 | `currentPlanId={t.subState === 'active' ? 'annual' : 'monthly'}` legacy slugs vs PlansSheet UUID match | ℹ️ Info (ADVISORY / WR-01) | Current-plan badge (isCurrent / 'сейчас активен' / 'Текущий тариф') is dead — slugs never equal a real UUID. Cosmetic; not a gap-plan must-have. |

No TBD/FIXME/XXX debt markers in any modified file. The remaining demo chrome (GymStatusPill, DEMO_TRAINER_CANCEL, '•••• 4821', notifications empty state) is pre-existing and explicitly out of scope per the plans — not presented as live data.

### Human Verification Required

1. **SW /api Cache-Storage runtime inspection** — confirm gym-v3 active, no gym-v2, zero /api/* cache keys, all /api/* from network, offline shell renders. (Re-runs UAT test 2.)
2. **Live real-data rendering** — confirm real identity + real/empty membership + numeric plan prices render with a logged-in session and seeded catalog. (Re-runs UAT test 1 + identity.)
3. **ЮKassa round-trip** — carried forward; needs sandbox creds.

### Gaps Summary

No gaps. All 14 statically-verifiable gap-closure truths across 71-08/09/10 are VERIFIED by code inspection: the SW network-only /api guard + gym-v3 bump are in place and correctly ordered; all three wired screens read the camelCase contract with zero residual snake_case field reads; Home/Profile are bound to /client/me with all mock identity literals and fabricated renewal amounts removed; membership=null routes to the real 'Нет абонемента' empty state with no demo fallback; and seed_demo_data seeds both catalog tables with columns that match the ORM models.

Status is `human_needed` (not `passed`) because the two blocker fixes that originally FAILED in live UAT (SW Cache-Storage state, real-data rendering) are inherently runtime behaviors. The code is correct; the original UAT method must confirm the runtime result before the phase can be marked fully passed.

One advisory regression (WR-01) is surfaced for follow-up: App.jsx:260 passes legacy plan slugs as `currentPlanId` while PlansSheet now matches real UUIDs, leaving the current-plan badge dead. This is cosmetic and does not block any gap-plan must-have.

---

_Verified: 2026-05-31_
_Verifier: Claude (gsd-verifier)_
