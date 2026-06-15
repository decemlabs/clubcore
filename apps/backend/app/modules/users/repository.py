"""Phase 43 users module repository (USERS-01/02 — D-43-09).

NO ``commit`` and NO ``flush`` calls live here. The caller
(service) owns the transactional moment so it can co-write the audit log row
in the same UoW. Mirrors ``clients/repository.py`` D-03 lineage.

Returns ORM objects or primitive tuples. Pydantic validation happens in the
service / router layer via ``UserListItemResponse.model_validate(...)``.

D-43-09 partition pattern: every read helper appends ``User.deleted_at IS NULL``
as the first predicate (forensic-only ``deleted=True`` mode in ``list_alive``
is the single, explicit exception per D-43-15).

Invitation-token CRUD targets the Phase 41 0025 ``password_reset_tokens`` table
with ``purpose='invitation'`` (D-41-04 + D-43-13/19). All TIMESTAMPTZ writes use
``datetime.now(tz=UTC)`` per Pitfall 6 mitigation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import UUID

from sqlalchemy import Select, and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import User
from app.core.pagination import PaginatedData
from app.core.permissions import Role
from app.modules.auth.password_reset_token_model import PasswordResetToken
from app.modules.users.constants import INVITATION_TOKEN_TTL
from app.modules.users.schemas import UserListItemResponse, UserListQuery


def _now_utc() -> datetime:
    """TZ-aware UTC now (Pitfall 6 — all TIMESTAMPTZ writes use tz=UTC)."""
    return datetime.now(tz=UTC)


def _hash_token(raw_token: str) -> str:
    """SHA-256 hex of the raw token (mirrors ``password_reset_tokens.token_hash`` column)."""
    return sha256(raw_token.encode("utf-8")).hexdigest()


async def get_alive(session: AsyncSession, user_id: UUID) -> User | None:
    """Return alive user by id, or None for missing/soft-deleted (D-43-09 partition pattern)."""
    stmt: Select[tuple[User]] = select(User).where(
        User.id == user_id,
        User.deleted_at.is_(None),
    )
    result: User | None = await session.scalar(stmt)
    return result


async def get_by_email_for_create(session: AsyncSession, email_lower: str) -> User | None:
    """Lookup an alive (``deleted_at IS NULL``) user by lowercased email.

    Used by ``service.create_user`` (D-43-13) to branch between INSERT-new vs
    re-issue-invitation paths. The partial UNIQUE on ``lower(email)`` WHERE
    ``deleted_at IS NULL`` (Phase 41 0022) means soft-deleted rows for the same
    email are intentionally invisible here — that is the email-reclaim path
    (D-43-13 fourth bullet / Pitfall 4 INSERT-only invariant).
    """
    stmt: Select[tuple[User]] = select(User).where(
        func.lower(User.email) == email_lower,
        User.deleted_at.is_(None),
    )
    result: User | None = await session.scalar(stmt)
    return result


async def list_alive(
    session: AsyncSession, query: UserListQuery
) -> PaginatedData[UserListItemResponse]:
    """D-43-10 / D-43-15 paginated list of users.

    Predicates:
      - ``deleted_at IS NULL`` (unless ``query.deleted=True``, owner-only
        forensic mode — D-43-15)
      - ``is_active = :active`` when ``query.active`` is not None

    Sort: ``created_at DESC, id DESC`` (mirrors v1.2 clients list convention).

    For each user, LEFT JOIN to ``password_reset_tokens`` (the single active
    invitation):
      ``ON pt.user_id = u.id AND pt.purpose='invitation'``
      ``AND pt.consumed_at IS NULL AND pt.expires_at > now()``
    The partial UNIQUE ``(user_id, purpose) WHERE consumed_at IS NULL``
    (D-41-05) guarantees at most one active invitation per user, so the join
    cannot fan out — the row id (``invitation_token_id``, D-43-19) and
    ``expires_at`` (``invitation_expires_at``) are selected directly without a
    ``MAX``/``GROUP BY`` aggregation. Both are ``None`` for rows without an
    active invitation (D-43-10).

    Returns ``PaginatedData[UserListItemResponse]`` constructed via
    ``model_construct`` (mirrors clients repository — skips re-validation since
    each item is already a fully-validated Pydantic instance).
    """
    predicates: list[Any] = []
    if not query.deleted:
        predicates.append(User.deleted_at.is_(None))
    if query.active is not None:
        predicates.append(User.is_active.is_(query.active))

    # Total count — same predicate list, no ORDER/LIMIT.
    total_stmt = select(func.count()).select_from(User)
    if predicates:
        total_stmt = total_stmt.where(and_(*predicates))
    total = await session.scalar(total_stmt) or 0

    # Subquery for the single active invitation (id + expires_at) per user.
    # ≤1 active invitation per user (D-41-05 partial unique) → select directly,
    # no MAX/GROUP BY needed; the LEFT JOIN cannot fan out.
    now = _now_utc()
    invitation_subq = (
        select(
            PasswordResetToken.user_id.label("u_id"),
            PasswordResetToken.id.label("inv_token_id"),
            PasswordResetToken.expires_at.label("inv_expires_at"),
        )
        .where(
            PasswordResetToken.purpose == "invitation",
            PasswordResetToken.consumed_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .subquery()
    )

    stmt = select(
        User, invitation_subq.c.inv_token_id, invitation_subq.c.inv_expires_at
    ).outerjoin(invitation_subq, invitation_subq.c.u_id == User.id)
    if predicates:
        stmt = stmt.where(and_(*predicates))
    stmt = stmt.order_by(User.created_at.desc(), User.id.desc())
    offset = (query.page - 1) * query.page_size
    stmt = stmt.offset(offset).limit(query.page_size)

    rows = (await session.execute(stmt)).all()

    items: list[UserListItemResponse] = []
    for user_row, inv_token_id, inv_expires_at in rows:
        items.append(
            UserListItemResponse(
                id=user_row.id,
                email=user_row.email,
                full_name=user_row.full_name,
                role=user_row.role,
                is_active=user_row.is_active,
                status=user_row.status,
                created_at=user_row.created_at,
                deactivated_at=user_row.deactivated_at,
                deactivated_by_user_id=user_row.deactivated_by_user_id,
                invitation_expires_at=inv_expires_at,
                invitation_token_id=inv_token_id,
            )
        )

    return PaginatedData.model_construct(
        items=items,
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


async def insert_user_pending_invitation(
    session: AsyncSession,
    *,
    email_lower: str,
    full_name: str,
    role: Role,
) -> User:
    """D-43-13 first branch: INSERT a new ``pending_invitation`` user row.

    Caller MUST have verified (via ``get_by_email_for_create``) that no alive
    row exists for this email. The partial UNIQUE on ``lower(email)`` WHERE
    ``deleted_at IS NULL`` will raise IntegrityError on race-collision — the
    service-layer catches and translates to a 409.

    Caller flushes (not us — D-03) to surface IntegrityError AND populate
    ``user.id`` before the subsequent invitation-token INSERT.
    """
    user = User(
        email=email_lower,
        email_verified=False,
        password_hash=None,
        role=role,
        full_name=full_name,
        is_active=True,
        status="pending_invitation",
    )
    session.add(user)
    return user


async def insert_invitation_token(
    session: AsyncSession,
    *,
    user_id: UUID,
    raw_token: str,
    audit_correlation_id: UUID,
) -> PasswordResetToken:
    """D-43-13 / D-41-04 — INSERT a ``password_reset_tokens`` row with ``purpose='invitation'``.

    Caller MUST have ensured no active (``consumed_at IS NULL``) invitation
    exists for this user OR have consumed it first (D-43-13 second branch —
    re-invite path). ``expires_at = now() + INVITATION_TOKEN_TTL`` (D-43-12).
    """
    token = PasswordResetToken(
        user_id=user_id,
        purpose="invitation",
        token_hash=_hash_token(raw_token),
        expires_at=_now_utc() + INVITATION_TOKEN_TTL,
        audit_correlation_id=audit_correlation_id,
    )
    session.add(token)
    return token


async def consume_active_invitation_for_user(
    session: AsyncSession, *, user_id: UUID
) -> UUID | None:
    """D-43-13 second branch — atomic-consume any active invitation for ``user_id``.

    Returns the consumed token id, or None if no active invitation existed.
    Uses ``UPDATE ... RETURNING`` (single SQL) so the operation is race-tight
    against parallel ``POST /users`` calls for the same email. Partial UNIQUE
    on ``(user_id, purpose) WHERE consumed_at IS NULL`` (D-41-05) guarantees
    at most one row matches.
    """
    stmt = (
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.purpose == "invitation",
            PasswordResetToken.consumed_at.is_(None),
        )
        .values(consumed_at=_now_utc())
        .returning(PasswordResetToken.id)
    )
    result = await session.execute(stmt)
    row = result.first()
    return row.id if row else None


async def deactivate_user(
    session: AsyncSession,
    *,
    target_user_id: UUID,
    actor_user_id: UUID,
) -> None:
    """D-43-16 — atomic flip ``is_active=false`` + set ``deactivated_at/by``.

    Single UPDATE. Service layer owns pre-conditions (self / last-owner guard)
    and the transactional commit — repository only emits the SQL.

    IN-02 (Phase 43 review) — defence-in-depth predicate ``deleted_at IS NULL``:
    a race between a parallel soft-delete and this deactivate could otherwise
    re-flip ``is_active`` on a tombstoned row, violating the "soft-deleted
    rows are tombstones, never mutated again" invariant.
    """
    await session.execute(
        update(User)
        .where(
            User.id == target_user_id,
            User.deleted_at.is_(None),
        )
        .values(
            is_active=False,
            deactivated_at=_now_utc(),
            deactivated_by_user_id=actor_user_id,
        )
    )


async def reactivate_user(session: AsyncSession, *, target_user_id: UUID) -> None:
    """D-43-17 — atomic flip back to ``is_active=true``, clear deactivated_* fields.

    Mirrors the column-consistency CHECK constraint from migration 0030:
    ``(is_active=true AND deactivated_at IS NULL)``
    ``OR (is_active=false AND deactivated_at IS NOT NULL)``.

    IN-02 (Phase 43 review) — defence-in-depth predicate ``deleted_at IS NULL``
    so a tombstoned row cannot be silently un-deactivated by a race against
    a soft-delete.
    """
    await session.execute(
        update(User)
        .where(
            User.id == target_user_id,
            User.deleted_at.is_(None),
        )
        .values(
            is_active=True,
            deactivated_at=None,
            deactivated_by_user_id=None,
        )
    )


async def soft_delete_user(
    session: AsyncSession, *, target_user_id: UUID, actor_user_id: UUID
) -> None:
    """D-43-18 — set ``deleted_at=now()``, ``is_active=false``, ``deactivated_at=COALESCE(...)``,
    ``deactivated_by_user_id=COALESCE(existing, actor_user_id)``.

    Single UPDATE; ``COALESCE`` preserves existing ``deactivated_at`` /
    ``deactivated_by_user_id`` (common path: delete after deactivate, where
    the deactivate step already populated both) and falls back to now() /
    actor_user_id (pure-delete-without-deactivate path).

    WR-03 (Phase 43 review) — pre-fix code never wrote ``deactivated_by_user_id``
    on the pure-delete path, breaking the forensic chain ("which owner ended
    this account"). The COALESCE pattern preserves history on the post-deactivate
    path and fills the slot on the pure-delete path.

    IN-02 (Phase 43 review) — ``deleted_at IS NULL`` predicate already added in 43-15.
    """
    now = _now_utc()
    await session.execute(
        update(User)
        .where(
            User.id == target_user_id,
            User.deleted_at.is_(None),
        )
        .values(
            deleted_at=now,
            is_active=False,
            deactivated_at=func.coalesce(User.deactivated_at, now),
            deactivated_by_user_id=func.coalesce(
                User.deactivated_by_user_id,
                actor_user_id,
            ),
        )
    )


async def get_invitation_token_by_id(
    session: AsyncSession, token_id: UUID
) -> PasswordResetToken | None:
    """D-43-19 — owner UI shows the token row id; revoke endpoint resolves by it.

    Filters on ``purpose='invitation'`` so a stray ``password_reset`` token id
    never resolves through this codepath (defence in depth — Phase 44 owns the
    reset purpose).
    """
    stmt: Select[tuple[PasswordResetToken]] = select(PasswordResetToken).where(
        PasswordResetToken.id == token_id,
        PasswordResetToken.purpose == "invitation",
    )
    result: PasswordResetToken | None = await session.scalar(stmt)
    return result


async def atomic_consume_invitation_token_by_id(
    session: AsyncSession, token_id: UUID
) -> UUID | None:
    """D-43-19 — atomic-consume by id; race-loss → None → service maps to 409.

    WR-06 (Phase 43 review) — filtered on ``expires_at > now()`` so an
    expired-but-unconsumed token cannot be silently "consumed" by a revoke
    operation. The service-layer pre-check raises ``InvitationExpiredError``
    before reaching this query for the deterministic-error path; this filter
    is defence-in-depth for the race between the pre-check and the UPDATE.

    Mirrors the v1.1 refresh-token rotation race-loss pattern: a single
    ``UPDATE ... RETURNING`` against ``consumed_at IS NULL`` means a parallel
    consume by another endpoint loses the race and gets ``None`` back, which
    the service translates to ``invitation_already_accepted``.
    """
    stmt = (
        update(PasswordResetToken)
        .where(
            PasswordResetToken.id == token_id,
            PasswordResetToken.purpose == "invitation",
            PasswordResetToken.consumed_at.is_(None),
            PasswordResetToken.expires_at > _now_utc(),
        )
        .values(consumed_at=_now_utc())
        .returning(PasswordResetToken.id)
    )
    result = await session.execute(stmt)
    row = result.first()
    return row.id if row else None


async def update_user_role(
    session: AsyncSession,
    *,
    target_user_id: UUID,
    new_role: Role,
) -> None:
    """Phase 112 TEAM-01 — single UPDATE setting role on the target user row.

    Defence-in-depth predicate ``deleted_at IS NULL`` mirrors the pattern in
    ``deactivate_user`` / ``reactivate_user`` (IN-02 lineage): a tombstoned row
    cannot have its role silently mutated by a race against a soft-delete.

    NO commit / flush — service (caller) owns the transactional moment (D-03 /
    SVC001). The UPDATE is co-transactional with the audit.emit row inserted
    by the service.
    """
    await session.execute(
        update(User)
        .where(
            User.id == target_user_id,
            User.deleted_at.is_(None),
        )
        .values(role=new_role)
    )


async def count_active_owners_excluding(session: AsyncSession, *, excluded_user_id: UUID) -> int:
    """D-43-16 last-owner guard — lock candidate owner ROWS, count Python-side.

    CR-02 / WR-05 (Phase 43 review) — the pre-fix code used
    ``select(func.count()).with_for_update()`` which Postgres rejects with
    ``FOR UPDATE is not allowed with aggregate functions``. Even if Postgres
    allowed it, FOR UPDATE on an aggregate has no rows to lock and would
    serialise nothing.

    The fix selects the row ids of the candidate owners (those that would
    remain active+alive+non-pending if ``excluded_user_id`` were deactivated)
    with ``with_for_update()``, materialises the result set Python-side, and
    returns the length. Two parallel deactivate attempts targeting the
    second-to-last owner now actually serialise: the first transaction holds
    locks on the surviving owner rows; the second blocks on those locks until
    the first commits; the second then re-reads the (possibly reduced) set
    and refuses if the count dropped to zero.

    This is the genuine "v1.2 freeze-period serial-arbiter" pattern — lock
    specific rows, then assert the invariant over the locked set.
    """
    stmt = (
        select(User.id)
        .where(
            User.role == Role.OWNER,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
            User.id != excluded_user_id,
            User.status == "active",
        )
        .with_for_update()
    )
    result = await session.execute(stmt)
    return len(result.all())
