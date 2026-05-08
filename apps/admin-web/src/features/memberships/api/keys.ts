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
  /**
   * Single source of truth for plan-list cache keys. Pass `undefined` to fetch
   * both active and archived plans; pass a boolean to filter. The loader and
   * the hook MUST pass the same value or prefetch is wasted (BLK-02).
   */
  plansList: (active: boolean | undefined) =>
    ['memberships', 'plans', 'list', { active }] as const,
  planDetail: (id: MembershipPlanId) => ['memberships', 'plans', 'detail', id] as const,
} as const
