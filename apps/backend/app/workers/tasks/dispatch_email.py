"""ARQ task: dispatch_email — Phase 42 EMAIL-03 / EMAIL-06 / Plan 42-08 Task 3.

Per D-42-07 (module renders, worker transports): this worker file MUST NOT
import ``app.modules.*`` — the ``EmailEnvelope`` arrives pre-rendered from
the dispatcher (``app.integrations.email.dispatcher.enqueue_email_dispatch``).
The worker file legally imports ``app.integrations.email.*`` (transport layer
always allowed for workers per ``app/workers/__init__.py:1-21`` rationale).

ARQ config (D-42-13): ``max_tries=2``, ``timeout=20s`` are wired via
per-enqueue kwargs in the dispatcher (``_max_tries=2, _expires=20`` on
``pool.enqueue_job``). Per-function ARQ wrapper REJECTED because
``WorkerSettings.functions`` in the existing project
(``app/workers/__init__.py:114-120``) lists bare callables with no
per-function settings. Provider SDK retries are disabled at the client
layer (D-42-02) so ARQ is the only retry mechanism (Pitfall 3 mitigation).

Concurrency cap (D-42-15): module-level ``asyncio.Semaphore(5)``. Yandex
Cloud Postbox default rate limit ~14 emails/sec; 5 concurrent leaves safe
margin and matches the LOCKED value from the phase context.

Circuit breaker (D-42-14): Redis sliding-window 5 failures / 60s opens
key ``sz:email:circuit:yandex_postbox`` with 5min TTL. Open circuit
short-circuits to ``EmailSendResult(ok=False, classification='transient_error',
error='circuit_open')`` WITHOUT touching the provider. The
``error='circuit_open'`` sentinel is the discriminator that maps to audit
reason ``'circuit_open'`` (vs ``'provider_5xx'`` for a real upstream 5xx).

Audit reason mapping (LOCKED — matches ``EmailSendFailedPayload.reason``
Literal in Phase 41 INFRA-35):

  classification='blocked'                           -> reason='invalid_recipient'
  classification='transient_error' + error=='circuit_open' -> reason='circuit_open'
  classification='transient_error' + other error     -> reason='provider_5xx'
  classification='permanent_error'                   -> reason='provider_5xx'

(Webhook-only reasons 'bounce' / 'complaint' are owned by Plan 42-10.)

Audit ordering (D-42-34 / Pitfall 2): ``audit.emit`` BEFORE
``session.commit`` so the audit row commits atomically with the
``email_send_log`` INSERT.

Worker ``ctx`` keys required:
  - ``sessionmaker``: ``async_sessionmaker[AsyncSession]`` from
    ``WorkerSettings.on_startup``
  - ``email_client``: ``EmailClient | SandboxEmailClient`` instance wired
    by Plan 42-09 worker startup
  - ``redis``: ``redis.asyncio.Redis`` client wired by Plan 42-09 worker
    startup
"""

from __future__ import annotations

import asyncio
from typing import Any, Final, Literal
from uuid import UUID

import structlog

from app.core import audit
from app.integrations.email.circuit_breaker import is_circuit_open, record_failure
from app.integrations.email.models import EmailSendLog
from app.integrations.email.types import EmailEnvelope, EmailSendResult

_log: Final = structlog.get_logger("workers.tasks.dispatch_email")
_SEMAPHORE: Final[asyncio.Semaphore] = asyncio.Semaphore(5)
_PROVIDER: Final[str] = "yandex_postbox"  # circuit-breaker key suffix

# LOCKED classification -> audit reason map. Literal targets
# ``app.core.audit_payloads.EmailSendFailedPayload.reason`` exactly. The
# dispatcher path emits exactly 3 of the 5 Literal values; the remaining
# 2 ('bounce' / 'complaint') are owned by the webhook in Plan 42-10.
_FailReason = Literal["provider_5xx", "circuit_open", "invalid_recipient"]


