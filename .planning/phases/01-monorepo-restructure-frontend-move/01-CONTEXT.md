# Phase 1: Monorepo Restructure & Frontend Move - Context

**Gathered:** 2026-04-30
**Status:** Ready for planning
**Source:** Inline decision capture during /gsd-plan-phase (user opted to skip full discuss-phase)

<domain>
## Phase Boundary

Restructure the repository into a pnpm-based monorepo skeleton (`apps/`, `packages/`, `infra/`) and relocate the existing React 19 SPA from `./frontend/` to `apps/admin-web/` without modifying its internal structure, mocks, RBAC, theme, i18n, ESLint chokepoints, or test files. Establish placeholder packages (`packages/ui`, `packages/api-client`) and infra directories (`infra/docker`, `infra/nginx`) so a backend can land alongside in subsequent phases without conflict.

**Out of scope for Phase 1:**
- Any backend code (`apps/backend/` is created in a later phase, not here)
- Any real source code in `packages/ui` or `packages/api-client` (placeholders only)
- Any frontend code modifications (file moves only — internal structure is frozen)
- Any UI/visual changes (no UI-SPEC required — purely structural)
- Creating `apps/client-web` (explicitly forbidden — even as an empty directory)

</domain>

<decisions>
## Implementation Decisions

### Git history strategy (LOCKED — user chose 2026-04-30)
- **D-01 [LOCKED]**: Use **clean collapse** for `frontend/.git`. Run `rm -rf frontend/.git` before/during the move. Do **NOT** use `git subtree add` or any history-preserving approach. Rationale: clean root history; the frontend's prior commits are not load-bearing for the monorepo.

### Workspace tooling (LOCKED — from CLAUDE.md)
- **D-02 [LOCKED]**: Package manager is **pnpm** (workspaces). pnpm version pinned to `>=9.0.0` (lockfile uses 9.15.9). Node `>=20.0.0`.
- **D-03 [LOCKED]**: `pnpm-workspace.yaml` lives at the repo root and registers `apps/*` and `packages/*`. No `apps/client-web` entry — only `apps/admin-web`.
- **D-04 [LOCKED]**: Frontend stack (React 19, Vite 6, TanStack Router, TanStack Query, Tailwind v4, Vitest, ESLint 9 flat config, TypeScript 5.7 strict) — DO NOT TOUCH. Existing `package.json`, `pnpm-lock.yaml`, `vite.config.ts`, `tsconfig*.json`, `eslint.config.js`, `vitest.config.ts`, `components.json` move as-is to `apps/admin-web/`.

