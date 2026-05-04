import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { clientsKeys } from './keys'
import { services } from '@/shared/api/services'
import type {
  ClientsListQuery,
  ClientCreateInput,
  ClientUpdateInput,
} from '@/shared/api/contracts/clients'
import type { Client, ClientId, Pagination } from '@/entities/client'

export function useClientsList(query: ClientsListQuery) {
  return useQuery({
    queryKey: clientsKeys.list(query),
    queryFn: () => services.clients.list(query),
  })
}

export function useClient(id: ClientId) {
  return useQuery({
    queryKey: clientsKeys.detail(id),
    queryFn: () => services.clients.get(id),
    enabled: !!id,
  })
}

export function useCreateClient() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: ClientCreateInput) => services.clients.create(input),
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: clientsKeys.lists() })
    },
  })
}

type UpdateVars = { id: ClientId; input: ClientUpdateInput }

export function useUpdateClient() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, input }: UpdateVars) => services.clients.update(id, input),
    onMutate: async ({ id, input }) => {
      await qc.cancelQueries({ queryKey: clientsKeys.lists() })
      await qc.cancelQueries({ queryKey: clientsKeys.detail(id) })
      const listSnapshots = qc.getQueriesData<Pagination<Client>>({ queryKey: clientsKeys.lists() })
      const detailSnapshot = qc.getQueryData<Client>(clientsKeys.detail(id))
      for (const [key, data] of listSnapshots) {
        if (!data) continue
        const items = data.items.map((c) => (c.id === id ? { ...c, ...input } : c))
        qc.setQueryData<Pagination<Client>>(key, { ...data, items })
      }
      if (detailSnapshot) {
        qc.setQueryData<Client>(clientsKeys.detail(id), { ...detailSnapshot, ...input })
      }
      return { listSnapshots, detailSnapshot }
    },
    onError: (_err, vars, ctx) => {
      if (!ctx) return
      for (const [key, data] of ctx.listSnapshots) qc.setQueryData(key, data)
      if (ctx.detailSnapshot) qc.setQueryData(clientsKeys.detail(vars.id), ctx.detailSnapshot)
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
    mutationFn: (id: ClientId) => services.clients.remove(id),
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: clientsKeys.lists() })
      const snapshots = qc.getQueriesData<Pagination<Client>>({ queryKey: clientsKeys.lists() })
      for (const [key, data] of snapshots) {
        if (!data) continue
        qc.setQueryData<Pagination<Client>>(key, {
          ...data,
          items: data.items.filter((c) => c.id !== id),
          total: Math.max(0, data.total - 1),
        })
      }
      return { snapshots }
    },
    onError: (_err, _id, ctx) => {
      if (!ctx) return
      for (const [key, data] of ctx.snapshots) qc.setQueryData(key, data)
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: clientsKeys.lists() })
    },
  })
}
