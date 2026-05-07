# Project Research Summary — v1.2 Memberships + Visits

**Project:** Sportzal — single-gym CRM (РФ/СНГ)
**Domain:** Time-based memberships (plan catalog + per-client snapshot instance with active|expired|cancelled lifecycle) + visits (reception manual check-in via admin-web + self check-in via Telegram bot `/checkin`) on the v1.1 modular monolith. First real ARQ scheduled job (`expire_memberships`). admin-web wiring of new domains through the validated `VITE_API_MODE=http` swap-seam.
**Researched:** 2026-05-07
**Confidence:** HIGH

---

## Executive Summary

v1.2 is a **low-novelty, high-leverage milestone** — every capability is covered by the locked v1.1 stack with no new runtime dependencies. ARQ 0.26 ships native `arq.cron`; ptb-22 `CommandHandler` plugs straight into the existing `build_application` factory; the cross-module `Visits → Memberships` validation is a direct mirror of the validated `register_user_loader` Protocol pattern; audit_log is already centralized in `core/audit.py`; admin-web composition reuses the route-as-orchestrator pattern from `clients.tsx`. **No `.importlinter` contract changes are needed** — every new edge either lives inside a module, or routes through `app/main.py` composition root, or extends the documented D-06 worker exception with parallel D-09 (ARQ→memberships) and D-10 (telegram_bot→visits).

The risk profile is concentrated in three integrity bands, not architecture: (1) **`await session.commit()` discipline** (Phase 12.1 reprise risk), addressed by a `BusinessService` template + AST commit gate in Phase 15; (2) **snapshot pricing** — Membership row MUST carry `price_kopecks_snapshot`/`duration_days_snapshot`/`plan_name_snapshot` NOT NULL at insert with `ON DELETE RESTRICT` FK to plan, so plan edits never retroactively rewrite history; (3) **1/day enforcement at DB level** — Postgres UNIQUE INDEX on `(client_id, gym_date)` where `gym_date` is `GENERATED ALWAYS AS ((checked_in_at AT TIME ZONE 'Europe/Moscow')::date) STORED` — app-layer check has a race window. All three are addressable with patterns specified down to file-and-function level.

Suggested 9 phases (15–23). Strict critical path 15→16→17 then 18 ∥ 19, 20 after 19, 21 after 16+17+19, 22 after 21. Phase 23 (CR-01/CR-02 + active sessions UI) parallel-eligible with anything.

---

## Key Findings

### Stack

- **Zero new runtime deps.** ARQ 0.26 cron, ptb-22 `CommandHandler` list, plain Postgres enum + UPDATE for lifecycle, stdlib `datetime` + `zoneinfo` cover everything.
- **Optional dev dep:** `time-machine>=2.16,<3` if cron / gym-hours tests grow brittle. Defer until pain forces it.
- **Rejected libraries:** APScheduler (use ARQ cron), pg_cron (out of scope, infra), `transitions`/`python-statemachine` (3 states, 2 transitions — 3-line UPDATE wins), `pendulum` (stdlib + zoneinfo sufficient since Russia abolished DST in 2014), anti-fraud libraries (uniqueness constraint, not detection problem).
- **One placeholder cleanup:** delete `apps/backend/app/workers/scheduler.py` placeholder during Phase 18 — its TODO is fulfilled by `cron_jobs` directly on `WorkerSettings`.
- **Compose topology gets a 5th service:** `arq-worker` (`uv run arq app.workers.WorkerSettings`) — mirrors precedent of bot worker as separate process.

### Features

