---
phase: 104-dashboard-reports-settings
reviewed: 2026-06-13T12:00:00Z
depth: standard
files_reviewed: 20
files_reviewed_list:
  - apps/admin-app/src/api/csv.ts
  - apps/admin-app/src/api/client.ts
  - apps/admin-app/src/features/audit/schemas.ts
  - apps/admin-app/src/features/audit/api.ts
  - apps/admin-app/src/features/reports/schemas.ts
  - apps/admin-app/src/features/reports/api.ts
  - apps/admin-app/src/features/reports/keys.ts
  - apps/admin-app/src/features/reports/utils.ts
  - apps/admin-app/src/features/dashboard/api.ts
  - apps/admin-app/src/features/settings/schemas.ts
  - apps/admin-app/src/features/settings/api.ts
  - apps/admin-app/src/features/users/schemas.ts
  - apps/admin-app/src/features/users/api.ts
  - apps/admin-app/src/pages/dashboard/DashboardPage.tsx
  - apps/admin-app/src/pages/dashboard/components/KpiStrip.tsx
  - apps/admin-app/src/pages/dashboard/components/OccupancyHours.tsx
  - apps/admin-app/src/pages/dashboard/components/ScheduleToday.tsx
  - apps/admin-app/src/pages/dashboard/components/ExpiringMemberships.tsx
  - apps/admin-app/src/pages/dashboard/components/RevenueChart.tsx
  - apps/admin-app/src/pages/dashboard/components/TopTrainers.tsx
  - apps/admin-app/src/pages/dashboard/components/PageHead.tsx
  - apps/admin-app/src/pages/reports/ReportsPage.tsx
  - apps/admin-app/src/pages/audit/AuditPage.tsx
  - apps/admin-app/src/pages/audit/components/AuditDetailModal.tsx
  - apps/admin-app/src/pages/audit/components/parts.tsx
  - apps/admin-app/src/pages/settings/SettingsPage.tsx
  - apps/admin-app/src/pages/settings/components/SectionsTop.tsx
  - apps/admin-app/src/pages/settings/components/SectionsBottom.tsx
  - apps/admin-app/src/layouts/AppLayout/nav-items.ts
findings:
  critical: 3
  warning: 5
  info: 4
  total: 12
status: issues_found
---

# Phase 104: Code Review Report

**Reviewed:** 2026-06-13T12:00:00Z
**Depth:** standard
**Files Reviewed:** 29
**Status:** issues_found

## Summary

Phase 104 implements Dashboard analytics, Reports (4-tab with CSV export), Audit log, and Settings/Users wiring. The architectural approach is largely sound: the two-component RBAC split (outer guard + inner content) is correctly applied in `ReportsPage` and `AuditPage`, CSV download is GET-based and CSRF-exempt, XSS in AuditDetailModal is correctly blocked with JSON.stringify into `<pre>`, and the 409-code mapping in users uses `err.code` (not message string-sniffing). However, there are three blockers: the owner-only hooks in `DashboardPage` mount unconditionally for all roles (contradicting the stated T-104-04 guarantee); the KpiStrip "Выручка сегодня" tile displays a 30-day aggregate while labelled as today's revenue; and `ExpiringMemberships` passes a UUID into the extend modal as `clientName`.

---

## Critical Issues

### CR-01: Owner-only hooks mount for ALL roles in DashboardPage (T-104-04 violated)

**File:** `apps/admin-app/src/pages/dashboard/DashboardPage.tsx:57-72`

**Issue:** The comment states "Owner-only hooks (only called when isOwner)" but `useRevenueReport`, `useVisitsReport`, `useClientsReport`, and `useTrainersReport` are called unconditionally at the top level of `DashboardPage` for both owner and reception. The `enabled: can(role, 'view', 'reports')` gate inside each hook suppresses the actual `fetch()`, but the hooks still mount and register observers in TanStack Query's cache for reception users. This contradicts the T-104-04 design goal ("reception fires ZERO owner-only API calls") stated in the architectural notes and the code comment itself.

The correct pattern used by `ReportsPage` and `AuditPage` is a two-component split: outer guard returns early before inner component (which calls hooks) mounts. `DashboardPage` does not use this pattern and uses a single-component design where all hooks fire regardless of role.

**Impact:** Currently, with `enabled: false`, no HTTP requests are fired. But the query observers are registered in the React tree for reception. Any future code change that removes or misorders the `enabled` guard will immediately leak owner-only data to reception. The design guarantee is not structurally enforced.

