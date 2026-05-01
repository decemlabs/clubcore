---
phase: 03-tests-dev-infrastructure-documentation
plan: 06
subsystem: infra

tags: [docker, docker-compose, fastapi, postgres, redis, alembic, env-overrides, gap-closure]

# Dependency graph
requires:
  - phase: 03-tests-dev-infrastructure-documentation
    provides: "INFRA-02 baseline docker-compose stack (backend/migrate/postgres/redis services + named volume)"
provides:
  - "Compose-network DSN overrides for backend (DATABASE_URL + REDIS_URL) and migrate (DATABASE_URL only) — closes CR-01 from 03-REVIEW.md / 03-VERIFICATION.md gaps[0]"
  - "Variant 1 (local-uv) developer flow remains intact — .env.example unchanged"
affects: ["phase-04+ runtime smoke (Docker variant)", "HUMAN-UAT.md Docker smoke validation"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "compose env-override: services declare both env_file:.env (Variant 1 contract) AND environment: (Variant 2 compose-network override) — precedence environment > env_file isolates the two flows without forking .env files"

key-files:
  created: []
  modified:
    - "apps/backend/docker-compose.yml — added environment: blocks to backend (DATABASE_URL + REDIS_URL) and migrate (DATABASE_URL only)"

key-decisions:
  - "Use compose environment: precedence over env_file:.env (Option A from 03-VERIFICATION.md gaps[0]) — keeps .env.example as Variant 1 single source of truth without forking into .env.compose / .env.local"
  - "migrate service receives DATABASE_URL only — alembic does not touch Redis, so REDIS_URL is intentionally not overridden there (the env_file fallback localhost value is irrelevant to alembic upgrade)"
  - "WR-04 (postgres host port 5432:5432) explicitly out of scope — Phase A dev-only choice per CONTEXT D-12; deferred to a future hardening pass"

patterns-established:
  - "Pattern: Two-flow DSN handling — Variant 1 reads localhost from .env (uv runs uvicorn on host), Variant 2 reads compose-DNS from environment: (containers reach service names). Same .env.example, no per-flow env files."

requirements-completed: ["INFRA-02"]

# Metrics
duration: 2min
completed: 2026-05-01
---

# Phase 03 Plan 06: Compose Env Override Gap Closure (CR-01) Summary

**Two surgical environment: blocks added to backend and migrate services so docker-compose containers reach postgres:5432 and redis:6379 instead of localhost — closes CR-01 without forking .env files.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-01T13:29:39Z
- **Completed:** 2026-05-01T13:31:37Z
- **Tasks:** 1 (single Edit task, two surgical block additions)
- **Files modified:** 1 (`apps/backend/docker-compose.yml`)

## Accomplishments

- Closed CR-01 from `03-REVIEW.md` / `03-VERIFICATION.md` gaps[0]: compose-network DSN mismatch resolved — `migrate` can now reach Postgres at `postgres:5432`, unblocking the `depends_on` chain that previously prevented `backend` (and `/healthz`) from starting.
- Variant 1 (`local-uv`) developer flow preserved verbatim — `apps/backend/.env.example` byte-identical (zero-byte git diff), keeping `localhost` DSNs intact for `uv run uvicorn` from the host.
- All compose service blocks unrelated to the fix (`postgres`, `redis`) and the `volumes:` section are byte-identical to pre-edit; only +5 lines added in two clearly scoped hunks.

## Task Commits

1. **Task 1: Add environment: overrides to backend and migrate services** — `36e0959` (fix)

**Plan metadata commit:** appended after this SUMMARY is written (docs commit covering SUMMARY.md + STATE.md + ROADMAP.md + REQUIREMENTS.md).

## Files Created/Modified

- `apps/backend/docker-compose.yml` — added two `environment:` blocks (5 net new lines):
  - `backend.environment.DATABASE_URL = postgresql+asyncpg://app:app@postgres:5432/sportzal`
  - `backend.environment.REDIS_URL = redis://redis:6379/0`
  - `migrate.environment.DATABASE_URL = postgresql+asyncpg://app:app@postgres:5432/sportzal`

### Exact Diff

```diff
@@ -6,6 +6,9 @@ services:
     build: .
     command: uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --reload --reload-dir /app/app
     env_file: .env
+    environment:
+      DATABASE_URL: postgresql+asyncpg://app:app@postgres:5432/sportzal
+      REDIS_URL: redis://redis:6379/0
     ports:
       - "8000:8000"
     volumes:
@@ -20,6 +23,8 @@ services:
     build: .
     command: alembic upgrade head
     env_file: .env
+    environment:
+      DATABASE_URL: postgresql+asyncpg://app:app@postgres:5432/sportzal
     depends_on:
       postgres:
         condition: service_healthy
```

## Verification Results

All 8 acceptance criteria from the plan pass:

| # | Check | Result |
|---|-------|--------|
| AC1 | `docker compose -f apps/backend/docker-compose.yml config` exits 0 | PASS (exit 0) |
| AC2 | Resolved config has `DATABASE_URL: postgresql+asyncpg://app:app@postgres:5432/sportzal` count >= 2 | PASS (count = 2: backend + migrate) |
| AC3 | Resolved config has `REDIS_URL: redis://redis:6379/0` count >= 1 | PASS (count = 1: backend only) |
| AC4 | `grep -v '^#' docker-compose.yml \| grep -c 'environment:'` >= 3 | PASS (count = 3: backend, migrate, postgres) |
| AC5 | `git diff HEAD -- apps/backend/.env.example \| wc -c` == 0 | PASS (0 bytes — file unchanged) |
| AC6 | `grep -v '^#' docker-compose.yml \| grep -c 'healthcheck:'` == 1 | PASS (postgres only — redis intentionally has none per CONTEXT D-12) |
| AC7 | `head -3 apps/backend/docker-compose.yml \| grep -c '^# Phase 3 INFRA-02'` == 1 | PASS (top-of-file comment preserved) |
| AC8 | `apps/backend/.env.example` line 2 still reads `DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/sportzal` | PASS (Variant 1 contract intact) |

The bundled `<verify>` automated chain command from the plan exited 0 (`VERIFY_EXIT=0`).

### Resolved Compose Config Excerpt

`docker compose -f apps/backend/docker-compose.yml config` produces (relevant `environment:` blocks):

```yaml
services:
  backend:
    environment:
      DATABASE_URL: postgresql+asyncpg://app:app@postgres:5432/sportzal
      DEBUG: "true"
      ENVIRONMENT: dev
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: change-me-dev-only-not-secret
  migrate:
    environment:
      DATABASE_URL: postgresql+asyncpg://app:app@postgres:5432/sportzal
      DEBUG: "true"
      ENVIRONMENT: dev
      REDIS_URL: redis://localhost:6379/0   # falls back to env_file — intentional, alembic does not use Redis
      SECRET_KEY: change-me-dev-only-not-secret
```

The `migrate.REDIS_URL` falling back to `localhost` from `env_file` is by design — alembic does not connect to Redis, so the value is never read at runtime.

### Verification Environment Note

`docker compose config` requires the file referenced by `env_file:` (`apps/backend/.env`) to exist on disk. The repo correctly gitignores `.env` (per `apps/backend/.gitignore` line 25), so a developer's local `cp .env.example .env` step is the canonical setup. To run the resolved-config verification in this autonomous execution, a temporary `.env` was materialized via `cp apps/backend/.env.example apps/backend/.env`, then removed after verification (`rm apps/backend/.env`). No tracked file was modified by this temporary materialization, and `git status` post-cleanup confirms only the intended `apps/backend/docker-compose.yml` change.

## Decisions Made

- **Option A (compose `environment:` override) over Option B (separate `.env.compose` file):** Per `03-VERIFICATION.md` gaps[0] recommendation. Option A is a single-file change with zero impact on the documented Variant 1 setup; Option B would require updating both compose AND README.

- **`migrate.environment` only carries `DATABASE_URL`:** Alembic has no Redis dependency. Adding `REDIS_URL` there would be redundant noise that obscures intent and risks future readers thinking the migration step needs Redis.

## Deviations from Plan

None — plan executed exactly as written. The two surgical Edit operations matched the plan's pre-specified replacement YAML verbatim, and all 8 acceptance criteria + the bundled verify chain pass on first run.

## Issues Encountered

- `docker compose config` initially failed with `env file ... apps/backend/.env not found` because `.env` is correctly gitignored and not present in a fresh checkout. Resolved by materializing a temporary `.env` from `.env.example` for verification only, then removing it. Pre-existing setup expectation, not caused by the edits.

## User Setup Required

None — no external service configuration required. This change is fully internal to `docker-compose.yml` and inherits the existing developer onboarding step (`cp apps/backend/.env.example apps/backend/.env`) already documented in the README.

## Next Phase Readiness

- **CR-01 closed at the YAML/static-validation level.** Live `docker compose up` smoke (Phase 3 SC #2/#3 runtime validation) remains a HUMAN-UAT.md item — see `.planning/phases/03-tests-dev-infrastructure-documentation/03-HUMAN-UAT.md` for the manual `docker compose up -d` + `curl :8000/healthz` flow that closes the runtime side of SC #2/#3.
- **WR-04 (postgres host port `5432:5432` exposure) deferred** as documented in plan threat T-03-06-05 — addressable via a future `/gsd-code-review-fix` pass if the user wants to bind to `127.0.0.1:5432:5432` or remove the host mapping entirely. Out of scope for this gap-closure plan.

---
*Phase: 03-tests-dev-infrastructure-documentation*
*Completed: 2026-05-01*

## Self-Check: PASSED

- FOUND: `.planning/phases/03-tests-dev-infrastructure-documentation/03-06-SUMMARY.md`
- FOUND: `apps/backend/docker-compose.yml` (modified)
- FOUND: commit `36e0959` (`fix(03-06): add compose env overrides for DATABASE_URL/REDIS_URL`)
- FOUND: `apps/backend/.env.example` byte-identical (zero git diff vs HEAD pre-commit)
