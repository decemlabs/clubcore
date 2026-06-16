# Plan 013: Integration runbook — land the approved advisor stack into `main`

> **This is a human-run runbook, not an executor-model plan.** It lands the 9
> approved-but-unmerged `advisor/*` branches (plans 002–009, 012) onto `main`,
> which is still at baseline `5ceb34b`. Run it yourself, in order, on `main` in
> the real repo. After each merge, run the verification gate and do NOT proceed
> until it's green. The advisor (improve skill) does not run `merge`/`push`/
> `commit` on your branches — it produced and verified this runbook read-only.

## Status

- **Priority**: P1 (unblocks the value of all 12 plans)
- **Effort**: M (8 merges, 2 conflicts, ~2 reinstalls)
- **Risk**: MED — two real conflicts (both resolved below) + one test-interaction watch point at the 003 step
- **Planned at**: 2026-06-12, baseline `5ceb34b`
- **Conflict map verified** read-only via `git diff --name-only` (branch disjointness) and `git merge-tree` (authoritative conflict simulation) on 2026-06-12.

## ✅ Validated end-to-end (2026-06-12)

This runbook was **trial-run in a throwaway worktree** and independently re-verified by the advisor. Every step behaved as scripted: exactly two conflicts (ClientsPage.tsx @ step 2, package.json @ step 8), both resolutions as written; all gates green at every step; final integrated tree → `typecheck` ✓, `lint` ✓, **58/58 tests** ✓ (incl. router-smoke's 20), `bun run build` ✓. **The 003 watch point is a confirmed NON-issue** — mock data resolves synchronously, so the loading states never trip the smoke tests.

**Shortcut (saves the manual re-merge):** the validated integration already exists as a commit — branch `worktree-agent-a30dd722110db1c6c` at `5f243ea`, a descendant of baseline `5ceb34b`. Instead of re-running the 8 merges below by hand, you can pin and fast-forward:

```bash
git branch integration-stack 5f243ea     # pin the validated commit to a stable name (the worktree branch persists, but pin to be safe)
git switch main
git merge --ff-only integration-stack     # lands the ENTIRE validated tree — no conflicts to re-resolve
git add plans/ && git commit -m "docs(plans): advisor backlog + integration runbook"
bun install && bun run check && bun run test   # sanity (already verified green)
```

Cosmetic trade-off: the merge commits read `into worktree-agent-…`. If you want tidy merge-commit messages, run the manual sequence below instead — the two resolutions are now proven exact, so it's mechanical.

## Verified facts (why this sequence is correct)

- `main` is at baseline `5ceb34b`; nothing is merged. The advisor branches stack like this:
  - `advisor/002-vitest-baseline` — off `main`. Adds vitest + the test scaffolding, **refactors `ClientsPage.tsx`** (extracts sort logic to `features/clients/sort.ts`), adds `test`/`test:watch` scripts + vitest devDeps.
  - `advisor/004-route-splitting` — **stacked on 002** (contains 002). Its unique delta beyond 002: `src/app/router.tsx`, `src/app/router-smoke.test.tsx`, `src/test/setup.ts` (a global `Request` shim).
  - `advisor/005`, `006`, `007`, `009`, `012` — each **stacked on 002**. Their unique deltas beyond 002 are **fully disjoint** (charts / modals / providers+deps / primitives / SessionModal) — verified.
  - `advisor/003-query-states` — off `main` (NOT on 002). Adds `components/feedback/PageState.tsx` + loading/error states to 22 page files, **including `ClientsPage.tsx`**.
  - `advisor/008-docs-dx` — off `main`. Touches `README.md`, `CLAUDE.md`, `.env.example`, and adds a `check` script to `package.json`.
- **Only two files are touched by more than one independent change → only two conflicts:**
  1. **`src/pages/clients/ClientsPage.tsx`** — 002's sort-extraction (arrives via the 004 ff-merge) vs 003's query states. Conflicts when merging **003**.
  2. **`package.json`** — 002's `test`/`test:watch` scripts + 007's dependency pruning (in `main` by the time 008 merges) vs 008's `check` script. Conflicts when merging **008**.
- Everything else auto-merges. Order does not change the conflict count (both conflicts are inherent to 002↔003 and 002↔008 overlaps).

## Rollback (read before starting)

```bash
git rev-parse HEAD          # note this SHA — call it $BASE (should be 5ceb34b, or your Step-0 commit)
git tag pre-integration     # optional: a named anchor
```

- Mid-merge with conflict markers and you want to bail that one merge: `git merge --abort`.
- Bail the whole integration: `git reset --hard $BASE` (or `git reset --hard pre-integration`). This is safe — the `advisor/*` branches are untouched by this runbook; you can always restart.

## The gate (run after EVERY merge step)

```bash
bun run typecheck && bun run lint && bun run test
```

All three must exit 0 before the next merge. (`test` exists only after Step 1 lands 002. After Step 8, `bun run check` is also available as the consolidated typecheck+lint gate.)

---

## Step 0 — Pre-flight: clean the working tree

`main` currently has uncommitted planning docs (`plans/`, `plans/research/`). Commit them so the tree is clean before merging (no `advisor/*` branch touches `plans/`, so this never conflicts):

```bash
git switch main
git status                                   # confirm only plans/ is dirty
git add plans/
git commit -m "docs(plans): advisor backlog, reconciled 008, integration runbook"
git status                                   # MUST be clean now
git rev-parse HEAD                           # this is your $BASE for rollback
```

> If you'd rather not keep `plans/` on `main`, `git stash -u` instead — but committing is cleaner and preserves the record. Don't leave the tree dirty; a couple of the merges below will refuse to run otherwise.

## Step 1 — Land 002 + 004 (fast-forward)

```bash
git merge --ff-only advisor/004-route-splitting   # brings 002 AND 004 (linear FF)
bun install                                        # 002 added vitest + testing devDeps — sync node_modules
bun run typecheck && bun run lint && bun run test  # GATE
```

Expected: FF moves `main` to 004's tip; gate green (vitest suite from 002 runs).
If `--ff-only` refuses ("not possible to fast-forward"): your tree isn't clean (redo Step 0) or `main` already moved — STOP and reassess.

## Step 2 — Merge 003 (CONFLICT: `ClientsPage.tsx`) ⚠️

```bash
git merge advisor/003-query-states
# → CONFLICT (content): src/pages/clients/ClientsPage.tsx
```

**Resolve `src/pages/clients/ClientsPage.tsx`** — combine both sides. The conflict is in the import block (and around the removed sort helpers). The resolved file must:

- Use these imports at the top (this is the whole manual part):
  ```tsx
  import { useMemo, useState } from 'react';
  import { useNavigate } from 'react-router-dom';
  import { ROUTES } from '@/app/routes';
  import { useClients } from '@/features/clients/api';
  import { PageLoading, PageError } from '@/components/feedback/PageState';   // ← from 003
  import type { ClientFilter, ClientSort, ClientSortKey } from '@/features/clients/types'; // ← from 002 (NO `Client`)
  import { compare, DEFAULT_DIR } from '@/features/clients/sort';            // ← from 002
  // …the rest of the existing imports (DataTable, Pagination, useTableSelection, ClientCard, columns, EmptyState) unchanged
  ```
- **NOT** contain an inline `DEFAULT_DIR` const or `compare()` function (002 deleted them; they now live in `@/features/clients/sort`). If the conflict left a copy, delete it.
- **Drop the `Client` type import** — it's unused once the inline `compare` is gone (002 ships exactly this and is lint-green at `--max-warnings=0`, so this is safe).
- Keep 003's runtime changes (these auto-merge, just don't undo them):
  ```tsx
  const { data, isPending, isError, refetch } = useClients();
  // …
  if (isPending) return <PageLoading />;
  if (isError || !data) return <PageError onRetry={() => void refetch()} />;
  ```

