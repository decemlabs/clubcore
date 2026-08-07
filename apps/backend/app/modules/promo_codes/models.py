"""PromoCode + PromoRedemption ORM models (Phase 999.4 D-04/D-07/D-08).

PromoCode composition: Base + UUIDPkMixin + TimestampMixin + SoftDeleteMixin.
PromoRedemption composition: Base + UUIDPkMixin ONLY — append-only ledger,
lifecycle tracked via redeemed_at column (single-temporal-column discipline
mirrors online_refunds/models.py and online_payments/models.py).

DB-level invariants (PromoCode):
- discount_type IN ('percentage', 'fixed') (CHECK ck_promo_codes_discount_type)
- discount_value > 0 (CHECK ck_promo_codes_discount_value_positive)
- Partial UNIQUE uq_promo_codes_code_alive: upper(code) WHERE deleted_at IS NULL
  (codes normalized to UPPER on write; partial index backs UPPER-case uniqueness).

DB-level invariants (PromoRedemption):
- discount_kopecks > 0 (CHECK ck_promo_redemptions_discount_kopecks_positive)
- UNIQUE(online_payment_id) (uq_promo_redemptions_online_payment_id) — one
  redemption per payment enforces D-07 at the schema layer.
- Three RESTRICT FKs: promo_code_id → promo_codes.id,
  client_id → clients.id,
  online_payment_id → online_payments.id.

NAMING_CONVENTION note: CheckConstraint name= takes a BARE suffix (not the
full ck_table_name_suffix). The ck_%(table_name)s_%(constraint_name)s template
applies the prefix automatically. See memberships/models.py:67-84 for the
established pattern.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base, SoftDeleteMixin, TimestampMixin, UUIDPkMixin


class PromoCode(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin):
    """Promo code definition row (Phase 999.4 D-04/D-07/D-08)."""

    __tablename__ = "promo_codes"

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    discount_type: Mapped[str] = mapped_column(String(16), nullable=False)  # 'percentage' | 'fixed'
    discount_value: Mapped[int] = mapped_column(
        BigInteger, nullable=False
    )  # kopecks or percent*100
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = unlimited
    per_client_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = unlimited
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    applicable_to: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )  # 'membership' | 'pt_package' | None = both (D-05)
    description: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )  # Phase 113 — optional owner-editable description

    __table_args__ = (
        CheckConstraint(
            "discount_type IN ('percentage', 'fixed')",
            # NAMING_CONVENTION expands to ck_promo_codes_discount_type
            name="discount_type",
        ),
        CheckConstraint(
            "discount_value > 0",
            # NAMING_CONVENTION expands to ck_promo_codes_discount_value_positive
            name="discount_value_positive",
        ),
        # Partial UNIQUE: codes are case-normalized to UPPER on write (D-04).
        # Literal index name (no convention expansion for Index objects).
        Index(
            "uq_promo_codes_code_alive",
            text("upper(code)"),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )


class PromoRedemption(Base, UUIDPkMixin):
    """Promo code redemption ledger row (Phase 999.4 D-07).

    Append-only. Recorded on successful payment (succeeded webhook).
    Composition: Base + UUIDPkMixin ONLY — no TimestampMixin, no SoftDeleteMixin.
    Lifecycle tracked via redeemed_at column (single-temporal-column discipline
    mirrors online_refunds/models.py:8-10 and online_payments/models.py:5-7).

    No relationship() to clients/online_payments per task spec.
    """

    __tablename__ = "promo_redemptions"

    promo_code_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "promo_codes.id",
            ondelete="RESTRICT",
            name="fk_promo_redemptions_promo_code_id_promo_codes",
        ),
        nullable=False,
    )
    client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "clients.id",
            ondelete="RESTRICT",
            name="fk_promo_redemptions_client_id_clients",
        ),
        nullable=False,
    )
    online_payment_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "online_payments.id",
            ondelete="RESTRICT",
            name="fk_promo_redemptions_online_payment_id_online_payments",
        ),
        nullable=False,
    )
    discount_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    redeemed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "discount_kopecks > 0",
            # NAMING_CONVENTION expands to ck_promo_redemptions_discount_kopecks_positive
            name="discount_kopecks_positive",
        ),
        UniqueConstraint(
            "online_payment_id",
            # one redemption per payment (D-07)
            name="uq_promo_redemptions_online_payment_id",
        ),
    )
