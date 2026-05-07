# Phase 15 — Deferred Items

Out-of-scope discoveries logged during execution per the executor SCOPE BOUNDARY rule.

## auth/service.py write-path semantics review (from Plan 15-04 Task 3)

**Discovered:** 2026-05-07 during INFRA-13 commit-gate AST walker development.

**Finding:** Pointing the SVC001 commit-gate walker at `apps/backend/app/modules/auth/service.py` surfaces two public functions that match the Phase 12.1 bug shape under strict D-04 / D-05 reading:

| File:Line | Function | Pattern |
|-----------|----------|---------|
| `apps/backend/app/modules/auth/service.py:88` | `authenticate` | Calls `audit.emit("login_failed", ...)` and `audit.emit("login_success", ...)` but does NOT call `await session.commit()` itself; commit happens in the caller chain (`issue_tokens` for the success path) or via the request lifecycle. |
| `apps/backend/app/modules/auth/service.py:271` | `rotate_refresh` | Uses `async with session.begin():` to wrap mutating SQL + `audit.emit("family_reuse_detected", ...)`. The `begin()` context-manager auto-commits on `__aexit__`, so this is correct in practice — but the walker only recognises explicit `session.commit()` calls. |

**Why deferred from Plan 15-04:**

- **Pre-existing.** Both shapes predate Phase 15 and have integration-test coverage that passes (the test fixture's SAVEPOINT-based per-test session masks any rollback issue in tests; the actual production-side audit-row-on-failure semantics would need a separate review).
- **Out of scope.** Plan 15-04 owns INFRA-13's regression bound for `clients/service.py` only (the post-12.1 fix). Extending the gate to other modules requires per-module write-path semantics review.
- **Walker correctness.** The `rotate_refresh` case (`async with session.begin():`) is a walker false positive — the begin-context-manager auto-commits and is structurally equivalent to an explicit commit. A future plan should either (a) extend the walker to recognise `async with session.begin():` as a commit equivalent, or (b) refactor `rotate_refresh` to use an explicit `await session.commit()`.
- **`authenticate` may be a real bug.** On the `InvalidPassword` failure path, `audit.emit("login_failed", ...)` enrolls an `AuditLog` row in the unit-of-work and then re-raises. In production (`get_db` per-request session, no SAVEPOINT), the request lifecycle's exception-driven exit would close the session WITHOUT committing — silently dropping the `login_failed` audit row. The integration test (`tests/integration/auth/test_login.py:186`) only sees the row because the test fixture shares a single connection-bound session with `join_transaction_mode='create_savepoint'`, so the emitted-but-not-committed row is visible to the same session's subsequent SELECT before the outer-transaction rollback.

**Recommended next step:** Open a quick task or Phase 16 hygiene plan to:
1. Reproduce the `login_failed` audit-row loss in production (single-session repro, confirm row is rolled back).
2. Either add `await session.commit()` after each `audit.emit` on the failure path of `authenticate`, OR document the pattern + add the SVC001 marker on a renamed private helper that the public `authenticate` delegates to.
3. Extend the live commit-gate `_CLIENTS_SERVICE` scope to include `auth/service.py` once those callsites are fixed.
4. Optionally extend the walker's `_function_has_commit` predicate to recognise `async with session.begin():` blocks as commit-equivalents (handles the `rotate_refresh` shape and any future module that uses the begin-context idiom).

**Risk if left indefinitely:** Repeats the Phase 12.1 incident class for the auth module (audit row loss on failure paths). Severity: medium — login_failed audit is used for forensics / rate-limit observability, not for correctness of the auth flow itself.
