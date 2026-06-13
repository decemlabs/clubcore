# Phase 101: Clients + Memberships — Pattern Map

**Mapped:** 2026-06-13
**Files analyzed:** 14 new/modified files
**Analogs found:** 13 / 14

---

## PT-Packages Wiring Decision (planner read-first)

Backend `app/modules/pt_packages/router.py` has **full endpoints**:
- `GET /api/v1/pt-package-plans` / `/{id}` / `POST` / `PATCH /{id}` / `DELETE /{id}` — owner-only
- `POST /api/v1/pt-packages` (sell, reception+owner, Idempotency-Key required)
- `GET /api/v1/pt-packages` + `GET /{id}` (reception+owner)
- `POST /api/v1/pt-packages/{id}/cancel` (owner-only, Idempotency-Key required, reason 1–200 chars REQUIRED)
- `POST /api/v1/pt-packages/{id}/refund` (reception+owner per B-07, Idempotency-Key required)

Sell body: `{ clientId, planId, amountKopecks }`. Immutable plan fields: `sessionCount`, `priceKopecks`, `validityDays`. Plan list query param: `includeArchived` (not `active`).

**Conclusion: PT-package plans + PT-package sell/list/read/cancel/refund endpoints exist and are fully wired. Include in Phase 101.**

---

## Visits & Payments Client-Detail Reads

- `GET /api/v1/visits?clientId=…` — exists, reception+owner `(VIEW, VISITS)`.
- `GET /api/v1/payments/by-client/{clientId}` — exists, reception+owner via `require_payments_view_for_subject()`. **Note: the path is NOT `GET /payments?clientId=` — it is `GET /payments/by-client/{clientId}`.** Planner must use the correct scoped path.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `features/clients/schemas.ts` (NEW) | model/schema | request-response | `features/auth/schemas.ts` | exact |
| `features/clients/api.ts` (MODIFY — flip mock→http) | service | CRUD | `features/auth/api.ts` | exact |
| `features/plans/schemas.ts` (NEW) | model/schema | CRUD | `features/auth/schemas.ts` | role-match |
| `features/plans/api.ts` (MODIFY — flip mock→http, add mutations) | service | CRUD | `features/auth/api.ts` | exact |
| `features/memberships/schemas.ts` (NEW) | model/schema | CRUD | `features/auth/schemas.ts` | role-match |
| `features/memberships/api.ts` (NEW) | service | CRUD + event-driven lifecycle | `apps/admin-web/.../memberships/api/hooks.ts` | exact |
| `features/memberships/keys.ts` (NEW) | utility | — | `apps/admin-web/.../memberships/api/keys.ts` | exact |
| `features/pt-packages/schemas.ts` (NEW) | model/schema | CRUD | `features/auth/schemas.ts` | role-match |
| `features/pt-packages/api.ts` (NEW) | service | CRUD + event-driven lifecycle | `apps/admin-web/.../memberships/api/hooks.ts` | role-match |
| `api/client.ts` (MODIFY — add idempotency header support) | utility | request-response | `api/client.ts` itself | self-extend |
| `components/modals/SubscriptionModal.tsx` (MODIFY — wire + add refund screen) | component | request-response | `components/modals/SubscriptionModal.tsx` itself | self-extend |
| `pages/clients/ClientsPage.tsx` (MODIFY — filter reduction, server pagination) | component | request-response | `apps/admin-web/.../clients/components/ClientsPage.tsx` | role-match |
| `pages/plans/PlansPage.tsx` (MODIFY — wire mutations, permission gating) | component | CRUD | `apps/admin-web/.../memberships/components/MembershipPlansPage.tsx` | role-match |
| `pages/client/ClientPage.tsx` (MODIFY — wire child reads) | component | CRUD | `apps/admin-web/.../memberships/components/MembershipsBlock.tsx` | partial-match |

---

## Pattern Assignments

---

### `features/clients/schemas.ts` (NEW — model/schema, request-response)

**Analog:** `apps/admin-app/src/features/auth/schemas.ts`

**Imports pattern** (lines 1–2):
```typescript
import { z } from 'zod'
```

