# Plan 008: Fix the lying README, sync CLAUDE.md with reality, add .env.example and a `check` script

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat <baseline SHA from plans/README.md>..HEAD -- README.md CLAUDE.md package.json`
> This plan documents the repo AS IT IS at execution time — check
> `plans/README.md` for which of plans 002/003/004/007 are DONE and document
> accordingly (details inline below).

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans/007-dependency-cleanup.md (dependency list accuracy); soft-depends on 002/003/004 (document their patterns only if landed)
- **Category**: docs / dx
- **Planned at**: 2026-06-12 (pre-git; baseline SHA in plans/README.md)
- **Reconciled at**: 2026-06-12 (executing against `main` @ `5ceb34b`; see Reconciliation)

## Reconciliation (2026-06-12 — executing against `main` at baseline `5ceb34b`)

**Context drift since planning.** Plans 002–007 are marked DONE in `plans/README.md` but live on **unmerged branches**; `main` is still at baseline. This worktree (off `main`) therefore contains **none** of their code. The plan originally keyed some edits off `plans/README.md` status — that is wrong here, because the status ("done") and the actual worktree code disagree.

**Reconciled rule: every conditional edit keys off whether the underlying code exists IN THIS WORKTREE, checked with a command — never off `plans/README.md`.**

Net effect on `main` today:
- **DO (stack-independent, true on `main` now)**: the README corrections in Step 1 *except the dependency line*; the full 8-dir `components/` map in CLAUDE.md (Step 2.1); the `bun run check` line in CLAUDE.md (Step 2.2); `.env.example` + the `check` script (Step 3).
- **LEAVE AS-IS**: README's dependency line — `zustand`, `react-hook-form`, `zod` are **still real dependencies on `main`** (007 unmerged), so line 14 is currently accurate. Do **not** remove them.
- **SKIP (code not in this worktree — verify with the checks in Step 2.3)**: all three CLAUDE.md conditional sentences (003 `PageState`, 004 lazy routes, 007 radix-monolith). Record the skip in NOTES.
- **DEFER to a post-merge pass** (out of scope here; see Maintenance): re-running the stack-dependent edits once 002–007 land on `main`.

## Why this matters

`README.md` is actively wrong in five places — wrong Tailwind major version, a config file that doesn't exist, a link to a file on one developer's machine, a superseded design rule, and a stale dependency list. CLAUDE.md (the contract both humans and AI agents execute against) documents only 4 of the 8 `components/` subdirectories, so agents place new components by stale rules. And two small DX gaps: the `VITE_API_BASE_URL` env var is undocumented (no `.env.example`), and there's no single `check` command gating typecheck+lint+format.

## Current state

- `README.md` (3,019 bytes, Russian) — the specific lies, verbatim:
  - Line 11: `- **Tailwind CSS 3** + CSS-переменные дизайн-токенов` — the project uses **Tailwind v4**, CSS-first via `@tailwindcss/vite`; there is **no** `tailwind.config.ts` (see `CLAUDE.md` "Styling" section, which is correct).
  - Line 14 lists `zustand`, `react-hook-form`, `zod` among the stack — after plan 007, zustand/RHF are gone; zod's presence depends on plan 010's outcome. Mirror the **current** `package.json`.
  - Line 23: `bun run typecheck     # tsc --noEmit` — actual script is `tsc -b --noEmit`; the scripts block also misses `test`/`check` if they exist by now.
  - Lines 45–46: «Подробное описание архитектуры … — в `~/.claude/plans/wondrous-swimming-bubble.md`» — machine-local path, unreachable for anyone else. Replace with a pointer to `CLAUDE.md`.
  - Line 51 (workflow step 2): «Извлекаются новые дизайн-токены (если есть) → `tailwind.config.ts` / `tokens.css`» — must say `src/styles/tokens.css` (raw values) + `src/styles/globals.css` (`@theme inline`).
  - Line 60 (workflow step 6): «Все hover/active/transition сохраняются 1:1 с исходным HTML» — superseded; CLAUDE.md's governing wording: faithful visual identity, clean responsive React, *not* a literal copy.
- `CLAUDE.md` "Layered component model" bullet documents `components/ui` and `components/{data,charts,icons}` only. Actual directories (verified): `src/components/{charts,data,feedback,icons,layout,modals,settings,ui}`. The four undocumented ones and their contents:
  - `layout/` — shared page-composition pieces: `Card.tsx` (+`CardHeader`/`CardLink`), `PageHeader.tsx`, `SectionHead.tsx`, `StatStrip.tsx`
  - `modals/` — the app-wide modal system: `ModalsProvider` + `modals-context.ts` + one file per dialog + shared `fields.tsx`
  - `feedback/` — `EmptyState.tsx`, `ErrorPage.tsx`, `RouteErrorBoundary.tsx` (+ `PageState.tsx` if plan 003 landed)
  - `settings/` — settings-page controls (`controls.tsx`, `ScrollspyNav.tsx`), shared by settings/system-settings/branch-settings pages
