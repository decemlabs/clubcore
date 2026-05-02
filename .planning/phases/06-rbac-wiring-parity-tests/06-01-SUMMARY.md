---
phase: 06-rbac-wiring-parity-tests
plan: 01
subsystem: auth
tags: [csrf, exceptions, rbac, fastapi, error-handling]

# Dependency graph
requires:
  - phase: 02-backend-skeleton-with-quality-tooling
    provides: AppError hierarchy + _app_error_handler in app/core/exceptions.py
provides:
  - CsrfMismatch(AppError) subclass with code='csrf_mismatch', status_code=403
  - Wire-format primitive for D-08 + D-21 CSRF validation failures
affects:
  - 06-02 (verify_csrf dependency raises CsrfMismatch)
  - 06-04 (parity tests assert distinct csrf_mismatch vs forbidden codes)
  - 09-* (Phase 9/10 frontend fetcher branches on code)
  - 10-* (admin-web CSRF retry logic)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Domain exception subclass with class-level code/status_code attributes"
    - "Reuses single @app.exception_handler(AppError) without handler changes"

key-files:
  created:
    - apps/backend/tests/unit/test_exceptions_csrf.py
  modified:
    - apps/backend/app/core/exceptions.py

key-decisions:
  - "CsrfMismatch slots between ForbiddenError and ConflictError (PATTERNS.md location)"
  - "Uses noqa: N818 to mirror InvalidAccessToken/InvalidPassword precedent (domain condition naming)"
  - "_app_error_handler unchanged — CsrfMismatch rides existing AppError handler binding"

patterns-established:
  - "New AppError subclasses get class-level code/status_code only — handler logic stays in one place"
  - "Wire-format codes are fixed string literals (no templating) for predictable frontend branching"

requirements-completed: [CSRF-02]

# Metrics
duration: 1min
completed: 2026-05-02
---

# Phase 06 Plan 01: CsrfMismatch Exception Subclass Summary

**Adds `CsrfMismatch(AppError)` to `app/core/exceptions.py` with `code="csrf_mismatch"` and `status_code=403`, locking the wire-format primitive for D-08/D-21 so Phase 6's `verify_csrf` dependency (Plan 06-02) and the future frontend fetcher (Phase 9/10) can branch on a CSRF-specific error code distinct from generic `forbidden`.**

## Performance

- **Duration:** ~1 min
- **Started:** 2026-05-02T14:19:24Z
- **Completed:** 2026-05-02T14:21:XXZ
- **Tasks:** 1 (TDD: RED + GREEN, no REFACTOR needed)
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments

- `CsrfMismatch(AppError)` subclass added at the exact slot specified in PATTERNS.md — between `ForbiddenError` and `ConflictError`.
- Five unit tests cover: importability, locked `code` literal, locked `status_code=403`, `AppError` subclass relationship, `fields` default to `None`.
- `_app_error_handler` was NOT modified — the new class rides the existing `@app.exception_handler(AppError)` binding unchanged.
- All quality gates green: ruff, mypy strict, import-linter (3 contracts kept), pytest 5/5.

## Task Commits

1. **Task 1 RED: failing tests for CsrfMismatch** — `52d43da` (test)
2. **Task 1 GREEN: CsrfMismatch(AppError) class** — `723e7a7` (feat)

## Files Created/Modified

- `apps/backend/app/core/exceptions.py` — Added `CsrfMismatch(AppError)` class (14 lines, between line 28 `ForbiddenError` close and line 44 `ConflictError`); `_app_error_handler` untouched.
- `apps/backend/tests/unit/test_exceptions_csrf.py` — New test file, 5 plain `def test_*` cases mirroring `test_permissions.py` style (no async).

## Slot Confirmation

The class occupies lines 29–40 in `app/core/exceptions.py`:

- Line 24–26: `ForbiddenError` (preceding sibling)
- Line 29: `class CsrfMismatch(AppError):  # noqa: N818`
- Line 39–40: `code = "csrf_mismatch"` / `status_code = 403`
- Line 43: `class ConflictError(AppError):` (following sibling)

`_app_error_handler` (lines 67–79 originally → now 79–91 after insertion) was NOT modified — confirmed by `grep -n "_app_error_handler"` showing identical body.

## Test File

- Path: `apps/backend/tests/unit/test_exceptions_csrf.py`
- Test count: **5** (all passing)
  1. `test_csrf_mismatch_is_importable`
  2. `test_csrf_mismatch_code_is_locked`
  3. `test_csrf_mismatch_status_code_is_403`
  4. `test_csrf_mismatch_is_app_error_subclass`
  5. `test_csrf_mismatch_fields_default_to_none`

## Decisions Made

None new — followed plan as specified. Plan-locked decisions (D-08, D-21) were already laid down in Phase 6 context and are now realized in code.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## Acceptance Criteria Verification

- `grep "class CsrfMismatch(AppError):" apps/backend/app/core/exceptions.py` → 1 hit (line 29)
- `grep -E 'code\s*=\s*"csrf_mismatch"' apps/backend/app/core/exceptions.py` → 1 hit (line 39)
- `grep -E 'status_code\s*=\s*403' apps/backend/app/core/exceptions.py` → 2 hits (line 26 ForbiddenError, line 40 CsrfMismatch)
- `grep -c "class CsrfMismatch" apps/backend/tests/unit/test_exceptions_csrf.py` → 0 (test imports, never redefines)
- `uv run python -c "from app.core.exceptions import CsrfMismatch; print(CsrfMismatch.code, CsrfMismatch.status_code)"` → `csrf_mismatch 403`
- `uv run pytest tests/unit/test_exceptions_csrf.py -x` → 5 passed
- `uv run ruff check` → All checks passed
- `uv run mypy app/core/exceptions.py` → Success: no issues found
- `uv run lint-imports` → 3 contracts kept (no `core ⊥ modules` regression)

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 06-02 can now `from app.core.exceptions import CsrfMismatch` and raise it from `verify_csrf` dependency.
- Plan 06-04 parity tests can assert `code: "csrf_mismatch"` is distinct from `code: "forbidden"`.
- Phase 9/10 frontend fetcher has the locked wire-format contract for CSRF-specific retry logic.

## Self-Check: PASSED

- FOUND: apps/backend/app/core/exceptions.py (CsrfMismatch class present at line 29)
- FOUND: apps/backend/tests/unit/test_exceptions_csrf.py (5 tests)
- FOUND: 52d43da (test commit)
- FOUND: 723e7a7 (feat commit)

---
*Phase: 06-rbac-wiring-parity-tests*
*Completed: 2026-05-02*
