# Phase 22: admin-web wiring — memberships + visits + active sessions UI - Pattern Map

**Mapped:** 2026-05-08
**Files analyzed:** 42 new/modified files
**Analogs found:** 40 / 42

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `features/memberships/api/keys.ts` | utility | request-response | `features/clients/api/keys.ts` | exact |
| `features/memberships/api/hooks.ts` | hook | CRUD | `features/clients/api/hooks.ts` | exact |
| `features/memberships/components/MembershipsBlock.tsx` | component | request-response | `features/clients/components/ClientsTable.tsx` | role-match |
| `features/memberships/components/SellMembershipDialog.tsx` | component | request-response | `features/clients/components/ClientFormDialog.tsx` | exact |
| `features/memberships/components/CancelMembershipDialog.tsx` | component | request-response | `features/clients/components/ClientFormDialog.tsx` | role-match |
| `features/memberships/components/MembershipsListPage.tsx` | component | request-response | `features/clients/components/ClientsTable.tsx` | role-match |
| `features/memberships/components/MembershipPlansPage.tsx` | component | CRUD | `features/clients/components/ClientsTable.tsx` | role-match |
| `features/memberships/model/schema.ts` | utility | transform | `features/clients/model/schema.ts` | exact |
| `features/memberships/index.ts` | config | — | `features/clients/index.ts` | exact |
| `features/visits/api/keys.ts` | utility | request-response | `features/clients/api/keys.ts` | exact |
| `features/visits/api/hooks.ts` | hook | request-response | `features/clients/api/hooks.ts` | exact |
| `features/visits/components/RecentVisitsBlock.tsx` | component | request-response | `features/clients/components/ClientsTable.tsx` | role-match |
| `features/visits/components/CheckInPage.tsx` | component | request-response | `features/clients/components/ClientForm.tsx` | role-match |
| `features/visits/model/schema.ts` | utility | transform | `features/clients/model/schema.ts` | exact |
| `features/visits/index.ts` | config | — | `features/clients/index.ts` | exact |
| `routes/_protected/membership-plans.tsx` | route | request-response | `routes/_protected/clients.tsx` | exact |
| `routes/_protected/memberships.tsx` | route | request-response | `routes/_protected/clients.tsx` | role-match |
| `routes/_protected/visits.tsx` | route | request-response | `routes/_protected/clients.tsx` | role-match |
| `routes/_protected/clients.$clientId.tsx` | route | request-response | `routes/_protected/clients.tsx` | role-match |
| `shared/api/contracts/memberships.ts` | model | — | `shared/api/contracts/clients.ts` | exact |
| `shared/api/contracts/visits.ts` | model | — | `shared/api/contracts/clients.ts` | exact |
| `shared/api/contracts/visitsMeta.ts` | model | — | `shared/api/contracts/auth.ts` | role-match |
| `shared/api/services/mock/memberships.ts` | service | CRUD | `shared/api/services/mock/clients.ts` | exact |
| `shared/api/services/mock/visits.ts` | service | request-response | `shared/api/services/mock/clients.ts` | role-match |
| `shared/api/services/http/memberships.ts` | service | CRUD | `shared/api/services/http/clients.ts` | exact |
| `shared/api/services/http/visits.ts` | service | request-response | `shared/api/services/http/clients.ts` | exact |
| `shared/api/services/http/_membershipsAdapter.ts` | utility | transform | `shared/api/services/http/_clientsAdapter.ts` | exact |
| `shared/api/services/http/_visitsAdapter.ts` | utility | transform | `shared/api/services/http/_clientsAdapter.ts` | exact |
| `__fixtures/features/illegal-cross-feature-import.ts` | test | — | `__fixtures/features/illegal-mock-import.ts` | exact |
| `features/auth/components/SessionsList.tsx` | component | request-response | `features/clients/components/ClientsTable.tsx` | role-match |
| `features/auth/api/sessionsHooks.ts` | hook | request-response | `features/auth/api/hooks.ts` | exact |
| `shared/session/registry.ts` (modify) | config | — | existing file | in-place extend |
| `shared/api/services/mock/index.ts` (modify) | config | — | existing file | in-place extend |
| `shared/api/services/http/index.ts` (modify) | config | — | existing file | in-place extend |
| `features/clients/components/ClientsTable.tsx` (modify) | component | request-response | existing file | in-place extend |
| `eslint.config.js` (modify) | config | — | existing file | in-place extend |
| `shared/i18n/ru.ts` (modify) | utility | — | existing file | in-place extend |
| `shared/i18n/date.ts` (modify) | utility | — | existing file | in-place extend |
| `features/clients/components/ClientsTable.rbac.test.tsx` (modify) | test | — | existing file | in-place extend |
| `packages/api-client/src/schema.contract.test.ts` (modify) | test | — | existing file | in-place extend |
| `backend/app/modules/visits/router.py` (modify) | route | request-response | existing file | in-place extend |
| `backend/app/integrations/telegram/handlers.py` (modify) | middleware | event-driven | existing file | in-place extend |

---

## Pattern Assignments

### `features/memberships/api/keys.ts` (utility, request-response)

**Analog:** `apps/admin-web/src/features/clients/api/keys.ts` (lines 1–10)

