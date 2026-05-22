"""Async httpx ЮKassa REST adapter — Phase 48 ADAPTER-02 (D-48-06..12).

``YooKassaClient`` exposes four async methods (``create_payment``,
``get_payment``, ``create_refund``, ``get_refund``) plus ``aclose``. Every
transport outcome is returned as a typed ``YooKassaPaymentResult`` /
``YooKassaRefundResult`` value — the client NEVER re-raises ``httpx``,
``json``, or generic exceptions across its boundary (SC1).

Classification chain (D-48-10) — mirror of the email integration's
``EmailClient`` outbound-boundary pattern, expanded for the richer httpx
failure surface:

- ``httpx.HTTPStatusError`` status == 422 → ``validation_error``
- ``httpx.HTTPStatusError`` status >= 500 → ``transient_error``
- ``httpx.HTTPStatusError`` other 4xx → ``permanent_error``
- ``httpx.TimeoutException`` → ``transient_error``
- ``httpx.RequestError`` (network) → ``transient_error``
- ``json.JSONDecodeError`` → ``permanent_error`` (malformed body)
- catch-all ``Exception`` → ``transient_error``
- success → ``ok`` with parsed payload populated

Divergences from the email adapter pattern:

- **Long-lived ``httpx.AsyncClient``** (D-48-06). ``aioboto3.Session`` is
  a factory (fresh client per call); ``httpx.AsyncClient`` is the opposite
  — designed for connection-pool reuse across the process lifetime.
  Constructed once in ``factory.py:build_yookassa_client`` and closed in
  the FastAPI lifespan teardown via ``YooKassaClient.aclose()``.
- **Idempotence-Key spelling quirk** (D-48-12). ЮKassa's interaction spec
  uses ONE 't' — ``Idempotence-Key`` — and silently rejects the
  standards-conformant double-t spelling. Locked as
  ``IDEMPOTENCE_KEY_HEADER: Final[str]`` below.
- **Confirmation auto-injection** (Claude's Discretion section of
  ``48-CONTEXT.md``). ``create_payment`` always sets
  ``confirmation = {"type": "redirect", "return_url": str(settings.return_url)}``
  on the request body — Phase 49 callers do NOT pass it. This keeps the
  redirect URL contract in one place (settings) and prevents per-callsite
  drift.

Idempotency contract (D-48-11): caller-owned ``idempotency_key: UUID``.
The adapter MUST NOT generate the key — the Phase 49 orchestrator persists
the key in ``online_payments`` BEFORE the HTTP call so ARQ retries replay
the same key (Pitfall 2 prevention).

Layer invariant: lives at ``integrations`` layer and MUST NOT import any
module under the per-domain modules package (importlinter contract
integrations-not-depend-on-modules).
"""

from __future__ import annotations

import json
from typing import Any, Final, Literal
from uuid import UUID

import httpx
import structlog

# Note: secret resolution lives in factory.py only — client.py operates on
# the already-constructed httpx.AsyncClient (which has BasicAuth pre-wired
# by the factory) and MUST NOT unwrap the SecretStr here. Single resolution
# point keeps the secret out of every other module's grep surface (D-48-07).
from app.integrations.yookassa._money import kopecks_to_yookassa, yookassa_to_kopecks
from app.integrations.yookassa.settings import YooKassaSettings
from app.integrations.yookassa.types import (
    YooKassaPaymentResult,
    YooKassaRefundResult,  # noqa: F401 — consumed by create_refund / get_refund in Task 2b
)

# Per ЮKassa interaction spec: header name has ONE 't' — "Idempotence-Key".
# Do NOT rename to the standards-conformant double-t spelling — ЮKassa
# silently rejects that form on POST /v3/payments (D-48-12).
IDEMPOTENCE_KEY_HEADER: Final[str] = "Idempotence-Key"

_log = structlog.get_logger("integrations.yookassa.client")


