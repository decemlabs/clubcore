---
phase: 71-client-checkout-full-pwa-screen-wiring
reviewed: 2026-05-30T00:00:00Z
depth: standard
files_reviewed: 27
files_reviewed_list:
  - apps/backend/app/modules/online_payments/service.py
  - apps/backend/app/core/dependencies.py
  - apps/backend/app/main.py
  - apps/backend/app/modules/client_portal/schemas.py
  - apps/backend/app/modules/client_portal/repository.py
  - apps/backend/app/modules/client_portal/service.py
  - apps/backend/app/modules/client_portal/router.py
  - apps/backend/tests/integration/client_portal/test_checkout.py
  - apps/backend/tests/integration/client_portal/conftest.py
  - apps/client-pwa/src/lib/queryClient.ts
  - apps/client-pwa/src/lib/clientQueries.ts
  - apps/client-pwa/src/data/index.js
  - apps/client-pwa/src/components/ComingSoon.tsx
  - apps/client-pwa/eslint.config.js
  - apps/client-pwa/src/App.jsx
  - apps/client-pwa/src/routes/PaymentReturnScreen.jsx
  - apps/client-pwa/src/screens/HomeScreen.jsx
  - apps/client-pwa/src/screens/ProfileScreen.jsx
  - apps/client-pwa/src/screens/BookScreen.jsx
  - apps/client-pwa/src/screens/ChatScreen.jsx
  - apps/client-pwa/src/screens/sheets/PlansSheet.jsx
  - apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx
  - apps/client-pwa/src/screens/sheets/QRSheet.jsx
  - apps/client-pwa/src/screens/sheets/ReferralSheet.jsx
  - apps/client-pwa/src/screens/sheets/TrainerDetailSheet.jsx
  - apps/client-pwa/src/screens/sheets/NotificationsSheet.jsx
  - apps/client-pwa/src/screens/sheets/GymInfoSheet.jsx
findings:
  critical: 3
  warning: 6
  info: 5
  total: 14
status: issues_found
---

# Phase 71: Code Review Report

**Reviewed:** 2026-05-30
**Depth:** standard
**Files Reviewed:** 27
**Status:** issues_found

## Summary

Phase 71 wires client checkout (ЮKassa redirect) plus full PWA screen wiring. The
backend anti-oracle status contract, IDOR 404-collapse, 54-ФЗ email gate, and the
ESLint import boundary for net-new screens are all implemented correctly and are
covered by tests. The defect surface is concentrated in the **PWA frontend
checkout-return round-trip**, where the redirect flow that is supposed to deliver
`payment_id` to the polling screen is broken: the return URL is never wired into the
ЮKassa redirect, so `PaymentReturnScreen` cannot poll and the anti-oracle "ожидаем
подтверждение" → "succeeded" → Home progression never completes. A second BLOCKER is
in `BookScreen`, which sends an empty-string `pt_package_id` to a required-UUID field
(guaranteed 422, not the `no_active_pt_package` path the code is written to handle).

The backend service/repository/router layer is solid; most remaining findings are
frontend correctness and dead-code issues.

## Critical Issues

### CR-01: Membership checkout never passes `payment_id` to the return screen — polling/anti-oracle flow is dead

**File:** `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx:66-74`
**Issue:** In the `kind === 'sub'` branch, `returnUrl` is built (`${origin}/payment/return?payment_id=`) and then **never used**. The code redirects directly to `result.confirmationUrl` (the ЮKassa hosted page). The ЮKassa `confirmation_url` does not carry the app's `payment_id`. When ЮKassa redirects the user back to the app's configured `return_url`, `PaymentReturnScreen` reads `params.get('payment_id')` — which will be absent — so `useClientPaymentStatus(null, false)` never fires and the screen permanently renders "Неверная ссылка возврата — payment_id не найден." The `onlinePaymentId` returned by the mutation (the only correct source) is discarded. This defeats Phase 71 criterion #1 (anti-oracle return-back polling) for the membership flow.
**Fix:** The return URL (with `payment_id` from `result.onlinePaymentId`) must be the ЮKassa `return_url`, which is configured server-side at payment creation time, not appended client-side. Either (a) have the backend embed the PWA return URL with `payment_id` as the ЮKassa `return_url` when creating the payment, or (b) persist `result.onlinePaymentId` client-side (e.g. via the return URL the server already configured) so `PaymentReturnScreen` can recover it. At minimum, stop discarding `onlinePaymentId`:
```js
result = await checkoutMembership.mutateAsync({ planId: ctx.planId })
// payment_id must reach /payment/return — currently it does not.
window.location.href = result.confirmationUrl
```

### CR-02: PT-package return URL appends `idempotency_key` to the ЮKassa confirmation URL, not the app return URL

