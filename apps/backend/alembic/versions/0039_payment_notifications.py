"""0039 — payment_notifications table (Phase 52 NOT-03 / D-52-04).

Creates the payment_notifications idempotency table for cross-channel
client notifications and owner operator alerts.

Polymorphic subject (D-52-10 resolution — Option A, DB-UNIQUE across all kinds):
``payment_id`` FK targets ``payments.id`` ON DELETE RESTRICT — used for
payment_succeeded, refund_succeeded, and fiscal_failed kinds (the notification
is tied to the ledger row).
``online_payment_id`` FK targets ``online_payments.id`` ON DELETE RESTRICT —
used for payment_canceled kind (canceled payments never write a payments ledger
row, so the online_payments.id is the stable dedup key).

Both FK columns are nullable with an XOR CHECK (exactly one non-null),
mirroring the OnlinePayment subject-XOR precedent (D-49-04 / D-52-10).

Dedup is via TWO PARTIAL UNIQUE INDEXES (one per subject FK) — a single
all-columns UNIQUE cannot span the NULL column, so PostgreSQL partial
indexes are required:
  uq_payment_notifications_payment_kind_channel   (payment_id IS NOT NULL)
  uq_payment_notifications_online_payment_kind_channel (online_payment_id IS NOT NULL)

NAMING_CONVENTION: op.f() wrappers on PK / FK / CHECK / UNIQUE.
ORM model lives at app/modules/online_payments/models.py (PaymentNotification).

Downgrade order: drop partial-unique indexes BEFORE drop_table.

Revision ID: 0039_payment_notifications
Revises: 0038_fiscal_receipts_created_at
Create Date: 2026-05-23 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0039_payment_notifications"
down_revision: str | None = "0038_fiscal_receipts_created_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payment_notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Polymorphic subject FKs — exactly one must be non-null (XOR CHECK below).
        # payment_id is used for payment_succeeded / refund_succeeded / fiscal_failed.
        # online_payment_id is used for payment_canceled (no payments ledger row).
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("online_payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # TimestampMixin columns (created_at / updated_at):
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_notifications")),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name=op.f("fk_payment_notifications_payment_id_payments"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["online_payment_id"],
            ["online_payments.id"],
            name=op.f("fk_payment_notifications_online_payment_id_online_payments"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "kind IN ('payment_succeeded', 'refund_succeeded', "
            "'payment_canceled', 'fiscal_failed')",
            name=op.f("ck_payment_notifications_kind"),
        ),
        sa.CheckConstraint(
            "channel IN ('telegram', 'email')",
            name=op.f("ck_payment_notifications_channel"),
        ),
        # XOR: exactly one of payment_id / online_payment_id must be non-null.
        # Mirrors the D-49-04 OnlinePayment subject-XOR precedent.
        sa.CheckConstraint(
            "(payment_id IS NOT NULL) <> (online_payment_id IS NOT NULL)",
            name=op.f("ck_payment_notifications_subject_xor"),
        ),
    )
    # Two partial UNIQUE indexes — one per subject FK — so NULL in the
    # other FK column does not break UNIQUE semantics.
    op.create_index(
        "uq_payment_notifications_payment_kind_channel",
        "payment_notifications",
        ["payment_id", "kind", "channel"],
        unique=True,
        postgresql_where=sa.text("payment_id IS NOT NULL"),
    )
    op.create_index(
        "uq_payment_notifications_online_payment_kind_channel",
        "payment_notifications",
        ["online_payment_id", "kind", "channel"],
        unique=True,
        postgresql_where=sa.text("online_payment_id IS NOT NULL"),
    )
    # Lookup indexes for FK columns.
    op.create_index(
        "ix_payment_notifications_payment_id",
        "payment_notifications",
        ["payment_id"],
    )
    op.create_index(
        "ix_payment_notifications_online_payment_id",
        "payment_notifications",
        ["online_payment_id"],
    )


def downgrade() -> None:
    # Drop indexes before dropping the table (lossless reverse order).
    op.drop_index("ix_payment_notifications_online_payment_id", "payment_notifications")
    op.drop_index("ix_payment_notifications_payment_id", "payment_notifications")
    op.drop_index(
        "uq_payment_notifications_online_payment_kind_channel",
        "payment_notifications",
    )
    op.drop_index(
        "uq_payment_notifications_payment_kind_channel",
        "payment_notifications",
    )
    op.drop_table("payment_notifications")
