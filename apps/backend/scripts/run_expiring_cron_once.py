"""One-shot in-process invocation of `send_expiring_notifications` against the live stack.

Used during Phase 29 milestone verification to fire the 06:15 MSK cron once
without waiting wall-clock. Bypasses ARQ scheduling entirely — the cron
function is a plain `async def` callable that accepts a `ctx` dict, so we
build that ctx via `WorkerSettings.on_startup` and `await` once.

NOT a production tool. NEVER invoked by CI or the compose stack. One-shot
operator command:

    cd apps/backend && uv run python -m scripts.run_expiring_cron_once

Safety gates (refuses to fire unless ALL are true):
  - DATABASE_URL contains 'localhost' or 'postgres:5432' (TM-29-02).
  - TELEGRAM_SANDBOX_CHAT_ID is set in env (TM-29-03 — env-presence check
    only; this script CANNOT inspect each candidate client's
    `telegram_user_id` because that requires running the same SELECT the
    cron itself runs. The env-set guard is therefore necessary-but-not-
    sufficient.

    Load-bearing mitigation for TM-29-03: the OPERATOR is required to
    manually `UPDATE clients SET telegram_user_id = $TELEGRAM_SANDBOX_CHAT_ID`
    for every client whose membership will trigger a DM during the
    upcoming firing (recorded as Plan 29-04 step 6 / Plan 29-03 fixture
    seeding). Without that manual UPDATE, DMs may be dispatched to
    whatever `telegram_user_id` is already in the row — which for the
    seeded `verify_*@fixture.local` clients is a deterministic
    70000000xx integer that is NOT a real Telegram chat (so the bot's
    send will fail at the Telegram API boundary). The operator MUST
    verify in 29-03 / 29-04 that the only clients with a real
    `telegram_user_id` are those they personally control via the
    sandbox).

On success, prints exactly: `Fired send_expiring_notifications once: count=<N>`
where <N> is the integer returned by the callable.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

from app.core.config import get_settings

# REG-29-04 (Phase 29 wave 3): SQLAlchemy resolves FK references lazily at
# first flush. The cron callable inserts audit_log rows that FK into users
# and clients, but neither models module is imported transitively from
# send_expiring_notifications, so the FK target tables are unknown to
# Base.metadata when the runner triggers commit. Eager-import the four
# models touched by the cron + audit path so all tables are registered
# before the session opens.
from app.modules.auth import models as _auth_models  # noqa: F401 — eager FK reg
from app.modules.clients import models as _client_models  # noqa: F401 — eager FK reg
from app.modules.memberships import models as _memberships_models  # noqa: F401 — eager FK reg
from app.modules.visits import models as _visits_models  # noqa: F401 — eager FK reg
from app.workers import WorkerSettings
from app.workers.scheduled.send_expiring_notifications import send_expiring_notifications


async def _run() -> int:
    # TM-29-02: refuse to run against a non-local DATABASE_URL.
    db_url = str(get_settings().database_url)
    if "localhost" not in db_url and "postgres:5432" not in db_url:
        print(
            "ERROR: run_expiring_cron_once refuses to run against a non-local "
            "DATABASE_URL (TM-29-02).",
            file=sys.stderr,
        )
        return 1

    # TM-29-03: env-presence guard. Necessary-but-not-sufficient — see module
    # docstring for the load-bearing operator-managed data-layer redirect.
    sandbox_chat = os.environ.get("TELEGRAM_SANDBOX_CHAT_ID")
    if not sandbox_chat:
        print(
            "ERROR: TELEGRAM_SANDBOX_CHAT_ID must be set; refusing to fire cron "
            "(TM-29-03).",
            file=sys.stderr,
        )
        return 1

    ctx: dict[str, Any] = {}
    # Reuse the locked WorkerSettings startup logic — populates ctx["sessionmaker"]
    # and runs the cron-resolution invariant assertion. DO NOT re-implement the
    # DB lifespan inline (MH-29-05): call the staticmethod, never the helper.
    await WorkerSettings.on_startup(ctx)
    try:
        count = await send_expiring_notifications(ctx)
        print(f"Fired send_expiring_notifications once: count={count}")
    finally:
        await WorkerSettings.on_shutdown(ctx)
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
