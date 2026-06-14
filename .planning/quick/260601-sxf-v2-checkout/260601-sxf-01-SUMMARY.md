---
status: complete
phase: 260601-sxf-v2-checkout
plan: "01"
subsystem: client-pwa
tags: [checkout, v2-restyle, css, jsx, animation, accessibility]
dependency_graph:
  requires: []
  provides: [v2-checkout-review-stage]
  affects: [CheckoutSheet.jsx, styles.css]
tech_stack:
  added: []
  patterns:
    - useCountUp hook (rAF cubic ease-out, prefers-reduced-motion aware)
    - local in-sheet toast (local state + .co-toast CSS class)
    - ReviewStage / PromoSection extracted as local functions (no new files)
key_files:
  created: []
  modified:
    - apps/client-pwa/src/styles.css
    - apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx
    - apps/client-pwa/src/screens/sheets/PlansSheet.jsx
decisions:
  - "D-01 preserved: .co-method is static (no wallet number, no picker chevron); lock icon only"
  - "D-06 preserved: total = promoResult.newAmountKopecks ?? ctx.amount; no client-side promo math"
  - "D-09 preserved: PROMO_ERROR_MESSAGES map unchanged, role=alert on error"
  - "D-10/D-13/D-12 preserved: paying spinner, 4 error kinds, success-on-server-truth untouched"
  - "Bonus block and recommended-promo chip omitted per CONTEXT.md locked decisions"
  - ".co-method-logo uses var(--accent-soft)/var(--accent-deep) instead of mockup purple #7a30e8"
  - "useCountUp hook runs rAF tween; snaps immediately when prefers-reduced-motion matches"
  - "Toast is local state + .co-toast (no global provider); auto-dismisses at 2600ms"
metrics:
  duration: "5m"
  completed: "2026-06-01"
  tasks: 2
  files: 2
---

# Phase 260601-sxf Plan 01: Checkout v2 Visual Restyle Summary

**One-liner:** Membership-pass hero card, coupon-style promo field, summary card with savings bar, restyled ЮKassa method plate, and count-up animation — all wired to server-authoritative pricing with locked states preserved.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add v2 checkout CSS classes + keyframes to styles.css | d0f77b4a | apps/client-pwa/src/styles.css |
| 2 (human-verify ✓ approved) | Rewrite CheckoutSheet review stage to v2 layout | c037695d | apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx |
| 3 (follow-up) | Drop redundant PlanConfirm step — open v2 checkout directly | 7d02b1ca | apps/client-pwa/src/screens/sheets/PlansSheet.jsx |
| 4 (follow-up) | Add hidden recommended-promo + club-bonuses scaffolding (flags off) | 9b27fc5b | styles.css, CheckoutSheet.jsx |

**Human visual verification:** APPROVED 2026-06-01 ("approved, всё отображается как надо") — checked in running PWA, light + dark.

## What Was Built

**Task 1 — CSS (`styles.css`):**
Appended a "Checkout v2" CSS block (616 lines) with entirely new `.co-*` class names to avoid clobbering existing `.field`/`.chip`/`.method`/`.toast` classes:

