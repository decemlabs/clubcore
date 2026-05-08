---
phase: 25-memberships-freeze-backend
plan: 01
subsystem: database
tags: [alembic, sqlalchemy, postgres, freeze, memberships, state-machine, exceptions]

# Dependency graph
requires:
  - phase: 24-foundations-tech-debt-bedrock
    provides: 0007_status_taxonomy migration (memberships.status accepts 'frozen'); MEMBERSHIP_STATUS_TRANSITIONS placeholder; LOCKED_AUDIT_EVENTS pre-registers (membership_frozen, membership_unfrozen).
provides:
  - 0008_freeze migration (membership_plans.freeze_days_limit, memberships.freeze_days_limit_snapshot, membership_freeze_periods table + partial unique index)
  - MembershipFreezePeriod ORM model
  - Populated MEMBERSHIP_STATUS_TRANSITIONS map (active->frozen, frozen->{active, cancelled})
  - FreezeLimitExceededError + AlreadyFrozenError exception classes
  - alembic env.py exclusion for partial unique index uq_membership_freeze_periods_active_per_membership
affects: [25-02-repository, 25-03-service, 25-04-schemas-router, 25-05-tests, 26-renewal, 27-notifications]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Partial unique index for active-row uniqueness: install via op.execute() in migration + Index(unique=True, postgresql_where=text(...)) in __table_args__ + autogenerate exclusion in alembic/env.py:_include_object — already canonical via uq_membership_plans_name_alive; Phase 25 mirrors for uq_membership_freeze_periods_active_per_membership."
    - "Snapshot column with backfill: add nullable -> UPDATE COALESCE(plan_value, default) -> SET NOT NULL — mirrors Phase 17 duration_days_snapshot rationale; archived plans backfill to 14."
    - "DEFAULT-then-DROP DEFAULT for required NOT NULL columns on existing rows: ADD COLUMN with server_default to backfill, then alter_column to drop default so future inserts must pass an explicit value (mirror Phase 17 duration_days immutability)."

key-files:
  created:
    - apps/backend/alembic/versions/0008_freeze.py
    - .planning/phases/25-memberships-freeze-backend/25-01-SUMMARY.md
    - .planning/phases/25-memberships-freeze-backend/deferred-items.md
  modified:
    - apps/backend/alembic/env.py
    - apps/backend/app/modules/memberships/models.py
    - apps/backend/app/modules/memberships/constants.py
    - apps/backend/app/core/exceptions.py
    - apps/backend/tests/unit/memberships/test_state_machine.py

key-decisions:
  - "Migration 0008_freeze chains directly from 0007_status_taxonomy (D-25-01 confirms the freeze-only scope; renewal column lands in Phase 26's 0009)."
  - "Backfill freeze_days_limit_snapshot uses COALESCE(plan.freeze_days_limit, 14) for archived plans (snapshot lock-in, mirrors duration_days_snapshot rationale)."
  - "Partial unique index uq_membership_freeze_periods_active_per_membership installed via op.execute() (autogenerate-stable pattern), name literal-pinned for service-layer IntegrityError discrimination in plan 25-03."
  - "MembershipFreezePeriod composes Base + UUIDPkMixin + TimestampMixin only (no SoftDeleteMixin); lifecycle encoded by ended_at IS NULL per D-25-04. Class docstring documents the created_at vs started_at semantic distinction."
  - "Downgrade is documented as data-lossy: snapshot column drop is irreversible (D-25-03)."

patterns-established:
  - "Constraint-name literal-pinning chain: migration op.f(...) -> ORM __table_args__ short name -> alembic env.py exclusion (when partial/expression index) -> service-layer IntegrityError discriminator. Each link MUST agree."
  - "MEMBERSHIP_STATUS_TRANSITIONS as MappingProxyType is the single source of truth for membership state-machine; populating placeholders in successive phases keeps the unit-test matrix authoritative."

requirements-completed:
  - MEM-FRZ-01
  - MEM-FRZ-02
  - MEM-FRZ-03

