# Phase 8: Clients Module + Audit Log - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Operator может list / search / filter / sort / view / create / edit / (owner-only) soft-delete клиентов через `/api/v1/clients/*`; каждая мутация (create / update / soft-delete) пишет ровно одну строку в `audit_log` атомарно с DDL-изменением. Soft-deleted phone становится свободным для нового клиента (partial unique `WHERE deleted_at IS NULL`). Phase 8 также превращает существующий `app.core.audit.emit()` из pure structlog passthrough в **structlog + DB INSERT** без изменения имён залоченных событий — `login_success`, `logout`, `otp_issued`, `otp_consumed`, `family_reuse_detected`, `session_revoked` и т.д. от Phase 5/7 начинают писать строки в `audit_log` без переписывания call-sites (только сигнатура + await).

**Phase 8 ships:**

1. **Migration `0002_clients.py`** (INFRA-04) — `CREATE EXTENSION IF NOT EXISTS pg_trgm`, создание таблиц `clients` и `audit_log`, partial unique `uq_clients_phone_alive ON clients(phone) WHERE deleted_at IS NULL`, GIN-индексы `ix_clients_last_name_trgm` / `ix_clients_first_name_trgm` (`gin_trgm_ops` на `lower(last_name)` / `lower(first_name)`).

2. **`app/modules/clients/`** — заполнение placeholder:
   - `models.py` — `Client(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin)` со всеми колонками CLIENTS-01 + `created_by_user_id ForeignKey('users.id', ondelete='RESTRICT')` (Phase 5 D-05).
   - `schemas.py` — `ClientCreateRequest` / `ClientUpdateRequest` (PATCH; `exclude_unset` semantics) / `ClientResponse` / `ClientListQuery` (`q?`, `tag?`, `gender?`, `createdFrom?`, `createdTo?`, `hasTelegram?`, `sort?`, плюс `PageQuery`-наследник).
   - `repository.py` — `list_alive` / `get_alive` / `insert_client` / `update_client` / `soft_delete_client` (CLIENTS-09) — единственный код, который видит `select(Client)`. Service-layer не трогает таблицу напрямую.
   - `service.py` — `list_clients` / `get_client` / `create_client` / `update_client` / `soft_delete_client` — orchestration: вызов repository → `await audit.emit(session, ...)` → один `session.flush()` под общим `session.begin()` транзакционным скоупом (D-03/D-04).
   - `router.py` — `GET /api/v1/clients` (`require_permission(VIEW, CLIENTS)`), `GET /api/v1/clients/{id}` (`VIEW`), `POST /api/v1/clients` (`CREATE` или `EDIT` — см. D-21), `PATCH /api/v1/clients/{id}` (`EDIT`), `DELETE /api/v1/clients/{id}` (`DELETE` → owner-only через OWNER_ONLY матрицу). CSRF dependency автоматически на mutations через Phase 6 D-09.
   - `permissions.py` — НЕ нужен; маппинг action↔resource использует уже существующие `Action.VIEW/CREATE/EDIT/DELETE` × `Resource.CLIENTS` из `app.core.permissions`.

