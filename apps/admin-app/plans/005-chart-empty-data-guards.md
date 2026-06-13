# Plan 005: Guard chart components against empty datasets (NaN/-Infinity rendering)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat <baseline SHA from plans/README.md>..HEAD -- src/pages/dashboard/components/RevenueChart.tsx src/pages/trainers/components/EarningsCard.tsx src/pages/plans/components/SalesChart.tsx`
> On any change, compare the excerpts below against the live code; mismatch = STOP.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans/001-init-git-baseline.md (recommended: 002 for the test gate)
- **Category**: bug
- **Planned at**: 2026-06-12 (pre-git; baseline SHA in plans/README.md)

## Why this matters

Three chart components compute `Math.max(...arr)` / `Math.min(...arr)` on data arrays and divide by the results. On an empty array, JS spread-math returns `-Infinity`/`Infinity`, averages become `NaN`, and the values flow silently into Recharts axis domains and CSS percentage widths — a blank or visually corrupted chart with no error anywhere. Mock data is never empty today, so this is invisible; the first backend response with an empty period (new club, filtered range) breaks these cards silently. The fix is small, mechanical guards that render the project's existing `EmptyState` inside the card shell.

## Current state

Authoritative list of spread-math sites (`grep -rn "Math\.max(\.\.\.\|Math\.min(\.\.\." src` — exactly these five, verified 2026-06-12):

1. `src/pages/dashboard/components/RevenueChart.tsx:54-58` (and the domain at `:107`):

   ```tsx
   const values = points.map((p) => p.value);
   const min = Math.min(...values);
   const max = Math.max(...values);
   const avg = values.reduce((s, v) => s + v, 0) / values.length;
   const pad = (max - min) * 0.12 || max * 0.1;
   // ...
   <YAxis hide domain={[Math.max(0, min - pad), max + pad]} />
   ```

   `points` comes from `data.series[period].points` (`RevenuePoint[]` — can be empty by type). The component's JSX shell is `<DashboardCard title={series.title} subtitle={series.rangeLabel} action={<MiniSegmented … />} className="md:col-span-2 xl:col-span-1">` (imported from `./shared`).

2. `src/pages/trainers/components/EarningsCard.tsx:25-26` (and the division at `:40`):

   ```tsx
   const maxRev = Math.max(...data.rows.map((r) => r.revenue));
   const maxPt = Math.max(...data.rows.map((r) => r.ptCount));
   // ...
   const barPct = unit === 'rub' ? (r.revenue / maxRev) * 100 : (r.ptCount / maxPt) * 100;
   ```

   Shell: `<Card as="section" …><CardHeader title="Выручка с тренеров · апрель" …/>` from `@/components/layout/Card`. Note: even with non-empty rows, all-zero revenue makes `maxRev = 0` → division by zero.

3. `src/pages/plans/components/SalesChart.tsx:14-16` (and the division at `:23`):

   ```tsx
   const values = data.months.map((m) => (unit === 'count' ? m.count : m.revenueK));
   const max = Math.max(...values);
   // ...
   const h = (values[i]! / max) * 92;
   ```

   Shell: `<Card>` from `@/components/layout/Card`. Same all-zero division hazard.

- **Reusable empty state**: `src/components/feedback/EmptyState.tsx` — props `{ icon?, title, message?, action?, className? }`.
- Conventions: Russian strings inline; semantic Tailwind tokens; `cn()` for class composition.

## Commands you will need

| Purpose   | Command             | Expected on success |
|-----------|---------------------|---------------------|
| Typecheck | `bun run typecheck` | exit 0              |
| Lint      | `bun run lint`      | exit 0              |
| Tests     | `bun run test`      | all pass            |

## Scope

**In scope**:
- The three component files above
- `src/pages/dashboard/components/RevenueChart.test.tsx` (create, if plan 002 landed)
- `plans/README.md` (status row)

