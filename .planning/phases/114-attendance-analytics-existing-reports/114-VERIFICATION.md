---
phase: 114-attendance-analytics-existing-reports
verified: 2026-06-15T13:40:00Z
status: human_needed
score: 9/9 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Open /load as Owner with a date range that has real visit data. Verify the day-of-week bar list (Пн–Вс), peak-hour KPI tile, daily-volume frequency histogram (bar chart, 6 bins), and 'Скоро' duration placeholder all render below the heatmap."
    expected: "Four analytics widgets visible below the existing heatmap. Bar list shows proportional bars with the peak weekday highlighted in primary colour. Peak-hour tile shows '{h}:00–{h+1}:00' and '{count} визитов'. Frequency histogram shows a bar chart over 6 bins. Duration card shows Clock icon + explanatory text + 'Скоро' badge with no numeric data."
    why_human: "Visual layout, colour correctness, responsive grid (md:grid-cols-2), and ARIA landmark cannot be verified programmatically."
  - test: "Open /load as Owner and select a date range with NO visits. Verify the page shows only the existing 'Нет данных за этот период' EmptyState — none of the four new widgets appear."
    expected: "Single all-zero EmptyState; no DayOfWeekCard, PeakHourCard, FrequencyCard, or DurationPlaceholderCard rendered."
    why_human: "Branch exclusivity (allZero path vs non-zero path) is structural in JSX; cannot observe visually with grep."
  - test: "Log in as Reception role and navigate to /load. Verify the Lock EmptyState is shown and none of the analytics widgets render."
    expected: "'Недостаточно прав' Lock EmptyState displayed; no data fetched, no widgets rendered."
    why_human: "RBAC early-return must be confirmed visually in the browser — grep confirms the guard exists but not that it fires correctly at runtime."
  - test: "On /load with real data, verify that the frequency histogram renders as a bar chart (discrete bins, no smooth interpolation) — not a smooth area curve."
    expected: "Six discrete vertical bars with no smooth interpolation between bins. No gradient fill under the bars that implies area-under-curve semantics."
    why_human: "Chart rendering type (bar vs monotone-area) requires visual inspection; cannot be confirmed from JSX alone."
---

# Phase 114: Attendance Analytics (Existing Reports) Verification Report

**Phase Goal:** Owner sees real attendance analytics derived from the already-shipped reports/visits aggregate — the built-but-unwired analytics widgets render live data.
**Verified:** 2026-06-15T13:40:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | deriveDayOfWeek groups daily[] by MSK-safe weekday (Mon-first) with zero-filled 7 buckets and never returns NaN | VERIFIED | `derive.ts:59` uses `parseISO`; `derive.ts:70` guards `daysWithData === 0 ? 0 : …`; `derive.test.ts:17-26` all-zero case asserts no NaN; 16/16 tests pass |
| 2 | derivePeakHour returns the earliest-hour argmax (order-independent) over hourly[] and null when all counts are 0 | VERIFIED | `derive.ts:96-108` single-pass argmax with `bucket.hour < best.hour` tie-break; `derive.test.ts:100-112` tests unordered/sparse input explicitly; test passes |
| 3 | deriveFrequency buckets days by daily visit-count into 6 fixed ranges (0–4 … 25+), zero-filled, never NaN | VERIFIED | `derive.ts:119-154`; `derive.test.ts:116-161` covers empty, boundary 4/5, count=3→"0–4", count=99→"25+"; all pass |
| 4 | Vitest unit tests cover all-zero, single-bucket, NaN-guard, MSK weekday grouping, peak-hour tie-break, unordered-input | VERIFIED | `derive.test.ts` 16 tests; `pnpm exec vitest run src/pages/load/components/derive.test.ts` → 16/16 passed |
| 5 | Owner on /load sees a day-of-week bar list, a peak-hour KPI tile, a daily-volume frequency histogram, and a "Скоро" duration placeholder below the existing heatmap | VERIFIED (code) / human needed (visual) | `LoadPage.tsx:102-109` — all four widgets in the non-zero data branch below `LoadHeatmapCard` |
| 6 | All four widgets are fed from the already-destructured hourly/daily — no new hooks or API calls | VERIFIED | 0 occurrences of `useLoad`/`fetch`/`useQuery` in any of the four widget files; `LoadPage.tsx` has exactly 1 `useLoad` call (line 58) |
| 7 | The duration placeholder shows a coming-soon state with NO fabricated/mock data | VERIFIED | `DurationPlaceholderCard.tsx` — no props, no numeric values, no state; only static copy + Clock icon + "Скоро" badge |
| 8 | Reception still sees only the existing Lock EmptyState — widgets never render for reception | VERIFIED (code) / human needed (runtime) | `LoadPage.tsx:39-48` early-return `can(role,'view','reports')` guard before any data hook fires |
| 9 | Empty period still shows the single existing all-zero EmptyState; widgets do not render in that branch | VERIFIED (code) | `LoadPage.tsx:92-98` allZero branch renders only `EmptyState`; four widgets are in the else-branch |

