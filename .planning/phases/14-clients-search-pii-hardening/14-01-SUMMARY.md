---
phase: 14-clients-search-pii-hardening
plan: 01
subsystem: api
tags: [security, sql-injection, ilike, postgres, sqlalchemy, pii, clients]

requires:
  - phase: 08-clients-module-audit-log
    provides: clients.list_alive ILIKE search predicates (CR-01 source bug)
provides:
  - "_escape_like_pattern(value, *, escape_like=True) helper in clients/repository.py"
  - "Both ILIKE callsites in list_alive (FIO + phone) route through the helper"
  - "Six-test unit coverage of the escape helper (tests/unit/clients/test_repository_escape.py)"
affects: [14-02, 14-03]

tech-stack:
  added: []
  patterns:
    - "User-supplied search input is escaped for LIKE/ILIKE before being wrapped in %...%"
    - "Escape order: backslash first, then % and _ (avoids double-escaping the escapes we add)"
    - "Module-private opt-out flag (escape_like: bool = True) preserved for future wildcard semantics"

key-files:
  created:
    - apps/backend/tests/unit/clients/test_repository_escape.py
    - apps/backend/tests/unit/clients/__init__.py
  modified:
    - apps/backend/app/modules/clients/repository.py

key-decisions:
  - "Escape order locked: backslash first, then % then _ (test_mixed_metacharacters_apply_in_correct_order pins this)"
  - "No ESCAPE clause added to ILIKE — Postgres default escape char is backslash; helper output is already understood natively"
  - "Helper kept module-private (_escape_like_pattern) — only in-file callers; not exposed in service layer"

patterns-established:
  - "LIKE/ILIKE metacharacter escaping at the repository boundary, not at the DTO or service layer"
  - "Helper unit tests live in tests/unit/<module>/ siblings to repository/service files"

requirements-completed: [CLIENTS-04]

duration: 6min
completed: 2026-05-05
---

# Phase 14 Plan 01: Clients Search PII Hardening — Escape Helper Summary

