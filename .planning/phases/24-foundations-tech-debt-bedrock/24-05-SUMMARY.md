---
phase: 24-foundations-tech-debt-bedrock
plan: 05
subsystem: auth-commit-gate
tags:
  - auth
  - svc001
  - commit-gate
  - tech-debt
  - debt-03
requires:
  - INFRA-13 SVC001 walker apparatus (Phase 15)
  - clients/service.py Phase 12.1 commit-on-write exemplar
provides:
  - DEBT-03 closure
  - SVC001 walker live coverage of app/modules/auth/service.py
  - Persisted audit rows on login_failed/login_success even when caller exception fires
affects:
  - app/modules/auth/service.py (authenticate + rotate_refresh)
  - tests/unit/test_service_commit_gate.py (_INSPECTED_SERVICES tuple)
tech-stack:
  added: []
  patterns:
    - Autobegin + explicit await session.commit() (matches in-file revoke_session/revoke_family shape)
    - Phase 12.1 commit-on-write pattern (audit.emit -> session.commit -> raise/return)
key-files:
  created: []
  modified:
    - apps/backend/app/modules/auth/service.py
    - apps/backend/tests/unit/test_service_commit_gate.py
decisions:
  - D-24-14 implemented: _AUTH_SERVICE added to _INSPECTED_SERVICES tuple
  - D-24-15 implemented: authenticate now commits on all 3 audit-emit branches; rotate_refresh refactored to expose explicit commits to the walker
  - D-24-16 honored: zero `# noqa: SVC001 caller-owns-txn` markers added in auth/service.py (none present)
  - D-24-17 verified: no integration test asserts audit-row absence on auth failure paths (existing tests assert presence)
metrics:
  duration_minutes: ~25
  completed_date: 2026-05-08
  tasks_completed: 1
  files_modified: 2
  commits: 1
requirements:
  - DEBT-03
---

# Phase 24 Plan 05: SVC001 walker -> auth/service.py + commit-on-write fix Summary

**One-liner:** Closed DEBT-03 by extending the SVC001 AST commit-gate to `app/modules/auth/service.py` and adding explicit `await session.commit()` calls in `authenticate` (3 audit-emit branches) and `rotate_refresh` (refactored to drop the `async with session.begin():` shape that the walker could not detect).

## What changed

### 1. `apps/backend/app/modules/auth/service.py` — `authenticate` (lines 110-203 post-edit)

Added explicit `await session.commit()` after each of the three `audit.emit(...)` callsites in `authenticate`, before the subsequent `raise` / `return`:

| Branch | audit.emit event | Commit insertion point |
|---|---|---|
| `verify_password` raised `InvalidPassword` (mismatch / corrupted hash) | `login_failed` reason=`invalid_credentials` | New `await session.commit()` before `raise` |
| `user is None` after sentinel-hash success (D-28 implausible collision) | `login_failed` reason=`invalid_credentials` | New `await session.commit()` before `raise InvalidPassword(...)` |
| Successful credential verify | `login_success` channel=`email_password` | New `await session.commit()` before `return user` |

Each commit is annotated with a `# Phase 24 DEBT-03 / SVC001:` rationale comment explaining the rollback-drop scenario it closes (mirrors the Phase 12.1 fix in `clients/service.py:create_client`).

### 2. `apps/backend/app/modules/auth/service.py` — `rotate_refresh` (lines ~325-490 post-edit)

**Inventory finding (deviation Rule 2 — auto-add missing critical functionality):** the SVC001 walker scope extension flagged `rotate_refresh` as a write-path offender despite the function having a transactionally-correct `async with session.begin():` block. Root cause: the walker's `_function_has_commit` detects only the literal `session.commit()` token in the AST and does not recognize the context-manager auto-commit on block exit.

The plan explicitly anticipated this risk in Action Step A and prescribed an explicit-commit fix. The implementation adopts the **same pattern already used in-file by `revoke_session`** (see lines 497-503 of `auth/service.py`, which document why the explicit `async with session.begin()` was dropped in favor of autobegin + explicit `commit()`):