**Core pattern — mirror auth schemas.ts structure:**
```typescript
// ---------------------------------------------------------------------------
// List response
// ---------------------------------------------------------------------------
export const ClientSchema = z.object({
  id: z.string(),
  lastName: z.string(),
  firstName: z.string(),
  middleName: z.string().nullable().optional(),
  phone: z.string(),
  email: z.string().nullable().optional(),
  birthday: z.string().nullable().optional(),
  gender: z.enum(['male', 'female']).nullable().optional(),
  tags: z.array(z.string()),
  notes: z.string().nullable().optional(),
  telegramUserId: z.string().nullable().optional(),
  createdAt: z.string(),
})
export type ClientData = z.infer<typeof ClientSchema>

export const ClientsListResponseSchema = z.object({
  data: z.object({
    items: z.array(ClientSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
})

// ---------------------------------------------------------------------------
// Create / Update input (client-side Zod for form + submit validation)
// ---------------------------------------------------------------------------
export const ClientCreateSchema = z.object({
  lastName: z.string().min(1, 'Фамилия обязательна'),
  firstName: z.string().min(1, 'Имя обязательно'),
  middleName: z.string().optional(),
  phone: z.string().regex(/^\+[1-9]\d{1,14}$/, 'Введите телефон в формате +7XXXXXXXXXX'),
  email: z.string().email('Введите корректный адрес почты').optional().or(z.literal('')),
  birthday: z.string().optional(),
  gender: z.enum(['male', 'female']).optional(),
  tags: z.array(z.string()
    .max(32, 'Тег не может быть длиннее 32 символов')
    .regex(/^[a-z0-9а-я\-_]+$/, 'Тег содержит недопустимые символы')
  ).max(16, 'Не более 16 тегов').optional(),
  notes: z.string().max(4096, 'Заметка не может превышать 4096 символов').optional(),
  telegramUserId: z.string().optional(),
})
export type ClientCreateInput = z.infer<typeof ClientCreateSchema>
// PATCH is the same schema but all fields optional
export const ClientUpdateSchema = ClientCreateSchema.partial()
export type ClientUpdateInput = z.infer<typeof ClientUpdateSchema>
```

**Pattern source:** `apps/admin-app/src/features/auth/schemas.ts` lines 1–94 (one `z.object` per wire shape, `data:` wrapper on list responses, inline Russian error messages, `export type = z.infer<typeof Schema>`).

---

### `features/clients/api.ts` (MODIFY — flip mock→http)

**Analog:** `apps/admin-app/src/features/auth/api.ts`

**Imports pattern** (lines 15–26 of auth/api.ts):
```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { staffRequest, ApiError } from '@/api/client'
import {
  ClientsListResponseSchema,
  ClientSchema,
  ClientCreateSchema,
  type ClientData,
  type ClientCreateInput,
  type ClientUpdateInput,
} from './schemas'
```

**Key factory — extend existing `clientsKeys`:**
```typescript
export const clientsKeys = {
  all: ['clients'] as const,
  lists: () => [...clientsKeys.all, 'list'] as const,
  list: (filter: ClientsListQuery) => [...clientsKeys.lists(), filter] as const,
  details: () => [...clientsKeys.all, 'detail'] as const,
  detail: (id: string) => [...clientsKeys.details(), id] as const,
}
```
Source: `apps/admin-web/src/features/clients/api/keys.ts` (adopt the `lists()`/`list(filter)` hierarchy — the current `clientsKeys.list` is a bare array, which prevents proper `invalidateQueries` for all list variants with different filter shapes).

**Core queryFn pattern — from auth/api.ts lines 49–55:**
```typescript
export function useClients(filter: ClientsListQuery) {
  return useQuery({
    queryKey: clientsKeys.list(filter),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/clients', { query: filterToQuery(filter) })
      return ClientsListResponseSchema.parse(raw).data
    },
    staleTime: 30_000,
  })
}

export function useClient(id: string) {
  return useQuery({
    queryKey: clientsKeys.detail(id),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/clients/{id}', { params: { id } })
      return ClientSchema.parse((raw as { data: unknown }).data)
    },
    enabled: !!id,
    staleTime: 30_000,
  })
}
```

**Mutation pattern — from auth/api.ts lines 61–75 + admin-web hooks.ts lines 28–98:**
```typescript
export function useCreateClient() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: ClientCreateInput) => {
      const raw = await staffRequest('post', '/api/v1/clients', { body })
      return ClientSchema.parse((raw as { data: unknown }).data)
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: clientsKeys.lists() })
    },
  })
}

export function useDeleteClient() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => staffRequest('delete', '/api/v1/clients/{id}', { params: { id } }),
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: clientsKeys.lists() })
    },
  })
}
```

**Re-export ApiError (auth/api.ts line 119):**
```typescript
export { ApiError }
```

---

### `features/plans/schemas.ts` (NEW — model/schema)

**Analog:** `apps/admin-app/src/features/auth/schemas.ts`

