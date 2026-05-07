"""Integration tests for visits self-check-in bot path (VIS-04, D-04, D-12).

Calls `service.create_visit_self_checkin(session, telegram_user_id, chat_id)` directly
(no Phase 20 bot worker needed). Covers all 4 rejection paths + success.

Assertions:
- channel='telegram_bot', checked_in_by IS None, actor_user_id IS NULL in audit row
- All anti-fraud rejections work identically to the reception path (shared D-04 chain)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.core.exceptions import (
    ClientNotLinkedError,
    DuplicateCheckinError,
    NoActiveMembershipError,
    OutsideGymHoursError,
)
from app.modules.clients.models import Client
from app.modules.visits import service
from app.modules.visits.models import Visit

_MSK = ZoneInfo("Europe/Moscow")

# Telegram user id used across self-checkin tests
_TG_USER_ID = 12345678
_CHAT_ID = 99999999


# ── Happy path ────────────────────────────────────────────────────────────────


async def test_self_checkin_happy_path(
    db_session: AsyncSession,
    app: Any,
    make_visit_setup: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """VIS-04 happy path: channel='telegram_bot', checked_in_by IS None, actor IS NULL."""
    from datetime import time

    import app.modules.visits.service as svc_mod
    from app.core.config import get_settings

    # Monkeypatch gym hours to always-open so this test passes at any wall-clock time
    settings = get_settings()
    monkeypatch.setattr(settings, "gym_hours_start", time(0, 0))
    monkeypatch.setattr(settings, "gym_hours_end", time(23, 59))
    monkeypatch.setattr(svc_mod, "get_settings", lambda: settings)

    _client_obj, _membership = await make_visit_setup(telegram_user_id=_TG_USER_ID)

    result = await service.create_visit_self_checkin(
        db_session, telegram_user_id=_TG_USER_ID, chat_id=_CHAT_ID
    )

    assert result.channel == "telegram_bot"
    assert result.checked_in_by is None

    # Verify audit row
    row = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "visit_created",
            AuditLog.resource_id == result.id,
        )
    )
    assert row is not None
    assert row.actor_user_id is None  # D-12: bot path has no actor
    assert row.resource_type == "visit"
    assert row.payload["channel"] == "telegram_bot"


# ── ClientNotLinkedError — no audit row (D-12) ────────────────────────────────


async def test_self_checkin_unknown_telegram_id_raises_client_not_linked(
    db_session: AsyncSession,
    app: Any,
) -> None:
    """D-12: unknown telegram_user_id => ClientNotLinkedError; NO audit row emitted.

    Phase 20 owns the `telegram_unknown_checkin` event. Phase 19 raises cleanly
    without audit (D-12 explicitly).
    """
    unknown_tg_id = 99999999

    with pytest.raises(ClientNotLinkedError):
        await service.create_visit_self_checkin(
            db_session, telegram_user_id=unknown_tg_id, chat_id=_CHAT_ID
        )

    # Assert NO audit row was written for the unknown tg_id
    # (Phase 20 owns telegram_unknown_checkin; Phase 19 raises with zero side effects)
    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "visit_rejected_no_membership"
            )
        )
    ).all()
    # No rows should exist in this SAVEPOINT context
    assert len(rows) == 0, (
        "D-12 violated: audit row was written for unknown telegram_user_id"
    )


# ── Outside gym hours via direct service call ─────────────────────────────────


async def test_self_checkin_outside_hours(
    db_session: AsyncSession,
    app: Any,
    make_visit_setup: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bot path outside hours: OutsideGymHoursError; audit actor_user_id IS NULL."""
    from datetime import time

    import app.modules.visits.service as svc_mod
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "gym_hours_start", time(0, 0))
    monkeypatch.setattr(settings, "gym_hours_end", time(0, 1))
    monkeypatch.setattr(svc_mod, "get_settings", lambda: settings)

    tg_id = _TG_USER_ID + 1
    client_obj, _membership = await make_visit_setup(telegram_user_id=tg_id)
    client_id_str = str(client_obj.id)  # capture before any rollback

    with pytest.raises(OutsideGymHoursError):
        await service.create_visit_self_checkin(
            db_session, telegram_user_id=tg_id, chat_id=_CHAT_ID
        )

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "visit_rejected_outside_hours",
            )
        )
    ).all()
    matching = [r for r in rows if r.payload.get("client_id") == client_id_str]
    assert len(matching) == 1
    row = matching[0]
    assert row.actor_user_id is None  # bot path: no actor
    assert row.payload["channel"] == "telegram_bot"


