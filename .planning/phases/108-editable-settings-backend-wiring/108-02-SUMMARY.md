---
phase: 108-editable-settings-backend-wiring
plan: "02"
subsystem: backend
tags: [settings, rbac, audit, endpoints, gym, csrf]
dependency_graph:
  requires:
    - "108-01 (RBAC pair, audit events, ORM models, migrations)"
  provides:
    - "GET + PUT /api/v1/settings/hours (CFG-02)"
    - "GET + PUT /api/v1/settings/booking (CFG-03)"
    - "GET + PUT /api/v1/settings/notifications (CFG-04)"
    - "GET /api/v1/gym staff-side (CFG-01 form pre-population)"
    - "GymInfoResponse lat/lng fields (CFG-01)"
    - "gym_card_updated audit emit in gym service (CFG-01)"
    - "settings schemas / repository / service layers"
    - "28-test integration suite for all four settings domains"
  affects:
    - apps/backend/app/modules/settings/schemas.py
    - apps/backend/app/modules/settings/repository.py
    - apps/backend/app/modules/settings/service.py
    - apps/backend/app/modules/settings/router.py
    - apps/backend/app/modules/gym/router.py
    - apps/backend/app/modules/gym/schemas.py
    - apps/backend/app/modules/gym/service.py
    - apps/backend/app/api/v1/router.py
tech_stack:
  added: []
  patterns:
    - "Singleton GET+PUT endpoint pair (mirrors gym/router.py GYM-02 pattern)"
    - "RBAC-04 ordering: require_permission BEFORE verify_csrf on all PUTs"
    - "Caller-owns-txn: flush + commit in service layer, not repository"
    - "LOCKED audit event emission in service (all three settings + gym update)"
    - "extra='forbid' + Field bounds for T-108-05 input validation"
    - "HH:MM pattern validator via @field_validator (quiet_hours)"
    - "schedule_step_minutes enum validator {15,30,60,90}"
key_files:
  created:
    - apps/backend/app/modules/settings/schemas.py
    - apps/backend/app/modules/settings/repository.py
    - apps/backend/app/modules/settings/service.py
    - apps/backend/app/modules/settings/router.py
    - apps/backend/tests/integration/test_settings_endpoints.py
  modified:
    - apps/backend/app/modules/gym/router.py
    - apps/backend/app/modules/gym/schemas.py
    - apps/backend/app/modules/gym/service.py
    - apps/backend/app/api/v1/router.py
decisions:
  - "D-108-02-GYM-EDIT-GATE: Staff GET /api/v1/gym gated on require_permission(EDIT, GYM) per CONTEXT line 36 — reception sees 403 on both GET and PUT (gym card fully owner-scoped; no separate VIEW gate)"
  - "D-108-02-SCHEDULE-STEP-ENUM: schedule_step_minutes validated via @field_validator to {15,30,60,90} (not ge/le bounds) because valid values are a discrete set, not a continuous range"
  - "D-108-02-AUDIT-PAYLOAD: audit.emit payload uses changed_fields=[list of keys] pattern (matches referral service pattern; human-readable set of mutated fields)"
metrics:
  duration: "~35 minutes"
  completed: "2026-06-14"
  tasks_completed: 3
  tasks_total: 3
  files_created: 5
  files_modified: 4
---

# Phase 108 Plan 02: Settings Endpoints + Staff Gym GET Summary

Settings persistence endpoints for CFG-02/03/04 landed; staff-side gym GET added for CFG-01 form pre-population; lat/lng fields wired to GymInfo; gym_card_updated audit emitted; 28 integration tests green covering RBAC/round-trip/audit/validation/CSRF.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Settings schemas + repository + service (CFG-02/03/04) | c1a05645 | schemas.py, repository.py, service.py |
| 2 | Settings router + staff gym GET + lat/lng + router registration | 84bb77cc | settings/router.py, gym/router.py, gym/schemas.py, gym/service.py, api/v1/router.py |
| 3 | Endpoint integration tests (RBAC + persistence + validation) | 9f81c810 | test_settings_endpoints.py |

## Endpoint Catalog

### Settings endpoints (all owner-only)

| Method | Path | Operation ID | Gate |
|--------|------|--------------|------|
| GET | /api/v1/settings/hours | owner_get_working_hours | require_permission(VIEW, SETTINGS) |
| PUT | /api/v1/settings/hours | owner_update_working_hours | require_permission(EDIT, SETTINGS) + verify_csrf |
| GET | /api/v1/settings/booking | owner_get_booking_config | require_permission(VIEW, SETTINGS) |
| PUT | /api/v1/settings/booking | owner_update_booking_config | require_permission(EDIT, SETTINGS) + verify_csrf |
| GET | /api/v1/settings/notifications | owner_get_notification_prefs | require_permission(VIEW, SETTINGS) |
| PUT | /api/v1/settings/notifications | owner_update_notification_prefs | require_permission(EDIT, SETTINGS) + verify_csrf |

