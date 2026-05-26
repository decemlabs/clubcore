"""FiscalReceipt ORM model (Phase 50 FISCAL-01 / D-50-29).

Mirrors the 0035_fiscal_receipts migration column-for-column. Class
composition is ``Base + UUIDPkMixin`` ONLY — no TimestampMixin, no
SoftDeleteMixin — because the FSM tracks lifecycle via explicit
``sent_at`` / ``succeeded_at`` / ``failed_at`` columns (single-temporal-column
discipline mirrors payments/models.py:46-49 and online_payments/models.py:5-7).

Constraint naming discipline (NAMING_CONVENTION):
- CheckConstraints use BARE suffixes (``"kind"``, ``"status"``)
  so ``ck_%(table_name)s_%(constraint_name)s`` expands to the same
  literal Alembic 0035 wrote via ``op.f("ck_fiscal_receipts_*")``.
  Specifying ``name="ck_fiscal_receipts_kind"`` would double-prefix
  to ``ck_fiscal_receipts_ck_fiscal_receipts_kind`` — the exact bug
  fixed by Plan 49-01 deviation #2 (see online_payments/models.py:9-15).
- ForeignKey + UniqueConstraint pass full literal names (no
  convention-expansion for those families when explicit).

T-50-01-01 mitigation: ``payment_id`` FK targets ``payments.id`` (NOT
``online_payments.id``) because the fiscal obligation attaches to the
committed ledger row, per FEATURES.md SUMMARY line 104. ON DELETE RESTRICT
prevents orphaning a fiscal receipt by deleting its parent Payment.

T-50-01-02 mitigation: ``audit_correlation_id`` nullable UUID threads back
to the Phase 50 webhook intake audit chain for forensic lineage.

FISCAL-02 cross-channel-discriminator: UNIQUE(payment_id, kind) allows at
most one 'payment' + one 'refund' receipt per Payment ledger row.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UUIDPkMixin


class FiscalReceipt(Base, UUIDPkMixin):
    """54-ФЗ fiscal receipt lifecycle row (Phase 50 FISCAL-01 / D-50-29)."""

    __tablename__ = "fiscal_receipts"

    payment_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "payments.id",
            ondelete="RESTRICT",
            name="fk_fiscal_receipts_payment_id_payments",
        ),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    yookassa_receipt_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_email: Mapped[str] = mapped_column(Text, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    succeeded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    audit_correlation_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True
    )
    # Plan 51-09 / D-51-16 — monitor cron age anchor (migration 0038).
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "kind IN ('payment', 'refund')",
            # NAMING_CONVENTION expands to ck_fiscal_receipts_kind
            name="kind",
        ),
        CheckConstraint(
            "status IN ('pending', 'sent', 'succeeded', 'failed')",
            # NAMING_CONVENTION expands to ck_fiscal_receipts_status
            name="status",
        ),
        UniqueConstraint(
            "payment_id",
            "kind",
            name="uq_fiscal_receipts_payment_id_kind",
        ),
    )
