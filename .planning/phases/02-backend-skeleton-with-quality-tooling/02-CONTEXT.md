# Phase 2: Backend Skeleton with Quality Tooling - Context

**Gathered:** 2026-04-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Bring up `apps/backend/` as a runnable FastAPI modular monolith with the architectural style (`core` / `modules` / `integrations` / `workers` / `api`) physically realized. Single real endpoint `GET /healthz` returning `{"status":"ok"}`. Async Alembic configured with empty `versions/`. ruff + mypy strict + import-linter contracts that fail loudly on any violation, enforceable locally from day one.

**In scope (Phase 2):** apps/backend/{pyproject.toml, ruff.toml, importlinter.ini, alembic.ini, .env.example, .gitignore}, app/{main.py, core/*, modules/{auth,members,…,notifications}/__init__.py (+ auth's empty placeholder files), integrations/{telegram,email}/* placeholders, workers/{arq_app.py, scheduler.py, tasks/*.py} placeholders, api/{router.py, v1/{router.py, health.py}}}, alembic/{env.py, script.py.mako, versions/.gitkeep}.

**Out of scope (Phase 2 — owned by Phase 3 or later):**
- pytest scaffold, conftest fixtures, test_healthz, test_security (Phase 3: TEST-01..04)
- Dockerfile, docker-compose.yml, scripts/ (Phase 3: INFRA-01..04)
- architecture.md / conventions.md / ADR / README.md (Phase 3: DOCS-01..04)
- Any business logic, business tables, business migrations, real auth, real Telegram/SMTP, ЮKassa
- CORS config, real SECRET_KEY usage (deferred to phases that need them)

</domain>

<decisions>
## Implementation Decisions

### Architectural inheritance (LOCKED upstream — recorded for downstream agents)
- **D-00 [LOCKED]:** Stack pinned by PROJECT.md/CLAUDE.md and not negotiable: Python 3.12 + uv + FastAPI 0.115+ + SQLAlchemy 2.0 async + Alembic async + Pydantic v2 + pydantic-settings + asyncpg + Postgres 16 + Redis 7 + ARQ + structlog + httpx. Package name is `app` (not `sportzal`, not `src/sportzal`). Layout is flat at `apps/backend/app/`, NOT `apps/backend/src/app/`.

### import-linter contract style (Area 1)
- **D-01 [LOCKED]:** `apps/backend/importlinter.ini` uses **mixed contract types** — `forbidden` for the two source→target rules and `independence` for the pairwise modules rule. Not pure layers, not all-forbidden. Concrete shape:

  ```ini
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

- **D-02 [LOCKED]:** `app.api → app.modules.*` is **allowed**. `app/api/v1/router.py` does `from app.modules.<name>.router import router as <name>_router; v1.include_router(<name>_router, prefix='/<name>', tags=['<name>'])`. Canonical FastAPI router-aggregation pattern. No contract added; no registry indirection. (In Phase A only `auth` has a `router.py`, but it has no endpoints — wiring may be commented out with TODO until first business module lands.)

- **D-03 [LOCKED]:** `app.workers → app.integrations` and `app.modules → app.integrations` are **allowed**. No contract restricts these directions. The "events bus → workers consume" pattern is deferred (no events in Phase A).

- **D-04 [LOCKED]:** `app.integrations → app.core` is **allowed** (integrations read `Settings` and use `structlog`). Only the inverse (`core → modules`) and (`integrations → modules`) are blocked, as already stated in D-01.

- **D-05 [LOCKED]:** Synthetic-violation verification (ROADMAP success criterion #3) is performed as an **ad-hoc plan task during execute-phase**, not committed: executor temporarily inserts `from app.modules.members import x` (or similar) into `app/core/config.py`, runs `uv run lint-imports`, asserts non-zero exit, reverts. No permanent script in Phase 2 (a CI check belongs in Phase 3 if needed).

### create_app() composition & lifespan (Area 2)
- **D-06 [LOCKED]:** Async SQLAlchemy engine is **lifespan-managed**. `app/core/database.py` exposes `db_lifespan(app)` as `@asynccontextmanager async def`. On startup it creates the engine via `create_async_engine(str(settings.database_url), pool_pre_ping=True, echo=settings.debug)` and an `async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)`, stashing both on `app.state.engine` and `app.state.sessionmaker`. On shutdown it `await engine.dispose()`. NOT module-level engine creation.

- **D-07 [LOCKED]:** `get_db` dependency reads from `request.app.state.sessionmaker`:
  ```python
  async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
      sessionmaker = request.app.state.sessionmaker
      async with sessionmaker() as session:
          yield session
  ```
  Per-test app instances therefore get their own engine without monkey-patching.

- **D-08 [LOCKED]:** `create_app()` factory in `app/main.py` composes via `FastAPI(lifespan=db_lifespan, ...)`. Other startup/shutdown work (logging setup, future integrations init) is added to the same lifespan as needed; no separate `@app.on_event` handlers.

### Observability & middleware (Area 2)
- **D-09 [LOCKED]:** Request ID propagation is implemented as a **custom ASGI middleware in `app/core/middleware.py`**. Reads incoming `X-Request-ID` header or generates a UUID4. Binds `request_id`, `path`, `method` to `structlog.contextvars`. Sets `X-Request-ID` on the outgoing response. Calls `structlog.contextvars.clear_contextvars()` at the start of each `dispatch` call to prevent cross-request bleed. Concrete shape:
  ```python
  class RequestIdMiddleware(BaseHTTPMiddleware):
      HEADER = 'X-Request-ID'
      async def dispatch(self, request, call_next):
          request_id = request.headers.get(self.HEADER) or str(uuid.uuid4())
          structlog.contextvars.clear_contextvars()
          structlog.contextvars.bind_contextvars(
              request_id=request_id, path=request.url.path, method=request.method,
          )
          response = await call_next(request)
          response.headers[self.HEADER] = request_id
          return response
  ```

- **D-10 [LOCKED]:** **No third-party correlation library** (no `asgi-correlation-id` dependency). Write our own ~30 lines.

- **D-11 [LOCKED]:** `app/core/middleware.py` also defines a `TimingMiddleware` (placeholder is fine for Phase A — logs request duration via structlog) and exposes `register_middleware(app: FastAPI)` that adds them in the correct order: RequestIdMiddleware first, TimingMiddleware second. CORS middleware is **deferred** with a TODO comment: `# TODO Phase X: CORS once frontend integrates`.

### Exception handling (Area 2)
- **D-12 [LOCKED]:** Domain error classes live in `app/core/exceptions.py` with class-level `code: str` and `status_code: int`:
  - `AppError` (500, `app_error`) — base
  - `NotFoundError` (404, `not_found`)
  - `ForbiddenError` (403, `forbidden`)
  - `ConflictError` (409, `conflict`)
  - `ValidationAppError` (422, `validation_error`)
  Constructor: `__init__(message: str, *, fields: dict | None = None)` — sets `self.message` and `self.fields`.

- **D-13 [LOCKED]:** The same file (`app/core/exceptions.py`) defines `register_exception_handlers(app: FastAPI) -> None` and the handler function. Handler returns `JSONResponse(status_code=exc.status_code, content={'code': exc.code, 'message': exc.message, 'fields': exc.fields})`. `main.py` calls `register_exception_handlers(app)` once during `create_app()`. NOT inline `@app.exception_handler` decorators in main.py; NOT in middleware.py.

### API surface — `/healthz` placement (Area 2 wrap-up)
- **D-14 [LOCKED]:** `GET /healthz` is mounted at the **root path** `/healthz` (response: `{"status":"ok"}`), but routes through the v1 router with an empty prefix. Wiring:
  - `app/api/v1/health.py` → `router = APIRouter()` with `@router.get('/healthz') -> dict`
  - `app/api/v1/router.py` → `v1 = APIRouter(); v1.include_router(health.router)`
  - `app/api/router.py` → `api = APIRouter(); api.include_router(v1)` (empty prefix in Phase A)
  - `main.create_app()` → `app.include_router(api)`

  Result: `curl http://localhost:8000/healthz` returns 200 with `{"status":"ok"}`. Both API-02 ("v1 router includes health") and ROADMAP success criterion #2 (curl at root) are satisfied. The `/api/v1` prefix gets added at `api.include_router(v1, prefix='/api/v1')` when the **first business module lands** (Phase B+) — at that point health may move or stay (decided in that phase). Explicit `# TODO Phase B+: add /api/v1 prefix; reconcile /healthz path` comment goes in `app/api/router.py`.

### Claude's Discretion
The user opted not to discuss tooling depth or Settings shape. Default to canonical, idiomatic patterns matching the locked stack:

- **ruff rule families** — beyond the named ones (E, F, I, B, UP, ASYNC, S), enable at minimum: `DTZ` (datetime hygiene — important since the project pins Europe/Moscow), `N` (PEP 8 naming), `SIM` (simplifications), `RUF` (ruff-native rules). Line length: **100** (matches the frontend Prettier `printWidth`).
- **mypy strict configuration** — `[tool.mypy] strict = true` in `pyproject.toml`. Enable `pydantic.mypy` plugin. **Do NOT** enable a separate sqlalchemy mypy plugin (SQLAlchemy 2.0 ships native PEP 484 typing; the legacy plugin is not needed). Per-module overrides: `[[tool.mypy.overrides]] module = "alembic.env"; disable_error_code = ["no-untyped-call"]` (alembic `env.py` instantiates engine config at runtime).
- **Settings shape** — `pydantic-settings` `Settings` class in `app/core/config.py`:
  - `database_url: PostgresDsn` (required, no default)
  - `redis_url: RedisDsn` (required, no default)
  - `environment: Literal['dev', 'staging', 'prod'] = 'dev'`
  - `debug: bool = False`
  - `secret_key: SecretStr` (required — present so the Settings shape is stable when auth lands; not used in Phase A)
  - `model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')`
  - **No env var prefix** — raw `DATABASE_URL` / `REDIS_URL` / `ENVIRONMENT` / `DEBUG` / `SECRET_KEY`. Matches Postgres/Redis ecosystem conventions and 12-factor expectations.
  - `get_settings()` is `@lru_cache` cached.
- **structlog dev-vs-prod renderer** — driven by `Settings.environment`: `ConsoleRenderer(colors=True)` for `'dev'`, `JSONRenderer()` for `'staging'` and `'prod'`. NOT TTY auto-detection, NOT a separate `DEBUG` flag.
- **`.env.example` contents** — working dev defaults, not just placeholders, so a fresh checkout works against the Phase 3 docker-compose Postgres without edits:
  ```
  DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/sportzal
  REDIS_URL=redis://localhost:6379/0
  ENVIRONMENT=dev
  DEBUG=true
  SECRET_KEY=change-me-dev-only-not-secret
  ```
- **uv project layout** — `pyproject.toml` with `[project] name="sportzal-backend", requires-python=">=3.12,<3.13"`, `[tool.uv] dev-dependencies = [...]` for ruff/mypy/import-linter/pytest/pytest-asyncio. `uv.lock` IS committed.
- **`.gitignore`** — at minimum `.venv/`, `__pycache__/`, `.mypy_cache/`, `.ruff_cache/`, `*.pyc`, `.pytest_cache/`, `.coverage`. Not `uv.lock` (lockfile is committed).
- **`app/core/security.py` placeholder** — empty module with module-level docstring "TODO Phase C+: password hashing, JWT issue/verify". No stub functions raising NotImplementedError.
- **ARQ `WorkerSettings`** — `app/workers/arq_app.py` defines `class WorkerSettings: functions: list = []; redis_settings = RedisSettings.from_dsn(get_settings().redis_url)`. No real tasks. `tasks/notifications.py`, `tasks/reminders.py`, `tasks/reports.py` are placeholder modules with module-level docstring TODO.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project specs (must read)
- `CLAUDE.md` — project instructions; locks the backend stack, package naming (`app`), modular-monolith layout, regional constraints (Stripe forbidden, ЮKassa-only).
- `.planning/PROJECT.md` — milestone scope, architectural invariants (`core ⊥ modules`, `modules` not importing each other), key decisions table, region constraints.
- `.planning/REQUIREMENTS.md` — Phase 2 owns these requirement IDs (every plan task must trace to one or more): BE-01..BE-10, MOD-01..MOD-03, INT-01..INT-02, WORK-01..WORK-03, API-01..API-03, DB-01..DB-02, TOOL-01..TOOL-06.
- `.planning/ROADMAP.md` — Phase 2 section: goal, dependency on Phase 1, six numbered success criteria. ROADMAP success criteria are the verification battery for `/gsd-verify-phase`.

### Cross-phase context
- `.planning/phases/01-monorepo-restructure-frontend-move/01-CONTEXT.md` — Phase 1 LOCKED decisions Phase 2 must honor: monorepo lives at root with `apps/`, `packages/`, `infra/`; `apps/admin-web` is the relocated frontend (do not touch); `apps/client-web` does NOT exist; placeholder packages contain only `package.json` + `README.md`.
- `.planning/phases/01-monorepo-restructure-frontend-move/01-VERIFICATION.md` — Phase 1 verification battery (D-16 gates) confirming the monorepo skeleton Phase 2 lands inside.

### Background context (not load-bearing for backend)
- `.planning/codebase/ARCHITECTURE.md` — describes the existing **frontend** FSD-lite layering. Backend reuses none of it. Useful only as a sibling reference: when frontend eventually flips `VITE_API_MODE=http` (deferred to Phase X+), the API contract that backend exposes must satisfy the frontend's swap-seam expectations.
- `.planning/codebase/STACK.md` — frontend stack inventory; useful for Phase X+ frontend-integration planning.
- `.planning/codebase/STRUCTURE.md`, `CONVENTIONS.md`, `TESTING.md`, `INTEGRATIONS.md`, `CONCERNS.md` — frontend-only reference docs.

### External docs (consulted during research)
- FastAPI 0.115+ docs (lifespan events, dependency injection, factory pattern with `--factory`)
- SQLAlchemy 2.0 async docs (`create_async_engine`, `async_sessionmaker`, `AsyncSession`)
- Alembic async docs (`async def run_migrations_online`, async engine in `env.py`)
- pydantic-settings docs (`SettingsConfigDict`, `env_file`, `model_config`)
- structlog docs (`structlog.contextvars`, ConsoleRenderer vs JSONRenderer, FastAPI integration patterns)
- import-linter docs (`forbidden` vs `independence` vs `layers` contract types, root_packages config)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets
- **`apps/admin-web/`** — relocated frontend SPA. **Not consumed by Phase 2.** Future relevance: when `VITE_API_MODE=http` flips on (Phase X+), the OpenAPI contract that backend exposes will populate `packages/api-client/`. Phase 2 produces zero real endpoints beyond `/healthz`, so there's no contract surface to wire yet.
- **`pnpm-workspace.yaml`** at repo root — registers `apps/*` and `packages/*`. `apps/backend/` lives next to `apps/admin-web/` but is NOT a pnpm workspace (it's a Python project managed by uv). `pnpm install` does not touch it. No coordination needed.
- **`infra/docker/`, `infra/nginx/`** — empty directories with `.gitkeep`. Phase 2 does NOT add Dockerfiles here (Phase 3 owns INFRA-01/02). The Dockerfile in Phase 3 conventionally lives at `apps/backend/Dockerfile`, not `infra/docker/`, per INFRA-01 wording in REQUIREMENTS.md.

### Established patterns to honor
- **Modular monolith over Clean Architecture layers** — code lives next to feature (PROJECT.md). `core/` is infrastructure, `modules/` are vertical features, `integrations/` are outbound adapters, `workers/` are background processors, `api/` is the HTTP surface.
- **No multi-tenancy in Phase A** — never reference `tenant_id`, `ContextVar[Tenant]`, RLS, or `SET LOCAL` in any backend code. PROJECT.md is explicit: "Никаких упоминаний tenant в коде Phase A".
- **No auth in Phase A** — `app/core/security.py` is a placeholder; `app/modules/auth/router.py` has no endpoints. JWT, password hashing, refresh tokens — all Phase C+.
- **Russian-region constraints** — Stripe is forbidden forever; ЮKassa is the only payment provider (placeholder only in Phase A).

### Integration points
- **Phase 3 (Tests, Dev Infra, Documentation)** consumes Phase 2's output directly: `tests/conftest.py` will use the `create_app()` factory and the `db_lifespan` engine from D-06/D-08; `tests/integration/test_healthz.py` will hit the `/healthz` route from D-14; `apps/backend/Dockerfile` will install via uv; `apps/backend/docker-compose.yml` will set the `DATABASE_URL` and `REDIS_URL` env vars from D-15's Settings shape; `apps/backend/docs/architecture.md` will describe the import-linter contracts from D-01..D-05.
- **`alembic/env.py` reads `DATABASE_URL` from `Settings`** (per ROADMAP success criterion #5) — so D-15's Settings shape is also the contract for env.py.
- **Frontend swap seam (Phase X+, not Phase 2)** — when `VITE_API_MODE=http` lands, `apps/admin-web/src/shared/api/services/http/` will hit the FastAPI app via the OpenAPI types generated into `packages/api-client/`. Phase 2's `/healthz` is the only endpoint that exists yet, so no client wiring happens.

</code_context>

<specifics>
## Specific Ideas

- **User signal — "use canonical/idiomatic FastAPI patterns".** Across all 8 questions in Areas 1 & 2, the user accepted the recommended option. This is a strong directional signal: when planner/researcher hits an undocumented sub-decision in Phase 2, default to "the canonical FastAPI pattern" / "what the SQLAlchemy 2.0 async docs show in their first example" rather than introducing project-specific abstractions.
- **Synthetic violation as an explicit verification step in PLAN.md.** ROADMAP success criterion #3 is satisfied by an explicit ad-hoc plan task, not a permanent script. Planner: include this as its own task in the plan, not a footnote.
- **`/healthz` at root, not `/api/v1/healthz`.** Despite v1 router being the include path, the public URL stays at `/` so it matches Kubernetes liveness conventions and the curl command in ROADMAP success criterion #2. The `# TODO Phase B+` comment in `api/router.py` is mandatory — without it the next phase will silently mount business modules at root too.

</specifics>

<deferred>
## Deferred Ideas

- **CORS middleware configuration** — deferred to Phase X+ (when frontend `VITE_API_MODE=http` flip happens). Phase 2 leaves a `# TODO Phase X` comment in `app/core/middleware.py`.
- **`/api/v1` URL prefix** — deferred until the first business module lands (Phase B+). Phase 2 mounts v1 at empty prefix so `/healthz` resolves at root. `app/api/router.py` must carry an explicit `# TODO Phase B+: add /api/v1 prefix; reconcile /healthz path`.
- **Real auth logic in `core/security.py`** — Phase C+ (password hashing, JWT issue/verify). Phase 2 keeps it as an empty module with a TODO docstring.
- **Real Telegram/SMTP/ЮKassa calls** — Phase X+ (each in its own phase). Phase 2 keeps `integrations/telegram/*.py` and `integrations/email/*.py` as placeholder modules.
- **ARQ task implementations** — Phase B+ (real notifications/reminders/reports). Phase 2 ships `WorkerSettings` skeleton with empty `functions` list.
- **Pytest scaffold, conftest fixtures, test_healthz, test_security** — Phase 3 (TEST-01..04). Phase 2 produces no `tests/` directory.
- **Dockerfile, docker-compose.yml, scripts/seed_demo_data.py, scripts/backup_db.sh** — Phase 3 (INFRA-01..04). Phase 2 produces no Docker artifacts.
- **architecture.md / conventions.md / ADR 0001 / README.md** — Phase 3 (DOCS-01..04). Phase 2 produces no docs.
- **Permanent CI script for synthetic-violation check** — Phase 3 if needed. Phase 2 uses an ad-hoc plan task only (D-05).
- **In-process event bus / `workers consume domain events` pattern** — deferred until events exist (Phase B+). Until then, `modules → integrations` direct calls are allowed.

</deferred>

---

*Phase: 02-backend-skeleton-with-quality-tooling*
*Context gathered: 2026-04-30*
