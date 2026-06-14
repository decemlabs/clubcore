# Phase 103: Attendance + Finance — Pattern Map

**Mapped:** 2026-06-13
**Files analyzed:** 12 new/modified files
**Analogs found:** 12 / 12

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `features/visits/schemas.ts` (EXTEND) | model | request-response | `features/payments/schemas.ts` | exact |
| `features/visits/api.ts` (EXTEND) | service | CRUD + mutation-optimistic | `features/bookings/api.ts` + `features/memberships/api.ts` | exact |
| `features/payments/schemas.ts` (EXTEND) | model | request-response | `features/visits/schemas.ts` | exact |
| `features/payments/api.ts` (EXTEND) | service | CRUD | `features/visits/api.ts` | exact |
| `features/reports/schemas.ts` (NEW) | model | request-response | `features/visits/schemas.ts` | role-match |
| `features/reports/keys.ts` (NEW) | utility | — | `features/memberships/keys.ts` | exact |
| `features/reports/api.ts` (REPLACE) | service | request-response | `features/payroll/api.ts` (owner-gated query) | exact |
| `features/attendance/api.ts` (REPLACE) | service | request-response | `features/visits/api.ts` | exact |
| `features/load/api.ts` (REPLACE) | service | request-response + transform | `features/reports/api.ts` (new) | role-match |
| `features/cashbox/api.ts` (REPLACE) | service | request-response + transform | `features/payments/api.ts` (extended) | role-match |
| `features/finance/api.ts` (REPLACE) | service | request-response | `features/reports/api.ts` (new) | role-match |
| `layouts/AppLayout/nav-items.ts` (EXTEND) | config | — | itself | self-extend |

---

## Pattern Assignments

### `features/visits/schemas.ts` (EXTEND — add list query schema + check-in input)

**Analog:** `apps/admin-app/src/features/visits/schemas.ts` (current file) + `features/payments/schemas.ts`

**Current file (lines 1–41):** keep as-is; append below.

**Additions to append:**

```typescript
// ---------------------------------------------------------------------------
// Paginated list query params (GET /api/v1/visits)
// ---------------------------------------------------------------------------

export const VisitsListQuerySchema = z.object({
  from: z.string().optional(),
  to: z.string().optional(),
  clientId: z.string().optional(),
  page: z.number().optional(),
  pageSize: z.number().optional(),
});
export type VisitsListQuery = z.infer<typeof VisitsListQuerySchema>;

// ---------------------------------------------------------------------------
// Gym meta (GET /api/v1/visits/_meta) — cacheable
// ---------------------------------------------------------------------------

export const GymMetaSchema = z.object({
  data: z.object({
    gymHoursStart: z.string(),  // e.g. "07:00"
    gymHoursEnd: z.string(),    // e.g. "23:00"
  }),
});
export type GymMetaData = z.infer<typeof GymMetaSchema>['data'];

// ---------------------------------------------------------------------------
// Check-in input (POST /api/v1/visits)
// ---------------------------------------------------------------------------

export const CheckInInputSchema = z.object({
  clientId: z.string().min(1, 'Клиент обязателен'),
});
export type CheckInInput = z.infer<typeof CheckInInputSchema>;
```

---

### `features/visits/api.ts` (EXTEND — add list hook, gym-meta hook, check-in mutation)

**Analogs:**
- List hook pattern: `apps/admin-app/src/features/visits/api.ts` lines 34–46 (current `useClientVisits`)
- Optimistic mutation pattern: `apps/admin-app/src/features/memberships/api.ts` lines 120–186 (`useFreezeMembership` — onMutate/cancelQueries/snapshot/setQueryData/onError rollback/onSettled invalidate)
- 409 multi-code error handling: `apps/admin-app/src/features/bookings/api.ts` lines 122–141 (`useCreateBooking` — caller catches ApiError.code inline; hook does NOT toast 409s)

**Key factory extension** (append to `visitsKeys` object in lines 21–24):

