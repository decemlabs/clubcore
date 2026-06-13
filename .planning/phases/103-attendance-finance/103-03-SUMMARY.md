---
phase: 103-attendance-finance
plan: "03"
subsystem: admin-app/pages + admin-app/features + admin-app/components
tags: [cashbox, load, nav-gating, date-range-picker, rbac, tdd, zero-fill, refund-rows]
dependency_graph:
  requires: [103-01]
  provides: [DateRangePicker, useCashbox, computeDailyTotals, useLoad(wired), CashboxPage(real), LoadPage(real)]
  affects: [103-04]
tech_stack:
  added: []
  patterns: [owner-gated-lock-guard, tdd-red-green, client-side-daily-totals, zero-fill-charts, read-only-refund-rows]
key_files:
  created:
    - apps/admin-app/src/features/cashbox/utils.ts
    - apps/admin-app/src/features/cashbox/utils.test.ts
    - apps/admin-app/src/components/common/DateRangePicker.tsx
  modified:
    - apps/admin-app/src/layouts/AppLayout/nav-items.ts
    - apps/admin-app/src/features/cashbox/api.ts
    - apps/admin-app/src/features/load/api.ts
    - apps/admin-app/src/pages/cashbox/CashboxPage.tsx
    - apps/admin-app/src/pages/cashbox/components/CashboxPageHead.tsx
    - apps/admin-app/src/pages/cashbox/components/CashboxKpis.tsx
    - apps/admin-app/src/pages/cashbox/components/TransactionsCard.tsx
    - apps/admin-app/src/pages/load/LoadPage.tsx
    - apps/admin-app/src/pages/load/components/LoadPageHead.tsx
    - apps/admin-app/src/pages/load/components/LoadKpis.tsx
    - apps/admin-app/src/pages/load/components/LoadHeatmapCard.tsx
decisions:
  - "D-103-03-CASHBOX-HOOKS-SPLIT: CashboxPage split into CashboxPage (RBAC guard, calls useSession) + CashboxPageContent (data hooks). Avoids conditional hook call violation — useSession called unconditionally, then early return or render inner component."
  - "D-103-03-LOAD-HEATMAP-SINGLE-ROW: IntensityHeatmap shown with one row ('Часы') mapping the 24 hourly aggregate buckets. Real data is a single-period aggregate not a 7-day matrix; single row is the most faithful representation."
  - "D-103-03-MSK-SLICE: computeDailyTotals derives MSK date via receivedAt.slice(0,10) (ISO prefix) rather than TZ conversion. date-fns-tz not installed; backend stores MSK-anchored timestamps; slice is safe and avoids new dependency."
  - "D-103-03-FAKEREFUND: «Оформить возврат» dropdown removed from TransactionsCard per T-103-03-FAKEREFUND — no /payments refund endpoint exists."
metrics:
  duration: "15m"
  completed: "2026-06-13"
  tasks_completed: 3
  tasks_total: 3
  files_created: 3
  files_modified: 11
---

# Phase 103 Plan 03: Cashbox + Load + nav-gating + DateRangePicker Summary

**One-liner:** Owner-gated CashboxPage wired to real /payments ledger with signed refund rows and daily totals; LoadPage wired to zero-filled /reports/visits aggregate; shared DateRangePicker (366-cap + inversion guard); nav Касса+Загруженность gated ownerOnly.

## What Was Built

### Task 1: nav gating correction + cashbox api/utils (TDD) + load api

**nav-items.ts correction:**
- `Касса` entry: added `ownerOnly: true, ownerResource: 'payments'`
- `Загруженность` entry: added `ownerOnly: true, ownerResource: 'reports'`
- `Посещаемость`: unchanged (reception+owner, no gate)

**features/cashbox/utils.ts (NEW):**
- `computeDailyTotals(items: PaymentData[]): DailyTotal[]` — groups by MSK date (ISO prefix slice), sums signed amountKopecks, sorted ascending
- MSK note: backend returns MSK-anchored ISO strings; slice(0,10) extracts date safely without date-fns-tz

**features/cashbox/utils.test.ts (TDD):**
- RED: tests failed (utils.ts not yet created)
- GREEN: 8 tests pass — empty array, single payment, sale+refund=300k, net negative, multi-date sort, multi-payment sum, NaN guard
- noUncheckedIndexedAccess: fixed by using `.at(0)` instead of `[0]`

