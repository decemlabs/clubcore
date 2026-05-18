"""Integration tests for D-22-11 days-remaining DM on successful check-in.

Phase 22 D-22-11 owner sign-off (Option B — special-case zero):
  days_remaining > 0  → "✅ Отмечено. Абонемент действует ещё {N} дн."
  days_remaining == 0 → "✅ Отмечено. Сегодня — последний день абонемента."

Co-located with test_checkin_handler.py; reuses the same fixture helpers
(_seed_client_with_membership, _build_update, _build_ctx, _open_gym_hours).

Three primary cases:
  1. days_remaining = 5  → days-remaining variant with "5 дн."
  2. days_remaining = 1  → days-remaining variant with "1 дн."
  3. days_remaining = 0  → last-day variant, no day-count in text
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, time, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import fakeredis.aioredis
import pytest
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.visits.service as svc_mod
from app.core.config import get_settings
from app.core.permissions import Role
from app.integrations.telegram import handlers as handlers_mod
from app.integrations.telegram import sender as sender_mod
from app.integrations.telegram.handlers import HandlerContext, checkin_handler
from app.modules.auth import telegram_service
from app.modules.auth.models import User
from app.modules.bookings import service as bookings_service
from app.modules.clients.models import Client
from app.modules.memberships.models import Membership, MembershipPlan
from app.modules.schedule import service as schedule_service
from app.modules.visits import service as visits_service
from tests.conftest import StubTelegramSender

_MSK = ZoneInfo("Europe/Moscow")


def _today_msk() -> date:
    from datetime import datetime

    return datetime.now(_MSK).date()


@pytest.fixture(autouse=True)
def _refresh_handler_logger(monkeypatch: pytest.MonkeyPatch) -> None:
    """Refresh cached module-level logger (mirrors test_checkin_handler.py)."""
    fresh = structlog.get_logger("telegram.handler")
    monkeypatch.setattr(handlers_mod, "logger", fresh)


def _build_update(*, telegram_user_id: int, chat_id: int, update_id: int) -> SimpleNamespace:
    eff_user = SimpleNamespace(id=telegram_user_id, username=None, is_bot=False)
    eff_chat = SimpleNamespace(id=chat_id, type="private")
    message = SimpleNamespace(text="/checkin", chat=eff_chat, from_user=eff_user)
    return SimpleNamespace(
        update_id=update_id,
        effective_user=eff_user,
        effective_chat=eff_chat,
        message=message,
    )


def _build_ctx(db_session: AsyncSession, redis_client: Any) -> HandlerContext:
    @asynccontextmanager
    async def _factory() -> AsyncIterator[AsyncSession]:
        yield db_session

    return HandlerContext(
        session_factory=_factory,  # type: ignore[arg-type]
        telegram_service=telegram_service,
        sender=sender_mod,
        visits_service=visits_service,
        redis=redis_client,
        bookings_service=bookings_service,
        schedule_service=schedule_service,
    )


def _open_gym_hours(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch settings to always-open gym hours (mirrors test_checkin_handler.py)."""
    settings = get_settings()
    monkeypatch.setattr(settings, "gym_hours_start", time(0, 0))
    monkeypatch.setattr(settings, "gym_hours_end", time(23, 59))
    monkeypatch.setattr(svc_mod, "get_settings", lambda: settings)


async def _seed_client_with_membership(
    db_session: AsyncSession,
    *,
    telegram_user_id: int,
    end_date: date,
) -> tuple[Client, Membership]:
    """Seed client + active membership with a specific end_date (D-22-11 test control)."""
    creator = User(
        email=f"setup-owner-{uuid4().hex[:8]}@example.com",
        password_hash="$argon2id$notreal",  # noqa: S106
        role=Role.OWNER,
        full_name="Setup Owner",
    )
    db_session.add(creator)
    await db_session.flush()

    plan = MembershipPlan(
        name=f"Plan-{uuid4().hex[:8]}",
        duration_days=30,
        price_kopecks=250000,
        freeze_days_limit=14,
        active=True,
    )
    db_session.add(plan)
    await db_session.flush()

    phone_suffix = uuid4().int % 10**7
    client = Client(
        last_name=f"Client-{uuid4().hex[:8]}",
        first_name="Test",
        phone=f"+7903{phone_suffix:07d}",
        telegram_user_id=telegram_user_id,
        created_by_user_id=creator.id,
    )
    db_session.add(client)
    await db_session.flush()

    membership = Membership(
        client_id=client.id,
        plan_id=plan.id,
        duration_days_snapshot=plan.duration_days,
        price_kopecks_snapshot=plan.price_kopecks,
        freeze_days_limit_snapshot=plan.freeze_days_limit,
        plan_name_snapshot=plan.name,
        start_date=_today_msk() - timedelta(days=1),
        end_date=end_date,
        status="active",
        activation_policy="purchase_date",
    )
    db_session.add(membership)
    await db_session.flush()
    return client, membership


