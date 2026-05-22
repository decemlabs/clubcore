"""WH-06 — payment.canceled records cancellation_details (Phase 50 SC #5).

W-5 FIX: uses the EXPLICIT ``yookassa_get_payment_canceled`` fixture from
conftest (concrete fixture, no "may not exist" hedge).
"""

from __future__ import annotations

from typing import Any

import pytest
import respx
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.fiscal_receipts.models import FiscalReceipt
from app.modules.online_payments.models import OnlinePayment
from tests.integration.webhook_yookassa.conftest import SeededOnlinePayment


@pytest.mark.asyncio
async def test_wh06_canceled_records_cancellation_details(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    seeded_online_payment_pending: SeededOnlinePayment,
    yookassa_get_payment_canceled: respx.MockRouter,
    webhook_payment_canceled_body: Any,
) -> None:
    """Cancellation body with cancellation_details → audit payload captures party + reason."""
    body = webhook_payment_canceled_body(
        seeded_online_payment_pending.yookassa_payment_id,
        party="yoo_money",
        reason="fraud_suspected",
    )
    response = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert response.status_code == 200, response.text

    await webhook_db_session.commit()

    # Row flipped to canceled with canceled_at populated.
    op = await webhook_db_session.scalar(
        select(OnlinePayment).where(
            OnlinePayment.id == seeded_online_payment_pending.online_payment_id
        )
    )
    assert op is not None
    assert op.status == "canceled"
    assert op.canceled_at is not None

    # Audit row carries cancellation_party + cancellation_reason.
    rows = (
        await webhook_db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "online_payment_canceled",
                AuditLog.resource_id
                == seeded_online_payment_pending.online_payment_id,
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    payload = rows[0].payload
    assert payload.get("cancellation_party") == "yoo_money"
    assert payload.get("cancellation_reason") == "fraud_suspected"


@pytest.mark.asyncio
async def test_wh06_canceled_missing_cancellation_details_is_none(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    seeded_online_payment_pending: SeededOnlinePayment,
    yookassa_get_payment_canceled: respx.MockRouter,
    webhook_payment_canceled_body: Any,
) -> None:
    """Cancellation body WITHOUT cancellation_details → audit fields are None (D-50-25)."""
    body = webhook_payment_canceled_body(
        seeded_online_payment_pending.yookassa_payment_id,
        party=None,
        reason=None,
    )
    # Ensure the cancellation_details key was actually omitted (factory only
    # adds it when at least one of party/reason is non-None).
    assert "cancellation_details" not in body["object"]

    response = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert response.status_code == 200, response.text

    await webhook_db_session.commit()
    rows = (
        await webhook_db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "online_payment_canceled",
                AuditLog.resource_id
                == seeded_online_payment_pending.online_payment_id,
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    payload = rows[0].payload
    assert payload.get("cancellation_party") is None
    assert payload.get("cancellation_reason") is None


@pytest.mark.asyncio
async def test_wh06_canceled_no_fiscal_receipt_inserted(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    seeded_online_payment_pending: SeededOnlinePayment,
    yookassa_get_payment_canceled: respx.MockRouter,
    webhook_payment_canceled_body: Any,
) -> None:
    """Cancelled payments produce NO fiscal_receipts row (D-50-26)."""
    body = webhook_payment_canceled_body(
        seeded_online_payment_pending.yookassa_payment_id,
    )
    response = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert response.status_code == 200, response.text

    await webhook_db_session.commit()
    receipts = (
        await webhook_db_session.execute(select(FiscalReceipt))
    ).scalars().all()
    assert len(receipts) == 0, (
        f"WH-06: cancellation must NOT insert a fiscal_receipt; found {len(receipts)}"
    )