```typescript
export const visitsKeys = {
  all: ['visits'] as const,
  byClient: (clientId: string) => [...visitsKeys.all, 'byClient', clientId] as const,
  // NEW Phase 103
  lists: () => [...visitsKeys.all, 'list'] as const,
  list: (filter: VisitsListQuery) => [...visitsKeys.lists(), filter] as const,
  meta: () => [...visitsKeys.all, '_meta'] as const,
};
```

**Paginated list hook pattern** (copy from `useClientVisits`, extend query params):

```typescript
export function useVisitsList(filter: VisitsListQuery) {
  return useQuery({
    queryKey: visitsKeys.list(filter),
    queryFn: async () => {
      const query: Record<string, string | number> = {};
      if (filter.from) query['from'] = filter.from;
      if (filter.to) query['to'] = filter.to;
      if (filter.clientId) query['clientId'] = filter.clientId;
      if (filter.page) query['page'] = filter.page;
      if (filter.pageSize) query['pageSize'] = filter.pageSize;
      const raw = await staffRequest('get', '/api/v1/visits', { query });
      return VisitsListResponseSchema.parse(raw).data;
    },
    staleTime: 30_000,
  });
}
```

**Gym meta hook** (cacheable, long staleTime):

```typescript
export function useGymMeta() {
  return useQuery({
    queryKey: visitsKeys.meta(),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/visits/_meta');
      return GymMetaSchema.parse(raw).data;
    },
    staleTime: 5 * 60_000, // 5 min — gym hours rarely change
  });
}
```

**Check-in mutation pattern** — optimistic prepend + 3-code 409 handling.
Analog for optimistic: `features/memberships/api.ts` lines 129–186 (onMutate snapshot + setQueryData + onError rollback).
Analog for 409 caller-handles: `features/bookings/api.ts` lines 122–141 (hook does NOT toast 409 — caller shows Callout).

```typescript
type CheckInVars = { clientId: string; clientName: string; currentUserId: string };
type CheckInCtx = {
  listSnapshots: [readonly unknown[], { items: VisitData[]; total: number; page: number; pageSize: number } | undefined][];
};

export function useCheckIn() {
  const qc = useQueryClient();
  return useMutation<VisitData, Error, CheckInVars, CheckInCtx>({
    mutationFn: async ({ clientId }: CheckInVars) => {
      const raw = await staffRequest('post', '/api/v1/visits', { body: { clientId } });
      return VisitSchema.parse((raw as { data: unknown }).data);
    },
    onMutate: async ({ clientId, clientName, currentUserId }: CheckInVars) => {
      await qc.cancelQueries({ queryKey: visitsKeys.lists() });
      const listSnapshots = qc.getQueriesData<{ items: VisitData[]; total: number; page: number; pageSize: number }>({
        queryKey: visitsKeys.lists(),
      });
      const optimisticRow: VisitData = {
        id: `optimistic-${crypto.randomUUID()}`,
        clientId,
        membershipId: '',
        checkedInAt: new Date().toISOString(),
        gymDate: new Date().toISOString().slice(0, 10),
        channel: 'reception',
        checkedInBy: currentUserId,
        createdAt: new Date().toISOString(),
        // UI-only flag for opacity-60 + Loader2 spinner treatment
        _optimistic: true,
      } as VisitData & { _optimistic: boolean };
      // Prepend optimistic row to each cached list
      for (const [key, data] of listSnapshots) {
        if (!data) continue;
        qc.setQueryData(key, { ...data, items: [optimisticRow, ...data.items] });
      }
      return { listSnapshots };
    },
    onSuccess: (_data, { clientName }, _ctx) => {
      // Caller shows toast.success and closes modal
      void qc.invalidateQueries({ queryKey: visitsKeys.lists() });
      // 'Визит зафиксирован' + clientName toast shown by caller (CheckInModal)
    },
    onError: (_err, _vars, ctx) => {
      // Rollback optimistic rows (pattern from memberships freeze/unfreeze)
      if (ctx) {
        for (const [key, data] of ctx.listSnapshots) {
          qc.setQueryData(key as readonly unknown[], data);
        }
      }
      // 409 code routing is handled by CheckInModal (catch ApiError.code)
      // Pattern: bookings/api.ts useCreateBooking — hook does NOT toast 409
    },
    // onSettled: caller invalidates in onSuccess — no separate onSettled needed
  });
}
```

