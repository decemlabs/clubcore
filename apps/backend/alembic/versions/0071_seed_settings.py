"""Seed settings singletons baseline (Phase 108 CFG-02/CFG-03/CFG-04).

Revision ID: 0071_seed_settings
Revises: 0070_settings_tables
Create Date: 2026-06-14

Data-only migration: seeds the three settings singletons with sane defaults
so fresh environments are functional with zero manual intervention.

Idempotency:
- INSERT ... ON CONFLICT (id) DO NOTHING on all three rows.
- Re-running upgrade() is a verified no-op (T-108-04 accept-mitigated).
- Conflict target is (id) because singletons have deterministic UUID PKs.

asyncpg driver sends all bind params as VARCHAR; explicit CAST(:id AS uuid)
and CAST(:col AS jsonb) are required for uuid/jsonb columns
(mirrors 0059_seed_gym_info + 0068_seed_referral_config pattern).

Seed values:
  booking_config     — mirrors bookings/constants.py defaults (cancel_window=24h)
  working_hours_config — Mon-Fri 08:00-22:00 / Sat-Sun 09:00-21:00; empty breaks/closures
  notification_prefs_config — all 7 notification kinds × in_app channel enabled;
                              sender_signature/quiet_hours NULL

Downgrade hard-deletes the three singleton rows.
"""  # noqa: RUF002

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0071_seed_settings"
down_revision: str | None = "0070_settings_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Deterministic singleton PKs — consistent across all environments.
# gym_info ...001; referral_config ...002; settings singletons ...003/004/005.
_BOOKING_CONFIG_ID = "00000000-0000-0000-0000-000000000003"
_WORKING_HOURS_CONFIG_ID = "00000000-0000-0000-0000-000000000004"
_NOTIFICATION_PREFS_CONFIG_ID = "00000000-0000-0000-0000-000000000005"

# Default working hours schedule — Mon-Fri 08:00-22:00, Sat-Sun 09:00-21:00.
# day_of_week: 0=Monday .. 6=Sunday (ISO weekday - 1)
_DEFAULT_SCHEDULE = json.dumps(
    [
        {"day_of_week": 0, "open": "08:00", "close": "22:00"},  # Monday
        {"day_of_week": 1, "open": "08:00", "close": "22:00"},  # Tuesday
        {"day_of_week": 2, "open": "08:00", "close": "22:00"},  # Wednesday
        {"day_of_week": 3, "open": "08:00", "close": "22:00"},  # Thursday
        {"day_of_week": 4, "open": "08:00", "close": "22:00"},  # Friday
        {"day_of_week": 5, "open": "09:00", "close": "21:00"},  # Saturday
        {"day_of_week": 6, "open": "09:00", "close": "21:00"},  # Sunday
    ]
)

# Default notification matrix: all 7 booking/payment/autopay kinds have in_app enabled.
# The 7 kinds from notifications/models.py _VALID_KINDS:
#   booking_confirmed, booking_cancelled_by_client, booking_cancelled_by_owner,
#   booking_rescheduled, payment_succeeded, autopay_charge_succeeded, autopay_charge_failed
_DEFAULT_MATRIX = json.dumps(
    {
        "booking_confirmed": {"in_app": True},
        "booking_cancelled_by_client": {"in_app": True},
        "booking_cancelled_by_owner": {"in_app": True},
        "booking_rescheduled": {"in_app": True},
        "payment_succeeded": {"in_app": True},
        "autopay_charge_succeeded": {"in_app": True},
        "autopay_charge_failed": {"in_app": True},
    }
)


def upgrade() -> None:
    # ── booking_config ─────────────────────────────────────────────────────────
    # Values mirror bookings/constants.py defaults (cancel_window_hours=24 mirrors
    # CANCEL_WINDOW_HOURS_RECEPTION). asyncpg: CAST(:id AS uuid) required.
    op.execute(
        sa.text(
            "INSERT INTO booking_config "
            "(id, schedule_step_minutes, booking_ahead_days, cutoff_minutes, "
            " cancel_window_hours, cancel_window_enabled, reschedule_same_day, "
            " no_show_penalty_kopecks, no_show_penalty_enabled, "
            " group_limit, waitlist_limit, waitlist_auto_transfer, "
            " client_self_book, show_trainer_windows) "
            "VALUES (CAST(:id AS uuid), :step, :ahead, :cutoff, "
            " :cancel_hours, :cancel_en, :reschedule_same_day, "
            " :no_show_kopecks, :no_show_en, "
            " :group_limit, :waitlist_limit, :waitlist_auto, "
            " :client_self_book, :show_trainer) "
            "ON CONFLICT (id) DO NOTHING"
        ).bindparams(
            id=_BOOKING_CONFIG_ID,
            step=60,
            ahead=14,
            cutoff=60,
            cancel_hours=24,  # mirrors CANCEL_WINDOW_HOURS_RECEPTION
            cancel_en=True,
            reschedule_same_day=True,
            no_show_kopecks=0,
            no_show_en=False,
            group_limit=20,
            waitlist_limit=10,
            waitlist_auto=True,
            client_self_book=True,
            show_trainer=True,
        )
    )

    # ── working_hours_config ───────────────────────────────────────────────────
    # asyncpg: CAST(:schedule AS jsonb) required for JSONB columns.
    op.execute(
        sa.text(
            "INSERT INTO working_hours_config (id, schedule, breaks, closures) "
            "VALUES (CAST(:id AS uuid), CAST(:schedule AS jsonb), "
            "        CAST(:breaks AS jsonb), CAST(:closures AS jsonb)) "
            "ON CONFLICT (id) DO NOTHING"
        ).bindparams(
            id=_WORKING_HOURS_CONFIG_ID,
            schedule=_DEFAULT_SCHEDULE,
            breaks="[]",
            closures="[]",
        )
    )

    # ── notification_prefs_config ──────────────────────────────────────────────
    # asyncpg: CAST(:matrix AS jsonb) required for JSONB columns.
    op.execute(
        sa.text(
            "INSERT INTO notification_prefs_config "
            "(id, matrix, sender_signature, quiet_hours_start, quiet_hours_end) "
            "VALUES (CAST(:id AS uuid), CAST(:matrix AS jsonb), "
            "        NULL, NULL, NULL) "
            "ON CONFLICT (id) DO NOTHING"
        ).bindparams(
            id=_NOTIFICATION_PREFS_CONFIG_ID,
            matrix=_DEFAULT_MATRIX,
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM notification_prefs_config WHERE id = CAST(:id AS uuid)").bindparams(
            id=_NOTIFICATION_PREFS_CONFIG_ID
        )
    )
    op.execute(
        sa.text("DELETE FROM working_hours_config WHERE id = CAST(:id AS uuid)").bindparams(
            id=_WORKING_HOURS_CONFIG_ID
        )
    )
    op.execute(
        sa.text("DELETE FROM booking_config WHERE id = CAST(:id AS uuid)").bindparams(
            id=_BOOKING_CONFIG_ID
        )
    )