**File:** `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx:78-85`
**Issue:** `window.location.href = result.confirmationUrl + '&idempotency_key=...'` appends a query param to the **ЮKassa hosted checkout URL**, not to the application's `return_url`. ЮKassa ignores unknown query params on its checkout page, and the param does not survive to `PaymentReturnScreen`. The comment claims this is "the sole persistence channel" so the key survives the redirect round-trip, but it does not: after ЮKassa redirects to the server-configured `return_url`, this appended param is gone. Same root cause as CR-01: the return URL (with `payment_id` and, for PT, `idempotency_key`) must be configured as the ЮKassa `return_url` server-side. As written, the PT return/polling flow is also non-functional, and the `&` prefix produces a malformed URL when `confirmationUrl` has no existing query string.
**Fix:** Configure the ЮKassa `return_url` server-side to include `payment_id` (and `idempotency_key` for PT). Do not string-concatenate query params onto the ЮKassa confirmation URL.

### CR-03: BookScreen sends empty-string `pt_package_id` to a required UUID field — booking always 422s

**File:** `apps/client-pwa/src/screens/BookScreen.jsx:159-170`
**Issue:** `createBookingMutation.mutateAsync({ slotId: selectedSlot, ptPackageId: '', ... })` sends `pt_package_id: ''`. The backend schema `ClientCreateBookingRequest` (schemas.py:121-130) declares `pt_package_id: UUID` as a **required, non-optional** field; an empty string fails Pydantic UUID parsing and returns **422 validation error**, never reaching the booking service. The inline comment asserts "server will resolve from active package," but no such server-side resolution exists — the schema requires a valid UUID and there is no fallback. The `no_active_pt_package` error-handling branch (lines 174-182) is therefore unreachable via this path; every confirm attempt fails with a generic validation error mapped to "Не удалось создать запись."
**Fix:** Resolve the client's active PT-package id before booking (add a hook reading the active package, or add a backend endpoint), and pass a real UUID. If the contract truly intends server-side resolution, the schema must make `pt_package_id` optional and the service must resolve it from `get_active_pt_package(client_id)` — neither is currently the case.

## Warnings

### WR-01: Email gate runs before the replay check — a replay can spuriously 422 after email removal

**File:** `apps/backend/app/modules/online_payments/service.py:206-220`
**Issue:** `_sell_subject_core` enforces the 54-ФЗ email gate (step 1) and reads the plan price (step 2) **before** the idempotency replay check (step 4). If a client completes checkout (row created) and later has their `email` cleared, a same-day replay POST raises `ClientEmailRequiredForOnlinePaymentError` (422) instead of replaying the already-created `confirmation_url`. A replay should be side-effect-free and return the existing row regardless of current email state. This is an edge case but contradicts the "replay returns the same URL" contract (CPAY-05).
**Fix:** Move the replay check (`get_online_payment_by_idempotency_key`) ahead of the email gate, or skip the email gate when an existing non-canceled row is found.

### WR-02: `client_checkout_membership` / `client_checkout_pt_package` assume `confirmation_url` is non-null but the core can return null

**File:** `apps/backend/app/modules/client_portal/service.py:492-496, 524-528`
**Issue:** Both build `ClientCheckoutResponse(confirmation_url=str(r.confirmation_url), ...)`. For a **QR replay**, `_sell_subject_core` returns `SellResponse(confirmation_url=None, qr_payload=...)` (service.py:236-240). The client checkout always passes `confirmation_type="redirect"`, so a redirect row should always have a URL — but the replay branch keys only on `idempotency_key`, and if a QR row was ever created with the same server-derived membership key (e.g. a staff QR sale for the same client+plan+day), the replay returns `confirmation_url=None`, and `str(None)` yields the literal string `"None"`, which is then returned to the PWA as a redirect target. The `ClientCheckoutResponse.confirmation_url: str` schema would accept `"None"` silently.
**Fix:** Guard against `r.confirmation_url is None` and raise a domain error (e.g. `ConflictError`/`BadGatewayAppError`) rather than coercing to `str(None)`. Do not use `str()` on a possibly-None field destined for a redirect.

### WR-03: `_redirecting` flag reset on a fixed 5s timer can swallow a legitimate later redirect or fire two redirects

**File:** `apps/client-pwa/src/lib/queryClient.ts:18-36`
**Issue:** The module-scoped `_redirecting` guard is reset after a hardcoded 5000ms `setTimeout`. If `window.location.replace('/login')` has not completed navigation within 5s (slow unload, blocked navigation), the flag resets and a subsequent 401 triggers a second `replace`. Conversely the magic 5000 is unexplained. This is a minor robustness/maintainability issue on an auth-critical path.
**Fix:** Do not reset the flag on a timer; the page is navigating away. If a reset is needed for SPA-style redirects, key it off an actual navigation/route-change event rather than an arbitrary timeout, and extract the constant.

