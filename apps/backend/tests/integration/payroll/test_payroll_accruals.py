"""Integration tests for POST /api/v1/payroll/accruals + POST /{id}/mark-paid (Phase 58 PAY-03/04).

Coverage:
  - POST /accruals 201: snapshot fields + status 'pending' + accrued_at set.
  - Duplicate period (same trainer+start+end) → 409 payroll_period_already_run.
  - No config → 422 comp_config_missing.
  - Both-NULL config → 422 comp_config_missing.
  - Snapshot immutability: PUT new comp config after accrual; accrual snapshots unchanged.
  - POST ./{id}/mark-paid 200 → status 'paid', paid_at + paid_by_user_id set.
  - Second mark-paid → 409 already_paid.
  - Reception receives 403 on POST /accruals.
  - Reception receives 403 on POST /accruals/{id}/mark-paid.
  - audit_log has payroll_accrual_created row after create.
  - audit_log has payroll_accrual_paid row after mark-paid.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.models import Client
from app.modules.payments.models import Payment
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.pt_sessions.models import PtSession

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PERIOD_START = "2026-04-01"
PERIOD_END = "2026-04-30"
# A performed_at within the period, in Europe/Moscow tz (UTC+3)
PERFORMED_AT = datetime(2026, 4, 15, 10, 0, 0, tzinfo=UTC)


def _csrf(client: AsyncClient) -> dict[str, str]:
    """Return the X-CSRF-Token header from the client's cookie jar."""
    token: str = client.cookies.get("sportzal_csrf") or ""
    return {"X-CSRF-Token": token}


async def _seed_pt_data(
    db_session: AsyncSession,
    *,
    trainer_id: UUID,
    sale_amount_kopecks: int,
    session_count: int = 1,
    user_id: UUID,
) -> None:
    """Seed a pt_package_plan, pt_package, N pt_sessions, and a payment via ORM.

    Uses ORM models from other modules — this is ALLOWED in test code; only
    payroll/repository.py is forbidden from cross-module ORM imports (D-58-19).
    """
    client = Client(
        last_name="Тестов",
        first_name="Тест",
        phone=f"+7999{uuid4().hex[:7]}",
        created_by_user_id=user_id,
    )
    db_session.add(client)
    await db_session.flush()

    plan = PtPackagePlan(
        name=f"Тест-план-{uuid4().hex[:4]}",
        session_count=10,
        price_kopecks=sale_amount_kopecks,
    )
    db_session.add(plan)
    await db_session.flush()

    pkg = PtPackage(
        client_id=client.id,
        trainer_id=trainer_id,
        plan_id=plan.id,
        plan_name_snapshot=plan.name,
        session_count_snapshot=plan.session_count,
        price_kopecks_snapshot=plan.price_kopecks,
        sessions_remaining=plan.session_count - session_count,
        status="active",
        start_date=date(2026, 4, 1),
    )
    db_session.add(pkg)
    await db_session.flush()

    for _ in range(session_count):
        sess = PtSession(
            pt_package_id=pkg.id,
            trainer_id=trainer_id,
            client_id=client.id,
            performed_at=PERFORMED_AT,
            performed_by_user_id=user_id,
            trainer_name_snapshot="Тренер Тест",
            cancelled_at=None,
        )
        db_session.add(sess)

    payment = Payment(
        subject_kind="pt_package",
        subject_id=pkg.id,
        amount_kopecks=sale_amount_kopecks,
        method="cash",
        received_at=PERFORMED_AT,
    )
    db_session.add(payment)
    await db_session.commit()


async def _count_audit_rows(
    db_session: AsyncSession,
    action: str,
    resource_type: str,
) -> int:
    """Return count of audit_log rows for a given (action, resource_type) pair."""
    row = (
        (
            await db_session.execute(
                sa.text(
                    "SELECT COUNT(*) AS cnt FROM audit_log "
                    "WHERE action = :action AND resource_type = :resource_type"
                ),
                {"action": action, "resource_type": resource_type},
            )
        )
        .mappings()
        .one()
    )
    return int(row["cnt"])


# ---------------------------------------------------------------------------
# PAY-03: POST /accruals
# ---------------------------------------------------------------------------


