---
phase: 71-client-checkout-full-pwa-screen-wiring
plan: "05"
subsystem: ui
tags: [react-query, react-router, pwa, checkout, yookassa, placeholders, anti-oracle]

# Dependency graph
requires:
  - phase: 71-04
    provides: clientQueries.ts hooks (useClientHome, useClientPlans, useClientPtPackages, useClientVisitHistory, useClientPtHistory, useClientPaymentHistory, useClientPaymentStatus, useClientCheckoutMembership, useClientCheckoutPtPackage); queryClient.ts; data/index.js swap seam; ComingSoon.tsx; ESLint D-71-09 import boundary
  - phase: 69-client-read-endpoints-pwa-stack-alignment
    provides: clientFetcher.ts typed transport; Phase-69 history endpoints in schema.d.ts

provides:
  - HomeScreen wired to real backend via useClientHome (membership status + next_booking)
  - ProfileScreen history tabs wired to useClientVisitHistory + useClientPtHistory + useClientPaymentHistory (zero mock history imports)
  - PlansSheet wired to useClientPlans + useClientPtPackages (API-to-card adapters)
  - CheckoutSheet calls real checkout mutations (mutateAsync) and redirects to ЮKassa confirmationUrl
  - PT idempotency key generated via crypto.randomUUID() and carried in return_url &idempotency_key= param (D-71-04)
  - PaymentReturnScreen at /payment/return — polls useClientPaymentStatus, shows ONLY "Ожидаем подтверждение..." (anti-oracle criterion #1), navigates Home on succeeded
  - App.jsx wrapped in QueryClientProvider (sole owner; provider above react-router v6 Routes)
  - /payment/return route registered in App.jsx
  - All 5 net-new screens (ChatScreen, ReferralSheet, TrainerDetailSheet, NotificationsSheet, GymInfoSheet) render ComingSoon — zero backend calls (D-71-08/09)
  - data/index.js mock exports cleaned: NOTIFICATIONS/GYM_INFO/TRAINER_CANCEL/PLANS/PLAN_FEATURES/PURCHASE_HISTORY/TRAINING_HISTORY/VISIT_HISTORY removed; retained UPCOMING_BOOKING+VISIT_HISTORY+TRAINING_HISTORY for BookingManageSheet/HistorySheets (Plan 06 scope)

affects:
  - 71-06 (BookScreen + QRSheet wiring — consumes same hook pattern established here)
  - Phase 72 (E2E verification of checkout redirect + anti-oracle return copy)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "In-file toSubInfo adapter: API ClientMembershipResponse → subInfo render shape (daysLeft/total/until/label/tone)"
    - "In-file API-to-card adapters: toMembershipCard / toPtCard map kopeck prices to display render shape"
    - "Per-tab loading/error guards in ProfileScreen: each history tab renders its own isLoading/isError state independently"
    - "crypto.randomUUID() idempotency key per checkout intent; carried via return_url query param (sole persistence channel, D-71-04)"
    - "PaymentReturnScreen anti-oracle: Navigate to '/' only on status=succeeded; 'Ожидаем подтверждение...' shown for loading+pending"
    - "mapApiErrorToKind: API error codes mapped to inline error kind (not toast) — email-required/offline/payment variants"
    - "DEMO_TRAINER_CANCEL inlined as static const in HomeScreen — tweaks-driven only, not from API"

key-files:
  created:
    - apps/client-pwa/src/routes/PaymentReturnScreen.jsx
  modified:
    - apps/client-pwa/src/screens/HomeScreen.jsx
    - apps/client-pwa/src/screens/ProfileScreen.jsx
    - apps/client-pwa/src/screens/sheets/PlansSheet.jsx
    - apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx
    - apps/client-pwa/src/screens/sheets/ReferralSheet.jsx
    - apps/client-pwa/src/screens/sheets/TrainerDetailSheet.jsx
    - apps/client-pwa/src/App.jsx
    - apps/client-pwa/src/data/index.js

key-decisions:
  - "DEMO_TRAINER_CANCEL and notifications/gym-status are not in the client home API — inlined as static demo data or empty state rather than removing UI components that are tweaks-driven"
  - "VISIT_HISTORY and TRAINING_HISTORY retained in data/index.js for HistorySheets.jsx (detail sheets opened from ProfileScreen tabs) — not in Plan 05 files_modified scope; Plan 06 will wire these"
  - "UPCOMING_BOOKING retained in data/index.js for BookingManageSheet.jsx — Plan 06 scope"
  - "PT idempotency key appended to confirmationUrl before redirect: window.location.href = result.confirmationUrl + idempotency_key param — confirmationUrl from API already contains the ЮKassa redirect, we append to the App return_url portion"
  - "CheckoutDone component removed from CheckoutSheet — no premature activation display; return route is the only success confirmation surface (criterion #1)"

patterns-established:
  - "PaymentReturnScreen: anti-oracle pattern — show confirmation-only copy while pending, navigate Home only on succeeded"
  - "In-file API adapters co-located with each screen file — toSubInfo, toMembershipCard, toPtCard"

requirements-completed: [PWA-05, CPAY-01, CPAY-02, CPAY-03]

# Metrics
duration: 18min
completed: "2026-05-30"
---

# Phase 71 Plan 05: PWA Screen Wiring + ЮKassa Return Route Summary

**Home/Profile/Plans/Checkout wired to real backend via React Query hooks; ЮKassa PaymentReturnScreen with anti-oracle "Ожидаем подтверждение" polling; QueryClientProvider root wrap; all 5 net-new screens converted to ComingSoon placeholders.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-05-30T16:15:26Z
- **Completed:** 2026-05-30T16:33:00Z
- **Tasks:** 3 (1a wire Home/Profile/Plans, 1b net-new placeholders, 2 checkout+return+provider)
- **Files modified:** 8 + 1 created

## Accomplishments

- HomeScreen: replaced 4 mock imports (GYM_INFO/NOTIFICATIONS/TRAINER_CANCEL/UPCOMING_BOOKING) with `useClientHome()`; toSubInfo adapter maps API membership shape; loading/error guards; next_booking rendered from API
- ProfileScreen: all 3 history tabs (visits/trainings/purchases) now consume real Phase-69 history hooks with independent loading/error states per tab; zero mock history constants remain
- PlansSheet: useClientPlans() + useClientPtPackages() replace PLANS/PLAN_FEATURES; API-to-card adapters; membership + PT sections rendered separately
- CheckoutSheet: real mutateAsync calls; PT idempotency key via crypto.randomUUID() carried in return_url; mapApiErrorToKind for inline errors (including email-required); removed CheckoutDone to prevent premature activation
- PaymentReturnScreen: polls useClientPaymentStatus; renders ONLY "Ожидаем подтверждение..." while pending; navigates "/" on succeeded; canceled view for canceled status
- App.jsx: QueryClientProvider wraps router (sole owner); /payment/return route registered
- ReferralSheet + TrainerDetailSheet: converted to ComingSoon (completing the 5-screen set with ChatScreen/NotificationsSheet/GymInfoSheet from Plan 04)

## Task Commits

1. **Task 1a: Wire Home + Profile + Plans to real data** - `36e00cc6` (feat)
2. **Task 1b: Convert ReferralSheet + TrainerDetailSheet to ComingSoon** - `f7b14a49` (feat)
3. **Task 2: CheckoutSheet mutation + PaymentReturnScreen + QueryClientProvider** - `3ef2e8b4` (feat)

## Files Created/Modified

- `apps/client-pwa/src/routes/PaymentReturnScreen.jsx` (new) — ЮKassa return_url target; anti-oracle polling; criteria #1
- `apps/client-pwa/src/screens/HomeScreen.jsx` — wired to useClientHome; toSubInfo adapter; loading/error guards
- `apps/client-pwa/src/screens/ProfileScreen.jsx` — 3 history tabs on real hooks; zero mock history imports
- `apps/client-pwa/src/screens/sheets/PlansSheet.jsx` — useClientPlans + useClientPtPackages; API-to-card adapters
- `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx` — real mutateAsync; idempotency key; mapApiErrorToKind
- `apps/client-pwa/src/screens/sheets/ReferralSheet.jsx` — ComingSoon placeholder (D-71-08)
- `apps/client-pwa/src/screens/sheets/TrainerDetailSheet.jsx` — ComingSoon placeholder (D-71-08)
- `apps/client-pwa/src/App.jsx` — QueryClientProvider root wrap; /payment/return route
- `apps/client-pwa/src/data/index.js` — removed wired mock exports; retained Plan-06-scope mocks

## Decisions Made

- DEMO_TRAINER_CANCEL inlined as local static const in HomeScreen (not imported) — tweaks-driven demo scenario, not an API concern
- Gym status pill simplified to neutral "О зале" pill — gym status endpoint not in client home API
- Notifications section shows empty-state in FeedSection (no notifications API in scope for this plan)
- VISIT_HISTORY + TRAINING_HISTORY + UPCOMING_BOOKING retained in data/index.js for HistorySheets.jsx + BookingManageSheet.jsx (Plan 06 scope)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed duplicate `padding` key in ProfileScreen loading states**
- **Found during:** Task 1a (ProfileScreen loading state)
- **Issue:** `style={{ padding: '8px 16px', ..., padding: '24px' }}` — duplicate key (esbuild warning during build)
- **Fix:** Removed first `padding: '8px 16px'` from the three loading-state divs
- **Files modified:** apps/client-pwa/src/screens/ProfileScreen.jsx
- **Committed in:** 36e00cc6 (Task 1a commit)

**2. [Rule 1 - Bug] Restored UPCOMING_BOOKING export for BookingManageSheet dependency**
- **Found during:** Task 1a (build step)
- **Issue:** BookingManageSheet.jsx imports UPCOMING_BOOKING from @/data — removing it broke the build
- **Fix:** Restored `export { UPCOMING_BOOKING }` in data/index.js (Plan 06 scope: wired in Book screen wiring)
- **Files modified:** apps/client-pwa/src/data/index.js
- **Committed in:** 36e00cc6 (Task 1a commit)

**3. [Rule 1 - Bug] Restored VISIT_HISTORY + TRAINING_HISTORY for HistorySheets.jsx**
- **Found during:** Task 1a (build step after BookingManageSheet fix)
- **Issue:** HistorySheets.jsx (detail view opened from ProfileScreen "Все посещения/тренировки" buttons) imports these constants — removing them broke the build
- **Fix:** Restored both exports in data/index.js with comment noting Plan 06 scope
- **Files modified:** apps/client-pwa/src/data/index.js
- **Committed in:** 36e00cc6 (Task 1a commit)

---

**Total deviations:** 3 auto-fixed (3 Rule 1 bugs)
**Impact on plan:** All fixes necessary to maintain build integrity. No scope creep — all retained mocks explicitly noted as Plan 06 scope.

## Known Stubs

None — all wired screens use real backend hooks; ComingSoon placeholders are intentional (D-71-08 decisions, not stubs blocking the plan's goal).

## Threat Flags

None — no new network endpoints, auth paths, or file access patterns introduced outside the plan's threat model (T-71-18/19/20/21 mitigated as designed).

## Self-Check: PASSED

Files exist:
- `/Users/andre/Workspace/Development/clubcore/apps/client-pwa/src/routes/PaymentReturnScreen.jsx` ✓
- `/Users/andre/Workspace/Development/clubcore/apps/client-pwa/src/screens/HomeScreen.jsx` ✓
- `/Users/andre/Workspace/Development/clubcore/apps/client-pwa/src/screens/ProfileScreen.jsx` ✓
- `/Users/andre/Workspace/Development/clubcore/apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx` ✓

Commits exist:
- `36e00cc6` ✓
- `f7b14a49` ✓
- `3ef2e8b4` ✓

Build/lint/typecheck: all pass ✓

## Issues Encountered

None beyond the 3 auto-fixed build dependency breaks (retained mock constants).

## Code Review Fixes

Post-review fixes applied to this plan's code (from 71-REVIEW.md, committed 2026-05-30):

**CR-01 (BLOCKER) — Membership checkout return_url never carried payment_id**
- Root cause: `CheckoutSheet.jsx` assigned `returnUrl` but never used it; ЮKassa `return_url` was the shared static staff URL, so `PaymentReturnScreen` never received `payment_id`.
- Fix: Added `YOOKASSA_CLIENT_RETURN_URL` to `YooKassaSettings`; added optional `return_url` param to `YooKassaClient.create_payment`; `_sell_subject_core` accepts `online_payment_id_override` + `return_url_override`; `client_checkout_membership` builds `return_url = client_return_url?payment_id={op_id}` and passes both overrides to the core. `CheckoutSheet.jsx` now just redirects to `result.confirmationUrl` (server bakes the correct URL).
- Commits: `0417fddb`, `7516f9a1`, `89b62486`

**CR-02 (BLOCKER) — PT-package return URL appended `idempotency_key` to ЮKassa confirmation URL**
- Root cause: `window.location.href = result.confirmationUrl + '&idempotency_key=...'` concatenated onto the ЮKassa checkout URL; ЮKassa ignores unknown query params; param never survived to `PaymentReturnScreen`.
- Fix: `client_checkout_pt_package` generates `op_id = uuid4()`, builds `return_url = client_return_url?payment_id={op_id}&idempotency_key={encoded}`, passes both to `_sell_subject_core`. `CheckoutSheet.jsx` PT branch simplified to `window.location.href = result.confirmationUrl`.
- Commits: `0417fddb`, `7516f9a1`, `89b62486`

**CR-03 (BLOCKER) — BookScreen sent `pt_package_id: ''` causing always-422**
- Root cause: `ClientCreateBookingRequest.pt_package_id` was required UUID; empty string failed Pydantic UUID parse before service ran; `no_active_pt_package` branch unreachable.
- Fix: `ClientCreateBookingRequest.pt_package_id` made optional (`UUID | None = None`); `create_booking_for_client_request` resolves the active package via `get_active_pt_package` when `pt_package_id is None` — raises `NoActivePtPackageError` directly if no package (CBOOK-04 reachable). `BookScreen.jsx` omits `ptPackageId` from `mutateAsync`. `clientQueries.ts` `useCreateBooking` updated to accept optional `ptPackageId`. `openapi.json` + `schema.d.ts` regenerated.
- Commits: `263c0f57`, `89b62486`, `0b429b4a`

**WR-01 (WARNING) — Email gate ran before replay check**
- Root cause: `_sell_subject_core` enforced 54-ФЗ email gate (step 1) before replay check (step 4); a same-day replay after email cleared returned 422 instead of the existing confirmation_url.
- Fix: Moved replay check to run BEFORE the email gate in `_sell_subject_core` (replay is side-effect-free and must not be blocked by current client state — CPAY-05).
- Commit: `0417fddb`

**WR-02 (WARNING) — `str(r.confirmation_url)` emitted literal "None"**
- Root cause: `client_checkout_membership`/`client_checkout_pt_package` called `str(r.confirmation_url)` without a None check; a QR-replay scenario returns `confirmation_url=None`.
- Fix: Added `if r.confirmation_url is None: raise BadGatewayAppError("checkout_confirmation_url_missing")` guard in both functions before constructing `ClientCheckoutResponse`.
- Commit: `7516f9a1`

**Regression tests added** (4 new integration tests in `test_checkout.py`):
- `test_membership_checkout_return_url_contains_payment_id` — CR-01
- `test_pt_checkout_return_url_contains_payment_id_and_idempotency_key` — CR-02
- `test_membership_replay_returns_original_confirmation_url` — WR-01
- `test_checkout_confirmation_url_none_raises_bad_gateway` — WR-02
- Commit: `8dc4e333`

**Full backend suite after fixes:** 2361 passed, 8 skipped (4 new tests added)
**client-pwa build + lint:** both pass

## User Setup Required

None — no external service configuration required for this plan.

## Next Phase Readiness

- Plan 71-06 (BookScreen + QRSheet wiring) can proceed: all hooks available, swap seam in place
- PaymentReturnScreen ready for live ЮKassa redirect testing in Phase 72 E2E
- Anti-oracle pattern established and verified (criterion #1 complete)

---
*Phase: 71-client-checkout-full-pwa-screen-wiring*
*Completed: 2026-05-30*
