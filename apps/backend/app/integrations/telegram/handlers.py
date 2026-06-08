"""Telegram /start handler (Phase 7 D-04, D-05, D-11, D-20).

Handlers receive a HandlerContext closure constructed in
app/workers/telegram_bot.py -- they NEVER import app.modules.auth directly
(integrations perp modules importlinter contract).

The /start <token> handler implements the atomic-after-DM pattern (D-11):
  1. Validate /start <token> shape.
  2. Open SAVEPOINT-rolled session via ctx.session_factory().
  3. ctx.telegram_service.bind_and_issue(session, token, chat_id, username)
     -- generates raw_code in-memory, NO commit yet.
  4. ctx.sender.send_otp_dm(bot, chat_id, raw_code).
  5. If ok=True -> ctx.telegram_service.commit_otp(session, ...).
  6. If blocked / error / TelegramUnknownAccount / OtpAlreadyConsumed:
     emit structlog event, optional DM, no OTP commit.

The /checkin handler (Phase 20 D-10):
  1. Defensive update-field guard.
  2. Redis SET-NX-EX dedup on `cc:bot:update:{update_id}` TTL 1h, fail-open on
     Redis errors (D-20-3).
  3. Open SAVEPOINT-rolled session via ctx.session_factory().
  4. ctx.visits_service.create_visit_self_checkin(...) -- service owns commit
     + audit emit on every branch EXCEPT ClientNotLinkedError (handler owns;
     D-20-10).
  5. Dispatch by type(exc).__name__ (string-name; integrations perp modules
     forbids importing the classes).
  6. DM one of 4 locked Russian strings (D-20-7); ClientNotLinkedError reuses
     _DM_NO_MEMBERSHIP (D-20-9 anti-oracle).
"""

from __future__ import annotations

import hashlib
import importlib
import json
from datetime import UTC, datetime, timedelta
from datetime import datetime as _datetime
from types import ModuleType
from typing import Any, Final, NamedTuple
from uuid import UUID
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfo as _ZoneInfo

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.core.audit import emit as audit_emit
from app.core.config import get_settings
from app.core.dependencies import (
    get_active_pt_package,
    resolve_client_by_telegram_user_id,
)

# NOTE: NO `from app.modules.auth import ...` -- integrations perp modules.
# Domain modules arrive via HandlerContext (or via importlib.import_module
# for type-only references — see book_handler's _bot_book_denied_dm /
# SlotListQuery / SlotStatus resolutions, which use the importlib indirection
# pattern from PATTERNS.md §5 Option A so import-linter's static AST walker
# stays clean against `integrations must not import modules`).

logger = structlog.get_logger("telegram.handler")


class HandlerContext(NamedTuple):
    """Closure passed to every handler -- D-05.

    session_factory   : async_sessionmaker for opening DB sessions per update.
    telegram_service  : the app.modules.auth.telegram_service module
                        (workers->modules.auth, D-06).
    sender            : the app.integrations.telegram.sender module.
    visits_service    : the app.modules.visits.service module
                        (workers->modules.visits, D-10 — Phase 20).
    redis             : redis.asyncio.Redis client for /checkin update_id dedup
                        (Phase 20 D-20-2; keyspace `cc:bot:update:*`).
    bookings_service  : the app.modules.bookings.service module
                        (workers->modules.bookings, Phase 40 D-40-04 —
                        create_booking_via_bot dispatch for /book callback).
    schedule_service  : the app.modules.schedule.service module
                        (workers->modules.schedule, Phase 40 D-40-06 —
                        list_slots for /book keyboard render).
    messaging_service : the app.modules.messaging.service module
                        (workers->modules.messaging, Phase 93 D-06 relaxation —
                        record_staff_message + publish helpers for reply routing).

    Field order is part of the stable contract — positional construction in
    workers/telegram_bot.py:main() depends on it. New fields are APPENDED at
    the END (never inserted in the middle).
    """

    session_factory: async_sessionmaker[AsyncSession]
    telegram_service: ModuleType
    sender: ModuleType
    visits_service: ModuleType
    redis: Redis
    bookings_service: ModuleType  # Phase 40 D-40-04 — create_booking_via_bot dispatch
    schedule_service: ModuleType  # Phase 40 D-40-06 — list_slots for keyboard render
    messaging_service: ModuleType  # Phase 93 D-06 relaxation — reply routing


