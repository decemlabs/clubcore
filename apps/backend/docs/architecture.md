# sportzal-backend — Архитектура

Модульный монолит на FastAPI 0.115+ с физическим разделением `core` / `modules` / `integrations` / `workers` / `api`. Архитектурные границы машинно-проверяются через `import-linter`. Полное обоснование выбора стиля — см. [ADR-0001: Modular Monolith](adr/0001-modular-monolith.md).

## Обзор

Sportzal — пет-проект CRM для одного зала. Backend — single-deploy modular monolith: один репозиторий, один процесс, одна Postgres-база, один Redis. Бизнес-фичи живут вертикальными слайсами в `app.modules.<feature>` (auth, members, memberships, visits, trainers, schedule, bookings, billing, notifications) и не импортируют друг друга напрямую — этот инвариант гарантирует, что код не превратится в spaghetti при росте до 9+ модулей.

Архитектурный стиль выбран осознанно: соло-разработчик с AI-агентами не может полагаться на code review большой команды, поэтому архитектурные правила должны быть **machine-enforceable от Phase A**. Отсюда `import-linter` контракты с самого начала, а не как ретроспективная санация. См. [ADR-0001](adr/0001-modular-monolith.md) для разбора альтернатив (microservices, layered/clean architecture, plain monolith) и причин их отклонения.

## Слои

### app.core

Общая инфраструктура: `Settings` (`pydantic-settings`), `db_lifespan` (async SQLAlchemy engine + sessionmaker), structlog setup, middleware (`RequestIdMiddleware`, `TimingMiddleware`), exception handlers, pagination helpers.

НЕ содержит бизнес-логики и НЕ импортирует ничего из `app.modules.*` — это базовый слой, поверх которого живут feature-слайсы. Контракт `core-not-depend-on-modules` в `.importlinter`.

### app.modules.<feature>

Вертикальные слайсы будущих бизнес-доменов: `auth`, `members`, `memberships`, `visits`, `trainers`, `schedule`, `bookings`, `billing`, `notifications`. Каждый модуль будет содержать `router.py`, `service.py`, `models.py`, `schemas.py` (по мере роста — `repository.py`, `permissions.py`, `constants.py`).

В Phase A — placeholder-пакеты (только `__init__.py` с docstring, без реальной логики). НЕ импортируют друг друга: cross-module коммуникация — через events / explicit service interfaces (Phase B+). Контракт `modules-independent` в `.importlinter`.

### app.integrations

Адаптеры внешних сервисов: `telegram`, `email`. ЮKassa-адаптер появится в Phase X+ (региональный constraint — Stripe запрещён в РФ/СНГ).

В Phase A — placeholder-модули без сетевых вызовов. Могут читать `Settings` и использовать `structlog` (зависимость от `app.core` разрешена), но НЕ импортируют `app.modules.*` напрямую. Контракт `integrations-not-depend-on-modules` в `.importlinter`.

### app.workers

ARQ background tasks. `app/workers/arq_app.py` определяет `WorkerSettings` skeleton; `app/workers/tasks/*.py` — placeholder-модули для будущих задач (notifications, reminders, reports).

В Phase A — нет реальных задач (пустой `WorkerSettings.functions`). Worker-процесс запускается отдельно (`uv run arq app.workers.arq_app.WorkerSettings`), но в Phase A это no-op.

### app.api

HTTP entry-points. `app/api/router.py` агрегирует версионные роутеры; `app/api/v1/router.py` подключает feature-роутеры через `include_router`.

В Phase A — единственный реальный endpoint `GET /healthz` (см. `app/api/v1/health.py`), возвращает `{"status": "ok"}`. Префикс `/api/v1` будет добавлен в Phase B+, когда появятся бизнес-роутеры (TODO в `app/api/router.py`); пока v1 включён с empty prefix, чтобы `/healthz` был доступен по корневому пути (Kubernetes liveness convention).

## Архитектурные инварианты

Список ниже — компрессия Phase 2 LOCKED decisions D-01..D-14. Каждый инвариант enforced либо `import-linter`-контрактом, либо архитектурным паттерном в коде.

