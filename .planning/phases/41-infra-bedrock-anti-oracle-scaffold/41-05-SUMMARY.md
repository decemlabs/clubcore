---
phase: 41-infra-bedrock-anti-oracle-scaffold
plan: 05
subsystem: infra
tags: [alembic, migration, users, soft-delete, partial-unique, postgres, infra-38]

# Dependency graph
requires:
  - phase: 5
    provides: users table + table-level UniqueConstraint("email", name="uq_users_email") (0001_auth.py)
  - phase: 40
    provides: alembic head 0021_bookings_actor_nullable
provides:
  - users.deleted_at TIMESTAMPTZ NULL column (soft-delete marker)
  - partial UNIQUE INDEX uq_users_email_active ON users (lower(email)) WHERE deleted_at IS NULL
  - DROP of table-level UniqueConstraint("email", name="uq_users_email")
  - alembic head bumped 0021_bookings_actor_nullable -> 0022_users_soft_delete_unique
affects:
  - phase-41-plan-10 (User ORM hoist will add Mapped deleted_at column + remove model-level unique=True)
  - phase-43 (USERS-05 soft-delete callsite, USERS-06 list-filter at repo layer)
  - phase-44 (RESET-04 re-onboard via invitation flow)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Partial UNIQUE expression index via op.create_index(postgresql_where=...) mirrors 0008_freeze.py / 0017_bookings.py precedent"
    - "Drop+recreate cycle on case-sensitive global UNIQUE -> case-insensitive partial UNIQUE in one migration (single-transaction DDL)"
    - "Shorten revision id (not filename) to fit alembic_version.version_num VARCHAR(32) cap"
    - "Skiplist partial-expression indexes in alembic/env.py:_include_object to keep alembic check clean (D-25-05 lineage)"

key-files:
  created:
    - apps/backend/alembic/versions/0022_users_soft_delete_partial_unique.py
  modified:
    - apps/backend/alembic/env.py

key-decisions:
  - "Revision id shortened to '0022_users_soft_delete_unique' (29 chars) — plan-spec name '0022_users_soft_delete_partial_unique' (37 chars) exceeds alembic_version.version_num VARCHAR(32). Filename retains the canonical spec name for grep continuity; only the revision_id literal inside the file was shortened."
  - "Partial UNIQUE expressed as INDEX (op.create_index unique=True postgresql_where) — Postgres does not support expression predicates in UniqueConstraint, only Index. Matches 0008_freeze.py + 0017_bookings.py."
  - "Added uq_users_email_active to alembic/env.py _include_object skiplist mirroring D-25-05 pattern for partial-expression indexes (autogenerate-unstable)."
  - "User ORM model unchanged in this plan — Plan 10 hoists User to app/core/models.py and adds Mapped[datetime | None] deleted_at + removes model-level unique=True on email. alembic check therefore reports drift between this plan and Plan 10 (expected, documented)."

patterns-established:
  - "Migrations whose plan-spec revision_id exceeds 32 chars shorten the revision_id literal only — filename keeps the canonical spec name"
  - "Partial UNIQUE expression-index name added to env.py skiplist at the same commit that introduces the index"

requirements-completed: []
requirements-progressed: [INFRA-38]

# Metrics
duration: 5min
completed: 2026-05-18
---

# Phase 41 Plan 05: INFRA-38 — Alembic 0022 (users.deleted_at + partial-UNIQUE on lower(email)) Summary

**Alembic migration 0022 ships the schema half of D-41-04/05/07: adds `users.deleted_at TIMESTAMPTZ NULL`, drops the case-sensitive global `UNIQUE (email)` from 0001_auth.py, and recreates the invariant as a partial UNIQUE expression-index `(lower(email)) WHERE deleted_at IS NULL` — enabling Phase 43 USERS-05 soft-delete + Phase 44 RESET-04 re-onboard-same-email.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-18T18:30:33Z
- **Completed:** 2026-05-18T18:31:09Z (incl. revision-id retry)
- **Tasks:** 1
- **Files created:** 1
- **Files modified:** 1