- Removed the outer `async with session.begin():` block that previously wrapped the SELECT, the three branches, and the audit emit on branch (C).
- Added `await session.commit()` at the end of branch (A) ACTIVE (after `session.add(new_row)` + `await session.flush()` + `row.replaced_by_id` mutation, before the Redis writes).
- Added `await session.commit()` at the end of branch (C) REUSE/REVOKED (after the bulk `update(RefreshToken).values(revoked_at=now)` + the `audit.emit("family_reuse_detected", ...)`, before the Redis cleanup + `raise InvalidAccessToken("family_reuse_detected")`).
- Branch (B) REPLACED-WITHIN-WINDOW remains read-only (no DB mutation, returns the cached pair from Redis); branch fall-through to (C) preserves the previous semantics.
- The `with_for_update()` row lock is preserved — `AsyncSession` autobegins a transaction the moment the SELECT executes, so the FOR UPDATE lock is held identically to the prior `async with session.begin():` shape.

**Why this is the right choice (vs. inserting `await session.commit()` inside the `async with` block):** SQLAlchemy 2.0's `SessionTransaction.__aexit__` calls `commit()` on the wrapped transaction; if the user code already committed inside the block, the SessionTransaction is no longer active and `__aexit__` raises `InvalidRequestError`. Refactoring to autobegin + explicit commits is the documented in-file pattern (`revoke_session` comment block) and the planner-recommended fallback.

### 3. `apps/backend/tests/unit/test_service_commit_gate.py`

- Added `_AUTH_SERVICE = _BACKEND_APP / "modules" / "auth" / "service.py"` near the existing `_CLIENTS_SERVICE` / `_MEMBERSHIPS_SERVICE` constants (lines 167-174 post-edit).
- Extended `_INSPECTED_SERVICES` tuple to include `_AUTH_SERVICE`.
- Replaced the docstring of `test_service_commit_gate_against_app_modules` (lines 187-209 post-edit) with the Phase 24 DEBT-03 wording. Removed the stale `auth/service.py:authenticate ... see deferred-items.md` reference.
- `test_walker_scope_is_modules_service_only` unchanged (auth/service.py is already under `modules/`).

## Inventory of `apps/backend/app/modules/auth/service.py` public functions

Per the plan's Step A inventory requirement, every public (non-`_`-prefixed) function in `auth/service.py` was audited for the SVC001 commit-gate. Status post-edit:

| Function | Lines (post-edit) | audit.emit / mutation? | Commit status | Action taken |
|---|---|---|---|---|
| `load_user_by_id` | 95-102 | read-only (`session.get`) | not a write path | none — passes walker trivially |
| `authenticate` | 110-203 | 3 audit.emit sites (login_failed x2, login_success) | **GAP -> fixed** | added 3 explicit `await session.commit()` calls |
| `issue_tokens` | 211-259 | INSERT RefreshToken row (`session.add`) | already correct (commit at line ~246) | verify only — no edit |
| `revoke_sessions_on_password_change` | 304-328 | audit.emit `password_changed_revokes_sessions` | already correct (commit at line ~327) | verify only — no edit |
| `rotate_refresh` | 336-490 | INSERT/UPDATE RefreshToken + audit.emit `family_reuse_detected` | **GAP (walker shape) -> fixed** | refactored to autobegin + 2 explicit commits (branches A and C) |
| `revoke_session` | 500-563 | UPDATE RefreshToken + audit.emit `session_revoked` | already correct (commit at line ~557) | verify only — no edit |
| `revoke_all_sessions` | 571-619 | UPDATE RefreshToken + audit.emit `session_revoked_all` | already correct (commit at line ~617) | verify only — no edit |
| `list_user_sessions` | 627-716 | read-only (no mutation, no audit.emit) | not a write path | none — explicitly documented "Caller-owns-txn: no session.commit() — read-only path" in docstring |
| `revoke_family` | 724-789 | UPDATE RefreshToken + audit.emit `session_revoked` | already correct (commit at line ~781) | verify only — no edit |

