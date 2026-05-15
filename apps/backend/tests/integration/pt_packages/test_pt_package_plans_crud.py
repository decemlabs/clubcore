"""Integration tests for /api/v1/pt-package-plans CRUD (Phase 33 PT-02 / D-33-06..08).

Each test owns its DB state via the SAVEPOINT-rolled ``db_session`` fixture
and exercises the full route → service → repository → DB chain through
httpx ASGITransport.

Marquee tests:
  - test_create_pt_package_plan_owner_happy_path — 201 + audit_log row
  - test_update_pt_package_plan_session_count_409_field_immutable (D-33-07)
  - test_update_pt_package_plan_price_kopecks_409_field_immutable (D-33-07)
  - test_update_pt_package_plan_validity_days_409_field_immutable (D-33-07)
  - test_archive_pt_package_plan_in_use_409 (D-33-08 — pre-flight guard)
  - test_create_pt_package_plan_duplicate_name_case_insensitive_409 (partial UNIQUE)
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.clients.models import Client
from app.modules.pt_packages.models import PtPackagePlan


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf", "")}


VALID_PLAN: dict[str, Any] = {
    "name": "10 тренировок",
    "sessionCount": 10,
    "priceKopecks": 500000,
    "validityDays": 90,
}


async def _create(
    authed_client_owner: AsyncClient,
    **overrides: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {**VALID_PLAN, **overrides}
    r = await authed_client_owner.post(
        "/api/v1/pt-package-plans",
        json=payload,
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


# ---------------------------------------------------------------------------
# CREATE — owner happy path / null validity / reception 403 / duplicate-name 409
# ---------------------------------------------------------------------------


async def test_create_pt_package_plan_owner_happy_path(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """PT-02 happy path: 201 + ResponseEnvelope + audit_log row."""
    r = await authed_client_owner.post(
        "/api/v1/pt-package-plans",
        json=VALID_PLAN,
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert "data" in body
    data = body["data"]
    UUID(data["id"])
    assert data["name"] == "10 тренировок"
    assert data["sessionCount"] == 10
    assert data["priceKopecks"] == 500000
    assert data["validityDays"] == 90
    assert "createdAt" in data
    assert "updatedAt" in data

    plan_id = UUID(data["id"])
    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "pt_package_plan_created",
                AuditLog.resource_id == plan_id,
            )
        )
    ).all()
    assert len(rows) == 1
    payload = rows[0].payload
    # D-33-15: PtPackagePlanCreatedPayload extra='forbid'.
    assert set(payload.keys()) == {
        "plan_id",
        "name",
        "session_count",
        "price_kopecks",
        "validity_days",
    }
    assert payload["session_count"] == 10
    assert payload["validity_days"] == 90


async def test_create_pt_package_plan_validity_null_ok(
    authed_client_owner: AsyncClient,
) -> None:
    """validityDays may be omitted (NULL) — бессрочный package."""
    payload = {k: v for k, v in VALID_PLAN.items() if k != "validityDays"}
    r = await authed_client_owner.post(
        "/api/v1/pt-package-plans",
        json=payload,
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    assert r.json()["data"]["validityDays"] is None


async def test_create_pt_package_plan_reception_403(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Owner-only: reception POST → 403 + no audit_log row."""
    r = await authed_client_reception.post(
        "/api/v1/pt-package-plans",
        json=VALID_PLAN,
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 403, r.text
    # No pt_package_plan_created audit row should exist for this plan.
    rows = (
        await db_session.scalars(
            select(AuditLog).where(AuditLog.action == "pt_package_plan_created")
        )
    ).all()
    assert len(rows) == 0


async def test_create_pt_package_plan_duplicate_name_alive_409(
    authed_client_owner: AsyncClient,
) -> None:
    """D-33-02: duplicate alive name → 409 pt_package_plan_name_conflict."""
    await _create(authed_client_owner, name="Package X")
    r = await authed_client_owner.post(
        "/api/v1/pt-package-plans",
        json={**VALID_PLAN, "name": "Package X"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "pt_package_plan_name_conflict"


async def test_create_pt_package_plan_duplicate_name_case_insensitive_409(
    authed_client_owner: AsyncClient,
) -> None:
    """D-33-02: lower(name) partial unique catches case-variant duplicates."""
    await _create(authed_client_owner, name="10 тренировок")
    r = await authed_client_owner.post(
        "/api/v1/pt-package-plans",
        json={**VALID_PLAN, "name": "10 ТРЕНИРОВОК"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "pt_package_plan_name_conflict"


async def test_create_pt_package_plan_duplicate_name_after_archive_ok(
    authed_client_owner: AsyncClient,
) -> None:
    """D-33-02: partial UNIQUE WHERE deleted_at IS NULL frees the name slot on archive."""
    first = await _create(authed_client_owner, name="Reusable")
    r_del = await authed_client_owner.delete(
        f"/api/v1/pt-package-plans/{first['id']}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_del.status_code == 204
    second = await _create(authed_client_owner, name="Reusable")
    assert second["id"] != first["id"]


async def test_create_pt_package_plan_invalid_session_count_422(
    authed_client_owner: AsyncClient,
) -> None:
    """Schema-layer 422 on session_count=0 (Field(ge=1))."""
    r = await authed_client_owner.post(
        "/api/v1/pt-package-plans",
        json={**VALID_PLAN, "sessionCount": 0},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 422, r.text


async def test_create_pt_package_plan_extra_field_422(
    authed_client_owner: AsyncClient,
) -> None:
    """BackendSchemaBase extra='forbid': unknown field rejected with 422."""
    r = await authed_client_owner.post(
        "/api/v1/pt-package-plans",
        json={**VALID_PLAN, "foo": "bar"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 422, r.text


# ---------------------------------------------------------------------------
# LIST + GET
# ---------------------------------------------------------------------------


async def test_list_pt_package_plans_owner(
    authed_client_owner: AsyncClient,
) -> None:
    """PT-02 list: alive plans only by default."""
    await _create(authed_client_owner, name="L1")
    await _create(authed_client_owner, name="L2")
    r = await authed_client_owner.get("/api/v1/pt-package-plans")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["total"] >= 2
    names = [item["name"] for item in data["items"]]
    assert "L1" in names
    assert "L2" in names


async def test_list_pt_package_plans_include_archived(
    authed_client_owner: AsyncClient,
) -> None:
    """?includeArchived=true returns soft-deleted rows as well."""
    p1 = await _create(authed_client_owner, name="A1")
    p2 = await _create(authed_client_owner, name="A2")

    # Archive A1
    r_del = await authed_client_owner.delete(
        f"/api/v1/pt-package-plans/{p1['id']}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_del.status_code == 204

    # Default list — A1 excluded.
    r_default = await authed_client_owner.get("/api/v1/pt-package-plans")
    default_ids = {item["id"] for item in r_default.json()["data"]["items"]}
    assert p1["id"] not in default_ids
    assert p2["id"] in default_ids

    # Include-archived — both visible.
    r_all = await authed_client_owner.get(
        "/api/v1/pt-package-plans?includeArchived=true"
    )
    all_ids = {item["id"] for item in r_all.json()["data"]["items"]}
    assert p1["id"] in all_ids
    assert p2["id"] in all_ids


async def test_get_pt_package_plan_owner(
    authed_client_owner: AsyncClient,
) -> None:
    """GET /{id}: 200 envelope with the same data as POST."""
    created = await _create(authed_client_owner)
    r = await authed_client_owner.get(f"/api/v1/pt-package-plans/{created['id']}")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["id"] == created["id"]
    assert data["sessionCount"] == created["sessionCount"]


async def test_get_pt_package_plan_not_found_404(
    authed_client_owner: AsyncClient,
) -> None:
    """GET with random UUID → 404 pt_package_plan_not_found."""
    r = await authed_client_owner.get(
        "/api/v1/pt-package-plans/00000000-0000-0000-0000-000000000000"
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "pt_package_plan_not_found"


# ---------------------------------------------------------------------------
# PATCH — happy path / 3x field_immutable 409 / no-op / reception 403
# ---------------------------------------------------------------------------


async def test_update_pt_package_plan_name_owner_happy_path(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """PATCH name updates the row + emits pt_package_plan_updated audit event."""
    created = await _create(authed_client_owner, name="Before")
    plan_id = UUID(created["id"])

    r = await authed_client_owner.patch(
        f"/api/v1/pt-package-plans/{plan_id}",
        json={"name": "After"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["name"] == "After"

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "pt_package_plan_updated",
                AuditLog.resource_id == plan_id,
            )
        )
    ).all()
    assert len(rows) == 1
    payload = rows[0].payload
    assert set(payload.keys()) == {"plan_id", "changed_fields"}
    assert payload["changed_fields"] == ["name"]


async def test_update_pt_package_plan_session_count_409_field_immutable(
    authed_client_owner: AsyncClient,
) -> None:
    """D-33-07: PATCH sessionCount → 409 field_immutable with fields.field=session_count."""
    created = await _create(authed_client_owner)
    r = await authed_client_owner.patch(
        f"/api/v1/pt-package-plans/{created['id']}",
        json={"sessionCount": 15},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    body = r.json()
    assert body["code"] == "field_immutable"
    assert body["fields"] == {"field": "session_count"}


async def test_update_pt_package_plan_price_kopecks_409_field_immutable(
    authed_client_owner: AsyncClient,
) -> None:
    """D-33-07: PATCH priceKopecks → 409 field_immutable."""
    created = await _create(authed_client_owner)
    r = await authed_client_owner.patch(
        f"/api/v1/pt-package-plans/{created['id']}",
        json={"priceKopecks": 999999},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    body = r.json()
    assert body["code"] == "field_immutable"
    assert body["fields"] == {"field": "price_kopecks"}


async def test_update_pt_package_plan_validity_days_409_field_immutable(
    authed_client_owner: AsyncClient,
) -> None:
    """D-33-07: PATCH validityDays → 409 field_immutable."""
    created = await _create(authed_client_owner)
    r = await authed_client_owner.patch(
        f"/api/v1/pt-package-plans/{created['id']}",
        json={"validityDays": 180},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    body = r.json()
    assert body["code"] == "field_immutable"
    assert body["fields"] == {"field": "validity_days"}


async def test_update_pt_package_plan_session_count_same_value_ok(
    authed_client_owner: AsyncClient,
) -> None:
    """PATCH with a matching immutable value (no-op) → 200, no error."""
    created = await _create(authed_client_owner)
    r = await authed_client_owner.patch(
        f"/api/v1/pt-package-plans/{created['id']}",
        json={"sessionCount": VALID_PLAN["sessionCount"]},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text


async def test_update_pt_package_plan_idempotent_noop_does_not_emit_audit(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Empty PATCH (no fields → no change) does not emit pt_package_plan_updated."""
    created = await _create(authed_client_owner)
    plan_id = UUID(created["id"])
    r = await authed_client_owner.patch(
        f"/api/v1/pt-package-plans/{plan_id}",
        json={},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text
    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "pt_package_plan_updated",
                AuditLog.resource_id == plan_id,
            )
        )
    ).all()
    assert len(rows) == 0


async def test_update_pt_package_plan_reception_403(
    authed_client_reception: AsyncClient,
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """Reception PATCH → 403 (EDIT, PT_PACKAGE_PLANS) in OWNER_ONLY."""
    plan = await make_pt_package_plan()
    r = await authed_client_reception.patch(
        f"/api/v1/pt-package-plans/{plan.id}",
        json={"name": "Reception cannot edit"},
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 403, r.text


async def test_update_pt_package_plan_extra_field_422(
    authed_client_owner: AsyncClient,
) -> None:
    """BackendSchemaBase extra='forbid' on PATCH body."""
    created = await _create(authed_client_owner)
    r = await authed_client_owner.patch(
        f"/api/v1/pt-package-plans/{created['id']}",
        json={"foo": "bar"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 422, r.text


# ---------------------------------------------------------------------------
# DELETE — happy path / in_use 409 / reception 403 / idempotent 404
# ---------------------------------------------------------------------------


async def test_archive_pt_package_plan_owner_happy_path(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """DELETE returns 204 + emits pt_package_plan_archived audit row."""
    created = await _create(authed_client_owner)
    plan_id = UUID(created["id"])
    r = await authed_client_owner.delete(
        f"/api/v1/pt-package-plans/{plan_id}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 204, r.text
    assert r.content == b""

    # Confirm the row was soft-deleted (deleted_at IS NOT NULL).
    refreshed = await db_session.get(PtPackagePlan, plan_id)
    assert refreshed is not None
    assert refreshed.deleted_at is not None

    # Audit event landed with the locked payload shape.
    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "pt_package_plan_archived",
                AuditLog.resource_id == plan_id,
            )
        )
    ).all()
    assert len(rows) == 1
    assert set(rows[0].payload.keys()) == {"plan_id"}


async def test_archive_pt_package_plan_in_use_409(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package: Callable[..., Any],
) -> None:
    """D-33-08: DELETE on a plan with at least one pt_packages row → 409 plan_in_use.

    Plan is NOT archived (deleted_at remains NULL).
    """
    plan = await make_pt_package_plan(name="In-Use Plan")
    client = await make_client()
    await make_pt_package(client_id=client.id, plan=plan)

    r = await authed_client_owner.delete(
        f"/api/v1/pt-package-plans/{plan.id}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "plan_in_use"

    # Plan must remain alive (deleted_at NULL).
    refreshed = await db_session.get(PtPackagePlan, plan.id)
    assert refreshed is not None
    assert refreshed.deleted_at is None


async def test_archive_pt_package_plan_reception_403(
    authed_client_reception: AsyncClient,
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """Reception DELETE → 403 (DELETE, PT_PACKAGE_PLANS) in OWNER_ONLY."""
    plan = await make_pt_package_plan()
    r = await authed_client_reception.delete(
        f"/api/v1/pt-package-plans/{plan.id}",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 403, r.text


async def test_archive_pt_package_plan_idempotent_404(
    authed_client_owner: AsyncClient,
) -> None:
    """Second DELETE on an already-archived plan → 404 (alive filter)."""
    created = await _create(authed_client_owner)
    plan_id = created["id"]

    r1 = await authed_client_owner.delete(
        f"/api/v1/pt-package-plans/{plan_id}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r1.status_code == 204

    r2 = await authed_client_owner.delete(
        f"/api/v1/pt-package-plans/{plan_id}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r2.status_code == 404
    assert r2.json()["code"] == "pt_package_plan_not_found"


async def test_get_archived_pt_package_plan_404(
    authed_client_owner: AsyncClient,
) -> None:
    """GET on a soft-deleted plan returns 404 (alive-only repository filter)."""
    created = await _create(authed_client_owner)
    plan_id = created["id"]
    r_del = await authed_client_owner.delete(
        f"/api/v1/pt-package-plans/{plan_id}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_del.status_code == 204

    r_get = await authed_client_owner.get(f"/api/v1/pt-package-plans/{plan_id}")
    assert r_get.status_code == 404
    assert r_get.json()["code"] == "pt_package_plan_not_found"