### WR-04: `client_list_bookings` calls a private service function (`service._get_client_next_booking`)

**File:** `apps/backend/app/modules/client_portal/router.py:192`
**Issue:** The router reaches into `service._get_client_next_booking` (underscore-prefixed private). Beyond the layering smell, the endpoint advertises a paginated bookings list (`PaginatedData[ClientNextBookingResponse]`) but returns at most one item (the single next booking) with `total=len(items)` (0 or 1). A PWA paginating this endpoint (clientQueries `useClientBookings` passes `page`) will silently get a max-1 list regardless of page, and `total` misreports the real count. This is a latent correctness bug for the Book screen's bookings list.
**Fix:** Add a public paginated service function backed by a real paginated repository query; do not call the private helper from the router, and return an accurate `total`.

### WR-05: ЮKassa provider re-fetched twice in the create path (replay branch + create branch)

**File:** `apps/backend/app/modules/online_payments/service.py:222-223, 264-265`
**Issue:** `get_yookassa_client_provider()` + `await provider()` is invoked in the replay branch and again in the create branch. In the non-replay path only the second runs, but the structure invites a future bug where a provider is awaited even when not needed. Minor; not a correctness defect today. Flagging because the provider call is on the hot path and the duplication is easy to mis-edit.
**Fix:** Resolve the client once near the top of the function (after the replay short-circuit decision) and reuse it.

### WR-06: `useClientBookings` ignores its `page` argument in the query key

**File:** `apps/client-pwa/src/lib/clientQueries.ts:184-195`
**Issue:** `useClientBookings(page = 1)` sends `query: { page }` to the server but keys the cache with `clientPortalKeys.bookings()` (no page). Two different pages share one cache entry, so paging will return stale data from another page until staleTime expires. Compare `useClientAvailableSlots` (line 200) which correctly includes the page in the key.
**Fix:** Include `page` in the query key: `queryKey: [...clientPortalKeys.bookings(), page]` (add a paged variant to the key factory).

## Info

### IN-01: Dead variable `_idempotencyKey` in PaymentReturnScreen

**File:** `apps/client-pwa/src/routes/PaymentReturnScreen.jsx:24`
**Issue:** `const _idempotencyKey = params.get('idempotency_key')` is read and never used (underscore-prefixed to suppress lint). Given CR-02, the key never arrives here anyway. Dead code that documents intent the implementation does not fulfill.
**Fix:** Remove, or actually consume it in a retry path.

### IN-02: Dead variable `returnUrl` in CheckoutSheet membership branch

**File:** `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx:71`
**Issue:** `const returnUrl = ...` is assigned and never referenced (root cause of CR-01). Dead code.
**Fix:** Remove once CR-01 is resolved (or wire it into the actual return-URL mechanism).

### IN-03: `extra_keys` computed but only used inside the assert message

**File:** `apps/backend/tests/integration/client_portal/test_checkout.py:510-513`
**Issue:** `extra_keys` is computed on line 510 but the assertion on 511 recomputes the set comparison independently; `extra_keys` is referenced only in the failure message. Harmless, but the double computation reads as a leftover.
**Fix:** Use `extra_keys` directly in the assertion: `assert not extra_keys, ...`.

### IN-04: HomeScreen/ProfileScreen progress bar uses a hardcoded `total: 90` denominator

**File:** `apps/client-pwa/src/screens/HomeScreen.jsx:26` and `apps/client-pwa/src/screens/ProfileScreen.jsx:27`
**Issue:** `total: 90` is a magic number duplicated across both adapters; the comment admits "server doesn't expose total days." The progress bar percentage (`daysLeft / 90`) is therefore cosmetic and can exceed/understate reality for non-90-day plans. Acceptable for a demo bar but the duplication and magic number should be a named constant.
**Fix:** Extract a shared `DEFAULT_PLAN_DAYS` constant (or compute from `start_date`/`end_date`), and share the `toSubInfo` adapter between the two screens instead of duplicating it.

### IN-05: ESLint boundary covers `.jsx` net-new screens but not the `.tsx` `ComingSoon` import target list completeness

**File:** `apps/client-pwa/eslint.config.js:87-109`
**Issue:** The `no-restricted-paths` zone blocks imports from `clientFetcher.ts`, `clientQueries.ts`, and `data/index.js` — correct for the data layer. However, the boundary does not block `@/data` (the alias form) explicitly, relying on path resolution of `./src/data/index.js`. If a net-new screen wrote `import { useClientHome } from '@/data'` (the alias actually used everywhere else in the app), confirm the resolver maps it to the same restricted path. Worth a test asserting the alias form is also caught.
**Fix:** Add a negative-test fixture importing `@/data` from one of the five screens and assert ESLint flags it, to prove the alias is covered by the zone.

---

_Reviewed: 2026-05-30_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
</content>
</invoke>
