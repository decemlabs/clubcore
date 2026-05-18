"""Phase 40 BOT-01 / BOT-02 — /book command handler integration tests.

Direct invocation of ``book_handler(update, context, ctx)`` with stubbed
``update`` / ``context`` and the real Phase 40 ``create_booking_via_bot``
service + Phase 38 ``list_slots`` reachable via ``ctx.schedule_service``.

Cases pinned:
  - Keyboard render with up to 5 buttons (1 button per row) + callback_data
    shape "BK:{uuid36}" exactly 39 bytes (< 64-byte Telegram cap).
  - Anti-oracle (C-12) — 3 denial paths reply with byte-identical
    ``_BOT_BOOK_DENIED_DM`` and NO ``reply_markup``:
      1. telegram_user_id resolves to no Client.
      2. Client has no active PT-package.
      3. Client + active package but ``list_slots`` returns 0 items.
  - Update-id dedup: replay of same update_id is silent (Phase 40 D-40-08).
  - Keyboard label shape — "DD.MM HH:MM — {trainer_full_name}".

Sender widening (WARNING-4) is verified end-to-end through the keyboard test
(``send_text_dm(..., reply_markup=...)`` is invoked and the captured
markup is asserted non-None). The unit-level kwarg-acceptance test for
``send_text_dm`` lives in ``tests/unit/integrations/telegram/test_sender.py``
(created by this plan as well).

The fixtures + factory pattern mirrors ``tests/integration/telegram_bot/test_checkin_handler.py``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import fakeredis.aioredis
import pytest
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import InlineKeyboardMarkup

from app.core.permissions import Role
from app.integrations.telegram import handlers as handlers_mod
from app.integrations.telegram.handlers import HandlerContext, book_handler
from app.modules.auth import telegram_service
from app.modules.auth.models import User
from app.modules.bookings import service as bookings_service_mod
from app.modules.bookings.notifications import _BOT_BOOK_DENIED_DM
from app.modules.clients.models import Client
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.schedule import service as schedule_service_mod
from app.modules.schedule.models import TrainerAvailabilitySlot
from app.modules.trainers.models import Trainer
from app.modules.visits import service as visits_service_mod
from tests.conftest import StubTelegramSender


@pytest.fixture(autouse=True)
def _refresh_handler_logger(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mirror of test_checkin_handler — refresh cached module-level logger."""
    fresh = structlog.get_logger("telegram.handler")
    monkeypatch.setattr(handlers_mod, "logger", fresh)


def _build_update(*, telegram_user_id: int, chat_id: int, update_id: int) -> SimpleNamespace:
    eff_user = SimpleNamespace(id=telegram_user_id, username=None, is_bot=False)
    eff_chat = SimpleNamespace(id=chat_id, type="private")
    message = SimpleNamespace(text="/book", chat=eff_chat, from_user=eff_user)
    return SimpleNamespace(
        update_id=update_id,
        effective_user=eff_user,
        effective_chat=eff_chat,
        message=message,
    )


def _build_ctx(
    db_session: AsyncSession,
    redis_client: Any,
    sender_module: Any,
) -> HandlerContext:
    """Build a HandlerContext bound to the SAVEPOINT-mode session."""

    @asynccontextmanager
    async def _factory() -> AsyncIterator[AsyncSession]:
        yield db_session

    return HandlerContext(
        session_factory=_factory,  # type: ignore[arg-type]
        telegram_service=telegram_service,
        sender=sender_module,
        visits_service=visits_service_mod,
        redis=redis_client,
        bookings_service=bookings_service_mod,
        schedule_service=schedule_service_mod,
    )


