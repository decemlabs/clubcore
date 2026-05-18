"""ARQ scheduled job: flip overdue confirmed bookings to no_show (Phase 39 CRON-01).

Per Phase 7 D-06 / Phase 18 D-09: this worker file MAY import
``app.modules.bookings.service`` — the file IS the bookings module's recurring
no-show classification fanout. Cross-module imports are still forbidden (no
importing memberships / payments / pt_packages from this file).

Transaction ownership (Phase 18 D-01 / Phase 39 D-39-06 single-session):
this function is the transaction owner. The service helper
``_mark_no_show_bookings`` (D-39-07, with ``SELECT FOR UPDATE OF b``) issues
the SELECT + bulk UPDATE + per-row audit emits but explicitly does NOT
commit (carries ``# noqa: SVC001 caller-owns-txn``); commit happens here,
after the helper returns. If the helper raises (e.g. audit-payload
regression at the ``booking_no_show`` callsite), the ``async with
session_factory() as session:`` block exits without committing, the
SQLAlchemy unit-of-work rolls back, and the next cron tick picks up the same
rows again — the SQL-level idempotency gate ``WHERE b.status='confirmed'``
makes this a safe retry (D-39-13).

Cron schedule: hour=20, minute=10 UTC = 23:10 MSK (container TZ=UTC per
Phase 18 D-09 locked Key Decisions). See workers/__init__.py for the
cron(...) entry. The 23:10 MSK timing is the "evening tick" — after the
gym's normal operating hours close, classifying any confirmed booking
whose slot ended without a recorded PT-session as no-show.

Observability (Phase 18 CD-03): emits one structlog INFO
``mark_no_show_bookings_complete count=N`` AFTER ``session.commit()``
returns successfully. The line is NOT an audit event — it is an ops-summary
line. ``job_id`` and ``job_name`` are already bound on the structlog
contextvars stack by ``WorkerSettings.on_job_start`` (Plan 18-03), so the
summary line carries them automatically.

Convention: ``<job_name>_complete count=N`` is the locked summary-event
shape for all scheduled jobs (mirrors expire_pt_packages / expire_memberships
verbatim — Phase 18 specifics).
"""

from __future__ import annotations

from typing import Any

import structlog

from app.modules.bookings import service as bookings_service

_log = structlog.get_logger("workers.scheduled.mark_no_show_bookings")


async def mark_no_show_bookings(ctx: dict[str, Any]) -> int:
    """Mark overdue confirmed bookings as no_show; return count of newly-marked rows.

    Args:
        ctx: ARQ job context dict. Required keys:
            - ctx["sessionmaker"]: ``async_sessionmaker[AsyncSession]``
              populated by ``WorkerSettings.on_startup`` (Plan 18-03) from
              ``core.database.db_lifespan_manager()``.
            - ctx["job_id"], ctx["function_name"]: bound on structlog
              contextvars by ``on_job_start`` (Plan 18-03); flow into the
              summary log line via ``merge_contextvars``.

    Returns:
        int — number of rows whose status flipped from 'confirmed' to
        'no_show' on this run. ARQ writes this into its result store
        automatically.
    """
    session_factory = ctx["sessionmaker"]
    async with session_factory() as session:
        count = await bookings_service._mark_no_show_bookings(session)
        await session.commit()

    # Summary log AFTER commit returns successfully (Phase 18 CD-03).
    # NOT an audit event — payload carries the count only; job_id/job_name
    # are on the contextvars stack from on_job_start.
    _log.info("mark_no_show_bookings_complete", count=count)
    return count
