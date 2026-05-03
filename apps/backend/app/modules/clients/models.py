"""Client ORM + Gender enum (Phase 8 CLIENTS-01, D-15..D-17).

Composes all four base/mixin classes:
    Base + UUIDPkMixin + TimestampMixin + SoftDeleteMixin

Schema invariants enforced at DB level:
- Partial unique index `uq_clients_phone_alive WHERE deleted_at IS NULL`
  (CLIENTS-02) — phone uniqueness applies only to alive rows. Soft-deleted
  clients keep their phone, allowing re-registration without history loss.
- CHECK `gender IN ('male', 'female')` (D-15) — defence in depth even if
  Pydantic validation is bypassed.
- `tags TEXT[]` with `server_default ARRAY[]::TEXT[]` (D-16, Pitfall 6) —
  inserts that omit `tags` get an empty list, not NULL.
- `emergency_contact JSONB NULL` (D-17) — free-shape contact blob owned by UI.
- `created_by_user_id` is FK ON DELETE RESTRICT — operator deletion is blocked
  while their created clients exist (audit retention).
- `telegram_user_id BIGINT UNIQUE` — bot binding flow (Phase 8+).

GIN trigram indexes `ix_clients_{first,last}_name_trgm` are NOT declared in
`__table_args__` — they live only in the migration via raw `op.execute(...)`
because SQLAlchemy autogenerate cannot represent expression indexes
(`lower(col) gin_trgm_ops`). Plan 08 (tests) installs an env.py
`include_object` filter to suppress the resulting autogenerate drift for
those two indexes.
"""

from datetime import date, datetime  # noqa: F401  -- datetime used by mixin Mapped types
from enum import StrEnum
from typing import Any
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    ARRAY,
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, SoftDeleteMixin, TimestampMixin, UUIDPkMixin


class Gender(StrEnum):
    """Client gender (D-15). Closed enum — only male/female v1."""

    MALE = "male"
    FEMALE = "female"


class Client(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin):
    """Gym client / member (CLIENTS-01)."""

    __tablename__ = "clients"

    last_name: Mapped[str] = mapped_column(Text, nullable=False)
    first_name: Mapped[str] = mapped_column(Text, nullable=False)
    middle_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    birthday: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[Gender | None] = mapped_column(
        SAEnum(
            Gender,
            native_enum=False,
            length=16,
            validate_strings=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=True,
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("ARRAY[]::TEXT[]"),
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    emergency_contact: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    telegram_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    created_by_user_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "gender IN ('male', 'female')",
            name="ck_clients_gender",
        ),
        UniqueConstraint("telegram_user_id", name="uq_clients_telegram_user_id"),
        Index(
            "uq_clients_phone_alive",
            "phone",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )
