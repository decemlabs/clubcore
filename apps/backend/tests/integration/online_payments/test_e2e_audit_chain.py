"""Phase 49 Plan 49-07 — audit-chain verification for D-49-19.

Verifies the two-event chain emitted by ``service.sell_membership`` /
``service.sell_pt_package``:

  1. ``online_payment_initiated`` (ROOT) — payload ``audit_correlation_id``
     is ``None``; the AuditLog row's own ``id`` becomes the chain UUID and
     is persisted on ``online_payments.audit_correlation_id``.
  2. ``yookassa_payment_created`` (CHILD) — payload ``audit_correlation_id``
     carries the ROOT row's chain UUID so Phase 50 webhook handlers can
     walk back to the initiating click.

Uses the verified ``AuditLog`` ORM (``app.core.audit_models``) with direct
``.action`` and dict ``.payload`` access — no ``json.loads`` (the column
is JSONB and the SQLAlchemy mapper returns it as ``dict[str, Any]``).
"""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import select

from app.core.audit_models import AuditLog
from app.modules.online_payments.models import OnlinePayment


@pytest.mark.asyncio
async def test_e2e_audit_chain_membership_sell_emits_root_then_child(
    authed_client_reception,
    db_session,
    make_client_with_email,
    make_membership_plan,
    yookassa_create_payment_success,
) -> None:
    """D-49-19 — membership sell emits initiated (ROOT) + yookassa_payment_created (CHILD)."""
    from tests.integration.online_payments.conftest import sell_headers

    client_row = await make_client_with_email()
    plan = await make_membership_plan()

    response = await authed_client_reception.post(
        f"/api/v1/online-payments/memberships/{plan.id}/sell",
        json={"clientId": str(client_row.id)},
        headers=sell_headers(authed_client_reception),
    )
    assert response.status_code == 201, response.text
    online_payment_id = UUID(response.json()["data"]["onlinePaymentId"])

    # Re-read the row to capture audit_correlation_id chain root
    row = await db_session.scalar(
        select(OnlinePayment).where(OnlinePayment.id == online_payment_id)
    )
    assert row is not None
    chain_root = row.audit_correlation_id
    assert chain_root is not None, "audit_correlation_id should be set at row insert"

    # Fetch both audit rows by resource_id
    audit_rows = (
        await db_session.scalars(
            select(AuditLog)
            .where(AuditLog.resource_id == online_payment_id)
            .order_by(AuditLog.created_at)
        )
    ).all()

    initiated = next((a for a in audit_rows if a.action == "online_payment_initiated"), None)
    created = next((a for a in audit_rows if a.action == "yookassa_payment_created"), None)

    assert initiated is not None, "online_payment_initiated row missing"
    assert created is not None, "yookassa_payment_created row missing"
    assert initiated.resource_type == "online_payment"
    assert created.resource_type == "online_payment"

    # ROOT semantics: payload audit_correlation_id is None
    root_corr = initiated.payload.get("audit_correlation_id")
    assert root_corr is None, "ROOT event must carry audit_correlation_id=None"

    # CHILD semantics: payload audit_correlation_id == chain root (the
    # online_payments.audit_correlation_id column value)
    child_corr = created.payload.get("audit_correlation_id")
    assert child_corr is not None, "CHILD event must carry audit_correlation_id"
    assert UUID(child_corr) == chain_root, (
        "CHILD audit_correlation_id must equal online_payments.audit_correlation_id"
    )

    # CHILD payload also locks the YooKassa wire fields
    assert created.payload["yookassa_payment_id"] == row.yookassa_payment_id
    assert created.payload["idempotency_key"] == row.idempotency_key
    assert created.payload["confirmation_type"] == "redirect"


@pytest.mark.asyncio
async def test_e2e_audit_chain_pt_package_qr_sell_uses_qr_confirmation_type(
    authed_client_reception,
    db_session,
    make_client_with_email,
    make_pt_package_plan,
    yookassa_create_payment_qr_success,
) -> None:
    """D-49-19 — PT-package QR sell emits both events; CHILD payload confirmation_type='qr'."""
    from tests.integration.online_payments.conftest import sell_headers

    client_row = await make_client_with_email()
    plan = await make_pt_package_plan()

    response = await authed_client_reception.post(
        f"/api/v1/online-payments/pt-packages/{plan.id}/sell-qr",
        json={"clientId": str(client_row.id)},
        headers=sell_headers(authed_client_reception),
    )
    assert response.status_code == 201, response.text
    online_payment_id = UUID(response.json()["data"]["onlinePaymentId"])

    audit_rows = (
        await db_session.scalars(
            select(AuditLog)
            .where(AuditLog.resource_id == online_payment_id)
            .order_by(AuditLog.created_at)
        )
    ).all()

    actions = [a.action for a in audit_rows]
    assert actions == [
        "online_payment_initiated",
        "yookassa_payment_created",
    ], f"expected ROOT then CHILD; got {actions}"

    child = audit_rows[1]
    assert child.payload["confirmation_type"] == "qr"


@pytest.mark.asyncio
async def test_e2e_audit_chain_phone_only_client_emits_audit_rows_d10(
    authed_client_reception,
    db_session,
    make_client_no_email,
    make_membership_plan,
    yookassa_create_payment_success,
) -> None:
    """D-10 / Phase 999.5 — phone-only client proceeds and emits audit chain.

    Pre-D-10 (D-49-12, D-49-20): email-gate failure → 422 → no audit rows.
    Post-D-10: phone-only client proceeds → 201 → audit chain emitted (2 rows).
    The gate is relaxed; phone is the 54-ФЗ fallback receipt contact.
    """
    from tests.integration.online_payments.conftest import sell_headers

    client_row = await make_client_no_email()
    plan = await make_membership_plan()

    response = await authed_client_reception.post(
        f"/api/v1/online-payments/memberships/{plan.id}/sell",
        json={"clientId": str(client_row.id)},
        headers=sell_headers(authed_client_reception),
    )
    # D-10: must succeed — phone-only client is no longer blocked
    assert response.status_code == 201, response.text

    # Audit chain IS emitted (online_payment_initiated + yookassa_payment_created)
    audit_rows = (
        await db_session.scalars(
            select(AuditLog).where(AuditLog.action == "online_payment_initiated")
        )
    ).all()
    matching = [a for a in audit_rows if a.payload.get("client_id") == str(client_row.id)]
    assert len(matching) == 1, (
        f"D-10: audit row must exist for phone-only client sell; got {matching}"
    )
