"""Unit tests for ``app.integrations.yookassa.types``.

Plan 48-01 Task 3: locks the four frozen-dataclass DTOs that form the
typed surface of the ЮKassa transport boundary (D-48-03/04/05). The
closed Literal classification taxonomy is verified at compile time by
mypy --strict; these tests cover instantiation + immutability + the
deliberate absence of ``classification`` on ``YooKassaWebhookEvent``
(inbound events are not transport results).
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.integrations.yookassa.types import (
    YooKassaPaymentResult,
    YooKassaReceiptResult,
    YooKassaRefundResult,
    YooKassaWebhookEvent,
)


def test_payment_result_success_instantiates() -> None:
    key = uuid4()
    result = YooKassaPaymentResult(
        ok=True,
        classification="ok",
        payment_id="22e12f66-000f-5000-8000-18db351245c7",
        status="pending",
        confirmation_url="https://yoomoney.ru/checkout/payments/v2/contract/...",
        amount_kopecks=199_000,
        idempotency_key=key,
    )
    assert result.ok is True
    assert result.classification == "ok"
    assert result.amount_kopecks == 199_000
    assert result.idempotency_key == key


def test_payment_result_failure_carries_error_code_and_http_status() -> None:
    result = YooKassaPaymentResult(
        ok=False,
        classification="validation_error",
        error_code="invalid_credentials",
        http_status=422,
        error="Invalid credentials",
    )
    assert result.ok is False
    assert result.classification == "validation_error"
    assert result.http_status == 422
    assert result.error_code == "invalid_credentials"


def test_payment_result_is_frozen() -> None:
    result = YooKassaPaymentResult(ok=True, classification="ok", payment_id="p_1")
    with pytest.raises(FrozenInstanceError):
        result.payment_id = "p_2"  # type: ignore[misc]


def test_refund_result_success_instantiates() -> None:
    result = YooKassaRefundResult(
        ok=True,
        classification="ok",
        refund_id="r_1",
        payment_id="p_1",
        status="succeeded",
        amount_kopecks=19_900,
    )
    assert result.classification == "ok"
    assert result.status == "succeeded"
    assert result.amount_kopecks == 19_900


def test_refund_result_is_frozen() -> None:
    result = YooKassaRefundResult(ok=True, classification="ok", refund_id="r_1")
    with pytest.raises(FrozenInstanceError):
        result.refund_id = "r_2"  # type: ignore[misc]


def test_receipt_result_placeholder_instantiates() -> None:
    result = YooKassaReceiptResult(ok=True, classification="ok", receipt_id="rec_123")
    assert result.classification == "ok"
    assert result.receipt_id == "rec_123"


def test_webhook_event_instantiates() -> None:
    obj_id = uuid4()
    event = YooKassaWebhookEvent(
        event="payment.succeeded",
        object_id=obj_id,
        object_payload={"id": str(obj_id), "status": "succeeded"},
        received_at=datetime.now(tz=UTC),
    )
    assert event.event == "payment.succeeded"
    assert event.object_id == obj_id
    assert event.object_payload["status"] == "succeeded"


def test_webhook_event_is_frozen() -> None:
    event = YooKassaWebhookEvent(
        event="payment.succeeded",
        object_id=uuid4(),
        object_payload={},
        received_at=datetime.now(tz=UTC),
    )
    with pytest.raises(FrozenInstanceError):
        event.event = "payment.canceled"  # type: ignore[misc]


def test_webhook_event_has_no_classification_field() -> None:
    event = YooKassaWebhookEvent(
        event="payment.succeeded",
        object_id=uuid4(),
        object_payload={},
        received_at=datetime.now(tz=UTC),
    )
    assert not hasattr(event, "classification")
