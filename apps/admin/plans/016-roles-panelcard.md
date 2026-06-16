# Plan 016: Migrate the last heavy-Panel duplicate (roles `PanelCard`) to the shared `Panel`

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result. If a STOP condition
> occurs, stop and report — do not improvise. Do NOT edit `plans/README.md` if
> a reviewer dispatched you.
>
> **Drift check (run first)**: `git diff --stat acb25f3..HEAD -- src/pages/roles/components/parts.tsx src/pages/roles/RolesPage.tsx src/components/layout/Panel.tsx`
> Mismatch with the excerpts below = STOP.

## Status

- **Priority**: P3
- **Effort**: S
- **Risk**: LOW (visual — but the two shells are byte-identical, so the rendered DOM is unchanged)
- **Depends on**: plan 009 (created the shared `components/layout/Panel`)
- **Category**: tech-debt
- **Planned at**: `acb25f3`, 2026-06-12
- **Origin**: surfaced during plan 009; left because `PanelCard` wasn't in 009's inventory. It is the one remaining true duplicate of the shared heavy Panel.

## Why this matters

`src/pages/roles/components/parts.tsx` defines `PanelCard` with a shell that is **byte-identical** to the shared `Panel` (`components/layout/Panel.tsx`, promoted in plan 009). Two copies of the same shell drift independently — a radius or shadow tweak lands in one and not the other. CLAUDE.md's "promote at second use" rule plus plan 009 already made `Panel` the canonical home; this finishes the job. Note `PcHead` (roles-specific head with a count badge) is a **different** component and stays.

## Current state (verified @ `acb25f3`)

- **Shared target** — `src/components/layout/Panel.tsx` exports `Panel`:
  ```tsx
  export function Panel({ className, children }: { className?: string; children: ReactNode }) {
    return (
      <div className={cn('overflow-hidden rounded-[18px] border-[0.5px] border-border bg-surface shadow-2', className)}>
        {children}
      </div>
    );
  }
  ```
- **Duplicate to remove** — `src/pages/roles/components/parts.tsx:62-68` (verbatim):
  ```tsx
  export function PanelCard({ children, className }: { children: ReactNode; className?: string }) {
    return (
      <div className={cn('overflow-hidden rounded-[18px] border-[0.5px] border-border bg-surface shadow-2', className)}>
        {children}
      </div>
    );
  }
  ```
  The shell string is **identical** to `Panel`'s. `PanelCard`'s only export-consumer is `RolesPage.tsx`.
- **`PcHead`** (`parts.tsx:70-77`) — roles-specific, KEEP unchanged. It is NOT a duplicate of `Panel`'s `PanelHead` (it renders a count badge, not an action slot).
- **Call sites** — `src/pages/roles/RolesPage.tsx`:
  - `:14` import: `import { AvatarStack, PanelCard, PcHead, RoleIco, Seg } from './components/parts';`
  - `:86`/`:103` — `<PanelCard>` … `</PanelCard>` (no `className`)
  - `:190`/`:314` — `<PanelCard>` … `</PanelCard>` (no `className`)
  - No `<PanelCard className=…>` usage exists (both are bare), so a plain symbol swap is exact.

## Commands you will need

| Purpose   | Command             | Expected |
|-----------|---------------------|----------|
| Typecheck | `bun run typecheck` | exit 0   |
| Lint      | `bun run lint`      | exit 0   |
| Tests     | `bun run test`      | all pass (roles route is in the smoke suite) |

## Scope

**In scope**: `src/pages/roles/components/parts.tsx` (delete `PanelCard`, keep everything else), `src/pages/roles/RolesPage.tsx` (swap import + 2 tag pairs).

**Out of scope**: `PcHead` and every other export in `parts.tsx`; `components/layout/Panel.tsx` (do not modify the shared component); any other page; `branches/parts.tsx` `BranchCard` (bespoke domain card — leave it, per plan 009).

## Git workflow

- One commit: `refactor: migrate roles PanelCard to shared components/layout/Panel`.
- Do NOT push.

## Steps

### Step 1: Remove the duplicate

In `src/pages/roles/components/parts.tsx`, delete the `PanelCard` function (lines 62-68). Keep the `/* ---------- Panel shell ---------- */` comment only if `PcHead` still reads well under it — optionally relabel to `/* ---------- Panel head ---------- */`. Keep `PcHead` and all other exports untouched. If `ReactNode` becomes an unused import after the deletion, check whether other code in the file still uses it (`PcHead` does not return children typed as `ReactNode`, but other exports may) — only remove the `ReactNode` import if `grep -c "ReactNode" parts.tsx` → 0 after the edit; otherwise leave it.

### Step 2: Point RolesPage at the shared Panel

In `src/pages/roles/RolesPage.tsx`:
1. Remove `PanelCard` from the `./components/parts` import (line 14):
   ```tsx
   import { AvatarStack, PcHead, RoleIco, Seg } from './components/parts';
   ```
2. Add the shared import (place it with the other `@/components/...` imports, matching the file's existing import ordering):
   ```tsx
   import { Panel } from '@/components/layout/Panel';
   ```
3. Replace all four tags: `<PanelCard>` → `<Panel>` and `</PanelCard>` → `</Panel>` (lines ~86/103 and ~190/314). `grep -c "PanelCard" src/pages/roles/RolesPage.tsx` → 0 afterwards.

### Step 3: Verify

`bun run typecheck` && `bun run lint` && `bun run test` → all exit 0.

## Done criteria

- [ ] `grep -c "PanelCard" src/pages/roles/components/parts.tsx` → 0
- [ ] `grep -c "PanelCard" src/pages/roles/RolesPage.tsx` → 0
- [ ] `grep -c "function PcHead" src/pages/roles/components/parts.tsx` → 1 (kept)
- [ ] `grep -c "from '@/components/layout/Panel'" src/pages/roles/RolesPage.tsx` → 1
- [ ] `bun run typecheck` && `bun run lint` && `bun run test` → all exit 0
- [ ] `git status --porcelain` → only `parts.tsx`, `RolesPage.tsx`

## STOP conditions

- Excerpts don't match live code (drift) — especially if a `<PanelCard className=…>` usage exists (then it still maps cleanly to `<Panel className=…>`, but report it so the reviewer knows the diff is larger).
- The shared `Panel` shell string differs from `PanelCard`'s — if they are NOT byte-identical, the swap would be a visible change; STOP and report the diff.
- Removing `PanelCard` reveals another importer beyond `RolesPage.tsx` (`grep -rn "PanelCard" src` should list only `parts.tsx` + `RolesPage.tsx`) — report any extra importer.

## Maintenance notes

- After this, the only remaining shells sharing the heavy-Panel look are intentional bespoke cards (`branches` `BranchCard`) — leave them.
- `src/pages/trainer/components/shared.tsx` also exports a `Panel`, but it wraps the **light** `Card`, not this heavy shell — a name collision only; out of scope here.
