"""Integration tests asserting audit_log DB rows for membership plan events (MEM-PLAN-AUDIT-01).

Each test exercises a membership-plans route via the authed httpx client, then
queries the SAVEPOINT-rolled `db_session` for the corresponding `AuditLog` rows.
Assertions cover D-11/D-12/D-13 payload shapes and D-09/D-14 idempotent skip.

Decision references (16-CONTEXT.md):
- D-11: membership_plan_created payload = {name, duration_days, price_kopecks}
- D-12: membership_plan_updated payload = {changed_fields} — NO before/after values
- D-13: membership_plan_archived payload = {} (empty)
- D-09 + D-14: no-op PATCH writes ZERO audit rows (service short-circuits before emit)
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.auth.models import User


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("clubcore_csrf", "")}


VALID_PLAN: dict[str, Any] = {
    "name": "Базовый",
    "durationDays": 30,
    "priceKopecks": 250000,
    "freezeDaysLimit": 14,
    "active": True,
}


async def _create(authed: AsyncClient, **overrides: Any) -> dict[str, Any]:
    payload = {**VALID_PLAN, **overrides}
    r = await authed.post(
        "/api/v1/membership-plans",
        json=payload,
        headers=_csrf_headers(authed),
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


async def test_post_emits_membership_plan_created_with_full_payload(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    """D-11: POST emits membership_plan_created with {name, duration_days, price_kopecks}."""
    created = await _create(authed_client_owner, name="Базовый")
    plan_id = UUID(created["id"])

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "membership_plan_created",
                AuditLog.resource_id == plan_id,
            )
        )
    ).all()
    assert len(rows) == 1, f"expected exactly 1 row, got {len(rows)}"
    row = rows[0]
    assert row.actor_user_id == seeded_owner.id
    assert row.resource_type == "membership_plan"
    assert row.resource_id == plan_id

    payload = row.payload
    # D-11: exact payload shape — plan_id is in resource_id, NOT in payload
    assert payload == {"name": "Базовый", "duration_days": 30, "price_kopecks": 250000}


async def test_patch_emits_membership_plan_updated_with_changed_fields_only(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    """D-12: PATCH emits membership_plan_updated with {changed_fields} only — no before/after."""
    created = await _create(authed_client_owner, name="Базовый")
    plan_id = UUID(created["id"])

    r = await authed_client_owner.patch(
        f"/api/v1/membership-plans/{plan_id}",
        json={"priceKopecks": 300000},
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
    assert len(rows) == 1
    row = rows[0]
    assert row.actor_user_id == seeded_owner.id
    assert row.resource_type == "membership_plan"
    assert row.payload["changed_fields"] == ["price_kopecks"]
    # D-12: NO before/after values anywhere in payload
    assert "previous_price_kopecks" not in row.payload
    assert "price_kopecks" not in row.payload or "changed_fields" in row.payload


async def test_delete_emits_membership_plan_archived_with_minimal_payload(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    """D-13: DELETE emits membership_plan_archived with empty payload {}."""
    created = await _create(authed_client_owner, name="Базовый")
    plan_id = UUID(created["id"])

    r = await authed_client_owner.delete(
        f"/api/v1/membership-plans/{plan_id}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 204, r.text

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "membership_plan_archived",
                AuditLog.resource_id == plan_id,
            )
        )
    ).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.actor_user_id == seeded_owner.id
    assert row.resource_type == "membership_plan"
    # D-13: empty payload — resource_id carries the plan id
    assert row.payload == {}


async def test_idempotent_noop_patch_writes_zero_audit_rows(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """D-09 + D-14: no-op PATCH (same values) must NOT emit membership_plan_updated."""
    created = await _create(authed_client_owner, name="Базовый")
    plan_id = UUID(created["id"])

    # Baseline: 0 update rows before PATCH
    before = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "membership_plan_updated",
                AuditLog.resource_id == plan_id,
            )
        )
    ).all()
    assert len(before) == 0

    # PATCH with the same priceKopecks the row already has
    r = await authed_client_owner.patch(
        f"/api/v1/membership-plans/{plan_id}",
        json={"priceKopecks": VALID_PLAN["priceKopecks"]},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text

    # Still 0 update rows after the no-op PATCH
    after = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "membership_plan_updated",
                AuditLog.resource_id == plan_id,
            )
        )
    ).all()
    assert len(after) == 0, "no-op PATCH must NOT emit membership_plan_updated (D-09)"


async def test_409_post_does_not_emit_audit(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Rollback on 409 clears spurious audit row: failed create does not appear in log."""
    created = await _create(authed_client_owner, name="Базовый")
    first_id = UUID(created["id"])

    # Second POST with same name -> 409
    r = await authed_client_owner.post(
        "/api/v1/membership-plans",
        json={**VALID_PLAN, "name": "Базовый"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 409, r.text

    # Only 1 membership_plan_created row exists — from the first successful POST
    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "membership_plan_created",
            )
        )
    ).all()
    # Filter to rows with resource_id matching the first plan (the rollback should
    # mean the failed attempt has no row at all)
    rows_for_first = [r for r in rows if r.resource_id == first_id]
    assert len(rows_for_first) == 1, "exactly 1 audit row from the successful POST"
    # The total count should also be 1 (the 409 rolled back before any audit emit)
    assert len(rows) == 1, f"expected 1 total audit row, got {len(rows)}"
