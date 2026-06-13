---
phase: 104-dashboard-reports-settings
fixed_at: 2026-06-13T23:15:00Z
review_path: .planning/phases/104-dashboard-reports-settings/104-REVIEW.md
iteration: 1
findings_in_scope: 12
fixed: 12
skipped: 0
status: all_fixed
---

# Phase 104: Code Review Fix Report

**Fixed at:** 2026-06-13T23:15:00Z
**Source review:** `.planning/phases/104-dashboard-reports-settings/104-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 12
- Fixed: 12
- Skipped: 0

All fixes verified: `pnpm -F @clubcore/admin-app typecheck && lint && test && build` — 337 tests pass, build succeeds.

---

## Fixed Issues

### CR-01: Owner-only hooks mount for ALL roles in DashboardPage

**Files modified:** `apps/admin-app/src/pages/dashboard/DashboardPage.tsx`
**Commit:** `580c8077`
**Applied fix:** Extracted all owner-only hooks (`useRevenueReport`, `useVisitsReport`, `useClientsReport`, `useTrainersReport`) into a new inner `DashboardOwnerSection` component that only mounts when `isOwner === true`. The outer `DashboardPage` now calls only both-role hooks (`useScheduleToday`, `useExpiringMemberships`). Reception users never instantiate owner-only hook observers — structural enforcement, not just an `enabled` gate.

---

### CR-02: KpiStrip "Выручка сегодня" displays 30-day aggregate

**Files modified:** `apps/admin-app/src/pages/dashboard/DashboardPage.tsx`
**Commit:** `580c8077`
**Applied fix:** Changed `netKopecks` from a `reduce` sum over all 30 buckets to `revenueQ.data?.buckets.find(b => b.period === today)?.netKopecks ?? 0` — extracts today's individual bucket. The 30-day window is still fetched for the `RevenueChart`, but the KPI tile now shows today's revenue only, matching the label «Выручка сегодня». Defaults to 0 (not NaN) on empty.

---

### CR-03: ExpiringMemberships passes UUID as clientName to extend modal

**Files modified:** `apps/admin-app/src/pages/dashboard/components/ExpiringMemberships.tsx`
**Commit:** `0c1e246f`
**Applied fix:** Changed `extend: { clientName: item.clientId }` to `extend: { clientName: planName }` (which is `item.planSnapshot.name`). Also corrected `getInitials` to use `planName` instead of `item.clientId`. Added a comment noting that when `clientFullName` becomes available on the membership wire shape, this should be updated. The modal no longer displays a raw UUID.

---

### WR-01: `downloadCsv` anchor not appended to DOM before click

**Files modified:** `apps/admin-app/src/api/csv.ts`
**Commit:** `ec12be19`
**Applied fix:** Added `a.style.display = 'none'`, `document.body.appendChild(a)` before `.click()`, and `document.body.removeChild(a)` after. `URL.revokeObjectURL` kept in place after removal. Firefox reliability fix per the standard programmatic download pattern.

---

### WR-02: `AuditItemList` receives dead `fromDate` prop

**Files modified:** `apps/admin-app/src/pages/audit/AuditPage.tsx`
**Commit:** `3005b0d9`
**Applied fix:** Removed `fromDate` from the `AuditItemList` function signature and its prop type definition. Removed the `fromDate={fromDate}` attribute from the single call site. Removed the `void fromDate` suppression line. The component still groups items by date using `item.createdAt` directly.

---

### WR-03: `OccupancyHours` uses local clock hour instead of MSK

**Files modified:** `apps/admin-app/src/pages/dashboard/components/OccupancyHours.tsx`
**Commit:** `c856d4d9`
**Applied fix:** Added `getMskHour()` helper using `new Date().toLocaleString('en-US', { hour: 'numeric', hour12: false, timeZone: 'Europe/Moscow' })` parsed as integer. Replaced both occurrences of `new Date().getHours()` — in `getHourState()` and in the X-axis bold-label check — with `getMskHour()`.

---

### WR-04: `monthStart` computed using local timezone

**Files modified:** `apps/admin-app/src/pages/dashboard/DashboardPage.tsx`
**Commit:** `580c8077`
**Applied fix:** Inside `DashboardOwnerSection`, derived `monthStart` from the MSK-aware `today` string (already `'YYYY-MM-DD'` in Moscow timezone): `today.slice(0, 7) + '-01'`. Eliminates the `new Date().getFullYear()` / `new Date().getMonth()` local-timezone derivation which could return the previous month near midnight for non-MSK users.

---

### WR-05: `hasFilter` excludes date range — wrong empty state

**Files modified:** `apps/admin-app/src/pages/audit/AuditPage.tsx`
**Commit:** `3005b0d9`
**Applied fix:** Added two module-level constants `INITIAL_FROM_DATE = mskDaysAgoISO(29)` and `INITIAL_TO_DATE = mskTodayISO()`. The `useState` initializers now reference these constants. `hasFilter` updated to include `fromDate !== INITIAL_FROM_DATE || toDate !== INITIAL_TO_DATE` — when only the date range is narrowed, the correct «Измените фильтры» empty state is shown.

---

### IN-01: Missing semicolons in features/settings and features/users files

**Files modified:** `apps/admin-app/src/features/settings/schemas.ts`, `apps/admin-app/src/features/settings/api.ts`, `apps/admin-app/src/features/users/schemas.ts`, `apps/admin-app/src/features/users/api.ts`
**Commit:** `eaa67ea5`
**Applied fix:** Added semicolons to all statement-terminating positions across all four files to match `apps/admin-app/.prettierrc` (`"semi": true`). All import statements, const declarations, type declarations, and function-terminating braces updated.

---

### IN-02: Legacy `useReports` mock still exported from `features/reports/api.ts`

**Files modified:** `apps/admin-app/src/features/reports/api.ts`
**Commit:** `55fef6ee`
**Applied fix:** Confirmed no importers (grep across full src/ found zero references outside the file itself). Removed: `useReports()` function, `reportsKeys` const, `reportsData` import from `@/mocks/reports`, `ReportsData` type import from `./types`, `mockResponse` from the `@/api/client` import, and the legacy-compat comment block. Dead weight eliminated.

---

### IN-03: `TrainerRow` name conflict in ReportsPage

**Files modified:** `apps/admin-app/src/pages/reports/ReportsPage.tsx`
**Commit:** `3af40a12`
**Applied fix:** Renamed the local function component from `TrainerRow` to `ReportsTrainerRow`. Updated the single JSX call site at line 504. The imported `TrainerRow` type from `@/features/reports/schemas` is unchanged and continues to be used in the component's prop signature (`row: TrainerRow`). No naming collision remains.

---

### IN-04: Date variables recalculated every render in DashboardPage

**Files modified:** `apps/admin-app/src/pages/dashboard/DashboardPage.tsx`
**Commit:** `580c8077`
**Applied fix:** Wrapped `today` in `useMemo(() => mskTodayISO(), [])` in the outer `DashboardPage`. Inside `DashboardOwnerSection`, wrapped `from30`, `monthStart`, and `monthName` in `useMemo` with stable deps (`[]` and `[today]`/`[monthStart]`). Query keys derived from these values are now stable across re-renders, preventing unnecessary refetch churn.

---

_Fixed: 2026-06-13T23:15:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
