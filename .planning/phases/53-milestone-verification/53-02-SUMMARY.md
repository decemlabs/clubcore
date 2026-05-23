---
phase: 53-milestone-verification
plan: "02"
subsystem: backend-tests
tags: [race-tests, online-payments, dedup, db-unique, refund, decimal-precision, ver-02]
dependency_graph:
  requires: []
  provides: [VER-02]
  affects: [tests/integration/online_payments]
tech_stack:
  added: []
  patterns:
    - inline real-commit engine (standalone create_async_engine + TRUNCATE-CASCADE teardown)
    - respx mock for outbound YooKassa GET /payments/{id} re-fetch
    - asyncio.gather N-concurrent webhook POSTs / converter round-trips
key_files:
  created:
    - apps/backend/tests/integration/online_payments/test_payment_succeeded_double_delivery_race.py
    - apps/backend/tests/integration/online_payments/test_webhook_after_redis_restart_race.py
    - apps/backend/tests/integration/online_payments/test_concurrent_refund_arbitration_race.py
    - apps/backend/tests/integration/online_payments/test_kopecks_rubles_precision_race.py
  modified: []
decisions:
  - "D-53-02-01: Used inline real-commit engine (standalone create_async_engine) instead of db_session_real_commit fixture re-export — each file is self-contained and avoids conftest discovery ordering issues"
  - "D-53-02-02: VER-02(c) test uses N=5 concurrent cash refund POSTs (mirror of test_payments_refund_race.py) rather than mixing online webhook + cash endpoint — this is the direct proof of uq_payments_refund_of_alive without requiring a seeded OnlineRefund row and respx mock for get_refund re-fetch"
  - "D-53-02-03: VER-02(d) DB test seeds distinct (client_id, plan_id) pairs per edge value to avoid uq_online_payments_membership_double_tap UNIQUE violation — the precision test targets amount_kopecks storage, not the dedup constraint"
metrics:
  duration: "8m 26s"
  completed_date: "2026-05-23"
  tasks_completed: 2
  tasks_total: 2
  files_created: 4
  tests_added: 14
  deviations: 1
---

# Phase 53 Plan 02: VER-02 Race Tests Summary

Four real-Postgres race tests proving the v1.7 payment/refund flow is serialized by DB constraints (not TOCTOU app-layer guards) across four concurrency surfaces.

## Tasks

### Task 1: VER-02(a) double-delivery + VER-02(b) Redis-restart race tests

**Commit:** `1fa721d`

**VER-02(a) — double-delivery race** (`test_payment_succeeded_double_delivery_race.py`):
- N=5 concurrent identical `payment.succeeded` webhook POSTs with same `object.id`
- Redis `SET NX EX 86400` lets exactly ONE request acquire the dedup lock; other 4 short-circuit before DB write
- Asserts all 5 responses are 200 (ЮKassa contract) + exactly 1 `fiscal_receipts` row survives
- Proves Redis dedup AND DB UNIQUE `uq_fiscal_receipts_payment_id_kind` both hold

**VER-02(b) — Redis-restart gap** (`test_webhook_after_redis_restart_race.py`):
- 1st delivery: succeeds, writes DB rows, Redis dedup key set
- Explicit `redis.delete(dedup_key)` simulates restart gap (key evicted)
- 2nd delivery: handler re-enters UoW, SELECT-FOR-UPDATE finds `OnlinePayment.status='succeeded'`, FSM guard raises `InvalidTransitionError` → returns 200 with `idempotency_outcome='illegal_transition'` (D-50-17)
- Asserts exactly 1 `fiscal_receipts` row + 1 `online_payment_succeeded` audit row across both deliveries
- Proves DB UNIQUE is the SOLE catcher when Redis is absent

### Task 2: VER-02(c) refund arbitration + VER-02(d) kopecks precision

**Commit:** `9395b79`

**VER-02(c) — concurrent refund arbitration** (`test_concurrent_refund_arbitration_race.py`):
- Mirrors `test_payments_refund_race.py` exactly with `uq_payments_refund_of_alive` as arbiter
- N=5 concurrent `POST /api/v1/memberships/{id}/refund` (cash path) on the same membership
- Expects exactly 1×200 + 4×409 `already_refunded` 
- DB invariant: exactly 1 `payments` refund row + exactly 1 `membership_refunded` + 1 `refund_issued` audit row
- Proves `uq_payments_refund_of_alive` on `(refund_of) WHERE refund_of IS NOT NULL` is the load-bearing race arbiter

**VER-02(d) — Decimal precision** (`test_kopecks_rubles_precision_race.py`):
- Edge values: 0, 1, 99, 100, 9_999_999 kopecks
- N=20 concurrent `kopecks_to_yookassa → yookassa_to_kopecks` round-trips per edge value — zero drift
- Wire-format assertions: always 2 decimal places ("0.00", "0.01", "99999.99")
- DB layer: concurrent INSERTs of each edge value with distinct (client_id, plan_id) pairs → `amount_kopecks` reads back exactly as seeded (no SQLAlchemy Integer coercion)
- All arithmetic flows through `decimal.Decimal` with `ROUND_HALF_EVEN` — no float

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed `uq_online_payments_membership_double_tap` violation in VER-02(d)**
- **Found during:** Task 2 initial test run
- **Issue:** The DB precision test seeded multiple `OnlinePayment` rows with the SAME `client_id` + `membership_plan_id` + same calendar day — tripped `uq_online_payments_membership_double_tap` partial UNIQUE during concurrent INSERTs
- **Fix:** Changed `_seed_fixtures` to create N distinct `(client, plan)` pairs (one per edge value), so each concurrent INSERT targets a unique combination
- **Files modified:** `test_kopecks_rubles_precision_race.py`
- **Commit:** `9395b79` (included in task commit)

## Architecture Notes

All four tests use the inline real-commit engine pattern (D-03 compliance):
- `create_async_engine(str(settings.database_url), pool_pre_ping=True)` 
- `async_sessionmaker(engine, expire_on_commit=False)`
- `pytest.skip` guard on unreachable Postgres (probe at fixture entry)
- `TRUNCATE ... RESTART IDENTITY CASCADE` teardown covers the full FK chain

No new test dependencies introduced (`pytest-postgresql`, `testcontainers` — both forbidden by D-03).

## Test Results

```
14 tests, 14 passed, 0 failed, 0 skipped (Postgres running)
```

- `test_payment_succeeded_double_delivery_race.py` — 1 test PASSED
- `test_webhook_after_redis_restart_race.py` — 1 test PASSED
- `test_concurrent_refund_arbitration_race.py` — 1 test PASSED
- `test_kopecks_rubles_precision_race.py` — 11 tests PASSED (5 parametrized round-trip + 5 wire-format + 1 DB)

## Threat Flags

None — these are test files only, no new network endpoints, auth paths, or schema changes.

## Known Stubs

None.

## Self-Check: PASSED

Files exist:
- `apps/backend/tests/integration/online_payments/test_payment_succeeded_double_delivery_race.py` — FOUND
- `apps/backend/tests/integration/online_payments/test_webhook_after_redis_restart_race.py` — FOUND
- `apps/backend/tests/integration/online_payments/test_concurrent_refund_arbitration_race.py` — FOUND
- `apps/backend/tests/integration/online_payments/test_kopecks_rubles_precision_race.py` — FOUND

Commits exist:
- `1fa721d` — test(53-02): VER-02(a/b) double-delivery + Redis-restart race tests — FOUND
- `9395b79` — test(53-02): VER-02(c/d) refund arbitration + kopecks precision race tests — FOUND
