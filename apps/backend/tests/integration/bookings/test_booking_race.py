"""BOOK-TEST-01 — N parallel POST /bookings → 1x201 + (N-1)x409 slot_already_booked.

Asserts the partial UNIQUE `uq_bookings_slot_confirmed` on `bookings.slot_id`
WHERE status='confirmed' (Alembic 0017 / BOOK-01 / C-02 / Pitfall 1) is the
source-of-truth race winner, NOT app-layer logic. The pre-INSERT slot status
UPDATE (active→booked via raw SQL) serialises at the row-lock level but the
final integrity guarantee is the partial UNIQUE — the test uses DISTINCT
Idempotency-Keys so the race surfaces at the DB layer rather than the Redis
idempotency cache (mirrors PTS-TEST-01 discipline).

Mirrors `tests/integration/pt_sessions/test_pt_session_record_race.py`
(PTS-TEST-01) with the subject swap pt_sessions.record → bookings.create.
Uses `db_session_real_commit` because SAVEPOINT-isolated `db_session`
interferes with concurrent UPDATE serialisation.

Postgres-only — the test is skipped automatically when the database is
unreachable via the same fixture-skip convention as PTS-TEST-01.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.audit_models import AuditLog
from app.core.config import get_settings
from app.core.permissions import Role
from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.bookings.models import Booking
from app.modules.clients.models import Client
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.schedule.models import TrainerAvailabilitySlot
from app.modules.trainers.models import Trainer

_RACE_OWNER_EMAIL = "book-create-race-owner@example.com"
_RACE_OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105


@pytest_asyncio.fixture
async def db_session_real_commit() -> AsyncIterator[AsyncSession]:
    """Real BEGIN/COMMIT per request — used ONLY by BOOK-TEST-01.

    The default `db_session` fixture wraps every test in a SAVEPOINT for
    per-test isolation; concurrent UPDATE-RETURNING + INSERT against the
    partial UNIQUE `uq_bookings_slot_confirmed` on bookings does NOT
    compose with nested savepoints (rollback on IntegrityError masks the
    serialisation observation BOOK-TEST-01 asserts). Mirrors
    `tests/integration/pt_sessions/conftest.py:db_session_real_commit`
    verbatim with the TRUNCATE list extended for the
    trainer_availability_slots + bookings tables.

    Defensively probes the database connection at fixture entry (mirrors
    the SAVEPOINT-mode `db_session` fixture in tests/conftest.py) so the
    Postgres-only race test cleanly SKIPs on SQLite / unreachable
    Postgres rather than raising a connect-failure exception out of the
    race body itself.
    """
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)

    try:
        async with engine.connect() as probe:
            await probe.execute(text("select 1"))
    except Exception as exc:  # broad: skip on any connectivity failure
        await engine.dispose()
        pytest.skip(
            f"DATABASE_URL not reachable for BOOK-TEST-01; "
            f"run `docker compose up postgres` first ({exc!r})"
        )

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    # Cleanup: real-commit writes are NOT rolled back. TRUNCATE every table
    # the BOOK-TEST-01 test seeds. CASCADE handles the FK chain.
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE users, clients, trainers, pt_package_plans, "
                "pt_packages, trainer_availability_slots, bookings, audit_log "
                "RESTART IDENTITY CASCADE"
            )
        )
    await engine.dispose()


async def _build_authed_client(app: FastAPI) -> AsyncClient:
    """Authenticate against the REAL app (no SAVEPOINT override)."""
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://testserver")
    r = await client.post(
        "/api/v1/auth/login",
        json={
            "email": _RACE_OWNER_EMAIL,
            "password": _RACE_OWNER_PASSWORD,
        },
    )
    assert r.status_code == 200, f"login failed: {r.text}"
    return client


@pytest.mark.asyncio
async def test_concurrent_create_booking_partial_unique_at_db_layer(
    db_session_real_commit: AsyncSession,
    app: FastAPI,
) -> None:
    """BOOK-TEST-01: 2 parallel POST /api/v1/bookings against the SAME slot
    with DISTINCT Idempotency-Keys → exactly 1x201 + 1x409 slot_already_booked.

    Asserts the partial UNIQUE `uq_bookings_slot_confirmed` is the
    source-of-truth race winner. App-layer `resolve_slot_by_id` + status
    pre-check cannot serialise the race — only the DB row lock + partial
    UNIQUE can. Race losers translate the IntegrityError to
    SlotAlreadyBookedError(code='slot_already_booked') via the
    `_is_slot_confirmed_conflict` constraint-name discriminator per D-38-15.

    Uses 2 DISTINCT Idempotency-Keys so the race surfaces at the DB layer
    rather than at the idempotency replay branch (a single shared key would
    collapse one of the requests into a cached-replay 201, masking the
    race).
    """
    # Seed owner + plan + client + active pt_package + trainer + slot.
    hashed = await hash_password(_RACE_OWNER_PASSWORD)
    owner = User(
        email=_RACE_OWNER_EMAIL,
        password_hash=hashed,
        role=Role.OWNER,
        full_name="Booking Create Race Owner",
    )
    db_session_real_commit.add(owner)
    await db_session_real_commit.commit()
    await db_session_real_commit.refresh(owner)
    owner_id = owner.id

    plan = PtPackagePlan(
        name=f"BookRacePlan-{uuid4().hex[:6]}",
        session_count=10,
        price_kopecks=500000,
        validity_days=90,
    )
    db_session_real_commit.add(plan)
    await db_session_real_commit.commit()
    await db_session_real_commit.refresh(plan)

    phone_suffix = uuid4().int % 10**7
    client_obj = Client(
        last_name=f"BookRaceClient-{uuid4().hex[:6]}",
        first_name="Test",
        phone=f"+7906{phone_suffix:07d}",
        created_by_user_id=owner_id,
    )
    db_session_real_commit.add(client_obj)
    await db_session_real_commit.commit()
    await db_session_real_commit.refresh(client_obj)

    today = datetime.now(tz=UTC).date()
    validity_days = plan.validity_days
    assert validity_days is not None
    pt_package = PtPackage(
        client_id=client_obj.id,
        plan_id=plan.id,
        plan_name_snapshot=plan.name,
        session_count_snapshot=plan.session_count,
        price_kopecks_snapshot=plan.price_kopecks,
        validity_days_snapshot=validity_days,
        sessions_remaining=10,  # plenty — race is at the slot layer, not the package.
        status="active",
        start_date=today,
        end_date=today + timedelta(days=validity_days - 1),
    )
    db_session_real_commit.add(pt_package)
    await db_session_real_commit.commit()
    await db_session_real_commit.refresh(pt_package)
    pt_package_id = pt_package.id

    trainer = Trainer(
        full_name=f"BookRaceTrainer-{uuid4().hex[:6]}",
        is_active=True,
    )
    db_session_real_commit.add(trainer)
    await db_session_real_commit.commit()
    await db_session_real_commit.refresh(trainer)

    # The race target — single active slot.
    # CR-01 fix: working-hours enforcement now fires correctly (0-based weekday).
    # Use a slot pinned to 10:00 Moscow on the next Monday so it always falls
    # within the seeded Mon-Fri 08:00-22:00 working-hours window, regardless of
    # what time or day the test suite runs.
    _moscow_tz = ZoneInfo("Europe/Moscow")
    _now_msk = datetime.now(_moscow_tz)
    # days_to_next_monday: 0 on Mon, 7 on Mon (wrap), 1 on Sun, etc.
    _days_ahead = (7 - _now_msk.weekday()) % 7 or 7  # always ≥ 1 day ahead
    _slot_msk = _now_msk.replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(
        days=_days_ahead
    )
    slot_start = _slot_msk.astimezone(UTC)
    slot = TrainerAvailabilitySlot(
        trainer_id=trainer.id,
        start_time=slot_start,
        end_time=slot_start + timedelta(hours=1),
        status="active",
        created_by_user_id=owner_id,
    )
    db_session_real_commit.add(slot)
    await db_session_real_commit.commit()
    await db_session_real_commit.refresh(slot)
    slot_id = slot.id

    # Flush Redis so rate-limit / idempotency keys don't bleed across tests.
    await app.state.redis.flushdb()

    authed = await _build_authed_client(app)
    csrf_token = authed.cookies.get("clubcore_csrf") or ""

    async def _post(idx: int) -> Any:
        # 2 DISTINCT Idempotency-Keys so the race surfaces at the DB layer.
        return await authed.post(
            "/api/v1/bookings",
            json={
                "slotId": str(slot_id),
                "clientId": str(client_obj.id),
                "ptPackageId": str(pt_package_id),
            },
            headers={
                "X-CSRF-Token": csrf_token,
                "Idempotency-Key": f"book-create-race-{idx}-{uuid4().hex}",
            },
        )

    # 2 parallel POST requests.
    n_concurrent = 2
    responses = await asyncio.gather(*[_post(i) for i in range(n_concurrent)])
    await authed.aclose()

    statuses = sorted(r.status_code for r in responses)
    assert statuses == [201, 409], (
        f"BOOK-TEST-01 failed: expected [201, 409], got {statuses}; "
        f"bodies: {[r.text for r in responses]}"
    )

    bodies_409 = [r.json() for r in responses if r.status_code == 409]
    codes = [b.get("code") for b in bodies_409]
    assert all(c == "slot_already_booked" for c in codes), (
        f"Unexpected 409 codes (expected all 'slot_already_booked'): {codes}"
    )

    # DB invariants: exactly 1 confirmed booking row for the slot + slot
    # status='booked'.
    db_session_real_commit.expire_all()
    confirmed_count = await db_session_real_commit.scalar(
        select(func.count())
        .select_from(Booking)
        .where(
            Booking.slot_id == slot_id,
            Booking.status == "confirmed",
        )
    )
    assert confirmed_count == 1, (
        f"Expected exactly 1 confirmed booking after race, got {confirmed_count}"
    )

    refreshed_slot = await db_session_real_commit.scalar(
        select(TrainerAvailabilitySlot).where(TrainerAvailabilitySlot.id == slot_id)
    )
    assert refreshed_slot is not None
    assert refreshed_slot.status == "booked"

    # Audit invariants: exactly 1 booking_created. The race-loser rolled
    # back BEFORE audit emit (the IntegrityError triggered
    # session.rollback() and the orchestrator raised SlotAlreadyBookedError,
    # never reaching audit.emit).
    created_count = await db_session_real_commit.scalar(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "booking_created")
    )
    assert created_count == 1, f"Expected exactly 1 booking_created audit row, got {created_count}"
