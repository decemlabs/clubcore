"""users lifecycle columns: is_active, status, deactivated_at, deactivated_by_user_id (USERS-04/05).

Revision ID: 0030_users_lifecycle_columns
Revises: 0029_email_send_log_hygiene
Create Date: 2026-05-19 12:00:00.000000

Phase 43 USERS-04/05 / D-43-05/06/07. Single feature-phase migration outside
the 0022-0025 bedrock bundle (D-41-15 scoped bedrock to those four). All
existing rows become is_active=true, status='active' on upgrade — matches
today's implicit always-active behaviour.

Steps:
  1. Add users.is_active BOOLEAN NOT NULL DEFAULT true.
  2. Add users.status TEXT NOT NULL DEFAULT 'active' with CHECK in ('active','pending_invitation').
  3. Add users.deactivated_at TIMESTAMPTZ NULL.
  4. Add users.deactivated_by_user_id UUID NULL FK users.id ON DELETE SET NULL.
  5. Add CHECK ck_users_lifecycle_consistency:
        (is_active = true AND deactivated_at IS NULL) OR
        (is_active = false AND deactivated_at IS NOT NULL)
  6. Drop NOT NULL from users.password_hash (invited-but-unaccepted rows carry NULL).

Naming-convention note (mirrors 0024/0026/0027/0029): pass literal CHECK and
FK constraint names through ``op.f()`` so the project naming_convention
(``ck_%(table_name)s_%(constraint_name)s`` /
``fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s`` in
``app/core/database.py``) does NOT re-prefix and double the table name.

Downgrade note: dropping NOT NULL on ``password_hash`` is reversed by
re-asserting NOT NULL. In production, any ``status='pending_invitation'``
rows carry NULL hashes and MUST be backfilled or deleted before downgrade.
The dev round-trip is safe because pending-invitation rows do not exist
until Phase 43 service code lands (Wave 2).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0030_users_lifecycle_columns"
down_revision: str | None = "0029_email_send_log_hygiene"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. is_active BOOLEAN NOT NULL DEFAULT true — every existing row becomes active.
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    # 2. status TEXT NOT NULL DEFAULT 'active' — explicit column over derived
    #    (password_hash IS NULL) per D-43-06 second bullet.
    op.add_column(
        "users",
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
    )

    # 3. deactivated_at TIMESTAMPTZ NULL — set atomically with is_active=false.
    op.add_column(
        "users",
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 4. deactivated_by_user_id UUID NULL — FK self-reference with SET NULL
    #    (preserves history past deactivator soft-delete; D-43-06 fourth bullet).
    op.add_column(
        "users",
        sa.Column(
            "deactivated_by_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        op.f("fk_users_deactivated_by_user_id_users"),
        "users",
        "users",
        ["deactivated_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 5. status CHECK — admit two values today; v1.7 may ALTER to add 'invited_expired'.
    op.create_check_constraint(
        op.f("ck_users_status"),
        "users",
        "status IN ('active', 'pending_invitation')",
    )

    # 6. lifecycle-consistency CHECK — correlate is_active and deactivated_at
    #    at the DB layer (mirrors v1.2 freeze period CHECK pattern, D-43-06 third bullet).
    op.create_check_constraint(
        op.f("ck_users_lifecycle_consistency"),
        "users",
        "(is_active = true AND deactivated_at IS NULL) "
        "OR (is_active = false AND deactivated_at IS NOT NULL)",
    )

    # 7. Drop NOT NULL on password_hash — invited rows live with NULL until
    #    invitation-accept (Phase 44 RESET-04) sets the password. D-43-06 fifth bullet.
    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.Text(),
        nullable=True,
    )


def downgrade() -> None:
    # Strict reverse-order: each undo is destructive; document semantics.
    # 1. Re-assert NOT NULL on password_hash. Production: backfill any NULL
    #    hashes (delete pending_invitation rows) before running this.
    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.Text(),
        nullable=False,
    )

    # 2. Drop lifecycle-consistency CHECK.
    op.drop_constraint(
        op.f("ck_users_lifecycle_consistency"),
        "users",
        type_="check",
    )

    # 3. Drop status CHECK.
    op.drop_constraint(
        op.f("ck_users_status"),
        "users",
        type_="check",
    )

    # 4. Drop self-FK before the column it lives on.
    op.drop_constraint(
        op.f("fk_users_deactivated_by_user_id_users"),
        "users",
        type_="foreignkey",
    )

    # 5-8. Drop columns in reverse add-order.
    op.drop_column("users", "deactivated_by_user_id")
    op.drop_column("users", "deactivated_at")
    op.drop_column("users", "status")
    op.drop_column("users", "is_active")
