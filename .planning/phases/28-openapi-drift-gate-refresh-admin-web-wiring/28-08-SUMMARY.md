---
phase: 28
plan: "08"
subsystem: frontend
tags: [list, filter, search-params, expiring, within, select]
dependency_graph:
  requires: [28-05, 28-07]
  provides: [FE-13]
  affects:
    - apps/admin-web/src/routes/_protected/memberships.tsx
    - apps/admin-web/src/features/memberships/components/MembershipsListPage.tsx
tech_stack:
  added: []
  patterns:
    - base-ui Select for filter selector (conditional on search.expiring)
    - Zod coerce.number().int().min(1).max(30).default(7) URL clamping
key_files:
  created:
    - apps/admin-web/src/features/memberships/components/MembershipsListPage.within.test.tsx
  modified:
    - apps/admin-web/src/routes/_protected/memberships.tsx
    - apps/admin-web/src/features/memberships/components/MembershipsListPage.tsx
decisions:
  - "Used data-slot='select-trigger' CSS selector in tests instead of getByRole('combobox') because base-ui SelectTrigger renders as a plain <button> without a combobox ARIA role in jsdom"
  - "Selector is conditionally rendered only when search.expiring===true, matching plan spec and preserving frozen pill mutual-exclusion from 28-07"
  - "Page resets to 1 on within change, consistent with existing filter patterns"
metrics:
  duration: "15m"
  completed: "2026-05-10"
  tasks_completed: 3
  files_changed: 3
---

# Phase 28 Plan 08: Within Selector for Expiring Filter Summary

Closed FE-13: added the "Истекает в течение" within-days selector to the memberships list page. The selector surfaces the Phase 24 DEBT-02 `within` plumbing already present in HTTP and mock services, completing the expiring filter UX.

## What Was Built

**Route schema extension** (`routes/_protected/memberships.tsx`): Added `within: z.coerce.number().int().min(1).max(30).default(7)` to the existing `searchSchema`. Zod's `coerce` + `min/max` silently clamps URL-tampered values (e.g. `?within=99` → 7) without returning errors to the user. The loader already passes the full `search` object through `loaderDeps` so no further change was needed there.

**Within selector UI** (`MembershipsListPage.tsx`): Added a conditional `<Select>` with options `[1, 3, 7, 14, 30]` дн. Renders only when `search.expiring === true`; hidden automatically when the user toggles back to the frozen pill (mutual exclusion from 28-07 is preserved). `onValueChange` navigates with `within: Number(v)` and resets `page: 1`. The selector imports from `@/shared/ui/select` which wraps `@base-ui/react/select`.

**Vitest test** (`MembershipsListPage.within.test.tsx`): 4 tests covering:
1. Selector hidden when `expiring=false`
2. Selector label visible when `expiring=true`
3. Selecting "14 дн." calls `navigate` with `within: 14, page: 1`
4. All 5 options [1, 3, 7, 14, 30] дн. appear in the dropdown

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test uses data-slot query instead of getByRole('combobox')**
- **Found during:** Task 3 — first test run
- **Issue:** The plan's suggested `getByRole('combobox')` approach does not work with base-ui's `SelectTrigger`, which renders as a plain `<button>` without a `combobox` ARIA role in jsdom. The plan itself anticipated this and provided the fallback instruction: "fall back to `screen.getByText` and click that to open the dropdown."
- **Fix:** Used `document.querySelector('[data-slot="select-trigger"]')` to locate the trigger button, consistent with how the rest of the test suite queries base-ui primitives.
- **Files modified:** `MembershipsListPage.within.test.tsx`
- **Commit:** 7e04ac4

None of the other plan instructions required deviation — all acceptance criteria matched exactly.

## Threat Surface Scan

| Threat ID | Mitigation | Status |
|-----------|-----------|--------|
| T-28-08-01 | `?within=99` → Zod rejects, defaults to 7 | Implemented via `min(1).max(30).default(7)` |
| T-28-08-02 | `?within=abc` → `z.coerce.number()` rejects, defaults to 7 | Implemented |
| T-28-08-03 | Rapid selector changes → TanStack Query dedupes | Accepted (no amplification) |

No new threat surface introduced beyond what is in the plan's threat model.

## Known Stubs

None — the selector is fully wired. `search.within` flows through `useMembershipsList` to `services.memberships.list({ ..., within })`. Both HTTP and mock impls already accept `within` (Phase 24 DEBT-02).

## Commits

| Task | Description | Hash |
|------|-------------|------|
| 1 | Add `within` to searchSchema + forward to useMembershipsList | 80d4f11 |
| 2 | Add within selector to MembershipsListPage filter row | 8bf5b8f |
| 3 | Add Vitest integration test (4 tests) | 7e04ac4 |

## Self-Check

- [x] `routes/_protected/memberships.tsx` contains `within: z.coerce.number().int().min(1).max(30).default(7)` — FOUND
- [x] `MembershipsListPage.tsx` contains `search.expiring &&` conditional — FOUND
- [x] `MembershipsListPage.within.test.tsx` exists — FOUND
- [x] Commits 80d4f11, 8bf5b8f, 7e04ac4 exist — FOUND
- [x] Full suite: 41 test files, 232 tests — all pass
- [x] Typecheck: 0 errors
- [x] Lint: 0 errors (2 pre-existing warnings)
- [x] Drift gate: `git diff --exit-code apps/backend/openapi.json packages/api-client/src/schema.d.ts` — untouched

## Self-Check: PASSED
