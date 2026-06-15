---
phase: 114-attendance-analytics-existing-reports
plan: "02"
subsystem: frontend
tags: [analytics, widgets, recharts, kpi, attendance, reports, load-page]
dependency_graph:
  requires:
    - "apps/admin-app/src/pages/load/components/derive.ts (Plan 114-01: deriveDayOfWeek, derivePeakHour, deriveFrequency)"
  provides:
    - "apps/admin-app/src/pages/load/components/DayOfWeekCard.tsx (weekday bar list)"
    - "apps/admin-app/src/pages/load/components/PeakHourCard.tsx (peak-hour KPI tile)"
    - "apps/admin-app/src/pages/load/components/FrequencyCard.tsx (daily-volume histogram)"
    - "apps/admin-app/src/pages/load/components/DurationPlaceholderCard.tsx (coming-soon)"
    - "apps/admin-app/src/pages/load/LoadPage.tsx (composed analytics section below LoadHeatmapCard)"
  affects:
    - "Owner /load view: four new analytics widgets visible in non-zero data branch"
tech_stack:
  added: []
  patterns:
    - "Card as=section + CardHeader chrome verbatim from LoadHeatmapCard"
    - "Horizontal bar list: percentage-width inner div, peak accent via cn + isPeak flag"
    - "KpiTile with Clock icon inside Card (PeakHourCard pattern)"
    - "AreaTrendChart over FrequencyBucket[] mapped to TrendPoint[]"
    - "Coming-soon card: muted Card, Clock icon, explanatory text, Скоро badge, no mock data"
    - "Section aria-label landmark wrapping four new cards below LoadHeatmapCard"
key_files:
  created:
    - apps/admin-app/src/pages/load/components/DayOfWeekCard.tsx
    - apps/admin-app/src/pages/load/components/PeakHourCard.tsx
    - apps/admin-app/src/pages/load/components/FrequencyCard.tsx
    - apps/admin-app/src/pages/load/components/DurationPlaceholderCard.tsx
  modified:
    - apps/admin-app/src/pages/load/LoadPage.tsx
decisions:
  - "DayOfWeekCard peak detection: first stat with total === maxTotal && maxTotal > 0 (ties go to earlier weekday, matching derive.ts argmax contract)"
  - "PeakHourCard renders KpiTile inside a Card wrapper (not standalone tile) for visual consistency with other analytics cards"
  - "FrequencyCard uses AreaTrendChart (pre-existing primitive) rather than a bar chart to avoid new Recharts dependency"
  - "DurationPlaceholderCard: no fabricated data per success criteria #3 and T-114-05 threat register (accept disposition)"
  - "Section layout: DayOfWeekCard full-width, PeakHourCard + FrequencyCard in md:grid-cols-2, DurationPlaceholderCard full-width"
metrics:
  duration: "~2 minutes"
  completed: "2026-06-15"
  tasks_completed: 2
  files_created: 4
  files_modified: 1
---

# Phase 114 Plan 02: Widget Components + LoadPage Compose Summary

Four attendance-analytics widgets built from derive.ts contracts and composed into LoadPage.tsx below the existing LoadHeatmapCard — weekday bar list, peak-hour KPI tile, daily-volume histogram, and honest coming-soon duration placeholder.

## What Was Built

### DayOfWeekCard.tsx (46 lines)

Card-chrome component wrapping a 7-row horizontal bar list for Mon–Sun. Calls `deriveDayOfWeek(daily)` and renders each weekday with a proportional bar (`(total/maxTotal)*100%`), with the peak weekday bar in `bg-primary` and all others in `bg-chart-2`. Zero bars render at 0% width (rows stay visible for alignment). Zero guard: `maxTotal === 0 ? 0 : pct`. Semantic tokens only.

### PeakHourCard.tsx (33 lines)

Card-chrome component wrapping a single `KpiTile` (Clock icon, label "Пиковое время"). Calls `derivePeakHour(hourly)`. Value: `{hour}:00–{hour+1}:00` when peak is non-null, `—` when null. Unit: `{count} визитов` when peak non-null, `undefined` otherwise (KpiTile gracefully omits unit).

### FrequencyCard.tsx (30 lines)

Card-chrome component wrapping an `AreaTrendChart` over the 6 frequency buckets. Calls `deriveFrequency(daily)` and maps `FrequencyBucket[]` to `TrendPoint[]` (`{ label: b.label, value: b.count }`). Height 160px. Uses existing AreaTrendChart primitive — no new chart dependency.

### DurationPlaceholderCard.tsx (27 lines)

No-props coming-soon card. No numeric or mock data. Contains: Clock icon (`size-8 text-fg-subtle`), explanatory copy ("Эта аналитика появится после добавления данных о продолжительности визитов."), muted "Скоро" badge (`bg-surface-2 border-border text-fg-muted`). Muted surface only — not accented, not destructive. Satisfies T-114-05 (accept disposition).

### LoadPage.tsx (additive edit)

Added four imports after `LoadHeatmapCard`. In the non-zero data branch, wrapped `LoadHeatmapCard` + new `<section aria-label="Дополнительная аналитика">` in a fragment. Section contains:
- `<DayOfWeekCard daily={daily} />` — full width
- `<div className="grid grid-cols-1 gap-4 md:grid-cols-2">` with `<PeakHourCard hourly={hourly} />` and `<FrequencyCard daily={daily} />`
- `<DurationPlaceholderCard />` — full width

RBAC guard, fetching skeleton, and all-zero EmptyState branches unchanged. One pre-existing `useLoad` call confirmed (no new hooks).

## Verification Results

- `pnpm -F @clubcore/admin-app typecheck` → clean (no errors)
- `pnpm -F @clubcore/admin-app lint` → clean (no raw-palette / import-boundary violations)
- `pnpm -F @clubcore/admin-app test` → 370/370 passed (includes derive.test.ts 15 tests + router-smoke 20 tests)
- `pnpm -F @clubcore/admin-app build` → success (2.76s; chunk size warning is pre-existing)
- `grep -n 'useLoad' LoadPage.tsx` → exactly 1 call confirmed (line 58)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. All four widgets render real derived data or an honest coming-soon state. DurationPlaceholderCard is intentionally data-absent (no duration field in `VisitsReportResponse`) and is documented in the threat register as T-114-05 (accept). No numeric placeholders, no TODO-data.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes. All four widgets:
- Render within the existing `can(role,'view','reports')` page gate (T-114-03 mitigated — reception never reaches this branch)
- Consume only already-fetched `hourly`/`daily` arrays from the single pre-existing `useLoad` call
- Use static Russian label constants and integer counts rendered as React text (T-114-04 mitigated — no injection surface)
- DurationPlaceholderCard has zero dynamic data (T-114-05 accept)

No new threat flags.

## Self-Check

- [x] `apps/admin-app/src/pages/load/components/DayOfWeekCard.tsx` — created, exists
- [x] `apps/admin-app/src/pages/load/components/PeakHourCard.tsx` — created, exists
- [x] `apps/admin-app/src/pages/load/components/FrequencyCard.tsx` — created, exists
- [x] `apps/admin-app/src/pages/load/components/DurationPlaceholderCard.tsx` — created, exists
- [x] `apps/admin-app/src/pages/load/LoadPage.tsx` — modified, imports + section added
- [x] Commit `c22c2661` (Task 1: four widget components) — exists in git log
- [x] Commit `21d84d1c` (Task 2: compose into LoadPage) — exists in git log
- [x] 370 tests pass, typecheck clean, lint clean, build succeeds

## Self-Check: PASSED
