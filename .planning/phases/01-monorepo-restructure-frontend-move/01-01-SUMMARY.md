---
phase: 01-monorepo-restructure-frontend-move
plan: 01
subsystem: infra
tags: [pnpm, monorepo, workspaces, scaffold]

requires:
  - phase: none
    provides: starting state — single ./frontend SPA with its own .git, ./backend empty placeholder
provides:
  - Root pnpm-workspace.yaml registering apps/* and packages/*
  - packages/ui/ placeholder workspace (@sportzal/ui — package.json + README.md only)
  - packages/api-client/ placeholder workspace (@sportzal/api-client — package.json + README.md only)
  - infra/docker/ tracked-empty directory (.gitkeep)
  - infra/nginx/ tracked-empty directory (.gitkeep)
affects: [01-02 (frontend move into apps/admin-web), 01-03 (root pnpm install + verification), phase 02 (backend scaffold under apps/backend)]

tech-stack:
  added: []
  patterns:
    - "pnpm workspaces via two-glob form (apps/*, packages/*) — no per-app explicit entries"
    - "Scoped placeholder package naming: @sportzal/<name>"
    - "Empty-dir tracking via .gitkeep markers"

key-files:
  created:
    - pnpm-workspace.yaml
    - packages/ui/package.json
    - packages/ui/README.md
    - packages/api-client/package.json
    - packages/api-client/README.md
    - infra/docker/.gitkeep
    - infra/nginx/.gitkeep
  modified: []

key-decisions:
  - "Two-glob form for pnpm-workspace.yaml (apps/*, packages/*) — no explicit per-app entries (D-03 + Claude's Discretion)"
  - "Scoped package names @sportzal/ui and @sportzal/api-client to avoid collisions; existing unscoped sportzal-adminka name in apps/admin-web stays untouched (D-11 + Claude's Discretion)"
  - "Use .gitkeep to track empty infra/docker and infra/nginx directories (D-13 + Claude's Discretion)"
  - "No apps/client-web directory created — explicitly forbidden in Phase A milestone (D-03)"

patterns-established:
  - "Workspace placeholders: package.json with private:true, version 0.0.0, engines block, no dependencies, no scripts"
  - "Phase-scoped marker text in placeholder READMEs for downstream agents to detect intentional emptiness"

requirements-completed: [MONO-01, MONO-02, MONO-04, MONO-05, MONO-06]

duration: 1m 36s
completed: 2026-04-30
---

# Phase 1 Plan 1: Monorepo Skeleton Summary

**Repo-root pnpm-workspace.yaml plus two minimal-placeholder packages (@sportzal/ui, @sportzal/api-client) and tracked-empty infra/docker + infra/nginx — structural foundation for the frontend move in plan 02.**

## Performance

- **Duration:** 1m 36s
- **Started:** 2026-04-30T14:43:49Z
- **Completed:** 2026-04-30T14:45:25Z
- **Tasks:** 3
- **Files created:** 7
- **Files modified:** 0

## Accomplishments

- pnpm workspace manifest at the repo root registers `apps/*` and `packages/*` (no `apps/client-web`, no `backend` — both forbidden in this phase)
- Two placeholder workspace packages created with **exactly two files each** (`package.json` + `README.md`), `private: true`, no dependencies, no scripts — locked-decision compliance
- Two infra directories (`infra/docker/`, `infra/nginx/`) created and tracked via empty `.gitkeep` markers
- All five MONO requirements addressed by this plan have observable filesystem evidence (MONO-01, MONO-02, MONO-04, MONO-05, MONO-06)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create root pnpm-workspace.yaml** — `9422e1a` (chore)
2. **Task 2: Scaffold packages/ui and packages/api-client placeholders** — `e2e02b7` (chore)
3. **Task 3: Create infra/docker and infra/nginx with .gitkeep** — `ea139dd` (chore)

**Plan metadata commit:** pending (final commit after this SUMMARY + STATE/ROADMAP updates)

## Files Created/Modified

- `pnpm-workspace.yaml` — registers `apps/*` and `packages/*` for pnpm workspaces
- `packages/ui/package.json` — `@sportzal/ui` placeholder workspace (private, no deps, no scripts)
- `packages/ui/README.md` — Phase 1 placeholder marker referencing locked decision D-09
- `packages/api-client/package.json` — `@sportzal/api-client` placeholder workspace
- `packages/api-client/README.md` — Phase 1 placeholder marker referencing locked decision D-10
- `infra/docker/.gitkeep` — empty marker so git tracks the directory
- `infra/nginx/.gitkeep` — empty marker so git tracks the directory

## Decisions Made

- **Two-glob workspace form chosen over explicit per-app listing.** Per D-03 and Claude's Discretion in CONTEXT.md, `apps/*` + `packages/*` is canonical and survives plan 02 (`apps/admin-web`) without manifest edits. The explicit-listing alternative was rejected because it duplicates filesystem state and would require a second commit when admin-web is added.
- **Scoped package names `@sportzal/ui`, `@sportzal/api-client`.** Existing `frontend/package.json` uses unscoped `sportzal-adminka`. Per D-11 + Claude's Discretion, scoped names are conventional for monorepo internal packages and avoid future collisions; the existing admin-web name will remain unscoped (planner-confirmed in plan 02).
- **`engines` block (node >=20, pnpm >=9) mirrored from frontend/package.json** so each placeholder advertises the same minimum runtime as admin-web — keeps `pnpm install` from emitting unnecessary engine warnings later.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## Known Stubs

Per locked decisions D-09 through D-12, the two placeholder packages are **intentional stubs**. They are not bugs and are not blocking the plan's goal:

| Stub | File | Reason | Resolves in |
|------|------|--------|-------------|
| `@sportzal/ui` placeholder workspace (no `src/`, no exports) | `packages/ui/package.json` | Phase 1 placeholder per D-09. Real shared UI primitives land only when there is a second consumer. | Deferred (Phase B+; see Phase 1 CONTEXT.md `## Deferred Ideas`) |
| `@sportzal/api-client` placeholder workspace (no `src/`, no exports) | `packages/api-client/package.json` | Phase 1 placeholder per D-10. Real client wires up after the backend exposes endpoints (v2 requirement FE-02). | Deferred (after Phase 2 backend scaffold) |

These stubs are required by the Phase 1 boundary in CLAUDE.md (`Placeholders only`) and CONTEXT.md (D-09..D-12). No data wiring is missing — these packages have no UI rendering surface yet by design.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Plan 01-02 (frontend move)** can now `git mv frontend/* apps/admin-web/` into the workspace skeleton this plan created. The `apps/*` glob in `pnpm-workspace.yaml` will pick up `apps/admin-web/` automatically.
- **Plan 01-03 (verification)** will run root `pnpm install`; until that runs, the lockfile remains the existing `frontend/pnpm-lock.yaml` (still inside `./frontend/`). No `pnpm install` was run in this plan because `apps/admin-web/` does not yet exist.
- **No blockers.** `apps/client-web` is verified absent; no forbidden entries in the manifest.

## Self-Check: PASSED

- [x] `pnpm-workspace.yaml` exists and contains `apps/*` and `packages/*`, no `client-web`, no `backend`
- [x] `packages/ui/package.json` and `packages/ui/README.md` exist (exactly 2 files in `packages/ui/`)
- [x] `packages/api-client/package.json` and `packages/api-client/README.md` exist (exactly 2 files in `packages/api-client/`)
- [x] `infra/docker/.gitkeep` and `infra/nginx/.gitkeep` exist (each directory contains exactly the .gitkeep)
- [x] `apps/client-web/` does NOT exist
- [x] Commits `9422e1a`, `e2e02b7`, `ea139dd` all found in `git log`

All 7 created files verified on disk. All 3 task commits verified in git history. Forbidden directory `apps/client-web/` confirmed absent.

---

*Phase: 01-monorepo-restructure-frontend-move*
*Completed: 2026-04-30*
