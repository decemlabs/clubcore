---
phase: 84-real-autopay-charge
plan: 01
subsystem: payments
tags: [yookassa, autopay, alembic, sqlalchemy, audit, migrations, postgres]

# Dependency graph
requires:
  - phase: 79-payment-methods-foundation
    provides: client_payment_methods table with yookassa_method_id card tokens
  - phase: 83-bonus-redemption-checkout
    provides: LOCKED_AUDIT_EVENTS at count 103; loyalty audit pair precedent
provides:
  - autopay_charges table with UNIQUE(membership_id, period_end) double-charge guard
  - autopay_charge_notifications table with UNIQUE(autopay_charge_id, kind, channel) claim store
  - migration 0056 (both tables + online_payments confirmation_type CHECK widened)
  - AutopayCharge + AutopayChargeNotification ORM models in app/modules/autopay_charges/
  - create_payment(payment_method_id=...) off-session support in YooKassaClient
  - autopay_charge_initiated + autopay_charge_failed LOCKED audit events at count 105
  - AutopayChargeInitiatedPayload + AutopayChargeFailedPayload in audit_payloads.py
affects:
  - 84-02 (cron uses autopay_charges table, create_payment off-session, audit events)
  - 84-03 (notifications use autopay_charge_notifications claim store)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Raw DDL via op.execute() for modifying CHECK constraints on locked tables (avoid naming convention double-prefix)"
    - "Plain UNIQUE index skip-list in alembic/env.py _include_object for op.f()-created indexes not in model __table_args__"
    - "Cross-module nullable UUID column without FK (online_payment_id on autopay_charges) per D-54-08"
    - "Separate dedicated claim table (autopay_charge_notifications) instead of extending Phase 52 payment_notifications (XOR constraint incompatibility)"

key-files:
  created:
    - apps/backend/app/modules/autopay_charges/__init__.py
    - apps/backend/app/modules/autopay_charges/models.py
    - apps/backend/alembic/versions/0056_autopay_charges.py
    - apps/backend/tests/integration/autopay_charges/__init__.py
    - apps/backend/tests/integration/autopay_charges/test_autopay_charges_migration.py
    - apps/backend/tests/integration/yookassa/__init__.py
    - apps/backend/tests/integration/yookassa/test_create_payment_off_session.py
    - apps/backend/tests/unit/autopay_charges/__init__.py
    - apps/backend/tests/unit/autopay_charges/test_autopay_audit_events.py
  modified:
    - apps/backend/alembic/env.py
    - apps/backend/.importlinter
    - apps/backend/app/modules/online_payments/models.py
    - apps/backend/app/integrations/yookassa/client.py
    - apps/backend/app/core/audit.py
    - apps/backend/app/core/audit_payloads.py
    - apps/backend/tests/unit/test_audit_taxonomy.py
    - apps/backend/tests/integration/test_phase51_audit_chain_invariants.py

key-decisions:
  - "Use raw op.execute() DDL for online_payments CHECK modification — op.drop_constraint passes name through naming convention template, double-prefixing already-expanded names like ck_online_payments_confirmation_type"
  - "Add plain index names to _include_object skip-list — indexes created via op.f() but absent from ORM __table_args__ appear as orphans in alembic check autogenerate diff"
  - "online_payment_id on autopay_charges has no FK (cross-module boundary, D-54-08) — Plan 02 writes it via raw SQL after the YooKassa call succeeds"
  - "Dedicated autopay_charge_notifications table instead of extending payment_notifications — the Phase 52 XOR CHECK + partial UNIQUE shape cannot accommodate a third subject FK without a major locked-table rewrite"

patterns-established:
  - "Raw DDL pattern: op.execute('ALTER TABLE ... DROP/ADD CONSTRAINT ...') for existing constraint modification when naming convention would double-prefix"
  - "Autogenerate skip pattern: add literal-named plain indexes (op.f() in migration, absent from __table_args__) to env.py _include_object exclusion list"

requirements-completed: [APAY-02, APAY-03, APAY-04]

# Metrics
duration: 35min
completed: 2026-06-05
---

# Phase 84 Plan 01: Real Autopay Charge Foundation Summary

**Migration 0056 creates autopay_charges (double-charge UNIQUE guard + online_payment_id) + autopay_charge_notifications (per-channel decline dedup); YooKassa off-session payment_method_id param added; two LOCKED audit events pre-registered at count-lock 105**

## Performance

