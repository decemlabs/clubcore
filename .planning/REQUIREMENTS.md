# Requirements: Sportzal

**Defined:** 2026-04-30
**Core Value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current Milestone:** Phase A — каркас. Никаких бизнес-фич, auth, бизнес-таблиц.

## v1 Requirements

Все v1 — это содержимое Phase A (текущий milestone). Дальнейшие фазы (B, C, …, J) — в v2 ниже.

### Monorepo

- [ ] **MONO-01**: Корневые папки `apps/`, `packages/`, `infra/` созданы; `apps/client-web` НЕ создаётся даже как пустая папка
- [ ] **MONO-02**: `pnpm-workspace.yaml` на корне настраивает workspaces для `apps/admin-web` и `packages/*`
- [ ] **MONO-03**: Существующий `./frontend` перенесён в `apps/admin-web/` без изменения внутренней структуры, моков и истории файлов
- [ ] **MONO-04**: `packages/ui/` создан с `package.json` + `README.md` без какого-либо реального кода
- [ ] **MONO-05**: `packages/api-client/` создан с `package.json` + `README.md` без какого-либо реального кода
- [ ] **MONO-06**: `infra/docker/` и `infra/nginx/` существуют как структура для будущих конфигов

### Backend Core

- [ ] **BE-01**: `apps/backend/app/` — корень Python-пакета с именем `app` (не `sportzal`, не `src/sportzal`)
- [ ] **BE-02**: `app/main.py` экспортирует `create_app()` factory, поднимает FastAPI с подключённым api-роутером, structlog и middleware
- [ ] **BE-03**: `app/core/config.py` — `Settings` через `pydantic-settings` + cached `get_settings()`, читает env только здесь
- [ ] **BE-04**: `app/core/database.py` — async engine, `async_sessionmaker`, `Base`, `get_db` dependency
- [ ] **BE-05**: `app/core/security.py` — пустой модуль с заготовкой под будущие helper-функции; никакой реальной auth-логики
- [ ] **BE-06**: `app/core/logging.py` — structlog setup, JSON в проде / colorized в dev
- [ ] **BE-07**: `app/core/exceptions.py` — `AppError`, `NotFoundError`, `ForbiddenError`, `ConflictError`, `ValidationAppError`
- [ ] **BE-08**: `app/core/pagination.py` — `LimitOffsetParams` + generic `Page[T]`
- [ ] **BE-09**: `app/core/dependencies.py` + `app/core/middleware.py` — placeholders + рабочие request_id, timing, exception handlers
- [ ] **BE-10**: `app/core` импорт-линтер: `core` не импортирует ничего из `app.modules` (проверяемо)

### Backend Modules (placeholders)

- [ ] **MOD-01**: `app/modules/auth/` — `__init__.py`, `router.py` (`APIRouter()` без endpoints, TODO), `service.py`/`models.py`/`schemas.py` пустые с TODO; **БЕЗ** User/RefreshToken моделей
- [ ] **MOD-02**: `app/modules/{members,memberships,visits,trainers,schedule,bookings,billing,notifications}/__init__.py` существуют, остальное пусто
- [ ] **MOD-03**: import-linter проверяет, что `modules/*` не импортируют друг друга напрямую

### Backend Integrations (placeholders)

- [ ] **INT-01**: `app/integrations/telegram/{bot.py,handlers.py,sender.py}` — placeholder-модули, **никаких** вызовов aiogram или Telegram API
- [ ] **INT-02**: `app/integrations/email/{client.py, templates/.gitkeep}` — placeholder, **никаких** SMTP-вызовов

### Backend Workers

- [ ] **WORK-01**: `app/workers/arq_app.py` — `WorkerSettings` skeleton без реальных задач
- [ ] **WORK-02**: `app/workers/tasks/{notifications,reminders,reports}.py` — placeholder-функции с TODO
- [ ] **WORK-03**: `app/workers/scheduler.py` — placeholder

### Backend API Surface

- [ ] **API-01**: `app/api/router.py` подключает v1 router
- [ ] **API-02**: `app/api/v1/router.py` подключает health (и потом модули)
- [ ] **API-03**: `app/api/v1/health.py` — `GET /healthz` возвращает `{"status": "ok"}` (единственный реальный endpoint в Phase A)