- **Locked v1.2 scope is sound.** Every domain item maps cleanly to RU-market table stakes (FitBase, 1С:Фитнес-клуб, fitness365, impulseCRM all have plan catalog + snapshot instance + active/expired/cancelled tri-state + 1/day cap + gym-hours window).
- **Three "free" column additions strongly recommended** in Phase 17 migration: `paid_at TIMESTAMPTZ NULL` (seeds v1.3 billing), `notes TEXT NULL` (operational reality), `activation_policy VARCHAR DEFAULT 'purchase_date' CHECK (activation_policy = 'purchase_date')` (forward-compat for v1.3 first-visit activation). Zero-cost now, expensive later.
- **Top cheap-win differentiators (D-1…D-7) — pure-read views over locked tables.** Best ROI: D-3 ("истёк сегодня" red badge in client list), D-2 (filter "expiring within N days"), D-5 (TG-bot reply with days-remaining on success). Pick 3-4 for Phase 22.
- **Anti-features explicitly rejected:** per-class booking, family memberships, visit-count plans, freeze, proportional refund, expiring-soon notifications, trainer commissions, CSV import, photo upload, websockets-driven "who's in the gym now" (poll instead), multi-gym, audit-log read API. Each has a "when to reconsider" in FEATURES.md so v1.2 planners can defend scope.
- **Anti-fraud verdict — gym-hours + 1/day is sufficient for honest single-gym pet project.** Telegram-bot binding to `telegram_chat_id` is higher friction than card-swap; reception-collusion vector exists but constrained by mandatory active-membership validation + audit log + (in pet-project context) owner often IS the reception. Real RU clubs use photo+biometrics at turnstile; v1.2 deliberately rejects that hardware tier. Document accepted residual risk in PROJECT.md Key Decisions in Phase 15.

### Architecture

- **Visits → Memberships dependency** via `ActiveMembership` Protocol callback in `core/dependencies.py` registered from `app/main.py`. Direct mirror of `register_user_loader` (`app/core/dependencies.py:44-61`, `app/main.py:88`). FK at DB level (string ref, no Python import).
- **ARQ scheduled job placement** in `app/workers/scheduled/expire_memberships.py`, importing `app.modules.memberships.service`. No `workers ⊥ modules` contract exists (verified in `apps/backend/.importlinter`). Documented as **D-09** parallel to D-06.
- **Telegram bot `/checkin` handler** via `HandlerContext.visits_service: ModuleType` extension (NOT direct import in `handlers.py` — would violate `integrations-not-depend-on-modules`). Anti-fraud lives in `visits.service` so reception manual + bot self check-in share validation. Documented as **D-10** parallel to D-06.
- **audit_log already centralized.** Pure stateless `audit.emit(...)` in `core/audit.py`; new modules write identically to `clients.service`. Add 10 new locked event names: `membership_plan_*` (3), `membership_*` (3), `visit_*` (4).
- **admin-web client-detail composition — Pattern α (route IS the page).** `routes/_protected/clients.$clientId.tsx` composes via `Promise.all(ensureQueryData)` in loader; `MembershipsBlock` and `RecentVisitsBlock` exported from their own features and consumed by the route — never `features/clients` importing them. Verify `eslint.config.js` `import/no-restricted-paths` rules in Phase 22 plan.

### Pitfalls (BLOCKER ranks)

1. **Service write paths missing `await session.commit()`** (Phase 12.1 reprise) → Phase 15 ships `BusinessService` template + AST gate verifying every `service.py` write path explicitly commits.
2. **Snapshot pricing not copied** → Phase 17 schema MUST include `price_kopecks_snapshot`/`duration_days_snapshot`/`plan_name_snapshot` NOT NULL at insert; `MembershipPlan` FK uses `ON DELETE RESTRICT` so plans can't be hard-deleted while instances exist.
3. **Visit `1/day` race window via app-layer check** → Phase 19 migration adds Postgres UNIQUE INDEX on `(client_id, gym_date)` with `gym_date GENERATED ALWAYS AS ((checked_in_at AT TIME ZONE 'Europe/Moscow')::date) STORED`. Concurrent-request test in Phase 19: 10 parallel → 1×201 + 9×409.

### Pitfalls (HIGH)

