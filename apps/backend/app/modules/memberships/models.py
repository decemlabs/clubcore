"""MembershipPlan ORM model (Phase 16, MEM-PLAN-01).

Composition: Base + UUIDPkMixin + TimestampMixin + SoftDeleteMixin.

DB-level invariants:
- duration_days > 0 (CHECK ck_membership_plans_duration_days_positive)
- price_kopecks >= 0 (CHECK ck_membership_plans_price_kopecks_nonneg)
- lower(name) is partial-unique among alive rows (uq_membership_plans_name_alive,
  WHERE deleted_at IS NULL). Expression index — declared in __table_args__ for
  ORM awareness, installed via raw op.execute in the migration, and suppressed in
  alembic/env.py:_include_object to keep autogenerate clean.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Index, Integer, String, text
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
