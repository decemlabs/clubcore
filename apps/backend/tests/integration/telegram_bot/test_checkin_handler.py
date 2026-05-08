"""Integration tests for /checkin handler (Phase 20 AUTH-TG-08, AUTH-TG-10, AUTH-TG-11).

Direct call to checkin_handler(update, context, ctx) with stubbed update/context
and the real Phase 19 service. The 7 cases pin the four ROADMAP success criteria
that are observable from the user perspective (DM string per branch + audit row +
replay-silent + Redis-outage-fail-open).

Phase 22 D-22-11: the happy-path DM now includes days_remaining. Tests that assert
the success DM use end_date = today + 29 days (default seed) → "Абонемент действует
ещё 29 дн." substring. See test_checkin_dm_days_remaining.py for boundary cases.
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
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs

import app.modules.visits.service as svc_mod
from app.core.audit_models import AuditLog
from app.core.config import get_settings
from app.core.permissions import Role
from app.integrations.telegram import handlers as handlers_mod
from app.integrations.telegram import sender as sender_mod
from app.integrations.telegram.handlers import HandlerContext, checkin_handler
from app.modules.auth import telegram_service
from app.modules.auth.models import User
from app.modules.clients.models import Client
from app.modules.memberships.models import Membership, MembershipPlan
from app.modules.visits import service as visits_service
from app.modules.visits.models import Visit
from tests.conftest import StubTelegramSender

_MSK = ZoneInfo("Europe/Moscow")


def _today_msk() -> date:
    from datetime import datetime

    return datetime.now(_MSK).date()


@pytest.fixture(autouse=True)
def _refresh_handler_logger(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mirror of test_handler_start.py:40-58 — refresh cached module-level logger."""
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
    )


def _open_gym_hours(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch settings to always-open gym hours.

    Phase 20: Settings is NOT frozen (verified at 2026-05-08 — app/core/config.py
    has no `frozen=True` in model_config). monkeypatch.setattr is safe AND undone
    at test teardown.
    """
    settings = get_settings()
    assert not getattr(settings.model_config, "frozen", False), (
        "Settings became frozen — _open_gym_hours must construct a fresh instance "
        "instead of mutating the cached one (see Phase 20 D-20 / 20-03-PLAN.md)."
    )
    monkeypatch.setattr(settings, "gym_hours_start", time(0, 0))
    monkeypatch.setattr(settings, "gym_hours_end", time(23, 59))
    monkeypatch.setattr(svc_mod, "get_settings", lambda: settings)


def _close_gym_hours(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch settings to a closed-window so any wall-clock time is outside."""
    settings = get_settings()
    monkeypatch.setattr(settings, "gym_hours_start", time(0, 0))
    monkeypatch.setattr(settings, "gym_hours_end", time(0, 1))
    monkeypatch.setattr(svc_mod, "get_settings", lambda: settings)


async def _seed_client_with_membership(
    db_session: AsyncSession,
    *,
    telegram_user_id: int,
    end_date: date | None = None,
) -> tuple[Client, Membership]:
    """Inline seed (creator-user, plan, client, active-membership).

    Mirrors `make_visit_setup` from tests/integration/visits/conftest.py — inlined
    here because that fixture is scoped to the visits test package.
    """
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
        active=True,
    )
    db_session.add(plan)
    await db_session.flush()

    phone_suffix = uuid4().int % 10**7
    client = Client(
        last_name=f"Client-{uuid4().hex[:8]}",
        first_name="Test",
        phone=f"+7901{phone_suffix:07d}",
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
        plan_name_snapshot=plan.name,
        start_date=_today_msk() - timedelta(days=1),
        end_date=end_date or (_today_msk() + timedelta(days=29)),
        status="active",
        activation_policy="purchase_date",
    )
    db_session.add(membership)
    await db_session.flush()
    return client, membership


async def _seed_client_no_membership(
    db_session: AsyncSession,
    *,
    telegram_user_id: int,
) -> Client:
    """Seed a Client (with telegram_user_id) but NO membership row."""
    creator = User(
        email=f"setup-owner-{uuid4().hex[:8]}@example.com",
        password_hash="$argon2id$notreal",  # noqa: S106
        role=Role.OWNER,
        full_name="Setup Owner",
    )
    db_session.add(creator)
    await db_session.flush()

    phone_suffix = uuid4().int % 10**7
    client = Client(
        last_name=f"Client-{uuid4().hex[:8]}",
        first_name="Test",
        phone=f"+7902{phone_suffix:07d}",
        telegram_user_id=telegram_user_id,
        created_by_user_id=creator.id,
    )
    db_session.add(client)
    await db_session.flush()
    return client


