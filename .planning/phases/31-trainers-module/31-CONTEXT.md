# Phase 31: Trainers Module — Context

**Gathered:** 2026-05-14
**Status:** Ready for planning
**Mode:** `/gsd-discuss-phase 31 --auto` (no interactive prompts; recommended defaults selected for every gray area; full audit trail in `31-DISCUSSION-LOG.md`).

<domain>
## Phase Boundary

Phase 31 материализует первый бизнес-модуль из v1.4 milestone — каталог тренеров — поверх bedrock, заложенного в Phase 30. Конкретно:

- Owner-only CRUD на новом `trainers` table (8 requirements — TRN-01..08).
- Soft-deactivation через `is_active` flag; hard-delete только при отсутствии FK refs из `pt_sessions` (409 `trainer_in_use`).
- Защитный double-wired Protocol slot `register_trainer_by_id_resolver` (готов под будущий PT-session валидатор в Phase 34, который ещё не подключает потребителя).
- Reception видит только `?active=true` срез для будущего PT-session picker; `(LIST, TRAINERS)` уже expressed через `(VIEW, TRAINERS)` outside OWNER_ONLY (Plan 30-02 commit e8beda0).
- 4 locked audit events эмитятся per lifecycle transition (`trainer_created`/`_updated`/`_deactivated`/`_reactivated`), schemas already locked in `app/core/audit_payloads.py` (Plan 30-01).
- admin-web `/trainers` route в mock-режиме (table + active filter pill + RHF/Zod create/edit modal + deactivate/reactivate + hard-delete с inline 409 surface). HTTP wiring живёт в Phase 35 (FE-10..18 + OpenAPI drift gate).

**Out of scope (deferred):**
- `pt_sessions` table + FK enforcement → Phase 34 (PT-Session Recording).
- HTTP-mode adapter `apps/admin-web/src/shared/api/services/http/trainers.ts` → Phase 35.
- Trainer scheduling, shift management, payroll, comissions → out of v1.4 entirely (см. PROJECT.md «Tech-debt carryover»: тренеры — только справочник).
- Trainer photo / bio / specializations → not in requirements; future phase if needed.
- Backfilling `trainer_name_snapshot` для исторических PT-сессий → B-05 lives в Phase 34, не здесь.

</domain>

<decisions>
## Implementation Decisions

### Migration shape (TRN-01 → `0011_trainers.py`)

- **D-31-01:** Mixin composition — mirror `clients.models.Client` shape, но БЕЗ `created_by_user_id` FK. Trainers — это owner-only справочник без creator-attribution requirement в TRN-* req-set; добавлять FK на `users` создаст лишний RESTRICT-чейн без бизнес-ценности. Использовать только `Base + UUIDPkMixin + TimestampMixin + SoftDeleteMixin` (3 mixins, не 4).
  - **Why:** TRN-01 не упоминает `created_by_user_id`; membership_plans тоже без него; ниже attack-surface на cascade DELETE.
- **D-31-02:** Колонки — `full_name TEXT NOT NULL`, `phone TEXT NULL` (free-text, E.164 validated на schema layer per D-10 reuse), `is_active BOOLEAN NOT NULL DEFAULT TRUE`, плюс mixin-managed `id UUIDv4 PK`, `created_at`, `updated_at`, `deleted_at TIMESTAMPTZ NULL`.
  - **Why:** Verbatim per TRN-01.
- **D-31-03:** Constraints — partial UNIQUE на `phone WHERE deleted_at IS NULL AND phone IS NOT NULL` (зеркало `uq_clients_phone_alive`). Имя индекса: `uq_trainers_phone_alive` (consistency naming convention).
  - **Why:** TRN-01 verbatim; reuse existing pattern; зрелый soft-delete-resilient uniqueness.
- **D-31-04:** Migration файл `apps/backend/alembic/versions/0011_trainers.py`. revision = `"0011_trainers"`, down_revision = `"0010_notifications"`. Безусловный `CREATE TABLE` (никакой conditional skip) — Alembic autogenerate уже корректно резолвит таблицу after Plan 30-03 placeholder model.
  - **Why:** Mirror v1.3 миграции 0007–0010 — линейная цепочка.

### `phone` validation (TRN-01 schema layer)

