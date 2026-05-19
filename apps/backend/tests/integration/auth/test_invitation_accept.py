"""RESET-04 invitation-accept integration tests (Phase 44 plan 44-08).

Covers the full RESET-04 lifecycle at the HTTP boundary against a real
Postgres via the project's SAVEPOINT-rolled session fixture:

  - Test 1 — happy path: atomic-consume + password set + status flip
    + email_verified flip + cookie pair issued + audit emit (D-44-18 /
    D-44-19 / D-44-21 / D-44-22 / D-44-23).
  - Test 2 — replay rejection: second POST with same token returns 410
    invalid_or_expired_token (anti-oracle parity with /password-reset/
    confirm per D-44-15 / D-44-19).
  - Test 3 — expired-invitation rejection: invitation row with
    ``expires_at < now()`` collapses to the same 410 envelope
    (D-44-15 anti-oracle).
  - Test 4a/4b/4c — full_name COALESCE branch (D-44-23): non-empty
    fullName overwrites the owner's value, empty / omitted preserves it.
  - Test 5 — race-with-soft-delete: between token-issue and accept the
    user is soft-deleted ⇒ 409 invitation_already_accepted per D-44-20
    (the UPDATE-where-pending-AND-not-deleted predicate returns zero
    rows even though the token-consume already fired).
  - Test 6 — RESET-05 cross-coverage: a token revoked via the Phase 43
    /invitations/{id}/revoke endpoint folds into the 410 anti-oracle
    bucket on a subsequent accept attempt (consumed_at IS NOT NULL ⇒
    atomic-consume predicate filters it out).
  - Test 7 — RESET-05 cross-coverage: revoking an already-accepted
    invitation returns 409 invitation_already_accepted (mirror of the
    Phase 43 USERS-05 "double-revoke" 409 path on the accepted side).

Fixtures here are intentionally LOCAL to ``tests/integration/auth/`` —
they parallel the Phase 43 ``tests/integration/users/conftest.py``
shape (sandbox email recorder + owner-authed AsyncClient + SAVEPOINT
``_client_app_overrides``) but live in this file so the auth-package
test suite does not depend on cross-package fixture wiring. The
discipline is identical to ``tests/integration/users/conftest.py``:

  - ``RecordingEmailDispatcher`` satisfies the Phase 41 D-41-24
    Protocol slot and records every dispatcher kwarg (``template_id``,
    ``to``, ``audit_correlation_id``, ``invitation_url``, …).
  - ``_client_app_overrides`` installs ``get_db`` / ``get_redis``
    overrides on the per-test ``app`` so the route handlers and the
    test inspector share the SAVEPOINT-rolled session.
  - ``authed_client_owner`` is logged in via POST /auth/login so the
    owner-only POST /users + DELETE /users/{id} flows succeed.

D-44-22 invariant — exactly one ``user_invitation_accepted`` audit row
is emitted per successful accept (no row on replay / expired / race).
JSONB serialises UUIDs as strings on roundtrip (Phase 12 audit-write
discipline), so ``payload["accepted_user_id"] == str(user_id)``.

Cookie name reference (D-44-21 / D-12 / D-26 — verified against
``app/core/security.py:issue_session_cookies``):
  - ``sz_access``      — Path=/, HttpOnly, Secure-on-prod
  - ``sz_refresh``     — Path=/api/v1/auth, HttpOnly, Secure-on-prod
  - ``sportzal_csrf``  — Path=/, NOT HttpOnly (read by JS for X-CSRF-Token)
"""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.core.database import get_db
from app.core.dependencies import register_email_dispatcher
from app.core.models import User
from app.core.permissions import Role
from app.core.redis import get_redis
from app.core.security import hash_password
from app.modules.auth.password_reset_token_model import PasswordResetToken

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Local fixture machinery (mirrors tests/integration/users/conftest.py shape).
# Kept local so the auth-package suite does not cross-import users-conftest.
# ---------------------------------------------------------------------------


_OWNER_EMAIL = "accept-flow-owner@example.com"
_OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test literal (>=12 chars)


