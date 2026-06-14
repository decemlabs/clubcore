"""VER-02 end-to-end payroll lifecycle integration test (Phase 110-03).

Verifies the full P102 trainer-payroll lifecycle on real seeded Postgres:
  comp-config (PUT /api/v1/payroll/trainer-configs/{trainer_id})
    → preview  (GET  /api/v1/payroll/preview)
    → run      (POST /api/v1/payroll/accruals, 201, status 'pending')
    → mark-paid (POST /api/v1/payroll/accruals/{id}/mark-paid, 200, pending→paid)

Accrual snapshot assertions (golden math):
  revenue = 100_000 kopecks, sessions = 2
  commission_pct_bps = 1000 → commission = ceil(100000 * 1000 / 10000) = 10_000
  session_fee_kopecks = 50_000, sessions = 2 → fixed = 100_000
  total = 110_000

Terminal transition: second mark-paid → 409 already_paid.

RBAC negative: reception receives 403 on all four owner-only payroll endpoints.

Reuses conftest factories: make_trainer, make_comp_config, authed_client_owner,
authed_client_reception, db_session, seeded_owner.
Copies _csrf + _seed_pt_data helpers from test_payroll_accruals.py (same pattern).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.models import Client
from app.modules.payments.models import Payment
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.pt_sessions.models import PtSession

# ---------------------------------------------------------------------------
# Constants (anchored to the 2026-04 window, Europe/Moscow)
# ---------------------------------------------------------------------------

PERIOD_START = "2026-04-01"
PERIOD_END = "2026-04-30"
PERFORMED_AT = datetime(2026, 4, 15, 10, 0, 0, tzinfo=UTC)

# Golden math constants (VER-02)
SALE_AMOUNT_KOPECKS = 100_000
SESSION_COUNT = 2
COMMISSION_PCT_BPS = 1000  # 10%
SESSION_FEE_KOPECKS = 50_000
# commission = ceil(100000 * 1000 / 10000) = 10000
EXPECTED_COMMISSION = 10_000
# fixed = 50000 * 2 = 100000
EXPECTED_FIXED = 100_000
EXPECTED_TOTAL = 110_000


# ---------------------------------------------------------------------------
# Helpers (copied from test_payroll_accruals.py — same pattern)
# ---------------------------------------------------------------------------


def _csrf(client: AsyncClient) -> dict[str, str]:
    """Return the X-CSRF-Token header from the client's cookie jar."""
    token: str = client.cookies.get("clubcore_csrf") or ""
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


# ---------------------------------------------------------------------------
# Task 1: VER-02 payroll lifecycle E2E (owner)
# ---------------------------------------------------------------------------


async def test_payroll_lifecycle_e2e(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    db_session: AsyncSession,
    seeded_owner: Any,
) -> None:
    """VER-02 end-to-end lifecycle: comp-config → preview → run → pending → paid.

    Drives the full HTTP path without using the make_comp_config factory —
    the PUT endpoint itself is step 1 of the lifecycle under test.

    Golden math (SESSION_COUNT=2, SALE_AMOUNT_KOPECKS=100_000):
      commission = ceil(100_000 * 1_000 / 10_000) = 10_000
      fixed      = 50_000 * 2                      = 100_000
      total                                         = 110_000
    """
    trainer = await make_trainer()
    owner = seeded_owner

    # Seed revenue + completed sessions before driving the HTTP lifecycle
    await _seed_pt_data(
        db_session,
        trainer_id=trainer.id,
        sale_amount_kopecks=SALE_AMOUNT_KOPECKS,
        session_count=SESSION_COUNT,
        user_id=owner.id,
    )

    # --- Step 1: SET comp config via HTTP PUT --------------------------------
    r_put = await authed_client_owner.put(
        f"/api/v1/payroll/trainer-configs/{trainer.id}",
        json={
            "commissionPctBps": COMMISSION_PCT_BPS,
            "sessionFeeKopecks": SESSION_FEE_KOPECKS,
            "effectiveFrom": "2026-01-01",
        },
        headers=_csrf(authed_client_owner),
    )
    assert r_put.status_code == 200, r_put.text
    config_data = r_put.json()["data"]
    config_id = config_data["id"]
    assert UUID(config_id)  # non-null UUID
    assert config_data["commissionPctBps"] == COMMISSION_PCT_BPS
    assert config_data["sessionFeeKopecks"] == SESSION_FEE_KOPECKS

    # --- Step 2: PREVIEW accrual via HTTP GET --------------------------------
    r_preview = await authed_client_owner.get(
        "/api/v1/payroll/preview",
        params={
            "trainerId": str(trainer.id),
            "periodStart": PERIOD_START,
            "periodEnd": PERIOD_END,
        },
        headers=_csrf(authed_client_owner),
    )
    assert r_preview.status_code == 200, r_preview.text
    preview = r_preview.json()["data"]
    assert preview["sessionCount"] == SESSION_COUNT
    assert preview["commissionKopecks"] == EXPECTED_COMMISSION
    assert preview["fixedKopecks"] == EXPECTED_FIXED
    assert preview["totalKopecks"] == EXPECTED_TOTAL

    # --- Step 3: RUN accrual via HTTP POST -----------------------------------
    r_run = await authed_client_owner.post(
        "/api/v1/payroll/accruals",
        json={
            "trainerId": str(trainer.id),
            "periodStart": PERIOD_START,
            "periodEnd": PERIOD_END,
        },
        headers=_csrf(authed_client_owner),
    )
    assert r_run.status_code == 201, r_run.text
    accrual = r_run.json()["data"]
    accrual_id: str = accrual["id"]

    # Status and temporal fields
    assert accrual["status"] == "pending"
    assert accrual.get("accruedAt") is not None
    assert accrual.get("paidAt") is None
    assert accrual.get("paidByUserId") is None

    # Snapshot fields must match the config created in step 1
    assert accrual.get("commissionPctBpsSnapshot") == COMMISSION_PCT_BPS
    assert accrual.get("sessionFeeKopecksSnapshot") == SESSION_FEE_KOPECKS
    assert accrual.get("compConfigIdSnapshot") == config_id

    # Computed snapshot fields (golden math)
    assert accrual.get("sessionsCount") == SESSION_COUNT
    assert accrual.get("accrualKopecks") == EXPECTED_TOTAL

    # Revenue field (sum of pt_package payments in the period)
    assert accrual.get("revenueKopecks") == SALE_AMOUNT_KOPECKS

    # --- Step 4: MARK PAID (pending → paid) ----------------------------------
    r_paid = await authed_client_owner.post(
        f"/api/v1/payroll/accruals/{accrual_id}/mark-paid",
        headers=_csrf(authed_client_owner),
    )
    assert r_paid.status_code == 200, r_paid.text
    paid_data = r_paid.json()["data"]
    assert paid_data["status"] == "paid"
    assert paid_data.get("paidAt") is not None
    assert paid_data.get("paidByUserId") is not None

    # --- Step 5: SECOND mark-paid → 409 already_paid (terminal transition) --
    r_dup = await authed_client_owner.post(
        f"/api/v1/payroll/accruals/{accrual_id}/mark-paid",
        headers=_csrf(authed_client_owner),
    )
    assert r_dup.status_code == 409, r_dup.text
    assert r_dup.json()["code"] == "already_paid"


