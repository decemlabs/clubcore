# Sportzal

## What This Is

Sportzal — CRM для тренажёрного зала. Пет-проект на один зал: управление клиентами, абонементами, посещениями, расписанием, бронированиями, тренерами, биллингом и уведомлениями. Под рынок РФ/СНГ.

**Текущее состояние (после v1.0 — Phase A):**
- **Frontend** — admin-панель на React 19 (Vite + TanStack Router) с моками; перенесена в `apps/admin-web/` без изменения внутренней структуры.
- **Backend** — модульный монолит на FastAPI в `apps/backend/app/`; реальный endpoint только `GET /healthz`. Архитектура (`core` / `modules` / `integrations` / `workers` / `api`) физически выложена и закреплена `import-linter`. Бизнес-логики и бизнес-таблиц нет.
- **Dev infrastructure** — `docker compose` поднимает backend + Postgres 16 + Redis 7 + miграции; pytest + httpx ASGITransport покрывает /healthz; ruff + mypy strict + import-linter — все зелёные.

## Core Value

Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.

## Requirements

### Validated

<!-- Frontend (унаследовано до v1.0): -->

- ✓ Admin SPA scaffold: React 19 + Vite 6 + TanStack Router (file-based) + TanStack Query — pre-existing
- ✓ Mock/HTTP swap seam: `services/index.ts` через `VITE_API_MODE` chokepoint, ESLint-enforced — pre-existing
- ✓ FSD-lite layering: `app/`, `routes/`, `features/`, `entities/`, `shared/` — pre-existing
- ✓ RBAC: `Role = 'owner' | 'reception'` через `can(role, action, resource)` + `RoleGate` — pre-existing
- ✓ Theme: Zustand-persisted `light|dark|system` с FOUC-free bootstrap — pre-existing
- ✓ i18n: `shared/i18n/ru.ts`, date-fns ru локаль, Europe/Moscow TZ — pre-existing
- ✓ shadcn/ui (new-york) + Radix primitives — pre-existing
- ✓ Test infrastructure: Vitest + jsdom + @testing-library/react — pre-existing
- ✓ Architectural ESLint: `no-restricted-paths` — pre-existing
- ✓ Versioned localStorage: `sportzal:session:v1`, `sportzal:ui:v1`, `sportzal:mock:v1` — pre-existing

<!-- Phase A v1.0 (validated 2026-05-01): -->

- ✓ Monorepo: `apps/`, `packages/`, `infra/` skeleton; pnpm workspaces — v1.0
- ✓ `frontend/` → `apps/admin-web/` без правок — v1.0
- ✓ `apps/backend/` модульный монолит на FastAPI с пакетом `app/` — v1.0
- ✓ Backend стек: Python 3.12 + uv, FastAPI 0.115+, SQLAlchemy 2.0 async, Alembic async, Pydantic v2, Postgres 16, Redis 7, ARQ, structlog — v1.0
- ✓ `app/core/` infrastructure: config, database lifespan, security placeholder, structlog, exceptions, pagination, dependencies, request-id + timing middleware — v1.0
- ✓ `app/modules/` placeholders: auth, members, memberships, visits, trainers, schedule, bookings, billing, notifications — v1.0
- ✓ `app/integrations/` (telegram, email) + `app/workers/` (ARQ skeleton) placeholders — v1.0
- ✓ `app/api/` chain → `GET /healthz` (единственный реальный endpoint) — v1.0
- ✓ `packages/ui`, `packages/api-client` placeholders (только `package.json` + `README.md`) — v1.0
- ✓ `apps/backend/Dockerfile` (multi-stage uv builder + non-root runtime) + `docker-compose.yml` (backend + migrate + postgres:16 + redis:7) — v1.0
- ✓ Async Alembic env.py + пустой `versions/.gitkeep` — v1.0
- ✓ Quality tooling: ruff, mypy strict, import-linter (3 контракта: `core ⊥ modules`, `modules independent`, `integrations ⊥ modules`) — v1.0
- ✓ Test scaffold: pytest + pytest-asyncio + httpx ASGITransport + LifespanManager; фикстуры `app`, `async_client`, `db_session`; integration `test_healthz.py` (200 + body shape + UUID4 x-request-id) — v1.0
- ✓ Документация: `docs/architecture.md`, `docs/conventions.md`, `docs/adr/0001-modular-monolith.md` (MADR 4.0), `docs/adr/template.md`, `README.md` — v1.0
- ✓ Утилитарные скрипты: `scripts/seed_demo_data.py` (Phase A placeholder), `scripts/backup_db.sh` (pg_dump через docker compose exec) — v1.0
- ✓ `.env.example`, `pyproject.toml`, `ruff.toml`, `.importlinter`, `alembic.ini` — v1.0

