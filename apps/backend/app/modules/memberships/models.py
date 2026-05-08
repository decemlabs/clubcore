"""MembershipPlan ORM model (Phase 16, MEM-PLAN-01).

Composition: Base + UUIDPkMixin + TimestampMixin + SoftDeleteMixin.

DB-level invariants:
- duration_days > 0 (CHECK ck_membership_plans_duration_days_positive)
- price_kopecks >= 0 (CHECK ck_membership_plans_price_kopecks_nonneg)
- lower(name) is partial-unique among alive rows (uq_membership_plans_name_alive,
  WHERE deleted_at IS NULL). Expression index — declared in __table_args__ for
  ORM awareness, installed via raw op.execute in the migration, and suppressed in
  alembic/env.py:_include_object to keep autogenerate clean.

Phase 17 / MEM-01 — Membership ORM model added below.

Composition: Base + UUIDPkMixin + TimestampMixin (NO SoftDeleteMixin — lifecycle
is purely status-based per Phase 17 D-12 / CONTEXT.md domain line 12).

DB-level invariants:
- status IN ('active', 'expired', 'cancelled') (CHECK ck_memberships_status)
- activation_policy = 'purchase_date' (CHECK ck_memberships_activation_policy)
- FK fk_memberships_client_id_clients ON DELETE RESTRICT to clients.id
- FK fk_memberships_plan_id_membership_plans ON DELETE RESTRICT to membership_plans.id
  (constraint name is literal-ref'd by service.py:_is_plan_in_use_conflict per D-05)
- Composite index ix_memberships_client_id_status_end_date on
  (client_id, status, end_date DESC) — covers the active-membership resolver
  query. DESC ordering installed via raw op.execute() in the migration.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, SoftDeleteMixin, TimestampMixin, UUIDPkMixin


class MembershipPlan(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin):
    """Gym membership plan / SKU (MEM-PLAN-01)."""

    __tablename__ = "membership_plans"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    price_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    __table_args__ = (
        CheckConstraint(
            "duration_days > 0",
            # NAMING_CONVENTION expands to ck_membership_plans_duration_days_positive
            name="duration_days_positive",
        ),
        CheckConstraint(
            "price_kopecks >= 0",
            # NAMING_CONVENTION expands to ck_membership_plans_price_kopecks_nonneg
            name="price_kopecks_nonneg",
        ),
        Index(
            "uq_membership_plans_name_alive",
            text("lower(name)"),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )


class Membership(Base, UUIDPkMixin, TimestampMixin):
    """Membership instance — client X bought plan Y on date Z (MEM-01).

    Snapshot pricing is immutable; status drives lifecycle. NO soft-delete
    column (Phase 17 D-12 / CONTEXT.md domain line 12) — cancelled rows
    keep their FK reference and block plan deletion (D-06).

    Structurally satisfies the `ActiveMembership` Protocol that Plan 17-02
    declares in core/dependencies.py (matches on id, client_id, end_date,
    status — D-18). No DTO conversion at the resolver boundary.
    """

    __tablename__ = "memberships"

    client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "clients.id",
            ondelete="RESTRICT",
            name="fk_memberships_client_id_clients",
        ),
        nullable=False,
    )
    plan_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "membership_plans.id",
            ondelete="RESTRICT",
            # Literal-ref'd by service.py:_is_plan_in_use_conflict (D-05).
            name="fk_memberships_plan_id_membership_plans",
        ),
        nullable=False,
    )
    plan_name_snapshot: Mapped[str] = mapped_column(String(120), nullable=False)
    duration_days_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    price_kopecks_snapshot: Mapped[int] = mapped_column(BigInteger, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        server_default=text("'active'"),
        nullable=False,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    activation_policy: Mapped[str] = mapped_column(
        String(32),
        server_default=text("'purchase_date'"),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'expired', 'cancelled', 'frozen')",
            # NAMING_CONVENTION expands to ck_memberships_status
            name="status",
        ),
        CheckConstraint(
            "activation_policy = 'purchase_date'",
            # NAMING_CONVENTION expands to ck_memberships_activation_policy
            name="activation_policy",
        ),
        Index(
            "ix_memberships_client_id_status_end_date",
            "client_id",
            "status",
            text("end_date DESC"),
        ),
    )
