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

from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.pagination import PaginatedData
from app.modules.bookings.models import Booking
from app.modules.bookings.schemas import (
    BookingListQuery,
    BookingsForClientListQuery,
    resolve_default_from_time,
    resolve_default_to_time,
)


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


async def get_booking_by_id_for_update_with_slot(
    session: AsyncSession,
    booking_id: UUID,
) -> Booking | None:
    """Row-locked booking read with eager-loaded slot for FSM-guarded transitions.

    Phase 38 plan 38-03 cancel_booking consumer: needs the slot's `start_time`
    in the same query (24h reception window check) AND the row-lock so a
    concurrent slot-cancel cascade serialises with this booking cancel.

    `joinedload(Booking.slot)` fetches the linked trainer_availability_slots
    row in the SAME SELECT (Pitfall 19 — N+1 prevention). The
    `.with_for_update(of=Booking)` row-lock is scoped to the booking row
    only (the slot row is read but not locked here — schedule.service.cancel_slot
    will row-lock the slot independently in its own UoW).
    """
    stmt: Select[tuple[Booking]] = (
        select(Booking)
        .options(joinedload(Booking.slot))
        .where(Booking.id == booking_id)
        .with_for_update(of=Booking)
        # populate_existing() forces SA to overwrite attributes on any in-
        # identity-map row from the DB row returned by this SELECT. Without
        # this, a prior raw `sa.text()` UPDATE (e.g., complete_booking flipping
        # status='completed') leaves the cached ORM instance at the stale
        # pre-UPDATE value, and the FSM gate in cancel_booking would
        # incorrectly admit the transition (test_cancel_completed_booking_409
        # regression). Same pattern is required for the cross-module UPDATE
        # bypassing the ORM identity map.
        .execution_options(populate_existing=True)
    )
    result: Booking | None = await session.scalar(stmt)
    return result


async def get_booking_with_relations(
    session: AsyncSession,
    booking_id: UUID,
) -> Booking | None:
    """Eager-loaded booking read for the GET /bookings/{id} detail endpoint.

    Phase 38 plan 38-03 / BOOK-09 / D-38-08 — denormalized detail payload
    served via joinedload(Booking.slot) + joinedload(Booking.pt_package).
    Pitfall 19: total queries = 1 (single SELECT with JOINs). The unit
    test asserts query count ≤ 2 to catch any future N+1 regression.

    Returns None for missing booking_id (no soft-delete filter — D-38-04
    mirror; cancelled / completed / no_show rows are still returned).
    """
    stmt: Select[tuple[Booking]] = (
        select(Booking)
        .options(
            joinedload(Booking.slot),
            joinedload(Booking.pt_package),
        )
        .where(Booking.id == booking_id)
        # See note on populate_existing in get_booking_by_id_for_update_with_slot:
        # cross-module raw UPDATEs (create_booking flipping slot 'active'→'booked'
        # via repository.update_slot_status_predicate_gated, complete_booking
        # flipping booking 'confirmed'→'completed') bypass the ORM, so the
        # identity-map cache for any pre-loaded slot / booking / pt_package
        # ORM instance carries STALE attribute values. populate_existing()
        # forces SA to overwrite attributes from the row this SELECT returned,
        # so the BookingDetailResponse projection sees the current DB state
        # (e.g., slot.status='booked' for a confirmed booking).
        .execution_options(populate_existing=True)
    )
    result: Booking | None = await session.scalar(stmt)
    return result


def _apply_booking_list_filters(
    stmt: Select[Any],
    *,
    client_id: UUID | None,
    trainer_id: UUID | None,
    from_time: Any,
    to_time: Any,
    status: Any,
) -> tuple[Select[Any], list[Any]]:
    """Build the WHERE predicate set for list_bookings_paginated / per-client.

    Returns a (statement-with-where-applied, predicates-list) tuple so the
    caller can reuse the predicate list for the COUNT statement (avoids
    rebuilding the WHERE clause twice).

    Datetime defaults: when from_time/to_time arrive as None (FastAPI query
    schema can't synthesize a datetime default — see schemas.py for the
    lazy-resolution rationale mirroring plan 38-01 Deviation #1), this
    helper applies the Moscow-relative ±30d default via
    `resolve_default_from_time` / `resolve_default_to_time`.

    Trainer-id filter joins via Booking.slot relationship — preserves the
    modules-independent contract (no schedule.models import; SA resolves
    "TrainerAvailabilitySlot" via Base.registry at mapper-config time).
    """
    effective_from = from_time if from_time is not None else resolve_default_from_time()
    effective_to = to_time if to_time is not None else resolve_default_to_time()
    predicates: list[Any] = [
        Booking.created_at >= effective_from,
        Booking.created_at < effective_to,
    ]
    if client_id is not None:
        predicates.append(Booking.client_id == client_id)
    if status is not None:
        # status may be a StrEnum or plain str — both expose .value/str equiv.
        status_value = getattr(status, "value", status)
        predicates.append(Booking.status == status_value)
    if trainer_id is not None:
        # Join via Booking.slot relationship; SA emits an INNER JOIN against
        # trainer_availability_slots. The relationship is string-keyed in
        # bookings/models.py so no schedule-module import lands here.
        stmt = stmt.join(Booking.slot)
        # Trainer FK lives on the slot — predicate uses sa.text() against the
        # joined table to avoid naming TrainerAvailabilitySlot directly.
        predicates.append(
            sa.text("trainer_availability_slots.trainer_id = :trainer_id_param")
            .bindparams(trainer_id_param=trainer_id)
        )
    return stmt.where(and_(*predicates)), predicates


