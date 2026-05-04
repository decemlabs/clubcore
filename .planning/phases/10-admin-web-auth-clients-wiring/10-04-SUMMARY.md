---
phase: 10-admin-web-auth-clients-wiring
plan: "04"
subsystem: http
tags: [admin-web, http, tanstack-query, session, refresh, rbac, @sportzal/api-client]

# Dependency graph
requires:
  - phase: 09-openapi-pipeline-api-client
    provides: request<P,M> typed fetcher + ApiError + schema.d.ts
  - phase: 10-admin-web-auth-clients-wiring-02
    provides: AuthService + ClientsService contracts + authKeys factory
  - phase: 10-admin-web-auth-clients-wiring-03
    provides: mock services for auth + clients
provides:
  - http/auth.ts implementing AuthService via @sportzal/api-client.request()
  - http/clients.ts implementing ClientsService via @sportzal/api-client.request()
  - http/_envelope.ts unwrap<T> stripping Phase 4 D-07 ResponseEnvelope
  - redirect-on-session-expired.ts single-flight session_expired handler
  - QueryClient with QueryCache + MutationCache wired to redirectOnSessionExpired
  - router.ts getSession() branching on API_MODE (mock: Zustand, http: query cache)
  - useCurrentRole() hook as unified role source for components in both modes
  - RoleGate refactored to use useCurrentRole instead of useSessionStore directly
  - shared/session/index.ts barrel export
affects:
  - 10-05 (login route + /login path typed in routeTree — redirect helper TODO resolved)
  - 10-06 (mock services parity — uses same contracts as http transport)
  - any feature adding TanStack Query hooks (inherits session_expired redirect globally)

# Tech tracking
tech-stack:
  added:
    - QueryCache/MutationCache from @tanstack/react-query (global onError hook)
  patterns:
    - Service boundary envelope unwrap (D-07): unwrap<T>(raw) at http wrapper level, not fetcher
    - Module-scoped redirecting flag for single-flight session_expired redirect (D-07)
    - Lazy dynamic import(@/app/router) to break queryClient<->router circular dep (Pitfall 3)
    - API_MODE branch in getSession() and useCurrentRole() per D-05
    - Unconditional hook calls (both useSessionStore + useQuery) regardless of API_MODE

key-files:
  created:
    - apps/admin-web/src/shared/api/services/http/_envelope.ts
    - apps/admin-web/src/shared/api/services/http/_envelope.test.ts
    - apps/admin-web/src/shared/api/services/http/auth.ts
    - apps/admin-web/src/shared/api/services/http/clients.ts
    - apps/admin-web/src/features/auth/api/redirect-on-session-expired.ts
    - apps/admin-web/src/features/auth/api/redirect-on-session-expired.test.ts
    - apps/admin-web/src/shared/session/useCurrentRole.ts
    - apps/admin-web/src/shared/session/index.ts
  modified:
    - apps/admin-web/src/shared/api/services/http/index.ts
    - apps/admin-web/src/app/queryClient.ts
    - apps/admin-web/src/app/router.ts
    - apps/admin-web/src/shared/session/RoleGate.tsx

key-decisions:
  - "HTTP methods use lowercase ('get', 'post', etc.) to match openapi paths map type — plan said uppercase but TS type requires lowercase"
  - "telegramStatus and clients.list use URL string append for query params (RequestInitWithBody has no query field)"
  - "clients path param is client_id not id — matches the openapi schema.d.ts path /api/v1/clients/{client_id}"
  - "login/telegramVerify unwrap LoginResponse{user} to extract MeResponse-compatible user"
  - "navigate type-cast in redirect helper with TODO comment — /login not in routeTree.gen.ts until Plan 05"
  - "vi.hoisted() required for test mocks referencing variables used in vi.mock factory functions"
  - "setTimeout(r, 0) instead of Promise.resolve() chains for lazy-import + .then microtask settling"

patterns-established:
  - "Envelope unwrap at service boundary: all http wrappers import unwrap from _envelope.ts"
  - "No body-type generic on request<P,M>() — only path/method generics inferred from arguments"
  - "Session source branching: getSession() in router.ts + useCurrentRole() in RoleGate both use API_MODE"

