import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { toast } from 'sonner'
import { membershipsKeys } from './keys'
import { services } from '@/shared/api/services'
import { isDomainError } from '@/shared/api/errors'
import { t } from '@/shared/i18n'
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

export function useMembershipPlans(opts?: {
  active?: boolean
  page?: number
  pageSize?: number
}) {
  const active = opts?.active // undefined OR boolean — undefined means "all plans"
  const page = opts?.page
  const pageSize = opts?.pageSize
  return useQuery({
    queryKey: membershipsKeys.plansList(active, page, pageSize),
    queryFn: () =>
      services.memberships.listPlans({
        ...(active === undefined ? {} : { active }),
        ...(page === undefined ? {} : { page }),
        ...(pageSize === undefined ? {} : { pageSize }),
      }),
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

type FreezeVars = { membershipId: MembershipId; clientId: string }

export function useFreezeMembership() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ membershipId }: FreezeVars) => services.memberships.freeze(membershipId),
    onMutate: async ({ membershipId }) => {
      await qc.cancelQueries({ queryKey: membershipsKeys.lists() })
      await qc.cancelQueries({ queryKey: membershipsKeys.detail(membershipId) })
      const listSnapshots = qc.getQueriesData<Pagination<Membership>>({
        queryKey: membershipsKeys.lists(),
      })
      const detailSnapshot = qc.getQueryData<Membership>(membershipsKeys.detail(membershipId))
      for (const [key, data] of listSnapshots) {
        if (!data) continue
        qc.setQueryData<Pagination<Membership>>(key, {
          ...data,
          items: data.items.map((m) =>
            m.id === membershipId
              ? {
                  ...m,
                  status: 'frozen',
                  currentFreezePeriod: {
                    id: 'optimistic',
                    startedAt: new Date().toISOString(),
                    startedBy: '',
                    endedAt: null,
                    endedBy: null,
                  },
                }
              : m,
          ),
        })
      }
      if (detailSnapshot) {
        qc.setQueryData<Membership>(membershipsKeys.detail(membershipId), {
          ...detailSnapshot,
          status: 'frozen',
          currentFreezePeriod: {
            id: 'optimistic',
            startedAt: new Date().toISOString(),
            startedBy: '',
            endedAt: null,
            endedBy: null,
          },
        })
      }
      return { listSnapshots, detailSnapshot }
    },
    onError: (err, vars, ctx) => {
      if (!ctx) return
      for (const [key, data] of ctx.listSnapshots) qc.setQueryData(key, data)
      if (ctx.detailSnapshot) {
        qc.setQueryData(membershipsKeys.detail(vars.membershipId), ctx.detailSnapshot)
      }
      toast.error(
        isDomainError(err)
          ? t(`memberships.freeze.errors.${err.code}` as Parameters<typeof t>[0])
          : t('common.errors.network'),
      )
    },
    onSettled: (_data, _err, vars) => {
      void qc.invalidateQueries({ queryKey: membershipsKeys.lists() })
      void qc.invalidateQueries({ queryKey: membershipsKeys.detail(vars.membershipId) })
      void qc.invalidateQueries({ queryKey: membershipsKeys.byClient(vars.clientId) })
    },
  })
}

type UnfreezeVars = { membershipId: MembershipId; clientId: string }

export function useUnfreezeMembership() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ membershipId }: UnfreezeVars) => services.memberships.unfreeze(membershipId),
    onMutate: async ({ membershipId }) => {
      await qc.cancelQueries({ queryKey: membershipsKeys.lists() })
      await qc.cancelQueries({ queryKey: membershipsKeys.detail(membershipId) })
      const listSnapshots = qc.getQueriesData<Pagination<Membership>>({
        queryKey: membershipsKeys.lists(),
      })
      const detailSnapshot = qc.getQueryData<Membership>(membershipsKeys.detail(membershipId))
      for (const [key, data] of listSnapshots) {
        if (!data) continue
        qc.setQueryData<Pagination<Membership>>(key, {
          ...data,
          items: data.items.map((m) =>
            m.id === membershipId ? { ...m, status: 'active', currentFreezePeriod: null } : m,
          ),
        })
      }
      if (detailSnapshot) {
        qc.setQueryData<Membership>(membershipsKeys.detail(membershipId), {
          ...detailSnapshot,
          status: 'active',
          currentFreezePeriod: null,
        })
      }
      return { listSnapshots, detailSnapshot }
    },
    onError: (err, vars, ctx) => {
      if (!ctx) return
      for (const [key, data] of ctx.listSnapshots) qc.setQueryData(key, data)
      if (ctx.detailSnapshot) {
        qc.setQueryData(membershipsKeys.detail(vars.membershipId), ctx.detailSnapshot)
      }
      toast.error(
        isDomainError(err)
          ? t(`memberships.freeze.errors.${err.code}` as Parameters<typeof t>[0])
          : t('common.errors.network'),
      )
    },
    onSettled: (_data, _err, vars) => {
      void qc.invalidateQueries({ queryKey: membershipsKeys.lists() })
      void qc.invalidateQueries({ queryKey: membershipsKeys.detail(vars.membershipId) })
      void qc.invalidateQueries({ queryKey: membershipsKeys.byClient(vars.clientId) })
    },
  })
}

type RenewVars = { membershipId: MembershipId; clientId: string }

export function useRenewMembership() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  return useMutation({
    mutationFn: ({ membershipId }: RenewVars) => services.memberships.renew(membershipId),
    onSuccess: (newMembership) => {
      toast.success(t('memberships.renew.success'))
      // TODO Phase 28-06: route '/memberships/$membershipId' added in wave-5; cast until then
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      void (navigate as (opts: any) => void)({
        to: '/memberships/$membershipId',
        params: { membershipId: newMembership.id },
      })
    },
    onError: (err) => {
      toast.error(
        isDomainError(err)
          ? t(`memberships.renew.errors.${err.code}` as Parameters<typeof t>[0])
          : t('common.errors.network'),
      )
    },
    onSettled: (_data, _err, vars) => {
      void qc.invalidateQueries({ queryKey: membershipsKeys.lists() })
      void qc.invalidateQueries({ queryKey: membershipsKeys.byClient(vars.clientId) })
      void qc.invalidateQueries({ queryKey: membershipsKeys.detail(vars.membershipId) })
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