- **D-31-05:** Reuse `PHONE_REGEX = r"^\+[1-9]\d{1,14}$"` (D-10 verbatim) на Pydantic level в `apps/backend/app/modules/trainers/schemas.py`. Phone optional — `phone: str | None = None` с `@field_validator` валидирующим только non-None values.
  - **Why:** Single E.164 regex проекта; разделение источника правды по двум модулям ведёт к drift.

### Hard-delete + soft-delete semantics (TRN-03 / TRN-05)

- **D-31-06:** DELETE endpoint = HARD DELETE (`session.delete(trainer)` или `delete(Trainer)`). При попытке удалить тренера с FK refs из `pt_sessions` — 409 `trainer_in_use` (TRN-05).
  - **Why:** TRN-05 verbatim.
- **D-31-07:** Поскольку Phase 34 ещё не создал `pt_sessions`, в Phase 31 hard-delete всегда успешен (никаких FK refs не существует). Но 409 detection logic ДОЛЖЕН быть написан pre-emptively по контракту, не как TODO. Реализация: try-except на `sqlalchemy.exc.IntegrityError` с `pgcode='23503'` (ForeignKeyViolation) → map в `AppError(409, "trainer_in_use")`. Test покрывает negative path через synthetic FK-violation fixture (либо deferred test until Phase 34 — pre-emptive interface).
  - **Why:** SVC001 + audit-payload предзагрузка уже locked события `trainer_deactivated/_reactivated/_created/_updated`; то же качество fail-fast 409 mapping обязано существовать до Phase 34 — иначе обнаружение бага в Phase 34 потребует править Phase 31 module retroactively.
- **D-31-08:** `deleted_at` column остаётся объявленным (SoftDeleteMixin), но НЕ читается/пишется через CRUD endpoints. Назначение в Phase 31 — поддержка partial UNIQUE на `phone WHERE deleted_at IS NULL` (i.e. survives reuse если когда-нибудь появится soft-delete API). Existing soft-delete machinery (SoftDeleteMixin) обеспечивает column shape; в репозитории фильтр `deleted_at IS NULL` ВСЕГДА применяется при list/get (consistency с clients pattern).
  - **Why:** TRN-01 предписывает column shape; partial UNIQUE правило ссылается на `deleted_at IS NULL`; легче оставить inert column чем переписывать UNIQUE.

### Reception filter + `is_active` semantics (TRN-03 / TRN-04)

- **D-31-09:** Endpoint `GET /api/v1/trainers` принимает query param `active: bool | None = None`. `active=true` → `WHERE is_active = true AND deleted_at IS NULL`; `active=false` → only inactive; omit → both. Reception имеет permission `(VIEW, TRAINERS)` (не в OWNER_ONLY), owner имеет implicit access ко всем срезам.
  - **Why:** TRN-04 говорит «reception видит только активных в PT-session picker»; owner CRUD page должна видеть оба status.
- **D-31-10:** Pagination envelope `{items, total, page, pageSize}` per project convention (D-14). Дефолт page=1, pageSize=50 (mirror clients/memberships).
- **D-31-11:** Deactivate/reactivate реализуются через `PATCH /api/v1/trainers/{id}` с body `{isActive: bool}`. Никакого отдельного `POST /api/v1/trainers/{id}/deactivate` endpoint — не нужно: state-flip simple boolean, нет invariants (mirror v1.3 freeze: freeze ИМЕЛ invariants → отдельный endpoint; для trainers это перебор).
  - **Why:** TRN-03 verbatim — «PATCH разрешает деактивацию/реактивацию».
- **D-31-12:** Service layer detects переход `is_active: True → False` → emit `trainer_deactivated`; `False → True` → emit `trainer_reactivated`; иначе нейтральный PATCH (no-op для `is_active` подмножества) → emit `trainer_updated` для других field changes. Если PATCH меняет И `is_active`, И `full_name`/`phone` одновременно — эмитим **только** state-flip event (`_deactivated`/`_reactivated`) ПЛЮС `trainer_updated` для других fields (2 события). Атомарно в одной UoW.
  - **Why:** Lifecycle audit чище если state flip — отдельный event; semantic match с payload schema (`TrainerDeactivatedPayload` = `{trainer_id}` без diff).

### Protocol slot wiring (TRN-06)

- **D-31-13:** Shape — `TrainerByIdResolver = Callable[[AsyncSession, UUID], Awaitable[Trainer | None]]`. Async callback по same shape что `UserLoader` (Phase 5) / `ActiveMembershipResolver` (Phase 17) / `ClientByTelegramResolver` (Phase 19). Возвращает `Trainer` ORM instance (НЕ DTO — Protocol slot internal-only).
  - **Why:** Shape consistency; future PT-session validator вызовет resolver внутри service.py и проверит `trainer.is_active`.
