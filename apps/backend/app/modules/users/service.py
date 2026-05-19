"""Phase 43 users module service (USERS-01/03/04/05 — D-43-09).

Service owns the transactional moment (D-03 / Phase 12.1 SVC001 lineage).
Repository emits zero commit/flush; service emits audit BEFORE flush (capture-
before-mutate where needed), then flush to surface IntegrityErrors, then
session.commit() at the route boundary.

Audit emit kwargs are FLAT (Phase 42 CR-01 lesson — never nested under
payload=). The AUDIT_PAYLOAD_SCHEMAS registry uses extra='forbid' so any
drift between callsite kwargs and Pydantic shape raises ValidationError at
audit.emit time.

Email render happens at enqueue time (D-43-24); the dispatcher gets a fully
materialised EmailEnvelope via kwargs. The literal template_id at the
get_email_dispatcher() callsite is enforced by the Phase 41 D-41-11 AST gate.

D-43-13 — POST /users is a 4-branch idempotent flow:
  A. No row found for email → INSERT user + invitation token + emit + email.
  B. Existing pending_invitation row → atomic-consume old invitation token,
     INSERT a fresh token, emit + email (idempotent re-invite path).
  C. Existing active row → 409 email_already_active.
  D. Soft-deleted row exists for the email → partial-UNIQUE on
     (lower(email)) WHERE deleted_at IS NULL excludes it; falls through to
     branch A (Pitfall 4 INSERT-only invariant at CREATE-time).

D-43-16/18 — deactivate / soft_delete share self + last-owner guards. The
last-owner count uses ``count_active_owners_excluding`` which acquires
``FOR UPDATE`` to serialise concurrent attempts (mirrors v1.2 freeze-period
serial-arbiter).

D-43-24 — invitation email is rendered at enqueue time (not transport time);
the EmailEnvelope (subject + html + text) is passed via kwargs to the
EmailDispatcher slot with literal ``template_id="USER_INVITATION_EMAIL"``.
"""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Final
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.config import get_settings
from app.core.dependencies import (
    CurrentUser,
    get_email_dispatcher,
    get_user_session_invalidator,
)
from app.core.exceptions import (
    CannotDeactivateLastOwnerError,
    CannotDeactivateSelfError,
    CannotDeleteLastOwnerError,
    CannotDeleteSelfError,
    EmailAlreadyActiveError,
    InvitationAlreadyAcceptedError,
    InvitationNotFoundError,
    UserAlreadyInactiveError,
    UserNotFoundError,
    UserNotInactiveError,
)
from app.core.pagination import PaginatedData
from app.core.permissions import Role
from app.modules.users import repository
from app.modules.users.email_templates import ROLE_RU, TEMPLATES
from app.modules.users.schemas import (
    UserCreateRequest,
    UserCreateResponse,
    UserListItemResponse,
    UserListQuery,
)

# Hand-rolled Russian long-form datetime helper (D-43-23 — no new dep).
# Babel is not in pyproject; the gym CRM only needs a single Russian locale.
_RU_MONTHS_GENITIVE: Final[tuple[str, ...]] = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


def _format_expires_ru(dt: datetime) -> str:
    """Render a Russian long-form datetime (e.g. '26 мая 2026 в 12:00').

    The output feeds the ``expires_at_human`` Jinja variable in the locked
    USER_INVITATION_EMAIL template (D-43-23 / D-43-OWNER-COPY-LOCK).
    """
    # Render in UTC to keep the wire shape deterministic; production deployment
    # can shift to Europe/Moscow render via a future Settings.tz field if owner
    # decides the email should carry local time instead of the canonical UTC.
    return (
        f"{dt.day} {_RU_MONTHS_GENITIVE[dt.month - 1]} {dt.year} "
        f"в {dt.hour:02d}:{dt.minute:02d}"
    )


def _build_invitation_url(raw_token: str) -> str:
    """Build the invitation URL with the raw token in the URL fragment (D-43-14 / RESET-03).

    Fragment is read by the SPA and submitted via the normal CSRF cookie pair;
    the raw token NEVER lands in audit payloads (D-43-14 / Pitfall 4).
    """
    base = get_settings().frontend_base_url.rstrip("/")
    return f"{base}/auth/accept-invite#token={raw_token}"


async def list_users(
    session: AsyncSession, query: UserListQuery
) -> PaginatedData[UserListItemResponse]:
    """USERS-02 — paginated list (D-43-15). Read-side: no audit emit, no commit."""
    return await repository.list_alive(session, query)


