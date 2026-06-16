# Plan 001: Put the repository under git and create the baseline commit

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: This repo has NO version control yet, so there
> is no SHA to diff against. Instead verify the "Current state" facts below
> (run the listed commands); on a mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: dx
- **Planned at**: no VCS existed at planning time — 2026-06-12. This plan creates the baseline all later plans stamp against.

## Why this matters

This repository contains ~31,800 lines of TypeScript/React across 305 source files, actively developed since late May 2026 — and it is **not a git repository**. There is no history, no rollback, no branching, and no way to review or revert any change. Every subsequent plan in `plans/` performs refactors that are only safe with a way to undo them. This plan creates the git baseline; it changes no source code.

## Current state

Verify each fact before proceeding:

- `git rev-parse --git-dir` from the repo root (`/Users/andre/Workspace/Development/clubcore-admin-frontend`) fails with "not a git repository". If it succeeds, STOP — someone initialized git since this plan was written.
- A correct `.gitignore` already exists at the repo root. Its current content (verbatim):

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
  ```

- Two TypeScript incremental-build artifacts sit in the root and are NOT yet ignored: `tsconfig.app.tsbuildinfo`, `tsconfig.node.tsbuildinfo`. They must not be committed.
- `bun.lock` (text lockfile) is authoritative per `CLAUDE.md` and MUST be committed. (`bun.lockb`, the old binary format, is already ignored — that is correct.)
- `package-lock.json` exists on disk. It is already gitignored; leave the file on disk (it supports the npm fallback described in `CLAUDE.md`) and do not commit it.
- The following are part of the project and MUST be committed: `src/`, `design/` (38 reference HTML templates — they are the design specs), `.claude/` (project skills), `.agents/`, `.mcp.json`, `components.json`, `skills-lock.json`, `CLAUDE.md`, `README.md`, `index.html`, `eslint.config.js`, `.prettierrc`, `vite.config.ts`, `tsconfig*.json`, `bun.lock`, `plans/`.

## Commands you will need

| Purpose   | Command                 | Expected on success |
|-----------|-------------------------|---------------------|
| Typecheck | `bun run typecheck`     | exit 0              |
| Lint      | `bun run lint`          | exit 0              |
| Git state | `git status --short`    | per step below      |

(Both typecheck and lint were verified green on 2026-06-12.)

## Scope

**In scope** (the only files you may modify/create):
- `.gitignore` (append two lines)
- `.git/` (created by `git init`)
- `plans/README.md` (status row + baseline SHA)

**Out of scope** (do NOT touch):
- Any file under `src/` — this plan changes zero source code.
- `package-lock.json` — leave on disk, ignored.
- Do NOT create a remote, do NOT push, do NOT configure CI. Baseline commit only.

## Git workflow

- This plan CREATES the git repo. Default branch: `main`.
- One single commit at the end. Message: `chore: initial commit — ClubCore admin frontend baseline`.
- Do not set or change `user.name`/`user.email` git config; use whatever the machine already has. If git complains that identity is unset, STOP and report (the operator must decide the committer identity).

## Steps

### Step 1: Confirm there is no existing repo (here or in a parent)

Run: `git rev-parse --git-dir 2>&1`

**Verify**: output contains `not a git repository`. If it prints a path instead, a repo exists somewhere up the tree — STOP and report which directory owns it.

### Step 2: Ignore the tsbuildinfo artifacts

Append to `.gitignore` (keep existing content intact):

```
*.tsbuildinfo
```

**Verify**: `tail -2 .gitignore` shows the new line; `grep -c "tsbuildinfo" .gitignore` → `1`.

### Step 3: Initialize the repository

Run: `git init -b main`

**Verify**: `git rev-parse --abbrev-ref HEAD` → `main`.

### Step 4: Stage everything and audit what got staged

Run: `git add -A`, then:

- `git status --porcelain | wc -l` → roughly 380–450 files (305 src files + design/ + config + plans/). If under 300 or over 600, investigate before committing.
- `git status --porcelain | grep -E "node_modules|^.. dist/|package-lock|tsbuildinfo|\.DS_Store" | wc -l` → **0**. If anything matches, the ignore rules failed — STOP.
- `git ls-files --cached --others --exclude-standard | grep -c "^bun.lock$"` after commit-stage: simpler check — `git status --porcelain | grep -c "bun.lock"` → `1` (bun.lock IS staged).

**Verify**: all three checks pass as stated.

### Step 5: Create the baseline commit

Run: `git commit -m "chore: initial commit — ClubCore admin frontend baseline"`

**Verify**: `git log --oneline` shows exactly 1 commit; `git status --short` is empty (except possibly untracked OS noise, which should be none).

### Step 6: Record the baseline SHA in the plans index

Run `git rev-parse --short HEAD` and write the result into `plans/README.md` in the "Baseline commit" line (the index has a placeholder for it). All later plans use this SHA for their drift checks.

**Verify**: `grep -n "Baseline commit" plans/README.md` shows the SHA, not the placeholder.

## Test plan

No tests — no code changed. The verification gates above are the test.

## Done criteria

ALL must hold:

- [ ] `git log --oneline | wc -l` → 1
- [ ] `git status --short` → empty output
- [ ] `git check-ignore node_modules dist package-lock.json tsconfig.app.tsbuildinfo` → prints all four paths (all ignored)
- [ ] `git ls-files | grep -c "^src/"` → ≥ 300
- [ ] `git ls-files | grep -c "^design/"` → ≥ 35
- [ ] `bun run typecheck` and `bun run lint` still exit 0 (nothing was modified)
- [ ] `plans/README.md` contains the baseline SHA and this plan's row says DONE

## STOP conditions

Stop and report back (do not improvise) if:

- A git repository already exists at or above the project root.
- Git identity (`user.name`/`user.email`) is not configured on the machine.
- The staged-file audit in Step 4 shows ignored artifacts being staged, or a file count far outside 380–450.
- `.gitignore` content differs from the verbatim block in "Current state" (drift — someone edited it since planning).

## Maintenance notes

- Every later plan (002–011) assumes this baseline exists; their drift checks diff against the SHA recorded in `plans/README.md`.
- Follow-ups deliberately NOT in this plan: remote/hosting choice, CI pipeline, pre-commit hooks, branch protection. Decide those after the team picks a host (GitHub/GitLab/other).
- A reviewer should scrutinize exactly one thing: the file list of the initial commit (`git show --stat HEAD | tail -30`) — nothing generated, nothing secret. There are no `.env*` files on disk as of planning (verified).
