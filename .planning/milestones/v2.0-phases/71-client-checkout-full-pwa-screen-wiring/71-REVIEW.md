---
phase: 71-client-checkout-full-pwa-screen-wiring
reviewed: 2026-05-30T00:00:00Z
depth: standard
files_reviewed: 44
files_reviewed_list:
  - apps/backend/app/core/dependencies.py
  - apps/backend/app/main.py
  - apps/backend/app/modules/client_auth/service.py
  - apps/backend/app/modules/client_portal/repository.py
  - apps/backend/app/modules/client_portal/router.py
  - apps/backend/app/modules/client_portal/schemas.py
  - apps/backend/app/modules/client_portal/service.py
  - apps/backend/app/modules/online_payments/service.py
  - apps/backend/openapi.json
  - apps/backend/scripts/seed_dev_client.py
  - apps/backend/tests/integration/client_portal/conftest.py
  - apps/backend/tests/integration/client_portal/test_checkout.py
  - apps/client-pwa/eslint.config.js
  - apps/client-pwa/package.json
  - apps/client-pwa/src/App.jsx
  - apps/client-pwa/src/components/ComingSoon.tsx
  - apps/client-pwa/src/components/LoadError.jsx
  - apps/client-pwa/src/context/AuthContext.jsx
  - apps/client-pwa/src/context/AuthContext.test.jsx
  - apps/client-pwa/src/context/RequireAuth.jsx
  - apps/client-pwa/src/context/RequireAuth.test.jsx
  - apps/client-pwa/src/data/index.js
  - apps/client-pwa/src/lib/authBus.test.tsx
  - apps/client-pwa/src/lib/authBus.ts
  - apps/client-pwa/src/lib/clientFetcher.test.tsx
  - apps/client-pwa/src/lib/clientQueries.ts
  - apps/client-pwa/src/lib/queryClient.ts
  - apps/client-pwa/src/main.jsx
  - apps/client-pwa/src/routes/PaymentReturnScreen.jsx
  - apps/client-pwa/src/screens/BookScreen.jsx
  - apps/client-pwa/src/screens/ChatScreen.jsx
  - apps/client-pwa/src/screens/HomeScreen.jsx
  - apps/client-pwa/src/screens/LoginScreen.jsx
  - apps/client-pwa/src/screens/ProfileScreen.jsx
  - apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx
  - apps/client-pwa/src/screens/sheets/GymInfoSheet.jsx
  - apps/client-pwa/src/screens/sheets/NotificationsSheet.jsx
  - apps/client-pwa/src/screens/sheets/PlansSheet.jsx
  - apps/client-pwa/src/screens/sheets/QRSheet.jsx
  - apps/client-pwa/src/screens/sheets/ReferralSheet.jsx
  - apps/client-pwa/src/screens/sheets/TrainerDetailSheet.jsx
  - packages/api-client/src/schema.d.ts
findings:
  critical: 2
  warning: 7
  info: 5
  total: 14
status: issues_found
---

# Phase 71: Code Review Report

**Reviewed:** 2026-05-30
**Depth:** standard
**Files Reviewed:** 44
**Status:** issues_found

## Summary

Phase 71 wires the client-portal checkout (CPAY-01..05), the ЮKassa redirect/return flow, the auth/login PWA shell, and replaces several net-new screens with "В разработке" placeholders. The backend cross-module discipline (Protocol slots in `core.dependencies`, raw-SQL reads, IDOR `client_id` binding, anti-oracle coarse status read) is consistent and well-tested. The login/auth-bus/RequireAuth machinery is sound and covered by unit tests.

Two correctness defects break real user flows:

1. The deterministic membership `online_payment_id` PK override collides on the **cancel-then-retry-same-day** path, raising a 500 instead of creating a new payment (BLOCKER).
2. The Plans → checkout handoff is broken: `PlansSheet` is mounted without the `onPick` prop it requires to open `CheckoutSheet`, so the primary subscription purchase path from the plans sheet dead-ends by silently closing the sheet (BLOCKER).

A cluster of warnings covers a non-functional logout button, a stuck pending-payment return screen, broken progress-bar math, browser-vs-Moscow timezone bucketing in BookScreen, and a fragile dev-OTP bypass. Most issues are in the frontend wiring layer; the backend service/repository layer is in good shape.

## Critical Issues