async def create_user(
    session: AsyncSession,
    actor: CurrentUser,
    data: UserCreateRequest,
    include_invite_link: bool,
) -> UserCreateResponse:
    """USERS-03 / D-43-13 — 4-branch idempotent invitation flow.

    Branches:
      A. No row: INSERT user(pending_invitation) + INSERT invitation token +
         emit + email + 201.
      B. Existing pending: atomic-consume old invitation, INSERT fresh token,
         emit + email + 200/201.
      C. Existing active: raise EmailAlreadyActiveError (409).
      D. Soft-deleted: partial-UNIQUE permits INSERT path automatically —
         falls through to branch A.
    """
    email_lower = data.email.lower()
    existing = await repository.get_by_email_for_create(session, email_lower)

    if existing is not None and existing.status == "active":
        raise EmailAlreadyActiveError("email_already_active")

    if existing is not None and existing.status == "pending_invitation":
        # Branch B — atomic-consume any active invitation (race-tight against
        # parallel POSTs for the same email).
        await repository.consume_active_invitation_for_user(
            session, user_id=existing.id
        )
        user = existing
    else:
        # Branch A / D — INSERT (partial-UNIQUE permits soft-deleted email
        # reclaim by excluding deleted_at IS NOT NULL rows).
        user = await repository.insert_user_pending_invitation(
            session,
            email_lower=email_lower,
            full_name=data.full_name,
            role=data.role,
        )
        try:
            await session.flush()  # surface IntegrityError on parallel-POST race
        except IntegrityError as exc:
            await session.rollback()
            raise EmailAlreadyActiveError("email_already_active") from exc

    # Generate raw token (URL-safe, 32 bytes → 43-char string).
    raw_token = secrets.token_urlsafe(32)
    audit_correlation_id = uuid4()

    token = await repository.insert_invitation_token(
        session,
        user_id=user.id,
        raw_token=raw_token,
        audit_correlation_id=audit_correlation_id,
    )
    await session.flush()  # surface partial-UNIQUE (user, purpose) race

    # Render email envelope (D-43-24 — render-at-enqueue).
    invitation_url = _build_invitation_url(raw_token)
    expires_at_human = _format_expires_ru(token.expires_at)
    template = TEMPLATES["USER_INVITATION_EMAIL"]
    role_ru = ROLE_RU[user.role]
    render_kwargs = {
        "full_name": user.full_name,
        "role_ru": role_ru,
        "invitation_url": invitation_url,
        "expires_at_human": expires_at_human,
    }
    envelope_fields = {
        "subject": template.subject,
        "html": template.html.render(**render_kwargs),
        "text": template.text.render(**render_kwargs),
    }

    # Audit emit — FLAT kwargs matching UserInvitedPayload (D-43-04 / D-43-14).
    # URL itself is NEVER in the payload — only link_copied bool (Pitfall 4).
    await audit.emit(
        session,
        "user_invited",
        actor_user_id=actor.id,
        resource_type="user",
        resource_id=user.id,
        audit_correlation_id=audit_correlation_id,
        invited_user_id=user.id,
        invited_email=email_lower,
        invited_role=user.role.value,
        invitation_expires_at=token.expires_at,
        link_copied=include_invite_link,
    )

    # Enqueue email — literal template_id required by AST gate (D-41-11).
    await get_email_dispatcher()(
        template_id="USER_INVITATION_EMAIL",
        to=email_lower,
        audit_correlation_id=audit_correlation_id,
        **envelope_fields,
    )

    await session.commit()

    return UserCreateResponse(
        id=user.id,
        email=email_lower,
        role=user.role,
        invitation_expires_at=token.expires_at,
        invite_link_url=invitation_url if include_invite_link else None,
    )


async def deactivate_user(
    session: AsyncSession, actor: CurrentUser, target_user_id: UUID
) -> None:
    """USERS-04 / D-43-16 — self + last-owner guards, then UPDATE + revoke + audit."""
    target = await repository.get_alive(session, target_user_id)
    if target is None:
        raise UserNotFoundError("user_not_found")
    if not target.is_active:
        raise UserAlreadyInactiveError("user_already_inactive")
    if target.id == actor.id:
        raise CannotDeactivateSelfError("cannot_deactivate_self")
    if target.role == Role.OWNER:
        # FOR UPDATE serialises parallel deactivate attempts on owners.
        active_owner_count = await repository.count_active_owners_excluding(
            session, excluded_user_id=target_user_id
        )
        if active_owner_count < 1:
            raise CannotDeactivateLastOwnerError("cannot_deactivate_last_owner")

    await repository.deactivate_user(
        session, target_user_id=target_user_id, actor_user_id=actor.id
    )

    sessions_revoked = await get_user_session_invalidator()(
        session, user_id=target_user_id, reason="deactivated"
    )

    await audit.emit(
        session,
        "user_deactivated",
        actor_user_id=actor.id,
        resource_type="user",
        resource_id=target_user_id,
        audit_correlation_id=uuid4(),
        deactivated_user_id=target_user_id,
        sessions_revoked_count=sessions_revoked,
    )
    await session.flush()
    await session.commit()


