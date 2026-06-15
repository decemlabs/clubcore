---
phase: 114-attendance-analytics-existing-reports
plan: "01"
subsystem: frontend
tags: [analytics, pure-functions, vitest, tdd, date-fns, reports]
dependency_graph:
  requires: []
  provides:
    - "apps/admin-app/src/pages/load/components/derive.ts (DayOfWeekStat, PeakHour, FrequencyBucket interfaces + deriveDayOfWeek, derivePeakHour, deriveFrequency functions)"
  affects:
    - "apps/admin-app/src/pages/load/LoadPage.tsx (Plan 02 will wire widgets)"
tech_stack:
  added: []
  patterns:
    - "MSK-safe parseISO weekday grouping (Mon-first (getDay()+6)%7)"
    - "Zero-guard division: daysWithData === 0 ? 0 : total / daysWithData"
    - "Argmax with all-zero early-out returning null"
    - "Fixed 6-range frequency histogram with en-dash labels"
    - "noUncheckedIndexedAccess-safe array indexing with undefined guards"
key_files:
  created:
    - apps/admin-app/src/pages/load/components/derive.ts
    - apps/admin-app/src/pages/load/components/derive.test.ts
  modified: []
decisions:
  - "Used parseISO (not new Date) for all date-only string parsing — DST safety per CLAUDE.md"
  - "Frequency bucket labels use en-dash U+2013 ('0–4'…'25+') matching UI-SPEC Copywriting Contract"
  - "derivePeakHour returns null (not 0) for all-zero hourly data — cleaner null-check at widget sites"
  - "deriveDayOfWeek initializes avgPerWeekday in a second pass after accumulation — cleaner than mutating mid-loop"
metrics:
  duration: "~2 minutes"
  completed: "2026-06-15"
  tasks_completed: 2
  files_created: 2
  files_modified: 0
---

# Phase 114 Plan 01: Visits Aggregate Derivation Layer Summary

Pure client-side derivation module over the visits aggregate — MSK-safe weekday grouping, peak-hour argmax, and daily-volume frequency histogram — with full Vitest coverage of zero/NaN/tie edge cases.

## What Was Built

### derive.ts (155 lines)

Three exported pure functions and their return-type interfaces, imported type-only from `@/features/reports/schemas`:

**`deriveDayOfWeek(daily)`** — groups `VisitsReportDailyBucket[]` by Mon-first weekday using `parseISO` (never `new Date(dateOnly)`). Returns exactly 7 `DayOfWeekStat` buckets (`weekday 0–6`, Russian label, `total`, `daysWithData`, `avgPerWeekday`). Division guarded: `daysWithData === 0 ? 0 : total / daysWithData`.

**`derivePeakHour(hourly)`** — computes `Math.max` over `VisitsReportHourlyBucket[]` with a 0 sentinel. Returns `PeakHour | null` — null when all counts are zero. Ties resolve to the earlier hour (first-found argmax).

**`deriveFrequency(daily)`** — buckets daily visit counts into 6 fixed ranges: `0–4`, `5–9`, `10–14`, `15–19`, `20–24`, `25+` (en-dash U+2013 per UI-SPEC Copywriting Contract). Returns `FrequencyBucket[]` with `label` and `count` (number of days in that range). Zero-filled; `findIndex`-based range lookup guarded for `noUncheckedIndexedAccess`.

### derive.test.ts (148 lines, 15 tests)

TDD suite following `sort.test.ts` structure. Three `describe` blocks with Russian `it()` names:

- `deriveDayOfWeek`: empty → 7 buckets avg=0 no NaN; single day; MSK weekday `2024-01-15 = Пн (0)`; label order; multi-day average
- `derivePeakHour`: all-zero → null; empty → null; single non-zero; tie → earlier hour
- `deriveFrequency`: empty → 6 buckets count=0; en-dash label contract; `count=3 → 0–4`; `count=25 → 25+`; `count=99 → 25+`; boundary 4/5

All 15 tests green. Typecheck and lint clean.

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED (`test(...)`) | `590f8d84` | Confirmed failing (module missing) |
| GREEN (`feat(...)`) | `bbf72958` | All 15 tests pass |
| REFACTOR | N/A | Code clean; no refactor needed |

## Verification Results

- `pnpm exec vitest run src/pages/load/components/derive.test.ts` → 15/15 passed
- `pnpm -F @clubcore/admin-app typecheck` → no errors
- `pnpm -F @clubcore/admin-app lint` → no errors
- No React/JSX import in derive.ts (pure logic module confirmed)
- No new dependency added to package.json (date-fns already present)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — derive.ts is pure logic with no data sources or UI rendering. No stubs exist.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. This is a pure client-side transformation module over already-fetched, Zod-validated data. T-114-01 mitigation (divide-by-zero / argmax guards) implemented as required.

## Self-Check

- [x] `apps/admin-app/src/pages/load/components/derive.ts` — created and exists
- [x] `apps/admin-app/src/pages/load/components/derive.test.ts` — created and exists
- [x] Commit `590f8d84` (RED) — exists in git log
- [x] Commit `bbf72958` (GREEN) — exists in git log
- [x] 15 tests pass, typecheck clean, lint clean

## Self-Check: PASSED
