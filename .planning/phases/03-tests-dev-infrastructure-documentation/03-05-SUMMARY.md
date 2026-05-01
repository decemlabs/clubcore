---
phase: 03-tests-dev-infrastructure-documentation
plan: 05
subsystem: backend / dev-infra
tags: [docker-compose, postgres-16, redis-7, alembic, healthcheck, depends_on, hot-reload, infra-02]
requirements: [INFRA-02]
dependency_graph:
  requires:
    - "Plan 03-02 — apps/backend/Dockerfile (consumed by `build: .`)"
    - "Phase 2 D-15 — Settings shape + apps/backend/.env.example env contract"
    - "apps/backend/alembic/env.py + alembic/versions/.gitkeep — async migrations machinery"
    - "apps/backend/scripts/backup_db.sh (Plan 03-03 — relies on compose-network postgres for SC #3 backup half)"
  provides:
    - "Local dev stack: backend + postgres:16 + one-shot migrate + redis:7 (INFRA-02)"
    - "End-to-end harness for Phase 2 deferred SC #5 (`alembic upgrade head` against containerized Postgres) — RUN PENDING (Docker daemon down)"
    - "End-to-end harness for ROADMAP Phase 3 SC #2 (`/healthz` 200 against compose backend) — RUN PENDING (Docker daemon down)"
    - "End-to-end harness for ROADMAP Phase 3 SC #3 backup half (backup_db.sh against compose postgres) — RUN PENDING (Docker daemon down)"
  affects:
    - "apps/backend/.gitignore (added `.env` exclusion)"
tech-stack:
  added: []
  patterns:
    - "Compose v2 minimal shape: NO `version:` key (modern compose ignores it)"
    - "One-shot `migrate` service running `alembic upgrade head` (D-12) — backend never starts before migrations finish via service_completed_successfully"
    - "Postgres healthcheck via `pg_isready -U app -d sportzal` (interval 2s, retries 10)"
    - "Hot-reload as compose override only (D-04): uvicorn --reload --reload-dir /app/app + bind-mount ./app:/app/app:ro — Dockerfile CMD stays prod-shape"
    - "Named volume `postgres-data` survives `docker compose down`; dropped via `down -v`"
    - "Redis NOT exposed to host (compose-network only) — no use case in Phase A"
key-files:
  created:
    - "apps/backend/docker-compose.yml (47 lines)"
  modified:
    - "apps/backend/.gitignore (added `.env` to local-env block)"
decisions:
  - "Honored CONTEXT D-12 verbatim: literal compose YAML shipped without modification"
  - "Honored CONTEXT D-04 verbatim: hot-reload override lives in compose, not Dockerfile"
  - "`.env` added to `apps/backend/.gitignore` (no root .gitignore exists; closest gitignore was the per-app one)"
  - "Task 2 (end-to-end stack smoke) DEFERRED — Docker daemon is down on the executing host; YAML parse-check via `docker compose config` succeeded (exit 0), all 21 grep acceptance checks PASS"
metrics:
  duration: "1m 26s"
  tasks_completed: "1/2 — Task 2 deferred per plan-spec line 293 (Docker unavailable → mark PENDING, re-run when Docker is up)"
  files_changed: 2
  completed_date: "2026-05-01"
---

# Phase 3 Plan 05: docker-compose.yml — Local Dev Stack Summary

INFRA-02 satisfied: `apps/backend/docker-compose.yml` defines the four-service local dev stack (backend + one-shot migrate + postgres:16 + redis:7) with `pg_isready` healthcheck, `service_completed_successfully` ordering, hot-reload override, and named `postgres-data` volume — all per CONTEXT D-04 + D-12 verbatim. End-to-end runtime smoke (`docker compose up`, `/healthz` curl, `alembic upgrade head` evidence, `backup_db.sh`) is PENDING because the executing host's Docker daemon is down; the YAML itself parses cleanly (`docker compose config` exit 0) and all 21 grep acceptance criteria are satisfied.

## What Was Built

### docker-compose.yml structure (47 lines)

