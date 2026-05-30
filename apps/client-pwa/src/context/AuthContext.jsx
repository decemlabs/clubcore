/**
 * AuthContext (Plan 71-07).
 *
 * Provides auth state (status: 'unknown' | 'authed' | 'anon') bootstrapped
 * via GET /client/me probe on mount. Subscribes to authBus session-expiry
 * signal (covers mid-use session expiry without window.location reload).
 *
 * Provider order: BrowserRouter → QueryClientProvider → AuthProvider → App
 * (AuthProvider uses useQuery, so QueryClientProvider must be above it).
 *
 * JSX file — in the allowJs ramp; no TS lint. Keep plain JS/JSX.
 */
import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { clientRequest } from '@/lib/clientFetcher'
import { subscribeSessionExpired } from '@/lib/authBus'
import { clientPortalKeys } from '@/lib/clientQueries'

// ---------------------------------------------------------------------------
// Context shape
// ---------------------------------------------------------------------------

const AuthContext = createContext(null)

// ---------------------------------------------------------------------------
// Internal: me-probe query (retry: false so 401 fails fast → anon)
// ---------------------------------------------------------------------------

function useClientMeProbe() {
  return useQuery({
    queryKey: clientPortalKeys.me(),
    queryFn: async () => {
      const res = await clientRequest('get', '/api/v1/client/me')
      // Return the data payload; fall back to the raw response if no .data property.
      // Cannot return undefined (TanStack Query requirement) — use null as anon sentinel.
      const payload = (res && typeof res === 'object' && 'data' in res) ? res.data : res
      return payload ?? null
    },
    retry: false,
    staleTime: 30_000,
  })
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthProvider({ children }) {
  const qc = useQueryClient()
  const probe = useClientMeProbe()

  // Derive status from probe result
  // 'unknown' while loading, 'authed' on success, 'anon' on error
  const probeStatus = probe.isSuccess ? 'authed' : probe.isError ? 'anon' : 'unknown'

  // Allow AuthContext to override status (expiry signal + login/logout actions)
  const [override, setOverride] = useState(null) // null = use probeStatus

  const status = override !== null ? override : probeStatus

  // Subscribe to session-expiry bus — flip to anon and clear cached client data
  useEffect(() => {
    const unsub = subscribeSessionExpired(() => {
      setOverride('anon')
      // Invalidate all client-portal cached data so protected screens don't show stale data
      void qc.invalidateQueries({ queryKey: clientPortalKeys.all })
    })
    return unsub
  }, [qc])

  // After probe settles, clear override if it was from a previous expiry
  // so future re-logins can re-probe correctly
  useEffect(() => {
    if (probe.isSuccess || probe.isError) {
      // Only clear override when the probe result agrees with it
      // (avoids clearing an 'anon' override set by the expiry bus if probe hasn't re-run yet)
      if (probe.isSuccess && override === null) return
      if (probe.isError && override === null) return
    }
  }, [probe.isSuccess, probe.isError, override])

  /**
   * Called by LoginScreen AFTER a successful OTP verify.
   * Invalidates and refetches the /client/me probe to confirm session is live.
   */
  const login = useCallback(async () => {
    setOverride(null) // let probe drive status
    await qc.invalidateQueries({ queryKey: clientPortalKeys.me() })
    await qc.refetchQueries({ queryKey: clientPortalKeys.me() })
    setOverride('authed')
  }, [qc])

  /**
   * Called by ProfileScreen logout button.
   * POSTs /client/session/logout then sets status anon.
   */
  const logout = useCallback(async () => {
    try {
      await clientRequest('post', '/api/v1/client/session/logout')
    } catch {
      // noop — even if the server call fails, drop local session
    }
    setOverride('anon')
    void qc.invalidateQueries({ queryKey: clientPortalKeys.all })
  }, [qc])

  return (
    <AuthContext.Provider value={{ status, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

/**
 * Hook: access auth state.
 * Must be used inside <AuthProvider>.
 */
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}

export default AuthContext
