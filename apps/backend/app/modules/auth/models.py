"""Auth ORM models — User / RefreshToken / OtpCode (Phase 5, D-03/D-04/D-06).

User does NOT compose SoftDeleteMixin (D-05). Operators are 1-2 people; hard-delete
after data export is acceptable. ON DELETE RESTRICT on `clients.created_by_user_id`
(Phase 8) blocks accidental orphans.

OtpCode ships its FINAL Phase 7 shape now (D-03). Phase 7 only writes app code,
no schema churn.
"""

from datetime import datetime
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPkMixin
from app.core.permissions import Role


class User(Base, UUIDPkMixin, TimestampMixin):
    """Operator user (D-06). 1-2 rows total — `full_name` is a single column (D-01).

    `password_hash` is NOT NULL (D-02): Phase 5 only mints email/password users.
    `telegram_chat_id` is BIGINT NULL UNIQUE from day one (D-02) so Phase 7's bind
    flow is a plain `UPDATE users SET telegram_chat_id = ... WHERE id = ...`.
    `role` is TEXT + CHECK constraint (D-07), NOT a native PG enum.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[Role] = mapped_column(
        SAEnum(
            Role,
            native_enum=False,
            length=16,
            validate_strings=True,
            values_callable=lambda enum: [m.value for m in enum],
        ),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    telegram_chat_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        unique=True,
    )

    __table_args__ = (
        CheckConstraint("role IN ('owner', 'reception')", name="role"),
    )


class RefreshToken(Base, UUIDPkMixin, TimestampMixin):
    """Refresh token row (D-04).

    `replaced_by_id` is a self-FK with ON DELETE SET NULL so the rotation chain
    survives ancestor deletion. `family_id` carries across one rotation chain;
    reuse outside the ~5s window revokes the entire family.
    """

    __tablename__ = "refresh_tokens"

    user_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    family_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    replaced_by_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("refresh_tokens.id", ondelete="SET NULL"),
        nullable=True,
    )
    replaced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_refresh_tokens_user_id_family_id", "user_id", "family_id"),
    )


class OtpCode(Base, UUIDPkMixin, TimestampMixin):
    """OTP / deep-link token row (D-03).

    Final Phase 7 shape. Phase 5 creates the table empty — no `/auth/telegram/*`
    endpoints write to it yet. `user_id` and `code_hash` are NULL until the bot
    worker binds the chat (Phase 7); `deep_link_token_hash` is set at /telegram/start.
    """

    __tablename__ = "otp_codes"

    user_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    telegram_chat_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    deep_link_token_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
    )
    code_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
