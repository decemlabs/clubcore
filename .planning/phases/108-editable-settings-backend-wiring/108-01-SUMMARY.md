---
phase: 108-editable-settings-backend-wiring
plan: "01"
subsystem: backend
tags: [rbac, audit, settings, migrations, orm]
dependency_graph:
  requires: []
  provides:
    - "(EDIT, SETTINGS) RBAC pair on both backend and frontend"
    - "Four LOCKED audit events for settings domain"
    - "BookingConfig / WorkingHoursConfig / NotificationPrefsConfig ORM models"
    - "Alembic migrations 0070 (DDL) + 0071 (seed)"
    - "gym_info.latitude / longitude columns"
  affects:
    - apps/backend/app/core/permissions.py
    - apps/admin-app/src/shared/session/can.ts
    - apps/backend/app/core/audit.py
    - apps/backend/app/modules/settings/models.py
    - apps/backend/app/modules/gym/models.py
tech_stack:
  added:
    - "app.modules.settings (new independent module per D-20-MODULE)"
  patterns:
    - "Singleton ORM model with UUIDPkMixin + TimestampMixin (mirrors gym_info pattern)"
    - "JSONB list columns with server_default '[]'::jsonb"
    - "asyncpg CAST(:id AS uuid) bind pattern for seed migrations"
    - "ON CONFLICT (id) DO NOTHING idempotent seed"
key_files:
  created:
    - apps/backend/app/modules/settings/__init__.py
    - apps/backend/app/modules/settings/models.py
    - apps/backend/alembic/versions/0070_settings_tables.py
    - apps/backend/alembic/versions/0071_seed_settings.py
  modified:
    - apps/backend/app/core/permissions.py
    - apps/admin-app/src/shared/session/can.ts
    - apps/backend/app/core/audit.py
    - apps/backend/app/modules/gym/models.py
    - apps/backend/alembic/env.py
    - apps/backend/tests/unit/test_permissions.py
    - apps/backend/tests/unit/test_audit_taxonomy.py
    - apps/backend/tests/integration/test_rbac_parity.py
decisions:
  - "D-108-01-ENV-VERSION-NUM: Alembic env.py now sets version_num_col_type=String(255) because project revision IDs exceed Alembic default VARCHAR(32). The existing alembic_version table was ALTER COLUMN'd to VARCHAR(255) on the fresh dev DB."
  - "D-108-01-SETTINGS-INDEPENDENT: settings module created as independent per D-20-MODULE; no FK references to domain modules"
metrics:
  duration: "~35 minutes"
  completed: "2026-06-14"
  tasks_completed: 3
  tasks_total: 3
  files_created: 4
  files_modified: 9
---

# Phase 108 Plan 01: RBAC + Audit Events + Settings Models + Migrations Summary

RBAC `(EDIT, SETTINGS)` byte-parity pair landed on both backend and frontend; four LOCKED audit events pre-registered; three settings singleton ORM models created; Alembic migrations 0070 (DDL) + 0071 (seed) round-trip clean.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | RBAC (EDIT, SETTINGS) parity + four LOCKED audit events | f83ef3b7 | permissions.py, can.ts, audit.py, 3 test files |
| 2 | Settings singleton ORM models + gym lat/lng columns | 8a2e9c4c | settings/__init__.py, settings/models.py, gym/models.py |
| 3 | Alembic migrations 0070 + 0071 + env.py fix | bfdb2c84 | 0070_settings_tables.py, 0071_seed_settings.py, env.py |

## Key Values

**RBAC (OWNER_ONLY count):** 42 (was 41 before Phase 108)

**Migration revision IDs:**
- `0070_settings_tables` — DDL for three singletons + gym lat/lng additive columns
- `0071_seed_settings` — seed data for three singletons

**Deterministic PK constants:**
- `BookingConfig` PK: `00000000-0000-0000-0000-000000000003`
- `WorkingHoursConfig` PK: `00000000-0000-0000-0000-000000000004`
- `NotificationPrefsConfig` PK: `00000000-0000-0000-0000-000000000005`

**Seeded booking_config defaults:**
- `schedule_step_minutes=60`, `booking_ahead_days=14`, `cutoff_minutes=60`
- `cancel_window_hours=24` (mirrors `CANCEL_WINDOW_HOURS_RECEPTION`)
- `cancel_window_enabled=true`, `reschedule_same_day=true`
- `no_show_penalty_kopecks=0`, `no_show_penalty_enabled=false`
- `group_limit=20`, `waitlist_limit=10`, `waitlist_auto_transfer=true`
- `client_self_book=true`, `show_trainer_windows=true`

**Seeded working_hours_config:**
- Mon-Fri: `08:00 - 22:00`; Sat-Sun: `09:00 - 21:00`
- `breaks=[]`, `closures=[]`

**Seeded notification_prefs_config:**
- `matrix`: all 7 kinds × in_app channel enabled (`true`)
- `sender_signature=NULL`, `quiet_hours_start=NULL`, `quiet_hours_end=NULL`

**LOCKED audit events added (Phase 108 v2.7 block):**
1. `("gym_card_updated", "gym")` — CFG-01 gym card
2. `("working_hours_updated", "settings")` — CFG-02 working hours
3. `("booking_config_updated", "settings")` — CFG-03 booking rules
4. `("notification_prefs_updated", "settings")` — CFG-04 notification matrix

**Audit event count:** 116 (was 112)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed alembic_version VARCHAR(32) truncation**
- **Found during:** Task 3 — `alembic upgrade head` failed at migration 0033 with `StringDataRightTruncationError`
- **Issue:** Alembic's default `alembic_version.version_num` column is `VARCHAR(32)` but project revision IDs like `0033_clients_email_partial_unique` (33 chars) exceed that limit
- **Fix:** Added `version_num_col_type=String(255)` to `env.py context.configure()`. Also executed `ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)` on the dev DB to fix the already-created table
- **Files modified:** `apps/backend/alembic/env.py`
- **Commit:** bfdb2c84

## Verification Results

- `test_rbac_parity` (integration): PASSED — 42 entries on both sides, set equality confirmed
- `test_owner_only_has_exactly_forty_two_entries` (unit): PASSED
- `test_locked_audit_events_has_expected_count` (unit): PASSED — 116 events
- `alembic upgrade head` → `downgrade -2` → `upgrade head`: round-trip CLEAN
- Seed rows confirmed: PKs ...0003/0004/0005 present with correct values
- `gym_info.latitude` / `gym_info.longitude` columns confirmed
- `mypy --strict` on all new/modified backend files: CLEAN

## Known Stubs

None — plan 01 is infrastructure-only (RBAC + audit events + models + migrations). No UI or service callsites.

## Self-Check: PASSED

Files created:
- apps/backend/app/modules/settings/__init__.py: FOUND
- apps/backend/app/modules/settings/models.py: FOUND
- apps/backend/alembic/versions/0070_settings_tables.py: FOUND
- apps/backend/alembic/versions/0071_seed_settings.py: FOUND

Commits:
- f83ef3b7 (Task 1): FOUND
- 8a2e9c4c (Task 2): FOUND
- bfdb2c84 (Task 3): FOUND
