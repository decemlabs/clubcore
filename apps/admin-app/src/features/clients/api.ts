/**
 * Clients domain TanStack Query hooks (Phase 101 CLI-01, CLI-03).
 *
 * Flipped from mock→http over the P100 `staffRequest` transport seam.
 * Follows the features/auth/api.ts exemplar (staffRequest + Schema.parse(raw).data).
 *
 * Key factory:
 *   clientsKeys.all          → ['clients']
 *   clientsKeys.lists()      → ['clients', 'list']
 *   clientsKeys.list(filter) → ['clients', 'list', filter]
 *   clientsKeys.details()    → ['clients', 'detail']
 *   clientsKeys.detail(id)   → ['clients', 'detail', id]
 *
 * Mutations:
 *   useCreateClient — POST /api/v1/clients; onSettled invalidates lists()
 *   useUpdateClient — PATCH /api/v1/clients/{id}; onSettled invalidates lists() + detail(id)
 *   useDeleteClient — DELETE /api/v1/clients/{id} (204); onSettled invalidates lists() + detail(id)
 *
 * ApiError re-exported (D-100-03-APIERROR-REEXPORT) so page/modal layers can
 * `instanceof ApiError` without importing @/api/client directly (ESLint boundary).
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { staffRequest, ApiError } from '@/api/client'
import {
  ClientsListResponseSchema,
  ClientSchema,
  type ClientData,
  type ClientCreateInput,
  type ClientUpdateInput,
} from './schemas'
import { filterToQuery, type ClientsListQuery } from './query'

// ---------------------------------------------------------------------------
// Key factory
// ---------------------------------------------------------------------------

export const clientsKeys = {
  all: ['clients'] as const,
  lists: () => [...clientsKeys.all, 'list'] as const,
  list: (filter: ClientsListQuery) => [...clientsKeys.lists(), filter] as const,
  details: () => [...clientsKeys.all, 'detail'] as const,
  detail: (id: string) => [...clientsKeys.details(), id] as const,
}

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

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
      const raw = await staffRequest('get', '/api/v1/clients/{client_id}', { params: { client_id: id } })
      return ClientSchema.parse((raw as { data: unknown }).data)
    },
    enabled: !!id,
    staleTime: 30_000,
  })
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

export function useCreateClient() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: ClientCreateInput): Promise<ClientData> => {
      const raw = await staffRequest('post', '/api/v1/clients', { body })
      return ClientSchema.parse((raw as { data: unknown }).data)
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: clientsKeys.lists() })
    },
  })
}

export function useUpdateClient() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      id,
      body,
    }: {
      id: string
      body: ClientUpdateInput
    }): Promise<ClientData> => {
      const raw = await staffRequest('patch', '/api/v1/clients/{client_id}', {
        params: { client_id: id },
        body,
      })
      return ClientSchema.parse((raw as { data: unknown }).data)
    },
    onSettled: (_data, _err, vars) => {
      void qc.invalidateQueries({ queryKey: clientsKeys.lists() })
      void qc.invalidateQueries({ queryKey: clientsKeys.detail(vars.id) })
    },
  })
}

export function useDeleteClient() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      staffRequest('delete', '/api/v1/clients/{client_id}', { params: { client_id: id } }),
    onSettled: (_data, _err, id) => {
      void qc.invalidateQueries({ queryKey: clientsKeys.lists() })
      void qc.invalidateQueries({ queryKey: clientsKeys.detail(id) })
    },
  })
}

// ---------------------------------------------------------------------------
// Re-export for page/modal layers (ESLint import-boundary — D-100-03-APIERROR-REEXPORT)
// ---------------------------------------------------------------------------

export { ApiError }
