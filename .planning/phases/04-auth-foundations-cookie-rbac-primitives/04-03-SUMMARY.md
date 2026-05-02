---
phase: 04-auth-foundations-cookie-rbac-primitives
plan: "03"
subsystem: database
tags: [sqlalchemy, alembic, postgres, orm, mixins, naming-convention, uuid]

# Dependency graph
requires:
  - phase: 02-backend-skeleton-with-quality-tooling
    provides: Base(DeclarativeBase) in app/core/database.py, lifespan-managed engine/session pattern

provides:
  - NAMING_CONVENTION dict (5-key SA template ix/uq/ck/fk/pk) attached to Base.metadata
  - UUIDPkMixin — gen_random_uuid() server_default PK (PG13+)
  - TimestampMixin — func.now() server_default on insert + onupdate, TIMESTAMPTZ
  - SoftDeleteMixin — deleted_at nullable column; business models add partial WHERE deleted_at IS NULL index

affects:
  - phase-05-user-schema-email-password-auth
  - phase-08-clients-module-audit-log
  - phase-04-plan-09-alembic-clean-smoke

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Base.metadata = MetaData(naming_convention=NAMING_CONVENTION) — naming convention attached at class level before first migration"
    - "Plain mixin classes (not subclassing Base) composed via MRO: class X(Base, UUIDPkMixin, TimestampMixin)"
    - "noqa: N811 on UUID aliases (ruff false-positive for class import aliases)"

key-files:
  created: []
  modified:
    - apps/backend/app/core/database.py

key-decisions:
  - "NAMING_CONVENTION uses verbatim SA standard 5-key template (D-19) — required for Alembic autogenerate empty-diff guarantee in Plan 04-09"
  - "UUIDPkMixin.id uses gen_random_uuid() server_default — no id= on INSERT; RETURNING returns generated UUID (D-15)"
  - "TimestampMixin uses func.now() DB-side for both server_default and onupdate — DB is source of truth for clock, eliminating app-side drift (D-16)"
  - "SoftDeleteMixin does NOT add a plain index on deleted_at — partial index WHERE deleted_at IS NULL belongs on business-specific __table_args__ (D-17)"
  - "Mixins are plain classes not subclassing Base (D-18) — composed via MRO, follows SA 2.0 mixin cookbook"
  - "noqa: N811 added to UUID import aliases (ruff N811 fires on class aliases that look like constants)"

patterns-established:
  - "Pattern 1: MetaData naming_convention attached on Base class — every future model's constraints auto-named deterministically"
  - "Pattern 2: Plain mixin composition — class Model(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin)"
  - "Pattern 3: DB-side server_default=func.now() for timestamps — never app-side datetime.utcnow()"

requirements-completed: [INFRA-01, INFRA-02]

# Metrics
duration: 3min
completed: 2026-05-02
---

# Phase 04 Plan 03: Database Foundation Summary

**`MetaData(naming_convention=...)` attached to `Base` + `UUIDPkMixin`/`TimestampMixin`/`SoftDeleteMixin` shipped for Postgres-native UUID PKs, DB-clock timestamps, and soft-delete column composition**

## Performance

- **Duration:** 3 min
- **Started:** 2026-05-02T06:38:38Z
- **Completed:** 2026-05-02T06:41:38Z
- **Tasks:** 1 of 1
- **Files modified:** 1

## Accomplishments

- `NAMING_CONVENTION` dict (5-key SA template) attached to `Base.metadata` — Alembic autogenerate will emit deterministic constraint names from this point forward; Plan 04-09 alembic-clean smoke becomes runnable
- `UUIDPkMixin` ships `gen_random_uuid()` as `server_default` on a `PgUUID(as_uuid=True)` primary key — no pgcrypto needed (PG13+, project pins PG16)
- `TimestampMixin` ships `created_at` and `updated_at` as `DateTime(timezone=True)` with `server_default=func.now()` and `onupdate=func.now()` — DB is the authoritative clock
- `SoftDeleteMixin` ships `deleted_at` nullable `DateTime(timezone=True)` with no plain index; docstring documents the partial-index contract for Phase 8 Client model
- `db_lifespan`, `get_db`, and existing `Base` inheritance preserved verbatim; `alembic/env.py` required zero changes (already reads `Base.metadata`)

## Task Commits

1. **Task 1: Attach naming_convention to Base + add 3 ORM mixins** - `6e8f9d4` (feat)

## Files Created/Modified

- `apps/backend/app/core/database.py` — Extended from 48 lines to 134 lines: added `NAMING_CONVENTION` dict, `metadata = MetaData(naming_convention=NAMING_CONVENTION)` on `Base`, plus `UUIDPkMixin`, `TimestampMixin`, `SoftDeleteMixin` mixin classes before existing `db_lifespan`/`get_db`

## Decisions Made

- `noqa: N811` added on `from uuid import UUID as UUIDType` and `from sqlalchemy.dialects.postgresql import UUID as PgUUID` — ruff N811 fires because both source names look like ALL_CAPS constants; these are genuinely classes and the aliases are correct PascalCase. This is an established pattern for disambiguating stdlib `uuid.UUID` from SQLAlchemy's `postgresql.UUID` dialect type.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added `noqa: N811` to UUID import aliases**
- **Found during:** Task 1 (acceptance criteria: `ruff check` must exit 0)
- **Issue:** `ruff check` reported N811 ("Constant imported as non-constant") on `UUID as UUIDType` and `UUID as PgUUID` — both source names are ALL_CAPS-looking but are actually class types; the aliases are valid PascalCase class names
- **Fix:** Added `# noqa: N811` to both import lines; the plan's code template did not include these suppressions but ruff enforcement requires them
- **Files modified:** `apps/backend/app/core/database.py`
- **Verification:** `uv run ruff check app/core/database.py` exits 0; `uv run mypy app/core/database.py` still exits 0
- **Committed in:** `6e8f9d4` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - ruff compliance)
**Impact on plan:** Minor inline fix for ruff N811 false-positive on class import aliases. No scope creep; no behavior change.

## Issues Encountered

None beyond the ruff N811 fix documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `Base.metadata.naming_convention == NAMING_CONVENTION` assertion passes — Plan 04-09 alembic-clean smoke can now run `alembic check` against a clean DB and expect an empty diff
- Phase 5+ business models can compose `class User(Base, UUIDPkMixin, TimestampMixin)` and `class Client(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin)` with zero changes to `database.py`
- All quality gates GREEN: mypy strict, ruff, lint-imports (3 contracts kept, 0 broken)
- `alembic/env.py` reads `target_metadata = Base.metadata` and picks up the naming convention automatically at import time — no edit required to env.py

## Self-Check: PASSED

- `apps/backend/app/core/database.py` exists: FOUND
- Commit `6e8f9d4` exists: FOUND
- `Base.metadata.naming_convention == NAMING_CONVENTION` assertion: PASSED
- mypy strict: PASSED
- ruff check: PASSED
- lint-imports: PASSED (3 contracts kept, 0 broken)

---
*Phase: 04-auth-foundations-cookie-rbac-primitives*
*Completed: 2026-05-02*
