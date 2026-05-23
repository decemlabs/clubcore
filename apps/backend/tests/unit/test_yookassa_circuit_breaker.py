"""Unit tests for ``app.integrations.yookassa.circuit_breaker`` (Plan 51-04).

The Redis sliding-window circuit breaker for ЮKassa /receipts (D-51-14):
  - threshold: 5 failures within 60s sliding window opens the circuit
  - open key:    ``sz:yookassa:circuit:<provider>`` (TTL = 300s)
  - window key:  ``sz:yookassa:circuit_window:<provider>`` (sorted set)
  - is_circuit_open uses cheap EXISTS on the open key (O(1))
  - record_failure runs ZADD + ZREMRANGEBYSCORE + EXPIRE + ZCARD inside a
    single MULTI/EXEC pipeline (Pitfall 11 — closes the concurrent-worker
    lost-trim race).

Tests use fakeredis (no live Redis required; matches the rest of the suite).
"""

from __future__ import annotations

import time
from typing import cast
from unittest.mock import MagicMock, patch

import fakeredis.aioredis
import pytest
from redis.asyncio import Redis

from app.integrations.yookassa.circuit_breaker import (
    _CIRCUIT_KEY_PREFIX,
    _FAILURE_THRESHOLD,
    _OPEN_TTL_SECONDS,
    _WINDOW_KEY_PREFIX,
    _WINDOW_SECONDS,
    is_circuit_open,
    record_failure,
)


def _fake_redis() -> Redis:
    """fakeredis async client typed as redis.asyncio.Redis for the function signature."""
    return cast(Redis, fakeredis.aioredis.FakeRedis(decode_responses=True))


@pytest.mark.asyncio
async def test_is_circuit_open_returns_false_when_no_open_marker() -> None:
    """Fresh Redis → False (no open-marker key, no window entries)."""
    redis = _fake_redis()
    assert await is_circuit_open(redis, "receipts") is False


@pytest.mark.asyncio
async def test_is_circuit_open_returns_true_when_marker_set() -> None:
    """Manually-set open marker → True (EXISTS short-circuit)."""
    redis = _fake_redis()
    await redis.set("sz:yookassa:circuit:receipts", "1", ex=300)
    assert await is_circuit_open(redis, "receipts") is True


@pytest.mark.asyncio
async def test_record_failure_increments_window_sorted_set() -> None:
    """One record_failure call → ZCARD(window) == 1."""
    redis = _fake_redis()
    await record_failure(redis, "receipts")
    count = await redis.zcard("sz:yookassa:circuit_window:receipts")
    assert count == 1


@pytest.mark.asyncio
async def test_record_failure_opens_circuit_at_threshold() -> None:
    """5 failures in 60s → circuit opens; open-marker TTL ≈ 300s."""
    redis = _fake_redis()
    for _ in range(_FAILURE_THRESHOLD):
        await record_failure(redis, "receipts")
    assert await is_circuit_open(redis, "receipts") is True
    ttl = await redis.ttl(f"{_CIRCUIT_KEY_PREFIX}receipts")
    # Allow a wide-enough window so the test stays stable even under
    # CI scheduling jitter; D-51-14 says open_ttl = 300s.
    assert 290 <= ttl <= _OPEN_TTL_SECONDS


@pytest.mark.asyncio
async def test_record_failure_does_not_open_below_threshold() -> None:
    """4 failures (threshold - 1) → circuit stays closed."""
    redis = _fake_redis()
    for _ in range(_FAILURE_THRESHOLD - 1):
        await record_failure(redis, "receipts")
    assert await is_circuit_open(redis, "receipts") is False


@pytest.mark.asyncio
async def test_record_failure_evicts_stale_entries_from_window() -> None:
    """Stale entries older than _WINDOW_SECONDS are trimmed by ZREMRANGEBYSCORE."""
    redis = _fake_redis()
    window_key = f"{_WINDOW_KEY_PREFIX}receipts"
    # Pre-seed a stale member (older than the 60s window).
    stale_score = int((time.time() - (_WINDOW_SECONDS + 60)) * 1000)
    await redis.zadd(window_key, {"stale-member": stale_score})
    # Record one fresh failure — the stale member should be trimmed.
    await record_failure(redis, "receipts")
    count = await redis.zcard(window_key)
    assert count == 1, "stale window member was not evicted by ZREMRANGEBYSCORE"


@pytest.mark.asyncio
async def test_atomic_pipeline_used_for_record_failure() -> None:
    """Pitfall 11 lock: ``redis.pipeline`` MUST be called with ``transaction=True``.

    Spy on Redis.pipeline via patch to assert the kwarg is set — guards
    against accidental regression to a non-pipelined or non-transactional form.
    """
    redis = _fake_redis()
    real_pipeline = redis.pipeline
    spy = MagicMock(side_effect=lambda *a, **kw: real_pipeline(*a, **kw))
    with patch.object(redis, "pipeline", spy):
        await record_failure(redis, "receipts")
    assert spy.called, "redis.pipeline was not called by record_failure"
    # transaction=True is the load-bearing kwarg (MULTI/EXEC).
    _, kwargs = spy.call_args
    assert kwargs.get("transaction") is True, (
        f"record_failure must call redis.pipeline(transaction=True); "
        f"got kwargs={kwargs!r}"
    )


@pytest.mark.asyncio
async def test_record_failure_with_different_providers_uses_separate_counters() -> None:
    """Per-provider isolation: each provider gets its own window + open-marker keys."""
    redis = _fake_redis()
    for _ in range(_FAILURE_THRESHOLD - 1):  # 4 — below threshold
        await record_failure(redis, "receipts")
    await record_failure(redis, "other")

    receipts_count = await redis.zcard(f"{_WINDOW_KEY_PREFIX}receipts")
    other_count = await redis.zcard(f"{_WINDOW_KEY_PREFIX}other")
    assert receipts_count == _FAILURE_THRESHOLD - 1
    assert other_count == 1

    assert await is_circuit_open(redis, "receipts") is False
    assert await is_circuit_open(redis, "other") is False
