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
 * Router navigate. Redirect uses window.location.replace('/login') so the
 * history entry is replaced (not pushed) and a back-nav cannot return to the
 * protected page.
 */
import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'
import { ApiError } from '@clubcore/api-client'

let _redirecting = false

/**
 * Redirect to /login on session_expired ApiError (T-71-17).
 * Module-scoped flag collapses a 401-storm to a single redirect.
 */
function handleSessionExpired(error: unknown): void {
  if (!(error instanceof ApiError)) return
  if (error.code !== 'session_expired') return
  if (_redirecting) return
  _redirecting = true
  // window.location.replace replaces the history entry so back-nav doesn't
  // return to a protected page. react-router v6 — no TanStack Router navigate.
  window.location.replace('/login')
  // Reset flag so a later (new session) expiry can redirect again.
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