_CHAT_ID = 666_000_111
_TG_USER_BASE = 80_000_000


# ---------------------------------------------------------------------------
# Case 1: days_remaining = 5 — days-remaining variant
# ---------------------------------------------------------------------------


async def test_checkin_dm_days_remaining_5(
    db_session: AsyncSession,
    stub_telegram_sender: StubTelegramSender,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """end_date = today + 5 days → DM contains 'Абонемент действует ещё 5 дн.'"""
    tg_user_id = _TG_USER_BASE + 1
    chat_id = _CHAT_ID + 1
    _open_gym_hours(monkeypatch)

    end_date = _today_msk() + timedelta(days=5)
    await _seed_client_with_membership(db_session, telegram_user_id=tg_user_id, end_date=end_date)

    fake_redis = fakeredis.aioredis.FakeRedis()
    update = _build_update(telegram_user_id=tg_user_id, chat_id=chat_id, update_id=10001)
    ctx = _build_ctx(db_session, fake_redis)
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    await checkin_handler(update, context, ctx)

    assert len(stub_telegram_sender.text_calls) == 1
    sent_chat_id, sent_text = stub_telegram_sender.text_calls[0]
    assert sent_chat_id == chat_id
    assert "Абонемент действует ещё 5 дн." in sent_text
    # Must NOT contain last-day copy when days_remaining > 0
    assert "последний день" not in sent_text


# ---------------------------------------------------------------------------
# Case 2: days_remaining = 1 — days-remaining variant (boundary above zero)
# ---------------------------------------------------------------------------


async def test_checkin_dm_days_remaining_1(
    db_session: AsyncSession,
    stub_telegram_sender: StubTelegramSender,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """end_date = today + 1 day → DM contains 'Абонемент действует ещё 1 дн.'"""
    tg_user_id = _TG_USER_BASE + 2
    chat_id = _CHAT_ID + 2
    _open_gym_hours(monkeypatch)

    end_date = _today_msk() + timedelta(days=1)
    await _seed_client_with_membership(db_session, telegram_user_id=tg_user_id, end_date=end_date)

    fake_redis = fakeredis.aioredis.FakeRedis()
    update = _build_update(telegram_user_id=tg_user_id, chat_id=chat_id, update_id=10002)
    ctx = _build_ctx(db_session, fake_redis)
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    await checkin_handler(update, context, ctx)

    assert len(stub_telegram_sender.text_calls) == 1
    sent_chat_id, sent_text = stub_telegram_sender.text_calls[0]
    assert sent_chat_id == chat_id
    assert "Абонемент действует ещё 1 дн." in sent_text
    assert "последний день" not in sent_text


# ---------------------------------------------------------------------------
# Case 3: days_remaining = 0 — last-day variant (INCLUSIVE end_date boundary)
# ---------------------------------------------------------------------------


async def test_checkin_dm_days_remaining_0_last_day(
    db_session: AsyncSession,
    stub_telegram_sender: StubTelegramSender,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """end_date = today (last valid day, INCLUSIVE per Phase 15 Key Decision).

    days_remaining = (today - today).days = 0 → last-day locked string.
    """
    tg_user_id = _TG_USER_BASE + 3
    chat_id = _CHAT_ID + 3
    _open_gym_hours(monkeypatch)

    end_date = _today_msk()  # last valid day — inclusive
    await _seed_client_with_membership(db_session, telegram_user_id=tg_user_id, end_date=end_date)

    fake_redis = fakeredis.aioredis.FakeRedis()
    update = _build_update(telegram_user_id=tg_user_id, chat_id=chat_id, update_id=10003)
    ctx = _build_ctx(db_session, fake_redis)
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    await checkin_handler(update, context, ctx)

    assert len(stub_telegram_sender.text_calls) == 1
    sent_chat_id, sent_text = stub_telegram_sender.text_calls[0]
    assert sent_chat_id == chat_id
    # Locked string: "✅ Отмечено. Сегодня — последний день абонемента."
    assert "Сегодня — последний день абонемента." in sent_text
    # Must NOT contain days count copy when days_remaining == 0
    assert "Абонемент действует ещё" not in sent_text
