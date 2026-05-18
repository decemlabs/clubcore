"""Phase 39 NOTIFY-03 integration tests — create_booking confirmation DM.

Asserts that ``create_booking`` dispatches ``BOOKING_CONFIRMED_DM`` exactly
once after commit (fire-and-forget per D-39-09 / D-39-10).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.telegram.sender import SendResult
from app.modules.auth.models import User
from app.modules.bookings import service as bookings_service
from app.modules.bookings.models import Booking
from app.modules.bookings.notifications import BOOKING_CONFIRMED_DM
from app.modules.bookings.schemas import BookingCreateRequest, BookingStatus


@pytest.fixture(autouse=True)
def _reset_bookings_service_logger_cache() -> Iterator[None]:
    """Invalidate the module-level structlog BoundLoggerLazyProxy cache.

    Mirrors the pt_packages worker test fixture (see
    ``tests/integration/pt_packages/test_expire_pt_packages_cron.py``) —
    without this reset, ``structlog.testing.capture_logs()`` misses
    ``_log.info`` / ``_log.warning`` lines from
    ``app.modules.bookings.service`` because the lazy proxy caches its
    first-call processor list at import time (resolved BEFORE the
    capture context patched the global structlog config).
    """
    if "bind" in bookings_service._log.__dict__:
        del bookings_service._log.__dict__["bind"]
    yield


@pytest.mark.asyncio
async def test_create_booking_sends_confirmed_dm(
    db_session: AsyncSession,
    seeded_owner: User,
    fake_bot: object,
    sender_stub: Any,
    make_linked_client: Any,
    make_active_trainer: Any,
    make_future_slot: Any,
    make_active_pt_package: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Happy path — confirmed DM is sent exactly once with the rendered locked text.

    Asserts:
      - sender stub captured exactly one call,
      - chat_id == client.telegram_user_id,
      - text matches `BOOKING_CONFIRMED_DM.format(...)` with the seeded
        client_name / trainer_name / MSK-formatted slot_start,
      - the booking row exists in the DB with status='confirmed' (HTTP
        path was unaffected by the DM dispatch).
    """
    sender_module, sender_state = sender_stub

    trainer = await make_active_trainer(full_name="Пётр Сидоров")
    slot = await make_future_slot(trainer=trainer)
    client = await make_linked_client(telegram_user_id=100001, first_name="Иван")
    pkg = await make_active_pt_package(
        client=client, trainer=trainer, sessions_remaining=5
    )

    monkeypatch.setattr(
        "app.modules.bookings.service.telegram_sender", sender_module
    )
    monkeypatch.setattr(
        "app.modules.bookings.service.build_bot",
        lambda *, token: fake_bot,
    )

    response = await bookings_service.create_booking(
        db_session,
        seeded_owner,
        BookingCreateRequest(
            slot_id=slot.id,
            client_id=client.id,
            pt_package_id=pkg.id,
        ),
    )

    assert response.status == BookingStatus.CONFIRMED

    # DB persistence — booking row exists with status='confirmed'.
    booking_row = await db_session.scalar(
        select(Booking).where(Booking.id == response.id)
    )
    assert booking_row is not None
    assert booking_row.status == "confirmed"

    # Exactly one DM call recorded; chat_id matches the seeded client.
    assert len(sender_state.calls) == 1
    call = sender_state.calls[0]
    assert call.chat_id == 100001
    assert call.bot is fake_bot

    # Rendered text matches the locked template substitution per D-39-11.
    expected_text = BOOKING_CONFIRMED_DM.format(
        client_name="Иван",
        trainer_name="Пётр Сидоров",
        slot_start_msk=slot.start_time.astimezone(
            bookings_service.MOSCOW_TZ
        ).strftime("%d.%m.%Y %H:%M"),
    )
    assert call.text == expected_text