Then:

```bash
# remove ALL conflict markers (<<<<<<<, =======, >>>>>>>) first
git add src/pages/clients/ClientsPage.tsx
git commit --no-edit                                # completes the merge
bun run typecheck && bun run lint && bun run test   # GATE
```

> **Watch point (test interaction) — VALIDATED as a non-issue.** 003 makes pages render `<PageLoading/>` while a query is pending; the trial integration confirmed the router-smoke suite (20 tests) **stays green** because mock data resolves synchronously. No action needed. (Kept here only so that if a future change makes mocks async, you know where to look: wrap smoke assertions in `await screen.findBy…`/`waitFor`. Never weaken assertions to force green.)

## Step 3 — Merge 005 (clean)

```bash
git merge advisor/005-chart-guards                  # disjoint: chart files only
bun run typecheck && bun run lint && bun run test    # GATE
```

## Step 4 — Merge 006 (clean)

```bash
git merge advisor/006-modal-reset                   # disjoint: modal files only
bun run typecheck && bun run lint && bun run test    # GATE
```

## Step 5 — Merge 007 (clean, but REINSTALL) 

```bash
git merge advisor/007-deps-cleanup                  # disjoint: providers.tsx + package.json/bun.lock
bun install                                          # 007 PRUNES deps (zustand, react-hook-form, next-themes, individual @radix-ui/react-*) — resync
bun run typecheck && bun run lint && bun run test    # GATE
```

