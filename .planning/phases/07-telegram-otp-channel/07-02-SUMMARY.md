---
phase: 07
plan: 02
subsystem: backend.modules.auth
tags: [migration, orm, telegram, schema]
requires:
  - apps/backend/app/modules/auth/models.py:User (Phase 5 D-02 — telegram_chat_id already present)
  - apps/backend/alembic/versions/0001_auth.py (current alembic HEAD)
  - apps/backend/app/core/database.py:NAMING_CONVENTION (Phase 4 D-19)
provides:
  - apps/backend/app/modules/auth/models.py:User.telegram_username (Mapped[str | None])
  - apps/backend/alembic/versions/0003_telegram_username.py (HEAD after migration)
  - users.telegram_username TEXT NULL UNIQUE column in DB
  - uq_users_telegram_username constraint
affects:
  - Phase 7 plan 07-04 (telegram_service.bind_and_issue selects User WHERE lower(telegram_username) = ?)
  - Phase 7 plan 07-07 (seed script writes telegram_username for owner)
tech-stack:
  added: []
  patterns:
    - "alembic migration following 0001_auth.py header style + op.f() naming-convention wrapping"
    - "ORM column mirroring telegram_chat_id shape (Mapped[T | None] + nullable=True + unique=True)"
key-files:
  created:
    - apps/backend/alembic/versions/0003_telegram_username.py
  modified:
    - apps/backend/app/modules/auth/models.py
decisions:
  - "down_revision = 0001_auth verified empirically (ls alembic/versions/ — only 0001_auth.py present); no Phase 5/6 0002_*.py exists"
  - "No data backfill in migration body (D-18); seed script (07-07) handles owner binding"
  - "Storage convention: lowercased on write at service layer (D-02); no native CHECK / CITEXT — keeps the column TEXT plain"
metrics:
  duration_minutes: 4
  completed_date: "2026-05-02"
  tasks_completed: 2
  files_changed: 2
  commits:
    - f942e67
    - 9cf1cfd
---

# Phase 07 Plan 02: User.telegram_username Column + Migration Summary

User ORM gains `telegram_username: Mapped[str | None]` (Text, nullable, unique) and migration `0003_telegram_username.py` adds the column with `op.f("uq_users_telegram_username")` UNIQUE constraint — sole schema change of Phase 7, gating the Phase 7 telegram bind/issue flow.

## What Shipped

### Task 1 — User.telegram_username column (commit f942e67)

Inserted the new column in `apps/backend/app/modules/auth/models.py` after `telegram_chat_id`, using the same shape (`Mapped[T | None]`, `nullable=True`, `unique=True`) and reusing the already-imported `Text` type. No CHECK constraint, no CITEXT — caller (Phase 7 telegram_service in plan 07-04) is responsible for `lower()`-on-write per D-02.

Verifications passed:
- `mypy --strict app/modules/auth/models.py` — Success
- `lint-imports` — 3 contracts KEPT, 0 broken
- grep regex assertions on `Mapped[str | None]` and `unique=True` — both matched

### Task 2 — Migration 0003_telegram_username.py (commit 9cf1cfd)

Created migration with:
- `revision = "0003_telegram_username"`, `down_revision = "0001_auth"` (verified via `ls alembic/versions/` — only `0001_auth.py` exists; no Phase 5/6 0002_*.py landed)
- `upgrade()`: `op.add_column` + `op.create_unique_constraint(op.f("uq_users_telegram_username"), ...)`
- `downgrade()`: `op.drop_constraint` + `op.drop_column` (rollback works)
- No data backfill (D-18 — seed script in plan 07-07 owns that)

Empirical verification on ephemeral Postgres 16 container (port 15432):
- `alembic upgrade head` ran clean: `Running upgrade 0001_auth -> 0003_telegram_username, telegram_username`
- `alembic check` reported `No new upgrade operations detected` — TEST-08 invariant GREEN
- Downgrade roundtrip: `alembic downgrade -1` → `current = 0001_auth` → `alembic upgrade head` → `current = 0003_telegram_username (head)`
- `psql \d users` confirmed: `telegram_username | text` column + `"uq_users_telegram_username" UNIQUE CONSTRAINT, btree (telegram_username)`
- `mypy --strict app` (full backend, 49 source files) — Success
- `ruff check` on changed files — All checks passed

## Decisions Made

| Decision | Why |
|----------|-----|
| `down_revision = "0001_auth"` (not adapted to a hypothetical 0002_*) | Verified empirically by `ls alembic/versions/`; only `0001_auth.py` exists. PATTERNS.md and CONTEXT D-22 of Phase 5 both confirmed naming was `0001_auth`. |
| Migration body has no data DDL beyond `op.add_column` + `op.create_unique_constraint` | D-18 explicitly forbids backfill — seed script (07-07) owns that path. Keeps migration single-purpose, deterministic, and auto-revertible. |
| Constraint declared via `op.create_unique_constraint` (not `unique=True` inline on `add_column`) | Matches the explicit `op.f(...)` wrapping pattern in `0001_auth.py`, which feeds the project-wide naming_convention template. Inline `unique=True` would emit an unnamed constraint. |

## Deviations from Plan

None — plan executed exactly as written. The plan's contingency for `down_revision` ("if a 0002_* exists, switch") did not apply because the filesystem confirmed `0001_auth.py` is the only existing migration.

## Threat Mitigations Honored

- **T-07-05 (Tampering — wrong down_revision)** mitigated: `ls alembic/versions/` ran before authoring; alembic upgrade head + downgrade roundtrip verified empirically.
- **T-07-06 (DoS — UNIQUE on nullable)** accepted as designed: Postgres treats NULL as distinct, so the UNIQUE on a nullable column is safe; partial index unnecessary.
- **T-07-07 (Info disclosure — plaintext)** accepted: Telegram username is a public handle.
- **T-07-08 (Repudiation)** out of scope for this plan — handled by emit calls in plan 07-04.

## Verification

- [x] `User.telegram_username: Mapped[str | None]` exists with Text + nullable + unique
- [x] Migration `0003_telegram_username.py` exists with correct revision shape
- [x] `alembic upgrade head` runs clean on a fresh PG16 DB
- [x] `alembic check` reports no diff after `upgrade head` (TEST-08 GREEN)
- [x] `alembic downgrade -1 && upgrade head` roundtrip works
- [x] Constraint name in DB matches `uq_users_telegram_username`
- [x] `mypy --strict app` passes (49 files)
- [x] `lint-imports` 3 contracts KEPT
- [x] `ruff check` clean

## Self-Check: PASSED

Files asserted to exist:
- FOUND: apps/backend/app/modules/auth/models.py (modified — telegram_username column present)
- FOUND: apps/backend/alembic/versions/0003_telegram_username.py (new file)

Commits asserted to exist on branch:
- FOUND: f942e67 (Task 1 — ORM column)
- FOUND: 9cf1cfd (Task 2 — migration)