async def test_post_accrual_happy_path(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_comp_config: Any,
    db_session: AsyncSession,
    seeded_owner: Any,
) -> None:
    """POST /accruals returns 201 with snapshotted fields and status 'pending' (PAY-03)."""
    trainer = await make_trainer()
    config = await make_comp_config(
        trainer_id=trainer.id,
        commission_pct_bps=1000,
        session_fee_kopecks=50000,
        effective_from=date(2026, 1, 1),
    )
    await _seed_pt_data(
        db_session,
        trainer_id=trainer.id,
        sale_amount_kopecks=100000,
        session_count=2,
        user_id=seeded_owner.id,
    )

    r = await authed_client_owner.post(
        "/api/v1/payroll/accruals",
        json={
            "trainerId": str(trainer.id),
            "periodStart": PERIOD_START,
            "periodEnd": PERIOD_END,
        },
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]

    # Status and temporal fields (camelCase wire format via BackendSchemaBase)
    assert data["status"] == "pending"
    assert data.get("accruedAt") is not None

    # Snapshot fields match the config
    assert data.get("commissionPctBpsSnapshot") == config.commission_pct_bps
    assert data.get("sessionFeeKopecksSnapshot") == config.session_fee_kopecks
    assert data.get("compConfigIdSnapshot") == str(config.id)

    # Computed fields: sessions_count = 2, commission = ceil(100000 * 1000 / 10000) = 10000
    # fixed = 50000 * 2 = 100000; total = 110000
    assert data.get("sessionsCount") == 2
    assert data.get("accrualKopecks") == 110000

    # Paid fields are NULL on a fresh pending accrual
    assert data.get("paidAt") is None
    assert data.get("paidByUserId") is None


async def test_post_accrual_duplicate_period_returns_409(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_comp_config: Any,
    db_session: AsyncSession,
    seeded_owner: Any,
) -> None:
    """Duplicate period POST returns 409 payroll_period_already_run (PAY-03 D-58-06)."""
    trainer = await make_trainer()
    await make_comp_config(
        trainer_id=trainer.id,
        commission_pct_bps=1000,
        effective_from=date(2026, 1, 1),
    )
    await _seed_pt_data(
        db_session,
        trainer_id=trainer.id,
        sale_amount_kopecks=100000,
        user_id=seeded_owner.id,
    )

    body = {
        "trainerId": str(trainer.id),
        "periodStart": PERIOD_START,
        "periodEnd": PERIOD_END,
    }

    # First run succeeds
    r1 = await authed_client_owner.post(
        "/api/v1/payroll/accruals",
        json=body,
        headers=_csrf(authed_client_owner),
    )
    assert r1.status_code == 201, r1.text

    # Second run on same period → 409
    r2 = await authed_client_owner.post(
        "/api/v1/payroll/accruals",
        json=body,
        headers=_csrf(authed_client_owner),
    )
    assert r2.status_code == 409, r2.text
    assert r2.json()["code"] == "payroll_period_already_run"


