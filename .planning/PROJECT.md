# Sportzal

## What This Is

Sportzal — CRM для тренажёрного зала. Сейчас пет-проект на один зал: управление клиентами, абонементами, посещениями, расписанием, бронированиями, тренерами, биллингом и уведомлениями. Под рынок РФ/СНГ. Frontend — admin-панель на React 19 (Vite + TanStack Router) с моками; backend сейчас отсутствует и будет построен в текущем milestone как модульный монолит на FastAPI.

## Core Value

Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.

## Requirements

### Validated

<!-- Уже существует в `frontend/` (см. `.planning/codebase/`). Закреплено: будет перенесено в `apps/admin-web` в Phase A без переписывания. -->

- ✓ Admin SPA scaffold: React 19 + Vite 6 + TanStack Router (file-based) + TanStack Query — existing
- ✓ Mock/HTTP swap seam: `services/index.ts` через `VITE_API_MODE` chokepoint (`shared/api/config/env.ts`), ESLint-enforced — existing
- ✓ FSD-lite layering: `app/`, `routes/`, `features/` (planned), `entities/` (planned), `shared/` — existing
- ✓ RBAC: `Role = 'owner' | 'reception'` через `can(role, action, resource)` + `RoleGate` + route `beforeLoad` guards — existing
- ✓ Theme: Zustand-persisted `light|dark|system` с FOUC-free bootstrap script в `index.html` — existing
- ✓ i18n: единый русский словарь `shared/i18n/ru.ts`, `date-fns` ru локаль, Europe/Moscow TZ, `Intl.PluralRules('ru-RU')` — existing
- ✓ shadcn/ui (new-york) + Radix primitives + reui registry; ban на сырые палитры через ESLint — existing
- ✓ Test infrastructure: Vitest + jsdom + @testing-library/react + setup shim для localStorage — existing
- ✓ Architectural ESLint: `no-restricted-paths` (features→features запрещены, прямой импорт `services/{mock,http}` запрещён) — existing
- ✓ Versioned localStorage: `sportzal:session:v1`, `sportzal:ui:v1`, `sportzal:mock:v1` — existing

### Active

<!-- Текущий milestone = Phase A: только каркас. Никаких бизнес-фич, auth, бизнес-таблиц. -->

- [ ] Монорепо-структура: `apps/`, `packages/`, `infra/` на корне; pnpm workspaces для frontend
- [ ] `frontend/` перенесён в `apps/admin-web/` без изменения внутренней структуры и моков
- [ ] `apps/backend/` — модульный монолит на FastAPI с Python-пакетом `app/`
- [ ] Backend стек закреплён: Python 3.12 + uv, FastAPI 0.115+, SQLAlchemy 2.0 async, Alembic async, Pydantic v2 + pydantic-settings, Postgres 16, Redis 7, ARQ, structlog
- [ ] Backend `core/`: config, database, security (placeholder), logging, exceptions, pagination, dependencies, middleware
- [ ] Backend `modules/` — placeholder-папки для auth, members, memberships, visits, trainers, schedule, bookings, billing, notifications (только `__init__.py` + TODO)
- [ ] Backend `integrations/`: telegram, email — placeholder-модули, никаких внешних вызовов
- [ ] Backend `workers/`: ARQ `WorkerSettings` skeleton без реальных задач
- [ ] Backend `api/`: главный router → v1 router → `GET /healthz` (единственный реальный endpoint)
- [ ] `packages/ui/`, `packages/api-client/` — только `package.json` + `README.md`, без кода
- [ ] `infra/docker/` + `infra/nginx/` — структура и рабочие dev-композы (Postgres, Redis, backend, admin-web)
- [ ] Alembic настроен async, `versions/` пуст (бизнес-миграций пока нет)
- [ ] Quality tooling: ruff, mypy strict, import-linter (архитектурные правила: `core` ⊥ `modules`, `modules` не импортят друг друга напрямую)
- [ ] Test scaffold: pytest + pytest-asyncio + httpx ASGITransport, фикстуры (`app`, `async_client`, `db_session`), `test_healthz.py` + минимальный unit-плейсхолдер
- [ ] Документация: `docs/architecture.md`, `docs/conventions.md`, ADR `0001-modular-monolith.md`
- [ ] `.env.example`, `Dockerfile`, `docker-compose.yml`, `pyproject.toml`, `ruff.toml`, `importlinter.ini`, `alembic.ini`, `README.md`

### Out of Scope

<!-- Зафиксировано пользователем явно. Не возвращать в этот milestone. -->

