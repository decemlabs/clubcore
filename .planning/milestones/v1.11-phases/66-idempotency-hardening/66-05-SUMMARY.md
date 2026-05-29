---
phase: 66-idempotency-hardening
plan: "05"
subsystem: backend/testing
tags: [idempotency, security, integration-tests, IDM-03, IDM-05, IDM-06]
dependency_graph:
  requires:
    - 66-02 (idempotent_execute orchestrator + user-scoped verify_idempotency)
    - 66-03 (4 C-class membership transitions wired to idempotent_execute)
  provides:
    - apps/backend/tests/integration/memberships/test_idempotency_hardening.py
    - apps/backend/tests/integration/online_payments/test_idempotency_hardening.py
    - apps/backend/tests/integration/pt_packages/test_idempotency_hardening.py
    - apps/backend/tests/integration/pt_sessions/test_idempotency_hardening.py
    - apps/backend/tests/integration/bookings/test_idempotency_hardening.py
  affects:
    - Future phases adding or modifying category-A endpoints
tech_stack:
  added: []
  patterns:
    - "IDM-03 regression lock: r2.content == r1.content + AuditLog count unchanged + 422 on body mismatch"
    - "IDM-05 cross-user proof: same Idempotency-Key from two users yields distinct Redis entries"
    - "IDM-06 AppError-replay proof: retry replays stored error (not idempotency_in_flight)"
    - "IDM-06 rollback-retry proof: raise_app_exceptions=False + monkeypatch RuntimeError"
key_files:
  created:
    - apps/backend/tests/integration/memberships/test_idempotency_hardening.py
    - apps/backend/tests/integration/online_payments/test_idempotency_hardening.py
    - apps/backend/tests/integration/pt_packages/test_idempotency_hardening.py
    - apps/backend/tests/integration/pt_sessions/test_idempotency_hardening.py
    - apps/backend/tests/integration/bookings/test_idempotency_hardening.py
  modified: []
decisions:
  - "pt_sessions record tests use fixed performedAt to ensure body is byte-identical across two HTTP calls (dynamic datetime would differ, triggering idempotency_key_reuse)"
  - "rollback-retry test creates its own ASGITransport(raise_app_exceptions=False) client so RuntimeError produces 500 response rather than propagating as Python exception to pytest"
  - "IDM-05 cross-user test seeds second owner via pytest_asyncio fixture; authed_client_second_owner closes app.dependency_overrides in finally block"
metrics:
  duration: "~18min"
  completed_date: "2026-05-29"
  tasks_completed: 3
  files_modified: 5
requirements-completed: [IDM-03, IDM-06]
---

# Phase 66 Plan 05: IDM-03 + IDM-06 Integration Tests Summary

**One-liner:** 48 hardened idempotency integration tests across 5 category-A modules prove byte-identical replay, no-re-emit-audit, cross-user separation (IDM-05), AppError-replay, and rollback-retry (IDM-06) against real Postgres + real Redis.

## Performance

- **Duration:** ~18 min
- **Started:** 2026-05-29T08:14Z
- **Completed:** 2026-05-29T08:32Z
- **Tasks:** 3 completed
- **Files created:** 5

## Accomplishments

- Added `test_idempotency_hardening.py` in memberships (15 tests), online_payments (12 tests), pt_packages (9 tests), pt_sessions (6 tests), bookings (6 tests) — 48 tests total.
- Every test file covers: byte-identical replay (r2.content == r1.content), unchanged AuditLog count after replay, and 422 idempotency_key_reuse on body mismatch.
- The memberships file additionally proves IDM-05 cross-user separation and IDM-06 exception lifecycle (AppError-replay + rollback-retry).

## Category-A Endpoints Covered

### memberships (5 endpoints)
- `POST /api/v1/memberships` (create_membership)
- `POST /api/v1/memberships/{id}/cancel` (cancel_membership, IDM-07)
- `POST /api/v1/memberships/{id}/freeze` (freeze_membership, IDM-07, empty body)
- `POST /api/v1/memberships/{id}/unfreeze` (unfreeze_membership, IDM-07, empty body)
- `POST /api/v1/memberships/{id}/renew` (renew_membership, IDM-07, empty body)

### online_payments (4 endpoints)
- `POST /api/v1/online-payments/memberships/{id}/sell` (sell_membership_redirect)
- `POST /api/v1/online-payments/memberships/{id}/sell-qr` (sell_membership_qr)
- `POST /api/v1/online-payments/pt-packages/{id}/sell` (sell_pt_package_redirect)
- `POST /api/v1/online-payments/pt-packages/{id}/sell-qr` (sell_pt_package_qr)

### pt_packages (3 endpoints)
- `POST /api/v1/pt-packages` (create_pt_package)
- `POST /api/v1/pt-packages/{id}/cancel` (cancel_pt_package)
- `POST /api/v1/pt-packages/{id}/refund` (refund_pt_package)

