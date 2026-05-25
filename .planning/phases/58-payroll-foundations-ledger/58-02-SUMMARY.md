---
phase: 58-payroll-foundations-ledger
plan: 02
subsystem: infra
tags: [import-linter, payroll, module-registration, constants, architecture]

# Dependency graph
requires:
  - phase: 54-reports-foundation
    provides: "INFRA-15 preemptive module registration discipline (D-54-09 reports precedent)"
provides:
  - "app.modules.payroll registered in modules-independent contract (INFRA-15 / D-58-18)"
  - "payroll/__init__.py module marker"
  - "payroll/constants.py with locally-pinned subject-kind literal + 3 snake_case error codes"
affects:
  - 58-03-PLAN (payroll models — will import from payroll/constants.py)
  - 58-04-PLAN (payroll service/router — will import from payroll/constants.py)
  - any future payroll callsite plans

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "INFRA-15 preemptive module registration before code lands (mirrors D-54-09 / INFRA-40 / D-51-08)"
    - "Locally-pinned cross-module literal with explanatory docstring (mirrors pt_packages/constants.py D-33)"

key-files:
  created:
    - apps/backend/app/modules/payroll/__init__.py
    - apps/backend/app/modules/payroll/constants.py
  modified:
    - apps/backend/.importlinter

key-decisions:
  - "D-58-18 confirmed: ZERO new ignore_imports edges — payroll cross-module reads go via raw SQL text(), cross-module write goes via PayrollClawbackRecorder Protocol slot"
  - "D-58-19 confirmed: PAYMENT_SUBJECT_KIND_PT_PACKAGE locally pinned to 'pt_package' (no import of payments.constants — modules-independent contract forbids it)"

patterns-established:
  - "Preemptive module registration comment block shape: Phase X INFRA-Y / D-X-N reason + raw SQL discipline + Protocol slot discipline"

requirements-completed: [PAY-01, PAY-02, PAY-03, PAY-04, PAY-05, PAY-06]

# Metrics
duration: 15min
completed: 2026-05-25
---

# Phase 58 Plan 02: Payroll Module INFRA-15 Registration + Constants Summary

**app.modules.payroll registered as 17th modules-independent entry with locally-pinned 'pt_package' literal and 3 snake_case error codes — zero new ignore_imports edges (D-58-18 / INFRA-15)**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-05-25T00:00:00Z
- **Completed:** 2026-05-25T00:00:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Registered `app.modules.payroll` in `[importlinter:contract:modules-independent]` with Phase 58 INFRA-15 / D-58-18 comment block explaining zero-ignore_imports discipline
- Created `app/modules/payroll/__init__.py` matching payments/__init__.py pattern with Phase 58 docstring
- Created `app/modules/payroll/constants.py` with locally-pinned `PAYMENT_SUBJECT_KIND_PT_PACKAGE = "pt_package"` + 3 snake_case error codes
- All quality gates green: ruff + mypy --strict + lint-imports (3 contracts kept, 0 broken)

## Task Commits

Each task was committed atomically:

1. **Task 1: Register app.modules.payroll in .importlinter modules-independent** - `e938c0a` (feat)
2. **Task 2: Create payroll module scaffold + constants.py** - `893bf87` (feat)

## Total modules in modules-independent contract after plan: 17

The payroll module was inserted alphabetically between `app.modules.users` and `app.modules.reports` — now the 16th entry (reports is 17th). Zero new `ignore_imports` edges added.

## Files Created/Modified
- `apps/backend/.importlinter` - Added `app.modules.payroll` + Phase 58 INFRA-15 comment block to modules-independent list
- `apps/backend/app/modules/payroll/__init__.py` - Module marker (mirrors payments/__init__.py shape)
- `apps/backend/app/modules/payroll/constants.py` - Subject-kind literal + 3 error codes with cross-module pinning rationale

## Decisions Made
- `app.modules.payroll` inserted before `app.modules.reports` in alphabetical order (matches D-54-09 pattern of alphabetical insertion)
- Module docstring explains INFRA-15 preemption + D-58-19 locally-pinned literal + D-58-20 Protocol slot cross-module write

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

**Worktree path safety (#3099):** Initial file edits targeted main repo path (`/Users/andre/Workspace/Development/clubcore/`) instead of the worktree path (`/Users/andre/Workspace/Development/clubcore/.claude/worktrees/agent-ae8012f453234df74/`). Caught before commit by `git status` showing no changes. All files were written to the correct worktree paths.

## Next Phase Readiness
- `app.modules.payroll` is now a first-class module from the architecture's perspective — import-linter will catch any cross-module drift immediately
- `payroll/constants.py` is ready for import by payroll/models.py, payroll/service.py, and future payroll plans
- Phase 58 Plan 03 (Alembic migration + ORM models) can proceed immediately

---
*Phase: 58-payroll-foundations-ledger*
*Completed: 2026-05-25*
