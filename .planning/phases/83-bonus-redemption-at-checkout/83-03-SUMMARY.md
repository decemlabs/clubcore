---
phase: 83-bonus-redemption-at-checkout
plan: "03"
subsystem: client-pwa + api-contract
tags: [loyalty, redemption, checkout, pwa, openapi, codegen, REDM-03]
dependency_graph:
  requires:
    - phase: 83-02
      provides: ClientCheckoutRequest.loyalty_redeem_kopecks field + server-authoritative checkout clamp
    - phase: 82
      provides: useClientLoyaltyBalance hook (GET /client/loyalty/balance)
  provides:
    - CheckoutSheet with real loyalty balance display + estimate-only redemption discount
    - loyaltyRedeemKopecks threaded into both checkout mutations
    - clubBonuses feature flag ON
    - openapi.json + schema.d.ts additively regenerated with new request field
  affects:
    - apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx
    - apps/client-pwa/src/screens/sheets/CheckoutSheet.bonus.test.jsx
    - apps/client-pwa/src/screens/sheets/CheckoutSheet.savecard.test.jsx
    - apps/backend/openapi.json
    - packages/api-client/src/schema.d.ts
tech_stack:
  added: []
  patterns:
    - balance state lifted to outer component (same as savePaymentMethod pattern)
    - estimate-only discount (bonusEstimateKopecks = Math.min(balanceKopecks, total)) — D-06 anti-oracle
    - conditional spread for optional request fields (mirrors savePaymentMethod spread)
    - section hidden on zero/loading/error (mirrors CardSheet "no card = no section" pattern)
key-files:
  created:
    - apps/client-pwa/src/screens/sheets/CheckoutSheet.bonus.test.jsx
  modified:
    - apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx
    - apps/client-pwa/src/screens/sheets/CheckoutSheet.savecard.test.jsx
    - apps/backend/openapi.json
    - packages/api-client/src/schema.d.ts
key-decisions:
  - "bonusOn and balanceKopecks lifted to CheckoutSheet scope (same as savePaymentMethod) so launchCheckout can include loyaltyRedeemKopecks in the request body; ReviewStage receives them as props"
  - "bonusEstimateKopecks is a derived constant (not state) — display-only, never mutates server-derived total/discount (D-06 invariant)"
  - "savecard.test.jsx updated to mock useClientLoyaltyBalance returning balance=0, which keeps the bonus section hidden so savecard tests are unaffected by the new hook"
  - "openapi.json regen is additive (+17/-2 lines; only a docstring update deleted); Phase 85 owns byte-stable freeze"
requirements-completed: [REDM-03]
duration: "~20 minutes"
completed: "2026-06-05"
---

# Phase 83 Plan 03: CheckoutSheet Bonus Wiring + Contract Regen Summary

**CheckoutSheet wired to real loyalty balance with estimate-only redemption behind clubBonuses=true; BONUS_PLACEHOLDER removed; loyaltyRedeemKopecks threaded into both checkout mutations; openapi.json + schema.d.ts additively regenerated so tsc -b passes (REDM-03)**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-06-05T17:00:00Z
- **Completed:** 2026-06-05T17:15:00Z
- **Tasks:** 2
- **Files modified:** 4 + 1 new test file

## Accomplishments

- `useClientLoyaltyBalance` imported from `@/data`; `bonusOn` state and `balanceKopecks` derived value lifted to `CheckoutSheet` scope so `launchCheckout` can spread `loyaltyRedeemKopecks` into both `checkoutMembership.mutateAsync` and `checkoutPtPackage.mutateAsync`
- `BONUS_PLACEHOLDER` removed; `clubBonuses` flag flipped to `true`
- Bonus section gated on `!loyaltyLoading && balanceKopecks > 0` — silently hidden on zero balance, loading, or fetch error (mirrors CardSheet pattern)
- Subtitle updated to `На счёте <b>{formatMoney(balanceKopecks)}</b>`; "до Gold" text removed (deferred to TIER-01)
- `bonusEstimateKopecks = Math.min(balanceKopecks, total)` and `estimatedTotal = total - bonusEstimateKopecks` added as display-only derived constants (D-06 invariant: server-derived `total`/`discount` unchanged)
- Bonus discount row added below promo row with `~` chip (estimate signal); savings bar updated to `totalDiscount = discount + bonusEstimateKopecks`; `useCountUp` receives `estimatedTotal` with bonus-related deps; pay button gets `~` prefix when bonusOn
- Toggle ON toast updated to "Бонусы будут списаны при оплате" (clarifies debit is server-side on payment, per D-06)
- New `CheckoutSheet.bonus.test.jsx`: 8 tests covering balance display, toggle discount row, request-body wiring (sub + PT), hidden-on-zero (0 balance, loading, error), and omission when OFF
- `CheckoutSheet.savecard.test.jsx` updated to mock `useClientLoyaltyBalance` (returns balance=0) so existing 3 savecard tests continue passing after the hook was added to `CheckoutSheet`
- `openapi.json` regenerated from live FastAPI app carrying `ClientCheckoutRequest.loyalty_redeem_kopecks`; `schema.d.ts` regenerated via `openapi-typescript` — `loyaltyRedeemKopecks?: number | null` now present; PWA `tsc -b` passes

