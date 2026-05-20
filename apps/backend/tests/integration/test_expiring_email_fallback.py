"""Phase 45 D-45-02 — expiring email-fallback integration tests.

Exercises the per-tick fanout when Telegram returns ``SendResult.blocked``
AND the candidate has ``client_email IS NOT NULL`` (D-45-01 cross-channel
relax). Three cases lock the cross-channel contract:

  1. ``test_telegram_blocked_with_email_fanouts_to_email`` — primary
     happy path: blocked sender → email-fallback branch fires → one
     ``membership_notifications`` row with ``channel='email'`` + one
     ``audit_log`` row with ``channel='email'`` in payload + one
     ``EmailDispatcher`` invocation with literal ``template_id``.

  2. ``test_telegram_blocked_without_email_skips_fallback`` — the
     fallback branch is gated on ``cand.client_email is not None``;
     a Telegram-only client with NULL email yields zero rows.

  3. ``test_telegram_success_with_email_no_email_fanout`` — when the
     Telegram send succeeds the email branch never runs (Telegram is
     v1.6 primary per D-45-01). One ``channel='telegram'`` row,
     ``channel='telegram'`` payload, zero dispatcher calls.

Mirrors ``tests/integration/notifications/test_idempotency_constraint.py``
shape (notifications conftest fixtures) + ``tests/integration/auth/
test_invitation_accept.py:168-186 sandbox_email_client`` (recording
dispatcher pattern). Lives in ``tests/integration/`` (not the
notifications sub-package) so it does NOT auto-inherit the
notifications/conftest sender stub — we register our own dispatcher
spy explicitly in fixture-scope. Re-uses the notifications conftest
fixtures (``notifications_session_factory``, ``sender_stub``,
``fake_bot``, ``make_plan``, ``make_membership``) by importing the
conftest module at the test path level via the standard pytest
fixture discovery (conftest at ``tests/integration/notifications/``
is NOT auto-inherited up the tree, so we redeclare minimal fixtures
locally).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import dependencies as deps_mod
from app.core.audit_models import AuditLog
from app.core.dependencies import register_email_dispatcher
from app.core.permissions import Role
from app.core.security import hash_password
from app.integrations.telegram import copy as telegram_copy
from app.integrations.telegram.sender import SendResult
from app.modules.auth.models import User
from app.modules.clients.models import Client
from app.modules.memberships import service as memberships_service
from app.modules.memberships.models import Membership, MembershipNotification, MembershipPlan

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Local fixtures — savepoint sessionmaker + sender stub + email recorder.
# Mirror tests/integration/notifications/conftest.py but stay local so the
# test does NOT cross-import from the notifications package conftest (pytest
# auto-discovery does not walk sibling sub-packages).
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
    """Spy satisfying the Phase 41 EmailDispatcher Protocol."""

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
# Factories — owner + clients + plans + memberships. Self-contained so the
# notifications package conftest is not required.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seeded_owner(db_session: AsyncSession) -> User:
    user = User(
        email=f"phase45-fallback-owner-{uuid4().hex[:8]}@example.com",
        password_hash=await hash_password("hunter22hunter22"),
        role=Role.OWNER,
        full_name="Phase 45 Fallback Owner",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def make_client(
    db_session: AsyncSession,
    seeded_owner: User,
) -> Callable[..., Awaitable[UUID]]:
    counter = {"i": 0}

    async def _make(
        *,
        telegram_user_id: int | None = None,
        email: str | None = None,
        last_name: str = "Тестов",
        first_name: str = "Клиент",
    ) -> UUID:
        counter["i"] += 1
        client = Client(
            last_name=last_name,
            first_name=first_name,
            phone=f"+7999280{counter['i']:04d}",
            email=email,
            telegram_user_id=telegram_user_id,
            created_by_user_id=seeded_owner.id,
        )
        db_session.add(client)
        await db_session.commit()
        await db_session.refresh(client)
        return client.id

    return _make


@pytest_asyncio.fixture
async def make_plan(db_session: AsyncSession) -> Callable[..., Awaitable[MembershipPlan]]:
    async def _make(*, name: str = "Phase 45 Fallback Plan") -> MembershipPlan:
        plan = MembershipPlan(
            name=name,
            duration_days=30,
            price_kopecks=250000,
            freeze_days_limit=14,
            active=True,
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
    async def _make(
        *,
        client_id: UUID,
        plan: MembershipPlan,
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
            status="active",
        )
        db_session.add(membership)
        await db_session.commit()
        await db_session.refresh(membership)
        return membership

    return _make


# ---------------------------------------------------------------------------
# Tests — three cases lock the cross-channel fanout contract.
# ---------------------------------------------------------------------------


async def test_telegram_blocked_with_email_fanouts_to_email(
    db_session: AsyncSession,
    session_factory: _SavepointSessionmaker,
    email_recorder: _RecordingEmailDispatcher,
    make_plan: Any,
    make_client: Any,
    make_membership: Any,
) -> None:
    today = date(2026, 6, 1)
    plan = await make_plan()
    client_id = await make_client(
        telegram_user_id=900_001,
        email="fallback-client@example.com",
    )
    m = await make_membership(
        client_id=client_id,
        plan=plan,
        start_date=today - timedelta(days=23),
        end_date=today + timedelta(days=7),
    )

    sender_module, sender_state = _make_sender_stub()
    sender_state.next_result = SendResult(ok=False, blocked=True, error="forbidden")

    count = await memberships_service._send_expiring_notifications(
        session_factory,
        today=today,
        bot=object(),  # type: ignore[arg-type]
        sender=sender_module,
        copy_module=telegram_copy,
    )

    assert count == 1
    assert len(sender_state.calls) == 1
    assert sender_state.calls[0].chat_id == 900_001

    # membership_notifications row — channel='email', telegram_chat_id IS NULL.
    notif_rows = (
        await db_session.execute(
            select(MembershipNotification).where(
                MembershipNotification.membership_id == m.id
            )
        )
    ).scalars().all()
    assert len(notif_rows) == 1
    assert notif_rows[0].kind == "expiring_7d"
    assert notif_rows[0].channel == "email"
    assert notif_rows[0].telegram_chat_id is None

    # audit_log row — channel='email' in payload.
    audits = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "expiring_notification_sent_7d",
                AuditLog.resource_id == m.id,
            )
        )
    ).scalars().all()
    assert len(audits) == 1
    assert audits[0].payload["channel"] == "email"
    assert audits[0].payload["telegram_chat_id"] is None

    # EmailDispatcher recorder — exactly one call with literal template id.
    assert len(email_recorder.calls) == 1
    rec = email_recorder.calls[0]
    assert rec.template_id in {
        "EMAIL_EXPIRING_7D_VARIANT_A",
        "EMAIL_EXPIRING_7D_VARIANT_B",
    }
    assert rec.template_id.startswith("EMAIL_EXPIRING_7D_")
    assert rec.to == "fallback-client@example.com"
    assert rec.audit_correlation_id is not None


async def test_telegram_blocked_without_email_skips_fallback(
    db_session: AsyncSession,
    session_factory: _SavepointSessionmaker,
    email_recorder: _RecordingEmailDispatcher,
    make_plan: Any,
    make_client: Any,
    make_membership: Any,
) -> None:
    today = date(2026, 6, 1)
    plan = await make_plan()
    client_id = await make_client(telegram_user_id=900_002, email=None)
    m = await make_membership(
        client_id=client_id,
        plan=plan,
        start_date=today - timedelta(days=23),
        end_date=today + timedelta(days=7),
    )

    sender_module, sender_state = _make_sender_stub()
    sender_state.next_result = SendResult(ok=False, blocked=True, error="forbidden")

    count = await memberships_service._send_expiring_notifications(
        session_factory,
        today=today,
        bot=object(),  # type: ignore[arg-type]
        sender=sender_module,
        copy_module=telegram_copy,
    )

    assert count == 0, "no email → no fallback"
    assert len(sender_state.calls) == 1, "Telegram still attempted"
    assert len(email_recorder.calls) == 0, "dispatcher must NOT be called"

    notif_rows = (
        await db_session.execute(
            select(MembershipNotification).where(
                MembershipNotification.membership_id == m.id
            )
        )
    ).scalars().all()
    assert notif_rows == []

    audits = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "expiring_notification_sent_7d",
                AuditLog.resource_id == m.id,
            )
        )
    ).scalars().all()
    assert audits == []


async def test_telegram_success_with_email_no_email_fanout(
    db_session: AsyncSession,
    session_factory: _SavepointSessionmaker,
    email_recorder: _RecordingEmailDispatcher,
    make_plan: Any,
    make_client: Any,
    make_membership: Any,
) -> None:
    today = date(2026, 6, 1)
    plan = await make_plan()
    client_id = await make_client(
        telegram_user_id=900_003,
        email="dual-channel-client@example.com",
    )
    m = await make_membership(
        client_id=client_id,
        plan=plan,
        start_date=today - timedelta(days=23),
        end_date=today + timedelta(days=7),
    )

    sender_module, sender_state = _make_sender_stub()
    # Default next_result = SendResult(ok=True).

    count = await memberships_service._send_expiring_notifications(
        session_factory,
        today=today,
        bot=object(),  # type: ignore[arg-type]
        sender=sender_module,
        copy_module=telegram_copy,
    )

    assert count == 1
    assert len(sender_state.calls) == 1
    assert len(email_recorder.calls) == 0, "Telegram success → no email fallback"

    notif_rows = (
        await db_session.execute(
            select(MembershipNotification).where(
                MembershipNotification.membership_id == m.id
            )
        )
    ).scalars().all()
    assert len(notif_rows) == 1
    assert notif_rows[0].channel == "telegram"
    assert notif_rows[0].telegram_chat_id == 900_003

    audits = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "expiring_notification_sent_7d",
                AuditLog.resource_id == m.id,
            )
        )
    ).scalars().all()
    assert len(audits) == 1
    assert audits[0].payload["channel"] == "telegram"
    assert audits[0].payload["telegram_chat_id"] == 900_003
