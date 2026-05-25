---
phase: 58-payroll-foundations-ledger
plan: 04
subsystem: payroll-orm
tags: [sqlalchemy, pydantic, payroll, orm, schemas, append-only, partial-unique]

# Dependency graph
requires:
  - phase: 58-payroll-foundations-ledger
    plan: 02
    provides: "app.modules.payroll module scaffold + constants.py"
  - phase: 58-payroll-foundations-ledger
    plan: 03
    provides: "Alembic migration 0041_payroll_foundations"
provides:
  - "TrainerCompConfig ORM model (INSERT-only versioned, D-58-02)"
  - "TrainerPayrollAccrual ORM model (append-only signed-amount ledger, D-58-03)"
  - "Pydantic schemas: TrainerCompConfigRequest, TrainerCompConfigResponse,
    PayrollPreviewResponse, PayrollAccrualCreate, PayrollAccrualResponse"
  - "alembic/env.py updated to register payroll models — alembic check green"
affects:
  - 58-05-PLAN (service + router — will import from payroll/models.py + payroll/schemas.py)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ORM models mirroring migration column-for-column (alembic check green)"
    - "NO TimestampMixin on append-only ledger (mirrors Payment discipline)"
    - "Self-FK clawback pattern (mirrors Payment.refund_of)"
    - "Partial UNIQUE with postgresql_where=text() in ORM __table_args__"
    - "Pydantic model_validator(mode='after') for cross-field date ordering"
    - "Defense-in-depth: Pydantic bounds (ge/le) mirror DB CHECK constraints"

key-files:
  created:
    - apps/backend/app/modules/payroll/models.py
    - apps/backend/app/modules/payroll/schemas.py
  modified:
    - apps/backend/alembic/env.py

key-decisions:
  - "D-58-02 confirmed in ORM: TrainerCompConfig has NO UNIQUE(trainer_id) — INSERT-only versioned table"
  - "D-58-03 confirmed in ORM: TrainerPayrollAccrual has NO TimestampMixin — accrued_at is the single creation temporal column"
  - "Alembic env.py import added to register payroll models for autogenerate comparison (Rule 3 auto-fix)"
  - "Partial UNIQUE + DESC indexes declared in ORM __table_args__ with postgresql_where/text() — alembic check stays green without exclusion list additions"
  - "TrainerCompConfigRequest uses BackendSchemaBase (extra='forbid') — rejects unknown fields"
  - "PayrollAccrualCreate uses model_validator(mode='after') for period_start <= period_end check"

# Metrics
duration: 20min
completed: 2026-05-25
---

# Phase 58 Plan 04: ORM Models + Pydantic Schemas Summary

**SQLAlchemy 2.0 async ORM TrainerCompConfig + TrainerPayrollAccrual mirroring migration 0041 column-for-column (alembic check green); Pydantic v2 schemas for all 5 payroll endpoint shapes with wire-boundary bps/kopecks bounds enforcement**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-05-25T09:40:00Z
- **Completed:** 2026-05-25T09:49:08Z
- **Tasks:** 2
- **Files created:** 2 (models.py, schemas.py)
- **Files modified:** 1 (alembic/env.py)

## Accomplishments

### Task 1: ORM Models (models.py)

Created `apps/backend/app/modules/payroll/models.py` with:

**TrainerCompConfig** (D-58-02 INSERT-only versioned, 7 columns):
- `id` (UUID PK / gen_random_uuid())
- `trainer_id` (FK→trainers RESTRICT NOT NULL)
- `commission_pct_bps` (Integer NULL)
- `session_fee_kopecks` (Integer NULL)
- `effective_from` (Date NOT NULL)
- `created_at` (TIMESTAMPTZ NOT NULL / now())
- `created_by_user_id` (FK→users RESTRICT NULL)
- CHECK `ck_trainer_comp_configs_commission_pct_bps_range` (0..10000 or NULL)
- CHECK `ck_trainer_comp_configs_session_fee_kopecks_nonneg` (>= 0 or NULL)
- Index `ix_trainer_comp_configs_trainer_effective` (trainer_id, effective_from DESC)

