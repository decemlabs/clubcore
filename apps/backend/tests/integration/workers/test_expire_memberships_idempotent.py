"""ARQ-TEST-02 — idempotency test (Phase 18 ROADMAP SC #2 / Pitfall 4).

Two consecutive calls to `expire_memberships(ctx)` MUST produce exactly the
same DB end state as one call. The SQL-level gate `WHERE status='active'`
is the real defence — the second call's UPDATE matches zero rows because
the first call already flipped them to 'expired'. ARQ `unique=True` is
necessary-not-sufficient (Pitfall 4 — `unique=True` deduplicates within a
Redis namespace but does not protect against worker-restart re-runs).

Asserts the second call:
  - Returns 0 (zero newly-expired rows on the second tick).
  - Inserts 0 NEW audit rows (total `membership_expired` rows stays at 1).
  - Emits a summary log line with `count=0` (CD-03 — operator sees a clean
    line on no-op days, proving the cron ran and the connection worked).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.workers.scheduled.expire_memberships import expire_memberships


async def test_expire_memberships_idempotent(
    db_session: AsyncSession,
    make_membership_with_dates: Any,
    worker_ctx: dict[str, Any],
) -> None:
    today = datetime.now(tz=UTC).date()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    await make_membership_with_dates(end_date=yesterday)
    await make_membership_with_dates(end_date=today)
    await make_membership_with_dates(end_date=tomorrow)

    # First call — flips the yesterday row.
    with structlog.testing.capture_logs() as first_capture:
        first_count = await expire_memberships(worker_ctx)
    assert first_count == 1

    first_summary = [e for e in first_capture if e.get("event") == "expire_memberships_complete"]
    assert len(first_summary) == 1
    assert first_summary[0].get("count") == 1

    # Audit log after first call — exactly 1 row.
    audit_count_after_first = await db_session.scalar(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "membership_expired")
    )
    assert audit_count_after_first == 1

    # Second call — idempotent no-op. count=0, no new audit rows.
    with structlog.testing.capture_logs() as second_capture:
        second_count = await expire_memberships(worker_ctx)
    assert second_count == 0, (
        f"second call must return 0 (SQL idempotency gate); got {second_count}"
    )

    second_summary = [e for e in second_capture if e.get("event") == "expire_memberships_complete"]
    assert len(second_summary) == 1, (
        "summary log emitted on every tick (proves cron ran), even on no-op runs"
    )
    assert second_summary[0].get("count") == 0

    # Audit log after second call — STILL exactly 1 row (no duplicate).
    audit_count_after_second = await db_session.scalar(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "membership_expired")
    )
    assert audit_count_after_second == 1, (
        f"second call must NOT insert duplicate audit row; "
        f"first run had {audit_count_after_first} rows, "
        f"second run shows {audit_count_after_second} rows"
    )