**Imports + full pattern** (copy verbatim, swap domain):
```typescript
import type { MembershipsListQuery } from '@/shared/api/contracts/memberships'
import type { MembershipId } from '@/entities/membership'

export const membershipsKeys = {
  all: ['memberships'] as const,
  lists: () => [...membershipsKeys.all, 'list'] as const,
  list: (filter: MembershipsListQuery) => [...membershipsKeys.lists(), filter] as const,
  details: () => [...membershipsKeys.all, 'detail'] as const,
  detail: (id: MembershipId) => [...membershipsKeys.details(), id] as const,
  byClient: (clientId: string) => [...membershipsKeys.all, 'byClient', clientId] as const,
} as const
```

Add a `byClient` sub-key since `useMembershipsByClient` is a first-class hook (distinct from `list`).

For `features/visits/api/keys.ts`, same structure with `visitsKeys` + a `recentByClient(clientId, opts)` sub-key:
```typescript
export const visitsKeys = {
  all: ['visits'] as const,
  lists: () => [...visitsKeys.all, 'list'] as const,
  list: (filter: VisitsListQuery) => [...visitsKeys.lists(), filter] as const,
  recentByClient: (clientId: string, opts: { limit: number }) =>
    [...visitsKeys.all, 'recentByClient', clientId, opts] as const,
  gymMeta: ['visits', 'gymMeta'] as const,
} as const
```

Note: `gymMeta` is a constant (not a function) because it takes no parameters.

---

### `features/memberships/api/hooks.ts` + `features/visits/api/hooks.ts` (hook, CRUD/request-response)

**Analog:** `apps/admin-web/src/features/clients/api/hooks.ts` (lines 1–125)

**Imports pattern** (lines 1–9):
```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { membershipsKeys } from './keys'
import { services } from '@/shared/api/services'
import type {
  MembershipsListQuery,
  MembershipCreateInput,
  MembershipCancelInput,
} from '@/shared/api/contracts/memberships'
import type { Membership, MembershipId, Pagination } from '@/entities/membership'
```

**Read query pattern** (lines 11–26):
```typescript
export function useMembershipsByClient(clientId: string) {
  return useQuery({
    queryKey: membershipsKeys.byClient(clientId),
    queryFn: () => services.memberships.byClient(clientId),
    enabled: !!clientId,
    staleTime: 30_000,
  })
}
```

**Optimistic mutation pattern for cancel** (mirrors `useDeleteClient` lines 100–125):
```typescript
export function useCancelMembership() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ membershipId, reason }: { membershipId: MembershipId; reason?: string }) =>
      services.memberships.cancel(membershipId, reason),
    onMutate: async ({ membershipId }) => {
      await qc.cancelQueries({ queryKey: membershipsKeys.lists() })
      const snapshots = qc.getQueriesData<Pagination<Membership>>({ queryKey: membershipsKeys.lists() })
      for (const [key, data] of snapshots) {
        if (!data) continue
        qc.setQueryData<Pagination<Membership>>(key, {
          ...data,
          items: data.items.map((m) =>
            m.id === membershipId ? { ...m, status: 'cancelled' } : m,
          ),
        })
      }
      return { snapshots }
    },
    onError: (_err, _vars, ctx) => {
      if (!ctx) return
      for (const [key, data] of ctx.snapshots) qc.setQueryData(key, data)
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: membershipsKeys.lists() })
    },
  })
}
```

**`useGymMeta` special case** — `staleTime: 300_000` (5 min, per UI-SPEC FE-08d):
```typescript
export function useGymMeta() {
  return useQuery({
    queryKey: visitsKeys.gymMeta,
    queryFn: () => services.visits.gymMeta(),
    staleTime: 300_000,
  })
}
```

**`useCheckIn` mutation** — no optimistic update (server derives all fields); invalidate visits list on settle:
```typescript
export function useCheckIn() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (clientId: string) => services.visits.checkIn(clientId),
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: visitsKeys.lists() })
    },
  })
}
```

---

### `features/memberships/components/MembershipsBlock.tsx` (component, request-response)

**Analog:** `apps/admin-web/src/features/clients/components/ClientsTable.tsx` (lines 1–159)

**Key patterns to copy:**
- Three-state render: skeleton (loading) → error → data (lines 113–159).
- `<RoleGate action="cancel" resource="memberships">` around the Cancel button (mirrors lines 67–78).
- `<DataGrid>` with `manualPagination: true` for the memberships list.

**D-3 badge pattern** — add to Период column cell, import `todayMSK` from `@/shared/i18n/date`:
```typescript
import { todayMSK } from '@/shared/i18n/date'
// In the Период column cell:
{m.status === 'active' && m.endDate === todayMSK() && (
  <Badge variant="destructive" className="ml-2 text-xs">
    {t('memberships.badge.expirestoday')}
  </Badge>
)}
```

**Skeleton pattern** (mirrors `ClientsTableSkeleton`):
```typescript
// 3 skeleton rows while loading
Array.from({ length: 3 }).map((_, i) => (
  <div key={i} className="flex gap-4">
    <Skeleton className="h-4 w-32" />
    <Skeleton className="h-4 w-24" />
    <Skeleton className="h-4 w-16" />
  </div>
))
```

---

### `features/memberships/components/SellMembershipDialog.tsx` (component, request-response)

