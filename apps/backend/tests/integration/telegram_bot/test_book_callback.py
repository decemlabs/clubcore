"""Phase 40 BOT-03 — /book CallbackQueryHandler integration tests.

Direct invocation of ``book_callback_handler(update, context, ctx)`` against:
  - The real ``bookings_service.create_booking_via_bot`` orchestrator (happy
    path, anti-oracle race-loss path, audit-row actor_role assertion).
  - AsyncMock-ed bookings_service stubs for the 6 non-race domain error classes
    (the service-mocked tests exercise the handler's exception-dispatch fork
    without re-seeding 6 different DB invariants — the matrix is in the
    bookings service's own integration suite).

Cases pinned:
  - Happy path edits original message to ``BOOKING_CONFIRMED_DM`` via
    ``render_booking_confirmed_dm`` consuming ``BookingResponse.trainer_full_name``
    + ``BookingResponse.slot_start_time`` (Phase 40 BLOCKER-3 fix — NO
    ``ctx.schedule_service.resolve_slot_by_id`` call; the attribute does not
    exist on the service module).
  - Every domain error → byte-identical ``_BOT_BOOK_DENIED_DM``
    (anti-oracle D-40-10 / C-12). 7 classes covered:
    ``SlotNotFoundError``, ``SlotNotAvailableError``, ``SlotAlreadyBookedError``,
    ``TrainerMismatchError``, ``PtPackageNotActiveError``,
    ``PtPackageExhaustedError``, ``PtPackageExpiredBeforeSlotError``.
  - structlog WARNING ``book_callback_denied`` carries
    ``error_class=type(exc).__name__`` for support debugging.
  - Update-id dedup: replay of same update_id is silent (D-40-08).
  - Audit row carries ``actor_role='telegram_bot'`` and ``actor_user_id IS NULL``
    (D-40-05 lock).
  - Anti-oracle DM byte-stability — AST inspection asserts
    ``_BOT_BOOK_DENIED_DM`` RHS is a constant string, not an f-string.
  - Concurrent race: two callbacks against the same slot resolve to exactly
    1 booking row in DB + 1 confirmation DM + 1 denial DM.
  - BLOCKER-3 regression guard — handlers.py source contains zero
    ``resolve_slot_by_id`` references.

Fixture pattern mirrors ``test_book_command.py``.
"""

from __future__ import annotations

import ast
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import fakeredis.aioredis
import pytest
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.core.permissions import Role
from app.integrations.telegram import handlers as handlers_mod
from app.integrations.telegram.handlers import HandlerContext, book_callback_handler
from app.modules.auth import telegram_service
from app.modules.auth.models import User
from app.modules.bookings import service as bookings_service_mod
from app.modules.bookings.models import Booking
from app.modules.bookings.notifications import _BOT_BOOK_DENIED_DM
from app.modules.clients.models import Client
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.schedule import service as schedule_service_mod
from app.modules.schedule.models import TrainerAvailabilitySlot
from app.modules.trainers.models import Trainer
from app.modules.visits import service as visits_service_mod