3. **`app/core/audit_models.py` (NEW)** — `AuditLog(Base, UUIDPkMixin)` с `actor_user_id PgUUID NULL ForeignKey('users.id', ondelete='RESTRICT')`, `action TEXT NOT NULL`, `resource_type TEXT NOT NULL`, `resource_id PgUUID NULL`, `payload JSONB NOT NULL DEFAULT '{}'::jsonb`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`. Строковая FK-ссылка `'users.id'` сохраняет `core ⊥ modules` (D-05).

4. **`app/core/audit.py`** — расширение `emit()`:
   - Старая сигнатура `def emit(event, **fields)` → **`async def emit(session, event, *, actor_user_id, resource_type, resource_id=None, **payload)`** (D-04).
   - Тело: `structlog.get_logger("audit").info(event, ...)` + `session.add(AuditLog(action=event, actor_user_id=..., resource_type=..., resource_id=..., payload=payload))`. Никакого commit'а — caller владеет транзакцией (D-03).
   - Все Phase 5 и Phase 7 call-sites обновляются по 1 строке (additive: добавить `await`, передать `session` + `actor_user_id` + `resource_type` + `resource_id`). Имена `event=` НЕ меняются — Phase 5 D-21 / Phase 7 D-04/D-11/D-14/D-20 событийная сетка остаётся залоченной.

5. **Тесты** (TEST-фронт INFRA-04 + AUDIT-02):
   - `tests/integration/clients/test_clients_list.py` — `q=`, тэг-фильтр, gender-фильтр, date-range, `hasTelegram`, sort default + `last_name ASC`, pagination envelope.
   - `tests/integration/clients/test_clients_crud.py` — POST happy + 422 invalid_phone + 409 phone_exists; PATCH partial; soft-deleted phone reusable; GET 404 на soft-deleted.
   - `tests/integration/clients/test_clients_rbac.py` — DELETE owner=204 / reception=403 (OWNER_ONLY mirror).
   - `tests/integration/clients/test_audit_writes.py` — после login/logout/otp_issued/otp_consumed/client_created/client_updated/client_soft_deleted/family_reuse_detected проверяет ровно одну строку `audit_log` с правильными `action`/`actor_user_id`/`resource_type`/`resource_id`/`payload` ключами.
   - `tests/integration/auth/test_audit_existing_events.py` — поправляет/расширяет существующие auth-тесты: они теперь проверяют DB-row + structlog (не только structlog).

**In scope (Phase 8 REQ-IDs):** INFRA-04, CLIENTS-01..09, AUDIT-01..03.

**Out of scope (deferred):**
- `GET /api/v1/audit-log` endpoint + UI (AUDIT-V12-01/02 — v1.2). Phase 8 пишет в таблицу, но никто её не читает по HTTP.
- Photo upload, bulk CSV import, "last visit" filter, tags taxonomy CRUD (CLIENTS-V12-01..04 — v1.2).
- Null-out optional полей через PATCH (`email = null`) — D-01 откладывает в v1.2 (DELETE /clients/{id}/email или sentinel-based PATCH). Phase 8: PATCH = "что прислал — то и обновили", null-в-JSON отвергается.
- Admin-web UI (Phase 10 — FE-01..07).
- OpenAPI export (Phase 9 — API-01/02 + codegen).
- Rate limit на `/clients` (premature; 1-2 операторов).

</domain>

<decisions>
## Implementation Decisions

### PATCH semantics

- **D-01 [LOCKED]:** **PATCH = `model_dump(exclude_unset=True)`; null-out не поддерживается в v1.1.** `ClientUpdateRequest` объявляет каждое опциональное поле как `Optional[T] = None` где `None` означает "не передано", НЕ "очистить". Pydantic-валидация явно запрещает `null` в JSON для опциональных полей через `model_validator(mode="before")` (если ключ присутствует со значением `None` → 422 `invalid_field`). Если в будущем понадобится "очистить email" — DELETE-as-null endpoint или sentinel `Unset` ложится в v1.2 (см. Deferred).

### Repository / service split

- **D-02 [LOCKED]:** **`repository.py` + `service.py` split.** Весь SQL для clients (`select(Client)`, `insert/update/soft_delete`, `list_alive`, `get_alive`) живёт в `app/modules/clients/repository.py` — функции принимают `AsyncSession`, возвращают ORM rows. `service.py` — бизнес-логика: phone-валидация, обработка `IntegrityError` partial-unique, audit emit, координация транзакции. CLIENTS-09 ("все query через `list_alive`/`get_alive`") выполняется конструктивно: service-слой даже не имеет import `Client` модели для прямых SELECT'ов (планнер может предусмотреть `from .models import Client` только в repository.py). lint-rule "forbid `select(Client)` outside repository.py" — backlog для v1.2.

### Audit emission

- **D-03 [LOCKED]:** **audit.emit вызывается внутри той же транзакции, что и мутация.** Service-функция открывает `async with session.begin():` (или naïve session, который коммитится в конце router-хэндлера через FastAPI dependency) — внутри: `await repository.insert_client(...)` → `await audit.emit(session, ...)` → `session.flush()`. Один commit = `clients` INSERT + `audit_log` INSERT либо оба happen, либо оба откатываются. Сохраняет инвариант AUDIT-02 "успешная мутация ⇔ ровно одна строка в audit_log" без race condition.

- **D-04 [LOCKED]:** **`audit.emit` сигнатура расширяется аддитивно (async, явные FK-поля).**
  Новая сигнатура: `async def emit(session: AsyncSession, event: str, *, actor_user_id: UUID | None, resource_type: str, resource_id: UUID | None = None, **payload: Any) -> None`.
  Тело: `structlog.get_logger("audit").info(event, **payload)` (как сейчас) + `session.add(AuditLog(action=event, actor_user_id=..., resource_type=..., resource_id=..., payload=payload))`. **Никакого `await session.commit()`** — caller владеет транзакцией.
  **Phase 5/7 call-sites обновляются построчно** (Phase 5 D-21 заранее задокументировал "Phase 8 меняет тело без переименования event="):
    | Event | actor_user_id | resource_type | resource_id |
    |---|---|---|---|
    | `login_success` | user.id | `'session'` | session_family_id |
    | `login_failed` | NULL | `'login_attempt'` | NULL (email в payload) |
    | `session_revoked` | user.id | `'session'` | family_id |
    | `session_revoked_all` | user.id | `'user'` | user.id |
    | `family_reuse_detected` | user.id | `'session'` | family_id |
    | `password_changed_revokes_sessions` | user.id | `'user'` | user.id |
    | `telegram_deep_link_issued` | NULL | `'otp'` | NULL (deep_link_token_hash в payload) |
    | `otp_issued` | user.id | `'otp'` | NULL |
    | `otp_consumed` | user.id | `'otp'` | NULL |
    | `telegram_unknown_start` | NULL | `'otp'` | NULL |
    | `telegram_dm_blocked` | NULL | `'otp'` | NULL (chat_id в payload) |
    | `telegram_dm_failed` | NULL | `'otp'` | NULL |
    | `telegram_replay_attempt` | NULL | `'otp'` | NULL |
    | `client_created` | actor.id | `'client'` | client.id |
    | `client_updated` | actor.id | `'client'` | client.id |
    | `client_soft_deleted` | actor.id | `'client'` | client.id |

### Audit log schema location

- **D-05 [LOCKED]:** **`AuditLog` ORM живёт в `app/core/audit_models.py`.** audit — cross-cutting infrastructure, не доменный модуль. FK на users объявляется через **строковую** ссылку `ForeignKey('users.id', ondelete='RESTRICT')` — SQLAlchemy не требует import; `import-linter` `core-not-depend-on-modules` остаётся GREEN. clients.models импортирует AuditLog тоже не нужно (Client → user через `created_by_user_id`, который и так строковая FK). Файл `audit_models.py` отделён от `audit.py` чтобы не плодить циклическую зависимость с `Base` (Base импортируется в `audit.py`'s INSERT path).

- **D-06 [LOCKED]:** **`audit_log.actor_user_id` NULLABLE.** Безактор-события (`login_failed`, `telegram_deep_link_issued`, `telegram_unknown_start`, `telegram_dm_blocked`, `telegram_dm_failed`, `telegram_replay_attempt`) пишут `actor_user_id = NULL`. ON DELETE RESTRICT на FK работает и для nullable. NOT NULL + sentinel system-user отвергнуто (фейковая строка в users путает RBAC и seed). Drop-the-event подход отвергнут (теряем след по неудачным попыткам входа).

### resource_id type & non-UUID identifiers (Discretion — recommended)

- **D-07 (Discretion):** **`audit_log.resource_id` — `PgUUID NULL`.** Большинство ресурсов в проекте — UUIDv4 (clients.id, users.id, refresh_tokens.id, otp_codes.id, family_id). Для событий с не-UUID идентификатором (telegram chat_id BIGINT, OTP hash 64-char) `resource_id IS NULL`, идентификатор живёт в `payload` под explicit ключом (`payload.chat_id`, `payload.deep_link_token_hash`). Альтернатива (`resource_id TEXT`) усложнила бы индексацию для будущего `GET /audit-log?resource_id=<uuid>` (v1.2) — UUID-колонка с btree-индексом точечно дешевле.

### Audit payload shape (Discretion — recommended)

- **D-08 (Discretion):** **payload — JSONB с per-event фиксированной структурой; client-mutations несут diff, не full state.**
  - `client_created`: `{full_name, phone, has_email, has_telegram}` — минимальное необходимое для аудита, БЕЗ ПД-чувствительных колонок (notes / emergency_contact / birthday). Полный snapshot достаётся из `clients` через `resource_id` + `created_at`.
  - `client_updated`: `{changed_fields: ['phone', 'gender'], previous_phone?: '+7...'}` — список изменённых ключей; для phone дополнительно `previous_phone` (помогает реконструировать историю при partial-unique споре). НЕ value-pairs full diff — экономия места, AUDIT-V12-01 (read UI) при необходимости делает `pg_temporal`-style join.
  - `client_soft_deleted`: `{phone, full_name}` — нужно чтобы понять "кого удалили" без JOIN (audit-log read endpoint v1.2 будет читать только audit_log).
  - `login_success`: `{email, channel, ip?, user_agent?}` (как Phase 5 D-20).
  - `login_failed`: `{email, reason, ip?}`.
  - Прочие auth/telegram события — payload = текущий kwargs из call-site (без structural диффинга).

- **D-09 (Discretion):** **No-op PATCH (нет реально изменённых полей после `exclude_unset`) → НЕ эмитим `client_updated`.** `service.update_client` сравнивает `model_dump(exclude_unset=True)` с текущим состоянием; если все поля совпадают → `await audit.emit` не вызывается, `session` ничего не пишет (только `updated_at = now()` обновляется через `onupdate=func.now()`, но даже это можно подавить, не передавая колонки в UPDATE — планнер решит). Идемпотентность PATCH'а — стандарт; шумный no-op в audit_log хуже, чем его отсутствие.

### Phone validation & error model (Discretion — recommended)

- **D-10 (Discretion):** **Phone — строгий E.164 regex `^\+[1-9]\d{1,14}$`, без нормализации.** Service отвергает любой нестандартный формат (пробелы, скобки, дефисы) → 422 `DomainError { code: 'invalid_phone' }`. Frontend (Phase 10) отвечает за normalize→display маски `+7 (XXX) XXX-XX-XX`; backend хранит и принимает только canonical E.164. Это перекладывает UX-mile на FE, но устраняет двусмысленность "какой формат каноничен в БД" и упрощает ILIKE-search.

- **D-11 (Discretion):** **IntegrityError на partial-unique (`uq_clients_phone_alive`) → service ловит и поднимает `DomainError { code: 'phone_exists' }` 409.** В `service.create_client` / `service.update_client` обёрнуто try/except `IntegrityError` с проверкой `e.orig.constraint_name == 'uq_clients_phone_alive'` (или просто текстовое match — планнер выберет). Любая другая `IntegrityError` пробрасывается в Phase 2 `_app_error_handler` как `internal_error` 500.

### Search / filter / sort semantics (Discretion — recommended)

- **D-12 (Discretion):** **`q=` ILIKE по объединённому выражению FIO + phone.**
  - Если `len(q.strip()) < 2` → ignore (не применяем фильтр).
  - WHERE: `lower(last_name || ' ' || first_name || ' ' || coalesce(middle_name, '')) ILIKE '%' || lower(:q) || '%' OR phone ILIKE '%' || :q || '%'`.
  - pg_trgm GIN-индексы (`ix_clients_last_name_trgm`, `ix_clients_first_name_trgm`) ускоряют trigram similarity-варианты, но текущий запрос — простой ILIKE; планнер решает, добавлять ли `pg_trgm` similarity-сравнение (`% оператор`) в Phase 8 или оставить чистый ILIKE до v1.2 (нужен ли — зависит от объёма; для 1-2 операторов ILIKE на 1k-10k строк seq scan приемлем).
  - Phone в q — точечный `phone ILIKE '%q%'` без trigram (E.164 короткие, btree уникальный индекс уже есть).

- **D-13 (Discretion):** **Tag-фильтр — `?tag=X` exact match через `:'X' = ANY(tags)`.** Один тэг за раз; multi-tag (AND/OR над массивом) — out of scope (CLIENTS-V12-04 v1.2). Тэги хранятся lowercased (D-15).

- **D-14 (Discretion):** **`createdFrom` / `createdTo` — inclusive ISO дата или datetime; принимаются Pydantic `datetime` с UTC-нормализацией.** WHERE: `created_at >= createdFrom AND created_at <= createdTo`. Если приходит date-only (без времени) → backend парсит как `00:00:00 UTC` (от) и `23:59:59.999999 UTC` (до) на boundary — конвертация в Pydantic-валидаторе. **`hasTelegram=true` → `telegram_user_id IS NOT NULL`; `hasTelegram=false` → `telegram_user_id IS NULL`.** **Sort: только два варианта по CLIENTS-04** — `created_at DESC` (default) либо `last_name ASC`. Direction-toggling и другие колонки — out of scope.

### Field validation (Discretion — recommended)

- **D-15 (Discretion):** **`gender` — TEXT + CHECK constraint `gender IN ('male', 'female')`** (паттерн Phase 5 D-07 для `role`). SQLAlchemy: `Mapped[Gender | None] = mapped_column(SAEnum(Gender, native_enum=False, length=16, ...))`. `Gender(StrEnum)` живёт в `app/modules/clients/models.py` (или `schemas.py`). Расширение enum'а в v1.2 (non-binary, prefer-not-to-say) — миграция CHECK constraint'а, не PG enum-альтер.

- **D-16 (Discretion):** **`tags TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[]`** + service-layer валидация:
  - каждый тег lowercased + `.strip()` на write;
  - `len(tag) <= 32` per tag;
  - `len(tags) <= 16` per client;
  - regex `^[a-z0-9а-я\-_]+$` (no whitespace, no спецсимволы);
  - Валидация в Pydantic `field_validator('tags')` в `ClientCreateRequest` / `ClientUpdateRequest`.
  - DB-level CHECK не добавляется (валидация на app-слое достаточна для гимовой шкалы).

- **D-17 (Discretion):** **`emergency_contact JSONB NULL`** хранится с Pydantic-структурой:
  ```python
  class EmergencyContact(ContractModel):
      name: str = Field(min_length=1, max_length=128)
      phone: str = Field(pattern=r'^\+[1-9]\d{1,14}$')  # E.164, как у Client.phone
      relation: str | None = Field(default=None, max_length=64)
  ```
  Service сериализует через `.model_dump()` перед `session.add(Client(...))`. На read — Pydantic парсит обратно из jsonb (`from_attributes=True` на `ContractModel`).

### Service / router shape (Discretion — recommended)

- **D-18 (Discretion):** **Module-level functions в `service.py` и `repository.py`, НЕ классы.** Соответствует Phase 5 D-15 / Phase 7 D-05 (telegram_service.py — module-level functions). Тестируемость через monkey-patch модуля; class-based DI не нужен в gym scale.

- **D-19 (Discretion):** **Service принимает `AsyncSession`, `actor: User`, и DTO-входы; возвращает ORM `Client` либо `PaginatedData`.** Router-handler декларирует `Depends(get_current_user)` (Phase 4 D-23 / Phase 6 D-02) → передаёт `current_user` в service вторым аргументом. Service использует `current_user.id` для `Client.created_by_user_id` (на create) и для `audit.emit(actor_user_id=current_user.id, ...)`.

### Migration shape (Discretion — recommended)

- **D-20 (Discretion):** **Один файл `0002_clients.py` создаёт обе таблицы + extension.** Порядок: `op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')` → `op.create_table('clients', ...)` → partial unique index → GIN trigram indices → `op.create_table('audit_log', ...)` → btree on `(actor_user_id, created_at DESC)` для будущего `GET /audit-log?actor=...&before=...` (AUDIT-V12-01). Downgrade: drop в обратном порядке + `DROP EXTENSION IF EXISTS pg_trgm`. TEST-08 (`alembic check` clean diff) подтверждает.