async def _seed_user(db_session: AsyncSession) -> User:
    user = User(
        email=f"book-owner-{uuid4().hex[:8]}@example.com",
        password_hash="$argon2id$notreal",  # noqa: S106
        role=Role.OWNER,
        full_name="Setup Owner",
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _seed_linked_client(
    db_session: AsyncSession,
    *,
    telegram_user_id: int,
    creator: User,
) -> Client:
    client = Client(
        last_name=f"Client-{uuid4().hex[:8]}",
        first_name="Иван",
        phone=f"+79051{uuid4().int % 10**7:07d}",
        telegram_user_id=telegram_user_id,
        created_by_user_id=creator.id,
    )
    db_session.add(client)
    await db_session.flush()
    return client


async def _seed_trainer(db_session: AsyncSession, full_name: str = "Анна Петрова") -> Trainer:
    trainer = Trainer(full_name=full_name, phone=None, is_active=True)
    db_session.add(trainer)
    await db_session.flush()
    return trainer


async def _seed_active_pt_package(
    db_session: AsyncSession,
    *,
    client: Client,
    sessions_remaining: int = 5,
) -> PtPackage:
    plan = PtPackagePlan(
        name=f"BookPlan-{uuid4().hex[:8]}",
        session_count=10,
        price_kopecks=500000,
        validity_days=90,
    )
    db_session.add(plan)
    await db_session.flush()
    today = datetime.now(tz=UTC).date()
    pkg = PtPackage(
        client_id=client.id,
        plan_id=plan.id,
        plan_name_snapshot=plan.name,
        session_count_snapshot=plan.session_count,
        price_kopecks_snapshot=plan.price_kopecks,
        validity_days_snapshot=plan.validity_days,
        sessions_remaining=sessions_remaining,
        status="active",
        start_date=today,
        end_date=today + timedelta(days=89),
    )
    db_session.add(pkg)
    await db_session.flush()
    return pkg


async def _seed_slot(
    db_session: AsyncSession,
    *,
    trainer: Trainer,
    creator: User,
    start_offset: timedelta = timedelta(hours=2),
) -> TrainerAvailabilitySlot:
    start = datetime.now(UTC) + start_offset
    slot = TrainerAvailabilitySlot(
        trainer_id=trainer.id,
        start_time=start,
        end_time=start + timedelta(hours=1),
        status="active",
        created_by_user_id=creator.id,
    )
    db_session.add(slot)
    await db_session.flush()
    return slot


_TG_USER_BASE = 80_000_000
_CHAT_BASE = 666_000_000


# ---------------------------------------------------------------------------
# Test 1: keyboard render — up to 5 buttons + callback_data byte length < 64
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_book_handler_renders_up_to_5_slot_keyboard(
    db_session: AsyncSession,
    stub_telegram_sender: StubTelegramSender,
) -> None:
    """Active pt_package + 8 future active slots → 5 buttons rendered, each
    button on its own row, callback_data "BK:{uuid}" exactly 39 bytes."""
    tg_user_id = _TG_USER_BASE + 1
    chat_id = _CHAT_BASE + 1
    creator = await _seed_user(db_session)
    client = await _seed_linked_client(
        db_session, telegram_user_id=tg_user_id, creator=creator,
    )
    trainer = await _seed_trainer(db_session, full_name="Иван Тренеров")
    await _seed_active_pt_package(db_session, client=client)
    for i in range(8):
        await _seed_slot(
            db_session,
            trainer=trainer,
            creator=creator,
            start_offset=timedelta(hours=2 + i),
        )

    fake_redis = fakeredis.aioredis.FakeRedis()
    from app.integrations.telegram import sender as sender_mod
    update = _build_update(
        telegram_user_id=tg_user_id, chat_id=chat_id, update_id=2001,
    )
    ctx = _build_ctx(db_session, fake_redis, sender_mod)
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    await book_handler(update, context, ctx)

    # Exactly one DM sent (the keyboard prompt).
    assert len(stub_telegram_sender.text_calls) == 1
    sent_chat_id, sent_text = stub_telegram_sender.text_calls[0]
    assert sent_chat_id == chat_id
    assert sent_text == "Выберите время:"

    # reply_markup was forwarded — Phase 40 WARNING-4 widening exercised.
    markup = stub_telegram_sender.text_call_markups[0]
    assert isinstance(markup, InlineKeyboardMarkup)
    keyboard = markup.inline_keyboard
    # Exactly 5 rows (1 button per row).
    assert len(keyboard) == 5
    for row in keyboard:
        assert len(row) == 1
        button = row[0]
        callback = button.callback_data
        assert callback.startswith("BK:")
        # 3 ("BK:") + 36 (UUID canonical hex with hyphens) == 39 bytes.
        assert len(callback.encode("utf-8")) == 39
        assert len(callback.encode("utf-8")) < 64  # Telegram limit
        # D-40-07 label format — "DD.MM HH:MM — {trainer_full_name}".
        assert " — " in button.text  # U+2014 EM DASH per D-40-07


# ---------------------------------------------------------------------------
# Test 2: anti-oracle — client_not_linked (Phase 40 C-12)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_book_handler_anti_oracle_client_not_linked(
    db_session: AsyncSession,
    stub_telegram_sender: StubTelegramSender,
) -> None:
    """telegram_user_id resolves to no Client → reply is exactly
    _BOT_BOOK_DENIED_DM with NO keyboard attached (anti-oracle C-12)."""
    tg_user_id = _TG_USER_BASE + 2
    chat_id = _CHAT_BASE + 2
    # No client seeded with this telegram_user_id.

    fake_redis = fakeredis.aioredis.FakeRedis()
    from app.integrations.telegram import sender as sender_mod
    update = _build_update(
        telegram_user_id=tg_user_id, chat_id=chat_id, update_id=2002,
    )
    ctx = _build_ctx(db_session, fake_redis, sender_mod)
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    await book_handler(update, context, ctx)

    assert len(stub_telegram_sender.text_calls) == 1
    sent_chat_id, sent_text = stub_telegram_sender.text_calls[0]
    assert sent_chat_id == chat_id
    assert sent_text == _BOT_BOOK_DENIED_DM
    assert stub_telegram_sender.text_call_markups[0] is None


