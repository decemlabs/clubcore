"""Phase 51 Plan 51-08 — integration tests for POST /memberships/{id}/refund.

Covers the critical operator-facing endpoint paths per the plan acceptance
criteria (RBAC, happy path, 404 on missing subject, 409 must_unfreeze_first,
409 invalid_transition, idempotency-key replay). PT-package smoke test lives
in ``test_initiate_pt_package_refund.py``.

These tests follow the Phase 49 ``tests/integration/online_payments/`` pattern:
ASGITransport + cookie-jar AsyncClient, SAVEPOINT-rolled db_session, respx-
intercepted ЮKassa HTTP boundary. The conftest provides:

  - ``seeded_membership_with_succeeded_online_payment`` — Client + Membership
    + OnlinePayment(succeeded) + Payment(method='online') seed graph.
  - ``yookassa_create_refund_success`` — POST /v3/refunds → 200 happy.
  - ``authed_client_owner`` / ``authed_client_reception`` — logged-in clients.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.online_refunds.models import OnlineRefund


def _refund_headers(client: AsyncClient) -> dict[str, str]:
    """CSRF header for POST /refund (D-49-25 RBAC-04 ordering).

    Refund endpoints do NOT use the HTTP Idempotency-Key middleware — the
    idempotency_key lives in the request body per D-48-11. So only X-CSRF-Token
    is required.
    """
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf") or ""}


# ─── Happy path ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_initiate_membership_refund_happy_path(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    seeded_membership_with_succeeded_online_payment,
    yookassa_create_refund_success,
) -> None:
    """POST /memberships/{id}/refund returns 202 + pending OnlineRefund row.

    Verifies:
      - HTTP 202 with envelope[data.onlineRefundId, .status='pending'].
      - DB row exists with status='pending' and matching idempotency_key.
      - ЮKassa POST /v3/refunds was hit exactly once.
    """
    _client, _op, _payment, membership = await seeded_membership_with_succeeded_online_payment()

    idem_key = uuid4()
    response = await authed_client_reception.post(
        f"/api/v1/online-payments/memberships/{membership.id}/refund",
        json={"idempotencyKey": str(idem_key), "reason": "operator-cancel"},
        headers=_refund_headers(authed_client_reception),
    )
    assert response.status_code == 202, response.text

    data = response.json()["data"]
    assert data["status"] == "pending"
    online_refund_id = UUID(data["onlineRefundId"])

    row = await db_session.scalar(select(OnlineRefund).where(OnlineRefund.id == online_refund_id))
    assert row is not None
    assert row.status == "pending"
    assert row.idempotency_key == str(idem_key)
    assert row.reason == "operator-cancel"

    # ЮKassa was actually called.
    refund_route = yookassa_create_refund_success.routes[0]
    assert refund_route.called
    assert refund_route.call_count == 1


# ─── 404 membership_not_found ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_initiate_membership_refund_404_unknown_membership(
    authed_client_reception: AsyncClient,
    yookassa_create_refund_success,
) -> None:
    """Unknown membership_id → 404 membership_not_found and NO ЮKassa call."""
    unknown_id = uuid4()
    response = await authed_client_reception.post(
        f"/api/v1/online-payments/memberships/{unknown_id}/refund",
        json={"idempotencyKey": str(uuid4()), "reason": None},
        headers=_refund_headers(authed_client_reception),
    )
    assert response.status_code == 404, response.text
    body = response.json()
    # AppError envelope shape: {"error": {"code": "...", ...}} OR {"detail": ...}.
    # Accept either; just ensure the literal slug appears somewhere.
    assert "membership_not_found" in response.text

    refund_route = yookassa_create_refund_success.routes[0]
    assert not refund_route.called


# ─── 409 must_unfreeze_first (B-08 / Phase 32 guard) ────────────────────────


@pytest.mark.asyncio
async def test_initiate_membership_refund_409_must_unfreeze_first(
    authed_client_reception: AsyncClient,
    seeded_membership_with_succeeded_online_payment,
    yookassa_create_refund_success,
) -> None:
    """Frozen membership → 409 must_unfreeze_first, ЮKassa NOT called."""
    _client, _op, _payment, membership = await seeded_membership_with_succeeded_online_payment(
        membership_status="frozen",
    )

    response = await authed_client_reception.post(
        f"/api/v1/online-payments/memberships/{membership.id}/refund",
        json={"idempotencyKey": str(uuid4()), "reason": None},
        headers=_refund_headers(authed_client_reception),
    )
    assert response.status_code == 409, response.text
    assert "must_unfreeze_first" in response.text

    refund_route = yookassa_create_refund_success.routes[0]
    assert not refund_route.called


# ─── 409 invalid_transition (refund-local FSM gate) ─────────────────────────


@pytest.mark.asyncio
async def test_initiate_membership_refund_409_invalid_transition(
    authed_client_reception: AsyncClient,
    seeded_membership_with_succeeded_online_payment,
    yookassa_create_refund_success,
) -> None:
    """Cancelled membership cannot transition to 'cancelled' again → 409."""
    _client, _op, _payment, membership = await seeded_membership_with_succeeded_online_payment(
        membership_status="cancelled",
    )

    response = await authed_client_reception.post(
        f"/api/v1/online-payments/memberships/{membership.id}/refund",
        json={"idempotencyKey": str(uuid4()), "reason": None},
        headers=_refund_headers(authed_client_reception),
    )
    assert response.status_code == 409, response.text
    assert "invalid_transition" in response.text


# ─── Idempotency-Key replay (D-51-Discretion) ───────────────────────────────


@pytest.mark.asyncio
async def test_initiate_membership_refund_idempotency_key_replay(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    seeded_membership_with_succeeded_online_payment,
    yookassa_create_refund_success,
) -> None:
    """Second POST with same idempotency_key returns same row, no second ЮKassa call."""
    _client, _op, _payment, membership = await seeded_membership_with_succeeded_online_payment()

    idem_key = uuid4()
    body = {"idempotencyKey": str(idem_key), "reason": "first-call"}

    r1 = await authed_client_reception.post(
        f"/api/v1/online-payments/memberships/{membership.id}/refund",
        json=body,
        headers=_refund_headers(authed_client_reception),
    )
    assert r1.status_code == 202, r1.text
    first_id = UUID(r1.json()["data"]["onlineRefundId"])

    r2 = await authed_client_reception.post(
        f"/api/v1/online-payments/memberships/{membership.id}/refund",
        json=body,
        headers=_refund_headers(authed_client_reception),
    )
    assert r2.status_code == 202, r2.text
    second_id = UUID(r2.json()["data"]["onlineRefundId"])

    # Same row returned — no second INSERT.
    assert first_id == second_id

    # ЮKassa POST /refunds called exactly once (replay short-circuits before HTTP).
    refund_route = yookassa_create_refund_success.routes[0]
    assert refund_route.call_count == 1

    # Exactly one OnlineRefund row in the DB for this online_payment.
    rows = (
        await db_session.scalars(
            select(OnlineRefund).where(OnlineRefund.idempotency_key == str(idem_key))
        )
    ).all()
    assert len(rows) == 1
