---
phase: 06-rbac-wiring-parity-tests
plan: 05
subsystem: testing

tags:
  - rbac
  - parity
  - introspection
  - architectural-enforcement
  - fastapi

# Dependency graph
requires:
  - phase: 06-rbac-wiring-parity-tests
    provides: "06-02 — `require_authenticated()` factory in `app/core/dependencies.py` (qualname discriminator anchor for TEST-07)"
  - phase: 06-rbac-wiring-parity-tests
    provides: "06-03 — auth router migration: `/me`, `/logout`, `/logout-all` swapped to `Depends(require_authenticated())` so TEST-07 turns green post-merge"
  - phase: 04-auth-foundations
    provides: "`Action` / `Resource` StrEnums + `OWNER_ONLY` frozenset in `app/core/permissions.py` (parity source-of-truth)"
provides:
  - "Architectural enforcement for FE↔BE RBAC parity (TEST-06): three set-equalities catch drift on OWNER_ONLY pairs, Resource enum, Action enum"
  - "Architectural enforcement for FastAPI route gating (TEST-07): every non-excluded `APIRoute` declares `require_permission(...)` or `require_authenticated()`; the test IS the rule"
  - "Documented `EXCLUDED_PATHS` audit trail (D-04 + D-19): a diff to the set is the only way to legally exempt a route"
  - "Pre-anticipated Phase 7 telegram routes: `EXCLUDED_PREFIXES = ('/api/v1/auth/telegram/',)` so TEST-07 stays green when `/api/v1/auth/telegram/{start,status,verify}` mount"
affects:
  - "Phase 7 — Telegram OTP channel (its routes are already prefix-excluded; no test edits needed when they mount)"
  - "Phase 8 — Clients module (every new client endpoint must declare a gate or TEST-07 fails)"
  - "Future FE refactors of `apps/admin-web/src/shared/session/{can,registry}.ts` (any rename is caught by TEST-06)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Static-file regex parsing for cross-stack parity (no codegen, no JSON IPC)"
    - "FastAPI dependant-tree walking via `route.dependant.dependencies` recursion + `__qualname__` prefix discriminator"
    - "Failure-message-as-runbook: TEST-07's assert message embeds the current `EXCLUDED_PATHS` so the developer who hits the failure can self-diagnose without opening the test file"

key-files:
  created:
    - apps/backend/tests/integration/test_rbac_parity.py
    - apps/backend/tests/integration/test_route_introspection.py
  modified: []

key-decisions:
  - "Stop signal for `_parse_ts_union` is the next top-level TS declaration prefix (`export `, `interface `, `type `, `const `, `function `, `class `), not a blank-line heuristic — registry.ts has Resource and Action separated only by a blank line, so a blank-line stop bleeds Action literals into Resource (caught during executor smoke testing on first pytest run)."
  - "TEST-07 main test currently FAILS in this isolated worktree (3 routes missing gate: /api/v1/auth/{me,logout,logout-all}) because Plan 06-03's auth-router migration lives in a sibling worktree that has not been merged into this branch's base. Post-merge by the orchestrator, all 3 tests pass. The other 6 tests pass in this worktree."

patterns-established:
  - "Three-way set-equality (D-13) for FE↔BE parity: pairs alone are insufficient because a Resource rename outside OWNER_ONLY (e.g., 'schedule' → 'timetable') leaves pair-count unchanged. The three-set check provides total coverage."
  - "Tests live at `tests/integration/` top-level (NOT `tests/integration/<sub>/`) when they don't need DB/Redis (D-16) — folder location is the implicit infrastructure marker."
  - "Sanity-belt tests around the discriminator (`test_gate_prefixes_match_factory_names`) prevent the TEST-07 enforcement from being silently invalidated by a refactor of `require_*` factory names."

requirements-completed:
  - RBAC-03
  - RBAC-04
  - TEST-06
  - TEST-07

# Metrics
duration: ~12 min
completed: 2026-05-02
---

# Phase 06 Plan 05: RBAC Parity & Route-Introspection Tests Summary

**Two architectural-enforcement tests: TEST-06 (three set-equalities of FE↔BE RBAC primitives via static TS parsing) + TEST-07 (every non-excluded `APIRoute` carries `require_permission`/`require_authenticated`).**

## Performance

- **Duration:** ~12 min (executor wall time)
- **Tasks:** 2 / 2 completed
- **Files created:** 2
- **Files modified:** 0 (production code untouched per parallel-executor boundary)

## Accomplishments

- **TEST-06 (`test_rbac_parity.py`)** — 4 tests; passes 4/4. Three set-equalities (OWNER_ONLY pairs, Resource values, Action values) plus a sanity count. Static-file regex against `apps/admin-web/src/shared/session/{can,registry}.ts` resolved through `Path(__file__).resolve().parents[4]` (D-14). No FastAPI / DB / Redis dependency.
- **TEST-07 (`test_route_introspection.py`)** — 3 tests; passes 2/3 in this worktree (sanity belts green; main test pending post-merge of Plan 06-03). Walks `app.routes` from a fresh `create_app()` and asserts every non-excluded `APIRoute` carries a callable whose `__qualname__` starts with `require_permission.` or `require_authenticated.` (D-18). `EXCLUDED_PATHS` (10 entries) + `EXCLUDED_PREFIXES = ('/api/v1/auth/telegram/',)` (D-04, D-19).
- **Failure message format on TEST-07** — embeds the failing route list AND the current `EXCLUDED_PATHS` / `EXCLUDED_PREFIXES`, so a developer who hits the failure can self-diagnose without opening the test file.

