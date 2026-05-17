"""Bookings module service (Phase 37 placeholder per INFRA-29 / INFRA-33 / D-37-06).

Phase 37 ships a stub implementation that always returns None so the
composition-root register_* wiring in app/main.py:create_app() can resolve
a real callable. Phase 38 replaces this stub with the actual
booking-FSM-transition logic. The Callable signature is pinned by
app/core/dependencies.py BookingCompleterCallable.

The stub body ignores all arguments and returns None, satisfying:
  - BookingCompleterCallable = Callable[[AsyncSession, UUID], Awaitable[None]]

Per PATTERNS.md §5 Recommendation (Option B): zero-LOC body trivially
satisfies the SVC001 commit-gate walker (no session writes to gate); the
INFRA-33 startup wiring + AST parity tests pass from the first commit.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


async def complete_booking(session: AsyncSession, booking_id: UUID) -> None:
    """Phase 37 stub.

    Phase 38 transitions booking.status 'confirmed' -> 'completed' in caller's UoW.
    """
    _ = (session, booking_id)
    return None
