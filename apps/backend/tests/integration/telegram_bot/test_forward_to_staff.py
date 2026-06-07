"""Tests for Phase 93 BRDG-01: forward_to_staff ARQ task + sender.send_photo + config.

Task 1 tests (config + send_photo):
  - staff_telegram_chat_id defaults to None
  - send_photo ok path
  - send_photo Forbidden → blocked
  - send_photo BadRequest("chat not found") → blocked
  - send_photo generic Exception → error

Task 2 tests (forward_to_staff ARQ task):
  - skipped when staff_telegram_chat_id is None
  - text-only forward writes Redis chat_forwarding_log with correct JSON + TTL 604800
  - photo attachment: streams storage bytes, calls send_photo, writes Redis
  - failed send (SendResult.ok=False) writes NO Redis key, returns "failed"
  - SendResult.message_id populated from bot return value

Task 3 tests (router enqueue — see test body for notes):
  - POST /messages with staff_telegram_chat_id set enqueues exactly one forward_to_staff job
  - POST /messages with staff_telegram_chat_id=None enqueues no forward_to_staff job
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Task 1: config + send_photo
# ─────────────────────────────────────────────────────────────────────────────


def test_staff_telegram_chat_id_default_none() -> None:
    """get_settings().staff_telegram_chat_id is None by default."""
    from app.core.config import get_settings

    settings = get_settings()
    assert settings.staff_telegram_chat_id is None


@pytest.mark.asyncio
async def test_send_photo_ok() -> None:
    """send_photo returns SendResult(ok=True, message_id=<int>) on success."""
    from app.integrations.telegram.sender import SendResult, send_photo

    sent_message = SimpleNamespace(message_id=42)

    bot = SimpleNamespace(
        send_photo=AsyncMock(return_value=sent_message),
    )
    result = await send_photo(bot, chat_id=100, photo=b"fakebytes", caption="test")  # type: ignore[arg-type]
    assert result == SendResult(ok=True, message_id=42)
    bot.send_photo.assert_awaited_once_with(chat_id=100, photo=b"fakebytes", caption="test")


@pytest.mark.asyncio
async def test_send_photo_forbidden() -> None:
    """send_photo returns SendResult(ok=False, blocked=True) on Forbidden."""
    from telegram.error import Forbidden

    from app.integrations.telegram.sender import SendResult, send_photo

    bot = SimpleNamespace(
        send_photo=AsyncMock(side_effect=Forbidden("blocked")),
    )
    result = await send_photo(bot, chat_id=100, photo=b"data")  # type: ignore[arg-type]
    assert result == SendResult(ok=False, blocked=True)


@pytest.mark.asyncio
async def test_send_photo_bad_request_chat_not_found() -> None:
    """send_photo returns blocked=True on BadRequest 'chat not found'."""
    from telegram.error import BadRequest

    from app.integrations.telegram.sender import SendResult, send_photo

    bot = SimpleNamespace(
        send_photo=AsyncMock(side_effect=BadRequest("Chat not found")),
    )
    result = await send_photo(bot, chat_id=100, photo=b"data")  # type: ignore[arg-type]
    assert result == SendResult(ok=False, blocked=True)


@pytest.mark.asyncio
async def test_send_photo_bad_request_other() -> None:
    """send_photo returns error (not blocked) on other BadRequest."""
    from telegram.error import BadRequest

    from app.integrations.telegram.sender import SendResult, send_photo

    bot = SimpleNamespace(
        send_photo=AsyncMock(side_effect=BadRequest("Something else")),
    )
    result = await send_photo(bot, chat_id=100, photo=b"data")  # type: ignore[arg-type]
    assert result.ok is False
    assert result.blocked is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_send_photo_generic_exception() -> None:
    """send_photo returns SendResult(ok=False, error=...) on generic Exception."""
    from app.integrations.telegram.sender import SendResult, send_photo

    bot = SimpleNamespace(
        send_photo=AsyncMock(side_effect=RuntimeError("network failure")),
    )
    result = await send_photo(bot, chat_id=100, photo=b"data")  # type: ignore[arg-type]
    assert result == SendResult(ok=False, blocked=False, error="network failure")


# ─────────────────────────────────────────────────────────────────────────────
# Task 2: forward_to_staff ARQ task
# ─────────────────────────────────────────────────────────────────────────────


def _make_ctx(
    redis: Any,
    *,
    storage: Any = None,
    bot: Any = None,
) -> dict[str, Any]:
    """Build a minimal ARQ ctx dict for forward_to_staff tests."""
    return {
        "redis": redis,
        "storage": storage or _stub_storage([]),
        "bot": bot or _stub_bot(ok=True, message_id=99),
        "sessionmaker": None,  # not used in forward_to_staff (no DB write)
    }


def _stub_storage(chunks: list[bytes]) -> Any:
    """Storage stub: open_stream yields the given chunks."""

    async def _open_stream(key: str) -> AsyncIterator[bytes]:
        for chunk in chunks:
            yield chunk

    storage = MagicMock()
    storage.open_stream = _open_stream
    return storage


def _stub_bot(*, ok: bool, message_id: int = 99) -> Any:
    """Telegram Bot stub returning the given result."""
    from app.integrations.telegram.sender import SendResult

    class _BotStub:
        pass

    from unittest.mock import AsyncMock as AM

    async def _send_text_dm(bot: Any, chat_id: int, text: str, **_kw: Any) -> SendResult:
        if ok:
            return SendResult(ok=True, message_id=message_id)
        return SendResult(ok=False, error="fail")

    async def _send_photo(bot: Any, chat_id: int, photo: bytes, caption: str | None = None) -> SendResult:
        if ok:
            return SendResult(ok=True, message_id=message_id)
        return SendResult(ok=False, error="fail")

    return _BotStub()


@pytest.mark.asyncio
async def test_forward_to_staff_skipped_when_no_chat_id() -> None:
    """Returns 'skipped' when staff_telegram_chat_id is None."""
    from app.workers.tasks.forward_to_staff import forward_to_staff

    redis = fakeredis.aioredis.FakeRedis()
    ctx = _make_ctx(redis)

    with patch("app.workers.tasks.forward_to_staff.get_settings") as mock_settings:
        mock_settings.return_value = SimpleNamespace(staff_telegram_chat_id=None)
        result = await forward_to_staff(
            ctx,
            client_id="client-uuid",
            message_id="msg-uuid",
            thread_id="thread-uuid",
            body="Hello",
            client_name="Иван Иванов",
            client_phone="+79991234567",
        )
    assert result == "skipped"
    # No Redis keys written
    keys = await redis.keys("cc:messaging:tg_msg:*")
    assert keys == []


@pytest.mark.asyncio
async def test_forward_to_staff_text_writes_redis_mapping() -> None:
    """Text-only forward writes cc:messaging:tg_msg:{id} → {thread_id, client_id} with TTL 604800."""
    from app.integrations.telegram import sender as sender_mod
    from app.integrations.telegram.sender import SendResult
    from app.workers.tasks.forward_to_staff import forward_to_staff

    redis = fakeredis.aioredis.FakeRedis()

    sent_message_id = 777
    send_text_dm_calls: list[dict[str, Any]] = []

    async def fake_send_text_dm(bot: Any, chat_id: int, text: str, **kw: Any) -> SendResult:
        send_text_dm_calls.append({"chat_id": chat_id, "text": text})
        return SendResult(ok=True, message_id=sent_message_id)

    ctx = _make_ctx(redis)

    with (
        patch("app.workers.tasks.forward_to_staff.get_settings") as mock_settings,
        patch.object(sender_mod, "send_text_dm", fake_send_text_dm),
    ):
        mock_settings.return_value = SimpleNamespace(staff_telegram_chat_id=55555)
        result = await forward_to_staff(
            ctx,
            client_id="client-uuid",
            message_id="msg-uuid",
            thread_id="thread-uuid",
            body="Test message",
            client_name="Иван Иванов",
            client_phone="+79991234567",
        )

    assert result == "sent"
    assert len(send_text_dm_calls) == 1
    assert send_text_dm_calls[0]["chat_id"] == 55555

    # Redis mapping written
    key = f"cc:messaging:tg_msg:{sent_message_id}"
    raw = await redis.get(key)
    assert raw is not None
    mapping = json.loads(raw)
    assert mapping["thread_id"] == "thread-uuid"
    assert mapping["client_id"] == "client-uuid"

    # TTL must be approximately 604800 seconds
    ttl = await redis.ttl(key)
    assert 604700 <= ttl <= 604800


@pytest.mark.asyncio
async def test_forward_to_staff_photo_streams_and_sends() -> None:
    """Photo attachment: streams storage bytes + calls send_photo + writes Redis."""
    from app.integrations.telegram import sender as sender_mod
    from app.integrations.telegram.sender import SendResult
    from app.workers.tasks.forward_to_staff import forward_to_staff

    redis = fakeredis.aioredis.FakeRedis()

    photo_chunks = [b"chunk1", b"chunk2"]
    storage = _stub_storage(photo_chunks)

    sent_message_id = 888
    send_photo_calls: list[dict[str, Any]] = []

    async def fake_send_photo(
        bot: Any, chat_id: int, photo: bytes, caption: str | None = None
    ) -> SendResult:
        send_photo_calls.append({"chat_id": chat_id, "photo": photo, "caption": caption})
        return SendResult(ok=True, message_id=sent_message_id)

    ctx = _make_ctx(redis, storage=storage)

    with (
        patch("app.workers.tasks.forward_to_staff.get_settings") as mock_settings,
        patch.object(sender_mod, "send_photo", fake_send_photo),
    ):
        mock_settings.return_value = SimpleNamespace(staff_telegram_chat_id=55555)
        result = await forward_to_staff(
            ctx,
            client_id="client-uuid",
            message_id="msg-uuid",
            thread_id="thread-uuid",
            body="Look at this",
            client_name="Мария Петрова",
            client_phone="+79997654321",
            attachment_id="att-uuid",
            object_key="photos/att-uuid.jpg",
        )

    assert result == "sent"
    assert len(send_photo_calls) == 1
    call = send_photo_calls[0]
    assert call["chat_id"] == 55555
    # Chunks concatenated
    assert call["photo"] == b"chunk1chunk2"
    assert call["caption"] is not None

    # Redis mapping written
    key = f"cc:messaging:tg_msg:{sent_message_id}"
    raw = await redis.get(key)
    assert raw is not None
    mapping = json.loads(raw)
    assert mapping["thread_id"] == "thread-uuid"


@pytest.mark.asyncio
async def test_forward_to_staff_failed_send_no_redis() -> None:
    """Failed send (SendResult.ok=False) writes no Redis key and returns 'failed'."""
    from app.integrations.telegram import sender as sender_mod
    from app.integrations.telegram.sender import SendResult
    from app.workers.tasks.forward_to_staff import forward_to_staff

    redis = fakeredis.aioredis.FakeRedis()

    async def fake_send_text_dm(bot: Any, chat_id: int, text: str, **kw: Any) -> SendResult:
        return SendResult(ok=False, error="network down")

    ctx = _make_ctx(redis)

    with (
        patch("app.workers.tasks.forward_to_staff.get_settings") as mock_settings,
        patch.object(sender_mod, "send_text_dm", fake_send_text_dm),
    ):
        mock_settings.return_value = SimpleNamespace(staff_telegram_chat_id=55555)
        result = await forward_to_staff(
            ctx,
            client_id="client-uuid",
            message_id="msg-uuid",
            thread_id="thread-uuid",
            body="Hello",
            client_name="Тест Тестов",
            client_phone="+79000000000",
        )

    assert result == "failed"
    keys = await redis.keys("cc:messaging:tg_msg:*")
    assert keys == []
