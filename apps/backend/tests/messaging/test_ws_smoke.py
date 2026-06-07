"""Phase 90 Plan 03 Task 1 -- WS test convention smoke test.

Establishes and proves the Starlette TestClient.websocket_connect() convention
for all WS tests in this module (P13 -- httpx ASGITransport cannot do WS upgrade).

After Task 2 lands the @router.websocket('/ws/messages') endpoint, this test
MUST pass (it will automatically pass once the endpoint exists).
"""

from __future__ import annotations

import uuid

from starlette.testclient import TestClient

from tests.messaging.conftest import (
    WS_ALLOWED_ORIGIN,
    auth_ws_client_sync,
    cleanup_client_sync,
    flush_redis_sync,
    seed_ws_client,
)

# Phone must be unique per test invocation to avoid unique-constraint collisions.
# Use a random 4-digit numeric suffix (0000-9999) so the phone is valid E.164.
_SMOKE_RUN_ID = str(uuid.uuid4().int % 10000).zfill(4)
_PHONE_SMOKE = f"+7916910{_SMOKE_RUN_ID}"

# ---------------------------------------------------------------------------
# Convention-proving test: connect with a valid cookie -> endpoint accepts
# ---------------------------------------------------------------------------


def test_ws_convention_authenticated_client_connects(ws_tc: TestClient) -> None:
    """Prove the Starlette TestClient WS convention (P13).

    An authenticated client (valid cc_client_access cookie) can open a WS to
    /api/v1/client/ws/messages and the connection is accepted.

    This is the canonical WS test template for this module:
      1. Use ws_tc fixture (TestClient with lifespan active).
      2. Seed + authenticate a client via the OTP flow (sync).
      3. Open the WS with cc_client_access cookie + allowed Origin.
      4. Assert the connection opens without an immediate rejection.
    """
    flush_redis_sync(ws_tc)
    cleanup_client_sync(ws_tc, phone=_PHONE_SMOKE)  # pre-clean in case prior run left residue

    client = seed_ws_client(ws_tc, phone=_PHONE_SMOKE, suffix=_SMOKE_RUN_ID)

    # Stub out the OTP Telegram sender so no real DM is needed.
    from app.modules.client_auth import service as client_auth_service

    original_sender = client_auth_service._client_otp_sender  # type: ignore[attr-defined]

    async def _noop(chat_id: int, code: str) -> None:
        pass

    client_auth_service._client_otp_sender = _noop  # type: ignore[attr-defined]

    try:
        cookie_val = auth_ws_client_sync(ws_tc, client)

        # Set the auth cookie on the TestClient's cookie jar directly (per
        # Starlette's deprecation of per-request cookies on websocket_connect).
        ws_tc.cookies.set("cc_client_access", cookie_val)
        with ws_tc.websocket_connect(
            "/api/v1/client/ws/messages",
            headers={"origin": WS_ALLOWED_ORIGIN},
        ) as ws:
            # Convention proven: connection opened without WebSocketDisconnect.
            # Send a no-op text to confirm the connection is live.
            # The server ignores inbound text in Phase 90 (only server->client
            # new_message frames are implemented; client sends via REST POST).
            ws.send_text("ping")
            # Connection did not close immediately -- convention established.
    finally:
        client_auth_service._client_otp_sender = original_sender  # type: ignore[attr-defined]
        cleanup_client_sync(ws_tc, phone=_PHONE_SMOKE)