### Action mapping for routes (Discretion — recommended)

- **D-21 (Discretion):** **Route → permission mapping:**
  | Route | action | resource | OWNER_ONLY? |
  |---|---|---|---|
  | `GET /clients` | `VIEW` | `CLIENTS` | no |
  | `GET /clients/{id}` | `VIEW` | `CLIENTS` | no |
  | `POST /clients` | `EDIT` | `CLIENTS` | no |
  | `PATCH /clients/{id}` | `EDIT` | `CLIENTS` | no |
  | `DELETE /clients/{id}` | `DELETE` | `CLIENTS` | **yes** (RBAC-05 / can.ts mirror) |

  Используется только `EDIT` для create+update — `Action.CREATE` существует в enum, но `OWNER_ONLY` матрица не содержит `(CREATE, CLIENTS)`, и frontend `can.ts` тоже одинаково разрешает create/edit reception'у. Если позже окажется, что reception не должен создавать — добавление `(CREATE, CLIENTS)` в OWNER_ONLY одной строкой в обоих языках (parity test ловит). Альтернатива (использовать `CREATE` для POST) тоже валидна — планнер может выбрать любую; главное, чтобы было консистентно с frontend. **Recommended: `EDIT` для POST + PATCH** (паритет с тем, как admin-web обычно тестировал бы reception на "может ли он создавать клиентов" → да, может).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project specs
