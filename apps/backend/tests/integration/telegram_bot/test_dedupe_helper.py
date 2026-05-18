"""Unit tests for `_dedupe_update_id` module-level helper (Phase 40 D-40-08).

The helper was extracted verbatim from the checkin_handler inlined dedup block
(handlers.py:258-279 pre-Phase-40). Behaviour is byte-identical:

* first-sight (Redis SET-NX returns "OK") -> True (proceed)
* replay (Redis SET-NX returns None)      -> False (skip)
* Redis outage (Exception raised)          -> True (fail-open per D-20-3)

Tests use unittest.mock.AsyncMock for redis.set to keep the helper exercise
hermetic (no fakeredis dependency, no network).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
import structlog
from redis.exceptions import ConnectionError as RedisConnectionError
from structlog.testing import capture_logs

from app.integrations.telegram import handlers as handlers_mod
from app.integrations.telegram.handlers import _dedupe_update_id

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _refresh_handler_logger(monkeypatch: pytest.MonkeyPatch) -> None:
    """Refresh the cached module-level logger so capture_logs sees emissions."""
    fresh = structlog.get_logger("telegram.handler")
    monkeypatch.setattr(handlers_mod, "logger", fresh)


async def test_dedupe_helper_first_sight() -> None:
    """First time we see this update_id: Redis SET-NX succeeds, helper returns True."""
    redis: Any = AsyncMock()
    redis.set = AsyncMock(return_value="OK")

    result = await _dedupe_update_id(redis, update_id=1, chat_id=100)

    assert result is True
    redis.set.assert_awaited_once_with("sz:bot:update:1", "1", nx=True, ex=3600)


async def test_dedupe_helper_replay_skipped() -> None:
    """Replay: Redis SET-NX returns None (key already set), helper returns False."""
    redis: Any = AsyncMock()
    redis.set = AsyncMock(return_value=None)

    with capture_logs() as caplog:
        result = await _dedupe_update_id(redis, update_id=42, chat_id=200)

    assert result is False
    # structlog event `bot_replay_skipped` emitted with update_id + chat_id.
    replays = [
        c
        for c in caplog
        if c.get("event") == "bot_replay_skipped"
        and c.get("update_id") == 42
        and c.get("chat_id") == 200
    ]
    assert replays, f"expected bot_replay_skipped event; got events={caplog}"


async def test_dedupe_helper_fail_open() -> None:
    """Redis outage: helper returns True (fail-open per D-20-3) and emits WARNING."""
    redis: Any = AsyncMock()
    redis.set = AsyncMock(side_effect=RedisConnectionError("redis down"))

    with capture_logs() as caplog:
        result = await _dedupe_update_id(redis, update_id=7, chat_id=300)

    assert result is True
    # structlog WARNING `bot_redis_dedup_unavailable` emitted with diagnostic fields.
    warnings = [
        c
        for c in caplog
        if c.get("event") == "bot_redis_dedup_unavailable"
        and c.get("update_id") == 7
        and c.get("chat_id") == 300
        and "redis down" in c.get("error", "")
    ]
    assert warnings, f"expected bot_redis_dedup_unavailable WARNING; got events={caplog}"
