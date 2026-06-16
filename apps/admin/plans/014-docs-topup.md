# Plan 014: Post-integration docs top-up (README deps + test scripts + CLAUDE.md pattern sentences)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving on. If a
> STOP condition occurs, stop and report — do not improvise. Do NOT edit
> `plans/README.md` if a reviewer dispatched you (they maintain the index).
>
> **Drift check (run first)**: `git diff --stat acb25f3..HEAD -- README.md CLAUDE.md package.json`
> If any changed since `acb25f3`, compare the excerpts below against the live
> code before proceeding; on a mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plan 013 (the advisor stack must be on `main` — it is, @ `acb25f3`)
- **Category**: docs
- **Planned at**: `acb25f3`, 2026-06-12
- **Origin**: deferred from plan 008's Reconciliation; unblocked once 002/003/004/007 landed on `main`.

## Why this matters

Plan 008 documented the repo while the advisor stack was still unmerged, so three doc edits were deliberately deferred. The stack is now on `main`, so the docs are once again out of sync with reality: `README.md` advertises two libraries that plan 007 deleted, neither README nor CLAUDE.md mention the test runner that plan 002 added, and CLAUDE.md teaches none of the three patterns the stack introduced (query states, lazy routes, radix-monolith-only). Contributors and AI agents execute against these docs — stale docs mean wrong code.

## Current state (verified @ `acb25f3`)

- `README.md:14` (verbatim) — lists deps removed by plan 007:
  ```
  - **Recharts**, **date-fns** (ru), **lucide-react**, **zustand**, **react-hook-form**, **zod**
  ```
  `zustand` and `react-hook-form` are **gone** from `package.json` (verify: `grep -c "zustand\|react-hook-form" package.json` → 0). `zod` **stays** (plan 010 verdict: KEEP).
- `README.md:16-27` — the scripts block lists `dev`/`build`/`preview`/`typecheck`/`lint`/`format`/`check` but **not** `test`/`test:watch` (both exist in `package.json` — verify: `grep -c '"test"' package.json` → 1).
- `README.md:36` — structure block says `components/   # ui / data / charts / icons` (only 4 of 8 dirs). Optional fix (see Step 1.4).
- `CLAUDE.md:14-21` — the Commands block lists the same scripts, **no** `test`/`test:watch`.
- `CLAUDE.md:24` (verbatim): `There is no test runner configured yet (tests are deferred per the project plan).` — now **false** (vitest landed in plan 002; 5 test files, 58 tests).
- `CLAUDE.md:34` — Routing paragraph; says nothing about lazy routes (plan 004 made all page routes `lazy:`).
- `CLAUDE.md:47` — Data-layer paragraph; says nothing about the loading/error components (plan 003 added `components/feedback/PageState.tsx`: `PageLoading` + `PageError`).
- `CLAUDE.md:55` — shadcn paragraph; says nothing about the radix-monolith-only convention (plan 007 consolidated on the `radix-ui` monolith).

## Commands you will need

| Purpose   | Command             | Expected |
|-----------|---------------------|----------|
| Typecheck | `bun run typecheck` | exit 0   |
| Lint      | `bun run lint`      | exit 0   |
| Grep gates| see Done criteria   | as stated|

## Scope

**In scope**: `README.md`, `CLAUDE.md`. (Plan 017 owns the `check`-script doc lines — leave any wording about prettier inside `check` to it; do not touch those lines here.)

**Out of scope**: `package.json` (no script changes here — 002/007 already shipped them), any source file, `plans/README.md` (reviewer maintains it).

## Git workflow

- One commit: `docs: sync README/CLAUDE.md with landed advisor stack (deps, test scripts, patterns)`.
- Do NOT push.

## Steps

### Step 1: README.md

1. **Deps line (14)** → remove `zustand` and `react-hook-form`, keep `zod`:
   ```
   - **Recharts**, **date-fns** (ru), **lucide-react**, **zod**
   ```
2. **Scripts block** — add two lines after the `check` line (keep alignment/comment style):
   ```
   bun run test          # vitest run (юнит + smoke-тесты роутов)
   bun run test:watch    # vitest в watch-режиме
   ```
3. Leave the `bun run check` comment line **as plan 017 will set it** — do not edit it in this plan.
4. **(Optional, low-risk)** structure block (36): change `components/   # ui / data / charts / icons` →
   `components/   # ui / data / charts / icons / layout / modals / feedback / settings`. Do it if trivial; skip if the surrounding ASCII alignment makes it fiddly — not a gate.

### Step 2: CLAUDE.md

1. **Commands block** — add after the `bun run check` line:
   ```
   bun run test          # vitest run (unit + route smoke tests)
   bun run test:watch    # vitest in watch mode
   ```
2. **Line 24** — replace the false sentence with the truth:
   > Tests run on **vitest** (`bun run test`): unit tests for pure logic (`src/lib/format.test.ts`, `src/features/clients/sort.test.ts`) plus a route smoke suite (`src/app/router-smoke.test.tsx`) that renders every registered route. `bun test` (Bun's own runner) will NOT pick up the vitest config — always use `bun run test`.
3. **Routing paragraph (34)** — append one sentence:
   > Page routes load lazily via the data-router `lazy:` property (`app/router.tsx`); new page routes MUST follow the same `lazy: async () => ({ Component: (await import('…')).XxxPage })` shape so the route stays code-split.
4. **Data-layer paragraph (47)** — append one sentence:
   > Pages render `<PageLoading />` while `isPending` and `<PageError onRetry={…} />` on `isError` (both from `components/feedback/PageState.tsx`) — new data-driven pages must handle these states, not just the success branch.
5. **shadcn paragraph** — add a bullet (or sentence) stating the convention:
   > Radix is imported ONLY from the `radix-ui` monolith (e.g. `import { Tooltip as TooltipPrimitive } from 'radix-ui'`), never from individual `@radix-ui/react-*` packages. After any `shadcn add`, check `package.json` and convert any individual `@radix-ui/*` the CLI pinned back to the monolith.

Keep all wording in the doc's existing voice (CLAUDE.md is English prose; README is Russian).

## Done criteria

- [ ] `grep -c "zustand\|react-hook-form" README.md` → **0**
- [ ] `grep -c "zod" README.md` → ≥ 1 (kept)
- [ ] `grep -c "bun run test" README.md` → ≥ 1 AND `grep -c "bun run test" CLAUDE.md` → ≥ 1
- [ ] `grep -c "There is no test runner configured yet" CLAUDE.md` → **0**
- [ ] `grep -c "PageState\|PageLoading" CLAUDE.md` → ≥ 1
- [ ] `grep -c "lazy:" CLAUDE.md` → ≥ 1
- [ ] `grep -c "radix-ui" CLAUDE.md` → ≥ 1 (monolith convention)
- [ ] `bun run typecheck` && `bun run lint` → exit 0 (no source touched, but confirm nothing odd)
- [ ] `git status --porcelain` → only `README.md`, `CLAUDE.md`

## STOP conditions

- README/CLAUDE.md text differs materially from the excerpts (someone rewrote them since `acb25f3`).
- `package.json` does NOT contain a `test` script (plan 002 not actually on `main`) — then the test-script claims are wrong; report.

## Maintenance notes

- These docs drift whenever deps or patterns change; treat them as living. Plan 017 owns the `check`-script line wording (it adds prettier to `check`).
