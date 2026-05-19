"""Pitfall 4 — INSERT-only invariant at the invitation-accept boundary.

This file is the grep-discoverable security-claim carrier for Phase 46
verification (VER-* will grep this path for the INSERT-only invariant
documentation). The single test verifies the full Phase 43 → Phase 44
lineage:

  - Phase 41 migration 0022 — partial-UNIQUE
    ``(lower(email)) WHERE deleted_at IS NULL`` allows a soft-deleted
    user's email to be re-INSERTed as a NEW user row.
  - Phase 43 D-43-13 — ``create_user`` 4-branch idempotent INSERT
    treats the soft-deleted-email case as a fall-through to the
    "no row" branch (INSERT new row, partial-UNIQUE permits it).
  - Phase 44 D-44-20 — ``password_reset_service.accept_invitation``
    NEVER INSERTs a users row; it UPDATEs the existing
    ``status='pending_invitation'`` row. By the time the accept-flow
    runs against the re-invited row, the row's ``id`` is the NEW one
    (B.id), not the soft-deleted one (A.id).

Pitfall 4 — "invite-accept-INSERT-only" — guards against the
regression where an accept-flow accidentally resurrects a soft-deleted
user (UPDATE deleted_at=NULL on the old row instead of operating on the
new row). The test asserts:

  - ``A.id != B.id`` — the re-invite created a NEW user row.
  - After accept, the accepted user's id equals B.id (NOT A.id).
  - Row A is untouched: ``deleted_at`` remains non-NULL, ``status``
    unchanged from its soft-deleted state, ``password_hash`` unchanged.
  - Row B has the post-accept post-state: ``status='active'``,
    ``email_verified=True``, ``password_hash`` non-NULL, ``full_name``
    set to the re-invite's value.
  - The ``user_invitation_accepted`` audit row's ``accepted_user_id``
    is B.id, NOT A.id.

References:
  - .planning/research/PITFALLS.md § Pitfall 4 (invite-accept-INSERT-only)
  - .planning/phases/44-invitation-password-reset-flow/44-CONTEXT.md
    (D-44-20 — INSERT-only invariant at the accept boundary)
  - .planning/phases/43-multi-user-admin-module/43-08-SUMMARY.md
    (Phase 43 INSERT-only at create-user; this plan extends to accept)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.core.database import get_db
from app.core.dependencies import register_email_dispatcher
from app.core.models import User
from app.core.permissions import Role
from app.core.redis import get_redis
from app.core.security import hash_password

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Local fixtures (mirror test_invitation_accept.py — kept local so this file
# remains a self-contained grep target for the INSERT-only security claim).
# ---------------------------------------------------------------------------


_OWNER_EMAIL = "insert-only-owner@example.com"
_OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test literal


class _RecordingEmailDispatcher:
    """Test-only EmailDispatcher Protocol satisfier."""

    def __init__(self) -> None:
        self.sent_emails: list[dict[str, Any]] = []

    async def __call__(
        self,
        *,
        template_id: str,
        to: str,
        audit_correlation_id: UUID | None,
        **template_vars: Any,
    ) -> None:
        self.sent_emails.append(
            {
                "template_id": template_id,
                "to": to,
                "audit_correlation_id": audit_correlation_id,
                **template_vars,
            }
        )


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf") or ""}


def _extract_raw_token(invitation_url: str) -> str:
    assert "#token=" in invitation_url, f"missing #token= in {invitation_url!r}"
    return invitation_url.split("#token=", 1)[1]


@pytest_asyncio.fixture
async def _redis_clean(app: FastAPI) -> Any:
    client = app.state.redis
    await client.flushdb()
    return client


@pytest_asyncio.fixture
async def _seeded_owner(db_session: AsyncSession, _redis_clean: Any) -> User:
    _ = _redis_clean
    owner = User(
        email=_OWNER_EMAIL,
        password_hash=await hash_password(_OWNER_PASSWORD),
        role=Role.OWNER,
        full_name="Insert-Only Owner",
        email_verified=True,
        status="active",
        is_active=True,
    )
    db_session.add(owner)
    await db_session.commit()
    return owner


@pytest_asyncio.fixture
async def _app_overrides(app: FastAPI, db_session: AsyncSession) -> AsyncIterator[FastAPI]:
    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    def _override_get_redis() -> Any:
        return app.state.redis

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis
    try:
        yield app
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sandbox_email_client(
    app: FastAPI,
) -> AsyncIterator[_RecordingEmailDispatcher]:
    _ = app
    from app.core import dependencies as deps_mod

    prior = deps_mod._email_dispatcher
    recorder = _RecordingEmailDispatcher()
    register_email_dispatcher(recorder)
    try:
        yield recorder
    finally:
        if prior is not None:
            register_email_dispatcher(prior)
        else:
            deps_mod._email_dispatcher = None


@pytest_asyncio.fixture
async def owner_client(
    _app_overrides: FastAPI,
    _seeded_owner: User,
) -> AsyncIterator[AsyncClient]:
    _ = _seeded_owner
    transport = ASGITransport(app=_app_overrides)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": _OWNER_EMAIL, "password": _OWNER_PASSWORD},
        )
        assert r.status_code == 200, r.text
        yield client


@pytest_asyncio.fixture
async def anon_client(_app_overrides: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=_app_overrides)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


# ---------------------------------------------------------------------------
# Pitfall 4 — INSERT-only invariant at the accept boundary.
# ---------------------------------------------------------------------------


async def test_soft_deleted_email_re_invite_accept_lands_as_new_user_id(
    db_session: AsyncSession,
    owner_client: AsyncClient,
    anon_client: AsyncClient,
    sandbox_email_client: _RecordingEmailDispatcher,
) -> None:
    """Pitfall 4 — INSERT-only at accept; soft-delete + re-invite + accept.

    Full lineage (Phase 41 0022 → Phase 43 D-43-13 → Phase 44 D-44-20):
      1. Owner creates user A with email ``alice@example.com``.
      2. Owner soft-deletes A (DELETE /users/{A.id} → ``deleted_at=NOW()``).
      3. Owner creates a NEW user B with the SAME email; Phase 43
         D-43-13 branch-D (soft-deleted fall-through) INSERTs a new
         row because the partial-UNIQUE ignores ``deleted_at IS NOT NULL``.
         A.id != B.id.
      4. Accept B's invitation with the new raw token + password.
      5. Pitfall 4 assertion — the accepted user's id is B.id, NOT A.id
         (Phase 44 D-44-20: accept_invitation NEVER UPDATEs the
         soft-deleted row's ``deleted_at`` back to NULL).
      6. Row A's state is untouched (deleted_at still non-NULL,
         password_hash still NULL, status still 'pending_invitation').
      7. ``user_invitation_accepted`` audit row pins ``accepted_user_id``
         to B.id (NOT A.id).

    INSERT-only — the accept-flow's UPDATE statement targets the existing
    ``status='pending_invitation'`` row by ``id``, not by ``email``, so
    even a buggy lookup-by-email path cannot revive A here: A's status
    transitioned to 'active' OR remained 'pending_invitation' at
    soft-delete time, but its ``deleted_at`` is non-NULL — the accept-
    flow's WHERE clause (``deleted_at IS NULL``) filters it out.
    """
    email = "alice@example.com"

    # Step 1 — create user A.
    sandbox_email_client.sent_emails.clear()
    r_a = await owner_client.post(
        "/api/v1/users",
        json={"email": email, "fullName": "Alice Old", "role": "reception"},
        headers=_csrf_headers(owner_client),
    )
    assert r_a.status_code == 201, r_a.text
    user_a_id = UUID(r_a.json()["data"]["id"])

    # Snapshot row A's state BEFORE soft-delete + re-invite + accept for
    # the immutability assertion below.
    row_a_pre = await db_session.scalar(select(User).where(User.id == user_a_id))
    assert row_a_pre is not None
    await db_session.refresh(row_a_pre)
    row_a_pre_status = row_a_pre.status
    row_a_pre_password_hash = row_a_pre.password_hash
    row_a_pre_full_name = row_a_pre.full_name

    # Step 2 — soft-delete A. Phase 43 USERS-05 / D-43-18.
    r_delete = await owner_client.delete(
        f"/api/v1/users/{user_a_id}",
        headers=_csrf_headers(owner_client),
    )
    assert r_delete.status_code == 204, r_delete.text

    # Verify A is now soft-deleted in the DB (deleted_at non-NULL).
    await db_session.refresh(row_a_pre)
    assert row_a_pre.deleted_at is not None, "row A must be soft-deleted"

    # Step 3 — re-invite the SAME email. Phase 43 D-43-13 branch-D fall-
    # through to branch-A INSERTs a fresh row because the partial-UNIQUE
    # `(lower(email)) WHERE deleted_at IS NULL` does not see the soft-
    # deleted A row.
    sandbox_email_client.sent_emails.clear()
    r_b = await owner_client.post(
        "/api/v1/users",
        json={"email": email, "fullName": "Alice New", "role": "reception"},
        headers=_csrf_headers(owner_client),
    )
    assert r_b.status_code == 201, r_b.text
    user_b_id = UUID(r_b.json()["data"]["id"])

    # Distinct UUIDs — the partial-UNIQUE permitted the INSERT path.
    assert user_a_id != user_b_id, (
        f"Pitfall 4 / Phase 43 D-43-13 — re-invite of a soft-deleted "
        f"email MUST INSERT a new user row (distinct id). Got "
        f"A.id={user_a_id} == B.id={user_b_id}."
    )

    # Capture B's invitation token from the recorder.
    assert len(sandbox_email_client.sent_emails) == 1, (
        f"expected 1 captured invitation for B; got "
        f"{len(sandbox_email_client.sent_emails)}"
    )
    envelope = sandbox_email_client.sent_emails[0]
    raw_token_b = _extract_raw_token(envelope["invitation_url"])
    assert envelope["to"] == email

    # Step 4 — accept B's invitation.
    accept_password = "alice-new-password-strong"  # noqa: S105 -- test literal
    r_accept = await anon_client.post(
        "/api/v1/users/invitations/accept",
        json={
            "token": raw_token_b,
            "password": accept_password,
            "fullName": "Alice New",
        },
    )
    assert r_accept.status_code == 200, r_accept.text

    # Step 5 — Pitfall 4 INSERT-only assertion at the accept boundary.
    accepted_user_id = UUID(r_accept.json()["data"]["user"]["id"])
    assert accepted_user_id == user_b_id, (
        f"Pitfall 4 INSERT-only — accept must land on B.id, not A.id. "
        f"Got accepted_user_id={accepted_user_id}; expected B.id="
        f"{user_b_id} (A.id={user_a_id})."
    )
    assert accepted_user_id != user_a_id, (
        f"Pitfall 4 INSERT-only — accept lands on the NEW user row, "
        f"NEVER on the soft-deleted one. Got accepted_user_id="
        f"{accepted_user_id} == A.id={user_a_id}."
    )

    # Step 6 — row A is untouched (D-44-20: accept NEVER UPDATEs A).
    await db_session.refresh(row_a_pre)
    assert row_a_pre.deleted_at is not None, (
        "Pitfall 4 — row A's deleted_at must remain non-NULL after "
        "the accept-flow ran. The accept-flow MUST NOT resurrect a "
        "soft-deleted user by UPDATEing deleted_at back to NULL."
    )
    assert row_a_pre.status == row_a_pre_status, (
        "Pitfall 4 — row A's status must be unchanged by the accept-flow."
    )
    assert row_a_pre.password_hash == row_a_pre_password_hash, (
        "Pitfall 4 — row A's password_hash must NOT be set by an "
        "accept-flow that landed on a DIFFERENT row (B)."
    )
    assert row_a_pre.full_name == row_a_pre_full_name, (
        "Pitfall 4 — row A's full_name must NOT be overwritten by an "
        "accept-flow that landed on B."
    )

    # Row B has the post-accept post-state.
    row_b = await db_session.scalar(select(User).where(User.id == user_b_id))
    assert row_b is not None
    await db_session.refresh(row_b)
    assert row_b.status == "active"
    assert row_b.email_verified is True
    assert row_b.password_hash is not None and row_b.password_hash != ""
    assert row_b.full_name == "Alice New"
    assert row_b.deleted_at is None

    # Step 7 — audit row pins to B.id, NOT A.id.
    audit_rows = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "user_invitation_accepted",
                AuditLog.resource_id == user_b_id,
            )
        )
    ).scalars().all()
    assert len(audit_rows) == 1, (
        f"expected 1 user_invitation_accepted audit row for B; got {len(audit_rows)}"
    )
    audit_row = audit_rows[0]
    assert audit_row.payload["accepted_user_id"] == str(user_b_id)
    assert audit_row.payload["accepted_user_id"] != str(user_a_id), (
        "Pitfall 4 — audit payload must pin accepted_user_id to B.id, "
        f"NOT A.id. Got {audit_row.payload['accepted_user_id']!r}."
    )

    # Defence in depth — no accept-audit row should exist for A.id.
    audit_rows_a = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "user_invitation_accepted",
                AuditLog.resource_id == user_a_id,
            )
        )
    ).scalars().all()
    assert audit_rows_a == [], (
        f"Pitfall 4 — no user_invitation_accepted audit row should "
        f"resolve_id to A.id={user_a_id}. Got {audit_rows_a!r}."
    )
