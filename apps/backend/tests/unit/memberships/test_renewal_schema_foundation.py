"""Phase 26 / 26-01 — schema foundation unit tests.

RED phase coverage for:
  - ORM Membership.previous_membership_id mapped column (D-26-04 / D-26-05).
  - Index `ix_memberships_previous_membership_id` declared in __table_args__.
  - Alembic migration `0009_renewal.py` chain header + DDL ops contain the
    expected operations (column + self-FK + index).

The migration body is asserted by source-text inspection (cheap, no DB
roundtrip) — full upgrade/downgrade round-trip is verified separately by the
plan's integration verification step (`uv run alembic upgrade head`).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import Index

from app.modules.memberships.models import Membership

# ---------------------------------------------------------------------------
# ORM column assertions (Phase 26 D-26-04 / D-26-05)
# ---------------------------------------------------------------------------


def test_membership_has_previous_membership_id_column() -> None:
    """Membership.previous_membership_id is a Mapped UUID, nullable=True."""
    column = Membership.__table__.c.get("previous_membership_id")
    assert column is not None, "previous_membership_id column missing on memberships"
    assert column.nullable is True, "previous_membership_id must be nullable"


def test_membership_previous_membership_id_self_fk() -> None:
    """Self-FK on memberships.id with ON DELETE SET NULL (D-26-05)."""
    column = Membership.__table__.c["previous_membership_id"]
    fks = list(column.foreign_keys)
    assert len(fks) == 1, "expected exactly one ForeignKey on previous_membership_id"
    fk = fks[0]
    assert fk.column.table.name == "memberships"
    assert fk.column.name == "id"
    assert fk.ondelete == "SET NULL", "ON DELETE SET NULL preserves chain (D-26-05)"
    assert fk.name == "fk_memberships_previous_membership_id_memberships"


def test_membership_table_args_includes_previous_membership_id_index() -> None:
    """__table_args__ declares Index('ix_memberships_previous_membership_id', ...)."""
    indexes = [
        item
        for item in Membership.__table_args__
        if isinstance(item, Index)
        and item.name == "ix_memberships_previous_membership_id"
    ]
    assert len(indexes) == 1, "expected exactly one ix_memberships_previous_membership_id Index"
    cols = [c.name for c in indexes[0].columns]
    assert cols == ["previous_membership_id"]


# ---------------------------------------------------------------------------
# Migration source-text assertions (Phase 26 D-26-01..D-26-03)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def migration_source() -> str:
    """Return raw text of 0009_renewal.py."""
    path = (
        Path(__file__).resolve().parents[3]
        / "alembic"
        / "versions"
        / "0009_renewal.py"
    )
    assert path.exists(), f"migration file missing: {path}"
    return path.read_text(encoding="utf-8")


def test_migration_revision_header(migration_source: str) -> None:
    """Revision header matches Phase 26 chain (0008_freeze → 0009_renewal)."""
    assert 'revision: str = "0009_renewal"' in migration_source
    assert 'down_revision: str | None = "0008_freeze"' in migration_source


def test_migration_upgrade_adds_column(migration_source: str) -> None:
    """upgrade() adds the previous_membership_id column as nullable UUID."""
    assert 'op.add_column(' in migration_source
    assert '"previous_membership_id"' in migration_source
    assert "nullable=True" in migration_source


def test_migration_upgrade_creates_self_fk_set_null(migration_source: str) -> None:
    """upgrade() creates a self-FK on memberships.id with ON DELETE SET NULL."""
    assert "op.create_foreign_key(" in migration_source
    assert '"fk_memberships_previous_membership_id_memberships"' in migration_source
    assert 'ondelete="SET NULL"' in migration_source


def test_migration_upgrade_creates_index(migration_source: str) -> None:
    """upgrade() creates ix_memberships_previous_membership_id."""
    assert "op.create_index(" in migration_source
    assert '"ix_memberships_previous_membership_id"' in migration_source


def test_migration_downgrade_reverses_in_reverse_order(migration_source: str) -> None:
    """downgrade() drops index → constraint → column in that order."""
    src = migration_source
    drop_index_pos = src.find("op.drop_index(")
    drop_constraint_pos = src.find("op.drop_constraint(")
    drop_column_pos = src.find("op.drop_column(")
    assert drop_index_pos != -1, "downgrade() must drop_index"
    assert drop_constraint_pos != -1, "downgrade() must drop_constraint"
    assert drop_column_pos != -1, "downgrade() must drop_column"
    assert drop_index_pos < drop_constraint_pos < drop_column_pos, (
        "downgrade order must be drop_index → drop_constraint → drop_column"
    )