### Database Migrations

- [ ] **DB-01**: `alembic.ini` + `alembic/env.py` (async настройка, читает URL из Settings) + `alembic/script.py.mako`
- [ ] **DB-02**: `alembic/versions/.gitkeep` — папка существует, бизнес-миграций нет

### Tooling & Quality Gates

- [ ] **TOOL-01**: `pyproject.toml` со всеми deps под uv (Python 3.12, FastAPI 0.115+, SQLAlchemy 2.0+, Alembic, Pydantic v2, pydantic-settings, asyncpg, structlog, ARQ, redis, httpx, pytest, pytest-asyncio, ruff, mypy, import-linter)
- [ ] **TOOL-02**: `ruff.toml` со строгим набором правил (E, F, I, B, UP, ASYNC, S, …)
- [ ] **TOOL-03**: mypy в strict-режиме (через секцию в `pyproject.toml`)
- [ ] **TOOL-04**: `importlinter.ini` с контрактами:
  - `core` не импортирует `app.modules.*`
  - `app.modules.X` не импортирует `app.modules.Y` (X≠Y)
  - `app.integrations.*` не импортируют `app.modules.*` напрямую
- [ ] **TOOL-05**: `.env.example` со всеми placeholder env переменными (DATABASE_URL, REDIS_URL, …)
- [ ] **TOOL-06**: `apps/backend/.gitignore` корректно игнорирует `.venv/`, `__pycache__/`, `.mypy_cache/`, `.ruff_cache/`

### Test Scaffold

- [ ] **TEST-01**: `tests/conftest.py` с фикстурами `app`, `async_client` (httpx ASGITransport), `db_session`
- [ ] **TEST-02**: `tests/integration/test_healthz.py` — `GET /healthz` возвращает 200 и корректное тело
- [ ] **TEST-03**: `tests/unit/test_security.py` — минимальный placeholder тест, который проходит
- [ ] **TEST-04**: `tests/factories/__init__.py` существует пустым (под будущие factory-boy)

### Dev Infrastructure

- [ ] **INFRA-01**: `apps/backend/Dockerfile` — multi-stage build, slim Python 3.12 base, uv для install
- [ ] **INFRA-02**: `apps/backend/docker-compose.yml` поднимает `backend`, `postgres:16`, `redis:7` для локальной разработки
- [ ] **INFRA-03**: `apps/backend/scripts/seed_demo_data.py` — placeholder, печатает `"Phase A: no data to seed"`
- [ ] **INFRA-04**: `apps/backend/scripts/backup_db.sh` — рабочий `pg_dump` против локального Postgres

### Documentation

- [ ] **DOCS-01**: `apps/backend/docs/architecture.md` описывает модульный монолит и архитектурные инварианты
- [ ] **DOCS-02**: `apps/backend/docs/conventions.md` описывает стиль кода, naming, тестирование
- [ ] **DOCS-03**: `apps/backend/docs/adr/0001-modular-monolith.md` фиксирует решение об архитектуре
- [ ] **DOCS-04**: `apps/backend/README.md` описывает quick start (`uv sync`, `docker compose up`, `pytest`)

## v2 Requirements

Деферы за пределы текущего milestone. Будут отдельными milestone-ами после Phase A.

### Auth (Phase C+)

- **AUTH-01**: Login / register / refresh endpoints
- **AUTH-02**: JWT issue/verify
- **AUTH-03**: Password hashing flow
- **AUTH-04**: Telegram-based auth (вероятный путь)

### Business Domain (Phase B+)

- **MEM-01**: Members модель + CRUD
- **MEMSHIP-01**: Memberships модель + CRUD
- **VIS-01**: Visits / check-ins
- **TRN-01**: Trainers модель
- **SCH-01**: Schedule + бронирования
- **BILL-01**: Billing модель
- **NOTIF-01**: Notifications модель

### Integrations (после соответствующих модулей)

- **TG-01**: Telegram bot на aiogram (auth + уведомления)
- **EM-01**: Email отправка через SMTP
- **PAY-01**: ЮKassa payment provider (Stripe запрещён)

### Frontend Real API (после auth + первого бизнес-модуля)

- **FE-01**: Замена mock-сервисов реальным HTTP-клиентом через swap seam
- **FE-02**: Генерация TS-типов в `packages/api-client/` из OpenAPI

