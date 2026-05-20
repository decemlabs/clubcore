---
phase: 45-email-notification-mirrors
plan: 11
subsystem: payments / payment_receipts UNIQUE
tags: [notify-11, race-test, real-postgres, d-45-28]
requires: [45-01, 45-09]
provides: [payment-receipts-unique-race-regression]
affects: [tests/integration/test_payment_receipt_race.py]
tech_stack:
  added: []
  patterns: [real-commit-race-test, truncate-cascade-teardown, asyncio-gather-independent-sessions]
key_files:
  created:
    - apps/backend/tests/integration/test_payment_receipt_race.py
  modified: []
decisions: [D-45-08, D-45-28]
requirements: [NOTIFY-11]
metrics:
  duration_minutes: ~8
  tasks_completed: 1
  completed_date: 2026-05-20
commits:
  - bead964 test(45-11): concurrent payment_receipts UNIQUE race regression (D-45-28)
---

# Phase 45 Plan 11: Payment-Receipts UNIQUE Race Regression Summary

Real-Postgres race regression test asserting `uq_payment_receipts_payment_channel`
serialises two concurrent `(payment_id, channel='email')` INSERTs to exactly one
surviving row — the loser's `IntegrityError` is the swallow path D-45-08 relies on.

## Files Touched

| File | Change | Commit |
|------|--------|--------|
| `apps/backend/tests/integration/test_payment_receipt_race.py` | NEW | bead964 |

## Verification

- `pytest tests/integration/test_payment_receipt_race.py -v` — 1 passed, 0.14s.
- Re-ran 10 / 10 times consecutively — all green, no flake.
- `ruff check` — clean.
- `mypy --strict` — clean.

## Test Shape

- Local real-commit engine + `async_sessionmaker` fixture (NOT the SAVEPOINT
  `db_session` from `tests/conftest.py:57`) — UNIQUE-index serialisation only
  manifests at COMMIT-time across separate sessions; SAVEPOINT nesting masks it.
- Seed: one `User` (OWNER, `password_hash=None` per D-43-06/08) + one sale `Payment`.
- Race: two independent sessions each `add` a `PaymentReceipt(payment_id=X, channel='email')`
  with distinct `audit_correlation_id`s, then `commit` concurrently via `asyncio.gather`
  (`return_exceptions=True`).
- Assertions: exactly 1 success + exactly 1 `IntegrityError` referencing
  `uq_payment_receipts_payment_channel`; `SELECT count(*) → 1`; surviving
  `audit_correlation_id` is one of the two we generated.
- Teardown: `TRUNCATE payment_receipts, payments, users RESTART IDENTITY CASCADE`
  (real-commit writes are NOT rolled back; CASCADE walks the FK chain).

## Deviations from Plan

None. The plan suggested Option A (direct ORM concurrent INSERT) or Option B
(invoke the orchestrator helper) — chose A as the closest mirror to
`test_payments_refund_race.py:42-72`. Plan's prose example referenced
`session_factory_real_commit` / `payment_seed_real_commit` fixtures; project
convention uses a single `db_session_real_commit` session per race test, so
the new test factories its own session_factory off the engine inline.

## Self-Check: PASSED

- File `apps/backend/tests/integration/test_payment_receipt_race.py`: FOUND.
- Commit `bead964` present in `git log --oneline`.
- `<success_criteria>` met: race test green; exactly 1 row survives 2 concurrent
  INSERTs; mirrors VIS-TEST-01 + real-Postgres discipline (D-45-28).
