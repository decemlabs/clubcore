"""Integration tests for GET /api/v1/payroll/preview (Phase 58 PAY-02).

Coverage:
  - Pure-pct golden: revenue 100000 kopecks, bps 1500 (15%) → commission 15000,
    fixed 0, total 15000.
  - Ceil-in-favor golden: revenue 10001 kopecks, bps 1500 → 1500.15 → ceil 1501.
  - Pure-fixed golden: session_fee 50000, 3 sessions → fixed 150000, commission 0.
  - Hybrid golden: pct + fixed both contribute; total = sum.
  - No config → 422 with code comp_config_missing.
  - Both-NULL config → 422 comp_config_missing.
  - Reception → 403 forbidden.
  - Zero-persistence: trainer_payroll_accruals row count is unchanged before and
    after a preview call (D-58-12 zero-persistence invariant).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.models import Client
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.pt_sessions.models import PtSession
from app.modules.payments.models import Payment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PERIOD_START = "2026-04-01"
PERIOD_END = "2026-04-30"
# A performed_at within the period, in Europe/Moscow tz (UTC+3)
PERFORMED_AT = datetime(2026, 4, 15, 10, 0, 0, tzinfo=timezone.utc)


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
    cancel_sessions: bool = False,
    user_id: UUID,
) -> None:
    """Seed a pt_package_plan, pt_package, N pt_sessions, and a payment via ORM.

    Uses ORM models from other modules — this is ALLOWED in test code; only
    payroll/repository.py is forbidden from cross-module ORM imports (D-58-19).

    Verified columns:
      pt_package_plans (pt_packages/models.py:64-69): name, session_count, price_kopecks
      pt_packages (pt_packages/models.py:103+): client_id, plan_id, plan_name_snapshot,
        session_count_snapshot, price_kopecks_snapshot, sessions_remaining, status,
        start_date, trainer_id
      pt_sessions (pt_sessions/models.py:47+): pt_package_id, trainer_id, client_id,
        performed_at, performed_by_user_id, trainer_name_snapshot, cancelled_at
      payments (payments/models.py:51+): subject_kind, subject_id, amount_kopecks,
        method, received_at
    """
    # Client (FK required by pt_packages.client_id and pt_sessions.client_id)
    client = Client(
        last_name="Тестов",
        first_name="Тест",
        phone=f"+7999{uuid4().hex[:7]}",
        created_by_user_id=user_id,
    )
    db_session.add(client)
    await db_session.flush()

    # Package plan
    plan = PtPackagePlan(
        name=f"Тест-план-{uuid4().hex[:4]}",
        session_count=10,
        price_kopecks=sale_amount_kopecks,
    )
    db_session.add(plan)
    await db_session.flush()

    # Package — assigned to trainer (attribution: assigned-at-sale)
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

    # Sessions (cancelled_at populates only when cancel_sessions=True)
    for _ in range(session_count):
        sess = PtSession(
            pt_package_id=pkg.id,
            trainer_id=trainer_id,
            client_id=client.id,
            performed_at=PERFORMED_AT,
            performed_by_user_id=user_id,
            trainer_name_snapshot="Тренер Тест",
            cancelled_at=PERFORMED_AT if cancel_sessions else None,
        )
        db_session.add(sess)

    # Sale payment
    payment = Payment(
        subject_kind="pt_package",
        subject_id=pkg.id,
        amount_kopecks=sale_amount_kopecks,
        method="cash",
        received_at=PERFORMED_AT,
    )
    db_session.add(payment)
    await db_session.commit()


async def _count_accruals(db_session: AsyncSession) -> int:
    """Return current row count in trainer_payroll_accruals."""
    row = (
        await db_session.execute(sa.text("SELECT COUNT(*) AS cnt FROM trainer_payroll_accruals"))
    ).mappings().one()
    return int(row["cnt"])


# ---------------------------------------------------------------------------
# Golden number tests
# ---------------------------------------------------------------------------


async def test_preview_pure_pct_golden(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_comp_config: Any,
    db_session: AsyncSession,
    seeded_owner: Any,
) -> None:
    """Pure-pct: revenue 100000 kopecks, bps 1500 → commission 15000, total 15000 (PAY-02)."""
    trainer = await make_trainer()
    await make_comp_config(
        trainer_id=trainer.id,
        commission_pct_bps=1500,
        session_fee_kopecks=None,
        effective_from=date(2026, 1, 1),
    )
    await _seed_pt_data(
        db_session,
        trainer_id=trainer.id,
        sale_amount_kopecks=100000,
        user_id=seeded_owner.id,
    )

    r = await authed_client_owner.get(
        "/api/v1/payroll/preview",
        params={
            "trainerId": str(trainer.id),
            "periodStart": PERIOD_START,
            "periodEnd": PERIOD_END,
        },
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["sessionCount"] == 1
    assert data["commissionKopecks"] == 15000
    assert data["fixedKopecks"] == 0
    assert data["totalKopecks"] == 15000


async def test_preview_ceil_in_favor_golden(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_comp_config: Any,
    db_session: AsyncSession,
    seeded_owner: Any,
) -> None:
    """Ceil-in-favor: revenue 10001 kopecks, bps 1500 → 1500.15 → ceil 1501 (PAY-02 / T-58-25).

    This test proves no float truncation: if commission were computed via float
    arithmetic, 10001 * 1500 / 10000 = 1500.15 might truncate to 1500.  math.ceil
    on a Python int division yields 1501 exactly.
    """
    trainer = await make_trainer()
    await make_comp_config(
        trainer_id=trainer.id,
        commission_pct_bps=1500,
        session_fee_kopecks=None,
        effective_from=date(2026, 1, 1),
    )
    await _seed_pt_data(
        db_session,
        trainer_id=trainer.id,
        sale_amount_kopecks=10001,
        user_id=seeded_owner.id,
    )

    r = await authed_client_owner.get(
        "/api/v1/payroll/preview",
        params={
            "trainerId": str(trainer.id),
            "periodStart": PERIOD_START,
            "periodEnd": PERIOD_END,
        },
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    # 10001 * 1500 / 10000 = 1500.15 → math.ceil → 1501 (proves no float truncation)
    assert data["commissionKopecks"] == 1501


async def test_preview_pure_fixed_golden(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_comp_config: Any,
    db_session: AsyncSession,
    seeded_owner: Any,
) -> None:
    """Pure-fixed: session_fee 50000, 3 sessions → fixed 150000, commission 0 (PAY-02)."""
    trainer = await make_trainer()
    await make_comp_config(
        trainer_id=trainer.id,
        commission_pct_bps=None,
        session_fee_kopecks=50000,
        effective_from=date(2026, 1, 1),
    )
    await _seed_pt_data(
        db_session,
        trainer_id=trainer.id,
        sale_amount_kopecks=150000,
        session_count=3,
        user_id=seeded_owner.id,
    )

    r = await authed_client_owner.get(
        "/api/v1/payroll/preview",
        params={
            "trainerId": str(trainer.id),
            "periodStart": PERIOD_START,
            "periodEnd": PERIOD_END,
        },
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["sessionCount"] == 3
    assert data["fixedKopecks"] == 150000
    assert data["commissionKopecks"] == 0
    assert data["totalKopecks"] == 150000


async def test_preview_hybrid_golden(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_comp_config: Any,
    db_session: AsyncSession,
    seeded_owner: Any,
) -> None:
    """Hybrid: pct 1000 bps + fixed 30000/session; 2 sessions, revenue 200000 (PAY-02)."""
    trainer = await make_trainer()
    await make_comp_config(
        trainer_id=trainer.id,
        commission_pct_bps=1000,
        session_fee_kopecks=30000,
        effective_from=date(2026, 1, 1),
    )
    await _seed_pt_data(
        db_session,
        trainer_id=trainer.id,
        sale_amount_kopecks=200000,
        session_count=2,
        user_id=seeded_owner.id,
    )

    r = await authed_client_owner.get(
        "/api/v1/payroll/preview",
        params={
            "trainerId": str(trainer.id),
            "periodStart": PERIOD_START,
            "periodEnd": PERIOD_END,
        },
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    # commission = ceil(200000 * 1000 / 10000) = 20000; fixed = 30000 * 2 = 60000
    assert data["commissionKopecks"] == 20000
    assert data["fixedKopecks"] == 60000
    assert data["totalKopecks"] == 80000


# ---------------------------------------------------------------------------
# Error / edge-case tests
# ---------------------------------------------------------------------------


async def test_preview_no_config_returns_422(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
) -> None:
    """No comp config for trainer → 422 comp_config_missing (PAY-02 / D-58-07)."""
    trainer = await make_trainer()
    r = await authed_client_owner.get(
        "/api/v1/payroll/preview",
        params={
            "trainerId": str(trainer.id),
            "periodStart": PERIOD_START,
            "periodEnd": PERIOD_END,
        },
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "comp_config_missing"


async def test_preview_both_null_config_returns_422(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_comp_config: Any,
) -> None:
    """Both-NULL comp config → 422 comp_config_missing (PAY-02 / D-58-09)."""
    trainer = await make_trainer()
    await make_comp_config(
        trainer_id=trainer.id,
        commission_pct_bps=None,
        session_fee_kopecks=None,
        effective_from=date(2026, 1, 1),
    )
    r = await authed_client_owner.get(
        "/api/v1/payroll/preview",
        params={
            "trainerId": str(trainer.id),
            "periodStart": PERIOD_START,
            "periodEnd": PERIOD_END,
        },
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "comp_config_missing"


async def test_preview_reception_forbidden(
    authed_client_reception: AsyncClient,
    make_trainer: Any,
) -> None:
    """Reception receives 403 forbidden on GET /preview (T-58-22 / D-58-19)."""
    trainer = await make_trainer()
    r = await authed_client_reception.get(
        "/api/v1/payroll/preview",
        params={
            "trainerId": str(trainer.id),
            "periodStart": PERIOD_START,
            "periodEnd": PERIOD_END,
        },
        headers=_csrf(authed_client_reception),
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_preview_zero_persistence(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_comp_config: Any,
    db_session: AsyncSession,
    seeded_owner: Any,
) -> None:
    """Preview does NOT persist any accrual row (D-58-12 zero-persistence invariant)."""
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

    count_before = await _count_accruals(db_session)

    r = await authed_client_owner.get(
        "/api/v1/payroll/preview",
        params={
            "trainerId": str(trainer.id),
            "periodStart": PERIOD_START,
            "periodEnd": PERIOD_END,
        },
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 200, r.text

    count_after = await _count_accruals(db_session)
    assert count_after == count_before, (
        f"Preview must not persist any accrual row: "
        f"before={count_before}, after={count_after}"
    )
