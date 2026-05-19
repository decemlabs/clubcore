---
phase: 43-multi-user-admin-module
plan: 01
subsystem: database
tags: [alembic, postgres, sqlalchemy, user-lifecycle, soft-delete, migrations]

# Dependency graph
requires:
  - phase: 41-infra-bedrock-anti-oracle-scaffold
    provides: hoisted User ORM in app.core.models (D-41-01); 0022 partial-UNIQUE on lower(email) WHERE deleted_at IS NULL; 0025 password_reset_tokens with purpose='invitation'
  - phase: 42-email-transport-layer-email-otp-fallback
    provides: alembic head at 0029_email_send_log_hygiene; constraint-naming op.f() discipline
provides:
  - Alembic migration 0030_users_lifecycle_columns (head)
  - users.is_active BOOLEAN NOT NULL DEFAULT true
  - users.status TEXT NOT NULL DEFAULT 'active' CHECK in ('active','pending_invitation')
  - users.deactivated_at TIMESTAMPTZ NULL
  - users.deactivated_by_user_id UUID NULL FK users.id ON DELETE SET NULL
  - users.password_hash now nullable (pending_invitation rows carry NULL until Phase 44 RESET-04)
  - User ORM mirror in app.core.models with 4 new Mapped columns + deleted_at + nullable password_hash
affects:
  - 43-04 (repository.py — list_alive/get_alive use new columns)
  - 43-05 (service.py — create/deactivate/reactivate/soft-delete consume status + lifecycle)
  - 43-07 (auth.service rotate_refresh joins is_active=true AND deleted_at IS NULL — D-43-20)
  - Phase 44 RESET-04 (invitation-accept sets status='active' + password_hash from NULL)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lifecycle columns as explicit discriminator (status TEXT + CHECK) over derived (password_hash IS NULL) per D-43-06"
    - "Self-FK with ON DELETE SET NULL for audit-survives-actor-delete (mirrors audit_log.actor_user_id D-41-08)"
    - "Two-column CHECK correlating is_active and deactivated_at at DB layer (mirrors 0008_freeze pattern)"

key-files:
  created:
    - apps/backend/alembic/versions/0030_users_lifecycle_columns.py
  modified:
    - apps/backend/app/core/models.py

key-decisions:
  - "Per D-43-05: single migration 0030 outside the 0022-0025 bedrock bundle (D-41-15 scope)"
  - "Per D-43-06: status as explicit TEXT column with CHECK, NOT derived from password_hash IS NULL (debuggable + admits future statuses)"
  - "Per D-43-06: deactivated_by_user_id ON DELETE SET NULL — preserves deactivation history past deactivator soft-delete"
  - "Per D-43-08: User ORM extended at app.core.models (hoisted location), NOT the auth.models.py re-export shim"
  - "Phase 41 0022 deleted_at column got its ORM Mapped mirror here — was DB-only before"

patterns-established:
  - "Pattern: lifecycle CHECK constraints wrapped in op.f() so project naming_convention does not double-prefix"
  - "Pattern: dropping NOT NULL is reversed in downgrade by re-asserting NOT NULL (data backfill required in prod)"

requirements-completed: [USERS-05]

# Metrics
duration: ~14min
completed: 2026-05-19
---

# Phase 43 Plan 01: Schema Foundation — Users Lifecycle Columns Summary

**Alembic 0030 lands 4 user-lifecycle columns (is_active, status, deactivated_at, deactivated_by_user_id) + 2 CHECK constraints + self-FK + drops password_hash NOT NULL; User ORM mirrored at app.core.models; round-trip clean against live Postgres.**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-05-19T13:36:00Z
- **Completed:** 2026-05-19T13:49:52Z
- **Tasks:** 3 (2 implementation + 1 BLOCKING checkpoint, auto-approved)
- **Files modified:** 2

## Accomplishments

- Alembic migration 0030 created with 4 ALTERs + 2 CHECKs + self-FK + password_hash NOT NULL drop
- User ORM in `app.core.models` extended with 4 lifecycle Mapped columns + `deleted_at` mirror; password_hash typed `Mapped[str | None]`
- Round-trip checkpoint PASS: `upgrade head → downgrade -1 → upgrade head` clean against live Postgres
- Constraint inspection PASS: both `ck_users_lifecycle_consistency` and `ck_users_status` present + self-FK `ON DELETE SET NULL` verified via pg_dump

## Task Commits

Each task was committed atomically:

1. **Task 1: Write Alembic migration 0030_users_lifecycle_columns** — `9a789fc` (feat)
2. **Task 2: Extend User ORM in app/core/models.py with 4 lifecycle columns** — `e4014a2` (feat)
3. **Task 3: [BLOCKING] Alembic round-trip checkpoint (D-43-36)** — no code commit (verification-only gate; auto-approved under --auto since objective verification PASSED)

**Plan metadata commit:** pending (final commit after STATE.md + ROADMAP.md update)

## Files Created/Modified