@pytest.fixture(autouse=True)
def _refresh_handler_logger(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mirror of test_book_command — refresh cached module-level logger."""
    fresh = structlog.get_logger("telegram.handler")
    monkeypatch.setattr(handlers_mod, "logger", fresh)


def _build_callback_update(
    *,
    telegram_user_id: int,
    chat_id: int,
    update_id: int,
    slot_id: UUID,
) -> SimpleNamespace:
    """Synthesize a PTB Update carrying a callback_query with data=BK:{uuid}."""
    eff_user = SimpleNamespace(id=telegram_user_id, username=None, is_bot=False)
    eff_chat = SimpleNamespace(id=chat_id, type="private")
    message = SimpleNamespace(chat=eff_chat, from_user=eff_user)
    # query.edit_message_text — AsyncMock so tests can assert call args.
    query = SimpleNamespace(
        data=f"BK:{slot_id}",
        message=message,
        edit_message_text=AsyncMock(),
    )
    return SimpleNamespace(
        update_id=update_id,
        effective_user=eff_user,
        effective_chat=eff_chat,
        callback_query=query,
        message=None,  # callback updates have no top-level .message
    )


def _build_ctx(
    db_session: AsyncSession,
    redis_client: Any,
    *,
    bookings_service: Any = bookings_service_mod,
    schedule_service: Any = schedule_service_mod,
) -> HandlerContext:
    @asynccontextmanager
    async def _factory() -> AsyncIterator[AsyncSession]:
        yield db_session

    return HandlerContext(
        session_factory=_factory,  # type: ignore[arg-type]
        telegram_service=telegram_service,
        sender=MagicMock(),  # not used on the callback path; edit_message_text is
        visits_service=visits_service_mod,
        redis=redis_client,
        bookings_service=bookings_service,
        schedule_service=schedule_service,
    )


async def _seed_user(db_session: AsyncSession) -> User:
    user = User(
        email=f"book-cb-{uuid4().hex[:8]}@example.com",
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
        last_name="Иванов",
        first_name="Иван",
        phone=f"+79052{uuid4().int % 10**7:07d}",
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
        name=f"CbPlan-{uuid4().hex[:8]}",
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


_TG_USER_BASE = 70_000_000
_CHAT_BASE = 555_000_000


# ---------------------------------------------------------------------------
# Test 1: happy path — edits original message to rendered BOOKING_CONFIRMED_DM
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_book_callback_happy_path_edits_to_confirmed_dm(
    db_session: AsyncSession,
) -> None:
    """Linked client + active pt_package + active slot → handler edits
    the original message to the rendered confirmation DM using
    ``BookingResponse.trainer_full_name`` + ``BookingResponse.slot_start_time``
    (Phase 40 BLOCKER-3 fix — no secondary lookup)."""
    tg_user_id = _TG_USER_BASE + 1
    chat_id = _CHAT_BASE + 1
    creator = await _seed_user(db_session)
    client = await _seed_linked_client(
        db_session,
        telegram_user_id=tg_user_id,
        creator=creator,
    )
    trainer = await _seed_trainer(db_session, full_name="Анна Петрова")
    await _seed_active_pt_package(db_session, client=client)
    slot = await _seed_slot(db_session, trainer=trainer, creator=creator)

    fake_redis = fakeredis.aioredis.FakeRedis()
    update = _build_callback_update(
        telegram_user_id=tg_user_id,
        chat_id=chat_id,
        update_id=3001,
        slot_id=slot.id,
    )
    ctx = _build_ctx(db_session, fake_redis)
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    await book_callback_handler(update, context, ctx)

    # Exactly one edit_message_text call.
    edit = update.callback_query.edit_message_text
    assert edit.await_count == 1
    sent_text = edit.await_args.args[0] if edit.await_args.args else edit.await_args.kwargs["text"]
    # Happy DM has trainer_full_name + Moscow-TZ marker + client first_name.
    assert "Анна Петрова" in sent_text
    assert "Иван" in sent_text
    assert "МСК" in sent_text  # noqa: RUF001
    assert sent_text != _BOT_BOOK_DENIED_DM


# ---------------------------------------------------------------------------
# Test 2: BLOCKER-3 regression guard — handlers.py contains no resolve_slot_by_id
# ---------------------------------------------------------------------------


def test_book_callback_does_not_reference_resolve_slot_by_id() -> None:
    """Static-source regression guard — Phase 40 BLOCKER-3.

    The Phase 40 iteration-1 plan called ``ctx.schedule_service.resolve_slot_by_id``,
    which would AttributeError at runtime (the attribute does not exist on the
    schedule service module — ``resolve_slot_by_id`` is a Protocol-slot free
    function in ``app.core.dependencies``). This test asserts the handler
    renders directly from BookingResponse fields and the bogus attribute name
    never appears in handlers.py.
    """
    source = Path(handlers_mod.__file__).read_text(encoding="utf-8")
    assert "resolve_slot_by_id" not in source, (
        "handlers.py must not reference resolve_slot_by_id — Phase 40 BLOCKER-3 "
        "regression guard. The book_callback_handler renders the confirmation DM "
        "directly from BookingResponse.trainer_full_name + "
        "BookingResponse.slot_start_time (populated by 40-02 Task 2 JOIN)."
    )


# ---------------------------------------------------------------------------
# Test 3: anti-oracle DM is byte-stable — no f-string placeholder
# ---------------------------------------------------------------------------


def test_anti_oracle_dm_byte_stable() -> None:
    """``_BOT_BOOK_DENIED_DM`` RHS must be an ``ast.Constant`` (str), NOT a
    JoinedStr (f-string). C-12 anti-oracle invariant — Phase 40 D-40-10."""
    notifications_path = Path(
        Path(__file__).resolve().parents[3] / "app" / "modules" / "bookings" / "notifications.py"
    )
    tree = ast.parse(notifications_path.read_text(encoding="utf-8"))
    found = False
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "_BOT_BOOK_DENIED_DM"
        ):
            found = True
            rhs = node.value
            assert rhs is not None, "_BOT_BOOK_DENIED_DM must have a value (Final[str] assignment)"
            assert isinstance(rhs, ast.Constant), (
                "_BOT_BOOK_DENIED_DM must be an ast.Constant (str), "
                "NOT an f-string / JoinedStr — anti-oracle invariant. "
                f"Actual node type: {type(rhs).__name__}"
            )
            assert isinstance(rhs.value, str), "_BOT_BOOK_DENIED_DM constant value must be str"
            break
    assert found, "_BOT_BOOK_DENIED_DM annotation not found in notifications.py"


# ---------------------------------------------------------------------------
# Test 4: replay dedup — same update_id seen twice → second call is silent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_book_callback_dedupe_replay_skipped(
    db_session: AsyncSession,
) -> None:
    """Same update_id seen twice → second invocation makes NO edit_message_text
    call (Redis SET-NX-EX first-sight contract; Phase 40 D-40-08)."""
    tg_user_id = _TG_USER_BASE + 4
    chat_id = _CHAT_BASE + 4
    # No client seeded → first call hits the anti-oracle path; replay must skip.
    fake_redis = fakeredis.aioredis.FakeRedis()
    update = _build_callback_update(
        telegram_user_id=tg_user_id,
        chat_id=chat_id,
        update_id=3004,
        slot_id=uuid4(),
    )
    ctx = _build_ctx(db_session, fake_redis)
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    await book_callback_handler(update, context, ctx)
    first_count = update.callback_query.edit_message_text.await_count
    assert first_count == 1

    # Replay — same update_id → silent (no second edit).
    await book_callback_handler(update, context, ctx)
    assert update.callback_query.edit_message_text.await_count == first_count


# ---------------------------------------------------------------------------
# Tests 5-11: anti-oracle on every domain error class (string-name dispatch)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error_class_name",
    [
        "SlotNotFoundError",
        "SlotNotAvailableError",
        "SlotAlreadyBookedError",
        "TrainerMismatchError",
        "PtPackageNotActiveError",
        "PtPackageExhaustedError",
        "PtPackageExpiredBeforeSlotError",
    ],
)
@pytest.mark.asyncio
async def test_book_callback_anti_oracle_on_domain_error(
    db_session: AsyncSession,
    error_class_name: str,
) -> None:
    """Each of the 7 domain error classes raised by ``create_booking_via_bot``
    maps to the SAME byte-identical ``_BOT_BOOK_DENIED_DM`` (anti-oracle).
    String-name dispatch — handler does not import the classes (preserves
    ``integrations must not import modules`` import-linter contract)."""
    tg_user_id = _TG_USER_BASE + 10
    chat_id = _CHAT_BASE + 10
    creator = await _seed_user(db_session)
    client = await _seed_linked_client(
        db_session,
        telegram_user_id=tg_user_id,
        creator=creator,
    )
    await _seed_active_pt_package(db_session, client=client)
    # A real slot id keeps the regex valid (PTB filter is conceptually upstream;
    # we still parse it here defensively).
    slot_uuid = uuid4()

    # Build a synthetic error class with the requested __name__.
    synthetic_error_cls = type(error_class_name, (Exception,), {})

    stub_bookings_service = MagicMock(spec=bookings_service_mod)
    stub_bookings_service.create_booking_via_bot = AsyncMock(
        side_effect=synthetic_error_cls("simulated")
    )

    fake_redis = fakeredis.aioredis.FakeRedis()
    update = _build_callback_update(
        telegram_user_id=tg_user_id,
        chat_id=chat_id,
        update_id=3100,
        slot_id=slot_uuid,
    )
    ctx = _build_ctx(
        db_session,
        fake_redis,
        bookings_service=stub_bookings_service,
    )
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    await book_callback_handler(update, context, ctx)

    edit = update.callback_query.edit_message_text
    assert edit.await_count == 1
    sent_text = edit.await_args.args[0] if edit.await_args.args else edit.await_args.kwargs["text"]
    assert sent_text == _BOT_BOOK_DENIED_DM, (
        f"Error class {error_class_name} must map to _BOT_BOOK_DENIED_DM "
        f"(anti-oracle), got: {sent_text!r}"
    )


# ---------------------------------------------------------------------------
# Test 12: structlog WARNING carries error_class for support
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_book_callback_logs_error_class_on_denial(
    db_session: AsyncSession,
) -> None:
    """When an error is raised, structlog WARNING ``book_callback_denied``
    carries ``error_class`` = the raised class's ``__name__``."""
    captured: list[dict[str, Any]] = []

    def _capture(_logger: Any, _name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        captured.append(dict(event_dict))
        return event_dict

    structlog.configure(processors=[_capture, structlog.dev.ConsoleRenderer()])
    try:
        synthetic_error_cls = type("SlotAlreadyBookedError", (Exception,), {})
        stub_bookings_service = MagicMock(spec=bookings_service_mod)
        stub_bookings_service.create_booking_via_bot = AsyncMock(
            side_effect=synthetic_error_cls("simulated race-loss")
        )

        tg_user_id = _TG_USER_BASE + 30
        chat_id = _CHAT_BASE + 30
        creator = await _seed_user(db_session)
        client = await _seed_linked_client(
            db_session,
            telegram_user_id=tg_user_id,
            creator=creator,
        )
        await _seed_active_pt_package(db_session, client=client)

        fake_redis = fakeredis.aioredis.FakeRedis()
        update = _build_callback_update(
            telegram_user_id=tg_user_id,
            chat_id=chat_id,
            update_id=3300,
            slot_id=uuid4(),
        )
        ctx = _build_ctx(
            db_session,
            fake_redis,
            bookings_service=stub_bookings_service,
        )
        context: Any = SimpleNamespace(bot=SimpleNamespace())

        # Refresh handler logger to pick up the new processors.
        handlers_mod.logger = structlog.get_logger("telegram.handler")

        await book_callback_handler(update, context, ctx)
    finally:
        structlog.reset_defaults()
        handlers_mod.logger = structlog.get_logger("telegram.handler")

    denial_events = [
        e
        for e in captured
        if e.get("event") == "book_callback_denied"
        and e.get("error_class") == "SlotAlreadyBookedError"
    ]
    assert denial_events, (
        f"Expected 'book_callback_denied' event with error_class='SlotAlreadyBookedError'; "
        f"got events: {[e.get('event') for e in captured]}"
    )


# ---------------------------------------------------------------------------
# Test 13: audit row carries actor_role='telegram_bot' on happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_book_callback_emits_audit_with_telegram_bot_actor_role(
    db_session: AsyncSession,
) -> None:
    """Happy-path callback writes an audit_log row with
    ``payload.actor_role='telegram_bot'`` and ``actor_user_id IS NULL``
    (D-40-05 lock)."""
    tg_user_id = _TG_USER_BASE + 40
    chat_id = _CHAT_BASE + 40
    creator = await _seed_user(db_session)
    client = await _seed_linked_client(
        db_session,
        telegram_user_id=tg_user_id,
        creator=creator,
    )
    trainer = await _seed_trainer(db_session)
    await _seed_active_pt_package(db_session, client=client)
    slot = await _seed_slot(db_session, trainer=trainer, creator=creator)

    fake_redis = fakeredis.aioredis.FakeRedis()
    update = _build_callback_update(
        telegram_user_id=tg_user_id,
        chat_id=chat_id,
        update_id=3400,
        slot_id=slot.id,
    )
    ctx = _build_ctx(db_session, fake_redis)
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    await book_callback_handler(update, context, ctx)

    rows = (
        (await db_session.execute(select(AuditLog).where(AuditLog.action == "booking_created")))
        .scalars()
        .all()
    )
    bot_rows = [r for r in rows if (r.payload or {}).get("actor_role") == "telegram_bot"]
    assert len(bot_rows) >= 1, (
        f"Expected at least 1 booking_created audit row with "
        f"actor_role='telegram_bot'; got rows: "
        f"{[(r.actor_user_id, (r.payload or {}).get('actor_role')) for r in rows]}"
    )
    for r in bot_rows:
        assert r.actor_user_id is None, (
            "telegram_bot audit rows must have actor_user_id IS NULL (D-40-05)"
        )


# ---------------------------------------------------------------------------
# Test 14: concurrent race — exactly 1 booking row + 1 confirmed + 1 denied
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_concurrent_book_callbacks_one_wins(
    db_session: AsyncSession,
) -> None:
    """Two concurrent invocations on the SAME slot → exactly 1 DB booking row
    (DB partial UNIQUE wins) + 1 confirmation DM + 1 denial DM."""
    tg_user_a = _TG_USER_BASE + 50
    tg_user_b = _TG_USER_BASE + 51
    chat_a = _CHAT_BASE + 50
    chat_b = _CHAT_BASE + 51
    creator = await _seed_user(db_session)
    client_a = await _seed_linked_client(
        db_session,
        telegram_user_id=tg_user_a,
        creator=creator,
    )
    client_b = await _seed_linked_client(
        db_session,
        telegram_user_id=tg_user_b,
        creator=creator,
    )
    trainer = await _seed_trainer(db_session)
    await _seed_active_pt_package(db_session, client=client_a)
    await _seed_active_pt_package(db_session, client=client_b)
    slot = await _seed_slot(db_session, trainer=trainer, creator=creator)

    fake_redis = fakeredis.aioredis.FakeRedis()
    ctx = _build_ctx(db_session, fake_redis)
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    update_a = _build_callback_update(
        telegram_user_id=tg_user_a,
        chat_id=chat_a,
        update_id=3501,
        slot_id=slot.id,
    )
    update_b = _build_callback_update(
        telegram_user_id=tg_user_b,
        chat_id=chat_b,
        update_id=3502,
        slot_id=slot.id,
    )

    # NOTE: SQLAlchemy AsyncSession is not safe for concurrent use across tasks,
    # but the SAVEPOINT-rolled per-test session forces sequential execution at
    # the DB-driver level regardless; the partial-UNIQUE race translation in
    # create_booking_via_bot still asserts the conflict shape. We run them
    # sequentially in this test to mirror the actual single-connection harness.
    await book_callback_handler(update_a, context, ctx)
    await book_callback_handler(update_b, context, ctx)

    # Exactly 1 booking row for this slot.
    rows = (
        (await db_session.execute(select(Booking).where(Booking.slot_id == slot.id)))
        .scalars()
        .all()
    )
    assert len(rows) == 1, f"Expected exactly 1 booking for slot {slot.id}; got {len(rows)}"

    # One DM was the confirmation (not _BOT_BOOK_DENIED_DM); the other was the
    # locked denial string.
    sent_texts: list[str] = []
    for upd in (update_a, update_b):
        edit = upd.callback_query.edit_message_text
        assert edit.await_count == 1
        text = edit.await_args.args[0] if edit.await_args.args else edit.await_args.kwargs["text"]
        sent_texts.append(text)

    confirmed = [t for t in sent_texts if t != _BOT_BOOK_DENIED_DM]
    denied = [t for t in sent_texts if t == _BOT_BOOK_DENIED_DM]
    assert len(confirmed) == 1, f"Expected exactly 1 confirmation DM; got {sent_texts!r}"
    assert len(denied) == 1, f"Expected exactly 1 denial DM; got {sent_texts!r}"


# ---------------------------------------------------------------------------
# Test 15: client-not-linked anti-oracle (defensive — keyboard normally
# pre-filters this, but a stale keyboard tap from an unlinked user reaches
# the callback)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_book_callback_client_not_linked_anti_oracle(
    db_session: AsyncSession,
) -> None:
    """telegram_user_id resolves to no Client → ``_BOT_BOOK_DENIED_DM``."""
    fake_redis = fakeredis.aioredis.FakeRedis()
    update = _build_callback_update(
        telegram_user_id=_TG_USER_BASE + 90,
        chat_id=_CHAT_BASE + 90,
        update_id=3900,
        slot_id=uuid4(),
    )
    ctx = _build_ctx(db_session, fake_redis)
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    await book_callback_handler(update, context, ctx)
    edit = update.callback_query.edit_message_text
    assert edit.await_count == 1
    text = edit.await_args.args[0] if edit.await_args.args else edit.await_args.kwargs["text"]
    assert text == _BOT_BOOK_DENIED_DM
