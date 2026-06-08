"""Referral domain ORM models (Phase 96 REFER-01 / REFER-03 / REFER-07).

Three append-only / singleton tables that form the referral data layer:

  referral_codes     — one stable row per client; code is UNIQUE (REFER-01).
  referral_captures  — one row per referee binding referrer↔referee (REFER-03);
                       UNIQUE on referee_client_id enforces one-referrer-per-referee
                       at schema level (T-96-03 mitigate).
  referral_config    — singleton owner-configurable bonus amounts (REFER-07).

Composition: Base + UUIDPkMixin ONLY — no TimestampMixin, no SoftDeleteMixin.
Single temporal column created_at on the two ledger-style tables
(single-temporal-column discipline mirrors loyalty_ledger / promo_redemptions).
referral_config is a bare singleton config table — no temporal column needed.

FK naming: all FKs use LITERAL names (NOT op.f()) in the migration per the
project pattern for explicitly-named FKs (mirrors loyalty_ledger / promo_redemptions).
ORM models carry the same literal names so the NAMING_CONVENTION dict does not
attempt to expand them.

UNIQUE indexes declared in migration 0067 (not as ORM Index):
  uq_referral_codes_code        — plain UNIQUE (op.f()) on referral_codes.code
  uq_referral_captures_referee_client_id — literal UNIQUE on referee_client_id
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    String,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base, UUIDPkMixin


class ReferralCode(Base, UUIDPkMixin):
    """One stable referral code per client (Phase 96 REFER-01).

    Append-only; codes are never deleted or recycled. Composition: Base + UUIDPkMixin
    ONLY — no TimestampMixin, no SoftDeleteMixin. Single temporal column created_at.

    Uniqueness on `code` is enforced by UNIQUE index uq_referral_codes_code
    declared in migration 0067 (not as an ORM Index per promo_codes precedent).

    client_id RESTRICT FK → clients.id prevents deletion of a client who has
    issued referral codes (defense in depth for REFER-01).
    """

    __tablename__ = "referral_codes"

    client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "clients.id",
            ondelete="RESTRICT",
            name="fk_referral_codes_client_id_clients",
        ),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    # Plain UNIQUE index uq_referral_codes_code declared in migration 0067 (op.f()).
    # Plain index ix_referral_codes_client_id also declared in migration 0067.


class ReferralCapture(Base, UUIDPkMixin):
    """Binding record: referee chose referrer (Phase 96 REFER-03).

    One row per captured referee — UNIQUE on referee_client_id (schema-level
    T-96-03 mitigate). Append-only; captures are never deleted.

    Three RESTRICT FKs:
      referee_client_id  → clients.id  (the new client who was referred)
      referrer_client_id → clients.id  (the existing client who invited)
      referral_code_id   → referral_codes.id  (the code that was used)

    UNIQUE index uq_referral_captures_referee_client_id declared in migration 0067
    with a LITERAL name (no op.f()) — unconditional (not partial), matching the
    96-PATTERNS discipline.
    """

    __tablename__ = "referral_captures"

    referee_client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "clients.id",
            ondelete="RESTRICT",
            name="fk_referral_captures_referee_client_id_clients",
        ),
        nullable=False,
    )
    referrer_client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "clients.id",
            ondelete="RESTRICT",
            name="fk_referral_captures_referrer_client_id_clients",
        ),
        nullable=False,
    )
    referral_code_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "referral_codes.id",
            ondelete="RESTRICT",
            name="fk_referral_captures_referral_code_id_referral_codes",
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    # UNIQUE index uq_referral_captures_referee_client_id declared in migration 0067
    # as a LITERAL name (no op.f()), unconditional (not partial).


class ReferralConfig(Base, UUIDPkMixin):
    """Owner-configurable singleton bonus amounts (Phase 96 REFER-07).

    Singleton row seeded by migration 0068 with deterministic PK
    "00000000-0000-0000-0000-000000000002". Owner updates via PATCH endpoint
    in Plan 96-03. No temporal column — this is a config table, not an
    event/ledger table. Composition: Base + UUIDPkMixin ONLY.

    referrer_bonus_kopecks  — bonus awarded to the client who shared the code.
    referee_welcome_kopecks — welcome bonus awarded to the new client.
    Both are BigInteger integer kopecks (same unit as loyalty_ledger.amount_kopecks).
    """

    __tablename__ = "referral_config"

    referrer_bonus_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    referee_welcome_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