async def test_post_accrual_no_config_returns_422(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
) -> None:
    """No comp config → 422 comp_config_missing on POST /accruals (PAY-03 D-58-07)."""
    trainer = await make_trainer()
    r = await authed_client_owner.post(
        "/api/v1/payroll/accruals",
        json={
            "trainerId": str(trainer.id),
            "periodStart": PERIOD_START,
            "periodEnd": PERIOD_END,
        },
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "comp_config_missing"


async def test_post_accrual_both_null_config_returns_422(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_comp_config: Any,
) -> None:
    """Both-NULL config → 422 comp_config_missing on POST /accruals (PAY-03 D-58-09)."""
    trainer = await make_trainer()
    await make_comp_config(
        trainer_id=trainer.id,
        commission_pct_bps=None,
        session_fee_kopecks=None,
        effective_from=date(2026, 1, 1),
    )
    r = await authed_client_owner.post(
        "/api/v1/payroll/accruals",
        json={
            "trainerId": str(trainer.id),
            "periodStart": PERIOD_START,
            "periodEnd": PERIOD_END,
        },
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "comp_config_missing"


async def test_post_accrual_snapshot_immutability(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_comp_config: Any,
    db_session: AsyncSession,
    seeded_owner: Any,
) -> None:
    """Snapshot columns are frozen at INSERT time; later config edits do not mutate them.

    D-58-03: The accrual row snapshots rate/config at run time. Editing the comp
    config AFTER accrual creation must NOT change the prior accrual's snapshot columns.
    """
    trainer = await make_trainer()
    original_config = await make_comp_config(
        trainer_id=trainer.id,
        commission_pct_bps=1000,
        session_fee_kopecks=None,
        effective_from=date(2026, 1, 1),
    )
    await _seed_pt_data(
        db_session,
        trainer_id=trainer.id,
        sale_amount_kopecks=100000,
        user_id=seeded_owner.id,
    )

    # Create accrual
    r_create = await authed_client_owner.post(
        "/api/v1/payroll/accruals",
        json={
            "trainerId": str(trainer.id),
            "periodStart": PERIOD_START,
            "periodEnd": PERIOD_END,
        },
        headers=_csrf(authed_client_owner),
    )
    assert r_create.status_code == 201, r_create.text
    accrual_data = r_create.json()["data"]
    accrual_id = accrual_data["id"]

    # Verify original snapshot
    assert accrual_data.get("commissionPctBpsSnapshot") == 1000

    # PUT a new comp config with different bps
    await authed_client_owner.put(
        f"/api/v1/payroll/trainer-configs/{trainer.id}",
        json={
            "commissionPctBps": 5000,  # changed from 1000 to 5000
            "sessionFeeKopecks": None,
            "effectiveFrom": "2026-02-01",
        },
        headers=_csrf(authed_client_owner),
    )

    # SELECT the existing accrual row directly and verify snapshot unchanged
    row = (
        (
            await db_session.execute(
                sa.text(
                    "SELECT commission_pct_bps_snapshot, comp_config_id_snapshot "
                    "FROM trainer_payroll_accruals WHERE id = :id"
                ),
                {"id": str(accrual_id)},
            )
        )
        .mappings()
        .one()
    )
    # Snapshot must still reflect the ORIGINAL config (1000 bps), not the new one (5000 bps)
    assert row["commission_pct_bps_snapshot"] == 1000
    assert str(row["comp_config_id_snapshot"]) == str(original_config.id)


async def test_post_accrual_reception_forbidden(
    authed_client_reception: AsyncClient,
    make_trainer: Any,
) -> None:
    """Reception receives 403 on POST /accruals (T-58-26 mitigate)."""
    trainer = await make_trainer()
    r = await authed_client_reception.post(
        "/api/v1/payroll/accruals",
        json={
            "trainerId": str(trainer.id),
            "periodStart": PERIOD_START,
            "periodEnd": PERIOD_END,
        },
        headers=_csrf(authed_client_reception),
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_post_accrual_audit_row_created(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_comp_config: Any,
    db_session: AsyncSession,
    seeded_owner: Any,
) -> None:
    """audit_log has a payroll_accrual_created row after POST /accruals (D-58-17 / T-58-29)."""
    trainer = await make_trainer()
    await make_comp_config(
        trainer_id=trainer.id,
        commission_pct_bps=1500,
        effective_from=date(2026, 1, 1),
    )
    await _seed_pt_data(
        db_session,
        trainer_id=trainer.id,
        sale_amount_kopecks=100000,
        user_id=seeded_owner.id,
    )

    count_before = await _count_audit_rows(
        db_session, "payroll_accrual_created", "payroll_accrual"
    )

    r = await authed_client_owner.post(
        "/api/v1/payroll/accruals",
        json={
            "trainerId": str(trainer.id),
            "periodStart": PERIOD_START,
            "periodEnd": PERIOD_END,
        },
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 201, r.text

    count_after = await _count_audit_rows(
        db_session, "payroll_accrual_created", "payroll_accrual"
    )
    assert count_after == count_before + 1, (
        f"Expected 1 new payroll_accrual_created audit row, "
        f"before={count_before}, after={count_after}"
    )


# ---------------------------------------------------------------------------
# PAY-04: POST /accruals/{id}/mark-paid
# ---------------------------------------------------------------------------


async def test_mark_paid_happy_path(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_comp_config: Any,
    db_session: AsyncSession,
    seeded_owner: Any,
) -> None:
    """mark-paid returns 200 with status 'paid', paid_at, and paid_by_user_id set (PAY-04)."""
    trainer = await make_trainer()
    await make_comp_config(
        trainer_id=trainer.id,
        commission_pct_bps=1000,
        effective_from=date(2026, 1, 1),
    )
    await _seed_pt_data(
        db_session,
        trainer_id=trainer.id,
        sale_amount_kopecks=100000,
        user_id=seeded_owner.id,
    )

    # Create the accrual first
    r_create = await authed_client_owner.post(
        "/api/v1/payroll/accruals",
        json={
            "trainerId": str(trainer.id),
            "periodStart": PERIOD_START,
            "periodEnd": PERIOD_END,
        },
        headers=_csrf(authed_client_owner),
    )
    assert r_create.status_code == 201, r_create.text
    accrual_id = r_create.json()["data"]["id"]
    assert r_create.json()["data"]["status"] == "pending"

    # Mark paid
    r_paid = await authed_client_owner.post(
        f"/api/v1/payroll/accruals/{accrual_id}/mark-paid",
        headers=_csrf(authed_client_owner),
    )
    assert r_paid.status_code == 200, r_paid.text
    data = r_paid.json()["data"]
    assert data["status"] == "paid"
    assert data.get("paidAt") is not None
    assert data.get("paidByUserId") is not None


async def test_mark_paid_second_attempt_returns_409(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_comp_config: Any,
    db_session: AsyncSession,
    seeded_owner: Any,
) -> None:
    """Second mark-paid returns 409 already_paid (PAY-04 D-58-08 / T-58-30)."""
    trainer = await make_trainer()
    await make_comp_config(
        trainer_id=trainer.id,
        commission_pct_bps=1000,
        effective_from=date(2026, 1, 1),
    )
    await _seed_pt_data(
        db_session,
        trainer_id=trainer.id,
        sale_amount_kopecks=100000,
        user_id=seeded_owner.id,
    )

    r_create = await authed_client_owner.post(
        "/api/v1/payroll/accruals",
        json={
            "trainerId": str(trainer.id),
            "periodStart": PERIOD_START,
            "periodEnd": PERIOD_END,
        },
        headers=_csrf(authed_client_owner),
    )
    assert r_create.status_code == 201, r_create.text
    accrual_id = r_create.json()["data"]["id"]

    # First mark-paid succeeds
    r1 = await authed_client_owner.post(
        f"/api/v1/payroll/accruals/{accrual_id}/mark-paid",
        headers=_csrf(authed_client_owner),
    )
    assert r1.status_code == 200, r1.text

    # Second mark-paid → 409 already_paid
    r2 = await authed_client_owner.post(
        f"/api/v1/payroll/accruals/{accrual_id}/mark-paid",
        headers=_csrf(authed_client_owner),
    )
    assert r2.status_code == 409, r2.text
    assert r2.json()["code"] == "already_paid"


async def test_mark_paid_reception_forbidden(
    authed_client_reception: AsyncClient,
) -> None:
    """Reception receives 403 on POST /accruals/{id}/mark-paid (T-58-26 mitigate)."""
    # Use a random UUID — 403 RBAC check fires before 404 not-found
    r = await authed_client_reception.post(
        f"/api/v1/payroll/accruals/{uuid4()}/mark-paid",
        headers=_csrf(authed_client_reception),
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_mark_paid_nonexistent_accrual_returns_404(
    authed_client_owner: AsyncClient,
) -> None:
    """mark-paid on a non-existent accrual returns 404 (PAY-04 D-58-08)."""
    r = await authed_client_owner.post(
        f"/api/v1/payroll/accruals/{uuid4()}/mark-paid",
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 404, r.text


async def test_mark_paid_audit_row_created(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_comp_config: Any,
    db_session: AsyncSession,
    seeded_owner: Any,
) -> None:
    """audit_log has a payroll_accrual_paid row after mark-paid (D-58-17 / T-58-29)."""
    trainer = await make_trainer()
    await make_comp_config(
        trainer_id=trainer.id,
        commission_pct_bps=1000,
        effective_from=date(2026, 1, 1),
    )
    await _seed_pt_data(
        db_session,
        trainer_id=trainer.id,
        sale_amount_kopecks=100000,
        user_id=seeded_owner.id,
    )

    r_create = await authed_client_owner.post(
        "/api/v1/payroll/accruals",
        json={
            "trainerId": str(trainer.id),
            "periodStart": PERIOD_START,
            "periodEnd": PERIOD_END,
        },
        headers=_csrf(authed_client_owner),
    )
    assert r_create.status_code == 201, r_create.text
    accrual_id = r_create.json()["data"]["id"]

    count_before = await _count_audit_rows(db_session, "payroll_accrual_paid", "payroll_accrual")

    r_paid = await authed_client_owner.post(
        f"/api/v1/payroll/accruals/{accrual_id}/mark-paid",
        headers=_csrf(authed_client_owner),
    )
    assert r_paid.status_code == 200, r_paid.text

    count_after = await _count_audit_rows(db_session, "payroll_accrual_paid", "payroll_accrual")
    assert count_after == count_before + 1, (
        f"Expected 1 new payroll_accrual_paid audit row, "
        f"before={count_before}, after={count_after}"
    )