# ── Duplicate check-in via direct service call ────────────────────────────────


async def test_self_checkin_duplicate(
    db_session: AsyncSession,
    app: Any,
    make_visit_setup: Any,
    seeded_owner: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bot path duplicate: DuplicateCheckinError; audit channel='telegram_bot'."""
    from datetime import time

    import app.modules.visits.service as svc_mod
    from app.core.config import get_settings

    # Open gym so the service reaches the duplicate check (not outside_hours)
    settings = get_settings()
    monkeypatch.setattr(settings, "gym_hours_start", time(0, 0))
    monkeypatch.setattr(settings, "gym_hours_end", time(23, 59))
    monkeypatch.setattr(svc_mod, "get_settings", lambda: settings)

    tg_id = _TG_USER_ID + 2
    client_obj, membership = await make_visit_setup(telegram_user_id=tg_id)
    client_id_str = str(client_obj.id)  # capture before session expires obj

    # Pre-insert today's visit to trigger UNIQUE constraint
    now_msk = datetime.now(_MSK)
    visit = Visit(
        client_id=client_obj.id,
        membership_id=membership.id,
        channel="telegram_bot",
        checked_in_at=now_msk,
        checked_in_by=None,
    )
    db_session.add(visit)
    await db_session.commit()

    with pytest.raises(DuplicateCheckinError):
        await service.create_visit_self_checkin(
            db_session, telegram_user_id=tg_id, chat_id=_CHAT_ID
        )

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "visit_rejected_duplicate",
            )
        )
    ).all()
    matching = [r for r in rows if r.payload.get("client_id") == client_id_str]
    assert len(matching) == 1
    assert matching[0].payload["channel"] == "telegram_bot"
    assert matching[0].actor_user_id is None


# ── No active membership via direct service call ──────────────────────────────


async def test_self_checkin_no_membership(
    db_session: AsyncSession,
    app: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bot path no membership: NoActiveMembershipError; audit channel='telegram_bot'."""
    from datetime import time

    import app.modules.visits.service as svc_mod
    from app.core.config import get_settings
    from app.core.permissions import Role
    from app.core.security import hash_password
    from app.modules.auth.models import User as _User

    # Open gym so the service reaches the membership check (not outside_hours)
    settings = get_settings()
    monkeypatch.setattr(settings, "gym_hours_start", time(0, 0))
    monkeypatch.setattr(settings, "gym_hours_end", time(23, 59))
    monkeypatch.setattr(svc_mod, "get_settings", lambda: settings)

    tg_id = _TG_USER_ID + 3
    # Seed a creator user for the required FK
    creator = _User(
        email=f"sci-nm-{uuid4().hex[:8]}@example.com",
        password_hash=await hash_password("test123456789"),
        role=Role.OWNER,
        full_name="SCI Creator",
    )
    db_session.add(creator)
    await db_session.flush()

    phone_suffix = uuid4().int % 10**7
    c = Client(
        last_name=f"SCI-NM-{uuid4().hex[:8]}",
        first_name="Test",
        phone=f"+7905{phone_suffix:07d}",
        telegram_user_id=tg_id,
        created_by_user_id=creator.id,
    )
    db_session.add(c)
    await db_session.flush()
    c_id_str = str(c.id)  # capture before session expires obj
    await db_session.commit()

    with pytest.raises(NoActiveMembershipError):
        await service.create_visit_self_checkin(
            db_session, telegram_user_id=tg_id, chat_id=_CHAT_ID
        )

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "visit_rejected_no_membership",
            )
        )
    ).all()
    matching = [r for r in rows if r.payload.get("client_id") == c_id_str]
    assert len(matching) == 1
    assert matching[0].payload["channel"] == "telegram_bot"
    assert matching[0].actor_user_id is None
