"""Phase 26 Plan 26-03 Task 2 — POST /memberships/{id}/renew + service flow.

RED-phase coverage for the renewal write path:
  - RBAC matrix: anonymous → 401, reception → 201, owner → 201.
  - CSRF enforcement: missing X-CSRF-Token → 403.
  - 404 membership_not_found for unknown source UUID.
  - 409 cannot_renew_cancelled for cancelled source.
  - 409 plan_archived for soft-deleted plan.
  - Active source: start_date = source.end_date + 1; strategy = from_source_end_date.
  - Expired source: start_date = today (Europe/Moscow); strategy = from_today_expired_source.
  - Frozen source: start_date = source.end_date + 1; source stays frozen.
  - Snapshots from CURRENT plan (price_kopecks_snapshot reflects post-PATCH plan price).
  - Audit `membership_renewed` payload contains the documented keys.
  - Source row is NOT mutated (status, end_date, snapshots unchanged).
  - Response includes `previousMembershipId` (camelCase) field.
  - Response baseline freeze projection: freezeDaysUsed=0, currentFreezePeriod=null.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.memberships.models import Membership


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf") or ""}


VALID_CLIENT: dict[str, Any] = {
    "lastName": "Иванов",
    "firstName": "Иван",
    "phone": "+79991235010",
}


async def _create_client(authed: AsyncClient, **overrides: Any) -> dict[str, Any]:
    payload = {**VALID_CLIENT, **overrides}
    r = await authed.post(
        "/api/v1/clients",
        json=payload,
        headers=_csrf_headers(authed),
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


# --- RBAC matrix -----------------------------------------------------------


async def test_renew_anonymous_returns_401(
    async_client: AsyncClient,
) -> None:
    """RBAC-04: unauth POST /renew → 401 before CSRF/RBAC fires."""
    r = await async_client.post(f"/api/v1/memberships/{uuid4()}/renew")
    assert r.status_code == 401, r.text


async def test_renew_csrf_missing_returns_403(
    authed_client_reception: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """T-26-03-02: missing X-CSRF-Token → 403 csrf_mismatch."""
    plan = await make_plan(name="CSRF gate")
    client = await _create_client(authed_client_reception, phone="+79991235011")
    client_uuid = UUID(client["id"])
    source = await make_membership(client_id=client_uuid, plan=plan, status="active")

    r = await authed_client_reception.post(
        f"/api/v1/memberships/{source.id}/renew",
        # NO X-CSRF-Token header
    )
    assert r.status_code == 403, r.text


async def test_renew_unknown_source_returns_404(
    authed_client_reception: AsyncClient,
) -> None:
    """Missing source UUID → 404 membership_not_found."""
    r = await authed_client_reception.post(
        f"/api/v1/memberships/{uuid4()}/renew",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "membership_not_found"


async def test_renew_reception_active_source_returns_201(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Reception can renew (CREATE,MEMBERSHIPS not in OWNER_ONLY); active source.

    start_date = source.end_date + 1; end_date = start + (duration - 1).
    Snapshots come from CURRENT plan; previousMembershipId = source.id.
    """
    plan = await make_plan(
        name="Reception renew",
        duration_days=30,
        price_kopecks=200_000,
        freeze_days_limit=14,
    )
    client = await _create_client(authed_client_reception, phone="+79991235012")
    client_uuid = UUID(client["id"])
    today = datetime.now(tz=UTC).date()
    source = await make_membership(
        client_id=client_uuid,
        plan=plan,
        status="active",
        start_date=today,
        end_date=today + timedelta(days=29),
    )

    r = await authed_client_reception.post(
        f"/api/v1/memberships/{source.id}/renew",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()["data"]

    expected_start = (source.end_date + timedelta(days=1)).isoformat()
    expected_end = (source.end_date + timedelta(days=30)).isoformat()
    assert body["startDate"] == expected_start
    assert body["endDate"] == expected_end
    assert body["status"] == "active"
    assert body["priceKopecksSnapshot"] == 200_000
    assert body["durationDaysSnapshot"] == 30
    assert body["freezeDaysLimitSnapshot"] == 14
    assert body["previousMembershipId"] == str(source.id)
    # Baseline freeze projection on a brand-new row.
    assert body["freezeDaysUsed"] == 0
    assert body["freezeDaysRemaining"] == 14
    assert body["currentFreezePeriod"] is None

    # Source row stays untouched.
    await db_session.refresh(source)
    assert source.status == "active"
    assert source.end_date == today + timedelta(days=29)
    assert source.price_kopecks_snapshot == 200_000


async def test_renew_owner_active_source_returns_201(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Owner can also renew (RBAC short-circuit)."""
    plan = await make_plan(name="Owner renew")
    client = await _create_client(authed_client_owner, phone="+79991235013")
    client_uuid = UUID(client["id"])
    source = await make_membership(client_id=client_uuid, plan=plan, status="active")

    r = await authed_client_owner.post(
        f"/api/v1/memberships/{source.id}/renew",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text


# --- Source-status guards -------------------------------------------------


async def test_renew_cancelled_source_returns_409_cannot_renew_cancelled(
    authed_client_reception: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Cancelled source → 409 cannot_renew_cancelled (T-26-03-08)."""
    plan = await make_plan(name="Cancel guard")
    client = await _create_client(authed_client_reception, phone="+79991235014")
    client_uuid = UUID(client["id"])
    source = await make_membership(client_id=client_uuid, plan=plan, status="cancelled")

    r = await authed_client_reception.post(
        f"/api/v1/memberships/{source.id}/renew",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "cannot_renew_cancelled"


async def test_renew_archived_plan_returns_409_plan_archived(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Source's plan soft-deleted → 409 plan_archived (T-26-03-09)."""
    plan = await make_plan(name="Archive guard")
    client = await _create_client(authed_client_reception, phone="+79991235015")
    client_uuid = UUID(client["id"])
    source = await make_membership(client_id=client_uuid, plan=plan, status="active")

    plan.deleted_at = datetime.now(tz=UTC)
    await db_session.commit()

    r = await authed_client_reception.post(
        f"/api/v1/memberships/{source.id}/renew",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "plan_archived"


# --- Date strategy branches ------------------------------------------------


async def test_renew_active_source_uses_from_source_end_date_strategy(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """active source → audit payload start_date_strategy='from_source_end_date'."""
    plan = await make_plan(name="Strategy active")
    client = await _create_client(authed_client_reception, phone="+79991235016")
    client_uuid = UUID(client["id"])
    source = await make_membership(client_id=client_uuid, plan=plan, status="active")

    r = await authed_client_reception.post(
        f"/api/v1/memberships/{source.id}/renew",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 201, r.text
    new_id = UUID(r.json()["data"]["id"])

    audit_row = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "membership_renewed",
            AuditLog.resource_id == new_id,
        )
    )
    assert audit_row is not None
    payload: dict[str, Any] = audit_row.payload
    assert payload["start_date_strategy"] == "from_source_end_date"
    assert payload["source_membership_id"] == str(source.id)
    assert payload["source_plan_id"] == str(source.plan_id)
    assert payload["client_id"] == str(source.client_id)
    assert payload["current_price_kopecks"] == plan.price_kopecks


async def test_renew_expired_source_uses_today_msk_and_from_today_strategy(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """expired source → start_date = today MSK; strategy=from_today_expired_source.

    The expired-source branch is the lock against retroactive renewals — see
    D-26-12. New start_date MUST be today (Europe/Moscow), NOT source.end_date+1.
    """
    plan = await make_plan(name="Strategy expired", duration_days=30)
    client = await _create_client(authed_client_reception, phone="+79991235017")
    client_uuid = UUID(client["id"])
    today_msk = datetime.now(ZoneInfo("Europe/Moscow")).date()
    long_past = today_msk - timedelta(days=60)
    source = await make_membership(
        client_id=client_uuid,
        plan=plan,
        status="expired",
        start_date=long_past,
        end_date=long_past + timedelta(days=29),  # ended ~31 days ago
    )

    r = await authed_client_reception.post(
        f"/api/v1/memberships/{source.id}/renew",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()["data"]

    # start_date = today MSK (NOT source.end_date + 1)
    assert body["startDate"] == today_msk.isoformat()
    assert body["endDate"] == (today_msk + timedelta(days=29)).isoformat()

    audit_row = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "membership_renewed",
            AuditLog.resource_id == UUID(body["id"]),
        )
    )
    assert audit_row is not None
    assert audit_row.payload["start_date_strategy"] == "from_today_expired_source"


async def test_renew_frozen_source_uses_from_source_end_date_and_keeps_source_frozen(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """frozen source: start_date = source.end_date + 1; source stays frozen."""
    plan = await make_plan(name="Strategy frozen")
    client = await _create_client(authed_client_reception, phone="+79991235018")
    client_uuid = UUID(client["id"])
    today = datetime.now(tz=UTC).date()
    source = await make_membership(
        client_id=client_uuid,
        plan=plan,
        status="frozen",
        start_date=today - timedelta(days=5),
        end_date=today + timedelta(days=10),
    )

    r = await authed_client_reception.post(
        f"/api/v1/memberships/{source.id}/renew",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()["data"]
    assert body["startDate"] == (source.end_date + timedelta(days=1)).isoformat()

    audit_row = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "membership_renewed",
            AuditLog.resource_id == UUID(body["id"]),
        )
    )
    assert audit_row is not None
    assert audit_row.payload["start_date_strategy"] == "from_source_end_date"

    # Source stays frozen — renewal is INSERT, not transition.
    await db_session.refresh(source)
    assert source.status == "frozen"


# --- Snapshot semantics ---------------------------------------------------


async def test_renew_snapshots_use_current_plan_after_price_change(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """If owner mutates plan between sale and renewal, NEW snapshot reflects current.

    The "client pays new price" lock from PROJECT.md and T-26-03-07.
    """
    plan = await make_plan(
        name="Price change",
        duration_days=30,
        price_kopecks=200_000,
        freeze_days_limit=14,
    )
    client = await _create_client(authed_client_reception, phone="+79991235019")
    client_uuid = UUID(client["id"])
    source = await make_membership(client_id=client_uuid, plan=plan, status="active")
    assert source.price_kopecks_snapshot == 200_000

    # Plan price increases between sale and renewal.
    plan.price_kopecks = 300_000
    await db_session.commit()
    await db_session.refresh(plan)

    r = await authed_client_reception.post(
        f"/api/v1/memberships/{source.id}/renew",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()["data"]
    assert body["priceKopecksSnapshot"] == 300_000  # CURRENT plan price

    audit_row = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "membership_renewed",
            AuditLog.resource_id == UUID(body["id"]),
        )
    )
    assert audit_row is not None
    assert audit_row.payload["current_price_kopecks"] == 300_000

    # Source row's snapshot stays the original (immutable).
    await db_session.refresh(source)
    assert source.price_kopecks_snapshot == 200_000


# --- Chain attribution + DB row presence ----------------------------------


async def test_renew_creates_chained_row_in_db(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Successful renewal inserts a Membership row with previous_membership_id=source.id."""
    plan = await make_plan(name="Chain")
    client = await _create_client(authed_client_reception, phone="+79991235020")
    client_uuid = UUID(client["id"])
    source = await make_membership(client_id=client_uuid, plan=plan, status="active")

    r = await authed_client_reception.post(
        f"/api/v1/memberships/{source.id}/renew",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 201, r.text
    new_id = UUID(r.json()["data"]["id"])

    new_row = await db_session.scalar(select(Membership).where(Membership.id == new_id))
    assert new_row is not None
    assert new_row.previous_membership_id == source.id
    assert new_row.client_id == source.client_id
    assert new_row.status == "active"


# --- Plan 26-04 acceptance shims ------------------------------------------
#
# Plan 26-04 acceptance criteria require these EXACT function names. The
# semantics duplicate the longer-named tests above but pin the contract under
# the names the criteria check, so a future rename of the longer tests can
# never silently drop the matrix coverage.


async def test_renew_reception_returns_201(
    authed_client_reception: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Plan 26-04 acceptance shim: reception POST → 201 (CREATE ∉ OWNER_ONLY)."""
    plan = await make_plan(name="Acceptance reception")
    client = await _create_client(authed_client_reception, phone="+79991235021")
    client_uuid = UUID(client["id"])
    source = await make_membership(client_id=client_uuid, plan=plan, status="active")

    r = await authed_client_reception.post(
        f"/api/v1/memberships/{source.id}/renew",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 201, r.text


async def test_renew_owner_returns_201(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Plan 26-04 acceptance shim: owner POST → 201."""
    plan = await make_plan(name="Acceptance owner")
    client = await _create_client(authed_client_owner, phone="+79991235022")
    client_uuid = UUID(client["id"])
    source = await make_membership(client_id=client_uuid, plan=plan, status="active")

    r = await authed_client_owner.post(
        f"/api/v1/memberships/{source.id}/renew",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text


async def test_renew_response_includes_previous_membership_id_camelcase(
    authed_client_reception: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Plan 26-04 acceptance shim: response.data.previousMembershipId == source.id (camelCase)."""
    plan = await make_plan(name="Acceptance camelCase")
    client = await _create_client(authed_client_reception, phone="+79991235023")
    client_uuid = UUID(client["id"])
    source = await make_membership(client_id=client_uuid, plan=plan, status="active")

    r = await authed_client_reception.post(
        f"/api/v1/memberships/{source.id}/renew",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()["data"]
    # The wire field is camelCase (BackendSchemaBase alias_generator).
    assert "previousMembershipId" in body
    assert body["previousMembershipId"] == str(source.id)


async def test_renew_response_includes_freeze_projection_zero_baseline(
    authed_client_reception: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Plan 26-04 acceptance shim: zero-baseline freeze projection on a brand-new row.

    A renewal row is freshly created — it has no MembershipFreezePeriod rows
    yet, so freezeDaysUsed=0, currentFreezePeriod=None, and
    freezeDaysRemaining=plan.freeze_days_limit (unclamped baseline).
    """
    plan = await make_plan(
        name="Acceptance freeze baseline",
        freeze_days_limit=14,
    )
    client = await _create_client(authed_client_reception, phone="+79991235024")
    client_uuid = UUID(client["id"])
    source = await make_membership(client_id=client_uuid, plan=plan, status="active")

    r = await authed_client_reception.post(
        f"/api/v1/memberships/{source.id}/renew",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()["data"]
    assert body["freezeDaysUsed"] == 0
    assert body["currentFreezePeriod"] is None
    assert body["freezeDaysRemaining"] == 14
