"""Bookings module service (Phase 37 placeholder per INFRA-29 / INFRA-33 / D-37-06).

Phase 37 shipped a stub `complete_booking` implementation so the
composition-root register_* wiring in app/main.py:create_app() can resolve
a real callable. Phase 38 plan 38-02 Task 2 lands the router + a
`create_booking` stub here so the router is mountable; Task 3 replaces
the stub with the real atomic UoW (slot transition + booking INSERT +
audit emit + IntegrityError race translation + Moscow-TZ validity-window
guard).
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.modules.bookings.schemas import BookingCreateRequest, BookingResponse


async def complete_booking(session: AsyncSession, booking_id: UUID) -> None:
    """Phase 37 stub.

    Phase 38 plan 38-02 Task 3 transitions booking.status 'confirmed' ->
    'completed' in caller's UoW.
    """
    _ = (session, booking_id)
    return None


async def create_booking(
    session: AsyncSession,
    actor: CurrentUser,
    data: BookingCreateRequest,
) -> BookingResponse:
    """Phase 38 plan 38-02 Task 2 stub.

    Task 3 replaces this body with the 10-step atomic UoW (resolve slot →
    validate pt_package + trainer + validity-window → flip slot
    active→booked → INSERT booking → flush → translate IntegrityError on
    uq_bookings_slot_confirmed → emit booking_created → commit). For now
    the route exists and is mountable; calls raise NotImplementedError so
    the smoke surface is reachable without the orchestrator logic.
    """
    _ = (session, actor, data)
    raise NotImplementedError("plan 38-02 Task 3 — create_booking lands in the next commit")
