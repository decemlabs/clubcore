"""email_send_log transport-layer audit table (EMAIL-01 / D-42-18 / D-42-33).

Revision ID: 0026_email_send_log
Revises: 0025_password_reset_tokens
Create Date: 2026-05-19 11:00:00.000000

Phase 42 Plan 42-01 — first Wave-1 migration of the email-transport milestone.
Ships the dispatcher's audit row table so Wave-2 (provider adapter + ARQ task)
and Wave-3 (webhook + module callsites) can land in parallel against a stable
schema.

DESIGN — single-table audit log (D-42-18)
-----------------------------------------
One row per dispatch attempt; the bounce-webhook (Phase 42 Plan 42-10) UPDATEs
the existing row's ``status`` / ``bounce_type`` by ``provider_message_id``
lookup. Business modules NEVER read this table — they consume the typed
``EmailSendResult`` returned by the dispatcher and emit their own
``audit_log`` row carrying the same ``audit_correlation_id``.

STATUS CHECK (D-42-13)
----------------------
The closed taxonomy gates two distinct lifecycle phases at one column:
  - INSERT-time values (``EmailSendResult.classification`` → row): ``sent``,
    ``rejected`` (permanent_error / blocked translated by the dispatcher).
  - UPDATE-time values (webhook event → row): ``delivered``, ``bounced``,
    ``complained``.
Transient errors do not produce a row — the dispatcher retries the send.

INDEXES
-------
- ``ix_email_send_log_audit_corr`` — forensic "show me everything for this
  correlation UUID" (single-column btree). Cardinality is high (one UUID per
  business event) so a plain btree is the right shape.
- ``ix_email_send_log_to_addr_recorded`` — operator query "did we send to X
  recently?" with DESC on ``recorded_at`` so PG can satisfy
  ``WHERE to_address = ? ORDER BY recorded_at DESC LIMIT N`` directly from the
  index. The ORM-side Index in ``models.py`` cannot surface DESC on the second
  column; this DDL is the source of truth for the index shape.

NO FK on ``to_address`` (D-42-18) — recipients in v1.6 include unlinked clients
(Telegram-only sign-up, no email yet) and operational recipients (owner alerts).

NO partial-UNIQUE on ``provider_message_id`` (D-42-18) — multiple bounce events
for one provider message ID are legitimate; the webhook is idempotent by
event-id, not by message-id.

DOWNGRADE
---------
Drops both indexes then the table. Lossless reverse — no other Phase 42
migration depends on this table existing (Wave-2 / Wave-3 plans add code, not
schema, against it).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0026_email_send_log"
down_revision: str | None = "0025_password_reset_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_send_log",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("audit_correlation_id", sa.UUID(), nullable=False),
        sa.Column("to_address", sa.Text(), nullable=False),
        sa.Column("template_id", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_message_id", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("bounce_type", sa.Text(), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('sent','bounced','complained','delivered','rejected')",
            name=op.f("ck_email_send_log_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_send_log")),
    )

    # Forensic correlation lookup (single-column btree).
    op.create_index(
        "ix_email_send_log_audit_corr",
        "email_send_log",
        ["audit_correlation_id"],
        unique=False,
    )

    # Operator query: "did we send to X recently?" — DESC on recorded_at so the
    # index satisfies ``WHERE to_address = ? ORDER BY recorded_at DESC LIMIT N``
    # directly. ORM Index can't surface DESC at the model layer (acceptable per
    # D-42-18 + models.py docstring).
    op.create_index(
        "ix_email_send_log_to_addr_recorded",
        "email_send_log",
        ["to_address", sa.text("recorded_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_email_send_log_to_addr_recorded",
        table_name="email_send_log",
    )
    op.drop_index(
        "ix_email_send_log_audit_corr",
        table_name="email_send_log",
    )
    op.drop_table("email_send_log")