**features/cashbox/api.ts (REPLACED mock):**
- `useCashbox(filter)`: reads session role, delegates to `usePaymentsLedger(filter, role)`, computes `dailyTotals = computeDailyTotals(result.data.items)`
- No shift concept; no fake refund action; no mock path
- Re-exports `ApiError` from payments

**features/load/api.ts (REPLACED mock):**
- `useLoad(query)`: delegates to `useVisitsReport(query)`, transforms data with `fillHourlyBuckets + fillDailyBuckets`
- OWNER_ONLY gate inherited from `useVisitsReport`
- Re-exports `reportsQueryKeys as loadKeys`

### Task 2: DateRangePicker + rewire CashboxPage

**components/common/DateRangePicker.tsx (NEW):**
- Props: `{ from, to, onChange, className? }`
- Two native `<input type="date">` styled per UI-SPEC §3.1
- Validation on blur: inverted range → «Дата "По" должна быть позже даты "С"»; >365 days → «Максимальный период — 365 дней»
- `onChange` fires only when valid; inline error in `text-[12px] text-danger`
- Mobile stacks vertically; desktop side-by-side

**CashboxPage.tsx (REWRITTEN):**
- Split into `CashboxPage` (RBAC guard via `can(role,'view','payments')`) + `CashboxPageContent` (data hooks)
- Lock-EmptyState returned BEFORE any data hook fires (T-103-03-RBAC-DIRECT)
- Default range: last 30 days; filter state bound to DateRangePicker
- `useCashbox(filter)` → real ledger with `dailyTotals`
- Client-side KPI sums: Приход / Возвраты / Нетто
- `isFetching && !isPending` → section Skeleton; items.length === 0 → EmptyState
- `ShiftDrawer` removed entirely; `useModals` removed

**CashboxPageHead.tsx (REWRITTEN):**
- Removed `ShiftPill`, shift props; now takes `{ from, to, total, dateRangePicker }`
- Subtitle: `«{from} – {to} · {total} операций»`

**CashboxKpis.tsx (REWRITTEN):**
- Props: `{ prikhod, vozvrat, netto }` (kopecks integers)
- 3 KpiTile components: Приход/Возвраты/Нетто via `formatRub(kopecks/100)`
- Возвраты shown in text-danger when >0; Нетто in text-danger when negative

**TransactionsCard.tsx (REWRITTEN):**
- Props: `{ items: PaymentData[], dailyTotals: DailyTotal[] }`
- Refund rows: `Undo2` chip `bg-danger-soft text-danger`, title «Возврат», amount `text-danger` with «−» U+2212 prefix (READ-ONLY)
- Non-refund rows: subject-kind chip, «+» prefix
- Daily-total separator rows between date groups: `bg-surface-2` with `formatWeekdayLongRu` + `Итого: {signed formatRub}`
- «Оформить возврат» dropdown REMOVED (T-103-03-FAKEREFUND comment)

### Task 3: Rewire LoadPage to zero-filled visits aggregate

**LoadPage.tsx (REWRITTEN):**
- Split into `LoadPage` (RBAC guard `can(role,'view','reports')`) + `LoadPageContent` (data hooks)
- Lock-EmptyState before any hook fires (T-103-03-RBAC-DIRECT)
- Default range last 30 days; `useLoad(query)` with DateRangePicker
- `isFetching && !isPending` → section Skeleton (head+KPIs stay visible)
- `allZero` (totalVisits === 0) → EmptyState «Нет данных за этот период»
- `LiveNowCard`: NOT imported/rendered; TODO Phase 104 comment

**LoadPageHead.tsx (REWRITTEN):**
- Removed mock avg/peak props; now `{ from, to, dateRangePicker }`
- Period subtitle; DateRangePicker in actions

**LoadKpis.tsx (REWRITTEN):**
- Props: `{ averagePerDay, totalVisits }` — real data from /reports/visits response
- «Среднее в день» + «Всего визитов» KpiTile tiles

**LoadHeatmapCard.tsx (UPDATED):**
- Props changed: `{ hourly: VisitsReportHourlyBucket[], daily: VisitsReportDailyBucket[] }`
- Hourly 24 pts → IntensityHeatmap (one row, count→level 0-6 via max ratio)
- Daily → AreaTrendChart trend line (label=MM-DD, value=count, Y from 0)
- All-zero case handled upstream (EmptyState in LoadPage)

