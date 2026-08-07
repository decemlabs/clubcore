"""autopay_charges idempotency ledger + autopay_charge_notifications claim store (Phase 84 APAY-03/APAY-04).

Revision ID: 0056_autopay_charges
Revises: 0055_loyalty_redemption_columns
Create Date: 2026-06-05

Creates two new tables:

1. autopay_charges — idempotency ledger for off-session recurring charges.
   - membership_id RESTRICT FK → memberships.id
   - period_end DATE NOT NULL
   - status TEXT NOT NULL server_default 'pending'
   - amount_kopecks INTEGER NOT NULL
   - yookassa_payment_id TEXT nullable
   - online_payment_id UUID nullable (links off-session online_payments row; NO FK — cross-module)
   - failure_reason TEXT nullable
   - charged_at TIMESTAMPTZ nullable
   - UNIQUE(membership_id, period_end) — double-charge guard (T-84-01)
   - CHECK status IN ('pending','succeeded','failed')

2. autopay_charge_notifications — per-channel claim store for failure notifications.
   - autopay_charge_id RESTRICT FK → autopay_charges.id
   - kind TEXT NOT NULL
   - channel TEXT NOT NULL
   - sent_at TIMESTAMPTZ NOT NULL server_default now()
   - UNIQUE(autopay_charge_id, kind, channel) — dedup guard (T-84-04b)
   - CHECK channel IN ('telegram','email')
   - CHECK kind IN ('autopay_charge_failed')

Also widens online_payments.ck_online_payments_confirmation_type from
IN ('redirect','qr') to IN ('redirect','qr','autopay') — required for the
Plan 02 off-session insert that sets confirmation_type='autopay'.
"""  # noqa: E501

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import func, text
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0056_autopay_charges"
down_revision: str | None = "0055_loyalty_redemption_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. autopay_charges — idempotency ledger
    # ------------------------------------------------------------------
    op.create_table(
        "autopay_charges",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("amount_kopecks", sa.Integer(), nullable=False),
        sa.Column("yookassa_payment_id", sa.Text(), nullable=True),
        # online_payment_id: links off-session online_payments row (Plan 02 UPDATE).
        # NO FK to keep modules-independent (D-54-08 / cross-module discipline).
        sa.Column("online_payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("charged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_autopay_charges")),
        sa.ForeignKeyConstraint(
            ["membership_id"],
            ["memberships.id"],
            name=op.f("fk_autopay_charges_membership_id_memberships"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed')",
            name=op.f("ck_autopay_charges_status"),
        ),
        # Literal UNIQUE name (no op.f()) — matches model declaration, alembic-clean-safe.
        sa.UniqueConstraint(
            "membership_id",
            "period_end",
            name="uq_autopay_charges_membership_period",
        ),
    )
    op.create_index(
        op.f("ix_autopay_charges_membership_id"),
        "autopay_charges",
        ["membership_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # 2. autopay_charge_notifications — per-channel claim store
    #    (created AFTER autopay_charges so the FK target exists)
    # ------------------------------------------------------------------
    op.create_table(
        "autopay_charge_notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("autopay_charge_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_autopay_charge_notifications")),
        sa.ForeignKeyConstraint(
            ["autopay_charge_id"],
            ["autopay_charges.id"],
            name=op.f("fk_autopay_charge_notifications_autopay_charge_id_autopay_charges"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "channel IN ('telegram', 'email')",
            name=op.f("ck_autopay_charge_notifications_channel"),
        ),
        sa.CheckConstraint(
            "kind IN ('autopay_charge_failed')",
            name=op.f("ck_autopay_charge_notifications_kind"),
        ),
        # Literal UNIQUE name (no op.f()) — matches model declaration, alembic-clean-safe.
        sa.UniqueConstraint(
            "autopay_charge_id",
            "kind",
            "channel",
            name="uq_autopay_charge_notifications_charge_kind_channel",
        ),
    )
    op.create_index(
        op.f("ix_autopay_charge_notifications_autopay_charge_id"),
        "autopay_charge_notifications",
        ["autopay_charge_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # 3. Widen online_payments.ck_online_payments_confirmation_type
    #    from IN ('redirect','qr') to IN ('redirect','qr','autopay').
    #    Plan 02 off-session insert writes confirmation_type='autopay';
    #    the existing 2-value CHECK would reject it with IntegrityError.
    #
    #    Use op.execute raw DDL (not op.drop_constraint / op.create_check_constraint)
    #    because the naming convention template would double-prefix an already-expanded
    #    name like "ck_online_payments_confirmation_type" — raw DDL is the safe path
    #    for modifying constraints on existing locked tables (D-25-05 lineage).
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE online_payments DROP CONSTRAINT ck_online_payments_confirmation_type")
    op.execute(
        "ALTER TABLE online_payments ADD CONSTRAINT ck_online_payments_confirmation_type "
        "CHECK (confirmation_type IN ('redirect','qr','autopay'))"
    )


def downgrade() -> None:
    # ------------------------------------------------------------------
    # Reverse in strict reverse order.
    # ------------------------------------------------------------------

    # 3. Restore original 2-value CHECK on online_payments (raw DDL — see upgrade comment)
    op.execute("ALTER TABLE online_payments DROP CONSTRAINT ck_online_payments_confirmation_type")
    op.execute(
        "ALTER TABLE online_payments ADD CONSTRAINT ck_online_payments_confirmation_type "
        "CHECK (confirmation_type IN ('redirect','qr'))"
    )

    # 2. autopay_charge_notifications (index then table)
    op.drop_index(
        op.f("ix_autopay_charge_notifications_autopay_charge_id"),
        table_name="autopay_charge_notifications",
    )
    op.drop_table("autopay_charge_notifications")

    # 1. autopay_charges (index then table)
    op.drop_index(
        op.f("ix_autopay_charges_membership_id"),
        table_name="autopay_charges",
    )
    op.drop_table("autopay_charges")
