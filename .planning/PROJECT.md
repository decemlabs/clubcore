# Sportzal

## What This Is

Sportzal — CRM для тренажёрного зала. Пет-проект на один зал: управление клиентами, абонементами, посещениями, расписанием, бронированиями, тренерами, биллингом и уведомлениями. Под рынок РФ/СНГ.

**Текущее состояние (после v1.1 — Auth + Clients):**
- **Frontend** — admin-панель на React 19 (Vite + TanStack Router) в `apps/admin-web/`. Routes `/login` (двухтабовый: email/password + Telegram OTP) и `/clients/*` (full CRUD + поиск/фильтры/сортировка) идут через `VITE_API_MODE=http` swap-seam → `@sportzal/api-client` → реальный backend. Остальные домены (memberships, billing, etc.) продолжают идти через моки. ~12.8K LOC TS.
- **Backend** — модульный монолит на FastAPI в `apps/backend/app/` (~4.4K LOC Python). Реальные endpoints: `/healthz` + полный `/api/v1/auth/{login,refresh,logout,logout-all,me,telegram/{start,status,verify}}` + `/api/v1/clients` (list/get/create/patch/delete). RBAC байт-паритетен с frontend `can.ts` через `Depends(require_permission)` + introspection guard. Архитектурные контракты (`core ⊥ modules`, `modules independent`, `integrations ⊥ modules`) держатся `import-linter`-ом.
- **Auth** — двухканальный: email/password (Argon2id, 12-char min, NIST 800-63B) + Telegram OTP (отдельный `python -m app.workers.telegram_bot` long-polling worker, deep-link → DM 6-digit code). JWT HS256 access + refresh-rotation family с reuse-window race tolerance в Redis-mirrored sessions. CSRF на каждом mutating endpoint.
- **Persistence** — Postgres 16 (тablitsy: `users`, `refresh_tokens`, `otp_codes`, `clients`, `audit_log`); Alembic naming convention + `MetaData(...)` зафиксированы перед первой бизнес-миграцией; `pg_trgm` GIN-индексы на `lower(last_name)`/`lower(first_name)`; partial unique index на `clients.phone WHERE deleted_at IS NULL`.
- **Dev infrastructure** — `docker compose up` поднимает backend + Postgres 16 + Redis 7 + Telegram bot worker + одноразовый migrate. CI workflow `.github/workflows/ci.yml` гонит backend + frontend gates параллельно с двойным drift-gate (`apps/backend/openapi.json` byte-stable + `packages/api-client/src/schema.d.ts` regenerated). pytest + httpx ASGITransport + SAVEPOINT-based per-test isolation против реального Postgres. ruff + mypy strict + import-linter — все зелёные.

## Core Value

Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.

## Current Milestone: v1.2 Memberships + Visits

**Goal:** Превратить CRM из «реестра клиентов» в операционный инструмент зала: продажа абонемента → ежедневная отметка посещений (двухканально: reception manual + клиент сам через Telegram bot).

**Target features:**

- **Memberships module** (`apps/backend/app/modules/memberships/`) — `MembershipPlan` (owner-only каталог: name, duration_days 30/90/180/365, price_kopecks, active flag) + `Membership` instance (client_id, plan_id, snapshot цены/длительности на момент покупки, start_date, end_date, status `active|expired|cancelled`, cancelled_at). ARQ daily scheduled job `expire_memberships`. Owner-only manual cancel. Audit log writes.
- **Visits module** (`apps/backend/app/modules/visits/`) — `Visit` (client_id, membership_id, checked_in_at, channel `reception|telegram_bot`, checked_in_by). Reception manual check-in через admin-web (поиск → кнопка). Self check-in через Telegram bot `/checkin` команду (расширение существующего ptb-22 worker), бот отвечает «✅ Отмечено». Anti-fraud: env-config окно часов работы зала + max 1 check-in/день/клиент → 409 conflict. Audit log writes.
- **admin-web wiring (`VITE_API_MODE=http`)** — новые роуты `/memberships/*` (каталог планов owner-only + список) + `/visits/*` (check-in page + history). Client-detail page enhancements: блоки «Memberships» (история + Add) и «Последние посещения». Active sessions UI + revoke на странице профиля.
- **v1.1 hygiene queue (минимум):** Phase 04 CR-01/CR-02 — Argon2 verify-error и невалидный UUID в cookie → 401, не 500.

