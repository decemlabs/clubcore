---
phase: 14-clients-search-pii-hardening
plan: 02
subsystem: api
tags: [security, sql-injection, ilike, postgres, integration-tests, pii, clients]

requires:
  - phase: 14-clients-search-pii-hardening
    plan: 01
    provides: "_escape_like_pattern helper + escaped ILIKE branches in list_alive"
provides:
  - "5 integration regression tests in tests/integration/clients/test_search.py"
  - "End-to-end coverage of LIKE-metacharacter literalisation through FastAPI → service → repository → Postgres"
  - "Phase 14 SCs #2, #3, #4 locked"
affects: [14-03]

tech-stack:
  added: []
  patterns:
    - "Integration regression tests for security fixes pin both the negative (no-match) and positive (literal-match) sides of the post-fix behaviour"
    - "Test queries chosen to actually pass the _normalise_q ≥2-char gate (`%a`, not bare `%`) so the ILIKE branch is exercised"

key-files:
  created:
    - apps/backend/tests/integration/clients/test_search.py
  modified: []

key-decisions:
  - "Test queries use `%a` (2 chars), not bare `%` (1 char) — bare `%` is dropped to None by `_normalise_q` before reaching ILIKE and cannot exercise CR-01"
  - "CSRF helper coerces `client.cookies.get('sportzal_csrf')` through `or ''` so headers dict stays `dict[str, str]` under mypy strict (Rule 1 fix vs the pre-existing pattern in test_clients_list.py)"
  - "Each test seeds at least one positive AND one negative row so wildcard-expansion regressions would fail the assertion immediately"

patterns-established:
  - "Security-mitigation regression tests live as siblings of feature tests (test_search.py next to test_clients_list.py) and reuse the existing authed_client_owner fixture"
  - "Test docstrings carry the pre-fix vs post-fix mechanism explanation so a future reader understands why the test exists"

requirements-completed: [CLIENTS-04]

duration: 2min
completed: 2026-05-05
---

# Phase 14 Plan 02: Clients Search PII Hardening — Integration Regression Tests Summary

