# Milestones

## v1.2 Memberships + Visits (Shipped: 2026-05-08)

**Phases completed:** 9 phases (15–23), 36 plans, 60 tasks
**Requirements:** 63/63 satisfied (2 accepted-at-planning deviations carried forward as v1.3 tech-debt: MEM-04 D-13, MEM-PLAN-EP-04 D-15)
**Code:** ~8.1K LOC backend Python (`apps/backend/app/`), ~16.8K LOC TypeScript (`apps/admin-web/src/`)
**Timeline:** 2026-05-07 → 2026-05-08 (rapid follow-on after v1.1 close), 166 commits (37 feat), 404 files changed (+39,142 / −1,173)
**Audit:** passed — re-audited 2026-05-08T16:30 after closing the two procedural gaps (Phase 22 stale verification + Phase 18 ARQ-03 prose decision); see `.planning/milestones/v1.2-MILESTONE-AUDIT.md`
**Known deferred items at close:** 1 (quick-task `260501-ndi` metadata flag carried over from v1.1; commit 71f28de shipped) + 6 `human_verification:` smoke items in 22-VERIFICATION.md awaiting an ops session with live backend / Telegram sandbox

**Key accomplishments:**

- **RBAC + audit + service-write commit gate (Phase 15)** — `Action.{CREATE, CANCEL, CHECK_IN}` + `Resource.{MEMBERSHIPS, MEMBERSHIP_PLANS, VISITS}` extended; `OWNER_ONLY` frozenset gained 6 entries (plan-catalog mutations + membership cancel/delete) while reception kept `(CREATE, MEMBERSHIPS)` + `(CHECK_IN, VISITS)`; three-way parity test (backend ↔ admin-web `can.ts` ↔ `registry.ts`) extended; `LOCKED_AUDIT_EVENTS` 28-entry frozenset enforced via `audit.emit` literal-string AST gate; `BackendSchemaBase` (Pydantic 2.11 canonical pair) replaced the deprecated `populate_by_name`; `BusinessService` SVC001 commit-gate AST walker fails CI on missing `await session.commit()` in any module write path; `core/sql.py:escape_like_pattern` hoisted from `clients/repository.py` for reuse without breaching `modules-independent` import-linter contract.
- **Memberships catalog + instances + resolver (Phases 16–17)** — `membership_plans` table (BIGINT kopecks, partial unique on `lower(name) WHERE deleted_at IS NULL`) + 5 owner-only endpoints with CSRF; `memberships` table with mandatory snapshot pricing (`plan_name_snapshot`/`duration_days_snapshot`/`price_kopecks_snapshot` NOT NULL) and `ON DELETE RESTRICT` FK to plans; **inclusive `end_date` semantics locked** — last valid check-in day = `end_date`; cancel guards (only `active → cancelled`, return 409 `invalid_transition` otherwise); `resolve_active_membership_by_client` exposed via Protocol slot in `core/dependencies.py` and registered from `app/main.py` — the v1.2 mirror of v1.1 `register_user_loader`. Phase 16 D-15 closed in Phase 17: `soft_delete_plan` now translates the FK IntegrityError to 409 `plan_in_use`.
- **ARQ scheduled `expire_memberships` (Phase 18)** — 06:05 Europe/Moscow daily tick (container `TZ=UTC` + `cron(hour=3, minute=5, unique=True, keep_result=60)`); single-statement idempotent `UPDATE ... RETURNING` with one `audit.emit("membership_expired", actor_user_id=None, ...)` per row; thin transaction-owner coroutine `expire_memberships(ctx) -> int` opens session from `ctx['sessionmaker']`, awaits `session.commit()`, emits locked `expire_memberships_complete count=N` summary log; canonical `WorkerSettings` at `app.workers.WorkerSettings` with `on_startup` cron-resolution invariant + `on_job_start`/`on_job_end` structlog `job_id`/`job_name` contextvars (Pitfall 14 RequestIdMiddleware mirror); 5th `arq-worker` docker-compose service. ARQ-TEST-01 (correctness, inclusive-`end_date` stays active) + ARQ-TEST-02 (idempotency) + 11 unit tests locking `WorkerSettings` shape under real Postgres + SAVEPOINT-isolated rollback.
- **Visits — race-proof DB enforcement + reception + Telegram self-checkin (Phases 19–20)** — `visits` table with `gym_date GENERATED ALWAYS AS ((checked_in_at AT TIME ZONE 'Europe/Moscow')::date) STORED` + `UNIQUE (client_id, gym_date)` so 1-per-day-per-client wins at the **DB layer, not app-layer** (proven by VIS-TEST-01 concurrent race test on real Postgres 16); reception `POST /api/v1/visits` with three rejection branches (`outside_gym_hours` / `no_active_membership` / `duplicate_checkin`) returning 409 with discriminating `code`; `GET /api/v1/visits/_meta` exposing gym-hours window with `Cache-Control: public, max-age=300`; Telegram bot `/checkin` handler via `HandlerContext` (D-10 worker→visits_service relaxation parallel to D-06 telegram_service); 4 owner-locked Russian DM strings (no oracle-leak — never includes client name, end_date, hours, or membership status); Redis `update_id` dedup at `sz:bot:update:{update_id}` (TTL 1h); 569-test backend suite green.
- **OpenAPI drift gate + admin-web wiring (Phases 21–22)** — byte-stable `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` regenerated with new operations for membership-plans / memberships / visits / sessions / `_meta`; admin-web ships the full v1.2 flow on `VITE_API_MODE=http`: `/membership-plans` (owner-only), `/memberships`, `/visits` reception check-in covering all 4 FE-08 edge cases (top-5 disambiguation, already-checked-in HH:MM badge, expires-today informational badge, outside-hours disable + tooltip), `/clients/$clientId` Pattern α route (Promise.all loader of 3 `ensureQueryData` calls + ESLint `import/no-restricted-paths` zone forbidding `features/clients → features/{memberships,visits}`), `/profile` active-sessions UI consuming HYG-03 endpoints; cheap-win differentiators D-2 (expiring-7-days filter), D-3 ("expires today" badge with correct copy after BLK-03 fix), D-5 (Telegram DM days-remaining with two locked Russian variants); 184 admin-web tests + 8 backend `_meta`/days-remaining tests green.
- **Auth hygiene — login error path + active sessions backend (Phase 23)** — HYG-01: `/auth/login` Argon2 verify-error returns 401 `invalid_credentials` (was 500), structlog WARNING captures the verify-error reason; HYG-02: tampered `sz_access`/`sz_refresh` cookie returns 401 `invalid_session` (was 500) — auth dependency catches `InvalidUUID` explicitly; HYG-03: `GET /api/v1/auth/sessions` lists active session families and `POST /api/v1/auth/sessions/{family_id}/revoke` (CSRF) revokes a single family — feeds FE-09 SessionsList + LogoutAllDialog on the new `/profile` route accessible to both roles.

