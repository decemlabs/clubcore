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
last-owner count uses ``count_active_owners_excluding`` which locks the
candidate-owner rows themselves (CR-02/WR-05 fix — aggregate FOR UPDATE is
illegal in Postgres) to serialise concurrent attempts at the row-lock layer.

D-43-24 — invitation email is rendered at enqueue time (not transport time);
the EmailEnvelope (subject + html + text) is passed via kwargs to the
EmailDispatcher slot with literal ``template_id="USER_INVITATION_EMAIL"``.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Final
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

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
    CannotChangeLastOwnerRoleError,
    CannotChangeOwnRoleError,
    CannotDeactivateLastOwnerError,
    CannotDeactivateSelfError,
    CannotDeleteLastOwnerError,
    CannotDeleteSelfError,
    EmailAlreadyActiveError,
    InvitationAlreadyAcceptedError,
    InvitationExpiredError,
    InvitationNotFoundError,
    UserAlreadyInactiveError,
    UserNotFoundError,
    UserNotInactiveError,
)
from app.core.pagination import PaginatedData
from app.core.permissions import Role
from app.modules.users import repository
from app.modules.users.email_templates import ROLE_RU
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

# WR-07 (Phase 43 review) — project i18n is Europe/Moscow; mirror the
# ZoneInfo precedent from app/integrations/telegram/handlers.py.
_MOSCOW_TZ: Final[ZoneInfo] = ZoneInfo("Europe/Moscow")


def _format_expires_ru(dt: datetime) -> str:
    """Render a Russian long-form datetime in Europe/Moscow with (MSK) suffix.

    The output feeds the ``expires_at_human`` Jinja variable in the locked
    USER_INVITATION_EMAIL template (D-43-23 / D-43-OWNER-COPY-LOCK).

    WR-07 (Phase 43 review) — converted to Europe/Moscow before formatting
    and tagged with Cyrillic MSK suffix to remove TZ ambiguity.
    The project i18n convention (CLAUDE.md: "all human-facing dates in
    Europe/Moscow") makes UTC rendering an off-by-3-hours defect.
    """
    local = dt.astimezone(_MOSCOW_TZ)
    return (
        f"{local.day} {_RU_MONTHS_GENITIVE[local.month - 1]} {local.year} "
        f"в {local.hour:02d}:{local.minute:02d} (МСК)"  # noqa: RUF001
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
        #
        # WR-02 (Phase 43 review) — re-invite POST is the authoritative
        # re-statement of the invite. Overwrite full_name/role from the
        # inbound request so an owner correcting a typo lands the new values
        # (previous behaviour: silently keep the original, defeating the
        # re-invite UX). The flush below surfaces any constraint violation.
        existing.full_name = data.full_name
        existing.role = data.role
        await repository.consume_active_invitation_for_user(session, user_id=existing.id)
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

    # Render variables for the locked USER_INVITATION_EMAIL template.
    # Dispatcher renders subject/html/text at enqueue time (D-43-24 / Phase 42
    # render-at-enqueue contract). The service NEVER pre-renders — passing
    # subject/html/text as **template_vars is silently ignored by Jinja and
    # was the CR-01 defect (Phase 43 review).
    invitation_url = _build_invitation_url(raw_token)
    expires_at_human = _format_expires_ru(token.expires_at)
    role_ru = ROLE_RU[user.role]

    # Audit emit — FLAT kwargs matching UserInvitedPayload (D-43-04 / D-43-14).
    # URL itself is NEVER in the payload — only link_copied bool (Pitfall 4).
    # UUIDs / datetimes stringified at the audit boundary (REG-36-03 / Phase 42
    # discipline): AuditLog.payload is JSONB with no UUID-aware serializer;
    # Pydantic schemas accept str → UUID/datetime coercion during validation.
    await audit.emit(
        session,
        "user_invited",
        actor_user_id=actor.id,
        resource_type="user",
        resource_id=user.id,
        audit_correlation_id=str(audit_correlation_id),
        invited_user_id=str(user.id),
        invited_email=email_lower,
        invited_role=user.role.value,
        invitation_expires_at=token.expires_at.isoformat(),
        link_copied=include_invite_link,
    )

    # Enqueue email — literal template_id required by AST gate (D-41-11).
    # Pass RAW template vars (CR-01 fix); the dispatcher renders the locked
    # template against these — matches the Phase 42 EMAIL_OTP_LOGIN callsite
    # at auth/service.py:1031-1036.
    await get_email_dispatcher()(
        template_id="USER_INVITATION_EMAIL",
        to=email_lower,
        audit_correlation_id=audit_correlation_id,
        full_name=user.full_name,
        role_ru=role_ru,
        invitation_url=invitation_url,
        expires_at_human=expires_at_human,
    )

    await session.commit()

    return UserCreateResponse(
        id=user.id,
        email=email_lower,
        role=user.role,
        invitation_expires_at=token.expires_at,
        invite_link_url=invitation_url if include_invite_link else None,
    )


async def deactivate_user(session: AsyncSession, actor: CurrentUser, target_user_id: UUID) -> None:
    """USERS-04 / D-43-16 — self + last-owner guards, then UPDATE + revoke + audit.

    CR-04 (Phase 43 review) — single atomic UoW: repository UPDATE + session
    revoke + session_revoked_all audit + user_deactivated audit all commit
    together. The previous mid-flow commit inside revoke_all_sessions has
    been eliminated by splitting it into a no-commit variant (43-16 plan).

    WR-01 (Phase 43 review) — actor_user_id=actor.id plumbed into the
    invalidator so the session_revoked_all audit row attributes to the
    initiating owner, not the deactivated target.
    """
    target = await repository.get_alive(session, target_user_id)
    if target is None:
        raise UserNotFoundError("user_not_found")
    if not target.is_active:
        raise UserAlreadyInactiveError("user_already_inactive")
    if target.id == actor.id:
        raise CannotDeactivateSelfError("cannot_deactivate_self")
    if target.role == Role.OWNER:
        # CR-02/WR-05 (Phase 43 review) — count_active_owners_excluding now
        # locks the candidate-owner ROWS (not an aggregate) so parallel
        # deactivate attempts targeting the second-to-last owner serialise
        # at the row-lock layer. The first tx holds locks; the second blocks
        # until the first commits, then re-reads — exactly one wins.
        active_owner_count = await repository.count_active_owners_excluding(
            session, excluded_user_id=target_user_id
        )
        if active_owner_count < 1:
            raise CannotDeactivateLastOwnerError("cannot_deactivate_last_owner")

    await repository.deactivate_user(session, target_user_id=target_user_id, actor_user_id=actor.id)

    sessions_revoked = await get_user_session_invalidator()(
        session,
        user_id=target_user_id,
        actor_user_id=actor.id,  # WR-01 — owner attribution
        reason="deactivated",
    )

    await audit.emit(
        session,
        "user_deactivated",
        actor_user_id=actor.id,
        resource_type="user",
        resource_id=target_user_id,
        audit_correlation_id=None,  # IN-01 — terminal event, no downstream chain
        deactivated_user_id=str(target_user_id),
        sessions_revoked_count=sessions_revoked,
    )
    await session.flush()
    await session.commit()  # ONE commit covers UPDATE + revoke + both audits.


async def reactivate_user(session: AsyncSession, actor: CurrentUser, target_user_id: UUID) -> None:
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
        audit_correlation_id=None,  # IN-01 — terminal event, no downstream chain
        reactivated_user_id=str(target_user_id),
    )
    await session.flush()
    await session.commit()