**Analog:** `apps/admin-web/src/features/clients/components/ClientFormDialog.tsx` (lines 1–36) + `ClientForm.tsx` (lines 1–125)

**Dialog shell pattern** (ClientFormDialog.tsx lines 15–36):
```typescript
export function SellMembershipDialog({ open, onClose, clientId }: Props) {
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{t('memberships.dialog.sellTitle')}</DialogTitle>
          <DialogDescription className="sr-only">
            Форма продажи абонемента клиенту
          </DialogDescription>
        </DialogHeader>
        <SellMembershipForm clientId={clientId} onSuccess={onClose} onCancel={onClose} />
      </DialogContent>
    </Dialog>
  )
}
```

**Form + error handling pattern** (ClientForm.tsx lines 27–75):
```typescript
const form = useForm<SellMembershipFormInput>({
  resolver: zodResolver(sellMembershipSchema),
  defaultValues: { planId: '', paidAt: todayMSK(), notes: '' },
})
const handleError = (err: unknown) => {
  const fields = err instanceof ApiError || isDomainError(err) ? err.fields : undefined
  if (fields) {
    for (const [k, v] of Object.entries(fields)) {
      const msg = Array.isArray(v) ? String(v[0] ?? '') : String(v)
      form.setError(k as keyof SellMembershipFormInput, { type: 'server', message: msg })
    }
    return
  }
  form.setError('root', { type: 'server', message: 'Ошибка соединения.' })
}
```

---

### `features/memberships/components/CancelMembershipDialog.tsx` (component, request-response)

**Analog:** `apps/admin-web/src/features/clients/components/ClientFormDialog.tsx` + shadcn `<AlertDialog>`

**Pattern** — uses `<AlertDialog>` not `<Dialog>` (destructive confirmation per UI-SPEC section 5):
```typescript
// AlertDialog (not Dialog) for destructive confirm
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/shared/ui/alert-dialog'
```

The optional reason `<Textarea>` is an inline state outside the AlertDialog's own form. The AlertDialogAction `onClick` (not form submit) calls `useCancelMembership().mutate({...})`.

---

### `features/memberships/model/schema.ts` (utility, transform)

**Analog:** `apps/admin-web/src/features/clients/model/schema.ts` (lines 1–11)

**Pattern** — re-export from `@/entities/membership/schema` (same forwarding indirection):
```typescript
export {
  sellMembershipSchema,
  cancelMembershipSchema,
  membershipsListQuerySchema,
  type SellMembershipFormInput,
  type CancelMembershipFormInput,
  type MembershipsListQueryInput,
} from '@/entities/membership/schema'
```

The actual Zod schemas live in `src/entities/membership/schema.ts` so mock services can import them without crossing the features→shared boundary in reverse.

---

### `features/memberships/index.ts` + `features/visits/index.ts` (config)

**Analog:** `apps/admin-web/src/features/clients/index.ts` (lines 1–9)

**Pattern** — barrel-export page components, keys, and hooks:
```typescript
// features/memberships/index.ts
export { MembershipsListPage } from './components/MembershipsListPage'
export { MembershipPlansPage } from './components/MembershipPlansPage'
export { MembershipsBlock } from './components/MembershipsBlock'
export { membershipsKeys } from './api/keys'
export {
  useMembershipsByClient,
  useMembershipPlans,
  useCreateMembership,
  useCancelMembership,
} from './api/hooks'
```

---

### `routes/_protected/membership-plans.tsx` (route, request-response)

**Analog:** `apps/admin-web/src/routes/_protected/clients.tsx` (lines 1–32) — **verbatim copy** with `resource` changed to `'membership-plans'`

**Owner-only beforeLoad gate** (lines 14–23 — copy verbatim per CONTEXT.md locked ref):
```typescript
import { createFileRoute, redirect } from '@tanstack/react-router'
import { can } from '@/shared/session/can'
import { membershipsKeys } from '@/features/memberships/api/keys'
import { services } from '@/shared/api/services'
import { MembershipPlansPage } from '@/features/memberships/components/MembershipPlansPage'

export const Route = createFileRoute('/_protected/membership-plans')({
  beforeLoad: ({ context, location }) => {
    const { role } = context.getSession()
    if (!can(role, 'view', 'membership-plans')) {
      throw redirect({
        to: '/',
        search: { forbidden: location.pathname + (location.searchStr ?? '') },
      })
    }
  },
  loader: ({ context }) =>
    context.queryClient.ensureQueryData({
      queryKey: membershipsKeys.lists(),
      queryFn: () => services.memberships.listPlans({}),
    }),
  component: MembershipPlansPage,
})
```

---

### `routes/_protected/memberships.tsx` (route, request-response)

**Analog:** `apps/admin-web/src/routes/_protected/clients.tsx` (lines 1–32)

**validateSearch + loaderDeps pattern** (mirrors clients.tsx):
```typescript
const searchSchema = z.object({
  expiring: z.coerce.boolean().optional(),
  page: z.coerce.number().int().min(1).default(1),
  pageSize: z.coerce.number().int().min(10).max(100).default(20),
})

export const Route = createFileRoute('/_protected/memberships')({
  validateSearch: searchSchema,
  loaderDeps: ({ search }) => ({ search }),
  loader: ({ context, deps: { search } }) =>
    context.queryClient.ensureQueryData({
      queryKey: membershipsKeys.list(search),
      queryFn: () => services.memberships.list(search),
    }),
  component: MembershipsListPage,
})
```

