import type { MembershipsListQuery } from '@/shared/api/contracts/memberships'
import type { MembershipId, MembershipPlanId } from '@/entities/membership'

export const membershipsKeys = {
  all: ['memberships'] as const,
  lists: () => [...membershipsKeys.all, 'list'] as const,
  list: (filter: MembershipsListQuery) => [...membershipsKeys.lists(), filter] as const,
  details: () => [...membershipsKeys.all, 'detail'] as const,
  detail: (id: MembershipId) => [...membershipsKeys.details(), id] as const,
  byClient: (clientId: string) => [...membershipsKeys.all, 'byClient', clientId] as const,
  plans: ['memberships', 'plans'] as const,
  planDetail: (id: MembershipPlanId) => ['memberships', 'plans', 'detail', id] as const,
} as const
