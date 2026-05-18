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

from sqlalchemy import BigInteger, CheckConstraint, Text
from sqlalchemy import Enum as SAEnum
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

    __table_args__ = (
        CheckConstraint("role IN ('owner', 'reception')", name="role"),
    )
