"""OnlinePayment + PaymentNotification ORM models (Phase 49 PAY-01 / Phase 52 NOT-03).

OnlinePayment mirrors the 0034 migration column-for-column. Class composition is
``Base + UUIDPkMixin`` ONLY — no TimestampMixin, no SoftDeleteMixin —
because the FSM tracks lifecycle via explicit ``initiated_at`` /
``succeeded_at`` / ``canceled_at`` columns (single-temporal-column
discipline per payments/models.py:46-49).

PaymentNotification (Phase 52 NOT-03 / D-52-04) is the cross-restart dedup
arbiter for cross-channel client notifications and owner operator alerts.
Composition: Base + UUIDPkMixin + TimestampMixin (NO SoftDeleteMixin — rows
are append-only; the partial-unique indexes per subject FK are the single
source of truth for cross-restart idempotency per D-52-04).

Constraint naming discipline (NAMING_CONVENTION):
- CheckConstraints use BARE suffixes (``"amount_kopecks_positive"``)
  so ``ck_%(table_name)s_%(constraint_name)s`` expands to the same
  literal Alembic 0034 wrote via ``op.f("ck_online_payments_*")``.
  Plan 49-02 originally specified full names — that would have
  double-prefixed to ``ck_online_payments_ck_online_payments_*``,
  the exact bug fixed by Plan 49-01 deviation #2.
- ForeignKey + Index pass full literal names (no convention-expansion
  for those families when explicit).
- Partial UNIQUE per-day expression uses
  ``((initiated_at AT TIME ZONE 'Europe/Moscow')::date)`` — IMMUTABLE
  per Postgres rules; ``DATE(timestamptz)`` is rejected on the
  partial-index predicate. Matches migration 0034 verbatim
  (Plan 49-01 deviation #1).
- PaymentNotification partial-unique indexes use full literal names
  (mirrors the ``uq_online_payments_*_double_tap`` Index blocks at
  lines 138-157 — NOT UniqueConstraint, because partial index predicates
  require ``Index(postgresql_where=...)``).
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
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPkMixin


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
    promo_code_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "promo_codes.id",
            ondelete="RESTRICT",
            name="fk_online_payments_promo_code_id_promo_codes",
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
    succeeded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
            name="fk_online_payments_created_by_user_id_users",
        ),
        nullable=True,
    )
    audit_correlation_id: Mapped[UUIDType] = mapped_column(PgUUID(as_uuid=True), nullable=False)

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
            postgresql_where=text("status != 'canceled' AND membership_plan_id IS NOT NULL"),
        ),
        Index(
            "uq_online_payments_pt_package_double_tap",
            "client_id",
            "pt_package_plan_id",
            text("((initiated_at AT TIME ZONE 'Europe/Moscow')::date)"),
            unique=True,
            postgresql_where=text("status != 'canceled' AND pt_package_plan_id IS NOT NULL"),
        ),
    )


class PaymentNotification(Base, UUIDPkMixin, TimestampMixin):
    """Idempotency record for cross-channel payment notifications (Phase 52 NOT-03).

    Composition: Base + UUIDPkMixin + TimestampMixin (NO SoftDeleteMixin —
    rows are append-only; the partial-unique indexes per subject FK are the
    single source of truth for cross-restart idempotency per D-52-04).

    Polymorphic subject (D-52-10 — Option A, DB-UNIQUE across all kinds):
    ``payment_id`` is used for payment_succeeded / refund_succeeded / fiscal_failed
    (the ledger row exists for these kinds).
    ``online_payment_id`` is used for payment_canceled (no payments ledger row —
    activation is webhook-gated; canceled payments never write a ledger row).
    Exactly one must be non-null; the XOR CHECK enforces this.

    DB-level invariants:
    - XOR CHECK (payment_id IS NOT NULL) <> (online_payment_id IS NOT NULL)
      → ck_payment_notifications_subject_xor
    - FK fk_payment_notifications_payment_id_payments ON DELETE RESTRICT
    - FK fk_payment_notifications_online_payment_id_online_payments ON DELETE RESTRICT
    - kind CHECK IN ('payment_succeeded', 'refund_succeeded', 'payment_canceled',
      'fiscal_failed') → ck_payment_notifications_kind
    - channel CHECK IN ('telegram', 'email') → ck_payment_notifications_channel
    - PARTIAL UNIQUE (payment_id, kind, channel) WHERE payment_id IS NOT NULL
      → uq_payment_notifications_payment_kind_channel
    - PARTIAL UNIQUE (online_payment_id, kind, channel) WHERE online_payment_id IS NOT NULL
      → uq_payment_notifications_online_payment_kind_channel
    """

    __tablename__ = "payment_notifications"

    # Polymorphic subject FKs — exactly one must be non-null (XOR CHECK in __table_args__).
    payment_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "payments.id",
            ondelete="RESTRICT",
            name="fk_payment_notifications_payment_id_payments",
        ),
        nullable=True,
    )
    online_payment_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "online_payments.id",
            ondelete="RESTRICT",
            name="fk_payment_notifications_online_payment_id_online_payments",
        ),
        nullable=True,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "kind IN ('payment_succeeded', 'refund_succeeded', "
            "'payment_canceled', 'fiscal_failed')",
            # NAMING_CONVENTION expands to ck_payment_notifications_kind
            name="kind",
        ),
        CheckConstraint(
            "channel IN ('telegram', 'email')",
            # NAMING_CONVENTION expands to ck_payment_notifications_channel
            name="channel",
        ),
        CheckConstraint(
            "(payment_id IS NOT NULL) <> (online_payment_id IS NOT NULL)",
            # NAMING_CONVENTION expands to ck_payment_notifications_subject_xor
            # Mirrors the D-49-04 exactly_one_subject_fk pattern on OnlinePayment.
            name="subject_xor",
        ),
        # Two partial UNIQUE indexes — one per subject FK — because a single
        # all-columns UNIQUE cannot span a NULL column in Postgres.
        # Full literal names (not NAMING_CONVENTION expansion) to match Alembic 0039.
        Index(
            "uq_payment_notifications_payment_kind_channel",
            "payment_id",
            "kind",
            "channel",
            unique=True,
            postgresql_where=text("payment_id IS NOT NULL"),
        ),
        Index(
            "uq_payment_notifications_online_payment_kind_channel",
            "online_payment_id",
            "kind",
            "channel",
            unique=True,
            postgresql_where=text("online_payment_id IS NOT NULL"),
        ),
        # Lookup indexes for FK columns.
        Index("ix_payment_notifications_payment_id", "payment_id"),
        Index("ix_payment_notifications_online_payment_id", "online_payment_id"),
    )
