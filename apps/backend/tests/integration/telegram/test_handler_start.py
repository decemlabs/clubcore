"""Direct call test for app.integrations.telegram.handlers.start_handler (Phase 7 D-15).

No live ptb event loop -- we hand-build SimpleNamespace doubles for Update /
Message / User / Chat with only the fields the handler reads. The
HandlerContext.session_factory is wired to a tiny asynccontextmanager that
yields the SAVEPOINT-rolled db_session so all writes are torn down at test
exit (Phase 5 D-22).

Three cases (per CONTEXT line 62):
  1. Known username binds + DMs (stub_telegram_sender.calls has one entry)
  2. Unknown username -> stranger DM, structlog telegram_unknown_start, OtpCode untouched
  3. Sender returns blocked=True -> no code_hash written (D-11 atomicity)
     + structlog telegram_dm_blocked
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest
import pytest_asyncio
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs

from app.core.permissions import Role
from app.core.security import hash_password
from app.integrations.telegram import handlers as handlers_mod
from app.integrations.telegram import sender as sender_mod
from app.integrations.telegram.handlers import HandlerContext, start_handler
from app.modules.auth import telegram_service
from app.modules.auth.models import OtpCode, User
from tests.conftest import StubSenderResult, StubTelegramSender


@pytest.fixture(autouse=True)
def _refresh_handler_logger(monkeypatch: pytest.MonkeyPatch) -> None:
    """Re-acquire `handlers_mod.logger` after the per-test app fixture re-configures structlog.

    structlog is configured with `cache_logger_on_first_use=True`, so the
    module-level `logger = structlog.get_logger('telegram.handler')` in
    handlers.py caches a BoundLogger from the FIRST `configure_logging()`
    call's processor chain. Subsequent re-configurations (each test gets a
    fresh `app` fixture which calls `configure_logging` again) do NOT
    re-bind that cached logger -- so `capture_logs()` (which mutates the
    current global processors) cannot intercept events emitted through it.

    Workaround: at every test entry, replace handlers_mod.logger with a
    freshly-acquired logger that observes the CURRENT processor chain.
    Affects only this test module.
    """
    fresh = structlog.get_logger("telegram.handler")
    monkeypatch.setattr(handlers_mod, "logger", fresh)


KNOWN_USERNAME = "known_user"
UNKNOWN_USERNAME = "stranger"
KNOWN_CHAT_ID = 1111
STRANGER_CHAT_ID = 2222


@pytest_asyncio.fixture
async def known_user(db_session: AsyncSession) -> User:
    user = User(
        email="known@example.com",
        password_hash=await hash_password("hunter22hunter22"),
        role=Role.OWNER,
        full_name="Known",
        telegram_username=KNOWN_USERNAME,
    )
    db_session.add(user)
    await db_session.commit()
    return user


def _build_update(
    *,
    deep_link_token: str,
    username: str | None,
    chat_id: int,
) -> SimpleNamespace:
    """Minimal ptb Update double -- only fields the handler reads."""
    eff_user = SimpleNamespace(id=chat_id, username=username, is_bot=False)
    eff_chat = SimpleNamespace(id=chat_id, type="private")
    message = SimpleNamespace(
        text=f"/start {deep_link_token}",
        chat=eff_chat,
        from_user=eff_user,
    )
    return SimpleNamespace(
        effective_user=eff_user,
        effective_chat=eff_chat,
        message=message,
    )


def _build_ctx(db_session: AsyncSession) -> HandlerContext:
    """Wrap db_session in an asynccontextmanager-style factory.

    Handler does `async with ctx.session_factory() as session:` -- the factory
    is typed as async_sessionmaker[AsyncSession] but at runtime any callable
    returning an async context manager that yields AsyncSession satisfies it.
    """

    @asynccontextmanager
    async def _factory() -> AsyncIterator[AsyncSession]:
        yield db_session

    return HandlerContext(
        session_factory=_factory,  # type: ignore[arg-type]
        telegram_service=telegram_service,
        sender=sender_mod,
    )


# ---------------------------------------------------------------------------
# Test 1: known username + chat_id NULL -> bind + DM + commit
# ---------------------------------------------------------------------------


async def test_handler_known_username_binds_and_dms(
    db_session: AsyncSession,
    known_user: User,
    stub_telegram_sender: StubTelegramSender,
) -> None:
    """Known username -> bind + DM + commit_otp; OtpCode.code_hash NOT NULL after."""
    raw_token, _hash = await telegram_service.start_deep_link(db_session)
    update = _build_update(
        deep_link_token=raw_token,
        username=KNOWN_USERNAME,
        chat_id=KNOWN_CHAT_ID,
    )
    ctx = _build_ctx(db_session)
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    await start_handler(update, context, ctx)

    # Sender called once with the 6-digit code.
    assert len(stub_telegram_sender.calls) == 1
    chat_id_called, code = stub_telegram_sender.calls[0]
    assert chat_id_called == KNOWN_CHAT_ID
    assert len(code) == 6 and code.isdigit()
    # No stranger DM.
    assert stub_telegram_sender.text_calls == []

    # OtpCode row: code_hash NOT NULL after commit_otp; user / chat bound.
    row = (await db_session.execute(select(OtpCode))).scalar_one()
    assert row.code_hash is not None
    assert row.user_id == known_user.id
    assert row.telegram_chat_id == KNOWN_CHAT_ID

    # User.telegram_chat_id bound (was NULL before).
    fresh = await db_session.scalar(select(User).where(User.id == known_user.id))
    assert fresh is not None
    assert fresh.telegram_chat_id == KNOWN_CHAT_ID


# ---------------------------------------------------------------------------
# Test 2: unknown username -> stranger DM, structlog telegram_unknown_start,
#         OtpCode UNTOUCHED (code_hash still NULL)
# ---------------------------------------------------------------------------


async def test_handler_unknown_username_emits_event_and_dms_stranger(
    db_session: AsyncSession,
    stub_telegram_sender: StubTelegramSender,
) -> None:
    """Stranger /start -> stranger text DM + telegram_unknown_start + OtpCode untouched."""
    raw_token, _hash = await telegram_service.start_deep_link(db_session)
    update = _build_update(
        deep_link_token=raw_token,
        username=UNKNOWN_USERNAME,
        chat_id=STRANGER_CHAT_ID,
    )
    ctx = _build_ctx(db_session)
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    with capture_logs() as caplog:
        await start_handler(update, context, ctx)

    # No OTP DM.
    assert stub_telegram_sender.calls == []
    # Stranger text DM was sent (D-04 fixed Russian copy).
    assert len(stub_telegram_sender.text_calls) == 1
    chat_id_called, text = stub_telegram_sender.text_calls[0]
    assert chat_id_called == STRANGER_CHAT_ID
    assert "Sportzal" in text

    # structlog telegram_unknown_start event emitted.
    events = [c.get("event") for c in caplog]
    assert "telegram_unknown_start" in events, f"events={events}"

    # OtpCode row UNTOUCHED -- code_hash still NULL.
    row = (await db_session.execute(select(OtpCode))).scalar_one()
    assert row.code_hash is None


# ---------------------------------------------------------------------------
# Test 3: sender returns blocked=True -> no code_hash written (D-11 atomicity)
# ---------------------------------------------------------------------------


async def test_handler_sender_blocked_skips_commit_and_emits_event(
    db_session: AsyncSession,
    known_user: User,
    stub_telegram_sender: StubTelegramSender,
) -> None:
    """Blocked DM -> no commit_otp; OtpCode.code_hash STILL NULL (D-11)."""
    _ = known_user
    stub_telegram_sender.next_result = StubSenderResult(ok=False, blocked=True)

    raw_token, _hash = await telegram_service.start_deep_link(db_session)
    update = _build_update(
        deep_link_token=raw_token,
        username=KNOWN_USERNAME,
        chat_id=KNOWN_CHAT_ID,
    )
    ctx = _build_ctx(db_session)
    context: Any = SimpleNamespace(bot=SimpleNamespace())

    with capture_logs() as caplog:
        await start_handler(update, context, ctx)

    # Sender WAS called (attempted), but commit_otp NOT executed.
    assert len(stub_telegram_sender.calls) == 1

    # OtpCode row: code_hash STILL NULL (D-11 atomicity -- DM blocked -> no commit).
    row = (await db_session.execute(select(OtpCode))).scalar_one()
    assert row.code_hash is None

    # structlog telegram_dm_blocked event emitted.
    events = [c.get("event") for c in caplog]
    assert "telegram_dm_blocked" in events, f"events={events}"
