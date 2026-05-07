---
phase: 19-visits-db-reception-check-in-backend
plan: "01"
subsystem: backend-visits-foundation
tags:
  - alembic-migration
  - sqlalchemy-computed
  - pydantic-schemas
  - domain-exceptions
  - config-settings
  - audit-reconciliation
dependency_graph:
  requires:
    - 17-membership-instances-resolver-backend (Membership ORM, 0005_memberships migration)
    - 15-foundations-rbac-audit-taxonomy-helper-hoisting (BackendSchemaBase, LOCKED_AUDIT_EVENTS)
  provides:
    - Visit ORM with STORED GENERATED gym_date column
    - 0006_visits migration (BLOCKED: not yet applied, Plan 19-04 owns upgrade head)
    - VisitCreateRequest, VisitResponse, VisitListQuery schemas
    - 5 new exception classes (NoActiveMembershipError, DuplicateCheckinError,
      OutsideGymHoursError, VisitNotFoundError, ClientNotLinkedError)
    - Settings.gym_hours_start/end + midnight-spanning validator
    - audit.py:46-49 docstring reconciled against CONTEXT D-16
  affects:
    - apps/backend/app/core/exceptions.py (new visit exceptions)
    - apps/backend/app/core/config.py (gym_hours fields)
    - apps/backend/app/core/audit.py (docstring fix, LOCKED_AUDIT_EVENTS unchanged)
tech_stack:
  added:
    - SQLAlchemy Computed() with persisted=True (STORED GENERATED column — first in project)
    - Pydantic v2 time type in Settings (native env string parsing)
    - model_validator(mode='after') on Settings (first cross-field validator on Settings)
  patterns:
    - STORED GENERATED column for race-proof 1/day enforcement (Pitfall 5 mitigation)
    - BackendSchemaBase sealed POST body (extra='forbid', client_id only)
    - Exception hierarchy extending ConflictError/NotFoundError with exact codes
    - Pydantic v2 field alias 'from' → from_ to avoid keyword collision
key_files:
  created:
    - apps/backend/alembic/versions/0006_visits.py
    - apps/backend/app/modules/visits/models.py
    - apps/backend/app/modules/visits/schemas.py
  modified:
    - apps/backend/app/modules/visits/__init__.py (placeholder → module docstring)
    - apps/backend/app/core/exceptions.py (5 new exception classes appended)
    - apps/backend/app/core/config.py (gym_hours fields + model_validator)
    - apps/backend/app/core/audit.py (docstring lines 46-49 reconciled)
    - apps/backend/.env.example (GYM_HOURS_START/END section added)
decisions:
  - "STORED GENERATED gym_date via Computed(..., persisted=True) — app NEVER writes it (D-06)"
  - "UNIQUE constraint uq_visits_client_id_gym_date is unconditional (no WHERE partial, CD-04)"
  - "VisitCreateRequest sealed to {clientId} only; extra='forbid' rejects tampering (D-01)"
  - "VisitListQuery: no sort enum, fixed checked_in_at DESC server-side (D-09)"
  - "gym_hours model_validator rejects midnight-spanning ranges in v1.2 (D-11)"
  - "audit.py docstring reconciled to D-16: visit_id in resource_id, not payload"
metrics:
  duration: "~12 minutes"
  completed: "2026-05-07"
  tasks_completed: 3
  files_changed: 8
---

# Phase 19 Plan 01: Visits Foundation — Migration + ORM + Schemas + Exceptions + Config Summary

**One-liner:** Alembic migration 0006_visits with STORED GENERATED gym_date + UNIQUE (client_id, gym_date), Visit ORM with Computed, sealed BackendSchemaBase schemas, 5 typed exception classes, and gym_hours Settings with midnight-spanning model_validator.

## What Was Built

### Task 1: Migration 0006_visits + Visit ORM + visits package init

**Migration `apps/backend/alembic/versions/0006_visits.py`:**
- Revision ID: `0006_visits`, down_revision: `0005_memberships`
- Creates `visits` table with all VIS-01 columns
- `gym_date DATE GENERATED ALWAYS AS ((checked_in_at AT TIME ZONE 'Europe/Moscow')::date) STORED` via `sa.Computed(..., persisted=True)` — the headline structural decision (Pitfall 5 mitigation)
- UNIQUE constraint `uq_visits_client_id_gym_date` (client_id, gym_date) — unconditional (no partial WHERE; CD-04 no soft-delete)
- 3 ForeignKeyConstraints: `fk_visits_client_id_clients` (RESTRICT), `fk_visits_membership_id_memberships` (RESTRICT), `fk_visits_checked_in_by_users` (SET NULL)
- CHECK constraint `ck_visits_channel` on `channel IN ('reception', 'telegram_bot')`
- Composite index `ix_visits_client_id_checked_in_at` via raw `op.execute("CREATE INDEX ... ON visits (client_id, checked_in_at DESC)")` (mirrors Phase 17 pattern for DESC ordering)
- **Migration NOT yet applied** — Plan 19-04 owns the BLOCKING `alembic upgrade head`

**ORM `apps/backend/app/modules/visits/models.py`:**
- `class Visit(Base, UUIDPkMixin, TimestampMixin)` — NO SoftDeleteMixin (CD-04)
- `gym_date: Mapped[date]` with `Computed("(checked_in_at AT TIME ZONE 'Europe/Moscow')::date", persisted=True)` — identical expression literal to migration so SA autogenerate stays in sync
- `__table_args__` mirrors migration: CheckConstraint, UniqueConstraint (`uq_visits_client_id_gym_date`), Index with `text("checked_in_at DESC")`

