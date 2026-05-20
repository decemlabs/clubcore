"""One-shot in-process invocation of `send_booking_reminders` against the live stack.

Used during Phase 40+ milestone verification to fire the 06:35 MSK cron once
without waiting wall-clock. Bypasses ARQ scheduling entirely — the cron
function is a plain `async def` callable that accepts a `ctx` dict, so we
build that ctx via `WorkerSettings.on_startup` and `await` once.

NOT a production tool. NEVER invoked by CI or the compose stack. One-shot
operator command:

    cd apps/backend && uv run python -m scripts.run_booking_reminders_once

Safety gates (refuses to fire unless ALL are true):
  - DATABASE_URL contains 'localhost' or 'postgres:5432' (TM-29-02 mirror).
  - TELEGRAM_SANDBOX_CHAT_ID is set in env (TM-29-03 mirror — the reminder
    cron DOES dispatch real Telegram DMs, so the operator MUST point all
    candidate clients' ``telegram_user_id`` columns at the sandbox chat
    before firing this script).

D-39-17 distinction from ``scripts/run_no_show_cron_once.py``: the no-show
runner OMITS TM-29-03 because the no-show cron is DB-only. THIS runner
KEEPS TM-29-03 because the reminder cron dispatches DMs. See the no-show
runner's module docstring for the omission rationale.

REG-29-04 (Phase 39 plan 39-04): SQLAlchemy resolves FK references lazily
at first flush. The cron callable reads bookings + clients +
trainer_availability_slots + trainers via the SELECT JOIN, then inserts
``booking_notifications`` rows on success. Eager-import the 5 models
touched by the helper so all tables are registered before the session
opens.

On success, prints exactly: `Fired send_booking_reminders once: count=<N>`
where <N> is the integer returned by the callable.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

from arq import create_pool

from app.core.config import get_settings

# REG-29-04 eager-imports — see module docstring rationale.
from app.modules.auth import models as _auth_models  # noqa: F401 — eager FK reg
from app.modules.bookings import models as _bookings_models  # noqa: F401 — eager FK reg
from app.modules.clients import models as _client_models  # noqa: F401 — eager FK reg
from app.modules.schedule import models as _schedule_models  # noqa: F401 — eager FK reg
from app.modules.trainers import models as _trainers_models  # noqa: F401 — eager FK reg
from app.workers import WorkerSettings
from app.workers.scheduled.send_booking_reminders import send_booking_reminders


async def _run() -> int:
    # TM-29-02: refuse to run against a non-local DATABASE_URL.
    db_url = str(get_settings().database_url)
    if "localhost" not in db_url and "postgres:5432" not in db_url:
        print(
            "ERROR: run_booking_reminders_once refuses to run against a non-local "
            "DATABASE_URL (TM-29-02).",
            file=sys.stderr,
        )
        return 1

    # TM-29-03: env-presence guard. Necessary-but-not-sufficient — the
    # operator MUST also redirect every candidate client's
    # ``telegram_user_id`` to the sandbox chat before firing the script
    # (see scripts/run_expiring_cron_once.py module docstring for the
    # load-bearing operator-managed data-layer redirect discussion).
    sandbox_chat = os.environ.get("TELEGRAM_SANDBOX_CHAT_ID")
    if not sandbox_chat:
        print(
            "ERROR: TELEGRAM_SANDBOX_CHAT_ID must be set; refusing to fire cron "
            "(TM-29-03).",
            file=sys.stderr,
        )
        return 1

    # Phase 42 wired `register_arq_pool(ctx["redis"])` into
    # WorkerSettings.on_startup so the email dispatcher can enqueue jobs.
    # The ARQ runtime normally pre-populates ctx["redis"] from the worker
    # pool; this one-shot script must supply an equivalent ArqRedis pool
    # manually before invoking on_startup.
    redis_pool = await create_pool(WorkerSettings.redis_settings)
    ctx: dict[str, Any] = {"redis": redis_pool}
    # Reuse the locked WorkerSettings startup logic — populates
    # ctx["sessionmaker"] and runs the cron-resolution invariant assertion.
    # DO NOT re-implement the DB lifespan inline (MH-29-05 mirror): call
    # the staticmethod, never the helper.
    await WorkerSettings.on_startup(ctx)
    try:
        count = await send_booking_reminders(ctx)
        print(f"Fired send_booking_reminders once: count={count}")
    finally:
        await WorkerSettings.on_shutdown(ctx)
        await redis_pool.aclose()
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