## Task Commits

1. **Task 1: CheckoutSheet bonus wiring + test** - `610a71ec` (feat)
2. **Task 2: Additive openapi.json + schema.d.ts regen** - `453e685f` (feat)

## Files Created/Modified

- `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx` — five 83-UI-SPEC changes: import, flag flip, real balance hook, bonus section guard + subtitle, bonus discount row, savings bar, request field spread in both mutations, pay button ~ prefix, toast update
- `apps/client-pwa/src/screens/sheets/CheckoutSheet.bonus.test.jsx` — new: 8 tests (all pass)
- `apps/client-pwa/src/screens/sheets/CheckoutSheet.savecard.test.jsx` — added `useClientLoyaltyBalance` mock returning balance=0 so savecard tests remain green
- `apps/backend/openapi.json` — additively regenerated (+17/-2 lines; docstring update only deletion)
- `packages/api-client/src/schema.d.ts` — additively regenerated (+9/-1 line; docstring tweak only deletion); `loyaltyRedeemKopecks?: number | null` in `ClientCheckoutRequest`

## Decisions Made

- `bonusOn` and `balanceKopecks` lifted to `CheckoutSheet` scope rather than keeping them in `ReviewStage`: `launchCheckout` runs in `CheckoutSheet` scope and must read these values to include `loyaltyRedeemKopecks` in the request body; mirrors the pre-existing `savePaymentMethod` state lift pattern
- `bonusEstimateKopecks` as a derived constant (not `useState`) — keeps state surface minimal and makes D-06 compliance explicit: it is separate from `total`/`discount` which remain server-derived
- `savecard.test.jsx` patched to mock `useClientLoyaltyBalance` with balance=0: the hook is now called at `CheckoutSheet` level (not `ReviewStage`), so the real hook would fire via `importActual` without a `QueryClientProvider`, causing `No QueryClient set` errors. Balance=0 keeps the bonus section hidden so savecard test assertions are unaffected

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] savecard.test.jsx broke when useClientLoyaltyBalance was added to CheckoutSheet**
- **Found during:** Task 1 test run
- **Issue:** `CheckoutSheet.savecard.test.jsx` mocked `@/data` without including `useClientLoyaltyBalance`; after the hook was added to `CheckoutSheet`, the real `importActual` path called `useQuery` which requires `QueryClientProvider`, crashing all 3 savecard tests with "No QueryClient set"
- **Fix:** Added `useClientLoyaltyBalance` to the savecard test mock, returning `{ data: { balanceKopecks: 0 }, isLoading: false }` so the bonus section stays hidden and savecard assertions are unaffected
- **Files modified:** `apps/client-pwa/src/screens/sheets/CheckoutSheet.savecard.test.jsx`
- **Commit:** included in `610a71ec`

## Known Stubs

None. The bonus section now uses real data from `useClientLoyaltyBalance`. The ring SVG `stroke-dashoffset: 45` stays static (decorative chrome — Gold tier progress is intentionally deferred to TIER-01 per 83-UI-SPEC Change 4).

## Threat Flags

No new security-relevant surface beyond what the plan's `<threat_model>` documents. T-83-10 (anti-oracle estimate), T-83-11 (client-set discount tamper), T-83-12 (balance source IDOR) all mitigated per plan.

## Self-Check: PASSED

- `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx`: FOUND
- `apps/client-pwa/src/screens/sheets/CheckoutSheet.bonus.test.jsx`: FOUND
- `apps/backend/openapi.json`: FOUND (loyaltyRedeemKopecks: 1 occurrence)
- `packages/api-client/src/schema.d.ts`: FOUND (loyaltyRedeemKopecks: 1 occurrence)
- Commit `610a71ec`: FOUND
- Commit `453e685f`: FOUND
- `grep -c BONUS_PLACEHOLDER CheckoutSheet.jsx`: 0
- `clubBonuses: true`: confirmed
- PWA `tsc -b`: PASSED (no output = success)
- PWA vitest: 149 passed (22 test files)
- PWA lint: clean (no errors)
- `git diff --stat apps/admin-web`: 0 lines (untouched)
