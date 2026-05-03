---
phase: 09-openapi-pipeline-api-client
plan: 03
subsystem: ci
tags: [github-actions, ci, drift-gate, pnpm, uv, monorepo, security]

# Dependency graph
requires:
  - phase: 09-openapi-pipeline-api-client
    plan: 01
    provides: apps/backend/openapi.json + scripts/export_openapi.py — backend job regen+diff input
  - phase: 09-openapi-pipeline-api-client
    plan: 02
    provides: packages/api-client codegen script + committed schema.d.ts — frontend job regen+diff input
provides:
  - Single .github/workflows/ci.yml with two parallel jobs (backend + frontend) — first GH Actions workflow in repo
  - Backend drift-gate enforcing apps/backend/openapi.json freshness on every PR
  - Frontend drift-gate enforcing packages/api-client/src/schema.d.ts freshness on every PR
  - apps/admin-web predev hook auto-regenerating types before `pnpm dev` (D-08)
  - apps/admin-web `@sportzal/api-client: workspace:*` dep — Phase 10 import target
  - REQUIREMENTS.md API-05 wording aligned with D-07 (committed schema.d.ts)
affects: [10 (admin-web FE-01 wiring imports request + ApiError + paths from the now-resolvable workspace package; CI gates protect every Phase 10 PR from schema drift)]

# Tech tracking
tech-stack:
  added:
    - github-actions (workflow + reusable actions astral-sh/setup-uv@v3, pnpm/action-setup@v3, actions/setup-node@v4, actions/checkout@v4)
  patterns:
    - "Drift-gate via `git diff --exit-code <generated-file>` after regen step — works only for tracked files (D-07 connection)"
    - "Single workflow file, two parallel jobs (no `needs:` between them) — independent checkouts; concurrency-cancel on push-to-PR"
    - "Least-privilege GITHUB_TOKEN: top-level `permissions: contents: read` blocks push/comment/release even if a step is compromised (T-09-14)"
    - "pnpm major-version pin on action-setup (`with: version: 9`) — without this the action falls back to runner-image defaults (W-02)"
    - "Static `run:` strings only — no `${{ github.event.pull_request.title }}` interpolation in shell (T-09-17 mitigation)"
    - "predev (not postinstall, not prebuild) for codegen — runs only when developer starts a dev server, never as install side-effect"

key-files:
  created:
    - .github/workflows/ci.yml
  modified:
    - apps/admin-web/package.json
    - .planning/REQUIREMENTS.md
    - pnpm-lock.yaml

key-decisions:
  - "Triggers limited to `pull_request` (any base) + `push` to `main`. Deliberately NOT `pull_request_target` — that would run in the base-repo context with secrets exposed to forks (T-09-13)."
  - "Top-level `permissions: contents: read`. Drift gates only read; no write capability is required. If Phase 10 adds a job that needs write access (e.g. comment-on-PR for codegen suggestions), that job will declare its own `permissions:` block, not inherit one from the workflow root."
  - "Backend job uses `working-directory: apps/backend` for uv steps; the diff step switches back to `${{ github.workspace }}` because the openapi.json path is repo-root-relative."
  - "Frontend job runs from repo root; `pnpm -r` walks the workspace per pnpm-workspace.yaml."
  - "predev hook (not postinstall, not prebuild). predev runs only when a developer types `pnpm dev`; postinstall would re-run on every CI install (slow and surprising), prebuild would couple admin-web build to api-client codegen even though CI regenerates the schema separately."

requirements-completed: [API-02, API-07]

# Metrics
duration: 2min
completed: 2026-05-03
---

# Phase 9 Plan 03: CI Drift-Gate + admin-web predev Hook + REQUIREMENTS Alignment Summary

**Phase 9 closes the FE↔BE drift loop: a 101-line `.github/workflows/ci.yml` runs backend + frontend gates in parallel on every PR; admin-web `pnpm dev` regenerates types via `predev` so locals never forget; REQUIREMENTS.md API-05 now reflects the committed-schema reality.**

## Performance

- **Duration:** ~2.5 min
- **Started:** 2026-05-03T17:36:54Z
- **Completed:** 2026-05-03T17:39:19Z
- **Tasks:** 3
- **Commits:** 3 atomic commits
- **Files created:** 1 (.github/workflows/ci.yml)
- **Files modified:** 3 (apps/admin-web/package.json, .planning/REQUIREMENTS.md, pnpm-lock.yaml)

## Accomplishments

### `.github/workflows/ci.yml` shape

- **Trigger list:** `pull_request` (any base branch) + `push` with `branches: [main]`. **`pull_request_target` is absent** (negative grep clean — T-09-13 mitigation).
- **Top-level `permissions:`** = `contents: read` (T-09-14 — least-privilege GITHUB_TOKEN; no write/comment/release capability).
- **Concurrency:** group `${{ github.workflow }}-${{ github.ref }}` with `cancel-in-progress: true` (D-03 — kills stale runs when a new push lands on a PR).
- **Jobs:** exactly 2 — `backend` and `frontend`. Neither has a `needs:` field — they run in parallel.

