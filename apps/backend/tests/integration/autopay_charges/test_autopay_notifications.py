"""Phase 84 APAY-04 — autopay notification integration tests.

Tests three behavioural scenarios (plan 84-03):

1. success — dispatch_payment_notification(kind='autopay_charge_succeeded') sends
   Telegram + email once, keyed on online_payment_id; a replayed enqueue sends no
   duplicate (PaymentNotification claim returns False on second call for each channel).

2. failure — dispatch_autopay_failure_notification(autopay_charge_id=...) sends
   Telegram + email once; a re-run / replay sends no duplicate
   (AutopayChargeNotification claim returns False on second call).
   Assert dedup keyed on autopay_charge_id (NOT online_payment_id — no online_payments
   row exists for a sync decline).

3. best-effort — make Telegram send raise; assert email channel still fires and the
   task does NOT re-raise (returns a non-skipped result, email claims asserted).

Design notes (mirrors test_payment_notifications_e2e.py discipline):
  - dispatch_payment_notification + dispatch_autopay_failure_notification both open
    their OWN sessions via ctx['sessionmaker'] — they CANNOT share the SAVEPOINT-wrapped
    db_session. Tests use a real-commit engine + TRUNCATE cleanup (D-13 pattern).
  - Telegram send_text_dm is monkey-patched to a recording stub.
  - get_email_dispatcher() is replaced with a _RecordingEmailDispatcher.
  - No real network (CLAUDE.md constraint).
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
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.modules.autopay_charges.tasks import dispatch_autopay_failure_notification
from app.modules.online_payments.tasks import dispatch_payment_notification

# ---------------------------------------------------------------------------
# Tables to TRUNCATE after every test — all autopay + payment notification tables.
# ---------------------------------------------------------------------------

_TRUNCATE_TABLES = (
    "autopay_charge_notifications",
    "autopay_charges",
    "payment_notifications",
    "audit_log",
    "fiscal_receipts",
    "payments",
    "memberships",
    "online_payments",
    "membership_plans",
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
    """Records get_email_dispatcher() calls without sending real email."""

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
    """Minimal settings stub for the dispatch tasks."""

    def __init__(self) -> None:
        real = get_settings()
        self.telegram_bot_token = real.telegram_bot_token
        self.owner_alert_telegram_chat_id = None
        self.owner_alert_email = None


# ---------------------------------------------------------------------------
# Real-commit engine fixture
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
    """Session factory passed to the dispatch tasks as ctx['sessionmaker']."""
    return async_sessionmaker(notif_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def notif_db_session(notif_engine: Any) -> AsyncIterator[AsyncSession]:
    """Real-commit session for test seeding (auto-commits on exit)."""
    sf = async_sessionmaker(notif_engine, expire_on_commit=False)
    async with sf() as session:
        yield session


# ---------------------------------------------------------------------------
# Structlog reset
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_structlog() -> None:
    structlog.reset_defaults()


# ---------------------------------------------------------------------------
# ARQ ctx builder
# ---------------------------------------------------------------------------


def _make_ctx(session_factory: async_sessionmaker[AsyncSession]) -> dict[str, Any]:
    """Build a minimal ARQ ctx for the notification dispatch tasks."""
    return {
        "sessionmaker": session_factory,
        "job_try": 1,
    }


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------


async def _seed_client_for_notification(
    session: AsyncSession,
    *,
    telegram_user_id: int | None = 88001,
    email: str | None = None,
) -> dict[str, Any]:
    """Seed user + client chain for notification tests. Returns ids."""
    nonce = uuid4().hex[:8]
    user_id = uuid4()
    client_id = uuid4()
    resolved_email = email if email is not None else f"notif-ap-{nonce}@example.com"

    await session.execute(
        text(
            "INSERT INTO users (id, email, password_hash, role, full_name, created_at, updated_at)"
            " VALUES (:u_id, :u_email, 'x', 'owner', 'Autopay Notif Test', now(), now())"
        ),
        {"u_id": user_id, "u_email": f"owner-{nonce}@example.com"},
    )
    await session.execute(
        text(
            "INSERT INTO clients"
            " (id, last_name, first_name, phone, email, telegram_user_id,"
            "  created_by_user_id, created_at, updated_at)"
            " VALUES (:c_id, 'Автооплата', 'Клиент', :c_phone, :c_email, :c_tg,"
            "  :c_uid, now(), now())"
        ),
        {
            "c_id": client_id,
            "c_phone": f"+7903{nonce}",
            "c_email": resolved_email,
            "c_tg": telegram_user_id,
            "c_uid": user_id,
        },
    )
    await session.commit()
    return {
        "user_id": user_id,
        "client_id": client_id,
        "client_email": resolved_email,
        "client_telegram_user_id": telegram_user_id,
    }


async def _seed_membership_for_notification(
    session: AsyncSession,
    client_id: UUID,
    *,
    price_kopecks: int = 199_000,
) -> dict[str, Any]:
    """Seed membership_plans + memberships + autopay_charges for notification tests."""
    nonce = uuid4().hex[:8]
    plan_id = uuid4()
    membership_id = uuid4()
    charge_id = uuid4()
    today = datetime.datetime.now(tz=datetime.UTC).date()

    await session.execute(
        text(
            "INSERT INTO membership_plans"
            " (id, name, duration_days, price_kopecks, freeze_days_limit, created_at, updated_at)"
            " VALUES (:p_id, :p_name, 30, :p_price, 30, now(), now())"
        ),
        {"p_id": plan_id, "p_name": f"ApNotifPlan-{nonce}", "p_price": price_kopecks},
    )
    await session.execute(
        text(
            "INSERT INTO memberships"
            " (id, client_id, plan_id, plan_name_snapshot, duration_days_snapshot,"
            "  price_kopecks_snapshot, freeze_days_limit_snapshot,"
            "  start_date, end_date, status, created_at, updated_at)"
            " VALUES (:m_id, :m_cid, :m_pid, 'ApNotifPlan', 30, :m_price, 30,"
            "         :m_start, :m_end, 'active', now(), now())"
        ),
        {
            "m_id": membership_id,
            "m_cid": client_id,
            "m_pid": plan_id,
            "m_price": price_kopecks,
            "m_start": today - datetime.timedelta(days=30),
            "m_end": today + datetime.timedelta(days=2),
        },
    )
    # Seed a failed autopay_charges row (simulates a declined charge).
    await session.execute(
        text(
            "INSERT INTO autopay_charges"
            " (id, membership_id, period_end, status, amount_kopecks,"
            "  failure_reason, created_at, updated_at)"
            " VALUES (:ac_id, :ac_mid, :ac_end, 'failed', :ac_kopecks,"
            "  'card_declined', now(), now())"
        ),
        {
            "ac_id": charge_id,
            "ac_mid": membership_id,
            "ac_end": today + datetime.timedelta(days=2),
            "ac_kopecks": price_kopecks,
        },
    )
    await session.commit()
    return {
        "plan_id": plan_id,
        "membership_id": membership_id,
        "charge_id": charge_id,
        "price_kopecks": price_kopecks,
        "end_date": today + datetime.timedelta(days=30),
    }


async def _seed_online_payment_for_autopay(
    session: AsyncSession,
    client_id: UUID,
    plan_id: UUID,
    *,
    amount_kopecks: int = 199_000,
) -> dict[str, Any]:
    """Seed an online_payments row with confirmation_type='autopay' for success notifications.

    Mimics what the cron inserts on the ok path (Plan 02). This is the row that the
    webhook creates when a payment.succeeded arrives for an autopay charge.
    """
    nonce = uuid4().hex[:8]
    online_payment_id = uuid4()

    await session.execute(
        text(
            "INSERT INTO online_payments"
            " (id, client_id, membership_plan_id, pt_package_plan_id,"
            "  yookassa_payment_id, idempotency_key, amount_kopecks,"
            "  status, confirmation_url, confirmation_type,"
            "  created_by_user_id, audit_correlation_id, save_payment_method,"
            "  initiated_at)"
            " VALUES"
            " (:id, :c_id, :mp_id, NULL,"
            "  :yk_id, :idem_key, :amount,"
            "  'succeeded', NULL, 'autopay',"
            "  NULL, :audit_id, false,"
            "  now())"
        ),
        {
            "id": str(online_payment_id),
            "c_id": str(client_id),
            "mp_id": str(plan_id),
            "yk_id": f"pay-ap-notif-{nonce}",
            "idem_key": f"idem-ap-{nonce}",
            "amount": amount_kopecks,
            "audit_id": str(uuid4()),
        },
    )
    await session.commit()
    return {"online_payment_id": online_payment_id}


# ---------------------------------------------------------------------------
# Test 1: autopay_charge_succeeded — dual-channel, replay-idempotent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_autopay_success_dual_channel_then_replay_no_duplicate(
    notif_session_factory: async_sessionmaker[AsyncSession],
    notif_db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Webhook-triggered success notification sends Telegram + email once.

    A replayed enqueue (same online_payment_id, same kind) sends NO duplicate:
    claim_payment_notification returns False for each channel on the second call.
    """
    # --- seed ---
    seed = await _seed_client_for_notification(notif_db_session, telegram_user_id=88001)
    client_id: UUID = seed["client_id"]
    client_email: str = seed["client_email"]

    mem_seed = await _seed_membership_for_notification(notif_db_session, client_id)
    plan_id: UUID = mem_seed["plan_id"]

    op_seed = await _seed_online_payment_for_autopay(
        notif_db_session, client_id, plan_id, amount_kopecks=199_000
    )
    online_payment_id: UUID = op_seed["online_payment_id"]

    # --- stubs ---
    tg_calls: list[_TelegramRecord] = []

    async def _stub_send_text_dm(bot: Any, *, chat_id: int, text: str) -> None:
        tg_calls.append(_TelegramRecord(chat_id=chat_id, text=text))

    email_dispatcher = _RecordingEmailDispatcher()

    import app.modules.online_payments.tasks as _tasks_module

    monkeypatch.setattr(_tasks_module, "get_settings", _SettingsStub)
    monkeypatch.setattr(_tasks_module.telegram_sender, "send_text_dm", _stub_send_text_dm)
    monkeypatch.setattr(_tasks_module, "get_email_dispatcher", lambda: email_dispatcher)

    ctx = _make_ctx(notif_session_factory)

    # --- First dispatch (both channels should send) ---
    result1 = await dispatch_payment_notification(
        ctx, payment_id=str(online_payment_id), kind="autopay_charge_succeeded"
    )
    assert result1 == "sent", f"Expected 'sent', got {result1!r}"

    # Telegram: one DM with autopay success copy
    assert len(tg_calls) == 1
    assert "продлён автосписанием" in tg_calls[0].text

    # Email: one email with EMAIL_AUTOPAY_CHARGE_SUCCEEDED
    assert len(email_dispatcher.calls) == 1
    assert email_dispatcher.calls[0].template_id == "EMAIL_AUTOPAY_CHARGE_SUCCEEDED"
    assert email_dispatcher.calls[0].to == client_email

    # --- Replay (second dispatch — idempotent: UNIQUE conflict on both channels) ---
    tg_calls.clear()
    email_dispatcher.calls.clear()

    result2 = await dispatch_payment_notification(
        ctx, payment_id=str(online_payment_id), kind="autopay_charge_succeeded"
    )
    # Both channels already claimed → "skipped" (no channels sent on replay)
    assert result2 == "skipped", f"Expected 'skipped' on replay, got {result2!r}"
    assert len(tg_calls) == 0, "No Telegram DM on replay"
    assert len(email_dispatcher.calls) == 0, "No email on replay"

    # Verify exactly 2 claim rows (one per channel) in payment_notifications.
    async with notif_session_factory() as session:
        count = (
            await session.execute(
                text("SELECT COUNT(*) FROM payment_notifications WHERE online_payment_id = :op_id"),
                {"op_id": str(online_payment_id)},
            )
        ).scalar_one()
    assert count == 2, f"Expected 2 payment_notifications rows, got {count}"


