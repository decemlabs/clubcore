# Phase 30: Foundations & Tech-Debt Bedrock - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-14
**Phase:** 30-Foundations & Tech-Debt Bedrock
**Areas discussed:** Audit payload schemas (INFRA-23), Append-only payments AST walker (INFRA-22), admin-web RBAC parity + DEBT-05 timing

**Areas not selected:** payment_row_hash canonicalization (deferred to planner's discretion at implementation time).

---

## Audit payload schemas (INFRA-23)

### Q1 — Какой механизм лока payload schemas?

| Option | Description | Selected |
|--------|-------------|----------|
| Pydantic models per-event | Новый app/core/audit_payloads.py с Pydantic v2 моделями (PaymentRecordedPayload и т.п.). LOCKED_AUDIT_EVENTS расширяется в dict[tuple, type[BaseModel]]. audit.emit() выполняет model_validate(payload) при вызове. Runtime enforced; mypy-friendly. | ✓ |
| TypedDict per-event | TypedDict-словарь пер event в audit_payloads.py. Нет runtime validation, только mypy --strict check. Легче и быстрее, но пользователи могут передать лишние ключи в runtime. | |
| Dict-key whitelist in audit.emit() | Каждый event мапится в frozenset разрешённых payload-ключей; audit.emit() бросает если set(kwargs.keys()) != allowed. Похоже на существующий LOCKED_AUDIT_EVENTS pattern, минимум кода. Нет type-validation значений. | |

**User's choice:** Pydantic models per-event
**Notes:** Recommended option — выбран без модификаций.

### Q2 — Backfill existing 34 events или только new 16?

| Option | Description | Selected |
|--------|-------------|----------|
| Только новые 16 | Lock payload schemas только для 16 v1.4 events. Существующие 34 остаются с free-form payload (бэккомпат). audit.emit() валидирует payload только если event в новой registry. Меньше risk регрессии. | ✓ |
| Backfill все 50 в Phase 30 | Пишем schemas для всех 50 events. Придётся реверс вывести схемы из реальных callsites в v1.1-v1.3 коде; больше работы + risk сломать старые emit-calls. | |
| Backfill отложить в v1.5 | 16 new events сразу со schemas; 34 старых — deferred-items entry для v1.5 separate cleanup phase. | |

**User's choice:** Только новые 16
**Notes:** Bounded blast radius для v1.4; backfill — explicit v1.5+ deferred idea.

### Q3 — Где живёт payload registry и validation?

| Option | Description | Selected |
|--------|-------------|----------|
| app/core/audit_payloads.py + extend audit.emit() | Новый файл audit_payloads.py со schemas + AUDIT_PAYLOAD_SCHEMAS dict. audit.py импортирует и emit() валидирует. Сохраняет LOCKED_AUDIT_EVENTS как single source для event-list, separate файл для схем. | ✓ |
| Всё в audit.py | Добавляем schemas прямо в существующий audit.py рядом с LOCKED_AUDIT_EVENTS. Одно место истины, но файл растёт больше 200 строк. | |
| В модулях (payments/audit_payloads.py + pt_packages/audit_payloads.py + ...) | Per-module файлы. Но modules-independent контракт ломается, если audit.py пытается их импортировать — каждый модуль регистрирует схемы через composition root. | |

**User's choice:** app/core/audit_payloads.py + extend audit.emit()
**Notes:** Separate file; audit.py остаётся под бюджетом строк; core-level location сохраняет import-linter контракты.

### Q4 — Strict vs forgiving validation mode?

| Option | Description | Selected |
|--------|-------------|----------|
| Strict: extra='forbid' + missing required raises | Pydantic модель с model_config = ConfigDict(extra='forbid'). Лишние ключи в payload сразу вызывают hard fail (под стать с существующей D-09 hard-fail discipline). Pre-commit обязывает писать ровно то что в схеме. | ✓ |
| Allow extra fields, validate types of known | model_config = ConfigDict(extra='allow'). Схемы фиксируют обязательные поля и их типы, но callsite может добавить диагностические kwargs. | |

**User's choice:** Strict
**Notes:** Зеркалит D-09 hard-fail discipline — любой mismatch = программерская ошибка, не graceful degradation.

---

## Append-only payments AST walker (INFRA-22)

### Q1 — Scope walker'а: где искать UPDATE/DELETE против payments?

| Option | Description | Selected |
|--------|-------------|----------|
| Все modules/**/service.py | Mirror SVC001 walker scope. Любой модуль не может писать UPDATE/DELETE в payments. Последовательно с существующим паттерном. | ✓ |
| Только payments/* + repository.py | Narrowest scope — только файлы внутри app/modules/payments/. | |
| Весь app/**/*.py | Самый широкий — включая workers/, integrations/, api/. Risk: больше false positives. | |

**User's choice:** Все modules/**/service.py
**Notes:** Mirrors SVC001 _SERVICE_GLOB constant для согласованности.

### Q2 — Детекция: как понять что операция направлена на payments?

| Option | Description | Selected |
|--------|-------------|----------|
| Import-tracking Payment model class | Walker проверяет import Payment в файле, затем ищет update(Payment)/delete(Payment)/session.delete(payment_instance типа Payment). Точнее чем string-match. Mirrors SVC001 _is_session_execute_with_mutating_sql паттерн. | ✓ |
| String-match table name 'payments' | Простейший: AST ast.Constant value 'payments' вблизи update()/delete() Call. False positives: docstrings, comments. False negatives: alias вроде _T='payments'. | |
| Hybrid: import-tracking + raw SQL text-match | Import-tracking плюс дополнительный скан на text() SQL литералы с 'UPDATE payments' / 'DELETE FROM payments'. | |

**User's choice:** Import-tracking Payment model class
**Notes:** Mirrors SVC001 AST-level type resolution; никаких docstring false positives.

### Q3 — Формат теста + negative-test fixture?

| Option | Description | Selected |
|--------|-------------|----------|
| Pytest unit в tests/unit/test_payments_appendonly.py + synthetic fixture | Mirror test_service_commit_gate.py паттерн. Negative-test fixture живёт в tests/unit/fixtures/ как synthetic .py файл, parametrized test проверяет что walker ловит нарушение и пропускает чистый код. | ✓ |
| Live gate против реальных app/modules/**/service.py + synthetic negative внутри того же теста | Один test_payments_appendonly.py: live walker bound + test_walker_catches_violation с synthetic AST inline. Схоже с SVC001 подходом. | |
| CI shell-script (не pytest) | Отдельный scripts/check_payments_appendonly.py вызывается отдельным CI step. Не проходит в pytest output, но независим от test session. | |

**User's choice:** Pytest unit + synthetic fixture in fixtures/
**Notes:** Mirrors SVC001 test file structure; separate fixtures dir держит negative-test код вне основного app/ tree.

### Q4 — INSERT-only policy — разрешить session.execute(insert(Payment).on_conflict(...))?

| Option | Description | Selected |
|--------|-------------|----------|
| Только plain INSERT | Walker разрешает только session.add(Payment(...)) или session.execute(insert(Payment)...). Postgres on_conflict_do_update() тоже формально UPDATE, запрещаем. ON CONFLICT DO NOTHING — OK (это не mutation). PAY-02 partial UNIQUE и так будет поднимать IntegrityError, on_conflict не нужен. | ✓ |
| INSERT + ON CONFLICT DO NOTHING разрешён, ON CONFLICT DO UPDATE запрещён | Прямо разрешаем .on_conflict_do_nothing() как allowed idempotency паттерн, запрещаем .on_conflict_do_update(). | |

**User's choice:** Только plain INSERT (incl. ON CONFLICT DO NOTHING — формально не mutation)
**Notes:** PAY-02 partial UNIQUE handles concurrent refund через IntegrityError; on_conflict не нужен.

---

## admin-web RBAC parity + DEBT-05 timing

### Q1 — Three-way RBAC parity test: когда обновляем admin-web can.ts + registry.ts?

| Option | Description | Selected |
|--------|-------------|----------|
| В Phase 30 — enum entries only, без routes | Сразу в Phase 30 расширяем admin-web Resource StrEnum, OWNER_ONLY array, и registry.ts mappings (только для новых resources). Parity test зелёный от commit №1. UI implementations в Phase 31/35 могут сразу использовать can(). | ✓ |
| Скипаем parity test в CI до Phase 35 | Бэк проходит полностью Phase 30, parity test помечен как xfail/skip-marker с TODO Phase 35. Risk: забыть включить. Против PROJECT.md «three-way byte-paritet» дисциплины. | |
| Отложить admin-web changes в Phase 31 | Backend пишет Resource.TRAINERS в Phase 30; admin-web миррорит в Phase 31. День в CI parity test красный между phases. | |

**User's choice:** В Phase 30 — enum entries only, без routes
**Notes:** Параллельное расширение бэка и admin-web preserves byte-paritet discipline.

### Q2 — DEBT-05 (mock memberships ?status= parity) — в какой phase?

| Option | Description | Selected |
|--------|-------------|----------|
| В Phase 30 — one-liner + 1-2 теста | Roadmap уже приписывает DEBT-05 к Phase 30. Foundations phase — правильное место для tech-debt carryover. Один файл mock/memberships.ts + 2 mock-parity теста. ~30 минут работы. | ✓ |
| Перенести в Phase 35 (естественная FE-phase) | Phase 30 остаётся чистым backend-foundations. DEBT-05 живёт рядом с FE-10..18 в Phase 35. Требует перепривязки в REQUIREMENTS.md и ROADMAP.md. | |

**User's choice:** В Phase 30 — one-liner + 1-2 теста
**Notes:** Соответствует ROADMAP.md/REQUIREMENTS.md mapping; parallel-eligible с backend планами.

### Q3 — Админ-web mock services для новых resources в Phase 30?

| Option | Description | Selected |
|--------|-------------|----------|
| Нет — только can.ts + registry.ts entries | Mock services для trainers/payments/pt_packages живут в своих phase-фазах (31/32/33). Phase 30 только расширяет enum/array для parity. | ✓ |
| Полные mock-service stubs в Phase 30 | Написать пустые mock services для trainers/payments/pt_packages. | |

**User's choice:** Нет — только can.ts + registry.ts entries
**Notes:** Сохраняет phase-cohesion; mocks принадлежат phase-консьюмерам.

### Q4 — Plan splitting Phase 30: один большой plan или несколько?

| Option | Description | Selected |
|--------|-------------|----------|
| Несколько plans (~3-4) | 1) audit_payloads + LOCKED_AUDIT_EVENTS расширение; 2) RBAC расширение + admin-web parity; 3) import-linter + SVC001 scope + append-only walker; 4) DEBT-05 mock-parity fix. Atomic commits per plan, parallel-eligible 1+3. | ✓ |
| Один большой atomic plan | Все 8 reqs в одном plan-файле, один big commit в конце. | |
| Planner решит сам | Не фиксируем сейчас; planner в /gsd-plan-phase выберет оптимальный split. | |

