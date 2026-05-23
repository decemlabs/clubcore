"""Phase 52 Plan 52-06 — E2E behavioural tests for ``dispatch_payment_notification``.

Covers all 6 ROADMAP Phase 52 success criteria at the observable-behaviour
layer (dual-channel delivery, cross-restart idempotency, channel-skip, owner-alert
routing, unset-log-only, and the payment_canceled FK-safety):

1. ``test_payment_succeeded_dual_channel_then_restart_no_duplicate``   — NOT-01/02/03
2. ``test_refund_succeeded_dual_channel``                              — NOT-01/02
3. ``test_channel_skipped_when_recipient_null``                        — D-52-02
4. ``test_fiscal_failed_routes_owner_alert_and_is_idempotent_across_restart``
   — NOT-04 + NOT-03 (WARNING fix — owner-alert idempotency)
5. ``test_owner_alert_unset_logs_only``                                — D-52-09
6. ``test_payment_canceled_owner_alert_db_claim_no_fk_violation_idempotent``
   — D-52-10 (BLOCKER fix: payment_canceled keys on online_payment_id)

Design notes
------------
- The ``dispatch_payment_notification`` task opens its own sessions via
  ``ctx["sessionmaker"]``; it cannot compose with the SAVEPOINT-wrapped root
  ``db_session``.  Each test uses a REAL-COMMIT engine + TRUNCATE cleanup
  (mirrors the Phase 51 fiscal_receipts conftest pattern — D-13).
- Telegram ``send_text_dm`` is monkey-patched to a recording stub (mirrors
  the root conftest ``stub_telegram_sender`` fixture pattern, but scoped
  locally so we can call the task directly without the app lifespan).
- ``get_email_dispatcher()`` is replaced with a ``_RecordingEmailDispatcher``
  (same pattern as ``tests/integration/test_payment_receipt_email.py``).
- Owner-alert settings are injected via ``monkeypatch.setattr`` on the task
  module's ``get_settings`` because ``app.core.config.get_settings`` is
  ``@lru_cache``'d — env-var patches do not reach the cached instance.
- The payment ledger row's ``subject_id`` must point to a ``memberships`` row
  (not a ``membership_plans`` row) so that ``_resolve_client_row`` can follow
  ``memberships.client_id → clients`` for the client kinds.
- Tests MUST NOT hit real Telegram or SMTP (no real network per CLAUDE.md —
  the task is invoked directly with external-send functions stubbed).
"""

from __future__ import annotations

import datetime
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.security import hash_password
from app.modules.clients.models import Client
from app.modules.memberships.models import Membership, MembershipPlan
from app.modules.online_payments.constants import (
    CONFIRMATION_TYPE_REDIRECT,
    STATUS_CANCELED,
    STATUS_SUCCEEDED,
)
from app.modules.online_payments.models import OnlinePayment, PaymentNotification
from app.modules.online_payments.tasks import dispatch_payment_notification
from app.modules.payments.models import Payment

# ---------------------------------------------------------------------------
# Tables to TRUNCATE after every test — must include ``payment_notifications``
# (Phase 52) in addition to the fiscal_receipts conftest set.
# ---------------------------------------------------------------------------

_TRUNCATE_TABLES = (
    "payment_notifications",
    "audit_log",
    "fiscal_receipts",
    "payments",
    "memberships",
    "pt_packages",
    "online_payments",
    "membership_plans",
    "pt_package_plans",
    "clients",
    "users",
)


# ---------------------------------------------------------------------------
# Recording stubs for external sends
# ---------------------------------------------------------------------------


@dataclass
class _TelegramRecord:
    chat_id: int
    text: str


@dataclass
class _EmailRecord:
    template_id: str
    to: str
    kwargs: dict[str, Any] = field(default_factory=dict)


class _RecordingEmailDispatcher:
    """Records ``get_email_dispatcher()`` calls without sending real email."""

    def __init__(self) -> None:
        self.calls: list[_EmailRecord] = []

    async def __call__(
        self,
        *,
        template_id: str,
        to: str,
        audit_correlation_id: Any,
        **template_vars: Any,
    ) -> None:
        self.calls.append(_EmailRecord(template_id=template_id, to=to, kwargs=template_vars))


