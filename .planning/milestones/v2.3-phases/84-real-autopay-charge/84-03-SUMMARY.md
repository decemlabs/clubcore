---
phase: 84-real-autopay-charge
plan: 03
subsystem: payments
tags: [yookassa, autopay, notifications, arq, sqlalchemy, pytest-asyncio, telegram, email]

# Dependency graph
requires:
  - phase: 84-02
    provides: charge_expiring_autopay cron enqueuing dispatch_autopay_failure_notification(autopay_charge_id=...) post-commit; webhook autopay discriminator enqueuing dispatch_payment_notification(kind='autopay_charge_succeeded', payment_id=online_payment_id)
provides:
  - autopay success + failure DM copy renderers (owner-signed) in autopay_charges/notifications.py
  - EMAIL_AUTOPAY_CHARGE_SUCCEEDED + EMAIL_AUTOPAY_CHARGE_FAILED owner-signed EmailTemplate records in online_payments/email_templates.py
  - autopay_charge_succeeded branch in dispatch_payment_notification (online_payment_id claim, end_date resolved)
  - dispatch_autopay_failure_notification ARQ task in autopay_charges/tasks.py (autopay_charge_id claim, Telegram + email, best-effort)
  - claim_autopay_failure_notification in autopay_charges/repository.py (UNIQUE(autopay_charge_id, kind, channel), fresh session, never re-raises)
  - migration 0057: payment_notifications.kind CHECK widened to include 'autopay_charge_succeeded'
  - 3 integration tests covering success + failure idempotency + best-effort channel isolation
affects:
  - 85 (OpenAPI handoff) — no new client HTTP paths; autopay notifications internal-only

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "claim_autopay_failure_notification: fresh-session INSERT, UNIQUE(autopay_charge_id, kind, channel) IntegrityError catch, never re-raise (D-52-02 mirror keyed on autopay_charge_id)"
    - "autopay_charge_succeeded dispatched via existing dispatch_payment_notification: online_payment_id claim key (D-52-10 pattern), client resolved directly from online_payments.client_id"
    - "999.2 email-mirror discipline: EMAIL_AUTOPAY_CHARGE_SUCCEEDED/FAILED templates mirror Telegram DM copy exactly"
    - "STRING LITERAL template_id at every get_email_dispatcher()(...) callsite (D-52-07 / AST gate)"
    - "Best-effort channel loop: per-channel try/except, never re-raise, one failure never blocks the other (D-52-02 / D-45-08)"
    - "metadata-table reads for cross-module recipient resolution (D-54-08 — no ORM import from memberships/clients)"

key-files:
  created:
    - apps/backend/app/modules/autopay_charges/notifications.py
    - apps/backend/app/modules/autopay_charges/repository.py
    - apps/backend/app/modules/autopay_charges/tasks.py
    - apps/backend/alembic/versions/0057_payment_notifications_widen_kind.py
    - apps/backend/tests/integration/autopay_charges/test_autopay_notifications.py
  modified:
    - apps/backend/app/modules/online_payments/tasks.py
    - apps/backend/app/modules/online_payments/email_templates.py
    - apps/backend/app/modules/online_payments/models.py
    - apps/backend/app/core/audit.py
    - apps/backend/app/workers/__init__.py
    - apps/backend/tests/unit/workers/test_worker_settings.py
    - apps/backend/.importlinter

key-decisions:
  - "D-84-09 payment_notifications.kind CHECK widened via migration 0057: the existing 4-kind CHECK on payment_notifications forbade 'autopay_charge_succeeded'; migration drops and recreates constraint with 5-kind predicate (Rule 2 auto-add). Used raw DDL per D-84-01 discipline (op.execute to avoid NAMING_CONVENTION double-prefix on locked table)"
  - "D-84-10 autopay success recipient resolution via online_payments.client_id: dispatch_payment_notification receives online_payment_id as payment_id for the autopay_charge_succeeded kind (same as payment_canceled pattern). Client resolved directly from online_payments.client_id column (no payment ledger row for canceled; autopay uses the same XOR pattern). Avoids _resolve_client_row which follows payments.subject_id → memberships/pt_packages"
  - "D-84-11 import-linter edge online_payments.tasks -> autopay_charges.notifications: the success DM renderer lives in autopay_charges/notifications.py (per plan artifact spec) and is imported by online_payments/tasks.py. One narrow ignore_imports edge added per D-20-MODULE precedent (minimum required, scoped to tasks.py only)"

patterns-established:
  - "Failure notification keyed on autopay_charge_id (always present) vs success keyed on online_payment_id (created by cron ok path) — two separate idempotency stores for the two outcome paths"
  - "Migration 0057 precedent: widen payment_notifications.kind CHECK for new notification kinds added post-Phase 52"

