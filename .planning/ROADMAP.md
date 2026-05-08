# Roadmap: Sportzal

## Milestones

- ✅ **v1.0 Phase A: Skeleton** — Phases 1-3 (shipped 2026-05-01) — see [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 Auth + Clients** — Phases 4-14 (shipped 2026-05-07) — see [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
- ✅ **v1.2 Memberships + Visits** — Phases 15-23 (shipped 2026-05-08) — see [milestones/v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md)
- 🚧 **v1.3 Memberships Extras + Tech-Debt** — Phases 24-29 (planning, started 2026-05-08) — see [milestones/v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)

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

### 🚧 v1.3 Memberships Extras + Tech-Debt (Phases 24-29) — IN PROGRESS

- [ ] **Phase 24: Foundations & Tech-Debt Bedrock** — INFRA-15/16 + DEBT-01/02/03 (5 reqs) — `LOCKED_AUDIT_EVENTS` extension, `frozen` status CHECK, resolver `end_date >= today` filter, `?expiring=` query, SVC001 walker → auth/service.py
- [ ] **Phase 25: Memberships — Freeze (backend)** — MEM-FRZ-01..07 + EP-01..03 + AUDIT-01 + TEST-01..03 (14 reqs) — `freeze_days_limit` + `membership_freeze_periods` + freeze/unfreeze endpoints + resolver-rejects-frozen
- [ ] **Phase 26: Memberships — Renewal (backend)** — MEM-REN-01..04 + EP-01 + AUDIT-01 + TEST-01..04 (10 reqs) — `previous_membership_id` FK + `POST /renew` with current-price snapshot + resolver tiebreak
- [ ] **Phase 27: Expiring-soon Telegram Notifications** — NTF-01..06 + COPY-01 + TEST-01..03 (10 reqs) — ARQ cron 06:15 Europe/Moscow + 6 locked Russian DM templates (anti-oracle) + idempotency table
- [ ] **Phase 28: OpenAPI Drift-Gate Refresh + admin-web Wiring** — FE-10..13 (4 reqs) — regenerate `openapi.json` + `schema.d.ts`; FE freeze/renewal UI + expiring-filter on `VITE_API_MODE=http` *(UI phase)*
- [ ] **Phase 29: Milestone Verification** — DEBT-04 (1 req) — 6 human-verification smoke tests + cross-phase integration sweep + verification log

### Phase 24: Foundations & Tech-Debt Bedrock
**Goal:** Расширить audit/status taxonomy и подчистить мелкий tech-debt — чтобы все последующие phases (25/26/27) могли эмитить новые locked события и полагаться на исправленный резолвер.
**Depends on:** Nothing (first phase of v1.3 milestone; builds on v1.2 Phase 15 foundations)
**Requirements:** INFRA-15, INFRA-16, DEBT-01, DEBT-02, DEBT-03
**Success Criteria** (what must be TRUE):
  1. `LOCKED_AUDIT_EVENTS` frozenset содержит 6 новых пар (`membership_frozen`, `membership_unfrozen`, `membership_renewed`, `expiring_notification_sent_{7d,3d,1d}`); `audit.emit` AST literal-string gate всё ещё блокирует ad-hoc строки.
  2. `Membership.status` CHECK constraint допускает `'frozen'`; `MEMBERSHIP_STATUS_TRANSITIONS` константа в `app/modules/memberships/constants.py` декларативно описывает разрешённые переходы; invalid transitions возвращают 409 `invalid_transition`.
  3. `resolve_active_membership_by_client` фильтрует `end_date >= today (Europe/Moscow)` — пропущенный ARQ tick не позволяет check-in на просроченном membership; integration test это подтверждает.
  4. `GET /api/v1/memberships?expiring=true&within=N` (1..30, default 7) возвращает только active memberships, истекающие в окне; mock service реализует identical filter (mock/http parity).
  5. `BusinessService` SVC001 AST walker применяется к `app/modules/auth/service.py`; `authenticate` + `classify_verify_error` либо явно `await session.commit()`, либо несут `# noqa: SVC001 caller-owns-txn` с обоснованием; CI gate ловит регрессии.
**Plans:** 2/5 plans executed
  - [x] 24-01-PLAN.md — Extend LOCKED_AUDIT_EVENTS with 6 v1.3 pairs (INFRA-15)
  - [x] 24-02-PLAN.md — Migration 0007_status_taxonomy + MEMBERSHIP_STATUS_TRANSITIONS + central transition guard (INFRA-16)
  - [ ] 24-03-PLAN.md — Resolver end_date >= today filter (DEBT-01)
  - [ ] 24-04-PLAN.md — ?expiring=true&within=N backend + mock/http parity (DEBT-02)
  - [ ] 24-05-PLAN.md — SVC001 walker → auth/service.py + commit-on-write fix (DEBT-03)

### Phase 25: Memberships — Freeze (backend)
**Goal:** Reception/owner может бесплатно заморозить и разморозить membership; `end_date` сдвигается на использованные дни; resolver не отдаёт frozen membership; cancel-during-freeze работает корректно.
**Depends on:** Phase 24 (нужен `'frozen'` в CHECK + новые audit events + резолвер с `end_date >= today` фильтром)
**Requirements:** MEM-FRZ-01, MEM-FRZ-02, MEM-FRZ-03, MEM-FRZ-04, MEM-FRZ-05, MEM-FRZ-06, MEM-FRZ-07, MEM-FRZ-EP-01, MEM-FRZ-EP-02, MEM-FRZ-EP-03, MEM-FRZ-AUDIT-01, MEM-FRZ-TEST-01, MEM-FRZ-TEST-02, MEM-FRZ-TEST-03
**Success Criteria** (what must be TRUE):
  1. Миграция `0008_freeze.py` добавляет `freeze_days_limit` (immutable post-creation) в `membership_plans`, `freeze_days_limit_snapshot` в `memberships`, и таблицу `membership_freeze_periods` с partial unique index `WHERE ended_at IS NULL`.
  2. `POST /api/v1/memberships/{id}/freeze` (CSRF, reception+owner) переводит active → frozen и открывает freeze period; `POST /api/v1/memberships/{id}/unfreeze` закрывает period, сдвигает `end_date += use_days` (half-day rounds up), переводит frozen → active.
  3. Membership detail responses включают `freezeDaysLimitSnapshot`, `freezeDaysUsed`, `freezeDaysRemaining`, `currentFreezePeriod` (object | null).
  4. Frozen membership не проходит check-in (reception + Telegram `/checkin` оба возвращают `no_active_membership` 409 без oracle-leak); cancel from frozen разрешён только owner-у и закрывает freeze period без extension; cumulative days > limit → 409 `freeze_limit_exceeded`; concurrent freeze → 409 `already_frozen`.
  5. Каждое freeze/unfreeze эмитит `audit.emit("membership_frozen"|"membership_unfrozen", ...)`; integration tests покрывают full freeze cycle, limit-exceeded, и race на одновременный freeze.
**Plans:** TBD

### Phase 26: Memberships — Renewal (backend)
**Goal:** Reception/owner может продлить membership одной кнопкой — backend создаёт follow-up row со snapshot текущей цены плана, резолвер корректно отдаёт текущий membership пока он жив и переключается на renewal только после `end_date`.
**Depends on:** Phase 24 (`membership_renewed` в `LOCKED_AUDIT_EVENTS`); Phase 25 (общая миграция `0008` либо combined revision, либо последовательное extension; renewal принимает `frozen` source)
**Requirements:** MEM-REN-01, MEM-REN-02, MEM-REN-03, MEM-REN-04, MEM-REN-EP-01, MEM-REN-AUDIT-01, MEM-REN-TEST-01, MEM-REN-TEST-02, MEM-REN-TEST-03, MEM-REN-TEST-04
**Success Criteria** (what must be TRUE):
  1. Миграция `0008` добавляет `previous_membership_id` (UUID NULL FK memberships.id ON DELETE SET NULL) — audit-цепочка для renewal.
  2. `POST /api/v1/memberships/{id}/renew` (CSRF, reception+owner) создаёт follow-up membership со snapshot **текущей** цены плана; разрешённые source-статусы — `active`, `frozen`, `expired`; cancelled source → 409 `cannot_renew_cancelled`; archived plan → 409 `plan_archived`.
  3. Дата старта: для active/frozen source — `start_date = source.end_date + 1` (Europe/Moscow); для expired source — `start_date = today` (новый membership начинается сразу, не ретроактивно); audit payload содержит `start_date_strategy`.
  4. Resolver tiebreak: при нескольких active membershipах с `end_date >= today` приоритет у того, у кого меньший `start_date` (текущий running), затем `created_at DESC`; check-in использует current до `end_date`, потом естественно переключается на renewal.
  5. `audit.emit("membership_renewed", actor, source_membership_id, new_membership_id, source_plan_id, current_price_kopecks, start_date_strategy)` на каждый renewal; integration tests покрывают active-renewal, price-changed-between-sale-and-renewal, expired-source-from-today, и rejection paths.
**Plans:** TBD

### Phase 27: Expiring-soon Telegram Notifications
**Goal:** Клиент с привязанным Telegram получает анти-oracle DM за 7/3/1 день до истечения membership; cron идемпотентен, не задваивает после рестарта, не шлёт frozen/cancelled/expired/unlinked.
**Depends on:** Phases 24 (locked audit events `expiring_notification_sent_{7d,3d,1d}` в фрозенсете), 25 (frozen status существует и фильтруется), 26 (миграция `0009` идёт после `0008`)
**Requirements:** NTF-01, NTF-02, NTF-03, NTF-04, NTF-05, NTF-06, NTF-COPY-01, NTF-TEST-01, NTF-TEST-02, NTF-TEST-03
**Success Criteria** (what must be TRUE):
  1. Миграция `0009_notifications.py` создаёт `membership_notifications` с UNIQUE INDEX на `(membership_id, kind)` — single source of truth для cron-идемпотентности.
  2. ARQ cron `send_expiring_notifications` (06:15 Europe/Moscow, container `TZ=UTC`, `cron(hour=3, minute=15, unique=True, keep_result=60)`) выбирает active memberships с `end_date IN (today+1, today+3, today+7)`, привязанным Telegram, и без существующей matching `membership_notifications` row; запускается **после** `expire_memberships` (06:05 → 06:15 ordering сохраняется через WorkerSettings.cron_jobs).
  3. Frozen, cancelled, expired memberships, и клиенты без `telegram_chat_id` или с `clients.deleted_at IS NOT NULL` пропускаются на уровне SQL select; 6 locked Russian DM templates (`EXPIRING_{7,3,1}D_VARIANT_{A,B}`, выбор по `client_id` hash, anti-oracle pattern из v1.2 D-5) загружены в `app/integrations/telegram/copy.py` с owner sign-off, занесённым в PROJECT.md Key Decisions.
  4. На каждую успешную отправку — INSERT `membership_notifications` row + `audit.emit("expiring_notification_sent_<kind>", actor=None, ...)`; ошибки send (403 bot blocked, network) логируются как WARNING, row НЕ вставляется → next tick retries; 403 не марает kind permanently (re-linked клиент получит будущие пинги).
  5. Integration tests покрывают: 7d-перед-истечением + linked Telegram → DM sent + idempotent на повторный run, frozen-membership-NOT-notified, send-403-then-retry-success.
**Plans:** TBD

### Phase 28: OpenAPI Drift-Gate Refresh + admin-web Wiring
**Goal:** Backend контракт регенерирован байт-стабильно; admin-web на `VITE_API_MODE=http` показывает freeze/renewal UI и expiring-filter с реальным backend, mock-сервисы синхронизированы для оффлайн-разработки.
**Depends on:** Phases 25, 26, 27 (все backend endpoints + status `frozen` + `expiringWithin` query param должны существовать перед codegen + UI wiring)
**Requirements:** FE-10, FE-11, FE-12, FE-13
**Success Criteria** (what must be TRUE):
  1. `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` регенерированы; CI `git diff --exit-code` зелёный на оба артефакта; новые типизированные пути включают freeze/unfreeze/renew + `expiring=` query (зеркалирует pattern v1.2 Phase 21).
  2. `/memberships/$membershipId` показывает кнопки "Заморозить"/"Снять заморозку" (`(CREATE, MEMBERSHIPS)`-gated, оба роли); freeze-кнопка disabled при `freezeDaysRemaining === 0` с tooltip; frozen-state badge с датами текущего period; cancel-during-freeze остаётся owner-only.
  3. `/memberships` list + `/clients/$clientId` overview показывают `frozen` как отдельный статус (не active/expired/cancelled); фильтр/сортировка учитывают; mock service синхронизирован.
  4. "Продлить" кнопка на membership detail показывает confirm dialog с current plan price (server-fetched, kopecks → ru-RU RUB через `formatMoney`) и computed `start_date`/`end_date`; optimistic mutation с rollback; success → toast + navigate на renewed membership.
  5. `/memberships?expiring=true&within=N` фильтр работает на `VITE_API_MODE=http` (DEBT-02 закрыт); FE-08 D-2 cheap-win больше не mock-only; mock service реализует identical filter для symmetric mock/http behaviour.
**Plans:** TBD
**UI hint**: yes

### Phase 29: Milestone Verification
**Goal:** Закрыть DEBT-04 (6 human_verification сценариев из v1.2 Phase 22) против live backend + Telegram sandbox, прогнать cross-phase integration sweep по freeze + renewal + expiring-cron, и зафиксировать verification log.
**Depends on:** Phase 28 (нужен полный backend + admin-web стек на `VITE_API_MODE=http` для smoke-сценариев)
**Requirements:** DEBT-04
**Success Criteria** (what must be TRUE):
  1. Все 6 interactive smoke tests из `.planning/milestones/v1.2-phases/22-VERIFICATION.md` `human_verification:` block прогнаны против live backend + Telegram sandbox; pass/fail зафиксирован в `.planning/milestones/v1.3-VERIFICATION-LOG.md`.
  2. Cross-phase smoke сценарий "freeze → renewal → expiring-soon" работает end-to-end: продаём membership → замораживаем на 5 дней → размораживаем → продлеваем → дожидаемся 06:15 cron → 7d/3d/1d DM приходят на Telegram sandbox; ни один шаг не падает.
  3. Backend test suite зелёный (≥600 tests), admin-web suite зелёный (≥190 tests), все CI gates (ruff + mypy strict + import-linter + eslint + drift-gate) зелёные.
  4. Verification report подшит в `.planning/milestones/v1.3-MILESTONE-AUDIT.md` (или эквивалентный артефакт от `/gsd-complete-milestone`); выявленные регрессии закрыты или явно перенесены в v1.4 deferred items.
**Plans:** TBD

Full details: [milestones/v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)

---

*Roadmap last updated: 2026-05-08 — v1.3 milestone planning started*
*v1.0 Coverage: 47/47 v1 requirements validated*
*v1.1 Coverage: 70/70 v1 requirements validated*
*v1.2 Coverage: 63/63 v1 requirements satisfied (2 accepted-at-planning deviations carried forward as v1.3 tech-debt)*
*v1.3 Coverage: 0/44 v1.3 requirements satisfied (44 mapped to phases, planning phase)*