---

### `routes/_protected/visits.tsx` (route, request-response)

**Analog:** `apps/admin-web/src/routes/_protected/clients.tsx` + `settings.tsx`

**Pattern** — no search schema (check-in page is stateless), loader fetches gymMeta:
```typescript
export const Route = createFileRoute('/_protected/visits')({
  loader: ({ context }) =>
    context.queryClient.ensureQueryData({
      queryKey: visitsKeys.gymMeta,
      queryFn: () => services.visits.gymMeta(),
    }),
  component: CheckInPage,
})
```

Note: no `beforeLoad` — both roles can check in (`CHECK_IN, VISITS` is NOT in `OWNER_ONLY`).

---

### `routes/_protected/clients.$clientId.tsx` (route, request-response)

**Analog:** `apps/admin-web/src/routes/_protected/clients.tsx` (lines 14–32) for loader pattern

**Pattern α: `Promise.all` loader + stacked layout** (per CONTEXT.md D-22-6):
```typescript
import { createFileRoute } from '@tanstack/react-router'
import { clientsKeys } from '@/features/clients/api/keys'
import { membershipsKeys } from '@/features/memberships/api/keys'
import { visitsKeys } from '@/features/visits/api/keys'
import { services } from '@/shared/api/services'

export const Route = createFileRoute('/_protected/clients/$clientId')({
  loader: ({ context, params }) => {
    const { clientId } = params
    return Promise.all([
      context.queryClient.ensureQueryData({
        queryKey: clientsKeys.detail(clientId as ClientId),
        queryFn: () => services.clients.get(clientId as ClientId),
      }),
      context.queryClient.ensureQueryData({
        queryKey: membershipsKeys.byClient(clientId),
        queryFn: () => services.memberships.byClient(clientId),
      }),
      context.queryClient.ensureQueryData({
        queryKey: visitsKeys.recentByClient(clientId, { limit: 20 }),
        queryFn: () => services.visits.recentByClient(clientId, { limit: 20 }),
      }),
    ])
  },
  component: ClientDetailPage,
})
```

Page layout uses `space-y-8` between blocks (UI-SPEC section 3).

---

### `shared/api/contracts/memberships.ts` (model, —)

**Analog:** `apps/admin-web/src/shared/api/contracts/clients.ts` (lines 1–29)

**Pattern** — typed service interface + input types (copy structure):
```typescript
import type { Membership, MembershipId, MembershipPlan, MembershipPlanId, Pagination } from '@/entities/membership'

export interface MembershipsListQuery {
  page: number
  pageSize: number
  clientId?: string
}

export interface MembershipCreateInput {
  clientId: string
  planId: MembershipPlanId
  paidAt?: string    // ISO date yyyy-MM-dd, defaults to today
  notes?: string
}

export interface MembershipCancelInput {
  reason?: string
}

export interface MembershipsService {
  list(query: MembershipsListQuery): Promise<Pagination<Membership>>
  byClient(clientId: string): Promise<Pagination<Membership>>
  listPlans(query: { page?: number; pageSize?: number }): Promise<Pagination<MembershipPlan>>
  get(id: MembershipId): Promise<Membership>
  create(input: MembershipCreateInput): Promise<Membership>
  cancel(id: MembershipId, reason?: string): Promise<Membership>
}
```

---

### `shared/api/contracts/visits.ts` + `visitsMeta.ts` (model, —)

**Analog:** `apps/admin-web/src/shared/api/contracts/clients.ts`

**visits.ts pattern:**
```typescript
export interface VisitsListQuery {
  page: number
  pageSize: number
  clientId?: string
}

export interface VisitsService {
  list(query: VisitsListQuery): Promise<Pagination<Visit>>
  recentByClient(clientId: string, opts: { limit: number }): Promise<Visit[]>
  checkIn(clientId: string): Promise<Visit>
  gymMeta(): Promise<GymMeta>
  get(id: VisitId): Promise<Visit>
}
```

**visitsMeta.ts pattern** (minimal standalone interface):
```typescript
export interface GymMeta {
  gymHoursStart: string  // HH:MM
  gymHoursEnd: string    // HH:MM
}
```

---

### `shared/api/services/mock/memberships.ts` (service, CRUD)

**Analog:** `apps/admin-web/src/shared/api/services/mock/clients.ts` (lines 1–141)

**Imports pattern** (lines 1–14):
```typescript
import { faker } from '@faker-js/faker'
import type { MembershipsService, MembershipsListQuery, MembershipCreateInput } from '@/shared/api/contracts/memberships'
import type { Membership, MembershipId, Pagination } from '@/entities/membership'
import { DomainError } from '@/shared/api/errors'
import { can } from '@/shared/session/can'
import { useSessionStore } from '@/shared/session/store'
import { loadDB, saveDB } from './_db'
import { delay } from './_latency'
```

**RBAC ensure pattern** (lines 16–24):
```typescript
function role() { return useSessionStore.getState().role }

function ensure(action: 'view' | 'cancel' | 'create', resource: 'memberships' | 'membership-plans') {
  if (!can(role(), action, resource)) {
    throw new DomainError('forbidden', 'Доступ запрещён')
  }
}
```

