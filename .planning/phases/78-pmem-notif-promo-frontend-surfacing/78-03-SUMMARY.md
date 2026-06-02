---
phase: 78-pmem-notif-promo-frontend-surfacing
plan: "03"
subsystem: ui
tags: [react, checkout, promo, feature-flag, pwa]

# Dependency graph
requires:
  - phase: 78-pmem-notif-promo-frontend-surfacing
    provides: "PROMO-01 chip JSX + handlePromoApply + usePromoValidate already built and gated false"
provides:
  - "CHECKOUT_FEATURE_FLAGS.recommendedPromo flipped true — FIT15 chip surfaced in checkout"
  - "One-tap FIT15 promo apply via server-authoritative POST /client/promo/validate"
affects:
  - 78-pmem-notif-promo-frontend-surfacing

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Feature flag pattern: deferred UI built + gated false, surfaced by single boolean flip"

key-files:
  created: []
  modified:
    - apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx

key-decisions:
  - "D-78-09: recommendedPromo flag flipped true; clubBonuses remains false (loyalty backend not ready)"
  - "D-78-10: existing !promoResult gate preserved — chip hides once any promo is applied; manual entry unchanged"

patterns-established:
  - "Flag-flip surfacing: pre-built UI gates deferred with a boolean; surfaced with single-line change"

requirements-completed: [PROMO-01]

# Metrics
duration: 3min
completed: 2026-06-02
---

# Phase 78 Plan 03: PROMO-01 FIT15 Chip Surfacing Summary

**FIT15 recommended-promo chip surfaced in checkout by flipping CHECKOUT_FEATURE_FLAGS.recommendedPromo false→true; one-tap apply via existing server-authoritative usePromoValidate flow now visible in both sub + PT contexts**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-06-02T23:12:00Z
- **Completed:** 2026-06-02T23:15:00Z
- **Tasks:** 1 auto task + 1 human-verify checkpoint (recorded, not blocked on)
- **Files modified:** 1

## Accomplishments
- Flipped `CHECKOUT_FEATURE_FLAGS.recommendedPromo` from `false` to `true` (single-line change, D-78-09)
- The pre-built FIT15 chip (`.co-rec-chip`) now renders in both `sub` and `pt` checkout contexts when no promo is yet applied
- The existing `handlePromoApply(RECOMMENDED_PROMO.code)` onClick handler and `!promoResult` hide-after-applied gate are completely unchanged (D-78-10)
- `clubBonuses` remains `false` — loyalty backend not yet available; flipping it would expose non-functional UI
- All automated gates passed: tsc, ESLint, Vite build, vitest (92 tests)

## Task Commits

Each task was committed atomically:

1. **Task 1: Flip recommendedPromo feature flag to true** - `bebebbb1` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx` — `recommendedPromo: false` → `recommendedPromo: true` (line 46)

## Decisions Made
- Kept `clubBonuses: false` exactly as specified — flipping it is out of scope and a client-side price-mutation hazard until the loyalty backend lands
- Did not restyle the chip or modify any other logic; purely a flag flip as instructed

## Deviations from Plan

None — plan executed exactly as written. Single-line flag flip; all gates green on first attempt. The one issue encountered (missing `node_modules` in the worktree) was resolved by running `pnpm install --frozen-lockfile` in the worktree root before running the gates — a standard worktree setup step, not a plan deviation.

## Issues Encountered

The worktree did not have `node_modules` pre-installed (expected for a fresh worktree). Ran `pnpm install --frozen-lockfile` (exit 0, reused 1030 packages from cache) before running the automated gates. No code changes required.

## Human Verification Required

**Checkpoint: Live checkout chip verification (sub + PT contexts)**

The automated gates (tsc + lint + build + vitest) have all passed. The following manual steps are required to fully close PROMO-01:

**Prerequisites:**
1. Start the backend stack (per backend local-stack runbook; FIT15 must be seeded via migration 0051)
2. Start the PWA dev server: `cd apps/client-pwa && pnpm dev`

**Verification steps:**

**Step 1 — Subscription checkout:**
- Log in as a client and open a membership plan
- Tap "К оплате" to open the checkout sheet
- In the "Промокод" section, confirm the recommended chip is visible showing "−15% Применить FIT15"
- Tap the chip once
- Confirm: a toast "Промокод FIT15 применён" appears, the discounted amount is shown, and the chip disappears

**Step 2 — Manual entry still works:**
- Remove the promo (if applicable), type "FIT15" manually in the input, tap "Применить"
- Confirm same result

**Step 3 — PT (personal-training) checkout (D-78-10):**
- Open a personal-training package checkout
- Confirm the FIT15 chip ALSO surfaces there (both ctx.kind='sub' and ctx.kind='pt' are covered by the same flag gate)
- Confirm one tap applies FIT15 with the discounted amount shown

**Resume signal:** Type "approved" if chip surfaces in both sub + PT contexts and one tap applies FIT15 with discounted amount shown.

## Next Phase Readiness
- PROMO-01 frontend surfacing is code-complete; pending human verification of the live chip UX
- Phase 78 all three plans (PMEM-01, NOTIF-01, PROMO-01) are now code-complete
- v2.1 milestone frontend-surfacing tech debt is closed

---
*Phase: 78-pmem-notif-promo-frontend-surfacing*
*Completed: 2026-06-02*
