# Phase 2: Backend Skeleton with Quality Tooling — Research

**Researched:** 2026-04-30
**Domain:** FastAPI modular monolith skeleton — uv, FastAPI 0.115+, SQLAlchemy 2.0 async, Alembic async, pydantic-settings v2, structlog, import-linter, ruff, mypy strict, ARQ
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-00:** Python 3.12 + uv + FastAPI 0.115+ + SQLAlchemy 2.0 async + Alembic async + Pydantic v2 + pydantic-settings + asyncpg + Postgres 16 + Redis 7 + ARQ + structlog + httpx. Package name `app`, layout flat at `apps/backend/app/`.
- **D-01:** importlinter.ini uses mixed contract types: `forbidden` for core→modules and integrations→modules, `independence` for pairwise module independence. Exact ini shape provided in CONTEXT.md.
- **D-02:** `app.api → app.modules.*` is allowed. `app/api/v1/router.py` wires module routers directly. No registry indirection. Only `auth` has a `router.py` in Phase A (no endpoints — may be commented out with TODO).
- **D-03:** `app.workers → app.integrations` and `app.modules → app.integrations` are allowed.
- **D-04:** `app.integrations → app.core` is allowed.
- **D-05:** Synthetic-violation verification is an ad-hoc plan task during execute-phase, not a committed script.
- **D-06:** Async SQLAlchemy engine is lifespan-managed via `db_lifespan(app)` `@asynccontextmanager`. Creates engine and `async_sessionmaker` on startup, stashes on `app.state`, disposes on shutdown.
- **D-07:** `get_db` reads `request.app.state.sessionmaker` — not module-level engine.
- **D-08:** `create_app()` factory composes `FastAPI(lifespan=db_lifespan, ...)`. No `@app.on_event`.
- **D-09:** `RequestIdMiddleware` extends `BaseHTTPMiddleware`. Reads/generates X-Request-ID, calls `clear_contextvars()` before `bind_contextvars()`, sets X-Request-ID on response.
- **D-10:** No third-party correlation library.
- **D-11:** `TimingMiddleware` (placeholder level). `register_middleware(app)` adds both in the correct order (RequestId runs first on incoming requests).
- **D-12:** Domain error hierarchy in `app/core/exceptions.py`: `AppError` (500), `NotFoundError` (404), `ForbiddenError` (403), `ConflictError` (409), `ValidationAppError` (422). Constructor `__init__(message, *, fields=None)`.
- **D-13:** Same file defines `register_exception_handlers(app)`. Handler returns `JSONResponse({code, message, fields})`. Called once during `create_app()`.
- **D-14:** `GET /healthz` mounted at root path via v1 router with empty prefix. Exact three-file chain: `health.py → v1/router.py → api/router.py → create_app()`. TODO comment in `api/router.py` for Phase B+ prefix.
- **Discretion items:** ruff rules (E, F, I, B, UP, ASYNC, S, DTZ, N, SIM, RUF), line-length 100. mypy strict + `pydantic.mypy` plugin, no SQLAlchemy mypy plugin, alembic.env override. Settings shape: `database_url: PostgresDsn`, `redis_url: RedisDsn`, `environment: Literal['dev','staging','prod']`, `debug: bool`, `secret_key: SecretStr`, no prefix. `get_settings()` `@lru_cache`. structlog renderer driven by `Settings.environment`. `.env.example` with working dev defaults. `uv.lock` committed. ARQ `WorkerSettings` with empty `functions` list.

### Claude's Discretion

See locked "Discretion items" above — all are now research findings, not open questions.

### Deferred Ideas (OUT OF SCOPE)

- CORS middleware — Phase X+
- `/api/v1` URL prefix — Phase B+
- Real auth logic — Phase C+
- Real Telegram/SMTP/ЮKassa — Phase X+
- ARQ real task implementations — Phase B+
- pytest scaffold, Dockerfile, docker-compose — Phase 3
- architecture.md / conventions.md / ADR / README.md — Phase 3
- Permanent synthetic-violation CI script — Phase 3 if needed
- In-process event bus — Phase B+
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BE-01 | `apps/backend/app/` — корень Python-пакета `app` | uv project layout; flat `app/` at backend root |
| BE-02 | `app/main.py` exports `create_app()`, wires FastAPI + router + structlog + middleware | D-08 lifespan, D-09/D-11 middleware, D-13 exceptions |
| BE-03 | `app/core/config.py` — Settings via pydantic-settings + cached `get_settings()` | pydantic-settings SettingsConfigDict pattern verified |
| BE-04 | `app/core/database.py` — async engine, async_sessionmaker, Base, get_db | SQLAlchemy 2.0 async pattern verified via Context7 |
| BE-05 | `app/core/security.py` — empty module with TODO docstring | Simple placeholder — no library research needed |
| BE-06 | `app/core/logging.py` — structlog setup, JSON in prod / colorized in dev | structlog configure() processor chain verified |
| BE-07 | `app/core/exceptions.py` — error hierarchy + register_exception_handlers | D-12/D-13 code shapes complete |
| BE-08 | `app/core/pagination.py` — LimitOffsetParams + generic Page[T] | Standard pattern; no external library needed |
| BE-09 | `app/core/dependencies.py` + `app/core/middleware.py` — placeholders + working request_id, timing, exception handlers | D-09/D-11 code shape verified |
| BE-10 | import-linter: core does not import app.modules | D-01 forbidden contract verified |
| MOD-01 | `app/modules/auth/` placeholder files | D-02 confirms no endpoints yet |
| MOD-02 | `app/modules/{8 domains}/__init__.py` exist | File manifest in this document |
| MOD-03 | import-linter verifies modules don't import each other | D-01 independence contract verified |
| INT-01 | `app/integrations/telegram/` placeholder modules | No aiogram calls — pure placeholder |
| INT-02 | `app/integrations/email/` placeholder | No SMTP — pure placeholder |
| WORK-01 | `app/workers/arq_app.py` — WorkerSettings skeleton | ARQ WorkerSettings verified via Context7 |
| WORK-02 | `app/workers/tasks/` placeholder functions | Pure placeholder modules |
| WORK-03 | `app/workers/scheduler.py` — placeholder | Pure placeholder |
| API-01 | `app/api/router.py` connects v1 router | D-14 chain verified |
| API-02 | `app/api/v1/router.py` connects health | D-14 chain verified |
| API-03 | `app/api/v1/health.py` — GET /healthz | D-14 verified; ROADMAP criterion 2 |
| DB-01 | alembic.ini + alembic/env.py async + script.py.mako | Async env.py pattern verified via Context7 |
| DB-02 | alembic/versions/.gitkeep | alembic upgrade head succeeds on empty versions/ |
| TOOL-01 | pyproject.toml with all deps under uv | uv [dependency-groups] pattern verified |
| TOOL-02 | ruff.toml strict rules | ruff [lint] select syntax verified for v0.6+ |
| TOOL-03 | mypy strict + pydantic.mypy plugin | mypy pyproject.toml pattern verified |
| TOOL-04 | importlinter.ini with three contracts | D-01 shape verified via Context7 |
| TOOL-05 | .env.example with working dev defaults | D-15 values documented |
| TOOL-06 | apps/backend/.gitignore | Standard Python .gitignore items |
</phase_requirements>

