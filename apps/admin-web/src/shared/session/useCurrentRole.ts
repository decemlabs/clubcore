import { useQuery } from '@tanstack/react-query'
import { useSessionStore } from './store'
import type { Role } from './types'
import { API_MODE } from '@/shared/api/services'
import { authKeys } from '@/features/auth/api/keys'
import { services } from '@/shared/api/services'
import type { MeResponse } from '@/shared/api/contracts/auth'

/**
 * Single hook that components, RoleGate, and route guards read for the
 * current role. Branches on API_MODE per D-05:
 *   mock -> Zustand session store (RoleSwitcher in dev controls this)
 *   http -> TanStack Query cache for /auth/me
 *
 * In http-mode this hook subscribes to the same query key the boot
 * sequence pre-warms (main.tsx + _protected.beforeLoad), so navigation
 * is cache-hit + cheap.
 *
 * React-hooks rules: both useSessionStore and useQuery MUST be called every
 * render regardless of mode. The `enabled: API_MODE === 'http'` flag prevents
 * the network call in mock-mode but the hook still runs unconditionally.
 */
export function useCurrentRole(): Role {
  const mockRole = useSessionStore((s) => s.role)
  const httpQuery = useQuery({
    queryKey: authKeys.me,
    queryFn: () => services.auth.me(),
    enabled: API_MODE === 'http',
    retry: false,
    staleTime: 30_000,
  })
  if (API_MODE === 'mock') return mockRole
  const me = httpQuery.data as MeResponse | undefined
  return me?.role ?? 'reception'
}
