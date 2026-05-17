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

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PaginatedData
from app.modules.schedule.models import TrainerAvailabilitySlot
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
    """
    stmt: Select[tuple[TrainerAvailabilitySlot]] = select(TrainerAvailabilitySlot).where(
        TrainerAvailabilitySlot.id == slot_id
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
        .where(where_clause)
        .order_by(
            TrainerAvailabilitySlot.start_time.asc(),
            TrainerAvailabilitySlot.id.asc(),
        )
    )
    offset = (query.page - 1) * query.page_size
    stmt = stmt.offset(offset).limit(query.page_size)
    rows = (await session.scalars(stmt)).all()
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


__all__ = [
    "find_buffer_violations",
    "find_overlapping_slots_for_update",
    "get_slot_by_id",
    "get_slot_by_id_for_update",
    "insert_slot",
    "list_slots_paginated",
    "update_slot_status_predicate_gated",
]
