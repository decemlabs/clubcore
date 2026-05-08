import { createFileRoute, redirect } from '@tanstack/react-router'
import { can } from '@/shared/session/can'
import { membershipsKeys } from '@/features/memberships/api/keys'
import { services } from '@/shared/api/services'
import { MembershipPlansPage } from '@/features/memberships/components/MembershipPlansPage'

export const Route = createFileRoute('/_protected/membership-plans')({
  beforeLoad: ({ context, location }) => {
    const { role } = context.getSession()
    if (!can(role, 'view', 'membership-plans')) {
      throw redirect({
        to: '/',
        search: { forbidden: location.pathname + (location.searchStr ?? '') },
      })
    }
  },
  loader: ({ context }) =>
    context.queryClient.ensureQueryData({
      queryKey: membershipsKeys.plansList(undefined),
      queryFn: () => services.memberships.listPlans({}),
    }),
  component: MembershipPlansPage,
})