requirements-completed: [FE-01, FE-05]

# Metrics
duration: 6min
completed: "2026-05-04"
---

# Phase 10 Plan 04: HTTP Transport + Session Redirect Integration Summary

**HTTP AuthService + ClientsService via @sportzal/api-client with global session_expired single-flight redirect and API_MODE-aware role adapter; RoleGate now reads the correct role in both mock and http modes**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-04T16:21:49Z
- **Completed:** 2026-05-04T16:28:00Z
- **Tasks:** 3
- **Files modified:** 12

## Accomplishments

- HTTP transport implemented: `auth.ts` and `clients.ts` wrap `@sportzal/api-client.request()` for all 11 endpoints; `_envelope.ts` strips Phase 4 D-07 `{data:T}` envelopes at the service boundary
- Global session_expired handler: `redirect-on-session-expired.ts` with module-scoped flag collapses concurrent 401 storms to one `router.navigate()` call; lazy dynamic import breaks the circular dep
- Integration spine wired: `queryClient` → `QueryCache + MutationCache onError` → `redirectOnSessionExpired`; `router.getSession()` and `useCurrentRole()` both branch on `API_MODE`; `RoleGate` fixed to use the unified hook

## Task Commits

1. **Task 1: http/auth.ts + http/clients.ts + populate http/index.ts** - `ff8e84e` (feat)
2. **Task 2: redirect-on-session-expired.ts + test** - `3678993` (feat)
3. **Task 3: queryClient + router + useCurrentRole + RoleGate refactor** - `af61d12` (feat)

## Files Created/Modified

- `apps/admin-web/src/shared/api/services/http/_envelope.ts` - unwrap<T> strips {data:T} envelope at service boundary (Phase 4 D-07)
- `apps/admin-web/src/shared/api/services/http/_envelope.test.ts` - 4 tests: envelope strip, 204 undefined, pass-through, null/primitive
- `apps/admin-web/src/shared/api/services/http/auth.ts` - AuthService: 6 endpoints via request(); login/telegramVerify map LoginResponse.user to MeResponse
- `apps/admin-web/src/shared/api/services/http/clients.ts` - ClientsService: 5 endpoints via request(); uses client_id path param per schema
- `apps/admin-web/src/shared/api/services/http/index.ts` - populated: `export const services = { auth, clients } as const`
- `apps/admin-web/src/features/auth/api/redirect-on-session-expired.ts` - single-flight redirect helper with module flag + lazy router import
- `apps/admin-web/src/features/auth/api/redirect-on-session-expired.test.ts` - 5 tests: navigate fires once, concurrent suppressed, pass-through, flag reset
- `apps/admin-web/src/app/queryClient.ts` - QueryCache + MutationCache both wired to redirectOnSessionExpired
- `apps/admin-web/src/app/router.ts` - getSession() branches on API_MODE; http fallback is 'reception' never 'owner'
- `apps/admin-web/src/shared/session/useCurrentRole.ts` - unified hook: mock → Zustand, http → useQuery(authKeys.me)
- `apps/admin-web/src/shared/session/RoleGate.tsx` - refactored to use useCurrentRole() (removed direct useSessionStore read)
- `apps/admin-web/src/shared/session/index.ts` - barrel export for all session primitives

## Decisions Made