---

### `features/payments/schemas.ts` (EXTEND — add global ledger list schema)

**Analog:** `apps/admin-app/src/features/payments/schemas.ts` lines 1–46 (existing file)

Keep existing `PaymentSchema` and `PaymentsListResponseSchema` as-is. Append:

```typescript
// ---------------------------------------------------------------------------
// Global ledger query params (GET /api/v1/payments — OWNER_ONLY)
// ---------------------------------------------------------------------------

export const PaymentsLedgerQuerySchema = z.object({
  receivedFrom: z.string().optional(),
  receivedTo: z.string().optional(),
  method: z.enum(['cash', 'online']).optional(),
  page: z.number().optional(),
  pageSize: z.number().optional(),
});
export type PaymentsLedgerQuery = z.infer<typeof PaymentsLedgerQuerySchema>;

// ---------------------------------------------------------------------------
// Client-side computed daily total
// ---------------------------------------------------------------------------

export type DailyTotal = {
  date: string;           // ISO date string 'YYYY-MM-DD' (MSK)
  totalKopecks: number;   // signed sum (refunds subtract)
};
```

---

### `features/payments/api.ts` (EXTEND — add global ledger hook)

**Analog:** `apps/admin-app/src/features/payments/api.ts` lines 25–60 (existing) + `features/payroll/api.ts` lines 41–57 (owner-gated enabled pattern)

Extend `paymentsKeys`:

```typescript
export const paymentsKeys = {
  all: ['payments'] as const,
  byClient: (clientId: string) => [...paymentsKeys.all, 'byClient', clientId] as const,
  // NEW Phase 103
  lists: () => [...paymentsKeys.all, 'list'] as const,
  list: (filter: PaymentsLedgerQuery) => [...paymentsKeys.lists(), filter] as const,
};
```

Add global ledger hook (owner-gated via `enabled: can(role, 'view', 'payments')`):

```typescript
/**
 * Global payments ledger (GET /api/v1/payments — OWNER_ONLY).
 * Enabled only for owner role (can(role,'view','payments') per OWNER_ONLY matrix).
 * Returns PaymentsListResponse; caller computes daily totals client-side.
 */
export function usePaymentsLedger(filter: PaymentsLedgerQuery, role: Role) {
  return useQuery({
    queryKey: paymentsKeys.list(filter),
    queryFn: async () => {
      const query: Record<string, string | number> = {};
      if (filter.receivedFrom) query['receivedFrom'] = filter.receivedFrom;
      if (filter.receivedTo) query['receivedTo'] = filter.receivedTo;
      if (filter.method) query['method'] = filter.method;
      if (filter.page) query['page'] = filter.page;
      if (filter.pageSize) query['pageSize'] = filter.pageSize;
      const raw = await staffRequest('get', '/api/v1/payments', { query });
      return PaymentsListResponseSchema.parse(raw).data;
    },
    enabled: can(role, 'view', 'payments'), // OWNER_ONLY — reception makes zero API calls
    staleTime: 30_000,
  });
}
```

---

### `features/reports/schemas.ts` (NEW file)

**Analog:** `apps/admin-app/src/features/visits/schemas.ts` (same Zod structure pattern) + `features/payments/schemas.ts` (sparse-data shape)

