---
phase: 66-idempotency-hardening
plan: "02"
subsystem: backend/idempotency
tags: [idempotency, security, refactor, orchestrator, user-scoped]
dependency_graph:
  requires:
    - 66-01 (audit/classification — already-wired set)
  provides:
    - apps/backend/app/core/idempotency.py (hardened primitive + shared orchestrator)
    - apps/backend/app/modules/*/router.py (12 callsites refactored)
  affects:
    - 66-03 (IDM-07 wiring — consumes idempotent_execute)
    - 66-05 (IDM-03 tests — regression baseline now clean)
tech_stack:
  added: []
  patterns:
    - "idempotent_execute: callable-wrapper orchestrator (status_code, body_bytes) tuple runner contract"
    - "D-66-USER-SCOPE: Redis key prefix {user_id}:{method}:{path}:{header} — user_id FIRST"
    - "IDM-06: AppError → store error envelope + re-raise; unknown Exception → delete placeholder + re-raise"
key_files:
  created:
    - apps/backend/tests/unit/test_idempotency_orchestrator.py
  modified:
    - apps/backend/app/core/idempotency.py
    - apps/backend/app/modules/pt_packages/router.py
    - apps/backend/app/modules/pt_sessions/router.py
    - apps/backend/app/modules/bookings/router.py
    - apps/backend/app/modules/memberships/router.py
    - apps/backend/app/modules/online_payments/router.py
    - apps/backend/app/modules/schedule/router.py
    - apps/backend/tests/unit/test_idempotency.py
decisions:
  - "idempotent_execute runner contract: Callable[[], Awaitable[tuple[int, bytes]]] — status_code + pre-serialized body_bytes"
  - "User-scoped key shape locked: f'{current_user.id}:{request.method}:{request.url.path}:{key}' — user_id FIRST (D-66-USER-SCOPE)"
  - "create_time_off kept on inline block: its TimeOffBookedConflictError builds a custom response with extra 'data' field (conflictingSlotIds/conflictingBookingIds) tested by test_time_off.py:638-639; the orchestrator AppError branch only preserves {code, message, fields}; deferring to 66-03 or future phase"
  - "store_idempotency_response uses response body hash; idempotent_execute stores REQUEST body hash in all envelopes (success + error) for T-66-05 body-hash invariant enforcement on replay"
metrics:
  duration: "~65min"
  completed_date: "2026-05-29"
  tasks_completed: 3
  files_modified: 8
---

# Phase 66 Plan 02: Idempotency Core Hardening Summary

**One-liner:** User-scoped TTL-86400 {16,128}-bounded idempotent_execute orchestrator with AppError-store/unknown-delete branches; 12 wired callsites refactored off inline blocks across 6 router files.

## What Was Done

### Task 1: Harden the core primitive (TDD RED → GREEN)

**RED:** Created `tests/unit/test_idempotency_orchestrator.py` with 19 tests covering all behavior-block cases. Tests failed on import (`idempotent_execute` not yet exported).

**GREEN:** Changed `apps/backend/app/core/idempotency.py`:
- `IDEMPOTENCY_TTL_SECONDS`: 3600 → 86400 (IDM-02)
- `IDEMPOTENCY_KEY_PATTERN`: `{1,128}` → `{16,128}` (IDM-02)
- `verify_idempotency`: added `Annotated[_CurrentUser, Depends(_get_current_user)]` parameter; returns `f"{current_user.id}:{method}:{path}:{key}"` (D-66-USER-SCOPE / IDM-05)
- New `idempotent_execute(redis, key, body_bytes, *, runner)` orchestrator added to `__all__` (IDM-06)
- Updated `tests/unit/test_idempotency.py` for new min-length (16) and user-scoped return format

The existing `test_idempotency.py` + `tests/integration/payments/test_idempotency.py` + 19 new orchestrator unit tests all pass.

### Orchestrator shape (for 66-03 consumption)

```python
async def idempotent_execute(
    redis: Redis,
    key: str,           # the user-scoped route-bound key from verify_idempotency()
    body_bytes: bytes,  # raw incoming request body (request.body())
    *,
    runner: Callable[[], Awaitable[tuple[int, bytes]]],
    # runner returns (status_code: int, response_body_bytes: bytes)
) -> Response:
    ...
```

**Runner contract:** The runner callable returns `(status_code, body_bytes)` where `body_bytes` is the pre-serialized UTF-8 JSON response body. The orchestrator stores the REQUEST body hash in the envelope (not the response body hash) so the T-66-05 body-hash invariant applies on both success-replay and error-replay paths.

**Exception branches (IDM-06):**
- `AppError` → build `{"code", "message", "fields"}` bytes at `exc.status_code`, `store_idempotency_response`, `raise` — retry replays the error (not `idempotency_in_flight`)
- Any other `Exception` → `redis.delete(_redis_key(key))`, `raise` — next retry gets a fresh claim (no 24h lockout)

**Public name added to `__all__`:** `idempotent_execute`

### Task 2: Refactor 8 callsites in pt_packages/pt_sessions/bookings/memberships + 5 callsites in schedule

Replaced every inline ~40-line claim/replay/store block with:
```python
incoming_body = await request.body()

async def _runner() -> tuple[int, bytes]:
    result = await service.do_operation(session, actor, ...)
    body_bytes = json.dumps(
        envelope(result).model_dump(mode="json", by_alias=True),
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return status.HTTP_2XX_CREATED_OR_OK, body_bytes

return await idempotent_execute(redis, idempotency_key, incoming_body, runner=_runner)
```

**Callsites refactored (12 total):**
- `pt_packages`: create_pt_package (201), cancel_pt_package (200), refund_pt_package (200)
- `pt_sessions`: record_pt_session (201), cancel_pt_session (200)
- `bookings`: create_booking (201), cancel_booking (200)
- `memberships`: create_membership (201)
- `schedule`: publish_slot (201), cancel_slot (200), create_recurring_template (201), deactivate_recurring_template (200)
- `schedule`: delete_time_off (204, empty body)

**Removed imports from each file:** `base64`, `IDEMPOTENCY_REDIS_PREFIX`, `IDEMPOTENCY_TTL_SECONDS`, `begin_idempotency`, `load_idempotency_response`, `ConflictError`, `ValidationAppError` (where not used elsewhere).

### Task 3: Remove _outer_idempotency_replay_or_run from online_payments

Deleted the module-local `_outer_idempotency_replay_or_run` (70 lines). Updated all 4 sell endpoint `_runner()` closures from `SellResponse` return to `tuple[int, bytes]`. Called `idempotent_execute` directly.

**grep count after:** `grep -c "_outer_idempotency_replay_or_run" online_payments/router.py` = 0.

## Deviations from Plan

### Auto-discovered: 6 schedule endpoints also wired (not in plan task list)

**Found during:** Task 2 scope verification
**Issue:** Plan task 2 listed pt_packages/pt_sessions/bookings/memberships. The 66-01 audit and additional_context both noted schedule was also wired. 6 schedule endpoints had the same inline block.
**Fix:** Refactored 5 of 6 schedule endpoints. `create_time_off` deferred (see below).
**Files modified:** `apps/backend/app/modules/schedule/router.py`
**Commit:** 1002d98c

### Partially deferred: create_time_off kept on inline block

**Found during:** Task 2 — schedule refactoring
**Issue:** `create_time_off` catches `TimeOffBookedConflictError` and builds a custom response body with an extra `"data"` field (`{"code", "message", "fields", "data": {"conflictingSlotIds": [...], "conflictingBookingIds": [...]}}`) that is asserted by `test_time_off.py:638-639`. The orchestrator's AppError branch only preserves `{code, message, fields}` — re-raising would lose the `"data"` field and break the test.
**Decision:** Keep `create_time_off` on the inline block. This is a semantic difference (enriched 409 body vs. standard AppError body) that requires a test update or orchestrator extension to handle correctly.
**Impact:** 1 of 13 wired schedule callsites remains on inline block. All existing tests pass.
**Deferred to:** 66-03 scope or future phase with explicit test contract.

## Verification Results

- `uv run pytest tests/integration/pt_packages tests/integration/pt_sessions tests/integration/bookings tests/integration/memberships tests/integration/payments tests/unit/test_idempotency*.py tests/integration/schedule` — **478 passed**
- `uv run ruff check` — passed
- `uv run ruff format --check` — passed (637 files formatted)
- `uv run mypy --strict app` — passed (210 source files, 0 errors)
- `uv run lint-imports` — passed
- `grep -c "_outer_idempotency_replay_or_run" apps/backend/app/modules/online_payments/router.py` — **0**
- `IDEMPOTENCY_TTL_SECONDS == 86400` — **confirmed**
- `IDEMPOTENCY_KEY_PATTERN == r"^[A-Za-z0-9_:-]{16,128}$"` — **confirmed**
- `verify_idempotency` returns `{user_id}:{method}:{path}:{key}` — **confirmed**

## Known Stubs

None — this plan is a pure implementation/refactoring plan with no UI or data wiring.

## Self-Check: PASSED
