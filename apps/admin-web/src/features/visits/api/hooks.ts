import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { visitsKeys } from './keys'
import { services } from '@/shared/api/services'
import { todayMSK } from '@/shared/i18n/date'

export function useRecentVisitsByClient(clientId: string, opts: { limit: number } = { limit: 20 }) {
  return useQuery({
    queryKey: visitsKeys.recentByClient(clientId, opts),
    queryFn: () => services.visits.recentByClient(clientId, opts),
    enabled: !!clientId,
    staleTime: 30_000,
  })
}

export function useGymMeta() {
  return useQuery({
    queryKey: visitsKeys.gymMeta,
    queryFn: () => services.visits.gymMeta(),
    staleTime: 300_000, // 5 min — mirrors backend Cache-Control: max-age=300
  })
}

export function useCheckIn() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (clientId: string) => services.visits.checkIn(clientId),
    onSettled: (_data, _err, clientId) => {
      void qc.invalidateQueries({ queryKey: visitsKeys.lists() })
      void qc.invalidateQueries({ queryKey: visitsKeys.recentByClient(clientId, { limit: 20 }) })
    },
  })
}

/**
 * LOCAL hook (Architecture Rule 5: features must not import other features).
 * Calls services.memberships.byClient via the swap-seam — NOT the memberships feature hook.
 * The queryKey is namespaced under visitsKeys.all so cache invalidation stays inside features/visits.
 * Returns derived state suitable for FE-08(c): { activeMembership, expiringToday, isPending }.
 */
export function useMembershipStatusForClient(clientId: string) {
  const query = useQuery({
    queryKey: [...visitsKeys.all, 'membershipStatusForClient', clientId] as const,
    queryFn: () => services.memberships.byClient(clientId),
    enabled: !!clientId,
    staleTime: 30_000,
  })
  const items = query.data?.items ?? []
  const activeMembership = items.find((m) => m.status === 'active')
  const expiringToday =
    activeMembership !== undefined && activeMembership.endDate === todayMSK()
  return { activeMembership, expiringToday, isPending: query.isPending, error: query.error }
}
