# Phase 2: Backend Skeleton with Quality Tooling — Pattern Map

**Mapped:** 2026-04-30
**Files analyzed:** ~47 new files + 1 directory deletion
**Analogs found:** 5 in-repo (monorepo/tooling conventions) / ~47 total
**Backend Python analogs:** NONE — `apps/backend/` does not exist yet; all Python files are net-new.

---

## Analog Availability Statement

The existing codebase is **frontend-only** (`apps/admin-web/`). There are zero Python files in the repository. For every backend Python file, the pattern source is **02-RESEARCH.md** — which contains verified, concrete code shapes for each file. The in-repo analogs that DO exist govern:

- **Monorepo app conventions** — how an `apps/*` member is laid out and what tooling config files it carries (`apps/admin-web/`)
- **Workspace manifest** — how `pnpm-workspace.yaml` registers members (backend is NOT a pnpm workspace — it is a uv Python project that lives next to `admin-web`)
- **`.gitignore` shape** — `apps/admin-web/.gitignore` is the repo-baseline `.gitignore` reference for the GSD-tooling header block
- **`.env.example` style** — `apps/admin-web/.env.example` shows the project's env-file commenting style

---

## File Classification

All files are in `apps/backend/` unless otherwise noted.

| New / Modified File | Role | Data Flow | Closest In-Repo Analog | Match Quality |
|---------------------|------|-----------|------------------------|---------------|
| `pyproject.toml` | config | — | `apps/admin-web/package.json` (manifest shape) | convention-only |
| `ruff.toml` | dev-tooling-config | — | `apps/admin-web/eslint.config.js` (linter config role) | convention-only |
| `importlinter.ini` | dev-tooling-config | — | NONE | none |
| `alembic.ini` | alembic-config | — | NONE | none |
| `.env.example` | config | — | `apps/admin-web/.env.example` | style-match |
| `.gitignore` | config | — | `apps/admin-web/.gitignore` | style-match |
| `uv.lock` (generated) | config | — | `pnpm-lock.yaml` (lockfile convention) | convention-only |
| `app/__init__.py` | module-package-init | — | NONE | none |
| `app/core/__init__.py` | module-package-init | — | NONE | none |
| `app/modules/__init__.py` | module-package-init | — | NONE | none |
| `app/integrations/__init__.py` | module-package-init | — | NONE | none |
| `app/workers/__init__.py` | module-package-init | — | NONE | none |
| `app/api/__init__.py` | module-package-init | — | NONE | none |
| `app/api/v1/__init__.py` | module-package-init | — | NONE | none |
| `app/main.py` | app-factory | request-response | NONE — net-new; see RESEARCH.md Pattern 1 | none |
| `app/core/config.py` | config | — | NONE — net-new; see RESEARCH.md Pattern 4 | none |
| `app/core/database.py` | core-infra | CRUD | NONE — net-new; see RESEARCH.md Pattern 2 | none |
| `app/core/logging.py` | core-infra | event-driven | NONE — net-new; see RESEARCH.md Pattern 5 | none |
| `app/core/exceptions.py` | core-infra | request-response | NONE — net-new; see RESEARCH.md Pattern 7 | none |
| `app/core/middleware.py` | middleware | request-response | NONE — net-new; see RESEARCH.md Pattern 6 | none |
| `app/core/security.py` | placeholder | — | NONE — empty module with docstring | none |
| `app/core/dependencies.py` | placeholder | — | NONE — empty module with docstring | none |
| `app/core/pagination.py` | utility | transform | NONE — net-new | none |
| `app/api/router.py` | api-route | request-response | NONE — net-new; see RESEARCH.md Pattern 8 | none |
| `app/api/v1/router.py` | api-route | request-response | NONE — net-new; see RESEARCH.md Pattern 8 | none |
| `app/api/v1/health.py` | api-route | request-response | NONE — net-new; see RESEARCH.md Pattern 8 | none |
| `app/modules/auth/__init__.py` | module-package-init | — | NONE | none |
| `app/modules/auth/router.py` | api-route (placeholder) | — | NONE — empty APIRouter, TODO Phase C+ | none |
| `app/modules/auth/service.py` | placeholder | — | NONE | none |
| `app/modules/auth/models.py` | placeholder | — | NONE | none |
| `app/modules/auth/schemas.py` | placeholder | — | NONE | none |
| `app/modules/{members,memberships,visits,trainers,schedule,bookings,billing,notifications}/__init__.py` (×8) | module-package-init | — | NONE | none |
| `app/integrations/telegram/__init__.py` | module-package-init | — | NONE | none |
| `app/integrations/telegram/bot.py` | integration-placeholder | event-driven | NONE | none |
| `app/integrations/telegram/handlers.py` | integration-placeholder | event-driven | NONE | none |
| `app/integrations/telegram/sender.py` | integration-placeholder | event-driven | NONE | none |
| `app/integrations/email/__init__.py` | module-package-init | — | NONE | none |
| `app/integrations/email/client.py` | integration-placeholder | request-response | NONE | none |
| `app/integrations/email/templates/.gitkeep` | config | — | `infra/docker/.gitkeep` (gitkeep pattern) | exact |
| `app/workers/arq_app.py` | worker-placeholder | event-driven | NONE — net-new; see RESEARCH.md Pattern 9 | none |
| `app/workers/scheduler.py` | worker-placeholder | batch | NONE | none |
| `app/workers/tasks/__init__.py` | module-package-init | — | NONE | none |
| `app/workers/tasks/notifications.py` | worker-placeholder | event-driven | NONE | none |
| `app/workers/tasks/reminders.py` | worker-placeholder | batch | NONE | none |
| `app/workers/tasks/reports.py` | worker-placeholder | batch | NONE | none |
| `alembic/env.py` | alembic-config | CRUD | NONE — net-new; see RESEARCH.md Pattern 3 | none |
| `alembic/script.py.mako` | alembic-config | — | NONE | none |
| `alembic/versions/.gitkeep` | config | — | `infra/docker/.gitkeep` (gitkeep pattern) | exact |
| **DELETE** root `backend/` dir | cleanup | — | n/a | n/a |

