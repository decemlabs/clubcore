"""Redis sliding-window circuit breaker for ЮKassa /receipts (Phase 51 D-51-14).

Two-key sliding-window-plus-open-marker breaker for the ЮKassa receipts
endpoint (Pitfall 11):

- ``cc:yookassa:circuit_window:<provider>`` — Redis sorted set of recent
  failure timestamps (ms since epoch). On every ``record_failure`` we ZADD
  a unique member, ZREMRANGEBYSCORE to trim entries older than 60s, and
  ZCARD to count what's left. When the count crosses
  ``_FAILURE_THRESHOLD`` we SET the open-marker key with a fixed TTL.

- ``cc:yookassa:circuit:<provider>`` — open-marker key. ``is_circuit_open``
  reduces to one ``EXISTS`` so the ARQ task's head-of-body check is O(1).
  Closing is implicit: TTL expiry returns the breaker to closed, with no
  manual reset surface in Phase 51.

Architectural invariant: this module lives at ``app.integrations.yookassa``
and MUST NOT import from any other integration package (D-51-14 chose
copy-and-adapt over generalization explicitly to keep the
``integrations-isolated`` import-linter contract clean). The breaker has
zero domain knowledge — it is a Redis primitive parameterised by
``provider`` string.

D-51-14 LOCKED:
- Threshold: 5 failures / 60s → open
- Open TTL: 300s (5 minutes)
- ``provider`` in v1.7: ``"receipts"`` (key suffix → cc:yookassa:circuit:receipts)
- Copy-and-adapt of the Phase 42 email circuit_breaker module — ONLY
  key prefixes + structlog logger namespace + docstring changed.
"""

from __future__ import annotations

import time
from typing import Final
from uuid import uuid4

import structlog
from redis.asyncio import Redis

_CIRCUIT_KEY_PREFIX: Final[str] = "cc:yookassa:circuit:"
_WINDOW_KEY_PREFIX: Final[str] = "cc:yookassa:circuit_window:"
_FAILURE_THRESHOLD: Final[int] = 5
_WINDOW_SECONDS: Final[int] = 60
_OPEN_TTL_SECONDS: Final[int] = 300  # 5 minutes (D-51-14)

_log = structlog.get_logger("integrations.yookassa.circuit_breaker")


async def is_circuit_open(redis: Redis, provider: str) -> bool:
    """Return True iff the open-marker key exists for ``provider``.

    Cheap O(1) EXISTS — designed to live at the head of the ARQ
    ``dispatch_fiscal_receipt`` task body so a short-circuit costs one
    Redis round trip rather than a full ЮKassa /receipts POST. The
    5-minute TTL on the open marker (set by ``record_failure`` once the
    threshold is crossed) is the only closing surface in Phase 51 —
    there is no manual reset.
    """
    exists = await redis.exists(f"{_CIRCUIT_KEY_PREFIX}{provider}")
    return bool(exists)


async def record_failure(redis: Redis, provider: str) -> None:
    """Record one provider failure in the sliding window; open the breaker on threshold.

    Steps (atomic on Redis via MULTI/EXEC):
      1. ZADD a unique-membered timestamp into the window sorted set
         (uuid hex suffix so duplicate same-ms calls do not silently dedupe).
      2. ZREMRANGEBYSCORE to drop entries older than 60s from the window.
      3. EXPIRE the window key at ``2 * _WINDOW_SECONDS`` so the structure
         self-cleans even when failures stop arriving.
      4. ZCARD to count what's left.

    Steps 1-4 run inside a single ``redis.pipeline(transaction=True)``
    MULTI/EXEC block so the ZCARD read is consistent with the trim that
    preceded it -- closes the concurrent-worker lost-trim race where
    the count read could interleave with another worker's
    ZREMRANGEBYSCORE and miss the threshold (Pitfall 11 step 3).

      5. If count >= threshold, SET the open-marker key with TTL = 5min
         and emit a structlog WARN for ops dashboards. The SET is
         idempotent (TTL refresh) and lives outside the MULTI -- the
         open-marker key is a separate Redis key with its own TTL contract.

    The function is idempotent in the "already open" case: the SET ... EX
    just refreshes the open-marker TTL.
    """
    window_key = f"{_WINDOW_KEY_PREFIX}{provider}"
    now_ms = int(time.time() * 1000)
    member = f"{now_ms}-{uuid4().hex[:8]}"
    cutoff = now_ms - _WINDOW_SECONDS * 1000

    async with redis.pipeline(transaction=True) as pipe:
        pipe.zadd(window_key, {member: now_ms})
        pipe.zremrangebyscore(window_key, 0, cutoff)
        pipe.expire(window_key, _WINDOW_SECONDS * 2)
        pipe.zcard(window_key)
        results = await pipe.execute()

    # pipeline results list is positional: [zadd_count, zremrange_count, expire_ok, zcard_count]
    count = int(results[3])

    if count >= _FAILURE_THRESHOLD:
        await redis.set(
            f"{_CIRCUIT_KEY_PREFIX}{provider}",
            "1",
            ex=_OPEN_TTL_SECONDS,
        )
        _log.warning(
            "circuit_open",
            provider=provider,
            failures_in_window=count,
            open_ttl_seconds=_OPEN_TTL_SECONDS,
        )
