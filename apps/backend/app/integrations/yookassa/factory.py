"""ЮKassa client factory + boot-time /v3/me probe (Phase 48 ADAPTER-03 D-48-13..15).

Single entrypoint ``build_yookassa_client`` returns the process-wide
``YooKassaClient`` for Wave 3 / Plan 48-07 callers: FastAPI's async lifespan
(HTTP-side compose root) and ARQ's ``WorkerSettings.on_startup`` (worker-side
compose root). Both callsites are already coroutine-shaped and ``await`` the
factory naturally.

LOCKED async signature -- divergence from ``telegram.bot.build_bot``:

``telegram.bot.build_bot`` is ``def`` (sync) because constructing a bare
``telegram.Bot`` is pure object construction with no I/O. This factory is
``async def`` because the non-sandbox branch performs a real network probe
against ЮKassa at boot time (D-48-13). Wrapping that probe in a
sync-from-async loop driver inside ARQ's ``on_startup`` -- which is itself
running inside the worker's live event loop -- raises ``RuntimeError: ...
cannot be called from a running event loop``. The async-factory shape is
therefore the only safe form. This rationale is inherited verbatim from
``email/factory.py`` (D-42-30 lineage).

DIVERGENCE FROM email/factory.py — httpx.AsyncClient returned here is
LONG-LIVED for the process lifetime (D-48-06). FastAPI lifespan teardown /
ARQ on_shutdown closes it via ``client.aclose()``. This is the OPPOSITE of
the ``aioboto3.Session`` per-call factory discipline ``email/factory.py``
follows -- the email factory deliberately constructs a fresh session per
call so aiohttp connection pools owned by the session do not leak across
worker container restarts. httpx is designed for connection-pool reuse;
re-creating the AsyncClient per outbound call would re-handshake TLS on
every payment.

DIVERGENCE FROM email/factory.py — probe failure is NON-FATAL (D-48-14,
SC2). The constructed ``YooKassaClient`` is returned regardless of probe
outcome; only the structlog signal differs. This is the OPPOSITE of
email's ``RuntimeError`` fail-fast (``email/factory.py:96-99``). The
operator runbook (Phase 53 deferred) covers the degraded-mode signal:
"If ``yookassa_boot_probe ok=False`` appears in logs, the online-payments
endpoints will return ``transient_error`` until ЮKassa reachability is
restored." Single probe attempt, no retry (D-48-15).

Layer invariant: lives at ``integrations`` layer — MUST NOT import from
``app.modules.*`` (importlinter contract integrations-not-depend-on-modules).
"""

from __future__ import annotations

import httpx
import structlog

from app.integrations.yookassa.client import YooKassaClient
from app.integrations.yookassa.settings import YooKassaSettings

_log = structlog.get_logger("integrations.yookassa.factory")

_YOOKASSA_BASE_URL: str = "https://api.yookassa.ru/v3/"


async def build_yookassa_client(*, settings: YooKassaSettings) -> YooKassaClient:
    """Construct process-wide YooKassaClient + run non-fatal /v3/me probe.

    D-48-06 (long-lived) + D-48-13..15 (probe contract).

    Divergence from email/factory.py:
      - httpx.AsyncClient is LONG-LIVED (factory returns a single instance per process,
        closed by FastAPI lifespan teardown / ARQ on_shutdown via client.aclose()).
      - Probe failure is NON-FATAL (D-48-14, SC2 — degraded mode). The constructed
        YooKassaClient is returned regardless; only the structlog signal differs.
      - Single probe attempt, no retry (D-48-15) — operator runbook covers degraded mode.

    The sandbox flag does NOT change the base URL (D-48-08); ЮKassa uses the SAME
    host with sandbox-issued credentials. ``sandbox=True`` only bypasses the
    webhook IP allowlist (Phase 47 D-47-07; Phase 48 webhook_verifier consumer).
    """
    http = httpx.AsyncClient(
        base_url=_YOOKASSA_BASE_URL,
        auth=httpx.BasicAuth(
            username=str(settings.shop_id),
            password=settings.secret_key.get_secret_value(),
        ),
        timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
        # User-Agent must be ASCII-safe — httpx normalises header values via
        # value.encode("ascii") (httpx._models._normalize_header_value).
        # Cyrillic glyphs (e.g. "ЮKassa") raise UnicodeEncodeError at
        # AsyncClient construction time. We keep the Latinised "YooKassa"
        # form for the wire header; the docstring / log messages still use
        # the original "ЮKassa" spelling.
        headers={"User-Agent": "Sportzal/1.7 YooKassa-Adapter"},
    )
    # D-48-13: boot probe via GET /v3/me. D-48-15: single attempt, no retry.
    try:
        resp = await http.get("me", timeout=5.0)
        resp.raise_for_status()
        body = resp.json()
        probe_account_id = body.get("account_id") if isinstance(body, dict) else None
        if probe_account_id is not None and str(probe_account_id) != str(settings.shop_id):
            _log.warning(
                "yookassa_boot_probe",
                ok=False,
                reason="shop_id_mismatch",
                expected=str(settings.shop_id),
                got=str(probe_account_id),
            )
        else:
            _log.info(
                "yookassa_boot_probe",
                ok=True,
                shop_id=str(settings.shop_id),
            )
    except Exception as exc:
        # D-48-14: NON-FATAL — log + continue. Caller still receives a usable client.
        _log.warning(
            "yookassa_boot_probe",
            ok=False,
            reason=type(exc).__name__,
            error=str(exc),
        )
    return YooKassaClient(http=http, settings=settings)