```typescript
/**
 * Reports domain Zod contract layer (Phase 103).
 *
 * Two report endpoints:
 *   GET /api/v1/reports/visits  → VisitsReportSchema (sparse hourly/daily buckets)
 *   GET /api/v1/reports/revenue → RevenueReportSchema (sparse period buckets, signed kopecks)
 *
 * Both are OWNER_ONLY (VIEW REPORTS). Buckets are SPARSE — client-side zero-fill required.
 * Wire shape: camelCase via Pydantic to_camel alias.
 */
import { z } from 'zod';

// ---------------------------------------------------------------------------
// Visits report (GET /api/v1/reports/visits)
// ---------------------------------------------------------------------------

export const VisitsReportDailyBucketSchema = z.object({
  date: z.string(),   // 'YYYY-MM-DD'
  count: z.number(),
});

export const VisitsReportHourlyBucketSchema = z.object({
  hour: z.number(),   // 0–23
  count: z.number(),
});

export const VisitsReportSchema = z.object({
  data: z.object({
    daily: z.array(VisitsReportDailyBucketSchema),
    hourly: z.array(VisitsReportHourlyBucketSchema),
    averagePerDay: z.number(),
    fromDate: z.string(),
    toDate: z.string(),
  }),
});
export type VisitsReportData = z.infer<typeof VisitsReportSchema>['data'];
export type VisitsReportDailyBucket = z.infer<typeof VisitsReportDailyBucketSchema>;
export type VisitsReportHourlyBucket = z.infer<typeof VisitsReportHourlyBucketSchema>;

// ---------------------------------------------------------------------------
// Revenue report (GET /api/v1/reports/revenue)
// ---------------------------------------------------------------------------

export const RevenueBucketSchema = z.object({
  period: z.string(),         // 'YYYY-MM-DD' (day) or 'YYYY-MM' (month)
  netKopecks: z.number(),     // signed — refunds make it negative
  byMethod: z.object({
    cash: z.number(),
    online: z.number(),
  }),
  bySubjectKind: z.object({
    membership: z.number(),
    pt_package: z.number(),
  }),
});

export const RevenueReportSchema = z.object({
  data: z.object({
    buckets: z.array(RevenueBucketSchema),
    fromDate: z.string(),
    toDate: z.string(),
    groupBy: z.enum(['day', 'month']),
  }),
});
export type RevenueReportData = z.infer<typeof RevenueReportSchema>['data'];
export type RevenueBucket = z.infer<typeof RevenueBucketSchema>;

// ---------------------------------------------------------------------------
// Query param types
// ---------------------------------------------------------------------------

export type VisitsReportQuery = {
  fromDate: string;
  toDate: string;
};

export type RevenueReportQuery = {
  fromDate: string;
  toDate: string;
  groupBy: 'day' | 'month';
};
```

---

### `features/reports/keys.ts` (NEW file)

**Analog:** `apps/admin-app/src/features/memberships/keys.ts` (lines 1–29 — exact key factory pattern)

```typescript
/**
 * Reports domain query-key factory (Phase 103).
 *
 * Hierarchy:
 *   all → visits(query) | revenue(query)
 */
import type { VisitsReportQuery, RevenueReportQuery } from './schemas';

export const reportsQueryKeys = {
  all: ['reports-data'] as const,  // distinct from legacy reportsKeys.all = ['reports']
  visits: (q: VisitsReportQuery) => [...reportsQueryKeys.all, 'visits', q] as const,
  revenue: (q: RevenueReportQuery) => [...reportsQueryKeys.all, 'revenue', q] as const,
} as const;
```

Note: use `'reports-data'` root (not `'reports'`) to avoid collision with the existing legacy `reportsKeys.all = ['reports']` in `features/reports/api.ts` (the old mock-based file).

---

### `features/reports/api.ts` (REPLACE — replace mock with real hooks)

**Analog:** `apps/admin-app/src/features/payroll/api.ts` lines 41–57 (owner-gated query with `enabled: can(role,'view','reports')`)

