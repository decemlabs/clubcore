/**
 * Membership-plans domain TanStack Query hooks (Phase 101 MEM-01).
 *
 * Flipped from mock→http over the P100 `staffRequest` transport seam.
 * Follows the features/auth/api.ts exemplar (staffRequest + Schema.parse(raw).data).
 *
 * Key factory:
 *   plansKeys.all            → ['plans']
 *   plansKeys.lists()        → ['plans', 'list']
 *   plansKeys.list(filter)   → ['plans', 'list', filter]
 *   plansKeys.detail(id)     → ['plans', 'detail', id]
 *
 * Mutations:
 *   useCreatePlan  — POST   /api/v1/membership-plans; onSettled invalidates lists()
 *   useUpdatePlan  — PATCH  /api/v1/membership-plans/{id}; onSettled invalidates lists() + detail(id)
 *   useDeletePlan  — DELETE /api/v1/membership-plans/{id} (204); onSettled invalidates lists() + detail(id)
 *
 * durationDays immutability: the update schema omits it client-side.
 * A backend 422 surfaces as «Длительность тарифа нельзя изменить после создания».
 *
 * ApiError re-exported (D-100-03-APIERROR-REEXPORT) so page/modal layers can
 * `instanceof ApiError` without importing @/api/client directly (ESLint boundary).
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { staffRequest, ApiError } from '@/api/client'
import {
  PlansListResponseSchema,
  MembershipPlanSchema,
  type MembershipPlanCreateInput,
  type MembershipPlanUpdateInput,
  type MembershipPlanData,
} from './schemas'

// ---------------------------------------------------------------------------
// Key factory
// ---------------------------------------------------------------------------

export const plansKeys = {
  all: ['plans'] as const,
  lists: () => [...plansKeys.all, 'list'] as const,
  list: (filter?: { active?: boolean; page?: number; pageSize?: number }) =>
    [...plansKeys.lists(), filter] as const,
  detail: (id: string) => [...plansKeys.all, 'detail', id] as const,
}

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

export function useCreatePlan() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: MembershipPlanCreateInput): Promise<MembershipPlanData> => {
      const raw = await staffRequest('post', '/api/v1/membership-plans', { body })
      return MembershipPlanSchema.parse((raw as { data: unknown }).data)
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: plansKeys.lists() })
    },
  })
}

export function useUpdatePlan() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      id,
      body,
    }: {
      id: string
      body: MembershipPlanUpdateInput
    }): Promise<MembershipPlanData> => {
      const raw = await staffRequest('patch', '/api/v1/membership-plans/{plan_id}', {
        params: { plan_id: id },
        body,
      })
      return MembershipPlanSchema.parse((raw as { data: unknown }).data)
    },
    onSettled: (_data, _err, vars) => {
      void qc.invalidateQueries({ queryKey: plansKeys.lists() })
      void qc.invalidateQueries({ queryKey: plansKeys.detail(vars.id) })
    },
  })
}

export function useDeletePlan() {
  const qc = useQueryClient()
  return useMutation({
    // DELETE /membership-plans/{plan_id} → 204 No Content (no body to parse)
    mutationFn: (id: string) =>
      staffRequest('delete', '/api/v1/membership-plans/{plan_id}', { params: { plan_id: id } }),
    onSettled: (_data, _err, id) => {
      void qc.invalidateQueries({ queryKey: plansKeys.lists() })
      void qc.invalidateQueries({ queryKey: plansKeys.detail(id) })
    },
  })
}

// ---------------------------------------------------------------------------
// Re-export for page/modal layers (ESLint import-boundary — D-100-03-APIERROR-REEXPORT)
// ---------------------------------------------------------------------------

export { ApiError }
