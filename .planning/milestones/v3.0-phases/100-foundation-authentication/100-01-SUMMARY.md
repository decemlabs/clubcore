---
phase: 100-foundation-authentication
plan: "01"
subsystem: infra
tags: [pnpm, workspace, eslint, vite, ci, admin-app]

# Dependency graph
requires: []
provides:
  - "@clubcore/admin-app workspace member (pnpm@9.15.9, @clubcore/api-client workspace:*)"
  - "Vite dev proxy /api → http://localhost:8000 (same-origin API in dev)"
  - "ESLint import boundary (pages/layouts/components must not import api/client.ts)"
  - "VITE_API_MODE chokepoint (only features/*/api.ts swap-seam files allowed)"
  - "Dedicated parallel admin-app CI job (typecheck + lint + test + build)"
  - "Regenerated root pnpm-lock.yaml including @clubcore/admin-app"
affects:
  - "100-02 (transport seam — builds on this workspace + proxy)"
  - "100-03 and beyond (auth wiring, RBAC port — all build on absorbed package)"

# Tech tracking
tech-stack:
  added:
    - "eslint-plugin-import@^2.32.0 (import boundary zones)"
    - "eslint-import-resolver-typescript@^3.6.3 (TS path resolution for zones)"
  patterns:
    - "pnpm workspace absorption: @clubcore/admin-app mirrors client-pwa pattern"
    - "Per-app parallel CI job with recursive-step exclusion (D-72-05 precedent)"
    - "Vite dev proxy VITE_API_PROXY_TARGET env var for flexible local dev"
    - "ESLint import boundary: only features/*/api.ts may call api/client.ts"
    - "VITE_API_MODE chokepoint: only swap-seam files read the env var"

key-files:
  created: []
  modified:
    - "apps/admin-app/package.json — @clubcore/admin-app, pnpm@9.15.9, api-client dep"
    - "apps/admin-app/.gitignore — removed bun/npm lockfile lines"
    - "apps/admin-app/CLAUDE.md — pnpm commands replacing bun"
    - "apps/admin-app/README.md — pnpm commands replacing bun"
    - "apps/admin-app/vite.config.ts — server.proxy /api block"
    - "apps/admin-app/eslint.config.js — import boundary + VITE_API_MODE chokepoint"
    - ".github/workflows/ci.yml — admin-app parallel job + recursive exclusions"
    - "pnpm-lock.yaml — regenerated including @clubcore/admin-app"

key-decisions:
  - "D-100-01-BOUNDARY: import/no-restricted-paths targets pages/layouts/components only (not features/**); features/*/api.ts are the legitimate swap-seam callers, not violations"
  - "D-100-01-ESLINTJS: @eslint/js pinned to ^9.17.0 to match eslint@9 peer constraint (original ^10.0.1 was incompatible)"
  - "D-100-01-VITE-STAY: Vite 5 not bumped to Vite 6 — out of scope, avoids risk"

patterns-established:
  - "Workspace absorption: scoped name + pnpm packageManager + workspace:* dep + engines field"
  - "CI parallel job: each app gets its own job; excluded from recursive pnpm -r steps"
  - "Vite proxy: VITE_API_PROXY_TARGET env var, changeOrigin: true, active only in dev server"

requirements-completed: [FND-01]

# Metrics
duration: 6min
completed: 2026-06-13
---

# Phase 100 Plan 01: Workspace Absorption Summary

**admin-app absorbed into clubcore pnpm workspace as @clubcore/admin-app with Vite dev proxy, ESLint import boundary, VITE_API_MODE chokepoint, and dedicated parallel CI job — all four scripts (typecheck/lint/test/build) green**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-06-13T08:48:51Z
- **Completed:** 2026-06-13T08:54:08Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- `apps/admin-app` absorbed as `@clubcore/admin-app` pnpm workspace member with `pnpm@9.15.9`, `engines` field, `@clubcore/api-client: workspace:*` dependency, typescript pinned to `~5.7.2`
- Vite dev proxy added: `/api` → `VITE_API_PROXY_TARGET ?? http://localhost:8000` (same-origin API calls in dev, no CORS)
- ESLint import boundary: `pages/layouts/components` must not import `api/client.ts` directly; `VITE_API_MODE` chokepoint enforced
- Dedicated parallel `admin-app` CI job (no `needs:`) added; admin-app excluded from all three recursive `pnpm -r` frontend steps
- Root `pnpm-lock.yaml` regenerated, `bun.lock` deleted; `pnpm install --frozen-lockfile` verified clean

## Task Commits

1. **Task 1: Migrate admin-app to pnpm workspace** — `3e614240` (chore)
2. **Task 2: Add Vite dev proxy and ESLint import-boundary** — `f62dc407` (feat)
3. **Task 3: Generate lockfile, add CI job, verify green** — `93917556` (feat)

