---
phase: 52-cross-channel-notifications-v1-6-carry-out
plan: "01"
subsystem: backend/notifications
tags: [alembic, orm, notifications, idempotency, telegram, polymorphic-subject]
dependency_graph:
  requires: [0038_fiscal_receipts_created_at, payments.id, online_payments.id]
  provides:
    - payment_notifications table (Alembic 0039)
    - PaymentNotification ORM model
    - claim_payment_notification repository helper
    - 4 locked Russian Telegram DM templates
    - PaymentNotification ORM eager-import at worker boot
  affects:
    - apps/backend/app/modules/online_payments/models.py
    - apps/backend/app/modules/online_payments/repository.py
    - apps/backend/app/modules/online_payments/notifications.py
    - apps/backend/app/workers/__init__.py
tech_stack:
  added: []
  patterns:
    - polymorphic-subject XOR (payment_id XOR online_payment_id) — mirrors D-49-04 OnlinePayment precedent
    - partial UNIQUE indexes (two per table, one per subject FK) — cannot use single all-columns UNIQUE with nullable FK
    - claim-before-send idempotency — INSERT before send (at-most-once leaning per D-52-02)
    - locked Russian DM copy with OWNER-COPY-LOCK + str.format renderers (mirrors D-39-02 bookings/notifications.py)
key_files:
  created:
    - apps/backend/alembic/versions/0039_payment_notifications.py
    - apps/backend/app/modules/online_payments/notifications.py
  modified:
    - apps/backend/app/modules/online_payments/models.py
    - apps/backend/app/modules/online_payments/repository.py
    - apps/backend/app/workers/__init__.py
decisions:
  - "D-52-04: payment_notifications table uses polymorphic subject XOR — payment_id FK for payment_succeeded/refund_succeeded/fiscal_failed, online_payment_id FK for payment_canceled (no ledger row for canceled payments)"
  - "D-52-05: claim_payment_notification opens a fresh session + txn via session_factory; asserts exactly-one-non-null at entry; returns False on IntegrityError (no re-raise)"
  - "D-52-06: 4 locked Russian DM templates with OWNER-COPY-LOCK; client-facing templates carry no failure-cause disclosure (anti-oracle C-12); owner-alert templates carry payment_id + failure details"
  - "Ruff fix: combined nested async with into single with statement with multiple contexts (SIM117); replaced % format with f-string (UP031)"
metrics:
  duration: "~25 minutes"
  completed: "2026-05-23"
  tasks_completed: 3
  files_created: 2
  files_modified: 3
---

# Phase 52 Plan 01: Payment Notifications Data Layer Summary

**One-liner:** `payment_notifications` idempotency table with polymorphic subject XOR (payment_id XOR online_payment_id), claim-before-send repository helper, and 4 locked Russian Telegram DM templates with client/owner-alert separation.

## Tasks Completed

| Task | Name | Commit | Key Output |
|------|------|--------|------------|
| 1 | Alembic 0039 + PaymentNotification model | bc116c9 | Migration + ORM model with XOR CHECK + two partial UNIQUE indexes |
| 2 | claim_payment_notification + eager-import | cb81e28 | Repo helper + PaymentNotification ORM registered at worker boot |
| 3 | Locked Russian DM templates | 79d83f5 | 4 Final[str] templates + str.format renderers; ruff fixes |

## Decisions Made

### D-52-04 (DB-UNIQUE polymorphic subject)
Applied Option A: DB-UNIQUE across all kinds via two partial UNIQUE indexes (one per subject FK). A single all-columns UNIQUE cannot span a nullable column in Postgres. This matches the XOR CHECK constraint shape on `OnlinePayment` (D-49-04).

- `uq_payment_notifications_payment_kind_channel` — `WHERE payment_id IS NOT NULL`
- `uq_payment_notifications_online_payment_kind_channel` — `WHERE online_payment_id IS NOT NULL`

### D-52-05 (claim-before-send, fresh session)
`claim_payment_notification` owns its own session + txn (fresh `session_factory()`) so the idempotency INSERT is independent of the caller's financial UoW. Claims before send (at-most-once leaning per D-52-02): a crash mid-send leaves the channel claimed rather than allowing a duplicate send on retry.

### D-52-06 (locked copy + owner sign-off)
**Owner sign-off date: 2026-05-23.** 4 locked Russian DM templates:
- `ONLINE_PAYMENT_SUCCEEDED_DM` — client (payment received + membership/PT-package activated)
- `ONLINE_PAYMENT_REFUNDED_DM` — client (refund processed)
- `ONLINE_PAYMENT_CANCELED_DM` — **OWNER-ALERT only** (NOT-05) — includes `payment_id` + `yookassa_payment_id`
- `FISCAL_RECEIPT_FAILED_DM` — **OWNER-ALERT only** (NOT-04) — includes `payment_id` + `failure_reason`

Anti-oracle C-12: client-facing templates carry no failure-cause disclosure.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ruff lint issues in initial implementation**
- **Found during:** Task 3 verification (`uv run ruff check`)
- **Issue:** 3 violations in notifications.py (`RUF001` + `RUF100` unused noqa directives); `UP031` (% format → f-string) + `E501` + `SIM117` in repository.py
- **Fix:** Removed unused `RUF001` noqa from client templates (those lines had no Cyrillic ambiguous chars); added `RUF001` only to `ONLINE_PAYMENT_REFUNDED_DM` which genuinely contains `у` (Cyrillic U); replaced `% format` with f-string in assert; combined nested `async with session_factory() as session, session.begin():` using SIM117 pattern
- **Files modified:** `notifications.py`, `repository.py`
- **Commit:** 79d83f5

## Known Stubs

None — plan 52-01 delivers the complete data layer foundation. No placeholder data or TODO stubs exist in the created/modified files.

## Self-Check

- [x] `apps/backend/alembic/versions/0039_payment_notifications.py` — created
- [x] `apps/backend/app/modules/online_payments/models.py` — PaymentNotification class added
- [x] `apps/backend/app/modules/online_payments/repository.py` — claim_payment_notification added
- [x] `apps/backend/app/modules/online_payments/notifications.py` — created
- [x] `apps/backend/app/workers/__init__.py` — PaymentNotification eager-import added
- [x] Commit bc116c9 — Task 1 (migration + model)
- [x] Commit cb81e28 — Task 2 (claim helper + eager-import)
- [x] Commit 79d83f5 — Task 3 (locked templates + ruff fixes)
- [x] `alembic upgrade head` → clean
- [x] Round-trip `upgrade → downgrade -1 → upgrade` → lossless
- [x] `alembic heads` → single head `0039_payment_notifications`
- [x] `uv run python -c "import app.workers"` → exits 0
- [x] `uv run mypy --strict` → clean on all 3 modified modules
- [x] `uv run ruff check` → All checks passed

## Self-Check: PASSED
