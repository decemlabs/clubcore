---
phase: 104-dashboard-reports-settings
plan: "02"
subsystem: admin-app/dashboard
tags: [dashboard, role-gating, reports, bookings, memberships, kpi, tdd]
dependency_graph:
  requires:
    - 104-01 (useRevenueReport/useVisitsReport/useClientsReport/useTrainersReport hooks)
  provides:
    - useScheduleToday(date) — both-role bookings hook for dashboard
    - useExpiringMemberships() — both-role memberships expiring hook
    - Role-gated DashboardPage (owner full analytics, reception operational-only)
    - KpiStrip wired to real revenue/visits/expiring/bookings data
    - OccupancyHours wired to VisitsReportData + fillHourlyBuckets zero-fill
    - RevenueChart wired to RevenueReportData + fillRevenueBuckets zero-fill
    - TopTrainers wired to TrainersReportData with formatRub(kopecks/100)
    - ScheduleToday wired to BookingData[] with empty/loading/error states
    - ExpiringMemberships wired to MembershipData[] with daysUntil urgency
  affects:
    - apps/admin-app/src/features/dashboard/api.ts (rewritten — mock removed)
    - apps/admin-app/src/pages/dashboard/DashboardPage.tsx (rewritten)
    - apps/admin-app/src/pages/dashboard/components/* (all widgets rewritten)
tech_stack:
  added: []
  patterns:
    - staffRequest + Schema.parse(raw).data (both-role hooks, no enabled guard)
    - can(role,'view','reports') role-gate in DashboardPage JSX (card absence, not lock)
    - fillHourlyBuckets / fillRevenueBuckets zero-fill before charting
    - undefined/null/NaN guards in KpiStrip (safeInt helper)
    - Per-widget loading/error/empty states (independent loading, no full-page PageLoading)
    - TDD RED/GREEN for api.ts rewrite
key_files:
  modified:
    - apps/admin-app/src/features/dashboard/api.ts
    - apps/admin-app/src/features/dashboard/api.test.ts
    - apps/admin-app/src/pages/dashboard/DashboardPage.tsx
    - apps/admin-app/src/pages/dashboard/components/KpiStrip.tsx
    - apps/admin-app/src/pages/dashboard/components/OccupancyHours.tsx
    - apps/admin-app/src/pages/dashboard/components/RevenueChart.tsx
    - apps/admin-app/src/pages/dashboard/components/TopTrainers.tsx
    - apps/admin-app/src/pages/dashboard/components/ScheduleToday.tsx
    - apps/admin-app/src/pages/dashboard/components/ExpiringMemberships.tsx
    - apps/admin-app/src/pages/dashboard/components/PageHead.tsx
    - apps/admin-app/src/pages/dashboard/components/RevenueChart.test.tsx
decisions:
  - "D-104-02-RECEPTION-LAYOUT: Reception layout uses flex-col (no grid) with ScheduleToday + ExpiringMemberships only; owner-only hooks never mount — card absence not lock"
  - "D-104-02-ACTIVITY-FEED: ActivityFeed replaced with EmptyState + link to /audit-log; no /audit-log call from dashboard (expensive, no real-time need)"
  - "D-104-02-OCCUPANCY-NOW: OccupancyNow hidden for all roles — no real-time endpoint (comment in DashboardPage)"
  - "D-104-02-KPISTRIP-REAL: KpiStrip accepts KpiStripData interface with safeInt NaN guard; shows 0/0₽ on null/undefined"
  - "D-104-02-EXPIRING-MEMBERSHIP-COLOR: Avatar color derived from clientId hash (no fullName available in booking list response)"
  - "D-104-02-REVENUEDATA-EMPTY: Empty state shown when data.buckets.length === 0 (no transactions); zero-filled dates not treated as empty"
metrics:
  duration: "~8 minutes"
  completed: "2026-06-13"
  tasks: 2
  files_created: 0
  files_modified: 11
---

# Phase 104 Plan 02: Dashboard Wiring (Role-Gated) Summary

**One-liner:** Role-gated dashboard with real per-domain hooks — owner sees full KPI/Occupancy/Revenue/TopTrainers analytics, reception sees only ScheduleToday + ExpiringMemberships with zero owner-only API calls.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 RED | Failing tests for useScheduleToday/useExpiringMemberships re-exports | 5012103b | features/dashboard/api.test.ts |
| 1 GREEN | Per-domain dashboard hooks — useScheduleToday + useExpiringMemberships + re-export | 68ef57d2 | features/dashboard/api.ts |
| 2 | Role-gated DashboardPage + all widget components wired with empty guards | d0c1d684 | DashboardPage.tsx + 7 widget components + test |

## Verification

Full admin-app gate result:
- `typecheck`: PASS
- `lint`: PASS (0 errors, 0 warnings)
- `test`: PASS (337/337 tests, 26 test files)
- `build`: PASS (2.98s, no errors)

Automated criteria check:
```
grep -q "useScheduleToday" features/dashboard/api.ts ✓
grep -q "useExpiringMemberships" features/dashboard/api.ts ✓
grep -q "withinDays" features/dashboard/api.ts ✓
! grep -q "export function useDashboard" features/dashboard/api.ts ✓
grep -q "can(role, 'view', 'reports')" DashboardPage.tsx ✓
! grep -q "<ClientMessages" DashboardPage.tsx ✓
! grep -q "useDashboard" DashboardPage.tsx ✓
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] RevenueChart.test.tsx used old mock RevenueData type**
- **Found during:** Task 2 typecheck gate
- **Issue:** Pre-existing `RevenueChart.test.tsx` imported `RevenueData` from `features/dashboard/types` and passed it to the old `RevenueChart` component signature (which accepted mock-era `RevenueData`). After the component was rewritten to accept `RevenueReportData`, the test broke with TS2739.
- **Fix:** Rewrote `RevenueChart.test.tsx` to use `RevenueReportData` from `features/reports/schemas` and updated test assertions to match the new component interface.
- **Files modified:** `apps/admin-app/src/pages/dashboard/components/RevenueChart.test.tsx`
- **Commit:** d0c1d684

**2. [Rule 2 - Missing] PageHead required update for new data shape**
- **Found during:** Task 2 implementation
- **Issue:** PageHead accepted mock-era props (`dateLabel`, `greetingName`, `trainingsToday`, `expectedVisits`, `defaultPeriod`) from `DashboardData` which no longer exists. The new DashboardPage derives date from `mskTodayISO()` and name from `useSession()`.
- **Fix:** Rewrote PageHead to accept `fullName?: string` and `bookingsToday: number`, deriving date label from `mskTodayISO()` + `formatWeekdayLongRu()`.
- **Files modified:** `apps/admin-app/src/pages/dashboard/components/PageHead.tsx`
- **Commit:** d0c1d684

**3. [Rule 1 - Bug] RevenueChart empty state logic for zero-filled buckets**
- **Found during:** Test execution
- **Issue:** `fillRevenueBuckets([], fromDate, toDate, 'day')` fills 30 buckets with zero values, making `points.length === 0` never true. The empty state never triggered.
- **Fix:** Changed empty state condition to `data == null || data.buckets.length === 0` — checks raw API response, not the zero-filled output.
- **Commit:** d0c1d684

## Known Stubs

None — all dashboard widgets are wired to real data with proper empty/loading/error states.

**Note:** `ExpiringMemberships` shows client avatar initials derived from `item.clientId` (UUID) because the memberships list response does not embed `clientFullName`. The first 2 chars of the UUID are used as initials placeholder — acceptable for MVP; a future plan can add a client-name lookup.

## Threat Flags

No new threat surface beyond what the plan's threat model covers (T-104-04, T-104-05).

T-104-04 implementation verified: `can(role, 'view', 'reports')` gate in DashboardPage JSX prevents owner-only components from mounting for reception. Each report hook also keeps its own `enabled: can(role, 'view', 'reports')` double-gate from `features/reports/api.ts`.

## TDD Gate Compliance

- Task 1: RED commit 5012103b → GREEN commit 68ef57d2 ✓

## Self-Check: PASSED

All created files exist on disk. All task commits verified in git log.
