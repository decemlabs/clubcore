---
phase: 10-admin-web-auth-clients-wiring
plan: "05"
subsystem: auth
tags: [admin-web, routes, auth, login, telegram, otp, tanstack-router, react-hook-form, zod]

# Dependency graph
requires:
  - phase: 10-admin-web-auth-clients-wiring-01
    provides: ReUI primitives (Button, Input, Form, Label, InputOTP) in shared/ui
  - phase: 10-admin-web-auth-clients-wiring-02
    provides: authKeys factory, emailLoginSchema, telegramOtpSchema, AuthService contract
  - phase: 10-admin-web-auth-clients-wiring-03
    provides: mock auth service with telegramStart/Status/Verify state-machine
  - phase: 10-admin-web-auth-clients-wiring-04
    provides: redirect-on-session-expired, API_MODE-aware session adapter, useCurrentRole
provides:
  - _public/_protected pathless layout split in routes/
  - AppShell isolated to _protected.tsx only (stripped from __root.tsx)
  - /login route (_public/login.tsx) with validateSearch({next}) + beforeLoad silent-redirect (D-03)
  - features/auth/api/hooks.ts: useMe, useLogin, useLogout, useTelegramStart, useTelegramStatus, useTelegramVerify
  - features/auth/components/LoginPage.tsx: Tabs with Email default (D-02), open-redirect guard
  - features/auth/components/EmailLoginForm.tsx: RHF + zodResolver + inline error mapping
  - features/auth/components/TelegramLoginTab.tsx: 3-state machine (idle/polling/bound+OTP), 5min timeout
  - features/auth/index.ts barrel export
  - LoginPage.test.tsx: 4 tests
  - TelegramLoginTab.test.tsx: 2 tests
affects:
  - 10-06 (clients route now under _protected/ as placeholder; Plan 06 replaces fully)
  - 10-07 (redirect-on-session-expired TODO type cast resolved — /login is now in routeTree.gen.ts)
  - any plan adding protected routes (must nest under /_protected/)

# Tech tracking
tech-stack:
  added:
    - shadcn standard Tabs component (standard shadcn fallback — ReUI registry returned 404 for tabs)
    - '@base-ui/react' installed (was in lockfile but not in node_modules; tabs.tsx depends on it)
  patterns:
    - Pathless layout split: _public (no shell/auth) + _protected (AppShell + http-mode auth gate)
    - LoginPage imports Route directly for useSearch (TanStack Router component-level route binding)
    - vi.mock('@/routes/_public/login') in tests to stub Route.useSearch() without full router context
    - Test files exempt from import/no-restricted-paths to allow mock DB access in test setup

key-files:
  created:
    - apps/admin-web/src/routes/_public.tsx
    - apps/admin-web/src/routes/_public/login.tsx
    - apps/admin-web/src/routes/_protected.tsx
    - apps/admin-web/src/routes/_protected/index.tsx
    - apps/admin-web/src/routes/_protected/clients.tsx
    - apps/admin-web/src/routes/_protected/schedule.tsx
    - apps/admin-web/src/routes/_protected/staff.tsx
    - apps/admin-web/src/routes/_protected/finance.tsx
    - apps/admin-web/src/routes/_protected/settings.tsx
    - apps/admin-web/src/shared/ui/tabs.tsx
    - apps/admin-web/src/features/auth/api/hooks.ts
    - apps/admin-web/src/features/auth/components/LoginPage.tsx
    - apps/admin-web/src/features/auth/components/LoginPage.test.tsx
    - apps/admin-web/src/features/auth/components/EmailLoginForm.tsx
    - apps/admin-web/src/features/auth/components/TelegramLoginTab.tsx
    - apps/admin-web/src/features/auth/components/TelegramLoginTab.test.tsx
    - apps/admin-web/src/features/auth/index.ts
  modified:
    - apps/admin-web/src/routes/__root.tsx (AppShell stripped)
    - apps/admin-web/eslint.config.js (tabs.tsx in allow-list; test files exempt from import/no-restricted-paths)
  deleted:
    - apps/admin-web/src/routes/index.tsx (moved to _protected/)
    - apps/admin-web/src/routes/clients.tsx (moved to _protected/)
    - apps/admin-web/src/routes/schedule.tsx (moved to _protected/)
    - apps/admin-web/src/routes/staff.tsx (moved to _protected/)
    - apps/admin-web/src/routes/finance.tsx (moved to _protected/)
    - apps/admin-web/src/routes/settings.tsx (moved to _protected/)

