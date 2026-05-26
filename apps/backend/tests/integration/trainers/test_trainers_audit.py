"""Integration tests asserting audit_log DB rows for trainer events (TRN-07, D-31-16..D-31-18).

Each test exercises a trainers route via the authed httpx client, then
queries the SAVEPOINT-rolled `db_session` for the corresponding
`AuditLog` rows. Assertions cover locked payload schemas per Phase 30 audit_payloads.py.

All 4 locked event types covered:
  - trainer_created: {trainer_id, full_name, phone} (TrainerCreatedPayload)
  - trainer_deactivated: {trainer_id} (TrainerDeactivatedPayload)
  - trainer_reactivated: {trainer_id} (TrainerReactivatedPayload)
  - trainer_updated: {trainer_id, changed_fields} (TrainerUpdatedPayload)
"""

from __future__ import annotations

from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.auth.models import User
from tests.integration.trainers.conftest import _create, _csrf_headers


async def test_trainer_created_writes_audit_row(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    """TRN-07: trainer_created row carries locked TrainerCreatedPayload shape."""
    created = await _create(authed_client_owner, phone="+79990002001")
    trainer_id = UUID(created["id"])

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "trainer_created",
                AuditLog.resource_id == trainer_id,
            )
        )
    ).all()
    assert len(rows) == 1, f"expected exactly 1 row, got {len(rows)}"
    row = rows[0]
    assert row.actor_user_id == seeded_owner.id
    assert row.resource_type == "trainer"
    assert row.resource_id == trainer_id

    payload = row.payload
    # TrainerCreatedPayload: {trainer_id, full_name, phone}
    assert payload["trainer_id"] == str(trainer_id)
    assert isinstance(payload["full_name"], str) and payload["full_name"]
    assert "phone" in payload  # phone may be None but key must be present
    assert payload["phone"] == "+79990002001"


async def test_trainer_created_with_null_phone_includes_phone_key(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """TrainerCreatedPayload requires phone kwarg even when None (D-31-16)."""
    r = await authed_client_owner.post(
        "/api/v1/trainers",
        json={"fullName": "Без Телефона"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    trainer_id = UUID(r.json()["data"]["id"])

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "trainer_created",
                AuditLog.resource_id == trainer_id,
            )
        )
    ).all()
    assert len(rows) == 1
    payload = rows[0].payload
    assert "phone" in payload
    assert payload["phone"] is None


async def test_trainer_deactivated_writes_audit_row(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """TRN-07: trainer_deactivated row has only {trainer_id} per TrainerDeactivatedPayload."""
    created = await _create(authed_client_owner, phone="+79990002002")
    trainer_id = UUID(created["id"])

    r = await authed_client_owner.patch(
        f"/api/v1/trainers/{created['id']}",
        json={"isActive": False},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "trainer_deactivated",
                AuditLog.resource_id == trainer_id,
            )
        )
    ).all()
    assert len(rows) == 1
    payload = rows[0].payload
    # TrainerDeactivatedPayload has only trainer_id
    assert payload["trainer_id"] == str(trainer_id)
    # No trainer_updated event should exist (is_active only flip)
    updated_rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "trainer_updated",
                AuditLog.resource_id == trainer_id,
            )
        )
    ).all()
    assert len(updated_rows) == 0, "pure deactivate must NOT emit trainer_updated"


async def test_trainer_reactivated_writes_audit_row(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """TRN-07: deactivate then reactivate; assert exactly one trainer_reactivated row."""
    created = await _create(authed_client_owner, phone="+79990002003")
    trainer_id = UUID(created["id"])

    # Deactivate
    await authed_client_owner.patch(
        f"/api/v1/trainers/{created['id']}",
        json={"isActive": False},
        headers=_csrf_headers(authed_client_owner),
    )

    # Reactivate
    r = await authed_client_owner.patch(
        f"/api/v1/trainers/{created['id']}",
        json={"isActive": True},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "trainer_reactivated",
                AuditLog.resource_id == trainer_id,
            )
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].payload["trainer_id"] == str(trainer_id)


async def test_trainer_updated_writes_audit_with_changed_fields(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """TRN-07: PATCH fullName-only → trainer_updated with changed_fields=['full_name']."""
    created = await _create(authed_client_owner, phone="+79990002004")
    trainer_id = UUID(created["id"])

    r = await authed_client_owner.patch(
        f"/api/v1/trainers/{created['id']}",
        json={"fullName": "Новое Имя"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "trainer_updated",
                AuditLog.resource_id == trainer_id,
            )
        )
    ).all()
    assert len(rows) == 1
    payload = rows[0].payload
    # TrainerUpdatedPayload: {trainer_id, changed_fields} — snake_case, sorted
    assert payload["trainer_id"] == str(trainer_id)
    assert payload["changed_fields"] == ["full_name"]


async def test_trainer_combined_patch_emits_two_events(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """D-31-12: PATCH {fullName, isActive=false} on active trainer → both trainer_deactivated
    AND trainer_updated rows; trainer_updated.changed_fields == ['full_name'] (not is_active).
    """
    created = await _create(authed_client_owner, phone="+79990002005")
    trainer_id = UUID(created["id"])

    r = await authed_client_owner.patch(
        f"/api/v1/trainers/{created['id']}",
        json={"fullName": "Другое Имя", "isActive": False},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text

    # trainer_deactivated row must exist
    deact_rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "trainer_deactivated",
                AuditLog.resource_id == trainer_id,
            )
        )
    ).all()
    assert len(deact_rows) == 1

    # trainer_updated row must exist for full_name change only
    upd_rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "trainer_updated",
                AuditLog.resource_id == trainer_id,
            )
        )
    ).all()
    assert len(upd_rows) == 1
    assert upd_rows[0].payload["changed_fields"] == ["full_name"]  # NOT is_active


async def test_trainer_noop_patch_emits_no_audit(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """D-31-12: PATCH with unchanged fullName → AuditLog count stays at 1 (only trainer_created)."""
    created = await _create(authed_client_owner, phone="+79990002006", full_name="Без Изменений")
    trainer_id = UUID(created["id"])

    r = await authed_client_owner.patch(
        f"/api/v1/trainers/{created['id']}",
        json={"fullName": "Без Изменений"},  # same as current
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text

    all_rows = (
        await db_session.scalars(select(AuditLog).where(AuditLog.resource_id == trainer_id))
    ).all()
    assert len(all_rows) == 1, "no-op PATCH must not emit additional audit rows"
    assert all_rows[0].action == "trainer_created"