```typescript
/**
 * Reports domain TanStack Query hooks (Phase 103).
 *
 * ALL OWNER_ONLY — every hook is enabled-gated by can(role, 'view', 'reports').
 * Reception makes ZERO reports API calls (mirrors T-102-PAY-RBAC pattern).
 *
 * Buckets are SPARSE — callers must zero-fill before passing to charts.
 * Zero-fill utilities: fillHourlyBuckets(), fillDailyBuckets(), fillRevenueBuckets()
 * live in features/reports/utils.ts (pure functions, no React deps).
 *
 * ApiError re-exported (D-100-03-APIERROR-REEXPORT).
 */
import { useQuery } from '@tanstack/react-query';
import { staffRequest, ApiError } from '@/api/client';
import { useSession } from '@/features/auth/api';
import { can } from '@/shared/session/can';
import { reportsQueryKeys } from './keys';
import { VisitsReportSchema, RevenueReportSchema } from './schemas';
import type { VisitsReportQuery, RevenueReportQuery } from './schemas';

export function useVisitsReport(query: VisitsReportQuery) {
  const session = useSession();
  const role = session.data?.role ?? 'reception';
  return useQuery({
    queryKey: reportsQueryKeys.visits(query),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/reports/visits', {
        query: { fromDate: query.fromDate, toDate: query.toDate },
      });
      return VisitsReportSchema.parse(raw).data;
    },
    enabled: can(role, 'view', 'reports'),
    staleTime: 30_000,
  });
}

export function useRevenueReport(query: RevenueReportQuery) {
  const session = useSession();
  const role = session.data?.role ?? 'reception';
  return useQuery({
    queryKey: reportsQueryKeys.revenue(query),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/reports/revenue', {
        query: { fromDate: query.fromDate, toDate: query.toDate, groupBy: query.groupBy },
      });
      return RevenueReportSchema.parse(raw).data;
    },
    enabled: can(role, 'view', 'reports'),
    staleTime: 30_000,
  });
}

export { ApiError };
```

---

### `features/attendance/api.ts` (REPLACE)

**Analog:** `apps/admin-app/src/features/visits/api.ts` (after extension — use `useVisitsList`)

```typescript
/**
 * Attendance feature API hooks (Phase 103 — wire from mock to real).
 *
 * Delegates to features/visits hooks. This thin re-export layer lets
 * AttendancePage import from @/features/attendance/api without knowing
 * the visits domain key structure directly.
 *
 * useCheckIn and useGymMeta re-exported so CheckInModal only needs one import.
 */
export { useVisitsList as useAttendanceList, useCheckIn, useGymMeta } from '@/features/visits/api';
export { visitsKeys as attendanceVisitsKeys } from '@/features/visits/api';
export { ApiError } from '@/features/visits/api';
```

Alternatively (if ESLint import boundary requires a separate hook), wrap:

```typescript
import { useVisitsList } from '@/features/visits/api';
import type { VisitsListQuery } from '@/features/visits/schemas';

/** Attendance page list (reception+owner). Delegates to visits domain. */
export function useAttendanceList(filter: VisitsListQuery) {
  return useVisitsList(filter);
}
```

---

### `features/load/api.ts` (REPLACE)

**Analog:** `apps/admin-app/src/features/reports/api.ts` (new — `useVisitsReport`) + zero-fill transform inline

```typescript
/**
 * Load feature API hooks (Phase 103 — wire from mock to real).
 *
 * Wraps useVisitsReport and applies client-side zero-fill so the
 * IntensityHeatmap / AreaTrendChart always receive complete arrays (no NaN).
 *
 * Zero-fill:
 *   - hourly: always 24 points (hours 0–23)
 *   - daily: every calendar day in [fromDate, toDate]
 *
 * OWNER_ONLY: enabled gate inherited from useVisitsReport (can(role,'view','reports')).
 */
import { useVisitsReport } from '@/features/reports/api';
import { fillHourlyBuckets, fillDailyBuckets } from '@/features/reports/utils';
import type { VisitsReportQuery } from '@/features/reports/schemas';

export { reportsQueryKeys as loadKeys } from '@/features/reports/keys';

export function useLoad(query: VisitsReportQuery) {
  const result = useVisitsReport(query);
  // Transform sparse → complete only when data is present
  const data = result.data
    ? {
        ...result.data,
        hourly: fillHourlyBuckets(result.data.hourly),
        daily: fillDailyBuckets(result.data.daily, result.data.fromDate, result.data.toDate),
      }
    : undefined;
  return { ...result, data };
}
```