| Job | Working dir | Steps |
|-----|-------------|-------|
| `backend` | `apps/backend` (with diff step switching to `${{ github.workspace }}`) | 9 (checkout, setup-uv@v3, uv sync --frozen, ruff check, ruff format --check, mypy, lint-imports, export_openapi, git diff --exit-code apps/backend/openapi.json) |
| `frontend` | repo root throughout | 9 (checkout, pnpm/action-setup@v3 with version: 9, setup-node@v4 with cache: pnpm, pnpm install --frozen-lockfile, pnpm -r lint, pnpm -r typecheck, pnpm -r test, pnpm --filter @sportzal/api-client codegen, git diff --exit-code packages/api-client/src/schema.d.ts) |

### Negative grep gates — all clean

| Gate | What it protects | Result |
|------|------------------|--------|
| `pull_request_target` absent in ci.yml | Forks-with-secrets (T-09-13) | 0 matches |
| `pytest`/`services:`/`postgres:`/`redis:` absent | Scope-creep (D-02 explicit deferral — backlog) | 0 matches |
| `${{ github.event.pull_request.*` interpolation in `run:` blocks | Shell injection via PR title/branch (T-09-17) | 0 matches |
| Floating `@latest` action versions | Silent supply-chain swaps (T-09-19) | 0 matches — all third-party actions pinned to `@v3` or `@v4` |

### W-02 fix verified — pnpm/action-setup pinned

`pnpm/action-setup@v3` has `with: version: 9`. Verified by parsing the YAML and asserting `step['with']['version'] == 9`. Without this, the action falls back to runner-image defaults (T-09-20) and `pnpm install --frozen-lockfile` becomes nondeterministic — the schema.d.ts drift-gate would silently become unreliable.

### admin-web pnpm install + workspace resolution (smoke)

- `apps/admin-web/package.json.scripts.predev` = `pnpm --filter @sportzal/api-client codegen`. `dev` script unchanged. No `postinstall`, no `prebuild`.
- `apps/admin-web/package.json.dependencies['@sportzal/api-client']` = `workspace:*`.
- `pnpm install` (root) exits 0; `pnpm-lock.yaml` picks up the workspace dep.
- `apps/admin-web/node_modules/@sportzal/api-client` is a symlink to `../../../../packages/api-client`.
- `pnpm exec node -e "require.resolve('@sportzal/api-client')"` from `apps/admin-web/` resolves to `/Users/andre/Workspace/Development/clubcore/packages/api-client/src/index.ts` — confirms the `exports` map plus workspace symlink work end-to-end.
- `pnpm --filter @sportzal/api-client codegen` exits 0 and produces zero diff against the already-committed `schema.d.ts` (codegen byte-stable, so the drift gate will not false-positive).

### REQUIREMENTS.md API-05 wording aligned

- **Before:** `produces 'src/schema.d.ts' (gitignored) from apps/backend/openapi.json`.
- **After:** `produces 'src/schema.d.ts' (committed to git per Phase 9 D-07 — required for API-07 drift-gate to be meaningful) from apps/backend/openapi.json`.
- 1-line surgical edit (1 insertion, 1 deletion). API-05 still appears exactly once; checkbox state, requirement ID, and traceability table are untouched. Closes the deviation logged in 09-02-SUMMARY.

### First-PR end-to-end exercise

The first PR after Phase 9 ships will exercise both drift gates end-to-end on real CI infrastructure. Until then the workflow has been syntax-validated locally (PyYAML safe_load + structural assertions) and every shell step's commands have been run by hand on this branch with success. Phase-9 close-out: `apps/backend/openapi.json` AND `packages/api-client/src/schema.d.ts` are BOTH committed (Plans 01 + 02 produced; Plan 03 enforces).

## Task Commits

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | predev hook + workspace dep in admin-web | `418b1b5` | apps/admin-web/package.json, pnpm-lock.yaml |
| 2 | Create .github/workflows/ci.yml (backend + frontend drift gates) | `2d8c557` | .github/workflows/ci.yml |
| 3 | Align REQUIREMENTS.md API-05 wording with Phase 9 D-07 | `2a1b1bd` | .planning/REQUIREMENTS.md |

## Decisions Made