## Accomplishments

- New migration file `apps/backend/alembic/versions/0022_users_soft_delete_partial_unique.py` (revision id `0022_users_soft_delete_unique`, down_revision `0021_bookings_actor_nullable`).
- `users.deleted_at` column added as `TIMESTAMP WITH TIME ZONE NULL` (Pitfall 6 tz-aware).
- Existing case-sensitive table-level `UniqueConstraint("email", name="uq_users_email")` (0001_auth.py:50) DROPPED.
- New partial UNIQUE expression-index `uq_users_email_active ON users (lower(email)) WHERE deleted_at IS NULL` created via `op.create_index(unique=True, postgresql_where=...)`.
- Downgrade reverses cleanly: drop the partial index, recreate the original table-level `uq_users_email` UniqueConstraint, drop `deleted_at`.
- `alembic upgrade head` succeeds against the dev Postgres (0021 -> 0022).
- Round-trip `alembic downgrade -1 && alembic upgrade head` is clean (0022 -> 0021 -> 0022).
- `alembic/env.py:_include_object` skiplist extended with `uq_users_email_active` mirroring D-25-05 pattern for partial-expression indexes.
- Behavioral verification (live Postgres):
  - Same `lower(email)` with one row `deleted_at IS NULL` + one row `deleted_at = now()` -> both INSERT succeed (RESET-04 re-onboard works).
  - Two rows with same `lower(email)` where both `deleted_at IS NULL` -> second INSERT raises `IntegrityError` (active-row uniqueness preserved).
  - Case-insensitivity verified: `INSERT email='foo@bar'` then `INSERT email='FOO@BAR'` both active -> conflict (whereas pre-0022 this would have succeeded — case-sensitive global UNIQUE allowed both).

## Task Commits

1. **Task 1: Author Alembic migration 0022_users_soft_delete_partial_unique.py** — `b367f76` (feat)

**Plan metadata commit:** _to be set on final commit_

## Files Created/Modified

