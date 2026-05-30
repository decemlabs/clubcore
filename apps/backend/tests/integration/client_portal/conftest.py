"""Fixtures for client_portal integration tests (Phase 69 Plan 03).

Provides:
  - stub_client_otp_sender: autouse fixture — replaces real Telegram sender with no-op.
  - redis_clean: flush Redis between tests (rate-limit + session key isolation).
  - seeded_staff: a staff User required for created_by_user_id FK on Client rows.
  - client_a / client_b: two distinct Client rows with deterministic E.164 phones.
  - seeded_owned_data: seeds BOTH client_a and client_b with one of each owned
    resource type so the IDOR sweep has real victim data that must NOT leak:
      membership (active, far-future) + membership_near_expiry (for expiring_soon test)
      booking (upcoming confirmed) via trainer + slot
      visit
      pt_package + pt_session
      payment (positive) + refund (negative, linked via refund_of)

All fixtures use the SAVEPOINT-rolled-back db_session from the root conftest.
Mirrors tests/integration/client_auth/conftest.py discipline.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role
from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.clients.models import Client
from app.modules.memberships.models import Membership, MembershipPlan
from app.modules.payments.models import Payment
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.pt_sessions.models import PtSession
from app.modules.schedule.models import TrainerAvailabilitySlot
from app.modules.trainers.models import Trainer
from app.modules.visits.models import Visit

# Re-export webhook fixtures needed by test_checkout.py (duplicate-webhook test).
# pytest conftest discovery is directory-tree-only; explicit re-import + noqa: F401 is the
# documented clubcore-internal pattern (mirrors online_payments/conftest.py lines 44-53).
from tests.integration.webhook_yookassa.conftest import (  # noqa: F401
    seeded_online_payment_pending,
    webhook_client,
    webhook_db_session,
    webhook_engine,
    webhook_payment_canceled_body,
    webhook_payment_succeeded_body,
)
from tests.integrations.yookassa.conftest import (  # noqa: F401
    yookassa_get_payment_succeeded,
)

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Phone constants — deterministic per test, unique per client
# ---------------------------------------------------------------------------

_CLIENT_A_PHONE = "+79997770001"
_CLIENT_B_PHONE = "+79997770002"


# ---------------------------------------------------------------------------
# Autouse stub — replace real Telegram OTP sender with no-op
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def stub_client_otp_sender(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the real Telegram OTP sender with a no-op stub for all client_portal tests.

    Mirrors tests/integration/client_auth/conftest.py:stub_client_otp_sender.
    Depends on `app` to ensure the lifespan has run register_client_otp_sender
    with the real sender before we replace it.
    """
    _ = app  # ensure lifespan + register_client_otp_sender has run before patch
    from app.modules.client_auth import service as client_auth_service

    async def _noop_sender(chat_id: int, code: str) -> None:
        """No-op: records nothing; makes no network call."""

    monkeypatch.setattr(client_auth_service, "_client_otp_sender", _noop_sender)


# ---------------------------------------------------------------------------
# redis_clean + seeded_staff (mirrors client_auth/conftest.py)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def redis_clean(app: FastAPI) -> Redis:
    """Flush Redis between tests so rate-limit + session keys don't bleed."""
    client: Redis = app.state.redis
    await client.flushdb()
    return client


@pytest_asyncio.fixture
async def seeded_staff(db_session: AsyncSession) -> User:
    """Insert a staff (RECEPTION) user — provides created_by_user_id FK for Client rows."""
    suffix = uuid4().hex[:8]
    user = User(
        email=f"staff-portal-test+{suffix}@example.com",
        password_hash=await hash_password("test-staff-pw-secure-123"),
        role=Role.RECEPTION,
        full_name="Test Staff Portal",
    )
    db_session.add(user)
    await db_session.commit()
    return user


# ---------------------------------------------------------------------------
# Client A + Client B
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client_a(db_session: AsyncSession, seeded_staff: User) -> Client:
    """First linked client — party A in the IDOR parametrize sweep."""
    client = Client(
        first_name="Portal",
        last_name=f"ClientA-{uuid4().hex[:6]}",
        phone=_CLIENT_A_PHONE,
        telegram_user_id=777_000_001,
        created_by_user_id=seeded_staff.id,
    )
    db_session.add(client)
    await db_session.commit()
    return client


