/**
 * Memberships domain query-key factory (Phase 101-03).
 *
 * Hierarchy:
 *   all → lists() → list(filter)
 *       → details() → detail(id)
 *       → byClient(clientId)
 *
 * Following the admin-web memberships/api/keys.ts pattern exactly.
 */

export type MembershipsListQuery = {
  clientId?: string
  status?: string
  sort?: string
  expiring?: boolean
  within?: number
  page?: number
  pageSize?: number
}

export const membershipsKeys = {
  all: ['memberships'] as const,
  lists: () => [...membershipsKeys.all, 'list'] as const,
  list: (filter: MembershipsListQuery) => [...membershipsKeys.lists(), filter] as const,
  details: () => [...membershipsKeys.all, 'detail'] as const,
  detail: (id: string) => [...membershipsKeys.details(), id] as const,
  byClient: (clientId: string) => [...membershipsKeys.all, 'byClient', clientId] as const,
} as const
