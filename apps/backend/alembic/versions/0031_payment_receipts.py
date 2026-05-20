"""payment_receipts ledger + telegram_chat_id nullability (NOTIFY-11 / D-45-11 / D-45-01).

Revision ID: 0031_payment_receipts
Revises: 0030_users_lifecycle_columns
Create Date: 2026-05-20 12:00:00.000000

Phase 45 Plan 01. Two coupled DDL operations land in a single migration:

1. CREATE TABLE payment_receipts (D-45-11) — pure idempotency ledger keyed
   by UNIQUE (payment_id, channel). Row is inserted at email-enqueue time
   in the orchestrator post-commit fanout block (D-45-08); the send-attempt
   outcome lives in `email_send_log` keyed by `audit_correlation_id`. No
   `status`/`provider_message_id`/`bounce_type` columns here.

2. ALTER COLUMN membership_notifications.telegram_chat_id DROP NOT NULL
   (D-45-01 + PATTERNS.md telegram_chat_id note) — when email-fallback fires
   on `SendResult.blocked`, the email-channel row has NO Telegram chat to
   record. `booking_notifications` does NOT carry a `telegram_chat_id`
   column at all (Phase 39 D-39-03 — explicit deviation from
   `membership_notifications`); no ALTER needed there.

NAMING CONVENTION
-----------------
All constraint names wrapped in op.f() so the project's NAMING_CONVENTION
(`ck_%(table_name)s_%(constraint_name)s`,
`fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s`,
`uq_%(table_name)s_%(column_0_name)s`,
`pk_%(table_name)s` — see app/core/database.py:28-34) does NOT re-prefix
and double the table name. Mirrors the 0024/0025/0030 pattern.

DOWNGRADE
---------
Reverses strictly: restore NOT NULL on telegram_chat_id, drop the audit
correlation lookup index, drop the table (implicit drop of CHECK / FK /
UNIQUE / PK).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0031_payment_receipts"
down_revision: str | None = "0030_users_lifecycle_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. payment_receipts — D-45-11 canonical schema.
    op.create_table(
        "payment_receipts",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("payment_id", sa.UUID(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("audit_correlation_id", sa.UUID(), nullable=False),
        sa.Column("to_address", sa.Text(), nullable=False),
        sa.Column(
            "enqueued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "channel IN ('telegram','email')",
            name=op.f("ck_payment_receipts_channel"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_receipts")),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name=op.f("fk_payment_receipts_payment_id_payments"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "payment_id",
            "channel",
            name=op.f("uq_payment_receipts_payment_channel"),
        ),
    )

    # 2. Forensic lookup index — supports the join-by-audit_correlation_id
    #    query in D-45-25 (payment_receipts ↔ email_send_log).
    op.create_index(
        "ix_payment_receipts_audit_corr",
        "payment_receipts",
        ["audit_correlation_id"],
        unique=False,
    )

    # 3. membership_notifications.telegram_chat_id → NULLABLE (D-45-01).
    #    Email-fallback rows (channel='email') carry NULL chat_id because
    #    Telegram is the BLOCKED channel by definition at fanout time.
    #    `booking_notifications` does NOT have this column (Phase 39 D-39-03)
    #    so no widening is performed there.
    op.alter_column(
        "membership_notifications",
        "telegram_chat_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )


def downgrade() -> None:
    # Strict reverse-order.
    # 1. Restore NOT NULL on telegram_chat_id. Production: any
    #    membership_notifications rows with channel='email' carry NULL here
    #    and MUST be deleted (or backfilled with a sentinel) before downgrade.
    #    The v1.6 dev round-trip is safe because email-fallback service code
    #    lands in subsequent Phase 45 plans.
    op.alter_column(
        "membership_notifications",
        "telegram_chat_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )

    # 2. Drop the audit_correlation_id lookup index.
    op.drop_index(
        "ix_payment_receipts_audit_corr",
        table_name="payment_receipts",
    )

    # 3. Drop the table — implicit drop of CHECK / FK / UNIQUE / PK.
    op.drop_table("payment_receipts")
