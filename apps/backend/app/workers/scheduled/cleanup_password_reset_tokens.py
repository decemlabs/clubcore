"""ARQ scheduled job: cleanup expired password_reset_tokens (D-44-31 / D-41-06).

Daily at 03:30 Europe/Moscow (= 00:30 UTC, container TZ=UTC — see
``app/workers/__init__.py`` cron precedent for the offset rationale).
30-day retention per D-44-32: rows where
``expires_at < NOW() - INTERVAL '30 days'`` are DELETEd. The 30-day window
is generous enough to admit a "did we send a reset for user X 3 weeks ago?"
forensic query (join ``audit_log`` ⇄ ``password_reset_tokens`` on
``audit_correlation_id``) and bounded enough to keep the table trivially
small at the v1.6 one-gym tenant scale.

No audit emit per D-44-31 — housekeeping, not an observable state change.
The Phase 41 D-41-09 ``actor_email_snapshot`` semantics + D-41-10 NULL/NULL
system-actor row would attribute the delete to the cron job, but the
deliberate decision is that pruning beyond the retention boundary is not an
event worth a log row: the original
``password_reset_requested`` / ``password_reset_used`` / ``user_invited``
emits already chronicle the token's intent and consumption inside the
retention window. Anything beyond it is operational noise.

Transaction ownership (Phase 27 D-27-07 pattern b — multi-session):
opens its own session via ``ctx["sessionmaker"]``. The DELETE + commit is
a single round-trip with no other I/O in the body, so a single session
suffices (no per-row Telegram-style fan-out here).

Observability (Phase 18 CD-03 / Phase 27 locked summary-event convention):
emits one structlog INFO ``cleanup_password_reset_tokens_complete count=N``
AFTER ``session.commit()`` returns. The line is NOT an audit event; it is
the standard ``<job_name>_complete count=N`` ops-summary shape. ``job_id``
and ``job_name`` are already on the structlog contextvars stack courtesy
of ``WorkerSettings.on_job_start``.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import structlog
from sqlalchemy import delete, func

from app.modules.auth.password_reset_token_model import PasswordResetToken

_log = structlog.get_logger("workers.scheduled.cleanup_password_reset_tokens")

_RETENTION = timedelta(days=30)


async def cleanup_password_reset_tokens(ctx: dict[str, Any]) -> int:
    """Delete password_reset_tokens rows older than the 30-day retention window.

    Args:
        ctx: ARQ job context dict. Required keys:
            - ctx["sessionmaker"]: ``async_sessionmaker[AsyncSession]``
              populated by ``WorkerSettings.on_startup`` from
              ``core.database.db_lifespan_manager()``.
            - ctx["job_id"], ctx["function_name"]: bound on structlog
              contextvars by ``on_job_start``; flow into the summary log
              line via ``merge_contextvars``.

    Returns:
        int — number of rows DELETEd on this run. ARQ writes this value
        into its result store automatically.
    """
    session_factory = ctx["sessionmaker"]
    async with session_factory() as session:
        stmt = delete(PasswordResetToken).where(
            PasswordResetToken.expires_at < func.now() - _RETENTION
        )
        result = await session.execute(stmt)
        await session.commit()
        deleted_count: int = result.rowcount or 0

    # Summary log AFTER commit returns successfully (Phase 18 CD-03).
    # NOT an audit event — housekeeping per D-44-31.
    _log.info("cleanup_password_reset_tokens_complete", count=deleted_count)
    return deleted_count
