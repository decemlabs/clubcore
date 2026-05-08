"""Telegram bot worker entry — long-polling python-telegram-bot 22 Application.

Per Phase 7 D-06 + Phase 20 D-10: workers MAY import owning modules' service
layers — currently `app.modules.auth.telegram_service` (D-06, /start handler)
and `app.modules.visits.service` (D-10, /checkin handler). Cross-module
imports inside workers are still forbidden — see app/workers/__init__.py
docstring.

Per Phase 7 D-09: NO module-level Application — built inside main()'s scope.
Per Phase 7 D-08: opens db_lifespan_manager() + redis_lifespan_manager()
under AsyncExitStack; pool configuration shared with the API process.

Entrypoint: `python -m app.workers.telegram_bot` (INFRA-06).
"""

from __future__ import annotations

import asyncio
import signal
from contextlib import AsyncExitStack, suppress

import structlog

from app.core.config import get_settings
from app.core.database import db_lifespan_manager
from app.core.logging import configure_logging
from app.core.redis import redis_lifespan_manager
from app.integrations.telegram import sender as telegram_sender
from app.integrations.telegram.bot import build_application
from app.integrations.telegram.handlers import (
    HandlerContext,
    checkin_handler,
    start_handler,
)
from app.modules.auth import telegram_service  # D-06 relaxation
from app.modules.visits import service as visits_service  # D-10 relaxation

# Sentinel matched against settings.telegram_bot_token; fresh-clone default
# from app/core/config.py. The worker refuses to start while this value is
# in effect — real deployments override via .env / docker-compose env.
_PLACEHOLDER_TELEGRAM_BOT_TOKEN = "placeholder-telegram-bot-token-not-real"  # noqa: S105


async def main() -> None:
    """Long-polling bot main loop."""
    settings = get_settings()
    configure_logging(settings)

    if settings.telegram_bot_token.get_secret_value() == _PLACEHOLDER_TELEGRAM_BOT_TOKEN:
        log = structlog.get_logger("workers.telegram_bot")
        log.error(
            "telegram_bot_placeholder_token",
            message=(
                "TELEGRAM_BOT_TOKEN is the placeholder default — the bot worker "
                "cannot start. Set TELEGRAM_BOT_TOKEN (from @BotFather) and "
                "TELEGRAM_BOT_USERNAME in .env or docker-compose env."
            ),
        )
        raise SystemExit(2)

    async with AsyncExitStack() as stack:
        _engine, sessionmaker = await stack.enter_async_context(db_lifespan_manager())
        redis = await stack.enter_async_context(redis_lifespan_manager())

        ctx = HandlerContext(
            session_factory=sessionmaker,
            telegram_service=telegram_service,
            sender=telegram_sender,
            visits_service=visits_service,
            redis=redis,
        )
        application = build_application(
            token=settings.telegram_bot_token.get_secret_value(),
            handlers=[("start", start_handler), ("checkin", checkin_handler)],
            ctx=ctx,
        )

        await application.initialize()
        try:
            await application.start()
            await application.updater.start_polling()  # type: ignore[union-attr]
            stop_event = asyncio.Event()

            def _shutdown() -> None:
                stop_event.set()

            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                # Signals may not be available on every platform (e.g. Windows tests).
                with suppress(NotImplementedError):
                    loop.add_signal_handler(sig, _shutdown)
            await stop_event.wait()
        finally:
            await application.updater.stop()  # type: ignore[union-attr]
            await application.stop()
            await application.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