**D-22-7 READ-ONLY mock — mutation stubs:**
```typescript
export const memberships: MembershipsService = {
  async list(query) {
    await delay()
    ensure('view', 'memberships')
    // ... seeded fixture read from loadDB()
  },
  async create(_input) {
    await delay()
    throw new DomainError(
      'mock_not_implemented',
      'Mock does not implement write paths — use VITE_API_MODE=http',
    )
  },
  async cancel(_id, _reason) {
    await delay()
    throw new DomainError(
      'mock_not_implemented',
      'Mock does not implement write paths — use VITE_API_MODE=http',
    )
  },
}
```

**DB extension** — `_db.ts` must grow `memberships: Membership[]` + `plans: MembershipPlan[]` arrays seeded with `faker`. The `DB` interface extends and `seed()` generates them.

---

### `shared/api/services/mock/visits.ts` (service, request-response)

**Analog:** `apps/admin-web/src/shared/api/services/mock/clients.ts`

Same D-22-7 read-only pattern — `list`, `recentByClient`, `gymMeta` return seeded fixtures; `checkIn` throws `mock_not_implemented`.

**gymMeta** returns a static object (no DB):
```typescript
async gymMeta() {
  await delay()
  return { gymHoursStart: '07:00', gymHoursEnd: '23:00' }
},
```

---

### `shared/api/services/http/memberships.ts` (service, CRUD)

**Analog:** `apps/admin-web/src/shared/api/services/http/clients.ts` (lines 1–64)

**Imports + pattern:**
```typescript
import { request, type components } from '@sportzal/api-client'
import type { MembershipsService, MembershipsListQuery, MembershipCreateInput } from '@/shared/api/contracts/memberships'
import type { MembershipId } from '@/entities/membership'
import { unwrap } from './_envelope'
import { responseToMembership, createInputToRequest } from './_membershipsAdapter'

export const memberships: MembershipsService = {
  async list(query) {
    const q: Record<string, string | number> = { page: query.page, pageSize: query.pageSize }
    if (query.clientId) q.clientId = query.clientId
    const raw = unwrap<PaginatedMembershipResponse>(
      await request('get', '/api/v1/memberships', { query: q }),
    )
    return { ...raw, items: raw.items.map(responseToMembership) }
  },
  async cancel(id, reason) {
    const raw = unwrap<MembershipResponse>(
      await request('post', '/api/v1/memberships/{membership_id}/cancel', {
        params: { membership_id: id },
        body: reason ? { reason } : {},
      }),
    )
    return responseToMembership(raw)
  },
}
```

---

### `shared/api/services/http/_membershipsAdapter.ts` + `_visitsAdapter.ts` (utility, transform)

**Analog:** `apps/admin-web/src/shared/api/services/http/_clientsAdapter.ts` (lines 1–94)

**Pattern** — pure mapping helpers between `components['schemas']['MembershipResponse']` and FE `Membership` domain type. Docblock explaining why the module exists (same as `_clientsAdapter.ts` lines 1–15).

**Key differences from clients adapter:**
- Membership: `endDate` field is INCLUSIVE (no transformation — pass through as-is).
- Money: `priceKopecks` comes from backend as integer; map to FE `Money` type or keep as `number`.
- `status` is an enum string — map to FE union `'active' | 'expired' | 'cancelled'`.

**Visits adapter** — simpler (no field renames needed if camelCase matches):
```typescript
import type { components } from '@sportzal/api-client'
import type { Visit, VisitId } from '@/entities/visit'
type VisitResponse = components['schemas']['VisitResponse']

export function responseToVisit(r: VisitResponse): Visit {
  return {
    id: r.id as VisitId,
    clientId: r.clientId,
    membershipId: r.membershipId,
    checkedInAt: r.checkedInAt,
    gymDate: r.gymDate,
    channel: r.channel as Visit['channel'],
  }
}
```

---

### `shared/api/services/mock/index.ts` + `shared/api/services/http/index.ts` (modify)

**Analog:** existing files (lines 10–13)

**Pattern** — append `memberships` and `visits` to the services const:
```typescript
// mock/index.ts
import { auth } from './auth'
import { clients } from './clients'
import { memberships } from './memberships'
import { visits } from './visits'

export const services = { auth, clients, memberships, visits } as const
```

Same shape for `http/index.ts`.

---

### `shared/session/registry.ts` (modify)

**Analog:** existing file (lines 26–56)

**navKey type extension** (line 34):
```typescript
navKey: 'home' | 'clients' | 'schedule' | 'staff' | 'finance' | 'settings'
  | 'visits' | 'memberships' | 'membershipPlans'  // NEW Phase 22
```

**New routeRegistry entries** (insert after `/` entry at position 2, then after `/clients` at positions 4–5):
```typescript
{ path: '/visits', resource: 'visits', label: 'Отметки', icon: 'LogIn', navKey: 'visits' },
// ...existing /clients entry...
{ path: '/memberships', resource: 'memberships', label: 'Абонементы', icon: 'Ticket', navKey: 'memberships' },
{ path: '/membership-plans', resource: 'membership-plans', label: 'Тарифы', icon: 'LayoutGrid', navKey: 'membershipPlans' },
```

