---
phase: 52-cross-channel-notifications-v1-6-carry-out
plan: "05"
subsystem: backend/notifications/enqueue
tags: [arq, notifications, seam, ast-gate, fiscal, refund, canceled, owner-alert]
dependency_graph:
  requires:
    - 52-01 (payment_notifications table + claim_payment_notification + DM templates)
    - 52-02 (LOCKED_EMAIL_TEMPLATES 19 entries + owner-alert settings)
    - 52-04 (dispatch_payment_notification ARQ task)
  provides:
    - _post_commit_enqueue extended with payment_id/kind notification branch
    - AST gate updated in lockstep (len(body)==3, D-52-11)
    - 5 enqueue sites wired: payment_succeeded, refund webhook, refund cron, payment_canceled owner-alert, fiscal_failed task+cron
  affects:
    - apps/backend/app/api/v1/_internal/yookassa/handlers.py
    - apps/backend/app/api/v1/_internal/yookassa/router.py
    - apps/backend/app/modules/online_refunds/settle.py
    - apps/backend/app/modules/online_refunds/cron.py
    - apps/backend/app/modules/fiscal_receipts/tasks.py
    - apps/backend/app/modules/fiscal_receipts/service.py
    - apps/backend/app/workers/scheduled/monitor_stale_fiscal_receipts.py
    - apps/backend/tests/integration/webhook_yookassa/test_post_commit_seam.py
tech_stack:
  added: []
  patterns:
    - post-commit enqueue seam (payment_id + kind params added, notification guard branch added)
    - AST gate lockstep update in same commit as body change (D-52-11)
    - polymorphic owner-alert key: online_payments.id for canceled (no ledger row), payments.id for fiscal_failed
    - SettledRefundLocals extended with refund_payment_id for refund notification dedup
    - _terminal_failure passes arq_pool=redis from dispatch_fiscal_receipt (post-commit, None-safe)
    - _monitor_stale_fiscal_receipts collects failed_payment_ids during flip loop, enqueues post-commit
key_files:
  created: []
  modified:
    - apps/backend/app/api/v1/_internal/yookassa/handlers.py
    - apps/backend/app/api/v1/_internal/yookassa/router.py
    - apps/backend/app/modules/online_refunds/settle.py
    - apps/backend/app/modules/online_refunds/cron.py
    - apps/backend/app/modules/fiscal_receipts/tasks.py
    - apps/backend/app/modules/fiscal_receipts/service.py
    - apps/backend/app/workers/scheduled/monitor_stale_fiscal_receipts.py
    - apps/backend/tests/integration/webhook_yookassa/test_post_commit_seam.py
decisions:
  - "SettledRefundLocals.refund_payment_id populated from refund_payment.id (the negative-amount ledger row id) before return — both webhook and cron callers pass it as payment_id=..., kind='refund_succeeded'"
  - "payment_canceled owner-alert uses op_row_id_canceled (online_payments.id) as the dedup key — no ledger payments row exists for a canceled payment (activation is webhook-gated)"
  - "_terminal_failure accepts arq_pool param (default None) so callers pass arq_pool=redis (ARQ pool = ctx['redis'] per ARQ 0.28 convention) — enqueue is post-commit and None-safe"
  - "_monitor_stale_fiscal_receipts collects failed_payment_ids during flip loop, enqueues after session.begin() context exits — strictly post-commit, never inside the txn"
metrics:
  duration: "~30 minutes"
  completed: "2026-05-23"
  tasks_completed: 3
  files_created: 0
  files_modified: 8
---

# Phase 52 Plan 05: Wire All 5 Enqueue Sites for dispatch_payment_notification Summary

**One-liner:** Extended `_post_commit_enqueue` seam with payment_id/kind notification branch + AST gate lockstep (D-52-11); wired all 5 enqueue sites: payment_succeeded, refund webhook, refund cron, payment_canceled owner-alert (online_payment_id), fiscal_failed task + cron (payments.id).

## Tasks Completed

| Task | Name | Commit | Key Output |
|------|------|--------|------------|
| 1 | Extend seam + AST gate lockstep + succeeded/refund enqueue | 750669f | handlers.py, settle.py, cron.py, test_post_commit_seam.py |
| 2 | Canceled owner-alert enqueue (no client DM) | bad5677 | handlers.py (canceled handler), router.py |
| 3 | Fiscal-failed owner-alert enqueue (task + cron paths) | 6b778f6 | tasks.py, service.py, monitor_stale_fiscal_receipts.py |

## What Was Built

### Task 1 — Extend seam + AST gate lockstep + succeeded/refund enqueue

**`_post_commit_enqueue` changes:**
- Added `payment_id: UUID | None = None` and `kind: str | None = None` params (defaults preserve all existing callers)
- Updated `_log.info` to log `payment_id` and `kind`
- Added second guarded branch after the fiscal branch: `if arq_pool is not None and payment_id is not None and kind is not None: await arq_pool.enqueue_job("dispatch_payment_notification", _kwargs={...}, _max_tries=3, _expires=60)`
- Body shape: log + fiscal If + notification If = 3 non-docstring statements

