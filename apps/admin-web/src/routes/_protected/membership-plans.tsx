import { createFileRoute, redirect } from '@tanstack/react-router'
import { z } from 'zod'
import { can } from '@/shared/session/can'
import { membershipsKeys } from '@/features/memberships/api/keys'
import { services } from '@/shared/api/services'
import { MembershipPlansPage } from '@/features/memberships/components/MembershipPlansPage'

const searchSchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  pageSize: z.coerce.number().int().min(10).max(100).default(20),
})

export const Route = createFileRoute('/_protected/membership-plans')({
  validateSearch: searchSchema,
  beforeLoad: ({ context, location }) => {
    const { role } = context.getSession()
    if (!can(role, 'view', 'membership-plans')) {
      throw redirect({
        to: '/',
        search: { forbidden: location.pathname + (location.searchStr ?? '') },
      })
    }
  },
  loaderDeps: ({ search }) => ({ search }),
  loader: ({ context, deps: { search } }) =>
    context.queryClient.ensureQueryData({
      // BLK-05: loader key MUST match useMembershipPlans hook key (active=undefined,
      // page, pageSize) — otherwise the prefetch is wasted and the page double-fetches.
      queryKey: membershipsKeys.plansList(undefined, search.page, search.pageSize),
      queryFn: () =>
        services.memberships.listPlans({ page: search.page, pageSize: search.pageSize }),
    }),
  component: MembershipPlansPage,
})
