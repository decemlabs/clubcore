# Sportzal

## What This Is

Sportzal — CRM для тренажёрного зала. Пет-проект на один зал: управление клиентами, абонементами, посещениями, расписанием, бронированиями, тренерами, биллингом и уведомлениями. Под рынок РФ/СНГ.

**Текущее состояние (после v1.3 — Memberships Extras + Tech-Debt):**
- **Frontend** — admin-панель на React 19 (Vite + TanStack Router) в `apps/admin-web/` (~18.8K LOC TS). Через `VITE_API_MODE=http` swap-seam идут: `/login`, `/clients/*`, `/memberships` (теперь с freeze/renewal flow + «Заморожен» filter pill + «Истекает в течение» within-days selector), `/memberships/$membershipId` (плоский detail route с `FreezeSection` + `RenewSection` + `RenewConfirmDialog`), `/membership-plans` (owner-only, `freeze_days_limit` immutable post-creation), `/visits` (reception check-in с FE-08 a..d edge cases), `/clients/$clientId` (Pattern α: Promise.all loader + ESLint-enforced cross-feature isolation), `/profile` (active sessions UI, http-only по D-22-2). Остальные домены продолжают идти через моки. Shared `StatusBadge` (4-value variant с frozen warning token), 3 TanStack Query mutation hooks (freeze/unfreeze optimistic, renew non-optimistic + navigate). 233 admin-web tests.
- **Backend** — модульный монолит на FastAPI в `apps/backend/app/` (~9.9K LOC Python, +1.8K vs v1.2). Реальные endpoints: `/healthz` + полный `/api/v1/auth/*` + `/api/v1/clients` (list/get/create/patch/delete) + `/api/v1/membership-plans` (5 endpoints, owner-only, теперь с `freezeDaysLimit`) + `/api/v1/memberships` (list/get/sell/cancel + **freeze + unfreeze + renew + `?expiring=true&within=N`**) + `/api/v1/visits` (list/get/check-in + `/_meta` gym-hours). RBAC байт-паритетен с frontend `can.ts` (`OWNER_ONLY` 15 entries; reception сохраняет `(CREATE, MEMBERSHIPS)` для freeze/unfreeze/renew) через `Depends(require_permission)` + introspection guard. Архитектурные контракты держатся `import-linter`-ом; cross-module callbacks (`ActiveMembershipResolver` Protocol, `register_user_loader`, `HandlerContext`) проходят через composition root `app/main.py`. 729 backend tests (включая 16-cell freeze state-machine matrix + ceil rounding + race-on-active-freeze + renewal date strategy + cron idempotency). SVC001 AST commit-gate теперь покрывает `app/modules/auth/service.py` (`authenticate` явно коммитит audit-rows).
- **Auth** — двухканальный: email/password (Argon2id, 12-char min, NIST 800-63B; v1.2 HYG-01/02 закрыли 500 → 401 на verify-error и tampered cookie) + Telegram OTP (отдельный `python -m app.workers.telegram_bot` long-polling worker; в v1.3 расширен `client_by_telegram` + `active_membership` resolver registrations для бота). JWT HS256 access + refresh-rotation family с reuse-window race tolerance в Redis-mirrored sessions. Per-family revoke + logout-all. CSRF на каждом mutating endpoint.
- **Memberships + Visits + Freeze + Renewal + Expiring-soon** — `MembershipPlan` каталог теперь с `freeze_days_limit` (immutable post-creation, как `duration_days`); `Membership` с **inclusive `end_date`** + mandatory snapshot pricing + `freeze_days_limit_snapshot` + self-FK `previous_membership_id` для renewal-цепочки; `membership_freeze_periods` с partial unique `WHERE ended_at IS NULL` (concurrent freeze loses at DB layer); resolver tiebreak `start_date ASC, created_at DESC` так что check-in держится за running membership пока тот живёт, потом естественно переходит на renewal; resolver отвергает `frozen` (anti-oracle DM); status transitions через центральный `_assert_can_transition` + декларативный `MEMBERSHIP_STATUS_TRANSITIONS` constant; 2 ARQ cron'а: `expire_memberships` 06:05 + `send_expiring_notifications` 06:15 Europe/Moscow (10-min buffer, `unique=True`), idempotency через UNIQUE `(membership_id, kind)` на `membership_notifications`; 6 locked Russian DM templates `EXPIRING_{7D,3D,1D}_VARIANT_{A,B}` с per-client variant (`client_id.bytes[0] & 1`, anti-oracle); `Visit` всё ещё на **DB-level race-proof** `gym_date STORED` + `UNIQUE (client_id, gym_date)`; Telegram `/checkin` + 4 owner-locked Russian DM strings.
- **Persistence** — Postgres 16 (теперь 10 бизнес-таблиц: `users`, `refresh_tokens`, `otp_codes`, `clients`, `audit_log`, `membership_plans`, `memberships`, `visits`, `membership_freeze_periods`, `membership_notifications`); Alembic миграции 0001–0009 применены (v1.3 добавил 0007/0008 freeze + renewal + 0009 expiring notifications). Indexes: `pg_trgm` GIN на clients search, partial unique на soft-deleted phones, `(client_id, status, end_date DESC)` для resolver, `(client_id, gym_date)` UNIQUE для visits, partial unique `(membership_id) WHERE ended_at IS NULL` для freeze period, UNIQUE `(membership_id, kind)` для notification idempotency.
- **Dev infrastructure** — `docker compose up` поднимает backend + Postgres 16 + Redis 7 + Telegram bot worker + ARQ worker (5-й сервис) + одноразовый migrate. `apps/backend/scripts/run_expiring_cron_once.py` — one-shot operator runner для verification (TM-29-02/03 gated). CI workflow `.github/workflows/ci.yml` гонит 6 параллельных gates: backend (`ruff`, `mypy --strict`, `pytest`, `openapi.json` drift-gate) + frontend (`typecheck`, `lint`, `test`, `pnpm --filter @sportzal/api-client codegen` drift-gate). `LOCKED_AUDIT_EVENTS` теперь 34-entry frozenset (28 v1.2 + 6 v1.3) с `audit.emit` AST literal-string gate.

