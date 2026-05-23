"""ARQ scheduled job: flip stale fiscal_receipts pending → failed (Phase 51 FISCAL-06).

Per Phase 7 D-06 / Phase 18 D-09: this worker file MAY import
``app.modules.fiscal_receipts.service`` (single owning-module exception).

Transaction ownership (Phase 51 Plan 51-09 / D-32-10): the service helper
owns the ``session.begin()`` block; this wrapper passes ``ctx['sessionmaker']``
and emits the ops-summary log line AFTER the helper returns.

Cadence: every 15 min Europe/Moscow (D-51-16). Cadence is independent of
the 90s staleness window (the cron checks 4x/hr regardless of the per-row
age threshold).

Observability (Phase 18 specifics convention): emits one structlog INFO
``monitor_stale_fiscal_receipts_complete count=N`` after the helper returns.
``<job_name>_complete count=N`` is the locked summary-event shape.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.modules.fiscal_receipts.service import _monitor_stale_fiscal_receipts

_log = structlog.get_logger("workers.scheduled.monitor_stale_fiscal_receipts")


async def monitor_stale_fiscal_receipts(ctx: dict[str, Any]) -> int:
    """Flip stale fiscal_receipts(pending) → failed; return count of newly-failed rows.

    Args:
        ctx: ARQ job context. Required keys:
            - ctx["sessionmaker"]: ``async_sessionmaker[AsyncSession]``
              populated by ``WorkerSettings.on_startup``.

    Returns:
        int — count of rows whose status flipped from 'pending' to 'failed'.
        ARQ writes this into its result store automatically.
    """
    session_factory = ctx["sessionmaker"]
    count = await _monitor_stale_fiscal_receipts(session_factory)
    _log.info("monitor_stale_fiscal_receipts_complete", count=count)
    return count
