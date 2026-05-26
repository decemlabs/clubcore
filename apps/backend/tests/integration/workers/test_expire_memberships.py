"""ARQ-TEST-01 — happy-path bulk-expire test (Phase 18 ARQ-02 / ROADMAP SC #1).

3-row fixture: today-1 (yesterday — overdue), today (inclusive end_date — NOT
overdue), today+1 (future — not overdue). One call to `expire_memberships(ctx)`
must flip exactly the today-1 row, emit exactly one `membership_expired` audit
row, leave the today + today+1 rows untouched, and emit exactly one
`expire_memberships_complete count=1` structlog INFO line.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.workers.scheduled.expire_memberships import expire_memberships


async def test_expire_memberships_flips_only_overdue_active_rows(
    db_session: AsyncSession,
    make_membership_with_dates: Any,
    worker_ctx: dict[str, Any],
) -> None:
    today = datetime.now(tz=UTC).date()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    overdue = await make_membership_with_dates(end_date=yesterday)
    inclusive_today = await make_membership_with_dates(end_date=today)
    future = await make_membership_with_dates(end_date=tomorrow)

    with structlog.testing.capture_logs() as captured:
        count = await expire_memberships(worker_ctx)

    assert count == 1, f"expected 1 newly-expired row, got {count}"

    # Audit row check — exactly 1 membership_expired with the overdue row's id.
    audit_rows = (
        (await db_session.execute(select(AuditLog).where(AuditLog.action == "membership_expired")))
        .scalars()
        .all()
    )
    assert len(audit_rows) == 1, (
        f"expected exactly 1 membership_expired audit row, got {len(audit_rows)}"
    )
    audit = audit_rows[0]
    assert audit.resource_type == "membership"
    assert audit.resource_id == overdue.id
    assert audit.actor_user_id is None
    assert audit.payload == {"client_id": str(overdue.client_id)}, audit.payload

    # Status check — overdue flipped, today + tomorrow untouched (inclusive end_date).
    await db_session.refresh(overdue)
    await db_session.refresh(inclusive_today)
    await db_session.refresh(future)
    assert overdue.status == "expired"
    assert inclusive_today.status == "active", (
        "today's row stays active until tomorrow's tick (inclusive end_date)"
    )
    assert future.status == "active"

    # Summary log check — exactly 1 expire_memberships_complete with count=1.
    completion_events = [e for e in captured if e.get("event") == "expire_memberships_complete"]
    assert len(completion_events) == 1, (
        f"expected 1 expire_memberships_complete log line, got {len(completion_events)}"
    )
    assert completion_events[0].get("count") == 1, completion_events[0]