async def list_bookings_paginated(
    session: AsyncSession,
    query: BookingListQuery,
) -> PaginatedData[Booking]:
    """Paginated booking list with optional filters (Phase 38 plan 38-03 / BOOK-07).

    Filters honoured: client_id, trainer_id (via slot join), from_time/
    to_time (BOOK-07 ±30d Moscow default), status. Orders by
    `created_at DESC, id DESC` (deterministic — id is the tiebreaker).

    Uses `joinedload(Booking.slot)` + `joinedload(Booking.pt_package)` to
    avoid the N+1 trap when consumers serialise BookingResponse with
    derived display fields (Pitfall 19). Even though BookingResponse
    itself doesn't carry slot/pt_package data, the eager-load is cheap
    and future-proofs the read path.

    `PaginatedData.model_construct` skips Pydantic validation against the
    SA ORM generic parameter (mirrors pt_packages.list_pt_packages_paginated).
    """
    base_stmt: Select[tuple[Booking]] = select(Booking).options(
        joinedload(Booking.slot),
        joinedload(Booking.pt_package),
    )
    list_stmt, _predicates = _apply_booking_list_filters(
        base_stmt,
        client_id=query.client_id,
        trainer_id=query.trainer_id,
        from_time=query.from_time,
        to_time=query.to_time,
        status=query.status,
    )

    # COUNT statement: rebuild from scratch with the same predicate set but
    # NO joinedload (count doesn't need the related rows). Re-applies the
    # trainer-id join only when filtering by trainer_id.
    count_base: Select[Any] = select(func.count()).select_from(Booking)
    count_stmt, _ = _apply_booking_list_filters(
        count_base,
        client_id=query.client_id,
        trainer_id=query.trainer_id,
        from_time=query.from_time,
        to_time=query.to_time,
        status=query.status,
    )
    total = await session.scalar(count_stmt) or 0

    list_stmt = list_stmt.order_by(
        Booking.created_at.desc(),
        Booking.id.desc(),
    )
    offset = (query.page - 1) * query.page_size
    list_stmt = list_stmt.offset(offset).limit(query.page_size)

    rows = (await session.scalars(list_stmt)).unique().all()
    return PaginatedData.model_construct(
        items=list(rows),
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


async def list_bookings_for_client_paginated(
    session: AsyncSession,
    client_id: UUID,
    query: BookingsForClientListQuery,
) -> PaginatedData[Booking]:
    """Per-client paginated booking list (Phase 38 plan 38-03 / BOOK-08).

    Same filter shape as `list_bookings_paginated` MINUS `trainer_id`
    (BOOK-08 surface only filters by from/to/status; client_id is taken
    from the URL path). Joinedload chain matches the generic list helper
    so the BookingDetailResponse projection path (if extended in v1.6+)
    finds the related rows already loaded.
    """
    base_stmt: Select[tuple[Booking]] = select(Booking).options(
        joinedload(Booking.slot),
        joinedload(Booking.pt_package),
    )
    list_stmt, _ = _apply_booking_list_filters(
        base_stmt,
        client_id=client_id,
        trainer_id=None,
        from_time=query.from_time,
        to_time=query.to_time,
        status=query.status,
    )
    count_base: Select[Any] = select(func.count()).select_from(Booking)
    count_stmt, _ = _apply_booking_list_filters(
        count_base,
        client_id=client_id,
        trainer_id=None,
        from_time=query.from_time,
        to_time=query.to_time,
        status=query.status,
    )
    total = await session.scalar(count_stmt) or 0

    list_stmt = list_stmt.order_by(
        Booking.created_at.desc(),
        Booking.id.desc(),
    )
    offset = (query.page - 1) * query.page_size
    list_stmt = list_stmt.offset(offset).limit(query.page_size)

    rows = (await session.scalars(list_stmt)).unique().all()
    return PaginatedData.model_construct(
        items=list(rows),
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


__all__ = [
    "get_booking_by_id",
    "get_booking_by_id_for_update_with_slot",
    "get_booking_with_relations",
    "insert_booking",
    "list_bookings_for_client_paginated",
    "list_bookings_paginated",
    "update_slot_status_predicate_gated",
]
