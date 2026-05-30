---
phase: 71-client-checkout-full-pwa-screen-wiring
verified: 2026-05-30T18:00:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Perform end-to-end membership purchase via ЮKassa in the PWA: log in as a client with email set, open Plans, select a membership, complete checkout, verify redirect to ЮKassa, return to /payment/return, confirm the polling screen shows 'Ожидаем подтверждение...' while pending and navigates to Home only after payment.succeeded."
    expected: "PaymentReturnScreen shows only the waiting copy while polling; Home shows active membership only after webhook fires; no premature activation state is shown in CheckoutSheet or PaymentReturnScreen."
    why_human: "End-to-end ЮKassa redirect flow requires a live payment environment; cannot be verified programmatically without a real or sandboxed ЮKassa account."
  - test: "Verify that the service worker does not cache any /api/* response. Open DevTools → Application → Service Workers, navigate through the wired screens (Home, Profile, Plans, Book, QR), and inspect Cache Storage for any api-prefixed entries."
    expected: "Cache Storage contains no /api/* entries. Only static assets (JS, CSS, HTML, images) are cached."
    why_human: "Service worker cache inspection requires a running browser environment; SW behavior cannot be verified by grepping the config alone."
  - test: "Confirm that the five net-new screens (Chat, Referral, TrainerDetail, Notifications, GymInfo) display the 'В разработке' placeholder and make zero network calls when opened. Use DevTools → Network to confirm no /api/* requests fire."
    expected: "Each screen renders the ComingSoon card. Network tab shows no API requests from any of the five screens."
    why_human: "Absence-of-network-call verification requires a running browser; grep confirms code structure but not runtime behavior."
---

# Phase 71: Client Checkout + Full PWA Screen Wiring — Verification Report

**Phase Goal:** A client can initiate a ЮKassa membership or PT-package purchase entirely from the PWA; payment activation is locked to the existing webhook; server-side price is authoritative; 54-ФЗ email gate is enforced; all core PWA screens (Home, Profile, Book, Plans, Checkout, QR) are wired to the real backend.
**Verified:** 2026-05-30T18:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification.

