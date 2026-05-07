---
phase: 15-foundations-rbac-audit-taxonomy-helper-hoisting
plan: 02
subsystem: infra
tags: [core, sql, escape-like, helper-hoist, importlinter, refactor, v1.2]

# Dependency graph
requires:
  - phase: 14-pii-hardening
    provides: "_escape_like_pattern in clients/repository.py (CR-01 closure body)"
provides:
  - "app/core/sql.py:escape_like_pattern — module-public ILIKE escape helper, single source for all modules"
  - "Direct unit test coverage independent of clients module (tests/unit/test_core_sql.py, 6 cases)"
  - "Clients repository now imports from core.sql; underscore-prefixed local helper removed"
affects:
  - 16-membership-plans
  - 19-visits
  - any future module that needs Postgres ILIKE search over user-supplied input

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Leaf core helpers: pure-function modules under app/core/* with no app.* imports — trivially satisfy `core ⊥ modules` import-linter contract"
    - "Aliased import in test bodies (`from app.core.sql import escape_like_pattern as _escape_like_pattern`) — preserves existing test syntax without behavioural drift during helper hoisting"

key-files:
  created:
    - apps/backend/app/core/sql.py
    - apps/backend/tests/unit/test_core_sql.py
  modified:
    - apps/backend/app/modules/clients/repository.py
    - apps/backend/tests/unit/clients/test_repository_escape.py
    - apps/backend/tests/integration/clients/test_search.py

key-decisions:
  - "Verbatim hoist — function body identical to v1.1 helper; only the leading underscore was dropped to make it module-public."
  - "Aliased import in regression test (`as _escape_like_pattern`) preserves test bodies exactly, so the CR-01 suite remains a pure regression check on the relocated helper."
  - "Integration test docstring updated to use the new public name (Rule 3) — required to fully retire the old identifier from grep visibility, except for the one deliberate alias rebinding inside the regression test."

patterns-established:
  - "INFRA-10 hoisting pattern: shared SQL/string helpers live in `app/core/sql.py` (or sibling leaf modules); modules import from `app.core.*` only — never from each other."
  - "TDD for verbatim hoists: write the direct unit test first (RED via missing module import), then create the leaf module (GREEN), keeping the body byte-equivalent to the original."

requirements-completed: [INFRA-10, TESTS-11]

# Metrics
duration: 4min
completed: 2026-05-07
---

# Phase 15 Plan 02: Hoist escape_like_pattern → app/core/sql Summary

**Hoisted the LIKE-escape helper from clients/repository.py into the new leaf module app/core/sql.py with a verbatim function body, dropping the leading underscore to make it module-public, so Phase 16 (memberships) and Phase 19 (visits) can reuse it without breaching the `modules-independent` import-linter contract.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-07T10:41:39Z
- **Completed:** 2026-05-07T10:45:28Z
- **Tasks:** 2 / 2
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments

- `app/core/sql.py` created with module-public `escape_like_pattern(value, *, escape_like=True)` — verbatim body from the v1.1 CR-01 closure helper.
- Direct unit test suite (`tests/unit/test_core_sql.py`, 6 cases) covers the helper independently of any module: order check, percent, underscore, backslash, mixed metacharacters, and `escape_like=False` opt-out.
- `clients/repository.py` no longer defines the helper; it imports from `app.core.sql` and uses the public name at both callsites.
- CR-01 regression suite (`tests/unit/clients/test_repository_escape.py`) re-routed to the new import path via aliased import — test bodies untouched; all 6 regression cases still green.
- import-linter contracts (`core ⊥ modules`, `modules-independent`, `integrations ⊥ modules`) all KEPT.
- `openapi.json` byte-stable (zero contract drift — pure refactor, as designed).

## Task Commits

Each task was committed atomically (with `--no-verify`, per parallel-executor protocol):

1. **Task 1: Create app/core/sql.py with verbatim escape_like_pattern (TDD)** — `db00d94` (feat)
   RED: `tests/unit/test_core_sql.py` failed with `ModuleNotFoundError: No module named 'app.core.sql'`.
   GREEN: created `app/core/sql.py` with the verbatim hoisted body; all 6 unit tests passed.
   (Combined feat commit — single logical hoist; the test+impl belong to the same atomic unit and there is no committable RED state to gate further work on.)

2. **Task 2: Swap clients repo + tests to core.sql.escape_like_pattern** — `f87e03b` (refactor)
   - Added `from app.core.sql import escape_like_pattern` import in `clients/repository.py`.
   - Removed the local `_escape_like_pattern` definition (28-line function body).
   - Updated both callsites (lower-name ILIKE branch + phone ILIKE branch).
   - Updated repository docstring reference to use the new module-public name.
   - Aliased import in `tests/unit/clients/test_repository_escape.py` (`escape_like_pattern as _escape_like_pattern`) — test bodies untouched.
   - Updated docstring references in `tests/integration/clients/test_search.py` (Rule 3 — see Deviations).

## Files Created/Modified

- `apps/backend/app/core/sql.py` — **created**. Leaf module, no `app.*` imports, defines `escape_like_pattern`.
- `apps/backend/tests/unit/test_core_sql.py` — **created**. 6 direct unit tests (mirror peer style).
- `apps/backend/app/modules/clients/repository.py` — **modified**. Import added, local def removed, 2 callsites + 1 docstring renamed.
- `apps/backend/tests/unit/clients/test_repository_escape.py` — **modified**. Single-line import swap (aliased) — preserves all test bodies as the plan instructed.
- `apps/backend/tests/integration/clients/test_search.py` — **modified**. Two docstring references renamed (no executable code change).

## Verification

- `uv run pytest tests/unit/test_core_sql.py` → 6 passed (Task 1 GREEN).
- `uv run pytest tests/unit/clients/test_repository_escape.py tests/unit/test_core_sql.py tests/unit/clients/` → 12 passed (Task 2 regression).
- `uv run pytest tests/integration/clients/test_search.py` → 5 skipped (Postgres not running in this worktree env; behaviour unchanged because the function body is verbatim and unit-level CR-01 regression suite is green).
- `uv run ruff check .` → All checks passed.
- `uv run mypy app/core/sql.py app/modules/clients/repository.py` → no issues.
- `uv run lint-imports` → 3 contracts KEPT (`core ⊥ modules`, `modules-independent`, `integrations ⊥ modules`).
- `git diff --exit-code apps/backend/openapi.json` → byte-stable.

## Decisions Made

- **Verbatim body, public name.** The plan mandated zero behaviour change. The function body is byte-equivalent to the original (`replace("\\", "\\\\")` then `%` then `_`); only the identifier was renamed (no underscore prefix).
- **Aliased import preserves regression test bodies.** Per plan §Task 2/B, the existing test file uses `from app.core.sql import escape_like_pattern as _escape_like_pattern`. This keeps test bodies as the literal regression check from v1.1 and avoids any behavioural drift introduced by reformatting tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Updated docstring references in `tests/integration/clients/test_search.py`**
- **Found during:** Task 2 (pre-edit grep gate).
- **Issue:** The plan's W2 acceptance criterion requires `grep -rn '_escape_like_pattern' apps/backend/ | wc -l == 0`, but `tests/integration/clients/test_search.py` (lines 3 and 70) carried two docstring/comment references to the old underscore-prefixed name. The plan's `<read_first>` block listed only repository.py and test_repository_escape.py as in-scope.
- **Fix:** Renamed the two docstring references to `escape_like_pattern` (with a parenthetical "Phase 15: hoisted to `app.core.sql`" note on the module docstring). No executable code touched in test_search.py.
- **Files modified:** `apps/backend/tests/integration/clients/test_search.py`.
- **Verification:** `uv run ruff check tests/integration/clients/test_search.py` clean. Integration tests skip cleanly (Postgres unavailable in worktree env, but behaviour is intrinsically unchanged because the function body is verbatim).
- **Committed in:** `f87e03b` (Task 2 commit).

### Plan Spec vs. Reality Notes (no code action; documented for future planners)

- **W2 strict gate is not literally achievable.** The acceptance criterion `grep -rn '_escape_like_pattern' apps/backend/ | wc -l == 0` is mathematically incompatible with the explicit instruction (Task 2/B) to use the aliased form `from app.core.sql import escape_like_pattern as _escape_like_pattern` and to NOT change any test body / docstring / fixture / `def test_…` line. After the migration, 10 hits remain — all inside `tests/unit/clients/test_repository_escape.py`, all referring to the aliased local name. The intent of the W2 gate is clearly "the underscore-prefixed name is gone as a definition/export" (which is verified — repository.py has 0 hits and there is no other definition site). Resolved in favour of the explicit instruction. Future planners: if a strict-zero-hit grep gate is desired, the test bodies must also be renamed in the same plan.
- **`grep -c "escape_like_pattern" apps/backend/app/modules/clients/repository.py` == 4, plan said 3.** The 4th hit is the docstring reference (`Search input ``query.q`` is routed through ``escape_like_pattern`` …`) which I updated in place to reflect the new name. The plan's count of 3 (1 import + 2 callsites) didn't anticipate the in-place docstring rename. Keeping the rename is more correct (consistency).

---

**Total deviations:** 1 auto-fixed (Rule 3 — blocking acceptance criterion) + 2 documented plan/reality notes (no code action).
**Impact on plan:** Hoist completed exactly as specified. CR-01 regression suite still green. Zero behaviour change. No scope creep.

## Issues Encountered

- Integration tests for `tests/integration/clients/test_search.py` skip in this worktree because Postgres is not running. Acceptable: function body is verbatim, unit-level CR-01 regression suite passes, and the plan's main guarantee is "pure refactor — zero behaviour change", which is verified at compile time (mypy / ruff), at static-architecture time (lint-imports), and at unit-test time (12 unit tests green from the new import path).

## TDD Gate Compliance

- **RED:** Demonstrated for Task 1 (`test_core_sql.py` failed with `ModuleNotFoundError` before `app/core/sql.py` was created — captured in agent transcript).
- **GREEN:** `app/core/sql.py` added; `pytest tests/unit/test_core_sql.py` → 6 passed.
- **Commit pattern note:** Task 1 was committed as a single `feat(15-02): hoist escape_like_pattern …` commit (test + impl together) rather than separate `test(...)` + `feat(...)` commits. Rationale: the helper is a 5-line pure function and the test file is co-creation context; gating on a separate `test(...)` commit produces no incremental verification value (the test cannot pass and was never meant to pass without the module). The RED state is preserved in the agent transcript and the GREEN state in the commit. If strict gate-commit auditing is required for future hoists, the planner should explicitly call for two commits.

## Threat Flags

None — the hoist does not introduce any new attack surface. The threat model in the plan (T-15-05/06/07) is fully mitigated:

- **T-15-05 (wildcard injection):** The function body is byte-equivalent; the 6 unit-test cases (including the order-check mixed metacharacter case) verify behaviour at the new home.
- **T-15-06 (drift between hoisted helper and callers):** Acceptance grep gates were enforced (0 hits of the underscore name in repository.py, 1 import + 1 docstring + 2 callsites of the public name).
- **T-15-07 (`core ⊥ modules` violation):** The new file has zero `app.*` imports (`grep -c "from app\." apps/backend/app/core/sql.py` == 0); `lint-imports` confirms all 3 contracts KEPT.

## User Setup Required

None — pure code refactor; no environment, secret, or external service changes.

## Next Phase Readiness

- **Phase 16 (membership_plans):** Can now `from app.core.sql import escape_like_pattern` directly inside any future `app/modules/memberships/repository.py` ILIKE branch — no `modules-independent` violation.
- **Phase 19 (visits):** Same — `from app.core.sql import escape_like_pattern` is the canonical path.
- **Phase 15 plans 03/04/05:** Independent of this hoist (RBAC matrix, audit taxonomy, …); no shared files. Wave 1 parallel safety preserved.

## Self-Check: PASSED

All files claimed to be created/modified exist on disk:
- `apps/backend/app/core/sql.py` ✓
- `apps/backend/tests/unit/test_core_sql.py` ✓
- `apps/backend/app/modules/clients/repository.py` ✓
- `apps/backend/tests/unit/clients/test_repository_escape.py` ✓
- `apps/backend/tests/integration/clients/test_search.py` ✓
- `.planning/phases/15-foundations-rbac-audit-taxonomy-helper-hoisting/15-02-SUMMARY.md` ✓

All claimed task commits exist in git log:
- `db00d94` (Task 1) ✓
- `f87e03b` (Task 2) ✓

---
*Phase: 15-foundations-rbac-audit-taxonomy-helper-hoisting*
*Plan: 02*
*Completed: 2026-05-07*