---

## Summary

Phase 2 brings up `apps/backend/` as a runnable FastAPI modular monolith. The entire phase is configuration and scaffolding: one real endpoint (`GET /healthz`), lifespan-managed async SQLAlchemy engine, structlog request correlation middleware, pydantic-settings configuration, and import-linter contracts that machine-enforce the core ⊥ modules architectural invariant from day one.

All 15 user decisions (D-00..D-14) are locked and validated by the research. The research fills in the implementation specifics that CONTEXT.md left to Claude's discretion: exact pyproject.toml shape (using modern `[dependency-groups]` not deprecated `[tool.uv] dev-dependencies`), verified ruff v0.15 rule syntax under `[tool.ruff.lint]` in `ruff.toml`, verified mypy pydantic plugin toml format, exact async Alembic `env.py` pattern, and the middleware add_middleware ordering pitfall (add_middleware call order is reversed from execution order).

The one notable discrepancy with CONTEXT.md: the CONTEXT.md mentions `[tool.uv] dev-dependencies` but that key is deprecated in uv. Modern syntax is `[dependency-groups]`. Research recommends using the current standard.

**Primary recommendation:** Follow locked decisions exactly. The implementation is straightforward scaffolding — the research provides exact code shapes for every module so the planner can produce actionable `<action>` blocks without further investigation.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| HTTP request routing | API (FastAPI) | — | FastAPI router chain is the standard HTTP surface |
| Request ID correlation | Middleware (ASGI) | Structlog contextvars | Must intercept at ASGI layer before any handler runs |
| Request timing | Middleware (ASGI) | Structlog | Same reason — wraps handler execution |
| Settings / config | Core | — | pydantic-settings at `app/core/config.py`; all other modules import core |
| Database engine lifecycle | Core (lifespan) | `app.state` | D-06: engine on `app.state`, not module-level |
| DB session per request | Core (dependency) | — | `get_db` via FastAPI Depends |
| Error handling | Core (exception handlers) | FastAPI | `register_exception_handlers(app)` in core |
| Logging setup | Core | Structlog | `app/core/logging.py` configures structlog once at startup |
| Pagination shapes | Core | — | Generic `Page[T]` lives in core, reused by all modules |
| Business domain logic | Modules | — | Each module is self-contained vertical slice |
| Inter-service calls (Telegram, email) | Integrations | — | Outbound adapters; modules and workers import them |
| Background task execution | Workers (ARQ) | Integrations | Workers call integrations, not modules directly |
| Migration management | Database (Alembic) | Core (Settings) | env.py reads Settings for DATABASE_URL |
| Architecture enforcement | Tooling (import-linter) | — | Machine-checked contracts; not runtime |

---

## Standard Stack

### Core (production runtime)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | 0.136.1 (pin `>=0.115`) | Web framework, DI, OpenAPI | Locked by D-00 |
| sqlalchemy | 2.0.49 | Async ORM + Core | Locked by D-00; PEP 484 native in 2.0 |
| asyncpg | 0.31.0 | PostgreSQL async driver | Fastest Postgres asyncio driver |
| alembic | 1.18.4 | Database migrations | Official SQLAlchemy migration tool |
| pydantic | 2.13.3 | Data validation | FastAPI depends on it; v2 required |
| pydantic-settings | 2.14.0 | Settings from env/dotenv | Standard companion to pydantic v2 |
| structlog | 25.5.0 | Structured logging | Locked by D-00 |
| arq | 0.28.0 | Async task queue (Redis-backed) | Locked by D-00 |
| redis | 7.4.0 | Redis client (ARQ dependency) | Required by ARQ |
| httpx | 0.28.1 | Async HTTP client | Locked by D-00; Phase 3 tests use ASGITransport |
| uvicorn | latest `>=0.30` | ASGI server | Standard FastAPI server; `--factory` flag needed |

### Development / Quality tooling

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| ruff | 0.15.12 (pin `>=0.6`) | Linter + formatter | replaces flake8, isort, black |
| mypy | 1.20.2 | Static type checker | strict mode + pydantic plugin |
| import-linter | 2.11 | Architectural boundary enforcement | import contracts |
| pytest | latest `>=8` | Test runner | Phase 3 (scaffold deferred) |
| pytest-asyncio | 1.3.0 | Async test support | Phase 3 |

