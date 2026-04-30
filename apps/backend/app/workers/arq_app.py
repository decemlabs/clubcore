"""ARQ worker settings entry point.

Run with `arq app.workers.arq_app.WorkerSettings` (in a future phase, once tasks land).
Phase A: empty `functions` list — defining the WorkerSettings shape now stabilizes
the import path so future tasks plug in without restructuring.
"""

from typing import Any, ClassVar

from arq.connections import RedisSettings

from app.core.config import get_settings


class WorkerSettings:
    """ARQ WorkerSettings skeleton (WORK-01).

    Future: add task functions to `functions`, configure cron jobs via `cron_jobs`,
    add `on_startup` / `on_shutdown` hooks. Phase A keeps it minimal.
    """

    functions: ClassVar[list[Any]] = []
    # TODO Phase B+: register real task functions here, e.g.
    # functions = [tasks.notifications.send_telegram, tasks.reminders.send_visit_reminder]
    redis_settings = RedisSettings.from_dsn(str(get_settings().redis_url))
