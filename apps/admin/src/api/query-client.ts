/**
 * Admin-app QueryClient (Phase 100 FND-02).
 *
 * Mirrors client queryClient.ts conventions:
 *  - staleTime: 30_000 (30 s)
 *  - refetchOnWindowFocus: false
 *  - retry: 1 for queries, 0 for mutations
 *  - QueryCache + MutationCache onError session-expiry handler
 *
 * Session expiry: on session_expired ApiError, publishSessionExpired() is
 * called via authBus. LoginPage.tsx useEffect subscribes and navigates to
 * /login?state=expired (plan 100-03). The _redirecting flag collapses a
 * 401-storm to a single publish within a 5-second window.
 */
import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'
import { ApiError } from '@/api/client'
import { publishSessionExpired } from '@/lib/authBus'

let _redirecting = false

/**
 * Notify authBus on session_expired ApiError.
 * Module-scoped flag collapses a 401-storm to a single publish.
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
