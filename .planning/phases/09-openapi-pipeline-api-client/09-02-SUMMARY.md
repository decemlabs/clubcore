---
phase: 09-openapi-pipeline-api-client
plan: 02
subsystem: api-client
tags: [openapi, openapi-typescript, fetch, csrf, single-flight, typescript, monorepo]

# Dependency graph
requires:
  - phase: 09-openapi-pipeline-api-client
    plan: 01
    provides: apps/backend/openapi.json (1376 lines, 11 paths) — input to openapi-typescript codegen
  - phase: 04-auth-foundations-cookie-rbac-primitives
    provides: sportzal_csrf cookie name + X-CSRF-Token header convention (Phase 6 D-04 mirror in fetcher)
  - phase: 06-rbac-wiring-parity-tests
    provides: server _SAFE_METHODS short-circuit (mirrored client-side as isMutating gate)
  - phase: 07-telegram-otp-channel
    provides: /auth/telegram/{start,status,verify} endpoints (3 of 8 auth-exempt paths)
provides:
  - Library-mode @sportzal/api-client (real package.json + tsconfig + src/*) — the Phase 1 placeholder is gone
  - Generated and committed packages/api-client/src/schema.d.ts (949 lines; openapi-typescript v7.13.0 output; 11 paths surfaced)
  - request<P,M>(method, path, init?) sole public function (D-10) with framework-agnostic single-flight refresh + CSRF injection + typed errors
  - ApiError class mirroring backend AppError envelope (D-12)
  - Public barrel exporting exactly { request, ApiError, type paths, type components }
affects: [09-03 (CI drift-gate diffs schema.d.ts; codegen byte-stability validated here unblocks the gate), 10 (admin-web FE-01 wiring imports request + ApiError + paths from this package)]

# Tech tracking
tech-stack:
  added:
    - openapi-typescript@^7.13.0 (devDep — TypeScript codegen from openapi.json)
    - typescript@~5.7.2 (devDep — exact match to admin-web pin per CLAUDE.md)
  patterns:
    - "Module-scoped single-flight Promise (`let inFlightRefresh: Promise<Response> | null = null`) with .finally() reset — no Subject/EventEmitter (D-A4)"
    - "Framework-agnostic transport: zero imports of @tanstack/react-router, no window.location, no /login literal (D-A2)"
    - "Synthetic client-side error codes (`session_expired`, `network_error`, `unknown_error`) distinct from server-issued codes — pass-through for /auth/* paths (D-A1, D-A3)"
    - "Workspace-source-as-public-surface: package.json main/types/exports point at ./src/index.ts; Vite transpiles consumer-side"
    - "Library-mode tsconfig: composite + declaration + emitDeclarationOnly + outDir=dist; strict block copied verbatim from admin-web"

key-files:
  created:
    - packages/api-client/tsconfig.json
    - packages/api-client/src/errors.ts
    - packages/api-client/src/fetcher.ts
    - packages/api-client/src/index.ts
    - packages/api-client/src/schema.d.ts
    - packages/api-client/.gitignore
  modified:
    - packages/api-client/package.json
    - packages/api-client/README.md
    - pnpm-lock.yaml

key-decisions:
  - "schema.d.ts committed to git (D-07) — explicit deviation from REQUIREMENTS API-05 wording 'gitignored locally'. Without commit, Plan 03 git-diff drift-gate is meaningless. Plan 03 Task 5 should reframe REQUIREMENTS.md API-05 to 'committed' or schedule wording-update in backlog."
  - "Public surface kept minimal — only `request` + `ApiError` + `type paths` + `type components` (D-10). Convenience wrappers (get/post/patch/del) deferred to backlog to keep transport unobtrusive."
  - "Single-flight refresh implemented as plain module-scoped Promise (D-A4). No reactive primitives, no class instance — easiest to reason about and unit-testable in jsdom without router/window mocks."
  - "Fetcher remains pure transport (D-A2). Redirect-on-session_expired logic deliberately punted to admin-web Phase 10 FE-05 (QueryClient onError + router error boundary)."
  - "Auth-exempt path list is a static const array of 8 paths (D-A3): /api/v1/auth/{login,refresh,me,logout,logout-all,telegram/start,telegram/status,telegram/verify}. Verified against apps/backend/app/modules/auth/router.py."
  - "RequestInitWithBody.body is `unknown` (not `BodyInit`); fetcher JSON.stringify's it and sets Content-Type:application/json on mutating methods. Aligns with backend ContractModel JSON-only wire format."

patterns-established:
  - "Pattern: pkg/api-client level .gitignore lists dist/ + node_modules/ but NOT schema.d.ts (D-07 contract — Plan 03 drift-gate depends on this)"
  - "Pattern: workspace package exposes ./src/index.ts as public entry without a build step — relies on consumer's bundler (Vite) for transpile"
  - "Pattern: server-mirror constants kept byte-equal as comments cite the server file/line (cookie name 'sportzal_csrf' references app/core/dependencies.py:194)"

requirements-completed: [API-05, API-06]

# Metrics
duration: 5min
completed: 2026-05-03
---

# Phase 9 Plan 02: packages/api-client transport implementation Summary

**Phase 1 placeholder становится реальным transport-пакетом: 949-строчный схема-файл, generic `request<P,M>` с single-flight refresh + CSRF, typed `ApiError` зеркалит backend envelope. `pnpm --filter @sportzal/api-client typecheck` exits 0; codegen byte-stable across reruns — Plan 03 drift-gate готов.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-03T17:29:06Z
- **Completed:** 2026-05-03T17:34Z
- **Tasks:** 4
- **Commits:** 4 atomic commits
- **Files created:** 6 (tsconfig.json, errors.ts, fetcher.ts, index.ts, schema.d.ts, .gitignore)
- **Files modified:** 3 (package.json, README.md, pnpm-lock.yaml)

## Accomplishments

### Final shape of fetcher.ts (LOC, deviation from "~80 LOC" target)

- **Actual LOC:** 179 lines (target was "~80 LOC" — overran by ~2.2x).
- **Reason for overrun:** the original target excluded comments. The realised file:
  - ~50 lines of doc-comments (top-doc, decision callouts, contract pointers — load-bearing for downstream maintainers).
  - ~129 lines of code split between `parseErrorBody`, `request`, `finishResponse`, refresh handling, retry path, CSRF reread post-refresh.
  - The retry path alone (post-refresh CSRF reread + second fetch + max-1 401 short-circuit) is ~25 lines and was implicit in the planner's mental model but explicit in code.
- **Functional surface remains exactly D-10:** one exported function (`request`), one exported error class re-exported from index, one auxiliary `RequestInitWithBody` interface for typing the optional `body: unknown`. No convenience wrappers.

### Confirmation of D-A1..D-A4 grep gates passing

| Gate | Decision | Grep target | Match count | Status |
|------|----------|-------------|-------------|--------|
| Single-flight Promise present | D-A4 | `inFlightRefresh` in fetcher.ts | 5 | PASS |
| Synthetic session_expired emitted | D-A1 + D-A4 | `session_expired` in fetcher.ts | 4 (refresh-throw, refresh-non-2xx, retry-401, network-during-retry path uses different code) | PASS (≥3 required) |
| CSRF cookie name byte-equal to server | D-11 | `sportzal_csrf` in fetcher.ts | 3 (initial + post-refresh + comment) | PASS (≥1 required) |
| X-CSRF-Token header inject | D-11 | `X-CSRF-Token` in fetcher.ts | 4 (initial set + retry set + retry delete + comment) | PASS (≥1 required) |
| 8 auth-exempt paths + refresh URL | D-A3 + D-A4 | `/api/v1/auth/` in fetcher.ts | 10 (8 in const array + refresh URL + retry-related comment ref via `/api/v1/auth/login` etc) | PASS (≥9 required) |
| No framework imports (D-A2 negative grep) | D-A2 | `@tanstack/react-router` OR `window\.location` OR `'/login'` | 0 | PASS (must be 0) |
| No console.log (T-09-11 STRIDE) | threat | `console\.` in fetcher.ts | 0 | PASS (must be 0) |
| No convenience wrappers exported | D-10 | `export (interface|const|function) (get|post|patch|put|del|delete)` | 0 | PASS (must be 0) |

### Codegen output size + paths-count

- **schema.d.ts:** 29,613 bytes / 949 lines.
- **Paths surfaced:** 11 (matches Plan 01 SUMMARY's 11-paths claim from openapi.json) — `/api/v1/auth/{login,refresh,me,logout,logout-all,telegram/start,telegram/status,telegram/verify}` + `/healthz` + clients routes (2 paths).
- **Generator:** openapi-typescript v7.13.0.
- **Header:** auto-generated banner `* This file was auto-generated by openapi-typescript.\n * Do not make direct changes to the file.` (matches v7's standard preamble — no postprocess needed).

### Codegen byte-stability confirmation (W-01 fix verified)

- Ran `pnpm --filter @sportzal/api-client codegen` twice with `cp` between runs.
- `diff -q packages/api-client/src/schema.d.ts /tmp/schema-first.d.ts` exited 0 (silent — files identical).
- Ran a third invocation as a final sanity check after Task 3 typecheck — also byte-identical.
- **Conclusion:** Plan 03 CI step `git diff --exit-code packages/api-client/src/schema.d.ts` will not false-positive on deterministic regen.

### REQUIREMENTS API-05 deviation logged

- **Wording in REQUIREMENTS.md:** "src/schema.d.ts (gitignored locally)".
- **What Phase 9 actually does (D-07):** schema.d.ts is committed to git.
- **Why:** without tracking, `git diff --exit-code` (Plan 03 API-07 drift-gate) is silent on untracked files — the entire CI gate would be a no-op.
- **Action item for Plan 03 Task 5:** reframe REQUIREMENTS API-05 acceptance text from 'gitignored locally' to 'committed; CI re-runs codegen and asserts no diff'. If Plan 03 does not have the bandwidth, file as backlog. Phase 9 SUMMARY (the parent phase summary) must surface this so the orchestrator routes the followup.

## Task Commits

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Package skeleton (tsconfig + package.json + pnpm install) | `3304d10` | packages/api-client/tsconfig.json, packages/api-client/package.json, pnpm-lock.yaml |
| 2 | ApiError class + generated schema.d.ts (committed) | `80f36ae` | packages/api-client/src/errors.ts, packages/api-client/src/schema.d.ts |
| 3 | fetcher.ts (single-flight + CSRF + typed errors) + barrel index.ts | `64b9db3` | packages/api-client/src/fetcher.ts, packages/api-client/src/index.ts, packages/api-client/.gitignore |
| 4 | README rewrite (drop Phase 1 placeholder framing) | `18e7642` | packages/api-client/README.md |

## Decisions Made

- **Library mode without build step.** package.json `main`/`types`/`exports` point straight at `./src/index.ts`. Vite (admin-web Phase 10 consumer) transpiles workspace dependencies natively, so no compile step is required. tsconfig still has `composite: true` + `declaration: true` + `emitDeclarationOnly: true` because the admin-web project-references graph (Phase 10) may use it, and emitting `.d.ts`-only avoids leaking JS noise into `dist/`.
- **CSRF reread after refresh.** On the post-refresh retry, the fetcher *re-reads* `sportzal_csrf` from `document.cookie` because Phase 4 D-26 rotates the CSRF cookie on every refresh. Reusing the original header would 403 with `csrf_mismatch`. The retry path explicitly `delete retryHeaders['X-CSRF-Token']` if the new cookie is absent rather than carrying over the old value.
- **Generic signature accepts `keyof paths` literals.** `request<P extends keyof paths, M extends keyof paths[P] & string>(method, path)`. Compile-time gate prevents callers from passing arbitrary URL strings; T-09-08 (path injection) is bounded by the generated schema. Runtime is permissive (TS erases types) but realistic consumers go through typecheck before bundling.
- **`.gitignore` added at package level.** Lists only `dist/` and `node_modules/`. **Does NOT** list `schema.d.ts` — a regression here would silently break Plan 03's drift-gate. The README explicitly calls this out.

## Deviations from Plan

### None — plan executed exactly as written.

All 4 tasks completed without auto-fixes. The only "judgement call" was the per-package `.gitignore` (which the plan didn't mandate but didn't forbid either) — added defensively so `dist/tsconfig.tsbuildinfo` (a side-effect of `tsc --noEmit` with `composite: true`) doesn't end up tracked. Verified by negative-grep that the new gitignore does not exclude `schema.d.ts` (D-07).

### Pre-existing item carried forward (not a deviation)

- **Plan 01 SUMMARY mentions API-01 only as completed.** This plan delivers API-05 + API-06. Plan 03 will deliver API-02 + API-07. The ROADMAP/REQUIREMENTS update for these requirement IDs is the orchestrator's responsibility (per the spawn instructions, this executor does NOT update STATE.md / ROADMAP.md / REQUIREMENTS.md — wave-completion handles tracking).

## Issues Encountered

- **pnpm install retried 4 transient ECONNRESET errors** during `pnpm install` (registry.npmjs.org throttling). All retries succeeded; final state: `Done in 1m 39s`. No action needed.
- **`tsc --noEmit` with `composite: true` still emits `dist/tsconfig.tsbuildinfo`.** This is expected TypeScript behavior — the tsbuildinfo cache is written even with `--noEmit`. Mitigated by adding `dist/` to `packages/api-client/.gitignore`.

## User Setup Required

None.

## Next Plan Readiness

- **Plan 03 input ready:** `packages/api-client/src/schema.d.ts` is committed (the drift-gate baseline) and codegen is byte-stable across reruns. The CI step `pnpm --filter @sportzal/api-client codegen && git diff --exit-code packages/api-client/src/schema.d.ts` is fully implementable.
- **Phase 10 (admin-web wiring) input ready:** `import { request, ApiError, type paths } from '@sportzal/api-client'` will resolve correctly once admin-web declares the `workspace:*` dependency (Plan 03 will add this alongside the `predev` hook per D-08, OR Phase 10 Plan 01 — see deferred-items below).
- **Phase 9 SC#3 unblocked:** drift-gate becomes feasible.
- **Phase 9 SC#4 fully delivered:** `request<P, M>` exists, `credentials: 'include'`, single-flight refresh on non-/auth/* 401, retry-once, typed `ApiError` on failures.

## Deferred Items (for Plan 03 to pick up)

- **`apps/admin-web/package.json` updates** (D-08, CONTEXT line 122-123): add `predev: pnpm --filter @sportzal/api-client codegen` script and `@sportzal/api-client: workspace:*` dependency. Plan 02 deliberately did not touch admin-web (CLAUDE.md "frontend integrity" — no edits to apps/admin-web internals in Phase A; Phase 9 explicitly defers admin-web wiring to Phase 10). Plan 03 is the right place because it lands the CI workflow that needs the `predev` hook to be in place. If Plan 03 is purely CI-only (no admin-web changes per D-02), schedule for Phase 10 Plan 01.
- **REQUIREMENTS.md API-05 wording update** ("gitignored locally" → "committed; CI re-runs codegen and asserts no diff"). See "REQUIREMENTS API-05 deviation logged" above.

## Self-Check: PASSED

- File `packages/api-client/tsconfig.json` — FOUND
- File `packages/api-client/package.json` — FOUND (modified)
- File `packages/api-client/src/errors.ts` — FOUND
- File `packages/api-client/src/fetcher.ts` — FOUND (179 LOC)
- File `packages/api-client/src/index.ts` — FOUND
- File `packages/api-client/src/schema.d.ts` — FOUND (29,613 bytes; 949 lines; 11 paths)
- File `packages/api-client/.gitignore` — FOUND
- File `packages/api-client/README.md` — FOUND (modified; placeholder framing dropped)
- Commit `3304d10` (Task 1) — FOUND
- Commit `80f36ae` (Task 2) — FOUND
- Commit `64b9db3` (Task 3) — FOUND
- Commit `18e7642` (Task 4) — FOUND
- `pnpm --filter @sportzal/api-client typecheck` — exits 0
- `pnpm --filter @sportzal/api-client codegen` — exits 0; byte-stable across consecutive runs
- Negative grep: no `@tanstack/react-router` / `window.location` / `'/login'` in fetcher.ts — 0 matches
- Negative grep: no `console.*` in fetcher.ts — 0 matches
- Positive grep: `inFlightRefresh` (5) / `session_expired` (4) / `sportzal_csrf` (3) / `/api/v1/auth/` (10) — all gates pass

---
*Phase: 09-openapi-pipeline-api-client*
*Completed: 2026-05-03*