- `.co-pass` + sub-parts: membership-pass hero card (barbell watermark, brand mark, duration pill, plan body, dashed-separator footer, guarantee badge)
- `.co-coupon` + ticket notches (::before/::after circles), glow strip, `.error`/`.applied` variants, `.co-field`, `.co-input-wrap`, `.co-promo-apply`, `.co-promo-hint`, `.co-applied-view`/`.co-av-*`
- `.co-sum`, `.co-sum-row`, `.co-sum-total`, `.co-tl`, `.co-amount` summary card
- `.co-save-wrap`, `.co-save-bar`, `.co-pay-seg`, `.co-save-seg`, `.co-save-legend` savings bar
- `.co-method`, `.co-method-logo`, `.co-method-text`, `.co-method-lock` ЮKassa plate (accent-soft/accent-deep palette — NOT mockup's purple #7a30e8)
- `.co-toast`, `.co-toast-ic`, `.co-toast-tx` in-sheet toast (absolute, auto-dismiss)
- `.co-sec-label`, `.co-ln` section label with trailing rule line
- `@keyframes tickA` + `.co-tick` number-tick animation

All colors via `var(--token)`; only raw hex is `#06120c` (on-accent, already project-sanctioned).

**Task 2 — JSX (`CheckoutSheet.jsx`):**
Restructured the review stage to v2 layout order:
1. `.co-pass` hero with `BarbellMark` SVG, brand mark "МЗ", plan name from `ctx.title`, meta from `ctx.subtitle`, base price `formatMoney(ctx.amount)`, "Гарантия возврата" badge
2. `.co-sec-label` "Промокод" + `PromoSection` (coupon ticket with idle/applied/error states)
3. `.co-sec-label` "Итог" + `.co-sum` with base row, conditional discount row, total row + `.co-save-wrap` savings bar (only when `total < ctx.amount`)
4. `.co-sec-label` "Способ оплаты" + `.co-method` (static plate, D-01)

Added `useCountUp` hook (rAF cubic ease-out ~440ms; `prefers-reduced-motion` snaps immediately). The count-up animates the paybar total on mount and on every `total` change.

Added local toast state (`const [toast, setToast] = useState(null)` + `showToast()` + auto-dismiss timer). Fires on promo apply, promo remove, and method tap.

All locked states byte-preserved: `mapApiErrorToKind`, `PROMO_ERROR_MESSAGES`, `handlePromoApply`/`handlePromoRemove`, `launchCheckout`, `startPay`, `ReceiptEmailGate` branch, paying spinner (D-13), `CheckoutError` (D-12 — exactly 4 kinds), `forceOutcome` demo guards.

## Post-Checkpoint Additions (user-requested, approved)

Two follow-ups landed after the plan's Task 2 was visually verified, on user request:

**Commit `7d02b1ca` — remove redundant PlanConfirm:** The `PlanConfirm` intermediate
sheet inside `PlansSheet.jsx` duplicated the new v2 checkout (plan, price, method,
refund) and rendered a fake saved "Visa ·· 4821" card that contradicts D-01. The
"Оформить · X ₽" CTA now calls `onPick(plan)` directly (matching how TrainerDetailSheet
and Tweaks already open checkout). Removed the `confirming` state, the `PlanConfirm`
component, and the now-unused `Divider`/`RowItem` import.

**Commit `9b27fc5b` — hidden deferred-feature scaffolding:** Built the v2 mockup's
recommended-promo chip and "Списать бонусы" toggle, gated OFF behind
`CHECKOUT_FEATURE_FLAGS` (both default `false`) so current behavior is unchanged.
Flip a flag to reveal. `recommendedPromo` applies `RECOMMENDED_PROMO.code` via the
existing server-authoritative `handlePromoApply` (now accepts an optional code arg;
event-passing call sites stay safe via a `typeof` guard) — works end-to-end once on.
`clubBonuses` is UI-only: toggling does NOT mutate `total`/`discount` client-side
(D-06); real point redemption still requires the deferred loyalty backend phase
(carries a `TODO(loyalty-phase)` marker). Added `.co-promo-rec`/`.co-rec-*` and
`.co-bonus*` classes (tokens only). Re-verified: typecheck/lint/test(49)/build all pass.

## Deviations from Plan

None — plan executed exactly as written. The two follow-ups above were additive,
user-requested changes made after approval (not deviations from the plan's scope).

Notable adaptation: the `.co-method-logo` uses `var(--accent-soft)` background + `var(--accent-deep)` text instead of the mockup's `#7a30e8` purple (mockup's purple is a YooMoney brand color; our plate represents ЮKassa generally). This is compliant with the no-raw-hex rule and the D-01 static-plate decision.

## Verification

Automated checks run before commit (all pass):
- `pnpm typecheck` — clean
- `pnpm lint` — clean
- `pnpm build` — clean (CheckoutSheet bundle: 24.57 kB / 7.14 kB gzip)
- `pnpm test` — 49/49 tests pass (CheckoutSheet/PaymentReturnScreen suites included)

Human visual verification pending (Task 2 checkpoint).

## Known Stubs

None. All data displayed in the review stage is wired to real props (`ctx`, `promoResult`, `total`, `discount`). The "Ваша выгода" savings bar only renders when `total < ctx.amount` — driven by server-authoritative values, not placeholders.

## Threat Flags

None. This is a frontend-only view-layer restyle. No new network endpoints, auth paths, or schema changes introduced.

## Self-Check: PASSED

- `apps/client-pwa/src/styles.css` — modified (verified via lint + build)
- `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx` — modified (verified via typecheck + lint + build + test)
- Commit d0f77b4a exists: `git log --oneline --all | grep d0f77b4a` ✓
- Commit c037695d exists: `git log --oneline --all | grep c037695d` ✓