class _RecordingEmailDispatcher:
    """Test-only EmailDispatcher Protocol satisfier (mirrors users-conftest)."""

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
    """Pull the raw token from an ``#token=...`` URL fragment."""
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
        full_name="Accept Owner",
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
    """Register a recording EmailDispatcher; restore on teardown."""
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
    """Owner-authed AsyncClient (cookies in jar after /auth/login)."""
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
    """Unauthenticated AsyncClient — POST /invitations/accept is anonymous (D-44-34)."""
    transport = ASGITransport(app=_app_overrides)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


# ---------------------------------------------------------------------------
# Helpers — owner-create-and-extract-token shorthand used by multiple tests.
# ---------------------------------------------------------------------------


async def _owner_create_invite(
    owner_client: AsyncClient,
    sandbox_email_client: _RecordingEmailDispatcher,
    *,
    email: str,
    full_name: str,
    role: str = "reception",
) -> tuple[UUID, str]:
    """Owner creates pending-invitation user; returns ``(user_id, raw_token)``.

    Clears the recorder first so the assertion below pins the freshly
    captured envelope unambiguously.
    """
    sandbox_email_client.sent_emails.clear()
    r = await owner_client.post(
        "/api/v1/users",
        json={"email": email, "fullName": full_name, "role": role},
        headers=_csrf_headers(owner_client),
    )
    assert r.status_code == 201, r.text
    user_id = UUID(r.json()["data"]["id"])

    assert len(sandbox_email_client.sent_emails) == 1, (
        f"expected 1 captured invitation; got "
        f"{len(sandbox_email_client.sent_emails)}"
    )
    envelope = sandbox_email_client.sent_emails[0]
    raw_token = _extract_raw_token(envelope["invitation_url"])
    return user_id, raw_token


# ---------------------------------------------------------------------------
# Test 1 — happy path (atomic-consume + flips + cookies + audit).
# ---------------------------------------------------------------------------


