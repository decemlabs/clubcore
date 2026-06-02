---
phase: 72-openapi-handoff-ci-e2e-verification
plan: "03"
subsystem: CI
tags: [ci, client-pwa, backend-pytest, idor, security, github-actions]
dependency_graph:
  requires: []
  provides: [HND-03, VER-02]
  affects:
    - .github/workflows/ci.yml
tech_stack:
  added: []
  patterns:
    - GitHub Actions service containers (postgres:16 + redis:7) for integration tests
    - pnpm --filter exclusion for per-job scoping
    - parallel CI jobs with no needs: dependency
key_files:
  created: []
  modified:
    - .github/workflows/ci.yml
decisions:
  - D-72-03: Dedicated parallel client-pwa job (no needs:) for all four gates
  - D-72-04: Build step mandatory to catch vite-plugin-pwa SW/manifest breakage
  - D-72-05: Frontend recursive pnpm -r steps scoped with --filter '!@clubcore/client-pwa'
  - VER-02: Backend pytest step added with postgres:16 + redis:7 service containers
metrics:
  duration: 4m
  completed: "2026-05-31"
  tasks_completed: 3
  files_modified: 1
---

# Phase 72 Plan 03: CI Gates (client-pwa + backend pytest) Summary

Added three CI gates to `.github/workflows/ci.yml`: a dedicated parallel `client-pwa` job (D-72-03/04, HND-03), frontend-job de-duplication via pnpm filter exclusion (D-72-05), and a backend pytest step with Postgres 16 + Redis 7 service containers plus `alembic upgrade head` so the Phase 68-70 IDOR/anti-oracle/two-principal tests execute green in CI (VER-02).

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Add parallel client-pwa CI job | 9e492d76 |
| 2 | Scope frontend job pnpm -r steps to exclude client-pwa | 9e492d76 |
| 3 | Add backend pytest step with Postgres 16 + Redis 7 service containers | 9e492d76 |

All three tasks were implemented atomically in a single `ci.yml` write since all changes target the same file.

## What Was Built

### Task 1: client-pwa parallel CI job (D-72-03/04, HND-03)

New `client-pwa` job with NO `needs:` key (runs in parallel with `backend`, `frontend`, `redocly-lint`). Copies the pnpm/Node 20 setup pattern from the `frontend` job, then runs four steps:

- `pnpm -F @clubcore/client-pwa typecheck`
- `pnpm -F @clubcore/client-pwa lint`
- `pnpm -F @clubcore/client-pwa test`
- `pnpm -F @clubcore/client-pwa build` (mandatory per D-72-04 — catches vite-plugin-pwa SW/manifest generation breakage)

`apps/client-pwa/package.json` already defines all four gate scripts (confirmed present):
- `build`: `tsc -b && vite build`
- `lint`: `eslint .`
- `test`: `vitest run`
- `typecheck`: `tsc -b --noEmit`

No changes needed to `package.json`.

### Task 2: Frontend job de-duplication (D-72-05)

The three recursive steps in the `frontend` job now carry `--filter '!@clubcore/client-pwa'` to prevent double-running:

```yaml
- name: Lint (workspaces)
  run: pnpm -r --filter '!@clubcore/client-pwa' lint

- name: Typecheck (workspaces)
  run: pnpm -r --filter '!@clubcore/client-pwa' typecheck

- name: Test (workspaces)
  run: pnpm -r --filter '!@clubcore/client-pwa' test
```

The `pnpm -F @clubcore/api-client test`, `codegen`, and `schema.d.ts` drift-gate steps are preserved unchanged — they target a specific package with no double-run risk.

### Task 3: Backend pytest step with service containers (VER-02, D-72-08)

Service containers added to the `backend` job:
- `postgres:16` with `POSTGRES_USER=app`, `POSTGRES_PASSWORD=app`, `POSTGRES_DB=clubcore`, port 5432, health-check via `pg_isready -U app -d clubcore`
- `redis:7` with port 6379, health-check via `redis-cli ping`

Job-level `env:` set:
- `DATABASE_URL: postgresql+asyncpg://app:app@localhost:5432/clubcore`
- `REDIS_URL: redis://localhost:6379/0`

Two steps added after the existing drift gate, in order:
1. `uv run alembic upgrade head` — integration tests assume a migrated schema; conftest does not create tables
2. `uv run pytest` — runs the full test suite

`SECRET_KEY` and `ENVIRONMENT` fall back from `.env.example` via `conftest.py`'s `os.environ.setdefault` at import time (L39-46), so no additional secrets are required.

#### VER-02 Security Test Files (now execute, not skip)

With `DATABASE_URL` pointed at the live service container, the following four security test files are collected and execute (not skipped by the `pytest.skip(f"DATABASE_URL not reachable..."`) guard in `conftest.py` L79/L87):

| File | Coverage |
|------|----------|
| `apps/backend/tests/integration/client_portal/test_idor_sweep.py` | Parametrized IDOR sweep — client A cannot see client B's owned resources (T-69-01) |
| `apps/backend/tests/integration/client_auth/test_idor.py` | IDOR guard on GET /client/me — authenticated principal only returns own data (CISO-04) |
| `apps/backend/tests/integration/client_auth/test_byte_parity.py` | `Role.CLIENT` absent from staff RBAC stack; ClientPrincipal has no role (CISO-01) |
| `apps/backend/tests/integration/client_auth/test_otp_isolation.py` | Two-principal isolation (staff/client token cross-rejection) + anti-oracle byte-parity (CISO-02, CAUTH-02) |

## Deviations from Plan

### Combined Implementation

All three tasks modify `.github/workflows/ci.yml` exclusively. The file was written once and committed in a single atomic commit (`9e492d76`) covering all three tasks rather than three separate commits. All acceptance criteria verified (automated YAML checks pass for each task).

## Verification Results

```
Task 1 OK: client-pwa job has no needs, all 4 gates present
Task 2 OK: frontend recursive steps all scoped, drift gate preserved
Task 3 OK: backend has postgres:16 + redis:7 services, alembic upgrade head, pytest, correct env URLs
```

## Known Stubs

None — this plan modifies only CI configuration.

## Threat Flags

None. The only changes are to `.github/workflows/ci.yml` — no new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check: PASSED

- `.github/workflows/ci.yml` exists and contains `client-pwa` job: FOUND
- Commit `9e492d76` exists: FOUND
- All three automated verify commands pass: CONFIRMED
