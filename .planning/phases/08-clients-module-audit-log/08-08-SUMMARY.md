---
phase: 08-clients-module-audit-log
plan: 08
subsystem: testing
tags: [pytest, integration, audit-log, clients, alembic, rbac, savepoint]

# Dependency graph
requires:
  - phase: 08-clients-module-audit-log
    provides: |
      Plan 08-01 (AuditLog ORM + clients migration with GIN trgm indexes),
      Plan 08-02 (audit.emit co-transactional INSERT signature),
      Plan 08-03 (Pydantic DTOs ClientCreateRequest / ClientUpdateRequest /
      ClientListQuery / ClientResponse / EmergencyContact),
      Plan 08-04 (repository: list_alive / get_alive / insert_client /
      update_client / soft_delete_client),
      Plan 08-06 (service orchestration with D-08 audit payloads + D-09 no-op skip),
      Plan 08-07 (router with require_permission gates + verify_csrf)
provides:
  - "apps/backend/tests/integration/clients/conftest.py — authed_client_owner / authed_client_reception fixtures"
  - "30 new clients integration tests across list / CRUD / RBAC / audit-writes"
  - "6 new auth audit-row assertions extending existing /login /logout /refresh /telegram tests"
  - "alembic env.py include_object filter for raw-DDL GIN trgm indexes (Pitfall 1)"
  - "Pydantic schema-generation fix for PaginatedData[Client] (PEP 563 + model_construct)"
  - "post-flush session.refresh fix for ClientResponse serialisation under async"
  - "CurrentUser Protocol switch in service.py (mypy --strict clean)"
