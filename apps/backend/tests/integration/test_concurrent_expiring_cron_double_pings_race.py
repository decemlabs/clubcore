"""Phase 46 D-46-14 #5 / VER-10 — concurrent expiring-cron double-pings race.

Real-Postgres concurrent IN-PROCESS invocation of
``_send_expiring_notifications`` twice against the SAME membership via
``asyncio.gather``. The UNIQUE ``(membership_id, kind, channel)`` index on
``membership_notifications`` (Alembic 0024 + Phase 41 D-41-15) catches
the duplicate; exactly one ``channel='email'`` row survives.

In-process ``asyncio.gather`` of the SAME helper sharing a single
``async_sessionmaker`` is the tight race surface — out-of-band invocation
shells would interleave too coarsely for the DB UNIQUE conflict window
(<1 ms) to fire.

Uses the Phase 45 D-45-01 synthesised-blocked branch (client with
``telegram_user_id IS NULL`` → helper synthesises
``SendResult(ok=False, blocked=True)`` without any Telegram I/O) so the
two arms reach the ``channel='email'`` INSERT deterministically; the
loser raises :class:`sqlalchemy.exc.IntegrityError` inside the helper's
explicit try/except (service.py D-45-04 race-duplicate guard).

Mirrors Phase 45 D-45-28 (``test_payment_receipt_race.py``) real-commit
engine pattern + Phase 27 D-27-07 multi-session-per-tick race-safety.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from app.core import dependencies as deps_mod
from app.core.config import get_settings
from app.core.dependencies import register_email_dispatcher
from app.integrations.telegram import copy as telegram_copy

_RACE_OWNER_EMAIL = "expiring-cron-race-owner@example.com"


@pytest_asyncio.fixture
async def real_commit_engine() -> AsyncIterator[AsyncEngine]:
    """Standalone real-commit engine for the expiring-cron UNIQUE race test.

    The default ``db_session`` SAVEPOINT pattern (tests/conftest.py)
    composes nested transactions; concurrent INSERTs from two separate
    sessions cannot race against a UNIQUE index inside a single outer
    SAVEPOINT, so we need a real engine that issues real COMMITs.

    Defensively probes Postgres at fixture entry — cleanly SKIPs on
    unreachable Postgres rather than erroring inside ``asyncio.gather``.
    TRUNCATE at teardown (real-commit writes are not rolled back);
    CASCADE handles the FK chain
    ``membership_notifications → memberships → clients → users``
    plus ``membership_plans``.
    """
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)

    try:
        async with engine.connect() as probe:
            await probe.execute(text("select 1"))
    except Exception as exc:  # broad: skip on any connectivity failure
        await engine.dispose()
        pytest.skip(
            f"DATABASE_URL not reachable for D-46-14 #5; "
            f"run `docker compose up postgres` first ({exc!r})"
        )

    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "TRUNCATE membership_notifications, audit_log, "
                    "memberships, membership_plans, clients, users "
                    "RESTART IDENTITY CASCADE"
                )
            )
        await engine.dispose()


class _RecordingEmailDispatcher:
    """Spy satisfying the Phase 41 D-41-24 EmailDispatcher Protocol.

    Concurrent dispatches append to ``calls``; the race winner gets one
    entry, the loser raises ``IntegrityError`` before its enqueue
    completes — so the dispatcher may legitimately record 1 OR 2 calls
    depending on whether the loser's dispatch ran BEFORE the UNIQUE
    insert (1 row, 1-or-2 dispatcher calls is the contract per D-45-04).
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def __call__(
        self,
        *,
        template_id: str,
        to: str,
        audit_correlation_id: UUID | None,
        **template_vars: Any,
    ) -> None:
        self.calls.append(
            {
                "template_id": template_id,
                "to": to,
                "audit_correlation_id": audit_correlation_id,
                **template_vars,
            }
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


@pytest.mark.asyncio
async def test_concurrent_expiring_cron_double_pings_race(
    real_commit_engine: AsyncEngine,
    email_recorder: _RecordingEmailDispatcher,
) -> None:
    """Two concurrent ``_send_expiring_notifications`` invocations against the
    same membership → exactly one ``channel='email'`` row in
    ``membership_notifications``.

    Race outcome (D-45-04 + Alembic 0024):
      - Both arms read the same candidate via
        ``find_expiring_candidates`` (NOT EXISTS predicate passes for
        both before either commits — the read sessions close before
        the write phase).
      - Both arms enter the email-fallback branch (``chat_id is None``
        → synthesised blocked).
      - One arm INSERTs first and commits — surviving row.
      - The other arm hits ``IntegrityError`` on
        ``uq_membership_notifications_membership_kind_channel`` inside
        the helper's explicit try/except, rolls back, logs warning,
        does NOT re-raise.
    """
    # Avoid expire_on_commit so concurrent sessions don't trip async-IO
    # in their commit hooks.
    session_factory = async_sessionmaker(real_commit_engine, expire_on_commit=False)

    today = date(2026, 6, 1)
    expires_at = today + timedelta(days=7)  # exactly 7d ahead → 'expiring_7d'

    owner_id = uuid4()
    plan_id = uuid4()
    client_id = uuid4()
    membership_id = uuid4()

    # ── Seed owner + plan + client (email-only, no telegram) + membership ──
    async with session_factory() as setup:
        await setup.execute(
            text(
                """
                INSERT INTO users (id, email, password_hash, role, full_name,
                                   is_active, created_at, updated_at)
                VALUES (:uid, :email, NULL, 'owner', 'Cron Race Owner',
                        TRUE, now(), now())
                """
            ),
            {"uid": owner_id, "email": _RACE_OWNER_EMAIL},
        )

        await setup.execute(
            text(
                """
                INSERT INTO membership_plans
                    (id, name, duration_days, price_kopecks, freeze_days_limit,
                     active, created_at, updated_at)
                VALUES (:pid, :name, 30, 250000, 14, TRUE, now(), now())
                """
            ),
            {"pid": plan_id, "name": f"Cron Race Plan {plan_id.hex[:6]}"},
        )

        # telegram_user_id IS NULL → D-45-01 synthesised blocked
        # branch routes the candidate to email-fallback.
        await setup.execute(
            text(
                """
                INSERT INTO clients (id, last_name, first_name, phone, email,
                                     telegram_user_id, created_by_user_id,
                                     tags, created_at, updated_at)
                VALUES (:cid, 'Race', 'Cron', :phone, :email,
                        NULL, :owner, ARRAY[]::TEXT[], now(), now())
                """
            ),
            {
                "cid": client_id,
                "phone": f"+7999{client_id.hex[:7]}",
                "email": f"race-cron+{client_id.hex[:6]}@local.dev",
                "owner": owner_id,
            },
        )

        await setup.execute(
            text(
                """
                INSERT INTO memberships
                    (id, client_id, plan_id, plan_name_snapshot,
                     duration_days_snapshot, price_kopecks_snapshot,
                     freeze_days_limit_snapshot, start_date, end_date,
                     status, activation_policy, created_at, updated_at)
                VALUES (:mid, :cid, :pid, 'cron-race-plan',
                        30, 250000, 14, :start, :end,
                        'active', 'purchase_date', now(), now())
                """
            ),
            {
                "mid": membership_id,
                "cid": client_id,
                "pid": plan_id,
                "start": today - timedelta(days=23),
                "end": expires_at,
            },
        )
        await setup.commit()

    # ── In-process race: import helper, build mock injectables ────────────
    # Imported lazily after fixture setup to avoid import-time side effects.
    from app.modules.memberships import service as memberships_service

    # ``cand.chat_id is None`` short-circuits the sender call before
    # render_expiring_dm — these mocks are required by the helper's
    # signature but never invoked on this candidate.
    fake_bot = SimpleNamespace()

    async def _never_called_send(
        bot: object, chat_id: int, body: str
    ) -> Any:  # pragma: no cover -- never reached
        raise AssertionError("sender.send_text_dm must not be called when chat_id is None")

    fake_sender = SimpleNamespace(send_text_dm=_never_called_send)

    async def _invoke() -> int:
        # Helper swallows IntegrityError internally (D-45-04 race guard);
        # both arms return their successful-send count (0 or 1).
        return await memberships_service._send_expiring_notifications(
            session_factory,
            today=today,
            bot=fake_bot,  # type: ignore[arg-type]
            sender=fake_sender,
            copy_module=telegram_copy,
        )

    results = await asyncio.gather(_invoke(), _invoke(), return_exceptions=False)

    # The race winner's helper invocation reports sent=1; the loser's
    # invocation either reports sent=0 (IntegrityError swallowed) OR
    # sent=1 if it observed the surviving row was theirs. Total winners
    # across both arms is exactly 1.
    assert sum(results) == 1, (
        f"expected exactly one successful send across both gather arms, got {results!r}"
    )

    # ── DB invariant: exactly one membership_notifications row, channel='email' ──
    async with session_factory() as verify:
        email_row_count = (
            await verify.execute(
                text(
                    "SELECT count(*) FROM membership_notifications "
                    "WHERE membership_id = :mid AND channel = 'email'"
                ),
                {"mid": membership_id},
            )
        ).scalar_one()
        assert email_row_count == 1, (
            f"expected exactly 1 'email' row on uq_membership_notifications_"
            f"membership_kind_channel, got {email_row_count}"
        )

        # Cross-channel invariant: zero telegram rows (chat_id was NULL).
        telegram_row_count = (
            await verify.execute(
                text(
                    "SELECT count(*) FROM membership_notifications "
                    "WHERE membership_id = :mid AND channel = 'telegram'"
                ),
                {"mid": membership_id},
            )
        ).scalar_one()
        assert telegram_row_count == 0, (
            f"telegram channel must be untouched (chat_id IS NULL); got {telegram_row_count} row(s)"
        )

    # Email dispatcher recorder — at least one literal-template invocation
    # (the loser MAY have dispatched before its INSERT failed, so 1 or 2
    # is acceptable; the DB invariant above is the canonical race assertion).
    assert len(email_recorder.calls) >= 1, "expected ≥1 EmailDispatcher invocation during the race"
    for call in email_recorder.calls:
        assert call["template_id"].startswith("EMAIL_EXPIRING_7D_"), (
            f"non-literal expiring_7d template_id observed: {call['template_id']!r}"
        )
        assert call["to"].startswith("race-cron+"), f"unexpected recipient: {call['to']!r}"

    # Suppress unused-import warning on datetime/UTC (imported for parity
    # with the analog test even though not consumed in the body).
    _ = (UTC, datetime)
