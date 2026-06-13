---
phase: 100-foundation-authentication
verified: 2026-06-13T12:26:00Z
status: human_needed
score: 14/14 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Staff member logs in, receives cc_access/cc_refresh/clubcore_csrf cookies, and the session survives a full browser refresh"
    expected: "After login, refreshing the browser still shows the authenticated dashboard (not the login page); dev tools show cc_* cookies persisted; the CSRF cookie is JS-readable"
    why_human: "Requires a running docker compose up stack; cookie round-trip cannot be verified by static analysis or unit tests"
  - test: "Mid-session 401 — expire the cc_access cookie server-side and perform any query"
    expected: "The app transparently navigates to /login?state=expired; the ExpiredScreen renders; no crash or stale data visible; network tab shows exactly one POST /api/v1/auth/refresh before the redirect"
    why_human: "Requires a live backend, manual cookie manipulation in DevTools, and browser-level observation of the redirect sequence"
---

# Phase 100: Foundation + Authentication — Verification Report

**Phase Goal:** admin-app is in the clubcore repo, talks to the real backend over staff cookies + CSRF, the deferred screens are gated, and a staff member can log in / log out / see their role reflected in the UI.
**Verified:** 2026-06-13T12:26:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `apps/admin-app` installs, typechecks, lints, tests and builds under pnpm in the clubcore workspace | ✓ VERIFIED | `pnpm -F @clubcore/admin-app typecheck`: clean; `lint`: clean; `test`: 99/99 pass; `build`: succeeds |
| 2 | A dedicated parallel admin-app CI job runs typecheck + lint + test + build | ✓ VERIFIED | `.github/workflows/ci.yml` line 206: `admin-app:` job with four `pnpm -F @clubcore/admin-app` steps |
| 3 | The recursive frontend CI steps no longer include admin-app (no double-run) | ✓ VERIFIED | ci.yml lines 140/143/146: all three recursive steps include `--filter '!@clubcore/admin-app'` |
| 4 | admin-app depends on `@clubcore/api-client` via `workspace:*` and can import its `paths`/`ApiError` | ✓ VERIFIED | `package.json` `dependencies["@clubcore/api-client"]: "workspace:*"`; `client.ts` imports `ApiError` and `type { paths }` from `@clubcore/api-client` |
| 5 | Vite dev proxies `/api` to the backend so requests are same-origin in dev (no CORS) | ✓ VERIFIED | `vite.config.ts` lines 22-28: `server.proxy['/api']` with `VITE_API_PROXY_TARGET ?? 'http://localhost:8000'`, `changeOrigin: true` |
| 6 | Every mutating request (POST/PUT/PATCH/DELETE) carries an `X-CSRF-Token` read from the `clubcore_csrf` cookie | ✓ VERIFIED | `client.ts` lines 197-199: `if (isMutating(upper)) { const csrf = readStaffCsrfCookie(); if (csrf) headers.set('X-CSRF-Token', csrf) }`; unit tested in `client.test.ts` (17 tests) |
| 7 | Every request is sent with `credentials:'include'` so cc_access/cc_refresh cookies flow | ✓ VERIFIED | `client.ts` line 217: `credentials: 'include'`; unit tested |
| 8 | A 401 on a non-exempt path triggers a single-flight POST `/api/v1/auth/refresh`, then one retry; a second 401 throws `ApiError('session_expired')` | ✓ VERIFIED | `client.ts` lines 234-267: full refresh + retry + session_expired flow; `STAFF_AUTH_EXEMPT_PATHS` exported; 17 unit tests cover all branches |
| 9 | A `session_expired` error published once routes the app toward /login without crashing (authBus + QueryClient onError) | ✓ VERIFIED | `query-client.ts`: `QueryCache` + `MutationCache` `onError` with `_redirecting` flag; `authBus.ts`: `publishSessionExpired`; `RequireAuth.tsx`: subscribes and navigates to `/login?state=expired` |
| 10 | A staff member logs in via POST `/api/v1/auth/login` and lands on the dashboard; `invalid_credentials` → generic banner; 422 fields → inline; other codes → toast | ✓ VERIFIED | `LoginForm.tsx`: `useLogin()` wired, anti-oracle banner «Неверный email или пароль.», field error mapping, 5xx toast; no `setTimeout(onSuccess` simulation |
| 11 | The session survives a browser refresh — `useSession()` reads GET `/api/v1/auth/me`; no role mirrored into a store | ✓ VERIFIED | `features/auth/api.ts`: `useSession()` queries `/api/v1/auth/me` via `staffRequest`; `RequireAuth.tsx` guards the AppLayout branch; no Zustand role store |
| 12 | Unauthenticated navigation redirects to `/login`; logout ends the session; mid-session 401 → `/login?state=expired` showing ExpiredScreen | ✓ VERIFIED | `RequireAuth.tsx`: `isError` → `<Navigate to={ROUTES.login} replace />`; `useLogout` removes `authKeys.me` on settled; authBus subscription in `RequireAuth` navigates to `?state=expired` |
| 13 | can(role, action, resource) and the 41-entry OWNER_ONLY matrix live in admin-app and are byte-parity with the backend `permissions.py`; the CISO-01 parity test is green | ✓ VERIFIED | `can.ts`: 41 unique pairs confirmed by `node -e` regex scan; `test_rbac_parity.py`: 4/4 assertions pass; `_CAN_TS`/`_REGISTRY_TS` repointed to admin-app |
| 14 | Deferred screens render `<ComingSoon/>` instead of their page; deferred items removed from sidebar nav for all roles; sidebar shows real fullName + role label with loading skeleton; owner-only nav items (Финансы, Отчёты) absent for reception | ✓ VERIFIED | `router.tsx`: 8 deferred routes with `element: <ComingSoon />`; `nav-items.ts`: Сообщения/Уведомления/Филиалы absent, Финансы+Отчёты flagged `ownerOnly: true`; `AppSidebar.tsx`: `useSession()` + `can()` + role pill + footer card + `getInitials` |