- `src/api/client.ts:5`: `const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api';` — the only env var; no `.env.example` exists. `.gitignore` already ignores `.env*` real files (a `.env.example` is NOT matched by those patterns — safe to commit).
- `package.json` scripts today: `dev`, `build`, `preview`, `typecheck` (`tsc -b --noEmit`), `lint` (`eslint . --max-warnings=0`), `format` (`prettier --write .`), plus `test`/`test:watch` if plan 002 landed.

## Commands you will need

| Purpose      | Command                | Expected on success |
|--------------|------------------------|---------------------|
| Typecheck    | `bun run typecheck`    | exit 0              |
| Lint         | `bun run lint`         | exit 0              |
| Format check | `bunx prettier --check .` | see Step 3       |
| New gate     | `bun run check`        | exit 0 (after Step 3) |

## Scope

**In scope**:
- `README.md`
- `CLAUDE.md` (surgical edits only — see boundaries below)
- `.env.example` (create)
- `package.json` (one script added)
- `plans/README.md` (status row)

**Out of scope** (do NOT touch):
- `CLAUDE.md` sections other than: the layer-model bullet list, the Commands block, and (conditionally) one line in the shadcn section + one line in the data-layer section. Do NOT rewrite the integration philosophy, styling docs, or anything else — they are correct and deliberately worded.
- `.prettierrc`, `eslint.config.js` — config is deliberate; no rule changes.
- `.gitignore` — already correct.
- Source code — zero `src/` changes in this plan.

## Git workflow

- Branch: `advisor/008-docs-dx` off `main`.
- Commits: (1) README rewrite, (2) CLAUDE.md sync, (3) `.env.example` + `check` script (+ the conditional format commit from Step 3, separate). Messages: `docs: …`, `chore: add check script and .env.example`.
- Do NOT push.

## Steps

### Step 1: Fix README.md

