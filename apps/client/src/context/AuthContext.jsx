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
import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react'
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

  // WR-07: timestamp (ms) at which override was set to 'anon' by the expiry bus.
  // The reconciliation effect only trusts a probe success that completed AFTER
  // this moment (dataUpdatedAt > anonSetAt), so a stale cached identity from
  // BEFORE the expiry can never clear the 'anon' override.
  const anonSetAtRef = useRef(0)

  const status = override !== null ? override : probeStatus

  // Subscribe to session-expiry bus — flip to anon and clear cached client data
  useEffect(() => {
    const unsub = subscribeSessionExpired(() => {
      anonSetAtRef.current = Date.now()
      setOverride('anon')
      // Invalidate all client-portal cached data so protected screens don't show stale data
      void qc.invalidateQueries({ queryKey: clientPortalKeys.all })
    })
    return unsub
  }, [qc])

  // WR-07: reconcile a stale 'anon' override against a freshly-succeeded probe.
  // The expiry bus sets override='anon' AND invalidates the me-probe, which then
  // refetches. If that refetch newly SUCCEEDS with a real identity (the session
  // was actually still valid), the stale 'anon' override must be cleared so the
  // successful probe can drive status back to 'authed' — otherwise the override
  // would shadow it forever. We require dataUpdatedAt to be strictly newer than
  // the moment the override was set (so a stale pre-expiry cached identity cannot
  // clear it) and only touch an 'anon' override (never the 'authed' override that
  // login() sets as its intended terminal state).
  const dataUpdatedAt = probe.dataUpdatedAt
  useEffect(() => {
    if (
      override === 'anon' &&
      probe.isSuccess &&
      probe.data != null &&
      dataUpdatedAt > anonSetAtRef.current
    ) {
      setOverride(null)
    }
  }, [probe.isSuccess, probe.data, dataUpdatedAt, override])

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