- **D-31-14:** Location — `app/core/dependencies.py` рядом с тремя существующими `register_*` функциями. Wiring точки: `app/main.py:create_app()` (production) И `app/workers/telegram_bot.py:main()` (bot, defensive double-wiring per REG-29-03 lesson из v1.3).
  - **Why:** TRN-06 verbatim — двойная привязка обязательна, даже если bot не consumer в v1.4. Pattern uniformly применён к 3 предыдущим slots.
- **D-31-15:** Implementation function `apps/backend/app/modules/trainers/service.py::resolve_trainer_by_id(session, trainer_id) -> Trainer | None` — filter `deleted_at IS NULL` (consistency), НЕ фильтрует `is_active` (вызывающая сторона решает). Возврат None если row missing/soft-deleted.
  - **Why:** Phase 34 валидация PT-session должна сама различать «тренер не существует» от «тренер деактивирован» для разных 409 message текстов.

### Audit emission (TRN-07)

- **D-31-16:** 4 event types, payload schemas УЖЕ locked в `app/core/audit_payloads.py` (Plan 30-01 commit ID see STATE.md). Service вызывает `await audit.emit(session, actor, event=..., resource_type='trainer', resource_id=trainer.id, **payload_kwargs)` — verbatim per existing emit-callsite pattern в clients/memberships.
- **D-31-17:** `trainer_updated` payload `{trainer_id, changed_fields: list[str]}` — `changed_fields` это lower_snake field-names на ORM-level (e.g. `["full_name", "phone"]`). НЕ camelCase. Diff computed против ORM instance до flush — не против request DTO (consistency с clients update audit).
  - **Why:** Audit storage shape — internal/snake_case; downstream readers (reports в v1.5) consume Python field names.
- **D-31-18:** Audit emit ПЕРЕД commit, но В ТОЙ ЖЕ UoW что mutation. SVC001 walker уже включает `trainers/service.py` в scope (Plan 30-03 D-30-05) — каждая mutation function ДОЛЖНА явно `await session.commit()` либо явно declare caller-owned-tx (D-03 conventions). Trainers — full service module: `await session.commit()` в конце каждой mutation (mirror clients/membership_plans, не memberships).
  - **Why:** Уже архитектурно зафиксировано; SVC001 fail-fast на пропуск commit.

### admin-web `/trainers` route (TRN-08)

- **D-31-19:** Route file `apps/admin-web/src/routes/_protected/trainers.tsx`. `beforeLoad` гард: `can(role, 'view', 'trainers')` — TRN-08 говорит owner-only `beforeLoad`. На самом деле verbatim TRN-08: «owner-only `beforeLoad` guard». Reception всё ещё может вызвать `GET /api/v1/trainers?active=true` через PT-session picker (Phase 35), но route `/trainers` сам по себе — owner-only. Поэтому `beforeLoad` ⇒ `if (role !== 'owner') throw redirect({to:'/', search:{forbidden:'trainers'}})`.
  - **Why:** TRN-08 verbatim — admin page для тренеров — owner-territory; reception видит trainers только через future PT-session picker (Phase 35), не через `/trainers` route.
- **D-31-20:** Feature folder `apps/admin-web/src/features/trainers/`:
  - `model/schema.ts` — Zod schemas (create/update/listQuery) — общие для RHF form И mock-service input validation.
  - `api/keys.ts` + `api/hooks.ts` — TanStack Query (per-feature `trainersKeys` factory + `useTrainersList`/`useTrainer`/`useCreateTrainer`/`useUpdateTrainer`/`useDeleteTrainer`).
  - `components/` — `TrainersTable.tsx`, `TrainerFormDialog.tsx` (create+edit), `DeleteTrainerAlertDialog.tsx`, `ActiveFilterPill.tsx`.