## Core Value

Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.

## Current State

**v1.5 Schedule + Bookings (PT slots) — shipped 2026-05-18** (4 phases, 20 plans, 57/57 v1.5 requirements satisfied; +35,957 / -322 lines across 150 files in the milestone diff; 18 days end-to-end). Backend now closes the last empty business-module gap: trainer availability slots can be published and listed; clients can be booked into slots via reception, owner, or Telegram bot `/book` with anti-oracle InlineKeyboard flow; race-safe partial UNIQUE `(slot_id) WHERE status='confirmed'` on `bookings` makes Postgres the race arbiter; booking FSM `confirmed → cancelled / no_show / completed` is centrally guarded; PT-session recording with `booking_id` atomically completes the booking; 5 new LOCKED audit events bring the frozenset from 51 → 56. New helpers: `bookings_service.create_booking_via_bot` self-service entry (Alembic 0021 makes `bookings.created_by_user_id` NULLABLE so bot bookings carry NULL actor + `actor_role='telegram_bot'` Literal in audit payload); `_dedupe_update_id` module-level Redis dedup helper extracted from `checkin_handler`; `SlotResponse` + `BookingResponse` JOIN-projected with `trainer_full_name` + `slot_start_time` so the callback handler renders the confirmation DM directly without a secondary lookup. ARQ adds 2 new cron jobs — `mark_no_show_bookings` (23:10 MSK, DB-only batch UPDATE on overdue confirmed bookings) and `send_booking_reminders` (06:35 MSK, multi-session DM loop with `booking_notifications` idempotency table preventing double-pings across container restarts). OpenAPI artifact regenerated byte-stably: `openapi.json` grew 5479 → 6775 lines, `schema.d.ts` 4086 → 5017 lines; `schema.contract.test.ts` gains +11 `AssertNonNever` forward-guards (count 50 → 61) plus a runtime `_v15Checks.length === 11` assertion. 4 locked Russian DM templates for booking flow (`BOOKING_CONFIRMED_DM`, `BOOKING_CANCELLED_BY_CLIENT_DM`, `BOOKING_CANCELLED_BY_OWNER_DM`, `BOOKING_REMINDER_24H_DM`) + 1 anti-oracle constant (`_BOT_BOOK_DENIED_DM`) live in `app/modules/bookings/notifications.py` (D-39-02 chose module-scope over shared telegram copy).

