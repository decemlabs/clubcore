"""Integration tests for recurring slot template CRUD (Phase 59 REC-01, REC-04).

Covers:
  1. POST /recurring-templates — owner creates template → 201
  2. POST /recurring-templates duplicate (trainer,dow,start,valid_from) → 409
  3. GET /recurring-templates — owner sees list (200, paginated)
  4. GET /recurring-templates — reception sees list (200, paginated) — REC-04 both-role
  5. POST /recurring-templates — reception 403
  6. POST /recurring-templates/{id}/deactivate — owner deactivates → 200 is_active=false
  7. POST /recurring-templates/{id}/deactivate — reception 403
  8. audit emit: recurring_slot_template_created and recurring_slot_template_cancelled
"""

from __future__ import annotations

from datetime import UTC, datetime, time
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.auth.models import User
from app.modules.schedule.models import RecurringSlotTemplate
from app.modules.trainers.models import Trainer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _template_body(trainer: Trainer, *, dow: int = 0) -> dict:
    return {
        "trainerId": str(trainer.id),
        "dayOfWeek": dow,
        "startTime": "10:00:00",
        "endTime": "11:00:00",
        "validFrom": datetime.now(UTC).date().isoformat(),
        "validUntil": None,
    }


# ---------------------------------------------------------------------------
# 1. Owner create → 201
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_owner_create_recurring_template_returns_201(
    authed_client_owner: AsyncClient,
    make_trainer,
) -> None:
    trainer = await make_trainer()
    csrf = authed_client_owner.cookies.get("clubcore_csrf") or ""
    r = await authed_client_owner.post(
        "/api/v1/recurring-templates",
        json=_template_body(trainer),
        headers={
            "X-CSRF-Token": csrf,
            "Idempotency-Key": f"rec-create-{uuid4()}",
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["data"]["isActive"] is True
    assert data["data"]["dayOfWeek"] == 0
    assert data["data"]["startTime"] == "10:00:00"


# ---------------------------------------------------------------------------
# 2. Duplicate (trainer, dow, start, valid_from) → 409
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_duplicate_recurring_template_returns_409(
    authed_client_owner: AsyncClient,
    make_trainer,
) -> None:
    trainer = await make_trainer()
    csrf = authed_client_owner.cookies.get("clubcore_csrf") or ""

    r1 = await authed_client_owner.post(
        "/api/v1/recurring-templates",
        json=_template_body(trainer, dow=1),
        headers={
            "X-CSRF-Token": csrf,
            "Idempotency-Key": f"rec-dup-{uuid4()}-a",
        },
    )
    assert r1.status_code == 201, r1.text

    r2 = await authed_client_owner.post(
        "/api/v1/recurring-templates",
        json=_template_body(trainer, dow=1),
        headers={
            "X-CSRF-Token": csrf,
            "Idempotency-Key": f"rec-dup-{uuid4()}-b",
        },
    )
    assert r2.status_code == 409, r2.text
    assert r2.json()["code"] == "recurring_template_duplicate"


# ---------------------------------------------------------------------------
# 3. Owner list → 200 paginated envelope
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_owner_list_recurring_templates_paginated(
    authed_client_owner: AsyncClient,
    make_trainer,
) -> None:
    trainer = await make_trainer()
    csrf = authed_client_owner.cookies.get("clubcore_csrf") or ""

    await authed_client_owner.post(
        "/api/v1/recurring-templates",
        json=_template_body(trainer, dow=2),
        headers={
            "X-CSRF-Token": csrf,
            "Idempotency-Key": f"rec-list-create-{uuid4()}",
        },
    )

    r = await authed_client_owner.get(
        "/api/v1/recurring-templates",
        params={"trainerId": str(trainer.id)},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["data"]["total"] >= 1
    assert isinstance(body["data"]["items"], list)
    assert body["data"]["items"][0]["trainerId"] == str(trainer.id)


# ---------------------------------------------------------------------------
# 4. Reception list → 200 (REC-04 both roles)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reception_can_list_recurring_templates(
    authed_client_reception: AsyncClient,
    make_trainer,
) -> None:
    trainer = await make_trainer()
    r = await authed_client_reception.get(
        "/api/v1/recurring-templates",
        params={"trainerId": str(trainer.id)},
    )
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# 5. Reception create → 403
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reception_create_recurring_template_forbidden(
    authed_client_reception: AsyncClient,
    make_trainer,
) -> None:
    trainer = await make_trainer()
    csrf = authed_client_reception.cookies.get("clubcore_csrf") or ""
    r = await authed_client_reception.post(
        "/api/v1/recurring-templates",
        json=_template_body(trainer, dow=3),
        headers={
            "X-CSRF-Token": csrf,
            "Idempotency-Key": f"rec-recep-{uuid4()}",
        },
    )
    assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# 6. Owner deactivate → 200, is_active=False
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_owner_deactivate_recurring_template(
    authed_client_owner: AsyncClient,
    make_trainer,
) -> None:
    trainer = await make_trainer()
    csrf = authed_client_owner.cookies.get("clubcore_csrf") or ""

    create_r = await authed_client_owner.post(
        "/api/v1/recurring-templates",
        json=_template_body(trainer, dow=4),
        headers={
            "X-CSRF-Token": csrf,
            "Idempotency-Key": f"rec-deact-create-{uuid4()}",
        },
    )
    assert create_r.status_code == 201, create_r.text
    template_id = create_r.json()["data"]["id"]

    deact_r = await authed_client_owner.post(
        f"/api/v1/recurring-templates/{template_id}/deactivate",
        headers={
            "X-CSRF-Token": csrf,
            "Idempotency-Key": f"rec-deact-{uuid4()}",
        },
    )
    assert deact_r.status_code == 200, deact_r.text
    assert deact_r.json()["data"]["isActive"] is False


# ---------------------------------------------------------------------------
# 7. Reception deactivate → 403
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reception_deactivate_recurring_template_forbidden(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
) -> None:
    trainer = await make_trainer()
    # Seed a template directly via DB for isolation.
    tmpl = RecurringSlotTemplate(
        trainer_id=trainer.id,
        day_of_week=5,
        start_time=time(9, 0),
        end_time=time(10, 0),
        valid_from=datetime.now(UTC).date(),
        is_active=True,
    )
    db_session.add(tmpl)
    await db_session.commit()
    await db_session.refresh(tmpl)

    csrf = authed_client_reception.cookies.get("clubcore_csrf") or ""
    r = await authed_client_reception.post(
        f"/api/v1/recurring-templates/{tmpl.id}/deactivate",
        headers={
            "X-CSRF-Token": csrf,
            "Idempotency-Key": f"rec-deact-recep-{uuid4()}",
        },
    )
    assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# 8. Audit events: recurring_slot_template_created + recurring_slot_template_cancelled
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_events_emitted_on_create_and_deactivate(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_trainer,
) -> None:
    trainer = await make_trainer()
    csrf = authed_client_owner.cookies.get("clubcore_csrf") or ""

    create_r = await authed_client_owner.post(
        "/api/v1/recurring-templates",
        json=_template_body(trainer, dow=6),
        headers={
            "X-CSRF-Token": csrf,
            "Idempotency-Key": f"rec-audit-create-{uuid4()}",
        },
    )
    assert create_r.status_code == 201, create_r.text
    template_id = create_r.json()["data"]["id"]

    created_audit = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "recurring_slot_template_created",
                )
            )
        )
        .scalars()
        .all()
    )
    assert any(str(a.resource_id) == template_id for a in created_audit), (
        "recurring_slot_template_created audit not found"
    )

    deact_r = await authed_client_owner.post(
        f"/api/v1/recurring-templates/{template_id}/deactivate",
        headers={
            "X-CSRF-Token": csrf,
            "Idempotency-Key": f"rec-audit-deact-{uuid4()}",
        },
    )
    assert deact_r.status_code == 200, deact_r.text

    cancelled_audit = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "recurring_slot_template_cancelled",
                )
            )
        )
        .scalars()
        .all()
    )
    assert any(str(a.resource_id) == template_id for a in cancelled_audit), (
        "recurring_slot_template_cancelled audit not found"
    )
