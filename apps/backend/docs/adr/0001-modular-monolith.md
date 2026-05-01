# ADR-0001: Modular Monolith с физическим разделением core / modules / integrations / workers / api

- Status: accepted
- Date: 2026-05-01
- Deciders: Andre

## Context and Problem Statement

Sportzal — пет-проект CRM для одного зала; соло backend-разработчик с активным использованием AI-агентов. Цель — наращивать бизнес-фичи поэтапно (auth, members, memberships, visits, trainers, schedule, bookings, billing, notifications — 9 модулей) без переписывания структуры по мере роста.

На старте нужно выбрать архитектурный стиль, который не превратится в spaghetti при росте до 9+ модулей и который reasonably обслуживается одним человеком. Решение должно учитывать региональные ограничения: РФ/СНГ — Stripe запрещён, платежи через ЮKassa, Telegram primary канал коммуникации с клиентом.

Без machine-enforceable границ соло-разработчик не может надеяться, что cross-module imports не проникнут постепенно — code review большой команды нет, а ручная дисциплина деградирует за месяцы.

## Decision Drivers

- **Solo dev + AI-агенты** — каркас должен быть machine-enforceable. Архитектурные правила должны проверяться локально через `uv run lint-imports`, а не зависеть от ревьюеров.
- **Single deploy, single repo, single DB** — operational complexity microservices не оправдана для пет-проекта на 1 зал.
- **No rewrites as features grow** — архитектурные правила должны выполняться на день первый и не деградировать; границы модулей — не "best practice" в README, а constraint в `.importlinter`.
- **Locally-enforceable architectural rules** — `ruff` + `mypy strict` + `import-linter` запускаются локально через `uv run`. Никакой внешней инфраструктуры не нужно.
- **Vertical slices over horizontal layers** — каждый бизнес-модуль (`app.modules.<feature>`) — самодостаточный slice (`router.py` / `service.py` / `models.py` / `schemas.py` внутри). Код держим рядом с фичей.
- **Регион РФ/СНГ** — Stripe forbidden, ЮKassa-only (Phase X+), Telegram primary (Phase B+). Архитектура должна позволять подключать региональные интеграции без переделки ядра.

## Considered Options

- **Option 1 — Modular Monolith с физическим разделением `core` / `modules` / `integrations` / `workers` / `api`** (chosen). Single repo, single deploy; модули — vertical slices; cross-module imports запрещены `import-linter` контрактами.
- **Option 2 — Microservices от старта.** Каждый бизнес-модуль — отдельный сервис с собственным репо, deploy и DB. Rejected: ops cost для соло-разработчика, network overhead, distributed-transaction complexity, debug overhead.
- **Option 3 — Layered/Clean Architecture (entities / use-cases / interface-adapters / frameworks).** Горизонтальные слои поверх всех фич. Rejected: vertical slices предпочтительнее для бизнес-фич CRM, классическая Clean — overkill для проекта на 9 модулей; inverse-dependency overhead не окупается.
- **Option 4 — Plain monolith без import-contracts.** Папочная структура есть, machine-enforced границ — нет. Rejected: degrades fast — без machine-enforceable правил cross-module imports проникают за месяцы и spaghetti неизбежен.

## Decision Outcome

Chosen option: **Option 1 — Modular Monolith** с физическим разделением `app.core`, `app.modules.<feature>`, `app.integrations.<service>`, `app.workers`, `app.api`. Одна codebase, один deploy, одна Postgres-база, один Redis.

Architectural границы enforced тремя контрактами в `.importlinter`:

1. `core-not-depend-on-modules` — `app.core` не импортирует `app.modules.*`.
2. `modules-independent` — `app.modules.X` не импортирует `app.modules.Y` (X≠Y).
3. `integrations-not-depend-on-modules` — `app.integrations.*` не импортируют `app.modules.*`.

Cross-module коммуникация — через events / explicit service interfaces (Phase B+ design). Реализационные детали каркаса зафиксированы в Phase 2 LOCKED decisions D-01..D-14 (factory pattern, lifespan-managed engine, REVERSED middleware add order, exception handler placement, `/healthz` mount).

### Consequences

- **`modules → modules` cross-imports forbidden** — cross-feature interaction только через events или explicit service interfaces (design — Phase B+).
- **Test isolation via `create_app()` factory** — каждый тест получает свежий `FastAPI`; engine + sessionmaker — per-app через `db_lifespan`. NO module-level `app = create_app()`.
- **Engine lifespan-bound** — `app.state.engine` создаётся в lifespan, не на module load. Tests требуют `asgi-lifespan.LifespanManager` чтобы lifespan fired под `httpx.ASGITransport`.
- **No multi-tenancy в Phase A** — `tenant_id` / `Tenant` model / Postgres RLS не вводятся; пет-проект на 1 зал. Если появится второй покупатель — отдельный milestone (v2 MT-01..MT-03).
- **No auth в Phase A** — auth lands в Phase C+ как отдельный milestone с собственным дизайном (вероятно через Telegram).
- **Stripe forbidden навсегда** — региональный constraint. ЮKassa — единственный payment provider (Phase X+).
- **Future ADRs (`0002-*`, `0003-*`)** будут касаться: events механики (cross-module communication), ЮKassa adapter, auth дизайна, Telegram bot integration. Все будущие ADR следуют MADR 4.0 — см. `template.md`.

## Pros and Cons of the Options

### Modular Monolith (chosen)

- **Good, because** single deploy, single DB, single repo — низкий ops cost для соло-разработчика.
- **Good, because** vertical slices масштабируются до 9+ модулей без переписывания структуры; код живёт рядом с фичей.
- **Good, because** import-linter контракты делают архитектурные правила machine-enforceable от Phase A — никакой деградации со временем.
- **Good, because** легко split into microservices later, если бизнес заставит — границы уже физические.
- **Bad, because** горизонтальное масштабирование (одинаковые модули на разных нодах) сложнее, чем у microservices; в пет-проекте на 1 зал — non-issue.

### Microservices

- **Good, because** независимый deploy каждого сервиса; технологическая гетерогенность возможна.
- **Bad, because** ops cost (множество репозиториев / pipelines / observability stack) непропорционален пет-проекту.
- **Bad, because** distributed transactions / saga pattern overkill для CRM на 1 зал.
- **Bad, because** debug overhead (cross-service tracing, network failures) — съедает время соло-разработчика.

### Layered/Clean Architecture

- **Good, because** чёткое разделение на слои (entities / use-cases / adapters / frameworks).
- **Bad, because** горизонтальные слои — anti-vertical-slice; CRM на 9 модулей лучше масштабируется через features-as-slices.
- **Bad, because** inverse-dependency overhead (DI container, repository interfaces в каждом модуле) — overkill для пет-проекта.

### Plain Monolith (no contracts)

- **Good, because** простейший старт — никаких дополнительных tools.
- **Bad, because** деградирует за месяцы — cross-module imports проникают и spaghetti неизбежен без machine-enforceable правил.
- **Bad, because** соло-разработчик не имеет ревьюера, который ловит нарушения границ; единственный способ удержать дисциплину — автоматическая проверка.