async def _dedupe_update_id(redis: Redis, update_id: int, chat_id: int) -> bool:
    """Return True on first-sight (proceed); False on replay (handler should return).

    Fail-open per D-20-3: Redis errors return True (DB UNIQUE is the real
    anti-replay backstop). Key prefix ``cc:bot:update:{update_id}`` TTL 1h.
    Extracted from the Phase 20 checkin_handler inlined block per Phase 40
    D-40-08 so that Phase 40's /book + /book-callback handlers reuse the
    exact same fail-open + structlog-event-name semantics.
    """
    dedup_key = f"cc:bot:update:{update_id}"
    try:
        set_result: Any = await redis.set(dedup_key, "1", nx=True, ex=3600)
    except Exception as exc:  # fail-open per D-20-3
        logger.warning(
            "bot_redis_dedup_unavailable",
            update_id=update_id,
            chat_id=chat_id,
            error=str(exc),
        )
        return True  # DB UNIQUE is the real anti-replay backstop
    if set_result is None:
        # Replay (Telegram resent the Update on bot restart). Silent per D-20-4.
        logger.debug("bot_replay_skipped", update_id=update_id, chat_id=chat_id)
        return False
    return True


# Russian copy -- locked per specifics line 253. Single-language by design.
_DM_STRANGER = "Этот Telegram не привязан к аккаунту Sportzal. Обратитесь к администратору."
_DM_REPLAY = "Этот код уже использован, запросите новый."

# Phase 20 — locked Russian DM copy per AUTH-TG-11. Owner-signed-off (gated in 20-03).
# Phase 22 D-22-11 — owner sign-off received (Option B: special-case zero).
# Two strings replace the single "✅ Отмечено":
#   days_remaining > 0 : days-remaining variant
#   days_remaining == 0 : last-day variant (INCLUSIVE end_date per Phase 15 Key Decision)
_DM_CHECKIN_OK_WITH_DAYS = "✅ Отмечено. Абонемент действует ещё {days_remaining} дн."
_DM_CHECKIN_OK_LAST_DAY = "✅ Отмечено. Сегодня — последний день абонемента."
_DM_NO_MEMBERSHIP = "У вас нет активного абонемента. Обратитесь к администратору."  # noqa: RUF001
_DM_DUPLICATE = "Вы уже отмечались сегодня."
_DM_OUTSIDE_HOURS = "Зал сейчас закрыт. Часы работы: {hours}."


def _parse_start_token(message_text: str | None) -> str | None:
    """Extract `<token>` from `/start <token>`. Return None if shape mismatch."""
    if not message_text:
        return None
    parts = message_text.split(maxsplit=1)
    if len(parts) != 2 or parts[0] != "/start":
        return None
    token = parts[1].strip()
    return token or None


