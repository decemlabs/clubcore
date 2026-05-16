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
