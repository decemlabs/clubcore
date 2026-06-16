/**
 * Auth bus — decoupled session-expiry pub/sub (Plan 71-07).
 *
 * Breaks the window.location.replace('/login') → catch-all → /home loop:
 *  - queryClient.ts publishes session-expiry via publishSessionExpired()
 *  - AuthContext subscribes and sets status 'anon' → RequireAuth renders <Navigate to="/login">
 *
 * Design: pure module-scoped state; NO React, NO router imports.
 * This keeps queryClient.ts decoupled from react-router while still triggering
 * in-app navigation (no full-page reload, no history loop).
 */

type SessionExpiredCallback = () => void

const _subscribers = new Set<SessionExpiredCallback>()

/**
 * Subscribe to session-expiry events.
 * Returns an unsubscribe function — call it in useEffect cleanup.
 */
export function subscribeSessionExpired(cb: SessionExpiredCallback): () => void {
  _subscribers.add(cb)
  return () => {
    _subscribers.delete(cb)
  }
}

/**
 * Publish a session-expiry event to all subscribers.
 * Called by queryClient.ts handleSessionExpired instead of window.location.replace.
 */
export function publishSessionExpired(): void {
  for (const cb of _subscribers) {
    cb()
  }
}
