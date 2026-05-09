"""ARQ scheduled job: send expiring-soon Telegram DMs (Phase 27 NTF-02 / NTF-03).

Per Phase 7 D-06 / Phase 18 D-09 / Phase 27 D-27-06: this worker file MAY import
`app.modules.memberships.service` (single owning-module exception) AND
`app.integrations.telegram.{sender, copy, bot}` (integrations layer is always
allowed for workers — `app/workers/__init__.py:1-21` rationale).

Bot construction (D-27-06 — Option B LOCKED):
Uses `app.integrations.telegram.bot.build_bot(*, token=...)` — keeps Bot
construction logic isolated to the bot factory module. Inline construction
of the Bot in the worker (Option A) was explicitly rejected.

Transaction ownership (Phase 27 D-27-07 pattern b — multi-session):
The service helper `_send_expiring_notifications` opens its own per-send write
sessions; the worker passes `ctx["sessionmaker"]` (the async_sessionmaker) and
does NOT open a session here. This contrasts with `expire_memberships.py` which
uses a single session (Phase 18 pattern). The reason is that Phase 27 send loop
makes multiple async network calls (Telegram DM) — holding one DB connection
across that I/O is wasteful, so the helper opens fresh sessions per success.

Observability (Phase 18 specifics line 195 / Phase 27 D-27-XX): emits one
structlog INFO `send_expiring_notifications_complete count=N` AFTER the helper
returns. `<job_name>_complete count=N` is the locked summary-event convention.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.core.config import get_settings
from app.integrations.telegram import copy as telegram_copy
from app.integrations.telegram import sender as telegram_sender
from app.integrations.telegram.bot import build_bot
from app.modules.memberships import service as memberships_service

_log = structlog.get_logger("workers.scheduled.send_expiring_notifications")


async def send_expiring_notifications(ctx: dict[str, Any]) -> int:
    """Send 7d/3d/1d expiring-soon DMs; return count of successful sends.

    Args:
        ctx: ARQ job context. Required keys:
            - ctx["sessionmaker"]: `async_sessionmaker[AsyncSession]` populated
              by `WorkerSettings.on_startup` (Phase 18 ARQ-03).
            - ctx["job_id"], ctx["function_name"]: bound on structlog
              contextvars by `on_job_start`.

    Returns:
        int — count of successful DM sends on this run. Each success ⇒ one
        `membership_notifications` row inserted + one audit_log row emitted.
        ARQ writes this count into its result store automatically.
    """
    session_factory = ctx["sessionmaker"]
    settings = get_settings()
    bot = build_bot(token=settings.telegram_bot_token.get_secret_value())

    count = await memberships_service._send_expiring_notifications(
        session_factory,
        bot=bot,
        sender=telegram_sender,
        copy_module=telegram_copy,
    )

    _log.info("send_expiring_notifications_complete", count=count)
    return count