## Files Created/Modified

- `apps/admin-app/package.json` — `@clubcore/admin-app`, `pnpm@9.15.9`, `@clubcore/api-client: workspace:*`, typescript `~5.7.2`, eslint-plugin-import devDeps, drop check/format scripts
- `apps/admin-app/.gitignore` — removed bun/npm lockfile lines, kept node_modules/dist/*.tsbuildinfo
- `apps/admin-app/CLAUDE.md` — pnpm commands replacing bun (install, dev, build, lint, test)
- `apps/admin-app/README.md` — pnpm commands replacing bun, stack updated
- `apps/admin-app/vite.config.ts` — `server.proxy['/api']` with `VITE_API_PROXY_TARGET` env var
- `apps/admin-app/eslint.config.js` — `eslint-plugin-import` registered, `import/no-restricted-paths` zone, `VITE_API_MODE` chokepoint config object
- `.github/workflows/ci.yml` — `admin-app` parallel job + `--filter '!@clubcore/admin-app'` on all three recursive steps
- `pnpm-lock.yaml` — regenerated workspace lockfile including `@clubcore/admin-app`
- ~~`apps/admin-app/bun.lock`~~ — deleted (superseded by root pnpm-lock.yaml)

## Decisions Made

- **D-100-01-BOUNDARY**: The `import/no-restricted-paths` zone targets `./src/pages/**`, `./src/layouts/**`, and `./src/components/**` only — NOT `./src/features/**`. The `features/*/api.ts` files ARE the legitimate swap-seam layer (TanStack Query hooks); restricting them would flag 19 pre-existing files as violations. The boundary intent is to stop pages/layouts/components from bypassing the hooks layer.
- **D-100-01-ESLINTJS**: `@eslint/js` version downgraded from `^10.0.1` to `^9.17.0`. Version 10 requires `eslint@^10.0.0` as a peer but admin-app stays on eslint@9 (matching the workspace). This was a bug in the existing admin-app package.json.
- **D-100-01-VITE-STAY**: Vite 5 is retained (not upgraded to Vite 6). Out of scope for this plan; upgrading risks build regressions not covered by existing tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] @eslint/js peer dependency mismatch**
- **Found during:** Task 3 (pnpm install)
- **Issue:** `@eslint/js@^10.0.1` requires `eslint@^10.0.0` as a peer; admin-app uses `eslint@^9.19.0`. pnpm reported an unmet peer-dep warning and would fail on `--strict-peer-dependencies`.
- **Fix:** Downgraded `@eslint/js` to `^9.17.0` (matches `client-pwa` and `admin-web`)
- **Files modified:** `apps/admin-app/package.json`, `pnpm-lock.yaml`
- **Verification:** `pnpm install` completed with no peer-dep warnings; `--frozen-lockfile` succeeds
- **Committed in:** `93917556` (Task 3 commit)

**2. [Rule 1 - Bug] import/no-restricted-paths target too broad**
- **Found during:** Task 3 (pnpm -F @clubcore/admin-app lint)
- **Issue:** Zone target included `./src/features/**`, which flagged all 19 existing `features/*/api.ts` swap-seam files as violations of the boundary. These files ARE the intended callers of `api/client.ts` (they wrap `mockResponse()` behind TanStack Query hooks).
- **Fix:** Removed `./src/features/**` from the zone `target`; kept only `./src/pages/**`, `./src/layouts/**`, `./src/components/**`
- **Files modified:** `apps/admin-app/eslint.config.js`
- **Verification:** `eslint .` passes with 0 errors; the boundary still prevents pages/layouts/components from importing directly
- **Committed in:** `93917556` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (2 x Rule 1 — Bug)
**Impact on plan:** Both fixes necessary for correctness; no scope creep. Boundary intent preserved.

## Issues Encountered

- **Pre-existing `admin-web` typecheck failure** (`apps/admin-web vitest.config.ts(13,3): error TS2578: Unused '@ts-expect-error' directive`): confirmed pre-existing before our changes by verifying the failure reproduced from the prior commit. Out of scope per deviation scope boundary — logged as deferred item.

## Known Stubs

None — this plan creates no UI components and wires no data sources.

## Next Phase Readiness

- `@clubcore/admin-app` is a full workspace citizen: `typecheck`, `lint`, `test`, `build` all green under pnpm
- `pnpm install --frozen-lockfile` succeeds against the committed lockfile
- Vite dev proxy ready for plan 100-02 (transport seam — staffRequest + CSRF)
- ESLint boundary and VITE_API_MODE chokepoint established — plan 100-02 auth domain is exempt, other domains enforced
- CI job will run in parallel on every PR push

---
*Phase: 100-foundation-authentication*
*Completed: 2026-06-13*
