---
status: complete
phase: 03-tests-dev-infrastructure-documentation
source:
  - 03-01-SUMMARY.md
  - 03-02-SUMMARY.md
  - 03-03-SUMMARY.md
  - 03-04-SUMMARY.md
  - 03-05-SUMMARY.md
  - 03-06-SUMMARY.md
started: 2026-05-01T14:00:00Z
updated: 2026-05-01T14:30:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: |
  From clean state: `cd apps/backend && cp .env.example .env && docker compose down -v && docker compose up --build -d`.
  Build completes, migrate exits 0, backend stays Up. `docker compose ps` shows expected service states.
result: pass
evidence: |
  postgres-1 Healthy 3.0s, redis-1 Started 0.5s, migrate-1 Exited 3.8s, backend-1 Started 3.8s.
  Both images built (40.5s each), network + volume created cleanly.

### 2. Healthz endpoint returns 200 inside live stack
expected: |
  With the compose stack from Test 1 running:
  `curl -i http://localhost:8000/healthz`
  Returns HTTP 200, body `{"status":"ok"}`, header `x-request-id` present and is a UUID4.
result: pass

### 3. Backup script against live Postgres
expected: |
  With the compose stack running:
  `cd apps/backend && bash scripts/backup_db.sh /tmp/sportzal-uat.sql.gz`
  Exits 0. `/tmp/sportzal-uat.sql.gz` exists and is a non-empty gzipped file
  (`file /tmp/sportzal-uat.sql.gz` says "gzip compressed data", `wc -c` > 0).
result: pass
evidence: |
  "Wrote /tmp/sportzal-uat.sql.gz (623 bytes)" — exit 0, файл создан, размер > 0.

### 4. Compose config resolves env overrides
expected: |
  `cd apps/backend && docker compose config`
  Exits 0. Resolved YAML shows `DATABASE_URL: postgresql+asyncpg://app:app@postgres:5432/sportzal`
  for both `backend` and `migrate` services, and `REDIS_URL: redis://redis:6379/0` for `backend`.
result: pass
evidence: |
  DATABASE_URL postgres:5432 — 2 occurrences (backend + migrate) ✓
  REDIS_URL redis:6379/0 — 1 override (backend) ✓
  Note: migrate also resolves REDIS_URL=localhost via env_file inheritance — harmless
  because alembic doesn't connect to Redis. Plan 03-06 deliberately did not add a Redis
  override to migrate. AC `grep -cE 'REDIS_URL: redis://redis:6379/0' >= 1` met.

### 5. Pytest suite green
expected: |
  `cd apps/backend && uv run pytest -v`
  Returns 3 passed (test_healthz_returns_200_and_status_ok, test_healthz_emits_request_id_header,
  test_security_module_is_importable). Exit code 0.
result: pass
evidence: "3 passed in 0.06s"

### 6. Quality gates (mypy + ruff + import-linter)
expected: |
  All three of the following exit 0:
  - `cd apps/backend && uv run mypy app tests` → "Success: no issues found"
  - `cd apps/backend && uv run ruff check .` → "All checks passed!"
  - `cd apps/backend && uv run lint-imports` → "Contracts: 3 kept, 0 broken"
result: pass
evidence: |
  mypy: Success: no issues found in 51 source files
  ruff: All checks passed!
  import-linter: Contracts: 3 kept, 0 broken (Analyzed 44 files, 11 dependencies)
note: |
  uv emits deprecation warning: `tool.uv.dev-dependencies` → use `dependency-groups.dev` instead.
  Non-blocking — пометить как cosmetic gap для будущей чистки pyproject.toml.

### 7. Seed script placeholder behavior
expected: |
  `cd apps/backend && uv run python scripts/seed_demo_data.py`
  Outputs `Phase A: no data to seed` (or similar Phase-A placeholder marker) and exits 0.
result: pass
evidence: "Phase A: no data to seed"

### 8. Documentation deliverables present
expected: |
  All five files exist and are non-empty:
  - `apps/backend/README.md`
  - `apps/backend/docs/architecture.md`
  - `apps/backend/docs/conventions.md`
  - `apps/backend/docs/adr/0001-modular-monolith.md`
  - `apps/backend/docs/adr/template.md`
result: pass
evidence: |
  ls -la from project root: README.md 2420b, architecture.md 11354b, conventions.md 10251b,
  adr/0001-modular-monolith.md 9422b, adr/template.md 1827b — все 5 присутствуют, не пустые.

## Summary

total: 8
passed: 8
issues: 1
pending: 0
skipped: 0

## Gaps

- truth: "pyproject.toml uses non-deprecated uv dependency-groups syntax"
  status: failed
  reason: "uv emits deprecation warning on every command: `tool.uv.dev-dependencies` is deprecated, use `dependency-groups.dev` instead. Discovered during Test 6."
  severity: cosmetic
  test: 6
  artifacts:
    - path: "apps/backend/pyproject.toml"
      issue: "Dev deps declared under `[tool.uv]` dev-dependencies block instead of `[dependency-groups] dev`"
  missing:
    - "Migrate dev deps from `[tool.uv].dev-dependencies` to `[dependency-groups].dev` per uv >=0.5 convention"
