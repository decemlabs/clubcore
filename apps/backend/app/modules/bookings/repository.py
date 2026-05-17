"""Bookings repository — single point of access to the Booking ORM.

This is the ONLY module in the codebase that imports the Booking ORM
model from `bookings.models`. The service layer calls these module-level
async helpers and never executes `select(Booking)` directly. That single
rule constructively guarantees the alive-bias invariant — status filters
happen here in repository land, mirrors v1.4 pt_packages discipline.

NO soft-delete (D-38-04 mirror): bookings are decommissioned by status
flip to 'cancelled'; `get_booking_by_id` does NOT filter on `deleted_at`
(the column does not exist on this table).

Transaction control: caller-owns-txn (mirror memberships D-14 / pt_packages
discipline). NO commits or flushes live in this module — the service layer
(caller) owns the transactional moment so it can co-write the audit_log row
in the same UoW.

Cross-module reach (D-38-11 / D-34-04a discipline):
- `update_slot_status_predicate_gated` issues a raw `sa.text()` UPDATE
  against `trainer_availability_slots`. Annotated with the canonical
  `# noqa: TABLE_REF` marker so grep + import-linter contract stay clean
  (NEVER reach the schedule module via direct ORM import — table name
  only, raw text statement only).

`from __future__ import annotations` is required: list helpers will be
annotated with `PaginatedData[Booking]` (Phase 38 plan 38-03 list
endpoints), and the SA ORM class is not Pydantic-compatible at runtime
(mirrors pt_packages/repository.py rationale).
"""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bookings.models import Booking


async def get_booking_by_id(
    session: AsyncSession,
    booking_id: UUID,
) -> Booking | None:
    """Return booking by id, or None for missing (D-38-04 mirror — no soft-delete filter).

    Cancelled / no_show / completed rows are still returned; lifecycle is
    purely status-based. Phase 38 plan 38-03 read/cancel endpoints consume.
    """
    stmt: Select[tuple[Booking]] = select(Booking).where(Booking.id == booking_id)
    result: Booking | None = await session.scalar(stmt)
    return result


async def insert_booking(
    session: AsyncSession,
    *,
    slot_id: UUID,
    client_id: UUID,
    pt_package_id: UUID,
    created_by_user_id: UUID,
) -> Booking:
    """Insert a Booking row. Caller MUST flush + commit (D-38 SVC001).

    Keyword-only after `*` to match the call shape from
    `service.create_booking` and document field intent at the callsite
    (mirrors pt_sessions/repository.py:insert_pt_session).

    Status defaults to 'confirmed' via the server_default in the ORM
    column. No `status=` kwarg here — the partial UNIQUE
    `uq_bookings_slot_confirmed` only triggers when status='confirmed',
    so the create-path NEVER inserts any other status.
    """
    booking = Booking(
        slot_id=slot_id,
        client_id=client_id,
        pt_package_id=pt_package_id,
        created_by_user_id=created_by_user_id,
        status="confirmed",
    )
    session.add(booking)
    return booking


async def update_slot_status_predicate_gated(
    session: AsyncSession,
    slot_id: UUID,
    *,
    from_status: str,
    to_status: str,
) -> bool:
    """Predicate-gated raw UPDATE on trainer_availability_slots from this module.

    Returns True iff one row updated, False otherwise (concurrent loser
    or wrong-status path). Caller-owns-txn — no flush, no commit; SVC001
    walker covers the public mutator that invokes this helper.

    Cross-module reach: this UPDATE targets `trainer_availability_slots`
    (owned by the schedule module). The `# noqa: TABLE_REF cross-module
    SQL per D-34-04a / Phase 38 D-38-11` marker documents the deliberate
    boundary crossing. NEVER reach the schedule module via direct ORM
    import here — that would break the modules-independent importlinter
    contract; table-name-only raw text is the documented escape.

    Used by `service.create_booking` to flip slot active→booked inside
    the same UoW as the booking INSERT, mirroring the pattern from
    `pt_sessions/repository.py:atomic_decrement_pt_package` (raw text
    predicate-gated UPDATE; the predicate is the sole race arbiter).
    """
    stmt = sa.text(
        """
        UPDATE trainer_availability_slots
        SET status = :to_status,
            updated_at = now()
        WHERE id = :slot_id AND status = :from_status
        RETURNING id
        """,  # noqa: TABLE_REF cross-module SQL per D-34-04a / Phase 38 D-38-11
    )
    result = await session.execute(
        stmt,
        {
            "slot_id": slot_id,
            "from_status": from_status,
            "to_status": to_status,
        },
    )
    return result.first() is not None


__all__ = [
    "get_booking_by_id",
    "insert_booking",
    "update_slot_status_predicate_gated",
]
