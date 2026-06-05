"""Phase 84 APAY-02 — YooKassaClient.create_payment off-session extension.

Verifies the Phase 84 off-session branch of create_payment:

1. With payment_method_id set, the POST body contains payment_method_id + capture=True
   and has NO "confirmation" key and NO "save_payment_method" key.
2. Without payment_method_id, the POST body is byte-identical to the existing redirect
   path (contains a "confirmation" block with type="redirect").
3. A 4xx provider decline for an off-session payment returns classification
   "permanent_error" (or the mapped value) without raising.

Respx mocking pattern mirrors tests/integrations/yookassa/test_client_create_payment.py.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx
from pydantic import SecretStr

from app.integrations.yookassa.client import IDEMPOTENCE_KEY_HEADER, YooKassaClient
from app.integrations.yookassa.settings import YooKassaSettings

_BASE_URL = "https://api.yookassa.ru/v3/"
_RETURN_URL = "https://example.com/return"

_SUCCEEDED_RESPONSE = {
    "id": "30000000-0000-5000-8000-000000000001",
    "status": "succeeded",
    "amount": {"value": "1990.00", "currency": "RUB"},
    "description": "Автопродление абонемента",
    "recipient": {"account_id": "123456", "gateway_id": "gw-test-001"},
    "payment_method": {
        "type": "bank_card",
        "id": "saved-method-id-abc",
        "saved": True,
    },
    "created_at": "2026-06-05T02:00:00.000Z",
    "paid": True,
    "refundable": True,
    "metadata": {},
}

_REDIRECT_SUCCESS_RESPONSE = {
    "id": "22e12f66-000f-5000-8000-18db351245c7",
    "status": "pending",
    "amount": {"value": "1990.00", "currency": "RUB"},
    "description": "Месячный абонемент в зал",
    "recipient": {"account_id": "123456", "gateway_id": "gw-test-001"},
    "payment_method": {
        "type": "bank_card",
        "id": "0eda4234-0001-5000-a000-1d8b1d6e5c45",
        "saved": False,
    },
    "created_at": "2026-05-21T10:00:00.000Z",
    "confirmation": {
        "type": "redirect",
        "return_url": _RETURN_URL,
        "confirmation_url": (
            "https://yoomoney.ru/checkout/payments/v2/contract"
            "?orderId=22e12f66-000f-5000-8000-18db351245c7"
        ),
    },
    "test": False,
    "paid": False,
    "refundable": False,
    "metadata": {},
}


def _test_settings() -> YooKassaSettings:
    return YooKassaSettings(
        shop_id=123456,
        secret_key=SecretStr("test_secret"),
        return_url=_RETURN_URL,  # type: ignore[arg-type]
        tax_system_code=1,
        default_vat_code=1,
        sandbox=False,
    )


def _base_kwargs(**overrides: Any) -> dict[str, Any]:
    """Common kwargs for create_payment (no payment_method_id by default)."""
    kwargs: dict[str, Any] = {
        "amount_kopecks": 199_000,
        "description": "Автопродление абонемента",
        "receipt_items": [
            {
                "description": "Месячный абонемент",
                "quantity": "1.00",
                "amount": {"value": "1990.00", "currency": "RUB"},
                "vat_code": 1,
                "payment_mode": "full_prepayment",
                "payment_subject": "service",
            }
        ],
        "customer_phone": "+79991234567",
        "idempotency_key": "a" * 64,  # deterministic sha256 hex shape (D-49-08)
    }
    kwargs.update(overrides)
    return kwargs


# ---------------------------------------------------------------------------
# 1. Off-session body: payment_method_id set → no confirmation key
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_off_session_body_has_payment_method_id_and_capture_no_confirmation() -> None:
    """With payment_method_id set, POST body must have payment_method_id + capture=True,
    no 'confirmation' key, and no 'save_payment_method' key (T-84-03)."""
    method_id = "saved-method-id-abc"
    captured_body: dict[str, Any] = {}

    def _capture_body(request: httpx.Request) -> httpx.Response:
        nonlocal captured_body
        captured_body = json.loads(request.content)
        return httpx.Response(200, json=_SUCCEEDED_RESPONSE)

    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(side_effect=_capture_body)
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            result = await client.create_payment(**_base_kwargs(payment_method_id=method_id))

    assert result.classification == "ok"
    assert captured_body.get("payment_method_id") == method_id, (
        "off-session body must include payment_method_id"
    )
    assert captured_body.get("capture") is True, "off-session body must have capture=True"
    assert "confirmation" not in captured_body, (
        "off-session body must NOT have a 'confirmation' key"
    )
    assert "save_payment_method" not in captured_body, (
        "off-session body must NOT have 'save_payment_method' key"
    )


@pytest.mark.asyncio
async def test_off_session_idempotence_key_sent_verbatim() -> None:
    """The Idempotence-Key header (ONE 't' — D-48-12) carries str(idempotency_key) verbatim."""
    idem_key = "b" * 64  # deterministic sha256 hex

    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as router:
        route = router.post("payments").mock(
            return_value=httpx.Response(200, json=_SUCCEEDED_RESPONSE)
        )
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            await client.create_payment(
                **_base_kwargs(idempotency_key=idem_key, payment_method_id="saved-id")
            )

    # Use route.calls.last.request.headers (case-insensitive Headers object)
    # per test_client_create_payment.py D-49-08 pattern.
    assert route.calls.last.request.headers[IDEMPOTENCE_KEY_HEADER] == idem_key, (
        "Idempotence-Key header must carry the caller's key verbatim"
    )


# ---------------------------------------------------------------------------
# 2. Existing redirect path unchanged (byte-identical)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redirect_body_unchanged_when_no_payment_method_id() -> None:
    """Without payment_method_id, POST body must contain a 'confirmation' block
    with type='redirect' — existing interactive checkout path is byte-identical."""
    captured_body: dict[str, Any] = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        nonlocal captured_body
        captured_body = json.loads(request.content)
        return httpx.Response(200, json=_REDIRECT_SUCCESS_RESPONSE)

    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(side_effect=_capture)
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            result = await client.create_payment(
                **_base_kwargs(customer_phone=None, customer_email="test@example.com")
            )

    assert result.classification == "ok"
    assert "confirmation" in captured_body, "redirect body must contain a 'confirmation' key"
    assert captured_body["confirmation"]["type"] == "redirect"
    assert "payment_method_id" not in captured_body, (
        "redirect body must NOT have 'payment_method_id'"
    )


# ---------------------------------------------------------------------------
# 3. 4xx decline for off-session returns classification without raising
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_off_session_decline_returns_classification_not_raises() -> None:
    """A 4xx provider decline (e.g. 422 insufficient_funds) for an off-session charge
    must return a YooKassaPaymentResult with classification != 'ok' and never re-raise."""
    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(
            return_value=httpx.Response(
                422,
                json={
                    "type": "error",
                    "id": "decline-id",
                    "code": "insufficient_funds",
                    "description": "Insufficient funds",
                },
            )
        )
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            result = await client.create_payment(
                **_base_kwargs(payment_method_id="saved-method-id")
            )

    assert result.classification != "ok", "a 4xx decline must return a non-ok classification"
    assert result.ok is False
    assert result.error_code == "insufficient_funds"


@pytest.mark.asyncio
async def test_off_session_decline_401_returns_permanent_error() -> None:
    """A 401 response (invalid credentials) classifies as 'permanent_error'."""
    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(
            return_value=httpx.Response(
                401,
                json={
                    "type": "error",
                    "code": "invalid_credentials",
                    "description": "Invalid credentials",
                },
            )
        )
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            result = await client.create_payment(
                **_base_kwargs(payment_method_id="saved-method-id")
            )

    assert result.classification == "permanent_error"
    assert result.ok is False
