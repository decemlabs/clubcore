"""Schedule module service (Phase 38 plan 38-01).

Phase 37 shipped stub implementations for `resolve_slot_by_id` and
`restore_slot_to_active` (signatures pinned by `SlotByIdResolver` /
`BookingSlotRestorerCallable` Protocol slots in core/dependencies.py).

Phase 38 plan 38-01 Task 2 lands the read-only orchestrators
(`list_slots`, `get_slot`) as thin call-throughs to repository helpers
so the router-level smoke tests can assert end-to-end shape contracts.

Task 3 replaces:
  - resolve_slot_by_id body with `repository.get_slot_by_id` delegate.
  - restore_slot_to_active body with predicate-gated UPDATE.
  - publish_slot stub with the full 10-step orchestrator (FK check,
    future-only guard, overlap/buffer detection, INSERT, audit, commit).
  - cancel_slot stub with the active-only FSM transition (booked-cascade
    lands in plan 38-03).
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.core.exceptions import NotFoundError
from app.core.pagination import PaginatedData
from app.modules.schedule import repository
from app.modules.schedule.schemas import (
    SlotCancelRequest,
    SlotCreateRequest,
    SlotListQuery,
    SlotResponse,
)


class SlotNotFoundError(NotFoundError):
    """Raised by get_slot / cancel_slot when the slot id does not exist."""

    code = "slot_not_found"
    status_code = 404


async def resolve_slot_by_id(session: AsyncSession, slot_id: UUID) -> None:
    """Phase 37 stub. Phase 38 Task 3 returns a SlotById-conformant ORM row or None."""
    _ = (session, slot_id)
    return None


async def restore_slot_to_active(session: AsyncSession, slot_id: UUID) -> None:
    """Phase 37 stub. Phase 38 Task 3 flips slot.status booked → active in caller's UoW."""
    _ = (session, slot_id)
    return None


# ---------------------------------------------------------------------------
# Phase 38 plan 38-01 Task 2 — read-only orchestrators (delegates).
# ---------------------------------------------------------------------------


async def list_slots(
    session: AsyncSession,
    query: SlotListQuery,
) -> PaginatedData[SlotResponse]:
    """Paginated slot list (SLOT-08). Read-only — NO commit.

    Delegates to `repository.list_slots_paginated`; maps ORM rows to
    `SlotResponse` via `model_validate(..., from_attributes=True)`. The
    repository resolves default time-window bounds when the query fields
    are None (FastAPI query schema cannot synthesize a default datetime).
    """
    page = await repository.list_slots_paginated(session, query)
    return PaginatedData.model_construct(
        items=[SlotResponse.model_validate(s, from_attributes=True) for s in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )


async def get_slot(
    session: AsyncSession,
    slot_id: UUID,
) -> SlotResponse:
    """Read a single slot (SLOT-08 detail). 404 `slot_not_found` for missing id."""
    slot = await repository.get_slot_by_id(session, slot_id)
    if slot is None:
        raise SlotNotFoundError("slot_not_found")
    return SlotResponse.model_validate(slot, from_attributes=True)


# ---------------------------------------------------------------------------
# Phase 38 plan 38-01 Task 3 — mutators land here. Placeholders raise so
# router smoke tests for the mutation surface document the deferred work.
# ---------------------------------------------------------------------------


async def publish_slot(
    session: AsyncSession,
    actor: CurrentUser,
    data: SlotCreateRequest,
) -> SlotResponse:
    """Task 3 — real publish_slot orchestrator (SLOT-02..06)."""
    _ = (session, actor, data)
    raise NotImplementedError("publish_slot lands in Task 3 of plan 38-01")


async def cancel_slot(
    session: AsyncSession,
    actor: CurrentUser,
    slot_id: UUID,
    data: SlotCancelRequest,
) -> SlotResponse:
    """Task 3 — cancel active-only path (SLOT-09; booked-cascade in plan 38-03)."""
    _ = (session, actor, slot_id, data)
    raise NotImplementedError("cancel_slot lands in Task 3 of plan 38-01")