# ---------------------------------------------------------------------------
# Settings stub (bypasses @lru_cache on get_settings)
# ---------------------------------------------------------------------------


class _SettingsStub:
    """Minimal settings stub for the dispatch task.

    ``get_settings()`` is ``@lru_cache``'d, so ``monkeypatch.setenv`` does NOT
    reach the cached instance. Tests that need owner-alert settings inject this
    stub via ``monkeypatch.setattr`` on the task module's ``get_settings``.
    """

    def __init__(
        self,
        *,
        owner_alert_telegram_chat_id: int | None = None,
        owner_alert_email: str | None = None,
    ) -> None:
        real = get_settings()
        self.telegram_bot_token = real.telegram_bot_token
        self.owner_alert_telegram_chat_id = owner_alert_telegram_chat_id
        self.owner_alert_email = owner_alert_email


# ---------------------------------------------------------------------------
# Real-commit engine fixture (mirrors fiscal_receipts conftest D-13 pattern)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def notif_engine() -> AsyncIterator[Any]:
    """Real-commit AsyncEngine; TRUNCATEs all touched tables on teardown."""
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)
    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text(f"TRUNCATE {', '.join(_TRUNCATE_TABLES)} RESTART IDENTITY CASCADE")
            )
        await engine.dispose()


@pytest_asyncio.fixture
async def notif_session_factory(notif_engine: Any) -> async_sessionmaker[AsyncSession]:
    """Session factory passed to the dispatch task as ``ctx['sessionmaker']``."""
    return async_sessionmaker(notif_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def notif_db_session(notif_engine: Any) -> AsyncIterator[AsyncSession]:
    """Real-commit session for test seeding."""
    sf = async_sessionmaker(notif_engine, expire_on_commit=False)
    async with sf() as session:
        yield session


# ---------------------------------------------------------------------------
# ARQ ctx builder (dispatch task does not use ctx.redis)
# ---------------------------------------------------------------------------


def _make_ctx(session_factory: async_sessionmaker[AsyncSession]) -> dict[str, Any]:
    """Build a minimal ARQ ctx for ``dispatch_payment_notification``."""
    return {
        "sessionmaker": session_factory,
        "job_try": 1,
    }


# ---------------------------------------------------------------------------
# Structlog reset (mirrors webhook_yookassa conftest pattern)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_structlog_notif() -> None:
    """Reset structlog defaults so capture_logs() works deterministically."""
    structlog.reset_defaults()


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------


async def _seed_owner_user(session: AsyncSession) -> Any:
    """Seed an owner User row (real-commit session)."""
    from app.core.models import User
    from app.core.permissions import Role

    nonce = uuid4().hex[:8]
    owner = User(
        email=f"notif-e2e-owner-{nonce}@example.com",
        password_hash=await hash_password("hunter22hunter22"),
        role=Role.OWNER,
        full_name="Notif E2E Owner",
    )
    session.add(owner)
    await session.flush()
    return owner


async def _seed_client(
    session: AsyncSession,
    owner: Any,
    *,
    telegram_user_id: int | None = 99001,
    email: str | None = None,
) -> Client:
    """Seed a Client row (real-commit session)."""
    nonce = uuid4().hex[:8]
    resolved_email = email if email is not None else f"notif-e2e-client-{nonce}@example.com"
    client = Client(
        last_name="Иванов",
        first_name="Иван",
        phone=f"+7999{nonce}",
        email=resolved_email,
        telegram_user_id=telegram_user_id,
        created_by_user_id=owner.id,
    )
    session.add(client)
    await session.flush()
    return client


async def _seed_plan(session: AsyncSession) -> MembershipPlan:
    """Seed a MembershipPlan row (real-commit session)."""
    plan = MembershipPlan(
        name=f"Notif-E2E-Plan-{uuid4().hex[:6]}",
        duration_days=30,
        price_kopecks=100_000,
        freeze_days_limit=7,
        active=True,
    )
    session.add(plan)
    await session.flush()
    return plan


async def _seed_membership(
    session: AsyncSession,
    *,
    client: Client,
    plan: MembershipPlan,
) -> Membership:
    """Seed a Membership row (real-commit session).

    The payments ledger row must point its ``subject_id`` to this row
    (not to MembershipPlan) so ``_resolve_client_row`` can follow
    ``memberships.client_id → clients`` (memberships.id = subject_id).
    """
    today = datetime.datetime.now(tz=datetime.UTC).date()
    membership = Membership(
        client_id=client.id,
        plan_id=plan.id,
        plan_name_snapshot=plan.name,
        duration_days_snapshot=plan.duration_days,
        price_kopecks_snapshot=plan.price_kopecks,
        freeze_days_limit_snapshot=plan.freeze_days_limit,
        start_date=today,
        end_date=today + datetime.timedelta(days=plan.duration_days),
        status="active",
    )
    session.add(membership)
    await session.flush()
    return membership


async def _seed_payment_ledger(
    session: AsyncSession,
    *,
    membership: Membership,
    subject_kind: str = "membership",
    amount_kopecks: int = 100_000,
    refund_of: UUID | None = None,
) -> Payment:
    """Seed a payments ledger row with subject_id pointing to the membership row."""
    payment = Payment(
        subject_kind=subject_kind,
        subject_id=membership.id,
        amount_kopecks=amount_kopecks,
        method="online",
        received_by_user_id=None,
        refund_of=refund_of,
    )
    session.add(payment)
    await session.flush()
    return payment


async def _seed_online_payment(
    session: AsyncSession,
    *,
    client: Client,
    plan: MembershipPlan,
    status: str = STATUS_SUCCEEDED,
) -> OnlinePayment:
    """Seed an OnlinePayment row (real-commit session)."""
    op = OnlinePayment(
        client_id=client.id,
        membership_plan_id=plan.id,
        pt_package_plan_id=None,
        yookassa_payment_id=f"yk-{uuid4().hex[:24]}",
        idempotency_key=uuid4().hex,
        amount_kopecks=100_000,
        status=status,
        confirmation_url="https://example.com/confirm",
        confirmation_type=CONFIRMATION_TYPE_REDIRECT,
        audit_correlation_id=uuid4(),
    )
    session.add(op)
    await session.flush()
    return op


async def _count_payment_notifications(
    session: AsyncSession,
    *,
    payment_id: UUID | None = None,
    online_payment_id: UUID | None = None,
    kind: str,
) -> int:
    """Count PaymentNotification rows for the given subject + kind."""
    stmt = select(PaymentNotification).where(PaymentNotification.kind == kind)
    if payment_id is not None:
        stmt = stmt.where(PaymentNotification.payment_id == payment_id)
    if online_payment_id is not None:
        stmt = stmt.where(PaymentNotification.online_payment_id == online_payment_id)
    rows = (await session.execute(stmt)).scalars().all()
    return len(rows)


# ---------------------------------------------------------------------------
# Shared stub installation helpers
# ---------------------------------------------------------------------------


def _install_stubs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    tg_records: list[_TelegramRecord],
    email_recorder: _RecordingEmailDispatcher,
    owner_alert_telegram_chat_id: int | None = None,
    owner_alert_email: str | None = None,
) -> Any:
    """Install Telegram + email stubs and optional settings override.

    Returns the prior email dispatcher so the caller can restore it.
    """
    import app.modules.online_payments.tasks as tasks_mod
    from app.core import dependencies as deps_mod
    from app.core.dependencies import register_email_dispatcher
    from app.integrations.telegram import sender as sender_mod

    async def _fake_send_text_dm(bot: Any, chat_id: int, text: str, **_kw: Any) -> Any:
        tg_records.append(_TelegramRecord(chat_id=chat_id, text=text))

    monkeypatch.setattr(sender_mod, "send_text_dm", _fake_send_text_dm)

    # Patch get_settings in the task module (bypasses the @lru_cache).
    stub_settings = _SettingsStub(
        owner_alert_telegram_chat_id=owner_alert_telegram_chat_id,
        owner_alert_email=owner_alert_email,
    )
    monkeypatch.setattr(tasks_mod, "get_settings", lambda: stub_settings)

    prior = deps_mod._email_dispatcher
    register_email_dispatcher(email_recorder)
    return prior


