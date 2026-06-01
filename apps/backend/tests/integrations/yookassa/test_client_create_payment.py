"""Phase 49 PAY-05 / BLOCKER #1 — adapter widens for QR + UUID|str + get_payment qr_payload.

Plan 49-01 Task 1 — RED gate. Locks the post-widening contract:

1. ``YooKassaPaymentResult.qr_payload`` field defaults to ``None`` (backward
   compatible with Phase 48 callsites).
2. ``YooKassaClient.create_payment`` accepts ``confirmation_type='qr'`` and
   populates ``qr_payload`` from ``response.confirmation.confirmation_data``.
3. ``YooKassaClient.create_payment`` accepts a string ``idempotency_key``
   (Phase 49 D-49-08 sha256 hex shape) and emits it verbatim in the
   ``Idempotence-Key`` header.
4. ``YooKassaClient.get_payment`` populates ``qr_payload`` when the upstream
   ``confirmation.type == "qr"`` (BLOCKER #1 — Plan 49-03 QR-replay re-fetch
   path depends on this).

These tests reuse fixtures defined in
``apps/backend/tests/integrations/yookassa/conftest.py``.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import httpx
import pytest
import respx
from pydantic import SecretStr

from app.integrations.yookassa.client import IDEMPOTENCE_KEY_HEADER, YooKassaClient
from app.integrations.yookassa.settings import YooKassaSettings
from app.integrations.yookassa.types import YooKassaPaymentResult

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


# ---------- dataclass field default + set --------------------------------------


def test_yookassa_payment_result_qr_payload_field_default_none() -> None:
    """Backward-compat — existing Phase 48 callsites construct without qr_payload."""
    r = YooKassaPaymentResult(ok=True, classification="ok")
    assert r.qr_payload is None


def test_yookassa_payment_result_qr_payload_set() -> None:
    r = YooKassaPaymentResult(ok=True, classification="ok", qr_payload="qr-data-blob")
    assert r.qr_payload == "qr-data-blob"


# ---------- create_payment redirect-default preserved --------------------------


@pytest.mark.asyncio
async def test_create_payment_redirect_default_preserves_existing_contract(
    yookassa_create_payment_success: respx.MockRouter,
) -> None:
    async with httpx.AsyncClient(base_url=_BASE_URL) as http:
        client = YooKassaClient(http=http, settings=_test_settings())
        result = await client.create_payment(**_payment_kwargs())
    assert result.classification == "ok"
    assert result.confirmation_url is not None
    assert result.qr_payload is None


# ---------- create_payment QR branch -------------------------------------------


@pytest.mark.asyncio
async def test_create_payment_qr_returns_payload(
    yookassa_create_payment_qr_success: respx.MockRouter,
) -> None:
    sha256_hex = "a" * 64  # D-49-08 sha256 hex shape
    async with httpx.AsyncClient(base_url=_BASE_URL) as http:
        client = YooKassaClient(http=http, settings=_test_settings())
        result = await client.create_payment(
            **_payment_kwargs(
                idempotency_key=sha256_hex,
                confirmation_type="qr",
            )
        )
    assert result.classification == "ok"
    assert result.qr_payload is not None
    assert result.qr_payload.startswith("DQQkAAEAAvOBpKgAAvSQE")
    assert result.confirmation_url is None


@pytest.mark.asyncio
async def test_create_payment_qr_sends_idempotence_key_verbatim_string(
    yookassa_create_payment_qr_success: respx.MockRouter,
) -> None:
    """D-49-08 — sha256 hex string idempotency_key flows verbatim through the header."""
    sha256_hex = "b" * 64
    route = yookassa_create_payment_qr_success.routes[0]
    async with httpx.AsyncClient(base_url=_BASE_URL) as http:
        client = YooKassaClient(http=http, settings=_test_settings())
        await client.create_payment(
            **_payment_kwargs(
                idempotency_key=sha256_hex,
                confirmation_type="qr",
            )
        )
    request = route.calls.last.request
    assert request.headers[IDEMPOTENCE_KEY_HEADER] == sha256_hex


@pytest.mark.asyncio
async def test_create_payment_accepts_string_idempotency_key_redirect(
    yookassa_create_payment_success: respx.MockRouter,
) -> None:
    """D-49-08 — string idempotency_key under redirect default is wire-compatible."""
    sha256_hex = "c" * 64
    async with httpx.AsyncClient(base_url=_BASE_URL) as http:
        client = YooKassaClient(http=http, settings=_test_settings())
        result = await client.create_payment(**_payment_kwargs(idempotency_key=sha256_hex))
    assert result.classification == "ok"
    # idempotency_key on the result is None because caller used str form, not UUID
    assert result.idempotency_key is None


@pytest.mark.asyncio
async def test_create_payment_qr_422_classifies_validation_error(
    yookassa_create_payment_qr_422: respx.MockRouter,
) -> None:
    sha256_hex = "d" * 64
    async with httpx.AsyncClient(base_url=_BASE_URL) as http:
        client = YooKassaClient(http=http, settings=_test_settings())
        result = await client.create_payment(
            **_payment_kwargs(
                idempotency_key=sha256_hex,
                confirmation_type="qr",
            )
        )
    assert result.classification == "validation_error"
    assert result.http_status == 422
    assert result.qr_payload is None
    # string idempotency_key → result.idempotency_key is None
    assert result.idempotency_key is None


# ---------- error_parameter surfacing (Plan 999.5-06 Task 1) -------------------


@pytest.mark.asyncio
async def test_create_payment_400_idempotence_key_collision_surfaces_parameter() -> None:
    """Plan 999.5-06 — a 400 invalid_request/Idempotence-Key surfaces error_parameter.

    This is the exact ЮKassa envelope returned (PROVEN live in UAT-10) when a
    deterministic day-key is reused with a changed receipt body. The client
    keeps the classification at ``permanent_error`` (the retry decision belongs
    to the service core) but MUST now thread the envelope ``parameter`` through.
    """
    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(
            return_value=httpx.Response(
                400,
                json={
                    "type": "error",
                    "code": "invalid_request",
                    "parameter": "Idempotence-Key",
                    "description": (
                        "You've already used this idempotence key for another "
                        "request within the past 24 hours."
                    ),
                },
            )
        )
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            result = await client.create_payment(**_payment_kwargs())
    assert result.classification == "permanent_error"
    assert result.http_status == 400
    assert result.error_code == "invalid_request"
    assert result.error_parameter == "Idempotence-Key"


@pytest.mark.asyncio
async def test_create_payment_400_without_parameter_yields_none() -> None:
    """Back-compat — a 400 with NO 'parameter' key leaves error_parameter None."""
    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(
            return_value=httpx.Response(
                400,
                json={"type": "error", "code": "invalid_request", "description": "bad"},
            )
        )
        async with httpx.AsyncClient(base_url=_BASE_URL) as http:
            client = YooKassaClient(http=http, settings=_test_settings())
            result = await client.create_payment(**_payment_kwargs())
    assert result.classification == "permanent_error"
    assert result.error_code == "invalid_request"
    assert result.error_parameter is None


@pytest.mark.asyncio
async def test_create_payment_ok_leaves_error_parameter_none(
    yookassa_create_payment_success: respx.MockRouter,
) -> None:
    """A successful create_payment defaults error_parameter to None."""
    async with httpx.AsyncClient(base_url=_BASE_URL) as http:
        client = YooKassaClient(http=http, settings=_test_settings())
        result = await client.create_payment(**_payment_kwargs())
    assert result.classification == "ok"
    assert result.error_parameter is None


# ---------- get_payment QR re-fetch (BLOCKER #1) -------------------------------


@pytest.mark.asyncio
async def test_get_payment_qr_populates_qr_payload(
    yookassa_get_payment_qr_pending: respx.MockRouter,
) -> None:
    """BLOCKER #1 — get_payment must extract confirmation.confirmation_data for QR-type payments."""
    async with httpx.AsyncClient(base_url=_BASE_URL) as http:
        client = YooKassaClient(http=http, settings=_test_settings())
        result = await client.get_payment("29ab1a59-000f-5000-8000-1399cb40ba0e")
    assert result.classification == "ok"
    assert result.qr_payload == "QR_PAYLOAD_REFETCHED"
    assert result.confirmation_url is None
