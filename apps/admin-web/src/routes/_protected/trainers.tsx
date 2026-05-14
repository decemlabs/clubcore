import { createFileRoute, redirect } from '@tanstack/react-router'
import { z } from 'zod'
import { trainersKeys } from '@/features/trainers/api/keys'
import { services } from '@/shared/api/services'
import { TrainersPage } from '@/features/trainers/components/TrainersPage'

const searchSchema = z.object({
  active: z.enum(['true', 'false']).optional(),
  page: z.coerce.number().int().min(1).default(1),
  pageSize: z.coerce.number().int().min(10).max(100).default(20),
})

export const Route = createFileRoute('/_protected/trainers')({
  validateSearch: searchSchema,
  beforeLoad: ({ context, location }) => {
    const { role } = context.getSession()
    if (role !== 'owner') {
      throw redirect({
        to: '/',
        search: { forbidden: location.pathname + (location.searchStr ?? '') },
      })
    }
  },
  loaderDeps: ({ search }) => ({ search }),
  loader: ({ context, deps: { search } }) =>
    context.queryClient.ensureQueryData({
      queryKey: trainersKeys.list({
        active: search.active ?? 'true', // default "Активные" view (D-31-22)
        page: search.page,
        pageSize: search.pageSize,
      }),
      queryFn: () =>
        services.trainers.list({
          active:
            search.active === 'true' ? true : search.active === 'false' ? false : true,
          page: search.page,
          pageSize: search.pageSize,
        }),
    }),
  component: TrainersPage,
})
