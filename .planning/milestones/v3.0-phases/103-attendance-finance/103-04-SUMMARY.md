---
phase: 103-attendance-finance
plan: "04"
subsystem: admin-app/pages + admin-app/features + admin-app/components
tags: [finance, revenue-chart, online-payments, rbac, zero-fill, lock-guard, tanstack-query]
dependency_graph:
  requires: [103-01, 103-03]
  provides: [FinancePage(real), RevenueChart, OnlinePaymentsTable, features/finance/api(delegated)]
  affects: []
tech_stack:
  added: []
  patterns: [owner-gated-lock-guard, zero-fill-charts, read-only-sign-kopecks, split-outer-inner-rbac]
key_files:
  created:
    - apps/admin-app/src/pages/finance/components/RevenueChart.tsx
    - apps/admin-app/src/pages/finance/components/OnlinePaymentsTable.tsx
  modified:
    - apps/admin-app/src/features/finance/api.ts
    - apps/admin-app/src/pages/finance/FinancePage.tsx
    - apps/admin-app/src/pages/finance/components/parts.tsx
decisions:
  - "D-103-04-FINANCE-SPLIT: FinancePage split into outer RBAC guard (useSession only) + inner FinancePageContent (data hooks) — same pattern as D-103-03-CASHBOX-HOOKS-SPLIT; React Rules of Hooks safe"
  - "D-103-04-ALLZERO-EMPTYSTATE: All-zero revenue (after zero-fill) and all-empty online payments both render EmptyState inline instead of a flat-zero chart or empty table"
  - "D-103-04-TAB-QUERY-INTERFACES: RevenueQueryResult/OnlineQueryResult inline interfaces typed via top-level imports (RevenueBucket, PaymentData); inline import() annotations removed per @typescript-eslint/consistent-type-imports rule"
metrics:
  duration: "5m"
  completed: "2026-06-13"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 3
---

# Phase 103 Plan 04: Finance Page Wiring Summary

**One-liner:** FinancePage wired to real /reports/revenue (zero-filled, groupBy day|month, signed netKopecks) and /payments?method=online (paginated) with Lock-EmptyState RBAC guard; mock tabs removed.

## What Was Built

### Task 1: features/finance/api.ts delegation

Replaced the mock `features/finance/api.ts` (which had `useFinance()` returning `mockResponse(financeData)`) with a thin delegation layer:

- `export { useRevenueReport } from '@/features/reports/api'` — owner-gated via can(role,'view','reports')
- `export { usePaymentsLedger as useOnlinePayments } from '@/features/payments/api'` — owner-gated via can(role,'view','payments')
- `export { ApiError } from '@/features/reports/api'` — ESLint import boundary

Removed: `mockResponse`, `financeData` import, mock `useFinance` hook, `financeKeys`.

### Task 2: FinancePage restructure + new components

**FinancePage.tsx (REWRITTEN):**
- Outer `FinancePage`: RBAC guard — `useSession()` → `!can(role,'view','reports')` → Lock-EmptyState BEFORE any data hook (T-103-04-RBAC)
- Inner `FinancePageContent`: data hooks only when guard passes (D-103-04-FINANCE-SPLIT)
- State: `fromDate`/`toDate` (last 30 days), `groupBy` ('day'), active `tab`, `page`
- `<DateRangePicker>` in PageHeader actions (reused from Plan 03)
- `FinanceTabs` with exactly 2 tabs: «Выручка» and «Онлайн-платежи»
- Removed: «Неудачные», «Выплаты тренерам», «Экспорт» CSV button, all mock STATE_OPTS/METHOD_OPTS

**RevenueChart.tsx (NEW):**
- Props: `{ buckets, fromDate, toDate, groupBy }`
- Zero-fills via `fillRevenueBuckets(buckets, fromDate, toDate, groupBy)` before chart
- Maps to `TrendPoint[]`: `label = period`, `value = netKopecks / 100` (rubles for Y-axis)
- Tooltip: signed formatRub, negative shown correctly
- All-zero → caller (FinancePage) shows inline EmptyState; chart not rendered (T-103-04-NONAN)
- Min 30 lines (actual: 65 lines)

