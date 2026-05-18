"""Phase 39 NOTIFY-04 integration tests — cancel-flow DM dispatch.

Asserts that ``cancel_booking`` and the ``schedule.cancel_slot``
booked->cancelled cascade dispatch the correct booking-cancellation DM
template per the D-39-05 ``actor.role`` discriminator (owner vs reception),
that unlinked clients are silently skipped, and that DM-send failures
NEVER roll back the cancel (fire-and-forget per D-39-09 / D-39-10).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.telegram.sender import SendResult
from app.modules.auth.models import User
from app.modules.bookings import service as bookings_service
from app.modules.bookings.models import Booking
from app.modules.bookings.notifications import (
    BOOKING_CANCELLED_BY_CLIENT_DM,
    BOOKING_CANCELLED_BY_OWNER_DM,
)
from app.modules.bookings.schemas import BookingCancelRequest, BookingStatus
from app.modules.schedule import service as schedule_service
from app.modules.schedule.schemas import SlotCancelRequest


@pytest.fixture(autouse=True)
def _reset_module_logger_caches() -> Iterator[None]:
    """Invalidate the module-level structlog BoundLoggerLazyProxy caches.

    Mirrors ``tests/integration/pt_packages/test_expire_pt_packages_cron.py``
    — without this reset, ``structlog.testing.capture_logs()`` misses
    ``_log.info`` / ``_log.warning`` lines from
    ``app.modules.bookings.service`` and ``app.modules.schedule.service``
    because the lazy proxies cache their first-call processor list at
    import time (resolved BEFORE the capture context patched the global
    structlog config). Both module loggers must be reset because the
    slot-cascade test transits through ``schedule.service.cancel_slot``
    which then function-locally re-enters ``bookings.service``.
    """
    for mod in (bookings_service, schedule_service):
        if "bind" in mod._log.__dict__:
            del mod._log.__dict__["bind"]
    yield


def _render_owner_cancel(*, client_name: str, trainer_name: str, slot) -> str:  # type: ignore[no-untyped-def]
    """Render the locked owner-initiated cancellation template for asserts."""
    return BOOKING_CANCELLED_BY_OWNER_DM.format(
        client_name=client_name,
        trainer_name=trainer_name,
        slot_start_msk=slot.start_time.astimezone(
            bookings_service.MOSCOW_TZ
        ).strftime("%d.%m.%Y %H:%M"),
    )


def _render_client_cancel(*, client_name: str, trainer_name: str, slot) -> str:  # type: ignore[no-untyped-def]
    """Render the locked client-initiated cancellation template for asserts."""
    return BOOKING_CANCELLED_BY_CLIENT_DM.format(
        client_name=client_name,
        trainer_name=trainer_name,
        slot_start_msk=slot.start_time.astimezone(
            bookings_service.MOSCOW_TZ
        ).strftime("%d.%m.%Y %H:%M"),
    )


@pytest.mark.asyncio
async def test_cancel_booking_by_owner_sends_owner_dm(
    db_session: AsyncSession,
    seeded_owner: User,
    fake_bot: object,
    sender_stub: Any,
    make_linked_client: Any,
    make_active_trainer: Any,
    make_future_slot: Any,
    make_active_pt_package: Any,
    make_confirmed_booking: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Owner cancels a confirmed booking -> exactly 1 BOOKING_CANCELLED_BY_OWNER_DM.

    Uses ``make_confirmed_booking`` direct-insert factory so the test
    starts from a confirmed/booked state WITHOUT triggering a
    confirmation-DM dispatch first (which would pollute sender_state).
    """
    sender_module, sender_state = sender_stub

    trainer = await make_active_trainer(full_name="Пётр Сидоров")
    slot = await make_future_slot(trainer=trainer)
    client = await make_linked_client(telegram_user_id=100101, first_name="Иван")
    pkg = await make_active_pt_package(client=client, trainer=trainer)
    booking = await make_confirmed_booking(
        slot=slot, client=client, pt_package=pkg, actor_user_id=seeded_owner.id
    )

    monkeypatch.setattr(
        "app.modules.bookings.service.telegram_sender", sender_module
    )
    monkeypatch.setattr(
        "app.modules.bookings.service.build_bot",
        lambda *, token: fake_bot,
    )

    response = await bookings_service.cancel_booking(
        db_session,
        seeded_owner,
        booking.id,
        BookingCancelRequest(reason="зал закрыт по техническим причинам"),
    )

    assert response.status == BookingStatus.CANCELLED

    # Exactly one DM call recorded — owner template, correct chat_id.
    assert len(sender_state.calls) == 1
    call = sender_state.calls[0]
    assert call.chat_id == 100101
    assert call.bot is fake_bot
    assert call.text == _render_owner_cancel(
        client_name="Иван", trainer_name="Пётр Сидоров", slot=slot
    )
    # Distinguishing assert — owner copy must NOT mention "по вашей просьбе"
    # (that wording is exclusive to the client-initiated template).
    assert "по вашей просьбе" not in call.text


