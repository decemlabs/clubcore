"""Visit ORM (Phase 19 VIS-02).

Composition: Base + UUIDPkMixin + TimestampMixin (CD-04: visits are immutable
historical records — no soft-delete column; lifecycle is the audit log, not a
deleted_at flag; the soft-delete mixin is intentionally excluded).

DB-level invariants:
- channel IN ('reception', 'telegram_bot') (CHECK ck_visits_channel)
- UNIQUE (client_id, gym_date) — unconditional, no WHERE partial (uq_visits_client_id_gym_date).
  Constraint name is literal-ref'd by service.py:_is_duplicate_visit_conflict (D-08).
- FK fk_visits_client_id_clients ON DELETE RESTRICT to clients.id
- FK fk_visits_membership_id_memberships ON DELETE RESTRICT to memberships.id
- FK fk_visits_checked_in_by_users ON DELETE SET NULL to users.id
- gym_date is a STORED GENERATED column: Computed("(checked_in_at AT TIME ZONE
  'Europe/Moscow')::date", persisted=True) so SA autogenerate stays in sync with
  the 0006_visits migration (D-06). The app NEVER writes this column directly.
- Composite index ix_visits_client_id_checked_in_at on (client_id, checked_in_at DESC)
  for the per-client history feed (VIS-EP-01).
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPkMixin


class Visit(Base, UUIDPkMixin, TimestampMixin):
    """Visit row — one client check-in (Phase 19 VIS-01).

    Structurally satisfies the audit event shape for visit_created:
    client_id, membership_id, channel live here as first-class attributes.
    The gym_date STORED GENERATED column is the race-proof 1/day enforcement
    mechanism (Pitfall 5 mitigation — D-06).
    """

    __tablename__ = "visits"

    client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "clients.id",
            ondelete="RESTRICT",
            name="fk_visits_client_id_clients",
        ),
        nullable=False,
    )
    membership_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "memberships.id",
            ondelete="RESTRICT",
            name="fk_visits_membership_id_memberships",
        ),
        nullable=False,
    )
    checked_in_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
    gym_date: Mapped[date] = mapped_column(
        Date,
        Computed(
            "(checked_in_at AT TIME ZONE 'Europe/Moscow')::date",
            persisted=True,
        ),
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    checked_in_by: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
            name="fk_visits_checked_in_by_users",
        ),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "channel IN ('reception', 'telegram_bot')",
            # NAMING_CONVENTION expands to ck_visits_channel
            name="channel",
        ),
        UniqueConstraint(
            "client_id",
            "gym_date",
            # Literal-ref'd by service.py:_is_duplicate_visit_conflict (D-08).
            name="uq_visits_client_id_gym_date",
        ),
        Index(
            "ix_visits_client_id_checked_in_at",
            "client_id",
            text("checked_in_at DESC"),
        ),
    )
