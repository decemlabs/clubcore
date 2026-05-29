"""Unit tests for app.core.idempotency (Phase 32 PAY-09 / D-32-18..D-32-20).

Hardened in Phase 66 IDM-02/05/06:
- TTL: 86400 (IDM-02)
- Pattern: {16,128} (IDM-02)
- User-scoped key: {user_id}:{method}:{path}:{header} (IDM-05 / D-66-USER-SCOPE)

Covers Idempotency-Key header validation, regex pattern coverage, body hash
helper, and user-scoped key return format. ``verify_idempotency`` is invoked
with a synthetic Request — no real ASGI / FastAPI runtime needed.
"""

from __future__ import annotations

import re
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app.core.exceptions import ValidationAppError
from app.core.idempotency import (
    IDEMPOTENCY_KEY_PATTERN,
    body_sha256,
    verify_idempotency,
)

_TEST_USER_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

# Minimum valid key length is now 16 (IDM-02). Tests use keys >= 16 chars.
_VALID_KEY = "valid_key-123abc"  # 16 chars


def _make_request(
    idempotency_key: str | None,
    *,
    method: str = "POST",
    path: str = "/api/v1/test",
) -> Any:
    """Return a stub Request with header + method + url.path exercised.

    ``verify_idempotency`` returns ``f"{user_id}:{method}:{path}:{key}"``
    (user-scoped + route-bound per D-66-USER-SCOPE / CR-01 / D-33-16).
    """
    headers: dict[str, str] = {}
    if idempotency_key is not None:
        headers["idempotency-key"] = idempotency_key

    class _Headers:
        def get(self, name: str, default: str | None = None) -> str | None:
            return headers.get(name.lower(), default)

    class _URL:
        def __init__(self, path_value: str) -> None:
            self.path = path_value

    class _Request:
        def __init__(self) -> None:
            self.headers = _Headers()
            self.method = method
            self.url = _URL(path)

    return _Request()


def _make_user(user_id: UUID = _TEST_USER_ID) -> Any:
    """Stub CurrentUser with .id attribute."""

    class _User:
        def __init__(self, uid: UUID) -> None:
            self.id = uid

    return _User(user_id)


@pytest.mark.asyncio
async def test_missing_header_raises_required() -> None:
    request = _make_request(None)
    redis = AsyncMock()
    user = _make_user()
    with pytest.raises(ValidationAppError) as exc_info:
        await verify_idempotency(request, redis, user)
    assert exc_info.value.message == "idempotency_key_required"


@pytest.mark.asyncio
async def test_empty_header_raises_required() -> None:
    """Empty string header is treated as missing (defensive against header tooling)."""
    request = _make_request("")
    redis = AsyncMock()
    user = _make_user()
    with pytest.raises(ValidationAppError) as exc_info:
        await verify_idempotency(request, redis, user)
    assert exc_info.value.message == "idempotency_key_required"


@pytest.mark.asyncio
async def test_invalid_format_with_space() -> None:
    request = _make_request("with space and extra")
    redis = AsyncMock()
    user = _make_user()
    with pytest.raises(ValidationAppError) as exc_info:
        await verify_idempotency(request, redis, user)
    assert exc_info.value.message == "idempotency_key_invalid_format"


@pytest.mark.asyncio
async def test_invalid_format_with_bang() -> None:
    request = _make_request("bad!key-toolong123")
    redis = AsyncMock()
    user = _make_user()
    with pytest.raises(ValidationAppError) as exc_info:
        await verify_idempotency(request, redis, user)
    assert exc_info.value.message == "idempotency_key_invalid_format"


@pytest.mark.asyncio
async def test_valid_format_returns_user_scoped_route_bound_key() -> None:
    """Returned key is ``f"{user_id}:{method}:{path}:{header}"`` (user-scoped + route-bound)."""
    request = _make_request(_VALID_KEY, method="POST", path="/api/v1/test")
    redis = AsyncMock()
    user = _make_user()
    key = await verify_idempotency(request, redis, user)
    assert key == f"{_TEST_USER_ID}:POST:/api/v1/test:{_VALID_KEY}"


@pytest.mark.asyncio
async def test_route_binding_distinguishes_endpoints() -> None:
    """Same header value on different routes returns distinct namespaced keys."""
    redis = AsyncMock()
    user = _make_user()
    sale_key_header = "a" * 16
    sale_req = _make_request(sale_key_header, method="POST", path="/api/v1/pt-packages")
    refund_req = _make_request(
        sale_key_header,
        method="POST",
        path="/api/v1/pt-packages/00000000-0000-0000-0000-000000000001/refund",
    )
    sale_key = await verify_idempotency(sale_req, redis, user)
    refund_key = await verify_idempotency(refund_req, redis, user)
    assert sale_key != refund_key
    assert sale_key.endswith(f":{sale_key_header}")
    assert refund_key.endswith(f":{sale_key_header}")


@pytest.mark.asyncio
async def test_too_long_is_invalid() -> None:
    request = _make_request("a" * 129)
    redis = AsyncMock()
    user = _make_user()
    with pytest.raises(ValidationAppError) as exc_info:
        await verify_idempotency(request, redis, user)
    assert exc_info.value.message == "idempotency_key_invalid_format"


@pytest.mark.asyncio
async def test_too_short_is_invalid() -> None:
    """Keys shorter than 16 characters are now invalid (IDM-02 {16,128} bound)."""
    request = _make_request("a" * 15)
    redis = AsyncMock()
    user = _make_user()
    with pytest.raises(ValidationAppError) as exc_info:
        await verify_idempotency(request, redis, user)
    assert exc_info.value.message == "idempotency_key_invalid_format"


@pytest.mark.asyncio
async def test_max_length_128_is_valid() -> None:
    request = _make_request("a" * 128, method="POST", path="/api/v1/test")
    redis = AsyncMock()
    user = _make_user()
    key = await verify_idempotency(request, redis, user)
    # User-scoped + route-bound: f"{user_id}:{method}:{path}:{header}" — header preserved verbatim.
    assert key == f"{_TEST_USER_ID}:POST:/api/v1/test:{'a' * 128}"


def test_pattern_matches_allowed_chars() -> None:
    pattern = re.compile(IDEMPOTENCY_KEY_PATTERN)
    # Must be >= 16 chars (IDM-02); use a 16-char value
    assert pattern.match("ABC_123:def-4567") is not None  # exactly 16 chars


def test_pattern_rejects_space() -> None:
    pattern = re.compile(IDEMPOTENCY_KEY_PATTERN)
    assert pattern.match("with space in it") is None


def test_body_sha256_is_64_hex() -> None:
    payload = b'{"reason":"refund"}'
    digest = body_sha256(payload)
    assert re.match(r"^[0-9a-f]{64}$", digest) is not None
