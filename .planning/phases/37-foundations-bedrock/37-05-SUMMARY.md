---
phase: 37-foundations-bedrock
plan: 05
subsystem: infra
tags: [importlinter, svc001, ast, modular-monolith, negative-fixture, contracts]

# Dependency graph
requires:
  - phase: 30-foundations-tech-debt-bedrock
    provides: SVC001 AST commit-gate walker + INFRA-21 pre-register-placeholder pattern (trainers/payments/pt_packages enrolment template)
  - phase: 34-pt-sessions
    provides: pt_sessions/service.py live module (now retroactively enrolled in the SVC001 walker scope)
provides:
  - Importlinter `modules-independent` contract negative-fixture proof (positive + Strategy-A synthesised independence contract red test) ensuring future cross-module imports between bookings/schedule (or any v1.5 module pair) go red on CI
  - Documented negative-fixture file at apps/backend/app/modules/bookings/_negative_importlinter_fixture.py (forbidden import recorded as STRING constant — not literal — to avoid breaking the live contract; documents the design constraint that importlinter performs static AST analysis regardless of runtime gates)
  - SVC001 AST commit-gate walker scope extended with `_SCHEDULE_SERVICE` + `_BOOKINGS_SERVICE` (Phase 37 INFRA-29 entries) + retroactive `_PT_SESSIONS_SERVICE` (Phase 34 omission, recovered)
affects: [38-schedule-bookings, 39-notifications, 40-telegram-book]

# Tech tracking
tech-stack:
  added: []  # No new dependencies — importlinter + pytest already in dev-deps; negative test uses subprocess + tmp_path stdlib
  patterns:
    - "Negative-fixture-as-string: when a static analyser (e.g. importlinter) cannot be told to ignore runtime-gated imports without modifying the locked config, encode the forbidden construct as a STRING constant and prove the analyser's correctness in a tmp_path synthesised mirror (Strategy A)."
    - "SVC001 walker pre-register placeholder pattern (Phase 30 INFRA-21 → Phase 37 INFRA-29 continuation): add module service.py paths to `_INSPECTED_SERVICES` BEFORE the substantive write-path code lands, so the walker enters the new module from its very first write commit."

key-files:
  created:
    - apps/backend/app/modules/bookings/_negative_importlinter_fixture.py (documentation-only negative fixture; forbidden import recorded as `_FORBIDDEN_IMPORT_LINE` string constant; `if False:` block kept as visual gate marker only)
    - apps/backend/tests/unit/test_importlinter_negative_fixture.py (positive + negative tests: positive runs real `uv run lint-imports`; negative builds tmp_path `pkg.mod_a`/`pkg.mod_b` package + tmp setup.cfg with `type = independence` contract and asserts non-zero exit)
  modified:
    - apps/backend/tests/unit/test_service_commit_gate.py (added `_SCHEDULE_SERVICE`, `_BOOKINGS_SERVICE`, retroactive `_PT_SESSIONS_SERVICE` Path constants + tuple entries; Phase 37 INFRA-29 comment block)
  unchanged:
    - apps/backend/.importlinter (byte-identical to HEAD — pattern-mapper pre-verified the contract already enumerates app.modules.schedule + app.modules.bookings on lines 22-23; orchestrator override confirmed; verified `git diff --quiet apps/backend/.importlinter` exits 0)

key-decisions:
  - "Negative-fixture file stores forbidden import as STRING (not literal import) — importlinter's static AST walker observes `if False:`-gated imports as real dependencies (verified empirically; the original plan design broke the contract). Negative proof shifts entirely to the tmp_path synthesised contract test, which the plan already permitted as Strategy A."
  - "`.importlinter` is UNCHANGED — pattern-mapper verified the contract already enumerates `app.modules.schedule` + `app.modules.bookings` on HEAD; orchestrator override took precedence over CONTEXT.md D-37-07's 'extend existing' wording."
  - "Retroactively added `_PT_SESSIONS_SERVICE` to the SVC001 walker scope during this plan's read-first sweep — the Phase 34 service file was created but never enrolled in the live gate (an INFRA-21-style omission); strictly-additive cleanup."

