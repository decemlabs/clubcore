"""Phase 80 RESCH-01/02 — bookings.service.reschedule_booking_for_client integration tests.

Covers:
  1. Happy path: reschedule returns 200 (BookingResponse); old booking cancelled,
     new booking confirmed on new slot, old slot restored to active, new slot booked.
  2. Race: pre-book the target new slot → 409 slot_already_booked.
  3. Window: original slot starts in <24h → 409 reschedule_window_expired.
  4. Cross-trainer: new slot belongs to a different trainer → 409 slot_trainer_mismatch.
  5. IDOR: reschedule another client's booking → 404 booking_not_found (anti-oracle).
  6. Audit: exactly one booking_rescheduled row linking old→new ids.
  7. PT-credit: sessions_remaining unchanged before/after reschedule (T-80-11).
  8. DM-sent: send_text_dm called exactly once with the rendered reschedule DM text
     containing the new slot time; NOT merely a row assertion (T-80-14).
  9. Notification row: booking_notifications row kind='rescheduled', channel='telegram'
     inserted as post-send evidence (RESCH-02).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.bookings import service as bookings_service
from app.modules.bookings.constants import CANCEL_WINDOW_HOURS_CLIENT
from app.modules.bookings.models import Booking, BookingNotification
from app.modules.bookings.notifications import render_booking_rescheduled_dm
from app.modules.bookings.schemas import BookingStatus

# ---------------------------------------------------------------------------
# Seed helpers (mirrors test_cancel_booking_for_client.py pattern)
# ---------------------------------------------------------------------------


async def _seed_confirmed_booking(
    db_session: AsyncSession,
    *,
    make_active_trainer: Any,
    make_linked_client: Any,
    make_active_pt_package: Any,
    make_future_slot: Any,
    slot_start_offset: timedelta = timedelta(hours=CANCEL_WINDOW_HOURS_CLIENT + 2),
    trainer: Any = None,
    client: Any = None,
    pt_package: Any = None,
) -> tuple[Any, Any, Any, Any, Any]:
    """Seed a linked client + trainer + active pt_package + future slot + confirmed booking.

    Returns (booking, original_slot, client, pkg, trainer).
    """
    if trainer is None:
        trainer = await make_active_trainer(full_name="Тренер Иванов")
    if client is None:
        client = await make_linked_client(telegram_user_id=880_001, first_name="Клиент")
    if pt_package is None:
        pt_package = await make_active_pt_package(
            client=client, trainer=trainer, sessions_remaining=5
        )
    slot = await make_future_slot(trainer=trainer, start_offset=slot_start_offset)

    # Direct ORM insert — bypasses HTTP/service-layer audit so tests start
    # from confirmed/booked state without triggering confirmation DM dispatch.
    booking = Booking(
        slot_id=slot.id,
        client_id=client.id,
        pt_package_id=pt_package.id,
        status="confirmed",
    )
    db_session.add(booking)
    slot.status = "booked"
    await db_session.commit()
    await db_session.refresh(booking)
    await db_session.refresh(slot)
    return booking, slot, client, pt_package, trainer


# ---------------------------------------------------------------------------
# 1. Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reschedule_booking_happy_path(
    db_session: AsyncSession,
    make_active_trainer: Any,
    make_linked_client: Any,
    make_active_pt_package: Any,
    make_future_slot: Any,
    fake_bot: object,
    sender_stub: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RESCH-01 happy path: old booking cancelled + new booking confirmed atomically."""
    sender_module, _sender_state = sender_stub
    monkeypatch.setattr("app.modules.bookings.service.telegram_sender", sender_module)
    monkeypatch.setattr("app.modules.bookings.service.build_bot", lambda *, token: fake_bot)

    trainer = await make_active_trainer(full_name="Тренер Смирнов")
    client = await make_linked_client(telegram_user_id=880_101, first_name="Аня")
    pkg = await make_active_pt_package(client=client, trainer=trainer, sessions_remaining=5)

    booking, old_slot, _, _, _ = await _seed_confirmed_booking(
        db_session,
        make_active_trainer=make_active_trainer,
        make_linked_client=make_linked_client,
        make_active_pt_package=make_active_pt_package,
        make_future_slot=make_future_slot,
        trainer=trainer,
        client=client,
        pt_package=pkg,
    )
    new_slot = await make_future_slot(trainer=trainer, start_offset=timedelta(hours=50))

    response = await bookings_service.reschedule_booking_for_client(
        db_session,
        client_id=client.id,
        booking_id=booking.id,
        new_slot_id=new_slot.id,
    )

    # Response: new booking confirmed on new slot.
    assert response.status == BookingStatus.CONFIRMED
    assert response.slot_id == new_slot.id
    assert response.client_id == client.id

    # Old booking row: status='cancelled', cancel_reason='rescheduled'.
    await db_session.refresh(booking)
    assert booking.status == "cancelled"
    assert booking.cancel_reason == "rescheduled"
    assert booking.cancelled_at is not None

    # Old slot restored to 'active'.
    await db_session.refresh(old_slot, attribute_names=["status"])
    assert old_slot.status == "active"

    # New slot flipped to 'booked'.
    await db_session.refresh(new_slot, attribute_names=["status"])
    assert new_slot.status == "booked"

    # New booking row confirmed and linked to the same pt_package.
    new_booking_row = await db_session.scalar(
        select(Booking).where(Booking.id == response.id)
    )
    assert new_booking_row is not None
    assert new_booking_row.status == "confirmed"
    assert new_booking_row.pt_package_id == booking.pt_package_id  # same linkage