**Score:** 9/9 truths verified (7 fully automated, 2 require browser UAT confirmation)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/admin-app/src/pages/load/components/derive.ts` | Pure derivation functions | VERIFIED | 155 lines; exports `deriveDayOfWeek`, `derivePeakHour`, `deriveFrequency` + 3 interfaces; `parseISO` used (not `new Date`); all division guarded |
| `apps/admin-app/src/pages/load/components/derive.test.ts` | Vitest edge-case coverage | VERIFIED | 162 lines, 16 tests (Plan-01 expected 15; WR-01 fix added 1 more); all pass |
| `apps/admin-app/src/pages/load/components/DayOfWeekCard.tsx` | Weekday bar list in Card chrome | VERIFIED | 52 lines; calls `deriveDayOfWeek`; `maxTotal === 0 ? 0` guard; semantic tokens only |
| `apps/admin-app/src/pages/load/components/PeakHourCard.tsx` | Peak-hour KpiTile in Card | VERIFIED | 32 lines; calls `derivePeakHour`; `peak ? '{h}:00–{h+1}:00' : '—'` null fallback |
| `apps/admin-app/src/pages/load/components/FrequencyCard.tsx` | Frequency bar chart in Card | VERIFIED | 58 lines; calls `deriveFrequency`; renders `BarChart` (not `AreaTrendChart`; WR-03 fix from REVIEW) |
| `apps/admin-app/src/pages/load/components/DurationPlaceholderCard.tsx` | Coming-soon card, no mock data | VERIFIED | 28 lines; no props; Clock icon + copy + "Скоро" badge; zero numeric values |
| `apps/admin-app/src/pages/load/LoadPage.tsx` | Composes four widgets below heatmap | VERIFIED | Imports all four; renders inside non-zero branch at lines 101-109 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `derive.ts` | `@/features/reports/schemas` | `import type VisitsReportDailyBucket / VisitsReportHourlyBucket` | WIRED | Line 16: `import type { VisitsReportDailyBucket, VisitsReportHourlyBucket } from '@/features/reports/schemas'` |
| `derive.ts` | `date-fns parseISO` | MSK-safe weekday parse | WIRED | Line 15: `import { parseISO } from 'date-fns'`; line 59: `parseISO(bucket.date)`; no `new Date(dateOnly)` |
| `DayOfWeekCard.tsx` | `./derive` | `import deriveDayOfWeek` | WIRED | Line 15 import; line 18 call |
| `PeakHourCard.tsx` | `@/components/ui/KpiTile` | KpiTile render | WIRED | Line 11 import; lines 22-28 render |
| `FrequencyCard.tsx` | `./derive` | `import deriveFrequency` | WIRED | Line 16 import; line 21 call |
| `LoadPage.tsx` | Four new widget components | Render below LoadHeatmapCard in non-allZero branch | WIRED | Lines 26-29 imports; lines 103-108 JSX render |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `DayOfWeekCard` | `daily` prop | `LoadPage.tsx` line 65: `data?.daily ?? []`; `useLoad` → `staffRequest('get', '/api/v1/reports/visits', …)` | Yes — real backend REST call | FLOWING |
| `PeakHourCard` | `hourly` prop | `LoadPage.tsx` line 64: `data?.hourly ?? []`; same `useLoad` call | Yes — real backend REST call | FLOWING |
| `FrequencyCard` | `daily` prop | Same as DayOfWeekCard | Yes — real backend REST call | FLOWING |
| `DurationPlaceholderCard` | (none) | No data source — intentional coming-soon state | N/A — no data expected | FLOWING (by design; no data is correct) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| derive.ts tests all pass | `pnpm exec vitest run src/pages/load/components/derive.test.ts` | 16/16 passed in 4ms | PASS |
| Full test suite green (371 tests) | `pnpm -F @clubcore/admin-app test` | 371/371 passed | PASS |
| TypeScript clean | `pnpm -F @clubcore/admin-app typecheck` | No errors | PASS |
| ESLint clean | `pnpm -F @clubcore/admin-app lint` | No violations | PASS |

### Probe Execution

No probe scripts defined for this phase (frontend-only, no migration probes).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| ANL-01 | Plans 114-01, 114-02 | Owner sees real attendance analytics widgets driven by existing `reports/visits` aggregate — hourly heatmap (pre-existing), hour-curve, day-of-week, peak, frequency, and duration | SATISFIED | `derive.ts` (3 derivation functions + 3 interfaces); 4 widget components; `LoadPage.tsx` composition; 371 tests green; typecheck + lint clean |

### Anti-Patterns Found

No debt markers (TBD, FIXME, XXX) found in any Phase 114 files. The `DurationPlaceholderCard` is an intentional coming-soon state documented in the threat register (T-114-05, accept disposition) — not a stub.

**Note on `FrequencyCard.tsx` — WR-03 fix confirmed:** The REVIEW flagged that a frequency histogram rendered as a smooth `AreaTrendChart` misrepresents discrete-bin data. The executor fixed this by replacing `AreaTrendChart` with a proper `BarChart` (Recharts). The actual `FrequencyCard.tsx` in the codebase uses `BarChart` — the SUMMARY.md description (which mentioned `AreaTrendChart`) is stale and reflects the pre-REVIEW state.

**Note on WR-01 fix confirmed:** The REVIEW flagged that `derivePeakHour` relied on input ordering for tie-breaking. The fix makes the tie-break order-independent (`bucket.hour < best.hour` comparison) and a test for unordered/sparse input was added (`derive.test.ts:100-112`). This explains the test count being 16, not 15 as the SUMMARY states.

### Human Verification Required

#### 1. Owner analytics widgets visible with real data

**Test:** Log in as Owner, navigate to /load, select any date range that includes visits. Scroll past the heatmap.
**Expected:** DayOfWeekCard (7-row bar list Пн–Вс with proportional bars; peak weekday in primary colour), PeakHourCard (KpiTile with "{h}:00–{h+1}:00" and "{count} визитов"), FrequencyCard (6-bin bar chart; no smooth interpolation), DurationPlaceholderCard (Clock icon + explanatory copy + "Скоро" badge, no numbers).
**Why human:** Visual layout, colour correctness, responsive 2-column grid (md:grid-cols-2), and ARIA landmark cannot be confirmed by static analysis.

#### 2. All-zero date range hides widgets

**Test:** On /load as Owner, select a narrow date range with no visits.
**Expected:** Only the existing "Нет данных за этот период" EmptyState (BarChart3 icon). None of the four new widgets appear.
**Why human:** Branch exclusivity (allZero → EmptyState, not analytics section) must be confirmed in the running app.

#### 3. Reception role sees only Lock EmptyState

**Test:** Log in as Reception, navigate to /load.
**Expected:** "Недостаточно прав" Lock EmptyState; no data fetched; no analytics widgets visible.
**Why human:** Runtime RBAC gate must be confirmed in the browser; grep confirms the guard exists but not that it fires correctly at runtime.

#### 4. FrequencyCard renders discrete bars (not smooth area)

**Test:** On /load as Owner with real data, inspect the "Распределение дневной посещаемости" card.
**Expected:** Six discrete vertical bars. No smooth curve between bins. No gradient area fill.
**Why human:** Chart rendering type requires visual inspection even though the code uses `BarChart`.

### Gaps Summary

No gaps. All must-have truths are verified by code inspection and automated checks. The four human verification items are browser UAT confirmation only — they are auto-deferred per the operator-pending-verify-autodefer policy for autonomous runs.

---

_Verified: 2026-06-15T13:40:00Z_
_Verifier: Claude (gsd-verifier)_
