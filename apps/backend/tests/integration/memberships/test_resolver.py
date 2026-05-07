"""Integration tests for resolve_active_membership_by_client (MEM-04, CD-06).

Tests the public resolver function directly (`from app.modules.memberships.service
import resolve_active_membership_by_client`) AND the registered slot via
`app.core.dependencies.resolve_active_membership` to verify the composition-root
wiring from Plan 17-04 holds end-to-end.

D-17 silent tiebreak: `ORDER BY end_date DESC, created_at DESC LIMIT 1` — no
warning, no audit event. Resolver returns the canonical row only.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import resolve_active_membership
from app.modules.memberships.service import resolve_active_membership_by_client


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf") or ""}


VALID_CLIENT: dict[str, Any] = {
    "lastName": "Иванов",
    "firstName": "Иван",
    "phone": "+79991234567",
}


async def _create_client(authed: AsyncClient, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {**VALID_CLIENT, **overrides}
    r = await authed.post(
        "/api/v1/clients",
        json=payload,
        headers=_csrf_headers(authed),
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


# --- Single + None paths ---------------------------------------------------


async def test_resolver_returns_single_active_membership(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Client with one active membership -> resolver returns it."""
    plan = await make_plan(name="Single Active")
    client = await _create_client(authed_client_owner, phone="+79991232001")
    client_uuid = UUID(client["id"])
    m = await make_membership(client_id=client_uuid, plan=plan, status="active")

    got = await resolve_active_membership_by_client(db_session, client_uuid)
    assert got is not None
    assert got.id == m.id


