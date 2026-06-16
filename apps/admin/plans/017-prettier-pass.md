# Plan 017: Repo-wide Prettier pass (scoped to source) + restore `prettier --check` to `check`

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result. If a STOP condition
> occurs, stop and report — do not improvise. Do NOT edit `plans/README.md` if
> a reviewer dispatched you. **Run this plan LAST** if executing alongside
> plans 014–016 — it reformats the source files they touch.
>
> **Drift check (run first)**: `git diff --stat acb25f3..HEAD -- package.json .prettierrc`
> and `bunx prettier --check . 2>&1 | grep -c '\[warn\]'` (expect a few hundred
> at `acb25f3`). If `package.json`'s `check` script already contains `prettier`,
> STOP — this plan was already applied.

## Status

- **Priority**: P3
- **Effort**: S–M
- **Risk**: LOW (Prettier only changes whitespace/quotes/wrapping — it cannot change behavior; typecheck/lint/test gate it)
- **Depends on**: plan 008 (which shipped `check` without prettier, deferring this)
- **Category**: dx / tooling
- **Planned at**: `acb25f3`, 2026-06-12
- **Origin**: "Repo-wide Prettier debt" recorded in `plans/README.md`.

## Why this matters

`check` currently ships as `tsc -b --noEmit && eslint . --max-warnings=0` — prettier was omitted because the tree had drifted (≈335 unformatted files) and 8 `design/*.html` reference templates fail prettier's **parser** (e.g. `design/Load.html` has a malformed `</hh1>`). Without prettier in `check`, formatting silently rots. This plan establishes a `.prettierignore`, formats the **source** once, and restores `prettier --check` to `check` — so formatting is enforced going forward.

**Scope decision (made at planning, do not re-litigate):** Prettier is scoped to **project source + root config** only. The 80+ vendored skill docs (`.claude/`, `.agents/`), the hand-authored `plans/*.md`, `CLAUDE.md`/`README.md`, and the `design/` HTML templates are **excluded** via `.prettierignore` — they are not project source, several can't be parsed, and reformatting them is pure noise/risk. This mirrors how `eslint` is scoped to `**/*.{ts,tsx}`. (Verified @ `acb25f3`: all 8 prettier parse-errors are under `design/`.)

## Current state (verified @ `acb25f3`)

- `package.json` scripts (verbatim):
  ```json
  "format": "prettier --write .",
  "check": "tsc -b --noEmit && eslint . --max-warnings=0"
  ```
  (`check` has **no** prettier today.)
- No `.prettierignore` exists. `.prettierrc` exists (Prettier config; do not change its rules).
- `bunx prettier --check .` @ `acb25f3`: **8** `[error]` (parse failures, all `design/*.html`) + ~335 `[warn]` (unformatted), spanning `src/`, root configs, `.claude/`, `.agents/`, `plans/`, `*.md`.

## Commands you will need

| Purpose         | Command                      | Expected |
|-----------------|------------------------------|----------|
| Prettier check  | `bunx prettier --check .`    | green after Step 1+2 |
| Format          | `bun run format`             | rewrites source files |
| Typecheck       | `bun run typecheck`          | exit 0 |
| Lint            | `bun run lint`               | exit 0 |
| Tests           | `bun run test`               | all pass |
| New gate        | `bun run check`              | exit 0 (after Step 3) |
| Build           | `bun run build`              | exit 0 |

## Scope

**In scope**: `.prettierignore` (create), `package.json` (the `check` script + leave `format` as-is), the source/config files Prettier rewrites in Step 2, and the two doc lines describing the `check` gate (`README.md` `bun run check` comment + `CLAUDE.md` `bun run check` comment).

**Out of scope**: `.prettierrc` rules; any logic change; the excluded trees listed in `.prettierignore`; `plans/README.md`.

## Git workflow

- **Two commits**, in this order:
  1. `chore: add .prettierignore (exclude docs, design templates, vendored skills)` — just the `.prettierignore`.
  2. `style: prettier --write across source` — the bulk reformat (the large diff).
  3. `chore: restore prettier --check to the check script` — `package.json` + the two doc-line edits.
  (Keeping the reformat in its own commit keeps the other plans' diffs reviewable.)
- Do NOT push.

## Steps

### Step 1: Create `.prettierignore`

```
# build output / deps
node_modules
dist
*.tsbuildinfo

# package manager lockfile
bun.lock

# design reference templates — raw HTML, not maintained as source (some have invalid markup)
design

# vendored skill / agent docs — not project source, maintained verbatim
.claude
.agents

# planning docs — hand-authored prose, not prettier-managed
plans

# project prose docs
*.md
```

Verify the parse-errors are gone: `bunx prettier --check . 2>&1 | grep -c '\[error\]'` → **0**. If it's not 0, a parse-error file lives **outside** `design/` — STOP and report which (do NOT just add it to the ignore without flagging; a parse error in real source is a bug to surface).

### Step 2: Format the source

```
bun run format
```
Then inspect: `git diff --stat | tail -1` (expect a few hundred files, all under `src/` or root configs — NOT under `.claude/`, `.agents/`, `plans/`, `design/`). Spot-check a couple diffs are whitespace/quote/wrap only (`git diff src/lib/format.ts | head -40`).

Gate the reformat:
```
bun run typecheck && bun run lint && bun run test
```
All exit 0. If typecheck/lint/test **breaks** after a pure format, STOP and report — formatting must never change behavior (this would indicate a prettier/parser bug or a pre-existing latent issue).

### Step 3: Restore prettier to `check` + fix the doc lines

1. `package.json` `check`:
   ```json
   "check": "tsc -b --noEmit && eslint . --max-warnings=0 && prettier --check ."
   ```
2. `README.md` — the `bun run check` comment line (currently `# typecheck + lint (gate перед коммитом)`) → `# typecheck + lint + prettier --check (gate перед коммитом)`.
3. `CLAUDE.md` — the `bun run check` comment line (currently mentions "prettier excluded pending repo-wide format pass") → `# typecheck + lint + format check (run before committing)`. Also, if CLAUDE.md's prose elsewhere says prettier is excluded from `check`, update that sentence to say `check` now includes `prettier --check`.

Verify: `bun run check` → exit 0.

## Done criteria

- [ ] `.prettierignore` exists and lists `design`, `.claude`, `.agents`, `plans`, `*.md`
- [ ] `bunx prettier --check .` → exit 0 (clean)
- [ ] `grep -c "prettier --check" package.json` → 1 (in `check`)
- [ ] `bun run check` → exit 0
- [ ] `bun run test` → exit 0
- [ ] `bun run build` → exit 0
- [ ] `git diff --name-only acb25f3..HEAD` shows **no** reformatted files under `.claude/`, `.agents/`, `plans/`, `design/` (only source + configs + the 3 in-scope doc/config files)
- [ ] README + CLAUDE.md `check` comment lines mention prettier

## STOP conditions

- A prettier parse-`[error]` exists outside `design/` (real-source parse failure) — report it, don't bury it in the ignore.
- `typecheck`/`lint`/`test` fails after a pure `format` run — report (behavior must be untouched).
- `package.json`'s `check` already includes prettier (plan already applied) — STOP.
- The reformat touches files under the excluded trees — the `.prettierignore` is wrong; fix it before the style commit.

## Maintenance notes

- New top-level non-source trees should be added to `.prettierignore` as they appear.
- `format`/`check` now both honor `.prettierignore`, so they stay consistent automatically.
- If the team later wants docs formatted too, remove `*.md`/`plans` from the ignore in a separate dedicated pass.
