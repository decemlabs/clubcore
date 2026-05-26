"""NTF-TEST-03 — 403 (bot blocked) → retry → success → idempotency catch (Phase 27).

Tick 1: sender returns blocked=True (403). Per D-27-14, the helper logs a
WARNING and skips — NO MembershipNotification row, NO AuditLog row. Helper
returns 0.

Tick 2: same today, sender now returns SendResult(ok=True). The candidate is
re-selected (no notification row exists yet), DM sends, row inserted, audit
emitted. Helper returns 1; sender now seen 2 calls (one failure, one success).

Tick 3: same today, candidate now blocked by NOT EXISTS subquery. Helper
returns 0; sender_stub.calls unchanged (length 2).

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
from app.integrations.telegram.sender import SendResult
from app.modules.memberships import service as memberships_service
from app.modules.memberships.models import MembershipNotification


async def test_send_403_then_retry_then_idempotent(
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
    plan = await make_plan(name="Phase 27 NTF-TEST-03 Plan")
    client_id = await make_client_with_telegram(telegram_user_id=345678)
    m = await make_membership(
        client_id=client_id,
        plan=plan,
        status="active",
        start_date=today - timedelta(days=23),
        end_date=today + timedelta(days=7),
    )

    # Tick 1 — bot blocked.
    sender_state.queue(SendResult(ok=False, blocked=True))
    count_1 = await memberships_service._send_expiring_notifications(
        notifications_session_factory,
        today=today,
        bot=fake_bot,  # type: ignore[arg-type]
        sender=sender_module,
        copy_module=telegram_copy,
    )
    assert count_1 == 0
    assert len(sender_state.calls) == 1
    assert sender_state.calls[0].chat_id == 345678

    notifs_after_1 = (
        (
            await db_session.execute(
                select(MembershipNotification).where(MembershipNotification.membership_id == m.id)
            )
        )
        .scalars()
        .all()
    )
    assert notifs_after_1 == []

    audits_after_1 = (
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
    assert audits_after_1 == []

    # Tick 2 — queue empty, default ok=True applies. Candidate is still
    # eligible (no notification row was inserted on tick 1).
    sender_state.set_default(SendResult(ok=True))
    count_2 = await memberships_service._send_expiring_notifications(
        notifications_session_factory,
        today=today,
        bot=fake_bot,  # type: ignore[arg-type]
        sender=sender_module,
        copy_module=telegram_copy,
    )
    assert count_2 == 1
    assert len(sender_state.calls) == 2
    assert sender_state.calls[1].chat_id == 345678

    notifs_after_2 = (
        (
            await db_session.execute(
                select(MembershipNotification).where(MembershipNotification.membership_id == m.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(notifs_after_2) == 1
    assert notifs_after_2[0].kind == "expiring_7d"

    audits_after_2 = (
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
    assert len(audits_after_2) == 1

    # Tick 3 — idempotency catches the now-locked (membership_id, '7d') pair.
    count_3 = await memberships_service._send_expiring_notifications(
        notifications_session_factory,
        today=today,
        bot=fake_bot,  # type: ignore[arg-type]
        sender=sender_module,
        copy_module=telegram_copy,
    )
    assert count_3 == 0
    assert len(sender_state.calls) == 2  # unchanged — sender not re-called.
