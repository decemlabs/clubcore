"""NTF-TEST-02 — frozen membership not notified (Phase 27).

A frozen membership ending in 7 days MUST NOT receive an expiring DM. The
SELECT in repository.find_expiring_candidates filters status='active' only,
so the row is excluded before the sender is reached. No DM, no row, no audit.

Status is set to 'frozen' via direct ORM update so we don't fire
freeze_membership's freeze-period side effect (which would emit its own
audit row and skew assertions).

Per D-27-21 explicit today injection (Phase 24 D-24-06 — clock-faking libs banned).
Per D-27-22 sender module stubbed.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.integrations.telegram import copy as telegram_copy
from app.modules.memberships import service as memberships_service
from app.modules.memberships.models import Membership, MembershipNotification


async def test_send_expiring_skips_frozen_membership(
    db_session: AsyncSession,
    notifications_session_factory: Any,
    fake_bot: object,
    sender_stub: Any,
    make_plan: Any,
    make_membership: Any,
    make_client_with_telegram: Any,
) -> None:
    sender_module, sender_state = sender_stub

    today = date(2026, 6, 1)
    plan = await make_plan(name="Phase 27 NTF-TEST-02 Plan")
    client_id = await make_client_with_telegram(telegram_user_id=234567)
    m = await make_membership(
        client_id=client_id,
        plan=plan,
        status="active",
        start_date=today - timedelta(days=23),
        end_date=today + timedelta(days=7),
    )

    # Flip status to 'frozen' via direct ORM update — bypasses
    # freeze_membership() side effects (freeze-period row + audit emit).
    await db_session.execute(
        update(Membership).where(Membership.id == m.id).values(status="frozen")
    )
    await db_session.commit()

    count = await memberships_service._send_expiring_notifications(
        notifications_session_factory,
        today=today,
        bot=fake_bot,  # type: ignore[arg-type]  # sentinel — sender stub never reaches into it
        sender=sender_module,
        copy_module=telegram_copy,
    )

    assert count == 0
    assert sender_state.calls == []

    notifs = (
        (
            await db_session.execute(
                select(MembershipNotification).where(MembershipNotification.membership_id == m.id)
            )
        )
        .scalars()
        .all()
    )
    assert notifs == []

    audits = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "expiring_notification_sent_7d",
                    AuditLog.resource_id == m.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert audits == []
