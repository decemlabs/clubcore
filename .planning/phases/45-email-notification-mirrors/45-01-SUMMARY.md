---
phase: 45-email-notification-mirrors
plan: 01
subsystem: backend / migrations + ORM
tags: [alembic, orm, notify-06, notify-11, notify-14, payment-receipts, channel-discriminator]
requires: [Alembic head 0030, dev Postgres up]
provides: [payment_receipts table, PaymentReceipt ORM, channel column ORM-wired, telegram_chat_id NULLABLE on membership_notifications]
affects: [memberships/models.py, bookings/models.py, payments/models.py, alembic head]
tech_stack_added: []
patterns: [op.f() naming wrapping, Literal Mapped column, server_default mirrors DB default, single-temporal-column discipline]
key_files_created:
  - apps/backend/alembic/versions/0031_payment_receipts.py
key_files_modified:
  - apps/backend/app/modules/payments/models.py
  - apps/backend/app/modules/memberships/models.py
  - apps/backend/app/modules/bookings/models.py
decisions: [D-45-01, D-45-11, D-45-13, D-45-25, PATTERNS.md correction #1]
requirements_completed: []
metrics:
  duration_minutes: ~25
  tasks_completed: 3
  completed_date: 2026-05-20
---

# Phase 45 Plan 01: payment_receipts table + ORM channel wiring Summary

Alembic 0031 introduces the payment_receipts idempotency ledger (UNIQUE payment_id, channel) and widens membership_notifications.telegram_chat_id to NULLABLE; ORM-side wiring adds Mapped[Literal['telegram','email']] channel columns on MembershipNotification + BookingNotification and a new PaymentReceipt model.

## Files Touched

| File | Change | Commit |
|------|--------|--------|
| apps/backend/alembic/versions/0031_payment_receipts.py | NEW migration | b640225 |
| apps/backend/app/modules/payments/models.py | + class PaymentReceipt | 162767c |
| apps/backend/app/modules/memberships/models.py | + channel column, telegram_chat_id → Mapped[int \| None], UNIQUE renamed | 1079a74 |
| apps/backend/app/modules/bookings/models.py | + channel column, UNIQUE renamed | 1079a74 |

## Migration

- Revision id: `0031_payment_receipts` (per PATTERNS.md correction #1 — 0029 slot is occupied by `email_send_log_hygiene`).
- down_revision: `0030_users_lifecycle_columns`.
- All constraint names wrapped in `op.f()` (5 occurrences); upgrade/downgrade round-trip clean.

## Deviations from Plan

**[Rule 1 — Bug / plan correction] `booking_notifications.telegram_chat_id` does not exist**
- Plan Task 1 step 3(c) directs `op.alter_column("booking_notifications", "telegram_chat_id", …, nullable=True)` and Task 3 instructs widening that column to `Mapped[int | None]`. Verified via grep of all migration files: only `0010_notifications.py` declares the column (on membership_notifications). `0020_booking_notifications.py` explicitly omits it per Phase 39 D-39-03 ("NO telegram_chat_id snapshot column"). Running the planned ALTER would fail at runtime.
- Resolution: skip both alter_column on booking_notifications AND the `Mapped[int | None]` retype in `BookingNotification`; document the omission in the migration docstring + ORM comment. Membership-side widening still applied per D-45-01.

## Verification Outcomes

- `uv run ruff check` on all 4 touched files — **clean**.
- `uv run mypy --strict` on the 3 ORM files — **Success: no issues found in 3 source files**.
- `uv run alembic upgrade head` then `alembic downgrade -1` then `alembic upgrade head` — **clean round-trip**; head = `0031_payment_receipts`.
- `uv run alembic check` after Task 3 — **No new upgrade operations detected**.
- `uv run pytest tests/integration/test_alembic_clean.py` — **2 passed**.
- Postgres inspection: `payment_receipts` table exists with `pk_payment_receipts`, `uq_payment_receipts_payment_channel`, `ck_payment_receipts_channel`, `fk_payment_receipts_payment_id_payments` (RESTRICT), `ix_payment_receipts_audit_corr`; `membership_notifications.telegram_chat_id.is_nullable = YES`.

## Self-Check: PASSED

- Files exist (4/4 verified above).
- Commits in git log: b640225 (Task 1), 162767c (Task 2), 1079a74 (Task 3).
- All success criteria from PLAN.md `<success_criteria>` met.
