---
phase: 13
plan: 03
subsystem: api-client + admin-web/http-services + ci
tags: [housekeeping, fetcher, query-params, vitest, ci, typescript]
requirements-completed: [housekeeping]
roadmap-success-criteria-closed: [SC-13-2, SC-13-5]
dependency-graph:
  requires: []
  provides:
    - "@sportzal/api-client RequestInitWithBody.query (typed query-string field)"
    - "@sportzal/api-client vitest test runner + regression-test suite"
    - "CI invocation: pnpm -F @sportzal/api-client test"
  affects:
    - "apps/admin-web/src/shared/api/services/http/auth.ts (drops as never path cast + TODO)"
    - "apps/admin-web/src/shared/api/services/http/clients.ts (drops URLSearchParams string-build + all as never casts)"
tech-stack:
  added:
    - "vitest ~2.1.8 — devDependency on packages/api-client (matches admin-web pin)"
  patterns:
    - "Typed query field on fetcher RequestInitWithBody composes with path params"
    - "Caller code passes plain Record<string, string|number|boolean> instead of building URL strings"
    - "fetcher.test.ts uses node env + globalThis.fetch stub (no jsdom required)"
key-files:
  created:
    - packages/api-client/vitest.config.ts
    - packages/api-client/src/fetcher.test.ts
  modified:
    - packages/api-client/src/fetcher.ts
    - packages/api-client/package.json
    - apps/admin-web/src/shared/api/services/http/auth.ts
    - apps/admin-web/src/shared/api/services/http/clients.ts
    - .github/workflows/ci.yml
    - pnpm-lock.yaml
decisions:
  - "Typed query field accepts Record<string, string | number | boolean> — booleans coerced via String() to match URLSearchParams' standard runtime behaviour."
  - "appendQuery() defensively handles a pre-existing '?' in the URL with an '&' separator even though interpolatePath never produces one — keeps the helper composable if a future caller passes a literal '?'."
  - "Init-level `as never` casts on clients.{get,update,remove} were removable too (bonus cleanup) — TypeScript inference for openapi-fetch typed paths now resolves cleanly with the post-Task-1 fetcher signature, so all three sites are typed end-to-end."
  - "Tests written with `as any` rather than `as never` casts on the path/method args because the test exercises runtime behaviour (URL building) rather than the typed surface — allows passing arbitrary literal paths like '/x' that are not in the openapi schema."
metrics:
  duration: "~25 minutes"
  completed: 2026-05-05
  tasks-completed: 3
  files-changed: 7
  tests-added: 8
---

# Phase 13 Plan 03: Typed Query Field + Vitest in api-client Summary

Eliminated the `as never` query-string casts in admin-web HTTP services by adding a typed `query?: Record<string, string | number | boolean>` field to `@sportzal/api-client`'s `RequestInitWithBody`, and stood up a real vitest runner inside the package with permanent regression tests wired into CI.

## What Changed

### Task 1 — Typed query field in fetcher (commit `afe40f7`)
- Extended `RequestInitWithBody` in `packages/api-client/src/fetcher.ts` with a typed `query?` field.
- Added `appendQuery(url, query)` helper that serializes via `URLSearchParams` and skips the `?` suffix on undefined/empty inputs.
- Wired it into `request()` (composes with `interpolatePath`) and extended the destructuring so `query` is stripped from the `RequestInit` forwarded to `fetch()`.

### Task 2 — Drop `as never` casts in admin-web HTTP services (commit `c96983a`)
- `auth.telegramStatus`: switched to `request('get', '/api/v1/auth/telegram/status', { query: { token } })`. Path-level `as never` cast and the multi-line TODO block are gone.
- `clients.list`: replaced URLSearchParams string-build pattern with `{ query: q }` field; path-level `as never` cast removed.
- Bonus cleanup: init-level `as never` casts on `clients.get`, `clients.update`, `clients.remove` were also safely removable — typecheck passes without them, so all three sites now flow through the typed openapi paths surface end-to-end. (See deviation below.)

