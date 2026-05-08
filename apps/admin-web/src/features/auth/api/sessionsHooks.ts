/**
 * FE-09 / HYG-03 — TanStack Query hooks for active session families.
 *
 * Per D-22-2 the mock impl throws `mock_not_implemented`; these hooks only
 * function in `VITE_API_MODE=http`. The UI surfaces a "demo mode unsupported"
 * fallback when invoked under mock mode (errors flow through React Query).
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { authKeys } from './keys'
import { services } from '@/shared/api/services'

export function useActiveSessions() {
  return useQuery({
    queryKey: authKeys.sessions,
    queryFn: () => services.auth.sessions(),
    staleTime: 30_000,
  })
}

export function useRevokeSession() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (familyId: string) => services.auth.revokeSession(familyId),
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: authKeys.sessions })
    },
  })
}

export function useLogoutAll() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => services.auth.logoutAll(),
    onSuccess: () => {
      // Wipe local cache so a fresh login pulls a clean state.
      qc.clear()
    },
  })
}
