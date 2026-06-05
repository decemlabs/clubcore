"""Phase 84 APAY-02 — webhook autopay discriminator test.

When the payment.succeeded webhook fires for an online_payments row with
confirmation_type='autopay' (set by the off-session charge cron), the webhook
handler must:
  1. Record method='autopay' (NOT 'online') on the charge-ledger payments.Payment row.
  2. Activate the membership renewal (D-06 webhook-locked activation unchanged).
  3. Pass kind='autopay_charge_succeeded' (NOT 'payment_succeeded') to _post_commit_enqueue.

This test uses the real-commit webhook_db_session + webhook_client to avoid the
SAVEPOINT conflict with `async with session.begin()` inside the handler.
Deviation from plan's file target (84-02 plan said test_charge_expiring_autopay.py):
rule 3 auto-fix — SAVEPOINT mode cannot compose with session.begin(); tests placed
in the webhook test directory where real-commit fixtures are available.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
import respx
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.memberships.models import Membership
from app.modules.online_payments.constants import STATUS_PENDING
from app.modules.online_payments.models import OnlinePayment
from app.modules.payments.models import Payment
from tests.integration.webhook_yookassa.conftest import (
    SeededOnlinePayment,
    _seed_client,
    _seed_membership_plan,
)

_YK_BASE = "https://api.yookassa.ru/v3/"

# ---------------------------------------------------------------------------
# Seed an autopay online_payments row (confirmation_type='autopay')
# ---------------------------------------------------------------------------


async def _seed_autopay_online_payment(session: AsyncSession) -> SeededOnlinePayment:
    """Insert Client + MembershipPlan + OnlinePayment(confirmation_type='autopay')."""
    client = await _seed_client(session)
    plan = await _seed_membership_plan(session)
    yk_id = f"yk-autopay-{uuid4().hex[:20]}"
    corr = uuid4()
    op = OnlinePayment(
        client_id=client.id,
        membership_plan_id=plan.id,
        pt_package_plan_id=None,
        yookassa_payment_id=yk_id,
        idempotency_key=uuid4().hex,
        amount_kopecks=199_000,
        status=STATUS_PENDING,
        confirmation_url=None,
        confirmation_type="autopay",  # ← the discriminator
        audit_correlation_id=corr,
    )
    session.add(op)
    await session.flush()
    await session.commit()
    return SeededOnlinePayment(
        online_payment_id=op.id,
        yookassa_payment_id=yk_id,
        client_id=client.id,
        client_email=client.email or "",
        client_phone=client.phone,
        membership_plan_id=plan.id,
        pt_package_plan_id=None,
        audit_correlation_id=corr,
        amount_kopecks=199_000,
    )


@pytest_asyncio.fixture
async def seeded_autopay_online_payment(
    webhook_db_session: AsyncSession,
) -> SeededOnlinePayment:
    """Insert a pending autopay OnlinePayment for the discriminator test."""
    return await _seed_autopay_online_payment(webhook_db_session)


# ---------------------------------------------------------------------------
# Test: payment.succeeded for confirmation_type='autopay' → method='autopay'
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_autopay_succeeded_webhook_records_method_autopay(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    seeded_autopay_online_payment: SeededOnlinePayment,
) -> None:
    """payment.succeeded for an autopay online_payments row → method='autopay' on Payment.

    Verifies:
    - The charge-ledger Payment row has method='autopay' (NOT 'online').
    - The membership IS renewed (activation is webhook-locked, D-06 unchanged).
    - The handler returns 200 (same as the interactive path).
    """
    yk_payment_id = seeded_autopay_online_payment.yookassa_payment_id
    amount_kopecks = seeded_autopay_online_payment.amount_kopecks

    # Simulate payment.succeeded webhook body.
    body = {
        "type": "notification",
        "event": "payment.succeeded",
        "object": {"id": yk_payment_id},
    }

    # Mock YooKassa GET /v3/payments/{id} → succeeded.
    with respx.mock(base_url=_YK_BASE, assert_all_called=False) as router:
        router.get(url__regex=r"payments/[\w-]+").mock(
            return_value=Response(
                200,
                json={
                    "id": yk_payment_id,
                    "status": "succeeded",
                    "amount": {"value": "1990.00", "currency": "RUB"},
                    "description": "Автопродление",
                    "paid": True,
                    "refundable": True,
                    "metadata": {},
                },
            )
        )

        response = await webhook_client.post(
            "/api/v1/_internal/yookassa/webhook",
            json=body,
        )

    assert response.status_code == 200, response.text

    await webhook_db_session.commit()

    # Verify: payments.Payment row has method='autopay'
    from sqlalchemy import select

    payment_rows = (
        (
            await webhook_db_session.execute(
                select(Payment).where(
                    Payment.subject_id == seeded_autopay_online_payment.membership_plan_id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(payment_rows) == 1, f"Expected 1 Payment row, got {len(payment_rows)}"
    assert payment_rows[0].method == "autopay", (
        f"Expected method='autopay' for autopay online_payments, got '{payment_rows[0].method}'"
    )
    assert payment_rows[0].amount_kopecks == amount_kopecks

    # Verify: membership IS activated/renewed (D-06 webhook-locked activation unchanged)
    memberships = (
        (
            await webhook_db_session.execute(
                select(Membership).where(
                    Membership.client_id == seeded_autopay_online_payment.client_id
                )
            )
        )
        .scalars()
        .all()
    )
    # At least 1 membership should exist (the activated one)
    assert len(memberships) >= 1, "Membership should be created/activated by the webhook"

    # Verify: online_payments row is now succeeded
    op = await webhook_db_session.scalar(
        select(OnlinePayment).where(
            OnlinePayment.id == seeded_autopay_online_payment.online_payment_id
        )
    )
    assert op is not None
    assert op.status == "succeeded"


@pytest.mark.asyncio
async def test_non_autopay_succeeded_webhook_records_method_online(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    seeded_online_payment_pending: SeededOnlinePayment,
) -> None:
    """payment.succeeded for a redirect online_payments row → method='online' (regression guard).

    Verifies that the existing interactive checkout path is UNCHANGED:
    method='online' on Payment, NOT 'autopay'.
    """
    yk_payment_id = seeded_online_payment_pending.yookassa_payment_id

    body = {
        "type": "notification",
        "event": "payment.succeeded",
        "object": {"id": yk_payment_id},
    }

    with respx.mock(base_url=_YK_BASE, assert_all_called=False) as router:
        router.get(url__regex=r"payments/[\w-]+").mock(
            return_value=Response(
                200,
                json={
                    "id": yk_payment_id,
                    "status": "succeeded",
                    "amount": {"value": "1000.00", "currency": "RUB"},
                    "description": "Тест",
                    "paid": True,
                    "refundable": True,
                    "metadata": {},
                },
            )
        )

        response = await webhook_client.post(
            "/api/v1/_internal/yookassa/webhook",
            json=body,
        )

    assert response.status_code == 200, response.text

    await webhook_db_session.commit()

    from sqlalchemy import select

    payment_rows = (
        (
            await webhook_db_session.execute(
                select(Payment).where(
                    Payment.subject_id == seeded_online_payment_pending.membership_plan_id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(payment_rows) == 1
    assert payment_rows[0].method == "online", (
        f"Non-autopay path must record method='online', got '{payment_rows[0].method}'"
    )
