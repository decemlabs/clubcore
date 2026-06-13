/**
 * Memberships domain TanStack Query hooks (Phase 101-03 MEM-02/MEM-03).
 *
 * Lifecycle mutations:
 *   useSellMembership    — POST /memberships + Idempotency-Key (non-optimistic)
 *   useFreezeMembership  — POST /memberships/{membership_id}/freeze + Idempotency-Key (OPTIMISTIC)
 *   useUnfreezeMembership— POST /memberships/{membership_id}/unfreeze + Idempotency-Key (OPTIMISTIC)
 *   useRenewMembership   — POST /memberships/{membership_id}/renew + Idempotency-Key (non-optimistic)
 *   useCancelMembership  — POST /memberships/{membership_id}/cancel + Idempotency-Key (OWNER_ONLY, non-optimistic)
 *   useRefundMembership  — POST /memberships/{membership_id}/refund (NO Idempotency-Key per UI-SPEC §3.2, non-optimistic)
 *
 * Idempotency-Key: crypto.randomUUID() called INSIDE mutationFn at submit time
 * (per-attempt UUID). Never called at hook init — each user-initiated attempt
 * carries a fresh key. Refund is the sole exception (no key sent).
 *
 * freeze/unfreeze are the ONLY optimistic mutations (onMutate→cancelQueries→
 * snapshot→setQueryData→onError rollback→onSettled invalidate).
 * All others are non-optimistic (invalidate + toast on success; toast on error).
 *
 * ApiError re-exported (D-100-03-APIERROR-REEXPORT) so page/modal layers
 * can `instanceof ApiError` without importing @/api/client directly (ESLint boundary).
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { staffRequest, ApiError } from '@/api/client'
import { formatRub, formatDateRu } from '@/lib/format'
import { membershipsKeys } from './keys'
import {
  MembershipsListResponseSchema,
  MembershipSchema,
  type MembershipData,
  type MembershipSellInput,
  type MembershipCancelInput,
  type MembershipRefundInput,
} from './schemas'

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

/** Fetch all memberships for a client (GET /api/v1/memberships?clientId=). */
export function useMembershipsByClient(clientId: string) {
  return useQuery({
    queryKey: membershipsKeys.byClient(clientId),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/memberships', {
        query: { clientId },
      })
      return MembershipsListResponseSchema.parse(raw).data
    },
    enabled: !!clientId,
    staleTime: 30_000,
  })
}

/** Fetch a single membership by id (GET /api/v1/memberships/{membership_id}). */
export function useMembership(id: string) {
  return useQuery({
    queryKey: membershipsKeys.detail(id),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/memberships/{membership_id}', {
        params: { membership_id: id },
      })
      return MembershipSchema.parse((raw as { data: unknown }).data)
    },
    enabled: !!id,
    staleTime: 30_000,
  })
}

// ---------------------------------------------------------------------------
// Mutation — Sell (non-optimistic)
// ---------------------------------------------------------------------------

/**
 * Sell a membership (POST /api/v1/memberships).
 * Idempotency-Key generated per attempt inside mutationFn (T-101-08-DOUBLECHARGE).
 */
export function useSellMembership() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: MembershipSellInput) => {
      // crypto.randomUUID() called at submit time — fresh key per attempt
      const raw = await staffRequest('post', '/api/v1/memberships', {
        body,
        headers: { 'Idempotency-Key': crypto.randomUUID() },
      })
      return MembershipSchema.parse((raw as { data: unknown }).data)
    },
    onSuccess: (data) => {
      const desc = `Оплата ${formatRub(data.paidAmountKopecks)} принята.`
      toast.success('Абонемент оформлен', { description: desc })
      void qc.invalidateQueries({ queryKey: membershipsKeys.lists() })
      void qc.invalidateQueries({ queryKey: membershipsKeys.byClient(data.clientId) })
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : undefined
      toast.error(
        msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.',
      )
    },
  })
}

// ---------------------------------------------------------------------------
// Mutation — Freeze (OPTIMISTIC)
// ---------------------------------------------------------------------------

type FreezeVars = { membershipId: string; clientId: string }
type OptimisticCtx = {
  listSnapshots: [readonly unknown[], { items: MembershipData[] } | undefined][]
  detailSnapshot: MembershipData | undefined
}

/**
 * Freeze a membership (POST /api/v1/memberships/{membership_id}/freeze).
 * Optimistic: flips status to 'frozen', injects placeholder currentFreezePeriod.
 * Rolls back to snapshot on error; invalidates on settle.
 */
