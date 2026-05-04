---
phase: 10-admin-web-auth-clients-wiring
plan: 08
subsystem: ui
tags: [tanstack-router, rbac, redirect, regression]

requires:
  - phase: 10-admin-web-auth-clients-wiring
    provides: "RBAC route guards and http-mode auth-failure redirect (CR-01 fix in commit 9fdc8e2)"
provides:
  - "Crash-free RBAC redirect for reception users hitting /finance, /settings, and other owner-only routes"
  - "Crash-free /login redirect from _protected.tsx http-mode 401 branch"
  - "Regression test asserting forbidden redirect string is built without object-coercion crash"
affects: [phase-11+, future-route-guards, future-redirect-builders]

tech-stack:
  added: []
  patterns:
    - "Use ParsedLocation.searchStr (encoded string) when concatenating with pathname; never ParsedLocation.search (parsed object)"

key-files:
  created:
    - apps/admin-web/src/routes/_protected/rbac-redirect.test.tsx
  modified:
    - apps/admin-web/src/routes/_protected.tsx
    - apps/admin-web/src/routes/_protected/finance.tsx
    - apps/admin-web/src/routes/_protected/settings.tsx
    - apps/admin-web/src/routes/_protected/staff.tsx
    - apps/admin-web/src/routes/_protected/schedule.tsx
    - apps/admin-web/src/routes/_protected/clients.tsx

key-decisions:
  - "Chose location.searchStr over location.href: keeps the CR-01 security guarantee (no origin in forbidden/next value) while delivering a string-typed property — searchStr is '' or '?...' encoded form."
  - "Regression test directly invokes Route.options.beforeLoad with a synthetic ParsedLocation rather than mounting RouterProvider — avoids jsdom-navigation flakiness and isolates the coercion contract."
  - "Test 4 simulates the failure mode with a Proxy whose Symbol.toPrimitive throws, locking in the contract that beforeLoad must read .searchStr (not .search) regardless of how TanStack's parsed-search proxy behaves."

patterns-established:
  - "Pattern: Building redirect search values from current location uses pathname + searchStr, both string-typed."
  - "Pattern: Regression tests for route guards invoke Route.options.beforeLoad directly with synthetic context/location, asserting on the thrown redirect's .search payload (with dual-read for top-level vs .options nesting)."

requirements-completed: []

duration: 6min
completed: 2026-05-04
---

# Phase 10 Plan 08: RBAC redirect crash fix (UAT-08 gap closure) Summary

**Replaced `location.search` (parsed object) with `location.searchStr` (encoded string) in 6 redirect-builder sites, eliminating the `TypeError: Cannot convert object to primitive value` crash on /finance and /settings for reception users.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-05-04T18:22:00Z
- **Completed:** 2026-05-04T18:28:00Z
- **Tasks:** 2
- **Files modified:** 6 (route guards) + 1 created (test)

## Accomplishments
- UAT-08 blocker (RBAC redirect crash for reception → /finance, /settings) resolved.
- All five `_protected/<route>.tsx` guards (finance, settings, staff, schedule, clients) plus the http-mode 401 branch in `_protected.tsx` now build their redirect strings via `location.pathname + (location.searchStr ?? '')`.
- Regression test (`rbac-redirect.test.tsx`, 4 cases) locks in the contract — including a Proxy-based simulation of TanStack's parsed-search throwing `Symbol.toPrimitive`.
- Full admin-web test suite green: 78/78 (was 74; +4 new).
- Typecheck clean — proves `searchStr` is a string-typed property of `ParsedLocation` on the installed TanStack Router 1.95.0.

## Task Commits

1. **Task 1: Replace `location.search` with `location.searchStr` in all six redirect sites** — `5e5324e` (fix)
2. **Task 2: Add regression test for RBAC redirect string construction** — `c5a5ea9` (test)

## Files Created/Modified

### Modified — single-token swap (`location.search` → `location.searchStr`)

