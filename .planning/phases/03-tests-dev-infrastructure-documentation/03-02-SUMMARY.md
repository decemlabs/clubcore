---
phase: 03-tests-dev-infrastructure-documentation
plan: 02
subsystem: backend-dev-infra
tags: [docker, multi-stage, uv, python-3.12, security, infra-01]
requirements: [INFRA-01]
one_liner: "Multi-stage Dockerfile (uv builder → bare python:3.12-slim-bookworm runtime, non-root `app` user) and .dockerignore for apps/backend/"

dependency_graph:
  requires:
    - "apps/backend/pyproject.toml (Phase 2 — defines deps + dev-deps split)"
    - "apps/backend/uv.lock (Phase 2 — committed, --frozen contract)"
    - "apps/backend/app/ (Phase 2 — modular monolith package)"
    - "apps/backend/alembic/ + apps/backend/alembic.ini (Phase 2 — async migrations)"
  provides:
    - "apps/backend/Dockerfile — runnable image artifact for INFRA-02 compose (Plan 03-05)"
    - "apps/backend/.dockerignore — lean build context, secret-leakage protection"
  affects:
    - "Plan 03-05 (docker-compose.yml) — both `backend` and `migrate` compose services build from this Dockerfile"
    - "Phase 2 SC #5 retirement — `migrate` service running `alembic upgrade head` against compose Postgres becomes possible once this image exists"

tech_stack:
  added:
    - "Docker multi-stage build (BuildKit syntax 1.7)"
    - "ghcr.io/astral-sh/uv:python3.12-bookworm-slim (builder base)"
    - "python:3.12-slim-bookworm (runtime base — pinned, NOT bare slim)"
  patterns:
    - "Multi-stage Docker: builder carries uv + dev tooling; runtime is bare Python slim (no uv)"
    - "uv layer split: two `uv sync --frozen` calls — deps-only first (cache-stable), then project source"
    - "BuildKit cache mounts on /root/.cache/uv — deps cache survives across builds"
    - "Non-root system user `app` (groupadd --system + useradd --system --gid app --create-home)"
    - "Production-shape CMD; hot-reload deferred to compose override (D-04)"

key_files:
  created:
    - path: "apps/backend/.dockerignore"
      role: "Build-context exclusions"
      lines: 10
    - path: "apps/backend/Dockerfile"
      role: "Multi-stage build for sportzal-backend (INFRA-01)"
      lines: 47
  modified: []

decisions:
  - "Honored CONTEXT D-01 verbatim: builder = ghcr.io/astral-sh/uv:python3.12-bookworm-slim, runtime = python:3.12-slim-bookworm (slim-bookworm pinned, not bare slim)"
  - "Honored CONTEXT D-02: two `uv sync --frozen` invocations. First with --no-install-project --no-dev after `COPY pyproject.toml uv.lock`; second with --no-dev after `COPY app ./app` + alembic copies. Both with BuildKit cache mount on /root/.cache/uv."
  - "Honored CONTEXT D-03: non-root system user `app` via `groupadd --system app && useradd --system --gid app --create-home app`. COPY --from=builder --chown=app:app /app /app. USER app. CMD = exec-form uvicorn ... --factory."
  - "Honored CONTEXT D-04: NO --reload in Dockerfile, NO Dockerfile.dev. Hot-reload is a compose-only override deferred to Plan 03-05."
  - "Honored CONTEXT D-13: .dockerignore with the 10 lines exactly as specified. pyproject.toml, uv.lock, app/, alembic/, alembic.ini are NOT excluded — they MUST reach the build context."
  - "alembic + alembic.ini are COPYed into the image (NOT excluded by .dockerignore) because the compose `migrate` service (D-12, Plan 03-05) runs `alembic upgrade head` from inside the image. This is the rationale the plan flagged explicitly."
  - "Set ENV UV_LINK_MODE=copy, UV_COMPILE_BYTECODE=1, UV_PROJECT_ENVIRONMENT=/app/.venv in the builder for predictable Docker behavior (matches uv's official Docker integration recipe)."
  - "Set ENV PATH=/app/.venv/bin:$PATH in the runtime so uvicorn + alembic resolve without `uv run` (uv is not present in the runtime stage per D-01)."
  - "Set PYTHONDONTWRITEBYTECODE=1, PYTHONUNBUFFERED=1 in the runtime — canonical Python-in-Docker hygiene; logs flush immediately, no .pyc clutter."
  - "BuildKit syntax directive `# syntax=docker/dockerfile:1.7` on line 1 enables `--mount=type=cache` cleanly across docker engine variants."

metrics:
  duration: "1m 10s"
  tasks_completed: "2/2"
  completed_date: "2026-05-01"
---

# Phase 3 Plan 02: Backend Dockerfile + .dockerignore Summary

## What Shipped

Two files closing INFRA-01:

