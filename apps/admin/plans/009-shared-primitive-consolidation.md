# Plan 009: Consolidate duplicated page-local primitives (Panel, Callout, metric tile)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat <baseline SHA from plans/README.md>..HEAD -- src/pages/notifications/components/parts.tsx src/pages/import-export/components/parts.tsx src/pages/finance/components/parts.tsx src/pages/branches/components/parts.tsx src/components/modals/fields.tsx`
> On any change, compare the excerpts below before proceeding; mismatch = STOP.

## Status

- **Priority**: P3
- **Effort**: M
- **Risk**: MED (visual-fidelity refactor — every change here is user-visible if done wrong)
- **Depends on**: plans/002-vitest-baseline.md (smoke gate)
- **Category**: tech-debt
- **Planned at**: 2026-06-12 (pre-git; baseline SHA in plans/README.md)

## Why this matters

Several pages re-implement the same visual primitives locally: two `Panel` components with byte-identical shells, two `Callout`s, and two metric tiles that differ by one or two pixels of font size. The repo's own convention (CLAUDE.md: "When a component reappears in a second screen, promote it") says these are overdue for promotion. Divergent copies drift — a border-radius tweak lands in one page and not the other. This plan promotes three primitives with surgical, visual-identity-preserving moves. It deliberately does NOT unify things that merely look similar but are different designs.

## Current state

All excerpts verified 2026-06-12.

**(a) Panel — two copies, identical shell.**

`src/pages/notifications/components/parts.tsx:95-106`:

```tsx
export function Panel({ children }: { children: ReactNode }) {
  return <div className="overflow-hidden rounded-[18px] border-[0.5px] border-border bg-surface shadow-2">{children}</div>;
}

export function PanelHead({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div className="flex items-center gap-2.5 border-b-[0.5px] border-border px-[18px] py-3.5">
      <h2 className="text-sm font-bold">{title}</h2>
      {action ? <div className="ml-auto flex items-center gap-2">{action}</div> : null}
    </div>
  );
}
```

`src/pages/import-export/components/parts.tsx:27-41`:

```tsx
export function Panel({ title, caption, bodyless, children }: { title?: string; caption?: ReactNode; bodyless?: boolean; children: ReactNode }) {
  return (
    <div className="overflow-hidden rounded-[18px] border-[0.5px] border-border bg-surface shadow-2">
      {title ? (
        <div className="px-[18px] pb-1 pt-4">
          <h2 className="text-[15px] font-bold">{title}</h2>
          {caption ? <div className="mt-1 text-[12.5px] text-fg-subtle">{caption}</div> : null}
        </div>
      ) : null}
      {bodyless ? children : <div className="px-[18px] pb-[18px] pt-3.5">{children}</div>}
    </div>
  );
}
```

The **shell div is identical**; the headers are two different designs (bordered compact vs caption-style). Both must be preserved exactly.

**(b) Callout — two copies.** `src/components/modals/fields.tsx:307+` (tones `default | accent | warn | danger`, shell `flex gap-2.5 rounded-xl border-[0.5px] p-[12px_14px]`, used by many modals — e.g. `CashModal` imports it) and `src/pages/import-export/components/parts.tsx:43-58` (tones `info | warn | ok`, shell `rounded-xl border p-[12px_14px] text-[12.5px] leading-relaxed` with per-tone text colors and `[&_b]` styling). Similar but NOT identical (border width, text styling).

**(c) Metric tile — two near-copies.** `src/pages/finance/components/parts.tsx:12-39` `FinanceKpi` (icon + label, value `text-[21px]`, unit `text-[12px]`, shell `rounded-[14px] border-[0.5px] border-border bg-surface px-4 py-3.5 shadow-1` + `transition-shadow hover:shadow-2`, variant color map `KPI_COLOR = { default: '', accent: 'text-primary-deep dark:text-primary', danger: 'text-danger' }`) and `src/pages/branches/components/parts.tsx:17-29` `SummaryTile` (no icon, value `text-[22px]`, unit `text-[13px]`, same shell minus hover).

**Existing shared homes** (do not duplicate them): `src/components/layout/` (Card/CardHeader/CardLink — `rounded-lg … shadow-1`, a DIFFERENT, lighter design than Panel — do **not** merge Panel into Card), `src/components/ui/` (StatTile, KpiTile, StatusPill — different designs, leave alone).

Conventions: semantic tokens, `cn()` from `@/lib/cn`, Russian doc-comments, `import type` under `verbatimModuleSyntax`.

## Commands you will need

| Purpose   | Command             | Expected on success |
|-----------|---------------------|---------------------|
| Typecheck | `bun run typecheck` | exit 0              |
| Lint      | `bun run lint`      | exit 0              |
| Tests     | `bun run test`      | all pass            |

## Scope