# ---------------------------------------------------------------------------
# Test 3: anti-oracle — no active pt_package (Phase 40 C-12)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_book_handler_anti_oracle_no_pt_package(
    db_session: AsyncSession,
    stub_telegram_sender: StubTelegramSender,
) -> None:
    """Linked client + no active pt_package → _BOT_BOOK_DENIED_DM, no keyboard."""
    tg_user_id = _TG_USER_BASE + 3
    chat_id = _CHAT_BASE + 3
    creator = await _seed_user(db_session)
    await _seed_linked_client(
        db_session, telegram_user_id=tg_user_id, creator=creator,
    )
    # Note: no _seed_active_pt_package call.

    fake_redis = fakeredis.aioredis.FakeRedis()
    from app.integrations.telegram import sender as sender_mod
    update = _build_update(
        telegram_user_id=tg_user_id, chat_id=chat_id, update_id=2003,
    )
    ctx = _build_ctx(db_session, fake_redis, sender_mod)
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    await book_handler(update, context, ctx)

    assert len(stub_telegram_sender.text_calls) == 1
    _, sent_text = stub_telegram_sender.text_calls[0]
    assert sent_text == _BOT_BOOK_DENIED_DM
    assert stub_telegram_sender.text_call_markups[0] is None


# ---------------------------------------------------------------------------
# Test 4: anti-oracle — pt_package exhausted (sessions_remaining=0)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_book_handler_anti_oracle_pt_package_exhausted(
    db_session: AsyncSession,
    stub_telegram_sender: StubTelegramSender,
) -> None:
    """Linked client + exhausted pt_package → _BOT_BOOK_DENIED_DM, no keyboard."""
    tg_user_id = _TG_USER_BASE + 4
    chat_id = _CHAT_BASE + 4
    creator = await _seed_user(db_session)
    client = await _seed_linked_client(
        db_session, telegram_user_id=tg_user_id, creator=creator,
    )
    await _seed_active_pt_package(
        db_session, client=client, sessions_remaining=0,
    )

    fake_redis = fakeredis.aioredis.FakeRedis()
    from app.integrations.telegram import sender as sender_mod
    update = _build_update(
        telegram_user_id=tg_user_id, chat_id=chat_id, update_id=2004,
    )
    ctx = _build_ctx(db_session, fake_redis, sender_mod)
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    await book_handler(update, context, ctx)

    assert len(stub_telegram_sender.text_calls) == 1
    _, sent_text = stub_telegram_sender.text_calls[0]
    assert sent_text == _BOT_BOOK_DENIED_DM
    assert stub_telegram_sender.text_call_markups[0] is None