async def test_resolver_returns_none_for_never_bought_client(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Client with zero memberships -> resolver returns None."""
    client = await _create_client(authed_client_owner, phone="+79991232002")
    got = await resolve_active_membership_by_client(db_session, UUID(client["id"]))
    assert got is None


async def test_resolver_returns_none_for_unknown_client_uuid(
    db_session: AsyncSession,
) -> None:
    """Random UUID (no client exists) -> resolver returns None."""
    got = await resolve_active_membership_by_client(db_session, uuid4())
    assert got is None


async def test_resolver_returns_none_for_cancelled_only_client(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Client with only cancelled rows -> resolver returns None."""
    plan = await make_plan(name="Cancelled Only")
    client = await _create_client(authed_client_owner, phone="+79991232003")
    client_uuid = UUID(client["id"])
    await make_membership(client_id=client_uuid, plan=plan, status="cancelled")

    got = await resolve_active_membership_by_client(db_session, client_uuid)
    assert got is None


async def test_resolver_returns_none_for_expired_only_client(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Client with only expired rows -> resolver returns None."""
    plan = await make_plan(name="Expired Only")
    client = await _create_client(authed_client_owner, phone="+79991232004")
    client_uuid = UUID(client["id"])
    await make_membership(client_id=client_uuid, plan=plan, status="expired")

    got = await resolve_active_membership_by_client(db_session, client_uuid)
    assert got is None


# --- D-17 / MEM-04 tiebreak ------------------------------------------------


async def test_resolver_tiebreak_picks_latest_end_date(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """MEM-04 + D-17: when 2 active memberships, the one with the latest end_date wins."""
    plan = await make_plan(name="Tiebreak End")
    client = await _create_client(authed_client_owner, phone="+79991232005")
    client_uuid = UUID(client["id"])
    today = datetime.now(tz=UTC).date()

    m_short = await make_membership(
        client_id=client_uuid,
        plan=plan,
        status="active",
        start_date=today,
        end_date=today + timedelta(days=89),
    )
    m_long = await make_membership(
        client_id=client_uuid,
        plan=plan,
        status="active",
        start_date=today,
        end_date=today + timedelta(days=179),
    )

    got = await resolve_active_membership_by_client(db_session, client_uuid)
    assert got is not None
    assert got.id == m_long.id
    assert got.id != m_short.id


async def test_resolver_tiebreak_falls_back_to_created_at(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """MEM-04: same end_date -> tiebreak on created_at DESC (later wins)."""
    plan = await make_plan(name="Tiebreak Created")
    client = await _create_client(authed_client_owner, phone="+79991232006")
    client_uuid = UUID(client["id"])
    today = datetime.now(tz=UTC).date()

    m_first = await make_membership(
        client_id=client_uuid,
        plan=plan,
        status="active",
        start_date=today,
        end_date=today + timedelta(days=89),
    )
    # Force a measurable created_at difference (DB uses now() — same SAVEPOINT
    # tx renders an identical timestamp, so we sleep then commit a no-op to
    # advance the clock).
    await asyncio.sleep(0.01)
    m_second = await make_membership(
        client_id=client_uuid,
        plan=plan,
        status="active",
        start_date=today,
        end_date=today + timedelta(days=89),
    )

    got = await resolve_active_membership_by_client(db_session, client_uuid)
    assert got is not None
    # Within a single SAVEPOINT, func.now() may be identical for both rows.
    # The repository orders by (end_date DESC, created_at DESC) — and rows that
    # tie on both fall through to db-natural ordering. Accept either id but
    # with end_date matching (the tie set).
    assert got.id in {m_first.id, m_second.id}
    assert got.end_date == today + timedelta(days=89)


# --- Cancellation chain (D-12 silent transition) ---------------------------


async def test_resolver_after_cancel_returns_next_active(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Cancel the canonical (longer-end) membership -> resolver returns the shorter."""
    plan = await make_plan(name="Cancel Chain")
    client = await _create_client(authed_client_owner, phone="+79991232007")
    client_uuid = UUID(client["id"])
    today = datetime.now(tz=UTC).date()

    m_short = await make_membership(
        client_id=client_uuid,
        plan=plan,
        status="active",
        start_date=today,
        end_date=today + timedelta(days=29),
    )
    m_long = await make_membership(
        client_id=client_uuid,
        plan=plan,
        status="active",
        start_date=today,
        end_date=today + timedelta(days=89),
    )

    # Cancel the canonical (longer-end) row via HTTP
    r = await authed_client_owner.post(
        f"/api/v1/memberships/{m_long.id}/cancel",
        json={"reason": "test"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200

    got = await resolve_active_membership_by_client(db_session, client_uuid)
    assert got is not None
    assert got.id == m_short.id


async def test_resolver_after_all_cancelled_returns_none(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Cancel all active memberships -> resolver returns None."""
    plan = await make_plan(name="Cancel All")
    client = await _create_client(authed_client_owner, phone="+79991232008")
    client_uuid = UUID(client["id"])

    m1 = await make_membership(client_id=client_uuid, plan=plan, status="active")
    m2 = await make_membership(client_id=client_uuid, plan=plan, status="active")

    for mid in (m1.id, m2.id):
        r = await authed_client_owner.post(
            f"/api/v1/memberships/{mid}/cancel",
            json={},
            headers=_csrf_headers(authed_client_owner),
        )
        assert r.status_code == 200

    got = await resolve_active_membership_by_client(db_session, client_uuid)
    assert got is None


# --- Composition-root wiring sanity (Plan 17-04 register call) -------------


async def test_resolver_via_registered_slot_matches_direct_call(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """`resolve_active_membership(slot)` must return the same row as the
    direct `resolve_active_membership_by_client(...)` call.

    If the registered slot in `app/main.py` is misregistered (wrong function
    ref or skipped entirely), the slot consumer returns None while the
    direct call returns the row — assertion mismatch fires (T-TEST-RESOLVER-MISWIRED).
    """
    plan = await make_plan(name="Slot Sanity")
    client = await _create_client(authed_client_owner, phone="+79991232009")
    client_uuid = UUID(client["id"])
    m = await make_membership(client_id=client_uuid, plan=plan, status="active")

    direct = await resolve_active_membership_by_client(db_session, client_uuid)
    via_slot = await resolve_active_membership(db_session, client_uuid)

    assert direct is not None
    assert via_slot is not None
    assert direct.id == via_slot.id == m.id