---

## Pattern Assignments

### Wave 0 — Project Scaffold

---

#### `apps/backend/pyproject.toml` (config)

**Analog:** `apps/admin-web/package.json` — monorepo app manifest conventions (private project, pinned tooling versions, named scripts).

**In-repo reference** (lines 1-10 of `apps/admin-web/package.json`):
```json
{
  "name": "sportzal-adminka",
  "private": true,
  "version": "0.1.0",
  "engines": {
    "node": ">=20.0.0",
    "pnpm": ">=9.0.0"
  }
}
```
**Apply:** Python equivalent uses `[project] name = "sportzal-backend"`, `requires-python = ">=3.12,<3.13"`, private via no `[project.urls]` publishing config.

**Primary pattern source — RESEARCH.md Pattern 11** (lines 688-729):
- `[project]` block with pinned version ranges
- `[dependency-groups] dev = [...]` — PEP 735 (NOT deprecated `[tool.uv] dev-dependencies`)
- `[tool.mypy] strict = true; plugins = ["pydantic.mypy"]`
- `[[tool.mypy.overrides]] module = "alembic.env"; disable_error_code = ["no-untyped-call"]`
- `[tool.pydantic-mypy]` plugin settings

---

#### `apps/backend/ruff.toml` (dev-tooling-config)

**Analog:** `apps/admin-web/eslint.config.js` — role is linter configuration. No code to copy — language mismatch.

**Primary pattern source — RESEARCH.md Pattern 12** (lines 736-764):
- `target-version = "py312"`, `line-length = 100` (matches frontend Prettier `printWidth: 100`)
- `[lint] select = ["E","F","I","B","UP","ASYNC","S","DTZ","N","SIM","RUF"]`
- `ignore = ["S101"]` (allow assert in tests)
- `[lint.per-file-ignores] "alembic/env.py" = ["S", "I001"]`
- `[format] quote-style = "double"` (ruff format uses double quotes by default)