### Move semantics (LOCKED)
- **D-05 [LOCKED]**: The move is a **bulk relocation** of every file under `./frontend/` (excluding `.git`, `node_modules`, `dist`, `.tanstack`, and other build artifacts) into `apps/admin-web/`. After the move, `./frontend/` no longer exists at the repo root.
- **D-06 [LOCKED]**: Inside `apps/admin-web/`, the FSD-lite layer layout (`src/app/`, `src/routes/`, `src/shared/`, future `src/features/`, `src/entities/`) is preserved verbatim. No path-alias changes (`@/* → src/*` keeps working because it's relative to each package's `tsconfig.json`).
- **D-07 [LOCKED]**: Test files are NOT modified. `pnpm --filter admin-web test` must pass against the existing Vitest suite untouched (success criterion #4).
- **D-08 [LOCKED]**: ESLint chokepoints (`api-mode-leak.ts`, `illegal-mock-import.ts`, `raw-palette.tsx` negative fixtures) and the layered `import/no-restricted-paths` rule continue to function inside `apps/admin-web/`. Any path-prefix adjustments inside `eslint.config.js` are allowed only if they're a direct mechanical consequence of the new working directory; semantics must be identical.

### Placeholder packages (LOCKED — from REQUIREMENTS.md MONO-04, MONO-05)
- **D-09 [LOCKED]**: `packages/ui/` contains exactly two files: `package.json` and `README.md`. No `src/`, no `index.ts`, no real exports.
- **D-10 [LOCKED]**: `packages/api-client/` contains exactly two files: `package.json` and `README.md`. No source code.
- **D-11 [LOCKED]**: Placeholder `package.json` files declare a workspace name (e.g. `@sportzal/ui`, `@sportzal/api-client`), `"private": true`, and the same `engines` block as the admin-web app. No dependencies, no scripts beyond a no-op placeholder if required by tooling.
- **D-12 [LOCKED]**: README.md files state "Phase 1 placeholder — no code yet. Real implementation lands in a later phase." (or equivalent).

### Infra directories (LOCKED — from REQUIREMENTS.md MONO-06)
- **D-13 [LOCKED]**: `infra/docker/` and `infra/nginx/` exist as directories. They may be empty or contain only `.gitkeep` so git tracks them. No real Dockerfiles, no nginx configs in this phase — those land in later infra phases.

### Frontend-integrity boundary (LOCKED — from CLAUDE.md `apps/admin-web` is a transfer of `./frontend`, no edits in Phase A)
- **D-14 [LOCKED]**: Zero edits to React/TS source files inside `apps/admin-web/src/`. Allowed root-level edits inside `apps/admin-web/` are limited to mechanical workspace-relative path adjustments only if absolutely required (e.g., relative paths in scripts that walked up to a previous root). Prefer NOT to edit anything; if an edit is required, it must be justified in the plan task with the exact line being changed and why.
- **D-15 [LOCKED]**: The existing `./backend/` placeholder directory at the repo root stays where it is for this phase (it will be relocated/replaced in a backend-scaffolding phase). It does NOT block the monorepo skeleton creation. If empty and untracked, planner may leave it alone or remove it — planner's discretion, but don't add anything to it.

### Verification (LOCKED — derived from ROADMAP success criteria)
- **D-16 [LOCKED]**: Verification commands (must all succeed from repo root after the move):
  - `test ! -d frontend` (top-level `frontend/` is gone)
  - `test ! -d apps/client-web` (forbidden directory absent)
  - `test -f pnpm-workspace.yaml`
  - `test -d apps/admin-web && test -f apps/admin-web/package.json`
  - `test -f packages/ui/package.json && test -f packages/ui/README.md && [ "$(ls packages/ui | wc -l)" -le 2 ]`
  - `test -f packages/api-client/package.json && test -f packages/api-client/README.md && [ "$(ls packages/api-client | wc -l)" -le 2 ]`
  - `test -d infra/docker && test -d infra/nginx`
  - `pnpm install` (succeeds; resolves all three workspaces)
  - `pnpm --filter admin-web typecheck` (succeeds)
  - `pnpm --filter admin-web lint` (succeeds — fixtures still trigger expected rules)
  - `pnpm --filter admin-web lint:fixtures` (succeeds — negative fixtures still violate rules as expected)
  - `pnpm --filter admin-web test` (existing Vitest suite passes unmodified)
  - `pnpm --filter admin-web build` (Vite build succeeds)
  - `pnpm --filter admin-web dev` (dev server starts on port 5173 — manual smoke or background-start + `curl localhost:5173` + kill)
- **D-17 [LOCKED]**: After the move, the root repo has a single `.git` (the existing clubcore repo). `frontend/.git` is gone. `apps/admin-web/` does NOT have its own `.git`.

### Claude's Discretion
- Internal organization of plan files (one big plan vs. wave-split plans across "scaffold dirs", "move SPA", "create placeholders", "verify").
- Exact filename of `pnpm-workspace.yaml` glob entries (`apps/*` + `packages/*` is conventional; `apps/admin-web` + `packages/ui` + `packages/api-client` explicitly is also fine).
- Whether `.gitkeep` is used in empty `infra/docker/` and `infra/nginx/` directories (recommended — git won't track empty dirs otherwise).
- The exact `name` field of placeholder packages (e.g. `@sportzal/ui` vs `sportzal-ui`); pick a convention consistent with the existing `frontend/package.json` `name: "sportzal-adminka"` style.
- Whether to use `git mv` for the bulk move (preserves git rename detection) vs `mv` followed by `git add`. Recommend `git mv` so the root repo's history shows file renames cleanly.
- Whether to delete `./backend/` if empty, or leave it as-is for a future backend phase.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project specs
- `CLAUDE.md` — project instructions; defines the constraint that `apps/admin-web` is a verbatim transfer of `./frontend` and that placeholder packages contain only `package.json` + `README.md` in Phase A.
- `.planning/PROJECT.md` — milestone scope.
- `.planning/REQUIREMENTS.md` — MONO-01 … MONO-06 are the requirement IDs every plan must address.
- `.planning/ROADMAP.md` — Phase 1 section; success criteria and the (now-resolved) `frontend/.git` open question.

### Existing frontend (do-not-modify reference)
- `frontend/package.json` — scripts (`dev`, `build`, `test`, `lint`, `lint:fix`, `lint:fixtures`, `typecheck`) that must continue to work after move.
- `frontend/pnpm-lock.yaml` — moves to `apps/admin-web/pnpm-lock.yaml`. After the workspace is configured at root, decide whether the lockfile should be re-resolved at the root level (pnpm prefers a single root lockfile) or kept at the app level. Plan must call this out.
- `frontend/vite.config.ts` — port 5173 dev server; no edits expected.
- `frontend/eslint.config.js` — chokepoint rules; no semantic edits expected.
- `frontend/tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json` — composite TS build, no edits expected.
- `frontend/scripts/assert-eslint-fixtures.mjs` — `lint:fixtures` runner; relative paths might need verification after move.

### Lockfile placement note
pnpm workspaces use a single root `pnpm-lock.yaml`. After moving `frontend/pnpm-lock.yaml` into `apps/admin-web/`, running `pnpm install` at the repo root will produce a new root `pnpm-lock.yaml`. The plan should explicitly state which lockfile is authoritative post-move and ensure CI / dev expectations are aligned.

</canonical_refs>

<specifics>
## Specific Ideas

### Suggested execution order (planner may refine)
1. Create empty skeleton: `apps/`, `packages/ui/`, `packages/api-client/`, `infra/docker/`, `infra/nginx/`, `pnpm-workspace.yaml`, placeholder `package.json` + `README.md` files. (Wave 1)
2. Drop `frontend/.git` and move `frontend/*` → `apps/admin-web/` via `git mv`. (Wave 2 — depends on Wave 1)
3. Reconcile lockfile + run `pnpm install` from root; verify all success criteria (typecheck, lint, lint:fixtures, test, build, dev smoke). (Wave 3 — depends on Wave 2)

### File operations summary
- **Create:** `pnpm-workspace.yaml`, `packages/ui/package.json`, `packages/ui/README.md`, `packages/api-client/package.json`, `packages/api-client/README.md`, `infra/docker/.gitkeep`, `infra/nginx/.gitkeep`.
- **Move:** entire contents of `frontend/` → `apps/admin-web/` (every file & subdir except `.git`, `node_modules`, `dist`, `.tanstack`).
- **Delete:** `frontend/.git`, `frontend/` itself (after move), optionally `frontend/node_modules` and `frontend/dist` (will be regenerated).

### Smoke-test approach
For `pnpm --filter admin-web dev`, the verification can be: start the dev server in background, `curl -fsS http://localhost:5173/` returns 200 and HTML contains `<div id="root">` (or whatever the actual mount node is in `apps/admin-web/index.html`), then kill the background process. Avoid manual interactive verification.

</specifics>

<deferred>
## Deferred Ideas

- Real `packages/ui` exports (shared shadcn primitives or design tokens shared with backend admin) — Phase B+ when there's a second consumer.
- Real `packages/api-client` — lands once the backend exposes endpoints (Phase A backend scaffolding generates types, but actual client wiring is in a frontend-integration phase later).
- `apps/client-web` (public-facing client app) — explicitly out of scope for the entire `Phase A` milestone.
- Real Dockerfiles in `infra/docker/` and nginx configs in `infra/nginx/` — they land in a backend-infra phase.
- Removing or replacing the existing `./backend/` placeholder directory — handled in the backend-scaffolding phase.

</deferred>

---

*Phase: 01-monorepo-restructure-frontend-move*
*Context gathered: 2026-04-30 via inline decision capture (user declined full /gsd-discuss-phase)*
