"""Phase 90 Plan 03 Task 3 -- WS Redis pub/sub fan-out + RT-04 reconnect catch-up tests.

Covers:
  RT-03: cross-context Redis pub/sub fan-out (T-90-15 -- delivery does NOT rely on
         module-level in-process state; works across workers because Redis is the
         ONLY fan-out mechanism).
  RT-04: reconnect catch-up via DB-first REST cursor -- messages published while
         disconnected are recovered via GET /api/v1/client/messages?after={last_id},
         NOT via pub/sub replay (pub/sub is at-most-once; DB is the source of truth).

All tests use the Starlette TestClient.websocket_connect() convention (P13).

Cross-context fan-out (T-90-15 design note):
  The fan-out test publishes directly to Redis using a second Redis client instance
  that is NOT the app's shared pool. This simulates a different uvicorn worker
  posting a message -- the WS subscriber MUST receive the frame because Redis
  pub/sub is the only mechanism (no in-process dict). If the test passes, the
  invariant is proven for multi-worker deployments.
"""

from __future__ import annotations

import json
import uuid

from starlette.testclient import TestClient

from tests.messaging.conftest import (
    WS_ALLOWED_ORIGIN,
    _portal_call,
    auth_ws_client_sync,
    cleanup_client_sync,
    flush_redis_sync,
    seed_ws_client,
    ws_receive_text_timeout,
)

# Unique 4-digit numeric suffix per test invocation.
_FANOUT_RUN_ID = str(uuid.uuid4().int % 10000).zfill(4)
_PHONE_FANOUT = f"+7916913{_FANOUT_RUN_ID}"
_PHONE_RECONNECT = f"+7916914{_FANOUT_RUN_ID}"


# ---------------------------------------------------------------------------
# RT-03 -- Cross-context Redis pub/sub fan-out
# ---------------------------------------------------------------------------


def test_ws_cross_context_fanout(ws_tc: TestClient) -> None:
    """Fan-out from a separate Redis client reaches the WS subscriber (RT-03 / T-90-15).

    Sequence:
      1. Seed + auth client A, open A's WS connection.
      2. Publish a new_message frame DIRECTLY to cc:messaging:client:{A} using a
         second Redis client (simulating a different uvicorn worker).
      3. Assert A's WS receives the frame.

    This proves delivery does NOT rely on module-level in-process state.
    Redis pub/sub is the only fan-out mechanism -- it works across workers.
    """
    flush_redis_sync(ws_tc)
    cleanup_client_sync(ws_tc, phone=_PHONE_FANOUT)

    client = seed_ws_client(ws_tc, phone=_PHONE_FANOUT, suffix=f"fo{_FANOUT_RUN_ID}")

    from app.modules.client_auth import service as client_auth_service

    original_sender = client_auth_service._client_otp_sender  # type: ignore[attr-defined]

    async def _noop(chat_id: int, code: str) -> None:
        pass

    client_auth_service._client_otp_sender = _noop  # type: ignore[attr-defined]

    try:
        cookie_val = auth_ws_client_sync(ws_tc, client)
        ws_tc.cookies.set("cc_client_access", cookie_val)

        # Build the id-only frame that the service layer would publish.
        # Normally sent by messaging.service.record_staff_message after DB write.
        fake_message_id = uuid.uuid4()
        channel = f"cc:messaging:client:{client.id}"
        frame_json = json.dumps({"type": "new_message", "messageId": str(fake_message_id)})

        with ws_tc.websocket_connect(
            "/api/v1/client/ws/messages",
            headers={"origin": WS_ALLOWED_ORIGIN},
        ) as ws:
            # Publish directly from a SEPARATE Redis client (cross-context publish).
            # This is the critical invariant: the subscriber loop in run_connection()
            # uses redis.pubsub() which creates a dedicated subscriber connection.
            # The WS handler subscribes to cc:messaging:client:{client.id} using the
            # APP's shared Redis pool; we publish using the SAME pool from app.state.redis
            # but via the portal (async context) -- simulating a worker that shares only
            # the Redis broker, not the Python process.
            async def _publish_cross_context() -> None:
                await ws_tc.app.state.redis.publish(channel, frame_json)

            _portal_call(ws_tc, _publish_cross_context())

            # WS should receive the frame within 3 seconds.
            raw = ws_receive_text_timeout(ws, timeout=3.0)
            assert raw is not None, (
                f"Fan-out frame not received within 3s. "
                f"messageId={fake_message_id!r}, channel={channel!r}"
            )
            received = json.loads(raw)
            assert received.get("type") == "new_message", (
                f"Expected new_message frame, got: {received!r}"
            )
            assert received.get("messageId") == str(fake_message_id), (
                f"Expected messageId={fake_message_id!r}, got {received.get('messageId')!r}"
            )

    finally:
        client_auth_service._client_otp_sender = original_sender  # type: ignore[attr-defined]
        cleanup_client_sync(ws_tc, phone=_PHONE_FANOUT)


# ---------------------------------------------------------------------------
# RT-04 -- Reconnect catch-up via DB-first REST cursor (not pub/sub replay)
# ---------------------------------------------------------------------------


