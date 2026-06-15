---
status: partial
phase: 117-openapi-handoff-milestone-gate
source: [117-VERIFICATION.md]
started: 2026-06-15
updated: 2026-06-15
---

## Current Test

[awaiting human testing — deferred by operator decision 2026-06-15]

## Tests

### 1. Full backend pytest suite green on a clean DB
expected: `uv run pytest` passes the full ~3000-test suite (incl.
`tests/integration/test_rbac_parity.py::test_owner_only_count_is_forty_six`).
result: [pending — blocked by a precisely-diagnosed PRE-EXISTING test-isolation deadlock, NOT a v3.2 defect]

**ROOT CAUSE (diagnosed v3.2 Phase 117, confirmed reproducible on a clean freshly-migrated+seeded DB):**
A function-scoped `autouse=True` fixture `permissive_booking_config`
(`apps/backend/tests/integration/conftest.py` + `.../bookings/conftest.py`) issues
`UPDATE working_hours_config SET schedule=…` on the SAVEPOINT-wrapped `db_session` and
leaves that transaction OPEN for the test. The migration round-trip tests then call
`_run_alembic("downgrade", …)` in a SUBPROCESS (separate connection) whose downgrade chain
runs `DELETE FROM working_hours_config` → blocks on the fixture's lock → deadlock (Postgres
`pg_blocking_pids` confirmed: DELETE pid blocked by the idle-in-transaction UPDATE pid).
The suite hangs immediately because `tests/integration/alembic/` sorts early. Possible only
since v3.1 Phase 108 added `working_hours_config`; pre-v3.2 — no v3.2 code involved.

Deadlocking files (deselect/ignore to unblock the rest of the suite):
- `tests/integration/alembic/test_migration_0027_cleanup.py`
- `tests/integration/alembic/test_migration_0033_clients_email.py`
- `tests/integration/migrations/test_visits_channel_client_qr.py`

**Two fix paths:**
1. (gate-unblock) run `uv run pytest --ignore=<the 3 files above>` on a clean DB → completes
   → confirm zero v3.2-domain regressions. The excluded files are pre-v3.2 migration
   round-trip tests; excluding them cannot mask a v3.2 regression.
2. (real fix, separate task) make `permissive_booking_config` commit/rollback before the
   downgrade subprocess runs, or scope it so it doesn't apply to the migration round-trip
   tests, or have those tests use their own committed connection. This is test-infra work
   outside v3.2 scope.

Clean-DB setup that works (avoids the documented VARCHAR(32) alembic_version overflow):
`psql -U app -d postgres -c "DROP DATABASE clubcore; CREATE DATABASE clubcore OWNER app;"`
→ `psql -U app -d clubcore -c "CREATE TABLE alembic_version(version_num VARCHAR(64) PRIMARY KEY);"`
→ `uv run alembic upgrade head` → `SEED_OWNER_EMAIL=owner@clubcore.dev
SEED_OWNER_PASSWORD=devpassword12345 uv run python -m scripts.seed_demo_data`.

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
