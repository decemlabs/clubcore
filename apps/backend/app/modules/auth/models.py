"""Auth ORM models — User (shim) / RefreshToken / OtpCode (Phase 5, D-03/D-04/D-06).

User does NOT compose SoftDeleteMixin (D-05). Operators are 1-2 people; hard-delete
after data export is acceptable. ON DELETE RESTRICT on `clients.created_by_user_id`
(Phase 8) blocks accidental orphans.

OtpCode ships its FINAL Phase 7 shape now (D-03). Phase 7 only writes app code,
no schema churn.

Phase 41 INFRA-40 / D-41-01 — ``User`` was hoisted to ``app.core.models``;
this module re-exports it as a one-milestone shim so every existing
``from app.modules.auth.models import User`` callsite keeps working.
v1.7 DEFER-41-shim removes this re-export — downstream callers should
migrate to ``from app.core.models import User`` at their convenience.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPkMixin

# Phase 41 INFRA-40 / D-41-01 — one-milestone shim. v1.7 DEFER-41-shim
# removes this re-export; downstream callers should migrate to
# `from app.core.models import User` at their convenience.
# Phase 63 DEBT-03: the pyflakes F401 suppression that previously sat on
# this line was REMOVED — the explicit ``__all__`` below (added per
# PITFALLS Pitfall #6) declares ``User`` as part of the module's public
# surface, which satisfies ruff/pyflakes' "imported but unused" check
# without needing a suppression directive.
from app.core.models import User

# Phase 42 AUTH-EM-01 / D-42-20 — OTP channel discriminator. Mirrors
# password_reset_token_model.py:38 PasswordResetTokenPurpose shape
# (Literal-as-TypeAlias). CHECK enforced at the DB layer via Alembic 0027.
OtpChannel = Literal["telegram", "email"]

# Phase 63 DEBT-03 / PITFALLS Pitfall #6 — explicit public surface so mypy
# --strict accepts the ``User`` re-export from ``app.core.models`` (line 34
# above). Without this, downstream ``from app.modules.auth.models import User``
# fires ``[attr-defined]``. Declaring ``User`` here in ``__all__`` also
# satisfies ruff's F401 (imported-but-unused) check, so the prior pyflakes
# suppression on the re-export line is no longer required.
__all__ = [
    "OtpChannel",  # Phase 42 AUTH-EM-01 / D-42-20 (line 35 above)
    "OtpCode",  # this module
    "RefreshToken",  # this module
    "User",  # Phase 41 INFRA-40 / D-41-01 re-export shim (line 30 above)
]


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

    __table_args__ = (Index("ix_refresh_tokens_user_id_family_id", "user_id", "family_id"),)


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
    # Phase 68 D-03 — nullable FK for client OTP rows.  XOR CHECK (below in
    # __table_args__) enforces exactly one of (user_id, client_id) non-null.
    client_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=True,
    )
    telegram_chat_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    # Phase 42 AUTH-EM-01 / D-42-20 — schema-side shipped by Alembic 0027.
    # ``server_default='telegram'`` matches the migration's column-DEFAULT
    # zero-row backfill; placed next to ``telegram_chat_id`` for locality
    # with the legacy channel.
    channel: Mapped[OtpChannel] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'telegram'"),
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

    __table_args__ = (
        # Phase 42 AUTH-EM-01 / D-42-20 — partial UNIQUE on
        # ``(user_id, channel) WHERE consumed_at IS NULL``. Declared in
        # BOTH ORM ``__table_args__`` and Alembic 0027 with the SAME
        # literal name + identical ``postgresql_where`` text so
        # SQLAlchemy + Alembic compare clean (mirrors
        # ``password_reset_token_model.py:94-100``). Allows one active
        # Telegram OTP AND one active email OTP per user simultaneously.
        Index(
            "uq_otp_codes_user_channel_active",
            "user_id",
            "channel",
            unique=True,
            postgresql_where=text("consumed_at IS NULL"),
        ),
        # Phase 68 D-03 — XOR CHECK: exactly one of (user_id, client_id) must
        # be non-null.  Prevents ownership confusion (T-68-01).
        CheckConstraint(
            "(user_id IS NULL) <> (client_id IS NULL)",
            name="ck_otp_codes_principal_xor",
        ),
        # Phase 68 D-03 — mirrors the staff partial-unique for client principal
        # single-active uniqueness (one active OTP per client + channel).
        Index(
            "uq_otp_codes_client_channel_active",
            "client_id",
            "channel",
            unique=True,
            postgresql_where=text("consumed_at IS NULL"),
        ),
    )
