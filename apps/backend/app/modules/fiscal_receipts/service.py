"""Phase 51 fiscal_receipts service helpers — exposed to ARQ crons (Plan 51-09 / D-51-16).

Caller-owns-txn (D-32-10): the helper opens its own session via the
async_sessionmaker passed by the cron wrapper, but the wrapper owns the
session lifecycle decision (multi-session vs single-session) and the
``session.begin()`` block boundary. The helper does NOT commit at module
level — the ``async with session.begin():`` block in the body commits on
clean exit.

Threat mitigations (Phase 51 T-51-09-01..08):
- ``SELECT ... FOR UPDATE SKIP LOCKED`` (T-51-09-01) lets the cron skip
  rows currently held by the dispatch task; loop budget LIMIT 50 (T-51-09-03)
  bounds worst-case lock contention and DB time per tick.
- ``status='pending'`` is the upstream-failure state (T-51-09-07): the
  Phase 50 atomic UoW inserts with ``status='sent'``, so any row in
  'pending' state never reached the dispatch task.
- Repudiation safety (T-51-09-08): audit row emitted inside the same
  ``session.begin()`` block before commit (D-32-10 / D-49-13 lineage).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core import audit
from app.modules.fiscal_receipts.constants import STATUS_FAILED, STATUS_PENDING
from app.modules.fiscal_receipts.models import FiscalReceipt

_log = structlog.get_logger("modules.fiscal_receipts.service")

# Plan 51-09 / D-51-16 — staleness window in seconds.
# Independent knob from the cron cadence (15 min) — rows older than 90s
# AND still 'pending' are considered upstream-failed.
_STALE_PENDING_SECONDS: int = 90

# Loop budget per cron tick (D-51-17 step 6 — Phase 27 expiring-notifications
# precedent; bounds DB time per tick to mitigate T-51-09-03 DoS).
_LOOP_BUDGET_PER_TICK: int = 50


async def _monitor_stale_fiscal_receipts(
    session_factory: async_sessionmaker[Any],
    arq_pool: Any | None = None,
) -> int:
    """Phase 51 FISCAL-06 — flip stale fiscal_receipts(pending) → failed.

    Selects fiscal_receipts with ``status='pending' AND created_at < now() -
    INTERVAL '90 seconds'``, ``FOR UPDATE SKIP LOCKED``, ``LIMIT 50``.

    For each row: ``status='failed'``, ``failed_at=now(UTC)``,
    ``failure_reason='stale_pending_no_dispatch'``; emit
    ``fiscal_receipt_failed`` audit (chain-root — no audit_correlation_id
    available for vacuous chain).

    Returns count of rows flipped.

    Phase 52 D-52-10: when ``arq_pool`` is non-None, enqueues
    ``dispatch_payment_notification(kind='fiscal_failed')`` for each flipped
    row post-commit as a best-effort owner alert. Enqueues are accumulated
    during the flip loop and fired after the commit boundary exits (never
    inside the txn). Guard-wrapped (pool is not None) so unit tests are
    unaffected.
    """
    flipped = 0
    failed_payment_ids: list[UUID] = []
    cutoff = datetime.now(UTC) - timedelta(seconds=_STALE_PENDING_SECONDS)
    async with session_factory() as session, session.begin():
        stmt = (
            select(FiscalReceipt)
            .where(FiscalReceipt.status == STATUS_PENDING)
            .where(FiscalReceipt.created_at < cutoff)
            .limit(_LOOP_BUDGET_PER_TICK)
            .with_for_update(skip_locked=True)
        )
        rows = (await session.execute(stmt)).scalars().all()
        for row in rows:
            row.status = STATUS_FAILED
            row.failed_at = datetime.now(UTC)
            row.failure_reason = "stale_pending_no_dispatch"
            await audit.emit(
                session,
                "fiscal_receipt_failed",
                actor_user_id=None,
                resource_type="fiscal_receipt",
                resource_id=row.id,
                audit_correlation_id=(
                    str(row.audit_correlation_id)
                    if row.audit_correlation_id is not None
                    else None
                ),
                fiscal_receipt_id=str(row.id),
                failure_reason="stale_pending_no_dispatch",
            )
            # Capture payment_id before commit (rows detach after session.begin() exits).
            failed_payment_ids.append(row.payment_id)
            flipped += 1
    # Phase 52 D-52-10 — best-effort owner alerts, post-commit, None-safe.
    if arq_pool is not None:
        for payment_id in failed_payment_ids:
            await arq_pool.enqueue_job(
                "dispatch_payment_notification",
                _kwargs={"payment_id": str(payment_id), "kind": "fiscal_failed"},
                _max_tries=3,
                _expires=60,
            )
    return flipped


__all__ = ("_monitor_stale_fiscal_receipts",)
