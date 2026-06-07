"""Phase 90 Plan 03 Task 3 -- WS auth / IDOR invariant tests.

Covers RT-02 (auth + IDOR over WS) and related threat mitigations:
  T-90-10: Cookie auth -- no URL token; missing cookie → 401 pre-accept.
  T-90-11: CSWSH guard (verify_ws_origin) -- disallowed Origin → close 1008.
  T-90-12: IDOR over WS -- client A's channel never delivers client B's frames.

All tests use the Starlette TestClient.websocket_connect() convention established
in tests/messaging/conftest.py (P13 -- httpx ASGITransport cannot do WS upgrade).

WS rejection behaviour (Starlette TestClient):
  - No cookie (no auth): FastAPI raises HTTP 401 BEFORE the WS handshake completes.
    TestClient raises WebSocketDenialResponse (status_code=401).
  - Disallowed Origin: verify_ws_origin raises WebSocketException(code=1008).
    The WS handshake completes (accept happens inside the ASGI layer) but the
    server immediately sends a close frame with code 1008.
    TestClient raises WebSocketDisconnect(code=1008).
"""

from __future__ import annotations

import json
import uuid

from starlette.testclient import TestClient, WebSocketDenialResponse
from starlette.websockets import WebSocketDisconnect

from tests.messaging.conftest import (
    WS_ALLOWED_ORIGIN,
    _portal_call,
    auth_ws_client_sync,
    cleanup_client_sync,
    flush_redis_sync,
    seed_ws_client,
    ws_receive_text_timeout,
)

# Unique 4-digit numeric suffix per test invocation to avoid unique-constraint collisions.
_AUTH_RUN_ID = str(uuid.uuid4().int % 10000).zfill(4)
_PHONE_A = f"+7916911{_AUTH_RUN_ID}"
_PHONE_B = f"+7916912{_AUTH_RUN_ID}"


# ---------------------------------------------------------------------------
# T-90-10 -- Missing / invalid cookie is rejected before accept (auth gate)
# ---------------------------------------------------------------------------


def test_ws_no_cookie_rejected_401(ws_tc: TestClient) -> None:
    """A WS upgrade without cc_client_access cookie is rejected with 401 (T-90-10).

    The missing-cookie path raises HTTP 401 BEFORE the WS handshake completes.
    TestClient raises WebSocketDenialResponse (status_code=401), not WebSocketDisconnect.
    No frame is ever delivered to the caller.
    """
    flush_redis_sync(ws_tc)
    # Clear any stale cookies on the test client
    ws_tc.cookies.clear()

    try:
        with ws_tc.websocket_connect(
            "/api/v1/client/ws/messages",
            headers={"origin": WS_ALLOWED_ORIGIN},
        ):
            raise AssertionError("Connection should have been rejected with 401")
    except WebSocketDenialResponse as exc:
        assert exc.status_code == 401, f"Expected 401, got {exc.status_code}"


# ---------------------------------------------------------------------------
# T-90-11 -- CSWSH guard: disallowed Origin is rejected (close 1008)
# ---------------------------------------------------------------------------


def test_ws_bad_origin_rejected_1008(ws_tc: TestClient) -> None:
    """A WS upgrade from a disallowed Origin is rejected with close code 1008 (T-90-11).

    verify_ws_origin raises WebSocketException(code=1008) before accept().
    TestClient raises WebSocketDisconnect(code=1008).
    No frame is delivered.
    """
    flush_redis_sync(ws_tc)
    ws_tc.cookies.clear()

    try:
        with ws_tc.websocket_connect(
            "/api/v1/client/ws/messages",
            headers={"origin": "http://evil.example.com"},
        ):
            raise AssertionError("Connection should have been rejected with 1008")
    except WebSocketDisconnect as exc:
        assert exc.code == 1008, f"Expected close code 1008, got {exc.code}"


def test_ws_missing_origin_rejected_1008(ws_tc: TestClient) -> None:
    """A WS upgrade with no Origin header is rejected with close code 1008 (T-90-11).

    An absent Origin is treated the same as a disallowed one -- cannot confirm
    same-origin intent so the CSWSH guard rejects it.
    """
    flush_redis_sync(ws_tc)
    ws_tc.cookies.clear()

    try:
        with ws_tc.websocket_connect(
            "/api/v1/client/ws/messages",
            # No 'origin' header passed
        ):
            raise AssertionError("Connection should have been rejected with 1008")
    except WebSocketDisconnect as exc:
        assert exc.code == 1008, f"Expected close code 1008, got {exc.code}"


# ---------------------------------------------------------------------------
# T-90-12 -- IDOR over WS: client A never receives client B's frames
# ---------------------------------------------------------------------------


