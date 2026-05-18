"""Phase 40 minimal verification — create_booking_via_bot self-service entry.

Asserts the four invariants Phase 40 actually adds:

  1. ``bookings_service.create_booking_via_bot(...)`` succeeds end-to-end against
     a live DB with a real slot + real active pt_package.
  2. The inserted ``bookings.created_by_user_id IS NULL`` (Alembic 0021 / BLOCKER-4
     relaxed the NOT NULL constraint).
  3. The returned ``BookingResponse`` carries ``trainer_full_name`` and
     ``slot_start_time`` populated from the JOIN (BLOCKER-2).
  4. The ``booking_created`` audit row has
     ``payload.actor_role == 'telegram_bot'`` (D-40-05 Literal expansion) and
     ``payload.actor_user_id IS NULL`` (raw None per WARNING-1 fix).

This is the v1.5 minimum verification that the new Phase 40 surface works against
a real Postgres. Designed to be runnable repeatedly — cleans up its own state at
the head of each run.

Usage:
    DATABASE_URL="postgresql+asyncpg://app:app@localhost:5432/sportzal" \\
    uv run python -m scripts.verify_40_create_booking_via_bot
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

# Eager-import every ORM module so the SQLAlchemy mapper registry sees all
# relationship() targets (REG-29-04 lesson — see scripts/run_*_cron_once.py).
import app.core.audit_models  # noqa: F401
import app.modules.auth.models  # noqa: F401
import app.modules.bookings.models  # noqa: F401
import app.modules.clients.models  # noqa: F401
import app.modules.memberships.models  # noqa: F401
import app.modules.payments.models  # noqa: F401
import app.modules.pt_packages.models  # noqa: F401
import app.modules.pt_sessions.models  # noqa: F401
import app.modules.schedule.models  # noqa: F401
import app.modules.trainers.models  # noqa: F401
import app.modules.visits.models  # noqa: F401

from app.core.database import db_lifespan_manager
from app.core.dependencies import (
    register_active_pt_package_resolver,
    register_slot_by_id_resolver,
    register_trainer_by_id_resolver,
)
from app.modules.bookings.models import Booking
from app.modules.bookings.service import create_booking_via_bot
from app.modules.pt_packages import service as pt_packages_service
from app.modules.schedule import service as schedule_service
from app.modules.trainers import service as trainers_service

VERIFY_CLIENT_EMAIL = "verify_smoke@fixture.local"
TRAINER_NAME = "Trainer Alpha"


async def _resolve_fixture_ids(session: AsyncSession) -> tuple[UUID, UUID]:
    """Return (client_id, trainer_id) — falls if seed not present."""
    row = await session.execute(
        text("SELECT id FROM clients WHERE email = :email"),
        {"email": VERIFY_CLIENT_EMAIL},
    )
    client_id = row.scalar_one_or_none()
    if client_id is None:
        raise SystemExit(
            f"FATAL: seed missing — no client with email {VERIFY_CLIENT_EMAIL}. "
            "Run: SEED_VERIFY_OWNER_PASSWORD=... SEED_VERIFY_RECEPTION_PASSWORD=... "
            "uv run python -m scripts.seed_v1_4_verification_fixtures"
        )
    row = await session.execute(
        text("SELECT id FROM trainers WHERE full_name = :name"),
        {"name": TRAINER_NAME},
    )
    trainer_id = row.scalar_one_or_none()
    if trainer_id is None:
        raise SystemExit(f"FATAL: seed missing — no trainer named {TRAINER_NAME}")
    return UUID(str(client_id)), UUID(str(trainer_id))


async def _seed_active_pt_package(
    session: AsyncSession, *, client_id: UUID, trainer_id: UUID
) -> UUID:
    """Idempotent — drops any existing pt_package for this client first."""
    # 1. Wipe priors (pt_sessions / bookings reference pt_packages via FK, so we
    #    must clear them too — easiest is to delete bookings linked to this
    #    client's existing pt_packages first).
    await session.execute(
        text(
            "DELETE FROM bookings WHERE pt_package_id IN ("
            "  SELECT id FROM pt_packages WHERE client_id = :client_id"
            ")"
        ),
        {"client_id": str(client_id)},
    )
    await session.execute(
        text("DELETE FROM pt_packages WHERE client_id = :client_id"),
        {"client_id": str(client_id)},
    )

    # 2. Resolve any active plan (seed creates 2 PT-package plans).
    plan_id_row = await session.execute(
        text("SELECT id FROM pt_package_plans WHERE deleted_at IS NULL LIMIT 1")
    )
    plan_id = plan_id_row.scalar_one_or_none()
    if plan_id is None:
        raise SystemExit("FATAL: seed missing pt_package_plan")

    # 3. Insert active pt_package tied to Trainer Alpha so the slot filter
    #    matches (D-40-06 / D-38-XX trainer-mismatch guard).
    pkg_id = uuid4()
    await session.execute(
        text(
            """
            INSERT INTO pt_packages (
                id, client_id, plan_id, trainer_id,
                plan_name_snapshot, session_count_snapshot,
                price_kopecks_snapshot, validity_days_snapshot,
                sessions_remaining, status, start_date, end_date,
                created_at, updated_at
            ) VALUES (
                :id, :client_id, :plan_id, :trainer_id,
                'Verify Pack', 10, 1000000, 90,
                10, 'active', :start_date, :end_date,
                now(), now()
            )
            """
        ),
        {
            "id": str(pkg_id),
            "client_id": str(client_id),
            "plan_id": str(plan_id),
            "trainer_id": str(trainer_id),
            "start_date": date.today(),
            "end_date": date.today() + timedelta(days=90),
        },
    )
    return pkg_id


async def _resolve_owner_id(session: AsyncSession) -> UUID:
    row = await session.execute(
        text("SELECT id FROM users WHERE role = 'owner' LIMIT 1")
    )
    owner_id = row.scalar_one_or_none()
    if owner_id is None:
        raise SystemExit("FATAL: seed missing owner user")
    return UUID(str(owner_id))


async def _seed_active_slot(
    session: AsyncSession, *, trainer_id: UUID, owner_id: UUID
) -> UUID:
    """Publish a fresh slot 1 hour from now (idempotent — wipes priors)."""
    await session.execute(
        text(
            "DELETE FROM trainer_availability_slots "
            "WHERE trainer_id = :t AND status = 'active' AND start_time > now()"
        ),
        {"t": str(trainer_id)},
    )
    slot_id = uuid4()
    start = datetime.now(UTC) + timedelta(hours=1)
    end = start + timedelta(minutes=60)
    await session.execute(
        text(
            """
            INSERT INTO trainer_availability_slots (
                id, trainer_id, start_time, end_time, status,
                created_by_user_id, created_at, updated_at
            ) VALUES (
                :id, :trainer_id, :start, :end, 'active',
                :owner_id, now(), now()
            )
            """
        ),
        {
            "id": str(slot_id),
            "trainer_id": str(trainer_id),
            "start": start,
            "end": end,
            "owner_id": str(owner_id),
        },
    )
    return slot_id


async def main() -> int:
    # Composition root — register the Protocol-slot resolvers
    # create_booking_via_bot indirectly relies on (via the standard
    # service callsites).
    register_active_pt_package_resolver(pt_packages_service.resolve_active_pt_package)
    register_slot_by_id_resolver(schedule_service.resolve_slot_by_id)
    register_trainer_by_id_resolver(trainers_service.resolve_trainer_by_id)

    async with db_lifespan_manager() as (_engine, sessionmaker):
        # 1. Seed prerequisites (own UoW — committed before the bot call)
        async with sessionmaker() as setup_session:
            client_id, trainer_id = await _resolve_fixture_ids(setup_session)
            pt_package_id = await _seed_active_pt_package(
                setup_session, client_id=client_id, trainer_id=trainer_id
            )
            owner_id = await _resolve_owner_id(setup_session)
            slot_id = await _seed_active_slot(
                setup_session, trainer_id=trainer_id, owner_id=owner_id
            )
            await setup_session.commit()
            print(
                f"[setup] client_id={client_id} trainer_id={trainer_id} "
                f"pt_package_id={pt_package_id} slot_id={slot_id}"
            )

        # 2. Call create_booking_via_bot — the THING we are verifying.
        async with sessionmaker() as bot_session:
            booking = await create_booking_via_bot(
                bot_session,
                client_id=client_id,
                slot_id=slot_id,
                pt_package_id=pt_package_id,
            )
            print(f"[bot] booking.id={booking.id} status={booking.status}")
            print(f"[bot] booking.trainer_full_name={booking.trainer_full_name!r}")
            print(f"[bot] booking.slot_start_time={booking.slot_start_time}")
            print(f"[bot] booking.created_by_user_id={booking.created_by_user_id!r}")

        # 3. Verify the four invariants via a fresh read session.
        async with sessionmaker() as verify_session:
            row = await verify_session.execute(
                select(Booking).where(Booking.id == booking.id)
            )
            persisted_booking = row.scalar_one()

            # Latest booking_created audit row for this client
            audit_row = await verify_session.execute(
                text(
                    """
                    SELECT actor_user_id, payload
                    FROM audit_log
                    WHERE action = 'booking_created'
                      AND payload->>'booking_id' = :booking_id
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {"booking_id": str(booking.id)},
            )
            audit = audit_row.first()

        failures: list[str] = []

        # Invariant 1: row inserted, status='confirmed'
        if persisted_booking.status != "confirmed":
            failures.append(
                f"Invariant 1 FAIL: bookings.status={persisted_booking.status!r} != 'confirmed'"
            )
        else:
            print(f"✓ Invariant 1: bookings.status = 'confirmed'")

        # Invariant 2: created_by_user_id IS NULL (Alembic 0021 / BLOCKER-4)
        if persisted_booking.created_by_user_id is not None:
            failures.append(
                f"Invariant 2 FAIL: bookings.created_by_user_id = "
                f"{persisted_booking.created_by_user_id!r}, expected NULL"
            )
        else:
            print("✓ Invariant 2: bookings.created_by_user_id IS NULL (Alembic 0021)")

        # Invariant 3: BookingResponse carries trainer_full_name + slot_start_time
        if booking.trainer_full_name != TRAINER_NAME:
            failures.append(
                f"Invariant 3a FAIL: BookingResponse.trainer_full_name = "
                f"{booking.trainer_full_name!r}, expected {TRAINER_NAME!r}"
            )
        else:
            print(f"✓ Invariant 3a: BookingResponse.trainer_full_name = {TRAINER_NAME!r}")
        if booking.slot_start_time is None:
            failures.append(
                "Invariant 3b FAIL: BookingResponse.slot_start_time is None"
            )
        else:
            print(f"✓ Invariant 3b: BookingResponse.slot_start_time populated")

        # Invariant 4: audit row carries actor_role='telegram_bot' + actor_user_id IS NULL
        if audit is None:
            failures.append(
                "Invariant 4 FAIL: no booking_created audit row found for this booking_id"
            )
        else:
            actor_role = audit.payload.get("actor_role")
            actor_user_id = audit.actor_user_id
            if actor_role != "telegram_bot":
                failures.append(
                    f"Invariant 4a FAIL: audit.payload.actor_role = {actor_role!r}, "
                    "expected 'telegram_bot'"
                )
            else:
                print(
                    "✓ Invariant 4a: audit_log.payload.actor_role = 'telegram_bot' "
                    "(D-40-05 Literal expansion)"
                )
            if actor_user_id is not None:
                failures.append(
                    f"Invariant 4b FAIL: audit.actor_user_id = {actor_user_id!r}, "
                    "expected NULL"
                )
            else:
                print(
                    "✓ Invariant 4b: audit_log.actor_user_id IS NULL (WARNING-1 fix)"
                )

        if failures:
            print("\n=== VERIFICATION FAILED ===")
            for f in failures:
                print(f"  {f}")
            return 1

        print("\n=== VERIFICATION PASSED ===")
        print(
            "Phase 40 self-service booking surface (BOT-01..05 + Alembic 0021 + "
            "BookingResponse extensions + audit Literal) is operational against "
            "the live stack."
        )
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
