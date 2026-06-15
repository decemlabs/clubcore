---
phase: 109-profile-security-backend-wiring
plan: 03
subsystem: auth
tags: [zod, tanstack-query, react, typescript, auth, profile, password]

# Dependency graph
requires:
  - phase: 109-01
    provides: PATCH /api/v1/auth/me + POST /api/v1/auth/change-password backend endpoints
  - phase: 109-02
    provides: backend change-password implementation + revoke-other-sessions logic
provides:
  - ProfileUpdateSchema zod contract (fullName, email validation with Russian messages)
  - ChangePasswordSchema zod contract (currentPassword, newPassword with 12-char NIST floor)
  - useUpdateProfile() TanStack mutation hook (PATCH /me → invalidates authKeys.me)
  - useChangePassword() TanStack mutation hook (POST /change-password → invalidates sessions)
affects:
  - 109-04-profile-security-ui-wiring
  - 111-openapi-handoff-milestone-gate

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "as-never path cast for additive endpoints not yet in schema.d.ts (D-V31-CONTRACT-ADDITIVE)"
    - "Inline sessions key literal in features/auth to avoid cross-feature import"
    - "TDD RED→GREEN for both schema additions and hook exports"
    - "ApiError propagated to callers — no toast in hooks (component owns error UX)"

key-files:
  created:
    - apps/admin-app/src/features/auth/api.test.ts
  modified:
    - apps/admin-app/src/features/auth/schemas.ts
    - apps/admin-app/src/features/auth/schemas.test.ts
    - apps/admin-app/src/features/auth/api.ts

key-decisions:
  - "D-109-03-SESSIONS-KEY-INLINE: sessions key ['auth','sessions'] inlined in features/auth/api.ts as a literal — avoids cross-feature import (features/auth → features/settings), mirrors settingsKeys.sessions"
  - "D-109-03-NO-CONFIRM-ON-WIRE: neither ProfileUpdateSchema nor ChangePasswordSchema has a confirmPassword field — confirm check is UI-only (Plan 04)"
  - "D-109-03-NO-TOAST-IN-HOOKS: useUpdateProfile/useChangePassword propagate ApiError to callers without swallowing into toasts — component decides inline field error vs toast"

patterns-established:
  - "ProfileUpdateSchema pattern: zod object with fullName(min 2) + email(format), reuses existing Russian message strings"
  - "ChangePasswordSchema pattern: currentPassword(min 1 Russian) + newPassword(min 12 Russian — reused from PasswordResetConfirmSchema)"
  - "Mutation hook pattern for additive paths: method + path cast as never with inline comment citing D-V31-CONTRACT-ADDITIVE + Phase 111"

requirements-completed: [PROF-01, PROF-02]

# Metrics
duration: 4min
completed: 2026-06-14
---

# Phase 109 Plan 03: Frontend Contract Layer — Zod Schemas + Mutation Hooks Summary

**ProfileUpdateSchema + ChangePasswordSchema zod contracts with Russian validation messages, plus useUpdateProfile/useChangePassword TanStack mutations wired via staffRequest `as never` casts against the additive PATCH /auth/me + POST /auth/change-password endpoints**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-06-14T18:57:21Z
- **Completed:** 2026-06-14T19:00:35Z
- **Tasks:** 2 (each TDD: RED commit + GREEN commit)
- **Files modified:** 4

## Accomplishments
- Appended `ProfileUpdateSchema` and `ChangePasswordSchema` to `features/auth/schemas.ts` with reused Russian error messages and no wire-level confirm field
- Added `useUpdateProfile()` hook: PATCH /api/v1/auth/me with `as never` cast, parses MeResponseSchema, invalidates `authKeys.me` on success
- Added `useChangePassword()` hook: POST /api/v1/auth/change-password with `as never` cast, invalidates `['auth','sessions']` on 204 success
- Both hooks propagate ApiError (including `.fields.email` for 409 duplicate email) to callers without swallowing into toasts
- Created `api.test.ts` for the new hook exports; extended `schemas.test.ts` with 8 new schema tests
- All 27 auth tests pass; typecheck + lint clean

## Task Commits

1. **Task 1 RED: failing schema tests** - `f1770ca5` (test)
2. **Task 1 GREEN: ProfileUpdateSchema + ChangePasswordSchema** - `e51b23da` (feat)
3. **Task 2 RED: failing hook export tests** - `d1410aed` (test)
4. **Task 2 GREEN: useUpdateProfile + useChangePassword** - `9c5ffe49` (feat)

## Files Created/Modified
- `apps/admin-app/src/features/auth/schemas.ts` — Added ProfileUpdateSchema + ChangePasswordSchema with inferred types
- `apps/admin-app/src/features/auth/schemas.test.ts` — Added 8 new tests for the two new schemas
- `apps/admin-app/src/features/auth/api.ts` — Added useUpdateProfile + useChangePassword hooks; re-exported ProfileUpdate + ChangePassword types
- `apps/admin-app/src/features/auth/api.test.ts` — New file: export-contract tests for the two hooks

## Decisions Made

- **D-109-03-SESSIONS-KEY-INLINE:** The sessions query key `['auth','sessions']` is inlined as a literal in `features/auth/api.ts` rather than importing `settingsKeys` from `features/settings/api.ts`. This avoids an unusual cross-feature import direction. The key is a trivial 2-element array with no logic attached; inlining with a comment citing `settingsKeys.sessions` is sufficient.
- **D-109-03-NO-CONFIRM-ON-WIRE:** No `confirmPassword` field on either schema. The backend `POST /auth/change-password` body has no confirm field — confirm/mismatch validation is purely a UI concern handled in Plan 04.
- **D-109-03-NO-TOAST-IN-HOOKS:** Hooks do not call `toast()` — callers (Plan 04 UI components) decide whether a 422/409 surfaces as an inline field error or a generic toast. This keeps the hook reusable.

## Deviations from Plan

None — plan executed exactly as written. ESLint boundary check confirmed: no `import/no-restricted-paths` rule restricts `features/auth → features/settings`; however, the inline literal approach was chosen as the cleaner option regardless.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 04 (UI wiring) can import `useUpdateProfile` + `useChangePassword` from `features/auth/api.ts` directly
- `ProfileUpdate` and `ChangePassword` types are re-exported for Plan 04 form type safety
- `authKeys` is already exported; Plan 04 can call `qc.invalidateQueries({ queryKey: authKeys.me })` if needed
- No blockers

## Threat Surface Scan

No new network endpoints or auth paths introduced in this plan (FE contract layer only).
CSRF: both hooks use `staffRequest` which auto-attaches `X-CSRF-Token` from `clubcore_csrf` on PATCH/POST (T-109-14 satisfied).
Password fields: mutation variables only — never written to the query cache (T-109-15 satisfied).

## Self-Check

Files exist:
- `apps/admin-app/src/features/auth/schemas.ts` — modified ✓
- `apps/admin-app/src/features/auth/api.ts` — modified ✓
- `apps/admin-app/src/features/auth/api.test.ts` — created ✓

Commits exist: f1770ca5, e51b23da, d1410aed, 9c5ffe49

---
*Phase: 109-profile-security-backend-wiring*
*Completed: 2026-06-14*
