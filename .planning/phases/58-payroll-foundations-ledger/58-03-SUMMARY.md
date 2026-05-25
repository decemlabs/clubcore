---
phase: 58-payroll-foundations-ledger
plan: 03
subsystem: db-migrations
tags: [alembic, payroll, schema, migration, append-only, partial-unique]

# Dependency graph
requires:
  - phase: 58-payroll-foundations-ledger
    plan: 02
    provides: "app.modules.payroll module scaffold + constants.py"
provides:
  - "Alembic migration 0041_payroll_foundations: trainer_comp_configs + trainer_payroll_accruals tables"
  - "trainer_comp_configs: INSERT-only versioned comp config (PAY-01 schema bedrock)"
  - "trainer_payroll_accruals: append-only signed-amount accrual ledger (PAY-03/04/06 schema bedrock)"
  - "Partial UNIQUE uq_trainer_payroll_accruals_period_alive for DB-wins-the-race idempotency (D-58-06)"
affects:
  - 58-04-PLAN (ORM models — will map trainer_comp_configs + trainer_payroll_accruals)
  - 58-05-PLAN (service/router — will INSERT into these tables)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Alembic DDL migration with two tables atomically (mirrors 0034_online_payments pattern)"
    - "Partial UNIQUE INDEX with postgresql_where (mirrors uq_payments_refund_of_alive)"
    - "CHECK constraint for FK pair integrity (clawback_fks_paired — T-58-10)"
    - "Self-referential FK for clawback rows (mirrors Payment.refund_of)"
    - "INSERT-only versioned table (no UNIQUE(trainer_id) — D-58-02)"
    - "append-only signed-amount ledger with single-transition status column (D-58-03)"

key-files:
  created:
    - apps/backend/alembic/versions/0041_payroll_foundations.py
  modified: []

key-decisions:
  - "D-58-02 confirmed: trainer_comp_configs has NO UNIQUE(trainer_id) — INSERT-only versioned; resolver picks ORDER BY effective_from DESC LIMIT 1 WHERE effective_from <= :as_of_date"
  - "D-58-03 confirmed: trainer_payroll_accruals is append-only with signed accrual_kopecks (no >= 0 CHECK — clawback rows are intentionally negative)"
  - "D-58-06 confirmed: partial UNIQUE uq_trainer_payroll_accruals_period_alive WHERE clawback_of_accrual_id IS NULL excludes clawback rows from period-collision check"
  - "T-58-10 confirmed: ck_trainer_payroll_accruals_clawback_fks_paired CHECK enforces both-NULL or both-NOT-NULL for clawback FK pair"
  - "T-58-12 confirmed: ck_trainer_comp_configs_commission_pct_bps_range enforces 0..10000 bps cap"
  - "T-58-11 confirmed: downgrade() drops accruals FIRST (FK-safe order), then configs"
  - "audit_log_id FK uses ON DELETE SET NULL (preserves accrual if audit log row is pruned)"
  - "down_revision correctly set to 0040_audit_log_report_indexes (verified via alembic current)"

# Metrics
duration: 3min
completed: 2026-05-25
---

# Phase 58 Plan 03: Alembic Migration 0041 Payroll Foundations Summary

**Alembic migration 0041_payroll_foundations: two append-only payroll tables with partial UNIQUE, self-FK for clawback rows, and all D-58-02..05 CHECK constraints — upgrade + downgrade round-trip verified clean against live Postgres**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-25T09:38:40Z
- **Completed:** 2026-05-25T09:41:40Z
- **Tasks:** 1
- **Files created:** 1

## Accomplishments

- Created `apps/backend/alembic/versions/0041_payroll_foundations.py` with:
  - `trainer_comp_configs` table: id (PK/UUID/gen_random_uuid()), trainer_id (FK→trainers RESTRICT), commission_pct_bps (Integer NULL), session_fee_kopecks (Integer NULL), effective_from (Date NOT NULL), created_at (TIMESTAMPTZ NOT NULL/now()), created_by_user_id (FK→users RESTRICT NULL)
  - `trainer_payroll_accruals` table: id, trainer_id (FK→trainers RESTRICT), period_start, period_end (Date NOT NULL), sessions_count, revenue_kopecks (Integer NOT NULL), commission_pct_bps_snapshot, session_fee_kopecks_snapshot (Integer NULL), comp_config_id_snapshot (FK→trainer_comp_configs RESTRICT NOT NULL), accrual_kopecks (Integer NOT NULL signed), status (Text/'pending' default), accrued_at (TIMESTAMPTZ/now()), paid_at (TIMESTAMPTZ NULL), paid_by_user_id (FK→users RESTRICT NULL), clawback_of_accrual_id (self-FK→trainer_payroll_accruals RESTRICT NULL), source_refund_payment_id (FK→payments RESTRICT NULL), audit_log_id (FK→audit_log SET NULL NULL)
