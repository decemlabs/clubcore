# Phase 3: Tests, Dev Infrastructure & Documentation - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the verified Phase 2 backend skeleton **verifiable and operable**:
1. **Tests** — pytest scaffold with `httpx ASGITransport`, fixtures (`app`, `async_client`, `db_session`), `tests/integration/test_healthz.py` (real 200 + body shape), `tests/unit/test_security.py` placeholder, `tests/factories/__init__.py` empty for future factory-boy.
2. **Dev infra** — `apps/backend/Dockerfile` (multi-stage, slim Python 3.12, uv), `apps/backend/docker-compose.yml` (`backend` + `postgres:16` + `redis:7`), `scripts/seed_demo_data.py` (prints `"Phase A: no data to seed"`, exits 0), `scripts/backup_db.sh` (working `pg_dump` against the local Postgres container).
3. **Documentation** — `apps/backend/docs/architecture.md`, `docs/conventions.md`, `docs/adr/0001-modular-monolith.md`, and `apps/backend/README.md` describing the modular monolith, `core ⊥ modules` and inter-`modules` import-linter contracts, the test approach, and `uv sync` / `docker compose up` / `pytest` quick-start.

**Also closes Phase 2 deferred SC #5:** `uv run alembic upgrade head` succeeds against the empty containerized Postgres (no migration files in `alembic/versions/`, only `.gitkeep`).

**In scope (Phase 3):**
- `apps/backend/tests/{conftest.py, integration/test_healthz.py, unit/test_security.py, factories/__init__.py}` (TEST-01..04)
- `apps/backend/Dockerfile` + `apps/backend/docker-compose.yml` + `apps/backend/.dockerignore` (INFRA-01, INFRA-02)
- `apps/backend/scripts/seed_demo_data.py` + `apps/backend/scripts/backup_db.sh` (INFRA-03, INFRA-04)
- `apps/backend/docs/{architecture.md, conventions.md, adr/0001-modular-monolith.md}` + `apps/backend/README.md` (DOCS-01..04)
- pytest configuration in `pyproject.toml` (`[tool.pytest.ini_options]`: `asyncio_mode = "auto"`, `testpaths = ["tests"]`)
- One-time `alembic upgrade head` smoke run against the compose Postgres to retire Phase 2 SC #5

**Out of scope (Phase 3 — deferred):**
- Any business test (no business modules exist; only `/healthz` and a placeholder unit test)
- Production Dockerfile variants, Kubernetes, Helm, CI/CD pipelines (Phase X+)
- CORS, real auth, business migrations, business endpoints (Phase B+ / C+)
- Real Telegram / SMTP / ЮKassa integration tests (Phase X+)
- factory-boy factories, only the empty `tests/factories/__init__.py` placeholder per TEST-04
- `apps/admin-web` Docker / compose entries — frontend stays out of compose in Phase A
- `infra/docker/`, `infra/nginx/` — placeholders only; INFRA-01 wording locks the Dockerfile at `apps/backend/Dockerfile`
- Multi-tenant test fixtures, ContextVar/`tenant_id` references — forbidden per PROJECT.md

</domain>

<decisions>
## Implementation Decisions

### Architectural inheritance (LOCKED upstream — recorded for downstream agents)
- **D-00 [LOCKED]:** Stack is non-negotiable per PROJECT.md/CLAUDE.md/02-CONTEXT.md D-00. Tests use `pytest` + `pytest-asyncio` + `httpx.AsyncClient(transport=ASGITransport(app))` — never the real network. Per-test app comes from `from app.main import create_app`. Engine is per-app via `db_lifespan` (D-06/D-07/D-08 from Phase 2). Settings shape (`DATABASE_URL`, `REDIS_URL`, `ENVIRONMENT`, `DEBUG`, `SECRET_KEY`) per Phase 2 D-15 is the env contract that `docker-compose.yml` populates.

### Dockerfile pattern (Area 1)
- **D-01 [LOCKED]:** **Base image strategy = `python:3.12-slim` + uv copied from `ghcr.io/astral-sh/uv:latest`.** Multi-stage build. The builder stage is FROM `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` (or copies the `uv` binary `--from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/`); the final runtime stage is FROM `python:3.12-slim-bookworm` and does NOT carry `uv`. Pin `slim-bookworm` not `slim` alone to avoid silent debian-version drift.

