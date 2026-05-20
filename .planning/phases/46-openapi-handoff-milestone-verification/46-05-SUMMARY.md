---
phase: 46-openapi-handoff-milestone-verification
plan: 05
subsystem: auth
tags: [verification, race-test, password-reset, atomic-consume, asyncio]
requirements: [VER-10]
dependency-graph:
  requires:
    - apps/backend/app/modules/auth/password_reset_service.py
    - apps/backend/app/modules/auth/password_reset_token_model.py
    - apps/backend/app/modules/auth/router.py
    - apps/backend/app/core/audit_models.py
    - apps/backend/app/core/security.py
    - apps/backend/app/main.py
  provides:
    - apps/backend/tests/integration/test_password_reset_token_replay_race.py
  affects: []
tech-stack:
  added: []
  patterns:
    - real-commit-engine fixture (mirrors Phase 45 D-45-28)
    - asyncio.gather concurrent ASGITransport POSTs
    - pytest.skip on unreachable Postgres (acceptance-equivalent)
    - TRUNCATE ... RESTART IDENTITY CASCADE teardown
key-files:
  created:
    - apps/backend/tests/integration/test_password_reset_token_replay_race.py
  modified: []
decisions:
  - "Verify audit row via AuditLog.resource_id (not a non-existent target_user_id column) — password_reset_completed emit sets resource_id=user_id at password_reset_service.py:408"
  - "Use LifespanManager around create_app() so app.state.sessionmaker + register_user_session_invalidator are wired before the ASGITransport requests fire"
  - "Use Role.RECEPTION (not OWNER) for the seeded user — both succeed at the confirm endpoint; reception is the lower-privilege baseline used elsewhere in race tests"
metrics:
  duration: ~5min
  completed: 2026-05-20
---

# Phase 46 Plan 05: Password-Reset Token-Replay Race Test Summary

One-liner: Real-Postgres `asyncio.gather` race test asserting that two concurrent `POST /password-reset/confirm` calls with the same raw token resolve to exactly one 200 + one 410, exactly one `password_reset_completed` audit row, and exactly one `consumed_at IS NOT NULL` token row — closes VER-10 #1.

## What Was Built

A new integration test file `apps/backend/tests/integration/test_password_reset_token_replay_race.py` (231 lines) that:

1. Defines a local `real_commit_engine` pytest-asyncio fixture which:
   - Builds an `AsyncEngine` from `settings.database_url`.
   - Probes Postgres with `SELECT 1` and `pytest.skip`s cleanly if unreachable (acceptance-equivalent per PATTERNS.md).
   - `TRUNCATE password_reset_tokens, audit_log, users RESTART IDENTITY CASCADE` at teardown so the test is re-runnable.

2. Seeds a single `users` row (RECEPTION, active, email_verified) and a single matching `password_reset_tokens` row (purpose=`password_reset`, `expires_at = now + 1 hour`, `token_hash = sha256(raw_token)`) in a real-commit setup session.

3. Fires two concurrent `POST /api/v1/auth/password-reset/confirm` requests via `asyncio.gather` through an `ASGITransport`-wrapped `AsyncClient`, sharing the same raw token and target user. Lifespan is fired via `LifespanManager` so `app.state.sessionmaker` and the `UserSessionInvalidator` slot are wired exactly as in production.

4. Asserts:
   - `sorted(statuses) == [200, 410]` — exactly one win, exactly one loss (race-tight invariant on the `UPDATE password_reset_tokens ... WHERE consumed_at IS NULL RETURNING ...` SQL from D-44-14).
   - Exactly one `audit_log` row with `action='password_reset_completed' AND resource_id = user_id`.
   - Exactly one `password_reset_tokens` row with `user_id = … AND consumed_at IS NOT NULL`.
   - Sanity check that the consumed-row id matches the seeded token id.

## Why It Matters

Catches any regression that loosens the atomic-consume contract — e.g. a refactor that moves from `UPDATE ... WHERE consumed_at IS NULL RETURNING ...` to a `SELECT-then-UPDATE` pattern would admit a race window where both requests observe `consumed_at IS NULL`, both succeed at the SQL layer, and both write a `password_reset_completed` audit row. The test would then fail with `sorted(statuses) == [200, 200]` or `audit_count == 2`.

