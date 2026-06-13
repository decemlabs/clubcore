/**
 * Visits domain TanStack Query hooks (Phase 101-04).
 *
 * Read-only: visits are fetched for client-detail display only.
 * No mutations — visits are written via the check-in flow (Phase 103 scope).
 *
 * Transport: staffRequest('get', '/api/v1/visits', { query: { clientId } })
 * → VisitsListResponseSchema.parse(raw).data
 *
 * ApiError re-exported (D-100-03-APIERROR-REEXPORT) so page/tab layers can
 * `instanceof ApiError` without importing @/api/client directly (ESLint boundary).
 */
import { useQuery } from '@tanstack/react-query'
import { staffRequest, ApiError } from '@/api/client'
import { VisitsListResponseSchema } from './schemas'

// ---------------------------------------------------------------------------
// Key factory
// ---------------------------------------------------------------------------

export const visitsKeys = {
  all: ['visits'] as const,
  byClient: (clientId: string) => [...visitsKeys.all, 'byClient', clientId] as const,
}

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

/**
 * Fetch visits for a client (GET /api/v1/visits?clientId=…).
 * Enabled only when clientId is truthy.
 */
export function useClientVisits(clientId: string) {
  return useQuery({
    queryKey: visitsKeys.byClient(clientId),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/visits', {
        query: { clientId },
      })
      return VisitsListResponseSchema.parse(raw).data
    },
    enabled: !!clientId,
    staleTime: 30_000,
  })
}

// ---------------------------------------------------------------------------
// Re-export for page/tab layers (ESLint import-boundary)
// ---------------------------------------------------------------------------

export { ApiError }