- **D-02 [LOCKED]:** **uv layer split = deps-only first, then project.** Two `uv sync` invocations:

  ```dockerfile
  # Stage: builder (caches deps independent of source changes)
  COPY pyproject.toml uv.lock ./
  RUN --mount=type=cache,target=/root/.cache/uv \
      uv sync --frozen --no-install-project --no-dev

  # Then bring in source and finalize the install
  COPY app ./app
  RUN --mount=type=cache,target=/root/.cache/uv \
      uv sync --frozen --no-dev
  ```

  Final runtime image excludes ruff/mypy/import-linter/pytest (they live in `[tool.uv] dev-dependencies`). `uv.lock` is committed (Phase 2 D-15) so `--frozen` is the contract.

- **D-03 [LOCKED]:** **Non-root runtime user `app`.** Final stage:

  ```dockerfile
  RUN groupadd --system app && useradd --system --gid app --create-home app
  WORKDIR /app
  COPY --from=builder --chown=app:app /app /app
  USER app
  EXPOSE 8000
  CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
  ```

  CMD matches Phase 2 verification command exactly (`uv run uvicorn app.main:create_app --factory`). NO `alembic upgrade head` in entrypoint — migrations are a compose-orchestration concern (see D-12 Discretion).

- **D-04 [LOCKED]:** **Hot-reload lives in `docker-compose.yml`, not in the Dockerfile.** Dockerfile CMD stays prod-shape. `docker-compose.yml` overrides:

  ```yaml
  services:
    backend:
      command: uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --reload --reload-dir /app/app
      volumes:
        - ./app:/app/app:ro     # bind-mount source for reload
  ```

  One Dockerfile, dev-only behavior in compose. No `Dockerfile.dev`.

### Docs language + ADR (Area 2)
- **D-05 [LOCKED]:** **Mixed language for all four docs.** Narrative, headings, conceptual explanations → **Russian** (matches PROJECT.md / REQUIREMENTS.md / ROADMAP.md tone). Code blocks, command examples, file paths, ADR `## Context` snippets that contain commands or environment text → **English**. Concretely: `architecture.md`, `conventions.md`, `adr/0001-modular-monolith.md`, `README.md` are written this way. Identifiers, library names (`uv`, `ruff`, `mypy`, `import-linter`, `httpx ASGITransport`, etc.) stay in their canonical English form.

- **D-06 [LOCKED]:** **ADR template = MADR 4.0.** `docs/adr/0001-modular-monolith.md` follows the MADR 4.0 section set:

  ```
  # ADR-0001: Modular Monolith с физическим разделением core / modules / integrations / workers / api

  - Status: accepted
  - Date: 2026-05-01
  - Deciders: Andre

  ## Context and Problem Statement
  ## Decision Drivers
  ## Considered Options
  ## Decision Outcome
  ### Consequences
  ## Pros and Cons of the Options
  ```

  Future ADRs (`0002-*`, `0003-*`) follow the same shape so the directory scales predictably. NOT Nygard's classic 5-section template; NOT freeform.

- **D-07 [LOCKED]:** **`architecture.md` = reference depth, not cookbook.** Sections (Russian narrative, English code/diagrams):
  - `## Обзор` — что такое modular monolith и почему он, ссылка на ADR-0001
  - `## Слои` — `core` / `modules` / `integrations` / `workers` / `api` — что делает каждый слой, что НЕ делает, какие правила импорта
  - `## Архитектурные инварианты` — сжатый список из Phase 2 D-01..D-14 (`core ⊥ modules`, `modules ⊥ modules`, `integrations ⊥ modules`, factory pattern, lifespan-managed engine, `register_middleware` reverse order, exception handler placement, `/healthz` mount)
  - `## Запреты на Phase A` — нет multi-tenancy, нет auth, нет бизнес-таблиц, нет Stripe (региональное)
  - `## Диаграмма` — ASCII-only (mermaid не используем — README markdown viewers всё ещё разнородные)

  NO step-by-step "how to add a module" cookbook. That belongs in conventions.md if anywhere, but Phase A defers it.

