"""Payment ORM model (Phase 32 PAY-01 / B-01 INFRA-22).

Append-only payment ledger row (B-01 INFRA-22). NO TimestampMixin (no
created_at/updated_at), NO SoftDeleteMixin (no deleted_at) — received_at is
the SINGLE temporal column per D-32-01..D-32-04. UPDATE/DELETE are banned by
the AST gate `tests/unit/test_payments_appendonly.py`.

DB-level invariants (mirror migration 0012_payments):
- CHECK ck_payments_amount_sign_matches_subject_kind: amount_kopecks sign
  agrees with subject_kind ('refund' < 0; 'membership'/'pt_package' > 0).
- CHECK ck_payments_subject_kind: subject_kind ∈ ('membership','pt_package','refund').
- FK fk_payments_received_by_user_id_users ON DELETE RESTRICT.
- FK fk_payments_refund_of_payments ON DELETE RESTRICT (self-ref for refund rows).
- FK fk_payments_audit_log_id_audit_log ON DELETE SET NULL.
- Partial UNIQUE uq_payments_refund_of_alive ON (refund_of) WHERE
  refund_of IS NOT NULL — at most one refund per sale.
- Composite index ix_payments_subject on (subject_kind, subject_id).
- ix_payments_received_by_user_id; ix_payments_received_at DESC.
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
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UUIDPkMixin


class Payment(Base, UUIDPkMixin):
    """Append-only payment ledger row (B-01 INFRA-22).

    NO TimestampMixin (no created_at/updated_at), NO SoftDeleteMixin (no deleted_at).
    `received_at` is the single temporal column (D-32-01..D-32-04).
    """

    __tablename__ = "payments"

    subject_kind: Mapped[str] = mapped_column(Text, nullable=False)
    subject_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        nullable=False,
    )
    amount_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)  # signed
    method: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'cash'"),
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    received_by_user_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
            name="fk_payments_received_by_user_id_users",
        ),
        nullable=False,
    )
    refund_of: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "payments.id",
            ondelete="RESTRICT",
            name="fk_payments_refund_of_payments",
        ),
        nullable=True,
    )
    audit_log_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "audit_log.id",
            ondelete="SET NULL",
            name="fk_payments_audit_log_id_audit_log",
        ),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "(subject_kind = 'refund' AND amount_kopecks < 0) "
            "OR (subject_kind IN ('membership','pt_package') AND amount_kopecks > 0)",
            # NAMING_CONVENTION expands to ck_payments_amount_sign_matches_subject_kind
            name="amount_sign_matches_subject_kind",
        ),
        CheckConstraint(
            "subject_kind IN ('membership','pt_package','refund')",
            # NAMING_CONVENTION expands to ck_payments_subject_kind
            name="subject_kind",
        ),
        Index(
            "uq_payments_refund_of_alive",
            "refund_of",
            unique=True,
            postgresql_where=text("refund_of IS NOT NULL"),
        ),
        Index("ix_payments_subject", "subject_kind", "subject_id"),
        Index("ix_payments_received_by_user_id", "received_by_user_id"),
        Index("ix_payments_received_at", text("received_at DESC")),
    )