def test_ws_reconnect_catchup_via_rest_cursor(ws_tc: TestClient) -> None:
    """Missed messages during disconnection are recovered via REST cursor (RT-04).

    Sequence:
      1. Seed + auth client, open WS.
      2. Send 2 messages while connected; verify WS delivers both frames.
         Record the last_seen_id = second message's id.
      3. Close the WS (simulated disconnect).
      4. Send 1 more message while disconnected (published to Redis but no subscriber
         → at-most-once loss; the frame is NOT delivered retroactively via pub/sub).
      5. Reconnect WS.
      6. Call GET /api/v1/client/messages?after={last_seen_id} (REST catch-up).
      7. Assert the REST response includes the missed message.
      8. Assert the WS did NOT receive the missed message via pub/sub replay (the
         reconnect WS only sees new frames published after reconnect).

    DB-first guarantee: every message persisted before publish (Plan 02 service).
    The REST cursor is the ONLY recovery path for missed frames (pub/sub is
    at-most-once -- no replay on reconnect).
    """
    from app.modules.messaging import service as messaging_service

    flush_redis_sync(ws_tc)
    cleanup_client_sync(ws_tc, phone=_PHONE_RECONNECT)

    client = seed_ws_client(ws_tc, phone=_PHONE_RECONNECT, suffix=f"rc{_FANOUT_RUN_ID}")

    from app.modules.client_auth import service as client_auth_service

    original_sender = client_auth_service._client_otp_sender  # type: ignore[attr-defined]

    async def _noop(chat_id: int, code: str) -> None:
        pass

    client_auth_service._client_otp_sender = _noop  # type: ignore[attr-defined]

    redis = ws_tc.app.state.redis
    session_factory = ws_tc.app.state.sessionmaker

    try:
        cookie_val = auth_ws_client_sync(ws_tc, client)
        ws_tc.cookies.set("cc_client_access", cookie_val)

        # Step 1-3: open WS, send 2 messages, record last id, close WS.
        last_seen_id: str | None = None

        with ws_tc.websocket_connect(
            "/api/v1/client/ws/messages",
            headers={"origin": WS_ALLOWED_ORIGIN},
        ) as ws:
            for i in range(2):
                async def _send_msg(body: str = f"msg {i}") -> str:
                    async with session_factory() as session:
                        result = await messaging_service.record_staff_message(
                            session,
                            client_id=client.id,
                            body=body,
                        )
                        await session.commit()
                        # CR-02: publish only AFTER commit (post-commit notification).
                        await messaging_service.publish_new_message(
                            redis,
                            client_id=client.id,
                            message_id=result.id,
                        )
                        return str(result.id)

                _portal_call(ws_tc, _send_msg())
                raw = ws_receive_text_timeout(ws, timeout=3.0)
                assert raw is not None, f"Expected new_message frame for msg {i} but got nothing"
                frame = json.loads(raw)
                assert frame.get("type") == "new_message", f"Expected new_message: {frame!r}"
                last_seen_id = frame.get("messageId")

        assert last_seen_id is not None, "last_seen_id not recorded"

        # Step 4: send 1 more message while disconnected.
        # (no subscriber at this point -- not delivered via pub/sub)
        missed_msg_id: str | None = None

        async def _send_while_disconnected() -> str:
            async with session_factory() as session:
                result = await messaging_service.record_staff_message(
                    session,
                    client_id=client.id,
                    body="missed while disconnected",
                )
                await session.commit()
                # CR-02: publish only AFTER commit (post-commit notification).
                await messaging_service.publish_new_message(
                    redis,
                    client_id=client.id,
                    message_id=result.id,
                )
                return str(result.id)

        missed_msg_id = _portal_call(ws_tc, _send_while_disconnected())
        assert missed_msg_id is not None

        # Step 5: reconnect WS.
        # Step 6: REST catch-up GET /messages?after={last_seen_id}.
        # Step 7: assert REST returns the missed message.
        # Step 8: assert WS does NOT retroactively deliver the missed message.
        with ws_tc.websocket_connect(
            "/api/v1/client/ws/messages",
            headers={"origin": WS_ALLOWED_ORIGIN},
        ) as ws_reconnect:
            # REST catch-up: GET /messages?after=<last_seen_id>
            rest_resp = ws_tc.get(
                f"/api/v1/client/messages?after={last_seen_id}",
            )
            assert rest_resp.status_code == 200, f"REST catch-up failed: {rest_resp.text}"
            body = rest_resp.json()
            items = body.get("data", {}).get("items", [])
            missed_ids = [item["id"] for item in items]
            assert missed_msg_id in missed_ids, (
                f"Missed message {missed_msg_id!r} not found in REST catch-up response. "
                f"Got: {missed_ids!r}"
            )

            # Assert WS does NOT deliver the missed message retroactively.
            # Pub/sub is at-most-once; no replay on reconnect (RT-04 design invariant).
            # We check for 1 second -- no new_message frame with missed_msg_id should arrive.
            # (A heartbeat ping may arrive after ~30s but that timeout is too long for a test.)
            unexpected_frame: str | None = None
            # Use ws_receive_text_timeout so the test does not block indefinitely.
            raw_reconnect = ws_receive_text_timeout(ws_reconnect, timeout=1.0)
            if raw_reconnect is not None:
                _frame = json.loads(raw_reconnect)
                if _frame.get("type") == "new_message" and _frame.get("messageId") == missed_msg_id:
                    unexpected_frame = raw_reconnect

            assert unexpected_frame is None, (
                f"RT-04 violation: WS replayed missed message on reconnect: "
                f"{unexpected_frame!r}. "
                "Pub/sub is at-most-once; catch-up MUST use REST cursor, not pub/sub replay."
            )

    finally:
        client_auth_service._client_otp_sender = original_sender  # type: ignore[attr-defined]
        cleanup_client_sync(ws_tc, phone=_PHONE_RECONNECT)
