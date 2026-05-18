"""One-shot in-process invocation of `mark_no_show_bookings` against the live stack.

Used during Phase 40+ milestone verification to fire the 23:10 MSK cron once
without waiting wall-clock. Bypasses ARQ scheduling entirely — the cron
function is a plain `async def` callable that accepts a `ctx` dict, so we
build that ctx via `WorkerSettings.on_startup` and `await` once.

NOT a production tool. NEVER invoked by CI or the compose stack. One-shot
operator command:

    cd apps/backend && uv run python -m scripts.run_no_show_cron_once

Safety gate (refuses to fire unless this is true):
  - DATABASE_URL contains 'localhost' or 'postgres:5432' (TM-29-02 mirror).

Note: TM-29-03 (TELEGRAM_SANDBOX_CHAT_ID) is intentionally OMITTED from this
runner — the no-show cron is DB-only and never invokes Telegram (D-39-17
mirror). This script flips overdue confirmed bookings to no_show + emits an
audit row; there is no DM dispatch, no `app.integrations.telegram` import,
and no risk of sending production traffic to a wrong Telegram chat. The
companion runner `scripts/run_booking_reminders_once.py` (plan 39-04) WILL
need the full TM-29-03 stanza because it dispatches DMs.

On success, prints exactly: `Fired mark_no_show_bookings once: count=<N>`
where <N> is the integer returned by the callable.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from app.core.config import get_settings

# REG-29-04 (Phase 39 plan 39-03): SQLAlchemy resolves FK references lazily
# at first flush. The cron callable inserts audit_log rows that FK into
# users; also reads bookings + trainer_availability_slots + clients +
# trainers via the SELECT JOIN. Eager-import the 5 models touched by the
# helper + audit path so all tables are registered before the session opens.
from app.modules.auth import models as _auth_models  # noqa: F401 — eager FK reg
from app.modules.bookings import models as _bookings_models  # noqa: F401 — eager FK reg
from app.modules.clients import models as _client_models  # noqa: F401 — eager FK reg
from app.modules.schedule import models as _schedule_models  # noqa: F401 — eager FK reg
from app.modules.trainers import models as _trainers_models  # noqa: F401 — eager FK reg
from app.workers import WorkerSettings
from app.workers.scheduled.mark_no_show_bookings import mark_no_show_bookings


async def _run() -> int:
    # TM-29-02: refuse to run against a non-local DATABASE_URL.
    db_url = str(get_settings().database_url)
    if "localhost" not in db_url and "postgres:5432" not in db_url:
        print(
            "ERROR: run_no_show_cron_once refuses to run against a non-local "
            "DATABASE_URL (TM-29-02).",
            file=sys.stderr,
        )
        return 1

    # NOTE: TM-29-03 (TELEGRAM_SANDBOX_CHAT_ID) is intentionally OMITTED —
    # the no-show cron is DB-only and never invokes Telegram (D-39-17
    # mirror). See module docstring for rationale.

    ctx: dict[str, Any] = {}
    # Reuse the locked WorkerSettings startup logic — populates
    # ctx["sessionmaker"] and runs the cron-resolution invariant assertion.
    # DO NOT re-implement the DB lifespan inline (MH-29-05 mirror): call
    # the staticmethod, never the helper.
    await WorkerSettings.on_startup(ctx)
    try:
        count = await mark_no_show_bookings(ctx)
        print(f"Fired mark_no_show_bookings once: count={count}")
    finally:
        await WorkerSettings.on_shutdown(ctx)
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
