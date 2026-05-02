---
phase: 06-rbac-wiring-parity-tests
plan: 04
subsystem: backend/tests/rbac
tags:
  - rbac
  - tests
  - fixture-router
  - integration

# Dependency graph
requires:
  - 06-02 # Wave 1: require_permission factory + audit-emit wiring
  - 05    # Wave 0: User model + /api/v1/auth/login + SAVEPOINT db_session
provides:
  - tests/_fixtures/owner_routes:router        # 9-route synthetic stub from OWNER_ONLY
  - tests/integration/rbac/conftest:app_with_fixture_routes # sibling app fixture
  - tests/integration/rbac/conftest:owner_client           # seeded OWNER + login flow
  - tests/integration/rbac/conftest:reception_client       # seeded RECEPTION + login flow
  - tests/integration/rbac/conftest:rbac_async_client      # anonymous client for 401 path
  - TEST-05                                                # 28 parametrized assertions
affects: []

# Tech surface
tech_stack:
  added: []
  patterns:
    - "Closure-factory for late-binding-safe APIRouter construction (defeat Python late-binding)"
    - "Sibling app fixture pattern (mounting test-only routes without touching create_app)"
    - "Per-fixture AsyncClient cookie jar isolation (owner vs reception cannot collide)"

# Files
key_files:
  created:
    - apps/backend/tests/_fixtures/__init__.py
    - apps/backend/tests/_fixtures/owner_routes.py
    - apps/backend/tests/integration/rbac/__init__.py
    - apps/backend/tests/integration/rbac/conftest.py
    - apps/backend/tests/integration/rbac/test_owner_only.py
  modified: []

# Decisions
decisions:
  - "Fixture router lives in tests/_fixtures/ (leading underscore) so pytest does not collect modules inside as test functions (D-10)."
  - "owner_client uses a dedicated AsyncClient (not rbac_async_client) so its cookie jar does not collide with reception_client when both fixtures are pulled into the same test."
  - "rbac_redis_clean is consumed by the role-client fixtures (kwarg, not Depends) — flushdb runs once before each role-client mints cookies, ensuring rate-limit / session keys do not bleed between tests."
  - "Production app.main.create_app() is NOT modified — the fixture router is mounted ONLY by app_with_fixture_routes (D-12)."

# Metrics
metrics:
  duration_minutes: 12
  completed: 2026-05-02T14:33:51Z
  task_count: 3
  file_count: 5
  commits:
    - d252c73 # Task 1: OWNER_ONLY fixture router
    - ef578b1 # Task 2: RBAC conftest with two-role login fixtures
    - a95807a # Task 3: TEST-05 parametrized over OWNER_ONLY
---

# Phase 06 Plan 04: TEST-05 OWNER_ONLY Integration Suite Summary

Built the dynamic OWNER_ONLY fixture router and parametrized integration suite (28 tests) that exercises the full RBAC chain (Argon2 → JWT → cookie → loader → require_permission → can() → ForbiddenError → JSON envelope) on REAL seeded users — without touching the production composition root.

## What was delivered

### Task 1 — `tests/_fixtures/owner_routes.py` (commit `d252c73`)

A test-only `APIRouter` mounted at prefix `/_t` exposes one synthetic stub per `(action, resource)` pair in `OWNER_ONLY`. Endpoints are constructed via a closure factory (`_make_endpoint(a, r)`) to defeat Python late-binding — without the indirection, every loop iteration would close over the same cell and all endpoints would resolve to the LAST pair. Sorted iteration over `OWNER_ONLY` works because `Action`/`Resource` are `StrEnum` subclasses (comparison falls back to underlying string).

Output (verified): 9 routes, paths exactly `{f'/_t/{a.value}/{r.value}' for a, r in OWNER_ONLY}`. Each carries `Depends(require_permission(action, resource))` from `app.core.dependencies`.

### Task 2 — `tests/integration/rbac/conftest.py` (commit `ef578b1`)

Five fixtures + two helpers, all built on the SAVEPOINT-rolled `db_session` from the root conftest (Phase 5 D-22):

