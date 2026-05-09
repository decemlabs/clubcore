# Phase 27 Deferred Items

## Pre-existing mypy errors in `apps/backend/tests/`

**Discovered:** 2026-05-09 (Plan 27-05 Task 12 final-bar verification)

**Status:** Out of scope for Phase 27 — baseline state from before the phase started.

**Detail:** Running `cd apps/backend && uv run mypy .` from the project root
reports 137 errors across 15 test files (none in `app/` source code; all
pre-existing in `tests/`). The errors are unchanged from the worktree base
commit `ed52b22f3187635c28a23bb57f321762adc88990` — verified by `git checkout`
of `tests/integration/auth/test_sessions_endpoints.py` at base + re-running
mypy: 45 errors at base, identical to the post-plan-27-05 count for that file.

**Per-file rough breakdown:**

- `tests/integration/auth/test_sessions_endpoints.py` — `dict | None` attr access (~45)
- `tests/integration/clients/*` — multiple files (~30)
- `tests/integration/memberships/test_audit_writes.py`, `test_plans_*` — (~25)
- `tests/unit/memberships/test_renewal_constants.py`, `test_schemas.py` — (~10)
- `tests/unit/test_config.py`, `test_dependencies_*` — (~25)

**Why deferred:**

- All errors are in PRE-EXISTING test files; none of Phase 27's new test files
  (`tests/integration/notifications/`, `tests/unit/integrations/telegram/`) have
  any mypy errors. Per the GSD scope-boundary rule, only issues DIRECTLY caused
  by the current task's changes are auto-fixed.
- Phase 27-02 / 27-04 / 27-05 verified mypy on per-file targets (`uv run mypy
  app/...` and `uv run mypy <new-test-file>`), not on `mypy .` over the whole
  tree.
- Fixing 137 errors across 15 unrelated test files would be a large refactor
  with risk of regressing the test logic; should be its own phase.

**Phase 27-05 Task 12 acceptance criterion** literally specifies
`cd apps/backend && uv run mypy .` exits 0, but the project's mypy baseline at
the worktree branch base did not satisfy this. Plan 27-05's new code is mypy-
clean (`uv run mypy tests/integration/notifications/ tests/unit/integrations/`
exits 0 — verified per task).

**Suggested follow-up phase:** dedicated test-tree mypy cleanup, file-by-file
with the test author re-validating each fix.
