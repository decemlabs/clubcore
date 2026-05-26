"""Integration tests for /api/v1/memberships sale + cancel CRUD (MEM-EP-02..04).

End-to-end via httpx ASGITransport against the SAVEPOINT-mode db_session.
Marquee tests:
  - test_sale_happy_path (D-04 — server-computed start/end dates inclusive)
  - test_sale_409_on_inactive_plan (D-02 — UI-bypass defence)
  - test_cancel_409_invalid_transition_expired / _cancelled (D-12 — state machine)
  - test_cancel_no_body_omits_reason (D-14 — reason key absent, not None)
  - test_cancel_rejects_explicit_null_reason (D-11 — Pydantic explicit-null guard)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.memberships.models import Membership


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    # Phase 32 PAY-09: POST /api/v1/memberships now requires Idempotency-Key.
    # Sub-routes (/cancel, /freeze, /renew) ignore the header — harmless to
    # always include. uuid4().hex is per-call unique so replay collision is
    # avoided across the test suite.
    return {
        "X-CSRF-Token": client.cookies.get("sportzal_csrf") or "",
        "Idempotency-Key": uuid4().hex,
    }


VALID_PLAN: dict[str, Any] = {
    "name": "Базовый",
    "durationDays": 30,
    "priceKopecks": 250000,
    "freezeDaysLimit": 14,
    "active": True,
}


VALID_CLIENT: dict[str, Any] = {
    "lastName": "Иванов",
    "firstName": "Иван",
    "phone": "+79991234567",
}


async def _create_plan(
    authed_client_owner: AsyncClient,
    **overrides: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {**VALID_PLAN, **overrides}
    r = await authed_client_owner.post(
        "/api/v1/membership-plans",
        json=payload,
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


async def _create_client(
    authed_client_owner: AsyncClient,
    **overrides: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {**VALID_CLIENT, **overrides}
    r = await authed_client_owner.post(
        "/api/v1/clients",
        json=payload,
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


# --- Sale (POST /memberships) -----------------------------------------------


async def test_sale_happy_path(
    authed_client_owner: AsyncClient,
) -> None:
    """MEM-EP-02 happy path: 201 + snapshot fields + server-computed dates (D-04).

    end_date is INCLUSIVE: start_date + (duration_days - 1).
    start_date is today in Europe/Moscow.
    """
    plan = await _create_plan(authed_client_owner)
    client = await _create_client(authed_client_owner)

    r = await authed_client_owner.post(
        "/api/v1/memberships",
        json={"clientId": client["id"], "planId": plan["id"]},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    UUID(data["id"])
    assert data["clientId"] == client["id"]
    assert data["planId"] == plan["id"]
    assert data["planNameSnapshot"] == plan["name"]
    assert data["durationDaysSnapshot"] == plan["durationDays"]
    assert data["priceKopecksSnapshot"] == plan["priceKopecks"]
    assert data["status"] == "active"
    assert data["paidAt"] is None
    assert data["notes"] is None
    assert data["cancelledAt"] is None
    assert data["cancelReason"] is None

    # D-04: start_date == today in Europe/Moscow; end_date inclusive.
    expected_start = datetime.now(ZoneInfo("Europe/Moscow")).date()
    expected_end = expected_start + timedelta(days=plan["durationDays"] - 1)
    assert data["startDate"] == expected_start.isoformat()
    assert data["endDate"] == expected_end.isoformat()


async def test_sale_with_paid_at_iso(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """D-03 / specifics: explicit ISO paidAt persists to the row's paid_at column."""
    plan = await _create_plan(authed_client_owner)
    client = await _create_client(authed_client_owner)

    paid_at_iso = "2026-05-01T10:00:00Z"
    r = await authed_client_owner.post(
        "/api/v1/memberships",
        json={
            "clientId": client["id"],
            "planId": plan["id"],
            "paidAt": paid_at_iso,
        },
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["paidAt"] is not None
    # Wire format may normalise the suffix; parse and compare timestamps.
    response_dt = datetime.fromisoformat(data["paidAt"].replace("Z", "+00:00"))
    expected_dt = datetime(2026, 5, 1, 10, 0, 0, tzinfo=UTC)
    assert response_dt == expected_dt

    # And verify the DB column is non-null.
    membership_id = UUID(data["id"])
    row = await db_session.scalar(select(Membership).where(Membership.id == membership_id))
    assert row is not None
    assert row.paid_at is not None


async def test_sale_without_paid_at_persists_null(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """D-03: omitted paidAt persists as NULL in the DB column."""
    plan = await _create_plan(authed_client_owner)
    client = await _create_client(authed_client_owner)

    r = await authed_client_owner.post(
        "/api/v1/memberships",
        json={"clientId": client["id"], "planId": plan["id"]},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    membership_id = UUID(r.json()["data"]["id"])
    row = await db_session.scalar(select(Membership).where(Membership.id == membership_id))
    assert row is not None
    assert row.paid_at is None


async def test_sale_with_notes(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """D-03: notes field persists to the row."""
    plan = await _create_plan(authed_client_owner)
    client = await _create_client(authed_client_owner)

    r = await authed_client_owner.post(
        "/api/v1/memberships",
        json={
            "clientId": client["id"],
            "planId": plan["id"],
            "notes": "renewal",
        },
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["notes"] == "renewal"

    membership_id = UUID(data["id"])
    row = await db_session.scalar(select(Membership).where(Membership.id == membership_id))
    assert row is not None
    assert row.notes == "renewal"


async def test_sale_404_on_unknown_plan(
    authed_client_owner: AsyncClient,
) -> None:
    """MEM-EP-02: random planId -> 404 plan_not_found."""
    client = await _create_client(authed_client_owner)
    r = await authed_client_owner.post(
        "/api/v1/memberships",
        json={"clientId": client["id"], "planId": str(uuid4())},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "plan_not_found"


async def test_sale_409_on_inactive_plan(
    authed_client_owner: AsyncClient,
) -> None:
    """D-02: POST against plan.active=False -> 409 plan_inactive (UI-bypass defence)."""
    plan = await _create_plan(authed_client_owner)
    # Deactivate via PATCH
    r_patch = await authed_client_owner.patch(
        f"/api/v1/membership-plans/{plan['id']}",
        json={"active": False},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_patch.status_code == 200, r_patch.text

    client = await _create_client(authed_client_owner)
    r = await authed_client_owner.post(
        "/api/v1/memberships",
        json={"clientId": client["id"], "planId": plan["id"]},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "plan_inactive"


async def test_sale_404_on_soft_deleted_plan(
    authed_client_owner: AsyncClient,
) -> None:
    """Soft-deleted plan is not alive -> 404 plan_not_found."""
    plan = await _create_plan(authed_client_owner)
    r_del = await authed_client_owner.delete(
        f"/api/v1/membership-plans/{plan['id']}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_del.status_code == 204, r_del.text

    client = await _create_client(authed_client_owner)
    r = await authed_client_owner.post(
        "/api/v1/memberships",
        json={"clientId": client["id"], "planId": plan["id"]},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "plan_not_found"


async def test_sale_extra_field_rejected(
    authed_client_owner: AsyncClient,
) -> None:
    """extra='forbid' on BackendSchemaBase: server-computed startDate must NOT be in body."""
    plan = await _create_plan(authed_client_owner)
    client = await _create_client(authed_client_owner)

    r = await authed_client_owner.post(
        "/api/v1/memberships",
        json={
            "clientId": client["id"],
            "planId": plan["id"],
            "startDate": "2026-01-01",  # server-computed; rejected
        },
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 422, r.text


async def test_sale_rejects_notes_above_1000_chars(
    authed_client_owner: AsyncClient,
) -> None:
    """notes max_length=1000 (T-17-02 mitigation)."""
    plan = await _create_plan(authed_client_owner)
    client = await _create_client(authed_client_owner)

    r = await authed_client_owner.post(
        "/api/v1/memberships",
        json={
            "clientId": client["id"],
            "planId": plan["id"],
            "notes": "x" * 1001,
        },
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 422, r.text


# --- Cancel (POST /memberships/{id}/cancel) ---------------------------------


async def test_cancel_happy_path(
    authed_client_owner: AsyncClient,
) -> None:
    """MEM-EP-04 happy path: active -> cancelled, body returns post-transition row."""
    plan = await _create_plan(authed_client_owner)
    client = await _create_client(authed_client_owner)
    sale_resp = await authed_client_owner.post(
        "/api/v1/memberships",
        json={"clientId": client["id"], "planId": plan["id"]},
        headers=_csrf_headers(authed_client_owner),
    )
    assert sale_resp.status_code == 201, sale_resp.text
    membership_id = sale_resp.json()["data"]["id"]

    r = await authed_client_owner.post(
        f"/api/v1/memberships/{membership_id}/cancel",
        json={"reason": "client requested"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["status"] == "cancelled"
    assert data["cancelledAt"] is not None
    assert data["cancelReason"] == "client requested"


async def test_cancel_no_body_omits_reason(
    authed_client_owner: AsyncClient,
) -> None:
    """D-14: cancel with no body -> cancelReason is None in response."""
    plan = await _create_plan(authed_client_owner)
    client = await _create_client(authed_client_owner)
    sale_resp = await authed_client_owner.post(
        "/api/v1/memberships",
        json={"clientId": client["id"], "planId": plan["id"]},
        headers=_csrf_headers(authed_client_owner),
    )
    assert sale_resp.status_code == 201
    membership_id = sale_resp.json()["data"]["id"]

    r = await authed_client_owner.post(
        f"/api/v1/memberships/{membership_id}/cancel",
        json={},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["status"] == "cancelled"
    assert data["cancelReason"] is None


async def test_cancel_409_invalid_transition_expired(
    authed_client_owner: AsyncClient,
    seeded_owner: User,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """D-12: cancel on expired -> 409 invalid_transition with {from_status, to_status}."""
    # Need a real client_id — but creating a client via API requires a created_by
    # FK that points to an active user. Reuse seeded_owner via direct insert.
    plan = await make_plan(name="Expired Plan")
    # Seed a Client row directly to get a real client_id without firing audit.
    client = await _create_client(authed_client_owner, phone="+79990000001")
    membership = await make_membership(
        client_id=UUID(client["id"]),
        plan=plan,
        status="expired",
    )
    assert seeded_owner is not None  # fixture used to align RBAC chain

    r = await authed_client_owner.post(
        f"/api/v1/memberships/{membership.id}/cancel",
        json={"reason": "n/a"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    body = r.json()
    assert body["code"] == "invalid_transition"
    assert body["fields"] == {
        "from_status": "expired",
        "to_status": "cancelled",
    }


async def test_cancel_409_invalid_transition_cancelled(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """D-12: cancel on cancelled -> 409 invalid_transition (idempotency NOT silent)."""
    plan = await make_plan(name="Cancelled Plan")
    client = await _create_client(authed_client_owner, phone="+79990000002")
    membership = await make_membership(
        client_id=UUID(client["id"]),
        plan=plan,
        status="cancelled",
    )

    r = await authed_client_owner.post(
        f"/api/v1/memberships/{membership.id}/cancel",
        json={},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    body = r.json()
    assert body["code"] == "invalid_transition"
    assert body["fields"] == {
        "from_status": "cancelled",
        "to_status": "cancelled",
    }


async def test_cancel_404_on_unknown_id(
    authed_client_owner: AsyncClient,
) -> None:
    """MEM-EP-04: cancel on random UUID -> 404 membership_not_found."""
    r = await authed_client_owner.post(
        f"/api/v1/memberships/{uuid4()}/cancel",
        json={},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "membership_not_found"


async def test_cancel_rejects_explicit_null_reason(
    authed_client_owner: AsyncClient,
) -> None:
    """D-11: explicit null reason -> 422 (Pydantic explicit-null guard)."""
    plan = await _create_plan(authed_client_owner)
    client = await _create_client(authed_client_owner)
    sale_resp = await authed_client_owner.post(
        "/api/v1/memberships",
        json={"clientId": client["id"], "planId": plan["id"]},
        headers=_csrf_headers(authed_client_owner),
    )
    assert sale_resp.status_code == 201
    membership_id = sale_resp.json()["data"]["id"]

    r = await authed_client_owner.post(
        f"/api/v1/memberships/{membership_id}/cancel",
        json={"reason": None},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 422, r.text
    assert "Explicit null" in r.text


# --- GET single membership -------------------------------------------------


async def test_get_membership_returns_row(
    authed_client_owner: AsyncClient,
) -> None:
    """MEM-EP-03: GET /{id} returns the membership row, 200 OK."""
    plan = await _create_plan(authed_client_owner)
    client = await _create_client(authed_client_owner)
    sale_resp = await authed_client_owner.post(
        "/api/v1/memberships",
        json={"clientId": client["id"], "planId": plan["id"]},
        headers=_csrf_headers(authed_client_owner),
    )
    assert sale_resp.status_code == 201
    membership_id = sale_resp.json()["data"]["id"]

    r = await authed_client_owner.get(f"/api/v1/memberships/{membership_id}")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["id"] == membership_id
    assert data["status"] == "active"


async def test_get_membership_404_on_unknown(
    authed_client_owner: AsyncClient,
) -> None:
    """MEM-EP-03: GET on random UUID -> 404 membership_not_found."""
    r = await authed_client_owner.get(f"/api/v1/memberships/{uuid4()}")
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "membership_not_found"


# --- Stacking (D-01) -------------------------------------------------------


async def test_sale_allows_stacking_on_existing_active(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """D-01: NO pre-flight active-membership check; second sale on same client succeeds."""
    plan = await make_plan(name="Stacking")
    client = await _create_client(authed_client_owner, phone="+79990000003")
    # Seed an active membership directly
    existing = await make_membership(
        client_id=UUID(client["id"]),
        plan=plan,
    )
    # Now POST a second sale on the same client — must succeed (D-01)
    r = await authed_client_owner.post(
        "/api/v1/memberships",
        json={"clientId": client["id"], "planId": str(plan.id)},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    new_id = r.json()["data"]["id"]
    assert new_id != str(existing.id)