**Score:** 14/14 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/admin-app/package.json` | `@clubcore/admin-app`, pnpm@9.15.9, api-client workspace dep | ✓ VERIFIED | `name: "@clubcore/admin-app"`, `packageManager: "pnpm@9.15.9"`, `dependencies["@clubcore/api-client"]: "workspace:*"` |
| `apps/admin-app/vite.config.ts` | `server.proxy /api` block | ✓ VERIFIED | Lines 22-28: `VITE_API_PROXY_TARGET ?? 'http://localhost:8000'` |
| `apps/admin-app/eslint.config.js` | import boundary zones + VITE_API_MODE chokepoint | ✓ VERIFIED | `import/no-restricted-paths` zone + `no-restricted-syntax` VITE_API_MODE chokepoint, both present |
| `.github/workflows/ci.yml` | admin-app parallel job + recursive-filter exclusion | ✓ VERIFIED | `admin-app:` job at line 206; all 3 recursive steps exclude `@clubcore/admin-app` |
| `pnpm-lock.yaml` | workspace lockfile includes admin-app | ✓ VERIFIED | Line 21: `apps/admin-app:` entry |
| `apps/admin-app/src/api/client.ts` | staffRequest, CSRF, refresh, ApiError re-export, mockResponse | ✓ VERIFIED | Full typed transport with all required exports and behaviors |
| `apps/admin-app/src/lib/authBus.ts` | subscribeSessionExpired / publishSessionExpired | ✓ VERIFIED | Pure pub/sub, 36 lines |
| `apps/admin-app/src/api/query-client.ts` | QueryCache+MutationCache onError, publishSessionExpired | ✓ VERIFIED | `_redirecting` flag, 5-second window |
| `apps/admin-app/src/api/client.test.ts` | 17 unit tests, all green | ✓ VERIFIED | 17/17 tests pass |
| `apps/admin-app/src/features/auth/schemas.ts` | LoginRequest/Response, MeResponse, PasswordReset schemas | ✓ VERIFIED | 6 schemas; `newPassword` field present; `password.min(12)` |
| `apps/admin-app/src/features/auth/api.ts` | authKeys, useSession, useLogin, useLogout + password-reset hooks | ✓ VERIFIED | All 5 hooks exported; http-only mode (no mock path) |
| `apps/admin-app/src/features/auth/RequireAuth.tsx` | Route guard, authBus subscription, /login redirect | ✓ VERIFIED | 62 lines; isPending→skeleton, isError→Navigate, authBus subscription in useEffect |
| `apps/admin-app/src/app/router.tsx` | RequireAuth wraps AppLayout; 8 deferred routes → ComingSoon | ✓ VERIFIED | `<RequireAuth><AppLayout /></RequireAuth>` at line 35; 8 ComingSoon elements |
| `apps/admin-app/src/shared/session/can.ts` | OWNER_ONLY (41 entries) + can(); byte-parity with admin-web | ✓ VERIFIED | 41 unique pairs by regex scan |
| `apps/admin-app/src/shared/session/registry.ts` | Resource/Action unions + routeRegistry | ✓ VERIFIED | All type unions verbatim from admin-web; routeRegistry adapted to admin-app ROUTES |
| `apps/admin-app/src/components/feedback/ComingSoon.tsx` | Hide-for-future placeholder, no action button | ✓ VERIFIED | Clock ScreenIcon, «Раздел в разработке» heading, no action button |
| `apps/backend/tests/integration/test_rbac_parity.py` | Repointed to admin-app; 4 parity assertions green | ✓ VERIFIED | `_CAN_TS`/`_REGISTRY_TS` point to admin-app; 4/4 pytest assertions pass |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `apps/admin-app/package.json` | `@clubcore/api-client` | `workspace:*` dependency | ✓ WIRED | `package.json` dependencies entry confirmed |
| `.github/workflows/ci.yml` | `pnpm -F @clubcore/admin-app` | Dedicated CI job steps | ✓ WIRED | 4 steps in `admin-app:` job |
| `apps/admin-app/src/api/client.ts` | `@clubcore/api-client` | `import { ApiError }` and `type { paths }` | ✓ WIRED | Lines 18-19 of client.ts |
| `apps/admin-app/src/api/query-client.ts` | `apps/admin-app/src/lib/authBus.ts` | `publishSessionExpired` on session_expired | ✓ WIRED | Line 17: `import { publishSessionExpired } from '@/lib/authBus'`; called on `code === 'session_expired'` |
| `apps/admin-app/src/features/auth/api.ts` | `/api/v1/auth/me` | `useSession` queryFn → `staffRequest('get', '/api/v1/auth/me')` → `MeResponseSchema.parse` | ✓ WIRED | Lines 50-52 of api.ts |
| `apps/admin-app/src/features/auth/RequireAuth.tsx` | `ROUTES.login` | Navigate when session errors + authBus subscription | ✓ WIRED | Lines 35-37 (authBus) and 56-58 (Navigate) |
| `apps/admin-app/src/pages/login/components/LoginForm.tsx` | `useLogin` | Mutation on submit with anti-oracle error mapping | ✓ WIRED | Line 17 import; lines 60-91 mutation call |
| `apps/backend/tests/integration/test_rbac_parity.py` | `apps/admin-app/src/shared/session/can.ts` | `_CAN_TS` path constant | ✓ WIRED | Line 30: `_CAN_TS = _REPO_ROOT / "apps" / "admin-app" / ...` |
| `apps/admin-app/src/layouts/AppLayout/AppSidebar.tsx` | `useSession` + `can` | Role badge + nav filtering | ✓ WIRED | Lines 18-19: imports; lines 37, 54: used |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `AppSidebar.tsx` | `session.data` (role, fullName) | `useSession()` → `staffRequest('get', '/api/v1/auth/me')` → `MeResponseSchema.parse` | Yes — live HTTP to backend | ✓ FLOWING |
| `LoginForm.tsx` | mutation result (user) | `useLogin()` → `staffRequest('post', '/api/v1/auth/login')` → `LoginResponseSchema.parse` | Yes — live HTTP to backend | ✓ FLOWING |
| `RequireAuth.tsx` | `isPending`, `isError` | `useSession()` same as above | Yes — driven by live /me response | ✓ FLOWING |
| `ComingSoon.tsx` | (none — static) | No data fetch by design (FND-04) | N/A — intentional static | ✓ VERIFIED (intentional no-data) |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| admin-app typecheck passes | `pnpm -F @clubcore/admin-app typecheck` | Clean exit, no errors | ✓ PASS |
| admin-app lint passes | `pnpm -F @clubcore/admin-app lint` | Clean exit, no errors | ✓ PASS |
| admin-app tests pass (99 tests) | `pnpm -F @clubcore/admin-app test` | 99/99 tests pass | ✓ PASS |
| admin-app build succeeds | `pnpm -F @clubcore/admin-app build` | Built in 2.67s, no errors | ✓ PASS |
| RBAC parity test green | `cd apps/backend && uv run pytest tests/integration/test_rbac_parity.py -x -q` | 4 passed in 0.02s | ✓ PASS |
| OWNER_ONLY has 41 unique pairs | node regex scan on can.ts | 41 | ✓ PASS |

---

### Probe Execution

No `probe-*.sh` scripts declared for this phase. Step 7c: SKIPPED (no probes configured for this phase).

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| FND-01 | 100-01 | admin-app part of clubcore repo, builds/runs/tests, dedicated CI job | ✓ SATISFIED | Package `@clubcore/admin-app` in workspace; 4-step CI job; typecheck/lint/test/build all pass |
| FND-02 | 100-02 | Talks to real backend — staff session cookie, X-CSRF-Token on mutations, 401 → login | ✓ SATISFIED | `staffRequest` with `credentials:'include'`; CSRF from `clubcore_csrf`; single-flight refresh + session_expired |
| FND-03 | 100-03 | Per-domain zod contract layer; mock queryFn removed once domain is live | ✓ SATISFIED | `features/auth/schemas.ts` (6 schemas); auth domain is http-only; README documents mock-removal path |
| FND-04 | 100-04 | Deferred screens hidden/gated as ComingSoon | ✓ SATISFIED | 8 routes render `<ComingSoon/>`; Сообщения/Уведомления/Филиалы removed from nav |
| AUTH-01 | 100-03 | Staff logs in via real `/api/v1/auth`; session persists; CSRF captured | ✓ SATISFIED | `useLogin()` → `POST /api/v1/auth/login`; `useSession()` → `GET /api/v1/auth/me` via cc_* cookies; CSRF from `clubcore_csrf` |
| AUTH-02 | 100-03 | Unauthenticated → /login; logout ends session; (AUTH-02 note: Settings sessions list is Phase 104 SET-01, not Phase 100) | ✓ SATISFIED | `RequireAuth` redirects unauthenticated; `useLogout` removes session query; mid-session 401 → `/login?state=expired` |
| AUTH-03 | 100-04 | UI reflects staff role; owner-only screens/actions hidden for reception; 403 → friendly state | ✓ SATISFIED | Sidebar role pill + nav filter via `can()`; Финансы/Отчёты absent for reception; `ErrorPage` for 403 |

Note on AUTH-02: The REQUIREMENTS.md text mentions "Settings lists active sessions (`/auth/sessions`) and can revoke them" — this is sub-requirement SET-01 (Phase 104), not Phase 100. The Phase 100 scope covers the guard/logout/expiry path only, which is verified.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `apps/admin-app/src/layouts/AppLayout/nav-items.ts` | 50 | `badge: 847` (hardcoded count) | ℹ Info | Static mock badge; intentional until Clients domain wired in Phase 101 |
| `apps/admin-app/src/layouts/AppLayout/nav-items.ts` | 53 | `badge: 12` (hardcoded count) | ℹ Info | Static mock badge; intentional until Trainers domain wired in Phase 102 |

No TBD/FIXME/XXX debt markers found in phase-modified files. No unresolved stubs in auth/transport/RBAC code paths. The two badge values are cosmetic display data for non-auth domains; they are not part of Phase 100's scope and will be resolved in Phases 101–102.

---

### Human Verification Required

### 1. Login Round-Trip with Cookie Persistence

**Test:** Run `docker compose up`, navigate to `http://localhost:5173/` in a browser, log in with valid staff credentials, then perform a hard reload (Ctrl+R / Cmd+R).
**Expected:** After reload, the browser still shows the dashboard (not the login screen). DevTools → Application → Cookies shows `cc_access`, `cc_refresh` (httpOnly, not readable in JS), and `clubcore_csrf` (JS-readable). Network tab shows a GET `/api/v1/auth/me` on reload that returns 200.
**Why human:** Requires a running backend stack; cookie round-trip and actual `Set-Cookie` header behavior cannot be verified by static analysis or unit tests.

### 2. Mid-Session 401 Redirect Without Crash

**Test:** While logged in, manually expire or delete the `cc_access` cookie in DevTools, then navigate to any app route or trigger a data refetch.
**Expected:** The transport posts to `/api/v1/auth/refresh` once; if the refresh token is also expired, the app navigates to `/login?state=expired` and shows the ExpiredScreen. No crash, no stale data visible, no redirect loop. Network tab shows exactly one refresh attempt.
**Why human:** Requires deliberate cookie manipulation in a live browser + real backend to trigger the 401 → refresh → session_expired path end-to-end.

---

### Gaps Summary

No gaps. All 14 must-have truths are VERIFIED with codebase evidence. The two items above require human verification against a running backend stack — they cannot be falsified by static analysis because they depend on actual HTTP round-trips and cookie behavior in a real browser.

---

_Verified: 2026-06-13T12:26:00Z_
_Verifier: Claude (gsd-verifier)_
