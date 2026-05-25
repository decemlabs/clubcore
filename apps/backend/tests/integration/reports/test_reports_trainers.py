"""Integration tests for GET /api/v1/reports/trainers + GET /api/v1/reports/trainers.csv
(Phase 60 RPT-01..04).

Coverage:
  test_owner_gets_trainer_usage_report              RPT-01..04 happy path — 200 + envelope shape
  test_reception_forbidden_on_trainers_json         RPT-01 reception 403
  test_reception_forbidden_on_trainers_csv          RPT-03 reception 403
  test_to_date_before_from_date_returns_422         RPT-01 validation (to<from)
  test_range_over_366_days_returns_report_range_too_large  D-06 range cap
  test_pitfall_11_deactivated_trainer_appears_in_report    PITFALL 11 / D-60-03
  test_pitfall_12_session_on_to_date_included_session_after_excluded  PITFALL 12 / VER-02
  test_pitfall_6_revenue_attributed_to_assigned_trainer_not_conducting  PITFALL 6 / D-58-21
  test_trainers_ordered_by_session_count_desc_then_name    RPT-01 / D-60-03 deterministic ordering
  test_utilization_pct_null_when_zero_active_slots  D-60-06 null sentinel
  test_utilization_pct_zero_when_slots_but_no_bookings     D-60-06 zero sentinel
  test_walkin_session_contributes_zero_hours        D-60-04 walk-in (booking_id NULL)
  test_rpt04_clawback_nets_in_total_accrued         RPT-04 / D-58-03 signed sum
  test_rpt04_payroll_overlap_includes_straddling_periods   D-60-05 overlap semantics
  test_trainers_csv_bom_and_content_type            RPT-03 / EXP-04
  test_trainers_csv_header_row_matches_constant     RPT-03 header lock
  test_trainers_csv_cyrillic_trainer_name_round_trip       RPT-03 / EXP-04
  test_trainers_csv_formula_injection_sanitized     T-56-07 / CR-01
  test_trainers_csv_utilization_null_renders_empty_cell    D-60-11
  test_pitfall_10_no_orm_imports_in_reports_module  PITFALL 10 / D-60-01 / RPT-04 ship gate

Wire format: ?fromDate=YYYY-MM-DD&toDate=YYYY-MM-DD
(BackendSchemaBase alias_generator=to_camel maps from_date->fromDate, to_date->toDate)

Fixtures: authed_client_owner, authed_client_reception, db_session, seeded_owner, make_client,
  make_payment_ledger — auto-discovered via tests/integration/reports/conftest.py.
"""

from __future__ import annotations

import csv
import io
import subprocess
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payroll.models import TrainerCompConfig, TrainerPayrollAccrual
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.pt_sessions.models import PtSession
from app.modules.reports.constants import CSV_TRAINER_USAGE_HEADERS, TRAINER_REPORT_REVENUE_NOTE
from app.modules.reports.csv_export import BOM
from app.modules.schedule.models import TrainerAvailabilitySlot
from app.modules.trainers.models import Trainer

# ---------------------------------------------------------------------------
# PITFALL 10 path resolution — module-level with is_dir() guard.
#
# parents walk from test file location:
#   parents[0] = tests/integration/reports/
#   parents[1] = tests/integration/
#   parents[2] = tests/
#   parents[3] = apps/backend/
# Target: apps/backend/app/modules/reports/
# ---------------------------------------------------------------------------
REPORTS_DIR = Path(__file__).resolve().parents[3] / "app" / "modules" / "reports"
assert REPORTS_DIR.is_dir(), (
    f"reports module path resolution broken: {REPORTS_DIR!r} — "
    "PITFALL 10 grep guard will silently vacuous-pass against a nonexistent path. "
    "If this test file was moved, update the .parents[3] depth accordingly."
)

# ---------------------------------------------------------------------------
# Local helper — parse CSV text (strip BOM, return list[list[str]])
# ---------------------------------------------------------------------------


def _parse_csv(text: str) -> list[list[str]]:
    """Strip BOM and parse CSV text into rows."""
    return list(csv.reader(io.StringIO(text.lstrip(BOM))))


# ---------------------------------------------------------------------------
# Local factory fixtures — trainer-domain objects not in reports conftest.
#
# D-60-13: no new conftest fixtures; keep these local to this test file.
# Imports from app.modules.* are permitted in test files (not ORM cross-module
# discipline which applies only to app/modules/reports/ source code).
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_trainer(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[Trainer]]:
    """Insert a Trainer row directly via the SAVEPOINT-mode session."""
    _counter: dict[str, int] = {"i": 0}

    async def _make(
        *,
        full_name: str | None = None,
        is_active: bool = True,
        phone: str | None = None,
    ) -> Trainer:
        _counter["i"] += 1
        trainer = Trainer(
            full_name=full_name or f"RPT04-Trainer-{_counter['i']}",
            is_active=is_active,
            phone=phone,
        )
        db_session.add(trainer)
        await db_session.commit()
        await db_session.refresh(trainer)
        return trainer

    return _make