> After this, `package.json` `dependencies` = the 18-package pruned set (zod kept per plan 010). If typecheck/lint fails with "cannot find module", something still imports a removed dep — that would be a real find; STOP and report.

## Step 6 — Merge 012 (clean)

```bash
git merge advisor/012-session-modal-reset           # disjoint: SessionModal.tsx only
bun run typecheck && bun run lint && bun run test    # GATE
```

## Step 7 — Merge 009 (clean)

```bash
git merge advisor/009-primitive-consolidation       # disjoint: Panel/MetricTile/callout/fields + parts.tsx
bun run typecheck && bun run lint && bun run test    # GATE
```

## Step 8 — Merge 008 (CONFLICT: `package.json`) ⚠️

```bash
git merge advisor/008-docs-dx
# → CONFLICT (content): package.json   (README.md, CLAUDE.md, .env.example merge clean)
```

**Resolve `package.json`:**
- **`dependencies`**: keep **`main`'s side (HEAD)** — the pruned 18-package set from 007. (008 branched off baseline so its side still lists the removed deps; discard that side for the deps block.)
- **`scripts`**: keep **all** of them — union `test`/`test:watch` (ours) with `check` (theirs). Final block:
  ```json
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "typecheck": "tsc -b --noEmit",
    "lint": "eslint . --max-warnings=0",
    "format": "prettier --write .",
    "test": "vitest run",
    "test:watch": "vitest",
    "check": "tsc -b --noEmit && eslint . --max-warnings=0"
  },
  ```

Then:

```bash
git add package.json
git commit --no-edit
bun run check && bun run test                        # GATE (check = typecheck + lint; plus tests)
```

## Step 9 — Final verification & cleanup

```bash
bun run typecheck && bun run lint && bun run test    # full gate, integrated tree
bun run build                                        # optional: confirm production build (004's code-splitting)
git log --oneline 5ceb34b..HEAD                      # review the integrated history
```

Cleanup (optional, after you're satisfied):

```bash
# remove the now-merged worktrees (branches persist until you delete them)
git worktree list
git worktree remove .claude/worktrees/agent-XXXX     # for each advisor worktree
git branch -d advisor/002-vitest-baseline advisor/003-query-states advisor/004-route-splitting \
              advisor/005-chart-guards advisor/006-modal-reset advisor/007-deps-cleanup \
              advisor/008-docs-dx advisor/009-primitive-consolidation advisor/012-session-modal-reset
git branch -d advisor/011-archive-spike              # redundant per the index
```

## Done criteria

- [ ] `git log --oneline 5ceb34b..HEAD` shows all 9 branches merged
- [ ] `git status` clean
- [ ] `bun run check` → exit 0
- [ ] `bun run test` → exit 0
- [ ] `bun run build` → succeeds
- [ ] `package.json` has the union scripts block (test, test:watch, check) and the pruned deps
- [ ] `ClientsPage.tsx` has no inline `compare`/`DEFAULT_DIR` and no `Client` import, renders `PageLoading`/`PageError`

## After integration — the two deferred follow-ups become runnable

Both were deferred from plan 008 because their target code wasn't on `main` yet. With the stack landed:

1. **Docs top-up** (small): in `README.md` drop `zustand`/`react-hook-form` from the dependency line (keep `zod`; note `next-themes` is also gone), add `test`/`test:watch` to both the README and CLAUDE.md script blocks, and add the three CLAUDE.md pattern sentences (003 `PageState`, 004 lazy `lazy:` routes, 007 radix-monolith-only).
2. **Repo-wide Prettier pass** (small): add `design/**` (the raw HTML templates — 8 of them fail prettier's parser) to a `.prettierignore`, run `bun run format` once, commit as a single `style:` pass, then restore `prettier --check .` to the `check` script.

Ask the improve advisor to turn either into a plan, or do them inline — they're both small and low-risk.
