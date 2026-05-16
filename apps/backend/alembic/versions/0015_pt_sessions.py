"""pt_sessions

Revision ID: 0015_pt_sessions
Revises: 0014_pt_packages
Create Date: 2026-05-16 00:00:00.000000

Phase 34 PT-14 — PT-session row (one per recorded training).

Notes:
- B-05 — `trainer_name_snapshot` is captured at INSERT time in
  pt_sessions.service.record_pt_session (Phase 34 Plan 34-02). This preserves
  historical UI integrity if the parent trainer is later renamed/deactivated.
- D-34-02 — NO partial UNIQUE constraint (multiple sessions per package per day
  allowed; no business rule preventing same-day re-recording).
- D-34-02 — CHECK `cancel_reason IS NULL OR cancelled_at IS NOT NULL` is the
  cancel-consistency invariant: forensic "is this session cancelled?" reduces to
  a single column check.
- Four FK ON DELETE RESTRICT (pt_package_id, trainer_id, client_id,
  performed_by_user_id) — never cascade-delete PT-session history.
- D-34-02 — composite indexes `(pt_package_id, performed_at DESC)` and
  `(trainer_id, performed_at DESC)` support PT-19 listing query (and future
  trainer-load analytics) with the DESC clause matching the access pattern.
- NO SoftDeleteMixin / deleted_at column — lifecycle is single-cancel via
  `cancelled_at IS NOT NULL` (mirrors PtPackage D-33-03 status-only pattern).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015_pt_sessions"
down_revision: str | None = "0014_pt_packages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pt_sessions",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("pt_package_id", sa.UUID(), nullable=False),
        sa.Column("trainer_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("performed_by_user_id", sa.UUID(), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("trainer_name_snapshot", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "cancel_reason IS NULL OR cancelled_at IS NOT NULL",
            name=op.f("ck_pt_sessions_cancel_reason_requires_cancelled_at"),
        ),
        sa.CheckConstraint(
            "cancel_reason IS NULL OR char_length(cancel_reason) <= 200",
            name=op.f("ck_pt_sessions_cancel_reason_length"),
        ),
        sa.CheckConstraint(
            "notes IS NULL OR char_length(notes) <= 500",
            name=op.f("ck_pt_sessions_notes_length"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pt_sessions")),
        sa.ForeignKeyConstraint(
            ["pt_package_id"],
            ["pt_packages.id"],
            name=op.f("fk_pt_sessions_pt_package_id_pt_packages"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["trainer_id"],
            ["trainers.id"],
            name=op.f("fk_pt_sessions_trainer_id_trainers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            name=op.f("fk_pt_sessions_client_id_clients"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["performed_by_user_id"],
            ["users.id"],
            name=op.f("fk_pt_sessions_performed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
    )
    # Composite indexes (D-34-02): performed_at DESC matches the access pattern
    # for `GET /pt-packages/{id}/sessions` (PT-19) and future trainer-load
    # analytics. sa.text("performed_at DESC") preserves the index direction.
    op.create_index(
        "ix_pt_sessions_pt_package_id_performed_at_desc",
        "pt_sessions",
        ["pt_package_id", sa.text("performed_at DESC")],
    )
    op.create_index(
        "ix_pt_sessions_trainer_id_performed_at_desc",
        "pt_sessions",
        ["trainer_id", sa.text("performed_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pt_sessions_trainer_id_performed_at_desc",
        table_name="pt_sessions",
    )
    op.drop_index(
        "ix_pt_sessions_pt_package_id_performed_at_desc",
        table_name="pt_sessions",
    )
    op.drop_table("pt_sessions")
