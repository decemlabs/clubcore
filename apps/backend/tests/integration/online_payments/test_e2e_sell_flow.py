"""Phase 49 Plan 49-07 — end-to-end sell-flow tests (Roadmap SC#1..#5).

Exercises the full HTTP → service → repository → DB → audit chain for the
four POST sell endpoints + the GET /return anti-oracle screen, plus the
three error classifications (validation / transient / permanent) returned by
the ЮKassa adapter.

Roadmap success-criteria mapping (Plan 49-07 must_haves):
    SC#1 — POST membership/sell  → test_e2e_sc1_membership_redirect
                                  → test_e2e_sc1_pt_package_redirect
    SC#2 — POST membership/sell-qr → test_e2e_sc2_membership_qr
                                    → test_e2e_sc2_pt_package_qr
    SC#3 — 422 client_email_required_for_online_payment
                                  → test_e2e_sc3_email_gate_422
    SC#4 — GET /return static screen + constant-time floor
                                  → test_e2e_sc4_return_screen_concurrent_identical_body
    SC#5 — Alembic 0034 + indexes shape post-flow
                                  → test_e2e_sc5_row_satisfies_check_constraints

SC#6 (4 v1.7 Protocol slots non-None) is owned by
``tests/integration/test_v17_protocol_slot_parity.py`` (Plan 49-06) and is
re-verified by the Plan 49-07 Task 3 regression sweep — not duplicated here.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import select

from app.modules.online_payments.models import OnlinePayment

# ─── SC#1 — membership redirect e2e ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_sc1_membership_redirect(
    authed_client_reception,
    db_session,
    make_client_with_email,
    make_membership_plan,
    yookassa_create_payment_success,
) -> None:
    """SC#1 — POST /memberships/{id}/sell returns 201 + confirmation_url; row pending."""
    from tests.integration.online_payments.conftest import sell_headers

    client_row = await make_client_with_email()
    plan = await make_membership_plan()

    response = await authed_client_reception.post(
        f"/api/v1/online-payments/memberships/{plan.id}/sell",
        json={"clientId": str(client_row.id)},
        headers=sell_headers(authed_client_reception),
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["confirmationUrl"] is not None
    assert data["qrPayload"] is None
    online_payment_id = UUID(data["onlinePaymentId"])

    # DB shape
    row = await db_session.scalar(
        select(OnlinePayment).where(OnlinePayment.id == online_payment_id)
    )
    assert row is not None
    assert row.status == "pending"
    assert row.confirmation_type == "redirect"
    assert row.yookassa_payment_id != ""
    assert row.membership_plan_id == plan.id
    assert row.pt_package_plan_id is None
    assert row.client_id == client_row.id


# ─── SC#2 — membership QR e2e ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_sc2_membership_qr(
    authed_client_reception,
    db_session,
    make_client_with_email,
    make_membership_plan,
    yookassa_create_payment_qr_success,
) -> None:
    """SC#2 — POST /memberships/{id}/sell-qr returns qrPayload; row confirmation_type='qr'."""
    from tests.integration.online_payments.conftest import sell_headers

    client_row = await make_client_with_email()
    plan = await make_membership_plan()

    response = await authed_client_reception.post(
        f"/api/v1/online-payments/memberships/{plan.id}/sell-qr",
        json={"clientId": str(client_row.id)},
        headers=sell_headers(authed_client_reception),
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["qrPayload"] is not None
    assert data["confirmationUrl"] is None

    row = await db_session.scalar(
        select(OnlinePayment).where(OnlinePayment.id == UUID(data["onlinePaymentId"]))
    )
    assert row is not None
    assert row.confirmation_type == "qr"
    assert row.confirmation_url is None


# ─── SC#1 — pt-package redirect e2e ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_sc1_pt_package_redirect(
    authed_client_reception,
    db_session,
    make_client_with_email,
    make_pt_package_plan,
    yookassa_create_payment_success,
) -> None:
    """SC#1 — POST /pt-packages/{id}/sell returns 201; row pt_package_plan_id populated."""
    from tests.integration.online_payments.conftest import sell_headers

    client_row = await make_client_with_email()
    plan = await make_pt_package_plan()

    response = await authed_client_reception.post(
        f"/api/v1/online-payments/pt-packages/{plan.id}/sell",
        json={"clientId": str(client_row.id)},
        headers=sell_headers(authed_client_reception),
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]

    row = await db_session.scalar(
        select(OnlinePayment).where(OnlinePayment.id == UUID(data["onlinePaymentId"]))
    )
    assert row is not None
    assert row.pt_package_plan_id == plan.id
    assert row.membership_plan_id is None


# ─── SC#2 — pt-package QR e2e ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_sc2_pt_package_qr(
    authed_client_reception,
    db_session,
    make_client_with_email,
    make_pt_package_plan,
    yookassa_create_payment_qr_success,
) -> None:
    """SC#2 — POST /pt-packages/{id}/sell-qr returns qrPayload."""
    from tests.integration.online_payments.conftest import sell_headers

    client_row = await make_client_with_email()
    plan = await make_pt_package_plan()

    response = await authed_client_reception.post(
        f"/api/v1/online-payments/pt-packages/{plan.id}/sell-qr",
        json={"clientId": str(client_row.id)},
        headers=sell_headers(authed_client_reception),
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["qrPayload"] is not None


# ─── SC#3 — locked email-gate code ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_sc3_phone_only_client_proceeds_d10(
    authed_client_reception,
    db_session,
    make_client_no_email,
    make_membership_plan,
    yookassa_create_payment_success,
) -> None:
    """SC#3 (D-10 / Phase 999.5) — email-less client with phone → 201, DB row inserted.

    Pre-D-10 (D-49-12): 422 with client_email_required_for_online_payment.
    Post-D-10: phone-only client proceeds; receipt goes to phone (54-ФЗ fallback).
    Since clients.phone is NOT NULL (OTP auth invariant), the gate effectively never blocks.
    """
    from tests.integration.online_payments.conftest import sell_headers

    client_row = await make_client_no_email()
    plan = await make_membership_plan()

    response = await authed_client_reception.post(
        f"/api/v1/online-payments/memberships/{plan.id}/sell",
        json={"clientId": str(client_row.id)},
        headers=sell_headers(authed_client_reception),
    )
    # D-10: phone-only client must proceed, not 422
    assert response.status_code == 201, response.text
    assert response.json()["data"]["confirmationUrl"] is not None

    # DB row written
    rows = (await db_session.execute(select(OnlinePayment))).all()
    assert len(rows) == 1
    # ЮKassa WAS called
    assert yookassa_create_payment_success.calls.call_count == 1


