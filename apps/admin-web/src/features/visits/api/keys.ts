import type { VisitsListQuery } from '@/shared/api/contracts/visits'

export const visitsKeys = {
  all: ['visits'] as const,
  lists: () => [...visitsKeys.all, 'list'] as const,
  list: (filter: VisitsListQuery) => [...visitsKeys.lists(), filter] as const,
  recentByClient: (clientId: string, opts: { limit: number }) =>
    [...visitsKeys.all, 'recentByClient', clientId, opts] as const,
  gymMeta: ['visits', 'gymMeta'] as const,
} as const