The race-tightness comes from PostgreSQL's row-level locking under `READ COMMITTED`: the second concurrent UPDATE blocks on the row lock held by the first, then re-evaluates its WHERE clause after the first commits, observes `consumed_at IS NOT NULL`, returns zero rows → service raises `InvalidOrExpiredTokenError` → router translates to 410 via the global `AppError` handler.

## Verification

```bash
cd apps/backend && uv run pytest tests/integration/test_password_reset_token_replay_race.py -v
# tests/integration/test_password_reset_token_replay_race.py::test_password_reset_token_replay_race PASSED [100%]
# ============================== 1 passed in 0.32s ===============================
```

Grep-gates (acceptance criteria from PLAN.md):

| Gate                                | Count | Min | Status |
| ----------------------------------- | ----- | --- | ------ |
| `asyncio.gather`                    | 4     | 1   | green  |
| `real_commit_engine`                | 3     | 1   | green  |
| `password_reset_completed`          | 4     | 1   | green  |
| `TRUNCATE password_reset_tokens`    | 1     | 1   | green  |
| `min_lines`                         | 231   | 120 | green  |

`--no-cov` was rejected by `pyproject.toml` (no `pytest-cov` plugin installed in this env); ran without it — `1 passed` either way.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Audit-row query column correction**
- **Found during:** Task 1 authoring (when reviewing `audit_models.py`).
- **Issue:** PLAN.md proposed `SELECT count(*) FROM audit_log WHERE action='password_reset_completed' AND target_user_id = :uid`, but `audit_log` has no `target_user_id` column — its schema only carries `actor_user_id`, `actor_email_snapshot`, `action`, `resource_type`, `resource_id`, `payload`, `created_at` (`apps/backend/app/core/audit_models.py:37-64`). The `password_reset_completed` emit (`password_reset_service.py:402-413`) writes `resource_id=user_id` and a flat `user_id=str(user_id)` kwarg that lands in the JSONB `payload`.
- **Fix:** Query via `AuditLog.resource_id == user_id` — the canonical column-level reference. Used ORM-typed `select(func.count()).select_from(AuditLog).where(...)` instead of raw `text()` for type safety.
- **Files modified:** test file only (no production code).
- **Commit:** 65ab502.

**2. [Rule 3 — Blocking] Test framework `--no-cov` flag**
- **Found during:** First test run.
- **Issue:** `pytest-cov` is not installed in the backend venv; `--no-cov` was rejected as unrecognised.
- **Fix:** Ran the test without `--no-cov`; grep gate `1 passed|1 skipped` still satisfied.
- **Files modified:** None.

### Other Implementation Notes

- **Test password literal:** Annotated `_RACE_NEW_PASSWORD` with `# noqa: S105` (bandit "hardcoded password" warning) — it's a test fixture, not a real secret.
- **`LifespanManager` requirement:** The plan's example test code instantiated `AsyncClient(transport=ASGITransport(app=app))` without `LifespanManager`. That would have failed because `get_db` reads `request.app.state.sessionmaker` which is set inside the FastAPI lifespan handler (`app/core/database.py:138-141`). Wrapping with `LifespanManager(app)` is mandatory for HTTP-level integration tests against the real app.

## Auth Gates Encountered

None.

## Threat Flags

None — the test exercises an existing trust boundary (concurrent HTTP clients → password-reset endpoint) that's already covered by the plan's `<threat_model>` (T-46-05-01 through T-46-05-03).

## Self-Check: PASSED

- Test file present: `apps/backend/tests/integration/test_password_reset_token_replay_race.py` (231 lines)
- Commit `65ab502` present in `git log --oneline`
- `pytest tests/integration/test_password_reset_token_replay_race.py -v` → `1 passed in 0.32s`
- All grep gates (asyncio.gather / real_commit_engine / password_reset_completed / TRUNCATE password_reset_tokens) ≥ 1
- No STATE.md or ROADMAP.md modifications
