"""Request-scoped actor identity ContextVar (Phase 41 INFRA-39 / D-41-08).

Mirrors RequestIdMiddleware's contextvars pattern (app/core/middleware.py).
Populated by:
  - ActorContextMiddleware (HTTP path) — sets baseline None; the
    ``get_current_user`` dependency overwrites with the resolved identity
    once auth succeeds (middleware runs BEFORE per-route dependencies, so
    request.state.current_user is not yet populated at middleware entry).
  - WorkerSettings.on_job_start (ARQ path) — reads job kwargs.

Consumed by:
  - audit.emit() — reads .get() when caller omits actor_email_snapshot=...

Override path (D-41-08):
  - audit.emit(..., actor_email_snapshot="explicit@value") wins over the
    ContextVar for batch reconciliation jobs / retroactive audits.

System emits (D-41-10):
  - When actor_user_id is None (cron without job-kwargs attribution, the
    anti-oracle unknown-email branch of password_reset_requested), the
    ContextVar lookup is skipped and audit_log writes
    actor_email_snapshot=NULL alongside actor_user_id=NULL.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import TypedDict
from uuid import UUID


class ActorIdentity(TypedDict):
    """The minimum identity carried alongside an audit-row write."""

    user_id: UUID
    email: str


actor_context_var: ContextVar[ActorIdentity | None] = ContextVar(
    "clubcore_actor_context",
    default=None,
)
"""ContextVar holding the resolved acting user's (id, email) for the
current request OR ARQ job. None during unauthenticated requests and
system-emitted audit events (D-41-10)."""


def set_actor(identity: ActorIdentity | None) -> Token[ActorIdentity | None]:
    """Set the contextvar; return token for later .reset() in a try/finally."""
    return actor_context_var.set(identity)


def reset_actor(token: Token[ActorIdentity | None]) -> None:
    """Reset the contextvar to its previous value."""
    actor_context_var.reset(token)


def get_current_actor() -> ActorIdentity | None:
    """Return the current actor identity, or None when not in an
    authenticated request / ARQ job context."""
    return actor_context_var.get()