# ---------------------------------------------------------------------------
# Task 2: VER-02 RBAC negative — reception 403 on all owner-only payroll endpoints
# ---------------------------------------------------------------------------


async def test_payroll_rbac_reception_forbidden_on_all_endpoints(
    authed_client_reception: AsyncClient,
    make_trainer: Any,
) -> None:
    """VER-02 RBAC negative: reception receives 403 on all owner-only payroll endpoints.

    Verifies that (Action.*, Resource.COMPENSATION|PAYROLL) ∈ OWNER_ONLY
    blocks the reception principal on every lifecycle endpoint.
    Zero owner-only payroll calls succeed for reception.

    For mark-paid, a random UUID is used for the path param — the RBAC gate
    fires before resource resolution, so 403 precedes any 404.
    """
    trainer = await make_trainer()

    # PUT /trainer-configs/{trainer_id} → 403
    r_put = await authed_client_reception.put(
        f"/api/v1/payroll/trainer-configs/{trainer.id}",
        json={
            "commissionPctBps": 1000,
            "sessionFeeKopecks": 50_000,
            "effectiveFrom": "2026-01-01",
        },
        headers=_csrf(authed_client_reception),
    )
    assert r_put.status_code == 403, f"Expected 403, got {r_put.status_code}: {r_put.text}"
    assert r_put.json()["code"] == "forbidden"

    # GET /preview?trainerId=...&periodStart=...&periodEnd=... → 403
    r_preview = await authed_client_reception.get(
        "/api/v1/payroll/preview",
        params={
            "trainerId": str(trainer.id),
            "periodStart": PERIOD_START,
            "periodEnd": PERIOD_END,
        },
        headers=_csrf(authed_client_reception),
    )
    assert r_preview.status_code == 403, (
        f"Expected 403, got {r_preview.status_code}: {r_preview.text}"
    )
    assert r_preview.json()["code"] == "forbidden"

    # POST /accruals → 403
    r_accruals = await authed_client_reception.post(
        "/api/v1/payroll/accruals",
        json={
            "trainerId": str(trainer.id),
            "periodStart": PERIOD_START,
            "periodEnd": PERIOD_END,
        },
        headers=_csrf(authed_client_reception),
    )
    assert r_accruals.status_code == 403, (
        f"Expected 403, got {r_accruals.status_code}: {r_accruals.text}"
    )
    assert r_accruals.json()["code"] == "forbidden"

    # POST /accruals/{random_uuid}/mark-paid → 403 (RBAC fires before 404)
    r_mark_paid = await authed_client_reception.post(
        f"/api/v1/payroll/accruals/{uuid4()}/mark-paid",
        headers=_csrf(authed_client_reception),
    )
    assert r_mark_paid.status_code == 403, (
        f"Expected 403, got {r_mark_paid.status_code}: {r_mark_paid.text}"
    )
    assert r_mark_paid.json()["code"] == "forbidden"
