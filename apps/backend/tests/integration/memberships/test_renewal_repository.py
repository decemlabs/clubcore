"""Phase 26 Plan 26-03 Task 1 — repository helpers for renewal.

RED-phase coverage for:
  - `repository.get_plan_for_renewal(session, plan_id)` returns:
      * `(None, False)` for non-existent id
      * `(plan, False)` for an alive plan (deleted_at IS NULL)
      * `(plan, True)` for an archived plan (deleted_at IS NOT NULL)
  - `repository.insert_renewal_membership(session, *, source, plan, ...)` returns
    a Membership with snapshots from CURRENT plan (NOT from source.*_snapshot),
    `previous_membership_id == source.id`, status='active', no flush/commit.

These helpers are used by `service.renew_membership` (Task 2) — the discriminator
between hard-delete (404 plan_not_found) and archive (409 plan_archived) lives
exclusively here so the service can stay declarative.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.models import Client
from app.modules.memberships import repository
from app.modules.memberships.models import Membership, MembershipPlan

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# get_plan_for_renewal — D-26-08 discriminator (alive | archived | missing)
# ---------------------------------------------------------------------------


async def test_get_plan_for_renewal_returns_none_for_missing_id(
    db_session: AsyncSession,
) -> None:
    """Non-existent plan id returns (None, False) — service raises 404."""
    plan, is_archived = await repository.get_plan_for_renewal(db_session, uuid4())
    assert plan is None
    assert is_archived is False


async def test_get_plan_for_renewal_returns_plan_false_for_alive_plan(
    db_session: AsyncSession,
    make_plan: Callable[..., Awaitable[MembershipPlan]],
) -> None:
    """Alive plan (deleted_at IS NULL) returns (plan, False)."""
    plan = await make_plan(name="Alive renewal plan")
    loaded, is_archived = await repository.get_plan_for_renewal(db_session, plan.id)
    assert loaded is not None
    assert loaded.id == plan.id
    assert is_archived is False


async def test_get_plan_for_renewal_returns_plan_true_for_archived_plan(
    db_session: AsyncSession,
    make_plan: Callable[..., Awaitable[MembershipPlan]],
) -> None:
    """Archived plan (deleted_at IS NOT NULL) returns (plan, True) — service raises 409."""
    plan = await make_plan(name="Archived renewal plan")
    plan.deleted_at = datetime.now(tz=UTC)
    await db_session.commit()
    await db_session.refresh(plan)

    loaded, is_archived = await repository.get_plan_for_renewal(db_session, plan.id)
    assert loaded is not None
    assert loaded.id == plan.id
    assert is_archived is True


# ---------------------------------------------------------------------------
# insert_renewal_membership — D-26-16 (snapshots from CURRENT plan; no commit)
# ---------------------------------------------------------------------------


async def test_insert_renewal_membership_snapshots_from_current_plan(
    db_session: AsyncSession,
    make_plan: Callable[..., Awaitable[MembershipPlan]],
    make_client: Callable[..., Awaitable[Client]],
    make_membership: Callable[..., Awaitable[Membership]],
) -> None:
    """Snapshots come from CURRENT plan fields, NOT from source's snapshots.

    The "if plan got more expensive between sale and renewal, client pays new
    price" lock from PROJECT.md depends on this — the source row's snapshots
    are stale and MUST be ignored.
    """
    plan = await make_plan(
        name="Original plan",
        duration_days=30,
        price_kopecks=200_000,
        freeze_days_limit=14,
    )
    client = await make_client()
    source = await make_membership(client_id=client.id, plan=plan)

    # Mutate plan AFTER source is created — simulates owner PATCH between sale and renewal.
    plan.name = "Updated plan name"
    plan.duration_days = 60
    plan.price_kopecks = 300_000
    plan.freeze_days_limit = 21
    await db_session.commit()
    await db_session.refresh(plan)

    start_date = source.end_date + timedelta(days=1)
    end_date = start_date + timedelta(days=plan.duration_days - 1)

    new_membership = await repository.insert_renewal_membership(
        db_session,
        source=source,
        plan=plan,
        start_date=start_date,
        end_date=end_date,
    )
    await db_session.flush()

    # Snapshots from CURRENT plan
    assert new_membership.plan_name_snapshot == "Updated plan name"
    assert new_membership.duration_days_snapshot == 60
    assert new_membership.price_kopecks_snapshot == 300_000
    assert new_membership.freeze_days_limit_snapshot == 21

    # Source snapshots remain unchanged (sanity)
    assert source.plan_name_snapshot == "Original plan"
    assert source.price_kopecks_snapshot == 200_000

    # Chain attribution + identity
    assert new_membership.client_id == source.client_id
    assert new_membership.plan_id == plan.id
    assert new_membership.previous_membership_id == source.id
    assert new_membership.status == "active"
    assert new_membership.start_date == start_date
    assert new_membership.end_date == end_date


async def test_insert_renewal_membership_does_not_flush_or_commit(
    db_session: AsyncSession,
    make_plan: Callable[..., Awaitable[MembershipPlan]],
    make_client: Callable[..., Awaitable[Client]],
    make_membership: Callable[..., Awaitable[Membership]],
) -> None:
    """Caller-owns-txn invariant — helper never flushes/commits.

    We assert the row has no id assigned BEFORE the test calls flush itself —
    SQLAlchemy assigns server-default ids at flush time. If the helper
    accidentally flushed, the id would already be populated.
    """
    plan = await make_plan(name="No-flush plan")
    client = await make_client()
    source = await make_membership(client_id=client.id, plan=plan)

    today = date.today()
    new_membership = await repository.insert_renewal_membership(
        db_session,
        source=source,
        plan=plan,
        start_date=today + timedelta(days=1),
        end_date=today + timedelta(days=plan.duration_days),
    )

    # No flush/commit issued by helper — id is server-default UUID and may be
    # populated client-side by SQLAlchemy. The robust assertion: the row is
    # in the session's pending set (new), not yet persistent.
    assert new_membership in db_session.new