**Key context:**

- **Billing откладываем в v1.3** — продажа в v1.2 = manual (owner создаёт Membership с `paid_at` без ЮKassa).
- **Без freeze, без visit-count plans, без expiring-soon notifications** — простые time-based абонементы; единственный Telegram-DM в v1.2 — это check-in confirm.
- **Pattern из v1.1 переиспользуется:** module template (`router/service/repository/schemas`), soft-delete + partial unique (если применимо), audit log, OpenAPI drift gate end-to-end, RBAC parity test, three-way contract enforcement.
- **ARQ — первый реальный scheduled job** (до этого только skeleton): `expire_memberships` daily.
- **Telegram bot — первая нетривиальная команда после `/start`** (`/checkin` с anti-fraud + DM-ответами); расширяет существующий long-polling worker, не отдельный процесс.

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

<!-- Phase B v1.1 (validated 2026-05-07): -->

- ✓ Auth foundations: JWT HS256 + Argon2id + httpOnly cookie pair (`sz_access`/`sz_refresh`) + CSRF cookie + camelCase wire format + pagination contract `{items, total, page, pageSize}` + Alembic naming convention + `UUIDPkMixin`/`TimestampMixin`/`SoftDeleteMixin` — v1.1 (Phase 4)
- ✓ Email/password auth: `/auth/login|refresh|logout|logout-all|me`; refresh-rotation family с reuse-window race tolerance; Redis-mirrored sessions; rate-limit 5/15min → 429; SAVEPOINT-based per-test isolation против реального Postgres — v1.1 (Phase 5)
- ✓ Server-side RBAC: `Role`/`Action`/`Resource` StrEnums + 9-entry `OWNER_ONLY` byte-paritet с admin-web `can.ts`; `Depends(require_permission)` на каждом business-route + route-introspection guard; CSRF dependency на POST/PATCH/DELETE; three-way parity test — v1.1 (Phase 6)
- ✓ Telegram OTP channel: отдельный `python -m app.workers.telegram_bot` ptb-22 long-polling worker (4-й docker-compose service); deep-link `/start <token>` → 6-digit DM (TTL 5min, max 5 attempts); 409 `bot_not_started` с deep-link URL — v1.1 (Phase 7)
- ✓ Clients CRUD + audit log: full CRUD с E.164 phone validation, partial unique index на `phone WHERE deleted_at IS NULL`, `pg_trgm` GIN-indexed ILIKE search, owner-only soft-delete, LIKE-escape `%`/`_`/`\` (CR-01 PII hardening); `audit_log` writes из auth + clients — v1.1 (Phases 8 + 14)
- ✓ OpenAPI drift gate + типизированный api-client: lifespan-safe `export_openapi.py`, byte-stable `openapi.json`, CI `git diff --exit-code` на backend spec И на сгенерированный `schema.d.ts`; `fetcher.ts` с single-flight 401→refresh→retry — v1.1 (Phase 9)
- ✓ admin-web wiring: `/login` (email/password + Telegram OTP tabs) + `/clients/*` (URL-driven search/pagination, ReUI DataGrid, optimistic mutations с rollback, RHF+Zod) полностью на `VITE_API_MODE=http`; остальные домены остаются на mocks без регрессий; ESLint ban на raw `fetch(` — v1.1 (Phases 10 + 11 + 13)

### Active (v1.2 — Memberships + Visits)

См. `.planning/REQUIREMENTS.md` для полного списка с REQ-ID. Высокоуровневые категории:

- **Memberships:** `MembershipPlan` каталог (owner-only CRUD), `Membership` per-client (snapshot цены/длительности), lifecycle `active → expired` (ARQ daily) + manual cancel (owner-only), audit
- **Visits:** Reception manual check-in + self check-in через Telegram bot `/checkin`, валидация active membership + anti-fraud (gym-hours window + 1/день/клиент), audit
- **admin-web wiring:** `/memberships/*` + `/visits/*` через `VITE_API_MODE=http`; enhancements на client-detail (Memberships + Visits history); Active sessions UI + revoke
- **v1.1 hygiene минимум:** Phase 04 CR-01/CR-02 — Argon2/UUID error mapping → 401

**Перенесено в v1.3+ (deferred from v1.1):**

- **Billing:** ЮKassa intake/webhooks/чеки 54-ФЗ/refunds (вся платёжная интеграция)
- **Auth UX:** password reset через Telegram bot DM, HaveIBeenPwned check, webhook-based bot mode для prod
- **Audit:** `GET /api/v1/audit-log` (owner-only) + read UI
- **Clients:** photo upload, bulk CSV import, tags taxonomy CRUD
- **v1.1 hygiene остатки:** Phase 06 audit `user_id` plumbing, Phase 03 advisories (env parser, db_session rollback semantics, postgres LAN exposure, backup_db.sh staging)
- **Memberships extras:** freeze, visit-count plans, expiring-soon notifications, hybrid plans
- **Next business slice:** trainers / schedule / bookings — TBD по приоритету

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
- **Команда:** один backend-разработчик + AI-агенты. Frontend знает слабее — admin-панель уже скаффолдена и трогать её внутренности нельзя без явного решения.
- **Backend пакет:** имя Python-пакета — **`app`** (не `sportzal`, не `src/sportzal`). Корень в `apps/backend/app/`.
- **Архитектурный стиль:** modular monolith с физическим разделением `core` / `modules` / `integrations` / `workers` / `api`. НЕ Clean Architecture. НЕ микросервисы.
- **Архитектурные инварианты (контролируются `import-linter`):**
  - `core` ничего не знает про `modules`
  - `modules` не импортируют друг друга напрямую
  - `integrations` не импортируют `modules` (исключение D-06 для `workers/telegram_bot.py` → `modules.auth.telegram_service` задокументировано в docstring)
- **Структура одного бизнес-модуля:** `router.py`, `service.py`, `models.py`, `schemas.py` + по мере роста `repository.py`, `permissions.py`, `constants.py`. Validated на `clients` модуле в Phase 8.
- **Cross-module callbacks:** Protocol-based registration в `app/main.py` composition root (`register_user_loader`, `HandlerContext`) — preserves `modules-independent` контракт.
- **Будущая трансформация в multi-tenant SaaS** возможна, но НЕ должна влиять на решения сейчас.
- **Текущий codebase (после v1.1):** ~52 Python source файлов в `apps/backend/app/` (~4.4K LOC); комплексный test suite (unit + integration с pytest-asyncio + httpx ASGITransport + SAVEPOINT-based per-test isolation); admin-web ~12.8K LOC TS; 4 docker-compose services (`web`, `migrate`, `postgres`, `redis`, `telegram-bot`).
- **CI:** `.github/workflows/ci.yml` гонит backend (`uv run ruff check`, `uv run mypy --strict`, `uv run pytest`, `uv run python apps/backend/scripts/export_openapi.py && git diff --exit-code apps/backend/openapi.json`) + frontend (`pnpm typecheck`, `pnpm lint`, `pnpm test`, `pnpm --filter @sportzal/api-client codegen && git diff --exit-code`) gates параллельно.

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
| Pinned РФ-стек (ЮKassa, Telegram, Postgres self-host) | Региональные ограничения известны | ✓ Good — v1.1 (Telegram bot validated; ЮKassa остаётся для billing-милстоуна) |
| Compose `environment:` precedence over `env_file: .env` (CR-01 fix) | Сохраняет `.env.example` как Variant 1 single source of truth без форка `.env.compose` / `.env.local` | ✓ Good — v1.0 (03-06) |
| REVERSED middleware add order: TimingMiddleware first, RequestIdMiddleware second | RequestId должен запускаться первым на incoming, чтобы timing log нёс request_id | ✓ Good — v1.0 (Phase 02 P06) |
| PEP 735 `[dependency-groups].dev` over deprecated `[tool.uv].dev-dependencies` | uv 0.5+ ругается deprecation warning; PEP 735 — стандарт | ✓ Good — v1.0 (quick 260501-ndi) |
| RBAC primitives живут в `core` (не `modules/auth`) | `core ⊥ modules` контракт остаётся, и любой модуль может импортировать `require_permission` без cross-module-нарушения | ✓ Good — v1.1 (Phase 4) |
| Cross-module callbacks через Protocol + регистрацию в `app/main.py` (composition root) | Сохраняет `modules-independent` контракт — `auth` не импортирует `clients`, telegram-handlers не импортируют `auth.service` напрямую | ✓ Good — v1.1 (Phase 4-7) |
| Telegram bot — отдельный процесс (`python -m app.workers.telegram_bot`), НЕ ARQ task | Long-polling — wrong fit для ARQ; ARQ остаётся для fire-and-forget jobs (e.g. send-OTP retry) | ✓ Good — v1.1 (Phase 7) |
| Backend wire format = camelCase via Pydantic `alias_generator=to_camel` + `populate_by_name=True` | Frontend остаётся single source of truth для контракта; Python identifiers внутри backend остаются snake_case | ✓ Good — v1.1 (Phase 4) |
| Pagination envelope `{items, total, page, pageSize}` | Match frozen frontend pagination expectations; никогда bare arrays | ✓ Good — v1.1 (Phase 4) |
| Refresh-rotation family с reuse-window race tolerance (~5s) | Mitigates parallel-request race; reuse выходит за окно → revoke entire family + audit | ✓ Good — v1.1 (Phase 5) |
| `clients.list_alive` LIKE-escape `%`/`_`/`\\` (CR-01 closure) | Reception user не может `?q=%` → dump всего roster (PII over-exposure) | ✓ Good — v1.1 (Phase 14) |
| OpenAPI drift gate: byte-stable `openapi.json` + committed `schema.d.ts` + CI `git diff --exit-code` на оба | FE↔BE drift невозможен без явного "I really meant it" commit | ✓ Good — v1.1 (Phase 9) |
| `VITE_API_MODE=http` swap-seam scoped to `/login` + `/clients/*` only | Phased rollout: остальные домены остаются на mocks до подтверждения паттерна; nodal regression risk = 0 | ✓ Good — v1.1 (Phase 10) |
| Soft-delete partial unique index `WHERE deleted_at IS NULL` | Phone reuse после soft-delete без data-loss; hard-delete никогда не exposed | ✓ Good — v1.1 (Phase 8) |
| 12-char min password, no complexity, no rotation, no lockout (NIST 800-63B 2024) | Counter-productive по NIST guidance; rate-limit вместо lockout (DoS amplifier) | ✓ Good — v1.1 (Phase 5) |
| `clients/service.py` write paths должны явно `await session.commit()` | `get_db` auto-rolls-back at request exit (database.py:145); audit logs уже зеркалят в structlog но БД-rows не коммитились | ✓ Good — v1.1 (Phase 12.1, quick-task 260504-fst) |
| Membership `end_date` is INCLUSIVE — last valid check-in day | Single rule across check-in / ARQ filter / display; ARQ uses `end_date < CURRENT_DATE` (strict) so the last day stays valid; inclusive `end_date = start_date + duration_days - 1` | ✓ Good — v1.2 (Phase 15) |
| `gym_date = (checked_in_at AT TIME ZONE 'Europe/Moscow')::date` materialised as a STORED Postgres column with `UNIQUE (client_id, gym_date)` | DB-level enforcement of "1 visit per client per gym day" — race-safe (Postgres wins, not app-layer); `gym_date` becomes the audit/report grouping key; container `TZ=UTC` so the AT TIME ZONE conversion is unambiguous | ✓ Good — v1.2 (Phase 15 / VIS-01) |
| Accepted residual friend-fraud risk for v1.2 single-zal scope | Telegram self check-in can be impersonated (member shares Telegram account); mitigation = photo turnstile (hardware tier) deferred to v1.3+; acceptable risk for one-zal pet-project scope | ✓ Accepted — v1.2 (Phase 15) |
| D-20: Telegram `/checkin` handler — Redis SET-NX-EX `sz:bot:update:{update_id}` TTL 1h dedup (fail-open per D-20-3); ClientNotLinkedError reuses `_DM_NO_MEMBERSHIP` for anti-oracle (D-20-9); 4 locked Russian DM strings owner-signed-off (AUTH-TG-11); HandlerContext.visits_service via D-10 worker→modules edge parallel to D-06 | Single-handler dedup keeps blast radius small; same DM for stranger and expired-membership defeats account enumeration; Russian-only locked code constants match REQUIREMENTS verbatim; D-10 narrative addendum mirrors D-06 (no new import-linter contract) | ✓ Good — v1.2 (Phase 20) |

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
*Last updated: 2026-05-07 — v1.2 (Memberships + Visits) milestone started*
