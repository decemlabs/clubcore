import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { membershipsKeys } from './keys'
import { services } from '@/shared/api/services'
import type {
  MembershipsListQuery,
  MembershipCreateInput,
  MembershipPlanCreateInput,
  MembershipPlanUpdateInput,
} from '@/shared/api/contracts/memberships'
import type { Membership, MembershipId, MembershipPlanId, Pagination } from '@/entities/membership'

export function useMembershipsByClient(clientId: string) {
  return useQuery({
    queryKey: membershipsKeys.byClient(clientId),
    queryFn: () => services.memberships.byClient(clientId),
    enabled: !!clientId,
    staleTime: 30_000,
  })
}

export function useMembershipsList(query: MembershipsListQuery) {
  return useQuery({
    queryKey: membershipsKeys.list(query),
    queryFn: () => services.memberships.list(query),
    staleTime: 30_000,
  })
}

export function useMembershipPlans({ active = true }: { active?: boolean } = {}) {
  return useQuery({
    queryKey: [...membershipsKeys.plans, { active }],
    queryFn: () => services.memberships.listPlans({ active }),
    staleTime: 30_000,
  })
}

export function useMembership(id: MembershipId) {
  return useQuery({
    queryKey: membershipsKeys.detail(id),
    queryFn: () => services.memberships.get(id),
    enabled: !!id,
    staleTime: 30_000,
  })
}

export function useCreateMembership() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: MembershipCreateInput) => services.memberships.create(input),
    onSettled: (_data, _err, vars) => {
      void qc.invalidateQueries({ queryKey: membershipsKeys.lists() })
      void qc.invalidateQueries({ queryKey: membershipsKeys.byClient(vars.clientId) })
    },
  })
}

type CancelVars = { membershipId: MembershipId; reason?: string }

export function useCancelMembership() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ membershipId, reason }: CancelVars) =>
      services.memberships.cancel(membershipId, reason),
    onMutate: async ({ membershipId }) => {
      await qc.cancelQueries({ queryKey: membershipsKeys.lists() })
      const snapshots = qc.getQueriesData<Pagination<Membership>>({
        queryKey: membershipsKeys.lists(),
      })
      for (const [key, data] of snapshots) {
        if (!data) continue
        qc.setQueryData<Pagination<Membership>>(key, {
          ...data,
          items: data.items.map((m) =>
            m.id === membershipId ? { ...m, status: 'cancelled' } : m,
          ),
        })
      }
      return { snapshots }
    },
    onError: (_err, _vars, ctx) => {
      if (!ctx) return
      for (const [key, data] of ctx.snapshots) qc.setQueryData(key, data)
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: membershipsKeys.lists() })
    },
  })
}

export function useCreatePlan() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: MembershipPlanCreateInput) => services.memberships.createPlan(input),
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: membershipsKeys.plans })
    },
  })
}

type UpdatePlanVars = { id: MembershipPlanId; input: MembershipPlanUpdateInput }

export function useUpdatePlan() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, input }: UpdatePlanVars) => services.memberships.updatePlan(id, input),
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: membershipsKeys.plans })
    },
  })
}

export function useDeletePlan() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: MembershipPlanId) => services.memberships.deletePlan(id),
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: membershipsKeys.plans })
    },
  })
}
