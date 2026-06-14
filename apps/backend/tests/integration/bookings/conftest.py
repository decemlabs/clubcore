"""Shared fixtures for bookings integration tests (Phase 38 plans 38-02 / 38-03).

Mirrors `tests/integration/schedule/conftest.py` with the role-specific
email constants swapped (``book-*`` prefix) so bookings tests can run in
parallel with schedule + pt_sessions tests without colliding on the auth
fixtures' seeded emails.

Includes:
  - ``redis_clean`` / ``seeded_owner`` / ``seeded_reception`` /
    ``authed_client_owner`` / ``authed_client_reception`` / ``anon_client``
    standard auth fixtures.
  - ``make_trainer`` / ``make_client`` / ``make_pt_package_plan`` /
    ``make_pt_package`` / ``make_slot`` factories for the service-layer
    create-booking integration test (plan 38-02 Task 3).
  - Phase 39 NOTIFY-03/04 (plan 39-02 Task 2): ``fake_bot``,
    ``sender_stub``, ``notifications_session_factory`` ported from
    ``tests/integration/notifications/conftest.py``, plus
    ``make_linked_client`` / ``make_unlinked_client`` /
    ``make_active_trainer`` / ``make_future_slot`` / ``make_active_pt_package``
    / ``make_confirmed_booking`` factories tailored for the DM-dispatch
    integration tests.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
import sqlalchemy as sa
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import Role
from app.core.redis import get_redis
from app.core.security import hash_password
from app.integrations.telegram.sender import SendResult
from app.modules.auth.models import User
from app.modules.bookings.models import Booking
from app.modules.clients.models import Client
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.schedule.models import TrainerAvailabilitySlot
from app.modules.trainers.models import Trainer

OWNER_EMAIL = "book-owner@example.com"
OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal (>=12 chars)
RECEPTION_EMAIL = "book-reception@example.com"
RECEPTION_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal

# Deterministic singleton PKs from migration 0071_seed_settings.
_BOOKING_CONFIG_ID = "00000000-0000-0000-0000-000000000003"
_WORKING_HOURS_CONFIG_ID = "00000000-0000-0000-0000-000000000004"

# All-day schedule for all 7 weekdays — used by permissive booking config reset.
# day_of_week: 0=Monday … 6=Sunday (CR-01 fix: 0-based, matches seed/frontend convention).
_ALL_DAYS_OPEN = [
    {"day_of_week": dow, "open_time": "00:00", "close_time": "23:59"}
    for dow in range(0, 7)
]


@pytest_asyncio.fixture(autouse=True)
async def permissive_booking_config(db_session: AsyncSession) -> None:
    """Reset booking_config and working_hours_config to permissive values before each test.

    Phase 108 Plan 03 added enforcement guards in bookings/service.py that read
    booking_config and working_hours_config from the DB. Tests that exercise
    cancel/reschedule/list behavior seed bookings with arbitrary slot timings
    (including slots close in time or outside normal working hours); they break
    when the seeded config values from migration 0071 enforce a 60-minute cutoff
    or Mon-Fri working hours.

    This autouse fixture resets to:
      booking_ahead_days=365  (allow up to a year ahead)
      cutoff_minutes=0        (no cutoff — any future slot accepted)
      cancel_window_hours=24  (preserves migration 0071 default — cancel tests depend on this)
      working_hours: all 7 days 00:00–23:59 (never blocked by schedule)
      closures: [] (no closure dates)

    Tests in test_booking_settings_enforcement.py override these values
    explicitly within each test body and restore them on teardown
    (their transactions roll back anyway).
    """
    # Reset booking_config to permissive values.
    await db_session.execute(
        sa.text(  # noqa: TABLE_REF
            "UPDATE booking_config "
            "SET booking_ahead_days = :ahead, cutoff_minutes = :cutoff, "
            "    cancel_window_hours = :cancel_h "
            "WHERE id = CAST(:id AS uuid)"
        ),
        {
            "ahead": 365,
            "cutoff": 0,
            "cancel_h": 24,  # preserve migration 0071 default — cancel window tests depend on 24h
            "id": _BOOKING_CONFIG_ID,
        },
    )
    # Reset working_hours_config to all-day open (no schedule or closure blocks).
    await db_session.execute(
        sa.text(  # noqa: TABLE_REF
            "UPDATE working_hours_config "
            "SET schedule = CAST(:schedule AS jsonb), closures = CAST(:closures AS jsonb) "
            "WHERE id = CAST(:id AS uuid)"
        ),
        {
            "schedule": json.dumps(_ALL_DAYS_OPEN),
            "closures": json.dumps([]),
            "id": _WORKING_HOURS_CONFIG_ID,
        },
    )


@pytest_asyncio.fixture
async def redis_clean(app: FastAPI) -> Redis:
    """Flush Redis between tests so rate-limit + idempotency keys don't bleed."""
    client: Redis = app.state.redis
    await client.flushdb()
    return client


