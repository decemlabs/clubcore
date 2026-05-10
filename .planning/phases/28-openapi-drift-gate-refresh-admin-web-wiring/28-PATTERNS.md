# Phase 28: OpenAPI Drift-Gate Refresh + admin-web Wiring — Pattern Map

**Mapped:** 2026-05-10
**Files analyzed:** 17 new/modified files
**Analogs found:** 15 / 17

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/backend/openapi.json` | generated | batch | `apps/backend/scripts/export_openapi.py` | exact |
| `packages/api-client/src/schema.d.ts` | generated | batch | codegen script in `packages/api-client/package.json` | exact |
| `apps/admin-web/src/entities/membership/types.ts` | type | transform | self (extend existing) | exact |
| `apps/admin-web/src/entities/membership/index.ts` | type | transform | self (extend existing) | exact |
| `apps/admin-web/src/shared/api/contracts/memberships.ts` | contract | request-response | self (extend existing) | exact |
| `apps/admin-web/src/shared/api/services/http/memberships.ts` | service-impl | request-response | `cancel()` method in same file (lines 96-104) | exact |
| `apps/admin-web/src/shared/api/services/http/_membershipsAdapter.ts` | service-impl | transform | `responseToMembership` in same file (lines 42-60) | exact |
| `apps/admin-web/src/shared/api/services/mock/memberships.ts` | service-impl | request-response | `memberships.list()` in same file (lines 29-57) | exact |
| `apps/admin-web/src/shared/api/services/mock/memberships.freeze.test.ts` | test | CRUD | `memberships.expiring.test.ts` | exact |
| `apps/admin-web/src/shared/api/services/mock/memberships.renew.test.ts` | test | CRUD | `memberships.expiring.test.ts` | exact |
| `apps/admin-web/src/features/memberships/api/hooks.ts` | hook | request-response | `useCancelMembership` in same file (lines 71-100) | exact |
| `apps/admin-web/src/features/memberships/api/keys.ts` | hook | request-response | self (verify `detail(id)` exists — confirmed line 9) | exact |
| `apps/admin-web/src/routes/_protected/memberships_.$membershipId.tsx` | route | request-response | `clients_.$clientId.tsx` | exact |
| `apps/admin-web/src/routes/_protected/memberships.tsx` | route | request-response | self (extend existing) | exact |
| `apps/admin-web/src/features/memberships/components/StatusBadge.tsx` | component | transform | inline `StatusBadge` in `MembershipsListPage.tsx` (lines 26-31) | exact |
| `apps/admin-web/src/features/memberships/components/FreezeSection.tsx` etc. | component | request-response | `CancelMembershipDialog.tsx` + `MembershipsBlock.tsx` | role-match |
| `apps/admin-web/src/shared/i18n/ru.ts` | i18n | transform | self (extend existing `memberships` namespace, lines 143-212) | exact |

---

## Pattern Assignments

### `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` (generated, batch)

**Pattern:** Single-regen-cycle discipline — no FE code changes until both artifacts are committed.

**Regen commands:**
```bash
# Step 1: from apps/backend/
uv run python -m scripts.export_openapi
# Step 2: from repo root
pnpm --filter @sportzal/api-client codegen
```

**CI gate** (`.github/workflows/ci.yml` lines 49-64, 100-117):
```bash
git diff --exit-code apps/backend/openapi.json
git diff --exit-code packages/api-client/src/schema.d.ts
```

---

### `apps/admin-web/src/entities/membership/types.ts` (type, transform)

**Analog:** Self — extend existing `types.ts` (lines 1-42)

**Current shape** (lines 1-42):
```typescript
import type { Brand } from '@/shared/lib/brand'

export type MembershipId = Brand<string, 'MembershipId'>
export type MembershipPlanId = Brand<string, 'MembershipPlanId'>
export type MembershipStatus = 'active' | 'expired' | 'cancelled'

export interface Membership {
  id: MembershipId
  clientId: string
  // ... existing fields ...
  cancelledAt?: string | null
  cancelReason?: string | null
  createdAt: string
  updatedAt: string
}
```

**Extension target:**
```typescript
// Extend MembershipStatus at line 5:
export type MembershipStatus = 'active' | 'expired' | 'cancelled' | 'frozen'

// New nested type — add before Membership interface:
export interface FreezePeriod {
  id: string
  startedAt: string      // ISO datetime
  startedBy: string      // user ID
  endedAt: string | null
  endedBy: string | null
}

