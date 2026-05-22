"""ЮKassa webhook IP allowlist (Phase 47 INFRA-37; Phase 48 ADAPTER-05 wires the real check).

Webhook security in v1.7 = IP allowlist (no HMAC). Source of the 6 CIDRs:
https://yookassa.ru/developers/using-api/webhooks (verified 2026-05-21).

Phase 47 shipped:
  - ``YOOKASSA_TRUSTED_IPS`` Final[frozenset[str]] — locked constant.
  - ``verify_yookassa_ip`` Depends()-callable SKELETON (stub-only; body
    deferred to Phase 48, filled by this module).

Phase 48 ADAPTER-05 fills the real body (this module):
  1. ``if settings.sandbox: return`` — sandbox bypass per D-47-07.
  2. Extract source IP from ``request.client.host``. X-Forwarded-For trust
     is deferred to Phase 50 (TODO marker below).
  3. Use ``ipaddress.ip_address`` + ``ipaddress.ip_network(cidr)`` for membership.
  4. On miss: emit ``yookassa_webhook_received`` STRUCTLOG WARNING with
     ``outcome="rejected_ip"`` + raise HTTPException(403, "forbidden_ip").

Phase 48 emission policy: ``verify_yookassa_ip`` runs as a FastAPI ``Depends()``
BEFORE the route body, so it has NO ``AsyncSession`` in scope. Rejection events
are emitted via ``structlog.warning(...)`` ONLY. The structured audit-DB row
(canonical event ``yookassa_webhook_received`` with ``idempotency_outcome=
"rejected_ip"``) is emitted by the Phase 50 webhook route handler via the
``app.core.audit`` canonical writer, which has the session. The widened
Literal in ``YookassaWebhookReceivedPayload.idempotency_outcome``
(Plan 48-01) exists for that Phase 50 consumer; this module never
constructs the payload.

AST-gate contract (test_locked_yookassa_constants_ast.py):
  - Every ``Depends(verify_yookassa_ip)`` callsite uses the literal name.
  - Any read of ``YOOKASSA_TRUSTED_IPS`` is via direct import — no dynamic
    ``set(...)`` / ``frozenset(...)`` / ``list(...)`` construction or
    attribute-lookup indirection.

Layer invariant: lives at integrations layer — MUST NOT import from
app.modules.* (importlinter contract integrations-not-depend-on-modules).
"""

from __future__ import annotations

import ipaddress
from typing import Final

import structlog
from fastapi import HTTPException, Request

from app.integrations.yookassa.settings import YooKassaSettings

YOOKASSA_TRUSTED_IPS: Final[frozenset[str]] = frozenset(
    {
        "185.71.76.0/27",
        "185.71.77.0/27",
        "77.75.153.0/25",
        "77.75.156.11/32",
        "77.75.156.35/32",
        "2a02:5180::/32",
    }
)

_settings: Final[YooKassaSettings] = YooKassaSettings()
_log = structlog.get_logger(__name__)


async def verify_yookassa_ip(request: Request) -> None:
    """Webhook IP allowlist check (Phase 48 ADAPTER-05; D-48-19).

    Order of checks:
      1. Sandbox bypass (D-47-07) — return immediately when settings.sandbox is True.
      2. Extract source IP from request.client.host. The X-Forwarded-For
         toggle is a Phase 50 concern (TODO marker below).
      3. Compare against YOOKASSA_TRUSTED_IPS via ipaddress.ip_network membership.
      4. On miss: emit STRUCTLOG warning (outcome="rejected_ip") + raise
         HTTPException(403, detail="forbidden_ip").

    Phase 48 reads request.client.host ONLY. Behind-reverse-proxy support
    (TRUSTED_PROXY_HEADER_ENABLED toggle) deferred to Phase 50 where the
    webhook route is wired and proxy topology is known.

    Audit emission split: this module emits via structlog only (no
    AsyncSession in scope at Depends() time). Phase 50's webhook route
    emits the audit DB row with idempotency_outcome="rejected_ip".

    Callsite contract (Phase 50 WH-01): always invoked via
    ``Depends(verify_yookassa_ip)`` so FastAPI's dependency ordering runs
    this BEFORE the route body parses the webhook payload.
    """
    # Step 1 — sandbox bypass (D-47-07).
    if _settings.sandbox:
        return

    # Step 2 — extract source IP. Phase 48 reads request.client.host only.
    # TODO Phase 50: honour X-Forwarded-For (first hop, comma-split, strip)
    # gated by a TRUSTED_PROXY_HEADER_ENABLED config flag once the reverse-proxy
    # topology in front of /_internal/yookassa/webhook is known.
    source_host = request.client.host if request.client is not None else None
    if source_host is None:
        _emit_rejected_ip_log(source_ip="(none)")
        raise HTTPException(status_code=403, detail="forbidden_ip")

    # Step 3 — parse + CIDR membership check.
    try:
        source_ip = ipaddress.ip_address(source_host)
    except ValueError:
        _emit_rejected_ip_log(source_ip=source_host)
        raise HTTPException(status_code=403, detail="forbidden_ip") from None

    for cidr in YOOKASSA_TRUSTED_IPS:
        try:
            if source_ip in ipaddress.ip_network(cidr):
                return
        except ValueError:
            # Malformed CIDR — defensive; AST gate already guards literal shape.
            continue

    # Step 4 — no CIDR match; emit structlog warning + raise 403.
    _emit_rejected_ip_log(source_ip=str(source_ip))
    raise HTTPException(status_code=403, detail="forbidden_ip")


def _emit_rejected_ip_log(*, source_ip: str) -> None:
    """Emit yookassa_webhook_received STRUCTLOG warning for IP-allowlist rejection.

    Phase 48 emission policy (see module docstring): structlog ONLY. The
    audit DB row is emitted by Phase 50's webhook route handler, which
    has an AsyncSession in scope and invokes the canonical
    ``app.core.audit`` writer with event ``yookassa_webhook_received``
    and ``idempotency_outcome="rejected_ip"``.

    ``source_ip`` is a structlog kwarg here, NOT a field on
    ``YookassaWebhookReceivedPayload`` (Pydantic v2 ``extra="forbid"``
    rejects unknown keys). The audit DB row carries
    ``outcome="rejected_ip"`` without IP; IP forensics come from this
    structlog log line.
    """
    # TODO Phase 50: Phase 50 webhook route will emit the canonical audit DB
    # row (via app.core.audit) with the same `outcome` literal after the IP
    # check passes/fails. This structlog warning is the Phase 48 record of
    # the rejection.
    _log.warning(
        "yookassa_webhook_received",
        outcome="rejected_ip",
        source_ip=source_ip,
    )
