---
phase: 43-multi-user-admin-module
plan: 16
subsystem: users-auth-atomic-uow
tags: [bug-fix, audit, atomicity, actor-attribution, forensics, integration-test]
dependency_graph:
  requires: [43-14, 43-15]
  provides: [CR-04-closed, WR-01-closed, WR-03-closed, WR-04-closed, USERS-04-atomic, USERS-05-atomic]
  affects:
    - apps/backend/app/core/dependencies.py
    - apps/backend/app/modules/auth/service.py
    - apps/backend/app/modules/users/service.py
    - apps/backend/app/modules/users/repository.py
    - apps/backend/tests/integration/users/test_deactivate_atomic_uow.py
    - apps/backend/tests/integration/users/test_session_revoked_all_actor_attribution.py
    - apps/backend/tests/integration/users/test_family_count_db_authoritative.py
    - apps/backend/tests/integration/users/test_soft_delete_records_actor.py
tech_stack:
  added: []
  patterns:
    - no-commit-helper-pattern (CR-04 — composable UoW variant)
    - UPDATE-RETURNING-distinct-count (WR-04 — DB-authoritative family_count)
    - COALESCE-actor-id-on-soft-delete (WR-03 — forensic chain preservation)
    - actor-vs-target-separation-in-Protocol (WR-01 — audit attribution clarity)
key_files:
  created:
    - apps/backend/tests/integration/users/test_deactivate_atomic_uow.py
    - apps/backend/tests/integration/users/test_session_revoked_all_actor_attribution.py
    - apps/backend/tests/integration/users/test_family_count_db_authoritative.py
    - apps/backend/tests/integration/users/test_soft_delete_records_actor.py
  modified:
    - apps/backend/app/core/dependencies.py
    - apps/backend/app/modules/auth/service.py
    - apps/backend/app/modules/users/service.py
    - apps/backend/app/modules/users/repository.py
decisions:
  - "CR-04 no-commit split: _revoke_all_sessions_no_commit (no commit) + revoke_all_sessions (thin commit wrapper). invalidate_all_families_for_user calls the no-commit variant. Both password_changed_revokes_sessions and /auth/logout-all use the wrapper — no changes needed there."
  - "WR-01 Protocol change: actor_user_id: UUID | None added to UserSessionInvalidator.__call__. None is valid (for self-initiated actions like logout-all where actor == target). revoke_all_sessions wrapper passes actor_user_id=user_id."
  - "WR-04 DB-authoritative count: UPDATE...RETURNING family_id used in _revoke_all_sessions_no_commit. len(family_ids_raw) from Redis SMEMBERS removed. The DB UPDATE runs regardless of Redis state."
  - "WR-03 COALESCE pattern: repository.soft_delete_user now accepts actor_user_id and uses func.coalesce(User.deactivated_by_user_id, actor_user_id) — preserves existing value on post-deactivate-delete path, fills NULL on pure-delete path."
  - "Task 4 test design: db_session.rollback() required after ASGITransport exception to undo uncommitted changes before asserting DB state. RuntimeError propagates through ASGITransport to the test (not converted to 500), caught with pytest.raises."
metrics:
  duration: "~25 minutes"
  completed: "2026-05-19T19:15:49Z"
  tasks_completed: 8
  files_changed: 8
---

# Phase 43 Plan 16: Atomic UoW + Audit Attribution Fix Summary

**One-liner:** Close CR-04/WR-01/WR-03/WR-04 by introducing `_revoke_all_sessions_no_commit`, plumbing `actor_user_id` through the `UserSessionInvalidator` Protocol, using DB-authoritative `RETURNING family_id` count, and COALESCE-populating `deactivated_by_user_id` on the pure-delete path — 4 source patches + 4 integration tests.

## What Was Built

### CR-04 (BLOCKER): deactivate_user / soft_delete_user UoW split fixed

**Root cause:** `invalidate_all_families_for_user` → `revoke_all_sessions` called `await session.commit()` internally. This split `deactivate_user`'s UoW into two transactions: tx-1 committed the UPDATE + revoke + `session_revoked_all` audit; tx-2 committed the `user_deactivated` audit. A failure of tx-2 left the system with a deactivated user but no `user_deactivated` audit row.

