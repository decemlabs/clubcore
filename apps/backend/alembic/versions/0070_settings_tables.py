"""settings_tables: booking_config + working_hours_config + notification_prefs_config singletons.

Phase 108 CFG-02/CFG-03/CFG-04.

Revision ID: 0070_settings_tables
Revises: 0069_referral_crediting_columns
Create Date: 2026-06-14

DDL for three settings singletons:
  booking_config            — scalar int/bool booking rules (CFG-03).
  working_hours_config      — JSONB schedule/breaks/closures (CFG-02).
  notification_prefs_config — JSONB matrix + sender_signature + quiet_hours (CFG-04).

Also adds nullable latitude/longitude columns to gym_info (CFG-01 additive).

Singletons follow the gym_info (0059) pattern: deterministic UUID PKs seeded
by migration 0071_seed_settings.

Downgrade drops columns + tables in reverse creation order (no FKs between them).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import func, text
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0070_settings_tables"
down_revision: str | None = "0069_referral_crediting_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── booking_config ─────────────────────────────────────────────────────────
    # Scalar int/bool columns for CFG-03 booking rules. server_defaults mirror
    # existing bookings/constants.py values so the seeded row is behaviorally
    # equivalent to the current hardcoded constants.
    op.create_table(
        "booking_config",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Scheduling granularity
        sa.Column("schedule_step_minutes", sa.Integer(), nullable=False, server_default="60"),
        # Booking window
        sa.Column("booking_ahead_days", sa.Integer(), nullable=False, server_default="14"),
        sa.Column("cutoff_minutes", sa.Integer(), nullable=False, server_default="60"),
        # Cancellation policy
        sa.Column("cancel_window_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("cancel_window_enabled", sa.Boolean(), nullable=False, server_default="true"),
        # Rescheduling policy
        sa.Column("reschedule_same_day", sa.Boolean(), nullable=False, server_default="true"),
        # No-show penalty (persisted; enforcement deferred per D-108 Context)
        sa.Column("no_show_penalty_kopecks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("no_show_penalty_enabled", sa.Boolean(), nullable=False, server_default="false"),
        # Group class limits
        sa.Column("group_limit", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("waitlist_limit", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("waitlist_auto_transfer", sa.Boolean(), nullable=False, server_default="true"),
        # Self-booking flags
        sa.Column("client_self_book", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("show_trainer_windows", sa.Boolean(), nullable=False, server_default="true"),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_booking_config")),
    )

    # ── working_hours_config ───────────────────────────────────────────────────
    # Three JSONB list columns for CFG-02 schedule/breaks/closures.
    # server_default '[]'::jsonb mirrors GymInfo.hours pattern.
    op.create_table(
        "working_hours_config",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "schedule",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=text("'[]'::jsonb"),
        ),
        sa.Column(
            "breaks",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=text("'[]'::jsonb"),
        ),
        sa.Column(
            "closures",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_working_hours_config")),
    )

    # ── notification_prefs_config ──────────────────────────────────────────────
    # JSONB matrix object + optional text columns for CFG-04 notification prefs.
    # server_default '{}'::jsonb for matrix.
    op.create_table(
        "notification_prefs_config",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "matrix",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=text("'{}'::jsonb"),
        ),
        sa.Column("sender_signature", sa.Text(), nullable=True),
        sa.Column("quiet_hours_start", sa.Text(), nullable=True),
        sa.Column("quiet_hours_end", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_prefs_config")),
    )

    # ── gym_info additive columns (CFG-01) ────────────────────────────────────
    # Nullable float columns — additive, no data loss on downgrade.
    op.add_column("gym_info", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("gym_info", sa.Column("longitude", sa.Float(), nullable=True))


def downgrade() -> None:
    # Remove gym_info additive columns first (no table-drop dependencies)
    op.drop_column("gym_info", "longitude")
    op.drop_column("gym_info", "latitude")

    # Drop settings tables in reverse creation order (no FKs between them)
    op.drop_table("notification_prefs_config")
    op.drop_table("working_hours_config")
    op.drop_table("booking_config")
