"""Telegram bot worker entry — long-polling python-telegram-bot 22 Application.

Per Phase 7 D-06: workers MAY import a single owning module's service layer
(here `app.modules.auth.telegram_service`). Cross-module imports inside
workers are still forbidden — see app/workers/__init__.py docstring.

Per Phase 7 D-09: NO module-level Application — built inside main()'s scope.
Per Phase 7 D-08: opens db_lifespan_manager() + redis_lifespan_manager()
under AsyncExitStack; pool configuration shared with the API process.

Entrypoint: `python -m app.workers.telegram_bot` (INFRA-06).
"""

from __future__ import annotations

import asyncio
import signal
from contextlib import AsyncExitStack, suppress

from app.core.config import get_settings
from app.core.database import db_lifespan_manager
from app.core.logging import configure_logging
from app.core.redis import redis_lifespan_manager
from app.integrations.telegram import sender as telegram_sender
from app.integrations.telegram.bot import build_application
from app.integrations.telegram.handlers import HandlerContext, start_handler
from app.modules.auth import telegram_service  # D-06 relaxation


async def main() -> None:
    """Long-polling bot main loop."""
    settings = get_settings()
    configure_logging(settings)

    async with AsyncExitStack() as stack:
        _engine, sessionmaker = await stack.enter_async_context(db_lifespan_manager())
        _redis = await stack.enter_async_context(redis_lifespan_manager())

        ctx = HandlerContext(
            session_factory=sessionmaker,
            telegram_service=telegram_service,
            sender=telegram_sender,
        )
        application = build_application(
            token=settings.telegram_bot_token.get_secret_value(),
            handlers=[("start", start_handler)],
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