# ─── Classification chain end-to-end ────────────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_transient_error_503(
    authed_client_reception,
    db_session,
    make_client_with_email,
    make_membership_plan,
    yookassa_create_payment_500,
) -> None:
    """ЮKassa 500 → router returns 503; no DB row written."""
    from tests.integration.online_payments.conftest import sell_headers

    client_row = await make_client_with_email()
    plan = await make_membership_plan()
    response = await authed_client_reception.post(
        f"/api/v1/online-payments/memberships/{plan.id}/sell",
        json={"clientId": str(client_row.id)},
        headers=sell_headers(authed_client_reception),
    )
    assert response.status_code == 503, response.text
    rows = (await db_session.execute(select(OnlinePayment))).all()
    assert rows == []


@pytest.mark.asyncio
async def test_e2e_permanent_error_502(
    authed_client_reception,
    db_session,
    make_client_with_email,
    make_membership_plan,
    yookassa_create_payment_404,
) -> None:
    """ЮKassa 404 → router returns 502; no DB row written."""
    from tests.integration.online_payments.conftest import sell_headers

    client_row = await make_client_with_email()
    plan = await make_membership_plan()
    response = await authed_client_reception.post(
        f"/api/v1/online-payments/memberships/{plan.id}/sell",
        json={"clientId": str(client_row.id)},
        headers=sell_headers(authed_client_reception),
    )
    assert response.status_code == 502, response.text
    rows = (await db_session.execute(select(OnlinePayment))).all()
    assert rows == []


@pytest.mark.asyncio
async def test_e2e_validation_error_422(
    authed_client_reception,
    db_session,
    make_client_with_email,
    make_membership_plan,
    yookassa_create_payment_422,
) -> None:
    """ЮKassa 422 → router returns 422 with yookassa_validation_error code; no DB row."""
    from tests.integration.online_payments.conftest import sell_headers

    client_row = await make_client_with_email()
    plan = await make_membership_plan()
    response = await authed_client_reception.post(
        f"/api/v1/online-payments/memberships/{plan.id}/sell",
        json={"clientId": str(client_row.id)},
        headers=sell_headers(authed_client_reception),
    )
    assert response.status_code == 422, response.text
    assert "yookassa_validation_error" in response.text
    rows = (await db_session.execute(select(OnlinePayment))).all()
    assert rows == []


# ─── SC#5 — schema integrity post-flow ──────────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_sc5_row_satisfies_check_constraints(
    authed_client_reception,
    db_session,
    make_client_with_email,
    make_membership_plan,
    yookassa_create_payment_success,
) -> None:
    """SC#5 — after a successful sell, the row satisfies all CHECK + XOR constraints."""
    from tests.integration.online_payments.conftest import sell_headers

    client_row = await make_client_with_email()
    plan = await make_membership_plan()
    response = await authed_client_reception.post(
        f"/api/v1/online-payments/memberships/{plan.id}/sell",
        json={"clientId": str(client_row.id)},
        headers=sell_headers(authed_client_reception),
    )
    assert response.status_code == 201, response.text
    row = await db_session.scalar(
        select(OnlinePayment).where(
            OnlinePayment.id == UUID(response.json()["data"]["onlinePaymentId"])
        )
    )
    assert row is not None
    # CHECK constraints implicitly hold (INSERT succeeded). Verify XOR:
    assert (row.membership_plan_id is not None) != (row.pt_package_plan_id is not None)
    # Status literal
    assert row.status in {"pending", "succeeded", "canceled"}
    # Confirmation type literal
    assert row.confirmation_type in {"redirect", "qr"}
    # Amount positive
    assert row.amount_kopecks > 0
    # Correlation ID set (D-49-04)
    assert row.audit_correlation_id is not None


# ─── SC#4 — return-screen under concurrent load ─────────────────────────────


@pytest.mark.asyncio
async def test_e2e_sc4_return_screen_concurrent_identical_body(
    async_client,
) -> None:
    """SC#4 — 10 concurrent GET /return: byte-identical bodies + cache-control no-store.

    Note: timing-floor magnitude is owned by ``tests/modules/online_payments/
    test_return_screen.py`` (Plan 49-05). This test re-asserts the static
    anti-oracle property under concurrent load — bodies MUST NOT differ
    across requests, regardless of any query-param the caller appends.
    """

    async def one() -> Any:
        return await async_client.get(
            "/api/v1/online-payments/return?payment_id=29ab1a59-000f-5000-8000-1399cb40ba0e"
        )

    responses = await asyncio.gather(*[one() for _ in range(10)])
    bodies = {r.content for r in responses}
    assert len(bodies) == 1, "All concurrent return-screen responses MUST be byte-identical"
    for r in responses:
        assert r.status_code == 200
        assert r.headers.get("cache-control", "").startswith("no-store")