| Service | Image / build | Role | Notable wiring |
|---------|---------------|------|----------------|
| `backend` | `build: .` (Plan 03-02 Dockerfile) | FastAPI dev server with hot-reload | `command:` overrides CMD with `--reload --reload-dir /app/app`; `volumes: ./app:/app/app:ro`; `ports: 8000:8000`; `depends_on` migrate (`service_completed_successfully`) + redis (`service_started`) |
| `migrate` | `build: .` (same Dockerfile) | One-shot `alembic upgrade head`, then exit | `depends_on` postgres (`service_healthy`); `env_file: .env`; idempotent against empty `alembic/versions/.gitkeep` (Phase A no-op) |
| `postgres` | `postgres:16` | Database | `pg_isready -U app -d sportzal` healthcheck (interval 2s, timeout 2s, retries 10); env `POSTGRES_USER/PASSWORD/DB = app/app/sportzal` matching `.env.example` DSN; named volume `postgres-data:/var/lib/postgresql/data`; `ports: 5432:5432` for IDE access |
| `redis` | `redis:7` | Cache / future ARQ broker | NO host port (compose-network only per D-12 — no Phase A use case) |

### .gitignore update

Added `.env` exclusion under a new `# Local env` block so the standard `cp .env.example .env` workflow stays local-only. No root `.gitignore` exists, so the per-app `apps/backend/.gitignore` is the only place this needed to land.

## Verification Evidence

### Static gates (all PASS)

| Check | Command | Result |
|-------|---------|--------|
| `version:` key absent (D-12) | `grep -c '^version:' apps/backend/docker-compose.yml` | **0** |
| Four service blocks | `grep -cE '^  (backend\|migrate\|postgres\|redis):$' docker-compose.yml` | **4** |
| `image: postgres:16` | `grep -c` | **1** |
| `image: redis:7` | `grep -c` | **1** |
| `build: .` (backend + migrate) | `grep -c 'build: \.'` | **2** |
| `pg_isready -U app -d sportzal` | `grep -c` | **1** |
| `service_healthy` (migrate→postgres) | `grep -c` | **1** |
| `service_completed_successfully` (backend→migrate) | `grep -c` | **1** |
| `service_started` (backend→redis) | `grep -c` | **1** |
| `alembic upgrade head` | `grep -c` | **1** |
| `--reload --reload-dir /app/app` | `grep -c` | **1** |
| `./app:/app/app:ro` bind-mount | `grep -c` | **1** |
| `POSTGRES_USER/PASSWORD/DB` triple | `grep -c` each | **1, 1, 1** |
| `8000:8000` (backend exposed) | `grep -c '"8000:8000"'` | **1** |
| `5432:5432` (postgres exposed) | `grep -c '"5432:5432"'` | **1** |
| `6379:6379` NOT exposed (D-12) | `grep -c '"6379:6379"'` | **0** |
| `^volumes:$` block | `grep -c` | **1** |
| `postgres-data:` named volume | `grep -c '^  postgres-data:'` | **1** |
| `.env` excluded by gitignore | `grep -nE '^\.env$' apps/backend/.gitignore` | **line 25 — present** |
| `docker compose config` parses YAML | `cd apps/backend && docker compose config` | **exit 0** (full canonical-form YAML produced; depends_on/healthcheck/named-volume all resolved) |

All 21 acceptance grep checks from PLAN.md Task 1 PASS.

### Runtime smoke (PENDING — Docker daemon down)

