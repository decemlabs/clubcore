"""NTF-TEST-01 — 7d happy path + idempotent re-run (Phase 27).

Calls the service helper directly with explicit today=date(2026, 6, 1) and a
membership ending 7 days later. First call sends 1 DM, inserts 1 notification
row, emits 1 audit. Second call with same today returns 0 (NOT EXISTS subquery
in repository.find_expiring_candidates filters the already-notified row out;
sender never reached again).

Per D-27-21: explicit today injection (Phase 24 D-24-06 — clock-faking libs banned).
Per D-27-22: sender module stubbed at fixture level (no real Telegram traffic).
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


async def test_send_expiring_7d_happy_path_then_idempotent(
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
    plan = await make_plan(name="Phase 27 NTF-TEST-01 Plan")
    client_id = await make_client_with_telegram(telegram_user_id=123456)
    m = await make_membership(
        client_id=client_id,
        plan=plan,
        status="active",
        start_date=today - timedelta(days=23),
        end_date=today + timedelta(days=7),
    )

    # First tick — should send 1 DM, insert 1 row, emit 1 audit.
    count = await memberships_service._send_expiring_notifications(
        notifications_session_factory,
        today=today,
        bot=fake_bot,  # type: ignore[arg-type]  # sentinel — sender stub never reaches into it
        sender=sender_module,
        copy_module=telegram_copy,
    )

    assert count == 1
    assert len(sender_state.calls) == 1
    assert sender_state.calls[0].chat_id == 123456

    # Notification row.
    notif_rows = (
        await db_session.execute(
            select(MembershipNotification).where(
                MembershipNotification.membership_id == m.id
            )
        )
    ).scalars().all()
    assert len(notif_rows) == 1
    assert notif_rows[0].kind == "expiring_7d"
    assert notif_rows[0].telegram_chat_id == 123456

    # Audit row.
    audits = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "expiring_notification_sent_7d",
                AuditLog.resource_id == m.id,
            )
        )
    ).scalars().all()
    assert len(audits) == 1
    assert audits[0].resource_type == "membership"
    assert audits[0].actor_user_id is None
    assert audits[0].payload == {
        "client_id": str(client_id),
        "telegram_chat_id": 123456,
        "kind": "expiring_7d",
        "channel": "telegram",
    }

    # Second tick — same today; UNIQUE / NOT EXISTS catches the candidate at
    # the SELECT level, sender is never reached.
    count_2 = await memberships_service._send_expiring_notifications(
        notifications_session_factory,
        today=today,
        bot=fake_bot,  # type: ignore[arg-type]  # sentinel — sender stub never reaches into it
        sender=sender_module,
        copy_module=telegram_copy,
    )
    assert count_2 == 0
    assert len(sender_state.calls) == 1, "sender must NOT be called on idempotent re-run"

    # Still exactly one notification row + one audit row.
    notif_rows_2 = (
        await db_session.execute(
            select(MembershipNotification).where(
                MembershipNotification.membership_id == m.id
            )
        )
    ).scalars().all()
    assert len(notif_rows_2) == 1

    audits_2 = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "expiring_notification_sent_7d",
                AuditLog.resource_id == m.id,
            )
        )
    ).scalars().all()
    assert len(audits_2) == 1
