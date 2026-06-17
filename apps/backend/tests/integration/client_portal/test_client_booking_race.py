"""Phase 70 criterion #1 — client booking race test.

2 parallel POST /api/v1/client/booking against the SAME slot with DISTINCT
Idempotency-Keys → exactly 1x201 + 1x409 slot_already_booked.

Asserts the partial UNIQUE `uq_bookings_slot_confirmed` on bookings.slot_id
WHERE status='confirmed' (Alembic 0017 / BOOK-01) is the source-of-truth race
winner — the same invariant proven by test_booking_race.py for the staff path.

Uses `db_session_real_commit` (real BEGIN/COMMIT) because SAVEPOINT-isolated
`db_session` interferes with concurrent UPDATE serialisation (the partial UNIQUE
race surfaces at the DB layer, not at the idempotency cache). Mirrors
`tests/integration/bookings/test_booking_race.py:db_session_real_commit` verbatim.

DISTINCT Idempotency-Keys so the race surfaces at the DB partial UNIQUE rather
than the Redis cache (same discipline as BOOK-TEST-01).

Postgres-only — skipped automatically when the database is unreachable.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.audit_models import AuditLog
from app.core.config import get_settings
from app.core.permissions import Role
from app.core.security import generate_otp_code, hash_password
from app.modules.auth.models import OtpCode, User
from app.modules.bookings.models import Booking
from app.modules.clients.models import Client
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.schedule.models import TrainerAvailabilitySlot
from app.modules.trainers.models import Trainer

# This test sets working_hours_config + booking_config EXPLICITLY via its own
# real-commit session (db_session_real_commit) so the concurrent HTTP bookings
# see permissive timing. The autouse permissive_booking_config fixture runs on a
# SEPARATE SAVEPOINT db_session connection and holds an uncommitted UPDATE row
# lock on the SAME working_hours_config singleton — so this test's own
# `UPDATE working_hours_config` deadlocks against the fixture (circular
# self-deadlock; verified via pg_blocking_pids — see debug session
# pytest-isolation-deadlock). Opt out of the autouse fixture: this test owns its
# config setup, so the fixture is both redundant and actively harmful here.
pytestmark = pytest.mark.no_permissive_booking_config

# ---------------------------------------------------------------------------
# db_session_real_commit fixture — copied verbatim from test_booking_race.py
# (see bookings/test_booking_race.py:54-101; TRUNCATE list extended for
# client_refresh_tokens + otp_codes for the client auth path)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session_real_commit() -> AsyncIterator[AsyncSession]:
    """Real BEGIN/COMMIT per request — used ONLY by the client race test.

    Mirrors `tests/integration/bookings/test_booking_race.py:db_session_real_commit`
    verbatim with TRUNCATE list extended to cover client_refresh_tokens + otp_codes
    (needed for the client auth path in this test module).

    Defensively probes the database connection at fixture entry so the test
    cleanly SKIPs on SQLite / unreachable Postgres.
    """
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)

    try:
        async with engine.connect() as probe:
            await probe.execute(text("select 1"))
    except Exception as exc:  # broad: skip on any connectivity failure
        await engine.dispose()
        pytest.skip(
            f"DATABASE_URL not reachable for client booking race test; "
            f"run `docker compose up postgres` first ({exc!r})"
        )

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    # Cleanup: real-commit writes are NOT rolled back. TRUNCATE the tables
    # seeded by the race test. CASCADE handles the FK chain.
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE users, clients, trainers, pt_package_plans, "
                "pt_packages, trainer_availability_slots, bookings, "
                "otp_codes, client_refresh_tokens, audit_log "
                "RESTART IDENTITY CASCADE"
            )
        )
        # The test mutates the booking_config + working_hours_config SINGLETONS via
        # REAL commits (so the concurrent HTTP bookings see permissive timing).
        # Those rows are NOT in the TRUNCATE list (and must not be — they are seeded
        # singletons), and this test opts out of the autouse permissive_booking_config
        # fixture (no_permissive_booking_config) which would otherwise roll them back.
        # So restore them to the migration 0071 seeded defaults here; otherwise the
        # mutated values (booking_ahead_days=365 etc.) leak into the shared DB and
        # break later tests that assert the pristine seeded singleton
        # (e.g. test_settings_endpoints::test_owner_get_booking_config_returns_seeded_singleton).
        await conn.execute(
            text(
                "UPDATE booking_config "
                "SET booking_ahead_days = 14, cutoff_minutes = 60 "
                "WHERE id = CAST(:id AS uuid)"
            ),
            {"id": "00000000-0000-0000-0000-000000000003"},
        )
        _seeded_schedule = [
            {"day_of_week": 0, "open": "08:00", "close": "22:00"},
            {"day_of_week": 1, "open": "08:00", "close": "22:00"},
            {"day_of_week": 2, "open": "08:00", "close": "22:00"},
            {"day_of_week": 3, "open": "08:00", "close": "22:00"},
            {"day_of_week": 4, "open": "08:00", "close": "22:00"},
            {"day_of_week": 5, "open": "09:00", "close": "21:00"},
            {"day_of_week": 6, "open": "09:00", "close": "21:00"},
        ]
        await conn.execute(
            text(
                "UPDATE working_hours_config "
                "SET schedule = CAST(:schedule AS jsonb), closures = CAST(:closures AS jsonb) "
                "WHERE id = CAST(:id AS uuid)"
            ),
            {
                "schedule": json.dumps(_seeded_schedule),
                "closures": json.dumps([]),
                "id": "00000000-0000-0000-0000-000000000004",
            },
        )
    await engine.dispose()


# ---------------------------------------------------------------------------
# Auth helper for real-commit mode (no SAVEPOINT — uses real network to app)
# ---------------------------------------------------------------------------


async def _auth_as_client_real_commit(
    http_client: AsyncClient,
    session: AsyncSession,
    client: Client,
) -> None:
    """Request OTP → patch hash → verify. Sets cookies on http_client.

    Real-commit variant: reads OtpCode without SAVEPOINT isolation.
    """
    settings = get_settings()

    req = await http_client.post(
        "/api/v1/client/otp/request",
        json={"phone": client.phone},
    )
    assert req.status_code == 202, f"OTP request failed: {req.text}"

    # Read the OtpCode using the real-commit session (no SAVEPOINT wrapper)
    otp_row = await session.scalar(
        select(OtpCode).where(
            OtpCode.client_id == client.id,
            OtpCode.consumed_at.is_(None),
        )
    )
    assert otp_row is not None, f"OtpCode not found for {client.id}"

    raw_code, code_hash = generate_otp_code()
    otp_row.code_hash = code_hash
    otp_row.expires_at = datetime.now(tz=UTC) + timedelta(seconds=settings.otp_code_ttl_seconds)
    await session.commit()

    verify = await http_client.post(
        "/api/v1/client/otp/verify",
        json={"phone": client.phone, "code": raw_code},
    )
    assert verify.status_code == 200, f"OTP verify failed: {verify.text}"
    # Cookies stored in http_client.cookies


# ---------------------------------------------------------------------------
# Race test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_client_create_booking_partial_unique_at_db_layer(
    db_session_real_commit: AsyncSession,
    app: FastAPI,
) -> None:
    """CBOOK-03 criterion #1: 2 parallel client POSTs → 1x201 + 1x409 slot_already_booked.

    Mirrors BOOK-TEST-01 (test_booking_race.py) for the client path.
    DISTINCT Idempotency-Keys surface the race at the DB partial UNIQUE, not
    the Redis cache. Real-commit session means the partial UNIQUE IS visible
    to both concurrent requests.

    Asserts:
      - sorted statuses == [201, 409]
      - 409 body code == "slot_already_booked"
      - exactly 1 confirmed booking row in DB
      - slot status == 'booked'
      - exactly 1 booking_created audit row (race loser rolled back before emit)
    """
    # Flush Redis so old idempotency keys don't interfere.
    await app.state.redis.flushdb()

    # Seed staff user (created_by_user_id FK for Client)
    staff = User(
        email=f"race-client-staff-{uuid4().hex[:6]}@example.com",
        password_hash=await hash_password("secure-test-password-race-123"),
        role=Role.RECEPTION,
        full_name="Race Test Staff",
    )
    db_session_real_commit.add(staff)
    await db_session_real_commit.commit()
    await db_session_real_commit.refresh(staff)

    phone_suffix = uuid4().int % 10**7
    client = Client(
        first_name="RaceClient",
        last_name=f"Test-{uuid4().hex[:4]}",
        phone=f"+7906{phone_suffix:07d}",
        telegram_user_id=abs(hash(f"race-{phone_suffix}")) % (10**10),
        created_by_user_id=staff.id,
    )
    db_session_real_commit.add(client)
    await db_session_real_commit.commit()
    await db_session_real_commit.refresh(client)

    plan = PtPackagePlan(
        name=f"RacePlan-{uuid4().hex[:4]}",
        session_count=10,
        price_kopecks=100_000,
        validity_days=90,
    )
    db_session_real_commit.add(plan)
    await db_session_real_commit.commit()
    await db_session_real_commit.refresh(plan)

    trainer = Trainer(
        full_name=f"RaceTrainer-{uuid4().hex[:4]}",
        is_active=True,
    )
    db_session_real_commit.add(trainer)
    await db_session_real_commit.commit()
    await db_session_real_commit.refresh(trainer)

    today = datetime.now(tz=UTC).date()
    pkg = PtPackage(
        client_id=client.id,
        plan_id=plan.id,
        plan_name_snapshot=plan.name,
        session_count_snapshot=plan.session_count,
        price_kopecks_snapshot=plan.price_kopecks,
        validity_days_snapshot=plan.validity_days,
        sessions_remaining=10,  # plenty — race is at the slot layer
        status="active",
        start_date=today,
        end_date=today + timedelta(days=89),
        trainer_id=trainer.id,
    )
    db_session_real_commit.add(pkg)
    await db_session_real_commit.commit()
    await db_session_real_commit.refresh(pkg)

    # Phase 111 fix: reset working_hours_config to all-day-open so the slot
    # time (now+48h) is accepted regardless of time-of-day. The real-commit
    # session makes this visible to the concurrent HTTP booking requests.
    _all_days_open = [
        {"day_of_week": dow, "open_time": "00:00", "close_time": "23:59"} for dow in range(7)
    ]
    await db_session_real_commit.execute(
        text(
            "UPDATE working_hours_config "
            "SET schedule = CAST(:schedule AS jsonb), closures = CAST(:closures AS jsonb) "
            "WHERE id = CAST(:id AS uuid)"
        ),
        {
            "schedule": json.dumps(_all_days_open),
            "closures": json.dumps([]),
            "id": "00000000-0000-0000-0000-000000000004",
        },
    )
    await db_session_real_commit.execute(
        text(
            "UPDATE booking_config "
            "SET booking_ahead_days = :ahead, cutoff_minutes = :cutoff "
            "WHERE id = CAST(:id AS uuid)"
        ),
        {
            "ahead": 365,
            "cutoff": 0,
            "id": "00000000-0000-0000-0000-000000000003",
        },
    )
    await db_session_real_commit.commit()

    slot_start = datetime.now(tz=UTC) + timedelta(hours=48)
    slot = TrainerAvailabilitySlot(
        trainer_id=trainer.id,
        start_time=slot_start,
        end_time=slot_start + timedelta(hours=1),
        status="active",
        created_by_user_id=staff.id,
    )
    db_session_real_commit.add(slot)
    await db_session_real_commit.commit()
    await db_session_real_commit.refresh(slot)
    # Store IDs now — after expire_all() these would be DetachedInstanceError
    slot_id = slot.id
    pkg_id = pkg.id

    # Build authed client against the REAL app (no SAVEPOINT override).
    transport = ASGITransport(app=app)
    http_client = AsyncClient(transport=transport, base_url="http://testserver")

    # Stub the OTP sender (no Telegram bot in test)
    from app.modules.client_auth import service as client_auth_service

    original_sender = getattr(client_auth_service, "_client_otp_sender", None)

    async def _noop(chat_id: int, code: str) -> None:
        pass

    client_auth_service._client_otp_sender = _noop  # type: ignore[assignment]
    try:
        await _auth_as_client_real_commit(http_client, db_session_real_commit, client)
    finally:
        client_auth_service._client_otp_sender = original_sender  # type: ignore[assignment]

    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""

    async def _post(idx: int) -> object:
        # DISTINCT Idempotency-Keys so the race surfaces at the DB layer.
        return await http_client.post(
            "/api/v1/client/booking",
            json={
                "slotId": str(slot_id),
                "ptPackageId": str(pkg_id),
            },
            headers={
                "X-CSRF-Token": csrf_token,
                "Idempotency-Key": f"client-race-{idx}-{uuid4().hex}",
            },
        )

    # 2 parallel POST requests.
    responses = await asyncio.gather(*[_post(i) for i in range(2)])
    await http_client.aclose()

    statuses = sorted(r.status_code for r in responses)  # type: ignore[union-attr]
    assert statuses == [201, 409], (
        f"Expected [201, 409], got {statuses}; bodies: {[r.text for r in responses]}"  # type: ignore[union-attr]
    )

    bodies_409 = [r.json() for r in responses if r.status_code == 409]  # type: ignore[union-attr]
    codes = [b.get("code") for b in bodies_409]
    assert all(c == "slot_already_booked" for c in codes), (
        f"Unexpected 409 codes (expected all 'slot_already_booked'): {codes}"
    )

    # DB invariants — exactly 1 confirmed booking + slot 'booked' + 1 audit row.
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

    created_count = await db_session_real_commit.scalar(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "booking_created")
    )
    assert created_count == 1, (
        f"Expected exactly 1 booking_created audit row after race, got {created_count}"
    )