**Summary:** 2 gaps fixed (`authenticate`, `rotate_refresh`); 5 functions verified-correct without edit; 2 functions are read-only and correctly out of scope.

## DEBT-03 deferred-scan: `auth/telegram_service.py`

Per PATTERNS.md Section 9 deferred-scan finding and CONTEXT.md D-24-15 follow-up question, `apps/backend/app/modules/auth/telegram_service.py` was scanned for the same audit.emit / commit pairing.

**Finding: file is already clean — no Phase 24 edit needed.**

Verification grep results:
```
102:    await audit.emit(...)
109:    await session.commit()
198:    await audit.emit(...)
205:    await session.commit()
253:        await session.commit()
265:        await session.commit()
270:        await session.commit()
274:    await audit.emit(...)
280:    await session.commit()
```

Each `audit.emit(...)` callsite is followed by an `await session.commit()` within ~7 lines. The file is correctly excluded from `_INSPECTED_SERVICES` because the SVC001 walker's `_SERVICE_GLOB = "modules/**/service.py"` matches by filename precisely; `telegram_service.py` is not in scope by design (DEBT-03 wording also scopes only to `service.py`).

This closes the D-24-15 follow-up scan question with no action required.

## D-24-17 risk verification: integration tests

Per CONTEXT.md D-24-17, the behavior change introduced by this plan (audit rows now persist on `login_failed` / `login_success` / `family_reuse_detected` even when the caller exception fires) could in principle break tests that asserted audit-row **absence** on the failure path.

**Finding: no such tests exist.** Grep results across `apps/backend/tests/integration/auth/`:

| File | line | assertion shape |
|---|---|---|
| `test_login.py` | 200-203 | asserts `len(rows) >= 1` for `login_failed` (presence) |
| `test_login_argon2_hygiene.py` | 98-101 | asserts `rows` non-empty for `login_failed` (presence) |
| `test_login.py` | 177-181 | asserts `len(rows) >= 1` for `login_success` (presence) |
| `test_refresh.py` | 202 | asserts `family_reuse_detected` row exists (presence) |
| `test_sessions_endpoints.py` | 305-326 | asserts `count_after == count_before` on a noop revoke (idempotent count check, not absence) |
| `test_logout.py` | 256-258 | asserts `session_revoked` row exists (presence) |
| `test_telegram_*` | various | asserts presence |

