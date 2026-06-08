"""Integration tests for Phase 93 BRDG-02/BRDG-03: staff_reply_handler.

Tests the inbound staff→client reply path:
  1. live-anchor reply → staff message persisted + new_message published
  2. ≥2 anchors anti-misroute: reply to older anchor routes to its client only (BRDG-03)
  3. stale/None anchor → "не могу определить тред" DM + zero staff rows
  4. non-Reply (no reply_to_message) → "use Reply" hint + zero rows
  5. echo guard: is_bot=True → no-op
  6. replay guard: same update_id twice → exactly one staff row
  7. reply-as-read: prior unread client message present → publish_read_receipt fired

Approach: direct call to staff_reply_handler(update, context, ctx) with
stubbed update/context (SimpleNamespace), a real DB session (SAVEPOINT-mode),
fakeredis for Redis, and a StubTelegramSender for DM capture.

The handler is reached via ctx.messaging_service — no static module import
in handlers.py (integrations⊥modules contract).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import fakeredis.aioredis
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.telegram.handlers import HandlerContext, staff_reply_handler
from app.modules.auth import telegram_service
from app.modules.bookings import service as bookings_service
from app.modules.clients.models import Client
from app.modules.messaging import service as messaging_service
from app.modules.messaging.models import Message
from app.modules.schedule import service as schedule_service
from app.modules.visits import service as visits_service

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Helpers: update builders + context builder
# ---------------------------------------------------------------------------

_STAFF_CHAT_ID = 99999888


def _build_plain_update(
    *,
    chat_id: int = _STAFF_CHAT_ID,
    user_id: int = 1001,
    username: str | None = "staff_user",
    update_id: int = 1,
    text: str = "Hello plain message",
    is_bot: bool = False,
) -> SimpleNamespace:
    """Build an update with NO reply_to_message (plain message)."""
    eff_user = SimpleNamespace(id=user_id, username=username, is_bot=is_bot)
    eff_chat = SimpleNamespace(id=chat_id)
    message = SimpleNamespace(
        text=text,
        reply_to_message=None,
        chat=eff_chat,
        from_user=eff_user,
    )
    return SimpleNamespace(
        update_id=update_id,
        effective_user=eff_user,
        effective_chat=eff_chat,
        message=message,
    )


def _build_reply_update(
    *,
    chat_id: int = _STAFF_CHAT_ID,
    user_id: int = 1001,
    username: str | None = "staff_user",
    update_id: int = 2,
    reply_text: str = "Staff reply text",
    replied_to_message_id: int = 42,
    is_bot: bool = False,
) -> SimpleNamespace:
    """Build an update that is a Reply to a specific message_id."""
    eff_user = SimpleNamespace(id=user_id, username=username, is_bot=is_bot)
    eff_chat = SimpleNamespace(id=chat_id)
    reply_to = SimpleNamespace(message_id=replied_to_message_id)
    message = SimpleNamespace(
        text=reply_text,
        reply_to_message=reply_to,
        chat=eff_chat,
        from_user=eff_user,
    )
    return SimpleNamespace(
        update_id=update_id,
        effective_user=eff_user,
        effective_chat=eff_chat,
        message=message,
    )


def _build_ctx(
    db_session: AsyncSession,
    redis_client: Any,
    sender_stub: Any,
) -> HandlerContext:
    @asynccontextmanager
    async def _factory() -> AsyncIterator[AsyncSession]:
        yield db_session

    return HandlerContext(
        session_factory=_factory,  # type: ignore[arg-type]
        telegram_service=telegram_service,
        sender=sender_stub,
        visits_service=visits_service,
        redis=redis_client,
        bookings_service=bookings_service,
        schedule_service=schedule_service,
        messaging_service=messaging_service,
    )


def _build_bot_ctx(sender_stub: Any) -> SimpleNamespace:
    return SimpleNamespace(bot=SimpleNamespace(id=99))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _StubSender:
    """Record send_text_dm calls; discard bot reference."""

    def __init__(self) -> None:
        self.text_calls: list[tuple[int, str]] = []

    async def send_text_dm(self, bot: Any, chat_id: int, text: str, **kwargs: Any) -> Any:
        self.text_calls.append((chat_id, text))
        return SimpleNamespace(ok=True)


@pytest.fixture
def fake_redis() -> Any:
    return fakeredis.aioredis.FakeRedis()


@pytest.fixture
def sender() -> _StubSender:
    return _StubSender()


async def _seed_client(db_session: AsyncSession) -> Client:
    """Seed a User + Client; return the Client row."""
    from app.core.permissions import Role

    from app.modules.auth.models import User

    user = User(
        email=f"staff-reply-{uuid4().hex[:8]}@example.com",
        password_hash="$argon2id$notreal",  # noqa: S106
        role=Role.OWNER,
        full_name="Test Owner",
    )
    db_session.add(user)
    await db_session.flush()

    client = Client(
        first_name="Test",
        last_name="Client",
        phone=f"+7999{uuid4().int % 10_000_000:07d}",
        created_by_user_id=user.id,
    )
    db_session.add(client)
    await db_session.flush()
    return client


async def _seed_client_message(db_session: AsyncSession, client_id: Any) -> None:
    """Insert a role='client' message so reply-as-read can mark it."""
    thread_id = await messaging_service.repository.get_or_create_thread(db_session, client_id)
    await db_session.execute(
        text(
            "INSERT INTO messages (id, thread_id, role, body) "
            "VALUES (:id, :tid, 'client', 'client msg')"
        ),
        {"id": str(uuid4()), "tid": str(thread_id)},
    )
    await db_session.flush()


# ---------------------------------------------------------------------------
# Test 1: live anchor → record + publish new_message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_live_anchor_routes_and_persists(
    db_session: AsyncSession,
    fake_redis: Any,
    sender: _StubSender,
) -> None:
    """A reply to a forwarded message with a live anchor persists a staff message."""
    client = await _seed_client(db_session)
    anchor = {"thread_id": str(uuid4()), "client_id": str(client.id)}
    tg_msg_id = 500
    await fake_redis.set(f"cc:messaging:tg_msg:{tg_msg_id}", json.dumps(anchor), ex=604800)

    published: list[str] = []

    async def _fake_publish(channel: str, message: str) -> None:
        published.append(channel)

    fake_redis.publish = _fake_publish  # type: ignore[method-assign]

    ctx = _build_ctx(db_session, fake_redis, sender)
    update = _build_reply_update(replied_to_message_id=tg_msg_id, update_id=100)
    bot_ctx = _build_bot_ctx(sender)

    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.staff_telegram_chat_id = _STAFF_CHAT_ID
        await staff_reply_handler(update, bot_ctx, ctx)

    # Staff message must be persisted
    rows = await db_session.execute(
        text("SELECT id FROM messages WHERE role='staff' AND thread_id=:tid"),
        {"tid": str(anchor["thread_id"])},
    )
    assert rows.fetchone() is not None, "Staff message not persisted"

    # new_message published to the correct channel
    assert any(str(client.id) in ch for ch in published), (
        f"new_message not published to client channel; published={published}"
    )


# ---------------------------------------------------------------------------
# Test 2: anti-misroute — reply to older anchor routes to its client (BRDG-03)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anti_misroute_routes_to_anchored_client(
    db_session: AsyncSession,
    fake_redis: Any,
    sender: _StubSender,
) -> None:
    """Reply to older anchor A routes to A's client — NOT to the newer anchor B's client."""
    client_a = await _seed_client(db_session)
    client_b = await _seed_client(db_session)

    tg_id_a, tg_id_b = 1001, 1002
    anchor_a = {"thread_id": str(uuid4()), "client_id": str(client_a.id)}
    anchor_b = {"thread_id": str(uuid4()), "client_id": str(client_b.id)}
    await fake_redis.set(f"cc:messaging:tg_msg:{tg_id_a}", json.dumps(anchor_a), ex=604800)
    await fake_redis.set(f"cc:messaging:tg_msg:{tg_id_b}", json.dumps(anchor_b), ex=604800)

    published: list[str] = []

    async def _fake_publish(channel: str, message: str) -> None:
        published.append(channel)

    fake_redis.publish = _fake_publish  # type: ignore[method-assign]

    ctx = _build_ctx(db_session, fake_redis, sender)
    # Reply to anchor A (the older one)
    update = _build_reply_update(replied_to_message_id=tg_id_a, update_id=200)
    bot_ctx = _build_bot_ctx(sender)

    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.staff_telegram_chat_id = _STAFF_CHAT_ID
        await staff_reply_handler(update, bot_ctx, ctx)

    # Staff message in anchor_a's thread
    rows_a = await db_session.execute(
        text("SELECT id FROM messages WHERE role='staff' AND thread_id=:tid"),
        {"tid": str(anchor_a["thread_id"])},
    )
    assert rows_a.fetchone() is not None, "Staff message not in anchor A's thread"

    # No staff message in anchor_b's thread
    rows_b = await db_session.execute(
        text("SELECT id FROM messages WHERE role='staff' AND thread_id=:tid"),
        {"tid": str(anchor_b["thread_id"])},
    )
    assert rows_b.fetchone() is None, "Staff message leaked to anchor B's thread (misroute!)"

    # publish channel must be client_a, not client_b
    assert any(str(client_a.id) in ch for ch in published), "Not published to client_a"
    assert not any(str(client_b.id) in ch for ch in published), "Leaked publish to client_b"


# ---------------------------------------------------------------------------
# Test 3: stale/None anchor → DM hint + no persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stale_anchor_sends_hint_and_no_record(
    db_session: AsyncSession,
    fake_redis: Any,
    sender: _StubSender,
) -> None:
    """When redis.get returns None (stale/expired), send the hint DM and drop the message."""
    ctx = _build_ctx(db_session, fake_redis, sender)
    update = _build_reply_update(
        replied_to_message_id=9999,  # no anchor in redis
        update_id=300,
        reply_text="orphan reply",
    )
    bot_ctx = _build_bot_ctx(sender)

    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.staff_telegram_chat_id = _STAFF_CHAT_ID
        await staff_reply_handler(update, bot_ctx, ctx)

    # A DM hint must have been sent to the staff chat
    assert len(sender.text_calls) == 1, f"Expected 1 DM hint, got {sender.text_calls}"
    _, hint_text = sender.text_calls[0]
    assert "тред" in hint_text.lower() or "определить" in hint_text.lower(), (
        f"Hint text does not mention thread lookup failure: {hint_text!r}"
    )

    # No staff messages persisted anywhere
    rows = await db_session.execute(text("SELECT id FROM messages WHERE role='staff'"))
    assert rows.fetchone() is None, "Staff message persisted despite stale anchor"


# ---------------------------------------------------------------------------
# Test 4: plain (non-Reply) message → "use Reply" hint + no persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plain_message_sends_use_reply_hint(
    db_session: AsyncSession,
    fake_redis: Any,
    sender: _StubSender,
) -> None:
    """A plain (non-Reply) message in the staff chat returns the 'use Reply' hint."""
    ctx = _build_ctx(db_session, fake_redis, sender)
    update = _build_plain_update(update_id=400, text="Plain staff message")
    bot_ctx = _build_bot_ctx(sender)

    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.staff_telegram_chat_id = _STAFF_CHAT_ID
        await staff_reply_handler(update, bot_ctx, ctx)

    # A DM hint must have been sent
    assert len(sender.text_calls) == 1, f"Expected 1 hint, got {sender.text_calls}"
    _, hint_text = sender.text_calls[0]
    # hint should reference "Reply" usage
    assert "reply" in hint_text.lower() or "ответ" in hint_text.lower(), (
        f"Hint text does not reference Reply: {hint_text!r}"
    )

    # No staff messages persisted
    rows = await db_session.execute(text("SELECT id FROM messages WHERE role='staff'"))
    assert rows.fetchone() is None


# ---------------------------------------------------------------------------
# Test 5: echo guard — is_bot=True → no-op
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_echo_guard_bot_message_ignored(
    db_session: AsyncSession,
    fake_redis: Any,
    sender: _StubSender,
) -> None:
    """Bot's own outbound messages (is_bot=True) are silently dropped."""
    # Pre-seed an anchor so the handler WOULD route if it reached that logic
    client = await _seed_client(db_session)
    tg_msg_id = 600
    anchor = {"thread_id": str(uuid4()), "client_id": str(client.id)}
    await fake_redis.set(f"cc:messaging:tg_msg:{tg_msg_id}", json.dumps(anchor), ex=604800)

    ctx = _build_ctx(db_session, fake_redis, sender)
    update = _build_reply_update(
        replied_to_message_id=tg_msg_id,
        update_id=500,
        is_bot=True,  # bot echo
    )
    bot_ctx = _build_bot_ctx(sender)

    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.staff_telegram_chat_id = _STAFF_CHAT_ID
        await staff_reply_handler(update, bot_ctx, ctx)

    # No DM sent, no persistence
    assert sender.text_calls == [], "Bot echo should not trigger any DM"
    rows = await db_session.execute(text("SELECT id FROM messages WHERE role='staff'"))
    assert rows.fetchone() is None, "Bot echo should not persist anything"


