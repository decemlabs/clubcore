"""Structural — SELECT exclusions for find_expiring_candidates (Phase 27).

Parametrized matrix proving that the repository SELECT (raw text() JOIN
against clients) excludes the four known-not-eligible scenarios:

    a) status='cancelled' membership at end_date=today+7d.
    b) status='expired' membership at end_date=today+7d.
    c) Active membership at end_date=today+7d but client.telegram_user_id IS NULL.
    d) Active membership at end_date=today+7d for soft-deleted client
       (clients.deleted_at IS NOT NULL).

Each case asserts: helper returns 0; sender_stub.calls is empty; no row inserted.

Per D-27-21 explicit today injection.
Per D-27-22 sender module stubbed.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.telegram import copy as telegram_copy
from app.modules.clients.models import Client
from app.modules.memberships import service as memberships_service
from app.modules.memberships.models import Membership, MembershipNotification


@pytest.mark.parametrize(
    "scenario",
    [
        "status_cancelled",
        "status_expired",
        "telegram_unlinked",
        "client_soft_deleted",
    ],
)
async def test_select_exclusions(
    scenario: str,
    db_session: AsyncSession,
    notifications_session_factory: Any,
    fake_bot: object,
    sender_stub: Any,
    make_plan: Any,
    make_membership: Any,
    make_client_with_telegram: Any,
    make_client_no_telegram: Any,
) -> None:
    sender_module, sender_state = sender_stub

    today = date(2026, 6, 1)
    plan = await make_plan(name=f"Phase 27 NTF-EXCL {scenario}")

    if scenario == "telegram_unlinked":
        client_id = await make_client_no_telegram()
    else:
        client_id = await make_client_with_telegram(
            telegram_user_id=400_000 + hash(scenario) % 100_000,
        )

    m = await make_membership(
        client_id=client_id,
        plan=plan,
        status="active",
        start_date=today - timedelta(days=23),
        end_date=today + timedelta(days=7),
    )

    if scenario == "status_cancelled":
        await db_session.execute(
            update(Membership).where(Membership.id == m.id).values(status="cancelled")
        )
        await db_session.commit()
    elif scenario == "status_expired":
        await db_session.execute(
            update(Membership).where(Membership.id == m.id).values(status="expired")
        )
        await db_session.commit()
    elif scenario == "client_soft_deleted":
        await db_session.execute(
            update(Client)
            .where(Client.id == client_id)
            .values(deleted_at=datetime.now(tz=UTC))
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
    assert sender_state.calls == []

    notifs = (
        await db_session.execute(
            select(MembershipNotification).where(
                MembershipNotification.membership_id == m.id
            )
        )
    ).scalars().all()
    assert notifs == []