requirements-completed: [APAY-04]

# Metrics
duration: 45min
completed: 2026-06-05
---

# Phase 84 Plan 03: Autopay Notifications (Success + Failure) Summary

**Channel-idempotent autopay outcome notifications: success DM + email mirror via existing dispatch_payment_notification (online_payment_id-keyed); failure DM + email mirror via new dispatch_autopay_failure_notification (autopay_charge_id-keyed); both owner-signed, best-effort, 3 passing integration tests**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-06-05T21:30:00Z
- **Completed:** 2026-06-05T22:15:00Z
- **Tasks:** 2
- **Files modified:** 12

## Accomplishments

- Created `autopay_charges/notifications.py`: `render_autopay_charge_succeeded_dm` (copy: "Абонемент продлён автосписанием" + amount + end_date) and `render_autopay_charge_failed_dm` (copy: "Автосписание не прошло — обновите карту"). Owner-signed, str.format, D-52-08 anti-oracle discipline.
- Added `EMAIL_AUTOPAY_CHARGE_SUCCEEDED` + `EMAIL_AUTOPAY_CHARGE_FAILED` owner-signed `EmailTemplate` records to `online_payments/email_templates.py` TEMPLATES dict (999.2 mirror — identical copy as Telegram DMs).
- Extended `dispatch_payment_notification`: new `autopay_charge_succeeded` branch resolves client via `online_payments.client_id` (direct), resolves `end_date` from newest active membership, claims on `online_payment_id` (existing PaymentNotification dedup store), sends Telegram + email with STRING LITERAL template_id.
- Created `autopay_charges/repository.py`: `claim_autopay_failure_notification` — fresh-session INSERT of `AutopayChargeNotification(autopay_charge_id, 'autopay_charge_failed', channel)`, returns False on UNIQUE(autopay_charge_id, kind, channel) IntegrityError, never re-raises.
- Created `autopay_charges/tasks.py`: `dispatch_autopay_failure_notification(ctx, *, autopay_charge_id)` — resolves recipient via autopay_charges→memberships→clients metadata reads, loops ("telegram","email"), claim-before-send, best-effort (exception caught per-channel, never re-raises), returns 'sent'|'partial'|'skipped'.
- Registered `dispatch_autopay_failure_notification` in `WorkerSettings.functions` (list 13→14); added `AutopayChargeNotification` eager-import (REG-29-04).
- Added `EMAIL_AUTOPAY_CHARGE_SUCCEEDED` + `EMAIL_AUTOPAY_CHARGE_FAILED` to `LOCKED_EMAIL_TEMPLATES` in `app/core/audit.py`.
- Migration 0057: widens `payment_notifications.kind` CHECK from 4 to 5 kinds (adds `'autopay_charge_succeeded'`).
- 3 integration tests using real-commit engine + TRUNCATE teardown: success idempotency (online_payment_id claim), failure idempotency (autopay_charge_id claim, no online_payments row asserted), best-effort channel isolation (Telegram raises → email still sends, task does not re-raise).

## Task Commits

1. **Task 1: autopay notification copy + email templates + success-kind routing** - `cacf9077` (feat)
2. **Task 2: claim_autopay_failure_notification + failure task + widen kind CHECK + tests** - `d55c4144` (feat)

## Files Created/Modified

- `apps/backend/app/modules/autopay_charges/notifications.py` - DM copy renderers (success + failure, owner-signed)
- `apps/backend/app/modules/autopay_charges/repository.py` - claim_autopay_failure_notification (fresh session, UNIQUE catch, never re-raises)
- `apps/backend/app/modules/autopay_charges/tasks.py` - dispatch_autopay_failure_notification ARQ task
- `apps/backend/app/modules/online_payments/tasks.py` - autopay_charge_succeeded branch + _resolve_autopay_membership_end_date helper
- `apps/backend/app/modules/online_payments/email_templates.py` - EMAIL_AUTOPAY_CHARGE_SUCCEEDED + EMAIL_AUTOPAY_CHARGE_FAILED templates
- `apps/backend/app/modules/online_payments/models.py` - PaymentNotification kind CHECK widened to include 'autopay_charge_succeeded'
- `apps/backend/app/core/audit.py` - LOCKED_EMAIL_TEMPLATES extended with 2 autopay template IDs
- `apps/backend/app/workers/__init__.py` - dispatch_autopay_failure_notification registered + AutopayChargeNotification eager-import
- `apps/backend/alembic/versions/0057_payment_notifications_widen_kind.py` - migration widen payment_notifications.kind CHECK
- `apps/backend/tests/integration/autopay_charges/test_autopay_notifications.py` - 3 integration tests
- `apps/backend/tests/unit/workers/test_worker_settings.py` - functions count 13→14 + dispatch_autopay_failure_notification assert
- `apps/backend/.importlinter` - online_payments.tasks -> autopay_charges.notifications ignore edge

