"""Core-owned ORM models hoisted out of feature modules.

Phase 41 INFRA-40 / D-41-01 — hoist ``User`` here so both ``auth`` and ``users``
modules can co-own it without crossing the ``core ⊥ modules`` import-linter
contract. Importing from ``app.modules.auth.models`` continues to work via
the one-milestone shim (D-41-01); v1.7 milestone removes the shim
(DEFER-41-shim).

Scope rule (D-41-01): one file per cohesive concern. ``audit_models.py``
stays separate. Future hoists land here only when they have the same
"shared between auth and another module" justification.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Text,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPkMixin
from app.core.permissions import Role


class User(Base, UUIDPkMixin, TimestampMixin):
    """Operator user (D-06). 1-2 rows total — `full_name` is a single column (D-01).

    Phase 43 D-43-06/08: ``password_hash`` is now nullable — invited-but-unaccepted
    rows carry NULL until invitation-accept (Phase 44 RESET-04) sets the password.
    `telegram_chat_id` is BIGINT NULL UNIQUE from day one (D-02) so Phase 7's bind
    flow is a plain `UPDATE users SET telegram_chat_id = ... WHERE id = ...`.
    `role` is TEXT + CHECK constraint (D-07), NOT a native PG enum.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("FALSE"),
    )
    # D-43-06 Phase 43: drops NOT NULL — invited-but-unaccepted rows carry NULL
    # until invitation-accept (Phase 44 RESET-04) sets the password.
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[Role] = mapped_column(
        SAEnum(
            Role,
            native_enum=False,
            length=16,
            validate_strings=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    telegram_chat_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        unique=True,
    )
    telegram_username: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        unique=True,
    )

    # Phase 41 0022 column — ORM mirror added in Phase 43 D-43-08 (deferred from
    # Phase 41 plan-05 which shipped DB-only; soft-delete consumers land here).
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Phase 43 D-43-08 — user lifecycle columns (migration 0030).
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    status: Mapped[Literal["active", "pending_invitation"]] = mapped_column(
        SAEnum(
            "active",
            "pending_invitation",
            name="user_status",
            native_enum=False,
            length=32,
            validate_strings=True,
        ),
        nullable=False,
        server_default=text("'active'"),
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deactivated_by_user_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint("role IN ('owner', 'reception')", name="role"),
    )
