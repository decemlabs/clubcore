"""Phase 43 USERS-03 invitation flow — D-43-13 / D-43-14 / D-43-19 / D-43-24 / D-43-25.

Sandbox email capture via the test-only ``RecordingEmailDispatcher`` installed
by the ``sandbox_email_client`` fixture in ``tests/integration/users/conftest.py``
(Phase 43 plan 43-07b). The prod ``app.integrations.email.client.SandboxEmailClient``
is a no-op stub (logs the envelope and returns a provider id) — it does NOT
capture envelopes. The conftest fixture swaps the Phase 41 D-41-24 dispatcher
slot for a recorder that exposes ``.sent_emails: list[dict[str, Any]]`` whose
entries merge the dispatcher kwargs (``template_id``, ``to``,
``audit_correlation_id``) with the rendered envelope vars the service emits
at enqueue time (``subject``, ``html``, ``text``, ``full_name``, ``role_ru``,
``invitation_url``, ``expires_at_human``).

Plan: ``.planning/phases/43-multi-user-admin-module/43-11-PLAN.md``.

Shared fixtures (``authed_client_owner``, ``sandbox_email_client``,
``db_session``) live in ``tests/integration/users/conftest.py`` (43-07b) —
never redefined here.

Rule-1 drifts from plan text (mirrors 43-08-SUMMARY.md):
  - Plan text referenced ``AuditLog.event``; the real ORM column is
    ``AuditLog.action`` (see ``app/core/audit_models.py``).
  - Plan text used ``r.json()["detail"]["error"]``; the AppError handler
    emits top-level ``{"code", "message", "fields"}`` (see
    ``app.core.exceptions.register_exception_handlers``).
  - ``audit_row.payload["invitation_token_id"]`` is compared to
    ``str(token_id)`` because JSONB serialises UUIDs as strings on
    roundtrip (see Phase 12 audit-write integration tests).
"""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.auth.password_reset_token_model import PasswordResetToken

from .conftest import RecordingEmailDispatcher

pytestmark = pytest.mark.asyncio


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("clubcore_csrf") or ""}