async def change_user_role(
    session: AsyncSession,
    actor: CurrentUser,
    target_user_id: UUID,
    new_role: Role,
) -> None:
    """Phase 112 TEAM-01 — self + last-owner demotion guards, then UPDATE + audit.

    Effect timing: role persists immediately; the new role is reflected on the
    target's NEXT login. No session invalidation — existing sessions keep the old
    role until re-auth (per 112-CONTEXT.md D-112 effect-timing decision;
    T-112-13 accepted risk).

    Guard chain (mirrors deactivate_user guard order):
      1. get_alive → 404 UserNotFoundError if None (deleted or missing).
      2. target.id == actor.id → 409 CannotChangeOwnRoleError.
      3. Demoting owner → non-owner: count_active_owners_excluding row-lock;
         if count < 1 → 409 CannotChangeLastOwnerRoleError.
         Guard fires ONLY when target is currently OWNER and new_role != OWNER,
         so an owner→owner request never mis-fires the guard (no-op promotion).
    """
    target = await repository.get_alive(session, target_user_id)
    if target is None:
        raise UserNotFoundError("user_not_found")
    if target.id == actor.id:
        raise CannotChangeOwnRoleError("cannot_change_own_role")
    if target.role == Role.OWNER and new_role != Role.OWNER:
        # Demoting an owner — guard against stranding the gym with zero owners.
        # count_active_owners_excluding locks candidate-owner rows (CR-02/WR-05
        # lineage from deactivate_user) so parallel demotion attempts serialise.
        active_owner_count = await repository.count_active_owners_excluding(
            session, excluded_user_id=target_user_id
        )
        if active_owner_count < 1:
            raise CannotChangeLastOwnerRoleError("cannot_change_last_owner_role")

    await repository.update_user_role(session, target_user_id=target_user_id, new_role=new_role)

    await audit.emit(
        session,
        "user_role_changed",
        actor_user_id=actor.id,
        resource_type="user",
        resource_id=target_user_id,
        audit_correlation_id=None,  # IN-01 — terminal event, no downstream chain
        changed_user_id=str(target_user_id),
        old_role=target.role.value,
        new_role=new_role.value,
    )
    await session.flush()
    await session.commit()