# ---------------------------------------------------------------------------
# Test 6: replay guard — same update_id twice → exactly one staff row
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_replay_guard_dedup_update_id(
    db_session: AsyncSession,
    fake_redis: Any,
    sender: _StubSender,
) -> None:
    """Replaying the same update_id produces exactly one staff message row."""
    client = await _seed_client(db_session)
    tg_msg_id = 700
    anchor = {"thread_id": str(uuid4()), "client_id": str(client.id)}
    await fake_redis.set(f"cc:messaging:tg_msg:{tg_msg_id}", json.dumps(anchor), ex=604800)

    # Patch publish to avoid actual Redis channel ops
    published: list[str] = []

    async def _fake_publish(channel: str, message: str) -> None:
        published.append(channel)

    fake_redis.publish = _fake_publish  # type: ignore[method-assign]

    ctx = _build_ctx(db_session, fake_redis, sender)
    update = _build_reply_update(replied_to_message_id=tg_msg_id, update_id=600)
    bot_ctx = _build_bot_ctx(sender)

    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.staff_telegram_chat_id = _STAFF_CHAT_ID
        # First invocation — should persist
        await staff_reply_handler(update, bot_ctx, ctx)
        # Second invocation with same update_id — should be silently dropped
        await staff_reply_handler(update, bot_ctx, ctx)

    rows = await db_session.execute(
        text("SELECT id FROM messages WHERE role='staff' AND thread_id=:tid"),
        {"tid": str(anchor["thread_id"])},
    )
    fetched = rows.fetchall()
    assert len(fetched) == 1, f"Expected exactly 1 staff row, got {len(fetched)}"


