"""Unit tests for app.core.idempotency (Phase 32 PAY-09 / D-32-18..D-32-20).

Covers Idempotency-Key header validation, regex pattern coverage, and body
hash helper. Verify_idempotency is invoked with a synthetic Request — no
real ASGI / FastAPI runtime needed.
"""

from __future__ import annotations

import re
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import ValidationAppError
from app.core.idempotency import (
    IDEMPOTENCY_KEY_PATTERN,
    body_sha256,
    verify_idempotency,
)


def _make_request(idempotency_key: str | None) -> Any:
    """Return a stub Request with only ``headers.get('idempotency-key')`` exercised."""
    headers: dict[str, str] = {}
    if idempotency_key is not None:
        headers["idempotency-key"] = idempotency_key

    class _Headers:
        def get(self, name: str, default: str | None = None) -> str | None:
            return headers.get(name.lower(), default)

    class _Request:
        def __init__(self) -> None:
            self.headers = _Headers()

    return _Request()


@pytest.mark.asyncio
async def test_missing_header_raises_required() -> None:
    request = _make_request(None)
    redis = AsyncMock()
    with pytest.raises(ValidationAppError) as exc_info:
        await verify_idempotency(request, redis)
    assert exc_info.value.message == "idempotency_key_required"


@pytest.mark.asyncio
async def test_empty_header_raises_required() -> None:
    """Empty string header is treated as missing (defensive against header tooling)."""
    request = _make_request("")
    redis = AsyncMock()
    with pytest.raises(ValidationAppError) as exc_info:
        await verify_idempotency(request, redis)
    assert exc_info.value.message == "idempotency_key_required"


@pytest.mark.asyncio
async def test_invalid_format_with_space() -> None:
    request = _make_request("with space")
    redis = AsyncMock()
    with pytest.raises(ValidationAppError) as exc_info:
        await verify_idempotency(request, redis)
    assert exc_info.value.message == "idempotency_key_invalid_format"


@pytest.mark.asyncio
async def test_invalid_format_with_bang() -> None:
    request = _make_request("bad!key")
    redis = AsyncMock()
    with pytest.raises(ValidationAppError) as exc_info:
        await verify_idempotency(request, redis)
    assert exc_info.value.message == "idempotency_key_invalid_format"


@pytest.mark.asyncio
async def test_valid_format_returns_key() -> None:
    request = _make_request("valid_key-123")
    redis = AsyncMock()
    key = await verify_idempotency(request, redis)
    assert key == "valid_key-123"


@pytest.mark.asyncio
async def test_too_long_is_invalid() -> None:
    request = _make_request("a" * 129)
    redis = AsyncMock()
    with pytest.raises(ValidationAppError) as exc_info:
        await verify_idempotency(request, redis)
    assert exc_info.value.message == "idempotency_key_invalid_format"


@pytest.mark.asyncio
async def test_max_length_128_is_valid() -> None:
    request = _make_request("a" * 128)
    redis = AsyncMock()
    key = await verify_idempotency(request, redis)
    assert key == "a" * 128


def test_pattern_matches_allowed_chars() -> None:
    pattern = re.compile(IDEMPOTENCY_KEY_PATTERN)
    assert pattern.match("ABC_123:def-456") is not None


def test_pattern_rejects_space() -> None:
    pattern = re.compile(IDEMPOTENCY_KEY_PATTERN)
    assert pattern.match("with space") is None


def test_body_sha256_is_64_hex() -> None:
    payload = b'{"reason":"refund"}'
    digest = body_sha256(payload)
    assert re.match(r"^[0-9a-f]{64}$", digest) is not None
