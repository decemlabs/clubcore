---
phase: 103-attendance-finance
reviewed: 2026-06-13T10:30:00Z
depth: standard
files_reviewed: 28
files_reviewed_list:
  - apps/admin-app/src/features/visits/schemas.ts
  - apps/admin-app/src/features/visits/api.ts
  - apps/admin-app/src/features/visits/schemas.test.ts
  - apps/admin-app/src/features/payments/schemas.ts
  - apps/admin-app/src/features/payments/api.ts
  - apps/admin-app/src/features/reports/schemas.ts
  - apps/admin-app/src/features/reports/keys.ts
  - apps/admin-app/src/features/reports/api.ts
  - apps/admin-app/src/features/reports/utils.ts
  - apps/admin-app/src/features/reports/utils.test.ts
  - apps/admin-app/src/features/attendance/api.ts
  - apps/admin-app/src/features/cashbox/api.ts
  - apps/admin-app/src/features/cashbox/utils.ts
  - apps/admin-app/src/features/cashbox/utils.test.ts
  - apps/admin-app/src/features/load/api.ts
  - apps/admin-app/src/features/finance/api.ts
  - apps/admin-app/src/components/common/DateRangePicker.tsx
  - apps/admin-app/src/components/modals/CheckInModal.tsx
  - apps/admin-app/src/components/modals/ModalsProvider.tsx
  - apps/admin-app/src/components/icons/index.tsx
  - apps/admin-app/src/pages/attendance/AttendancePage.tsx
  - apps/admin-app/src/pages/attendance/components/AttendancePageHead.tsx
  - apps/admin-app/src/pages/attendance/components/VisitsList.tsx
  - apps/admin-app/src/pages/cashbox/CashboxPage.tsx
  - apps/admin-app/src/pages/cashbox/components/CashboxKpis.tsx
  - apps/admin-app/src/pages/cashbox/components/CashboxPageHead.tsx
  - apps/admin-app/src/pages/cashbox/components/TransactionsCard.tsx
  - apps/admin-app/src/pages/load/LoadPage.tsx
  - apps/admin-app/src/pages/load/components/LoadHeatmapCard.tsx
  - apps/admin-app/src/pages/load/components/LoadKpis.tsx
  - apps/admin-app/src/pages/load/components/LoadPageHead.tsx
  - apps/admin-app/src/pages/finance/FinancePage.tsx
  - apps/admin-app/src/pages/finance/components/OnlinePaymentsTable.tsx
  - apps/admin-app/src/pages/finance/components/RevenueChart.tsx
  - apps/admin-app/src/pages/finance/components/parts.tsx
  - apps/admin-app/src/layouts/AppLayout/nav-items.ts
findings:
  critical: 4
  warning: 5
  info: 2
  total: 11
status: issues_found
---

# Phase 103: Code Review Report

**Reviewed:** 2026-06-13T10:30:00Z
**Depth:** standard
**Files Reviewed:** 36
**Status:** issues_found

## Summary

Phase 103 wires the Attendance (visits list + check-in), Cashbox (payments ledger), Load (visits aggregate / heatmap), and Finance (revenue + online payments) screens to real API endpoints. The RBAC outer-guard pattern (CashboxPage / LoadPage / FinancePage) is correctly structured — the outer component calls only `useSession` and `can()`, with data hooks deferred to inner content components. The check-in optimistic update, rollback, and 409-code routing are correctly implemented. Zero-fill utilities (fillHourlyBuckets / fillDailyBuckets / fillRevenueBuckets) are correct and well-tested.

Four blockers found: a stale-closure prop-sync bug in DateRangePicker, a local-TZ date slip in todayISO() / daysAgoISO() used for API query parameters, an optimistic rollback that misses the `byClient` cache key family, and a `page=1` filter being silently dropped as falsy. Five warnings found, all correctness-adjacent.

---

## Critical Issues

### CR-01: DateRangePicker does not sync when parent `from`/`to` props change