### Multi-Tenant SaaS (только если появится второй покупатель)

- **MT-01**: Tenant модель + ContextVar
- **MT-02**: Postgres RLS / `SET LOCAL`
- **MT-03**: Tenant-aware миграции

### Client App (Phase J)

- **CLI-01**: `apps/client-web` с client-facing UI

### Production Deploy (Phase X+)

- **OPS-01**: Production Docker images, secrets management
- **OPS-02**: CI/CD pipeline
- **OPS-03**: Monitoring + alerting

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-tenancy (ContextVar/`tenant_id`/RLS) в Phase A | Пет-проект на 1 зал; преждевременно усложняет всё на годы |
| Auth любого вида в Phase A | Каркас должен встать без auth; auth — отдельная фаза с собственным дизайном |
| Бизнес-таблицы (User, Member, …) в Phase A | Только каркас в текущем milestone |
| Бизнес-миграции Alembic в Phase A | Alembic настраивается, но `versions/` пуст |
| Telegram bot real impl в Phase A | Только placeholder-модули |
| Email SMTP в Phase A | Только placeholder |
| ЮKassa интеграция в Phase A | Только placeholder; интеграция — Phase X+ |
| **Stripe** во всём проекте | Недоступен в РФ — никогда не использовать |
| Замена frontend-моков реальным API в Phase A | Mock остаётся до появления реальных эндпоинтов |
| `apps/client-web` в Phase A | Появится только в Phase J |
| Kubernetes / Terraform / production deploy в Phase A | Только локальный dev docker-compose |

## Traceability

Какие фазы покрывают какие требования. Заполняется при создании ROADMAP.md.

| Requirement | Phase | Status |
|-------------|-------|--------|
| MONO-01 | Phase 1 | Pending |
| MONO-02 | Phase 1 | Pending |
| MONO-03 | Phase 1 | Pending |
| MONO-04 | Phase 1 | Pending |
| MONO-05 | Phase 1 | Pending |
| MONO-06 | Phase 1 | Pending |
| BE-01 | Phase 2 | Pending |
| BE-02 | Phase 2 | Pending |
| BE-03 | Phase 2 | Pending |
| BE-04 | Phase 2 | Pending |
| BE-05 | Phase 2 | Pending |
| BE-06 | Phase 2 | Pending |
| BE-07 | Phase 2 | Pending |
| BE-08 | Phase 2 | Pending |
| BE-09 | Phase 2 | Pending |
| BE-10 | Phase 2 | Pending |
| MOD-01 | Phase 2 | Pending |
| MOD-02 | Phase 2 | Pending |
| MOD-03 | Phase 2 | Pending |
| INT-01 | Phase 2 | Pending |
| INT-02 | Phase 2 | Pending |
| WORK-01 | Phase 2 | Pending |
| WORK-02 | Phase 2 | Pending |
| WORK-03 | Phase 2 | Pending |
| API-01 | Phase 2 | Pending |
| API-02 | Phase 2 | Pending |
| API-03 | Phase 2 | Pending |
| DB-01 | Phase 2 | Pending |
| DB-02 | Phase 2 | Pending |
| TOOL-01 | Phase 2 | Pending |
| TOOL-02 | Phase 2 | Pending |
| TOOL-03 | Phase 2 | Pending |
| TOOL-04 | Phase 2 | Pending |
| TOOL-05 | Phase 2 | Pending |
| TOOL-06 | Phase 2 | Pending |
| TEST-01 | Phase 3 | Pending |
| TEST-02 | Phase 3 | Pending |
| TEST-03 | Phase 3 | Pending |
| TEST-04 | Phase 3 | Pending |
| INFRA-01 | Phase 3 | Pending |
| INFRA-02 | Phase 3 | Pending |
| INFRA-03 | Phase 3 | Pending |
| INFRA-04 | Phase 3 | Pending |
| DOCS-01 | Phase 3 | Pending |
| DOCS-02 | Phase 3 | Pending |
| DOCS-03 | Phase 3 | Pending |
| DOCS-04 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 47 total
- Mapped to phases: 47 (Phase 1: 6, Phase 2: 29, Phase 3: 12)
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-30*
*Last updated: 2026-04-30 after roadmap creation (47/47 mapped)*
