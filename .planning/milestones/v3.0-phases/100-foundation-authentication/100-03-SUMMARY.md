---
phase: 100-foundation-authentication
plan: "03"
subsystem: auth
tags: [auth, session, zod, tanstack-query, react-router, login, password-reset]

# Dependency graph
requires:
  - "100-02 (staffRequest, ApiError, authBus, queryClient with session-expiry handler)"
provides:
  - "features/auth/schemas.ts — LoginRequestSchema, LoginResponseSchema, MeResponseSchema, ApiErrorEnvelopeSchema, PasswordResetRequestSchema, PasswordResetConfirmSchema (newPassword field)"
  - "features/auth/api.ts — authKeys, useSession, useLogin, useLogout, usePasswordResetRequest, usePasswordResetConfirm (http mode only, no mock path)"
  - "features/auth/RequireAuth.tsx — useSession() guard for AppLayout branch + authBus expiry redirect"
  - "router.tsx AppLayout branch wrapped in RequireAuth (AUTH-02)"
  - "LoginForm wired to real useLogin mutation with anti-oracle error mapping (T-100-07)"
  - "RecoveryScreens wired to password-reset endpoints; PasswordStrength min updated to 12 chars"
  - "twofa view hidden-for-future: removed from DEEP_LINKABLE and renderScreen()"
  - "README.md FND-03 per-domain mock-removal path documented for Phase 101+"
affects:
  - "101-104 (each domain flip repeats FND-03 seam — schemas.ts + staffRequest queryFn)"
  - "100-04 (AppSidebar session wiring depends on useSession from this plan)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "FND-03 zod contract seam: per-domain schemas.ts mirrors backend wire shapes; parse result in queryFn"
    - "auth domain always http (no VITE_API_MODE branch) — other domains stay mock until their phase"
    - "useLogin invalidates authKeys.me (not setQueryData) to keep MeResponse shape consistent"
    - "RequireAuth owns authBus subscription — fires regardless of current screen"
    - "ApiError re-exported from features/auth/api.ts so pages don't violate import/no-restricted-paths"

key-files:
  created:
    - "apps/admin-app/src/features/auth/schemas.ts — 6 zod schemas, 6 inferred types"
    - "apps/admin-app/src/features/auth/api.ts — 5 hooks + authKeys + ApiError re-export"
    - "apps/admin-app/src/features/auth/schemas.test.ts — 17 pure zod assertions"
    - "apps/admin-app/src/features/auth/RequireAuth.tsx — useSession guard + authBus subscription"
  modified:
    - "apps/admin-app/src/app/router.tsx — AppLayout wrapped in RequireAuth"
    - "apps/admin-app/src/pages/login/LoginPage.tsx — twofa removed"
    - "apps/admin-app/src/pages/login/components/LoginForm.tsx — real useLogin mutation"
    - "apps/admin-app/src/pages/login/components/RecoveryScreens.tsx — password-reset wired"
    - "apps/admin-app/README.md — mock-removal path documentation"

key-decisions:
  - "D-100-03-LOGININVALIDATE: useLogin invalidates authKeys.me (not setQueryData). Login response lacks email/hasTelegram; setting partial data would pollute cache shape. Cost: one extra /me round-trip. Benefit: single source of truth."
  - "D-100-03-APIERROR-REEXPORT: ApiError re-exported from features/auth/api.ts so page-layer consumers don't import @/api/client directly (ESLint import/no-restricted-paths boundary). Clean layering preserved."
  - "D-100-03-REQUIREAUTH-BUS: authBus subscription lives in RequireAuth (always mounted inside router) not LoginPage — fires on any route, not just when LoginPage is rendered."
  - "D-100-03-STRENGTH-MIN: PasswordStrength checker updated to 12+ chars (was 8) to match backend password.min(12) and T-100-10."

requirements-completed: [FND-03, AUTH-01, AUTH-02]

# Metrics
duration: 7min
completed: 2026-06-13
---

# Phase 100 Plan 03: Auth Domain Wiring Summary

