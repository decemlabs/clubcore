---
phase: 42-email-transport-layer-email-otp-fallback
plan: 15
subsystem: database
tags: [alembic, postgres, migration, otp, partial-unique, regression-test]

# Dependency graph
requires:
  - phase: 42-email-transport-layer-email-otp-fallback
    provides: "migration 0027 otp_codes channel discriminator (AUTH-EM-01)"

provides:
  - "CR-04 defensive UPDATE pass in migration 0027 before partial-UNIQUE creation"
  - "Regression test seeding colliding rows to guard against future partial-UNIQUE violations"

affects: [Phase 42 deployment, Phase 44 password-reset, any future otp_codes writer]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Defensive pre-UNIQUE-creation UPDATE pass in alembic upgrade() (DISTINCT ON keeps latest per group)"
    - "Migration regression test seeding pre-column-add rows via direct async engine (not SAVEPOINT) so rows visible to alembic subprocess"

key-files:
  created:
    - apps/backend/tests/integration/alembic/test_migration_0027_cleanup.py
    - apps/backend/tests/integration/alembic/__init__.py
  modified:
    - apps/backend/alembic/versions/0027_otp_codes_channel_discriminator.py

key-decisions:
  - "CR-04 defensive UPDATE uses DISTINCT ON (user_id, channel) ORDER BY created_at DESC — keeps the newest unconsumed row per (user_id, channel) pair, idempotent on a clean schema"
  - "Regression tests use subprocess.run('uv run alembic ...') with a real-commit direct async engine (not SAVEPOINT) so seeded rows are visible to alembic subprocess commands (mirrors test_alembic_clean.py pattern)"
  - "Defensive UPDATE placed AFTER create_check_constraint (channel column exists) and BEFORE create_index (partial-UNIQUE creation) — strictly bounded position in upgrade() body"

patterns-established:
  - "Migration regression test pattern: seed colliding data at schema N-1, upgrade to N, assert correctness and cleanup — usable for any future partial-UNIQUE migration risk"

requirements-completed:
  - AUTH-EM-01

# Metrics
duration: 70min
completed: 2026-05-19
---

# Phase 42 Plan 15: CR-04 Defensive Cleanup for Migration 0027 Summary

**Defensive DISTINCT ON UPDATE pass added to Alembic migration 0027 before partial-UNIQUE creation, closing CR-04 deploy-data-risk with a regression test seeding duplicate otp_codes rows**

## Performance

- **Duration:** ~70 min (Task 1 + Task 2 commits + checkpoint human-verify round-trip)
- **Started:** 2026-05-19T09:56:11Z
- **Completed:** 2026-05-19T10:04:01Z
- **Tasks:** 3 (Task 1: migration fix, Task 2: regression test, Task 3: human-verify checkpoint)
- **Files modified:** 3

## Accomplishments

- Added `op.execute()` defensive UPDATE pass in `migration 0027 upgrade()` that marks duplicate `(user_id, channel) consumed_at IS NULL` rows as consumed (keeping latest by `created_at DESC`) before the `create_index uq_otp_codes_user_channel_active` call
- Updated migration 0027 module docstring with a CR-04 block citing the bounded data-risk rationale, VERIFICATION.md, and REVIEW.md
- Created `tests/integration/alembic/test_migration_0027_cleanup.py` with two tests (`test_0027_upgrade_with_colliding_unconsumed_rows` and `test_0027_round_trip_with_data`) that seed colliding rows at the 0026 schema state and assert upgrade succeeds without a partial-UNIQUE violation
- Alembic round-trip verified against the live Postgres test DB: `downgrade 0028->0027`, `downgrade 0027->0026`, `upgrade head` — all passed cleanly; CR-04 closed

## Task Commits

Each task was committed atomically:

1. **Task 1: Add defensive UPDATE pass to migration 0027 + update docstring** - `d99ee34` (fix)
2. **Task 2: Add regression test seeding colliding rows + asserting upgrade succeeds** - `04dfe7e` (test)
3. **Task 3: Alembic round-trip schema push validation** - checkpoint:human-verify (no code commit; approved by user)

## Files Created/Modified

- `apps/backend/alembic/versions/0027_otp_codes_channel_discriminator.py` — Added defensive UPDATE `op.execute()` block (lines 95-107) and CR-04 rationale in module docstring (lines 41-53)
- `apps/backend/tests/integration/alembic/test_migration_0027_cleanup.py` — New 268-line regression test; two async tests using real-commit direct engine + subprocess alembic calls
- `apps/backend/tests/integration/alembic/__init__.py` — New empty init to make the directory a package

## Decisions Made

- Used `DISTINCT ON (user_id, channel) ORDER BY user_id, channel, created_at DESC` Postgres semantics (project is Postgres 16 per CLAUDE.md); no SQLite fallback needed
- Regression tests use `subprocess.run('uv run alembic ...')` (blocking) and a direct async engine with real COMMITs (not SAVEPOINT-wrapped `db_session`) so seeded rows are visible to alembic's own DB connection — matches the pattern established by `test_alembic_clean.py`
- Cleanup: DELETE seeded rows in a `finally` block so subsequent test runs start on a clean state
- Skips tests gracefully when `DATABASE_URL` is unreachable rather than failing (avoids CI noise when Postgres container is not up)

## Deviations from Plan

None - plan executed exactly as written. The defensive UPDATE, docstring update, and regression tests were all specified in the plan; the code was written according to spec without deviations.

## Issues Encountered

None - migration changes applied cleanly, tests passed on the live DB, and the round-trip was verified by the user.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- CR-04 closed: `migration 0027` is now safe to deploy even if future writers (Phase 43+ user-session code, Phase 44 password-reset) accumulate `user_id IS NOT NULL + consumed_at IS NULL` rows before a deploy
- Round-trip migration discipline preserved (cross-cutting Phase 42 constraint)
- Regression test is the first migration-level integration test in the `tests/integration/alembic/` directory; sets a reusable pattern for future partial-UNIQUE migrations

---
*Phase: 42-email-transport-layer-email-otp-fallback*
*Completed: 2026-05-19*