**Fix:** Apply the same outer-guard / inner-content split used in ReportsPage:

```tsx
export function DashboardPage() {
  const { data: me } = useSession();
  const role = me?.role ?? 'reception';
  const isOwner = can(role, 'view', 'reports');

  const today = mskTodayISO();

  // Both-role hooks always fire
  const scheduleTodayQ = useScheduleToday(today);
  const expiringQ = useExpiringMemberships();

  const scheduleItems = scheduleTodayQ.data?.items ?? [];
  const confirmedToday = scheduleItems.filter((b) => b.status === 'confirmed').length;
  const expiringItems = expiringQ.data?.items ?? [];

  return (
    <div ...>
      <PageHead fullName={me?.fullName} bookingsToday={confirmedToday} />

      {isOwner && (
        <DashboardOwnerSection
          role={role}
          today={today}
          scheduleItems={scheduleItems}
          scheduleTotal={scheduleTodayQ.data?.total ?? 0}
          schedulePending={scheduleTodayQ.isPending}
          scheduleError={scheduleTodayQ.isError}
          scheduleRefetch={() => void scheduleTodayQ.refetch()}
          expiringItems={expiringItems}
          expiringPending={expiringQ.isPending}
        />
      )}

      {!isOwner && (
        <>
          <ScheduleToday ... />
          <ExpiringMemberships ... />
        </>
      )}
    </div>
  );
}

// Inner component — only mounts when isOwner === true
function DashboardOwnerSection({ role, today, ... }) {
  const from30 = mskDaysAgoISO(29);
  const revenueQ = useRevenueReport({ fromDate: from30, toDate: today, groupBy: 'day' }, role);
  const visitsQ  = useVisitsReport({ fromDate: today, toDate: today }, role);
  const clientsQ = useClientsReport({ fromDate: from30, toDate: today, within: 7 }, role);
  const trainersQ = useTrainersReport({ fromDate: monthStart, toDate: today }, role);
  // ... render owner-only cards
}
```

---

### CR-02: KpiStrip "Выручка сегодня" displays 30-day aggregate, not today's revenue

**File:** `apps/admin-app/src/pages/dashboard/DashboardPage.tsx:88-91` and `apps/admin-app/src/pages/dashboard/components/KpiStrip.tsx:32`

**Issue:** `revenueQ` is fetched with `{ fromDate: from30, toDate: today, groupBy: 'day' }` — a 30-day range. The `netKopecks` passed to `KpiStrip` is the sum of all buckets over 30 days:

```tsx
netKopecks: revenueQ.data?.buckets.reduce(
  (s, b) => s + (b.netKopecks ?? 0),
  0,
),
```

`KpiStrip` then labels this `"Выручка сегодня"` (Revenue today). A user reading the dashboard will believe this tile shows today's revenue when it actually shows 30-day total revenue. This is incorrect data labelling that directly misleads business decisions.

`visitsToday` is correct (fetched with `{ fromDate: today, toDate: today }`, single day).

**Fix:** Either:
1. Change the label to `"Выручка за 30 дней"` in `KpiStrip.tsx:32`, or
2. Filter to today's bucket: `revenueQ.data?.buckets.find(b => b.period === today)?.netKopecks`.

The simpler fix that matches the tile's intent:
```tsx
// In DashboardPage — extract today's revenue bucket only
const todayBucket = revenueQ.data?.buckets.find((b) => b.period === today);
// Pass to KpiStrip:
netKopecks: todayBucket?.netKopecks,
```

---

### CR-03: ExpiringMemberships passes UUID as clientName to extend modal

**File:** `apps/admin-app/src/pages/dashboard/components/ExpiringMemberships.tsx:72-74`

**Issue:** The `MembershipData` wire shape (from `features/memberships/schemas.ts`) contains `clientId` (a UUID string) but no `clientFullName`. The extend modal is opened with:

```tsx
open('extend', {
  extend: { clientName: item.clientId },
})
```

This passes a UUID like `"3fa85f64-5717-4562-b3fc-2c963f66afa6"` as the `clientName` displayed to the user in the extend modal. The comment on line 45 acknowledges this: `// clientId is UUIDv4; show plan name as fallback` — but this awareness is only applied to `getInitials`, not to the modal call.