- `CLAUDE.md` — backend stack lock (Python 3.12 + uv + FastAPI + SQLAlchemy 2.0 async + Pydantic v2 + Postgres 16 + Redis 7 + structlog), `httpx ASGITransport` + `pytest-asyncio` testing rule, RU-locale strings, `pg_trgm` ban отсутствует — Phase 8 включает.
- `apps/admin-web/CLAUDE.md` — frontend reference (Phase 10 будет потреблять `/clients/*`); Phase 8 НЕ трогает FE; mock-сервисы остаются как есть.
- `.planning/PROJECT.md` — milestone scope; `core ⊥ modules` invariant; "тэги/notes/emergency_contact jsonb cover v1.1" из Out of Scope; "soft-delete only".
- `.planning/REQUIREMENTS.md` — Phase 8 owns: `INFRA-04`, `CLIENTS-01..09`, `AUDIT-01..03`. Каждая plan-task должна трассироваться на REQ-ID.
- `.planning/ROADMAP.md` Phase 8 section — goal + 4 success criteria (list/search/filter shape; soft-delete + E.164 + owner-only delete; partial-unique-on-phone-alive ⇒ phone reuse; audit_log row per mutation, no GET endpoint).

### Cross-phase context (load-bearing)
- `.planning/phases/04-auth-foundations-cookie-rbac-primitives/04-CONTEXT.md` — D-15..D-19 (UUIDPkMixin / TimestampMixin / SoftDeleteMixin); D-17 (`SoftDeleteMixin` partial-index pattern — Phase 8 партишь по этому контракту); D-10/D-11 (PageQuery + PaginatedData[T]); D-13 (ResponseEnvelope[T]); `core ⊥ modules` контракт.
- `.planning/phases/05-user-schema-email-password-auth/05-CONTEXT.md` — D-05 (User БЕЗ SoftDeleteMixin; FK `clients.created_by_user_id ON DELETE RESTRICT`); D-06 (User columns); D-15 (module-level functions в service.py); D-20 (locked event names); D-21 (Phase 8 swap-in без переименования event=); D-22 (SAVEPOINT db_session фикстура для Phase 8 тестов).
- `.planning/phases/06-rbac-wiring-parity-tests/06-CONTEXT.md` — D-01/D-02/D-04 (`require_permission` на router-уровне; `verify_csrf` на mutations; TEST-07 introspection enforcement); D-09 (CSRF exempt list — clients все четыре mutation routes требуют CSRF, НЕ исключения). RBAC-05 (DELETE clients owner-only) и parity test поймает дрейф.
- `.planning/phases/07-telegram-otp-channel/07-CONTEXT.md` — D-04/D-11/D-14/D-20 (locked telegram event names — Phase 8 переводит их на DB writes без переименования); D-08 (`db_lifespan_manager` — Phase 8 не меняет, только использует через FastAPI dependency).

