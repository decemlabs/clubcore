# Phase 38 Deferred Items

Out-of-scope discoveries logged during plan execution. NOT fixed in the
plan that discovered them because they are pre-existing failures unrelated
to the plan's diff (per executor SCOPE BOUNDARY rule).

## Pre-existing `db_session.expire_all()` MissingGreenlet failures

**Discovered during:** Plan 38-05 execution (regression run)

**Affected tests** (5+):
- `tests/integration/pt_sessions/test_pt_session_cancel.py::test_cancel_pt_session_happy_path_reception_within_24h`
- `tests/integration/pt_sessions/test_pt_session_record.py::test_record_decrement_to_zero_emits_exhausted`
- (and additional tests in `test_pt_session_cancel.py` / `test_pt_session_record.py`
  that follow the same `db_session.expire_all()` pattern)

**Symptom:** `sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called`

**Root cause:** Pre-existing pattern documented in `38-02-SUMMARY.md`
deviation #3 — `db_session.expire_all()` followed by
`await db_session.scalar(...)` raises `MissingGreenlet` in the SAVEPOINT-
mode session (`join_transaction_mode='create_savepoint'`). The expire-then-
async-fetch sequence trips an attribute-loader chain that runs outside the
async-greenlet context.

**Confirmation pre-existed plan 38-05:** `git stash` of plan 38-05 changes
+ rerun → same failures persist. The plan 38-05 diff did not introduce or
worsen this behaviour.

**Recommended fix (defer to a follow-up plan):** Replace `expire_all()` calls
with targeted `await db_session.refresh(orm_instance, attribute_names=[...])`
calls per the pattern established in plan 38-02 (bookings tests landed
this fix; pt_sessions still uses the legacy pattern).

**Why not fixed in 38-05:** SCOPE BOUNDARY — out-of-scope for the
booking-completion plan; would balloon the diff into the legacy pt_sessions
test suite. The booking-completion test file (NEW in 38-05) deliberately
avoids `expire_all()` and uses `refresh(attribute_names=[...])` per the
established pattern.

**Carry forward:** Plan 38-06 (gate plan) will attempt an opportunistic sweep
of these failures (and the wider DEFER-36-04-A set) while the test surface
is being touched anyway. Remaining failures carry to Phase 40 verification.

## Pre-existing `alembic check` drift from prior-run DB state

**Discovered during:** Plan 38-04 execution

**Symptom:** Database has stale `pt_sessions.booking_id` column from a prior
run (likely a sibling worktree that executed plan 38-05 against this same
dev DB earlier). `alembic check` flags it as drift because plan 38-04 has
not shipped that ORM column change — plan 38-05 does.

**Root cause:** Wave-3 parallel execution against a shared dev DB instance.
Worktree isolation covers the filesystem and git state but not the database.

**Resolution:** NOT caused by plan 38-04's diff; reconciles automatically
once plan 38-05 lands its ORM column change (orchestrator merge of 0019
brings the migration into chain alignment).

**Carry forward:** No action — auto-resolves after orchestrator merges all
Wave 3 worktrees and the alembic chain is serialised (0017 → 0018 → 0019).
