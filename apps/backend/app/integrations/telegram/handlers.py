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
"""

from __future__ import annotations

import hashlib
from types import ModuleType
from typing import Any, NamedTuple

import structlog
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
    """

    session_factory: async_sessionmaker[AsyncSession]
    telegram_service: ModuleType
    sender: ModuleType


# Russian copy -- locked per specifics line 253. Single-language by design.
_DM_STRANGER = (
    "Этот Telegram не привязан к аккаунту Sportzal. "
    "Обратитесь к администратору."
)
_DM_REPLAY = "Этот код уже использован, запросите новый."


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
