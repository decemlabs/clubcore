"""Email client factory + boot-time domain probe (Phase 42 D-42-29 + D-42-30).

Single entrypoint ``build_email_client`` returns the configured transport for
Wave 3 callers: FastAPI's async lifespan (HTTP-side compose root) and ARQ's
``WorkerSettings.on_startup`` (worker-side compose root). Both callsites are
already coroutine-shaped and ``await`` the factory naturally.

LOCKED async signature -- divergence from ``telegram.bot.build_bot``:

``telegram.bot.build_bot`` is ``def`` (sync) because constructing a bare
``telegram.Bot`` is pure object construction with no I/O. This factory is
``async def`` because the non-sandbox branch performs a real network probe
against Yandex Cloud Postbox at boot time (D-42-30). Wrapping that probe
in a sync-from-async loop driver inside ARQ's ``on_startup`` -- which is
itself running inside the worker's live event loop -- raises
``RuntimeError: ... cannot be called from a running event loop``. The
async-factory shape is therefore the only safe form.

The factory is also explicitly **uncached**: a fresh client is constructed
per call so aiohttp connection pools owned by aioboto3 sessions do not leak
across worker container restarts.

Layer invariant: this module lives at ``integrations`` layer and MUST NOT
import from the per-domain modules package (import-linter contract 3).
"""

from __future__ import annotations

import aioboto3
import structlog
from botocore.config import Config

from app.core.config import EmailProviderSettings
from app.integrations.email.client import EmailClient, SandboxEmailClient

_log = structlog.get_logger("integrations.email.factory")


async def build_email_client(
    *, settings: EmailProviderSettings
) -> EmailClient | SandboxEmailClient:
    """Construct a fresh email client per call (no caching).

    Sandbox path (D-42-29): when ``settings.provider == 'sandbox'`` OR
    ``settings.sandbox_mode`` is true, return a ``SandboxEmailClient`` stub
    that logs envelopes at INFO and returns ``EmailSendResult.ok`` without
    any provider call. The sandbox branch performs ZERO I/O -- the await
    completes immediately.

    Non-sandbox path (D-42-30): construct an ``aioboto3.Session`` with
    ``Config(retries={'max_attempts': 1})`` (per D-42-02 -- provider SDK
    retries disabled; ARQ owns retry). Boot-time, ALSO call the SES-V2
    ``get_email_identity`` endpoint with ``EmailIdentity=settings.from_domain``
    and assert ``VerificationStatus == 'Success'``; failure raises
    ``RuntimeError`` at app boot (mirrors v1.2 D-18 ARQ on_startup
    fail-fast). The probe call happens natively via ``await`` -- never via
    a sync-from-async wrapper.

    Returns a FRESH client per call -- no module-level caching.
    """
    if settings.provider == "sandbox" or settings.sandbox_mode:
        _log.info(
            "email_client_built",
            provider="sandbox",
            sandbox_mode=settings.sandbox_mode,
        )
        return SandboxEmailClient()

    # Non-sandbox path: real Yandex Cloud Postbox adapter.
    # The validator on EmailProviderSettings guarantees both keys + from_domain
    # are non-empty when we land here, but we narrow types defensively for mypy.
    if settings.aws_access_key_id is None or settings.aws_secret_access_key is None:
        raise RuntimeError(
            "EmailProviderSettings AWS credentials missing for non-sandbox provider "
            "(validator should have rejected this earlier)."
        )

    session = aioboto3.Session(
        aws_access_key_id=settings.aws_access_key_id.get_secret_value(),
        aws_secret_access_key=settings.aws_secret_access_key.get_secret_value(),
    )

    # D-42-30: boot-time /domains probe. Fails fast on unverified sender domain
    # so the app cannot start in a configuration where every send would bounce.
    async with session.client(
        "sesv2",
        endpoint_url=settings.endpoint_url,
        config=Config(retries={"max_attempts": 1}),
    ) as probe_client:
        resp = await probe_client.get_email_identity(
            EmailIdentity=settings.from_domain,
        )

    status = resp.get("VerificationStatus") if isinstance(resp, dict) else None
    if status != "Success":
        raise RuntimeError(
            f"EmailProviderSettings.from_domain {settings.from_domain!r} "
            f"not verified: status={status!r}"
        )

    _log.info(
        "email_client_built",
        provider=settings.provider,
        from_domain=settings.from_domain,
        endpoint_url=settings.endpoint_url,
    )
    return EmailClient(
        session=session,
        endpoint_url=settings.endpoint_url,
        from_address=settings.from_address,
    )