### Active (v1.1 — Auth + Clients)

См. подробный список в `.planning/REQUIREMENTS.md` (REQ-IDs `AUTH-*`, `RBAC-*`, `CLIENTS-*`, `API-*`, `FE-*`).

Кратко:

- **Auth (двухканальный):** Telegram bot deep-link + одноразовый код (primary) + email/password fallback; JWT access (~15min) + refresh (~30d) в httpOnly Secure cookie с rotation; sessions tracking в Redis для revoke.
- **RBAC server-side:** паритет с `apps/admin-web/src/shared/session/can.ts`; FastAPI dependency `require_permission(action, resource)` на каждом business-endpoint; reception lockouts по `OWNER_ONLY`.
- **Clients CRUD + поиск/фильтры:** Postgres-таблица `clients` с soft-delete; первая бизнес-миграция Alembic; `POST/GET/PATCH/DELETE /api/v1/clients`; server-side pagination (`{items,total,page,pageSize}`); ILIKE-поиск по ФИО/phone.
- **Frontend wiring:** admin-web routes `/login` + `/clients/*` идут через `VITE_API_MODE=http` swap-seam → `packages/api-client`; остальные домены остаются на mocks до v1.2+.
- **`packages/api-client` (типизированный):** FastAPI пишет `openapi.json` → `openapi-typescript` генерит TS-типы; тонкий fetch wrapper с cookie credentials и typed `ApiError`; CI check `git diff --exit-code` против drift.

## Current Milestone: v1.1 Auth + Clients

**Goal:** Поднять первый бизнес-слой — двухканальная аутентификация (Telegram + email/password) с серверным RBAC и полный Clients CRUD с поиском, доведённый до admin-web через типизированный HTTP-клиент.

**Target features:**

- Auth — двухканальный (Telegram bot deep-link primary + email/password fallback) + JWT access/refresh в httpOnly cookie + Redis sessions
- RBAC server-side — паритет с frontend `can(role, action, resource)` через FastAPI dependency
- Clients CRUD — полный CRUD + server-side pagination + ILIKE-поиск + soft-delete; первая бизнес-миграция Alembic
- Frontend wiring — `apps/admin-web` routes auth/clients через real HTTP swap-seam (`VITE_API_MODE=http`); остальные модули продолжают идти через mocks
- `packages/api-client` — типизированный клиент (openapi-typescript codegen + CI drift check) для auth + clients endpoints

### Out of Scope

<!-- Зафиксировано пользователем явно. Не возвращать без явного запроса. -->

- Multi-tenancy (ContextVar/`tenant_id`/RLS/`SET LOCAL`) — пет-проект на 1 зал; добавим только когда появится второй покупатель
- **Stripe** — недоступен в РФ, не использовать никогда в этом проекте
- `apps/client-web` — клиентский фронт появится только в Phase J, не раньше
- Kubernetes / Terraform / production deploy — пока только dev docker-compose

## Context

- **Регион:** РФ/СНГ. Внешние сервисы выбираются под этот рынок.
  - Платежи: только ЮKassa. Stripe запрещён.
  - Уведомления / авторизация: Telegram как основной канал.
- **Команда:** один backend-разработчик + AI-агенты. Frontend знает слабее, поэтому admin-панель уже скаффолдена и трогать её внутренности нельзя без явного решения.
- **Backend пакет:** имя Python-пакета — **`app`** (не `sportzal`, не `src/sportzal`). Корень в `apps/backend/app/`.
- **Архитектурный стиль:** modular monolith с физическим разделением `core` / `modules` / `integrations` / `workers` / `api`. НЕ Clean Architecture. НЕ микросервисы.
- **Архитектурные инварианты (контролируются `import-linter`):**
  - `core` ничего не знает про `modules`
  - `modules` не импортируют друг друга напрямую
  - `integrations` не импортируют `modules`
