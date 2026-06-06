"""Trainer ORM (Phase 31 TRN-01, D-31-01/D-31-02/D-31-03).

Composes three base/mixin classes:
    Base + UUIDPkMixin + TimestampMixin + SoftDeleteMixin

NO created_by_user_id FK — trainers are owner-only reference data
without creator-attribution requirement (D-31-01).

Schema invariants:
- Partial unique index `uq_trainers_phone_alive WHERE deleted_at IS NULL AND
  phone IS NOT NULL` (D-31-03) — lives in __table_args__ + migration.
- `is_active BOOLEAN NOT NULL DEFAULT TRUE` — deactivation via PATCH (TRN-03).
- `deleted_at` column present (SoftDeleteMixin) but only for partial UNIQUE
  support; hard-delete is the actual delete operation (D-31-06).
"""

from sqlalchemy import Boolean, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, SoftDeleteMixin, TimestampMixin, UUIDPkMixin


class Trainer(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin):
    """Gym trainer / personal training staff (TRN-01)."""

    __tablename__ = "trainers"

    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    # Phase 88 TRNR-01/TRNR-02: profile fields (owner-write via PATCH, client-read via GET)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    specialization: Mapped[str | None] = mapped_column(Text, nullable=True)
    # photo_url: max_length=2048 enforced at DTO boundary (TrainerUpdateRequest);
    # scheme validation deferred to render layer (Plan 03 T-88-03).
    photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "uq_trainers_phone_alive",
            "phone",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND phone IS NOT NULL"),
        ),
    )
