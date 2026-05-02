"""Telegram bot Application factory (Phase 7 D-09).

Per D-09: NO module-level Application -- `build_application` is a factory that
returns a fresh Application bound to the supplied token + handlers + ctx.
The live instance lives inside app/workers/telegram_bot.py main()'s scope.

Per D-05: handlers receive HandlerContext via a thin adapter closure that
ptb 22's CommandHandler signature `async def(update, context)` permits.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.integrations.telegram.handlers import HandlerContext

logger = structlog.get_logger("telegram.bot")

# A handler signature accepted by build_application:
# (update, context, ctx) -> awaitable.
HandlerCallable = Callable[
    [Update, ContextTypes.DEFAULT_TYPE, HandlerContext],
    Awaitable[None],
]


async def _global_error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Swallow + log any unhandled handler exception (resilience).

    Bot must never crash on a handler exception -- long-polling stays alive.
    """
    logger.exception("telegram_handler_error", error=str(context.error))


def build_application(
    *,
    token: str,
    handlers: list[tuple[str, HandlerCallable]],
    ctx: HandlerContext,
) -> Application[Any, Any, Any, Any, Any, Any]:
    """Construct a ptb 22 Application with the supplied command handlers.

    Args:
        token   : raw bot token (caller is responsible for SecretStr unwrap).
        handlers: list of (command_name, handler_callable) tuples --
                  e.g. [("start", start_handler)].
                  Each handler signature is
                  `async def(update, context, ctx: HandlerContext)`.
        ctx     : HandlerContext closure passed to every handler.

    Returns:
        Configured Application -- caller starts/stops via
        `await application.run_polling()` OR the manual
        initialize/start/stop dance documented in workers/telegram_bot.py.
    """
    application = Application.builder().token(token).build()

    for command_name, handler in handlers:
        # Adapter: ptb's CommandHandler signature is (update, context) -- we close
        # over `ctx` to keep handler functions ctx-aware without ptb knowing about
        # the closure shape. Default args `_h`, `_c` fix the binding to avoid the
        # late-binding bug in a loop.
        async def _adapter(
            update: Update,
            context: ContextTypes.DEFAULT_TYPE,
            _h: HandlerCallable = handler,
            _c: HandlerContext = ctx,
        ) -> None:
            await _h(update, context, _c)

        application.add_handler(CommandHandler(command_name, _adapter))

    application.add_error_handler(_global_error_handler)
    return application