async def test_invitation_email_enqueued_through_sandbox(
    db_session: AsyncSession,
    authed_client_owner: AsyncClient,
    sandbox_email_client: RecordingEmailDispatcher,
) -> None:
    """D-43-13/24/25 — POST /users enqueues USER_INVITATION_EMAIL with rendered envelope.

    Asserts the recorder captured exactly one envelope addressed to the
    invitee with the locked ``template_id='USER_INVITATION_EMAIL'`` and the
    rendered subject + text body containing the Russian copy and the
    invitation URL fragment (D-43-OWNER-COPY-LOCK).
    """
    _ = db_session  # SAVEPOINT-rolled session shared with the route handler
    # Reset the recorder so a prior fixture-graph touch can't pollute the count.
    sandbox_email_client.sent_emails.clear()

    r = await authed_client_owner.post(
        "/api/v1/users",
        json={
            "email": "invitee@example.com",
            "fullName": "Иван Тестовый",
            "role": "reception",
        },
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text

    sent = sandbox_email_client.sent_emails
    assert len(sent) == 1, f"expected 1 sandbox email; got {len(sent)}: {sent!r}"
    email = sent[0]
    assert email["to"] == "invitee@example.com"
    assert email["template_id"] == "USER_INVITATION_EMAIL"
    # CR-01 fix (Phase 43 plan 43-14): the recorder now captures raw template
    # vars (full_name, role_ru, invitation_url, expires_at_human) NOT the
    # pre-rendered subject/html/text. The prod dispatcher renders at enqueue
    # time (D-43-24 / Phase 42 render-at-enqueue contract). Assert on the
    # raw vars that the service passes through to the dispatcher.
    assert email["full_name"] == "Иван Тестовый"
    assert "/auth/accept-invite#token=" in email["invitation_url"]
    # audit_correlation_id is forwarded to the dispatcher (D-41-04 chain).
    assert email["audit_correlation_id"] is not None


async def test_include_invite_link_returns_url_with_token_fragment(
    authed_client_owner: AsyncClient,
) -> None:
    """D-43-14 — ?include_invite_link=true exposes the URL with #token= fragment for copy-paste.

    Validates the URL shape (scheme + path + token-in-fragment per RESET-03
    anti-oracle: the raw token NEVER lands in the path). The token component
    is at least 32 url-safe characters — ``secrets.token_urlsafe(32)``
    produces 43 chars in practice (service.py:172).
    """
    r = await authed_client_owner.post(
        "/api/v1/users?include_invite_link=true",
        json={
            "email": "with-link-fragment@example.com",
            "fullName": "Borya B.",
            "role": "reception",
        },
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    url = r.json()["data"]["inviteLinkUrl"]
    assert isinstance(url, str)
    assert url.startswith(("http://", "https://"))
    assert "/auth/accept-invite#token=" in url
    # Raw token is in the URL fragment, never the path — splitting on '#token='
    # MUST yield a non-empty suffix.
    token_part = url.split("#token=", 1)[1]
    assert len(token_part) >= 32, (
        f"raw token suspiciously short ({len(token_part)} chars); "
        "expected ~43 chars from secrets.token_urlsafe(32)"
    )


async def test_revoke_invitation_flips_consumed_and_emits_audit(
    db_session: AsyncSession,
    authed_client_owner: AsyncClient,
) -> None:
    """D-43-19 — POST /invitations/{id}/revoke atomic-consumes + emits user_invitation_revoked."""
    r_create = await authed_client_owner.post(
        "/api/v1/users",
        json={
            "email": "to-revoke@example.com",
            "fullName": "Revoke Target",
            "role": "reception",
        },
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_create.status_code == 201, r_create.text
    user_id = UUID(r_create.json()["data"]["id"])

    # Look up the invitation token row id (consumed_at IS NULL — fresh from create).
    token_row = await db_session.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.purpose == "invitation",
            PasswordResetToken.consumed_at.is_(None),
        )
    )
    assert token_row is not None, "fresh invitation token row missing after POST /users"
    token_id = token_row.id

    r_revoke = await authed_client_owner.post(
        f"/api/v1/users/invitations/{token_id}/revoke",
        json={"reason": "wrong email address"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_revoke.status_code == 204, r_revoke.text

    # consumed_at is populated in the DB after revoke.
    await db_session.refresh(token_row)
    assert token_row.consumed_at is not None

    # Audit row exists with FLAT payload kwargs (D-43-04 / UserInvitationRevokedPayload).
    audit_row = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "user_invitation_revoked",
                AuditLog.resource_id == user_id,
            )
        )
    ).scalar_one()
    # JSONB serialises UUIDs as strings on roundtrip.
    assert audit_row.payload["invitation_token_id"] == str(token_id)
    assert audit_row.payload["revoked_user_id"] == str(user_id)
    assert audit_row.payload["reason"] == "wrong email address"


async def test_users_list_exposes_invitation_token_id(
    db_session: AsyncSession,
    authed_client_owner: AsyncClient,
) -> None:
    """REV-01 Variant B — GET /users returns invitationTokenId for pending invites, null for active.

    The list-item ``invitationTokenId`` is the live ``password_reset_tokens``
    row id (D-43-19) that the revoke endpoint resolves by. It MUST equal the
    issued token id for a freshly-invited pending user and be null for an
    active user (the seeded owner).
    """
    r_create = await authed_client_owner.post(
        "/api/v1/users",
        json={
            "email": "listed-pending@example.com",
            "fullName": "Listed Pending",
            "role": "reception",
        },
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_create.status_code == 201, r_create.text
    pending_user_id = r_create.json()["data"]["id"]

    # The issued invitation token row id (consumed_at IS NULL — fresh).
    token_row = await db_session.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == UUID(pending_user_id),
            PasswordResetToken.purpose == "invitation",
            PasswordResetToken.consumed_at.is_(None),
        )
    )
    assert token_row is not None
    expected_token_id = str(token_row.id)

    r_list = await authed_client_owner.get("/api/v1/users?pageSize=100")
    assert r_list.status_code == 200, r_list.text
    items = r_list.json()["data"]["items"]
    by_id = {item["id"]: item for item in items}

    pending_item = by_id[pending_user_id]
    assert pending_item["status"] == "pending_invitation"
    assert pending_item["invitationTokenId"] == expected_token_id

    # The seeded owner is an active user → invitationTokenId is null.
    active_items = [i for i in items if i["status"] == "active"]
    assert active_items, "expected at least one active user (the seeded owner) in the list"
    assert all(i["invitationTokenId"] is None for i in active_items)


