"""WebSocket connection handler for messaging (Phase 90 RT-01..04).

Per-connection Redis pub/sub subscriber loop with heartbeat, idle cleanup,
and session-per-operation pattern.

Six WS invariants (all locked here from day one):

  1. Cookie auth via cc_client_access -- NOT URL token (T-90-10 / P1)
  2. Per-principal channel cc:messaging:client:{client_id} derived from principal
     ONLY -- never from path/query/payload (T-90-12 / P2 IDOR-safe)
  3. Per-connection redis.pubsub() subscriber -- NOT a global lifespan task,
     NOT subscribe() on the shared pool client (T-90-15 / P4 multi-worker fan-out)
  4. session_factory from app.state opened per-operation -- NOT Depends(get_db)
     which would hold a pooled DB session for the WS lifetime (T-90-13 / P3)
  5. App-level ~30s heartbeat + asyncio.wait_for idle detection with finally
     teardown (T-90-14 / P6 zombie cleanup)
  6. DB-first delivery: frames are id-only {type,messageId}; the PWA refetches
     via REST; pub/sub is notification-only, never carries full payload (P5)

Called from: app/modules/messaging/router.py @router.websocket("/ws/messages")
"""

from __future__ import annotations

import asyncio
import contextlib
import json

import structlog
from fastapi import WebSocket
from fastapi.websockets import WebSocketState
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.websockets import WebSocketDisconnect

_log = structlog.get_logger("modules.messaging.ws")

# Heartbeat interval: server sends {"type":"ping"} every 30 seconds (P6).
_HEARTBEAT_INTERVAL_S: float = 30.0

# Idle timeout: if no message received in 90 seconds (3x heartbeat) the
# connection is considered zombie and closed with 1001 (Going Away) (P6).
_IDLE_TIMEOUT_S: float = 90.0


async def run_connection(
    websocket: WebSocket,
    client_id: object,  # UUID -- typed as object to avoid importing UUID at call site
    redis: Redis,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Drive a single authenticated WS connection.

    Invariant summary (all six required):
      - channel derived from client_id (principal) ONLY -- never from request data
      - dedicated pubsub connection via redis.pubsub() (not the shared pool)
      - session opened per DB operation via session_factory() (not Depends(get_db))
      - fan-out task cancelled + pubsub closed in finally (zombie cleanup)
      - heartbeat every ~30s, idle timeout ~90s (1001 on timeout)
      - forwards id-only frames verbatim (DB-first; PWA refetches via REST)

    Args:
        websocket: the accepted WebSocket connection (caller must call accept() first)
        client_id: the authenticated client's UUID (from require_client() principal)
        redis: the shared Redis pool client (redis.pubsub() creates a dedicated connection)
        session_factory: app.state.sessionmaker; used for per-operation DB access
    """
    # P2 / T-90-12: channel derived ONLY from principal.client_id.
    # Never from websocket path params, query params, or inbound message payload.
    channel: str = f"cc:messaging:client:{client_id}"

    # P4 / T-90-15: create a DEDICATED pub/sub connection.
    # Never call subscribe() on the shared pool redis client -- that would hold
    # the connection in subscriber mode, preventing other commands on the pool.
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)

    _log.info(
        "ws_connection_opened",
        client_id=str(client_id),
        channel=channel,
    )

    # Fan-out task: reads messages from pub/sub and forwards to the WS.
    # Each message from the service layer is an id-only JSON frame already
    # serialized by NewMessageEvent.model_dump_json() (P6 DB-first).
    async def _fan_out_loop() -> None:
        """Forward Redis pub/sub messages to the WebSocket client."""
        try:
            async for raw in pubsub.listen():
                if raw["type"] != "message":
                    continue
                if websocket.client_state != WebSocketState.CONNECTED:
                    break
                try:
                    await websocket.send_text(raw["data"])
                    # WR-02: do NOT log the full frame body (information exposure for
                    # messaging); log the frame size only.
                    _log.debug(
                        "ws_frame_sent",
                        client_id=str(client_id),
                        frame_bytes=len(raw["data"]) if raw["data"] is not None else 0,
                    )
                except (WebSocketDisconnect, RuntimeError):
                    # Connection closed mid-send -- expected; stop forwarding.
                    break
                except Exception:  # BLE001
                    # WR-02: narrow the broad swallow -- a serialization/logic bug
                    # must not silently leave a half-dead connection with no signal.
                    _log.warning(
                        "ws_fan_out_send_failed",
                        client_id=str(client_id),
                        exc_info=True,
                    )
                    break
        except asyncio.CancelledError:
            pass

    fan_out_task = asyncio.create_task(_fan_out_loop())

    try:
        # Heartbeat + receive loop.
        # asyncio.wait_for detects idle connections (P6 zombie prevention).
        # Inbound client text frames are accepted and silently ignored in Phase 90:
        # the client sends messages via POST /messages (REST), not via WS.
        heartbeat_elapsed: float = 0.0

        while True:
            # Wait for a client frame or heartbeat timeout.
            try:
                _data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=min(_HEARTBEAT_INTERVAL_S, _IDLE_TIMEOUT_S - heartbeat_elapsed),
                )
                # Client sent something -- reset idle tracking.
                heartbeat_elapsed = 0.0
                # Phase 90: inbound frames are ignored (client uses REST to send messages).
                # Future phases may process "pong" or typing indicators here.

            except TimeoutError:
                heartbeat_elapsed += _HEARTBEAT_INTERVAL_S

                if heartbeat_elapsed >= _IDLE_TIMEOUT_S:
                    # No activity for _IDLE_TIMEOUT_S seconds -- zombie connection (P6).
                    _log.info(
                        "ws_idle_timeout",
                        client_id=str(client_id),
                        idle_s=heartbeat_elapsed,
                    )
                    await websocket.close(code=1001)
                    return

                # Send application-level ping to keep the connection alive (P6).
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                    _log.debug("ws_heartbeat_sent", client_id=str(client_id))
                except Exception:  # BLE001: WS may have closed -- exit silently
                    return

            except WebSocketDisconnect:
                _log.info("ws_client_disconnected", client_id=str(client_id))
                return

            # P3 / T-90-13: DB access (if any future operation needs it) opens a
            # session per operation via session_factory(), NOT via Depends(get_db).
            # Example (not needed in Phase 90 receive path):
            #   async with session_factory() as session:
            #       await some_db_operation(session, ...)
            # The session_factory parameter is retained here so the WS handler
            # signature is stable for future phases (read receipts, typing, etc.).
            _ = session_factory  # referenced to satisfy mypy --strict unused-param

    finally:
        # P6 / T-90-14: unconditional teardown -- runs on normal exit, disconnect,
        # timeout, or unhandled exception.
        # WR-06: suppress only CancelledError for the task await; a genuine teardown
        # failure (e.g. aclose() raising) must be LOGGED, not silently swallowed —
        # blanket Exception suppression hides the one failure mode (pooled pub/sub
        # subscriber-connection leak) the teardown exists to prevent.
        fan_out_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await fan_out_task

        try:
            await pubsub.unsubscribe(channel)
        except Exception:  # BLE001
            _log.warning(
                "ws_pubsub_teardown_failed",
                client_id=str(client_id),
                step="unsubscribe",
                exc_info=True,
            )

        try:
            await pubsub.aclose()  # type: ignore[no-untyped-call]
        except Exception:  # BLE001
            _log.warning(
                "ws_pubsub_teardown_failed",
                client_id=str(client_id),
                step="aclose",
                exc_info=True,
            )

        _log.info("ws_connection_closed", client_id=str(client_id), channel=channel)