# ---------------------------------------------------------------------------
# 2. Race: target slot pre-booked → 409 slot_already_booked
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reschedule_booking_race_slot_already_booked(
    db_session: AsyncSession,
    make_active_trainer: Any,
    make_linked_client: Any,
    make_active_pt_package: Any,
    make_future_slot: Any,
    fake_bot: object,
    sender_stub: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Race condition: another client pre-books the target slot → 409 slot_already_booked."""
    sender_module, _sender_state = sender_stub
    monkeypatch.setattr("app.modules.bookings.service.telegram_sender", sender_module)
    monkeypatch.setattr("app.modules.bookings.service.build_bot", lambda *, token: fake_bot)

    trainer = await make_active_trainer(full_name="Тренер Кузнецов")
    client = await make_linked_client(telegram_user_id=880_201, first_name="Борис")
    rival_client = await make_linked_client(telegram_user_id=880_202, first_name="Конкурент")
    pkg = await make_active_pt_package(client=client, trainer=trainer, sessions_remaining=5)
    rival_pkg = await make_active_pt_package(
        client=rival_client, trainer=trainer, sessions_remaining=5
    )

    booking, _, _, _, _ = await _seed_confirmed_booking(
        db_session,
        make_active_trainer=make_active_trainer,
        make_linked_client=make_linked_client,
        make_active_pt_package=make_active_pt_package,
        make_future_slot=make_future_slot,
        trainer=trainer,
        client=client,
        pt_package=pkg,
    )
    # Target slot — still 'active' (so the status guard passes) but already has
    # a confirmed booking row (partial UNIQUE uq_bookings_slot_confirmed fires on flush).
    # This simulates the TOCTOU scenario: the slot was 'active' when we loaded it but
    # another booking was inserted concurrently before our flush.
    new_slot = await make_future_slot(trainer=trainer, start_offset=timedelta(hours=55))
    rival_booking = Booking(
        slot_id=new_slot.id,
        client_id=rival_client.id,
        pt_package_id=rival_pkg.id,
        status="confirmed",
    )
    db_session.add(rival_booking)
    # Slot stays 'active' — the IntegrityError (not the status guard) is the
    # load-bearing race guard (mirrors D-38-15 / BOOK-10 discipline).
    await db_session.commit()

    with pytest.raises(bookings_service.SlotAlreadyBookedError) as exc_info:
        await bookings_service.reschedule_booking_for_client(
            db_session,
            client_id=client.id,
            booking_id=booking.id,
            new_slot_id=new_slot.id,
        )
    assert exc_info.value.code == "slot_already_booked"


# ---------------------------------------------------------------------------
# 3. Window guard: original slot starts in <24h → 409 reschedule_window_expired
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reschedule_booking_window_expired(
    db_session: AsyncSession,
    make_active_trainer: Any,
    make_linked_client: Any,
    make_active_pt_package: Any,
    make_future_slot: Any,
) -> None:
    """RESCH-01 window guard: original slot <24h away → 409 reschedule_window_expired."""
    trainer = await make_active_trainer(full_name="Тренер Васин")
    client = await make_linked_client(telegram_user_id=880_301, first_name="Вера")  # noqa: RUF001
    pkg = await make_active_pt_package(client=client, trainer=trainer, sessions_remaining=5)

    # Original slot starting in less than CANCEL_WINDOW_HOURS_CLIENT (e.g. 12h).
    booking, _, _, _, _ = await _seed_confirmed_booking(
        db_session,
        make_active_trainer=make_active_trainer,
        make_linked_client=make_linked_client,
        make_active_pt_package=make_active_pt_package,
        make_future_slot=make_future_slot,
        trainer=trainer,
        client=client,
        pt_package=pkg,
        slot_start_offset=timedelta(hours=CANCEL_WINDOW_HOURS_CLIENT - 12),
    )
    new_slot = await make_future_slot(trainer=trainer, start_offset=timedelta(hours=50))

    with pytest.raises(bookings_service.RescheduleWindowExpiredError) as exc_info:
        await bookings_service.reschedule_booking_for_client(
            db_session,
            client_id=client.id,
            booking_id=booking.id,
            new_slot_id=new_slot.id,
        )
    assert exc_info.value.code == "reschedule_window_expired"


# ---------------------------------------------------------------------------
# 4. Cross-trainer: new slot belongs to a different trainer → 409 slot_trainer_mismatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reschedule_booking_cross_trainer(
    db_session: AsyncSession,
    make_active_trainer: Any,
    make_linked_client: Any,
    make_active_pt_package: Any,
    make_future_slot: Any,
) -> None:
    """RESCH-01 cross-trainer guard: new slot belongs to a different trainer → 409."""
    trainer_a = await make_active_trainer(full_name="Тренер А")  # noqa: RUF001
    trainer_b = await make_active_trainer(full_name="Тренер Б")
    client = await make_linked_client(telegram_user_id=880_401, first_name="Гена")
    pkg = await make_active_pt_package(client=client, trainer=trainer_a, sessions_remaining=5)

    booking, _, _, _, _ = await _seed_confirmed_booking(
        db_session,
        make_active_trainer=make_active_trainer,
        make_linked_client=make_linked_client,
        make_active_pt_package=make_active_pt_package,
        make_future_slot=make_future_slot,
        trainer=trainer_a,
        client=client,
        pt_package=pkg,
    )
    # Target slot belongs to trainer_b — cross-trainer reschedule is forbidden.
    different_trainer_slot = await make_future_slot(
        trainer=trainer_b, start_offset=timedelta(hours=60)
    )

    with pytest.raises(bookings_service.SlotTrainerMismatchError) as exc_info:
        await bookings_service.reschedule_booking_for_client(
            db_session,
            client_id=client.id,
            booking_id=booking.id,
            new_slot_id=different_trainer_slot.id,
        )
    assert exc_info.value.code == "slot_trainer_mismatch"


# ---------------------------------------------------------------------------
# 5. IDOR: another client's booking → 404 booking_not_found (anti-oracle)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reschedule_booking_idor_404(
    db_session: AsyncSession,
    make_active_trainer: Any,
    make_linked_client: Any,
    make_active_pt_package: Any,
    make_future_slot: Any,
) -> None:
    """T-80-05 IDOR anti-oracle: client A reschedules client B's booking → 404."""
    trainer = await make_active_trainer(full_name="Тренер IDOR")
    victim_client = await make_linked_client(telegram_user_id=880_501, first_name="Жертва")
    attacker_client = await make_linked_client(telegram_user_id=880_502, first_name="Атакующий")
    victim_pkg = await make_active_pt_package(
        client=victim_client, trainer=trainer, sessions_remaining=5
    )

    victim_booking, _, _, _, _ = await _seed_confirmed_booking(
        db_session,
        make_active_trainer=make_active_trainer,
        make_linked_client=make_linked_client,
        make_active_pt_package=make_active_pt_package,
        make_future_slot=make_future_slot,
        trainer=trainer,
        client=victim_client,
        pt_package=victim_pkg,
    )
    new_slot = await make_future_slot(trainer=trainer, start_offset=timedelta(hours=70))

    # Attacker tries to reschedule the victim's booking — must get 404 (anti-oracle).
    with pytest.raises(bookings_service.BookingNotFoundError) as exc_info:
        await bookings_service.reschedule_booking_for_client(
            db_session,
            client_id=attacker_client.id,  # attacker, NOT victim
            booking_id=victim_booking.id,
            new_slot_id=new_slot.id,
        )
    assert exc_info.value.code == "booking_not_found"


# ---------------------------------------------------------------------------
# 6. Audit: exactly one booking_rescheduled row linking old→new ids
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reschedule_booking_audit_row(
    db_session: AsyncSession,
    make_active_trainer: Any,
    make_linked_client: Any,
    make_active_pt_package: Any,
    make_future_slot: Any,
    fake_bot: object,
    sender_stub: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RESCH-02: exactly one booking_rescheduled audit row with old→new linkage."""
    sender_module, _ = sender_stub
    monkeypatch.setattr("app.modules.bookings.service.telegram_sender", sender_module)
    monkeypatch.setattr("app.modules.bookings.service.build_bot", lambda *, token: fake_bot)

    trainer = await make_active_trainer(full_name="Тренер Аудит")
    client = await make_linked_client(telegram_user_id=880_601, first_name="Зина")
    pkg = await make_active_pt_package(client=client, trainer=trainer, sessions_remaining=5)

    booking, _, _, _, _ = await _seed_confirmed_booking(
        db_session,
        make_active_trainer=make_active_trainer,
        make_linked_client=make_linked_client,
        make_active_pt_package=make_active_pt_package,
        make_future_slot=make_future_slot,
        trainer=trainer,
        client=client,
        pt_package=pkg,
    )
    old_booking_id = booking.id
    new_slot = await make_future_slot(trainer=trainer, start_offset=timedelta(hours=80))

    response = await bookings_service.reschedule_booking_for_client(
        db_session,
        client_id=client.id,
        booking_id=old_booking_id,
        new_slot_id=new_slot.id,
    )

    # Exactly one booking_rescheduled audit row.
    audit_rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "booking_rescheduled",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_rows) == 1, f"Expected 1 booking_rescheduled audit row, got {len(audit_rows)}"
    payload = audit_rows[0].payload
    assert payload["old_booking_id"] == str(old_booking_id)
    assert payload["new_booking_id"] == str(response.id)
    assert payload["client_id"] == str(client.id)
    assert payload["actor_role"] == "client"


# ---------------------------------------------------------------------------
# 7. PT-credit preservation: sessions_remaining unchanged (T-80-11)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reschedule_booking_pt_credit_preserved(
    db_session: AsyncSession,
    make_active_trainer: Any,
    make_linked_client: Any,
    make_active_pt_package: Any,
    make_future_slot: Any,
    fake_bot: object,
    sender_stub: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-80-11: PT-session credit preserved — sessions_remaining IDENTICAL before/after."""
    sender_module, _ = sender_stub
    monkeypatch.setattr("app.modules.bookings.service.telegram_sender", sender_module)
    monkeypatch.setattr("app.modules.bookings.service.build_bot", lambda *, token: fake_bot)

    trainer = await make_active_trainer(full_name="Тренер Кредит")
    client = await make_linked_client(telegram_user_id=880_701, first_name="Игорь")
    pkg = await make_active_pt_package(
        client=client, trainer=trainer, sessions_remaining=7
    )

    booking, _, _, _, _ = await _seed_confirmed_booking(
        db_session,
        make_active_trainer=make_active_trainer,
        make_linked_client=make_linked_client,
        make_active_pt_package=make_active_pt_package,
        make_future_slot=make_future_slot,
        trainer=trainer,
        client=client,
        pt_package=pkg,
    )
    new_slot = await make_future_slot(trainer=trainer, start_offset=timedelta(hours=90))

    # Capture sessions_remaining BEFORE reschedule.
    await db_session.refresh(pkg)
    sessions_before = pkg.sessions_remaining

    await bookings_service.reschedule_booking_for_client(
        db_session,
        client_id=client.id,
        booking_id=booking.id,
        new_slot_id=new_slot.id,
    )

    # Capture sessions_remaining AFTER reschedule.
    await db_session.refresh(pkg)
    sessions_after = pkg.sessions_remaining

    assert sessions_before == sessions_after, (
        f"PT credit changed! before={sessions_before}, after={sessions_after} — "
        "reschedule must be a slot MOVE, not cancel+rebook (T-80-11)"
    )


# ---------------------------------------------------------------------------
# 8. DM sent: send_text_dm called once with rendered reschedule DM text (T-80-14)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reschedule_booking_dm_sent(
    db_session: AsyncSession,
    make_active_trainer: Any,
    make_linked_client: Any,
    make_active_pt_package: Any,
    make_future_slot: Any,
    fake_bot: object,
    sender_stub: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-80-14: send_text_dm called exactly once with reschedule DM text containing
    the NEW slot time — NOT merely asserting the notification row exists."""
    sender_module, sender_state = sender_stub
    monkeypatch.setattr("app.modules.bookings.service.telegram_sender", sender_module)
    monkeypatch.setattr("app.modules.bookings.service.build_bot", lambda *, token: fake_bot)

    trainer_full_name = "Тренер ДМ"
    client_first_name = "Катя"
    trainer = await make_active_trainer(full_name=trainer_full_name)
    client = await make_linked_client(
        telegram_user_id=880_801, first_name=client_first_name
    )
    pkg = await make_active_pt_package(client=client, trainer=trainer, sessions_remaining=5)

    booking, _, _, _, _ = await _seed_confirmed_booking(
        db_session,
        make_active_trainer=make_active_trainer,
        make_linked_client=make_linked_client,
        make_active_pt_package=make_active_pt_package,
        make_future_slot=make_future_slot,
        trainer=trainer,
        client=client,
        pt_package=pkg,
    )
    new_slot = await make_future_slot(trainer=trainer, start_offset=timedelta(hours=100))

    await bookings_service.reschedule_booking_for_client(
        db_session,
        client_id=client.id,
        booking_id=booking.id,
        new_slot_id=new_slot.id,
    )

    # Assert send_text_dm was called exactly once (not zero, not two).
    assert len(sender_state.calls) == 1, (
        f"Expected exactly 1 send_text_dm call, got {len(sender_state.calls)}"
    )
    call = sender_state.calls[0]
    assert call.bot is fake_bot
    assert call.chat_id == 880_801

    # Assert the sent text contains the NEW slot time in Moscow TZ.
    new_slot_start_msk = new_slot.start_time.astimezone(
        bookings_service.MOSCOW_TZ
    ).strftime("%d.%m.%Y %H:%M")
    expected_text = render_booking_rescheduled_dm(
        client_name=client_first_name,
        trainer_name=trainer_full_name,
        new_slot_start_msk=new_slot_start_msk,
    )
    assert call.text == expected_text, (
        f"DM text mismatch.\nExpected: {expected_text!r}\nGot: {call.text!r}"
    )
    # The new slot time string must appear in the DM body.
    assert new_slot_start_msk in call.text, (
        f"New slot time {new_slot_start_msk!r} not found in DM text: {call.text!r}"
    )


# ---------------------------------------------------------------------------
# 9. Notification row: booking_notifications kind='rescheduled', channel='telegram'
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reschedule_booking_notification_row_inserted(
    db_session: AsyncSession,
    make_active_trainer: Any,
    make_linked_client: Any,
    make_active_pt_package: Any,
    make_future_slot: Any,
    fake_bot: object,
    sender_stub: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RESCH-02: booking_notifications row kind='rescheduled', channel='telegram'
    inserted as post-send evidence for the new booking."""
    sender_module, sender_state = sender_stub
    monkeypatch.setattr("app.modules.bookings.service.telegram_sender", sender_module)
    monkeypatch.setattr("app.modules.bookings.service.build_bot", lambda *, token: fake_bot)

    trainer = await make_active_trainer(full_name="Тренер Уведомление")
    client = await make_linked_client(telegram_user_id=880_901, first_name="Лена")
    pkg = await make_active_pt_package(client=client, trainer=trainer, sessions_remaining=5)

    booking, _, _, _, _ = await _seed_confirmed_booking(
        db_session,
        make_active_trainer=make_active_trainer,
        make_linked_client=make_linked_client,
        make_active_pt_package=make_active_pt_package,
        make_future_slot=make_future_slot,
        trainer=trainer,
        client=client,
        pt_package=pkg,
    )
    new_slot = await make_future_slot(trainer=trainer, start_offset=timedelta(hours=110))

    response = await bookings_service.reschedule_booking_for_client(
        db_session,
        client_id=client.id,
        booking_id=booking.id,
        new_slot_id=new_slot.id,
    )

    # Exactly one send was made (confirming it's a post-send INSERT).
    assert len(sender_state.calls) == 1

    # booking_notifications row for the NEW booking.
    notif_row = await db_session.scalar(
        select(BookingNotification).where(
            BookingNotification.booking_id == response.id,
            BookingNotification.kind == "rescheduled",
            BookingNotification.channel == "telegram",
        )
    )
    assert notif_row is not None, (
        f"Expected booking_notifications row kind='rescheduled', channel='telegram' "
        f"for new booking {response.id} — not found (RESCH-02 post-send evidence)"
    )


# ---------------------------------------------------------------------------
# 10. CR-01: post-commit DM failure does NOT fail the reschedule (fire-and-forget)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reschedule_booking_dm_failure_does_not_fail_reschedule(
    db_session: AsyncSession,
    make_active_trainer: Any,
    make_linked_client: Any,
    make_active_pt_package: Any,
    make_future_slot: Any,
    fake_bot: object,
    sender_stub: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 80 CR-01 / D-39-09: a post-commit DM-send failure (network exception
    raised AFTER the authoritative Step 11 commit) MUST NOT propagate out of the
    reschedule. The function still returns the 200 response and the reschedule is
    durable (old booking cancelled, new booking confirmed)."""
    sender_module, _sender_state = sender_stub

    async def _raising_send_text_dm(bot: object, chat_id: int, text: str) -> Any:
        # Simulate a transient Telegram/connection failure that raises instead of
        # returning a typed SendResult — the worst case the fire-and-forget
        # envelope must swallow.
        raise RuntimeError("simulated telegram failure after commit")

    sender_module.send_text_dm = _raising_send_text_dm
    monkeypatch.setattr("app.modules.bookings.service.telegram_sender", sender_module)
    monkeypatch.setattr("app.modules.bookings.service.build_bot", lambda *, token: fake_bot)

    trainer = await make_active_trainer(full_name="Тренер Сбой")
    client = await make_linked_client(telegram_user_id=881_001, first_name="Олег")
    pkg = await make_active_pt_package(client=client, trainer=trainer, sessions_remaining=5)

    booking, old_slot, _, _, _ = await _seed_confirmed_booking(
        db_session,
        make_active_trainer=make_active_trainer,
        make_linked_client=make_linked_client,
        make_active_pt_package=make_active_pt_package,
        make_future_slot=make_future_slot,
        trainer=trainer,
        client=client,
        pt_package=pkg,
    )
    new_slot = await make_future_slot(trainer=trainer, start_offset=timedelta(hours=120))

    # MUST NOT raise — the DM failure is swallowed by the fire-and-forget envelope.
    response = await bookings_service.reschedule_booking_for_client(
        db_session,
        client_id=client.id,
        booking_id=booking.id,
        new_slot_id=new_slot.id,
    )

    # Response reflects the durably-committed reschedule.
    assert response.status == BookingStatus.CONFIRMED
    assert response.slot_id == new_slot.id

    # Reschedule is durable: old cancelled, new confirmed, slots flipped.
    await db_session.refresh(booking)
    assert booking.status == "cancelled"
    await db_session.refresh(old_slot, attribute_names=["status"])
    assert old_slot.status == "active"
    await db_session.refresh(new_slot, attribute_names=["status"])
    assert new_slot.status == "booked"

    new_booking_row = await db_session.scalar(
        select(Booking).where(Booking.id == response.id)
    )
    assert new_booking_row is not None
    assert new_booking_row.status == "confirmed"

    # No evidence row was written (the send raised before the INSERT) — and that
    # is fine: the reschedule succeeded regardless.
    notif_row = await db_session.scalar(
        select(BookingNotification).where(
            BookingNotification.booking_id == response.id,
            BookingNotification.kind == "rescheduled",
        )
    )
    assert notif_row is None
