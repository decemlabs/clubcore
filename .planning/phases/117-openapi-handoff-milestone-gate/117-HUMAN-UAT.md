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
result: [pending]
note: Blocked in the autonomous run by a local-env Postgres deadlock (`alembic downgrade`
DELETE on `working_hours_config` blocked by an idle-in-transaction lock), not a v3.2 code
defect. Recommended clean re-run: `docker compose down -v` → `alembic upgrade head` → seed
→ `uv run pytest --timeout=60` (pytest-timeout, so a deadlock fails the culprit test
instead of hanging).

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