---

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A client can initiate a membership purchase/renewal and a PT-package purchase via ЮKassa from the PWA; the redirect-back screen shows only "awaiting confirmation" (anti-oracle — no premature activation) | VERIFIED | CR-01/CR-02 fixes confirmed in code: `_sell_subject_core` accepts `return_url_override`; `client_checkout_membership` builds `return_url = {client_return_url}?payment_id={op_id}`; `client_checkout_pt_package` appends `&idempotency_key=...`; `CheckoutSheet.jsx:73-85` redirects to `result.confirmationUrl` only; `PaymentReturnScreen.jsx:26-31` shows ONLY "Ожидаем подтверждение..." while pending, navigates to "/" only on `status === 'succeeded'`; regression test `test_membership_checkout_return_url_contains_payment_id` (line 634) asserts `payment_id={online_payment_id}` in the captured ЮKassa return_url; `test_pt_checkout_return_url_contains_payment_id_and_idempotency_key` (line 703) asserts both params present |
| 2 | Membership/PT-package activation occurs only after `payment.succeeded` webhook fires; a duplicate webhook delivery does not double-activate (idempotent checkout) | VERIFIED | `test_duplicate_webhook_does_not_double_activate` (line 565 of test_checkout.py) delivers `payment.succeeded` twice and asserts exactly one activation; the existing `handle_payment_succeeded` webhook handler was already idempotent; client checkout writes to the same `OnlinePayment` row shape consumed by the webhook |
| 3 | Attempting checkout without a client email returns 422 `client_email_required_for_online_payment` (54-ФЗ fiscal receipt gate) | VERIFIED | `_sell_subject_core` enforces the email gate at service.py line 267 (WR-01 fix: after replay check); `ClientEmailRequiredForOnlinePaymentError` → 422 `client_email_required_for_online_payment`; test `test_checkout_without_email_returns_422` (line 412) proves the 422 response; WR-01 fix confirmed at service.py:219 (replay check moved before email gate) |
| 4 | The PWA Home, Profile, Book, Plans, Checkout, and QR screens fetch data from the real client backend; the mock data layer is replaced for these six screens | VERIFIED | HomeScreen: `useClientHome()` at line 80 (no mock imports); ProfileScreen: `useClientVisitHistory`, `useClientPtHistory`, `useClientPaymentHistory` hooks (lines 8-10, no VISIT_HISTORY/TRAINING_HISTORY/PURCHASE_HISTORY imports); PlansSheet: `useClientPlans()` and `useClientPtPackages()` at lines 44-45; CheckoutSheet: `mutateAsync` calls via `useClientCheckoutMembership`/`useClientCheckoutPtPackage` at line 35-36; QRSheet: `useClientQrToken(true)` at line 12, `QRCodeSVG` renders real signed JWT; BookScreen: `useClientAvailableSlots()`, `useCreateBooking()`, `useCancelBooking()` at lines 61-63 (real Phase-70 slot data, no CALENDAR/TIME_SLOTS/BUSY_SLOTS imports) |
| 5 | Net-new screens (Chat, Referral, trainer reviews, notification inbox, gym-info) display a "coming soon" placeholder — no backend calls are made from them; the service worker never caches `/api/*` requests | VERIFIED | All 5 net-new screens confirmed: ChatScreen renders `<ComingSoon title="Сообщения" />`, ReferralSheet `<ComingSoon title="Привести друга" />`, TrainerDetailSheet `<ComingSoon title="Тренер" />`, NotificationsSheet `<ComingSoon title="Уведомления" />`, GymInfoSheet `<ComingSoon title="Информация о зале" />`; none import clientFetcher/clientQueries/@tanstack/react-query; ComingSoon.tsx renders "В разработке"; ESLint `no-restricted-paths` boundary at eslint.config.js line 87; SW vite.config.js: `navigateFallbackDenylist: [/^\/api\//]`, `runtimeCaching: []` |

**Score:** 5/5 truths verified

---

### Code Review Fixes Verification (CR-01, CR-02, CR-03 + WR-01, WR-02)

All three BLOCKER and two WARNING findings from 71-REVIEW.md were addressed in post-review commits:

| Finding | Severity | Fix Status | Evidence |
|---------|----------|------------|----------|
| CR-01: membership return_url never carried payment_id | BLOCKER | FIXED | `_sell_subject_core` accepts `online_payment_id_override` + `return_url_override` (service.py:180-181); `client_checkout_membership` builds `return_url = f"{yookassa_settings.client_return_url}?payment_id={op_id}"` (service.py:505); commit `0417fddb`, `7516f9a1` |
| CR-02: PT return URL appended idempotency_key to ЮKassa URL | BLOCKER | FIXED | `client_checkout_pt_package` builds return_url server-side with both params (service.py:549-554); `CheckoutSheet.jsx:78-85` now just `window.location.href = result.confirmationUrl`; commit `89b62486` |
| CR-03: BookScreen sent `pt_package_id: ''` causing always-422 | BLOCKER | FIXED | `ClientCreateBookingRequest.pt_package_id: UUID | None = None` (schemas.py:138); service resolves active package via `get_active_pt_package` when None (service.py:291-294); BookScreen.jsx:164 omits `ptPackageId`; commit `263c0f57` |
| WR-01: email gate ran before replay check | WARNING | FIXED | Replay check moved before email gate in `_sell_subject_core` (service.py:229); regression test `test_membership_replay_returns_original_confirmation_url` (line 769); commit `0417fddb` |
| WR-02: `str(r.confirmation_url)` emitted literal "None" | WARNING | FIXED | Guard `if r.confirmation_url is None: raise BadGatewayAppError(...)` added to both checkout functions (service.py:519-521, 567-569); regression test `test_checkout_confirmation_url_none_raises_bad_gateway` (line 841); commit `7516f9a1` |