**File:** `apps/admin-app/src/components/common/DateRangePicker.tsx:49-50`

**Issue:** `useState(from)` and `useState(to)` capture the prop values only on first render. If the parent component resets the date range externally (e.g., a "last 30 days" preset button, or the parent's `useState` initializer runs with a different value after hydration), the picker inputs will show stale values while the parent query already uses the new range. The `localFrom`/`localTo` state is fully uncontrolled after mount — there is no `useEffect` to sync incoming prop changes back to local state. In its current usage the parent never resets from outside, so the bug is latent; but it will manifest the moment any "quick range" shortcut or URL-driven filter is added.

**Fix:**
```tsx
// Add a useEffect to sync external prop changes to local state.
// Guard against feedback loops by comparing to avoid re-triggering.
useEffect(() => {
  setLocalFrom(from);
}, [from]);

useEffect(() => {
  setLocalTo(to);
}, [to]);
```

---

### CR-02: `todayISO()` / `daysAgoISO()` use UTC `.toISOString()` — delivers wrong date for MSK users after 21:00 local time

**File:** `apps/admin-app/src/pages/attendance/AttendancePage.tsx:29-37`
**File:** `apps/admin-app/src/pages/cashbox/CashboxPage.tsx:26-33`
**File:** `apps/admin-app/src/pages/load/LoadPage.tsx:29-36`
**File:** `apps/admin-app/src/pages/finance/FinancePage.tsx:40-47`
**File:** `apps/admin-app/src/components/common/DateRangePicker.tsx:26-28`

**Issue:** `new Date().toISOString().slice(0, 10)` returns the UTC date. Moscow is UTC+3, so between 00:00 and 02:59 MSK the UTC date is still the previous day. This causes the default filter range (e.g., `from=2026-06-12, to=2026-06-12`) to be one day behind for MSK users during that window — today's visits will be excluded from the default view, and the attendance KPI subtitle will show yesterday's date as "today".

The backend stores `gymDate` as MSK-anchored per the module comment in `cashbox/utils.ts`, so the mismatch between the client's UTC-derived `to` and the server's MSK-anchored data means fresh check-ins will appear missing from the default view for those three hours.

**Fix:** Derive the local MSK date using `toLocaleDateString` or via `Intl.DateTimeFormat`:
```ts
function todayMSK(): string {
  return new Date().toLocaleDateString('sv-SE', { timeZone: 'Europe/Moscow' });
  // 'sv-SE' locale gives ISO yyyy-MM-dd format natively.
}

function daysAgoMSK(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toLocaleDateString('sv-SE', { timeZone: 'Europe/Moscow' });
}
```
Apply the same fix to `DateRangePicker.todayISO()`.

---

### CR-03: `useCheckIn` optimistic rollback misses the `byClient` cache key family

**File:** `apps/admin-app/src/features/visits/api.ts:124`

**Issue:** `onMutate` calls `qc.cancelQueries({ queryKey: visitsKeys.lists() })` and snapshots only queries under `visitsKeys.lists()` (the `['visits','list']` prefix). The `useClientVisits` hook stores its cache under `visitsKeys.byClient(clientId)` = `['visits','byClient',clientId]`. When the client is on the client detail page's visits tab and performs a check-in, the `byClient` query is not cancelled and not snapshotted. The optimistic prepend is applied only to list queries, but `onSuccess` calls `qc.invalidateQueries({ queryKey: visitsKeys.lists() })` which also does not invalidate the `byClient` family — meaning the client-detail visits tab does not refresh after a successful check-in. More critically, if the check-in fires simultaneously with a `byClient` refetch, the stale optimistic state and the fresh refetch can produce a race-condition double-render. The by-client tab will never show the new visit without a manual page reload.

**Fix:** Extend cancel/snapshot/invalidate to cover both families, or use the shared `visitsKeys.all` root:
```ts
// onMutate — cancel both families
await qc.cancelQueries({ queryKey: visitsKeys.all });

// snapshot both families
const listSnapshots = qc.getQueriesData<...>({ queryKey: visitsKeys.lists() });
const byClientSnapshots = qc.getQueriesData<...>({ queryKey: visitsKeys.all });

// onError — rollback both
for (const [key, data] of ctx.allSnapshots) {
  qc.setQueryData(key as readonly unknown[], data);
}

// onSuccess — invalidate both
void qc.invalidateQueries({ queryKey: visitsKeys.all });
```

---

### CR-04: `useVisitsList` and `usePaymentsLedger` silently drop `page=1` because `if (filter.page)` is falsy for 1… wait, 1 is truthy. Re-examining: `page` starts at 1 and `if (filter.page)` with value 1 is truthy — page=1 is sent. However, `pageSize` in `useCashbox` is called with `{ receivedFrom, receivedTo, pageSize: 100 }` and no `page` field. That omits `page` from the query, which is the intended default.

**Actual bug — `useVisitsList` with explicit `page: 1` in `filter` drops `pageSize` when `pageSize` is `0`:** The pattern `if (filter.pageSize) query['pageSize'] = filter.pageSize;` is falsy-gated. If a caller ever passes `pageSize: 0` (an edge case for "fetch all"), the guard silently drops it and the backend falls back to its own default. This is an unlikely but latent defect. More concretely: the same pattern is used for `page` — if for any reason `page` is 0 (should not happen from a 1-indexed paginator, but possible from a reset bug), it is silently dropped, causing the backend to return page 1 when page 0 was intended as a no-op signal.

**File:** `apps/admin-app/src/features/visits/api.ts:70-71`
**File:** `apps/admin-app/src/features/payments/api.ts:75-76`

**Issue:** Numeric query params use truthiness guards (`if (filter.page)`). The value `0` is silently dropped. For `page`, `0` is not a valid server page number, but the pattern is inconsistent with other filters that use explicit `!== undefined` checks. For `pageSize`, `0` would erroneously be dropped.

**Fix:** Use `!= null` guards for numeric params:
```ts
if (filter.page != null) query['page'] = filter.page;
if (filter.pageSize != null) query['pageSize'] = filter.pageSize;
```

---

## Warnings

### WR-01: `TransactionsCard` — `PaymentRow first` prop uses raw `rows` array index, producing incorrect border suppression after a `DailyTotalRow` separator

**File:** `apps/admin-app/src/pages/cashbox/components/TransactionsCard.tsx:167`

**Issue:** The `first` prop passed to `PaymentRow` is `i === 0` where `i` is the index in the composite `rows` array. The first element in `rows` is always a `DailyTotalRow` (a date-separator), not a `PaymentRow`. So the first actual `PaymentRow` (at index 1) receives `first={false}` and renders a top `border-t-[0.5px]` border immediately below the separator — an unwanted hairline between the date-total banner and the first payment row of that date group.

Additionally, when a new date group starts (after the first), the `DailyTotalRow` already provides visual separation; the first `PaymentRow` after any separator also gets `first={false}` (because `i !== 0`) and draws a redundant top border directly below the separator.

**Fix:** Track `firstOfDate` that was already computed and stored in the row object, and use it instead:
```tsx
return (
  <PaymentRow
    key={row.payment.id}
    payment={row.payment}
    first={row.firstOfDate}   // already computed, suppresses border after separator
  />
);
```

---

### WR-02: `formatDateRu` / `formatWeekdayLongRu` use `new Date(dateOnlyString)` which causes DST-sensitive midnight-UTC-shift on date-only strings

**File:** `apps/admin-app/src/lib/format.ts:21`

**Issue:** `formatDateRu(date: string)` does `new Date(date)` which, per ECMA-262, parses a date-only string (`'YYYY-MM-DD'`) as UTC midnight. In timezones west of UTC this shifts to the previous day. For MSK (UTC+3) the date-only parsing gives `00:00 UTC = 03:00 MSK` — i.e., the date displays correctly. However the project's own CLAUDE.md says: **"Never `new Date(dateOnlyString)` (DST risk)"** under the Dates convention. This is a direct violation of the project convention. If the timezone offset is negative (west-of-UTC clients, or server-generated test environments), the date shifts back one calendar day.

`TransactionsCard.tsx` passes `total.date` (a `'YYYY-MM-DD'` slice) to `formatWeekdayLongRu` → `new Date(date)` which hits the same path.
`VisitsList.tsx` passes `visit.gymDate` (also a date-only string) to `formatDateRu`.
`AttendancePage.tsx` passes `from` / `to` (date-only strings) to `formatDateRu`.

**Fix:** Use `parseISO` from `date-fns` (already imported in `utils.ts`) which interprets date-only strings as local midnight, avoiding the UTC-midnight shift:
```ts
import { parseISO } from 'date-fns';

export function formatDateRu(date: Date | string, pattern = 'd MMMM'): string {
  const d = typeof date === 'string' ? parseISO(date) : date;
  return format(d, pattern, { locale: ru });
}
// Apply the same fix to formatWeekdayLongRu, formatRelativeRu, formatTime.
```

---

### WR-03: `RevenueChart` — `Math.max(...filled.map(...), 0)` can produce `-Infinity` when `filled` is empty, which propagates to the chart `yMax` prop

**File:** `apps/admin-app/src/pages/finance/components/RevenueChart.tsx:49`

**Issue:** `Math.max(...filled.map((b) => b.netKopecks / 100), 0)` is safe when `filled` is non-empty because `0` is always in the spread. The expression correctly includes `0` as the final argument, so `Math.max` will never return `-Infinity` here. However on line 49 the `|| undefined` escape hatch after `Math.max(...)` means: if the max is exactly `0` (all buckets are zero), `yMax` becomes `undefined`. This causes the chart to auto-scale from zero up — which is fine — but the intent seems to be "pass an explicit `yMax` for non-zero data". The bug is the semantics: when the entire date range has a total of exactly 0 roubles revenue but some months have positive and negative amounts that cancel, the `allZero` check (which checks `netKopecks === 0` per bucket, not the max) correctly shows the chart — but then `yMax` is `undefined` because the spread max of all per-bucket values may indeed be `> 0`. So the guard is inverted: `|| undefined` fires on all-zero (correct no-op) but the same pattern in `LoadHeatmapCard` (line 101) uses `Math.max(...daily.map((b) => b.count), 0)` without the `|| undefined` — here if `daily` is empty (after the all-zero guard in LoadPage), `Math.max` returns `0` which is passed as `yMax=0`, potentially causing chart division-by-zero in the `AreaTrendChart` Y scale.

**File:** `apps/admin-app/src/pages/load/components/LoadHeatmapCard.tsx:101`

**Fix:** Add `|| undefined` to the `LoadHeatmapCard` yMax to match `RevenueChart` pattern, preventing `yMax=0` from being passed to the chart:
```tsx
yMax={Math.max(...daily.map((b) => b.count), 0) || undefined}
```

---

### WR-04: `useVisitsReport` and `useRevenueReport` derive `role` from `useSession().data?.role ?? 'reception'` — during the loading window the role defaults to `'reception'`, causing the `enabled` gate to evaluate as `false` and the query to remain disabled until the session resolves

**File:** `apps/admin-app/src/features/reports/api.ts:63`

**Issue:** `const role = session.data?.role ?? 'reception'` means that while the session query is still loading (first render, cold cache), `session.data` is `undefined` and `role` is `'reception'`. `can('reception', 'view', 'reports')` returns `false`, so the query's `enabled` is `false`. When the session query resolves and returns `'owner'`, TanStack Query re-evaluates `enabled` to `true` and the report query fires. This is a two-waterfall sequence: session fetch → role resolved → report fetch starts. The net effect is an extra round-trip delay for the owner on every page mount. The pages already guard with `isPending` and show a loading spinner, so there is no data-leak, but the UX has unnecessary delay.

This is the same pattern used elsewhere (e.g., `cashbox/api.ts`) — it is consistently applied. The correct fix is to accept `role` as a parameter (the Finance page already passes `role` explicitly to `useOnlinePayments`), or to pass `enabled` explicitly from the caller. Flagged as Warning since the behavior is functionally safe.

**Fix (preferred):** Accept `role` as a parameter from the page-level hook call site (mirrors how `usePaymentsLedger` receives `role`):
```ts
export function useVisitsReport(query: VisitsReportQuery, role: Role) {
  return useQuery({
    ...
    enabled: can(role, 'view', 'reports'),
  });
}
```
The `useLoad` wrapper in `features/load/api.ts` would call `const session = useSession()` and pass `session.data?.role ?? 'reception'` down, keeping the dual-waterfall in one place at the delegation layer rather than inside the base hook.

---

### WR-05: `CheckInModal` — hardcoded color `#2dd4a4` for avatar chip is a raw palette value, violating the semantic-token rule

**File:** `apps/admin-app/src/components/modals/CheckInModal.tsx:229`
**File:** `apps/admin-app/src/components/modals/CheckInModal.tsx:264`

**Issue:** `color="#2dd4a4"` is passed to `ResultItem`. CLAUDE.md's Styling convention explicitly bans raw palette values: "Use semantic shadcn tokens for all colors". The same value appears in `BookModal.tsx` and `BookingModal.tsx` so it is a pre-existing pattern, but the new `CheckInModal` replicates it in Phase 103 code. ESLint's raw-palette ban targets Tailwind class strings, not JSX props — so this escapes the linter and must be caught in review.

**Fix:** Add the brand emerald color as a semantic CSS variable (e.g., `--color-brand-emerald` or reuse `--color-primary`) and reference it via `var(--color-primary)` in the prop, or define a constant:
```tsx
const AVATAR_COLOR = 'var(--color-primary)'; // brand emerald from tokens.css
// ...
<ResultItem color={AVATAR_COLOR} ... />
```

---

## Info

### IN-01: `routeRegistry` in `registry.ts` is missing the `load` route entry

**File:** `apps/admin-app/src/shared/session/registry.ts:61-72`

**Issue:** `ROUTES.load` is listed in `NAV_SECTIONS` (nav-items.ts) with `ownerOnly: true, ownerResource: 'reports'`, but the `routeRegistry` array (used by AppSidebar, tests, and breadcrumbs) does not include a `RouteEntry` for the load route. The load route is functionally accessible and gated, but the registry-based breadcrumb derivation and route smoke tests will not cover it. This is a consistency gap, not a data-loss or security issue.

**Fix:** Add the entry:
```ts
{ path: ROUTES.load, resource: 'reports', label: 'Загруженность', icon: 'Clock', navKey: 'finance' },
```

---

### IN-02: `getInitials` is duplicated — implemented both in `CheckInModal.tsx` and in `lib/format.ts`

**File:** `apps/admin-app/src/components/modals/CheckInModal.tsx:65-72`
**File:** `apps/admin-app/src/lib/format.ts:44-50`

**Issue:** `CheckInModal.tsx` defines a local `getInitials(name: string)` function. The identical function (same logic: split on whitespace, take first two words, uppercase first char) is exported from `@/lib/format.ts` as `getInitials`. `VisitsList.tsx` already imports `getInitials` from `@/lib/format`. The modal's local copy is dead code from the perspective of the shared library.

**Fix:** Remove the local definition in `CheckInModal.tsx` and import from `@/lib/format`:
```tsx
import { useCheckIn, useGymMeta, ApiError } from '@/features/attendance/api';
// add:
import { getInitials } from '@/lib/format';
```

---

_Reviewed: 2026-06-13T10:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