| Check | Status | Reason |
|-------|--------|--------|
| `docker compose build` exits 0 | ⏸ PENDING | `docker info` reports daemon unreachable on executing host |
| `docker compose up -d` exits 0 | ⏸ PENDING | Daemon down |
| `migrate` service exits 0 (closes Phase 2 deferred SC #5) | ⏸ PENDING | Daemon down |
| `curl /healthz` returns 200 + `{"status":"ok"}` (closes ROADMAP SC #2) | ⏸ PENDING | Daemon down |
| `x-request-id` header present (Phase 2 middleware in container) | ⏸ PENDING | Daemon down |
| `bash scripts/backup_db.sh /tmp/sportzal-test.sql.gz` produces non-empty file (closes Plan 03-03 deferred + ROADMAP SC #3 backup half) | ⏸ PENDING | Daemon down |
| `docker compose down` exits 0 | ⏸ PENDING | Daemon down |

**Resumption point:** When Docker is started locally (`open -a Docker` on macOS), re-run the Task 2 verification battery from `apps/backend/`:

```bash
cd apps/backend && \
  ([ -f .env ] || cp .env.example .env) && \
  docker compose build && \
  docker compose up -d && \
  for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    curl -fsS http://localhost:8000/healthz >/dev/null 2>&1 && break || sleep 2
  done && \
  echo "migrate exit: $(docker inspect --format='{{.State.ExitCode}}' "$(docker compose ps -q migrate)")" && \
  curl -fsSI http://localhost:8000/healthz | tr -d '\r' && \
  curl -fsS http://localhost:8000/healthz && \
  bash scripts/backup_db.sh /tmp/sportzal-test.sql.gz && \
  ls -l /tmp/sportzal-test.sql.gz && \
  docker compose down
```

Per plan-spec line 293: this deferral is the explicit, documented path. Phase 2 SC #5 + ROADMAP Phase 3 SC #2 stay open until this smoke succeeds.

## Phase 2 SC #5 retirement statement

The Phase 2 verification report (`02-VERIFICATION.md` row #10) deferred `uv run alembic upgrade head` against an empty Postgres because no Postgres was reachable in the verifier's environment. Plan 03-05 ships the YAML harness — the `migrate` service runs `alembic upgrade head` exactly once on `docker compose up`, gated on `postgres.service_healthy`, and exits 0 against the empty `alembic/versions/.gitkeep` directory. **The harness is in place; the live retirement requires Docker daemon up** (see Pending row above). The STATIC code path was already proven in Phase 2 (`02-VERIFICATION.md` Behavioral Spot-Checks row #10: "Loads env.py, runs async engine, reaches asyncpg `__connect_addr`, fails on TCP `[Errno 61]` — environmental, code path proven"); only the network barrier remained, and this plan supplies the containerized Postgres that closes that barrier.

## Decisions Made

1. **Literal D-12 + D-04 verbatim.** No deviations from the locked compose shape; `env_file: .env` reuses the same `.env` for local-uv and compose paths per CONTEXT `<code_context>` line 341.
2. **`.env` excluded via `apps/backend/.gitignore`** (line 25) rather than a new root `.gitignore`. Matches the Phase 2 pattern of per-app gitignore files.
3. **Task 2 deferred per plan-spec line 293.** Plan-spec explicitly anticipates Docker-unavailable case and instructs PENDING marking, not silent closure.

## Deviations from Plan

None — plan executed exactly as written. The Task 2 deferral is itself a planned branch in the plan-spec (line 293 + acceptance_criteria last bullet: "If Docker is unavailable: task BLOCKS, marks all the above as PENDING").

## Known Stubs

None.

## Threat Flags

None — Plan 03-05 introduces no new attack surface beyond the locked threat register entries (T-03-19 through T-03-25 in PLAN.md). The `:8000` and `:5432` host port exposures are accepted (local-dev only); redis stays compose-network-only; `.env` is gitignored (T-03-24 mitigated); hot-reload bind-mount is `:ro` (T-03-25 mitigated).

## Notes for Phase 3 verifier

- **Single new commit** at `cf7a90c` (per-task commit). No final metadata commit will be made by this executor — the wave orchestrator owns ROADMAP/STATE writes.
- **YAML grep gates** are reproducible from the pasted `## Verification Evidence` section above (all 21 PASS).
- **When Docker daemon is up**, the verifier should run the resumption block above and confirm: `migrate` exits 0, `curl /healthz` 200 with `{"status":"ok"}` body and `x-request-id` header, `backup_db.sh` produces a non-empty file. That closes Phase 2 SC #5 + ROADMAP Phase 3 SC #2 + ROADMAP Phase 3 SC #3 backup half in one shot.
- **Environment notes:** macOS Darwin 24.6.0; Docker version 29.4.0 (CLI installed); Docker Compose v5.1.1; daemon was DOWN at execution time.

## Self-Check: PASSED

- File created: `apps/backend/docker-compose.yml` — FOUND (47 lines)
- File modified: `apps/backend/.gitignore` — FOUND (`.env` line present)
- Commit: `cf7a90c feat(03-05): add docker-compose.yml for local dev stack (INFRA-02)` — FOUND
- 21 acceptance grep checks — ALL PASS (executed in Task 1 verification block)
- `docker compose config` — exit 0 (YAML parses; static gate green)
- Task 2 — DEFERRED per plan-spec line 293 (Docker daemon unavailable; PENDING in SUMMARY)