def _hash_token_for_log(raw_token: str) -> str:
    """sha256(raw_token) hex -- non-secret correlator for structlog events.

    Computed locally with stdlib so the handler does not need to reach into
    `ctx.telegram_service` private helpers (preserves integrations perp modules).
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _hash_telegram_user_id(tg_user_id: int) -> str:
    """sha256(str(tg_user_id)) hex -- non-secret correlator for audit + structlog.

    Used by the `telegram_unknown_checkin` audit emit (D-20-10) so the
    audit_log table never stores the raw Telegram identifier (PII minimization).
    """
    return hashlib.sha256(str(tg_user_id).encode("utf-8")).hexdigest()


def _format_gym_hours(exc: Exception) -> str:
    """Format OutsideGymHoursError.fields as 'HH:MM-HH:MM' joined by U+2013 EN DASH.

    Strips trailing ':SS' from time.isoformat() output ('07:00:00' -> '07:00').
    Defensive: raises RuntimeError if exc.fields is missing 'open'/'close'
    (Phase 19 service.py:99-100, 142 contract -- load-bearing for D-20-8).
    """
    fields = getattr(exc, "fields", None) or {}
    try:
        open_t = fields["open"][:5]
        close_t = fields["close"][:5]
    except (KeyError, TypeError) as e:
        raise RuntimeError(
            "OutsideGymHoursError fields contract broken — Phase 19 regression"
        ) from e
    return f"{open_t}–{close_t}"  # noqa: RUF001 — U+2013 EN DASH per D-20-8


async def start_handler(
    update: Any,  # telegram.Update at runtime; Any to keep ptb types out of public sig
    context: Any,  # telegram.ext.CallbackContext at runtime
    ctx: HandlerContext,
) -> None:
    """ptb /start handler (D-04, D-11, D-20).

    `update` and `context` are ptb 22 types (telegram.Update,
    telegram.ext.CallbackContext). Typed as `Any` so the public signature
    does not constrain callers (mypy strict still enforces internal usage).
    """
    bot = context.bot
    effective_user = update.effective_user
    effective_chat = update.effective_chat
    if effective_user is None or effective_chat is None or update.message is None:
        return

    chat_id: int = effective_chat.id
    username: str | None = effective_user.username

    raw_token = _parse_start_token(update.message.text)
    if raw_token is None:
        # Bot received /start without an arg -- silently ignore per CONTEXT specifics
        # ("no commands beyond /start <token>"). Log at debug only.
        logger.debug("telegram_start_without_token", chat_id=chat_id, username=username)
        return

    deep_link_token_hash = _hash_token_for_log(raw_token)

    async with ctx.session_factory() as session:
        try:
            user, raw_code, otp_row = await ctx.telegram_service.bind_and_issue(
                session,
                raw_token,
                chat_id,
                username,
            )
        except ctx.telegram_service.TelegramUnknownAccount:
            # D-04 stranger path -- DM fixed Russian message, leave OtpCode untouched.
            await audit_emit(
                session,
                "telegram_unknown_start",
                actor_user_id=None,
                resource_type="otp",
                username=username,
                chat_id=chat_id,
                deep_link_token_hash=deep_link_token_hash,
            )
            await ctx.sender.send_text_dm(bot, chat_id, _DM_STRANGER)
            return
        except Exception as exc:
            # OtpAlreadyConsumed (D-20 second-device) / TokenUnknown / OtpExpired --
            # dispatch by class name to avoid importing the exception classes
            # (integrations perp modules; we import them transitively via the service module).
            cls_name = type(exc).__name__
            if cls_name == "OtpAlreadyConsumed":
                await audit_emit(
                    session,
                    "telegram_replay_attempt",
                    actor_user_id=None,
                    resource_type="otp",
                    chat_id=chat_id,
                    deep_link_token_hash=deep_link_token_hash,
                )
                await ctx.sender.send_text_dm(bot, chat_id, _DM_REPLAY)
                return
            # TokenUnknown / OtpExpired / other -- silent
            # (don't leak token validity to bot UX).
            logger.warning(
                "telegram_start_rejected",
                reason=cls_name,
                chat_id=chat_id,
                deep_link_token_hash=deep_link_token_hash,
            )
            return

        # We got a valid (user, raw_code, otp_row) but no OTP commit yet (D-11).
        send_result = await ctx.sender.send_otp_dm(bot, chat_id, raw_code)
        if send_result.ok:
            await ctx.telegram_service.commit_otp(session, otp_row, user, raw_code, chat_id)
            # commit_otp emits otp_issued internally.
            return
        if send_result.blocked:
            await audit_emit(
                session,
                "telegram_dm_blocked",
                actor_user_id=None,
                resource_type="otp",
                chat_id=chat_id,
            )
            # No commit -- OtpCode keeps code_hash IS NULL ->
            # /verify will return bot_not_started.
            return
        # Transient failure.
        await audit_emit(
            session,
            "telegram_dm_failed",
            actor_user_id=None,
            resource_type="otp",
            chat_id=chat_id,
            error=send_result.error,
        )


async def checkin_handler(
    update: Any,  # telegram.Update at runtime
    context: Any,  # telegram.ext.CallbackContext at runtime
    ctx: HandlerContext,
) -> None:
    """ptb /checkin handler (Phase 20 D-10).

    Routes a client's /checkin DM into Phase 19's create_visit_self_checkin
    service while preserving the integrations perp modules import-linter contract:
    the visits service is reached only via ctx.visits_service.* (NamedTuple
    attribute access; never `from app.modules.visits import ...`).
    """
    bot = context.bot
    effective_user = update.effective_user
    effective_chat = update.effective_chat
    if effective_user is None or effective_chat is None or update.message is None:
        return
    update_id = getattr(update, "update_id", None)
    if update_id is None:
        return
    chat_id: int = effective_chat.id
    tg_user_id: int = effective_user.id

    # Redis SET-NX-EX dedup (D-20-1, D-20-3, D-20-5, D-20-6). Fail-open on Redis errors;
    # the DB UNIQUE on (client_id, gym_date) is the real anti-replay invariant.
    # Phase 40 D-40-08: extracted to module-level _dedupe_update_id helper so
    # Phase 40 /book + /book-callback handlers share the same semantics.
    if not await _dedupe_update_id(ctx.redis, update_id, chat_id):
        return

    async with ctx.session_factory() as session:
        try:
            visit, membership_end_date = await ctx.visits_service.create_visit_self_checkin(
                session,
                telegram_user_id=tg_user_id,
                chat_id=chat_id,
            )
        except Exception as exc:  # string-name dispatch (integrations perp modules)
            # D-20-9 anti-oracle: ClientNotLinkedError reuses _DM_NO_MEMBERSHIP so the
            # bot is useless for account enumeration. Do NOT "fix" this to a 5th honest-UX
            # string -- a stranger MUST see the same DM as a linked-but-no-membership client.
            cls_name = type(exc).__name__
            if cls_name == "NoActiveMembershipError":
                await ctx.sender.send_text_dm(bot, chat_id, _DM_NO_MEMBERSHIP)
                return
            if cls_name == "DuplicateCheckinError":
                await ctx.sender.send_text_dm(bot, chat_id, _DM_DUPLICATE)
                return
            if cls_name == "OutsideGymHoursError":
                await ctx.sender.send_text_dm(
                    bot,
                    chat_id,
                    _DM_OUTSIDE_HOURS.format(hours=_format_gym_hours(exc)),
                )
                return
            if cls_name == "ClientNotLinkedError":
                # D-20-10: handler owns the audit emit (Phase 19 D-12 deferred this).
                await audit_emit(
                    session,
                    "telegram_unknown_checkin",
                    actor_user_id=None,
                    resource_type="visit",
                    resource_id=None,
                    chat_id=chat_id,
                    telegram_user_id_hash=_hash_telegram_user_id(tg_user_id),
                )
                await session.commit()
                await ctx.sender.send_text_dm(bot, chat_id, _DM_NO_MEMBERSHIP)
                return
            # Any other exception -- re-raise; ptb _global_error_handler logs and the
            # polling loop continues (Phase 7 D-09 resilience).
            raise

        # Happy path. Phase 19 service has already committed + emitted visit_created.
        # Handler does NOT call session.commit() (Phase 19 D-05 + INFRA-13 commit gate).
        # D-22-11: compute days_remaining from membership end_date (INCLUSIVE per Phase 15).
        _today = _datetime.now(_ZoneInfo("Europe/Moscow")).date()
        days_remaining = (membership_end_date - _today).days
        if days_remaining == 0:
            dm_text = _DM_CHECKIN_OK_LAST_DAY
        elif days_remaining > 0:
            dm_text = _DM_CHECKIN_OK_WITH_DAYS.format(days_remaining=days_remaining)
        else:
            # WR-08: anti-fraud chain SHOULD have rejected with no_active_membership
            # before we reach the happy path with a past-end membership. If a future
            # bug ever lets this slip through, surface it loudly instead of telling
            # the user "today is the last day" for an already-expired membership.
            logger.error(
                "checkin_negative_days_remaining",
                membership_end_date=str(membership_end_date),
                chat_id=chat_id,
                days_remaining=days_remaining,
            )
            dm_text = _DM_CHECKIN_OK_LAST_DAY  # safe fallback
        await ctx.sender.send_text_dm(bot, chat_id, dm_text)
        # Ignore SendResult: a blocked DM does not roll back the visit (mirror Phase 7).
        _ = visit  # silence unused; structlog at sender layer already logs send failures


# ---------------------------------------------------------------------------
# Phase 40 BOT-01 / BOT-02 — /book command handler (D-40-02, D-40-06, D-40-07).
# ---------------------------------------------------------------------------

# Phase 40 D-40-07 — keyboard prompt text. Locked Russian copy; lives next to
# the handler (not in bookings/notifications.py) because it is a transient
# UX label, NOT a booking-domain DM template. The 4 denial paths reuse the
# locked _BOT_BOOK_DENIED_DM constant from bookings/notifications.py instead.
# Cyrillic letters are intentional (Russian-only product).
_BOOK_PROMPT_DM: Final[str] = "Выберите время:"

# Phase 40 D-40-07 — Moscow timezone for keyboard label formatting.
_MOSCOW_TZ = ZoneInfo("Europe/Moscow")

# Phase 40 D-40-07 — number of slots displayed per /book invocation.
# Locked at 5 to fit the Telegram inline-keyboard ergonomic envelope (1 button
# per row, 5 rows max keeps the keyboard scannable on mobile).
_BOOK_KEYBOARD_PAGE_SIZE: Final[int] = 5

# Phase 40 D-40-07 — forward look-ahead window for slot enumeration. Mirrors
# the SlotListQuery 14-day default to avoid surfacing far-future slots that
# the trainer might cancel before the client books them.
_BOOK_HORIZON_DAYS: Final[int] = 14


async def book_handler(
    update: Any,  # telegram.Update at runtime
    context: Any,  # telegram.ext.CallbackContext at runtime
    ctx: HandlerContext,
) -> None:
    """ptb /book command handler — Phase 40 BOT-01 / BOT-02.

    Stateless — no ConversationHandler (D-40-03). Renders up to 5 future
    active slots filtered by the client's active PT-package trainer within
    the next 14 days. Every failure path replies with the byte-identical
    ``_BOT_BOOK_DENIED_DM`` (Phase 40 C-12 anti-oracle — no failure-cause
    disclosure to the chat; only structlog WARNING discriminates for support).

    Modules-independent contract: the bot's bookings + schedule + notifications
    modules arrive via ``ctx.bookings_service`` / ``ctx.schedule_service`` (set
    by Wave 1's HandlerContext extension) and via ``importlib.import_module``
    for type-only references — no static ``from app.modules.* import ...``
    statements land in this file.
    """
    bot = context.bot
    effective_user = update.effective_user
    effective_chat = update.effective_chat
    if effective_user is None or effective_chat is None or update.message is None:
        return
    update_id = getattr(update, "update_id", None)
    if update_id is None:
        return
    chat_id: int = effective_chat.id
    tg_user_id: int = effective_user.id

    # Redis SET-NX-EX dedup (D-40-08 — extracted helper from Wave 1).
    if not await _dedupe_update_id(ctx.redis, update_id, chat_id):
        return

    # Resolve the modules-level constants + types we need WITHOUT static
    # imports (preserves `integrations must not import modules`).
    bookings_notifications = importlib.import_module("app.modules.bookings.notifications")
    schedule_schemas = importlib.import_module("app.modules.schedule.schemas")
    bot_book_denied_dm: str = bookings_notifications._BOT_BOOK_DENIED_DM
    slot_list_query_cls = schedule_schemas.SlotListQuery
    slot_status_cls = schedule_schemas.SlotStatus

    async with ctx.session_factory() as session:
        # Anti-oracle path A — telegram_user_id is not linked to any client.
        client = await resolve_client_by_telegram_user_id(session, tg_user_id)
        if client is None:
            logger.warning(
                "book_handler_denied",
                reason="client_not_linked",
                chat_id=chat_id,
            )
            await ctx.sender.send_text_dm(bot, chat_id, bot_book_denied_dm)
            return

        # Anti-oracle path B — no active PT-package OR exhausted package.
        pt_package = await get_active_pt_package(session, client.id)
        if pt_package is None or pt_package.sessions_remaining <= 0:
            logger.warning(
                "book_handler_denied",
                reason=("pt_package_not_active" if pt_package is None else "pt_package_exhausted"),
                chat_id=chat_id,
                client_id=str(client.id),
            )
            await ctx.sender.send_text_dm(bot, chat_id, bot_book_denied_dm)
            return

        # Slot enumeration — narrow to the client's trainer (NULL trainer_id
        # on pt_package means "any trainer" per C-08; passing None as the
        # trainer_id filter widens the list to all trainers).
        now_utc = datetime.now(UTC)
        horizon = now_utc + timedelta(days=_BOOK_HORIZON_DAYS)
        pkg_trainer_id = getattr(pt_package, "trainer_id", None)
        query = slot_list_query_cls(
            trainer_id=pkg_trainer_id,
            from_time=now_utc,
            to_time=horizon,
            status=slot_status_cls.ACTIVE,
            page=1,
            page_size=_BOOK_KEYBOARD_PAGE_SIZE,
        )
        page = await ctx.schedule_service.list_slots(session, query)
        slots = list(page.items)[:_BOOK_KEYBOARD_PAGE_SIZE]

        # Anti-oracle path C — no matching active slots.
        if not slots:
            logger.warning(
                "book_handler_denied",
                reason="no_slots",
                chat_id=chat_id,
                client_id=str(client.id),
            )
            await ctx.sender.send_text_dm(bot, chat_id, bot_book_denied_dm)
            return

        # Build the InlineKeyboard. D-40-07 label format:
        # "DD.MM HH:MM — {trainer_full_name}"; callback_data "BK:{slot.id}"
        # (39 bytes total, < 64-byte Telegram limit — test asserts).
        buttons: list[list[InlineKeyboardButton]] = []
        for s in slots:
            label = f"{s.start_time.astimezone(_MOSCOW_TZ):%d.%m %H:%M} — {s.trainer_full_name}"
            buttons.append(
                [
                    InlineKeyboardButton(
                        label,
                        callback_data=f"BK:{s.id}",
                    )
                ]
            )
        markup = InlineKeyboardMarkup(buttons)
        await ctx.sender.send_text_dm(
            bot,
            chat_id,
            _BOOK_PROMPT_DM,
            reply_markup=markup,
        )


# ---------------------------------------------------------------------------
# Phase 40 BOT-03 — /book CallbackQueryHandler (D-40-09, D-40-10).
# ---------------------------------------------------------------------------


async def book_callback_handler(
    update: Any,  # telegram.Update at runtime
    context: Any,  # telegram.ext.CallbackContext at runtime
    ctx: HandlerContext,
) -> None:
    """ptb /book CallbackQueryHandler — Phase 40 BOT-03.

    PTB's ``CallbackQueryHandler(pattern=r"^BK:[uuid]$")`` already filters
    callback_data shape (D-40-09); structurally invalid data never reaches
    this handler. Defensive UUID parse is still applied — a regex bypass
    via spoofed callback returns silently with a structlog WARNING.

    Anti-oracle D-40-10 / C-12: every one of the 7 domain error classes
    raised by ``ctx.bookings_service.create_booking_via_bot`` maps to the
    byte-identical ``_BOT_BOOK_DENIED_DM`` (NO discriminating placeholder).
    Discrimination lives only in structlog WARNING ``book_callback_denied``
    with ``error_class=type(exc).__name__``.

    BLOCKER-3 fix: confirmation DM renders directly from
    ``BookingResponse.trainer_full_name`` + ``BookingResponse.slot_start_time``
    (populated by Phase 40 plan 40-02 Task 2 JOIN projection). The handler
    does NOT call any secondary slot-by-id resolver on the schedule service
    module — that attribute does not exist there (the actual resolver is a
    Protocol slot in ``app.core.dependencies``, not a service method).
    The regression-guard test ``test_book_callback_does_not_reference_*``
    asserts this file is free of any reference to the bogus attribute name.

    Modules-independent contract preserved: the bookings_service module
    arrives via ``HandlerContext``; the ``_BOT_BOOK_DENIED_DM`` constant
    and ``render_booking_confirmed_dm`` helper are reached via
    ``importlib.import_module`` (mirrors ``book_handler``'s indirection).
    """
    query = update.callback_query
    if query is None or query.data is None:
        return
    update_id = getattr(update, "update_id", None)
    if update_id is None:
        return
    if query.message is None:
        return
    chat_id: int = query.message.chat.id

    if not await _dedupe_update_id(ctx.redis, update_id, chat_id):
        return

    raw = query.data
    if not raw.startswith("BK:"):
        # PTB regex already filtered this — defensive log + drop (D-40-09).
        logger.warning(
            "book_callback_invalid_data",
            update_id=update_id,
            chat_id=chat_id,
            data_prefix=raw[:10],
        )
        return
    try:
        slot_id = UUID(raw[3:])
    except ValueError:
        logger.warning(
            "book_callback_invalid_uuid",
            update_id=update_id,
            chat_id=chat_id,
            data_prefix=raw[:10],
        )
        return

    effective_user = update.effective_user
    if effective_user is None:
        return
    tg_user_id: int = effective_user.id

    # Resolve modules-level constants WITHOUT static imports
    # (preserves `integrations must not import modules` import-linter contract).
    bookings_notifications = importlib.import_module("app.modules.bookings.notifications")
    bot_book_denied_dm: str = bookings_notifications._BOT_BOOK_DENIED_DM
    render_confirmed = bookings_notifications.render_booking_confirmed_dm

    async with ctx.session_factory() as session:
        # Anti-oracle path A — stale keyboard tap from an unlinked user.
        client = await resolve_client_by_telegram_user_id(session, tg_user_id)
        if client is None:
            logger.warning(
                "book_callback_denied",
                update_id=update_id,
                chat_id=chat_id,
                error_class="ClientNotLinkedError",
            )
            await query.edit_message_text(bot_book_denied_dm)
            return

        # Anti-oracle path B — pt_package state changed between render and tap.
        pt_package = await get_active_pt_package(session, client.id)
        if pt_package is None:
            logger.warning(
                "book_callback_denied",
                update_id=update_id,
                chat_id=chat_id,
                error_class="PtPackageNotActiveError",
            )
            await query.edit_message_text(bot_book_denied_dm)
            return

        try:
            booking_response = await ctx.bookings_service.create_booking_via_bot(
                session,
                client_id=client.id,
                slot_id=slot_id,
                pt_package_id=pt_package.id,
            )
        except Exception as exc:
            # Anti-oracle D-40-10: EVERY error class → byte-identical DM.
            # String-name dispatch (integrations perp modules — no error class
            # import lands in this file).
            cls_name = type(exc).__name__
            logger.warning(
                "book_callback_denied",
                update_id=update_id,
                chat_id=chat_id,
                error_class=cls_name,
            )
            await query.edit_message_text(bot_book_denied_dm)
            return

        # Happy path. Service already committed + emitted booking_created
        # with actor_role='telegram_bot'. Render the confirmation DM directly
        # from BookingResponse JOIN-projected fields (BLOCKER-3 fix — no
        # secondary lookup against schedule_service).
        # NOTE: ClientByTelegram Protocol exposes only `.id` (Phase 19 D-02 —
        # kept narrow). The real resolver yields the full Client ORM row, so
        # `first_name` is present at runtime. `getattr` access keeps the
        # Protocol contract narrow while still letting us display a friendly
        # name in the confirmation DM.
        start_msk = booking_response.slot_start_time.astimezone(_MOSCOW_TZ)
        raw_first_name: Any = getattr(client, "first_name", None) or "клиент"
        client_display_name: str = str(raw_first_name).strip() or "клиент"
        dm_text = render_confirmed(
            client_name=client_display_name,
            trainer_name=booking_response.trainer_full_name,
            slot_start_msk=start_msk.strftime("%d.%m.%Y %H:%M"),
        )
        await query.edit_message_text(dm_text)


# ---------------------------------------------------------------------------
# Phase 93 BRDG-02 / BRDG-03 — staff→client reply handler.
# ---------------------------------------------------------------------------

# Russian hint strings for staff — locked per Phase 93 Claude's Discretion.
# _DM_STAFF_STALE_ANCHOR: sent when the Redis anchor for a Reply is absent/expired.
# _DM_STAFF_USE_REPLY   : sent when the staff sends a plain (non-Reply) message.
_DM_STAFF_STALE_ANCHOR: Final[str] = (
    "⚠️ Не могу определить тред клиента. "
    "Возможно, ссылка устарела (>7 дн.). "
    "Найдите нужное сообщение клиента и ответьте на него через Reply."
)
_DM_STAFF_USE_REPLY: Final[str] = (
    "ℹ️ Чтобы ответить клиенту, используйте Reply на пересланное сообщение — "
    "не пишите отдельное сообщение."
)

# Redis key prefix written by forward_to_staff (Plan 01).
_TG_MSG_KEY_PREFIX: Final[str] = "cc:messaging:tg_msg:"


async def staff_reply_handler(
    update: Any,  # telegram.Update at runtime
    context: Any,  # telegram.ext.CallbackContext at runtime
    ctx: HandlerContext,
) -> None:
    """ptb MessageHandler for staff replies in the configured staff Telegram chat.

    Phase 93 BRDG-02 / BRDG-03. Reached ONLY via
    ``MessageHandler(tg_filters.Chat(staff_chat_id) & tg_filters.TEXT, ...)``;
    the PTB filter is the primary gate. A defensive in-handler chat-id check
    provides belt-and-suspenders against misconfiguration.

    Security boundaries:
      T-93-06: MessageHandler filter + in-handler chat-id guard.
      T-93-07: client_id/thread_id sourced ONLY from the Redis anchor keyed by
               reply_to.message_id — never from the message body. Stale/missing
               anchor DROPS the message with a staff hint (no most-recent-thread
               fallback — SC-2 / BRDG-03).
      T-93-08: Triple echo guard: is_bot early-return + _dedupe_update_id SET-NX
               + anchor-presence requirement.
      T-93-09: publish_new_message / publish_read_receipt carry only ids/timestamps
               (never the message body) to the channel derived from the anchored
               client_id only.
      T-93-10: chat_staff_reply_sent audit emitted co-transactionally (before
               commit) — atomic with the staff message insert.

    Modules-independent contract: messaging_service is reached ONLY via
    ``ctx.messaging_service.*`` — no static ``from app.modules.messaging import ...``
    in this file (integrations⊥modules).
    """
    bot = context.bot
    effective_user = update.effective_user
    effective_chat = update.effective_chat
    if effective_user is None or effective_chat is None or update.message is None:
        return

    # T-93-08: echo guard — bot's own outbound messages arrive as updates
    # when running in a group/supergroup chat; skip them immediately.
    if effective_user.is_bot:
        return

    update_id = getattr(update, "update_id", None)
    if update_id is None:
        return
    chat_id: int = effective_chat.id

    # T-93-08: replay guard — reuse the existing SET-NX dedup helper.
    if not await _dedupe_update_id(ctx.redis, update_id, chat_id):
        return

    # T-93-06: defensive in-handler chat-id check (belt-and-suspenders).
    staff_chat_id = get_settings().staff_telegram_chat_id
    if staff_chat_id is None or chat_id != staff_chat_id:
        logger.debug(
            "staff_reply_handler_wrong_chat",
            chat_id=chat_id,
            staff_chat_id=staff_chat_id,
        )
        return

    reply_to = update.message.reply_to_message

    # Non-Reply message: hint + drop.
    if reply_to is None:
        await ctx.sender.send_text_dm(bot, chat_id, _DM_STAFF_USE_REPLY)
        return

    # T-93-07: look up the routing anchor from Redis.
    raw_anchor = await ctx.redis.get(f"{_TG_MSG_KEY_PREFIX}{reply_to.message_id}")
    if raw_anchor is None:
        # Stale/missing anchor → hint + drop (no fallback, no misroute).
        await ctx.sender.send_text_dm(bot, chat_id, _DM_STAFF_STALE_ANCHOR)
        return

    anchor = json.loads(raw_anchor)
    client_id = UUID(anchor["client_id"])

    async with ctx.session_factory() as session:
        result = await ctx.messaging_service.record_staff_message(
            session,
            client_id=client_id,
            body=update.message.text or "",
            telegram_user_id=effective_user.id,
            telegram_username=effective_user.username,
        )

        # T-93-10: emit audit co-transactionally (before commit).
        await audit_emit(
            session,
            "chat_staff_reply_sent",
            actor_user_id=None,
            resource_type="message",
            resource_id=result.id,
            client_id=str(client_id),
        )

        await session.commit()

    # CR-02 / DB-first (P5): publish AFTER commit so frames are never emitted
    # for rows that did not commit.
    await ctx.messaging_service.publish_new_message(
        ctx.redis,
        client_id=client_id,
        message_id=result.id,
    )

    # T-93-09 / RCPT-03: publish read_receipt only when prior client messages
    # were marked read (reply_read_at is not None from record_staff_message).
    if result.reply_read_at is not None:
        await ctx.messaging_service.publish_read_receipt(
            ctx.redis,
            client_id=client_id,
            read_at=result.reply_read_at,
        )

    logger.info(
        "staff_reply_routed",
        client_id=str(client_id),
        message_id=str(result.id),
        tg_user_id=effective_user.id,
        chat_id=chat_id,
    )
