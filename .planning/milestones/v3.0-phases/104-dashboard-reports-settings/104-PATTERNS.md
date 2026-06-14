# Phase 104: Dashboard, Reports + Settings — Pattern Map

**Mapped:** 2026-06-13
**Files analyzed:** 12 new/modified files
**Analogs found:** 11 / 12

---

## Confirmed Findings Before Classification

### PATCH /auth/me — DOES NOT EXIST
Grep of `apps/backend/app/modules/auth/router.py` found these handlers: `POST /login`, `POST /refresh`, `POST /logout`, `GET /me`, `GET /sessions` (list), `POST /sessions/{familyId}/revoke`, `POST /logout-all`, telegram endpoints, OTP, password-reset. **No `PATCH /me` route exists.** Profile edit is READ-ONLY in Phase 104.

### can() resources — CONFIRMED
`audit-log` and `users` are already in `can.ts` OWNER_ONLY matrix. `dashboard` and `profile` are in `Resource` union but NOT in OWNER_ONLY (both roles can access). `settings` is owner-only for `view`.

### Nav entries — CONFIRMED MISSING
`nav-items.ts` has NO audit-log or users entry. «Журнал действий» (`ownerOnly: true, ownerResource: 'audit-log'`) must be added to «Аналитика» section. Settings navigation stays as-is (self-service sections are inside SettingsPage already accessible to owner who can view settings).

### can('reception','view','settings') — owner-only
Settings nav item is `ownerOnly: true, ownerResource: 'settings'` — reception cannot reach SettingsPage at all. Profile/sessions are self-service but entry point is within Settings. This matches CONTEXT.md.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `features/dashboard/api.ts` | service | request-response (multi-domain compose) | `features/reports/api.ts` | role-match |
| `features/reports/api.ts` | service | CRUD (owner-gated queries) | `features/reports/api.ts` itself (extend) | exact — extend |
| `features/reports/schemas.ts` | model | transform | `features/reports/schemas.ts` itself (extend) | exact — extend |
| `features/reports/keys.ts` | utility | — | `features/reports/keys.ts` itself (extend) | exact — extend |
| `features/audit/api.ts` | service | CRUD + pagination | `features/clients/api.ts` | role-match |
| `features/audit/schemas.ts` *(new)* | model | transform | `features/reports/schemas.ts` | role-match |
| `features/settings/api.ts` | service | request-response | `features/auth/api.ts` | role-match |
| `features/users/api.ts` *(new)* | service | CRUD + mutations | `features/clients/api.ts` | exact |
| `features/users/schemas.ts` *(new)* | model | transform | `features/clients/schemas.ts` (pattern) | role-match |
| `src/api/csv.ts` *(new)* | utility | file-I/O | `src/api/client.ts` (reuse helpers) | partial |
| `layouts/AppLayout/nav-items.ts` | config | — | `layouts/AppLayout/nav-items.ts` itself | exact — extend |
| `pages/dashboard/DashboardPage.tsx` | component | request-response | `pages/finance/FinancePage.tsx` (multi-hook) | role-match |

---

## Pattern Assignments

---

### `features/dashboard/api.ts` (service, request-response)

**Action:** Replace monolithic `useDashboard()` mock with per-domain hooks. Keep the existing `dashboardKeys` export for now (legacy compat) but add new per-domain key prefixes or reuse the domain keys directly.

**Analog:** `features/reports/api.ts`

**Pattern — owner-gated hook** (lines 65–98 of existing `features/reports/api.ts`):
```typescript
import { useQuery } from '@tanstack/react-query';
import { staffRequest, mockResponse, ApiError } from '@/api/client';
import { can } from '@/shared/session/can';
import type { Role } from '@/shared/session/types';
import { reportsQueryKeys } from './keys';
import { VisitsReportSchema, RevenueReportSchema } from './schemas';
import type { VisitsReportQuery, RevenueReportQuery } from './schemas';

export function useVisitsReport(query: VisitsReportQuery, role: Role) {
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
```

**Pattern — both-role hook (no owner gate)** — use `useBookingsByWeek` from `features/bookings/api.ts` as analog for dashboard's ScheduleToday and ExpiringMemberships hooks (no `enabled:` restriction, always active when authenticated):
```typescript
export function useBookingsByWeek(params: { fromTime: string; toTime: string }) {
  return useQuery({
    queryKey: bookingsKeys.list({ fromTime: params.fromTime, toTime: params.toTime }),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/bookings', { query: { ... } });
      return BookingsListResponseSchema.parse(raw).data;
    },
    staleTime: 30_000,
  });
}
```