## Decisions Made

- **D-84-09 Migration 0057 — payment_notifications.kind CHECK widened:** The existing CHECK on `payment_notifications` only allowed 4 kinds (`payment_succeeded`, `refund_succeeded`, `payment_canceled`, `fiscal_failed`). The `autopay_charge_succeeded` kind in `claim_payment_notification` would trigger a DB `IntegrityError` caught as `False` (idempotent replay), blocking all channels on first dispatch. Migration 0057 adds the 5th kind using raw DDL (`op.execute`) per D-84-01 discipline. Categorized as Rule 2 (missing critical functionality for correctness).
- **D-84-10 Autopay success recipient via online_payments.client_id:** The `autopay_charge_succeeded` kind uses `online_payment_id` as the `payment_id` arg (same as `payment_canceled` pattern). Client resolved directly from `online_payments.client_id` rather than through `_resolve_client_row` (which follows `payments.subject_id → memberships → clients` — not applicable here since we key on online_payments, not payments ledger).
- **D-84-11 import-linter edge for autopay success renderer:** `online_payments/tasks.py` imports `autopay_charges.notifications` for the success DM renderer (per plan artifact spec). Added one narrow ignore_imports edge to `.importlinter` (minimum required per D-20-MODULE, scoped to tasks.py only).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] payment_notifications.kind CHECK blocked 'autopay_charge_succeeded' claim INSERT**
- **Found during:** Task 2 (first test run — `claim_payment_notification` returned False on both channels immediately)
- **Issue:** The `payment_notifications` table has a CHECK constraint limiting `kind` to 4 values. `'autopay_charge_succeeded'` was not in the predicate. The `claim_payment_notification` helper catches `IntegrityError` and returns `False` (idempotent replay signal) — causing every first-dispatch of the success notification to appear as a duplicate and skip.
- **Fix:** Created migration `0057_payment_notifications_widen_kind.py` to drop and recreate the CHECK constraint with 5 kinds. Also updated `PaymentNotification` ORM model `kind` CHECK to match. Used raw DDL (`op.execute`) per D-84-01 discipline for locked tables.
- **Files modified:** `alembic/versions/0057_payment_notifications_widen_kind.py`, `app/modules/online_payments/models.py`
- **Commit:** d55c4144 (Task 2)

---

**Total deviations:** 1 auto-fixed (Rule 2 — missing schema constraint widening required for correctness)
**Impact on plan:** Necessary for correct idempotency behaviour of the success notification path. No scope creep.

## Issues Encountered

None beyond the auto-fixed deviation above.

## Known Stubs

None. All notification paths are fully wired: Telegram DM + email dispatched with real template IDs resolving to real `EmailTemplate` records in the `TEMPLATES` dict. No placeholder text, no hardcoded empty values.

## Threat Surface Scan

No new security-relevant surface beyond the plan's threat model.

- T-84-13 (duplicate success DM on webhook replay): claim_payment_notification UNIQUE(online_payment_id, kind, channel) enforced; replay test asserts no second send — IMPLEMENTED and TESTED
- T-84-13b (duplicate failure DM on task replay): claim_autopay_failure_notification UNIQUE(autopay_charge_id, kind, channel) enforced; replay test asserts no second send — IMPLEMENTED and TESTED
- T-84-14 (one channel failure blocking the other): per-channel try/except, never re-raise; best-effort test asserts email still sends when Telegram raises — IMPLEMENTED and TESTED
- T-84-15 (PII in logs): recipient resolved via metadata-table read, never logged; card token never touched by notification path — PRESERVED
- T-84-16 (silent notification loss on decline): accepted — best-effort delivery per milestone policy; failure audited via autopay_charge_failed event (Plan 02)

## Self-Check: PASSED

Files exist:
- apps/backend/app/modules/autopay_charges/notifications.py: FOUND
- apps/backend/app/modules/autopay_charges/repository.py: FOUND
- apps/backend/app/modules/autopay_charges/tasks.py: FOUND
- apps/backend/alembic/versions/0057_payment_notifications_widen_kind.py: FOUND
- apps/backend/tests/integration/autopay_charges/test_autopay_notifications.py: FOUND

Commits exist:
- cacf9077: FOUND (Task 1 — notifications.py + email_templates + tasks.py success kind)
- d55c4144: FOUND (Task 2 — repository + tasks + worker + migration + tests)

Tests: 3 passed (test_autopay_notifications.py), 24 passed (all autopay integration), 8 passed (worker_settings)
mypy --strict: Success (all 6 files clean)
lint-imports: 3 contracts kept, 0 broken

---
*Phase: 84-real-autopay-charge*
*Completed: 2026-06-05*
