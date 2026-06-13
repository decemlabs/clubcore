/**
 * PT-packages domain TanStack Query hooks — Plan-CRUD portion (Phase 101 MEM-01).
 *
 * This file covers the PT-package PLAN catalog CRUD (owner-only writes):
 *   usePtPackagePlans         — GET  /api/v1/pt-package-plans
 *   useCreatePtPackagePlan    — POST /api/v1/pt-package-plans (OWNER_ONLY)
 *   useUpdatePtPackagePlan    — PATCH /api/v1/pt-package-plans/{id} (name only, OWNER_ONLY)
 *   useDeletePtPackagePlan    — DELETE /api/v1/pt-package-plans/{id} (OWNER_ONLY)
 *
 * NOTE: PT-package plan list uses `includeArchived` query param (NOT `active`).
 * NOTE: PATCH sends only {name} — sessionCount/priceKopecks/validityDays are immutable.
 *
 * ── 101-03 section ────────────────────────────────────────────────────────────
 * The sell/cancel/refund/list-instance hooks are added in Phase 101 Plan 03 (101-03)
 * against the schemas already defined in ./schemas.ts. Add them here after this comment.
 * ────────────────────────────────────────────────────────────────────────────
 *
 * ApiError re-exported (D-100-03-APIERROR-REEXPORT) so page/modal layers can
 * `instanceof ApiError` without importing @/api/client directly (ESLint boundary).
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { staffRequest, ApiError } from '@/api/client'
import {
  PtPackagePlansListResponseSchema,
  PtPackagePlanSchema,
  type PtPackagePlanCreateInput,
  type PtPackagePlanUpdateInput,
  type PtPackagePlanData,
} from './schemas'

// ---------------------------------------------------------------------------
// Key factory
// ---------------------------------------------------------------------------

export const ptPackagesKeys = {
  all: ['pt-packages'] as const,
  plans: () => [...ptPackagesKeys.all, 'plans'] as const,
  planList: (filter?: { includeArchived?: boolean }) =>
    [...ptPackagesKeys.plans(), filter] as const,
  planDetail: (id: string) => [...ptPackagesKeys.plans(), 'detail', id] as const,
  // Instance keys (for 101-03 sell/lifecycle hooks)
  instances: () => [...ptPackagesKeys.all, 'instances'] as const,
  instanceList: (filter?: { clientId?: string }) =>
    [...ptPackagesKeys.instances(), filter] as const,
  instanceDetail: (id: string) => [...ptPackagesKeys.instances(), 'detail', id] as const,
}

// ---------------------------------------------------------------------------
// Queries — PT-Package Plans (catalog)
// ---------------------------------------------------------------------------

export function usePtPackagePlans(opts?: { includeArchived?: boolean }) {
  return useQuery({
    queryKey: ptPackagesKeys.planList(opts),
    // NOTE: query param is `includeArchived` (not `active`) per backend PtPackagePlanListQuery
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/pt-package-plans', {
        query: opts ?? {},
      })
      return PtPackagePlansListResponseSchema.parse(raw).data
    },
    staleTime: 30_000,
  })
}

// ---------------------------------------------------------------------------
// Mutations — PT-Package Plans (CRUD, OWNER_ONLY)
// ---------------------------------------------------------------------------

export function useCreatePtPackagePlan() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: PtPackagePlanCreateInput): Promise<PtPackagePlanData> => {
      const raw = await staffRequest('post', '/api/v1/pt-package-plans', { body })
      return PtPackagePlanSchema.parse((raw as { data: unknown }).data)
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: ptPackagesKeys.plans() })
    },
  })
}

export function useUpdatePtPackagePlan() {
  const qc = useQueryClient()
  return useMutation({
    // Only {name} is sent — other fields are immutable (extra='forbid' on backend)
    mutationFn: async ({
      id,
      body,
    }: {
      id: string
      body: PtPackagePlanUpdateInput
    }): Promise<PtPackagePlanData> => {
      const raw = await staffRequest('patch', '/api/v1/pt-package-plans/{plan_id}', {
        params: { plan_id: id },
        body,
      })
      return PtPackagePlanSchema.parse((raw as { data: unknown }).data)
    },
    onSettled: (_data, _err, vars) => {
      void qc.invalidateQueries({ queryKey: ptPackagesKeys.plans() })
      void qc.invalidateQueries({ queryKey: ptPackagesKeys.planDetail(vars.id) })
    },
  })
}

export function useDeletePtPackagePlan() {
  const qc = useQueryClient()
  return useMutation({
    // DELETE /pt-package-plans/{plan_id} → 204 No Content (no body to parse)
    mutationFn: (id: string) =>
      staffRequest('delete', '/api/v1/pt-package-plans/{plan_id}', { params: { plan_id: id } }),
    onSettled: (_data, _err, id) => {
      void qc.invalidateQueries({ queryKey: ptPackagesKeys.plans() })
      void qc.invalidateQueries({ queryKey: ptPackagesKeys.planDetail(id) })
    },
  })
}

// ---------------------------------------------------------------------------
// Re-export for page/modal layers (ESLint import-boundary — D-100-03-APIERROR-REEXPORT)
// ---------------------------------------------------------------------------

export { ApiError }
