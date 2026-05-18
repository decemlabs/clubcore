"""Phase 39 CRON-01 integration tests.

Covers ``_mark_no_show_bookings`` service helper + ``mark_no_show_bookings``
ARQ worker per D-39-06 (single-session), D-39-07 (SELECT FOR UPDATE OF b),
D-39-14 (BookingNoShowPayload locked shape).

Direct calls to the service helper against the SAVEPOINT-rolled
``db_session``. Mirrors ``tests/integration/pt_packages/test_expire_pt_packages_cron.py``
shape but exercises the new no-show classification surface.

Coverage:
  1. Overdue confirmed booking flips to no_show + emits ``booking_no_show``
     audit; future confirmed booking + already-completed booking untouched.
     Audit payload keys EXACTLY match BookingNoShowPayload (extra='forbid' /
     INFRA-25): {booking_id, slot_id, client_id, no_show_at}.
  2. Idempotent re-run: 2nd helper call returns 0 — WHERE status='confirmed'
     guard skips already-flipped rows; only one audit_log row exists.
  3. Worker e2e: mark_no_show_bookings(ctx) invokes the helper, commits,
     emits 'mark_no_show_bookings_complete' structlog summary AFTER commit.

Out of scope (D-39-18): real-Postgres asyncio.gather race test between the
no-show cron and pt_sessions.record_pt_session — that lands in Phase 40
VER-07 milestone verification.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest_asyncio
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.auth.models import User
from app.modules.bookings import service as bookings_service
from app.modules.bookings.models import Booking
from app.modules.clients.models import Client
from app.modules.pt_packages.models import PtPackage
from app.modules.schedule.models import TrainerAvailabilitySlot
from app.modules.trainers.models import Trainer
from app.workers.scheduled.mark_no_show_bookings import mark_no_show_bookings


@pytest_asyncio.fixture(autouse=True)
async def _reset_no_show_worker_logger_cache() -> AsyncIterator[None]:
    """Invalidate the module-level structlog cache for mark_no_show_bookings.

    Mirrors ``_reset_pt_packages_worker_logger_cache`` in
    ``tests/integration/pt_packages/test_expire_pt_packages_cron.py:36-49``
    — without this reset, ``structlog.testing.capture_logs()`` misses the
    worker's INFO line because the BoundLoggerLazyProxy caches its
    first-call processor list at module import time.

    Also resets the bookings.service module-level ``_log`` so any audit /
    warning lines emitted from ``_mark_no_show_bookings`` are observable
    via ``capture_logs()`` (matches the pattern in
    ``test_create_sends_dm.py`` autouse fixture).
    """
    from app.workers.scheduled import mark_no_show_bookings as worker_mod

    if "bind" in worker_mod._log.__dict__:
        del worker_mod._log.__dict__["bind"]
    if "bind" in bookings_service._log.__dict__:
        del bookings_service._log.__dict__["bind"]
    yield


async def _seed_overdue_confirmed_booking(
    db_session: AsyncSession,
    *,
    make_active_trainer: Callable[..., Awaitable[Trainer]],
    make_unlinked_client: Callable[..., Awaitable[Client]],
    make_future_slot: Callable[..., Awaitable[TrainerAvailabilitySlot]],
    make_active_pt_package: Callable[..., Awaitable[PtPackage]],
    make_confirmed_booking: Callable[..., Awaitable[Booking]],
    actor: User,
    hours_overdue: int = 2,
) -> tuple[Booking, TrainerAvailabilitySlot, Client]:
    """Helper: seed one confirmed booking whose slot ended ``hours_overdue`` ago.

    Uses the negative-offset contract on ``make_future_slot`` (extended by
    plan 39-03 Task 4) — ORM-direct insert bypasses the Phase 38 future-only
    publish-time guard. Returns (booking, slot, client) for assertions.
    """
    trainer = await make_active_trainer()
    client = await make_unlinked_client()
    pt_package = await make_active_pt_package(client=client, trainer=trainer)
    slot = await make_future_slot(
        trainer=trainer,
        start_offset=timedelta(hours=-hours_overdue) - timedelta(hours=1),
        duration=timedelta(hours=1),
    )
    booking = await make_confirmed_booking(
        slot=slot,
        client=client,
        pt_package=pt_package,
        actor_user_id=actor.id,
    )
    return booking, slot, client


async def test_no_show_cron_marks_overdue_and_emits_audit(
    db_session: AsyncSession,
    seeded_owner: User,
    make_active_trainer: Callable[..., Awaitable[Trainer]],
    make_unlinked_client: Callable[..., Awaitable[Client]],
    make_future_slot: Callable[..., Awaitable[TrainerAvailabilitySlot]],
    make_active_pt_package: Callable[..., Awaitable[PtPackage]],
    make_confirmed_booking: Callable[..., Awaitable[Booking]],
) -> None:
    """3-row fixture: overdue/future/completed — only overdue flips to no_show."""
    # 1) Overdue confirmed booking (slot ended 2h ago) — SHOULD flip.
    overdue_booking, overdue_slot, overdue_client = await _seed_overdue_confirmed_booking(
        db_session,
        make_active_trainer=make_active_trainer,
        make_unlinked_client=make_unlinked_client,
        make_future_slot=make_future_slot,
        make_active_pt_package=make_active_pt_package,
        make_confirmed_booking=make_confirmed_booking,
        actor=seeded_owner,
        hours_overdue=2,
    )

    # 2) Future confirmed booking (slot starts 24h from now) — should NOT flip.
    future_trainer = await make_active_trainer(full_name="Future Trainer")
    future_client = await make_unlinked_client(first_name="Future")
    future_pkg = await make_active_pt_package(client=future_client, trainer=future_trainer)
    future_slot = await make_future_slot(trainer=future_trainer)  # default +25h
    future_booking = await make_confirmed_booking(
        slot=future_slot,
        client=future_client,
        pt_package=future_pkg,
        actor_user_id=seeded_owner.id,
    )

    # 3) Already-completed booking with overdue slot — should NOT flip
    # (WHERE b.status='confirmed' filter excludes it).
    done_trainer = await make_active_trainer(full_name="Done Trainer")
    done_client = await make_unlinked_client(first_name="Done")
    done_pkg = await make_active_pt_package(client=done_client, trainer=done_trainer)
    done_slot = await make_future_slot(
        trainer=done_trainer,
        start_offset=timedelta(hours=-3),
        duration=timedelta(hours=1),
    )
    done_booking = await make_confirmed_booking(
        slot=done_slot,
        client=done_client,
        pt_package=done_pkg,
        actor_user_id=seeded_owner.id,
    )
    done_booking.status = "completed"
    done_booking.completed_at = datetime.now(tz=UTC)
    await db_session.commit()

    # Sanity — overdue slot is in the past, future slot is in the future.
    now_utc = datetime.now(tz=UTC)
    assert overdue_slot.end_time < now_utc
    assert future_slot.start_time > now_utc

    # Fire the helper.
    count = await bookings_service._mark_no_show_bookings(db_session)
    await db_session.commit()
    assert count == 1, f"expected 1 flipped row, got {count}"

    # Refresh + assert flipped state.
    await db_session.refresh(overdue_booking)
    await db_session.refresh(future_booking)
    await db_session.refresh(done_booking)
    assert overdue_booking.status == "no_show", overdue_booking.status
    assert overdue_booking.no_show_at is not None
    assert future_booking.status == "confirmed", future_booking.status
    assert future_booking.no_show_at is None
    assert done_booking.status == "completed", done_booking.status
    assert done_booking.no_show_at is None

    # Audit assertion — exactly one booking_no_show row for the overdue booking
    # with the locked payload shape.
    audit_rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "booking_no_show",
            )
        )
    ).all()
    assert len(audit_rows) == 1, f"expected 1 audit row, got {len(audit_rows)}"
    row = audit_rows[0]
    assert row.resource_type == "booking"
    assert row.resource_id == overdue_booking.id
    assert row.actor_user_id is None  # system actor — audit_log.actor_user_id nullable
    payload = row.payload
    # INFRA-25 / extra='forbid' lock — payload keys EXACTLY match
    # BookingNoShowPayload (no extras, no missing).
    assert set(payload.keys()) == {
        "booking_id",
        "slot_id",
        "client_id",
        "no_show_at",
    }, payload.keys()
    assert payload["booking_id"] == str(overdue_booking.id)
    assert payload["slot_id"] == str(overdue_slot.id)
    assert payload["client_id"] == str(overdue_client.id)
    assert isinstance(payload["no_show_at"], str)
    # no_show_at is an ISO-8601 string in Europe/Moscow TZ — parseable.
    parsed = datetime.fromisoformat(payload["no_show_at"])
    assert parsed.utcoffset() is not None, "no_show_at must carry TZ offset"


async def test_no_show_cron_idempotent_second_run_zero(
    db_session: AsyncSession,
    seeded_owner: User,
    make_active_trainer: Callable[..., Awaitable[Trainer]],
    make_unlinked_client: Callable[..., Awaitable[Client]],
    make_future_slot: Callable[..., Awaitable[TrainerAvailabilitySlot]],
    make_active_pt_package: Callable[..., Awaitable[PtPackage]],
    make_confirmed_booking: Callable[..., Awaitable[Booking]],
) -> None:
    """2nd call returns 0 — WHERE status='confirmed' guard makes re-run a no-op."""
    await _seed_overdue_confirmed_booking(
        db_session,
        make_active_trainer=make_active_trainer,
        make_unlinked_client=make_unlinked_client,
        make_future_slot=make_future_slot,
        make_active_pt_package=make_active_pt_package,
        make_confirmed_booking=make_confirmed_booking,
        actor=seeded_owner,
        hours_overdue=2,
    )

    n1 = await bookings_service._mark_no_show_bookings(db_session)
    await db_session.commit()
    n2 = await bookings_service._mark_no_show_bookings(db_session)
    await db_session.commit()

    assert n1 == 1
    assert n2 == 0

    # Only one audit_log row across both runs — re-run was a no-op (the
    # candidate SELECT pre-filter `b.status='confirmed'` excludes the now-
    # no_show row, so the per-row audit loop is never entered on the 2nd
    # tick).
    audit_rows = (
        await db_session.scalars(
            select(AuditLog).where(AuditLog.action == "booking_no_show")
        )
    ).all()
    assert len(audit_rows) == 1, len(audit_rows)


async def test_no_show_cron_worker_e2e_via_sessionmaker_emits_summary_log(
    db_session: AsyncSession,
    seeded_owner: User,
    make_active_trainer: Callable[..., Awaitable[Trainer]],
    make_unlinked_client: Callable[..., Awaitable[Client]],
    make_future_slot: Callable[..., Awaitable[TrainerAvailabilitySlot]],
    make_active_pt_package: Callable[..., Awaitable[PtPackage]],
    make_confirmed_booking: Callable[..., Awaitable[Booking]],
) -> None:
    """Worker invocation emits 'mark_no_show_bookings_complete' AFTER commit."""
    overdue_booking, _, _ = await _seed_overdue_confirmed_booking(
        db_session,
        make_active_trainer=make_active_trainer,
        make_unlinked_client=make_unlinked_client,
        make_future_slot=make_future_slot,
        make_active_pt_package=make_active_pt_package,
        make_confirmed_booking=make_confirmed_booking,
        actor=seeded_owner,
        hours_overdue=2,
    )

    # ctx with a sessionmaker that yields the SAVEPOINT-rolled db_session
    # (mirrors test_expire_pt_packages_cron.py:184-193 verbatim — never
    # closes the session because the outer db_session fixture owns teardown).
    class _SessionContext:
        async def __aenter__(self) -> AsyncSession:
            return db_session

        async def __aexit__(self, *args: Any) -> None:
            return None

    class _Sessionmaker:
        def __call__(self) -> _SessionContext:
            return _SessionContext()

    ctx: dict[str, Any] = {
        "sessionmaker": _Sessionmaker(),
        "job_id": "test-no-show-cron-0001",
        "function_name": "mark_no_show_bookings",
    }

    with structlog.testing.capture_logs() as captured:
        count = await mark_no_show_bookings(ctx)

    assert count == 1
    completion = [
        e for e in captured if e.get("event") == "mark_no_show_bookings_complete"
    ]
    assert len(completion) == 1, (
        f"expected exactly 1 summary log line, got {len(completion)}: "
        f"{[e.get('event') for e in captured]}"
    )
    assert completion[0].get("count") == 1

    await db_session.refresh(overdue_booking)
    assert overdue_booking.status == "no_show"
