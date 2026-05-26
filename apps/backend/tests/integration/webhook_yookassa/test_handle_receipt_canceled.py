"""Phase 51 D-51-22 — handle_receipt_canceled integration tests.

Mirror of handle_receipt_succeeded with target='failed', failure_reason
extracted from body['object']['cancellation_details']['reason'] (D-51-22).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.fiscal_receipts.models import FiscalReceipt
from app.modules.payments.constants import SUBJECT_KIND_MEMBERSHIP
from app.modules.payments.models import Payment


async def _seed_fiscal_receipt_sent(
    session: AsyncSession,
    *,
    yookassa_receipt_id: str | None = None,
) -> FiscalReceipt:
    payment = Payment(
        subject_kind=SUBJECT_KIND_MEMBERSHIP,
        subject_id=uuid4(),
        amount_kopecks=100_000,
        method="online",
        received_by_user_id=None,
        refund_of=None,
    )
    session.add(payment)
    await session.flush()

    fr = FiscalReceipt(
        payment_id=payment.id,
        kind="payment",
        status="sent",
        yookassa_receipt_id=yookassa_receipt_id or f"rcpt-{uuid4().hex[:24]}",
        customer_email=f"receipt-test-{uuid4().hex[:8]}@example.com",
        audit_correlation_id=uuid4(),
        sent_at=datetime.now(UTC),
    )
    session.add(fr)
    await session.flush()
    await session.commit()
    return fr


@pytest_asyncio.fixture
async def seeded_fiscal_receipt_sent(
    webhook_db_session: AsyncSession,
) -> FiscalReceipt:
    return await _seed_fiscal_receipt_sent(webhook_db_session)


def _webhook_receipt_canceled_body(
    receipt_id: str, *, reason: str | None = "ofd_offline"
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "event": "receipt.canceled",
        "object": {
            "id": receipt_id,
            "type": "payment",
            "status": "canceled",
        },
    }
    if reason is not None:
        body["object"]["cancellation_details"] = {"reason": reason}
    return body


@pytest.mark.asyncio
async def test_handle_receipt_canceled_transitions_fsm_sent_to_failed(
    webhook_client: Any,
    webhook_db_session: AsyncSession,
    seeded_fiscal_receipt_sent: FiscalReceipt,
) -> None:
    fr = seeded_fiscal_receipt_sent
    fr_id = fr.id
    fr_yookassa_id = fr.yookassa_receipt_id
    assert fr_yookassa_id is not None
    body = _webhook_receipt_canceled_body(fr_yookassa_id)
    response = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert response.status_code == 200, response.text

    await webhook_db_session.commit()
    webhook_db_session.expire_all()
    after_row = (
        await webhook_db_session.execute(
            select(FiscalReceipt.status, FiscalReceipt.failed_at).where(FiscalReceipt.id == fr_id)
        )
    ).one()
    assert after_row.status == "failed"
    assert after_row.failed_at is not None


@pytest.mark.asyncio
async def test_handle_receipt_canceled_extracts_failure_reason_from_cancellation_details(
    webhook_client: Any,
    webhook_db_session: AsyncSession,
    seeded_fiscal_receipt_sent: FiscalReceipt,
) -> None:
    fr = seeded_fiscal_receipt_sent
    fr_id = fr.id
    fr_yookassa_id = fr.yookassa_receipt_id
    assert fr_yookassa_id is not None
    body = _webhook_receipt_canceled_body(fr_yookassa_id, reason="ofd_offline")
    response = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert response.status_code == 200, response.text

    await webhook_db_session.commit()
    webhook_db_session.expire_all()
    after_failure_reason = await webhook_db_session.scalar(
        select(FiscalReceipt.failure_reason).where(FiscalReceipt.id == fr_id)
    )
    assert after_failure_reason == "ofd_offline"


@pytest.mark.asyncio
async def test_handle_receipt_canceled_emits_fiscal_receipt_failed_audit_with_failure_reason(
    webhook_client: Any,
    webhook_db_session: AsyncSession,
    seeded_fiscal_receipt_sent: FiscalReceipt,
) -> None:
    fr = seeded_fiscal_receipt_sent
    assert fr.yookassa_receipt_id is not None
    body = _webhook_receipt_canceled_body(fr.yookassa_receipt_id, reason="ofd_offline")
    response = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert response.status_code == 200, response.text

    await webhook_db_session.commit()
    audits = (
        (
            await webhook_db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "fiscal_receipt_failed",
                    AuditLog.resource_id == fr.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audits) == 1
    assert audits[0].payload.get("failure_reason") == "ofd_offline"


@pytest.mark.asyncio
async def test_handle_receipt_canceled_falls_back_to_default_reason_when_cancellation_details_missing(
    webhook_client: Any,
    webhook_db_session: AsyncSession,
    seeded_fiscal_receipt_sent: FiscalReceipt,
) -> None:
    fr = seeded_fiscal_receipt_sent
    fr_id = fr.id
    fr_yookassa_id = fr.yookassa_receipt_id
    assert fr_yookassa_id is not None
    body = _webhook_receipt_canceled_body(fr_yookassa_id, reason=None)
    response = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert response.status_code == 200, response.text

    await webhook_db_session.commit()
    webhook_db_session.expire_all()
    after_failure_reason = await webhook_db_session.scalar(
        select(FiscalReceipt.failure_reason).where(FiscalReceipt.id == fr_id)
    )
    assert after_failure_reason == "yookassa_receipt_canceled"


@pytest.mark.asyncio
async def test_handle_receipt_canceled_emits_orphan_audit_when_row_missing(
    webhook_client: Any,
    webhook_db_session: AsyncSession,
) -> None:
    orphan_id = f"rcpt-orphan-{uuid4().hex[:16]}"
    body = _webhook_receipt_canceled_body(orphan_id)
    response = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert response.status_code == 200, response.text

    await webhook_db_session.commit()
    audits = (
        (
            await webhook_db_session.execute(
                select(AuditLog).where(AuditLog.action == "yookassa_webhook_received")
            )
        )
        .scalars()
        .all()
    )
    outcomes = [a.payload.get("idempotency_outcome") for a in audits]
    assert "orphan" in outcomes
