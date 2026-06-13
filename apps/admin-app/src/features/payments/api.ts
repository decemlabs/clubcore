/**
 * Payments domain TanStack Query hooks (Phase 101-04).
 *
 * Read-only: payments are fetched for client-detail display only.
 * No mutations — refund/edit actions live on the membership lifecycle (101-03 scope).
 *
 * Transport: staffRequest('get', '/api/v1/payments/by-client/{client_id}', { params: { client_id: clientId } })
 * → PaymentsListResponseSchema.parse(raw).data
 *
 * IMPORTANT: the path is /by-client/{client_id} (path param, NOT ?clientId= query).
 * The backend `require_payments_view_for_subject()` scopes access to that client's
 * payments — the global /payments route 403s for non-privileged staff (T-101-12-IDOR).
 *
 * ApiError re-exported (D-100-03-APIERROR-REEXPORT) so page/tab layers can
 * `instanceof ApiError` without importing @/api/client directly (ESLint boundary).
 */
import { useQuery } from '@tanstack/react-query'
import { staffRequest, ApiError } from '@/api/client'
import { PaymentsListResponseSchema } from './schemas'

// ---------------------------------------------------------------------------
// Key factory
// ---------------------------------------------------------------------------

export const paymentsKeys = {
  all: ['payments'] as const,
  byClient: (clientId: string) => [...paymentsKeys.all, 'byClient', clientId] as const,
}

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

/**
 * Fetch payments for a client via the scoped path:
 * GET /api/v1/payments/by-client/{client_id}
 *
 * Uses `params` (path interpolation), NOT `query` — the path has a {client_id}
 * placeholder, not a ?clientId= query string (per CONTEXT §Payments + PATTERNS §Backend Path Corrections).
 * Enabled only when clientId is truthy.
 */
export function usePaymentsByClient(clientId: string) {
  return useQuery({
    queryKey: paymentsKeys.byClient(clientId),
    queryFn: async () => {
      const raw = await staffRequest(
        'get',
        '/api/v1/payments/by-client/{client_id}',
        { params: { client_id: clientId } },
      )
      return PaymentsListResponseSchema.parse(raw).data
    },
    enabled: !!clientId,
    staleTime: 30_000,
  })
}

// ---------------------------------------------------------------------------
// Re-export for page/tab layers (ESLint import-boundary)
// ---------------------------------------------------------------------------

export { ApiError }