// Add to Membership interface (after cancelReason):
freezeDaysLimitSnapshot: number
freezeDaysUsed: number
freezeDaysRemaining: number        // max(limit - used, 0), server-computed
currentFreezePeriod: FreezePeriod | null  // null when status !== 'frozen'
previousMembershipId?: string | null      // renewal chain attribution
```

---

### `apps/admin-web/src/entities/membership/index.ts` (type, transform)

**Analog:** Self — extend existing re-exports (lines 1-21)

**Extension target** — add `FreezePeriod` to the type export line:
```typescript
export type {
  Membership,
  FreezePeriod,    // NEW
  MembershipId,
  MembershipPlan,
  MembershipPlanId,
  MembershipStatus,
  Pagination,
} from './types'
// existing schema exports stay unchanged
```

---

### `apps/admin-web/src/shared/api/contracts/memberships.ts` (contract, request-response)

**Analog:** Self — extend `MembershipsService` interface (lines 43-55)

**Current interface tail** (lines 43-55):
```typescript
export interface MembershipsService {
  list(query: MembershipsListQuery): Promise<Pagination<Membership>>
  byClient(clientId: string): Promise<Pagination<Membership>>
  get(id: MembershipId): Promise<Membership>
  create(input: MembershipCreateInput): Promise<Membership>
  cancel(id: MembershipId, reason?: string): Promise<Membership>
  // Plans ...
  listPlans(query: MembershipPlansListQuery): Promise<Pagination<MembershipPlan>>
  getPlan(id: MembershipPlanId): Promise<MembershipPlan>
  createPlan(input: MembershipPlanCreateInput): Promise<MembershipPlan>
  updatePlan(id: MembershipPlanId, input: MembershipPlanUpdateInput): Promise<MembershipPlan>
  deletePlan(id: MembershipPlanId): Promise<void>
}
```

**Extension — add after `cancel`:**
```typescript
freeze(id: MembershipId): Promise<Membership>    // 200; updated source membership
unfreeze(id: MembershipId): Promise<Membership>  // 200; updated source membership
renew(id: MembershipId): Promise<Membership>     // 201; the NEW membership (chain child)
```

Also extend `MembershipsListQuery` — add `status?`:
```typescript
export interface MembershipsListQuery {
  page: number
  pageSize: number
  clientId?: string
  status?: MembershipStatus    // NEW — forwarded as ?status=frozen filter
  expiring?: boolean
  within?: number
}
```

---

### `apps/admin-web/src/shared/api/services/http/memberships.ts` (service-impl, request-response)

**Analog:** `cancel()` method (lines 96-104) — same `request + unwrap + responseToMembership` envelope

**Pattern to copy** (lines 96-104):
```typescript
async cancel(id: MembershipId, reason?: string) {
  const raw = unwrap<MembershipResponse>(
    await request('post', '/api/v1/memberships/{membership_id}/cancel', {
      params: { membership_id: id },
      body: reason ? { reason } : {},
    }),
  )
  return responseToMembership(raw)
},
```

**New methods — apply the same `request + unwrap + responseToMembership` pattern:**
```typescript
async freeze(id: MembershipId) {
  const raw = unwrap<MembershipResponse>(
    await request('post', '/api/v1/memberships/{membership_id}/freeze', {
      params: { membership_id: id },
    }),
  )
  return responseToMembership(raw)
},

async unfreeze(id: MembershipId) {
  const raw = unwrap<MembershipResponse>(
    await request('post', '/api/v1/memberships/{membership_id}/unfreeze', {
      params: { membership_id: id },
    }),
  )
  return responseToMembership(raw)
},

async renew(id: MembershipId) {
  const raw = unwrap<MembershipResponse>(
    await request('post', '/api/v1/memberships/{membership_id}/renew', {
      params: { membership_id: id },
    }),
  )
  return responseToMembership(raw)
},
```

Also extend `list()` to forward the new `status?` filter:
```typescript
// Inside list(), after `if (query.expiring)` block:
if (query.status) q.status = query.status
```

---

### `apps/admin-web/src/shared/api/services/http/_membershipsAdapter.ts` (service-impl, transform)

**Analog:** `responseToMembership` function (lines 42-60) — pure field mapping with branding

**Current function** (lines 42-60):
```typescript
export function responseToMembership(r: MembershipResponse): Membership {
  return {
    id: r.id as MembershipId,
    clientId: r.clientId,
    planId: r.planId as MembershipPlanId,
    planNameSnapshot: r.planNameSnapshot,
    durationDaysSnapshot: r.durationDaysSnapshot,
    priceKopecksSnapshot: r.priceKopecksSnapshot,
    startDate: r.startDate,
    endDate: r.endDate,
    status: r.status as MembershipStatus,
    paidAt: r.paidAt ?? null,
    notes: r.notes ?? null,
    cancelledAt: r.cancelledAt ?? null,
    cancelReason: r.cancelReason ?? null,
    createdAt: r.createdAt,
    updatedAt: r.updatedAt,
  }
}
```

**Extension — add new fields at bottom of return object:**
```typescript
// New fields (backend already camelCase via BackendSchemaBase — direct assignment):
freezeDaysLimitSnapshot: r.freezeDaysLimitSnapshot,
freezeDaysUsed: r.freezeDaysUsed,
freezeDaysRemaining: r.freezeDaysRemaining,
currentFreezePeriod: r.currentFreezePeriod
  ? {
      id: r.currentFreezePeriod.id,
      startedAt: r.currentFreezePeriod.startedAt,
      startedBy: r.currentFreezePeriod.startedBy,
      endedAt: r.currentFreezePeriod.endedAt ?? null,
      endedBy: r.currentFreezePeriod.endedBy ?? null,
    }
  : null,