async def test_accept_happy_path_atomic_consume_password_set_email_verified_cookies_issued(
    db_session: AsyncSession,
    owner_client: AsyncClient,
    anon_client: AsyncClient,
    sandbox_email_client: _RecordingEmailDispatcher,
) -> None:
    """RESET-04 lifecycle — all flips land in a single committed UoW.

    D-44-18 / D-44-19 / D-44-21 / D-44-22 / D-44-23:
      - password_hash becomes non-NULL (Argon2 hash present).
      - status flips 'pending_invitation' → 'active'.
      - email_verified flips false → true.
      - password_reset_tokens.consumed_at is non-NULL (atomic-consume).
      - Set-Cookie headers carry sz_access + sz_refresh + sportzal_csrf.
      - Response body wraps LoginResponse(user=UserPublic(...)).
      - Exactly one ``user_invitation_accepted`` audit row with
        accepted_user_id = user_id, invitation_token_id = token row id.
      - The new password authenticates end-to-end via /auth/login
        (Argon2 verify works on the freshly set hash).
    """
    user_id, raw_token = await _owner_create_invite(
        owner_client,
        sandbox_email_client,
        email="newuser@example.com",
        full_name="Анна Петрова",
    )

    # Capture the invitation token row id BEFORE accept so we can assert
    # the audit payload's invitation_token_id pin even after consumed_at is set.
    token_row = await db_session.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.purpose == "invitation",
            PasswordResetToken.consumed_at.is_(None),
        )
    )
    assert token_row is not None, "fresh invitation token row missing after POST /users"
    token_id = token_row.id

    # NB: invitation-accept service enforces >=8 chars (D-44-17) but
    # /auth/login's LoginRequest schema enforces >=12 chars. Use a
    # >=12-char password here so the end-to-end Argon2 verify below
    # exercises a successful /auth/login, not a 422.
    new_password = "newpass-1234-strong"  # noqa: S105 -- test literal
    r = await anon_client.post(
        "/api/v1/users/invitations/accept",
        json={
            "token": raw_token,
            "password": new_password,
            "fullName": "Анна Петрова-Иванова",
        },
    )
    assert r.status_code == 200, r.text

    body = r.json()
    assert body["data"]["user"]["id"] == str(user_id)
    assert body["data"]["user"]["role"] == "reception"
    assert body["data"]["user"]["fullName"] == "Анна Петрова-Иванова"

    # Set-Cookie matrix — all 3 cookies issued by issue_session_cookies (D-44-21).
    # httpx parses Set-Cookie into the cookies jar; assert on jar membership
    # rather than the raw header (httpx exposes only the last set-cookie
    # value via response.headers["set-cookie"] when servers send multiple).
    assert "sz_access" in r.cookies, f"sz_access missing; got {dict(r.cookies)}"
    assert "sz_refresh" in r.cookies, f"sz_refresh missing; got {dict(r.cookies)}"
    assert "sportzal_csrf" in r.cookies, f"sportzal_csrf missing; got {dict(r.cookies)}"

    # DB-side flips — fetch the user row fresh.
    user_row = await db_session.scalar(select(User).where(User.id == user_id))
    assert user_row is not None
    await db_session.refresh(user_row)
    assert user_row.status == "active"
    assert user_row.email_verified is True
    assert user_row.password_hash is not None and user_row.password_hash != ""
    assert user_row.full_name == "Анна Петрова-Иванова"

    # Token row — consumed_at populated.
    await db_session.refresh(token_row)
    assert token_row.consumed_at is not None

    # Audit — exactly one user_invitation_accepted row pinned to this user.
    audit_rows = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "user_invitation_accepted",
                AuditLog.resource_id == user_id,
            )
        )
    ).scalars().all()
    assert len(audit_rows) == 1, (
        f"expected 1 user_invitation_accepted audit row; got {len(audit_rows)}"
    )
    audit_row = audit_rows[0]
    # JSONB serialises UUIDs as strings on roundtrip (Phase 12 discipline).
    assert audit_row.payload["accepted_user_id"] == str(user_id)
    assert audit_row.payload["invitation_token_id"] == str(token_id)

    # End-to-end Argon2 verify — log in with the freshly-set password.
    r_login = await anon_client.post(
        "/api/v1/auth/login",
        json={"email": "newuser@example.com", "password": new_password},
    )
    assert r_login.status_code == 200, r_login.text


# ---------------------------------------------------------------------------
# Test 2 — replay rejection.
# ---------------------------------------------------------------------------


async def test_accept_replay_returns_410_with_identical_body(
    db_session: AsyncSession,
    owner_client: AsyncClient,
    anon_client: AsyncClient,
    sandbox_email_client: _RecordingEmailDispatcher,
) -> None:
    """D-44-15 anti-oracle — replay collapses into the same 410 envelope.

    Asserts NO additional audit row appears after the replay (the
    atomic-consume returned zero rows because the row's consumed_at is
    non-NULL after the first accept).
    """
    user_id, raw_token = await _owner_create_invite(
        owner_client,
        sandbox_email_client,
        email="replay-target@example.com",
        full_name="Иван Тест",
    )

    # First accept — 200 (happy path).
    r1 = await anon_client.post(
        "/api/v1/users/invitations/accept",
        json={"token": raw_token, "password": "newpass1234", "fullName": "Иван Тест"},
    )
    assert r1.status_code == 200, r1.text

    # Second accept — same token — 410 invalid_or_expired_token.
    r2 = await anon_client.post(
        "/api/v1/users/invitations/accept",
        json={"token": raw_token, "password": "newpass1234", "fullName": "Иван Тест"},
    )
    assert r2.status_code == 410, r2.text
    assert r2.json()["code"] == "invalid_or_expired_token"

    # Exactly ONE audit row — replay did NOT emit a second.
    audit_rows = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "user_invitation_accepted",
                AuditLog.resource_id == user_id,
            )
        )
    ).scalars().all()
    assert len(audit_rows) == 1, (
        f"replay must NOT emit a 2nd audit row; got {len(audit_rows)}"
    )


# ---------------------------------------------------------------------------
# Test 3 — expired invitation.
# ---------------------------------------------------------------------------


