"""Idempotency-Key per-route dependency (Phase 32 PAY-09 / D-32-18..D-32-20).

Hardened in Phase 66 IDM-02/05/06:
- TTL: 86400s (24h)
- Key pattern: {16,128} characters
- User-scoped Redis key: cc:idem:{user_id}:{method}:{path}:{key}
- Exception-aware shared orchestrator: idempotent_execute

Provides:
- ``IDEMPOTENCY_KEY_PATTERN`` — regex literal pattern for valid keys.
- ``verify_idempotency`` — FastAPI Depends that validates the Idempotency-Key
  header (required for POST sale/refund flows). Raises ``ValidationAppError``
  with code ``idempotency_key_required`` or ``idempotency_key_invalid_format``.
  Binds ``Depends(get_current_user)`` so the returned key is user-scoped
  (D-66-USER-SCOPE / IDM-05): prefix ``{user_id}:`` prevents cross-user replay.
- ``begin_idempotency`` — Redis SET NX EX wrapper that claims the key with a
  placeholder marker; returns True when the caller wins the race.
- ``store_idempotency_response`` / ``load_idempotency_response`` — two-phase
  envelope persistence (sha256(body) + base64(body) + status_code).
- ``body_sha256`` — convenience helper for diff checks.
- ``idempotent_response`` — composed helper that runs the pre-handler check
  and replays the cached response on retry.
- ``idempotent_execute`` — exception-aware orchestrator (IDM-06) that owns the
  full claim → run → store-success / store-error / cleanup-on-unknown-exception
  lifecycle. All wired callsites MUST use this instead of the inline block.

Redis key shape: ``cc:idem:{user_id}:{method}:{path}:{key}``. TTL: 86400s.
Encoding: JSON envelope.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Annotated, TypedDict

from fastapi import Depends, Request, Response
from redis.asyncio import Redis

from app.core.exceptions import AppError, ValidationAppError
from app.core.redis import get_redis

if TYPE_CHECKING:
    from app.core.dependencies import CurrentUser

IDEMPOTENCY_KEY_PATTERN: str = r"^[A-Za-z0-9_:-]{16,128}$"
_IDEMPOTENCY_KEY_RE = re.compile(IDEMPOTENCY_KEY_PATTERN)

IDEMPOTENCY_REDIS_PREFIX: str = "cc:idem:"
IDEMPOTENCY_TTL_SECONDS: int = 86400
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


# ---------------------------------------------------------------------------
# Import get_current_user at module level (no circular dependency exists —
# app.core.dependencies does NOT import from app.core.idempotency).
# The import is deferred below __all__ would normally go, but placed here
# so Annotated[..., Depends(get_current_user)] is resolved at class-definition
# time (FastAPI inspects the signature at route-registration time, not lazily).
# ---------------------------------------------------------------------------
from app.core.dependencies import CurrentUser as _CurrentUser, get_current_user as _get_current_user  # noqa: E402


async def verify_idempotency(
    request: Request,
    redis: Annotated[Redis, Depends(get_redis)],
    current_user: Annotated[_CurrentUser, Depends(_get_current_user)],
) -> str:
    """Validate the ``Idempotency-Key`` header; return the user-scoped route-bound key.

    Failure modes:
      - Missing header → ``ValidationAppError("idempotency_key_required")``.
      - Pattern mismatch → ``ValidationAppError("idempotency_key_invalid_format")``.

    Returns ``f"{current_user.id}:{method}:{path}:{header_value}"`` (D-66-USER-SCOPE /
    IDM-05). User-id FIRST so the same client-supplied header value from two different
    users produces two distinct Redis entries (cross-user replay fix).

    The route-method+path binding (D-32-19 / D-33-16 / CR-01) prevents the same
    header value reused across DIFFERENT endpoints from colliding in the Redis
    namespace ``cc:idem:{...}``.

    The Redis dependency is included so the per-route Depends graph already
    has a Redis client at hand for the orchestrator step (begin / store / load);
    production callers chain this with ``idempotent_execute``.

    FastAPI deduplicates the ``get_current_user`` node so adding it here does
    NOT introduce an extra DB hit when the endpoint signature already has an
    auth-requiring dependency (RBAC-04 ordering documented in 66-CONTEXT.md).
    """
    key = request.headers.get("idempotency-key")
    if key is None or key == "":
        raise ValidationAppError("idempotency_key_required")
    if not _IDEMPOTENCY_KEY_RE.match(key):
        raise ValidationAppError("idempotency_key_invalid_format")
    # User-scope + route-bind: user_id FIRST per D-66-USER-SCOPE, then
    # method:path to prevent cross-endpoint replay (D-32-19 / D-33-16 / CR-01).
    return f"{current_user.id}:{request.method}:{request.url.path}:{key}"


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
    from app.core.exceptions import ConflictError  # local import to avoid cycle

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


async def idempotent_execute(
    redis: Redis,
    key: str,
    body_bytes: bytes,
    *,
    runner: Callable[[], Awaitable[tuple[int, bytes]]],
) -> Response:
    """Exception-aware idempotency orchestrator (Phase 66 IDM-06 / D-66-LIFECYCLE-HELPER).

    Owns the complete claim → run → store-success / store-error / cleanup lifecycle.
    Generalises ``online_payments.router._outer_idempotency_replay_or_run`` and
    adds IDM-06 exception branches so every callsite gets exception-aware cleanup
    for free without duplicating the ~40-line inline block.

    Runner contract:
      The ``runner`` callable returns ``(status_code: int, body_bytes: bytes)``
      where ``body_bytes`` is the pre-serialised response body (UTF-8 JSON).

    Decision flow:
      1. Read any existing envelope / placeholder from Redis.
           - Stored envelope with matching body hash → replay verbatim.
           - Stored envelope with different body hash → 422 idempotency_key_reuse.
           - Placeholder present → 409 idempotency_in_flight.
           - Nothing → claim placeholder (SET NX), proceed to step 2.
      2. ``await runner()`` wrapped in try/except:
           - ``AppError`` → build error bytes from ``{code, message, fields}``,
             store as envelope (error is replayable), then ``raise`` so the HTTP
             exception handler returns the correct status.
             A retry with the same key+body replays the error (not
             ``idempotency_in_flight``) — IDM-06 AppError branch.
           - Any other ``Exception`` → ``await redis.delete(_redis_key(key))``
             (remove stuck placeholder), then ``raise`` so the next retry is
             fresh (not locked out for 24h) — IDM-06 unknown-exception branch.
      3. On success → store envelope and return verbatim ``Response``.

    Body-hash invariant (T-66-05): even on the error-replay path, a retry
    with the same key but a DIFFERENT body raises
    ``ValidationAppError("idempotency_key_reuse")`` — the body-hash stored
    in the error envelope is the REQUEST body hash, exactly as in the success
    envelope.

    Verbatim-replay contract (locked per 66-PATTERNS.md):
      ``Response(content=base64.b64decode(stored["body_b64"]),
               status_code=stored["status_code"],
               media_type="application/json")``
    """
    from app.core.exceptions import ConflictError  # local import to avoid cycle

    # Step 1: check for existing envelope / placeholder.
    incoming_hash = body_sha256(body_bytes)
    cached = await load_idempotency_response(redis, key)

    if cached is None:
        # Nothing in Redis — attempt to claim the placeholder.
        claimed = await begin_idempotency(redis, key)
        if not claimed:
            # Lost the SET NX race — re-read to get the winner's state.
            cached = await load_idempotency_response(redis, key)
            if cached is None or isinstance(cached, str):
                raise ConflictError("idempotency_in_flight")
            # Fallthrough to envelope replay below.
        # If claimed: cached remains None → proceed to runner.

    if cached is not None:
        if isinstance(cached, str):
            raise ConflictError("idempotency_in_flight")
        # Validate body hash (T-66-05 — same key, different body is always 422).
        if cached["body_hash"] != incoming_hash:
            raise ValidationAppError("idempotency_key_reuse")
        # Replay verbatim (locked contract).
        return Response(
            content=base64.b64decode(cached["body_b64"]),
            status_code=cached["status_code"],
            media_type="application/json",
        )

    # Step 2: we own the placeholder — run the handler.
    try:
        status_code, response_body_bytes = await runner()
    except AppError as exc:
        # IDM-06 AppError branch: store error envelope so retry replays the error.
        # Use REQUEST body hash (incoming_hash) for collision detection — same as
        # the success path, so the body-hash invariant (T-66-05) applies on
        # both success-replay and error-replay paths.
        error_bytes = json.dumps(
            {
                "code": exc.code,
                "message": exc.message,
                "fields": exc.fields,
            },
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        error_envelope: IdempotencyEnvelope = {
            "status_code": exc.status_code,
            "body_hash": incoming_hash,  # REQUEST body hash for T-66-05 enforcement
            "body_b64": base64.b64encode(error_bytes).decode("ascii"),
        }
        await redis.set(
            _redis_key(key),
            json.dumps(error_envelope, separators=(",", ":"), ensure_ascii=False),
            ex=IDEMPOTENCY_TTL_SECONDS,
        )
        raise
    except Exception:
        # IDM-06 unknown-exception branch: delete placeholder so next retry is fresh.
        await redis.delete(_redis_key(key))
        raise

    # Step 3: success — store envelope and return.
    # Store with REQUEST body hash (incoming_hash) so replay validation compares
    # the incoming request body against the original request body (not the response).
    success_envelope: IdempotencyEnvelope = {
        "status_code": status_code,
        "body_hash": incoming_hash,
        "body_b64": base64.b64encode(response_body_bytes).decode("ascii"),
    }
    await redis.set(
        _redis_key(key),
        json.dumps(success_envelope, separators=(",", ":"), ensure_ascii=False),
        ex=IDEMPOTENCY_TTL_SECONDS,
    )
    return Response(
        content=response_body_bytes,
        status_code=status_code,
        media_type="application/json",
    )


__all__ = (
    "IDEMPOTENCY_KEY_PATTERN",
    "IDEMPOTENCY_REDIS_PREFIX",
    "IDEMPOTENCY_TTL_SECONDS",
    "IdempotencyEnvelope",
    "begin_idempotency",
    "body_sha256",
    "idempotent_execute",
    "idempotent_response",
    "load_idempotency_response",
    "store_idempotency_response",
    "verify_idempotency",
)