**Key project constraint:** `line-length = 100` is mandatory — must match frontend Prettier width (CLAUDE.md, Formatting section).

---

#### `apps/backend/.env.example` (config)

**Analog:** `apps/admin-web/.env.example` (line 1-4):
```
# Picks the data layer impl. 'mock' (default) wires the in-memory mock services;
# 'http' wires the real HTTP client (added in a later phase).
VITE_API_MODE=mock
```
**Apply:** Same style — comment line above each var explaining what it controls, working values not placeholders.

**Primary pattern source — RESEARCH.md (Discretion items, line ~144-151)**:
```
DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/sportzal
REDIS_URL=redis://localhost:6379/0
ENVIRONMENT=dev
DEBUG=true
SECRET_KEY=change-me-dev-only-not-secret
```
Must be **working dev defaults**, not `YOUR_VALUE_HERE` placeholders.

---

#### `apps/backend/.gitignore` (config)

**Analog:** `apps/admin-web/.gitignore` — reference for the GSD-tooling baseline header block (lines 42-69 show the auto-generated block pattern).

**Copy the Python-relevant entries** (no node_modules, no dist, no coverage):
```
.venv/
__pycache__/
.mypy_cache/
.ruff_cache/
*.pyc
.pytest_cache/
.coverage
```
Do NOT add `uv.lock` to `.gitignore` — the lockfile is committed (CONTEXT.md Discretion items).

---

#### `apps/backend/importlinter.ini` (dev-tooling-config)

**Analog:** NONE — no import-linter equivalent in the frontend codebase.

**Primary pattern source — RESEARCH.md Pattern 10** (lines 646-682, which reproduces CONTEXT.md D-01 exactly):

Three contracts:
1. `[importlinter:contract:core-not-depend-on-modules]` — `type = forbidden`
2. `[importlinter:contract:modules-independent]` — `type = independence` (lists all 9 module packages)
3. `[importlinter:contract:integrations-not-depend-on-modules]` — `type = forbidden`

**Allowed directions NOT in contracts** (per D-02..D-04): `api → modules`, `workers → integrations`, `modules → integrations`, `integrations → core`.

---

#### `apps/backend/alembic.ini` (alembic-config)

**Analog:** NONE.

**Pattern:** Standard Alembic-generated `alembic.ini`. Critical settings:
- `script_location = alembic` (relative to `apps/backend/`)
- `sqlalchemy.url` is left as placeholder — `env.py` overrides it from `Settings.database_url` at runtime
- Keep alembic's default `[loggers]`, `[handlers]`, `[formatters]` sections unchanged

---

### Wave 1 — Core Package Inits

#### All `__init__.py` files (module-package-init)

**Analog:** NONE — Python package init convention.

**Pattern:** Empty files (0 bytes) are acceptable and mypy-clean. No imports, no `__all__`, no docstrings unless a specific module warrants one. Per RESEARCH.md: "Placeholder modules with only a docstring are clean."

Files:
- `app/__init__.py`
- `app/core/__init__.py`
- `app/modules/__init__.py`
- `app/integrations/__init__.py`
- `app/workers/__init__.py`
- `app/api/__init__.py`
- `app/api/v1/__init__.py`

---

### Wave 2 — Core Modules

---

#### `apps/backend/app/core/config.py` (config)

**Analog:** NONE — net-new Python file.

**Primary pattern source — RESEARCH.md Pattern 4** (lines 429-455):

