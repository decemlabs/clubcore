---
quick_id: 260504-uws
slug: adminweb-cleanup
type: quick
date: 2026-05-04
status: complete
duration_min: 5
commits:
  - 40a2b3c
  - 064b35e
files_modified:
  - .gitignore
  - apps/admin-web/vite.config.ts
---

# Quick Task: adminweb-cleanup

## What changed

Two unrelated hygiene fixes surfaced during Phase 10 UAT, bundled into one quick task because they're both "remove noise from `pnpm dev` / `git status`":

1. **Root `.gitignore`** (`40a2b3c`) — covers `.DS_Store`, `apps/.DS_Store`, root-level `node_modules/`, `.claude/` (GSD-installed per-project Claude Code config), and editor temp files. Per-app `.gitignore` files (`apps/*/.gitignore`) were already comprehensive but didn't reach the repo root or sibling directories.

2. **TanStack Router test-file ignore** (`064b35e`) — added `routeFileIgnorePattern: '\\.test\\.tsx?$'` to the `tanstackRouter` plugin in `apps/admin-web/vite.config.ts`. Removes the warning `Route file ".../rbac-redirect.test.tsx" does not export a Route` that appeared after Plan 10-08 landed the colocated regression test. Future colocated route tests will be silently excluded the same way.

## Verification

- `git status --short` shows zero entries for `.DS_Store`, `apps/.DS_Store`, `node_modules/`, `.claude/`.
- `git check-ignore -v` confirms each path resolves to a `.gitignore:N` line.
- `pnpm -F admin-web typecheck` passes.
- `pnpm -F admin-web test` passes (78/78, no regression).
- `pnpm dev` starts cleanly with no `Route file ... does not export a Route` warning.

## Gotcha — non-obvious

`routeFileIgnorePattern` is parsed by a Zod schema as a `string` (regex source), not a `RegExp` literal. First attempt used `/\.test\.tsx?$/` and the dev server failed to start with:

```
ZodError: routeFileIgnorePattern: Expected string, received object
```

Fixed by switching to the string form `'\\.test\\.tsx?$'`. Documented inline in the commit body so the next person who edits this option doesn't repeat the mistake.

## Out of scope

- Per-app `.gitignore` consolidation (each app maintains its own; root only covers cross-cutting noise).
- Removing already-tracked `.DS_Store` files from history (none are tracked — verified via `git ls-files | grep DS_Store` returning empty).
- Migrating `rbac-redirect.test.tsx` out of `routes/` to a sibling test directory — left in place to honor the project convention that tests live next to source.