- **D-31-21:** Delete confirmation — AlertDialog (shadcn) с inline error surface для 409 `trainer_in_use` (mirror existing pattern из memberships cancel/refund AlertDialog scheme). Error displayed via `<Alert variant="destructive">` inside dialog body, не toast (critical error → blocking surface per project convention).
- **D-31-22:** Active filter pill — shadcn `<Badge>` или `<ToggleGroup>` (вариант `<ToggleGroup>` с 3 опциями: «Активные» / «Неактивные» / «Все»). Mirrors v1.3 «Заморожен» pill UX на `/memberships`. State хранится в URL search params (`?active=true|false|undefined`) для shareability + browser-back consistency.
- **D-31-23:** Mock service `apps/admin-web/src/shared/api/services/mock/trainers.ts` — следует Faker-backed in-memory DB pattern из `mock/clients.ts`. localStorage key `sportzal:mock:v1` already versioned; trainers seed добавляется в новой migration entry mock-db (бамп `sportzal:mock:v1` не нужен — migrations within-version handled). Seed: 8 fake trainers (5 active, 3 inactive) с `faker.person.fullName({locale:'ru'})` + 50% phone presence.
- **D-31-24:** RHF + Zod integration через `@hookform/resolvers/zod` (already in deps). Same schema validates form AND mock service input (defence-in-depth + UI inline error parity).

### Plan splitting

- **D-31-25:** Phase разбивается на **2 plans** (compact, atomic, parallel-eligible after backend types stable):
  - **Plan 31-01 — Backend trainers module** (TRN-01..07): миграция 0011, `app/modules/trainers/{models,schemas,repository,router,service}.py`, Protocol slot + double-wiring (main.py + telegram_bot.py), audit emit на 4 lifecycle событиях, FK 409 mapping pre-emptive, integration tests (CRUD happy path + 409 phone_exists + RBAC matrix + audit emission tests + SVC001 commit gate passes), backend OpenAPI snapshot bump (`openapi.json` regen).
  - **Plan 31-02 — admin-web `/trainers` mock-mode UI** (TRN-08): mock service `mock/trainers.ts`, feature folder `features/trainers/`, route `/trainers` с owner-only `beforeLoad`, RHF+Zod form, AlertDialog для delete, active filter pill, vitest specs (component-level + mock-service parity + role-gate redirect test). Service swap seam НЕ trogaeм (HTTP wiring живёт в Phase 35).
- **D-31-26:** Plans 01 и 02 parallel-eligible после того как backend Zod-equivalent schemas стабилизируются (буквально через ~30 минут backend Plan 01). Альтернатива (3 plans) — отвергнута: чрезмерная granularность для domain без cross-module symmetries.
  - **Why:** Mirror v1.3 phase split discipline; единый «admin-web mock-mode» плана достаточен (HTTP уходит в Phase 35).

### Claude's Discretion

- Точная форма pagination defaults (page=1, pageSize=50) — planner может калибровать если другие endpoint'ы codified другие defaults, но 50 — текущий convention.
- Reception RBAC nuance: `(VIEW, TRAINERS)` outside OWNER_ONLY уже locked. Но `(LIST, TRAINERS)` per TRN-04 expressed через `(VIEW, TRAINERS)` (Plan 30-02 commit e8beda0 STATE.md note). Никаких новых Action enum entries не добавляется. Planner подтверждает в plan.
- Тестовая стратегия для FK-409 mapping pre-emptive (до `pt_sessions` существует): planner выбирает между (a) synthetic FK fixture через ad-hoc test-only migration в conftest, (b) deferred test до Phase 34 c TODO marker в Phase 31 test file, (c) mock IntegrityError через monkeypatch на repository delete. Рекомендация: (c) — cheapest, no fixture overhead, exercises mapping logic точно.
- Имена admin-web Zod schema полей — следовать существующему convention (`fullName: z.string().min(1).max(200)`, `phone: z.string().regex(PHONE_REGEX).nullable().optional()`, `isActive: z.boolean()`). Точные min/max bounds — planner.
- Сидинг mock-trainers в localStorage: lazy при первом `list()` call vs eager при сервис init — planner. Lazy предпочтителен (mirrors clients/memberships mock).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v1.4 Milestone-level Contracts (CRITICAL)
- `.planning/REQUIREMENTS.md` §TRN — TRN-01..08 verbatim requirements.
- `.planning/ROADMAP.md` §Phase 31 — phase goal + 5 success criteria; depends on Phase 30 (delivered).
- `.planning/PROJECT.md` Key Decisions table — B-01..B-12 v1.4 bedrock decisions; CLAUDE.md project constraints.
- `.planning/STATE.md` §Decisions — Phase 30 D-30-01..D-30-12 implementations log (audit_payloads + RBAC parity + architectural gates).