# ---------------------------------------------------------------------------
# Test 2: autopay_charge_failed — dual-channel, replay-idempotent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_autopay_failure_dual_channel_then_replay_no_duplicate(
    notif_session_factory: async_sessionmaker[AsyncSession],
    notif_db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Decline-path failure notification sends Telegram + email once.

    A replayed enqueue (same autopay_charge_id, same kind, same channel) sends NO
    duplicate: claim_autopay_failure_notification returns False for each channel on
    the second call. Dedup keyed on autopay_charge_id (NOT online_payment_id —
    no online_payments row exists for a sync decline).
    """
    # --- seed ---
    seed = await _seed_client_for_notification(notif_db_session, telegram_user_id=88002)
    client_id: UUID = seed["client_id"]
    client_email: str = seed["client_email"]

    mem_seed = await _seed_membership_for_notification(notif_db_session, client_id)
    charge_id: UUID = mem_seed["charge_id"]

    # --- stubs ---
    tg_calls: list[_TelegramRecord] = []

    async def _stub_send_text_dm(bot: Any, *, chat_id: int, text: str) -> None:
        tg_calls.append(_TelegramRecord(chat_id=chat_id, text=text))

    email_dispatcher = _RecordingEmailDispatcher()

    import app.modules.autopay_charges.tasks as _ap_tasks_module

    monkeypatch.setattr(_ap_tasks_module, "get_settings", _SettingsStub)
    monkeypatch.setattr(_ap_tasks_module.telegram_sender, "send_text_dm", _stub_send_text_dm)
    monkeypatch.setattr(_ap_tasks_module, "get_email_dispatcher", lambda: email_dispatcher)

    ctx = _make_ctx(notif_session_factory)

    # --- First dispatch (both channels should send) ---
    result1 = await dispatch_autopay_failure_notification(ctx, autopay_charge_id=str(charge_id))
    assert result1 == "sent", f"Expected 'sent', got {result1!r}"

    # Telegram: one DM with autopay failure copy
    assert len(tg_calls) == 1
    assert "не прошло" in tg_calls[0].text
    assert tg_calls[0].chat_id == 88002

    # Email: one email with EMAIL_AUTOPAY_CHARGE_FAILED
    assert len(email_dispatcher.calls) == 1
    assert email_dispatcher.calls[0].template_id == "EMAIL_AUTOPAY_CHARGE_FAILED"
    assert email_dispatcher.calls[0].to == client_email

    # --- Replay (second dispatch — idempotent) ---
    tg_calls.clear()
    email_dispatcher.calls.clear()

    result2 = await dispatch_autopay_failure_notification(ctx, autopay_charge_id=str(charge_id))
    assert result2 == "skipped", f"Expected 'skipped' on replay, got {result2!r}"
    assert len(tg_calls) == 0, "No Telegram DM on replay"
    assert len(email_dispatcher.calls) == 0, "No email on replay"

    # Verify exactly 2 claim rows (one per channel) in autopay_charge_notifications.
    async with notif_session_factory() as session:
        count = (
            await session.execute(
                text(
                    "SELECT COUNT(*) FROM autopay_charge_notifications"
                    " WHERE autopay_charge_id = :ac_id"
                ),
                {"ac_id": str(charge_id)},
            )
        ).scalar_one()
    assert count == 2, f"Expected 2 autopay_charge_notifications rows, got {count}"

    # Assert NO online_payments row is needed — verify none exists for this charge.
    # (This is the key correctness property: dedup on autopay_charge_id, not online_payment_id.)
    async with notif_session_factory() as session:
        op_count = (
            await session.execute(
                text("SELECT COUNT(*) FROM online_payments WHERE client_id = :c_id"),
                {"c_id": str(client_id)},
            )
        ).scalar_one()
    assert op_count == 0, (
        f"Decline failure notification must not require an online_payments row; found {op_count}"
    )


# ---------------------------------------------------------------------------
# Test 3: best-effort — Telegram failure does not block email and does not re-raise
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_autopay_failure_telegram_down_email_still_sends(
    notif_session_factory: async_sessionmaker[AsyncSession],
    notif_db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Telegram send failure does not block the email channel and does not re-raise.

    The task must:
      - Claim both channels (Telegram claim succeeds before send attempt).
      - Telegram send raises RuntimeError (simulated provider down).
      - Email channel still claims + sends (best-effort, D-52-02 / D-45-08).
      - Task returns 'partial' (one channel sent, one failed mid-send).
      - Task does NOT re-raise the Telegram exception.
    """
    # --- seed ---
    seed = await _seed_client_for_notification(notif_db_session, telegram_user_id=88003)
    client_id: UUID = seed["client_id"]
    client_email: str = seed["client_email"]

    mem_seed = await _seed_membership_for_notification(notif_db_session, client_id)
    charge_id: UUID = mem_seed["charge_id"]

    # --- stubs ---
    async def _stub_tg_raise(bot: Any, *, chat_id: int, text: str) -> None:
        raise RuntimeError("Telegram provider down — simulated failure")

    email_dispatcher = _RecordingEmailDispatcher()

    import app.modules.autopay_charges.tasks as _ap_tasks_module

    monkeypatch.setattr(_ap_tasks_module, "get_settings", _SettingsStub)
    monkeypatch.setattr(_ap_tasks_module.telegram_sender, "send_text_dm", _stub_tg_raise)
    monkeypatch.setattr(_ap_tasks_module, "get_email_dispatcher", lambda: email_dispatcher)

    ctx = _make_ctx(notif_session_factory)

    # --- Dispatch (Telegram fails, email should still send) ---
    result = await dispatch_autopay_failure_notification(ctx, autopay_charge_id=str(charge_id))

    # Task must NOT re-raise — it must return a result string.
    # Email sent → 'partial' (Telegram channel failed during send but was claimed).
    assert result in ("partial", "sent"), (
        f"Task must not re-raise; expected 'partial' or 'sent', got {result!r}"
    )

    # Email channel sent (despite Telegram failure).
    assert len(email_dispatcher.calls) == 1
    assert email_dispatcher.calls[0].template_id == "EMAIL_AUTOPAY_CHARGE_FAILED"
    assert email_dispatcher.calls[0].to == client_email

    # Both channels were claimed (claim happens before send — at-most-once leaning).
    async with notif_session_factory() as session:
        count = (
            await session.execute(
                text(
                    "SELECT COUNT(*) FROM autopay_charge_notifications"
                    " WHERE autopay_charge_id = :ac_id"
                ),
                {"ac_id": str(charge_id)},
            )
        ).scalar_one()
    assert count == 2, f"Both channels must be claimed (claim-before-send); got {count} rows"