```typescript
import { z } from 'zod'

export const MembershipPlanSchema = z.object({
  id: z.string(),
  name: z.string(),
  durationDays: z.number(),
  priceKopecks: z.number(),
  freezeDaysLimit: z.number().nullable().optional(),
  active: z.boolean(),
  createdAt: z.string(),
})
export type MembershipPlanData = z.infer<typeof MembershipPlanSchema>

export const PlansListResponseSchema = z.object({
  data: z.object({
    items: z.array(MembershipPlanSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
})

// Create (all fields required)
export const MembershipPlanCreateSchema = z.object({
  name: z.string().min(1, 'Укажите название тарифа'),
  durationDays: z.number().int().min(1, 'Длительность: от 1 до 3650 дней').max(3650, 'Длительность: от 1 до 3650 дней'),
  priceKopecks: z.number().int().min(0, 'Цена не может быть отрицательной'),
  freezeDaysLimit: z.number().int().min(1, 'Лимит заморозки: от 1 до 365 дней').max(365, 'Лимит заморозки: от 1 до 365 дней').optional(),
  active: z.boolean().optional(),
})
export type MembershipPlanCreateInput = z.infer<typeof MembershipPlanCreateSchema>

// PATCH: durationDays is immutable — omit from update schema (submit → 422 from backend if included)
export const MembershipPlanUpdateSchema = MembershipPlanCreateSchema
  .omit({ durationDays: true })
  .partial()
export type MembershipPlanUpdateInput = z.infer<typeof MembershipPlanUpdateSchema>
```

**Note:** `durationDays` immutability: the schema omits it from the PATCH shape client-side. If the user somehow triggers a 422 `durationDays` from the backend, surface: `«Длительность тарифа нельзя изменить после создания»`.

---

### `features/plans/api.ts` (MODIFY — flip mock→http, add mutations)

**Analog:** `apps/admin-app/src/features/auth/api.ts` + `apps/admin-web/src/features/memberships/api/hooks.ts` lines 255–285

```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { staffRequest, ApiError } from '@/api/client'
import {
  PlansListResponseSchema, MembershipPlanSchema,
  type MembershipPlanCreateInput, type MembershipPlanUpdateInput,
} from './schemas'

export const plansKeys = {
  all: ['plans'] as const,
  lists: () => [...plansKeys.all, 'list'] as const,
  list: (filter?: { active?: boolean; page?: number }) => [...plansKeys.lists(), filter] as const,
  detail: (id: string) => [...plansKeys.all, 'detail', id] as const,
}

export function usePlans(opts?: { active?: boolean; page?: number; pageSize?: number }) {
  return useQuery({
    queryKey: plansKeys.list(opts),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/membership-plans', { query: opts ?? {} })
      return PlansListResponseSchema.parse(raw).data
    },
    staleTime: 30_000,
  })
}

export function useCreatePlan() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: MembershipPlanCreateInput) => {
      const raw = await staffRequest('post', '/api/v1/membership-plans', { body })
      return MembershipPlanSchema.parse((raw as { data: unknown }).data)
    },
    onSettled: () => { void qc.invalidateQueries({ queryKey: plansKeys.lists() }) },
  })
}
// useUpdatePlan / useDeletePlan follow same onSettled invalidation pattern
```

**Permission gate pattern (from UI-SPEC §2):** In `PlansPage.tsx`, wrap all Add/Edit/Delete buttons with `can(role, 'edit', 'memberships')` — hide (not disable) when false.

---

### `features/memberships/schemas.ts` (NEW — model/schema)

**Analog:** `apps/admin-app/src/features/auth/schemas.ts`

```typescript
import { z } from 'zod'
import { MembershipPlanSchema } from '../plans/schemas'

export const FreezePeriodSchema = z.object({
  id: z.string(),
  startedAt: z.string(),
  startedBy: z.string(),
  endedAt: z.string().nullable(),
  endedBy: z.string().nullable(),
})

export const MembershipSchema = z.object({
  id: z.string(),
  clientId: z.string(),
  status: z.enum(['active', 'frozen', 'expired', 'cancelled']),
  planSnapshot: MembershipPlanSchema,
  paidAmountKopecks: z.number(),
  paidAt: z.string().nullable().optional(),
  startDate: z.string(),
  endDate: z.string(),
  freezeDaysUsed: z.number(),
  freezeDaysRemaining: z.number().nullable().optional(),
  currentFreezePeriod: FreezePeriodSchema.nullable().optional(),
  previousMembershipId: z.string().nullable().optional(),
  notes: z.string().nullable().optional(),
  createdAt: z.string(),
})
export type MembershipData = z.infer<typeof MembershipSchema>

export const MembershipsListResponseSchema = z.object({
  data: z.object({
    items: z.array(MembershipSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
})

// Sell
export const MembershipSellSchema = z.object({
  clientId: z.string().min(1),
  planId: z.string().min(1),
  paidAt: z.string().optional(),
  notes: z.string().optional(),
})
export type MembershipSellInput = z.infer<typeof MembershipSellSchema>

// Cancel
export const MembershipCancelSchema = z.object({
  reason: z.string().max(500).optional(),
})

// Refund (reason required 1–200)
export const MembershipRefundSchema = z.object({
  reason: z.string().min(1, 'Причина обязательна для возврата').max(200),
})
export type MembershipRefundInput = z.infer<typeof MembershipRefundSchema>
```

