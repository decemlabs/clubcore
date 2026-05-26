"""Unit tests for ``app.integrations.yookassa.factory.build_yookassa_client``.

Plan 48-03 Task 2: locks the async-factory shape (mirror
``test_build_email_client_is_coroutine_function`` rationale) AND the SC2
invariant — probe failure is NON-FATAL: ``build_yookassa_client`` returns
the constructed ``YooKassaClient`` regardless of probe outcome; only the
structlog signal differs.

Four failure-mode tests exercise SC2 (5xx, timeout, network error, sweep),
one success test locks the ok=True INFO log shape, and one shop_id-mismatch
test locks the WARNING log shape with ``reason="shop_id_mismatch"``.
"""

from __future__ import annotations

import inspect
from collections.abc import MutableMapping
from typing import Any

import httpx
import respx
import structlog
from pydantic import SecretStr

from app.integrations.yookassa.client import YooKassaClient
from app.integrations.yookassa.factory import build_yookassa_client
from app.integrations.yookassa.settings import YooKassaSettings

_BASE_URL = "https://api.yookassa.ru/v3/"
_RETURN_URL = "https://example.com/return"


def _test_settings(shop_id: int = 123456) -> YooKassaSettings:
    """Construct a YooKassaSettings instance for the factory test."""
    return YooKassaSettings(
        shop_id=shop_id,
        secret_key=SecretStr("test_secret"),
        return_url=_RETURN_URL,  # type: ignore[arg-type]
        tax_system_code=1,
        default_vat_code=1,
        sandbox=False,
    )


def _probe_logs(
    captured: list[MutableMapping[str, Any]],
) -> list[MutableMapping[str, Any]]:
    """Filter structlog records to ``yookassa_boot_probe`` events."""
    return [e for e in captured if e.get("event") == "yookassa_boot_probe"]


def test_build_yookassa_client_is_coroutine_function() -> None:
    """LOCKED: factory MUST be ``async def`` so callers can await naturally.

    Sync def + asyncio.run inside ARQ's on_startup (which is already running
    inside the worker event loop) raises RuntimeError. This test pins the
    async shape so the divergence from ``telegram.bot.build_bot`` cannot
    regress. Inherited from D-42-30 rationale; locked again here for
    D-48-13..15.
    """
    assert inspect.iscoroutinefunction(build_yookassa_client)


async def test_probe_success_returns_client_and_logs_ok() -> None:
    """200 + matching account_id → returns client, logs ok=True at INFO."""
    with (
        structlog.testing.capture_logs() as captured,
        respx.mock(base_url=_BASE_URL, assert_all_called=False) as router,
    ):
        router.get("me").mock(return_value=httpx.Response(200, json={"account_id": 123456}))
        client = await build_yookassa_client(settings=_test_settings())
    assert isinstance(client, YooKassaClient)
    probe_logs = _probe_logs(captured)
    assert len(probe_logs) == 1
    assert probe_logs[0]["ok"] is True
    assert probe_logs[0]["shop_id"] == "123456"
    await client.aclose()


async def test_probe_500_is_non_fatal_returns_client() -> None:
    """SC2 — probe 5xx is non-fatal: client is still returned, ok=False logged."""
    with (
        structlog.testing.capture_logs() as captured,
        respx.mock(base_url=_BASE_URL, assert_all_called=False) as router,
    ):
        router.get("me").mock(return_value=httpx.Response(500))
        client = await build_yookassa_client(settings=_test_settings())
    assert isinstance(client, YooKassaClient)
    probe_logs = _probe_logs(captured)
    assert len(probe_logs) == 1
    assert probe_logs[0]["ok"] is False
    await client.aclose()


async def test_probe_timeout_is_non_fatal_returns_client() -> None:
    """SC2 — probe TimeoutException is non-fatal; reason=TimeoutException logged."""
    with (
        structlog.testing.capture_logs() as captured,
        respx.mock(base_url=_BASE_URL, assert_all_called=False) as router,
    ):
        router.get("me").mock(side_effect=httpx.TimeoutException("test timeout"))
        client = await build_yookassa_client(settings=_test_settings())
    assert isinstance(client, YooKassaClient)
    probe_logs = _probe_logs(captured)
    assert len(probe_logs) == 1
    assert probe_logs[0]["ok"] is False
    assert probe_logs[0]["reason"] == "TimeoutException"
    await client.aclose()


async def test_probe_network_error_is_non_fatal() -> None:
    """SC2 — probe ConnectError is non-fatal; reason=ConnectError logged."""
    with (
        structlog.testing.capture_logs() as captured,
        respx.mock(base_url=_BASE_URL, assert_all_called=False) as router,
    ):
        router.get("me").mock(side_effect=httpx.ConnectError("test connect error"))
        client = await build_yookassa_client(settings=_test_settings())
    assert isinstance(client, YooKassaClient)
    probe_logs = _probe_logs(captured)
    assert len(probe_logs) == 1
    assert probe_logs[0]["ok"] is False
    assert probe_logs[0]["reason"] == "ConnectError"
    await client.aclose()


async def test_probe_shop_id_mismatch_logs_warning() -> None:
    """200 + mismatched account_id → ok=False, reason=shop_id_mismatch, expected+got."""
    with (
        structlog.testing.capture_logs() as captured,
        respx.mock(base_url=_BASE_URL, assert_all_called=False) as router,
    ):
        router.get("me").mock(return_value=httpx.Response(200, json={"account_id": 999999}))
        client = await build_yookassa_client(settings=_test_settings(shop_id=123456))
    assert isinstance(client, YooKassaClient)
    probe_logs = _probe_logs(captured)
    assert len(probe_logs) == 1
    assert probe_logs[0]["ok"] is False
    assert probe_logs[0]["reason"] == "shop_id_mismatch"
    assert probe_logs[0]["expected"] == "123456"
    assert probe_logs[0]["got"] == "999999"
    await client.aclose()


async def test_factory_never_raises_on_probe_failure() -> None:
    """SC2 sweep — probe 503 must not propagate any exception."""
    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as router:
        router.get("me").mock(return_value=httpx.Response(503))
        client = await build_yookassa_client(settings=_test_settings())
    assert isinstance(client, YooKassaClient)
    await client.aclose()
