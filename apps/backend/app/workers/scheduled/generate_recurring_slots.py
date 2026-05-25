"""ARQ scheduled job: materialize concrete trainer availability slots from recurring templates.

Per Phase 59 D-59-04 / REC-02 / PATTERNS.md §generate_recurring_slots.py:

    This worker file MAY import ``app.modules.schedule.service`` — the file
    IS the schedule module's recurring I/O fanout. Cross-module imports are
    still forbidden (no importing memberships / trainers / bookings from this
    file). Single-module-import rule mirrors Phase 18 D-09.

Transaction ownership (Phase 18 D-01 / Phase 59 D-59-04): this function is
the transaction owner. The service helper ``_generate_recurring_slots`` (REC-02
/ noqa: SVC001 caller-owns-txn) expands templates, runs the bulk INSERT with
ON CONFLICT DO NOTHING, emits ``slot_published`` audit per real insert, but
explicitly does NOT commit. Commit happens here, after the helper returns.
If the helper raises, the ``async with session_factory() as session:`` block
exits without committing; the unit-of-work rolls back. The next cron tick
retries safely — the ON CONFLICT (trainer_id, start_time) DO NOTHING gate
ensures repeat runs are idempotent (PITFALL 8).

Observability (Phase 18 CD-03): emits one structlog INFO
``generate_recurring_slots_complete count=N`` AFTER ``session.commit()`` returns
successfully. The line is NOT an audit event — it is an ops-summary line.
``job_id`` and ``job_name`` are already bound on the structlog contextvars
stack by ``WorkerSettings.on_job_start`` (Plan 18-03), so the summary line
carries them automatically.

Convention: ``<job_name>_complete count=N`` is the locked summary-event
shape for all scheduled jobs (mirrors expire_memberships / expire_pt_packages
verbatim — Phase 18 specifics).
"""

from __future__ import annotations

from typing import Any

import structlog

from app.modules.schedule import service as schedule_service

_log = structlog.get_logger("workers.scheduled.generate_recurring_slots")


async def generate_recurring_slots(ctx: dict[str, Any]) -> int:
    """Materialize trainer availability slots from recurring templates; return insert count.

    Args:
        ctx: ARQ job context dict. Required keys:
            - ctx["sessionmaker"]: ``async_sessionmaker[AsyncSession]``
              populated by ``WorkerSettings.on_startup`` (Plan 18-03) from
              ``core.database.db_lifespan_manager()``.
            - ctx["job_id"], ctx["function_name"]: bound on structlog
              contextvars by ``on_job_start`` (Plan 18-03); flow into the
              summary log line via ``merge_contextvars``.

    Returns:
        int — number of rows actually inserted on this run. 0 on a pure
        conflict re-run (idempotency — ON CONFLICT (trainer_id, start_time)
        DO NOTHING). ARQ writes this into its result store automatically.

    Raises:
        Any exception from ``_generate_recurring_slots`` (e.g. audit-payload
        regression at the ``slot_published`` callsite) propagates after the
        session block exits; the unit-of-work rolls back the bulk INSERT +
        any partial audit rows. Next cron tick retries (idempotent — PITFALL 8).
    """
    session_factory = ctx["sessionmaker"]
    async with session_factory() as session:
        count = await schedule_service._generate_recurring_slots(session)
        await session.commit()

    # Summary log AFTER commit returns successfully (Phase 18 CD-03).
    # NOT an audit event — payload carries the count only; job_id/job_name
    # are on the contextvars stack from on_job_start.
    _log.info("generate_recurring_slots_complete", count=count)
    return count