1. `apps/backend/.dockerignore` (10 lines) — keeps build context lean and prevents `.env*` / `.git/` / dev artifacts from leaking into image layers.
2. `apps/backend/Dockerfile` (47 lines) — multi-stage build:
   - **Stage 1 (builder)** uses `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` to run two `uv sync --frozen` invocations against the committed `uv.lock`. First sync is deps-only (`--no-install-project --no-dev`) so source changes don't bust the deps cache; second sync (`--no-dev`) finalizes the project install after `COPY app ./app`. Both syncs use BuildKit cache mounts on `/root/.cache/uv`.
   - **Stage 2 (runtime)** uses bare `python:3.12-slim-bookworm` (no `uv` in this image). Creates a non-root system user `app`, `COPY --from=builder --chown=app:app /app /app`, sets `PATH` to include the venv, runs `uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000` as `app`. NO `--reload`. NO `alembic upgrade head`.

The image is the artifact `docker-compose.yml` (Phase 03-05) will build for both the `backend` and `migrate` services.

## Why alembic Lives Inside the Image

Plan-spec called this out, so it's documented here: `apps/backend/.dockerignore` deliberately does NOT exclude `alembic/` or `alembic.ini`, and the Dockerfile explicitly `COPY alembic ./alembic` + `COPY alembic.ini ./alembic.ini` into the builder. Reason: the compose `migrate` service (D-12, Plan 03-05) is a one-shot service that runs `alembic upgrade head` inside the same image. If alembic weren't in the image, the migrate service couldn't function. This is also what closes Phase 2 deferred SC #5 (`alembic upgrade head` against the empty containerized Postgres) once Plan 03-05 lands.

## Build Smoke — DEFERRED

Docker daemon (`unix:///Users/andre/.docker/run/docker.sock`) is unreachable in this worktree environment (Docker Desktop server not running). The plan explicitly permits this: "If unreachable, mark as DEFERRED and execute the build inside Plan 03-05 (compose) which is a hard prerequisite anyway." All file-shape acceptance criteria (Task 1: 15 grep checks; Task 2: 19 grep checks) passed. The actual `docker build -t sportzal-backend:dev .` will run when Plan 03-05 brings up the compose stack (which is the natural integration point — the Dockerfile is consumed by `services.backend.build: .` and `services.migrate.build: .`).

Verification still pending after Plan 03-05 brings Docker up:
- `docker run --rm --entrypoint id sportzal-backend:dev` → reports `uid=*(app) gid=*(app)` (non-root)
- `docker run --rm sportzal-backend:dev which uvicorn` → `/app/.venv/bin/uvicorn`
- `docker run --rm sportzal-backend:dev sh -c "ls /app/.venv/bin"` → does NOT contain `pytest`, `ruff`, `mypy`, `lint-imports`

## Tasks

### Task 1 — apps/backend/.dockerignore — `af88577`
Created the file with the exact 10-line content from D-13. Required-line grep counts all returned 1; forbidden-line grep counts (pyproject.toml, uv.lock, app/, alembic) all returned 0. Mitigates T-03-05 (Information Disclosure: secret leakage into image).

### Task 2 — apps/backend/Dockerfile — `588bc29`
Created the multi-stage Dockerfile per the literal D-01..D-04 fragments. All 19 grep-based acceptance checks pass (counts match expected values exactly). Mitigates T-03-06 (non-root user), T-03-07 (`--frozen` against committed lockfile), T-03-08 (`--no-dev` excludes dev tooling from runtime). Build smoke deferred to Plan 03-05 (Docker daemon unavailable in worktree).

## Deviations from Plan

None — plan executed exactly as written. Both literal D-13 (.dockerignore) and D-01..D-04 (Dockerfile) fragments were honored verbatim. The build-smoke deferral is the plan's own pre-authorized fallback path, not a deviation.

## Threat Mitigations Applied

| Threat ID | Disposition | How |
|-----------|-------------|-----|
| T-03-05 (Info Disclosure: build context) | mitigate | `.dockerignore` excludes `.env*` and `.git/` (acceptance grep enforces both). |
| T-03-06 (Elevation of Privilege) | mitigate | `groupadd --system app && useradd --system --gid app --create-home app` + `USER app`. CMD runs as uid != 0. |
| T-03-07 (Tampering: lockfile) | mitigate | Both `uv sync` invocations use `--frozen` against committed `uv.lock`. |
| T-03-08 (Info Disclosure: dev-deps in prod) | mitigate | Both `uv sync` invocations pass `--no-dev`. ruff/mypy/import-linter/pytest/asgi-lifespan never reach runtime. |
| T-03-09 (Supply chain: tag drift) | accept | `slim-bookworm` pin (D-01) prevents Debian channel drift. Digest pinning deferred to Phase X+ production hardening. |
| T-03-10 (DoS: uncached build) | accept | `.dockerignore` keeps build context small. BuildKit cache mounts cache deps across builds. |

## Self-Check: PASSED

- `apps/backend/.dockerignore` exists (10 lines) — FOUND
- `apps/backend/Dockerfile` exists (47 lines) — FOUND
- Commit `af88577` — FOUND in git log
- Commit `588bc29` — FOUND in git log
- All 15 Task 1 grep acceptance checks pass
- All 19 Task 2 grep acceptance checks pass
- Build smoke explicitly DEFERRED per plan-authorized fallback (Docker daemon unreachable in worktree)