@pytest_asyncio.fixture
async def make_pt_package_plan(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[PtPackagePlan]]:
    """Insert a PtPackagePlan directly."""
    _counter: dict[str, int] = {"i": 0}

    async def _make(
        *,
        name: str | None = None,
        session_count: int = 10,
        price_kopecks: int = 500000,
        validity_days: int | None = 90,
    ) -> PtPackagePlan:
        _counter["i"] += 1
        plan = PtPackagePlan(
            name=name or f"RPT04-Plan-{_counter['i']}",
            session_count=session_count,
            price_kopecks=price_kopecks,
            validity_days=validity_days,
        )
        db_session.add(plan)
        await db_session.commit()
        await db_session.refresh(plan)
        return plan

    return _make


@pytest_asyncio.fixture
async def make_pt_package_with_trainer(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[PtPackage]]:
    """Insert a PtPackage with an explicit trainer_id (assigned-at-sale — D-58-21)."""

    async def _make(
        *,
        client_id: UUID,
        plan: PtPackagePlan,
        trainer_id: UUID | None = None,
        status: str = "active",
    ) -> PtPackage:
        today = datetime.now(tz=UTC).date()
        end = (
            today + timedelta(days=plan.validity_days - 1)
            if plan.validity_days is not None
            else None
        )
        pkg = PtPackage(
            client_id=client_id,
            plan_id=plan.id,
            plan_name_snapshot=plan.name,
            session_count_snapshot=plan.session_count,
            price_kopecks_snapshot=plan.price_kopecks,
            validity_days_snapshot=plan.validity_days,
            sessions_remaining=plan.session_count,
            status=status,
            start_date=today,
            end_date=end,
            trainer_id=trainer_id,
        )
        db_session.add(pkg)
        await db_session.commit()
        await db_session.refresh(pkg)
        return pkg

    return _make


@pytest_asyncio.fixture
async def make_pt_session(
    db_session: AsyncSession,
    seeded_owner: Any,
) -> Callable[..., Awaitable[PtSession]]:
    """Insert a PtSession row directly via the SAVEPOINT-mode session.

    D-60-04: walk-in sessions have booking_id=None and contribute 0.0 hours.
    seeded_owner is required for performed_by_user_id (NOT NULL FK).
    """

    async def _make(
        *,
        pt_package_id: UUID,
        trainer_id: UUID,
        client_id: UUID,
        performed_at: datetime,
        trainer_name_snapshot: str = "Test Trainer",
        cancelled_at: datetime | None = None,
        booking_id: UUID | None = None,
    ) -> PtSession:
        session_row = PtSession(
            pt_package_id=pt_package_id,
            trainer_id=trainer_id,
            client_id=client_id,
            performed_at=performed_at,
            performed_by_user_id=seeded_owner.id,
            trainer_name_snapshot=trainer_name_snapshot,
            cancelled_at=cancelled_at,
            booking_id=booking_id,
        )
        db_session.add(session_row)
        await db_session.commit()
        await db_session.refresh(session_row)
        return session_row

    return _make


@pytest_asyncio.fixture
async def make_slot(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[TrainerAvailabilitySlot]]:
    """Insert a TrainerAvailabilitySlot directly via the SAVEPOINT-mode session."""

    async def _make(
        *,
        trainer_id: UUID,
        start_time: datetime,
        end_time: datetime,
        status: str = "active",
    ) -> TrainerAvailabilitySlot:
        slot = TrainerAvailabilitySlot(
            trainer_id=trainer_id,
            start_time=start_time,
            end_time=end_time,
            status=status,
        )
        db_session.add(slot)
        await db_session.commit()
        await db_session.refresh(slot)
        return slot

    return _make


