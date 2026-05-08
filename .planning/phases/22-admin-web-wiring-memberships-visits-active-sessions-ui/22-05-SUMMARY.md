---
phase: 22-admin-web-wiring-memberships-visits-active-sessions-ui
plan: 05
subsystem: ui
tags: [react, tanstack-router, tanstack-query, fe-09, hyg-03, active-sessions, auth, profile-route]

# Dependency graph
requires:
  - phase: 22-02
    provides: Card / Badge / Skeleton / Alert primitives, t() helper for sessions keys
  - phase: 23
    provides: GET /api/v1/auth/sessions + POST /api/v1/auth/sessions/{family_id}/revoke endpoints in packages/api-client/src/schema.d.ts (CD-05 unconditional contract assertions)

provides:
  - Auth contract extended with SessionFamily, sessions(), revokeSession(familyId), logoutAll()
  - http auth impl wired to /auth/sessions GET + /auth/sessions/{family_id}/revoke POST + /auth/logout-all POST
  - mock auth impl throws DomainError('mock_not_implemented') for sessions/revokeSession (D-22-2)
  - useActiveSessions / useRevokeSession / useLogoutAll TanStack Query hooks with authKeys.sessions
  - SessionsList component (Card-rendered list with channel badge, current badge, revoke button, footer logout-all CTA)
  - LogoutAllDialog (shadcn AlertDialog destructive confirm; sonner toast → navigate /login)
  - NEW /_protected/profile route accessible to BOTH roles (Warning 2 fix)
  - 'profile' resource added to can.ts; OWNER_ONLY does NOT include any pair with 'profile'
  - ProfileMenu (user-menu dropdown) gains a 'Профиль' link before 'Выйти'
  - Russian dictionary additions: profile.* + sessions.* (heading, revoke, current, logoutAll, logoutAllConfirm.*, empty, error, channel.*, toast.*, errors.mockNotImplemented)

affects:
  - apps/admin-web/src/shared/session/registry.ts: Resource type +'profile'
  - apps/admin-web/src/shared/i18n/ru.ts: +profile, +sessions namespaces
  - apps/admin-web/src/shared/ui/app-shell/ProfileMenu.tsx: dropdown gains /profile link
  - phase-22-closure: FE-09 ships → Phase 22 ready for /gsd-verify-phase 22 (all FE-04..FE-11 closed)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "AuthService extension consuming a paginated wire envelope: ResponseEnvelope[PaginatedData[ActiveSessionItem]] → unwrap().items"
    - "Mock-not-implemented surface via DomainError('mock_not_implemented') for http-only features (D-22-2)"
    - "Both-roles route gated by Resource type membership (NOT OWNER_ONLY membership)"
    - "ProfileMenu dropdown link uses useNavigate via onSelect e.preventDefault to keep menu close behavior consistent"
    - "Test toast/navigate vi.hoisted mock pattern (matches ProfileMenu.test.tsx precedent)"

key-files:
  created:
    - apps/admin-web/src/features/auth/api/sessionsHooks.ts
    - apps/admin-web/src/features/auth/api/sessionsHooks.test.ts
    - apps/admin-web/src/features/auth/components/SessionsList.tsx
    - apps/admin-web/src/features/auth/components/SessionsList.test.tsx
    - apps/admin-web/src/features/auth/components/LogoutAllDialog.tsx
    - apps/admin-web/src/features/auth/components/LogoutAllDialog.test.tsx
    - apps/admin-web/src/routes/_protected/profile.tsx
    - apps/admin-web/src/routes/_protected/profile.test.tsx
  modified:
    - apps/admin-web/src/features/auth/api/keys.ts
    - apps/admin-web/src/features/auth/index.ts
    - apps/admin-web/src/shared/api/contracts/auth.ts
    - apps/admin-web/src/shared/api/services/http/auth.ts
    - apps/admin-web/src/shared/api/services/mock/auth.ts
    - apps/admin-web/src/shared/i18n/ru.ts
    - apps/admin-web/src/shared/session/can.test.ts
    - apps/admin-web/src/shared/session/registry.ts
    - apps/admin-web/src/shared/ui/app-shell/ProfileMenu.tsx

key-decisions:
  - "/profile is a NEW route, NOT a modification to /settings. settings.tsx remained owner-only and untouched. The 'profile' Resource is added but is intentionally NOT in OWNER_ONLY, so both roles pass `can(_, 'view', 'profile')`. (Warning 2 resolution per plan §rationale.)"
  - "Profile link surfaces via existing ProfileMenu dropdown — NO sidebar entry. Profile is account-management surface (own sessions), not navigation."
  - "Mock auth.logoutAll is a no-op (parity with logout); only sessions/revokeSession throw mock_not_implemented because their value is the real refresh-rotation invariant, not a stub list."
  - "SessionFamily wire shape pulled directly from backend ActiveSessionItem (camelCase via alias_generator) — no FE-side adapter needed, contract types match 1:1."
  - "useLogoutAll lives in sessionsHooks.ts (NEW) rather than extending the existing hooks.ts barrel — the FE-09 cluster (active sessions + logout-all) is a coherent unit and keeps hooks.ts pristine for the original v1.1 auth flows (login/me/logout/telegram/*)."

