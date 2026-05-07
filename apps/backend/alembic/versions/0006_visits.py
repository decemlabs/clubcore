"""visits

Revision ID: 0006_visits
Revises: 0005_memberships
Create Date: 2026-05-07 20:00:00.000000

Phase 19 / VIS-01 — visits table + STORED GENERATED gym_date + race-proof UNIQUE.

Notes:
- gym_date is a Postgres GENERATED ALWAYS AS ((checked_in_at AT TIME ZONE
  'Europe/Moscow')::date) STORED column (D-06). The app NEVER writes it; the
  UNIQUE INDEX uq_visits_client_id_gym_date enforces 1/day at the DB level
  (Pitfall 5 mitigation).
- The constraint name "uq_visits_client_id_gym_date" is referenced as a literal
  string by app/modules/visits/service.py:_is_duplicate_visit_conflict
  (Phase 19 D-08). Renaming the UNIQUE requires updating the service helper.
- The CHECK constraint name "ck_visits_channel" lives in __table_args__ on the
  ORM as well (channel IN ('reception','telegram_bot')).
- Composite index ix_visits_client_id_checked_in_at uses raw op.execute() for
  the DESC qualifier (mirrors Phase 17 ix_memberships_client_id_status_end_date).
- No soft-delete column — visits are immutable historical records (CD-04).
  The UNIQUE is unconditional (no WHERE deleted_at IS NULL partial).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_visits"
down_revision: str | None = "0005_memberships"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "visits",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("membership_id", sa.UUID(), nullable=False),
        sa.Column(
            "checked_in_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "gym_date",
            sa.Date(),
            sa.Computed(
                "(checked_in_at AT TIME ZONE 'Europe/Moscow')::date",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("checked_in_by", sa.UUID(), nullable=True),
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
            "channel IN ('reception', 'telegram_bot')",
            name=op.f("ck_visits_channel"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_visits")),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            name=op.f("fk_visits_client_id_clients"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["membership_id"],
            ["memberships.id"],
            name=op.f("fk_visits_membership_id_memberships"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["checked_in_by"],
            ["users.id"],
            # NOTE: literal-ref'd by service.py:_is_duplicate_visit_conflict (D-08).
            name=op.f("fk_visits_checked_in_by_users"),
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "client_id",
            "gym_date",
            # Unconditional — no WHERE deleted_at IS NULL partial (visits are
            # immutable history; no soft-delete per CD-04). Literal-ref'd by
            # service.py:_is_duplicate_visit_conflict (D-08).
            name="uq_visits_client_id_gym_date",
        ),
    )
    # Composite index — DESC ordering on checked_in_at requires raw SQL because
    # SQLAlchemy's Index() representation of DESC inside a multi-column mixed
    # index is not autogenerate-stable (mirrors Phase 17 pattern).
    op.execute(
        "CREATE INDEX ix_visits_client_id_checked_in_at "
        "ON visits (client_id, checked_in_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_visits_client_id_checked_in_at")
    op.drop_table("visits")