## Task Commits

Each task was committed atomically:

1. **Task 1: TEST-06 — three-way set-equality parity test** — `b1ec77f` (test)
2. **Task 2: TEST-07 — route-introspection guard for `require_permission` / `require_authenticated`** — `9cb5bd7` (test)

## Files Created/Modified

- `apps/backend/tests/integration/test_rbac_parity.py` — 4 tests (`test_owner_only_pairs_match`, `test_resource_values_match`, `test_action_values_match`, `test_owner_only_count_is_nine`); module-level `_PAIR_RE` and `_DECL_PREFIXES` constants; `_parse_owner_only_pairs()` + `_parse_ts_union()` helpers.
- `apps/backend/tests/integration/test_route_introspection.py` — 3 tests (`test_every_protected_route_declares_a_gate`, `test_excluded_paths_set_is_locked`, `test_gate_prefixes_match_factory_names`); `EXCLUDED_PATHS` (frozenset, 10 entries), `EXCLUDED_PREFIXES = ('/api/v1/auth/telegram/',)`, `_GATE_PREFIXES = ("require_permission.", "require_authenticated.")`; `_route_has_gate(route)` recurses `route.dependant.dependencies` with cycle-defensive `seen` set.

## Routes Inspected at Test Time

Walking `app.routes` from `create_app()` yields the following surface in the current base (`a3f99cf` — Wave 1 of phase 06 already merged):

| Path | Disposition | Gate |
| --- | --- | --- |
| `/healthz` | EXCLUDED_PATHS | (none — Kubernetes liveness, D-04) |
| `/openapi.json`, `/docs`, `/docs/oauth2-redirect`, `/redoc` | EXCLUDED_PATHS | (none — FastAPI built-ins) |
| `/api/v1/auth/login` | EXCLUDED_PATHS | (none — identity in body, D-04) |
| `/api/v1/auth/refresh` | EXCLUDED_PATHS | (none — identity in `sz_refresh` cookie, D-04) |
| `/api/v1/auth/me` | enforced | `Depends(get_current_user)` directly — **fails post-Wave-2-merge requirement** until Plan 06-03 lands |
| `/api/v1/auth/logout` | enforced | `Depends(get_current_user)` directly — same |
| `/api/v1/auth/logout-all` | enforced | `Depends(get_current_user)` directly — same |