patterns-established:
  - "Reusable test pattern: vi.hoisted({...mocks}) + vi.mock('@tanstack/react-router', { useNavigate: () => navigateMock }) + vi.mock('sonner', { toast: { success, error } }) — applied to LogoutAllDialog, SessionsList, ProfileMenu (precedent)"
  - "Both-roles 'profile' surface as the canonical pattern for own-account screens (vs. /settings which is admin/system surface)"

requirements-completed: [FE-09]

# Metrics
duration: ~25min
completed: 2026-05-08
---

# Phase 22 Plan 05: FE-09 Active Sessions UI Summary

**FE-09 active-sessions UI consuming Phase 23 HYG-03 endpoints on a NEW /_protected/profile route accessible to both roles**

## Performance

- **Duration:** ~25 min (Tasks 1 + 2 + 3)
- **Started:** 2026-05-08T17:05:00Z
- **Completed:** 2026-05-08
- **Tasks:** 3/3 completed
- **Files created/modified:** 17 (8 created + 9 modified)

## Phase 23 Dependency Verification (Task 1)

- **Phase 23 main merge:** confirmed at base commit `d31c657` (worktree base) — HYG-03 paths landed in `packages/api-client/src/schema.d.ts` via Phase 23 commit `d703c84` (CD-05 drift gate refresh).
- **`grep -E "/api/v1/auth/sessions" packages/api-client/src/schema.d.ts | grep -v logout-all`** → 2 matches (`/auth/sessions` GET + `/auth/sessions/{family_id}/revoke` POST). ✅
- **schema.contract.test.ts uplift:** ALREADY DONE in Phase 23 (CD-05). The file already contains unconditional assertions:
  - `type _GetSessions = AssertNonNever<paths['/api/v1/auth/sessions']['get']>`
  - `type _PostRevokeSession = AssertNonNever<paths['/api/v1/auth/sessions/{family_id}/revoke']['post']>`
  - Both bound to runtime checks `_sessionsGetCheck`/`_sessionsRevokeCheck` and asserted in the lone `it()` block.
- **`pnpm --filter @sportzal/api-client test`** → 9 tests pass (schema.contract.test.ts:1 + fetcher.test.ts:8). ✅
- **`pnpm --filter @sportzal/api-client tsc --noEmit`** → exit 0. ✅
- Task 1 had no new code to commit — the dependency verification gate is fully satisfied by Phase 23's prior work.

## Components and SchemaName

- **Schema name (used in http impl):** `components['schemas']['ActiveSessionItem']` (singular item) wrapped via `components['schemas']['PaginatedData_ActiveSessionItem_']` and finally `components['schemas']['ResponseEnvelope_PaginatedData_ActiveSessionItem__']`. Wire fields: `familyId`, `createdAt`, `lastUsedAt`, `userAgent`, `channel`, `isCurrent`. The FE `SessionFamily` interface (in `shared/api/contracts/auth.ts`) is a 1:1 mirror — no adapter needed.

## Accomplishments

- **Task 1 (Phase 23 dep verification + contract test uplift):** verified schema.d.ts contains both HYG-03 paths; confirmed schema.contract.test.ts already asserts them unconditionally per Phase 23 CD-05; recorded `ActiveSessionItem` as the canonical wire schema name. No code commit needed.
- **Task 2 (auth contract + http service + mock + hooks + ru.ts + can.ts profile):** committed as `045adc8`.
  - `AuthService` extended with `sessions()`, `revokeSession(familyId)`, `logoutAll()` methods + `SessionFamily` + `SessionChannel` types.
  - `http/auth.ts`: `sessions()` calls `request('get', '/api/v1/auth/sessions')`, unwraps `PaginatedSessionsResponse`, returns `.items[]`. `revokeSession(familyId)` calls `request('post', '/api/v1/auth/sessions/{family_id}/revoke', { params: { family_id: familyId } })`. `logoutAll()` calls `/auth/logout-all`.
  - `mock/auth.ts`: `sessions()` and `revokeSession()` throw `DomainError('mock_not_implemented', …)`. `logoutAll()` is a no-op for parity with `logout()`.
  - `authKeys.sessions = ['auth', 'sessions']`.
  - `sessionsHooks.ts`: `useActiveSessions` (staleTime 30s), `useRevokeSession` (invalidate on settle), `useLogoutAll` (qc.clear on success).
  - `can.ts` / `registry.ts`: `'profile'` Resource added; OWNER_ONLY does NOT include profile (verified by new test).
  - `ru.ts`: `profile.{heading, menuLink}` + `sessions.{heading, revoke, current, logoutAll, logoutAllConfirm.{title, body, action, cancel}, empty, error, channel.{email, telegram, unknown}, toast.{revoked, loggedOutAll}, errors.mockNotImplemented}`.
  - 9 tests added (3 sessionsHooks + 2 new can tests for profile + 4 baseline can tests still passing).