---

### `features/cashbox/api.ts` (REPLACE)

**Analog:** `apps/admin-app/src/features/payments/api.ts` (after extension — `usePaymentsLedger`)

```typescript
/**
 * Cashbox feature API hooks (Phase 103 — wire from mock to real).
 *
 * Delegates to features/payments usePaymentsLedger (OWNER_ONLY).
 * Daily totals computed client-side via computeDailyTotals().
 *
 * No shift concept — removed (no backend endpoint for shifts).
 * No refund action — refund rows are READ-ONLY in the ledger.
 */
import { useSession } from '@/features/auth/api';
import { usePaymentsLedger } from '@/features/payments/api';
import { computeDailyTotals } from '@/features/cashbox/utils';
import type { PaymentsLedgerQuery } from '@/features/payments/schemas';

export { paymentsKeys as cashboxPaymentsKeys } from '@/features/payments/api';
export { ApiError } from '@/features/payments/api';

export function useCashbox(filter: PaymentsLedgerQuery) {
  const session = useSession();
  const role = session.data?.role ?? 'reception';
  const result = usePaymentsLedger(filter, role);
  const dailyTotals = result.data ? computeDailyTotals(result.data.items) : [];
  return { ...result, dailyTotals };
}
```

---

### `features/finance/api.ts` (REPLACE)

**Analog:** `apps/admin-app/src/features/reports/api.ts` (new — `useRevenueReport`) + `usePaymentsLedger` for online slice

```typescript
/**
 * Finance feature API hooks (Phase 103 — wire from mock to real).
 *
 * Revenue tab: useRevenueReport (OWNER_ONLY, sparse → zero-filled by caller page).
 * Online-payments tab: usePaymentsLedger(filter, role) with method='online'.
 *
 * Both are OWNER_ONLY (can(role,'view','reports') / can(role,'view','payments')).
 */
export { useRevenueReport } from '@/features/reports/api';
export { usePaymentsLedger as useOnlinePayments } from '@/features/payments/api';
export { ApiError } from '@/features/reports/api';
```

---

### `layouts/AppLayout/nav-items.ts` (EXTEND — ownerOnly for Загруженность + Касса)

**Analog:** `apps/admin-app/src/layouts/AppLayout/nav-items.ts` itself (lines 64–70 show existing ownerOnly pattern)

**Current state (lines 56–80):** `Касса` has no `ownerOnly`; `Загруженность` has no `ownerOnly`.

**Correction — two targeted changes:**

Change `Касса` entry (currently lines 59):
```typescript
// BEFORE:
{ label: 'Касса', to: ROUTES.cashbox, icon: Wallet },

// AFTER:
{ label: 'Касса', to: ROUTES.cashbox, icon: Wallet, ownerOnly: true, ownerResource: 'payments' },
```

Change `Загруженность` entry (currently line 80):
```typescript
// BEFORE:
{ label: 'Загруженность', to: ROUTES.load, icon: Clock },

// AFTER:
{ label: 'Загруженность', to: ROUTES.load, icon: Clock, ownerOnly: true, ownerResource: 'reports' },
```

`Посещаемость` (line 79) remains ungated — no change.

---

## Shared Patterns

### Transport call + Zod parse
**Source:** `apps/admin-app/src/features/visits/api.ts` lines 37–42
**Apply to:** all new/extended `api.ts` files

```typescript
const raw = await staffRequest('get', '/api/v1/visits', { query: { clientId } });
return VisitsListResponseSchema.parse(raw).data;
```

Pattern: `staffRequest` returns raw JSON → `Schema.parse(raw).data` extracts the data envelope.
For single-item responses (not lists): `Schema.parse((raw as { data: unknown }).data)` (see `bookings/api.ts` line 99).

### Owner-gated enabled pattern
**Source:** `apps/admin-app/src/features/payroll/api.ts` lines 41–57
**Apply to:** `features/reports/api.ts`, `features/payments/api.ts` (global hook), `features/load/api.ts`, `features/cashbox/api.ts`, `features/finance/api.ts`