- All CHECK constraints verified in live DB via psql \d output:
  - `ck_trainer_comp_configs_commission_pct_bps_range` (0..10000 or NULL)
  - `ck_trainer_comp_configs_session_fee_kopecks_nonneg` (>= 0 or NULL)
  - `ck_trainer_payroll_accruals_status` (IN ('pending','paid'))
  - `ck_trainer_payroll_accruals_clawback_fks_paired` (both NULL or both NOT NULL)
- All indexes verified:
  - `ix_trainer_comp_configs_trainer_effective` (trainer_id, effective_from DESC)
  - `uq_trainer_payroll_accruals_period_alive` (trainer_id, period_start, period_end) UNIQUE WHERE clawback_of_accrual_id IS NULL
  - `ix_trainer_payroll_accruals_trainer_accrued` (trainer_id, accrued_at DESC)
  - `ix_trainer_payroll_accruals_status_period` (status, period_start DESC)
- `alembic upgrade head` and `alembic downgrade -1 && alembic upgrade head` both run clean
- `ruff check` + `mypy` both pass on the migration file

## Revision Identity

| Field | Value |
|-------|-------|
| revision | `0041_payroll_foundations` |
| down_revision | `0040_audit_log_report_indexes` |
| branch_labels | None |
| depends_on | None |

## Task Commits

1. **Task 1: Create Alembic migration 0041_payroll_foundations** - `bbf89d6` (feat)

## Schema Contract Verification

### trainer_comp_configs

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| id | uuid | NOT NULL | gen_random_uuid() |
| trainer_id | uuid | NOT NULL | — |
| commission_pct_bps | integer | NULL | — |
| session_fee_kopecks | integer | NULL | — |
| effective_from | date | NOT NULL | — |
| created_at | timestamptz | NOT NULL | now() |
| created_by_user_id | uuid | NULL | — |

### trainer_payroll_accruals

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| id | uuid | NOT NULL | gen_random_uuid() |
| trainer_id | uuid | NOT NULL | — |
| period_start | date | NOT NULL | — |
| period_end | date | NOT NULL | — |
| sessions_count | integer | NOT NULL | — |
| revenue_kopecks | integer | NOT NULL | — |
| commission_pct_bps_snapshot | integer | NULL | — |
| session_fee_kopecks_snapshot | integer | NULL | — |
| comp_config_id_snapshot | uuid | NOT NULL | — |
| accrual_kopecks | integer | NOT NULL | — |
| status | text | NOT NULL | 'pending' |
| accrued_at | timestamptz | NOT NULL | now() |
| paid_at | timestamptz | NULL | — |
| paid_by_user_id | uuid | NULL | — |
| clawback_of_accrual_id | uuid | NULL | — |
| source_refund_payment_id | uuid | NULL | — |
| audit_log_id | uuid | NULL | — |

## Files Created/Modified

- `apps/backend/alembic/versions/0041_payroll_foundations.py` — new migration (260 lines)

## Decisions Made

- `down_revision = "0040_audit_log_report_indexes"` — verified against live Postgres (`alembic current` confirmed head at 0040)
- Partial UNIQUE uses `postgresql_where=text("clawback_of_accrual_id IS NULL")` (matches 0034/0037 pattern)
- Index column expressions with DESC use `text("column DESC")` syntax (mirrors 0040 pattern)
- comment in migration documents that ON CONFLICT targets the partial UNIQUE (not an actual INSERT — DDL-only migration)

## Deviations from Plan

None - plan executed exactly as written.

## Next Phase Readiness

- Migration 0041 is at head; `alembic upgrade head` on any fresh DB will create both tables
- ORM models (Plan 58-04) can now define `TrainerCompConfig` and `TrainerPayrollAccrual` mapped against these tables
- Service layer (Plan 58-05) can use `ON CONFLICT (trainer_id, period_start, period_end) WHERE clawback_of_accrual_id IS NULL DO NOTHING` for idempotent accrual creation

## Self-Check: PASSED

- `apps/backend/alembic/versions/0041_payroll_foundations.py` exists: FOUND
- Commit `bbf89d6` exists: FOUND
- Both tables present in live Postgres: VERIFIED via psql \d output
- All 4 CHECK constraints present: VERIFIED
- All 4 indexes present (including partial UNIQUE): VERIFIED
- Round-trip downgrade + upgrade: PASSED

---
*Phase: 58-payroll-foundations-ledger*
*Completed: 2026-05-25*
