"""ARQ scheduled job: flip overdue active PT-packages to expired (Phase 33 PT-12).

Per Phase 7 D-06 / Phase 18 D-09: this worker file MAY import
``app.modules.pt_packages.service`` — the file IS the pt_packages module's
recurring I/O fanout. Cross-module imports are still forbidden (no importing
memberships / payments / trainers from this file).

Transaction ownership (Phase 18 D-01 / Phase 33 D-33-13): this function is
the transaction owner. The service helper ``_expire_due_pt_packages`` (Plan
33-02 / D-33-13) issues the bulk UPDATE + per-row audit emits but explicitly
does NOT commit (carries ``# noqa: SVC001 caller-owns-txn``); commit happens
here, after the helper returns. If the helper raises (e.g. audit-payload
regression at the ``pt_package_expired`` callsite), the ``async with
session_factory() as session:`` block exits without committing, the
SQLAlchemy unit-of-work rolls back, and the next cron tick picks up the same
rows again — the SQL-level idempotency gate ``WHERE status='active'`` makes
this a safe retry (D-33-13).

Observability (Phase 18 CD-03): emits one structlog INFO
``expire_pt_packages_complete count=N`` AFTER ``session.commit()`` returns
successfully. The line is NOT an audit event — it is an ops-summary line.
``job_id`` and ``job_name`` are already bound on the structlog contextvars
stack by ``WorkerSettings.on_job_start`` (Plan 18-03), so the summary line
carries them automatically.

Convention: ``<job_name>_complete count=N`` is the locked summary-event
shape for all scheduled jobs (mirrors expire_memberships verbatim — Phase
18 specifics).
"""

from __future__ import annotations

from typing import Any

import structlog

from app.modules.pt_packages import service as pt_packages_service

_log = structlog.get_logger("workers.scheduled.expire_pt_packages")


async def expire_pt_packages(ctx: dict[str, Any]) -> int:
    """Flip overdue active PT-packages to expired; return count of newly-expired rows.

    Args:
        ctx: ARQ job context dict. Required keys:
            - ctx["sessionmaker"]: ``async_sessionmaker[AsyncSession]``
              populated by ``WorkerSettings.on_startup`` (Plan 18-03) from
              ``core.database.db_lifespan_manager()``.
            - ctx["job_id"], ctx["function_name"]: bound on structlog
              contextvars by ``on_job_start`` (Plan 18-03); flow into the
              summary log line via ``merge_contextvars``.

    Returns:
        int — number of rows whose status flipped from 'active' to 'expired'
        on this run. ARQ writes this into its result store automatically.

    Raises:
        Any exception from ``_expire_due_pt_packages`` (e.g. audit-payload
        regression at the ``pt_package_expired`` callsite) propagates after
        the session block exits; the unit-of-work rolls back the bulk
        UPDATE + any partial audit rows. Next cron tick retries (D-33-13).
    """
    session_factory = ctx["sessionmaker"]
    async with session_factory() as session:
        count = await pt_packages_service._expire_due_pt_packages(session)
        await session.commit()

    # Summary log AFTER commit returns successfully (Phase 18 CD-03).
    # NOT an audit event — payload carries the count only; job_id/job_name
    # are on the contextvars stack from on_job_start.
    _log.info("expire_pt_packages_complete", count=count)
    return count