async def soft_delete_user(session: AsyncSession, actor: CurrentUser, target_user_id: UUID) -> None:
    """USERS-05 / D-43-18 — same self+last-owner guards as deactivate.

    Allowed regardless of ``is_active`` state (the common case is delete after
    deactivate). Defensive session revoke covers the pure-delete-without-
    deactivate path. Pending invitations are atomic-consumed in the same UoW —
    no separate audit event (the parent ``user_soft_deleted`` covers it).

    CR-04 (Phase 43 review) — single atomic UoW: repository UPDATE + session
    revoke + invitation-consume + session_revoked_all audit + user_soft_deleted
    audit all commit together.

    WR-01 (Phase 43 review) — actor_user_id=actor.id plumbed into the invalidator.
    WR-03 (Phase 43 review) — actor.id plumbed into repository.soft_delete_user
    so the pure-delete path populates deactivated_by_user_id via COALESCE.
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

    await repository.soft_delete_user(
        session,
        target_user_id=target_user_id,
        actor_user_id=actor.id,  # WR-03 — COALESCE into deactivated_by_user_id
    )
    # Defensive — most deletes follow a deactivate (no families left), but
    # pure-delete-without-deactivate path needs the kill.
    await get_user_session_invalidator()(
        session,
        user_id=target_user_id,
        actor_user_id=actor.id,  # WR-01
        reason="soft_deleted",
    )
    # Atomic-consume pending invitation (no separate audit — parent event covers).
    await repository.consume_active_invitation_for_user(session, user_id=target_user_id)

    await audit.emit(
        session,
        "user_soft_deleted",
        actor_user_id=actor.id,
        resource_type="user",
        resource_id=target_user_id,
        audit_correlation_id=None,  # IN-01 — terminal event, no downstream chain
        deleted_user_id=str(target_user_id),
    )
    await session.flush()
    await session.commit()  # ONE commit covers UPDATE + revoke + invitation + both audits.


async def revoke_invitation(
    session: AsyncSession,
    actor: CurrentUser,
    token_id: UUID,
    reason: str | None,
) -> None:
    """USERS-03 / D-43-19 — atomic-consume invitation token; race-loss → 409.

    WR-06 (Phase 43 review) — expired-token pre-check raises
    InvitationExpiredError so the owner UI can distinguish "expired" from
    "already accepted". Both the pre-check and the race-loss against
    atomic_consume_invitation_token_by_id (now filtered on expires_at > now())
    fall back to the same domain error.

    REV-01 (quick 260614-jt7) — revoking a pending invitation also soft-deletes
    the placeholder user in the SAME UoW so the owner's team list no longer
    shows a zombie "Ожидает" row with no live invitation ("отозвать" =
    "разпригласить"). By the time we reach the soft-delete the token was just
    consumed from an unconsumed + unexpired state, so ``token.user_id`` is
    necessarily still a ``pending_invitation`` user (an accepted invite would
    have raised 409 above). A pending user is never the actor and never an
    active owner, so the active-user self / last-owner guards from
    ``soft_delete_user`` do not apply — the repository soft-delete is invoked
    directly. The single ``user_invitation_revoked`` audit row (with
    ``revoked_user_id``) is the forensic record of the removal; no separate
    ``user_soft_deleted`` event is emitted for this placeholder cleanup.
    """
    token = await repository.get_invitation_token_by_id(session, token_id)
    if token is None:
        raise InvitationNotFoundError("invitation_not_found")
    if token.consumed_at is not None:
        raise InvitationAlreadyAcceptedError("invitation_already_accepted")
    # WR-06 — expired tokens cannot be revoked (already useless, audit muddying).
    now = datetime.now(tz=UTC)
    if token.expires_at <= now:
        raise InvitationExpiredError("invitation_expired")

    consumed_id = await repository.atomic_consume_invitation_token_by_id(session, token_id)
    if consumed_id is None:
        # Race lost — another request consumed between get + UPDATE, OR
        # the token expired between the pre-check and the UPDATE (the
        # repository now filters on expires_at > now() too).
        raise InvitationAlreadyAcceptedError("invitation_already_accepted")

    await audit.emit(
        session,
        "user_invitation_revoked",
        actor_user_id=actor.id,
        resource_type="user",
        resource_id=token.user_id,
        audit_correlation_id=None,  # IN-01 — terminal event, no downstream chain
        revoked_user_id=str(token.user_id),
        invitation_token_id=str(token_id),
        reason=reason,
    )

    # REV-01 — un-invite the placeholder user (see docstring). Direct repository
    # soft-delete: deleted_at=now, is_active=False, deactivated_by=actor. The
    # token row itself is left intact (consumed) so the double-revoke 409 path
    # and the audit chain stay valid.
    await repository.soft_delete_user(
        session,
        target_user_id=token.user_id,
        actor_user_id=actor.id,
    )

    await session.flush()
    await session.commit()
