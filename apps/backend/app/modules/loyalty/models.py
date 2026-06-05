"""LoyaltyLedger ORM model (Phase 82 LOYL-03 / ACCR-01 / ACCR-02).

Append-only ledger. Composition: Base + UUIDPkMixin ONLY — no TimestampMixin,
no SoftDeleteMixin. Single temporal column `created_at` (single-temporal-column
discipline mirrors PromoRedemption / online_refunds / online_payments).

DB-level invariants:
- entry_type IN ('welcome', 'owner_grant', 'redemption')
  (CHECK ck_loyalty_ledger_entry_type). 'redemption' is reserved for Phase 83.
- Partial UNIQUE uq_loyalty_ledger_welcome: (client_id) WHERE entry_type='welcome'
  — one welcome row per client; idempotency enforced at schema level (ACCR-01).
- client_id RESTRICT FK → clients.id (promo_redemptions pattern).
- Index ix_loyalty_ledger_client_id for balance/history fold performance.

NAMING_CONVENTION note: CheckConstraint name= takes a BARE suffix (not the
full ck_table_name_suffix). The ck_%(table_name)s_%(constraint_name)s template
applies the prefix automatically (mirror promo_codes/models.py:22-26 discipline).
Partial UNIQUE index declared in migration (not as ORM Index) — literal name
per uq_promo_codes_code_alive precedent.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base, UUIDPkMixin


class LoyaltyLedger(Base, UUIDPkMixin):
    """Loyalty bonus ledger row (Phase 82 LOYL-03).

    Append-only. Composition: Base + UUIDPkMixin ONLY — no TimestampMixin,
    no SoftDeleteMixin. Lifecycle tracked via created_at column
    (single-temporal-column discipline mirrors PromoRedemption).

    amount_kopecks is SIGNED: positive = accrual (welcome / owner_grant),
    negative = redemption (Phase 83). Balance is derived as SUM(amount_kopecks)
    fold (LOYL-03) — never a stored mutable column.

    entry_type values:
      - 'welcome'    — automatic one-time welcome bonus (ACCR-01)
      - 'owner_grant' — owner-only manual grant (ACCR-02)
      - 'redemption' — debit row reserved for Phase 83 (REDM-01)
    """

    __tablename__ = "loyalty_ledger"

    client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "clients.id",
            ondelete="RESTRICT",
            name="fk_loyalty_ledger_client_id_clients",
        ),
        nullable=False,
    )
    entry_type: Mapped[str] = mapped_column(String(16), nullable=False)
    amount_kopecks: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        # SIGNED: positive = accrual, negative = redemption (Phase 83)
    )
    category: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        # owner_grant rows only: 'promo' | 'referral' | 'manual' (ACCR-02)
    )
    reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        # owner_grant rows only: free-text reason for audit trail (ACCR-02)
    )
    # Phase 83 REDM-02: nullable FK → online_payments.id (RESTRICT).
    # Idempotency anchor for the webhook-locked redemption write.
    # NULL for welcome/owner_grant rows; set for redemption rows only.
    # Partial UNIQUE index uq_loyalty_ledger_online_payment_id is declared
    # in migration 0055 (not as an ORM Index) — same pattern as
    # uq_loyalty_ledger_welcome (0054) and uq_promo_codes_code_alive.
    online_payment_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "online_payments.id",
            ondelete="RESTRICT",
            name="fk_loyalty_ledger_online_payment_id_online_payments",
        ),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "entry_type IN ('welcome', 'owner_grant', 'redemption')",
            # NAMING_CONVENTION expands to ck_loyalty_ledger_entry_type
            # 'redemption' is reserved for Phase 83 row-writer (REDM-01).
            name="entry_type",
        ),
    )
    # Partial UNIQUE index uq_loyalty_ledger_welcome, partial UNIQUE index
    # uq_loyalty_ledger_online_payment_id (Phase 83 / migration 0055), and
    # plain index ix_loyalty_ledger_client_id are declared in migrations
    # (not as ORM Indexes) — mirrors PromoCode's uq_promo_codes_code_alive
    # partial-index pattern.