async def test_revoke_invitation_using_listed_token_id(
    authed_client_owner: AsyncClient,
) -> None:
    """REV-01 Variant B happy path — revoke using the token id surfaced by GET /users.

    Mirrors the real FE flow: read ``invitationTokenId`` from the list, POST a
    non-empty ``{ reason }`` body to the revoke endpoint, expect 204, then the
    placeholder user is soft-deleted and the row disappears from the list.
    """
    r_create = await authed_client_owner.post(
        "/api/v1/users",
        json={
            "email": "revoke-via-list@example.com",
            "fullName": "Revoke Via List",
            "role": "reception",
        },
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_create.status_code == 201, r_create.text
    pending_user_id = r_create.json()["data"]["id"]

    r_list = await authed_client_owner.get("/api/v1/users?pageSize=100")
    assert r_list.status_code == 200, r_list.text
    pending_item = next(
        i for i in r_list.json()["data"]["items"] if i["id"] == pending_user_id
    )
    token_id = pending_item["invitationTokenId"]
    assert token_id is not None

    r_revoke = await authed_client_owner.post(
        f"/api/v1/users/invitations/{token_id}/revoke",
        json={"reason": "Отозвано владельцем"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_revoke.status_code == 204, r_revoke.text

    # REV-01 — revoking a pending invitation un-invites the user: the
    # placeholder row is soft-deleted and no longer appears in GET /users.
    r_list_after = await authed_client_owner.get("/api/v1/users?pageSize=100")
    assert r_list_after.status_code == 200, r_list_after.text
    ids_after = {i["id"] for i in r_list_after.json()["data"]["items"]}
    assert pending_user_id not in ids_after, (
        "revoked pending user must disappear from the team list (soft-deleted)"
    )


async def test_revoke_already_consumed_invitation_returns_409(
    db_session: AsyncSession,
    authed_client_owner: AsyncClient,
) -> None:
    """D-43-19 — second revoke on the same token returns 409 invitation_already_accepted.

    Same code is emitted for both pre-check (consumed_at IS NOT NULL on get)
    and race-loss (UPDATE...RETURNING returned zero rows). Mirrors v1.1
    refresh-rotation race-loss discipline.
    """
    r_create = await authed_client_owner.post(
        "/api/v1/users",
        json={
            "email": "double-revoke@example.com",
            "fullName": "Double Revoke",
            "role": "reception",
        },
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_create.status_code == 201, r_create.text
    user_id = UUID(r_create.json()["data"]["id"])

    token_row = await db_session.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.purpose == "invitation",
            PasswordResetToken.consumed_at.is_(None),
        )
    )
    assert token_row is not None
    token_id = token_row.id

    r1 = await authed_client_owner.post(
        f"/api/v1/users/invitations/{token_id}/revoke",
        json={},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r1.status_code == 204, r1.text

    r2 = await authed_client_owner.post(
        f"/api/v1/users/invitations/{token_id}/revoke",
        json={},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r2.status_code == 409, r2.text
    # AppError handler shape: {"code", "message", "fields"} — see app/core/exceptions.py.
    assert r2.json()["code"] == "invitation_already_accepted"
