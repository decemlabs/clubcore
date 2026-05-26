---
phase: 62-clubcore-rebrand
plan: 01
subsystem: workspace-config
tags: [rebrand, pnpm, workspace, atomic-rename]
requires:
  - .planning/phases/62-clubcore-rebrand/62-CONTEXT.md
  - .planning/phases/62-clubcore-rebrand/62-PATTERNS.md
provides:
  - "@clubcore/api-client workspace package identifier"
  - "@clubcore/ui workspace package identifier"
  - "clubcore-adminka admin-web package identifier"
  - "Regenerated pnpm-lock.yaml under @clubcore/* scope"
affects:
  - downstream-plans: [62-02, 62-03, 62-04, 62-05, 62-06]
tech-stack:
  added: []
  patterns: [atomic-package-rename, workspace-scope-bump]
key-files:
  created: []
  modified:
    - packages/api-client/package.json
    - packages/ui/package.json
    - apps/admin-web/package.json
    - apps/admin-web/eslint.config.js
    - .github/workflows/ci.yml
    - pnpm-lock.yaml
decisions:
  - "G-1 landed as a single atomic commit (D-62-11 ATOMIC-PACKAGE-RENAME); residual @sportzal/api-client imports in admin-web/src/* are intentionally deferred to G-2..G-6"
  - "pnpm-lock.yaml regenerated via `pnpm install` (not hand-edited); second `--frozen-lockfile` run is byte-stable (md5 unchanged)"
metrics:
  duration_minutes: 8
  completed_at: "2026-05-26"
  task_count: 2
  file_count_modified: 6
requirements: [REB-01, REB-06, REB-07]
---

# Phase 62 Plan 01: G-1 pnpm workspace rename @sportzal/* -> @clubcore/* Summary

One-liner: Atomic rename of all pnpm workspace package identifiers from `@sportzal/*` to `@clubcore/*` (api-client + ui + admin-web app), plus matching CI workflow filter strings and ESLint user-facing message, with regenerated stable `pnpm-lock.yaml`, landed in a single commit per D-62-11.