**Per-domain zod contract seam (FND-03) on auth/session: useSession()/useLogin()/useLogout()/password-reset hooks, RequireAuth guard with mid-session 401 redirect, anti-oracle error mapping, twofa hidden, and mock-removal path documented**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-06-13T09:04:13Z
- **Completed:** 2026-06-13T09:11:22Z
- **Tasks:** 3
- **Files created/modified:** 9

## Accomplishments

- `features/auth/schemas.ts` — 6 zod schemas exactly matching the verified backend wire shapes:
  `LoginRequestSchema` (password.min(12)), `LoginResponseSchema`, `MeResponseSchema`,
  `ApiErrorEnvelopeSchema` (top-level, not wrapped), `PasswordResetRequestSchema`,
  `PasswordResetConfirmSchema` (uses `newPassword` key, not `password`)
- `features/auth/api.ts` — all auth hooks over `staffRequest` (http-only mode):
  `useSession` (retry:false), `useLogin` (invalidates /me on success), `useLogout`
  (removeQueries on settled), `usePasswordResetRequest`, `usePasswordResetConfirm`
- `features/auth/RequireAuth.tsx` — wraps AppLayout branch; pending → skeleton (no flash);
  error → Navigate to /login; subscribes to authBus → clears session cache + navigates
  to /login?state=expired on mid-session 401 (T-100-09)
- `router.tsx` — `<RequireAuth><AppLayout/></RequireAuth>` (AUTH-02); login/error routes outside guard
- `LoginPage.tsx` — twofa removed from DEEP_LINKABLE + renderScreen(); file kept un-imported
- `LoginForm.tsx` — real `useLogin()` mutation, anti-oracle banner (T-100-07), 422 inline errors,
  5xx toast, pending state, remember-me Callout no-op, Google no-op toast
- `RecoveryScreens.tsx` — ForgotScreen calls `usePasswordResetRequest`, ResetScreen calls
  `usePasswordResetConfirm({token, newPassword})`; T-100-10 weak_password → field error
- `README.md` — "Mock queryFn removal path" section for Phase 101+ domains

## Task Commits

1. **Task 1: Auth zod contract layer + session/login/logout/password-reset hooks** — `f952308e` (feat)
2. **Task 2: RequireAuth route guard + remove twofa + wire 401-expiry redirect** — `c3f9a979` (feat)
3. **Task 3: Wire LoginForm + RecoveryScreens; document mock-removal path** — `e1a3175d` (feat)

## Files Created/Modified

- `apps/admin-app/src/features/auth/schemas.ts` — 6 zod schemas, 6 inferred types; newPassword field
- `apps/admin-app/src/features/auth/api.ts` — 5 hooks + authKeys + ApiError/LoginRequestSchema re-export
- `apps/admin-app/src/features/auth/schemas.test.ts` — 17 pure zod assertions (all green)
- `apps/admin-app/src/features/auth/RequireAuth.tsx` — useSession guard + authBus expiry subscription
- `apps/admin-app/src/app/router.tsx` — AppLayout wrapped in RequireAuth
- `apps/admin-app/src/pages/login/LoginPage.tsx` — twofa removed
- `apps/admin-app/src/pages/login/components/LoginForm.tsx` — useLogin wired, anti-oracle, callout
- `apps/admin-app/src/pages/login/components/RecoveryScreens.tsx` — password-reset endpoints wired
- `apps/admin-app/README.md` — mock-removal path documentation

## Decisions Made

- **D-100-03-LOGININVALIDATE**: `useLogin` invalidates `authKeys.me` rather than `setQueryData`. The login
  response `{id, role, fullName}` lacks `email` and `hasTelegram` that `MeResponse` includes — setting
  partial data would cause type inconsistency. Invalidating triggers a fresh `/me` fetch.
- **D-100-03-APIERROR-REEXPORT**: `ApiError` re-exported from `features/auth/api.ts` so LoginForm.tsx and
  RecoveryScreens.tsx can do `instanceof ApiError` checks without importing `@/api/client` directly
  (which would violate the ESLint `import/no-restricted-paths` boundary for page-layer files).
