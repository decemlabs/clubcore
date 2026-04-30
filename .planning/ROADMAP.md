# Roadmap: Sportzal — Phase A (Skeleton)

## Overview

Phase A is a **skeleton-only** milestone: zero business features, zero auth, zero business tables. The journey is foundation → backend skeleton with enforced architecture → tests/infra/docs that make the skeleton verifiable and runnable. Three coarse phases mapped from 47 v1 requirements. Phase 1 lays the monorepo so subsequent phases have a place to land. Phase 2 brings up the FastAPI modular monolith with quality tooling enforceable from day one. Phase 3 makes everything testable, locally runnable via Docker, and documented.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Monorepo Restructure & Frontend Move** — Establish `apps/`/`packages/`/`infra/` skeleton at repo root and relocate the existing `frontend/` into `apps/admin-web/` without rewriting it. **Completed 2026-04-30.**
- [ ] **Phase 2: Backend Skeleton with Quality Tooling** — Bring up the FastAPI modular monolith (`apps/backend/app/`) with `core`/`modules`/`integrations`/`workers`/`api`, the single real endpoint `GET /healthz`, async Alembic config, and ruff + mypy strict + import-linter contracts enforced from day one.
- [ ] **Phase 3: Tests, Dev Infrastructure & Documentation** — Add pytest scaffold (httpx ASGITransport), Dockerfile + dev `docker-compose.yml` (backend + Postgres 16 + Redis 7), placeholder scripts, and architecture/conventions/ADR docs.

## Phase Details

### Phase 1: Monorepo Restructure & Frontend Move
**Goal**: Repo root presents the monorepo skeleton (`apps/`, `packages/`, `infra/`) and the existing frontend SPA lives at `apps/admin-web/` unchanged, ready for backend work to land alongside it without conflict.
**Depends on**: Nothing (first phase)
**Requirements**: MONO-01, MONO-02, MONO-03, MONO-04, MONO-05, MONO-06
**Success Criteria** (what must be TRUE):
  1. Repo root contains `apps/admin-web/`, `packages/ui/`, `packages/api-client/`, `infra/docker/`, `infra/nginx/`, and `pnpm-workspace.yaml`; no top-level `frontend/` directory remains and `apps/client-web` does NOT exist.
  2. Running `pnpm install` from repo root succeeds and resolves the `apps/admin-web` workspace plus the two placeholder packages.
  3. Running `pnpm --filter admin-web dev` (or equivalent existing script) starts the existing Vite dev server on port 5173 with all FSD-lite layers, mocks, RBAC, theme, i18n, and ESLint chokepoints behaving exactly as before the move.
  4. Running `pnpm --filter admin-web test` from the repo root passes the existing Vitest suite without modification of test files.
  5. `packages/ui/` and `packages/api-client/` each contain only `package.json` + `README.md` (no source code).

**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md — Scaffold monorepo skeleton (pnpm-workspace.yaml, packages/ui, packages/api-client, infra/docker, infra/nginx)
- [x] 01-02-PLAN.md — Move frontend/ to apps/admin-web/ verbatim (clean-collapse frontend/.git per D-01)
- [x] 01-03-PLAN.md — Reconcile root lockfile + run full D-16 verification battery (typecheck/lint/lint:fixtures/test/build/dev smoke)

**Open questions** (resolved during /gsd-discuss-phase 2026-04-30):
  - ~~`frontend/.git` strategy~~ → **RESOLVED** as clean collapse (`rm -rf frontend/.git`) per locked decision D-01 in `.planning/phases/01-monorepo-restructure-frontend-move/01-CONTEXT.md`.

