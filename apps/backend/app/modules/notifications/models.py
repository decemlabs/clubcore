"""Notification module ORM models (Phase 87 INBOX-01/INBOX-02).

InAppNotification: in-app inbox rows for client-visible system events.
ClientPushToken: push-notification device/browser token registration.

NAMING_CONVENTION: CheckConstraint name= takes a BARE suffix; the
ck_%(table_name)s_%(constraint_name)s template applies the prefix automatically.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPkMixin

# Valid notification kind values (T-87-03 — dedup key covers all 7).
_VALID_KINDS = (
    "booking_confirmed",
    "booking_cancelled_by_client",
    "booking_cancelled_by_owner",
    "booking_rescheduled",
    "payment_succeeded",
    "autopay_charge_succeeded",
    "autopay_charge_failed",
)

_KIND_CHECK = (
    "kind IN ("
    + ", ".join(f"'{k}'" for k in _VALID_KINDS)
    + ")"
)


class InAppNotification(Base, UUIDPkMixin, TimestampMixin):
    """Per-client in-app inbox row for a system event (Phase 87 INBOX-01/INBOX-03).

    UNIQUE(client_id, source_type, source_id, kind) is the idempotent dedup guard:
    a replay/retry of the same event raises IntegrityError, which create_notification
    catches, rolls back the nested savepoint, and silently returns (T-87-03 mitigate).

    read_at NULL = unread; read_at = timestamp = read.
    title/body are server-side rendered — no client-supplied content stored here (T-87-02).
    """

    __tablename__ = "in_app_notifications"

    client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "clients.id",
            ondelete="RESTRICT",
            name="fk_in_app_notifications_client_id_clients",
        ),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[UUIDType] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # NAMING_CONVENTION expands to ck_in_app_notifications_kind
        CheckConstraint(_KIND_CHECK, name="kind"),
        UniqueConstraint(
            "client_id",
            "source_type",
            "source_id",
            "kind",
            name="uq_in_app_notifications_client_source_kind",
        ),
        Index("ix_in_app_notifications_client_id", "client_id"),
    )


class ClientPushToken(Base, UUIDPkMixin, TimestampMixin):
    """Device/browser push-token registration for a client (Phase 87 INBOX-02).

    unregistered_at mirrors the soft-delete pattern of ClientPaymentMethod.unlinked_at.
    Partial UNIQUE on (client_id, token) WHERE unregistered_at IS NULL enforces one
    live token per (client, token) pair — reviving an unregistered token resets
    unregistered_at to NULL (idempotent upsert, T-87-04 mitigate).
    platform CheckConstraint restricts to web/android/ios (T-87-04 mitigate).
    """

    __tablename__ = "client_push_tokens"

    client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "clients.id",
            ondelete="RESTRICT",
            name="fk_client_push_tokens_client_id_clients",
        ),
        nullable=False,
    )
    token: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    unregistered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # NAMING_CONVENTION expands to ck_client_push_tokens_platform
        CheckConstraint("platform IN ('web', 'android', 'ios')", name="platform"),
        # Partial UNIQUE — must use Index (partial indexes are not expressible as
        # sa.UniqueConstraint inside __table_args__; mirrors migration 0052 pattern).
        Index(
            "uq_client_push_tokens_client_token_alive",
            "client_id",
            "token",
            unique=True,
            postgresql_where=text("unregistered_at IS NULL"),
        ),
        Index("ix_client_push_tokens_client_id", "client_id"),
    )