---

### `features/memberships/api.ts` (NEW — service, CRUD + lifecycle)

**Analog:** `apps/admin-web/src/features/memberships/api/hooks.ts` (primary; lines 1–285)
**Secondary analog:** `apps/admin-app/src/features/auth/api.ts` (staffRequest + Schema.parse pattern)

**Imports pattern:**
```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { staffRequest, ApiError } from '@/api/client'
import { membershipsKeys } from './keys'
import {
  MembershipsListResponseSchema, MembershipSchema,
  type MembershipSellInput, type MembershipRefundInput,
} from './schemas'
```

**Queries pattern (from admin-web hooks.ts lines 16–60):**
```typescript
export function useMembershipsByClient(clientId: string) {
  return useQuery({
    queryKey: membershipsKeys.byClient(clientId),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/memberships', { query: { clientId } })
      return MembershipsListResponseSchema.parse(raw).data
    },
    enabled: !!clientId,
    staleTime: 30_000,
  })
}
```

**Sell mutation (non-optimistic; Idempotency-Key via extended staffRequest):**
```typescript
export function useSellMembership() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ body, idempotencyKey }: { body: MembershipSellInput; idempotencyKey: string }) => {
      const raw = await staffRequest('post', '/api/v1/memberships', {
        body,
        headers: { 'Idempotency-Key': idempotencyKey },
      })
      return MembershipSchema.parse((raw as { data: unknown }).data)
    },
    onSuccess: (data) => {
      toast.success('Абонемент оформлен', { description: `Оплата принята.` })
      void qc.invalidateQueries({ queryKey: membershipsKeys.lists() })
      void qc.invalidateQueries({ queryKey: membershipsKeys.byClient(data.clientId) })
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : undefined
      toast.error(msg ?? 'Не удалось выполнить действие.')
    },
  })
}
```

**Freeze mutation (optimistic; from admin-web hooks.ts lines 108–173):**
```typescript
type FreezeVars = { membershipId: string; clientId: string; idempotencyKey: string }

export function useFreezeMembership() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ membershipId, idempotencyKey }: FreezeVars) =>
      staffRequest('post', '/api/v1/memberships/{id}/freeze', {
        params: { id: membershipId },
        body: {},
        headers: { 'Idempotency-Key': idempotencyKey },
      }),
    onMutate: async ({ membershipId }) => {
      await qc.cancelQueries({ queryKey: membershipsKeys.lists() })
      await qc.cancelQueries({ queryKey: membershipsKeys.detail(membershipId) })
      const listSnapshots = qc.getQueriesData<{ items: MembershipData[] }>({
        queryKey: membershipsKeys.lists(),
      })
      const detailSnapshot = qc.getQueryData<MembershipData>(membershipsKeys.detail(membershipId))
      // Optimistic: flip status → 'frozen', inject placeholder currentFreezePeriod
      for (const [key, data] of listSnapshots) {
        if (!data) continue
        qc.setQueryData(key, {
          ...data,
          items: data.items.map((m) =>
            m.id === membershipId
              ? { ...m, status: 'frozen', currentFreezePeriod: { id: 'optimistic', startedAt: new Date().toISOString(), startedBy: '', endedAt: null, endedBy: null } }
              : m,
          ),
        })
      }
      if (detailSnapshot) {
        qc.setQueryData(membershipsKeys.detail(membershipId), {
          ...detailSnapshot,
          status: 'frozen',
          currentFreezePeriod: { id: 'optimistic', startedAt: new Date().toISOString(), startedBy: '', endedAt: null, endedBy: null },
        })
      }
      return { listSnapshots, detailSnapshot }
    },
    onError: (_err, vars, ctx) => {
      if (!ctx) return
      for (const [key, data] of ctx.listSnapshots) qc.setQueryData(key, data)
      if (ctx.detailSnapshot) qc.setQueryData(membershipsKeys.detail(vars.membershipId), ctx.detailSnapshot)
      toast.error('Недостаточно прав', { description: 'Это действие доступно только владельцу.' })
    },
    onSettled: (_data, _err, vars) => {
      void qc.invalidateQueries({ queryKey: membershipsKeys.lists() })
      void qc.invalidateQueries({ queryKey: membershipsKeys.detail(vars.membershipId) })
      void qc.invalidateQueries({ queryKey: membershipsKeys.byClient(vars.clientId) })
      toast.success('Абонемент заморожен')
    },
  })
}
```

