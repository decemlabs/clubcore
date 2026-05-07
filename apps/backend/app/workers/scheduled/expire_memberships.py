"""ARQ scheduled job: flip overdue active memberships to expired (Phase 18 ARQ-01).

Per Phase 7 D-06 / Phase 18 D-09: this worker file MAY import
`app.modules.memberships.service` — the file IS the memberships module's
recurring I/O fanout. Cross-module imports are still forbidden (no importing
clients/visits/billing from this file).

Transaction ownership (Phase 18 D-01): this function is the transaction owner.
The service helper `_expire_due_memberships` (Plan 18-01) issues the bulk
UPDATE + per-row audit emits but explicitly does NOT commit (carries
`# noqa: SVC001 caller-owns-txn`); commit happens here, after the helper
returns. If the helper raises (e.g. audit-taxonomy regression at the
`membership_expired` callsite), the `async with session_factory() as session:`
block exits without committing, the SQLAlchemy unit-of-work rolls back, and
the next cron tick picks up the same rows again — the SQL-level idempotency
gate `WHERE status='active'` makes this a safe retry.

Observability (Phase 18 CD-03): emits one structlog INFO
`expire_memberships_complete count=N` AFTER `session.commit()` returns
successfully. The line is NOT an audit event — it is an ops-summary line.
`job_id` and `job_name` are already bound on the structlog contextvars stack
by `WorkerSettings.on_job_start` (Plan 18-03), so the summary line carries
them automatically (PITFALLS Pitfall 14).

Convention (Phase 18 specifics line 195): `<job_name>_complete count=N` is
the locked summary-event shape for all future scheduled jobs (v1.3+
`expire_otps_complete`, `aggregate_visits_daily_complete`, etc.).
"""

from __future__ import annotations

from typing import Any

import structlog

from app.modules.memberships import service as memberships_service

_log = structlog.get_logger("workers.scheduled.expire_memberships")


async def expire_memberships(ctx: dict[str, Any]) -> int:
    """Flip overdue active memberships to expired; return count of newly-expired rows.

    Args:
        ctx: ARQ job context dict. Required keys:
            - ctx["sessionmaker"]: `async_sessionmaker[AsyncSession]` populated
              by `WorkerSettings.on_startup` (Plan 18-03) from
              `core.database.db_lifespan_manager()`.
            - ctx["job_id"], ctx["function_name"]: bound on structlog
              contextvars by `on_job_start` (Plan 18-03); flow into the
              summary log line via `merge_contextvars`.

    Returns:
        int — number of rows whose status flipped from 'active' to 'expired'
        on this run. ARQ writes this into its result store automatically.

    Raises:
        Any exception from `_expire_due_memberships` (e.g. taxonomy regression
        at the audit.emit callsite) propagates after the session block exits;
        the SAVEPOINT-style unit-of-work rolls back the bulk UPDATE + any
        partial audit rows. Next cron tick retries.
    """
    session_factory = ctx["sessionmaker"]
    async with session_factory() as session:
        count = await memberships_service._expire_due_memberships(session)
        await session.commit()

    # Summary log AFTER commit returns successfully (CD-03). NOT an audit
    # event — payload carries the count only; job_id/job_name are on the
    # contextvars stack from on_job_start.
    _log.info("expire_memberships_complete", count=count)
    return count
