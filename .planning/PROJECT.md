# Sportzal

## What This Is

Sportzal — CRM для тренажёрного зала. Пет-проект на один зал: управление клиентами, абонементами, посещениями, расписанием, бронированиями, тренерами, биллингом и уведомлениями. Под рынок РФ/СНГ.

**Текущее состояние (после v1.2 — Memberships + Visits):**
- **Frontend** — admin-панель на React 19 (Vite + TanStack Router) в `apps/admin-web/`. Через `VITE_API_MODE=http` swap-seam идут: `/login`, `/clients/*`, `/memberships`, `/membership-plans` (owner-only), `/visits` (reception check-in с FE-08 a..d edge cases), `/clients/$clientId` (Pattern α: Promise.all loader + ESLint-enforced cross-feature isolation), `/profile` (active sessions UI, http-only по D-22-2). Остальные домены продолжают идти через моки. ~16.8K LOC TS.
- **Backend** — модульный монолит на FastAPI в `apps/backend/app/` (~8.1K LOC Python). Реальные endpoints: `/healthz` + полный `/api/v1/auth/{login,refresh,logout,logout-all,me,telegram/{start,status,verify},sessions,sessions/{family_id}/revoke}` + `/api/v1/clients` (list/get/create/patch/delete) + `/api/v1/membership-plans` (5 endpoints, owner-only) + `/api/v1/memberships` (list/get/sell/cancel) + `/api/v1/visits` (list/get/check-in + `/_meta` gym-hours, Cache-Control 5min). RBAC байт-паритетен с frontend `can.ts` (`OWNER_ONLY` 15 entries) через `Depends(require_permission)` + introspection guard. Архитектурные контракты (`core ⊥ modules`, `modules independent`, `integrations ⊥ modules`) держатся `import-linter`-ом; cross-module callbacks (`ActiveMembershipResolver` Protocol, `register_user_loader`, `HandlerContext`) проходят через composition root `app/main.py`.
- **Auth** — двухканальный: email/password (Argon2id, 12-char min, NIST 800-63B; v1.2 HYG-01/02 закрыли 500 → 401 на verify-error и tampered cookie) + Telegram OTP (отдельный `python -m app.workers.telegram_bot` long-polling worker, deep-link → DM 6-digit code). JWT HS256 access + refresh-rotation family с reuse-window race tolerance в Redis-mirrored sessions. Per-family revoke + logout-all через `/auth/sessions{,/{family_id}/revoke}`. CSRF на каждом mutating endpoint.
- **Memberships + Visits** — `MembershipPlan` каталог с partial unique на `lower(name) WHERE deleted_at IS NULL`; `Membership` с **inclusive `end_date`** + mandatory snapshot pricing (`plan_name_snapshot`/`duration_days_snapshot`/`price_kopecks_snapshot` NOT NULL); ARQ scheduled `expire_memberships` (06:05 Europe/Moscow daily, container `TZ=UTC` + `cron(unique=True, keep_result=60)`); `Visit` с **DB-level race-proof** `gym_date GENERATED ALWAYS AS ((checked_in_at AT TIME ZONE 'Europe/Moscow')::date) STORED` + `UNIQUE (client_id, gym_date)`. Anti-fraud branches: `outside_gym_hours` / `no_active_membership` / `duplicate_checkin` (409 + discriminating code). Telegram self check-in `/checkin` через `HandlerContext.visits_service` + 4 owner-locked Russian DM strings (no oracle leak) + Redis `update_id` dedup at `sz:bot:update:{id}` TTL 1h.
- **Persistence** — Postgres 16 (теперь 7 бизнес-таблиц: `users`, `refresh_tokens`, `otp_codes`, `clients`, `audit_log`, `membership_plans`, `memberships`, `visits`); Alembic naming convention + `MetaData(...)` зафиксированы; миграции 0001–0006 применены. Indexes: `pg_trgm` GIN на `lower(last_name)`/`lower(first_name)`, partial unique на soft-deleted phones, `(client_id, status, end_date DESC)` для resolver, `(client_id, gym_date)` UNIQUE для visits race-proof.
- **Dev infrastructure** — `docker compose up` поднимает backend + Postgres 16 + Redis 7 + Telegram bot worker + ARQ worker (5-й сервис) + одноразовый migrate. CI workflow `.github/workflows/ci.yml` гонит backend + frontend gates параллельно с двойным drift-gate (`apps/backend/openapi.json` byte-stable + `packages/api-client/src/schema.d.ts` regenerated). pytest + httpx ASGITransport + SAVEPOINT-based per-test isolation против реального Postgres; backend suite 569+ tests; admin-web 184+ tests; всё зелёное (ruff + mypy strict + import-linter + eslint).

