"""Phase 43 CR-04 regression — deactivate_user is one atomic UoW.

Pre-fix: invalidate_all_families_for_user → revoke_all_sessions called
session.commit() mid-flow, so the UPDATE users SET is_active=false AND the
session_revoked_all audit row committed in tx-1, while the user_deactivated
audit row committed in tx-2. Failure of tx-2 left the system in:
  - is_active=false COMMITTED
  - session_revoked_all COMMITTED
  - refresh_tokens revoked COMMITTED
  - user_deactivated MISSING

Fix: invalidate_all_families_for_user now calls _revoke_all_sessions_no_commit,
so the whole flow lives in ONE UoW with a single commit at the end of
deactivate_user. A failure anywhere in between rolls everything back.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit as audit_module
from app.core.audit_models import AuditLog
from app.core.models import User
from app.core.permissions import Role

from .conftest import _csrf_headers

pytestmark = pytest.mark.asyncio


async def test_deactivate_atomic_rollback_on_audit_failure(
    monkeypatch: pytest.MonkeyPatch,
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """If the final audit.emit / commit fails, the UPDATE + session revoke roll back.

    simulated audit_log failure post-revoke: audit.emit raises RuntimeError on
    the user_deactivated event so we can assert the whole UoW rolls back
    including the is_active=false flip (CR-04 invariant).
    """
    # Seed a reception user to deactivate.
    target = User(
        email="rollback-target-cr04@example.com",
        email_verified=True,
        password_hash="$argon2id$placeholder",
        role=Role.RECEPTION,
        full_name="Rollback Target",
        is_active=True,
        status="active",
    )
    db_session.add(target)
    await db_session.commit()
    await db_session.refresh(target)
    target_id: UUID = target.id

    # Monkeypatch audit.emit to raise on the user_deactivated event
    # specifically (the second emit in the deactivate flow).
    original_emit = audit_module.emit
    call_log: list[str] = []

    async def failing_emit(session: AsyncSession, event: str, *args: object, **kwargs: object) -> None:  # type: ignore[override]
        call_log.append(event)
        if event == "user_deactivated":
            raise RuntimeError("simulated audit_log failure post-revoke")
        return await original_emit(session, event, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(audit_module, "emit", failing_emit)

    # Act — expect failure (RuntimeError propagates through ASGITransport and raises
    # in the test, since unhandled exceptions in ASGI apps surface to the caller
    # when using httpx ASGITransport).
    with pytest.raises(RuntimeError, match="simulated audit_log failure post-revoke"):
        await authed_client_owner.patch(
            f"/api/v1/users/{target_id}/deactivate",
            headers=_csrf_headers(authed_client_owner),
        )

    # Assert: BOTH emit attempts were made in the correct order.
    assert "session_revoked_all" in call_log, (
        "session_revoked_all emit was never attempted — flow did not reach the "
        "revoke step. Check that deactivate_user calls the session invalidator."
    )
    assert "user_deactivated" in call_log, (
        "user_deactivated emit was never attempted — flow did not reach the "
        "final audit step. Check that the RuntimeError was actually raised."
    )

    # Roll back the session to undo any uncommitted changes left by the failed
    # route handler. In the SAVEPOINT test harness, session.rollback() issues
    # ROLLBACK TO SAVEPOINT, undoing all pending (uncommitted) DB mutations.
    # This is the "cleanup" that the service's exception handler would normally
    # do (FastAPI's 500 handler rolls back the session via get_db dependency
    # teardown). In this test we share the db_session directly, so we must
    # replicate that cleanup ourselves before querying state.
    await db_session.rollback()

    # Critical CR-04 invariant: user row is STILL is_active=True (UPDATE rolled back).
    # With the CR-04 fix, the service has NO intermediate session.commit() calls,
    # so the entire deactivate flow (UPDATE users + UPDATE refresh_tokens +
    # audit inserts) was pending in one SAVEPOINT that just rolled back.
    await db_session.refresh(target)
    assert target.is_active is True, (
        "CR-04 regression — UPDATE users SET is_active=false committed before "
        "the final audit.emit failure. The whole deactivate flow MUST be one "
        "atomic UoW; the mid-flow commit inside revoke_all_sessions must be gone."
    )

    # The session_revoked_all audit row should ALSO be rolled back (same tx).
    audit_rows = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "session_revoked_all",
                AuditLog.resource_id == target_id,
            )
        )
    ).scalars().all()
    assert len(audit_rows) == 0, (
        f"CR-04 regression — {len(audit_rows)} session_revoked_all audit row(s) "
        "committed despite the user_deactivated failure. The whole flow must "
        "roll back together as one atomic UoW."
    )


async def test_deactivate_happy_path_commits_both_audit_rows(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Positive control — without the audit failure, both rows commit together."""
    target = User(
        email="happy-target-cr04@example.com",
        email_verified=True,
        password_hash="$argon2id$placeholder",
        role=Role.RECEPTION,
        full_name="Happy Target",
        is_active=True,
        status="active",
    )
    db_session.add(target)
    await db_session.commit()
    await db_session.refresh(target)
    target_id: UUID = target.id

    response = await authed_client_owner.patch(
        f"/api/v1/users/{target_id}/deactivate",
        headers=_csrf_headers(authed_client_owner),
    )
    assert response.status_code == 204, response.text

    await db_session.refresh(target)
    assert target.is_active is False

    # Both audit rows present.
    audit_actions = {
        row.action
        for row in (
            await db_session.execute(
                select(AuditLog).where(AuditLog.resource_id == target_id)
            )
        ).scalars().all()
    }
    # session_revoked_all uses resource_id=target_id; user_deactivated also resource_id=target_id.
    assert "session_revoked_all" in audit_actions, (
        "session_revoked_all audit row missing after successful deactivate. "
        "Check that _revoke_all_sessions_no_commit calls audit.emit."
    )
    assert "user_deactivated" in audit_actions, (
        "user_deactivated audit row missing after successful deactivate."
    )