### Gym endpoint (staff-side)

| Method | Path | Operation ID | Gate |
|--------|------|--------------|------|
| GET | /api/v1/gym | owner_get_gym_info | require_permission(EDIT, Resource.GYM) — reception 403 |
| PUT | /api/v1/gym | owner_update_gym_info | require_permission(EDIT, Resource.GYM) + verify_csrf |

**Staff gym GET note:** EDIT gate (not VIEW) is intentional per CONTEXT line 36 — the gym card is owner-only end to end. Reception sees 403 on both GET and PUT.

## Request Schema Bounds (T-108-05)

### WorkingHoursUpdateRequest
- `schedule`, `breaks`, `closures`: `list[Any] | None` — passthrough JSONB arrays
- No numeric bounds — structural validation deferred to frontend (UI-SPEC)

### BookingConfigUpdateRequest
| Field | Constraint |
|-------|-----------|
| `schedule_step_minutes` | One of {15, 30, 60, 90} via @field_validator |
| `booking_ahead_days` | `ge=1, le=365` |
| `cutoff_minutes` | `ge=0, le=1440` |
| `cancel_window_hours` | `ge=1` |
| `group_limit` | `ge=1` |
| `waitlist_limit` | `ge=0` |
| `no_show_penalty_kopecks` | `ge=0` |
| All booleans | `bool | None` (optional) |

### NotificationPrefsUpdateRequest
| Field | Constraint |
|-------|-----------|
| `sender_signature` | `max_length=11` (SMS/Telegram sender ID limit) |
| `quiet_hours_start` | `r"^\d{2}:\d{2}$"` via @field_validator |
| `quiet_hours_end` | Same HH:MM pattern |
| `matrix` | `dict[str, Any] | None` — passthrough JSONB object |

### GymInfoUpdateRequest (additive)
| Field | Constraint |
|-------|-----------|
| `latitude` | `ge=-90, le=90` |
| `longitude` | `ge=-180, le=180` |

## Audit Payload Shapes

Each service emits via `audit.emit(session, event, actor_user_id=actor.id, resource_type=..., changed_fields=[...])`.

| Event | resource_type | Payload |
|-------|--------------|---------|
| `gym_card_updated` | `gym` | `changed_fields: list[str]` — names of mutated fields |
| `working_hours_updated` | `settings` | `changed_fields: list[str]` |
| `booking_config_updated` | `settings` | `changed_fields: list[str]` |
| `notification_prefs_updated` | `settings` | `changed_fields: list[str]` |

## RBAC Summary

- GET endpoints on settings: `require_permission(VIEW, SETTINGS)` — already in OWNER_ONLY (Plan 01)
- PUT endpoints on settings: `require_permission(EDIT, SETTINGS)` — added in Plan 01
- Staff gym GET + PUT: `require_permission(EDIT, Resource.GYM)` — existing GYM-02 gate
- Reception → 403 on ALL of the above
- RBAC-04 ordering maintained: `require_permission` BEFORE `verify_csrf` on all PUTs

## Deviations from Plan

None — plan executed exactly as written.

Note: During Task 3 verification, the SeaweedFS S3 service (port 8333) was not running in the local dev stack, causing the `LifespanManager` `ensure_bucket()` call to timeout (pre-existing environment issue, not caused by this plan). Starting the S3 service via `docker compose up -d s3` restored full test functionality. All 28 integration tests passed after the service was running.

## Known Stubs

None — all settings endpoints are fully wired to the DB singletons seeded by migration 0071.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: settings_put_endpoint | apps/backend/app/modules/settings/router.py | New state-changing endpoints at /api/v1/settings/{hours,booking,notifications} — mitigated: RBAC(EDIT,SETTINGS) + CSRF + extra='forbid' + numeric bounds per T-108-05/06/07 |
| threat_flag: gym_staff_read | apps/backend/app/modules/gym/router.py | New read endpoint at GET /api/v1/gym — mitigated: EDIT-gated (reception 403), no new data exposure (same row as existing client/gym) |

## Self-Check: PASSED

Files created:
- apps/backend/app/modules/settings/schemas.py: FOUND
- apps/backend/app/modules/settings/repository.py: FOUND
- apps/backend/app/modules/settings/service.py: FOUND
- apps/backend/app/modules/settings/router.py: FOUND
- apps/backend/tests/integration/test_settings_endpoints.py: FOUND

Commits:
- c1a05645 (Task 1): FOUND
- 84bb77cc (Task 2): FOUND
- 9f81c810 (Task 3): FOUND
