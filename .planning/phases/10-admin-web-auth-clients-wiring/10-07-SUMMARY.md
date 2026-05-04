---
phase: 10-admin-web-auth-clients-wiring
plan: "07"
subsystem: ui
tags: [admin-web, polish, eslint, i18n, env, splash, logout, role-switcher, tdd]

# Dependency graph
requires:
  - phase: 10-admin-web-auth-clients-wiring-01
    provides: ReUI primitives, shared-ui foundation
  - phase: 10-admin-web-auth-clients-wiring-02
    provides: authKeys factory (authKeys.me used in splash gate)
  - phase: 10-admin-web-auth-clients-wiring-03
    provides: services swap seam (API_MODE, services.auth.logout)
  - phase: 10-admin-web-auth-clients-wiring-04
    provides: useCurrentRole hook (used in ProfileMenu)

provides:
  - Splash component (semantic tokens, Loader2 spinner, http-mode boot gate in main.tsx)
  - ProfileMenu active logout (useMutation → services.auth.logout → queryClient.clear → navigate /login)
  - ProfileMenu.test.tsx: 2 tests verifying D-08/FE-06 logout flow with userEvent
  - RoleSwitcher: API_MODE !== 'mock' early return guard (D-12) + authKeys.me invalidation on role change
  - ESLint FE-07: no-restricted-syntax block banning raw fetch() outside src/shared/api/services/http/**
  - raw-fetch-leak.ts negative-test fixture + EXPECTED array 4th entry
  - eslint.fixtures.config.js updated with fetch ban rule
  - ru.ts: top-level auth block (login, telegram, errors, splash) + clients block (all UI-SPEC Copywriting Contract entries)
  - .env.example documenting VITE_API_MODE=mock (+ http option) and VITE_API_BASE_URL

affects:
  - Phase 10 ROADMAP success criteria verified: SC#4 (logout+cache clear), SC#5 (ESLint fetch ban + fixture)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Splash gate: http-mode renders Splash before ensureQueryData(authKeys.me), catch swallows 401, then real tree mounts"
    - "ProfileMenu logout: useMutation with onError also clears cache + navigates (T-10-31 mitigation)"
    - "RoleSwitcher: hooks called unconditionally before API_MODE early return (react-hooks/rules-of-hooks)"
    - "ESLint flat config: each no-restricted-syntax rule in its own file-targeted block — stacks additively, does not replace"
    - "Fixtures ESLint config mirrors main config rules to prove guard-rails fire on fixture files"
    - "ProfileMenu test uses userEvent.setup() (not fireEvent) to open Radix DropdownMenu"
    - "vi.hoisted() for mock factories in vi.mock() — same pattern established in Plan 06"

key-files:
  created:
    - apps/admin-web/src/shared/ui/splash.tsx
    - apps/admin-web/src/shared/ui/app-shell/ProfileMenu.test.tsx
    - apps/admin-web/src/__fixtures/raw-fetch-leak.ts
  modified:
    - apps/admin-web/src/app/main.tsx
    - apps/admin-web/src/shared/ui/app-shell/ProfileMenu.tsx
    - apps/admin-web/src/shared/ui/app-shell/RoleSwitcher.tsx
    - apps/admin-web/eslint.config.js
    - apps/admin-web/scripts/eslint.fixtures.config.js
    - apps/admin-web/scripts/assert-eslint-fixtures.mjs
    - apps/admin-web/src/shared/i18n/ru.ts
    - apps/admin-web/.env.example

key-decisions:
  - "userEvent.setup() required for Radix DropdownMenu in tests — fireEvent.click does not trigger Radix pointer-event handlers"
  - "vi.hoisted() required for mock factories in vi.mock() — same Pattern established in Plan 06"
  - "RoleSwitcher hooks moved before API_MODE early return to comply with react-hooks/rules-of-hooks"
  - ".env.development is gitignored via .env.* pattern — updated locally only; .env.example is the committed doc"
  - "ESLint fixtures.config.js duplicates the fetch ban rule alongside the main eslint.config.js so the fixture script picks it up"

patterns-established:
  - "Splash gate: render Splash → ensureQueryData with retry:false → catch swallows → render real tree"
  - "ESLint fetch ban: separate file-targeted block for each no-restricted-syntax selector preserves all rules"
  - "Test mocking chain: vi.hoisted for all mocks used in vi.mock() factory bodies (established by Plan 06)"

requirements-completed: [FE-03, FE-05, FE-06, FE-07]

# Metrics
duration: 6min
completed: "2026-05-04"
---

# Phase 10 Plan 07: Polish — Splash Gate, Active Logout, ESLint Fetch Ban, ru.ts Expansion Summary

**http-mode splash gate before /auth/me, active ProfileMenu logout with cache-clear, RoleSwitcher hidden in http-mode, ESLint raw-fetch() ban with negative-test fixture, and full ru.ts auth+clients i18n dictionary**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-04T13:53:28Z
- **Completed:** 2026-05-04T14:00:00Z
- **Tasks:** 3 (all TDD)
- **Files modified:** 11 (3 created, 8 modified)

## Accomplishments

- `Splash` component ships with `Loader2` spinner and semantic-only tokens; `main.tsx` http-mode gate renders it before `ensureQueryData(authKeys.me)` and catches any 401 (D-06, FE-05)
- `ProfileMenu` logout is now active: `useMutation` → `services.auth.logout()` → `queryClient.clear()` → `navigate('/login', replace:true)`; `onError` handler also clears+navigates (T-10-31 mitigated); 2 unit tests verify the full chain (D-08, FE-06)
- `RoleSwitcher` returns null when `API_MODE !== 'mock'` (D-12); hooks still called before early return to satisfy `react-hooks/rules-of-hooks`; invalidates `authKeys.me` on role change (Pitfall 7)
- ESLint `no-restricted-syntax` block bans `CallExpression[callee.name='fetch']` outside `src/shared/api/services/http/**`; `raw-fetch-leak.ts` fixture proves it fires; `lint:fixtures` exits 0 with all 4 fixtures (FE-07)
- `ru.ts` adds full `auth` and `clients` top-level blocks per UI-SPEC Copywriting Contract — 80+ new keys, `TranslationKey` type auto-derives them
- `.env.example` documents `VITE_API_MODE=mock|http` and `VITE_API_BASE_URL`

## Task Commits

1. **Task 1: Splash + main.tsx + ProfileMenu logout + RoleSwitcher guard** - `ae3d1fa` (feat)
2. **Task 2: ESLint fetch ban (FE-07) + raw-fetch-leak fixture** - `692d596` (feat)
3. **Task 3: Expand ru.ts (auth + clients) + .env documentation** - `9243106` (feat)

## Files Created/Modified

- `apps/admin-web/src/shared/ui/splash.tsx` — Splash component: centered "SportZal" + Loader2 animate-spin, semantic tokens only
- `apps/admin-web/src/app/main.tsx` — Added splash gate: http-mode renders Splash, awaits ensureQueryData(authKeys.me) with retry:false, catches 401
- `apps/admin-web/src/shared/ui/app-shell/ProfileMenu.tsx` — Active logout via useMutation; LogOut icon; disabled={logout.isPending}
- `apps/admin-web/src/shared/ui/app-shell/ProfileMenu.test.tsx` — 2 tests: renders "Выйти" item; logout calls mock chain in order
- `apps/admin-web/src/shared/ui/app-shell/RoleSwitcher.tsx` — API_MODE guard + hooks before early return + authKeys.me invalidation
- `apps/admin-web/eslint.config.js` — New FE-07 block: no-restricted-syntax banning fetch() outside http/**
- `apps/admin-web/scripts/eslint.fixtures.config.js` — Same fetch ban added to fixtures config
- `apps/admin-web/scripts/assert-eslint-fixtures.mjs` — 4th EXPECTED entry for raw-fetch-leak.ts
- `apps/admin-web/src/__fixtures/raw-fetch-leak.ts` — Negative-test fixture: `export const leaked = fetch('/api/v1/clients')`
- `apps/admin-web/src/shared/i18n/ru.ts` — Added auth + clients top-level blocks (80+ keys per UI-SPEC)
- `apps/admin-web/.env.example` — Documents VITE_API_MODE and VITE_API_BASE_URL

## Decisions Made

- **userEvent over fireEvent for Radix DropdownMenu**: `fireEvent.click` does not dispatch pointer events that Radix UI's DropdownMenu trigger requires; `userEvent.setup()` from `@testing-library/user-event` correctly opens the dropdown
- **vi.hoisted() for all mock factories**: Same pattern established in Plan 06 — mock factories in `vi.mock()` are hoisted before `const` declarations, so `vi.hoisted(() => ({ mock: vi.fn() }))` is required
- **Hooks before early return in RoleSwitcher**: React-hooks/rules-of-hooks forbids conditional hook calls; `useQueryClient` and `useSessionStore` must be called before `if (API_MODE !== 'mock') return null`
- **.env.development is gitignored**: `.env.*` is in `.gitignore` (except `.env.example`); updated `.env.development` locally — this is expected behaviour, not a blocker

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] vi.mock hoisting causes ReferenceError for mock factories**
- **Found during:** Task 1 (ProfileMenu.test.tsx RED phase)
- **Issue:** `const navigateMock = vi.fn()` etc. at module level are inaccessible in `vi.mock()` factory bodies (Vitest hoists `vi.mock` above const declarations)
- **Fix:** Changed to `vi.hoisted(() => ({ navigateMock: vi.fn() }))` destructuring pattern for all 3 mocks
- **Files modified:** `apps/admin-web/src/shared/ui/app-shell/ProfileMenu.test.tsx`
- **Verification:** Both tests pass
- **Committed in:** ae3d1fa (Task 1 commit)

**2. [Rule 1 - Bug] react-hooks/rules-of-hooks on RoleSwitcher**
- **Found during:** Task 1 lint check
- **Issue:** `if (API_MODE !== 'mock') return null` was placed before hook calls, violating rules-of-hooks
- **Fix:** Moved all `useQueryClient` + `useSessionStore` calls before the early return; `const current` derivation moved after the guard
- **Files modified:** `apps/admin-web/src/shared/ui/app-shell/RoleSwitcher.tsx`
- **Verification:** `pnpm lint` exits 0 (0 errors)
- **Committed in:** ae3d1fa (Task 1 commit)

**3. [Rule 1 - Bug] fireEvent.click doesn't open Radix DropdownMenu in tests**
- **Found during:** Task 1 GREEN phase test run
- **Issue:** `fireEvent.click` dispatches a DOM click but not pointer events — Radix DropdownMenu requires pointer-down/up sequence to open
- **Fix:** Switched to `userEvent.setup()` + `await user.click(...)` for the trigger interaction
- **Files modified:** `apps/admin-web/src/shared/ui/app-shell/ProfileMenu.test.tsx`
- **Verification:** Both tests pass (Выйти item found, logout chain called)
- **Committed in:** ae3d1fa (Task 1 commit)

**4. [Rule 3 - Deviation] .env.development gitignored**
- **Found during:** Task 3 git staging
- **Issue:** `.env.*` is gitignored except `.env.example`; `git add .env.development` fails
- **Fix:** Documented change in `.env.development` locally; only `.env.example` committed
- **Files modified:** `.env.example` (committed), `.env.development` (local only)
- **Verification:** Plan's intent achieved — `.env.example` has the canonical documentation
- **Committed in:** 9243106 (Task 3 commit)

---

**Total deviations:** 4 auto-fixed (3 bugs, 1 environment constraint)
**Impact on plan:** All fixes required for correct operation. No scope creep.

## Issues Encountered

- **Pre-existing test failure**: `src/shared/ui/components-json.test.ts` expects `style: 'new-york'` but finds `base-nova`. Introduced in Plan 03; not caused by Plan 07. 17/18 test files pass; all Phase 10 feature tests pass.

## Known Stubs

None — all plan outputs are fully wired.

## Threat Flags

None — all implemented items match the plan's threat model. T-10-27 (existing rules preserved), T-10-29 (catch block in splash gate), T-10-31 (onError still clears cache) all mitigated as planned.

## Self-Check: PASSED

All created files verified:
- `apps/admin-web/src/shared/ui/splash.tsx` — contains Loader2, bg-background, text-muted-foreground
- `apps/admin-web/src/app/main.tsx` — contains Splash, API_MODE === 'http', ensureQueryData, authKeys.me
- `apps/admin-web/src/shared/ui/app-shell/ProfileMenu.tsx` — contains queryClient.clear, LogOut, services.auth.logout; no `<DropdownMenuItem disabled`
- `apps/admin-web/src/shared/ui/app-shell/ProfileMenu.test.tsx` — 2 tests pass
- `apps/admin-web/src/shared/ui/app-shell/RoleSwitcher.tsx` — contains API_MODE !== 'mock'
- `apps/admin-web/eslint.config.js` — contains callee.name='fetch', src/shared/api/services/http/
- `apps/admin-web/src/__fixtures/raw-fetch-leak.ts` — contains fetch(
- `apps/admin-web/scripts/assert-eslint-fixtures.mjs` — contains raw-fetch-leak.ts
- `apps/admin-web/src/shared/i18n/ru.ts` — contains Войти в систему, Клиентов пока нет, Срок действия ссылки истёк
- `apps/admin-web/.env.example` — contains VITE_API_MODE, VITE_API_BASE_URL

All 3 task commits verified: ae3d1fa, 692d596, 9243106

---
*Phase: 10-admin-web-auth-clients-wiring*
*Completed: 2026-05-04*
