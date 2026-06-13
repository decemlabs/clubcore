# Plan 011 (spike): Specify the Archive, Duplicates and Trainers-Archive screens

> **Executor instructions**: This is an INVESTIGATION plan. You will read the
> design templates and existing code, then write ONE integration spec — you
> will NOT modify any source file or build any screen. Follow the steps,
> fill every section of the deliverable, and update `plans/README.md` when
> done. If a STOP condition occurs, stop and report.
>
> **Drift check (run first)**: `git diff --stat <baseline SHA from plans/README.md>..HEAD -- src/app/routes.ts src/app/router.tsx src/components/data src/features/clients src/features/trainers`
> Drift doesn't block the spike — read changed files fresh.

## Status

- **Priority**: P3
- **Effort**: M (reading + writing; no production code)
- **Risk**: LOW (no code changes)
- **Depends on**: plans/001-init-git-baseline.md (to commit the doc)
- **Category**: direction
- **Planned at**: 2026-06-12 (pre-git; baseline SHA in plans/README.md)

## Why this matters

Three screens are fully designed but unbuilt: `design/Archive.html` (архив клиентов), `design/Duplicates.html` (дубликаты клиентов), `design/Trainers-Archive.html` (архив тренеров). Their route constants are already staged in `src/app/routes.ts:15-17,25` (`clientsArchive: '/clients/archive'`, `clientsDuplicates: '/clients/duplicates'`, `trainersArchive: '/trainers/archive'`) with the registration rule documented ("static sub-routes register BEFORE `:id` routes"). They share one interaction pattern — list + filters + selection + bulk action — that the codebase already has primitives for. This spike turns the templates into an implementation-ready spec, and surfaces the backend questions (soft-delete/restore/merge semantics) that are cheaper to answer before building than after.

## Current state

- Templates: `design/Archive.html`, `design/Duplicates.html`, `design/Trainers-Archive.html` (38 templates total in `design/`; also see `design/States.html` — the canonical empty/edge-state designs, already the cited source of `src/components/feedback/EmptyState.tsx`).
- Routing: `src/app/router.tsx` registers `/clients` then `/clients/:clientId` (via `ROUTES.client()`); the router file's header comment mandates static routes before `:id` routes — the spec must show exact insertion points. Note plan 004 may have converted routes to `lazy:` — read the live `router.tsx` and match whatever pattern is current.
- Reusable machinery (verified to exist):
  - `src/components/data/` — `DataTable.tsx`, `Pagination.tsx`, `BulkBar.tsx`, `FilterTabs.tsx`, `Toolbar.tsx`, `useTableSelection.ts`
  - The worked example of the whole pattern: `src/pages/clients/ClientsPage.tsx` (filter tabs + toolbar + table + bulk bar + selection + EmptyState) and `src/pages/clients/components/`
  - `src/features/clients/types.ts`, `src/mocks/clients.ts`, `src/features/clients/api.ts` (hook pattern), same for trainers
- Integration conventions: CLAUDE.md "Template integration workflow" (route mapping → token extraction → layer decomposition → mocks/types/hook → states & breakpoints). The project's governing philosophy: faithful visual identity, clean responsive React, NOT a literal HTML port.
- Navigation: `src/layouts/AppLayout/nav-items.ts` has NO links to these routes — entry points must come from the parent pages (check the templates for where they link from, e.g. a «Архив» action on the clients toolbar) — the spec must answer this.

## Commands you will need

| Purpose | Command | Expected |
|---------|---------|----------|
| Template inventory | `ls design/` | the 3 targets present |
| No-op guard | `bun run typecheck` | exit 0 before and after |

## Scope

**In scope** (the ONLY writes):
- `plans/research/archive-screens-spec.md` (create)
- `plans/README.md` (status row)

**Out of scope**:
- ANY `src/` file. No routes registered, no mocks added, no components built.
- Redesigning the templates — the spec adapts them to the codebase, not vice versa.

## Git workflow