Apply exactly the six corrections from "Current state" (keep the document's existing Russian tone and structure):

1. Стек: `**Tailwind CSS v4** — CSS-first через плагин `@tailwindcss/vite`; файла `tailwind.config.ts` нет, токены в `src/styles/tokens.css` + `src/styles/globals.css``.
2. Dependency line: it must mirror current `package.json` `dependencies`. **On `main` it already does** — `zustand`, `react-hook-form`, `zod` are still declared, so line 14 is accurate. **Leave it unchanged; do NOT remove those three** (007, which removes them, is unmerged — see Reconciliation).
3. Scripts block: copy the actual `scripts` from `package.json`, including `check` (added in Step 3). On `main` there is **no** `test` script (002 unmerged) — do not invent one; list `dev`/`build`/`preview`/`typecheck`/`lint`/`format`/`check`.
4. Replace the `~/.claude/plans/…` sentence with: «Архитектура, конвенции и workflow интеграции шаблонов — в [CLAUDE.md](./CLAUDE.md).»
5. Workflow step 2 → `src/styles/tokens.css` (raw values) + `src/styles/globals.css` (`@theme inline`).
6. Workflow step 6 → «Интерактивные состояния (hover/active/focus/disabled) и все брейкпоинты реализуются по референсу — верность визуальному стилю, но чистый адаптивный React, не дословная копия HTML.»

**Verify**: `grep -n "tailwind.config\|Tailwind CSS 3\|wondrous-swimming-bubble\|1:1" README.md` → **0 matches**.

### Step 2: Sync CLAUDE.md

1. In the "Layered component model" section, extend the `components/` bullet to cover all 8 dirs using the one-line descriptions from "Current state" (keep the existing `data`/`charts`/`icons` wording; add `layout`, `modals`, `feedback`, `settings`).
2. In the Commands block, add `bun run check` (and `bun run test` if it exists).
3. **Conditional — key off whether the code exists IN THIS WORKTREE (run the check), NOT off `plans/README.md` status** (see Reconciliation). On `main` at baseline ALL THREE are SKIPPED; run the checks to confirm, then skip, and record each result in NOTES:
   - Add the **003** sentence ONLY if `test -f src/components/feedback/PageState.tsx` succeeds. (On `main`: absent → **skip**.) Sentence if added: pages handle `isPending`/`isError` via `PageLoading`/`PageError` from `components/feedback/PageState.tsx`.
   - Add the **004** sentence ONLY if `grep -q "lazy:" src/app/router.tsx` succeeds. (On `main`: routes are not lazy → **skip**.) Sentence if added: page routes load via the data-router `lazy:` property; new routes must follow it.
   - Add the **007** line ONLY if the individual packages are gone, i.e. `grep -q "@radix-ui/react-" package.json` **fails** (exit non-zero). (On `main`: 7 individual `@radix-ui/react-*` packages still present → **skip**.) Line if added: «Radix импортируется ТОЛЬКО из монолита `radix-ui` (не из индивидуальных `@radix-ui/react-*`); после `shadcn add` проверь, что CLI не добавил индивидуальные пакеты.»

**Verify**: `grep -c "feedback\|modals" CLAUDE.md` → ≥ 2; `bun run check` mentioned: `grep -n "bun run check" CLAUDE.md` → ≥ 1 (after Step 3 adds it — order Steps 3 then 2 if you prefer; both orders fine as long as both land).

### Step 3: Add `.env.example` and the `check` script

`.env.example`:

```
# База API. Пока backend отсутствует, хуки используют моки и значение не читается
# по-настоящему; при подключении backend задайте полный origin (например,
# https://api.clubcore.example). По умолчанию — относительный /api.
VITE_API_BASE_URL=/api
```

`package.json` scripts — add:

```json
"check": "tsc -b --noEmit && eslint . --max-warnings=0 && prettier --check ."
```

Before committing, run `bunx prettier --check .` alone:
- If it passes → done.
- If it fails on **≤ 10 files** → run `bun run format`, inspect `git diff --stat` (should be whitespace/quoting only), commit separately as `style: prettier pass`, then proceed.
- If it fails on **> 10 files** → do NOT mass-format; add the `check` script WITHOUT the prettier part (`tsc -b --noEmit && eslint . --max-warnings=0`), and report the file count as a STOP-adjacent note in your summary (the operator decides on a repo-wide format).

**Verify**: `bun run check` → exit 0.

## Test plan

No tests — docs and scripts. The machine gates: the greps in Steps 1–2 and a green `bun run check`.

## Done criteria

ALL must hold:

- [ ] `grep -n "Tailwind CSS 3\|wondrous-swimming-bubble" README.md` → 0 matches  *(corrected during review: the original criterion also grepped `tailwind.config`, but Step 1.1 deliberately writes the truthful phrase «файла `tailwind.config.ts` нет» — that mention is correct and expected, so it is NOT a failure)*
- [ ] README scripts block matches `package.json` scripts (manually compare — list both in your summary; on `main` = dev/build/preview/typecheck/lint/format/check, **no** test)
- [ ] README dependency line **unchanged** — still lists `zustand`/`react-hook-form`/`zod` (they remain deps on `main`; see Reconciliation)
- [ ] CLAUDE.md lists all 8 `components/` subdirectories
- [ ] **No** 003/004/007 conditional sentences added to CLAUDE.md — all skipped on `main`; confirm via the three Step 2.3 checks and report each result
- [ ] `.env.example` exists and `git check-ignore .env.example` exits **non-zero** (NOT ignored — it must be committable)
- [ ] `bun run check` → exit 0
- [ ] `git status --porcelain` → only in-scope files
- [ ] `plans/README.md` row — **SKIP** (reviewer maintains the index per dispatch preamble; do NOT edit it)

## STOP conditions

Stop and report back if:

- CLAUDE.md's current text differs materially from the quotes here (someone rewrote it — re-syncing needs fresh judgment, not this plan).
- The prettier check fails on more than 10 files (see Step 3 — partial completion is the defined behavior, report it).
- You feel the urge to "improve" CLAUDE.md's philosophy/styling sections — that's out of scope by design.

## Maintenance notes

- README's dependency list will drift again — it deliberately mirrors `package.json` loosely; keep it to the notable libraries.
- When plan 010 resolves zod and plan 011 adds routes, whoever executes them should touch README/CLAUDE.md per their own plans, not this one.
- Reviewer focus: CLAUDE.md diff is small and additive; README no longer references anything that doesn't exist in the repo.
- **Post-merge follow-up (deferred from this run — see Reconciliation)**: once `advisor/002`–`007` land on `main`, a second docs pass must (a) drop `zustand`/`react-hook-form`/`zod` from the README dependency line, (b) add the three CLAUDE.md sentences from Step 2.3 (003 `PageState`, 004 lazy routes, 007 radix-monolith), and (c) add `test`/`test:watch` to the README + CLAUDE.md script blocks. This run skipped all of these because the code is not on `main` yet.