**Out of scope** (do NOT touch):
- Mock data files — do not "fix" this by guaranteeing non-empty mocks; the guard must live in the components.
- Other chart components without spread-math (the grep above is the authoritative list — if you find more sites, report them, don't expand scope silently).
- `DashboardCard`, `Card`, `EmptyState` internals.

## Git workflow

- Branch: `advisor/005-chart-guards` off `main`.
- One commit per component + one for tests. Messages: `fix: guard <Component> against empty/zero datasets`.
- Do NOT push.

## Steps

### Step 1: RevenueChart — empty guard preserving the card shell

In `RevenueChart.tsx`, immediately after `const points = series.points;` (line ~51) insert:

```tsx
if (points.length === 0) {
  return (
    <DashboardCard
      title={series.title}
      subtitle={series.rangeLabel}
      action={
        <MiniSegmented
          options={PERIOD_OPTIONS}
          value={period}
          onChange={setPeriod}
          ariaLabel="Период выручки"
        />
      }
      className="md:col-span-2 xl:col-span-1"
    >
      <EmptyState className="py-10" title="Нет данных за период" message="Выберите другой период." />
    </DashboardCard>
  );
}
```

Add `import { EmptyState } from '@/components/feedback/EmptyState';`. Keep the `MiniSegmented` in the guard so the user can switch to a period that has data. Note the guard sits AFTER the `useState` call (line 49) — hooks order is preserved.

**Verify**: `bun run typecheck` && `bun run lint` → exit 0.

### Step 2: EarningsCard — empty + all-zero guard

After line 26 (`const maxPt = …`), normalize the divisors and add the empty guard:

```tsx
const safeMaxRev = maxRev > 0 ? maxRev : 1;
const safeMaxPt = maxPt > 0 ? maxPt : 1;
```

Change line ~40 to use `safeMaxRev`/`safeMaxPt`. Before the divisor lines, add an early return when `data.rows.length === 0`, rendering the existing `<Card as="section" …><CardHeader …/>` shell with `<EmptyState className="py-10" title="Нет данных" />` as the body (keep the `Segmented` action in the header). Note `useState` for `unit` is line 24 — the guard goes after it.

**Verify**: `bun run typecheck` && `bun run lint` → exit 0.

### Step 3: SalesChart — empty + all-zero guard

Same pattern: `const safeMax = max > 0 ? max : 1;` and use `safeMax` in the height math at line ~23; early-return `<Card><EmptyState className="py-14" title="Нет данных" /></Card>` when `data.months.length === 0`. (This component has no hooks — the guard can be first.)

**Verify**: `bun run typecheck` && `bun run lint` → exit 0.

### Step 4: Tests (only if plan 002 landed)

`src/pages/dashboard/components/RevenueChart.test.tsx`: build a minimal `RevenueData` fixture (check `src/features/dashboard/types.ts` for the exact shape — `series` keyed by `'30' | '90' | 'year'`, each with `points: []` and the string fields the component reads: `title`, `rangeLabel`, `total`, `delta.label`, `deltaSub`, `ticksEvery`, `breakdown: []`, plus `defaultPeriod`). Render with empty `points` for the default period; assert `Нет данных за период` is in the document and no console error fired. Add one happy-path render with 3 points asserting the title renders (the ResizeObserver stub from plan 002's setup makes Recharts mount safely under jsdom).

**Verify**: `bun run test` → all pass.

## Test plan

- New: `RevenueChart.test.tsx` (empty + happy path). EarningsCard/SalesChart are covered by the shared pattern; add equivalent tests only if their fixture types are small — otherwise note them as deferred in your summary.
- Regression: plan 002 smoke suite (dashboard/trainers/plans pages still render with full mocks).

## Done criteria

ALL must hold:

- [ ] `bun run typecheck`, `bun run lint`, `bun run test` → all exit 0
- [ ] `grep -n "safeMax" src/pages/plans/components/SalesChart.tsx src/pages/trainers/components/EarningsCard.tsx` → ≥ 3 matches
- [ ] `grep -n "Нет данных" src/pages/dashboard/components/RevenueChart.tsx` → 1 match
- [ ] The five original spread-math lines still exist (the guards prevent the empty case; the math itself was correct for non-empty data)
- [ ] `git status --porcelain` → only in-scope files
- [ ] `plans/README.md` row updated

## STOP conditions

Stop and report back if:

- Component code at the cited lines doesn't match the excerpts (drift).
- The `RevenueData`/`EarningsData`/`SalesChartData` types make the guard ambiguous (e.g. `points` is typed non-empty) — report; the type may be the better place for the invariant.
- Your grep finds NEW spread-math sites beyond the five listed — report them for a follow-up rather than silently widening scope.

## Maintenance notes

- The real fix for the long run is an upstream contract: when plan 010's zod spike lands, consider schema-level `nonempty()` where the design guarantees data, making some guards dead code (fine — they're cheap).
- New chart components must handle the empty case from day one; reviewers should ask "what renders when the array is empty?" on every chart PR.
- Deferred: dashboard-wide empty/zero-state design pass (what a brand-new club with no data sees) — a design task, not a guard.