## Core Value

Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.

## Current Milestone: v1.3 (TBD — planning next milestone)

v1.2 Memberships + Visits shipped 2026-05-08 (9 phases, 36 plans, 63/63 requirements satisfied; 2 accepted-at-planning deviations carried forward as tech-debt). See [milestones/v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md) and `MILESTONES.md` v1.2 entry.

**Carry-forward tech-debt for v1.3:**

- **MEM-04 fail-safe (D-13)** — `resolve_active_membership_by_client` filters by `status='active'` only and relies on Phase 18 ARQ tick to flip expired rows. Add a defence-in-depth `end_date >= today (Europe/Moscow)` filter at the resolver so a missed cron tick doesn't allow check-ins on expired memberships.
- **WR-07 — D-2 expiring-7-days filter** is a no-op in mock mode. Long-term fix is backend `?expiring=true&within=7` so http+mock have parity.
- **D-22-2 — FE-09 Active Sessions UI is http-only by design.** Mock service throws `mock_not_implemented`; live E2E queued in 22-VERIFICATION.md `human_verification:` block (requires running backend + Telegram sandbox).
- **15-foundations SVC001 walker scope** — gate is currently scoped to `clients/service.py`; `auth/service.py:authenticate` has a possible audit-row loss on `login_failed` path. Mitigated by Phase 23 HYG-01 WARNING log + classify_verify_error helper, but the gate scope itself was not extended.

**Likely v1.3 candidates** (from REQUIREMENTS.md "Future Requirements deferred to v1.3+"):

- **Billing (entire category)** — ЮKassa intake + webhooks + 54-ФЗ чеки + refund flows + card vault + receipts UI.
- **Memberships extras** — freeze (заморозка), visit-count plans, hybrid plans, expiring-soon Telegram notifications, renewal flow.
- **Visits extras** — group lessons attendance, per-class booking integration (depends on schedule module).
- **Audit log read API + UI** — `GET /api/v1/audit-log` (owner-only) with filters.
- **Auth UX** — password reset via Telegram bot DM, HaveIBeenPwned check, webhook-based bot mode for prod.
- **Clients extras** — photo upload, bulk CSV import, tags taxonomy CRUD.

Run `/gsd-new-milestone` to scope and plan v1.3.

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

<!-- v1.2 Memberships + Visits (validated 2026-05-08): -->