**OnlinePaymentsTable.tsx (NEW):**
- Props: `{ items, total, page, pageSize, onPageChange }`
- Mirrors TransactionsCard row anatomy: icon chip, title, amount with signed prefix
- Refund rows: Undo2 chip `bg-danger-soft text-danger`, «Возврат», `−` U+2212 prefix — READ-ONLY
- Non-refund: CreditCard/User chip, «Абонемент»/«PT-пакет», `+` prefix
- Amount: `formatRub(Math.abs(amountKopecks) / 100)` — kopecks → rubles (T-103-04-MONEY)
- Server-side `<Pagination>` rendered when pageCount > 1

**parts.tsx (UPDATED):**
- Kept: `FinanceTabs`, `Panel`, `Toolbar`, `FinStatus` (used by FinanceModals.tsx)
- Removed: `FinanceKpi`, `RegTable`, `FailTable`, `PayTable` (only used in old FinancePage)
- Removed: mock type imports from finance/types (RegRow, FailRow, PayRow)

## Commits

| Hash | Description |
|------|-------------|
| 38f8a9b2 | feat(103-04): features/finance/api.ts delegation (useRevenueReport + useOnlinePayments re-exports) |
| 7ccd8ac1 | feat(103-04): restructure FinancePage to 2 real tabs with Lock guard, RevenueChart, OnlinePaymentsTable |

## Verification Results

- `pnpm -F @clubcore/admin-app typecheck` — exit 0
- `pnpm -F @clubcore/admin-app lint` — exit 0 (0 errors, 0 warnings; inline import() fixed)
- `pnpm -F @clubcore/admin-app test` — 311 tests across 23 files, all pass
- `pnpm -F @clubcore/admin-app build` — built in 2.58s, no errors
- FinancePage: Lock-EmptyState BEFORE any data hook for reception ✓
- Exactly 2 real tabs (Выручка + Онлайн-платежи); Неудачные/Выплаты/Экспорт absent ✓
- RevenueChart calls fillRevenueBuckets before mapping to chart ✓
- All-zero → EmptyState inline, not flat-zero chart ✓
- No new dependency in apps/admin-app/package.json ✓

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Inline import() type annotations in FinancePage.tsx**
- **Found during:** Task 2 lint phase
- **Issue:** TypeScript `import()` inline type annotations (e.g. `import('@/features/reports/schemas').RevenueBucket[]`) triggered `@typescript-eslint/consistent-type-imports` warnings
- **Fix:** Extracted `RevenueBucket` and `PaymentData` as top-level `import type` declarations; replaced inline annotations with the named types
- **Files modified:** `pages/finance/FinancePage.tsx`
- **Commit:** 7ccd8ac1

## Known Stubs

None. All hooks wire to real endpoints. Lock-EmptyState ensures reception makes zero owner-only API calls.

## Threat Surface Scan

All T-103-04-* threat mitigations implemented:
- **T-103-04-RBAC**: Lock-EmptyState BEFORE any data hook in FinancePage; useRevenueReport/useOnlinePayments are themselves enabled-gated ✓
- **T-103-04-MONEY**: netKopecks/100 for display; formatRub takes rubles; signed values render correctly; Math.abs display-only ✓
- **T-103-04-NONAN**: fillRevenueBuckets guarantees a bucket per period; all-zero → EmptyState (no NaN chart) ✓
- **T-103-04-PII**: Only amount/method/subjectKind/date shown in OnlinePaymentsTable; no card data, no raw payload ✓
- **T-103-SC**: No new packages added ✓

## Self-Check: PASSED

All key files exist on disk. Both task commits verified in git log.