def _restore_email_dispatcher(prior: Any) -> None:
    from app.core import dependencies as deps_mod
    from app.core.dependencies import register_email_dispatcher

    if prior is not None:
        register_email_dispatcher(prior)
    else:
        deps_mod._email_dispatcher = None


# ---------------------------------------------------------------------------
# Test 1: payment_succeeded — dual-channel + cross-restart idempotency (NOT-01/02/03)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_payment_succeeded_dual_channel_then_restart_no_duplicate(
    notif_session_factory: async_sessionmaker[AsyncSession],
    notif_db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """payment_succeeded delivers exactly one Telegram DM + one email.

    A simulated worker restart (second task invocation) must NOT produce
    additional sends or additional payment_notifications rows (NOT-03
    cross-restart idempotency proof).
    """
    # Seed: Owner → Client (tg + email) → Plan → Membership → Payment ledger.
    owner = await _seed_owner_user(notif_db_session)
    client = await _seed_client(
        notif_db_session, owner, telegram_user_id=99101, email="client1@example.com"
    )
    plan = await _seed_plan(notif_db_session)
    membership = await _seed_membership(notif_db_session, client=client, plan=plan)
    payment = await _seed_payment_ledger(notif_db_session, membership=membership)
    await notif_db_session.commit()

    tg_records: list[_TelegramRecord] = []
    email_recorder = _RecordingEmailDispatcher()
    prior = _install_stubs(
        monkeypatch,
        tg_records=tg_records,
        email_recorder=email_recorder,
        # No owner-alert settings needed for client kinds.
    )
    try:
        ctx = _make_ctx(notif_session_factory)

        # ── FIRST invocation ──────────────────────────────────────────────
        result1 = await dispatch_payment_notification(
            ctx, payment_id=str(payment.id), kind="payment_succeeded"
        )
        assert result1 == "sent", f"expected 'sent', got {result1!r}"

        # Exactly one Telegram send + one email send.
        assert len(tg_records) == 1, f"expected 1 TG send; got {tg_records}"
        assert tg_records[0].chat_id == 99101
        assert len(email_recorder.calls) == 1
        assert email_recorder.calls[0].to == "client1@example.com"
        assert email_recorder.calls[0].template_id == "EMAIL_ONLINE_PAYMENT_SUCCEEDED"

        # Two payment_notifications rows (telegram + email) for this payment + kind.
        async with notif_session_factory() as s:
            row_count = await _count_payment_notifications(
                s, payment_id=payment.id, kind="payment_succeeded"
            )
        assert row_count == 2, f"expected 2 rows after first run; got {row_count}"

        # ── SECOND invocation (simulated worker restart / ARQ retry) ──────
        result2 = await dispatch_payment_notification(
            ctx, payment_id=str(payment.id), kind="payment_succeeded"
        )
        assert result2 == "skipped", f"expected 'skipped' on retry; got {result2!r}"

        # No additional sends.
        assert len(tg_records) == 1, "TG must NOT send again on restart"
        assert len(email_recorder.calls) == 1, "email must NOT send again on restart"

        # Row count unchanged (dedup arbiter — partial UNIQUE indexes).
        async with notif_session_factory() as s:
            row_count2 = await _count_payment_notifications(
                s, payment_id=payment.id, kind="payment_succeeded"
            )
        assert row_count2 == 2, f"row count must stay 2 after restart; got {row_count2}"
    finally:
        _restore_email_dispatcher(prior)


