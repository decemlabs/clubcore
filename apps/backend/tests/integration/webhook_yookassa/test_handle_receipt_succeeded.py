"""Phase 51 D-51-21 — handle_receipt_succeeded integration tests.

Receipt webhook does NOT re-fetch (D-51-03 — status is informational; webhook
body is authoritative). Atomic UoW: SELECT-FOR-UPDATE FiscalReceipt by
yookassa_receipt_id, FSM guard target='succeeded', UPDATE status + succeeded_at,
emit fiscal_receipt_succeeded + yookassa_webhook_received audits.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

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
    """Seed a FiscalReceipt(status='sent', kind='payment') with its parent Payment row."""
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


def _webhook_receipt_succeeded_body(receipt_id: str) -> dict[str, Any]:
    return {
        "event": "receipt.succeeded",
        "object": {
            "id": receipt_id,
            "type": "payment",
            "status": "succeeded",
        },
    }


@pytest.mark.asyncio
async def test_handle_receipt_succeeded_transitions_fsm_sent_to_succeeded(
    webhook_client: Any,
    webhook_db_session: AsyncSession,
    seeded_fiscal_receipt_sent: FiscalReceipt,
) -> None:
    """sent → succeeded FSM transition with succeeded_at populated."""
    fr = seeded_fiscal_receipt_sent
    fr_id = fr.id
    assert fr.yookassa_receipt_id is not None
    body = _webhook_receipt_succeeded_body(fr.yookassa_receipt_id)
    response = await webhook_client.post(
        "/api/v1/_internal/yookassa/webhook", json=body
    )
    assert response.status_code == 200, response.text

    await webhook_db_session.commit()
    webhook_db_session.expire_all()
    after_row = (
        await webhook_db_session.execute(
            select(FiscalReceipt.status, FiscalReceipt.succeeded_at).where(
                FiscalReceipt.id == fr_id
            )
        )
    ).one()
    assert after_row.status == "succeeded"
    assert after_row.succeeded_at is not None


@pytest.mark.asyncio
async def test_handle_receipt_succeeded_emits_fiscal_receipt_succeeded_audit_with_correlation_id_from_row(
    webhook_client: Any,
    webhook_db_session: AsyncSession,
    seeded_fiscal_receipt_sent: FiscalReceipt,
) -> None:
    fr = seeded_fiscal_receipt_sent
    assert fr.yookassa_receipt_id is not None
    expected_corr: UUID | None = fr.audit_correlation_id
    body = _webhook_receipt_succeeded_body(fr.yookassa_receipt_id)
    response = await webhook_client.post(
        "/api/v1/_internal/yookassa/webhook", json=body
    )
    assert response.status_code == 200, response.text

    await webhook_db_session.commit()
    audits = (
        await webhook_db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "fiscal_receipt_succeeded",
                AuditLog.resource_id == fr.id,
            )
        )
    ).scalars().all()
    assert len(audits) == 1
    payload = audits[0].payload
    if expected_corr is not None:
        assert payload.get("audit_correlation_id") == str(expected_corr)
    assert payload.get("yookassa_receipt_id") == fr.yookassa_receipt_id


@pytest.mark.asyncio
async def test_handle_receipt_succeeded_does_not_refetch_via_yookassa(
    webhook_client: Any,
    webhook_db_session: AsyncSession,
    seeded_fiscal_receipt_sent: FiscalReceipt,
) -> None:
    """D-51-03 — receipt handlers MUST NOT re-fetch via YooKassaClient.

    Patch YooKassaClient.get_payment / get_refund to raise if called; invoke
    the handler; assert no exception (proves no re-fetch happened).
    """
    fr = seeded_fiscal_receipt_sent
    assert fr.yookassa_receipt_id is not None

    from app.integrations.yookassa import client as yk_client_mod

    original_get_payment = yk_client_mod.YooKassaClient.get_payment
    original_get_refund = yk_client_mod.YooKassaClient.get_refund

    async def _explosive(self: Any, *_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("YooKassaClient.get_* called during receipt webhook")

    yk_client_mod.YooKassaClient.get_payment = _explosive  # type: ignore[method-assign]
    yk_client_mod.YooKassaClient.get_refund = _explosive  # type: ignore[method-assign]
    try:
        body = _webhook_receipt_succeeded_body(fr.yookassa_receipt_id)
        response = await webhook_client.post(
            "/api/v1/_internal/yookassa/webhook", json=body
        )
        assert response.status_code == 200, response.text
    finally:
        yk_client_mod.YooKassaClient.get_payment = original_get_payment  # type: ignore[method-assign]
        yk_client_mod.YooKassaClient.get_refund = original_get_refund  # type: ignore[method-assign]


@pytest.mark.asyncio
async def test_handle_receipt_succeeded_emits_orphan_audit_when_row_missing(
    webhook_client: Any,
    webhook_db_session: AsyncSession,
) -> None:
    """No FiscalReceipt matches the object_id → orphan audit row."""
    orphan_id = f"rcpt-orphan-{uuid4().hex[:16]}"
    body = _webhook_receipt_succeeded_body(orphan_id)
    response = await webhook_client.post(
        "/api/v1/_internal/yookassa/webhook", json=body
    )
    assert response.status_code == 200, response.text

    await webhook_db_session.commit()
    audits = (
        await webhook_db_session.execute(
            select(AuditLog).where(AuditLog.action == "yookassa_webhook_received")
        )
    ).scalars().all()
    outcomes = [a.payload.get("idempotency_outcome") for a in audits]
    assert "orphan" in outcomes


@pytest.mark.asyncio
async def test_handle_receipt_succeeded_rejects_illegal_transition(
    webhook_client: Any,
    webhook_db_session: AsyncSession,
) -> None:
    """Pre-set status='succeeded' (terminal) → second delivery is no-op +
    illegal_transition audit."""
    fr = await _seed_fiscal_receipt_sent(webhook_db_session)
    fr_id = fr.id
    fr_yookassa_id = fr.yookassa_receipt_id
    # Flip to terminal manually.
    row = await webhook_db_session.scalar(
        select(FiscalReceipt).where(FiscalReceipt.id == fr_id)
    )
    assert row is not None
    row.status = "succeeded"
    row.succeeded_at = datetime.now(UTC)
    await webhook_db_session.flush()
    await webhook_db_session.commit()

    assert fr_yookassa_id is not None
    body = _webhook_receipt_succeeded_body(fr_yookassa_id)
    response = await webhook_client.post(
        "/api/v1/_internal/yookassa/webhook", json=body
    )
    assert response.status_code == 200, response.text

    await webhook_db_session.commit()
    webhook_db_session.expire_all()
    after_status = await webhook_db_session.scalar(
        select(FiscalReceipt.status).where(FiscalReceipt.id == fr_id)
    )
    assert after_status == "succeeded"

    audits = (
        await webhook_db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "yookassa_webhook_received",
                AuditLog.resource_id == fr_id,
            )
        )
    ).scalars().all()
    outcomes = [a.payload.get("idempotency_outcome") for a in audits]
    assert "illegal_transition" in outcomes
