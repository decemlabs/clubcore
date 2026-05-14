---
phase: "31"
plan: "01"
subsystem: "trainers"
tags: [trainers, crud, rbac, audit, migration, fastapi, sqlalchemy]
dependency_graph:
  requires: [phase-30-audit-payloads, phase-29-protocol-slots, phase-28-clients]
  provides: [trainers-module, resolve-trainer-by-id-protocol]
  affects: [audit-log, api-v1-router, openapi-snapshot]
tech_stack:
  added: []
  patterns:
    - Partial UNIQUE index (WHERE deleted_at IS NULL AND phone IS NOT NULL)
    - Protocol slot 4th registration in create_app() + telegram_bot.main()
    - D-31-12 combined PATCH emits two audit events atomically
    - SVC001 commit gate in every service mutation function
    - RBAC-04 ordering: require_permission Depends before verify_csrf Depends
key_files:
  created:
    - apps/backend/alembic/versions/0011_trainers.py
    - apps/backend/app/modules/trainers/models.py
    - apps/backend/app/modules/trainers/schemas.py
    - apps/backend/app/modules/trainers/repository.py
    - apps/backend/app/modules/trainers/service.py
    - apps/backend/app/modules/trainers/router.py
    - apps/backend/tests/integration/trainers/__init__.py
    - apps/backend/tests/integration/trainers/conftest.py
    - apps/backend/tests/integration/trainers/test_trainers_crud.py
    - apps/backend/tests/integration/trainers/test_trainers_audit.py
    - apps/backend/tests/integration/trainers/test_trainers_rbac.py
  modified:
    - apps/backend/alembic/env.py
    - apps/backend/app/modules/trainers/__init__.py
    - apps/backend/app/core/dependencies.py
    - apps/backend/app/core/exceptions.py
    - apps/backend/app/main.py
    - apps/backend/app/workers/telegram_bot.py
    - apps/backend/app/api/v1/router.py
    - apps/backend/openapi.json
decisions:
  - "trainer_id in audit payloads must be str(uuid) not UUID object — JSONB column requires JSON-serializable primitives"
  - "D-31-09: both GET /trainers and GET /trainers?active=true/false allowed for RECEPTION role (VIEW is not in OWNER_ONLY)"
  - "resolve_trainer_by_id Protocol slot returns alive trainer regardless of is_active — caller decides"
  - "alembic env.py must import trainers.models AND exclude uq_trainers_phone_alive from autogenerate to avoid false drift"
metrics:
  duration: "~45 minutes"
  completed: "2026-05-14T13:49:48Z"
  tasks_completed: 3
  files_created: 11
  files_modified: 8
---

# Phase 31 Plan 01: Trainers Module Summary

**One-liner:** Full trainers CRUD module with partial UNIQUE phone index, 4 locked audit events, Protocol slot (4th), RBAC-04-ordered 5-endpoint router, and 31 integration tests covering CRUD/audit/RBAC.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Migration + ORM + Schemas + Repository | ea8ecca | 0011_trainers.py, models.py, schemas.py, repository.py, env.py |
| 2 | Service + Protocol + Router + API mount | 2b7ea83 | service.py, router.py, dependencies.py, exceptions.py, main.py, telegram_bot.py, api/v1/router.py, openapi.json |
| 3 | Integration Tests (CRUD + Audit + RBAC) | 6838b8d | tests/integration/trainers/ (5 files), service.py fix |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] alembic/env.py missing trainers model import**
- **Found during:** Task 1 verification (`alembic check`)
- **Issue:** `alembic check` reported "Detected removed table 'trainers'" because env.py didn't import `app.modules.trainers.models`, preventing autogenerate from seeing the Trainer ORM. Additionally, partial index `uq_trainers_phone_alive` caused false drift detection.
- **Fix:** Added `import app.modules.trainers.models` to env.py; added both partial index names (`uq_trainers_phone_alive`, `uq_clients_phone_alive`) to `_include_object` exclusion list.
- **Files modified:** `alembic/env.py`
- **Commit:** ea8ecca

**2. [Rule 1 - Bug] mypy error in repository.py: Returning Any from function declared to return Trainer | None**
- **Found during:** Task 1 quality gate (mypy)
- **Issue:** `session.scalar()` returns `Any | None`; mypy couldn't infer the concrete `Trainer` return type.
- **Fix:** Added explicit type annotations: `stmt: Select[tuple[Trainer]]` and `result: Trainer | None = await session.scalar(stmt)`.
- **Files modified:** `repository.py`
- **Commit:** ea8ecca

**3. [Rule 1 - Bug] Ruff E501 line-too-long in exceptions.py**
- **Found during:** Task 2 quality gate (ruff)
- **Issue:** `TrainerNotFoundError` docstring exceeded 100-char line limit.
- **Fix:** Shortened docstring removing phase reference.
- **Files modified:** `exceptions.py`
- **Commit:** 2b7ea83

**4. [Rule 1 - Bug] UUID JSON serialization failure in JSONB audit payload**
- **Found during:** Task 3 first integration test run
- **Issue:** `audit.emit()` stores `**payload` kwargs as JSONB. Passing `trainer_id=trainer.id` (Python `UUID` object) caused `TypeError: Object of type UUID is not JSON serializable` from asyncpg.
- **Fix:** Changed all 4 audit emit callsites in service.py from `trainer_id=trainer.id` to `trainer_id=str(trainer.id)`. Pydantic audit payload schema `trainer_id: UUID` accepts string input (coerces to UUID for validation). Tests check `payload["trainer_id"] == str(trainer_id)` which matches correctly.
- **Files modified:** `service.py`
- **Commit:** 6838b8d

## Verification Results

All quality gates passed after fixes:
- `ruff check app/` — All checks passed
- `mypy app/` — No errors (strict mode)
- `lint-imports` — 3 contracts kept, 0 broken
- `pytest tests/ -k svc001` — 10 passed (SVC001 commit gate still enforced)
- `pytest tests/integration/trainers/ -x -q` — 31 passed in 4.00s

## Known Stubs

None. All trainer endpoints return real database data. No placeholder text or hardcoded empty values.

## Threat Flags

None. The `/api/v1/trainers` endpoints introduced here follow the same auth + RBAC + CSRF pattern already established for `/api/v1/clients`. No new trust boundaries. Phone field is validated with E.164 regex before storage.

## Self-Check: PASSED

- ea8ecca exists in git log: FOUND
- 2b7ea83 exists in git log: FOUND
- 6838b8d exists in git log: FOUND
- apps/backend/alembic/versions/0011_trainers.py: FOUND
- apps/backend/app/modules/trainers/models.py: FOUND
- apps/backend/app/modules/trainers/service.py: FOUND
- apps/backend/app/modules/trainers/router.py: FOUND
- apps/backend/tests/integration/trainers/test_trainers_crud.py: FOUND
- apps/backend/tests/integration/trainers/test_trainers_audit.py: FOUND
- apps/backend/tests/integration/trainers/test_trainers_rbac.py: FOUND