- **Task 3 (SessionsList + LogoutAllDialog + /profile route + ProfileMenu link):** committed as `53029bf`.
  - `SessionsList`: skeleton (3 rows) → error → empty → data state machine. Each row: ChannelBadge + formatDate(createdAt) + optional userAgent + optional 'Текущая' badge + 'Отозвать' ghost button (disabled while pending). Footer: destructive 'Выйти со всех устройств' button opening `LogoutAllDialog`.
  - `LogoutAllDialog`: shadcn `AlertDialog` with destructive confirm. `useLogoutAll().mutate` → `toast.success(…)` → `onClose()` → `navigate({to: '/login', replace: true})`.
  - `/_protected/profile` route: `beforeLoad` mirrors `settings.tsx` but uses `'profile'` resource. Renders `<Card>` with `CardTitle "Активные сессии"` containing `<SessionsList />`.
  - `ProfileMenu` (user-menu dropdown): adds 'Профиль' link (lucide `User` icon) above the existing 'Выйти' item, navigating to `/profile` via `useNavigate`.
  - 11 new tests + existing tests all pass: SessionsList (5 — loading/empty/data/revoke/logout-all-open) + LogoutAllDialog (3 — render/confirm/cancel) + profile route gate (3 — owner-allowed, reception-allowed, reception-blocked-from-/settings sanity).

## Task Commits

1. **Task 1: Phase 23 dependency verification + contract test uplift** — no commit (verification only; contract test was already at the unconditional assertion form via Phase 23 CD-05 commit `d703c84`)
2. **Task 2: Auth contract + http service + mock + hooks + ru.ts + can.ts profile resource** — `045adc8` (feat)
3. **Task 3: SessionsList + LogoutAllDialog + /profile route + ProfileMenu link** — `53029bf` (feat)

**Plan metadata:** See final docs commit (docs(22-05): complete plan)

## Architecture confirmation

- **Sessions paths in schema.d.ts:** `grep -c "/api/v1/auth/sessions" packages/api-client/src/schema.d.ts` (excluding logout-all) → 2 ✅
- **Contract test unconditional sessions assertions:** `grep -q "paths\['/api/v1/auth/sessions'\]\['get'\]" packages/api-client/src/schema.contract.test.ts` → 0 ✅; same for `/sessions/{family_id}/revoke` POST.
- **Mock not implemented:** `grep -q "mock_not_implemented" apps/admin-web/src/shared/api/services/mock/auth.ts` → 0 ✅
- **'profile' Resource:** `grep -q "'profile'" apps/admin-web/src/shared/session/registry.ts` → 0 ✅
- **'profile' NOT in OWNER_ONLY:** verified by `OWNER_ONLY does NOT include any pair with profile` test ✅
- **Both roles can view profile:** `can('owner', 'view', 'profile') === true && can('reception', 'view', 'profile') === true` ✅
- **/settings still owner-only:** verified untouched + reception still blocked (`can('reception', 'view', 'settings') === false`) ✅
- **Sessions hooks staleTime:** `grep -q "staleTime: 30_000" apps/admin-web/src/features/auth/api/sessionsHooks.ts` → 0 ✅
- **ProfileMenu /profile link:** `grep -q "/profile" apps/admin-web/src/shared/ui/app-shell/ProfileMenu.tsx` → 0 ✅
- **routeTree.gen.ts includes /profile:** `grep -q "/profile" apps/admin-web/src/routeTree.gen.ts` → 0 (regenerated via `vite build`) ✅
- **All 184 admin-web tests pass:** `pnpm test -- --run` → exit 0 ✅
- **Typecheck:** `pnpm tsc --noEmit` → exit 0 ✅
- **Lint:** `pnpm lint` → 0 errors (only 2 pre-existing warnings in unrelated files) ✅

## Decisions Made