### Phase 2: Backend Skeleton with Quality Tooling
**Goal**: A runnable FastAPI modular monolith exists at `apps/backend/app/` with the architectural style (`core` / `modules` / `integrations` / `workers` / `api`) physically realized, only `GET /healthz` as a real endpoint, Alembic configured async with empty `versions/`, and ruff + mypy strict + import-linter contracts that fail loudly on any violation.
**Depends on**: Phase 1
**Requirements**: BE-01, BE-02, BE-03, BE-04, BE-05, BE-06, BE-07, BE-08, BE-09, BE-10, MOD-01, MOD-02, MOD-03, INT-01, INT-02, WORK-01, WORK-02, WORK-03, API-01, API-02, API-03, DB-01, DB-02, TOOL-01, TOOL-02, TOOL-03, TOOL-04, TOOL-05, TOOL-06
**Success Criteria** (what must be TRUE):
  1. Running `uv sync` in `apps/backend/` resolves all backend dependencies (FastAPI 0.115+, SQLAlchemy 2.0 async, Alembic, Pydantic v2 + pydantic-settings, asyncpg, structlog, ARQ, redis, httpx, pytest, ruff, mypy, import-linter) against Python 3.12.
  2. Running `uv run uvicorn app.main:app --factory` starts the API and `curl http://localhost:8000/healthz` returns HTTP 200 with body `{"status":"ok"}`.
  3. Running `uv run lint-imports` (import-linter) exits 0 against the current tree, AND a synthetic test import of `app.modules.X` from `app.core.*`, or of `app.modules.Y` from `app.modules.X`, causes it to fail.
  4. Running `uv run ruff check .` and `uv run mypy app` both pass on the skeleton with strict mypy and the configured ruff rule set (E, F, I, B, UP, ASYNC, S, …).
  5. Running `uv run alembic upgrade head` succeeds against an empty database (no migration files in `alembic/versions/`, only `.gitkeep`); `alembic/env.py` reads the async DATABASE_URL from `Settings`.
  6. The Python package is named `app` (importable as `from app.main import create_app`); `app/modules/{auth,members,memberships,visits,trainers,schedule,bookings,billing,notifications}/__init__.py` all exist and contain no business logic; `app/integrations/{telegram,email}/` contain only placeholder modules with zero real Telegram/SMTP calls.

**Plans**: TBD

### Phase 3: Tests, Dev Infrastructure & Documentation
**Goal**: The skeleton becomes verifiable and operable: pytest passes including a real `/healthz` integration test via `httpx ASGITransport`, the full local dev stack comes up via `docker compose`, and architecture/conventions/ADR documents capture the modular-monolith decision so the next milestone has unambiguous ground rules.
**Depends on**: Phase 2
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04, INFRA-01, INFRA-02, INFRA-03, INFRA-04, DOCS-01, DOCS-02, DOCS-03, DOCS-04
**Success Criteria** (what must be TRUE):
  1. Running `uv run pytest` from `apps/backend/` passes, including `tests/integration/test_healthz.py` (asserts 200 + body shape via `httpx.AsyncClient` over `ASGITransport`) and `tests/unit/test_security.py` placeholder; `tests/conftest.py` exposes `app`, `async_client`, and `db_session` fixtures.
  2. Running `docker compose up` from `apps/backend/` builds the multi-stage `Dockerfile` and starts `backend`, `postgres:16`, and `redis:7`; `curl http://localhost:8000/healthz` returns 200 against the containerized backend.
  3. Running `uv run python apps/backend/scripts/seed_demo_data.py` prints `"Phase A: no data to seed"` and exits 0; running `apps/backend/scripts/backup_db.sh` against the local Postgres container produces a non-empty `pg_dump` output file.
  4. `apps/backend/docs/architecture.md`, `docs/conventions.md`, `docs/adr/0001-modular-monolith.md`, and `apps/backend/README.md` exist and consistently describe the modular monolith, the `core ⊥ modules` and inter-`modules` import-linter contracts, the test approach, and the `uv sync` / `docker compose up` / `pytest` quick-start.

**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Monorepo Restructure & Frontend Move | 3/3 | Complete | 2026-04-30 |
| 2. Backend Skeleton with Quality Tooling | 0/TBD | Not started | - |
| 3. Tests, Dev Infrastructure & Documentation | 0/TBD | Not started | - |

---
*Roadmap created: 2026-04-30*
*Granularity: coarse (3 phases)*
*Coverage: 47/47 v1 requirements mapped*