Phase 40 milestone verification — minimal live-Postgres proof (`scripts/verify_40_create_booking_via_bot.py`) confirmed all 6 invariants of the new Phase 40 surface against a docker-compose stack on 2026-05-18: `create_booking_via_bot` returns `confirmed` BookingResponse, `bookings.created_by_user_id IS NULL` (Alembic 0021), BookingResponse carries `trainer_full_name` + `slot_start_time` (BLOCKER-2 JOIN), audit row has `actor_role='telegram_bot'` (D-40-05) AND `actor_user_id IS NULL` (WARNING-1). Full 10-scenario operator runbook (6 curl + 2 Telegram sandbox + 2 cron + 5 CI gate URLs) deferred to v1.9 as **DEFER-40-01** — the runbook script (`v1.5-verification-evidence/run.sh`) needed 4 hotfixes during the verification attempt (Alembic revision-id length overflow → 32-char limit; `/healthz` vs `/health` URL; `trainer_availability_slots` vs `trainer_slots` table name; `verify_*@local.dev` vs `@fixture.local` login defaults), and the remaining bugs (wrong RBAC actor on POST /trainer-slots; missing X-CSRF-Token header) cluster around the runbook scaffolding, not the Phase 40 code itself.

Cumulative shipped versions: v1.0 (Skeleton, 47/47), v1.1 (Auth + Clients, 70/70), v1.2 (Memberships + Visits, 63/63), v1.3 (Memberships Extras + Tech-Debt, 44/44), v1.4 (Cash Sales + PT Packages, 61/61), v1.5 (Schedule + Bookings, 57/57). See `MILESTONES.md` for full history and `.planning/milestones/v1.X-ROADMAP.md` for per-milestone phase breakdowns.

**Business-module completeness (against original 8-domain CRM scope):**

| Domain | State | Notes |
|---|---|---|
| Auth | ✅ full | email/password + Telegram OTP + RBAC + active sessions |
| Clients | ✅ full | CRUD + search + soft-delete + audit |
| Memberships | ✅ full | plans + instances + freeze + renewal + auto-expire + expiring-soon DM |
| Visits | ✅ full | reception + bot self-checkin + DB race-safe 1/day |
| Schedule + Bookings | ✅ full | trainer slots + race-safe bookings (PT slots) + FSM + Telegram `/book` + 23:10 no-show cron + 06:35 reminder cron |
| Trainers | 🟡 catalog only | no schedule/payroll yet |
| Billing | 🟡 cash only | no online payments / 54-ФЗ — v1.7 |
| Notifications | 🟡 Telegram only | no email channel — v1.6 |

Reports + Audit Log read API: write-side complete (51 LOCKED events), read-side scheduled for v1.8.

## Next Milestone Goals

**v1.6 Email channel + Multi-user admin (next)** — добавить email как второй канал уведомлений (Resend / SES / Mailgun — выбор TBD на спек-фазе) и закрыть последний промежуток operator-onboarding. Email-каналы покроют OTP fallback, expiring-soon, payment-receipt notifications, booking confirmations + reminders (parallel-friendly с уже existing Telegram-каналом). Multi-user admin — `POST /api/v1/users` (owner-only) для онбординга reception-аккаунтов без прямого ковыряния в БД + soft-delete/deactivate + multi-user audit traceability. Это последняя infra-фаза перед online-платежами (v1.7) и API-handoff'ом (v1.9).

Постлинейка milestone'ов осталась без изменений после v1.5 close:

| Milestone | Focus |
|---|---|
| **v1.6 — Email channel + Multi-user admin (next)** | Email integration (Resend / SES / Mailgun — TBD) как второй канал уведомлений; шаблоны для OTP / expiring / payment-receipt / booking confirm/remind; owner-managed `POST /api/v1/users` чтобы reception-аккаунты онбордились без БД-инвазивности; soft-delete + deactivate; multi-user audit |
| **v1.7 — Online Payments (ЮKassa) + 54-ФЗ fiscal receipts** | ЮKassa payment intake (memberships + PT-packages) + webhook state machine + online refunds; ЮKassa `/receipts` integration (АТОЛ-Онлайн / Чек.ОФД path) для 54-ФЗ-compliant фискальных чеков на email/SMS клиенту. **Bundled** — online sales по РФ нельзя запускать без фискальных чеков |
| **v1.8 — Reports + Audit Log read API** | Owner-dashboard backend: revenue by day/month, active/expiring clients, top trainers, PT-session usage; `GET /api/v1/audit-log` с owner-only RBAC + фильтры (actor / resource / time-window / event-kind) |
| **v1.9 — API Handoff + Production Hardening** | (was v1.5) Curated Postman v2.1 collection + Newman CLI runner; auth runbook expansion; OpenAPI doc site + versioned spec URL; `@sportzal/api-client` publish to npm; OpenAPI tag curation + explicit `operation_id=`; idempotency hardening (CR-01/02/02b carry-over from Phase 33); residual DEFER-36-04-A (11 failures) + DEFER-36-04-B (ruff format 123 files); **DEFER-40-01 full v1.5 operator runbook execution + run.sh hardening**; doc-debt sweep |
| **v2.0 — Frontend Integration + Launch** | Design team integrates production admin + client apps against the frozen v1.9 contract; integration tests at the seam (live backend + real frontends); coexistence with frozen `apps/admin-web` (mock reference); launch checklist + production deploy story |

