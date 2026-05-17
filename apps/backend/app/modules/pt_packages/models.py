"""PtPackagePlan + PtPackage ORM models (Phase 33 PT-01 / PT-04).

PtPackagePlan composition: Base + UUIDPkMixin + TimestampMixin + SoftDeleteMixin.

PtPackage composition: Base + UUIDPkMixin + TimestampMixin (NO SoftDeleteMixin —
lifecycle is purely status-based per Phase 17 D-12 precedent / D-33-03).

DB-level invariants (PtPackagePlan, D-33-02):
- session_count > 0      (CHECK ck_pt_package_plans_session_count_positive)
- price_kopecks > 0      (CHECK ck_pt_package_plans_price_kopecks_positive)
- validity_days IS NULL OR validity_days > 0
                         (CHECK ck_pt_package_plans_validity_days_positive)
- lower(name) is partial-unique among alive rows
  (uq_pt_package_plans_name_alive WHERE deleted_at IS NULL).
  Expression index — declared here in __table_args__ for ORM awareness,
  installed via raw op.execute() in the migration, and suppressed in
  alembic/env.py:_include_object to keep autogenerate clean.

DB-level invariants (PtPackage, D-33-03):
- status IN ('active', 'exhausted', 'expired', 'cancelled')
                         (CHECK ck_pt_packages_status)
- sessions_remaining >= 0 AND sessions_remaining <= session_count_snapshot
                         (CHECK ck_pt_packages_sessions_remaining_bounded;
                          defence-in-depth for Phase 34 decrement)
- session_count_snapshot / price_kopecks_snapshot > 0
                         (CHECK ck_pt_packages_session_count_snapshot_positive,
                          ck_pt_packages_price_kopecks_snapshot_positive)
- validity_days_snapshot IS NULL OR validity_days_snapshot > 0
                         (CHECK ck_pt_packages_validity_days_snapshot_positive)
- FK fk_pt_packages_client_id_clients ON DELETE RESTRICT to clients.id
- FK fk_pt_packages_plan_id_pt_package_plans ON DELETE RESTRICT to
  pt_package_plans.id (audit-trail integrity; archive of plan keeps historical
  instances readable via snapshot fields per D-33-08)
- Partial UNIQUE uq_pt_packages_active_per_client on (client_id) WHERE
  status='active' — one active PT-package per client (D-33-09; Plan 33-02 sale
  catches IntegrityError via _is_active_pt_package_conflict discriminator).
"""

from __future__ import annotations

from datetime import date
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
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


class PtPackagePlan(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin):
    """PT-package plan / SKU (Phase 33 PT-01 / D-33-02)."""

    __tablename__ = "pt_package_plans"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    session_count: Mapped[int] = mapped_column(Integer, nullable=False)
    price_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    validity_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        # NAMING_CONVENTION expands to ck_pt_package_plans_session_count_positive
        CheckConstraint("session_count > 0", name="session_count_positive"),
        # NAMING_CONVENTION expands to ck_pt_package_plans_price_kopecks_positive
        CheckConstraint("price_kopecks > 0", name="price_kopecks_positive"),
        # NAMING_CONVENTION expands to ck_pt_package_plans_validity_days_positive
        CheckConstraint(
            "validity_days IS NULL OR validity_days > 0",
            name="validity_days_positive",
        ),
        Index(
            "uq_pt_package_plans_name_alive",
            text("lower(name)"),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )


class PtPackage(Base, UUIDPkMixin, TimestampMixin):
    """PT-package instance — client X bought plan Y on date Z (Phase 33 PT-04).

    Snapshot pricing is immutable; status drives lifecycle. NO soft-delete
    column (D-33-03 mirror of Phase 17 D-12) — cancelled / expired / exhausted
    rows keep their FK references and block plan deletion (D-33-08).

    Structurally satisfies the `ActivePtPackage` Protocol that Plan 33-02
    declares in core/dependencies.py (matches on id, client_id, status,
    sessions_remaining, end_date — D-33-12). No DTO conversion at the
    resolver boundary.
    """

    __tablename__ = "pt_packages"

    client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "clients.id",
            ondelete="RESTRICT",
            name="fk_pt_packages_client_id_clients",
        ),
        nullable=False,
    )
    plan_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "pt_package_plans.id",
            ondelete="RESTRICT",
            name="fk_pt_packages_plan_id_pt_package_plans",
        ),
        nullable=False,
    )
    # Phase 38 PKG-01 / C-08 — optional trainer association (added in
    # Alembic 0018). NULL = "any trainer" (booking trainer-mismatch guard
    # short-circuits per C-08). FK ON DELETE RESTRICT — trainers are
    # soft-deleted via is_active (Phase 31 TRN-04); never hard-deleted.
    trainer_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "trainers.id",
            ondelete="RESTRICT",
            name="fk_pt_packages_trainer_id_trainers",
        ),
        nullable=True,
    )
    plan_name_snapshot: Mapped[str] = mapped_column(String(120), nullable=False)
    session_count_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    price_kopecks_snapshot: Mapped[int] = mapped_column(BigInteger, nullable=False)
    validity_days_snapshot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sessions_remaining: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        server_default=text("'active'"),
        nullable=False,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        # NAMING_CONVENTION expands to ck_pt_packages_status
        CheckConstraint(
            "status IN ('active', 'exhausted', 'expired', 'cancelled')",
            name="status",
        ),
        # NAMING_CONVENTION expands to ck_pt_packages_sessions_remaining_bounded
        CheckConstraint(
            "sessions_remaining >= 0 AND sessions_remaining <= session_count_snapshot",
            name="sessions_remaining_bounded",
        ),
        # NAMING_CONVENTION expands to ck_pt_packages_session_count_snapshot_positive
        CheckConstraint(
            "session_count_snapshot > 0",
            name="session_count_snapshot_positive",
        ),
        # NAMING_CONVENTION expands to ck_pt_packages_price_kopecks_snapshot_positive
        CheckConstraint(
            "price_kopecks_snapshot > 0",
            name="price_kopecks_snapshot_positive",
        ),
        # NAMING_CONVENTION expands to ck_pt_packages_validity_days_snapshot_positive
        CheckConstraint(
            "validity_days_snapshot IS NULL OR validity_days_snapshot > 0",
            name="validity_days_snapshot_positive",
        ),
        Index(
            "uq_pt_packages_active_per_client",
            "client_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_pt_packages_client_id", "client_id"),
        Index("ix_pt_packages_status", "status"),
        Index("ix_pt_packages_plan_id", "plan_id"),
        # Phase 38 PKG-01 — forensic lookup on trainer association (Alembic 0018).
        Index("ix_pt_packages_trainer_id", "trainer_id"),
    )
