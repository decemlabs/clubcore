# Phase 30: Foundations & Tech-Debt Bedrock — Context

**Gathered:** 2026-05-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 30 расширяет audit/RBAC/architectural bedrock для v1.4 и закрывает один deferred v1.3 mock-parity gap — чтобы Phases 31..35 могли:
- эмитить новые locked события (`trainer_*`, `payment_*`, `pt_package_*`, `pt_session_*`) с валидированными payload-схемами;
- ссылаться на новые `Resource` значения (`TRAINERS`, `PAYMENTS`, `PT_PACKAGE_PLANS`, `PT_PACKAGES`, `PT_SESSIONS`) с byte-paritet admin-web `can.ts`/`registry.ts`;
- опираться на enforced append-only discipline для `payments` table (AST walker);
- проходить расширенный SVC001 commit-gate + расширенный `.importlinter` `modules-independent` контракт.

8 requirements в скоупе: INFRA-17..23 + DEBT-05 (см. `.planning/REQUIREMENTS.md`).

**Out of scope (deferred):**
- Backfill payload schemas для существующих 34 v1.1–v1.3 events (только новые 16 v1.4).
- Mock-service stubs для trainers/payments/pt_packages (живут в Phase 31/32/33).
- Routes/sidebar items для новых resources (Phase 31/35).
- `payment_row_hash` canonicalization детали (planner решит при имплементации INFRA-23).

</domain>

<decisions>
## Implementation Decisions

### Audit Payload Schemas (INFRA-23)