key-decisions:
  - "Tabs primitive: standard shadcn tabs installed as fallback (ReUI https://reui.io/r/base-nova/tabs.json returned 404); uses @base-ui/react/tabs not @radix-ui"
  - "base-ui tabs use aria-selected=true for active tab (not data-state=active like Radix); tests adapted to check aria-selected"
  - "@base-ui/react was in pnpm lockfile but not installed in node_modules — ran pnpm install to fix typecheck"
  - "test files need import/no-restricted-paths exemption — TelegramLoginTab.test.tsx imports resetDB from mock/_db for test isolation"
  - "_public/login.tsx stub created as part of Task 2 (not Task 3) to prevent TanStack Router path conflict during routeTree generation"
  - "open-redirect guard in LoginPage.sanitizeNext: rejects next values starting with 'http' or '//' (T-10-17)"

patterns-established:
  - "Pathless layout routes: _public (Outlet only) + _protected (AppShell + auth gate) under __root"
  - "Route-component coupling: LoginPage imports Route from routes/_public/login for useSearch(); mocked in tests via vi.mock"
  - "TelegramLoginTab state machine: 4 render states (idle/polling/bound/timedOut); timeout via setInterval + startedAtRef"
  - "Auth hooks: useTelegramStatus polls every 3000ms via refetchInterval; enabled flag stops polling"

requirements-completed: [FE-02]

# Metrics
duration: 9min
completed: "2026-05-04"
---

# Phase 10 Plan 05: Routes Restructure + Login Page Summary

**Pathless _public/_protected layout split ships /login standalone without AppShell; Tabs with Email/Telegram OTP tabs, 3s polling state-machine, 5min timeout, and open-redirect guard**

## Performance

- **Duration:** 9 min
- **Started:** 2026-05-04T13:32:01Z
- **Completed:** 2026-05-04T13:41:00Z
- **Tasks:** 3 (+ 1 auto-approved checkpoint)
- **Files modified:** 23 (17 created, 2 modified, 6 deleted)

## Accomplishments

- Routes tree restructured: 6 flat routes moved under `_protected/`, AppShell removed from `__root.tsx`, `_public` layout for /login added
- /login route ships with `validateSearch({next})` + `beforeLoad` silent-redirect for already-authenticated users (D-03), satisfying FE-02
- Full auth feature surface: useMe, useLogin, useLogout, useTelegramStart, useTelegramStatus, useTelegramVerify hooks; LoginPage + EmailLoginForm + TelegramLoginTab components
- TelegramLoginTab implements 4-state machine (idle → polling → bound+OTP → timed-out) with 3s poll cadence, 5min timeout, "Получить новую ссылку" reset (D-04)
- Open-redirect guard in `LoginPage.sanitizeNext` protects `?next=` param (T-10-17); `rel="noreferrer"` on Telegram deep-link (T-10-18)
- All 11 auth feature tests pass; typecheck and lint exit 0

## Task Commits

1. **Task 1: Install ReUI Tabs primitive** - `26f1340` (chore)
2. **Task 2: Routes restructure** - `499f59c` (refactor)
3. **Task 3: features/auth + /login route** - `1123822` (feat)

## Files Created/Modified

