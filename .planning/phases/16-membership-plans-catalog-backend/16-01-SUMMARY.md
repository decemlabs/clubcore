---
phase: 16-membership-plans-catalog-backend
plan: "01"
subsystem: database
tags: [alembic, sqlalchemy, postgres, migration, orm, membership-plans]

requires:
  - phase: 15-foundations-rbac-audit-taxonomy-helper-hoisting
    provides: Base + UUIDPkMixin + TimestampMixin + SoftDeleteMixin mixins, NAMING_CONVENTION

provides:
  - membership_plans table with 8 columns (id, name, duration_days, price_kopecks, active, created_at, updated_at, deleted_at)
  - Alembic migration 0004_membership_plans (down_revision=0002_clients)
  - MembershipPlan ORM model for downstream plans (schemas, repository, service)
  - Partial-unique expression index uq_membership_plans_name_alive on lower(name) WHERE deleted_at IS NULL
  - CHECK constraints ck_membership_plans_duration_days_positive and ck_membership_plans_price_kopecks_nonneg
  - alembic/env.py extended with model registration and _include_object drift suppression

affects:
  - 16-02 (schemas — consumes MembershipPlan ORM model)
  - 16-03 (repository/service — uses MembershipPlan, constraint name uq_membership_plans_name_alive)
  - 16-04 (router — mounts endpoints consuming the model)
  - 17-membership-instances (FK plan_id ON DELETE RESTRICT references membership_plans.id)

tech-stack:
  added: []
  patterns:
    - "Expression index partial-unique via op.execute + __table_args__ ORM awareness + env.py _include_object suppression"
    - "NAMING_CONVENTION ck suffix expansion: pass short name (duration_days_positive), convention expands to ck_membership_plans_duration_days_positive"

key-files:
  created:
    - apps/backend/app/modules/memberships/models.py
    - apps/backend/alembic/versions/0004_membership_plans.py
  modified:
    - apps/backend/app/modules/memberships/__init__.py
    - apps/backend/alembic/env.py

key-decisions:
  - "CheckConstraint name uses short suffix (duration_days_positive) not full name — NAMING_CONVENTION expands to ck_membership_plans_duration_days_positive"
  - "Expression index uq_membership_plans_name_alive installed via raw op.execute; declared in __table_args__ for ORM awareness; suppressed in env.py _include_object"
  - "Constraint name uq_membership_plans_name_alive is the canonical literal referenced by service.py:_is_plan_name_conflict (D-02)"
  - "No created_by_user_id FK per MEM-PLAN-01 — plans have no creator attribution"

patterns-established:
  - "Expression partial-unique index pattern: op.execute in migration + Index in __table_args__ + env.py skip-tuple extension"
  - "NAMING_CONVENTION ck format: pass constraint_name suffix only, not full prefixed name"

requirements-completed:
  - MEM-PLAN-01
  - MEM-PLAN-02

duration: 7min
completed: 2026-05-07
---

# Phase 16 Plan 01: Membership Plans Storage Layer Summary

**Alembic migration 0004_membership_plans creating membership_plans table with 2 CHECK constraints and partial-unique expression index uq_membership_plans_name_alive on lower(name)**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-07T13:26:56Z
- **Completed:** 2026-05-07T13:34:17Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created `MembershipPlan` ORM model composed via `Base + UUIDPkMixin + TimestampMixin + SoftDeleteMixin` with all 8 MEM-PLAN-01 columns
- Shipped Alembic migration `0004_membership_plans` (down_revision=`0002_clients`); upgrade and downgrade cycle verified clean
- Partial-unique expression index `uq_membership_plans_name_alive` (`lower(name) WHERE deleted_at IS NULL`) installed via `op.execute` and suppressed in `env.py:_include_object` — `alembic check` reports no spurious drift
- CHECK constraints `ck_membership_plans_duration_days_positive` (duration_days > 0) and `ck_membership_plans_price_kopecks_nonneg` (price_kopecks >= 0) enforced at DB level
- Extended `alembic/env.py` to register `app.modules.memberships.models` and suppress autogenerate drift; all import-linter contracts remain green

## Task Commits

1. **Task 1: Create MembershipPlan ORM model and replace __init__.py placeholder** - `7ec5998` (feat)
2. **Task 2: Create Alembic migration 0004_membership_plans and extend env.py** - `d59a249` (feat)

**Plan metadata:** (committed with SUMMARY.md)

## Files Created/Modified

- `apps/backend/app/modules/memberships/models.py` — MembershipPlan ORM with mixin composition, CHECK constraints, expression partial-unique in __table_args__
- `apps/backend/alembic/versions/0004_membership_plans.py` — Forward/backward compatible DDL migration; expression index via op.execute
- `apps/backend/app/modules/memberships/__init__.py` — Replaced placeholder with Phase 16 module docstring
- `apps/backend/alembic/env.py` — Added memberships model import; added uq_membership_plans_name_alive to _include_object skip-tuple

