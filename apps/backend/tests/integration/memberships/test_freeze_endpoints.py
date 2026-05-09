"""Integration tests for POST /freeze + /unfreeze endpoints (MEM-FRZ-EP-01..03).

Coverage:
  - RBAC matrix: anonymous → 401, reception → 200, owner → 200.
  - CSRF enforcement: missing X-CSRF-Token → 403.
  - Response shape: 4 new freeze fields present in camelCase wire format.
  - currentFreezePeriod object shape (id, startedAt, startedBy, endedAt, endedBy).
  - GET /memberships/{id} after unfreeze returns currentFreezePeriod=null.
  - Invalid transitions (cancelled→freeze, active→unfreeze) → 409 invalid_transition.

Reception+owner permission per D-25-19: (CREATE, MEMBERSHIPS) ∉ OWNER_ONLY.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf") or ""}


VALID_CLIENT: dict[str, Any] = {
    "lastName": "Иванов",
    "firstName": "Иван",
    "phone": "+79991234070",
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


async def test_freeze_anonymous_returns_401(
    async_client: AsyncClient,
) -> None:
    """RBAC-04: unauth POST /freeze → 401 (auth fires before CSRF/RBAC)."""
    r = await async_client.post(f"/api/v1/memberships/{uuid4()}/freeze")
    assert r.status_code == 401, r.text


async def test_unfreeze_anonymous_returns_401(
    async_client: AsyncClient,
) -> None:
    """RBAC-04: unauth POST /unfreeze → 401."""
    r = await async_client.post(f"/api/v1/memberships/{uuid4()}/unfreeze")
    assert r.status_code == 401, r.text


async def test_freeze_reception_returns_200(
    authed_client_reception: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """(CREATE, MEMBERSHIPS) ∉ OWNER_ONLY → reception 200 on /freeze."""
    plan = await make_plan(name="EP Reception")
    client = await _create_client(authed_client_reception, phone="+79991234071")
    client_uuid = UUID(client["id"])
    membership = await make_membership(client_id=client_uuid, plan=plan, status="active")

    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership.id}/freeze",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "frozen"


async def test_freeze_owner_returns_200(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Owner can also freeze (owner role short-circuits RBAC)."""
    plan = await make_plan(name="EP Owner")
    client = await _create_client(authed_client_owner, phone="+79991234072")
    client_uuid = UUID(client["id"])
    membership = await make_membership(client_id=client_uuid, plan=plan, status="active")

    r = await authed_client_owner.post(
        f"/api/v1/memberships/{membership.id}/freeze",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "frozen"


async def test_freeze_csrf_missing_returns_403(
    authed_client_reception: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """RBAC-04: auth OK but no CSRF header → 403 (csrf fires after auth/rbac)."""
    plan = await make_plan(name="EP CSRF")
    client = await _create_client(authed_client_reception, phone="+79991234073")
    membership = await make_membership(
        client_id=UUID(client["id"]), plan=plan, status="active"
    )

    # No CSRF header
    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership.id}/freeze",
    )
    assert r.status_code == 403, r.text


async def test_unfreeze_reception_returns_200(
    authed_client_reception: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Reception can unfreeze a frozen membership."""
    plan = await make_plan(name="EP Unfreeze Recep")
    client = await _create_client(authed_client_reception, phone="+79991234074")
    membership = await make_membership(
        client_id=UUID(client["id"]), plan=plan, status="active"
    )

    # Freeze first
    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership.id}/freeze",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 200

    # Unfreeze
    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership.id}/unfreeze",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "active"


# --- Response shape (MEM-FRZ-EP-03) ----------------------------------------


async def test_freeze_response_shape_includes_4_new_fields(
    authed_client_reception: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """MEM-FRZ-EP-03: response carries the 4 new camelCase keys."""
    plan = await make_plan(name="EP Shape", freeze_days_limit=14)
    client = await _create_client(authed_client_reception, phone="+79991234075")
    membership = await make_membership(
        client_id=UUID(client["id"]), plan=plan, status="active"
    )

    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership.id}/freeze",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]

    # Phase 25 D-25-12: 4 new freeze projection fields in camelCase.
    assert "freezeDaysLimitSnapshot" in data
    assert "freezeDaysUsed" in data
    assert "freezeDaysRemaining" in data
    assert "currentFreezePeriod" in data
    assert data["freezeDaysLimitSnapshot"] == 14
    assert data["freezeDaysRemaining"] == 14 - data["freezeDaysUsed"]


async def test_freeze_response_currentFreezePeriod_object_shape(
    authed_client_reception: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """currentFreezePeriod is a dict with id, startedAt, startedBy, endedAt, endedBy keys."""
    plan = await make_plan(name="EP Period Shape")
    client = await _create_client(authed_client_reception, phone="+79991234076")
    membership = await make_membership(
        client_id=UUID(client["id"]), plan=plan, status="active"
    )

    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership.id}/freeze",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 200, r.text
    period = r.json()["data"]["currentFreezePeriod"]
    assert isinstance(period, dict)
    assert "id" in period
    assert "startedAt" in period
    assert "startedBy" in period
    assert "endedAt" in period
    assert "endedBy" in period
    # Open period invariants.
    assert period["endedAt"] is None
    assert period["endedBy"] is None


async def test_membership_get_after_unfreeze_currentFreezePeriod_null(
    authed_client_reception: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """After unfreeze, GET /memberships/{id} returns currentFreezePeriod=null."""
    plan = await make_plan(name="EP After Unfreeze")
    client = await _create_client(authed_client_reception, phone="+79991234077")
    membership = await make_membership(
        client_id=UUID(client["id"]), plan=plan, status="active"
    )

    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership.id}/freeze",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 200

    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership.id}/unfreeze",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 200

    r = await authed_client_reception.get(f"/api/v1/memberships/{membership.id}")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["status"] == "active"
    assert data["currentFreezePeriod"] is None


# --- Invalid transition guards (D-25-15) -----------------------------------


async def test_freeze_invalid_transition_from_cancelled_returns_409(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Cancelled membership → POST /freeze → 409 invalid_transition."""
    plan = await make_plan(name="EP InvFreeze")
    client = await _create_client(authed_client_owner, phone="+79991234078")
    membership = await make_membership(
        client_id=UUID(client["id"]), plan=plan, status="cancelled"
    )

    r = await authed_client_owner.post(
        f"/api/v1/memberships/{membership.id}/freeze",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    body = r.json()
    assert body["code"] == "invalid_transition"
    assert body["fields"]["from_status"] == "cancelled"
    assert body["fields"]["to_status"] == "frozen"


async def test_unfreeze_invalid_transition_from_active_returns_409(
    authed_client_reception: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Active (non-frozen) membership → POST /unfreeze → 409 invalid_transition."""
    plan = await make_plan(name="EP InvUnfreeze")
    client = await _create_client(authed_client_reception, phone="+79991234079")
    membership = await make_membership(
        client_id=UUID(client["id"]), plan=plan, status="active"
    )

    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership.id}/unfreeze",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 409, r.text
    body = r.json()
    assert body["code"] == "invalid_transition"
    assert body["fields"]["from_status"] == "active"
    assert body["fields"]["to_status"] == "active"


# Note: db_session imported only via fixture chain; explicit import for type stability
async def test_freeze_membership_not_found_returns_404(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,  # noqa: ARG001 -- forces savepoint scope
) -> None:
    """POST /freeze on a non-existent membership → 404 membership_not_found."""
    r = await authed_client_reception.post(
        f"/api/v1/memberships/{uuid4()}/freeze",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "membership_not_found"
