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


def _make_request(
    idempotency_key: str | None,
    *,
    method: str = "POST",
    path: str = "/api/v1/test",
) -> Any:
    """Return a stub Request with header + method + url.path exercised.

    ``verify_idempotency`` returns ``f"{method}:{path}:{key}"`` (route-bound
    namespace per CR-01 / D-33-16) so the stub must expose both.
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
async def test_valid_format_returns_route_bound_key() -> None:
    """Returned key is ``f"{method}:{path}:{header}"`` (route-bound — CR-01)."""
    request = _make_request("valid_key-123", method="POST", path="/api/v1/test")
    redis = AsyncMock()
    key = await verify_idempotency(request, redis)
    assert key == "POST:/api/v1/test:valid_key-123"


@pytest.mark.asyncio
async def test_route_binding_distinguishes_endpoints() -> None:
    """Same header value on different routes returns distinct namespaced keys."""
    redis = AsyncMock()
    sale_req = _make_request(
        "abc123", method="POST", path="/api/v1/pt-packages"
    )
    refund_req = _make_request(
        "abc123",
        method="POST",
        path="/api/v1/pt-packages/00000000-0000-0000-0000-000000000001/refund",
    )
    sale_key = await verify_idempotency(sale_req, redis)
    refund_key = await verify_idempotency(refund_req, redis)
    assert sale_key != refund_key
    assert sale_key.endswith(":abc123")
    assert refund_key.endswith(":abc123")


@pytest.mark.asyncio
async def test_too_long_is_invalid() -> None:
    request = _make_request("a" * 129)
    redis = AsyncMock()
    with pytest.raises(ValidationAppError) as exc_info:
        await verify_idempotency(request, redis)
    assert exc_info.value.message == "idempotency_key_invalid_format"


@pytest.mark.asyncio
async def test_max_length_128_is_valid() -> None:
    request = _make_request("a" * 128, method="POST", path="/api/v1/test")
    redis = AsyncMock()
    key = await verify_idempotency(request, redis)
    # Route-bound: f"{method}:{path}:{header}" — header itself is preserved verbatim.
    assert key == f"POST:/api/v1/test:{'a' * 128}"


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