# Metrics
duration: 6min
completed: 2026-05-08
---

# Phase 25 Plan 01: Freeze Schema Foundation Summary

**Schema, ORM, transitions map, and exception classes for the membership freeze flow — bedrock for plans 25-02..05.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-05-08T20:25:58Z
- **Completed:** 2026-05-08T20:31:50Z
- **Tasks:** 3
- **Files modified:** 5 (1 created migration, 4 modified)

## Accomplishments
- Migration `0008_freeze.py` adds `membership_plans.freeze_days_limit` (NOT NULL, CHECK > 0) with backfill to 14, `memberships.freeze_days_limit_snapshot` (NOT NULL) backfilled via `COALESCE(plan.freeze_days_limit, 14)`, and the `membership_freeze_periods` table with the partial unique index `uq_membership_freeze_periods_active_per_membership` installed via `op.execute()`.
- ORM model `MembershipFreezePeriod` (Base + UUIDPkMixin + TimestampMixin) added with FKs to `memberships` (RESTRICT) and `users` (started_by RESTRICT, ended_by SET NULL). `Membership.freeze_days_limit_snapshot` and `MembershipPlan.freeze_days_limit` columns extended; CHECK constraint mirrored in `__table_args__`.
- `MEMBERSHIP_STATUS_TRANSITIONS` populated for the freeze edges (`active -> frozen` and `frozen -> {active, cancelled}`); Phase 24 placeholder removed.
- `FreezeLimitExceededError` and `AlreadyFrozenError` (both `ConflictError`, status_code 409) added to `app.core.exceptions` for plan 25-03 to consume.
- `alembic/env.py:_include_object` exclusion list now suppresses `uq_membership_freeze_periods_active_per_membership` from autogenerate, keeping `alembic check` clean.

## Task Commits

Each task was committed atomically:

1. **Task 1: Migration 0008_freeze.py** — `19af3f0` (feat)
2. **Task 2: ORM model + columns + env.py exclusion** — `0f5ca85` (feat)
3. **Task 3: Transitions map + exception classes** — `e820789` (feat)

## Files Created/Modified
- `apps/backend/alembic/versions/0008_freeze.py` — new migration: freeze_days_limit + freeze_days_limit_snapshot + membership_freeze_periods + partial unique index + backfill (COALESCE).
- `apps/backend/app/modules/memberships/models.py` — `MembershipPlan.freeze_days_limit` + `Membership.freeze_days_limit_snapshot` + new `MembershipFreezePeriod` ORM class.
- `apps/backend/alembic/env.py` — added `uq_membership_freeze_periods_active_per_membership` to the autogenerate exclusion tuple.
- `apps/backend/app/modules/memberships/constants.py` — `MEMBERSHIP_STATUS_TRANSITIONS` populated with freeze edges; module docstring updated to reflect Phase 25 scope.
- `apps/backend/app/core/exceptions.py` — added `FreezeLimitExceededError` (`code='freeze_limit_exceeded'`, 409) and `AlreadyFrozenError` (`code='already_frozen'`, 409).
- `apps/backend/tests/unit/memberships/test_state_machine.py` — Phase 24 contents-test renamed and updated to assert the populated freeze edges (deviation Rule 3, see below).
- `.planning/phases/25-memberships-freeze-backend/deferred-items.md` — records pre-existing ruff E501 in `app/core/permissions.py:45` (out of scope).

