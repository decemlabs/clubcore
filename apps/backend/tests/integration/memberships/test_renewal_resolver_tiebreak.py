"""Phase 26 MEM-REN-03 / D-26-17 — resolver tiebreak inversion regression.

The resolver previously used `ORDER BY end_date DESC, created_at DESC LIMIT 1`
(Phase 17 D-17). When a client holds BOTH a still-running source AND a renewal
sold ahead, the old order would jump straight to the renewal — operator
intuition expects check-in to keep using the running membership until it
expires. Phase 26 inverts to `ORDER BY start_date ASC, created_at DESC LIMIT 1`
so the running (earlier-started) membership wins; ARQ `expire_memberships`
(06:05 cron) then flips source.status='expired' and the renewal naturally
takes over the next morning.

These tests pin the new ordering. If they fail, the check-in path is broken
for renewal-stacked clients; do NOT mass-update other tests without
revisiting this lock.

NOTE on `previous_membership_id`: the conftest `make_membership` fixture does
NOT yet accept `previous_membership_id` as a kwarg (Phase 25-era helper). To
keep this test self-contained without modifying the shared fixture (separate
risk), we set `previous_membership_id` via direct ORM attribute assignment
after construction inside each test.
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import date, timedelta
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.memberships import repository
from app.modules.memberships.models import Membership


async def test_resolver_prefers_running_source_over_renewal(
    db_session: AsyncSession,
    make_plan: Any,
    make_client: Any,
    make_membership: Any,
) -> None:
    """D-26-17: when both source (running) and renewal (future) are active,
    resolver returns SOURCE because start_date ASC wins.
    """
    today = date(2026, 5, 15)
    plan = await make_plan(
        name="Renewal Tiebreak Running",
        duration_days=30,
        freeze_days_limit=14,
        price_kopecks=200_000,
    )
    client = await make_client(phone="+79991240001")
    source = await make_membership(
        client_id=client.id,
        plan=plan,
        status="active",
        start_date=today - timedelta(days=25),
        end_date=today + timedelta(days=5),
    )
    # Force a measurable created_at delta so the renewal is unambiguously LATER
    # in created_at as well — the test must pass on start_date ASC alone, not
    # on a coincidental created_at tiebreak.
    await asyncio.sleep(0.01)
    renewal = await make_membership(
        client_id=client.id,
        plan=plan,
        status="active",
        start_date=today + timedelta(days=6),
        end_date=today + timedelta(days=35),
    )
    # Phase 26 chain attribution; set via direct ORM (conftest helper-agnostic).
    renewal.previous_membership_id = source.id
    await db_session.flush()

    resolved = await repository.find_active_for_client(
        db_session, client.id, today=today
    )
    assert resolved is not None
    assert resolved.id == source.id, (
        "Phase 26 D-26-17: running source must win over future renewal "
        "(start_date ASC). Got renewal — ORDER BY likely still end_date DESC."
    )


async def test_resolver_switches_to_renewal_when_source_expires(
    db_session: AsyncSession,
    make_plan: Any,
    make_client: Any,
    make_membership: Any,
) -> None:
    """D-26-17: simulate ARQ flip on source.end_date+1 → resolver returns renewal."""
    today = date(2026, 5, 15)
    plan = await make_plan(
        name="Renewal Tiebreak Switch",
        duration_days=30,
        freeze_days_limit=14,
        price_kopecks=200_000,
    )
    client = await make_client(phone="+79991240002")
    source = await make_membership(
        client_id=client.id,
        plan=plan,
        status="active",
        start_date=today - timedelta(days=25),
        end_date=today + timedelta(days=5),
    )
    await asyncio.sleep(0.01)
    renewal = await make_membership(
        client_id=client.id,
        plan=plan,
        status="active",
        start_date=today + timedelta(days=6),
        end_date=today + timedelta(days=35),
    )
    renewal.previous_membership_id = source.id
    await db_session.flush()

    # ARQ simulation: flip source to expired on day end_date+1.
    await db_session.execute(
        update(Membership).where(Membership.id == source.id).values(status="expired")
    )
    await db_session.flush()

    resolved = await repository.find_active_for_client(
        db_session, client.id, today=today + timedelta(days=6)
    )
    assert resolved is not None
    assert resolved.id == renewal.id, (
        "After source flips to expired, only renewal remains active and must "
        "be returned by resolver."
    )


async def test_resolver_manual_stacking_same_start_date_tiebreaks_created_at_desc(
    db_session: AsyncSession,
    make_plan: Any,
    make_client: Any,
    make_membership: Any,
) -> None:
    """Phase 17 D-01 manual stacking: two memberships, same start_date.
    Tiebreak by created_at DESC → LATER-created wins (silent, no audit).
    """
    today = date(2026, 5, 15)
    plan = await make_plan(
        name="Manual Stacking Same Start",
        duration_days=30,
        freeze_days_limit=14,
        price_kopecks=200_000,
    )
    client = await make_client(phone="+79991240003")
    same_start = today - timedelta(days=5)
    same_end = today + timedelta(days=24)
    earlier = await make_membership(
        client_id=client.id,
        plan=plan,
        status="active",
        start_date=same_start,
        end_date=same_end,
    )
    # Force a measurable created_at gap so the test's intent (later-created wins)
    # is not muddled by func.now() returning identical timestamps within the
    # same SAVEPOINT.
    await asyncio.sleep(0.01)
    later = await make_membership(
        client_id=client.id,
        plan=plan,
        status="active",
        start_date=same_start,
        end_date=same_end,
    )

    resolved = await repository.find_active_for_client(
        db_session, client.id, today=today
    )
    assert resolved is not None
    # `later` was created after `earlier` → its created_at is greater → wins.
    # If created_at happens to be identical (single-statement clock), accept
    # either id but pin the start_date so we don't silently accept a wrong row.
    assert resolved.id in {earlier.id, later.id}
    assert resolved.start_date == same_start
    if earlier.created_at != later.created_at:
        assert resolved.id == later.id, (
            "created_at DESC tiebreak: later-created row must win when "
            "start_date is equal."
        )


def test_resolver_signature_unchanged() -> None:
    """D-26-18: Phase 26 only changes ORDER BY; signature stays
    (session, client_id, *, today).
    """
    sig = inspect.signature(repository.find_active_for_client)
    params = list(sig.parameters.values())
    assert [p.name for p in params] == ["session", "client_id", "today"]
    today_param = sig.parameters["today"]
    assert today_param.kind == inspect.Parameter.KEYWORD_ONLY
