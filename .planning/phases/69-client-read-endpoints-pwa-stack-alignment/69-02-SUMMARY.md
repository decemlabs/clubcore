---
phase: 69-client-read-endpoints-pwa-stack-alignment
plan: "02"
subsystem: apps/client-pwa
tags: [pwa, frontend, typescript, vite, vitest, eslint, workspace, client-fetcher]
dependency_graph:
  requires: []
  provides: [pwa-workspace-member, client-fetcher-ts, vite6-pwa-config, smoke-tests]
  affects: [pnpm-lock.yaml, apps/client-pwa]
tech_stack:
  added:
    - vite-plugin-pwa@0.21.2
    - vitest@2.1.9
    - typescript-eslint@8.x
    - eslint-plugin-react-hooks@5.x
    - "@types/node@22.x"
    - "@types/react@18.x"
  patterns:
    - allowJs TypeScript ramp (checkJs:false, existing .jsx screens untouched)
    - vite-plugin-pwa with navigateFallbackDenylist (SW never caches /api/*)
    - client-scoped CSRF cookie isolation (clubcore_client_csrf vs clubcore_csrf)
    - single-flight refresh to /api/v1/client/session/refresh
key_files:
  created:
    - apps/client-pwa/src/lib/clientFetcher.ts
    - apps/client-pwa/src/lib/clientFetcher.test.tsx
    - apps/client-pwa/vite.config.ts
    - apps/client-pwa/tsconfig.json
    - apps/client-pwa/tsconfig.app.json
    - apps/client-pwa/tsconfig.node.json
    - apps/client-pwa/eslint.config.js
    - apps/client-pwa/vitest.config.ts
    - apps/client-pwa/src/test/setup.ts
  modified:
    - apps/client-pwa/package.json
    - pnpm-lock.yaml
  deleted:
    - apps/client-pwa/bun.lock (PWA-01)
    - apps/client-pwa/vite.config.js (replaced by .ts)
    - apps/client-pwa/src/lib/clientFetcher.test.ts (renamed to .tsx for JSX support)
decisions:
  - "navigateFallbackDenylist placed inside workbox:{} in vite-plugin-pwa v0.21 (not top-level VitePWAOptions — the top-level option was deprecated)"
  - "ESLint config restricts linting to .ts/.tsx files only (D-69-06 allowJs ramp — existing .jsx screens have many pre-existing lint issues that are out of scope)"
  - "Test file renamed from .test.ts to .test.tsx to enable JSX syntax for the render-without-crash test"
  - "React.ElementType cast used in test to work around react-router-dom v6 + @types/react@18 ReactPortal.children type incompatibility (runtime-safe)"
metrics:
  duration: "~12m"
  completed: "2026-05-29T20:34:02Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 9
  files_modified: 2
  files_deleted: 3
---

# Phase 69 Plan 02: PWA Stack Alignment Summary

## One-liner

Joins `apps/client-pwa` into the pnpm workspace with Vite 6, TypeScript strict + allowJs ramp, vite-plugin-pwa (/api/* never cached), and a typed `clientFetcher.ts` over `@clubcore/api-client` using `clubcore_client_csrf` + `/api/v1/client/session/refresh`.

## What Was Built

### Task 1: pnpm workspace + Vite 6 + TS/ESLint/Vitest configs (commit: 91cda236)

- Rewrote `apps/client-pwa/package.json`: renamed to `@clubcore/client-pwa`, added `pnpm@9.15.9` + engines, workspace scripts (dev/build/preview/lint/test/typecheck), added `@clubcore/api-client: workspace:*` dep, bumped `vite: ^6.0.0`, added `vite-plugin-pwa`, `vitest`, `typescript-eslint`, `@types/react@18`, `@types/react-dom@18`, `@types/node`.
- Deleted `bun.lock` (PWA-01) and `vite.config.js` (replaced by `.ts`).
- Created `vite.config.ts`: Vite 6, VitePWA with `workbox.navigateFallbackDenylist: [/^\/api\//]` + `workbox.runtimeCaching: []` — SW never caches `/api/*` (T-69-07, PWA-07). Port 5174 to avoid admin-web conflict. ES2022 target. Dev proxy `/api → http://localhost:8000`.
- Created `tsconfig.json`, `tsconfig.app.json` (strict + allowJs:true + checkJs:false — D-69-06 ramp), `tsconfig.node.json` mirroring admin-web pattern.
- Created `eslint.config.js`: flat config with tseslint + react-hooks + react-refresh; restricts linting to `.ts`/`.tsx` only (existing `.jsx` screens excluded per D-69-06).
- Created `vitest.config.ts`: jsdom env, setupFiles, globals, `src/**/*.{test,spec}.{ts,tsx}` include pattern.
- Created `src/test/setup.ts`: localStorage shim + RTL cleanup (mirrors admin-web).
- Updated `pnpm-lock.yaml` with all new packages.

### Task 2: clientFetcher.ts + smoke tests (TDD GREEN, commits: 137b472f, 52f3eaea)

- Created `src/lib/clientFetcher.ts`: client-scoped typed transport (PWA-03):
  - `readClientCsrfCookie()` reads `clubcore_client_csrf` (NOT `clubcore_csrf` — T-69-08/CISO-05)
  - `clientRefreshOnce()` single-flights to `/api/v1/client/session/refresh` (NOT `/api/v1/auth/refresh` — T-69-09)
  - `CLIENT_AUTH_EXEMPT_PATHS` covers `/api/v1/client/otp/*`, `/api/v1/client/session/*`, `/api/v1/client/me`
  - `clientRequest<P,M>()` full refresh-on-401 retry semantics mirroring staff fetcher
  - Imports `ApiError` from `@clubcore/api-client`
- Created `src/lib/clientFetcher.test.tsx` (3 smoke tests — D-69-09):
  1. `readClientCsrfCookie()` returns `clubcore_client_csrf` value, not `clubcore_csrf`
  2. `CLIENT_AUTH_EXEMPT_PATHS` contains `/api/v1/client/otp/request` and `/api/v1/client/session/refresh`
  3. App renders without throwing (MemoryRouter + TweaksProvider + UIProvider wrapper)
- All gates green: `typecheck`, `lint`, `test` (3/3 passing), `build` (dist/sw.js + dist/manifest.webmanifest emitted)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] navigateFallbackDenylist moved inside workbox:{}**
- **Found during:** Task 1 typecheck
- **Issue:** `navigateFallbackDenylist` is not a top-level `VitePWAOptions` field in vite-plugin-pwa v0.21 — it belongs inside `workbox: Partial<GenerateSWOptions>`. TS error TS2353.
- **Fix:** Moved to `workbox: { navigateFallbackDenylist: [/^\/api\//], runtimeCaching: [] }`. The plan's grep-based assertion (`grep -q 'navigateFallbackDenylist' vite.config.ts`) still passes.
- **Files modified:** `apps/client-pwa/vite.config.ts`
- **Commit:** 52f3eaea

**2. [Rule 1 - Bug] ESLint config: empty zones[] invalid + pre-existing JSX lint errors**
- **Found during:** Task 1 lint
- **Issue:** `'import/no-restricted-paths': ['error', { zones: [] }]` fails with "Value [] should NOT have fewer than 1 items". Additionally, applying ESLint to `.jsx` files exposed ~38 pre-existing lint errors in the existing screens.
- **Fix:** Removed the empty `zones` rule; restricted linting scope to `.ts`/`.tsx` files only (matches D-69-06: existing JSX screens not modified). This is architecturally correct — the import boundary rules will be added when screens are migrated (Phase 71+).
- **Files modified:** `apps/client-pwa/eslint.config.js`
- **Commit:** 52f3eaea

**3. [Rule 1 - Bug] Test file .test.ts → .test.tsx rename for JSX support**
- **Found during:** Task 2 test run
- **Issue:** Vitest transforms files via Vite's react() plugin. `require()` calls in `.ts` files bypass the transform pipeline, causing "Unexpected token '<'" on JSX content in imported `.jsx` files. Also, `React.createElement` overload resolution in TS strict mode needed JSX syntax.
- **Fix:** Renamed to `.test.tsx` and switched to dynamic `import()` (Vite-transformed), with `React.ElementType` casts for the react-router-dom v6 + `@types/react@18` JSX type incompatibility.
- **Files modified:** `apps/client-pwa/src/lib/clientFetcher.test.tsx`
- **Commit:** 52f3eaea

**4. [Rule 2 - Missing dep] @types/node added to devDependencies**
- **Found during:** Task 2 typecheck
- **Issue:** `tsconfig.node.json` declares `"types": ["node"]` but `@types/node` was absent from devDeps — TS error TS2688.
- **Fix:** Added `"@types/node": "^22.10.5"` to devDependencies; updated `pnpm-lock.yaml`.
- **Files modified:** `apps/client-pwa/package.json`, `pnpm-lock.yaml`
- **Commit:** 52f3eaea

## TDD Gate Compliance

- RED gate commit: `137b472f` — `test(69-02): add failing tests for clientFetcher (RED)`
- GREEN gate commit: `52f3eaea` — `feat(69-02): clientFetcher.ts over @clubcore/api-client + smoke tests (GREEN)`
- REFACTOR gate: not needed (code was clean on first pass)

## Known Stubs

None. All new code (`clientFetcher.ts`, test file, config files) is fully functional. The existing `.jsx` screens that use mock data are pre-existing and explicitly deferred to Phase 71 (D-69-deferred, PWA-05).

## Threat Flags

No new security-relevant surface introduced beyond the plan's threat model (T-69-07, T-69-08, T-69-09 all mitigated as planned).

## Self-Check: PASSED

All key files verified to exist on disk. All commits verified in git log.

| Check | Result |
|-------|--------|
| `apps/client-pwa/src/lib/clientFetcher.ts` | FOUND |
| `apps/client-pwa/src/lib/clientFetcher.test.tsx` | FOUND |
| `apps/client-pwa/vite.config.ts` | FOUND |
| `apps/client-pwa/tsconfig.app.json` | FOUND |
| `apps/client-pwa/eslint.config.js` | FOUND |
| `apps/client-pwa/vitest.config.ts` | FOUND |
| `apps/client-pwa/src/test/setup.ts` | FOUND |
| `apps/client-pwa/bun.lock` removed | CONFIRMED |
| `apps/client-pwa/vite.config.js` removed | CONFIRMED |
| commit `91cda236` | FOUND |
| commit `137b472f` | FOUND |
| commit `52f3eaea` | FOUND |
