/**
 * Client PWA QueryClient (Phase 71 D-71-06).
 *
 * Mirrors admin-web queryClient.ts conventions:
 *  - staleTime: 30_000 (30 s)
 *  - refetchOnWindowFocus: false
 *  - retry: 1 for queries, 0 for mutations
 *  - QueryCache + MutationCache onError session-expiry handler
 *
 * Session expiry: react-router v6 is kept (D-20-PWA-ROUTER) — no TanStack
 * Router navigate. On session_expired ApiError, publishSessionExpired() is
 * called via authBus → AuthContext sets status 'anon' → RequireAuth renders
 * <Navigate to="/login"> via react-router (no window.location, no full reload,
 * no redirect loop).
 */
import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'
import { ApiError } from '@clubcore/api-client'
import { publishSessionExpired } from './authBus'

let _redirecting = false

/**
 * Notify authBus on session_expired ApiError (T-71-17).
 * Module-scoped flag collapses a 401-storm to a single publish.
 * AuthContext subscribes and sets status 'anon'; RequireAuth redirects to /login.
 */
function handleSessionExpired(error: unknown): void {
  if (!(error instanceof ApiError)) return
  if (error.code !== 'session_expired') return
  if (_redirecting) return
  _redirecting = true
  publishSessionExpired()
  // Reset flag so a later (new session) expiry can notify again.
  setTimeout(() => {
    _redirecting = false
  }, 5000)
}

export const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: handleSessionExpired }),
  mutationCache: new MutationCache({ onError: handleSessionExpired }),
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
    mutations: {
      retry: 0,
    },
  },
})
