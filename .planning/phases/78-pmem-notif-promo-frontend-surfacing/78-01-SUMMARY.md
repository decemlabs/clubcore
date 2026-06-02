---
phase: 78-pmem-notif-promo-frontend-surfacing
plan: 01
subsystem: ui
tags: [react, formatMoney, useClientMembership, vitest, PMEM-01]

# Dependency graph
requires:
  - phase: 75-pmem-notif-promo-backend
    provides: "priceKopecks and autoRenew fields on /client/membership response; useClientMembership hook already exposes them"
provides:
  - "Profile screen membership hero renders priceKopecks as formatted ₽ via formatMoney()"
  - "Auto-renew indicator hidden when autoRenew is null (D-78-02/D-75-01)"
  - "ProfileScreen.membership.test.jsx: 4 vitest tests covering price render, null membership, autoRenew boolean, loading state"
  - "ProfileScreen.identity.test.jsx repaired: useClientMembership added to vi.mock stub"
affects: [phase-78-plan-02, phase-78-plan-03, PMEM-01-requirement]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "null-guard price row: render only when membership?.priceKopecks is a finite number > 0 (D-78-03)"
    - "null-driven auto-renew: row hidden entirely when autoRenew is null; shows on/off when boolean (D-78-02)"
    - "vi.mock('@/data') pattern: every hook the component calls must be listed in the mock object"

key-files:
  created:
    - apps/client-pwa/src/screens/ProfileScreen.membership.test.jsx
  modified:
    - apps/client-pwa/src/screens/ProfileScreen.jsx
    - apps/client-pwa/src/screens/ProfileScreen.identity.test.jsx

key-decisions:
  - "D-78-01: useClientMembership() added to ProfileScreen alongside existing useClientHome(); sub (toSubInfo) stays sourced from homeData"
  - "D-78-02: autoRenew row hidden entirely when null — no dash placeholder rendered"
  - "D-78-03: price row guard uses membership != null && typeof priceKopecks === 'number' && priceKopecks > 0"
  - "Identity test mock repair: useClientMembership stub returns { data: null } (simplest correct stub)"
  - "Worktree node_modules: symlinked from main repo to run vitest/tsc in the worktree context"

patterns-established:
  - "autoRenew null-gate pattern: membership.autoRenew !== null && membership.autoRenew !== undefined guards the auto-renew row"
  - "Test regex for NBSP money: /4[\\s\\u00a0]900[\\s\\u00a0]₽/ tolerates Intl.NumberFormat NBSP vs regular space"

requirements-completed: [PMEM-01]

# Metrics
duration: 12min
completed: 2026-06-02
---

# Phase 78 Plan 01: PMEM-01 Profile Membership Price Surfacing Summary

**Profile membership hero now renders priceKopecks as formatted ₽ (via formatMoney) from useClientMembership(); auto-renew row hidden when null per D-78-02; 4 new vitest tests covering all render branches**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-06-02T20:58:00Z
- **Completed:** 2026-06-02T23:04:30Z
- **Tasks:** 2 (both auto + tdd)
- **Files modified:** 3

## Accomplishments
- Wired `useClientMembership()` into `ProfileScreen.jsx` alongside existing `useClientHome()` call
- Added price row (label "Стоимость" + `formatMoney(priceKopecks)`) guarded by D-78-03: only renders when membership is non-null and priceKopecks > 0
- Added auto-renew row guarded by D-78-02: completely hidden when `autoRenew === null`; shows "Включено"/"Выключено" for real boolean values
- Removed the "Price/auto-renew block deliberately omitted" comment that marked the PMEM-01 frontend debt
- Created `ProfileScreen.membership.test.jsx` with 4 vitest tests covering all price/auto-renew render branches
- Repaired `ProfileScreen.identity.test.jsx` `vi.mock('@/data')` to include `useClientMembership` stub (prevented "is not a function" runtime error)
- Full vitest suite: 15 files / 86 tests, all green (up from 14 files / 82 tests)

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire useClientMembership price + null-driven auto-renew into membership hero** - `a9437423` (feat)
2. **Task 2: Add membership-render Vitest coverage and repair identity test mock** - `79fc72e0` (test)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `apps/client-pwa/src/screens/ProfileScreen.jsx` - Added useClientMembership import+call; price row + auto-renew row in .membership-hero; removed deliberate-omission comment
- `apps/client-pwa/src/screens/ProfileScreen.identity.test.jsx` - Added useClientMembership to vi.mock('@/data') stub
- `apps/client-pwa/src/screens/ProfileScreen.membership.test.jsx` - New: 4 vitest tests for price/auto-renew render branches

## Decisions Made
- Used `aria-label="auto-renew-indicator"` on the auto-renew row `<div>` to make absence assertable in tests without adding a data attribute
- Used regex match `/4[\s ]900[\s ]₽/` in tests to tolerate NBSP characters from Intl.NumberFormat ru-RU output
- Symlinked main-repo node_modules into worktree's client-pwa directory to enable vitest/tsc to run from the worktree

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- The worktree has no node_modules (pnpm installs into the main repo). Running tsc/eslint/vitest required symlinking `apps/client-pwa/node_modules` from the main repo into the worktree. The symlink is gitignored and does not affect the commit.

## Known Stubs

None — all price/auto-renew data is sourced from `useClientMembership()` which calls the real `/client/membership` backend endpoint. No hardcoded values or placeholders introduced.

## Threat Flags

None — this plan adds frontend rendering of an already-authorized read (see T-78-01/T-78-02 in plan threat model). No new write paths or trust-boundary changes.

## Next Phase Readiness
- PMEM-01 frontend surfacing complete; next plans in phase 78 cover NOTIF-01 (plan 78-02) and PROMO-01 (plan 78-03)
- No blockers

---
*Phase: 78-pmem-notif-promo-frontend-surfacing*
*Completed: 2026-06-02*
