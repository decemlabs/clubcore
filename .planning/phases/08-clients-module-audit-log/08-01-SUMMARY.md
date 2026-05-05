---
phase: 08-clients-module-audit-log
plan: 01
subsystem: backend-foundation
tags: [migration, orm, audit, clients, schema]
requirements-completed: [INFRA-04, CLIENTS-01, AUDIT-01]
requires:
  - 0001_auth migration (users table)
  - 0003_telegram_username migration (Phase 7 chain head)
  - app.core.database (Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin)
  - app.core.exceptions (AppError, NotFoundError, ConflictError, ValidationAppError)
provides:
  - app.core.audit_models.AuditLog (D-05)
  - app.modules.clients.models.Client (CLIENTS-01)
  - app.modules.clients.models.Gender (D-15)
  - app.core.exceptions.ClientNotFoundError (404, "client_not_found")
  - app.core.exceptions.PhoneExistsError (409, "phone_exists")
  - app.core.exceptions.InvalidPhoneError (422, "invalid_phone")
  - 0002_clients migration (clients + audit_log + pg_trgm + indexes)
affects:
  - apps/backend/alembic/env.py (registers two new ORM modules with Base.metadata)
  - apps/backend/app/core/exceptions.py (AppError.__init__ message default '')
  - apps/backend/app/modules/clients/__init__.py (docstring updated to module marker)
tech-stack:
  added: []
  patterns:
    - "Partial unique index pattern on phone WHERE deleted_at IS NULL (CLIENTS-02)"
    - "GIN trigram expression indexes via raw op.execute (Pitfall 1)"
    - "String FK to keep core ⊥ modules contract (D-05)"
    - "Linear migration chain: 0001_auth → 0003_telegram_username → 0002_clients"
key-files:
  created:
    - apps/backend/app/core/audit_models.py
    - apps/backend/app/modules/clients/models.py
    - apps/backend/alembic/versions/0002_clients.py
    - .planning/phases/08-clients-module-audit-log/08-01-SUMMARY.md
  modified:
    - apps/backend/alembic/env.py
    - apps/backend/app/core/exceptions.py
    - apps/backend/app/modules/clients/__init__.py
decisions:
  - "down_revision='0003_telegram_username' (not '0001_auth' as plan stated) — Phase 7 telegram_username had already landed ahead of Phase 8 starting; chain stays linear"
  - "Removed 'noqa: F401' from auth/clients side-effect imports in env.py — current ruff version recognises namespace-only imports without F401 suppression (RUF100)"
  - "AppError.__init__ message default '' enables zero-arg instantiation for verification asserts; existing callers still pass strings"
  - "GIN trgm indexes intentionally NOT in Client.__table_args__ — they live only in migration; Plan 08 owns the env.py include_object filter (Pitfall 1, explicit deferral by 08-01-PLAN.md Task 3)"
metrics:
  duration_seconds: 354
  duration_human: "5m 54s"
  completed_at: "2026-05-03T08:47:30Z"
  tasks_completed: 4
  tasks_total: 4
  files_changed: 7
  commits: 4
---

# Phase 8 Plan 01: Clients + Audit Foundation Summary

Phase 8 foundation laid: migration `0002_clients.py` with `pg_trgm` extension + `clients` and `audit_log` tables + partial unique + GIN trgm + btree indexes; `AuditLog` ORM in `app/core/audit_models.py` (cross-cutting, string FK preserves `core ⊥ modules`); `Client` ORM + `Gender(StrEnum)` in `app/modules/clients/models.py` composing UUIDPkMixin/TimestampMixin/SoftDeleteMixin; three new `AppError` subclasses (`ClientNotFoundError`, `PhoneExistsError`, `InvalidPhoneError`).

## What Got Built

### Task 1 — `app/core/audit_models.py` (commit `d5a51c0`)

`AuditLog(Base, UUIDPkMixin)` cross-cutting model:

- `actor_user_id PgUUID NULL` — D-06; FK `users.id ON DELETE RESTRICT` via **string** ref so module is not imported (preserves `core-not-depend-on-modules` import-linter contract).
- `action TEXT NOT NULL`, `resource_type TEXT NOT NULL`.
- `resource_id PgUUID NULL` — D-07; non-UUID identifiers belong in `payload`.
- `payload JSONB NOT NULL DEFAULT '{}'::jsonb` — emitters never need to pass an empty dict.
- `created_at` only, no `updated_at` (audit rows are immutable).
- Btree `ix_audit_log_actor_user_id_created_at` for per-actor history queries.

### Task 2 — `app/modules/clients/models.py` (commit `6c38c72`)

`Gender(StrEnum)` with values `MALE='male'`, `FEMALE='female'` (D-15, closed enum).

`Client(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin)`:

- 14 business columns: name parts (last/first/middle), phone, email, birthday, gender, tags, notes, emergency_contact, telegram_user_id, created_by_user_id.
- `tags TEXT[]` `server_default ARRAY[]::TEXT[]` (D-16, Pitfall 6 — empty list, never NULL).
- `emergency_contact JSONB NULL` (D-17, free-shape).
- `telegram_user_id BIGINT UNIQUE` for bot-binding flow.
- `created_by_user_id` FK `users.id ON DELETE RESTRICT` (operator deletion blocked while their clients exist).
- Partial unique index `uq_clients_phone_alive WHERE deleted_at IS NULL` (CLIENTS-02).
- CHECK `gender IN ('male', 'female')`.
- GIN trgm indexes deliberately absent from `__table_args__` — they live in migration only.

`apps/backend/app/modules/clients/__init__.py` docstring updated to `"""Clients module (Phase 8)."""`.

### Task 3 — `alembic/versions/0002_clients.py` (commit `16bf8eb`)

Migration applies in D-20 order:

1. `CREATE EXTENSION IF NOT EXISTS pg_trgm`
2. `CREATE TABLE clients (...)` with FK / CHECK / UNIQUE constraints inside `op.create_table`.
3. `CREATE UNIQUE INDEX uq_clients_phone_alive ON clients (phone) WHERE deleted_at IS NULL`.
4. `CREATE INDEX ix_clients_last_name_trgm USING gin (lower(last_name) gin_trgm_ops)` (raw DDL).
5. `CREATE INDEX ix_clients_first_name_trgm USING gin (lower(first_name) gin_trgm_ops)` (raw DDL).
6. `CREATE TABLE audit_log (...)` with FK ON DELETE RESTRICT.
7. `CREATE INDEX ix_audit_log_actor_user_id_created_at ON audit_log (actor_user_id, created_at)`.

`downgrade()` reverses in mirror order including `DROP EXTENSION IF EXISTS pg_trgm`.

`alembic/env.py` adds two side-effect imports right after `app.modules.auth.models`:

```python
import app.modules.clients.models
import app.core.audit_models  # noqa: F401
```

(Removed redundant `noqa: F401` from the first two imports — see Deviations.)

**DB verification on docker-compose Postgres:**

- `alembic upgrade head` succeeds (`0003_telegram_username → 0002_clients`).
- `alembic downgrade -1` then `alembic upgrade head` round-trips clean.
- `\dx pg_trgm` shows extension installed (v1.6).
- `\d clients` shows: pk_clients, ix_clients_first_name_trgm (gin), ix_clients_last_name_trgm (gin), uq_clients_phone_alive (partial unique), uq_clients_telegram_user_id, ck_clients_gender, fk_clients_created_by_user_id_users (RESTRICT).
- `\d audit_log` shows: pk_audit_log, ix_audit_log_actor_user_id_created_at, fk_audit_log_actor_user_id_users (RESTRICT).

### Task 4 — three AppError subclasses (commit `7479da0`)

Appended to `apps/backend/app/core/exceptions.py` before `register_exception_handlers`:

| Class                  | Inherits              | Code               | HTTP |
| ---------------------- | --------------------- | ------------------ | ---- |
| `ClientNotFoundError`  | `NotFoundError`       | `client_not_found` | 404  |
| `PhoneExistsError`     | `ConflictError`       | `phone_exists`     | 409  |
| `InvalidPhoneError`    | `ValidationAppError`  | `invalid_phone`    | 422  |

All three ride the existing `_app_error_handler` routing automatically (no handler changes).

`AppError.__init__` `message` parameter now defaults to `""` to allow zero-arg instantiation in verification asserts (e.g. `ClientNotFoundError().status_code == 404`). Existing callers across `app/core/dependencies.py`, `app/core/security.py`, `app/modules/auth/{service,rate_limit,telegram_service}.py` all pass explicit strings — backwards compatible.

## Verification Confirmation

- `alembic upgrade head` — clean apply on docker-compose Postgres
- `alembic downgrade -1 && alembic upgrade head` — round-trip clean
- `ruff check` — All checks passed!
- `mypy --strict app/` — Success: no issues found in 54 source files
- `lint-imports` — Contracts: 3 kept, 0 broken
- `pytest --deselect tests/integration/test_alembic_clean.py` — 202 passed, 2 deselected
- All ORM imports succeed: `from app.core.audit_models import AuditLog; from app.modules.clients.models import Client, Gender; from app.core.exceptions import ClientNotFoundError, PhoneExistsError, InvalidPhoneError`

## Success Criteria Checklist

- [x] INFRA-04 — `0002_clients.py` migration creates pg_trgm + clients + audit_log + indexes + partial unique
- [x] CLIENTS-01 — Client ORM has all 14 columns + composes UUIDPkMixin/TimestampMixin/SoftDeleteMixin
- [x] CLIENTS-02 — partial unique `uq_clients_phone_alive WHERE deleted_at IS NULL` exists in DB after migration
- [x] AUDIT-01 — audit_log table with all six business columns + FK RESTRICT + payload jsonb default exists in DB
- [x] D-05 — AuditLog ORM in `app.core` with string FK; no `from app.modules` import in audit_models.py
- [x] D-06 — `audit_log.actor_user_id` is NULLABLE
- [x] D-07 — `audit_log.resource_id` is `PgUUID NULL`
- [x] D-15 — `Gender(StrEnum)` with `male` / `female` + CHECK constraint at DB level
- [x] D-16 — `clients.tags TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[]`
- [x] D-17 — `clients.emergency_contact JSONB NULL`
- [x] D-20 — single migration with documented order: extension → clients → partial unique → GIN → audit_log → btree
- [x] Three `AppError` subclasses (`ClientNotFoundError`, `PhoneExistsError`, `InvalidPhoneError`) importable

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Migration parent revision adjusted from `0001_auth` to `0003_telegram_username`**

