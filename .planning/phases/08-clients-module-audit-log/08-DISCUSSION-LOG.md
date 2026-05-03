# Phase 8: Clients Module + Audit Log - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-03
**Phase:** 08-clients-module-audit-log
**Areas discussed:** PATCH + repository/service shape (audit emit + AuditLog ORM location + nullability)

---

## Gray Areas Initially Presented

| Option | Description | Selected |
|--------|-------------|----------|
| Audit log: запись + payload | Транзакционная vs best-effort; payload shape; resource_id для не-UUID событий | |
| Search & filters: семантика q/тегов/дат | q= по каким колонкам; pg_trgm покрытие phone; tag-фильтр; date inclusivity | |
| Validation & error model | Phone E.164; gender storage; tags constraints; коды ошибок duplicate/invalid | |
| PATCH + repository/service shape | Partial PATCH null-out; repository.py vs service.py; audit emit location | ✓ |

**User's choice:** PATCH + repository/service shape (single area). Остальные три помечены для recommended-defaults в Claude's Discretion.

---

## PATCH semantics (null-out)

| Option | Description | Selected |
|--------|-------------|----------|
| exclude_unset — нельзя null-out (Recommended) | PATCH = "что передал — то и обновили". null в JSON отвергается Pydantic-валидацией. Очистка поля откладывается в v1.2. Контракт никогда не расходится. | ✓ |
| Sentinel Unset для явного null | Optional[T] \| UnsetType: missing/null/value — три состояния. Гибко, но усложняет схемы и OpenAPI codegen в Phase 9. | |
| DELETE-as-null подэндпоинты | Отдельные DELETE /clients/{id}/email и т.п. Зря плодит routes для v1.1, явно в спеце. | |

**User's choice:** exclude_unset — нельзя null-out (Recommended).
**Notes:** Зафиксировано как D-01 LOCKED. Null-out → v1.2 Deferred.

---

## Repository / service split

| Option | Description | Selected |
|--------|-------------|----------|
| repository.py + service.py (Recommended) | Чистые SQL-функции в repository.py принимают AsyncSession. service.py — бизнес-логика + audit. CLIENTS-09 выполняется конструктивно. lint-rule на v1.2. | ✓ |
| Всё в service.py | Phase 5/7 паттерн (однородность). Но в clients alive-фильтр везде — риск забыть фильтр в новом методе. | |
| Repository в виде класса ClientsRepo | Класс с self.session. DI-хуки, но в проекте везде module-level functions (Phase 5 D-15). Неоднородность. | |

**User's choice:** repository.py + service.py (Recommended).
**Notes:** Зафиксировано как D-02 LOCKED.

---

## Audit emission timing

| Option | Description | Selected |
|--------|-------------|----------|
| В service.py в той же транзакции (Recommended) | Атомарно: clients INSERT и audit_log INSERT либо оба happen, либо оба rollback. Сохраняет AUDIT-02 invariant. Требует расширения сигнатуры audit.emit(). | ✓ |
| В router после вызова сервиса | Router вызывает service → он коммитит → router эмитит audit. Неатомарно: если audit DB INSERT упадёт после commit клиента — событие потеряно. | |
| Best-effort post-commit хук | session.after_commit или BackgroundTask. Жертвует атомарностью ради простоты. Переосмысливает "одна строка в успехе". | |

**User's choice:** В service.py в той же транзакции (Recommended).
**Notes:** Зафиксировано как D-03 LOCKED.

---

## audit.emit signature update

| Option | Description | Selected |
|--------|-------------|----------|
| async emit(session, event, *, actor_user_id, resource_type, resource_id, **payload) (Recommended) | Async + явные FK-колонки + остальные kwargs → payload jsonb. Все Phase 5/7 call-sites обновляются по 1 строке. Phase 5 D-21 заранее договорился об этом. | ✓ |
| ContextVar с session | Sync emit; session из contextvar (разворачивается в db_session dependency). Не ломает call-sites, но скрывает сайд-эффект. Сложно тестировать без живой БД. | |
| Две функции (emit_log + emit_db) | Гибко, но "два хелпера" создаёт риск выбрать не тот в новом коде. | |

**User's choice:** async emit(session, event, *, actor_user_id, resource_type, resource_id, **payload) (Recommended).
**Notes:** Зафиксировано как D-04 LOCKED. Mapping table за 14 событий (login_*, session_*, telegram_*, otp_*, client_*) включён в CONTEXT.md.

---

## AuditLog ORM model location

| Option | Description | Selected |
|--------|-------------|----------|
| app/core/audit_models.py + clients.models рядом (Recommended) | AuditLog в core (audit cross-cutting). FK как строковая 'users.id' — SQLAlchemy не требует import. core⊥modules import-linter contract GREEN. | ✓ |
| AuditLog в modules/auth/models | Логически рядом с users. Но clients.service не может импортировать AuditLog (modules-independent). Проигрывает. | |
| AuditLog в modules/audit — отдельный модуль | Новый placeholder modules/audit/. Но modules.clients и modules.auth пишут в него — ломает modules-independent. | |

