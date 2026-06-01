"""WH-07 — phone-only payment.succeeded UoW (Phase 999.5 Plan 08 / Issue 2).

Closes the UAT-12 BLOCKER: a «Чек не нужен» phone-only client (email NULL,
phone set) completes a real ЮKassa payment. Before Plan 08 the webhook called
``_read_customer_email`` which raised ``RuntimeError`` on the NULL email, rolling
back the already-set succeeded status → permanent HTTP 500 / stuck-``pending``.

This suite asserts the phone-only path now:
  - returns HTTP 200,
  - flips online_payments.status → 'succeeded' + succeeded_at,
  - activates the membership + writes a payments ledger row,
  - persists a fiscal_receipts row with customer_email NULL + customer_phone set
    (status='sent', kind='payment'),

and a regression test asserts the email-bearing path is unchanged
(customer_email == client email, customer_phone NULL).

Plus PII discipline: no client contact value (email or phone) appears in any
structlog event emitted by the webhook.
"""

from __future__ import annotations

from typing import Any

import pytest
import respx
import structlog
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.fiscal_receipts.models import FiscalReceipt
from app.modules.memberships.models import Membership
from app.modules.online_payments.models import OnlinePayment
from app.modules.payments.models import Payment
from tests.integration.webhook_yookassa.conftest import SeededOnlinePayment


@pytest.mark.asyncio
async def test_wh07_phone_only_succeeded_completes_uow(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    seeded_online_payment_pending_phone_only: SeededOnlinePayment,
    yookassa_get_payment_succeeded: respx.MockRouter,
    webhook_payment_succeeded_body: Any,
) -> None:
    """Phone-only client → 200, succeeded flip, membership activated, ledger row."""
    seeded = seeded_online_payment_pending_phone_only
    body = webhook_payment_succeeded_body(seeded.yookassa_payment_id)
    response = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert response.status_code == 200, response.text

    await webhook_db_session.commit()

    # OnlinePayment flipped to succeeded (the RuntimeError no longer rolls it back).
    op = await webhook_db_session.scalar(
        select(OnlinePayment).where(OnlinePayment.id == seeded.online_payment_id)
    )
    assert op is not None
    assert op.status == "succeeded"
    assert op.succeeded_at is not None

    # Payment ledger row written.
    payment_row = await webhook_db_session.scalar(
        select(Payment).where(
            Payment.subject_id == seeded.membership_plan_id,
            Payment.method == "online",
        )
    )
    assert payment_row is not None
    assert payment_row.amount_kopecks == seeded.amount_kopecks

    # Membership activated.
    membership = await webhook_db_session.scalar(
        select(Membership).where(
            Membership.client_id == seeded.client_id,
            Membership.plan_id == seeded.membership_plan_id,
        )
    )
    assert membership is not None
    assert membership.status == "active"


@pytest.mark.asyncio
async def test_wh07_phone_only_fiscal_receipt_carries_phone(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    seeded_online_payment_pending_phone_only: SeededOnlinePayment,
    yookassa_get_payment_succeeded: respx.MockRouter,
    webhook_payment_succeeded_body: Any,
) -> None:
    """The fiscal_receipts row has customer_email NULL + customer_phone == phone."""
    seeded = seeded_online_payment_pending_phone_only
    body = webhook_payment_succeeded_body(seeded.yookassa_payment_id)
    response = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert response.status_code == 200, response.text

    await webhook_db_session.commit()

    payment_row = await webhook_db_session.scalar(
        select(Payment).where(
            Payment.subject_id == seeded.membership_plan_id,
            Payment.method == "online",
        )
    )
    assert payment_row is not None

    fr = await webhook_db_session.scalar(
        select(FiscalReceipt).where(FiscalReceipt.payment_id == payment_row.id)
    )
    assert fr is not None
    assert fr.kind == "payment"
    assert fr.status == "sent"
    assert fr.customer_email is None
    assert fr.customer_phone == seeded.client_phone


@pytest.mark.asyncio
async def test_wh07_email_path_unchanged_regression(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    seeded_online_payment_pending: SeededOnlinePayment,
    yookassa_get_payment_succeeded: respx.MockRouter,
    webhook_payment_succeeded_body: Any,
) -> None:
    """Regression: email-bearing client still writes email-only fiscal receipt."""
    seeded = seeded_online_payment_pending
    body = webhook_payment_succeeded_body(seeded.yookassa_payment_id)
    response = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert response.status_code == 200, response.text

    await webhook_db_session.commit()

    payment_row = await webhook_db_session.scalar(
        select(Payment).where(
            Payment.subject_id == seeded.membership_plan_id,
            Payment.method == "online",
        )
    )
    assert payment_row is not None

    fr = await webhook_db_session.scalar(
        select(FiscalReceipt).where(FiscalReceipt.payment_id == payment_row.id)
    )
    assert fr is not None
    assert fr.customer_email == seeded.client_email
    assert fr.customer_phone is None


@pytest.mark.asyncio
async def test_wh07_phone_only_contact_never_logged(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    seeded_online_payment_pending_phone_only: SeededOnlinePayment,
    yookassa_get_payment_succeeded: respx.MockRouter,
    webhook_payment_succeeded_body: Any,
) -> None:
    """PII discipline (T-999.5-12): client phone never lands in a structlog kwarg."""
    seeded = seeded_online_payment_pending_phone_only
    phone = seeded.client_phone
    assert phone  # defensive: the seed must actually carry a phone

    body = webhook_payment_succeeded_body(seeded.yookassa_payment_id)
    with structlog.testing.capture_logs() as cap:
        response = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert response.status_code == 200, response.text

    for entry in cap:
        for key, value in entry.items():
            if isinstance(value, str):
                assert phone not in value, (
                    f"client phone leaked into structlog kwarg {key!r}={value!r}"
                )
