"""ЮKassa adapter test fixtures — Phase 48 ADAPTER-06 (D-48-22..24).

Six canonical fixtures + one dict fixture covering the wire shapes Phase 48's
test_client / test_factory and all Phase 49/50/51 downstream tests reuse.

JSON response bodies live in ``_responses/<name>.json`` so docs-driven shape
updates do not churn Python code (D-48-23).

Fixture index (D-48-22 + Phase 49 PAY-05 / BLOCKER #1):
    1. yookassa_create_payment_success    — POST /payments → 200 pending + confirmation_url
    2. yookassa_create_payment_422        — POST /payments → 422 validation error
    3. yookassa_get_payment_pending       — GET /payments/{id} → 200 pending
    4. yookassa_get_payment_succeeded     — GET /payments/{id} → 200 succeeded
    5. yookassa_create_refund_success     — POST /refunds → 200 succeeded
    6. yookassa_webhook_payload           — NOT a respx route — plain dict (Phase 50 webhook tests)
    7. yookassa_create_payment_qr_success — POST /payments → 200 + confirmation_data (PAY-05)
    8. yookassa_create_payment_qr_422     — POST /payments → 422 (QR branch, PAY-05)
    9. yookassa_get_payment_qr_pending    — GET /payments/{id} → 200 QR-style (BLOCKER #1)
"""
from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

_RESPONSES_DIR: Path = Path(__file__).parent / "_responses"
_YOOKASSA_BASE_URL: str = "https://api.yookassa.ru/v3/"


def _load(name: str) -> dict[str, Any]:
    """Load and parse one of the canonical _responses/<name>.json files."""
    path = _RESPONSES_DIR / f"{name}.json"
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


@pytest.fixture
def yookassa_create_payment_success() -> Generator[respx.MockRouter, None, None]:
    """D-48-22 #1 — POST /v3/payments → 200 with status:pending + confirmation_url."""
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(
            return_value=httpx.Response(200, json=_load("create_payment_success"))
        )
        yield router


@pytest.fixture
def yookassa_create_payment_422() -> Generator[respx.MockRouter, None, None]:
    """D-48-22 #2 — POST /v3/payments → 422 validation error (ЮKassa error body shape)."""
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(
            return_value=httpx.Response(422, json=_load("create_payment_422"))
        )
        yield router


@pytest.fixture
def yookassa_create_payment_qr_success() -> Generator[respx.MockRouter, None, None]:
    """Phase 49 PAY-05 — POST /v3/payments with confirmation_type='qr' returns confirmation_data.

    Mirrors yookassa_create_payment_success (D-48-22 #1) but for the QR branch
    introduced by Plan 49-01. The QR body shape comes from the ЮKassa API spec
    for QR-confirmation payments: ``confirmation.type == "qr"`` +
    ``confirmation.confirmation_data == <base64-blob>``.
    """
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "29ab1a59-000f-5000-8000-1399cb40ba0e",
                    "status": "pending",
                    "amount": {"value": "100.00", "currency": "RUB"},
                    "confirmation": {
                        "type": "qr",
                        "confirmation_data": "DQQkAAEAAvOBpKgAAvSQE...QR_PAYLOAD",
                    },
                },
            )
        )
        yield router


@pytest.fixture
def yookassa_create_payment_qr_422() -> Generator[respx.MockRouter, None, None]:
    """Phase 49 PAY-05 — POST /v3/payments with confirmation_type='qr' returns 422."""
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(
            return_value=httpx.Response(
                422,
                json={
                    "type": "error",
                    "code": "invalid_request",
                    "description": "invalid",
                },
            )
        )
        yield router


@pytest.fixture
def yookassa_get_payment_qr_pending() -> Generator[respx.MockRouter, None, None]:
    """Phase 49 BLOCKER #1 — GET /v3/payments/{id} returns a QR-style pending payment.

    Drives the Plan 49-03 service-layer QR-replay re-fetch path test
    (test_replay_qr_sale_refetches_and_returns_qr_payload). Without this
    fixture the QR-replay path cannot be unit-tested without a live ЮKassa
    sandbox.
    """
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.get(url__regex=r"^https://api\.yookassa\.ru/v3/payments/[\w-]+$").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "29ab1a59-000f-5000-8000-1399cb40ba0e",
                    "status": "pending",
                    "amount": {"value": "100.00", "currency": "RUB"},
                    "confirmation": {
                        "type": "qr",
                        "confirmation_data": "QR_PAYLOAD_REFETCHED",
                    },
                },
            )
        )
        yield router


@pytest.fixture
def yookassa_get_payment_pending() -> Generator[respx.MockRouter, None, None]:
    """D-48-22 #3 — GET /v3/payments/{id} → 200 with status:pending."""
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        # respx matches the path regex; use a permissive pattern so any UUID suffix matches.
        router.get(url__regex=r"^https://api\.yookassa\.ru/v3/payments/[\w-]+$").mock(
            return_value=httpx.Response(200, json=_load("get_payment_pending"))
        )
        yield router


@pytest.fixture
def yookassa_get_payment_succeeded() -> Generator[respx.MockRouter, None, None]:
    """D-48-22 #4 — GET /v3/payments/{id} → 200 succeeded + receipt_registration:succeeded."""
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.get(url__regex=r"^https://api\.yookassa\.ru/v3/payments/[\w-]+$").mock(
            return_value=httpx.Response(200, json=_load("get_payment_succeeded"))
        )
        yield router


@pytest.fixture
def yookassa_create_refund_success() -> Generator[respx.MockRouter, None, None]:
    """D-48-22 #5 — POST /v3/refunds → 200 refund body."""
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.post("refunds").mock(
            return_value=httpx.Response(200, json=_load("create_refund_success"))
        )
        yield router


@pytest.fixture
def yookassa_webhook_payload() -> dict[str, Any]:
    """D-48-22 #6 — Canonical payment.succeeded webhook body.

    NOT a respx route — this is a plain dict that Phase 50 webhook tests
    ``request.json()`` after sending it as the POST body. Returned directly
    (no yield, no respx.mock).
    """
    return _load("webhook_payment_succeeded")