**`_escape_like_pattern` helper escapes `%`, `_`, and `\` in user-supplied `q` so a reception user can no longer `?q=%` and dump the full client roster (CR-01 closure).**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-05-05T11:25:00Z
- **Completed:** 2026-05-05T11:31:25Z
- **Tasks:** 2
- **Files modified:** 3 (1 modified + 2 created)

## Accomplishments

- Added module-private `_escape_like_pattern(value: str, *, escape_like: bool = True) -> str` helper in `apps/backend/app/modules/clients/repository.py` (defined just below imports, before `get_alive`).
- Routed both ILIKE callsites in `list_alive` through the helper:
  - FIO branch (`apps/backend/app/modules/clients/repository.py:104`) — `escaped_q = _escape_like_pattern(query.q.lower())` before wrapping in `%...%`.
  - Phone branch (`apps/backend/app/modules/clients/repository.py:117`) — `_escape_like_pattern(query.q)` inline inside the f-string wrap.
- Created `apps/backend/tests/unit/clients/test_repository_escape.py` with six direct unit tests covering plain input, `%`, `_`, `\`, the mixed-input order invariant, and the `escape_like=False` opt-out.
- Added `apps/backend/tests/unit/clients/__init__.py` to match the existing `tests/unit/` package layout.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add `_escape_like_pattern` helper + apply to both ILIKE branches in `list_alive`** — `7f170cb` (feat)
2. **Task 2: Add direct unit tests for `_escape_like_pattern`** — `cc46ce8` (test)

_Note: Per the plan's Task 1/Task 2 split, the helper landed first (with static verification via ruff + mypy + grep acceptance criteria) and the unit tests landed in Task 2 — both commits ship the same atomic CR-01 mitigation._

## Files Created/Modified

- `apps/backend/app/modules/clients/repository.py` — Added `_escape_like_pattern` helper (line 46–73) and routed both ILIKE callsites through it (lines 104, 117). Updated `list_alive` docstring to point at the helper.
- `apps/backend/tests/unit/clients/test_repository_escape.py` — Six unit tests:
  - `test_plain_alphanumeric_is_unchanged` — `Иванов` and `foo123` round-trip unchanged.
  - `test_percent_is_escaped` — `50%` → `50\%`.
  - `test_underscore_is_escaped` — `a_b` → `a\_b`.
  - `test_backslash_is_doubled` — `a\b` → `a\\b`.
  - `test_mixed_metacharacters_apply_in_correct_order` — `100%_x\y` → `100\%\_x\\y` (pins escape order: `\` first, then `%`, then `_`).
  - `test_escape_like_false_returns_input_unchanged` — opt-out hook returns input verbatim.
- `apps/backend/tests/unit/clients/__init__.py` — Empty package marker matching the existing `tests/unit/` convention.

## Verification

- `cd apps/backend && uv run ruff check app/modules/clients/repository.py` → exit 0.
- `cd apps/backend && uv run mypy --strict app/modules/clients/repository.py` → exit 0.
- `cd apps/backend && uv run pytest tests/unit/clients/test_repository_escape.py -v` → `6 passed in 0.01s`.
- `cd apps/backend && uv run ruff check tests/unit/clients/test_repository_escape.py` → exit 0.
- `cd apps/backend && uv run mypy --strict tests/unit/clients/test_repository_escape.py` → exit 0.
- Acceptance grep checks (post-Task-1):
  - `grep -n "def _escape_like_pattern"` → 1 match.
  - `grep -c "_escape_like_pattern"` → 4 (1 def + 1 docstring mention in `list_alive` + 2 callsites).
  - `grep -n 'escape_like: bool = True'` → 1 match.
  - `grep -E 'f"%\{query\.q(\.lower\(\))?\}%"'` → 0 matches (un-escaped raw interpolation removed).

## Decisions Made

- **Escape order locked: `\` first, then `%`, then `_`.** Pinned by `test_mixed_metacharacters_apply_in_correct_order`. Reverse order would re-escape the backslashes we add for `%`/`_`.
- **No `ESCAPE` clause on the ILIKE expressions.** Postgres default escape char is `\`, and the helper produces backslash-escaped sequences that ILIKE understands natively — adding `ESCAPE '\\'` would be redundant and would force a re-quote review.
- **Helper kept module-private (`_escape_like_pattern`).** Only callers are in `repository.py:list_alive`; service layer (Plan 06) does not need access. Exporting later is cheap; un-exporting later is not.
- **Phone branch escapes raw `query.q` (not `query.q.lower()`).** Matches the existing semantics — phone is canonical E.164 (digits + `+`) so case-folding is a no-op, but escaping the raw value keeps the phone path symmetric with the FIO path without changing observable behaviour.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added pointer to `_escape_like_pattern` in `list_alive` docstring**

- **Found during:** Task 1 (verification)
- **Issue:** The plan's automated verification (`grep -n "_escape_like_pattern" ... | wc -l ≥ 4`) expected 4 occurrences (1 def + 1 docstring mention + 2 callsites). Plan's `<action>` block did not explicitly write the docstring mention into `list_alive`, so the file shipped with only 3 occurrences (1 def + 2 callsites).
- **Fix:** Added a 3-line note to the existing `list_alive` docstring naming `_escape_like_pattern` and explaining the CR-01 rationale. This brings the file to 4 occurrences and aligns with the planner's documented expectation.
- **Files modified:** `apps/backend/app/modules/clients/repository.py` (docstring of `list_alive` only — no behaviour change).
- **Verification:** `grep -c "_escape_like_pattern"` → 4. Ruff + mypy still clean.
- **Committed in:** `7f170cb` (Task 1 commit, same atomic change).

---

**Total deviations:** 1 auto-fixed (Rule 2 — missing critical: matched the plan's automated verification expectation).
**Impact on plan:** No scope creep. Pure documentation alignment with the plan's own verification spec.

## Issues Encountered

None.

## TDD Gate Compliance

The plan tagged both tasks `tdd="true"` but its task ordering inverts strict RED→GREEN: Task 1 lands the helper (verified statically via ruff + mypy + grep acceptance criteria, not by tests) and Task 2 lands the unit tests. Per the plan's own `<verification>` and `<acceptance_criteria>` blocks, this is the intended sequence — the unit tests are confirmatory rather than RED-phase drivers. Final state matches both task `<done>` blocks: helper + 6/6 passing tests + ruff/mypy clean.

Resulting commit history:
- `7f170cb feat(14-01): escape SQL LIKE metacharacters in clients.list_alive`
- `cc46ce8 test(14-01): add unit coverage for _escape_like_pattern helper`

## Next Phase Readiness

- Plan 14-02 (integration regression) can now build on a stable helper that already has direct unit coverage and is exercised by both ILIKE branches.
- Plan 14-03 (08-VERIFICATION.md update) can reference `7f170cb` as the CR-01 mitigation commit and `cc46ce8` as the locked unit-test fixture.
- No blockers for downstream plans.

## Self-Check: PASSED

- `apps/backend/app/modules/clients/repository.py` — FOUND
- `apps/backend/tests/unit/clients/test_repository_escape.py` — FOUND
- `apps/backend/tests/unit/clients/__init__.py` — FOUND
- `.planning/phases/14-clients-search-pii-hardening/14-01-SUMMARY.md` — FOUND
- Commit `7f170cb` — FOUND in `git log --all`
- Commit `cc46ce8` — FOUND in `git log --all`

---
*Phase: 14-clients-search-pii-hardening*
*Plan: 01*
*Completed: 2026-05-05*