- **Duration:** 35 min
- **Started:** 2026-06-05T19:10:00Z
- **Completed:** 2026-06-05T19:45:00Z
- **Tasks:** 3
- **Files modified:** 18

## Accomplishments

- Created `autopay_charges` module with ORM models and migration 0056 — includes the online_payment_id nullable column (Plan 02 UPDATE path) that PATTERNS.md omitted; UNIQUE(membership_id, period_end) is the DB-level double-charge guard (T-84-01)
- Created dedicated `autopay_charge_notifications` claim table with UNIQUE(autopay_charge_id, kind, channel) — decline-path failure notification idempotency cannot reuse Phase 52 payment_notifications (XOR constraint incompatibility with a third subject FK)
- Extended `YooKassaClient.create_payment` with `payment_method_id: str | None = None` — off-session body (no confirmation block, capture=True) when set; existing redirect/QR path byte-identical when absent (T-84-03)
- Widened `online_payments.ck_online_payments_confirmation_type` CHECK from IN ('redirect','qr') to IN ('redirect','qr','autopay') — required for Plan 02 off-session insert that writes confirmation_type='autopay' as the webhook discriminator
- Pre-registered autopay_charge_initiated + autopay_charge_failed LOCKED audit events + payload schemas; count-locks bumped 103 → 105 (INFRA-15 — callsites land in Plan 02)

## Task Commits

1. **Task 1: autopay_charges + autopay_charge_notifications models + migration 0056 + env.py allowlist + .importlinter** - `aecc0da5` (feat)
2. **Task 2: YooKassa off-session create_payment extension** - `c1d06a9f` (feat)
3. **Task 3: Pre-register autopay LOCKED audit events + bump count-locks 103 to 105** - `1bb65449` (feat)
4. **Ruff formatting fixes** - `909fdee0` (style)

## Files Created/Modified

- `apps/backend/app/modules/autopay_charges/__init__.py` - Module package
- `apps/backend/app/modules/autopay_charges/models.py` - AutopayCharge + AutopayChargeNotification ORM models
- `apps/backend/alembic/versions/0056_autopay_charges.py` - Migration: both tables + CHECK widening via raw DDL
- `apps/backend/alembic/env.py` - Added autopay_charges import; added 2 plain index names to _include_object skip-list
- `apps/backend/.importlinter` - Added app.modules.autopay_charges to modules-independent contract
- `apps/backend/app/modules/online_payments/models.py` - Updated confirmation_type CHECK to match 0056 DB state
- `apps/backend/app/integrations/yookassa/client.py` - Added payment_method_id param; off-session body branch
- `apps/backend/app/core/audit.py` - Appended autopay_charge_initiated + autopay_charge_failed to LOCKED_AUDIT_EVENTS
- `apps/backend/app/core/audit_payloads.py` - Added AutopayChargeInitiatedPayload + AutopayChargeFailedPayload + registry entries
- `apps/backend/tests/unit/test_audit_taxonomy.py` - Count-lock bumped 103 → 105
- `apps/backend/tests/integration/test_phase51_audit_chain_invariants.py` - Count-lock bumped 103 → 105
- `apps/backend/tests/integration/autopay_charges/test_autopay_charges_migration.py` - Migration shape + UNIQUE guard + CHECK tests
- `apps/backend/tests/integration/yookassa/test_create_payment_off_session.py` - Off-session body, idempotency key, redirect byte-identity, decline tests
- `apps/backend/tests/unit/autopay_charges/test_autopay_audit_events.py` - Event registration, payload schema, extra=forbid, required fields

## Decisions Made