previousMembershipId: r.previousMembershipId ?? null,
```

**Note:** Backend field name is `currentFreezePeriod` (already camelCase via `BackendSchemaBase`); no snake_case conversion needed. The `?? null` pattern mirrors existing nullable field handling (`paidAt`, `notes`, etc.).

---

### `apps/admin-web/src/shared/api/services/mock/memberships.ts` (service-impl, CRUD)

**Analog:** `list()` and `get()` in same file (lines 29-80) — `delay()` + `ensure()` + `loadDB()` + `DomainError` pattern

**Current guard + DB access pattern** (lines 18-27, 74-80):
```typescript
function role() {
  return useSessionStore.getState().role
}

function ensure(action: Action, resource: Resource) {
  if (!can(role(), action, resource)) {
    throw new DomainError('forbidden', 'Доступ запрещён')
  }
}

// In each method:
async get(id: MembershipId): Promise<Membership> {
  await delay()
  ensure('view', 'memberships')
  const db = loadDB()
  const found = db.memberships.find((m) => m.id === id)
  if (!found) throw new DomainError('not_found', 'Абонемент не найден')
  return found
},
```

**Pattern for `freeze` method:**
```typescript
async freeze(id: MembershipId): Promise<Membership> {
  await delay()
  ensure('create', 'memberships')
  const db = loadDB()
  const idx = db.memberships.findIndex((m) => m.id === id)
  if (idx === -1) throw new DomainError('not_found', 'Абонемент не найден')
  const m = db.memberships[idx]!
  if (m.status === 'frozen') throw new DomainError('already_frozen', 'Абонемент уже заморожен.')
  if (m.status !== 'active') throw new DomainError('invalid_transition', 'Нельзя заморозить: статус абонемента не позволяет это действие.')
  if (m.freezeDaysRemaining <= 0) throw new DomainError('freeze_limit_exceeded', 'Лимит дней заморозки исчерпан.')
  const now = new Date().toISOString()
  const updated: Membership = {
    ...m,
    status: 'frozen',
    currentFreezePeriod: {
      id: faker.string.uuid(),
      startedAt: now,
      startedBy: role(),    // actor ID; role string as proxy in mock
      endedAt: null,
      endedBy: null,
    },
    updatedAt: now,
  }
  db.memberships[idx] = updated
  saveDB(db)
  return updated
},
```

**Pattern for `renew` method** (creates new row, returns new membership):
```typescript
async renew(id: MembershipId): Promise<Membership> {
  await delay()
  ensure('create', 'memberships')
  const db = loadDB()
  const source = db.memberships.find((m) => m.id === id)
  if (!source) throw new DomainError('not_found', 'Абонемент не найден')
  if (source.status === 'cancelled') throw new DomainError('cannot_renew_cancelled', 'Нельзя продлить отменённый абонемент.')
  const plan = db.plans.find((p) => p.id === source.planId)
  if (!plan || !plan.active) throw new DomainError('plan_archived', 'Тариф архивирован — продление недоступно.')
  // date computation: max(todayMSK, currentEndDate + 1)
  const today = todayMSK()
  const afterEnd = new Date(source.endDate)
  afterEnd.setUTCDate(afterEnd.getUTCDate() + 1)
  const afterEndStr = afterEnd.toISOString().slice(0, 10)
  const newStart = afterEndStr > today ? afterEndStr : today
  const newEndDate = new Date(newStart)
  newEndDate.setUTCDate(newEndDate.getUTCDate() + source.durationDaysSnapshot - 1)
  const now = new Date().toISOString()
  const newMembership: Membership = {
    ...source,
    id: faker.string.uuid() as MembershipId,
    startDate: newStart,
    endDate: newEndDate.toISOString().slice(0, 10),
    status: 'active',
    previousMembershipId: source.id,
    currentFreezePeriod: null,
    freezeDaysUsed: 0,
    freezeDaysRemaining: source.freezeDaysLimitSnapshot,
    cancelledAt: null,
    cancelReason: null,
    paidAt: now,
    createdAt: now,
    updatedAt: now,
  }
  db.memberships.push(newMembership)
  saveDB(db)
  return newMembership
},
```

**Note on mock DB seed:** `generateMembership` in `_db.ts` must be extended to initialize the new fields:
```typescript
// Add to the returned object in generateMembership():
freezeDaysLimitSnapshot: Math.round(plan.durationDays / 7),  // sensible default ~4-52 days
freezeDaysUsed: 0,
freezeDaysRemaining: Math.round(plan.durationDays / 7),
currentFreezePeriod: null,
previousMembershipId: null,
```

---

### `apps/admin-web/src/shared/api/services/mock/memberships.freeze.test.ts` (test, CRUD)

**Analog:** `memberships.expiring.test.ts` (entire file, lines 1-133) — exact file structure, scaffolding, and naming to mirror

**File structure to copy** (from `memberships.expiring.test.ts`):
```typescript
import { describe, it, expect, beforeEach } from 'vitest'
import { useSessionStore } from '@/shared/session/store'
import { memberships } from './memberships'
import { resetDB, loadDB, saveDB } from './_db'
import type { Membership } from '@/entities/membership'