- ✓ RBAC + audit + service-write commit gate: `Action.{CREATE, CANCEL, CHECK_IN}` + `Resource.{MEMBERSHIPS, MEMBERSHIP_PLANS, VISITS}` extended; `OWNER_ONLY` 15 entries (added 6 для plan-catalog mutations + membership cancel/delete; reception keeps `(CREATE, MEMBERSHIPS)` + `(CHECK_IN, VISITS)`); `LOCKED_AUDIT_EVENTS` 28-entry frozenset with `audit.emit` literal-string AST gate; `BackendSchemaBase` (Pydantic 2.11 canonical pair, replaced `populate_by_name`); `BusinessService` SVC001 commit-gate AST walker; `core/sql.py:escape_like_pattern` hoisted from `clients/repository.py` — v1.2 (Phase 15)
- ✓ Membership Plans Catalog: `membership_plans` table with `lower(name)` partial unique on `WHERE deleted_at IS NULL`; 5 owner-only endpoints (`/api/v1/membership-plans` GET/POST/PATCH/DELETE) with CSRF; `duration_days` immutable post-creation; soft-delete with 409 `plan_in_use` translation when FK references exist; 3 locked audit events — v1.2 (Phase 16)
- ✓ Membership Instances + Resolver: `memberships` table with mandatory snapshot pricing (`plan_name_snapshot`/`duration_days_snapshot`/`price_kopecks_snapshot` NOT NULL) + `ON DELETE RESTRICT` FK; **inclusive `end_date` semantics** (last valid check-in day); transition guards (only `active → cancelled`, 409 `invalid_transition` otherwise); `resolve_active_membership_by_client` exposed via `ActiveMembership` Protocol slot in `core/dependencies.py` and registered from `app/main.py` (the v1.2 mirror of v1.1 `register_user_loader`) — v1.2 (Phase 17)
- ✓ ARQ scheduled `expire_memberships` daily tick: 06:05 Europe/Moscow (container `TZ=UTC` + `cron(hour=3, minute=5, unique=True, keep_result=60)`); single-statement idempotent SQL with one `audit.emit("membership_expired", actor_user_id=None, ...)` per row; canonical `WorkerSettings` at `app.workers.WorkerSettings` with `on_startup` cron-resolution invariant + `on_job_start`/`on_job_end` structlog `job_id`/`job_name` contextvars (Pitfall 14 RequestIdMiddleware mirror); 5th `arq-worker` docker-compose service — v1.2 (Phase 18)
- ✓ Visits — DB-level race-proof 1/day enforcement: `visits` table with `gym_date GENERATED ALWAYS AS ((checked_in_at AT TIME ZONE 'Europe/Moscow')::date) STORED` + `UNIQUE (client_id, gym_date)` (Postgres wins the race, not app-layer; proven by VIS-TEST-01 concurrent test); reception `POST /api/v1/visits` with three rejection branches (`outside_gym_hours` / `no_active_membership` / `duplicate_checkin`) returning 409 with discriminating `code`; `GET /api/v1/visits/_meta` for gym-hours window with `Cache-Control: public, max-age=300` — v1.2 (Phase 19)
- ✓ Telegram bot `/checkin` self check-in: handler via `HandlerContext.visits_service` (D-10 worker→visits_service relaxation parallel to D-06); 4 owner-locked Russian DM strings (no oracle leak — never includes client name, end_date, hours, or membership status; same DM for stranger and expired-membership); Redis `update_id` dedup at `sz:bot:update:{update_id}` TTL 1h (fail-open per D-20-3); D-5 success DM includes days-remaining with two locked Russian variants — v1.2 (Phase 20)
- ✓ OpenAPI drift gate refresh + api-client codegen: byte-stable `apps/backend/openapi.json` + regenerated `packages/api-client/src/schema.d.ts` exposing all v1.2 typed paths (membership-plans, memberships, visits, sessions, `_meta`); `schema.contract.test.ts` forward-guard pins v1.2 paths and conditionally probes sessions paths so codegen regressions surface before admin-web consumption — v1.2 (Phase 21)
- ✓ admin-web wiring on `VITE_API_MODE=http`: full v1.2 flow ships with `/membership-plans` (owner-only `beforeLoad`), `/memberships`, `/visits` reception check-in (FE-08 a..d edges: top-5 disambiguation, already-checked-in HH:MM badge, expires-today informational badge with button stays enabled, outside-hours disable + tooltip), `/clients/$clientId` Pattern α route (Promise.all loader of 3 `ensureQueryData` calls + ESLint `import/no-restricted-paths` zone forbidding `features/clients → features/{memberships,visits}`), `/profile` active-sessions UI (http-only по D-22-2); cheap-win differentiators D-2/D-3/D-5 — v1.2 (Phase 22)
- ✓ Auth hygiene + active sessions backend: HYG-01 `/auth/login` Argon2 verify-error → 401 `invalid_credentials` (was 500), structlog WARNING; HYG-02 tampered cookie UUID → 401 `invalid_session` (was 500); HYG-03 `GET /api/v1/auth/sessions` lists family records and `POST /api/v1/auth/sessions/{family_id}/revoke` (CSRF) revokes a single family — feeds FE-09 SessionsList/LogoutAllDialog — v1.2 (Phase 23)