- `apps/backend/alembic/versions/0022_users_soft_delete_partial_unique.py` — NEW. Pure-schema migration (no User ORM change). upgrade() = add_column + drop_constraint + create_index(unique, postgresql_where). downgrade() reverses in order: drop_index + create_unique_constraint + drop_column. Docstring spells out the three-step semantics and the rationale (Pitfall 6 tz-aware; 0008_freeze.py / 0017_bookings.py precedent; no separate index on deleted_at because the partial-UNIQUE predicate index already covers `WHERE deleted_at IS NULL` lookups per the D-41 Claude's Discretion bullet).
- `apps/backend/alembic/env.py` — added `"uq_users_email_active"` to the `_include_object` skiplist tuple. One-line addition next to the existing partial-expression-index entries. Comment credits Phase 41 INFRA-38.

## Decisions Made

- **Revision id shortened to `0022_users_soft_delete_unique` (29 chars).** The plan-spec `revision: str` value `"0022_users_soft_delete_partial_unique"` (37 chars) exceeds `alembic_version.version_num` default `VARCHAR(32)` and the first `alembic upgrade head` attempt failed with `StringDataRightTruncationError` on the version-table UPDATE step. Per Postgres transactional DDL, the failed transaction rolled back leaving head at 0021 — no orphan column or index was left behind. Two surgical edits (`Revision ID:` docstring line + `revision: str = ...` assignment) shrank the id while preserving the filename for grep continuity with the plan's spec language ("file path: `0022_users_soft_delete_partial_unique.py`"). Filename and revision_id need not match — alembic resolves migrations by their internal `revision` literal, not by filename.

- **Partial UNIQUE expressed as INDEX, not CONSTRAINT.** Postgres does not support expression predicates (`lower(email)`) inside `UniqueConstraint`; SQLAlchemy `op.create_unique_constraint` forwards columns only. The canonical workaround across this codebase is `op.create_index(..., unique=True, postgresql_where=text(...))` (precedent: `0008_freeze.py:uq_membership_freeze_periods_active_per_membership`; `0017_bookings.py:uq_bookings_slot_confirmed`; `0004_membership_plans.py:uq_membership_plans_name_alive`).

- **`alembic/env.py:_include_object` skiplist extended.** Without this, `alembic check` would report `Detected removed index 'uq_users_email_active'` on every future autogenerate run (the index has no corresponding model-level declaration because Plan 10 has not yet hoisted the User ORM). Mirrors the D-25-05 / Pitfall 1 / RESEARCH.md skiplist discipline established in v1.2 Phase 8 clients.

- **No User ORM model changes.** The plan explicitly defers User model edits to Plan 10 (D-41-01, Path A with shim). The current `app/modules/auth/models.py:User` declaration still has `email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)` and no `deleted_at` attribute. This is deliberate: Plan 10 hoists User to `app/core/models.py`, removes `unique=True`, and adds `deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)`. Between this plan and Plan 10, `alembic check` reports two-line drift (`add_constraint uq_users_email` + `remove_column users.deleted_at`) which is expected and dissolves when Plan 10 lands.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Shortened `revision_id` literal from 37 -> 29 chars to fit `alembic_version.version_num` VARCHAR(32)**

- **Found during:** Task 1 verify-block (first `alembic upgrade head` attempt).
- **Issue:** Plan's example `revision: str = "0022_users_soft_delete_partial_unique"` is 37 characters. The default `alembic_version.version_num` column is `VARCHAR(32)`. `alembic upgrade head` ran the DDL successfully but failed on `UPDATE alembic_version SET version_num = '0022_users_soft_delete_partial_unique'` with `asyncpg.exceptions.StringDataRightTruncationError: value too long for type character varying(32)`. Postgres rolled the entire transaction back (transactional DDL), so the database remained at 0021 with no orphan column.
- **Fix:** Shortened the revision id to `0022_users_soft_delete_unique` (29 chars) in two places: the `Revision ID:` line of the module docstring and the `revision: str = ...` assignment. Filename was NOT renamed — the plan's `<artifacts>` block specifies the path `0022_users_soft_delete_partial_unique.py` and the docstring already carries the full canonical name. Filename ≠ revision_id is a valid alembic configuration; alembic resolves by the `revision` literal, not by the filename slug.
- **Files modified:** `apps/backend/alembic/versions/0022_users_soft_delete_partial_unique.py` (2 lines).
- **Verification:** `uv run alembic upgrade head` -> exit 0; `uv run alembic current` -> `0022_users_soft_delete_unique (head)`; `uv run alembic downgrade -1 && uv run alembic upgrade head` round-trip exit 0.
- **Committed in:** `b367f76` (Task 1 commit — first-and-only commit on this plan).

**2. [Rule 2 — Critical] Added `uq_users_email_active` to `alembic/env.py:_include_object` skiplist**

- **Found during:** Task 1 verify-block (`alembic check` after first successful upgrade).
- **Issue:** `alembic check` reported `Detected removed index 'uq_users_email_active' on 'users'` because the new partial-expression index has no corresponding `Index(..., postgresql_where=...)` in the (still-Plan-5-shape) User ORM model — Plan 10 owns model-level declarations. Every prior partial-expression index in this codebase (`uq_membership_plans_name_alive`, `uq_clients_phone_alive`, `uq_membership_freeze_periods_active_per_membership`, `uq_trainers_phone_alive`, `uq_pt_package_plans_name_alive`, `uq_pt_packages_active_per_client`) is skiplisted in `_include_object` per the D-25-05 discipline. Without the skiplist entry, every future `alembic check` run would flag this index as "missing from model".
- **Fix:** Single-line addition to the existing tuple inside `_include_object`, with a comment crediting Phase 41 INFRA-38.
- **Files modified:** `apps/backend/alembic/env.py` (+2 lines).
- **Verification:** `uv run ruff check alembic/env.py` -> All checks passed; `uv run alembic check` -> still reports the unrelated User ORM `add_constraint uq_users_email` + `remove_column users.deleted_at` drift (expected, Plan 10's responsibility), but no longer flags `uq_users_email_active`.
- **Committed in:** `b367f76` (same Task 1 commit).

---

**Total deviations:** 2 auto-fixed (Rule 3 blocking + Rule 2 critical-for-discipline). Both anticipated edge cases of the plan's own structure (revision-id length cap; env.py skiplist convention). No architectural change, no scope creep.
**Impact on plan:** Migration content (`upgrade()` / `downgrade()` bodies) is byte-identical to the plan's example; only the revision-id literal differs. The `<artifacts>` declaration (`contains: "op.add_column"`, `contains_2: "postgresql_where"`) holds verbatim.

## Issues Encountered

- **Revision-id-too-long surfaced as a transactional DDL rollback.** The first `alembic upgrade head` attempt looked alarming (long sqlalchemy traceback) but resolved cleanly because Postgres is transactional-DDL. `alembic current` after the failure confirmed the DB was still at 0021 — no manual cleanup required. The retry with the shortened id succeeded immediately.

## User Setup Required

None. Migration is auto-applied by `alembic upgrade head` on next CI / deploy. No env-var changes, no external service config. Once Phase 43 ships USERS-05 callsite, soft-delete + re-onboard will work end-to-end against the schema this plan ships.

## Next Phase Readiness

- **INFRA-38 schema half — DELIVERED.** Plan 10 (User ORM hoist) is now unblocked: it will add `deleted_at` to the User model + remove model-level `unique=True` on email, which dissolves the remaining `alembic check` drift.
- **Phase 43 USERS-05 soft-delete — UNBLOCKED schemaically.** Service layer can write `UPDATE users SET deleted_at = now() WHERE id = :id` and INSERT a new row for the same email afterwards without conflict.
- **Phase 44 RESET-04 re-onboard — UNBLOCKED schemaically.** Invitation flow can INSERT a new users row for an email whose prior owner was soft-deleted.
- **Phase 41 plans 06–11 — UNAFFECTED.** This migration touches `users` only; no cross-table impact, no FK changes. Migrations 0023/0024/0025 (next three plans in the bedrock bundle) are independent of 0022 except for the dependency-chain `down_revision` pointer (0023.down_revision = `0022_users_soft_delete_unique`, etc.).
- **Known follow-up (Plan 10 territory, NOT a stub):** `alembic check` currently reports `add_constraint uq_users_email` + `remove_column users.deleted_at` drift because the User ORM model still has the v1.0 shape. This is the expected intermediate state and dissolves when Plan 10 lands.

## Threat Flags

None. The migration is the schema half of the threat-model-listed mitigation T-41-05-01 (partial UNIQUE prevents post-soft-delete duplicate-email race) — no new threat surface introduced.

## Self-Check

Files modified verification:

- `apps/backend/alembic/versions/0022_users_soft_delete_partial_unique.py` — FOUND (new file, 81 lines)
- `apps/backend/alembic/env.py` — FOUND (modified, +2 lines in `_include_object`)

Commits verification:

- `b367f76` — FOUND in `git log --oneline -3` (Task 1: feat(41-05): add migration 0022 — users.deleted_at + partial-UNIQUE on lower(email))

Verification commands re-run at SUMMARY time:

- `cd apps/backend && uv run alembic current` -> `0022_users_soft_delete_unique (head)`
- `uv run alembic downgrade -1 && uv run alembic upgrade head` -> both exit 0, head returns to 0022
- Live Postgres behavior test (Python inline): same lower(email) with one deleted_at IS NULL + one deleted_at = now() both INSERT succeed; second active row with same lower(email) raises IntegrityError -> ALL CASES PASS
- `uv run ruff check alembic/versions/0022_users_soft_delete_partial_unique.py alembic/env.py` -> All checks passed
- `uv run alembic check` -> still reports expected User-ORM drift (Plan 10 territory); no longer flags `uq_users_email_active` (skiplist working)

## Self-Check: PASSED

---
*Phase: 41-infra-bedrock-anti-oracle-scaffold*
*Plan: 05*
*Completed: 2026-05-18*