### CR-01: Deterministic membership payment-id override collides on same-day cancel-then-retry → 500

**File:** `apps/backend/app/modules/client_portal/service.py:501-517` (with `apps/backend/app/modules/online_payments/service.py:232,300-319`)

**Issue:** `client_checkout_membership` derives a **deterministic** per-day `op_id` from the idempotency key:

```python
idem_key = _derive_membership_idempotency_key(plan_id=plan_id, client_id=client.id)
op_id = UUID(bytes=bytes.fromhex(idem_key)[:16]) if len(idem_key) >= 32 else uuid4()
...
online_payment_id_override=op_id,
```

In `_sell_subject_core` the replay short-circuit only returns the existing row when `existing.status != "canceled"` (`online_payments/service.py:232`). If a client cancels a membership checkout and retries the same plan the same (UTC) day, the replay branch is skipped and a fresh `insert_online_payment(..., id_override=op_id)` runs. Because `op_id` is derived from the (unchanged) per-day idem_key, the INSERT reuses the **same primary key** as the canceled row → `OnlinePayment` PK collision → `IntegrityError` surfaced as a 500. (The reused `idempotency_key` would also violate `uq_online_payments_idempotency_key`.) The membership cancel-then-rebuy-same-day path is therefore broken.

Phase-71-specific: the staff membership path does not pass `id_override`, so it never hits the PK collision vector. The new deterministic PK is the regression introduced here.

**Fix:** Do not derive the PK from the idempotency key. Generate a fresh `uuid4()` and build the return_url from it (mirroring the PT path which already uses `uuid4()`):

```python
op_id = uuid4()
return_url = f"{yookassa_settings.client_return_url}?payment_id={op_id}"
```

Separately decide the intended canceled-replay semantics: if a same-day retry after cancel must succeed, the idempotency key also has to incorporate an attempt nonce (or the canceled row must be excluded from the `uq_online_payments_idempotency_key` reuse) so neither the PK nor the idempotency_key UNIQUE constraint fires.

### CR-02: Plans sheet cannot open checkout — `onPick` prop never supplied, purchase path dead-ends

**File:** `apps/client-pwa/src/App.jsx:257-262`, `apps/client-pwa/src/screens/sheets/PlansSheet.jsx:97,290-296`

**Issue:** `PlansSheet`'s confirm step calls `onPaid` → `() => { onPick && onPick(plan); onClose(); }` (PlansSheet.jsx:97). `onPick` is the only channel that propagates the chosen plan to `CheckoutSheet` (via `ui.setCheckoutCtx`). But `App.jsx` mounts the sheet without an `onPick` prop:

```jsx
<PlansSheet
  onClose={() => ui.setPlansOpen(false)}
  currentPlanId={t.subState === 'active' ? 'annual' : 'monthly'}
/>
```

So when the user taps "Перейти к оплате" in `PlanConfirm`, `onPick` is `undefined`, only `onClose()` runs, and the plans sheet closes without ever opening `CheckoutSheet` or initiating a ЮKassa checkout. The membership/PT purchase flow from the Plans sheet — a primary Phase-71 deliverable — never reaches the wired `useClientCheckoutMembership` / `useClientCheckoutPtPackage` mutations. (`BookScreen`/`TrainerDetailSheet` pass `onCheckout`, but the Plans sheet is the main subscription purchase entry point and it is broken.)

**Fix:** Pass an `onPick` in `App.jsx` that maps the selected plan to a checkout context:

```jsx
<PlansSheet
  onClose={() => ui.setPlansOpen(false)}
  currentPlanId={t.subState === 'active' ? 'annual' : 'monthly'}
  onPick={(plan) => {
    ui.setPlansOpen(false)
    ui.setCheckoutCtx({
      kind: plan.kind,        // 'sub' | 'pt'
      planId: plan.id,
      title: plan.name,
      subtitle: plan.period,
      amount: plan.priceTotal,
    })
  }}
/>
```

Confirm the `kind`/`planId`/`amount` field names match what `CheckoutSheet` reads (`ctx.kind`, `ctx.planId`, `ctx.amount`).

## Warnings

### WR-01: Logout button in Profile settings has no handler — `useAuth().logout` is never called

**File:** `apps/client-pwa/src/screens/ProfileScreen.jsx:471-479`