- **End_date calendar math** — days-only model (no `relativedelta` weirdness on Jan 31 + 30 days); end_date computed once at sell time, never recomputed. **Inclusive semantics** (last valid check-in day = `end_date`); ARQ filter uses strict `<`.
- **ARQ `expire_memberships` not idempotent** → use `UPDATE … WHERE end_date < CURRENT_DATE AND status='active' RETURNING id` in single transaction. ARQ `unique=True` + `keep_cronjob_progress=60` does NOT protect against worker-restart re-runs (verified: ARQ issue #193). Idempotency must be SQL-level.
- **ILIKE search forgets CR-01 escape pattern** → promote `_escape_like_pattern` from `clients/repository.py` to `core/sql.py`. Future modules import without `modules-independent` violation.
- **import-linter drift via TYPE_CHECKING/Protocol abuse** — visits never `from app.modules.memberships import ...` even under `TYPE_CHECKING`. The `ActiveMembership` Protocol lives in `core/dependencies.py`, not in memberships.
- **Bot `/checkin` DM oracle leak** — single generic Russian failure DM. Precise reason audit-only, NEVER include client name / end_date / hours / membership status in DM. Owner copy review before Phase 20 merge.
- **Bot replay / friend-fraud** — Redis `update_id` dedup with key-prefix discipline alongside `arq:*` and `sz:session:*`. Accept residual risk for v1.2 single-zal scope; lock as Key Decision in Phase 15.
- **Audit log taxonomy drift** — frozenset of `(action, resource_type)` tuples in `core/audit.py`; `audit.emit` validates at call. Test that walks every new event added in v1.2.
- **OpenAPI drift on schema add** — `BackendSchemaBase` (camelCase + `populate_by_name=True`) template; ruff `UP007` enforces `X | None` not `Optional[X]` (Pydantic v2 schema differences).

---

## Cross-Research Conflicts Resolved

| Topic | Conflict | Resolution |
|---|---|---|
| `paid_at` / `notes` / `activation_policy` columns | FEATURES recommends adding (M-7/M-9/M-8); ARCHITECTURE schema sketch omits | **Add per FEATURES** — zero runtime cost, saves v1.3 migration cost. Phase 17 plan-author includes them. |
| `end_date` inclusive vs exclusive | ARCHITECTURE Protocol comment: exclusive; FEATURES + PITFALLS: inclusive | **Inclusive wins** — matches client expectation "купил на месяц до 30 числа = тренируюсь 30-го числа". ARQ filter `end_date < CURRENT_DATE AT TIME ZONE 'Europe/Moscow'` (strict `<`). Lock in Phase 15 Key Decisions. |
| 1/day index mechanism | STACK/FEATURES/ARCHITECTURE: partial unique on date expression; PITFALLS: STORED GENERATED `gym_date` column + UNIQUE on `(client_id, gym_date)` | **PITFALLS approach wins** — generated column prevents app from writing wrong value; Phase 19 migration uses `GENERATED ALWAYS AS (...) STORED`. |
| ARQ daily tick time | STACK `hour=3, minute=5` UTC; ARCHITECTURE `hour=3, minute=15` (TZ unspecified); PITFALLS "03:05 MSK" | **Defer to Phase 18 plan** — recommend UTC tick `hour=3, minute=5` (06:05 MSK), document MSK conversion in WorkerSettings docstring. Container `TZ=UTC`. |
| `/checkin` cross-module shape | STACK "decision deferred"; ARCHITECTURE "extend HandlerContext"; PITFALLS aligns | **Aligned — extend `HandlerContext` with `visits_service: ModuleType`**, document as D-10. |
| State-machine library | STACK rejects (3 states, 2 transitions); PITFALLS adds Postgres CHECK + transition matrix unit test | **Aligned — plain enum + CHECK constraint + service-layer guards + transition test.** No library. |

---

## Build Order — Suggested Phase Sequence

```
15 → 16 → 17 ┬→ 18
             └→ 19 → 20 → 21 → 22

23 (independent — anywhere)
```

| # | Phase | Inputs | Outputs |
|---|-------|--------|---------|
| **15** | **Foundations: RBAC parity + audit taxonomy + helper hoisting** | none | `Action.{CREATE, CANCEL, CHECK_IN}`, `Resource.{MEMBERSHIPS, MEMBERSHIP_PLANS, VISITS}`, `OWNER_ONLY` extensions both sides; TEST-06 byte-paritet extended; `BusinessService` template + AST commit gate; `_escape_like_pattern` hoisted to `core/sql.py`; audit taxonomy frozenset; `BackendSchemaBase`; **Key Decisions:** inclusive `end_date`, `gym_date` definition, accepted residual fraud risk. |
| **16** | **Memberships DB + plans CRUD backend** | 15 | Alembic 0004 (`membership_plans` table); module template; `/api/v1/membership-plans` 4 routes (owner-only); audit events `membership_plan_*`. |
| **17** | **Membership instances backend (sell + cancel + resolver)** | 16 | Alembic 0005 (`memberships` with snapshots + `paid_at` + `notes` + `activation_policy CHECK`); `service.create_membership` (computes `end_date` once); `service.cancel_membership` (transition guard); `service.resolve_active_membership_by_client` (latest `end_date` then `created_at DESC`); `register_active_membership_resolver` Protocol; `app/main.py` wiring; `/api/v1/memberships` 4 routes; transition matrix tests; Postgres CHECK on status. |
| **18** | **ARQ scheduled `expire_memberships`** ∥ 19 | 17 | `app/workers/scheduled/expire_memberships.py` (D-09); `WorkerSettings.cron_jobs`; idempotent `UPDATE … RETURNING id`; `on_job_start`/`on_job_end` `job_id` contextvars binding; new docker-compose `arq-worker` service; patched-clock double-run test. Delete `scheduler.py` placeholder. |
| **19** | **Visits DB + reception check-in backend** ∥ 18 | 17 | Alembic 0006 (`visits` with STORED GENERATED `gym_date` + UNIQUE + channel ENUM + `checked_in_by` FK); module template; shared anti-fraud helpers (gym hours from env + active-membership lookup via core resolver); `/api/v1/visits` 3 routes; concurrent-request test (10 parallel → 1×201 + 9×409). |
| **20** | **Telegram bot `/checkin`** | 19 | `HandlerContext.visits_service` (D-10); `checkin_handler` with single generic Russian failure DM; `service.create_visit_self_checkin`; Redis `update_id` dedup; `visit_rejected_bot` vs `visit_rejected_reception` audit events. Owner Russian-copy sign-off. |
| **21** | **OpenAPI drift gate refresh + api-client codegen** | 16, 17, 19 | Regen `apps/backend/openapi.json`; `pnpm --filter @sportzal/api-client codegen`; commit both; CI green. |
| **22** | **admin-web wiring (memberships + visits)** | 21 | `features/memberships`, `features/visits`; new routes `/_protected/memberships.tsx`, `/_protected/membership-plans.tsx` (owner-only via `beforeLoad`), `/_protected/visits.tsx`; client-detail Pattern α (route IS page; `Promise.all(ensureQueryData)` in loader); reception UX edge cases (expired-today / already-today / multi-phone-match); cheap-wins D-2/D-3/D-5/D-1 per budget. |
| **23** | **Hygiene + v1.1 carryover** ∥ anywhere | none | Phase 04 CR-01 (Argon2 verify-error → 401), CR-02 (invalid UUID in cookie → 401), active sessions UI + revoke. |

### Dependencies and Parallelization

- 15 must finish first — RBAC contract that 16/17/19 all depend on.
- 18 and 19 are parallelizable after 17 (no shared code beyond the resolver from 17).
- 20 must wait for 19 (handler imports `visits_service`).
- 21 cannot start until 16+17+19 are merged — OpenAPI drift gate is byte-stable.
- 22 cannot start until 21 — admin-web codegen depends on `schema.d.ts` from 21.
- 23 is fully independent — touches Phase 4 auth code + frontend session UI.

---

## Research Flags for Plan-Phase

**Needs deeper plan-time research:**

- **Phase 18 (first real ARQ cron):** validate `unique=True` on docker restart, `keep_cronjob_progress=60` semantics, `on_startup` cron-resolves assertion, design `job_id` contextvars convention for structlog binding.
- **Phase 20:** Russian copy review with owner; Redis `update_id` dedup design with key-prefix discipline alongside `arq:*` and `sz:session:*`; accepted-residual-risk Key Decisions entry in PROJECT.md.

**Standard patterns — skip deeper research:**

- Phase 15 — extends three v1.1 patterns (RBAC parity, audit taxonomy, repository helper hoisting).
- Phases 16/17/19 — full mirror of `clients` module template (validated v1.1).
- Phase 21 — rerun of v1.1 Phase 9 (OpenAPI drift gate established).
- Phase 22 — rerun of v1.1 Phases 10/11/13. Only Pitfall 12 (waterfall + stale-while-revalidate) is novel and addressed by the route loader pattern.
- Phase 23 — micro-fixes.

---

## Open Decisions for Plan-Phase Authors

1. **`Action.CREATE` vs reusing `EDIT`** (Phase 15) — recommend introducing CREATE + CANCEL for clarity.
2. **Gym hours config location** (Phase 19) — recommend env vars `GYM_HOURS_START` / `GYM_HOURS_END` (Europe/Moscow); tunable per deploy without redeploy.
3. **`end_date` inclusive semantics** (Phase 15) — lock as PROJECT.md Key Decision; ARQ filter strict `<`.
4. **`activation_policy` "now-vs-later"** (Phase 17) — ship column NOW with single CHECK value `'purchase_date'`, widen the CHECK in v1.3.
5. **ARQ cron timezone + slot** (Phase 18) — recommend container `TZ=UTC` + `hour=3, minute=5` (06:05 MSK).
6. **Multiple-overlapping-active-memberships tiebreak** (Phase 17) — latest `end_date`, then `created_at DESC`. Document explicitly in resolver docstring.
7. **Russian DM copy lock** (Phase 20) — single generic failure string; owner sign-off before merge.
8. **Reception UX edge cases** (Phase 22) — pre-fetch today's visit + channel badge; top-5 phone-prefix search results.

---

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Stack additions (none required) | HIGH | Context7 verification of ARQ 0.26.3 + ptb-22.5; no library introduces incompatibility |
| Architecture integration | HIGH | Direct repo reads; `register_user_loader` precedent; `.importlinter` contracts inspected |
| Pitfall coverage | HIGH | Grounded in v1.1 retrospective + Phase 12.1 incident + ARQ issue #193 |
| Feature scope (RU market) | MEDIUM-HIGH | Triangulated from FitBase, 1С:Фитнес-клуб, fitness365, impulseCRM, Sigur primary docs |
| Anti-fraud sufficiency | MEDIUM | Argument is structural (TG account-binding > card-swap friction; owner=reception in pet-project) — sound logic but assumption-heavy. Document accepted residual risk explicitly. |
| Build order + dependencies | HIGH | Falls out of file-level inspection of cross-module edges |

**Gaps to flag for plan-phase:**

- Pattern α vs β admin-web confirmation needs `eslint.config.js` `no-restricted-paths` read in Phase 22 plan.
- ARQ `keep_cronjob_progress` docker-restart end-to-end validation pending in Phase 18.
- Russian DM copy needs explicit owner sign-off before Phase 20 merge.
- Pitfall 9 (residual friend-fraud risk acceptance) must land in PROJECT.md Key Decisions during Phase 15, not buried in comments.

---

## Ready for Requirements

All four research files (STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md) on disk. Cross-research conflicts resolved with concrete decisions. Pitfalls mapped to phases. Build order derived from dependency analysis with parallelization noted. Orchestrator can proceed to REQUIREMENTS.md definition + ROADMAP creation.
