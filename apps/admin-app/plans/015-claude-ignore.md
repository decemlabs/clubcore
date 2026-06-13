# Plan 015: Stop ESLint/git from tripping over `.claude/` agent worktrees

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result. If a STOP condition
> occurs, stop and report. Do NOT edit `plans/README.md` if a reviewer
> dispatched you.
>
> **Drift check (run first)**: `git diff --stat acb25f3..HEAD -- eslint.config.js .gitignore`
> Mismatch with the excerpts below = STOP.

## Status

- **Priority**: P3
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plan 001 (git baseline)
- **Category**: dx / tooling
- **Planned at**: `acb25f3`, 2026-06-12
- **Origin**: surfaced post-integration; recorded in `plans/README.md` "acknowledged but not planned".

## Why this matters

ESLint's flat config has no `ignores` entry for `.claude/`. Whenever an agent worktree is left under `.claude/worktrees/agent-*/` (the `improve`/`execute` flow creates these), `eslint .` recurses into those scratch checkouts and lints duplicate copies of `src/` — and the vendored `components/ui/*` there trip `react-refresh/only-export-components` (the `components/ui/**` override doesn't match under the nested path), producing spurious `--max-warnings=0` failures that have nothing to do with the real code. It also risks committing scratch worktrees. A two-line durable fix removes the whole class of false failures.

## Current state (verified @ `acb25f3`)

- `eslint.config.js:8` (verbatim):
  ```js
  { ignores: ['dist', 'node_modules'] },
  ```
- `.gitignore` (verbatim, full file):
  ```
  node_modules
  dist
  .DS_Store
  .env
  .env.local
  .env.*.local
  *.log
  .vite
  .cache
  bun.lockb

  # npm lockfile (project uses bun; lock kept out of VCS)
  package-lock.json

  *.tsbuildinfo
  ```
- `.claude/` IS tracked (project skills must be committed — see plan 001); only the transient `.claude/worktrees/` should be git-ignored. ESLint, however, should ignore all of `.claude/**` (none of it is project source).

## Commands you will need

| Purpose | Command | Expected |
|---------|---------|----------|
| Lint    | `bun run lint` | exit 0 |
| Verify ignore | `git check-ignore .claude/worktrees/x` | prints the path (ignored) |

## Scope

**In scope**: `eslint.config.js` (the `ignores` array on line 8), `.gitignore` (append one line).

**Out of scope**: any other eslint rule/override, the tracked `.claude/` skill files themselves (do NOT git-rm them), any source file.

## Git workflow

- One commit: `chore: ignore .claude/ in eslint and git-ignore .claude/worktrees`.
- Do NOT push.

## Steps

### Step 1: ESLint ignore

In `eslint.config.js` change line 8 to add `.claude/**`:
```js
{ ignores: ['dist', 'node_modules', '.claude/**'] },
```

### Step 2: git-ignore the scratch worktrees

Append to `.gitignore` (keep existing content intact):
```
# transient agent worktrees (improve/execute flow)
.claude/worktrees/
```
Do NOT ignore all of `.claude/` — the skills are tracked.

## Done criteria

- [ ] `grep -c "\.claude/\*\*" eslint.config.js` → 1
- [ ] `grep -c "\.claude/worktrees/" .gitignore` → 1
- [ ] `git check-ignore .claude/worktrees/agent-test/src/x.ts` → prints the path (exit 0)
- [ ] `git check-ignore .claude/skills` → **no output, exit 1** (skills NOT ignored — still tracked)
- [ ] `bun run lint` → exit 0
- [ ] `git status --porcelain` → only `eslint.config.js`, `.gitignore`

## STOP conditions

- `eslint.config.js` line 8 or `.gitignore` differ from the excerpts (drift).
- Adding `.claude/**` to eslint ignores somehow changes the lint result on `src/` (it must not — `.claude/` holds no project source); if `bun run lint` output changes for `src/` files, report.

## Maintenance notes

- If the team moves agent worktrees elsewhere, update both ignores together.
- This is preventive: with no worktree present today, lint already passes; the fix matters the next time a worktree is left under the repo.
