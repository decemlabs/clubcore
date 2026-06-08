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

Task 3 tests (router enqueue):
  - POST /messages with staff_telegram_chat_id set enqueues exactly one forward_to_staff job
  - POST /messages with staff_telegram_chat_id=None enqueues no forward_to_staff job
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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

    from app.integrations.telegram.sender import send_photo

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


def _stub_bot(*, ok: bool = True, message_id: int = 99) -> Any:
    """Telegram Bot stub — an opaque object.

    The actual send_text_dm / send_photo functions are patched at the module
    level by each Task 2 test, so the bot itself only needs to be a placeholder
    object passed through forward_to_staff's ctx.
    """
    _ = (ok, message_id)  # accepted for call-site symmetry; behaviour is patched

    class _BotStub:
        pass

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
    """Text-only forward writes cc:messaging:tg_msg:{id} mapping with TTL 604800.

    Mapping value carries {thread_id, client_id}.
    """
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


# ─────────────────────────────────────────────────────────────────────────────
# Task 3: messaging router post-commit forward_to_staff enqueue
#
# These tests drive POST /api/v1/client/messages through the real ASGI app
# (httpx ASGITransport — CLAUDE.md constraint) over a SAVEPOINT-wrapped session,
# with app.state.arq_pool replaced by a spy so we assert the enqueue contract
# without a live ARQ/Redis queue. They require Postgres + Redis and skip cleanly
# otherwise (db_session fixture idiom).
# ─────────────────────────────────────────────────────────────────────────────

_BRIDGE_BASE_PHONE = "+79168000"


def _bridge_phone(n: int) -> str:
    """Stable E.164 phone for bridge router tests (no collision with REST tests)."""
    return f"{_BRIDGE_BASE_PHONE}{n:04d}"


async def _seed_bridge_staff_client(db_session: AsyncSession, phone: str) -> Any:
    """Seed a RECEPTION user + Client and return the Client (flushed, not committed)."""
    from app.core.permissions import Role
    from app.core.security import hash_password
    from app.modules.auth.models import User
    from app.modules.clients.models import Client

    staff = User(
        email=f"bridge-staff-{phone[-6:]}@example.com",
        password_hash=await hash_password("bridge-staff-pw-secure-93"),
        role=Role.RECEPTION,
        full_name="Bridge Test Staff",
    )
    db_session.add(staff)
    await db_session.flush()

    client = Client(
        first_name="Иван",
        last_name="Петров",
        phone=phone,
        telegram_user_id=abs(hash(phone)) % (10**9),
        created_by_user_id=staff.id,
    )
    db_session.add(client)
    await db_session.flush()
    return client


async def _auth_bridge_client(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client: Any,
) -> str:
    """Run the client OTP flow and return the cc_client_access token value."""
    from app.core.config import get_settings
    from app.core.security import generate_otp_code
    from app.modules.auth.models import OtpCode

    req = await async_client.post(
        "/api/v1/client/otp/request",
        json={"phone": client.phone},
    )
    assert req.status_code == 202, f"OTP request failed: {req.text}"

    otp_row = await db_session.scalar(
        select(OtpCode).where(
            OtpCode.client_id == client.id,
            OtpCode.consumed_at.is_(None),
        )
    )
    assert otp_row is not None, "OtpCode row not found"

    settings = get_settings()
    raw_code, code_hash = generate_otp_code()
    otp_row.code_hash = code_hash
    otp_row.expires_at = datetime.now(tz=UTC) + timedelta(seconds=settings.otp_code_ttl_seconds)
    await db_session.commit()

    verify = await async_client.post(
        "/api/v1/client/otp/verify",
        json={"phone": client.phone, "code": raw_code},
    )
    assert verify.status_code == 200, f"OTP verify failed: {verify.text}"
    set_cookies = verify.headers.get_list("set-cookie")
    access_cookie = next(
        (c for c in set_cookies if c.startswith("cc_client_access=")),
        None,
    )
    assert access_cookie is not None, "cc_client_access cookie missing"
    return access_cookie.split("=", 1)[1].split(";", 1)[0]