---

## v1.1 Auth + Clients (Shipped: 2026-05-07)

**Phases completed:** 11 phases (4–14, including 3 gap-closure phases 12/13/14 + inline quick-fix Phase 12.1), 63 plans, 101 tasks
**Requirements:** 70/70 satisfied
**Code:** ~4.4K LOC backend Python, ~12.8K LOC TypeScript (admin-web + api-client)
**Timeline:** 2026-05-02 → 2026-05-07 (5 days, 341 commits, 74 feat)
**Audit:** passed (`.planning/milestones/v1.1-MILESTONE-AUDIT.md`)
**Known deferred items at close:** 4 (3 advisory UAT scenarios, 1 quick-task metadata flag — see STATE.md `## Deferred Items`)

**Key accomplishments:**

- **Auth foundations & wire-format contract** — JWT HS256 + Argon2id + CSPRNG token generators + httpOnly cookie pair (`sz_access`/`sz_refresh`) + CSRF dependency; Pydantic `alias_generator=to_camel` + `populate_by_name=True` flips the wire format to camelCase; pagination contract unified to `{items, total, page, pageSize}`; `MetaData(naming_convention=...)` + `UUIDPkMixin`/`TimestampMixin`/`SoftDeleteMixin` set before the first business migration. (Phase 4)
- **Email/password auth + refresh-rotation family** — `/auth/login|refresh|logout|logout-all|me` end-to-end; refresh tokens stored hashed in Postgres with `family_id`, ~5s reuse-window race tolerance, `family_reuse_detected` audit on replay; Redis-mirrored sessions; SAVEPOINT-based `db_session` fixture for per-test isolation against real Postgres; rate-limit (5/15min → 429). (Phase 5)
- **Server-side RBAC at FE parity** — `Role`/`Action`/`Resource` StrEnums + 9-entry `OWNER_ONLY` frozenset byte-equal to admin-web `can.ts`; `Depends(require_permission)` on every business route (route-introspection guard enforces it); `verify_csrf` dependency on POST/PATCH/DELETE; three-way parity test (backend ↔ admin-web `can.ts` ↔ `registry.ts`). (Phase 6)
- **Telegram OTP channel** — separate `python -m app.workers.telegram_bot` ptb-22 long-polling worker (4th docker-compose service, `restart: unless-stopped`); deep-link `/start <token>` flow → 6-digit DM (TTL 5min, max 5 attempts) → `/auth/telegram/verify` upsert by `telegram_chat_id`; 409 `bot_not_started` returns the deep-link URL when DM is blocked. (Phase 7)
- **Clients module + audit log** — first business CRUD with E.164 phone validation, partial unique index `WHERE deleted_at IS NULL` so soft-deleted phones can be reused, `pg_trgm` GIN-indexed ILIKE search, owner-only soft-delete; `audit_log` table with writes from auth (login/logout/otp/family-reuse) and clients (create/update/soft-delete); Phase 14 hardened the search by escaping `%`/`_`/`\` so reception can't dump the roster via `?q=%`. (Phases 8 + 14)
- **OpenAPI drift gate + typed api-client + admin-web wiring** — lifespan-safe `export_openapi.py` writes byte-stable `apps/backend/openapi.json`; CI `git diff --exit-code` on backend spec AND on `openapi-typescript`-generated `packages/api-client/src/schema.d.ts`; `fetcher.ts` exposes generic `request<P, M>` with `credentials: 'include'`, automatic `X-CSRF-Token`, single-flight `/auth/refresh` on 401; admin-web `/login` (email/password + Telegram OTP tabs) and `/clients/*` fully wired through `VITE_API_MODE=http` swap-seam, all other domains stay on mocks (no regression). (Phases 9, 10, 11, 13)

---

## v1.0 Phase A: Skeleton (Shipped: 2026-05-01)

**Phases completed:** 3 phases, 17 plans, 36 tasks

**Key accomplishments:**

- Repo-root pnpm-workspace.yaml plus two minimal-placeholder packages (@sportzal/ui, @sportzal/api-client) and tracked-empty infra/docker + infra/nginx — structural foundation for the frontend move in plan 02.
- Verbatim relocation of the React 19 SPA from `./frontend/` to `apps/admin-web/` with a clean-collapse drop of the legacy `frontend/.git` sub-repo — 820 files staged into the root repo's history without a single byte of source modification.
- Single root `pnpm-lock.yaml` is authoritative; full D-16 verification battery (typecheck/lint/lint:fixtures/test/build + dev-server smoke) all green from the new `apps/admin-web/` location after a Rule-4 deviation added the missing `eslint-import-resolver-typescript` devDependency.
- apps/backend/ scaffolded with six tooling configs (uv pyproject, ruff, mypy strict, three import-linter contracts, alembic, env example, gitignore) and legacy empty root backend/ removed — ready for `uv lock` and Python source in subsequent plans.
- `uv lock` resolved 52 packages against Python 3.12; `uv sync` installed apps/backend/.venv with fastapi 0.136.1, sqlalchemy 2.0.49, mypy 1.20.2, ruff 0.15.12, import-linter 2.11 and the rest of the locked stack — all five dev tools invocable via `uv run` and all 11 runtime deps importable.
- Wrote the entire `app/core/` infrastructure layer (10 files, 246 lines): Settings + cached get_settings(), async DB lifespan with engine on app.state, structlog config with contextvars-aware processor chain, AppError hierarchy + JSONResponse handler, request-id + timing ASGI middleware with REVERSED add order, and pagination primitives — all passing ruff (12 rule packs), ruff format, and mypy strict + pydantic.mypy plugin.
- 1. [Rule 1 - Linter] Multi-line reformat of `billing/__init__.py` docstring
- 1. [Rule 1 - Linter] Added `ClassVar` wrapper to `WorkerSettings.functions` typing
- Wired the API surface: `app/main.py:create_app()` factory plus the four-file router chain mounting `GET /healthz` at the root URL. End-to-end smoke test (httpx ASGITransport) returns `200` + `{"status":"ok"}` and the timing log carries `request_id` (REVERSED middleware order works as designed). All 44 source files pass `ruff check` and `mypy strict`.
- Async Alembic env.py reading Settings.database_url via async_engine_from_config + run_sync cookbook, plus standard script.py.mako and empty versions/.gitkeep — wired for asyncpg-driven migrations.
- Phase 2 verification battery: ruff + mypy strict + lint-imports clean + synthetic-violation D-05 GREEN + /healthz returns 200 with X-Request-ID + alembic live-run formally deferred to Phase 3 (no Postgres in env). Phase 2 is COMPLETE.
- One-liner:
- Two utility scripts for the Phase A backend: a pure-stdlib placeholder seeder that prints the exact INFRA-03 string, and a working pg_dump-via-compose backup script with a `.gitignore` carve-out for the output directory.
- 1. [Rule 3 — Blocking] Removed literal `mermaid` token from architecture.md `## Диаграмма` description
- Two surgical environment: blocks added to backend and migrate services so docker-compose containers reach postgres:5432 and redis:6379 instead of localhost — closes CR-01 without forking .env files.

---
