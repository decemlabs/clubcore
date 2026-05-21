"""ЮKassa transport DTOs — locked at Phase 48 D-48-03 (4 frozen dataclasses)
+ D-48-04 (closed Literal classification taxonomy) + D-48-05 (no SDK types
cross the boundary).

Four frozen dataclasses form the entire typed surface of the ЮKassa
transport boundary:

- ``YooKassaPaymentResult`` is the typed outcome of ``create_payment`` /
  ``get_payment`` calls. Its ``classification`` is a closed ``Literal`` so
  downstream code (orchestrator dispatch, ARQ retry, audit row insertion)
  can switch on it without runtime guards leaking free-form strings into
  the audit chain (D-48-04).
- ``YooKassaRefundResult`` mirrors the payment shape for ``create_refund`` /
  ``get_refund`` outcomes. The refund FSM omits ``waiting_for_capture``.
- ``YooKassaReceiptResult`` is a placeholder for Phase 51 FISCAL-04
  (``POST /v3/receipts``). Phase 48 ships no client method for receipts;
  the type exists for forward-compat with the wider classification
  taxonomy (D-48-03).
- ``YooKassaWebhookEvent`` is the inbound webhook event parsed by the
  Phase 50 webhook handler. No classification — inbound events are not
  transport results.

Shape mirrors ``app.integrations.email.types.EmailSendResult`` (D-42-13
lineage) but expands the failure taxonomy to four named buckets:
``ok`` / ``validation_error`` (422 — never retry, fix request) /
``transient_error`` (5xx, timeout, network — ARQ retries) /
``permanent_error`` (4xx non-422 — operator alert). The taxonomy diverges
from the email module's ``blocked`` variant because ЮKassa 422 is a
separate concern from recipient-block (D-48-04).

All four dataclasses are cloudpickle-safe (primitives + UUID + datetime
only) for forward-compat with ARQ task enqueue. Transport errors are
values, not exceptions, so handler atomicity is observable without
try/except gymnastics.

No SDK types cross the boundary — this module never imports from
``yookassa.*`` or ``aioyookassa.*``.

Layer invariant: lives at integrations layer — MUST NOT import from
app.modules.* (importlinter contract integrations-not-depend-on-modules).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID


@dataclass(frozen=True)
class YooKassaPaymentResult:
    """Outcome of one ``POST /v3/payments`` or ``GET /v3/payments/{id}`` attempt (D-48-03/04).

    ``classification`` is the closed taxonomy the orchestrator switches on:

    - ``ok``: provider accepted (2xx). ``payment_id`` / ``status`` /
      ``confirmation_url`` / ``amount_kopecks`` are populated; ``error`` is None.
    - ``validation_error``: provider returned 422. Request was malformed
      (e.g. ``invalid_credentials``, ``parameter_required``). DO NOT retry
      — fix the request.
    - ``transient_error``: provider returned 5xx / network failure / timeout.
      ARQ should retry per its backoff schedule.
    - ``permanent_error``: provider returned 4xx other than 422 (e.g. 401,
      403, 404). DO NOT retry — operator alert.

    Failure variants carry ``error_code`` + ``http_status`` for forensic
    audit; the ``error`` string preserves the upstream message.
    """

    ok: bool
    classification: Literal["ok", "validation_error", "transient_error", "permanent_error"]
    payment_id: str | None = None
    status: Literal["pending", "waiting_for_capture", "succeeded", "canceled"] | None = None
    confirmation_url: str | None = None
    amount_kopecks: int | None = None
    idempotency_key: UUID | None = None
    error_code: str | None = None
    http_status: int | None = None
    error: str | None = None


@dataclass(frozen=True)
class YooKassaRefundResult:
    """Outcome of one ``POST /v3/refunds`` or ``GET /v3/refunds/{id}`` attempt (D-48-03/04).

    Mirrors ``YooKassaPaymentResult`` shape and classification taxonomy.
    The refund FSM omits ``waiting_for_capture`` per ЮKassa API — refunds
    transition directly from ``pending`` to ``succeeded`` / ``canceled``.

    ``payment_id`` is the parent payment the refund applies to; populated
    on success so the orchestrator can join the refund row against the
    originating ``online_payments`` row without re-fetching the payment.
    """

    ok: bool
    classification: Literal["ok", "validation_error", "transient_error", "permanent_error"]
    refund_id: str | None = None
    payment_id: str | None = None
    status: Literal["pending", "succeeded", "canceled"] | None = None
    amount_kopecks: int | None = None
    idempotency_key: UUID | None = None
    error_code: str | None = None
    http_status: int | None = None
    error: str | None = None


@dataclass(frozen=True)
class YooKassaReceiptResult:
    """Placeholder for Phase 51 FISCAL-04 (``POST /v3/receipts``).

    Phase 48 ships no client method for receipts — the type exists for
    forward-compat with the wider classification taxonomy. Phase 51 will
    populate ``receipt_id`` on success and route failure variants through
    the same retry/alert disposition as payments/refunds.
    """

    ok: bool
    classification: Literal["ok", "validation_error", "transient_error", "permanent_error"]
    receipt_id: str | None = None
    error_code: str | None = None
    http_status: int | None = None
    error: str | None = None


@dataclass(frozen=True)
class YooKassaWebhookEvent:
    """Inbound webhook event parsed by Phase 50 webhook handler (D-48-03).

    ``object_payload`` is kept as ``dict[str, Any]`` because the inner
    ЮKassa object varies per event type; the Phase 50 handler performs
    the typed re-fetch via ``GET /v3/payments/{id}`` before any FSM
    transition (Pitfall 1 prevention — never trust webhook body content).

    No ``classification`` field: inbound events are not transport results.
    """

    event: Literal["payment.succeeded", "payment.canceled", "refund.succeeded"]
    object_id: UUID
    object_payload: dict[str, Any]
    received_at: datetime
    correlation_id: UUID | None = None
