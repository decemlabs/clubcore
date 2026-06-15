"""Messaging module ORM models (Phase 90 MSG-01; Phase 92 ATT-01..03).

MessageThread: single 1:1 thread per client (UNIQUE client_id enforces this).
Message: individual message rows under a thread; role restricted to 'client'|'staff'.
MessageAttachment: photo attachment metadata (Phase 92); client_id is the IDOR
  ownership column (T-92-03 mitigate) consumed by the Plan 03 serve endpoint.

NAMING_CONVENTION: CheckConstraint name= takes a BARE suffix; the
ck_%(table_name)s_%(constraint_name)s template applies the prefix automatically.
UniqueConstraint and Index use bare names as written (no template applies).

Cross-module reads (e.g. clients.name for display) MUST use raw SQL text() in
the repository (D-54-08). ZERO foreign ORM imports from other modules.
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
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPkMixin


class MessageThread(Base, UUIDPkMixin, TimestampMixin):
    """Single lazily-created 1:1 thread between a client and the gym (Phase 90 MSG-01).

    UNIQUE(client_id) enforces the single-thread-per-client invariant and is the
    ON CONFLICT target for the get-or-create insert in the repository.

    client_unread_count is incremented on each new client message and reset to 0
    by PATCH /client/messages/read (MSG-02). last_message_at is updated on every
    new message for inbox sorting.
    """

    __tablename__ = "message_threads"

    client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "clients.id",
            ondelete="RESTRICT",
            name="fk_message_threads_client_id_clients",
        ),
        nullable=False,
    )
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    client_unread_count: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
        nullable=False,
    )
    # Phase 116 MSG-01: staff-side unread watermark — NULL = never read by staff.
    # Staff unread count is derived on read: COUNT(*) WHERE role='client'
    # AND sent_at > staff_last_read_at (or all client messages when NULL).
    staff_last_read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("client_id", name="uq_message_threads_client_id"),
    )


class MessageAttachment(Base, UUIDPkMixin, TimestampMixin):
    """Photo attachment metadata row (Phase 92 ATT-01..03, migration 0066).

    client_id NOT NULL is the IDOR ownership column (T-92-03 mitigate):
    the Plan 03 serve endpoint enforces ``attachment.client_id == principal.client_id``
    with a 404-collapse on non-owned objects (MSG-02 precedent).

    mime_type is the validated MIME type from the magic-byte guard (never user-supplied).
    object_key is a server-generated UUID4-based S3 object key (P8 — no user filename).
    size_bytes is the byte count validated at upload time (5 MB cap per ATT-02).
    """

    __tablename__ = "message_attachments"

    thread_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "message_threads.id",
            ondelete="RESTRICT",
            name="fk_message_attachments_thread_id_message_threads",
        ),
        nullable=False,
    )
    client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "clients.id",
            ondelete="RESTRICT",
            name="fk_message_attachments_client_id_clients",
        ),
        nullable=False,
    )
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)


class Message(Base, UUIDPkMixin, TimestampMixin):
    """Individual message row under a thread (Phase 90 MSG-01; Phase 92 ATT-01).

    role is constrained to 'client'|'staff' at the DB layer (T-90-01 mitigate).
    read_at NULL = unread; read_at = timestamp = read.
    sent_at has a DB server_default of now() and is set explicitly by the
    repository on insert for accurate tiebreak ordering.
    attachment_id is nullable FK to message_attachments.id (Phase 92 migration 0066).
    body OR attachment required is enforced at the service layer (Plan 02).
    """

    __tablename__ = "messages"

    thread_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "message_threads.id",
            ondelete="RESTRICT",
            name="fk_messages_thread_id_message_threads",
        ),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attachment_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "message_attachments.id",
            ondelete="RESTRICT",
            name="fk_messages_attachment_id_message_attachments",
        ),
        nullable=True,
    )

    __table_args__ = (
        # NAMING_CONVENTION expands to ck_messages_role
        CheckConstraint("role IN ('client','staff')", name="role"),
        Index("ix_messages_thread_sent", "thread_id", "sent_at"),
    )
