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

Idempotency contract (D-48-11 + Phase 49 D-49-08 widening): caller-owned
``idempotency_key: UUID | str``. UUID form is the Phase 48 default; sha256
hex string form is the Phase 49 deterministic-key shape. The adapter MUST
NOT generate the key — the Phase 49 orchestrator persists the key in
``online_payments`` BEFORE the HTTP call so ARQ retries replay the same
key (Pitfall 2 prevention).

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
    YooKassaReceiptResult,
    YooKassaRefundResult,
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
        """Map an httpx HTTPStatusError to the closed classification taxonomy.

        Extracts ``error_code`` from the ЮKassa error envelope
        (``{"type":"error","code":"...","description":"..."}``) when the body
        parses; otherwise leaves it ``None``. The mapping itself is the
        canonical D-48-10 split:

        - 422 → ``classification="validation_error"``
        - 5xx → ``classification="transient_error"``
        - all other 4xx → ``classification="permanent_error"``
        """
        status = exc.response.status_code
        error_code: str | None = None
        try:
            body = exc.response.json()
            if isinstance(body, dict):
                raw = body.get("code")
                if isinstance(raw, str):
                    error_code = raw
        except (json.JSONDecodeError, ValueError):
            error_code = None
        if status == 422:
            return ("validation_error", status, error_code)
        if status >= 500:
            return ("transient_error", status, error_code)
        return ("permanent_error", status, error_code)

    async def create_payment(
        self,
        *,
        amount_kopecks: int,
        description: str,
        receipt_items: list[dict[str, Any]],
        customer_email: str | None = None,
        customer_phone: str | None = None,
        idempotency_key: UUID | str,
        confirmation_type: Literal["redirect", "qr"] = "redirect",
        return_url: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> YooKassaPaymentResult:
        """POST /v3/payments — caller-owned idempotency_key (D-48-11 + D-49-08).

        ``confirmation_type`` (Phase 49 PAY-05) selects the confirmation
        method ЮKassa returns: ``'redirect'`` (default — adapter auto-injects
        ``return_url`` from settings, Claude's Discretion) or ``'qr'``
        (provider returns ``confirmation.confirmation_data`` instead of
        ``confirmation_url``).

        ``idempotency_key`` is ``UUID`` (Phase 48 default) or ``str`` (Phase
        49 sha256 hex shape, D-49-08). The ``Idempotence-Key`` header (ONE
        't' — D-48-12) carries the value verbatim — ЮKassa accepts any
        opaque ASCII string. For string keys the returned
        ``result.idempotency_key`` is ``None`` (the typed dataclass field
        is ``UUID | None``); the caller already owns the key.

        Receipt contact (D-10 Phase 999.5):
        ``customer_email`` maps to ЮKassa ``receipt.customer.email`` key.
        ``customer_phone`` maps to ЮKassa ``receipt.customer.phone`` key.
        Exactly one must be supplied — email is preferred when present
        (staff + email-gate paths); phone is the 54-ФЗ fallback when email
        is absent («Чек не нужен» path).  Both None is an invariant violation.
        PII discipline (T-51-03-01 / T-999.5-12): contact values NEVER appear
        in structlog events — only in the ЮKassa request body (non-logged).

        Returns ``YooKassaPaymentResult`` — never re-raises (SC1).
        """
        # Preserved key for echo into the result dataclass (UUID-typed only).
        result_idempotency_key: UUID | None = (
            idempotency_key if isinstance(idempotency_key, UUID) else None
        )
        # D-10 / T-999.5-11: build customer object with the correct key.
        # Email maps to "email" key; phone maps to "phone" key — never crossed.
        # Both None is an invariant violation (phone is DB NOT NULL via OTP auth,
        # so this guard should never fire in production).
        if customer_email is not None:
            customer_obj: dict[str, str] = {"email": customer_email}
        elif customer_phone is not None:
            customer_obj = {"phone": customer_phone}
        else:
            raise ValueError(
                "create_payment requires either customer_email or customer_phone; "
                "neither was provided (invariant violation — phone is NOT NULL)"
            )
        # CR-01/CR-02: caller can supply a per-payment return_url (client path bakes
        # payment_id into the URL so PWA can poll status). Staff callers pass nothing
        # → falls back to the shared settings.return_url (byte-identical behaviour).
        confirmation_body: dict[str, Any]
        if confirmation_type == "redirect":
            confirmation_body = {
                "type": "redirect",
                "return_url": return_url if return_url is not None else str(self._settings.return_url),
            }
        else:  # "qr"
            confirmation_body = {"type": "qr"}
        body: dict[str, Any] = {
            "amount": {"value": kopecks_to_yookassa(amount_kopecks), "currency": "RUB"},
            "description": description,
            "capture": True,
            "confirmation": confirmation_body,
            "receipt": {
                "customer": customer_obj,
                "items": receipt_items,
                "tax_system_code": int(self._settings.tax_system_code),
            },
        }
        if metadata:
            body["metadata"] = metadata
        try:
            # idempotency_key may be a UUID (Phase 48 callsite) or a sha256 hex
            # string (Phase 49 D-49-08 deterministic key). ЮKassa Idempotence-Key
            # accepts any opaque ASCII string — both forms are wire-compatible.
            response = await self._http.post(
                "payments",
                json=body,
                headers={IDEMPOTENCE_KEY_HEADER: str(idempotency_key)},
            )
            response.raise_for_status()
            payload = response.json()
            confirmation = payload.get("confirmation") or {}
            qr_payload: str | None = None
            if confirmation_type == "qr":
                qr_payload = confirmation.get("confirmation_data")
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
                idempotency_key=result_idempotency_key,
                qr_payload=qr_payload,
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
                idempotency_key=result_idempotency_key,
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
                idempotency_key=result_idempotency_key,
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
                idempotency_key=result_idempotency_key,
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
                idempotency_key=result_idempotency_key,
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
            # BLOCKER #1 (Phase 49 D-49-04 + D-49-09): re-fetch path for QR-style
            # payments must surface the upstream confirmation_data so the
            # service-layer QR-replay returns a SellResponse that satisfies
            # the Pydantic XOR validator. The row stores no qr_payload — ЮKassa
            # server-side dedup returns the original payment object with the
            # current confirmation_data on every GET /payments/{id}.
            qr_payload: str | None = None
            if confirmation.get("type") == "qr":
                qr_payload = confirmation.get("confirmation_data")
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
                qr_payload=qr_payload,
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

    async def create_refund(
        self,
        *,
        payment_id: str,
        amount_kopecks: int,
        idempotency_key: UUID,
        receipt_items: list[dict[str, Any]] | None = None,
    ) -> YooKassaRefundResult:
        """POST /v3/refunds — caller-owned idempotency_key (D-48-11).

        Optionally accepts ``receipt_items`` (54-ФЗ fiscalization needs a
        refund receipt for membership/PT refunds — Phase 51). Sends the
        ``Idempotence-Key`` header (ONE 't' — D-48-12). Never re-raises.
        """
        body: dict[str, Any] = {
            "payment_id": payment_id,
            "amount": {"value": kopecks_to_yookassa(amount_kopecks), "currency": "RUB"},
        }
        if receipt_items is not None:
            body["receipt"] = {
                "items": receipt_items,
                "tax_system_code": int(self._settings.tax_system_code),
            }
        try:
            response = await self._http.post(
                "refunds",
                json=body,
                headers={IDEMPOTENCE_KEY_HEADER: str(idempotency_key)},
            )
            response.raise_for_status()
            payload = response.json()
            _log.info(
                "yookassa_create_refund_ok",
                refund_id=payload["id"],
                payment_id=payload["payment_id"],
                status=payload["status"],
            )
            return YooKassaRefundResult(
                ok=True,
                classification="ok",
                refund_id=payload["id"],
                payment_id=payload["payment_id"],
                status=payload["status"],
                amount_kopecks=yookassa_to_kopecks(payload["amount"]["value"]),
                idempotency_key=idempotency_key,
            )
        except httpx.HTTPStatusError as exc:
            classification, status, error_code = self._classify_http_status_error(exc)
            _log.warning(
                f"yookassa_create_refund_{classification}",
                http_status=status,
                error_code=error_code,
            )
            return YooKassaRefundResult(
                ok=False,
                classification=classification,
                http_status=status,
                error_code=error_code,
                idempotency_key=idempotency_key,
                error=str(exc),
            )
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            _log.warning(
                "yookassa_create_refund_transient_error",
                reason=type(exc).__name__,
            )
            return YooKassaRefundResult(
                ok=False,
                classification="transient_error",
                idempotency_key=idempotency_key,
                error=str(exc),
            )
        except json.JSONDecodeError as exc:
            _log.warning(
                "yookassa_create_refund_permanent_error",
                reason="malformed_json",
            )
            return YooKassaRefundResult(
                ok=False,
                classification="permanent_error",
                idempotency_key=idempotency_key,
                error=str(exc),
            )
        except Exception as exc:
            _log.warning(
                "yookassa_create_refund_transient_error",
                reason=type(exc).__name__,
            )
            return YooKassaRefundResult(
                ok=False,
                classification="transient_error",
                idempotency_key=idempotency_key,
                error=str(exc),
            )

    async def create_receipt(
        self,
        *,
        payment_id: str,
        customer_email: str,
        items: list[dict[str, Any]],
        tax_system_code: int,
        idempotency_key: str,
        kind: Literal["payment", "refund"] = "payment",
    ) -> YooKassaReceiptResult:
        """POST /v3/receipts — 54-ФЗ fiscalization (Phase 51 FISCAL-05 / D-51-20).

        Caller-owned ``idempotency_key`` (D-48-11 + D-51-20). Mirrors
        ``create_refund`` (line 350) shape byte-for-byte: same closed
        classification taxonomy (``ok`` / ``validation_error`` /
        ``transient_error`` / ``permanent_error``), same ``Idempotence-Key``
        header (ONE 't' — D-48-12), same never-re-raise discipline.

        ``kind`` discriminates the receipt body:

        - ``"payment"`` — receipt for a successful ``online_payments`` row
          (``fiscal_receipts.kind='payment'``). Body uses ``"payment_id"``.
        - ``"refund"`` — receipt for a successful ``refunds`` row
          (``fiscal_receipts.kind='refund'``). Body uses ``"refund_id"``.
          The ``payment_id`` parameter carries the refund_id in this branch
          per ЮKassa /v3/receipts API spec.

        ЮKassa fires a ``receipt.succeeded`` webhook AFTER fiscalization
        settles. The caller (plan 51-05 dispatch task) MUST NOT mark the
        ``fiscal_receipts`` row ``succeeded`` on ``classification == 'ok'``
        — only stash ``result.receipt_id`` into
        ``fiscal_receipts.yookassa_receipt_id`` and let the webhook FSM
        transition the row.

        PII discipline (Threat T-51-03-01): structlog events log only
        ``receipt_id`` / ``status`` / ``classification`` / ``http_status``.
        ``customer_email`` NEVER appears in any ``_log.info`` /
        ``_log.warning`` kwarg — audit-DB rows are PII-acceptable; structlog
        is not.

        Returns ``YooKassaReceiptResult`` — never re-raises (SC1).
        """
        link_field = "payment_id" if kind == "payment" else "refund_id"
        body: dict[str, Any] = {
            "type": kind,
            link_field: payment_id,
            "customer": {"email": customer_email},
            "items": items,
            "tax_system_code": int(tax_system_code),
            "send": True,
        }
        try:
            response = await self._http.post(
                "receipts",
                json=body,
                headers={IDEMPOTENCE_KEY_HEADER: idempotency_key},
            )
            response.raise_for_status()
            payload = response.json()
            _log.info(
                "yookassa_create_receipt_ok",
                receipt_id=payload["id"],
                status=payload.get("status"),
                kind=kind,
                # NO customer_email in logs — PII discipline (Threat T-51-03-01).
            )
            return YooKassaReceiptResult(
                ok=True,
                classification="ok",
                receipt_id=payload["id"],
            )
        except httpx.HTTPStatusError as exc:
            classification, status, error_code = self._classify_http_status_error(exc)
            _log.warning(
                f"yookassa_create_receipt_{classification}",
                http_status=status,
                error_code=error_code,
                kind=kind,
            )
            return YooKassaReceiptResult(
                ok=False,
                classification=classification,
                http_status=status,
                error_code=error_code,
                error=str(exc),
            )
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            _log.warning(
                "yookassa_create_receipt_transient_error",
                reason=type(exc).__name__,
                kind=kind,
            )
            return YooKassaReceiptResult(
                ok=False,
                classification="transient_error",
                error=str(exc),
            )
        except json.JSONDecodeError as exc:
            _log.warning(
                "yookassa_create_receipt_permanent_error",
                reason="malformed_json",
                kind=kind,
            )
            return YooKassaReceiptResult(
                ok=False,
                classification="permanent_error",
                error=str(exc),
            )
        except Exception as exc:  # outbound boundary — classify all transport failures
            _log.warning(
                "yookassa_create_receipt_transient_error",
                reason=type(exc).__name__,
                kind=kind,
            )
            return YooKassaReceiptResult(
                ok=False,
                classification="transient_error",
                error=str(exc),
            )

    async def get_refund(self, refund_id: str) -> YooKassaRefundResult:
        """GET /v3/refunds/{id} — read-only, idempotent by HTTP semantics.

        No ``Idempotence-Key`` header; ``idempotency_key`` is ``None`` on
        the returned result variants.
        """
        try:
            response = await self._http.get(f"refunds/{refund_id}")
            response.raise_for_status()
            payload = response.json()
            _log.info(
                "yookassa_get_refund_ok",
                refund_id=payload["id"],
                payment_id=payload["payment_id"],
                status=payload["status"],
            )
            return YooKassaRefundResult(
                ok=True,
                classification="ok",
                refund_id=payload["id"],
                payment_id=payload["payment_id"],
                status=payload["status"],
                amount_kopecks=yookassa_to_kopecks(payload["amount"]["value"]),
                idempotency_key=None,
            )
        except httpx.HTTPStatusError as exc:
            classification, status, error_code = self._classify_http_status_error(exc)
            _log.warning(
                f"yookassa_get_refund_{classification}",
                http_status=status,
                error_code=error_code,
            )
            return YooKassaRefundResult(
                ok=False,
                classification=classification,
                http_status=status,
                error_code=error_code,
                idempotency_key=None,
                error=str(exc),
            )
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            _log.warning(
                "yookassa_get_refund_transient_error",
                reason=type(exc).__name__,
            )
            return YooKassaRefundResult(
                ok=False,
                classification="transient_error",
                idempotency_key=None,
                error=str(exc),
            )
        except json.JSONDecodeError as exc:
            _log.warning(
                "yookassa_get_refund_permanent_error",
                reason="malformed_json",
            )
            return YooKassaRefundResult(
                ok=False,
                classification="permanent_error",
                idempotency_key=None,
                error=str(exc),
            )
        except Exception as exc:
            _log.warning(
                "yookassa_get_refund_transient_error",
                reason=type(exc).__name__,
            )
            return YooKassaRefundResult(
                ok=False,
                classification="transient_error",
                idempotency_key=None,
                error=str(exc),
            )
