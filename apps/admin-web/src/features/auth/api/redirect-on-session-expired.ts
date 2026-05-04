import { ApiError } from '@sportzal/api-client'
import { queryClient } from '@/app/queryClient'

let redirecting = false

/**
 * Global handler for synthetic ApiError(code='session_expired') from
 * @sportzal/api-client. Phase 9 D-A1: emitted when single-flight /auth/refresh
 * fails. Phase 10 D-07: caught at QueryCache + MutationCache onError level so
 * EXACTLY ONE redirect happens regardless of how many queries/mutations fail
 * in the same tick.
 *
 * Module-scoped `redirecting` flag is reset in `.finally()` so a subsequent
 * (later) session_expired CAN redirect again -- but a 401 storm in the same
 * tick collapses to a single navigate (RESEARCH Pitfall 5).
 *
 * The router is imported lazily (dynamic import) to break the
 * queryClient <-> router <-> redirect-helper static import cycle (RESEARCH Pitfall 3).
 */
export function redirectOnSessionExpired(error: unknown): void {
  if (!(error instanceof ApiError)) return
  if (error.code !== 'session_expired') return
  if (redirecting) return
  redirecting = true
  queryClient.clear()
  // Lazy import to break circular dep -- fire-and-forget is fine because
  // navigate completion is not awaited by the caller (cache onError signature is sync).
  void import('@/app/router')
    .then(({ router }) => {
      // WARNING #4 fix: pass `next` raw -- TanStack Router serializes search params automatically.
      // Pre-encoding via encodeURIComponent produces double-encoded URLs that fail sanitizeNext.
      // Use pathname + search (NOT full href) so the origin is never carried -- cross-origin
      // redirects must be blocked anyway by the sanitizeNext guard in LoginPage.
      const loc = router.state.location
      const next = loc.pathname + (loc.search ?? '')
      // TODO Plan 05: /login route not in routeTree.gen.ts yet — added in Plan 05.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return (router.navigate as (opts: any) => Promise<void>)({
        to: '/login',
        search: { next },
        replace: true,
      })
    })
    .finally(() => {
      redirecting = false
    })
}

/** Test-only -- resets the module flag between cases. NOT exported in barrels. */
export function __resetRedirectingFlagForTests(): void {
  redirecting = false
}

/** Test-only -- read flag state. */
export function __getRedirectingForTests(): boolean {
  return redirecting
}
