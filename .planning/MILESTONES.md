# Milestones

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
