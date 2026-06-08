"""Regression guard: build_application registers BOTH start and checkin (AUTH-TG-09)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import fakeredis.aioredis
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from telegram.ext import CommandHandler

from app.integrations.telegram import sender as sender_mod
from app.integrations.telegram.bot import build_application
from app.integrations.telegram.handlers import (
    HandlerContext,
    checkin_handler,
    start_handler,
)
from app.modules.auth import telegram_service
from app.modules.bookings import service as bookings_service
from app.modules.messaging import service as messaging_service
from app.modules.schedule import service as schedule_service
from app.modules.visits import service as visits_service

pytestmark = pytest.mark.asyncio


async def test_worker_registers_start_and_checkin(
    db_session: AsyncSession,
) -> None:
    @asynccontextmanager
    async def _factory() -> AsyncIterator[AsyncSession]:
        yield db_session

    # Phase 20: deterministic in-memory redis stub. Lives only for this test.
    # Chosen over lifting `redis_clean` from `tests/integration/visits/conftest.py`
    # so we do not touch unrelated test infra.
    fake_redis = fakeredis.aioredis.FakeRedis()
    ctx = HandlerContext(
        session_factory=_factory,  # type: ignore[arg-type]
        telegram_service=telegram_service,
        sender=sender_mod,
        visits_service=visits_service,
        redis=fake_redis,
        bookings_service=bookings_service,
        schedule_service=schedule_service,
        messaging_service=messaging_service,  # Phase 93 D-06 relaxation
    )
    app = build_application(
        token="dummy:token",  # noqa: S106 — ptb does no network on construction
        handlers=[("start", start_handler), ("checkin", checkin_handler)],
        ctx=ctx,
    )
    registered = [h for group in app.handlers.values() for h in group]
    cmd_names: set[str] = set()
    for h in registered:
        if isinstance(h, CommandHandler):
            cmd_names.update(h.commands)
    assert {"start", "checkin"} <= cmd_names, cmd_names