| File | Line | Context |
|------|------|---------|
| `apps/admin-web/src/routes/_protected/finance.tsx` | 11 | RBAC `beforeLoad` → `forbidden` payload |
| `apps/admin-web/src/routes/_protected/settings.tsx` | 11 | RBAC `beforeLoad` → `forbidden` payload |
| `apps/admin-web/src/routes/_protected/staff.tsx` | 11 | RBAC `beforeLoad` → `forbidden` payload |
| `apps/admin-web/src/routes/_protected/schedule.tsx` | 11 | RBAC `beforeLoad` → `forbidden` payload |
| `apps/admin-web/src/routes/_protected/clients.tsx` | 21 | RBAC `beforeLoad` → `forbidden` payload |
| `apps/admin-web/src/routes/_protected.tsx` | 19 | http-mode 401 branch → `next` payload |

### Created

- `apps/admin-web/src/routes/_protected/rbac-redirect.test.tsx` — 4 test cases:
  1. `reception → /finance` produces `forbidden=/finance` redirect with no TypeError.
  2. `reception → /settings` produces `forbidden=/settings` redirect.
  3. `searchStr` (`'?page=2'`) is preserved → `forbidden=/finance?page=2`.
  4. **Negative regression:** `search` is a Proxy whose `Symbol.toPrimitive`/`toString`/`valueOf` throw — `beforeLoad` still succeeds because it reads `searchStr`, not `search`.

## TanStack Router fact justifying the fix

`ParsedLocation` exposes both `search` (parsed object form, e.g. `{ page: 1, pageSize: 20 }`) and `searchStr` (encoded string form, `''` or `'?...'`). The `+` operator on the parsed object triggers `Symbol.toPrimitive`, which on TanStack's parsed-search proxy throws "Cannot convert object to primitive value". `searchStr` is already a string and concatenates safely. Both properties are origin-free, so the CR-01 security intent (no scheme/host in `forbidden` / `next`) is preserved.

## Decisions Made

- **Use `searchStr`, not `href`.** Both are origin-free in TanStack Router (`href` is `pathname + searchStr + hash`), but `searchStr` makes the coercion-free contract explicit at the call site and isolates the search-string concern from any future `hash` usage.
- **Keep the `?? ''` defensive guard.** `searchStr` is typed as `string` and should always be defined, but matching the existing nullish-coalescing style keeps the diff minimal and the call site uniform across all six occurrences.
- **Regression test invokes `Route.options.beforeLoad` directly.** No router/jsdom navigation; deterministic and fast (3 ms total for 4 cases). Synthetic `ParsedLocation` is shape-cast with `as unknown as ...location` to avoid leaking router internals into the test.

## Deviations from Plan

None — plan executed exactly as written. Single-token swap in 6 files; regression test created with the four cases the plan specified; sanity-check (revert finance.tsx to buggy `.search`) confirmed cases 3 and 4 fail with the original `Cannot convert object to primitive value` error before being restored to fixed state. No commit of the revert.

## Issues Encountered

- `pnpm -F admin-web typecheck` filter as written in the plan does not match the workspace package name (`sportzal-adminka`). Used `cd apps/admin-web && pnpm typecheck` and `pnpm -F sportzal-adminka typecheck` interchangeably. No code impact; just a CLI invocation note for verifiers.

## Verification

| Check | Result |
|-------|--------|
| `grep -rn "location\.pathname + (location\.search " apps/admin-web/src/routes` | 0 hits ✓ |
| `grep -rn "location\.pathname + (location\.searchStr " apps/admin-web/src/routes \| wc -l` | 6 ✓ |
| `pnpm typecheck` (admin-web) | passes ✓ |
| `pnpm test` (admin-web, full suite) | 78/78 pass (19 files) ✓ |
| Sanity-check revert of finance.tsx | cases 3 + 4 fail with `TypeError: Cannot convert object to primitive value` — test guards the regression ✓ |

UAT Test 8 (RBAC redirect) is unblocked. The verifier should re-run it manually in the next pass:
- Switch role to "Администратор стойки" (reception) via the role switcher.
- Navigate to `/finance` → expect redirect to `/?forbidden=%2Ffinance` (or `/?forbidden=/finance`) and the index page rendering the forbidden notice with `/finance` in a `<code>` element.
- Repeat for `/settings`. Browser console must show no `TypeError`.

## Next Phase Readiness

- This was the only `severity: blocker` gap in `10-UAT.md`. With it closed, Phase 10 sign-off is unblocked.
- No follow-up plans required.

## Self-Check

- [x] All claimed files exist on disk.
- [x] All claimed commit hashes exist in `git log`.

---
*Phase: 10-admin-web-auth-clients-wiring*
*Completed: 2026-05-04*
