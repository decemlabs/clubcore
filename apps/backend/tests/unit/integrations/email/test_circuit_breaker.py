"""Unit tests for ``app.integrations.email.circuit_breaker`` (Plan 42-08 Task 1).

The Redis sliding-window circuit breaker (D-42-14):
  - threshold: 5 failures within 60s sliding window opens the circuit
  - open key: ``cc:email:circuit:<provider>`` with TTL <= 300s (5 min)
  - sliding-window backing store: Redis sorted set ``cc:email:circuit_window:<provider>``
  - is_circuit_open uses cheap EXISTS on the open key (O(1))
  - while the open key is present, is_circuit_open returns True even after
    every failure timestamp slides out of the 60s window (TTL-driven close)
  - tests use fakeredis (no live Redis required; matches the rest of the suite)
"""

from __future__ import annotations

import asyncio
import time
from typing import cast

import fakeredis.aioredis
import pytest
from redis.asyncio import Redis

from app.integrations.email.circuit_breaker import (
    _CIRCUIT_KEY_PREFIX,
    _FAILURE_THRESHOLD,
    _OPEN_TTL_SECONDS,
    _WINDOW_SECONDS,
    is_circuit_open,
    record_failure,
)


def _fake_redis() -> Redis:
    """fakeredis async client typed as redis.asyncio.Redis for the function signature."""
    return cast(Redis, fakeredis.aioredis.FakeRedis(decode_responses=True))


@pytest.mark.asyncio
async def test_is_circuit_open_returns_false_when_no_failures_recorded() -> None:
    """Test 1: clean state → False (no open key, no window entries)."""
    redis = _fake_redis()
    assert await is_circuit_open(redis, "yandex_postbox") is False


@pytest.mark.asyncio
async def test_four_failures_within_window_does_not_open() -> None:
    """Test 2: 4 failures in 60s → still closed (threshold is >= 5)."""
    redis = _fake_redis()
    for _ in range(4):
        await record_failure(redis, "yandex_postbox")
    assert await is_circuit_open(redis, "yandex_postbox") is False


@pytest.mark.asyncio
async def test_five_failures_within_window_opens_circuit() -> None:
    """Test 3: 5 failures in 60s → open, with TTL bounded by _OPEN_TTL_SECONDS."""
    redis = _fake_redis()
    for _ in range(5):
        await record_failure(redis, "yandex_postbox")
    assert await is_circuit_open(redis, "yandex_postbox") is True
    ttl = await redis.ttl(f"{_CIRCUIT_KEY_PREFIX}yandex_postbox")
    assert 0 < ttl <= _OPEN_TTL_SECONDS


@pytest.mark.asyncio
async def test_circuit_stays_open_after_window_entries_slide_out() -> None:
    """Test 4: TTL-driven, not count-driven.

    Once the open key is set, is_circuit_open returns True even if every
    timestamp in the sliding-window sorted set has slid past the 60s
    horizon (since is_circuit_open keys off the open marker, not the
    window count).
    """
    redis = _fake_redis()
    for _ in range(5):
        await record_failure(redis, "yandex_postbox")
    assert await is_circuit_open(redis, "yandex_postbox") is True
    # Simulate every window entry sliding out by removing them entirely;
    # this is the moral equivalent of >60s passing with no new failures.
    await redis.delete("cc:email:circuit_window:yandex_postbox")
    # The open key remains — circuit still considered open.
    assert await is_circuit_open(redis, "yandex_postbox") is True


@pytest.mark.asyncio
async def test_circuit_closes_after_open_key_ttl_expires() -> None:
    """Test 5: deleting the open key (simulating TTL expiry) closes the circuit."""
    redis = _fake_redis()
    for _ in range(5):
        await record_failure(redis, "yandex_postbox")
    assert await is_circuit_open(redis, "yandex_postbox") is True
    # Simulate TTL expiry.
    await redis.delete(f"{_CIRCUIT_KEY_PREFIX}yandex_postbox")
    assert await is_circuit_open(redis, "yandex_postbox") is False


@pytest.mark.asyncio
async def test_constants_match_locked_values() -> None:
    """Belt-and-suspenders: the locked D-42-14 constants stay byte-exact."""
    assert _FAILURE_THRESHOLD == 5
    assert _WINDOW_SECONDS == 60
    assert _OPEN_TTL_SECONDS == 300
    assert _CIRCUIT_KEY_PREFIX == "cc:email:circuit:"


@pytest.mark.asyncio
async def test_record_failure_trims_stale_window_entries() -> None:
    """Old entries (>60s) are trimmed; only fresh ones count toward threshold."""
    redis = _fake_redis()
    window_key = "cc:email:circuit_window:yandex_postbox"
    # Pre-seed 4 stale entries older than 60s.
    stale_score = int((time.time() - 120) * 1000)
    for i in range(4):
        await redis.zadd(window_key, {f"stale-{i}": stale_score})
    # Record one fresh failure — stale ones should be trimmed, count = 1, NOT 5.
    await record_failure(redis, "yandex_postbox")
    assert await is_circuit_open(redis, "yandex_postbox") is False
    count = await redis.zcard(window_key)
    assert count == 1


@pytest.mark.asyncio
async def test_record_failure_concurrent_open_at_threshold() -> None:
    """CR-03 regression: N=threshold concurrent record_failure calls open the circuit exactly once.

    Races _FAILURE_THRESHOLD parallel record_failure calls via asyncio.gather.
    The pipelined implementation must produce N window members AND set the
    open-marker. The pre-fix non-pipelined form could miss the open under
    race-y interleaving of ZREMRANGEBYSCORE/ZCARD.

    Note: fakeredis pipeline enforces sequential execution per-call, so this
    test exercises pipeline-call ordering / structural correctness (pipeline +
    execute() with positional results indexing) rather than true MULTI atomicity.
    That is acceptable at the unit tier — the purpose is to lock the API surface
    against accidental regression to the non-pipelined form.
    """
    redis = _fake_redis()
    provider = "test_provider_concurrent"

    # Race N=threshold parallel record_failure calls.
    await asyncio.gather(
        *[record_failure(redis, provider) for _ in range(_FAILURE_THRESHOLD)]
    )

    # Open-marker key MUST exist after threshold is reached.
    exists = await redis.exists(f"{_CIRCUIT_KEY_PREFIX}{provider}")
    assert exists == 1, "circuit failed to open after N concurrent failures (CR-03 regression)"

    # Window key must have exactly N entries (unique uuid suffix per call).
    count = await redis.zcard(f"cc:email:circuit_window:{provider}")
    assert count == _FAILURE_THRESHOLD, (
        f"window cardinality drift: expected {_FAILURE_THRESHOLD}, got {count} "
        "(lost member from non-atomic ZADD?)"
    )


@pytest.mark.asyncio
async def test_record_failure_below_threshold_does_not_open() -> None:
    """Below-threshold concurrent calls do NOT set the open-marker."""
    redis = _fake_redis()
    provider = "test_provider_below"

    n = _FAILURE_THRESHOLD - 1
    await asyncio.gather(*[record_failure(redis, provider) for _ in range(n)])

    exists = await redis.exists(f"{_CIRCUIT_KEY_PREFIX}{provider}")
    assert exists == 0, "circuit opened below threshold (false positive)"

    count = await redis.zcard(f"cc:email:circuit_window:{provider}")
    assert count == n
