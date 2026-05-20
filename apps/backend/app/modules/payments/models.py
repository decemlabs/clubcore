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
from typing import Literal
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


class PaymentReceipt(Base, UUIDPkMixin):
    """Email/Telegram receipt idempotency ledger (Phase 45 NOTIFY-11 / D-45-11).

    Composition: Base + UUIDPkMixin (NO TimestampMixin — only `enqueued_at`
    is carried; matches `Payment`'s single-temporal-column discipline at
    D-32-01..D-32-04).

    DB-level invariants (mirror migration 0031_payment_receipts):
    - CHECK channel IN ('telegram','email') (ck_payment_receipts_channel).
    - UNIQUE (payment_id, channel) (uq_payment_receipts_payment_channel) —
      one attempt per (payment, channel) tuple. The orchestrator post-commit
      fanout (D-45-08) catches IntegrityError on this constraint to skip
      docker-restart race re-enqueues.
    - FK fk_payment_receipts_payment_id_payments ON DELETE RESTRICT — receipts
      MUST NOT orphan; deleting a payment with sent receipts requires an
      explicit cascade decision (T-45-01-03 accept disposition).
    - Index ix_payment_receipts_audit_corr — non-unique btree supporting the
      forensic join `payment_receipts ↔ email_send_log` keyed by
      audit_correlation_id (D-45-25).

    NO `status` / `provider_message_id` / `bounce_type` columns — the actual
    send-attempt outcome lives in `email_send_log` (Phase 42) keyed by the
    shared `audit_correlation_id`. This row is a pure idempotency ledger:
    one INSERT = one channel-targeted attempt enqueued.

    NO relationship() back to Payment — the join is by id only; no ORM-level
    navigation required in v1.6 (the read query in D-45-25 is raw SQL via
    repository helpers in later Phase 45 plans).
    """

    __tablename__ = "payment_receipts"

    payment_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "payments.id",
            ondelete="RESTRICT",
            name="fk_payment_receipts_payment_id_payments",
        ),
        nullable=False,
    )
    channel: Mapped[Literal["telegram", "email"]] = mapped_column(
        Text,
        nullable=False,
    )
    audit_correlation_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        nullable=False,
    )
    to_address: Mapped[str] = mapped_column(Text, nullable=False)
    enqueued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "channel IN ('telegram','email')",
            # NAMING_CONVENTION expands to ck_payment_receipts_channel
            # (matches migration 0031 op.f()-derived name).
            name="channel",
        ),
        UniqueConstraint(
            "payment_id",
            "channel",
            name="uq_payment_receipts_payment_channel",
        ),
        Index(
            "ix_payment_receipts_audit_corr",
            "audit_correlation_id",
        ),
    )