### Source files Phase 8 directly reads or mutates
- `apps/backend/alembic/versions/0002_clients.py` — NEW (INFRA-04, D-20).
- `apps/backend/app/modules/clients/__init__.py` — обновить docstring placeholder.
- `apps/backend/app/modules/clients/models.py` — NEW. Client + Gender(StrEnum) + EmergencyContactJSON shape.
- `apps/backend/app/modules/clients/schemas.py` — NEW. ClientCreateRequest / ClientUpdateRequest / ClientResponse / ClientListQuery / EmergencyContact (D-01, D-15, D-16, D-17).
- `apps/backend/app/modules/clients/repository.py` — NEW (D-02). list_alive / get_alive / insert_client / update_client / soft_delete_client.
- `apps/backend/app/modules/clients/service.py` — NEW (D-03, D-09, D-10, D-11, D-19). Module-level async functions.
- `apps/backend/app/modules/clients/router.py` — NEW (D-21). 5 endpoints + ResponseEnvelope[X].
- `apps/backend/app/main.py` — добавить `app.include_router(clients.router, prefix="/api/v1/clients", tags=["clients"])`.
- `apps/backend/app/core/audit_models.py` — NEW (D-05, D-06, D-07). AuditLog ORM.
- `apps/backend/app/core/audit.py` — расширить `emit()` сигнатуру (D-04). Сохранить структурные docstring-таблицы event-names.
- `apps/backend/app/modules/auth/service.py` — обновить call-sites `audit.emit(...)` для login_success / family_reuse_detected / session_revoked / session_revoked_all (D-04 mapping).
- `apps/backend/app/modules/auth/router.py` — обновить call-sites в /logout / /logout-all (D-04 mapping); login_failed эмиссия с actor_user_id=NULL.
- `apps/backend/app/modules/auth/telegram_service.py` — обновить call-sites для telegram_deep_link_issued / otp_issued / otp_consumed / telegram_replay_attempt (D-04 mapping).
- `apps/backend/app/integrations/telegram/handlers.py` — обновить call-sites для telegram_unknown_start / telegram_dm_blocked / telegram_dm_failed (D-04 mapping). NB: handler уже имеет `db_session` через HandlerContext (Phase 7 D-05) — `await audit.emit(session, ...)` ложится естественно.
- `apps/backend/tests/integration/clients/__init__.py` — NEW. Empty.
- `apps/backend/tests/integration/clients/test_clients_list.py` — NEW.
- `apps/backend/tests/integration/clients/test_clients_crud.py` — NEW.
- `apps/backend/tests/integration/clients/test_clients_rbac.py` — NEW.
- `apps/backend/tests/integration/clients/test_audit_writes.py` — NEW.
- `apps/backend/tests/integration/auth/test_login.py` / `test_logout.py` / `test_refresh.py` — расширить assertions: проверить, что после события появляется строка в `audit_log` с правильными action/actor_user_id/resource_type/resource_id/payload (или эти ассерты сосредоточены в `test_audit_writes.py` через парам/factory — планнер решает).
- `apps/backend/tests/integration/auth/test_telegram_*.py` — то же расширение для telegram_*-событий.

