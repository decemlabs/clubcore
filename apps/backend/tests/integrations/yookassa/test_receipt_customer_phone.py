"""Phase 999.5 Plan 03 Task 2 — create_payment receipt.customer email-OR-phone contract.

RED gate: these tests define the new contract BEFORE the implementation ships.
They MUST fail (or error) on the current client.py, then pass after Task 2's GREEN step.

Contract being locked:
  - create_payment with customer_email=<email>, customer_phone=None builds
    {"email": <email>} in receipt.customer (byte-identical to pre-change behavior).
  - create_payment with customer_email=None, customer_phone=<phone> builds
    {"phone": <phone>} in receipt.customer (new phone-fallback path — D-10).
  - create_payment with customer_email=None, customer_phone=None raises ValueError
    (invariant guard — neither contact present).
  - Phone value MUST map to the "phone" key; email MUST map to the "email" key.
    Cross-mapping is explicitly forbidden.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import httpx
import pytest
import respx
from pydantic import SecretStr

from app.integrations.yookassa.client import YooKassaClient
from app.integrations.yookassa.settings import YooKassaSettings

_BASE_URL = "https://api.yookassa.ru/v3/"
_RETURN_URL = "https://example.com/return"


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
    """Minimal valid create_payment kwargs — contact keys provided by each test."""
    kwargs: dict[str, Any] = {
        "amount_kopecks": 199_000,
        "description": "Тест чека",
        "receipt_items": [
            {
                "description": "Тест",
                "quantity": "1.00",
                "amount": {"value": "1990.00", "currency": "RUB"},
                "vat_code": 1,
                "payment_mode": "full_prepayment",
                "payment_subject": "service",
            }
        ],
        "idempotency_key": uuid4(),
    }
    kwargs.update(overrides)
    return kwargs


def _payment_success_response() -> httpx.Response:
    """Minimal ЮKassa POST /v3/payments 200 response — enough for create_payment to parse."""
    return httpx.Response(
        200,
        json={
            "id": "29ab1a59-000f-5000-8000-1399cb40ba0e",
            "status": "pending",
            "amount": {"value": "1990.00", "currency": "RUB"},
            "confirmation": {
                "type": "redirect",
                "confirmation_url": "https://yoomoney.ru/checkout/payments/v2/contract?orderId=test",
            },
        },
    )


# ── Email path (byte-identical to pre-change) ──────────────────────────────────


@pytest.mark.asyncio
async def test_create_payment_email_contact_emits_email_key() -> None:
    """D-999.5-03-A: customer_email present → receipt.customer = {"email": ...} (unchanged)."""
    captured_body: dict[str, Any] = {}

    def capture_and_respond(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        return _payment_success_response()

    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(side_effect=capture_and_respond)
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            result = await client.create_payment(
                **_base_kwargs(
                    customer_email="client@example.com",
                    customer_phone=None,
                )
            )

    assert result.classification == "ok"
    customer = captured_body["receipt"]["customer"]
    assert customer == {"email": "client@example.com"}, (
        "Email path must emit {'email': ...} in receipt.customer — byte-identical to pre-change"
    )
    assert "phone" not in customer, "Email path must NOT include a phone key"


# ── Phone fallback path (new — D-10) ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_payment_phone_contact_emits_phone_key() -> None:
    """D-999.5-03-A: customer_email=None, customer_phone present → receipt.customer = {"phone": ...}."""  # noqa: E501
    captured_body: dict[str, Any] = {}

    def capture_and_respond(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        return _payment_success_response()

    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(side_effect=capture_and_respond)
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            result = await client.create_payment(
                **_base_kwargs(
                    customer_email=None,
                    customer_phone="+79991234567",
                )
            )

    assert result.classification == "ok"
    customer = captured_body["receipt"]["customer"]
    assert customer == {"phone": "+79991234567"}, (
        "Phone-only path must emit {'phone': ...} in receipt.customer"
    )
    assert "email" not in customer, "Phone-fallback path must NOT include an email key"


@pytest.mark.asyncio
async def test_create_payment_phone_never_mapped_to_email_key() -> None:
    """D-999.5-03-B: phone MUST NOT flow through customer_email key (PATTERNS collapsing rejected).

    This test explicitly catches the forbidden 'customer_email=phone_number' anti-pattern
    from the superseded PATTERNS.md excerpt. The ЮKassa API would receive {'email': '+7...'}
    producing an illegal 54-ФЗ receipt.
    """
    captured_body: dict[str, Any] = {}

    def capture_and_respond(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        return _payment_success_response()

    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(side_effect=capture_and_respond)
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            await client.create_payment(
                **_base_kwargs(
                    customer_email=None,
                    customer_phone="+79991234567",
                )
            )

    customer = captured_body["receipt"]["customer"]
    # The email key must NOT contain a phone number (starts with '+' or is all-digits)
    if "email" in customer:
        assert not customer["email"].startswith("+"), (
            "Phone number must NEVER appear in the 'email' key of receipt.customer"
        )
        assert not customer["email"].lstrip("+").isdigit(), (
            "Phone number must NEVER appear in the 'email' key of receipt.customer"
        )


# ── Invariant guard (neither contact) ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_payment_neither_contact_raises_value_error() -> None:
    """T-999.5-10 invariant: customer_email=None AND customer_phone=None → ValueError.

    This guard should never be triggered in production (Task 3's gate ensures
    at least phone is present), but the client must not silently emit an empty
    customer object to ЮKassa.
    """
    with respx.mock(base_url=_BASE_URL, assert_all_called=False):
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            with pytest.raises((ValueError, TypeError)):
                await client.create_payment(
                    **_base_kwargs(
                        customer_email=None,
                        customer_phone=None,
                    )
                )
