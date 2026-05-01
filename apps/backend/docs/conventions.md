# sportzal-backend — Конвенции

Кодстайл, naming, тестирование, observability и migrations. Все правила proverable машинно через `uv run` (см. `## Quality gates`).

## Naming

- **Python modules**: `snake_case.py` (например, `database.py`, `request_id.py`, `arq_app.py`).
- **Classes / Pydantic models / SQLAlchemy models**: `PascalCase` (например, `Settings`, `RequestIdMiddleware`, `WorkerSettings`, `AppError`).
- **Constants**: `UPPER_SNAKE_CASE` (например, `DATABASE_URL_DEFAULT`).
- **Functions / variables**: `snake_case` (`get_settings`, `register_middleware`, `db_lifespan`).
- **Test files**: `test_*.py` (matches `python_files = ["test_*.py"]` в `[tool.pytest.ini_options]`).
- **Test methods**: `test_<scenario>` — sentence-style readable (`test_healthz_returns_ok`, `test_request_id_header_is_uuid4`).
- **Migration files** (Phase B+): `<rev_id>_<short_slug>.py` per Alembic default. Custom naming policy можно ввести отдельным ADR в Phase B+.

## Imports

- **Порядок** (enforced by ruff `I001` — isort-совместимая сортировка): stdlib → third-party → `app.*`. Ruff format автоматически переупорядочивает.
- **`from __future__ import annotations`** опционально, но рекомендован в новых файлах для forward-refs и более быстрых импортов.
- **Cross-module imports внутри `app.modules.*` ЗАПРЕЩЕНЫ** — контракт `modules-independent` в `.importlinter`. `app.modules.X` не импортирует `app.modules.Y` (X≠Y). В Phase B+ communication между модулями — через events или explicit service interfaces.
- **`app.core` не зависит от `app.modules.*`** — контракт `core-not-depend-on-modules`. Базовая инфраструктура не должна знать про feature-слайсы.
- **`app.integrations.*` не импортируют `app.modules.*`** — контракт `integrations-not-depend-on-modules`. Обратное направление (`modules → integrations`) разрешено.
- **`app.api → app.modules.*`** разрешено: `app/api/v1/router.py` агрегирует feature-роутеры через `include_router`.

## Quality gates

Pre-commit / pre-push гейтов пять. Все запускаются через `uv run` — без локальной активации `.venv`. Эти же пять команд — будущий контракт CI.

| Gate | Command | Source |
|------|---------|--------|
| Linting | `uv run ruff check .` | `ruff.toml` |
| Formatting | `uv run ruff format .` | `ruff.toml` |
| Type check | `uv run mypy app` | `pyproject.toml [tool.mypy]` (strict) |
| Architecture | `uv run lint-imports` | `.importlinter` |
| Tests | `uv run pytest` | `pyproject.toml [tool.pytest.ini_options]` |

**ruff** правила (см. `ruff.toml`): `E` (pycodestyle errors), `F` (pyflakes), `I` (isort), `B` (bugbear), `UP` (pyupgrade), `ASYNC` (async hygiene), `S` (security/bandit), `DTZ` (datetime hygiene — important: проект пинит `Europe/Moscow`), `N` (PEP 8 naming), `SIM` (simplifications), `RUF` (ruff-native). Line length: `100` (matches frontend Prettier `printWidth`).

**mypy** strict: `python_version = "3.12"`, `strict = true`, `plugins = ["pydantic.mypy"]`. SQLAlchemy 2.0 ships native PEP 484 typing — отдельный sqlalchemy plugin не подключён. Per-module override: `module = "alembic.env"; disable_error_code = ["no-untyped-call"]`.

**import-linter** — три контракта в `.importlinter` (имена цитируются verbatim, чтобы доки и enforcement-файл не расходились):

1. **`core-not-depend-on-modules`** — `app.core` (и подмодули) не импортирует ничего из `app.modules.*`. Тип контракта — `forbidden`.
2. **`modules-independent`** — модули в `app.modules.*` независимы; X не импортирует Y. Тип контракта — `independence`. Список модулей (9): `auth`, `members`, `memberships`, `visits`, `trainers`, `schedule`, `bookings`, `billing`, `notifications`.
3. **`integrations-not-depend-on-modules`** — `app.integrations.*` не импортируют `app.modules.*`. Тип контракта — `forbidden`.

## Testing

Обязательный раздел — закрепляет TEST-01..04 паттерн машинно-читаемо.

- **HTTP transport** — `httpx.AsyncClient(transport=ASGITransport(app))`. НЕ реальная сеть. Constraint из `CLAUDE.md` (Testing section) — backend-тесты не открывают TCP-сокеты.
- **Async runner** — `pytest-asyncio` в `auto` режиме (`asyncio_mode = "auto"` в `[tool.pytest.ini_options]`). Декораторы `@pytest.mark.asyncio` НЕ нужны.
- **Per-test app** — каждый тест получает свежий `FastAPI` через `create_app()` factory (function-scope fixture). NO module-level `app = create_app()` синглтон.

