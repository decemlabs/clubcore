import { createFileRoute, redirect } from '@tanstack/react-router'
import { z } from 'zod'
import { can } from '@/shared/session/can'
import { membershipsKeys } from '@/features/memberships/api/keys'
import { services } from '@/shared/api/services'
import { MembershipsListPage } from '@/features/memberships/components/MembershipsListPage'

const searchSchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  pageSize: z.coerce.number().int().min(10).max(100).default(20),
  status: z.enum(['active', 'expired', 'cancelled', 'frozen']).optional(),
  expiring: z.boolean().optional().default(false),
})

export const Route = createFileRoute('/_protected/memberships')({
  validateSearch: searchSchema,
  beforeLoad: ({ context, location }) => {
    const { role } = context.getSession()
    if (!can(role, 'view', 'memberships')) {
      throw redirect({
        to: '/',
        search: { forbidden: location.pathname + (location.searchStr ?? '') },
      })
    }
  },
  loaderDeps: ({ search }) => ({ search }),
  loader: ({ context, deps: { search } }) =>
    context.queryClient.ensureQueryData({
      queryKey: membershipsKeys.list(search),
      queryFn: () => services.memberships.list(search),
    }),
  component: MembershipsListPage,
})