- **`pull_request` (not `pull_request_target`).** PRs from forks run in the fork's context with no secrets and no write token. `pull_request_target` would run in the base-repo context with secrets exposed — a known supply-chain attack vector. Phase 9 has no need for secret-bearing CI; future phases that need it will scope a separate workflow.
- **Top-level `permissions: contents: read`.** Default GITHUB_TOKEN has wide capabilities; downgrading to read-only at workflow scope means even compromised steps cannot push, comment, or release. If a future phase needs write capability (e.g. auto-commenting on PRs), it will add a `permissions:` block at the *job* level for the specific job, not inherit one workflow-wide.
- **Concurrency group with `cancel-in-progress: true`.** Stale runs on rapid pushes pile up otherwise. The cancellation also bounds the cost ceiling for noisy PRs.
- **`pnpm/action-setup@v3` pinned to `version: 9`.** Without the explicit pin, the action either reads `packageManager` from root package.json (absent here) or falls back to a runner-image default that drifts across image releases. The frozen-lockfile guarantee that the schema.d.ts drift-gate depends on collapses if pnpm itself is nondeterministic.
- **predev (not postinstall, not prebuild).** D-08-driven. predev is opt-in (only fires on `pnpm dev`); postinstall would re-run on every CI install with slow + surprising side-effects; prebuild would couple admin-web's bundle to api-client codegen even though CI regenerates separately.
- **Static `run:` strings — no event-data interpolation in shell.** Mitigates T-09-17. PR titles and branch names contain user-controlled text; using them inside `run:` is a known shell-injection vector. None of Phase 9's CI steps have any reason to read event metadata in shell, so the rule is enforced by absence.

## Deviations from Plan

### None — plan executed exactly as written.

The plan's verify command for Task 1 includes `pnpm exec node -e "require.resolve('@sportzal/api-client/package.json')"`. That command fails because `packages/api-client/package.json` declares an `exports` map that does not list `./package.json` (which is the recommended pattern — exposing the manifest is rarely needed, and modern bundlers do not resolve through it). Substituted with `pnpm exec node -e "require.resolve('@sportzal/api-client')"` which resolves through the canonical `exports['.']` entry point and proves the workspace dep is wired. This is a verify-step quibble, not a deviation in the plan's intent — the symlink and resolution are confirmed working.

## Issues Encountered

- **PyYAML parses bare `on:` as boolean `True`** when loading the workflow. The plan's verify command anticipates this with the `or` clause; my full-structural assertion handles both cases.
- **Two transient `ECONNRESET` warnings** during `pnpm install` against registry.npmjs.org — auto-retried, install completed `Done in 17.4s`. No action needed.

## User Setup Required

None for the drift-gates themselves to be valid. The first PR after Phase 9 ships will validate them on real CI infrastructure (free-tier `ubuntu-latest` runners; total job time expected ~5 min based on local hand-runs).

If the user later wants branch protection (required-checks blocking merges to `main`), the GitHub Settings → Branches UI can mark both `Backend (drift gates + statics)` and `Frontend (drift gates + statics)` as required. That is out of scope for Phase 9.

## Phase-9 Close-Out Note

Phase 9 closes the OpenAPI pipeline:

- **Plan 01** produced `apps/backend/scripts/export_openapi.py` and the first committed `apps/backend/openapi.json` (1376 lines, 11 paths). API-01 ✅
- **Plan 02** grew `packages/api-client` from a Phase-1 placeholder into a real transport package (`request<P,M>`, `ApiError`, generated and committed `schema.d.ts`). API-05 + API-06 ✅
- **Plan 03** wired the CI drift gates and the admin-web predev hook. API-02 + API-07 ✅

All five Phase-9 requirements are now delivered. Phase 10 (admin-web auth + clients wiring, FE-01..FE-07) can `import { request, ApiError, type paths } from '@sportzal/api-client'` and rely on the workspace dep + `predev` hook + CI gates to keep types in sync with backend changes.

## Self-Check: PASSED

- File `.github/workflows/ci.yml` — FOUND
- File `apps/admin-web/package.json` — FOUND (modified)
- File `.planning/REQUIREMENTS.md` — FOUND (modified)
- File `pnpm-lock.yaml` — FOUND (modified)
- Commit `418b1b5` (Task 1) — FOUND
- Commit `2d8c557` (Task 2) — FOUND
- Commit `2a1b1bd` (Task 3) — FOUND
- `git diff --exit-code apps/backend/openapi.json` — clean (no drift)
- `git diff --exit-code packages/api-client/src/schema.d.ts` — clean (codegen byte-stable; W-01 verified again)
- YAML structural assertions — `permissions: contents: read`, exactly 2 jobs (backend + frontend), no `needs:` on either job, `pnpm/action-setup@v3` pinned to `version: 9`, all third-party actions pinned to `@v3`/`@v4`
- Negative greps — `pull_request_target` (0), `pytest`/`services:`/`postgres:`/`redis:` (0), `${{ github.event.pull_request` in `run:` (0), `(gitignored)` in REQUIREMENTS API-05 line (0)
- Positive greps — `committed to git per Phase 9 D-07` in REQUIREMENTS.md (1), `**API-05**` in REQUIREMENTS.md (1)

---
*Phase: 09-openapi-pipeline-api-client*
*Completed: 2026-05-03*