**Issue:** The "Выйти из аккаунта" button renders with no `onClick`. `ProfileScreen`/`SettingsList` never import or use `useAuth()`, and `App.jsx`'s `ProfileRoute` passes no logout callback. The `logout` action implemented in `AuthContext` (POST `/client/session/logout` + flip to `anon`) is unreachable from the UI, so users cannot sign out. The `AuthContext.jsx:96-105` comment claims it is "Called by ProfileScreen logout button" — that wiring is absent.

**Fix:** Wire the button:

```jsx
import { useAuth } from '@/context/AuthContext.jsx'
const { logout } = useAuth()
<button onClick={() => { void logout() }} ...>Выйти из аккаунта</button>
```

### WR-02: `PaymentReturnScreen` strands the user on "Ожидаем подтверждение..." when payment is abandoned

**File:** `apps/client-pwa/src/routes/PaymentReturnScreen.jsx:35-37,63`, `apps/client-pwa/src/lib/clientQueries.ts:366`

**Issue:** The screen shows `PaymentCanceledView` only when `data?.status === 'canceled'`. A user who abandons/cancels at ЮKassa is redirected back while the row is still `pending` (canceled status only appears after a `payment.canceled` webhook, if one arrives). The poller stops only when status is non-`pending`, and the pending view has no timeout and no manual exit button (only the canceled view has one). An abandoned-payment user sits on the spinner indefinitely.

**Fix:** Add a max-poll timeout that surfaces a "still pending / на главную" affordance, and/or a manual "На главную" button on the pending view so the user is never stuck.

### WR-03: Membership progress bar uses a hardcoded 90-day denominator → meaningless fill

**File:** `apps/client-pwa/src/screens/HomeScreen.jsx:27,118`, `apps/client-pwa/src/screens/ProfileScreen.jsx:27,94`

**Issue:** `toSubInfo` hardcodes `total: 90` ("server doesn't expose total days"), then the bar computes `pct = (sub.daysLeft / sub.total) * 100`. For any plan whose duration ≠ 90 days the bar is wrong: a 30-day plan with 30 days left shows ~33% full; a 365-day plan shows clamped 100%. The fraction does not represent remaining membership time and misleads users.

**Fix:** Compute `total` from `end_date - start_date` (both are in `ClientMembershipResponse`), or drop the progress bar in favor of the absolute days-remaining text already shown.

### WR-04: BookScreen day/today/period bucketing uses browser-local timezone, not Europe/Moscow

**File:** `apps/client-pwa/src/screens/BookScreen.jsx:16-33,384`

**Issue:** `parseSlotDate`/`parseSlotTime` use `d.toISOString().slice(0,10)`, `d.getDate()`, `d.getHours()` — all browser-local-timezone operations — and line 384 buckets slots into morning/day/evening via `new Date(s.startTime).getHours()`. CLAUDE.md pins display to `Europe/Moscow`, and sibling screens (HomeScreen `UpcomingCard`, ProfileScreen rows) correctly pass `timeZone: 'Europe/Moscow'`. For a client whose device is not on MSK, calendar day grouping, the `isToday` flag, and period bucketing are wrong — a slot can appear under the wrong calendar date.

**Fix:** Derive the day key and hour in Europe/Moscow consistently (e.g. `Intl.DateTimeFormat('ru-RU', { timeZone: 'Europe/Moscow', ... })` parts), matching the convention used elsewhere.

### WR-05: `trainerBg` throws if a slot ever lacks `trainerId`, crashing the whole BookScreen

**File:** `apps/client-pwa/src/screens/BookScreen.jsx:42-46,124`

**Issue:** `trainerBg(trainerId)` does `for (let i = 0; i < trainerId.length; i++)` with no guard, called as `trainerBg(s.trainerId)`. If any slot arrives with null/undefined `trainerId` (shape drift, partial row), `.length` on `undefined` throws and crashes the entire BookScreen render — there is no error boundary around it.

**Fix:** `const s = String(trainerId ?? '')` (or early-return a default color when falsy) before hashing.

### WR-06: Dev-pinned OTP `"111111"` guarded only by `environment == "dev"` — auth-bypass blast radius

**File:** `apps/backend/app/modules/client_auth/service.py:212-217`, `apps/backend/app/main.py:490-502`, `apps/backend/scripts/seed_dev_client.py`