export function useFreezeMembership() {
  const qc = useQueryClient()
  return useMutation<unknown, Error, FreezeVars, OptimisticCtx>({
    mutationFn: async ({ membershipId }: FreezeVars) =>
      staffRequest('post', '/api/v1/memberships/{membership_id}/freeze', {
        params: { membership_id: membershipId },
        body: {},
        headers: { 'Idempotency-Key': crypto.randomUUID() },
      }),
    onMutate: async ({ membershipId }: FreezeVars) => {
      await qc.cancelQueries({ queryKey: membershipsKeys.lists() })
      await qc.cancelQueries({ queryKey: membershipsKeys.detail(membershipId) })

      const listSnapshots = qc.getQueriesData<{ items: MembershipData[] }>({
        queryKey: membershipsKeys.lists(),
      })
      const detailSnapshot = qc.getQueryData<MembershipData>(membershipsKeys.detail(membershipId))

      const optimisticFreezePeriod = {
        id: 'optimistic',
        startedAt: new Date().toISOString(),
        startedBy: '',
        endedAt: null,
        endedBy: null,
      }

      // Optimistic: flip status → 'frozen', inject placeholder currentFreezePeriod
      for (const [key, data] of listSnapshots) {
        if (!data) continue
        qc.setQueryData(key, {
          ...data,
          items: data.items.map((m) =>
            m.id === membershipId
              ? { ...m, status: 'frozen', currentFreezePeriod: optimisticFreezePeriod }
              : m,
          ),
        })
      }
      if (detailSnapshot) {
        qc.setQueryData(membershipsKeys.detail(membershipId), {
          ...detailSnapshot,
          status: 'frozen',
          currentFreezePeriod: optimisticFreezePeriod,
        })
      }

      return { listSnapshots, detailSnapshot }
    },
    onError: (_err, vars, ctx) => {
      if (!ctx) return
      for (const [key, data] of ctx.listSnapshots) {
        qc.setQueryData(key as readonly unknown[], data)
      }
      if (ctx.detailSnapshot) {
        qc.setQueryData(membershipsKeys.detail(vars.membershipId), ctx.detailSnapshot)
      }
      toast.error('Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.')
    },
    onSettled: (_data, _err, vars) => {
      void qc.invalidateQueries({ queryKey: membershipsKeys.lists() })
      void qc.invalidateQueries({ queryKey: membershipsKeys.detail(vars.membershipId) })
      void qc.invalidateQueries({ queryKey: membershipsKeys.byClient(vars.clientId) })
      toast.success('Абонемент заморожен')
    },
  })
}

// ---------------------------------------------------------------------------
// Mutation — Unfreeze (OPTIMISTIC)
// ---------------------------------------------------------------------------

type UnfreezeVars = { membershipId: string; clientId: string }

/**
 * Unfreeze a membership (POST /api/v1/memberships/{membership_id}/unfreeze).
 * Optimistic: flips status to 'active', clears currentFreezePeriod to null.
 * Rolls back to snapshot on error; invalidates on settle.
 */
export function useUnfreezeMembership() {
  const qc = useQueryClient()
  return useMutation<unknown, Error, UnfreezeVars, OptimisticCtx>({
    mutationFn: async ({ membershipId }: UnfreezeVars) =>
      staffRequest('post', '/api/v1/memberships/{membership_id}/unfreeze', {
        params: { membership_id: membershipId },
        body: {},
        headers: { 'Idempotency-Key': crypto.randomUUID() },
      }),
    onMutate: async ({ membershipId }: UnfreezeVars) => {
      await qc.cancelQueries({ queryKey: membershipsKeys.lists() })
      await qc.cancelQueries({ queryKey: membershipsKeys.detail(membershipId) })

      const listSnapshots = qc.getQueriesData<{ items: MembershipData[] }>({
        queryKey: membershipsKeys.lists(),
      })
      const detailSnapshot = qc.getQueryData<MembershipData>(membershipsKeys.detail(membershipId))

      // Optimistic: flip status → 'active', clear currentFreezePeriod
      for (const [key, data] of listSnapshots) {
        if (!data) continue
        qc.setQueryData(key, {
          ...data,
          items: data.items.map((m) =>
            m.id === membershipId
              ? { ...m, status: 'active', currentFreezePeriod: null }
              : m,
          ),
        })
      }
      if (detailSnapshot) {
        qc.setQueryData(membershipsKeys.detail(membershipId), {
          ...detailSnapshot,
          status: 'active',
          currentFreezePeriod: null,
        })
      }

      return { listSnapshots, detailSnapshot }
    },
    onError: (_err, vars, ctx) => {
      if (!ctx) return
      for (const [key, data] of ctx.listSnapshots) {
        qc.setQueryData(key as readonly unknown[], data)
      }
      if (ctx.detailSnapshot) {
        qc.setQueryData(membershipsKeys.detail(vars.membershipId), ctx.detailSnapshot)
      }
      toast.error('Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.')
    },
    onSettled: (_data, _err, vars) => {
      void qc.invalidateQueries({ queryKey: membershipsKeys.lists() })
      void qc.invalidateQueries({ queryKey: membershipsKeys.detail(vars.membershipId) })
      void qc.invalidateQueries({ queryKey: membershipsKeys.byClient(vars.clientId) })
      toast.success('Абонемент разморожен')
    },
  })
}

