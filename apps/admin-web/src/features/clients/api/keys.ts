import type { ClientsListQuery } from '@/shared/api/contracts/clients'
import type { ClientId } from '@/entities/client'

export const clientsKeys = {
  all: ['clients'] as const,
  lists: () => [...clientsKeys.all, 'list'] as const,
  list: (filter: ClientsListQuery) => [...clientsKeys.lists(), filter] as const,
  details: () => [...clientsKeys.all, 'detail'] as const,
  detail: (id: ClientId) => [...clientsKeys.details(), id] as const,
} as const
