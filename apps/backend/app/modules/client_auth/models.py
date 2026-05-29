"""ClientRefreshToken ORM model (Phase 68 D-09).

Fully parallel to auth.RefreshToken — FK target is clients.id, not users.id.
Redis namespace: auth:client:session:{client_id}:{family_id} (D-09).

Staff and client refresh storage never intersect — strongest CISO-05
isolation guarantee (separate table, separate Redis namespace, separate
cookies cc_client_*).
"""

from datetime import datetime
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPkMixin


class ClientRefreshToken(Base, UUIDPkMixin, TimestampMixin):
    """Client refresh token row (D-09).

    Fully parallel to auth.RefreshToken — FK target is clients, not users.
    Redis namespace: auth:client:session:{client_id}:{family_id}.

    `replaced_by_id` is a self-FK with ON DELETE SET NULL so the rotation
    chain survives ancestor deletion. `family_id` carries across one rotation
    chain; reuse outside the ~5s window revokes the entire family (mirroring
    the staff rotate_refresh 3-branch logic).
    """

    __tablename__ = "client_refresh_tokens"

    client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
    )
    family_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    replaced_by_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("client_refresh_tokens.id", ondelete="SET NULL"),
        nullable=True,
    )
    replaced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_client_refresh_tokens_client_id_family_id", "client_id", "family_id"),
    )