### External docs (consulted)
- PostgreSQL `pg_trgm` extension docs — GIN-индексы с `gin_trgm_ops` на выражении `lower(column)` для accent-insensitive ILIKE; `CREATE EXTENSION IF NOT EXISTS pg_trgm` в migration.
- SQLAlchemy 2.0 async docs — `ARRAY(Text)` mapping для `tags`; `JSONB` через `sqlalchemy.dialects.postgresql.JSONB`; `AsyncSession.add` + `flush` без commit для co-transactional INSERT'ов; `Index(..., postgresql_using='gin', postgresql_ops={'col': 'gin_trgm_ops'})` для trgm GIN.
- Pydantic v2 docs — `model_validator(mode='before')` для запрета null-в-JSON на опциональные поля (D-01); `field_validator` для tags + emergency_contact + phone (D-16, D-17, D-10).
- Alembic async migration cookbook — `op.execute()` для `CREATE EXTENSION`; partial unique index через `op.create_index(..., postgresql_where=text(...))`.
- E.164 spec (ITU-T E.164) — `^\+[1-9]\d{1,14}$` (1-15 digits после `+`, первая ≠ 0).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (Phase 4/5/6/7 outputs Phase 8 consumes verbatim)
- `app/core/database.py:Base` + `UUIDPkMixin` + `TimestampMixin` + `SoftDeleteMixin` (Phase 4 D-15..D-17) — `Client` композирует все четыре; `AuditLog` — только UUIDPkMixin (без timestamps mixin'а — `created_at` руками с `server_default=now()`, без `updated_at`).
- `app/core/database.py:db_lifespan_manager` (Phase 7 D-08) — Phase 8 не меняет; FastAPI dependency `get_session` (Phase 4 D-23 эквивалент или Phase 5) уже даёт AsyncSession под одной транзакцией.
- `app/core/pagination.py:PageQuery` / `PaginatedData[T]` (Phase 4 D-10) — `ClientListQuery` наследует `PageQuery`; список endpoint возвращает `ResponseEnvelope[PaginatedData[ClientResponse]]`.
- `app/core/schemas.py:ContractModel` / `RequestContract` / `ResponseData` / `ResponseEnvelope` (Phase 4 D-09..D-13) — все Phase 8 DTO наследуют; camelCase wire / snake_case Python приходит автоматически.
- `app/core/exceptions.py:AppError` + `_app_error_handler` (Phase 2 D-12) — Phase 8 `DomainError`-подклассы (`InvalidPhone`, `PhoneExists`, `ClientNotFound`) extend это.
- `app/core/permissions.py:Action` / `Resource` / `OWNER_ONLY` / `can` (Phase 4 D-04 / RBAC-01) — Phase 8 router использует `Action.VIEW/EDIT/DELETE` × `Resource.CLIENTS` без новых enum-значений.
- `app/core/dependencies.py:get_current_user` + `require_permission` + `require_authenticated` + `verify_csrf` (Phase 4 D-23, Phase 6 D-01..D-02) — каждый endpoint декларирует один `require_permission(...)` + наследованный CSRF от Phase 6.
- `app/core/audit.py:emit` (Phase 5 D-21) — Phase 8 расширяет тело без переименования call-sites (D-04). Locked event-names docstring обновляется: добавляются `client_created` / `client_updated` / `client_soft_deleted`.
- `app/modules/auth/models.py:User` (Phase 5 D-06) — Phase 8 на него FK через `clients.created_by_user_id` и `audit_log.actor_user_id` (обе RESTRICT).
- `tests/conftest.py:db_session` (Phase 5 D-22 SAVEPOINT) — переиспользуется во всех clients/auth-аудит-тестах.
- `tests/conftest.py:authed_client_owner` / `authed_client_reception` (Phase 5/6 фикстуры) — RBAC-тесты для clients.

### Established patterns to honor
- **Module-level functions, не классы** (Phase 5 D-15, Phase 7 D-05) — `service.py` / `repository.py` экспортирует чистые `async def`-функции.
- **`select(Client)` ТОЛЬКО в repository.py** (D-02 + CLIENTS-09) — service-слой не имеет доступа к ORM-таблице напрямую.
- **`AppError` → JSONResponse handler** (Phase 2 D-12) — `InvalidPhone` / `PhoneExists` / `ClientNotFound` ездят по этому пути; OpenAPI `responses={4xx: ProblemDetails}` декларируется на роуте.
- **camelCase wire / snake_case Python** (Phase 4 D-09) — все DTO inherit из `ContractModel`; `created_from` Python ↔ `createdFrom` wire automatic.
- **`require_permission` НА route-сигнатуре, никогда внутри service** (RBAC-03 / Phase 6 D-03) — service вообще не знает про Role.
- **Pagination envelope `{items, total, page, pageSize}`** (Phase 4 D-10) — никогда bare arrays.
- **Russian-narrative + English-code** (Phase 3 D-05) — PLAN.md / SUMMARY.md narrative по-русски, код — английский.
- **SAVEPOINT-rolled db_session** (Phase 5 D-22) — clients-тесты создают User+Client внутри откатываемой транзакции.
- **Partial unique index через `__table_args__`** (Phase 4 D-17 mixin contract) — `Client.__table_args__` включает `Index('uq_clients_phone_alive', 'phone', unique=True, postgresql_where=text('deleted_at IS NULL'))`.

### Integration points
- **Phase 5 (shipped) — `audit.emit` call-sites обновляются построчно** (D-04 mapping table). Тесты `test_login.py` / `test_logout.py` / `test_refresh.py` расширяются проверками DB-row (раньше — только structlog).
- **Phase 6 (shipped) — `require_permission` + `verify_csrf` уже работают; clients router просто декларирует.** TEST-07 (route-introspection) автоматически проверяет, что все 5 clients endpoints имеют `require_permission`. TEST-06 (parity) ловит, если `OWNER_ONLY` дрейфует от can.ts.
- **Phase 7 (shipped) — `audit.emit` call-sites в `telegram_service.py` + `integrations/telegram/handlers.py` обновляются.** `HandlerContext.session_factory` Phase 7 D-05 уже передаёт session — `await audit.emit(session, ...)` ложится естественно.
- **Phase 9 (forthcoming) — Pydantic-схемы Phase 8 автоматически попадут в openapi.json через FastAPI introspection.** `ClientResponse` / `ClientCreateRequest` / `ClientUpdateRequest` / `ClientListQuery` — все наследуются от ContractModel, alias_generator работает out-of-box; `ProblemDetails` уже зарегистрирован.
- **Phase 10 (forthcoming) — admin-web FE-01..04 будет потреблять /clients/* через packages/api-client.** Phase 8 — единственный owner контракта; никаких изменений из FE-стороны не приходит (admin-web сейчас mock-only).

</code_context>

<specifics>
## Specific Ideas

- **`AuditLog` лежит в `app/core/audit_models.py`, а не в `app/modules/auth/models.py`.** audit — cross-cutting infrastructure (его пишут все модули, не только auth). Размещение в core + строковая FK `'users.id'` сохраняет `core ⊥ modules` import-linter контракт (D-05).

- **`audit.emit` — async, принимает `session` явно.** Никаких ContextVar-magic. Caller владеет транзакцией, audit просто `session.add(...)`. Альтернативные паттерны (post-commit hooks, BackgroundTask) явно отвергнуты — нарушают AUDIT-02 invariant "ровно одна строка на успешное событие" (D-03).

- **payload — НЕ full state на update, а changed_fields list + old phone snapshot для phone-conflict восстановления** (D-08). Всё, что нужно для будущего read-UI (v1.2), реконструируется через JOIN clients+audit_log по resource_id + созданию before-image из последовательных `client_updated` событий.

- **PATCH с null-в-JSON отвергается Pydantic-валидатором** (D-01). Нельзя послать `{"email": null}` чтобы стереть email — это будет 422. Очистка через DELETE-as-null-эндпоинты — feature v1.2.

- **`q=` имеет минимальную длину 2** (D-12). Однобуквенные запросы = no-op (возвращает unfiltered list). Защищает от случайных полных пробежек по таблице с `WHERE col ILIKE '%a%'`.

- **`gender` — `('male', 'female')` строго через CHECK constraint** (D-15). Расширение enum'а в v1.2 — миграция CHECK'а, не PG enum-альтер. (Паттерн Phase 5 D-07 для `role` — тот же.)

- **Phone — strict E.164 без backend-нормализации** (D-10). `+79991234567` — единственный canonical вид. UX-маски — забота FE (Phase 10).

- **Soft-delete + partial unique = свобода переиспользовать phone.** Это литеральная success criteria #3 Phase 8 — она работает за счёт `uq_clients_phone_alive ... WHERE deleted_at IS NULL` (Phase 4 D-17 mixin contract).

- **DELETE owner-only — наследуется через `require_permission(DELETE, CLIENTS)`** + frozen `OWNER_ONLY` matrix (Phase 4 D-04). `(DELETE, CLIENTS)` уже в наборе (RBAC-05). Никакого дополнительного код-чека `if role != owner` не нужно.

- **No `GET /audit-log` endpoint в v1.1.** Таблица существует, пишется, но HTTP-чтения нет (AUDIT-03). Это специально — чтобы не платить за доступ-контроль и pagination read-side в v1.1.

</specifics>

<deferred>
## Deferred Ideas

- **Null-out optional полей через PATCH** (`{"email": null}` → set NULL) — v1.2. Текущий контракт D-01 — `exclude_unset` only. Возможные подходы в v1.2: (a) DELETE /clients/{id}/email подэндпоинт, (b) Pydantic sentinel `Unset` + custom serializer.

- **lint-rule "forbid `select(Client)` outside `repository.py`"** — backlog v1.2. Сейчас CLIENTS-09 выполняется конвенционально (service.py не импортирует Client model). Lint можно добавить через `import-linter` `forbidden_imports` или ruff custom rule.

- **`GET /api/v1/audit-log`** + read-UI — v1.2 (AUDIT-V12-01/02). Phase 8 готовит таблицу: `(actor_user_id, created_at DESC)` btree index, payload jsonb с per-event фиксированной структурой (D-08).

- **Audit log full diff (value-pairs old↔new)** — пока пишем только `changed_fields: ['phone', 'gender']` + `previous_phone`. Полный diff — v1.2 если read-UI потребует.

- **No-op PATCH эмиссия** — D-09 пропускает; если в v1.2 продукт-команда захочет видеть "ничего не изменили, но подтвердили клиента" — добавить отдельное событие `client_touched`.

- **Multi-tag фильтр (AND/OR семантика)** — v1.2 (CLIENTS-V12-04 tags taxonomy management). `?tag=X` exact-only в Phase 8 (D-13).

- **pg_trgm similarity (% оператор) для fuzzy ФИО** — Phase 8 ставит GIN-индексы (CLIENTS-03 требует), но запрос ILIKE — простой substring. Переход на `WHERE last_name % :q` — v1.2 если ILIKE покажет seq scan на реальном объёме.

- **Direction-toggling sort + другие колонки (`phone ASC`, `birthday DESC`)** — out of scope (CLIENTS-04 фиксирует только два варианта).

- **`tag CRUD endpoint`** + tags taxonomy — v1.2 (CLIENTS-V12-04). Phase 8: tags — свободный массив text'ов.

- **Photo upload + storage** — v1.2 (CLIENTS-V12-01).

- **Bulk CSV import** — v1.2 (CLIENTS-V12-02).

- **"Last visit" filter** — depends on visits module, отдельный milestone после v1.1 (CLIENTS-V12-03).

- **Partial-unique conflict resolution UI** — Phase 10 (FE) сделает frontend-обработку 409 phone_exists. Backend — только структурированный ответ (D-11).

- **System actor в `audit_log`** — D-06 отвергнут в пользу `actor_user_id NULL`. Если v1.2 потребует "невозможный NULL", — миграция NOT NULL + INSERT системной строки в `users` + backfill historic NULL → system_user.id.

- **Per-IP / per-actor rate limit на `/clients`** — v1.2; 1-2 операторов делает rate limit преждевременным.

- **`emergency_contact` нормализация / международные форматы phone в emergency_contact** — D-17 принимает E.164; если в v1.2 потребуется domestic-format — расширить regex.

- **Audit-log retention policy** (TTL / archival) — v1.2+. Phase 8 пишет навсегда; для гимовой шкалы 1k-10k клиентов × ~10 событий/мес. = ~10MB/год — приемлемо без retention.

</deferred>

---

*Phase: 08-clients-module-audit-log*
*Context gathered: 2026-05-03*
