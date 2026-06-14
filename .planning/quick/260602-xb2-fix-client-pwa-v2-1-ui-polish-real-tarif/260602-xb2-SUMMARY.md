---
status: complete
quick_id: 260602-xb2
description: Fix client-pwa v2.1 UI polish — real tariff buttons, checkout scroll padding, applied-promo chip overflow
completed: 2026-06-03
tasks_total: 3
tasks_completed: 3
subsystem: client-pwa
tags: [ui-polish, client-pwa, homescreen, checkout, css]
key_files:
  modified:
    - apps/client-pwa/src/screens/HomeScreen.jsx
    - apps/client-pwa/src/screens/HomeScreen.identity.test.jsx
    - apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx
    - apps/client-pwa/src/styles.css
decisions:
  - Data-driven tariff buttons map plans directly from useClientPlans(); price shown per button, not in separate chip — simpler mental model, no incoherence between chip count and button count
  - STATIC_TARIFF_LABELS fallback kept as module-level constant (fail-open per D-76-04/09)
  - Scroller bottom padding via inline style on checkout scroller only, not shared .scroller rule
  - Notch suppression via content:none (lowest specificity override, no side-effects on non-applied states)
duration_minutes: 15
---

# Quick Task 260602-xb2: client-pwa v2.1 UI polish

Three targeted UI fixes in `apps/client-pwa` diagnosed at 390×844 during v2.1 browser verification.

## One-liner

Data-driven tariff buttons (useClientPlans), checkout scroller cleared of floating-footer overlap, and applied-promo notch overflow eliminated via `content: none`.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Data-drive HeroNewbie tariff buttons from useClientPlans | 11b52a4f | HomeScreen.jsx, HomeScreen.identity.test.jsx |
| 2 | CheckoutSheet scroller bottom padding clears floating pay footer | 87680e87 | CheckoutSheet.jsx |
| 3 | Suppress ticket-notch pseudo-elements in co-coupon.applied state | 23e2b888 | styles.css |

## Task Details

### Task 1 — Data-driven tariff buttons (#2)

Replaced the hardcoded `tariffs` array (`Месяц/Полгода/Год`, no prices, decorative ХИТ badge) and the separate plan-info chip block with buttons mapped from `useClientPlans()`. Each button now shows `plan.name` + `formatMoney(plan.priceKopecks)`. Price is only rendered when `priceKopecks` is a finite positive number (guard on the display div). The `STATIC_TARIFF_LABELS` fallback renders 3 unlabelled buttons (no price) when plans are loading or empty — fail-open.

Removed `pluralPlan` helper (dead code after chip removal). Updated NHOME-02 test to assert per-button prices instead of chip text pattern.

Default selection index changed from `1` (hardcoded "Полгода") to `0` since catalog order is now canonical.

### Task 2 — CheckoutSheet scroller bottom padding (#3 + #5)

Changed the checkout `.scroller` inline bottom padding from `8px` to `calc(120px + env(safe-area-inset-bottom))`. This gives enough clearance for the floating `Оплатить` button (measured ~100px tall). Scoped to inline style; the shared `.scroller` CSS rule in styles.css is unchanged.

### Task 3 — Applied-promo coupon chip no overflow (#4)

Added `.co-coupon.applied::before, .co-coupon.applied::after { content: none; }` to `styles.css` immediately after the `.co-coupon.applied` rule. This suppresses the ticket-notch circles (18px `border-radius: var(--r-pill)` positioned at `left: -9px` / `right: -9px`) in the applied state, where the `box-shadow: 0 0 0 3px var(--accent-soft)` ring conflicts with the right notch, producing a 9px `scrollWidth > clientWidth` overflow artifact. Ticket notches are preserved for non-applied states.

## Deviations from Plan

None — plan executed exactly as written.

## Gates

- `pnpm lint`: passed
- `pnpm exec tsc -b`: passed (JSX files excluded from TS check per D-69-06)
- `pnpm exec vitest run`: 92 tests passed (16 test files)
- `pnpm build`: passed (614 kB precache, 710 ms build)

## Known Stubs

None introduced by this task.

## Threat Flags

None — purely UI/CSS changes, no new network endpoints or auth paths.

## Self-Check: PASSED

- HomeScreen.jsx modified: confirmed
- HomeScreen.identity.test.jsx modified: confirmed
- CheckoutSheet.jsx modified: confirmed
- styles.css modified: confirmed
- Commits 11b52a4f, 87680e87, 23e2b888 exist in git log
