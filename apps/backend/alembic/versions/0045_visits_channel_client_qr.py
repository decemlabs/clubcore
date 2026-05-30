"""Extend ck_visits_channel CHECK to allow 'client_qr' channel (Phase 70 D-70-11).

Revision ID: 0045_visits_channel_client_qr
Revises: 0044_client_refresh_token
Create Date: 2026-05-30 00:00:00.000000

Postgres requires DROP + CREATE to modify a CHECK constraint expression
(no ALTER CONSTRAINT for CHECK). The constraint name `ck_visits_channel`
is kept identical so it remains discoverable alongside the UNIQUE
`uq_visits_client_id_gym_date` (sibling discipline in service.py).

The ORM CheckConstraint in visits/models.py __table_args__ must be kept
in sync — updated in the same plan (70-01, Task 3).

Security: T-70-04 — DB-level CHECK restricts channel to an allow-list;
'client_qr' added explicitly, no open-ended values. Migration round-trip
tested in tests/integration/migrations/test_visits_channel_client_qr.py.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0045_visits_channel_client_qr"
down_revision: str | None = "0044_client_refresh_token"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CONSTRAINT_NAME = "ck_visits_channel"


def upgrade() -> None:
    # Postgres cannot ALTER a CHECK constraint expression — must drop then recreate.
    # op.f() marks the name as already-formatted so the project's NAMING_CONVENTION
    # (ck_%(table_name)s_%(constraint_name)s) does NOT double-prefix — mirrors 0032
    # and 0024 precedent.
    op.drop_constraint(op.f(_CONSTRAINT_NAME), "visits", type_="check")
    op.create_check_constraint(
        op.f(_CONSTRAINT_NAME),
        "visits",
        "channel IN ('reception', 'telegram_bot', 'client_qr')",
    )


def downgrade() -> None:
    # Reverse: drop the extended CHECK, restore the original two-value CHECK.
    op.drop_constraint(op.f(_CONSTRAINT_NAME), "visits", type_="check")
    op.create_check_constraint(
        op.f(_CONSTRAINT_NAME),
        "visits",
        "channel IN ('reception', 'telegram_bot')",
    )