**Version verification:** All versions confirmed via `pip index versions` on 2026-04-30. [VERIFIED: pip registry]

**Installation (inside `apps/backend/` with uv):**
```bash
uv sync
# or bootstrap:
uv init --name sportzal-backend --python 3.12
uv add fastapi sqlalchemy asyncpg alembic pydantic-settings structlog arq redis httpx uvicorn
uv add --dev ruff mypy import-linter pytest pytest-asyncio
```

---

## Architecture Patterns

### System Architecture Diagram

```
HTTP Request
     |
     v
[ASGI: uvicorn]
     |
     v
[RequestIdMiddleware] ──> generates/reads X-Request-ID
     |                    clears + binds structlog contextvars
     v
[TimingMiddleware]   ──> logs request duration
     |
     v
[FastAPI router]
     |
     v
[app/api/router.py]  ──> aggregates api
     |
     v
[app/api/v1/router.py] ──> aggregates v1
     |
     |─────────────────────────────────┐
     v                                 v
[health.py]                    [modules/*.router] (Phase B+)
GET /healthz                           |
     |                                 v
     |                        [module service]
     v                                 |
[JSONResponse]               [get_db dependency]
{"status":"ok"}                        |
                               [AsyncSession] <── created from
                                              app.state.sessionmaker
                                              (lifespan-managed engine)

Lifespan events:
  startup: create_async_engine → async_sessionmaker → app.state
  shutdown: engine.dispose()

Background workers (separate process):
  arq worker → WorkerSettings → functions list (empty in Phase A)
               → RedisSettings.from_dsn(settings.redis_url)
```

### Recommended Project Structure

```
apps/backend/
├── pyproject.toml           # uv project + all tool configs
├── ruff.toml                # ruff rules (imports from pyproject or standalone)
├── importlinter.ini         # import-linter contracts
├── alembic.ini              # alembic config (script_location = alembic)
├── .env.example             # dev defaults
├── .gitignore               # Python ignores
├── uv.lock                  # committed lockfile
└── app/
    ├── __init__.py
    ├── main.py              # create_app() factory
    ├── core/
    │   ├── __init__.py
    │   ├── config.py        # Settings, get_settings()
    │   ├── database.py      # db_lifespan, get_db, Base
    │   ├── security.py      # placeholder — TODO Phase C+
    │   ├── logging.py       # structlog configure()
    │   ├── exceptions.py    # AppError hierarchy + register_exception_handlers
    │   ├── pagination.py    # LimitOffsetParams, Page[T]
    │   ├── dependencies.py  # shared FastAPI Depends (placeholder)
    │   └── middleware.py    # RequestIdMiddleware, TimingMiddleware, register_middleware
    ├── modules/
    │   ├── __init__.py
    │   ├── auth/
    │   │   ├── __init__.py
    │   │   ├── router.py    # APIRouter() — no endpoints, TODO Phase C+
    │   │   ├── service.py   # placeholder
    │   │   ├── models.py    # placeholder
    │   │   └── schemas.py   # placeholder
    │   ├── members/__init__.py
    │   ├── memberships/__init__.py
    │   ├── visits/__init__.py
    │   ├── trainers/__init__.py
    │   ├── schedule/__init__.py
    │   ├── bookings/__init__.py
    │   ├── billing/__init__.py
    │   └── notifications/__init__.py
    ├── integrations/
    │   ├── __init__.py
    │   ├── telegram/
    │   │   ├── __init__.py
    │   │   ├── bot.py       # placeholder — no aiogram
    │   │   ├── handlers.py  # placeholder
    │   │   └── sender.py    # placeholder
    │   └── email/
    │       ├── __init__.py
    │       ├── client.py    # placeholder — no SMTP
    │       └── templates/
    │           └── .gitkeep
    ├── workers/
    │   ├── __init__.py
    │   ├── arq_app.py       # WorkerSettings
    │   ├── scheduler.py     # placeholder
    │   └── tasks/
    │       ├── __init__.py
    │       ├── notifications.py  # placeholder
    │       ├── reminders.py      # placeholder
    │       └── reports.py        # placeholder
    └── api/
        ├── __init__.py
        ├── router.py        # api = APIRouter(); includes v1
        └── v1/
            ├── __init__.py
            ├── router.py    # v1 = APIRouter(); includes health
            └── health.py    # GET /healthz
alembic/
├── env.py                   # async migration setup
├── script.py.mako           # migration template
└── versions/
    └── .gitkeep
```

### Pattern 1: create_app() Factory with Lifespan

**What:** `create_app()` returns a fully configured `FastAPI` instance. The lifespan context manager handles async SQLAlchemy engine startup/shutdown.

**When to use:** Always — enables test isolation (each test creates its own app instance with its own engine).

```python
# Source: Context7 /websites/fastapi_tiangolo (lifespan events)
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.config import get_settings
from app.core.database import db_lifespan
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import register_middleware
from app.api.router import api

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

### Pattern 2: Lifespan-Managed Database Engine (D-06 / D-07)

**What:** Engine and sessionmaker created during lifespan startup, stored on `app.state`. `get_db` reads from `app.state` per-request.

**When to use:** Always for async SQLAlchemy in FastAPI — avoids module-level singletons that break test isolation.

```python
# Source: Context7 /websites/sqlalchemy_en_20 (async_sessionmaker)
# app/core/database.py
from contextlib import asynccontextmanager
from typing import AsyncIterator
from fastapi import FastAPI, Request
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


@asynccontextmanager
async def db_lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    engine = create_async_engine(
        str(settings.database_url),
        pool_pre_ping=True,
        echo=settings.debug,
    )
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    app.state.engine = engine
    app.state.sessionmaker = session_factory
    yield
    await engine.dispose()


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory = request.app.state.sessionmaker
    async with session_factory() as session:
        yield session