# ---------------------------------------------------------------------------
# Test 2: refund_succeeded — dual-channel (NOT-01/02)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refund_succeeded_dual_channel(
    notif_session_factory: async_sessionmaker[AsyncSession],
    notif_db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """refund_succeeded delivers Telegram DM + email via same idempotency pattern."""
    owner = await _seed_owner_user(notif_db_session)
    client = await _seed_client(
        notif_db_session, owner, telegram_user_id=99201, email="refund-client@example.com"
    )
    plan = await _seed_plan(notif_db_session)
    membership = await _seed_membership(notif_db_session, client=client, plan=plan)
    # Original sale payment.
    sale_payment = await _seed_payment_ledger(notif_db_session, membership=membership)
    # Refund payment row (subject_kind='refund', negative amount, refund_of=sale).
    # For refund rows, _resolve_client_row follows refund_of → original payment →
    # then resolves via memberships. The refund's subject_id must also be the
    # membership.id since the original payment's subject_id is the membership.id.
    refund_payment = await _seed_payment_ledger(
        notif_db_session,
        membership=membership,
        subject_kind="refund",
        amount_kopecks=-100_000,
        refund_of=sale_payment.id,
    )
    await notif_db_session.commit()

    tg_records: list[_TelegramRecord] = []
    email_recorder = _RecordingEmailDispatcher()
    prior = _install_stubs(
        monkeypatch, tg_records=tg_records, email_recorder=email_recorder
    )
    try:
        ctx = _make_ctx(notif_session_factory)
        result = await dispatch_payment_notification(
            ctx, payment_id=str(refund_payment.id), kind="refund_succeeded"
        )
        assert result == "sent", f"expected 'sent'; got {result!r}"

        assert len(tg_records) == 1, f"expected 1 TG send; got {tg_records}"
        assert tg_records[0].chat_id == 99201
        assert len(email_recorder.calls) == 1
        assert email_recorder.calls[0].to == "refund-client@example.com"
        assert email_recorder.calls[0].template_id == "EMAIL_ONLINE_PAYMENT_REFUNDED"

        async with notif_session_factory() as s:
            row_count = await _count_payment_notifications(
                s, payment_id=refund_payment.id, kind="refund_succeeded"
            )
        assert row_count == 2
    finally:
        _restore_email_dispatcher(prior)


