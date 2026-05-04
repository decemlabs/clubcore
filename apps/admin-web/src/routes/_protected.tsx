import { createFileRoute, Outlet, redirect } from '@tanstack/react-router'
import { AppShell } from '@/shared/ui/app-shell'
import { authKeys } from '@/features/auth/api/keys'
import { services, API_MODE } from '@/shared/api/services'

export const Route = createFileRoute('/_protected')({
  beforeLoad: async ({ context, location }) => {
    if (API_MODE === 'mock') return
    try {
      await context.queryClient.ensureQueryData({
        queryKey: authKeys.me,
        queryFn: () => services.auth.me(),
        retry: false,
      })
    } catch {
      // WARNING #4 (Plan 04): TanStack Router serializes search params; pass raw pathname+search,
      // not full href. Origin is dropped to keep cross-origin out of `next` (LoginPage sanitizeNext
      // is the second line of defense — see Plan 04 + Plan 05 LoginPage.sanitizeNext).
      throw redirect({ to: '/login', search: { next: location.pathname + (location.search ?? '') } })
    }
  },
  component: () => (
    <AppShell>
      <Outlet />
    </AppShell>
  ),
})