def _audit_reason_for(result: EmailSendResult) -> _FailReason:
    """Map ``EmailSendResult`` into the locked ``EmailSendFailedPayload.reason`` Literal.

    Webhook-only reasons (``'bounce'`` / ``'complaint'``) are owned by
    Plan 42-10 and are NEVER returned from this dispatcher path.
    """
    assert result.ok is False, "_audit_reason_for is only called for non-ok results"
    if result.classification == "blocked":
        return "invalid_recipient"
    if result.classification == "transient_error" and result.error == "circuit_open":
        return "circuit_open"
    # All other transient_error (real 5xx / network) AND permanent_error
    # (4xx non-blocked, exhausted retries) collapse to provider_5xx for the
    # audit reason. Fine-grained classification is preserved on the
    # EmailSendLog row + provider_error_code field; the audit Literal is
    # the ops-dashboard-friendly bucket.
    return "provider_5xx"


async def dispatch_email(ctx: dict[str, Any], envelope_kwargs: dict[str, Any]) -> str:
    """Reconstruct envelope, send via ctx['email_client'], record + audit, return summary.

    Returns ``'sent'`` on ok, ``'failed'`` otherwise. ARQ persists the
    return value to its result store; the string is a stable summary
    surface for ops queries.
    """
    # 1. Reconstruct envelope (cloudpickle-safe per D-42-16; audit_correlation_id
    #    arrived as str(UUID) from the dispatcher).
    envelope = EmailEnvelope(
        to=envelope_kwargs["to"],
        subject=envelope_kwargs["subject"],
        html=envelope_kwargs["html"],
        text=envelope_kwargs["text"],
        template_id=envelope_kwargs["template_id"],
        audit_correlation_id=UUID(envelope_kwargs["audit_correlation_id"]),
    )

    session_factory = ctx["sessionmaker"]
    email_client = ctx["email_client"]
    redis = ctx["redis"]

    # 2. Acquire concurrency token + check breaker; either short-circuit
    #    or call the provider.
    async with _SEMAPHORE:
        if await is_circuit_open(redis, _PROVIDER):
            result = EmailSendResult(
                ok=False,
                classification="transient_error",
                provider_message_id=None,
                error="circuit_open",  # sentinel — _audit_reason_for keys off this
            )
            _log.warning(
                "email_circuit_short_circuit",
                provider=_PROVIDER,
                template_id=envelope.template_id,
            )
        else:
            result = await email_client.send_email(envelope)
            # Only arm the breaker on transient_error from a real provider
            # call. Permanent_error (4xx non-blocked) is a programmer/config
            # bug, not a transient health signal; blocked is recipient-level.
            if result.classification == "transient_error":
                await record_failure(redis, _PROVIDER)

    # 3. INSERT email_send_log row + audit.emit (BEFORE commit per Pitfall 2)
    #    + commit. Single session, one transaction; audit row commits
    #    atomically with the EmailSendLog INSERT.
    async with session_factory() as session:
        log_row = EmailSendLog(
            audit_correlation_id=envelope.audit_correlation_id,
            to_address=envelope.to,
            template_id=envelope.template_id,
            provider=_PROVIDER,
            provider_message_id=result.provider_message_id,
            status="sent" if result.ok else "rejected",
            bounce_type=None,
        )
        session.add(log_row)
        # Flush so the server-side gen_random_uuid() PK populates log_row.id
        # before audit.emit reads resource_id (also surfaces FK/CHECK errors
        # synchronously rather than at commit time).
        await session.flush()

        if result.ok:
            await audit.emit(
                session,
                "email_sent",
                actor_user_id=None,
                resource_type="email_send_log",
                resource_id=log_row.id,
                # Flattened kwargs per **payload: Any contract (D-42-34 / CR-01 fix).
                # UUID is str-cast for JSONB serialisability — mirrors router.py:192.
                audit_correlation_id=str(envelope.audit_correlation_id),
                template_id=envelope.template_id,
                to_email=envelope.to,
                provider_message_id=result.provider_message_id,
            )
        else:
            reason = _audit_reason_for(result)
            await audit.emit(
                session,
                "email_send_failed",
                actor_user_id=None,
                resource_type="email_send_log",
                resource_id=log_row.id,
                # Flattened kwargs per **payload: Any contract (D-42-34 / CR-01 fix).
                audit_correlation_id=str(envelope.audit_correlation_id),
                template_id=envelope.template_id,
                to_email=envelope.to,
                reason=reason,
                provider_error_code=result.error,
            )
        await session.commit()

    _log.info(
        "dispatch_email_complete",
        status="sent" if result.ok else "failed",
        classification=result.classification,
        template_id=envelope.template_id,
        provider_message_id=result.provider_message_id,
    )
    return "sent" if result.ok else "failed"
