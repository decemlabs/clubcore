---
phase: 03-tests-dev-infrastructure-documentation
plan: 01
subsystem: backend/tests
tags: [pytest, fastapi, asgi, asgi-lifespan, httpx, async-test]
requirements: [TEST-01, TEST-02, TEST-03, TEST-04]
dependency-graph:
  requires:
    - apps/backend/app/main.py:create_app  # Phase 2 D-08 factory
    - apps/backend/app/core/database.py:db_lifespan  # Phase 2 D-06/D-07
    - apps/backend/app/core/middleware.py:RequestIdMiddleware  # Phase 2 D-09
    - apps/backend/app/api/v1/health.py:GET /healthz  # Phase 2 D-14
    - apps/backend/app/core/security.py  # Phase 2 BE-05 placeholder
    - apps/backend/.env.example  # Phase 2 D-15 (read by conftest fallback)
  provides:
    - pytest scaffold (conftest fixtures + integration + unit suites)
    - asgi-lifespan dev-dep (lifespan-under-ASGITransport contract)
    - [tool.pytest.ini_options] config (asyncio_mode = auto, testpaths)
    - tests/factories/ placeholder for Phase B+ factory-boy
  affects:
    - apps/backend/pyproject.toml (added pytest config + dev-dep)
    - apps/backend/uv.lock (added asgi-lifespan v2.1.0 + sniffio v1.3.1)
    - apps/backend/ruff.toml (per-file-ignore for plan-locked noqa)
tech-stack:
  added:
    - asgi-lifespan>=2.1 (dev-only)
  patterns:
    - per-test create_app() factory (no module-level FastAPI singleton)
    - LifespanManager wraps app so app.state.sessionmaker is populated
    - httpx.AsyncClient over ASGITransport (no real network)
    - pytest-asyncio auto mode (no @pytest.mark.asyncio decorators)
    - AsyncIterator[T] from collections.abc for fixture return types (mypy strict)
key-files:
  created:
    - apps/backend/tests/__init__.py
    - apps/backend/tests/integration/__init__.py
    - apps/backend/tests/unit/__init__.py
    - apps/backend/tests/factories/__init__.py
    - apps/backend/tests/conftest.py
    - apps/backend/tests/integration/test_healthz.py
    - apps/backend/tests/unit/test_security.py
  modified:
    - apps/backend/pyproject.toml
    - apps/backend/uv.lock
    - apps/backend/ruff.toml
decisions:
  - "Honored locked D-11 fixture shape verbatim (per-test create_app + LifespanManager + ASGITransport)"
  - "Honored locked D-10 except form: `except Exception as exc:  # noqa: BLE001` (broad-on-purpose so OperationalError triggers pytest.skip)"
  - "Honored Phase 2 D-15 [tool.uv] dev-dependencies shape — did NOT migrate to PEP 735"
  - "Added conftest-time .env.example loader (Rule 3 deviation) so Settings validation passes on a fresh checkout without `.env`"
  - "Added ruff per-file-ignore RUF100 for tests/conftest.py (Rule 1 micro-deviation) to preserve plan-locked `# noqa: BLE001` rationale comment"
metrics:
  duration: "~5 min"
  completed: "2026-05-01"
  tasks: 2
  files_changed: 10
---

# Phase 3 Plan 01: Pytest Scaffold Summary

**One-liner:** Pytest scaffold that lets `uv run pytest` from `apps/backend/` exit 0 with three tests collected (healthz x2 + security placeholder), wiring `httpx.ASGITransport` to a per-test `create_app()` instance via `asgi-lifespan.LifespanManager`.

## Tasks Completed

| Task | Name                                                                                     | Commit    | Files                                                        |
| ---- | ---------------------------------------------------------------------------------------- | --------- | ------------------------------------------------------------ |
| 1    | Extend pyproject.toml — pytest config + asgi-lifespan dev-dep + uv lock                  | `6fee12a` | `apps/backend/pyproject.toml`, `apps/backend/uv.lock`        |
| 2    | Create tests/ tree — package markers + conftest fixtures + healthz + security placeholder | `9c9d118` | 7 new files under `apps/backend/tests/` + `ruff.toml` tweak  |

## What Shipped

### `apps/backend/pyproject.toml`
- New top-level `[tool.pytest.ini_options]` block (D-14 literal):
  ```toml
  [tool.pytest.ini_options]
  asyncio_mode = "auto"
  testpaths = ["tests"]
  python_files = ["test_*.py"]
  filterwarnings = [
      "error",
      "ignore::DeprecationWarning:pydantic.*",
  ]
  ```