### Phase 30 Deliverables (CONSUME from Phase 31)
- `apps/backend/app/core/audit_payloads.py` — locked Pydantic schemas `TrainerCreatedPayload`, `TrainerUpdatedPayload`, `TrainerDeactivatedPayload`, `TrainerReactivatedPayload` + `AUDIT_PAYLOAD_SCHEMAS` registry (lines 42–74 + 286–289). Service ДОЛЖЕН передавать payload kwargs verbatim per schema.
- `apps/backend/app/core/audit.py` §`LOCKED_AUDIT_EVENTS` lines 177–180 — 4 trainer events locked. `audit.emit()` валидирует payload против registered schema.
- `apps/backend/app/core/permissions.py` lines 46 + 74 + 78–80 — `Resource.TRAINERS = "trainers"`; `OWNER_ONLY` содержит `(CREATE, TRAINERS)`, `(EDIT, TRAINERS)`, `(DELETE, TRAINERS)` — но НЕ `(VIEW, TRAINERS)` (reception видит для PT-session picker).
- `apps/backend/.importlinter` `[importlinter:contract:modules-independent]` — `trainers` уже в modules list (Plan 30-03). Никаких новых import-linter изменений.
- `apps/backend/tests/unit/test_service_commit_gate.py` SVC001 scope — `trainers/service.py` уже в `_LIVE_MODULES` (Plan 30-03). Каждая mutation в новом service.py ОБЯЗАНА `await session.commit()` либо явно declare caller-owns-tx.
- `apps/admin-web/src/shared/session/can.ts` — `Resource.TRAINERS` + OWNER_ONLY entries уже locked (Plan 30-02 commit e8beda0). Three-way parity test зелёный.
- `apps/admin-web/src/shared/session/registry.ts` — `'trainers'` kebab-case mirror уже locked.

### Reusable Module Pattern (Phase 8 — clients module)
- `apps/backend/app/modules/clients/models.py` — `Client` ORM с mixin composition pattern; partial UNIQUE на phone WHERE deleted_at IS NULL pattern (line 105–110); column-level CHECK constraints.
- `apps/backend/app/modules/clients/schemas.py` — `PHONE_REGEX = r"^\+[1-9]\d{1,14}$"` (D-10, line 42); BackendSchemaBase chain; PATCH semantics (no explicit-null clear v1.1).
- `apps/backend/app/modules/clients/router.py` — 5-endpoint surface; RBAC-04 ordering invariant (permission Depends BEFORE csrf Depends); ResponseEnvelope wrapping.
- `apps/backend/app/modules/clients/service.py` — audit emission pattern; caller-owns-txn vs explicit-commit discipline (clients = explicit-commit — mirror this).
- `apps/backend/app/modules/clients/repository.py` — partial-unique IntegrityError mapping pattern (phone_exists 409); cursor list/filter pattern.

### Reusable Protocol Slot Pattern
- `apps/backend/app/core/dependencies.py` lines 55 (`register_user_loader`), 93 (`register_active_membership_resolver`), 165 (`register_client_by_telegram_resolver`) — three existing slots; trainer slot mirrors verbatim.
- `apps/backend/app/main.py` `create_app()` lines 113–135 — composition root registration discipline.
- `apps/backend/app/workers/telegram_bot.py` lines 27–63 — bot-side defensive double-wiring pattern (REG-29-03 lesson).

### Reusable admin-web Pattern (Phase 15 — membership_plans owner-only catalog)
- `apps/admin-web/src/routes/_protected/membership-plans.tsx` — owner-only `beforeLoad` redirect pattern; table + create/edit modal + delete confirmation; closest analog UX for trainers `/trainers`.
- `apps/admin-web/src/features/memberships/` — feature folder structure (api/keys, api/hooks, components, model) — trainer feature folder следует ту же shape.
- `apps/admin-web/src/shared/api/services/mock/clients.ts` — Faker-backed seed pattern; latency simulation; role enforcement через `can(...)` throw DomainError.
- `apps/admin-web/src/features/memberships/components/FreezeSection.tsx` (или аналогичный inline-error AlertDialog) — pattern для 409 inline error UI (для delete trainer 409 trainer_in_use).

