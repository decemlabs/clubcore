"""Integration tests for /api/v1/membership-plans CRUD (MEM-PLAN-EP-01..04).

Each test owns its DB state via the SAVEPOINT-rolled `db_session` fixture
and exercises the full route -> service -> repository -> DB chain through
httpx ASGITransport.

Marquee tests:
  - test_delete_frees_unique_name_slot (D-16 — partial-unique-on-alive)
  - test_patch_duration_days_returns_422 (D-04 — extra='forbid')
  - test_patch_idempotent_noop_does_not_emit_audit (D-09 + D-14)
  - test_post_duplicate_alive_name_returns_409_plan_name_exists (D-02)
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf", "")}


VALID_PLAN: dict[str, Any] = {
    "name": "Базовый",
    "durationDays": 30,
    "priceKopecks": 250000,
    "freezeDaysLimit": 14,
    "active": True,
}


async def _create(
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


async def test_post_creates_plan_returns_201_with_envelope(
    authed_client_owner: AsyncClient,
) -> None:
    """MEM-PLAN-EP-02 happy path: POST returns 201 + ResponseEnvelope[MembershipPlanResponse]."""
    r = await authed_client_owner.post(
        "/api/v1/membership-plans",
        json=VALID_PLAN,
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert "data" in body
    data = body["data"]
    # id must parse as UUID
    UUID(data["id"])
    assert data["name"] == "Базовый"
    assert data["durationDays"] == 30
    assert data["priceKopecks"] == 250000
    assert data["active"] is True
    assert "createdAt" in data
    assert "updatedAt" in data


async def test_post_active_defaults_to_true_when_omitted(
    authed_client_owner: AsyncClient,
) -> None:
    """D-06: omitting `active` defaults to True (DTO default + DB DEFAULT TRUE)."""
    payload = {k: v for k, v in VALID_PLAN.items() if k != "active"}
    r = await authed_client_owner.post(
        "/api/v1/membership-plans",
        json=payload,
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    assert r.json()["data"]["active"] is True


async def test_post_duplicate_alive_name_returns_409_plan_name_exists(
    authed_client_owner: AsyncClient,
) -> None:
    """D-02: second POST with same name among alive rows -> 409 plan_name_exists."""
    await _create(authed_client_owner, name="Базовый")

    r = await authed_client_owner.post(
        "/api/v1/membership-plans",
        json={**VALID_PLAN, "name": "Базовый"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "plan_name_exists"


async def test_post_case_variant_duplicate_returns_409(
    authed_client_owner: AsyncClient,
) -> None:
    """D-02: partial-unique on lower(name) catches case-variant duplicates."""
    await _create(authed_client_owner, name="Базовый")

    r = await authed_client_owner.post(
        "/api/v1/membership-plans",
        json={**VALID_PLAN, "name": "БАЗОВЫЙ"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "plan_name_exists"


async def test_post_trims_whitespace_preserves_casing(
    authed_client_owner: AsyncClient,
) -> None:
    """D-01: leading/trailing whitespace is stripped; internal casing preserved."""
    data = await _create(authed_client_owner, name="  Базовый  ")
    assert data["name"] == "Базовый"


async def test_post_rejects_post_trim_empty_name(
    authed_client_owner: AsyncClient,
) -> None:
    """D-01 + D-06: whitespace-only name fails min_length=1 after trim."""
    r = await authed_client_owner.post(
        "/api/v1/membership-plans",
        json={**VALID_PLAN, "name": "   "},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 422, r.text


async def test_get_single_returns_plan(
    authed_client_owner: AsyncClient,
) -> None:
    """MEM-PLAN-EP-01: GET /{plan_id} returns 200 with envelope + same data as POST."""
    created = await _create(authed_client_owner)
    plan_id = created["id"]

    r = await authed_client_owner.get(f"/api/v1/membership-plans/{plan_id}")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["id"] == plan_id
    assert data["name"] == created["name"]
    assert data["durationDays"] == created["durationDays"]
    assert data["priceKopecks"] == created["priceKopecks"]


async def test_get_single_404_for_missing(
    authed_client_owner: AsyncClient,
) -> None:
    """MEM-PLAN-EP-01: GET on a non-existent UUID -> 404 plan_not_found."""
    r = await authed_client_owner.get(
        "/api/v1/membership-plans/00000000-0000-0000-0000-000000000000"
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "plan_not_found"


async def test_patch_updates_name_and_price(
    authed_client_owner: AsyncClient,
) -> None:
    """MEM-PLAN-EP-03: PATCH updates specified fields; GET reflects new values."""
    created = await _create(authed_client_owner)
    plan_id = created["id"]

    r_patch = await authed_client_owner.patch(
        f"/api/v1/membership-plans/{plan_id}",
        json={"name": "Премиум", "priceKopecks": 500000},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_patch.status_code == 200, r_patch.text

    r_get = await authed_client_owner.get(f"/api/v1/membership-plans/{plan_id}")
    body = r_get.json()["data"]
    assert body["name"] == "Премиум"
    assert body["priceKopecks"] == 500000
    assert body["durationDays"] == created["durationDays"]  # unchanged


async def test_patch_duration_days_returns_422(
    authed_client_owner: AsyncClient,
) -> None:
    """D-04: PATCH with durationDays in body -> 422 (extra='forbid' from BackendSchemaBase)."""
    created = await _create(authed_client_owner)
    plan_id = created["id"]

    r = await authed_client_owner.patch(
        f"/api/v1/membership-plans/{plan_id}",
        json={"durationDays": 90},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 422, r.text
    # Pydantic stock "Extra inputs are not permitted" names the rejected key
    assert "durationDays" in r.text


async def test_patch_explicit_null_returns_422(
    authed_client_owner: AsyncClient,
) -> None:
    """D-05: explicit null in PATCH body -> 422 with 'Explicit null' message."""
    created = await _create(authed_client_owner)
    plan_id = created["id"]

    r = await authed_client_owner.patch(
        f"/api/v1/membership-plans/{plan_id}",
        json={"name": None},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 422, r.text
    assert "Explicit null" in r.text


async def test_patch_idempotent_noop_does_not_emit_audit(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """D-09 + D-14: PATCH that changes nothing must not emit membership_plan_updated.

    Send the same priceKopecks the row already has. The service short-circuits
    before audit.emit when `repository.update_plan` returns an empty changed dict.
    """
    created = await _create(authed_client_owner)
    plan_id = UUID(created["id"])

    r = await authed_client_owner.patch(
        f"/api/v1/membership-plans/{plan_id}",
        json={"priceKopecks": VALID_PLAN["priceKopecks"]},  # same as current
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "membership_plan_updated",
                AuditLog.resource_id == plan_id,
            )
        )
    ).all()
    assert len(rows) == 0, "no-op PATCH must NOT emit membership_plan_updated (D-09)"


async def test_delete_returns_204(
    authed_client_owner: AsyncClient,
) -> None:
    """MEM-PLAN-EP-04: DELETE returns 204 No Content with empty body."""
    created = await _create(authed_client_owner)
    r = await authed_client_owner.delete(
        f"/api/v1/membership-plans/{created['id']}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 204, r.text
    assert r.content == b""


async def test_delete_then_get_returns_404(
    authed_client_owner: AsyncClient,
) -> None:
    """Soft-delete invariant: GET on soft-deleted plan -> 404 plan_not_found."""
    created = await _create(authed_client_owner)
    plan_id = created["id"]

    r_del = await authed_client_owner.delete(
        f"/api/v1/membership-plans/{plan_id}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_del.status_code == 204, r_del.text

    r_get = await authed_client_owner.get(f"/api/v1/membership-plans/{plan_id}")
    assert r_get.status_code == 404
    assert r_get.json()["code"] == "plan_not_found"


async def test_delete_then_delete_returns_404(
    authed_client_owner: AsyncClient,
) -> None:
    """Soft-delete invariant: second DELETE on already-soft-deleted -> 404."""
    created = await _create(authed_client_owner)
    plan_id = created["id"]

    r_del1 = await authed_client_owner.delete(
        f"/api/v1/membership-plans/{plan_id}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_del1.status_code == 204, r_del1.text

    r_del2 = await authed_client_owner.delete(
        f"/api/v1/membership-plans/{plan_id}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_del2.status_code == 404
    assert r_del2.json()["code"] == "plan_not_found"


async def test_delete_frees_unique_name_slot(
    authed_client_owner: AsyncClient,
) -> None:
    """D-16: soft-delete frees the partial-unique name slot so the same name
    can be reused for a new alive plan.

    POST "Базовый" -> DELETE -> POST "Базовый" again -> 201 with a new id.
    """
    first = await _create(authed_client_owner, name="Базовый")
    first_id = first["id"]

    r_del = await authed_client_owner.delete(
        f"/api/v1/membership-plans/{first_id}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_del.status_code == 204, r_del.text

    second = await _create(authed_client_owner, name="Базовый")
    assert second["id"] != first_id, "new plan must have a different id"
    assert second["name"] == "Базовый"
