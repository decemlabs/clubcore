"""Phase 39 CRON-02 + NOTIFY-05 integration tests — _send_booking_reminders
multi-session cron + booking_notifications idempotency-row insert + IntegrityError
rollback + 403 skip + unlinked-client SELECT exclusion (D-39-08 / D-39-13 / D-39-19).

Direct calls to the service helper against the SAVEPOINT-rolled ``db_session``
via the ``notifications_session_factory`` (``_SavepointSessionmaker``) wrapper —
the helper's per-send write sessions translate to SAVEPOINT releases inside the
outer test transaction, which rolls back at test teardown.

Coverage (5 scenarios per plan 39-04 Task 4 revised contract):
  1. Happy path — eligible booking → 1 send + 1 booking_notifications row.
  2. Idempotent re-run — 2nd helper call returns 0; LEFT JOIN pre-filter
     excludes the already-notified row; sender NEVER reached.
  3. 403-blocked skip — SendResult(ok=False, blocked=True) → WARNING-log
     ``booking_reminder_send_failed reason='bot_blocked'`` + NO row.
  4. Unlinked-client SELECT exclusion — client with
     ``telegram_user_id IS NULL`` → SQL filter excludes; zero sender calls.
  5. IntegrityError collision rollback — a parallel-session pre-INSERT
     between render + post-send write triggers the UNIQUE violation;
     helper rolls back the write session + INFO-logs
     ``booking_reminder_idempotency_collision`` + continues.

Out of scope (D-39-18): real-Postgres asyncio.gather race test between the
reminder cron and a one-shot operator runner — that lands in Phase 40
VER-07 milestone verification. Scenario 5 above LOCKS the IntegrityError
branch under test coverage so the branch is not dead code.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import pytest_asyncio
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.telegram.sender import SendResult
from app.modules.auth.models import User
from app.modules.bookings import notifications as bookings_notifications
from app.modules.bookings import service as bookings_service
from app.modules.bookings.models import Booking, BookingNotification
from app.modules.bookings.service import MOSCOW_TZ
from app.modules.clients.models import Client
from app.modules.pt_packages.models import PtPackage
from app.modules.schedule.models import TrainerAvailabilitySlot
from app.modules.trainers.models import Trainer


@pytest_asyncio.fixture(autouse=True)
async def _reset_reminder_worker_logger_cache() -> AsyncIterator[None]:
    """Invalidate the module-level structlog cache so ``capture_logs()`` works.

    Mirrors ``_reset_no_show_worker_logger_cache`` in ``test_no_show_cron.py``
    — without this reset, ``structlog.testing.capture_logs()`` misses the
    helper's INFO + WARNING lines because the ``BoundLoggerLazyProxy`` caches
    its first-call processor list at module import time.

    Resets BOTH ``bookings.service._log`` (where the helper emits its
    summary + collision + failure events) AND the worker module's ``_log``
    (kept for symmetry with the no-show conftest pattern; the worker
    function itself is not exercised in this test file but the import side-
    effect would still warm its cache).
    """
    from app.workers.scheduled import send_booking_reminders as worker_mod

    if "bind" in worker_mod._log.__dict__:
        del worker_mod._log.__dict__["bind"]
    if "bind" in bookings_service._log.__dict__:
        del bookings_service._log.__dict__["bind"]
    yield


async def _seed_eligible_reminder_candidate(
    *,
    make_active_trainer: Callable[..., Awaitable[Trainer]],
    make_linked_client: Callable[..., Awaitable[Client]] | None,
    make_unlinked_client: Callable[..., Awaitable[Client]] | None,
    make_future_slot: Callable[..., Awaitable[TrainerAvailabilitySlot]],
    make_active_pt_package: Callable[..., Awaitable[PtPackage]],
    make_confirmed_booking: Callable[..., Awaitable[Booking]],
    actor: User,
    telegram_user_id: int | None = 100001,
    start_offset: timedelta = timedelta(hours=24),
) -> tuple[Booking, TrainerAvailabilitySlot, Client, Trainer]:
    """Seed one confirmed booking inside the 23h-25h reminder window.

    ``telegram_user_id=None`` selects the unlinked-client factory (SQL
    pre-filter excludes); a positive int seeds a linked client.

    Returns (booking, slot, client, trainer) — the trainer is returned so
    tests can pre-compute the expected DM text without re-querying.
    """
    trainer = await make_active_trainer()
    if telegram_user_id is None:
        assert make_unlinked_client is not None
        client = await make_unlinked_client()
    else:
        assert make_linked_client is not None
        client = await make_linked_client(telegram_user_id=telegram_user_id)
    pt_package = await make_active_pt_package(client=client, trainer=trainer)
    slot = await make_future_slot(
        trainer=trainer,
        start_offset=start_offset,
        duration=timedelta(hours=1),
    )
    booking = await make_confirmed_booking(
        slot=slot,
        client=client,
        pt_package=pt_package,
        actor_user_id=actor.id,
    )
    return booking, slot, client, trainer


async def test_reminders_cron_inserts_idempotency_row_per_send(
    db_session: AsyncSession,
    notifications_session_factory: Any,
    fake_bot: object,
    sender_stub: Any,
    seeded_owner: User,
    make_active_trainer: Callable[..., Awaitable[Trainer]],
    make_linked_client: Callable[..., Awaitable[Client]],
    make_future_slot: Callable[..., Awaitable[TrainerAvailabilitySlot]],
    make_active_pt_package: Callable[..., Awaitable[PtPackage]],
    make_confirmed_booking: Callable[..., Awaitable[Booking]],
) -> None:
    """Happy path: 1 candidate → 1 send → 1 booking_notifications row."""
    sender_module, sender_state = sender_stub

    booking, slot, client, trainer = await _seed_eligible_reminder_candidate(
        make_active_trainer=make_active_trainer,
        make_linked_client=make_linked_client,
        make_unlinked_client=None,
        make_future_slot=make_future_slot,
        make_active_pt_package=make_active_pt_package,
        make_confirmed_booking=make_confirmed_booking,
        actor=seeded_owner,
    )

    expected_text = bookings_notifications.render_booking_reminder_24h_dm(
        client_name=client.first_name,
        trainer_name=trainer.full_name,
        slot_start_msk=slot.start_time.astimezone(MOSCOW_TZ).strftime(
            "%d.%m.%Y %H:%M"
        ),
    )

    count = await bookings_service._send_booking_reminders(
        notifications_session_factory,
        bot=fake_bot,  # type: ignore[arg-type]  # sentinel; sender stub never reaches in
        sender=sender_module,
        notifications_module=bookings_notifications,
    )

    assert count == 1
    assert len(sender_state.calls) == 1
    assert sender_state.calls[0].chat_id == client.telegram_user_id
    assert sender_state.calls[0].text == expected_text

    # Idempotency row inserted via the helper's per-send write session.
    notif_rows = (
        await db_session.execute(
            select(BookingNotification).where(
                BookingNotification.booking_id == booking.id
            )
        )
    ).scalars().all()
    assert len(notif_rows) == 1
    assert notif_rows[0].kind == "reminder_24h"


async def test_reminders_cron_idempotent_second_run_zero(
    db_session: AsyncSession,
    notifications_session_factory: Any,
    fake_bot: object,
    sender_stub: Any,
    seeded_owner: User,
    make_active_trainer: Callable[..., Awaitable[Trainer]],
    make_linked_client: Callable[..., Awaitable[Client]],
    make_future_slot: Callable[..., Awaitable[TrainerAvailabilitySlot]],
    make_active_pt_package: Callable[..., Awaitable[PtPackage]],
    make_confirmed_booking: Callable[..., Awaitable[Booking]],
) -> None:
    """LEFT JOIN booking_notifications pre-filter excludes the notified row."""
    sender_module, sender_state = sender_stub

    booking, *_ = await _seed_eligible_reminder_candidate(
        make_active_trainer=make_active_trainer,
        make_linked_client=make_linked_client,
        make_unlinked_client=None,
        make_future_slot=make_future_slot,
        make_active_pt_package=make_active_pt_package,
        make_confirmed_booking=make_confirmed_booking,
        actor=seeded_owner,
    )

    first = await bookings_service._send_booking_reminders(
        notifications_session_factory,
        bot=fake_bot,  # type: ignore[arg-type]
        sender=sender_module,
        notifications_module=bookings_notifications,
    )
    assert first == 1

    second = await bookings_service._send_booking_reminders(
        notifications_session_factory,
        bot=fake_bot,  # type: ignore[arg-type]
        sender=sender_module,
        notifications_module=bookings_notifications,
    )

    assert second == 0
    assert len(sender_state.calls) == 1, (
        "sender must NOT be called on idempotent re-run — the LEFT JOIN "
        "n.id IS NULL pre-filter excludes the already-notified row at "
        "the SELECT layer"
    )

    notif_rows = (
        await db_session.execute(
            select(BookingNotification).where(
                BookingNotification.booking_id == booking.id
            )
        )
    ).scalars().all()
    assert len(notif_rows) == 1


async def test_reminders_cron_skips_403_blocked_no_row(
    db_session: AsyncSession,
    notifications_session_factory: Any,
    fake_bot: object,
    sender_stub: Any,
    seeded_owner: User,
    make_active_trainer: Callable[..., Awaitable[Trainer]],
    make_linked_client: Callable[..., Awaitable[Client]],
    make_future_slot: Callable[..., Awaitable[TrainerAvailabilitySlot]],
    make_active_pt_package: Callable[..., Awaitable[PtPackage]],
    make_confirmed_booking: Callable[..., Awaitable[Booking]],
) -> None:
    """403-blocked send → WARNING-log + NO booking_notifications row."""
    sender_module, sender_state = sender_stub
    sender_state.queue(SendResult(ok=False, blocked=True, error="403 Forbidden"))

    booking, *_ = await _seed_eligible_reminder_candidate(
        make_active_trainer=make_active_trainer,
        make_linked_client=make_linked_client,
        make_unlinked_client=None,
        make_future_slot=make_future_slot,
        make_active_pt_package=make_active_pt_package,
        make_confirmed_booking=make_confirmed_booking,
        actor=seeded_owner,
    )

    with structlog.testing.capture_logs() as captured:
        count = await bookings_service._send_booking_reminders(
            notifications_session_factory,
            bot=fake_bot,  # type: ignore[arg-type]
            sender=sender_module,
            notifications_module=bookings_notifications,
        )

    assert count == 0
    assert len(sender_state.calls) == 1, (
        "the failed send is still recorded as a call — only the post-send "
        "INSERT is skipped"
    )

    notif_rows = (
        await db_session.execute(
            select(BookingNotification).where(
                BookingNotification.booking_id == booking.id
            )
        )
    ).scalars().all()
    assert len(notif_rows) == 0

    failed_events = [
        e for e in captured
        if e.get("event") == "booking_reminder_send_failed"
        and e.get("reason") == "bot_blocked"
    ]
    assert len(failed_events) == 1
    assert failed_events[0].get("booking_id") == str(booking.id)


async def test_reminders_cron_skips_unlinked_client(
    db_session: AsyncSession,
    notifications_session_factory: Any,
    fake_bot: object,
    sender_stub: Any,
    seeded_owner: User,
    make_active_trainer: Callable[..., Awaitable[Trainer]],
    make_unlinked_client: Callable[..., Awaitable[Client]],
    make_future_slot: Callable[..., Awaitable[TrainerAvailabilitySlot]],
    make_active_pt_package: Callable[..., Awaitable[PtPackage]],
    make_confirmed_booking: Callable[..., Awaitable[Booking]],
) -> None:
    """Client with telegram_user_id IS NULL → SQL pre-filter excludes; no send."""
    sender_module, sender_state = sender_stub

    booking, *_ = await _seed_eligible_reminder_candidate(
        make_active_trainer=make_active_trainer,
        make_linked_client=None,
        make_unlinked_client=make_unlinked_client,
        make_future_slot=make_future_slot,
        make_active_pt_package=make_active_pt_package,
        make_confirmed_booking=make_confirmed_booking,
        actor=seeded_owner,
        telegram_user_id=None,
    )

    count = await bookings_service._send_booking_reminders(
        notifications_session_factory,
        bot=fake_bot,  # type: ignore[arg-type]
        sender=sender_module,
        notifications_module=bookings_notifications,
    )

    assert count == 0
    assert len(sender_state.calls) == 0, (
        "the c.telegram_user_id IS NOT NULL SQL filter excludes the row "
        "BEFORE any sender call is attempted"
    )

    notif_rows = (
        await db_session.execute(
            select(BookingNotification).where(
                BookingNotification.booking_id == booking.id
            )
        )
    ).scalars().all()
    assert len(notif_rows) == 0


async def test_reminders_cron_collision_rollback_on_pre_inserted_row(
    db_session: AsyncSession,
    notifications_session_factory: Any,
    fake_bot: object,
    sender_stub: Any,
    seeded_owner: User,
    make_active_trainer: Callable[..., Awaitable[Trainer]],
    make_linked_client: Callable[..., Awaitable[Client]],
    make_future_slot: Callable[..., Awaitable[TrainerAvailabilitySlot]],
    make_active_pt_package: Callable[..., Awaitable[PtPackage]],
    make_confirmed_booking: Callable[..., Awaitable[Booking]],
) -> None:
    """IntegrityError on uq_booking_notifications_booking_kind → rollback + INFO-log.

    Exercises the ``except IntegrityError`` branch in
    ``_send_booking_reminders`` without spinning a parallel real Postgres
    transaction (the SAVEPOINT-mode sessionmaker keeps everything inside
    the outer test transaction). The collision is injected by wrapping
    the sender stub: between the (sync) renderer call and the post-send
    write_session.add() + commit(), the wrapped sender performs the
    pre-INSERT through the same savepoint factory the helper uses. By
    the time control returns to the helper's ``write_session.add(
    BookingNotification(...))`` + ``commit()``, the UNIQUE collision
    fires.

    Sender (not renderer) is the injection seam because the helper
    awaits the sender — the renderer is a sync call. The pre-INSERT
    needs an ``async with session_factory() as parallel: await
    parallel.commit()`` round-trip, which requires an async context.

    D-39-08 step ordering: render → send → write_session.add → commit.
    The send fires (one recorded sender call) BEFORE the per-send INSERT
    is attempted, so the collision happens at commit time, not before.
    """
    sender_module, sender_state = sender_stub

    booking, *_ = await _seed_eligible_reminder_candidate(
        make_active_trainer=make_active_trainer,
        make_linked_client=make_linked_client,
        make_unlinked_client=None,
        make_future_slot=make_future_slot,
        make_active_pt_package=make_active_pt_package,
        make_confirmed_booking=make_confirmed_booking,
        actor=seeded_owner,
    )
    # Capture booking.id eagerly — the helper's per-send write sessions
    # opening + closing causes SQLAlchemy to expire the test's ORM
    # instance attributes; later reads would trigger async refresh
    # outside any greenlet context and raise MissingGreenlet.
    booking_id = booking.id

    pre_insert_done = {"fired": False}
    real_sender = sender_module.send_text_dm

    async def _pre_insert_then_send(
        bot: object, chat_id: int, text: str
    ) -> SendResult:
        # Insert the colliding row through the SAME savepoint factory the
        # helper uses, so the INSERT lives inside the outer test
        # transaction (no real cross-process race needed for the
        # IntegrityError branch coverage). Fire ONCE so multi-row
        # scenarios don't accidentally lock every candidate.
        if not pre_insert_done["fired"]:
            pre_insert_done["fired"] = True
            async with notifications_session_factory() as parallel_session:
                parallel_session.add(
                    BookingNotification(booking_id=booking_id, kind="reminder_24h")
                )
                await parallel_session.commit()
        return await real_sender(bot, chat_id, text)

    sender_shim = SimpleNamespace(send_text_dm=_pre_insert_then_send)

    with structlog.testing.capture_logs() as captured:
        count = await bookings_service._send_booking_reminders(
            notifications_session_factory,
            bot=fake_bot,  # type: ignore[arg-type]
            sender=sender_shim,
            notifications_module=bookings_notifications,
        )

    # The only candidate collided → 0 successful sends (the IntegrityError
    # branch fired). D-39-08 step ordering: the send went out BEFORE the
    # per-send INSERT was attempted, so sender_state.calls has 1 entry.
    assert count == 0
    assert len(sender_state.calls) == 1

    # Exactly ONE collision INFO event for this booking.
    collisions = [
        e for e in captured
        if e.get("event") == "booking_reminder_idempotency_collision"
        and e.get("booking_id") == str(booking_id)
    ]
    assert len(collisions) == 1

    # Exactly one row survives (the pre-inserted one; the helper's
    # write_session was rolled back).
    notif_rows = (
        await db_session.execute(
            select(BookingNotification).where(
                BookingNotification.booking_id == booking_id
            )
        )
    ).scalars().all()
    assert len(notif_rows) == 1