async def test_accept_expired_invitation_returns_410(
    db_session: AsyncSession,
    owner_client: AsyncClient,
    anon_client: AsyncClient,
    sandbox_email_client: _RecordingEmailDispatcher,
) -> None:
    """D-44-15 anti-oracle — expired invitation collapses into 410.

    Forces the token row's ``expires_at`` to the past so the atomic-consume
    predicate (``expires_at > NOW()``) filters it out. The 410 envelope
    matches the replay/unknown buckets verbatim — no oracle leak.
    """
    user_id, raw_token = await _owner_create_invite(
        owner_client,
        sandbox_email_client,
        email="expired-target@example.com",
        full_name="Expired Tester",
    )

    # Force expiry 1 minute in the past — direct UPDATE on the SAVEPOINT-rolled
    # connection so the route handler sees the same row state.
    past = datetime.now(tz=UTC) - timedelta(minutes=1)
    await db_session.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user_id)
        .values(expires_at=past)
    )
    await db_session.commit()

    r = await anon_client.post(
        "/api/v1/users/invitations/accept",
        json={"token": raw_token, "password": "newpass1234", "fullName": "Expired Tester"},
    )
    assert r.status_code == 410, r.text
    assert r.json()["code"] == "invalid_or_expired_token"

    # consumed_at remains NULL — the predicate filtered the row out so the
    # UPDATE landed zero rows (atomic-consume short-circuit per D-44-14).
    token_row = await db_session.scalar(
        select(PasswordResetToken).where(PasswordResetToken.user_id == user_id)
    )
    assert token_row is not None
    await db_session.refresh(token_row)
    assert token_row.consumed_at is None


# ---------------------------------------------------------------------------
# Test 4 — full_name COALESCE branch (D-44-23).
# ---------------------------------------------------------------------------


async def test_accept_full_name_branch_overwrite(
    db_session: AsyncSession,
    owner_client: AsyncClient,
    anon_client: AsyncClient,
    sandbox_email_client: _RecordingEmailDispatcher,
) -> None:
    """D-44-23 — non-empty fullName overwrites owner's value (self-healing typo)."""
    user_id, raw_token = await _owner_create_invite(
        owner_client,
        sandbox_email_client,
        email="overwrite-fullname@example.com",
        full_name="Aннa Иванов",  # intentional Latin/Cyrillic mix
    )

    r = await anon_client.post(
        "/api/v1/users/invitations/accept",
        json={"token": raw_token, "password": "newpass1234", "fullName": "Анна Иванова"},
    )
    assert r.status_code == 200, r.text

    user_row = await db_session.scalar(select(User).where(User.id == user_id))
    assert user_row is not None
    await db_session.refresh(user_row)
    assert user_row.full_name == "Анна Иванова"


async def test_accept_full_name_branch_preserve_on_empty(
    db_session: AsyncSession,
    owner_client: AsyncClient,
    anon_client: AsyncClient,
    sandbox_email_client: _RecordingEmailDispatcher,
) -> None:
    """D-44-23 — empty-string fullName preserves the owner's original value."""
    user_id, raw_token = await _owner_create_invite(
        owner_client,
        sandbox_email_client,
        email="preserve-empty@example.com",
        full_name="Aннa Иванов",
    )

    r = await anon_client.post(
        "/api/v1/users/invitations/accept",
        json={"token": raw_token, "password": "newpass1234", "fullName": ""},
    )
    assert r.status_code == 200, r.text

    user_row = await db_session.scalar(select(User).where(User.id == user_id))
    assert user_row is not None
    await db_session.refresh(user_row)
    assert user_row.full_name == "Aннa Иванов"


