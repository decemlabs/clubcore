"""Integration tests for activator body fills (Phase 50 Plan 50-03 Task 2 / D-50-22, D-50-24).

Validates:
  - ``activate_membership_from_webhook`` SELECTs the OnlinePayment seed,
    INSERTs a Membership row with ``status='active'`` and snapshot fields
    sourced from the resolved MembershipPlan, and emits exactly ONE
    LOCKED audit event ``membership_activated_online`` (Blocker #6 —
    NOT ``membership_created``).
  - ``activate_pt_package_from_webhook`` mirrors the above for PtPackage.
  - Both activators raise on missing OnlinePayment + on subject-kind
    mismatch (a Membership activator called against a PT-package
    OnlinePayment row must reject, and vice versa) — defense in depth
    on top of Plan 50-04 handler dispatch (T-50-03-06 mitigation).
  - System-emit discipline: activator runs without a CurrentUser so the
    audit row's ``actor_user_id`` must be NULL (D-41-10 / INFRA-39).
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.memberships.service import activate_membership_from_webhook
from app.modules.online_payments.models import OnlinePayment
from app.modules.pt_packages.service import activate_pt_package_from_webhook


async def _seed_online_payment(
    session: AsyncSession,
    *,
    client_id,
    membership_plan_id=None,
    pt_package_plan_id=None,
    amount_kopecks: int = 250000,
    status: str = "succeeded",
) -> OnlinePayment:
    """Seed an OnlinePayment row matching the shape Phase 49 sell flow writes."""
    op = OnlinePayment(
        client_id=client_id,
        membership_plan_id=membership_plan_id,
        pt_package_plan_id=pt_package_plan_id,
        yookassa_payment_id=f"test-yk-{uuid4().hex[:12]}",
        idempotency_key=f"test-idem-{uuid4().hex}",
        amount_kopecks=amount_kopecks,
        status=status,
        confirmation_type="redirect",
        confirmation_url="https://yookassa.test/confirm",
        succeeded_at=(
            datetime.now(ZoneInfo("Europe/Moscow")) if status == "succeeded" else None
        ),
        audit_correlation_id=uuid4(),
    )
    session.add(op)
    await session.flush()
    await session.refresh(op)
    return op


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Membership activator tests
# ---------------------------------------------------------------------------


async def test_activate_membership_from_webhook_inserts_membership_and_emits_locked_event(
    db_session: AsyncSession,
    make_client_with_email,
    make_membership_plan,
):
    plan = await make_membership_plan()
    client = await make_client_with_email()
    op = await _seed_online_payment(
        db_session,
        client_id=client.id,
        membership_plan_id=plan.id,
        amount_kopecks=plan.price_kopecks,
    )

    membership = await activate_membership_from_webhook(
        db_session,
        online_payment_id=op.id,
        audit_correlation_id=op.audit_correlation_id,
    )
    await db_session.flush()

    assert membership.status == "active"
    assert membership.client_id == client.id
    assert membership.plan_id == plan.id
    assert membership.plan_name_snapshot == plan.name
    assert membership.price_kopecks_snapshot == plan.price_kopecks
    assert membership.duration_days_snapshot == plan.duration_days
    assert membership.freeze_days_limit_snapshot == plan.freeze_days_limit

    # Audit assertion: exactly ONE membership_activated_online row (Blocker #6).
    rows = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "membership_activated_online",
                AuditLog.resource_id == membership.id,
            )
        )
    ).scalars().all()
    assert len(rows) == 1, (
        f"expected exactly 1 membership_activated_online row, got {len(rows)}"
    )

    # ZERO membership_created rows (Blocker #6 — that locked event is reserved
    # for the in-person sell flow; the activator must NOT emit it).
    created_rows = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "membership_created",
                AuditLog.resource_id == membership.id,
            )
        )
    ).scalars().all()
    assert len(created_rows) == 0, (
        f"Blocker #6: activator must NOT emit membership_created — got {len(created_rows)} rows"
    )

    # System emit: actor_user_id is NULL (webhook flow has no operator).
    assert rows[0].actor_user_id is None, (
        "system-emit discipline: actor_user_id must be NULL for webhook activation"
    )


async def test_activate_membership_from_webhook_raises_on_missing_online_payment(
    db_session: AsyncSession,
):
    bogus_id = uuid4()
    with pytest.raises(Exception):
        await activate_membership_from_webhook(
            db_session,
            online_payment_id=bogus_id,
            audit_correlation_id=None,
        )


async def test_activate_membership_from_webhook_rejects_pt_package_online_payment(
    db_session: AsyncSession,
    make_client_with_email,
    make_pt_package_plan,
):
    pt_plan = await make_pt_package_plan()
    client = await make_client_with_email()
    op = await _seed_online_payment(
        db_session,
        client_id=client.id,
        pt_package_plan_id=pt_plan.id,
        amount_kopecks=pt_plan.price_kopecks,
    )

    with pytest.raises(Exception):
        await activate_membership_from_webhook(
            db_session,
            online_payment_id=op.id,
            audit_correlation_id=op.audit_correlation_id,
        )


# ---------------------------------------------------------------------------
# PtPackage activator tests
# ---------------------------------------------------------------------------


async def test_activate_pt_package_from_webhook_inserts_pt_package_and_emits_locked_event(
    db_session: AsyncSession,
    make_client_with_email,
    make_pt_package_plan,
):
    plan = await make_pt_package_plan()
    client = await make_client_with_email()
    op = await _seed_online_payment(
        db_session,
        client_id=client.id,
        pt_package_plan_id=plan.id,
        amount_kopecks=plan.price_kopecks,
    )

    pt_package = await activate_pt_package_from_webhook(
        db_session,
        online_payment_id=op.id,
        audit_correlation_id=op.audit_correlation_id,
    )
    await db_session.flush()

    assert pt_package.status == "active"
    assert pt_package.client_id == client.id
    assert pt_package.plan_id == plan.id
    assert pt_package.plan_name_snapshot == plan.name
    assert pt_package.price_kopecks_snapshot == plan.price_kopecks
    assert pt_package.session_count_snapshot == plan.session_count
    assert pt_package.sessions_remaining == plan.session_count

    rows = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "pt_package_activated_online",
                AuditLog.resource_id == pt_package.id,
            )
        )
    ).scalars().all()
    assert len(rows) == 1

    # Blocker #6 — activator must NOT emit pt_package_sold.
    sold_rows = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "pt_package_sold",
                AuditLog.resource_id == pt_package.id,
            )
        )
    ).scalars().all()
    assert len(sold_rows) == 0

    assert rows[0].actor_user_id is None


async def test_activate_pt_package_from_webhook_rejects_membership_online_payment(
    db_session: AsyncSession,
    make_client_with_email,
    make_membership_plan,
):
    mem_plan = await make_membership_plan()
    client = await make_client_with_email()
    op = await _seed_online_payment(
        db_session,
        client_id=client.id,
        membership_plan_id=mem_plan.id,
        amount_kopecks=mem_plan.price_kopecks,
    )

    with pytest.raises(Exception):
        await activate_pt_package_from_webhook(
            db_session,
            online_payment_id=op.id,
            audit_correlation_id=op.audit_correlation_id,
        )
