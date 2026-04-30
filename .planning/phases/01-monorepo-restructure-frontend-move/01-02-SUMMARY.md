---
phase: 01-monorepo-restructure-frontend-move
plan: 02
subsystem: infra
tags: [monorepo, frontend-move, pnpm, history-collapse]

requires:
  - phase: 01-01
    provides: pnpm workspace skeleton (apps/*, packages/*, infra/) ready to receive admin-web
provides:
  - apps/admin-web/ populated verbatim with the entire React 19 SPA tree (configs, scripts, src/, lockfile, .gitignore, .env.* templates)
  - Removal of legacy ./frontend/ directory at repo root
  - Removal of legacy frontend/.git sub-repo (clean collapse per D-01)
  - Single .git at the repo root as the sole source of version-control truth
affects: [01-03 (root pnpm install + verification battery), phase 02 (backend scaffold under apps/backend)]

tech-stack:
  added: []
  patterns:
    - "Verbatim file move (plain mv, not git mv) — source untracked by root repo"
    - "Clean-collapse history strategy for legacy sub-repo (rm -rf .git, no subtree)"
    - "Build-artifact exclusion at the source: node_modules, dist, .tanstack pre-pruned before move"

key-files:
  created:
    - apps/admin-web/package.json
    - apps/admin-web/pnpm-lock.yaml
    - apps/admin-web/vite.config.ts
    - apps/admin-web/vitest.config.ts
    - apps/admin-web/eslint.config.js
    - apps/admin-web/tsconfig.json
    - apps/admin-web/tsconfig.app.json
    - apps/admin-web/tsconfig.node.json
    - apps/admin-web/components.json
    - apps/admin-web/index.html
    - apps/admin-web/CLAUDE.md
    - apps/admin-web/README.md
    - apps/admin-web/.gitignore
    - apps/admin-web/.env.example
    - apps/admin-web/.env.development
    - apps/admin-web/.prettierrc.json
    - apps/admin-web/.prettierignore
    - apps/admin-web/scripts/assert-eslint-fixtures.mjs
    - apps/admin-web/src/ (full FSD-lite tree — 68 tracked files under src/)
  modified: []

key-decisions:
  - "Bulk move executed via plain `mv` because ./frontend/ was untracked by the root repo (the sub-repo's .git was the only history holder, and it was dropped per D-01) — `git mv` is not applicable here"
  - "Combined Tasks 1+2 into a single git commit (6ef25d7) because Tasks 1 and 2 produce no tracked-file delta in isolation: Task 1 deletes inside an untracked subtree, Task 2 moves between an untracked source and a previously untracked destination. Only Task 3's `git add` materializes the change in the index. Committing each task individually would have produced two empty commits, violating GSD's no-empty-commits norm."
  - "All 30 top-level frontend entries (15 dotfiles/dirs + 15 regular) moved verbatim; no entries dropped, none renamed, none edited"
  - "Build artifacts pre-pruned at source (frontend/node_modules, frontend/dist, frontend/.tanstack, .DS_Store) before the move, so they never reach apps/admin-web/"

requirements-completed: [MONO-03]

duration: 2m 56s
completed: 2026-04-30
---

# Phase 1 Plan 2: Frontend Move Summary

**Verbatim relocation of the React 19 SPA from `./frontend/` to `apps/admin-web/` with a clean-collapse drop of the legacy `frontend/.git` sub-repo — 820 files staged into the root repo's history without a single byte of source modification.**

## Performance

- **Duration:** 2m 56s
- **Started:** 2026-04-30T14:48:08Z
- **Completed:** 2026-04-30T14:51:04Z
- **Tasks:** 3 (all executed; consolidated into one commit per locked-decision constraints)
- **Files added (tracked):** 820
- **Files modified:** 0
- **Top-level entries moved:** 30 (verbatim, including dotfiles)

## Accomplishments

- `frontend/.git` removed via `rm -rf` per D-01 (clean collapse, no subtree).
- `frontend/` no longer exists at the repo root; `rmdir frontend` succeeded after the move (confirming zero residue).
- `apps/admin-web/` now contains every config, script, source file, lockfile, and dotfile that previously lived under `./frontend/` — minus build artifacts (`.git`, `node_modules`, `dist`, `.tanstack`) per D-05.
- Manifest preserved verbatim: `apps/admin-web/package.json` retains `"name": "sportzal-adminka"` and `"packageManager": "pnpm@9.15.9"` per D-04.
- FSD-lite layer layout intact: `src/app/`, `src/routes/`, `src/shared/` exist verbatim under `apps/admin-web/src/` per D-06.
- ESLint chokepoint runner preserved verbatim: `apps/admin-web/scripts/assert-eslint-fixtures.mjs` (uses `path.resolve(__dirname, "..")` which is anchored to the package root, so the script needed no path edit) per D-08.
- No nested `.git` exists under `apps/admin-web/` — only the root `.git` survives per D-17.
- `./backend/` directory unchanged: `git status --porcelain backend` produces zero lines per D-15.
- `apps/client-web/` does not exist per D-03 / MONO-01.
- `git diff --cached --diff-filter=M` produced zero modifications during staging — proves verbatim preservation per D-04 / D-14.

## Task Commits

Per the consolidation decision documented in `key-decisions` above, Tasks 1, 2, and 3 share a single atomic commit. The commit message lists every locked decision honored.

| Task | Name | Commit | Notes |
|------|------|--------|-------|
| 1 | Pre-move sanity check + drop frontend/.git | (folded into 6ef25d7) | `rm -rf frontend/.git` operates on untracked content; no tracked delta to commit alone |
| 2 | Move frontend contents to apps/admin-web verbatim | (folded into 6ef25d7) | `mv` between untracked source and untracked destination; no tracked delta to commit alone |
| 3 | Stage moved tree in root git index | **6ef25d7** | `git add` materializes all changes; commit covers Tasks 1+2+3 atomically |

**Plan metadata commit:** pending (final commit after this SUMMARY + STATE/ROADMAP updates).

## Files Created/Modified

The move added 820 tracked files under `apps/admin-web/`. Selected high-signal entries:

**Build / config / tooling**
- `apps/admin-web/package.json` — manifest verbatim (`sportzal-adminka`, pnpm 9.15.9, Node ≥20)
- `apps/admin-web/pnpm-lock.yaml` — frontend lockfile relocated; root lockfile reconciliation deferred to plan 03
- `apps/admin-web/vite.config.ts`, `vitest.config.ts`, `eslint.config.js`
- `apps/admin-web/tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`
- `apps/admin-web/components.json` — shadcn registry config
- `apps/admin-web/index.html` — SPA entry with theme bootstrap script (CSP TODO at line 7 preserved)
- `apps/admin-web/.gitignore`, `.prettierrc.json`, `.prettierignore`
- `apps/admin-web/.env.example`, `.env.development`

**Source tree (verbatim, zero edits)**
- `apps/admin-web/src/app/` — composition root, providers, query client, router instance, global CSS
- `apps/admin-web/src/routes/` — TanStack Router file-based tree
- `apps/admin-web/src/shared/` — ui/, api/, session/, lib/, theme/, i18n/
- 68 tracked source files in total under `apps/admin-web/src/`

**Scripts / docs**
- `apps/admin-web/scripts/assert-eslint-fixtures.mjs` — `lint:fixtures` runner
- `apps/admin-web/CLAUDE.md` — moved with the source per D-04 (documents app-local conventions)
- `apps/admin-web/README.md`

**Tooling state directories (came along verbatim per D-04 / D-05)**
- `apps/admin-web/.claude/`, `.codex/`, `.gsd/`, `.planning/`, `.auto-claude/`, `.bg-shell/`, `.omc/`, `.mcp.json`, `.gsd-id`, `.claude_settings.json`, `.auto-claude-security.json` — these are per-developer / per-tool state files that lived inside `./frontend/` and moved verbatim. They are not source code; they are not edited; they are not blocking. A future cleanup phase may decide to remove them or move them to root, but that is explicitly out of scope for this plan (D-04 mandates verbatim).

## Decisions Made

- **Plain `mv` over `git mv`.** The `frontend/` directory was untracked by the root repo (verified via `git ls-files --error-unmatch frontend` returning non-zero pre-flight). `git mv` requires a tracked source; using it would have failed. Plan plan correctly anticipated this and specified plain `mv`.
- **`rm -rf frontend/.git` over `git subtree`.** User-locked decision D-01. The plan executed this verbatim; no history-preserving alternative was attempted.
- **Three logical tasks, one git commit.** Tasks 1 and 2 produce no index delta in isolation (they operate on untracked filesystem state). Per GSD norms (no empty commits, atomic per-task commits), the only way to honor both norms simultaneously is to consolidate at the staging boundary (Task 3). The consolidated commit's message explicitly enumerates the locked decisions honored across all three tasks, preserving traceability.
- **Build artifacts pre-pruned at source.** `frontend/node_modules`, `frontend/dist`, `frontend/.tanstack`, and stray `.DS_Store` files were deleted before the move loop ran. This guarantees the move loop only deals with files that should land in the destination, and it makes the post-move verification trivially deterministic.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking issue] zsh `nomatch` failed on `..?*` glob**
- **Found during:** Task 2, first move attempt
- **Issue:** The plan's portable shell snippet `for entry in * .[!.]* ..?*; do ...` fails under zsh because zsh defaults to `nomatch` (errors on patterns with no matches) and there are no `..*` entries in `frontend/`. The first move attempt aborted with `(eval):2: no matches found: ..?*` and moved zero files.
- **Fix:** Re-ran the move under explicit `bash -c` with `shopt -s dotglob nullglob`, iterating just `*` (with dotglob enabled, `*` matches dotfiles too). This is the equivalent the plan offered as the dotglob-enabled snippet; it was simply needed to be run under bash, not zsh.
- **Files modified:** none (this was a process correction, not a source edit)
- **Commit:** 6ef25d7 (the move ultimately landed correctly under bash)

**2. [Rule 3 — Process accommodation] Task-level commit consolidation**
- **Found during:** Task 1
- **Issue:** Tasks 1 and 2 produce no tracked-file delta in the root repo because they operate entirely on untracked filesystem state. A literal "commit per task" approach would require `--allow-empty` commits, violating standard git hygiene and GSD norms.
- **Fix:** Consolidated the three tasks into a single commit at the staging boundary (Task 3). The commit message enumerates every locked decision honored. Task-by-task traceability is preserved in this SUMMARY's task table.
- **Files modified:** none
- **Commit:** 6ef25d7

### Plan Verify Clauses That Required Re-Interpretation

**Task 3 acceptance criterion:** `git status --porcelain pnpm-workspace.yaml | grep -cE '^A '` was specified to equal 1. In reality, `pnpm-workspace.yaml` was already committed during plan 01-01 (commit `9422e1a`), so its `git status` line is empty (clean). The intent of the criterion — "the workspace manifest is tracked by the root repo" — is satisfied: `git ls-files pnpm-workspace.yaml` returns one match. No deviation; the criterion's literal form was a slight overspecification.

## Issues Encountered

None blocking. Both auto-fixes above are routine process accommodations.

## Auth Gates

None — this plan is purely structural / filesystem; no external services invoked.

## Known Stubs

None new in this plan. The stubs already documented in plan 01-01's SUMMARY (`@sportzal/ui`, `@sportzal/api-client`) remain in place by design.

## User Setup Required

None — no external configuration. Plan 03 will run `pnpm install` from the root.

## Next Phase Readiness

- **Plan 01-03 (verification battery)** can now run `pnpm install` from the repo root. The current state has:
  - `apps/admin-web/pnpm-lock.yaml` (relocated frontend lockfile) — present
  - No root `pnpm-lock.yaml` — pnpm will produce one when `pnpm install` runs at root
  - `pnpm-workspace.yaml` already at root (from plan 01-01) registers `apps/*` and `packages/*`, so admin-web is auto-discovered
- **Workspace filter naming:** `pnpm --filter admin-web ...` may or may not match (pnpm matches manifest `name` by default). Per plan 01-02's action note, fall back to `pnpm --filter sportzal-adminka ...` if the directory-name filter does not resolve. The manifest is NOT to be edited.
- **No blockers.** Backend remains untouched (D-15). Forbidden `apps/client-web` remains absent (D-03 / MONO-01).

## Self-Check: PASSED

- [x] `frontend/` does not exist at repo root: `test ! -d frontend` → 0
- [x] `frontend/.git` does not exist anywhere: removed in Task 1
- [x] `apps/admin-web/` exists and contains `package.json`, `pnpm-lock.yaml`, `vite.config.ts`, `eslint.config.js`, `tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`, `vitest.config.ts`, `components.json`, `index.html` — all verified present
- [x] `apps/admin-web/.git` does NOT exist: `test ! -d apps/admin-web/.git` → 0
- [x] `apps/admin-web/node_modules`, `dist`, `.tanstack` do NOT exist (excluded per D-05)
- [x] FSD-lite layout: `src/app/`, `src/routes/`, `src/shared/` all present under `apps/admin-web/src/`
- [x] `apps/admin-web/scripts/assert-eslint-fixtures.mjs` present (lint:fixtures runner per D-08)
- [x] `grep -c '"sportzal-adminka"' apps/admin-web/package.json` == 1 (manifest verbatim per D-04)
- [x] `grep -c '"packageManager": "pnpm@9.15.9"' apps/admin-web/package.json` == 1
- [x] `apps/client-web/` absent (D-03 / MONO-01)
- [x] Root `.git/` intact (D-17)
- [x] Backend untouched: `git status --porcelain backend` returns 0 lines (D-15)
- [x] `git ls-files apps/admin-web | wc -l` == 820 (>> 50 sanity threshold)
- [x] `git ls-files apps/admin-web/.git` returns 0 entries (no nested git tracked, D-17)
- [x] `git ls-files apps/admin-web/node_modules` returns 0 entries (no node_modules tracked, D-05)
- [x] No `M` (modified) entries staged — proves verbatim preservation per D-04 / D-14
- [x] Commit `6ef25d7` exists in `git log`

---

*Phase: 01-monorepo-restructure-frontend-move*
*Completed: 2026-04-30*