## Commits

| Hash | Description |
|------|-------------|
| d58247a9 | feat(103-03): nav gating correction + cashbox/load api wiring + computeDailyTotals (TDD) |
| 028d87f9 | feat(103-03): DateRangePicker + rewire CashboxPage (Lock guard + real ledger + refund rows) |
| b4fad3bc | feat(103-03): rewire LoadPage to zero-filled visits aggregate (Lock guard + no-NaN + ATT-02) |

## Verification Results

- `pnpm -F @clubcore/admin-app test -- src/features/cashbox/utils.test.ts` — 8 tests pass (signed daily totals, NaN guard)
- `pnpm -F @clubcore/admin-app typecheck` — exit 0
- `pnpm -F @clubcore/admin-app lint` — exit 0
- `pnpm -F @clubcore/admin-app test` — 311 tests across 23 files, all pass
- `pnpm -F @clubcore/admin-app build` — built in 2.63s, no errors
- nav-items.ts: `ownerResource: 'payments'` (Касса) ✓; `ownerResource: 'reports'` (Загруженность) ✓; Посещаемость ungated ✓
- CashboxPage + LoadPage: Lock-EmptyState before any data hook ✓
- No new dependency in apps/admin-app/package.json ✓

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] noUncheckedIndexedAccess TS errors in utils.test.ts**
- **Found during:** Task 1 typecheck
- **Issue:** `result[0]` produces `T | undefined` under `noUncheckedIndexedAccess: true`; TypeScript rejected direct index access in assertions
- **Fix:** Changed all indexed accesses in test file to `.at(0)` and `?.` optional chaining
- **Files modified:** `features/cashbox/utils.test.ts`
- **Commit:** d58247a9

**2. [Rule 3 - Blocking] Hook-in-condition pattern**
- **Found during:** Task 2 design review
- **Issue:** Naive implementation would call `useSession()` then `useCashbox()` after the `!can()` guard — but React Rules of Hooks prohibit conditional hook calls. Calling hooks after an early return based on hook data is valid, but calling the data hooks (useCashbox, useLoad) after the session check is only valid if the inner hooks are in a separate component.
- **Fix:** Split each page into an outer RBAC guard component (only `useSession()` called) and an inner content component (data hooks only called when guard passes). This is consistent with existing P101/P102 patterns.
- **Files modified:** `CashboxPage.tsx`, `LoadPage.tsx`
- **Commit:** 028d87f9, b4fad3bc

**3. [Rule 1 - Bug] IntensityHeatmap format mismatch**
- **Found during:** Task 3 — plan says "Feed data.hourly to IntensityHeatmap" but IntensityHeatmap expects `HeatRowData[]` (2D matrix), not `VisitsReportHourlyBucket[]`
- **Fix:** LoadHeatmapCard converts 24 hourly buckets into one `HeatRowData` row ("Часы") with cells mapped from count→level 0-6. This faithfully uses IntensityHeatmap and shows the hourly distribution per plan intent (ATT-02).
- **Decision:** D-103-03-LOAD-HEATMAP-SINGLE-ROW
- **Files modified:** `LoadHeatmapCard.tsx`
- **Commit:** b4fad3bc

## Known Stubs

None. All hooks wire to real endpoints. Lock-EmptyState ensures reception makes zero owner-only API calls.

## Threat Surface Scan

All T-103-03-* threat mitigations implemented:
- **T-103-03-RBAC-NAV**: nav-items.ts Касса+Загруженность get `ownerOnly:true` ✓
- **T-103-03-RBAC-DIRECT**: Lock-EmptyState before any hook in CashboxPage+LoadPage ✓
- **T-103-03-MONEY**: Signed integer kopecks; formatRub(kopecks/100); − U+2212; Math.abs display-only ✓
- **T-103-03-NONAN**: fillHourlyBuckets/fillDailyBuckets guarantee complete arrays; count 0 → level 0; all-zero → EmptyState ✓
- **T-103-03-FAKEREFUND**: «Оформить возврат» REMOVED — refund rows READ-ONLY ✓
- **T-103-SC**: No new packages added; date-fns-tz deliberately not used ✓

## Self-Check: PASSED

All key files exist on disk. All 3 task commits verified in git log.