4 regression tests added to test_checkout.py (commit `8dc4e333`) locking the fix behavior.

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/modules/online_payments/service.py` | `_sell_subject_core` actor-agnostic helper | VERIFIED | `async def _sell_subject_core` at line 170; accepts `actor_user_id: UUID | None`, `idempotency_key: str`, `return_url_override: str | None`; no amount param (CPAY-03) |
| `apps/backend/app/core/dependencies.py` | Protocol slot triplet | VERIFIED | `SellSubjectCoreCallable` at line 1660; `_client_checkout_core` at 1673; `register_client_checkout_core` at 1676; `invoke_client_checkout_core` at 1687; no runtime import of `app.modules.online_payments` |
| `apps/backend/app/main.py` | Composition-root wiring | VERIFIED | `register_client_checkout_core(_sell_subject_core)` at line 601 |
| `apps/backend/app/modules/client_portal/schemas.py` | Checkout + status schemas | VERIFIED | `ClientCheckoutRequest` (line 238), `ClientCheckoutResponse` with `online_payment_id` + `confirmation_url` (line 246), `ClientPaymentStatusResponse` with `id` + `status` (line 253) |
| `apps/backend/app/modules/client_portal/repository.py` | IDOR-safe raw-SQL status reader | VERIFIED | `fetch_client_payment_status` at line 493; SQL `SELECT id, status FROM online_payments WHERE id = :payment_id AND client_id = :client_id`; no ORM import of OnlinePayment |
| `apps/backend/app/modules/client_portal/service.py` | Client checkout service functions | VERIFIED | `client_checkout_membership` (line 481), `client_checkout_pt_package` (line 528), `get_client_payment_status` (line 576); all checkout calls use `actor_user_id=None`; WR-02 guards at lines 519-521, 567-569 |
| `apps/backend/app/modules/client_portal/router.py` | Three client endpoints | VERIFIED | `POST /checkout/memberships/{plan_id}` (line 554, op_id `client_checkout_membership`, CSRF); `POST /checkout/pt-packages/{plan_id}` (line 589, CSRF, `Idempotency-Key` header); `GET /payments/{payment_id}/status` (line 629, no CSRF) |
| `apps/backend/tests/integration/client_portal/test_checkout.py` | 11 integration tests (7 original + 4 regression) | VERIFIED | 11 test functions confirmed; all 5 success criteria covered; duplicate-webhook, IDOR 404, anti-oracle projection, 422 email gate, idempotency replay, return_url payload, None guard |
| `packages/api-client/src/schema.d.ts` | Client checkout + status paths typed | VERIFIED | `/api/v1/client/checkout/memberships/{plan_id}` at line 2892; `/api/v1/client/checkout/pt-packages/{plan_id}` at line 2920; `/api/v1/client/payments/{payment_id}/status` at line 2948 |
| `apps/client-pwa/src/lib/queryClient.ts` | QueryClient with admin-web defaults | VERIFIED | `staleTime: 30_000`, `refetchOnWindowFocus: false`, `retry: 1/0`, session-expiry handler via `window.location.replace('/login')` |
| `apps/client-pwa/src/lib/clientQueries.ts` | 14 typed hooks over clientFetcher | VERIFIED | `clientPortalKeys` factory; `useClientHome`, `useClientPlans`, `useClientPtPackages`, `useClientVisitHistory`, `useClientPtHistory`, `useClientPaymentHistory`, `useClientPaymentStatus` (polling, refetchInterval 3000ms while pending), `useClientCheckoutMembership`, `useClientCheckoutPtPackage`, `useClientBookings`, `useClientAvailableSlots`, `useCreateBooking`, `useCancelBooking`, `useClientQrToken` (staleTime:0, refetchInterval:50s) |
| `apps/client-pwa/src/data/index.js` | Single swap seam re-exporting hooks | VERIFIED | Re-exports all query hooks; retains legacy mocks (CALENDAR/TRAINERS/UPCOMING_BOOKING/VISIT_HISTORY/TRAINING_HISTORY) for non-wired consumers (BookingManageSheet, HistorySheets, TweaksRoot) |
| `apps/client-pwa/src/components/ComingSoon.tsx` | "В разработке" placeholder | VERIFIED | Renders "В разработке" at line 31; no clientFetcher/clientQueries/@tanstack imports |
| `apps/client-pwa/eslint.config.js` | Import boundary for net-new screens | VERIFIED | `no-restricted-paths` at line 87; targets ChatScreen, ReferralSheet, TrainerDetailSheet, NotificationsSheet, GymInfoSheet; bars clientFetcher, clientQueries, data/index.js |
| `apps/client-pwa/src/routes/PaymentReturnScreen.jsx` | Anti-oracle polling return screen | VERIFIED | `useClientPaymentStatus(paymentId, !!paymentId)` at line 26; "Ожидаем подтверждение..." rendered while pending (line 80); `<Navigate to="/" replace />` only on `status === 'succeeded'` (line 31) |
| `apps/client-pwa/src/App.jsx` | QueryClientProvider root wrap + /payment/return route | VERIFIED | `QueryClientProvider` at line 198 wraps the router; `/payment/return` route at line 227 |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/main.py` | `app/modules/online_payments/service.py` | `register_client_checkout_core(_sell_subject_core)` | WIRED | Confirmed at main.py:601 |
| `app/core/dependencies.py` | client_portal service | `invoke_client_checkout_core` Protocol slot | WIRED | No runtime import of online_payments in dependencies.py (confirmed zero matches) |
| `app/modules/client_portal/service.py` | `app/core/dependencies.py` | `invoke_client_checkout_core` | WIRED | service.py imports and calls invoke_client_checkout_core with actor_user_id=None |
| `app/modules/client_portal/repository.py` | online_payments table | raw-SQL WHERE id=:payment_id AND client_id=:client_id | WIRED | Confirmed at repository.py:514-515 |
| `apps/client-pwa/src/screens/HomeScreen.jsx` | `useClientHome` | import from @/data | WIRED | HomeScreen.jsx:9 imports useClientHome |
| `apps/client-pwa/src/screens/ProfileScreen.jsx` | `useClientVisitHistory\|useClientPtHistory\|useClientPaymentHistory` | import from @/data | WIRED | ProfileScreen.jsx:8-10 |
| `apps/client-pwa/src/routes/PaymentReturnScreen.jsx` | `useClientPaymentStatus` | polling hook + react-router useSearchParams payment_id | WIRED | PaymentReturnScreen.jsx:15,26 |
| `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx` | `window.location.href = result.confirmationUrl` | checkout mutation result | WIRED | CheckoutSheet.jsx:74,85 |
| `apps/client-pwa/src/App.jsx` | `apps/client-pwa/src/lib/queryClient.ts` | QueryClientProvider wrapping router | WIRED | App.jsx:3,17,198,404 |
| `apps/client-pwa/src/screens/BookScreen.jsx` | `useClientAvailableSlots / useCreateBooking / useCancelBooking` | import from @/data | WIRED | BookScreen.jsx:10,61-63 |
| `apps/client-pwa/src/screens/sheets/QRSheet.jsx` | `useClientQrToken` | import from @/data | WIRED | QRSheet.jsx:4,12 |
| `apps/backend/openapi.json` | `packages/api-client/src/schema.d.ts` | pnpm codegen (openapi-typescript) | WIRED | schema.d.ts contains all three client paths at lines 2892, 2920, 2948 |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `HomeScreen.jsx` | `homeData` | `useClientHome()` → `clientRequest('get', '/api/v1/client/home')` | Yes — DB-backed FastAPI endpoint | FLOWING |
| `ProfileScreen.jsx` | visit/pt/payment history | `useClientVisitHistory/Pt/Payment()` → `/api/v1/client/history/*` | Yes — DB-backed Phase-69 endpoints | FLOWING |
| `PlansSheet.jsx` | `membershipPlans`, `ptPackages` | `useClientPlans/PtPackages()` → `/api/v1/client/plans`, `/api/v1/client/pt-packages` | Yes — DB-backed catalog endpoints | FLOWING |
| `CheckoutSheet.jsx` | `result.confirmationUrl` | `mutateAsync` → `invoke_client_checkout_core` → ЮKassa API | Yes — real payment creation | FLOWING |
| `PaymentReturnScreen.jsx` | `data.status` | `useClientPaymentStatus` → `fetch_client_payment_status` → SQL on online_payments | Yes — real DB read | FLOWING |
| `BookScreen.jsx` | `slotsData` | `useClientAvailableSlots()` → `/api/v1/client/slots` | Yes — Phase-70 DB-backed endpoint | FLOWING |
| `QRSheet.jsx` | `qrData.token` | `useClientQrToken()` → `/api/v1/client/qr-token` | Yes — Phase-70 signed JWT | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `_sell_subject_core` function exists and is actor-agnostic | `grep -n "async def _sell_subject_core" service.py` | Found at line 170 | PASS |
| Protocol slot raises RuntimeError when unregistered | `grep -n "slot not registered" dependencies.py` | Found at line 1704 | PASS |
| Fetch client payment status SQL filters by client_id | `grep "client_id = :client_id" repository.py` | Found in fetch_client_payment_status | PASS |
| PWA polling hook uses refetchInterval | `grep "refetchInterval.*3_000\|3000" clientQueries.ts` | Found at line 314 | PASS |
| Service worker denylist blocks /api/* | `grep "navigateFallbackDenylist.*api" vite.config.js` | Found at line 15 | PASS |
| 4 regression tests for review fixes exist | `grep "def test_membership_checkout_return_url\|def test_pt_checkout_return_url\|def test_membership_replay_returns\|def test_checkout_confirmation_url_none" test_checkout.py` | All 4 found | PASS |

---

### Probe Execution

Step 7c: SKIPPED — no probe-*.sh scripts declared in phase plans. Backend integration tests were run by the executor (pytest exits 0 per SUMMARY) and are not re-runnable here without a live DB/Redis.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CPAY-01 | 71-01, 71-02, 71-03 | Client initiates membership purchase via ЮKassa | SATISFIED | `POST /api/v1/client/checkout/memberships/{plan_id}` returns 201 + confirmationUrl; tested in test_checkout.py |
| CPAY-02 | 71-01, 71-02, 71-03 | Client purchases PT-package via ЮKassa | SATISFIED | `POST /api/v1/client/checkout/pt-packages/{plan_id}` + Idempotency-Key header; tested |
| CPAY-03 | 71-01, 71-02, 71-03, 71-05 | Server-side price; webhook-only activation; anti-oracle redirect-back | SATISFIED | No price param in schemas; PaymentReturnScreen shows only pending copy; test_status_returns_coarse_state_only asserts id+status only |
| CPAY-04 | 71-01, 71-02, 71-03 | 422 client_email_required_for_online_payment when no email | SATISFIED | Email gate in _sell_subject_core (after WR-01 fix); test_checkout_without_email_returns_422 |
| CPAY-05 | 71-01, 71-02, 71-03 | Idempotent checkout (no double-charge) | SATISFIED | Membership: server-derived per-day key; PT: client-supplied Idempotency-Key header; duplicate-webhook test; replay tests |
| PWA-05 | 71-04, 71-05, 71-06 | Home/Profile/Book/Plans/Checkout/QR wired to real backend | SATISFIED | All 6 screens verified with real hooks; mock data layer replaced for wired screens |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `apps/client-pwa/src/lib/queryClient.ts` | 34 | `setTimeout(() => { _redirecting = false }, 5000)` — magic 5000ms timer reset (WR-03 from review, not fixed) | Warning | Minor robustness concern on auth path; no correctness defect today |
| `apps/client-pwa/src/lib/clientQueries.ts` | 186 | `queryKey: clientPortalKeys.bookings()` — page not in cache key (WR-06 from review, not fixed) | Warning | Stale data risk when paginating bookings; BookScreen currently doesn't paginate so no immediate user impact |
| `apps/client-pwa/src/routes/PaymentReturnScreen.jsx` | 24 | `const _idempotencyKey = params.get('idempotency_key')` — read but never used (IN-01, not fixed) | Info | Dead code; underscore prefix suppresses lint; no behavioral impact |
| `apps/backend/app/modules/client_portal/router.py` | 192 | `service._get_client_next_booking` — router calls private service function (WR-04, not fixed) | Warning | Layering violation; paginated bookings list returns max-1 item — `useClientBookings` hook exists but is unused in BookScreen, which builds its view from slots only |

No TBD/FIXME/XXX debt markers found in any phase-71-modified files.

---

### Human Verification Required

The automated checks pass for all 5 success criteria. The following items require live browser or staging environment verification:

#### 1. ЮKassa Redirect Round-Trip (criterion #1 end-to-end)

**Test:** Log in as a client with an email address set. Open Plans → select a membership → proceed to CheckoutSheet → tap "Оплатить". Verify redirect to ЮKassa. Complete or cancel payment in ЮKassa sandbox. Confirm browser returns to `/payment/return?payment_id=<UUID>`.
**Expected:** While payment is `pending`, the screen shows only "Ожидаем подтверждение..." and the spinner. On webhook delivery of `payment.succeeded`, the screen transitions to Home where the active membership is displayed. No activation state is shown in CheckoutSheet or the return screen before the webhook fires.
**Why human:** End-to-end ЮKassa redirect requires a live or sandbox payment account; cannot be faked with ASGITransport alone.

#### 2. Service Worker Does Not Cache /api/* (criterion #5 partial)

**Test:** Open the PWA in Chrome DevTools. Navigate through all 6 wired screens. Open Application → Cache Storage → inspect all named caches.
**Expected:** Zero /api/* entries in any cache. Only static assets (JS bundles, CSS, icons) are cached.
**Why human:** SW cache inspection requires a running browser runtime; vite.config.js config has been verified (navigateFallbackDenylist + empty runtimeCaching) but runtime behavior needs confirmation.

#### 3. Net-New Screens Make Zero API Calls (criterion #5)

**Test:** Open each of the 5 net-new screens (Chat, Referral, TrainerDetail, Notifications, GymInfo). In DevTools → Network filter by XHR/Fetch, confirm no /api/* requests fire.
**Expected:** Each screen renders "В разработке" card only. Network tab is empty of API requests from these screens.
**Why human:** Absence-of-network-call cannot be asserted by code grep alone; ESLint boundary is structural but runtime confirmation is standard for a shipping verification.

---

### Gaps Summary

No blockers found. All 3 critical review findings (CR-01, CR-02, CR-03) have been fixed and confirmed in code. Both warning-level fixes (WR-01, WR-02) have been applied. Four regression tests lock the fixes.

Remaining unfixed items from the review (WR-03, WR-04, WR-05, WR-06, IN-01, IN-05) are non-blocking for the phase goal:
- WR-04 (`client_list_bookings` max-1 pagination): `useClientBookings` is exported but unused in BookScreen (which derives its view from real slots data). The BookScreen success criterion (SC #4: "Book screen fetches from real backend") is met via `useClientAvailableSlots`.
- WR-06 (bookings cache key missing page): No user impact until BookScreen adds pagination.
- WR-03, WR-05: Minor robustness/efficiency issues, no correctness defect.

The only items pending are 3 human verifications requiring a live PWA session.

---

_Verified: 2026-05-30T18:00:00Z_
_Verifier: Claude (gsd-verifier)_