async def _seed_user(
    db_session: AsyncSession,
    *,
    role: Role,
    email: str,
    password: str,
    full_name: str,
) -> User:
    user = User(
        email=email,
        password_hash=await hash_password(password),
        role=role,
        full_name=full_name,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _login(client: AsyncClient, *, email: str, password: str) -> None:
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text


@pytest_asyncio.fixture
async def seeded_owner(
    db_session: AsyncSession,
    redis_clean: Redis,
) -> User:
    return await _seed_user(
        db_session,
        role=Role.OWNER,
        email=OWNER_EMAIL,
        password=OWNER_PASSWORD,
        full_name="Bookings Owner",
    )


@pytest_asyncio.fixture
async def seeded_reception(
    db_session: AsyncSession,
    redis_clean: Redis,
) -> User:
    return await _seed_user(
        db_session,
        role=Role.RECEPTION,
        email=RECEPTION_EMAIL,
        password=RECEPTION_PASSWORD,
        full_name="Bookings Reception",
    )


@pytest_asyncio.fixture
async def _client_app_overrides(
    app: FastAPI,
    db_session: AsyncSession,
) -> AsyncIterator[FastAPI]:
    """Install dependency overrides on `app` so route handlers see the
    SAVEPOINT-rolled session and the lifespan-bound Redis singleton.
    """

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    def _override_get_redis() -> Any:
        return app.state.redis

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis
    try:
        yield app
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authed_client_owner(
    _client_app_overrides: FastAPI,
    seeded_owner: User,
) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=_client_app_overrides)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, email=OWNER_EMAIL, password=OWNER_PASSWORD)
        yield client


@pytest_asyncio.fixture
async def authed_client_reception(
    _client_app_overrides: FastAPI,
    seeded_reception: User,
) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=_client_app_overrides)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, email=RECEPTION_EMAIL, password=RECEPTION_PASSWORD)
        yield client


@pytest_asyncio.fixture
async def anon_client(
    _client_app_overrides: FastAPI,
) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=_client_app_overrides)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


# ---------------------------------------------------------------------------
# DB-direct factories (Task 3 consumers).
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_trainer(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[Trainer]]:
    """Insert a Trainer row directly via the SAVEPOINT-mode session."""
    _counter = {"i": 0}

    async def _make(
        *,
        full_name: str | None = None,
        is_active: bool = True,
        phone: str | None = None,
    ) -> Trainer:
        _counter["i"] += 1
        trainer = Trainer(
            full_name=full_name or f"BookTrainer-{_counter['i']}-{uuid4().hex[:4]}",
            phone=phone,
            is_active=is_active,
        )
        db_session.add(trainer)
        await db_session.commit()
        await db_session.refresh(trainer)
        return trainer

    return _make


@pytest_asyncio.fixture
async def make_client(
    db_session: AsyncSession,
    seeded_owner: User,
) -> Callable[..., Awaitable[Client]]:
    """Insert a Client row directly via the SAVEPOINT-mode session."""
    _counter = {"i": 0}

    async def _make(
        *,
        last_name: str = "Петров",
        first_name: str = "Пётр",
        phone: str | None = None,
    ) -> Client:
        _counter["i"] += 1
        client_obj = Client(
            last_name=last_name,
            first_name=first_name,
            phone=phone or f"+79059{_counter['i']:06d}",
            created_by_user_id=seeded_owner.id,
        )
        db_session.add(client_obj)
        await db_session.commit()
        await db_session.refresh(client_obj)
        return client_obj

    return _make


