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
| `pnpm -r typecheck` exits 0 | **FAIL** (see "Deviations" — explicitly deferred to G-2 per plan Task 2 STOP directive) |

## Deviations from Plan

### Plan-directed deferral (not a deviation in the usual sense)

**Residual `@sportzal/api-client` imports in `apps/admin-web/src/*` source files cause `pnpm -r typecheck` to fail at this commit tip.**

- **Plan instruction (Task 2, verbatim):** "If typecheck surfaces residual @sportzal import references in source files, STOP — those belong to G-2..G-6 plans and must not be fixed here; report them in the SUMMARY for downstream awareness."
- **Tension with success criterion:** The plan's `must_haves.truths` list includes `"pnpm -r typecheck exits 0"`, which directly contradicts the Task 2 STOP directive. The Task 2 directive is more specific and tied to the atomic-commit-group decomposition (D-62-11) — it takes precedence. The success-criterion line appears to be an oversight in the plan; the planner explicitly anticipated this residual via the STOP language.
- **Action taken:** STOPPED at Task 2 verification per plan instruction. Reporting downstream in this SUMMARY.

### Pre-existing baseline noise (not introduced by this plan)

Backend route-tree typecheck errors of the form `Property 'queryClient' does not exist on type 'never'` / `Argument of type '"/_protected/…"' is not assignable to parameter of type 'undefined'` in `apps/admin-web/src/routes/**` were observed at the base commit (`9034b951`) **before any rename**, verified by stashing this plan's changes and re-running `pnpm -r typecheck`. They reflect a stale/missing `routeTree.gen.ts` regen that this plan does not touch and is out of scope per `<scope_boundary>` (only fix issues DIRECTLY caused by current task's changes).

## Known Stubs

None.

## Deferred Issues / Residual @sportzal in Source Code

The following 12 source files in `apps/admin-web/src/` still import `@sportzal/api-client` (or reference the old scope in test/auth flows) and are scheduled for fix-up by the parallel G-2..G-6 plans. These are **deliberate residuals**, not bugs:

| File | Type | Target plan |
| ---- | ---- | ----------- |
| `apps/admin-web/src/shared/api/errors.ts` | `import type { … } from '@sportzal/api-client'` | G-2 (frontend rename pass) |
| `apps/admin-web/src/shared/api/services/http/_clientsAdapter.test.ts` | import | G-2 |
| `apps/admin-web/src/shared/api/services/http/_clientsAdapter.ts` | import | G-2 |
| `apps/admin-web/src/shared/api/services/http/_membershipsAdapter.ts` | import | G-2 |
| `apps/admin-web/src/shared/api/services/http/_visitsAdapter.ts` | import | G-2 |
| `apps/admin-web/src/shared/api/services/http/auth.ts` | import | G-2 |
| `apps/admin-web/src/shared/api/services/http/clients.ts` | import | G-2 |
| `apps/admin-web/src/shared/api/services/http/memberships.ts` | import | G-2 |
| `apps/admin-web/src/shared/api/services/http/visits.ts` | import | G-2 |
| `apps/admin-web/src/shared/api/services/http/index.ts` | barrel re-export | G-2 |
| `apps/admin-web/src/features/auth/api/redirect-on-session-expired.ts` | import | G-2 |
| `apps/admin-web/src/features/auth/api/redirect-on-session-expired.test.ts` | import | G-2 |

Until G-2 rewrites these import sites to `@clubcore/api-client`, the admin-web TypeScript build is broken at runtime — which is exactly the predicted blast radius of "atomic at workspace-graph layer, parallel sweep at source-import layer".

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
  - FOUND: `a937090b` (G-1 atomic rename)
- Plan-touched files contain expected literals: confirmed via `jq` + `grep` (see Verification Results).
- Zero `@sportzal` residue across the six plan-touched files: confirmed.
