"""Telegram outbound DM wrapper -- SOLE outbound boundary (Phase 7 D-07).

TEST-03 stubs this single function. Bot handlers MUST go through send_otp_dm --
never call bot.send_message directly. Returns a typed SendResult instead of
raising on transport failures, so the handler atomicity (D-11) is observable
without try/except in the handler.
"""

from __future__ import annotations

from dataclasses import dataclass

from telegram import Bot
from telegram.error import BadRequest, Forbidden

# Russian DM body -- locked copy per CONTEXT line 253. No i18n framework (RU/CIS only).
# RUF001 disabled: Cyrillic letters are intentional (Russian-only product per PROJECT.md).
_OTP_DM_TEMPLATE = "Ваш код: {code}\nДействителен 5 минут."  # noqa: RUF001


@dataclass(frozen=True)
class SendResult:
    """Outcome of an outbound DM attempt (D-07).

    - ok=True                                : DM delivered.
    - ok=False, blocked=True                 : user blocked the bot or chat not found --
                                               give up; FE will see bot_not_started.
    - ok=False, blocked=False, error=...     : transient (network, rate-limit). Same
                                               outcome for FE; future ARQ retry only
                                               retries this branch (D-12 deferred).
    """

    ok: bool
    blocked: bool = False
    error: str | None = None


async def send_otp_dm(bot: Bot, chat_id: int, code: str) -> SendResult:
    """Send the OTP code DM to chat_id. Never re-raises transport errors."""
    try:
        await bot.send_message(chat_id=chat_id, text=_OTP_DM_TEMPLATE.format(code=code))
        return SendResult(ok=True)
    except Forbidden:
        # User blocked the bot, or hasn't started a chat with it.
        return SendResult(ok=False, blocked=True)
    except BadRequest as exc:
        # ptb raises BadRequest("Chat not found") when chat_id is unknown to bot.
        msg = str(exc).lower()
        if "chat not found" in msg or "chat_id" in msg:
            return SendResult(ok=False, blocked=True)
        return SendResult(ok=False, blocked=False, error=str(exc))
    except Exception as exc:  # outbound boundary -- classify all transport failures
        return SendResult(ok=False, blocked=False, error=str(exc))


async def send_text_dm(bot: Bot, chat_id: int, text: str) -> SendResult:
    """Generic text DM (used by handlers.py for stranger / replay messages).

    Same SendResult contract as send_otp_dm. Stubbing send_text_dm in tests is
    optional (the stranger / replay paths are observed via DB state + structlog).
    """
    try:
        await bot.send_message(chat_id=chat_id, text=text)
        return SendResult(ok=True)
    except Forbidden:
        return SendResult(ok=False, blocked=True)
    except BadRequest as exc:
        msg = str(exc).lower()
        if "chat not found" in msg or "chat_id" in msg:
            return SendResult(ok=False, blocked=True)
        return SendResult(ok=False, blocked=False, error=str(exc))
    except Exception as exc:  # outbound boundary -- mirror send_otp_dm classification
        return SendResult(ok=False, blocked=False, error=str(exc))