**User's choice:** Несколько plans (~3-4)
**Notes:** Атомарный rollback per concern; параллельный execute possible на Plans 1+4.

---

## Claude's Discretion

- `payment_row_hash` canonicalization details (column set, JSON canonicalization algorithm, prefix, helper location). User skipped this gray area — planner выберет при имплементации INFRA-23 с constraint deterministic + reproducible.
- Точные payload fields каждой из 16 audit-schemas (выводятся из REQ описаний — PAY-10 уже даёт shape `payment_recorded`, остальные 15 by analogy).
- Имена новых Action/Resource StrEnum members (следовать существующему naming).
- Финальный split на 3 vs 4 plans (planner finalize в /gsd-plan-phase 30).

## Deferred Ideas

- Backfill payload schemas для существующих 34 v1.1–v1.3 events → v1.5+ backlog (рассмотрено и отклонено).
- `payment_row_hash` для других subject_kind events (membership_refunded, pt_package_refunded) — в Phase 32, не Phase 30.
- Mock services для новых resources — per-phase (31/32/33).
- Routes/sidebar items для новых resources — Phase 31 и 35.
- CI shell-script вариант append-only walker (отклонён в пользу pytest unit).
- ON CONFLICT DO UPDATE allow-list (отклонён; PAY-09 Redis idempotency покрывает).
