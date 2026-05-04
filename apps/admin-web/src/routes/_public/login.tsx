import { createFileRoute, redirect } from '@tanstack/react-router'
import { z } from 'zod'
import { LoginPage } from '@/features/auth'
import { authKeys } from '@/features/auth/api/keys'
import { services, API_MODE } from '@/shared/api/services'

export const Route = createFileRoute('/_public/login')({
  validateSearch: z.object({ next: z.string().optional() }),
  beforeLoad: async ({ context, search }) => {
    if (API_MODE === 'mock') return
    try {
      await context.queryClient.ensureQueryData({
        queryKey: authKeys.me,
        queryFn: () => services.auth.me(),
        retry: false,
      })
      // Already authenticated — silent redirect to next ?? '/' (D-03)
      throw redirect({ to: search.next ?? '/', replace: true })
    } catch (e) {
      const { isRedirect } = await import('@tanstack/react-router')
      if (isRedirect(e)) throw e
      // 401 from /auth/me → render login page (continue)
    }
  },
  component: LoginPage,
})