- `apps/backend/alembic/versions/0030_users_lifecycle_columns.py` (created) — DDL adds 4 columns, 2 CHECKs, self-FK with SET NULL, drops password_hash NOT NULL; downgrade reverses in strict order
- `apps/backend/app/core/models.py` (modified) — User ORM extended with `is_active`, `status` (Literal-typed SAEnum non-native), `deactivated_at`, `deactivated_by_user_id` (self-FK), `deleted_at` (mirror of 0022), and `password_hash: Mapped[str | None]`

## Decisions Made

- **deleted_at ORM mirror added here, not in Phase 41:** Phase 41 plan-05 shipped the DB column only; the Mapped attribute was deferred to "first consumer" (D-43-08 catch-up). Phase 43 is the first consumer (USERS-05), so the mirror lands here.
- **`status` as native_enum=False SAEnum with length=32:** matches the `user_status` Python-side enum semantics with a DB-side TEXT + CHECK, future-proof for adding `'invited_expired'` in v1.7 without an enum-type ALTER.
- **No new index on `deactivated_by_user_id`:** Per D-43 Claude's Discretion — read-side audit join is rare and not on a hot path; partial-UNIQUE on `(lower(email)) WHERE deleted_at IS NULL` (0022) already covers all single-user lookups.

## Deviations from Plan

None - plan executed exactly as written.

One minor inline correction: ruff flagged `from sqlalchemy.dialects.postgresql import UUID as PgUUID` with N811 (Constant imported as non-constant). Added `# noqa: N811` to match the established convention in `app/modules/auth/models.py:22`. This is a notation correction inside Task 2, not a deviation in behavior.

## Issues Encountered

**Pre-existing mypy attr-defined drift on auth.models re-export shim** (`User` not "explicitly exported"). Unrelated to this plan — verified by stashing changes and re-running mypy on auth/service.py. The shim attr-defined drift was already present (Phase 41 D-41-01 known issue tracked as DEFER-41-shim for v1.7).

**Anticipated mypy follow-up in auth.service.py:** Changing `password_hash: Mapped[str]` to `Mapped[str | None]` makes `verify_password(password, target_hash)` raise an arg-type error at `app/modules/auth/service.py:141` (`target_hash` is now `str | None`). This is explicitly scoped to **Plan 43-07** (Wave 3) per D-43-06 fifth bullet — the `_authenticate_password` SELECT will gain an explicit `WHERE password_hash IS NOT NULL` filter at that time. Not in scope for Plan 43-01's `files_modified`.

## Round-Trip Checkpoint Evidence (Task 3 — D-43-36 BLOCKING gate)

All 5 verification steps PASS:

1. **upgrade head:** Applied 0029 → 0030 clean (`Running upgrade 0029_email_send_log_hygiene -> 0030_users_lifecycle_columns`)
2. **downgrade -1:** Reverted 0030 → 0029 clean (no orphan constraints, no FK errors)
3. **upgrade head (re-apply):** Re-applied 0029 → 0030 clean
4. **Column + constraint inspection:**
   - Columns: `deactivated_at: YES, deactivated_by_user_id: YES, is_active: NO, password_hash: YES, status: NO` (matches expected)
   - CHECK constraints: `ck_users_lifecycle_consistency`, `ck_users_role`, `ck_users_status` (2 new + existing role check)
   - FK: `fk_users_deactivated_by_user_id_users FOREIGN KEY (deactivated_by_user_id) REFERENCES users(id) ON DELETE SET NULL`
5. **pg_dump verification:** Both `ck_users_lifecycle_consistency` and `ck_users_status` present in schema dump; self-FK `ON DELETE SET NULL` confirmed
6. **alembic current:** `0030_users_lifecycle_columns (head)` — no drift

Auto-mode: round-trip PASSED clean → checkpoint auto-approved per --auto directive (objective verification is the gate, no operator intervention required).

## User Setup Required

None — no external service configuration required. Migration applies automatically via `alembic upgrade head` (already executed on dev Postgres during checkpoint verification).

## Next Phase Readiness

- **Wave 2 unblocked:** Plans 43-04 (repository), 43-05 (service), 43-06 (router) can now consume the 4 new columns from both the DB and the ORM layer.
- **Plan 43-07 (Wave 3) follow-up flagged:** `auth.service._authenticate_password` SELECT must gain `WHERE password_hash IS NOT NULL` to keep the password verify path race-tight per Pitfall 5 / Phase 12.1 lesson. Plan 43-07 already lists `auth/service.py` in `files_modified`.
- **D-43-32 reconfirmed:** No new ORM tables added → zero amendments to `tests/unit/test_workers_eager_import.py`. `User` was already eagerly imported via the Phase 41 0022 registration.

## Self-Check: PASSED

- File `apps/backend/alembic/versions/0030_users_lifecycle_columns.py`: FOUND
- File `apps/backend/app/core/models.py`: FOUND (modified)
- Commit `9a789fc`: FOUND
- Commit `e4014a2`: FOUND
- Alembic head: `0030_users_lifecycle_columns (head)` (confirmed live)
- 4 expected new columns in users: present (verified via information_schema)
- 2 expected CHECK constraints in users: present (verified via pg_constraint)
- Self-FK with ON DELETE SET NULL: present (verified via pg_get_constraintdef)
- password_hash nullable: YES (verified via information_schema is_nullable column)

---
*Phase: 43-multi-user-admin-module*
*Completed: 2026-05-19*