- **D-100-03-REQUIREAUTH-BUS**: The authBus `subscribeSessionExpired` subscription is placed in
  `RequireAuth` (always mounted) rather than `LoginPage` (only mounted on the login route). This
  ensures the mid-session 401 redirect fires regardless of the current screen.
- **D-100-03-STRENGTH-MIN**: `PasswordStrength` checklist updated to 12+ chars (was 8) to match
  backend `password.min(12)` and the T-100-10 client-side enforcement.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added ApiError re-export to features/auth/api.ts**
- **Found during:** Task 3 (lint run after LoginForm.tsx wiring)
- **Issue:** LoginForm.tsx and RecoveryScreens.tsx imported `ApiError` from `@/api/client` directly.
  The `import/no-restricted-paths` ESLint rule blocks pages from importing `@/api/client` — only
  `features/**/api.ts` files are allowed to cross that boundary.
- **Fix:** Added `export { ApiError }` to `features/auth/api.ts`; page imports updated to use
  `@/features/auth/api` for both `ApiError` and `LoginRequestSchema`.
- **Files modified:** `apps/admin-app/src/features/auth/api.ts`, `LoginForm.tsx`, `RecoveryScreens.tsx`
- **Verification:** `pnpm -F @clubcore/admin-app lint` passes cleanly after fix.
- **Committed in:** `e1a3175d` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (Rule 2 — Missing Critical / import boundary)
**Impact on plan:** Correct layering enforced by existing ESLint rules; fix is architecturally required.

## Known Stubs

None — all wired paths call real endpoints. The only intentional no-ops:
- Remember-me checkbox: visual only, documented no-op callout (backend TTLs are fixed)
- Google Workspace button: no-op toast (OAuth not yet wired — per plan)
- ResetScreen token extraction: reads from `window.location.search` — works for email-link deep-links

## Threat Surface Scan

All mitigations from the plan's threat model are confirmed implemented:

| Threat ID | Mitigation | File | Status |
|-----------|------------|------|--------|
| T-100-07 | Anti-oracle: single generic banner for invalid_credentials; no field aria-invalid | LoginForm.tsx | implemented |
| T-100-08 | RequireAuth: app routes render only after /auth/me succeeds | RequireAuth.tsx | implemented |
| T-100-09 | session_expired: removeQueries(authKeys.me) before navigate | RequireAuth.tsx | implemented |
| T-100-10 | newPassword.min(12) client-side; weak_password 422 → field error | RecoveryScreens.tsx | implemented |

No new security-relevant surface introduced beyond what the plan's threat model covers.

## Self-Check: PASSED

Files verified present:
- `apps/admin-app/src/features/auth/schemas.ts` — FOUND
- `apps/admin-app/src/features/auth/api.ts` — FOUND
- `apps/admin-app/src/features/auth/schemas.test.ts` — FOUND
- `apps/admin-app/src/features/auth/RequireAuth.tsx` — FOUND
- `apps/admin-app/src/app/router.tsx` — FOUND (RequireAuth wired)
- `apps/admin-app/src/pages/login/LoginPage.tsx` — FOUND (twofa removed)
- `apps/admin-app/src/pages/login/components/LoginForm.tsx` — FOUND (useLogin wired)
- `apps/admin-app/src/pages/login/components/RecoveryScreens.tsx` — FOUND (endpoints wired)
- `apps/admin-app/README.md` — FOUND (mock-removal path documented)

Commits verified:
- `f952308e` — Task 1 (zod schemas + hooks)
- `c3f9a979` — Task 2 (RequireAuth + twofa removal)
- `e1a3175d` — Task 3 (LoginForm + RecoveryScreens + README)

Tests: 92/92 passing. Typecheck: clean. Lint: clean.

## Next Phase Readiness

- `useSession()` is available for AppSidebar session wiring (plan 100-04)
- `authKeys.me` is the canonical session query key — AppSidebar and any future domain can read it
- The FND-03 zod seam pattern is documented and ready for Phase 101–104 domain flips
- No blockers. All AUTH-01, AUTH-02, FND-03 requirements delivered.