- /profile is a NEW route accessible to BOTH roles (Warning 2 fix). /settings stays owner-only and untouched.
- 'profile' Resource added to can.ts; OWNER_ONLY does NOT include it. Reception passes `can(role, 'view', 'profile')`.
- Profile surface via existing ProfileMenu dropdown — no sidebar entry. Profile is account-management surface, not navigation.
- Mock auth.logoutAll is a no-op (parity with logout); sessions/revokeSession throw mock_not_implemented (D-22-2).
- SessionFamily wire shape pulled 1:1 from backend ActiveSessionItem (camelCase). No adapter needed.
- useLogoutAll lives in sessionsHooks.ts to keep the existing hooks.ts pristine for v1.1 auth flows.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Lint Bug] Renamed `_familyId` to `familyId` in mock auth.revokeSession**
- **Found during:** Task 2 lint gate
- **Issue:** `@typescript-eslint/no-unused-vars` errors on `_familyId` (the project ESLint flat config does NOT recognize `_`-prefix as unused-allowed for this rule).
- **Fix:** Renamed to `familyId` and added `void familyId` to satisfy noUnusedParameters strict mode while keeping the throw-only mock body.
- **Files modified:** `apps/admin-web/src/shared/api/services/mock/auth.ts`
- **Committed in:** `045adc8` (part of Task 2 commit)

**Total deviations:** 1 auto-fixed (Rule 1 — lint bug). No scope creep, no architectural changes.

### Phase 23 Pre-existing Work

The plan's Task 1 step C (schema.contract.test.ts uplift) was already completed by Phase 23 (CD-05 drift gate refresh, commit `d703c84` on the worktree base). The unconditional `_GetSessions` and `_PostRevokeSession` assertions are present and asserted in the runtime `it()` block. Task 1 had no code change to commit; the dependency was verified and proceeded directly to Task 2. This is not a deviation per se — it is a redundant-by-virtue-of-prior-completion work item that the plan correctly identified as an OR ("uplift the conditional → unconditional"); Phase 23 did the uplift first.

## Auth Gates

None — all hooks/components were exercised via vitest with mocked `services.auth.*` and `useNavigate`. No real auth required for this plan's automated verification. The plan's "Manual http-mode smoke" (boot backend + admin-web with `VITE_API_MODE=http`) is documented for the user to perform during phase verification but is not blocking for this executor.

## Known Stubs

None — `SessionsList`, `LogoutAllDialog`, and the `/profile` route all wire to real services via the swap seam. In `VITE_API_MODE=mock`, `SessionsList` displays the friendly demo-mode hint (`sessions.errors.mockNotImplemented`) sourced from the surfaced `DomainError('mock_not_implemented')`. The plan's D-22-2 explicitly designates http-only as the production path for FE-09 — this is a documented mock gap, not a stub.

## Threat Flags

None beyond the plan's documented `<threat_model>`:
- T-22-17 (revoke another user's session): backend Phase 23 enforces caller-owns-family; FE only triggers.
- T-22-18 (UA / channel exposure in UI): own-account audit only — accept per plan.
- T-22-19 (family_id URL parameter tampering): backend validates UUID + ownership; FE passes through.
- T-22-20 (logout-all DoS): backend rate-limits; UI requires AlertDialog confirm (LogoutAllDialog).

No new security-relevant surface introduced. The /profile route reads its session-family list from an authenticated GET; revoke is CSRF-protected by the existing fetcher.

## Self-Check: PASSED

- `apps/admin-web/src/features/auth/api/sessionsHooks.ts` — FOUND
- `apps/admin-web/src/features/auth/components/SessionsList.tsx` — FOUND (120 lines, ≥50)
- `apps/admin-web/src/features/auth/components/LogoutAllDialog.tsx` — FOUND (74 lines, ≥20)
- `apps/admin-web/src/routes/_protected/profile.tsx` — FOUND (46 lines, ≥20)
- `apps/admin-web/src/routes/_protected/profile.test.tsx` — FOUND
- Commits `045adc8`, `53029bf` — FOUND in `git log --oneline -3`
- routeTree.gen.ts contains `/profile` — verified
- All 184 admin-web tests pass — verified
- `pnpm tsc --noEmit` — exit 0
- `pnpm lint` — 0 errors

## Issues Encountered

- pnpm install was missing in worktree at start (`vitest: command not found`). Resolved by running `pnpm install` (lockfile up-to-date, completed in 2.3s). Standard worktree initialization, not a deviation.
- One eslint error on `_familyId` parameter (auto-fixed per Rule 1 above). 

## Next Phase Readiness

- FE-09 ships → all 8 FE-04..FE-11 requirements addressed across plans 22-01..22-05.
- Phase 22 verification gates can now run: `/gsd-verify-phase 22`.
- /settings remains owner-only and untouched; /profile is the both-roles surface.
- Manual http-mode smoke (boot backend with Phase 23 endpoints + admin-web with VITE_API_MODE=http; login as both roles; verify list/revoke/logout-all) is the user's pre-verification step per plan §verification.

---
*Phase: 22-admin-web-wiring-memberships-visits-active-sessions-ui*
*Completed: 2026-05-08*