**Fixtures (в `tests/conftest.py`):**

- **`app`** — per-test FastAPI instance, обёрнутый в `asgi_lifespan.LifespanManager` чтобы выполнились startup/shutdown handlers под `ASGITransport`. Без `LifespanManager` `app.state.sessionmaker` остаётся unset, и `db_session` падает с `AttributeError`.
- **`async_client`** — `httpx.AsyncClient(transport=ASGITransport(app), base_url="http://test")`.
- **`db_session`** — per-test `AsyncSession`, создаётся через `app.state.sessionmaker`, rolled back на teardown (TEST-04 contract). В Phase A не используется в тестах — Phase B+ exercise когда появятся бизнес-модули. **Не удалять "as unused"**.

**`asgi-lifespan`** — required dev-dependency (`asgi-lifespan>=2.1` в `[tool.uv] dev-dependencies`). FastAPI lifespan не fires автоматически под `httpx.ASGITransport` — `LifespanManager` принудительно вызывает startup/shutdown. Альтернатива (manual `app.router.startup()` / `shutdown()`) — менее идиоматична. Не удалять library "for being unused" — это tax for ASGITransport correctness.

**Раскладка тестов:**

- `tests/integration/` — тесты, поднимающие FastAPI через `create_app()` + ASGITransport.
- `tests/unit/` — pure-Python unit tests без FastAPI / DB / network.
- `tests/factories/` — placeholder под `factory-boy` / `model_bakery` factories в Phase B+. В Phase A — пустой `__init__.py`.

**Integration smoke pattern** (`tests/integration/test_healthz.py`): через `async_client` зовём `GET /healthz`, проверяем `200`, body `{"status": "ok"}` и `x-request-id` header — валидный UUID4. Это доказывает что middleware (`RequestIdMiddleware`) fires под `ASGITransport`.

## Logging

- **structlog** с `request_id` / `path` / `method` в contextvars. Настройка — `app/core/logging.py` + биндинг — `app/core/middleware.py:RequestIdMiddleware`.
- **Renderer** driven by `Settings.environment` (Phase 2 D-15): `ConsoleRenderer(colors=True)` для `'dev'`, `JSONRenderer()` для `'staging'` и `'prod'`. NOT TTY auto-detection.
- **НЕ использовать stdlib `logging` напрямую** в новом коде — всегда `structlog.get_logger(...)`. structlog проксирует stdlib loggers, но прямой вызов теряет contextvars binding.
- `RequestIdMiddleware` зовёт `structlog.contextvars.clear_contextvars()` в начале каждого `dispatch` — предотвращает cross-request bleed contextvars.

## Errors

- **Иерархия `AppError`** (`app/core/exceptions.py`) — class-level `code: str` и `status_code: int`:
  - `AppError` (500, `app_error`) — base.
  - `NotFoundError` (404, `not_found`).
  - `ForbiddenError` (403, `forbidden`).
  - `ConflictError` (409, `conflict`).
  - `ValidationAppError` (422, `validation_error`).
- **Constructor** — `__init__(message: str, *, fields: dict | None = None)`.
- **Все доменные ошибки** — подклассы `AppError`. Никогда не `raise Exception(...)` или `raise HTTPException(...)` напрямую в бизнес-коде.
- **`register_exception_handlers(app)`** вызывается ВНУТРИ `create_app()` (Phase 2 D-12) — НЕ декораторы `@app.exception_handler`, НЕ в middleware. Handler возвращает `JSONResponse(status_code=exc.status_code, content={"code": exc.code, "message": exc.message, "fields": exc.fields})`.

## Migrations

- **Alembic в async-режиме**. `alembic/env.py` читает `DATABASE_URL` из `Settings` (один источник правды для DSN — без дублирования в `alembic.ini`).
- **Команды:**
  - `uv run alembic upgrade head` — применить pending миграции.
  - `uv run alembic revision --autogenerate -m "<msg>"` — сгенерировать новую ревизию (Phase B+, когда появятся бизнес-модели).
  - `uv run alembic downgrade -1` — откатить одну ревизию (use sparingly).
- **В Phase A** `alembic/versions/` содержит только `.gitkeep` — миграций нет. `alembic upgrade head` против пустой `versions/` — no-op (это ROADMAP Phase 3 SC #2 — закрытие Phase 2 deferred SC #5).
- **Naming convention** для будущих ревизий — Alembic default (`<rev_id>_<short_slug>.py`). Если понадобится более жёсткая политика (timestamp prefix, ticket id) — вводится отдельным ADR в Phase B+.
- **Online-only mode** — `run_migrations_offline` намеренно `raises NotImplementedError` (Phase 2 D-13 / T-02-18 accepted). Async-engine `connection.run_sync` cookbook (asyncpg).
