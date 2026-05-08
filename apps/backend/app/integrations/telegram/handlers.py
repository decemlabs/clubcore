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
  2. Redis SET-NX-EX dedup on `sz:bot:update:{update_id}` TTL 1h, fail-open on
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
from datetime import datetime as _datetime
from types import ModuleType
from typing import Any, NamedTuple
from zoneinfo import ZoneInfo as _ZoneInfo

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import emit as audit_emit

# NOTE: NO `from app.modules.auth import ...` -- integrations perp modules.
# Domain modules arrive via HandlerContext.

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
                        (Phase 20 D-20-2; keyspace `sz:bot:update:*`).
    """

    session_factory: async_sessionmaker[AsyncSession]
    telegram_service: ModuleType
    sender: ModuleType
    visits_service: ModuleType
    redis: Redis


# Russian copy -- locked per specifics line 253. Single-language by design.
_DM_STRANGER = (
    "Этот Telegram не привязан к аккаунту Sportzal. "
    "Обратитесь к администратору."
)
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
    dedup_key = f"sz:bot:update:{update_id}"
    try:
        set_result: Any = await ctx.redis.set(dedup_key, "1", nx=True, ex=3600)
    except Exception as exc:  # fail-open per D-20-3
        logger.warning(
            "bot_redis_dedup_unavailable",
            update_id=update_id,
            chat_id=chat_id,
            error=str(exc),
        )
        set_result = "OK"  # proceed; DB UNIQUE is the real anti-replay backstop
    if set_result is None:
        # Replay (Telegram resent the Update on bot restart). Silent per D-20-4.
        logger.debug("bot_replay_skipped", update_id=update_id, chat_id=chat_id)
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
