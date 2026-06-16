---
phase: quick
plan: 260616-xa9
subsystem: monorepo-structure
tags: [rename, refactor, monorepo, helm, infra, backend-tests]
requires: []
provides: [apps/admin (renamed from apps/admin-app), apps/client (renamed from apps/client-pwa), @clubcore/admin, @clubcore/client]
affects: [frontend, infra/helm, infra/docker, infra/nginx, infra/scripts, backend tests, alembic seeds, ci]
tech-stack:
  added: []
  patterns: [literal-token-sweep, helm-lockstep-labels]
key-files:
  created: []
  modified:
    - 42 files in Task 2 sweep
    - pnpm-lock.yaml (Task 3)
decisions:
  - "client-pwa→client literal sweep cannot collide with backend `client` domain tokens (no `-pwa` suffix)"
  - "camelCase Helm value keys (.Values.adminApp/.clientPwa) preserved — only hyphenated tokens renamed"
  - "alembic 0059/0063 admin-app/client-pwa refs were comment/source-path only, not seeded data"
metrics:
  completed: 2026-06-17
  tasks: 3
  files_changed: 43
---

# Quick Plan 260616-xa9: Rename apps admin-app→admin, client-pwa→client Summary

Renamed the two frontend app directories and their npm package names (`@clubcore/admin-app`→`@clubcore/admin`, `@clubcore/client-pwa`→`@clubcore/client`), then swept all ~252 remaining textual references across infra, backend tests, alembic seed comments, docs, and CI, and regenerated the pnpm lockfile — with all typecheck/lint gates green and backend `client` domain tokens left intact.

## What Was Done

This continuation completed Tasks 2 and 3 (Task 1 — `git mv` of dirs + package.json renames — was done in commit `b0a98805`).

### Task 2 — Reference sweep (commit `46afa447`)
Literal token substitution `admin-app`→`admin` and `client-pwa`→`client` (which also covers `@clubcore/` scoped variants since they are prefixes of the bare token) across 42 files: 250 insertions / 250 deletions (perfectly symmetric — pure token swap).

Notable categories:
- **Backend test live filesystem paths** repointed to `apps/admin/`: `test_rbac_parity.py` (`_REPO_ROOT / "apps" / "admin" / ...`), `test_byte_parity.py`, and 5 `*_capture.py` fixtures (`FIXTURES_DIR = _REPO_ROOT / "apps/admin/src/features/.../capture"`). Verified the fixture dirs exist under the renamed path before relying on them.
- **Helm templates** — labels, selectors, Service names, Deployment names, Ingress backends, and NetworkPolicy names all moved in lockstep (`app.kubernetes.io/component: admin`/`client`, `<fullname>-admin`/`-client`, `-allow-admin`/`-allow-client`).
- **infra/docker, infra/nginx, infra/scripts, infra/runbooks** — Dockerfiles, nginx conf header comments, build/deploy/scan/smoke scripts, production runbook.
- **Docs/CI** — root `CLAUDE.md`, `apps/admin/CLAUDE.md`, `apps/admin/README.md`, `.dockerignore`, `Makefile`, `.github/workflows/ci.yml` (job ids `admin-app:`→`admin:`, `client-pwa:`→`client:` and `-F`/`--filter` package selectors).
- **Backend comments** — `config.py`, `permissions.py`, `loyalty/permissions.py` (source-of-truth path comments only; no field names changed).
- **alembic seeds** — `0059_seed_gym_info.py`, `0063_seed_trainer_profiles.py`: the `admin-app`/`client-pwa` strings were docstring/comment references to the frontend content-source path (`apps/client-pwa/src/data/gym.js` → `apps/client/src/data/gym.js`). They are NOT seeded user-facing data (actual seeded values are `_HOURS`, gym name, trainer bios). Renaming them is a documentation-correctness fix that keeps the comment pointing at the real (renamed) source file. No public URL or DB-persisted value was altered.

### Task 3 — Lockfile + checks (commit `f2a3570c`)
- `pnpm install` regenerated `pnpm-lock.yaml`: workspace keys `apps/admin-app:`→`apps/admin:`, `apps/client-pwa:`→`apps/client:`. (Net -711/+27 lines = pnpm normalizing to current v9 resolution; no dependency changes.)
- `pnpm -F @clubcore/admin typecheck` → PASS
- `pnpm -F @clubcore/client typecheck` → PASS
- `pnpm -F @clubcore/admin lint` → PASS
- `pnpm -F @clubcore/client lint` → PASS

## Precision Guarantees (verified)

| Constraint | Result |
|---|---|
| Backend `client` domain tokens untouched (`ClientPrincipal`, `cc_client_`, `/api/v1/client`, `clients` table, `seed_dev_client`) | PASS — 98 backend files still match domain tokens |
| `admin-web` / `apps/admin-web` (deleted app) untouched | PASS — all `admin-web` refs intact (literal `admin-app`→`admin` never matches `admin-web`) |
| camelCase Helm keys `.Values.adminApp` / `.Values.clientPwa` untouched | PASS — only hyphenated tokens renamed; `certificate.yaml` (camelCase-only) correctly unchanged |
| `.planning/` untouched | PASS — sweep excluded `.planning` and `pnpm-lock.yaml` (lockfile handled separately by pnpm) |
| Helm label/selector lockstep preserved | PASS — component labels + selectors + Service names + Ingress backends + NetworkPolicy selectors all renamed together |

## Final Verification Results

1. `git grep -n 'admin-app|client-pwa|@clubcore/admin-app|@clubcore/client-pwa' -- ':!.planning'` → **ZERO HITS** (PASS)
2. `git grep -ln 'ClientPrincipal|cc_client_|/api/v1/client' -- apps/backend` → **98 files** (domain survived, PASS)
3. `helm lint infra/helm/clubcore` → **helm not installed in this environment — skipped (non-blocking)**. Lockstep label/selector/name integrity was instead verified manually via targeted grep (see Precision table).
4. typecheck (admin, client) + lint (admin, client) → **all PASS**

## Deviations from Plan

None beyond the prescribed approach. Two operational notes:
- The initial bulk-sweep attempt used a shell loop whose word-splitting collapsed the file list into one oversized argument (no edits applied). Re-run per-file via a temp file list. A subsequent `IFS=`-based loop was blocked by the shell guard; replaced with a temp-file `while read` loop. No content impact — caught immediately by the post-sweep grep.

## Commits

- `b0a98805` refactor(260616-xa9): git mv app dirs + infra files + rename package names (Task 1, prior session)
- `46afa447` refactor(260616-xa9): sweep all admin-app/client-pwa references → admin/client (Task 2)
- `f2a3570c` chore(260616-xa9): regenerate pnpm-lock for renamed packages (Task 3)

## Self-Check

- Commit `46afa447` exists: FOUND
- Commit `f2a3570c` exists: FOUND
- SUMMARY path exists: written to `.planning/quick/260616-xa9-rename-apps-admin-app-to-admin-client-pw/260616-xa9-SUMMARY.md`

## Self-Check: PASSED
