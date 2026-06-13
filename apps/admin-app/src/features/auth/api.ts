/**
 * Auth domain TanStack Query hooks (Phase 100 AUTH-01, AUTH-02).
 *
 * This is the auth domain's http swap-seam — auth always uses http in Phase 100 (D-V30).
 * There is no mock path here. The VITE_API_MODE chokepoint ESLint rule exempts
 * features/auth/** from the no-restricted-syntax rule.
 *
 * Design decision (D-100-03-LOGININVALIDATE):
 *   useLogin invalidates authKeys.me on success rather than setQueryData.
 *   The login response user object lacks `email` and `hasTelegram` that MeResponse
 *   includes — setting partial data would produce a shape inconsistent with MeResponse.
 *   Invalidating forces a fresh /auth/me fetch that returns the complete shape.
 *   Cost: one extra round-trip on login. Benefit: single source of truth, no cache pollution.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { staffRequest, ApiError } from '@/api/client'
import {
  LoginRequestSchema,
  LoginResponseSchema,
  MeResponseSchema,
  type LoginRequest,
  type MeData,
  type PasswordResetConfirm,
  type PasswordResetRequest,
} from './schemas'

// ---------------------------------------------------------------------------
// Key factory
// ---------------------------------------------------------------------------

export const authKeys = {
  me: ['auth', 'me'] as const,
}

// ---------------------------------------------------------------------------
// useSession — single source of truth for role/fullName/email
// ---------------------------------------------------------------------------

/**
 * Probes GET /api/v1/auth/me to determine if the user is authenticated.
 * retry:false — a 401 on /me is the definitive "unauthenticated" signal.
 * The transport's 401→refresh→retry already attempted renewal; if that
 * still failed, the session truly expired and the QueryCache onError will
 * publish session_expired via authBus (handled in RequireAuth).
 */
export function useSession() {
  return useQuery({
    queryKey: authKeys.me,
    queryFn: async (): Promise<MeData> => {
      const raw = await staffRequest('get', '/api/v1/auth/me')
      return MeResponseSchema.parse(raw).data
    },
    retry: false,
  })
}

// ---------------------------------------------------------------------------
// useLogin
// ---------------------------------------------------------------------------

export function useLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: LoginRequest) => {
      const raw = await staffRequest('post', '/api/v1/auth/login', { body })
      // Parse the login response — returns {id, role, fullName} (no email/hasTelegram).
      return LoginResponseSchema.parse(raw).data.user
    },
    onSuccess: () => {
      // Invalidate (not setQueryData) so the next useSession fetch returns the
      // full MeResponse shape including email and hasTelegram. See D-100-03-LOGININVALIDATE.
      void qc.invalidateQueries({ queryKey: authKeys.me })
    },
  })
}

// ---------------------------------------------------------------------------
// useLogout
// ---------------------------------------------------------------------------

export function useLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => staffRequest('post', '/api/v1/auth/logout'),
    onSettled: () => {
      qc.removeQueries({ queryKey: authKeys.me })
    },
  })
}

// ---------------------------------------------------------------------------
// usePasswordResetRequest
// ---------------------------------------------------------------------------

export function usePasswordResetRequest() {
  return useMutation({
    mutationFn: (body: PasswordResetRequest) =>
      staffRequest('post', '/api/v1/auth/password-reset/request', { body }),
  })
}

// ---------------------------------------------------------------------------
// usePasswordResetConfirm
// ---------------------------------------------------------------------------

export function usePasswordResetConfirm() {
  return useMutation({
    mutationFn: (body: PasswordResetConfirm) =>
      // Body uses `newPassword` key (camelCase wire format — mirrors backend `new_password`).
      staffRequest('post', '/api/v1/auth/password-reset/confirm', { body }),
  })
}

// ---------------------------------------------------------------------------
// Re-exports for page-layer consumers (pages import from features/, not api/client directly)
// ---------------------------------------------------------------------------

// ApiError is re-exported so pages can do `instanceof ApiError` without importing @/api/client.
export { ApiError }
export { LoginRequestSchema }