**5 integration tests pin the CR-01 fix end-to-end: `%`, `_`, and `\` are now literals through the full FastAPI → service → repository → Postgres stack, while plain alphanumeric substring search still works.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-05T11:34:24Z
- **Completed:** 2026-05-05T11:36:13Z
- **Tasks:** 1
- **Files modified:** 1 (created)

## Accomplishments

- Created `apps/backend/tests/integration/clients/test_search.py` with 5 named regression tests, all passing under the existing `authed_client_owner` fixture and the SAVEPOINT-rolled session.
- Each test exercises the FastAPI route → service → `list_alive` → Postgres path via httpx `ASGITransport`, the same pattern used by `test_clients_list.py`.
- Phase 14 success criteria #2 (`%`/`_` literal), #3 (`_test_` literal), and #4 (plain alphanumeric regression preserved) are now machine-verifiable.

## The Five Tests

| # | Test name | Seeded rows | Wire query | Asserted result |
|---|-----------|-------------|-----------|-----------------|
| 1 | `test_search_percent_literal_returns_zero_when_no_match` | `Adams` (+79991111111), `Baker` (+79992222222) | `?q=%a` (httpx URL-encodes to `?q=%25a`) | `total == 0`, `items == []` |
| 2 | `test_search_percent_literal_matches_only_when_present` | `100%apple` (+79993333333), `Adams` (+79991111111) | `?q=%a` | `total == 1`, `items[0].lastName == "100%apple"` |
| 3 | `test_search_underscore_is_literal_not_wildcard` | `_test_` (+79995555555), `atestz` (+79996666666) | `?q=_test_` | `total == 1`, `items[0].lastName == "_test_"` |
| 4 | `test_search_backslash_is_literal` | `A\B` (+79997777777), `AB` (+79998888888) | `?q=A\B` | `total == 1`, `items[0].lastName == "A\B"` |
| 5 | `test_search_plain_alphanumeric_still_matches` | `Иванов` (+79990000001), `Иванова` (+79990000002) | `?q=Иванов` | `total == 2`, both rows present |

Pre-fix mechanism (Phase 8 CR-01): the ILIKE pattern was built as `f"%{q.lower()}%"`, so `q="%a"` became `%%a%`. The leading `%` was a SQL wildcard, reducing the pattern to "any row whose lowered name contains the letter `a`" — Test 1's Adams+Baker would BOTH leak.

Post-fix (Plan 14-01): the pattern is `f"%{_escape_like_pattern(q.lower())}%"`, so `q="%a"` becomes `%\%a%`. The `\%` is now a literal `%`, so the pattern requires the contiguous substring `%a` — neither Adams nor Baker contains it, so Test 1 asserts `total == 0`.

## Task Commits

1. **Task 1: Create test_search.py with 5 regression tests for LIKE metacharacter literalisation** — `11b3caf` (test)

The plan tagged the task `tdd="true"` but the helper had already landed in Plan 14-01 with direct unit coverage, so this plan's role is GREEN-side regression evidence rather than a fresh RED→GREEN cycle. Per the plan's `<verification>` block, the tests are confirmatory against the already-shipped helper.

## Files Created/Modified

- `apps/backend/tests/integration/clients/test_search.py` — New file. Contains:
  - Module docstring explaining pre-fix bug, post-fix mechanism, and the `_normalise_q` ≥2-char gate (so future readers know why bare `?q=%` cannot exercise the bug).
  - `_csrf_headers(client)` helper (mirrors `test_clients_list.py` but adds `or ""` fallback for mypy strict).
  - `_create(authed_client_owner, *, last_name, phone, first_name="Иван")` helper for keyword-only seeding.
  - 5 `async def test_*` functions with verbatim names from the plan.

## Verification

- `cd apps/backend && uv run pytest tests/integration/clients/test_search.py -v` → `5 passed in 0.67s`.
- `cd apps/backend && uv run pytest tests/integration/clients -v` → `39 passed in 4.44s` (5 new + 34 existing).
- `cd apps/backend && uv run pytest -q` (full backend suite) → `254 passed in 11.51s`.
- `cd apps/backend && uv run ruff check tests/integration/clients/test_search.py` → `All checks passed!`.
- `cd apps/backend && uv run mypy --strict tests/integration/clients/test_search.py` → `Success: no issues found in 1 source file`.
- Acceptance grep checks:
  - `grep -c "^async def test_" apps/backend/tests/integration/clients/test_search.py` → `5`.
  - All five exact test function names present (verbatim grep) → confirmed.
  - `grep -n 'params={"q": "%"}' apps/backend/tests/integration/clients/test_search.py | grep -v '%[a-zA-Z_\\]'` → no matches (no bare 1-char `%` queries).

## Decisions Made

- **Test queries use `%a` (2 chars) not bare `%` (1 char).** `ClientListQuery._normalise_q` (schemas.py:253-262) drops any `q` shorter than 2 chars to `None`, which means a bare `?q=%` bypasses the ILIKE branch entirely — the filter is skipped, every alive row comes back, and the test cannot distinguish "bug present" from "bug fixed". `%a` is the smallest query that simultaneously passes the normaliser AND contains a LIKE metacharacter, so it actually exercises both the wildcard-expansion bug and its escape-based fix.
- **CSRF cookie helper coerces `None` to `""`.** `client.cookies.get("sportzal_csrf")` returns `str | None` per httpx typing; the original `test_clients_list.py` pattern (`get(..., "")`) silently fails mypy strict because the second arg is keyword-only `default`. Used `cookies.get(...) or ""` so the result is unambiguously `str` and the headers dict stays `dict[str, str]`. This was a Rule 1 fix vs the pre-existing pattern; the production code was untouched.
- **Each test seeds both a positive (matching) and a negative (non-matching) row.** This means a wildcard-expansion regression would fail the assertion immediately — for example, if `_test_` ever wildcards back into a single-char `_`, Test 3's `atestz` would be returned and `total == 1, items[0].lastName == "_test_"` would fail.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Adjusted `_csrf_headers` so mypy strict passes**

- **Found during:** Task 1 (post-write verification)
- **Issue:** The plan's `<action>` block specified `client.cookies.get("sportzal_csrf", "")` (mirroring the pre-existing pattern in `test_clients_list.py`). This pattern fails `mypy --strict` because httpx typing returns `str | None` from `cookies.get(...)`, and the dict value type would be inferred as `str | None`, breaking the `dict[str, str]` return annotation. The acceptance criterion explicitly requires `mypy --strict tests/integration/clients/test_search.py` to exit 0.
- **Fix:** Used `token = client.cookies.get("sportzal_csrf") or ""` then `return {"X-CSRF-Token": token}`. Behaviourally identical (empty string when cookie missing), strict-typing clean.
- **Files modified:** `apps/backend/tests/integration/clients/test_search.py` (helper only).
- **Verification:** ruff + mypy strict both clean post-fix. All 5 tests still pass.
- **Committed in:** `11b3caf` (Task 1 commit, same atomic change).
- **Scope note:** The pre-existing `test_clients_list.py` has the same pattern and the same mypy-strict failure. Per the SCOPE BOUNDARY rule, that is out of scope for this plan and intentionally left untouched — this plan's acceptance criterion only required the new file to be clean.

---

**Total deviations:** 1 auto-fixed (Rule 1 — mypy strict typing).
**Impact on plan:** No scope creep. Adjustment was confined to the helper inside the new file.

## Issues Encountered

None.

## TDD Gate Compliance

The plan tagged the task `tdd="true"`. Strictly speaking, RED→GREEN is satisfied at the phase level (Plan 14-01 landed the helper after its own unit tests; Plan 14-02 ships integration tests against the already-passing implementation). At commit-history level this plan produces only a `test(...)` commit since no production code is changed.

Resulting commit history for Phase 14 so far:
- `7f170cb feat(14-01): escape SQL LIKE metacharacters in clients.list_alive` — production fix
- `cc46ce8 test(14-01): add unit coverage for _escape_like_pattern helper` — unit-level lock
- `11b3caf test(14-02): add 5 integration regression tests for LIKE-metacharacter literalisation` — integration-level lock (this plan)

## Next Phase Readiness

- Plan 14-03 (`08-VERIFICATION.md` update) can reference all three commits above as the CR-01 mitigation evidence chain: production fix + unit lock + integration lock.
- Phase 14 SCs #2, #3, #4 are now locked by named tests; SC #5 closure is owned by Plan 14-03.
- No blockers for downstream plans.

## Self-Check: PASSED

- `apps/backend/tests/integration/clients/test_search.py` — FOUND
- `.planning/phases/14-clients-search-pii-hardening/14-02-SUMMARY.md` — FOUND (this file)
- Commit `11b3caf` — FOUND in `git log`
- 5 test functions with verbatim plan-mandated names — FOUND
- `pytest tests/integration/clients/test_search.py` → 5 passed
- `pytest tests/integration/clients` → 39 passed
- `pytest` (full suite) → 254 passed
- `ruff check` on new file → clean
- `mypy --strict` on new file → clean

---
*Phase: 14-clients-search-pii-hardening*
*Plan: 02*
*Completed: 2026-05-05*
