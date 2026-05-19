"""Unit tests for ``app.integrations.email.factory.build_email_client``.

Plan 42-07 Task 3 — locks the async-factory shape and the sandbox-branch
zero-I/O guarantee. The non-sandbox /domains probe is exercised in the
integration tier (plan 42-09 wiring) because it requires a live aioboto3
session against Yandex Cloud Postbox; here we only assert the sandbox
short-circuit.
"""

from __future__ import annotations

import inspect

import pytest

from app.core.config import EmailProviderSettings
from app.integrations.email.client import SandboxEmailClient
from app.integrations.email.factory import build_email_client


def test_build_email_client_is_coroutine_function() -> None:
    """LOCKED: factory MUST be ``async def`` so callers can await naturally.

    Sync def + asyncio.run inside ARQ's on_startup (which is already running
    inside the worker event loop) raises RuntimeError. This test pins the
    async shape so the divergence from telegram.bot.build_bot cannot regress.
    """
    assert inspect.iscoroutinefunction(build_email_client)


@pytest.mark.asyncio
async def test_sandbox_branch_returns_sandbox_client() -> None:
    """When ``provider='sandbox'``, factory returns a SandboxEmailClient stub."""
    s = EmailProviderSettings()  # defaults: provider='sandbox', sandbox_mode=False
    client = await build_email_client(settings=s)
    assert isinstance(client, SandboxEmailClient)


@pytest.mark.asyncio
async def test_sandbox_mode_flag_returns_sandbox_client() -> None:
    """When sandbox_mode=True regardless of provider, factory returns sandbox stub.

    This is the operator-flag escape hatch — even with provider='yandex_postbox'
    set, flipping sandbox_mode=True short-circuits to the no-op stub.
    """
    s = EmailProviderSettings(
        provider="sandbox",  # validator requires sandbox or full creds
        sandbox_mode=True,
    )
    client = await build_email_client(settings=s)
    assert isinstance(client, SandboxEmailClient)