# ---------------------------------------------------------------------------
# Test 7: reply-as-read — prior client message → publish_read_receipt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reply_as_read_publishes_read_receipt(
    db_session: AsyncSession,
    fake_redis: Any,
    sender: _StubSender,
) -> None:
    """When prior unread client messages exist, publish_read_receipt is called after commit."""
    client = await _seed_client(db_session)

    # Ensure a thread exists and seed a client message into it (so reply-as-read triggers)
    await _seed_client_message(db_session, client.id)

    tg_msg_id = 800
    # Use the actual thread_id that was created
    thread_id = await messaging_service.repository.get_or_create_thread(db_session, client.id)
    anchor = {"thread_id": str(thread_id), "client_id": str(client.id)}
    await fake_redis.set(f"cc:messaging:tg_msg:{tg_msg_id}", json.dumps(anchor), ex=604800)

    published_channels: list[str] = []

    async def _fake_publish(channel: str, message: str) -> None:
        published_channels.append(channel)

    fake_redis.publish = _fake_publish  # type: ignore[method-assign]

    ctx = _build_ctx(db_session, fake_redis, sender)
    update = _build_reply_update(replied_to_message_id=tg_msg_id, update_id=700)
    bot_ctx = _build_bot_ctx(sender)

    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.staff_telegram_chat_id = _STAFF_CHAT_ID
        await staff_reply_handler(update, bot_ctx, ctx)

    # Should have published: at least new_message + read_receipt (= 2 channel publishes)
    client_channel = f"cc:messaging:client:{client.id}"
    count = sum(1 for ch in published_channels if ch == client_channel)
    assert count >= 2, (
        f"Expected ≥2 publishes (new_message + read_receipt) to {client_channel}, "
        f"got {count}; all published: {published_channels}"
    )