**Wiring plan for `features/dashboard/api.ts`:**
- `useScheduleToday(date: string)` — `GET /api/v1/bookings?date={date}` (both roles, no `enabled:` guard)
- `useExpiringMemberships()` — `GET /api/v1/memberships?expiring=true&withinDays=7` (both roles)
- Re-export `useVisitsReport`, `useRevenueReport` from `features/reports/api.ts` (don't duplicate)
- Re-export `useTrainersReport`, `useClientsReport` once added to `features/reports/api.ts`
- Remove the `useDashboard()` mock after page is wired

---

### `features/reports/api.ts` — EXTEND (service, CRUD owner-gated)

**Action:** Add `useClientsReport` and `useTrainersReport` following the exact pattern of `useVisitsReport`/`useRevenueReport`.

**Pattern to copy** (existing lines 65–98):
```typescript
export function useClientsReport(query: ClientsReportQuery, role: Role) {
  return useQuery({
    queryKey: reportsQueryKeys.clients(query),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/reports/clients', {
        query: { fromDate: query.fromDate, toDate: query.toDate, within: query.within ?? 30 },
      });
      return ClientsReportSchema.parse(raw).data;
    },
    enabled: can(role, 'view', 'reports'),
    staleTime: 30_000,
  });
}

export function useTrainersReport(query: TrainersReportQuery, role: Role) {
  return useQuery({
    queryKey: reportsQueryKeys.trainers(query),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/reports/trainers', {
        query: { fromDate: query.fromDate, toDate: query.toDate },
      });
      return TrainersReportSchema.parse(raw).data;
    },
    enabled: can(role, 'view', 'reports'),
    staleTime: 30_000,
  });
}
```

**Keep:** `useReports()` mock + `reportsKeys` legacy export (Phase 104 will flip ReportsPage away from them, then delete).

---

### `features/reports/schemas.ts` — EXTEND (model, transform)

**Action:** Add `ClientsReportSchema`, `TrainersReportSchema`, and query param types.

**Pattern to copy** (existing lines 27–35 of `features/reports/schemas.ts`):
```typescript
// clients report
export const ClientsReportSchema = z.object({
  data: z.object({
    activeCount: z.number(),
    expiringCount: z.number(),
    newClientsCount: z.number(),
    withinDays: z.number(),
  }),
});
export type ClientsReportData = z.infer<typeof ClientsReportSchema>['data'];

// trainers report — rows array
export const TrainerRowSchema = z.object({
  trainerId: z.string(),
  name: z.string(),
  sessionCount: z.number(),
  totalHours: z.number(),
  uniqueClients: z.number(),
  utilizationPct: z.number(),
  totalRevenueKopecks: z.number(),
});
export const TrainersReportSchema = z.object({
  data: z.object({
    rows: z.array(TrainerRowSchema),
  }),
});
export type TrainersReportData = z.infer<typeof TrainersReportSchema>['data'];
export type TrainerRow = z.infer<typeof TrainerRowSchema>;

// Query param types
export type ClientsReportQuery = { fromDate: string; toDate: string; within?: number };
export type TrainersReportQuery = { fromDate: string; toDate: string };
```

---

### `features/reports/keys.ts` — EXTEND (utility)

**Action:** Add `clients` and `trainers` keys following existing pattern (lines 14–15):

```typescript
export const reportsQueryKeys = {
  all: ['reports-data'] as const,
  visits: (q: VisitsReportQuery) => [...reportsQueryKeys.all, 'visits', q] as const,
  revenue: (q: RevenueReportQuery) => [...reportsQueryKeys.all, 'revenue', q] as const,
  // ADD:
  clients: (q: ClientsReportQuery) => [...reportsQueryKeys.all, 'clients', q] as const,
  trainers: (q: TrainersReportQuery) => [...reportsQueryKeys.all, 'trainers', q] as const,
} as const;
```

---

### `features/audit/api.ts` — REWRITE (service, CRUD + pagination)

**Action:** Replace mock `useAuditLog()` with real paginated query + CSV-aware filter params.

**Analog:** `features/clients/api.ts`

**Pattern — key factory + paginated query** (lines 37–58 of `features/clients/api.ts`):
```typescript
import { useQuery } from '@tanstack/react-query';
import { staffRequest, ApiError } from '@/api/client';
import { can } from '@/shared/session/can';
import type { Role } from '@/shared/session/types';
import { AuditLogResponseSchema } from './schemas';

export const auditKeys = {
  all: ['audit'] as const,
  lists: () => [...auditKeys.all, 'list'] as const,
  list: (filter: AuditFilter) => [...auditKeys.lists(), filter] as const,
};

export function useAuditLog(filter: AuditFilter, role: Role) {
  return useQuery({
    queryKey: auditKeys.list(filter),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/audit-log', {
        query: {
          ...(filter.actorEmailSnapshot && { actorEmailSnapshot: filter.actorEmailSnapshot }),
          ...(filter.resourceType && { resourceType: filter.resourceType }),
          ...(filter.action && { action: filter.action }),
          ...(filter.from && { from: filter.from }),
          ...(filter.to && { to: filter.to }),
          page: filter.page ?? 1,
          pageSize: 25,
        },
      });
      return AuditLogResponseSchema.parse(raw).data;
    },
    enabled: can(role, 'view', 'audit-log'),
    staleTime: 30_000,
  });
}

export { ApiError };
```

---

### `features/audit/schemas.ts` *(new)* (model, transform)

**Analog:** `features/reports/schemas.ts` (structure) + audit item fields from CONTEXT.md

```typescript
import { z } from 'zod';

export const AuditEventSchema = z.object({
  id: z.string(),
  createdAt: z.string(),
  actorUserId: z.string(),
  actorEmailSnapshot: z.string(),
  action: z.string(),
  resourceType: z.string(),
  resourceId: z.string().nullable(),
  payload: z.record(z.unknown()).nullable(),
});

export const AuditLogResponseSchema = z.object({
  data: z.object({
    items: z.array(AuditEventSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
});
export type AuditEvent = z.infer<typeof AuditEventSchema>;
export type AuditLogData = z.infer<typeof AuditLogResponseSchema>['data'];

export type AuditFilter = {
  actorEmailSnapshot?: string;
  resourceType?: string;
  action?: string;
  from?: string;
  to?: string;
  page?: number;
};
```

---

### `features/settings/api.ts` — REWRITE (service, request-response)

**Action:** Replace mock `useSettings()` with real auth/sessions hooks + profile hook.

**Analog:** `features/auth/api.ts` (lines 46–55, 81–89 — useSession, useLogout patterns)

**Profile (read-only — no PATCH /auth/me):**
```typescript
// Profile is read-only: reuse authKeys.me + useSession() from features/auth/api.ts.
// ProfileSection reads MeData (id, role, fullName, email) from useSession().data.
// No separate useProfile hook needed — import useSession from features/auth/api.ts.
```

**Sessions list:**
```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { staffRequest, ApiError } from '@/api/client';
import { SessionsListResponseSchema, type SessionData } from './schemas';

export const settingsKeys = {
  sessions: ['auth', 'sessions'] as const,
};

export function useSessions() {
  return useQuery({
    queryKey: settingsKeys.sessions,
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/auth/sessions');
      return SessionsListResponseSchema.parse(raw).data;
    },
    staleTime: 30_000,
  });
}
```

**Session revoke (non-current):**
```typescript
export function useRevokeSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (familyId: string) =>
      staffRequest('post', '/api/v1/auth/sessions/{family_id}/revoke', {
        params: { family_id: familyId },
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: settingsKeys.sessions });
    },
  });
}
```

**Self-revoke (current session):** after 204, publish `authBus.emit('session_expired')` — same path as T-100-05 in `features/auth/RequireAuth.tsx`. No invalidation needed since the user will be navigated to `/login`.

---

### `features/users/api.ts` *(new)* (service, CRUD)

**Analog:** `features/clients/api.ts` — exact same pattern: key factory + list query + mutations + invalidation + ApiError re-export.

**Pattern — key factory** (lines 37–43 of `features/clients/api.ts`):
```typescript
export const usersKeys = {
  all: ['users'] as const,
  lists: () => [...usersKeys.all, 'list'] as const,
  list: (filter: UsersFilter) => [...usersKeys.lists(), filter] as const,
  detail: (id: string) => [...usersKeys.all, 'detail', id] as const,
};
```

**Pattern — list query** (lines 49–58):
```typescript
export function useUsers(filter: UsersFilter, role: Role) {
  return useQuery({
    queryKey: usersKeys.list(filter),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/users', {
        query: { page: filter.page ?? 1, pageSize: 20 },
      });
      return UsersListResponseSchema.parse(raw).data;
    },
    enabled: can(role, 'list', 'users'),
    staleTime: 30_000,
  });
}
```

**Pattern — invite mutation** (follow `useCreateClient` lines 78–89, but include `includeInviteLink` query param):
```typescript
export function useInviteUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: UserInviteInput) => {
      const raw = await staffRequest('post', '/api/v1/users', {
        query: { includeInviteLink: true },
        body,
      });
      return UserInviteResponseSchema.parse((raw as { data: unknown }).data);
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: usersKeys.lists() });
    },
  });
}
```

**Pattern — deactivate/reactivate/delete mutations** (follow `useDeleteClient` lines 114–123):
```typescript
export function useDeactivateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      staffRequest('patch', '/api/v1/users/{user_id}/deactivate', { params: { user_id: id } }),
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: usersKeys.lists() });
    },
  });
}
// useReactivateUser, useDeleteUser follow same pattern
```

**409 error handling** — from `features/payroll/api.ts` pattern (catch ApiError, check `err.code`, call `toast.error(...)`):
```typescript
// In the page/modal layer (not in the hook):
} catch (err) {
  if (err instanceof ApiError) {
    if (err.code === 'cannot_deactivate_self') toast.error('Нельзя деактивировать себя');
    else if (err.code === 'cannot_deactivate_last_owner') toast.error('Нельзя деактивировать единственного владельца');
    else if (err.code === 'already_inactive') toast.error('Пользователь уже неактивен');
    else toast.error('Не удалось выполнить действие. Попробуйте ещё раз.');
  }
}
```

---

### `features/users/schemas.ts` *(new)* (model, transform)

**Analog:** `features/clients/schemas.ts` structure (Zod object + paginated list wrapper).

```typescript
import { z } from 'zod';

export const UserSchema = z.object({
  id: z.string(),
  email: z.string(),
  fullName: z.string(),
  role: z.enum(['owner', 'reception']),
  status: z.enum(['active', 'pending_invitation', 'deactivated']),
});
export type UserData = z.infer<typeof UserSchema>;

export const UsersListResponseSchema = z.object({
  data: z.object({
    items: z.array(UserSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
});

export const UserInviteResponseSchema = z.object({
  id: z.string(),
  email: z.string(),
  fullName: z.string(),
  role: z.enum(['owner', 'reception']),
  inviteLinkUrl: z.string().optional(),
  invitationExpiresAt: z.string().optional(),
});

export type UserInviteInput = { email: string; fullName: string; role: 'owner' | 'reception' };
export type UsersFilter = { page?: number };
```

---

### `src/api/csv.ts` *(new)* (utility, file-I/O)

**No existing analog** — first file-download helper in the codebase. Reuse `appendQuery` and `parseErrorBody` patterns from `src/api/client.ts` (lines 122–153). CSV fetching uses `credentials:'include'` (same as `staffRequest`) but returns `blob()` → anchor download, not JSON.

**Pattern to implement:**
```typescript
// GET is CSRF-exempt — no X-CSRF-Token header needed.
// On error: parse body → throw with message for caller to toast.
export async function downloadCsv(
  endpoint: string,
  filename: string,
  query?: Record<string, string | number | boolean>,
): Promise<void> {
  const url = appendQuery(endpoint, query);
  const res = await fetch(url, { credentials: 'include' });
  if (!res.ok) {
    const body = await parseErrorBody(res);
    throw new Error(body.message || 'Download failed');
  }
  const blob = await res.blob();
  const href = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = href;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(href);
}
```

**`appendQuery` and `parseErrorBody` are NOT currently exported** from `src/api/client.ts` (lines 83–132). The planner must either:
1. Export them from `api/client.ts` (preferred — add `export` keyword).
2. Or duplicate the minimal logic inline in `csv.ts`.

---

### `layouts/AppLayout/nav-items.ts` — EXTEND (config)

**Action:** Add «Журнал действий» nav entry to «Аналитика» section. Confirm by reading lines 61–81.

**Pattern to copy** (lines 65–73 of existing `nav-items.ts`):
```typescript
{
  label: 'Журнал действий',
  to: ROUTES.audit,
  icon: Activity,            // reuse Activity icon — already imported
  ownerOnly: true,
  ownerResource: 'audit-log',
},
```

Add after «Загруженность» entry. `ROUTES.audit` must exist in `app/routes.ts` — confirm this route constant exists; if missing, add it.

---

## Shared Patterns

### staffRequest + Schema.parse(raw).data
**Source:** `features/clients/api.ts` lines 52–57; `features/reports/api.ts` lines 69–74
**Apply to:** All new api.ts files (`audit`, `settings`, `users`, `dashboard`)
```typescript
const raw = await staffRequest('get', '/api/v1/...', { query: { ... } });
return SomeSchema.parse(raw).data;
```

### Owner-gating with `can()` + `enabled:`
**Source:** `features/reports/api.ts` lines 74, 94
**Apply to:** `useAuditLog` (resource: `'audit-log'`, action: `'view'`), `useUsers` (resource: `'users'`, action: `'list'`), all dashboard owner-only hooks (resource: `'reports'`)
```typescript
enabled: can(role, 'view', 'reports'),   // reports hooks
enabled: can(role, 'view', 'audit-log'), // audit hook
enabled: can(role, 'list', 'users'),     // users hook
```

### CSRF on mutations
**Source:** `src/api/client.ts` lines 197–199 (automatic in `staffRequest` for POST/PATCH/DELETE)
**Apply to:** `useRevokeSession`, `useInviteUser`, `useDeactivateUser`, `useReactivateUser`, `useDeleteUser`, `useRevokeInvitation`
No explicit CSRF header code needed in hooks — `staffRequest` adds `X-CSRF-Token` automatically for mutating methods.

### ApiError re-export
**Source:** `features/clients/api.ts` line 130; `features/auth/api.ts` line 119
**Apply to:** All new api.ts files — end with `export { ApiError };`

### Paginated response pattern
**Source:** `features/clients/api.ts` (ClientsListResponseSchema wraps `{data:{items,total,page,pageSize}}`)
**Apply to:** `AuditLogResponseSchema`, `UsersListResponseSchema`, `SessionsListResponseSchema`

### onSettled invalidation (non-optimistic)
**Source:** `features/clients/api.ts` lines 85–87, 107–110
**Apply to:** All users mutations (`useInviteUser`, `useDeactivateUser`, `useReactivateUser`, `useDeleteUser`)
```typescript
onSettled: () => {
  void qc.invalidateQueries({ queryKey: usersKeys.lists() });
},
```

### Zero-fill + NaN guard
**Source:** `features/reports/utils.ts` — `fillHourlyBuckets`, `fillDailyBuckets`, `fillRevenueBuckets`
**Apply to:** Dashboard widget hooks that consume visits/revenue data. Import and apply before passing to chart components.

### mskTodayISO / mskDaysAgoISO
**Source:** Used in P103 (located in `features/reports/utils.ts` or a date helper — confirm import path). These provide MSK-anchored date strings for default date ranges (dashboard today, reports last-30-days).

### authBus session_expired (self-revoke)
**Source:** `features/auth/RequireAuth.tsx` — authBus subscriber that navigates to `/login`. Self-revoke of the current session must publish `session_expired` on authBus after 204, NOT navigate directly.

### Lock-EmptyState pattern
**Source:** `pages/reports/ReportsPage.tsx` or `pages/finance/FinancePage.tsx` (P103 implementation)
**Apply to:** AuditPage (reception gate), ReportsPage (reception gate), TeamSection body (reception gate)
Check the exact import path for the Lock-EmptyState — it may be an inline pattern or a component in `components/feedback/`.

---

## Settings schemas (new `features/settings/schemas.ts`)

**New file needed** to replace `features/settings/types.ts` (mock-era type) with Zod schemas for sessions wire format.

```typescript
import { z } from 'zod';

export const SessionSchema = z.object({
  familyId: z.string(),
  createdAt: z.string(),
  lastUsedAt: z.string(),
  userAgent: z.string(),
  channel: z.string(), // 'admin_web' | 'api'
  isCurrent: z.boolean(),
});

export const SessionsListResponseSchema = z.object({
  data: z.object({
    items: z.array(SessionSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
});

export type SessionData = z.infer<typeof SessionSchema>;
export type SessionsListData = z.infer<typeof SessionsListResponseSchema>['data'];
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `src/api/csv.ts` | utility | file-I/O | First blob-download helper in codebase; no streaming/file-download pattern exists. Reuse `appendQuery`/`parseErrorBody` internals from `api/client.ts` but requires exporting them first. |

---

## Metadata

**Analog search scope:** `apps/admin-app/src/features/`, `apps/admin-app/src/pages/`, `apps/admin-app/src/api/`, `apps/admin-app/src/layouts/`, `apps/admin-app/src/shared/`
**Files scanned:** 19 source files read
**Backend verified:** `apps/backend/app/modules/auth/router.py` — confirmed NO `PATCH /auth/me` endpoint. Profile edit deferred.
**Pattern extraction date:** 2026-06-13
