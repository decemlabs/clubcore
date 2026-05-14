# Roadmap: Sportzal

## Milestones

- ✅ **v1.0 Phase A: Skeleton** — Phases 1-3 (shipped 2026-05-01) — see [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 Auth + Clients** — Phases 4-14 (shipped 2026-05-07) — see [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
- ✅ **v1.2 Memberships + Visits** — Phases 15-23 (shipped 2026-05-08) — see [milestones/v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md)
- ✅ **v1.3 Memberships Extras + Tech-Debt** — Phases 24-29 (shipped 2026-05-14) — see [milestones/v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)
- 🚧 **v1.4 Cash Sales + PT Packages** — Phases 30-36 (planning, started 2026-05-14)

## Phases

<details>
<summary>✅ v1.0 Phase A: Skeleton (Phases 1-3) — SHIPPED 2026-05-01</summary>

- [x] Phase 1: Monorepo Restructure & Frontend Move (3/3 plans) — completed 2026-04-30
- [x] Phase 2: Backend Skeleton with Quality Tooling (8/8 plans) — completed 2026-04-30
- [x] Phase 3: Tests, Dev Infrastructure & Documentation (6/6 plans) — completed 2026-05-01

Full details: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

<details>
<summary>✅ v1.1 Auth + Clients (Phases 4-14) — SHIPPED 2026-05-07</summary>

- [x] Phase 4: Auth Foundations & Cookie/RBAC Primitives (9/9 plans) — completed 2026-05-02
- [x] Phase 5: User Schema + Email/Password Auth (8/8 plans) — completed 2026-05-03
- [x] Phase 6: RBAC Wiring + Parity Tests (5/5 plans) — completed 2026-05-03
- [x] Phase 7: Telegram OTP Channel (8/8 plans) — completed 2026-05-04
- [x] Phase 8: Clients Module + Audit Log (8/8 plans) — completed 2026-05-04
- [x] Phase 9: OpenAPI Pipeline + packages/api-client (3/3 plans) — completed 2026-05-04
- [x] Phase 10: admin-web Auth + Clients Wiring (8/8 plans) — completed 2026-05-04
- [x] Phase 11: Clients HTTP-mode Shape Adapter *(gap closure)* (2/2 plans) — completed 2026-05-04
- [x] Phase 12: v1.1 Verification Backfill *(gap closure)* (5/5 plans) — completed 2026-05-05
- [x] Phase 12.1: Clients Service Commit Fix *(inline quick-fix `260504-fst`, commit ba14aba)* — completed 2026-05-04
- [x] Phase 13: v1.1 Minor Drift & Hygiene Cleanup *(gap closure)* (4/4 plans) — completed 2026-05-05
- [x] Phase 14: Clients Search PII Hardening *(gap closure, security)* (3/3 plans) — completed 2026-05-07

Full details: [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)

</details>

<details>
<summary>✅ v1.2 Memberships + Visits (Phases 15-23) — SHIPPED 2026-05-08</summary>

- [x] Phase 15: Foundations — RBAC + audit taxonomy + helper hoisting (5/5 plans) — completed 2026-05-07
- [x] Phase 16: Membership Plans Catalog (backend) (5/5 plans) — completed 2026-05-07
- [x] Phase 17: Membership Instances + Resolver (backend) (5/5 plans) — completed 2026-05-07
- [x] Phase 18: ARQ scheduled `expire_memberships` (6/6 plans) — completed 2026-05-07
- [x] Phase 19: Visits — DB + reception check-in (backend) (5/5 plans) — completed 2026-05-07
- [x] Phase 20: Telegram bot `/checkin` self check-in (3/3 plans) — completed 2026-05-08
- [x] Phase 21: OpenAPI drift gate refresh + api-client codegen (1/1 plan) — completed 2026-05-08
- [x] Phase 22: admin-web wiring — memberships + visits + active sessions UI (5/5 plans) — completed 2026-05-08
- [x] Phase 23: Hygiene + active sessions backend *(parallel-eligible)* (1/1 plan) — completed 2026-05-08

Full details: [milestones/v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md)

</details>

<details>
<summary>✅ v1.3 Memberships Extras + Tech-Debt (Phases 24-29) — SHIPPED 2026-05-14</summary>

- [x] Phase 24: Foundations & Tech-Debt Bedrock (5/5 plans) — completed 2026-05-08 — INFRA-15/16 + DEBT-01/02/03
- [x] Phase 25: Memberships — Freeze (backend) (5/5 plans) — completed 2026-05-09 — MEM-FRZ-01..07 + EP-01..03 + AUDIT-01 + TEST-01..03
- [x] Phase 26: Memberships — Renewal (backend) (4/4 plans) — completed 2026-05-09 — MEM-REN-01..04 + EP-01 + AUDIT-01 + TEST-01..04
- [x] Phase 27: Expiring-soon Telegram Notifications (5/5 plans) — completed 2026-05-09 — NTF-01..06 + COPY-01 + TEST-01..03
- [x] Phase 28: OpenAPI Drift-Gate Refresh + admin-web Wiring (8/8 plans) — completed 2026-05-10 — FE-10/11/12/13 *(1 mock-parity gap deferred to v1.4)*
- [x] Phase 29: Milestone Verification (6/6 plans) — completed 2026-05-14 — DEBT-04 *(7/7 scenarios passed; 3 inline blocker fixes; see milestones/v1.3-VERIFICATION-LOG.md)*

Full details: [milestones/v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)

</details>

### 🚧 v1.4 Cash Sales + PT Packages (Phases 30-36) — IN PROGRESS

- [ ] **Phase 30: Foundations & Tech-Debt Bedrock** — INFRA-17/18/19/20/21/22/23 + DEBT-05 (8 reqs) — `LOCKED_AUDIT_EVENTS` 34→51, Resource/OWNER_ONLY extension, import-linter modules list, SVC001 walker scope, append-only `payments` AST guard, v1.3 mock `?status=` parity fix
- [ ] **Phase 31: Trainers Module** — TRN-01..08 (8 reqs) — `trainers` table + CRUD + `is_active` deactivate/reactivate + Protocol slot resolver + admin-web `/trainers` page
- [ ] **Phase 32: Payment Ledger + Sale Flow + Refund** — PAY-01..10 + REF-01..08 (18 reqs) — `payments` append-only ledger + `record_payment`/`issue_refund` services + Protocol slots + `Idempotency-Key` header + `POST /memberships/{id}/refund` + frozen/renewed-source guards
- [ ] **Phase 33: PT-Package Plans + Instances** — PT-01..13 (13 reqs) — `pt_package_plans` + `pt_packages` tables + sell/cancel/refund endpoints + status transitions + `expire_pt_packages` ARQ cron 06:25 MSK
- [ ] **Phase 34: PT-Session Recording** — PT-14..22 (9 reqs) — `pt_sessions` table + race-safe decrement + auto-exhausted transition + cancel with balance restore + backdating windows
- [ ] **Phase 35: OpenAPI Drift Gate + admin-web Full Wiring** — FE-10..18 (9 reqs) — byte-stable regen of `openapi.json` + `schema.d.ts` + sale-with-payment + refund AlertDialog + PT-session UI + `/trainers` + `PaymentBadge` + `PtPackageStatusBadge` + locked Russian i18n + three-way RBAC parity
- [ ] **Phase 36: Milestone Verification** — VER-01..04 (4 reqs) — 7+ operator scenarios against live stack + race tests (REF/PTS/PAY/AUDIT) + 6 CI gates green + operator sign-off in `v1.4-VERIFICATION-LOG.md`

## Phase Details

### Phase 30: Foundations & Tech-Debt Bedrock
**Goal:** Расширить audit/RBAC/architectural bedrock и закрыть deferred v1.3 mock-parity gap — чтобы все последующие phases (31..35) могли эмитить новые locked события, ссылаться на новые `Resource` значения, и опираться на enforced append-only discipline для payments.
**Depends on:** Nothing (first phase of v1.4 milestone; builds on v1.3 Phase 24 foundations)
**Requirements:** INFRA-17, INFRA-18, INFRA-19, INFRA-20, INFRA-21, INFRA-22, INFRA-23, DEBT-05
**Success Criteria** (what must be TRUE):
  1. `LOCKED_AUDIT_EVENTS` frozenset содержит 51 entries (17 новых v1.4 событий — trainer/payment/refund/pt_package/pt_session lifecycle); `audit.emit` AST literal-string gate всё ещё блокирует ad-hoc строки; canonical payload schemas зафиксированы, включая `payment_row_hash` (SHA-256) на `payment_refunded`.
  2. `Resource` enum расширен на 5 значений (`TRAINERS`, `PAYMENTS`, `PT_PACKAGE_PLANS`, `PT_PACKAGES`, `PT_SESSIONS`); `OWNER_ONLY` frozenset вырос с 15 до ~26 entries (reception сохраняет `(CREATE, PAYMENTS)`, `(REFUND, MEMBERSHIPS)`, `(REFUND, PT_PACKAGES)`, `(CREATE, PT_PACKAGES)`, `(CREATE, PT_SESSIONS)`, `(LIST, TRAINERS)`); three-way byte-paritet с admin-web `can.ts` + `registry.ts` проходит CI.
  3. `.importlinter` `modules-independent` контракт расширен на `trainers`, `payments`, `pt_packages`; три top-level контракта остаются неизменными по форме; `lint-imports` зелёный.
  4. SVC001 AST commit-gate walker покрывает `payments/service.py`, `trainers/service.py`, `pt_packages/service.py` (даже на заглушках); новый AST walker запрещает `UPDATE`/`DELETE` SQL против таблицы `payments` в любом service-файле, negative-test fixture проваливается на CI.
  5. v1.3 deferred gap закрыт — `apps/admin-web/src/shared/api/services/mock/memberships.ts` `list()` фильтрует по `query.status`; «Заморожен» pill на `/memberships` работает идентично в mock и http режимах; 1-2 mock-parity теста зафиксированы.
**Plans:** 3/4 plans executed
- [x] 30-01-PLAN.md — Audit bedrock: LOCKED_AUDIT_EVENTS 34→51 + audit_payloads.py Pydantic schemas + emit() validation hook (INFRA-17, INFRA-23) — Wave 1
- [x] 30-02-PLAN.md — RBAC bedrock: backend Resource/OWNER_ONLY +5/+11 + admin-web can.ts/registry.ts byte-paritet + parity test (INFRA-18, INFRA-19) — Wave 2
- [ ] 30-03-PLAN.md — Architectural bedrock: .importlinter modules-independent +2 + SVC001 walker scope +3 + new append-only AST walker + 5 fixtures + module placeholders (INFRA-20, INFRA-21, INFRA-22) — Wave 2
- [x] 30-04-PLAN.md — DEBT-05 mock parity: mock/memberships.ts list() respects query.status inside expiring branch + 2 new vitest specs (DEBT-05) — Wave 1

### Phase 31: Trainers Module
**Goal:** Owner может вести каталог тренеров (CRUD + soft-delete через `is_active`), reception видит только активных в PT-session picker; новый бизнес-модуль `trainers/` следует существующему монолитному паттерну, не нарушает `modules-independent` контракт, и закладывает Protocol slot для будущего PT-session валидатора.
**Depends on:** Phase 30 (нужны новые `Resource` значения, `OWNER_ONLY` расширение, locked audit events `trainer_created`/`updated`/`deactivated`/`reactivated`, SVC001 walker scope на `trainers/service.py`, `.importlinter` modules entry)
**Requirements:** TRN-01, TRN-02, TRN-03, TRN-04, TRN-05, TRN-06, TRN-07, TRN-08
**Success Criteria** (what must be TRUE):
  1. Миграция `0011_trainers.py` создаёт `trainers` (`id`, `full_name`, `phone NULL`, `is_active BOOL DEFAULT TRUE`, `deleted_at`) с partial UNIQUE на `phone WHERE deleted_at IS NULL AND phone IS NOT NULL` (mirrors v1.1 clients pattern).
  2. Owner-only CRUD `POST/GET/PATCH/DELETE /api/v1/trainers` с CSRF; PATCH разрешает деактивацию/реактивацию; hard-delete возвращает 409 `trainer_in_use` при наличии FK из `pt_sessions`; `GET /api/v1/trainers?active=true` доступен reception для PT-session picker.
  3. Protocol slot `register_trainer_by_id_resolver` в `core/dependencies.py` зарегистрирован из `app/main.py:create_app()` И из `app/workers/telegram_bot.py:main()` (defensive double-wiring per REG-29-03 lesson из v1.3).
  4. Каждая lifecycle transition эмитит соответствующее audit-событие (`trainer_created`/`trainer_updated`/`trainer_deactivated`/`trainer_reactivated`); `BusinessService` SVC001 gate проходит.
  5. admin-web `/trainers` route (owner-only `beforeLoad`) показывает таблицу тренеров с active filter pill, create/edit modal (RHF + Zod), deactivate/reactivate кнопки, hard-delete с inline 409 surface; mock service синхронизирован.
**Plans:** TBD
**UI hint**: yes

### Phase 32: Payment Ledger + Sale Flow + Refund
**Goal:** Каждая продажа абонемента фиксируется в append-only ledger с указанием суммы и принявшего сотрудника; reception/owner может выполнить возврат, который атомарно добавляет negative-amount row, переводит membership в `cancelled` со специальным `cancellation_reason='refunded'`, и эмитит forensic-traceable audit chain — без owner-approval gate (B-07 uniform reception).
**Depends on:** Phase 30 (locked audit events `payment_recorded`/`refund_issued`/`membership_refunded`, append-only AST guard, новые Resource значения), Phase 31 (нужен только в части reception RBAC — PAYMENTS resource); PT-package refund endpoint (REF-02) определяется здесь по схеме, но wires в pt_packages модуле в Phase 33
**Requirements:** PAY-01, PAY-02, PAY-03, PAY-04, PAY-05, PAY-06, PAY-07, PAY-08, PAY-09, PAY-10, REF-01, REF-02, REF-03, REF-04, REF-05, REF-06, REF-07, REF-08
**Success Criteria** (what must be TRUE):
  1. Миграция `0012_payments.py` создаёт `payments` (UUIDv4 PK, `subject_kind ∈ {'membership','pt_package','refund'}`, `subject_id`, `amount_kopecks` signed, `method='cash'` default forward-seam, `received_at`, `received_by_user_id FK users`, `refund_of` self-FK ON DELETE RESTRICT, `audit_log_id` FK); CHECK enforces amount-sign matches subject_kind; partial UNIQUE `(refund_of) WHERE refund_of IS NOT NULL` (concurrent refund loses at DB layer); **NO `deleted_at`, NO `updated_at`** (append-only, AST-guarded).
  2. Новый модуль `app/modules/payments/` (router + service + repository + schemas + permissions); `record_payment(...)` и `issue_refund(...)` следуют caller-owns-txn discipline; Protocol slots `register_payment_recorder` + `register_payment_refunder` зарегистрированы исключительно из `app/main.py:create_app()`; `memberships.service.create_membership` потребляет recorder в той же UoW и пишет `payment.amount == membership.price_kopecks_snapshot` (mandatory snapshot symmetry, server-enforced).
  3. `POST /api/v1/memberships/{id}/refund` (reception+owner per B-07) принимает `{reason: string}`, отвергает explicit `amount_kopecks` (B-02 full-only), возвращает 409 `must_unfreeze_first` для frozen membership (B-08), 409 `cannot_refund_renewed_source` если у membership есть descendant в `previous_membership_id` (B-09); атомарно: insert negative-amount payments row + transition membership на `cancelled` с `cancellation_reason='refunded'` + emit `refund_issued` + `payment_refunded` + `membership_refunded`.
  4. `Idempotency-Key` HTTP header требуется на `POST /api/v1/memberships` (sale) и forthcoming PT-package sale; Redis-cached `sz:idem:{key}` 1h, replay возвращает cached response; `GET /api/v1/payments` (owner-only с фильтрами `subject_kind`/`subject_id`/`received_by_user_id`/`received_from`/`received_to`) + `GET /api/v1/clients/{id}/payments` + `GET /api/v1/memberships/{id}/payments` (оба reception+owner) возвращают pagination envelope.
  5. Postgres integration test REF-TEST-01 проверяет: 2 concurrent `POST /refund` против одного membership → ровно один успешен (partial UNIQUE wins), второй 409; audit chain `payment_recorded` → `refund_issued` → `payment_refunded` → `membership_refunded` traceable через `payment_row_hash`.
**Plans:** TBD

### Phase 33: PT-Package Plans + Instances
**Goal:** Зал может продавать PT-пакеты как новый тариф рядом с месячными абонементами; каждый клиент имеет максимум один активный пакет; expired-by-date pакеты автоматически переходят в `expired` через daily ARQ cron; refund переиспользует payment ledger из Phase 32.
**Depends on:** Phase 30 (locked audit events `pt_package_*`, новые Resource значения, append-only AST guard), Phase 32 (Protocol slots `payment_recorder`/`payment_refunder` уже доступны; REF-02 endpoint shape определён). Сессии (PT-14..22) сюда НЕ входят — landed в Phase 34.
**Requirements:** PT-01, PT-02, PT-03, PT-04, PT-05, PT-06, PT-07, PT-08, PT-09, PT-10, PT-11, PT-12, PT-13
**Success Criteria** (what must be TRUE):
  1. Миграции `0013_pt_package_plans.py` + `0014_pt_packages.py` создают `pt_package_plans` (`name`, `session_count INT CHECK > 0` immutable, `price_kopecks CHECK > 0`, `validity_days NULL CHECK > 0`, partial UNIQUE `lower(name) WHERE deleted_at IS NULL`) и `pt_packages` (full snapshot suite — `plan_name_snapshot`/`session_count_snapshot`/`price_kopecks_snapshot`/`validity_days_snapshot NULL`, `sessions_remaining INT NOT NULL CHECK >= 0 AND <= session_count_snapshot`, `status ∈ {active,exhausted,expired,cancelled}`, `start_date` default Europe/Moscow, derived `end_date NULL`, `cancellation_reason NULL`) с partial UNIQUE `(client_id) WHERE status='active'`.
  2. Owner-only CRUD `POST/GET/PATCH/DELETE /api/v1/pt-package-plans` с immutability invariants на `session_count`/`price_kopecks`/`validity_days` (PATCH rejects 409 `field_immutable`); soft-delete возвращает 409 `plan_in_use` при наличии instance FK; 3 audit events эмитятся.
  3. `POST /api/v1/pt-packages` (reception+owner) продаёт пакет: snapshot из current plan, insert instance, вызов `payment_recorder` в той же UoW (symmetric к v1.2 membership sale); `POST /api/v1/pt-packages/{id}/cancel` (owner-only) переводит на `cancelled` без refund; `POST /api/v1/pt-packages/{id}/refund` (reception+owner per B-07) переиспользует `payment_refunder` Protocol slot; `PT_PACKAGE_STATUS_TRANSITIONS` константа + `_assert_can_transition` guard (mirrors v1.3 memberships) запрещают invalid moves с 409 `invalid_transition`.
  4. Protocol slot `register_active_pt_package_resolver` (тот же shape что v1.2 `ActiveMembership`) зарегистрирован в `app/main.py`; `GET /api/v1/pt-packages?client_id=...&status=active` доступен reception для PT-session form prefill; `GET /api/v1/pt-packages/{id}` возвращает instance со snapshot fields и `sessions_remaining`.
  5. Новый ARQ cron `expire_pt_packages` в 06:25 Europe/Moscow (контейнер `TZ=UTC` + `cron(hour=3, minute=25, unique=True, keep_result=60)`) переводит packages с `status='active' AND end_date IS NOT NULL AND end_date < today(Europe/Moscow)` в `expired`, идемпотентен (re-run в тот же день — no-op), эмитит один `pt_package_expired` per row; 5 audit events (`pt_package_sold`/`cancelled`/`refunded`/`exhausted`/`expired`) проходят `LOCKED_AUDIT_EVENTS` gate.
**Plans:** TBD

### Phase 34: PT-Session Recording
**Goal:** Reception фиксирует факт проведённой персональной тренировки с конкретным тренером; баланс пакета атомарно декрементируется DB-level race-safe SQL; при достижении нуля пакет автоматически переходит в `exhausted`; cancellation сессии восстанавливает баланс; PT-сессии независимы от visits (orthogonal events).
**Depends on:** Phase 31 (trainers FK target + `register_trainer_by_id_resolver` slot для валидации active trainer), Phase 33 (`pt_packages` instance таблица с `sessions_remaining` + Protocol slot `active_pt_package_resolver`)
**Requirements:** PT-14, PT-15, PT-16, PT-17, PT-18, PT-19, PT-20, PT-21, PT-22
**Success Criteria** (what must be TRUE):
  1. Миграция `0015_pt_sessions.py` создаёт `pt_sessions` (`id`, `pt_package_id FK ON DELETE RESTRICT`, `trainer_id FK ON DELETE RESTRICT`, `client_id FK` денормализованный, `performed_at`, `performed_by_user_id`, `cancelled_at NULL`, `cancel_reason NULL`, `trainer_name_snapshot NOT NULL` per B-05, `notes NULL` ≤500 chars) с composite indexes `(pt_package_id, performed_at DESC)` и `(trainer_id, performed_at DESC)`.
  2. `POST /api/v1/pt-sessions` (reception+owner) валидирует trainer existence+active через Protocol slot + package active status + `performed_at` в backdating-окне (B-11: reception ≤7d, owner unlimited); race-safe декремент через single SQL `UPDATE pt_packages SET sessions_remaining = sessions_remaining - 1 WHERE id=:id AND sessions_remaining > 0 AND status='active' RETURNING sessions_remaining`; 0-row return → 409 `pt_package_exhausted`; defence-in-depth CHECK `sessions_remaining >= 0` в схеме.
  3. Auto-transition пакета в `'exhausted'` синхронно в той же UoW когда decrement возвращает `sessions_remaining = 0`; эмитит один `pt_package_exhausted` once.
  4. `POST /api/v1/pt-sessions/{id}/cancel` (B-12: reception ≤24h после записи, owner anytime) атомарно: set `cancelled_at` + `cancel_reason`, increment `sessions_remaining` на parent package, если пакет был `exhausted` — переход обратно в `active`; эмитит `pt_session_cancelled`; `GET /api/v1/pt-packages/{id}/sessions` возвращает history (включая cancelled).
  5. PT-sessions полностью независимы от `visits` таблицы (Q3 default — запись session НЕ создаёт visit row, и наоборот); `pt_session_recorded` + `pt_session_cancelled` audit events проходят `LOCKED_AUDIT_EVENTS` gate; Postgres integration test PTS-TEST-01 проверяет 2 concurrent recordings против пакета с `sessions_remaining=1` → ровно один успех, другой 409.
**Plans:** TBD

### Phase 35: OpenAPI Drift Gate + admin-web Full Wiring
**Goal:** Backend контракт регенерирован байт-стабильно с типизированными путями для всех v1.4 endpoints; admin-web на `VITE_API_MODE=http` показывает обновлённый sale flow с записью оплаты, refund AlertDialog с H-13 mitigation, `/trainers` страницу, UI записи PT-сессии, и детали PT-пакета с балансом + историей; mock services синхронизированы для оффлайн-разработки.
**Depends on:** Phases 31, 32, 33, 34 (все backend endpoints + новые resources/permissions/status enums должны существовать перед codegen + UI wiring)
**Requirements:** FE-10, FE-11, FE-12, FE-13, FE-14, FE-15, FE-16, FE-17, FE-18
**Success Criteria** (what must be TRUE):
  1. Atomic single-commit регенерация: `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` экспонируют все типизированные v1.4 paths (payments, trainers, pt-package-plans, pt-packages, pt-sessions, refund endpoints на memberships и pt-packages); CI `git diff --exit-code` зелёный на оба артефакта; mirrors v1.2 Phase 21 + v1.3 Phase 28 pattern.
  2. Новые роуты: `/trainers` (owner-only `beforeLoad`), `/pt-package-plans` (owner-only), `/pt-packages` (list + `$pt_packageId` detail), `/clients/$clientId` расширен с payments-history block + active-pt-package block; sale-form на `/memberships` И `/pt-packages` включает "Получено наличными" mandatory amount input (defaulted к `plan.price_kopecks`, server-validated equality).
  3. Refund AlertDialog на `/memberships/$membershipId` и `/pt-packages/$pt_packageId` показывает client full name + plan name + `formatMoney(amount)` + sale date + free-text reason input (≤200 chars required); confirm button disabled до checkbox "Понимаю, что возврат необратим" (H-13 mitigation per B-07); PT-session UI panel на pt-package detail показывает trainer-dropdown (loads `?active=true`), datetime picker (defaulted now, ≤7d backdating для reception), notes textarea, session history с `(уволен)` suffix на inactive-trainer names.
  4. Новые shared компоненты: `PaymentBadge` (sale/refund tint через `bg-success`/`bg-warning` семантические токены) + `PtPackageStatusBadge` (4-variant discriminated union active/exhausted/expired/cancelled); 10 новых TanStack Query mutation hooks (`usePtPackageSell`/`Cancel`/`Refund`, `useMembershipRefund`, `usePtSessionRecord`/`Cancel`, `useTrainerCreate`/`Update`/`Deactivate`/`Reactivate`) — optimistic где safe, refund non-optimistic + navigate-on-success.
  5. Locked Russian i18n strings зафиксированы в `src/shared/i18n/ru.ts` для всех новых flows; three-way RBAC parity test расширен (backend `OWNER_ONLY` ↔ admin-web `can.ts` ↔ `registry.ts`) для новых resources и проходит на CI; raw Tailwind palette ESLint ban не нарушен; нет regression в существующих admin-web тестах.
**Plans:** TBD
**UI hint**: yes

### Phase 36: Milestone Verification
**Goal:** Прогнать 7+ operator human-verification сценариев против live backend + admin-web стека, выполнить race-condition Postgres integration tests, зафиксировать 6/6 CI gate evidence и operator sign-off — gate перед закрытием v1.4 milestone (mirrors v1.3 Phase 29 discipline).
**Depends on:** Phase 35 (нужен полный backend + admin-web стек на `VITE_API_MODE=http` для smoke-сценариев)
**Requirements:** VER-01, VER-02, VER-03, VER-04
**Success Criteria** (what must be TRUE):
  1. 7+ operator human-verification scenarios прогнаны против live backend + admin-web: sale-with-payment golden path; refund of fresh sale; refund attempt on frozen membership (rejected 409 `must_unfreeze_first`); PT-package sale; PT-session recording с active trainer; PT-package exhaustion mid-flow; trainer deactivation; cross-phase smoke "sell membership → freeze → refund-attempt-rejected → unfreeze → refund-succeeds"; pass/fail зафиксирован в `.planning/milestones/v1.4-VERIFICATION-LOG.md`.
  2. Race-condition Postgres integration tests все зелёные: REF-TEST-01 (concurrent refund), PTS-TEST-01 (concurrent PT-session decrement), PAY-TEST-01 (concurrent sale double-submit с одинаковым `Idempotency-Key`), AUDIT-TEST-01 (каждая state-mutating service-операция эмитит ожидаемое событие).
  3. 6/6 CI gates зелёные: backend `ruff` + `mypy --strict` + `pytest` + OpenAPI drift; frontend `pnpm typecheck` + `pnpm lint` + `pnpm test` + api-client codegen drift; evidence captured как gate logs в `milestones/v1.4-VERIFICATION-LOG.md`.
  4. Operator sign-off задокументирован в `.planning/milestones/v1.4-VERIFICATION-LOG.md` с verbatim DM / UI evidence per scenario; любые production-blocker regressions discovered fixed inline (v1.3 поймал 3 таких на этом gate); deferred items занесены в STATE.md перед milestone-close.
**Plans:** TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 30. Foundations & Tech-Debt Bedrock | 3/4 | In Progress|  |
| 31. Trainers Module | 0/? | Not started | — |
| 32. Payment Ledger + Sale Flow + Refund | 0/? | Not started | — |
| 33. PT-Package Plans + Instances | 0/? | Not started | — |
| 34. PT-Session Recording | 0/? | Not started | — |
| 35. OpenAPI Drift Gate + admin-web Full Wiring | 0/? | Not started | — |
| 36. Milestone Verification | 0/? | Not started | — |

---

*Roadmap last updated: 2026-05-14 — v1.4 milestone planning started*
*v1.0 Coverage: 47/47 v1 requirements validated*
*v1.1 Coverage: 70/70 v1 requirements validated*
*v1.2 Coverage: 63/63 v1 requirements satisfied (2 accepted-at-planning deviations carried forward as v1.3 tech-debt — both closed in Phase 24 DEBT-01/02)*
*v1.3 Coverage: 44/44 v1.3 requirements satisfied (1 mock-mode UX deferred to v1.4 — closed in Phase 30 DEBT-05)*
*v1.4 Coverage: 0/69 v1.4 requirements satisfied (69 mapped to phases, planning stage)*
