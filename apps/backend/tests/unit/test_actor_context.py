"""Unit tests for the Phase 41 INFRA-39 / D-41-08 actor_context wiring.

Covers:
  - Default contextvar value is None (cron / unauthenticated baseline — D-41-10).
  - set_actor / reset_actor round-trip restores to None.
  - audit.emit() reads actor_context_var when caller omits the kwarg, AND
    the persisted AuditLog row carries actor_email_snapshot from the
    contextvar (D-41-08).
  - Explicit audit.emit(..., actor_email_snapshot="...") override wins
    over the contextvar (D-41-08 override path).
  - System emit with actor_user_id=None writes NULL actor_email_snapshot
    even when the contextvar is populated (D-41-10).
  - Defensive identity mismatch (T-41-07-02): when the contextvar's
    user_id does NOT match the passed actor_user_id, snapshot stays None
    (no misattribution).
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.core import audit
from app.core.actor_context import (
    get_current_actor,
    reset_actor,
    set_actor,
)


class _CapturingSession:
    """Stub AsyncSession that captures the AuditLog row passed to .add().

    Only `.add` is needed — audit.emit() never calls commit/flush/refresh.
    """

    def __init__(self) -> None:
        self.added: list[Any] = []

    def add(self, row: Any) -> None:
        self.added.append(row)


def test_get_current_actor_default_is_none() -> None:
    # Sanity baseline — outside any explicit set, the contextvar holds None.
    # This is the D-41-10 system-emit envelope: cron jobs and unauthenticated
    # requests rely on this default.
    assert get_current_actor() is None


def test_set_and_reset_roundtrip() -> None:
    uid = uuid4()
    assert get_current_actor() is None
    token = set_actor({"user_id": uid, "email": "owner@clubcore.local"})
    try:
        ident = get_current_actor()
        assert ident is not None
        assert ident["user_id"] == uid
        assert ident["email"] == "owner@clubcore.local"
    finally:
        reset_actor(token)
    assert get_current_actor() is None


async def test_audit_emit_reads_contextvar_when_kwarg_omitted() -> None:
    uid = uuid4()
    rid = uuid4()
    session = _CapturingSession()
    token = set_actor({"user_id": uid, "email": "operator@clubcore.local"})
    try:
        # 'login_success' / 'session' — a locked pair with free-form payload
        # (pre-v1.4, no Pydantic schema validation), so we can pass minimal kwargs.
        await audit.emit(
            session,  # type: ignore[arg-type]
            "login_success",
            actor_user_id=uid,
            resource_type="session",
            resource_id=rid,
        )
    finally:
        reset_actor(token)

    assert len(session.added) == 1
    row = session.added[0]
    assert row.actor_user_id == uid
    assert row.actor_email_snapshot == "operator@clubcore.local"


async def test_audit_emit_explicit_override_wins_over_contextvar() -> None:
    uid = uuid4()
    rid = uuid4()
    session = _CapturingSession()
    token = set_actor({"user_id": uid, "email": "from-contextvar@clubcore.local"})
    try:
        await audit.emit(
            session,  # type: ignore[arg-type]
            "login_success",
            actor_user_id=uid,
            resource_type="session",
            resource_id=rid,
            actor_email_snapshot="explicit-batch@clubcore.local",
        )
    finally:
        reset_actor(token)

    row = session.added[0]
    assert row.actor_email_snapshot == "explicit-batch@clubcore.local"


async def test_audit_emit_system_event_writes_null_snapshot() -> None:
    # D-41-10: actor_user_id=None ⇒ snapshot must stay None even when the
    # contextvar happens to be populated. This is the cron / anti-oracle
    # unknown-email branch behaviour.
    session = _CapturingSession()
    token = set_actor({"user_id": uuid4(), "email": "leaked@clubcore.local"})
    try:
        # 'login_failed' / 'login_attempt' is a locked pair commonly emitted
        # with actor_user_id=None (the email is unknown / wrong).
        await audit.emit(
            session,  # type: ignore[arg-type]
            "login_failed",
            actor_user_id=None,
            resource_type="login_attempt",
            email="anonymous@nowhere",
            reason="bad_password",
            ip="127.0.0.1",
        )
    finally:
        reset_actor(token)

    row = session.added[0]
    assert row.actor_user_id is None
    assert row.actor_email_snapshot is None


async def test_audit_emit_user_id_mismatch_leaves_snapshot_none() -> None:
    # T-41-07-02 defensive identity check: a contextvar populated for user A
    # must not bleed into an audit row attributed to user B.
    contextvar_user = uuid4()
    explicit_user = uuid4()
    assert contextvar_user != explicit_user
    rid = uuid4()
    session = _CapturingSession()
    token = set_actor({"user_id": contextvar_user, "email": "userA@clubcore.local"})
    try:
        await audit.emit(
            session,  # type: ignore[arg-type]
            "login_success",
            actor_user_id=explicit_user,
            resource_type="session",
            resource_id=rid,
        )
    finally:
        reset_actor(token)

    row = session.added[0]
    assert row.actor_user_id == explicit_user
    # Snapshot stayed None because contextvar's user_id != explicit_user.
    assert row.actor_email_snapshot is None


async def test_worker_on_job_start_sets_actor_baseline_none() -> None:
    # D-41-08 ARQ envelope: on_job_start writes None to the contextvar so
    # the job body either calls set_actor() itself (attributed jobs) or
    # leaves it None (system cron). on_job_end resets cleanly.
    from app.workers import WorkerSettings

    # Pre-populate the contextvar to confirm on_job_start REPLACES it with None.
    outer_token = set_actor({"user_id": uuid4(), "email": "outer@clubcore.local"})
    try:
        ctx: dict[str, Any] = {
            "job_id": "test-job-1",
            "function_name": "test_fn",
        }
        await WorkerSettings.on_job_start(ctx)
        # Inside the "job", the actor envelope is None.
        assert get_current_actor() is None
        # ctx stashes the token for on_job_end (Phase 41 D-41-08).
        assert "_actor_token" in ctx

        # Simulate a job body that attributes itself.
        uid = uuid4()
        set_actor({"user_id": uid, "email": "job-actor@clubcore.local"})
        assert get_current_actor() == {
            "user_id": uid,
            "email": "job-actor@clubcore.local",
        }

        await WorkerSettings.on_job_end(ctx)
        # on_job_end resets back to the outer envelope (the value the
        # contextvar had immediately before on_job_start's set(None)).
        outer = get_current_actor()
        assert outer is not None
        assert outer["email"] == "outer@clubcore.local"
    finally:
        reset_actor(outer_token)
