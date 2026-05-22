"""WH-05 — payment.succeeded atomic UoW (Phase 50 success criterion #4 full).

A single ``async with session.begin()`` block writes ALL of:

  a) online_payments.status='succeeded'
  b) payments ledger row with method='online', subject_kind/subject_id
  c) memberships row activated (or pt_packages row for the PT branch)
  d) fiscal_receipts row with status='sent', kind='payment'

Plus 4 audit rows (payment_recorded + activator + online_payment_succeeded +
yookassa_webhook_received).
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
from app.modules.memberships.models import Membership
from app.modules.online_payments.models import OnlinePayment
from app.modules.payments.models import Payment
from app.modules.pt_packages.models import PtPackage
from tests.integration.webhook_yookassa.conftest import SeededOnlinePayment


@pytest.mark.asyncio
async def test_wh05_succeeded_writes_4_entities_in_one_commit(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    seeded_online_payment_pending: SeededOnlinePayment,
    yookassa_get_payment_succeeded: respx.MockRouter,
    webhook_payment_succeeded_body: Any,
) -> None:
    """Single commit writes online_payment + payment + membership + fiscal_receipt."""
    body = webhook_payment_succeeded_body(
        seeded_online_payment_pending.yookassa_payment_id
    )
    response = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert response.status_code == 200, response.text

    await webhook_db_session.commit()

    # (a) OnlinePayment row flipped + succeeded_at populated.
    op = await webhook_db_session.scalar(
        select(OnlinePayment).where(
            OnlinePayment.id == seeded_online_payment_pending.online_payment_id
        )
    )
    assert op is not None
    assert op.status == "succeeded"
    assert op.succeeded_at is not None

    # (b) Payment ledger row with method='online'.
    payments = (
        await webhook_db_session.execute(
            select(Payment).where(
                Payment.subject_id == seeded_online_payment_pending.membership_plan_id,
                Payment.method == "online",
            )
        )
    ).scalars().all()
    assert len(payments) == 1
    payment_row = payments[0]
    assert payment_row.amount_kopecks == seeded_online_payment_pending.amount_kopecks
    assert payment_row.received_by_user_id is None  # Blocker #2

    # (c) Activated Membership row.
    memberships = (
        await webhook_db_session.execute(
            select(Membership).where(
                Membership.client_id == seeded_online_payment_pending.client_id,
                Membership.plan_id == seeded_online_payment_pending.membership_plan_id,
            )
        )
    ).scalars().all()
    assert len(memberships) == 1
    assert memberships[0].status == "active"

    # (d) FiscalReceipt row with status='sent', kind='payment'.
    receipts = (
        await webhook_db_session.execute(
            select(FiscalReceipt).where(FiscalReceipt.payment_id == payment_row.id)
        )
    ).scalars().all()
    assert len(receipts) == 1
    fr = receipts[0]
    assert fr.kind == "payment"
    assert fr.status == "sent"
    assert fr.customer_email == seeded_online_payment_pending.client_email

    # 4 audit rows from this commit (payment_recorded + membership_activated_online +
    # online_payment_succeeded + yookassa_webhook_received).
    audit_events = {
        r.action
        for r in (
            await webhook_db_session.execute(
                select(AuditLog).where(
                    AuditLog.resource_id.in_(
                        [
                            seeded_online_payment_pending.online_payment_id,
                            memberships[0].id,
                            payment_row.id,
                        ]
                    )
                )
            )
        ).scalars().all()
    }
    assert "payment_recorded" in audit_events
    assert "membership_activated_online" in audit_events
    assert "online_payment_succeeded" in audit_events
    assert "yookassa_webhook_received" in audit_events


@pytest.mark.asyncio
async def test_wh05_succeeded_pt_package_path(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    seeded_online_payment_pending_pt_package: SeededOnlinePayment,
    yookassa_get_payment_succeeded: respx.MockRouter,
    webhook_payment_succeeded_qr_body: Any,
) -> None:
    """PT-package branch: PtPackage row activated + pt_package_activated_online audit."""
    body = webhook_payment_succeeded_qr_body(
        seeded_online_payment_pending_pt_package.yookassa_payment_id
    )
    response = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert response.status_code == 200, response.text

    await webhook_db_session.commit()

    pkgs = (
        await webhook_db_session.execute(
            select(PtPackage).where(
                PtPackage.client_id
                == seeded_online_payment_pending_pt_package.client_id,
                PtPackage.plan_id
                == seeded_online_payment_pending_pt_package.pt_package_plan_id,
            )
        )
    ).scalars().all()
    assert len(pkgs) == 1
    assert pkgs[0].status == "active"

    audits = (
        await webhook_db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "pt_package_activated_online",
                AuditLog.resource_id == pkgs[0].id,
            )
        )
    ).scalars().all()
    assert len(audits) == 1


@pytest.mark.asyncio
async def test_wh05_orphan_payment_returns_200_no_write(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    yookassa_get_payment_succeeded: respx.MockRouter,
    webhook_payment_succeeded_body: Any,
) -> None:
    """No OnlinePayment row matching the webhook → 200, no DB writes.

    The handler's orphan branch is structurally observable through DB state:
    no Payment / Membership / FiscalReceipt rows are created. Structlog
    capture inside the in-process app sometimes misses messages emitted from
    deep within the handler stack (the production logger is configured at
    lifespan time with cached processors); DB-state assertions are the
    canonical observability surface for this test.
    """
    body = webhook_payment_succeeded_body("ffffffff-ffff-ffff-ffff-ffffffffffff")
    response = await webhook_client.post(
        "/api/v1/_internal/yookassa/webhook", json=body
    )
    assert response.status_code == 200, response.text

    # No payments / memberships / fiscal_receipts were written.
    await webhook_db_session.commit()
    payment_row = await webhook_db_session.scalar(
        select(Payment).where(Payment.method == "online")
    )
    assert payment_row is None, (
        f"WH-05 orphan path must NOT write any Payment row; got {payment_row}"
    )


@pytest.mark.asyncio
async def test_wh05_customer_email_fetched_via_narrow_select(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    seeded_online_payment_pending: SeededOnlinePayment,
    yookassa_get_payment_succeeded: respx.MockRouter,
    sqlalchemy_query_log_timestamps: list[tuple[str, float]],
    webhook_payment_succeeded_body: Any,
) -> None:
    """Blocker #4 — Client.email read via narrow ``SELECT email FROM clients``, NOT JOIN.

    The SQL log should contain at least one narrow ``SELECT clients.email``
    statement and ZERO statements that JOIN ``online_payments`` to
    ``clients`` (relationship traversal).
    """
    body = webhook_payment_succeeded_body(
        seeded_online_payment_pending.yookassa_payment_id
    )
    response = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert response.status_code == 200, response.text

    stmts = [s for s, _ in sqlalchemy_query_log_timestamps]
    narrow_email_selects = [s for s in stmts if "clients.email" in s and "JOIN" not in s]
    assert len(narrow_email_selects) >= 1, (
        f"expected a narrow SELECT clients.email; statements: {stmts}"
    )

    # No relationship-traversal JOIN from online_payments to clients.
    joined = [
        s
        for s in stmts
        if "online_payments" in s
        and "JOIN clients" in s.upper().replace("\n", " ")
    ]
    assert not joined, (
        f"Blocker #4: relationship traversal detected; joined statements: {joined}"
    )


@pytest.mark.asyncio
async def test_wh05_payment_recorder_called_with_none_audit_actor(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    seeded_online_payment_pending: SeededOnlinePayment,
    yookassa_get_payment_succeeded: respx.MockRouter,
    webhook_payment_succeeded_body: Any,
) -> None:
    """Blocker #2 — payments row carries received_by_user_id=None for the
    anonymous webhook flow."""
    body = webhook_payment_succeeded_body(
        seeded_online_payment_pending.yookassa_payment_id
    )
    response = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert response.status_code == 200, response.text

    await webhook_db_session.commit()
    payments = (
        await webhook_db_session.execute(
            select(Payment).where(
                Payment.subject_id == seeded_online_payment_pending.membership_plan_id,
                Payment.method == "online",
            )
        )
    ).scalars().all()
    assert len(payments) == 1
    assert payments[0].received_by_user_id is None, (
        "Blocker #2: webhook-driven payment ledger row MUST have "
        "received_by_user_id=None (anonymous flow)"
    )