### pt_sessions (2 endpoints)
- `POST /api/v1/pt-sessions` (record_pt_session)
- `POST /api/v1/pt-sessions/{id}/cancel` (cancel_pt_session)

### bookings (2 endpoints)
- `POST /api/v1/bookings` (create_booking)
- `POST /api/v1/bookings/{id}/cancel` (cancel_booking)

## IDM-05 + IDM-06 Regression Locks

### IDM-05 Cross-user (T-66-13)

`test_cross_user_same_key_distinct_outcomes` — two distinct owner users send the same
`Idempotency-Key` header value to `POST /api/v1/memberships`. Both receive 201 success;
the created membership IDs differ; response bodies differ. The user-scoped Redis key shape
`cc:idem:{user_id}:POST:/api/v1/memberships:{key}` ensures user B is never served user A's
cached envelope.

### IDM-06 AppError-replay (T-66-14)

`test_app_error_retry_replays_error_not_in_flight` — cancelling an already-cancelled
membership raises `ConflictError(invalid_transition)` on the first call (409). The retry
with the same key+body replays the stored 409 invalid_transition body — NOT
`409 idempotency_in_flight`. The stored envelope's body hash is the REQUEST body hash
(per D-66-LIFECYCLE-HELPER), so body-hash mismatch would still give 422 on a different body.

### IDM-06 Rollback-retry (T-66-14)

`test_rollback_retry_allows_fresh_attempt` — monkeypatches `service.create_membership` to
raise `RuntimeError` on the first invocation. The `idempotent_execute` orchestrator catches
the unknown exception, calls `await redis.delete(_redis_key(key))`, and re-raises. The test
uses `ASGITransport(raise_app_exceptions=False)` so the re-raised RuntimeError becomes a 500
HTTP response (not a Python exception in the test). The second call with the same key+body
returns 201 (fresh claim, placeholder deleted). Confirms no 24h lockout (T-66-14).

## Task Commits

1. **Task 1: memberships + online_payments tests** - `c29beac0` (feat)
2. **Task 2: pt_packages + pt_sessions + bookings tests** - `90bf6369` (feat)

(Task 3 cross-user/IDM-06 tests were included in Task 1's memberships file.)

**Plan metadata:** (pending final commit)

## Verification Results

- `uv run pytest tests/integration/memberships/test_idempotency_hardening.py tests/integration/online_payments/test_idempotency_hardening.py tests/integration/pt_packages/test_idempotency_hardening.py tests/integration/pt_sessions/test_idempotency_hardening.py tests/integration/bookings/test_idempotency_hardening.py -q` — **48 passed**
- `uv run pytest tests/integration -q` — **1230 passed, 5 skipped** (3 pre-existing failures in test_payments_refund.py unrelated to this plan)
- `uv run ruff check tests` — passed
- `uv run mypy --strict app` — 0 errors, 210 source files
- `uv run lint-imports` — 3 contracts kept, 0 broken

## Deviations from Plan

### Rule 1 - Bug: pt_sessions performedAt must be captured before both submits

**Found during:** Task 2 — test_record_pt_session_double_submit_byte_identical
**Issue:** The `_record_body()` helper called `datetime.now(UTC)` dynamically, so the two submits
had different `performedAt` values → idempotency check compared different request bodies →
422 `idempotency_key_reuse` (correct behavior, wrong test setup).
**Fix:** Changed `_record_body` to accept an optional `performed_at` parameter; tests capture
`performed_at = datetime.now(UTC) - timedelta(minutes=10)` once and pass it to both calls.
**Files modified:** `tests/integration/pt_sessions/test_idempotency_hardening.py`

### Rule 1 - Bug: rollback test needed raise_app_exceptions=False

**Found during:** Task 1 — test_rollback_retry_allows_fresh_attempt
**Issue:** When `idempotent_execute` catches an unknown `Exception`, it deletes the placeholder
and re-raises. FastAPI has no registered handler for `RuntimeError`, so `ASGITransport` propagated
the exception to the test (Python exception, not HTTP 500).
**Fix:** The rollback test creates its own `ASGITransport(raise_app_exceptions=False)` client
with explicit `get_db` / `get_redis` overrides. Starlette's internal 500 handler converts the
unhandled RuntimeError to an HTTP 500 response. Added `seeded_owner` and `app` to fixture args.
**Files modified:** `tests/integration/memberships/test_idempotency_hardening.py`

### Rule 1 - Bug: cancel_pt_session body uses cancelReason not reason

**Found during:** Task 2 — cancel pt_session tests
**Issue:** `PtSessionCancelRequest` uses `cancel_reason` field (aliased to `cancelReason` in
camelCase API). Test used `{"reason": "..."}` → 422 field-required validation error.
**Fix:** Changed all cancel_pt_session body JSON to use `{"cancelReason": "..."}`.
**Files modified:** `tests/integration/pt_sessions/test_idempotency_hardening.py`

## Known Stubs

None — this plan is a pure test-addition plan with no UI or data stubs.

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes introduced. All new code is in test files.

## Self-Check: PASSED