- **D-08 [LOCKED]:** **`conventions.md` = reference depth, MUST contain a `## Testing` section.** Sections:
  - `## Naming` — Python identifiers (snake_case modules, PascalCase classes, UPPER_SNAKE constants), file naming, test file names (`test_*.py`)
  - `## Imports` — порядок (stdlib / third-party / `app.*`), запрет на cross-module imports внутри `app.modules`, путь только через events / explicit service interfaces (отложено до Phase B+)
  - `## Quality gates` — ruff (E/F/I/B/UP/ASYNC/S/DTZ/N/SIM/RUF), mypy strict, import-linter contracts (3 contracts из `.importlinter`); все три запускаются через `uv run`
  - `## Testing` — обязательный раздел: ASGITransport вместо реальной сети (constraint из CLAUDE.md), `pytest-asyncio` в `auto` режиме, фикстуры `app` / `async_client` / `db_session`, паттерн integration-теста для `/healthz`, раскладка `tests/{integration,unit,factories}/`. Закрепляет TEST-01..04 паттерн машинно-читаемо.
  - `## Logging` — structlog, `request_id`/`path`/`method` в contextvars, `ConsoleRenderer` для dev / `JSONRenderer` для staging+prod (Phase 2 D-15)
  - `## Errors` — `AppError` иерархия (Phase 2 D-12), `register_exception_handlers` в `create_app()`
  - `## Migrations` — alembic async, `alembic upgrade head`, `versions/.gitkeep` (Phase A пуст), naming для будущих миграций — placeholder

- **D-09 [LOCKED]:** **`README.md` quick-start = два явных пути (local uv + docker-compose), оба top-level.** Структура:
  ```
  # sportzal-backend
  Краткое описание (Russian, 2-3 строки).

  ## Quick start

  ### Вариант 1: локально (требует внешний Postgres + Redis)
  cp .env.example .env
  uv sync
  uv run uvicorn app.main:create_app --factory
  # → http://localhost:8000/healthz

  ### Вариант 2: docker compose (всё включено)
  cp .env.example .env
  docker compose up
  # → backend на :8000, postgres:16 на :5432, redis:7 на :6379

  ## Команды
  uv run pytest               # тесты (httpx ASGITransport)
  uv run ruff check .          # линтер
  uv run ruff format .         # форматирование
  uv run mypy app              # type check (strict)
  uv run lint-imports          # архитектурные контракты
  uv run alembic upgrade head  # применить миграции (в Phase A — ноль миграций)

  ## Документация
  - docs/architecture.md — модульный монолит, инварианты
  - docs/conventions.md — стиль кода, тестирование, миграции
  - docs/adr/ — ADR-каталог (0001 — modular monolith)
  ```

  Оба пути first-class. Никаких "for advanced users" сносок.

### Claude's Discretion

The user opted not to discuss `Test DB & fixtures` and `compose & alembic` directly — defer to canonical patterns matching Phase 2 D-00 signal ("use canonical/idiomatic FastAPI patterns"). Locked here so downstream agents have explicit defaults; user can override when reading this document.

- **D-10 (Discretion):** **Test DB strategy = require docker-compose Postgres up, NOT testcontainers.** Rationale: pet-project, single developer, INFRA-02 already provides `postgres:16` via compose for dev. Adding `testcontainers-python` doubles the dependency surface and slows local test runs. CONFTEST contract:
  - `tests/conftest.py` reads `DATABASE_URL` via `Settings`. If unset/unreachable, `db_session` fixture is `pytest.skip(reason="DATABASE_URL not reachable; run `docker compose up postgres` first")`.
  - `pytest` against the unit suite (`tests/unit/`) does NOT require Postgres — `test_security.py` is a pure-Python placeholder.
  - `pytest` against `tests/integration/test_healthz.py` does NOT require Postgres either — `/healthz` makes no DB query (Phase 2 verified). Integration test sets up the app via `create_app()` and hits `/healthz` via ASGITransport; no `db_session` use.
  - `db_session` fixture exists per TEST-01 spec but is **unused in Phase A tests**. It connects to the test DB via the lifespan-built `app.state.sessionmaker`, yields one session, and rolls back (no commit) on teardown. Phase B+ will exercise it when business modules land.