Full verified implementation:
```python
from functools import lru_cache
from typing import Literal
from pydantic import PostgresDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )
    database_url: PostgresDsn
    redis_url: RedisDsn
    environment: Literal['dev', 'staging', 'prod'] = 'dev'
    debug: bool = False
    secret_key: SecretStr

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**Key constraints:**
- No env var prefix (raw `DATABASE_URL`, `REDIS_URL`, etc.)
- `extra='ignore'` not `'forbid'` (Pitfall 3 in RESEARCH.md)
- `@lru_cache` not `@lru_cache()` (Python 3.8+ preferred style)
- `SecretStr` for `secret_key` — not `str` (needed for future auth, stable shape from day 1)

---

#### `apps/backend/app/core/database.py` (core-infra, CRUD)

**Analog:** NONE — net-new Python file.

**Primary pattern source — RESEARCH.md Pattern 2** (lines 323-365):

Full verified implementation of `db_lifespan`, `Base`, and `get_db`. Critical points:
- `async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)` — NOT sync `sessionmaker`
- Engine stashed on `app.state.engine`; sessionmaker on `app.state.sessionmaker`
- `get_db` return type is `AsyncIterator[AsyncSession]` from `collections.abc` — NOT `AsyncGenerator` (mypy strict, RESEARCH.md line 1048)
- `await engine.dispose()` in the `finally` path of lifespan (after `yield`)
- Never import `create_app` from `main.py` in this file (Pitfall 2 in RESEARCH.md)

---

#### `apps/backend/app/core/logging.py` (core-infra, event-driven)

**Analog:** NONE — net-new Python file.

**Primary pattern source — RESEARCH.md Pattern 5** (lines 463-488):

Key points:
- `merge_contextvars` MUST be first processor in chain (Pitfall 4 in RESEARCH.md)
- Renderer: `ConsoleRenderer(colors=True)` for `environment == 'dev'`; `JSONRenderer()` for staging/prod
- NOT TTY detection, NOT `DEBUG` flag — driven by `Settings.environment`
- `cache_logger_on_first_use=True` is a performance optimization that is safe here

---

#### `apps/backend/app/core/exceptions.py` (core-infra, request-response)

**Analog:** NONE — net-new Python file.

**Primary pattern source — RESEARCH.md Pattern 7** (lines 549-596):

Error class hierarchy and `register_exception_handlers`:
- `AppError` base with class-level `code: str` and `status_code: int`
- `NotFoundError(404)`, `ForbiddenError(403)`, `ConflictError(409)`, `ValidationAppError(422)`
- Constructor: `__init__(message: str, *, fields: dict | None = None)` — keyword-only `fields`
- Handler returns `JSONResponse(status_code=exc.status_code, content={'code':..., 'message':..., 'fields':...})`
- `register_exception_handlers` uses `@app.exception_handler(AppError)` inline — NOT a separate method

---

#### `apps/backend/app/core/middleware.py` (middleware, request-response)

**Analog:** NONE — net-new Python file.

**Primary pattern source — RESEARCH.md Pattern 6** (lines 495-544):

Critical ordering constraint — `add_middleware` order is **REVERSED** from execution order (Pitfall 1 in RESEARCH.md):
```python
def register_middleware(app: FastAPI) -> None:
    # TODO Phase X: CORS once frontend integrates
    app.add_middleware(TimingMiddleware)     # added first → runs SECOND on request
    app.add_middleware(RequestIdMiddleware)  # added second → runs FIRST on request
```
- `clear_contextvars()` called before `bind_contextvars()` every request (Pitfall in D-09)
- `TimingMiddleware` logs via `structlog.get_logger().info(...)` — placeholder level is fine
- `Any` type needed for `call_next` parameter — import from `typing`

---

#### `apps/backend/app/core/security.py` (placeholder)

**Analog:** NONE — simplest possible file.

**Pattern:** Module docstring only, no imports, no functions:
```python
"""TODO Phase C+: password hashing, JWT issue/verify."""
```

---

#### `apps/backend/app/core/dependencies.py` (placeholder)

**Analog:** NONE.

**Pattern:** Module docstring describing purpose:
```python
"""Shared FastAPI Depends factories. TODO Phase B+: add per-module dependencies here."""
```

---

#### `apps/backend/app/core/pagination.py` (utility, transform)

**Analog:** NONE — net-new Python file.

**Pattern source:** RESEARCH.md mentions `LimitOffsetParams` + generic `Page[T]` (BE-08). No code shape provided in RESEARCH.md — use canonical pydantic v2 generic model pattern:

```python
from typing import Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar('T')