- `app_with_fixture_routes` — sibling of the root `app` fixture; calls `create_app()` then `include_router(_owner_routes_router)`. Overrides `get_db` and `get_redis` exactly the way the root `async_client` does (so seeded users are visible to the auth flow that resolves them via the loader).
- `rbac_redis_clean` — flushdb hook on `app.state.redis`.
- `rbac_async_client` — anonymous `AsyncClient` bound to the fixture-router-mounted app (used by 401 tests).
- `owner_client` — seeded OWNER user + dedicated `AsyncClient` + completed `/api/v1/auth/login` (cookies in jar).
- `reception_client` — seeded RECEPTION user + a SEPARATE `AsyncClient` so cookies do not collide with `owner_client`.
- Helpers `_seed_user(db_session, *, role, email, password)` and `_login(client, *, email, password)`.

### Task 3 — `tests/integration/rbac/test_owner_only.py` (commit `a95807a`)

Four test functions, 28 cases total:

| Test                                                       | Cases | What it asserts                                                                  |
| ---------------------------------------------------------- | ----- | -------------------------------------------------------------------------------- |
| `test_owner_allowed_on_every_owner_only_pair`              | 9     | owner_client.GET → 200, body `{"ok": true}` (T-06-16 mitigation)                 |
| `test_reception_forbidden_on_every_owner_only_pair`        | 9     | reception_client.GET → 403, code='forbidden', message='forbidden:{a}:{r}', fields=null (T-06-15) |
| `test_unauthenticated_returns_401_before_403`              | 9     | rbac_async_client.GET → 401 invalid_token (RBAC-04 ordering invariant; T-06-17)  |
| `test_reception_denial_emits_rbac_forbidden_event`         | 1     | structlog.capture_logs sees `event=rbac_forbidden` with locked key set (T-06-19) |

The audit-emit smoke test picks `(Action.DELETE, Resource.CLIENTS)` and asserts the `rbac_forbidden` event carries `role=reception`, `action=delete`, `resource=clients`, `path=/_t/delete/clients`, plus a `user_id` (the seeded reception UUID, str). This validates that Plan 06-02's audit wiring shipped end-to-end and reaches structlog through the real router → handler chain.

## Final fixture topology

```
root tests/conftest.py
├── app (root FastAPI per-test)
├── db_session (SAVEPOINT-rolled)
└── async_client (bound to root app)

tests/integration/rbac/conftest.py (sibling — does NOT replace root)
├── app_with_fixture_routes (create_app() + include_router(_owner_routes_router))
├── rbac_redis_clean (flushdb)
├── rbac_async_client (anonymous; bound to app_with_fixture_routes)
├── owner_client    (seeded OWNER     + dedicated AsyncClient + login cookies)
└── reception_client (seeded RECEPTION + dedicated AsyncClient + login cookies)
```

Phase 5 tests continue using the root `app` / `async_client`. Only RBAC tests opt into `app_with_fixture_routes`.

## Production composition root: UNCHANGED

```
$ grep -E "_owner_routes_router" apps/backend/app/main.py
$ echo $?
1
```

`grep` returns nothing — `apps/backend/app/main.py` does not import or reference the fixture router. T-06-18 mitigated.

## Test run count

```
$ uv run pytest tests/integration/rbac/test_owner_only.py -v --collect-only
========================= 28 tests collected in 0.01s ==========================
```

```
$ uv run pytest tests/integration/rbac/test_owner_only.py -v
============================== 28 passed in 2.32s ==============================
```

```
$ uv run pytest tests/integration/auth/ tests/integration/rbac/ tests/unit/
============================== 178 passed in 3.71s ==============================
```

## Audit-emit smoke test result

`test_reception_denial_emits_rbac_forbidden_event` PASSED — `event=rbac_forbidden` reached structlog via `structlog.testing.capture_logs()` with all locked fields (`user_id`, `role`, `action`, `resource`, `path`). Confirms D-23 wiring (shipped by Plan 06-02) fires end-to-end through the real router → `require_permission` → `emit()` → structlog stack on a REAL seeded user. Phase 8 audit_log DB writer (INFRA-04) can latch on without renaming.