После v1.9 контракт замораживается. v2.0 — финальная интеграция и запуск.

<details>
<summary>Previous milestone scope (v1.4 — shipped 2026-05-16)</summary>

**Goal:** Закрыть критический MVP-gap "симуляция продажи без денег" + добавить персональные тренировки как новый тип услуги, чтобы зал реально мог принимать клиентов на двух тарифах (месячный абонемент и ПТ-пакет) с настоящим учётом наличных и возвратов. Стратегический pivot 2026-05-15: дизайн-команда взяла оба фронтенда; v1.4 поставляется как backend-complete + API handoff.

Target features (all delivered):
- **Payment ledger (наличные)** — append-only `payments` table; CHECK signed-amount/subject correlation; partial UNIQUE on `refund_of`; `Idempotency-Key` mandatory on sales; per-client + per-membership + owner-only listing endpoints.
- **Refund flow (B-07 uniform reception)** — `POST /memberships/{id}/refund` and `POST /pt-packages/{id}/refund` reception+owner; full-only refund (B-02 deferred to v1.5+); 409 `must_unfreeze_first` (B-08) + 409 `cannot_refund_renewed_source` (B-09); atomic audit chain `payment_recorded → refund_issued → payment_refunded → membership_refunded` with `payment_row_hash` SHA-256 traceability.
- **PT-package (новый тариф)** — `pt_package_plans` + `pt_packages` instances; immutable plan fields; mandatory snapshot suite; partial UNIQUE `(client_id) WHERE status='active'`; sale orchestrator consumes payment_recorder Protocol slot; cancel-without-refund + refund; `expire_pt_packages` ARQ cron 06:25 MSK.
- **Trainers catalog (owner-only)** — `0011_trainers` migration; CRUD with soft-delete via `is_active`; reception sees `?active=true` for PT-session picker; double-wired Protocol slot resolver (REG-29-03 lesson preserved).
- **PT-session recording (race-safe)** — `0015_pt_sessions` with `trainer_name_snapshot NOT NULL` (B-05); single-SQL atomic decrement with auto-`exhausted` transition; reception ≤7d / owner unlimited backdating (B-11); reception ≤24h cancel / owner anytime (B-12) with predicate-gated reverse `exhausted → active` transition.
- **OpenAPI handoff** — atomic byte-stable regen of `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts`; 36 compile-time `AssertNonNever` forward-guards; README v1.4 changelog + auth quick-start; `.planning/handoff/v1.4-postman.json` (55-endpoint draft) + `.planning/handoff/v1.4-auth-runbook.md` (5 sections) — v1.5 will curate.
- **Milestone verification (Phase 36 as gate)** — 8 operator scenarios + 20 race tests + 4 backend CI gates + admin-web canary; 5 inline regressions at the D-36-17 cap; 44 pre-existing pytest failures rolled to DEFER-36-04-A.

