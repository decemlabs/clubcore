"""EmailSendLog ORM — transport-layer audit row per send attempt (D-42-18 / D-42-33).

The dispatcher (Phase 42 Plan 42-04+) is the SOLE writer of new rows; the bounce
webhook (Phase 42 Plan 42-10) is the SOLE updater of ``status`` / ``bounce_type``
on existing rows by ``provider_message_id`` lookup. Business modules (auth,
memberships, bookings, payments) NEVER read this table directly — they consume
the typed ``EmailSendResult`` returned from the dispatcher and emit their own
audit-log row carrying the same ``audit_correlation_id`` for forensic continuity.

Eager-imported by ``app/workers/__init__.py`` per REG-29-04 / D-41-29 / D-42-33
so ``Base.metadata.tables`` is populated before any cron one-shot script runs
that might enqueue an email send.

NO ``TimestampMixin`` (D-42-18) — the table has a single ``recorded_at TIMESTAMPTZ
DEFAULT now()`` column, not the standard ``created_at`` / ``updated_at`` pair.
The row is INSERT-on-send + UPDATE-on-webhook-event; a v1 audit log of email
attempts does not need to distinguish "first seen" from "last updated" because
each bounce/complaint event additionally INSERTs an audit-log row by-design.

NO ForeignKey on ``to_address → users.email`` (D-42-18) — email recipients in
v1.6 include unlinked clients (Telegram-only sign-up, no email yet) and
operational recipients (owner alerts) that may not be User rows.

NO partial-UNIQUE on ``provider_message_id`` (D-42-18) — multiple bounce events
for one provider message ID are legitimate (a soft bounce followed by a
complaint), and the webhook is idempotent by event-id, not by message-id.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UUIDPkMixin


class EmailSendLog(Base, UUIDPkMixin):
    """Row-per-email-send-attempt log (D-42-18).

    Columns track the dispatch → provider-ack → eventual-bounce lifecycle:

    - ``audit_correlation_id``: chains to the business audit row that triggered
      this send (e.g. ``email_send_requested.audit_correlation_id``). Indexed
      for "show me everything for this correlation UUID" forensic queries.
    - ``to_address`` / ``template_id`` / ``provider``: forensic projection of
      the envelope. ``provider`` literal is the adapter name (``yandex_postbox``
      / ``unisender_go`` / ``ses`` depending on Phase 42 provider pick).
    - ``provider_message_id``: nullable because transient transport failures
      (network, 5xx) never produced a provider-side ID. The webhook joins by
      this column when present.
    - ``status``: closed taxonomy gated at the DB layer by a CHECK constraint;
      mirrors ``EmailSendResult.classification`` taxonomy extended with bounce-
      webhook event types (``delivered`` / ``bounced`` / ``complained`` /
      ``rejected``) which only the webhook can flip a row to.
    - ``bounce_type``: nullable provider-specific bounce reason (``hard`` /
      ``soft`` / ``complaint``) — typed prose only, not part of the CHECK.
    - ``recorded_at``: server-default ``now()``; single-column timestamp.
    """

    __tablename__ = "email_send_log"

    audit_correlation_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        nullable=False,
    )
    to_address: Mapped[str] = mapped_column(Text, nullable=False)
    template_id: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    bounce_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (
        # CHECK name passed bare (``"status"``) — the project naming_convention
        # in ``core/database.py`` expands to ``ck_email_send_log_status``,
        # matching the migration's ``op.f("ck_email_send_log_status")``.
        # Mirrors PasswordResetToken's ``name="purpose"`` pattern
        # (``password_reset_token_model.py:88``).
        CheckConstraint(
            "status IN ('sent','bounced','complained','delivered','rejected')",
            name="status",
        ),
        # Forensic lookup: "what did we send for this audit correlation UUID?"
        Index(
            "ix_email_send_log_audit_corr",
            "audit_correlation_id",
            unique=False,
        ),
        # Operator query: "did we send to X in the last N days?" DESC on the
        # second column is expressed in the migration DDL only — SQLAlchemy
        # Index does not surface DESC on the second column at the ORM layer.
        # This shape difference is intentional and does not trip alembic check
        # because Alembic compares only the column list at the model layer.
        Index(
            "ix_email_send_log_to_addr_recorded",
            "to_address",
            "recorded_at",
            unique=False,
        ),
    )
