/**
 * Phase-94 PWA-01: App-level WebSocket hook for the client messaging channel.
 *
 * This is the first WebSocket hook in the codebase. Closest structural analogs:
 *   - authBus.ts (subscribe/unsubscribe effect-cleanup pattern)
 *   - AuthContext.jsx (useEffect with cleanup return, lines 68-76)
 *
 * Design decisions:
 *   - Mounted ONCE at app root in App() gated on status==='authed' — not inside ChatScreen —
 *     so the unread badge updates in real time from any screen.
 *   - Auth rides the same-origin httpOnly cc_client_access cookie on WS upgrade (no URL token).
 *   - Reconnects with capped exponential backoff (×2, max 30s) via destroyed-flag teardown
 *     that prevents reconnects after unmount (T-94-03 DoS mitigation).
 *   - WS frames carry only IDs/events, NOT payloads — REST catch-up on reconnect (DB-first).
 *   - ping frames: server heartbeat, no client action.
 *   - malformed JSON: swallowed silently (T-94-02 information disclosure mitigation).
 */
import { useEffect, useRef } from 'react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface UseClientMessagingWSOptions {
  /** If false, no socket is opened. Use this to gate on auth status. Default: true. */
  enabled?: boolean
  /** Called when a new_message frame arrives with the message UUID. */
  onNewMessage: (messageId: string) => void
  /** Called when a read_receipt frame arrives with the send-time watermark ISO string.
   *  readAt = max(sentAt) of just-read client messages — NOT the read clock.
   *  Caller should mark messages with sentAt <= readAt as delivered (✓✓). */
  onReadReceipt: (readAt: string) => void
  /** Called when a typing frame arrives (actor: staff). Caller sets a 5s dismiss timer. */
  onTyping: () => void
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Initial reconnect delay in ms. */
const BASE_DELAY = 1_000
/** Maximum reconnect delay cap (T-94-03: prevents tight loops on persistent failure). */
const MAX_DELAY = 30_000

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Open a WebSocket to /api/v1/client/ws/messages, dispatch typed frames to
 * the provided callbacks, and reconnect with capped exponential backoff.
 *
 * Lifecycle:
 *   1. mount with enabled=true → open socket
 *   2. onopen → reset delay to BASE_DELAY
 *   3. onmessage → dispatch frame
 *   4. onclose → scheduleReconnect (unless destroyed)
 *   5. unmount → destroyed=true, clearTimeout, ws.close()
 *
 * enabled=false → no socket opened (useful for gating on auth status).
 */
export function useClientMessagingWS({
  enabled = true,
  onNewMessage,
  onReadReceipt,
  onTyping,
}: UseClientMessagingWSOptions): void {
  const reconnectDelay = useRef(BASE_DELAY)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // CR-01: Keep the callbacks in a ref so the connect effect can depend ONLY on
  // [enabled]. App() passes fresh inline closures every render; if they were in
  // the dep array the singleton socket would tear down + reopen on every App
  // re-render (every sheet open/close, push toast, and crucially every
  // setUnreadChat from the badge feed → connect churn). The ref is updated each
  // render so the latest callbacks are always invoked, without re-running the effect.
  const cbRef = useRef({ onNewMessage, onReadReceipt, onTyping })
  cbRef.current = { onNewMessage, onReadReceipt, onTyping }

  useEffect(() => {
    if (!enabled) return

    // destroyed flag: set on cleanup to prevent reconnects after unmount
    let destroyed = false

    function connect() {
      if (destroyed) return
      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(`${proto}//${location.host}/api/v1/client/ws/messages`)
      wsRef.current = ws

      ws.onopen = () => {
        // Successful connect: reset backoff to base
        reconnectDelay.current = BASE_DELAY
      }

      ws.onmessage = (event: MessageEvent) => {
        let frame: { type: string; messageId?: string; readAt?: string; actor?: string }
        try {
          frame = JSON.parse(event.data as string) as typeof frame
        } catch {
          // T-94-02: malformed JSON swallowed — no throw, no leak
          return
        }

        if (frame.type === 'new_message' && frame.messageId) {
          cbRef.current.onNewMessage(frame.messageId)
        } else if (frame.type === 'read_receipt' && frame.readAt) {
          cbRef.current.onReadReceipt(frame.readAt)
        } else if (frame.type === 'typing') {
          cbRef.current.onTyping()
        }
        // 'ping' frames: server heartbeat — no client action
      }

      ws.onclose = () => {
        wsRef.current = null
        if (!destroyed) scheduleReconnect()
      }

      // onerror: close so onclose fires and schedules reconnect
      ws.onerror = () => {
        ws.close()
      }
    }

    function scheduleReconnect() {
      // WR-05: clear any pending timer before scheduling a new one. If two
      // onclose events race (onerror→close plus a server close), the earlier
      // timer would otherwise be orphaned (untracked) and still fire connect(),
      // opening a second socket that escapes the single-socket invariant.
      if (reconnectTimer.current !== null) {
        clearTimeout(reconnectTimer.current)
        reconnectTimer.current = null
      }
      reconnectTimer.current = setTimeout(() => {
        // WR-05: null the ref inside the callback so the tracked timer always
        // reflects a pending (not already-fired) timeout.
        reconnectTimer.current = null
        // Double the delay before the next attempt, capped at MAX_DELAY
        reconnectDelay.current = Math.min(reconnectDelay.current * 2, MAX_DELAY)
        connect()
      }, reconnectDelay.current)
    }

    connect()

    return () => {
      // Cleanup: stop any pending reconnect and close the socket
      destroyed = true
      if (reconnectTimer.current !== null) {
        clearTimeout(reconnectTimer.current)
        reconnectTimer.current = null
      }
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [enabled])
}