### Task 3 — Vitest + regression test + CI (commit `6eeecc6`)
- Added `vitest ~2.1.8` devDep + `test` / `test:watch` scripts to `packages/api-client/package.json` (matches `admin-web` pin).
- Created `packages/api-client/vitest.config.ts` with node env, no jsdom (the fetcher is framework-agnostic).
- Authored `packages/api-client/src/fetcher.test.ts` with 8 tests:
  - 6 query-serialization regression tests (Phase 13 SC #2): undefined / empty / typed values / URL-encoded whitespace / params+query composition / `query` field stripped from RequestInit.
  - 2 error-envelope regression tests (CR-01/CR-02): JSON body unwraps to `ApiError`, and 401 from `/api/v1/auth/*` does NOT trigger a refresh attempt (D-A3).
- Added `pnpm -F @sportzal/api-client test` step to `.github/workflows/ci.yml` Frontend job after the workspace `-r test` invocation.

## Verification

| Check | Result |
| --- | --- |
| `pnpm -F @sportzal/api-client typecheck` | exit 0 |
| `pnpm -F @sportzal/api-client test` | 8 passed |
| `pnpm -F sportzal-adminka typecheck` | exit 0 |
| `pnpm -F sportzal-adminka lint` | 0 errors (2 pre-existing warnings unrelated to this plan) |
| `pnpm -F sportzal-adminka test` | 108 passed |
| `grep -c 'as never' apps/admin-web/src/shared/api/services/http/auth.ts` | 0 |
| `grep -c 'as never' apps/admin-web/src/shared/api/services/http/clients.ts` | 0 |
| `grep -c 'URLSearchParams' apps/admin-web/src/shared/api/services/http/clients.ts` | 0 |
| `grep -c 'TODO' apps/admin-web/src/shared/api/services/http/auth.ts` | 0 |
| `grep -c '@sportzal/api-client' .github/workflows/ci.yml` | 3 (codegen + drift gate + new test step) |

## Deviations from Plan

### 1. [Rule 2 — Auto-add critical cleanup] Removed init-level `as never` casts in clients.{get,update,remove}

- **Found during:** Task 2 (Step C — the plan's "bonus cleanup if free" branch).
- **Issue:** The plan documented the init-level `as never` casts as out-of-scope but flagged that they may be removable if typecheck stays clean.
- **Decision:** Removed all three. After Task 1 widened the fetcher signature, openapi-fetch's path inference resolves cleanly without the casts. `pnpm typecheck` is green; admin-web tests still pass.
- **Files modified:** `apps/admin-web/src/shared/api/services/http/clients.ts` (lines for `get`, `update`, `remove`).
- **Commit:** `c96983a` (rolled into Task 2).
- **Rationale:** Strictly tighter type safety with no runtime change; leaving them would have forced future readers to wonder why some paths cast and others don't.

### 2. [Acceptance criterion literal] `grep -c "query?: Record<string, string | number | boolean>" packages/api-client/src/fetcher.ts` returns 2 (plan expected 1)

- **Found during:** Task 1 verify.
- **Issue:** The plan's acceptance criterion expected `1` match. Actual count is `2`: one for the field declaration on `RequestInitWithBody`, one for the `appendQuery()` helper signature that consumes the same shape.
- **Decision:** Kept both — the helper signature reusing the exact same record literal is desirable consistency, not duplication. The criterion's intent (the typed field exists in the public surface) is satisfied.
- **Files:** `packages/api-client/src/fetcher.ts` lines 114 and 130.

### 3. [Build infra] Generated routeTree.gen.ts via `pnpm vite build` to unblock typecheck

- **Found during:** Task 2 verify.
- **Issue:** Worktree had no `apps/admin-web/src/routeTree.gen.ts` — the file is normally regenerated by the Vite dev server on `pnpm dev`. Initial `pnpm typecheck` failed with 14 unrelated routing errors.
- **Fix:** Ran `pnpm vite build` once to regenerate the file. Subsequent typechecks pass.
- **Note:** This is a pre-existing worktree-bootstrap condition, not a regression introduced by this plan. Not committed (the file is gitignored per Phase 1 conventions).

## Key Decisions

- **Boolean coercion via `String(v)`:** Plan-prescribed. `URLSearchParams.set('c', 'true')` is what the backend sees; backend query-param decoders (Pydantic v2 `bool`) accept `'true' | 'false' | '1' | '0'` etc. — matches the existing convention.
- **Defensive `?` vs `&` separator in `appendQuery`:** Even though `interpolatePath` cannot produce a `?`, the helper handles both because it's called with a string output that may, in the future, come from a caller-built URL. Cheap defensive code; no measurable cost.
- **Test casts use `as any`, not `as never`:** Tests need to pass arbitrary literal paths like `'/x'` that aren't in the generated openapi `paths` map. `as any` is conventional for "we're testing runtime behaviour, not types" and a top-of-file `eslint-disable @typescript-eslint/no-explicit-any` makes the intent explicit.

## Roadmap Success Criteria Closed

- **Phase 13 SC #2** — typed `query` field added; admin-web HTTP services use it; TODO comment + path-level `as never` casts gone.
- **Phase 13 SC #5** — vitest installed; permanent regression test for query serialization (and the CR-01/CR-02 throwaway tests promoted to permanent); CI runs `pnpm -F @sportzal/api-client test`.

## Threat Flags

None — no new security-relevant surface introduced. The change reduces attack surface marginally (typed query serialization replaces hand-written URL string concatenation, removing one class of injection-shaped bug from the future-modification surface).

## Self-Check: PASSED

- ✅ `packages/api-client/src/fetcher.ts` modified — verified (commit `afe40f7`)
- ✅ `apps/admin-web/src/shared/api/services/http/auth.ts` modified — verified (commit `c96983a`)
- ✅ `apps/admin-web/src/shared/api/services/http/clients.ts` modified — verified (commit `c96983a`)
- ✅ `packages/api-client/package.json` modified — verified (commit `6eeecc6`)
- ✅ `packages/api-client/vitest.config.ts` created — verified (commit `6eeecc6`)
- ✅ `packages/api-client/src/fetcher.test.ts` created — verified (commit `6eeecc6`)
- ✅ `.github/workflows/ci.yml` modified — verified (commit `6eeecc6`)
- ✅ Commits `afe40f7`, `c96983a`, `6eeecc6` exist in `git log`
