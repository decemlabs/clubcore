"""AutopayCharge + AutopayChargeNotification ORM models (Phase 84 APAY-03/APAY-04).

AutopayCharge — idempotency ledger for off-session recurring charges.
  UNIQUE(membership_id, period_end) is the DB-level double-charge guard (T-84-01).
  status: 'pending' → 'succeeded' (via webhook) | 'failed' (sync decline).
  online_payment_id: nullable — links the off-session online_payments row created
    by the cron (Plan 02 UPDATEs it on the ok path). NO FK to keep modules-independent.

AutopayChargeNotification — per-channel notification claim store (T-84-04b).
  Dedicated separate table (NOT reusing payment_notifications) because the FAILURE
  notification fires on a DECLINE — no online_payments row exists — so its idempotency
  must key on the always-present autopay_charges.id (D-52-02 discipline).

NAMING_CONVENTION note: CheckConstraint name= takes a BARE suffix.
ck_%(table_name)s_%(constraint_name)s template applies the prefix automatically.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPkMixin


class AutopayCharge(Base, UUIDPkMixin, TimestampMixin):
    """Autopay charge claim / idempotency ledger (Phase 84 APAY-03).

    UNIQUE(membership_id, period_end) is the DB-level double-charge guard.
    status: 'pending' → 'succeeded' (via webhook) | 'failed' (sync decline).
    yookassa_payment_id: populated after successful POST /v3/payments.
    online_payment_id: nullable link to the online_payments row created by the cron
      (Plan 02 UPDATEs it). NO FK — cross-module boundary (D-54-08 discipline).
    """

    __tablename__ = "autopay_charges"

    membership_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "memberships.id",
            ondelete="RESTRICT",
            name="fk_autopay_charges_membership_id_memberships",
        ),
        nullable=False,
    )
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'pending'")
    )
    amount_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
    yookassa_payment_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Links the off-session online_payments row (Plan 02 writes this column on ok path).
    # NO FK to keep modules-independent (D-54-08 — cross-module column, raw SQL reads).
    online_payment_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    charged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed')",
            # NAMING_CONVENTION expands to ck_autopay_charges_status
            name="status",
        ),
        UniqueConstraint(
            "membership_id",
            "period_end",
            name="uq_autopay_charges_membership_period",
        ),
    )


class AutopayChargeNotification(Base, UUIDPkMixin, TimestampMixin):
    """Per-channel claim store for autopay failure notifications (Phase 84 APAY-04 / T-84-04b).

    Dedicated separate table (NOT reusing payment_notifications) because the DECLINE
    path has NO online_payments row — its idempotency must key on autopay_charges.id.

    UNIQUE(autopay_charge_id, kind, channel) is the dedup guard: a second INSERT for
    the same (charge, kind, channel) triple raises IntegrityError (claim-before-send,
    D-52-02 discipline).
    """

    __tablename__ = "autopay_charge_notifications"

    autopay_charge_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "autopay_charges.id",
            ondelete="RESTRICT",
            name="fk_autopay_charge_notifications_autopay_charge_id_autopay_charges",
        ),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "channel IN ('telegram', 'email')",
            # NAMING_CONVENTION expands to ck_autopay_charge_notifications_channel
            name="channel",
        ),
        CheckConstraint(
            "kind IN ('autopay_charge_failed')",
            # NAMING_CONVENTION expands to ck_autopay_charge_notifications_kind
            name="kind",
        ),
        UniqueConstraint(
            "autopay_charge_id",
            "kind",
            "channel",
            name="uq_autopay_charge_notifications_charge_kind_channel",
        ),
    )
