"""OnlinePayment ORM model (Phase 49 PAY-01 / D-49-04).

Mirrors the 0034 migration column-for-column. Class composition is
``Base + UUIDPkMixin`` ONLY — no TimestampMixin, no SoftDeleteMixin —
because the FSM tracks lifecycle via explicit ``initiated_at`` /
``succeeded_at`` / ``canceled_at`` columns (single-temporal-column
discipline per payments/models.py:46-49).

Constraint naming discipline (NAMING_CONVENTION):
- CheckConstraints use BARE suffixes (``"amount_kopecks_positive"``)
  so ``ck_%(table_name)s_%(constraint_name)s`` expands to the same
  literal Alembic 0034 wrote via ``op.f("ck_online_payments_*")``.
  Plan 49-02 originally specified full names — that would have
  double-prefixed to ``ck_online_payments_ck_online_payments_*``,
  the exact bug fixed by Plan 49-01 deviation #2.
- ForeignKey + UniqueConstraint + Index pass full literal names
  (no convention-expansion for those families when explicit).
- Partial UNIQUE per-day expression uses
  ``((initiated_at AT TIME ZONE 'Europe/Moscow')::date)`` — IMMUTABLE
  per Postgres rules; ``DATE(timestamptz)`` is rejected on the
  partial-index predicate. Matches migration 0034 verbatim
  (Plan 49-01 deviation #1).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UUIDPkMixin


class OnlinePayment(Base, UUIDPkMixin):
    """ЮKassa-side online payment ledger row (Phase 49 PAY-01 / D-49-04)."""

    __tablename__ = "online_payments"

    client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "clients.id",
            ondelete="RESTRICT",
            name="fk_online_payments_client_id_clients",
        ),
        nullable=False,
    )
    membership_plan_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "membership_plans.id",
            ondelete="RESTRICT",
            name="fk_online_payments_membership_plan_id_membership_plans",
        ),
        nullable=True,
    )
    pt_package_plan_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "pt_package_plans.id",
            ondelete="RESTRICT",
            name="fk_online_payments_pt_package_plan_id_pt_package_plans",
        ),
        nullable=True,
    )
    yookassa_payment_id: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    amount_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    confirmation_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmation_type: Mapped[str] = mapped_column(Text, nullable=False)
    initiated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    succeeded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    canceled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by_user_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
            name="fk_online_payments_created_by_user_id_users",
        ),
        nullable=True,
    )
    audit_correlation_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "amount_kopecks > 0",
            # NAMING_CONVENTION expands to ck_online_payments_amount_kopecks_positive
            name="amount_kopecks_positive",
        ),
        CheckConstraint(
            "status IN ('pending','succeeded','canceled')",
            # NAMING_CONVENTION expands to ck_online_payments_status
            name="status",
        ),
        CheckConstraint(
            "confirmation_type IN ('redirect','qr')",
            # NAMING_CONVENTION expands to ck_online_payments_confirmation_type
            name="confirmation_type",
        ),
        CheckConstraint(
            "(membership_plan_id IS NOT NULL) <> (pt_package_plan_id IS NOT NULL)",
            # NAMING_CONVENTION expands to ck_online_payments_exactly_one_subject_fk
            name="exactly_one_subject_fk",
        ),
        UniqueConstraint(
            "yookassa_payment_id",
            name="uq_online_payments_yookassa_payment_id",
        ),
        UniqueConstraint(
            "idempotency_key",
            name="uq_online_payments_idempotency_key",
        ),
        Index(
            "uq_online_payments_membership_double_tap",
            "client_id",
            "membership_plan_id",
            text("((initiated_at AT TIME ZONE 'Europe/Moscow')::date)"),
            unique=True,
            postgresql_where=text(
                "status != 'canceled' AND membership_plan_id IS NOT NULL"
            ),
        ),
        Index(
            "uq_online_payments_pt_package_double_tap",
            "client_id",
            "pt_package_plan_id",
            text("((initiated_at AT TIME ZONE 'Europe/Moscow')::date)"),
            unique=True,
            postgresql_where=text(
                "status != 'canceled' AND pt_package_plan_id IS NOT NULL"
            ),
        ),
    )
