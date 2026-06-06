---
phase: 84-real-autopay-charge
plan: 02
subsystem: payments
tags: [yookassa, autopay, arq, cron, sqlalchemy, respx, pytest-asyncio]

# Dependency graph
requires:
  - phase: 84-01
    provides: autopay_charges table (UNIQUE membership_id+period_end), online_payments confirmation_type='autopay' CHECK, create_payment(payment_method_id=...) off-session support, autopay_charge_initiated + autopay_charge_failed LOCKED audit events
provides:
  - _charge_expiring_autopay_memberships caller-owns-txn service helper in app/modules/autopay_charges/service.py
  - charge_expiring_autopay ARQ cron registered in WorkerSettings (hour=2, minute=0, unique=True)
  - AutopayCharge eager-import in WorkerSettings (REG-29-04)
  - is_autopay discriminator in handlers.py (confirmation_type='autopay' → method='autopay' + kind='autopay_charge_succeeded')
  - Full skip-matrix + idempotency + ФЗ-376 no-consent test suite (41 new tests)
affects:
  - 84-03 (notifications) — dispatch_autopay_failure_notification enqueued by cron with autopay_charge_id
  - 85 (OpenAPI handoff) — no new client HTTP paths; autopay internal-only

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Caller-owns-txn service helper with noqa: SVC001 + post-commit enqueue from cron fn (Phase 18 D-01 discipline)"
    - "Claim-before-charge: INSERT ON CONFLICT (membership_id, period_end) DO NOTHING RETURNING id — DB-level double-charge guard"
    - "Deterministic sha256 idempotency_key = hashlib.sha256(f'{membership_id}:{period_end}'.encode()).hexdigest() — provider-level crash guard"
    - "confirmation_type='autopay' as webhook discriminator — additive, no migration, reversible"
    - "Audit payload UUID fields cast to str at emit() callsite (JSONB-serialisability requirement)"
    - "Skip-matrix tests using respx mock with side_effect call-counter pattern"
    - "Idempotency tests: pre-inserted claim row simulates crash-between-claim-and-provider scenario"
    - "Webhook discriminator test in webhook_yookassa/ directory (real-commit session required — SAVEPOINT conflicts with session.begin())"

key-files:
  created:
    - apps/backend/app/modules/autopay_charges/service.py
    - apps/backend/app/workers/scheduled/charge_expiring_autopay.py
    - apps/backend/tests/integration/autopay_charges/test_charge_expiring_autopay.py
    - apps/backend/tests/integration/autopay_charges/test_autopay_skip_matrix.py
    - apps/backend/tests/integration/autopay_charges/test_autopay_idempotency.py
    - apps/backend/tests/integration/webhook_yookassa/test_wh08_autopay_discriminator.py
  modified:
    - apps/backend/app/workers/__init__.py
    - apps/backend/tests/unit/workers/test_worker_settings.py
    - apps/backend/app/api/v1/_internal/yookassa/handlers.py

key-decisions:
  - "D-84-05 Webhook discriminator test in webhook_yookassa/ directory: the plan specified test_charge_expiring_autopay.py but handle_payment_succeeded uses async with session.begin() which conflicts with SAVEPOINT-mode db_session; placed in webhook_yookassa/ where real-commit fixtures exist (Rule 3 auto-fix)"
  - "D-84-06 Audit payload UUIDs cast to str: AutopayChargeInitiatedPayload/AutopayChargeFailedPayload expect UUID type from Pydantic but JSONB serialisation requires str; cast at emit() callsite (same pattern as all other v1.4 emit callsites)"
  - "D-84-07 is_autopay_local capture before async with exits: row is detached after session.begin() exits; captured into local before commit boundary so _post_commit_enqueue receives the correct discriminator value"
  - "D-84-08 if/else literal assignment before _post_commit_enqueue: plan required literal strings at enqueue site; resolved via notification_kind local variable with if/else branches producing literal 'autopay_charge_succeeded' / 'payment_succeeded'"

patterns-established:
  - "Claim-before-charge pattern: INSERT ON CONFLICT DO NOTHING RETURNING id as the primary double-charge guard; unique=True on cron as second line of defence (per PITFALLS Pitfall 4)"
  - "Post-commit failure enqueue: ctx['redis'].enqueue_job AFTER session.commit() — never inside the transaction (mirrors webhook _post_commit_enqueue discipline)"
  - "Webhook additive discriminator: confirmation_type column as the method/kind selector — no new migration, no activation-logic change"

requirements-completed: [APAY-01, APAY-02, APAY-03]

