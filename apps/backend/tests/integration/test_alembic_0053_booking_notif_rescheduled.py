"""Phase 80 RESCH-02 — Alembic 0053 widens booking_notifications.kind CHECK for 'rescheduled'.

Migration under test: ``0053_booking_notif_widen_kind_rescheduled``

Background: Migration 0053 drops ``ck_booking_notifications_kind`` (the 4-kind
CHECK shipped by 0032) and recreates it with a 5-kind predicate that adds
'rescheduled'.  No VARCHAR ALTER is needed: 'rescheduled' (12 chars) fits
the existing VARCHAR(32) column.

Test strategy:
- Schema-shape test: verify ``ck_booking_notifications_kind`` still exists
  post-migration and that it accepts 'rescheduled' as a valid kind.
- Row-level accept test: INSERT a booking_notifications row with
  kind='rescheduled' succeeds (no IntegrityError).
- Row-level reject test: INSERT a row with kind='bogus_kind' still raises
  IntegrityError (CHECK is still enforced; widening did not break the guard).

Seeding strategy: booking_notifications has a NOT NULL FK → bookings.id
(RESTRICT).  We seed the minimum chain via raw SQL inside a SAVEPOINT so the
outer test transaction rolls everything back on teardown:
  users → clients → trainers → trainer_availability_slots → bookings
  → booking_notifications

The ``db_session`` fixture from tests/conftest.py wraps each test in a
SAVEPOINT rollback so seeded rows never persist between tests.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_booking(session: AsyncSession) -> Any:
    """Seed the minimum chain (users → clients → trainers → pt_package_plans →
    pt_packages → slots → bookings).

    Returns the booking_id UUID so the caller can reference it in
    booking_notifications rows.

    All inserts use raw SQL; UUIDs are generated client-side.
    Uses SAVEPOINT-aware flush: no ``commit()`` — the outer ``db_session``
    fixture owns the rollback.
    """
    uid = uuid4()
    client_id = uuid4()
    trainer_id = uuid4()
    plan_id = uuid4()
    pt_package_id = uuid4()
    slot_id = uuid4()
    booking_id = uuid4()

    nonce = uid.hex[:8]

    await session.execute(
        text(
            "INSERT INTO users (id, email, password_hash, role, full_name, created_at, updated_at)"
            " VALUES (:id, :email, 'x', 'owner', :full_name, now(), now())"
        ).bindparams(
            id=uid,
            email=f"test-0053-{nonce}@example.com",
            full_name="Test Owner 0053",
        )
    )

    await session.execute(
        text(
            "INSERT INTO clients"
            " (id, last_name, first_name, phone, created_by_user_id, created_at, updated_at)"
            " VALUES (:id, 'Test', 'Client', :phone, :user_id, now(), now())"
        ).bindparams(id=client_id, phone=f"+7999{nonce}", user_id=uid)
    )

    await session.execute(
        text(
            "INSERT INTO trainers"
            " (id, full_name, created_at, updated_at)"
            " VALUES (:id, :full_name, now(), now())"
        ).bindparams(id=trainer_id, full_name=f"Trainer 0053 {nonce}")
    )

    await session.execute(
        text(
            "INSERT INTO pt_package_plans"
            " (id, name, session_count, price_kopecks, validity_days, created_at, updated_at)"
            " VALUES (:id, :name, 10, 100000, 90, now(), now())"
        ).bindparams(id=plan_id, name=f"Plan 0053 {nonce}")
    )

    await session.execute(
        text(
            "INSERT INTO pt_packages"
            " (id, client_id, plan_id, plan_name_snapshot, session_count_snapshot,"
            "  price_kopecks_snapshot, validity_days_snapshot, sessions_remaining,"
            "  status, start_date, created_at, updated_at)"
            " VALUES (:id, :client_id, :plan_id, 'Plan 0053', 10, 100000, 90, 10,"
            "         'active', CURRENT_DATE, now(), now())"
        ).bindparams(id=pt_package_id, client_id=client_id, plan_id=plan_id)
    )

    await session.execute(
        text(
            "INSERT INTO trainer_availability_slots"
            " (id, trainer_id, start_time, end_time, status, created_at, updated_at)"
            " VALUES (:id, :trainer_id, now() + interval '2 days',"
            "         now() + interval '2 days 1 hour', 'booked', now(), now())"
        ).bindparams(id=slot_id, trainer_id=trainer_id)
    )

    await session.execute(
        text(
            "INSERT INTO bookings"
            " (id, slot_id, client_id, pt_package_id, status, created_at, updated_at)"
            " VALUES (:id, :slot_id, :client_id, :pt_package_id, 'confirmed', now(), now())"
        ).bindparams(
            id=booking_id,
            slot_id=slot_id,
            client_id=client_id,
            pt_package_id=pt_package_id,
        )
    )

    await session.flush()
    return booking_id


# ---------------------------------------------------------------------------
# Schema-shape assertions
# ---------------------------------------------------------------------------


async def test_0053_kind_check_constraint_still_present(
    db_session: AsyncSession,
) -> None:
    """Migration 0053 must preserve (drop+recreate) ck_booking_notifications_kind."""

    def _checks(sync_conn: Any) -> set[str | None]:
        inspector = inspect(sync_conn)
        return {cc["name"] for cc in inspector.get_check_constraints("booking_notifications")}

    conn = await db_session.connection()
    check_names = await conn.run_sync(_checks)
    assert "ck_booking_notifications_kind" in check_names, (
        "ck_booking_notifications_kind must exist after 0053 migration"
    )


# ---------------------------------------------------------------------------
# Row-level acceptance: 'rescheduled' kind now passes the CHECK
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_0053_rescheduled_kind_inserts_successfully(
    db_session: AsyncSession,
) -> None:
    """A booking_notifications row with kind='rescheduled' must INSERT without error."""
    booking_id = await _seed_booking(db_session)

    await db_session.execute(
        text(
            "INSERT INTO booking_notifications"
            " (id, booking_id, kind, channel, sent_at, created_at, updated_at)"
            " VALUES (gen_random_uuid(), :booking_id, 'rescheduled', 'telegram',"
            "         now(), now(), now())"
        ).bindparams(booking_id=booking_id)
    )
    await db_session.flush()

    count = await db_session.scalar(
        text(
            "SELECT COUNT(*) FROM booking_notifications"
            " WHERE booking_id = :bid AND kind = 'rescheduled'"
        ).bindparams(bid=booking_id)
    )
    assert count == 1, "Expected 1 rescheduled booking_notifications row"


# ---------------------------------------------------------------------------
# Row-level rejection: unknown kind still violates the CHECK
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_0053_unknown_kind_still_rejected(
    db_session: AsyncSession,
) -> None:
    """CHECK ck_booking_notifications_kind still rejects bogus kinds post-0053."""
    booking_id = await _seed_booking(db_session)

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO booking_notifications"
                    " (id, booking_id, kind, channel, sent_at, created_at, updated_at)"
                    " VALUES (gen_random_uuid(), :booking_id, 'bogus_kind', 'telegram',"
                    "         now(), now(), now())"
                ).bindparams(booking_id=booking_id)
            )
            await db_session.flush()
