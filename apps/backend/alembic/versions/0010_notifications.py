"""Phase 27 / NTF-01: expiring-soon notification idempotency table.

Revision ID: 0010_notifications
Revises: 0009_renewal
Create Date: 2026-05-09 00:00:00.000000

Notes:
- The unique constraint `uq_membership_notifications_membership_kind` is
  the single source of truth for cron idempotency (D-27-15). Helper code
  in `app/modules/memberships/service.py:_send_expiring_notifications`
  catches IntegrityError on this constraint to skip race-duplicates.
- Constraint name is NOT literal-ref'd by service code (no constraint-name
  discriminator needed; the entire UNIQUE family is treated uniformly), so
  NO entry is added to `apps/backend/alembic/env.py:_include_object`
  (mirrors Phase 26 D-26-XX — only literal-ref'd constraint names go there).
- Downgrade DROPs the table — disaster recovery only; loses idempotency
  history (worst case: client receives a duplicate DM in the next 7d/3d/1d
  window after an upgrade-then-downgrade cycle).
- Alembic chain context: 0007_status_taxonomy → 0008_freeze → 0009_renewal
  → 0010_notifications (Phase 27).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010_notifications"
down_revision: str | None = "0009_renewal"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) CREATE TABLE membership_notifications (single new table — Phase 27 NTF-01).
    op.create_table(
        "membership_notifications",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("membership_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_membership_notifications")),
        sa.ForeignKeyConstraint(
            ["membership_id"],
            ["memberships.id"],
            name=op.f("fk_membership_notifications_membership_id_memberships"),
            # D-27-02: cascade — DBA-direct hard-delete drops history.
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "kind IN ('expiring_7d', 'expiring_3d', 'expiring_1d')",
            name=op.f("ck_membership_notifications_kind"),
        ),
    )

    # 2) UNIQUE constraint on (membership_id, kind) — idempotency single source of truth.
    #    Explicit literal name (NOT op.f()) per D-27-02; matches service-side
    #    helper expectations and the ORM __table_args__ entry in models.py.
    op.create_unique_constraint(
        "uq_membership_notifications_membership_kind",
        "membership_notifications",
        ["membership_id", "kind"],
    )

    # 3) Single-column index for forensic per-membership lookup.
    op.create_index(
        op.f("ix_membership_notifications_membership_id"),
        "membership_notifications",
        ["membership_id"],
    )


def downgrade() -> None:
    """Reverse upgrade in reverse order — disaster recovery only (D-27-03)."""
    op.drop_index(
        op.f("ix_membership_notifications_membership_id"),
        table_name="membership_notifications",
    )
    op.drop_constraint(
        "uq_membership_notifications_membership_kind",
        "membership_notifications",
        type_="unique",
    )
    op.drop_table("membership_notifications")