- Multi-tenancy (ContextVar/`tenant_id`/RLS/`SET LOCAL`) — пет-проект на 1 зал; добавим только когда понадобится продавать
- Auth (login, register, refresh, JWT issue/verify, password hashing) — отдельная фаза C+
- Бизнес-таблицы (User, RefreshToken, Tenant, Member, Membership, Visit, Payment, …) — Phase B+
- Бизнес-миграции Alembic — Phase B+ (Alembic настраивается, но `versions/` пуст)
- Telegram bot (aiogram, отправка) — Phase X+, в Phase A только пустые placeholder-модули
- Email отправка / SMTP — Phase X+, в Phase A только placeholder
- Платежи: ЮKassa интеграция, mock-провайдер, payment models — Phase X+
- **Stripe** — недоступен в РФ, не использовать никогда в этом проекте
- Замена frontend-моков реальным API — Phase X+, после поднятия реальных эндпоинтов
- `apps/client-web` — появится только в Phase J, в Phase A не создавать даже как пустую папку
- Kubernetes / Terraform / production deploy — Phase X+, сейчас только dev docker-compose

## Context

- **Регион:** РФ/СНГ. Внешние сервисы выбираются под этот рынок.
  - Платежи: только ЮKassa (когда дойдём). Stripe запрещён — недоступен.
  - Уведомления / авторизация: Telegram как основной канал.
- **Команда:** один backend-разработчик, активно использует AI-агентов. Frontend знает слабее, поэтому admin-панель уже скаффолдена и трогать её внутренности в Phase A нельзя.
- **Существующий frontend:** `frontend/` имеет собственный `.git` (отдельный sub-repo). При переносе в `apps/admin-web` нужно решить, поглощаем ли историю в корневой репо или сохраняем через subtree (см. Key Decisions, открытый вопрос для Phase A plan).
- **Backend пакет:** имя Python-пакета — **`app`** (не `sportzal`, не `src/sportzal`, не `backend`). Корень пакета лежит в `apps/backend/app/`.
- **Архитектурный стиль:** modular monolith с физическим разделением `core` / `modules` / `integrations` / `workers` / `api`. НЕ глобальные слои Clean Architecture (presentation/application/domain/infrastructure). НЕ микросервисы. Код держим рядом с бизнес-фичей.
- **Архитектурные инварианты (важно для всех будущих фаз):**
  - `core` ничего не знает про `modules`
  - `modules` не импортируют друг друга напрямую — только через события или явные сервисные интерфейсы
  - Контролируется `import-linter` начиная с Phase A
- **Структура одного бизнес-модуля (когда появятся файлы в Phase C+):** `router.py`, `service.py`, `models.py`, `schemas.py`. По мере роста — `repository.py`, `permissions.py`, `constants.py`.
- **Будущая трансформация в multi-tenant SaaS** возможна, но НЕ должна влиять на решения сейчас. Никаких упоминаний tenant в коде Phase A.

## Constraints

- **Tech stack — Backend**: Python 3.12 + uv + FastAPI 0.115+ + SQLAlchemy 2.0 async + Alembic async + Pydantic v2 + Postgres 16 + Redis 7 + ARQ + structlog — закреплено пользователем; альтернативы не рассматриваются в Phase A
- **Tech stack — Frontend**: пакетный менеджер pnpm (workspaces); существующий frontend стек (React 19, Vite 6, TanStack) не трогаем
- **Region**: РФ/СНГ — Stripe запрещён; платежи только ЮKassa; Telegram как первичный канал
- **Tooling**: ruff + mypy strict + import-linter обязательны с Phase A — архитектурные правила должны быть выполнимы локально
- **Testing**: backend-тесты используют `httpx ASGITransport` (не реальный сетевой стек) и `pytest-asyncio`
- **Frontend integrity**: `apps/admin-web` — это перенос `./frontend`, никаких правок внутренней структуры или моков в Phase A
- **Placeholders only**: `packages/ui` и `packages/api-client` — только `package.json` + `README.md` в Phase A; никакого реального кода

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Modular monolith (`core` / `modules` / `integrations` / `workers` / `api`) | Соло-разработчик; код держим рядом с фичей; микросервисы преждевременны; глобальные слои Clean Architecture создают inverse-dependency overhead | — Pending |
| Python-пакет называется `app`, не `sportzal` | Короче в импортах; нет коллизии с потенциальным `sportzal-cli` или `sportzal-shared`; единое имя для всех будущих app-target билдов | — Pending |
| `frontend/` → `apps/admin-web/` без переписывания | Frontend уже стабилен (FSD-lite, моки, RBAC, i18n); переписывание — чистая регрессия | — Pending |
| Без multi-tenancy в Phase A | Пет-проект на 1 зал; multi-tenant добавим, только когда появится второй покупатель; преждевременная архитектура усложняет всё на годы | — Pending |
| Без auth в Phase A | Каркас должен быть устойчив без auth; auth — отдельная фаза с собственным дизайном (вероятно через Telegram) | — Pending |
| `import-linter` с Phase A, не позже | Архитектурные границы дешевле закрепить машинно сразу, чем чинить ад нарушений потом | — Pending |
| Pinned РФ-стек (ЮKassa, Telegram, Postgres self-host) | Региональные ограничения известны; нет смысла держать варианты | — Pending |
| `frontend/.git` судьба при переезде в `apps/admin-web` | Сохранить историю через `git subtree` ИЛИ обнулить (`rm -rf .git` + новый коммит)? — открытый вопрос для plan-phase 1 | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
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
*Last updated: 2026-04-30 after initialization*
