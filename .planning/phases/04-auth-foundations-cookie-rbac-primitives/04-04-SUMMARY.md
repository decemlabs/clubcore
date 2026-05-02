---
phase: 04-auth-foundations-cookie-rbac-primitives
plan: "04"
subsystem: auth
tags: [rbac, permissions, exceptions, strenums, python]

# Dependency graph
requires: []
provides:
  - "Role/Action/Resource StrEnums with locked string values mirroring frontend registry.ts"
  - "OWNER_ONLY frozenset of 9 (Action, Resource) tuples mirroring frontend can.ts"
  - "can(role, action, resource) function with owner short-circuit + reception OWNER_ONLY blacklist"
  - "InvalidAccessToken (code=invalid_token, 401), InvalidPassword (code=invalid_credentials, 401), RateLimited (code=rate_limited, 429) AppError subclasses"
affects:
  - "04-07 (security.py imports Role + raises InvalidAccessToken/InvalidPassword)"
  - "04-08 (auth dependency imports can + OWNER_ONLY)"
  - "04-09 (unit tests for permissions.py)"
  - "Phase 5 (auth endpoints raise InvalidPassword/RateLimited)"
  - "Phase 6 TEST-06 (parity test reads OWNER_ONLY frozenset vs frontend can.ts)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "StrEnum for locked domain enumerations (stdlib only, no pydantic/FastAPI dependency in core utilities)"
    - "frozenset[tuple[Enum, Enum]] for O(1) membership check in authorization hot-path"
    - "noqa: N818 on exception class lines where name is a locked API contract (not a style choice)"

key-files:
  created:
    - "apps/backend/app/core/permissions.py"
  modified:
    - "apps/backend/app/core/exceptions.py"

key-decisions:
  - "OWNER_ONLY modeled as frozenset[tuple[Action, Resource]] for O(1) membership + parity-set equality in Phase 6 TEST-06"
  - "Exception class names (InvalidAccessToken, InvalidPassword, RateLimited) are locked API contracts; noqa: N818 added to satisfy ruff pep8-naming while preserving the contract names"
  - "InvalidPassword docstring mentions Phase 5 AUTH-EP-02 timing equivalence (sentinel hash for user-not-found) to prevent enumeration — noted at definition site for future implementors"
  - "permissions.py imports only stdlib StrEnum — zero app-local or third-party imports, trivially satisfying import-linter core-not-depend-on-modules"

patterns-established:
  - "Pattern: StrEnum values match frontend TypeScript string literals byte-for-byte (verified by parity test in Phase 6)"
  - "Pattern: AppError subclasses use class-level code + status_code overrides only; never override __init__"

requirements-completed: [RBAC-01]

# Metrics
duration: 3min
completed: "2026-05-02"
---

# Phase 04 Plan 04: RBAC Primitives + Auth Exception Subclasses Summary

**Role/Action/Resource StrEnums + 9-entry OWNER_ONLY frozenset mirroring apps/admin-web can.ts + three AppError subclasses (InvalidAccessToken 401, InvalidPassword 401, RateLimited 429)**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-02T06:38:49Z
- **Completed:** 2026-05-02T06:41:01Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `app/core/permissions.py` with 2 Role, 5 Action, 11 Resource StrEnum members; OWNER_ONLY frozenset with exactly 9 tuples; can() function semantically identical to frontend can.ts
- Extended `app/core/exceptions.py` with InvalidAccessToken (401), InvalidPassword (401), and RateLimited (429) as AppError subclasses; all existing classes and register_exception_handlers preserved unchanged
- All quality gates passed: mypy strict, ruff, lint-imports (3 contracts KEPT) across both files

## Task Commits

1. **Task 1: Create app/core/permissions.py** - `143678e` (feat)
2. **Task 2: Append exception subclasses to exceptions.py** - `c119682` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified

- `apps/backend/app/core/permissions.py` — NEW: Role/Action/Resource StrEnums + OWNER_ONLY frozenset (9 entries) + can() function; pure stdlib only
- `apps/backend/app/core/exceptions.py` — EXTENDED: appended InvalidAccessToken, InvalidPassword, RateLimited AppError subclasses (lines 39-64)

## Resource String Values (11)

`dashboard`, `clients`, `schedule`, `staff`, `finance`, `reports`, `payroll`, `compensation`, `templates`, `settings`, `owner-area`

Note: `Resource.OWNER_AREA` Python member name uses underscore; string value `"owner-area"` contains hyphen to match frontend.

## Action String Values (5)

`view`, `create`, `edit`, `delete`, `refund`

## OWNER_ONLY Tuples (9)

| Action | Resource |
|--------|----------|
| view | finance |
| view | reports |
| view | payroll |
| view | compensation |
| view | settings |
| view | owner-area |
| edit | templates |
| delete | clients |
| refund | finance |

## Exception Subclasses (3 new)

| Class | code | status_code |
|-------|------|-------------|
| InvalidAccessToken | invalid_token | 401 |
| InvalidPassword | invalid_credentials | 401 |
| RateLimited | rate_limited | 429 |

## Decisions Made

- `OWNER_ONLY` modeled as `frozenset[tuple[Action, Resource]]` — O(1) membership in `can()` + enables set-equality assertion in Phase 6 TEST-06 parity test
- Exception class names are locked API contracts (Plan 04-07 `raise InvalidAccessToken(...)`, Plan 04-07 `raise InvalidPassword(...)`); added `# noqa: N818` to suppress ruff pep8-naming rule (would want `...Error` suffix) without renaming the exported symbols
- Docstring for `InvalidPassword` includes Phase 5 AUTH-EP-02 note about timing equivalence / user enumeration masking — placed at the definition site so future implementors see the context before writing the call sites

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added noqa: N818 and fixed E501 docstring line in exceptions.py**
- **Found during:** Task 2 (ruff check after editing exceptions.py)
- **Issue:** ruff `N818` fires on exception class names not ending in `Error`; `E501` fired on the 103-char `InvalidPassword` docstring line. Plan specified exact class names as locked API contracts and did not mention these lint suppressions.
- **Fix:** Added `# noqa: N818` to all three class definition lines; split the InvalidPassword docstring into two shorter lines.
- **Files modified:** apps/backend/app/core/exceptions.py
- **Verification:** `uv run ruff check app/core/exceptions.py` exits 0; runtime assertions still pass
- **Committed in:** c119682 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - linting fix for locked contract names)
**Impact on plan:** Trivial cosmetic fix. No behavior change, no scope creep. All acceptance criteria met.

## Issues Encountered

None beyond the ruff noqa fix described above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 04-07 (security helpers) can now import `Role` from `app.core.permissions` and raise `InvalidAccessToken` / `InvalidPassword` from `app.core.exceptions`
- Plan 04-08 (auth dependencies) can import `can`, `OWNER_ONLY`, `Role`, `Action`, `Resource`
- Plan 04-09 (unit tests) can parametrize over `OWNER_ONLY` entries and `can()` behavior
- Phase 6 TEST-06 parity test can extract OWNER_ONLY as a set and compare against the frontend can.ts array

---
*Phase: 04-auth-foundations-cookie-rbac-primitives*
*Completed: 2026-05-02*