## Tasks Executed

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1+2 (atomic per D-62-11) | Rename @sportzal/* -> @clubcore/* in 5 config files + regenerate pnpm-lock.yaml | `a937090b` | packages/api-client/package.json, packages/ui/package.json, apps/admin-web/package.json, apps/admin-web/eslint.config.js, .github/workflows/ci.yml, pnpm-lock.yaml |

Per D-62-11 ATOMIC-PACKAGE-RENAME, Task 1 (file edits) and Task 2 (lockfile regen + verification) were collapsed into a single atomic commit so that `pnpm install --frozen-lockfile` is green at the commit tip. Splitting them across two commits would have left a transient state where package.json declares `@clubcore/api-client` while pnpm-lock.yaml still resolves `@sportzal/api-client` — exactly the mid-rename incoherence the decision prohibits.

## Exact Rename Map Applied

### `packages/api-client/package.json`
- `"name": "@sportzal/api-client"` → `"name": "@clubcore/api-client"`
- `"description": "Typed transport for the Sportzal backend …"` → `"description": "Typed transport for the clubcore backend …"`

### `packages/ui/package.json`
- `"name": "@sportzal/ui"` → `"name": "@clubcore/ui"`
- Description left intact (no brand reference).

### `apps/admin-web/package.json`
- `"name": "sportzal-adminka"` → `"name": "clubcore-adminka"`
- `"predev": "pnpm --filter @sportzal/api-client codegen"` → `"predev": "pnpm --filter @clubcore/api-client codegen"`
- `"@sportzal/api-client": "workspace:*"` → `"@clubcore/api-client": "workspace:*"` (dependency block)

### `apps/admin-web/eslint.config.js` (FE-07 message at line 120)
- `'Use @sportzal/api-client.request<P,M> instead of raw fetch(). …'` → `'Use @clubcore/api-client.request<P,M> instead of raw fetch(). …'`

### `.github/workflows/ci.yml` (lines 102-106)
- Step name `Test @sportzal/api-client` → `Test @clubcore/api-client`
- `pnpm -F @sportzal/api-client test` → `pnpm -F @clubcore/api-client test`
- `pnpm --filter @sportzal/api-client codegen` → `pnpm --filter @clubcore/api-client codegen`

### `pnpm-lock.yaml`
- Regenerated via `pnpm install` (no hand-edit).
- Diff stat: `6 lines changed, 3 insertions, 3 deletions` — purely identifier swap; no dependency graph reshuffle.
- Verified stable: second `pnpm install --frozen-lockfile` produces byte-identical lockfile (md5 unchanged: `e1ec83f286cecc52121c4155117dce50`).

## Verification Results

| Check | Result |
| ----- | ------ |
| `pnpm install --frozen-lockfile` exits 0 | PASS (lockfile coherent with renamed package.json files) |
| `grep -c '@sportzal' packages/api-client/package.json packages/ui/package.json apps/admin-web/package.json apps/admin-web/eslint.config.js .github/workflows/ci.yml pnpm-lock.yaml` == 0 | PASS (0 residual matches across all 6 plan-touched files) |
| `jq '.name'` on three package.json files | PASS (`@clubcore/api-client`, `@clubcore/ui`, `clubcore-adminka`) |
| `grep -c '@clubcore/api-client' pnpm-lock.yaml` >= 1 | PASS (1 workspace dep entry) |
| Second `pnpm install --frozen-lockfile` is diff-clean (md5 stable) | PASS |
| `pnpm -r typecheck` exits 0 | PASS (after orchestrator-added Task 3 closing the residual-import gap — see "Deviations") |

## Deviations from Plan

### Orchestrator-added Task 3: close residual-import gap

**Initial executor run (commit `a937090b`) followed Task 2's STOP directive and left 12 `apps/admin-web/src/*` files importing `@sportzal/api-client`.** The orchestrator subsequently confirmed those 12 sites were not owned by any downstream plan (62-PATTERNS.md G-1..G-6 surface tables do not enumerate them, and `files_modified` of plans 62-02..62-07 do not include them either), making the deferral an orphan-set rather than a legitimate hand-off.

To honor D-62-11 ATOMIC-PACKAGE-RENAME and the `must_haves.truths` requirement for green typecheck at tip, the orchestrator added a third commit (`2cc1d690`) doing a mechanical `@sportzal/api-client → @clubcore/api-client` rename across the 12 source files. Verification ran cleanly afterwards:

- `pnpm install --frozen-lockfile` — PASS
- `pnpm -r typecheck` — PASS (exit 0, both workspace projects clean)
- `grep -rln '@sportzal/api-client' apps/admin-web/src` — 0 matches

The original Task 2 STOP directive was a planning defect (referenced "G-2..G-6 plans" that did not in fact own the work). The plan's `must_haves.truths` line was correct; the in-task STOP was wrong. Logged as a planning-quality issue for retrospective.

### Worktree-isolation artifact, not pre-existing baseline noise

The earlier executor report flagged routes/* TS2339/TS2345 errors as "pre-existing baseline noise". On follow-up the orchestrator established these were a worktree-isolation artifact, not a real codebase problem: `apps/admin-web/src/routeTree.gen.ts` is gitignored and produced by the `@tanstack/router-plugin` Vite plugin on dev/build startup. The main checkout has the file present; fresh worktrees do not, which makes `tsc -b --noEmit` fail with cascading `getSession` / `queryClient` "does not exist on type 'never'" errors against `RouterContext`. Running `pnpm exec vite build` once in the worktree regenerates `routeTree.gen.ts`; subsequent typecheck passes cleanly. No real code defect.

## Known Stubs

None.

## Deferred Issues / Residual @sportzal in Source Code

None remaining. The 12 source-import sites listed in the initial executor pass were closed by orchestrator-added commit `2cc1d690` (see "Deviations from Plan" above). At tip:

- `grep -rln '@sportzal/api-client' apps/admin-web/src` → 0 matches
- `grep -rn '@sportzal' apps/admin-web/src` → 0 matches outside of intentional v1.10 shim sites (which belong to G-2/G-4, not G-1)

## Threat Flags

None — pure identifier rename with workspace-local scope. No new attack surface introduced. STRIDE register from the PLAN remains accurate:
- T-62-01-01 (Tampering / pnpm-lock.yaml): MITIGATED — second `--frozen-lockfile` is diff-clean.
- T-62-01-02 (Spoofing / @clubcore scope): ACCEPTED — workspace-only, no npm publish path.
- T-62-01-03 (Information Disclosure / CI filters): MITIGATED — grep verified zero `@sportzal` in `.github/workflows/ci.yml`.
- T-62-01-04 (DoS / downstream plans): MITIGATED — atomic single-commit landing.

## TDD Gate Compliance

Not applicable. Plan type is `execute`, not `tdd`. No `<behavior>` blocks. Tasks are pure-mechanical rename + lockfile regen with no new runtime behaviour.

## Self-Check: PASSED

- Created files: none (only modifications).
- Modified files exist:
  - FOUND: `packages/api-client/package.json`
  - FOUND: `packages/ui/package.json`
  - FOUND: `apps/admin-web/package.json`
  - FOUND: `apps/admin-web/eslint.config.js`
  - FOUND: `.github/workflows/ci.yml`
  - FOUND: `pnpm-lock.yaml`
- Commits exist:
  - FOUND: `a937090b` (G-1 atomic rename — workspace config)
  - FOUND: `2482f186` (G-1 SUMMARY scaffold)
  - FOUND: `2cc1d690` (G-1 orchestrator-added closure — 12 admin-web src/* import fixups)
- Plan-touched files contain expected literals: confirmed via `jq` + `grep` (see Verification Results).
- Zero `@sportzal` residue across the six plan-touched files: confirmed.