@pytest_asyncio.fixture
async def make_accrual_row(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[TrainerPayrollAccrual]]:
    """Insert a TrainerPayrollAccrual with its comp_config dependency.

    Creates a companion TrainerCompConfig row automatically so callers only
    need to supply the business-level fields (trainer_id, period, amounts).
    The partial UNIQUE on (trainer_id, period_start, period_end) WHERE
    clawback_of_accrual_id IS NULL means regular accruals must use distinct
    period ranges; clawbacks may share the range with their source accrual.
    """

    async def _make(
        *,
        trainer_id: UUID,
        period_start: date,
        period_end: date,
        accrual_kopecks: int,
        status: str = "pending",
        clawback_of_accrual_id: UUID | None = None,
        source_refund_payment_id: UUID | None = None,
    ) -> TrainerPayrollAccrual:
        # Create a comp config as the FK prerequisite
        config = TrainerCompConfig(
            trainer_id=trainer_id,
            session_fee_kopecks=10000,
            effective_from=period_start,
        )
        db_session.add(config)
        await db_session.commit()
        await db_session.refresh(config)

        accrual = TrainerPayrollAccrual(
            trainer_id=trainer_id,
            period_start=period_start,
            period_end=period_end,
            sessions_count=1,
            revenue_kopecks=0,
            comp_config_id_snapshot=config.id,
            accrual_kopecks=accrual_kopecks,
            status=status,
            clawback_of_accrual_id=clawback_of_accrual_id,
            source_refund_payment_id=source_refund_payment_id,
        )
        db_session.add(accrual)
        await db_session.commit()
        await db_session.refresh(accrual)
        return accrual

    return _make


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_owner_gets_trainer_usage_report(
    authed_client_owner: AsyncClient,
) -> None:
    """Owner GET /reports/trainers returns 200 with ResponseEnvelope[TrainerUsageReportResponse]
    shape including revenueAttributionNote string (RPT-01..04 happy path).
    """
    r = await authed_client_owner.get(
        "/api/v1/reports/trainers",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert isinstance(body["trainers"], list)
    assert body["fromDate"] == "2026-05-01"
    assert body["toDate"] == "2026-05-31"
    assert isinstance(body["revenueAttributionNote"], str)
    assert len(body["revenueAttributionNote"]) > 0
    assert body["revenueAttributionNote"] == TRAINER_REPORT_REVENUE_NOTE


async def test_reception_forbidden_on_trainers_json(
    authed_client_reception: AsyncClient,
) -> None:
    """(VIEW, REPORTS) ∈ OWNER_ONLY → reception receives 403 on JSON endpoint (RPT-01, SC#4)."""
    r = await authed_client_reception.get(
        "/api/v1/reports/trainers",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_reception_forbidden_on_trainers_csv(
    authed_client_reception: AsyncClient,
) -> None:
    """(VIEW, REPORTS) ∈ OWNER_ONLY → reception receives 403 on CSV endpoint (RPT-03, SC#4)."""
    r = await authed_client_reception.get(
        "/api/v1/reports/trainers.csv",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_to_date_before_from_date_returns_422(
    authed_client_owner: AsyncClient,
) -> None:
    """toDate < fromDate → 422 validation error (RPT-01 / D-05)."""
    r = await authed_client_owner.get(
        "/api/v1/reports/trainers",
        params={"fromDate": "2026-05-31", "toDate": "2026-05-01"},
    )
    assert r.status_code == 422, r.text


async def test_range_over_366_days_returns_report_range_too_large(
    authed_client_owner: AsyncClient,
) -> None:
    """Range > 366 days → 422 with code 'report_range_too_large' (D-06)."""
    r = await authed_client_owner.get(
        "/api/v1/reports/trainers",
        params={"fromDate": "2024-01-01", "toDate": "2026-01-01"},
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "report_range_too_large"


async def test_pitfall_11_deactivated_trainer_appears_in_report(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_pt_package_plan: Any,
    make_pt_package_with_trainer: Any,
    make_pt_session: Any,
    make_client: Any,
) -> None:
    """PITFALL 11 (D-60-03): trainer with is_active=False and historical sessions in period
    MUST appear in the report — NO is_active filter on the LEFT JOIN over trainers.
    """
    deactivated = await make_trainer(
        full_name="Деактивированный Тренер",
        is_active=False,
    )
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package_with_trainer(
        client_id=client.id,
        plan=plan,
        trainer_id=deactivated.id,
    )
    ts = datetime(2026, 5, 15, 10, 0, 0, tzinfo=UTC)
    await make_pt_session(
        pt_package_id=pkg.id,
        trainer_id=deactivated.id,
        client_id=client.id,
        performed_at=ts,
        trainer_name_snapshot=deactivated.full_name,
    )
    await make_pt_session(
        pt_package_id=pkg.id,
        trainer_id=deactivated.id,
        client_id=client.id,
        performed_at=ts + timedelta(hours=2),
        trainer_name_snapshot=deactivated.full_name,
    )

    r = await authed_client_owner.get(
        "/api/v1/reports/trainers",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 200, r.text
    trainers_list = r.json()["data"]["trainers"]
    trainer_ids = [t["trainerId"] for t in trainers_list]
    assert str(deactivated.id) in trainer_ids, (
        f"Deactivated trainer {deactivated.id} must appear in report "
        f"(PITFALL 11). Found trainer_ids: {trainer_ids}"
    )
    row = next(t for t in trainers_list if t["trainerId"] == str(deactivated.id))
    assert row["sessionCount"] == 2, f"Expected sessionCount=2, got {row['sessionCount']}"


async def test_pitfall_12_session_on_to_date_included_session_after_excluded(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_pt_package_plan: Any,
    make_pt_package_with_trainer: Any,
    make_pt_session: Any,
    make_client: Any,
) -> None:
    """PITFALL 12 (mirrors VER-02): session on to_date=2026-05-31 (MSK) is INCLUDED;
    session on 2026-06-01 MSK (=2026-05-31 21:30 UTC) is EXCLUDED from the
    [fromDate, toDate] BETWEEN filter using AT TIME ZONE 'Europe/Moscow'.
    """
    trainer = await make_trainer(full_name="Граничный Тренер")
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package_with_trainer(
        client_id=client.id,
        plan=plan,
        trainer_id=trainer.id,
    )

    # Session A: 2026-05-31 23:30 MSK = 2026-05-31 20:30 UTC → included (on to_date)
    session_on_to_date = datetime(2026, 5, 31, 20, 30, 0, tzinfo=UTC)
    await make_pt_session(
        pt_package_id=pkg.id,
        trainer_id=trainer.id,
        client_id=client.id,
        performed_at=session_on_to_date,
        trainer_name_snapshot=trainer.full_name,
    )

    # Session B: 2026-06-01 00:30 MSK = 2026-05-31 21:30 UTC → excluded (past to_date)
    session_after_to_date = datetime(2026, 5, 31, 21, 30, 0, tzinfo=UTC)
    await make_pt_session(
        pt_package_id=pkg.id,
        trainer_id=trainer.id,
        client_id=client.id,
        performed_at=session_after_to_date,
        trainer_name_snapshot=trainer.full_name,
    )

    r = await authed_client_owner.get(
        "/api/v1/reports/trainers",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 200, r.text
    trainers_list = r.json()["data"]["trainers"]
    row = next(
        (t for t in trainers_list if t["trainerId"] == str(trainer.id)),
        None,
    )
    assert row is not None, f"Trainer {trainer.id} must appear in report"
    assert row["sessionCount"] == 1, (
        f"PITFALL 12: expected sessionCount=1 (session on to_date included, "
        f"session after excluded), got {row['sessionCount']}"
    )


async def test_pitfall_6_revenue_attributed_to_assigned_trainer_not_conducting(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_pt_package_plan: Any,
    make_pt_package_with_trainer: Any,
    make_pt_session: Any,
    make_client: Any,
    make_payment_ledger: Any,
    seeded_owner: Any,
) -> None:
    """PITFALL 6 (D-58-21): revenue follows pt_packages.trainer_id (assigned at sale),
    NOT pt_sessions.trainer_id (conducting trainer).

    Package is assigned to trainer A; session is conducted by trainer B.
    → trainer A gets revenue; trainer B gets 0 revenue.
    """
    trainer_a = await make_trainer(full_name="Тренер А Назначен")
    trainer_b = await make_trainer(full_name="Тренер Б Проводит")
    client = await make_client()
    plan = await make_pt_package_plan(price_kopecks=100000)
    # Package assigned to trainer A (assigned-at-sale)
    pkg = await make_pt_package_with_trainer(
        client_id=client.id,
        plan=plan,
        trainer_id=trainer_a.id,
    )
    # Session conducted by trainer B (conducting)
    ts = datetime(2026, 5, 15, 10, 0, 0, tzinfo=UTC)
    await make_pt_session(
        pt_package_id=pkg.id,
        trainer_id=trainer_b.id,
        client_id=client.id,
        performed_at=ts,
        trainer_name_snapshot=trainer_b.full_name,
    )
    # Payment for this package (positive amount, subject_kind='pt_package')
    await make_payment_ledger(
        subject_id=pkg.id,
        subject_kind="pt_package",
        amount_kopecks=100000,
        method="cash",
        received_at=ts,
        received_by_user_id=seeded_owner.id,
    )

    r = await authed_client_owner.get(
        "/api/v1/reports/trainers",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 200, r.text
    trainers_list = r.json()["data"]["trainers"]
    row_a = next((t for t in trainers_list if t["trainerId"] == str(trainer_a.id)), None)
    row_b = next((t for t in trainers_list if t["trainerId"] == str(trainer_b.id)), None)

    assert row_a is not None, "Trainer A (assigned at sale) must appear in report"
    assert row_b is not None, "Trainer B (conducting) must appear in report"

    assert row_a["revenueKopecks"] == 100000, (
        f"PITFALL 6: trainer A (assigned at sale) should have revenue=100000, "
        f"got {row_a['revenueKopecks']}"
    )
    assert row_b["revenueKopecks"] == 0, (
        f"PITFALL 6: trainer B (conducting, not assigned) should have revenue=0, "
        f"got {row_b['revenueKopecks']}"
    )


async def test_trainers_ordered_by_session_count_desc_then_name(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_pt_package_plan: Any,
    make_pt_package_with_trainer: Any,
    make_pt_session: Any,
    make_client: Any,
) -> None:
    """RPT-01 / D-60-03: ORDER BY session_count DESC, full_name ASC, trainer_id ASC —
    deterministic golden with deliberate tie on session_count.

    Seeds 4 trainers:
      - "А Алексеев": 5 sessions
      - "Б Борисов":  5 sessions (tie with А Алексеев — broken by full_name ASC)
      - "В Васильев": 3 sessions
      - "Г Григорьев": 0 sessions (LEFT JOIN — appears even with zero sessions)

    Expected order:
      1. А Алексеев  (5) — "А" < "Б" lexicographically
      2. Б Борисов   (5)
      3. В Васильев  (3)
      4. Г Григорьев (0)
    """
    trainer_a = await make_trainer(full_name="А Алексеев")
    trainer_b = await make_trainer(full_name="Б Борисов")
    trainer_v = await make_trainer(full_name="В Васильев")
    trainer_g = await make_trainer(full_name="Г Григорьев")  # 0 sessions

    # Each package needs its own client due to uq_pt_packages_active_per_client UNIQUE
    # constraint (one active PT-package per client — D-33-09).
    client_a = await make_client()
    client_b = await make_client()
    client_v = await make_client()
    plan = await make_pt_package_plan(session_count=10)
    pkg_a = await make_pt_package_with_trainer(
        client_id=client_a.id, plan=plan, trainer_id=trainer_a.id
    )
    pkg_b = await make_pt_package_with_trainer(
        client_id=client_b.id, plan=plan, trainer_id=trainer_b.id
    )
    pkg_v = await make_pt_package_with_trainer(
        client_id=client_v.id, plan=plan, trainer_id=trainer_v.id
    )
    # Г Григорьев deliberately gets no sessions

    base_ts = datetime(2026, 5, 10, 10, 0, 0, tzinfo=UTC)

    # А Алексеев — 5 sessions
    for i in range(5):
        await make_pt_session(
            pt_package_id=pkg_a.id,
            trainer_id=trainer_a.id,
            client_id=client_a.id,
            performed_at=base_ts + timedelta(hours=i),
            trainer_name_snapshot=trainer_a.full_name,
        )

    # Б Борисов — 5 sessions (deliberate tie)
    for i in range(5):
        await make_pt_session(
            pt_package_id=pkg_b.id,
            trainer_id=trainer_b.id,
            client_id=client_b.id,
            performed_at=base_ts + timedelta(hours=i + 10),
            trainer_name_snapshot=trainer_b.full_name,
        )

    # В Васильев — 3 sessions
    for i in range(3):
        await make_pt_session(
            pt_package_id=pkg_v.id,
            trainer_id=trainer_v.id,
            client_id=client_v.id,
            performed_at=base_ts + timedelta(hours=i + 20),
            trainer_name_snapshot=trainer_v.full_name,
        )

    r = await authed_client_owner.get(
        "/api/v1/reports/trainers",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 200, r.text
    all_trainers = r.json()["data"]["trainers"]

    # Extract only our 4 seeded trainers in their returned order
    our_ids = {
        str(trainer_a.id),
        str(trainer_b.id),
        str(trainer_v.id),
        str(trainer_g.id),
    }
    our_rows = [t for t in all_trainers if t["trainerId"] in our_ids]

    assert len(our_rows) == 4, (
        f"Expected all 4 seeded trainers in report, got {len(our_rows)}: "
        f"{[t['trainerNameSnapshot'] for t in our_rows]}"
    )

    # Assert exact (full_name, sessionCount) tuple order
    actual = [(t["trainerNameSnapshot"], t["sessionCount"]) for t in our_rows]
    expected = [
        ("А Алексеев", 5),
        ("Б Борисов", 5),
        ("В Васильев", 3),
        ("Г Григорьев", 0),
    ]
    assert actual == expected, (
        f"Ordering golden failed (D-60-03).\n"
        f"Expected: {expected}\n"
        f"Got:      {actual}"
    )

    # Also assert DESC invariant
    counts = [t["sessionCount"] for t in our_rows]
    assert counts == sorted(counts, reverse=True), (
        f"sessionCount must be DESC-ordered, got {counts}"
    )


async def test_utilization_pct_null_when_zero_active_slots(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_pt_package_plan: Any,
    make_pt_package_with_trainer: Any,
    make_pt_session: Any,
    make_client: Any,
) -> None:
    """D-60-06: trainer with sessions but 0 active|booked trainer_availability_slots
    in the period → utilizationPct must be null (JSON null), NOT 0.
    """
    trainer = await make_trainer(full_name="Без Слотов Тренер")
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package_with_trainer(
        client_id=client.id, plan=plan, trainer_id=trainer.id
    )
    ts = datetime(2026, 5, 15, 10, 0, 0, tzinfo=UTC)
    await make_pt_session(
        pt_package_id=pkg.id,
        trainer_id=trainer.id,
        client_id=client.id,
        performed_at=ts,
        trainer_name_snapshot=trainer.full_name,
    )
    # No TrainerAvailabilitySlot rows for this trainer

    r = await authed_client_owner.get(
        "/api/v1/reports/trainers",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 200, r.text
    trainers_list = r.json()["data"]["trainers"]
    row = next((t for t in trainers_list if t["trainerId"] == str(trainer.id)), None)
    assert row is not None, f"Trainer {trainer.id} must appear"
    assert row["utilizationPct"] is None, (
        f"D-60-06: trainer with 0 active|booked slots must have utilizationPct=null, "
        f"got {row['utilizationPct']!r}"
    )


async def test_utilization_pct_zero_when_slots_but_no_bookings(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_slot: Any,
) -> None:
    """D-60-06: trainer with active slots but 0 booked slots → utilizationPct == 0.0."""
    trainer = await make_trainer(full_name="Активный Слот Тренер")

    # 2 active slots in May 2026 (MSK = UTC+3, so 09:00 MSK = 06:00 UTC)
    slot_start1 = datetime(2026, 5, 10, 6, 0, 0, tzinfo=UTC)   # 09:00 MSK
    slot_end1 = datetime(2026, 5, 10, 7, 0, 0, tzinfo=UTC)     # 10:00 MSK
    await make_slot(
        trainer_id=trainer.id,
        start_time=slot_start1,
        end_time=slot_end1,
        status="active",
    )
    slot_start2 = datetime(2026, 5, 15, 6, 0, 0, tzinfo=UTC)
    slot_end2 = datetime(2026, 5, 15, 7, 0, 0, tzinfo=UTC)
    await make_slot(
        trainer_id=trainer.id,
        start_time=slot_start2,
        end_time=slot_end2,
        status="active",
    )

    r = await authed_client_owner.get(
        "/api/v1/reports/trainers",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 200, r.text
    trainers_list = r.json()["data"]["trainers"]
    row = next((t for t in trainers_list if t["trainerId"] == str(trainer.id)), None)
    assert row is not None, f"Trainer {trainer.id} must appear in report"
    assert row["utilizationPct"] == 0.0, (
        f"D-60-06: trainer with active slots but 0 bookings must have utilizationPct=0.0, "
        f"got {row['utilizationPct']!r}"
    )


async def test_walkin_session_contributes_zero_hours(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_pt_package_plan: Any,
    make_pt_package_with_trainer: Any,
    make_pt_session: Any,
    make_client: Any,
) -> None:
    """D-60-04: pt_session with booking_id=NULL (walk-in) counts in sessionCount but
    contributes 0.0 to totalHours — no canonical slot duration to derive from.
    """
    trainer = await make_trainer(full_name="Вокин Тренер")
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package_with_trainer(
        client_id=client.id, plan=plan, trainer_id=trainer.id
    )
    ts = datetime(2026, 5, 20, 10, 0, 0, tzinfo=UTC)
    await make_pt_session(
        pt_package_id=pkg.id,
        trainer_id=trainer.id,
        client_id=client.id,
        performed_at=ts,
        trainer_name_snapshot=trainer.full_name,
        booking_id=None,  # walk-in: no booking
    )

    r = await authed_client_owner.get(
        "/api/v1/reports/trainers",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 200, r.text
    trainers_list = r.json()["data"]["trainers"]
    row = next((t for t in trainers_list if t["trainerId"] == str(trainer.id)), None)
    assert row is not None
    assert row["sessionCount"] == 1, "Walk-in session must count in sessionCount"
    assert row["totalHours"] == 0.0, (
        f"D-60-04: walk-in session (booking_id NULL) must contribute 0.0 totalHours, "
        f"got {row['totalHours']!r}"
    )


async def test_rpt04_clawback_nets_in_total_accrued(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_accrual_row: Any,
    make_client: Any,
    make_payment_ledger: Any,
    seeded_owner: Any,
) -> None:
    """RPT-04 / D-58-03: positive accrual + negative clawback → totalAccruedKopecks = net."""
    trainer = await make_trainer(full_name="Клобэк Тренер")
    client = await make_client()

    # Positive accrual: +50000 (distinct period for UNIQUE constraint)
    accrual = await make_accrual_row(
        trainer_id=trainer.id,
        period_start=date(2026, 5, 1),
        period_end=date(2026, 5, 31),
        accrual_kopecks=50000,
        status="pending",
    )
    # Create a real refund payment row — source_refund_payment_id is FK to payments.id;
    # CheckConstraint clawback_fks_paired requires both clawback_of_accrual_id and
    # source_refund_payment_id to be non-NULL together (cannot reuse a dummy UUID).
    refund_payment = await make_payment_ledger(
        subject_id=client.id,
        subject_kind="refund",
        amount_kopecks=-30000,
        method="cash",
        received_at=datetime(2026, 5, 20, 10, 0, 0, tzinfo=UTC),
        received_by_user_id=seeded_owner.id,
    )
    # Negative clawback: -30000 (uses different period dates to avoid UNIQUE conflict;
    # partial UNIQUE on (trainer_id, period_start, period_end) WHERE clawback IS NULL
    # only applies to regular accruals — clawbacks bypass the constraint)
    await make_accrual_row(
        trainer_id=trainer.id,
        period_start=date(2026, 5, 2),
        period_end=date(2026, 5, 28),
        accrual_kopecks=-30000,
        status="pending",
        clawback_of_accrual_id=accrual.id,
        source_refund_payment_id=refund_payment.id,
    )

    r = await authed_client_owner.get(
        "/api/v1/reports/trainers",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 200, r.text
    trainers_list = r.json()["data"]["trainers"]
    row = next((t for t in trainers_list if t["trainerId"] == str(trainer.id)), None)
    assert row is not None, f"Trainer {trainer.id} must appear in report"
    assert row["totalAccruedKopecks"] == 20000, (
        f"RPT-04 clawback netting: expected totalAccruedKopecks=20000 "
        f"(50000 - 30000), got {row['totalAccruedKopecks']}"
    )


async def test_rpt04_payroll_overlap_includes_straddling_periods(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_accrual_row: Any,
) -> None:
    """D-60-05: accrual whose period straddles the report window boundary contributes
    its FULL amount (no proration). period_start=2026-04-15, period_end=2026-05-15
    overlaps with fromDate=2026-05-01 → full 75000 kopecks appears in totalAccruedKopecks.
    """
    trainer = await make_trainer(full_name="Страддлинг Тренер")
    # Accrual period straddles fromDate=2026-05-01
    await make_accrual_row(
        trainer_id=trainer.id,
        period_start=date(2026, 4, 15),
        period_end=date(2026, 5, 15),
        accrual_kopecks=75000,
        status="pending",
    )

    r = await authed_client_owner.get(
        "/api/v1/reports/trainers",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 200, r.text
    trainers_list = r.json()["data"]["trainers"]
    row = next((t for t in trainers_list if t["trainerId"] == str(trainer.id)), None)
    assert row is not None, f"Trainer {trainer.id} must appear in report"
    assert row["totalAccruedKopecks"] == 75000, (
        f"D-60-05 overlap (non-prorated): expected totalAccruedKopecks=75000 "
        f"(full amount, not prorated), got {row['totalAccruedKopecks']}"
    )


async def test_trainers_csv_bom_and_content_type(
    authed_client_owner: AsyncClient,
) -> None:
    """RPT-03 / EXP-04: GET /reports/trainers.csv → 200; text/csv; body starts with
    UTF-8 BOM (U+FEFF, first char == chr(0xFEFF)).
    """
    r = await authed_client_owner.get(
        "/api/v1/reports/trainers.csv",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv"), (
        f"Expected text/csv content-type, got {r.headers['content-type']!r}"
    )
    assert r.text[0] == BOM, f"Expected BOM as first char, got {r.text[0]!r}"
    assert ord(r.text[0]) == 0xFEFF, f"BOM must be U+FEFF, got U+{ord(r.text[0]):04X}"


async def test_trainers_csv_header_row_matches_constant(
    authed_client_owner: AsyncClient,
) -> None:
    """RPT-03: first data row (after BOM) equals list(CSV_TRAINER_USAGE_HEADERS) exactly
    — locks the 10-column header order.
    """
    r = await authed_client_owner.get(
        "/api/v1/reports/trainers.csv",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 200, r.text
    rows = _parse_csv(r.text)
    assert len(rows) >= 1, "CSV must have at least a header row"
    header_row = rows[0]
    assert header_row == list(CSV_TRAINER_USAGE_HEADERS), (
        f"CSV header mismatch.\n"
        f"Expected: {list(CSV_TRAINER_USAGE_HEADERS)}\n"
        f"Got:      {header_row}"
    )


async def test_trainers_csv_cyrillic_trainer_name_round_trip(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_pt_package_plan: Any,
    make_pt_package_with_trainer: Any,
    make_pt_session: Any,
    make_client: Any,
) -> None:
    """RPT-03 / EXP-04: Cyrillic trainer full_name appears verbatim in CSV body after BOM."""
    cyrillic_name = "Иван Петров"
    trainer = await make_trainer(full_name=cyrillic_name)
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package_with_trainer(
        client_id=client.id, plan=plan, trainer_id=trainer.id
    )
    ts = datetime(2026, 5, 14, 10, 0, 0, tzinfo=UTC)
    await make_pt_session(
        pt_package_id=pkg.id,
        trainer_id=trainer.id,
        client_id=client.id,
        performed_at=ts,
        trainer_name_snapshot=cyrillic_name,
    )

    r = await authed_client_owner.get(
        "/api/v1/reports/trainers.csv",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 200, r.text
    assert cyrillic_name in r.text, (
        f"Cyrillic trainer name '{cyrillic_name}' must appear verbatim in CSV output"
    )


async def test_trainers_csv_formula_injection_sanitized(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_pt_package_plan: Any,
    make_pt_package_with_trainer: Any,
    make_pt_session: Any,
    make_client: Any,
) -> None:
    """T-56-07 / CR-01: trainer full_name starting with '=' is sanitized in CSV —
    cell is prefixed with apostrophe per sanitize_csv_text.
    """
    malicious_name = "=cmd|'/C calc'!A0"
    trainer = await make_trainer(full_name=malicious_name)
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package_with_trainer(
        client_id=client.id, plan=plan, trainer_id=trainer.id
    )
    ts = datetime(2026, 5, 13, 10, 0, 0, tzinfo=UTC)
    await make_pt_session(
        pt_package_id=pkg.id,
        trainer_id=trainer.id,
        client_id=client.id,
        performed_at=ts,
        trainer_name_snapshot=malicious_name,
    )

    r = await authed_client_owner.get(
        "/api/v1/reports/trainers.csv",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 200, r.text
    rows = _parse_csv(r.text)

    # Find the row for our trainer (trainerNameSnapshot is column index 0)
    name_col = list(CSV_TRAINER_USAGE_HEADERS).index("trainerNameSnapshot")
    trainer_rows = [
        row for row in rows[1:]
        if row and len(row) > name_col and malicious_name in row[name_col]
    ]
    assert trainer_rows, (
        f"Row with formula-injection trainer name must be present in CSV. "
        f"rows[1:] = {rows[1:]!r}"
    )
    cell = trainer_rows[0][name_col]
    assert cell == f"'{malicious_name}", (
        f"Formula-injection cell must be quote-prefixed, got {cell!r}"
    )
    assert not cell.startswith("="), "Sanitized cell must not start with a formula trigger"


async def test_trainers_csv_utilization_null_renders_empty_cell(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_pt_package_plan: Any,
    make_pt_package_with_trainer: Any,
    make_pt_session: Any,
    make_client: Any,
) -> None:
    """D-60-11: utilization_pct=NULL (trainer with sessions, 0 slots) renders as
    empty CSV cell (delimiter-delimiter pair), NOT "None" or "NULL".
    """
    trainer = await make_trainer(full_name="Нуль Утилизация Тренер")
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package_with_trainer(
        client_id=client.id, plan=plan, trainer_id=trainer.id
    )
    ts = datetime(2026, 5, 12, 10, 0, 0, tzinfo=UTC)
    await make_pt_session(
        pt_package_id=pkg.id,
        trainer_id=trainer.id,
        client_id=client.id,
        performed_at=ts,
        trainer_name_snapshot=trainer.full_name,
    )
    # No slots → utilization_pct=None

    r = await authed_client_owner.get(
        "/api/v1/reports/trainers.csv",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 200, r.text
    rows = _parse_csv(r.text)
    util_col = list(CSV_TRAINER_USAGE_HEADERS).index("utilizationPct")
    name_col = list(CSV_TRAINER_USAGE_HEADERS).index("trainerNameSnapshot")

    trainer_rows = [
        row for row in rows[1:]
        if row and len(row) > name_col and trainer.full_name in row[name_col]
    ]
    assert trainer_rows, f"Trainer row must be present. rows[1:] = {rows[1:]!r}"
    util_cell = trainer_rows[0][util_col]
    assert util_cell == "", (
        f"D-60-11: utilizationPct=NULL must render as empty CSV cell, "
        f"got {util_cell!r} (must NOT be 'None' or 'NULL')"
    )
    assert util_cell != "None", "CSV null must not serialize as literal 'None'"
    assert util_cell != "NULL", "CSV null must not serialize as literal 'NULL'"


async def test_pitfall_10_no_orm_imports_in_reports_module() -> None:
    """PITFALL 10 (D-60-01 / D-60-02 / RPT-04 ship gate): zero cross-module ORM imports
    in apps/backend/app/modules/reports/ — raw SQL text() only (D-REPORT-READONLY).

    Uses module-level REPORTS_DIR (pathlib-derived, import-time is_dir() assertion).
    The grep returns exit code 1 when no matches are found (PASS).
    Also asserts lint-imports exit 0 (RPT-04 acceptance criterion).
    """
    # REPORTS_DIR is module-level (pathlib, parents[3] / "app" / "modules" / "reports").
    # The module-level `assert REPORTS_DIR.is_dir()` guarantees the path is real.
    pattern = (
        r"from app\.modules\."
        r"(pt_sessions|trainers|payments|payroll|schedule|bookings|pt_packages)"
        r"\.models"
    )
    result = subprocess.run(
        ["grep", "-rE", pattern, str(REPORTS_DIR)],
        capture_output=True,
        text=True,
        check=False,
    )
    # grep returncode: 0 = match found (FAIL), 1 = no match (PASS), 2 = error
    assert result.returncode == 1, (
        f"PITFALL 10: unexpected ORM cross-module imports in reports/ "
        f"(returncode={result.returncode}):\n"
        f"stdout={result.stdout!r}\n"
        f"stderr={result.stderr!r}\n"
        f"REPORTS_DIR={REPORTS_DIR}"
    )
    assert result.stdout == "", (
        f"PITFALL 10: grep stdout must be empty when no ORM imports found, "
        f"got {result.stdout!r}"
    )

    # Also assert lint-imports exit 0 (RPT-04 ship gate — zero new ignore_imports edges)
    # Use `uv run lint-imports` to ensure the virtualenv's lint-imports binary is found
    # (mirrors test_importlinter_negative_fixture.py subprocess pattern).
    lint_result = subprocess.run(
        ["uv", "run", "lint-imports"],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(REPORTS_DIR.parents[2]),  # apps/backend/ (REPORTS_DIR = .../app/modules/reports)
    )
    assert lint_result.returncode == 0, (
        f"lint-imports failed (RPT-04 ship gate):\n"
        f"stdout={lint_result.stdout}\n"
        f"stderr={lint_result.stderr}"
    )
