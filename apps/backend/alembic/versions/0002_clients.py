"""clients_and_audit_log

Revision ID: 0002_clients
Revises: 0003_telegram_username
Create Date: 2026-05-03 08:45:00.000000

Phase 8 INFRA-04 + AUDIT-01 + CLIENTS-01/CLIENTS-02 + D-05/D-06/D-07/D-15..D-17/D-20.

Order is significant (D-20):
  1. CREATE EXTENSION pg_trgm — required by GIN trgm indexes below.
  2. clients table.
  3. Partial unique index on (phone) WHERE deleted_at IS NULL (CLIENTS-02).
  4. GIN trigram expression indexes on lower(last_name) / lower(first_name)
     declared via raw op.execute() because SA autogenerate can't represent them
     (Pitfall 1 — Plan 08 will install env.py include_object filter).
  5. audit_log table.
  6. Btree (actor_user_id, created_at) on audit_log.

Note: down_revision points to 0003_telegram_username because Phase 7 already
landed that migration ahead of Phase 8 starting; the chain stays linear.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_clients"
down_revision: str | None = "0003_telegram_username"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. pg_trgm extension (D-20). Idempotent — safe to re-run.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # 2. clients table (CLIENTS-01).
    op.create_table(
        "clients",
        sa.Column("last_name", sa.Text(), nullable=False),
        sa.Column("first_name", sa.Text(), nullable=False),
        sa.Column("middle_name", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("birthday", sa.Date(), nullable=True),
        sa.Column(
            "gender",
            sa.Enum("male", "female", name="gender", native_enum=False, length=16),
            nullable=True,
        ),
        sa.Column(
            "tags",
            sa.ARRAY(sa.Text()),
            server_default=text("ARRAY[]::TEXT[]"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "emergency_contact",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
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
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "gender IN ('male', 'female')",
            name=op.f("ck_clients_gender"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_clients")),
        sa.UniqueConstraint(
            "telegram_user_id",
            name=op.f("uq_clients_telegram_user_id"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_clients_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
    )

    # 3. Partial unique index — phone uniqueness only across alive clients (CLIENTS-02).
    op.create_index(
        "uq_clients_phone_alive",
        "clients",
        ["phone"],
        unique=True,
        postgresql_where=text("deleted_at IS NULL"),
    )

    # 4. GIN trigram expression indexes for ILIKE-search on last/first name.
    #    Raw DDL because SA autogenerate cannot represent expression indexes.
    op.execute(
        "CREATE INDEX ix_clients_last_name_trgm "
        "ON clients USING gin (lower(last_name) gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_clients_first_name_trgm "
        "ON clients USING gin (lower(first_name) gin_trgm_ops)"
    )

    # 5. audit_log table (AUDIT-01, D-05/D-06/D-07).
    op.create_table(
        "audit_log",
        sa.Column("actor_user_id", sa.UUID(), nullable=True),  # D-06
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=False),
        sa.Column("resource_id", sa.UUID(), nullable=True),  # D-07
        sa.Column(
            "payload",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            server_default=text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_audit_log_actor_user_id_users"),
            ondelete="RESTRICT",
        ),
    )

    # 6. Btree on (actor_user_id, created_at) for per-actor history queries.
    op.create_index(
        "ix_audit_log_actor_user_id_created_at",
        "audit_log",
        ["actor_user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_audit_log_actor_user_id_created_at",
        table_name="audit_log",
    )
    op.drop_table("audit_log")
    op.drop_index("ix_clients_first_name_trgm", table_name="clients")
    op.drop_index("ix_clients_last_name_trgm", table_name="clients")
    op.drop_index("uq_clients_phone_alive", table_name="clients")
    op.drop_table("clients")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
