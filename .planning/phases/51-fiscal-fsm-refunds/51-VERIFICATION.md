---
phase: 51-fiscal-fsm-refunds
verified: 2026-05-23T16:45:00Z
status: passed
score: 6/6 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 5/6
  gaps_closed:
    - "handle_refund_succeeded now calls _post_commit_enqueue post-commit with fiscal_receipt_id from SettledRefundLocals; dispatch_fiscal_receipt is enqueued for the refund-side fiscal_receipts row (commit 9e19ef1)"
  gaps_remaining: []
  regressions: []
---

# Phase 51: Fiscal FSM + Refunds Verification Report

**Phase Goal:** Fiscal receipt status is tracked end-to-end with ARQ retry and a circuit breaker; operator can initiate a full online refund that completes when `refund.succeeded` arrives
**Verified:** 2026-05-23T16:45:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure (commit 9e19ef1)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `receipt.succeeded` webhook transitions `fiscal_receipts.status` from `sent` to `succeeded`; `receipt.canceled` transitions to `failed` | ✓ VERIFIED | `handlers.py:860` sets `row.status = FR_STATUS_SUCCEEDED`; `handlers.py:975` sets `row.status = FR_STATUS_FAILED`. FSM guard via `_assert_can_transition_receipt` using `FISCAL_RECEIPT_STATUS_TRANSITIONS`. 5 integration tests in `test_handle_receipt_succeeded.py` + 4 in `test_handle_receipt_canceled.py` exercise both paths. |
| 2 | `dispatch_fiscal_receipt` ARQ task retries up to 3 times with exponential backoff; Redis circuit breaker `sz:yookassa:circuit:receipts` opens on repeated failures | ✓ VERIFIED | `tasks.py:63-64` declares `_MAX_TRIES=3` and `_BACKOFF_BASE_SECONDS=(30,120,600)`. `circuit_breaker.py:41-44` uses key prefix `sz:yookassa:circuit:receipts`. `tasks.py:262-264` checks `is_circuit_open` at head-of-body and raises `Retry(defer=300)`. `tasks.py:333` calls `record_failure()` on transient errors. Unit tests in `test_yookassa_circuit_breaker.py` verify threshold logic. |
| 3 | ARQ cron `monitor_stale_fiscal_receipts` detects `fiscal_receipts.status='pending'` rows older than 90 seconds and emits a `fiscal_receipt_failed` audit event | ✓ VERIFIED | `service.py:38` sets `_STALE_PENDING_SECONDS=90`. `service.py:65-92` scans for `status='pending' AND created_at < cutoff` via FOR UPDATE SKIP LOCKED. Emits `fiscal_receipt_failed` audit inside the same `session.begin()` block. Wired in `workers/__init__.py:106,230-236`. Integration tests in `test_monitor_stale_cron.py` exercise the 90s boundary. |
| 4 | `POST /api/v1/online-payments/memberships/{id}/refund` returns 202 and a refund row is created; endpoint is analogous for PT-packages | ✓ VERIFIED | `router.py:420-465` defines `refund_membership_online` with `status_code=HTTP_202_ACCEPTED`. `router.py:468-503` defines `refund_pt_package_online`. Both delegate to `initiate_online_refund()` which calls ЮKassa, INSERTs `online_refunds` row with `status='pending'`, and commits. Test `test_initiate_membership_refund.py:65` asserts `response.status_code == 202`. |
| 5 | `refund.succeeded` webhook atomically: writes a refund row to `payments`, transitions membership/PT-package to `refunded`, inserts `fiscal_receipts(kind='refund')`, **and enqueues dispatch_fiscal_receipt post-commit** | ✓ VERIFIED | **Gap closed by commit 9e19ef1.** `_settle_online_refund` returns `SettledRefundLocals(fiscal_receipt_id, online_payment_id, subject_kind, subject_id)`. `handle_refund_succeeded` captures this in `settled_locals` and — after the `async with session.begin()` commit boundary — calls `_post_commit_enqueue(arq_pool, ..., fiscal_receipt_id=settled_locals.fiscal_receipt_id)` (handlers.py lines 808-815). `router.py:133` threads `request.app.state.arq_pool` into the handler (symmetric to payment.succeeded). `_poll_pending_refunds` also accepts `arq_pool` and enqueues post-commit for cron-path settles (cron.py:136-142). New test `test_handle_refund_succeeded_enqueues_dispatch_fiscal_receipt_post_commit` (test_handle_refund_succeeded.py:820-894) mounts a spy AsyncMock on `app.state.arq_pool` and asserts `enqueue_job` was awaited once with `("dispatch_fiscal_receipt", str(fr_id), _max_tries=3, _expires=60)`. |
| 6 | ARQ cron `poll_pending_refunds` runs every 30 minutes and reconciles any refund row with `status='pending'` older than 30 minutes by calling `GET /v3/refunds/{id}` | ✓ VERIFIED | `cron.py:47` sets `_PENDING_AGE_MINUTES=30`. `cron.py:92-178` iterates over `select_pending_older_than(cutoff=cutoff, limit=50)` and calls `yookassa_client.get_refund()` per row. Wired in `workers/__init__.py:107,237-248`. 6 integration tests in `test_poll_pending_refunds_cron.py`. |