- **D-30-01:** Механизм — Pydantic v2 BaseModel per-event с `model_config = ConfigDict(extra='forbid')`. Strict validation: extra-keys raise; missing-required raises; mirrors существующую D-09 hard-fail discipline в `audit.emit()`.
- **D-30-02:** Scope backfill — лочим payload schemas ТОЛЬКО для 16 новых v1.4 events. Существующие 34 v1.1–v1.3 события остаются с free-form payload (бэккомпат). `audit.emit()` валидирует payload только если `(event, resource_type)` есть в новом `AUDIT_PAYLOAD_SCHEMAS` registry.
- **D-30-03:** Location — новый файл `apps/backend/app/core/audit_payloads.py` экспортирует `AUDIT_PAYLOAD_SCHEMAS: dict[tuple[str, str], type[BaseModel]]`. `app/core/audit.py` импортирует этот dict и вызывает `Schema.model_validate(payload_kwargs)` после `LOCKED_AUDIT_EVENTS` check, но перед structlog + DB write. `LOCKED_AUDIT_EVENTS` остаётся single source для event-list; schemas — отдельный файл.
- **D-30-04:** `payment_refunded` schema МUST include `payment_row_hash: str` (SHA-256 canonical-JSON of original payment row) per INFRA-23. Точная canonicalization алгоритма (sort_keys vs RFC 8785, какие колонки, prefix) — planner решит при имплементации (помечено как Claude's Discretion ниже).

### Append-only Payments AST Walker (INFRA-22)

- **D-30-05:** Scope — `modules/**/service.py` glob (mirrors существующий SVC001 walker scope в `apps/backend/tests/unit/test_service_commit_gate.py`). Любой будущий business module не может писать UPDATE/DELETE против `payments`.
- **D-30-06:** Detection — import-tracking: walker резолвит `Payment` model class через `from app.modules.payments.models import Payment` (или эквивалентный alias), затем флагает `update(Payment)`, `delete(Payment)`, `session.execute(update(Payment)...)`, `session.execute(delete(Payment)...)`, `session.delete(<Payment-typed instance>)`. Точнее чем string-match — никаких false positives на docstrings. Mirrors `_is_session_execute_with_mutating_sql` pattern из SVC001.
- **D-30-07:** Test format — pytest unit-test в `apps/backend/tests/unit/test_payments_appendonly.py` mirroring `test_service_commit_gate.py`. Live walker bound против `app/modules/**/service.py` + synthetic negative-test fixture в `apps/backend/tests/unit/fixtures/payments_violation_*.py` (parametrized: проверяем что walker ловит UPDATE и DELETE, и пропускает чистый INSERT/`session.add`).
- **D-30-08:** INSERT-only policy — разрешён только plain INSERT: `session.add(Payment(...))`, `session.execute(insert(Payment).values(...))`, `session.execute(insert(Payment)...on_conflict_do_nothing())`. Запрещён `on_conflict_do_update()` (формально UPDATE). PAY-02 partial UNIQUE `(refund_of) WHERE refund_of IS NOT NULL` handles concurrent refund через IntegrityError — on_conflict не нужен.

### admin-web RBAC Parity + DEBT-05 (INFRA-18/19 + DEBT-05)

- **D-30-09:** Three-way parity timing — admin-web `can.ts` + `registry.ts` обновляются в Phase 30 в той же атомарной серии что backend Resource/OWNER_ONLY расширение. Только enum entries + OWNER_ONLY array deltas — никаких routes/sidebar items (это в Phase 31/35). Parity test зелёный от первого commit Phase 30; downstream UI implementations (Phase 31/35) могут сразу вызывать `can(role, action, resource)` без блокеров.
- **D-30-10:** Mock services scope — Phase 30 НЕ пишет mock-service stubs для trainers/payments/pt_packages. Mock services для них живут в своих phase-фазах (Phase 31 trainers mock, Phase 32 payments mock, Phase 33 pt_packages mock). Phase 30 ограничивается admin-web `can.ts` Resource/OWNER_ONLY entries.
- **D-30-11:** DEBT-05 остаётся в Phase 30 (как и в ROADMAP.md/REQUIREMENTS.md). One-liner fix в `apps/admin-web/src/shared/api/services/mock/memberships.ts` `list()` — добавить `query.status` filter; 1-2 mock-parity теста ("Заморожен" pill в mock-режиме фильтрует). Логически часть «foundations / cleanup» phase, parallel-eligible с backend работой.

### Plan Splitting

- **D-30-12:** Разбиваем Phase 30 на ~3-4 plans для атомарных commits:
  - **Plan 1 — Audit bedrock**: `LOCKED_AUDIT_EVENTS` 34→50 + `audit_payloads.py` Pydantic schemas + `audit.emit()` extension (INFRA-17 + INFRA-23).
  - **Plan 2 — RBAC bedrock**: backend `Resource`/`OWNER_ONLY` extension + admin-web `can.ts`/`registry.ts` entries + three-way parity test расширение (INFRA-18 + INFRA-19).
  - **Plan 3 — Architectural bedrock**: `.importlinter` `modules-independent` contract entries для `payments`+`pt_packages` + SVC001 walker scope extension + новый append-only AST walker + negative-test fixtures (INFRA-20 + INFRA-21 + INFRA-22).
  - **Plan 4 — DEBT-05 mock parity**: `mock/memberships.ts` `?status=` filter + 1-2 mock-parity теста (DEBT-05).
  - Plans 1 и 4 parallel-eligible (no overlapping files). Plans 2 и 3 must follow Plan 1 (Resource enum needed first для OWNER_ONLY entries; new event-payload pairs needed before downstream callsites can compile-check).

### Claude's Discretion

- `payment_row_hash` SHA-256 canonicalization детали (columns set, JSON canonicalization algorithm — `json.dumps(..., sort_keys=True, separators=(',', ':'), default=str)` vs RFC 8785 JCS, prefix `sha256:` vs raw hex, location helper в `core/audit_hash.py` vs `payments/service.py`) — planner выберет при имплементации INFRA-23. Constraint: deterministic, reproducible, документировано в payload schema docstring.
- Точный split (a) одного big plan-файла vs (b) 3-4 plans — finalize в `/gsd-plan-phase 30` с учётом текущей `parallel-eligible` дисциплины.
- Имена новых Action/Resource enum members — следовать существующему StrEnum naming (`CREATE`/`VIEW`/`LIST`/`EDIT`/`DELETE`/`CANCEL`/`REFUND` — REUSE existing Actions per INFRA-18; никаких новых Actions).
- Точные payload-поля для каждой из 16 schemas — выводятся из REQ описаний (PAY-10 говорит payload `{payment_id, subject_kind, subject_id, amount_kopecks, method, received_by_user_id, payment_row_hash}` для `payment_recorded`; остальные 15 — research/planner выведет по аналогии из existing audit emit-callsites).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v1.4 Milestone-level Contracts (CRITICAL)
- `.planning/REQUIREMENTS.md` §INFRA — INFRA-17..23 + DEBT-05 verbatim requirements; bedrock decisions B-01..B-12 listed in header.
- `.planning/ROADMAP.md` §Phase 30 — phase goal + 5 success criteria; dependencies (none — first phase of v1.4).
- `.planning/PROJECT.md` Key Decisions table — 12 v1.4 bedrock decisions B-01..B-12 will be appended here on phase completion.
- `.planning/STATE.md` §Decisions — B-01..B-12 листинг с B-04 и B-07 confirmed by user.

### Existing Bedrock Files (TOUCHED in this phase)
- `apps/backend/app/core/audit.py` §`LOCKED_AUDIT_EVENTS` (line 102) — 34-entry frozenset to be extended to 50; `emit()` function (line ~166) extended to call `Schema.model_validate(payload)` if event in new registry.
- `apps/backend/app/core/permissions.py` §`Resource`/`Action`/`OWNER_ONLY` (lines 20–80) — extend Resource (+5), OWNER_ONLY (+~11 net entries), reuse existing Actions.
- `apps/backend/.importlinter` §`[importlinter:contract:modules-independent]` (line 13) — extend modules list (`payments`, `pt_packages`; `trainers` уже есть как v1.0 placeholder).
- `apps/backend/tests/unit/test_service_commit_gate.py` — extend `_LIVE_MODULES` scope (or equivalent) to include `payments/service.py`, `trainers/service.py`, `pt_packages/service.py` (даже на заглушках).
- `apps/admin-web/src/shared/session/can.ts` — extend Resource StrEnum + OWNER_ONLY array (byte-paritet with backend).
- `apps/admin-web/src/shared/session/registry.ts` — extend resource mappings (entries только, без routes).
- `apps/admin-web/src/shared/api/services/mock/memberships.ts` §`list()` — DEBT-05 one-liner: add `query.status` filter.

### New Files (CREATED in this phase)
- `apps/backend/app/core/audit_payloads.py` — Pydantic schemas + `AUDIT_PAYLOAD_SCHEMAS` registry dict for 16 new events.
- `apps/backend/tests/unit/test_payments_appendonly.py` — new AST walker test (mirrors SVC001 pattern).
- `apps/backend/tests/unit/fixtures/payments_violation_*.py` — synthetic negative-test fixtures.

### Prior-Phase Patterns to Mirror
- `.planning/milestones/v1.3-ROADMAP.md` §Phase 24 — v1.3 foundations phase precedent (INFRA-15 audit pre-registration + INFRA-16 status taxonomy + DEBT-01/02/03 closure). Same discipline: pre-register events BEFORE callsites; extend lints before module-shells exist.

### Decision References
- PROJECT.md Key Decisions: «`LOCKED_AUDIT_EVENTS` — frozen up-front before callsites land» (v1.3 Phase 24 entry) — same discipline для Phase 30 INFRA-17.
- PROJECT.md Key Decisions: «D-09 hard-fail» — strict validation pattern для payload-schema mismatch (INFRA-23).
- PROJECT.md Constraints: «Tooling: ruff + mypy strict + import-linter обязательны» — все 3 walkers/contracts остаются runnable локально через `uv run`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/core/audit.py` `emit()` function — extension point: insert `Schema.model_validate(payload)` call between `LOCKED_AUDIT_EVENTS` check (line ~199) и existing structlog/DB write. Caller-owns-txn discipline (D-03) сохраняется.
- `apps/backend/tests/unit/test_service_commit_gate.py` AST walker pattern — `_is_session_call`, `_is_session_execute_with_mutating_sql`, `_is_audit_emit_call` helpers — reusable shape для нового append-only walker.
- `app/core/schemas.py` `BackendSchemaBase` — Pydantic 2.11 canonical pair с `alias_generator=to_camel`. NOT to be used для audit-payloads (audit payloads — internal, snake_case kwargs). Audit-payload schemas наследуют `BaseModel` напрямую.
- Existing `_SERVICE_GLOB = "modules/**/service.py"` constant в SVC001 walker — reuse идентично в новом payments-appendonly walker.

### Established Patterns
- **Pre-registration discipline (v1.3 Phase 24 INFRA-15):** новые audit events лочатся в frozenset ДО первого callsite. Phase 30 повторяет — все 16 событий + их schemas live в этой phase, Phases 31..35 потребляют без drift.
- **Three-way RBAC parity (v1.1 Phase 6 TEST-06):** backend `OWNER_ONLY` ↔ admin-web `can.ts` ↔ `registry.ts` — байт-паритет через parity test. Phase 30 расширяет все три ноды в одном плане.
- **AST gate test pattern (v1.2 Phase 15 INFRA-13 / SVC001):** AST walker как pytest unit-test с synthetic fixture; live bound против реальных модулей. Phase 30 повторяет ровно ту же структуру для append-only walker.
- **`.importlinter` 3 контракта (v1.0 Phase A):** top-level shape не меняется; только `modules-independent` modules list расширяется. Mirrors v1.3 Phase 24 (расширили на v1.3 modules без структурных изменений).
- **D-09 hard-fail discipline:** unknown `(event, resource_type)` raises `AuditEventNotLockedError` — НЕ DEBUG-only assert, НЕ graceful degradation. Phase 30 расширяет: invalid payload (extra='forbid') тоже raises (Pydantic `ValidationError`).

### Integration Points
- `audit.emit()` — единственная точка вызова валидации payload schemas; не дублируется в callsites.
- `AUDIT_PAYLOAD_SCHEMAS` registry — single import в `audit.py`. Не зависит от `app.modules.*` (uses primitive types в Pydantic models), сохраняя `core ⊥ modules` контракт.
- New append-only walker зависит ТОЛЬКО от `apps/backend/app/modules/payments/models.py` existence (для resolution Payment class). Поскольку Phase 30 не создаёт `models.py` (только модуль-shells via INFRA-20/21), walker должен корректно обрабатывать «no Payment import found» → no-op (no false negatives когда `payments` модуль ещё не материализовался). Альтернативно: гарантировать что Phase 30 создаёт минимальный `payments/models.py` со stub `Payment` declarative class (decision — planner).
- admin-web parity test — `apps/admin-web/src/test/*` (existing parity tests location); расширение покрытия на 5 новых resources.

</code_context>

<specifics>
## Specific Ideas

- **Strict-only validation** (Pydantic `extra='forbid'`): user явно зафиксировал «mirror существующую D-09 hard-fail discipline». Никакой tolerant/permissive режим не рассматривается.
- **«Только новые 16» backfill scope**: user явно отверг полный backfill 50 events и v1.5-deferred backfill plan. Решение «keep existing 34 free-form» — bounded blast radius для v1.4.
- **Import-tracking detection** (а не string-match): user явно выбрал точную AST-резолюцию класса `Payment`. False positives недопустимы (SVC001 lesson).
- **3-4 plans, не один**: user явно выбрал split на parallel-eligible plans (audit / RBAC / arch / DEBT-05). Атомарный rollback per concern.
- **DEBT-05 остаётся в Phase 30**: user явно подтвердил — не двигаем в Phase 35 несмотря на FE-природу fix'а. Foundations phase — правильное место для tech-debt carryover.

</specifics>

<deferred>
## Deferred Ideas

- **Backfill payload schemas для 34 v1.1–v1.3 audit events.** Рассмотрено — отклонено. Если потребуется retro-fit, отдельная phase в v1.5+ (note для v1.5 backlog).
- **`payment_row_hash` для v1.4 — это только `payment_refunded` event.** Расширение на другие subject_kind events (например, `membership_refunded`, `pt_package_refunded`) — рассмотреть в Phase 32, не Phase 30. INFRA-23 conservative scope.
- **Mock services для новых resources (trainers/payments/pt_packages).** Per-phase (31/32/33), не в Phase 30. Сохраняет phase-cohesion.
- **Routes/sidebar items для новых resources в admin-web.** Phase 31 (`/trainers`) и Phase 35 (`/pt-packages`, `/pt-package-plans`); Phase 30 только can.ts/registry.ts entries.
- **CI shell-script вариант append-only walker** (вместо pytest unit). Отклонён — pytest mirror SVC001 удобнее для local dev (uv run pytest).
- **ON CONFLICT DO UPDATE allow-list для future Idempotency-Key replay.** Отклонён — PAY-09 Redis-cached `sz:idem:{key}` уже решает replay; on_conflict_do_update не нужен в payments.

### Reviewed Todos (not folded)
None — no pending todos matched phase 30 scope (state.md «Pending Todos» только содержит `Run /gsd-discuss-phase 30` который мы и выполняем).

</deferred>

---

*Phase: 30-Foundations & Tech-Debt Bedrock*
*Context gathered: 2026-05-14*
