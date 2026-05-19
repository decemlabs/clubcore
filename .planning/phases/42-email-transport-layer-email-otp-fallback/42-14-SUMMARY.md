---
phase: 42-email-transport-layer-email-otp-fallback
plan: 14
subsystem: email-circuit-breaker
tags: [circuit-breaker, redis, pipeline, concurrency, atomicity, gap-closure]
gap_closure: CR-03

dependency_graph:
  requires: []
  provides:
    - atomic-record-failure-pipeline
  affects:
    - apps/backend/app/integrations/email/circuit_breaker.py
    - apps/backend/tests/unit/integrations/email/test_circuit_breaker.py

tech_stack:
  added: []
  patterns:
    - redis.pipeline(transaction=True) MULTI/EXEC for atomic read-modify-write
    - asyncio.gather for unit-tier concurrency regression testing

key_files:
  modified:
    - apps/backend/app/integrations/email/circuit_breaker.py
    - apps/backend/tests/unit/integrations/email/test_circuit_breaker.py

decisions:
  - Conditional open-marker SET left outside MULTI per plan guidance — idempotent, own TTL contract, acceptable for this threat model
  - fakeredis pipeline serializes per-call so test exercises API surface correctness rather than true MULTI atomicity — acknowledged and acceptable at unit tier

metrics:
  duration: ~8 minutes
  completed: 2026-05-19T09:49:13Z
  tasks_completed: 2
  files_modified: 2
---

# Phase 42 Plan 14: Circuit Breaker Atomic Pipeline (CR-03 Gap Closure) Summary

Closed CR-03 (warning): wrapped `record_failure`'s five sequential Redis awaits in a single `redis.pipeline(transaction=True)` MULTI/EXEC block, eliminating the lost-trim race where concurrent workers could read a ZCARD count one shy of threshold and fail to open the circuit. Added two concurrency regression tests using `asyncio.gather`.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Pipeline ZADD+ZREMRANGEBYSCORE+EXPIRE+ZCARD inside record_failure | e4628f4 | `app/integrations/email/circuit_breaker.py` |
| 2 | Add concurrency tests asserting circuit opens at threshold under asyncio.gather | 394b37e | `tests/unit/integrations/email/test_circuit_breaker.py` |

## What Was Built

**Task 1 — Atomic pipeline in `record_failure`:**

Replaced five sequential `await redis.*` calls with a single `async with redis.pipeline(transaction=True) as pipe:` block. Commands are buffered without `await` (ZADD, ZREMRANGEBYSCORE, EXPIRE, ZCARD) and executed atomically via `await pipe.execute()`. The count is read from `results[3]` (positional pipeline result). The conditional open-marker `SET ... EX` remains outside the MULTI block — it is idempotent and has its own TTL contract, which is acceptable per CR-03 review guidance.

**Task 2 — Concurrency regression tests:**

Added `test_record_failure_concurrent_open_at_threshold` and `test_record_failure_below_threshold_does_not_open` to the existing test file. Both race parallel `record_failure` calls via `asyncio.gather`. The threshold test asserts the open-marker exists and the window has exactly N members after N concurrent calls. The below-threshold test asserts the open-marker does not exist after N-1 calls.

## Verification Results

```
grep -c "pipeline(transaction=True)" app/integrations/email/circuit_breaker.py → 2 (≥1 ✓)
ruff check circuit_breaker.py → All checks passed
mypy --strict circuit_breaker.py → Success: no issues found
ruff check test_circuit_breaker.py → All checks passed
mypy --strict test_circuit_breaker.py → Success: no issues found
pytest tests/unit/integrations/email/test_circuit_breaker.py → 9 passed (7 existing + 2 new)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pre-existing F541 ruff violation in test file**
- **Found during:** Task 2 verification
- **Issue:** Line 80 of the test file had `f"sz:email:circuit_window:yandex_postbox"` — an f-string with no placeholders, flagged by ruff F541.
- **Fix:** Removed the `f` prefix to make it a plain string literal.
- **Files modified:** `tests/unit/integrations/email/test_circuit_breaker.py`
- **Commit:** 394b37e (included in Task 2 commit)

## Known Stubs

None.

## Threat Flags

None. This plan modifies existing internals only; no new network endpoints, auth paths, or trust boundaries introduced.

## Self-Check: PASSED

- `apps/backend/app/integrations/email/circuit_breaker.py` — FOUND (modified)
- `apps/backend/tests/unit/integrations/email/test_circuit_breaker.py` — FOUND (modified)
- Commit e4628f4 — FOUND
- Commit 394b37e — FOUND
- All 9 tests pass
- ruff + mypy --strict pass on both files
