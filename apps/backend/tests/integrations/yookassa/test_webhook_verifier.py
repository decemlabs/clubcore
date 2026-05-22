"""Phase 48 ADAPTER-05 — verify_yookassa_ip body unit tests (Plan 48-05 Task 2).

Locks SC4 ("returns 403 for IPs outside trusted CIDRs; sandbox bypasses the
check") and the D-48-19 step-by-step contract:

  1. Sandbox bypass returns None immediately (D-47-07).
  2. IPv4/IPv6 inside any YOOKASSA_TRUSTED_IPS CIDR returns None silently.
  3. IP outside all CIDRs raises HTTPException(403, "forbidden_ip").
  4. request.client is None and malformed IP strings are caught and converted
     to 403 (no uncaught ValueError reaches the route layer).
  5. Every rejection emits exactly one ``yookassa_webhook_received`` structlog
     WARNING with kwargs ``outcome="rejected_ip"`` + ``source_ip=<ip>``.

Emission policy (Phase 48): structlog ONLY. ``source_ip`` lives as a structlog
kwarg, NOT as a field on ``YookassaWebhookReceivedPayload`` (Pydantic v2
``extra="forbid"``). The audit DB row is emitted by Phase 50's webhook route
handler (which has an ``AsyncSession``); tests for THAT live in Phase 50.

TODO Phase 50: tests for X-Forwarded-For trust (gated by
``TRUSTED_PROXY_HEADER_ENABLED``) belong in Phase 50 once the reverse-proxy
topology in front of /_internal/yookassa/webhook is known.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest
import structlog
from fastapi import HTTPException

from app.integrations.yookassa import webhook_verifier as wv
from app.integrations.yookassa.webhook_verifier import verify_yookassa_ip


class _MockClient:
    """Minimal stand-in for the ``request.client`` attribute (Starlette Address)."""

    def __init__(self, host: str) -> None:
        self.host = host


class _MockRequest:
    """Minimal stand-in for fastapi.Request — only exposes ``.client.host``.

    A real ``starlette.requests.Request`` would require constructing an ASGI
    scope; the verifier only reads ``request.client.host`` so we stub it.
    """

    def __init__(self, client_host: str | None) -> None:
        self.client: _MockClient | None = (
            _MockClient(host=client_host) if client_host is not None else None
        )


class _StubSettings:
    """Stand-in for ``YooKassaSettings`` exposing only ``.sandbox`` (the field
    ``verify_yookassa_ip`` reads).
    """

    def __init__(self) -> None:
        self.sandbox: bool = False


@pytest.fixture
def patched_settings(monkeypatch: pytest.MonkeyPatch) -> _StubSettings:
    """Replace the module-level ``_settings`` singleton with a configurable stub.

    Returns the stub instance so each test can flip ``.sandbox`` as needed.
    """
    stub = _StubSettings()
    monkeypatch.setattr(wv, "_settings", stub)
    return stub


@pytest.fixture(autouse=True)
def _reset_webhook_verifier_logger_cache() -> Iterator[None]:
    """Invalidate the module-level structlog cache so ``capture_logs()`` works.

    ``structlog.get_logger(__name__)`` returns a ``BoundLoggerLazyProxy`` whose
    first ``.warning(...)`` call caches the processor chain in
    ``proxy.__dict__["bind"]``. ``structlog.testing.capture_logs()`` patches
    the global processor list, but the cached bind on the proxy bypasses it —
    so we drop the cache before each test (mirrors the pattern in
    tests/integration/bookings/test_reminder_cron.py).
    """
    if "bind" in wv._log.__dict__:
        del wv._log.__dict__["bind"]
    yield
    if "bind" in wv._log.__dict__:
        del wv._log.__dict__["bind"]


async def test_sandbox_bypass_returns_none_without_inspecting_request(
    patched_settings: _StubSettings,
) -> None:
    """D-47-07: sandbox=True short-circuits BEFORE any IP check.

    The mock request has ``client=None`` which would otherwise raise 403;
    sandbox bypass must return None without inspecting it.
    """
    patched_settings.sandbox = True
    request = _MockRequest(client_host=None)
    with structlog.testing.capture_logs() as captured:
        # No exception raised + returns None implicitly = sandbox bypass succeeded.
        await verify_yookassa_ip(request)  # type: ignore[arg-type]
    assert not any(c.get("event") == "yookassa_webhook_received" for c in captured)


async def test_trusted_ipv4_allowed(patched_settings: _StubSettings) -> None:
    """An IP inside the 185.71.76.0/27 trusted CIDR passes silently."""
    patched_settings.sandbox = False
    request = _MockRequest(client_host="185.71.76.5")
    with structlog.testing.capture_logs() as captured:
        await verify_yookassa_ip(request)  # type: ignore[arg-type]
    assert not any(c.get("event") == "yookassa_webhook_received" for c in captured)


async def test_untrusted_ipv4_raises_403_and_emits_structlog(
    patched_settings: _StubSettings,
) -> None:
    """Public-internet IP (8.8.8.8) is not in any trusted CIDR — 403 + structlog warning."""
    patched_settings.sandbox = False
    request = _MockRequest(client_host="8.8.8.8")
    with structlog.testing.capture_logs() as captured, pytest.raises(HTTPException) as exc:
        await verify_yookassa_ip(request)  # type: ignore[arg-type]
    assert exc.value.status_code == 403
    assert exc.value.detail == "forbidden_ip"
    events = [c for c in captured if c.get("event") == "yookassa_webhook_received"]
    assert len(events) == 1
    assert events[0]["outcome"] == "rejected_ip"
    assert events[0]["source_ip"] == "8.8.8.8"
    assert events[0]["log_level"] == "warning"


async def test_missing_client_raises_403_and_emits_structlog(
    patched_settings: _StubSettings,
) -> None:
    """request.client=None is treated as a rejection (source_ip='(none)' sentinel)."""
    patched_settings.sandbox = False
    request = _MockRequest(client_host=None)
    with structlog.testing.capture_logs() as captured, pytest.raises(HTTPException) as exc:
        await verify_yookassa_ip(request)  # type: ignore[arg-type]
    assert exc.value.status_code == 403
    assert exc.value.detail == "forbidden_ip"
    events = [c for c in captured if c.get("event") == "yookassa_webhook_received"]
    assert len(events) == 1
    assert events[0]["outcome"] == "rejected_ip"
    assert events[0]["source_ip"] == "(none)"


async def test_malformed_ip_raises_403_no_uncaught_valueerror(
    patched_settings: _StubSettings,
) -> None:
    """T-48-05-04 mitigation: ipaddress.ip_address raises ValueError on garbage;
    the verifier MUST catch it and convert to 403 (not leak as 500).
    """
    patched_settings.sandbox = False
    request = _MockRequest(client_host="not-an-ip-address")
    with structlog.testing.capture_logs() as captured, pytest.raises(HTTPException) as exc:
        await verify_yookassa_ip(request)  # type: ignore[arg-type]
    assert exc.value.status_code == 403
    assert exc.value.detail == "forbidden_ip"
    events = [c for c in captured if c.get("event") == "yookassa_webhook_received"]
    assert len(events) == 1
    assert events[0]["outcome"] == "rejected_ip"
    assert events[0]["source_ip"] == "not-an-ip-address"


async def test_ipv6_trusted_range_accepted(patched_settings: _StubSettings) -> None:
    """The 2a02:5180::/32 IPv6 CIDR is in YOOKASSA_TRUSTED_IPS — IPv6 inside it passes."""
    patched_settings.sandbox = False
    request = _MockRequest(client_host="2a02:5180:0001:0002::1")
    with structlog.testing.capture_logs() as captured:
        await verify_yookassa_ip(request)  # type: ignore[arg-type]
    assert not any(c.get("event") == "yookassa_webhook_received" for c in captured)


async def test_structlog_event_shape_for_rejected_ip(
    patched_settings: _StubSettings,
) -> None:
    """The rejected-IP structlog event MUST carry outcome + source_ip kwargs.

    NOTE: source_ip lives as a structlog kwarg ONLY — it is NOT a field on
    YookassaWebhookReceivedPayload (Pydantic v2 extra="forbid"). The audit
    DB row (Phase 50) carries outcome="rejected_ip" without IP; IP forensics
    come from the structlog log line captured here.
    """
    patched_settings.sandbox = False
    request = _MockRequest(client_host="1.2.3.4")
    with structlog.testing.capture_logs() as captured, pytest.raises(HTTPException):
        await verify_yookassa_ip(request)  # type: ignore[arg-type]
    events = [c for c in captured if c.get("event") == "yookassa_webhook_received"]
    assert len(events) == 1
    event = events[0]
    assert event["outcome"] == "rejected_ip"
    assert event["source_ip"] == "1.2.3.4"
    assert event["log_level"] == "warning"
