"""Phase 45 D-45-05 / D-45-06 — booking email-fallback integration tests.

Exercises the per-callsite fanout when Telegram returns ``SendResult.blocked``
AND the client has ``email IS NOT NULL`` (D-45-01 cross-channel relax). Four
positive cases lock the 4 booking ``kind`` literals + 1 negative case
verifies Telegram-success does NOT fan out to email:

  1. ``test_booking_confirmed_telegram_blocked_fanouts_email`` — FSM
     transition to confirmed for a client with email + telegram_user_id;
     sender returns blocked=True. Assert ``booking_notifications`` row
     with ``kind='confirmed'`` ``channel='email'`` + recorder.calls with
     ``template_id='EMAIL_BOOKING_CONFIRMED'``.

  2. ``test_booking_cancelled_by_client_fanouts_email`` — same shape but
     reception cancels (kind=cancelled_by_client). Template
     ``EMAIL_BOOKING_CANCELLED_BY_CLIENT``.

  3. ``test_booking_cancelled_by_owner_fanouts_email`` — same shape but
     owner cancels (kind=cancelled_by_owner). Template
     ``EMAIL_BOOKING_CANCELLED_BY_OWNER``.

  4. ``test_booking_reminder_24h_fanouts_email`` — invoke the reminder
     cron (``_send_booking_reminders``). Assert ``booking_notifications``
     row with ``kind='reminder_24h'`` ``channel='email'`` + recorder.calls
     with ``template_id='EMAIL_BOOKING_REMINDER_24H'``.

  5. ``test_booking_reminder_telegram_success_no_email`` — negative.
     Telegram succeeds → channel='telegram' row + 0 recorder.calls.

Mirrors ``tests/integration/test_expiring_email_fallback.py`` (Plan 45-07)
shape locally (no fixture cross-import) per D-45-03 / D-45-04. Uses the
SAVEPOINT-rolled ``db_session`` fixture for atomic test isolation.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import dependencies as deps_mod
from app.core.dependencies import register_email_dispatcher
from app.core.permissions import Role
from app.core.security import hash_password
from app.integrations.telegram.sender import SendResult
from app.modules.auth.models import User
from app.modules.bookings import notifications as bookings_notifications
from app.modules.bookings import service as bookings_service
from app.modules.bookings.models import Booking, BookingNotification
from app.modules.bookings.schemas import BookingCancelRequest, BookingCreateRequest
from app.modules.clients.models import Client
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.schedule.models import TrainerAvailabilitySlot
from app.modules.trainers.models import Trainer

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Local fixtures — savepoint sessionmaker + sender stub + email recorder.
# Mirror tests/integration/test_expiring_email_fallback.py shape.
# ---------------------------------------------------------------------------


class _SessionContext:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *args: Any) -> None:
        return None


class _SavepointSessionmaker:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def __call__(self) -> _SessionContext:
        return _SessionContext(self._session)


@pytest_asyncio.fixture
async def session_factory(db_session: AsyncSession) -> _SavepointSessionmaker:
    return _SavepointSessionmaker(db_session)


@dataclass
class _RecordedSend:
    chat_id: int | None
    text: str


@dataclass
class _SenderState:
    next_result: SendResult = field(default_factory=lambda: SendResult(ok=True))
    calls: list[_RecordedSend] = field(default_factory=list)


def _make_sender_stub() -> tuple[SimpleNamespace, _SenderState]:
    state = _SenderState()

    async def send_text_dm(bot: object, chat_id: int, text: str) -> SendResult:
        state.calls.append(_RecordedSend(chat_id=chat_id, text=text))
        return state.next_result

    module = SimpleNamespace(send_text_dm=send_text_dm)
    return module, state


@dataclass
class _RecordedEmail:
    template_id: str
    to: str
    audit_correlation_id: UUID | None
    template_vars: dict[str, Any]


class _RecordingEmailDispatcher:
    """Spy satisfying the Phase 41 D-41-24 EmailDispatcher Protocol."""

    def __init__(self) -> None:
        self.calls: list[_RecordedEmail] = []

    async def __call__(
        self,
        *,
        template_id: str,
        to: str,
        audit_correlation_id: UUID | None,
        **template_vars: Any,
    ) -> None:
        self.calls.append(
            _RecordedEmail(
                template_id=template_id,
                to=to,
                audit_correlation_id=audit_correlation_id,
                template_vars=template_vars,
            )
        )


@pytest_asyncio.fixture
async def email_recorder() -> AsyncIterator[_RecordingEmailDispatcher]:
    prior = deps_mod._email_dispatcher
    recorder = _RecordingEmailDispatcher()
    register_email_dispatcher(recorder)
    try:
        yield recorder
    finally:
        if prior is not None:
            register_email_dispatcher(prior)
        else:
            deps_mod._email_dispatcher = None


# ---------------------------------------------------------------------------
# Factories — owner + clients + plans + slots + bookings. Self-contained.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seeded_owner(db_session: AsyncSession) -> User:
    user = User(
        email=f"phase45-book-fallback-owner-{uuid4().hex[:8]}@example.com",
        password_hash=await hash_password("hunter22hunter22"),
        role=Role.OWNER,
        full_name="Phase 45 Booking Fallback Owner",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def seeded_reception(db_session: AsyncSession) -> User:
    user = User(
        email=f"phase45-book-fallback-reception-{uuid4().hex[:8]}@example.com",
        password_hash=await hash_password("hunter22hunter22"),
        role=Role.RECEPTION,
        full_name="Phase 45 Booking Fallback Reception",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _make_client(
    db_session: AsyncSession,
    *,
    owner: User,
    counter: int,
    telegram_user_id: int | None,
    email: str | None,
    last_name: str = "Тестов",
    first_name: str = "Клиент",
) -> Client:
    client = Client(
        last_name=last_name,
        first_name=first_name,
        phone=f"+7999285{counter:04d}",
        email=email,
        telegram_user_id=telegram_user_id,
        created_by_user_id=owner.id,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


async def _make_trainer(
    db_session: AsyncSession,
    *,
    full_name: str = "Алексей Иванов",
) -> Trainer:
    trainer = Trainer(full_name=full_name, phone=None, is_active=True)
    db_session.add(trainer)
    await db_session.commit()
    await db_session.refresh(trainer)
    return trainer


async def _make_slot(
    db_session: AsyncSession,
    *,
    trainer: Trainer,
    owner: User,
    start_offset: timedelta = timedelta(hours=24),
    duration: timedelta = timedelta(hours=1),
) -> TrainerAvailabilitySlot:
    start = datetime.now(tz=UTC) + start_offset
    slot = TrainerAvailabilitySlot(
        trainer_id=trainer.id,
        start_time=start,
        end_time=start + duration,
        status="active",
        created_by_user_id=owner.id,
    )
    db_session.add(slot)
    await db_session.commit()
    await db_session.refresh(slot)
    return slot


async def _make_active_pkg(
    db_session: AsyncSession,
    *,
    client: Client,
    counter: int,
) -> PtPackage:
    plan = PtPackagePlan(
        name=f"BookFallbackPlan-{counter}-{uuid4().hex[:4]}",
        session_count=10,
        price_kopecks=500000,
        validity_days=90,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)

    today = datetime.now(tz=UTC).date()
    pkg = PtPackage(
        client_id=client.id,
        plan_id=plan.id,
        plan_name_snapshot=plan.name,
        session_count_snapshot=plan.session_count,
        price_kopecks_snapshot=plan.price_kopecks,
        validity_days_snapshot=plan.validity_days,
        sessions_remaining=5,
        status="active",
        start_date=today,
        end_date=today + timedelta(days=89),
    )
    db_session.add(pkg)
    await db_session.commit()
    await db_session.refresh(pkg)
    return pkg


async def _make_confirmed_booking_direct(
    db_session: AsyncSession,
    *,
    slot: TrainerAvailabilitySlot,
    client: Client,
    pkg: PtPackage,
    actor: User,
) -> Booking:
    """Insert a confirmed Booking + flip the slot to 'booked' directly.

    Bypasses the service-layer create_booking UoW (no audit emit, no DM
    dispatch) so cancel-side tests can craft a starting state without
    triggering an upstream confirmation-DM dispatch.
    """
    booking = Booking(
        slot_id=slot.id,
        client_id=client.id,
        pt_package_id=pkg.id,
        created_by_user_id=actor.id,
        status="confirmed",
    )
    db_session.add(booking)
    slot.status = "booked"
    await db_session.commit()
    await db_session.refresh(booking)
    return booking


# ---------------------------------------------------------------------------
# Tests — 4 positive (one per kind) + 1 negative (Telegram success).
# ---------------------------------------------------------------------------


async def test_booking_confirmed_telegram_blocked_fanouts_email(
    db_session: AsyncSession,
    email_recorder: _RecordingEmailDispatcher,
    seeded_owner: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FSM hook: create_booking with Telegram-blocked + email → fanout."""
    trainer = await _make_trainer(db_session, full_name="Алексей Иванов")
    slot = await _make_slot(db_session, trainer=trainer, owner=seeded_owner)
    client = await _make_client(
        db_session,
        owner=seeded_owner,
        counter=1,
        telegram_user_id=900_101,
        email="confirmed-fallback@example.com",
        first_name="Иван",
    )
    pkg = await _make_active_pkg(db_session, client=client, counter=1)

    sender_module, sender_state = _make_sender_stub()
    sender_state.next_result = SendResult(ok=False, blocked=True, error="forbidden")

    monkeypatch.setattr("app.modules.bookings.service.telegram_sender", sender_module)
    monkeypatch.setattr(
        "app.modules.bookings.service.build_bot",
        lambda *, token: object(),
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

    assert response is not None
    assert len(sender_state.calls) == 1, "Telegram still attempted"

    # booking_notifications row — channel='email'.
    notif_rows = (
        (
            await db_session.execute(
                select(BookingNotification).where(BookingNotification.booking_id == response.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(notif_rows) == 1, "exactly one email-channel row"
    assert notif_rows[0].kind == "confirmed"
    assert notif_rows[0].channel == "email"

    # EmailDispatcher recorder — one call with EMAIL_BOOKING_CONFIRMED.
    assert len(email_recorder.calls) == 1
    rec = email_recorder.calls[0]
    assert rec.template_id == "EMAIL_BOOKING_CONFIRMED"
    assert rec.to == "confirmed-fallback@example.com"
    assert rec.audit_correlation_id is not None
    assert rec.template_vars["trainer_name"] == "Алексей Иванов"


async def test_booking_cancelled_by_client_fanouts_email(
    db_session: AsyncSession,
    email_recorder: _RecordingEmailDispatcher,
    seeded_owner: User,
    seeded_reception: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FSM hook: cancel_booking (reception actor) → cancelled_by_client kind."""
    trainer = await _make_trainer(db_session)
    # 48h offset so the reception-actor cancel window guard (24h floor)
    # does not fire — this test exercises the cancel-DM path, not the
    # window-validation path.
    slot = await _make_slot(
        db_session,
        trainer=trainer,
        owner=seeded_owner,
        start_offset=timedelta(hours=48),
    )
    client = await _make_client(
        db_session,
        owner=seeded_owner,
        counter=2,
        telegram_user_id=900_102,
        email="cbc-fallback@example.com",
    )
    pkg = await _make_active_pkg(db_session, client=client, counter=2)
    booking = await _make_confirmed_booking_direct(
        db_session, slot=slot, client=client, pkg=pkg, actor=seeded_owner
    )

    sender_module, sender_state = _make_sender_stub()
    sender_state.next_result = SendResult(ok=False, blocked=True, error="forbidden")
    monkeypatch.setattr("app.modules.bookings.service.telegram_sender", sender_module)
    monkeypatch.setattr(
        "app.modules.bookings.service.build_bot",
        lambda *, token: object(),
    )

    await bookings_service.cancel_booking(
        db_session,
        seeded_reception,
        booking.id,
        BookingCancelRequest(reason="client-request"),
    )

    assert len(sender_state.calls) == 1

    notif_rows = (
        (
            await db_session.execute(
                select(BookingNotification).where(BookingNotification.booking_id == booking.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(notif_rows) == 1
    assert notif_rows[0].kind == "cancelled_by_client"
    assert notif_rows[0].channel == "email"

    assert len(email_recorder.calls) == 1
    assert email_recorder.calls[0].template_id == "EMAIL_BOOKING_CANCELLED_BY_CLIENT"
    assert email_recorder.calls[0].to == "cbc-fallback@example.com"


async def test_booking_cancelled_by_owner_fanouts_email(
    db_session: AsyncSession,
    email_recorder: _RecordingEmailDispatcher,
    seeded_owner: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FSM hook: cancel_booking (owner actor) → cancelled_by_owner kind."""
    trainer = await _make_trainer(db_session)
    slot = await _make_slot(db_session, trainer=trainer, owner=seeded_owner)
    client = await _make_client(
        db_session,
        owner=seeded_owner,
        counter=3,
        telegram_user_id=900_103,
        email="cbo-fallback@example.com",
    )
    pkg = await _make_active_pkg(db_session, client=client, counter=3)
    booking = await _make_confirmed_booking_direct(
        db_session, slot=slot, client=client, pkg=pkg, actor=seeded_owner
    )

    sender_module, sender_state = _make_sender_stub()
    sender_state.next_result = SendResult(ok=False, blocked=True, error="forbidden")
    monkeypatch.setattr("app.modules.bookings.service.telegram_sender", sender_module)
    monkeypatch.setattr(
        "app.modules.bookings.service.build_bot",
        lambda *, token: object(),
    )

    await bookings_service.cancel_booking(
        db_session,
        seeded_owner,
        booking.id,
        BookingCancelRequest(reason="venue-conflict"),
    )

    assert len(sender_state.calls) == 1

    notif_rows = (
        (
            await db_session.execute(
                select(BookingNotification).where(BookingNotification.booking_id == booking.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(notif_rows) == 1
    assert notif_rows[0].kind == "cancelled_by_owner"
    assert notif_rows[0].channel == "email"

    assert len(email_recorder.calls) == 1
    assert email_recorder.calls[0].template_id == "EMAIL_BOOKING_CANCELLED_BY_OWNER"


async def test_booking_reminder_24h_fanouts_email(
    db_session: AsyncSession,
    session_factory: _SavepointSessionmaker,
    email_recorder: _RecordingEmailDispatcher,
    seeded_owner: User,
) -> None:
    """Reminder cron: _send_booking_reminders with Telegram-blocked + email."""
    trainer = await _make_trainer(db_session)
    slot = await _make_slot(
        db_session,
        trainer=trainer,
        owner=seeded_owner,
        start_offset=timedelta(hours=24),
    )
    client = await _make_client(
        db_session,
        owner=seeded_owner,
        counter=4,
        telegram_user_id=900_104,
        email="reminder-fallback@example.com",
    )
    pkg = await _make_active_pkg(db_session, client=client, counter=4)
    booking = await _make_confirmed_booking_direct(
        db_session, slot=slot, client=client, pkg=pkg, actor=seeded_owner
    )

    sender_module, sender_state = _make_sender_stub()
    sender_state.next_result = SendResult(ok=False, blocked=True, error="forbidden")

    count = await bookings_service._send_booking_reminders(
        session_factory,
        bot=object(),  # type: ignore[arg-type]
        sender=sender_module,
        notifications_module=bookings_notifications,
    )

    assert count == 1, "email fanout counts as a 'send'"
    assert len(sender_state.calls) == 1

    notif_rows = (
        (
            await db_session.execute(
                select(BookingNotification).where(BookingNotification.booking_id == booking.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(notif_rows) == 1
    assert notif_rows[0].kind == "reminder_24h"
    assert notif_rows[0].channel == "email"

    assert len(email_recorder.calls) == 1
    rec = email_recorder.calls[0]
    assert rec.template_id == "EMAIL_BOOKING_REMINDER_24H"
    assert rec.to == "reminder-fallback@example.com"
    assert "slot_date" in rec.template_vars


async def test_booking_reminder_telegram_success_no_email(
    db_session: AsyncSession,
    session_factory: _SavepointSessionmaker,
    email_recorder: _RecordingEmailDispatcher,
    seeded_owner: User,
) -> None:
    """Negative — Telegram succeeds → channel='telegram' row + zero email."""
    trainer = await _make_trainer(db_session)
    slot = await _make_slot(
        db_session,
        trainer=trainer,
        owner=seeded_owner,
        start_offset=timedelta(hours=24),
    )
    client = await _make_client(
        db_session,
        owner=seeded_owner,
        counter=5,
        telegram_user_id=900_105,
        email="dual-channel-reminder@example.com",
    )
    pkg = await _make_active_pkg(db_session, client=client, counter=5)
    booking = await _make_confirmed_booking_direct(
        db_session, slot=slot, client=client, pkg=pkg, actor=seeded_owner
    )

    sender_module, sender_state = _make_sender_stub()
    # default = SendResult(ok=True) — Telegram succeeds.

    count = await bookings_service._send_booking_reminders(
        session_factory,
        bot=object(),  # type: ignore[arg-type]
        sender=sender_module,
        notifications_module=bookings_notifications,
    )

    assert count == 1
    assert len(sender_state.calls) == 1
    assert len(email_recorder.calls) == 0, "Telegram success → no email"

    notif_rows = (
        (
            await db_session.execute(
                select(BookingNotification).where(BookingNotification.booking_id == booking.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(notif_rows) == 1
    assert notif_rows[0].kind == "reminder_24h"
    assert notif_rows[0].channel == "telegram"