# ---------------------------------------------------------------------------
# Test 3: channel skipped when telegram_user_id is None (D-52-02)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_channel_skipped_when_recipient_null(
    notif_session_factory: async_sessionmaker[AsyncSession],
    notif_db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Client with telegram_user_id=None → only email sent; no TG idempotency row."""
    owner = await _seed_owner_user(notif_db_session)
    # Client WITHOUT telegram_user_id.
    client = await _seed_client(
        notif_db_session, owner, telegram_user_id=None, email="email-only@example.com"
    )
    plan = await _seed_plan(notif_db_session)
    membership = await _seed_membership(notif_db_session, client=client, plan=plan)
    payment = await _seed_payment_ledger(notif_db_session, membership=membership)
    await notif_db_session.commit()

    tg_records: list[_TelegramRecord] = []
    email_recorder = _RecordingEmailDispatcher()
    prior = _install_stubs(
        monkeypatch, tg_records=tg_records, email_recorder=email_recorder
    )
    try:
        ctx = _make_ctx(notif_session_factory)
        result = await dispatch_payment_notification(
            ctx, payment_id=str(payment.id), kind="payment_succeeded"
        )
        # Only email channel — result is 'partial' (1 of 2 channels).
        assert result == "partial", f"expected 'partial'; got {result!r}"

        # No Telegram send.
        assert len(tg_records) == 0, f"expected 0 TG sends; got {tg_records}"

        # Exactly one email send.
        assert len(email_recorder.calls) == 1
        assert email_recorder.calls[0].to == "email-only@example.com"

        # Only ONE payment_notifications row (email only — no TG idempotency row).
        async with notif_session_factory() as s:
            rows = (
                await s.execute(
                    select(PaymentNotification).where(
                        PaymentNotification.payment_id == payment.id,
                        PaymentNotification.kind == "payment_succeeded",
                    )
                )
            ).scalars().all()
        assert len(rows) == 1, f"expected 1 row (email only); got {len(rows)}"
        assert rows[0].channel == "email"
    finally:
        _restore_email_dispatcher(prior)


# ---------------------------------------------------------------------------
# Test 4: fiscal_failed → owner alert idempotent across restart (NOT-04 + NOT-03 WARNING fix)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fiscal_failed_routes_owner_alert_and_is_idempotent_across_restart(
    notif_session_factory: async_sessionmaker[AsyncSession],
    notif_db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fiscal_failed routes owner alert to owner recipients; re-run is idempotent.

    Proves:
    - Owner Telegram alert + owner email go to OWNER recipients (not the client).
    - Exactly two payment_notifications rows (telegram + email) keyed on payment_id.
    - Re-running the task produces NO additional rows/sends (NOT-03 owner-alert
      idempotency — the WARNING fix from D-52-09 extended to the full restart scenario).
    """
    # Seed a payments ledger row — the fiscal_failed kind is owner-alert only
    # and does not resolve client data. But the payments.id FK must exist.
    owner = await _seed_owner_user(notif_db_session)
    client = await _seed_client(notif_db_session, owner, telegram_user_id=99401)
    plan = await _seed_plan(notif_db_session)
    membership = await _seed_membership(notif_db_session, client=client, plan=plan)
    fiscal_payment = await _seed_payment_ledger(notif_db_session, membership=membership)
    await notif_db_session.commit()

    tg_records: list[_TelegramRecord] = []
    email_recorder = _RecordingEmailDispatcher()
    prior = _install_stubs(
        monkeypatch,
        tg_records=tg_records,
        email_recorder=email_recorder,
        owner_alert_telegram_chat_id=88001,
        owner_alert_email="owner@example.com",
    )
    try:
        ctx = _make_ctx(notif_session_factory)

        # ── FIRST invocation ──────────────────────────────────────────────
        result1 = await dispatch_payment_notification(
            ctx, payment_id=str(fiscal_payment.id), kind="fiscal_failed"
        )
        assert result1 == "sent", f"expected 'sent'; got {result1!r}"

        # Owner TG alert routed to owner chat (NOT client telegram_user_id).
        assert len(tg_records) == 1
        assert tg_records[0].chat_id == 88001  # owner's chat id

        # Owner email routed to owner address.
        assert len(email_recorder.calls) == 1
        assert email_recorder.calls[0].to == "owner@example.com"
        assert email_recorder.calls[0].template_id == "EMAIL_FISCAL_RECEIPT_FAILED"

        # Two rows keyed on payment_id.
        async with notif_session_factory() as s:
            row_count = await _count_payment_notifications(
                s, payment_id=fiscal_payment.id, kind="fiscal_failed"
            )
        assert row_count == 2, f"expected 2 rows after first run; got {row_count}"

        # ── SECOND invocation (simulated worker restart) ───────────────────
        result2 = await dispatch_payment_notification(
            ctx, payment_id=str(fiscal_payment.id), kind="fiscal_failed"
        )
        assert result2 == "skipped", f"expected 'skipped' on restart; got {result2!r}"

        assert len(tg_records) == 1, "owner TG must NOT send again on restart"
        assert len(email_recorder.calls) == 1, "owner email must NOT send again on restart"

        async with notif_session_factory() as s:
            row_count2 = await _count_payment_notifications(
                s, payment_id=fiscal_payment.id, kind="fiscal_failed"
            )
        assert row_count2 == 2, f"row count must stay 2 after restart; got {row_count2}"
    finally:
        _restore_email_dispatcher(prior)


