"""Phase 25 Plan 02 — Postgres-backed sanity for compute_freeze_days_used.

Catches SQL-level errors (syntax, cast, named-bind) at the Plan 02 boundary,
BEFORE Plan 05 integration tests run. Closes revision-iteration-1
verification_derivation gap: hand-written text() SQL with EXTRACT(EPOCH FROM ...)
+ named-parameter binding wouldn't surface until Wave 5 otherwise.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.memberships import repository
from app.modules.memberships.models import MembershipFreezePeriod


@pytest.mark.asyncio
async def test_compute_freeze_days_used_zero_rows_returns_zero(
    db_session: AsyncSession,
    make_plan: Any,
    make_client: Any,
    make_membership: Any,
) -> None:
    """No freeze periods exist → returns 0 (COALESCE(SUM(...), 0) safe path)."""
    plan = await make_plan(name="Freeze zero")
    client = await make_client(phone="+79991239001")
    membership = await make_membership(client_id=client.id, plan=plan, status="active")

    days = await repository.compute_freeze_days_used(
        db_session, membership.id, today_msk=date(2026, 5, 8)
    )
    assert days == 0


@pytest.mark.asyncio
async def test_compute_freeze_days_used_one_closed_period_ceil_rounds_up(
    db_session: AsyncSession,
    make_user: Any,
    make_plan: Any,
    make_client: Any,
    make_membership: Any,
) -> None:
    """Closed period of ~1.5 days → ceil(1.5 * 86400 / 86400) == 2."""
    actor = await make_user(role="reception", email="freeze-actor@example.com")
    plan = await make_plan(name="Freeze ceil")
    client = await make_client(phone="+79991239002")
    membership = await make_membership(client_id=client.id, plan=plan, status="active")

    started = datetime.now(tz=UTC) - timedelta(days=2)
    ended = started + timedelta(days=1, hours=12)  # 1.5 days
    period = MembershipFreezePeriod(
        membership_id=membership.id,
        started_by=actor.id,
        started_at=started,
        ended_at=ended,
        ended_by=actor.id,
    )
    db_session.add(period)
    await db_session.flush()

    days = await repository.compute_freeze_days_used(
        db_session, membership.id, today_msk=date(2026, 5, 8)
    )
    assert days == 2  # ceil(1.5) == 2; matches Python math.ceil semantics