async def test_accept_full_name_branch_preserve_on_omitted(
    db_session: AsyncSession,
    owner_client: AsyncClient,
    anon_client: AsyncClient,
    sandbox_email_client: _RecordingEmailDispatcher,
) -> None:
    """D-44-23 — omitted fullName (field absent) preserves the owner's original.

    Identical effective outcome to ``test_accept_full_name_branch_preserve_on_empty``
    but exercises the ``None`` Pydantic branch instead of the empty-string
    normalisation — both should collapse to the same COALESCE-keeps-original
    behaviour per D-44-23.
    """
    user_id, raw_token = await _owner_create_invite(
        owner_client,
        sandbox_email_client,
        email="preserve-omitted@example.com",
        full_name="Aннa Иванов",
    )

    r = await anon_client.post(
        "/api/v1/users/invitations/accept",
        json={"token": raw_token, "password": "newpass1234"},
    )
    assert r.status_code == 200, r.text

    user_row = await db_session.scalar(select(User).where(User.id == user_id))
    assert user_row is not None
    await db_session.refresh(user_row)
    assert user_row.full_name == "Aннa Иванов"


# ---------------------------------------------------------------------------
# Test 5 — race-with-soft-delete (D-44-20).
# ---------------------------------------------------------------------------


async def test_accept_race_with_soft_delete_returns_409(
    db_session: AsyncSession,
    owner_client: AsyncClient,
    anon_client: AsyncClient,
    sandbox_email_client: _RecordingEmailDispatcher,
) -> None:
    """D-44-20 — soft-delete between token-issue and accept ⇒ 409.

    Sequence:
      1. Owner creates user + invitation token.
      2. Owner soft-deletes the user (sets deleted_at = NOW()).
      3. Accept POSTs with the still-valid (consumed_at IS NULL, not
         expired) token.

    The atomic-consume DOES fire (the token row predicate ignores user
    soft-delete state), but the subsequent UPDATE-where-pending-AND-not-
    deleted on the users row matches zero rows because deleted_at is now
    non-NULL. The service raises ``InvitationAlreadyAcceptedError`` →
    409 ``invitation_already_accepted``.

    Token-state assertion: per the Wave 2 (44-04) implementation order
    the atomic-consume fires BEFORE the user-row UPDATE — so consumed_at
    is non-NULL on the token row even though the user-row UPDATE failed.
    See ``password_reset_service.accept_invitation`` body order.
    """
    user_id, raw_token = await _owner_create_invite(
        owner_client,
        sandbox_email_client,
        email="race-target@example.com",
        full_name="Race Target",
    )

    # Simulate the race — owner soft-deletes the user between token-issue
    # and accept. Direct UPDATE on the SAVEPOINT-rolled session (the route
    # handler shares this connection per the _app_overrides fixture).
    now = datetime.now(tz=UTC)
    await db_session.execute(
        update(User)
        .where(User.id == user_id)
        .values(deleted_at=now, is_active=False, deactivated_at=now)
    )
    await db_session.commit()

    r = await anon_client.post(
        "/api/v1/users/invitations/accept",
        json={"token": raw_token, "password": "newpass1234", "fullName": "Race Target"},
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "invitation_already_accepted"

    # Per the 44-04 implementation order, consumed_at IS already populated
    # by the time the user-row UPDATE fails — the service raises AFTER the
    # atomic-consume. Verify against the password_reset_tokens row.
    token_row = await db_session.scalar(
        select(PasswordResetToken).where(PasswordResetToken.user_id == user_id)
    )
    assert token_row is not None
    await db_session.refresh(token_row)
    assert token_row.consumed_at is not None, (
        "44-04 implementation orders atomic-consume BEFORE the user-row "
        "UPDATE — consumed_at should be set even on the 409 path. If the "
        "implementation re-orders these (commit before user UPDATE), "
        "this assertion's expectation must change."
    )

    # No accepted-audit row should exist (the service raised before the
    # audit.emit step). NB: even though session.commit() never ran on the
    # accept-flow path, the test uses SAVEPOINT isolation — what we assert
    # here is that the audit_log table contains no user_invitation_accepted
    # row for THIS user_id.
    audit_rows = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "user_invitation_accepted",
                AuditLog.resource_id == user_id,
            )
        )
    ).scalars().all()
    assert audit_rows == [], (
        f"409 path must NOT emit user_invitation_accepted; got {audit_rows!r}"
    )


