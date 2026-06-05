"""ARQ scheduled job: initiate off-session autopay charges for expiring memberships (Phase 84).

APAY-01: charge_expiring_autopay cron — off-session YooKassa charge for memberships expiring soon.

Transaction ownership (Phase 18 D-01 discipline): this function is the transaction owner.
The service helper `_charge_expiring_autopay_memberships` (Plan 84-02) queries eligible
memberships, claims each period, calls YooKassa, and audits the outcome — but does NOT
commit (carries `# noqa: SVC001 caller-owns-txn`). Commit happens here, AFTER the helper
returns, so the entire batch is atomic.

Post-commit enqueue discipline (mirrors webhook `_post_commit_enqueue`): the failure
notification dispatch (`dispatch_autopay_failure_notification`) is enqueued AFTER commit,
never inside the transaction. This prevents an enqueue failure from rolling back a
successful charge batch. The ARQ redis pool is available via `ctx["redis"]` (standard
ARQ 0.28 convention — the same pool the worker uses to dequeue its own jobs).

Observability: emits `charge_expiring_autopay_complete count=N declined=M` AFTER commit.
NOT an audit event — operational summary line (Phase 18 CD-03 discipline).

ФЗ-376 compliance: the service helper's eligibility query requires consent_recorded_at IS NOT NULL.
No membership without recorded autopay consent is ever charged (T-84-07).

D-06 (webhook-locked activation): the cron NEVER activates or creates memberships.
Renewal activation is locked to the payment.succeeded webhook (D-06 invariant).
"""

from __future__ import annotations

from typing import Any

import structlog

from app.modules.autopay_charges import service as autopay_service

_log = structlog.get_logger("workers.scheduled.charge_expiring_autopay")


async def charge_expiring_autopay(ctx: dict[str, Any]) -> int:
    """Initiate off-session autopay charges for memberships expiring within the window.

    Args:
        ctx: ARQ job context dict. Required keys:
            - ctx["sessionmaker"]: `async_sessionmaker[AsyncSession]` populated
              by `WorkerSettings.on_startup` from `core.database.db_lifespan_manager()`.
            - ctx["redis"]: ArqRedis pool for post-commit enqueue (ARQ 0.28 convention).
            - ctx["job_id"], ctx["function_name"]: bound on structlog contextvars
              by `on_job_start`; flow into the summary log line automatically.

    Returns:
        int — number of charge attempts made (ok + declined) on this run.
        ARQ writes this into its result store automatically.
    """
    session_factory = ctx["sessionmaker"]
    async with session_factory() as session:
        count, declined_charge_ids = await autopay_service._charge_expiring_autopay_memberships(
            session
        )
        await session.commit()

    # Post-commit: enqueue failure notifications for each declined claim id.
    # Enqueued AFTER commit (post-commit discipline — mirrors webhook _post_commit_enqueue).
    # The actual notification send is Plan 03; here we just enqueue by job name.
    # T-84-12b: keyed on autopay_charges.id (always-present claim anchor), NOT online_payment_id
    # (which does not exist on a decline — yookassa_payment_id is NOT NULL invariant).
    arq_pool = ctx.get("redis")
    if arq_pool is not None and declined_charge_ids:
        for charge_id in declined_charge_ids:
            await arq_pool.enqueue_job(
                "dispatch_autopay_failure_notification",
                _kwargs={"autopay_charge_id": str(charge_id)},
                _max_tries=3,
                _expires=60,
            )

    # Summary log AFTER commit (CD-03). NOT an audit event — operational summary.
    # job_id/job_name are on the structlog contextvars stack from on_job_start.
    _log.info(
        "charge_expiring_autopay_complete",
        count=count,
        declined=len(declined_charge_ids),
    )
    return count
