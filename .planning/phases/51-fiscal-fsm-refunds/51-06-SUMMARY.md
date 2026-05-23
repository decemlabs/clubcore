---
phase: 51-fiscal-fsm-refunds
plan: 06
subsystem: payments
tags: [yookassa, fiscal-receipts, arq, webhooks, ast-gate, fsm]

# Dependency graph
requires:
  - phase: 51-fiscal-fsm-refunds/05
    provides: ARQ task "dispatch_fiscal_receipt" registered in WorkerSettings.functions with _max_tries=3 retry contract
  - phase: 50-webhook-fsm-fiscal-foundation/04
    provides: _post_commit_enqueue stub (DEFER-50-04) with W-4-locked signature (arq_pool, *, online_payment_id, subject_kind, subject_id)
provides:
  - Filled fiscal-dispatch branch of _post_commit_enqueue (DEFER-50-04 closed)
  - Phase 50 handle_payment_succeeded callsite now threads the just-INSERTed fiscal_receipts.id through to the post-commit hook
  - Router threads request.app.state.arq_pool through to the handler so the enqueue actually fires
  - AST gate test renamed in-place to lock the new 2-statement body shape (Expr(_log.info) + If(BoolOp(And)) → Await(arq_pool.enqueue_job))
affects:
  - phase 51-07 (already shipped — registered receipt webhook handlers; no impact on this plan, just sequencing context)
  - phase 51-10 (E2E milestone verification — payment.succeeded webhook now drives a real dispatch_fiscal_receipt enqueue)
  - phase 52 (notification branches NOT-02 refund DM, NOT-04 fiscal-failure DM — same _post_commit_enqueue function, must update AST gate in lockstep per PATTERNS.md errata #3)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two-statement post-commit body shape (log + guarded enqueue) gated by AST walker"
    - "Just-INSERTed row id capture via session.flush() inside session.begin() block + locals carried past the commit boundary"
    - "Router-level lazy attribute read getattr(request.app.state, 'arq_pool', None) — keeps test paths that bypass the lifespan safe"

key-files:
  created: []
  modified:
    - "apps/backend/app/api/v1/_internal/yookassa/handlers.py (signature extension + body fill + flush-then-capture pattern in handle_payment_succeeded)"
    - "apps/backend/app/api/v1/_internal/yookassa/router.py (threads request.app.state.arq_pool through to handle_payment_succeeded)"
    - "apps/backend/tests/integration/webhook_yookassa/test_post_commit_seam.py (AST gate renamed in-place + 3 runtime auxiliary tests)"

key-decisions:
  - "Default fiscal_receipt_id=None preserves Phase 50 callsite compatibility (handle_payment_canceled still calls nothing; future Phase 52 notification-only callers can pass fiscal_receipt_id=None without dispatch)"
  - "Router uses getattr(request.app.state, 'arq_pool', None) (not request.app.state.arq_pool directly) so unit tests that bypass the lifespan don't AttributeError"
  - "Capture fr_row from insert_fiscal_receipt + session.flush() to populate server_default=gen_random_uuid() id, then carry the UUID in a local past the session.begin() boundary"
  - "AST gate uses a structural walker (BoolOp(And) + IsNot None compares + locked literal task name + locked _max_tries=3/_expires=60 constants) rather than a string match — preserves the tautology-resistance property from the Plan 50-04 W-2 revision"

patterns-established:
  - "Pattern: post-commit hook structural lockstep — body fill + AST gate flip MUST land in same commit (PATTERNS.md errata #3); enforced by 4 structural assertions in the gate test"
  - "Pattern: capture-then-flush for just-INSERTed rows inside a session.begin() block when the post-commit world needs the server-generated id"

requirements-completed: [FISCAL-05]

# Metrics
duration: ~25min
completed: 2026-05-23
---

# Phase 51 Plan 06: fill _post_commit_enqueue fiscal-dispatch branch + flip AST gate Summary

**`_post_commit_enqueue` now enqueues `dispatch_fiscal_receipt` (max_tries=3, expires=60) when a fiscal_receipts row is present; the AST gate was renamed in-place from `_body_is_only_log_info` to `_dispatches_fiscal_receipt` so the body change and the structural guard land in the SAME commit (PATTERNS.md errata #3).**

## Performance

- **Duration:** ~25 min
- **Tasks:** 1 (atomic body fill + AST gate flip + 3 runtime auxiliary tests, single commit)
- **Files modified:** 3

## Accomplishments
- Extended `_post_commit_enqueue` signature with `fiscal_receipt_id: UUID | None = None` (default `None` preserves Phase 50 callsite shape — `handle_payment_canceled` and tests untouched).
- Filled the body's fiscal-dispatch branch: `if arq_pool is not None and fiscal_receipt_id is not None: await arq_pool.enqueue_job("dispatch_fiscal_receipt", str(fiscal_receipt_id), _max_tries=3, _expires=60)`. Retry contract carried verbatim from D-51-Discretion / Pitfall 11.
- Threaded the just-INSERTed `fiscal_receipts.id` through `handle_payment_succeeded`: capture `fr_row` from `insert_fiscal_receipt`, `await session.flush()` to populate `server_default=gen_random_uuid()`, carry the local `fiscal_receipt_row_id` past the `session.begin()` commit boundary.
- Router now threads `request.app.state.arq_pool` (via `getattr(..., None)` for lifespan-bypass safety) into `handle_payment_succeeded` so the post-commit enqueue actually fires.
- AST gate renamed in-place from `test_post_commit_enqueue_body_is_only_log_info` to `test_post_commit_enqueue_dispatches_fiscal_receipt`; structural walker now asserts exactly 2 non-docstring statements: `Expr(Call(_log.info))` + `If(BoolOp(And, [Compare(arq_pool IsNot None), Compare(fiscal_receipt_id IsNot None)])) → Expr(Await(Call(arq_pool.enqueue_job, ['dispatch_fiscal_receipt', ...], {_max_tries=3, _expires=60})))`. Constants are pinned to the literal AST nodes, not regex string matching — tautology-resistance preserved.
- Added 3 runtime auxiliary tests (`AsyncMock` pool): enqueue fires when `fiscal_receipt_id` present; no enqueue when `fiscal_receipt_id=None`; no enqueue when `arq_pool=None`. These lock the runtime contract alongside the structural AST gate.

## Task Commits

1. **Task 1: Atomic body-fill + AST-gate-flip** — `69cb712` (`feat(51-06): fill _post_commit_enqueue fiscal-dispatch branch + flip AST gate`)

## Files Created/Modified
- `apps/backend/app/api/v1/_internal/yookassa/handlers.py` — `_post_commit_enqueue` signature gains `fiscal_receipt_id`; body adds guarded enqueue; `handle_payment_succeeded` accepts `arq_pool` kwarg, captures `fr_row` + flushes, threads `fiscal_receipt_row_id` to the post-commit hook; module W-4 docstring updated.
- `apps/backend/app/api/v1/_internal/yookassa/router.py` — `payment.succeeded` dispatch branch reads `getattr(request.app.state, 'arq_pool', None)` and threads it to `handle_payment_succeeded` via the new kwarg.
- `apps/backend/tests/integration/webhook_yookassa/test_post_commit_seam.py` — full rewrite: docstring narrates the Plan 50-04 → Plan 51-06 transition; old `test_post_commit_enqueue_body_is_only_log_info` REMOVED; new `test_post_commit_enqueue_dispatches_fiscal_receipt` AST walker asserts the 2-statement shape; 3 runtime aux tests added.

## Decisions Made

- **Default `fiscal_receipt_id=None`**: keeps Phase 50 callsite compatibility (the cancel path doesn't pass one; future Phase 52 NOT-02/NOT-04 enqueue-notification callers can pass `None` here too without firing dispatch).
- **Capture-then-flush for the just-INSERTed id**: `insert_fiscal_receipt` already returns the in-memory row; an explicit `session.flush()` populates `server_default=gen_random_uuid()` so the post-commit code can reference `fr_row.id`.
- **`getattr(request.app.state, 'arq_pool', None)` in router**: explicit default-None keeps tests/code paths that bypass the FastAPI lifespan from `AttributeError` — important because `WorkerSettings.on_startup` in tests does not run.
- **AST structural assertions (not string regex)**: gate walks `BoolOp(And) → [Compare(IsNot None), Compare(IsNot None)]` and pins `_max_tries=3` / `_expires=60` as `ast.Constant` literal values. A future plan that renames `arq_pool` or alters the constants will trip the gate even if the test name is unchanged.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Belt-and-braces auxiliary test removed**
- **Found during:** Task 1 (AST gate flip)
- **Issue:** Drafted a `test_post_commit_enqueue_old_stub_test_name_is_gone` that string-searched its own source for the legacy test name. Because the literal string `"def test_post_commit_enqueue_body_is_only_log_info"` appears inside the assertion itself, the test failed trivially against its own source.
- **Fix:** Removed the redundant aux test; the AST gate already enforces the 2-statement shape (which structurally cannot include the legacy single-statement assertion), so the lockstep guarantee is preserved without it.
- **Files modified:** `apps/backend/tests/integration/webhook_yookassa/test_post_commit_seam.py`
- **Verification:** Remaining 4 tests in the file pass.
- **Committed in:** `69cb712`

**2. [Rule 3 - Blocking] Router signature change (not in plan body)**
- **Found during:** Task 1 (callsite update)
- **Issue:** Plan said the callsite to `_post_commit_enqueue` must pass a real `arq_pool` but did not pick between the two Option A (Depends) / Option B (request.app.state) wiring patterns; needed to choose without further user input.
- **Fix:** Chose Option B (`getattr(request.app.state, "arq_pool", None)`) because (a) other Phase 49/50 code reads `app.state.arq_pool` directly inside the lifespan-registered dispatcher closure (`app/main.py:350`), matching the existing convention; (b) no new `Depends` factory is needed; (c) `getattr` with explicit default keeps test paths that don't run the FastAPI lifespan safe.
- **Files modified:** `apps/backend/app/api/v1/_internal/yookassa/router.py`
- **Verification:** Full 46-test webhook suite green; new runtime auxiliary tests cover the no-pool branch.
- **Committed in:** `69cb712`

---

**Total deviations:** 2 auto-fixed (both Rule 3 — blocking issues during single task).
**Impact on plan:** No scope creep; both fixes are local mechanics of the same atomic commit. The substantive code change (body fill + AST gate flip + callsite update) ships exactly as the plan specified.

## Issues Encountered

- `mypy --strict app/api/v1/_internal/yookassa/handlers.py` surfaces one pre-existing tech-debt warning in `app/modules/online_refunds/settle.py:153` (`unused type: ignore`). Verified pre-existing by `git stash` + re-run on `ad96b71`; out of scope for this plan per the executor scope boundary rule. Should be swept by the v1.9 tech-debt sweep (DEFER-46-04 lineage).

## Threat Flags

None — the change is structurally additive in a previously-stubbed branch; no new network endpoints, auth paths, file access patterns, or schema changes. The threat register entries T-51-06-01..05 from PLAN.md are all mitigated as documented:
- T-51-06-01 (AST gate bypass): the renamed gate asserts the exact structural shape; Phase 52 must update it in lockstep.
- T-51-06-02 (Redis slowness): `_expires=60` drops stale enqueues; runs POST-COMMIT so a failure does not roll back the row.
- T-51-06-03 (double enqueue): plan 51-05's dispatch task is idempotent on `status != STATUS_SENT`.
- T-51-06-04 (race vs commit): hook runs after `async with session.begin()` exits.
- T-51-06-05 (info disclosure): UUIDs are not PII.

## Known Stubs

None. DEFER-50-04 is closed by this commit. Phase 52 NOT-02 (refund DM) and NOT-04 (fiscal-failure DM) branches remain deliberate scope deferrals — documented in the plan's `<must_haves>` and in the new `_post_commit_enqueue` docstring (not stubs, just out-of-scope branches).

## Verification

- `cd apps/backend && uv run pytest tests/integration/webhook_yookassa/ -x -q` → **46 passed in 12.21s**
- `cd apps/backend && uv run ruff check app/api/v1/_internal/yookassa/ tests/integration/webhook_yookassa/test_post_commit_seam.py` → **All checks passed**
- `cd apps/backend && uv run mypy --strict app/api/v1/_internal/yookassa/handlers.py app/api/v1/_internal/yookassa/router.py` → only the pre-existing `settle.py:153` warning (out of scope; verified pre-existing on `ad96b71`)
- All acceptance grep gates green:
  - `fiscal_receipt_id: UUID | None = None` ✓
  - `arq_pool.enqueue_job` ✓
  - `"dispatch_fiscal_receipt"` ✓
  - `_max_tries=3` + `_expires=60` ✓
  - `test_post_commit_enqueue_body_is_only_log_info` no longer present ✓
  - `test_post_commit_enqueue_dispatches_fiscal_receipt` present ✓

## Self-Check: PASSED

- `apps/backend/app/api/v1/_internal/yookassa/handlers.py` — modified, present.
- `apps/backend/app/api/v1/_internal/yookassa/router.py` — modified, present.
- `apps/backend/tests/integration/webhook_yookassa/test_post_commit_seam.py` — modified, present.
- Commit `69cb712` — present in `git log`.

## Next Phase Readiness

- Phase 51-07 (receipt webhook handlers) already shipped on this branch's base — no impact.
- Phase 51-09 (poll_pending_refunds cron) — orthogonal; can proceed.
- Phase 51-10 (E2E milestone verification) — payment.succeeded webhook now drives a REAL `dispatch_fiscal_receipt` enqueue against the ARQ worker. Verification can exercise the full chain end-to-end.
- Phase 52 NOT-02 / NOT-04 — must update the AST gate in lockstep when adding notification branches to `_post_commit_enqueue` (gate will FAIL on any structural drift, which is the desired forcing function).

---
*Phase: 51-fiscal-fsm-refunds*
*Completed: 2026-05-23*
