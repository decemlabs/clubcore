"""Unit tests for verify_csrf dependency.

Phase 6 — D-05, D-06, D-07, D-08, D-23.
"""

from __future__ import annotations

import secrets as secrets_mod
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from structlog.testing import capture_logs

from app.core.dependencies import _SAFE_METHODS, verify_csrf
from app.core.exceptions import CsrfMismatch


def _req(
    method: str = "POST",
    *,
    cookie: str | None = None,
    header: str | None = None,
    path: str = "/api/v1/auth/logout",
    host: str | None = "127.0.0.1",
) -> Any:
    cookies = {"sportzal_csrf": cookie} if cookie is not None else {}
    headers = {"x-csrf-token": header} if header is not None else {}
    client = SimpleNamespace(host=host) if host is not None else None
    return SimpleNamespace(
        method=method,
        cookies=SimpleNamespace(get=lambda k, default=None: cookies.get(k, default)),
        headers=SimpleNamespace(get=lambda k, default=None: headers.get(k, default)),
        url=SimpleNamespace(path=path),
        client=client,
    )


def _session() -> Any:
    """Stub AsyncSession sufficient for audit.emit's session.add() call."""
    return SimpleNamespace(add=lambda _row: None)


def test_safe_methods_constant_is_locked() -> None:
    assert frozenset({"GET", "HEAD", "OPTIONS", "TRACE"}) == _SAFE_METHODS


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS", "TRACE"])
async def test_safe_methods_short_circuit_returns_none(method: str) -> None:
    # No cookies / headers — must NOT raise (D-06).
    result = await verify_csrf(_req(method=method), session=_session())
    assert result is None


async def test_post_with_matching_cookie_and_header_returns_none() -> None:
    token = "abc123" * 6  # 36 chars; identical for cookie + header
    result = await verify_csrf(
        _req(method="POST", cookie=token, header=token), session=_session()
    )
    assert result is None


async def test_post_with_missing_header_raises_and_emits() -> None:
    with capture_logs() as captured, pytest.raises(CsrfMismatch):
        await verify_csrf(
            _req(method="POST", cookie="abc", header=None), session=_session()
        )
    events = [c for c in captured if c.get("event") == "csrf_mismatch"]
    assert len(events) == 1
    ev = events[0]
    # Phase 8 D-04: actor_user_id and resource_type moved to AuditLog DB columns;
    # structlog event keeps only payload kwargs.
    assert ev["has_cookie"] is True
    assert ev["has_header"] is False
    assert ev["method"] == "POST"
    assert ev["path"] == "/api/v1/auth/logout"
    assert ev["ip"] == "127.0.0.1"


async def test_post_with_missing_cookie_raises_and_emits() -> None:
    with capture_logs() as captured, pytest.raises(CsrfMismatch):
        await verify_csrf(
            _req(method="POST", cookie=None, header="abc"), session=_session()
        )
    ev = next(c for c in captured if c.get("event") == "csrf_mismatch")
    assert ev["has_cookie"] is False
    assert ev["has_header"] is True


async def test_post_with_mismatched_values_raises() -> None:
    with capture_logs() as captured, pytest.raises(CsrfMismatch):
        await verify_csrf(
            _req(method="POST", cookie="aaa", header="bbb"), session=_session()
        )
    ev = next(c for c in captured if c.get("event") == "csrf_mismatch")
    assert ev["has_cookie"] is True
    assert ev["has_header"] is True


async def test_post_uses_secrets_compare_digest() -> None:
    with patch(
        "app.core.dependencies.secrets.compare_digest",
        wraps=secrets_mod.compare_digest,
    ) as spy:
        await verify_csrf(
            _req(method="POST", cookie="x", header="x"), session=_session()
        )
        assert spy.called


async def test_emit_ip_none_when_client_missing() -> None:
    with capture_logs() as captured, pytest.raises(CsrfMismatch):
        await verify_csrf(
            _req(method="POST", cookie="a", header=None, host=None),
            session=_session(),
        )
    ev = next(c for c in captured if c.get("event") == "csrf_mismatch")
    assert ev["ip"] is None


async def test_csrf_mismatch_message_is_locked_code() -> None:
    """D-21 envelope: message string is 'csrf_mismatch' so client retry branch matches."""
    with pytest.raises(CsrfMismatch) as excinfo:
        await verify_csrf(
            _req(method="POST", cookie="a", header="b"), session=_session()
        )
    assert excinfo.value.message == "csrf_mismatch"
    assert excinfo.value.code == "csrf_mismatch"
    assert excinfo.value.status_code == 403