_CHAT_ID = 555_000_111
_TG_USER_BASE = 70_000_000


# ---------------------------------------------------------------------------
# Test 1: happy path — visit row + visit_created audit + _DM_CHECKIN_OK
# ---------------------------------------------------------------------------


async def test_checkin_happy_path(
    db_session: AsyncSession,
    stub_telegram_sender: StubTelegramSender,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Happy path: handler sends days-remaining DM + visit row + visit_created audit row.

    Default seed: end_date = today + 29 days → days_remaining = 29.
    D-22-11: success DM is now "✅ Отмечено. Абонемент действует ещё {N} дн."
    """
    tg_user_id = _TG_USER_BASE + 1
    chat_id = _CHAT_ID + 1
    _open_gym_hours(monkeypatch)
    client, _membership = await _seed_client_with_membership(
        db_session, telegram_user_id=tg_user_id,
    )

    fake_redis = fakeredis.aioredis.FakeRedis()
    update = _build_update(telegram_user_id=tg_user_id, chat_id=chat_id, update_id=1001)
    ctx = _build_ctx(db_session, fake_redis)
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    await checkin_handler(update, context, ctx)

    # D-22-11: DM now includes days_remaining (29 days with default seed)
    assert len(stub_telegram_sender.text_calls) == 1
    sent_chat_id, sent_text = stub_telegram_sender.text_calls[0]
    assert sent_chat_id == chat_id
    assert "Отмечено" in sent_text
    assert "Абонемент действует ещё" in sent_text

    visits = (
        await db_session.scalars(select(Visit).where(Visit.client_id == client.id))
    ).all()
    assert len(visits) == 1
    assert visits[0].channel == "telegram_bot"
    assert visits[0].checked_in_by is None

    audits = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "visit_created",
                AuditLog.resource_id == visits[0].id,
            )
        )
    ).all()
    assert len(audits) == 1
    assert audits[0].payload["channel"] == "telegram_bot"
    assert audits[0].actor_user_id is None


# ---------------------------------------------------------------------------
# Test 2: no active membership — _DM_NO_MEMBERSHIP + visit_rejected_no_membership
# ---------------------------------------------------------------------------


async def test_checkin_no_active_membership(
    db_session: AsyncSession,
    stub_telegram_sender: StubTelegramSender,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Client linked but no membership: _DM_NO_MEMBERSHIP + visit_rejected_no_membership audit."""
    tg_user_id = _TG_USER_BASE + 2
    chat_id = _CHAT_ID + 2
    _open_gym_hours(monkeypatch)
    client = await _seed_client_no_membership(db_session, telegram_user_id=tg_user_id)
    client_id_str = str(client.id)
    await db_session.commit()

    fake_redis = fakeredis.aioredis.FakeRedis()
    update = _build_update(telegram_user_id=tg_user_id, chat_id=chat_id, update_id=2002)
    ctx = _build_ctx(db_session, fake_redis)
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    await checkin_handler(update, context, ctx)

    expected_dm = (
        "У вас нет активного абонемента. Обратитесь к администратору."  # noqa: RUF001
    )
    assert stub_telegram_sender.text_calls == [(chat_id, expected_dm)]

    rows = (
        await db_session.scalars(
            select(AuditLog).where(AuditLog.action == "visit_rejected_no_membership")
        )
    ).all()
    matching = [r for r in rows if r.payload.get("client_id") == client_id_str]
    assert len(matching) == 1
    assert matching[0].payload["channel"] == "telegram_bot"
    assert matching[0].actor_user_id is None


# ---------------------------------------------------------------------------
# Test 3: duplicate — _DM_DUPLICATE + visit_rejected_duplicate
# ---------------------------------------------------------------------------


async def test_checkin_duplicate(
    db_session: AsyncSession,
    stub_telegram_sender: StubTelegramSender,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pre-seeded today's visit triggers UNIQUE → _DM_DUPLICATE + audit row."""
    from datetime import datetime as _dt

    tg_user_id = _TG_USER_BASE + 3
    chat_id = _CHAT_ID + 3
    _open_gym_hours(monkeypatch)
    client, membership = await _seed_client_with_membership(
        db_session, telegram_user_id=tg_user_id,
    )
    client_id_str = str(client.id)

    pre_visit = Visit(
        client_id=client.id,
        membership_id=membership.id,
        channel="telegram_bot",
        checked_in_at=_dt.now(_MSK),
        checked_in_by=None,
    )
    db_session.add(pre_visit)
    await db_session.commit()

    fake_redis = fakeredis.aioredis.FakeRedis()
    update = _build_update(telegram_user_id=tg_user_id, chat_id=chat_id, update_id=3003)
    ctx = _build_ctx(db_session, fake_redis)
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    await checkin_handler(update, context, ctx)

    assert stub_telegram_sender.text_calls == [(chat_id, "Вы уже отмечались сегодня.")]

    rows = (
        await db_session.scalars(
            select(AuditLog).where(AuditLog.action == "visit_rejected_duplicate")
        )
    ).all()
    matching = [r for r in rows if r.payload.get("client_id") == client_id_str]
    assert len(matching) == 1
    assert matching[0].payload["channel"] == "telegram_bot"
    assert matching[0].actor_user_id is None


# ---------------------------------------------------------------------------
# Test 4: outside hours — _DM_OUTSIDE_HOURS + visit_rejected_outside_hours
# ---------------------------------------------------------------------------


async def test_checkin_outside_hours(
    db_session: AsyncSession,
    stub_telegram_sender: StubTelegramSender,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closed-window monkeypatch → _DM_OUTSIDE_HOURS with U+2013 EN DASH + audit."""
    tg_user_id = _TG_USER_BASE + 4
    chat_id = _CHAT_ID + 4
    _close_gym_hours(monkeypatch)
    client, _membership = await _seed_client_with_membership(
        db_session, telegram_user_id=tg_user_id,
    )
    client_id_str = str(client.id)

    fake_redis = fakeredis.aioredis.FakeRedis()
    update = _build_update(telegram_user_id=tg_user_id, chat_id=chat_id, update_id=4004)
    ctx = _build_ctx(db_session, fake_redis)
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    await checkin_handler(update, context, ctx)

    expected_dm = "Зал сейчас закрыт. Часы работы: 00:00–00:01."  # noqa: RUF001
    assert stub_telegram_sender.text_calls == [(chat_id, expected_dm)]
    # Belt-and-braces: U+2013 EN DASH in the captured DM.
    captured_text = stub_telegram_sender.text_calls[0][1]
    assert "–" in captured_text  # noqa: RUF001 — U+2013 EN DASH

    rows = (
        await db_session.scalars(
            select(AuditLog).where(AuditLog.action == "visit_rejected_outside_hours")
        )
    ).all()
    matching = [r for r in rows if r.payload.get("client_id") == client_id_str]
    assert len(matching) == 1
    assert matching[0].payload["channel"] == "telegram_bot"
    assert matching[0].actor_user_id is None


# ---------------------------------------------------------------------------
# Test 5: client not linked — _DM_NO_MEMBERSHIP (anti-oracle) + telegram_unknown_checkin
# ---------------------------------------------------------------------------


async def test_checkin_client_not_linked(
    db_session: AsyncSession,
    stub_telegram_sender: StubTelegramSender,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown telegram_user_id → _DM_NO_MEMBERSHIP (anti-oracle D-20-9) + handler-emitted audit."""
    tg_user_id = _TG_USER_BASE + 5  # NO row seeded for this id
    chat_id = _CHAT_ID + 5
    _open_gym_hours(monkeypatch)

    fake_redis = fakeredis.aioredis.FakeRedis()
    update = _build_update(telegram_user_id=tg_user_id, chat_id=chat_id, update_id=5005)
    ctx = _build_ctx(db_session, fake_redis)
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    await checkin_handler(update, context, ctx)

    expected_dm = (
        "У вас нет активного абонемента. Обратитесь к администратору."  # noqa: RUF001
    )
    assert stub_telegram_sender.text_calls == [(chat_id, expected_dm)]

    # Handler-emitted telegram_unknown_checkin audit row with hashed tg id.
    rows = (
        await db_session.scalars(
            select(AuditLog).where(AuditLog.action == "telegram_unknown_checkin")
        )
    ).all()
    matching = [r for r in rows if r.payload.get("chat_id") == chat_id]
    assert len(matching) == 1
    row = matching[0]
    assert row.actor_user_id is None
    assert row.resource_type == "visit"
    assert row.resource_id is None
    tg_hash = row.payload["telegram_user_id_hash"]
    assert isinstance(tg_hash, str)
    assert len(tg_hash) == 64
    assert all(c in "0123456789abcdef" for c in tg_hash)

    # Belt-and-braces: NO Visit row created.
    visits = (await db_session.scalars(select(Visit))).all()
    assert len(visits) == 0


# ---------------------------------------------------------------------------
# Test 6: replay silent — second call with same update_id is a no-op
# ---------------------------------------------------------------------------


async def test_checkin_replay_silent(
    db_session: AsyncSession,
    stub_telegram_sender: StubTelegramSender,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Second call with same update_id: no DM, no second visit, structlog bot_replay_skipped."""
    tg_user_id = _TG_USER_BASE + 6
    chat_id = _CHAT_ID + 6
    _open_gym_hours(monkeypatch)
    client, _membership = await _seed_client_with_membership(
        db_session, telegram_user_id=tg_user_id,
    )

    fake_redis = fakeredis.aioredis.FakeRedis()
    update = _build_update(telegram_user_id=tg_user_id, chat_id=chat_id, update_id=42)
    ctx = _build_ctx(db_session, fake_redis)
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    # First call — successful checkin. D-22-11: DM now includes days_remaining.
    await checkin_handler(update, context, ctx)
    assert len(stub_telegram_sender.text_calls) == 1
    assert stub_telegram_sender.text_calls[0][0] == chat_id
    assert "Отмечено" in stub_telegram_sender.text_calls[0][1]
    stub_telegram_sender.text_calls.clear()

    # Second call — same update_id; SET-NX-EX returns None → silent return.
    with capture_logs() as caplog:
        await checkin_handler(update, context, ctx)

    assert stub_telegram_sender.text_calls == []  # no DM on replay

    # Exactly one Visit row total — the dedup prevented even reaching the service.
    visits = (
        await db_session.scalars(select(Visit).where(Visit.client_id == client.id))
    ).all()
    assert len(visits) == 1

    # structlog event bot_replay_skipped emitted with update_id=42.
    matching_events = [
        c for c in caplog if c.get("event") == "bot_replay_skipped" and c.get("update_id") == 42
    ]
    assert len(matching_events) >= 1, f"events={[c.get('event') for c in caplog]}"


# ---------------------------------------------------------------------------
# Test 7: redis outage fail-open — visit row still created
# ---------------------------------------------------------------------------


async def test_checkin_redis_outage_fail_open(
    db_session: AsyncSession,
    stub_telegram_sender: StubTelegramSender,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Redis.set raising ConnectionError → handler proceeds, structlog WARN, visit created."""
    tg_user_id = _TG_USER_BASE + 7
    chat_id = _CHAT_ID + 7
    _open_gym_hours(monkeypatch)
    client, _membership = await _seed_client_with_membership(
        db_session, telegram_user_id=tg_user_id,
    )

    fake_redis = fakeredis.aioredis.FakeRedis()

    async def _raising_set(*_args: Any, **_kwargs: Any) -> Any:
        raise RedisConnectionError("simulated outage")

    monkeypatch.setattr(fake_redis, "set", _raising_set)

    update = _build_update(telegram_user_id=tg_user_id, chat_id=chat_id, update_id=7007)
    ctx = _build_ctx(db_session, fake_redis)
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    with capture_logs() as caplog:
        await checkin_handler(update, context, ctx)

    # Handler still proceeded (fail-open per D-20-3). D-22-11: DM includes days_remaining.
    assert len(stub_telegram_sender.text_calls) == 1
    assert stub_telegram_sender.text_calls[0][0] == chat_id
    assert "Отмечено" in stub_telegram_sender.text_calls[0][1]

    # structlog event bot_redis_dedup_unavailable emitted.
    events = [c.get("event") for c in caplog]
    assert "bot_redis_dedup_unavailable" in events, f"events={events}"

    # Visit row created — DB UNIQUE on (client_id, gym_date) is the real anti-replay invariant.
    visits = (
        await db_session.scalars(select(Visit).where(Visit.client_id == client.id))
    ).all()
    assert len(visits) == 1
