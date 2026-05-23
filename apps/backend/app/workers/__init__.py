"""ARQ background-worker namespace + WorkerSettings entrypoint (Phase 18 ARQ-03).

Workers consume tasks from Redis and may call app.integrations.* (D-03).
They MUST NOT import app.modules.* directly — events bus pattern lands in v1.2+.

EXCEPTION (Phase 7 D-06): app.workers.telegram_bot is permitted to import
`app.modules.auth.telegram_service` — workers MAY import a single owning
module's service layer (e.g., app.modules.auth.telegram_service) when the
worker IS that module's I/O fanout. Cross-module imports inside workers are
still forbidden (no telegram_bot importing modules.clients, etc.).

EXCEPTION (Phase 18 D-09): app.workers.scheduled.expire_memberships imports
`app.modules.memberships.service` — same shape as D-06, applied to the
scheduled cron worker. Each `app/workers/scheduled/<job>.py` file MAY import
ONE owning module's service layer; cross-module imports inside one scheduled
file remain forbidden.

These relaxations are documented-only — no importlinter contract change is
required because no current contract enforces `workers ⊥ modules`. The
contracts that DO exist (`core-not-depend-on-modules`, `modules-independent`,
`integrations-not-depend-on-modules`) all remain green.

WorkerSettings (Phase 18 ARQ-03):
  - `redis_settings` = `RedisSettings.from_dsn(str(get_settings().redis_url))`.
  - `functions = [expire_memberships]` — every callable ARQ may invoke.
  - `cron_jobs = [cron(expire_memberships, hour=3, minute=5, unique=True,
    keep_result=60)]` — 06:05 Europe/Moscow given container
    `TZ=UTC` (locked Phase 15 Key Decisions). `unique=True` is necessary
    but NOT sufficient — the SQL-level idempotency gate
    (`WHERE status='active'`) is the real defence (PITFALLS Pitfall 4).
  - `on_startup(ctx)` opens `db_lifespan_manager()` via AsyncExitStack,
    stashes the stack in `ctx['_db_stack']`, exposes
    `(engine, sessionmaker)` as `ctx['engine'] / ctx['sessionmaker']`,
    AND runs the cron-resolution invariant
    `assert all(c.coroutine.__name__ in {f.__name__ for f in functions}
    for c in cron_jobs)` (PITFALLS Pitfall 4 step 6 — silent no-op trap:
    ARQ does nothing if a cron entry references a function name absent
    from `functions`; the assertion catches this at worker boot, not at
    06:05 the next morning).
  - `on_shutdown(ctx)` closes the AsyncExitStack — disposes engine,
    releases sessionmaker.
  - `on_job_start(ctx)` clears + binds `job_id`/`job_name` on the
    structlog contextvars stack (Pitfall 14 — direct mirror of
    `RequestIdMiddleware` shape in `app/core/middleware.py:21-25`).
    Phase 41 INFRA-39 / D-41-08 ALSO sets the actor_context_var
    baseline to None for the duration of this job, mirroring
    ActorContextMiddleware's request-scoped envelope.
  - `on_job_end(ctx)` clears contextvars + resets actor_context_var
    (prevents leak across runs in the same asyncio task — Pitfall 14
    mitigation step 3).

ARQ ctx limitation (Phase 41 D-41-08 fallback):
  ARQ 0.28's `run_job` only exposes `job_id / job_try / enqueue_time /
  score` in ctx; the per-call `*args / **kwargs` flow directly to the
  job coroutine without landing on ctx. Therefore on_job_start cannot
  inspect job kwargs for `actor_user_id` / `actor_email_snapshot`.
  Pattern: job bodies needing actor attribution call
  `set_actor({"user_id": ..., "email": ...})` themselves near the top
  of the job (a token is unnecessary because on_job_end resets the
  contextvar to the prior frame). System cron jobs leave the contextvar
  as None — actor_user_id=None at the emit() callsite triggers the
  D-41-10 NULL/NULL row.
"""

from __future__ import annotations

from contextlib import AsyncExitStack
from typing import Any, ClassVar

import structlog
import structlog.contextvars
from arq.connections import RedisSettings
from arq.cron import cron

