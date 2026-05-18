"""PasswordResetToken ORM — unified reset/invitation token table.

Phase 41 INFRA-38 / D-41-03/04/05 — ORM half of migration 0025. Single table
(``password_reset_tokens``) backs BOTH the password-reset flow (Phase 44
RESET-01..05) and the invitation flow (Phase 44 USERS-03 invite-accept).
The ``purpose`` column discriminates between the two and is constrained
to ``{'password_reset', 'invitation'}`` at the DB layer via a CHECK
constraint declared in the migration.

Eager-imported by ``app/workers/__init__.py`` per REG-29-04 / D-41-29 so
``Base.metadata.tables`` is populated before any cron one-shot script runs.
Phase 44 ships the actual callsite (``POST /api/v1/auth/password-reset/{request,confirm}``)
— this module ships only the schema-side mapping.

No ``relationship()`` back to ``User`` (D-41-04 footnote): v1.6 callsites
query by ``user_id`` UUID directly; no join requirement. Adding the
relationship would force every auth-side ``User`` import to drag this
model with it, complicating the v1.7 ``DEFER-41-shim`` cleanup.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPkMixin

PasswordResetTokenPurpose = Literal["password_reset", "invitation"]


class PasswordResetToken(Base, UUIDPkMixin, TimestampMixin):
    """Row-per-issued-token for password-reset and invitation flows (D-41-04).

    ``token_hash`` is sha256(raw_token) — the raw opaque token only ever
    exists in the URL fragment of the email body (T-41-09-01). ``consumed_at``
    is both the atomic-consume marker AND the revocation marker (D-41-04);
    the reason (redeemed vs revoked) lives in the audit-event payload.

    ``audit_correlation_id`` chains the issuing audit event
    (``password_reset_requested`` / ``user_invited``) to the eventual consume
    audit event so forensic queries can walk the full token lifecycle by a
    single UUID (D-41-04 / D-41-20).
    """

    __tablename__ = "password_reset_tokens"

    user_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    purpose: Mapped[PasswordResetTokenPurpose] = mapped_column(
        Text,
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    audit_correlation_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        nullable=False,
    )

    __table_args__ = (
        # CHECK constraint name MUST match migration 0025 letter-for-letter so
        # `alembic check` produces an empty diff. The naming_convention in
        # core/database.py expands `name="purpose"` to
        # `ck_password_reset_tokens_purpose` (matches op.f() in the migration).
        CheckConstraint(
            "purpose IN ('password_reset', 'invitation')",
            name="purpose",
        ),
        # Partial UNIQUE (D-41-05) — declared in BOTH ORM `__table_args__` and
        # migration 0025 with the SAME literal name (mirrors the bookings
        # `uq_bookings_slot_confirmed` pattern, models.py:165). SQLAlchemy +
        # Alembic compare the partial-Index round-trip on the literal
        # `postgresql_where` SQL text — keep them byte-identical.
        Index(
            "uq_password_reset_tokens_active",
            "user_id",
            "purpose",
            unique=True,
            postgresql_where=text("consumed_at IS NULL"),
        ),
        # Non-UNIQUE hash-lookup index (D-41-04). Phase 44's confirm path:
        # UPDATE password_reset_tokens
        #    SET consumed_at = NOW()
        #  WHERE token_hash = :hash AND purpose = :purpose
        #    AND consumed_at IS NULL
        # RETURNING id, user_id, audit_correlation_id;
        Index(
            "ix_password_reset_tokens_token_hash",
            "token_hash",
        ),
    )
