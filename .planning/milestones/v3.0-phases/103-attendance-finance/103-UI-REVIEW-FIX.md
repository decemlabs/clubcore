---
phase: 103
fixed_at: 2026-06-13T21:26:00+03:00
review_path: .planning/phases/103-attendance-finance/103-UI-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 103: Code Review Fix Report

**Fixed at:** 2026-06-13
**Source review:** .planning/phases/103-attendance-finance/103-UI-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3
- Fixed: 3
- Skipped: 0

## Fixed Issues

### BLOCKER: Attendance page missing date-range picker

**Files modified:** `apps/admin-app/src/pages/attendance/AttendancePage.tsx`, `apps/admin-app/src/pages/attendance/components/AttendancePageHead.tsx`
**Commit:** d990c42f
**Applied fix:**
- `AttendancePage`: replaced two bare `const from = mskDaysAgoISO(29)` / `const to = mskTodayISO()` (re-evaluated every render, no UI control) with `useState(DEFAULT_FROM)` / `useState(DEFAULT_TO)` where `DEFAULT_FROM`/`DEFAULT_TO` are module-level constants initialised once.
- Added `handleRangeChange(nextFrom, nextTo)` that updates state and resets `page` to 1.
- Passed `<DateRangePicker from={from} to={to} onChange={handleRangeChange} />` as the new `dateRangePicker` prop to `AttendancePageHead`.
- `AttendancePageHead`: added optional `dateRangePicker?: ReactNode` prop and `import type { ReactNode }` from React. Rendered the picker in a responsive flex wrapper alongside the existing «Чек-ин» button; added `actionsClassName="items-start"` on `PageHeader` to align the stacked layout at the top edge (same pattern as `CashboxPageHead`).

### WARNING: `hasFilter = true` constant makes «Визитов пока нет» dead code

**Files modified:** `apps/admin-app/src/pages/attendance/AttendancePage.tsx`
**Commit:** d990c42f (same atomic commit as above)
**Applied fix:**
- Replaced `const hasFilter = true` with `const hasFilter = from !== DEFAULT_FROM || to !== DEFAULT_TO`.
- When the date range equals the module-level defaults (user has not interacted with the picker), `hasFilter` is `false` and `VisitsList` shows the onboarding empty state «Визитов пока нет · Зафиксируйте первый визит, нажав «Чек-ин»» for a zero-visit install.
- When the user changes the range to any non-default value, `hasFilter` becomes `true` and the filtered empty state «Нет визитов · За выбранный период визитов не зафиксировано» is shown. Both branches are now reachable.

### WARNING: Finance subtitle renders raw ISO date strings

**Files modified:** `apps/admin-app/src/pages/finance/FinancePage.tsx`
**Commit:** d990c42f (same atomic commit)
**Applied fix:**
- Added `formatDateRu` to the existing `@/lib/format` import line (was `mskTodayISO, mskDaysAgoISO`).
- Changed `subtitle={\`${fromDate} – ${toDate} · выручка и онлайн-платежи\`}` to `subtitle={\`${formatDateRu(fromDate, 'dd.MM.yy')} – ${formatDateRu(toDate, 'dd.MM.yy')} · выручка и онлайн-платежи\`}`.
- Result: subtitle now shows e.g. «14.05.26 – 13.06.26 · выручка и онлайн-платежи» instead of the raw «2026-05-14 – 2026-06-13 · …». Consistent with `AttendancePage` subtitle and `TotalVisitsKpi` which both use `formatDateRu(…, 'dd.MM.yy')`.

## Verification

All checks passed after fixes were applied:

- `pnpm -F @clubcore/admin-app typecheck` — clean (0 errors)
- `pnpm -F @clubcore/admin-app lint` — clean (0 warnings)
- `pnpm -F @clubcore/admin-app test` — 316/316 passed
- `pnpm -F @clubcore/admin-app build` — built in 2.58s (no errors)

---

_Fixed: 2026-06-13_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