### Active (v1.3 — TBD)

См. `MILESTONES.md` v1.2 entry для shipped baseline. Run `/gsd-new-milestone` to scope v1.3 (likely candidates listed in **Current Milestone** section above: Billing / Memberships extras / Visits extras / Audit log read API+UI / Auth UX / Clients extras).

**Tech-debt carried forward from v1.2:**

- MEM-04 D-13 — resolver fail-safe (defence-in-depth `end_date >= today` filter)
- WR-07 — D-2 expiring filter mock/http parity gap
- 15-foundations — SVC001 walker scope extension to `auth/service.py`
- 22-VERIFICATION.md `human_verification:` queue (6 interactive smoke tests pending live backend / Telegram sandbox)

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
- **Текущий codebase (после v1.2):** ~8.1K LOC Python в `apps/backend/app/` (4 бизнес-модуля: auth, clients, memberships, visits); комплексный test suite (569+ tests: unit + integration с pytest-asyncio + httpx ASGITransport + SAVEPOINT-based per-test isolation, plus VIS-TEST-01 real-Postgres concurrent race test, ARQ-TEST-01/02 cron correctness + idempotency); admin-web ~16.8K LOC TS (184+ tests); 5 docker-compose services (`web`, `migrate`, `postgres`, `redis`, `telegram-bot`, `arq-worker`).
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
| Phase 21 — OpenAPI drift gate refresh shipped without sessions endpoints (D-21-1); auto-derived operationIds retained (D-21-3); `packages/api-client/src/schema.contract.test.ts` forward-guard pins the v1.2 typed paths and conditionally probes sessions paths (D-21-4 + D-21-2). | Phase 23 owns the sessions endpoints; its merge will trigger its own drift-gate refresh independently. Contract test catches future codegen regressions (openapi-typescript major bumps, accidental router prefix typos, operationId collisions) before admin-web consumption. | ✓ Good — v1.2 (Phase 21) |
| Phase 22 — Pattern α: `/clients/$clientId` route loader composes `Promise.all([ensureQueryData × 3])` and the page imports blocks from sibling features; `features/clients` cannot import `features/memberships` or `features/visits` (ESLint `import/no-restricted-paths` + negative-test fixture + `verify-pattern-alpha.sh`). FE-09 Active Sessions ships http-only by design (D-22-2): mock throws `mock_not_implemented`. Money stays in kopecks at the form boundary (BLK-04 fix). | Compose at the route layer (which already coordinates loaders), not at the feature layer (which would force `features/clients` to know about the other two). Mock parity for sessions is non-trivial (would require a stateful refresh-rotation simulation) and the use-case requires a live backend anyway. Money precision in form state preserves the CLAUDE.md "integer minor units" invariant across edit roundtrips. | ✓ Good — v1.2 (Phase 22) |
| Phase 18 ARQ 0.28 reconciliation — REQUIREMENTS.md ARQ-03 prose updated to `keep_result=60`; arq pin remains `>=0.28`. | `keep_cronjob_progress=60` was renamed `keep_result=60` in ARQ 0.28 (parameter dropped from `cron(...)` upstream). Editing prose preserves the SQL-level idempotency gate as defence-in-depth and avoids pinning to an EOL ARQ minor; reverting the worker code was rejected. | ✓ Good — v1.2 (closed during /gsd-complete-milestone pre-flight 2026-05-08) |

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
*Last updated: 2026-05-08 — v1.2 (Memberships + Visits) milestone shipped*
