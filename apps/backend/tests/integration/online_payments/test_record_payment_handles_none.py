"""Integration tests for record_payment None-handling (Phase 50 Plan 50-03 Task 3 / Blocker #2).

Validates:
  - ``record_payment(audit_actor=None, received_by_user_id=None)`` succeeds
    without ``AttributeError`` on ``None.id``.
  - The inserted ``Payment`` row has ``received_by_user_id IS NULL``
    (Alembic 0036 flips the column to nullable).
  - The ``payment_recorded`` audit row has ``actor_user_id IS NULL``
    (system emit per D-41-10 / INFRA-39).
  - Existing in-person sale callers (``audit_actor=<user>``,
    ``received_by_user_id=<uuid>``) continue to work unchanged —
    backward-compat (W-1: this assertion is also fenced earlier by
    Task 1's sweep over tests/integration/memberships/ +
    tests/integration/pt_packages/).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.payments.models import Payment
from app.modules.payments.service import record_payment


pytestmark = pytest.mark.asyncio


async def test_record_payment_with_none_audit_actor_and_none_received_by(
    db_session: AsyncSession,
):
    subject_id = uuid4()
    payment = await record_payment(
        db_session,
        subject_kind="membership",
        subject_id=subject_id,
        amount_kopecks=100000,
        method="online",
        received_by_user_id=None,
        audit_actor=None,
    )
    await db_session.flush()

    assert payment.received_by_user_id is None, (
        "received_by_user_id NULL must round-trip through Alembic 0036's nullability flip"
    )
    assert payment.amount_kopecks == 100000
    assert payment.method == "online"
    assert payment.subject_kind == "membership"
    assert payment.subject_id == subject_id

    rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "payment_recorded",
                    AuditLog.resource_id == payment.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].actor_user_id is None, (
        "system-emit discipline: actor_user_id must be NULL when audit_actor=None"
    )


async def test_record_payment_no_attribute_error_on_none_audit_actor(
    db_session: AsyncSession,
):
    """Regression guard: prior code path called audit_actor.id unconditionally."""
    # If the body still has an unguarded `audit_actor.id` access this raises
    # AttributeError; widening shape must guard the access.
    payment = await record_payment(
        db_session,
        subject_kind="pt_package",
        subject_id=uuid4(),
        amount_kopecks=500000,
        method="online",
        received_by_user_id=None,
        audit_actor=None,
    )
    assert payment is not None


async def test_record_payment_with_full_actor_still_works(
    db_session: AsyncSession,
    make_user,
):
    """Backward-compat — in-person sale callers pass non-None and must
    still see actor_user_id populated."""
    user = await make_user(role="owner")

    payment = await record_payment(
        db_session,
        subject_kind="membership",
        subject_id=uuid4(),
        amount_kopecks=250000,
        method="cash",
        received_by_user_id=user.id,
        audit_actor=user,  # User row also satisfies CurrentUser structurally for the .id access
    )
    await db_session.flush()

    assert payment.received_by_user_id == user.id

    rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "payment_recorded",
                    AuditLog.resource_id == payment.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].actor_user_id == user.id
