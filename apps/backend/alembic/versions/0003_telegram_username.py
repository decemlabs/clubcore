"""telegram_username

Revision ID: 0003_telegram_username
Revises: 0001_auth
Create Date: 2026-05-02 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_telegram_username"
down_revision: str | None = "0001_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("telegram_username", sa.Text(), nullable=True),
    )
    op.create_unique_constraint(
        op.f("uq_users_telegram_username"),
        "users",
        ["telegram_username"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("uq_users_telegram_username"),
        "users",
        type_="unique",
    )
    op.drop_column("users", "telegram_username")