## Verification commands

| Command                                                                                                                | Result      |
| ---------------------------------------------------------------------------------------------------------------------- | ----------- |
| `uv run python -c "from tests._fixtures.owner_routes import router; assert len(router.routes) == 9"`                    | exit 0      |
| `uv run mypy tests/_fixtures/owner_routes.py tests/integration/rbac/conftest.py tests/integration/rbac/test_owner_only.py` | 3 files OK  |
| `uv run ruff check tests/_fixtures/ tests/integration/rbac/`                                                           | All passed  |
| `uv run lint-imports`                                                                                                  | 3 contracts kept, 0 broken |
| `uv run pytest tests/integration/rbac/test_owner_only.py`                                                              | 28 passed   |
| `uv run pytest tests/integration/auth/ tests/integration/rbac/ tests/unit/`                                            | 178 passed  |
| `grep -E "_owner_routes_router" apps/backend/app/main.py`                                                              | exit 1 (no match — production unchanged) |

## Threats mitigated

| Threat ID | Description                                                                  | Mitigated by                                              |
| --------- | ---------------------------------------------------------------------------- | --------------------------------------------------------- |
| T-06-15   | Reception bypasses OWNER_ONLY at runtime                                     | Task 3 `test_reception_forbidden_on_every_owner_only_pair`|
| T-06-16   | Owner mistakenly denied on a non-OWNER_ONLY pair (false positive)            | Task 3 `test_owner_allowed_on_every_owner_only_pair`      |
| T-06-17   | RBAC-04 violation: 401 vs 403 leaks identity existence                       | Task 3 `test_unauthenticated_returns_401_before_403`      |
| T-06-18   | Fixture router leaks into production                                          | Task 1 + grep guard on `apps/backend/app/main.py`         |
| T-06-19   | Forbidden denials produce no audit trail                                     | Task 3 `test_reception_denial_emits_rbac_forbidden_event` |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Lint] Removed two `# noqa: ARG001` directives that ruff flagged as unused**
- **Found during:** Task 2 ruff check
- **Issue:** The `ARG001` rule isn't enabled in this repo's ruff config, so the `# noqa: ARG001` comments on `rbac_redis_clean: Redis,` were flagged as unused noqa directives by RUF100.
- **Fix:** Removed the trailing `# noqa: ARG001 — fixture used for its flushdb side-effect` comments from both `owner_client` and `reception_client` parameter lists.
- **Files modified:** `apps/backend/tests/integration/rbac/conftest.py` (during Task 2 — committed in `ef578b1`)
- **Why:** Style consistency with the repo's actual ruff configuration; functional behavior unchanged (the fixture is still consumed for its side effect via the parameter dependency edge).

### Out-of-scope discoveries (not fixed)

**Test isolation flake when running `auth/` tests AFTER `rbac/` in same pytest session with `-x`:**
- `tests/integration/auth/test_login.py::test_login_429_after_5_failures` failed once when run after the rbac suite under `-x`, because the rate-limit Redis counter from rbac fixtures wasn't fully cleared by the auth `redis_clean` fixture in the failing window.
- Running the full suite without `-x` (so all fixtures complete normally): **178 passed**.
- Running auth suite alone: **13 passed**.
- This is a pre-existing fixture-isolation concern, not introduced by Plan 06-04. **Not fixed** per scope boundary.

### Auth gates encountered

None. Tests authenticate via the real `/api/v1/auth/login` endpoint with seeded users created inside the SAVEPOINT-rolled `db_session`.

## Self-Check: PASSED

Files verified to exist:
- `apps/backend/tests/_fixtures/__init__.py` ✓
- `apps/backend/tests/_fixtures/owner_routes.py` ✓
- `apps/backend/tests/integration/rbac/__init__.py` ✓
- `apps/backend/tests/integration/rbac/conftest.py` ✓
- `apps/backend/tests/integration/rbac/test_owner_only.py` ✓

Commits verified to exist (`git log --oneline`):
- `d252c73` Task 1 ✓
- `ef578b1` Task 2 ✓
- `a95807a` Task 3 ✓
