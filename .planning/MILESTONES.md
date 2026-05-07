# Milestones

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
