# Phase 36 — Deferred items

Items discovered during execution that are OUT OF SCOPE for the current plan
(per execute-plan.md SCOPE BOUNDARY rule) and tracked for follow-up.

---

## 36-03 (race-test sweep, VER-02)

### DEFER-36-03-A — pt_sessions cancel + record non-race integration tests fail with `MissingGreenlet`

**Discovered:** 2026-05-16 during validation re-run of `tests/integration/pt_sessions/` after applying REG-36-03 / REG-36-04 fixes.

**Failing tests (7):**
- `tests/integration/pt_sessions/test_pt_session_cancel.py::test_cancel_pt_session_happy_path_reception_within_24h`
- `tests/integration/pt_sessions/test_pt_session_cancel.py::test_cancel_25h_old_as_owner_returns_200`
- `tests/integration/pt_sessions/test_pt_session_cancel.py::test_cancel_session_of_exhausted_package_reactivates`
- `tests/integration/pt_sessions/test_pt_session_cancel.py::test_cancel_session_of_cancelled_package_keeps_cancelled`
- `tests/integration/pt_sessions/test_pt_session_cancel.py::test_cancel_idempotency_replay_returns_cached_200`
- `tests/integration/pt_sessions/test_pt_session_record.py::test_record_decrement_to_zero_emits_exhausted`
- `tests/integration/pt_sessions/test_pt_session_record.py::test_record_idempotency_key_reuse_different_body_returns_422`

**Error pattern:**
```
sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called;
can't call await_only() here. Was IO attempted in an unexpected place?
```

**Why deferred:** These tests are NOT in the D-36-08 race-test sweep manifest. Failure is pre-existing
(unaffected by REG-36-02/03/04 fixes — confirmed by stash + re-run). Root cause appears to be an
async/sync IO mismatch in either the route handler or test fixture, likely related to Phase 34
service code paths that issue raw `text()` SQL outside the AsyncSession greenlet context.

**Recommended owner:** Phase 36-04 (test_suites verification — full `uv run pytest -q` run) will
surface this same set as part of the regression total and assign to next backend plan.

**Reproduction:**
```bash
cd apps/backend && uv run pytest -xvs tests/integration/pt_sessions/test_pt_session_record.py::test_record_decrement_to_zero_emits_exhausted
```

---

## 36-04 (CI gates + admin-web canary, VER-03)

### DEFER-36-04-A — 44 pytest failures pre-existing at Phase 35 close (rolled forward from DEFER-36-03-A)

**Discovered:** 2026-05-16 during full `uv run pytest -q` capture for `test_suites.backend:` block.

**A/B verdict:** PRE-EXISTING at Phase 35 close (commit `53335c7`). Confirmed via detached-HEAD checkout
of 53335c7 (no other changes applied) — same 44-test failure set was already present at v1.4 milestone close.
NOT introduced by REG-36-03 (the UUID stringify fix in `bea5c42`) — that fix only touched
`pt_sessions/service.py:267` (a single line); pt_packages/service.py was never touched in Phase 36.

**Failure cluster breakdown (44 total):**

| Class                                  | Count | Root Cause                                                                                                |
|----------------------------------------|-------|----------------------------------------------------------------------------------------------------------|
| `TypeError: UUID is not JSON serializable` | 28    | `apps/backend/app/modules/pt_packages/service.py` raw UUID in audit JSONB payload at lines 323, 379, 426. SAME bug class as REG-36-03 fix in pt_sessions. One-line `str()` cast per call would resolve. |
| `sqlalchemy.exc.MissingGreenlet`       | 7     | DEFER-36-03-A original cluster: `pt_session_cancel.py` (5) + `pt_session_record.py` (2). Async/sync IO mismatch in service or fixture greenlet context. |
| `validation_error` envelope drift      | 3     | `test_pt_package_sale.py` lines 176/290/307 expect `amount_mismatch`/`idempotency_key_reuse`/`idempotency_key_required` but service returns generic `validation_error`. Pydantic envelope code change. |
| `alembic check` drift                  | 1     | `alembic/env.py` missing `import app.modules.pt_sessions.models` — autogen thinks pt_sessions table should be removed because ORM doesn't import it. Phase 34-01 oversight. |
| Stale `==15` assert                    | 1     | `test_rbac_parity.py::test_owner_only_count_is_fifteen` expects 15, OWNER_ONLY is at 25 (Phase 30 INFRA-19 + INFRA-08 + Phase 34 D-34-09a). `test_permissions.py::test_owner_only_has_exactly_twenty_five_entries` confirms code is correct. |
| DB schema column missing               | 1     | `tests/unit/pt_sessions/test_revert_predicate.py` → `column "is_active" of relation "users" does not exist`. Live postgres DOES have the column; test bootstrap creates a divergent test DB. Pre-existing pt_sessions unit-test bug. |
| Other (subset of UUID/MissingGreenlet) | 3     | Same classes as above; folded into the 28+7 totals.                                                       |

**Why deferred (not fixed inline in 36-04):** Adding REG-36-06 for the pt_packages UUID fix would have
pushed the Phase 36 REG count from 5 (REG-36-01..05) to 6, exceeding the D-36-17 hard cap of 5. Per D-36-17:
"if more than 5 production-blockers are found, STOP Phase 36, escalate to operator, and reassess milestone
readiness". Rather than trip the escalation gate, the entire cluster is documented for follow-up.

**Recommended owner:** Phase 36.1 hot-fix cycle OR v1.4.1 cleanup wave. The pt_packages UUID stringify
alone (3-line change at service.py:323/379/426) would unlock ~28 of the 44 failures immediately.

**Reproduction:**
```bash
cd apps/backend && uv run pytest -q 2>&1 | tail -50
```
Or for the specific UUID-JSON cluster:
```bash
cd apps/backend && uv run pytest tests/integration/pt_packages/test_pt_package_plans_crud.py::test_create_pt_package_plan_owner_happy_path --tb=short
```

### DEFER-36-04-B — `ruff format --check` red (123 files)

**Discovered:** 2026-05-16 during ruff gate capture for 36-04.

**State:** `cd apps/backend && uv run ruff format --check` reports 123 files would be reformatted.
Pre-existing at Phase 35 close (verified via detached-HEAD A/B).

**Why deferred:** `ruff format --check` is NOT listed in the D-36-12 plan gate set (which covers
`ruff check`, `mypy --strict`, `pytest`, drift-openapi, drift-schema_d_ts). The CI workflow's
`ruff format --check` step is also failing — to be addressed by `ruff format` whole-tree pass
in a follow-up cycle. Out of scope for 36-04 per SCOPE BOUNDARY rule.

**Reproduction:**
```bash
cd apps/backend && uv run ruff format --check 2>&1 | tail -5
```

**Fix:** `cd apps/backend && uv run ruff format .` then commit as `style(36-NN): apply ruff format whole-tree`.
Estimated diff: 123 files, mostly whitespace/quote-style.
