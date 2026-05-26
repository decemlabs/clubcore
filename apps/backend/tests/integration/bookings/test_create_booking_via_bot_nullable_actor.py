"""Integration tests for Phase 40 BLOCKER-4 — bookings.created_by_user_id NULL.

Task 1 deliverables (Alembic 0021 + ORM nullability + repository signature):
  - Alembic 0021 upgrade flips ``bookings.created_by_user_id`` to NULLABLE.
  - ORM model ``Mapped[UUID | None]`` + ``nullable=True``.
  - ``repository.insert_booking`` accepts ``created_by_user_id: UUID | None``.
  - Downgrade is guarded by a NULL-row operational check.

The full ``create_booking_via_bot`` happy-path audit-row assertion lives in
``tests/unit/bookings/test_create_booking_via_bot.py`` (Task 4). This file
covers the DB / ORM / repository slice only — proves that the schema-layer
relaxation works end-to-end against a real Postgres instance.

CI runs the full suite against a live Postgres container. In the local
worktree (no Postgres reachable), the integration tests skip cleanly via the
shared autouse conftest fixtures — same pattern as the rest of
``tests/integration/bookings/``.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.bookings import repository as bookings_repo
from app.modules.bookings.models import Booking


@pytest.mark.asyncio
async def test_bookings_created_by_user_id_is_nullable_in_db(
    db_session: AsyncSession,
) -> None:
    """Alembic 0021 effect — information_schema reports is_nullable='YES'.

    The Alembic chain is applied by the conftest scaffolding before any test
    runs; we just observe the current column state.
    """
    result = await db_session.execute(
        text(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name = 'bookings' "
            "  AND column_name = 'created_by_user_id'"
        )
    )
    row = result.first()
    assert row is not None, "bookings.created_by_user_id column not found"
    assert row[0] == "YES", "bookings.created_by_user_id must be NULLABLE after Alembic 0021"


def test_bookings_orm_mapping_marks_created_by_user_id_nullable() -> None:
    """ORM ``Mapped[UUID | None]`` with ``nullable=True`` (Phase 40 D-40-05)."""
    mapper = inspect(Booking)
    column = mapper.columns["created_by_user_id"]
    assert column.nullable is True, (
        "Booking.created_by_user_id must be ORM-nullable (Phase 40 BLOCKER-4)"
    )


def test_insert_booking_signature_accepts_none_created_by_user_id() -> None:
    """Type-level guard: repository.insert_booking takes ``UUID | None``.

    Hits the function signature directly so we don't need DB connectivity to
    catch a regression where someone re-tightens the type to ``UUID``.
    """
    import inspect as _inspect

    sig = _inspect.signature(bookings_repo.insert_booking)
    param = sig.parameters["created_by_user_id"]
    annotation = param.annotation
    # The annotation may be a typing-string form (`'UUID | None'` with PEP 563)
    # or already a resolved type — accept both.
    if isinstance(annotation, str):
        assert "None" in annotation, annotation
    else:
        # When future annotations are not in effect, annotation is a Union
        # (UUID | None) — `type(None)` participates.
        assert type(None) in getattr(annotation, "__args__", ()), annotation
    assert param.default is None, (
        "insert_booking.created_by_user_id default must be None for the bot path"
    )


@pytest.mark.asyncio
async def test_insert_booking_with_null_actor_succeeds(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """``repository.insert_booking(..., created_by_user_id=None)`` succeeds.

    Verifies the column actually accepts NULL at the DB layer, not just at
    the ORM layer — direct repository call mirrors the create_booking_via_bot
    insert site landing in Task 4.
    """
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(
        client_id=client.id,
        plan=plan,
        sessions_remaining=5,
    )
    slot = await make_slot(trainer_id=trainer.id)

    booking = await bookings_repo.insert_booking(
        db_session,
        slot_id=slot.id,
        client_id=client.id,
        pt_package_id=pkg.id,
        created_by_user_id=None,
    )
    await db_session.flush()
    assert booking.created_by_user_id is None

    # Re-fetch via raw SELECT to be sure the row is durable (not just
    # transient SA state).
    row = (await db_session.execute(select(Booking).where(Booking.id == booking.id))).scalar_one()
    assert row.created_by_user_id is None


@pytest.mark.asyncio
async def test_insert_booking_with_real_actor_still_works(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """Reception/owner regression: passing a real UUID still inserts cleanly.

    Phase 40 D-40-05 relaxation must not break the Phase 38 reception path.
    """
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(
        client_id=client.id,
        plan=plan,
        sessions_remaining=5,
    )
    slot = await make_slot(trainer_id=trainer.id)

    booking = await bookings_repo.insert_booking(
        db_session,
        slot_id=slot.id,
        client_id=client.id,
        pt_package_id=pkg.id,
        created_by_user_id=seeded_owner.id,
    )
    await db_session.flush()
    assert booking.created_by_user_id == seeded_owner.id
