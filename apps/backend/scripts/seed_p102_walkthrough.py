"""Idempotent seed for the P102 (bookings + payroll) walkthrough prerequisite graph.

Creates the full data set required by the booking lifecycle (create → cancel →
complete-via-pt-session) and trainer payroll (comp-config → preview → run → paid)
walkthroughs.  This is the committed repeatable deliverable that closes the v3.0
``data-setup-blocked`` root cause (Phase 110 criterion #4).

Run this script AFTER ``seed_demo_data`` (the bootstrap owner must exist):

    cd apps/backend
    uv run python -m scripts.seed_demo_data
    uv run python -m scripts.seed_p102_walkthrough

Environment:
    SEED_OWNER_EMAIL      — owner login email (same as used by seed_demo_data)
    SEED_OWNER_PASSWORD   — owner password (≥ 12 chars, NIST 800-63B 2024)

Both vars are REQUIRED; the script exits 1 with a clear message if either is absent
or the password is shorter than 12 characters.

TM-29-02 guard: the script refuses to run unless DATABASE_URL contains 'localhost'
or 'postgres:5432', preventing accidental execution against staging/prod.

Idempotency: every row is keyed by a uuid5-deterministic PK; each INSERT uses
ON CONFLICT (id) DO NOTHING so re-runs are true no-ops (no integrity errors, no
duplicate rows).

Entities seeded (in dependency order):
    1. Trainer          — "P102 Walkthrough Trainer" (active)
    2. TrainerAvailabilitySlot — future Monday 10:00 MSK, 1 h, status='active'
    3. PtPackagePlan    — "P102 PT 10 Sessions" (10 sessions, 1 500 ₽, 90 days)
    4. Client           — "P102 Walkthrough Client" (phone seeded deterministically)
    5. PtPackage        — trainer-matched, active, sessions_remaining=5, validity covers slot
    6. TrainerCompConfig — 10% commission + 500 ₽/session fee, effective 2026-01-01
    7. Payment          — subject_kind='pt_package', POSITIVE amount (payroll revenue)
    8. PtSession        — non-cancelled, performed_at=2026-04-15 UTC (inside payroll period)
                          Links PACKAGE_ID + TRAINER_ID so payroll EXISTS subquery returns >0
                          rows and revenue/accrual are non-zero (fixes false-positive walkthrough).
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.permissions import Role
from app.modules.auth.models import User
from app.modules.clients.models import Client
from app.modules.payments.models import Payment
from app.modules.payroll.models import TrainerCompConfig
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.pt_sessions.models import PtSession
from app.modules.schedule.models import TrainerAvailabilitySlot
from app.modules.trainers.models import Trainer

_UTC = ZoneInfo("UTC")
_MSK = ZoneInfo("Europe/Moscow")

# ---------------------------------------------------------------------------
# Deterministic PK namespace — all IDs are uuid5(NAMESPACE_URL, "p102-walkthrough:<name>")
# so re-runs produce identical PKs and ON CONFLICT DO NOTHING is a true no-op.
# ---------------------------------------------------------------------------
_NS = uuid.NAMESPACE_URL

TRAINER_ID = uuid.uuid5(_NS, "p102-walkthrough:trainer")
SLOT_ID = uuid.uuid5(_NS, "p102-walkthrough:slot")
PLAN_ID = uuid.uuid5(_NS, "p102-walkthrough:plan")
CLIENT_ID = uuid.uuid5(_NS, "p102-walkthrough:client")
PACKAGE_ID = uuid.uuid5(_NS, "p102-walkthrough:package")
COMP_CONFIG_ID = uuid.uuid5(_NS, "p102-walkthrough:comp-config")
PAYMENT_ID = uuid.uuid5(_NS, "p102-walkthrough:payment")
PT_SESSION_ID = uuid.uuid5(_NS, "p102-walkthrough:pt-session")

# Slot anchor: Monday 10:00 MSK → next Monday relative to seed-time (always future).
# Mirrors test_booking_race.py:207-214 «next Monday» math so the slot is guaranteed
# inside the Mon-Fri working-hours window the booking service enforces.
def _next_monday_10_msk() -> datetime:
    now_msk = datetime.now(_MSK)
    # days_ahead: 0 on Monday wraps to 7 so the slot is always at least 1 day away.
    days_ahead = (7 - now_msk.weekday()) % 7 or 7
    slot_msk = now_msk.replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(
        days=days_ahead
    )
    return slot_msk.astimezone(_UTC)


# Payment / payroll period anchor — matches PERFORMED_AT in test_payroll_accruals.py.
_PAYMENT_AT = datetime(2026, 4, 15, 10, 0, 0, tzinfo=_UTC)

# Comp-config effective_from matches the payroll conftest exemplar (2026-01-01).
_COMP_EFFECTIVE_FROM = date(2026, 1, 1)

# Plan / package economics (in kopecks; money in integer minor units per project convention).
_PLAN_PRICE_KOPECKS = 1_500_00  # 1 500 ₽
_PLAN_SESSION_COUNT = 10
_PLAN_VALIDITY_DAYS = 90
_PKG_SESSIONS_REMAINING = 5  # > 0, satisfies booking guard
_COMP_COMMISSION_BPS = 1_000  # 10% in basis points
_COMP_SESSION_FEE_KOPECKS = 500_00  # 500 ₽/session


async def _run() -> int:
    # --- Env validation (THREAT-110-02 / THREAT-110-03) ----------------------
    email = os.environ.get("SEED_OWNER_EMAIL")
    password = os.environ.get("SEED_OWNER_PASSWORD")
    if not email or not password:
        print(
            "ERROR: SEED_OWNER_EMAIL and SEED_OWNER_PASSWORD must be set "
            "(see .env.example).",
            file=sys.stderr,
        )
        return 1
    if len(password) < 12:
        print(
            "ERROR: SEED_OWNER_PASSWORD must be at least 12 characters "
            "(NIST 800-63B 2024).",
            file=sys.stderr,
        )
        return 1

    settings = get_settings()
    db_url = str(settings.database_url)

    # --- TM-29-02 guard (THREAT-110-01) — refuse non-local DB ---------------
    if "localhost" not in db_url and "postgres:5432" not in db_url:
        print(
            "ERROR: seed_p102_walkthrough refuses to run against a non-local "
            "DATABASE_URL (TM-29-02). Expected 'localhost' or 'postgres:5432' in the URL.",
            file=sys.stderr,
        )
        return 1

    engine = create_async_engine(db_url)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker() as session:
            # --- Resolve bootstrap owner (must exist from seed_demo_data) -----
            owner = await session.scalar(
                select(User)
                .where(User.role == Role.OWNER)
                .where(User.email == email.lower())
                .order_by(User.created_at)
            )
            if owner is None:
                print(
                    f"ERROR: no owner with email '{email}' found. "
                    "Run `uv run python -m scripts.seed_demo_data` first.",
                    file=sys.stderr,
                )
                return 1

            # 1. Trainer -------------------------------------------------------
            trainer_stmt = (
                pg_insert(Trainer)
                .values(
                    id=TRAINER_ID,
                    full_name="P102 Walkthrough Trainer",
                    is_active=True,
                    phone="+79001020102",
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
            await session.execute(trainer_stmt)

            # 2. TrainerAvailabilitySlot (future Monday 10:00 MSK → UTC) ------
            slot_start = _next_monday_10_msk()
            slot_end = slot_start + timedelta(hours=1)
            slot_stmt = (
                pg_insert(TrainerAvailabilitySlot)
                .values(
                    id=SLOT_ID,
                    trainer_id=TRAINER_ID,
                    start_time=slot_start,
                    end_time=slot_end,
                    status="active",
                    created_by_user_id=owner.id,
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
            await session.execute(slot_stmt)

            # 3. PtPackagePlan -------------------------------------------------
            plan_stmt = (
                pg_insert(PtPackagePlan)
                .values(
                    id=PLAN_ID,
                    name="P102 PT 10 Sessions",
                    session_count=_PLAN_SESSION_COUNT,
                    price_kopecks=_PLAN_PRICE_KOPECKS,
                    validity_days=_PLAN_VALIDITY_DAYS,
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
            await session.execute(plan_stmt)

            # 4. Client --------------------------------------------------------
            client_stmt = (
                pg_insert(Client)
                .values(
                    id=CLIENT_ID,
                    last_name="P102",
                    first_name="Walkthrough",
                    phone="+79001020103",
                    created_by_user_id=owner.id,
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
            await session.execute(client_stmt)

            # 5. PtPackage — trainer-matched, active, validity covers slot -----
            today_msk = datetime.now(_MSK).date()
            pkg_end_date = today_msk + timedelta(days=_PLAN_VALIDITY_DAYS - 1)
            pkg_stmt = (
                pg_insert(PtPackage)
                .values(
                    id=PACKAGE_ID,
                    client_id=CLIENT_ID,
                    plan_id=PLAN_ID,
                    trainer_id=TRAINER_ID,  # trainer-matched: C-08 guard passes
                    plan_name_snapshot="P102 PT 10 Sessions",
                    session_count_snapshot=_PLAN_SESSION_COUNT,
                    price_kopecks_snapshot=_PLAN_PRICE_KOPECKS,
                    validity_days_snapshot=_PLAN_VALIDITY_DAYS,
                    sessions_remaining=_PKG_SESSIONS_REMAINING,
                    status="active",
                    start_date=today_msk,
                    end_date=pkg_end_date,
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
            await session.execute(pkg_stmt)

            # 6. TrainerCompConfig — 10% commission + 500 ₽/session fee --------
            comp_stmt = (
                pg_insert(TrainerCompConfig)
                .values(
                    id=COMP_CONFIG_ID,
                    trainer_id=TRAINER_ID,
                    commission_pct_bps=_COMP_COMMISSION_BPS,
                    session_fee_kopecks=_COMP_SESSION_FEE_KOPECKS,
                    effective_from=_COMP_EFFECTIVE_FROM,
                    created_by_user_id=owner.id,
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
            await session.execute(comp_stmt)

            # 7. Payment — subject_kind='pt_package', POSITIVE amount (revenue) -
            # CHECK ck_payments_amount_sign_matches_subject_kind: pt_package > 0 ✓
            # received_at within the payroll period 2026-04-01..2026-04-30 so
            # payroll preview/accrual picks it up.
            payment_stmt = (
                pg_insert(Payment)
                .values(
                    id=PAYMENT_ID,
                    subject_kind="pt_package",
                    subject_id=PACKAGE_ID,
                    amount_kopecks=_PLAN_PRICE_KOPECKS,  # positive — passes sign CHECK
                    method="cash",
                    received_at=_PAYMENT_AT,
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
            await session.execute(payment_stmt)

            # 8. PtSession — links the package to the period for payroll revenue
            # attribution.  The payroll repository's fetch_trainer_session_revenue
            # uses an EXISTS subquery that requires at least one non-cancelled
            # pt_session in the period for PACKAGE_ID; without this row the EXISTS
            # returns no rows and commission_revenue_kopecks = 0 (false positive).
            # performed_at = _PAYMENT_AT (2026-04-15 10:00 UTC) is inside the
            # standard walkthrough payroll window 2026-04-01..2026-04-30.
            session_stmt = (
                pg_insert(PtSession)
                .values(
                    id=PT_SESSION_ID,
                    pt_package_id=PACKAGE_ID,
                    trainer_id=TRAINER_ID,
                    client_id=CLIENT_ID,
                    performed_at=_PAYMENT_AT,
                    performed_by_user_id=owner.id,
                    trainer_name_snapshot="P102 Walkthrough Trainer",
                    cancelled_at=None,
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
            await session.execute(session_stmt)

            await session.commit()

    finally:
        await engine.dispose()

    # Print summary of seeded IDs — NEVER print password or hash (THREAT-110-03).
    print("seed_p102_walkthrough: idempotent seed complete.")
    print(f"  trainer_id       = {TRAINER_ID}")
    print(f"  slot_id          = {SLOT_ID}")
    print(f"  pt_package_plan  = {PLAN_ID}")
    print(f"  client_id        = {CLIENT_ID}")
    print(f"  pt_package_id    = {PACKAGE_ID}")
    print(f"  comp_config_id   = {COMP_CONFIG_ID}")
    print(f"  payment_id       = {PAYMENT_ID}")
    print(f"  pt_session_id    = {PT_SESSION_ID}")
    # NOTE: slot_start is recomputed each run; the DB row is written only on the
    # first run (ON CONFLICT DO NOTHING), so on idempotent re-runs the printed
    # value may differ from the stored DB value.  Use SLOT_ID (above) as the
    # canonical reference — not slot_start — when configuring the walkthrough.
    print(
        f"  slot_start (UTC) = {slot_start.isoformat()}"
        " (computed this run; may differ from DB on re-runs)"
    )
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