```typescript
const session = useSession();
const role = session.data?.role ?? 'reception';
return useQuery({
  ...
  enabled: can(role, 'view', 'reports'), // or 'payments'
  staleTime: 30_000,
});
```

Reception makes ZERO API calls — `enabled: false` when `can()` returns false. No API call is fired; the page shows Lock-EmptyState before any hook fires (client-side guard, not hook-guard).

### 409 multi-code handling (check-in)
**Source:** `apps/admin-app/src/components/modals/BookingModal.tsx` lines 121–134
**Apply to:** `CheckInModal.tsx` for the 3 distinct 409 codes

```typescript
try {
  await checkIn.mutateAsync({ clientId, clientName, currentUserId });
  toast.success('Визит зафиксирован', { description: selectedClient.fullName });
  onOpenChange(false);
} catch (err) {
  if (err instanceof ApiError) {
    // Map err.code → distinct Russian copy (stay in modal, show Callout)
    setApiError(err.code); // caller maps code → heading/body in render
  }
  // Modal stays open — user must see specific reason
}
```

The hook (`useCheckIn`) does NOT toast 409 errors. The modal catches `ApiError.code` and maps it to one of 3 `Callout tone='danger'` states. Selecting a new client clears `apiError` state.

### Optimistic prepend + rollback
**Source:** `apps/admin-app/src/features/memberships/api.ts` lines 129–186
**Apply to:** `useCheckIn` mutation in `features/visits/api.ts`

Core shape:
```typescript
onMutate: async (vars) => {
  await qc.cancelQueries({ queryKey: visitsKeys.lists() });
  const listSnapshots = qc.getQueriesData<...>({ queryKey: visitsKeys.lists() });
  // Prepend optimistic row with _optimistic: true flag
  for (const [key, data] of listSnapshots) {
    if (!data) continue;
    qc.setQueryData(key, { ...data, items: [optimisticRow, ...data.items] });
  }
  return { listSnapshots };
},
onError: (_err, _vars, ctx) => {
  // Rollback — restore all snapshots
  for (const [key, data] of ctx.listSnapshots) {
    qc.setQueryData(key as readonly unknown[], data);
  }
},
```

### Sparse bucket zero-fill utility (NEW `features/reports/utils.ts`)
**Analog:** none in codebase — new utility. Pattern from CONTEXT.md + UI-SPEC §4.1.

```typescript
// features/reports/utils.ts (NEW)
import { eachDayOfInterval, parseISO, format } from 'date-fns';
import type { VisitsReportHourlyBucket, VisitsReportDailyBucket, RevenueBucket } from './schemas';

/** Fill sparse hourly array to full 24 hours (0–23). Missing hours → count: 0. */
export function fillHourlyBuckets(sparse: VisitsReportHourlyBucket[]): VisitsReportHourlyBucket[] {
  const map = new Map(sparse.map((b) => [b.hour, b.count]));
  return Array.from({ length: 24 }, (_, hour) => ({ hour, count: map.get(hour) ?? 0 }));
}

/** Fill sparse daily array to every calendar day in [fromDate, toDate]. Missing dates → count: 0. */
export function fillDailyBuckets(
  sparse: VisitsReportDailyBucket[],
  fromDate: string,
  toDate: string,
): VisitsReportDailyBucket[] {
  const map = new Map(sparse.map((b) => [b.date, b.count]));
  const days = eachDayOfInterval({ start: parseISO(fromDate), end: parseISO(toDate) });
  return days.map((d) => { const date = format(d, 'yyyy-MM-dd'); return { date, count: map.get(date) ?? 0 }; });
}

/** Fill sparse revenue buckets (groupBy=day). Missing dates → zero bucket. */
export function fillRevenueBuckets(
  sparse: RevenueBucket[],
  fromDate: string,
  toDate: string,
  groupBy: 'day' | 'month',
): RevenueBucket[] {
  const ZERO: Omit<RevenueBucket, 'period'> = {
    netKopecks: 0,
    byMethod: { cash: 0, online: 0 },
    bySubjectKind: { membership: 0, pt_package: 0 },
  };
  const map = new Map(sparse.map((b) => [b.period, b]));
  if (groupBy === 'day') {
    const days = eachDayOfInterval({ start: parseISO(fromDate), end: parseISO(toDate) });
    return days.map((d) => { const period = format(d, 'yyyy-MM-dd'); return map.get(period) ?? { period, ...ZERO }; });
  }
  // groupBy === 'month': fill months
  // ... similar logic with format(d, 'yyyy-MM')
  return sparse; // fallback — implement full month iteration in plan
}
```