```

### Pattern 3: Async Alembic env.py (DB-01)

**What:** Alembic `env.py` uses the official async cookbook pattern: `async_engine_from_config` + `connection.run_sync(do_run_migrations)`.

**When to use:** Always with asyncpg — Alembic itself is synchronous; the async bridge is required.

```python
# Source: Context7 /websites/alembic_sqlalchemy (async cookbook)
# alembic/env.py
import asyncio
from logging.config import fileConfig
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool
from alembic import context
from app.core.config import get_settings
from app.core.database import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def do_run_migrations(connection):  # type: ignore[no-untyped-def]
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    settings = get_settings()
    configuration = config.get_section(config.config_ini_section) or {}
    configuration['sqlalchemy.url'] = str(settings.database_url)
    connectable = async_engine_from_config(
        configuration,
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


def run_migrations_offline() -> None:
    # Offline mode not needed — always use online async path
    raise NotImplementedError('Offline migrations not supported in async mode')


run_migrations_online()
```

**Note:** The mypy override `[[tool.mypy.overrides]] module = "alembic.env" disable_error_code = ["no-untyped-call"]` is required because `do_run_migrations` cannot be typed without alembic stubs. [CITED: Context7 /websites/alembic_sqlalchemy]

### Pattern 4: pydantic-settings Settings Class (BE-03)

**What:** Reads env vars or `.env` file. `PostgresDsn` validates `postgresql+asyncpg://` scheme. `get_settings()` is `@lru_cache` so it's instantiated once.

```python
# Source: Context7 /pydantic/pydantic-settings (SettingsConfigDict)
# app/core/config.py
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

**Verified:** `pydantic.PostgresDsn` accepts `postgresql+asyncpg://` scheme. [VERIFIED: live Python test 2026-04-30]

### Pattern 5: structlog Configuration (BE-06)

**What:** `configure_logging()` called once during `create_app()`. Renderer switches on `settings.environment`: `ConsoleRenderer` for dev, `JSONRenderer` for staging/prod. `merge_contextvars` processor must be in the chain to pick up request-scoped context.

```python
# Source: Context7 /hynek/structlog (configure + contextvars)
# app/core/logging.py
import structlog
from structlog.contextvars import merge_contextvars
from app.core.config import Settings


def configure_logging(settings: Settings) -> None:
    shared_processors: list[structlog.types.Processor] = [
        merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt='iso', utc=True),
        structlog.processors.StackInfoRenderer(),
    ]
    if settings.environment == 'dev':
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

### Pattern 6: RequestIdMiddleware (D-09)

**What:** ASGI middleware that clears contextvars before binding — prevents cross-request context bleed in async workers.

```python
# Source: CONTEXT.md D-09 (verified against Context7 /hynek/structlog contextvars pattern)
# app/core/middleware.py
import uuid
import time
import structlog
import structlog.contextvars
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from fastapi import FastAPI


class RequestIdMiddleware(BaseHTTPMiddleware):
    HEADER = 'X-Request-ID'

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        request_id = request.headers.get(self.HEADER) or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            path=request.url.path,
            method=request.method,
        )
        response = await call_next(request)
        response.headers[self.HEADER] = request_id
        return response


class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        structlog.get_logger().info(
            'request_complete',
            duration_ms=round(duration_ms, 2),
            status_code=response.status_code,
        )
        return response


def register_middleware(app: FastAPI) -> None:
    # TODO Phase X: CORS once frontend integrates
    # add_middleware order is REVERSED from execution order.
    # TimingMiddleware added first → innermost (runs last on request).
    # RequestIdMiddleware added second → outermost (runs first on request).
    app.add_middleware(TimingMiddleware)
    app.add_middleware(RequestIdMiddleware)
```

### Pattern 7: Exception Handlers (D-12 / D-13)

```python
# Source: CONTEXT.md D-12/D-13 (canonical FastAPI JSONResponse pattern)
# app/core/exceptions.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    code: str = 'app_error'
    status_code: int = 500

    def __init__(self, message: str, *, fields: dict | None = None) -> None:
        self.message = message
        self.fields = fields
        super().__init__(message)


class NotFoundError(AppError):
    code = 'not_found'
    status_code = 404


class ForbiddenError(AppError):
    code = 'forbidden'
    status_code = 403


class ConflictError(AppError):
    code = 'conflict'
    status_code = 409


class ValidationAppError(AppError):
    code = 'validation_error'
    status_code = 422


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                'code': exc.code,
                'message': exc.message,
                'fields': exc.fields,
            },
        )
```

### Pattern 8: Health Router Chain (D-14)

```python
# app/api/v1/health.py
from fastapi import APIRouter

router = APIRouter()

@router.get('/healthz')
async def health() -> dict[str, str]:
    return {'status': 'ok'}

# app/api/v1/router.py
from fastapi import APIRouter
from app.api.v1 import health

v1 = APIRouter()
v1.include_router(health.router)
# TODO Phase B+: include module routers here
# e.g. v1.include_router(auth_router, prefix='/auth', tags=['auth'])

# app/api/router.py
from fastapi import APIRouter
from app.api.v1.router import v1

api = APIRouter()
# TODO Phase B+: add /api/v1 prefix; reconcile /healthz path
api.include_router(v1)
```

### Pattern 9: ARQ WorkerSettings (WORK-01)

```python
# Source: Context7 /python-arq/arq (WorkerSettings, RedisSettings.from_dsn)
# app/workers/arq_app.py
from arq.connections import RedisSettings
from app.core.config import get_settings


class WorkerSettings:
    functions: list = []
    # TODO Phase B+: add real task functions here
    redis_settings = RedisSettings.from_dsn(str(get_settings().redis_url))
```

### Pattern 10: importlinter.ini (D-01)

```ini
# apps/backend/importlinter.ini
# Source: Context7 /seddonym/import-linter (forbidden + independence contracts)