- **HTTP method case**: Plan said uppercase but TypeScript openapi paths map requires lowercase — used `'get'`, `'post'`, etc. Methods still work correctly since fetcher.ts line 125 calls `.toUpperCase()` internally
- **Query params via URL string**: `RequestInitWithBody` has no `query` field — telegramStatus and clients.list append params to URL string with `as never` cast for openapi type
- **Path param name**: Clients endpoint path param is `client_id` (per schema.d.ts `/api/v1/clients/{client_id}`), not `id` as plan example suggested
- **login/telegramVerify response mapping**: Schema returns `ResponseEnvelope_LoginResponse_` wrapping `{user: UserPublic}` — unwrap outer envelope then extract `.user` to get MeResponse
- **navigate type cast**: `/login` route not in routeTree.gen.ts until Plan 05 — used `(router.navigate as (opts: any) => Promise<void>)` with TODO comment
- **vi.hoisted() for test mocks**: vitest hoists `vi.mock()` to top of file; mock factory references must be created with `vi.hoisted()` to avoid "Cannot access before initialization" errors
- **setTimeout(0) for microtask settling**: Dynamic import + `.then` chain needs `new Promise(r => setTimeout(r, 0))` rather than multiple `await Promise.resolve()` chains in vitest

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] HTTP methods must be lowercase to match openapi paths type**
- **Found during:** Task 1 typecheck
- **Issue:** Plan recommended uppercase methods ('GET', 'POST', etc.) for "consistency" but openapi schema.d.ts type `keyof paths[P] & string` requires lowercase ('get', 'post', etc.)
- **Fix:** Changed all method strings to lowercase in auth.ts and clients.ts
- **Files modified:** auth.ts, clients.ts
- **Verification:** pnpm typecheck passes with zero errors for http/ files
- **Committed in:** ff8e84e (Task 1 commit)

**2. [Rule 3 - Blocking] navigate type-cast needed for missing /login route**
- **Found during:** Task 2 typecheck
- **Issue:** router.navigate({ to: '/login' }) fails type check because /login is not in routeTree.gen.ts yet (added in Plan 05)
- **Fix:** Type-cast navigate with `as (opts: any) => Promise<void>` with TODO Plan 05 comment
- **Files modified:** redirect-on-session-expired.ts
- **Verification:** pnpm typecheck passes; navigate still calls correctly at runtime
- **Committed in:** 3678993 (Task 2 commit)

**3. [Rule 1 - Bug] Test mock initialization order required vi.hoisted()**
- **Found during:** Task 2 test run
- **Issue:** `vi.mock()` factories are hoisted but `clearMock`/`navigateMock` defined below — "Cannot access before initialization" ReferenceError
- **Fix:** Wrapped mock creation in `vi.hoisted()` so variables are initialized before the hoisted `vi.mock()` factories execute
- **Files modified:** redirect-on-session-expired.test.ts
- **Verification:** All 5 tests pass
- **Committed in:** 3678993 (Task 2 commit)

**4. [Rule 1 - Bug] Promise.resolve() insufficient for lazy import microtask settling**
- **Found during:** Task 2 test run
- **Issue:** Tests expecting navigate to be called after `await Promise.resolve()` x2 were failing — dynamic import + .then + .finally chain requires more microtask settling
- **Fix:** Used `await new Promise(r => setTimeout(r, 0))` which flushes the full microtask queue including timers
- **Files modified:** redirect-on-session-expired.test.ts
- **Verification:** All 5 tests pass consistently
- **Committed in:** 3678993 (Task 2 commit)

---

**Total deviations:** 4 auto-fixed (2 bugs, 2 blocking)
**Impact on plan:** All auto-fixes necessary for correctness and test stability. No scope creep.

## Known Stubs

- `redirect-on-session-expired.ts:36` — `// TODO Plan 05: /login route not in routeTree.gen.ts yet — added in Plan 05.` — The navigate type-cast is intentional; it resolves when Plan 05 adds the /login route and the routeTree regenerates.

## Issues Encountered

- Pre-existing test failure in `src/shared/ui/components-json.test.ts` (`style: 'new-york'` expected, `'base-nova'` received) — introduced in Plan 03 when components.json was updated for ReUI registry. Not caused by this plan.

## Next Phase Readiness

- FE-01 complete: http transport compiles and type-checks; both AuthService + ClientsService implemented
- FE-05 partial: session_expired redirect handler wired and tested; Plan 05 completes by adding the /login route target
- D-05 complete: API_MODE branching in both router context and useCurrentRole hook
- D-07 complete: QueryCache + MutationCache wired to global session_expired handler
- RESEARCH Pitfalls 2 + 3 explicitly fixed
- Plan 05 (login route) unblocked: routeTree.gen.ts will add /login, resolving the TODO type cast

## Self-Check: PASSED

All 8 created files exist. All 3 task commits verified in git log.

---
*Phase: 10-admin-web-auth-clients-wiring*
*Completed: 2026-05-04*
