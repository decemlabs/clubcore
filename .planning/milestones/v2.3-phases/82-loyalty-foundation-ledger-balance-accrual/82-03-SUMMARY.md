---
phase: 82
plan: "03"
subsystem: client-pwa
tags: [loyalty, balance, history, pwa, hooks, vitest, feature-flag]
dependency_graph:
  requires:
    - 82-02 (backend endpoints GET /client/loyalty/balance + /history)
  provides:
    - useClientLoyaltyBalance + useClientLoyaltyHistory hooks in clientQueries.ts
    - LoyaltyBalanceCard component (ProfileScreen, behind clubBonuses flag)
    - BonusHistorySheet component (full-screen paginated bonus history)
    - LoyaltySheet.test.jsx (10 behavior tests)
  affects:
    - apps/client-pwa/src/lib/clientQueries.ts (2 new hooks + 2 key factory entries)
    - apps/client-pwa/src/data/index.js (re-exports)
    - apps/client-pwa/src/screens/ProfileScreen.jsx (clubBonuses flag + card mount)
    - apps/client-pwa/src/screens/ProfileScreen.identity.test.jsx (loyalty stubs)
    - apps/client-pwa/src/screens/ProfileScreen.membership.test.jsx (loyalty stubs)
    - apps/client-pwa/src/screens/sheets/CardSheet.wiring.test.jsx (loyalty stubs)
tech_stack:
  added: []
  patterns:
    - TanStack Query useQuery hook with staleTime 30s (mirrors useClientWeeklyActivity)
    - Intl.DateTimeFormat ru-RU Europe/Moscow for date formatting (no date-fns — not in package.json)
    - Sign derivation from signed amountKopecks (+ accrual / − U+2212 redemption)
    - formatMoney for all money display — no manual kopeck division
    - Page-accumulation pattern for load-more pagination (useState + useEffect dedup)
    - Silent error-hide (return null on isError) — matches CardSheet pattern
    - Full-screen sub-sheet (position:absolute, inset:0, z-index:220, sheet-up animation)
key_files:
  created:
    - apps/client-pwa/src/screens/sheets/LoyaltySheet.jsx
    - apps/client-pwa/src/screens/sheets/LoyaltySheet.test.jsx
  modified:
    - apps/client-pwa/src/lib/clientQueries.ts
    - apps/client-pwa/src/data/index.js
    - apps/client-pwa/src/screens/ProfileScreen.jsx
    - apps/client-pwa/src/screens/ProfileScreen.identity.test.jsx
    - apps/client-pwa/src/screens/ProfileScreen.membership.test.jsx
    - apps/client-pwa/src/screens/sheets/CardSheet.wiring.test.jsx
decisions:
  - "date-fns replaced by Intl.DateTimeFormat ru-RU/Europe/Moscow (date-fns not in client-pwa package.json — rule 1 auto-fix)"
  - "Page accumulation via useEffect + Set-based dedup rather than infinite query — simpler, no new TanStack Query package needed"
  - "LoyaltyBalanceCard placed below weeklyActivity card and above quick-action tiles per 82-UI-SPEC placement contract"
  - "BonusHistorySheet groups items by month using Intl.DateTimeFormat (LLLL yyyy equivalent)"
metrics:
  duration_minutes: 20
  completed_date: "2026-06-05"
  tasks_completed: 3
  tasks_total: 3
  files_created: 2
  files_modified: 6
---

# Phase 82 Plan 03: Client PWA Loyalty UI — Balance Card + History Sheet Summary

**One-liner:** LoyaltyBalanceCard + BonusHistorySheet wired to real loyalty endpoints via two TanStack Query hooks, with Intl-based Russian date formatting (date-fns not available in client-pwa), signed amount display (+/−), paginated load-more, and 10 green Vitest behaviors.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add useClientLoyaltyBalance + useClientLoyaltyHistory hooks + key factory + data export | 6352c7b9 | clientQueries.ts, data/index.js |
| 2 | Build LoyaltyBalanceCard + BonusHistorySheet and mount behind clubBonuses flag | 3f852f02 | LoyaltySheet.jsx, ProfileScreen.jsx |
| 3 | Vitest for LoyaltySheet — balance render, empty state, sign formatting, pagination | 64ca1e3b | LoyaltySheet.test.jsx, LoyaltySheet.jsx (date-fns fix) |
| Fix | Add loyalty hook stubs to existing ProfileScreen tests (regression fix) | a3af3926 | ProfileScreen.identity.test.jsx, ProfileScreen.membership.test.jsx, CardSheet.wiring.test.jsx |

