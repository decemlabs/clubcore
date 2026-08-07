"""Phase 91 Plan 02 — WS read_receipt + typing fan-out, IDOR isolation,
end-to-end reply-as-read, and PATCH polling-fallback regression.

Covers RCPT-01, RCPT-02, RCPT-03 over the live WS transport:
  test_ws_read_receipt_fanout
      A read_receipt frame published post-commit reaches the client's open WS
      connection (fan-out). Verifies that A's WS receives {type:"read_receipt",
      readAt:...} within 3 s.
  test_ws_typing_fanout
      A typing frame reaches the client's open WS connection. Verifies
      {type:"typing", actor:"staff"} with no body/preview/messageId key
      (T-91-LEAK regression guard).
  test_ws_idor_client_a_does_not_receive_client_b_receipt_or_typing
      Client A's WS never sees client B's read_receipt or typing frame
      (T-91-IDOR over the new Phase 91 event types).
  test_ws_reply_as_read_e2e
      End-to-end: seed client messages → record_staff_message → commit →
      publish_read_receipt delivers a read_receipt frame to A's WS; GET confirms
      client messages carry non-null readAt (RCPT-01/03 persisted ✓✓).
  test_patch_read_polling_fallback_persists
      RCPT-03 polling-fallback regression: PATCH /client/messages/read persists
      read state even when WS is not the delivery path.

All tests use Starlette TestClient.websocket_connect() (not httpx ASGITransport —
P13: httpx cannot upgrade to WS). Tests are SYNCHRONOUS pytest functions.

Cross-context publish invariant (T-91-IDOR):
  The IDOR test publishes ONLY to the B-channel and asserts A receives nothing.
  publish_read_receipt / publish_typing derive the channel from client_id only
  (the test exercises the real derivation, not a hand-built string).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

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

# Unique 4-digit run-id prevents phone/email collisions between test runs.
_RUN_ID = str(uuid.uuid4().int % 10000).zfill(4)
_PHONE_A = f"+7916921{_RUN_ID}"
_PHONE_B = f"+7916922{_RUN_ID}"
_PHONE_E2E = f"+7916923{_RUN_ID}"
_PHONE_POLL = f"+7916924{_RUN_ID}"


# ---------------------------------------------------------------------------
# RCPT-01 — read_receipt fan-out over WS
# ---------------------------------------------------------------------------


def test_ws_read_receipt_fanout(ws_tc: TestClient) -> None:
    """A read_receipt frame published post-commit reaches the client's open WS (RCPT-01).

    Sequence:
      1. Seed + auth client A; open A's WS.
      2. _portal_call(publish_read_receipt) simulates the post-commit publish.
      3. Assert A's WS receives {type:"read_receipt", readAt:...} within 3 s.

    Proves publish_read_receipt fan-out over the cc:messaging:client:{client_id} channel.
    """
    from app.modules.messaging import service as messaging_service

    flush_redis_sync(ws_tc)
    cleanup_client_sync(ws_tc, phone=_PHONE_A)

    client_a = seed_ws_client(ws_tc, phone=_PHONE_A, suffix=f"rra{_RUN_ID}")

    from app.modules.client_auth import service as client_auth_service

    original_sender = client_auth_service._client_otp_sender  # type: ignore[attr-defined]

    async def _noop(chat_id: int, code: str) -> None:
        pass

    client_auth_service._client_otp_sender = _noop  # type: ignore[attr-defined]

    try:
        cookie_val = auth_ws_client_sync(ws_tc, client_a)
        ws_tc.cookies.set("cc_client_access", cookie_val)

        read_at_now = datetime.now(tz=UTC)

        with ws_tc.websocket_connect(
            "/api/v1/client/ws/messages",
            headers={"origin": WS_ALLOWED_ORIGIN},
        ) as ws:
            # Post-commit publish (CR-02 / T-91-PHANTOM): in production this fires
            # after session.commit(); here we simulate the post-commit publish step directly.
            async def _publish() -> None:
                await messaging_service.publish_read_receipt(
                    ws_tc.app.state.redis,
                    client_id=client_a.id,
                    read_at=read_at_now,
                )

            _portal_call(ws_tc, _publish())

            raw = ws_receive_text_timeout(ws, timeout=3.0)
            assert raw is not None, (
                f"read_receipt frame not received within 3 s. "
                f"client_id={client_a.id!r}, read_at={read_at_now!r}"
            )

            frame = json.loads(raw)
            assert frame.get("type") == "read_receipt", (
                f"Expected type='read_receipt', got: {frame!r}"
            )
            # readAt must be present and parseable (T-91-PHANTOM: reflects committed read_at).
            read_at_wire = frame.get("readAt")
            assert read_at_wire is not None, (
                f"Expected 'readAt' key in read_receipt frame, got: {frame!r}"
            )
            # Must be a parseable ISO datetime string.
            datetime.fromisoformat(read_at_wire)

    finally:
        client_auth_service._client_otp_sender = original_sender  # type: ignore[attr-defined]
        cleanup_client_sync(ws_tc, phone=_PHONE_A)


# ---------------------------------------------------------------------------
# RCPT-02 — typing fan-out over WS  (T-91-LEAK: no content keys)
# ---------------------------------------------------------------------------


def test_ws_typing_fanout(ws_tc: TestClient) -> None:
    """A typing frame published reaches the client's WS with no content leakage (RCPT-02).

    Sequence:
      1. Seed + auth client A; open A's WS.
      2. _portal_call(publish_typing) — ephemeral, no DB, no commit dependency.
      3. Assert A's WS receives exactly {type:"typing", actor:"staff"}.
      4. Assert the frame has NO body, preview, or messageId key (T-91-LEAK guard).
    """
    from app.modules.messaging import service as messaging_service

    flush_redis_sync(ws_tc)
    cleanup_client_sync(ws_tc, phone=_PHONE_A)

    client_a = seed_ws_client(ws_tc, phone=_PHONE_A, suffix=f"rta{_RUN_ID}")

    from app.modules.client_auth import service as client_auth_service

    original_sender = client_auth_service._client_otp_sender  # type: ignore[attr-defined]

    async def _noop(chat_id: int, code: str) -> None:
        pass

    client_auth_service._client_otp_sender = _noop  # type: ignore[attr-defined]

    try:
        cookie_val = auth_ws_client_sync(ws_tc, client_a)
        ws_tc.cookies.set("cc_client_access", cookie_val)

        with ws_tc.websocket_connect(
            "/api/v1/client/ws/messages",
            headers={"origin": WS_ALLOWED_ORIGIN},
        ) as ws:

            async def _publish() -> None:
                await messaging_service.publish_typing(
                    ws_tc.app.state.redis,
                    client_id=client_a.id,
                )

            _portal_call(ws_tc, _publish())

            raw = ws_receive_text_timeout(ws, timeout=3.0)
            assert raw is not None, (
                f"typing frame not received within 3 s. client_id={client_a.id!r}"
            )

            frame = json.loads(raw)
            assert frame.get("type") == "typing", f"Expected type='typing', got: {frame!r}"
            assert frame.get("actor") == "staff", f"Expected actor='staff', got: {frame!r}"

            # T-91-LEAK: typing frame MUST NOT carry message content.
            for forbidden_key in ("body", "preview", "messageId", "message_id"):
                assert forbidden_key not in frame, (
                    f"T-91-LEAK violation: typing frame contains forbidden key "
                    f"{forbidden_key!r}: {frame!r}"
                )

    finally:
        client_auth_service._client_otp_sender = original_sender  # type: ignore[attr-defined]
        cleanup_client_sync(ws_tc, phone=_PHONE_A)


# ---------------------------------------------------------------------------
# T-91-IDOR — client A never receives client B's read_receipt or typing frames
# ---------------------------------------------------------------------------


def test_ws_idor_client_a_does_not_receive_client_b_receipt_or_typing(
    ws_tc: TestClient,
) -> None:
    """Client A's WS never receives client B's read_receipt or typing frame (T-91-IDOR).

    Sequence:
      1. Seed + auth client A; seed client B (no auth).
      2. Open only client A's WS.
      3. Publish a read_receipt AND a typing frame to client B's channel.
      4. Assert A receives NEITHER within ~1 s (ws_receive_text_timeout returns None).

    The test uses publish_read_receipt / publish_typing directly so the channel
    derivation (from client_id) is the code under test — not a hand-built string.
    """
    from app.modules.messaging import service as messaging_service

    flush_redis_sync(ws_tc)
    cleanup_client_sync(ws_tc, phone=_PHONE_A)
    cleanup_client_sync(ws_tc, phone=_PHONE_B)

    client_a = seed_ws_client(ws_tc, phone=_PHONE_A, suffix=f"ia{_RUN_ID}")
    client_b = seed_ws_client(ws_tc, phone=_PHONE_B, suffix=f"ib{_RUN_ID}")

    from app.modules.client_auth import service as client_auth_service

    original_sender = client_auth_service._client_otp_sender  # type: ignore[attr-defined]

    async def _noop(chat_id: int, code: str) -> None:
        pass

    client_auth_service._client_otp_sender = _noop  # type: ignore[attr-defined]

    try:
        cookie_val_a = auth_ws_client_sync(ws_tc, client_a)
        ws_tc.cookies.set("cc_client_access", cookie_val_a)

        redis = ws_tc.app.state.redis

        with ws_tc.websocket_connect(
            "/api/v1/client/ws/messages",
            headers={"origin": WS_ALLOWED_ORIGIN},
        ) as ws_a:
            # Publish read_receipt + typing to client B's channel only.
            async def _publish_to_b() -> None:
                await messaging_service.publish_read_receipt(
                    redis,
                    client_id=client_b.id,
                    read_at=datetime.now(tz=UTC),
                )
                await messaging_service.publish_typing(
                    redis,
                    client_id=client_b.id,
                )

            _portal_call(ws_tc, _publish_to_b())

            # A's WS must receive nothing — both event types go to B's channel only.
            raw = ws_receive_text_timeout(ws_a, timeout=1.0)

            # If something arrives, confirm it is NOT a read_receipt or typing frame
            # for client B (any such frame would be an IDOR violation).
            if raw is not None:
                parsed = json.loads(raw)
                assert parsed.get("type") not in ("read_receipt", "typing"), (
                    f"T-91-IDOR violation: client A received a {parsed.get('type')!r} "
                    f"frame intended for client B: {parsed!r}"
                )

    finally:
        client_auth_service._client_otp_sender = original_sender  # type: ignore[attr-defined]
        cleanup_client_sync(ws_tc, phone=_PHONE_A)
        cleanup_client_sync(ws_tc, phone=_PHONE_B)


# ---------------------------------------------------------------------------
# RCPT-01 / RCPT-03 — end-to-end reply-as-read (WS delivery + DB persistence)
# ---------------------------------------------------------------------------


def test_ws_reply_as_read_e2e(ws_tc: TestClient) -> None:
    """End-to-end reply-as-read: record_staff_message → commit → publish delivers
    a read_receipt frame to the client WS, and GET confirms non-null readAt on
    client messages (RCPT-01/03 persisted ✓✓, T-91-PHANTOM ordering enforced).

    Sequence:
      1. Seed + auth client A; open A's WS.
      2. Via _portal_call: seed 2 role='client' messages via send_client_message.
      3. Via _portal_call: record_staff_message → session.commit() →
         if reply_read_at: publish_read_receipt.
      4. Assert A's WS receives {type:"read_receipt", readAt:...}.
      5. Via REST GET /api/v1/client/messages (ws_tc HTTP transport), assert the two
         client messages now carry non-null readAt (persisted ✓✓).
    """
    from app.modules.messaging import service as messaging_service
    from app.modules.messaging.schemas import SendMessageRequest

    flush_redis_sync(ws_tc)
    cleanup_client_sync(ws_tc, phone=_PHONE_E2E)

    client_a = seed_ws_client(ws_tc, phone=_PHONE_E2E, suffix=f"e2e{_RUN_ID}")

    from app.modules.client_auth import service as client_auth_service

    original_sender = client_auth_service._client_otp_sender  # type: ignore[attr-defined]

    async def _noop(chat_id: int, code: str) -> None:
        pass

    client_auth_service._client_otp_sender = _noop  # type: ignore[attr-defined]

    try:
        cookie_val = auth_ws_client_sync(ws_tc, client_a)
        ws_tc.cookies.set("cc_client_access", cookie_val)

        redis = ws_tc.app.state.redis
        session_factory = ws_tc.app.state.sessionmaker

        # Step 2: seed 2 client messages before opening the WS.
        async def _seed_client_msgs() -> None:
            async with session_factory() as session:
                for body in ("клиент: первый вопрос", "клиент: второй вопрос"):
                    await messaging_service.send_client_message(
                        session,
                        client_id=client_a.id,
                        payload=SendMessageRequest(body=body),
                    )
                await session.commit()

        _portal_call(ws_tc, _seed_client_msgs())

        with ws_tc.websocket_connect(
            "/api/v1/client/ws/messages",
            headers={"origin": WS_ALLOWED_ORIGIN},
        ) as ws:
            # Step 3: staff reply — DB-first + post-commit publish (T-91-PHANTOM).
            reply_read_at: datetime | None = None

            async def _staff_reply() -> None:
                nonlocal reply_read_at
                async with session_factory() as session:
                    result = await messaging_service.record_staff_message(
                        session,
                        client_id=client_a.id,
                        body="сотрудник: ответ",
                    )
                    await session.commit()
                    # Publish AFTER commit (CR-02 / T-91-PHANTOM ordering).
                    await messaging_service.publish_new_message(
                        redis,
                        client_id=client_a.id,
                        message_id=result.id,
                    )
                    if result.reply_read_at is not None:
                        reply_read_at = result.reply_read_at
                        await messaging_service.publish_read_receipt(
                            redis,
                            client_id=client_a.id,
                            read_at=result.reply_read_at,
                        )

            _portal_call(ws_tc, _staff_reply())

            # Step 4: collect WS frames; find the read_receipt frame.
            import time

            receipt_frame: dict | None = None
            deadline = time.monotonic() + 4.0
            while time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                raw = ws_receive_text_timeout(ws, timeout=min(remaining, 1.0))
                if raw is None:
                    break
                parsed = json.loads(raw)
                if parsed.get("type") == "read_receipt":
                    receipt_frame = parsed
                    break  # found it; stop collecting

            assert receipt_frame is not None, (
                "read_receipt frame not received within 4 s on reply-as-read e2e path. "
                f"reply_read_at captured: {reply_read_at!r}"
            )
            read_at_wire = receipt_frame.get("readAt")
            assert read_at_wire is not None, f"read_receipt frame missing readAt: {receipt_frame!r}"
            received_read_at = datetime.fromisoformat(read_at_wire)
            assert reply_read_at is not None, (
                "reply_read_at was None — record_staff_message found no unread client messages"
            )
            # The WS readAt must match (or be >= first client msg sent_at).
            assert (
                received_read_at >= reply_read_at.replace(tzinfo=UTC)
                if (reply_read_at.tzinfo is None)
                else received_read_at >= reply_read_at
            ), f"WS readAt={received_read_at!r} is before reply_read_at={reply_read_at!r}"

        # Step 5: confirm persistence via REST GET (RCPT-01 ✓✓ persisted).
        get_resp = ws_tc.get("/api/v1/client/messages")
        assert get_resp.status_code == 200, f"GET /messages failed: {get_resp.text}"
        items = get_resp.json()["data"]["items"]

        # The two role='client' messages must now have a non-null readAt.
        client_items = [item for item in items if item["role"] == "client"]
        assert len(client_items) == 2, (
            f"Expected 2 client messages, got {len(client_items)}: {items!r}"
        )
        for item in client_items:
            assert item.get("readAt") is not None, (
                f"RCPT-01 violation: client message {item['id']!r} still has null readAt "
                f"after reply-as-read: {item!r}"
            )

    finally:
        client_auth_service._client_otp_sender = original_sender  # type: ignore[attr-defined]
        cleanup_client_sync(ws_tc, phone=_PHONE_E2E)


# ---------------------------------------------------------------------------
# RCPT-03 polling-fallback — PATCH /client/messages/read persists read state
# ---------------------------------------------------------------------------


def test_patch_read_polling_fallback_persists(ws_tc: TestClient) -> None:
    """PATCH /client/messages/read persists read state without a live WS (RCPT-03 fallback).

    The polling-fallback path (no WS connection) must still work: the existing
    PATCH endpoint marks staff messages read and resets unreadCount to 0.

    Sequence:
      1. Seed + auth client; record a staff message → unreadCount > 0.
      2. GET /messages: assert unreadCount > 0.
      3. PATCH /client/messages/read: assert 204.
      4. GET /messages: assert unreadCount == 0.

    Regression guard: this path must not break if the WS read_receipt
    delivery path is added (the two are complementary, not mutually exclusive).
    """
    from app.modules.messaging import service as messaging_service

    flush_redis_sync(ws_tc)
    cleanup_client_sync(ws_tc, phone=_PHONE_POLL)

    client = seed_ws_client(ws_tc, phone=_PHONE_POLL, suffix=f"pf{_RUN_ID}")

    from app.modules.client_auth import service as client_auth_service

    original_sender = client_auth_service._client_otp_sender  # type: ignore[attr-defined]

    async def _noop(chat_id: int, code: str) -> None:
        pass

    client_auth_service._client_otp_sender = _noop  # type: ignore[attr-defined]

    try:
        session_factory = ws_tc.app.state.sessionmaker

        # Seed a staff message so client_unread_count > 0.
        async def _seed_staff_msg() -> None:
            async with session_factory() as session:
                await messaging_service.record_staff_message(
                    session,
                    client_id=client.id,
                    body="сотрудник: привет",
                )
                await session.commit()

        _portal_call(ws_tc, _seed_staff_msg())

        cookie_val = auth_ws_client_sync(ws_tc, client)
        ws_tc.cookies.set("cc_client_access", cookie_val)
        csrf_token = ws_tc.cookies.get("clubcore_client_csrf") or ""

        # GET: unreadCount must be > 0 (staff message not yet read by client).
        get_resp = ws_tc.get("/api/v1/client/messages")
        assert get_resp.status_code == 200, f"GET /messages failed: {get_resp.text}"
        unread_before = get_resp.json()["data"]["unreadCount"]
        assert unread_before > 0, (
            f"Expected unreadCount > 0 after staff message, got {unread_before}. "
            "PATCH polling-fallback test requires at least one unread staff message."
        )

        # PATCH /client/messages/read → 204 (marks all STAFF messages read).
        patch_resp = ws_tc.patch(
            "/api/v1/client/messages/read",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert patch_resp.status_code == 204, (
            f"Expected 204 from PATCH /read, got {patch_resp.status_code}: {patch_resp.text}"
        )

        # GET again: unreadCount must be 0 (RCPT-03 polling-fallback persisted).
        get_resp2 = ws_tc.get("/api/v1/client/messages")
        assert get_resp2.status_code == 200, f"Second GET /messages failed: {get_resp2.text}"
        unread_after = get_resp2.json()["data"]["unreadCount"]
        assert unread_after == 0, (
            f"RCPT-03 polling-fallback failure: unreadCount={unread_after} after PATCH /read "
            f"(expected 0). PATCH /messages/read must persist read state without a live WS."
        )

    finally:
        client_auth_service._client_otp_sender = original_sender  # type: ignore[attr-defined]
        cleanup_client_sync(ws_tc, phone=_PHONE_POLL)