@pytest_asyncio.fixture
async def bridge_http_client(
    app: FastAPI,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[AsyncClient]:
    """Cookie-persisting ASGITransport client wired to the SAVEPOINT session.

    Stubs the client OTP Telegram sender to a no-op and flushes Redis so
    idempotency/rate-limit keys don't bleed across tests (mirrors the REST
    suite's autouse fixtures, but scoped to the tests that request it).
    """
    from app.core.database import get_db
    from app.core.redis import get_redis
    from app.modules.client_auth import service as client_auth_service

    async def _noop_otp(chat_id: int, code: str) -> None:
        pass

    monkeypatch.setattr(client_auth_service, "_client_otp_sender", _noop_otp)

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = lambda: app.state.redis
    await app.state.redis.flushdb()

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as c:
            yield c
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def arq_spy(app: FastAPI) -> AsyncIterator[Any]:
    """Replace app.state.arq_pool with an AsyncMock spy for the duration of a test."""
    spy = AsyncMock()
    original = getattr(app.state, "arq_pool", None)
    app.state.arq_pool = spy
    try:
        yield spy
    finally:
        app.state.arq_pool = original


@pytest.mark.asyncio
async def test_post_message_enqueues_forward_to_staff_when_chat_id_set(
    bridge_http_client: AsyncClient,
    db_session: AsyncSession,
    arq_spy: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /messages with staff_telegram_chat_id set enqueues exactly one forward_to_staff job."""
    from app.modules.messaging import router as messaging_router

    monkeypatch.setattr(
        messaging_router,
        "get_settings",
        lambda: SimpleNamespace(staff_telegram_chat_id=55555),
    )

    client = await _seed_bridge_staff_client(db_session, _bridge_phone(1))
    await db_session.commit()

    await _auth_bridge_client(bridge_http_client, db_session, client)
    csrf_token = bridge_http_client.cookies.get("clubcore_client_csrf") or ""

    resp = await bridge_http_client.post(
        "/api/v1/client/messages",
        json={"body": "привет залу"},
        headers={
            "X-CSRF-Token": csrf_token,
            "Idempotency-Key": f"bridge-enqueue-{uuid.uuid4().hex[:8]}",
        },
    )
    assert resp.status_code == 200, resp.text

    forward_calls = [
        c for c in arq_spy.enqueue_job.await_args_list if c.args and c.args[0] == "forward_to_staff"
    ]
    assert len(forward_calls) == 1, f"expected one forward_to_staff enqueue, got {forward_calls!r}"
    kwargs = forward_calls[0].kwargs
    assert kwargs["client_id"] == str(client.id)
    assert kwargs["body"] == "привет залу"
    assert kwargs["client_name"] == "Иван Петров"
    assert kwargs["client_phone"] == client.phone
    assert "message_id" in kwargs
    assert "thread_id" in kwargs
    assert kwargs["attachment_id"] is None
    assert kwargs["object_key"] is None
    assert kwargs["_max_tries"] == 2
    assert kwargs["_expires"] == 20


@pytest.mark.asyncio
async def test_post_message_no_enqueue_when_chat_id_none(
    bridge_http_client: AsyncClient,
    db_session: AsyncSession,
    arq_spy: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /messages with staff_telegram_chat_id None enqueues no forward_to_staff job."""
    from app.modules.messaging import router as messaging_router

    monkeypatch.setattr(
        messaging_router,
        "get_settings",
        lambda: SimpleNamespace(staff_telegram_chat_id=None),
    )

    client = await _seed_bridge_staff_client(db_session, _bridge_phone(2))
    await db_session.commit()

    await _auth_bridge_client(bridge_http_client, db_session, client)
    csrf_token = bridge_http_client.cookies.get("clubcore_client_csrf") or ""

    resp = await bridge_http_client.post(
        "/api/v1/client/messages",
        json={"body": "тишина"},
        headers={
            "X-CSRF-Token": csrf_token,
            "Idempotency-Key": f"bridge-noenqueue-{uuid.uuid4().hex[:8]}",
        },
    )
    assert resp.status_code == 200, resp.text

    forward_calls = [
        c for c in arq_spy.enqueue_job.await_args_list if c.args and c.args[0] == "forward_to_staff"
    ]
    assert forward_calls == [], f"expected zero forward_to_staff enqueues, got {forward_calls!r}"