def test_ws_idor_client_a_does_not_receive_client_b_messages(ws_tc: TestClient) -> None:
    """Client A's WS never receives new_message frames published for client B (T-90-12).

    Sequence:
      1. Seed client A and client B.
      2. Authenticate client A, open client A's WS connection.
      3. Publish a staff message for client B via record_staff_message().
      4. Assert A's WS receives NOTHING within a short timeout (1 second).
      5. Publish a staff message for client A.
      6. Assert A's WS DOES receive the frame with the correct messageId.

    This proves cc:messaging:client:{client_id} is principal-keyed and IDOR-safe.
    """
    from app.modules.messaging import service as messaging_service
    from app.modules.messaging.schemas import SendMessageRequest  # noqa: F401

    flush_redis_sync(ws_tc)
    cleanup_client_sync(ws_tc, phone=_PHONE_A)
    cleanup_client_sync(ws_tc, phone=_PHONE_B)

    client_a = seed_ws_client(ws_tc, phone=_PHONE_A, suffix=f"a{_AUTH_RUN_ID}")
    client_b = seed_ws_client(ws_tc, phone=_PHONE_B, suffix=f"b{_AUTH_RUN_ID}")

    from app.modules.client_auth import service as client_auth_service

    original_sender = client_auth_service._client_otp_sender  # type: ignore[attr-defined]

    async def _noop(chat_id: int, code: str) -> None:
        pass

    client_auth_service._client_otp_sender = _noop  # type: ignore[attr-defined]

    try:
        cookie_val_a = auth_ws_client_sync(ws_tc, client_a)
        ws_tc.cookies.set("cc_client_access", cookie_val_a)

        redis = ws_tc.app.state.redis
        session_factory = ws_tc.app.state.sessionmaker

        with ws_tc.websocket_connect(
            "/api/v1/client/ws/messages",
            headers={"origin": WS_ALLOWED_ORIGIN},
        ) as ws_a:
            # Publish a message for client B -- A's WS must NOT receive it.
            async def _send_to_b() -> None:
                async with session_factory() as session:
                    await messaging_service.record_staff_message(
                        session,
                        client_id=client_b.id,
                        body="Hello client B -- should not reach client A",
                        redis=redis,
                    )
                    await session.commit()

            # Publish a message for client A -- A MUST receive it.
            client_a_message_id: str | None = None

            async def _send_to_a() -> None:
                nonlocal client_a_message_id
                async with session_factory() as session:
                    result = await messaging_service.record_staff_message(
                        session,
                        client_id=client_a.id,
                        body="Hello client A -- you SHOULD receive this",
                        redis=redis,
                    )
                    await session.commit()
                    client_a_message_id = str(result.id)

            # Strategy: publish B's message, then A's message immediately.
            # A's WS MUST receive A's frame and MUST NOT receive B's frame.
            # We publish both before receiving so daemon-thread race conditions
            # cannot steal the message between publish and receive.
            _portal_call(ws_tc, _send_to_b())
            _portal_call(ws_tc, _send_to_a())

            # Receive ALL frames that arrive within 3 seconds.
            # Collect up to 2 frames (only A's should appear).
            import time

            frames_received: list[str] = []
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                raw = ws_receive_text_timeout(ws_a, timeout=min(remaining, 1.0))
                if raw is None:
                    break
                frames_received.append(raw)
                # If we have A's frame, we can stop early.
                if any(
                    json.loads(f).get("messageId") == client_a_message_id
                    for f in frames_received
                ):
                    break

            assert len(frames_received) >= 1, (
                f"Expected at least 1 frame for client A but received none. "
                f"client_a_message_id={client_a_message_id!r}"
            )

            # Assert A received its own frame.
            frame_ids = [json.loads(f).get("messageId") for f in frames_received]
            assert client_a_message_id in frame_ids, (
                f"Expected frame for client A (messageId={client_a_message_id!r}) "
                f"but got: {frame_ids!r}"
            )

            # Assert B's frame is NOT among the received frames.
            for raw_frame in frames_received:
                parsed = json.loads(raw_frame)
                # B's message id is unknown from A's perspective, but if any frame
                # arrived that is NOT A's message, that is an IDOR violation.
                if parsed.get("messageId") != client_a_message_id:
                    raise AssertionError(
                        f"IDOR violation: client A received an unexpected frame: {parsed!r}. "
                        f"Only client A's own message (id={client_a_message_id!r}) is expected."
                    )

    finally:
        client_auth_service._client_otp_sender = original_sender  # type: ignore[attr-defined]
        cleanup_client_sync(ws_tc, phone=_PHONE_A)
        cleanup_client_sync(ws_tc, phone=_PHONE_B)
