---
phase: 44-invitation-password-reset-flow
plan: 11
status: complete
requirements:
  - RESET-02
tags:
  - cleanup-cron
  - integration-test
  - retention-boundary
commits:
  - 434859a  # test(44-11): cleanup_password_reset_tokens 30-day retention boundary
---

# Plan 44-11 — Cleanup cron integration test

## What landed

- `apps/backend/tests/integration/workers/test_cleanup_password_reset_tokens.py` (210 lines, NEW). 2 tests:
  - `test_cleanup_deletes_beyond_30d_retention_preserves_within` — partitions 6 seeded rows across the boundary (-90d, -45d, -31d to delete; -30d+1min, -7d, +1h to preserve); asserts cron returns 3, surviving IDs match expected, no audit row emitted, structlog summary `cleanup_password_reset_tokens_complete count=3` fires.
  - `test_cleanup_noop_when_nothing_to_delete` — empty-window run; asserts return = 0 and summary log fires with `count=0`.
- `apps/backend/tests/integration/workers/conftest.py` (+5 lines): extended the `_reset_worker_logger_cache` autouse fixture to also bust the cached BoundLoggerLazyProxy on `app.workers.scheduled.cleanup_password_reset_tokens` so `structlog.testing.capture_logs()` picks up its summary lines (matches the Phase 18 W-3 pattern that originally exposed this gotcha for `expire_memberships`).

## Verification

- `uv run pytest tests/integration/workers/test_cleanup_password_reset_tokens.py tests/integration/workers/test_expire_memberships.py` → 3 passed (new tests + existing cron regression green)
- Tests use the existing `worker_ctx` fixture (Phase 18 SAVEPOINT-mode session aliasing) so the cron's DELETE sees the test's seeded rows.

## Key invariants verified

- **30-day retention boundary** (D-44-31/32): cron deletes strictly `expires_at < NOW() - 30d` rows; boundary row at `-30d + 1min` preserved (strict `<`, not `<=`).
- **No audit emission** (D-44-31 housekeeping invariant): pre-run and post-run `audit_log` counts equal; the cleanup cron never produces an audit row.
- **Structlog summary shape** (Phase 18 CD-03 convention): `cleanup_password_reset_tokens_complete count=N` event fires after `session.commit()`, NOT as an audit emit.
- **Idempotent on empty window**: noop run returns 0 + emits summary with `count=0` (no errors, no spurious writes).
- **Partial-UNIQUE compatibility** (Phase 41 D-41-05): seed helper defaults `consumed_at` to NOW so multiple test rows per (user, purpose) coexist without violating `uq_password_reset_tokens_active`. The cleanup cron's WHERE clause filters on `expires_at` only, so consumed status is orthogonal to deletion eligibility — verified by the test fixture pattern.

## Recovery note

Plan 44-11 was implemented inline by the orchestrator (rather than via a spawned executor agent) because the prior agent for 44-10 hit usage limits. Single-file integration test with a single concern, no service/router changes, no schema changes — the inline path was lower-risk than re-spawning under rate-limit pressure.