- Branch: `advisor/011-archive-spike` off `main`. One commit: `docs: archive/duplicates screens integration spec`.
- Do NOT push.

## Steps

### Step 1: Read the three templates

For each of `design/Archive.html`, `design/Duplicates.html`, `design/Trainers-Archive.html`: catalog the screen's regions (header/summary, filters, table columns, row actions, bulk actions, modals/confirm dialogs, empty states), interaction states, and any design tokens not yet in `src/styles/tokens.css` (grep the HTML for hex colors / px values and spot-check against tokens.css). Compare against `design/States.html` for the empty-archive case.

### Step 2: Map to the codebase

For each screen, write the decomposition table: template region → target layer (`pages/<route>/components/…` vs reuse of `components/data/*` / `features/<domain>/components/…` vs a promotion). Explicitly answer:
- Which existing `components/data` pieces fit as-is, which need props added (e.g. does `DataTable` support the archive row-state styling?).
- Route registration snippet for `router.tsx` (static-before-`:id` placement, matching the file's current eager/lazy pattern).
- Entry points: where users reach each screen from (toolbar links on `/clients` & `/trainers`? template evidence) — exact components to touch.
- Breadcrumbs: the `handle: { breadcrumb: […] }` values, following the existing examples in `router.tsx`.

### Step 3: Data model & mocks

Spec the types/mocks per CLAUDE.md's workflow: `ArchivedClient` (or `Client` + `archivedAt`/`archiveReason` extension?), duplicate-pair/group shape (match fields the template shows: similarity hints, merge direction), hooks (`useArchivedClients`, `useClientDuplicates`, `useArchivedTrainers`) with query keys following `clientsKeys`-style factories, and the mock files to create. State explicitly whether `Client` gets extended or a parallel type is cleaner — recommend one.

### Step 4: Backend questions & bulk-action semantics

List the questions implementation will hit: soft-delete model (restore window? who can restore?), what «Удалить навсегда» means, merge semantics for duplicates (field-level winner selection or whole-record? what happens to the loser's visit history?), audit-trail expectations (the app has an audit page — do archive/merge actions log there?). For the mock phase, define what each bulk action does locally (e.g. optimistic cache update via `queryClient.setQueryData`).

### Step 5: Assemble the deliverable

`plans/research/archive-screens-spec.md` with sections: `## Screens overview` · `## Archive (clients)` · `## Duplicates` · `## Trainers archive` (each containing the Step-2 decomposition + Step-3 data spec) · `## Shared pattern & promotions` · `## Routing & entry points` · `## Backend questions` · `## Effort estimate` (per screen, S/M/L with one-line rationale) · `## Suggested build order`. Update `plans/README.md` row.

**Verify**: `grep -c "^## " plans/research/archive-screens-spec.md` → ≥ 9; `git status --porcelain` → only the two in-scope files; `bun run typecheck` → exit 0.

## Test plan

Not applicable (no code). Quality bar: an executor could build screen #1 from the spec without opening this conversation or re-deriving decisions.

## Done criteria

- [ ] `plans/research/archive-screens-spec.md` exists with all nine sections
- [ ] Each screen has: decomposition table, route snippet, entry-point answer, data/mock spec
- [ ] Backend questions section is non-empty and specific
- [ ] `git status --porcelain` → only deliverable + index
- [ ] `bun run typecheck` → exit 0

## STOP conditions

- Any of the three template files is missing or is not a full screen design (e.g. a fragment) — report what's actually there.
- The templates reveal a fourth dependent screen (e.g. a merge-wizard page) — note it in the spec's overview and continue; do NOT expand the spec to fully cover it.
- You catch yourself writing files under `src/` — revert; this spike is paper only.

## Maintenance notes

- The spec seeds 1–3 build plans (one per screen, Archive first — simplest, shares most with ClientsPage). Number them as new plans when commissioned.
- If plan 010's zod layer is adopted before these screens are built, the new entities' schemas should be written alongside their types — note this in the spec's data section.
- The unregistered `ROUTES` constants stay until the screens land (they're documented as phased — do not "clean them up").