## Verification Results

- `pnpm exec tsc --noEmit` — clean (no type errors)
- `pnpm exec vitest run src/screens/sheets/LoyaltySheet.test.jsx` — 10/10 passed
- `pnpm exec vitest run src/lib` — 23/23 passed (src/lib tests unaffected)
- `pnpm exec vitest run` — 141/141 passed (full suite, including regressions fixed)
- `git diff --stat apps/admin-web` — no changes (admin-web frozen)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] date-fns not available in client-pwa**
- **Found during:** Task 3 — first test run. Import of `date-fns` failed: `Failed to resolve import "date-fns"`. The PATTERNS.md referenced "date-fns 4.1.0 in package.json" but that is the admin-web's package.json, not client-pwa's. client-pwa has no date-fns in its dependencies.
- **Fix:** Replaced `format(parseISO(isoString), 'd MMMM yyyy', { locale: ru })` with a local `formatBonusDate()` using `Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Europe/Moscow' })`. Month grouping likewise uses Intl. Semantically equivalent output (Russian long date, Moscow timezone).
- **Files modified:** `apps/client-pwa/src/screens/sheets/LoyaltySheet.jsx`
- **Commit:** 64ca1e3b

**2. [Rule 1 - Bug] Existing ProfileScreen tests broken by new LoyaltyBalanceCard dependency**
- **Found during:** Post-task full suite run — 7 failures in ProfileScreen.identity, ProfileScreen.membership, and CardSheet.wiring tests.
- **Issue:** These tests mock `@/data` without the new `useClientLoyaltyBalance`/`useClientLoyaltyHistory` hooks; vitest strict mock mode throws `No "useClientLoyaltyBalance" export is defined on the "@/data" mock`.
- **Fix:** Added loyalty hook stubs to each test's `vi.mock('@/data', ...)` call returning `{ data: undefined, isLoading: false, isError: false }`.
- **Files modified:** `ProfileScreen.identity.test.jsx`, `ProfileScreen.membership.test.jsx`, `CardSheet.wiring.test.jsx`
- **Commit:** a3af3926

## Known Stubs

None — both hooks call real API endpoints. The `LoyaltyBalanceCard` is behind `clubBonuses: true` flag which is already enabled. The `BonusHistorySheet` fetches real paginated data. No placeholder values were introduced.

## Threat Flags

No new threat surface beyond what is documented in the plan threat model (T-82-11..13):
- T-82-11 (IDOR): Client reads only what `require_client()` principal-scoped API returns — no client_id in PWA requests
- T-82-12 (Display integrity): Sign derived from server's signed `amountKopecks`; `formatMoney(Math.abs(...))` for magnitude only; no client-side balance recompute
- T-82-13 (Error leakage): Balance card hides silently (`return null`) on error; history shows generic Russian retry message — no server internals surfaced

## Self-Check: PASSED

- `apps/client-pwa/src/screens/sheets/LoyaltySheet.jsx` — FOUND (LoyaltyBalanceCard, BonusHistorySheet, BonusRow, formatBonusDate)
- `apps/client-pwa/src/screens/sheets/LoyaltySheet.test.jsx` — FOUND (10 tests)
- `apps/client-pwa/src/lib/clientQueries.ts` — FOUND (useClientLoyaltyBalance, useClientLoyaltyHistory, loyaltyBalance key, loyaltyHistory key)
- `apps/client-pwa/src/data/index.js` — FOUND (useClientLoyaltyBalance, useClientLoyaltyHistory re-exported)
- `apps/client-pwa/src/screens/ProfileScreen.jsx` — FOUND (clubBonuses: true, LoyaltyBalanceCard mount, BonusHistorySheet conditional)
- Commit 6352c7b9 — FOUND (feat: add loyalty hooks)
- Commit 3f852f02 — FOUND (feat: build LoyaltySheet components)
- Commit 64ca1e3b — FOUND (test: LoyaltySheet behaviors)
- Commit a3af3926 — FOUND (fix: loyalty hook stubs in existing tests)
- `grep -c "amountKopecks / 100\|balanceKopecks / 100" apps/client-pwa/src/screens/sheets/LoyaltySheet.jsx` — 0 (no manual division)
- `git diff --stat apps/admin-web` — empty (admin-web untouched)
- `git diff --stat apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx` — empty (BONUS_PLACEHOLDER untouched)