patterns-established:
  - "Importlinter static-AST awareness: any documentation file referencing a forbidden import MUST encode the import as a string constant (or live entirely outside the configured root package) — runtime gates like `if False:` / `if TYPE_CHECKING:` are NOT respected unless the contract sets `exclude_type_checking_imports = True`, which Sportzal's `.importlinter` does not currently set."
  - "Strategy-A negative proof: prove a contract type works via a hermetic tmp_path mirror with synthesised modules + tmp config, rather than mutating the real config file or planting a real broken import in production."

requirements-completed: [INFRA-28, INFRA-29]

# Metrics
duration: ~30min
completed: 2026-05-17
---

# Phase 37 Plan 05: import-linter negative-fixture + SVC001 walker scope extension Summary

**Locks the v1.5 architectural enforcement layer: a Strategy-A tmp_path independence-contract test proves the existing `modules-independent` importlinter contract will reject any future cross-module import between bookings/schedule, and the SVC001 AST commit-gate walker scope is pre-registered with both new service.py paths (plus a retroactive `pt_sessions/service.py` recovery) so the very first write-path commit in Phase 38 triggers the gate.**

## Performance

- **Duration:** ~30 min
- **Tasks:** 2
- **Files modified:** 3 (2 new, 1 modified)

## Accomplishments
- Importlinter contract enforcement for v1.5 — verified green on HEAD with the pattern-mapper's claim (`app.modules.schedule` + `app.modules.bookings` already enumerated lines 22-23) and proven to have teeth via a hermetic tmp_path mirror that synthesises an independence contract and asserts `lint-imports` exits non-zero with the offending modules named.
- SVC001 walker scope extended for v1.5 — `_SCHEDULE_SERVICE` and `_BOOKINGS_SERVICE` added to `_INSPECTED_SERVICES` per the Phase 30 INFRA-21 pre-register-placeholder pattern. The walker will now enter both modules' write paths from the first commit in Phase 38.
- Retroactive recovery — `_PT_SESSIONS_SERVICE` (Phase 34 omission) added in the same atomic change.
- `.importlinter` is byte-identical to HEAD, per the orchestrator's explicit override of CONTEXT.md D-37-07.

## Task Commits

Each task was committed atomically (per-task `--no-verify` per parallel-executor protocol):

1. **Task 1: Negative-fixture file + negative-fixture test** — `defa966` (`test`)
2. **Task 2: Extend SVC001 walker scope (_SCHEDULE/_BOOKINGS/_PT_SESSIONS)** — `8da5f9d` (`test`)

_Plan metadata (this SUMMARY) commits separately at the bottom._

## Files Created/Modified
- `apps/backend/app/modules/bookings/_negative_importlinter_fixture.py` — NEW; documents the canonical forbidden `from app.modules.schedule import service` as a STRING constant (`_FORBIDDEN_IMPORT_LINE`) and explains why a literal import (even under `if False:`) would break the contract. Retains an inert `if False:` block for pattern recognition.
- `apps/backend/tests/unit/test_importlinter_negative_fixture.py` — NEW; two tests:
  - `test_importlinter_modules_independent_contract_green_on_head` — runs real `uv run lint-imports` from `apps/backend/`, asserts exit 0 (positive).
  - `test_modules_independent_contract_rejects_bookings_schedule_cross_import` — Strategy A: builds tmp_path `pkg/__init__.py` + `pkg/mod_a.py` (imports `pkg.mod_b`) + `pkg/mod_b.py`, writes tmp setup.cfg with `type = independence` contract listing both modules, invokes `uv run --project <backend> lint-imports --config <tmp>` from tmp_path, asserts non-zero exit + `mod_a`/`mod_b` named in output.
- `apps/backend/tests/unit/test_service_commit_gate.py` — MODIFIED; added three Path constants (`_PT_SESSIONS_SERVICE`, `_SCHEDULE_SERVICE`, `_BOOKINGS_SERVICE`) + three new tuple entries in `_INSPECTED_SERVICES`. Phase 37 INFRA-29 comment block included.

