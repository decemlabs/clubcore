"""Phase 27 notifications integration test fixtures (NTF-TEST-01..03 + structural).

Provides:
- ``fake_bot`` — sentinel object passed as ``bot=`` to the service helper. The real
  bot's ``send_message`` is never reached because ``sender_stub`` short-circuits.
- ``sender_stub`` — a module-typed stub exposing ``send_text_dm(bot, chat_id, text) -> SendResult``.
  Tests configure the stub's return value per scenario (ok / blocked / transient).
- ``notifications_session_factory`` — the ``async_sessionmaker``-shaped callable
  the service helper consumes. Wraps the SAVEPOINT-mode ``db_session`` so the
  helper's per-send write sessions yield the SAME session the test queries
  directly (mirrors ``tests/integration/workers/conftest.py:_SavepointSessionmaker``).
- ``make_client_with_telegram`` — creates a ``Client`` row with
  ``telegram_user_id`` set; auto-seeds an owner User as ``created_by_user_id``.
- ``make_client_no_telegram`` — sibling that leaves ``telegram_user_id`` NULL
  (used for the SELECT-exclusion structural test).

Per D-27-22: tests stub at the ``sender`` module level (NOT at Bot level) — the
sender boundary is the cleanest swap seam (existing Phase 7 / 20 convention).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role
from app.core.security import hash_password
from app.integrations.telegram.sender import SendResult
from app.modules.auth.models import User
from app.modules.clients.models import Client
from app.modules.memberships.models import Membership, MembershipPlan

# ---------------------------------------------------------------------------
# Sender stub — module-typed object exposing send_text_dm + state recorder.
# ---------------------------------------------------------------------------


@dataclass
class _RecordedCall:
    """One captured invocation of ``send_text_dm``."""

    chat_id: int
    text: str


@dataclass
class _SenderStubState:
    """Mutable state the test controls per call.

    Tests typically use:

        sender_module, sender_state = sender_stub
        sender_state.queue(SendResult(ok=False, blocked=True), SendResult(ok=True))
        await service._send_expiring_notifications(..., sender=sender_module, ...)
        assert len(sender_state.calls) == 2

    ``queue`` adds canned results that pop off in FIFO order; once the queue
    drains, ``default_result`` is returned for every subsequent call.
    """

    results_queue: list[SendResult] = field(default_factory=list)
    default_result: SendResult = field(default_factory=lambda: SendResult(ok=True))
    calls: list[_RecordedCall] = field(default_factory=list)

    def queue(self, *results: SendResult) -> None:
        self.results_queue.extend(results)

    def set_default(self, result: SendResult) -> None:
        self.default_result = result


def fake_bot() -> object:
    """Sentinel passed as ``bot=`` — the stub never reaches into it."""
    return object()


# Re-export as a pytest fixture (the function name above keeps the literal
# `^def fake_bot` greppable for the plan acceptance criterion).
fake_bot = pytest.fixture(fake_bot)


def sender_stub() -> tuple[SimpleNamespace, _SenderStubState]:
    """Module-typed stub exposing async ``send_text_dm`` + a state-handle.

    Returns ``(module, state)`` so tests can configure the next response and
    inspect captured calls.
    """
    state = _SenderStubState()

    async def send_text_dm(bot: object, chat_id: int, text: str) -> SendResult:
        state.calls.append(_RecordedCall(chat_id=chat_id, text=text))
        if state.results_queue:
            return state.results_queue.pop(0)
        return state.default_result

    # SimpleNamespace is enough — the helper signature accepts ModuleType but
    # only reads ``.send_text_dm``; SimpleNamespace satisfies that.
    module = SimpleNamespace(send_text_dm=send_text_dm)
    return module, state


sender_stub = pytest.fixture(sender_stub)


# ---------------------------------------------------------------------------
# Session factory — wraps SAVEPOINT-mode db_session so the helper's
# `async with session_factory() as write_session` yields the SAME session the
# test queries directly. Mirrors `tests/integration/workers/conftest.py`.
# ---------------------------------------------------------------------------


class _SessionContext:
    """Async context manager that yields the shared SAVEPOINT-mode session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *args: Any) -> None:
        # Teardown belongs to the outer fixture (db_session rolls back the
        # SAVEPOINT at end of test). Do NOT close the session here.
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
    """``async_sessionmaker``-shaped factory bound to the SAVEPOINT-mode session.

    The service helper ``_send_expiring_notifications`` opens its own per-send
    write sessions via ``async with session_factory() as session``. For tests we
    want every ``async with`` to yield the SAME ``db_session`` the test seeds
    against — otherwise READ COMMITTED isolation hides the seeded data from a
    fresh connection. The wrapper preserves the helper's ``commit()`` calls as
    SAVEPOINT releases (the outer transaction rolls back at teardown).
    """
    return _SavepointSessionmaker(db_session)


