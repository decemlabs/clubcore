"""Email transport DTOs — locked at Phase 42 D-42-16 (envelope) + D-42-13 (result classification).

Two frozen dataclasses form the entire typed surface of the email-transport boundary:

- ``EmailEnvelope`` is the immutable payload handed across the dispatch boundary
  (service → ARQ enqueue → worker → provider adapter). Six fields exactly, locked
  at D-42-16; cloudpickle-safe (frozen dataclass with primitives + UUID) so ARQ
  enqueue serializes cleanly without custom hooks.
- ``EmailSendResult`` is the typed outcome the provider adapter returns to the
  dispatcher (and which the dispatcher writes to ``email_send_log.status``).
  ``classification`` is a closed ``Literal`` so downstream code (dispatcher row
  insertion, audit-event picker) can switch on it without runtime guards leaking
  free-form strings into the audit chain (D-42-13).

Shape mirrors ``app.integrations.telegram.sender.SendResult`` (PATTERNS.md §1):
frozen dataclass with classified failure modes; transport errors are values,
not exceptions, so handler atomicity is observable without try/except gymnastics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID


@dataclass(frozen=True)
class EmailEnvelope:
    """Immutable email payload crossing the dispatch boundary (D-42-16).

    All six fields are mandatory and lock the wire shape ARQ enqueues; do not
    add ``Optional`` defaults here — the dispatcher is responsible for assembling
    a complete envelope before handing it to the transport.

    - ``to``: recipient address (single RFC5322 mailbox; bulk send is not in v1.6).
    - ``subject`` / ``html`` / ``text``: rendered template output. ``text`` is
      mandatory (no degraded HTML-only path) so deliverability heuristics never
      see a missing alt-part.
    - ``template_id``: literal identifier from ``LOCKED_EMAIL_TEMPLATES``
      (Phase 41 Plan 41-03). The AST gate forbids non-literal values at every
      dispatcher callsite.
    - ``audit_correlation_id``: UUID that ties this envelope to its triggering
      audit row (``email_send_requested``) and, after the send completes, to the
      ``email_sent`` / ``email_send_failed`` audit row. Persisted on
      ``email_send_log.audit_correlation_id`` for forensic continuity (D-42-35).
    """

    to: str
    subject: str
    html: str
    text: str
    template_id: str
    audit_correlation_id: UUID


@dataclass(frozen=True)
class EmailSendResult:
    """Outcome of one transport attempt (D-42-13).

    ``classification`` is the closed taxonomy the dispatcher writes to
    ``email_send_log.status`` and that downstream retry / circuit-breaker logic
    switches on:

    - ``ok``: provider accepted the message (2xx). ``provider_message_id`` is
      populated; ``error`` is None.
    - ``blocked``: provider rejected the recipient permanently (hard bounce
      from prior history, suppression list, complained recipient). DO NOT retry.
    - ``transient_error``: provider returned 5xx / network failure / 429. ARQ
      should retry per its backoff schedule.
    - ``permanent_error``: provider returned 4xx other than ``blocked`` (malformed
      address, invalid template, auth failure). DO NOT retry — operator alert.

    Mirrors the Telegram ``SendResult`` taxonomy (PATTERNS.md §1) but explicit
    on the retry-vs-give-up split because the email provider returns richer
    failure information than Telegram's BadRequest/Forbidden pair.
    """

    ok: bool
    classification: Literal["ok", "blocked", "transient_error", "permanent_error"]
    provider_message_id: str | None = None
    error: str | None = None
