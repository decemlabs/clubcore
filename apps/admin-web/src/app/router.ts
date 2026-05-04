import { createRouter } from '@tanstack/react-router'
import type { QueryClient } from '@tanstack/react-query'
import { routeTree } from '@/routeTree.gen'
import { queryClient } from './queryClient'
import { useSessionStore } from '@/shared/session/store'
import type { Role, SessionState } from '@/shared/session/types'
import { API_MODE } from '@/shared/api/services'
import { authKeys } from '@/features/auth/api/keys'
import type { MeResponse } from '@/shared/api/contracts/auth'

export interface RouterContext {
  queryClient: QueryClient
  getSession: () => SessionState
}

function getSession(): SessionState {
  if (API_MODE === 'mock') {
    return useSessionStore.getState()
  }
  // http-mode: cache-backed (D-05). Fallback to 'reception' (least-privileged) when
  // cache is empty -- _protected.beforeLoad will redirect to /login long before any
  // RoleGate runs, so this fallback is never user-visible. NEVER fall back to 'owner'.
  const me = queryClient.getQueryData<MeResponse>(authKeys.me)
  const role: Role = me?.role ?? 'reception'
  return {
    role,
    // setRole is a no-op in http-mode (RoleSwitcher hidden by D-12 guard);
    // satisfies the SessionState interface without mutating cache.
    setRole: () => undefined,
  }
}

export const router = createRouter({
  routeTree,
  defaultPreload: 'intent',
  defaultPreloadStaleTime: 0,
  context: {
    queryClient,
    getSession,
  } satisfies RouterContext,
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