**User's choice:** app/core/audit_models.py + clients.models рядом (Recommended).
**Notes:** Зафиксировано как D-05 LOCKED. Файл `audit_models.py` отделён от `audit.py` чтобы не плодить циклическую зависимость с Base.

---

## audit_log.actor_user_id nullability

| Option | Description | Selected |
|--------|-------------|----------|
| NULL разрешён (Recommended) | login_failed (нет идентифицированного user'а), telegram_deep_link_issued (до привязки), telegram_unknown_start. RESTRICT работает и для nullable. | ✓ |
| NOT NULL + системный user | Сид-row 'system'. Добавляет фейковую строку в users — путает RBAC и seed. | |
| NOT NULL + пропускать без-актора события | Не писать login_failed в audit_log. Теряем след по неудачным попыткам входа. | |

**User's choice:** NULL разрешён (Recommended).
**Notes:** Зафиксировано как D-06 LOCKED.

---

## Continuation gate

| Option | Description | Selected |
|--------|-------------|----------|
| Ещё вопросы по PATCH/repo/audit | Sub-вопросы: resource_id type, payload shape, no-op PATCH, IntegrityError handling | |
| Перейти к Audit payload | Payload jsonb shape per-event | |
| Перейти к Search & filters | q= columns, pg_trgm coverage, tag semantics | |
| Перейти к Validation & errors | Phone E.164, gender, tags constraints | |
| Other (free text) | "Пропустить — используй recommended" | ✓ |

**User's choice:** "Пропустить — используй recommended" (free-text Other).
**Notes:** Все остальные нерешённые подвопросы и три неоткрытые gray areas (Audit payload shape, Search & filters, Validation/error model) → Claude's Discretion с recommended defaults в CONTEXT.md.

---

## Claude's Discretion

Шесть LOCKED решений (D-01..D-06) выше. Тринадцать решений отмечены как (Discretion — recommended) — пользователь явно делегировал:

- **D-07** — `audit_log.resource_id PgUUID NULL`. Не-UUID идентификаторы (telegram chat_id BIGINT, OTP hash) живут в payload.
- **D-08** — payload shape per event: `client_created` = краткий snapshot без ПД; `client_updated` = changed_fields list + previous_phone; `client_soft_deleted` = phone+full_name; auth/telegram события — текущий kwargs из call-site.
- **D-09** — no-op PATCH (после exclude_unset нет реальных изменений) → НЕ эмитим `client_updated`.
- **D-10** — Phone E.164 strict regex без backend-нормализации; FE отвечает за маски.
- **D-11** — IntegrityError partial-unique → DomainError `phone_exists` 409.
- **D-12** — `q=` ILIKE по `lower(last_name || ' ' || first_name || ' ' || coalesce(middle_name, ''))` + phone separately; min length 2.
- **D-13** — Tag-фильтр `?tag=X` exact match через `:'X' = ANY(tags)`. Multi-tag → v1.2.
- **D-14** — `createdFrom`/`createdTo` inclusive ISO datetime; `hasTelegram` bool → IS NOT NULL/IS NULL; sort: `created_at DESC` default или `last_name ASC`.
- **D-15** — `gender` TEXT + CHECK `('male', 'female')` (Phase 5 D-07 паттерн).
- **D-16** — `tags TEXT[]` + service-layer валидация: lowercased, max 32 chars/tag, max 16 tags/client, regex `^[a-z0-9а-я\-_]+$`.
- **D-17** — `emergency_contact JSONB` с Pydantic-структурой `{name, phone E.164, relation?}`.
- **D-18** — Module-level functions в service.py / repository.py (не классы).
- **D-19** — Service принимает `AsyncSession`, `actor: User`, DTO; возвращает ORM Client или PaginatedData.
- **D-20** — Migration shape: один файл `0002_clients.py` создаёт extension + clients + audit_log + индексы.
- **D-21** — Route → permission mapping: VIEW/EDIT для read+create+update; DELETE owner-only.

## Deferred Ideas

Все полно перечислены в CONTEXT.md `<deferred>` секции. Кратко:

- Null-out optional полей через PATCH → v1.2
- lint-rule "forbid `select(Client)` outside repository.py" → v1.2 backlog
- `GET /api/v1/audit-log` + read-UI → v1.2 (AUDIT-V12-01/02)
- Audit log full diff (value-pairs old↔new) → v1.2
- Multi-tag фильтр (AND/OR) → v1.2 (CLIENTS-V12-04)
- pg_trgm similarity (`%` оператор) для fuzzy ФИО → v1.2 если ILIKE покажет seq scan
- Direction-toggling sort + другие колонки → out of scope per CLIENTS-04
- Photo upload, Bulk CSV import, "Last visit" filter → v1.2 (CLIENTS-V12-01..03)
- Per-IP rate limit на /clients → v1.2
- Audit-log retention policy → v1.2+
