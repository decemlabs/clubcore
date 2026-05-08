import { createFileRoute, redirect, useParams } from '@tanstack/react-router'
import { can } from '@/shared/session/can'
import { clientsKeys } from '@/features/clients/api/keys'
import { membershipsKeys } from '@/features/memberships/api/keys'
import { visitsKeys } from '@/features/visits/api/keys'
import { services } from '@/shared/api/services'
import { useClient } from '@/features/clients/api/hooks'
import { ClientProfileCard } from '@/features/clients/components/ClientProfileCard'
import { MembershipsBlock } from '@/features/memberships'
import { RecentVisitsBlock } from '@/features/visits'
import type { ClientId } from '@/entities/client'

/**
 * COLOCATED page component. Lives in the route file (NOT under features/clients/)
 * because it composes three features: clients + memberships + visits.
 * Per apps/admin-web/CLAUDE.md Architecture Rule 5 ("features must not import other
 * features"), this composition is legal ONLY at the route layer.
 * ESLint Pattern α zone (D-22-12) enforces this statically.
 */
function ClientDetailPage() {
  const { clientId } = useParams({ from: '/_protected/clients_/$clientId' })
  const id = clientId as ClientId
  const { data: client } = useClient(id)

  // Loader already prefetched all three; this null-guard should not hit in practice.
  if (!client) return null

  return (
    <main className="container mx-auto px-4 py-6 space-y-8">
      <ClientProfileCard client={client} />
      <MembershipsBlock clientId={clientId} />
      <RecentVisitsBlock clientId={clientId} />
    </main>
  )
}

export const Route = createFileRoute('/_protected/clients_/$clientId')({
  beforeLoad: ({ context, location }) => {
    const { role } = context.getSession()
    if (!can(role, 'view', 'clients')) {
      throw redirect({
        to: '/',
        search: { forbidden: location.pathname + (location.searchStr ?? '') },
      })
    }
  },
  loader: ({ context, params }) => {
    const { clientId } = params
    const id = clientId as ClientId
    return Promise.all([
      context.queryClient.ensureQueryData({
        queryKey: clientsKeys.detail(id),
        queryFn: () => services.clients.get(id),
      }),
      context.queryClient.ensureQueryData({
        queryKey: membershipsKeys.byClient(clientId),
        queryFn: () => services.memberships.byClient(clientId),
      }),
      context.queryClient.ensureQueryData({
        queryKey: visitsKeys.recentByClient(clientId, { limit: 20 }),
        queryFn: () => services.visits.recentByClient(clientId, { limit: 20 }),
      }),
    ])
  },
  component: ClientDetailPage,
})
