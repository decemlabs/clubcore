"""Unit tests for ``YooKassaClient.create_receipt`` — Phase 51 FISCAL-05 / 51-03.

Locks the classification chain mirror of ``create_refund`` for the new
``POST /v3/receipts`` 54-ФЗ fiscalization method:

- ``ok`` / ``validation_error`` / ``transient_error`` / ``permanent_error``
- SC1: NEVER re-raises transport errors — every failure-path test asserts
  on the returned ``YooKassaReceiptResult`` value; **no** ``pytest.raises``
  wraps an adapter call.
- PII discipline (Threat T-51-03-01): ``customer_email`` MUST NOT leak
  into structlog kwargs.
- Idempotence-Key header (D-48-12, ONE 't') carries caller-supplied value.
- ``kind="refund"`` branch routes body field to ``refund_id``.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx
import structlog
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
        tax_system_code=2,
        default_vat_code=1,
        sandbox=False,
    )


def _receipt_kwargs(**overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "payment_id": "9b1f5cf6-1111-5000-8000-2d3b4e5f6789",
        "customer_email": "client@example.ru",
        "items": [
            {
                "description": "Месячный абонемент",
                "quantity": "1.00",
                "amount": {"value": "1990.00", "currency": "RUB"},
                "vat_code": 1,
                "payment_mode": "full_prepayment",
                "payment_subject": "service",
            }
        ],
        "tax_system_code": 2,
        "idempotency_key": "fiscal-receipt-abc123",
    }
    kwargs.update(overrides)
    return kwargs


# ---------- classification chain --------------------------------------------


@pytest.mark.asyncio
async def test_create_receipt_returns_ok_classification_with_receipt_id(
    yookassa_create_receipt_ok: respx.MockRouter,
) -> None:
    async with httpx.AsyncClient(base_url=_BASE_URL) as http:
        client = YooKassaClient(http=http, settings=_test_settings())
        result = await client.create_receipt(**_receipt_kwargs())
    assert result.ok is True
    assert result.classification == "ok"
    assert result.receipt_id == "rcpt_test_001"
    assert result.http_status is None
    assert result.error is None


@pytest.mark.asyncio
async def test_create_receipt_classifies_429_as_permanent_error(
    yookassa_create_receipt_429: respx.MockRouter,
) -> None:
    """Per ``_classify_http_status_error`` (client.py line 130), 4xx other than
    422 (including 429) maps to ``permanent_error``. ЮKassa rate-limit retry
    is the operator's concern, not the ARQ backoff schedule — matches
    create_refund / create_payment classification convention exactly."""
    async with httpx.AsyncClient(base_url=_BASE_URL) as http:
        client = YooKassaClient(http=http, settings=_test_settings())
        # SC1: NO pytest.raises wrapping — client must classify, not raise.
        result = await client.create_receipt(**_receipt_kwargs())
    assert result.ok is False
    assert result.classification == "permanent_error"
    assert result.http_status == 429
    assert result.error_code == "too_many_requests"


@pytest.mark.asyncio
async def test_create_receipt_classifies_500_as_transient_error(
    yookassa_create_receipt_500: respx.MockRouter,
) -> None:
    """Per _classify_http_status_error (client.py line 130), 5xx → transient_error."""
    async with httpx.AsyncClient(base_url=_BASE_URL) as http:
        client = YooKassaClient(http=http, settings=_test_settings())
        result = await client.create_receipt(**_receipt_kwargs())
    assert result.ok is False
    assert result.classification == "transient_error"
    assert result.http_status == 500
    assert result.error_code == "internal_server_error"


@pytest.mark.asyncio
async def test_create_receipt_classifies_422_as_validation_error() -> None:
    """422 → validation_error per the canonical D-48-10 split (permanent path)."""
    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as router:
        router.post("receipts").mock(
            return_value=httpx.Response(
                422,
                json={
                    "type": "error",
                    "code": "invalid_request",
                    "description": "missing tax_system_code",
                },
            )
        )
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            result = await client.create_receipt(**_receipt_kwargs())
    assert result.ok is False
    assert result.classification == "validation_error"
    assert result.http_status == 422
    assert result.error_code == "invalid_request"


@pytest.mark.asyncio
async def test_create_receipt_classifies_403_as_permanent_error() -> None:
    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as router:
        router.post("receipts").mock(return_value=httpx.Response(403, json={}))
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            result = await client.create_receipt(**_receipt_kwargs())
    assert result.ok is False
    assert result.classification == "permanent_error"
    assert result.http_status == 403


@pytest.mark.asyncio
async def test_create_receipt_timeout_returns_transient_error() -> None:
    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as router:
        router.post("receipts").mock(side_effect=httpx.TimeoutException("timeout"))
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            result = await client.create_receipt(**_receipt_kwargs())
    assert result.ok is False
    assert result.classification == "transient_error"
    assert result.http_status is None


# ---------- header + body invariants ----------------------------------------


@pytest.mark.asyncio
async def test_create_receipt_passes_idempotency_key_in_header(
    yookassa_create_receipt_ok: respx.MockRouter,
) -> None:
    """Caller-owned Idempotence-Key (ONE 't' — D-48-12) routes verbatim."""
    fixed_key = "fiscal_receipt_001_hex_abc"
    route = yookassa_create_receipt_ok.routes[0]
    async with httpx.AsyncClient(base_url=_BASE_URL) as http:
        client = YooKassaClient(http=http, settings=_test_settings())
        await client.create_receipt(**_receipt_kwargs(idempotency_key=fixed_key))
    request = route.calls.last.request
    assert request.headers[IDEMPOTENCE_KEY_HEADER] == fixed_key
    # Defensive: the standards-conformant double-t spelling MUST NOT appear.
    assert "Idempotency-Key" not in request.headers


@pytest.mark.asyncio
async def test_create_receipt_kind_refund_uses_refund_id_field_name(
    yookassa_create_receipt_ok: respx.MockRouter,
) -> None:
    """When kind='refund', body uses ``refund_id`` (not ``payment_id``) + ``type='refund'``."""
    route = yookassa_create_receipt_ok.routes[0]
    refund_id = "44e12f66-1234-5000-8000-aabbccddeeff"
    async with httpx.AsyncClient(base_url=_BASE_URL) as http:
        client = YooKassaClient(http=http, settings=_test_settings())
        await client.create_receipt(**_receipt_kwargs(payment_id=refund_id, kind="refund"))
    body = json.loads(route.calls.last.request.content)
    assert body["type"] == "refund"
    assert body["refund_id"] == refund_id
    assert "payment_id" not in body


@pytest.mark.asyncio
async def test_create_receipt_kind_payment_uses_payment_id_field_name(
    yookassa_create_receipt_ok: respx.MockRouter,
) -> None:
    """Default kind='payment' branch — body uses ``payment_id`` and ``type='payment'``."""
    route = yookassa_create_receipt_ok.routes[0]
    async with httpx.AsyncClient(base_url=_BASE_URL) as http:
        client = YooKassaClient(http=http, settings=_test_settings())
        await client.create_receipt(**_receipt_kwargs())
    body = json.loads(route.calls.last.request.content)
    assert body["type"] == "payment"
    assert body["payment_id"] == "9b1f5cf6-1111-5000-8000-2d3b4e5f6789"
    assert "refund_id" not in body
    assert body["customer"]["email"] == "client@example.ru"
    assert body["tax_system_code"] == 2
    assert body["send"] is True


# ---------- email-OR-phone contact (Phase 999.5 Plan 07 / D-10) -------------


@pytest.mark.asyncio
async def test_create_receipt_email_path_posts_customer_email_only(
    yookassa_create_receipt_ok: respx.MockRouter,
) -> None:
    """email present, phone None → body.customer == {"email": ...} (byte-identical to today)."""
    route = yookassa_create_receipt_ok.routes[0]
    async with httpx.AsyncClient(base_url=_BASE_URL) as http:
        client = YooKassaClient(http=http, settings=_test_settings())
        await client.create_receipt(**_receipt_kwargs(customer_email="a@b.ru", customer_phone=None))
    body = json.loads(route.calls.last.request.content)
    assert body["customer"] == {"email": "a@b.ru"}


@pytest.mark.asyncio
async def test_create_receipt_phone_path_posts_customer_phone_only(
    yookassa_create_receipt_ok: respx.MockRouter,
) -> None:
    """phone present, email None → body.customer == {"phone": ...} — never {"email": "+7..."}."""
    route = yookassa_create_receipt_ok.routes[0]
    async with httpx.AsyncClient(base_url=_BASE_URL) as http:
        client = YooKassaClient(http=http, settings=_test_settings())
        await client.create_receipt(
            **_receipt_kwargs(customer_email=None, customer_phone="+79991234567")
        )
    body = json.loads(route.calls.last.request.content)
    assert body["customer"] == {"phone": "+79991234567"}
    assert "email" not in body["customer"]


@pytest.mark.asyncio
async def test_create_receipt_neither_contact_raises_value_error() -> None:
    """Neither email nor phone → ValueError (neither-present invariant, mirrors create_payment)."""
    async with httpx.AsyncClient(base_url=_BASE_URL) as http:
        client = YooKassaClient(http=http, settings=_test_settings())
        with pytest.raises(ValueError, match="customer_email or customer_phone"):
            await client.create_receipt(**_receipt_kwargs(customer_email=None, customer_phone=None))


@pytest.mark.asyncio
async def test_create_receipt_does_not_leak_customer_phone_to_structlog(
    yookassa_create_receipt_ok: respx.MockRouter,
) -> None:
    """customer_phone MUST NOT appear in any structlog event kwarg (T-51-03-01)."""
    leaky_phone = "+79990001122"
    with structlog.testing.capture_logs() as logs:
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            await client.create_receipt(
                **_receipt_kwargs(customer_email=None, customer_phone=leaky_phone)
            )
    for entry in logs:
        for key, value in entry.items():
            assert value != leaky_phone, (
                f"PII leak: customer_phone {leaky_phone!r} appeared in log entry "
                f"{entry!r} under key {key!r}"
            )
        assert "customer_phone" not in entry, (
            f"PII leak: structlog event {entry!r} carries a 'customer_phone' kwarg"
        )


# ---------- PII discipline (Threat T-51-03-01) ------------------------------


@pytest.mark.asyncio
async def test_create_receipt_does_not_leak_customer_email_to_structlog(
    yookassa_create_receipt_ok: respx.MockRouter,
) -> None:
    """customer_email MUST NOT appear in any structlog event kwarg (T-51-03-01)."""
    leaky_email = "leaky-pii@example.ru"
    with structlog.testing.capture_logs() as logs:
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            await client.create_receipt(**_receipt_kwargs(customer_email=leaky_email))
    for entry in logs:
        for key, value in entry.items():
            assert value != leaky_email, (
                f"PII leak: customer_email {leaky_email!r} appeared in log entry "
                f"{entry!r} under key {key!r}"
            )
        assert "customer_email" not in entry, (
            f"PII leak: structlog event {entry!r} carries a 'customer_email' kwarg"
        )


@pytest.mark.asyncio
async def test_create_receipt_failure_path_does_not_leak_customer_email(
    yookassa_create_receipt_500: respx.MockRouter,
) -> None:
    """Failure-path structlog warning MUST also NOT leak customer_email."""
    leaky_email = "leaky-failure-path@example.ru"
    with structlog.testing.capture_logs() as logs:
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            result = await client.create_receipt(**_receipt_kwargs(customer_email=leaky_email))
    assert result.classification == "transient_error"
    for entry in logs:
        for _key, value in entry.items():
            assert value != leaky_email, (
                f"PII leak (failure path): {entry!r} contains {leaky_email!r}"
            )
        assert "customer_email" not in entry