**Issue:** When `settings.environment == "dev"`, `request_client_otp` overwrites the OTP with the constant `"111111"` and `_send_client_otp_dm` logs the raw code at WARNING. This is a deliberate UAT convenience, but it is a hard auth bypass if `ENVIRONMENT` is ever misset to `"dev"` in a non-local deployment: every linked phone's OTP becomes `111111` and is dumped to logs. There is no secondary guard (no separate opt-in flag, no localhost-DSN assertion). The seed script's fixed `+79999999999` / fixed-code fixture compounds the surface.

**Fix:** Gate the pin behind an explicit separate opt-in (e.g. `settings.dev_otp_pin_enabled`, default False) in addition to `environment == "dev"`, and add a startup assertion that it can never be True when `environment in {"staging","prod"}`. At minimum, do not log the raw code, or scope it to a debug-only logger that is off by default.

### WR-07: `AuthContext` post-probe reconciliation effect is dead — body never updates state

**File:** `apps/client-pwa/src/context/AuthContext.jsx:73-80`

**Issue:** The "After probe settles, clear override..." effect contains only two `if (...) return` guards and never calls `setOverride`. Its stated purpose ("clear override if it was from a previous expiry so future re-logins can re-probe correctly") is not implemented. Either the intended reconciliation is missing (a latent bug where a stale `'anon'` override could shadow a now-successful probe) or it is dead code. As written it cannot do what its comment claims.

**Fix:** Implement the intended reconciliation (e.g. clear `'anon'` override when the probe newly succeeds) or delete the effect. Verify the re-login path: `login()` sets `override='authed'` after refetch, which masks the probe — confirm that is the intended terminal state.

## Info

### IN-01: `_idempotencyKey` read in PaymentReturnScreen is unused dead code

**File:** `apps/client-pwa/src/routes/PaymentReturnScreen.jsx:24`

**Issue:** `const _idempotencyKey = params.get('idempotency_key')` is read "for display/retry purposes" but never used. If the retry-safety use case is real, implement it; otherwise remove the read and the comment so it does not imply behavior that does not exist.

### IN-02: CheckoutSheet promo/discount/card UI is decoration with no backend effect

**File:** `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx:40,173-243`

**Issue:** The promo code, 10% discount math (`ctx.amount * 0.1`), saved-card picker, and "save promo" toggle are local-only and never sent to the checkout endpoint (the mutations take only `planId`/`idempotencyKey`). The server charges the full plan price via its own price authority (CPAY-03). The displayed "К оплате" total can therefore differ from what ЮKassa actually charges — misleading UI.

**Fix:** Remove the discount/promo/card chrome (or mark it clearly non-functional) until a real promo/payment-method backend exists; do not show a reduced total the server will not honor.

### IN-03: `useClientBookings` ignores its `page` arg in the query key

**File:** `apps/client-pwa/src/lib/clientQueries.ts:236-247`

**Issue:** `useClientBookings(page=1)` sends `query: { page }` but keys as `clientPortalKeys.bookings()` (no page). Paginating bookings would serve cached page-1 for any page or clobber the cache across pages. Sibling hooks (`visitHistory`/`ptHistory`/`paymentHistory`) correctly include `page` in the key. Harmless today (only page 1 used), latent cache-correctness bug.

**Fix:** Add a `bookings: (page) => [...all, 'bookings', page]` key and use it.

### IN-04: HomeScreen `UpcomingCard` countdown is a fixed fake value, not derived from the booking

**File:** `apps/client-pwa/src/screens/HomeScreen.jsx:410,532-533`

**Issue:** `useCountdown(4 * 3600 * 1000 + 12 * 60 * 1000)` hardcodes "через 4ч 12м" regardless of `booking.start_time`, which is available. The countdown next to a real upcoming booking is decorative and can contradict the displayed start time.

**Fix:** Compute the countdown from `new Date(booking.start_time) - Date.now()`.

### IN-05: `seed_dev_client` owner selection is broader than its docstring implies

**File:** `apps/backend/scripts/seed_dev_client.py:53-62`

**Issue:** The script picks the oldest non-deleted `User` as `created_by_user_id`; if the first user is a reception account rather than the bootstrap owner, the dev client is still created (functionally fine) but the docstring implies it requires the owner. Not a defect — flagging for clarity. The `environment != "dev"` refusal guard is correct.

**Fix:** Optional — narrow selection to an owner-role user to match the docstring intent.

---

_Reviewed: 2026-05-30_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