# ---------------------------------------------------------------------------
# Client factories — Phase 27 needs telegram_user_id-aware variants.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def _seeded_owner_for_client(db_session: AsyncSession) -> User:
    """A single owner User row (SAVEPOINT-rolled) — FK target for clients.created_by_user_id.

    Phase 27 notifications tests never authenticate; they call the service
    helper directly. We just need a real User row so the
    ``clients.created_by_user_id`` NOT NULL FK is satisfied.
    """
    user = User(
        email="phase27-notifications-owner@example.com",
        password_hash=await hash_password("hunter22hunter22"),
        role=Role.OWNER,
        full_name="Phase 27 Notifications Test Owner",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def make_client_with_telegram(
    db_session: AsyncSession,
    _seeded_owner_for_client: User,
) -> Callable[..., Awaitable[UUID]]:
    """Insert a Client with ``telegram_user_id`` set; return its UUID.

    Per-call counter ensures unique phone + telegram_user_id across multiple
    invocations in the same test (matrix tests need distinct rows).
    """
    counter = {"i": 0}

    async def _make(*, telegram_user_id: int) -> UUID:
        counter["i"] += 1
        client = Client(
            last_name="Тестов",
            first_name="Клиент",
            phone=f"+7999277{counter['i']:04d}",
            telegram_user_id=telegram_user_id,
            created_by_user_id=_seeded_owner_for_client.id,
        )
        db_session.add(client)
        await db_session.commit()
        await db_session.refresh(client)
        return client.id

    return _make


@pytest_asyncio.fixture
async def make_client_no_telegram(
    db_session: AsyncSession,
    _seeded_owner_for_client: User,
) -> Callable[..., Awaitable[UUID]]:
    """Insert a Client WITHOUT ``telegram_user_id`` (NULL) — for SELECT-exclusion test."""
    counter = {"i": 0}

    async def _make() -> UUID:
        counter["i"] += 1
        client = Client(
            last_name="Безтелеги",
            first_name="Клиент",
            phone=f"+7999278{counter['i']:04d}",
            telegram_user_id=None,
            created_by_user_id=_seeded_owner_for_client.id,
        )
        db_session.add(client)
        await db_session.commit()
        await db_session.refresh(client)
        return client.id

    return _make


# ---------------------------------------------------------------------------
# Plan + membership factories — direct ORM inserts via SAVEPOINT-mode session.
# Mirror tests/integration/memberships/conftest.py shape (re-implemented here
# because pytest only auto-discovers conftest.py within the same package).
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_plan(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[MembershipPlan]]:
    """Insert a ``MembershipPlan`` row directly via the SAVEPOINT-mode session."""

    async def _make(
        *,
        name: str = "Базовый",
        duration_days: int = 30,
        price_kopecks: int = 250000,
        freeze_days_limit: int = 14,
        active: bool = True,
    ) -> MembershipPlan:
        plan = MembershipPlan(
            name=name,
            duration_days=duration_days,
            price_kopecks=price_kopecks,
            freeze_days_limit=freeze_days_limit,
            active=active,
        )
        db_session.add(plan)
        await db_session.commit()
        await db_session.refresh(plan)
        return plan

    return _make


@pytest_asyncio.fixture
async def make_membership(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[Membership]]:
    """Insert a ``Membership`` row directly via the SAVEPOINT-mode session.

    ``status``, ``start_date``, and ``end_date`` may be overridden so the
    notifications matrix tests can craft 7d / 3d / 1d / cancelled / expired /
    frozen scenarios without going through the HTTP create-membership flow
    (which emits its own audit row that would skew assertions).
    """

    async def _make(
        *,
        client_id: UUID,
        plan: MembershipPlan,
        status: str = "active",
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> Membership:
        today = start_date or datetime.now(tz=UTC).date()
        end = end_date or (today + timedelta(days=plan.duration_days - 1))
        membership = Membership(
            client_id=client_id,
            plan_id=plan.id,
            plan_name_snapshot=plan.name,
            duration_days_snapshot=plan.duration_days,
            price_kopecks_snapshot=plan.price_kopecks,
            freeze_days_limit_snapshot=plan.freeze_days_limit,
            start_date=today,
            end_date=end,
            status=status,
        )
        db_session.add(membership)
        await db_session.commit()
        await db_session.refresh(membership)
        return membership

    return _make


__all__ = [
    "fake_bot",
    "make_client_no_telegram",
    "make_client_with_telegram",
    "make_membership",
    "make_plan",
    "notifications_session_factory",
    "sender_stub",
]


# Re-export AsyncIterator for typing-only consumers (silences ruff F401 if unused).
_ = AsyncIterator
