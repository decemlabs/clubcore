---
phase: 86-gym-info-cms
plan: "01"
subsystem: backend-gym-module
tags: [gym-info, singleton, permissions, rbac-parity, alembic, jsonb]
dependency_graph:
  requires: []
  provides:
    - GymInfo ORM singleton model
    - GymInfoResponse + GymInfoUpdateRequest DTOs
    - get_singleton + upsert_singleton repository
    - get_gym_info + update_gym_info service
    - Resource.GYM + OWNER_ONLY (EDIT, GYM)
    - frontend RBAC parity mirror (can.ts + registry.ts)
    - migrations 0058 (DDL) + 0059 (idempotent seed)
  affects:
    - apps/backend/app/core/permissions.py
    - apps/admin-web/src/shared/session/can.ts
    - apps/admin-web/src/shared/session/registry.ts
    - apps/backend/alembic/env.py
tech_stack:
  added: []
  patterns:
    - GymInfo singleton ORM (Base+UUIDPkMixin+TimestampMixin, no SoftDeleteMixin)
    - D-03 caller-owns-txn (flush+commit in service, not repository)
    - ON CONFLICT (id) DO NOTHING idempotent seed with deterministic UUID PK
    - CAST(:param AS type) for asyncpg bind-param type compatibility
key_files:
  created:
    - apps/backend/app/modules/gym/__init__.py
    - apps/backend/app/modules/gym/models.py
    - apps/backend/app/modules/gym/schemas.py
    - apps/backend/app/modules/gym/repository.py
    - apps/backend/app/modules/gym/service.py
    - apps/backend/alembic/versions/0058_gym_info.py
    - apps/backend/alembic/versions/0059_seed_gym_info.py
  modified:
    - apps/backend/app/core/permissions.py
    - apps/backend/tests/unit/test_permissions.py
    - apps/backend/tests/integration/test_rbac_parity.py
    - apps/admin-web/src/shared/session/registry.ts
    - apps/admin-web/src/shared/session/can.ts
    - apps/backend/alembic/env.py
decisions:
  - "D-86-CAST: asyncpg send all bind params as VARCHAR; CAST(:id AS uuid) and CAST(:param AS jsonb) required in seed migration (not :param::type shorthand — SQLAlchemy bindparams cannot parse ::cast suffix)"
  - "D-86-SEED-NO-AUDIT: no audit emit on singleton upsert — gym-info is owner-only configuration content, not a business event; rationale documented in service.py docstring"
  - "D-86-SINGLETON-DEF: GymInfoNotFoundError subclasses NotFoundError directly (not a separate AppError subclass hierarchy) for code consistency with existing 404 errors"
metrics:
  duration: ~25 minutes
  completed_date: "2026-06-06"
  tasks_completed: 2
  tasks_total: 2
  files_created: 7
  files_modified: 6
---

# Phase 86 Plan 01: GymInfo Module Foundation Summary

GymInfo singleton ORM + DTOs + repository/service + Resource.GYM permission (owner-only EDIT) + frontend RBAC parity mirror + migrations 0058 (DDL) + 0059 (idempotent baseline seed).

## What Was Built

**Backend gym module** (`apps/backend/app/modules/gym/`):
- `models.py`: `GymInfo(Base, UUIDPkMixin, TimestampMixin)` — singleton table `gym_info` with scalar Text cols (name/address NOT NULL, tagline/city/metro/phone/email NULL) and four `Mapped[list[Any]]` JSONB cols (hours/amenities/rules/social, server_default `'[]'::jsonb`). No SoftDeleteMixin — singleton cannot be deleted.
- `schemas.py`: `GymInfoResponse(ResponseData)` (camelCase wire) and `GymInfoUpdateRequest(BackendSchemaBase)` (partial upsert, extra='forbid', scalar fields capped at max_length=255 per T-86-03).
- `repository.py`: `get_singleton` + `upsert_singleton` — D-03 caller-owns-txn (no flush/commit here). Defensive guard: constructs new GymInfo if seed row missing.
- `service.py`: `get_gym_info` (raises `GymInfoNotFoundError` 404 on missing seed) + `update_gym_info` (upsert → flush → commit → model_validate).

**Permissions** (`apps/backend/app/core/permissions.py`):
- Added `Resource.GYM = "gym"` to StrEnum.
- Added `(Action.EDIT, Resource.GYM)` to OWNER_ONLY frozenset (count 40 → 41).