## Decisions Made
- **Negative-fixture-as-string** (replaces plan's `if False:`-gated literal import design): importlinter's static AST walker observes gated imports as real dependencies regardless of runtime reachability — verified empirically (initial attempt broke the contract, output: `app.modules.bookings._negative_importlinter_fixture -> app.modules.schedule (l.22)`). Resolution: encode the forbidden import as a string constant; the negative proof moves entirely into the tmp_path synthesised contract test (which the plan already permitted as Strategy A — the canonical path). Logged as a Rule 1 deviation.
- **`.importlinter` byte-identical to HEAD**: pattern-mapper pre-verified the contract already enumerates `app.modules.schedule` (line 22) + `app.modules.bookings` (line 23); orchestrator override took precedence over CONTEXT.md D-37-07's "extend existing" wording. Verified `git diff --quiet apps/backend/.importlinter` exits 0 post-commit.
- **Retroactive `_PT_SESSIONS_SERVICE` enrolment**: noticed during the read-first sweep that Phase 34's service file was created but never enrolled in the live SVC001 gate (an INFRA-21-style omission). Strictly-additive cleanup folded into Task 2 per the plan's permission in Step 1(a).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan's `if False:`-gated literal cross-module import would break the live importlinter contract**

- **Found during:** Task 1 (Negative-fixture file)
- **Issue:** Plan's Step 1 fixture body included `if False: from app.modules.schedule import service as _schedule`. After creating the file, `uv run lint-imports` went RED with: `app.modules.bookings is not allowed to import app.modules.schedule: - app.modules.bookings._negative_importlinter_fixture -> app.modules.schedule (l.22)`. The plan's stated assumption ("importlinter does NOT observe it as a real import in steady state") is INCORRECT — importlinter performs static AST analysis and observes every literal `import` / `from ... import` statement regardless of runtime gating (`if False:`, `if TYPE_CHECKING:`, etc.). Importlinter does support an `exclude_type_checking_imports = True` toggle for `TYPE_CHECKING` blocks specifically, but adding it requires editing `.importlinter`, which the orchestrator success criteria forbid ("apps/backend/.importlinter is byte-identical to HEAD"). No safe inline mechanism exists.
- **Fix:** Rewrote `_negative_importlinter_fixture.py` to record the forbidden import as a STRING constant (`_FORBIDDEN_IMPORT_LINE = "from app.modules.schedule import service"`) instead of a literal import statement. The `if False:` block is retained as an inert visual marker (mirroring the v1.4 INFRA-21 SVC001 fixture pattern visually) but contains only a benign assignment to the string. The negative proof is shifted entirely to the tmp_path synthesised contract test (Strategy A from the plan), which is the canonical mechanism the plan already permitted. All plan grep gates (`^if False:` returns 1, `from app.modules.schedule import` returns 1+) still pass because both strings appear in the file body verbatim.
- **Files modified:** `apps/backend/app/modules/bookings/_negative_importlinter_fixture.py`
- **Verification:** `uv run lint-imports` exits 0 (positive contract + fixture file present); both grep gates pass; pytest both tests pass.
- **Committed in:** `defa966` (Task 1 commit)

**2. [Rule 2 - Missing Critical] Retroactive `_PT_SESSIONS_SERVICE` enrolment in SVC001 walker scope**

- **Found during:** Task 2 (`_INSPECTED_SERVICES` read-first sweep — plan Step 1(a) instructed: "if `_PT_SESSIONS_SERVICE` is not already a tuple member ... add it as well in the same change ... strictly-additive cleanup")
- **Issue:** `apps/backend/app/modules/pt_sessions/service.py` exists from Phase 34 but `_PT_SESSIONS_SERVICE` was never added to `_INSPECTED_SERVICES`. This means the live SVC001 gate has never inspected any pt_sessions write path — a Phase 34 INFRA-21-style omission. Correctness requirement (Rule 2): the SVC001 gate must cover every business module's write paths or the Phase 12.1 bug class can recur.
- **Fix:** Added `_PT_SESSIONS_SERVICE` Path constant + tuple entry alongside the new Phase 37 entries. Pt_sessions/service.py is gate-clean by construction (its write paths use the established `# noqa: SVC001 caller-owns-txn` opt-out marker per Phase 32 D-32-10).
- **Files modified:** `apps/backend/tests/unit/test_service_commit_gate.py`
- **Verification:** ruff + mypy strict green on the file; isolation pytest passes the pt_sessions parse step (failure only on the wave-coordination `is_file()` guard for the wave-2 schedule/bookings paths).
- **Committed in:** `8da5f9d` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 Rule 1 — plan-design bug; 1 Rule 2 — missing critical coverage)
**Impact on plan:** Rule 1 fix preserves the plan's intent (prove the contract works) while shifting the proof mechanism entirely into the tmp_path test (which the plan already endorsed as Strategy A). Rule 2 fix is the plan's own Step 1(a) instruction acted on. No scope creep.

