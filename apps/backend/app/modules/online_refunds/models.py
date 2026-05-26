"""OnlineRefund ORM model (Phase 51 REFUND-01 / D-51-04).

Mirrors the 0037 migration column-for-column. Class composition is
``Base + UUIDPkMixin`` ONLY — no TimestampMixin, no SoftDeleteMixin — because
the FSM tracks lifecycle via explicit ``requested_at`` / ``succeeded_at`` /
``canceled_at`` columns (single-temporal-column discipline mirroring
online_payments/models.py:46-49).

Constraint naming discipline (NAMING_CONVENTION):
- CheckConstraints use BARE suffixes (``"amount_kopecks_positive"``) so
  ``ck_%(table_name)s_%(constraint_name)s`` expands to the same literal
  Alembic 0037 wrote via ``op.f("ck_online_refunds_*")``. (online_payments
  PATTERN — full names would double-prefix.)
- UniqueConstraint + Index pass full literal names (no convention-expansion
  for those families when explicit).
- Partial UNIQUE predicate uses ``text("status IN ('pending','succeeded')")``
  — backs REFUND-03 at the schema layer per D-51-04.
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


class OnlineRefund(Base, UUIDPkMixin):
    """ЮKassa-side online refund ledger row (Phase 51 REFUND-01 / D-51-04)."""

    __tablename__ = "online_refunds"

    online_payment_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "online_payments.id",
            ondelete="RESTRICT",
            name="fk_online_refunds_online_payment_id_online_payments",
        ),
        nullable=False,
    )
    original_payment_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "payments.id",
            ondelete="RESTRICT",
            name="fk_online_refunds_original_payment_id_payments",
        ),
        nullable=False,
    )
    client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "clients.id",
            ondelete="RESTRICT",
            name="fk_online_refunds_client_id_clients",
        ),
        nullable=False,
    )
    yookassa_refund_id: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    amount_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by_user_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
            name="fk_online_refunds_requested_by_user_id_users",
        ),
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    audit_correlation_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    succeeded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "amount_kopecks > 0",
            # NAMING_CONVENTION expands to ck_online_refunds_amount_kopecks_positive
            name="amount_kopecks_positive",
        ),
        CheckConstraint(
            "status IN ('pending','succeeded','canceled')",
            # NAMING_CONVENTION expands to ck_online_refunds_status
            name="status",
        ),
        UniqueConstraint(
            "yookassa_refund_id",
            name="uq_online_refunds_yookassa_refund_id",
        ),
        UniqueConstraint(
            "idempotency_key",
            name="uq_online_refunds_idempotency_key",
        ),
        Index(
            "uq_online_refunds_alive_per_online_payment",
            "online_payment_id",
            unique=True,
            postgresql_where=text("status IN ('pending','succeeded')"),
        ),
    )
