---
phase: 103-attendance-finance
fixed_at: 2026-06-13T21:25:00Z
review_path: .planning/phases/103-attendance-finance/103-REVIEW.md
iteration: 1
findings_in_scope: 11
fixed: 11
skipped: 0
status: all_fixed
---

# Phase 103: Code Review Fix Report

**Fixed at:** 2026-06-13T21:25:00Z
**Source review:** `.planning/phases/103-attendance-finance/103-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 11 (4 Critical + 5 Warning + 2 Info)
- Fixed: 11
- Skipped: 0

Post-fix verification: `pnpm -F @clubcore/admin-app typecheck && lint && test && build` — all green.
Test count: 316 passed (up from 311; +5 new MSK date helper tests).

## Fixed Issues

### CR-01: DateRangePicker does not sync when parent `from`/`to` props change

**Files modified:** `apps/admin-app/src/components/common/DateRangePicker.tsx`
**Commit:** `3889bcf2`
**Applied fix:** Added two `useEffect` hooks that call `setLocalFrom(from)` and `setLocalTo(to)` when their respective props change. Combined with CR-02 fix in the same commit.

---

### CR-02: `todayISO()` / `daysAgoISO()` use UTC `.toISOString()` — wrong date for MSK 00:00–02:59

**Files modified:**
- `apps/admin-app/src/lib/format.ts` (new `mskTodayISO()` and `mskDaysAgoISO()` helpers)
- `apps/admin-app/src/lib/format.test.ts` (new tests for MSK date helpers)
- `apps/admin-app/src/components/common/DateRangePicker.tsx`
- `apps/admin-app/src/pages/attendance/AttendancePage.tsx`
- `apps/admin-app/src/pages/cashbox/CashboxPage.tsx`
- `apps/admin-app/src/pages/load/LoadPage.tsx`
- `apps/admin-app/src/pages/finance/FinancePage.tsx`

**Commit:** `3889bcf2`
**Applied fix:** Created `mskTodayISO()` and `mskDaysAgoISO(n)` in `@/lib/format` using `toLocaleDateString('sv-SE', { timeZone: 'Europe/Moscow' })` (sv-SE locale yields ISO YYYY-MM-DD natively). Removed all 5 duplicate local `todayISO()`/`daysAgoISO()`/`subtractDays()` implementations and replaced with the shared helpers. Added 5 unit tests asserting the correct Moscow calendar day is returned including during the critical 23:00 UTC window (00:00–02:59 MSK).

---

### CR-03: `useCheckIn` optimistic rollback misses `byClient` cache key family

**Files modified:** `apps/admin-app/src/features/visits/api.ts`
**Commit:** `314805cc`
**Applied fix:** Extended `cancelQueries`, `getQueriesData` (snapshot), and `invalidateQueries` to use `visitsKeys.all` (the `['visits']` root prefix) instead of `visitsKeys.lists()`. Updated the `CheckInCtx` type to `allSnapshots` covering all visits queries. The rollback `onError` handler now iterates `ctx.allSnapshots`. Also updated the optimistic `gymDate` to use `toLocaleDateString('sv-SE', { timeZone: 'Europe/Moscow' })` consistent with CR-02.

---

### CR-04: Numeric query-param guards silently drop value `0`

**Files modified:**
- `apps/admin-app/src/features/visits/api.ts`
- `apps/admin-app/src/features/payments/api.ts`

**Commit:** `b68f537e`
**Applied fix:** Changed `if (filter.page)` → `if (filter.page != null)` and `if (filter.pageSize)` → `if (filter.pageSize != null)` in both `useVisitsList` and `usePaymentsLedger`, ensuring the value `0` is never silently dropped.

---

### WR-01: `TransactionsCard` `first` prop uses raw array index instead of `firstOfDate`

**Files modified:** `apps/admin-app/src/pages/cashbox/components/TransactionsCard.tsx`
**Commit:** `c67008c2`
**Applied fix:** Changed `first={i === 0}` to `first={row.firstOfDate}` in the `rows.map()` render loop, and removed the unused `i` index parameter from the arrow function. `firstOfDate` is already computed in the row-building loop above and correctly identifies the first `PaymentRow` in each date group.

---

### WR-02: `formatDateRu` / `formatWeekdayLongRu` / `formatRelativeRu` / `formatTime` use `new Date(dateOnlyString)`

**Files modified:** `apps/admin-app/src/lib/format.ts`
**Commit:** `3889bcf2`
**Applied fix:** Added `parseISO` to the `date-fns` import. All four format functions now use `parseISO(date)` instead of `new Date(date)` when the input is a string. `parseISO` interprets date-only strings as local midnight per RFC 3339, avoiding the UTC midnight shift that occurs with ECMA-262 date-only parsing. This directly fulfills the CLAUDE.md Dates convention: "Never `new Date(dateOnlyString)` (DST risk)".

---

### WR-03: `LoadHeatmapCard` passes `yMax=0` to `AreaTrendChart` on all-zero data

**Files modified:** `apps/admin-app/src/pages/load/components/LoadHeatmapCard.tsx`
**Commit:** `5a5216b8`
**Applied fix:** Changed `yMax={Math.max(...daily.map((b) => b.count), 0)}` to `yMax={Math.max(...daily.map((b) => b.count), 0) || undefined}`, matching the same `|| undefined` pattern used by `RevenueChart`. When all daily counts are zero, `yMax` becomes `undefined` and the chart auto-scales, preventing a potential divide-by-zero in the Y-axis domain calculation.

---

### WR-04: `useVisitsReport` / `useRevenueReport` cause session double-waterfall

**Files modified:**
- `apps/admin-app/src/features/reports/api.ts`
- `apps/admin-app/src/features/load/api.ts`
- `apps/admin-app/src/pages/load/LoadPage.tsx`
- `apps/admin-app/src/pages/finance/FinancePage.tsx`

**Commit:** `a584eea5`
**Applied fix:** Removed the internal `useSession()` calls from `useVisitsReport` and `useRevenueReport`. Both hooks now accept `role: Role` as a parameter, mirroring `usePaymentsLedger`. Updated the call chain: `LoadPage` (which already calls `useSession()` for the RBAC guard) now passes `role` down to `LoadPageContent` → `useLoad(query, role)` → `useVisitsReport(query, role)`. `FinancePageContent` already received `role` from `FinancePage` and now passes it to `useRevenueReport`. The `useSession` import was removed from `reports/api.ts` as it is no longer used.

---

### WR-05: `CheckInModal` uses hardcoded hex `#2dd4a4` for avatar color

