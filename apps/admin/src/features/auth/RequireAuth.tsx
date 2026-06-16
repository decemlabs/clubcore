/**
 * RequireAuth route guard (Phase 100 AUTH-02).
 *
 * Wraps the AppLayout route branch and enforces authentication:
 *  - isPending: shows a full-screen loading placeholder (no flash of login screen)
 *  - error (unauthenticated after transport refresh attempt): Navigate to /login
 *  - success: render children/Outlet
 *
 * Also subscribes to authBus session-expiry events (mid-session 401 path):
 *  - published by queryClient.ts when any query/mutation throws session_expired
 *  - removes the session query cache and navigates to /login?state=expired
 *  - ExpiredScreen in LoginPage.tsx renders on ?state=expired
 *
 * T-100-08: App routes render only after /auth/me succeeds.
 * T-100-09: session_expired removes stale cache before redirect.
 */
import { useEffect, type ReactNode } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { Skeleton } from '@/components/ui/skeleton'
import { ROUTES } from '@/app/routes'
import { queryClient } from '@/api/query-client'
import { subscribeSessionExpired } from '@/lib/authBus'
import { useSession, authKeys } from './api'

export function RequireAuth({ children }: { children: ReactNode }) {
  const { isPending, isError } = useSession()
  const navigate = useNavigate()

  // Mid-session 401 path (T-100-09):
  // queryClient → publishSessionExpired → this handler →
  //   removeQueries(authKeys.me) + navigate to /login?state=expired
  useEffect(() => {
    return subscribeSessionExpired(() => {
      queryClient.removeQueries({ queryKey: authKeys.me })
      void navigate(`${ROUTES.login}?state=expired`, { replace: true })
    })
  }, [navigate])

  // While /auth/me is pending — show a minimal full-screen placeholder.
  // Do NOT flash the login screen; the skeleton communicates loading.
  if (isPending) {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-bg p-8">
        <div className="w-full max-w-xs space-y-3">
          <Skeleton className="h-8 w-32" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      </div>
    )
  }

  // The /me query errored (unauthenticated — transport already tried refresh).
  // Redirect to /login; the login screen shows the default login view.
  if (isError) {
    return <Navigate to={ROUTES.login} replace />
  }

  // Session confirmed — render the protected app tree.
  return <>{children}</>
}
