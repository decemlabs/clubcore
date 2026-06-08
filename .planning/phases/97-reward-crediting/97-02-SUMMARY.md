---
phase: 97-reward-crediting
plan: "02"
subsystem: loyalty / referrals
tags: [loyalty, referrals, migration, tdd, idempotency, partial-unique]
dependency_graph:
  requires: [97-01]
  provides: [accrue_referral_bonus, uq_loyalty_ledger_referral_accrual, referral_accrual entry_type]
  affects: [loyalty_ledger schema, alembic/env.py]
tech_stack:
  added: []
  patterns:
    - pg_insert on_conflict_do_nothing with compound partial UNIQUE (index_elements + index_where literal text())
    - RETURNING-gated audit emit (INFRA-15)
    - op.execute() raw DDL for CHECK constraint drop+recreate (naming_convention bypass)
key_files:
  created:
    - apps/backend/alembic/versions/0069_referral_crediting_columns.py
    - apps/backend/tests/unit/test_referral_bonus_accrual.py
  modified:
    - apps/backend/app/modules/loyalty/models.py
    - apps/backend/app/modules/loyalty/service.py
    - apps/backend/alembic/env.py
decisions:
  - "op.execute() raw DDL for CHECK drop+recreate bypasses naming_convention double-prefix (mirrors 0007_status_taxonomy pattern)"
  - "alembic/env.py: added messaging + referrals model imports (pre-existing gap, required for FK resolution)"
metrics:
  duration: "~35 minutes"
  completed: "2026-06-08T12:40:13Z"
  tasks_completed: 3
  files_changed: 5
---

# Phase 97 Plan 02: Referral Crediting Data Layer Summary

Idempotent referral_accrual ledger support: nullable FK + compound partial UNIQUE + accrue_referral_bonus primitive.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Widen loyalty_ledger ORM model | 9eda4a7b | models.py |
| 2 | Migration 0069 + alembic/env.py fix | 72fbf459 | 0069_referral_crediting_columns.py, env.py |
| 3 RED | TDD failing tests | 367fcfcd | tests/unit/test_referral_bonus_accrual.py |
| 3 GREEN | accrue_referral_bonus implementation | fe770c60 | service.py |

## What Was Built

**loyalty_ledger ORM model** (`apps/backend/app/modules/loyalty/models.py`):
- Added `referral_capture_id: Mapped[UUIDType | None]` nullable FK column → `referral_captures.id` with `ondelete="RESTRICT"` and FK name `fk_loyalty_ledger_referral_capture_id_referral_captures`
- Widened `entry_type` CHECK constraint string to include `'referral_accrual'` (4th literal); name `"entry_type"` (bare suffix) unchanged

**Migration 0069** (`apps/backend/alembic/versions/0069_referral_crediting_columns.py`):
- `op.add_column` + `op.create_foreign_key` for `referral_capture_id`
- `op.create_index("uq_loyalty_ledger_referral_accrual", ...)` on `(referral_capture_id, client_id)` WHERE `entry_type = 'referral_accrual'` — LITERAL name, compound idempotency guard
- CHECK widen via `op.execute()` raw DDL (bypasses naming_convention double-prefix; mirrors migration 0007 pattern)
- Full round-trip: upgrade head → downgrade -1 → upgrade head all succeed

**`accrue_referral_bonus` primitive** (`apps/backend/app/modules/loyalty/service.py`):
- Signature: `(session, *, client_id, amount_kopecks, referral_capture_id, online_payment_id, role: Literal["referrer", "referee"]) -> UUID | None`
- `pg_insert(LoyaltyLedger).on_conflict_do_nothing(index_elements=["referral_capture_id", "client_id"], index_where=text("entry_type = 'referral_accrual'"))` — literal text() predicate, mirrors `accrue_welcome_bonus`
- RETURNING-gated `audit.emit("referral_bonus_accrued", resource_type="referral", role=role, ...)`
- Returns `UUID` on real insert, `None` on conflict — no `session.flush()`/`session.commit()`
- category="referral" set on accrual rows

**TDD test suite** (`apps/backend/tests/unit/test_referral_bonus_accrual.py`):
- 13 tests: registry lock, payload validation, AUDIT_PAYLOAD_SCHEMAS, importability, signature, no-flush/commit, mocked behavior (insert → UUID+audit, conflict → None+no audit, role tagging)
- All 13 pass after GREEN implementation

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] alembic/env.py missing referrals and messaging model imports**
- **Found during:** Task 2 (alembic check raised `NoReferencedTableError: could not find table 'referral_captures'`)
- **Issue:** `app.modules.referrals.models` and `app.modules.messaging.models` were never added to `alembic/env.py` when Phase 96 added referral tables. The FK `loyalty_ledger.referral_capture_id → referral_captures.id` in the ORM model could not be resolved by SQLAlchemy autogenerate without the referral table registered in `Base.metadata`.
- **Fix:** Added both imports to `alembic/env.py` with comments indicating the phase/migration they correspond to
- **Files modified:** `apps/backend/alembic/env.py`
- **Commit:** 72fbf459

**2. [Rule 1 - Bug] CHECK constraint drop via op.drop_constraint causes double-prefix from naming_convention**
- **Found during:** Task 2 first migration run
- **Issue:** `op.drop_constraint("ck_loyalty_ledger_entry_type", "loyalty_ledger", type_="check")` was expanding the name through the `ck_%(table_name)s_%(constraint_name)s` convention, producing `ck_loyalty_ledger_ck_loyalty_ledger_entry_type` — not found in DB
- **Fix:** Replaced both `drop_constraint`/`create_check_constraint` calls with `op.execute()` raw DDL, following the existing project pattern in migration 0007_status_taxonomy.py
- **Files modified:** `apps/backend/alembic/versions/0069_referral_crediting_columns.py`
- **Commit:** 72fbf459

## Gates

- `cd apps/backend && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head` — clean round-trip
- `cd apps/backend && uv run mypy --strict app/modules/loyalty/` — 6 source files, 0 issues
- `cd apps/backend && uv run ruff check app/modules/loyalty/ alembic/versions/0069_referral_crediting_columns.py` — all checks passed
- `cd apps/backend && uv run lint-imports` — 3 contracts kept, 0 broken
- `cd apps/backend && uv run pytest tests/unit/test_referral_bonus_accrual.py` — 13 passed

## TDD Gate Compliance

- RED gate: `test(97-02)` commit `367fcfcd` — 7 tests failing (service import errors)
- GREEN gate: `feat(97-02)` commit `fe770c60` — all 13 tests passing
- No REFACTOR phase needed (code is clean as-written)

## Known Stubs

None — all components are fully implemented.

## Threat Flags

No new threat surface beyond what is modeled in the plan's STRIDE register.

## Self-Check: PASSED
