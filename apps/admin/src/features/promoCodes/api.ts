/**
 * Promo codes domain TanStack Query hooks (Phase 113 PROMO-01/02).
 *
 * Staff CRUD over the promo_codes backend module:
 *   list (both roles), create/update/deactivate (owner-only via can()).
 *
 * Key factory:
 *   promoCodesKeys.all           → ['promo-codes']
 *   promoCodesKeys.lists()       → ['promo-codes', 'list']
 *   promoCodesKeys.list(filter)  → ['promo-codes', 'list', filter]
 *   promoCodesKeys.detail(id)    → ['promo-codes', 'detail', id]
 *
 * CSRF: staffRequest auto-attaches X-CSRF-Token for POST/PATCH — no
 * manual header needed.
 *
 * ApiError re-exported (D-100-03-APIERROR-REEXPORT) so page/modal layers can
 * `instanceof ApiError` without importing @/api/client directly.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { staffRequest, ApiError } from '@/api/client'
import { can } from '@/shared/session/can'
import type { Role } from '@/shared/session/types'
import {
  PromoCodesListResponseSchema,
  PromoCodeWriteResponseSchema,
  type PromoCodeCreateInput,
  type PromoCodeUpdateInput,
} from './schemas'

// ---------------------------------------------------------------------------
// Key factory
// ---------------------------------------------------------------------------

export const promoCodesKeys = {
  all: ['promo-codes'] as const,
  lists: () => [...promoCodesKeys.all, 'list'] as const,
  list: (filter?: { active?: boolean; page?: number }) =>
    [...promoCodesKeys.lists(), filter] as const,
  detail: (id: string) => [...promoCodesKeys.all, 'detail', id] as const,
}

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

/**
 * Promo codes list. Both roles can view — enabled: can(role, 'list', 'promo-codes').
 * The backend returns 403 for truly unauthorized callers; can() here mirrors it.
 */
export function usePromoCodes(opts: { active?: boolean; page?: number }, role: Role) {
  return useQuery({
    queryKey: promoCodesKeys.list(opts),
    queryFn: async () => {
      const raw = await staffRequest(
        'get',
        '/api/v1/promo-codes',
        { query: opts },
      )
      return PromoCodesListResponseSchema.parse(raw).data
    },
    enabled: can(role, 'list', 'promo-codes'),
    staleTime: 30_000,
  })
}

// ---------------------------------------------------------------------------
// Mutations — all onSettled invalidate promoCodesKeys.lists()
// ---------------------------------------------------------------------------

/**
 * Create a new promo code.
 * POST /api/v1/promo-codes
 * Returns PromoCodeData.
 * May throw ApiError with code: promo_code_already_exists (409)
 */
export function useCreatePromoCode() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: PromoCodeCreateInput) => {
      const raw = await staffRequest(
        'post',
        '/api/v1/promo-codes',
        { body },
      )
      return PromoCodeWriteResponseSchema.parse((raw as { data: unknown }).data)
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: promoCodesKeys.lists() })
    },
  })
}

/**
 * Update an existing promo code.
 * PATCH /api/v1/promo-codes/{promo_id}
 * Returns updated PromoCodeData.
 * May throw ApiError with code: promo_code_already_exists (409)
 */
export function useUpdatePromoCode() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, body }: { id: string; body: PromoCodeUpdateInput }) => {
      const raw = await staffRequest(
        'patch',
        '/api/v1/promo-codes/{promo_id}',
        { params: { promo_id: id }, body },
      )
      return PromoCodeWriteResponseSchema.parse((raw as { data: unknown }).data)
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: promoCodesKeys.lists() })
    },
  })
}

/**
 * Deactivate a promo code (soft — sets is_active=False).
 * PATCH /api/v1/promo-codes/{promo_id}/deactivate
 * Returns 204 No Content.
 */
export function useDeactivatePromoCode() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      staffRequest(
        'patch',
        '/api/v1/promo-codes/{promo_id}/deactivate',
        { params: { promo_id: id } },
      ),
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: promoCodesKeys.lists() })
    },
  })
}

// ---------------------------------------------------------------------------
// Re-export for page/modal layers (ESLint import-boundary — D-100-03-APIERROR-REEXPORT)
// ---------------------------------------------------------------------------

export { ApiError }