**Fix split:**
```
_revoke_all_sessions_no_commit(session, redis, user_id, *, actor_user_id)  → no commit
    ↑ called by
revoke_all_sessions(session, redis, user_id)  → wraps with session.commit()
    (used by /auth/logout-all + password_changed_revokes_sessions — unchanged semantics)
    ↑ NOT called by
invalidate_all_families_for_user(session, *, user_id, actor_user_id, reason)  → calls no-commit variant
    (UserSessionInvalidator Protocol impl registered in main.py)
```

`deactivate_user` and `soft_delete_user` now have ONE `session.commit()` at the end covering all mutations + audits atomically.

### WR-01 (WARNING): session_revoked_all actor attribution fixed

**Root cause:** `revoke_all_sessions` emitted `actor_user_id=user_id` where `user_id` was the TARGET. Audit review looked like the target deactivated themselves.

**Fix:** `UserSessionInvalidator` Protocol's `__call__` now includes `actor_user_id: UUID | None`. Every callsite passes `actor_user_id=actor.id`. The `revoke_all_sessions` wrapper passes `actor_user_id=user_id` (self-action semantics for logout-all/password-change).

**4-callsite inventory confirmed all updated atomically:**
1. `users/service.py:deactivate_user` — `actor_user_id=actor.id`
2. `users/service.py:soft_delete_user` — `actor_user_id=actor.id`
3. `auth/service.py:invalidate_all_families_for_user` — Protocol impl (accepts + passes `actor_user_id`)
4. `auth/service.py:revoke_all_sessions` — wrapper (passes `actor_user_id=user_id` for self-action)

`main.py:270` registration via `register_user_session_invalidator(invalidate_all_families_for_user)` required no change — it's parametric over the Protocol shape.

### WR-04 (WARNING): DB-authoritative family_count fixed

**Root cause:** `revoke_all_sessions` computed `family_count = len(SMEMBERS auth:user_sessions:{user_id})`. Redis can drift below DB ground truth.

**Fix:** `_revoke_all_sessions_no_commit` uses `UPDATE...RETURNING family_id` and counts the distinct set of returned family_ids. The UPDATE runs regardless of Redis state; Redis cleanup is best-effort.

### WR-03 (WARNING): soft_delete_user populates deactivated_by_user_id fixed

**Root cause:** `repository.soft_delete_user` UPDATE never touched `deactivated_by_user_id`. Pure-delete-without-deactivate path left `deactivated_by_user_id=NULL`.

**Fix:** `soft_delete_user` now accepts `actor_user_id: UUID` and uses:
```python
deactivated_by_user_id=func.coalesce(User.deactivated_by_user_id, actor_user_id)
```
This preserves existing values (delete-after-deactivate path) and fills NULLs (pure-delete path).

## Integration Tests

### Task 4 — CR-04 atomic UoW regression (`test_deactivate_atomic_uow.py`)

Two tests:
1. **Rollback test**: monkeypatches `audit.emit` to raise `RuntimeError` on `user_deactivated` event. After `pytest.raises(RuntimeError)` catches the exception propagating through `ASGITransport`, calls `await db_session.rollback()` to clean up uncommitted changes, then asserts `target.is_active is True` (UPDATE rolled back) and no `session_revoked_all` audit rows committed.
2. **Positive control**: normal deactivate succeeds 204; both `session_revoked_all` + `user_deactivated` audit rows present.

**Key design note:** `ASGITransport` propagates unhandled `RuntimeError` from the ASGI app to the test caller (not converted to 500). `db_session.rollback()` must be called after the exception to undo uncommitted SQL statements before querying DB state.

### Task 5 — WR-01 actor attribution regression (`test_session_revoked_all_actor_attribution.py`)

One test: owner deactivates reception → `session_revoked_all.actor_user_id == owner.id` and `!= target.id`.

### Task 6 — WR-04 DB-authoritative family_count regression (`test_family_count_db_authoritative.py`)

One test: seeds 3 RefreshToken rows + Redis SMEMBERS, then deletes the Redis key before deactivation. Asserts `session_revoked_all.payload['family_count'] == 3` and `user_deactivated.payload['sessions_revoked_count'] == 3` (DB truth, not Redis 0).

### Task 7 — WR-03 soft_delete actor population regression (`test_soft_delete_records_actor.py`)

Two tests:
1. Pure-delete path: `deactivated_by_user_id == owner_id` after DELETE on active user (was NULL pre-fix).
2. Delete-after-deactivate path: `deactivated_by_user_id` unchanged after DELETE (COALESCE preserves existing value); `deactivated_at` unchanged.

## Pre-existing Test Adjustments