**Unfreeze mutation (same optimistic shape — from admin-web hooks.ts lines 175–223):**
Identical structure to freeze. `onMutate` optimistic: `status: 'active'`, `currentFreezePeriod: null`.

**Refund mutation (non-optimistic; NO Idempotency-Key per UI-SPEC §3.2):**
```typescript
export function useRefundMembership() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ membershipId, body }: { membershipId: string; body: MembershipRefundInput }) =>
      staffRequest('post', '/api/v1/memberships/{id}/refund', {
        params: { id: membershipId },
        body,
      }),
    onSuccess: (_data, vars) => {
      toast.success('Возврат оформлен', { description: 'Средства будут возвращены клиенту.' })
      void qc.invalidateQueries({ queryKey: membershipsKeys.detail(vars.membershipId) })
      void qc.invalidateQueries({ queryKey: membershipsKeys.lists() })
    },
  })
}
```

---

### `features/memberships/keys.ts` (NEW — utility)

**Analog:** `apps/admin-web/src/features/memberships/api/keys.ts` (exact copy — adapt to admin-app paths)

```typescript
// keys.ts
export const membershipsKeys = {
  all: ['memberships'] as const,
  lists: () => [...membershipsKeys.all, 'list'] as const,
  list: (filter: MembershipsListQuery) => [...membershipsKeys.lists(), filter] as const,
  details: () => [...membershipsKeys.all, 'detail'] as const,
  detail: (id: string) => [...membershipsKeys.details(), id] as const,
  byClient: (clientId: string) => [...membershipsKeys.all, 'byClient', clientId] as const,
} as const
```

Source: `apps/admin-web/src/features/memberships/api/keys.ts` lines 1–25.

---

### `features/pt-packages/schemas.ts` (NEW — model/schema)

**Analog:** `features/auth/schemas.ts` + `apps/backend/app/modules/pt_packages/schemas.py`

```typescript
import { z } from 'zod'

export const PtPackagePlanSchema = z.object({
  id: z.string(),
  name: z.string(),
  sessionCount: z.number(),
  priceKopecks: z.number(),
  validityDays: z.number().nullable().optional(),
  active: z.boolean(),
  createdAt: z.string(),
})
export type PtPackagePlanData = z.infer<typeof PtPackagePlanSchema>

export const PtPackagePlanCreateSchema = z.object({
  name: z.string().min(1, 'Укажите название'),
  sessionCount: z.number().int().min(1).max(1000),
  priceKopecks: z.number().int().min(1),
  validityDays: z.number().int().min(1).max(3650).optional(),
})

// PATCH: sessionCount / priceKopecks / validityDays are immutable — only `name` is mutable
export const PtPackagePlanUpdateSchema = z.object({ name: z.string().min(1) })

export const PtPackageSchema = z.object({
  id: z.string(),
  clientId: z.string(),
  status: z.enum(['active', 'exhausted', 'expired', 'cancelled']),
  planSnapshot: PtPackagePlanSchema,
  sessionsTotal: z.number(),
  sessionsUsed: z.number(),
  sessionsRemaining: z.number(),
  amountKopecks: z.number(),
  createdAt: z.string(),
})
export type PtPackageData = z.infer<typeof PtPackageSchema>

// Sell: requires amountKopecks (must match plan.priceKopecks — backend validates 422 amount_mismatch)
export const PtPackageSellSchema = z.object({
  clientId: z.string().min(1),
  planId: z.string().min(1),
  amountKopecks: z.number().int().min(1),
})
export type PtPackageSellInput = z.infer<typeof PtPackageSellSchema>

// Cancel: reason required 1–200 (D-33-10, unlike memberships cancel where reason is optional)
export const PtPackageCancelSchema = z.object({
  reason: z.string().min(1, 'Причина обязательна').max(200),
})

// Refund: reason required 1–200
export const PtPackageRefundSchema = z.object({
  reason: z.string().min(1, 'Причина обязательна для возврата').max(200),
})
```