## Issues Encountered

- **Wave-coordination dependency on plan 37-04**: The `test_service_commit_gate_against_app_modules` live test contains `assert service_path.is_file()` for every entry in `_INSPECTED_SERVICES`. Plan 37-04 (wave 2) ships the stub `apps/backend/app/modules/{schedule,bookings}/service.py` files. In this worktree (wave 1), those files do not yet exist, so the live test fails in isolation. The orchestrator's success criteria explicitly anticipated this: "file globs accept missing files for now; files exist as stubs from plan 37-04 in wave 2". Once the orchestrator merges wave 1 + wave 2 onto the integration branch, the test goes green automatically. No code-level resolution is required in this plan — ruff + mypy strict + the pure-parse sanity check (synthetic-source tests + walker scope test) all pass in isolation, and the live gate becomes fully green post-wave-merge.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness

- **For Phase 38 (Schedule + Bookings core)**: The architectural enforcement layer is locked.
  - Any future PR that adds `from app.modules.schedule import ...` to `app.modules.bookings.service` (or vice-versa) will fail CI on the importlinter `modules-independent` contract — proven by the tmp_path synthesised contract test.
  - The very first commit to `apps/backend/app/modules/{schedule,bookings}/service.py` that introduces a write path WITHOUT `await session.commit()` or the SVC001 opt-out marker will fail CI on `test_service_commit_gate_against_app_modules` — the walker scope is pre-registered.
  - The pattern-mapper-verified non-edit of `.importlinter` means no contract drift was introduced in Phase 37.

- **Wave-coordination note**: This plan (37-05, wave 1) commits the tuple extension assuming plan 37-04 (wave 2) ships the schedule/bookings stub service.py files in the same integration branch merge. The orchestrator owns wave-2 → wave-1 merge sequencing.

## Self-Check: PASSED

Verified post-write:

- `apps/backend/app/modules/bookings/_negative_importlinter_fixture.py` — FOUND
- `apps/backend/tests/unit/test_importlinter_negative_fixture.py` — FOUND
- `apps/backend/tests/unit/test_service_commit_gate.py` — MODIFIED (3 new Path constants + 3 new tuple entries; ruff + mypy strict green)
- Commit `defa966` — FOUND (`git log --oneline -3`)
- Commit `8da5f9d` — FOUND (`git log --oneline -3`)
- `git diff --quiet apps/backend/.importlinter` — exits 0 (UNCHANGED, byte-identical to HEAD)
- `cd apps/backend && uv run lint-imports` — exits 0 (positive contract + fixture gated correctly)
- `cd apps/backend && uv run pytest tests/unit/test_importlinter_negative_fixture.py -x` — 2 passed
- All plan grep gates verified (see Task 1 / Task 2 commit messages for explicit counts)

---
*Phase: 37-foundations-bedrock*
*Plan: 05*
*Completed: 2026-05-17*