- Appended `"asgi-lifespan>=2.1"` to existing `[tool.uv] dev-dependencies` (D-15). Did **not** migrate to PEP 735 `[dependency-groups]` per Phase 2 D-15 lock; the comment lines above `[tool.uv]` were preserved.
- Did **not** touch `[project] dependencies` — `asgi-lifespan` is dev-only so it stays out of the production runtime image (Phase 3-02 Dockerfile uses `uv sync --no-dev`, T-03-03 mitigation).

### `apps/backend/uv.lock`
- Regenerated via `uv lock`. Added: `asgi-lifespan==2.1.0`, `sniffio==1.3.1`. `uv sync --frozen` succeeds.

### `apps/backend/tests/conftest.py`
Three fixtures, all honoring locked D-11 shape with mypy-strict types from `collections.abc`:

- **`app`** — per-test `FastAPI` instance via `create_app()`, wrapped in `LifespanManager(app)`. This is the entire reason `asgi-lifespan` was added: `httpx.ASGITransport` does not auto-fire FastAPI's lifespan, so without `LifespanManager` the engine + sessionmaker never get bound to `app.state` and `db_session` would never work in Phase B+.
- **`async_client`** — `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`. No real network — CLAUDE.md constraint enforced by construction.
- **`db_session`** — pulls `app.state.sessionmaker`, opens a session, runs `select 1` to probe connectivity. On any failure, `pytest.skip(...)` per D-10. The `except Exception as exc:  # noqa: BLE001` form is locked broad-on-purpose because SQLAlchemy's `OperationalError` does not inherit from `OSError`, so a narrower `except (OSError, ConnectionError)` would let connectivity failures crash the test instead of skipping it. Yields the session, rolls back on teardown (never commits — preserves the contract for Phase B+).

The fixture file is currently unused by Phase A test bodies (`/healthz` makes no DB call); `db_session` is shipped per TEST-01 contract and exercised first in Phase B+.

### `apps/backend/tests/integration/test_healthz.py`
Two assertions:
1. `response.status_code == 200` and `response.json() == {"status": "ok"}` — satisfies TEST-02 verbatim.
2. `x-request-id` header is present and parses as `uuid.UUID(version=4)` — proves Phase 2 RequestIdMiddleware fires under `httpx.ASGITransport`. Catches the "tests pass but middleware silently bypassed" failure mode.

### `apps/backend/tests/unit/test_security.py`
Pure-Python placeholder. Imports `app.core.security` (smoke-test) and asserts `True`. Exists so `tests/unit/` is non-empty and pytest discovery works under TEST-03; real password-hashing / JWT tests land in Phase C+.

### Empty package markers
- `apps/backend/tests/__init__.py` — 0 bytes
- `apps/backend/tests/integration/__init__.py` — 0 bytes
- `apps/backend/tests/unit/__init__.py` — 0 bytes
- `apps/backend/tests/factories/__init__.py` — 0 bytes (TEST-04 contract; future factory-boy lands in Phase B+)

## Why `asgi-lifespan`?

FastAPI's `lifespan` context manager is the only place `app.state.engine` and `app.state.sessionmaker` get bound (Phase 2 D-06/D-07/D-08). When tests reach `app` via `httpx.ASGITransport`, the lifespan is **not** automatically fired — `ASGITransport` only proxies HTTP requests, not the ASGI lifespan protocol. Without `LifespanManager`, every request would land on a `FastAPI` whose state was never initialized.

`asgi-lifespan.LifespanManager` is a tiny library (~50 LOC of correctness) that explicitly drives the lifespan protocol around an `async with` block. It's the canonical fix and is listed in `[tool.uv] dev-dependencies` only — production never imports it.

## Verification Battery (Plan Section)