- **Структура одного бизнес-модуля (когда появятся файлы в Phase B+):** `router.py`, `service.py`, `models.py`, `schemas.py`. По мере роста — `repository.py`, `permissions.py`, `constants.py`.
- **Будущая трансформация в multi-tenant SaaS** возможна, но НЕ должна влиять на решения сейчас.
- **Текущий codebase (после v1.0):** ~46 Python source файлов в `apps/backend/app/`; 3 теста (test_healthz × 2, test_security_module_importable); 5 doc-файлов; docker-compose с тремя сервисами + одноразовым migrate.

## Constraints

- **Tech stack — Backend**: Python 3.12 + uv + FastAPI 0.115+ + SQLAlchemy 2.0 async + Alembic async + Pydantic v2 + Postgres 16 + Redis 7 + ARQ + structlog — закреплено пользователем; альтернативы не рассматриваются
- **Tech stack — Frontend**: pnpm workspaces; существующий frontend стек (React 19, Vite 6, TanStack) не трогаем
- **Region**: РФ/СНГ — Stripe запрещён; платежи только ЮKassa; Telegram как первичный канал
- **Tooling**: ruff + mypy strict + import-linter обязательны — архитектурные правила выполнимы локально через `uv run`
- **Testing**: backend-тесты используют `httpx ASGITransport` (не реальный сетевой стек) и `pytest-asyncio`
- **Frontend integrity**: `apps/admin-web` — это перенос `./frontend`; правки внутренней структуры или моков требуют явного решения
- **Dev deps формат**: PEP 735 `[dependency-groups].dev` (мигрировано с `[tool.uv].dev-dependencies` в quick task 260501-ndi)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Modular monolith (`core` / `modules` / `integrations` / `workers` / `api`) | Соло-разработчик; код держим рядом с фичей; микросервисы преждевременны | ✓ Good — v1.0 закрепил структуру с `import-linter` |
| Python-пакет называется `app`, не `sportzal` | Короче в импортах; нет коллизии с потенциальными CLI/shared пакетами | ✓ Good — v1.0 |
| `frontend/` → `apps/admin-web/` без переписывания (clean-collapse `.git`) | Frontend уже стабилен (FSD-lite, моки, RBAC, i18n); переписывание — чистая регрессия | ✓ Good — v1.0 (820 файлов перенесены, 0 byte source change) |
| Без multi-tenancy в Phase A | Пет-проект на 1 зал; multi-tenant добавим, только когда появится второй покупатель | ✓ Good — v1.0 |
| Без auth в Phase A | Каркас должен быть устойчив без auth; auth — отдельная фаза с собственным дизайном (вероятно через Telegram) | ✓ Good — v1.0; следующий milestone разморозит |
| `import-linter` с Phase A, не позже | Архитектурные границы дешевле закрепить машинно сразу | ✓ Good — v1.0 (3 контракта KEPT, синтетические нарушения BROKEN с non-zero exit) |
| Pinned РФ-стек (ЮKassa, Telegram, Postgres self-host) | Региональные ограничения известны | — Pending (применится в business-фазах) |
| Compose `environment:` precedence over `env_file: .env` (CR-01 fix) | Сохраняет `.env.example` как Variant 1 single source of truth без форка `.env.compose` / `.env.local` | ✓ Good — v1.0 (03-06) |
| REVERSED middleware add order: TimingMiddleware first, RequestIdMiddleware second | RequestId должен запускаться первым на incoming, чтобы timing log нёс request_id | ✓ Good — v1.0 (Phase 02 P06) |
| PEP 735 `[dependency-groups].dev` over deprecated `[tool.uv].dev-dependencies` | uv 0.5+ ругается deprecation warning; PEP 735 — стандарт | ✓ Good — v1.0 (quick 260501-ndi) |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition:**
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-01 — v1.1 (Auth + Clients) milestone started*