### Prior-Phase Patterns to Mirror
- **v1.1 Phase 8 (clients) — most directly analogous shape.** Trainers structurally идентичен clients (CRUD + soft-delete-aware partial UNIQUE phone), но проще (no tags/emergency_contact/birthday/gender/email).
- **v1.2 Phase 15 (membership_plans) — owner-only catalog precedent.** UX pattern для `/trainers` ближе всего к `/membership-plans`. Immutability invariants там сильнее (price/duration immutable post-creation), а у trainers только `is_active` toggleable; в остальном structurally идентично.
- **v1.3 Phase 24 (foundations) → 25 (freeze)** — приём «foundations phase locks the events + schemas, feature phase consumes them». Phase 31 = feature phase, consuming Phase 30 bedrock.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/core/database.py` `Base + UUIDPkMixin + TimestampMixin + SoftDeleteMixin` — ровно те mixins, что нужны trainers. Trainers использует все 4 (Base + 3 mixins) — `created_by_user_id` НЕ нужен.
- `app/core/dependencies.py` `register_*_resolver` triplet (3 existing slots) — copy-paste shape для `register_trainer_by_id_resolver` (lines 55, 93, 165).
- `app/core/schemas.py` `BackendSchemaBase` + `ResponseEnvelope` + `PaginatedData` + `envelope()` — universal wire-format pieces.
- `app/core/permissions.py` `require_permission(Action, Resource)` + `Resource.TRAINERS` (line 46) — already wired.
- `app/core/audit.py` `audit.emit()` + payload validation (Plan 30-01) — trainer events уже LOCKED + payload schemas зарегистрированы.
- `app/core/audit_payloads.py` `TrainerCreatedPayload` etc. (lines 42–74) — payload schemas locked.
- `apps/backend/app/modules/clients/repository.py` — IntegrityError → 409 phone_exists mapping (re-use логика для trainers `uq_trainers_phone_alive`).
- `apps/admin-web/src/shared/session/can.ts` + `registry.ts` — TRAINERS Resource уже в admin-web (Plan 30-02 byte-parity locked).

### Established Patterns
- **Module placeholder discipline (Phase 30 INFRA-20/21):** `trainers/__init__.py` + `trainers/service.py` placeholders уже существуют (commit be962d7); Plan 31-01 их replaces с реальным content. `import-linter` modules-independent contract уже зелёный → mutating placeholder в production code не нарушает архитектурные правила.
- **SVC001 commit-gate (Plan 30-03 D-30-05):** scope `modules/**/service.py` уже включает `trainers/service.py`. Каждая mutation function в новом service ОБЯЗАНА `await session.commit()` либо вызвать caller-owned-tx alias — иначе CI красный.
- **Three-way RBAC parity (TEST-06 + Plan 30-02):** backend `OWNER_ONLY` ↔ admin-web `can.ts` ↔ `registry.ts` уже byte-parity для TRAINERS. Adding routes/sidebar items НЕ ломает parity test (тест проверяет matrix, не presence routes).
- **Pre-registered audit events (v1.3 Phase 24 + Phase 30 D-30-01):** все 4 trainer events locked в frozenset; emit() validates payload через `AUDIT_PAYLOAD_SCHEMAS` registry. Service callsites вызывают emit с kwargs verbatim per schema, hard-fail на mismatch.
- **PATCH semantics (D-01 from clients):** PATCH принимает `Partial<X>` без explicit-null clear; omit key = leave unchanged. Trainers следует те же rules для `fullName`/`phone`. `isActive` всегда передаётся явно (boolean toggle).
- **Defensive double-wiring (REG-29-03):** Phase 19 урок — composition root в main.py + workers/telegram_bot.py регистрирует одинаковые resolvers, даже если bot не consumer.

### Integration Points
- New file `apps/backend/alembic/versions/0011_trainers.py` — линейная цепочка после `0010_notifications`. Alembic autogenerate теперь корректно резолвит `trainers.models.Trainer` (Plan 30-03 уже добавил placeholder model; Plan 31-01 поднимает stub → реальный mapper).
- `apps/backend/app/main.py:create_app()` — Plan 31-01 добавляет 4-й `register_*_resolver(...)` строку перед `app.include_router(api_router)` (точное место — после третьего register call, между «Phase 19 D-21» комментарием и `await...` if any).
- `apps/backend/app/workers/telegram_bot.py:main()` — Plan 31-01 добавляет 3-й `register_*_resolver(...)` (defensive); import добавляется в верх файла.
- `apps/backend/app/api/v1/__init__.py` (или эквивалентный chain) — `app.include_router(trainers.router, prefix='/trainers', tags=['trainers'])`. Точное место — после memberships, перед visits (alphabetic в текущем chain — planner подтверждает).
- `apps/admin-web/src/shared/api/services/mock/index.ts` — Plan 31-02 добавляет `import { trainers } from './trainers'` + `trainers` в `services` const (line 13 current).
- `apps/admin-web/src/routes/_protected/trainers.tsx` — новый route; sidebar entry уже в `registry.ts` (Plan 30-02). TanStack Router auto-codegen регенерирует `routeTree.gen.ts`.
- OpenAPI `apps/backend/openapi.json` snapshot — Plan 31-01 регенерирует (drift gate в Phase 35 финализирует с admin-web codegen).

### Phase 30 Outputs (Verified Available)
- 4 trainer audit events in `LOCKED_AUDIT_EVENTS` frozenset (51 total events).
- 4 trainer payload schemas in `AUDIT_PAYLOAD_SCHEMAS` registry with `extra='forbid'`.
- `Resource.TRAINERS` in backend permissions + `OWNER_ONLY` entries.
- `'trainers'` resource in admin-web `can.ts` + `registry.ts` (kebab-case mirror).
- `trainers/service.py` placeholder + SVC001 walker scope включает trainers.
- `.importlinter` modules-independent contract включает trainers.
- Append-only AST walker (для payments) — НЕ относится к trainers (trainers не append-only).

</code_context>

<specifics>
## Specific Ideas

- **Mirror Phase 8 (clients) module shape — simpler.** Trainers ≈ stripped-down Client (no tags, no birthday, no gender, no email, no emergency_contact, no telegram binding, no created_by_user_id FK). Same mixin composition pattern, same router shape, same audit emission discipline, same repository IntegrityError → 409 mapping.
- **`/trainers` UX ≈ `/membership-plans` UX.** Owner-only catalog page, table + create/edit dialog + status toggle + delete with FK-block error surface.
- **Defensive double-wire `register_trainer_by_id_resolver`** даже хотя bot не consumer в v1.4 — explicit user-confirmed bedrock decision per TRN-06 (REG-29-03 lesson).
- **Pre-emptive 409 `trainer_in_use` mapping** до того как `pt_sessions` table существует — exercise через monkeypatched IntegrityError test (Claude's Discretion option c). Не deferred TODO.
- **2 plans, не 3.** Backend trainers module + admin-web `/trainers` mock-mode. HTTP wiring в Phase 35 — НЕ в Phase 31.
- **`(VIEW, TRAINERS)` outside OWNER_ONLY** уже locked Plan 30-02 — reception видит trainers только для будущего PT-session picker (Phase 35 wiring); `/trainers` route сам по себе owner-only via `beforeLoad`.

</specifics>

<deferred>
## Deferred Ideas

- **HTTP-mode service `apps/admin-web/src/shared/api/services/http/trainers.ts`** + codegen-driven typing — Phase 35 (FE-10..18 OpenAPI drift gate + full admin-web wiring).
- **Trainer scheduling, shifts, payroll, commissions** — out of v1.4 entirely (см. PROJECT.md «Tech-debt carryover»). Future milestone if business needs it.
- **Trainer photo / bio / specializations** — not in TRN-* requirements. Future phase if needed.
- **Trainer_name_snapshot на PT-sessions** (B-05 bedrock decision) — landed в Phase 34 (PT-Session Recording), не здесь.
- **`POST /api/v1/trainers/{id}/deactivate` отдельный endpoint** — отвергнут (D-31-11). PATCH с `isActive: false` достаточно.
- **Owner override hard-delete (force=true)** — не в TRN-* spec. Owner всегда деактивирует. Future phase if business needs.
- **Sidebar entry для `/trainers` route в `AppShell` left nav** — registry уже содержит `'trainers'` entry; точная sidebar icon (Lucide name) + Russian label — Phase 31 Plan 02 финализирует через `t()` dictionary entry в `shared/i18n/ru.ts` (`nav.trainers = "Тренеры"`). НЕ отдельная phase.

### Reviewed Todos (not folded)
None — `gsd-sdk query todo.match-phase 31` returned 0 matches.

</deferred>

---

*Phase: 31-Trainers Module*
*Context gathered: 2026-05-14*
*Mode: --auto (single-pass; recommended defaults; no AskUserQuestion prompts)*