**In scope**:
- `src/components/layout/Panel.tsx` (create)
- `src/components/ui/callout.tsx` (create)
- `src/components/ui/MetricTile.tsx` (create)
- `src/pages/notifications/components/parts.tsx`, `src/pages/import-export/components/parts.tsx` (migrate Panel; import-export Callout per Step 3's bounded rule)
- `src/pages/finance/components/parts.tsx`, `src/pages/branches/components/parts.tsx` (migrate metric tiles)
- `src/components/modals/fields.tsx` (Callout body moves out; file re-exports it)
- Files that import the migrated symbols from the parts files (imports may need updating — find with grep)
- `plans/README.md` (status row)

**Out of scope** (do NOT touch — these look related but are different designs or domain data):
- `components/layout/Card.tsx`, `ui/StatTile.tsx`, `ui/KpiTile.tsx`, `ui/StatusPill.tsx`
- Ghost-button class constants (`GHOST_SM` notifications:108, `GHOST` branches:12, `BTN` import-export:9) — different heights/sizes (34 vs 38px), genuinely distinct variants; unifying them is a design decision, not a refactor.
- Status→tone maps (`TONE_CLS`, `REC_STATUS`, `KPI_COLOR`-style records) — domain data; the base `StatusPill` already centralizes rendering.
- `KpiCell` (branches:31) — borderless cell inside BranchCard's grid, a different component.
- Everything else inside the parts files (NotifRow, Stepper, Dropzone, etc. — page-specific by design).

## Git workflow

- Branch: `advisor/009-primitive-consolidation` off `main`.
- One commit per primitive (3–4 commits). Messages: `refactor: promote Panel to components/layout`, etc.
- Do NOT push.

## Steps

### Step 1: Shared Panel

Create `src/components/layout/Panel.tsx`:

```tsx
import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

/** Тяжёлая панель раздела: 18px-радиус + shadow-2 (в отличие от лёгкой Card). */
export function Panel({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cn('overflow-hidden rounded-[18px] border-[0.5px] border-border bg-surface shadow-2', className)}>
      {children}
    </div>
  );
}

/** Компактная шапка панели с нижней границей (стиль «Уведомления»). */
export function PanelHead({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div className="flex items-center gap-2.5 border-b-[0.5px] border-border px-[18px] py-3.5">
      <h2 className="text-sm font-bold">{title}</h2>
      {action ? <div className="ml-auto flex items-center gap-2">{action}</div> : null}
    </div>
  );
}

/** Заголовок-с-подписью без границы (стиль «Импорт/экспорт»). */
export function PanelTitle({ title, caption }: { title: string; caption?: ReactNode }) {
  return (
    <div className="px-[18px] pb-1 pt-4">
      <h2 className="text-[15px] font-bold">{title}</h2>
      {caption ? <div className="mt-1 text-[12.5px] text-fg-subtle">{caption}</div> : null}
    </div>
  );
}

/** Стандартный отступ тела панели. */
export function PanelBody({ children }: { children: ReactNode }) {
  return <div className="px-[18px] pb-[18px] pt-3.5">{children}</div>;
}
```

Migrate:
- notifications: delete its local `Panel`/`PanelHead`, import from `@/components/layout/Panel`. Usage sites keep identical markup.
- import-export: delete its local `Panel`; recreate its API locally as a thin composition OR update its call sites to `<Panel>{title && <PanelTitle …/>}{bodyless ? children : <PanelBody>…</PanelBody>}</Panel>` — choose whichever keeps the page diff smallest; the rendered DOM/classes must be identical either way.
- Update any other files importing `Panel`/`PanelHead` from these parts files (`grep -rn "from './parts'" src/pages/notifications src/pages/import-export` and check imported names).

**Verify**: `bun run typecheck` && `bun run lint` && `bun run test` → exit 0; `grep -rn "export function Panel(" src/pages` → **0 matches**.

### Step 2: Promote the modal Callout

Move the `Callout` component from `src/components/modals/fields.tsx:307+` **verbatim** (body, tone map, props) into new `src/components/ui/callout.tsx`. In `fields.tsx`, replace the definition with a re-export: `export { Callout } from '@/components/ui/callout';` — so all modal imports keep working unchanged.

**Verify**: `bun run typecheck` && `bun run lint` && `bun run test` → exit 0; `grep -n "function Callout" src/components/modals/fields.tsx` → 0; `grep -rn "from './fields'" src/components/modals | wc -l` unchanged from before the step.

### Step 3 (bounded attempt): migrate import-export's Callout to the shared one

Attempt ONLY under this rule: the rendered class strings must be reproducible exactly via the shared component's `tone` + a `className` pass-through (tailwind-merge resolves conflicts — e.g. passing `border items-start text-[12.5px] leading-relaxed` overrides `border-[0.5px]`). Compare old vs new rendered classNames in a quick unit test or by temporary `console.log` in a test render — exact string match per tone (`info`→`default`, `ok`→`accent`, `warn`→`warn`) including the per-tone text-color and the `[&_b]` styles. If exact reproduction needs component changes beyond an optional `className` prop, **leave import-export's Callout in place**, add a code comment `/* локальный вариант Callout — см. plans/009, осознанно не слит */`, and record the deferral in your summary. Partial completion here is the designed outcome, not a failure.

**Verify**: `bun run typecheck` && `bun run lint` && `bun run test` → exit 0 (whichever branch you took).

### Step 4: Shared MetricTile

Create `src/components/ui/MetricTile.tsx`:

```tsx
import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';

const VALUE_COLOR = {
  default: '',
  accent: 'text-primary-deep dark:text-primary',
  danger: 'text-danger',
} as const;

/**
 * Компактная метрика-плитка (финансы, филиалы): подпись (+иконка) и крупное
 * значение. Нормализовано: значение 22px, единица 12px (страницы расходились
 * на ±1px — приведено к большему/меньшему осознанно, см. plans/009).
 */
export function MetricTile({
  icon: Icon,
  label,
  value,
  unit,
  variant = 'default',
  className,
}: {
  icon?: LucideIcon;
  label: string;
  value: ReactNode;
  unit?: string;
  variant?: keyof typeof VALUE_COLOR;
  className?: string;
}) {
  return (
    <div className={cn('rounded-[14px] border-[0.5px] border-border bg-surface px-4 py-3.5 shadow-1', className)}>
      <div className="flex items-center gap-1.5 text-[12px] text-fg-muted">
        {Icon ? <Icon className="size-[13px] shrink-0 text-fg-subtle" strokeWidth={2} /> : null}
        {label}
      </div>
      <div className={cn('mt-1.5 text-[22px] font-bold tabular-nums tracking-[-0.5px]', VALUE_COLOR[variant])}>
        {value}
        {unit ? <span className="text-[12px] font-semibold text-fg-subtle">{unit}</span> : null}
      </div>
    </div>
  );
}
```

Normalization decision (made at planning, do not re-litigate): value 22px (FinanceKpi's 21→22, matching SummaryTile/StatTile), unit 12px (SummaryTile's 13→12, matching FinanceKpi). Migrate:
- finance: `FinanceKpi` → re-export or direct replacement with `<MetricTile … className="transition-shadow hover:shadow-2" />` (preserving its hover); delete the local component + `KPI_COLOR`.
- branches: `SummaryTile` → `<MetricTile label=… value=… unit=… />`; delete the local component.

**Verify**: `bun run typecheck` && `bun run lint` && `bun run test` → exit 0; `grep -rn "function FinanceKpi\|function SummaryTile" src/pages` → 0 matches.

### Step 5: Visual spot-check

If a dev preview is available: `bun run dev`, open `/notifications`, `/settings/import-export`, `/finance`, `/branches` in **both themes** (toggle `data-theme`) and compare against pre-change screenshots (take them before starting, from `main`). Panels/callouts/tiles must look identical except the documented ±1px font normalization on metric tiles. If no preview is available, state so in the summary — the class-string equality checks in Steps 1–4 are the fallback evidence.

## Test plan

- The plan-002 smoke suite covers all four affected pages rendering.
- Step 3's class-string comparison is the Callout migration's acceptance test.
- No new permanent test files required; if you wrote a throwaway class-comparison test, either keep it as `callout.test.tsx` (fine) or remove it before the final commit — your choice, state which.

## Done criteria

ALL must hold:

- [ ] `grep -rn "export function Panel(\|function FinanceKpi\|function SummaryTile" src/pages` → 0 matches
- [ ] `src/components/layout/Panel.tsx`, `src/components/ui/callout.tsx`, `src/components/ui/MetricTile.tsx` exist
- [ ] `grep -n "function Callout" src/components/modals/fields.tsx` → 0 (re-export only)
- [ ] `bun run typecheck` && `bun run lint` && `bun run test` → all exit 0
- [ ] Step 3 outcome (migrated or deliberately deferred) recorded in summary and `plans/README.md`
- [ ] `git status --porcelain` → only in-scope files
- [ ] `plans/README.md` row updated

## STOP conditions

Stop and report back if:

- Any excerpt in "Current state" doesn't match the live code (drift).
- A migration forces a visible class change beyond the two documented ±1px normalizations.
- You find additional Panel/Callout/tile copies beyond those listed — report; don't widen scope.
- The import updates fan out beyond the four pages + fields.tsx (something else imported these symbols) — list the files and wait.

## Maintenance notes

- Future pages needing a heavy panel/callout/metric tile must import the shared ones; CLAUDE.md's "promote at second use" rule now has these as exemplars.
- The deferred items (ghost-button unification, import-export Callout if Step 3 deferred, status-map centralization) are recorded as rejected/deferred in `plans/README.md` — don't resurrect them without a design pass.
- Reviewer focus: rendered class strings before/after (the diffs should be import moves, not styling edits), and the two intentional font-size normalizations on `/finance` and `/branches`.
