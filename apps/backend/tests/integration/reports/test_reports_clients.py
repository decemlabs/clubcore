"""Integration tests for GET /api/v1/reports/clients (Phase 55 CLR-01..04).

Coverage:
  - Owner receives 200 with active/expiring/new client counters (CLR-01..04).
  - Reception receives 403 ((VIEW, REPORTS) ∈ OWNER_ONLY — owner-only; SC#4).
  - Soft-deleted client's active membership is NOT counted in activeCount (CLR-04).
  - Membership ending within `within` days appears in expiringCount (CLR-02).
  - within=0 and within=31 → 422 out-of-range (D-07).
  - newClientsCount reflects created-in-range live clients only (CLR-03).
  - newClientsCount excludes soft-deleted clients (CLR-04).

Wire format: ?fromDate=YYYY-MM-DD&toDate=YYYY-MM-DD&within=N
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# --- helpers -------------------------------------------------------------------


async def _soft_delete_client(db_session: AsyncSession, client_id: Any) -> None:
    """Mark a client as soft-deleted directly via session (avoids HTTP delete flow)."""
    from sqlalchemy import text

    await db_session.execute(
        text("UPDATE clients SET deleted_at = now() WHERE id = :id"),
        {"id": str(client_id)},
    )
    await db_session.commit()


# --- tests --- -----------------------------------------------------------------


async def test_owner_gets_clients_report(
    authed_client_owner: AsyncClient,
) -> None:
    """Owner GET /reports/clients returns 200 with correct shape (CLR-01)."""
    r = await authed_client_owner.get(
        "/api/v1/reports/clients",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31", "within": "7"},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert "activeCount" in body
    assert "expiringCount" in body
    assert "newClientsCount" in body
    assert "withinDays" in body
    assert body["withinDays"] == 7


async def test_reception_forbidden_clients(
    authed_client_reception: AsyncClient,
) -> None:
    """(VIEW, REPORTS) ∈ OWNER_ONLY → reception receives 403 on /reports/clients (SC#4)."""
    r = await authed_client_reception.get(
        "/api/v1/reports/clients",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_active_count_excludes_soft_deleted_client(
    authed_client_owner: AsyncClient,
    make_client: Any,
    make_plan: Any,
    make_membership: Any,
    db_session: AsyncSession,
) -> None:
    """Active membership owned by a soft-deleted client must NOT be in activeCount (CLR-04)."""
    plan = await make_plan(name="SoftDeleteTest")
    live_client = await make_client()
    deleted_client = await make_client()

    await make_membership(client_id=live_client.id, plan=plan, status="active")
    await make_membership(client_id=deleted_client.id, plan=plan, status="active")

    # Count before soft-delete
    r1 = await authed_client_owner.get(
        "/api/v1/reports/clients",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r1.status_code == 200, r1.text
    count_before = r1.json()["data"]["activeCount"]

    # Soft-delete one client
    await _soft_delete_client(db_session, deleted_client.id)

    r2 = await authed_client_owner.get(
        "/api/v1/reports/clients",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r2.status_code == 200, r2.text
    count_after = r2.json()["data"]["activeCount"]

    # After soft-delete, active count should be exactly 1 less
    assert count_after == count_before - 1, (
        f"Expected activeCount {count_before - 1}, got {count_after} "
        "(soft-deleted client's membership should be excluded)"
    )


async def test_expiring_count_within_boundary(
    authed_client_owner: AsyncClient,
    make_client: Any,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Membership ending in 3 days is in expiringCount when within>=3; absent when within<3 (CLR-02)."""
    plan = await make_plan(name="ExpiringTest")
    cli = await make_client()
    today = datetime.now(tz=UTC).date()
    end_in_3_days = today + timedelta(days=3)

    await make_membership(
        client_id=cli.id,
        plan=plan,
        status="active",
        end_date=end_in_3_days,
    )

    # within=3 → should include this membership
    r_within_3 = await authed_client_owner.get(
        "/api/v1/reports/clients",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31", "within": "3"},
    )
    assert r_within_3.status_code == 200, r_within_3.text
    count_within_3 = r_within_3.json()["data"]["expiringCount"]

    # within=2 → membership ending in 3 days should NOT be included
    r_within_2 = await authed_client_owner.get(
        "/api/v1/reports/clients",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31", "within": "2"},
    )
    assert r_within_2.status_code == 200, r_within_2.text
    count_within_2 = r_within_2.json()["data"]["expiringCount"]

    assert count_within_3 > count_within_2, (
        f"Membership expiring in 3 days should appear in within=3 ({count_within_3}) "
        f"but not within=2 ({count_within_2})"
    )


async def test_within_zero_returns_422(
    authed_client_owner: AsyncClient,
) -> None:
    """within=0 → 422 out-of-range validation (D-07)."""
    r = await authed_client_owner.get(
        "/api/v1/reports/clients",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31", "within": "0"},
    )
    assert r.status_code == 422, r.text


async def test_within_31_returns_422(
    authed_client_owner: AsyncClient,
) -> None:
    """within=31 → 422 out-of-range validation (D-07)."""
    r = await authed_client_owner.get(
        "/api/v1/reports/clients",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31", "within": "31"},
    )
    assert r.status_code == 422, r.text


async def test_new_clients_count_reflects_created_in_range(
    authed_client_owner: AsyncClient,
    make_client: Any,
) -> None:
    """newClientsCount counts clients created_at within [fromDate, toDate] MSK (CLR-03)."""
    today = datetime.now(tz=UTC).date()
    today_str = today.isoformat()

    # Count before inserting our client
    r_before = await authed_client_owner.get(
        "/api/v1/reports/clients",
        params={"fromDate": today_str, "toDate": today_str},
    )
    assert r_before.status_code == 200, r_before.text
    count_before = r_before.json()["data"]["newClientsCount"]

    # Create a new client (created_at defaults to now — within today's window)
    await make_client()

    r_after = await authed_client_owner.get(
        "/api/v1/reports/clients",
        params={"fromDate": today_str, "toDate": today_str},
    )
    assert r_after.status_code == 200, r_after.text
    count_after = r_after.json()["data"]["newClientsCount"]

    assert count_after == count_before + 1, (
        f"Expected newClientsCount {count_before + 1}, got {count_after}"
    )


async def test_new_clients_count_excludes_soft_deleted(
    authed_client_owner: AsyncClient,
    make_client: Any,
    db_session: AsyncSession,
) -> None:
    """newClientsCount excludes soft-deleted clients even if created in range (CLR-04)."""
    today = datetime.now(tz=UTC).date()
    today_str = today.isoformat()

    cli = await make_client()

    # Count including our new client (not yet deleted)
    r_alive = await authed_client_owner.get(
        "/api/v1/reports/clients",
        params={"fromDate": today_str, "toDate": today_str},
    )
    assert r_alive.status_code == 200, r_alive.text
    count_alive = r_alive.json()["data"]["newClientsCount"]

    # Soft-delete the client
    await _soft_delete_client(db_session, cli.id)

    r_deleted = await authed_client_owner.get(
        "/api/v1/reports/clients",
        params={"fromDate": today_str, "toDate": today_str},
    )
    assert r_deleted.status_code == 200, r_deleted.text
    count_deleted = r_deleted.json()["data"]["newClientsCount"]

    assert count_deleted == count_alive - 1, (
        f"Soft-deleted client should be excluded from newClientsCount: "
        f"before={count_alive} after={count_deleted}"
    )


async def test_within_default_is_7(
    authed_client_owner: AsyncClient,
) -> None:
    """Default within=7 is applied when param is omitted (D-07)."""
    r_default = await authed_client_owner.get(
        "/api/v1/reports/clients",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r_default.status_code == 200, r_default.text
    assert r_default.json()["data"]["withinDays"] == 7


async def test_to_before_from_returns_422_clients(
    authed_client_owner: AsyncClient,
) -> None:
    """toDate < fromDate → 422 (D-05)."""
    r = await authed_client_owner.get(
        "/api/v1/reports/clients",
        params={"fromDate": "2026-05-31", "toDate": "2026-05-01"},
    )
    assert r.status_code == 422, r.text