@pytest.mark.asyncio
async def test_create_booking_skips_dm_for_unlinked_client(
    db_session: AsyncSession,
    seeded_owner: User,
    fake_bot: object,
    sender_stub: Any,
    make_unlinked_client: Any,
    make_active_trainer: Any,
    make_future_slot: Any,
    make_active_pt_package: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unlinked client (telegram_user_id IS NULL) — no send call; INFO-log emitted.

    The booking still persists (DM-skip never affects the HTTP path).
    """
    sender_module, sender_state = sender_stub

    trainer = await make_active_trainer()
    slot = await make_future_slot(trainer=trainer)
    client = await make_unlinked_client()
    pkg = await make_active_pt_package(client=client, trainer=trainer)

    monkeypatch.setattr(
        "app.modules.bookings.service.telegram_sender", sender_module
    )
    monkeypatch.setattr(
        "app.modules.bookings.service.build_bot",
        lambda *, token: fake_bot,
    )

    with structlog.testing.capture_logs() as cap:
        response = await bookings_service.create_booking(
            db_session,
            seeded_owner,
            BookingCreateRequest(
                slot_id=slot.id,
                client_id=client.id,
                pt_package_id=pkg.id,
            ),
        )

    assert response.status == BookingStatus.CONFIRMED
    assert len(sender_state.calls) == 0
    assert any(
        e.get("event") == "booking_dm_skipped_unlinked" for e in cap
    ), f"expected booking_dm_skipped_unlinked INFO-log; got {[e.get('event') for e in cap]}"

    # Booking persisted regardless of the DM-skip.
    booking_row = await db_session.scalar(
        select(Booking).where(Booking.id == response.id)
    )
    assert booking_row is not None
    assert booking_row.status == "confirmed"


@pytest.mark.asyncio
async def test_create_booking_swallows_send_failure(
    db_session: AsyncSession,
    seeded_owner: User,
    fake_bot: object,
    sender_stub: Any,
    make_linked_client: Any,
    make_active_trainer: Any,
    make_future_slot: Any,
    make_active_pt_package: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SendResult.ok=False -> WARNING-log; the booking still persists (D-39-09).

    Asserts the fire-and-forget contract: a DM-send failure NEVER rolls
    back the booking row or raises through the HTTP path.
    """
    sender_module, sender_state = sender_stub
    sender_state.queue(
        SendResult(ok=False, blocked=True, error="403 Forbidden — bot blocked")
    )

    trainer = await make_active_trainer()
    slot = await make_future_slot(trainer=trainer)
    client = await make_linked_client(telegram_user_id=100002)
    pkg = await make_active_pt_package(client=client, trainer=trainer)

    monkeypatch.setattr(
        "app.modules.bookings.service.telegram_sender", sender_module
    )
    monkeypatch.setattr(
        "app.modules.bookings.service.build_bot",
        lambda *, token: fake_bot,
    )

    with structlog.testing.capture_logs() as cap:
        response = await bookings_service.create_booking(
            db_session,
            seeded_owner,
            BookingCreateRequest(
                slot_id=slot.id,
                client_id=client.id,
                pt_package_id=pkg.id,
            ),
        )
        # Snapshot cap content before exiting the context — see note
        # below about the global ROOT_LOGGER swap.
        cap_snapshot = list(cap)

    # Booking row durable despite the DM-send failure.
    assert response.status == BookingStatus.CONFIRMED
    booking_row = await db_session.scalar(
        select(Booking).where(Booking.id == response.id)
    )
    assert booking_row is not None
    assert booking_row.status == "confirmed"

    # WARNING-log emitted with the bot_blocked reason classifier.
    assert len(sender_state.calls) == 1
    matching = [
        e
        for e in cap_snapshot
        if e.get("event") == "booking_dm_send_failed"
        and e.get("reason") == "bot_blocked"
    ]
    assert matching, (
        f"expected booking_dm_send_failed WARNING-log with reason='bot_blocked'; "
        f"got {[(e.get('event'), e.get('reason')) for e in cap_snapshot]}"
    )
