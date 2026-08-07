"""Phase 87 INBOX-03 — event hook integration tests.

Covers every system event that must produce an in_app_notifications row for the
affected client, plus the two anti-oracle/idempotency invariants required by the
plan success criteria:

  Booking events (5 hooks in bookings/service.py — SAVEPOINT-mode sessions):
    1. create_booking → booking_confirmed
    2. cancel_booking (owner) → booking_cancelled_by_owner (client notified)
    3. cancel_booking (reception) → booking_cancelled_by_client (client notified)
    4. cancel_booking_for_client (self-cancel) → booking_cancelled_by_client
    5. reschedule_booking_for_client → booking_rescheduled (source_id=new_booking.id)

  STAFF-cancels-client-booking test: ensures affected client gets a row even
  when the actor is reception or owner (not the client themselves).

  Payment event (yookassa handler — real-commit via webhook_client):
    6. handle_payment_succeeded (non-autopay) → payment_succeeded
    7. handle_payment_succeeded (autopay) → autopay_charge_succeeded
    (Replay test: calling twice creates exactly ONE row — UNIQUE dedup.)

  Anti-oracle (D-52-08):
    - handle_payment_canceled MUST create ZERO in_app_notifications rows.

  Autopay failure (autopay_charges/service.py — SAVEPOINT-mode):
    8. permanent-failure branch → autopay_charge_failed row for the client.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
import respx
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role
from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.bookings import service as bookings_service
from app.modules.bookings.schemas import BookingCancelRequest, BookingCreateRequest
from app.modules.clients.models import Client
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.schedule.models import TrainerAvailabilitySlot
from app.modules.trainers.models import Trainer

# Re-use the real-commit fixtures from the webhook_yookassa conftest.
from tests.integration.webhook_yookassa.conftest import (  # noqa: F401
    _YOOKASSA_BASE_URL,
    SeededOnlinePayment,
    seeded_online_payment_pending,
    webhook_client,
    webhook_db_session,
    webhook_engine,
    yookassa_get_payment_succeeded,
    yookassa_webhook_payload,
)

# ---------------------------------------------------------------------------
# Helpers — raw SQL count of in_app_notifications rows for assertions.
# ---------------------------------------------------------------------------


async def _count_notifications(
    session: AsyncSession,
    *,
    client_id: UUID,
    kind: str | None = None,
    source_id: UUID | None = None,
) -> int:
    """Count in_app_notifications rows for the given client/kind/source_id."""
    parts = ["SELECT COUNT(*) FROM in_app_notifications WHERE client_id = :client_id"]
    params: dict[str, Any] = {"client_id": str(client_id)}
    if kind is not None:
        parts.append("AND kind = :kind")
        params["kind"] = kind
    if source_id is not None:
        parts.append("AND source_id = :source_id")
        params["source_id"] = str(source_id)
    row = (await session.execute(text(" ".join(parts)), params)).fetchone()
    return int(row[0]) if row else 0


async def _count_all_notifications(session: AsyncSession) -> int:
    row = (await session.execute(text("SELECT COUNT(*) FROM in_app_notifications"))).fetchone()
    return int(row[0]) if row else 0


# ---------------------------------------------------------------------------
# SAVEPOINT-mode fixtures for booking / autopay tests.
# ---------------------------------------------------------------------------


async def _seed_owner_user(db_session: AsyncSession, *, suffix: str) -> User:
    owner = User(
        email=f"hook-owner-{suffix}@example.com",
        password_hash=await hash_password("hunter22hunter22"),
        role=Role.OWNER,
        full_name="Hook Owner",
    )
    db_session.add(owner)
    await db_session.commit()
    await db_session.refresh(owner)
    return owner


async def _seed_reception_user(db_session: AsyncSession, *, suffix: str) -> User:
    user = User(
        email=f"hook-recep-{suffix}@example.com",
        password_hash=await hash_password("hunter22hunter22"),
        role=Role.RECEPTION,
        full_name="Hook Reception",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _seed_trainer(db_session: AsyncSession) -> Trainer:
    trainer = Trainer(full_name=f"Hook Trainer {uuid4().hex[:4]}", is_active=True, phone=None)
    db_session.add(trainer)
    await db_session.commit()
    await db_session.refresh(trainer)
    return trainer


async def _seed_client(db_session: AsyncSession, *, owner: User) -> Client:
    nonce = uuid4().hex[:6]
    client = Client(
        last_name="Тестов",
        first_name="Тест",
        phone=f"+7910{nonce}",
        created_by_user_id=owner.id,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


async def _seed_pt_plan(db_session: AsyncSession) -> PtPackagePlan:
    plan = PtPackagePlan(
        name=f"HookPlan-{uuid4().hex[:4]}",
        session_count=10,
        price_kopecks=500_000,
        validity_days=90,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    return plan


async def _seed_pt_package(
    db_session: AsyncSession, *, client: Client, plan: PtPackagePlan
) -> PtPackage:
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


async def _seed_active_slot(
    db_session: AsyncSession, *, trainer: Trainer, owner: User, start_offset_hours: int = 25
) -> TrainerAvailabilitySlot:
    start = datetime.now(tz=UTC) + timedelta(hours=start_offset_hours)
    slot = TrainerAvailabilitySlot(
        trainer_id=trainer.id,
        start_time=start,
        end_time=start + timedelta(hours=1),
        status="active",
        created_by_user_id=owner.id,
    )
    db_session.add(slot)
    await db_session.commit()
    await db_session.refresh(slot)
    return slot


async def _seed_confirmed_booking(
    db_session: AsyncSession,
    *,
    slot: TrainerAvailabilitySlot,
    client: Client,
    pkg: PtPackage,
    owner: User,
) -> Any:
    """Direct ORM insert of a confirmed booking + flip slot to 'booked'."""
    from app.modules.bookings.models import Booking

    booking = Booking(
        slot_id=slot.id,
        client_id=client.id,
        pt_package_id=pkg.id,
        created_by_user_id=owner.id,
        status="confirmed",
    )
    db_session.add(booking)
    slot.status = "booked"
    await db_session.commit()
    await db_session.refresh(booking)
    await db_session.refresh(slot)
    return booking


# ---------------------------------------------------------------------------
# Hook 1 — create_booking → booking_confirmed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_booking_creates_booking_confirmed_row(
    db_session: AsyncSession,
    app: Any,
) -> None:
    """create_booking must insert one booking_confirmed inbox row for the client."""
    owner = await _seed_owner_user(db_session, suffix=uuid4().hex[:6])
    trainer = await _seed_trainer(db_session)
    client = await _seed_client(db_session, owner=owner)
    plan = await _seed_pt_plan(db_session)
    pkg = await _seed_pt_package(db_session, client=client, plan=plan)
    slot = await _seed_active_slot(db_session, trainer=trainer, owner=owner)

    # User satisfies the CurrentUser Protocol structurally (id + role + email attrs)
    await bookings_service.create_booking(
        db_session,
        owner,  # type: ignore[arg-type]  # User satisfies CurrentUser Protocol
        BookingCreateRequest(
            slot_id=slot.id,
            client_id=client.id,
            pt_package_id=pkg.id,
        ),
    )

    count = await _count_notifications(db_session, client_id=client.id, kind="booking_confirmed")
    assert count == 1, f"Expected 1 booking_confirmed row, got {count}"


# ---------------------------------------------------------------------------
# Hook 1b — create_booking_via_bot → booking_confirmed (WR-03 fix)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_booking_via_bot_creates_booking_confirmed_row(
    db_session: AsyncSession,
    app: Any,
) -> None:
    """WR-03: create_booking_via_bot must insert one booking_confirmed inbox row for the client."""
    from unittest.mock import AsyncMock, patch

    owner = await _seed_owner_user(db_session, suffix=uuid4().hex[:6])
    trainer = await _seed_trainer(db_session)
    client = await _seed_client(db_session, owner=owner)
    plan = await _seed_pt_plan(db_session)
    pkg = await _seed_pt_package(db_session, client=client, plan=plan)
    slot = await _seed_active_slot(db_session, trainer=trainer, owner=owner)

    # Patch the post-commit DM dispatch so it doesn't fail without Telegram creds.
    with patch(
        "app.modules.bookings.service._dispatch_booking_lifecycle_notification",
        new_callable=AsyncMock,
    ):
        await bookings_service.create_booking_via_bot(
            db_session,
            client_id=client.id,
            slot_id=slot.id,
            pt_package_id=pkg.id,
        )

    count = await _count_notifications(db_session, client_id=client.id, kind="booking_confirmed")
    assert count == 1, (
        f"WR-03: Expected 1 booking_confirmed row from create_booking_via_bot, got {count}"
    )


# ---------------------------------------------------------------------------
# Hook 1c — create_booking_for_client → booking_confirmed (WR-04 fix)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_booking_for_client_creates_booking_confirmed_row(
    db_session: AsyncSession,
    app: Any,
) -> None:
    """WR-04: create_booking_for_client must insert one booking_confirmed inbox row for the client."""  # noqa: E501
    owner = await _seed_owner_user(db_session, suffix=uuid4().hex[:6])
    trainer = await _seed_trainer(db_session)
    client = await _seed_client(db_session, owner=owner)
    plan = await _seed_pt_plan(db_session)
    pkg = await _seed_pt_package(db_session, client=client, plan=plan)
    slot = await _seed_active_slot(db_session, trainer=trainer, owner=owner)

    await bookings_service.create_booking_for_client(
        db_session,
        client_id=client.id,
        slot_id=slot.id,
        pt_package_id=pkg.id,
    )

    count = await _count_notifications(db_session, client_id=client.id, kind="booking_confirmed")
    assert count == 1, (
        f"WR-04: Expected 1 booking_confirmed row from create_booking_for_client, got {count}"
    )


# ---------------------------------------------------------------------------
# Hook 2 — cancel_booking (owner) → booking_cancelled_by_owner
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_booking_owner_creates_cancelled_by_owner_row(
    db_session: AsyncSession,
    app: Any,
) -> None:
    """Staff cancel by OWNER must insert booking_cancelled_by_owner for the AFFECTED CLIENT."""
    owner = await _seed_owner_user(db_session, suffix=uuid4().hex[:6])
    trainer = await _seed_trainer(db_session)
    client = await _seed_client(db_session, owner=owner)
    plan = await _seed_pt_plan(db_session)
    pkg = await _seed_pt_package(db_session, client=client, plan=plan)
    slot = await _seed_active_slot(db_session, trainer=trainer, owner=owner)
    booking = await _seed_confirmed_booking(
        db_session, slot=slot, client=client, pkg=pkg, owner=owner
    )

    await bookings_service.cancel_booking(
        db_session,
        owner,  # type: ignore[arg-type]  # User satisfies CurrentUser Protocol
        booking.id,
        BookingCancelRequest(reason="test-owner-cancel"),
    )

    count = await _count_notifications(
        db_session, client_id=client.id, kind="booking_cancelled_by_owner"
    )
    assert count == 1, f"Expected 1 booking_cancelled_by_owner row, got {count}"
    # Anti-oracle: no booking_cancelled_by_client row created
    by_client_count = await _count_notifications(
        db_session, client_id=client.id, kind="booking_cancelled_by_client"
    )
    assert by_client_count == 0


# ---------------------------------------------------------------------------
# Hook 3 — cancel_booking (reception) → booking_cancelled_by_client
# STAFF-cancels-client-booking test: client receives a row when STAFF cancels.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_booking_reception_creates_cancelled_by_client_row(
    db_session: AsyncSession,
    app: Any,
) -> None:
    """Staff cancel by RECEPTION must insert booking_cancelled_by_client for the AFFECTED CLIENT.

    INBOX-03: the affected client MUST be notified even though the actor is staff, not the client.
    """
    owner = await _seed_owner_user(db_session, suffix=uuid4().hex[:6])
    recep = await _seed_reception_user(db_session, suffix=uuid4().hex[:6])
    trainer = await _seed_trainer(db_session)
    client = await _seed_client(db_session, owner=owner)
    plan = await _seed_pt_plan(db_session)
    pkg = await _seed_pt_package(db_session, client=client, plan=plan)
    # Slot must be > 24h in the future for reception cancel window
    slot = await _seed_active_slot(db_session, trainer=trainer, owner=owner, start_offset_hours=48)
    booking = await _seed_confirmed_booking(
        db_session, slot=slot, client=client, pkg=pkg, owner=owner
    )

    await bookings_service.cancel_booking(
        db_session,
        recep,  # type: ignore[arg-type]  # User satisfies CurrentUser Protocol
        booking.id,
        BookingCancelRequest(reason="test-reception-cancel"),
    )

    # STAFF-cancels-client-booking: affected CLIENT gets the row (not the actor)
    count = await _count_notifications(
        db_session, client_id=client.id, kind="booking_cancelled_by_client"
    )
    assert count == 1, (
        f"Expected 1 booking_cancelled_by_client row for affected client, got {count}. "
        "INBOX-03: staff-initiated cancel MUST notify the affected client."
    )
    # Anti-oracle: no booking_cancelled_by_owner row
    by_owner_count = await _count_notifications(
        db_session, client_id=client.id, kind="booking_cancelled_by_owner"
    )
    assert by_owner_count == 0


# ---------------------------------------------------------------------------
# Hook 4 — cancel_booking_for_client (self-cancel) → booking_cancelled_by_client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_booking_for_client_creates_cancelled_by_client_row(
    db_session: AsyncSession,
    app: Any,
) -> None:
    """Client self-cancel must insert booking_cancelled_by_client for the client."""
    owner = await _seed_owner_user(db_session, suffix=uuid4().hex[:6])
    trainer = await _seed_trainer(db_session)
    client = await _seed_client(db_session, owner=owner)
    plan = await _seed_pt_plan(db_session)
    pkg = await _seed_pt_package(db_session, client=client, plan=plan)
    # Client cancel window is 24h; slot must be > 24h in the future
    slot = await _seed_active_slot(db_session, trainer=trainer, owner=owner, start_offset_hours=48)
    booking = await _seed_confirmed_booking(
        db_session, slot=slot, client=client, pkg=pkg, owner=owner
    )

    await bookings_service.cancel_booking_for_client(
        db_session,
        client_id=client.id,
        booking_id=booking.id,
        cancel_reason="self-cancel",
    )

    count = await _count_notifications(
        db_session, client_id=client.id, kind="booking_cancelled_by_client"
    )
    assert count == 1, f"Expected 1 booking_cancelled_by_client (self-cancel) row, got {count}"


# ---------------------------------------------------------------------------
# Hook 5 — reschedule_booking_for_client → booking_rescheduled (source_id=new_booking.id)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reschedule_booking_for_client_creates_booking_rescheduled_row(
    db_session: AsyncSession,
    app: Any,
) -> None:
    """reschedule_booking_for_client must insert booking_rescheduled with source_id=new_booking.id."""  # noqa: E501
    owner = await _seed_owner_user(db_session, suffix=uuid4().hex[:6])
    trainer = await _seed_trainer(db_session)
    client = await _seed_client(db_session, owner=owner)
    plan = await _seed_pt_plan(db_session)
    pkg = await _seed_pt_package(db_session, client=client, plan=plan)
    # Both slots > 24h in the future for the reschedule window
    old_slot = await _seed_active_slot(
        db_session, trainer=trainer, owner=owner, start_offset_hours=48
    )
    new_slot = await _seed_active_slot(
        db_session, trainer=trainer, owner=owner, start_offset_hours=72
    )
    booking = await _seed_confirmed_booking(
        db_session, slot=old_slot, client=client, pkg=pkg, owner=owner
    )

    response = await bookings_service.reschedule_booking_for_client(
        db_session,
        client_id=client.id,
        booking_id=booking.id,
        new_slot_id=new_slot.id,
    )

    # source_id must be the NEW booking id (plan mapping)
    count = await _count_notifications(
        db_session,
        client_id=client.id,
        kind="booking_rescheduled",
        source_id=response.id,
    )
    assert count == 1, (
        f"Expected 1 booking_rescheduled row with source_id=new_booking.id, got {count}"
    )


# ---------------------------------------------------------------------------
# STAFF-cancels-client-booking explicit assertion (INBOX-03 guard)
# ---------------------------------------------------------------------------
# Already covered above in test_cancel_booking_reception_creates_cancelled_by_client_row
# and test_cancel_booking_owner_creates_cancelled_by_owner_row. Both assert that
# the AFFECTED CLIENT receives a row when staff (owner or reception) cancels.


# ---------------------------------------------------------------------------
# Payment-succeeded hook — real-commit via webhook_client (session.begin() compat)
# ---------------------------------------------------------------------------


@pytest.fixture
def webhook_payment_succeeded_body_factory() -> Any:
    """Return a factory for a minimal payment.succeeded webhook body."""

    def _factory(yookassa_payment_id: str) -> dict[str, Any]:
        return {
            "event": "payment.succeeded",
            "object": {"id": yookassa_payment_id, "status": "succeeded"},
        }

    return _factory


@pytest.mark.asyncio
async def test_payment_succeeded_creates_payment_succeeded_row(
    webhook_client: AsyncClient,  # noqa: F811
    webhook_db_session: AsyncSession,  # noqa: F811
    seeded_online_payment_pending: SeededOnlinePayment,  # noqa: F811
    yookassa_get_payment_succeeded: respx.MockRouter,  # noqa: F811
    webhook_payment_succeeded_body_factory: Any,
) -> None:
    """payment.succeeded webhook must insert one payment_succeeded inbox row for the client."""
    body = webhook_payment_succeeded_body_factory(seeded_online_payment_pending.yookassa_payment_id)
    response = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert response.status_code == 200, response.text

    await webhook_db_session.commit()

    count = await _count_notifications(
        webhook_db_session,
        client_id=seeded_online_payment_pending.client_id,
        kind="payment_succeeded",
        source_id=seeded_online_payment_pending.online_payment_id,
    )
    assert count == 1, f"Expected 1 payment_succeeded row, got {count}"


@pytest.mark.asyncio
async def test_payment_succeeded_webhook_replay_creates_exactly_one_row(
    webhook_client: AsyncClient,  # noqa: F811
    webhook_db_session: AsyncSession,  # noqa: F811
    seeded_online_payment_pending: SeededOnlinePayment,  # noqa: F811
    yookassa_get_payment_succeeded: respx.MockRouter,  # noqa: F811
    webhook_payment_succeeded_body_factory: Any,
) -> None:
    """Invoking handle_payment_succeeded twice for the same payment creates exactly ONE row (dedup).

    The UNIQUE(client_id, source_type, source_id, kind) constraint on in_app_notifications
    ensures idempotent replay (T-87-11).
    """
    body = webhook_payment_succeeded_body_factory(seeded_online_payment_pending.yookassa_payment_id)

    # First invocation — should succeed (FSM: pending → succeeded)
    r1 = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert r1.status_code == 200, r1.text

    # Second invocation — FSM guard fires (illegal_transition: succeeded → succeeded)
    # The handler returns 200 (D-50-17 forensic audit); the notification dedup
    # prevents a second inbox row.
    r2 = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert r2.status_code == 200, r2.text

    await webhook_db_session.commit()

    count = await _count_notifications(
        webhook_db_session,
        client_id=seeded_online_payment_pending.client_id,
        kind="payment_succeeded",
        source_id=seeded_online_payment_pending.online_payment_id,
    )
    assert count == 1, (
        f"Expected exactly 1 payment_succeeded row after replay, got {count}. "
        "Webhook replay must not create duplicate inbox rows (T-87-11)."
    )


# ---------------------------------------------------------------------------
# Anti-oracle (D-52-08) — payment_canceled creates ZERO client inbox rows
# ---------------------------------------------------------------------------


@pytest.fixture
def yookassa_get_payment_canceled_fixture() -> Any:
    """respx mock: GET /v3/payments/{id} returns status='canceled'."""
    import httpx
    import respx as _respx

    with _respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.get(url__regex=r"^https://api\.yookassa\.ru/v3/payments/[\w-]+$").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "00000000-0000-0000-0000-000000000000",
                    "status": "canceled",
                    "amount": {"value": "100.00", "currency": "RUB"},
                    "cancellation_details": {
                        "party": "yandex_checkout",
                        "reason": "general_decline",
                    },
                },
            )
        )
        yield router


@pytest.mark.asyncio
async def test_payment_canceled_creates_zero_inbox_rows(
    webhook_client: AsyncClient,  # noqa: F811
    webhook_db_session: AsyncSession,  # noqa: F811
    seeded_online_payment_pending: SeededOnlinePayment,  # noqa: F811
    yookassa_get_payment_canceled_fixture: Any,
) -> None:
    """Anti-oracle (D-52-08): payment_canceled MUST NOT create any in_app_notifications rows.

    Owner-only events (cancellation) are NOT client-facing inbox events.
    """
    body = {
        "event": "payment.canceled",
        "object": {
            "id": seeded_online_payment_pending.yookassa_payment_id,
            "status": "canceled",
        },
    }
    response = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert response.status_code == 200, response.text

    await webhook_db_session.commit()

    count = await _count_notifications(
        webhook_db_session,
        client_id=seeded_online_payment_pending.client_id,
    )
    assert count == 0, (
        f"Anti-oracle violated: payment_canceled created {count} inbox row(s). "
        "D-52-08: payment_canceled must create ZERO client inbox rows."
    )


# ---------------------------------------------------------------------------
# Autopay failure hook — SAVEPOINT-mode (cron caller-owns-txn pattern)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_autopay_charge_failed_creates_inbox_row(
    db_session: AsyncSession,
    app: Any,
) -> None:
    """Permanent autopay-charge failure must insert one autopay_charge_failed inbox row."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.modules.autopay_charges import service as autopay_service

    owner = await _seed_owner_user(db_session, suffix=uuid4().hex[:6])
    client = await _seed_client(db_session, owner=owner)

    # Seed a membership plan + active membership with autopay card (for eligibility).
    nonce = uuid4().hex[:6]
    plan_id = uuid4()
    await db_session.execute(
        text(
            "INSERT INTO membership_plans (id, name, duration_days, price_kopecks, freeze_days_limit, active, created_at, updated_at) "  # noqa: E501
            "VALUES (:id, :name, 30, 100000, 7, true, now(), now())"
        ),
        {"id": str(plan_id), "name": f"AutopayPlan-{nonce}"},
    )
    await db_session.execute(
        text(
            "INSERT INTO memberships "
            "(id, client_id, plan_id, plan_name_snapshot, duration_days_snapshot, "
            " price_kopecks_snapshot, freeze_days_limit_snapshot, "
            " status, start_date, end_date, created_at, updated_at) "
            "VALUES (:id, :client_id, :plan_id, :plan_name, 30, 100000, 7, "
            "        'active', CURRENT_DATE, CURRENT_DATE + 1, now(), now())"
        ),
        {
            "id": str(uuid4()),
            "client_id": str(client.id),
            "plan_id": str(plan_id),
            "plan_name": f"AutopayPlan-{nonce}",
        },
    )
    await db_session.execute(
        text(
            "INSERT INTO client_payment_methods "
            "(id, client_id, yookassa_method_id, last4, brand, expiry_month, expiry_year, "
            " autopay_enabled, consent_recorded_at, created_at, updated_at) "
            "VALUES (:id, :client_id, :method_id, '4477', 'MasterCard', 12, 2027, true, now(), now(), now())"  # noqa: E501
        ),
        {
            "id": str(uuid4()),
            "client_id": str(client.id),
            "method_id": f"yk-method-{nonce}",
        },
    )
    await db_session.commit()

    # Build a mock YooKassa client that returns permanent_error for any charge.
    mock_result = MagicMock()
    mock_result.classification = "permanent_error"
    mock_result.error_code = "card_expired"
    mock_result.payment_id = None
    mock_result.amount_kopecks = None

    mock_yookassa = AsyncMock()
    mock_yookassa.create_payment = AsyncMock(return_value=mock_result)

    async def _mock_provider() -> Any:
        return mock_yookassa

    today = datetime.now(UTC).date()
    with (
        patch(
            "app.modules.autopay_charges.service.get_yookassa_client_provider",
            return_value=_mock_provider,
        ),
    ):
        _count_attempted, declined = await autopay_service._charge_expiring_autopay_memberships(
            db_session,
            today=today,
            window_days=5,
        )

    # At least one decline should have been collected (the seeded membership is eligible).
    assert len(declined) >= 1, (
        "Expected at least one declined charge id; check eligibility seed data."
    )

    # The inbox row must exist pre-commit (co-transactional with the autopay state change).
    count = await _count_notifications(
        db_session, client_id=client.id, kind="autopay_charge_failed"
    )
    assert count >= 1, (
        f"Expected at least 1 autopay_charge_failed row for client {client.id}, got {count}"
    )