---

### `features/clients/components/ClientsTable.tsx` (modify, D-22-5)

**Analog:** existing file (lines 28–111)

**Row-click navigation pattern** — add `useNavigate` (already imported) + row `onClick`:
```typescript
// In the column definitions or on the <tr> rendered by DataGridTable:
// Option A: wrap row in Link (preferred for accessibility)
// Option B: onRowClick prop
// Since DataGrid/DataGridTable exposes table instance, use onRowClick callback or
// pass a custom rowProps to DataGridTable that wraps onClick + Link.

// The row click handler (add to the table instance options or DataGridTable prop):
onRowClick: (row: Row<Client>) => {
  void navigate({ to: '/clients/$clientId', params: { clientId: row.original.id } })
}
```

**stopPropagation on action buttons** (lines 58–78 — add to both edit and delete button onClick):
```typescript
onClick={(e) => { e.stopPropagation(); onEdit(client) }}
onClick={(e) => { e.stopPropagation(); onDelete(client) }}
```

**Row cursor style** (add to row's className):
```typescript
className="cursor-pointer hover:bg-muted/50"
```

---

### `eslint.config.js` (modify, D-22-12)

**Analog:** existing file (lines 48–69)

**New zone** — append to the `zones` array inside the `'import/no-restricted-paths'` rule:
```javascript
{
  target: ['./src/features/clients/**'],
  from: ['./src/features/memberships/**', './src/features/visits/**'],
  message:
    'Pattern α: features/clients must not import features/memberships or features/visits. Compose at the route level (clients.$clientId.tsx).',
},
```

**New shadcn files to add to the `react-refresh/only-export-components: off` block** (lines 130–154) — add once `badge.tsx`, `textarea.tsx`, `alert.tsx`, `card.tsx` are installed via `npx shadcn add`.

---

### `__fixtures/features/illegal-cross-feature-import.ts` (test)

**Analog:** `apps/admin-web/src/__fixtures/features/illegal-mock-import.ts` (lines 1–5)

**Pattern** (copy verbatim, swap imports):
```typescript
// FIXTURE: must trigger `import/no-restricted-paths` Pattern α zone.
import { MembershipsBlock } from '@/features/memberships'
import { RecentVisitsBlock } from '@/features/visits'

export const illegal = { MembershipsBlock, RecentVisitsBlock }
```

---

### `features/clients/components/ClientsTable.rbac.test.tsx` (modify)

**Analog:** existing file (lines 1–60)

**Navigation assertion to add:**
```typescript
import userEvent from '@testing-library/user-event'
import { expect, vi } from 'vitest'

// Mock useNavigate
const mockNavigate = vi.fn()
vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return { ...actual, useNavigate: () => mockNavigate }
})

it('navigates to /clients/$clientId on row click', async () => {
  renderWithProviders(<ClientsTable {...props()} />, { role: 'owner' })
  await userEvent.click(screen.getByText('Тест Тест'))
  expect(mockNavigate).toHaveBeenCalledWith(
    expect.objectContaining({ to: '/clients/$clientId', params: { clientId: sample[0]!.id } }),
  )
})

it('does not navigate on Pencil button click (stopPropagation)', async () => {
  const onEdit = vi.fn()
  renderWithProviders(<ClientsTable {...props()} onEdit={onEdit} />, { role: 'owner' })
  await userEvent.click(screen.getByLabelText('Редактировать клиента'))
  expect(mockNavigate).not.toHaveBeenCalled()
  expect(onEdit).toHaveBeenCalledWith(sample[0])
})
```

---

### `packages/api-client/src/schema.contract.test.ts` (modify)

**Analog:** existing file (lines 44–73)

**New assertion to add** (after line 44, extend `_checks` tuple + array):
```typescript
// Add to the v1.2 surface section:
type _VisitsMetaGet = AssertNonNever<paths['/api/v1/visits/_meta']['get']>

// Add to the _checks tuple type:
_VisitsMetaGet,
// Add to the _checks array:
true,
// Update expect(_checks).toHaveLength(9) → toHaveLength(10)
```

---

### `shared/i18n/date.ts` (modify)

**Analog:** existing file (lines 1–27)

**Add `todayMSK` helper** (UI-SPEC section 9 — not present in current file):
```typescript
// After existing exports, add:
export function todayMSK(): string {
  // Returns today's date in YYYY-MM-DD format pinned to Europe/Moscow timezone.
  // Uses sv-SE locale which produces ISO YYYY-MM-DD format natively.
  return new Intl.DateTimeFormat('sv-SE', { timeZone: MOSCOW_TZ }).format(new Date())
}
```

`MOSCOW_TZ` is already exported from line 8: `export const MOSCOW_TZ = 'Europe/Moscow'`.

---

### `shared/i18n/ru.ts` (modify)

**Analog:** existing file (lines 1–60+)

**Pattern** — append new top-level keys at the end of the `ru` object (matching the existing style):
```typescript
export const ru = {
  // ...existing keys...
  shell: {
    // extend nav:
    nav: {
      // ...existing...
      visits: 'Отметки',
      memberships: 'Абонементы',
      membershipPlans: 'Тарифы',
    },
  },
  memberships: {
    heading: 'Абонементы',
    // ...all new keys per UI-SPEC copywriting contract...
  },
  membershipPlans: { /* ... */ },
  visits: { /* ... */ },
  sessions: { /* ... */ },
  clientProfile: { /* ... */ },
}
```

Full key list is in UI-SPEC sections "New `memberships` domain keys" through "`clientProfile` keys".

---

### `backend/app/modules/visits/router.py` (modify, D-22-1)

**Analog:** existing file (lines 36–107) — the existing GET endpoints

**New `_meta` endpoint** — append after the existing `get_visit` function. Pattern mirrors the existing `list_visits` GET handler:
```python
from app.modules.visits.schemas import VisitsMetaResponse

@router.get(
    "/_meta",
    response_model=ResponseEnvelope[VisitsMetaResponse],
    summary="Gym hours metadata (cacheable 5 min)",
)
async def get_visits_meta(
    _actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.VIEW, Resource.VISITS)),
    ],
) -> ResponseEnvelope[VisitsMetaResponse]:
    """Returns gym hours window. Reception+owner. Cache-Control: public, max-age=300.
    No DB access — reads Settings from lru_cache."""
    from fastapi.responses import Response
    settings = get_settings()
    meta = VisitsMetaResponse(
        gym_hours_start=settings.gym_hours_start.isoformat()[:5],
        gym_hours_end=settings.gym_hours_end.isoformat()[:5],
    )
    # NOTE: FastAPI does not set Cache-Control automatically; use Response header injection
    # via middleware or return a Response directly. Plan-phase decides mechanism.
    return envelope(meta)
```

**IMPORTANT:** `/_meta` must be registered BEFORE `/{visit_id}` in the router to avoid path collision. Add it before the `/{visit_id}` GET handler.

---

### `backend/app/modules/visits/schemas.py` (modify)

**Analog:** existing `VisitResponse` class (lines 36–59)

**New Pydantic model to add:**
```python
class VisitsMetaResponse(BackendSchemaBase):
    """GET /api/v1/visits/_meta response (Phase 22 D-22-1).

    Returns gym hours window as HH:MM strings. Serialises from Settings
    (lru_cache) — no DB access. Cache-Control: public, max-age=300.
    """
    gym_hours_start: str  # HH:MM, e.g. "07:00"
    gym_hours_end: str    # HH:MM, e.g. "23:00"
```

`BackendSchemaBase` is already imported (line 22); `camelCase alias_generator` means the wire names are `gymHoursStart` and `gymHoursEnd` — matching `schema.d.ts` consumer expectation.

---

### `backend/app/integrations/telegram/handlers.py` (modify, D-22-11)

**Analog:** existing file (lines 77–80 — locked DM constants) + lines 318–322 (happy path send)

**D-5 tweak** — extend `_DM_CHECKIN_OK` to include days remaining:
```python
# BEFORE (line 77):
_DM_CHECKIN_OK = "✅ Отмечено"

# AFTER (owner sign-off required per Phase 20 precedent):
_DM_CHECKIN_OK = "✅ Отмечено. Абонемент действует ещё {days_remaining} дн."
```

The handler's happy path (lines 318–320) must compute `days_remaining` from the returned `visit` object. The `visit` returned by `create_visit_self_checkin` includes `membership_id`; the handler needs access to `end_date`. Options:
1. Extend the `VisitResponse` schema to include `membershipEndDate` — plan-phase decides.
2. Have the service return a `(visit, membership)` tuple — simpler but changes service signature.
3. Do a second DB read in the handler (violates integrations perp modules if it hits the DB directly).

**Recommended approach** (plan-phase decides): extend `VisitResponse` with `membershipEndDate: date` (or pass it back via a new `CheckinResult` named tuple from the service). The handler then computes:
```python
days_remaining = (visit.membership_end_date - _today_msk()).days
await ctx.sender.send_text_dm(bot, chat_id, _DM_CHECKIN_OK.format(days_remaining=days_remaining))
```

---

### `features/auth/components/SessionsList.tsx` + `features/auth/api/sessionsHooks.ts` (FE-09, blocked on Phase 23)

**Analog:** `apps/admin-web/src/features/auth/api/hooks.ts` (lines 1–59) + `ClientsTable.tsx` for list component

**sessionsHooks.ts pattern** (mirrors `useLogout` mutation pattern + `useMe` query pattern):
```typescript
export function useActiveSessions() {
  return useQuery({
    queryKey: authKeys.sessions,        // extend authKeys with sessions entry
    queryFn: () => services.auth.sessions(),
    staleTime: 30_000,
  })
}

export function useRevokeSession() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (familyId: string) => services.auth.revokeSession(familyId),
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: authKeys.sessions })
    },
  })
}

export function useLogoutAll() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => services.auth.logoutAll(),
    onSuccess: () => { qc.clear() },
  })
}
```

**SessionsList.tsx** — renders list from `useActiveSessions()`, skeleton while loading (3 rows), empty state, "Отозвать" ghost button with `<RoleGate>` not needed (sessions are own-account, not RBAC-gated), "Выйти со всех устройств" via `<AlertDialog>` pattern.

---

## Shared Patterns

### Authentication / RBAC Gate
**Source:** `apps/admin-web/src/shared/session/RoleGate.tsx` (lines 1–17) + `can.ts` (lines 31–35)
**Apply to:** `MembershipsBlock.tsx` (Cancel button), `MembershipPlansPage.tsx` (all write actions), `CancelMembershipDialog.tsx`
```typescript
import { RoleGate } from '@/shared/session/RoleGate'
// In JSX:
<RoleGate action="cancel" resource="memberships">
  <Button variant="ghost" size="sm" className="text-destructive">Отменить</Button>
</RoleGate>
```

### Swap-Seam Extension
**Source:** `apps/admin-web/src/shared/api/services/mock/index.ts` (line 13) + `http/index.ts` (line 13)
**Apply to:** Both index files
```typescript
export const services = { auth, clients, memberships, visits } as const
```

### Error Handling in Forms
**Source:** `apps/admin-web/src/features/clients/components/ClientForm.tsx` (lines 44–58)
**Apply to:** `SellMembershipDialog.tsx`, `CheckInPage.tsx`
```typescript
const handleError = (err: unknown) => {
  const fields = err instanceof ApiError || isDomainError(err) ? err.fields : undefined
  if (fields) {
    for (const [k, v] of Object.entries(fields)) {
      const msg = Array.isArray(v) ? String(v[0] ?? '') : String(v)
      form.setError(k as keyof FormInput, { type: 'server', message: msg })
    }
    return
  }
  form.setError('root', { type: 'server', message: 'Ошибка соединения.' })
}
```

### Mock Latency + RBAC Enforcement
**Source:** `apps/admin-web/src/shared/api/services/mock/clients.ts` (lines 16–24, 36–39)
**Apply to:** All new mock service files (`memberships.ts`, `visits.ts`)
```typescript
function role() { return useSessionStore.getState().role }
function ensure(action: Action, resource: Resource) {
  if (!can(role(), action, resource)) throw new DomainError('forbidden', 'Доступ запрещён')
}
// In every read method:
async list(query) {
  await delay()
  ensure('view', 'memberships')
  // ...
}
```

### Envelope Unwrap in HTTP Services
**Source:** `apps/admin-web/src/shared/api/services/http/_envelope.ts` (lines 13–19)
**Apply to:** `http/memberships.ts`, `http/visits.ts`
```typescript
import { unwrap } from './_envelope'
// In every method: const raw = unwrap<T>(await request(...))
```

### Route Loader with `ensureQueryData`
**Source:** `apps/admin-web/src/routes/_protected/clients.tsx` (lines 25–31)
**Apply to:** All new route files
```typescript
loader: ({ context, deps: { search } }) =>
  context.queryClient.ensureQueryData({
    queryKey: someKeys.list(search),       // SAME key as the consuming hook
    queryFn: () => services.X.list(search),
  }),
```

### Backend `ResponseEnvelope` Pattern
**Source:** `apps/backend/app/modules/visits/router.py` (lines 39–54)
**Apply to:** New `/visits/_meta` GET handler
```python
from app.core.schemas import ResponseEnvelope, envelope
# Return:
return envelope(meta)
```

### Mock Test RBAC Pattern
**Source:** `apps/admin-web/src/shared/api/services/mock/clients.rbac.test.ts` (lines 1–45)
**Apply to:** New `memberships.read.test.ts`, `visits.read.test.ts`
```typescript
import { describe, it, expect, beforeEach } from 'vitest'
import { useSessionStore } from '@/shared/session/store'
import { isDomainError } from '@/shared/api/errors'

describe('mock/memberships RBAC', () => {
  beforeEach(() => { resetDB() })

  it('forbids reception from calling owner-only mock read paths', async () => {
    useSessionStore.setState({ role: 'reception' })
    let caught: unknown
    try { await memberships.listPlans({}) } catch (e) { caught = e }
    expect(isDomainError(caught)).toBe(true)
    if (isDomainError(caught)) expect(caught.code).toBe('forbidden')
  })

  it('throws mock_not_implemented on create', async () => {
    useSessionStore.setState({ role: 'owner' })
    let caught: unknown
    try { await memberships.create({ clientId: 'x', planId: 'y' as MembershipPlanId }) } catch (e) { caught = e }
    expect(isDomainError(caught)).toBe(true)
    if (isDomainError(caught)) expect(caught.code).toBe('mock_not_implemented')
  })
})
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `features/visits/components/CheckInPage.tsx` | component | request-response | No search-with-disambiguation pattern exists yet in the codebase; closest is `ClientsTable` for list rendering + `ClientForm` for mutation handling — partial only. Plan should combine both. |
| `backend/app/modules/visits/schemas.py:VisitsMetaResponse` | model | — | Simple new Pydantic schema with no precedent for a "meta/config" endpoint; analog is `VisitResponse` for structure but this is read-from-Settings not DB. |

---

## Metadata

**Analog search scope:** `apps/admin-web/src/features/`, `apps/admin-web/src/routes/_protected/`, `apps/admin-web/src/shared/api/`, `apps/admin-web/src/shared/session/`, `apps/admin-web/src/shared/i18n/`, `apps/backend/app/modules/visits/`, `apps/backend/app/integrations/telegram/`, `packages/api-client/src/`
**Files scanned:** 32 source files read
**Pattern extraction date:** 2026-05-08