**Tests updated**:
- `test_permissions.py`: count bump 40→41, added `(Action.EDIT, Resource.GYM)` to expected frozenset, updated resource value set to include "gym".
- `test_rbac_parity.py`: bumped `test_owner_only_count_is_forty` from 40 to 41 on BOTH backend and frontend assertions.

**Frontend RBAC parity mirror**:
- `registry.ts`: appended `| 'gym' // NEW Phase 86 GYM-02 — mirror Resource.GYM.value; owner-only gym-info write`.
- `can.ts`: appended `{ action: 'edit', resource: 'gym' }` under `// v2.4 (Phase 86 GYM-02 ...)` comment block.

**Alembic migrations**:
- `0058_gym_info.py`: DDL migration creating `gym_info` table (down_revision: 0057_payment_notifications_widen_kind).
- `0059_seed_gym_info.py`: Idempotent seed with Тверская baseline content (ON CONFLICT (id) DO NOTHING, deterministic PK `00000000-0000-0000-0000-000000000001`).
- `alembic/env.py`: registered `app.modules.gym.models`; `alembic check` clean (no autogenerate drift).

## Verification Results

- `pytest tests/unit/test_permissions.py tests/integration/test_rbac_parity.py -q`: 279 passed
- `mypy --strict app/modules/gym`: no issues found (5 source files)
- `alembic upgrade head` (first run): applied 0058 + 0059 successfully
- `alembic upgrade head` (second run): no-op (idempotency verified)
- `alembic check`: "No new upgrade operations detected"

## Commits

- `e39c8131`: feat(86-01): GymInfo module — model, schemas, repository, service, Resource.GYM + RBAC parity mirror
- `42c81992`: feat(86-01): migrations 0058 (gym_info DDL) + 0059 (idempotent baseline seed) + env.py

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] asyncpg bind-param type incompatibility in seed migration**
- **Found during:** Task 2 — first alembic upgrade attempt
- **Issue:** SQLAlchemy `sa.text().bindparams()` cannot parse the PostgreSQL `::cast` shorthand (`:param::jsonb`), raising `ArgumentError`. The asyncpg driver also sends all bind params as VARCHAR, causing `DatatypeMismatchError` on the UUID column.
- **Fix:** Used `CAST(:param AS jsonb)` for JSONB columns and `CAST(:id AS uuid)` for the UUID PK. Added explanatory comment in migration docstring.
- **Files modified:** `apps/backend/alembic/versions/0059_seed_gym_info.py`
- **Commit:** 42c81992

**2. [Rule 1 - Bug] mypy strict `no-any-return` on repository.get_singleton**
- **Found during:** Task 1 mypy verification
- **Issue:** `session.scalar()` returns `Any`; without an explicit type annotation the return type was inferred as `Any`, violating `--strict`.
- **Fix:** Added `result: GymInfo | None = await session.scalar(stmt)` explicit annotation.
- **Files modified:** `apps/backend/app/modules/gym/repository.py`
- **Commit:** e39c8131

## Known Stubs

None — all required files are fully implemented. The gym module provides data + authorization layer that Plan 02's router will consume; no stub patterns present.

## Threat Flags

None — no new network endpoints or auth paths introduced in this plan (Plan 02 adds the router).

## Self-Check: PASSED

- [x] `apps/backend/app/modules/gym/__init__.py` exists
- [x] `apps/backend/app/modules/gym/models.py` exists (class GymInfo)
- [x] `apps/backend/app/modules/gym/schemas.py` exists (GymInfoResponse + GymInfoUpdateRequest)
- [x] `apps/backend/app/modules/gym/repository.py` exists (get_singleton + upsert_singleton)
- [x] `apps/backend/app/modules/gym/service.py` exists (get_gym_info + update_gym_info)
- [x] `apps/backend/alembic/versions/0058_gym_info.py` exists
- [x] `apps/backend/alembic/versions/0059_seed_gym_info.py` exists
- [x] Commits e39c8131 and 42c81992 verified in git log
- [x] All 279 permission + parity tests green
- [x] mypy --strict app/modules/gym: no issues
- [x] alembic upgrade head idempotent (second run = no-op)
- [x] alembic check: no autogenerate drift
