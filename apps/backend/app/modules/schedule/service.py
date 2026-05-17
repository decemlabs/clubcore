"""Schedule module service (Phase 37 placeholder per INFRA-29 / INFRA-33 / D-37-06).

Phase 37 ships stub implementations that always return None so the
composition-root register_* wiring in app/main.py:create_app() can resolve
real callables. Phase 38 replaces these stubs with the actual slot CRUD /
cancel-with-restore logic. The Callable signatures are pinned by
app/core/dependencies.py SlotByIdResolver and BookingSlotRestorerCallable.

The stub bodies ignore all arguments and return None, satisfying:
  - SlotByIdResolver = Callable[[AsyncSession, UUID], Awaitable[SlotById | None]]
  - BookingSlotRestorerCallable = Callable[[AsyncSession, UUID], Awaitable[None]]

Per PATTERNS.md §5 Recommendation (Option B): zero-LOC bodies trivially
satisfy the SVC001 commit-gate walker (no session writes to gate); the
INFRA-33 startup wiring + AST parity tests pass from the first commit.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


async def resolve_slot_by_id(session: AsyncSession, slot_id: UUID) -> None:
    """Phase 37 stub. Phase 38 returns a SlotById-conformant ORM row or None."""
    _ = (session, slot_id)
    return None


async def restore_slot_to_active(session: AsyncSession, slot_id: UUID) -> None:
    """Phase 37 stub. Phase 38 flips slot.status from 'booked' to 'active' in caller's UoW."""
    _ = (session, slot_id)
    return None