[importlinter]
root_packages =
    app

[importlinter:contract:core-not-depend-on-modules]
name = core must not import modules
type = forbidden
source_modules =
    app.core
forbidden_modules =
    app.modules

[importlinter:contract:modules-independent]
name = modules cannot import each other
type = independence
modules =
    app.modules.auth
    app.modules.members
    app.modules.memberships
    app.modules.visits
    app.modules.trainers
    app.modules.schedule
    app.modules.bookings
    app.modules.billing
    app.modules.notifications

[importlinter:contract:integrations-not-depend-on-modules]
name = integrations must not import modules
type = forbidden
source_modules =
    app.integrations
forbidden_modules =
    app.modules
```

### Pattern 11: pyproject.toml (TOOL-01)

**Critical note:** CONTEXT.md mentions `[tool.uv] dev-dependencies` but that key is **deprecated** in uv (since 0.4.27). Modern uv uses `[dependency-groups]`. Both work — uv merges them — but `[dependency-groups]` is the PEP 735 standard and what `uv add --dev` creates. [VERIFIED: Context7 /astral-sh/uv]

```toml
[project]
name = "sportzal-backend"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = [
    "fastapi>=0.115",
    "sqlalchemy>=2.0",
    "asyncpg>=0.30",
    "alembic>=1.13",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "structlog>=24.0",
    "arq>=0.26",
    "redis>=7.0",
    "httpx>=0.27",
    "uvicorn[standard]>=0.30",
]

