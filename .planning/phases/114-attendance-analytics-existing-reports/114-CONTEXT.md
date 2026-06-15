# Phase 114: Attendance Analytics on Existing Reports - Context

**Gathered:** 2026-06-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Frontend-only (ANL-01): surface real attendance analytics derived ENTIRELY from the
already-shipped `GET /api/v1/reports/visits` aggregate. NO new backend queries/endpoints.

The Load page (`apps/admin-app/src/pages/load/LoadPage.tsx`) already wires `useLoad` →
`reports/visits` and renders KPIs + an hourly heatmap + a daily trend (LoadHeatmapCard).
This phase ADDS the missing analytics widgets, all derived client-side from the same
`{ daily:[{date,count}], hourly:[{hour,count}], averagePerDay, fromDate, toDate }` payload:
day-of-week breakdown, peak-hour, visit-frequency distribution, and a visit-duration
"coming soon" placeholder (the aggregate carries NO duration data — no silent mock).

Out of scope: new backend aggregate queries (those are Phase 115); per-member visit
frequency (the aggregate has no per-client data); live gym-load counter (Phase 115).
</domain>

<decisions>
## Implementation Decisions

### Widget placement & derivation
- **Host screen:** the Load page — it already hosts visits analytics, the DateRangePicker,
  and `useLoad`. New widgets render as a section below the existing LoadHeatmapCard.
- **day-of-week breakdown:** group `daily[]` by weekday, computed MSK-safe (use the project
  date helpers / ISO parsing — NEVER `new Date(dateOnlyString)`, DST risk per CLAUDE.md).
  Show per-weekday total and/or average.
- **peak-hour:** argmax over `hourly[]`; label the hour; ties resolve to the earlier hour.
- **visit-frequency distribution:** since the aggregate has NO per-client data, this is the
  distribution of DAILY VISIT VOLUMES — a histogram bucketing days by their visit count
  (derived from `daily[]`). Labeled to make the meaning clear (e.g. "распределение дневной
  посещаемости").
- **visit-duration widget:** explicit "Скоро" / coming-soon state — the aggregate has no
  duration data, so render a clearly-labeled placeholder card, NOT mock data (success criteria #3).

### States & correctness
- **Zero/NaN:** zero-fill all buckets; guard every average/ratio against divide-by-zero so
  empty buckets render `0`, never `NaN` (success criteria #1).
- **Reception:** all widgets live under the existing `can(role, 'view', 'reports')` page gate.
- **Empty period:** the existing all-zero EmptyState («Нет данных за этот период») covers the
  whole section; widgets need not each render a separate empty state.

### Claude's Discretion
- Exact chart primitives reused for each widget (AreaTrendChart / IntensityHeatmap / bar list
  already in the codebase) and their visual layout/grid.
- Whether day-of-week shows sum, average, or both; histogram bucket boundaries for the
  frequency distribution.
- Component file names under `pages/load/components/`.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `apps/admin-app/src/features/load/api.ts` (`useLoad`) → `GET /api/v1/reports/visits`;
  `features/load/types.ts` (VisitsReport bucket types); `features/visits/` schemas.
- `apps/admin-app/src/pages/load/LoadPage.tsx` (current layout, all-zero EmptyState, date
  range state) + `components/LoadHeatmapCard.tsx` (IntensityHeatmap + AreaTrendChart usage),
  `LoadKpis.tsx`.
- Backend (read-only reference — DO NOT modify): `app/modules/reports/schemas.py`
  `VisitsReportResponse` = daily[{date,count}] + hourly[{hour,count}] + average_per_day +
  from_date + to_date. No duration field.
- Date helpers: `apps/admin-app/src/lib/format.ts` (mskTodayISO, mskDaysAgoISO) +
  `shared/i18n/date.ts` (MSK-pinned formatting). Use these, never raw `new Date(dateOnly)`.
- Chart primitives already used by LoadHeatmapCard (IntensityHeatmap, AreaTrendChart).

### Established Patterns
- Frontend: TanStack Query per-feature hooks + `staffRequest`; semantic shadcn tokens only;
  `can()` page gating; MSK-pinned date handling; integer counts.
- Pure client-side derivation from a single fetched aggregate (no extra requests).

### Integration Points
- New widget components under `pages/load/components/`, composed into `LoadPage.tsx` below
  LoadHeatmapCard, all fed from the same `useLoad` result already in scope.
- A small pure-function module (e.g. `pages/load/components/derive.ts`) for the day-of-week /
  peak-hour / frequency-histogram derivations — unit-testable with Vitest.
</code_context>

<specifics>
## Specific Ideas

- "visit-frequency distribution" is interpreted as daily-volume histogram (aggregate has no
  per-client data) — explicitly labeled so it isn't mistaken for per-member frequency.
- Visit-duration is a "coming soon" placeholder (no mock) because the aggregate lacks duration.
- All derivations are pure client-side functions over the existing aggregate — add Vitest unit
  tests for the zero/NaN edge cases and the MSK weekday grouping.
</specifics>

<deferred>
## Deferred Ideas

- New backend aggregate queries (cohort/anomaly/at-risk, live gym-load) — Phase 115.
- Per-member visit frequency — needs a backend per-client aggregate, not in scope.
- Real visit-duration analytics — needs duration data in the backend aggregate (future).
</deferred>
