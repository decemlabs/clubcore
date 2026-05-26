"""Unit tests for ``app.integrations.yookassa.client.YooKassaClient``.

Plan 48-02 Task 3: locks the classification chain
(``ok`` / ``validation_error`` / ``transient_error`` / ``permanent_error``)
and the SC1 invariant — ``YooKassaClient`` NEVER re-raises transport errors.
Each failure-path test asserts on the returned ``YooKassaPaymentResult`` /
``YooKassaRefundResult`` value; **none** use ``pytest.raises`` around an
adapter call.

Tests inline the canonical JSON response bodies — the shared
``_responses/*.json`` fixture wiring lands in Plan 48-06.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
import respx
from pydantic import SecretStr

from app.integrations.yookassa.client import IDEMPOTENCE_KEY_HEADER, YooKassaClient
from app.integrations.yookassa.settings import YooKassaSettings

_BASE_URL = "https://api.yookassa.ru/v3/"
_RETURN_URL = "https://example.com/return"


def _test_settings() -> YooKassaSettings:
    """Construct a sandbox-credentialed YooKassaSettings for the test client."""
    return YooKassaSettings(
        shop_id=123456,
        secret_key=SecretStr("test_secret"),
        return_url=_RETURN_URL,  # type: ignore[arg-type]
        tax_system_code=1,
        default_vat_code=1,
        sandbox=False,
    )


def _payment_kwargs(**overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "amount_kopecks": 199_000,
        "description": "Месячный абонемент в зал",
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
        "customer_email": "client@example.com",
        "idempotency_key": uuid4(),
    }
    kwargs.update(overrides)
    return kwargs


_CREATE_PAYMENT_OK_BODY: dict[str, Any] = {
    "id": "22e12f66-000f-5000-8000-18db351245c7",
    "status": "pending",
    "amount": {"value": "1990.00", "currency": "RUB"},
    "confirmation": {
        "type": "redirect",
        "return_url": _RETURN_URL,
        "confirmation_url": "https://yoomoney.ru/checkout/payments/v2/contract?orderId=22e12f66",
    },
}

_CREATE_PAYMENT_422_BODY: dict[str, Any] = {
    "type": "error",
    "code": "invalid_credentials",
    "description": "Authentication failed.",
}

_GET_PAYMENT_OK_BODY: dict[str, Any] = {
    "id": "22e12f66-000f-5000-8000-18db351245c7",
    "status": "succeeded",
    "amount": {"value": "1990.00", "currency": "RUB"},
    "confirmation": {},
}

_CREATE_REFUND_OK_BODY: dict[str, Any] = {
    "id": "44e12f66-1234-5000-8000-aabbccddeeff",
    "payment_id": "9b1f5cf6-1111-5000-8000-2d3b4e5f6789",
    "status": "succeeded",
    "amount": {"value": "1990.00", "currency": "RUB"},
}


# ---------- create_payment classification chain -----------------------------


@pytest.mark.asyncio
async def test_create_payment_ok_returns_ok_classification() -> None:
    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(return_value=httpx.Response(200, json=_CREATE_PAYMENT_OK_BODY))
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            result = await client.create_payment(**_payment_kwargs())
    assert result.classification == "ok"
    assert result.ok is True
    assert result.payment_id == "22e12f66-000f-5000-8000-18db351245c7"
    assert result.status == "pending"
    assert result.amount_kopecks == 199_000
    assert result.confirmation_url is not None
    assert result.confirmation_url.startswith("https://yoomoney.ru/checkout/")


@pytest.mark.asyncio
async def test_create_payment_422_returns_validation_error_no_raise() -> None:
    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(
            return_value=httpx.Response(422, json=_CREATE_PAYMENT_422_BODY)
        )
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            # SC1: NO pytest.raises wrapping — client must classify, not raise.
            result = await client.create_payment(**_payment_kwargs())
    assert result.classification == "validation_error"
    assert result.http_status == 422
    assert result.error_code == "invalid_credentials"
    assert result.ok is False


@pytest.mark.asyncio
async def test_create_payment_500_returns_transient_error() -> None:
    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(return_value=httpx.Response(500, json={}))
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            result = await client.create_payment(**_payment_kwargs())
    assert result.classification == "transient_error"
    assert result.http_status == 500
    assert result.ok is False


@pytest.mark.asyncio
async def test_create_payment_403_returns_permanent_error() -> None:
    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(return_value=httpx.Response(403, json={}))
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            result = await client.create_payment(**_payment_kwargs())
    assert result.classification == "permanent_error"
    assert result.http_status == 403


@pytest.mark.asyncio
async def test_create_payment_timeout_returns_transient_error() -> None:
    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(side_effect=httpx.TimeoutException("timeout"))
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            result = await client.create_payment(**_payment_kwargs())
    assert result.classification == "transient_error"
    assert result.http_status is None


@pytest.mark.asyncio
async def test_create_payment_network_error_returns_transient_error() -> None:
    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(side_effect=httpx.ConnectError("connect failed"))
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            result = await client.create_payment(**_payment_kwargs())
    assert result.classification == "transient_error"


@pytest.mark.asyncio
async def test_create_payment_malformed_json_returns_permanent_error() -> None:
    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(return_value=httpx.Response(200, content=b"not-json"))
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            result = await client.create_payment(**_payment_kwargs())
    assert result.classification == "permanent_error"


# ---------- header + body invariants ----------------------------------------


@pytest.mark.asyncio
async def test_create_payment_sends_idempotence_key_header() -> None:
    fixed_key = UUID("11111111-2222-3333-4444-555555555555")
    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as router:
        route = router.post("payments").mock(
            return_value=httpx.Response(200, json=_CREATE_PAYMENT_OK_BODY)
        )
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            await client.create_payment(**_payment_kwargs(idempotency_key=fixed_key))
        request = route.calls.last.request
    assert request.headers[IDEMPOTENCE_KEY_HEADER] == str(fixed_key)
    # Defensive: the standards-conformant double-t spelling MUST NOT be present.
    assert "Idempotency-Key" not in request.headers


@pytest.mark.asyncio
async def test_create_payment_injects_confirmation_return_url() -> None:
    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as router:
        route = router.post("payments").mock(
            return_value=httpx.Response(200, json=_CREATE_PAYMENT_OK_BODY)
        )
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            await client.create_payment(**_payment_kwargs())
        body = json.loads(route.calls.last.request.content)
    assert body["confirmation"]["type"] == "redirect"
    # W-1: Pydantic v2 AnyHttpUrl appends trailing slash; rstrip absorbs.
    assert body["confirmation"]["return_url"].rstrip("/") == _RETURN_URL.rstrip("/")


# ---------- get_payment -----------------------------------------------------


@pytest.mark.asyncio
async def test_get_payment_ok_returns_ok_classification() -> None:
    payment_id = "22e12f66-000f-5000-8000-18db351245c7"
    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as router:
        router.get(url__regex=r"^https://api\.yookassa\.ru/v3/payments/[\w-]+$").mock(
            return_value=httpx.Response(200, json=_GET_PAYMENT_OK_BODY)
        )
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            result = await client.get_payment(payment_id)
    assert result.classification == "ok"
    assert result.status == "succeeded"
    assert result.idempotency_key is None


# ---------- refunds ---------------------------------------------------------


@pytest.mark.asyncio
async def test_create_refund_ok_returns_refund_result() -> None:
    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as router:
        router.post("refunds").mock(return_value=httpx.Response(200, json=_CREATE_REFUND_OK_BODY))
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            result = await client.create_refund(
                payment_id="9b1f5cf6-1111-5000-8000-2d3b4e5f6789",
                amount_kopecks=199_000,
                idempotency_key=uuid4(),
            )
    assert result.classification == "ok"
    assert result.refund_id == "44e12f66-1234-5000-8000-aabbccddeeff"
    assert result.payment_id == "9b1f5cf6-1111-5000-8000-2d3b4e5f6789"
    assert result.status == "succeeded"
    assert result.amount_kopecks == 199_000


@pytest.mark.asyncio
async def test_create_refund_sends_idempotence_key_header() -> None:
    fixed_key = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as router:
        route = router.post("refunds").mock(
            return_value=httpx.Response(200, json=_CREATE_REFUND_OK_BODY)
        )
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            await client.create_refund(
                payment_id="9b1f5cf6-1111-5000-8000-2d3b4e5f6789",
                amount_kopecks=199_000,
                idempotency_key=fixed_key,
            )
        request = route.calls.last.request
    assert request.headers[IDEMPOTENCE_KEY_HEADER] == str(fixed_key)


@pytest.mark.asyncio
async def test_get_refund_ok_returns_refund_result() -> None:
    refund_id = "44e12f66-1234-5000-8000-aabbccddeeff"
    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as router:
        router.get(url__regex=r"^https://api\.yookassa\.ru/v3/refunds/[\w-]+$").mock(
            return_value=httpx.Response(200, json=_CREATE_REFUND_OK_BODY)
        )
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            result = await client.get_refund(refund_id)
    assert result.classification == "ok"
    assert result.refund_id == "44e12f66-1234-5000-8000-aabbccddeeff"
    assert result.payment_id == "9b1f5cf6-1111-5000-8000-2d3b4e5f6789"
    assert result.status == "succeeded"
    assert result.idempotency_key is None


# ---------- aclose ----------------------------------------------------------


@pytest.mark.asyncio
async def test_aclose_closes_http_client() -> None:
    http = httpx.AsyncClient(base_url=_BASE_URL)
    client = YooKassaClient(http=http, settings=_test_settings())
    await client.aclose()
    # After aclose, the underlying httpx.AsyncClient should refuse further requests.
    with pytest.raises(RuntimeError):
        await http.get("payments/whatever")