**Score:** 6/6 truths verified

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | Telegram DM notifications for refund events (NOT-02) | Phase 52 | deferred-items.md line 82: `NOT-02, NOT-04 notification branches (Telegram DM on payment events) → Phase 52` |
| 2 | Email notifications for refund events (NOT-04) | Phase 52 | ROADMAP.md Phase 52 success criteria |
| 3 | Orphan refund webhook reconciliation (DEFER-51-01) | Phase 53 | deferred-items.md: "When ЮKassa sends refund.succeeded for a refund whose OnlineRefund row does not exist" |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/alembic/versions/0037_online_refunds.py` | online_refunds migration with 3 UNIQUEs | ✓ VERIFIED | `down_revision="0036_payments_received_by_user_id_nullable"`, 3 UNIQUEs (yookassa_refund_id, idempotency_key, partial on online_payment_id), 2 CHECKs, 4 FKs with RESTRICT |
| `apps/backend/app/modules/online_refunds/` | Module package (constants, models, repository, schemas, service, settle, cron) | ✓ VERIFIED | All 8 files present and substantive |
| `apps/backend/app/modules/fiscal_receipts/tasks.py` | ARQ dispatch task with retry/circuit breaker | ✓ VERIFIED | `dispatch_fiscal_receipt` with `_MAX_TRIES=3`, exponential backoff, circuit breaker check at head-of-body |
| `apps/backend/app/integrations/yookassa/circuit_breaker.py` | Redis sliding-window circuit breaker | ✓ VERIFIED | Key `sz:yookassa:circuit:receipts`, threshold=5/60s, open TTL=300s |
| `apps/backend/app/workers/scheduled/monitor_stale_fiscal_receipts.py` | ARQ cron for stale fiscal receipts | ✓ VERIFIED | Delegates to `_monitor_stale_fiscal_receipts` in fiscal_receipts.service |
| `apps/backend/app/workers/scheduled/poll_pending_refunds.py` | ARQ cron for pending refunds | ✓ VERIFIED | Delegates to `_poll_pending_refunds`; now threads `ctx['redis']` as arq_pool for post-settle enqueue |
| `apps/backend/app/modules/online_refunds/settle.py` | Shared atomic settle UoW helper returning SettledRefundLocals | ✓ VERIFIED | Returns `SettledRefundLocals(fiscal_receipt_id, online_payment_id, subject_kind, subject_id)` for post-commit enqueue |
| `apps/backend/app/api/v1/_internal/yookassa/handlers.py` | 3 new webhook handlers; handle_refund_succeeded enqueues post-commit | ✓ VERIFIED | `settled_locals` captured from `_settle_online_refund`; `_post_commit_enqueue` called post-commit with `fiscal_receipt_id` |
| `apps/backend/app/api/v1/_internal/yookassa/router.py` | arq_pool threaded into handle_refund_succeeded | ✓ VERIFIED | `refund.succeeded` branch reads `arq_pool = getattr(request.app.state, "arq_pool", None)` at line 133, symmetric to payment.succeeded |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `router.py` | `handle_refund_succeeded` | `elif event_type == "refund.succeeded"` | ✓ WIRED | Line 127 |
| `router.py` | `handle_receipt_succeeded` | `elif event_type == "receipt.succeeded"` | ✓ WIRED | Line 137 |
| `router.py` | `handle_receipt_canceled` | `elif event_type == "receipt.canceled"` | ✓ WIRED | Line 142 |
| `router.py` | `arq_pool → handle_refund_succeeded` | `getattr(request.app.state, "arq_pool", None)` at line 133 | ✓ WIRED | Symmetric to payment.succeeded branch; threads arq_pool for post-commit enqueue |
| `handle_refund_succeeded` | `_settle_online_refund` | delegation, returns SettledRefundLocals | ✓ WIRED | Lines 770-780; return value captured in `settled_locals` |
| `handle_refund_succeeded` | `_post_commit_enqueue` | `if settled_locals is not None` guard, lines 808-815 | ✓ WIRED | Runs after `async with session.begin()` commit boundary; enqueues `dispatch_fiscal_receipt` with `fiscal_receipt_id=settled_locals.fiscal_receipt_id` |
| `_settle_online_refund` | `fiscal_receipts.insert_fiscal_receipt` | step 8 | ✓ WIRED | `fr_row = await insert_fiscal_receipt(session, kind=KIND_REFUND, status=STATUS_SENT, ...)` |
| `_settle_online_refund` | `SettledRefundLocals` return | `return SettledRefundLocals(fiscal_receipt_id=fr_row.id, ...)` | ✓ WIRED | Post-flush so `fr_row.id` is populated by server_default gen_random_uuid() |
| `_poll_pending_refunds` | `arq_pool.enqueue_job` | `if settled_locals is not None and arq_pool is not None` (cron.py:136-142) | ✓ WIRED | Cron path mirrors webhook path for 54-ФЗ compliance |
| `poll_pending_refunds` ARQ wrapper | `_poll_pending_refunds arq_pool` | `arq_pool = ctx.get("redis")` (poll_pending_refunds.py:50) | ✓ WIRED | ARQ injects `ctx['redis']` for cron jobs |
| `handle_payment_succeeded` | `_post_commit_enqueue` | line 506 | ✓ WIRED | Payment-side fiscal dispatch enqueued post-commit (unchanged) |
| `dispatch_fiscal_receipt` | `circuit_breaker.is_circuit_open` | line 262 | ✓ WIRED | Head-of-body check |
| `dispatch_fiscal_receipt` | `circuit_breaker.record_failure` | line 333 | ✓ WIRED | On transient error |
| `workers/__init__.py` | `dispatch_fiscal_receipt` in `functions` | line 137 | ✓ WIRED | ARQ can dispatch the task |
| `workers/__init__.py` | `monitor_stale_fiscal_receipts` in `cron_jobs` | lines 230-236 | ✓ WIRED | Every 15 min |
| `workers/__init__.py` | `poll_pending_refunds` in `cron_jobs` | lines 237-248 | ✓ WIRED | Every 30 min |
| `FiscalReceiptDispatcher` slot | real impl (`arq_pool.enqueue_job`) | `main.py:341-358` + `workers/__init__.py:340-356` | ✓ WIRED | REG-29-03 double-wire present in both composition roots |
| `online_payments/router.py` | `online_refunds_service.initiate_online_refund` | import line 77, calls at lines 457, 495 | ✓ WIRED | POST refund endpoints delegate correctly |
| `.importlinter` | online_refunds cross-module edges | commit 10388b0 | ✓ WIRED | `uv run lint-imports` → 3 kept, 0 broken |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `dispatch_fiscal_receipt` | `fr_row.kind`, `customer_email`, `yookassa_object_id`, `amount_kopecks` | DB query via `fiscal_repo.get_fiscal_receipt_by_id` + `_resolve_yookassa_object_id` + `_resolve_amount_kopecks` | Yes — real DB reads, abs() applied to amount | ✓ FLOWING |
| `_monitor_stale_fiscal_receipts` | `rows` (FiscalReceipt list) | `SELECT ... WHERE status='pending' AND created_at < cutoff FOR UPDATE SKIP LOCKED LIMIT 50` | Yes — real DB query | ✓ FLOWING |
| `_poll_pending_refunds` | `row_refund_ids` | `select_pending_older_than(cutoff, limit=50)` FOR UPDATE SKIP LOCKED | Yes — real DB query | ✓ FLOWING |
| `initiate_online_refund` | `result.refund_id`, row data | `yookassa_client.create_refund()` + DB insert | Yes — ЮKassa API call + insert | ✓ FLOWING |
| `_resolve_refund_id_via_db_join` | `online_refund.yookassa_refund_id` | DB join: Payment → OnlineRefund by `original_payment_id` | Yes — but missing ORDER BY/LIMIT 1 (CR-03 risk) | ⚠ HOLLOW — could return wrong row when multiple refunds share same `original_payment_id` |

### Behavioral Spot-Checks

Step 7b: SKIPPED — no runnable entry points without a live database. The phase has extensive integration tests verified against a test database.

### Probe Execution

Step 7c: No phase-declared probes found in PLAN or SUMMARY files.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| FISCAL-04 | 51-07 | `handle_receipt_webhook()` processes `receipt.succeeded` / `receipt.canceled` FSM transitions | ✓ SATISFIED | `handlers.py`: `handle_receipt_succeeded` (sent→succeeded) + `handle_receipt_canceled` (sent→failed) with FSM guards |
| FISCAL-05 | 51-05, 51-06 | `dispatch_fiscal_receipt` ARQ task with max_tries=3, exponential backoff, circuit breaker | ✓ SATISFIED | `tasks.py`: `_MAX_TRIES=3`, `_backoff_with_jitter`, `is_circuit_open` head-of-body check, `record_failure` on transient |
| FISCAL-06 | 51-09 | ARQ cron `monitor_stale_fiscal_receipts` — 90s pending detection + `fiscal_receipt_failed` audit | ✓ SATISFIED | `service.py:_monitor_stale_fiscal_receipts`, wired in `workers/__init__.py`, cron every 15 min |
| FISCAL-07 | 51-05 | `YOOKASSA_TAX_SYSTEM_CODE` + `YOOKASSA_VAT_CODE` read from `YooKassaSettings` (never hardcoded) | ✓ SATISFIED | `tasks.py:298-300`: `settings = YooKassaSettings()`, `tax_system_code = int(settings.tax_system_code)`, `vat_code = VatCode(int(settings.default_vat_code))` |
| REFUND-01 | 51-08 | `POST /memberships/{id}/refund` + `POST /pt-packages/{id}/refund` — returns 202, creates OnlineRefund row | ✓ SATISFIED | `router.py:420-503`, `service.py:initiate_online_refund`, tests assert 202 + DB row |
| REFUND-02 | 51-07 | `handle_refund_webhook()` atomic UoW: payments INSERT + subject cancelled + fiscal_receipts INSERT + dispatch_fiscal_receipt enqueued post-commit | ✓ SATISFIED | Atomic UoW verified. `dispatch_fiscal_receipt` enqueued post-commit via `_post_commit_enqueue` with `fiscal_receipt_id` (commit 9e19ef1). New integration test asserts enqueue with correct args. |
| REFUND-03 | 51-07, 51-08 | Idempotent replay: duplicate POST returns same refund ID; webhook replay returns 200 silently | ✓ SATISFIED | Partial UNIQUE `uq_online_refunds_alive_per_online_payment` + idempotency_key lookup prevents duplicate INSERTs. `uq_payments_refund_of_alive` provides second layer for webhook replay. Tests: `test_initiate_membership_refund.py:163-204` + `test_e2e_refund_full_cycle.py:542-599` + `test_handle_refund_succeeded.py:536-615` |
| REFUND-04 | 51-09 | `poll_pending_refunds` ARQ cron — 30 min, calls `GET /v3/refunds/{id}` for stale pending rows | ✓ SATISFIED | `cron.py:_poll_pending_refunds`, wired in `workers/__init__.py`, cron every 30 min, 6 integration tests |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `fiscal_receipts/tasks.py` | 218, 243 | `_terminal_failure`: `async with session_factory() as session:` without `session.begin()`, uses `session.commit()` directly | ⚠ WARNING | CR-02: violates project convention D-32-10; relies on SQLAlchemy autobegin which works in practice but is fragile |
| `fiscal_receipts/tasks.py` | 366, 393 | Success path: same `session.commit()` without `session.begin()` pattern | ⚠ WARNING | CR-04: same as CR-02 plus missing concurrent-update guard for status change between the two sessions |
| `fiscal_receipts/tasks.py` | 177-183 | `_resolve_refund_id_via_db_join`: no `ORDER BY` or `LIMIT 1` on OnlineRefund query | ⚠ WARNING | CR-03: nondeterministic row selection if multiple OnlineRefund rows share the same `original_payment_id`; potential 54-ФЗ receipt-to-wrong-refund data integrity risk |
| `online_refunds/settle.py` | 251 | `amount_kopecks=refund_payment.amount_kopecks` passes negative value to `OnlinePaymentRefundedPayload` | ⚠ WARNING | CR-05: audit trail stores negative amount; Phase 52 notification consumers expecting positive amount will receive negative value |
| `online_refunds/cron.py` | 154-155 | Redundant `row.status = STATUS_CANCELED` after `refund_repo.mark_canceled()` already sets it | ℹ INFO | IN-01: dead code; minor noise |

**No TBD/FIXME/XXX debt markers found in Phase 51 files.**

### Human Verification Required

None. All must-haves are verified programmatically.

### Gaps Summary

All 6 success criteria are now verified. The SC5 gap (refund-side fiscal receipt not enqueued for dispatch) was closed by commit 9e19ef1:

- `_settle_online_refund` returns `SettledRefundLocals` carrying `fiscal_receipt_id`.
- `handle_refund_succeeded` captures the return value and calls `_post_commit_enqueue` after the commit boundary, enqueuing `dispatch_fiscal_receipt` with `_max_tries=3, _expires=60`.
- `router.py` threads `arq_pool` into `handle_refund_succeeded` symmetrically to the payment.succeeded branch.
- `_poll_pending_refunds` and its ARQ wrapper also thread arq_pool for cron-path settles.
- A new integration test (`test_handle_refund_succeeded_enqueues_dispatch_fiscal_receipt_post_commit`) directly asserts the enqueue via a spy mock.

**Carry-forward WARNING items (not blocking):** CR-02/CR-04 (missing `session.begin()` in tasks.py terminal/success paths), CR-03 (missing ORDER BY/LIMIT 1 in refund-id join), CR-05 (negative amount in audit payload). These should be addressed before Phase 53 verification.

---

_Verified: 2026-05-23T16:45:00Z_
_Re-verified: 2026-05-23T16:45:00Z (SC5 gap closure — commit 9e19ef1)_
_Verifier: Claude (gsd-verifier)_
