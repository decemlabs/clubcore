import { createFileRoute, redirect } from '@tanstack/react-router'
import { z } from 'zod'
import { can } from '@/shared/session/can'
import { clientsKeys } from '@/features/clients/api/keys'
import { services } from '@/shared/api/services'
import { ClientsPage } from '@/features/clients/components/ClientsPage'

const searchSchema = z.object({
  q: z.string().optional(),
  page: z.coerce.number().int().min(1).default(1),
  pageSize: z.coerce.number().int().min(10).max(100).default(20),
})

export const Route = createFileRoute('/_protected/clients')({
  validateSearch: searchSchema,
  beforeLoad: ({ context, location }) => {
    const { role } = context.getSession()
    if (!can(role, 'view', 'clients')) {
      throw redirect({
        to: '/',
        search: { forbidden: location.pathname + (location.search ?? '') },
      })
    }
  },
  loaderDeps: ({ search }) => ({ search }),
  loader: ({ context, deps: { search } }) =>
    context.queryClient.ensureQueryData({
      queryKey: clientsKeys.list(search),
      queryFn: () => services.clients.list(search),
    }),
  component: ClientsPage,
})
