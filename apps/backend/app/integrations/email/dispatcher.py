"""Concrete EmailDispatcher impl (Phase 42 D-42-25 / EMAIL-03 / EMAIL-04).

Module renders at enqueue time inside the calling module's import-legal
context; the ARQ task body (``app.workers.tasks.dispatch_email``) NEVER
imports ``app.modules.*`` — that preserves the spirit of import-linter
contract ``integrations-not-depend-on-modules``. The dispatcher is the
ONE narrative-exception import bridge — it lives in
``app.integrations.email`` but legally imports
``app.modules.<X>.email_templates`` because per-domain template ownership
(D-39-02 / D-41-11) lives in modules.

This exception is enforced by an explicit ``ignore_imports`` entry in
``apps/backend/.importlinter`` (Plan 42-08 Task 4); function-scoped
imports do NOT bypass import-linter's grimp-backed static analysis, which
is why the escape hatch is required.

Wiring (D-42-25 / REG-29-03 — Plan 42-09 deliverable):
  ``register_arq_pool(pool)`` is called once per process by:
    - ``app.main.create_app`` (FastAPI compose root)
    - ``app.workers.__init__.WorkerSettings.on_startup`` (ARQ worker process)
  Each process holds its own pool reference.

ARQ retry / timeout policy (D-42-13 — LOCKED):
  Per-enqueue ``_max_tries=2, _expires=20`` kwargs on ``pool.enqueue_job``.
  The existing project (``app/workers/__init__.py:114-120``) lists 5 ARQ
  callables in ``WorkerSettings.functions`` with NO per-function config —
  per-enqueue overrides are the project-conventional knob.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import structlog
from arq.connections import ArqRedis

from app.integrations.email.types import EmailEnvelope

_log = structlog.get_logger("integrations.email.dispatcher")


# ---------------------------------------------------------------------------
# Per-module template registry walker.
#
# Phase 42 registers ``auth.email_templates``; Phase 43 added ``users``;
# Phase 45 (Plans 04/05/06) wires ``memberships``, ``bookings``, and
# ``payments`` registries. Adding a new domain is a single-line edit here —
# the walker is the central transport-boundary indirection that keeps the
# .importlinter exception bounded to one source -> target pair (per
# ignore_imports allowlist in ``apps/backend/.importlinter``).
# ---------------------------------------------------------------------------


def _resolve_template(template_id: str) -> Any:
    """Walk per-module template registries; raise KeyError on miss.

    The walker function (not a single import) lets future per-module
    registries plug in via a single-line edit per D-42-25. The first miss
    raises ``KeyError`` so a misspelled ``template_id`` surfaces at
    enqueue time, not at worker-job dequeue time.

    NOTE on the import-linter exception: the function-scoped import of
    ``app.modules.auth.email_templates`` DOES surface to import-linter
    (grimp parses nested imports). The legal path is the
    ``ignore_imports`` entry in ``apps/backend/.importlinter`` shipped
    in Plan 42-08 Task 4.

    Returns:
        ``EmailTemplate`` instance — typed as ``Any`` here because the
        return-type annotation cannot name ``app.modules.*`` at module
        scope without invoking the .importlinter exception twice.
        Callers consume ``.subject`` / ``.html.render(...)`` /
        ``.text.render(...)`` directly so the structural shape suffices.
    """
    from app.modules.auth.email_templates import TEMPLATES as AUTH_TEMPLATES
    from app.modules.bookings.email_templates import TEMPLATES as BOOKINGS_TEMPLATES
    from app.modules.memberships.email_templates import TEMPLATES as MEMBERSHIPS_TEMPLATES
    from app.modules.online_payments.email_templates import (
        TEMPLATES as ONLINE_PAYMENTS_TEMPLATES,
    )
    from app.modules.payments.email_templates import TEMPLATES as PAYMENTS_TEMPLATES
    from app.modules.users.email_templates import TEMPLATES as USERS_TEMPLATES

    if template_id in AUTH_TEMPLATES:
        return AUTH_TEMPLATES[template_id]
    if template_id in USERS_TEMPLATES:
        return USERS_TEMPLATES[template_id]
    if template_id in MEMBERSHIPS_TEMPLATES:
        return MEMBERSHIPS_TEMPLATES[template_id]
    if template_id in BOOKINGS_TEMPLATES:
        return BOOKINGS_TEMPLATES[template_id]
    if template_id in PAYMENTS_TEMPLATES:
        return PAYMENTS_TEMPLATES[template_id]
    if template_id in ONLINE_PAYMENTS_TEMPLATES:
        return ONLINE_PAYMENTS_TEMPLATES[template_id]
    raise KeyError(
        f"template_id {template_id!r} not in any per-module registry "
        f"(Phase 42 auth + Phase 43 users + Phase 45 memberships/bookings/payments + "
        f"Phase 52 online_payments); "
        f"add the per-module import + if-block here when a new domain registers "
        f"additional template files."
    )


# ---------------------------------------------------------------------------
# ArqRedis pool slot + defensive accessor.
#
# Mirrors the Phase 41 D-41-24 register_email_dispatcher / get_email_dispatcher
# pattern at ``app.core.dependencies``: a missing pool at the email-issuing
# call site is a hard misconfiguration, not a recoverable state.
# ---------------------------------------------------------------------------


_arq_pool: ArqRedis | None = None


def register_arq_pool(pool: ArqRedis) -> None:
    """Set the ArqRedis pool used by ``enqueue_email_dispatch``.

    Called once per process by ``app.main.create_app`` (compose root) and
    once by ``app.workers.__init__.WorkerSettings.on_startup`` (worker
    process). Each process holds its own pool reference. Idempotent —
    re-registering replaces the slot (useful for tests).
    """
    global _arq_pool
    _arq_pool = pool


def _get_arq_pool() -> ArqRedis:
    """Defensive accessor — raises ``RuntimeError`` if the pool is unregistered.

    Mirrors ``app.core.dependencies.get_payment_recorder`` (defensive raise);
    the email-issuing flow cannot proceed without an enqueue surface.
    """
    if _arq_pool is None:
        raise RuntimeError(
            "ArqRedis pool not registered. Call register_arq_pool(pool) at "
            "compose-root / worker-startup time before enqueue_email_dispatch."
        )
    return _arq_pool


# ---------------------------------------------------------------------------
# Public EmailDispatcher Protocol impl.
# ---------------------------------------------------------------------------


async def enqueue_email_dispatch(
    *,
    template_id: str,
    to: str,
    audit_correlation_id: UUID | None,
    **template_vars: Any,
) -> None:
    """Concrete EmailDispatcher impl (Phase 41 D-41-24 Protocol slot / Plan 42-08).

    Signature MUST match the EmailDispatcher Protocol at
    ``app.core.dependencies`` byte-for-byte — the ``register_email_dispatcher``
    slot accepts this callable as the Protocol implementation.

    Flow:
      1. Resolve template via per-module walker (raises KeyError on miss).
      2. Render subject/html/text against ``template_vars`` AT ENQUEUE TIME
         (D-42-07 — module renders inside the calling module's import-legal
         context; the ARQ task body never imports app.modules.*).
      3. Build an ``EmailEnvelope`` frozen dataclass (cloudpickle-safe).
      4. Enqueue ``'dispatch_email'`` on ARQ with the envelope fields as
         ``envelope_kwargs``, passing per-enqueue ARQ overrides
         ``_max_tries=2, _expires=20`` (D-42-13).

    ``audit_correlation_id=None`` is permitted at the Protocol surface, but
    ``EmailEnvelope`` mandates a UUID — we generate ``uuid4()`` here if the
    caller passes ``None`` so the downstream ``email_sent`` audit row carries
    a correlation seed.

    The envelope is serialised through cloudpickle by ARQ; ``UUID`` does not
    have a stable cross-process pickle contract via primitive-only fields,
    so we stringify it on the wire and ``UUID(...)``-reconstruct on the
    worker side (mirror of ``app.workers.tasks.dispatch_email``'s envelope
    reconstruction).
    """
    template = _resolve_template(template_id)

    # Subject is locked at the EmailTemplate dataclass (D-42-23) — no
    # interpolation. html + text take template_vars.
    rendered_html: str = template.html.render(**template_vars)
    rendered_text: str = template.text.render(**template_vars)

    correlation_id = audit_correlation_id if audit_correlation_id is not None else uuid4()

    envelope = EmailEnvelope(
        to=to,
        subject=template.subject,
        html=rendered_html,
        text=rendered_text,
        template_id=template_id,
        audit_correlation_id=correlation_id,
    )

    pool = _get_arq_pool()  # raises if unset — defensive (D-42-25)
    # ARQ enqueue with per-enqueue overrides (D-42-13 LOCKED).
    # Project convention (app/workers/__init__.py:114-120): bare callables
    # in WorkerSettings.functions with NO per-function config. ARQ 0.28's
    # per-enqueue kwargs are the only available knob:
    #   _max_tries=2 -> max retry attempts (D-42-13)
    #   _expires=20  -> job-level timeout seconds (D-42-13 timeout=20s;
    #                   ARQ uses _expires as the job-expiry deadline)
    await pool.enqueue_job(
        "dispatch_email",
        envelope_kwargs={
            "to": envelope.to,
            "subject": envelope.subject,
            "html": envelope.html,
            "text": envelope.text,
            "template_id": envelope.template_id,
            "audit_correlation_id": str(envelope.audit_correlation_id),
        },
        _max_tries=2,
        _expires=20,
    )

    _log.info(
        "email_dispatch_enqueued",
        template_id=template_id,
        to=to,
        audit_correlation_id=str(correlation_id),
    )