@pytest_asyncio.fixture
async def make_pt_package_plan(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[PtPackagePlan]]:
    _counter = {"i": 0}

    async def _make(
        *,
        name: str | None = None,
        session_count: int = 10,
        price_kopecks: int = 500000,
        validity_days: int | None = 90,
    ) -> PtPackagePlan:
        _counter["i"] += 1
        plan = PtPackagePlan(
            name=name or f"BookPlan-{_counter['i']}-{uuid4().hex[:4]}",
            session_count=session_count,
            price_kopecks=price_kopecks,
            validity_days=validity_days,
        )
        db_session.add(plan)
        await db_session.commit()
        await db_session.refresh(plan)
        return plan

    return _make


@pytest_asyncio.fixture
async def make_pt_package(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[PtPackage]]:
    """Insert a PtPackage instance directly (bypasses HTTP sale flow + audit)."""

    async def _make(
        *,
        client_id: UUID,
        plan: PtPackagePlan,
        status: str = "active",
        sessions_remaining: int | None = None,
        start_date: Any = None,
        end_date: Any = None,
    ) -> PtPackage:
        today = start_date or datetime.now(tz=UTC).date()
        if end_date is None and plan.validity_days is not None:
            end = today + timedelta(days=plan.validity_days - 1)
        else:
            end = end_date
        sessions = sessions_remaining if sessions_remaining is not None else plan.session_count
        pt_package = PtPackage(
            client_id=client_id,
            plan_id=plan.id,
            plan_name_snapshot=plan.name,
            session_count_snapshot=plan.session_count,
            price_kopecks_snapshot=plan.price_kopecks,
            validity_days_snapshot=plan.validity_days,
            sessions_remaining=sessions,
            status=status,
            start_date=today,
            end_date=end,
        )
        db_session.add(pt_package)
        await db_session.commit()
        await db_session.refresh(pt_package)
        return pt_package

    return _make


@pytest_asyncio.fixture
async def make_slot(
    db_session: AsyncSession,
    seeded_owner: User,
) -> Callable[..., Awaitable[TrainerAvailabilitySlot]]:
    """Insert a TrainerAvailabilitySlot directly (bypasses HTTP publish flow)."""
    _counter = {"i": 0}

    async def _make(
        *,
        trainer_id: UUID,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        status: str = "active",
        created_by_user_id: UUID | None = None,
    ) -> TrainerAvailabilitySlot:
        _counter["i"] += 1
        start = start_time or (datetime.now(tz=UTC) + timedelta(hours=2 + _counter["i"]))
        end = end_time or (start + timedelta(hours=1))
        slot = TrainerAvailabilitySlot(
            trainer_id=trainer_id,
            start_time=start,
            end_time=end,
            status=status,
            created_by_user_id=created_by_user_id or seeded_owner.id,
        )
        db_session.add(slot)
        await db_session.commit()
        await db_session.refresh(slot)
        return slot

    return _make


# ---------------------------------------------------------------------------
# Phase 39 NOTIFY-03/04 (plan 39-02 Task 2) — Telegram DM dispatch test
# fixtures. Mirror the patterns in tests/integration/notifications/conftest.py
# (D-39-19 — sender-stub at module level, NOT bot-level).
# ---------------------------------------------------------------------------


@dataclass
class _RecordedCall:
    """One captured invocation of ``send_text_dm`` (Phase 39 plan 39-02)."""

    bot: object
    chat_id: int
    text: str


@dataclass
class _SenderStubState:
    """Mutable per-call state controlling the sender_stub fixture.

    Usage::

        sender_module, sender_state = sender_stub
        sender_state.queue(SendResult(ok=False, blocked=True))
        await service.create_booking(...)
        assert len(sender_state.calls) == 1
    """

    results_queue: list[SendResult] = field(default_factory=list)
    default_result: SendResult = field(default_factory=lambda: SendResult(ok=True))
    calls: list[_RecordedCall] = field(default_factory=list)

    def queue(self, *results: SendResult) -> None:
        """Push one or more SendResults that pop off in FIFO order."""
        self.results_queue.extend(results)

    def set_default(self, result: SendResult) -> None:
        """Replace the default result returned once the queue drains."""
        self.default_result = result