// ---------------------------------------------------------------------------
// Mutation — Renew (non-optimistic)
// ---------------------------------------------------------------------------

/**
 * Renew a membership (POST /api/v1/memberships/{membership_id}/renew, 201).
 * Backend extends by one plan duration — no period parameter needed.
 */
export function useRenewMembership() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      membershipId,
    }: {
      membershipId: string
      clientId: string
    }) => {
      const raw = await staffRequest('post', '/api/v1/memberships/{membership_id}/renew', {
        params: { membership_id: membershipId },
        body: {},
        headers: { 'Idempotency-Key': crypto.randomUUID() },
      })
      return MembershipSchema.parse((raw as { data: unknown }).data)
    },
    onSuccess: (data) => {
      const desc = `Действует до ${formatDateRu(data.endDate, 'd MMMM yyyy')}.`
      toast.success('Абонемент продлён', { description: desc })
      void qc.invalidateQueries({ queryKey: membershipsKeys.lists() })
      void qc.invalidateQueries({ queryKey: membershipsKeys.detail(data.id) })
      void qc.invalidateQueries({ queryKey: membershipsKeys.byClient(data.clientId) })
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : undefined
      toast.error(
        msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.',
      )
    },
  })
}

// ---------------------------------------------------------------------------
// Mutation — Cancel (non-optimistic, OWNER_ONLY)
// ---------------------------------------------------------------------------

/**
 * Cancel a membership (POST /api/v1/memberships/{membership_id}/cancel).
 * OWNER_ONLY — can(role,'cancel','memberships') gates the button in the UI.
 * A 403 that still reaches the client surfaces as a non-blocking toast.
 */
export function useCancelMembership() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      membershipId,
      body,
    }: {
      membershipId: string
      body: MembershipCancelInput
    }) => {
      const raw = await staffRequest('post', '/api/v1/memberships/{membership_id}/cancel', {
        params: { membership_id: membershipId },
        body,
        headers: { 'Idempotency-Key': crypto.randomUUID() },
      })
      return MembershipSchema.parse((raw as { data: unknown }).data)
    },
    onSuccess: (data) => {
      toast.success('Абонемент отменён')
      void qc.invalidateQueries({ queryKey: membershipsKeys.lists() })
      void qc.invalidateQueries({ queryKey: membershipsKeys.detail(data.id) })
      void qc.invalidateQueries({ queryKey: membershipsKeys.byClient(data.clientId) })
    },
    onError: (err) => {
      if (
        err instanceof ApiError &&
        (err.code === 'forbidden' || err.message.toLowerCase().includes('forbidden'))
      ) {
        toast.error('Недостаточно прав', {
          description: 'Отмена абонемента доступна только владельцу.',
        })
      } else {
        const msg = err instanceof ApiError ? err.message : undefined
        toast.error(
          msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.',
        )
      }
    },
  })
}

// ---------------------------------------------------------------------------
// Mutation — Refund (non-optimistic, NO Idempotency-Key per UI-SPEC §3.2)
// ---------------------------------------------------------------------------

/**
 * Refund a membership (POST /api/v1/memberships/{membership_id}/refund).
 * Full-refund only — no amount field (backend forbids amountKopecks).
 * Reason required 1-200 chars.
 * NO Idempotency-Key (refund is idempotent by nature; backend does not specify one).
 */
export function useRefundMembership() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      membershipId,
      body,
    }: {
      membershipId: string
      body: MembershipRefundInput
    }) =>
      staffRequest('post', '/api/v1/memberships/{membership_id}/refund', {
        params: { membership_id: membershipId },
        body,
        // Deliberately NO Idempotency-Key header (UI-SPEC §3.2)
      }),
    onSuccess: (_data, vars) => {
      toast.success('Возврат оформлен', { description: 'Средства будут возвращены клиенту.' })
      void qc.invalidateQueries({ queryKey: membershipsKeys.detail(vars.membershipId) })
      void qc.invalidateQueries({ queryKey: membershipsKeys.lists() })
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : undefined
      toast.error(
        msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.',
      )
    },
  })
}

// ---------------------------------------------------------------------------
// Re-export for page/modal layers (ESLint import-boundary)
// ---------------------------------------------------------------------------

export { ApiError }
