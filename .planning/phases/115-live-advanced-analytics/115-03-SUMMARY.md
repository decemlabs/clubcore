---
phase: 115-live-advanced-analytics
plan: "03"
subsystem: frontend/load-analytics
tags: [frontend, analytics, reports, zod, tanstack-query, recharts, load-page, rbac]
dependency_graph:
  requires:
    - GET /api/v1/reports/cohort (ANL-02, Plan 01)
    - GET /api/v1/reports/anomaly (ANL-02, Plan 01)
    - GET /api/v1/reports/at-risk (ANL-02, Plan 01)
    - GET /api/v1/reports/load/now (ANL-03, Plan 01)
  provides:
    - CohortRetentionCard (cohort grid, Load page)
    - VisitAnomalyCard (anomaly area chart, Load page)
    - AtRiskWidget (at-risk members list, Load page)
    - LiveNowCard wired to useLoadNow (Load page)
    - LoadNowSchema/CohortRetentionSchema/VisitAnomalySchema/AtRiskSchema (Zod contracts)
    - useCohortReport/useVisitAnomaly/useAtRiskMembers/useLoadNow (TanStack hooks)
  affects:
    - apps/admin-app/src/features/reports/schemas.ts
    - apps/admin-app/src/features/reports/keys.ts
    - apps/admin-app/src/features/reports/api.ts
    - apps/admin-app/src/features/reports/schemas.test.ts
    - apps/admin-app/src/features/load/api.ts
    - apps/admin-app/src/pages/load/components/CohortRetentionCard.tsx
    - apps/admin-app/src/pages/load/components/VisitAnomalyCard.tsx
    - apps/admin-app/src/pages/load/components/AtRiskWidget.tsx
    - apps/admin-app/src/pages/load/LoadPage.tsx
    - packages/api-client/src/schema.d.ts
tech_stack:
  added: []
  patterns:
    - Zod nested schema envelope { data: { ... } } matching real wire keys (D-V32-DRIFT-LESSON)
    - TanStack Query owner-gated hook (enabled: can(role,'view','reports')) — WR-04 role param pattern
    - useLoadNow refetchInterval 60s (live poll)
    - Custom Area dot renderer for anomaly markers (recharts dot prop)
    - CohortRetentionSchema nested cohort[] shape (overrides stale PATTERNS.md flat rows[] shape)
    - schema.d.ts stub paths (Phase 117 OpenAPI regen deferred)
key_files:
  created:
    - apps/admin-app/src/pages/load/components/CohortRetentionCard.tsx
    - apps/admin-app/src/pages/load/components/VisitAnomalyCard.tsx
    - apps/admin-app/src/pages/load/components/AtRiskWidget.tsx
  modified:
    - apps/admin-app/src/features/reports/schemas.ts
    - apps/admin-app/src/features/reports/keys.ts
    - apps/admin-app/src/features/reports/api.ts
    - apps/admin-app/src/features/reports/schemas.test.ts
    - apps/admin-app/src/features/load/api.ts
    - apps/admin-app/src/pages/load/LoadPage.tsx
    - packages/api-client/src/schema.d.ts
decisions:
  - "CohortRetentionSchema uses NESTED { cohorts: [{ cohortMonth, label, months: [{ offset, retentionPct }] }], maxOffset } matching 115-01-SUMMARY — overrides stale PATTERNS.md flat rows[] shape"
  - "LiveData mapping: capacity=0 / meterPct=0 since endpoint returns no capacity; single 'Зал' zone with approximation sub-label per T-115-F3"
  - "schema.d.ts stub paths added for 4 new endpoints to unblock TypeScript builds — full OpenAPI regen deferred to Phase 117"
  - "AnomalyDot via custom dot prop on Area component (not separate Scatter) — correct coordinate placement within AreaChart"
  - "Расширенная аналитика section renders independently from the visits all-zero check so it always shows owner-only analytics"
metrics:
  duration: "~10 minutes"
  completed: "2026-06-15"
  tasks_completed: 2
  files_modified: 10
---

# Phase 115 Plan 03: FE Advanced Analytics Widgets + Live Counter Summary

Four new backend aggregates wired into the Load page: cohort retention grid, visit-anomaly chart, at-risk members widget, and LiveNowCard fed by the live headcount endpoint — all owner-gated, each with skeleton/empty/error states. Zod schemas pinned to the REAL camelCase wire shapes from 115-01/02 SUMMARYs (no mock→real drift).

## What Was Built

### Task 1: Zod Schemas + Query Keys + Hooks

