"""Redis sliding-window circuit breaker (Phase 42 D-42-14 / Plan 42-08 Task 1).

Two-key sliding-window-plus-open-marker breaker for the email transport:

- ``sz:email:circuit_window:<provider>`` — Redis sorted set of recent failure
  timestamps (ms since epoch). On every ``record_failure`` we ZADD a unique
  member, ZREMRANGEBYSCORE to trim entries older than 60s, and ZCARD to count
  what's left. When the count crosses ``_FAILURE_THRESHOLD`` we SET the
  open-marker key with a fixed TTL.

- ``sz:email:circuit:<provider>`` — open-marker key. ``is_circuit_open``
  reduces to one ``EXISTS`` so the ARQ task's head-of-body check is O(1).
  Closing is implicit: TTL expiry returns the breaker to closed, with no
  manual reset surface in Phase 42.

Architectural invariant: this module lives at ``app.integrations`` and MUST
NOT import any per-domain module. The breaker has zero domain knowledge —
it is a generic Redis primitive parameterised by ``provider`` string.

References:
- D-42-14 (LOCKED): 5 failures / 60s window / 5min open TTL — values picked
  in 42-CONTEXT.md to balance Yandex Postbox SDK's ~14 emails/sec rate limit
  against the operational cost of mis-closing on a transient blip.
- D-42-15 (concurrency cap, Semaphore(5)) is enforced in the dispatcher; this
  module knows nothing of concurrency.
"""

from __future__ import annotations

import time
from typing import Final
from uuid import uuid4

import structlog
from redis.asyncio import Redis

_CIRCUIT_KEY_PREFIX: Final[str] = "sz:email:circuit:"
_WINDOW_KEY_PREFIX: Final[str] = "sz:email:circuit_window:"
_FAILURE_THRESHOLD: Final[int] = 5
_WINDOW_SECONDS: Final[int] = 60
_OPEN_TTL_SECONDS: Final[int] = 300  # 5 minutes (D-42-14)

_log = structlog.get_logger("integrations.email.circuit_breaker")


async def is_circuit_open(redis: Redis, provider: str) -> bool:
    """Return True iff the open-marker key exists for ``provider``.

    Cheap O(1) EXISTS — designed to live at the head of the ARQ
    ``dispatch_email`` task body so a short-circuit costs one Redis round trip
    rather than a full SES-V2 send. The 5-minute TTL on the open marker (set
    by ``record_failure`` once the threshold is crossed) is the only closing
    surface in Phase 42 — there is no manual reset.
    """
    exists = await redis.exists(f"{_CIRCUIT_KEY_PREFIX}{provider}")
    return bool(exists)


async def record_failure(redis: Redis, provider: str) -> None:
    """Record one provider failure in the sliding window; open the breaker on threshold.

    Steps (all on Redis):
      1. ZADD a unique-membered timestamp into the window sorted set
         (uuid hex suffix so duplicate same-ms calls do not silently dedupe).
      2. ZREMRANGEBYSCORE to drop entries older than 60s from the window.
      3. EXPIRE the window key at ``2 * _WINDOW_SECONDS`` so the structure
         self-cleans even when failures stop arriving.
      4. ZCARD to count what's left.
      5. If count >= threshold, SET the open-marker key with TTL = 5min
         and emit a structlog WARN for ops dashboards.

    The function is idempotent in the "already open" case: the SET ... EX
    just refreshes the open-marker TTL.
    """
    window_key = f"{_WINDOW_KEY_PREFIX}{provider}"
    now_ms = int(time.time() * 1000)

    # Step 1 — unique member name so two failures in the same ms do not collapse.
    await redis.zadd(window_key, {f"{now_ms}-{uuid4().hex[:8]}": now_ms})
    # Step 2 — trim old entries (older than the 60s window).
    await redis.zremrangebyscore(window_key, 0, now_ms - _WINDOW_SECONDS * 1000)
    # Step 3 — TTL safety net so the window key self-cleans.
    await redis.expire(window_key, _WINDOW_SECONDS * 2)
    # Step 4 — count fresh failures within the window.
    count = await redis.zcard(window_key)

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