**Fix:** Use `item.planSnapshot.name` as the display name fallback until `clientFullName` is available on the membership wire shape, or use the plan name as context:

```tsx
open('extend', {
  extend: { clientName: item.planSnapshot.name },
})
```

Or, if the extend modal accepts a membership ID and resolves the client internally, pass `item.id` and update the modal signature accordingly.

---

## Warnings

### WR-01: `downloadCsv` anchor not appended to DOM before `.click()` — unreliable in Firefox

**File:** `apps/admin-app/src/api/csv.ts:33-36`

**Issue:** The created `<a>` element is never appended to `document.body` before `.click()` is called. Chromium-based browsers and Safari handle detached anchor clicks correctly, but Firefox historically required the anchor to be in the document for programmatic click downloads. The pattern is fragile across browser engines.

```ts
const a = document.createElement('a');
a.href = href;
a.download = filename;
a.click();           // anchor not in DOM — unreliable in Firefox
URL.revokeObjectURL(href);
```

**Fix:** Append and remove the anchor:

```ts
const a = document.createElement('a');
a.href = href;
a.download = filename;
a.style.display = 'none';
document.body.appendChild(a);
a.click();
document.body.removeChild(a);
URL.revokeObjectURL(href);
```

---

### WR-02: `AuditItemList` receives `fromDate` prop but immediately discards it (`void fromDate`)

**File:** `apps/admin-app/src/pages/audit/AuditPage.tsx:299-317`

**Issue:** `AuditItemList` declares a `fromDate: string` prop that is used nowhere. Line 317 explicitly discards it with `void fromDate`. This prop was presumably included for grouping date labels relative to "today" vs "yesterday" vs absolute dates, but the logic was never implemented. The dead prop pollutes the component API and will cause a `noUnusedParameters` TypeScript error if that compiler option is ever enforced here.

```ts
function AuditItemList({
  items,
  onOpenEvent,
  fromDate,       // never used — voided on line 317
}: { ... fromDate: string }) {
  ...
  void fromDate;  // intentional suppression — but prop should be removed
```

**Fix:** Remove the `fromDate` prop from both the component signature and the call site (`AuditPage.tsx:265`), or implement the intended "Today / Yesterday / date" grouping.

---

### WR-03: `OccupancyHours` uses local clock hour, not MSK hour

**File:** `apps/admin-app/src/pages/dashboard/components/OccupancyHours.tsx:19` and `94`

**Issue:** `getHourState` calls `new Date().getHours()` which returns the browser's local timezone hour. The domain is pinned to `Europe/Moscow` (MSK, UTC+3). An admin accessing the dashboard from a non-Moscow timezone will see the wrong bar highlighted as "now" and the wrong X-axis label bolded.

The same issue exists on line 94: `bar.hour === new Date().getHours()`.

**Fix:** Extract current MSK hour:

```ts
function getMskHour(): number {
  return parseInt(
    new Date().toLocaleString('en-US', { hour: 'numeric', hour12: false, timeZone: 'Europe/Moscow' }),
    10,
  );
}

function getHourState(hour: number): HourState {
  const nowHour = getMskHour();
  if (hour < nowHour) return 'past';
  if (hour === nowHour) return 'now';
  return 'future';
}
```

---

### WR-04: `DashboardPage` computes `monthStart` using local timezone, not MSK

**File:** `apps/admin-app/src/pages/dashboard/DashboardPage.tsx:47-49`

**Issue:** `monthStart` is calculated using `new Date(now.getFullYear(), now.getMonth(), 1)` which constructs a date at local midnight, then converts to `sv-SE` in Moscow timezone. For users UTC+4 or later, `new Date().getFullYear()` and `new Date().getMonth()` may return the previous month during the first hours of the 1st (since MSK may be the 1st but local time is still the last day). Conversely, for users west of MSK, the 1st in Moscow will not yet have arrived locally.

`mskTodayISO()` correctly uses `toLocaleDateString('sv-SE', { timeZone: 'Europe/Moscow' })`, but `monthStart` does not fully use this pattern.

**Fix:** Derive `monthStart` from the MSK-aware `today` string:

```tsx
const today = mskTodayISO(); // 'YYYY-MM-DD' in MSK
const monthStart = today.slice(0, 7) + '-01'; // 'YYYY-MM-01'
```

---

### WR-05: `hasFilter` in AuditPage excludes date range — wrong empty-state shown when only dates are filtered