**Files modified:** `apps/admin-app/src/components/modals/CheckInModal.tsx`
**Commit:** `4f8f5c07`
**Applied fix:** Added a module-level constant `const AVATAR_COLOR = 'var(--color-primary)'` and replaced both `color="#2dd4a4"` occurrences with `color={AVATAR_COLOR}`. Combined with IN-02 fix in the same commit.

---

### IN-01: `routeRegistry` missing the `load` route entry

**Files modified:** `apps/admin-app/src/shared/session/registry.ts`
**Commit:** `2a815161`
**Applied fix:** Added `{ path: ROUTES.load, resource: 'reports', label: 'Загруженность', icon: 'Clock', navKey: 'finance' }` to the `routeRegistry` array, after the `attendance` entry. The route smoke test now covers `/load`.

---

### IN-02: `getInitials` duplicated in `CheckInModal.tsx`

**Files modified:** `apps/admin-app/src/components/modals/CheckInModal.tsx`
**Commit:** `4f8f5c07`
**Applied fix:** Removed the local `getInitials` function definition and added `import { getInitials } from '@/lib/format'` to the existing imports. The shared export from `@/lib/format` is identical in semantics (both split on whitespace, take first two words, uppercase first char) and is already used by `VisitsList.tsx`.

---

_Fixed: 2026-06-13T21:25:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