| Gate                                 | Result                                                  |
| ------------------------------------ | ------------------------------------------------------- |
| `uv sync --frozen`                   | Checked 52 packages — OK                                |
| `uv run pytest -v`                   | **3 passed** (healthz x2 + security x1) in 0.05s        |
| `uv run mypy app tests`              | Success: no issues found in 51 source files            |
| `uv run ruff check tests` / `ruff check .` | All checks passed                                  |
| `uv run lint-imports`                | Contracts: 3 kept, 0 broken                             |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] conftest auto-loads `.env.example` defaults when `.env` absent**
- **Found during:** Task 2 verification (`uv run pytest`)
- **Issue:** `Settings` (Phase 2 D-15) requires `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY` from env or `.env`. Fresh worktree has no `.env`; pytest startup → `create_app()` → `db_lifespan` → `Settings()` raised `pydantic.ValidationError` for 3 missing fields, blocking all tests with `ERROR` status. Plan acceptance criterion explicitly requires `3 passed`.
- **Fix:** Added a top-level snippet in `tests/conftest.py` that, at import time, reads `apps/backend/.env.example` and applies each `KEY=VALUE` pair via `os.environ.setdefault(...)` (does not overwrite existing env vars — production env always wins). The `.env.example` is the single source of truth for both the README D-09 quick-start (`cp .env.example .env`) and the test fallback.
- **Files modified:** `apps/backend/tests/conftest.py`
- **Commit:** `9c9d118`
- **Why this fits Rule 3:** Without it, the plan's locked acceptance "`uv run pytest reports 3 passed`" is unreachable; the fix is test-only (does not change production behaviour) and reuses the existing `.env.example` rather than introducing new defaults.

**2. [Rule 1 - Bug] ruff per-file-ignore for `RUF100` on tests/conftest.py**
- **Found during:** Task 2 verification (`uv run ruff check tests`)
- **Issue:** Plan locks the literal `except Exception as exc:  # noqa: BLE001` (D-10 rationale comment). `BLE` (flake8-blind-except) is **not** in `ruff.toml [lint] select`, so ruff flagged the noqa as redundant via `RUF100` ("Unused `noqa` directive — Remove unused `noqa` directive"). Plan acceptance grep `grep -c 'except Exception as exc:.*# noqa: BLE001'` requires the literal stay.
- **Fix:** Added `"tests/conftest.py" = ["RUF100"]` under `[lint.per-file-ignores]` in `apps/backend/ruff.toml`, with an inline comment explaining the rationale.
- **Files modified:** `apps/backend/ruff.toml`
- **Commit:** `9c9d118`
- **Alternative considered:** Adding `BLE` to `[lint] select` — rejected because it widens ruff scope across the whole repo for one comment.

## Threat Surface Scan

No new surface relative to the plan's `<threat_model>`. The four registered threats (T-03-01..T-03-04) are mitigated as designed:

- **T-03-01 (Tampering, conftest.py)** → mitigated. Per-test `create_app()` (no shared mutable state); `db_session` rolls back, never commits.
- **T-03-02 (Information Disclosure, filterwarnings)** → accepted. `error` policy plus narrow `pydantic.*` `DeprecationWarning` carve-out, both in `[tool.pytest.ini_options]`.
- **T-03-03 (EoP, asgi-lifespan dev-dep)** → mitigated. Listed in `[tool.uv] dev-dependencies` only; verified absent from `[project] dependencies` block.
- **T-03-04 (DoS, db_session against unreachable DB)** → mitigated. `select 1` probe wrapped in `try/except` → `pytest.skip(...)` per D-10. Tests do not hang.

The `.env.example` auto-load (Rule 3 deviation above) does not change the trust surface: it only sets in-process env vars during test runs, never writes to disk, and uses `os.environ.setdefault` so real production env always wins.

## Self-Check: PASSED

- [x] `apps/backend/tests/__init__.py` — exists, 0 bytes
- [x] `apps/backend/tests/integration/__init__.py` — exists, 0 bytes
- [x] `apps/backend/tests/unit/__init__.py` — exists, 0 bytes
- [x] `apps/backend/tests/factories/__init__.py` — exists, 0 bytes
- [x] `apps/backend/tests/conftest.py` — exists; LifespanManager + create_app imports present; 3 `@pytest_asyncio.fixture` decorators; locked `# noqa: BLE001` comment present
- [x] `apps/backend/tests/integration/test_healthz.py` — exists; both `test_healthz_returns_200_and_status_ok` and `test_healthz_emits_request_id_header` defined
- [x] `apps/backend/tests/unit/test_security.py` — exists; `test_security_module_is_importable` defined; `import app.core.security` present
- [x] `apps/backend/pyproject.toml` — `[tool.pytest.ini_options]` block present; `asgi-lifespan>=2.1` in `[tool.uv] dev-dependencies`; no `[dependency-groups]` table header
- [x] `apps/backend/uv.lock` — `asgi-lifespan` package entry present
- [x] Commit `6fee12a` (chore Task 1) — verified in `git log`
- [x] Commit `9c9d118` (feat Task 2) — verified in `git log`
- [x] `uv run pytest -v` — 3 passed
- [x] `uv run mypy app tests` — Success: 51 source files
- [x] `uv run ruff check .` — All checks passed
- [x] `uv run lint-imports` — 3 contracts kept, 0 broken
