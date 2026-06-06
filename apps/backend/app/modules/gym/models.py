"""GymInfo singleton ORM model (Phase 86 GYM-01, D-31-08).

This is the ONLY module that imports the `GymInfo` ORM model.
Singleton table — one row, seeded via migration 0059. No SoftDeleteMixin
(singleton cannot be deleted). No created_by FK (owner-level reference data).

JSONB list columns (hours, amenities, rules, social) carry server_default '[]'::jsonb
so the row is always valid even if fields are omitted at insert time.
"""

from typing import Any

from sqlalchemy import Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPkMixin


class GymInfo(Base, UUIDPkMixin, TimestampMixin):
    """Gym facility info singleton (GYM-01).

    One row only — seeded by migration 0059_seed_gym_info with deterministic PK
    00000000-0000-0000-0000-000000000001. The singleton pattern means there is
    no per-row soft-delete; the row is permanent reference data managed by the owner.
    """

    __tablename__ = "gym_info"

    # Scalar text columns
    name: Mapped[str] = mapped_column(Text, nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    tagline: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(Text, nullable=True)
    metro: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)

    # JSONB list columns — server_default '[]'::jsonb ensures a valid empty list
    hours: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    amenities: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    rules: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    social: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