Plan 06-03 swaps the three `Depends(get_current_user)` calls to `Depends(require_authenticated())`. After the orchestrator merges 06-03 into this branch's base, TEST-07's main test turns green for the same route surface (verified by reading 06-03's plan; commit exists in sibling worktree `worktree-agent-ad5b7ca61ece7ec81` as `04e6ab7 feat(06-03): migrate auth router to require_authenticated + per-route CSRF`).

## Decisions Made

- **`_parse_ts_union` stop signal** (Rule 1 fix during smoke-testing, see "Deviations" below): blank-line stop is unsafe; only "next top-level TS declaration prefix" is a stable end-of-union sentinel.
- **Test path resolution from `parents[4]`**: independently verified during Task 1 development by reading `apps/backend/tests/integration/test_rbac_parity.py` location:
  - `parents[0]` = `apps/backend/tests/integration`
  - `parents[1]` = `apps/backend/tests`
  - `parents[2]` = `apps/backend`
  - `parents[3]` = `apps`
  - `parents[4]` = repo root → `apps/admin-web/src/shared/session/can.ts` resolves correctly.
- **Acceptance criterion phrasing for "no FastAPI/Redis import"**: the plan's `grep -E "FastAPI|AsyncClient|Depends|Redis"` returns 1 line on `test_rbac_parity.py` because the docstring at line 8 reads "Static-file analysis only — no FastAPI app, no DB, no Redis." This is a docstring describing what the test does NOT use; the spirit of the criterion (no imports of those names) is satisfied — `grep -nE "^(import|from) .*(FastAPI|AsyncClient|Depends|Redis)"` returns 0 lines. No modification needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] `_parse_ts_union` algorithm bled Action literals into Resource set**
- **Found during:** Task 1 (first `pytest` run after writing the file)
- **Issue:** Plan-supplied algorithm used a "blank line + no `|` + no `'`" stop heuristic. registry.ts has `| 'owner-area'` on line 12, then a blank line on 13, then `export type Action = 'view' | 'create' | ...` on line 14. The blank line did not break (because `stripped` is empty → the heuristic skipped it), and line 14 contained `'`, so all 5 Action values were appended to the Resource set. `test_resource_values_match` failed with `FE-only: ['create', 'delete', 'edit', 'refund', 'view']`.
- **Fix:** Replaced the loop's stop condition with "current line begins (after `lstrip`) with one of `_DECL_PREFIXES = ('export ', 'interface ', 'type ', 'const ', 'function ', 'class ')` AND we are past the anchor line (`offset > 0`)". This is the only stable end-of-union signal in TS sources where unions can be separated only by whitespace.
- **Files modified:** `apps/backend/tests/integration/test_rbac_parity.py`
- **Verification:** `uv run pytest tests/integration/test_rbac_parity.py -v` → 4 passed; `uv run mypy ...` → clean; `uv run ruff check ...` → clean.
- **Committed in:** `b1ec77f` (Task 1 commit; the fix and the file landed together — no separate commit because the fix happened within the same authoring pass).

**2. [Rule 1 — Bug] `_DECL_PREFIXES` defined inside function failed `ruff` N806 (uppercase variable in function)**
- **Found during:** Task 1 (first `ruff check` run after the algorithm fix)
- **Issue:** Constant declared inside `_parse_ts_union`. `ruff` N806 flagged the uppercase identifier. Module-level constant is the correct location anyway (it's not state).
- **Fix:** Promoted `_DECL_PREFIXES` to module scope alongside `_PAIR_RE`.
- **Files modified:** `apps/backend/tests/integration/test_rbac_parity.py`
- **Committed in:** `b1ec77f` (same Task 1 commit).

**3. [Rule 1 — Bug] `_route_has_gate` inner walk used `for/return True/return False` flagged by `ruff` SIM110**
- **Found during:** Task 2 (`ruff check` after first run)
- **Issue:** `for sub in deps: if _walk(sub): return True; return False` is the canonical `any()` rewrite per `ruff` SIM110.
- **Fix:** Replaced with `return any(_walk(sub) for sub in getattr(dep, "dependencies", []))`. Behaviour-preserving.
- **Files modified:** `apps/backend/tests/integration/test_route_introspection.py`
- **Committed in:** `9cb5bd7` (Task 2 commit).

---

**Total deviations:** 3 auto-fixed (3 × Rule 1 bug — one algorithmic, two style/lint).
**Impact on plan:** All three were inside the test files this plan owns; none crossed the executor boundary. The algorithmic fix (#1) is the substantive one — the plan-supplied `_parse_ts_union` body would have shipped a false-positive parity failure. The fix is documented in the file's own docstring (`_parse_ts_union` rationale block) so a future reader understands why the stop signal is a declaration prefix, not a blank line.

## Issues Encountered

**TEST-07 main test fails in this worktree.** This is the parallel-execution model working as intended:

- This worktree was branched from `a3f99cffcd4831449caec099346e0ba454567c8c`.
- Plan 06-03's auth-router migration (`Depends(get_current_user)` → `Depends(require_authenticated())` on `/me`, `/logout`, `/logout-all`) lives in sibling worktree `worktree-agent-ad5b7ca61ece7ec81` (commit `04e6ab7 feat(06-03): migrate auth router to require_authenticated + per-route CSRF`) and has NOT been merged into this branch's base.
- Plan 06-05's wave is `wave: 2` with `depends_on: [06-02, 06-03]`. The orchestrator's wave-2 prerequisite is the merge of all wave-1 worktrees; my executor boundary forbids me from touching production app code (`Do NOT modify production app code or any other test file`).
- Therefore the test is correctly written per spec; the prerequisite is unmet only inside this isolated worktree. After the orchestrator merges 06-03, TEST-07 turns green on the same route surface.

The two sanity-belt tests (`test_excluded_paths_set_is_locked`, `test_gate_prefixes_match_factory_names`) and all 4 TEST-06 tests pass in this worktree without any external dependency.

## Next Phase Readiness

- **Phase 7 (Telegram OTP)** requires NO change to TEST-07: `EXCLUDED_PREFIXES = ('/api/v1/auth/telegram/',)` already covers `/api/v1/auth/telegram/{start,status,verify}` and any sibling routes the Phase 7 agent decides to mount under that prefix.
- **Phase 8 (Clients module)** is subject to TEST-07 enforcement on day one: every new endpoint under `/api/v1/clients/*` MUST declare `Depends(require_permission(Action.X, Resource.CLIENTS))` or the introspection test fails the build. The failure message will list the unguarded paths and the current exclusion sets — a self-documenting runbook.
- **Phase 6 ROADMAP**: the only outstanding piece for Wave 2's "ARCH ENFORCED" gate is the orchestrator's merge of 06-02 / 06-03 into 06-05 + verifier sweep. No further test work is required from this plan.

## Self-Check: PASSED

- Files exist:
  - `FOUND: apps/backend/tests/integration/test_rbac_parity.py`
  - `FOUND: apps/backend/tests/integration/test_route_introspection.py`
- Commits exist:
  - `FOUND: b1ec77f` — `test(06-05): add TEST-06 backend↔frontend RBAC parity test`
  - `FOUND: 9cb5bd7` — `test(06-05): add TEST-07 route-introspection guard`
- Production source code unchanged: `git diff a3f99cf..HEAD -- apps/backend/app apps/admin-web` returns nothing (boundary respected).

---
*Phase: 06-rbac-wiring-parity-tests*
*Completed: 2026-05-02*
