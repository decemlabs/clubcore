"""Structural — three windows (7d / 3d / 1d) dispatched in one tick (Phase 27).

Three distinct memberships (one per window) must all receive their
corresponding DM in a single helper invocation. Verifies the repository's
CASE-based kind discriminator + the service helper's per-row dispatch
through _emit_send_event's three literal-string branches.

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


async def test_three_kinds_dispatched_in_one_run(
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
    plan = await make_plan(name="Phase 27 NTF-THREE-KINDS Plan")

    c1 = await make_client_with_telegram(telegram_user_id=510_001)
    c2 = await make_client_with_telegram(telegram_user_id=510_002)
    c3 = await make_client_with_telegram(telegram_user_id=510_003)

    m_7d = await make_membership(
        client_id=c1,
        plan=plan,
        status="active",
        start_date=today - timedelta(days=23),
        end_date=today + timedelta(days=7),
    )
    m_3d = await make_membership(
        client_id=c2,
        plan=plan,
        status="active",
        start_date=today - timedelta(days=27),
        end_date=today + timedelta(days=3),
    )
    m_1d = await make_membership(
        client_id=c3,
        plan=plan,
        status="active",
        start_date=today - timedelta(days=29),
        end_date=today + timedelta(days=1),
    )

    count = await memberships_service._send_expiring_notifications(
        notifications_session_factory,
        today=today,
        bot=fake_bot,  # type: ignore[arg-type]
        sender=sender_module,
        copy_module=telegram_copy,
    )

    assert count == 3
    assert len(sender_state.calls) == 3
    chat_ids_called = {c.chat_id for c in sender_state.calls}
    assert chat_ids_called == {510_001, 510_002, 510_003}

    # MembershipNotification rows — one per kind.
    membership_ids = {m_7d.id, m_3d.id, m_1d.id}
    notif_rows = (
        (
            await db_session.execute(
                select(MembershipNotification).where(
                    MembershipNotification.membership_id.in_(membership_ids)
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(notif_rows) == 3
    notif_kinds = {row.kind for row in notif_rows}
    assert notif_kinds == {"expiring_7d", "expiring_3d", "expiring_1d"}

    # AuditLog — three rows, one per locked kind action.
    audits = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action.in_(
                        [
                            "expiring_notification_sent_7d",
                            "expiring_notification_sent_3d",
                            "expiring_notification_sent_1d",
                        ]
                    ),
                    AuditLog.resource_id.in_(membership_ids),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audits) == 3
    actions = {a.action for a in audits}
    assert actions == {
        "expiring_notification_sent_7d",
        "expiring_notification_sent_3d",
        "expiring_notification_sent_1d",
    }
