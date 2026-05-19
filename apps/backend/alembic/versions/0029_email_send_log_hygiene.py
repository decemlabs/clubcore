"""email_send_log hygiene: bounce_type CHECK + status CHECK extension for circuit_open.

Revision ID: 0029_email_send_log_hygiene
Revises: 0028_users_email_verified
Create Date: 2026-05-19 12:00:00.000000

Phase 42 plan 42-16. Two small CHECK adjustments:

  1. WR-01 -- Add CHECK ck_email_send_log_bounce_type enforcing
     bounce_type IN ('hard','soft','complaint') OR bounce_type IS NULL.
     The model docstring already declared this taxonomy (models.py:65-66)
     but the column was free-form Text; webhook writes 'hard'/'soft'
     correctly today, but any future typo would silently land malformed
     data in a forensic column.

  2. WR-04 -- Extend ck_email_send_log_status to include 'circuit_open'.
     The dispatch_email task short-circuits the provider call when the
     Redis breaker is open and currently writes status='rejected', which
     the 0026 migration docstring reserves for permanent_error from the
     provider. The new value separates breaker-shorts from real
     rejections so forensic queries can distinguish them.

Naming-convention note (mirrors 0026/0027): pass the literal CHECK
constraint names through ``op.f()`` so the project ``naming_convention``
(``ck_%(table_name)s_%(constraint_name)s`` in ``app/core/database.py``)
does NOT re-prefix the table name.

Downgrade note: if any rows have status='circuit_open' at downgrade time,
the final op.create_check_constraint will raise. Down-migration is a
developer/test-only path; production data should not contain the new value
when reverting. Stop all workers before running downgrade.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0029_email_send_log_hygiene"
down_revision: str | None = "0028_users_email_verified"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STATUS_OLD = "status IN ('sent','bounced','complained','delivered','rejected')"
_STATUS_NEW = (
    "status IN ('sent','bounced','complained','delivered','rejected','circuit_open')"
)
_BOUNCE_TYPE_PREDICATE = (
    "bounce_type IN ('hard','soft','complaint') OR bounce_type IS NULL"
)


def upgrade() -> None:
    # 1. WR-04: drop + recreate status CHECK with the extended set.
    op.drop_constraint(
        op.f("ck_email_send_log_status"),
        "email_send_log",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_email_send_log_status"),
        "email_send_log",
        _STATUS_NEW,
    )

    # 2. WR-01: add bounce_type CHECK (predicate allows NULL).
    op.create_check_constraint(
        op.f("ck_email_send_log_bounce_type"),
        "email_send_log",
        _BOUNCE_TYPE_PREDICATE,
    )


def downgrade() -> None:
    # Reverse WR-01.
    op.drop_constraint(
        op.f("ck_email_send_log_bounce_type"),
        "email_send_log",
        type_="check",
    )
    # Reverse WR-04 -- revert to original 5-value status CHECK.
    # NOTE: if any rows have status='circuit_open' at downgrade time, this
    # will raise. Down-migration is a developer/test-only path; production
    # data should not contain the new value when reverting.
    op.drop_constraint(
        op.f("ck_email_send_log_status"),
        "email_send_log",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_email_send_log_status"),
        "email_send_log",
        _STATUS_OLD,
    )
