"""Integration tests for PAY-06: PT-package refund → payroll clawback hook (Phase 58 D-58-20).

Test scenarios (all go through the real refund HTTP endpoint so the slot fires through
real wiring):

  1. Full flow: sell PT-package (assigned trainer) → seed a status='paid' accrual
     covering its session → refund the package → a NEGATIVE clawback row exists with
     clawback_of_accrual_id = original.id and source_refund_payment_id = refund.id,
     committed atomically (visible after the refund response).
  2. Original paid accrual is UNCHANGED (status still 'paid', accrual_kopecks unchanged).
  3. Refund of a package with NO paid accrual → zero clawback rows written.
  4. Refund of a package whose trainer_id is NULL → zero clawback rows written.
  5. audit_log has a payroll_clawback_recorded row in the same transaction as the refund.

Architecture:
  - Tests drive the refund via the HTTP POST /api/v1/pt-packages/{id}/refund endpoint.
  - The conftest _client_app_overrides calls register_payroll_clawback_recorder to wire
    the real payroll service slot into the test app, mirroring how production main.py
    wires it alongside register_payment_refunder.
  - SAVEPOINT fixture (db_session) provides per-test isolation consistent with the
    rest of the payroll test suite.

Cross-module note: test code is ALLOWED to use ORM models from any module; only
payroll/repository.py is forbidden from cross-module ORM imports (D-58-19).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import register_payroll_clawback_recorder
from app.core.redis import get_redis
from app.modules.clients.models import Client
from app.modules.payments.models import Payment
from app.modules.payroll.models import TrainerPayrollAccrual
from app.modules.payroll.router import router as payroll_router
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.pt_sessions.models import PtSession

# ---------------------------------------------------------------------------
# Re-export fixtures from payroll conftest so pytest can discover them.
# ---------------------------------------------------------------------------
from tests.integration.payroll.conftest import (
    authed_client_owner as authed_client_owner,
    db_session_real_commit as db_session_real_commit,
    make_accrual as make_accrual,
    make_client as make_client,
    make_comp_config as make_comp_config,
    make_plan as make_plan,
    make_trainer as make_trainer,
    make_user as make_user,
    redis_clean as redis_clean,
    seeded_owner as seeded_owner,
    seeded_reception as seeded_reception,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PERIOD_START = date(2026, 4, 1)
PERIOD_END = date(2026, 4, 30)
PERFORMED_AT = datetime(2026, 4, 15, 10, 0, 0, tzinfo=UTC)  # MSK date = 2026-04-15


# ---------------------------------------------------------------------------
# conftest override: wire payroll router + payroll clawback recorder into test app
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def _client_app_overrides(
    app: FastAPI,
    db_session: AsyncSession,
) -> object:
    """Override get_db, get_redis; mount payroll + pt-packages routers;
    wire register_payroll_clawback_recorder.

    Mirrors how production main.py wires register_payroll_clawback_recorder alongside
    register_payment_refunder (D-58-20). The pt-packages refund endpoint is already
    mounted by the base app fixture; this conftest only adds the payroll router and
    wires the clawback slot.
    """
    from app.modules.payroll import service as payroll_service

    # Wire the real slot implementation into the test app.
    register_payroll_clawback_recorder(payroll_service.record_clawback_for_pt_package_refund)

    async def _override_get_db() -> object:
        yield db_session

    def _override_get_redis() -> object:
        return app.state.redis

    # Mount payroll router (idempotent guard — the app fixture is function-scoped).
    existing_paths = {r.path for r in app.routes}  # type: ignore[attr-defined]
    if "/api/v1/payroll/trainer-configs/{trainer_id}" not in existing_paths:
        app.include_router(payroll_router, prefix="/api/v1/payroll", tags=["payroll"])

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis
    try:
        yield app
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _csrf(client: AsyncClient) -> dict[str, str]:
    token: str = client.cookies.get("sportzal_csrf") or ""
    return {"X-CSRF-Token": token}


async def _sell_pt_package(
    authed: AsyncClient,
    *,
    client_id: UUID,
    plan_id: UUID,
    amount_kopecks: int,
) -> UUID:
    """Sell a PT-package via the HTTP endpoint; return its id."""
    r = await authed.post(
        "/api/v1/pt-packages",
        json={
            "clientId": str(client_id),
            "planId": str(plan_id),
            "amountKopecks": amount_kopecks,
        },
        headers={**_csrf(authed), "Idempotency-Key": uuid4().hex},
    )
    assert r.status_code == 201, r.text
    return UUID(r.json()["data"]["id"])


async def _refund_pt_package(authed: AsyncClient, pt_package_id: UUID) -> dict:  # type: ignore[type-arg]
    """Refund a PT-package via the HTTP endpoint; return response JSON."""
    r = await authed.post(
        f"/api/v1/pt-packages/{pt_package_id}/refund",
        json={"reason": "test-clawback-refund"},
        headers={**_csrf(authed), "Idempotency-Key": uuid4().hex},
    )
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


async def _seed_pt_session(
    db_session: AsyncSession,
    *,
    pt_package_id: UUID,
    trainer_id: UUID,
    client_id: UUID,
    user_id: UUID,
    performed_at: datetime = PERFORMED_AT,
) -> PtSession:
    """Seed a non-cancelled PtSession row inside the SAVEPOINT session."""
    sess = PtSession(
        pt_package_id=pt_package_id,
        trainer_id=trainer_id,
        client_id=client_id,
        performed_at=performed_at,
        performed_by_user_id=user_id,
        trainer_name_snapshot="Тренер Тест",
        cancelled_at=None,
    )
    db_session.add(sess)
    await db_session.commit()
    await db_session.refresh(sess)
    return sess


async def _count_clawback_rows(db_session: AsyncSession, trainer_id: UUID) -> int:
    """Return the number of clawback accrual rows for a trainer."""
    result = await db_session.execute(
        sa.text(
            "SELECT COUNT(*) FROM trainer_payroll_accruals "
            "WHERE trainer_id = :tid AND clawback_of_accrual_id IS NOT NULL"
        ),
        {"tid": str(trainer_id)},
    )
    return int(result.scalar_one())


async def _count_audit_rows(
    db_session: AsyncSession, action: str, resource_type: str
) -> int:
    result = await db_session.execute(
        sa.text(
            "SELECT COUNT(*) FROM audit_log "
            "WHERE action = :action AND resource_type = :resource_type"
        ),
        {"action": action, "resource_type": resource_type},
    )
    return int(result.scalar_one())


# ---------------------------------------------------------------------------
# Test 1 — Full clawback flow: sell → paid accrual → refund → negative row
# ---------------------------------------------------------------------------


async def test_clawback_negative_row_appended_after_paid_accrual(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_trainer: object,
    make_comp_config: object,
    make_accrual: object,
    seeded_owner: object,
) -> None:
    """Full PAY-06 flow: refund after paid accrual appends a NEGATIVE clawback row.

    Atomicity: the clawback row is visible immediately after the refund
    response (same-UoW commit per D-58-20 / T-58-34).
    """
    import sqlalchemy as sa

    from app.modules.trainers.models import Trainer

    # Seed trainer
    trainer: Trainer = await make_trainer()  # type: ignore[call-arg,assignment]
    owner = seeded_owner

    # Seed client + plan via ORM (allowed in tests)
    client = Client(
        last_name="Тестов",
        first_name="Иван",
        phone=f"+7999{uuid4().hex[:7]}",
        created_by_user_id=owner.id,
    )
    db_session.add(client)
    plan = PtPackagePlan(
        name=f"Тест-план-{uuid4().hex[:4]}",
        session_count=10,
        price_kopecks=500_000,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(client)
    await db_session.refresh(plan)

    # Seed comp config
    comp_config = await make_comp_config(  # type: ignore[call-arg,assignment]
        trainer_id=trainer.id,
        commission_pct_bps=1000,  # 10%
        effective_from=date(2026, 1, 1),
    )

    # Sell via HTTP (creates payment row)
    pt_package_id = await _sell_pt_package(
        authed_client_owner,
        client_id=client.id,
        plan_id=plan.id,
        amount_kopecks=plan.price_kopecks,
    )

    # Fetch the newly-sold PtPackage via ORM to get its id and verify trainer_id
    pkg_result = await db_session.execute(
        sa.text("SELECT id, trainer_id FROM pt_packages WHERE id = :pid"),
        {"pid": str(pt_package_id)},
    )
    pkg_row = pkg_result.mappings().one()
    assert pkg_row["trainer_id"] is None  # sale endpoint doesn't set trainer_id by default

    # Update trainer_id on the package so it matches our trainer (assigned-at-sale simulation)
    await db_session.execute(
        sa.text("UPDATE pt_packages SET trainer_id = :tid WHERE id = :pid"),
        {"tid": str(trainer.id), "pid": str(pt_package_id)},
    )
    await db_session.commit()

    # Seed a non-cancelled pt_session in the accrual period
    await _seed_pt_session(
        db_session,
        pt_package_id=pt_package_id,
        trainer_id=trainer.id,
        client_id=client.id,
        user_id=owner.id,
    )

    # Seed a status='paid' regular accrual covering the session
    paid_accrual: TrainerPayrollAccrual = await make_accrual(  # type: ignore[call-arg,assignment]
        trainer_id=trainer.id,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        sessions_count=1,
        revenue_kopecks=500_000,
        comp_config_id_snapshot=comp_config.id,
        accrual_kopecks=50_000,  # 10% of 500k
        commission_pct_bps_snapshot=1000,
        status="paid",
    )
    assert paid_accrual.accrual_kopecks == 50_000
    assert paid_accrual.status == "paid"

    # Count clawback rows before refund (should be 0)
    count_before = await _count_clawback_rows(db_session, trainer.id)
    assert count_before == 0

    # Refund via HTTP
    await _refund_pt_package(authed_client_owner, pt_package_id)

    # Verify clawback row was appended
    count_after = await _count_clawback_rows(db_session, trainer.id)
    assert count_after == 1

    # Fetch the clawback row and verify its fields
    clawback_result = await db_session.execute(
        sa.text(
            "SELECT id, accrual_kopecks, status, clawback_of_accrual_id, "
            "source_refund_payment_id "
            "FROM trainer_payroll_accruals "
            "WHERE trainer_id = :tid AND clawback_of_accrual_id IS NOT NULL"
        ),
        {"tid": str(trainer.id)},
    )
    clawback_row = clawback_result.mappings().one()
    assert clawback_row["accrual_kopecks"] < 0, "Clawback must be negative"
    assert clawback_row["status"] == "pending", "Clawback row starts as pending"
    assert str(clawback_row["clawback_of_accrual_id"]) == str(
        paid_accrual.id
    ), "clawback_of_accrual_id must point to the original paid accrual"
    assert clawback_row["source_refund_payment_id"] is not None, "source_refund_payment_id must be set"


# ---------------------------------------------------------------------------
# Test 2 — Original paid accrual is NOT mutated
# ---------------------------------------------------------------------------


async def test_original_accrual_unchanged_after_clawback(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_trainer: object,
    make_comp_config: object,
    make_accrual: object,
    seeded_owner: object,
) -> None:
    """The original paid accrual must NOT be modified (no UPDATE — append-only ledger, D-58-03)."""
    import sqlalchemy as sa

    from app.modules.trainers.models import Trainer

    trainer: Trainer = await make_trainer()  # type: ignore[call-arg,assignment]
    owner = seeded_owner

    client = Client(
        last_name="Оригинальский",
        first_name="Тест",
        phone=f"+7999{uuid4().hex[:7]}",
        created_by_user_id=owner.id,
    )
    db_session.add(client)
    plan = PtPackagePlan(
        name=f"Тест-план-{uuid4().hex[:4]}",
        session_count=5,
        price_kopecks=300_000,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(client)
    await db_session.refresh(plan)

    comp_config = await make_comp_config(  # type: ignore[call-arg,assignment]
        trainer_id=trainer.id,
        commission_pct_bps=2000,  # 20%
        effective_from=date(2026, 1, 1),
    )

    pt_package_id = await _sell_pt_package(
        authed_client_owner,
        client_id=client.id,
        plan_id=plan.id,
        amount_kopecks=plan.price_kopecks,
    )

    # Set trainer_id on the package
    await db_session.execute(
        sa.text("UPDATE pt_packages SET trainer_id = :tid WHERE id = :pid"),
        {"tid": str(trainer.id), "pid": str(pt_package_id)},
    )
    await db_session.commit()

    await _seed_pt_session(
        db_session,
        pt_package_id=pt_package_id,
        trainer_id=trainer.id,
        client_id=client.id,
        user_id=owner.id,
    )

    paid_accrual: TrainerPayrollAccrual = await make_accrual(  # type: ignore[call-arg,assignment]
        trainer_id=trainer.id,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        sessions_count=1,
        revenue_kopecks=300_000,
        comp_config_id_snapshot=comp_config.id,
        accrual_kopecks=60_000,  # 20% of 300k
        commission_pct_bps_snapshot=2000,
        status="paid",
    )
    original_accrual_kopecks = paid_accrual.accrual_kopecks
    original_status = paid_accrual.status

    await _refund_pt_package(authed_client_owner, pt_package_id)

    # Re-fetch the original accrual and assert it is unchanged
    await db_session.refresh(paid_accrual)
    assert paid_accrual.accrual_kopecks == original_accrual_kopecks, "accrual_kopecks must not change"
    assert paid_accrual.status == original_status, "status must not change (no UPDATE)"
    assert paid_accrual.clawback_of_accrual_id is None, "original row must not become a clawback row"


# ---------------------------------------------------------------------------
# Test 3 — No paid accrual → no clawback row
# ---------------------------------------------------------------------------


async def test_no_clawback_when_no_paid_accrual(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_trainer: object,
    seeded_owner: object,
) -> None:
    """Refund of a package with NO paid accrual → zero clawback rows written."""
    from app.modules.trainers.models import Trainer

    trainer: Trainer = await make_trainer()  # type: ignore[call-arg,assignment]
    owner = seeded_owner

    client = Client(
        last_name="НетАкрual",
        first_name="Тест",
        phone=f"+7999{uuid4().hex[:7]}",
        created_by_user_id=owner.id,
    )
    db_session.add(client)
    plan = PtPackagePlan(
        name=f"Тест-план-{uuid4().hex[:4]}",
        session_count=10,
        price_kopecks=200_000,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(client)
    await db_session.refresh(plan)

    pt_package_id = await _sell_pt_package(
        authed_client_owner,
        client_id=client.id,
        plan_id=plan.id,
        amount_kopecks=plan.price_kopecks,
    )

    # Set trainer_id on the package but do NOT create any accrual
    await db_session.execute(
        sa.text("UPDATE pt_packages SET trainer_id = :tid WHERE id = :pid"),
        {"tid": str(trainer.id), "pid": str(pt_package_id)},
    )
    await db_session.commit()

    count_before = await _count_clawback_rows(db_session, trainer.id)
    assert count_before == 0

    await _refund_pt_package(authed_client_owner, pt_package_id)

    count_after = await _count_clawback_rows(db_session, trainer.id)
    assert count_after == 0, "No clawback row when no paid accrual exists"


# ---------------------------------------------------------------------------
# Test 4 — NULL trainer_id on package → no clawback
# ---------------------------------------------------------------------------


async def test_no_clawback_when_trainer_id_null(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: object,
) -> None:
    """Refund of a package with trainer_id=NULL → no clawback (non-commissionable per D-58-21)."""
    owner = seeded_owner

    client = Client(
        last_name="НетТренера",
        first_name="Тест",
        phone=f"+7999{uuid4().hex[:7]}",
        created_by_user_id=owner.id,
    )
    db_session.add(client)
    plan = PtPackagePlan(
        name=f"Тест-план-{uuid4().hex[:4]}",
        session_count=10,
        price_kopecks=100_000,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(client)
    await db_session.refresh(plan)

    # Sell PT-package WITHOUT setting trainer_id (NULL trainer)
    pt_package_id = await _sell_pt_package(
        authed_client_owner,
        client_id=client.id,
        plan_id=plan.id,
        amount_kopecks=plan.price_kopecks,
    )

    # Verify trainer_id is NULL on this package
    result = await db_session.execute(
        sa.text("SELECT trainer_id FROM pt_packages WHERE id = :pid"),
        {"pid": str(pt_package_id)},
    )
    assert result.scalar_one_or_none() is None, "trainer_id must be NULL for this test"

    # Count clawback rows across all trainers — should be 0 before and after
    result2 = await db_session.execute(
        sa.text("SELECT COUNT(*) FROM trainer_payroll_accruals WHERE clawback_of_accrual_id IS NOT NULL")
    )
    count_before = int(result2.scalar_one())

    await _refund_pt_package(authed_client_owner, pt_package_id)

    result3 = await db_session.execute(
        sa.text("SELECT COUNT(*) FROM trainer_payroll_accruals WHERE clawback_of_accrual_id IS NOT NULL")
    )
    count_after = int(result3.scalar_one())
    assert count_after == count_before, "No clawback row when package trainer_id is NULL"


# ---------------------------------------------------------------------------
# Test 5 — audit_log has payroll_clawback_recorded row
# ---------------------------------------------------------------------------


async def test_audit_row_emitted_on_clawback(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_trainer: object,
    make_comp_config: object,
    make_accrual: object,
    seeded_owner: object,
) -> None:
    """payroll_clawback_recorded audit row must exist after a successful clawback (D-58-17)."""
    import sqlalchemy as sa

    from app.modules.trainers.models import Trainer

    trainer: Trainer = await make_trainer()  # type: ignore[call-arg,assignment]
    owner = seeded_owner

    client = Client(
        last_name="АудитТест",
        first_name="Тест",
        phone=f"+7999{uuid4().hex[:7]}",
        created_by_user_id=owner.id,
    )
    db_session.add(client)
    plan = PtPackagePlan(
        name=f"Тест-план-{uuid4().hex[:4]}",
        session_count=10,
        price_kopecks=400_000,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(client)
    await db_session.refresh(plan)

    comp_config = await make_comp_config(  # type: ignore[call-arg,assignment]
        trainer_id=trainer.id,
        commission_pct_bps=1000,
        effective_from=date(2026, 1, 1),
    )

    pt_package_id = await _sell_pt_package(
        authed_client_owner,
        client_id=client.id,
        plan_id=plan.id,
        amount_kopecks=plan.price_kopecks,
    )

    await db_session.execute(
        sa.text("UPDATE pt_packages SET trainer_id = :tid WHERE id = :pid"),
        {"tid": str(trainer.id), "pid": str(pt_package_id)},
    )
    await db_session.commit()

    await _seed_pt_session(
        db_session,
        pt_package_id=pt_package_id,
        trainer_id=trainer.id,
        client_id=client.id,
        user_id=owner.id,
    )

    await make_accrual(  # type: ignore[call-arg]
        trainer_id=trainer.id,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        sessions_count=1,
        revenue_kopecks=400_000,
        comp_config_id_snapshot=comp_config.id,
        accrual_kopecks=40_000,  # 10% of 400k
        commission_pct_bps_snapshot=1000,
        status="paid",
    )

    audit_before = await _count_audit_rows(db_session, "payroll_clawback_recorded", "payroll_accrual")

    await _refund_pt_package(authed_client_owner, pt_package_id)

    audit_after = await _count_audit_rows(db_session, "payroll_clawback_recorded", "payroll_accrual")
    assert audit_after == audit_before + 1, (
        "payroll_clawback_recorded audit row must be emitted on refund with paid accrual"
    )
