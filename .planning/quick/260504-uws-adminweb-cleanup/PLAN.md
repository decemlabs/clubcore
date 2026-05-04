---
quick_id: 260504-uws
slug: adminweb-cleanup
type: quick
date: 2026-05-04
description: "Tighten dev hygiene: add root .gitignore for monorepo-wide noise, and exclude colocated *.test.tsx files from TanStack Router scanning."
files_modified:
  - .gitignore
  - apps/admin-web/vite.config.ts
---

<objective>
Two unrelated-but-related hygiene fixes surfaced during Phase 10 UAT:

1. **Root `.gitignore` is missing.** `git status` chronically shows `.DS_Store`, `apps/.DS_Store`, `node_modules/`, and `.claude/` as untracked. Per-app `.gitignore` files exist (`apps/admin-web/.gitignore`, etc.) but they don't cover the repo root or sibling directories. Add a root `.gitignore` that covers monorepo-wide noise without duplicating the per-app rules.

2. **TanStack Router scans `*.test.tsx` inside `routes/`.** Adding `apps/admin-web/src/routes/_protected/rbac-redirect.test.tsx` (Plan 10-08, regression test) triggers a dev-server warning: `Route file "..." does not export a Route. This file will not be included in the route tree.` The test file works correctly (TanStack silently skips it), but the warning is noise and will recur for any future colocated route test. Add `routeFileIgnorePattern: /\.test\.tsx?$/` to the `tanstackRouter` plugin config in `apps/admin-web/vite.config.ts`.

Out of scope: per-app `.gitignore` consolidation, removing `.DS_Store` from already-tracked paths (none are tracked), or migrating the test file out of `routes/`.
</objective>

<tasks>

<task type="manual">
  <name>Task 1: Add root `.gitignore` for monorepo-wide noise</name>
  <files>.gitignore</files>
  <behavior>
    - File `.gitignore` exists at the repo root.
    - `git status` no longer reports `.DS_Store`, `apps/.DS_Store`, `node_modules/`, or `.claude/` as untracked.
    - The file does NOT duplicate rules already covered by per-app `.gitignore` files (e.g., `apps/admin-web/dist/`); it only covers root-level / cross-cutting paths.
    - Includes a short comment block explaining what the file is for so future maintainers don't add to the wrong file.
  </behavior>
  <action>
    Write `.gitignore` at the repo root with the following sections:
      - macOS noise: `.DS_Store` (matches `.DS_Store` and `apps/.DS_Store` thanks to gitignore's "match anywhere" default for paths without `/`).
      - Editor noise: `*.swp`, `*.swo`, `*~`, `.idea/`, `.vscode/`.
      - Dependency tree: `node_modules/` (root-level pnpm cache for tooling installs).
      - Claude Code per-project config: `.claude/` (GSD-installed agents/hooks/settings — auto-generated, user-specific).
      - Logs: `*.log`, `pnpm-debug.log*`, `yarn-debug.log*`, `npm-debug.log*`.
  </action>
  <verify>
    <automated>test -f .gitignore && git status --short | grep -Ev "^\?\? \.planning/" | grep -E "^\?\? (\.DS_Store|apps/\.DS_Store|node_modules/|\.claude/)" | wc -l | tr -d ' ' | grep -q '^0$'</automated>
  </verify>
  <done>
    - `.gitignore` exists at repo root.
    - `git status --short` shows no entries for `.DS_Store`, `apps/.DS_Store`, `node_modules/`, or `.claude/`.
    - `git check-ignore -v .DS_Store apps/.DS_Store node_modules .claude` reports a hit for each.
  </done>
</task>

<task type="manual">
  <name>Task 2: Exclude colocated `*.test.tsx` from TanStack Router scanning</name>
  <files>apps/admin-web/vite.config.ts</files>
  <behavior>
    - `tanstackRouter` plugin in `vite.config.ts` receives `routeFileIgnorePattern: /\.test\.tsx?$/` so `*.test.ts` and `*.test.tsx` files inside `src/routes/` are skipped.
    - `pnpm dev` no longer emits the warning `Route file ".../rbac-redirect.test.tsx" does not export a Route...`.
    - All existing routes still resolve correctly; route tree generation does not regress.
    - No other plugin options change.
  </behavior>
  <action>
    Edit `apps/admin-web/vite.config.ts`. Inside the `tanstackRouter({...})` call, add the line:

      routeFileIgnorePattern: /\.test\.tsx?$/,

    Place it adjacent to the existing `autoCodeSplitting`, `routesDirectory`, and `generatedRouteTree` options. Preserve project style (no semicolons, single quotes, 100-char width). Do not touch any other plugin or config field.
  </action>
  <verify>
    <automated>cd apps/admin-web && grep -q "routeFileIgnorePattern.*test\\.tsx" vite.config.ts && pnpm typecheck</automated>
  </verify>
  <done>
    - `vite.config.ts` contains `routeFileIgnorePattern: /\.test\.tsx?$/`.
    - `pnpm -F admin-web typecheck` passes.
    - Manual: `pnpm dev` (briefly) emits no warning about `rbac-redirect.test.tsx`.
    - `apps/admin-web/src/routeTree.gen.ts` is unchanged (the test file was already silently excluded; the explicit filter just removes the warning).
  </done>
</task>

</tasks>

<success_criteria>
- Two atomic commits (`chore: add root .gitignore`, `chore(admin-web): exclude *.test.tsx from TanStack Router scan`).
- `git status` clean of monorepo-wide noise after Task 1.
- Dev-server warning gone after Task 2.
- `pnpm -F admin-web typecheck` and `pnpm -F admin-web test` both still green.
- SUMMARY.md created with status: complete.
- STATE.md "Quick Tasks Completed" table updated.
</success_criteria>
