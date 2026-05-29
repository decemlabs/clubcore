"""Unit tests for the hardened idempotency orchestrator (Phase 66 IDM-02/05/06).

Covers:
- TTL constant equals 86400
- Pattern bounds {16,128}
- User-scoped key (verify_idempotency returns {user_id}:{method}:{path}:{key})
- Orchestrator success path: stores envelope, replays byte-identically
- Orchestrator AppError path (IDM-06): stores error envelope, re-raises, replays on retry
- Orchestrator unknown-exception path (IDM-06): deletes placeholder, re-raises
- Body-hash on error replay: different body → idempotency_key_reuse
"""

from __future__ import annotations

import base64
import json
import re
from typing import Any
from uuid import UUID

import pytest

from app.core.exceptions import ConflictError, ValidationAppError
from app.core.idempotency import (
    IDEMPOTENCY_KEY_PATTERN,
    IDEMPOTENCY_TTL_SECONDS,
    _redis_key,
    idempotent_execute,
    verify_idempotency,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(
    idempotency_key: str | None,
    *,
    method: str = "POST",
    path: str = "/x",
) -> Any:
    """Stub Request (no ASGI needed)."""
    headers: dict[str, str] = {}
    if idempotency_key is not None:
        headers["idempotency-key"] = idempotency_key

    class _Headers:
        def get(self, name: str, default: str | None = None) -> str | None:
            return headers.get(name.lower(), default)

    class _URL:
        def __init__(self, p: str) -> None:
            self.path = p

    class _Request:
        def __init__(self) -> None:
            self.headers = _Headers()
            self.method = method
            self.url = _URL(path)

    return _Request()


def _make_user(user_id: UUID) -> Any:
    """Stub CurrentUser with .id attribute."""

    class _User:
        def __init__(self, uid: UUID) -> None:
            self.id = uid

    return _User(user_id)


def _make_fake_redis() -> Any:
    """Return a simple in-memory Redis-like store for unit tests."""
    store: dict[str, Any] = {}

    class _FakeRedis:
        async def get(self, key: str) -> Any:
            return store.get(key)

        async def set(
            self,
            key: str,
            value: Any,
            *,
            nx: bool = False,
            ex: int | None = None,
        ) -> bool | None:
            if nx:
                if key in store:
                    return None  # Redis returns nil when NX fails
                store[key] = value
                return True
            store[key] = value
            return True

        async def delete(self, key: str) -> int:
            existed = key in store
            store.pop(key, None)
            return 1 if existed else 0

        def _store(self) -> dict[str, Any]:  # test inspection
            return store

    return _FakeRedis()


# ---------------------------------------------------------------------------
# IDM-02: TTL and pattern constants
# ---------------------------------------------------------------------------


def test_ttl_is_86400() -> None:
    assert IDEMPOTENCY_TTL_SECONDS == 86400


def test_pattern_bounds_16_128() -> None:
    assert IDEMPOTENCY_KEY_PATTERN == r"^[A-Za-z0-9_:-]{16,128}$"


def test_15_char_key_fails() -> None:
    re_obj = re.compile(IDEMPOTENCY_KEY_PATTERN)
    assert re_obj.match("a" * 15) is None


def test_16_char_key_matches() -> None:
    re_obj = re.compile(IDEMPOTENCY_KEY_PATTERN)
    assert re_obj.match("a" * 16) is not None


def test_128_char_key_matches() -> None:
    re_obj = re.compile(IDEMPOTENCY_KEY_PATTERN)
    assert re_obj.match("a" * 128) is not None


def test_129_char_key_fails() -> None:
    re_obj = re.compile(IDEMPOTENCY_KEY_PATTERN)
    assert re_obj.match("a" * 129) is None


# ---------------------------------------------------------------------------
# IDM-05: User-scoped key (D-66-USER-SCOPE)
# ---------------------------------------------------------------------------

UUID_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
UUID_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

# Minimum valid key length is 16 (IDM-02)
_VALID_HEADER_KEY = "a" * 16


@pytest.mark.asyncio
async def test_verify_idempotency_user_scoped_key() -> None:
    """Returns {user_id}:{method}:{path}:{header} with user_id FIRST (D-66-USER-SCOPE)."""
    from unittest.mock import AsyncMock

    request = _make_request(_VALID_HEADER_KEY, method="POST", path="/x")
    redis = AsyncMock()
    user = _make_user(UUID_A)

    result = await verify_idempotency(request, redis, user)
    assert result == f"{UUID_A}:POST:/x:{_VALID_HEADER_KEY}"


@pytest.mark.asyncio
async def test_verify_idempotency_different_users_yield_different_keys() -> None:
    """Same Idempotency-Key header for two different users → different Redis entries."""
    from unittest.mock import AsyncMock

    redis = AsyncMock()
    request = _make_request(_VALID_HEADER_KEY, method="POST", path="/x")
    user_a = _make_user(UUID_A)
    user_b = _make_user(UUID_B)

    key_a = await verify_idempotency(request, redis, user_a)
    key_b = await verify_idempotency(request, redis, user_b)

    assert key_a != key_b
    assert key_a.startswith(str(UUID_A) + ":")
    assert key_b.startswith(str(UUID_B) + ":")


# ---------------------------------------------------------------------------
# Orchestrator: success path
# ---------------------------------------------------------------------------

# Use a 16-char minimum key for orchestrator tests
_GOOD_KEY = "a" * 16


@pytest.mark.asyncio
async def test_orchestrator_success_stores_and_returns() -> None:
    """First call stores the envelope and returns correct body+status."""
    redis = _make_fake_redis()
    body_bytes = b'{"data":"result"}'
    status_code = 201

    async def runner() -> tuple[int, bytes]:
        return status_code, body_bytes

    response = await idempotent_execute(redis, _GOOD_KEY, body_bytes, runner=runner)
    assert response.status_code == 201
    assert response.body == body_bytes
    assert response.media_type == "application/json"


@pytest.mark.asyncio
async def test_orchestrator_replay_does_not_call_runner_again() -> None:
    """Second call with same key+body replays byte-identically without invoking runner."""
    redis = _make_fake_redis()
    body_bytes = b'{"data":"result"}'
    status_code = 201
    call_count = 0

    async def runner() -> tuple[int, bytes]:
        nonlocal call_count
        call_count += 1
        return status_code, body_bytes

    first = await idempotent_execute(redis, _GOOD_KEY, body_bytes, runner=runner)
    second = await idempotent_execute(redis, _GOOD_KEY, body_bytes, runner=runner)

    assert call_count == 1  # runner called exactly once
    assert second.status_code == first.status_code
    assert second.body == first.body


# ---------------------------------------------------------------------------
# IDM-06: AppError path — store error envelope + re-raise
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_orchestrator_app_error_stores_envelope_and_reraises() -> None:
    """Runner raises ConflictError → orchestrator stores error envelope, then re-raises."""
    redis = _make_fake_redis()
    body_bytes = b'{"x":1}'
    exc = ConflictError("resource_conflict")

    async def runner() -> tuple[int, bytes]:
        raise exc

    with pytest.raises(ConflictError):
        await idempotent_execute(redis, _GOOD_KEY, body_bytes, runner=runner)

    # The key must now hold a stored envelope (not the placeholder)
    raw = await redis.get(_redis_key(_GOOD_KEY))
    assert raw is not None
    assert raw != "__in_flight__"
    stored = json.loads(raw)
    assert stored["status_code"] == ConflictError.status_code
    body = json.loads(base64.b64decode(stored["body_b64"]))
    assert body["code"] == ConflictError.code


@pytest.mark.asyncio
async def test_orchestrator_app_error_replay_returns_stored_error() -> None:
    """Retry with same key+body after AppError replays the stored error (not in_flight)."""
    redis = _make_fake_redis()
    body_bytes = b'{"x":1}'

    async def runner() -> tuple[int, bytes]:
        raise ConflictError("resource_conflict")

    # First call: raises
    with pytest.raises(ConflictError):
        await idempotent_execute(redis, _GOOD_KEY, body_bytes, runner=runner)

    # Second call: same key + same body → replays the stored error envelope
    replay = await idempotent_execute(redis, _GOOD_KEY, body_bytes, runner=runner)
    assert replay.status_code == ConflictError.status_code
    payload = json.loads(replay.body)
    assert payload["code"] == ConflictError.code


@pytest.mark.asyncio
async def test_orchestrator_app_error_different_body_raises_key_reuse() -> None:
    """After AppError is stored, retry with same key but DIFFERENT body raises key_reuse."""
    redis = _make_fake_redis()
    body_bytes = b'{"x":1}'
    different_body = b'{"x":2}'

    async def runner() -> tuple[int, bytes]:
        raise ConflictError("resource_conflict")

    with pytest.raises(ConflictError):
        await idempotent_execute(redis, _GOOD_KEY, body_bytes, runner=runner)

    with pytest.raises(ValidationAppError) as exc_info:
        await idempotent_execute(redis, _GOOD_KEY, different_body, runner=runner)
    assert exc_info.value.message == "idempotency_key_reuse"


# ---------------------------------------------------------------------------
# IDM-06: Unknown exception path — delete placeholder + re-raise
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_orchestrator_unknown_exception_deletes_placeholder_and_reraises() -> None:
    """Runner raises RuntimeError → orchestrator deletes the placeholder and re-raises."""
    redis = _make_fake_redis()
    body_bytes = b'{"y":1}'

    async def runner() -> tuple[int, bytes]:
        raise RuntimeError("network failure")

    with pytest.raises(RuntimeError):
        await idempotent_execute(redis, _GOOD_KEY, body_bytes, runner=runner)

    # Placeholder must be gone so the next retry can claim it fresh
    raw = await redis.get(_redis_key(_GOOD_KEY))
    assert raw is None


@pytest.mark.asyncio
async def test_orchestrator_unknown_exception_next_retry_can_claim() -> None:
    """After unknown exception deletes placeholder, next retry wins the SET NX claim."""
    redis = _make_fake_redis()
    body_bytes = b'{"y":1}'
    calls: list[int] = []

    async def runner() -> tuple[int, bytes]:
        calls.append(len(calls) + 1)
        if len(calls) == 1:
            raise RuntimeError("transient failure")
        return 201, body_bytes

    with pytest.raises(RuntimeError):
        await idempotent_execute(redis, _GOOD_KEY, body_bytes, runner=runner)

    # Second call: fresh claim, runner runs again successfully
    response = await idempotent_execute(redis, _GOOD_KEY, body_bytes, runner=runner)
    assert len(calls) == 2
    assert response.status_code == 201