**TrainerPayrollAccrual** (D-58-03 append-only, 17 columns):
- `id` (UUID PK / gen_random_uuid())
- `trainer_id` (FK→trainers RESTRICT NOT NULL)
- `period_start`, `period_end` (Date NOT NULL)
- `sessions_count`, `revenue_kopecks` (Integer NOT NULL)
- `commission_pct_bps_snapshot`, `session_fee_kopecks_snapshot` (Integer NULL)
- `comp_config_id_snapshot` (FK→trainer_comp_configs RESTRICT NOT NULL)
- `accrual_kopecks` (Integer NOT NULL, signed — no >= 0 CHECK per D-58-03)
- `status` (Text NOT NULL / 'pending' default)
- `accrued_at` (TIMESTAMPTZ NOT NULL / now())
- `paid_at` (TIMESTAMPTZ NULL)
- `paid_by_user_id` (FK→users RESTRICT NULL)
- `clawback_of_accrual_id` (self-FK→trainer_payroll_accruals RESTRICT NULL)
- `source_refund_payment_id` (FK→payments RESTRICT NULL)
- `audit_log_id` (FK→audit_log SET NULL NULL)
- CHECK `ck_trainer_payroll_accruals_status` (IN ('pending','paid'))
- CHECK `ck_trainer_payroll_accruals_clawback_fks_paired` (both NULL or both NOT NULL)
- Partial UNIQUE `uq_trainer_payroll_accruals_period_alive` (trainer_id, period_start, period_end WHERE clawback_of_accrual_id IS NULL)
- Index `ix_trainer_payroll_accruals_trainer_accrued` (trainer_id, accrued_at DESC)
- Index `ix_trainer_payroll_accruals_status_period` (status, period_start DESC)

Also updated `alembic/env.py` to import `app.modules.payroll.models` so alembic autogenerate can compare ORM vs DB.

### Task 2: Pydantic Schemas (schemas.py)

Created `apps/backend/app/modules/payroll/schemas.py` with 5 schema classes:

| Class | Role | Key Constraints |
|-------|------|-----------------|
| `TrainerCompConfigRequest` | PUT body | commission_pct_bps ge=0/le=10000; session_fee_kopecks ge=0 |
| `TrainerCompConfigResponse` | GET/PUT response | 6 fields; id, trainer_id, amounts, dates |
| `PayrollPreviewResponse` | Preview response | 4 int fields all ge=0; session_count, fixed, commission, total kopecks |
| `PayrollAccrualCreate` | POST body | period_start <= period_end model_validator(mode='after') |
| `PayrollAccrualResponse` | Accrual response | 16 fields; signed accrual_kopecks; clawback FK fields |

## Quality Gate Results

| Gate | Result |
|------|--------|
| `alembic check` | No new upgrade operations detected |
| `ruff check app/modules/payroll/` | All checks passed |
| `mypy app/modules/payroll/` | Success: no issues in 4 source files |
| `lint-imports --config .importlinter` | KEPT (3 contracts, 0 broken) |
| Import test | `from app.modules.payroll import models, schemas` exits 0 |
| Pydantic bps > 10000 | ValidationError raised |
| Pydantic kopecks < 0 | ValidationError raised |
| period_end < period_start | ValidationError raised |

## Task Commits

1. **Task 1: ORM Models** - `34dc887` (feat)
2. **Task 2: Pydantic Schemas** - `c83b056` (feat)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] alembic/env.py missing payroll models import**
- **Found during:** Task 1 verification (alembic check)
- **Issue:** `alembic check` reported "Detected removed table trainer_comp_configs / trainer_payroll_accruals" because the ORM models were not imported into `alembic/env.py` (the Alembic autogenerate registration file).
- **Fix:** Added `import app.modules.payroll.models  # Phase 58 PAY-01..06 / 0041` to `alembic/env.py` in alphabetical position between `online_refunds` and `payments`.
- **Files modified:** `apps/backend/alembic/env.py`
- **Commit:** `34dc887` (included with Task 1)

## Known Stubs

None — this plan creates foundation models and schemas; no UI rendering or data source wiring required at this layer.

## Threat Flags

No new security surface introduced beyond what the threat model documents. Models mirror the 0041 migration's trust boundary; schemas enforce T-58-13 / T-58-14 bounds at the wire.

## Self-Check: PASSED

- `apps/backend/app/modules/payroll/models.py`: FOUND
- `apps/backend/app/modules/payroll/schemas.py`: FOUND
- `apps/backend/alembic/env.py` (modified): FOUND
- Commit `34dc887` exists: FOUND
- Commit `c83b056` exists: FOUND
- `alembic check`: No new upgrade operations detected — VERIFIED
- `ruff check app/modules/payroll/`: All checks passed — VERIFIED
- `mypy app/modules/payroll/`: Success, no issues — VERIFIED
- `lint-imports`: All 3 contracts KEPT — VERIFIED
- Pydantic bounds enforced (bps, kopecks, period dates): VERIFIED

---
*Phase: 58-payroll-foundations-ledger*
*Completed: 2026-05-25*
