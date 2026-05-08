import { createFileRoute, redirect } from '@tanstack/react-router'
import { can } from '@/shared/session/can'
import { visitsKeys } from '@/features/visits/api/keys'
import { services } from '@/shared/api/services'
import { CheckInPage } from '@/features/visits/components/CheckInPage'

export const Route = createFileRoute('/_protected/visits')({
  beforeLoad: ({ context, location }) => {
    const { role } = context.getSession()
    if (!can(role, 'view', 'visits')) {
      throw redirect({
        to: '/',
        search: { forbidden: location.pathname + (location.searchStr ?? '') },
      })
    }
  },
  loader: ({ context }) =>
    context.queryClient.ensureQueryData({
      queryKey: visitsKeys.gymMeta,
      queryFn: () => services.visits.gymMeta(),
    }),
  component: CheckInPage,
})
