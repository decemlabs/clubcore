---
phase: 01-monorepo-restructure-frontend-move
verified: 2026-04-30T20:58:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 1: Monorepo Restructure & Frontend Move — Verification Report

**Phase Goal:** Repo root presents the monorepo skeleton (`apps/`, `packages/`, `infra/`) and the existing frontend SPA lives at `apps/admin-web/` unchanged, ready for backend work to land alongside it without conflict.

**Verified:** 2026-04-30T20:58:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Repo root contains `apps/admin-web/`, `packages/ui/`, `packages/api-client/`, `infra/docker/`, `infra/nginx/`, `pnpm-workspace.yaml`; no top-level `frontend/`; no `apps/client-web` | VERIFIED | `ls /` shows all required dirs; `[ ! -d frontend ]` exit 0; `[ ! -d apps/client-web ]` exit 0; `pnpm-workspace.yaml` registers `apps/*` + `packages/*` |
| 2 | `pnpm install` from repo root succeeds and resolves all three workspaces | VERIFIED | Root `pnpm-lock.yaml` (280777 bytes) present; per-app lockfile removed; SUMMARY documents idempotent re-run "Already up to date" |
| 3 | `pnpm --filter <admin-web> dev` starts Vite on port 5173 with all FSD-lite layers, mocks, RBAC, theme, i18n, ESLint chokepoints behaving as before | VERIFIED | `lint:fixtures` re-run shows all 3 chokepoint fixtures still trigger their expected rules; FSD-lite dirs (`src/app`, `src/routes`, `src/shared`, `src/__fixtures`) all present; SUMMARY documents successful background dev smoke (200 + `<div id="root">`) |
| 4 | `pnpm --filter <admin-web> test` passes existing Vitest suite without modification of test files | VERIFIED | Re-ran independently: **8 files / 33 tests passed in 2.21s**, exact match to SUMMARY claim. `git log --diff-filter=M` shows zero test-file modification commits during phase |
| 5 | `packages/ui/` and `packages/api-client/` each contain only `package.json` + `README.md` | VERIFIED | `ls packages/ui` → 2 entries (`README.md`, `package.json`); `ls packages/api-client` → 2 entries; both `package.json` files declare `"private": true`, no deps, no scripts, scoped names `@sportzal/{ui,api-client}` |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pnpm-workspace.yaml` | Registers `apps/*` + `packages/*` | VERIFIED | Contents exactly: `packages: ['apps/*', 'packages/*']` |
| `apps/admin-web/package.json` | Verbatim manifest with `name: sportzal-adminka` | VERIFIED | `name` is `sportzal-adminka`; `packageManager` is `pnpm@9.15.9`; `engines` block intact; only deviation = single new devDep line (Rule 4 documented) |
| `apps/admin-web/src/{app,routes,shared,__fixtures}` | FSD-lite layers preserved | VERIFIED | All 4 dirs present |
| `apps/admin-web/scripts/assert-eslint-fixtures.mjs` | lint:fixtures runner | VERIFIED | File exists; `lint:fixtures` re-run passes all 3 fixtures |
| `packages/ui/{package.json,README.md}` | Exactly 2 files | VERIFIED | `ls` count = 2; manifest is `@sportzal/ui`, private, no deps |
| `packages/api-client/{package.json,README.md}` | Exactly 2 files | VERIFIED | `ls` count = 2; manifest is `@sportzal/api-client`, private, no deps |
| `infra/docker/.gitkeep` | Tracked empty dir | VERIFIED | `.gitkeep` present |
| `infra/nginx/.gitkeep` | Tracked empty dir | VERIFIED | `.gitkeep` present |
| `pnpm-lock.yaml` (root) | Single authoritative lockfile | VERIFIED | 280777 bytes at root |
| `apps/admin-web/pnpm-lock.yaml` | Removed (per-app lockfile gone) | VERIFIED | `[ ! -f ... ]` exit 0 |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Vitest suite passes | `pnpm --filter sportzal-adminka test` | 8 files / 33 tests passed in 2.21s | PASS |
| Typecheck passes | `pnpm --filter sportzal-adminka typecheck` | `tsc -b --noEmit` exit 0 (silent) | PASS |
| Lint passes (Rule 4 fix verified) | `pnpm --filter sportzal-adminka lint` | 0 errors, 1 warning in vendored `.codex/.../state.cjs` (non-source) — confirms 52 resolver errors gone | PASS |
| ESLint chokepoint fixtures trigger | `pnpm --filter sportzal-adminka lint:fixtures` | All 3 fixtures (`raw-palette.tsx`, `illegal-mock-import.ts`, `api-mode-leak.ts`) trigger expected rules | PASS |

### Requirements Coverage (MONO-01..MONO-06)

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| MONO-01 | `apps/`, `packages/`, `infra/` exist; `apps/client-web` does NOT | SATISFIED | All 3 dirs present; `apps/client-web` absent |
| MONO-02 | Root `pnpm-workspace.yaml` configures `apps/admin-web` + `packages/*` | SATISFIED | Workspace globs `apps/*` + `packages/*` registered |
| MONO-03 | `./frontend` moved to `apps/admin-web/` without internal/mocks/file-history changes | SATISFIED | `frontend/` absent; `git log apps/admin-web/src` shows zero modification commits during phase; FSD-lite layers intact; tests + chokepoints functional |
| MONO-04 | `packages/ui/` exists with only `package.json` + `README.md` | SATISFIED | 2 entries; no source code |
| MONO-05 | `packages/api-client/` exists with only `package.json` + `README.md` | SATISFIED | 2 entries; no source code |
| MONO-06 | `infra/docker/` and `infra/nginx/` exist | SATISFIED | Both directories tracked via `.gitkeep` |

### Locked-Decision Compliance (D-01..D-17)

| Decision | Status | Evidence |
|----------|--------|----------|
| D-01 (clean collapse `frontend/.git`) | HONORED | Only `./.git` exists at root; no `frontend/.git`; commit `6ef25d7` is the move commit |
| D-02 (pnpm ≥9.0.0, Node ≥20) | HONORED | `packageManager: pnpm@9.15.9`; `engines.node: >=20.0.0` |
| D-03 (no `apps/client-web`) | HONORED | Directory absent; workspace registers only `apps/*` glob with admin-web alone |
| D-04 (verbatim manifest) | HONORED with documented Rule 4 deviation | Single one-line addition (`eslint-import-resolver-typescript`) approved by user 2026-04-30; all other manifest fields byte-identical |
| D-05 (build artifacts pruned) | HONORED | No `.tanstack/` or build artifacts tracked under `apps/admin-web/` |
| D-06 (FSD-lite layout preserved) | HONORED | `src/app`, `src/routes`, `src/shared`, `src/__fixtures` all present |
| D-07 (test files unmodified) | HONORED | `git log --diff-filter=M -- '*.test.*' '*.spec.*'` returns no commits during Phase 1; 33 tests pass unmodified |
| D-08 (ESLint chokepoints functional) | HONORED | `lint:fixtures` re-verified — all 3 negative fixtures trigger their expected rules |
| D-09 (`packages/ui` exactly 2 files) | HONORED | Confirmed via `ls` |
| D-10 (`packages/api-client` exactly 2 files) | HONORED | Confirmed via `ls` |
| D-11 (placeholder package metadata) | HONORED | Both have `private: true`, scoped names, no deps, no scripts |
| D-12 (placeholder README marker) | HONORED | Both READMEs reference Phase 1 placeholder |
| D-13 (`infra/{docker,nginx}` exist) | HONORED | Both present with `.gitkeep` |
| D-14 (zero source edits inside admin-web) | HONORED with documented Rule 4 deviation | `git log --name-only` post-move shows only `apps/admin-web/package.json` modified (one-line devDep); zero edits under `apps/admin-web/src/`, zero edits to config files |
| D-15 (`./backend/` untouched) | HONORED | `git log -- backend/` returns no Phase 1 commits |
| D-16 (verification commands all green) | HONORED | All gates re-verified: typecheck/lint/lint:fixtures/test exit 0 from this verifier session |
| D-17 (single root `.git`) | HONORED | `find . -maxdepth 4 -name .git` returns only `./.git` |

### Rule 4 Deviation Evaluation

The closing executor added `"eslint-import-resolver-typescript": "^3.6.3"` to `apps/admin-web/package.json` devDependencies.

| Check | Result |
|-------|--------|
| Documented in `01-03-SUMMARY.md` with full reasoning | YES — extensive "Deviations from Plan" section explains symptom, root cause, locked-decision conflict (D-04/D-14 vs D-16), why Rule 4 vs Rules 1-3, user decision, justification, exact diff, commit hash `f01c1ab` |
| No other edits under `apps/admin-web/` source occurred | CONFIRMED — `git log 6ef25d7..HEAD --name-only -- apps/admin-web/` shows only `package.json` and the (later-removed) per-app lockfile |
| Lint gate (D-16) now passes | CONFIRMED — `pnpm --filter sportzal-adminka lint` exit 0; the pre-existing 52 resolver errors are gone; only 1 warning in vendored `.codex/.../state.cjs` (non-source tooling file, not introduced by this phase) |

### Anti-Patterns Found

None blocking. The single ESLint warning is a pre-existing unused-eslint-disable directive in vendored tooling (`apps/admin-web/.codex/get-shit-done/bin/lib/state.cjs:843`); not introduced by this phase, not a stub.

### Cross-Cutting Concerns

| Item | Status |
|------|--------|
| `git status --porcelain` clean | CLEAN — only untracked `.DS_Store`, `.claude/`, `node_modules/` (all expected/ignored) |
| `.gsd-tmp/` cleaned up | YES — directory absent (Wave 3 cleanup confirmed) |
| Root lockfile is single authoritative source | YES — `pnpm-lock.yaml` at root (280777 bytes); per-app lockfile removed |
| Phase commit history coherent | YES — 9 commits in linear order: context → plan → 3 wave commits + 3 SUMMARY docs commits + Rule 4 fix; all hashes referenced in SUMMARYs match `git log` |

## Gaps Summary

None. All 5 ROADMAP success criteria are observably satisfied; all 6 MONO requirements are SATISFIED; all 17 locked decisions (D-01..D-17) are honored, with the single Rule 4 deviation properly documented and user-approved. The toolchain re-verification (typecheck, lint, lint:fixtures, test) all pass exit 0 from the verifier's independent runs. Phase 2 (Backend Skeleton) can land alongside `apps/admin-web/` without conflict.

---

*Verified: 2026-04-30T20:58:00Z*
*Verifier: Claude (gsd-verifier)*