from app.core.config import get_settings
from app.core.database import db_lifespan_manager

# ORM eager-imports (REG-29-04 / D-41-29 — REG-29-04 mirror).
# ----------------------------------------------------------------
# Cron one-shot scripts (`app/workers/scheduled/<job>.py`) and ad-hoc
# `arq` invocations boot via this package's __init__; if any ORM model
# is only reachable through a `from app.modules.X.models import ...`
# inside a deeply-nested service, `Base.metadata.tables` is missing
# that table at worker boot time and the first SELECT raises a
# "no such table" error from SQLAlchemy's reflection layer (the v1.3
# expiring-notifications regression that birthed REG-29-04).
#
# Rule: every ORM table added in v1.6+ that the worker namespace might
# touch — directly OR indirectly through a cron job — gets an eager
# import here so the module-load side effect registers the table on
# `Base.metadata` before any worker code runs.
from app.integrations.email.models import (  # noqa: F401
    EmailSendLog,  # Phase 42 D-42-33 — email_send_log eager-import (REG-29-04)
)
from app.modules.auth.password_reset_token_model import (  # noqa: F401
    PasswordResetToken,  # Phase 41 INFRA-38 / D-41-29 — password_reset_tokens
)
from app.modules.fiscal_receipts.tasks import dispatch_fiscal_receipt
from app.modules.payments.models import (  # noqa: F401
    PaymentReceipt,  # Phase 45 D-45-20 — payment_receipts eager-import (REG-29-04)
)
from app.workers.scheduled.cleanup_password_reset_tokens import cleanup_password_reset_tokens
from app.workers.scheduled.expire_memberships import expire_memberships
from app.workers.scheduled.expire_pt_packages import expire_pt_packages
from app.workers.scheduled.mark_no_show_bookings import mark_no_show_bookings
from app.workers.scheduled.monitor_stale_fiscal_receipts import monitor_stale_fiscal_receipts
from app.workers.scheduled.poll_pending_refunds import poll_pending_refunds
from app.workers.scheduled.send_booking_reminders import send_booking_reminders
from app.workers.scheduled.send_expiring_notifications import send_expiring_notifications
from app.workers.tasks.dispatch_email import dispatch_email

_log = structlog.get_logger("workers")


