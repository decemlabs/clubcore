"""HTTP-level integration tests for the 4 POST sell endpoints (Phase 49 PAY-03..06).

Exercises ``/api/v1/online-payments/{memberships,pt-packages}/{plan_id}/{sell,sell-qr}``
end-to-end via the ``httpx.ASGITransport``-backed ``authed_client_*`` fixtures
(CLAUDE.md test convention: no real network). The Phase 48 respx fixtures from
``tests/integrations/yookassa/conftest.py`` are re-exposed into this directory
by ``tests/modules/online_payments/conftest.py`` (shipped by Plan 49-03 — see
the parallel-execution note in SUMMARY.md).

Test surface (12 functions; pytest auto-detects async via ``asyncio_mode='auto'``):
  1.  membership / redirect  → 201 + ``confirmationUrl`` non-null, ``qrPayload`` null
  2.  membership / qr        → 201 + ``qrPayload`` non-null, ``confirmationUrl`` null
  3.  pt-package / redirect  → 201
  4.  pt-package / qr        → 201
  5.  unauthenticated        → 401 BEFORE 403 (RBAC-04 ordering)
  6.  missing CSRF header    → 403 csrf_invalid (Phase 8 D-15 convention)
  7.  missing Idempotency-Key→ 422 idempotency_key_required (Phase 32 PAY-09)
  8.  email-NULL gate        → 422 client_email_required_for_online_payment;
                                no upstream call to ЮKassa (respx call_count == 0)
  9.  ЮKassa 5xx             → 503 yookassa_unavailable
  10. ЮKassa 4xx (non-422)   → 502 yookassa_permanent_error
  11. ЮKassa 422             → 422 yookassa_validation_error
  12. idempotency replay     → identical body returns same envelope verbatim
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from httpx import AsyncClient

ENDPOINT_MEMBERSHIP_REDIRECT = "/api/v1/online-payments/memberships/{plan_id}/sell"
ENDPOINT_MEMBERSHIP_QR = "/api/v1/online-payments/memberships/{plan_id}/sell-qr"
ENDPOINT_PT_REDIRECT = "/api/v1/online-payments/pt-packages/{plan_id}/sell"
ENDPOINT_PT_QR = "/api/v1/online-payments/pt-packages/{plan_id}/sell-qr"


def _csrf_idem_headers(client: AsyncClient) -> dict[str, str]:
    """Standard POST-mutation headers: CSRF token from cookie jar + fresh idempotency key.

    Mirrors ``tests/integration/memberships/test_memberships_crud.py:_csrf_headers``
    — the canonical Sportzal POST helper. The ``X-CSRF-Token`` header is read from
    the ``sportzal_csrf`` cookie set by the login flow; ``Idempotency-Key`` is a
    fresh uuid4 hex per call so the outer-layer Redis dedup never collides across
    tests.
    """
    return {
        "X-CSRF-Token": client.cookies.get("sportzal_csrf") or "",
        "Idempotency-Key": uuid4().hex,
    }


def _unwrap(body: dict[str, Any]) -> dict[str, Any]:
    """ResponseEnvelope unwrap helper — returns ``body['data']`` or raw body."""
    data = body.get("data")
    assert isinstance(data, dict), f"expected envelope with 'data' object; got {body!r}"
    return data


# ─── Happy-path: all 4 endpoints return 201 ─────────────────────────────────


async def test_sell_membership_redirect_201_reception(
    authed_client_reception: AsyncClient,
    make_membership_plan_with_price: Any,
    make_client_with_email: Any,
    yookassa_create_payment_success: Any,
) -> None:
    """PAY-03 happy: reception sells membership in redirect flow → 201 + confirmation_url."""
    plan = await make_membership_plan_with_price()
    client_row = await make_client_with_email()
    response = await authed_client_reception.post(
        ENDPOINT_MEMBERSHIP_REDIRECT.format(plan_id=plan.id),
        json={"clientId": str(client_row.id)},
        headers=_csrf_idem_headers(authed_client_reception),
    )
    assert response.status_code == 201, response.text
    data = _unwrap(response.json())
    assert data["confirmationUrl"] is not None
    assert data["qrPayload"] is None
    assert "onlinePaymentId" in data


async def test_sell_membership_qr_201_owner(
    authed_client_owner: AsyncClient,
    make_membership_plan_with_price: Any,
    make_client_with_email: Any,
    yookassa_create_payment_qr_success: Any,
) -> None:
    """PAY-05 happy: owner sells membership in QR flow → 201 + qr_payload."""
    plan = await make_membership_plan_with_price()
    client_row = await make_client_with_email()
    response = await authed_client_owner.post(
        ENDPOINT_MEMBERSHIP_QR.format(plan_id=plan.id),
        json={"clientId": str(client_row.id)},
        headers=_csrf_idem_headers(authed_client_owner),
    )
    assert response.status_code == 201, response.text
    data = _unwrap(response.json())
    assert data["qrPayload"] is not None
    assert data["confirmationUrl"] is None


async def test_sell_pt_package_redirect_201_reception(
    authed_client_reception: AsyncClient,
    make_pt_package_plan_with_price: Any,
    make_client_with_email: Any,
    yookassa_create_payment_success: Any,
) -> None:
    """PAY-04 happy: reception sells PT-package in redirect flow → 201."""
    plan = await make_pt_package_plan_with_price()
    client_row = await make_client_with_email()
    response = await authed_client_reception.post(
        ENDPOINT_PT_REDIRECT.format(plan_id=plan.id),
        json={"clientId": str(client_row.id)},
        headers=_csrf_idem_headers(authed_client_reception),
    )
    assert response.status_code == 201, response.text
    data = _unwrap(response.json())
    assert data["confirmationUrl"] is not None
    assert data["qrPayload"] is None


async def test_sell_pt_package_qr_201_reception(
    authed_client_reception: AsyncClient,
    make_pt_package_plan_with_price: Any,
    make_client_with_email: Any,
    yookassa_create_payment_qr_success: Any,
) -> None:
    """PAY-05 happy: reception sells PT-package in QR flow → 201 + qr_payload."""
    plan = await make_pt_package_plan_with_price()
    client_row = await make_client_with_email()
    response = await authed_client_reception.post(
        ENDPOINT_PT_QR.format(plan_id=plan.id),
        json={"clientId": str(client_row.id)},
        headers=_csrf_idem_headers(authed_client_reception),
    )
    assert response.status_code == 201, response.text
    data = _unwrap(response.json())
    assert data["qrPayload"] is not None
    assert data["confirmationUrl"] is None


# ─── RBAC-04 ordering — 401 before 403 ──────────────────────────────────────


async def test_sell_membership_401_when_unauthenticated(
    async_client: AsyncClient,
) -> None:
    """RBAC-04 invariant: unauthenticated request fires 401 BEFORE 403/422.

    The order of dependency resolution in the endpoint signature
    (``require_permission`` is first) guarantees the missing session cookie
    is detected before CSRF or idempotency-key validation runs.
    """
    response = await async_client.post(
        ENDPOINT_MEMBERSHIP_REDIRECT.format(plan_id=uuid4()),
        json={"clientId": str(uuid4())},
        # no cookies — no session
        headers={"Idempotency-Key": uuid4().hex},
    )
    assert response.status_code == 401, (
        f"401 must fire BEFORE 403/422 (RBAC-04). Got {response.status_code}: "
        f"{response.text}"
    )


# ─── CSRF + Idempotency-Key gate (Sportzal POST mutation contract) ──────────


async def test_sell_membership_403_when_csrf_missing(
    authed_client_reception: AsyncClient,
    make_membership_plan_with_price: Any,
    make_client_with_email: Any,
) -> None:
    """CSRF gate — missing X-CSRF-Token header → 403 csrf_invalid (Phase 8 D-15)."""
    plan = await make_membership_plan_with_price()
    client_row = await make_client_with_email()
    response = await authed_client_reception.post(
        ENDPOINT_MEMBERSHIP_REDIRECT.format(plan_id=plan.id),
        json={"clientId": str(client_row.id)},
        headers={"Idempotency-Key": uuid4().hex},  # CSRF intentionally omitted
    )
    assert response.status_code == 403, response.text


async def test_sell_membership_422_when_idempotency_key_missing(
    authed_client_reception: AsyncClient,
    make_membership_plan_with_price: Any,
    make_client_with_email: Any,
) -> None:
    """Idempotency-Key gate — missing header → 422 idempotency_key_required (PAY-09)."""
    plan = await make_membership_plan_with_price()
    client_row = await make_client_with_email()
    response = await authed_client_reception.post(
        ENDPOINT_MEMBERSHIP_REDIRECT.format(plan_id=plan.id),
        json={"clientId": str(client_row.id)},
        # CSRF present, Idempotency-Key intentionally omitted
        headers={"X-CSRF-Token": authed_client_reception.cookies.get("sportzal_csrf") or ""},
    )
    assert response.status_code == 422
    body = response.json()
    error_code = body.get("code") or body.get("error", {}).get("code") or body.get("detail")
    assert "idempotency_key_required" in str(error_code), body


# ─── Service-layer error mapping (FIS-05 gate + ЮKassa classification) ──────


async def test_sell_membership_422_when_client_email_null(
    authed_client_reception: AsyncClient,
    make_membership_plan_with_price: Any,
    make_client_no_email: Any,
    yookassa_create_payment_success: Any,  # injected but MUST NOT be called
) -> None:
    """FIS-05 email gate (D-49-12): client.email IS NULL → 422 with locked code.

    The service raises ``ValidationAppError(client_email_required_for_online_payment)``
    BEFORE any ЮKassa call — verified by asserting ``respx.call_count == 0``.
    """
    plan = await make_membership_plan_with_price()
    client_row = await make_client_no_email()
    response = await authed_client_reception.post(
        ENDPOINT_MEMBERSHIP_REDIRECT.format(plan_id=plan.id),
        json={"clientId": str(client_row.id)},
        headers=_csrf_idem_headers(authed_client_reception),
    )
    assert response.status_code == 422
    body = response.json()
    error_code = body.get("code") or body.get("error", {}).get("code") or body.get("detail")
    assert "client_email_required_for_online_payment" in str(error_code), body
    # respx MUST NOT have been called — gate fires before upstream
    assert yookassa_create_payment_success.calls.call_count == 0


async def test_sell_membership_503_on_yookassa_5xx(
    authed_client_reception: AsyncClient,
    make_membership_plan_with_price: Any,
    make_client_with_email: Any,
    yookassa_create_payment_500: Any,
) -> None:
    """ЮKassa transient error (5xx) → 503 yookassa_unavailable (D-49-10)."""
    plan = await make_membership_plan_with_price()
    client_row = await make_client_with_email()
    response = await authed_client_reception.post(
        ENDPOINT_MEMBERSHIP_REDIRECT.format(plan_id=plan.id),
        json={"clientId": str(client_row.id)},
        headers=_csrf_idem_headers(authed_client_reception),
    )
    assert response.status_code == 503, response.text
    body = response.json()
    error_code = body.get("code") or body.get("error", {}).get("code") or body.get("detail")
    assert "yookassa_unavailable" in str(error_code), body


async def test_sell_membership_502_on_yookassa_4xx_non_422(
    authed_client_reception: AsyncClient,
    make_membership_plan_with_price: Any,
    make_client_with_email: Any,
    yookassa_create_payment_404: Any,
) -> None:
    """ЮKassa permanent error (4xx non-422) → 502 yookassa_permanent_error (D-49-10)."""
    plan = await make_membership_plan_with_price()
    client_row = await make_client_with_email()
    response = await authed_client_reception.post(
        ENDPOINT_MEMBERSHIP_REDIRECT.format(plan_id=plan.id),
        json={"clientId": str(client_row.id)},
        headers=_csrf_idem_headers(authed_client_reception),
    )
    assert response.status_code == 502, response.text
    body = response.json()
    error_code = body.get("code") or body.get("error", {}).get("code") or body.get("detail")
    assert "yookassa_permanent_error" in str(error_code), body


async def test_sell_membership_422_on_yookassa_validation_error(
    authed_client_reception: AsyncClient,
    make_membership_plan_with_price: Any,
    make_client_with_email: Any,
    yookassa_create_payment_422: Any,
) -> None:
    """ЮKassa 422 validation_error → 422 yookassa_validation_error (D-49-10)."""
    plan = await make_membership_plan_with_price()
    client_row = await make_client_with_email()
    response = await authed_client_reception.post(
        ENDPOINT_MEMBERSHIP_REDIRECT.format(plan_id=plan.id),
        json={"clientId": str(client_row.id)},
        headers=_csrf_idem_headers(authed_client_reception),
    )
    assert response.status_code == 422
    body = response.json()
    error_code = body.get("code") or body.get("error", {}).get("code") or body.get("detail")
    assert "yookassa_validation_error" in str(error_code), body


# ─── Outer-layer Idempotency-Key replay (D-49-16) ───────────────────────────


async def test_sell_membership_idempotency_replay_returns_same_envelope(
    authed_client_reception: AsyncClient,
    make_membership_plan_with_price: Any,
    make_client_with_email: Any,
    yookassa_create_payment_success: Any,
) -> None:
    """Outer idempotency replay (D-49-16): identical Idempotency-Key + identical
    body returns the cached envelope verbatim — same body bytes, same status.
    """
    plan = await make_membership_plan_with_price()
    client_row = await make_client_with_email()
    payload = {"clientId": str(client_row.id)}
    csrf = authed_client_reception.cookies.get("sportzal_csrf") or ""
    idem_key = uuid4().hex
    headers = {"X-CSRF-Token": csrf, "Idempotency-Key": idem_key}

    first = await authed_client_reception.post(
        ENDPOINT_MEMBERSHIP_REDIRECT.format(plan_id=plan.id),
        json=payload,
        headers=headers,
    )
    assert first.status_code == 201, first.text

    second = await authed_client_reception.post(
        ENDPOINT_MEMBERSHIP_REDIRECT.format(plan_id=plan.id),
        json=payload,
        headers=headers,
    )
    assert second.status_code == 201, second.text
    assert second.content == first.content, "outer-layer replay must be byte-identical"
    # upstream ЮKassa called exactly once across both clicks
    assert yookassa_create_payment_success.calls.call_count == 1