---

### `features/pt-packages/api.ts` (NEW — service, CRUD + lifecycle)

**Analog:** `features/memberships/api.ts` (same pattern; same staffRequest + Idempotency-Key shape)

Key differences from memberships:
- Plans path: `/api/v1/pt-package-plans`
- Instances path: `/api/v1/pt-packages`
- Sell body has `amountKopecks` (required)
- Cancel also requires `reason` (not optional)
- Plans list query: `includeArchived` (not `active`)
- No freeze/unfreeze on pt-packages
- Cancel is owner-only; refund is reception+owner

Pattern for hooks is identical to memberships — `staffRequest` + `Schema.parse(raw).data` + invalidate keys on settle.

---

### `api/client.ts` (MODIFY — add per-call Idempotency-Key header support)

**Analog:** `apps/admin-app/src/api/client.ts` lines 105–109 (StaffRequestInit interface)

The `StaffRequestInit` interface already includes `headers?: HeadersInit`. The `staffRequest` function already passes `init?.headers` through (line 175: `const headers = new Headers(init?.headers)`). Therefore, callers can pass `Idempotency-Key` via the existing `headers` field **without any change to `client.ts`**:

```typescript
// No change to client.ts needed — callers do:
await staffRequest('post', '/api/v1/memberships', {
  body,
  headers: { 'Idempotency-Key': crypto.randomUUID() },
})
```

**Verify:** `api/client.ts` line 175 reads `new Headers(init?.headers)`, then sets CSRF on top. Custom headers passed in `init.headers` are preserved. The `Idempotency-Key` header will pass through as-is.

**Conclusion: no changes to `api/client.ts` are needed.** The existing `StaffRequestInit.headers` field already supports per-call headers. Planner should note this — the idempotency key is generated via `crypto.randomUUID()` at the call site in each mutation hook.

---

### `components/modals/SubscriptionModal.tsx` (MODIFY — wire existing screens + add refund screen)

**Analog:** `components/modals/SubscriptionModal.tsx` itself (lines 1–35 for imports, line 83–164 for CreateScreen pattern)

**Submitting state pattern (all dialogs — from UI-SPEC §3.1):**
```typescript
// Add `isSubmitting` prop to each ScreenProps
type ScreenProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  isSubmitting?: boolean
}

// In footerActions:
<ModalButton
  disabled={isSubmitting}
  onClick={handleSubmit}
>
  {isSubmitting ? <><Loader2 className="size-[18px] animate-spin" /> Обработка…</> : 'Создать и принять оплату'}
</ModalButton>
// ghost cancel button also disabled while submitting:
<ModalButton variant="ghost" disabled={isSubmitting} onClick={() => onOpenChange(false)}>
  Отмена
</ModalButton>
```

**Error state pattern (inline Callout — from UI-SPEC §3.1):**
```typescript
// In dialog body, below last field:
{error && (
  <Callout tone="danger" icon={TriangleAlert}>
    {error.message ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.'}
  </Callout>
)}
```

**Refund screen (NET-NEW — from UI-SPEC §3.2):**
```typescript
function RefundScreen({ open, onOpenChange, membership }: ScreenProps & { membership: MembershipData }) {
  const [reason, setReason] = useState('')
  const [touched, setTouched] = useState(false)
  const { mutate: refund, isPending, error } = useRefundMembership()

  return (
    <AdaptiveModal
      open={open}
      onOpenChange={isPending ? () => {} : onOpenChange}
      icon={<IconChip icon={ReceiptX} tone="danger" />}
      title="Оформить возврат"
      description={`${clientName} · «${membership.planSnapshot.name}»`}
      footerActions={
        <>
          <ModalButton variant="ghost" disabled={isPending} onClick={() => onOpenChange(false)}>
            Отмена
          </ModalButton>
          <ModalButton
            tone="danger"
            disabled={isPending || reason.trim().length === 0}
            onClick={() => { setTouched(true); if (reason.trim()) refund({ membershipId: membership.id, body: { reason } }) }}
          >
            {isPending
              ? <><Loader2 className="size-[18px] animate-spin" /> Обработка…</>
              : `Вернуть ${formatMoney(membership.paidAmountKopecks)}`}
          </ModalButton>
        </>
      }
    >
      <Callout tone="warn" icon={TriangleAlert}>
        Возврат полный и необратимый. Средства вернутся тем же способом, которым была принята оплата.
      </Callout>
      <StatRow label="Оплачено" value={formatMoney(membership.paidAmountKopecks)} accent />
      <StatRow label="Дата покупки" value={formatDate(membership.paidAt)} />
      <Field label="Причина возврата" required>
        <textarea
          className="min-h-[80px] w-full resize-none rounded-[10px] border-[0.5px] border-border bg-surface-2 px-3 py-2.5 text-[13.5px] outline-none placeholder:text-fg-subtle focus:border-ring focus:ring-2 focus:ring-ring/20"
          maxLength={200}
          placeholder="Укажите причину возврата"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          onBlur={() => setTouched(true)}
        />
        <div className="mt-1 flex justify-between">
          {touched && reason.trim().length === 0
            ? <span className="text-[12px] text-danger">Причина обязательна для возврата</span>
            : <span />}
          <span className="ml-auto text-[11.5px] tabular-nums text-fg-subtle">{reason.length}/200</span>
        </div>
      </Field>
      {error && (
        <Callout tone="danger" icon={TriangleAlert}>
          {error instanceof ApiError ? error.message : 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.'}
        </Callout>
      )}
    </AdaptiveModal>
  )
}
```