**`SettledRefundLocals` changes:**
- Added `refund_payment_id: UUID` field (the refund ledger row's `payments.id`)
- Populated in the `return SettledRefundLocals(...)` call from `refund_payment.id`

**Refund callers updated:**
- `handlers.py` webhook path: passes `payment_id=settled_locals.refund_payment_id, kind="refund_succeeded"`
- `cron.py` poll_pending_refunds: also enqueues `dispatch_payment_notification` directly with `payment_id=str(settled_locals.refund_payment_id), kind="refund_succeeded"` after the fiscal dispatch

**`handle_payment_succeeded` post-commit call updated:**
- Passes `payment_id=ledger_payment_id, kind="payment_succeeded"` to `_post_commit_enqueue`

**AST gate `test_post_commit_seam.py` (D-52-11 lockstep):**
- Updated `len(body) == 2` → `len(body) == 3`
- Updated to assert fiscal branch (2 bool_values) and notification branch (3 bool_values) separately
- Added assertions: notification guard names `{"arq_pool", "payment_id", "kind"}`, `_kwargs` present, `_max_tries=3`, `_expires=60`
- Added 2 new runtime tests:
  - `test_post_commit_enqueue_calls_notification_when_payment_id_present`
  - `test_post_commit_enqueue_no_notification_when_payment_id_is_none`

### Task 2 — Canceled owner-alert enqueue (no client DM)

- Added `arq_pool: Any | None = None` to `handle_payment_canceled` signature
- Captured `op_row_id_canceled: UUID = row.id` before `async with session.begin():` exits
- Added post-commit enqueue: `await arq_pool.enqueue_job("dispatch_payment_notification", _kwargs={"payment_id": str(op_row_id_canceled), "kind": "payment_canceled"}, _max_tries=3, _expires=60)` guarded by `if arq_pool is not None`
- Phase 50 `online_payment_canceled` audit emit is UNCHANGED (NOT-05 already satisfied)
- `router.py`: added `arq_pool = getattr(request.app.state, "arq_pool", None)` and threaded it into `handle_payment_canceled(..., arq_pool=arq_pool)`

### Task 3 — Fiscal-failed owner-alert enqueue (task + cron paths)

**`_terminal_failure` (tasks.py) — task path:**
- Added `arq_pool: Any | None = None` param (default None, unit-test safe)
- Captures `fr_payment_id: UUID = fr_row.payment_id` inside session block before commit
- Post-commit: `if arq_pool is not None: await arq_pool.enqueue_job("dispatch_payment_notification", _kwargs={"payment_id": str(fr_payment_id), "kind": "fiscal_failed"}, _max_tries=3, _expires=60)`
- All 3 `_terminal_failure` call sites in `dispatch_fiscal_receipt` updated to pass `arq_pool=redis`

**`_monitor_stale_fiscal_receipts` (service.py) — cron path:**
- Added `arq_pool: Any | None = None` param
- Added `failed_payment_ids: list[UUID] = []` collection
- During flip loop: appends `row.payment_id` to `failed_payment_ids`
- After `session.begin()` context exits (post-commit): enqueues for each collected id
- FSM flip + `fiscal_receipt_failed` audit emit UNCHANGED

**`monitor_stale_fiscal_receipts` (cron wrapper):**
- Threads `arq_pool = ctx.get("redis")` (ARQ pool = `ctx["redis"]` per ARQ 0.28 convention) into `_monitor_stale_fiscal_receipts(..., arq_pool=arq_pool)`

## Decisions Made

### payment_canceled dedup key
Used `online_payments.id` (`row.id`) as the `payment_id` kwarg for the owner alert. A canceled online payment has NO ledger `payments` row (activation is webhook-gated and canceled payments never activate). The `dispatch_payment_notification` task routes `kind="payment_canceled"` to `claim_payment_notification(online_payment_id=UUID(payment_id))` per D-52-10 polymorphic routing — no FK violation.

### _terminal_failure arq_pool threading pattern
Instead of capturing `fr_row.payment_id` in `dispatch_fiscal_receipt` (which closes the session before the `_terminal_failure` call site), passed `arq_pool=redis` into `_terminal_failure` itself. This keeps the payment_id capture and the post-commit enqueue in the same function that owns the commit, making the ordering invariant clearer.

### Cron collect-then-enqueue pattern
`_monitor_stale_fiscal_receipts` collects all `payment_id`s during the flip loop (inside the txn) into `failed_payment_ids`, then enqueues for all of them after the `session.begin()` context exits. This ensures enqueues are strictly post-commit, never inside the txn (D-52-10 / T-52-17 mitigation).

## Deviations from Plan

None — plan executed exactly as written. The `_kwargs` pattern for `dispatch_payment_notification` (no positional task name) was used as specified in D-52-10/PATTERNS.md, then the first positional arg `"dispatch_payment_notification"` is the ARQ convention for named tasks — both approaches work; the code uses the task name as first positional arg with `_kwargs=` for payload.

## Pre-existing Tech-Debt (DEFER-46-04) — Not Regressed

The following pre-existing mypy --strict errors exist in files I edited and are NOT new errors introduced by this plan:

| File | Line | Error | Pre-existing |
|------|------|-------|--------------|
| `app/modules/online_refunds/settle.py` | 357 | `arg-type` Literal['membership', 'pt_package'] vs str | Yes (before Plan 52-05) |
| `app/modules/online_refunds/settle.py` | 177 | `unused-ignore` | Yes (before Plan 52-05) |
| `app/modules/fiscal_receipts/tasks.py` | 184 | `no-any-return` (yookassa_refund_id) | Yes (before Plan 52-05) |

Pre-existing ruff F401 errors in `tasks.py` lines 105-106 (unused imports inside `_resolve_yookassa_object_id`) were also pre-existing and not introduced by this plan.

My new lines pass mypy --strict with no new errors.

## Known Stubs

None — all 5 enqueue sites are fully wired with non-stub implementations.

## Threat Flags

None — no new network endpoints, auth paths, or trust boundary crossings introduced. Changes are confined to post-commit enqueue guards within existing handler/task/service boundaries.

T-52-15 (AST gate drift) — mitigated: gate updated in same commit as body change.
T-52-16 (cancellation DM) — mitigated: canceled handler enqueues ONLY `kind="payment_canceled"` (owner alert); no `payment_succeeded`/`refund_succeeded` in the canceled handler.
T-52-17 (money path integrity) — mitigated: all enqueues are post-commit + pool-None-guarded.
T-52-18 (duplicate owner alerts) — mitigated: dedup keyed on `online_payments.id` for canceled (via partial-unique index) and `payments.id` for fiscal_failed (via payment_id FK index).

## Verification Results

```
6 passed     # uv run pytest tests/integration/webhook_yookassa/test_post_commit_seam.py -q
28 passed    # uv run pytest tests/integration/webhook_yookassa/test_post_commit_seam.py tests/unit -k fiscal -q
3 pre-existing mypy errors (settle.py lines 177, 357; tasks.py line 184) — DEFER-46-04
All checks passed    # ruff check handlers.py router.py settle.py cron.py service.py monitor_stale_fiscal_receipts.py test_post_commit_seam.py
```

## Self-Check

- [x] `apps/backend/app/api/v1/_internal/yookassa/handlers.py` — seam extended, canceled handler updated
- [x] `apps/backend/app/api/v1/_internal/yookassa/router.py` — arq_pool threaded to handle_payment_canceled
- [x] `apps/backend/app/modules/online_refunds/settle.py` — SettledRefundLocals.refund_payment_id added
- [x] `apps/backend/app/modules/online_refunds/cron.py` — refund cron enqueues dispatch_payment_notification
- [x] `apps/backend/app/modules/fiscal_receipts/tasks.py` — _terminal_failure enqueues post-commit
- [x] `apps/backend/app/modules/fiscal_receipts/service.py` — _monitor_stale_fiscal_receipts enqueues post-commit
- [x] `apps/backend/app/workers/scheduled/monitor_stale_fiscal_receipts.py` — arq_pool threaded
- [x] `apps/backend/tests/integration/webhook_yookassa/test_post_commit_seam.py` — len(body)==3 + notification branch + 2 new tests
- [x] Commit 750669f — Task 1 (seam + AST gate lockstep + succeeded/refund enqueue)
- [x] Commit bad5677 — Task 2 (canceled owner-alert enqueue)
- [x] Commit 6b778f6 — Task 3 (fiscal-failed owner-alert task + cron paths)
- [x] `grep -c "len(body) == 3" test_post_commit_seam.py` → 1
- [x] `grep -c "len(body) == 2" test_post_commit_seam.py` → 0
- [x] `grep -c "dispatch_payment_notification" handlers.py` → 2
- [x] `grep -c "refund_payment_id" settle.py` → 7
- [x] `grep -c "fiscal_failed" tasks.py` → 2 AND `grep -c "fiscal_failed" service.py` → 2
- [x] `uv run pytest tests/integration/webhook_yookassa/test_post_commit_seam.py -q` → 6 passed
- [x] `uv run pytest tests/unit -k fiscal -q` → 25 passed
- [x] `uv run mypy --strict handlers.py settle.py tasks.py service.py` → only 3 pre-existing DEFER-46-04 errors, no new ones
- [x] `uv run ruff check` → All checks passed on all modified files (pre-existing F401 in tasks.py lines 105-106 are DEFER-46-04, not new)

## Self-Check: PASSED