/**
 * Phase 28 mock service freeze/unfreeze parity tests.
 * Backend error codes: Phase 25 router.py lines 354-355.
 */

function injectMembership(partial: Partial<Membership> & Pick<Membership, 'id' | 'status'>) {
  const db = loadDB()
  const seed = db.memberships[0]
  if (!seed) throw new Error('mock DB has no memberships seed')
  const fixture: Membership = { ...seed, ...partial }
  db.memberships.push(fixture)
  saveDB(db)
}

describe('mock/memberships freeze parity', () => {
  beforeEach(() => {
    resetDB()
    useSessionStore.setState({ role: 'owner' })
  })

  it('freeze transitions active → frozen and sets currentFreezePeriod', async () => { ... })
  it('freeze throws already_frozen when status=frozen', async () => { ... })
  it('freeze throws invalid_transition when status=expired', async () => { ... })
  it('freeze throws freeze_limit_exceeded when freezeDaysRemaining === 0', async () => { ... })
  it('unfreeze transitions frozen → active and extends endDate', async () => { ... })
  it('unfreeze throws invalid_transition when status=active', async () => { ... })
  it('reception can freeze (CREATE MEMBERSHIPS is not owner-only)', async () => { ... })
})
```

**`injectMembership` pattern** (mirrors `memberships.expiring.test.ts` lines 28-43):
```typescript
function injectMembership(partial: Partial<Membership> & Pick<Membership, 'id' | 'status'>) {
  const db = loadDB()
  const seed = db.memberships[0]
  if (!seed) throw new Error('mock DB has no memberships seed — cannot fabricate fixture')
  const fixture: Membership = { ...seed, ...partial }
  db.memberships.push(fixture)
  saveDB(db)
}
```

**Error assertion pattern** (use `expect(...).rejects.toMatchObject`):
```typescript
await expect(memberships.freeze('nonexistent-id' as MembershipId)).rejects.toMatchObject({
  code: 'not_found',
})
```

---

### `apps/admin-web/src/shared/api/services/mock/memberships.renew.test.ts` (test, CRUD)

**Analog:** `memberships.expiring.test.ts` — same scaffolding; focus on renew-specific scenarios:
```typescript
describe('mock/memberships renew parity', () => {
  it('renew creates a new membership with previousMembershipId pointing to source', async () => { ... })
  it('renew new start date = max(today, sourceEndDate + 1)', async () => { ... })
  it('renew throws cannot_renew_cancelled when source is cancelled', async () => { ... })
  it('renew throws plan_archived when source plan is not active', async () => { ... })
  it('renew resets freeze counters on the new membership', async () => { ... })
})
```

---

### `apps/admin-web/src/features/memberships/api/hooks.ts` (hook, request-response)

**Analog:** `useCancelMembership` (lines 71-100) — the complete optimistic pattern to mirror

**`useCancelMembership` pattern** (lines 71-100 — full copy target):
```typescript
type CancelVars = { membershipId: MembershipId; reason?: string }