Add `'refund'` to `SubscriptionScreen` type in `modals-context.ts`.

---

### `pages/clients/ClientsPage.tsx` (MODIFY — filter reduction, server pagination)

**Analog:** `apps/admin-web/src/features/clients/components/ClientsPage.tsx`

**Filter reduction (from UI-SPEC §4):**
```typescript
// REMOVE: <ClientFilterTabs> component and statusFilter state entirely
// REMOVE: planType and trainer FilterSelect dropdowns
// REMOVE: sort presets except name:asc and recent:desc

const SORT_PRESETS = [
  { value: 'recent:desc', label: 'Недавние', backendParam: 'created_at_desc' },
  { value: 'name:asc',   label: 'По имени (А–Я)', backendParam: 'last_name_asc' },
] as const

// KEEP: gender, hasTelegram, tag FilterSelect dropdowns (NEW — backend-supported)
// KEEP: SearchInput with debounce 300ms + min-2-char gate
```

**Server pagination pattern (from UI-SPEC §4.5):**
```typescript
// Replace mock pagination shape with real {items, total, page, pageSize}
// Page in URL: ?page=N (omit when page=1)
const { page = 1 } = Route.useSearch()
const { data, isPending, isError, refetch } = useClients({ ...filters, page, pageSize: 25 })
// data.total, data.page, data.pageSize drive Pagination component
```

**Debounce + min-2-char gate (admin-web precedent):**
```typescript
const [searchRaw, setSearchRaw] = useState('')
const searchDebounced = useDebounce(searchRaw, 300)
const q = searchDebounced.length >= 2 ? searchDebounced : undefined
// pass q to useClients({ q, ... })
```

---

### `pages/plans/PlansPage.tsx` (MODIFY — wire mutations, permission gating)

**Analog:** `apps/admin-web/src/features/memberships/components/MembershipPlansPage.tsx`

**Permission gating pattern (from CONTEXT.md §Mutations & Permissions + UI-SPEC §2):**
```typescript
import { can } from '@/shared/session/can'
import { useSessionStore } from '@/shared/session/store'

const role = useSessionStore((s) => s.role)

// Add/Edit/Delete buttons — hidden for reception
{can(role, 'edit', 'memberships') && (
  <button onClick={() => openCreatePlanModal()}>Добавить тариф</button>
)}

// 403 query response:
if (isError && error instanceof ApiError && error.code === 'forbidden') {
  return <EmptyState icon={Lock} title="Недостаточно прав" message="Этот раздел доступен только владельцу. Обратитесь к владельцу клуба." />
}
```

---

### `pages/client/ClientPage.tsx` (MODIFY — wire child reads)

**Analog:** `apps/admin-web/src/features/memberships/components/MembershipsBlock.tsx`

**Child query per tab (from CONTEXT.md):**
```typescript
// Memberships tab
const membershipsQuery = useMembershipsByClient(clientId)
// Visits tab
const visitsQuery = useQuery({
  queryKey: ['visits', 'byClient', clientId],
  queryFn: async () => {
    const raw = await staffRequest('get', '/api/v1/visits', { query: { clientId } })
    return VisitsListResponseSchema.parse(raw).data
  },
  staleTime: 30_000,
})
// Payments tab — CORRECT path is /payments/by-client/{id}, not /payments?clientId=
const paymentsQuery = useQuery({
  queryKey: ['payments', 'byClient', clientId],
  queryFn: async () => {
    const raw = await staffRequest('get', '/api/v1/payments/by-client/{client_id}', {
      params: { client_id: clientId },
    })
    return PaymentsListResponseSchema.parse(raw).data
  },
  staleTime: 30_000,
})
```