- **Found during:** Task 3
- **Issue:** Plan instructed `down_revision='0001_auth'`, but the migrations directory already contained `0003_telegram_username.py` (Phase 7 chain head) before Phase 8 started. Setting `down_revision='0001_auth'` would fork the migration tree and produce two heads — `alembic upgrade head` would refuse with `Multiple heads`.
- **Fix:** Set `down_revision='0003_telegram_username'`. Migration applied cleanly: `0003_telegram_username → 0002_clients`. Round-trip `downgrade -1 → upgrade head` verified.
- **Files modified:** `apps/backend/alembic/versions/0002_clients.py`
- **Commit:** `16bf8eb`

**2. [Rule 1 - Bug] RUF100 unused-noqa on env.py side-effect imports**

- **Found during:** Task 3 ruff verification
- **Issue:** After adding `import app.modules.clients.models` and `import app.core.audit_models` next to the pre-existing `import app.modules.auth.models  # noqa: F401`, ruff started flagging the first two with RUF100 ("Unused `noqa` directive"). Current ruff understands that `import x.y.z` is a namespace-side-effect import and does not raise F401, so the noqa is genuinely unused.
- **Fix:** Removed `# noqa: F401` from the first two import lines (kept on the third because it's the trailing import — keeping at least one preserves the contract that the comment block above remains anchored). All four code-quality gates clean afterwards.
- **Files modified:** `apps/backend/alembic/env.py`
- **Commit:** `16bf8eb`

**3. [Rule 3 - Blocking] `AppError.__init__` `message` default `""`**

- **Found during:** Task 4 verification
- **Issue:** The plan's verification command instantiates new exceptions without args (`ClientNotFoundError().status_code == 404`). Original signature `def __init__(self, message: str, ...)` would TypeError on missing argument.
- **Fix:** Defaulted `message: str = ""` in `AppError.__init__`. Verified all existing callers (8 files: `app/core/dependencies.py`, `app/core/security.py`, `app/modules/auth/{service,rate_limit,telegram_service}.py`) pass explicit strings, so the default is never observed in production paths.
- **Files modified:** `apps/backend/app/core/exceptions.py`
- **Commit:** `7479da0`

### Authentication Gates

None.

### Architectural Decisions Required

None.

## Known Stubs

None — this plan creates the foundation layer only. Service/repository/router stubs are explicitly owned by Plans 02–07 of Phase 8.

## Deferred Issues

**`tests/integration/test_alembic_clean.py::test_alembic_check_clean`** — Currently fails with:

```
FAILED: New upgrade operations detected:
  ('remove_index', Index('ix_clients_first_name_trgm', ...))
  ('remove_index', Index('ix_clients_last_name_trgm', ...))
```

This is **explicitly anticipated and deferred** by the plan itself (08-01-PLAN.md Task 3 action block, last paragraph): "Plan 08 will install the env.py-level filter `include_object` to skip indexes whose name starts with `ix_clients_`*`_trgm` from autogenerate comparison. **For this task, do NOT touch env.py beyond the two import lines** — the autogenerate-skip is Plan 08's responsibility."

GIN trigram expression indexes (`lower(col) gin_trgm_ops`) cannot be represented in SQLAlchemy `__table_args__` (Pitfall 1), so autogenerate sees them in the DB but not in the metadata and reports drift. Plan 08 of Phase 8 owns the env.py `include_object` filter that suppresses this specific drift. All other 202 backend tests pass.

## Threat Flags

None — all surface introduced by this plan is registered in `<threat_model>` (T-08-01..T-08-07). DB-level enforcement of phone uniqueness (T-08-01), gender enum (T-08-02), audit FK RESTRICT (T-08-03, T-08-06), and core ⊥ modules contract (T-08-04) all verified.

## Self-Check: PASSED

**Files exist:**
- `apps/backend/app/core/audit_models.py` — FOUND
- `apps/backend/app/modules/clients/models.py` — FOUND
- `apps/backend/alembic/versions/0002_clients.py` — FOUND
- `apps/backend/app/core/exceptions.py` — FOUND (modified)
- `apps/backend/alembic/env.py` — FOUND (modified)
- `apps/backend/app/modules/clients/__init__.py` — FOUND (modified)

**Commits exist (verified via `git log --oneline`):**
- `d5a51c0` — Task 1 (AuditLog ORM)
- `6c38c72` — Task 2 (Client ORM + Gender)
- `16bf8eb` — Task 3 (migration + env.py)
- `7479da0` — Task 4 (AppError subclasses)