@pytest_asyncio.fixture
async def client_b(db_session: AsyncSession, seeded_staff: User) -> Client:
    """Second linked client — party B in the IDOR parametrize sweep."""
    client = Client(
        first_name="Portal",
        last_name=f"ClientB-{uuid4().hex[:6]}",
        phone=_CLIENT_B_PHONE,
        telegram_user_id=777_000_002,
        created_by_user_id=seeded_staff.id,
    )
    db_session.add(client)
    await db_session.commit()
    return client


# ---------------------------------------------------------------------------
# Owned-data dataclass returned by seeded_owned_data
# ---------------------------------------------------------------------------


@dataclass
class ClientOwnedData:
    """IDs of owned resources seeded for one client — used in sweep assertions."""

    client_id: UUID
    membership_id: UUID
    membership_near_expiry_id: UUID
    visit_id: UUID
    pt_package_id: UUID
    pt_session_id: UUID
    payment_id: UUID
    refund_id: UUID


@dataclass
class SeededOwnedData:
    """Paired owned data for both clients A and B."""

    a: ClientOwnedData
    b: ClientOwnedData


# ---------------------------------------------------------------------------
# Helper: seed all owned resource types for one client
# ---------------------------------------------------------------------------


async def _seed_client_owned_data(
    db_session: AsyncSession,
    client: Client,
    staff: User,
    phone_index: int,  # 1 for A, 2 for B — keeps gym_date unique per client
) -> ClientOwnedData:
    """Seed one of each owned resource type for the given client.

    Returns IDs of each seeded object for use in sweep assertions.
    Phone-index offsets gym_date so the visits UNIQUE (client_id, gym_date)
    constraint isn't an issue across clients sharing a test DB snapshot.
    """
    now = datetime.now(tz=UTC)
    today_offset = timedelta(days=phone_index)  # distinct date per client

    # ------------------------------------------------------------------
    # 1. MembershipPlan (catalog item — shared but needs to exist)
    # ------------------------------------------------------------------
    suffix = uuid4().hex[:6]
    plan = MembershipPlan(
        name=f"Test Plan {suffix}",
        duration_days=30,
        price_kopecks=100_000,
        freeze_days_limit=7,
        active=True,
    )
    db_session.add(plan)
    await db_session.flush()

    # ------------------------------------------------------------------
    # 2. Active Membership (far future — expiring_soon=False)
    # ------------------------------------------------------------------
    far_end = (now + timedelta(days=60)).date()
    membership = Membership(
        client_id=client.id,
        plan_id=plan.id,
        plan_name_snapshot=plan.name,
        duration_days_snapshot=plan.duration_days,
        price_kopecks_snapshot=plan.price_kopecks,
        freeze_days_limit_snapshot=plan.freeze_days_limit,
        start_date=(now - timedelta(days=5)).date(),
        end_date=far_end,
        status="active",
    )
    db_session.add(membership)
    await db_session.flush()

    # ------------------------------------------------------------------
    # 3. Near-expiry Membership (within 7 days — expiring_soon=True)
    # ------------------------------------------------------------------
    near_plan = MembershipPlan(
        name=f"Near Plan {suffix}",
        duration_days=30,
        price_kopecks=50_000,
        freeze_days_limit=5,
        active=True,
    )
    db_session.add(near_plan)
    await db_session.flush()

    near_end = (now + timedelta(days=3)).date()
    membership_near = Membership(
        client_id=client.id,
        plan_id=near_plan.id,
        plan_name_snapshot=near_plan.name,
        duration_days_snapshot=near_plan.duration_days,
        price_kopecks_snapshot=near_plan.price_kopecks,
        freeze_days_limit_snapshot=near_plan.freeze_days_limit,
        start_date=(now - timedelta(days=27)).date(),
        end_date=near_end,
        # Use 'frozen' status so the fetch_client_membership query (status='active')
        # skips this and returns the far-future one as the primary membership.
        # The near-expiry test will assert separately via service function.
        status="frozen",
    )
    db_session.add(membership_near)
    await db_session.flush()

    # ------------------------------------------------------------------
    # 4. Trainer (needed for slot + booking + pt_session)
    # ------------------------------------------------------------------
    trainer_suffix = uuid4().hex[:6]
    trainer = Trainer(
        full_name=f"Trainer {trainer_suffix}",
        is_active=True,
    )
    db_session.add(trainer)
    await db_session.flush()

    # ------------------------------------------------------------------
    # 5. TrainerAvailabilitySlot (upcoming — for booking)
    # ------------------------------------------------------------------
    future_time = now + timedelta(days=2) + today_offset
    slot = TrainerAvailabilitySlot(
        trainer_id=trainer.id,
        start_time=future_time,
        end_time=future_time + timedelta(hours=1),
        status="booked",  # booked since we create a booking below
    )
    db_session.add(slot)
    await db_session.flush()

    # ------------------------------------------------------------------
    # 6. PtPackagePlan (catalog)
    # ------------------------------------------------------------------
    pkg_plan = PtPackagePlan(
        name=f"PT Plan {suffix}",
        session_count=10,
        price_kopecks=50_000,
    )
    db_session.add(pkg_plan)
    await db_session.flush()

    # ------------------------------------------------------------------
    # 7. PtPackage (owned by client) — status='exhausted' to avoid
    #    partial UNIQUE conflict if both clients create 'active' packages
    # ------------------------------------------------------------------
    pt_package = PtPackage(
        client_id=client.id,
        plan_id=pkg_plan.id,
        plan_name_snapshot=pkg_plan.name,
        session_count_snapshot=pkg_plan.session_count,
        price_kopecks_snapshot=pkg_plan.price_kopecks,
        sessions_remaining=0,
        status="exhausted",
        start_date=(now - timedelta(days=30)).date(),
    )
    db_session.add(pt_package)
    await db_session.flush()

    # ------------------------------------------------------------------
    # 8. Booking (upcoming confirmed — refs slot + pt_package)
    # ------------------------------------------------------------------
    from app.modules.bookings.models import Booking

    booking = Booking(
        slot_id=slot.id,
        client_id=client.id,
        pt_package_id=pt_package.id,
        status="confirmed",
    )
    db_session.add(booking)
    await db_session.flush()

    # ------------------------------------------------------------------
    # 9. Visit (historical — unique gym_date per client via offset)
    # ------------------------------------------------------------------
    checked_in_at = now - timedelta(days=10) + today_offset
    visit = Visit(
        client_id=client.id,
        membership_id=membership.id,
        checked_in_at=checked_in_at,
        channel="reception",
    )
    db_session.add(visit)
    await db_session.flush()

    # ------------------------------------------------------------------
    # 10. PtSession (owned via pt_package.client_id — CHIST-02 chain)
    # ------------------------------------------------------------------
    pt_session = PtSession(
        pt_package_id=pt_package.id,
        trainer_id=trainer.id,
        client_id=client.id,
        performed_at=now - timedelta(days=5),
        performed_by_user_id=staff.id,
        trainer_name_snapshot=trainer.full_name,
    )
    db_session.add(pt_session)
    await db_session.flush()

    # ------------------------------------------------------------------
    # 11. Payment (positive — membership purchase)
    # ------------------------------------------------------------------
    payment = Payment(
        subject_kind="membership",
        subject_id=membership.id,
        amount_kopecks=100_000,
        method="cash",
        received_by_user_id=staff.id,
    )
    db_session.add(payment)
    await db_session.flush()

    # ------------------------------------------------------------------
    # 12. Refund (negative — linked via refund_of — CHIST-03)
    # ------------------------------------------------------------------
    refund = Payment(
        subject_kind="refund",
        subject_id=payment.id,
        amount_kopecks=-50_000,
        method="cash",
        received_by_user_id=staff.id,
        refund_of=payment.id,
    )
    db_session.add(refund)
    await db_session.commit()

    return ClientOwnedData(
        client_id=client.id,
        membership_id=membership.id,
        membership_near_expiry_id=membership_near.id,
        visit_id=visit.id,
        pt_package_id=pt_package.id,
        pt_session_id=pt_session.id,
        payment_id=payment.id,
        refund_id=refund.id,
    )


# ---------------------------------------------------------------------------
# seeded_owned_data: both clients A and B seeded with all resource types
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seeded_owned_data(
    db_session: AsyncSession,
    client_a: Client,
    client_b: Client,
    seeded_staff: User,
) -> SeededOwnedData:
    """Seed A and B each with: membership, booking, visit, pt_package+pt_session,
    payment+refund. Returns structured IDs for sweep assertions.

    Victim data seeded for both clients ensures the IDOR sweep is never
    vacuously green (T-69-11 hollow-gate mitigation).
    """
    data_a = await _seed_client_owned_data(db_session, client_a, seeded_staff, phone_index=1)
    data_b = await _seed_client_owned_data(db_session, client_b, seeded_staff, phone_index=2)
    return SeededOwnedData(a=data_a, b=data_b)
