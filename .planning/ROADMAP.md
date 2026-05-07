# Roadmap: Sportzal

## Milestones

- ✅ **v1.0 Phase A: Skeleton** — Phases 1-3 (shipped 2026-05-01) — see [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 Auth + Clients** — Phases 4-14 (shipped 2026-05-07) — see [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
- 🚧 **v1.2 Memberships + Visits** — Phases 15-23 (started 2026-05-07)

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

### 🚧 v1.2 Memberships + Visits (Phases 15-23)

- [x] **Phase 15: Foundations — RBAC + audit taxonomy + helper hoisting** — extend `Action`/`Resource`/`OWNER_ONLY` (backend ↔ admin-web byte parity), hoist `escape_like_pattern` to `core/sql.py`, lock audit-event taxonomy, ship `BackendSchemaBase` + `BusinessService` template + AST commit gate, log v1.2 Key Decisions. (completed 2026-05-07)
- [x] **Phase 16: Membership Plans Catalog (backend)** — `membership_plans` table + module + 4 owner-only endpoints + audit events; first piece of v1.2 business surface. (completed 2026-05-07)
- [ ] **Phase 17: Membership Instances + Resolver (backend)** — `memberships` table with snapshot pricing + `paid_at`/`notes`/`activation_policy`; sell + cancel + active resolver via Protocol callback registered in `app/main.py`; transition matrix + audit events.
- [ ] **Phase 18: ARQ scheduled `expire_memberships`** — first real ARQ cron job (D-09); idempotent SQL `UPDATE … RETURNING id`; new `arq-worker` compose service; structlog `job_id` contextvars binding.
- [ ] **Phase 19: Visits — DB + reception check-in (backend)** — `visits` table with `gym_date GENERATED STORED` + UNIQUE `(client_id, gym_date)` for race-proof 1/day rule; gym-hours window from env; 3 endpoints; concurrent-request test.
- [ ] **Phase 20: Telegram bot `/checkin` self check-in** — `HandlerContext.visits_service` (D-10); locked Russian DM strings (no oracle leak); Redis `update_id` dedup; owner copy sign-off.
- [ ] **Phase 21: OpenAPI drift gate refresh + api-client codegen** — regen byte-stable `openapi.json` + `schema.d.ts`; CI green on both diffs.
- [ ] **Phase 22: admin-web wiring — memberships + visits + active sessions UI** — new `features/memberships`, `features/visits`; `/memberships`, `/membership-plans`, `/visits` routes; client-detail Pattern α; reception UX edge cases; cheap-win differentiators D-2/D-3/D-5; sessions UI.
- [ ] **Phase 23: Hygiene + active sessions backend (parallel-eligible)** — Phase 04 CR-01 (Argon2 verify-error → 401) + CR-02 (invalid UUID in cookie → 401); ship `GET /auth/sessions` + per-family revoke endpoints if not present.

## Phase Details

### Phase 15: Foundations — RBAC + audit taxonomy + helper hoisting
**Goal**: Lock the v1.2 contract surface (RBAC enums byte-paritetic FE↔BE, audit event taxonomy, schema base, service-write commit gate, key decisions) so phases 16/17/19/22 build on a frozen foundation.
**Depends on**: Nothing (first v1.2 phase; v1.1 shipped)
**Requirements**: INFRA-08, INFRA-09, INFRA-10, INFRA-11, INFRA-12, INFRA-13, INFRA-14, TESTS-08, TESTS-11
**Success Criteria** (what must be TRUE):
  1. `app/core/permissions.py` exposes `Action.{CREATE, CANCEL, CHECK_IN}` and `Resource.{MEMBERSHIPS, MEMBERSHIP_PLANS, VISITS}` and the `OWNER_ONLY` frozenset includes the v1.2 owner-only pairs; admin-web `registry.ts`/`can.ts` mirror them byte-for-byte and the three-way TEST-06 parity test passes.
  2. `app/core/sql.py:escape_like_pattern` is the single source of LIKE-escape; `clients/repository.py` imports from there with no behavior change and the v1.1 CR-01 regression suite passes against the relocated path.
  3. `audit.emit()` rejects any `(event_name, resource_type)` pair not in `LOCKED_AUDIT_EVENTS`; the locked set already lists every v1.2 event the next phases will emit (`membership_plan_*`, `membership_*`, `visit_*`).
  4. `BackendSchemaBase` (`alias_generator=to_camel`, `populate_by_name=True`, `extra='forbid'`) and the `BusinessService` template exist; a CI gate fails if any `service.py` write function lacks an explicit `await session.commit()` (or the documented `# noqa: SVC001` opt-out).
  5. PROJECT.md `## Key Decisions` records inclusive `end_date` semantics, `gym_date = (checked_in_at AT TIME ZONE 'Europe/Moscow')::date`, and the accepted residual friend-fraud risk for v1.2 single-zal scope.
**Plans**: 5 plans
  - [x] 15-01-PLAN.md — RBAC three-way parity extension (backend permissions.py + admin-web registry.ts + can.ts + test_rbac_parity.py) — INFRA-08, INFRA-09, TESTS-08
  - [x] 15-02-PLAN.md — Hoist escape_like_pattern to app/core/sql.py + relocate regression suite — INFRA-10, TESTS-11
  - [x] 15-03-PLAN.md — LOCKED_AUDIT_EVENTS frozenset + AuditEventNotLockedError + AST taxonomy walker — INFRA-11
  - [x] 15-04-PLAN.md — RequestContract → BackendSchemaBase rename + core/services.py docstring template + AST commit gate — INFRA-12, INFRA-13
  - [x] 15-05-PLAN.md — PROJECT.md Key Decisions (3 v1.2 entries) + REQUIREMENTS.md INFRA-12 wording fix — INFRA-14

### Phase 16: Membership Plans Catalog (backend)
**Goal**: Owner can manage the gym's plan catalog (the SKUs reception will sell in Phase 17).
**Depends on**: Phase 15 (RBAC contract, schema base, audit taxonomy)
**Requirements**: MEM-PLAN-01, MEM-PLAN-02, MEM-PLAN-EP-01, MEM-PLAN-EP-02, MEM-PLAN-EP-03, MEM-PLAN-EP-04, MEM-PLAN-AUDIT-01
**Success Criteria** (what must be TRUE):
  1. Owner can list plans via `GET /api/v1/membership-plans` with paginated `{items,total,page,pageSize}` envelope and an optional `?active=true` filter; reception receives 403.
  2. Owner can create a plan via `POST /api/v1/membership-plans` with `{name, durationDays, priceKopecks, active?}`; partial-unique `lower(name) WHERE deleted_at IS NULL` rejects duplicates.
  3. Owner can update plan name/price/active via `PATCH /api/v1/membership-plans/{id}`; `duration_days` is rejected as immutable to preserve sold-instance snapshot semantics.
  4. Owner can soft-delete a plan via `DELETE /api/v1/membership-plans/{id}`; deletion returns 409 `plan_in_use` when any `Membership` references it (cancelled and expired included) (FK `ON DELETE RESTRICT`).
  5. Every successful plan create/update/archive writes a locked audit event (`membership_plan_created` / `_updated` / `_archived`) with the actor and changed fields.
**Plans**: 5 plans
  - [x] 16-01-PLAN.md — Migration 0004_membership_plans + MembershipPlan ORM + alembic env.py extension — MEM-PLAN-01, MEM-PLAN-02
  - [x] 16-02-PLAN.md — schemas.py (Create/Update/Response/ListQuery/Sort) + PlanNameExistsError + PlanNotFoundError — MEM-PLAN-02, MEM-PLAN-EP-01..03
  - [x] 16-03-PLAN.md — repository.py + service.py + AST commit gate extension — MEM-PLAN-02, MEM-PLAN-EP-01..04, MEM-PLAN-AUDIT-01
  - [x] 16-04-PLAN.md — router.py with 5 endpoints + v1 wiring + openapi.json regen — MEM-PLAN-EP-01..04, MEM-PLAN-AUDIT-01
  - [x] 16-05-PLAN.md — Integration tests (CRUD/list/RBAC/audit) + unit schemas test — MEM-PLAN-EP-01..04, MEM-PLAN-AUDIT-01

### Phase 17: Membership Instances + Resolver (backend)
**Goal**: Reception can sell a membership to a client and the system can answer the single question "does this client have an active membership today?" — the foundation Visits will validate against.
**Depends on**: Phase 16 (plans table for FK + price/duration source)
**Requirements**: MEM-01, MEM-02, MEM-03, MEM-04, MEM-05, MEM-EP-01, MEM-EP-02, MEM-EP-03, MEM-EP-04, MEM-AUDIT-01, TESTS-09, TESTS-10
**Success Criteria** (what must be TRUE):
  1. A new sale via `POST /api/v1/memberships` snapshots `plan_name`, `duration_days`, `price_kopecks` at insert time and computes `end_date = start_date + duration_days - 1` (inclusive); subsequent plan edits never mutate the row.
  2. `POST /api/v1/memberships/{id}/cancel` is owner-only and accepts only `status='active' → 'cancelled'`; `expired→cancelled` and `cancelled→cancelled` return 409 `invalid_transition`, validated by an exhaustive transition-matrix test.
  3. `core.dependencies.resolve_active_membership(session, client_id)` returns the SINGLE active membership (status='active' AND end_date >= today Europe/Moscow), tiebreaking on latest `end_date` then `created_at DESC`; the resolver is registered from `app/main.py` via `register_active_membership_resolver` without `modules-independent` violation.
  4. Reception+owner can list/get memberships filtered by `clientId`/`status` via `GET /api/v1/memberships` and `GET /api/v1/memberships/{id}` with paginated envelope.
  5. `audit.emit("membership_created" | "membership_cancelled")` fires on the corresponding business action; the `audit.emit` meta-test (TESTS-09) confirms every callsite uses a pair in `LOCKED_AUDIT_EVENTS`.
**Plans**: 5 plans
  - [x] 17-01-PLAN.md — Migration 0005_memberships + Membership ORM + schemas + 4 new exceptions — MEM-01, MEM-EP-01..04
  - [x] 17-02-PLAN.md — core/dependencies.py ActiveMembership Protocol + register_active_membership_resolver slot — MEM-05
  - [ ] 17-03-PLAN.md — repository + service (sale, cancel, list, get, resolver, _is_plan_in_use_conflict) + Phase 16 D-15 closure + ROADMAP D-07 wording fix — MEM-02, MEM-03, MEM-04, MEM-AUDIT-01
  - [ ] 17-04-PLAN.md — Router (4 endpoints), v1 mount, app/main.py resolver wiring, openapi.json regen [BLOCKING migration apply] — MEM-EP-01..04, MEM-AUDIT-01
  - [ ] 17-05-PLAN.md — Integration tests (CRUD/list/RBAC/audit/plan_in_use/resolver) + unit tests (TESTS-10 9-cell matrix + schemas) — TESTS-09, TESTS-10, MEM-AUDIT-01

### Phase 18: ARQ scheduled `expire_memberships`
**Goal**: Active memberships transition to `expired` automatically when their `end_date` passes — without manual intervention or duplicate audit events on worker restart.
**Depends on**: Phase 17 (membership rows + service to expire)
**Parallel-eligible with**: Phase 19
**Requirements**: ARQ-01, ARQ-02, ARQ-03, ARQ-04, ARQ-05, ARQ-TEST-01, ARQ-TEST-02
**Success Criteria** (what must be TRUE):
  1. `app/workers/scheduled/expire_memberships.py` exists under D-09, exposes `async def expire_memberships(ctx) -> int`, and a single-transaction `UPDATE … WHERE end_date < CURRENT_DATE AND status='active' RETURNING id` flips due rows and returns the count.
  2. Running `expire_memberships(ctx)` twice on the same data returns 0 the second time and produces no duplicate `membership_expired` audit events (idempotency proven at SQL level, not relying on ARQ `unique=True`).
  3. `WorkerSettings` registers `cron(expire_memberships, hour=3, minute=5, unique=True)` (06:05 Europe/Moscow with container `TZ=UTC`); `on_startup`/`on_shutdown` open and close the DB lifespan and expose `sessionmaker` via `ctx`.
  4. `infra/docker-compose.yml` runs a 5th `arq-worker` service (`uv run arq app.workers.WorkerSettings`, `restart: unless-stopped`, depends on postgres+redis+migrate); the placeholder `app/workers/scheduler.py` is deleted.
  5. `on_job_start`/`on_job_end` bind `job_id`/`job_name` into structlog contextvars so cron-job log lines carry the same shape as request log lines (mirror of `RequestIdMiddleware`).
**Plans**: TBD

### Phase 19: Visits — DB + reception check-in (backend)
**Goal**: Reception can check a client into the gym from admin-web, and the system enforces "1 visit per gym-day per client" at the database level (race-proof) plus gym-hours window and active-membership requirement.
**Depends on**: Phase 17 (active-membership resolver)
**Parallel-eligible with**: Phase 18
**Requirements**: VIS-01, VIS-02, VIS-03, VIS-04, VIS-05, VIS-EP-01, VIS-EP-02, VIS-EP-03, VIS-AUDIT-01, VIS-TEST-01
**Success Criteria** (what must be TRUE):
  1. `visits` table has `gym_date GENERATED ALWAYS AS ((checked_in_at AT TIME ZONE 'Europe/Moscow')::date) STORED` plus `UNIQUE (client_id, gym_date)`; concurrent-request test sends 10 parallel `POST /api/v1/visits` for the same client and observes exactly 1×201 + 9×409 `duplicate_checkin`.
  2. `POST /api/v1/visits` (reception+owner, CSRF) validates gym hours from `Settings.gym_hours_start`/`_end` (Europe/Moscow) → 409 `outside_gym_hours`, calls `core.dependencies.resolve_active_membership` → 409 `no_active_membership` if None, then inserts with `channel='reception'` and `checked_in_by=actor.id`.
  3. `service.create_visit_self_checkin(session, telegram_user_id, chat_id)` runs the same anti-fraud chain but sets `channel='telegram_bot'`, `checked_in_by=NULL`, and raises module-specific exception classes (`NoActiveMembershipError` / `DuplicateCheckinError` / `OutsideGymHoursError`) the bot handler can map to DM strings (Phase 20 consumer).
  4. Reception+owner can list/get visits via `GET /api/v1/visits?clientId&from&to` and `GET /api/v1/visits/{id}` (paginated, default sort `checked_in_at DESC`).
  5. Every successful or rejected check-in writes the locked audit event (`visit_created` | `visit_rejected_no_membership` | `visit_rejected_duplicate` | `visit_rejected_outside_hours`) with `channel` payload; bot-path rejections are emitted with `actor_user_id=None`.
**Plans**: TBD

### Phase 20: Telegram bot `/checkin` self check-in
**Goal**: A client can DM the gym bot `/checkin` and get an immediate confirmation (or a generic, oracle-leak-free rejection) — extending the existing long-polling worker without violating `integrations ⊥ modules`.
**Depends on**: Phase 19 (visits service is the consumer behind the handler)
**Requirements**: AUTH-TG-07, AUTH-TG-08, AUTH-TG-09, AUTH-TG-10, AUTH-TG-11
**Success Criteria** (what must be TRUE):
  1. `HandlerContext` carries `visits_service: ModuleType` (D-10 documented in handler + worker docstrings, parallel to D-06); `app/integrations/telegram/handlers.py` calls `ctx.visits_service.*` and never imports from `app.modules.*` directly.
  2. The `/checkin` command, when the client has an active membership and is inside gym hours and hasn't checked in today, replies `"✅ Отмечено"` and writes a `visit_created` audit row with `channel='telegram_bot'`; `await session.commit()` is explicit on the success path.
  3. Each rejection branch DMs exactly one of the four locked Russian strings (`"У вас нет активного абонемента..."`, `"Вы уже отмечались сегодня."`, `"Зал сейчас закрыт. Часы работы: {hours}."`) with NO client name, end-date, or membership status leaked; the strings are constants in code, not freeform i18n, and signed off by the project owner before merge.
  4. Redis dedup on `sz:bot:update:{update_id}` (TTL 1h) prevents replay-driven double-creates; the namespace coexists with `arq:*` and `sz:session:*` without collision.
  5. `app/workers/telegram_bot.py` registers `("checkin", checkin_handler)` alongside `("start", start_handler)` and passes `visits_service` via `HandlerContext`; the bot-worker process restart does not double-create visits when Telegram resends Updates.
**Plans**: TBD

### Phase 21: OpenAPI drift gate refresh + api-client codegen
**Goal**: The frontend↔backend contract is byte-frozen for the new memberships/visits/sessions surface — drift becomes impossible without an explicit "I really meant it" commit.
**Depends on**: Phases 16, 17, 19 (and Phase 23 if active-sessions endpoints land there before this gate)
**Requirements**: API-04, API-05
**Success Criteria** (what must be TRUE):
  1. `apps/backend/scripts/export_openapi.py` regenerates `apps/backend/openapi.json` byte-stably with new operationIds for `membership-plans`, `memberships`, `visits` (and `sessions` if Phase 23 has merged); CI `git diff --exit-code apps/backend/openapi.json` passes.
  2. `pnpm --filter @sportzal/api-client codegen` regenerates `packages/api-client/src/schema.d.ts` to match the new spec; CI `git diff --exit-code packages/api-client/src/schema.d.ts` passes.
  3. The committed `schema.d.ts` exposes typed `paths['/membership-plans']`, `paths['/memberships']`, `paths['/visits']` (+ sessions when applicable) consumable from `apps/admin-web/src/shared/api`.
**Plans**: TBD

### Phase 22: admin-web wiring — memberships + visits + active sessions UI
**Goal**: An owner/reception user can do the full v1.2 flow end-to-end in admin-web on `VITE_API_MODE=http` — manage plans, sell memberships, check clients in, and review history — without regressing any v1.1 mock-backed domain.
**Depends on**: Phase 21 (typed api-client + frozen schema)
**Requirements**: FE-04, FE-05, FE-06, FE-07, FE-08, FE-09, FE-10, FE-11
**UI hint**: yes
**Success Criteria** (what must be TRUE):
  1. New routes `/_protected/membership-plans` (owner-only via `beforeLoad`), `/_protected/memberships`, and `/_protected/visits` work end-to-end against the real backend; loaders use `queryClient.ensureQueryData` with the same keys as the feature hooks (no waterfall, no double-fetch).
  2. The client-detail page `/_protected/clients/$clientId` loads client + memberships + recent-visits in a single `Promise.all(ensureQueryData)` and composes `<MembershipsBlock>` (from `features/memberships`) + `<RecentVisitsBlock>` (from `features/visits`) — Pattern α confirmed; ESLint `import/no-restricted-paths` rejects any `features/clients/* → features/memberships/*` or `features/visits/*` import (negative-test fixture).
  3. Reception's check-in page handles all the documented edge cases: phone-prefix search shows top-5 matches with disambiguation, today's-already-checked-in clients show a disabled button + "Отмечен в HH:MM via {channel}" badge, expired-today memberships still allow check-in, and outside-gym-hours disables the button with the actual gym-hours string.
  4. Active-sessions UI on the profile page lists session families (created/last-used/UA/channel) and supports per-session "Revoke" + "Logout all" buttons consuming `GET /api/v1/auth/sessions`, `POST /api/v1/auth/sessions/{family_id}/revoke`, and existing `POST /api/v1/auth/logout-all`.
  5. Cheap-win differentiators ship: D-3 red badge "истёк сегодня" in the client list, D-2 "expiring within 7 days" filter on the memberships list, D-5 Telegram bot success DM includes days-remaining; other differentiators (D-1/D-4/D-6/D-7) explicitly deferred.
**Plans**: TBD

### Phase 23: Hygiene + active sessions backend (parallel-eligible)
**Goal**: Close the v1.1 carryover error-mapping gaps (Argon2/UUID parse errors must surface as 401, not 500) and ship the backend endpoints the admin-web sessions UI needs in Phase 22.
**Depends on**: Nothing (parallel-eligible with anything after Phase 15; if it lands before Phase 21, the sessions endpoints flow through that drift gate)
**Requirements**: HYG-01, HYG-02, HYG-03
**Success Criteria** (what must be TRUE):
  1. `POST /auth/login` with a tampered/corrupted Argon2 hash returns 401 `invalid_credentials` (not 500); the rate-limit (5/15min) still applies and structlog logs the verify-error reason at WARNING level.
  2. A request carrying an invalid-UUID `sz_access` or `sz_refresh` cookie (e.g. tampered) returns 401 `invalid_session` (not 500); the auth dependency catches the parse error explicitly.
  3. `GET /api/v1/auth/sessions` returns the user's active session families with `{family_id, created_at, last_used_at, user_agent?, channel}`, and `POST /api/v1/auth/sessions/{family_id}/revoke` (CSRF) revokes a single family without affecting others; `POST /api/v1/auth/logout-all` retains its existing behavior.
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status   | Completed  |
|-------|-----------|----------------|----------|------------|
| 1. Monorepo Restructure & Frontend Move | v1.0 | 3/3 | Complete | 2026-04-30 |
| 2. Backend Skeleton with Quality Tooling | v1.0 | 8/8 | Complete | 2026-04-30 |
| 3. Tests, Dev Infrastructure & Documentation | v1.0 | 6/6 | Complete | 2026-05-01 |
| 4. Auth Foundations & Cookie/RBAC Primitives | v1.1 | 9/9 | Complete | 2026-05-02 |
| 5. User Schema + Email/Password Auth | v1.1 | 8/8 | Complete | 2026-05-03 |
| 6. RBAC Wiring + Parity Tests | v1.1 | 5/5 | Complete | 2026-05-03 |
| 7. Telegram OTP Channel | v1.1 | 8/8 | Complete | 2026-05-04 |
| 8. Clients Module + Audit Log | v1.1 | 8/8 | Complete | 2026-05-04 |
| 9. OpenAPI Pipeline + packages/api-client | v1.1 | 3/3 | Complete | 2026-05-04 |
| 10. admin-web Auth + Clients Wiring | v1.1 | 8/8 | Complete | 2026-05-04 |
| 11. Clients HTTP-mode Shape Adapter | v1.1 | 2/2 | Complete | 2026-05-04 |
| 12. v1.1 Verification Backfill | v1.1 | 5/5 | Complete | 2026-05-05 |
| 12.1. Clients Service Commit Fix (inline quick-fix) | v1.1 | — | Complete | 2026-05-04 |
| 13. v1.1 Minor Drift & Hygiene Cleanup | v1.1 | 4/4 | Complete | 2026-05-05 |
| 14. Clients Search PII Hardening | v1.1 | 3/3 | Complete | 2026-05-07 |
| 15. Foundations — RBAC + audit taxonomy + helper hoisting | v1.2 | 5/5 | Complete   | 2026-05-07 |
| 16. Membership Plans Catalog (backend) | v1.2 | 5/5 | Complete   | 2026-05-07 |
| 17. Membership Instances + Resolver (backend) | v1.2 | 2/5 | In Progress|  |
| 18. ARQ scheduled `expire_memberships` | v1.2 | 0/TBD | Not started | — |
| 19. Visits — DB + reception check-in (backend) | v1.2 | 0/TBD | Not started | — |
| 20. Telegram bot `/checkin` self check-in | v1.2 | 0/TBD | Not started | — |
| 21. OpenAPI drift gate refresh + api-client codegen | v1.2 | 0/TBD | Not started | — |
| 22. admin-web wiring — memberships + visits + active sessions UI | v1.2 | 0/TBD | Not started | — |
| 23. Hygiene + active sessions backend | v1.2 | 0/TBD | Not started | — |

---
*Roadmap last updated: 2026-05-07 — v1.2 Memberships + Visits planning (phases 15-23)*
*v1.0 Coverage: 47/47 v1 requirements validated*
*v1.1 Coverage: 70/70 requirements validated*
*v1.2 Coverage: 63/63 requirements mapped to 9 phases (planning)*