**Per-tab inline error (from UI-SPEC §1):**
```typescript
// Each tab renders its own error state — do NOT bubble to full-page error
if (membershipsQuery.isError) {
  return <PageError onRetry={() => void membershipsQuery.refetch()} />
}
```

---

## Shared Patterns

### Auth / Transport
**Source:** `apps/admin-app/src/api/client.ts` + `features/auth/api.ts`
**Apply to:** All new api.ts files

```typescript
// Every queryFn:
const raw = await staffRequest('get', '/api/v1/...', { query: { ... } })
return SomeSchema.parse(raw).data

// Every mutation that requires Idempotency-Key:
await staffRequest('post', '/api/v1/...', {
  body,
  headers: { 'Idempotency-Key': crypto.randomUUID() },
})
// Note: crypto.randomUUID() must be called at submit time (per attempt), not at hook init.

// Re-export ApiError so pages can instanceof check without importing @/api/client:
export { ApiError }
```

**No change to `api/client.ts` needed.** The existing `headers` field in `StaffRequestInit` already passes through to `new Headers(init?.headers)` (line 175 of client.ts). Idempotency-Key is passed inline.

### Error Handling — Mutation 403
**Source:** UI-SPEC §2 + auth/api.ts pattern
**Apply to:** All mutation hooks + modal submit handlers

```typescript
// 403 on mutation → Sonner toast (not ErrorPage)
onError: (err) => {
  if (err instanceof ApiError && err.code === 'forbidden') {
    toast.error('Недостаточно прав', { description: 'Это действие доступно только владельцу.' })
  }
}
// 403 on query (whole screen forbidden) → <EmptyState icon={Lock} ...>
```

### Error Handling — 422 Field Errors
**Source:** `features/auth/schemas.ts` pattern + UI-SPEC §2
**Apply to:** All form submit handlers

```typescript
// Surface backend 422 field errors inline:
if (err instanceof ApiError && err.fields) {
  // err.fields is Record<string, string> — set each field error via react-hook-form setError
  for (const [field, message] of Object.entries(err.fields)) {
    form.setError(field as FieldPath<FormData>, { message })
  }
}
```

### Optimistic Mutation Shape
**Source:** `apps/admin-web/src/features/memberships/api/hooks.ts` lines 106–223
**Apply to:** freeze + unfreeze membership hooks only (all other mutations are non-optimistic)

```typescript
// Pattern: cancel → optimistic-update → onError rollback → onSettled invalidate
onMutate: async (vars) => {
  await qc.cancelQueries(...)
  const snapshots = qc.getQueriesData(...)
  // apply optimistic updates
  return { snapshots }
},
onError: (_err, _vars, ctx) => {
  if (!ctx) return
  for (const [key, data] of ctx.snapshots) qc.setQueryData(key, data)
},
onSettled: () => {
  void qc.invalidateQueries(...)
},
```

### PageState (loading/error)
**Source:** `apps/admin-app/src/components/feedback/PageState.tsx`
**Apply to:** ClientsPage, ClientPage, PlansPage and all child tab sections

```typescript
if (isPending) return <PageLoading />
if (isError) return <PageError onRetry={() => void refetch()} />
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `features/pt-packages/api.ts` plans CRUD portion | service | CRUD | No existing admin-app PT-package feature; pattern copied from plans/api.ts |

---

## Backend Path Corrections (planner alert)

- Payments client-detail read: `GET /api/v1/payments/by-client/{client_id}` — NOT `GET /payments?clientId=`. The path parameter is `client_id` (snake_case in URL pattern per FastAPI route definition).
- PT-package plans list query param: `includeArchived` (boolean) — NOT `active`. The backend `PtPackagePlanListQuery` uses `includeArchived`.
- PT-package sell body: `{ clientId, planId, amountKopecks }` — `amountKopecks` is required (backend validates `422 amount_mismatch` if it differs from plan price). Frontend must pre-fill from selected plan.
- PT-package cancel: `reason` is **required** (1–200 chars), unlike memberships cancel where `reason` is optional.
- `api/client.ts` needs NO changes — idempotency header passed via existing `headers` field in `StaffRequestInit`.

---

## Metadata

**Analog search scope:** `apps/admin-app/src/`, `apps/admin-web/src/features/`, `apps/backend/app/modules/`
**Files scanned:** 18 source files read
**Pattern extraction date:** 2026-06-13