class LimitOffsetParams(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
```

**mypy strict note:** Generic `BaseModel` requires `from __future__ import annotations` or explicit `Generic[T]` inheritance — the above form is safe in Python 3.12 + pydantic v2.

---

### Wave 3 — API Surface

---

#### `apps/backend/app/main.py` (app-factory, request-response)

**Analog:** NONE — net-new Python file.

**Primary pattern source — RESEARCH.md Pattern 1** (lines 290-315):

Full `create_app()` factory:
```python
def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    app = FastAPI(
        title='Sportzal API',
        lifespan=db_lifespan,
        docs_url='/docs' if settings.environment == 'dev' else None,
        redoc_url=None,
    )
    register_middleware(app)
    register_exception_handlers(app)
    app.include_router(api)
    return app
```

**No module-level `app = create_app()`** — uvicorn is launched with `--factory app.main:create_app` flag. This enables test isolation (each test calls `create_app()` directly).

---

#### `apps/backend/app/api/router.py` (api-route, request-response)

**Primary pattern source — RESEARCH.md Pattern 8** (lines 619-626):
```python
from fastapi import APIRouter
from app.api.v1.router import v1

api = APIRouter()
# TODO Phase B+: add /api/v1 prefix; reconcile /healthz path
api.include_router(v1)
```
The `# TODO Phase B+` comment is **mandatory** per CONTEXT.md D-14 and Specifics section.

---

#### `apps/backend/app/api/v1/router.py` (api-route, request-response)

**Primary pattern source — RESEARCH.md Pattern 8** (lines 612-618):
```python
from fastapi import APIRouter
from app.api.v1 import health

v1 = APIRouter()
v1.include_router(health.router)
# TODO Phase B+: include module routers here
```

---

#### `apps/backend/app/api/v1/health.py` (api-route, request-response)

**Primary pattern source — RESEARCH.md Pattern 8** (lines 601-611):
```python
from fastapi import APIRouter

router = APIRouter()

@router.get('/healthz')
async def health() -> dict[str, str]:
    return {'status': 'ok'}
```
Return type must be `dict[str, str]` for mypy strict — not bare `dict`.

---

### Wave 4 — Module Placeholders

---

#### `apps/backend/app/modules/auth/router.py` (api-route placeholder)

**Analog:** NONE — net-new.

**Pattern:** Empty `APIRouter` with TODO comment per D-02:
```python
"""Auth module router. TODO Phase C+: add JWT auth endpoints."""
from fastapi import APIRouter

router = APIRouter()
# TODO Phase C+: add /login, /refresh, /logout endpoints
```

---

#### `apps/backend/app/modules/auth/{service,models,schemas}.py` (placeholder ×3)

**Pattern:** Module-level docstring only:
```python
"""Auth {service|models|schemas} placeholder. TODO Phase C+."""
```

---

#### `apps/backend/app/modules/{members,memberships,visits,trainers,schedule,bookings,billing,notifications}/__init__.py` (module-package-init ×8)

**Pattern:** Empty files. import-linter's `independence` contract requires these packages to exist in the import graph. RESEARCH.md Pitfall 5 notes that empty `__init__.py` files may not be scanned by grimp — if the synthetic violation test (D-05) fails because of this, add a single comment line `# module placeholder` to make the file non-empty.

---

### Wave 5 — Integration + Worker Placeholders

---

#### `apps/backend/app/integrations/telegram/{bot,handlers,sender}.py` (integration-placeholder ×3)

**Pattern:** Module-level docstring:
```python
"""Telegram {bot|handlers|sender} placeholder. TODO Phase X+: aiogram integration."""
```
No imports — aiogram is not in `pyproject.toml` dependencies. Empty bodies pass mypy strict.

---

#### `apps/backend/app/integrations/email/client.py` (integration-placeholder)

```python
"""Email client placeholder. TODO Phase X+: SMTP/transactional email integration."""
```

---

#### `apps/backend/app/integrations/email/templates/.gitkeep` (config)

**Analog:** `infra/docker/.gitkeep` — exact pattern. Empty file, committed to track the empty directory in git.

---

#### `apps/backend/app/workers/arq_app.py` (worker-placeholder, event-driven)

**Primary pattern source — RESEARCH.md Pattern 9** (lines 631-641):
```python
from arq.connections import RedisSettings
from app.core.config import get_settings

class WorkerSettings:
    functions: list[Any] = []
    # TODO Phase B+: add real task functions here
    redis_settings = RedisSettings.from_dsn(str(get_settings().redis_url))
```
**mypy strict note:** `list` must be typed — use `list[Any]` with `from typing import Any` (RESEARCH.md line 1049).

---

#### `apps/backend/app/workers/scheduler.py` + `tasks/{notifications,reminders,reports}.py` (placeholder ×4)

**Pattern:** Module-level docstring only:
```python
"""Worker {scheduler|tasks.notifications|tasks.reminders|tasks.reports} placeholder. TODO Phase B+."""
```

---

### Wave 6 — Alembic

---

#### `apps/backend/alembic/env.py` (alembic-config, CRUD)

**Analog:** NONE — net-new Python file.

**Primary pattern source — RESEARCH.md Pattern 3** (lines 373-421):

Full async migration setup. Critical points:
- Import `Base` from `app.core.database` and `get_settings` from `app.core.config` — NEVER import `create_app` (Pitfall 2)
- `do_run_migrations(connection)` has no type annotation — covered by `[[tool.mypy.overrides]] disable_error_code = ["no-untyped-call"]` in pyproject.toml
- `run_migrations_offline()` raises `NotImplementedError` — online async path only
- `asyncio.run(run_async_migrations())` at module level is correct — Alembic calls `run_migrations_online()`

**mypy override required** in `pyproject.toml` (already in Pattern 11):
```toml
[[tool.mypy.overrides]]
module = "alembic.env"
disable_error_code = ["no-untyped-call"]
```

---

#### `apps/backend/alembic/script.py.mako` (alembic-config)

**Analog:** NONE.

**Pattern:** Standard Alembic-generated template. Run `uv run alembic init alembic` to generate it and then keep the output verbatim. Alternatively copy the canonical template from Alembic source. Do not customize.

---

#### `apps/backend/alembic/versions/.gitkeep` (config)

**Analog:** `infra/docker/.gitkeep` — exact pattern. Empty file to track the `versions/` directory before any migration is generated.

---

### Cleanup Task

#### DELETE: root-level `backend/` directory

**Pattern source — RESEARCH.md Pitfall 7** (lines 867-873):

The empty `backend/` at the repo root was left by Phase 1 (D-15). Phase 2 Wave 0 must delete it before or alongside creating `apps/backend/`. Command: `rmdir /path/to/clubcore/backend`. Verify empty first with `ls backend/` — it should show no files.

---

## Shared Patterns

### Placeholder Module Docstring Convention

**Apply to:** All files marked `[PLACEHOLDER]` in RESEARCH.md file manifest

**Pattern:**
```python
"""<Module description>. TODO Phase <X>+: <what will land here>."""
```

Single-line module docstring. No imports. No stub functions raising `NotImplementedError`. This is the explicit CONTEXT.md constraint: "No stub functions raising NotImplementedError."

---

### Import Convention for Python Modules

**Apply to:** All `app/core/` modules and `app/main.py`

Since `app` is the root package (not `sportzal`), all internal imports use:
```python
from app.core.config import get_settings
from app.core.database import db_lifespan
```
Never relative imports (`from .config import ...`) — absolute imports are required for import-linter's grimp graph builder to resolve contracts correctly.

---

### mypy Strict Compliance Patterns

**Apply to:** All Python files

Key gotchas from RESEARCH.md (lines 1044-1052):
1. `get_db` return type: `AsyncIterator[AsyncSession]` (from `collections.abc`), not `AsyncGenerator`
2. `WorkerSettings.functions`: `list[Any]` not bare `list`
3. `do_run_migrations`: covered by `[[tool.mypy.overrides]]` in pyproject.toml — do not add stubs
4. Placeholder modules with only docstrings: mypy skips cleanly — no additional annotation needed
5. `dict[str, str]` for health endpoint return type — not bare `dict`

---

### `.gitkeep` Convention

**Apply to:** `alembic/versions/.gitkeep`, `app/integrations/email/templates/.gitkeep`

**Analog:** `infra/docker/.gitkeep`, `infra/nginx/.gitkeep` — exact same pattern: zero-byte file committed to track an otherwise-empty directory. File name is `.gitkeep` (with leading dot).

---

### Line Length Consistency

**Apply to:** All Python files (ruff.toml) and the project manifest (pyproject.toml)

`line-length = 100` in `ruff.toml` matches the frontend Prettier `printWidth: 100` (CLAUDE.md Formatting). This is a cross-language project consistency constraint.

---

## No Analog Found (Full Backend Python List)

All backend Python files have no in-repo code analog. The table below summarizes the RESEARCH.md section that is the canonical pattern source for each file.

| File | Role | Data Flow | RESEARCH.md Pattern Section |
|------|------|-----------|------------------------------|
| `app/main.py` | app-factory | request-response | Pattern 1 (lines 284-315) |
| `app/core/config.py` | config | — | Pattern 4 (lines 425-457) |
| `app/core/database.py` | core-infra | CRUD | Pattern 2 (lines 317-365) |
| `app/core/logging.py` | core-infra | event-driven | Pattern 5 (lines 459-488) |
| `app/core/exceptions.py` | core-infra | request-response | Pattern 7 (lines 547-596) |
| `app/core/middleware.py` | middleware | request-response | Pattern 6 (lines 491-544) |
| `app/core/pagination.py` | utility | transform | BE-08 description + pydantic v2 Generic |
| `app/api/router.py` | api-route | request-response | Pattern 8 (lines 598-626) |
| `app/api/v1/router.py` | api-route | request-response | Pattern 8 (lines 598-626) |
| `app/api/v1/health.py` | api-route | request-response | Pattern 8 (lines 598-626) |
| `app/workers/arq_app.py` | worker | event-driven | Pattern 9 (lines 629-641) |
| `importlinter.ini` | dev-tooling-config | — | Pattern 10 (lines 643-682) |
| `pyproject.toml` | config | — | Pattern 11 (lines 684-729) |
| `ruff.toml` | dev-tooling-config | — | Pattern 12 (lines 731-764) |
| `alembic/env.py` | alembic-config | CRUD | Pattern 3 (lines 367-421) |

---

## Wave Dependency Summary (for Planner)

The RESEARCH.md file manifest defines 6 waves. The dependency chain is:

```
Wave 0 (scaffold: pyproject.toml, ruff.toml, importlinter.ini, alembic.ini, .env.example, .gitignore)
  + Cleanup (rmdir backend/)
     ↓
Wave 1 (__init__.py files — makes `app.*` importable)
     ↓
Wave 2 (core/ modules — all can be written in parallel after Wave 1)
     ↓
Wave 3 (main.py + api/ chain — depends on core being importable)
Wave 4 (modules/ placeholders — can be parallel with Wave 3)
Wave 5 (integrations/ + workers/ placeholders — can be parallel with Wave 3/4)
Wave 6 (alembic/ — depends only on Wave 2 core being importable; parallel with Wave 3/4/5)
```

Waves 3, 4, 5, 6 can all execute in parallel after Wave 2 completes.

**After all waves:** `uv lock` generates `uv.lock` — this must happen after `pyproject.toml` is final (Wave 0) but only needs to be committed once at the end.

---

## Metadata

**Analog search scope:** `apps/admin-web/`, root config files (`pnpm-workspace.yaml`, `pnpm-lock.yaml`), `packages/`, `infra/`
**Files scanned:** 15 in-repo files
**Python files in repo:** 0
**Pattern extraction date:** 2026-04-30

## PATTERN MAPPING COMPLETE
