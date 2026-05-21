"""ЮKassa webhook IP allowlist (Phase 47 INFRA-37; Phase 48 ADAPTER-05 wires the real check).

Webhook security in v1.7 = IP allowlist (no HMAC). Source of the 6 CIDRs:
https://yookassa.ru/developers/using-api/webhooks (verified 2026-05-21).

Phase 47 ships:
  - ``YOOKASSA_TRUSTED_IPS`` Final[frozenset[str]] — locked constant.
  - ``verify_yookassa_ip`` Depends()-callable SKELETON — raises NotImplementedError.

Phase 48 ADAPTER-05 fills the real body:
  1. ``if settings.sandbox: return`` — sandbox bypass per D-47-07.
  2. Parse ``request.headers.get("x-forwarded-for")`` or ``request.client.host``.
  3. Use ``ipaddress.ip_address`` + ``ipaddress.ip_network(cidr)`` for membership.
  4. On miss: emit ``yookassa_webhook_received`` audit with
     ``idempotency_outcome="rejected_ip"`` (or analogous) + raise HTTPException(403).

AST-gate contract (test_locked_yookassa_constants_ast.py):
  - Every ``Depends(verify_yookassa_ip)`` callsite uses the literal name.
  - Any read of ``YOOKASSA_TRUSTED_IPS`` is via direct import — no dynamic
    ``set(...)`` / ``frozenset(...)`` / ``list(...)`` construction or
    attribute-lookup indirection.

Layer invariant: lives at integrations layer — MUST NOT import from
app.modules.* (importlinter contract integrations-not-depend-on-modules).
"""

from __future__ import annotations

from typing import Final

from fastapi import Request

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


async def verify_yookassa_ip(request: Request) -> None:
    """Validate webhook source IP against YOOKASSA_TRUSTED_IPS (Phase 48 ADAPTER-05).

    Phase 47 skeleton — raises NotImplementedError. Phase 48 fills the body
    per the contract documented in the module docstring above.

    Callsite contract (Phase 50 WH-01): always invoked via
    ``Depends(verify_yookassa_ip)`` so FastAPI's dependency ordering runs
    this BEFORE the route body parses the webhook payload.
    """
    raise NotImplementedError(
        "verify_yookassa_ip impl lands in Phase 48 ADAPTER-05 — "
        "Phase 47 ships only the import-resolvable name + the "
        "AST-gated YOOKASSA_TRUSTED_IPS frozenset."
    )