- **D-11 (Discretion):** **Test fixtures shape:**
  ```python
  # tests/conftest.py
  import pytest_asyncio
  from collections.abc import AsyncIterator
  from httpx import ASGITransport, AsyncClient
  from fastapi import FastAPI
  from sqlalchemy.ext.asyncio import AsyncSession

  from app.main import create_app

  @pytest_asyncio.fixture
  async def app() -> AsyncIterator[FastAPI]:
      _app = create_app()
      async with LifespanManager(_app):  # asgi-lifespan or manual __aenter__
          yield _app

  @pytest_asyncio.fixture
  async def async_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
      transport = ASGITransport(app=app)
      async with AsyncClient(transport=transport, base_url="http://test") as client:
          yield client

  @pytest_asyncio.fixture
  async def db_session(app: FastAPI) -> AsyncIterator[AsyncSession]:
      sessionmaker = app.state.sessionmaker
      async with sessionmaker() as session:
          yield session
          await session.rollback()
      ```
  - **Per-test `create_app()`** (function-scope) — matches Phase 2 D-08 docstring "Phase 3 conftest creates a new app per test". No global app singleton.
  - **`LifespanManager`** from `asgi-lifespan` (add to `[tool.uv] dev-dependencies`) — required for `app.state.sessionmaker` to be populated under ASGITransport (FastAPI lifespan doesn't fire on its own with `httpx.ASGITransport`). Alternative: manually call `await app.router.startup()` / `shutdown()`. The library is the canonical choice — adds ~50 LOC of correctness.
  - `pytest-asyncio` in `auto` mode → no `@pytest.mark.asyncio` decorators needed.

- **D-12 (Discretion):** **compose orchestration:**
  - **`alembic upgrade head` runs as a separate one-shot service**, not as backend entrypoint. Concrete shape:
    ```yaml
    services:
      backend:
        build: .
        depends_on:
          migrate:
            condition: service_completed_successfully
          redis:
            condition: service_started
        # ...

      migrate:
        build: .
        command: alembic upgrade head
        depends_on:
          postgres:
            condition: service_healthy
        env_file: .env

      postgres:
        image: postgres:16
        environment:
          POSTGRES_USER: app
          POSTGRES_PASSWORD: app
          POSTGRES_DB: sportzal
        healthcheck:
          test: ["CMD-SHELL", "pg_isready -U app -d sportzal"]
          interval: 2s
          timeout: 2s
          retries: 10
        volumes:
          - postgres-data:/var/lib/postgresql/data

      redis:
        image: redis:7
        # no healthcheck needed in Phase A; redis is fast and unused

    volumes:
      postgres-data:
    ```
  - **Postgres healthcheck via `pg_isready`** — required so the `migrate` service waits.
  - **Named volume `postgres-data`** — survives `docker compose down`, dropped via `docker compose down -v`.
  - **No exposed ports for redis** in Phase A (no host-side use yet); `postgres:5432` IS exposed for local IDE access; `backend:8000` IS exposed for `curl`.
  - **Bind-mount `./app:/app/app:ro`** for hot reload (D-04).
  - **`migrate` service is harmless when `versions/` is empty** — `alembic upgrade head` against zero revisions is a no-op + retires Phase 2 SC #5.

- **D-13 (Discretion):** **`scripts/` design.**
  - `scripts/seed_demo_data.py` — exactly per SC #3:
    ```python
    """Phase A placeholder. Real seeding lands in Phase B+ when business modules exist."""
    def main() -> int:
        print("Phase A: no data to seed")
        return 0

    if __name__ == "__main__":
        raise SystemExit(main())
    ```
    No DB connect. No imports from `app.*`. Pure Python so `uv run python apps/backend/scripts/seed_demo_data.py` works without a running compose stack.
  - `scripts/backup_db.sh` — bash, executable (`chmod +x`), targets the **compose-network** Postgres. Concrete shape:
    ```bash
    #!/usr/bin/env bash
    set -euo pipefail
    OUT="${1:-./backups/sportzal-$(date -u +%Y%m%dT%H%M%SZ).sql.gz}"
    mkdir -p "$(dirname "$OUT")"
    docker compose exec -T postgres pg_dump -U app -d sportzal | gzip > "$OUT"
    echo "Wrote $OUT ($(stat -f%z "$OUT" 2>/dev/null || stat -c%s "$OUT") bytes)"
    ```
    UTC-timestamped, gzip-compressed, defaults to `./backups/`. Output path overridable as `$1`. Uses `docker compose exec` so the script works regardless of host Postgres install state. SC #3 verifier check ("non-empty pg_dump output file") is satisfied by piping into a real file.
  - `apps/backend/.dockerignore` is added in this phase — excludes `.venv/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `__pycache__/`, `tests/`, `docs/`, `*.md`, `.env*`, `.git/`. Cuts build context and avoids leaking dev artifacts into the image.

- **D-14 (Discretion):** **pytest configuration in `pyproject.toml`** — no separate `pytest.ini`:
  ```toml
  [tool.pytest.ini_options]
  asyncio_mode = "auto"
  testpaths = ["tests"]
  python_files = ["test_*.py"]
  filterwarnings = [
      "error",
      "ignore::DeprecationWarning:pydantic.*",  # uv dev-dependencies deprecation noise
  ]
  ```

- **D-15 (Discretion):** **`asgi-lifespan` is added to `[tool.uv] dev-dependencies`** — only test code uses it. Production runtime never imports it. Constraint: `>=2.1`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project specs (must read)
- `CLAUDE.md` — locks the backend stack, package naming `app`, modular-monolith layout, regional constraints (Stripe forbidden, ЮKassa-only, Telegram primary).
- `.planning/PROJECT.md` — milestone scope, architectural invariants (`core ⊥ modules`, `modules` not importing each other), key decisions table.
- `.planning/REQUIREMENTS.md` — Phase 3 owns these requirement IDs (every plan task must trace to one or more): TEST-01..TEST-04, INFRA-01..INFRA-04, DOCS-01..DOCS-04. v2 sections (Auth, Business Domain, Integrations) are NOT in scope.
- `.planning/ROADMAP.md` — Phase 3 section: goal, dependency on Phase 2, four numbered success criteria. SC #2 explicitly retires Phase 2's deferred `alembic upgrade head` check.

### Cross-phase context (load-bearing)
- `.planning/phases/02-backend-skeleton-with-quality-tooling/02-CONTEXT.md` — Phase 2 LOCKED decisions Phase 3 must honor: D-00 (stack), D-06/D-07/D-08 (lifespan-managed engine, factory pattern), D-09/D-10/D-11 (middleware shape — RequestId+Timing, no asgi-correlation-id), D-12/D-13 (exception classes + handler), D-14 (`/healthz` at root via empty-prefix v1 router), D-15 (Settings shape and `.env.example` defaults).
- `.planning/phases/02-backend-skeleton-with-quality-tooling/02-VERIFICATION.md` — Phase 2 verification battery; row #10 documents the deferred `alembic upgrade head` resumption point that Phase 3 SC #2 closes.
- `.planning/phases/01-monorepo-restructure-frontend-move/01-CONTEXT.md` — locks the monorepo skeleton; `apps/backend/Dockerfile` lives at `apps/backend/`, NOT in `infra/docker/` (per INFRA-01 wording).

### Source files Phase 3 directly consumes
- `apps/backend/app/main.py` — `create_app()` factory used by `tests/conftest.py` `app` fixture.
- `apps/backend/app/core/database.py` — `db_lifespan`, `Base`, `get_db`; `tests/conftest.py` `db_session` fixture reads `app.state.sessionmaker` from here.
- `apps/backend/app/core/config.py` — `Settings` shape; `docker-compose.yml` env vars must match this shape; `tests/conftest.py` constructs Settings from environment under test.
- `apps/backend/app/api/v1/health.py` — `/healthz` endpoint; `tests/integration/test_healthz.py` asserts `200` + `{"status": "ok"}` + `x-request-id` header.
- `apps/backend/pyproject.toml` — Phase 3 adds `[tool.pytest.ini_options]` and a new dev-dep (`asgi-lifespan>=2.1`).
- `apps/backend/.env.example` — already locks the env contract (Phase 2 D-15); compose `env_file: .env` reads the rendered version.
- `apps/backend/alembic.ini` + `apps/backend/alembic/env.py` — already async per Phase 2; Phase 3 invokes `alembic upgrade head` against compose Postgres.
- `apps/backend/.importlinter` — three contracts already defined (Phase 2 D-01); `conventions.md` quotes them.

### Background context (not load-bearing for Phase 3 deliverables)
- `.planning/codebase/STRUCTURE.md`, `STACK.md`, `TESTING.md`, `CONVENTIONS.md` — these describe the **frontend** (admin-web). Phase 3 does NOT consume them; backend test patterns are independent.

### External docs (consulted during research/planning)
- pytest-asyncio docs (`asyncio_mode = "auto"`, fixture conventions)
- httpx docs (`AsyncClient` + `ASGITransport` pattern)
- `asgi-lifespan` README (`LifespanManager` for forcing FastAPI lifespan under ASGITransport)
- uv docs (`uv sync --frozen --no-install-project`, Docker integration recipes — https://docs.astral.sh/uv/guides/integration/docker/)
- Docker official docs (multi-stage builds, BuildKit cache mounts, healthchecks, `depends_on.condition`)
- Postgres 16 official image docs (env vars, `pg_isready`, named volumes)
- alembic async docs (`async_engine_from_config`, `connection.run_sync`)
- MADR 4.0 spec (https://adr.github.io/madr/) — section set for ADR-0001
- structlog docs (already consulted in Phase 2; reused for `conventions.md` Logging section)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets
- **`apps/backend/app/main.py:create_app()`** — the only entry test fixtures use. Per-test fixture scope means each test gets its own engine + sessionmaker via `db_lifespan`. No monkey-patching needed.
- **`apps/backend/app/core/middleware.py`** — RequestIdMiddleware injects `x-request-id` header on every response. `test_healthz.py` can additionally assert this header is a valid UUID4 — proves middleware wiring under ASGITransport.
- **`apps/backend/app/core/config.py:Settings`** — `pydantic-settings` reads `.env`. Tests can override via `monkeypatch.setenv` BEFORE `create_app()` is called, then call `get_settings.cache_clear()`. Conftest documents this pattern for Phase B+.
- **`apps/backend/.env.example`** — already has working dev DSNs (`postgresql+asyncpg://app:app@localhost:5432/sportzal`, `redis://localhost:6379/0`). compose's Postgres is configured with the same `app/app/sportzal` triple so the same `.env` works for both local-uv and compose paths (D-09).
- **`apps/backend/alembic/env.py`** — already async; reads `DATABASE_URL` from Settings. The compose `migrate` service literally invokes `alembic upgrade head` and the path Phase 2 verified statically becomes the live path here (closes Phase 2 SC #5).
- **`apps/backend/.importlinter`** — three contracts. `conventions.md ## Quality gates` quotes their names verbatim so the doc and the enforcement file stay in sync.

### Established patterns to honor
- **Factory pattern, no module-level `app`** (Phase 2 main.py docstring) — tests MUST instantiate via `create_app()` per test. NO `app = create_app()` shortcut anywhere.
- **Lifespan-managed engine** (Phase 2 D-06/D-08) — tests cannot bypass lifespan; that's why `asgi-lifespan.LifespanManager` is added. Without it, ASGITransport doesn't fire startup, and `app.state.sessionmaker` stays unset.
- **No multi-tenancy / no auth in Phase A** — test fixtures and docs MUST NOT mention `tenant_id`, `Tenant`, RLS, JWT, refresh tokens, or password hashing. PROJECT.md is explicit.
- **structlog `ConsoleRenderer` in dev** — test runs are environment=dev (default). Test logs are colorized. Acceptable noise.
- **Russian-region constraints in docs** — ADR/architecture/conventions all reference ЮKassa-only / Stripe-forbidden / Telegram-primary; matches PROJECT.md tone.

### Integration points
- **Phase B+ (first business module)** — will exercise `db_session` for the first time; will add the `/api/v1` prefix per Phase 2 D-14 TODO; will add migrations to `alembic/versions/` so the `migrate` service stops being a no-op.
- **Phase 7 (frontend integration)** — when `VITE_API_MODE=http` flips, the frontend hits the FastAPI backend running in compose. CORS lands then. Phase 3's compose mounts backend at `:8000` so the frontend dev server (`:5173`) can call it once that toggle ships.
- **Future CI** — `pytest`, `ruff check`, `ruff format --check`, `mypy app`, `lint-imports` are the five gates a CI matrix would run. Phase 3 doesn't ship CI config but documents these in `conventions.md ## Quality gates` so any future CI plan picks the right list automatically.

</code_context>

<specifics>
## Specific Ideas

- **Mixed-language doc style is a deliberate signal:** narrative + reasoning in Russian = the user's working language; commands + code = English (greppable, copy-paste-stable). Downstream `gsd-doc-writer` (or whichever agent writes these docs) MUST honor both — do not fully translate code blocks; do not write the prose in English "because the rest of the codebase is".
- **MADR 4.0 over Nygard for ADR-0001 is forward-looking:** the user expects more ADRs over time (Phase B+ will land 0002+ for events, 0003+ for ЮKassa adapter, 0004+ for auth). MADR scales; Nygard requires retro-fit. Plan: don't just write 0001 — also drop a `docs/adr/template.md` (MADR skeleton) so the next ADR is one `cp` away.
- **Two-path README is explicit:** local uv path is for the user's own dev loop (fastest); compose path is the onboarding answer + the path that retires Phase 2 SC #5. Both are first-class — do not bury one as "advanced".
- **`migrate` as separate compose service** keeps `backend` startup deterministic and idempotent — `docker compose up` always lands a migrated DB, never races. This pattern carries cleanly into Phase B+ when real migrations exist.
- **`db_session` is intentionally unused in Phase A test bodies** but defined per TEST-01 — Phase 3 ships the contract; Phase B+ uses it. Don't be tempted to delete it as YAGNI.
- **`asgi-lifespan` dependency is a tax for ASGITransport correctness** — noted in `conventions.md ## Testing` so future test authors know why it's there and don't try to remove it for being "unused".

</specifics>

<deferred>
## Deferred Ideas

- **CI/CD pipelines** (GitHub Actions, GitLab CI, etc.) — Phase X+. Phase 3 only ships the local commands a CI would invoke; orchestration is its own phase.
- **Production Dockerfile variants** (distroless final stage, signed images, multi-arch buildx) — Phase X+ deploy concerns.
- **`testcontainers-python`** — explicitly NOT chosen (D-10). May reconsider if Phase B+ test parallelization needs ephemeral DBs per test class. Until then, compose Postgres is enough.
- **factory-boy / model_bakery factories** — Phase B+ when business models exist. Phase 3 only ships the empty `tests/factories/__init__.py` per TEST-04.
- **mermaid diagrams in architecture.md** — deferred. ASCII-only for Phase 3 (markdown viewer compatibility). Reconsider when README.md is rendered in a known-good viewer (GitHub, GitLab) consistently.
- **CORS middleware config + frontend-backend wiring** — Phase 7+ when `VITE_API_MODE=http` flips. Phase 3 leaves the existing TODO in `app/core/middleware.py:59` untouched.
- **Permanent CI script for the synthetic-violation check** (Phase 2 D-05 follow-up) — Phase X+ if needed; the verification was already done as a one-shot in Phase 2.
- **`scripts/restore_db.sh`** — counterpart to `backup_db.sh`. Phase X+ when there's actual data to lose.
- **`docs/operations.md` / runbook** — Phase X+ deployment concern; Phase A is local-dev only.
- **uv `dev-dependencies` → PEP-735 `[dependency-groups]` migration** — informational deferral from Phase 2; non-blocking. Touch only if Phase 3 happens to bump uv anyway.

</deferred>

---

*Phase: 03-tests-dev-infrastructure-documentation*
*Context gathered: 2026-05-01*
