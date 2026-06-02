"""clients: notif_prefs JSONB column for notification preferences (Phase 75 NOTIF-01).

Revision ID: 0050_clients_notif_prefs
Revises: 0049_fiscal_receipts_customer_phone
Create Date: 2026-06-02 00:00:00.000000

Additive migration — one nullable JSONB column on the clients table.
No DEFAULT value, no CHECK constraint — JSON content is validated by the
NotifPrefs Pydantic schema (BackendSchemaBase, extra='forbid') at the wire layer.

ADD COLUMN is metadata-only on Postgres 16 — negligible lock window.
Server-side defaults ({promo:true, schedule:true, trainer:true, sound:false})
are applied in the service layer when notif_prefs IS NULL (D-06).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0050_clients_notif_prefs"
down_revision: str | None = "0049_fiscal_receipts_customer_phone"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "clients",
        sa.Column("notif_prefs", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("clients", "notif_prefs")