**`apps/backend/app/modules/visits/__init__.py`:** placeholder replaced with module docstring.

### Task 2: visits/schemas.py

Three Pydantic v2 classes, all inheriting transitively from `BackendSchemaBase`:

- **`VisitCreateRequest(BackendSchemaBase)`** — `client_id: UUID` only. `extra='forbid'` (inherited) rejects any extra field with 422. Server derives: membership_id, checked_in_at, gym_date, channel, checked_in_by.
- **`VisitResponse(BackendSchemaBase)`** — `from_attributes=True` merged into model_config for `model_validate(visit_orm)`. Fields: id, client_id, membership_id, checked_in_at, gym_date, channel, checked_in_by, created_at.
- **`VisitListQuery(PageQuery)`** — `client_id: UUID | None`, `from_: date | None = Field(alias="from")` (Python keyword avoidance), `to: date | None`. No sort enum (D-09 fixed `checked_in_at DESC`).

### Task 3: Exceptions + Config + Audit + .env.example

**5 new exception classes in `apps/backend/app/core/exceptions.py`:**

| Class | Base | status_code | code |
|-------|------|-------------|------|
| `NoActiveMembershipError` | `ConflictError` | 409 | `no_active_membership` |
| `DuplicateCheckinError` | `ConflictError` | 409 | `duplicate_checkin` |
| `OutsideGymHoursError` | `ConflictError` | 409 | `outside_gym_hours` |
| `VisitNotFoundError` | `NotFoundError` | 404 | `visit_not_found` |
| `ClientNotLinkedError` | `NotFoundError` | 404 | `client_not_linked` |

**`apps/backend/app/core/config.py:Settings` additions (VIS-05):**
- `gym_hours_start: time = time(7, 0)` — Pydantic v2 parses `"07:00"` env string natively
- `gym_hours_end: time = time(23, 0)`
- `@model_validator(mode="after") def _gym_hours_range_invariant` — rejects `gym_hours_end <= gym_hours_start` with ValueError (D-11 no midnight-spanning in v1.2)

**`apps/backend/.env.example`:** Added section:
```
# Visits — gym hours window (Europe/Moscow)
GYM_HOURS_START=07:00
GYM_HOURS_END=23:00
```

**`apps/backend/app/core/audit.py` docstring reconciliation (D-16):**
- Lines 46-49 updated: `visit_created` payload is `{client_id, membership_id, channel}` with `[resource_id=visit.id]` annotation (visit_id NOT in payload — mirrors membership_created precedent where membership_id lives in resource_id)
- `visit_rejected_outside_hours` now documents `current_local_time, gym_open, gym_close` payload keys
- `LOCKED_AUDIT_EVENTS` frozenset at lines 111-114: **UNCHANGED** (docstring-only edit)

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | 7846444 | feat(19-01): 0006_visits migration + Visit ORM + visits package init |
| Task 2 | c953ee8 | feat(19-01): visits/schemas.py — sealed VisitCreateRequest + VisitResponse + VisitListQuery |
| Task 3 | 02e2a82 | feat(19-01): 5 visit exceptions + gym_hours settings + audit docstring fix + .env.example |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SoftDeleteMixin string in models.py docstring causing grep check failure**
- **Found during:** Task 1 verification
- **Issue:** Docstring said "NO SoftDeleteMixin" — the grep -c check for 0 occurrences would fail because `grep` finds it in the docstring
- **Fix:** Rephrased docstring to "soft-delete mixin is intentionally excluded" without the exact import name string
- **Files modified:** apps/backend/app/modules/visits/models.py

**2. [Rule 1 - Bug] audit.py docstring lines > 100 chars (ruff E501)**
- **Found during:** Task 3 verification
- **Issue:** D-16 docstring alignment with `[resource_id=...]` annotations exceeded 100 char limit
- **Fix:** Shortened inline alignment to fit within 100 chars while preserving all D-16 information
- **Files modified:** apps/backend/app/core/audit.py

## Known Stubs

None. All Plan 19-01 artifacts are structural definitions (ORM, migration, schemas, exceptions, config). No data flows to UI in this plan — service, router, and tests are Plans 19-02, 19-03, 19-04, 19-05.

## Threat Flags

None. All threat mitigations from the plan's threat register are implemented:
- T-19-01-01 (Tampering/POST body): `VisitCreateRequest(BackendSchemaBase)` with `client_id` only; `extra='forbid'` inherited
- T-19-01-02 (Tampering/gym_date): `Computed(..., persisted=True)` — app cannot write the column
- T-19-01-03 (Config drift): `_gym_hours_range_invariant` model_validator rejects boot-time misconfiguration
- T-19-01-05 (Repudiation/audit drift): docstring reconciled against D-16; LOCKED_AUDIT_EVENTS frozenset unchanged

## Self-Check: PASSED

All created files exist on disk. All task commits verified in git history:
- 7846444: Migration + ORM + package init
- c953ee8: visits/schemas.py
- 02e2a82: Exceptions + config + audit + .env.example
- 19-01-SUMMARY.md: present at .planning/phases/19-visits-db-reception-check-in-backend/19-01-SUMMARY.md