export function useCancelMembership() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ membershipId, reason }: CancelVars) =>
      services.memberships.cancel(membershipId, reason),
    onMutate: async ({ membershipId }) => {
      await qc.cancelQueries({ queryKey: membershipsKeys.lists() })
      const snapshots = qc.getQueriesData<Pagination<Membership>>({
        queryKey: membershipsKeys.lists(),
      })
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

**`useFreezeMembership` — mirrors the above with detail-cache too:**
```typescript
type FreezeVars = { membershipId: MembershipId; clientId: string }

export function useFreezeMembership() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ membershipId }: FreezeVars) => services.memberships.freeze(membershipId),
    onMutate: async ({ membershipId }) => {
      // Cancel in-flight queries for both lists and the specific detail
      await qc.cancelQueries({ queryKey: membershipsKeys.lists() })
      await qc.cancelQueries({ queryKey: membershipsKeys.detail(membershipId) })
      // Snapshot list caches
      const listSnapshots = qc.getQueriesData<Pagination<Membership>>({
        queryKey: membershipsKeys.lists(),
      })
      // Snapshot detail cache
      const detailSnapshot = qc.getQueryData<Membership>(membershipsKeys.detail(membershipId))
      // Optimistically patch lists
      for (const [key, data] of listSnapshots) {
        if (!data) continue
        qc.setQueryData<Pagination<Membership>>(key, {
          ...data,
          items: data.items.map((m) =>
            m.id === membershipId
              ? { ...m, status: 'frozen', currentFreezePeriod: { id: 'optimistic', startedAt: new Date().toISOString(), startedBy: '', endedAt: null, endedBy: null } }
              : m,
          ),
        })
      }
      // Optimistically patch detail
      if (detailSnapshot) {
        qc.setQueryData<Membership>(membershipsKeys.detail(membershipId), {
          ...detailSnapshot,
          status: 'frozen',
        })
      }
      return { listSnapshots, detailSnapshot }
    },
    onError: (err, _vars, ctx) => {
      if (!ctx) return
      for (const [key, data] of ctx.listSnapshots) qc.setQueryData(key, data)
      if (ctx.detailSnapshot) {
        qc.setQueryData(membershipsKeys.detail(_vars.membershipId), ctx.detailSnapshot)
      }
      // Surface DomainError message via Sonner toast
      toast.error(isDomainError(err) ? t(`memberships.freeze.errors.${err.code}`) : t('common.errors.network'))
    },
    onSettled: (_data, _err, vars) => {
      void qc.invalidateQueries({ queryKey: membershipsKeys.lists() })
      void qc.invalidateQueries({ queryKey: membershipsKeys.detail(vars.membershipId) })
      void qc.invalidateQueries({ queryKey: membershipsKeys.byClient(vars.clientId) })
    },
  })
}
```

**`useRenewMembership` — NOT optimistic (new resource, UUID from server):**
```typescript
type RenewVars = { membershipId: MembershipId; clientId: string }

export function useRenewMembership() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  return useMutation({
    mutationFn: ({ membershipId }: RenewVars) => services.memberships.renew(membershipId),
    onSuccess: (newMembership, vars) => {
      toast.success(t('memberships.renew.success'))
      void navigate({ to: '/memberships/$membershipId', params: { membershipId: newMembership.id } })
    },
    onError: (err) => {
      toast.error(isDomainError(err) ? t(`memberships.renew.errors.${err.code}`) : t('common.errors.network'))
    },
    onSettled: (_data, _err, vars) => {
      void qc.invalidateQueries({ queryKey: membershipsKeys.lists() })
      void qc.invalidateQueries({ queryKey: membershipsKeys.byClient(vars.clientId) })
      void qc.invalidateQueries({ queryKey: membershipsKeys.detail(vars.membershipId) })
    },
  })
}
```

---

### `apps/admin-web/src/features/memberships/api/keys.ts` (hook, request-response)

**Analog:** Self — `detail(id)` confirmed at line 9, `byClient(clientId)` at line 10.

No changes needed unless `status` is added to `MembershipsListQuery` — the `list(filter)` key at line 7 already includes the full query object, so `status` flows through automatically once added to the query type.

---

### `apps/admin-web/src/routes/_protected/memberships_.$membershipId.tsx` (route, request-response)

**Analog:** `clients_.$clientId.tsx` (lines 1-66) — exact flat-route pattern

**Pattern to copy** (lines 37-66):
```typescript
export const Route = createFileRoute('/_protected/clients_/$clientId')({
  beforeLoad: ({ context, location }) => {
    const { role } = context.getSession()
    if (!can(role, 'view', 'clients')) {
      throw redirect({
        to: '/',
        search: { forbidden: location.pathname + (location.searchStr ?? '') },
      })
    }
  },
  loader: ({ context, params }) => {
    const { clientId } = params
    const id = clientId as ClientId
    return Promise.all([
      context.queryClient.ensureQueryData({
        queryKey: clientsKeys.detail(id),
        queryFn: () => services.clients.get(id),
      }),
      // ... additional prefetches
    ])
  },
  component: ClientDetailPage,
})
```

**New route adaptation:**
```typescript
import { createFileRoute, redirect, useParams } from '@tanstack/react-router'
import { z } from 'zod'
import { can } from '@/shared/session/can'
import { membershipsKeys } from '@/features/memberships/api/keys'
import { services } from '@/shared/api/services'
import type { MembershipId } from '@/entities/membership'

// validateSearch: empty (no search params on detail)
// beforeLoad: no extra RBAC — both roles can read (mirrors memberships list)

export const Route = createFileRoute('/_protected/memberships_/$membershipId')({
  beforeLoad: ({ context, location }) => {
    const { role } = context.getSession()
    if (!can(role, 'view', 'memberships')) {
      throw redirect({
        to: '/',
        search: { forbidden: location.pathname + (location.searchStr ?? '') },
      })
    }
  },
  loader: ({ context, params }) => {
    const id = params.membershipId as MembershipId
    return context.queryClient.ensureQueryData({
      queryKey: membershipsKeys.detail(id),
      queryFn: () => services.memberships.get(id),
    })
  },
  component: MembershipDetailPage,   // co-located in this file
})
```

**Co-located page component pattern** (mirrors `ClientDetailPage` lines 20-35):
```typescript
function MembershipDetailPage() {
  const { membershipId } = useParams({ from: '/_protected/memberships_/$membershipId' })
  const id = membershipId as MembershipId
  const { data: membership } = useMembership(id)

  // Loader already prefetched; null-guard should not hit in practice
  if (!membership) return null

  return (
    <main className="container mx-auto px-4 py-6 space-y-8">
      {/* Header card, FreezeSection, RenewSection, Metadata */}
    </main>
  )
}
```

---

### `apps/admin-web/src/routes/_protected/memberships.tsx` (route, request-response)

**Analog:** Self — extend existing `searchSchema` and `loaderDeps`

**Current searchSchema** (lines 8-12):
```typescript
const searchSchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  pageSize: z.coerce.number().int().min(10).max(100).default(20),
  expiring: z.boolean().optional().default(false),
})
```

**Extension — add `status` and `within`:**
```typescript
const searchSchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  pageSize: z.coerce.number().int().min(10).max(100).default(20),
  status: z.enum(['active', 'expired', 'cancelled', 'frozen']).optional(),  // NEW
  expiring: z.boolean().optional().default(false),
  within: z.coerce.number().int().min(1).max(30).default(7),               // NEW
})
```

---

### `apps/admin-web/src/features/memberships/components/StatusBadge.tsx` (component, transform)

**Analog:** Inline `StatusBadge` duplicated in `MembershipsListPage.tsx` (lines 26-31) and `MembershipsBlock.tsx` (lines 19-23)

**Current inline definition** (lines 26-31 of `MembershipsListPage.tsx`):
```typescript
function StatusBadge({ status }: { status: Membership['status'] }) {
  if (status === 'active') return <Badge variant="default">{t('memberships.status.active')}</Badge>
  if (status === 'expired')
    return <Badge variant="secondary">{t('memberships.status.expired')}</Badge>
  return <Badge variant="outline">{t('memberships.status.cancelled')}</Badge>
}
```

**Extracted component with `frozen` variant** (apply `className` override per UI-SPEC badge contract):
```typescript
import { Badge } from '@/shared/ui/badge'
import { t } from '@/shared/i18n'
import type { MembershipStatus } from '@/entities/membership'

interface Props {
  status: MembershipStatus
}

export function StatusBadge({ status }: Props) {
  if (status === 'active')
    return <Badge variant="default">{t('memberships.status.active')}</Badge>
  if (status === 'expired')
    return <Badge variant="secondary">{t('memberships.status.expired')}</Badge>
  if (status === 'cancelled')
    return <Badge variant="outline">{t('memberships.status.cancelled')}</Badge>
  // 'frozen' — use outline variant + semantic warning token override
  // NOT a raw palette color; bg-warning and text-warning-foreground are CSS
  // variable aliases defined in index.css via reui-extras (ESLint safe)
  return (
    <Badge variant="outline" className="bg-warning text-warning-foreground border-warning/50">
      {t('memberships.status.frozen')}
    </Badge>
  )
}
```

**Note on `badge.tsx` `cva`** (lines 7-28): No `warning` variant exists. The `className` override is the correct approach — it applies semantic tokens through CSS variables, not raw palette classes.

---

### `apps/admin-web/src/features/memberships/components/FreezeSection.tsx` (component, request-response)

**Analog:** `CancelMembershipDialog.tsx` (lines 1-117) for button+dialog shape; `MembershipsBlock.tsx` (lines 95-107) for `<RoleGate>` + `<Button size="sm">` pattern

**`<RoleGate>` + `<Button>` pattern** (from `MembershipsBlock.tsx` lines 95-107):
```typescript
<RoleGate action="cancel" resource="memberships">
  <Button
    variant="ghost"
    size="sm"
    className="text-destructive"
    onClick={() => setCancelId(m.id)}
    disabled={m.status !== 'active'}
  >
    {t('memberships.actions.cancel')}
  </Button>
</RoleGate>
```

**Tooltip-on-disabled pattern** (from 28-UI-SPEC.md — no existing analog; first use):
```tsx
<TooltipProvider>
  <Tooltip>
    <TooltipTrigger asChild>
      <span tabIndex={0}>
        <Button variant="outline" size="sm" disabled>
          {t('memberships.freeze.button')}
        </Button>
      </span>
    </TooltipTrigger>
    <TooltipContent>{t('memberships.freeze.no_days_remaining')}</TooltipContent>
  </Tooltip>
</TooltipProvider>
```

**Spinner pattern** (no exact analog — use lucide Loader2):
```tsx
import { Loader2 } from 'lucide-react'
// Inside button:
{freeze.isPending ? <Loader2 className="animate-spin" size={14} /> : t('memberships.freeze.button')}
```

---

### `apps/admin-web/src/features/memberships/components/RenewConfirmDialog.tsx` (component, request-response)

**Analog:** `CancelMembershipDialog.tsx` (lines 1-117) — complete `<AlertDialog>` structure to mirror

**Full AlertDialog pattern** (lines 62-116):
```typescript
return (
  <AlertDialog
    open={open}
    onOpenChange={(o) => {
      if (!o) { setInlineError(null); onClose() }
    }}
  >
    <AlertDialogContent>
      <AlertDialogHeader>
        <AlertDialogTitle>{t('memberships.dialog.cancelTitle')}</AlertDialogTitle>
        <AlertDialogDescription>{t('memberships.dialog.cancelBody')}</AlertDialogDescription>
      </AlertDialogHeader>
      {/* body content */}
      <AlertDialogFooter>
        <AlertDialogCancel disabled={cancel.isPending} onClick={...}>
          {t('memberships.dialog.cancelAbort')}
        </AlertDialogCancel>
        <AlertDialogAction
          disabled={cancel.isPending}
          className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          onClick={handleConfirm}
        >
          {cancel.isPending ? '…' : t('memberships.dialog.cancelConfirm')}
        </AlertDialogAction>
      </AlertDialogFooter>
    </AlertDialogContent>
  </AlertDialog>
)
```

**RenewConfirmDialog differences from CancelMembershipDialog:**
- No textarea (snapshot data only, per D-28-08)
- `<AlertDialogAction>` uses `variant="default"` (renew is NOT destructive — no `bg-destructive` class)
- Body shows: `formatMoney(priceKopecksSnapshot)` + `formatDate(computedStart)` + `formatDate(computedEnd)`
- Date computation (display-only):
  ```typescript
  import { addDays, parseISO } from 'date-fns'
  const computedStart = membership.status === 'expired'
    ? todayMSK()
    : addDays(parseISO(membership.endDate), 1).toISOString().slice(0, 10)
  const computedEnd = addDays(parseISO(computedStart), membership.durationDaysSnapshot - 1)
    .toISOString().slice(0, 10)
  ```

---

### `apps/admin-web/src/features/memberships/components/MembershipsListPage.tsx` (component, modified)

**Analog:** Self — extend existing filter row (lines 162-177)

**Current filter row** (lines 162-177):
```typescript
<div className="flex items-center justify-between">
  <h1 className="text-xl font-semibold">{t('memberships.heading')}</h1>
  <Button
    variant={search.expiring ? 'secondary' : 'outline'}
    size="sm"
    onClick={() =>
      void navigate({
        search: (prev) => ({ ...prev, expiring: !prev.expiring, page: 1 }),
      })
    }
  >
    {t('memberships.filter.expiring')}
  </Button>
</div>
```

**Extension — add frozen pill + within selector:**
```typescript
<div className="flex items-center gap-2">
  {/* Frozen status filter pill */}
  <Button
    variant={search.status === 'frozen' ? 'secondary' : 'outline'}
    size="sm"
    onClick={() =>
      void navigate({
        search: (prev) => ({
          ...prev,
          status: prev.status === 'frozen' ? undefined : 'frozen',
          expiring: false,  // mutually exclusive
          page: 1,
        }),
      })
    }
  >
    {t('memberships.status.frozen')}
  </Button>
  {/* Existing expiring toggle */}
  <Button
    variant={search.expiring ? 'secondary' : 'outline'}
    size="sm"
    onClick={() => void navigate({ search: (prev) => ({ ...prev, expiring: !prev.expiring, status: undefined, page: 1 }) })}
  >
    {t('memberships.filter.expiring')}
  </Button>
  {/* Within selector — visible only when expiring=true */}
  {search.expiring && (
    <div className="flex items-center gap-2">
      <span className="text-muted-foreground text-sm">{t('memberships.list.expiringWithin.label')}</span>
      <Select
        value={String(search.within ?? 7)}
        onValueChange={(v) => void navigate({ search: (prev) => ({ ...prev, within: Number(v) }) })}
      >
        <SelectTrigger size="sm"><SelectValue /></SelectTrigger>
        <SelectContent>
          {[1, 3, 7, 14, 30].map((n) => (
            <SelectItem key={n} value={String(n)}>{n} {t('memberships.list.expiringWithin.option_days')}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )}
</div>
```

---

### `apps/admin-web/src/shared/i18n/ru.ts` (i18n, transform)

**Analog:** Self — extend existing `memberships` namespace (lines 143-212)

**Existing namespace structure** (lines 143-212) shows:
- Flat keys under `memberships.status`, `memberships.dialog`, `memberships.toast`, `memberships.errors`
- No template engine — string interpolation done by caller via `.replace('{key}', value)`

**Extension — add to `memberships` object after `errors`:**
```typescript
// status: add frozen alongside existing active/expired/cancelled
status: {
  active: 'Активен',
  expired: 'Истёк',
  cancelled: 'Отменён',
  frozen: 'Заморожен',  // NEW
},
// New top-level keys under memberships:
freeze: {
  button: 'Заморозить',
  no_days_remaining: 'Все дни заморозки использованы',
  errors: {
    freeze_limit_exceeded: 'Лимит дней заморозки исчерпан.',
    already_frozen: 'Абонемент уже заморожен.',
    invalid_transition: 'Нельзя заморозить: статус абонемента не позволяет это действие.',
  },
  success: 'Абонемент заморожен',
},
unfreeze: {
  button: 'Снять заморозку',
  success: 'Заморозка снята',
},
frozen: {
  badge: 'Заморожено с {date}',
  period_dates: 'С {startedAt} по {nowOrEndedAt}',
},
renew: {
  button: 'Продлить',
  confirm: {
    title: 'Продлить абонемент?',
    body: 'Тариф: {plan} · {price}\nНовый период: {startDate} — {endDate}',
    cta: 'Продлить',
    cancel: 'Отмена',
  },
  success: 'Абонемент продлён',
  errors: {
    cannot_renew_cancelled: 'Нельзя продлить отменённый абонемент.',
    plan_archived: 'Тариф архивирован — продление недоступно.',
  },
},
list: {
  expiringWithin: {
    label: 'Истекает в течение',
    option_days: 'дн.',
  },
},
detail: {
  title: 'Абонемент',
  section: {
    freeze: 'Заморозка',
    renewal: 'Продление',
  },
  previousMembership: 'Продлён из абонемента',
},
```

**Interpolation pattern** (matches existing usage, e.g. `visits.checkin.alreadyCheckedIn`):
```typescript
t('memberships.frozen.badge').replace('{date}', formatDate(currentFreezePeriod.startedAt))
```

---

## Shared Patterns

### RBAC Guard Pattern
**Source:** `apps/admin-web/src/shared/session/RoleGate.tsx` (lines 1-17) + `can.ts` (lines 12-28)
**Apply to:** `FreezeSection`, `RenewSection`, detail page action buttons

```typescript
// Declarative in JSX:
<RoleGate action="create" resource="memberships">
  <Button ...>{t('memberships.freeze.button')}</Button>
</RoleGate>

// Imperative in mock service:
ensure('create', 'memberships')  // throws DomainError('forbidden', ...) if denied
```

**OWNER_ONLY entries relevant to this phase:**
- `cancel/memberships` — owner-only (existing); cancel-during-freeze stays this way
- `create/memberships` is NOT in `OWNER_ONLY` — both roles can freeze/unfreeze/renew

### DomainError + Toast Error Pattern
**Source:** `apps/admin-web/src/shared/api/errors.ts` (lines 3-12) + `CancelMembershipDialog.tsx` (lines 38-57)
**Apply to:** All mutation `onError` callbacks in freeze/unfreeze/renew hooks

```typescript
import { isDomainError } from '@/shared/api/errors'
import { toast } from 'sonner'

onError: (err) => {
  toast.error(
    isDomainError(err)
      ? t(`memberships.freeze.errors.${err.code}`)
      : t('common.errors.network')
  )
}
```

### `delay()` + `ensure()` + `loadDB()` / `saveDB()` Mock Pattern
**Source:** `apps/admin-web/src/shared/api/services/mock/memberships.ts` (lines 18-27)
**Apply to:** All new mock methods (`freeze`, `unfreeze`, `renew`)

```typescript
async freeze(id: MembershipId): Promise<Membership> {
  await delay()               // 120-300ms simulated latency
  ensure('create', 'memberships')  // RBAC check
  const db = loadDB()         // parse from localStorage
  // ... mutation ...
  saveDB(db)                  // persist back
  return updated
}
```

### `formatMoney` + `formatDate` Display Pattern
**Source:** `apps/admin-web/src/shared/lib/money.ts` (line 14) + `apps/admin-web/src/shared/i18n/date.ts` (lines 16-18)
**Apply to:** `RenewConfirmDialog`, membership detail header

```typescript
import { formatMoney } from '@/shared/lib/money'
import { formatDate, todayMSK } from '@/shared/i18n/date'

formatMoney(membership.priceKopecksSnapshot)  // "1 000,00 ₽" with NBSP
formatDate(membership.startDate)              // "01.06.2026"
```

### Test Setup Pattern
**Source:** `apps/admin-web/src/shared/api/services/mock/memberships.expiring.test.ts` (lines 1-49)
**Apply to:** `memberships.freeze.test.ts`, `memberships.renew.test.ts`

```typescript
import { describe, it, expect, beforeEach } from 'vitest'
import { useSessionStore } from '@/shared/session/store'
import { memberships } from './memberships'
import { resetDB, loadDB, saveDB } from './_db'

describe('mock/memberships ... parity', () => {
  beforeEach(() => {
    resetDB()                              // clear localStorage
    useSessionStore.setState({ role: 'owner' })  // set role
  })
  // tests...
})
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `FreezeSection.tsx` — tooltip-on-disabled sub-pattern | component | request-response | No existing component wraps a disabled `<Button>` in `<TooltipTrigger asChild><span>`. 28-UI-SPEC.md provides the pattern from Radix Tooltip docs. |
| `ExpiringWithinSelector` (inline in `MembershipsListPage.tsx`) | component | request-response | No `<Select>`-based filter selector exists in the codebase. Use `shared/ui/select.tsx` (confirmed in repo) with the pattern from 28-UI-SPEC.md. |

---

## Metadata

**Analog search scope:** `apps/admin-web/src/` (entities, features/memberships, shared/api, routes, test)
**Files scanned:** 20
**Pattern extraction date:** 2026-05-10