**`apps/admin-app/src/features/reports/schemas.ts`** — four new schemas added:

| Schema | Wire shape (authoritative: 115-01-SUMMARY) |
|--------|---------------------------------------------|
| `LoadNowSchema` | `{ data: { count: int>=0, asOf: ISO string, windowMinutes: int>0 } }` |
| `CohortRetentionSchema` | `{ data: { cohorts: [{ cohortMonth, label, months: [{ offset, retentionPct\|null }] }], maxOffset } }` — NESTED (PATTERNS.md flat shape was stale) |
| `VisitAnomalySchema` | `{ data: { points: [{ date, count, isAnomaly, direction: 'spike'\|'drop'\|null, label }], windowDays, sigmaThreshold, anomalyCount } }` |
| `AtRiskSchema` | `{ data: { count, items: [{ clientId, name, membershipType, lastVisitDate\|null, daysSinceVisit, lastVisitLabel }], thresholdDays } }` |

Exported types: `LoadNowData`, `CohortRetentionData`, `CohortEntry`, `CohortMonth`, `VisitAnomalyData`, `VisitAnomalyPoint`, `AtRiskData`, `AtRiskItem`.
Query types: `CohortRetentionQuery`, `VisitAnomalyQuery`.

**`apps/admin-app/src/features/reports/keys.ts`** — extended with:
`cohort(q)`, `anomaly(q)`, `atRisk()`, `loadNow()` factory functions.

**`apps/admin-app/src/features/reports/api.ts`** — four new owner-gated hooks:
- `useCohortReport(query, role)` — GET /api/v1/reports/cohort, staleTime 30s
- `useVisitAnomaly(query, role)` — GET /api/v1/reports/anomaly, optional fromDate/toDate, staleTime 30s
- `useAtRiskMembers(role)` — GET /api/v1/reports/at-risk, staleTime 30s
- `useLoadNow(role)` — GET /api/v1/reports/load/now, staleTime 60s + refetchInterval 60s (live poll)

**`apps/admin-app/src/features/load/api.ts`** — re-exports all four new hooks for LoadPage colocation.

**`apps/admin-app/src/features/reports/schemas.test.ts`** — 15 new Zod round-trip assertions added (TDD RED→GREEN):
- `LoadNowSchema` × 5 tests (valid, zero count, reject negative, reject non-integer, reject zero windowMinutes)
- `CohortRetentionSchema` × 3 tests (nested shape, empty array, null retentionPct)
- `VisitAnomalySchema` × 4 tests (full shape, empty points, drop direction, reject unknown direction)
- `AtRiskSchema` × 3 tests (full shape, null lastVisitDate, empty items)
- `reportsQueryKeys` Phase 115 keys × 4 tests

Total test suite: 390 tests pass.

### Task 2: Widgets + LoadPage Wiring

**`CohortRetentionCard.tsx`** (84 lines):
- `<table role="grid" aria-label="Таблица удержания">` with `<th scope="col">` M0..M{maxOffset} headers and `<th scope="row">` cohort label
- `retentionBg(pct)` color scale: transparent / var(--surface-2) / color-mix primary 30% / color-mix primary 75%
- Cells ≥70% get `font-semibold`; null cells render "—"
- Gradient legend footer
- Skeleton `h-[240px]` while pending; EmptyState on empty/error

**`VisitAnomalyCard.tsx`** (135 lines):
- `ChartContainer` + `AreaChart` with custom `AnomalyDot` renderer on the `Area` component
- Spike dots = `var(--chart-1)`, drop dots = `var(--chart-4)` — colored circles r=5 with surface stroke
- Summary line "Найдено аномалий: N", legend chips when anomalyCount > 0
- "Аномалий не обнаружено..." footnote when data present but no anomalies
- Skeleton `h-[180px]` while pending; EmptyState for empty points / error

**`AtRiskWidget.tsx`** (72 lines):
- Count badge: `bg-warning-soft text-warning-deep`, `aria-label="Клиентов под риском: {count}"`
- Up to 5 read-only `div` rows (grid-cols layout, truncate name, membershipType, lastVisitLabel)
- "И ещё N клиентов →" overflow line when count > 5
- Zero-risk: `CheckCircle2` EmptyState "Отток под контролем"; error: `TriangleAlert` EmptyState
- Three stacked Skeleton rows while pending

