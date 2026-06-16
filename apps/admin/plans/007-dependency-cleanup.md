# Plan 007: Remove unused dependencies and consolidate on the radix-ui monolith

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat <baseline SHA from plans/README.md>..HEAD -- package.json src/app/providers.tsx`
> Also re-run every grep in "Current state" — they are the ground truth; if any
> "zero imports" claim no longer holds, that package leaves the removal list.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans/001-init-git-baseline.md
- **Category**: tech-debt
- **Planned at**: 2026-06-12 (pre-git; baseline SHA in plans/README.md)

## Why this matters

`package.json` declares three primitive-component libraries and four entirely unused packages. The actual usage (verified by import grep on 2026-06-12): 19 files import the **`radix-ui` monolith**; exactly one file imports an individual `@radix-ui/*` package; `zustand`, `react-hook-form`, and `next-themes` are imported nowhere. Dead and overlapping deps cost install time, security-advisory noise, and — worse — mislead contributors and AI agents into the wrong library (e.g. reaching for react-hook-form because it's "installed"). This plan removes what's dead and finishes the monolith consolidation. **`zod` stays** — its fate is decided by plan 010's spike.

## Current state

All verified 2026-06-12; re-verify each before acting:

- `grep -rn "from ['\"]zustand\|from ['\"]react-hook-form\|from ['\"]next-themes" src` → **no matches** (the string `next-themes` appears only in a comment in `src/components/ui/sonner.tsx:10`: «проект не использует next-themes»).
- `grep -rln "@radix-ui/" src` → exactly **one** file: `src/app/providers.tsx`. Its line 2 (verbatim): `import { TooltipProvider } from '@radix-ui/react-tooltip';` used as `<TooltipProvider delayDuration={200}>`.
- `grep -rln "from ['\"]radix-ui['\"]" src | wc -l` → **19** (the vendored shadcn primitives in `src/components/ui/` — e.g. `src/components/ui/tooltip.tsx:2`: `import { Tooltip as TooltipPrimitive } from "radix-ui"`). The monolith is the project's convention.
- `grep -rln "@base-ui" src` → exactly one file: `src/components/ui/combobox.tsx`. **`@base-ui/react` stays** (sole combobox implementation; replacing it is a separate decision).
- `package.json` dependencies to act on:
  - Remove (unused): `zustand`, `react-hook-form`, `next-themes`
  - Remove (superseded by the monolith, unused directly): `@radix-ui/react-dialog`, `@radix-ui/react-dropdown-menu`, `@radix-ui/react-separator`, `@radix-ui/react-slot`, `@radix-ui/react-tabs`, `@radix-ui/react-toggle-group`
  - Remove after Step 2's one-line migration: `@radix-ui/react-tooltip`
  - Keep: `zod` (plan 010 decides), `@base-ui/react`, `radix-ui`, everything else (`cmdk`, `vaul`, `sonner`, `react-day-picker`, `recharts`, `date-fns`, `lucide-react`, `react-router-dom`, `@tanstack/react-query`, `class-variance-authority`, `clsx`, `tailwind-merge`, `react`, `react-dom`)
- Package manager: **bun**; `bun.lock` is authoritative. `vite.config.ts` `optimizeDeps.include: ['sonner', 'vaul']` and `dedupe: ['react', 'react-dom']` are unrelated — leave them.

## Commands you will need

| Purpose   | Command             | Expected on success      |
|-----------|---------------------|--------------------------|
| Remove    | `bun remove <pkgs>` | exit 0, lockfile updated |
| Install   | `bun install`       | exit 0                   |
| Typecheck | `bun run typecheck` | exit 0                   |
| Lint      | `bun run lint`      | exit 0                   |
| Tests     | `bun run test`      | all pass (if 002 landed) |
| Build     | `bun run build`     | exit 0                   |

## Scope

**In scope**:
- `package.json`, `bun.lock`
- `src/app/providers.tsx` (one import + one JSX-name change)
- `plans/README.md` (status row)

**Out of scope** (do NOT touch):
- `zod` — pending plan 010. Do not remove even though it has zero imports today.
- `@base-ui/react` and `src/components/ui/combobox.tsx`.
- The 19 vendored `components/ui/*` files importing the monolith.
- `components.json` (shadcn config) — unchanged.
- `package-lock.json` on disk — gitignored npm-fallback artifact; ignore it (it will go stale; that's accepted).

## Git workflow

- Branch: `advisor/007-deps-cleanup` off `main`.
- Two commits: (1) providers.tsx migration, (2) dependency removals. Messages: `refactor: import TooltipProvider from radix-ui monolith`, `chore: remove unused deps (zustand, react-hook-form, next-themes, individual @radix-ui/*)`.
- Do NOT push.

## Steps

### Step 1: Re-verify every zero-import claim

Run all five greps from "Current state". Every package on the removal list must still have zero `src/` imports (quote-agnostic patterns as written).

**Verify**: outputs match "Current state". Any mismatch → that package stays; note it in the summary.

### Step 2: Migrate providers.tsx to the monolith

In `src/app/providers.tsx`, replace line 2 and the JSX usage:

```tsx
// БЫЛО:
import { TooltipProvider } from '@radix-ui/react-tooltip';
// ...
<TooltipProvider delayDuration={200}>

// СТАЛО:
import { Tooltip as TooltipPrimitive } from 'radix-ui';
// ...
<TooltipPrimitive.Provider delayDuration={200}>
```

(Closing tag becomes `</TooltipPrimitive.Provider>`. This matches the convention in `src/components/ui/tooltip.tsx:2`, which already aliases the monolith namespace the same way.)

**Verify**: `bun run typecheck` && `bun run lint` → exit 0; `grep -rln "@radix-ui/" src` → no matches.

### Step 3: Remove the packages

```
bun remove zustand react-hook-form next-themes @radix-ui/react-dialog @radix-ui/react-dropdown-menu @radix-ui/react-separator @radix-ui/react-slot @radix-ui/react-tabs @radix-ui/react-toggle-group @radix-ui/react-tooltip
```

**Verify**: exit 0; `grep -c "zustand\|react-hook-form\|next-themes\|@radix-ui/" package.json` → **0**; `grep -c '"zod"' package.json` → **1** (still present).

### Step 4: Full gate

```
bun install
bun run typecheck
bun run lint
bun run build
bun run test   # if the script exists
```

**Verify**: all exit 0. If the build fails with a module-resolution error naming a removed package, some file imports it in a way the greps missed — STOP, restore via `bun add <pkg>`, and report the importing file.

## Test plan

No new tests. The gate is: typecheck + lint + production build + (if present) the plan-002 suite, all green after removal. Tooltip behavior is exercised by any page render in the smoke suite (the provider wraps everything).

## Done criteria

ALL must hold:

- [ ] `grep -rn "@radix-ui/" src package.json` → 0 matches
- [ ] `grep -n "zustand\|react-hook-form\|next-themes" package.json` → 0 matches
- [ ] `grep -n '"zod"' package.json` → 1 match (kept)
- [ ] `bun run typecheck` && `bun run lint` && `bun run build` → all exit 0
- [ ] `bun run test` → exit 0 (if script exists)
- [ ] `git status --porcelain` → only `package.json`, `bun.lock`, `src/app/providers.tsx`, `plans/README.md`
- [ ] `plans/README.md` row updated

## STOP conditions

Stop and report back if:

- Any Step 1 grep finds an import the planning pass missed.
- `bun remove` errors, or `radix-ui`'s monolith doesn't export `Tooltip` with a `Provider` (it does in the vendored `tooltip.tsx` — if typecheck disagrees, the installed monolith version drifted; report instead of pinning).
- The build breaks in a way not fixed by restoring exactly one package.

## Maintenance notes

- **shadcn CLI gotcha**: future `bunx shadcn@latest add <component>` runs may re-add individual `@radix-ui/react-*` packages (the registry sometimes pins them). After any shadcn add, check `package.json` and prefer monolith imports; CLAUDE.md's shadcn section is where this rule should live (plan 008 updates docs — flag this line to it).
- `zod`'s keep/remove decision belongs to plan 010; record the outcome in `plans/README.md`.
- `@base-ui/react` exists solely for `combobox.tsx`. If a second base-ui consumer ever appears, fine; if the combobox gets rebuilt on radix primitives, remove the package then.
- Reviewer focus: the `providers.tsx` diff is exactly two lines + closing tag; `bun.lock` shrank; nothing else moved.
