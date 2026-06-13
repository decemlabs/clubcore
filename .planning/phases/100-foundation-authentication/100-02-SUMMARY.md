---
phase: 100-foundation-authentication
plan: "02"
subsystem: transport
tags: [transport, csrf, auth, fetch, tanstack-query, vitest]

# Dependency graph
requires:
  - "100-01 (pnpm workspace, ESLint boundary, @clubcore/api-client dep)"
provides:
  - "staffRequest<P,M> typed transport with credentials:'include' + CSRF double-submit"
  - "readStaffCsrfCookie() — reads clubcore_csrf (JS-readable double-submit token)"
  - "staffRefreshOnce() — single-flight POST /api/v1/auth/refresh"
  - "STAFF_AUTH_EXEMPT_PATHS — login/refresh/logout/password-reset bypass list"
  - "ApiError re-exported from @clubcore/api-client (string code field)"
  - "mockResponse<T>() preserved for all non-auth domain swap-seam files"
  - "subscribeSessionExpired / publishSessionExpired pub/sub (authBus)"
  - "QueryClient with QueryCache+MutationCache onError session-expiry handler"
affects:
  - "100-03 (auth wiring — useLogin/useLogout/useSession will call staffRequest)"
  - "101-104 (each domain flip replaces mockResponse with staffRequest)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CSRF double-submit: read clubcore_csrf cookie, set X-CSRF-Token on POST/PUT/PATCH/DELETE"
    - "Single-flight refresh: module-scoped Promise + queueMicrotask slot-clear"
    - "401-storm collapse: _redirecting flag in queryClient with 5s reset window"
    - "Pub/sub auth bus: pure module-scoped Set, no React/router imports"
    - "Re-export ApiError from @clubcore/api-client to share one class identity"

key-files:
  created:
    - "apps/admin-app/src/lib/authBus.ts — subscribeSessionExpired/publishSessionExpired"
    - "apps/admin-app/src/api/client.test.ts — 17 vitest unit tests for transport"
  modified:
    - "apps/admin-app/src/api/client.ts — full rewrite: staffRequest, CSRF, 401→refresh→retry, ApiError re-export, mockResponse preserved"
    - "apps/admin-app/src/api/query-client.ts — QueryCache+MutationCache onError, handleSessionExpired + publishSessionExpired"

key-decisions:
  - "D-100-02-APICLASS: ApiError is re-exported from @clubcore/api-client (not a local class). This ensures instanceof checks across queryClient.ts, client.test.ts, and future feature hooks all use the same class identity — avoiding the 'same error, different instanceof' footgun."
  - "D-100-02-JSONLY: staffRequest URL paths are used as-is (same-origin, Vite proxy handles /api/* in dev). No VITE_API_BASE_URL prefix to avoid double-prefix on already-absolute paths."
  - "D-100-02-MOCKPRESERVE: mockResponse<T>() signature and export name are identical to the original — zero changes required in any of the 19 feature api.ts files that import it."

# Metrics
duration: 4min
completed: 2026-06-13
---

# Phase 100 Plan 02: Transport Seam Summary

**Staff-scoped typed transport with CSRF double-submit, single-flight 401→refresh→retry, authBus pub/sub, and session-expiry-aware QueryClient — all unit-tested with mocked fetch; mockResponse preserved for non-auth domains**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-06-13T08:57:28Z
- **Completed:** 2026-06-13T09:01:07Z
- **Tasks:** 2
- **Files created/modified:** 4

## Accomplishments

- `apps/admin-app/src/api/client.ts` rewritten as a staff-scoped transport port of `clientFetcher.ts`:
  - `staffRequest<P,M>` sends `credentials:'include'` on every request
  - `readStaffCsrfCookie()` reads `clubcore_csrf` and injects `X-CSRF-Token` on POST/PUT/PATCH/DELETE
  - `staffRefreshOnce()` single-flights POST `/api/v1/auth/refresh` with `queueMicrotask` slot-clear
  - `STAFF_AUTH_EXEMPT_PATHS` prevents refresh loop on login/logout/refresh/password-reset paths
  - 401 on non-exempt path → single-flight refresh → one retry → `ApiError('session_expired')` on second 401
  - `ApiError` re-exported from `@clubcore/api-client` (string `code` field, not `status:number`)
  - `mockResponse<T>()` preserved with identical signature for all 19 non-auth domain feature files

- `apps/admin-app/src/lib/authBus.ts` created — pure module-scoped pub/sub, no React/router imports:
  - `subscribeSessionExpired(cb)` → returns unsubscribe function for useEffect cleanup
  - `publishSessionExpired()` → calls all subscribers