## Key Constraints Installed

| Constraint | Type | Expression |
|-----------|------|-----------|
| `ck_membership_plans_duration_days_positive` | CHECK | `duration_days > 0` |
| `ck_membership_plans_price_kopecks_nonneg` | CHECK | `price_kopecks >= 0` |
| `uq_membership_plans_name_alive` | UNIQUE INDEX | `lower(name) WHERE deleted_at IS NULL` |
| `pk_membership_plans` | PRIMARY KEY | `id` |

## Decisions Made

- **NAMING_CONVENTION nuance:** `CheckConstraint` `name=` accepts the suffix portion only (`"duration_days_positive"`), not the full prefixed name. The convention template `ck_%(table_name)s_%(constraint_name)s` expands it to `ck_membership_plans_duration_days_positive`. Passing the full prefixed name causes double-prefixing (mirroring the pre-existing behavior in `clients/models.py:Client` which also has the double-prefix quirk for ck_clients_gender but works identically at the migration layer via `op.f()`).
- **Canonical constraint name:** `uq_membership_plans_name_alive` is documented in the migration comment as the literal string consumed by `service.py:_is_plan_name_conflict` (D-02). Plan 03 must use this exact string.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] CheckConstraint name suffix vs full name**
- **Found during:** Task 1 (ORM model creation)
- **Issue:** Plan template showed `name="ck_membership_plans_duration_days_positive"` in `__table_args__`. With `NAMING_CONVENTION` active, passing the full prefixed name results in `ck_membership_plans_ck_membership_plans_duration_days_positive` (double-prefix). The plan's Python verification `c.name == 'ck_membership_plans_duration_days_positive'` would fail.
- **Fix:** Changed `CheckConstraint(name="ck_membership_plans_duration_days_positive")` to `CheckConstraint(name="duration_days_positive")` with a comment explaining the expansion. The migration uses `name=op.f("ck_membership_plans_duration_days_positive")` which bypasses the naming convention and uses the literal canonical name — no migration change needed.
- **Files modified:** `apps/backend/app/modules/memberships/models.py`
- **Verification:** `uv run python -c "from app.modules.memberships.models import MembershipPlan; assert any(c.name == 'ck_membership_plans_duration_days_positive' for c in MembershipPlan.__table_args__ if hasattr(c,'name')); print('OK')"` passes
- **Committed in:** `7ec5998` (Task 1 commit)

**2. [Rule 1 - Bug] Ruff import sorting and unused noqa in env.py**
- **Found during:** Task 2 (env.py and migration file creation)
- **Issue:** Migration file `0004_membership_plans.py` had import ordering issue (I001); env.py had spurious `# noqa: F401` on memberships model import (RUF100 unused directive).
- **Fix:** Applied `uv run ruff check --fix` to auto-sort migration imports; removed `# noqa: F401` from env.py memberships import line.
- **Files modified:** `apps/backend/alembic/versions/0004_membership_plans.py`, `apps/backend/alembic/env.py`
- **Verification:** `uv run ruff check alembic/` exits 0
- **Committed in:** `d59a249` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs)
**Impact on plan:** Both fixes required for correctness (constraint name resolution) and lint hygiene. No scope creep.

## Issues Encountered

- Docker was not running at Task 2 migration verification. Docker Desktop was launched automatically, Postgres container started via `docker compose up -d postgres`, and the migration verified successfully. No user intervention required.

## Known Stubs

None — this plan creates DDL only (table + index + constraints). No data-layer stubs.

## Threat Flags

None — DDL-only plan. No new network endpoints, auth paths, file access, or data-flow trust boundaries. T-16-01-01 through T-16-01-05 mitigations are satisfied as verified.

## Next Phase Readiness

- `MembershipPlan` ORM model is importable; all 8 columns verified via `__table__.c.keys()`
- `uq_membership_plans_name_alive` is the canonical constraint name for `service.py:_is_plan_name_conflict` (Plan 03 / D-02)
- `alembic check` is clean — Plan 02 can proceed without autogenerate noise
- Plan 02 (schemas) can import `MembershipPlan` and `MembershipPlanResponse` as output type

---
*Phase: 16-membership-plans-catalog-backend*
*Completed: 2026-05-07*

## Self-Check: PASSED

- FOUND: apps/backend/app/modules/memberships/models.py
- FOUND: apps/backend/app/modules/memberships/__init__.py
- FOUND: apps/backend/alembic/versions/0004_membership_plans.py
- FOUND: .planning/phases/16-membership-plans-catalog-backend/16-01-SUMMARY.md
- FOUND: commit 7ec5998 (Task 1 — ORM model)
- FOUND: commit d59a249 (Task 2 — migration + env.py)
