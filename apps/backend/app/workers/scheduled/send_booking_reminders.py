"""ARQ scheduled job: send 24h booking reminder DMs (Phase 39 CRON-02).

Per Phase 7 D-06 / Phase 18 D-09 / Phase 39 D-39-06 (multi-session): this
worker file MAY import ``app.modules.bookings.service`` (single-owning-
module exception) + ``app.modules.bookings.notifications`` + the
``app.integrations.telegram.{sender, bot}`` integrations layer. Cross-
module imports are still forbidden (no importing memberships /
pt_packages from this file).

Bot construction (D-39-10 / D-27-06 mirror): fresh Bot per worker
invocation via ``app.integrations.telegram.bot.build_bot(*, token=...)``.
NEVER cached at module scope (aiohttp session leak risk under repeated
cron firings).

Transaction ownership (D-39-06 pattern b — multi-session): the helper
opens its own per-send write sessions; the worker passes
``ctx["sessionmaker"]`` (the async_sessionmaker) and does NOT open a
session here. The loop makes Telegram I/O between writes — holding one
DB connection across that I/O would waste the pool (mirror v1.3
D-27-07b).

Cron schedule: hour=3, minute=35 UTC = 06:35 MSK (container TZ=UTC per
Phase 18 D-09 locked Key Decisions). Order per D-39-16: fires 10 min
after expire_pt_packages at 06:25.

Observability (Phase 18 CD-03 / locked summary-event convention): emits
one structlog INFO ``send_booking_reminders_complete count=N`` AFTER the
helper returns. ``job_id`` and ``job_name`` are bound on the structlog
contextvars stack by ``WorkerSettings.on_job_start``, so the summary
line carries them automatically.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.core.config import get_settings
from app.integrations.telegram import sender as telegram_sender
from app.integrations.telegram.bot import build_bot
from app.modules.bookings import notifications as bookings_notifications
from app.modules.bookings import service as bookings_service

_log = structlog.get_logger("workers.scheduled.send_booking_reminders")


async def send_booking_reminders(ctx: dict[str, Any]) -> int:
    """Send 24h-out booking reminder DMs; return count of successful sends.

    Args:
        ctx: ARQ job context. Required keys:
            - ctx["sessionmaker"]: ``async_sessionmaker[AsyncSession]``
              populated by ``WorkerSettings.on_startup`` (Phase 18 ARQ-03).
            - ctx["job_id"], ctx["function_name"]: bound on structlog
              contextvars by ``on_job_start``.

    Returns:
        int — count of successful DM sends on this run. Each success ⇒
        one ``booking_notifications`` row inserted (no separate audit
        event — the row IS the audit per D-39-14). ARQ writes this count
        into its result store automatically.
    """
    session_factory = ctx["sessionmaker"]
    settings = get_settings()
    bot = build_bot(token=settings.telegram_bot_token.get_secret_value())

    count = await bookings_service._send_booking_reminders(
        session_factory,
        bot=bot,
        sender=telegram_sender,
        notifications_module=bookings_notifications,
    )

    _log.info("send_booking_reminders_complete", count=count)
    return count
