import { createFileRoute } from '@tanstack/react-router'
import { visitsKeys } from '@/features/visits/api/keys'
import { services } from '@/shared/api/services'
import { CheckInPage } from '@/features/visits/components/CheckInPage'

export const Route = createFileRoute('/_protected/visits')({
  loader: ({ context }) =>
    context.queryClient.ensureQueryData({
      queryKey: visitsKeys.gymMeta,
      queryFn: () => services.visits.gymMeta(),
    }),
  component: CheckInPage,
})