- `apps/admin-web/src/shared/ui/tabs.tsx` - Standard shadcn Tabs component (base-ui fallback; ReUI 404'd)
- `apps/admin-web/src/routes/__root.tsx` - AppShell stripped; now Outlet + devtools only
- `apps/admin-web/src/routes/_public.tsx` - Pathless public layout (Outlet only)
- `apps/admin-web/src/routes/_public/login.tsx` - /login with validateSearch({next}) + beforeLoad (D-03)
- `apps/admin-web/src/routes/_protected.tsx` - AppShell wrapper + http-mode auth gate + mock bypass
- `apps/admin-web/src/routes/_protected/{index,clients,schedule,staff,finance,settings}.tsx` - Moved from flat routes
- `apps/admin-web/src/features/auth/api/hooks.ts` - 6 TanStack Query hooks
- `apps/admin-web/src/features/auth/components/LoginPage.tsx` - Tabs container + heading + sanitizeNext
- `apps/admin-web/src/features/auth/components/EmailLoginForm.tsx` - RHF + zodResolver + 3 error codes
- `apps/admin-web/src/features/auth/components/TelegramLoginTab.tsx` - 4-state polling machine
- `apps/admin-web/src/features/auth/components/LoginPage.test.tsx` - 4 unit tests
- `apps/admin-web/src/features/auth/components/TelegramLoginTab.test.tsx` - 2 unit tests
- `apps/admin-web/src/features/auth/index.ts` - Barrel export
- `apps/admin-web/eslint.config.js` - tabs.tsx allow-list + test files import/no-restricted-paths exemption

## Decisions Made

- **Tabs fallback**: ReUI base-nova registry returned 404 for tabs; installed standard `shadcn@latest add tabs` which uses `@base-ui/react/tabs`. This is still consistent with the overall base-nova stack.
- **aria-selected vs data-state**: base-ui tabs use `aria-selected="true"` for active tab (not Radix's `data-state="active"`). Tests adapted to check `aria-selected` per the installed component's actual behavior.
- **Stub-first login route**: Task 2 created a minimal `_public/login.tsx` stub to prevent TanStack Router path conflict error during routeTree generation. Task 3 replaced it with full implementation.
- **eslint test exemption**: `import/no-restricted-paths` turned off for `*.test.ts(x)` files — test setup legitimately needs direct mock DB access (`resetDB()`). Production code boundary still enforced.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] ReUI tabs 404 — fell back to standard shadcn tabs**
- **Found during:** Task 1
- **Issue:** `pnpm dlx shadcn@latest add @reui/tabs` returned HTTP 404 from ReUI base-nova registry
- **Fix:** Installed standard shadcn tabs via `pnpm dlx shadcn@latest add tabs` (Plan 01 Task 2 documented this fallback pattern)
- **Files modified:** `apps/admin-web/src/shared/ui/tabs.tsx`
- **Verification:** tabs.tsx exists with TabsList, TabsTrigger, TabsContent exports; typecheck passes
- **Committed in:** 26f1340 (Task 1 commit)

**2. [Rule 3 - Blocking] @base-ui/react not installed despite being in lockfile**
- **Found during:** Task 2 typecheck
- **Issue:** `tabs.tsx` imports from `@base-ui/react/tabs`; package was in lockfile but absent from node_modules
- **Fix:** Ran `pnpm install --filter sportzal-adminka` to install missing peer dependency
- **Files modified:** None (install only)
- **Verification:** typecheck exits 0 after install
- **Committed in:** No code change needed

**3. [Rule 3 - Blocking] TanStack Router path conflict during routeTree generation**
- **Found during:** Task 2 (running `pnpm dev` to regenerate routeTree)
- **Issue:** `_public.tsx` without children was treated as a leaf route at `/`, conflicting with `_protected/index.tsx` also at `/`
- **Fix:** Created `_public/login.tsx` stub as part of Task 2 so the router sees `_public` as a layout with children
- **Files modified:** `apps/admin-web/src/routes/_public/login.tsx` (stub created in T2, replaced with full impl in T3)
- **Verification:** `pnpm dev` starts without route conflicts; routeTree.gen.ts generates correctly
- **Committed in:** 499f59c (Task 2 commit)

**4. [Rule 1 - Bug] Test files blocked by import/no-restricted-paths**
- **Found during:** Task 3 lint check
- **Issue:** `TelegramLoginTab.test.tsx` imports `resetDB` from `@/shared/api/services/mock/_db` — a restricted import path. Test files legitimately need this for test isolation.
- **Fix:** Added `'import/no-restricted-paths': 'off'` to the test files block in `eslint.config.js`
- **Files modified:** `apps/admin-web/eslint.config.js`
- **Verification:** `pnpm lint` exits 0
- **Committed in:** 1123822 (Task 3 commit)

---

**Total deviations:** 4 auto-fixed (1 service unavailable, 1 missing install, 1 router conflict, 1 lint config)
**Impact on plan:** All auto-fixes required for correct behavior. The tabs fallback is fully functional; base-ui tabs provide equivalent UX. No scope creep.

## Issues Encountered

- **Pre-existing test failure**: `src/shared/ui/components-json.test.ts` expects `style: 'new-york'` but finds `base-nova`. This was introduced in Plan 03 when `components.json` was updated for ReUI registry. Not caused by Plan 05.

## Known Stubs

None — all placeholder stubs from Task 2 were replaced with full implementations in Task 3.

## Next Phase Readiness

- FE-02 complete: /login renders standalone, two tabs, Telegram polls, code entry works
- D-01: pathless _public + _protected layout split active; /login has no AppShell
- D-02: Email tab is default
- D-03: silent redirect for already-authenticated /login visits
- D-04: 3s polling + 5min timeout + refresh button functional with mock service
- Plan 04 TODO resolved: /login is now in routeTree.gen.ts → `redirect-on-session-expired.ts` type cast can be cleaned up (tracked as deferred)
- Plan 06 (clients feature) can proceed: `_protected/clients.tsx` placeholder is in place

## Self-Check: PASSED

All created files verified:
- `apps/admin-web/src/routes/_public.tsx` ✓
- `apps/admin-web/src/routes/_public/login.tsx` ✓
- `apps/admin-web/src/routes/_protected.tsx` ✓
- `apps/admin-web/src/routes/_protected/index.tsx` ✓
- `apps/admin-web/src/features/auth/api/hooks.ts` ✓
- `apps/admin-web/src/features/auth/components/LoginPage.tsx` ✓
- `apps/admin-web/src/features/auth/index.ts` ✓
All 3 task commits verified in git log: 26f1340, 499f59c, 1123822

---
*Phase: 10-admin-web-auth-clients-wiring*
*Completed: 2026-05-04*