## Decisions Made
- Followed plan as specified — D-25-01..05, D-25-14, D-25-21 implemented verbatim.
- Backfill SQL inlined as a single-line statement (necessary to satisfy the plan's `grep 'COALESCE.*freeze_days_limit FROM membership_plans'` acceptance check) using table alias `m` to keep the line under 100 chars (ruff E501).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Renamed and updated `test_membership_status_transitions_phase24_contents`**
- **Found during:** Task 3 (constants update)
- **Issue:** The Phase 24 unit test hard-coded the old transitions contents (`active: {expired, cancelled}`, `frozen: frozenset()`); after Plan 25-01 populates the freeze edges per D-25-14 the test would fail CI.
- **Fix:** Renamed to `test_membership_status_transitions_phase25_contents`; asserts populated edges (`active: {expired, cancelled, frozen}`, `frozen: {active, cancelled}`); terminal sets unchanged.
- **Files modified:** `apps/backend/tests/unit/memberships/test_state_machine.py`
- **Verification:** `uv run pytest tests/unit/memberships/test_state_machine.py` — 12/12 passed; full unit suite 301/301 passed.
- **Committed in:** `e820789` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** No scope creep; the test was directly coupled to the constants this plan modifies, so the update is a same-UoW correctness requirement.

## Issues Encountered
- Initial draft of the backfill SQL split the `COALESCE` clause across two concatenated string literals; this defeated the plan's single-line `grep 'COALESCE.*freeze_days_limit FROM membership_plans'` acceptance check. Resolved by introducing a table alias `m` so the predicate fits on one line within ruff's 100-char limit.
- Ruff reports a pre-existing E501 at `app/core/permissions.py:45` (Phase 22 line). Out of scope for this plan; recorded in `deferred-items.md`.

## Verification Evidence

- `uv run alembic upgrade head` — clean.
- `uv run alembic downgrade -1 && uv run alembic upgrade head` — clean (cycle confirmed).
- `uv run alembic check` — `No new upgrade operations detected.` (zero ORM/migration drift).
- `uv run mypy app/` — `Success: no issues found in 71 source files`.
- `uv run ruff check` on Plan 25-01 files — `All checks passed!`.
- `uv run pytest tests/unit/` — 301/301 passed.
- Importability: `from app.modules.memberships.models import MembershipFreezePeriod; from app.core.exceptions import FreezeLimitExceededError, AlreadyFrozenError` — OK; `MembershipFreezePeriod.__tablename__ == 'membership_freeze_periods'`; `FreezeLimitExceededError.code == 'freeze_limit_exceeded'`, status_code 409; `AlreadyFrozenError.code == 'already_frozen'`, status_code 409.
- `MEMBERSHIP_STATUS_TRANSITIONS['active'] == frozenset({'expired', 'cancelled', 'frozen'})`; `MEMBERSHIP_STATUS_TRANSITIONS['frozen'] == frozenset({'active', 'cancelled'})`.

## User Setup Required
None — no external service configuration required. (`.env` was bootstrapped from `.env.example` to run alembic locally; gitignored.)

## Next Phase Readiness
- Plan 25-02 (repository helpers) can import `MembershipFreezePeriod`, query the partial unique index, and rely on `freeze_days_limit_snapshot` being NOT NULL on every existing row.
- Plan 25-03 (service layer) can `raise FreezeLimitExceededError(...)` and `AlreadyFrozenError(...)`; the central transition guard `_assert_can_transition` (Phase 24 D-24-04) now permits the freeze edges automatically.
- Plan 25-04 (schemas/router) can add `MembershipStatus.FROZEN` and the freeze projection fields without further constants changes.
- No blockers. The pre-existing ruff E501 in `permissions.py` is unrelated and tracked in `deferred-items.md`.

## Self-Check: PASSED

**Files verified:**
- FOUND: apps/backend/alembic/versions/0008_freeze.py
- FOUND: apps/backend/app/modules/memberships/models.py (MembershipFreezePeriod present)
- FOUND: apps/backend/app/modules/memberships/constants.py (freeze edges populated)
- FOUND: apps/backend/app/core/exceptions.py (FreezeLimitExceededError + AlreadyFrozenError present)
- FOUND: apps/backend/alembic/env.py (uq_membership_freeze_periods_active_per_membership in exclusion)
- FOUND: apps/backend/tests/unit/memberships/test_state_machine.py (phase25 test name)

**Commits verified:**
- FOUND: 19af3f0 (Task 1)
- FOUND: 0f5ca85 (Task 2)
- FOUND: e820789 (Task 3)

---
*Phase: 25-memberships-freeze-backend*
*Completed: 2026-05-08*