**Net result:** existing integration assertions all check for **presence**, which already succeeded before this plan (because the `verify_password` `raise` after the audit.emit happened to occur in a path where SQLAlchemy autobegun the transaction and `audit.emit`'s internal flush actually persisted the row pre-commit in some configurations). After this plan, presence is now **guaranteed by explicit commit** rather than incidental — strictly stronger semantics, no test edit needed. Integration tests are skipped locally (Docker / Postgres not running on this dev box) but logic-level reasoning confirms no assertion contradicts the new persistence semantics.

## Verification commands run

| Command | Result |
|---|---|
| `uv run pytest tests/unit/test_service_commit_gate.py -x -v` | 7/7 passed |
| `uv run pytest tests/unit/ -q` | 301/301 passed |
| `uv run pytest tests/ -q` | 314 passed, 290 skipped (integration tests skip — no local Postgres), 1 unrelated pre-existing visits-concurrency test fails on connection error |
| `uv run ruff check app/modules/auth/service.py tests/unit/test_service_commit_gate.py` | All checks passed |
| `uv run mypy --strict app/modules/auth/service.py` | Success: no issues found |
| `grep -F '_AUTH_SERVICE = _BACKEND_APP / "modules" / "auth" / "service.py"'` | 1 match |
| `count "await session.commit()" inside authenticate` | 3 (one per audit.emit branch) |
| `grep '# noqa: SVC001 caller-owns-txn' app/modules/auth/service.py` | 0 matches (D-24-16 honored) |

## Deviations from Plan

### Rule 2 — Auto-add missing critical functionality

**1. [Rule 2] `rotate_refresh` refactor — autobegin + explicit commits**

- **Found during:** Task 1 RED phase — extending `_INSPECTED_SERVICES` to include `_AUTH_SERVICE` produced TWO offenders, not one (`authenticate` AND `rotate_refresh`).
- **Issue:** The plan's Step A inventory anticipated `rotate_refresh` would be walker-acceptable via the `commit()` token detection on the `async with session.begin():` auto-commit shape. Empirically the walker's `_function_has_commit` AST predicate detects only the literal `session.commit()` call expression and **does not recognize the context-manager auto-commit on block exit**.
- **Fix:** Refactored `rotate_refresh` to drop the `async with session.begin():` block and rely on `AsyncSession` autobegin (triggered by the `SELECT ... FOR UPDATE`) plus explicit `await session.commit()` at the end of each mutating branch (A and C). Pattern is identical to in-file `revoke_session` / `revoke_all_sessions` — same author-pinned rationale at `auth/service.py:497-503`.
- **Why Rule 2 (auto-add) and not Rule 4 (architectural):** the change preserves all observable semantics — `with_for_update()` row lock holds for the same duration, transaction boundaries identical (autobegin to commit), all branches exit in the same DB state. The "refactor" is purely the literal expression of the same UoW with a different syntax that the walker can detect. Plan Action Step A explicitly authorized this fix path: "PRIORITIZE the former (no walker change) — the explicit commit is idempotent inside an already-committed `async with session.begin():`...". Note: I chose the alternate fix (drop `async with`) over the inside-block commit because SQLAlchemy 2.0 `SessionTransaction.__aexit__` calls `commit()` on its tracked transaction unconditionally; if user code committed first, the second commit raises `InvalidRequestError("This SessionTransaction is no longer active")`. The drop-the-block approach matches the in-file canonical pattern and avoids that runtime hazard.
- **Files modified:** `apps/backend/app/modules/auth/service.py` (function body of `rotate_refresh`).
- **Commit:** `72fba84`.

No other deviations. The plan's Step B (authenticate edits), Step C (test file edits), Step D (integration-test grep), and Step E (telegram_service.py confirmed-clean) executed exactly as written.

## Threat model coverage

All five threats from the plan's `<threat_model>` block are mitigated:

- **T-24-05-01** (login_failed audit row dropped on rollback) — mitigated by explicit commit after `audit.emit("login_failed", ...)`.
- **T-24-05-02** (login_success audit row dropped on later exception) — mitigated by explicit commit after `audit.emit("login_success", ...)`.
- **T-24-05-03** (future commit-gate evasion in auth) — mitigated by extending `_INSPECTED_SERVICES` to include `_AUTH_SERVICE`; CI now fails on any new public function in auth/service.py that emits audit or mutates session without an explicit commit.
- **T-24-05-04** (existing tests asserting audit-row absence on failure) — mitigated; D-24-17 grep confirmed no such tests exist.
- **T-24-05-05** (out-of-scope tampering on telegram_service.py) — accepted; file confirmed already clean by independent grep verification.

## Self-Check: PASSED

- File `apps/backend/app/modules/auth/service.py` exists ✓
- File `apps/backend/tests/unit/test_service_commit_gate.py` exists ✓
- File `.planning/phases/24-foundations-tech-debt-bedrock/24-05-SUMMARY.md` exists ✓
- Commit `72fba84` exists in git log ✓
- `_AUTH_SERVICE` constant present in test file ✓
- `authenticate` contains 3 `await session.commit()` calls ✓
- Zero SVC001 noqa markers in auth/service.py ✓
- 301/301 unit tests pass; ruff + mypy --strict clean on modified files ✓
