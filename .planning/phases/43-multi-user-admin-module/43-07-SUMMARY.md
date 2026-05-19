---
phase: 43-multi-user-admin-module
plan: 07
subsystem: auth

tags: [auth, refresh-token, anti-oracle, audit, mypy, sqlalchemy]

# Dependency graph
requires:
  - phase: 43-multi-user-admin-module
    plan: 01
    provides: User.is_active + User.deleted_at Mapped columns; password_hash now Mapped[str | None]
  - phase: 43-multi-user-admin-module
    plan: 03
    provides: ('refresh_failed', 'session') in LOCKED_AUDIT_EVENTS + RefreshFailedPayload with reason='account_inactive' Literal
  - phase: 5-auth-bedrock
    provides: rotate_refresh structure (D-13 three branches); InvalidSession exception class (HYG-02 D-23-11)
provides:
  - rotate_refresh single-SELECT predicate (User.is_active=True AND User.deleted_at IS NULL) — race-tight against parallel deactivate/soft-delete
  - Forensic ('refresh_failed', 'session') audit emit with reason='account_inactive' (emit → commit → raise ordering)
  - Anti-oracle harmonisation — truly-missing refresh-row branch raises InvalidSession('invalid_session') (was InvalidAccessToken('refresh_not_found'))
  - authenticate() SELECT extended with WHERE password_hash IS NOT NULL — pending_invitation users fold into unknown-email anti-oracle bucket
  - mypy --strict clears app/modules/auth/service.py (line 155 arg-type error from 43-01 follow-up resolved)
affects:
  - 43-12 (Wave 4 test plan: test_refresh_account_inactive.py — will assert byte-identical response + bounded timing across active/deactivated/deleted/missing)
  - Phase 44 RESET-02 (password-reset-confirm reuses InvalidSession parity pattern when sessions revoked)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single-SELECT race-tight authorisation predicate (D-43-20): user-lifecycle gates live IN the SQL WHERE clause, not as a post-fetch Python branch (Pitfall 5 case 3)"
    - "Anti-oracle exception harmonisation (D-20-9 / D-43-20): all rotate_refresh failure paths whose distinction would leak via response converge on the same InvalidSession('invalid_session') shape"
    - "By-types/on-the-wire alignment (Phase 12.1 lesson): when a column drops NOT NULL, every consuming SELECT MUST add the IS NOT NULL predicate explicitly — mypy follow-up resolves at the SAME plan as the consumer-of-the-new-shape, not later"

key-files:
  modified:
    - apps/backend/app/modules/auth/service.py

key-decisions:
  - "InvalidSession chosen as the anti-oracle convergence class — `code='invalid_session'` (FE distinguishes from `code='invalid_token'`/auto-refresh). Both the truly-missing-row branch and the new account_inactive branch raise InvalidSession('invalid_session') for byte-identical response."
  - "family_reuse_detected branch (C) keeps InvalidAccessToken — different conceptual class (forensic stolen-token detection, not lifecycle gate); existing tests (test_refresh.py lines 149-150) pin code='invalid_token' for that path."
  - "Router-level missing-cookie path (InvalidAccessToken('missing_refresh_cookie') in router.py:112) unchanged — it never reaches rotate_refresh and is pinned by test_refresh_without_cookie_returns_401 (line 173)."
  - "require_user access-token path NOT modified per D-43-21 — 5-min token TTL acceptable per threat model; refresh chokepoint catches within 1 cycle."
  - "authenticate() splits target_hash assignment into explicit if/else with Python None re-check — mypy cannot follow SQL is_not(None) narrowing, so the Python guard carries the invariant and clears strict typing."

patterns-established:
  - "Pattern: when a SQL filter narrows a Mapped[T | None] column, pair the SQL predicate with an explicit Python `is not None` guard at the consumer so mypy stays green (defence-in-depth + by-types alignment)."

requirements-completed: [USERS-06]

# Metrics
duration: ~17min
completed: 2026-05-19
---

# Phase 43 Plan 07: Refresh-Token is-active Guard Summary

**rotate_refresh's user-row SELECT now requires is_active=true AND deleted_at IS NULL in a single race-tight query; on miss, emits forensic refresh_failed/account_inactive audit and raises InvalidSession('invalid_session') for byte-identical anti-oracle response with the truly-missing-row path (D-43-20).**

## Performance

