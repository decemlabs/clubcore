"""Structural — pre-inserted notification row blocks the SELECT (Phase 27).

Simulates a previous-tick success by pre-inserting a MembershipNotification
row BEFORE calling the helper. The repository's NOT EXISTS subquery on
(membership_id, kind) filters the candidate out; sender is never reached.

Verifies the "single source of truth" idempotency claim made by D-27-15:
the UNIQUE constraint table acts as the cron's idempotency marker, and the
SELECT side actively respects it (independent from the IntegrityError catch
which only fires on race-duplicate write attempts).

Per D-27-21 explicit today injection.
Per D-27-22 sender module stubbed.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.integrations.telegram import copy as telegram_copy
from app.modules.memberships import service as memberships_service
from app.modules.memberships.models import MembershipNotification


async def test_pre_inserted_notification_blocks_send(
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
    plan = await make_plan(name="Phase 27 NTF-IDEMPOTENCY Plan")
    client_id = await make_client_with_telegram(telegram_user_id=678_901)
    m = await make_membership(
        client_id=client_id,
        plan=plan,
        status="active",
        start_date=today - timedelta(days=23),
        end_date=today + timedelta(days=7),
    )

    # Pre-insert the (membership_id, 'expiring_7d') row simulating a
    # previous-tick success. After this, find_expiring_candidates'
    # NOT EXISTS subquery should filter the row out.
    db_session.add(
        MembershipNotification(
            membership_id=m.id,
            kind="expiring_7d",
            telegram_chat_id=999,
        )
    )
    await db_session.commit()

    count = await memberships_service._send_expiring_notifications(
        notifications_session_factory,
        today=today,
        bot=fake_bot,  # type: ignore[arg-type]
        sender=sender_module,
        copy_module=telegram_copy,
    )

    assert count == 0
    assert sender_state.calls == [], (
        "sender must NOT be called when notification row already exists"
    )

    # Still exactly 1 row (pre-inserted, no second one written).
    notifs = (
        await db_session.execute(
            select(MembershipNotification).where(
                MembershipNotification.membership_id == m.id
            )
        )
    ).scalars().all()
    assert len(notifs) == 1
    assert notifs[0].telegram_chat_id == 999  # the pre-inserted row, not a fresh one.

    # No audit row — pre-insert was a manual seed, not a service-driven send.
    audits = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "expiring_notification_sent_7d",
                AuditLog.resource_id == m.id,
            )
        )
    ).scalars().all()
    assert audits == []
