"""ARQ scheduled job: poll pending online_refunds against ЮKassa (Phase 51 REFUND-04).

Per Phase 7 D-06 / Phase 18 D-09: this worker file MAY import
``app.modules.online_refunds.cron`` (single owning-module exception applied
to the online_refunds module's recurring I/O fanout).

Transaction ownership (Plan 51-09 / D-32-10): the cron-body helper owns
per-row ``session.begin()`` blocks; this wrapper only passes through the
session factory + YooKassa client and emits the ops-summary log line.

Cadence: every 30 min Europe/Moscow (D-51-17). Independent of the 30-min
pending-age threshold — the cron checks 2x/hr regardless of the per-row
age cutoff.

Observability: emits one structlog INFO
``poll_pending_refunds_complete count=N`` after the helper returns.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.modules.online_refunds.cron import _poll_pending_refunds

_log = structlog.get_logger("workers.scheduled.poll_pending_refunds")


async def poll_pending_refunds(ctx: dict[str, Any]) -> int:
    """Poll pending online_refunds; return count of rows settled-or-canceled this tick.

    Args:
        ctx: ARQ job context. Required keys:
            - ctx["sessionmaker"]: ``async_sessionmaker[AsyncSession]``
              populated by ``WorkerSettings.on_startup``.
            - ctx["yookassa_client"]: ``YooKassaClient`` populated by
              ``WorkerSettings.on_startup`` (D-48-25 mirror of main.py).
            - ctx["redis"] (optional): ARQ pool — ARQ injects this as
              ``ctx['redis']`` for cron jobs so the helper can enqueue
              ``dispatch_fiscal_receipt`` for newly-INSERTed refund-side
              fiscal_receipts rows (verification gap fix).

    Returns:
        int — count of rows whose status moved from 'pending' to a terminal
        state on this run.
    """
    session_factory = ctx["sessionmaker"]
    yookassa_client = ctx["yookassa_client"]
    arq_pool = ctx.get("redis")
    count = await _poll_pending_refunds(session_factory, yookassa_client, arq_pool=arq_pool)
    _log.info("poll_pending_refunds_complete", count=count)
    return count