- `apps/admin-app/src/api/query-client.ts` upgraded with `QueryCache` + `MutationCache` `onError`:
  - `handleSessionExpired` guards on `instanceof ApiError && code === 'session_expired'`
  - Module-scoped `_redirecting` flag collapses 401-storms to a single publish within 5 seconds
  - `publishSessionExpired()` called once → `LoginPage.tsx` useEffect (plan 100-03) will subscribe and navigate

- `apps/admin-app/src/api/client.test.ts` — 17 vitest unit tests, all green:
  - CSRF injection on POST/PUT, absence on GET, absence when cookie missing
  - `credentials:'include'` on every request
  - `401 → refresh → retry → retryBody` flow (3 fetch calls, correct URL on #2)
  - CSRF re-read after rotation on retry
  - `session_expired` when refresh returns 401
  - `session_expired` when retry still 401 after successful refresh
  - Exempt path (login) does not trigger refresh
  - `network_error` on fetch rejection
  - `ApiError` instanceof check
  - `mockResponse` resolves correctly with and without delay

## Task Commits

1. **Task 1: Build the staff-scoped typed transport** — `d6018689` (feat)
2. **Task 2: Add authBus, upgrade QueryClient, add transport unit tests** — `16606594` (feat)

## Files Created/Modified

- `apps/admin-app/src/api/client.ts` — rewritten; staffRequest + CSRF + refresh + ApiError re-export + mockResponse preserved
- `apps/admin-app/src/lib/authBus.ts` — created; pure pub/sub
- `apps/admin-app/src/api/query-client.ts` — upgraded; QueryCache + MutationCache onError
- `apps/admin-app/src/api/client.test.ts` — created; 17 unit tests

## Decisions Made

- **D-100-02-APICLASS**: `ApiError` is re-exported from `@clubcore/api-client` (not re-implemented locally). Eliminates the dual-class identity issue where `error instanceof ApiError` would fail if query-client.ts and client.ts imported from different sources.
- **D-100-02-JSONLY**: Transport uses paths as-is (no `VITE_API_BASE_URL` prefix) matching clientFetcher.ts behavior — paths already start with `/api/v1/...` and the Vite proxy handles routing in dev.
- **D-100-02-MOCKPRESERVE**: `mockResponse<T>(value, delay = 0)` export signature kept identical. Zero cascading changes to the 19 feature api.ts files.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] JSDoc comment with glob pattern broke TypeScript parser**
- **Found during:** Task 1 (first typecheck run)
- **Issue:** `feature/*/api.ts` in a JSDoc block comment caused TS parser errors — the `*/` sequence looked like a comment close to the parser, producing 30+ syntax errors in lines 15-17 and 272-274.
- **Fix:** Replaced `feature/*/api.ts` with `feature api.ts` in the two affected comments.
- **Files modified:** `apps/admin-app/src/api/client.ts`
- **Verification:** `pnpm -F @clubcore/admin-app typecheck` passes cleanly after the fix.
- **Committed in:** `d6018689` (Task 1)

---

**Total deviations:** 1 auto-fixed (Rule 1 — Bug)
**Impact on plan:** Single-line comment text only; no functional change.

## Known Stubs

None — this plan produces transport infrastructure only; no UI components and no data sources to wire.

## Threat Surface Scan

The following STRIDE mitigations from the plan's threat model are confirmed implemented:

| Threat ID | Mitigation | File | Verified |
|-----------|------------|------|---------|
| T-100-03 | X-CSRF-Token from clubcore_csrf on every POST/PUT/PATCH/DELETE | client.ts | unit tested |
| T-100-04 | staffRefreshOnce → /api/v1/auth/refresh ONLY (never client path) | client.ts | unit tested |
| T-100-05 | session_expired after second 401; _redirecting flag prevents loop | client.ts + query-client.ts | unit tested |
| T-100-06 | Only clubcore_csrf read by JS; cc_access/cc_refresh travel via credentials:'include' | client.ts | by design |

No new security-relevant surface introduced beyond what the plan's threat model covers.

## Self-Check: PASSED

All files verified present:
- `apps/admin-app/src/api/client.ts` — found
- `apps/admin-app/src/lib/authBus.ts` — found
- `apps/admin-app/src/api/query-client.ts` — found
- `apps/admin-app/src/api/client.test.ts` — found
- `.planning/phases/100-foundation-authentication/100-02-SUMMARY.md` — found

All commits verified:
- `d6018689` — Task 1 (transport)
- `16606594` — Task 2 (authBus + QueryClient + tests)

## Next Phase Readiness

- `staffRequest` is available for plan 100-03 to wire `useLogin`, `useLogout`, `useSession`
- `authBus` is ready for `LoginPage.tsx` to subscribe in a `useEffect`
- All 75 tests green; typecheck and lint clean
