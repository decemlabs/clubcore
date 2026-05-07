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
  - `on_job_end(ctx)` clears contextvars (prevents leak across runs in
    the same asyncio task — Pitfall 14 mitigation step 3).
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
from app.workers.scheduled.expire_memberships import expire_memberships

_log = structlog.get_logger("workers")


class WorkerSettings:
    """ARQ WorkerSettings — entrypoint resolved by `arq app.workers.WorkerSettings`.

    Class attributes only — ARQ reads them via class introspection, never
    instantiates this class. `ClassVar[...]` annotations satisfy mypy strict
    mode against ARQ's untyped-attribute introspection.
    """

    redis_settings = RedisSettings.from_dsn(str(get_settings().redis_url))

    functions: ClassVar[list[Any]] = [expire_memberships]

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
        _log.info("worker_startup_complete", function_count=len(function_names))

    @staticmethod
    async def on_shutdown(ctx: dict[str, Any]) -> None:
        """Close the AsyncExitStack stored in ctx — disposes engine + sessionmaker."""
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
        """
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            job_id=str(ctx["job_id"]),
            job_name=ctx["function_name"],
        )

    @staticmethod
    async def on_job_end(ctx: dict[str, Any]) -> None:
        """Clear contextvars (prevents leak across runs in the same asyncio task)."""
        structlog.contextvars.clear_contextvars()