No pre-existing tests asserted the old (buggy) WR-01 attribution shape (`actor_user_id == target.id`). The `test_users_session_invalidation.py` tests only assert `sessions_revoked_count >= 1` and `401` — no actor attribution assertions. No test updates required.

## Regression Suite Results (Task 8)

```
uv run pytest tests/integration/users/ tests/integration/auth/ tests/integration/test_app_wiring.py tests/unit/users/ -q --no-header
88 passed, 1 xfailed in 13.70s
```

The `xfailed` is `test_password_reset_no_oracle.py` — expected (D-41-17 anti-oracle gate, awaiting Phase 44 RESET-01).

Previous baseline (43-15): 27 passed in users suite. After 43-16: 33 passed in users suite (+6 new from this plan's 4 test files × multiple tests).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan's inline sanity check matches `session.commit()` in docstring text**
- **Found during:** Task 2 verification
- **Issue:** The plan's verification script asserted `'session.commit()' not in inspect.getsource(_revoke_all_sessions_no_commit)` — but `getsource` includes the function's docstring, which contains the text "NO session.commit()". This is a false positive; the actual code has no `session.commit()` call.
- **Fix:** Skipped the false-positive assertion; confirmed correctness via `grep -n 'session.commit()' app/modules/auth/service.py` and manual code inspection.
- **Impact:** None — the implementation is correct.

**2. [Rule 1 - Bug] Task 4 test needed `db_session.rollback()` after ASGITransport exception**
- **Found during:** Task 4 test execution
- **Issue:** After `RuntimeError` propagates through `ASGITransport`, uncommitted SQL (UPDATE users SET is_active=False, etc.) executed by the route handler remains visible to the test's `db_session` (same connection, same PostgreSQL transaction). `db_session.refresh(target)` showed `is_active=False` not because the changes committed but because the session's own transaction sees its own pending changes.
- **Fix:** Added `await db_session.rollback()` after the `pytest.raises` block to undo the pending changes (ROLLBACK TO SAVEPOINT in the test harness), then asserted the clean state.
- **Impact:** The test now correctly validates CR-04 atomicity.

## Known Stubs

None. All changes are functional end-to-end.

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes. The `UserSessionInvalidator` Protocol extension adds a parameter but does not widen the attack surface.

## Grep Verification Matrix

| Check | Expected | Actual |
|-------|----------|--------|
| `grep -c 'actor_user_id: UUID \| None' dependencies.py` | ≥1 | 1 |
| `grep -c 'WR-01' dependencies.py` | ≥1 | 1 |
| `grep -c 'async def _revoke_all_sessions_no_commit' auth/service.py` | 1 | 1 |
| `grep -c '.returning(RefreshToken.family_id)' auth/service.py` | 1 | 1 |
| `grep -c 'len(family_ids_raw)' auth/service.py` | 0 | 0 |
| `grep -c 'actor_user_id=user_id' auth/service.py` | ≥1 | 4 |
| `grep -c 'actor_user_id=actor.id' users/service.py` | ≥4 | 11 |
| `grep -c 'User.deactivated_by_user_id, actor_user_id' users/repository.py` | 1 | 1 |
| `grep -c 'actor_user_id: UUID' users/repository.py` | ≥2 | 2 |
| `grep -c 'await session.commit()' users/service.py` | ≥5 | 5 |
| ruff on all 4 modified source files | green | PASS |
| mypy --strict on dependencies.py + users/*.py | green | PASS |
| mypy --strict on auth/service.py | pre-existing attr-defined errors | unchanged |
| lint-imports | 0 broken | PASS |
| Full suite (88 tests) | all pass | PASS |

## Commits

| Hash | Type | Description |
|------|------|-------------|
| `ef85c64` | fix | Extend UserSessionInvalidator Protocol with actor_user_id (WR-01) |
| `1d70be9` | fix | Refactor auth/service.py — no-commit helper + DB family_count (CR-04+WR-01+WR-04) |
| `4f4524e` | fix | Plumb actor_user_id through users service + repository (CR-04+WR-01+WR-03) |
| `ba97ec5` | test | Atomic UoW regression test — rollback on audit failure (CR-04) |
| `b320ae0` | test | session_revoked_all actor attribution regression test (WR-01) |
| `7f16e65` | test | DB-authoritative family_count regression test (WR-04) |
| `0ebcbda` | test | soft_delete_user populates deactivated_by_user_id regression test (WR-03) |

## Self-Check: PASSED