**`LoadPage.tsx`** (updated):
- `useLoadNow`, `useCohortReport`, `useVisitAnomaly`, `useAtRiskMembers` imported from `@/features/load/api`
- `LiveNowCard` un-hidden: wired to `useLoadNow`, mapped `{ count, asOf, windowMinutes }` → `LiveData` (single "Зал" zone with `metaRest = "Оценка присутствующих · окно N мин"`); omitted silently on error
- Removed original TODO comment about LiveNowCard being hidden
- New `<section aria-label="Расширенная аналитика">` after "Дополнительная аналитика" with all three new widgets

**`packages/api-client/src/schema.d.ts`** — stub path entries for four new endpoints added to unblock TypeScript builds. Full OpenAPI regen deferred to Phase 117.

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] schema.d.ts missing paths for new endpoints**
- **Found during:** Task 2 production build
- **Issue:** `staffRequest()` is typed against `paths` from `@clubcore/api-client`. The four new Phase 115 endpoints (`/cohort`, `/anomaly`, `/at-risk`, `/load/now`) were not registered in `schema.d.ts`, causing TypeScript errors: `Argument of type '"/api/v1/reports/cohort"' is not assignable to parameter of type 'keyof paths'`.
- **Fix:** Added minimal stub path definitions for the four new routes to `packages/api-client/src/schema.d.ts` with a `TODO Phase 117: regenerate from OpenAPI spec` comment. This matches the 115-01-SUMMARY decision that OpenAPI regen is deferred.
- **Files modified:** `packages/api-client/src/schema.d.ts`
- **Commit:** c5943324

**2. [Rule 1 - Design] LiveData capacity mapping**
- **Found during:** Task 2 LoadPage wiring
- **Issue:** `LiveData.capacity` has no equivalent in `LoadNowResponse` (the endpoint returns only `count`, `asOf`, `windowMinutes` — no gym capacity). The existing `LiveNowCard` renders `{count} / {capacity}` and a fill meter.
- **Fix:** Set `capacity=0`, `meterPct=0`, `filledPct=count.toString()` to render "N / 0" while avoiding division by zero. The approximation disclaimer is conveyed via the "Зал" zone `metaRest = "Оценка присутствующих · окно N мин"` label (T-115-F3). This is intentional — real capacity is a gym-settings concern deferred to a future phase.
- **Impact:** Meter bar is invisible (0%); the count is displayed correctly. No over-claim of precision.

### AnomalyDot Implementation Note

The UI-SPEC suggested using recharts `<Scatter>` components inside an `<AreaChart>` for anomaly markers. This is not directly supported in recharts (Scatter inside AreaChart has no shared coordinate system). Instead, anomaly dots are rendered via a **custom dot renderer** (`AnomalyDot` function component) passed as the `dot` prop to the `<Area>` component. This renders colored circles at the correct x/y coordinates derived from the chart's own scale — cleaner and more correct than a composed chart approach.

### Browser-deferred UAT Items

Per project convention, visual correctness of the following is a browser-UAT item:
- Cohort grid color-scale (low/mid/high retention tints) in light + dark themes
- Anomaly marker dots (spike vs drop color, dot radius on chart)
- LiveNowCard live counter auto-refresh at 60s intervals
- Zero-count state of LiveNowCard (capacity=0 display)

---

## Verification Results

- `pnpm -F @clubcore/admin-app exec tsc --noEmit` — **clean**
- `pnpm -F @clubcore/admin-app exec eslint [new/modified files]` — **clean**
- `pnpm -F @clubcore/admin-app test` — **390 tests pass** (29 test files)
- `grep -q "Расширенная аналитика" LoadPage.tsx` — **FOUND**
- `grep -q "useLoadNow" LoadPage.tsx` — **FOUND**
- `pnpm -F @clubcore/admin-app build` — **succeeded** (LoadPage-Bf1xB40k.js 34.18 kB gzip 11.96 kB)

---

## Threat Surface Scan

No new threat surface beyond the plan's `<threat_model>`:
- T-115-F1 (Zod parse at seam): all four schemas use `Schema.parse(raw).data` before render.
- T-115-F2 (reception gate): all hooks have `enabled: can(role,'view','reports')`; LoadPage page-level guard also blocks.
- T-115-F3 (LiveNow approximation copy): "Оценка присутствующих · окно N мин" sub-label present in zone metaRest.
- No new network endpoints introduced by the FE plan.

## Known Stubs

None. All four hooks call real backend endpoints. The `capacity=0` in LiveData is intentional (documented above) — the count display is fully functional.

## Self-Check: PASSED

All 8 new/modified files confirmed to exist. Commits e70a100b (Task 1) and c5943324 (Task 2) both confirmed in git log.