- **Duration:** ~17 min
- **Started:** 2026-05-19T14:35:00Z (approx)
- **Completed:** 2026-05-19T14:52:00Z
- **Tasks:** 1 (single-task plan)
- **Files modified:** 1

## Accomplishments

- `rotate_refresh` user-row fetch upgraded from `session.get(User, row.user_id)` to a predicate-filtered `session.scalar(select(User).where(User.id == row.user_id, User.is_active.is_(True), User.deleted_at.is_(None)))` — Pitfall 5 case 3 race-tight mitigation in a SINGLE SQL statement (not a post-fetch Python branch).
- On predicate miss, the forensic `('refresh_failed', 'session')` audit row is emitted with `reason='account_inactive'`, then `session.commit()` persists the audit transaction, then `raise InvalidSession('invalid_session')` exits with the anti-oracle response shape.
- Truly-missing refresh-row branch (`row is None`) harmonised from `InvalidAccessToken('refresh_not_found')` (code=`invalid_token`) to `InvalidSession('invalid_session')` so the dashboard / response body cannot distinguish "token unknown" from "account inactive" (D-20-9 lineage). The plan-43-12 anti-oracle parity test (Wave 4) can now assert byte-identical body across (active, deactivated, deleted, missing) cases.
- `authenticate()` SELECT extended with explicit `WHERE password_hash IS NOT NULL` filter (43-01-SUMMARY follow-up) — pending_invitation users (password_hash=NULL since migration 0030) now fold into the unknown-email anti-oracle bucket via the sentinel-hash branch instead of raising a `Mapped[str | None]` mypy error at the `verify_password(password, target_hash)` callsite.
- `target_hash` assignment refactored into an explicit `if/else` with a Python `user.password_hash is not None` re-check so mypy `--strict` narrows correctly (SQL `is_not(None)` does NOT propagate to mypy's static analysis).
- `from app.core.exceptions import InvalidSession` added to the import block.
- mypy `--strict app/modules/auth/service.py` — the previously flagged `arg-type` error at line 141/155 (`Argument 2 to "verify_password" has incompatible type "str | None"; expected "str"`) is RESOLVED. 2 remaining errors are pre-existing `DEFER-41-shim` attr-defined drift on `app.modules.auth.models`, tracked for v1.7 removal (Phase 41 D-41-01/02 lineage — NOT in scope per the explicit 43-01-SUMMARY hand-off).
- ruff green on `app/modules/auth/service.py`.

## Task Commits

1. **Task 1: Modify rotate_refresh user-row SELECT + add refresh_failed audit emit + 43-01 follow-up** — `adebcba` (feat)

## Files Created/Modified

- `apps/backend/app/modules/auth/service.py` (modified) — three sub-changes in one commit:
  1. **Import** (`InvalidSession` added to `from app.core.exceptions import` line — alphabetical insertion).
  2. **`authenticate()` SELECT** (lines 137-167) — extended `select(User)` `where()` clause with `User.password_hash.is_not(None)`; `target_hash` split into explicit `if/else` with Python None re-check.
  3. **`rotate_refresh()`** (lines 386-432) — `row is None` branch raises `InvalidSession('invalid_session')`; Branch A user-row fetch replaced with predicate-filtered `session.scalar(select(User).where(...))`; on miss → `audit.emit('refresh_failed', resource_type='session', reason='account_inactive', ...)` → `await session.commit()` → `raise InvalidSession('invalid_session')`.

## Decisions Made

**Q1 — Exception class for anti-oracle convergence: InvalidSession vs InvalidAccessToken.**

Both classes return 401 but with different `code` fields (`invalid_session` vs `invalid_token`). The plan's PATTERNS.md line 559 contract is "same shape as invalid_session". Existing pre-Phase-43 behaviour for `rotate_refresh`'s `row is None` branch was `InvalidAccessToken('refresh_not_found')` (code=`invalid_token`).

**Chose:** Both the new account_inactive branch AND the existing `row is None` branch raise `InvalidSession('invalid_session')`. The class change is internal — the response body collapses to `{code: 'invalid_session', ...}` for both paths, so plan-43-12's bounded-timing+identical-body assertion can hold.

**Did NOT change:**
- `family_reuse_detected` raise (Branch C, line 539) — pinned by `test_refresh.py::test_refresh_reuse_writes_family_reuse_detected_audit_row` (line 150 asserts `code == 'invalid_token'`) and represents a distinct forensic class (stolen-token detection, NOT a lifecycle gate). The plan-43-12 anti-oracle test will deliberately exclude this path because it has its own distinct dashboard signal.
- Router-level `missing_refresh_cookie` raise (router.py:112) — pinned by `test_refresh_without_cookie_returns_401` (line 173). Never reaches rotate_refresh; the cookie-missing case is a client-error class that does not enumerate user state.

**Q2 — Why split `target_hash` assignment in authenticate()?**

The SQL filter `User.password_hash.is_not(None)` guarantees at the DB level that any returned row has a non-NULL `password_hash`. But mypy's static analysis CANNOT follow SQL predicate narrowing — `user.password_hash` is still `Mapped[str | None]` at the Python type level. Two options:

- **Option A (rejected):** `assert user.password_hash is not None` inside the conditional.
- **Option B (chosen):** Split into explicit `if user is not None and user.password_hash is not None:` — defence-in-depth (catches a hypothetical concurrent `UPDATE...SET password_hash=NULL` race that races against our SELECT) AND clears mypy without an assertion.

The Phase 12.1 lesson cited in 43-CONTEXT.md D-43-06 fourth bullet specifically warns about "verify by-types vs verify on-the-wire" alignment — Option B carries the invariant on BOTH the SQL side and the Python side.

**Q3 — Why no test added in this plan?**

Plan 43-07 is scoped tightly to the single-function modification (frontmatter `files_modified: [apps/backend/app/modules/auth/service.py]`). Test coverage for the new behaviour is the explicit deliverable of Wave 4 plan 43-12 (`test_refresh_account_inactive.py`) per the plan's success criteria: "Wave 4 test 43-12 will assert: identical body + bounded timing across (active, deactivated, deleted, missing) refresh-token cases."

## Deviations from Plan

None — plan executed exactly as written.

The plan's CRITICAL section warned about the exception-class harmonisation question. The harmonisation was applied as advised (both `row is None` and the new account_inactive raise converge on `InvalidSession('invalid_session')`), with the `family_reuse_detected` branch left untouched (different conceptual class, pinned by tests).

## Issues Encountered

**Pre-existing `app/modules/auth/test_telegram_verify_errors.py::test_verify_otp_expired_returns_410` failure on master** — verified by `git stash && pytest <test> ; git stash pop` round-trip. Failure exists on master without this plan's changes; unrelated to refresh-token logic. Out of scope per the executor's scope-boundary rule.

**Pre-existing mypy `DEFER-41-shim` attr-defined errors** at `auth/service.py:45` and `auth/telegram_service.py:45` — Phase 41 D-41-01/02 known issue. Both 43-01-SUMMARY (line 107) and 43-03-SUMMARY (line 144) document these as v1.7 cleanup items. NOT auto-fixed per scope boundary.

## Verification Evidence

**Acceptance grep counts (`apps/backend/app/modules/auth/service.py`):**

| Acceptance criterion | Expected | Actual |
|---|---|---|
| `grep -c 'User.is_active.is_(True)'` | ≥ 1 | 1 ✅ |
| `grep -c 'User.deleted_at.is_(None)'` | ≥ 1 | 1 ✅ |
| `grep -c '"refresh_failed"'` | 1 | 1 ✅ |
| `grep -c 'reason="account_inactive"'` | 1 | 1 ✅ |
| `grep -c 'D-43-20'` | ≥ 1 | 3 ✅ |
| `grep -c 'await session.get(User, row.user_id)'` | 0 | 0 ✅ |

**Inline ordering check (from plan):** emit_idx < commit_idx < raise_idx → `OK` (verified via `inspect.getsource(rotate_refresh)` walk).

**Tooling:**
- `uv run ruff check app/modules/auth/service.py` → `All checks passed!`
- `uv run mypy --strict app/modules/auth/service.py` → 0 errors in this file (2 errors in `auth/telegram_service.py` are pre-existing DEFER-41-shim, not introduced by this plan).

**Regression suite:**
- `uv run pytest tests/integration/auth/test_refresh.py -x -q` → **5 passed in 0.80s**.
- Broader auth suite + audit taxonomy + commit gate (deselecting the pre-existing telegram_verify failure) → **59 passed, 1 deselected, 1 xfailed in 7.72s**.

## Diff Snapshot (rotate_refresh body — before/after)

**Before (Phase 5 / D-13 Branch A user-row fetch, lines 387-389):**

```python
user_loaded = await session.get(User, row.user_id)
if user_loaded is None:
    raise InvalidAccessToken("user_not_found")
```

**After (Phase 43 / D-43-20, lines 392-432):**

```python
# Phase 43 D-43-20 — USERS-06 anti-oracle refresh chokepoint.
# Single SELECT race-tight against parallel deactivate / soft-delete
# (Pitfall 5 case 3). Predicate filtered IN the SQL — NOT a post-fetch
# Python branch (which would race against UPDATE...SET is_active=false).
user_loaded = await session.scalar(
    select(User).where(
        User.id == row.user_id,
        User.is_active.is_(True),
        User.deleted_at.is_(None),
    )
)
if user_loaded is None:
    # Anti-oracle: same 401 invalid_session response shape as the
    # truly-missing refresh-row branch above (D-20-9 lineage, D-43-20).
    # ... emit → commit → raise (Pitfall 2 ordering)
    await audit.emit(
        session,
        "refresh_failed",
        actor_user_id=None,
        resource_type="session",
        resource_id=None,
        audit_correlation_id=None,
        user_id=row.user_id,
        reason="account_inactive",
    )
    await session.commit()
    raise InvalidSession("invalid_session")
```

**Before (`row is None` branch, line 379):**

```python
if row is None:
    raise InvalidAccessToken("refresh_not_found")
```

**After (anti-oracle harmonised, lines 387-395):**

```python
if row is None:
    # Phase 43 D-43-20 — anti-oracle harmonisation. The truly-missing
    # refresh row and the deactivated-account branch below MUST surface
    # byte-identical 401 ``invalid_session`` bodies ...
    raise InvalidSession("invalid_session")
```

## User Setup Required

None — internal service-layer change, no external configuration.

## Threat Flags

None — Plan 43-07 adds no new network endpoints, auth paths, or trust-boundary surface. It TIGHTENS an existing trust boundary (the `/auth/refresh` chokepoint per D-43-20) and adds a forensic audit emit on an already-locked `('refresh_failed', 'session')` event pair. The refresh-token rotation contract is unchanged from the caller's perspective; only the predicate filter and the failure-path audit row are new.

## Next Phase Readiness

- **Wave 4 plan 43-12 unblocked:** `test_refresh_account_inactive.py` can now assert (a) HTTP 401 with `{code: 'invalid_session'}` body across active/deactivated/deleted/missing refresh-token cases, (b) the forensic audit row `('refresh_failed', 'session')` with `reason='account_inactive'` IS written for the deactivated/deleted cases (and NOT for the missing-row case), (c) bounded wall-clock timing parity across all four cases (existing test infra from Phase 42 EMAIL_OTP_LOGIN anti-oracle suite provides the timing harness).
- **Wave 2 → Wave 3 chokepoint pinned:** when `users/service.py:deactivate_user` (43-05 wave 2) calls `get_user_session_invalidator()(reason='deactivated')`, the user's existing refresh families are revoked AND their next /auth/refresh attempt (within the 5-min access-token window or after) is caught by THIS plan's predicate — defence-in-depth against the race where a refresh-token presentation lands between session-invalidate completion and the next access-token expiry.
- **Phase 44 RESET-02 reuse:** `password_reset_completed` flow will call the same `UserSessionInvalidator` slot with `reason='password_reset'`, and refresh attempts after that point will hit the same `is_active` chokepoint (if the operator was also deactivated) — no new code needed in Phase 44 to honour the chokepoint.

## Self-Check: PASSED

- File `apps/backend/app/modules/auth/service.py`: FOUND (modified)
- Commit `adebcba`: FOUND on master
- Acceptance grep counts: 6/6 ✅
- Inline ordering check (emit → commit → raise): PASS
- ruff: clean on auth/service.py
- mypy --strict: 0 errors in auth/service.py (2 pre-existing DEFER-41-shim in unrelated files)
- pytest tests/integration/auth/test_refresh.py: 5 passed
- broader auth suite (excl. pre-existing failure): 59 passed
- `InvalidSession` correctly imported from `app.core.exceptions`
- `await session.get(User, row.user_id)` count = 0 (old pattern fully removed)

---
*Phase: 43-multi-user-admin-module*
*Completed: 2026-05-19*