# ---------------------------------------------------------------------------
# Test 6 — RESET-05 cross-coverage: accept with a revoked token → 410.
# ---------------------------------------------------------------------------


async def test_accept_with_revoked_token_returns_410(
    db_session: AsyncSession,
    owner_client: AsyncClient,
    anon_client: AsyncClient,
    sandbox_email_client: _RecordingEmailDispatcher,
) -> None:
    """RESET-05 cross-coverage — revoked-token accept folds into the 410 bucket.

    Phase 43 D-43-19 ships the ``/invitations/{id}/revoke`` endpoint —
    revocation flips ``consumed_at`` on the token row. Subsequent
    accept-attempt's atomic-consume predicate (``consumed_at IS NULL``)
    filters the revoked row out → anti-oracle 410, same envelope as
    replay/expired/unknown.
    """
    user_id, raw_token = await _owner_create_invite(
        owner_client,
        sandbox_email_client,
        email="revoke-then-accept@example.com",
        full_name="Revoke Target",
    )

    token_row = await db_session.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.purpose == "invitation",
            PasswordResetToken.consumed_at.is_(None),
        )
    )
    assert token_row is not None
    token_id = token_row.id

    # Owner revokes the invitation (Phase 43 D-43-19).
    r_revoke = await owner_client.post(
        f"/api/v1/users/invitations/{token_id}/revoke",
        json={"reason": "revoked before accept"},
        headers=_csrf_headers(owner_client),
    )
    assert r_revoke.status_code == 204, r_revoke.text

    # Now try to accept with the revoked raw token → 410.
    r_accept = await anon_client.post(
        "/api/v1/users/invitations/accept",
        json={"token": raw_token, "password": "newpass1234", "fullName": "Revoke Target"},
    )
    assert r_accept.status_code == 410, r_accept.text
    assert r_accept.json()["code"] == "invalid_or_expired_token"

    # Defence in depth — the raw token's hash matches the revoked row
    # (proves we revoked the right row and the anti-oracle 410 is a
    # genuine bucket collapse, not an unrelated lookup miss).
    expected_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    await db_session.refresh(token_row)
    assert token_row.token_hash == expected_hash
    assert token_row.consumed_at is not None


# ---------------------------------------------------------------------------
# Test 7 — RESET-05 cross-coverage: revoke after accept → 409.
# ---------------------------------------------------------------------------


async def test_revoke_already_accepted_invitation_returns_409(
    db_session: AsyncSession,
    owner_client: AsyncClient,
    anon_client: AsyncClient,
    sandbox_email_client: _RecordingEmailDispatcher,
) -> None:
    """RESET-05 — revoking an already-accepted invitation returns 409.

    Mirror of Phase 43 ``test_revoke_already_consumed_invitation_returns_409``
    (which exercises the double-revoke path); here the first ``consumed_at``
    write comes from the Phase 44 accept-flow rather than a prior revoke.
    Same 409 code (``invitation_already_accepted``) because the
    UPDATE-where-consumed_at-IS-NULL predicate matches zero rows in both
    cases.
    """
    user_id, raw_token = await _owner_create_invite(
        owner_client,
        sandbox_email_client,
        email="accept-then-revoke@example.com",
        full_name="Accept First",
    )

    token_row = await db_session.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.purpose == "invitation",
            PasswordResetToken.consumed_at.is_(None),
        )
    )
    assert token_row is not None
    token_id = token_row.id

    # Accept first (200).
    r_accept = await anon_client.post(
        "/api/v1/users/invitations/accept",
        json={"token": raw_token, "password": "newpass1234", "fullName": "Accept First"},
    )
    assert r_accept.status_code == 200, r_accept.text

    # Now revoke — already-consumed-after-accept ⇒ 409.
    r_revoke = await owner_client.post(
        f"/api/v1/users/invitations/{token_id}/revoke",
        json={"reason": "too late"},
        headers=_csrf_headers(owner_client),
    )
    assert r_revoke.status_code == 409, r_revoke.text
    assert r_revoke.json()["code"] == "invitation_already_accepted"