# ---------------------------------------------------------------------------
# Test 5: owner-alert unset → logs only, no raise (D-52-09 best-effort)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_owner_alert_unset_logs_only(
    notif_session_factory: async_sessionmaker[AsyncSession],
    notif_db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When owner_alert settings are None, the task does NOT raise; logs ERROR and skips."""
    owner = await _seed_owner_user(notif_db_session)
    client = await _seed_client(notif_db_session, owner, telegram_user_id=99501)
    plan = await _seed_plan(notif_db_session)
    membership = await _seed_membership(notif_db_session, client=client, plan=plan)
    fiscal_payment = await _seed_payment_ledger(notif_db_session, membership=membership)
    await notif_db_session.commit()

    tg_records: list[_TelegramRecord] = []
    email_recorder = _RecordingEmailDispatcher()
    # Settings stub with owner_alert settings = None (explicit default).
    prior = _install_stubs(
        monkeypatch,
        tg_records=tg_records,
        email_recorder=email_recorder,
        owner_alert_telegram_chat_id=None,
        owner_alert_email=None,
    )
    try:
        ctx = _make_ctx(notif_session_factory)

        # Must NOT raise (D-52-09 best-effort).
        result = await dispatch_payment_notification(
            ctx, payment_id=str(fiscal_payment.id), kind="fiscal_failed"
        )
        assert result == "skipped"

        # No sends — owner channels were skipped.
        assert len(tg_records) == 0
        assert len(email_recorder.calls) == 0

        # No payment_notifications rows written (skip = no claim = no row).
        async with notif_session_factory() as s:
            row_count = await _count_payment_notifications(
                s, payment_id=fiscal_payment.id, kind="fiscal_failed"
            )
        assert row_count == 0
    finally:
        _restore_email_dispatcher(prior)


# ---------------------------------------------------------------------------
# Test 6: payment_canceled — real DB claim, no FK violation, idempotent (D-52-10 BLOCKER)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_payment_canceled_owner_alert_db_claim_no_fk_violation_idempotent(
    notif_session_factory: async_sessionmaker[AsyncSession],
    notif_db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """payment_canceled owner-alert uses online_payment_id (no ledger row) — no FK violation.

    This test MUST hit the real DB (do NOT stub ``claim_payment_notification``
    or bypass the UNIQUE index) — the FK contradiction (D-52-10) is invisible
    to a stubbed suite. Proves:

    (a) The call does NOT raise (no ``IntegrityError`` /
        ``fk_payment_notifications_payment_id_payments`` FK violation).
    (b) Exactly two ``payment_notifications`` rows exist with
        ``online_payment_id = <op.id>`` and ``payment_id IS NULL``.
    (c) One owner TG send + one owner email send recorded.
    (d) Re-run produces NO additional rows and NO additional sends.
    """
    # Seed an online_payment in status=canceled.
    # There is NO payments ledger row — canceled payments never activate.
    owner = await _seed_owner_user(notif_db_session)
    client = await _seed_client(
        notif_db_session, owner, telegram_user_id=99601, email="client6@example.com"
    )
    plan = await _seed_plan(notif_db_session)
    op = await _seed_online_payment(
        notif_db_session, client=client, plan=plan, status=STATUS_CANCELED
    )
    await notif_db_session.commit()

    tg_records: list[_TelegramRecord] = []
    email_recorder = _RecordingEmailDispatcher()
    prior = _install_stubs(
        monkeypatch,
        tg_records=tg_records,
        email_recorder=email_recorder,
        owner_alert_telegram_chat_id=88002,
        owner_alert_email="owner2@example.com",
    )
    try:
        ctx = _make_ctx(notif_session_factory)

        # ── FIRST invocation — must NOT raise ─────────────────────────────
        # (This would raise IntegrityError on the FK if the task tried
        # payment_id=op.id instead of online_payment_id=op.id — D-52-10.)
        result1 = await dispatch_payment_notification(
            ctx, payment_id=str(op.id), kind="payment_canceled"
        )
        assert result1 == "sent", f"expected 'sent'; got {result1!r}"

        # Owner TG + email sent to owner (not client).
        assert len(tg_records) == 1
        assert tg_records[0].chat_id == 88002
        assert len(email_recorder.calls) == 1
        assert email_recorder.calls[0].to == "owner2@example.com"
        assert email_recorder.calls[0].template_id == "EMAIL_ONLINE_PAYMENT_CANCELED"

        # Two rows: online_payment_id set, payment_id IS NULL.
        async with notif_session_factory() as s:
            rows = (
                await s.execute(
                    select(PaymentNotification).where(
                        PaymentNotification.online_payment_id == op.id,
                        PaymentNotification.kind == "payment_canceled",
                    )
                )
            ).scalars().all()
        assert len(rows) == 2, f"expected 2 rows; got {len(rows)}"
        for row in rows:
            assert row.payment_id is None, "payment_id must be NULL for canceled path"
            assert row.online_payment_id == op.id

        # ── SECOND invocation (simulated worker restart) ───────────────────
        result2 = await dispatch_payment_notification(
            ctx, payment_id=str(op.id), kind="payment_canceled"
        )
        assert result2 == "skipped", f"expected 'skipped' on restart; got {result2!r}"

        assert len(tg_records) == 1, "owner TG must NOT send again on restart"
        assert len(email_recorder.calls) == 1, "owner email must NOT send again on restart"

        async with notif_session_factory() as s:
            rows2 = (
                await s.execute(
                    select(PaymentNotification).where(
                        PaymentNotification.online_payment_id == op.id,
                        PaymentNotification.kind == "payment_canceled",
                    )
                )
            ).scalars().all()
        assert len(rows2) == 2, f"row count must stay 2 after restart; got {len(rows2)}"
    finally:
        _restore_email_dispatcher(prior)
