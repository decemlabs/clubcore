/**
 * Settings domain TanStack Query hooks (Phase 104 SET-01).
 *
 * Profile is read-only: ProfileSection reuses useSession() from features/auth/api.ts.
 * No PATCH /auth/me endpoint exists — profile edit is deferred (Phase 104).
 *
 * Sessions:
 *   useSessions()             — GET /api/v1/auth/sessions (list)
 *   useRevokeSession()        — POST /api/v1/auth/sessions/{family_id}/revoke (non-current)
 *   useRevokeCurrentSession() — POST same endpoint for the current session; on 204 publishes
 *                               session_expired via authBus → RequireAuth redirects to /login.
 *                               Does NOT navigate directly (T-104-09 mitigation).
 *
 * useMockSettingsData() — mock compat for sections not yet wired (Branch/Hours/Booking/Payments/
 *   Notifications/App/Integrations/Billing). Renamed from `useSettings` so the old mock is gone.
 *   TODO: Remove when all SettingsPage sections are wired to real endpoints.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { staffRequest, mockResponse, ApiError } from '@/api/client'
import { publishSessionExpired } from '@/lib/authBus'
import { settingsData } from '@/mocks/settings'
import type { SettingsData } from './types'
import { SessionsListResponseSchema } from './schemas'

// ---------------------------------------------------------------------------
// Key factory
// ---------------------------------------------------------------------------

export const settingsKeys = {
  sessions: ['auth', 'sessions'] as const,
}

// ---------------------------------------------------------------------------
// useSessions — list active sessions
// ---------------------------------------------------------------------------

export function useSessions() {
  return useQuery({
    queryKey: settingsKeys.sessions,
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/auth/sessions')
      return SessionsListResponseSchema.parse(raw).data
    },
    staleTime: 30_000,
  })
}

// ---------------------------------------------------------------------------
// useRevokeSession — revoke a NON-current session
// ---------------------------------------------------------------------------

/**
 * Revokes a session by familyId (for non-current sessions only).
 * On 204 success: invalidates the sessions query so the row is removed.
 * For the CURRENT session, use useRevokeCurrentSession instead.
 */
export function useRevokeSession() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (familyId: string) =>
      staffRequest('post', '/api/v1/auth/sessions/{family_id}/revoke', {
        params: { family_id: familyId },
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: settingsKeys.sessions })
    },
  })
}

// ---------------------------------------------------------------------------
// useRevokeCurrentSession — self-revoke via authBus (T-104-09)
// ---------------------------------------------------------------------------

/**
 * Self-revokes the CURRENT session.
 * On 204 success: publishes session_expired via authBus — the same path
 * that RequireAuth subscribes to (T-100-09). This clears the auth cache and
 * navigates to /login?state=expired without a direct navigate() call here.
 *
 * Do NOT use this for non-current sessions — it triggers a full logout flow.
 */
export function useRevokeCurrentSession() {
  return useMutation({
    mutationFn: (familyId: string) =>
      staffRequest('post', '/api/v1/auth/sessions/{family_id}/revoke', {
        params: { family_id: familyId },
      }),
    onSuccess: () => {
      // Route through authBus session-expiry path (same as mid-session 401):
      // RequireAuth subscriber removes authKeys.me + navigates to /login?state=expired.
      publishSessionExpired()
    },
  })
}

// ---------------------------------------------------------------------------
// useMockSettingsData — mock compat for unwired sections
// ---------------------------------------------------------------------------

/**
 * Mock settings data for sections not yet wired to the backend.
 * ProfileSection and SecuritySection are self-fetching (Plan 104-04).
 * TeamSection will be wired in Plan 104-05.
 * Renamed from `useSettings` (the old mock hook is removed).
 */
export function useMockSettingsData() {
  return useQuery({
    queryKey: ['settings', 'mock'],
    queryFn: () => mockResponse<SettingsData>(settingsData),
  })
}

// ---------------------------------------------------------------------------
// Re-exports
// ---------------------------------------------------------------------------

export { ApiError }