async def reactivate_user(
    session: AsyncSession, actor: CurrentUser, target_user_id: UUID
) -> None:
    """USERS-04 / D-43-17 — flip back to active; NO self/last-owner guards.

    Sessions are NOT auto-restored — refresh families revoked at deactivate
    time stay revoked; the user re-authenticates via the normal login path.
    """
    target = await repository.get_alive(session, target_user_id)
    if target is None:
        raise UserNotFoundError("user_not_found")
    if target.is_active:
        raise UserNotInactiveError("user_not_inactive")

    await repository.reactivate_user(session, target_user_id=target_user_id)

    await audit.emit(
        session,
        "user_reactivated",
        actor_user_id=actor.id,
        resource_type="user",
        resource_id=target_user_id,
        audit_correlation_id=uuid4(),
        reactivated_user_id=target_user_id,
    )
    await session.flush()
    await session.commit()


async def soft_delete_user(
    session: AsyncSession, actor: CurrentUser, target_user_id: UUID
) -> None:
    """USERS-05 / D-43-18 — same self+last-owner guards as deactivate.

    Allowed regardless of ``is_active`` state (the common case is delete after
    deactivate). Defensive session revoke covers the pure-delete-without-
    deactivate path. Pending invitations are atomic-consumed in the same UoW —
    no separate audit event (the parent ``user_soft_deleted`` covers it).
    """
    target = await repository.get_alive(session, target_user_id)
    if target is None:
        raise UserNotFoundError("user_not_found")
    if target.id == actor.id:
        raise CannotDeleteSelfError("cannot_delete_self")
    if target.role == Role.OWNER:
        active_owner_count = await repository.count_active_owners_excluding(
            session, excluded_user_id=target_user_id
        )
        if active_owner_count < 1:
            raise CannotDeleteLastOwnerError("cannot_delete_last_owner")

    await repository.soft_delete_user(session, target_user_id=target_user_id)
    # Defensive — most deletes follow a deactivate (no families left), but
    # pure-delete-without-deactivate path needs the kill.
    await get_user_session_invalidator()(
        session, user_id=target_user_id, reason="soft_deleted"
    )
    # Atomic-consume pending invitation (no separate audit — parent event covers).
    await repository.consume_active_invitation_for_user(
        session, user_id=target_user_id
    )

    await audit.emit(
        session,
        "user_soft_deleted",
        actor_user_id=actor.id,
        resource_type="user",
        resource_id=target_user_id,
        audit_correlation_id=uuid4(),
        deleted_user_id=target_user_id,
    )
    await session.flush()
    await session.commit()


async def revoke_invitation(
    session: AsyncSession,
    actor: CurrentUser,
    token_id: UUID,
    reason: str | None,
) -> None:
    """USERS-03 / D-43-19 — atomic-consume invitation token; race-loss → 409.

    Pre-check (consumed_at IS NOT NULL) and race-loss (UPDATE...RETURNING
    returned zero rows because a concurrent consume won) both map to the same
    InvitationAlreadyAcceptedError. Mirrors v1.1 refresh-rotation discipline.
    """
    token = await repository.get_invitation_token_by_id(session, token_id)
    if token is None:
        raise InvitationNotFoundError("invitation_not_found")
    if token.consumed_at is not None:
        raise InvitationAlreadyAcceptedError("invitation_already_accepted")

    consumed_id = await repository.atomic_consume_invitation_token_by_id(
        session, token_id
    )
    if consumed_id is None:
        # Race lost — another request consumed between get + UPDATE.
        raise InvitationAlreadyAcceptedError("invitation_already_accepted")

    await audit.emit(
        session,
        "user_invitation_revoked",
        actor_user_id=actor.id,
        resource_type="user",
        resource_id=token.user_id,
        audit_correlation_id=uuid4(),
        revoked_user_id=token.user_id,
        invitation_token_id=token_id,
        reason=reason,
    )
    await session.flush()
    await session.commit()