- **`core ⊥ modules`** — `app.core` (и подмодули) НЕ импортирует ничего из `app.modules.*`. Контракт `core-not-depend-on-modules` в `.importlinter`. Проверяется командой `uv run lint-imports`.
- **`modules ⊥ modules`** — `app.modules.X` НЕ импортирует `app.modules.Y` (X≠Y). Контракт `modules-independent` в `.importlinter`. Cross-module communication — через events / explicit service interfaces (Phase B+ design).
- **`integrations ⊥ modules`** — `app.integrations.*` НЕ импортируют `app.modules.*`. Контракт `integrations-not-depend-on-modules` в `.importlinter`. Обратное направление (`modules → integrations`) разрешено.
- **Factory pattern** — `app.main:create_app()` — единственный способ получить `FastAPI` instance. `uvicorn` запускается с флагом `--factory` (`uv run uvicorn app.main:create_app --factory`). NO module-level `app = create_app()` — каждый тест получает свежий FastAPI per-test.
- **Lifespan-managed engine** — `app.state.engine` и `app.state.sessionmaker` populated by `db_lifespan` async context manager (`app/core/database.py`). Engine создаётся на startup, disposed на shutdown. Tests требуют `asgi-lifespan.LifespanManager` чтобы lifespan выполнился под `httpx.ASGITransport` (FastAPI lifespan не fires автоматически с `ASGITransport`).
- **`register_middleware` REVERSED add order** — в `create_app()` middleware регистрируются в обратном порядке к выполнению: `TimingMiddleware` добавляется первым, `RequestIdMiddleware` вторым. Поэтому `RequestId` выполняется FIRST на входящем запросе, и timing log несёт `request_id` в contextvars (Phase 2 D-09).
- **Exception handler placement** — `register_exception_handlers(app)` вызывается ВНУТРИ `create_app()` (Phase 2 D-12), NOT через `@app.exception_handler` декораторы и NOT в middleware. Иерархия `AppError` живёт в `app/core/exceptions.py`.
- **`/healthz` mount** — единственный реальный endpoint в Phase A. Подключён через empty-prefix v1 router: `api.include_router(v1)` без `prefix=`. Префикс `/api/v1` добавится в Phase B+ когда появятся бизнес-роутеры (TODO в `app/api/router.py`).

## Запреты на Phase A

- **Нет multi-tenancy** — нет `tenant_id` в моделях, нет `Tenant` сущности, нет Postgres RLS, нет `SET LOCAL`. Sportzal — пет-проект на 1 зал; multi-tenant — преждевременная сложность. Если появится второй покупатель — отдельный milestone (v2 MT-01..MT-03).
- **Нет auth** — нет JWT, нет OAuth, нет password hashing, нет refresh tokens, нет permission системы. Auth — отдельная фаза (Phase C+) с собственным дизайном (вероятно через Telegram). `app/core/security.py` в Phase A — placeholder с TODO docstring.
- **Нет бизнес-таблиц** — нет `User`, `Member`, `Subscription`, `Visit`, `Payment`, `Booking`. Phase A — только каркас. Бизнес-модели — Phase B+; миграции в `alembic/versions/` в Phase A отсутствуют (только `.gitkeep`).
- **Нет Stripe** — региональный запрет. РФ/СНГ — Stripe недоступен. Платежи только через ЮKassa (Phase X+ интеграция). НЕ возвращаться к этому решению.
- **Нет реальной интеграции Telegram bot, SMTP email, ЮKassa** — только placeholder-модули в `app/integrations/`. Реальные сетевые вызовы появятся в отдельных фазах (Phase X+).

## Диаграмма

ASCII-only по решению D-07 (markdown viewers неоднородны; графические диаграммы отложены).

```text
                ┌─────────────────────────────────────┐
                │           api / v1 routers         │
                └────────────────┬────────────────────┘
                                 │
                ┌────────────────▼────────────────────┐
                │        modules.{auth,members,…}     │  ─┐
                └────────┬──────────────┬─────────────┘   │ independence
                         │              │                 │ (modules ⊥ modules)
                ┌────────▼──────┐  ┌────▼────────────┐    │
                │    core       │  │ integrations    │ ◄──┘ (forbidden ↔ modules)
                │ (config, db,  │  │ (telegram,email)│
                │  logging,…)   │  │                 │
                └───────────────┘  └─────────────────┘
                         ▲                  ▲
                         │                  │
                         └──────────────────┘
                            allowed: integrations → core
```

Легенда:
- Сплошные стрелки сверху вниз — разрешённые зависимости (`api → modules`, `modules → core`, `modules → integrations`, `integrations → core`).
- Запрещённые направления (`core → modules`, `modules ↔ modules`, `integrations → modules`) enforced контрактами в `.importlinter` и проверяются `uv run lint-imports`.