def _fake_bot_factory() -> object:
    """Sentinel ``bot=`` arg — the stub never reaches into it (only identity)."""
    return object()


fake_bot = pytest.fixture(_fake_bot_factory)


def _sender_stub_factory() -> tuple[SimpleNamespace, _SenderStubState]:
    """Module-typed Telegram sender stub + state-handle (D-39-19 pattern).

    Returns ``(module, state)`` — tests monkeypatch
    ``app.modules.bookings.service.telegram_sender`` to ``module`` (the
    ``SimpleNamespace`` quacks like a ModuleType exposing ``send_text_dm``).
    The state exposes ``.calls`` for assertions and ``.queue(...)`` to push
    custom SendResults before the next send.
    """
    state = _SenderStubState()

    async def send_text_dm(bot: object, chat_id: int, text: str) -> SendResult:
        state.calls.append(_RecordedCall(bot=bot, chat_id=chat_id, text=text))
        if state.results_queue:
            return state.results_queue.pop(0)
        return state.default_result

    module = SimpleNamespace(send_text_dm=send_text_dm)
    return module, state


sender_stub = pytest.fixture(_sender_stub_factory)


# ---------------------------------------------------------------------------
# SAVEPOINT-mode session factory wrapper (mirrors the notifications conftest)
# — optional in plan 39-02 (the sync-dispatch path doesn't use it) but kept
# here so plan 39-04's cron-helper tests can land without re-porting.
# ---------------------------------------------------------------------------


class _SessionContext:
    """Async context manager yielding the shared SAVEPOINT-mode session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *args: Any) -> None:
        # Teardown belongs to the outer db_session fixture (SAVEPOINT-roll
        # at end of test). Do NOT close the session here.
        return None


class _SavepointSessionmaker:
    """Callable returning ``_SessionContext`` — quacks like ``async_sessionmaker``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def __call__(self) -> _SessionContext:
        return _SessionContext(self._session)


@pytest_asyncio.fixture
async def notifications_session_factory(
    db_session: AsyncSession,
) -> _SavepointSessionmaker:
    """``async_sessionmaker``-shaped factory bound to the SAVEPOINT-mode session."""
    return _SavepointSessionmaker(db_session)


# ---------------------------------------------------------------------------
# Booking-domain factories for the DM-dispatch integration tests. These are
# thin wrappers around the existing Phase 38 ``make_*`` factories with
# defaults tuned for the DM happy path (linked client, future slot, active
# package).
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_linked_client(
    db_session: AsyncSession,
    seeded_owner: User,
) -> Callable[..., Awaitable[Client]]:
    """Insert a Client with ``telegram_user_id`` set (DM happy path).

    Per-call counter ensures unique phone + telegram_user_id across
    multiple invocations in the same test.
    """
    _counter = {"i": 0}

    async def _make(
        *,
        telegram_user_id: int = 100001,
        first_name: str = "Иван",
        last_name: str = "Петров",
    ) -> Client:
        _counter["i"] += 1
        client = Client(
            last_name=last_name,
            first_name=first_name,
            phone=f"+79051{_counter['i']:06d}",
            telegram_user_id=telegram_user_id + _counter["i"] - 1,
            created_by_user_id=seeded_owner.id,
        )
        db_session.add(client)
        await db_session.commit()
        await db_session.refresh(client)
        return client

    return _make


@pytest_asyncio.fixture
async def make_unlinked_client(
    db_session: AsyncSession,
    seeded_owner: User,
) -> Callable[..., Awaitable[Client]]:
    """Insert a Client with ``telegram_user_id IS NULL`` (DM-skip path)."""
    _counter = {"i": 0}

    async def _make(
        *,
        first_name: str = "Анна",
        last_name: str = "Сидорова",
    ) -> Client:
        _counter["i"] += 1
        client = Client(
            last_name=last_name,
            first_name=first_name,
            phone=f"+79052{_counter['i']:06d}",
            telegram_user_id=None,
            created_by_user_id=seeded_owner.id,
        )
        db_session.add(client)
        await db_session.commit()
        await db_session.refresh(client)
        return client

    return _make