**File:** `apps/admin-app/src/pages/audit/AuditPage.tsx:157`

**Issue:** The empty-state discriminator only checks `debouncedEmail`, `resourceType`, and `action`:

```ts
const hasFilter = Boolean(debouncedEmail || resourceType || action);
```

If a user narrows the date range to a period with no events but sets no other filters, `hasFilter` is `false` and the UI shows "Журнал пуст" (log is empty) instead of "Измените фильтры" (change your filters). This is misleading because the log is not actually empty — the date range filtered it.

**Fix:**

```ts
const hasFilter = Boolean(debouncedEmail || resourceType || action
  || fromDate !== initialFromDate || toDate !== initialToDate);
```

Or compare against the default range constants established at component initialization.

---

## Info

### IN-01: `features/settings/schemas.ts`, `features/settings/api.ts`, `features/users/schemas.ts`, `features/users/api.ts` omit semicolons

**File:** `apps/admin-app/src/features/settings/schemas.ts:9`, `apps/admin-app/src/features/settings/api.ts:18`, `apps/admin-app/src/features/users/schemas.ts` (multiple lines), `apps/admin-app/src/features/users/api.ts:22`

**Issue:** `apps/admin-app/.prettierrc` sets `"semi": true`. These four Phase 104 feature files use no-semicolon style (matching the main `frontend/` project CLAUDE.md style, not the admin-app style). All other Phase 104 files in `pages/` use semicolons correctly.

Example (`features/settings/schemas.ts:9`):
```ts
import { z } from 'zod'   // ← missing semicolon
```

**Fix:** Run `pnpm -F @clubcore/admin-app lint --fix` which will insert the semicolons via Prettier/ESLint.

---

### IN-02: Legacy `useReports` mock still exported from `features/reports/api.ts`

**File:** `apps/admin-app/src/features/reports/api.ts:46-51`

**Issue:** `useReports()` (the mock-based legacy hook) is still exported and the `reportsKeys.summary` cache key remains. The `@deprecated` tag notes Phase 104 will replace it, but Phase 104 is now done. The legacy hook keeps `reportsData` mock data imported and adds dead weight to the bundle. It also imports `reportsData` from `@/mocks/reports` unnecessarily.

**Fix:** After confirming `ReportsPage.tsx` no longer calls `useReports()` (confirmed — it does not), remove the legacy `useReports` export, the `reportsKeys` const, and the `reportsData` import from `features/reports/api.ts`.

---

### IN-03: `TrainerRow` name conflict in ReportsPage — imported type shadows local component

**File:** `apps/admin-app/src/pages/reports/ReportsPage.tsx:44` and `510`

**Issue:** `TrainerRow` is both an imported type (from `@/features/reports/schemas`) and a local function component defined at line 510. TypeScript resolves this as the component overriding the type in value space, and the imported `TrainerRow` type is used in inline prop types. The naming collision is confusing and triggers `noUnusedLocals` if the imported type is considered shadowed.

```ts
import type { TrainerRow, ... } from '@/features/reports/schemas'; // line 44
// ...
function TrainerRow({ row, first, maxRevenue }: ...) { ... }       // line 510
```

**Fix:** Rename the local component to `TrainerRowItem` (matches the naming used in `TopTrainers.tsx`) or `ReportsTrainerRow`:

```tsx
function ReportsTrainerRow({ row, first, maxRevenue }: { row: TrainerRow; ... }) { ... }
// and update the usage at line 504:
{rows.map((row, i) => (
  <ReportsTrainerRow key={row.trainerId} row={row} first={i === 0} maxRevenue={maxRevenue} />
))}
```

---

### IN-04: `monthStart` recalculated on every render in DashboardPage

**File:** `apps/admin-app/src/pages/dashboard/DashboardPage.tsx:47-50`

**Issue:** `today`, `from30`, `now`, `monthStart`, and `monthName` are all computed on every render of `DashboardPage`. While inexpensive, `today` and `monthStart` feed into query keys — if a render happens across midnight, these values change and trigger a refetch. This is minor but worth noting.

**Fix:** Wrap in `useMemo` with an empty or date-stable dependency if consistent query keys across renders are desired:

```tsx
const today = useMemo(() => mskTodayISO(), []);
const from30 = useMemo(() => mskDaysAgoISO(29), []);
```

---

_Reviewed: 2026-06-13T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
