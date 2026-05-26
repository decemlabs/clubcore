"""Idempotency-Key per-route dependency (Phase 32 PAY-09 / D-32-18..D-32-20).

Provides:
- ``IDEMPOTENCY_KEY_PATTERN`` — regex literal pattern for valid keys.
- ``verify_idempotency`` — FastAPI Depends that validates the Idempotency-Key
  header (required for POST sale/refund flows). Raises ``ValidationAppError``
  with code ``idempotency_key_required`` or ``idempotency_key_invalid_format``.
- ``begin_idempotency`` — Redis SET NX EX wrapper that claims the key with a
  placeholder marker; returns True when the caller wins the race.
- ``store_idempotency_response`` / ``load_idempotency_response`` — two-phase
  envelope persistence (sha256(body) + base64(body) + status_code).
- ``body_sha256`` — convenience helper for diff checks.
- ``idempotent_response`` — composed helper that runs ``run_handler`` once
  per key, replays the cached response on retry, and surfaces
  ``ConflictError("idempotency_in_flight")`` when the placeholder is still
  present, ``ValidationAppError("idempotency_key_reuse")`` on body diff.

Redis key shape: ``cc:idem:{key}``. TTL: 3600s. Encoding: JSON envelope.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from typing import Annotated, TypedDict

from fastapi import Depends, Request
from redis.asyncio import Redis

from app.core.exceptions import ConflictError, ValidationAppError
from app.core.redis import get_redis

IDEMPOTENCY_KEY_PATTERN: str = r"^[A-Za-z0-9_:-]{1,128}$"
_IDEMPOTENCY_KEY_RE = re.compile(IDEMPOTENCY_KEY_PATTERN)

IDEMPOTENCY_REDIS_PREFIX: str = "cc:idem:"
IDEMPOTENCY_TTL_SECONDS: int = 3600
_PLACEHOLDER: str = "__in_flight__"


class IdempotencyEnvelope(TypedDict):
    """Stored shape for replayable responses (D-32-19)."""

    status_code: int
    body_hash: str
    body_b64: str


def _redis_key(key: str) -> str:
    return f"{IDEMPOTENCY_REDIS_PREFIX}{key}"


def body_sha256(payload: bytes) -> str:
    """Return ``hexdigest()`` of ``sha256(payload)`` (64 chars)."""
    return hashlib.sha256(payload).hexdigest()


async def verify_idempotency(
    request: Request,
    redis: Annotated[Redis, Depends(get_redis)],
) -> str:
    """Validate the ``Idempotency-Key`` header; return the route-bound key string.

    Failure modes:
      - Missing header → ``ValidationAppError("idempotency_key_required")``.
      - Pattern mismatch → ``ValidationAppError("idempotency_key_invalid_format")``.

    Returns ``f"{method}:{path}:{header_value}"`` so the same client-supplied
    header value reused across DIFFERENT endpoints (e.g. sale + cancel +
    refund) cannot collide in the Redis namespace ``cc:idem:{...}``. This
    is the route-binding invariant referenced by D-32-19 / D-33-16 — the
    prior return of the bare header value allowed cross-route replay where
    a sale envelope could be served as a refund response when bodies
    happened to hash equal.

    The Redis dependency is included so the per-route Depends graph already
    has a Redis client at hand for the orchestrator step (begin / store /
    load); production callers chain this with ``idempotent_response``.
    """
    key = request.headers.get("idempotency-key")
    if key is None or key == "":
        raise ValidationAppError("idempotency_key_required")
    if not _IDEMPOTENCY_KEY_RE.match(key):
        raise ValidationAppError("idempotency_key_invalid_format")
    # Bind route+method so the same header value cannot replay across
    # endpoints (D-32-19 / D-33-16 / CR-01 from Phase 33 review).
    return f"{request.method}:{request.url.path}:{key}"


async def begin_idempotency(redis: Redis, key: str) -> bool:
    """Claim the key with the in-flight placeholder.

    Returns True iff the SET NX won the race (caller proceeds to run the
    handler). When False, the caller MUST inspect ``load_idempotency_response``
    to decide whether to replay or raise ``idempotency_in_flight``.
    """
    result = await redis.set(
        _redis_key(key),
        _PLACEHOLDER,
        nx=True,
        ex=IDEMPOTENCY_TTL_SECONDS,
    )
    return bool(result)


async def store_idempotency_response(
    redis: Redis,
    key: str,
    *,
    status_code: int,
    body_bytes: bytes,
) -> None:
    """Replace the in-flight placeholder with the full envelope.

    Stored as JSON so ``load_idempotency_response`` can roundtrip the
    placeholder marker and the envelope through a single GET. TTL is
    refreshed to ``IDEMPOTENCY_TTL_SECONDS`` so replay survives the same
    window.
    """
    envelope: IdempotencyEnvelope = {
        "status_code": status_code,
        "body_hash": body_sha256(body_bytes),
        "body_b64": base64.b64encode(body_bytes).decode("ascii"),
    }
    await redis.set(
        _redis_key(key),
        json.dumps(envelope, separators=(",", ":"), ensure_ascii=False),
        ex=IDEMPOTENCY_TTL_SECONDS,
    )


async def load_idempotency_response(
    redis: Redis,
    key: str,
) -> IdempotencyEnvelope | str | None:
    """Return the placeholder sentinel, parsed envelope, or None.

    - ``None`` — key never claimed (caller proceeds with ``begin_idempotency``).
    - ``"__in_flight__"`` (str literal == ``_PLACEHOLDER``) — concurrent caller
      holds the lock; consumer raises ``idempotency_in_flight``.
    - ``IdempotencyEnvelope`` — completed response; consumer replays.
    """
    raw = await redis.get(_redis_key(key))
    if raw is None:
        return None
    if raw == _PLACEHOLDER:
        return _PLACEHOLDER
    try:
        envelope_data = json.loads(raw)
    except json.JSONDecodeError:
        # Defensive: corrupted entry → treat as unset so the caller can claim.
        return None
    if not isinstance(envelope_data, dict):
        return None
    return IdempotencyEnvelope(
        status_code=int(envelope_data["status_code"]),
        body_hash=str(envelope_data["body_hash"]),
        body_b64=str(envelope_data["body_b64"]),
    )


async def idempotent_response(
    redis: Redis,
    key: str,
    body_bytes: bytes,
) -> IdempotencyEnvelope | None:
    """Check whether the incoming request matches a stored idempotent response.

    Decision matrix:
      - No stored entry → claim placeholder, return None (caller runs handler
        then calls ``store_idempotency_response``).
      - Placeholder present → raise ``ConflictError("idempotency_in_flight")``.
      - Stored envelope with matching ``body_hash`` → return envelope so the
        caller can replay verbatim.
      - Stored envelope with different ``body_hash`` →
        ``ValidationAppError("idempotency_key_reuse")``.
    """
    cached = await load_idempotency_response(redis, key)
    if cached is None:
        claimed = await begin_idempotency(redis, key)
        if claimed:
            return None
        # Lost the race to a concurrent claim → re-read.
        cached = await load_idempotency_response(redis, key)
        if cached is None or isinstance(cached, str):
            raise ConflictError("idempotency_in_flight")
        # Fallthrough into envelope comparison.
    if isinstance(cached, str):
        raise ConflictError("idempotency_in_flight")
    # cached narrowed to IdempotencyEnvelope (TypedDict / Mapping).
    incoming_hash = body_sha256(body_bytes)
    if cached["body_hash"] != incoming_hash:
        raise ValidationAppError("idempotency_key_reuse")
    return cached


__all__ = (
    "IDEMPOTENCY_KEY_PATTERN",
    "IDEMPOTENCY_REDIS_PREFIX",
    "IDEMPOTENCY_TTL_SECONDS",
    "IdempotencyEnvelope",
    "begin_idempotency",
    "body_sha256",
    "idempotent_response",
    "load_idempotency_response",
    "store_idempotency_response",
    "verify_idempotency",
)