@pytest_asyncio.fixture
async def make_active_trainer(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[Trainer]]:
    """Insert an active Trainer with a known display name (used in DM body)."""
    _counter = {"i": 0}

    async def _make(*, full_name: str = "Пётр Сидоров") -> Trainer:
        _counter["i"] += 1
        trainer = Trainer(
            full_name=full_name,
            phone=None,
            is_active=True,
        )
        db_session.add(trainer)
        await db_session.commit()
        await db_session.refresh(trainer)
        return trainer

    return _make


@pytest_asyncio.fixture
async def make_future_slot(
    db_session: AsyncSession,
    seeded_owner: User,
) -> Callable[..., Awaitable[TrainerAvailabilitySlot]]:
    """Insert an active TrainerAvailabilitySlot (default +25h in the future).

    Negative ``start_offset`` produces a past slot (used by the no-show cron
    tests in plan 39-03). The factory inserts directly via ORM — it does NOT
    call ``schedule.service.publish_slot``, so the Phase 38 future-only
    publish-time guard is bypassed by design. The resulting slot row is NOT
    validated by service-layer rules; the only DB-level invariants enforced
    are ``status IN ('active','booked','cancelled')`` and
    ``end_time > start_time`` (CHECK constraints from migration 0016).
    Callers that pass a negative offset are responsible for understanding
    they are crafting a cron-test fixture, not exercising the publish API.
    """
    _counter = {"i": 0}

    async def _make(
        *,
        trainer: Trainer,
        start_offset: timedelta = timedelta(hours=25),
        duration: timedelta = timedelta(hours=1),
    ) -> TrainerAvailabilitySlot:
        _counter["i"] += 1
        start = datetime.now(tz=UTC) + start_offset + timedelta(minutes=_counter["i"])
        slot = TrainerAvailabilitySlot(
            trainer_id=trainer.id,
            start_time=start,
            end_time=start + duration,
            status="active",
            created_by_user_id=seeded_owner.id,
        )
        db_session.add(slot)
        await db_session.commit()
        await db_session.refresh(slot)
        return slot

    return _make


@pytest_asyncio.fixture
async def make_active_pt_package(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[PtPackage]]:
    """Insert an active PtPackage (with an auto-generated plan snapshot)."""
    _counter = {"i": 0}

    async def _make(
        *,
        client: Client,
        trainer: Trainer | None = None,
        sessions_remaining: int = 5,
    ) -> PtPackage:
        _counter["i"] += 1
        plan = PtPackagePlan(
            name=f"DMPlan-{_counter['i']}-{uuid4().hex[:4]}",
            session_count=10,
            price_kopecks=500000,
            validity_days=90,
        )
        db_session.add(plan)
        await db_session.commit()
        await db_session.refresh(plan)

        today = datetime.now(tz=UTC).date()
        pt_package = PtPackage(
            client_id=client.id,
            plan_id=plan.id,
            plan_name_snapshot=plan.name,
            session_count_snapshot=plan.session_count,
            price_kopecks_snapshot=plan.price_kopecks,
            validity_days_snapshot=plan.validity_days,
            sessions_remaining=sessions_remaining,
            status="active",
            start_date=today,
            end_date=today + timedelta(days=89),
        )
        db_session.add(pt_package)
        await db_session.commit()
        await db_session.refresh(pt_package)
        return pt_package

    return _make


@pytest_asyncio.fixture
async def make_confirmed_booking(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[Booking]]:
    """Insert a confirmed Booking row + flip the linked slot to 'booked'.

    Direct ORM inserts (bypasses HTTP / service-layer audit emits) so the
    cancel-DM tests can craft a starting state without triggering a
    confirmation-DM dispatch along the way.
    """

    async def _make(
        *,
        slot: TrainerAvailabilitySlot,
        client: Client,
        pt_package: PtPackage,
        actor_user_id: UUID,
    ) -> Booking:
        booking = Booking(
            slot_id=slot.id,
            client_id=client.id,
            pt_package_id=pt_package.id,
            created_by_user_id=actor_user_id,
            status="confirmed",
        )
        db_session.add(booking)
        # Flip the slot to 'booked' so the cancel path's FSM gate
        # (booked->cancelled) accepts the transition.
        slot.status = "booked"
        await db_session.commit()
        await db_session.refresh(booking)
        await db_session.refresh(slot)
        return booking

    return _make