Audit: `.planning/milestones/v1.4-VERIFICATION-LOG.md` (operator sign-off recorded with delegation disclosure under user's `сделай это сам` authorization).

</details>

<details>
<summary>Previous milestone scope (v1.3 — shipped 2026-05-14)</summary>

**Goal:** Доращиваем memberships до полноценной фичи (freeze, expiring-soon notifications, renewal) и закрываем 4 переноса из v1.2 — без новых внешних интеграций.

Target features (all delivered):
- **Freeze (заморозка)** — `freeze_days_limit` per-plan (immutable, как `duration_days`); reception/owner ставит и снимает; `end_date` сдвигается на использованные дни (ceil rounding); `frozen` status; resolver отвергает; cancel-during-freeze разрешён (owner) с двойным audit `membership_unfrozen` + `membership_cancelled`; partial unique на open period.
- **Expiring-soon Telegram** — эскалация 7+3+1; ARQ daily cron 06:15 MSK; idempotency через UNIQUE `(membership_id, kind)`; 6 locked Russian templates (2 варианта × 3 окна) с per-client variant выбором; skip для frozen / unlinked / soft-deleted.
- **Renewal** — `POST /memberships/{id}/renew`; current-price snapshot; `previous_membership_id` FK; resolver tiebreak `start_date ASC`; expired-source → `start_date = today`; archived plan → 409.
- **Tech-debt** — все 4 closed (DEBT-01/02/03 в Phase 24; DEBT-04 в Phase 29).

</details>

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

<!-- v1.3 Memberships Extras + Tech-Debt (validated 2026-05-14): -->

- ✓ Foundations & tech-debt bedrock — `LOCKED_AUDIT_EVENTS` extended to 34-entry frozenset (6 v1.3 pairs: `membership_frozen`/`unfrozen`/`renewed` + `expiring_notification_sent_{7d,3d,1d}`); `Membership.status` CHECK admits `'frozen'` + declarative `MEMBERSHIP_STATUS_TRANSITIONS` constant + central `_assert_can_transition` guard; resolver `end_date >= today (Europe/Moscow)` defence-in-depth filter (MEM-04 D-13 closed); backend `GET /api/v1/memberships?expiring=true&within=N` (1..30, default 7) with mock/http parity (WR-07 closed); SVC001 AST commit-gate extended to `app/modules/auth/service.py` (`authenticate` explicitly commits audit-rows) — v1.3 (Phase 24)
- ✓ Memberships — Freeze: `freeze_days_limit` (INT NOT NULL CHECK > 0, immutable post-creation) on plans + `freeze_days_limit_snapshot` on memberships (mandatory snapshot semantics from v1.2); `membership_freeze_periods` table with partial unique `(membership_id) WHERE ended_at IS NULL` (concurrent freezes lose at DB layer); `freeze_membership` / `unfreeze_membership` / `cancel_membership` frozen extension with caller-owns-txn repository helpers + ceil-rounded day accounting (client never loses partial days); 2 new POST endpoints `/freeze` and `/unfreeze` with `(CREATE, MEMBERSHIPS)` RBAC + CSRF (both roles); resolver rejects `frozen` (no oracle leak — same DM as stranger / expired); 16-cell state-machine matrix + 6 integration tests covering happy path, limit exhaustion, race, cancel-during-freeze — v1.3 (Phase 25)
- ✓ Memberships — Renewal: self-FK `previous_membership_id` for audit chain; `renew_membership` snapshots from **current** plan price/duration/freeze-limit (rejects archived plans with 409 `plan_archived`); `start_date = source.end_date + 1` for active/frozen sources, but `start_date = today` for expired sources with audit payload `start_date_strategy='from_today_expired_source'`; resolver tiebreak inverted to `start_date ASC, created_at DESC` so check-in keeps using the running membership until its `end_date`, then renewal naturally takes over; `POST /memberships/{id}/renew` returns 201 with `previousMembershipId`; 4 integration tests lock snapshot semantics, price change, archived-plan, expired-source date strategy — v1.3 (Phase 26)
- ✓ Expiring-soon Telegram notifications: `membership_notifications` table with UNIQUE `(membership_id, kind)` for cron idempotency (no double-pings even across docker-restart races); 5th ARQ cron `send_expiring_notifications` at 06:15 Europe/Moscow (`hour=3, minute=15, unique=True, keep_result=60`), 10-min buffer after `expire_memberships`; selects active memberships with `end_date IN (today+1, today+3, today+7)` and linked Telegram, sends DM via `build_bot` factory, inserts idempotency row only on successful send (403/blocked → WARNING log, retry next tick); 6 locked Russian DM templates `EXPIRING_{7D,3D,1D}_VARIANT_{A,B}` with per-client variant selected by `client_id.bytes[0] & 1` (anti-oracle); owner sign-off auto-recorded as `D-27-OWNER-COPY-LOCK` under `workflow.auto_advance` — v1.3 (Phase 27)
- ✓ OpenAPI drift gate refresh + admin-web freeze/renewal/expiring UI: single atomic regen produces byte-stable `openapi.json` (3151 lines) + `schema.d.ts` (2291 lines) exposing typed `/memberships/{id}/freeze`, `/unfreeze`, `/renew` + `expiring?: boolean` + `within?: number` + `MembershipStatus` 4-value union including `frozen`; admin-web entity types + mock service (17 parity tests) + HTTP service forwarding `status`/`within`; 3 TanStack Query mutation hooks (freeze/unfreeze optimistic with rollback; renew non-optimistic + navigate); `/memberships/$membershipId` flat detail route with `FreezeSection` (button states + tooltip at limit + frozen badge using semantic `bg-warning` token) + `RenewSection` + `RenewConfirmDialog` (server-fetched price via `formatMoney`, computed dates); shared `StatusBadge` (4 variants) wired into list page + clients overview; «Заморожен» filter pill + «Истекает в течение» within-days selector (`{1, 3, 7, 14, 30}`, Zod-clamped) on `/memberships`; 24 locked Russian i18n strings — v1.3 (Phase 28; 1 mock-mode `?status=` filter parity gap deferred to v1.4)
- ✓ Milestone verification: 7/7 inherited DEBT-04 human-verification scenarios from v1.2 22-VERIFICATION (5 reception + bot + cross-phase freeze→renewal→expiring-cron sweep) executed against live backend + Telegram sandbox; 729 backend tests + 233 admin-web tests + 6/6 CI gates captured as evidence; 3 production-blocker regressions discovered and fixed inline (REG-29-01 Vite dev-proxy for admin-web http mode, fix `aea55f3`; REG-29-03 telegram bot worker missing `client_by_telegram`/`active_membership` resolver registrations, fix `f3cd01f`; REG-29-04 one-shot cron runner missing eager ORM-model import, fix `1dfc7a8`); operator sign-off with verbatim DM evidence in `milestones/v1.3-VERIFICATION-LOG.md`; 1 minor mock-mode UX gap deferred to v1.4 — v1.3 (Phase 29)

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

### Active (v1.5 — Schedule + Bookings, PT slots)

See `.planning/REQUIREMENTS.md` for the locked REQ-IDs. Themes:
- **Trainer availability** — `trainer_availability_slots` table with one-off and/or recurring slot semantics; owner-managed CRUD (optionally trainer self-service); capacity fixed at 1 (PT-individual)
- **Bookings (race-safe)** — `bookings` table with partial UNIQUE `(slot_id) WHERE status='confirmed'`; FSM `confirmed → cancelled / no_show / completed`; reception ≤24h cancel / owner anytime
- **PT-package linkage** — booking requires active PT-package with `sessions_remaining > 0`; session decrement remains atomic on PT-session creation, not on booking; `booking_id` becomes optional FK on `pt_sessions`
- **Telegram bot `/book`** — client self-service when linked + has active PT-package
- **Audit chain** — 5 new LOCKED events (`slot_published`, `booking_created`, `booking_cancelled`, `booking_no_show`, `booking_completed`); frozenset grows 51 → 56

### Out of scope for v1.5 (explicit)

- **Group classes / capacity > 1** — Sportzal runs an open-gym model for non-PT; if group classes become a real requirement they will be a later milestone, not a v1.5 sub-scope
- **Online payment at booking time** — booking does not charge money; payment for the underlying PT-package is still cash via v1.4 flow (online path lands in v1.7)
- **Trainer payroll / commission per session** — out of scope until at least v1.8
- **Booking reminders by email** — depends on v1.6 email channel; Telegram reminders may land within v1.5 if cheap

### Out of Scope

<!-- Зафиксировано пользователем явно. Не возвращать без явного запроса. -->

- Multi-tenancy (ContextVar/`tenant_id`/RLS/`SET LOCAL`) — пет-проект на 1 зал; добавим только когда появится второй покупатель
- **Stripe** — недоступен в РФ, не использовать никогда в этом проекте
- **Production frontend code** (admin + client apps) — оба фронтенда разрабатываются дизайн-командой **отдельно от этого репозитория** (pivot 2026-05-15). Backend публикует контракт через OpenAPI / `schema.d.ts` / Postman collection (v1.5 API Handoff milestone) и интегрируется с готовыми фронтендами в v2.0 Frontend Integration milestone. `apps/admin-web` остаётся как mock-mode contract reference и не считается production target
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
- **Текущий codebase (после v1.3):** ~9.9K LOC Python в `apps/backend/app/` (4 бизнес-модуля: auth, clients, memberships, visits); 729 backend tests (unit + integration с pytest-asyncio + httpx ASGITransport + SAVEPOINT-based per-test isolation, plus VIS-TEST-01 real-Postgres concurrent race test, ARQ-TEST-01/02 cron correctness + idempotency, 16-cell freeze state-machine matrix, expiring-soon idempotency tests); admin-web ~18.8K LOC TS (233 tests); 6 docker-compose services (`web`, `migrate`, `postgres`, `redis`, `telegram-bot`, `arq-worker`); 10 бизнес-таблиц in Postgres.
- **CI:** `.github/workflows/ci.yml` гонит backend (`uv run ruff check`, `uv run mypy --strict`, `uv run pytest`, `uv run python apps/backend/scripts/export_openapi.py && git diff --exit-code apps/backend/openapi.json`) + frontend (`pnpm typecheck`, `pnpm lint`, `pnpm test`, `pnpm --filter @sportzal/api-client codegen && git diff --exit-code`) gates параллельно.

## Constraints

- **Tech stack — Backend**: Python 3.12 + uv + FastAPI 0.115+ + SQLAlchemy 2.0 async + Alembic async + Pydantic v2 + Postgres 16 + Redis 7 + ARQ + structlog — закреплено пользователем; альтернативы не рассматриваются
- **Tech stack — Frontend**: pnpm workspaces; существующий frontend стек (React 19, Vite 6, TanStack) не трогаем
- **Region**: РФ/СНГ — Stripe запрещён; платежи только ЮKassa; Telegram как первичный канал
- **Tooling**: ruff + mypy strict + import-linter обязательны — архитектурные правила выполнимы локально через `uv run`
- **Testing**: backend-тесты используют `httpx ASGITransport` (не реальный сетевой стек) и `pytest-asyncio`
- **Frontend integrity** (updated 2026-05-15): `apps/admin-web` остаётся frozen-as-of-v1.3 как **mock-mode contract reference** — показывает UX intent + детерминированные mock-данные (faker seed=42) для дизайнер-команды; не является production target. Production admin + client apps разрабатываются дизайн-командой **вне этого репозитория**; backend — единственный source of truth через OpenAPI / `schema.d.ts` / Postman collection (formal handoff lands in v1.9, after all business modules complete). Не редактировать внутреннюю структуру `apps/admin-web/` без явного решения
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
| D-27-OWNER-COPY-LOCK | Phase 27 owner sign-off — 6 locked Russian DM templates (NTF-COPY-01); per-client A/B variant via `client_id.bytes[0] & 1` (anti-oracle); placeholder `{end_date}` formatted via Russian long form (e.g. `16 мая 2026 г.`). Mirrors v1.2 Phase 20 D-20-9 / D-5 sign-off mechanism — locked Russian copy must be owner-signed; modification requires new sign-off row. | ✓ Auto-approved — v1.3 (Phase 27) — auto-approved under `workflow.auto_advance` 2026-05-09 |
| Membership status taxonomy — central `_assert_can_transition` guard + read-only `MEMBERSHIP_STATUS_TRANSITIONS` constant in `app/modules/memberships/constants.py`; Postgres CHECK admits `'frozen'` as of migration `0007_status_taxonomy` | One source of truth for legal transitions; invalid moves return 409 `invalid_transition` with discriminating code; declarative table is grep-able and unit-testable independently of any callsite | ✓ Good — v1.3 (Phase 24 / INFRA-16) |
| Resolver defence-in-depth — `resolve_active_membership_by_client` filters `end_date >= today (Europe/Moscow)` regardless of `status` | A missed ARQ `expire_memberships` tick can no longer leak an expired row to check-in or self check-in — the resolver is the second wall. Closes MEM-04 D-13 carried from v1.2. | ✓ Good — v1.3 (Phase 24 / DEBT-01) |
| Mock/HTTP `?expiring=true&within=N` parity — both impls implement identical filter (1..30, default 7); admin-web HTTP service drops its old client-side filter + BLK-06 single-page pagination collapse | Closes WR-07 carried from v1.2; «Истекают» pill on `/memberships` works the same in mock and http modes (modulo Phase 28 `?status=` mock-parity gap deferred to v1.4) | ✓ Good — v1.3 (Phase 24 / DEBT-02) |
| Freeze period concurrency — partial unique index `(membership_id) WHERE ended_at IS NULL` on `membership_freeze_periods` | DB wins the race for the second concurrent freeze (IntegrityError → service returns 409 `already_frozen`); app-layer check is informative only. Mirrors v1.2 visits `UNIQUE (client_id, gym_date)` discipline. | ✓ Good — v1.3 (Phase 25 / MEM-FRZ-TEST-03) |
| Freeze day accounting — ceil-rounded `end_date += ceil((ended_at - started_at) in Europe/Moscow days)` | Client never loses partial days — a 30-second freeze still credits a full day; safer to over-grant than to short-change. Single source: `_compute_days_used` in `freeze_helpers.py`. | ✓ Good — v1.3 (Phase 25 / MEM-FRZ-05) |
| Renewal date strategy — `start_date = source.end_date + 1` for active/frozen sources, but `start_date = today (Europe/Moscow)` for expired sources; audit payload carries `start_date_strategy` literal | A renewal on an expired membership should begin **now**, not retroactively (would imply a back-dated membership with zero useful days). Strategy is audit-traceable so a future report can split renewal categories. | ✓ Good — v1.3 (Phase 26 / MEM-REN-04) |
| Renewal pricing — snapshot from **current** plan, not from source membership | If the plan price changed between original sale and renewal, the customer pays the **new** price. Documented user-visible behaviour; symmetric with v1.2 mandatory snapshot pricing on initial sale. | ✓ Good — v1.3 (Phase 26 / MEM-REN-02 + TEST-02) |
| Resolver tiebreak — `start_date ASC, created_at DESC` (was `end_date DESC, created_at DESC` in v1.2) | When a client has both a running membership and a renewal queued, check-in keeps using the **currently running** one until its `end_date` passes — then the renewal naturally takes over without an explicit switch. Single rule across reception + bot + ARQ. | ✓ Good — v1.3 (Phase 26 / MEM-REN-03) |
| Expiring-soon notification idempotency — UNIQUE `(membership_id, kind)` on `membership_notifications`; insert only on successful Telegram send (403/blocked → no row, retry next tick) | Docker-restart at 06:14 cannot double-ping; transient Telegram outage doesn't burn the window — next 06:15 tick retries. The table is the single source of truth, not a "sent" boolean on the membership. | ✓ Good — v1.3 (Phase 27 / NTF-01 + NTF-05) |
| ARQ cron ordering — `expire_memberships` 06:05 then `send_expiring_notifications` 06:15 (10-min buffer, both `unique=True`) | Expired memberships must transition to `status='expired'` before the expiring-soon selector runs; 10-min buffer absorbs slow expire_memberships ticks without ordering races. Both jobs are idempotent so a re-run is safe. | ✓ Good — v1.3 (Phase 27) |
| `LOCKED_AUDIT_EVENTS` — frozen up-front before callsites land (v1.3 added 6 pairs in Phase 24, used by Phases 25/26/27) | The AST literal-string gate on `audit.emit` forbids ad-hoc strings; pre-registering the new events lets all subsequent phases pass CI from their first commit without a churn of "add event then add callsite" iterations. | ✓ Good — v1.3 (Phase 24 / INFRA-15) |
| Phase 29 — milestone-verification phase replaces a standalone `v1.3-MILESTONE-AUDIT.md`; gate runs against live backend + Telegram sandbox; 3 production-blocker regressions discovered + fixed inline (REG-29-01/03/04) | The verification phase is itself the audit: 7/7 human-verification scenarios, cross-phase smoke, 6/6 CI gate evidence. Catching REG-29-01 (Vite dev-proxy), REG-29-03 (bot worker resolver registrations), REG-29-04 (one-shot cron eager-import) proved the gate works — these would have been v1.4 blockers if discovered after milestone close. | ✓ Good — v1.3 (Phase 29 / DEBT-04) |

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
*Last updated: 2026-05-17 — Milestone v1.5 Schedule + Bookings (PT slots) opened. Roadmap re-ordered under "finish business modules first → polish → integrate → launch" strategy: v1.5 → v1.6 (Email + Multi-user) → v1.7 (ЮKassa + 54-ФЗ) → v1.8 (Reports + Audit Log API) → v1.9 (API Handoff + Hardening; was v1.5) → v2.0 (Frontend Integration + Launch). Phase numbering continues from Phase 37.*