### Daily totals client-side computation (NEW `features/cashbox/utils.ts`)
**Analog:** none in codebase — new utility. Pattern from CONTEXT.md §Cashbox + UI-SPEC §5.2.

```typescript
// features/cashbox/utils.ts (NEW)
import { formatInTimeZone } from 'date-fns-tz';
import type { PaymentData } from '@/features/payments/schemas';
import type { DailyTotal } from '@/features/payments/schemas';

const MSK_TZ = 'Europe/Moscow';

/** Group payments by MSK date, sum signed amountKopecks. Sorted ascending. */
export function computeDailyTotals(items: PaymentData[]): DailyTotal[] {
  const map = new Map<string, number>();
  for (const item of items) {
    const date = formatInTimeZone(new Date(item.receivedAt), MSK_TZ, 'yyyy-MM-dd');
    map.set(date, (map.get(date) ?? 0) + item.amountKopecks);
  }
  return Array.from(map.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, totalKopecks]) => ({ date, totalKopecks }));
}
```

### can() resources confirmed
**Source:** `apps/admin-app/src/shared/session/can.ts`

- `visits` — reception+owner (NOT in OWNER_ONLY for view/check_in actions)
- `reports` — owner-only: `{ action: 'view', resource: 'reports' }` at line 9 of OWNER_ONLY
- `payments` — owner-only: `{ action: 'view', resource: 'payments' }` at line 41 of OWNER_ONLY

No changes needed to `can.ts` — all three resources are already defined.

### ApiError re-export pattern
**Source:** `apps/admin-app/src/features/visits/api.ts` line 52
**Apply to:** all new/extended `api.ts` files

```typescript
// Last line of every api.ts
export { ApiError };
```

### EmptyState Lock pattern (owner-only pages)
**Source:** analog is P101/P102 pattern (described in UI-SPEC §2.1). Component: `apps/admin-app/src/components/feedback/EmptyState.tsx`
**Apply to:** Load, Cashbox, Finance pages — early return before any hooks fire:

```typescript
// At top of LoadPage / CashboxPage / FinancePage
if (!can(role, 'view', ownerResource)) {
  return (
    <EmptyState
      icon={Lock}
      title="Недостаточно прав"
      body="Этот раздел доступен только владельцу. Обратитесь к владельцу клуба."
      className="py-24"
    />
  );
}
// Hooks only called below this guard
```

---

## No Analog Found

All files have analogs. The following are truly new (no existing code to copy from):

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `features/reports/utils.ts` | utility | transform | No zero-fill utility exists; pattern described in CONTEXT.md |
| `features/cashbox/utils.ts` | utility | transform | No daily-total grouping utility exists |
| `components/modals/CheckInModal.tsx` | component | mutation | Existing `CheckinModal.tsx` is mock-only (QR scanner); must be rebuilt from BookingModal pattern |

For `CheckInModal.tsx`: use `BookingModal.tsx` as the structural analog — same `AdaptiveModal` + `Section` + `ModalInput` + `ResultList` + `ResultItem` + `Callout` + `ModalButton` pattern; omit PT-package picker; add gym-meta pre-validation callout and 3-code 409 Callout mapping.

---

## Metadata

**Analog search scope:** `apps/admin-app/src/features/`, `apps/admin-app/src/components/modals/`, `apps/admin-app/src/layouts/`, `apps/admin-app/src/shared/`
**Files read:** 18
**Pattern extraction date:** 2026-06-13