[dependency-groups]
dev = [
    "ruff>=0.6",
    "mypy>=1.10",
    "import-linter>=2.0",
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = "alembic.env"
disable_error_code = ["no-untyped-call"]

[tool.pydantic-mypy]
init_forbid_extra = true
init_typed = true
warn_required_dynamic_aliases = true
```

### Pattern 12: ruff.toml (TOOL-02)

In ruff v0.6+, linting config lives under `[lint]` (not `[tool.ruff.lint]`) when using standalone `ruff.toml`. [VERIFIED: Context7 /astral-sh/ruff]

```toml
# apps/backend/ruff.toml
target-version = "py312"
line-length = 100

[lint]
select = [
    "E",     # pycodestyle errors
    "F",     # Pyflakes
    "I",     # isort
    "B",     # flake8-bugbear
    "UP",    # pyupgrade
    "ASYNC", # flake8-async
    "S",     # flake8-bandit (security)
    "DTZ",   # flake8-datetimez (datetime hygiene — Europe/Moscow)
    "N",     # pep8-naming
    "SIM",   # flake8-simplify
    "RUF",   # Ruff-native rules
]
ignore = [
    "S101",  # allow assert in tests
]

[lint.per-file-ignores]
"alembic/env.py" = ["S", "I001"]  # alembic template; skip security + isort

[format]
quote-style = "double"
indent-style = "space"
```

### Anti-Patterns to Avoid

- **Module-level engine singleton:** `engine = create_async_engine(...)` at module import time. Prevents test isolation. Always use lifespan (D-06).
- **`@app.on_event("startup")`:** Deprecated in FastAPI. Use `lifespan=` on `FastAPI()` constructor (D-08).
- **Binding contextvars without clearing first:** Cross-request bleed in async workers. Always `clear_contextvars()` before `bind_contextvars()` (D-09).
- **`import-linter` with `root_package` (singular):** Phase 2 has only one root package (`app`), so `root_package = app` also works, but `root_packages = \n    app` is future-proof if `workers` or `integrations` ever become separate packages.
- **Adding middleware in "execution order":** `app.add_middleware()` call order is reversed from execution order. See Pitfall 1 below.
- **`[tool.uv] dev-dependencies`:** Deprecated. Use `[dependency-groups]`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async SQLAlchemy session | Custom context manager | `async_sessionmaker` from SQLAlchemy 2.0 | Handles commit/rollback/close edge cases |
| Request-scoped logging context | Thread-local dict | `structlog.contextvars` | asyncio-safe; survives `await` boundary |
| Environment config loading | `os.environ.get()` calls | `pydantic-settings BaseSettings` | Validation, type coercion, dotenv support |
| Async database migrations | Sync `psycopg2` in migration | `async_engine_from_config` + `run_sync` wrapper | Required for asyncpg driver |
| Import boundary enforcement | Code review | `import-linter` contracts | Machine-enforced; catches day-1 violations |
| UUID generation for request IDs | hashlib/custom | `uuid.uuid4()` + `str()` | Standard; no dependency |
| Background job retry / TTL | Custom Redis logic | ARQ `WorkerSettings` | ARQ handles retry, TTL, serialization |

**Key insight:** Every "hand-rolled" solution in this stack has a 3-6 month half-life before an edge case in async context management, ASGI scoping, or Postgres connection pooling breaks it silently. Use the standard tools.

---

## Common Pitfalls

### Pitfall 1: Middleware add_middleware Ordering (REVERSED)

**What goes wrong:** Developer writes `register_middleware()` that calls `app.add_middleware(RequestIdMiddleware)` then `app.add_middleware(TimingMiddleware)`. Expects RequestId to run first. It runs second.

**Why it happens:** FastAPI/Starlette's `app.add_middleware()` wraps the current stack: the last added middleware is the outermost (runs first on request path). This is counterintuitive — it's a stack, not a queue.

**How to avoid:**
```python
def register_middleware(app: FastAPI) -> None:
    app.add_middleware(TimingMiddleware)     # added first → innermost → runs SECOND on request
    app.add_middleware(RequestIdMiddleware)  # added second → outermost → runs FIRST on request
```

**Warning signs:** Timing logs appear without a `request_id` field (structlog context not yet bound when TimingMiddleware starts).

---

### Pitfall 2: Async Alembic env.py — Do Not Import `app.main`

**What goes wrong:** `env.py` imports `create_app()` or `app` to access `Base.metadata`. This triggers FastAPI app instantiation, lifespan setup, and structlog configuration at migration time.

**Why it happens:** Naive pattern of sharing app reference to access metadata.

**How to avoid:** Import `Base` directly from `app.core.database` and `Settings` from `app.core.config`. Never import `create_app` in `env.py`.

**Warning signs:** Alembic prints FastAPI startup logs, or fails because DATABASE_URL is not set when running `alembic revision`.

---

### Pitfall 3: `pydantic-settings` extra='ignore' vs 'forbid'

**What goes wrong:** Using `extra='forbid'` means any env var present in the environment but not declared in `Settings` raises a `ValidationError`. CI machines with broad env sets will fail `uv run uvicorn`.

**Why it happens:** `extra='forbid'` is useful for strict local development but impractical in production/CI where many unrelated env vars exist.

**How to avoid:** Use `extra='ignore'` (locked in D-15 discretion). This is correct for a FastAPI app.

---

### Pitfall 4: structlog `merge_contextvars` Position in Processor Chain

**What goes wrong:** `merge_contextvars` placed after renderers. Context vars don't appear in output.

**Why it happens:** Processors execute in order; `merge_contextvars` must be early in the chain so subsequent processors see the bound `request_id`, `path`, `method` keys.

**How to avoid:** Always place `merge_contextvars` as the first processor in the chain.

---

### Pitfall 5: `independence` Contract and Transitive Imports

**What goes wrong:** Module A imports `app.core.utils`. Module B imports `app.core.utils`. import-linter incorrectly raises an independence violation.

**Why it happens:** `independence` type checks for direct AND indirect imports between the listed modules. `app.core` is a shared dependency — if A or B imports from each other transitively through a third module, it will flag.

**How to avoid:** The `independence` contract in D-01 lists `app.modules.X` packages. As long as no module imports from another `app.modules.*` package (directly or transitively), the contract passes. All imports from `app.core` are fine because `app.core` is not in the `modules` list.

**Warning signs:** `lint-imports` fails on new module that transitively reaches another `app.modules.*` via an unexpected import chain.

---

### Pitfall 6: `uv run alembic upgrade head` with Empty `versions/`

**What goes wrong:** Executor sees "nothing happened" and assumes it failed.

**Why it happens:** Alembic with no migration files and no `alembic_version` table just silently exits 0. This is correct behavior for ROADMAP success criterion #5 — the test is that `env.py` can connect and read `Settings`, not that migrations ran.

**How to avoid:** Run against a real (empty) Postgres database. The check is exit code 0 + no Python errors (not "at least one migration ran"). ROADMAP criterion #5 says "succeeds against an empty database (no migration files in `alembic/versions/`)".

---

### Pitfall 7: `root-level backend/` Directory Conflict

**What goes wrong:** Phase 2 creates `apps/backend/` but the empty `backend/` directory at the repo root (from Phase 1, D-15) is still there.

**Why it happens:** Phase 1 D-15 explicitly left `./backend/` in place. Phase 2 lands at `apps/backend/`.

**How to avoid:** Phase 2's plan should include a task to delete the empty root-level `backend/` as part of setup. Confirmed: `backend/` exists at repo root and is completely empty (no files). [VERIFIED: `find` 2026-04-30]

---

### Pitfall 8: Synthetic Violation Test (D-05) — Correct Target Module

**What goes wrong:** Executor inserts `from app.modules.members import x` into the wrong file (e.g., one that isn't under `app.core.*`), doesn't violate any contract, lint-imports passes, executor concludes contracts are broken.

**Why it happens:** The forbidden contract catches `app.core → app.modules` and `app.integrations → app.modules`. Not `app.api → app.modules` (that's allowed per D-02).

**How to avoid:** For the core contract test, insert the illegal import into `app/core/config.py` or `app/core/database.py`. For the independence test, insert `from app.modules.members import x` into `app/modules/auth/__init__.py`. Both must cause non-zero exit from `uv run lint-imports`.

---

## File Creation Manifest

Complete ordered list of all files Phase 2 must create. Files with `[PLACEHOLDER]` contain only a module docstring and no functional code (except `__init__.py` which can be empty).

**Wave 0 — Project scaffold (prerequisite for all other waves):**
```
apps/backend/
  pyproject.toml
  ruff.toml
  importlinter.ini
  alembic.ini
  .env.example
  .gitignore
  uv.lock                     ← generated by `uv lock`, then committed
```

**Wave 1 — Core Python package initialization:**
```
apps/backend/app/__init__.py
apps/backend/app/core/__init__.py
apps/backend/app/modules/__init__.py
apps/backend/app/integrations/__init__.py
apps/backend/app/workers/__init__.py
apps/backend/app/api/__init__.py
apps/backend/app/api/v1/__init__.py
```

**Wave 2 — Core modules (can parallel-write after Wave 1):**
```
apps/backend/app/core/config.py          Settings, get_settings()
apps/backend/app/core/database.py        db_lifespan, Base, get_db
apps/backend/app/core/logging.py         configure_logging()
apps/backend/app/core/exceptions.py      AppError hierarchy + register_exception_handlers
apps/backend/app/core/middleware.py      RequestIdMiddleware, TimingMiddleware, register_middleware
apps/backend/app/core/security.py        [PLACEHOLDER] TODO Phase C+
apps/backend/app/core/dependencies.py   [PLACEHOLDER] shared Depends
apps/backend/app/core/pagination.py     LimitOffsetParams, Page[T]
```

**Wave 3 — API surface (depends on Wave 2 core being importable):**
```
apps/backend/app/main.py                 create_app()
apps/backend/app/api/router.py           api = APIRouter() + include v1
apps/backend/app/api/v1/router.py        v1 = APIRouter() + include health
apps/backend/app/api/v1/health.py        GET /healthz
```

**Wave 4 — Module placeholders (parallel with Wave 3):**
```
apps/backend/app/modules/auth/__init__.py
apps/backend/app/modules/auth/router.py      APIRouter() — no endpoints, TODO Phase C+
apps/backend/app/modules/auth/service.py     [PLACEHOLDER]
apps/backend/app/modules/auth/models.py      [PLACEHOLDER]
apps/backend/app/modules/auth/schemas.py     [PLACEHOLDER]
apps/backend/app/modules/members/__init__.py
apps/backend/app/modules/memberships/__init__.py
apps/backend/app/modules/visits/__init__.py
apps/backend/app/modules/trainers/__init__.py
apps/backend/app/modules/schedule/__init__.py
apps/backend/app/modules/bookings/__init__.py
apps/backend/app/modules/billing/__init__.py
apps/backend/app/modules/notifications/__init__.py
```

**Wave 5 — Integration + worker placeholders (parallel with Wave 3/4):**
```
apps/backend/app/integrations/telegram/__init__.py
apps/backend/app/integrations/telegram/bot.py       [PLACEHOLDER]
apps/backend/app/integrations/telegram/handlers.py  [PLACEHOLDER]
apps/backend/app/integrations/telegram/sender.py    [PLACEHOLDER]
apps/backend/app/integrations/email/__init__.py
apps/backend/app/integrations/email/client.py       [PLACEHOLDER]
apps/backend/app/integrations/email/templates/.gitkeep
apps/backend/app/workers/__init__.py
apps/backend/app/workers/arq_app.py                 WorkerSettings skeleton
apps/backend/app/workers/scheduler.py               [PLACEHOLDER]
apps/backend/app/workers/tasks/__init__.py
apps/backend/app/workers/tasks/notifications.py     [PLACEHOLDER]
apps/backend/app/workers/tasks/reminders.py         [PLACEHOLDER]
apps/backend/app/workers/tasks/reports.py           [PLACEHOLDER]
```

**Wave 6 — Alembic (parallel with other waves, depends only on Wave 2 core):**
```
alembic/env.py                           async migration setup (reads Settings)
alembic/script.py.mako                   standard alembic template
alembic/versions/.gitkeep
```

**Cleanup task (can be Wave 0):**
```
DELETE: /apps/../backend/    ← empty root-level backend/ dir must be removed
```

**Total files to create:** ~47 files + 1 directory deletion.

---

## Synthetic Violation Verification Recipe (D-05 / ROADMAP #3)

This is an **ad-hoc plan task** (not a committed script). Executor steps:

```bash
# Step 1: Verify contracts pass on clean tree
cd /path/to/clubcore/apps/backend
uv run lint-imports
# Expected: exit 0, all contracts KEPT

# Step 2: Insert violation in core (tests the forbidden contract)
echo "from app.modules.members import x  # SYNTHETIC VIOLATION" \
  >> app/core/config.py

# Step 3: Verify contracts fail
uv run lint-imports
# Expected: exit non-zero, "core-not-depend-on-modules" contract BROKEN

# Step 4: Revert
git checkout app/core/config.py

# Step 5: Insert violation in modules (tests the independence contract)
echo "from app.modules.members import x  # SYNTHETIC VIOLATION" \
  >> app/modules/auth/__init__.py

# Step 6: Verify independence contract fails
uv run lint-imports
# Expected: exit non-zero, "modules-independent" contract BROKEN

# Step 7: Revert
git checkout app/modules/auth/__init__.py

# Step 8: Verify clean again
uv run lint-imports
# Expected: exit 0
```

**Note:** The synthetic violation file modification must happen to files that are actually in the import graph. Empty `__init__.py` files may not be scanned by import-linter's grimp graph builder unless they have at least one import statement. If `app/modules/auth/__init__.py` is empty, add `from app.modules.auth import schemas` to make it graphable first.

---

## ruff + mypy "Fails Loudly" Recipe (ROADMAP #4)

```bash
cd /path/to/clubcore/apps/backend

# Ruff check (exit non-zero if any violations)
uv run ruff check .
# Expected: exit 0 (clean skeleton)

# Ruff format check (exit non-zero if formatting differs)
uv run ruff format --check .
# Expected: exit 0

# mypy strict (exit non-zero if any type errors)
uv run mypy app
# Expected: exit 0 (clean skeleton with all type annotations)
```

**Common mypy gotchas on this stack:**

1. `alembic/env.py` needs the override: `disable_error_code = ["no-untyped-call"]` — otherwise `do_run_migrations(connection)` raises `error: Function is missing a return type annotation`.

2. `async def get_db(request: Request) -> AsyncIterator[AsyncSession]:` — must be `AsyncIterator`, not `AsyncGenerator`. Import from `collections.abc`.

3. `class WorkerSettings: functions: list = []` — mypy strict complains about bare `list`. Use `list[Any]` with `from typing import Any` or `list[Coroutine[Any, Any, Any]]`.

4. Placeholder modules with only a docstring are clean; mypy skips files with no typed code in strict mode when using `--ignore-missing-imports` (not needed here — all deps are installed).

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | All Python tooling | ✓ | 0.11.6 | — |
| Python 3.12 | D-00 stack pin | ✓ | 3.12.12 (via uv managed) | — |
| PostgreSQL 16 | DB-01, DB-02 (alembic upgrade) | ✗ | — | Skip DB tests; alembic upgrade fails without DB |
| Redis 7 | WORK-01 (ARQ), Phase 3 tests | ✗ | — | ARQ WorkerSettings still creatable without live Redis |
| pip (for version checks) | Version verification | ✓ | via Python 3.14 system | — |

**Missing dependencies with no fallback:**
- PostgreSQL 16 is required for ROADMAP success criterion #5 (`alembic upgrade head` against empty DB). The Phase 3 docker-compose will provide it. For Phase 2 execution: either start a local Postgres or skip criterion #5 until Phase 3. Plan should note this dependency explicitly.

**Missing dependencies with fallback:**
- Redis 7: `WorkerSettings` class can be defined and mypy/ruff checked without a live Redis. `RedisSettings.from_dsn()` is called at import time — if Postgres/Redis are not running, the `get_settings()` call will succeed (Settings validation is URL format only, not connectivity). ARQ does not connect at import.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` | `lifespan=` context manager | FastAPI 0.93 | `on_event` deprecated; lifespan is the canonical pattern |
| `[tool.uv] dev-dependencies` | `[dependency-groups] dev` (PEP 735) | uv 0.4.27 | `tool.uv.dev-dependencies` deprecated (still works but will warn) |
| `ruff` config under `[tool.ruff.lint]` in pyproject.toml | Same key in `ruff.toml` as `[lint]` (no `tool.ruff` prefix) | ruff 0.2+ | Both work; standalone `ruff.toml` uses shorter keys |
| SQLAlchemy mypy plugin (`sqlalchemy.ext.mypy.plugin`) | No plugin needed | SQLAlchemy 2.0 | SA 2.0 has native PEP 484 typing; legacy plugin removed |
| Starlette `BaseHTTPMiddleware` | Same (still canonical) | — | No change; still the right tool |

**Deprecated/outdated:**
- `@app.on_event`: Works but deprecated since FastAPI 0.93. Never use in new code.
- `sessionmaker` (sync): Do not use in async context. Use `async_sessionmaker` (added SA 2.0).
- `[tool.uv] dev-dependencies`: Will produce deprecation warnings in future uv releases. Use `[dependency-groups]`.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `alembic upgrade head` exits 0 with empty `versions/` (only `.gitkeep`) | Pitfall 6, ROADMAP #5 | ROADMAP criterion #5 fails; plan may need "alembic init" step instead | 

**All other claims in this document were verified via Context7, official pip registry, or live Python execution on 2026-04-30.**

---

## Open Questions

1. **ROADMAP criterion #5 — Live Postgres required**
   - What we know: `alembic upgrade head` requires a live database connection. Phase 3's `docker-compose.yml` is not yet written.
   - What's unclear: Whether the Phase 2 plan executor will have a local Postgres 16 available, or whether criterion #5 is deferred to Phase 3.
   - Recommendation: Plan should include a note that criterion #5 passes only if a local Postgres is available. Mark it conditional; Phase 3 provides the Docker environment.

2. **Root-level `backend/` deletion ownership**
   - What we know: Empty `backend/` directory exists at repo root. D-15 said Phase 1 could leave it. Phase 2 creates `apps/backend/`.
   - What's unclear: Whether deleting `backend/` is Wave 0 of Phase 2 or out of scope.
   - Recommendation: Include it as a Wave 0 cleanup task — it's a 1-second `rmdir` and prevents confusion.

---

## Sources

### Primary (HIGH confidence — Context7 / official docs / live verification)

- Context7 `/websites/fastapi_tiangolo` — lifespan events, middleware, APIRouter aggregation, add_middleware ordering [VERIFIED]
- Context7 `/websites/sqlalchemy_en_20` — `create_async_engine`, `async_sessionmaker`, `AsyncSession`, `pool_pre_ping` [VERIFIED]
- Context7 `/websites/alembic_sqlalchemy` — async env.py cookbook pattern, `async_engine_from_config`, `run_sync` wrapper [VERIFIED]
- Context7 `/pydantic/pydantic-settings` — `SettingsConfigDict`, `env_file`, `PostgresDsn`, `RedisDsn`, `SecretStr` [VERIFIED]
- Context7 `/hynek/structlog` — `contextvars`, `merge_contextvars`, `clear_contextvars`, `ConsoleRenderer`, `JSONRenderer`, processor chain [VERIFIED]
- Context7 `/seddonym/import-linter` — `forbidden` contract semantics, `independence` contract semantics, `root_packages` [VERIFIED]
- Context7 `/python-arq/arq` — `WorkerSettings`, `RedisSettings.from_dsn` [VERIFIED]
- Context7 `/astral-sh/ruff` — `[lint]` section syntax, `select`, `per-file-ignores` [VERIFIED]
- Context7 `/python/mypy` — `[tool.mypy]`, `strict = true`, `[[tool.mypy.overrides]]` [VERIFIED]
- Context7 `/pydantic/pydantic` — `pydantic.mypy` plugin config for pyproject.toml [VERIFIED]
- Context7 `/astral-sh/uv` — `[dependency-groups]`, `tool.uv.dev-dependencies` deprecation, `uv lock` [VERIFIED]
- Live Python test: `pydantic.PostgresDsn` validates `postgresql+asyncpg://` scheme — confirmed 2026-04-30 [VERIFIED]
- `pip index versions` for all 11 packages — current versions confirmed 2026-04-30 [VERIFIED]
- `uv python list` — Python 3.12.12 available via uv managed [VERIFIED]
- Filesystem check: `apps/backend/` does not exist yet; `backend/` (root) is empty [VERIFIED]

### Secondary (MEDIUM confidence)

- FastAPI docs re: middleware execution order (verified in Context7 and consistent with Starlette source behavior) [CITED: Context7 /websites/fastapi_tiangolo]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions confirmed via pip registry 2026-04-30
- Architecture: HIGH — all patterns verified via Context7 official docs
- Pitfalls: HIGH — middleware ordering verified via official FastAPI docs; other pitfalls from first-principles analysis of verified patterns
- Code examples: HIGH — shapes derived from Context7 patterns + locked decisions

**Research date:** 2026-04-30
**Valid until:** 2026-05-30 (stable ecosystem; SQLAlchemy 2.0/FastAPI 0.11x are not moving fast on APIs)
