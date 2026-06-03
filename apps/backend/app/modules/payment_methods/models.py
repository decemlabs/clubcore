"""ClientPaymentMethod ORM model (Phase 79 PAYM-01..04).

Single active card per client: partial UNIQUE uq_client_payment_methods_client_id_alive:
  client_id WHERE unlinked_at IS NULL.
Token yookassa_method_id stored plaintext. NEVER serialized to the client.
Composition: Base + UUIDPkMixin + TimestampMixin (no SoftDeleteMixin — lifecycle
tracked via explicit unlinked_at column, mirrors online_payments/models.py single-
temporal-column discipline).

NAMING_CONVENTION note: CheckConstraint name= takes a BARE suffix.
ck_%(table_name)s_%(constraint_name)s template applies the prefix automatically.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPkMixin


class ClientPaymentMethod(Base, UUIDPkMixin, TimestampMixin):
    """Payment method (saved card) for a client (Phase 79 PAYM-01..04)."""

    __tablename__ = "client_payment_methods"

    client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "clients.id",
            ondelete="RESTRICT",
            name="fk_client_payment_methods_client_id_clients",
        ),
        nullable=False,
    )
    # plaintext token; NEVER serialized to the client (T-79-01)
    yookassa_method_id: Mapped[str] = mapped_column(Text, nullable=False)
    last4: Mapped[str] = mapped_column(Text, nullable=False)
    brand: Mapped[str] = mapped_column(Text, nullable=False)
    expiry_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expiry_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    autopay_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    consent_recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    unlinked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # Partial UNIQUE: single active card per client (literal name, no convention expansion).
        Index(
            "uq_client_payment_methods_client_id_alive",
            "client_id",
            unique=True,
            postgresql_where=text("unlinked_at IS NULL"),
        ),
    )