# Metrics
duration: 90min
completed: 2026-06-05
---

# Phase 84 Plan 02: Real Autopay Charge Cron Summary

**Off-session autopay cron (charge_expiring_autopay) with DB-claim idempotency + sha256 provider key + webhook discriminator for method='autopay' charge-ledger labeling + 41 new passing tests covering skip matrix, ФЗ-376, double-charge, crash-between-claim, and decline-enqueue**

## Performance

- **Duration:** 90 min
- **Started:** 2026-06-05T19:50:00Z
- **Completed:** 2026-06-05T21:20:00Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments

- Created `_charge_expiring_autopay_memberships(session, today, window_days)` helper: raw SQL eligibility JOIN with ФЗ-376 consent gate, ON CONFLICT DO NOTHING claim INSERT, sha256 idempotency key, off-session YooKassa charge, online_payments row (ok-only), audit emit, declined id collection — all without session.commit() (caller-owns-txn)
- Created `charge_expiring_autopay` ARQ cron entry: commits after helper, enqueues dispatch_autopay_failure_notification post-commit for each declined claim (keyed on autopay_charges.id, NOT online_payment_id which doesn't exist on decline)
- Registered in WorkerSettings: AutopayCharge eager-import (REG-29-04) + functions list + cron(hour=2, minute=0, unique=True, keep_result=60)
- Added additive webhook discriminator: `is_autopay = row.confirmation_type == 'autopay'` → `method='autopay'` on Payment + `kind='autopay_charge_succeeded'` notification — D-06 activation path unchanged
- 41 new integration/unit tests: ok/decline paths, amount=plan-price, ФЗ-376 zero-charges, 6 skip conditions, duplicate-tick, crash-between-claim, failure-no-retry, decline-enqueue, webhook method='autopay' + non-autopay regression

## Task Commits

1. **Task 1: service helper** - `433d28f5` (feat)
2. **Task 2: cron + WorkerSettings + skip/idempotency tests** - `6bab9f82` (feat)
3. **Task 3: webhook discriminator** - `dc64700a` (feat)

## Files Created/Modified

- `apps/backend/app/modules/autopay_charges/service.py` - _charge_expiring_autopay_memberships caller-owns-txn helper
- `apps/backend/app/workers/scheduled/charge_expiring_autopay.py` - ARQ cron entry with post-commit failure enqueue
- `apps/backend/app/workers/__init__.py` - AutopayCharge eager-import + charge_expiring_autopay in functions + cron_jobs
- `apps/backend/app/api/v1/_internal/yookassa/handlers.py` - is_autopay discriminator; method + kind branch
- `apps/backend/tests/integration/autopay_charges/test_charge_expiring_autopay.py` - ok path, decline, amount, ФЗ-376
- `apps/backend/tests/integration/autopay_charges/test_autopay_skip_matrix.py` - 6 skip conditions
- `apps/backend/tests/integration/autopay_charges/test_autopay_idempotency.py` - duplicate tick, crash, failure-no-retry, decline-enqueue
- `apps/backend/tests/unit/workers/test_worker_settings.py` - assert charge_expiring_autopay registered + cron at hour=2
- `apps/backend/tests/integration/webhook_yookassa/test_wh08_autopay_discriminator.py` - method='autopay' + regression

## Decisions Made

- **D-84-05 Webhook test location:** plan specified test_charge_expiring_autopay.py but handle_payment_succeeded uses `async with session.begin()` — SAVEPOINT-mode db_session raises InvalidRequestError. Placed in webhook_yookassa/ where real-commit fixtures (webhook_db_session, webhook_client) are available. Documented as Rule 3 auto-fix.
- **D-84-06 UUID→str cast at audit emit:** JSONB column requires JSON-serializable values; Pydantic validates UUID from str so model_validate passes. Pattern matches all other v1.4 emit callsites (e.g., membership_expired, online_payment_succeeded).
- **D-84-07 is_autopay_local capture:** row is ORM-detached after `async with session.begin()` exits. `is_autopay_local: bool = is_autopay` captured inside the block, used outside for _post_commit_enqueue.
- **D-84-08 Literal kind via if/else:** `notification_kind` local variable with `if is_autopay_local: notification_kind = "autopay_charge_succeeded"; else: notification_kind = "payment_succeeded"` produces literal strings at the assignment site, satisfying the plan's literal-string requirement.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] UUID not JSON-serializable in audit emit payload**
- **Found during:** Task 1 (first test run)
- **Issue:** `audit.emit(..., membership_id=membership_id)` where membership_id is a Python UUID — JSONB column raises `TypeError: Object of type UUID is not JSON serializable`
- **Fix:** Cast to `str(membership_id)` at all emit() callsites (Pydantic validates UUID from str)
- **Files modified:** `app/modules/autopay_charges/service.py`
- **Verification:** Tests pass with audit rows visible after flush()
- **Committed in:** 433d28f5 (Task 1)

**2. [Rule 1 - Bug] Test SQL used `::uuid` cast incompatible with asyncpg parameter binding**
- **Found during:** Task 1 (test SQL syntax error)
- **Issue:** `WHERE resource_id = :claim_id::uuid` — asyncpg treats `:` inside `::uuid` as a second parameter marker, causing PostgresSyntaxError
- **Fix:** Changed to `CAST(:claim_id AS UUID)` in all test queries
- **Files modified:** `tests/integration/autopay_charges/test_charge_expiring_autopay.py`
- **Verification:** Tests pass without syntax errors
- **Committed in:** 433d28f5 (Task 1)

**3. [Rule 1 - Bug] SQLAlchemy cached query plan conflicted with different parameter names**
- **Found during:** Task 1 (InvalidRequestError for bind parameter 'cid')
- **Issue:** Multiple text() queries in the same session caused SA to confuse parameter names from its query cache; queries with `:client_id` got `A value is required for bind parameter 'cid'` errors
- **Fix:** Rewrote test queries to use unique, non-colliding parameter names (`:ap_mid`, `:op_id`, `:ar_id`, `:mc_id`, etc.)
- **Files modified:** `tests/integration/autopay_charges/test_charge_expiring_autopay.py`
- **Verification:** All 4 tests pass without parameter name errors
- **Committed in:** 433d28f5 (Task 1)

**4. [Rule 3 - Blocking] Webhook discriminator test moved to webhook_yookassa/**
- **Found during:** Task 3 (planning — SAVEPOINT/session.begin() conflict is a known constraint)
- **Issue:** `handle_payment_succeeded` uses `async with session.begin():` which is incompatible with SAVEPOINT-mode `db_session`; putting the test in `test_charge_expiring_autopay.py` would cause `InvalidRequestError: A transaction is already begun on this Session`
- **Fix:** Added `test_wh08_autopay_discriminator.py` in `tests/integration/webhook_yookassa/` where `webhook_db_session` + `webhook_client` fixtures with real-commit engine are already established (Phase 50 precedent)
- **Files modified:** `tests/integration/webhook_yookassa/test_wh08_autopay_discriminator.py` (created)
- **Verification:** 2 tests pass; 102 total webhook tests pass (no regression)
- **Committed in:** dc64700a (Task 3)

---

**Total deviations:** 4 auto-fixed (3 bugs, 1 blocking)
**Impact on plan:** All necessary for correctness and test isolation. No scope creep. Task 3 test file location changed from plan spec; functionality fully verified.

## Issues Encountered

None beyond the auto-fixed deviations above.

## Threat Surface Scan

No new security-relevant surface beyond what's in the plan's threat model.

- T-84-05: UNIQUE(membership_id, period_end) ON CONFLICT DO NOTHING — implemented and tested (duplicate-tick test)
- T-84-06: Crash-between-claim-and-provider — sha256 deterministic key tested; stable across runs
- T-84-07: ФЗ-376 consent gate — eligibility JOIN enforces consent_recorded_at IS NOT NULL; explicit test asserts zero charges
- T-84-08: Card eligibility — JOIN requires unlinked_at IS NULL + autopay_enabled; skip-matrix covers all cases
- T-84-09: Audit — autopay_charge_initiated and autopay_charge_failed both emitted and tested
- T-84-10: No synchronous activation — cron never creates memberships; webhook-locked activation unchanged
- T-84-11: yookassa_method_id PII — token used only as create_payment arg, never logged or stored on any claim/online_payments row
- T-84-12: Failure-no-retry — failed claim row blocks next tick via ON CONFLICT; tested explicitly
- T-84-12b: Decline notification keyed on autopay_charge_id — tested in decline-enqueue test

## Next Phase Readiness

- Plan 84-03 (notifications) can now use `dispatch_autopay_failure_notification(autopay_charge_id=...)` job name — already enqueued by cron with the correct key
- The charge-ledger method='autopay' is now correct for financial reporting
- All APAY-01/02/03 requirements are delivered

---
*Phase: 84-real-autopay-charge*
*Completed: 2026-06-05*