class WorkerSettings:
    """ARQ WorkerSettings — entrypoint resolved by `arq app.workers.WorkerSettings`.

    Class attributes only — ARQ reads them via class introspection, never
    instantiates this class. `ClassVar[...]` annotations satisfy mypy strict
    mode against ARQ's untyped-attribute introspection.
    """

    redis_settings = RedisSettings.from_dsn(str(get_settings().redis_url))

    functions: ClassVar[list[Any]] = [
        expire_memberships,
        send_expiring_notifications,
        expire_pt_packages,
        send_booking_reminders,  # Phase 39 CRON-02
        mark_no_show_bookings,  # Phase 39 CRON-01
        dispatch_email,  # Phase 42 EMAIL-03 — request-handler-driven (NOT a cron)
        cleanup_password_reset_tokens,  # Phase 44 D-44-31 — housekeeping
        # Phase 51 FISCAL-05 — request-handler-driven dispatch task.
        # Bare callable per the dispatch_email convention (Option B from
        # plan 51-05); per-enqueue `_max_tries=3, _expires=60` carries the
        # ARQ retry contract from D-51-Discretion / Pitfall 11 step 2.
        dispatch_fiscal_receipt,
        # Phase 51 FISCAL-06 / Plan 51-09 — every 15 min stale-pending sweep.
        monitor_stale_fiscal_receipts,
        # Phase 51 REFUND-04 / Plan 51-09 — every 30 min ЮKassa-side poll
        # for pending online_refunds older than 30 min.
        poll_pending_refunds,
    ]

    # NOTE (Rule 4 deviation, 2026-05-07): The plan locked
    # `keep_cronjob_progress=60` from ARQ 0.26 docs, but the installed
    # version is `arq==0.28.0` (uv.lock — pyproject pin is `>=0.26`),
    # which removed `keep_cronjob_progress` from `cron(...)` and replaced
    # the Redis result-retention knob with `keep_result` (seconds). The
    # original intent — bound the lifetime of ARQ's per-tick tracking key
    # so `unique=True` dedup is not unbounded — maps to `keep_result=60`
    # in 0.28. Documented in SUMMARY 18-03; user should confirm at verify
    # time whether to (a) accept the rename, (b) downgrade arq to <0.27.
    cron_jobs: ClassVar[list[Any]] = [
        cron(
            expire_memberships,
            hour=3,
            minute=5,
            unique=True,
            keep_result=60,
        ),
        cron(
            send_expiring_notifications,
            hour=3,
            minute=15,
            unique=True,
            keep_result=60,
        ),
        # Phase 33 PT-12 — D-33-13: 06:25 Europe/Moscow (container TZ=UTC).
        # SQL-level idempotency via WHERE status='active' is the real gate
        # (PITFALLS Pitfall 4); unique=True dedups concurrent ARQ ticks.
        cron(
            expire_pt_packages,
            hour=3,
            minute=25,
            unique=True,
            keep_result=60,
        ),
        # Phase 39 CRON-02 — 06:35 MSK morning reminder (container TZ=UTC).
        # Sends 24h-out booking reminder DMs; LEFT JOIN booking_notifications
        # + WHERE n.id IS NULL is the SQL-level idempotency pre-filter
        # (D-39-08); unique=True dedups concurrent ARQ ticks. Multi-session
        # per-send pattern (D-39-06b) frees the DB connection across N
        # Telegram HTTPS round-trips. Order per D-39-16: fires 10 min after
        # expire_pt_packages at 06:25 and BEFORE mark_no_show_bookings's
        # 23:10 evening tick.
        cron(
            send_booking_reminders,
            hour=3,
            minute=35,
            unique=True,
            keep_result=60,
        ),
        # Phase 39 CRON-01 — 23:10 MSK evening tick (container TZ=UTC).
        # Flips overdue confirmed bookings (slot.end_time < now()) to
        # no_show. Order per D-39-16: this is the LAST cron entry — the
        # send_booking_reminders entry above sits between expire_pt_packages
        # and this one (final order: memberships -> expiring_notifs ->
        # pt_packages -> reminders -> no_show).
        # SQL-level idempotency via WHERE b.status='confirmed' is the real
        # gate (PITFALLS Pitfall 4); unique=True dedups concurrent ARQ
        # ticks. SELECT FOR UPDATE OF b (D-39-07) serializes against
        # pt_sessions.service.record_pt_session (D-38-19).
        cron(
            mark_no_show_bookings,
            hour=20,
            minute=10,
            unique=True,
            keep_result=60,
        ),
        # Phase 44 D-44-31/32 — daily 03:30 Europe/Moscow (container TZ=UTC
        # → hour=0, minute=30). Off-peak: well away from the 06:05-06:35
        # morning notification crons above and the 23:10 MSK no-show cron.
        # 30-day retention per D-41-06; DELETEs password_reset_tokens whose
        # expires_at is older than now() - INTERVAL '30 days'. No audit
        # emit (housekeeping, not an observable state change — D-44-31).
        cron(
            cleanup_password_reset_tokens,
            hour=0,
            minute=30,
            unique=True,
            keep_result=60,
        ),
        # Phase 51 FISCAL-06 / Plan 51-09 (D-51-16) — every 15 min sweep
        # of stale-pending fiscal_receipts. Cadence is independent of the
        # 90s staleness window — the cron checks 4x/hr regardless of the
        # per-row age threshold. SQL-level safety via FOR UPDATE SKIP
        # LOCKED + LIMIT 50 (T-51-09-01 / T-51-09-03); unique=True dedups
        # concurrent ARQ ticks (Pitfall 4).
        cron(
            monitor_stale_fiscal_receipts,
            minute={0, 15, 30, 45},
            hour=set(range(24)),
            unique=True,
            keep_result=60,
        ),
        # Phase 51 REFUND-04 / Plan 51-09 (D-51-17) — every 30 min poll
        # of pending online_refunds. Cadence independent of the 30-min
        # pending-age cutoff. Multi-session pattern releases the DB
        # connection across N HTTPS round-trips to ЮKassa
        # (T-51-09-02 mitigation).
        cron(
            poll_pending_refunds,
            minute={0, 30},
            hour=set(range(24)),
            unique=True,
            keep_result=60,
        ),
    ]

    @staticmethod
    async def on_startup(ctx: dict[str, Any]) -> None:
        """Open DB lifespan + stash stack in ctx + run cron-resolution invariant.

        AsyncExitStack survives this function's return (stored in ctx); on_shutdown
        closes it. `engine` / `sessionmaker` are exposed at the top of `ctx` so
        worker entries (e.g. `expire_memberships`) can read `ctx['sessionmaker']`
        without touching the stack.

        PITFALLS Pitfall 4 step 6: assert every cron entry's coroutine name is
        in `functions` so a typo at the registration site fails LOUD at boot
        rather than silently producing zero ticks at 06:05.
        """
        function_names = {f.__name__ for f in WorkerSettings.functions}
        cron_function_names = {c.coroutine.__name__ for c in WorkerSettings.cron_jobs}
        unresolved = cron_function_names - function_names
        assert not unresolved, (
            f"cron_jobs reference function names not in WorkerSettings.functions: "
            f"{sorted(unresolved)}. Add the missing callables to `functions` or "
            f"fix the cron registration. (Pitfall 4 step 6 — silent no-op trap.)"
        )

        stack = AsyncExitStack()
        engine, sessionmaker = await stack.enter_async_context(db_lifespan_manager())
        ctx["_db_stack"] = stack
        ctx["engine"] = engine
        ctx["sessionmaker"] = sessionmaker

        # Phase 42 D-42-26 / EMAIL-04 — REG-29-03 double-wire of EmailDispatcher.
        # The IDENTICAL symbol reference `enqueue_email_dispatch` is also passed
        # in app/main.py:create_app() so the Phase 42 parity test (plan 42-11)
        # sees a byte-equal callable in both processes. The per-process ArqRedis
        # pool itself differs (each process holds its own pool reference); only
        # the dispatcher function reference must match.
        #
        # Local imports keep the top-of-module clean and avoid eager-loading
        # email integration code in cron-only worker invocations that never
        # dequeue a dispatch_email job.
        from app.core.config import get_settings as _get_settings_local
        from app.core.dependencies import (
            register_email_dispatcher,
            register_fiscal_receipt_dispatcher,  # Phase 47 D-47-01 — REG-29-03 double-wire.
            register_yookassa_client_provider,  # Phase 47 D-47-01 — REG-29-03 double-wire.
        )
        from app.integrations.email.dispatcher import (
            enqueue_email_dispatch,
            register_arq_pool,
        )
        from app.integrations.email.factory import build_email_client
        from app.integrations.yookassa.client import YooKassaClient
        from app.integrations.yookassa.factory import build_yookassa_client
        from app.integrations.yookassa.settings import YooKassaSettings

        settings_local = _get_settings_local()

        # LOCKED async — plan 42-07 ships build_email_client as async def. The
        # non-sandbox branch awaits a real Yandex Cloud Postbox /domains probe;
        # sync def + asyncio.run would crash inside ARQ's running event loop.
        ctx["email_client"] = await build_email_client(settings=settings_local.email)

        register_email_dispatcher(enqueue_email_dispatch)

        # Phase 48 D-48-25 — REG-29-03 mirror of main.py: construct the
        # YooKassaClient inside on_startup so the worker process owns its
        # own httpx.AsyncClient. The parity test (Plan 48-07) now asserts
        # "real wiring in both processes" rather than object identity.
        yookassa_settings = YooKassaSettings()
        ctx["yookassa_client"] = await build_yookassa_client(settings=yookassa_settings)

        async def _yookassa_client_provider() -> YooKassaClient:
            client: YooKassaClient = ctx["yookassa_client"]
            return client

        register_yookassa_client_provider(_yookassa_client_provider)

        # Phase 51 FISCAL-05 — REAL FiscalReceiptDispatcher closure
        # (REG-29-03 double-wire mirror of app/main.py:create_app()). Replaces
        # the Phase 49 phase49_fiscal_dispatcher_stub which raised
        # NotImplementedError. The closure captures the worker's own
        # ArqRedis pool exposed at ``ctx["redis"]`` (ARQ 0.28 convention —
        # workers self-enqueue using the same pool used to dequeue, mirrors
        # the register_arq_pool(ctx["redis"]) call below for the email
        # dispatcher). Per-enqueue `_max_tries=3, _expires=60` per
        # D-51-Discretion / Pitfall 11 step 2 — keeps the retry contract
        # outside ``WorkerSettings.functions`` (Option B in plan 51-05).
        from uuid import UUID as _UUID

        arq_pool = ctx["redis"]

        async def _real_fiscal_receipt_dispatcher(
            *,
            fiscal_receipt_id: _UUID,
            audit_correlation_id: _UUID | None,
        ) -> None:
            # audit_correlation_id is part of the Protocol-pinned signature
            # but is not carried on the enqueue (the task body re-reads it
            # from the fiscal_receipts row).
            del audit_correlation_id
            await arq_pool.enqueue_job(
                "dispatch_fiscal_receipt",
                str(fiscal_receipt_id),
                _max_tries=3,
                _expires=60,
            )

        register_fiscal_receipt_dispatcher(_real_fiscal_receipt_dispatcher)

        # ARQ 0.28 exposes the in-worker ArqRedis pool to job bodies via
        # ctx["redis"] (the standard ARQ convention). The worker's own pool
        # reference is the same Redis client used to dequeue this job;
        # reusing it for re-enqueue (e.g., when a scheduled cron emits an
        # email later in Phase 45) is the project-canonical wiring.
        register_arq_pool(ctx["redis"])

        _log.info("worker_startup_complete", function_count=len(function_names))

    @staticmethod
    async def on_shutdown(ctx: dict[str, Any]) -> None:
        """Close YooKassaClient (Phase 48 D-48-25) + DB AsyncExitStack.

        Closes the long-lived httpx.AsyncClient owned by the worker's
        YooKassaClient BEFORE the DB stack so the event loop is still
        healthy when httpx drains in-flight requests. Then disposes the
        SQLAlchemy engine + sessionmaker via the AsyncExitStack stored in
        ctx.
        """
        # Phase 48 D-48-25 — close the long-lived httpx client cleanly.
        yookassa_client = ctx.get("yookassa_client")
        if yookassa_client is not None:
            await yookassa_client.aclose()

        stack: AsyncExitStack | None = ctx.get("_db_stack")
        if stack is not None:
            await stack.aclose()
        _log.info("worker_shutdown_complete")

    @staticmethod
    async def on_job_start(ctx: dict[str, Any]) -> None:
        """Bind job_id + job_name on structlog contextvars (Pitfall 14).

        Direct mirror of `RequestIdMiddleware` shape (clear THEN bind) so audit
        rows + summary log lines emitted during the job carry job_id/job_name
        the same way HTTP-side rows carry request_id/path/method.

        Phase 41 INFRA-39 / D-41-08: also sets actor_context_var to None as
        the job-scoped baseline. Job bodies that need actor attribution call
        `set_actor(...)` themselves near the top — ARQ 0.28's ctx does not
        surface job kwargs (see module-level docstring "ARQ ctx limitation").
        The set-token is stashed on ctx so on_job_end can reset cleanly even
        if the job body did not.
        """
        # Local import avoids a top-level cycle (workers loads at module
        # import time; app.core.actor_context is a tiny leaf module — safe
        # either way, mirrors the audit.py defensive local-import pattern).
        from app.core.actor_context import actor_context_var

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            job_id=str(ctx["job_id"]),
            job_name=ctx["function_name"],
        )
        # Phase 41 D-41-08 — own the job-scoped contextvar envelope.
        ctx["_actor_token"] = actor_context_var.set(None)

    @staticmethod
    async def on_job_end(ctx: dict[str, Any]) -> None:
        """Clear contextvars + reset actor_context_var (no leak across runs)."""
        # Phase 41 D-41-08 — reset the actor envelope set in on_job_start.
        from app.core.actor_context import actor_context_var

        token = ctx.pop("_actor_token", None)
        if token is not None:
            actor_context_var.reset(token)
        structlog.contextvars.clear_contextvars()
