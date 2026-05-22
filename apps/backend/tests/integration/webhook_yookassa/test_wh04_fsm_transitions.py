"""WH-04 — FSM guard / illegal transition (Phase 50 success criterion #4 partial).

Illegal-transition POST returns 200 (D-50-17: ЮKassa retries on 4xx — audit-as-
forensic + 200 is the correct telemetry), with an ``yookassa_webhook_received``
audit row whose ``idempotency_outcome='illegal_transition'``.
"""

from __future__ import annotations

from typing import Any

import pytest
import respx
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.online_payments.models import OnlinePayment
from tests.integration.webhook_yookassa.conftest import SeededOnlinePayment


@pytest.mark.asyncio
async def test_wh04_illegal_transition_returns_200_with_audit_row(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    seeded_online_payment_pending: SeededOnlinePayment,
    yookassa_get_payment_succeeded: respx.MockRouter,
    webhook_payment_succeeded_body: Any,
) -> None:
    """Pre-set the OnlinePayment row to 'canceled' (a terminal state) and POST
    payment.succeeded — expect 200 + illegal_transition audit row."""
    # Force the seeded row into a terminal state BEFORE the webhook arrives.
    row = await webhook_db_session.scalar(
        select(OnlinePayment).where(
            OnlinePayment.id == seeded_online_payment_pending.online_payment_id
        )
    )
    assert row is not None
    row.status = "canceled"
    await webhook_db_session.flush()
    await webhook_db_session.commit()

    body = webhook_payment_succeeded_body(
        seeded_online_payment_pending.yookassa_payment_id
    )
    response = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert response.status_code == 200, response.text

    # Status still canceled (no mutation).
    await webhook_db_session.commit()
    after_status = await webhook_db_session.scalar(
        select(OnlinePayment.status).where(
            OnlinePayment.id == seeded_online_payment_pending.online_payment_id
        )
    )
    assert after_status == "canceled"

    # Audit row exists with idempotency_outcome='illegal_transition'.
    rows = (
        await webhook_db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "yookassa_webhook_received",
                AuditLog.resource_id
                == seeded_online_payment_pending.online_payment_id,
            )
        )
    ).scalars().all()
    assert len(rows) >= 1, "expected at least one yookassa_webhook_received audit row"
    outcomes = [r.payload.get("idempotency_outcome") for r in rows]
    assert "illegal_transition" in outcomes, outcomes


@pytest.mark.asyncio
async def test_wh04_legal_pending_to_succeeded(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    seeded_online_payment_pending: SeededOnlinePayment,
    yookassa_get_payment_succeeded: respx.MockRouter,
    webhook_payment_succeeded_body: Any,
) -> None:
    """The legal pending → succeeded transition flips the row to 'succeeded'."""
    body = webhook_payment_succeeded_body(
        seeded_online_payment_pending.yookassa_payment_id
    )
    response = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert response.status_code == 200, response.text

    await webhook_db_session.commit()
    after_status = await webhook_db_session.scalar(
        select(OnlinePayment.status).where(
            OnlinePayment.id == seeded_online_payment_pending.online_payment_id
        )
    )
    assert after_status == "succeeded"


@pytest.mark.asyncio
async def test_wh04_legal_pending_to_canceled(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    seeded_online_payment_pending: SeededOnlinePayment,
    yookassa_get_payment_canceled: respx.MockRouter,
    webhook_payment_canceled_body: Any,
) -> None:
    """The legal pending → canceled transition flips the row to 'canceled'."""
    body = webhook_payment_canceled_body(
        seeded_online_payment_pending.yookassa_payment_id
    )
    response = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert response.status_code == 200, response.text

    await webhook_db_session.commit()
    after_status = await webhook_db_session.scalar(
        select(OnlinePayment.status).where(
            OnlinePayment.id == seeded_online_payment_pending.online_payment_id
        )
    )
    assert after_status == "canceled"


@pytest.mark.asyncio
async def test_wh04_succeeded_terminal_no_re_transition(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    seeded_online_payment_pending: SeededOnlinePayment,
    yookassa_get_payment_succeeded: respx.MockRouter,
    webhook_payment_succeeded_body: Any,
) -> None:
    """A second payment.succeeded against an already-succeeded row is illegal."""
    row = await webhook_db_session.scalar(
        select(OnlinePayment).where(
            OnlinePayment.id == seeded_online_payment_pending.online_payment_id
        )
    )
    assert row is not None
    row.status = "succeeded"
    await webhook_db_session.flush()
    await webhook_db_session.commit()

    body = webhook_payment_succeeded_body(
        seeded_online_payment_pending.yookassa_payment_id
    )
    response = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert response.status_code == 200, response.text

    await webhook_db_session.commit()
    rows = (
        await webhook_db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "yookassa_webhook_received",
                AuditLog.resource_id
                == seeded_online_payment_pending.online_payment_id,
            )
        )
    ).scalars().all()
    outcomes = [r.payload.get("idempotency_outcome") for r in rows]
    assert "illegal_transition" in outcomes, outcomes