- **Raw DDL for CHECK modification**: `op.drop_constraint` / `op.create_check_constraint` apply the NAMING_CONVENTION template to the name argument, double-prefixing an already-expanded name like `ck_online_payments_confirmation_type` into `ck_online_payments_ck_online_payments_confirmation_type`. Resolved by using `op.execute("ALTER TABLE ... DROP/ADD CONSTRAINT ...")` directly.
- **Autogenerate skip entries for plain indexes**: Indexes created via `op.f()` in the migration but not declared in model `__table_args__` appear as "removed" orphans in `alembic check`. Added `ix_autopay_charges_membership_id` and `ix_autopay_charge_notifications_autopay_charge_id` to `_include_object` exclusion list (same lineage as loyalty_ledger indexes).
- **Separate autopay_charge_notifications table**: The Phase 52 `payment_notifications` table uses an XOR CHECK + two partial-unique indexes keyed on exactly two nullable subject FKs. Adding a third subject would require rewriting the XOR predicate, adding a third partial UNIQUE, and changing the claim service API — too invasive for a locked multi-constraint table. A dedicated additive table is architecturally cleaner and matches Plan 84's isolation requirement.
- **online_payment_id without FK**: Nullable UUID column on autopay_charges references online_payments without a declarative FK (D-54-08 cross-module discipline). Plan 02 writes it via raw SQL after the YooKassa call succeeds.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Raw DDL for CHECK widening — naming convention double-prefix**
- **Found during:** Task 1 (migration execution)
- **Issue:** `op.drop_constraint("ck_online_payments_confirmation_type", ...)` caused `UndefinedObjectError: constraint "ck_online_payments_ck_online_payments_confirmation_type" does not exist` — the naming convention template prefixed the already-expanded name a second time
- **Fix:** Replaced with `op.execute("ALTER TABLE online_payments DROP CONSTRAINT ck_online_payments_confirmation_type")` + `op.execute("ALTER TABLE online_payments ADD CONSTRAINT ...")` — raw DDL bypasses the template
- **Files modified:** `alembic/versions/0056_autopay_charges.py`
- **Verification:** Migration applied cleanly; `alembic check` shows "No new upgrade operations detected"
- **Committed in:** aecc0da5 (Task 1 commit)

**2. [Rule 2 - Missing Critical] Add plain index names to alembic _include_object skip-list**
- **Found during:** Task 1 (alembic check after migration)
- **Issue:** `alembic check` flagged `ix_autopay_charges_membership_id` and `ix_autopay_charge_notifications_autopay_charge_id` as "Detected removed index" — they exist in the DB but not in ORM `__table_args__`, so autogenerate thinks they're orphans
- **Fix:** Added both literal index names to `_include_object` exclusion list in `alembic/env.py` (same pattern as loyalty_ledger indexes)
- **Files modified:** `alembic/env.py`
- **Verification:** `alembic check` returns "No new upgrade operations detected"
- **Committed in:** aecc0da5 (Task 1 commit)

**3. [Rule 1 - Bug] Test seed for membership_plans needed freeze_days_limit > 0**
- **Found during:** Task 1 (migration integration tests)
- **Issue:** `ck_membership_plans_freeze_days_limit_positive` CHECK rejected value 0 in seed; test used 0 as a placeholder
- **Fix:** Changed seed value from 0 to 30 in all `_seed_membership` calls
- **Files modified:** `tests/integration/autopay_charges/test_autopay_charges_migration.py`
- **Verification:** All 9 migration tests pass
- **Committed in:** aecc0da5 (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (1 blocking migration bug, 1 missing critical alembic config, 1 test seed bug)
**Impact on plan:** All auto-fixes necessary for correctness. No scope creep.

## Issues Encountered

None beyond the auto-fixed deviations above.

## Threat Surface Scan

No new security-relevant surface beyond what's in the plan's threat model.

- T-84-01: UNIQUE(membership_id, period_end) guard — in place and tested
- T-84-02: yookassa_payment_id stored (charge ID, not card token); no token stored on autopay_charges — confirmed by model column set
- T-84-03: off-session branch tested byte-identical to existing path with no save_payment_method key
- T-84-04: audit events pre-registered; count-lock 105 enforced by 2 test files

## Next Phase Readiness

- Plan 84-02 (cron + service layer) can now use:
  - `autopay_charges` table with all required columns including `online_payment_id`
  - `create_payment(payment_method_id=...)` for off-session charges
  - `autopay_charge_initiated` and `autopay_charge_failed` audit events (pre-registered)
- Plan 84-03 (notifications) can use `autopay_charge_notifications` claim table

---
*Phase: 84-real-autopay-charge*
*Completed: 2026-06-05*

## Self-Check: PASSED

Files created:
- FOUND: apps/backend/app/modules/autopay_charges/__init__.py
- FOUND: apps/backend/app/modules/autopay_charges/models.py
- FOUND: apps/backend/alembic/versions/0056_autopay_charges.py
- FOUND: apps/backend/tests/integration/autopay_charges/test_autopay_charges_migration.py
- FOUND: apps/backend/tests/integration/yookassa/test_create_payment_off_session.py
- FOUND: apps/backend/tests/unit/autopay_charges/test_autopay_audit_events.py

Commits:
- FOUND: aecc0da5 (Task 1)
- FOUND: c1d06a9f (Task 2)
- FOUND: 1bb65449 (Task 3)
- FOUND: 909fdee0 (style fixes)