class YooKassaClient:
    """Async ЮKassa REST adapter (D-48-06..12).

    Owns a long-lived ``httpx.AsyncClient`` (constructed by the factory with
    BasicAuth + base URL + pinned timeouts) and a ``YooKassaSettings`` instance.
    Every method classifies its transport outcome into a typed result variant —
    the client never re-raises ``httpx`` / ``json`` / generic exceptions.
    """

    def __init__(
        self,
        *,
        http: httpx.AsyncClient,
        settings: YooKassaSettings,
    ) -> None:
        self._http = http
        self._settings = settings

    async def aclose(self) -> None:
        """Close the underlying ``httpx.AsyncClient`` (D-48-06).

        Called from the FastAPI lifespan teardown / ARQ ``on_shutdown`` so
        the connection pool releases TLS handles cleanly on process exit.
        """
        await self._http.aclose()

    def _classify_http_status_error(
        self,
        exc: httpx.HTTPStatusError,
    ) -> tuple[Literal["validation_error", "transient_error", "permanent_error"], int, str | None]:
        # Task 2b fills the body. The stub is acceptable transient state
        # between Tasks 2a and 2b (ruff accepts NotImplementedError as a body).
        raise NotImplementedError  # filled in Task 2b

    async def create_payment(
        self,
        *,
        amount_kopecks: int,
        description: str,
        receipt_items: list[dict[str, Any]],
        customer_email: str,
        idempotency_key: UUID,
        metadata: dict[str, str] | None = None,
    ) -> YooKassaPaymentResult:
        """POST /v3/payments — caller-owned idempotency_key (D-48-11).

        Auto-injects ``confirmation.return_url`` from
        ``settings.return_url`` (Claude's Discretion). The
        ``Idempotence-Key`` header (ONE 't' — D-48-12) is set on every call.
        Returns ``YooKassaPaymentResult`` — never re-raises (SC1).
        """
        body: dict[str, Any] = {
            "amount": {"value": kopecks_to_yookassa(amount_kopecks), "currency": "RUB"},
            "description": description,
            "capture": True,
            "confirmation": {
                "type": "redirect",
                "return_url": str(self._settings.return_url),
            },
            "receipt": {
                "customer": {"email": customer_email},
                "items": receipt_items,
                "tax_system_code": int(self._settings.tax_system_code),
            },
        }
        if metadata:
            body["metadata"] = metadata
        try:
            response = await self._http.post(
                "payments",
                json=body,
                headers={IDEMPOTENCE_KEY_HEADER: str(idempotency_key)},
            )
            response.raise_for_status()
            payload = response.json()
            confirmation = payload.get("confirmation") or {}
            _log.info(
                "yookassa_create_payment_ok",
                payment_id=payload["id"],
                status=payload["status"],
            )
            return YooKassaPaymentResult(
                ok=True,
                classification="ok",
                payment_id=payload["id"],
                status=payload["status"],
                confirmation_url=confirmation.get("confirmation_url"),
                amount_kopecks=yookassa_to_kopecks(payload["amount"]["value"]),
                idempotency_key=idempotency_key,
            )
        except httpx.HTTPStatusError as exc:
            classification, status, error_code = self._classify_http_status_error(exc)
            _log.warning(
                f"yookassa_create_payment_{classification}",
                http_status=status,
                error_code=error_code,
            )
            return YooKassaPaymentResult(
                ok=False,
                classification=classification,
                http_status=status,
                error_code=error_code,
                idempotency_key=idempotency_key,
                error=str(exc),
            )
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            _log.warning(
                "yookassa_create_payment_transient_error",
                reason=type(exc).__name__,
            )
            return YooKassaPaymentResult(
                ok=False,
                classification="transient_error",
                idempotency_key=idempotency_key,
                error=str(exc),
            )
        except json.JSONDecodeError as exc:
            _log.warning(
                "yookassa_create_payment_permanent_error",
                reason="malformed_json",
            )
            return YooKassaPaymentResult(
                ok=False,
                classification="permanent_error",
                idempotency_key=idempotency_key,
                error=str(exc),
            )
        except Exception as exc:  # outbound boundary — classify all transport failures
            _log.warning(
                "yookassa_create_payment_transient_error",
                reason=type(exc).__name__,
            )
            return YooKassaPaymentResult(
                ok=False,
                classification="transient_error",
                idempotency_key=idempotency_key,
                error=str(exc),
            )

    async def get_payment(self, payment_id: str) -> YooKassaPaymentResult:
        """GET /v3/payments/{id} — read-only, idempotent by HTTP semantics.

        No ``Idempotence-Key`` header (GET is HTTP-idempotent by definition).
        ``idempotency_key`` is ``None`` on the returned result variants.
        """
        try:
            response = await self._http.get(f"payments/{payment_id}")
            response.raise_for_status()
            payload = response.json()
            confirmation = payload.get("confirmation") or {}
            _log.info(
                "yookassa_get_payment_ok",
                payment_id=payload["id"],
                status=payload["status"],
            )
            return YooKassaPaymentResult(
                ok=True,
                classification="ok",
                payment_id=payload["id"],
                status=payload["status"],
                confirmation_url=confirmation.get("confirmation_url"),
                amount_kopecks=yookassa_to_kopecks(payload["amount"]["value"]),
                idempotency_key=None,
            )
        except httpx.HTTPStatusError as exc:
            classification, status, error_code = self._classify_http_status_error(exc)
            _log.warning(
                f"yookassa_get_payment_{classification}",
                http_status=status,
                error_code=error_code,
            )
            return YooKassaPaymentResult(
                ok=False,
                classification=classification,
                http_status=status,
                error_code=error_code,
                idempotency_key=None,
                error=str(exc),
            )
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            _log.warning(
                "yookassa_get_payment_transient_error",
                reason=type(exc).__name__,
            )
            return YooKassaPaymentResult(
                ok=False,
                classification="transient_error",
                idempotency_key=None,
                error=str(exc),
            )
        except json.JSONDecodeError as exc:
            _log.warning(
                "yookassa_get_payment_permanent_error",
                reason="malformed_json",
            )
            return YooKassaPaymentResult(
                ok=False,
                classification="permanent_error",
                idempotency_key=None,
                error=str(exc),
            )
        except Exception as exc:
            _log.warning(
                "yookassa_get_payment_transient_error",
                reason=type(exc).__name__,
            )
            return YooKassaPaymentResult(
                ok=False,
                classification="transient_error",
                idempotency_key=None,
                error=str(exc),
            )