affects: [09-openapi-pipeline, 10-admin-web-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SAVEPOINT-rolled db_session shared across route + test via dependency override (TEST-01 pattern)"
    - "Authed httpx clients per-role with isolated cookie jar + same dependency-override app"
    - "Direct AuditLog row queries via select(AuditLog).where(action == ..., resource_id == ...)"
    - "alembic include_object filter for raw-DDL expression indexes (Pitfall 1)"
    - "PaginatedData.model_construct(...) avoids PydanticSchemaGenerationError on ORM type parametrisation"

key-files:
  created:
    - "apps/backend/tests/integration/clients/__init__.py"
    - "apps/backend/tests/integration/clients/conftest.py"
    - "apps/backend/tests/integration/clients/test_clients_list.py"
    - "apps/backend/tests/integration/clients/test_clients_crud.py"
    - "apps/backend/tests/integration/clients/test_clients_rbac.py"
    - "apps/backend/tests/integration/clients/test_audit_writes.py"
  modified:
    - "apps/backend/alembic/env.py — include_object filter for GIN trgm indexes"
    - "apps/backend/app/modules/clients/repository.py — PEP 563 + model_construct + typed Client local"
    - "apps/backend/app/modules/clients/service.py — CurrentUser Protocol + post-flush refresh"
    - "apps/backend/tests/integration/auth/test_login.py — login_success + login_failed audit assertions"
    - "apps/backend/tests/integration/auth/test_logout.py — session_revoked audit assertion"
    - "apps/backend/tests/integration/auth/test_refresh.py — family_reuse_detected audit assertion"
    - "apps/backend/tests/integration/auth/test_telegram_start.py — telegram_deep_link_issued audit assertion"
    - "apps/backend/tests/integration/auth/test_telegram_verify_happy.py — otp_consumed audit assertion"

key-decisions:
  - "Use `from __future__ import annotations` + `PaginatedData.model_construct(...)` in repository.py to defer Pydantic generic schema build (PaginatedData[Client] tries to register Client as a Pydantic-compatible type at runtime, raising PydanticSchemaGenerationError)"
  - "Switch service.actor parameter from `app.modules.auth.models.User` to `app.core.dependencies.CurrentUser` Protocol — service only uses `actor.id`, the Protocol satisfies that, and the change makes the existing router-to-service call type-clean under mypy --strict"
  - "Refresh `updated_at` after flush() before model_validate() in update_client — SA 2.0 expires modified attributes after flush; without explicit refresh Pydantic's attribute read triggers an implicit lazy-load (MissingGreenlet under async)"
  - "Add `_include_object` filter in alembic/env.py rather than declaring GIN trgm indexes in `__table_args__` — Plan 08-01 chose raw `op.execute()` because `lower(col) gin_trgm_ops` cannot be expressed in SA Core; the filter is the symmetric autogenerate-side mitigation"
  - "Test the default `created_at DESC` sort via the `id DESC` tie-breaker rather than via timestamps — Postgres `func.now()` returns `transaction_timestamp()` which is constant within the SAVEPOINT-rolled per-test transaction, so two POSTs share `created_at` exactly and the deciding key is `id DESC`"

patterns-established:
  - "Per-test authed httpx client with dependency-override-bound app (clients/conftest.py:_client_app_overrides)"
  - "AuditLog row-existence assertion: select(AuditLog).where(action == EVT, resource_id == ID) -> exactly 1 row"
  - "AUDIT-03 negative test: GET on plausible audit paths must 404 (route absent), not 401/403 (route gated)"

requirements-completed: [CLIENTS-02, CLIENTS-03, CLIENTS-04, CLIENTS-05, CLIENTS-06, CLIENTS-07, CLIENTS-08, AUDIT-02, AUDIT-03, INFRA-04]

# Metrics
duration: ~50min
completed: 2026-05-03
---

# Phase 08 Plan 08: Tests + Repository/Service Hardening Summary

**One-liner:** 30 new clients integration tests + 6 auth audit-row assertions + 4 production-code Rule-1 fixes that surfaced once tests started exercising the integration boundary, all four Phase 8 success criteria automatically verified by the 239-test backend suite.

## Performance

- **Duration:** ~50 min (incl. Postgres/Redis docker bring-up + repository import-issue diagnosis)
- **Started:** 2026-05-03T15:30Z
- **Completed:** 2026-05-03T16:20Z
- **Tasks completed:** 5 plan tasks + 1 defensive prerequisite (repository import fix)
- **Files created:** 6
- **Files modified:** 8

## Task Commits

Each task was committed atomically (in order):

| # | Task | Commit | Type |
|---|------|--------|------|
| 0 | Defensive: defer `PaginatedData[Client]` schema build (PEP 563) — prerequisite for any test that imports `app.modules.clients.router` | `d02249b` | fix |
| 1 | alembic env.py `_include_object` filter for GIN trgm indexes (Pitfall 1) | `c62c954` | chore |
| 1b | Rule 1: runtime `PaginatedData[Client]` -> `model_construct`; post-flush `session.refresh` | `814028b` | fix |
| 2 | tests/integration/clients/{__init__, conftest, test_clients_list, test_clients_crud}.py | `9167fdc` | test |
| 3 | tests/integration/clients/{test_clients_rbac, test_audit_writes}.py | `a130ab2` | test |
| 4 | Audit-row assertions extending existing /login /logout /refresh /telegram_start /telegram_verify tests | `7bfe0d8` | test |
| 5 | Rule 1: service.actor type from `User` -> `CurrentUser` Protocol (mypy --strict clean) | `df53dc4` | fix |

## Per-Success-Criterion Pointers

Each Phase 8 success criterion is now backed by a passing integration test:

| Phase 8 Success Criterion | Test | File |
|---|---|---|
| List/search/filter/sort/pagination (CLIENTS-03 + CLIENTS-04) | `test_list_*` (10 tests) | `test_clients_list.py` |
| POST E.164 + PATCH partial + DELETE owner-only soft-delete + GET 404 | `test_create_*`, `test_patch_*`, `test_delete_*`, `test_get_returns_404_for_*` | `test_clients_crud.py` + `test_clients_rbac.py` |
| Soft-deleted phone reusable (CLIENTS-02 marquee) | `test_delete_is_soft_delete_phone_reusable` | `test_clients_crud.py` |
| Audit rows for every locked event (AUDIT-02) | `test_*_writes_audit_row` x9 | `test_audit_writes.py` + `tests/integration/auth/*` |
| AUDIT-03 — no GET /audit-log endpoint exists | `test_no_audit_log_endpoint_exists` | `test_audit_writes.py` |
| INFRA-04 — alembic upgrade head + check clean post-Pitfall-1 | `test_alembic_check_clean` | `test_alembic_clean.py` |
| TEST-06 RBAC parity | `test_owner_only.py` parametrized over OWNER_ONLY | `test_rbac_parity.py` |
| TEST-07 route introspection | `test_route_introspection.py` enumerates all clients endpoints | `test_route_introspection.py` |

## Test Counts

```
$ cd apps/backend && uv run pytest tests/ --no-header -q
...
239 passed in 9.81s
```

- Phase 8 NEW: 30 (clients/) + 6 (auth/ extensions) = **36 new tests**
- Phase 8 supporting tests (TEST-06, TEST-07, TEST-08): **all green**
- Pre-existing tests still passing: **203**
- **Total: 239 passing, 0 failed, 0 skipped (with Postgres + Redis up)**

## Quality Gates (Task 5 acceptance criteria)

| Gate | Command | Status |
|---|---|---|
| ruff lint | `uv run ruff check` | ✓ All checks passed |
| mypy --strict | `uv run mypy --strict app/` | ✓ Success: no issues found in 58 source files |
| import-linter | `uv run lint-imports` | ✓ Contracts: 3 kept, 0 broken |
| alembic upgrade + check | `uv run alembic upgrade head && uv run alembic check` | ✓ "No new upgrade operations detected." |
| alembic round-trip | `downgrade base && upgrade head && check` | ✓ clean |
| pytest tests/ | `uv run pytest tests/ -x` | ✓ 239 passed in 9.81s |

## Alembic Status (post-Pitfall-1 fix)

`apps/backend/alembic/env.py` now declares `_include_object` and wires it into `context.configure(...)`. This skips the two raw-DDL GIN trigram indexes (`ix_clients_last_name_trgm`, `ix_clients_first_name_trgm`) from autogenerate diffing because they cannot be expressed in `__table_args__`. Result: `alembic check` exits 0 with stdout `"No new upgrade operations detected."` even though the indexes exist in the DB but not in `Base.metadata`.

```
$ uv run alembic upgrade head && uv run alembic check
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.schemas
...
No new upgrade operations detected.
```

## Phase 8 Ready for Verification

All four Phase 8 success criteria from ROADMAP.md are observable as passing integration tests:

1. **List/search/filter/sort/pagination** — 10 tests in `test_clients_list.py`, all green.
2. **POST E.164 + PATCH partial + DELETE owner-only + GET 404** — 10 tests in `test_clients_crud.py` + 5 in `test_clients_rbac.py`, all green.
3. **Soft-deleted phone reusable** — `test_delete_is_soft_delete_phone_reusable` (the marquee test) green.
4. **Audit rows for every locked event** — 5 tests in `test_audit_writes.py` (clients events) + 6 new audit assertions in `tests/integration/auth/` (auth events), all green.

INFRA-04, AUDIT-02, AUDIT-03 plus all CLIENTS-* requirements are backed by the test suite. Phase 8 is ready for the verifier.

## Deviations from Plan

### Auto-fixed Issues (Rule 1 / Rule 3)

**1. [Rule 3 — Blocking] Repository import fails before any test can collect**

- **Found during:** Plan-context check (the `<known_integration_issue>` block in the orchestrator's prompt explicitly flagged this; reproduced via `python -c "from app.modules.clients.router import router"`).
- **Issue:** `repository.py:list_alive` was annotated `-> PaginatedData[Client]`. Without `from __future__ import annotations`, the annotation is evaluated at module-load and Pydantic eagerly tries to build a core schema for `Client` (a SQLAlchemy ORM class), raising `PydanticSchemaGenerationError`.
- **Fix:** Added `from __future__ import annotations` to repository.py + an explicit `result: Client | None = await session.scalar(stmt)` local in `get_alive` to keep mypy happy after annotation deferral made `Select[tuple[Client]]` a string.
- **Files:** `apps/backend/app/modules/clients/repository.py`
- **Commit:** `d02249b`

**2. [Rule 1 — Bug] Runtime `PaginatedData[Client](...)` still triggered Pydantic schema build**

- **Found during:** Task 2 first test run. The annotation deferral fixed import-time evaluation, but the call site `return PaginatedData[Client](...)` in `list_alive` evaluates `__class_getitem__(Client)` at runtime, hitting the same `PydanticSchemaGenerationError`.
- **Fix:** Switch to `PaginatedData.model_construct(items=..., total=..., page=..., page_size=...)` — bypasses validation against the unparametrised generic. The service layer (Plan 06) immediately re-wraps as `PaginatedData[ClientResponse]` so semantically nothing changes downstream.
- **Files:** `apps/backend/app/modules/clients/repository.py`
- **Commit:** `814028b`

**3. [Rule 1 — Bug] `update_client` returned a stale ORM row to Pydantic after flush**

- **Found during:** Task 2 PATCH test. SA 2.0 expires modified attributes after `session.flush()`. `service.update_client` flushed early to surface phone-conflict, then handed the now-expired Client to `ClientResponse.model_validate(client)` — Pydantic's attribute read of `updated_at` triggered an implicit lazy-load that requires a greenlet context, raising `MissingGreenlet`.
- **Fix:** Added `await session.refresh(client, attribute_names=["updated_at"])` between `audit.emit` and `model_validate`.
- **Files:** `apps/backend/app/modules/clients/service.py`
- **Commit:** `814028b`

**4. [Rule 1 — Bug] mypy --strict regression on Plan 07 router-to-service call**

- **Found during:** Task 5 final verification.
- **Issue:** `service.create_client / update_client / soft_delete_client` declared `actor: User` (the SA ORM class). The router resolves `require_permission(...)` to a `CurrentUser` Protocol instance. mypy --strict reported 3 `[arg-type]` errors on the router-to-service calls.
- **Fix:** Switched the service `actor` parameter to `CurrentUser` (the structural Protocol from `app.core.dependencies`) and dropped the now-unused `from app.modules.auth.models import User`. The service uses only `actor.id`, which is part of the Protocol — runtime semantics unchanged.
- **Files:** `apps/backend/app/modules/clients/service.py`
- **Commit:** `df53dc4`

### Authentication Gates

None encountered. Postgres + Redis containers were brought up via `docker compose up -d postgres` plus a host-network `docker run -p 6379:6379 redis:7` (Redis container in `docker-compose.yml` does not publish 6379 — pre-existing infra quirk; the host-mapped run is local to this worktree only and does not affect the committed compose file).

### Deferred Items

None. All five plan tasks are complete and all acceptance criteria pass.

## Threat Flags

None. The Plan's `<threat_model>` mitigations were honored:

- **T-08-44 (test misses an audit row):** Tests share the SAVEPOINT-rolled `db_session` with route handlers via the conftest dependency override; flush-only writes are visible.
- **T-08-46 (alembic check false-positive on GIN trgm):** `_include_object` filter applied.
- **T-08-48 (AUDIT-03 negative test passes via 404, not 401/403):** `test_no_audit_log_endpoint_exists` checks for 404 specifically.
- **T-08-49 (TEST-07 misses new clients endpoints):** Existing TEST-07 enumerates `app.routes` and is parametrised — no edit needed; passes against Plan 07 endpoints.

## Known Stubs

None. All five clients service functions, all five repository helpers, all integration tests, and all production-code fixes are fully implemented.

## TDD Gate Compliance

N/A — plan is `type: execute`, not `type: tdd`. The plan IS the test suite for Phase 8 production code from Plans 08-01..08-07.

## Next Phase Readiness

- Phase 09 (OpenAPI pipeline + packages/api-client): the FastAPI app can now generate `openapi.json` covering the 5 `/api/v1/clients` endpoints. All Pydantic DTOs are alias-camelCased and have `from_attributes=True` where needed.
- Phase 10 (admin-web wiring): typed clients endpoints are stable for `VITE_API_MODE=http` swap-seam; CSRF double-submit (`sportzal_csrf` cookie + `X-CSRF-Token` header) is already exercised in tests and matches the frontend fetch helper expectation.

## Self-Check: PASSED

Files exist:
- `apps/backend/tests/integration/clients/__init__.py` — **FOUND**
- `apps/backend/tests/integration/clients/conftest.py` — **FOUND**
- `apps/backend/tests/integration/clients/test_clients_list.py` — **FOUND**
- `apps/backend/tests/integration/clients/test_clients_crud.py` — **FOUND**
- `apps/backend/tests/integration/clients/test_clients_rbac.py` — **FOUND**
- `apps/backend/tests/integration/clients/test_audit_writes.py` — **FOUND**
- `apps/backend/alembic/env.py` (modified) — **VERIFIED via grep `_include_object`**

Commits exist (latest -> oldest):
- `df53dc4` (Task 5 mypy fix) — **FOUND**
- `7bfe0d8` (Task 4 auth audit assertions) — **FOUND**
- `a130ab2` (Task 3 RBAC + audit-writes tests) — **FOUND**
- `9167fdc` (Task 2 list + crud tests) — **FOUND**
- `814028b` (Rule 1 bug fixes — runtime PaginatedData + post-flush refresh) — **FOUND**
- `c62c954` (Task 1 alembic env.py) — **FOUND**
- `d02249b` (Task 0 defensive repository import fix) — **FOUND**

Quality gates (Task 5 acceptance criteria):
- ruff check: clean — **VERIFIED**
- mypy --strict app/: clean (58 source files, 0 errors) — **VERIFIED**
- import-linter: 3 contracts kept, 0 broken — **VERIFIED**
- alembic round-trip: clean ("No new upgrade operations detected.") — **VERIFIED**
- pytest tests/: 239 passed, 0 failed, 0 skipped — **VERIFIED**
