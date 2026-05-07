# Sportzal v1.2 — Memberships + Visits Requirements

**Milestone:** v1.2 Memberships + Visits
**Goal:** Превратить CRM из «реестра клиентов» в операционный инструмент зала: продажа абонемента → ежедневная отметка посещений (двухканально: reception manual + клиент сам через Telegram bot).
**Source documents:** `.planning/PROJECT.md`, `.planning/research/SUMMARY.md`
**REQ-ID convention:** Continued from v1.1 milestone. New categories: `MEM-PLAN`, `MEM`, `VIS`, `ARQ`, `HYG`.

---

## v1.2 Requirements

### Foundations (Phase 15)

- [ ] **INFRA-08**: `app/core/permissions.py` adds `Action.{CREATE, CANCEL, CHECK_IN}` and `Resource.{MEMBERSHIPS, MEMBERSHIP_PLANS, VISITS}` StrEnum entries; `OWNER_ONLY` frozenset extended with `(VIEW|EDIT|CREATE|DELETE, MEMBERSHIP_PLANS)` + `(CANCEL|DELETE, MEMBERSHIPS)`. Reception RETAINS `(CREATE, MEMBERSHIPS)` and `(CHECK_IN, VISITS)`.
- [ ] **INFRA-09**: `apps/admin-web/src/shared/session/registry.ts` and `can.ts` mirror the new resources/actions/OWNER_ONLY entries byte-paritetic with backend; TEST-06 three-way parity test (backend ↔ admin-web `can.ts` ↔ `registry.ts`) extended to cover the new pairs.
- [ ] **INFRA-10**: `app/core/sql.py` exposes `escape_like_pattern(value: str) -> str` (escapes `%`, `_`, `\`); migrated from `app/modules/clients/repository.py`; clients repository imports from `core/sql.py` (no behavior change, regression-tested).
- [ ] **INFRA-11**: `app/core/audit.py` defines `LOCKED_AUDIT_EVENTS: frozenset[tuple[str, str]]` (event_name, resource_type) tuples; `audit.emit()` validates the pair at call and raises if not in the set; locked list extended with the 10 new v1.2 events (`membership_plan_*` ×3, `membership_*` ×3 incl. `membership_expired`, `visit_*` ×4 incl. `visit_rejected_*`).
- [ ] **INFRA-12**: `app/core/schemas.py` exposes `BackendSchemaBase(BaseModel)` with `alias_generator=to_camel`, `validate_by_name=True`, `validate_by_alias=True`, `extra='forbid'` (Pydantic 2.11+ canonical pair, replacing the deprecated `populate_by_name=True`); v1.2 schemas (memberships, visits) inherit from it; ruff `UP007` enforced repo-wide (`X | None` not `Optional[X]`).
- [ ] **INFRA-13**: `app/core/services.py` exposes `BusinessService` mixin / template documenting the `await session.commit()` invariant for write paths; CI gate (ruff custom rule OR pytest meta-test) walks every `service.py` write function and fails if it lacks an explicit `commit` call (or an explicit `# noqa: SVC001 caller-owns-txn` comment).
- [ ] **INFRA-14**: PROJECT.md `## Key Decisions` extended in Phase 15 commit with: (a) inclusive `end_date` semantics for memberships, (b) `gym_date` defined as `(checked_in_at AT TIME ZONE 'Europe/Moscow')::date`, (c) accepted residual friend-fraud risk for v1.2 single-zal scope.

### Memberships — Plans Catalog (Phase 16)

- [ ] **MEM-PLAN-01**: Alembic migration `0004_membership_plans.py` creates `membership_plans` table with columns: `id` (UUID PK gen_random_uuid()), `name` (VARCHAR(120) NOT NULL), `duration_days` (INT NOT NULL CHECK > 0), `price_kopecks` (BIGINT NOT NULL CHECK >= 0), `active` (BOOLEAN NOT NULL DEFAULT TRUE), `created_at`/`updated_at` (TIMESTAMPTZ via TimestampMixin), `deleted_at` (TIMESTAMPTZ NULL via SoftDeleteMixin). Partial unique index `WHERE deleted_at IS NULL` on `lower(name)`.
- [ ] **MEM-PLAN-02**: `app/modules/memberships/{models,schemas,repository,service,router}.py` follow the validated `clients` module template; service write paths use the `BusinessService` template (INFRA-13); ILIKE search (if implemented) uses `core/sql.py:escape_like_pattern`.
- [ ] **MEM-PLAN-EP-01**: `GET /api/v1/membership-plans` lists plans (owner-only via `Depends(require_permission(Action.VIEW, Resource.MEMBERSHIP_PLANS))`); paginated envelope `{items, total, page, pageSize}`; `?active=true` filter optional.
- [ ] **MEM-PLAN-EP-02**: `POST /api/v1/membership-plans` creates a plan (owner-only, CSRF); body `{name, durationDays, priceKopecks, active?}`; returns 201 with the created plan.
- [ ] **MEM-PLAN-EP-03**: `PATCH /api/v1/membership-plans/{id}` updates `name`/`price_kopecks`/`active` (owner-only, CSRF); `duration_days` is **immutable** post-creation (would invalidate existing sold instances' snapshots semantics).
- [ ] **MEM-PLAN-EP-04**: `DELETE /api/v1/membership-plans/{id}` soft-deletes a plan (owner-only, CSRF); returns 409 `plan_in_use` if any non-cancelled `Membership` row references it (since FK is `ON DELETE RESTRICT`).
- [ ] **MEM-PLAN-AUDIT-01**: `audit.emit("membership_plan_created", actor, resource_type='membership_plan', resource_id=plan.id, name, duration_days, price_kopecks)` on create; analogous events on update/archive.

### Memberships — Instances (Phase 17)

- [ ] **MEM-01**: Alembic migration `0005_memberships.py` creates `memberships` table with columns: `id` (UUID PK), `client_id` (UUID NOT NULL FK clients.id ON DELETE RESTRICT), `plan_id` (UUID NOT NULL FK membership_plans.id ON DELETE RESTRICT), `duration_days_snapshot` (INT NOT NULL), `price_kopecks_snapshot` (BIGINT NOT NULL), `plan_name_snapshot` (VARCHAR(120) NOT NULL), `start_date` (DATE NOT NULL), `end_date` (DATE NOT NULL — INCLUSIVE last valid check-in day), `status` (VARCHAR NOT NULL CHECK IN ('active','expired','cancelled') DEFAULT 'active'), `cancelled_at` (TIMESTAMPTZ NULL), `cancel_reason` (TEXT NULL), `paid_at` (TIMESTAMPTZ NULL — manual today, ЮKassa in v1.3), `notes` (TEXT NULL), `activation_policy` (VARCHAR NOT NULL DEFAULT 'purchase_date' CHECK = 'purchase_date'), `created_at`/`updated_at`. Index on `(client_id, status, end_date DESC)` for resolver queries.
- [ ] **MEM-02**: `Membership.create_membership(session, client_id, plan_id, actor)` snapshots plan fields at insert time (`plan_name_snapshot`, `duration_days_snapshot`, `price_kopecks_snapshot`); `start_date = today (Europe/Moscow)`, `end_date = start_date + duration_days_snapshot - 1` (inclusive); `status='active'`. Plan edits after sale never affect existing membership rows.
- [ ] **MEM-03**: `service.cancel_membership(session, membership_id, actor, reason?)` is **owner-only** (enforced at router level), only valid when current `status='active'`; sets `status='cancelled'`, `cancelled_at=now()`. Transition guards: `expired → cancelled` and `cancelled → cancelled` return 409 `invalid_transition`.
- [ ] **MEM-04**: `service.resolve_active_membership_by_client(session, client_id) -> ActiveMembership | None` returns the SINGLE active membership matching `status='active' AND end_date >= today (Europe/Moscow)`. Tiebreak when client has multiple active memberships: latest `end_date`, then `created_at DESC`. Documented in service docstring.
- [ ] **MEM-05**: `app/core/dependencies.py` defines `ActiveMembership` Protocol (`id, client_id, end_date, status`), `ActiveMembershipResolver` callable type, `register_active_membership_resolver(resolver)` setter, `resolve_active_membership(session, client_id)` consumer; `app/main.py:create_app()` registers `memberships.service.resolve_active_membership_by_client` as the resolver before `lifespan` starts.
- [ ] **MEM-EP-01**: `GET /api/v1/memberships?clientId={uuid}&status={active|expired|cancelled}` lists memberships (paginated envelope); reception+owner can VIEW.
- [ ] **MEM-EP-02**: `GET /api/v1/memberships/{id}` returns single membership; reception+owner can VIEW.
- [ ] **MEM-EP-03**: `POST /api/v1/memberships` (CSRF) sells a membership; body `{clientId, planId, paidAt?, notes?}`; reception+owner can CREATE; returns 201 with created Membership.
- [ ] **MEM-EP-04**: `POST /api/v1/memberships/{id}/cancel` (CSRF) cancels a membership; body `{reason?}`; **owner-only** via `Depends(require_permission(Action.CANCEL, Resource.MEMBERSHIPS))`; returns 200 with the updated row.
- [ ] **MEM-AUDIT-01**: `audit.emit("membership_created", ...)` on sale, `"membership_cancelled"` on cancel (with reason in payload), `"membership_expired"` on auto-expiry (actor_user_id=None).

### ARQ Scheduled Job — Membership Expiry (Phase 18)

- [x] **ARQ-01**: `app/workers/scheduled/__init__.py` (namespace marker) and `app/workers/scheduled/expire_memberships.py` exist; the latter exposes `async def expire_memberships(ctx) -> int`. D-09 docstring documents the worker→module exception.
- [x] **ARQ-02**: `expire_memberships(ctx)` is idempotent: single-transaction `UPDATE memberships SET status='expired' WHERE end_date < CURRENT_DATE AND status='active' RETURNING id` (or equivalent ORM flow); returns count of newly-expired rows; emits `audit.emit("membership_expired", actor_user_id=None, ...)` for each row.
- [x] **ARQ-03**: `app/workers/__init__.py` defines a real `WorkerSettings` (replacing the placeholder docstring): `redis_settings` from `get_settings().redis_url`, `on_startup`/`on_shutdown` opening/closing the DB lifespan and exposing `sessionmaker` via `ctx`, `functions=[expire_memberships]`, `cron_jobs=[cron(expire_memberships, hour=3, minute=5, unique=True, keep_cronjob_progress=60)]` (06:05 Europe/Moscow with container `TZ=UTC`).
- [x] **ARQ-04**: ARQ worker is added to `apps/backend/docker-compose.yml` (per Phase 18 CD-02 — the canonical compose file lives at `apps/backend/`, not `infra/`; relocation deferred to a future infra-consolidation phase) as a 5th service `arq-worker` (`command: uv run arq app.workers.WorkerSettings`, `restart: unless-stopped`, `depends_on: [migrate (service_completed_successfully), redis (service_started)]`, `env_file: .env`, `environment: { TZ: UTC, DATABASE_URL: postgresql+asyncpg://app:app@postgres:5432/sportzal, REDIS_URL: redis://redis:6379/0 }`); placeholder `apps/backend/app/workers/scheduler.py` is deleted.
- [x] **ARQ-05**: `on_job_start`/`on_job_end` hooks bind `job_id`/`job_name` to structlog contextvars so cron-job log lines carry the same shape as request log lines (analogous to `request_id` from RequestIdMiddleware).
- [x] **ARQ-TEST-01**: Unit test calls `expire_memberships(ctx)` directly (no real ARQ runtime needed) with a fixture creating 3 memberships (1 expiring today, 1 expiring yesterday, 1 future); expects exactly 1 newly-expired row (yesterday's, end_date < today) and exactly 1 `membership_expired` audit event; today's row (end_date == today) stays `active` until tomorrow's tick (inclusive end_date per Phase 15 Key Decisions).
- [x] **ARQ-TEST-02**: Idempotency test runs `expire_memberships(ctx)` twice with the same data; second call returns 0 (no double-expire), no duplicate audit events.

### Visits (Phase 19)

- [ ] **VIS-01**: Alembic migration `0006_visits.py` creates `visits` table with columns: `id` (UUID PK), `client_id` (UUID NOT NULL FK clients.id ON DELETE RESTRICT), `membership_id` (UUID NOT NULL FK memberships.id ON DELETE RESTRICT), `checked_in_at` (TIMESTAMPTZ NOT NULL DEFAULT now()), `gym_date` (DATE NOT NULL GENERATED ALWAYS AS ((checked_in_at AT TIME ZONE 'Europe/Moscow')::date) STORED), `channel` (VARCHAR NOT NULL CHECK IN ('reception','telegram_bot')), `checked_in_by` (UUID NULL FK users.id ON DELETE SET NULL — nullable for telegram_bot), `created_at`. UNIQUE INDEX on `(client_id, gym_date)`. Indexes: `(client_id, checked_in_at DESC)` for history queries.
- [ ] **VIS-02**: `app/modules/visits/{models,schemas,repository,service,router}.py` follow the validated module template; service uses `BusinessService` (INFRA-13).
- [ ] **VIS-03**: `service.create_visit_reception(session, client_id, actor)` validates: (a) gym hours window via `settings.gym_hours_start` / `settings.gym_hours_end` Europe/Moscow → `OutsideGymHoursError(409)`, (b) calls `core.dependencies.resolve_active_membership(session, client_id)` → `NoActiveMembershipError(409)` if None, (c) inserts Visit row → IntegrityError on `(client_id, gym_date)` UNIQUE → `DuplicateCheckinError(409)`. Sets `channel='reception'`, `checked_in_by=actor.id`.
- [ ] **VIS-04**: `service.create_visit_self_checkin(session, telegram_user_id, chat_id)` looks up Client via `users.telegram_user_id` ↔ `users.id` ↔ existing client mapping (TBD in Phase 19 plan: how clients are linked to users — likely via `users.client_id` FK or lookup). Same anti-fraud chain as VIS-03 but: `channel='telegram_bot'`, `checked_in_by=NULL`. Specific exception classes for bot path: `NoActiveMembershipError`, `DuplicateCheckinError`, `OutsideGymHoursError`.
- [ ] **VIS-05**: `apps/backend/.env.example` adds `GYM_HOURS_START=07:00` and `GYM_HOURS_END=23:00` (HH:MM Europe/Moscow); `app/core/config.py` `Settings` parses to `time` objects; missing values fail loud at startup.
- [ ] **VIS-EP-01**: `GET /api/v1/visits?clientId={uuid}&from={date}&to={date}` lists visits (paginated envelope, default sort `checked_in_at DESC`); reception+owner can VIEW.
- [ ] **VIS-EP-02**: `GET /api/v1/visits/{id}` returns single visit; reception+owner.
- [ ] **VIS-EP-03**: `POST /api/v1/visits` (CSRF) reception manual check-in; body `{clientId}`; reception+owner can CHECK_IN; returns 201 with the created Visit. 409 responses include `code` discriminating `no_active_membership` / `duplicate_checkin` / `outside_gym_hours`.
- [ ] **VIS-AUDIT-01**: `audit.emit("visit_created", ..., channel)` on success; `"visit_rejected_no_membership"` / `"visit_rejected_duplicate"` / `"visit_rejected_outside_hours"` on rejections (with `channel` payload). Bot-path rejections also emitted (actor_user_id=None for telegram_bot).
- [ ] **VIS-TEST-01**: Concurrent-request test — 10 parallel `POST /api/v1/visits` for the same client → exactly 1×201 + 9×409 `duplicate_checkin` (Postgres UNIQUE INDEX wins the race, not app-layer check).

### Telegram Bot — `/checkin` (Phase 20)

- [ ] **AUTH-TG-07**: `HandlerContext` NamedTuple in `app/integrations/telegram/handlers.py` extends to include `visits_service: ModuleType`; D-10 documents the worker→visits_service exception (parallel to D-06 for telegram_service).
- [ ] **AUTH-TG-08**: `app/integrations/telegram/handlers.py` adds `checkin_handler(update, context, ctx)`; calls `ctx.visits_service.create_visit_self_checkin(...)` inside `async with ctx.session_factory() as session`; explicit `await session.commit()` on success; failure paths reply with locked Russian DM strings (NEVER include client name, end_date, hours, membership status — single generic failure message per branch).
- [ ] **AUTH-TG-09**: `app/workers/telegram_bot.py` imports `app.modules.visits.service` (D-10), passes it via `HandlerContext`, and registers `("checkin", checkin_handler)` in the handlers list alongside `("start", start_handler)`.
- [ ] **AUTH-TG-10**: Redis-backed `update_id` dedup in the bot worker uses keyspace `sz:bot:update:{update_id}` (TTL 1 hour); replay attempts (Telegram resending an Update on bot restart) do not double-create visits. Key prefix coexists with `arq:*` and `sz:session:*` without collision.
- [ ] **AUTH-TG-11**: Russian DM copy is locked in code constants (NOT freeform i18n) and reviewed/signed-off by the project owner before Phase 20 merge: success `"✅ Отмечено"`, no-membership `"У вас нет активного абонемента. Обратитесь к администратору."`, duplicate `"Вы уже отмечались сегодня."`, outside-hours `"Зал сейчас закрыт. Часы работы: {hours}."` (gym hours interpolated from env).

### API Surface — OpenAPI Drift Gate Refresh (Phase 21)

- [ ] **API-04**: `apps/backend/scripts/export_openapi.py` regenerated `apps/backend/openapi.json` is byte-stable; CI `git diff --exit-code apps/backend/openapi.json` passes after Phases 16/17/19/23 merge.
- [ ] **API-05**: `pnpm --filter @sportzal/api-client codegen` regenerates `packages/api-client/src/schema.d.ts`; new operation IDs surface for membership-plans / memberships / visits / sessions; CI `git diff --exit-code packages/api-client/src/schema.d.ts` passes.

### Frontend Wiring — admin-web (Phase 22)

- [ ] **FE-04**: `apps/admin-web/src/features/memberships/{api,components,model,index.ts}` exists; `useMembershipsByClient(clientId)` + `useMembershipPlans()` hooks wired to typed `services.memberships.*` swap-seam (mock + http impls).
- [ ] **FE-05**: `apps/admin-web/src/features/visits/{api,components,model,index.ts}` exists; `useRecentVisitsByClient(clientId, opts)` hook wired.
- [ ] **FE-06**: New routes: `/_protected/membership-plans.tsx` (owner-only via `beforeLoad` mirror of `clients.tsx:14-23`), `/_protected/memberships.tsx`, `/_protected/visits.tsx` — all loaders use `queryClient.ensureQueryData` with same keys as hooks.
- [ ] **FE-07**: `routes/_protected/clients.$clientId.tsx` (NEW — Pattern α) composes `Promise.all([ensureQueryData(client), ensureQueryData(memberships), ensureQueryData(visits)])` in loader (no waterfall). Page renders `<MembershipsBlock>` (from `features/memberships`) and `<RecentVisitsBlock>` (from `features/visits`) — `features/clients` does NOT import either.
- [ ] **FE-08**: Reception UX edge cases on check-in page: (a) phone-prefix search returns top-5 matches with disambiguation, (b) if today's visit already exists for that client, the button is disabled and shows badge "Отмечен в HH:MM via {channel}", (c) if active membership ends today (inclusive), the button still enables, (d) outside gym hours the button is disabled with the actual gym-hours string from a `GET /api/v1/visits/_meta` (or env-mirrored config) response.
- [ ] **FE-09**: Active sessions UI on profile page (carryover from v1.1 Auth UX queue): `/auth/sessions` list + per-session "Revoke" button + "Logout all" button; uses existing `/api/v1/auth/logout-all` + new `GET /api/v1/auth/sessions` and `POST /api/v1/auth/sessions/{family_id}/revoke` endpoints (Phase 23 may also need to ship the `GET sessions` and per-family revoke endpoints if not present; this requirement spans both backend and frontend).
- [ ] **FE-10**: Cheap-win differentiator picks: D-3 (red badge "истёк сегодня" in client list memberships block), D-2 ("expiring within 7 days" filter on memberships list page), D-5 (Telegram bot success DM includes days-remaining). Other differentiators (D-1/D-4/D-6/D-7 from FEATURES.md) deferred to v1.3+.
- [ ] **FE-11**: ESLint flat config validates Pattern α — no `features/clients/*` imports `features/memberships/*` or `features/visits/*`; tested via negative-test fixture in `eslint.config.js` (mirror of v1.1 fixtures). Confirm `eslint.config.js` `import/no-restricted-paths` rules in Phase 22 plan.

### Hygiene — v1.1 Carryover (Phase 23, parallel-eligible)

- [ ] **HYG-01**: Phase 04 CR-01 closure — `/auth/login` Argon2 verify-error path returns 401 `invalid_credentials` (not 500); structlog logs the verify-error reason at WARNING level. Existing rate-limit (5/15min) still enforced.
- [ ] **HYG-02**: Phase 04 CR-02 closure — invalid UUID in `sz_access`/`sz_refresh` cookie value (e.g. tampered) returns 401 `invalid_session` (not 500); auth dependency catches the parse error explicitly.
- [ ] **HYG-03**: Active sessions backend endpoints (if not already shipped in v1.1): `GET /api/v1/auth/sessions` returns the user's active session families with `{family_id, created_at, last_used_at, user_agent?, channel}`; `POST /api/v1/auth/sessions/{family_id}/revoke` (CSRF) revokes a single family. Existing `POST /api/v1/auth/logout-all` retains its behavior. (FE-09 consumes these.)

### Tests

- [ ] **TESTS-08**: TEST-06 RBAC parity test extended to cover the new (action, resource) pairs across backend `permissions.py` ↔ admin-web `can.ts` ↔ `registry.ts`; fails if any side drifts.
- [ ] **TESTS-09**: `audit.emit` validation against `LOCKED_AUDIT_EVENTS` covered by a meta-test that walks every `audit.emit(...)` callsite in the codebase and confirms the (event_name, resource_type) pair is in the locked frozenset.
- [ ] **TESTS-10**: Membership state-machine transition matrix unit test enumerates all 9 (from_status, action) cells and asserts allowed transitions match `MEM-03` rules + Postgres CHECK constraint.
- [ ] **TESTS-11**: `_escape_like_pattern` regression suite from v1.1 CR-01 closure runs against `core/sql.py` (relocated module path); existing `clients` tests pass unchanged after import path swap.

---

## Future Requirements (deferred to v1.3+)

### Memberships extras
- Freeze (заморозка) with daily counter
- Visit-count plans (10/20/50 visits, no time limit)
- Hybrid plans (N visits within M months)
- Expiring-soon Telegram notifications (3 days before end_date)
- Membership renewal flow (auto-extend or one-click renew)
- Plan price history / promotions / coupons

### Visits extras
- Photo turnstile (hardware integration)
- Geofencing for self check-in
- Per-class booking integration (depends on schedule module)
- Group lessons attendance

### Billing (entire category)
- ЮKassa intake + webhooks + idempotency keys
- Чеки 54-ФЗ generation
- Refund flows
- Card vault for recurring charges
- Receipts UI

### Auth UX deferred
- Password reset flow via Telegram bot DM
- HaveIBeenPwned check on registration
- Webhook-based bot mode for prod

### Audit log extras
- `GET /api/v1/audit-log` (owner-only) with filters
- Audit log read UI

### Clients extras
- Photo upload
- Bulk CSV import
- Tags taxonomy CRUD

### v1.1 hygiene remainders
- Phase 06 audit `user_id` plumbing (audit_log.user_id NULL on early auth events)
- Phase 03 advisories: env parser, db_session rollback semantics, postgres LAN exposure, backup_db.sh staging

### Next business slices
- Trainers
- Schedule
- Bookings

---

## Out of Scope (v1.2 — explicit exclusions)

- **Multi-tenancy** — пет-проект на 1 зал; добавляется только когда появится второй покупатель.
- **Stripe** — недоступен в РФ.
- **`apps/client-web`** — клиентский фронт появится только в Phase J; self check-in в v1.2 идёт через Telegram bot (расширение существующего).
- **Kubernetes / Terraform / production deploy** — пока только dev docker-compose.
- **Membership freeze / visit-count plans / expiring-soon notifications** — деферд в v1.3+ (см. Future Requirements).
- **Photo+biometrics turnstile** — hardware tier; единственный self-check-in канал в v1.2 — Telegram bot.
- **GET /api/v1/audit-log read endpoint + UI** — деферд (audit_log пишется новыми модулями, но read-side API остаётся в v1.3+).
- **Password reset / HaveIBeenPwned / webhook bot mode** — Auth UX queue остаётся деферд.

---

## Traceability

*Filled by gsd-roadmapper during ROADMAP creation on 2026-05-07. 63/63 v1.2 requirements mapped to 9 phases (15-23).*

| REQ-ID | Phase | Status |
|--------|-------|--------|
| INFRA-08 | Phase 15 | Pending |
| INFRA-09 | Phase 15 | Pending |
| INFRA-10 | Phase 15 | Pending |
| INFRA-11 | Phase 15 | Pending |
| INFRA-12 | Phase 15 | Pending |
| INFRA-13 | Phase 15 | Pending |
| INFRA-14 | Phase 15 | Pending |
| TESTS-08 | Phase 15 | Pending |
| TESTS-11 | Phase 15 | Pending |
| MEM-PLAN-01 | Phase 16 | Pending |
| MEM-PLAN-02 | Phase 16 | Pending |
| MEM-PLAN-EP-01 | Phase 16 | Pending |
| MEM-PLAN-EP-02 | Phase 16 | Pending |
| MEM-PLAN-EP-03 | Phase 16 | Pending |
| MEM-PLAN-EP-04 | Phase 16 | Pending |
| MEM-PLAN-AUDIT-01 | Phase 16 | Pending |
| MEM-01 | Phase 17 | Pending |
| MEM-02 | Phase 17 | Pending |
| MEM-03 | Phase 17 | Pending |
| MEM-04 | Phase 17 | Pending |
| MEM-05 | Phase 17 | Pending |
| MEM-EP-01 | Phase 17 | Pending |
| MEM-EP-02 | Phase 17 | Pending |
| MEM-EP-03 | Phase 17 | Pending |
| MEM-EP-04 | Phase 17 | Pending |
| MEM-AUDIT-01 | Phase 17 | Pending |
| TESTS-09 | Phase 17 | Pending |
| TESTS-10 | Phase 17 | Pending |
| ARQ-01 | Phase 18 | Complete |
| ARQ-02 | Phase 18 | Complete |
| ARQ-03 | Phase 18 | Complete |
| ARQ-04 | Phase 18 | Complete |
| ARQ-05 | Phase 18 | Complete |
| ARQ-TEST-01 | Phase 18 | Complete |
| ARQ-TEST-02 | Phase 18 | Complete |
| VIS-01 | Phase 19 | Pending |
| VIS-02 | Phase 19 | Pending |
| VIS-03 | Phase 19 | Pending |
| VIS-04 | Phase 19 | Pending |
| VIS-05 | Phase 19 | Pending |
| VIS-EP-01 | Phase 19 | Pending |
| VIS-EP-02 | Phase 19 | Pending |
| VIS-EP-03 | Phase 19 | Pending |
| VIS-AUDIT-01 | Phase 19 | Pending |
| VIS-TEST-01 | Phase 19 | Pending |
| AUTH-TG-07 | Phase 20 | Pending |
| AUTH-TG-08 | Phase 20 | Pending |
| AUTH-TG-09 | Phase 20 | Pending |
| AUTH-TG-10 | Phase 20 | Pending |
| AUTH-TG-11 | Phase 20 | Pending |
| API-04 | Phase 21 | Pending |
| API-05 | Phase 21 | Pending |
| FE-04 | Phase 22 | Pending |
| FE-05 | Phase 22 | Pending |
| FE-06 | Phase 22 | Pending |
| FE-07 | Phase 22 | Pending |
| FE-08 | Phase 22 | Pending |
| FE-09 | Phase 22 | Pending |
| FE-10 | Phase 22 | Pending |
| FE-11 | Phase 22 | Pending |
| HYG-01 | Phase 23 | Pending |
| HYG-02 | Phase 23 | Pending |
| HYG-03 | Phase 23 | Pending |

**Coverage:** 63/63 v1.2 requirements mapped. No orphans, no duplicates.
