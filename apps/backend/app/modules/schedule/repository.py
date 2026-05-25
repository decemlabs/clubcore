"""Schedule repository — single point of access to the TrainerAvailabilitySlot ORM.

This is the ONLY module in the codebase that imports the TrainerAvailabilitySlot
ORM model from `schedule.models`. The service layer calls these module-level
async helpers and never executes `select(TrainerAvailabilitySlot)` directly.
That single rule constructively guarantees the alive-bias invariant (every
status filter happens here in repository land, mirrors v1.4 pt_packages
discipline).

NO soft-delete (D-38-04): slots are decommissioned by status flip to
'cancelled'; the repository's `get_slot_by_id` does NOT filter on deleted_at
(the column does not exist on this table).

Transaction control: NO `session.commit()` and NO `session.flush()` calls live
here (mirror memberships D-14 / pt_packages caller-owns-txn). The caller
(service) owns the transactional moment so it can co-write the audit_log row
in the same UoW.

`from __future__ import annotations` is required: list helpers are annotated
with `PaginatedData[TrainerAvailabilitySlot]`, and the SA ORM class is not
Pydantic-compatible. Without PEP 563 deferred evaluation, importing this
module triggers `PaginatedData.__class_getitem__(...)` at runtime, which
delegates to Pydantic's generic schema-builder and raises
`PydanticSchemaGenerationError` (mirrors pt_packages/repository.py rationale).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Select, and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.pagination import PaginatedData
from app.modules.schedule.models import (
    RecurringSlotTemplate,
    TrainerAvailabilitySlot,
    TrainerTimeOff,
)
from app.modules.schedule.schemas import (
    SlotListQuery,
    resolve_default_from_time,
    resolve_default_to_time,
)


async def get_slot_by_id(
    session: AsyncSession, slot_id: UUID
) -> TrainerAvailabilitySlot | None:
    """Return slot by id, or None for missing (D-38-04 — NO soft-delete filter).

    Cancelled / booked rows are still returned; lifecycle is purely status-based.
    Phase 38 bookings.service consumes via the SlotById Protocol slot in
    core.dependencies (silent-None per D-37-06).

    Phase 40 BLOCKER-2 — ``joinedload(TrainerAvailabilitySlot.trainer)`` so the
    schedule service can project ``trainer_full_name`` into ``SlotResponse``
    without an N+1 lookup (D-38-08 — preserves modules-independent contract;
    the relationship is string-keyed so no ``trainers`` module import is
    introduced here).
    """
    stmt: Select[tuple[TrainerAvailabilitySlot]] = (
        select(TrainerAvailabilitySlot)
        .options(joinedload(TrainerAvailabilitySlot.trainer))
        .where(TrainerAvailabilitySlot.id == slot_id)
    )
    result: TrainerAvailabilitySlot | None = await session.scalar(stmt)
    return result


async def get_slot_by_id_for_update(
    session: AsyncSession, slot_id: UUID
) -> TrainerAvailabilitySlot | None:
    """Row-locked slot read for FSM-guarded transitions (Phase 38 cancel_slot)."""
    stmt: Select[tuple[TrainerAvailabilitySlot]] = (
        select(TrainerAvailabilitySlot)
        .where(TrainerAvailabilitySlot.id == slot_id)
        .with_for_update()
    )
    result: TrainerAvailabilitySlot | None = await session.scalar(stmt)
    return result


async def insert_slot(
    session: AsyncSession,
    *,
    trainer_id: UUID,
    start_time: datetime,
    end_time: datetime,
    created_by_user_id: UUID,
) -> TrainerAvailabilitySlot:
    """Insert a TrainerAvailabilitySlot row. Caller MUST flush + commit (D-38-04 / SVC001)."""
    slot = TrainerAvailabilitySlot(
        trainer_id=trainer_id,
        start_time=start_time,
        end_time=end_time,
        created_by_user_id=created_by_user_id,
        status="active",
    )
    session.add(slot)
    return slot


async def list_slots_paginated(
    session: AsyncSession, query: SlotListQuery
) -> PaginatedData[TrainerAvailabilitySlot]:
    """Paginated slot list with optional trainer_id + status + time-window filters.

    Mirrors pt_packages.list_pt_packages_paginated — `model_construct` to skip
    Pydantic validation against the SA ORM generic parameter. Defaults from
    SlotListQuery (trainer_id=None, status=ACTIVE, 14d Moscow window) are
    applied at the schema layer.
    """
    from_time = query.from_time if query.from_time is not None else resolve_default_from_time()
    to_time = query.to_time if query.to_time is not None else resolve_default_to_time()
    predicates: list[Any] = [
        TrainerAvailabilitySlot.start_time >= from_time,
        TrainerAvailabilitySlot.start_time < to_time,
        TrainerAvailabilitySlot.status == query.status.value,
    ]
    if query.trainer_id is not None:
        predicates.append(TrainerAvailabilitySlot.trainer_id == query.trainer_id)

    where_clause = and_(*predicates)

    total_stmt = (
        select(func.count())
        .select_from(TrainerAvailabilitySlot)
        .where(where_clause)
    )
    total = await session.scalar(total_stmt) or 0

    stmt: Select[tuple[TrainerAvailabilitySlot]] = (
        select(TrainerAvailabilitySlot)
        # Phase 40 BLOCKER-2 — eager-load trainer for trainer_full_name
        # projection in SlotResponse (avoids N+1; D-38-08 preserved).
        .options(joinedload(TrainerAvailabilitySlot.trainer))
        .where(where_clause)
        .order_by(
            TrainerAvailabilitySlot.start_time.asc(),
            TrainerAvailabilitySlot.id.asc(),
        )
    )
    offset = (query.page - 1) * query.page_size
    stmt = stmt.offset(offset).limit(query.page_size)
    rows = (await session.scalars(stmt)).unique().all()
    return PaginatedData.model_construct(
        items=list(rows),
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


async def find_overlapping_slots_for_update(
    session: AsyncSession,
    *,
    trainer_id: UUID,
    start_time: datetime,
    end_time: datetime,
) -> list[UUID]:
    """Return non-cancelled slots for `trainer_id` whose tstzrange overlaps
    [start_time, end_time) (D-38-06 — app-layer overlap check via Postgres
    tstzrange '&&' operator).

    `with_for_update()` row-locks the candidate slots so two concurrent
    publishes against the same trainer's overlapping window serialise at
    the DB layer (the row-lock holds until the surrounding service
    transaction commits).
    """
    stmt = (
        select(TrainerAvailabilitySlot.id)
        .where(
            TrainerAvailabilitySlot.trainer_id == trainer_id,
            TrainerAvailabilitySlot.status != "cancelled",
            sa.func.tstzrange(
                TrainerAvailabilitySlot.start_time,
                TrainerAvailabilitySlot.end_time,
                "[)",
            ).op("&&")(sa.func.tstzrange(start_time, end_time, "[)")),
        )
        .with_for_update()
    )
    rows = await session.scalars(stmt)
    return list(rows.all())


async def find_buffer_violations(
    session: AsyncSession,
    *,
    trainer_id: UUID,
    start_time: datetime,
    end_time: datetime,
    buffer_minutes: int,
) -> list[UUID]:
    """Return non-cancelled slots for `trainer_id` whose widened tstzrange
    overlaps the buffer-widened candidate range (D-38-07 — SLOT_BUFFER_MINUTES
    enforcement).

    Discriminator vs `find_overlapping_slots_for_update`: this helper widens
    the candidate range by `buffer_minutes` on each side and EXCLUDES exact
    overlaps (those already triggered the slot_overlap branch). The 10-minute
    boundary is inclusive on the boundary itself — a slot ending exactly
    10 minutes before the new start is OK (>= boundary), only strict gap < 10
    triggers the violation.
    """
    delta = timedelta(minutes=buffer_minutes)
    widened_start = start_time - delta
    widened_end = end_time + delta
    stmt = (
        select(TrainerAvailabilitySlot.id)
        .where(
            TrainerAvailabilitySlot.trainer_id == trainer_id,
            TrainerAvailabilitySlot.status != "cancelled",
            sa.func.tstzrange(
                TrainerAvailabilitySlot.start_time,
                TrainerAvailabilitySlot.end_time,
                "[)",
            ).op("&&")(sa.func.tstzrange(widened_start, widened_end, "[)")),
            # Exclude rows that already overlap the unwidened candidate
            # range — those are slot_overlap, not slot_too_close.
            ~sa.func.tstzrange(
                TrainerAvailabilitySlot.start_time,
                TrainerAvailabilitySlot.end_time,
                "[)",
            ).op("&&")(sa.func.tstzrange(start_time, end_time, "[)")),
        )
        .with_for_update()
    )
    rows = await session.scalars(stmt)
    return list(rows.all())


async def update_slot_status_predicate_gated(
    session: AsyncSession,
    slot_id: UUID,
    *,
    from_status: str,
    to_status: str,
    cancel_reason: str | None = None,
) -> bool:
    """Predicate-gated raw UPDATE — flip slot status iff current matches `from_status`.

    Returns True when one row updated, False otherwise (the concurrent loser
    or wrong-status path). Caller-owns-txn — no flush, no commit; SVC001
    walker covers the public mutator that invokes this helper.

    Mirrors pt_sessions/repository.py atomic_transition_exhausted_to_active
    raw-text predicate-gated pattern (defeats lost-update via single SQL
    statement). The `cancel_reason` + `cancelled_at` columns are conditionally
    cleared/set inside the same statement depending on direction.
    """
    if to_status == "cancelled":
        stmt = sa.text(
            """
            UPDATE trainer_availability_slots
            SET status = :to_status,
                cancelled_at = now(),
                cancel_reason = :cancel_reason,
                updated_at = now()
            WHERE id = :slot_id AND status = :from_status
            RETURNING id
            """,
        )
        params: dict[str, object] = {
            "slot_id": slot_id,
            "from_status": from_status,
            "to_status": to_status,
            "cancel_reason": cancel_reason,
        }
    else:
        # Restore (booked -> active) flow: clear cancellation fields.
        stmt = sa.text(
            """
            UPDATE trainer_availability_slots
            SET status = :to_status,
                cancelled_at = NULL,
                cancel_reason = NULL,
                updated_at = now()
            WHERE id = :slot_id AND status = :from_status
            RETURNING id
            """,
        )
        params = {
            "slot_id": slot_id,
            "from_status": from_status,
            "to_status": to_status,
        }
    result = await session.execute(stmt, params)
    return result.first() is not None


# ---------------------------------------------------------------------------
# Phase 59 — RecurringSlotTemplate helpers (REC-01 / REC-04)
# ---------------------------------------------------------------------------


async def insert_recurring_template(
    session: AsyncSession,
    *,
    trainer_id: UUID,
    day_of_week: int,
    start_time: Any,  # datetime.time
    end_time: Any,    # datetime.time
    valid_from: date,
    valid_until: date | None,
) -> RecurringSlotTemplate | None:
    """Insert a RecurringSlotTemplate. Returns None on UNIQUE violation
    (trainer_id, day_of_week, start_time, valid_from) — caller raises ConflictError.
    Caller owns flush + commit (SVC001).
    """
    tmpl = RecurringSlotTemplate(
        trainer_id=trainer_id,
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
        valid_from=valid_from,
        valid_until=valid_until,
        is_active=True,
    )
    session.add(tmpl)
    try:
        await session.flush()
        return tmpl
    except IntegrityError as exc:
        await session.rollback()
        # Re-raise as None only on the UNIQUE violation; propagate other errors.
        if "uq_recurring_slot_templates_trainer_id" in str(exc.orig):
            return None
        raise


async def get_recurring_template_by_id_for_update(
    session: AsyncSession,
    template_id: UUID,
) -> RecurringSlotTemplate | None:
    """Row-locked fetch for FSM-guarded mutations (deactivate)."""
    stmt: Select[tuple[RecurringSlotTemplate]] = (
        select(RecurringSlotTemplate)
        .where(RecurringSlotTemplate.id == template_id)
        .with_for_update()
    )
    result: RecurringSlotTemplate | None = await session.scalar(stmt)
    return result


async def list_recurring_templates(
    session: AsyncSession,
    *,
    trainer_id: UUID | None = None,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedData[RecurringSlotTemplate]:
    """Paginated list of recurring templates (both roles — REC-04)."""
    predicates: list[Any] = []
    if trainer_id is not None:
        predicates.append(RecurringSlotTemplate.trainer_id == trainer_id)

    where_clause = and_(*predicates) if predicates else sa.true()

    total_stmt = (
        select(func.count())
        .select_from(RecurringSlotTemplate)
        .where(where_clause)
    )
    total = await session.scalar(total_stmt) or 0

    stmt: Select[tuple[RecurringSlotTemplate]] = (
        select(RecurringSlotTemplate)
        .where(where_clause)
        .order_by(
            RecurringSlotTemplate.created_at.asc(),
            RecurringSlotTemplate.id.asc(),
        )
    )
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)
    rows = (await session.scalars(stmt)).all()
    return PaginatedData.model_construct(
        items=list(rows),
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# Phase 59 — TrainerTimeOff helpers (REC-03 / REC-04)
# ---------------------------------------------------------------------------


async def insert_time_off(
    session: AsyncSession,
    *,
    trainer_id: UUID,
    block_start: datetime,
    block_end: datetime,
    reason: str | None,
) -> TrainerTimeOff:
    """Insert a TrainerTimeOff block. Caller owns flush + commit (SVC001)."""
    time_off = TrainerTimeOff(
        trainer_id=trainer_id,
        block_start=block_start,
        block_end=block_end,
        reason=reason,
    )
    session.add(time_off)
    return time_off


async def get_time_off_by_id(
    session: AsyncSession,
    time_off_id: UUID,
) -> TrainerTimeOff | None:
    """Return a TrainerTimeOff row by id, or None."""
    stmt: Select[tuple[TrainerTimeOff]] = (
        select(TrainerTimeOff).where(TrainerTimeOff.id == time_off_id)
    )
    result: TrainerTimeOff | None = await session.scalar(stmt)
    return result


async def list_time_off(
    session: AsyncSession,
    *,
    trainer_id: UUID | None = None,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedData[TrainerTimeOff]:
    """Paginated list of time-off blocks (both roles — REC-04)."""
    predicates: list[Any] = []
    if trainer_id is not None:
        predicates.append(TrainerTimeOff.trainer_id == trainer_id)

    where_clause = and_(*predicates) if predicates else sa.true()

    total_stmt = (
        select(func.count())
        .select_from(TrainerTimeOff)
        .where(where_clause)
    )
    total = await session.scalar(total_stmt) or 0

    stmt: Select[tuple[TrainerTimeOff]] = (
        select(TrainerTimeOff)
        .where(where_clause)
        .order_by(
            TrainerTimeOff.block_start.asc(),
            TrainerTimeOff.id.asc(),
        )
    )
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)
    rows = (await session.scalars(stmt)).all()
    return PaginatedData.model_construct(
        items=list(rows),
        total=total,
        page=page,
        page_size=page_size,
    )


__all__ = [
    "find_buffer_violations",
    "find_overlapping_slots_for_update",
    "get_recurring_template_by_id_for_update",
    "get_slot_by_id",
    "get_slot_by_id_for_update",
    "get_time_off_by_id",
    "insert_recurring_template",
    "insert_slot",
    "insert_time_off",
    "list_recurring_templates",
    "list_slots_paginated",
    "list_time_off",
    "update_slot_status_predicate_gated",
]
