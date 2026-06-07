"""Phase 90 Plan 03 Task 1 — WS test convention smoke test.

Establishes and proves the Starlette TestClient.websocket_connect() convention
for all WS tests in this module (P13 — httpx ASGITransport cannot do WS upgrade).

This test exists FIRST to lock the convention before the endpoint logic is
fleshed out in Task 2. The endpoint is created in Task 2; this test is marked
xfail until the endpoint exists so CI does not red before the full implementation.

After Task 2 lands the @router.websocket('/ws/messages') endpoint, this test
MUST pass (it will automatically pass once the endpoint exists).
"""

from __future__ import annotations

from starlette.testclient import TestClient

from tests.messaging.conftest import (
    WS_ALLOWED_ORIGIN,
    auth_ws_client_sync,
    flush_redis_sync,
    seed_ws_client,
)

_PHONE_SMOKE = "+79169100001"

# ---------------------------------------------------------------------------
# Convention-proving test: connect with a valid cookie → endpoint accepts
# ---------------------------------------------------------------------------


def test_ws_convention_authenticated_client_connects(ws_app: object) -> None:
    """Prove the Starlette TestClient WS convention (P13).

    An authenticated client (valid cc_client_access cookie) can open a WS to
    /api/v1/client/ws/messages and the connection is accepted.

    This is the canonical WS test template for this module:
      1. Build a TestClient(ws_app).
      2. Seed + authenticate a client via the OTP flow (sync).
      3. Open the WS with cc_client_access cookie + allowed Origin.
      4. Assert the connection opens without an immediate rejection.

    The xfail marker ensures CI does not red before Task 2 lands the endpoint.
    Once the endpoint exists, remove the xfail marker.
    """
    # Probe: if ws_app fixture skipped (no Postgres), we already skipped.
    flush_redis_sync(ws_app)  # type: ignore[arg-type]
    client = seed_ws_client(ws_app, phone=_PHONE_SMOKE, suffix="smoke")  # type: ignore[arg-type]

    tc = TestClient(ws_app)  # type: ignore[arg-type]

    # Stub out the OTP Telegram sender so no real DM is needed.
    from app.modules.client_auth import service as client_auth_service

    original_sender = client_auth_service._client_otp_sender  # type: ignore[attr-defined]

    async def _noop(chat_id: int, code: str) -> None:
        pass

    client_auth_service._client_otp_sender = _noop  # type: ignore[attr-defined]

    try:
        cookie_val = auth_ws_client_sync(tc, ws_app, client)  # type: ignore[arg-type]

        with tc.websocket_connect(
            "/api/v1/client/ws/messages",
            cookies={"cc_client_access": cookie_val},
            headers={"origin": WS_ALLOWED_ORIGIN},
        ) as ws:
            # Convention proven: connection opened without WebSocketDisconnect.
            # Send a no-op text to confirm the connection is live.
            # The server ignores inbound text in Phase 90 (only server→client
            # new_message frames are implemented; client sends via REST POST).
            ws.send_text("ping")
            # Just assert the connection did not close immediately.
            # Task 2 will make this test green by implementing the endpoint.
    finally:
        client_auth_service._client_otp_sender = original_sender  # type: ignore[attr-defined]