@pytest.mark.asyncio
async def test_cancel_booking_by_reception_sends_client_dm(
    db_session: AsyncSession,
    seeded_owner: User,
    seeded_reception: User,
    fake_bot: object,
    sender_stub: Any,
    make_linked_client: Any,
    make_active_trainer: Any,
    make_future_slot: Any,
    make_active_pt_package: Any,
    make_confirmed_booking: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reception cancels a confirmed booking -> 1 BOOKING_CANCELLED_BY_CLIENT_DM.

    Slot start is >24h in the future so the reception 24h-window check
    (D-38-16) does NOT block the cancel. Confirms the actor-role
    discriminator is independent of the window check.
    """
    sender_module, sender_state = sender_stub

    trainer = await make_active_trainer(full_name="Анна Тренерова")
    # Default make_future_slot offset is 25h — comfortably outside the
    # 24h reception window per D-38-16.
    slot = await make_future_slot(trainer=trainer, start_offset=timedelta(hours=48))
    client = await make_linked_client(telegram_user_id=100201, first_name="Мария")
    pkg = await make_active_pt_package(client=client, trainer=trainer)
    booking = await make_confirmed_booking(
        slot=slot, client=client, pt_package=pkg, actor_user_id=seeded_owner.id
    )

    monkeypatch.setattr(
        "app.modules.bookings.service.telegram_sender", sender_module
    )
    monkeypatch.setattr(
        "app.modules.bookings.service.build_bot",
        lambda *, token: fake_bot,
    )

    response = await bookings_service.cancel_booking(
        db_session,
        seeded_reception,
        booking.id,
        BookingCancelRequest(reason="клиент попросил отменить"),
    )

    assert response.status == BookingStatus.CANCELLED
    assert len(sender_state.calls) == 1
    call = sender_state.calls[0]
    assert call.chat_id == 100201
    assert call.text == _render_client_cancel(
        client_name="Мария", trainer_name="Анна Тренерова", slot=slot
    )
    # Distinguishing assert — client copy must mention "по вашей просьбе"
    # (the phrase that's exclusive to the reception-initiated template).
    assert "по вашей просьбе" in call.text


@pytest.mark.asyncio
async def test_cancel_booking_skips_dm_for_unlinked_client(
    db_session: AsyncSession,
    seeded_owner: User,
    fake_bot: object,
    sender_stub: Any,
    make_unlinked_client: Any,
    make_active_trainer: Any,
    make_future_slot: Any,
    make_active_pt_package: Any,
    make_confirmed_booking: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Owner cancels for an unlinked client (telegram_user_id IS NULL).

    Asserts: 0 sender calls, INFO-log ``booking_dm_skipped_unlinked``
    emitted, booking still flips to ``cancelled``.
    """
    sender_module, sender_state = sender_stub

    trainer = await make_active_trainer()
    slot = await make_future_slot(trainer=trainer)
    client = await make_unlinked_client()
    pkg = await make_active_pt_package(client=client, trainer=trainer)
    booking = await make_confirmed_booking(
        slot=slot, client=client, pt_package=pkg, actor_user_id=seeded_owner.id
    )

    monkeypatch.setattr(
        "app.modules.bookings.service.telegram_sender", sender_module
    )
    monkeypatch.setattr(
        "app.modules.bookings.service.build_bot",
        lambda *, token: fake_bot,
    )

    with structlog.testing.capture_logs() as cap:
        response = await bookings_service.cancel_booking(
            db_session,
            seeded_owner,
            booking.id,
            BookingCancelRequest(reason="owner cancel for unlinked"),
        )
        cap_snapshot = list(cap)

    assert response.status == BookingStatus.CANCELLED
    assert len(sender_state.calls) == 0
    assert any(
        e.get("event") == "booking_dm_skipped_unlinked" for e in cap_snapshot
    ), f"expected booking_dm_skipped_unlinked; got {[e.get('event') for e in cap_snapshot]}"

    # Booking row durable; HTTP path unaffected.
    booking_row = await db_session.scalar(
        select(Booking).where(Booking.id == booking.id)
    )
    assert booking_row is not None
    assert booking_row.status == "cancelled"


@pytest.mark.asyncio
async def test_cancel_booking_swallows_send_failure(
    db_session: AsyncSession,
    seeded_owner: User,
    fake_bot: object,
    sender_stub: Any,
    make_linked_client: Any,
    make_active_trainer: Any,
    make_future_slot: Any,
    make_active_pt_package: Any,
    make_confirmed_booking: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SendResult.ok=False -> WARNING-log; cancel still commits (D-39-09).

    Fire-and-forget contract — a DM-send failure on the cancel path NEVER
    rolls back the booking row or raises through the HTTP path.
    """
    sender_module, sender_state = sender_stub
    sender_state.queue(
        SendResult(ok=False, blocked=True, error="403 Forbidden — bot blocked")
    )

    trainer = await make_active_trainer()
    slot = await make_future_slot(trainer=trainer)
    client = await make_linked_client(telegram_user_id=100301)
    pkg = await make_active_pt_package(client=client, trainer=trainer)
    booking = await make_confirmed_booking(
        slot=slot, client=client, pt_package=pkg, actor_user_id=seeded_owner.id
    )

    monkeypatch.setattr(
        "app.modules.bookings.service.telegram_sender", sender_module
    )
    monkeypatch.setattr(
        "app.modules.bookings.service.build_bot",
        lambda *, token: fake_bot,
    )

    with structlog.testing.capture_logs() as cap:
        response = await bookings_service.cancel_booking(
            db_session,
            seeded_owner,
            booking.id,
            BookingCancelRequest(reason="owner cancel; bot blocked"),
        )
        cap_snapshot = list(cap)

    assert response.status == BookingStatus.CANCELLED
    assert len(sender_state.calls) == 1

    # Booking row durable despite the DM-send failure.
    booking_row = await db_session.scalar(
        select(Booking).where(Booking.id == booking.id)
    )
    assert booking_row is not None
    assert booking_row.status == "cancelled"

    # WARNING-log emitted with the bot_blocked reason classifier.
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


@pytest.mark.asyncio
async def test_slot_cancel_cascade_sends_owner_dm_per_booking(
    db_session: AsyncSession,
    seeded_owner: User,
    fake_bot: object,
    sender_stub: Any,
    make_linked_client: Any,
    make_active_trainer: Any,
    make_future_slot: Any,
    make_active_pt_package: Any,
    make_confirmed_booking: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Owner cancels a 'booked' slot -> cascade flips booking AND sends 1 DM.

    Verifies the schedule.cancel_slot booked->cancelled cascade dispatches
    exactly one ``BOOKING_CANCELLED_BY_OWNER_DM`` for the cascaded booking
    via the function-local importlib bridge (PATTERNS.md §5 Option A).
    """
    sender_module, sender_state = sender_stub

    trainer = await make_active_trainer(full_name="Сергей Иванов")
    slot = await make_future_slot(trainer=trainer)
    client = await make_linked_client(telegram_user_id=100401, first_name="Ольга")
    pkg = await make_active_pt_package(client=client, trainer=trainer)
    booking = await make_confirmed_booking(
        slot=slot, client=client, pt_package=pkg, actor_user_id=seeded_owner.id
    )

    # The schedule cascade reaches the bookings DM helper via
    # ``importlib.import_module`` (PATTERNS.md §5 Option A escape hatch
    # to preserve the import-linter ``modules-independent`` contract).
    # That import returns the LIVE ``app.integrations.telegram.sender``
    # module, NOT our SimpleNamespace stub — so patching
    # ``app.modules.bookings.service.telegram_sender`` does not cover the
    # cascade callsite. Patch the real module's ``send_text_dm`` function
    # directly so any code path (direct bookings.service or cascade)
    # routes through our recording stub.
    monkeypatch.setattr(
        "app.integrations.telegram.sender.send_text_dm",
        sender_module.send_text_dm,
    )
    # Both call sites (bookings.service direct + schedule.service cascade)
    # construct a Bot via ``build_bot(token=...)`` — patch both module
    # references so each callsite hands the same fake_bot sentinel into
    # the stub (the stub does not touch the bot beyond recording identity).
    monkeypatch.setattr(
        "app.modules.bookings.service.build_bot",
        lambda *, token: fake_bot,
    )
    monkeypatch.setattr(
        "app.integrations.telegram.bot.build_bot",
        lambda *, token: fake_bot,
    )

    slot_response = await schedule_service.cancel_slot(
        db_session,
        seeded_owner,
        slot.id,
        SlotCancelRequest(cancel_reason="owner cancels booked slot"),
    )

    assert slot_response.status == "cancelled"

    # The cascaded booking flipped to cancelled. The cross-module raw
    # UPDATE in `schedule.cancel_slot` bypasses ORM tracking, so we must
    # `populate_existing=True` to force the identity-map to refresh
    # (otherwise a plain `select(...).where(...)` returns the cached
    # pre-cascade ORM instance with status='confirmed').
    booking_row = await db_session.scalar(
        select(Booking)
        .where(Booking.id == booking.id)
        .execution_options(populate_existing=True)
    )
    assert booking_row is not None
    assert booking_row.status == "cancelled"

    # Exactly one DM call recorded — owner template, correct chat_id.
    assert len(sender_state.calls) == 1
    call = sender_state.calls[0]
    assert call.chat_id == 100401
    assert call.text == _render_owner_cancel(
        client_name="Ольга", trainer_name="Сергей Иванов", slot=slot
    )
    # Distinguishing assert — cascade always uses the OWNER template per
    # D-39-05 (the cascade is owner-initiated by definition).
    assert "по вашей просьбе" not in call.text