# ---------------------------------------------------------------------------
# Test 5: anti-oracle — no matching active slots
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_book_handler_anti_oracle_no_slots(
    db_session: AsyncSession,
    stub_telegram_sender: StubTelegramSender,
) -> None:
    """Linked + active pt_package but ``list_slots`` returns empty
    → _BOT_BOOK_DENIED_DM with no keyboard."""
    tg_user_id = _TG_USER_BASE + 5
    chat_id = _CHAT_BASE + 5
    creator = await _seed_user(db_session)
    client = await _seed_linked_client(
        db_session, telegram_user_id=tg_user_id, creator=creator,
    )
    await _seed_active_pt_package(db_session, client=client)
    # Trainer exists but NO slots.
    await _seed_trainer(db_session)

    fake_redis = fakeredis.aioredis.FakeRedis()
    from app.integrations.telegram import sender as sender_mod
    update = _build_update(
        telegram_user_id=tg_user_id, chat_id=chat_id, update_id=2005,
    )
    ctx = _build_ctx(db_session, fake_redis, sender_mod)
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    await book_handler(update, context, ctx)

    assert len(stub_telegram_sender.text_calls) == 1
    _, sent_text = stub_telegram_sender.text_calls[0]
    assert sent_text == _BOT_BOOK_DENIED_DM
    assert stub_telegram_sender.text_call_markups[0] is None


# ---------------------------------------------------------------------------
# Test 6: update_id dedup — replay is silent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_book_handler_dedupe_replay_skipped(
    db_session: AsyncSession,
    stub_telegram_sender: StubTelegramSender,
) -> None:
    """Same update_id seen twice → second invocation sends NO message
    (Redis SET-NX-EX first-sight contract; Phase 40 D-40-08)."""
    tg_user_id = _TG_USER_BASE + 6
    chat_id = _CHAT_BASE + 6
    # No client → first invocation hits anti-oracle path; replay must skip.
    fake_redis = fakeredis.aioredis.FakeRedis()
    from app.integrations.telegram import sender as sender_mod
    update = _build_update(
        telegram_user_id=tg_user_id, chat_id=chat_id, update_id=2006,
    )
    ctx = _build_ctx(db_session, fake_redis, sender_mod)
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    await book_handler(update, context, ctx)
    assert len(stub_telegram_sender.text_calls) == 1

    # Replay — same update_id → silent.
    await book_handler(update, context, ctx)
    assert len(stub_telegram_sender.text_calls) == 1  # unchanged


# ---------------------------------------------------------------------------
# Test 7: callback_data byte-length invariant (unit-style on the kb result)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_book_handler_callback_data_byte_length_under_64(
    db_session: AsyncSession,
    stub_telegram_sender: StubTelegramSender,
) -> None:
    """Sanity guard — every callback_data MUST be < 64 bytes (Telegram cap)."""
    tg_user_id = _TG_USER_BASE + 7
    chat_id = _CHAT_BASE + 7
    creator = await _seed_user(db_session)
    client = await _seed_linked_client(
        db_session, telegram_user_id=tg_user_id, creator=creator,
    )
    trainer = await _seed_trainer(db_session)
    await _seed_active_pt_package(db_session, client=client)
    for i in range(3):
        await _seed_slot(
            db_session,
            trainer=trainer,
            creator=creator,
            start_offset=timedelta(hours=2 + i),
        )

    fake_redis = fakeredis.aioredis.FakeRedis()
    from app.integrations.telegram import sender as sender_mod
    update = _build_update(
        telegram_user_id=tg_user_id, chat_id=chat_id, update_id=2007,
    )
    ctx = _build_ctx(db_session, fake_redis, sender_mod)
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    await book_handler(update, context, ctx)
    markup = stub_telegram_sender.text_call_markups[0]
    assert isinstance(markup, InlineKeyboardMarkup)
    for row in markup.inline_keyboard:
        for button in row:
            assert len(button.callback_data.encode("utf-8")) < 64
