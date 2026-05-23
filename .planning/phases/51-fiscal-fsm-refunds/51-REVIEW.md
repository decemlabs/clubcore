---
phase: 51-fiscal-fsm-refunds
reviewed: 2026-05-23T00:00:00Z
depth: standard
files_reviewed: 27
files_reviewed_list:
  - apps/backend/alembic/versions/0037_online_refunds.py
  - apps/backend/alembic/versions/0038_fiscal_receipts_created_at.py
  - apps/backend/app/api/v1/_internal/yookassa/handlers.py
  - apps/backend/app/api/v1/_internal/yookassa/router.py
  - apps/backend/app/core/audit.py
  - apps/backend/app/core/audit_payloads.py
  - apps/backend/app/core/dependencies.py
  - apps/backend/app/integrations/yookassa/circuit_breaker.py
  - apps/backend/app/integrations/yookassa/client.py
  - apps/backend/app/integrations/yookassa/types.py
  - apps/backend/app/main.py
  - apps/backend/app/modules/fiscal_receipts/models.py
  - apps/backend/app/modules/fiscal_receipts/service.py
  - apps/backend/app/modules/fiscal_receipts/tasks.py
  - apps/backend/app/modules/online_payments/router.py
  - apps/backend/app/modules/online_refunds/__init__.py
  - apps/backend/app/modules/online_refunds/constants.py
  - apps/backend/app/modules/online_refunds/cron.py
  - apps/backend/app/modules/online_refunds/models.py
  - apps/backend/app/modules/online_refunds/repository.py
  - apps/backend/app/modules/online_refunds/schemas.py
  - apps/backend/app/modules/online_refunds/service.py
  - apps/backend/app/modules/online_refunds/settle.py
  - apps/backend/app/modules/payments/service.py
  - apps/backend/app/workers/__init__.py
  - apps/backend/app/workers/scheduled/monitor_stale_fiscal_receipts.py
  - apps/backend/app/workers/scheduled/poll_pending_refunds.py
findings:
  critical: 5
  warning: 7
  info: 3
  total: 15
status: issues_found
---

# Phase 51: Code Review Report

**Reviewed:** 2026-05-23T00:00:00Z
**Depth:** standard
**Files Reviewed:** 27
**Status:** issues_found

## Summary

Phase 51 ships the online-refund lifecycle (REFUND-01..04), 54-ФЗ fiscal-receipt dispatch (FISCAL-05/06), refund/receipt webhook handlers (D-51-11/21/22), and two ARQ crons (monitor_stale_fiscal_receipts, poll_pending_refunds). The overall architecture is sound — atomic UoW discipline, SKIP LOCKED loop budgets, and circuit-breaker wiring are all present.

Five blockers were found:

1. A session-atomicity gap in `handle_refund_succeeded`: the `AlreadyRefundedError / IntegrityError` catch wraps the entire `async with session.begin()` block, but the underlying `session` is tainted after the rollback and the orphan-path audit emit (`idempotency_outcome='orphan'`) that runs inside the same block will silently fail on retry.
2. `_terminal_failure` in `tasks.py` commits without a `session.begin()` context manager, relying on auto-commit mode; under the project's standard `async_sessionmaker` this silently leaves the mutation uncommitted.
3. `_resolve_refund_id_via_db_join` in `tasks.py` locates the OnlineRefund row by matching `original_payment_id == refund_payment.refund_of`, but `Payment.refund_of` stores the **original** payment's `id`, not the `original_payment_id` FK of the OnlineRefund. The join can return the wrong refund row (or None) when multiple refunds exist on the same original payment.
4. The `circuit_breaker.record_failure` pipeline `ZREMRANGEBYSCORE` uses an inclusive lower bound of `0` rather than `-inf`, meaning it silently retains window entries whose score is negative (which cannot happen in practice, but the canonical Redis docs require `-inf` for unbounded lower end; more critically the intent of "trim older than 60s" is not clearly bounded from below).
5. `_poll_pending_refunds` in `cron.py` catches `IntegrityError` inside `async with session.begin()` and calls `continue` — but the `async with session.begin()` context manager already rolled back the transaction at that point; the `continue` is safe, however the processed counter is **not incremented** for idempotent-replay rows, which causes the ops summary count to undercount reconciled rows in a way that could mask repeated webhook failures at the monitoring layer.

---

## Critical Issues

### CR-01: `handle_refund_succeeded` catches `AlreadyRefundedError`/`IntegrityError` outside the `session.begin()` block, but the `try` wraps the block containing an orphan-path audit emit that uses the tainted session

**File:** `apps/backend/app/api/v1/_internal/yookassa/handlers.py:713-790`

**Issue:** The outer `try` begins at line 713 and wraps the entire `async with session.begin():` block. On the happy path `_settle_online_refund` raises `AlreadyRefundedError` or `IntegrityError` inside the `session.begin()` block; the context manager rolls back the transaction, and the outer `except` at line 773 catches it correctly. However, the orphan-path audit emit at lines 725–735 (reached when `row is None`) also runs **inside** the same `session.begin()` block and therefore inside the same `try`. If `audit.emit` itself raises (e.g., because `LOCKED_AUDIT_EVENTS` check fails for any reason), the exception is caught by the outer `except (AlreadyRefundedError, IntegrityError)` only if it happens to be one of those types; otherwise it propagates. More critically: the `return` at line 736 exits through the `async with session.begin()` exit, committing the orphan audit row atomically. But if a **second** delivery arrives for the same object_id whose DB row was already settled (so row exists, `_settle_online_refund` raises `AlreadyRefundedError`), the session is rolled back inside the `begin()` block, the outer `except` catches it, and the function returns silently — this is correct. The actual bug is subtler: on the **orphan path** (`row is None`), the orphan audit emit at line 725 targets `resource_id=None`. Under the current `YookassaWebhookReceivedPayload` schema, `object_id` and `idempotency_outcome` are required. The `audit.emit` call at line 724 passes `event_type`, `object_id`, and `idempotency_outcome` as kwargs — these land in `**payload` for the Pydantic schema validation inside `audit.emit`. This is correct only if the schema's `extra="forbid"` config accepts `audit_correlation_id` as a separate kwarg. Inspection of `YookassaWebhookReceivedPayload` (audit_payloads.py:964) confirms `audit_correlation_id` IS a field on the schema but the emit call passes it as a top-level kwarg to `audit.emit`, not inside `**payload`. The `audit.emit` signature takes `audit_correlation_id` as a positional kwarg at the `session.add(AuditLog(...))` level (not passed to `schema.model_validate(payload)`). This is fine. The real bug is: **when `row is None`, the code does `return` at line 736 INSIDE `async with session.begin()`**, which commits the orphan audit. Then the outer try's `except` block is never reached. But if `_settle_online_refund` then succeeds on a re-delivery (after a race), the outer except will never see it. This path is in fact correctly structured. Upon closer analysis, the actual atomicity gap is:

The `try` at line 713 wraps the `async with session.begin():` block. When `IntegrityError` from a non-refund-uniqueness source (e.g. FK violation) is raised inside `session.begin()`, the context manager rolls back the transaction, then the outer `except` re-raises it via the `raise` at line 790. This is structurally correct. **The real defect** is that `_settle_online_refund` calls `session.flush()` at line 235 of `settle.py` inside an already-started `session.begin()` — and an `AlreadyRefundedError` or `IntegrityError` from the `get_payment_refunder()` call will taint the session. The `session.begin()` async context manager exits via `__aexit__` with the exception and calls `session.rollback()`. The outer `except` then catches the exception after the session is already rolled back and the transaction is closed. This is **correct** — the session is no longer in a bad state because `session.begin()` handles rollback. The actual bug that exists here is more narrow: the `session` object itself may be in an invalidated state after `rollback()` if subsequent code (like a hypothetical future audit emit in the `except` branch) tries to use it. Currently no code after the `except` uses `session`, so this is latent rather than immediately active.

**The definitive bug:** The orphan-audit-path `return` at line 736 exits from inside `async with session.begin()`, committing the orphan-audit row. This is correct. But the `session.begin()` block and the `try` wrap are structurally inverted from what is needed: the `try` should wrap only the `_settle_online_refund` call, not the entire `session.begin()` block including the `row is None` guard and FSM-transition check. As written, an `IntegrityError` from the `audit.emit` orphan row (line 725-735) would be caught by the outer except at line 773, tested against `_is_refund_of_uniqueness_conflict`, fail the test, and then re-raised — but the `session.begin()` block's rollback has already occurred, so the orphan audit row is lost. This means **orphan deliveries under rare DB contention silently drop their forensic audit row**.

**Fix:**
```python
# Restructure so the try/except wraps only the settle call,
# not the entire session.begin() block:
async with session.begin():
    row = await _select_for_update_online_refund(...)
    if row is None:
        # orphan path — audit emit is NOT in the AlreadyRefundedError try
        await audit.emit(session, "yookassa_webhook_received", ...)
        return

    try:
        _assert_can_transition_refund(row, target=REFUND_STATUS_SUCCEEDED)
    except InvalidTransitionError:
        await audit.emit(session, "yookassa_webhook_received", ..., idempotency_outcome="illegal_transition")
        return

    try:
        await _settle_online_refund(session, ...)
    except (AlreadyRefundedError, IntegrityError) as exc:
        if isinstance(exc, AlreadyRefundedError) or _is_refund_of_uniqueness_conflict(exc):
            _log.warning("yookassa_refund_idempotent_replay", ...)
            return
        raise
```

---

### CR-02: `_terminal_failure` in `tasks.py` calls `session.commit()` directly without `session.begin()`, leaving the mutation uncommitted under the project's standard `async_sessionmaker`

**File:** `apps/backend/app/modules/fiscal_receipts/tasks.py:218-244`

**Issue:** `_terminal_failure` opens a session via `async with session_factory() as session:` (line 218) but calls `await session.commit()` at line 243 **without** an intervening `async with session.begin():` block. The project's `async_sessionmaker` is configured with `expire_on_commit=True` and `autocommit=False` (SQLAlchemy 2.0 async defaults). Without an explicit `session.begin()`, the ORM mutations at lines 227-229 (`fr_row.status = STATUS_FAILED`, etc.) and the `session.add(AuditLog(...))` call inside `audit.emit` at line 229 are queued on the unit-of-work, but there is no active transaction to bind them to before `commit()` is called. Under SQLAlchemy 2.0 async, calling `session.commit()` on a session that has no active transaction will either begin-and-commit an implicit transaction (if `autobegin=True`, which is the 2.0 default) or raise. In practice, SQLAlchemy 2.0 async sessions do have `autobegin=True` so this actually works — **but** it violates the project's explicit convention of `async with session.begin():` (D-32-10) and is inconsistent with every other service function in the codebase. More importantly, `session.add(AuditLog(...))` inside `audit.emit` is called *before* any explicit transaction context, meaning the session's identity map is not flushed before `commit()`. This is actually fine with autobegin but the **real risk** is: if `session.flush()` is never called between the mutation and `commit()`, a DB CHECK constraint violation on `failure_reason` length (not currently constrained, but a future schema change could add one) would surface as an unhandled exception inside `commit()` rather than being caught by the caller. The more immediate issue is the convention violation that could silently regress when the sessionmaker is reconfigured.

**Fix:**
```python
async def _terminal_failure(
    session_factory: Any,
    receipt_uuid: UUID,
    failure_reason: str,
) -> str:
    async with session_factory() as session:
        async with session.begin():          # <-- add explicit transaction
            fr_row = await fiscal_repo.get_fiscal_receipt_by_id(session, receipt_uuid)
            if fr_row is None:
                _log.warning(...)
                return "skipped"
            fr_row.status = STATUS_FAILED
            fr_row.failed_at = datetime.now(UTC)
            fr_row.failure_reason = failure_reason
            await audit.emit(session, "fiscal_receipt_failed", ...)
            # session.begin() commits on clean exit; no explicit commit needed
    return "failed"
```

---

### CR-03: `_resolve_refund_id_via_db_join` uses wrong join key — matches `OnlineRefund.original_payment_id == refund_payment.refund_of` but these fields have different semantics

**File:** `apps/backend/app/modules/fiscal_receipts/tasks.py:154-184`

**Issue:** At line 177-182, the DB-join path looks up `OnlineRefund` with the predicate:
```python
select(OnlineRefund).where(
    OnlineRefund.original_payment_id == refund_payment.refund_of
)
```
`refund_payment.refund_of` is the `payments.refund_of` FK column, which stores the **id of the original sale Payment row** (i.e. the positive-amount row being refunded). `OnlineRefund.original_payment_id` is also the FK to `payments.id` of the original sale Payment row. So these two columns are semantically equivalent: `refund_payment.refund_of == original_sale_payment.id` and `OnlineRefund.original_payment_id == original_sale_payment.id`. This means the join correctly finds any `OnlineRefund` whose original sale Payment matches the one that was refunded. **However**, if a membership is re-sold and refunded multiple times (i.e. multiple Payment ledger rows with the same `subject_kind + subject_id + method='online'`), there could be multiple `OnlineRefund` rows sharing the same `original_payment_id`, and the query returns **one arbitrarily** (no `ORDER BY`, no `.limit(1)`). The `session.scalar()` returns the first row from whatever the DB chooses. If the wrong `OnlineRefund` row is selected, `yookassa_refund_id` from that row is sent to ЮKassa as the receipt link-field, creating a fiscal receipt attached to the wrong refund. This is a data-integrity issue for 54-ФЗ compliance.

**Fix:** Add an explicit `ORDER BY` or constrain the query to the refund row whose `online_payment_id` matches the fiscal receipt's payment context. Since `FiscalReceipt.payment_id` → refund Payment → `refund_of` → original sale Payment, and a given fiscal refund receipt should correspond to exactly one `OnlineRefund`, the correct join should also filter by `online_payment_id` matching the refund payment's parent online payment. However, that chain requires an additional join. The simplest safe fix is to add `.order_by(OnlineRefund.created_at.desc()).limit(1)` to return the most-recent refund, which will be the one associated with the current fiscal receipt in the normal flow:
```python
online_refund = await session.scalar(
    select(OnlineRefund)
    .where(OnlineRefund.original_payment_id == refund_payment.refund_of)
    .order_by(OnlineRefund.created_at.desc())
    .limit(1)
)
```

---

### CR-04: `_terminal_failure` second session block (on success path, line 366-393 in `tasks.py`) has the same missing `session.begin()` issue AND does not check for concurrent status change

**File:** `apps/backend/app/modules/fiscal_receipts/tasks.py:366-393`

**Issue:** The success-path block at line 366 is `async with session_factory() as session:` without `session.begin()`. The same autobegin argument from CR-02 applies. More critically: between the first session (lines 272-286 where the row is loaded and data is snapshotted) and this second session (lines 366-393), another worker could have processed the same `fiscal_receipt_id` (e.g. a duplicate enqueue). The code checks `if fr_row is None` but does NOT check if `fr_row.status` has changed from `STATUS_SENT`. If a concurrent worker already moved the row to `succeeded` or `failed`, this worker will overwrite `yookassa_receipt_id` again and emit a duplicate `fiscal_receipt_dispatched` audit row. Additionally, the missing `session.begin()` means the commit semantics are autobegin-dependent.

**Fix:**
```python
async with session_factory() as session:
    async with session.begin():                  # <-- explicit transaction
        fr_row = await fiscal_repo.get_fiscal_receipt_by_id(session, receipt_uuid)
        if fr_row is None:
            _log.warning(...)
            return "skipped"
        if fr_row.status != STATUS_SENT:         # <-- guard concurrent change
            _log.info("fiscal_receipt_status_changed_concurrent", ...)
            return "skipped"
        if result.receipt_id is not None:
            fr_row.yookassa_receipt_id = result.receipt_id
        await audit.emit(session, "fiscal_receipt_dispatched", ...)
        # commits on exit
```

---

### CR-05: `audit.emit` for `online_payment_refunded` in `settle.py` passes `amount_kopecks=refund_payment.amount_kopecks` which is a **negative** value, but `OnlinePaymentRefundedPayload` has no sign constraint — and the schema comment in `audit_payloads.py` says this field is positive

**File:** `apps/backend/app/modules/online_refunds/settle.py:241-251`

**Issue:** At line 251, the emit is:
```python
amount_kopecks=refund_payment.amount_kopecks,
```
`refund_payment` is the result of `get_payment_refunder()()`, which calls `issue_refund` in `payments/service.py`. By the append-only ledger design (B-01 INFRA-22), refund rows have a **negative** `amount_kopecks`. The `OnlinePaymentRefundedPayload` schema (audit_payloads.py:866-880) declares `amount_kopecks: int` with no sign constraint. The audit.py docstring for the event says "amount_kopecks" without qualification of sign. However, `RefundIssuedPayload` (line 114-132 in audit_payloads.py) explicitly states "`amount_kopecks` is negative (refund row in append-only payments ledger)" — so the convention is that the refund row's amount is negative. But for `OnlinePaymentRefundedPayload`, the docstring at line 868 says "amount_kopecks" without sign qualification, while the `FiscalReceiptDispatchedPayload.customer_email` docstring for refund kind implies a positive amount. The `_resolve_amount_kopecks` helper in tasks.py explicitly calls `abs()` (line 203) to make the amount positive for 54-ФЗ receipt purposes. If `online_payment_refunded` is consumed downstream (Phase 52 notification DMs) expecting a positive kopeck amount for display, passing the raw negative value will produce a confusingly negative money display. This is a behavioral correctness issue for the audit trail and any Phase 52 consumer.

**Fix:** Explicitly pass `abs(refund_payment.amount_kopecks)` to be consistent with the fiscal receipt path and the payment display convention:
```python
amount_kopecks=abs(refund_payment.amount_kopecks),
```

---

## Warnings

### WR-01: `cron.py` (`_poll_pending_refunds`) does not increment `processed` for idempotent-replay rows, causing the ops summary to undercount

**File:** `apps/backend/app/modules/online_refunds/cron.py:118-129`

**Issue:** When `_is_refund_of_uniqueness_conflict(exc)` is True (the prior webhook already settled the refund), the code logs a warning and calls `continue` at line 128 without incrementing `processed`. The function's docstring says it returns "count of rows processed (succeeded or canceled)". An idempotent replay is arguably "processed" — the refund is in a terminal state. The current behavior means repeated cron ticks for already-settled refunds (due to webhook delivery delay) will always report `count=0` for those rows, making the ops summary misleading. Under alert thresholds based on this count, a prolonged backlog of webhook-missed refunds that were settled by the cron could appear as "nothing processed" when in fact the cron is doing useful work.

**Fix:** Increment `processed` before `continue`:
```python
processed += 1  # replay counts as resolved
_log.warning("yookassa_refund_poll_idempotent_replay", ...)
continue
```

---

### WR-02: `handle_payment_canceled` orphan path does not emit an audit row, breaking the forensic chain

**File:** `apps/backend/app/api/v1/_internal/yookassa/handlers.py:575-580`

**Issue:** When `row is None` on the canceled webhook path (lines 575-579), the code logs a structlog warning and returns without emitting a `yookassa_webhook_received` audit row. This is inconsistent with the `handle_refund_succeeded` orphan path (line 724-735) which explicitly emits an audit with `idempotency_outcome='orphan'` for forensic completeness. The D-50-17 / D-51-11 forensic discipline requires every webhook delivery to produce an audit row.

**Fix:** Add an audit emit before the `return`:
```python
if row is None:
    _log.warning("yookassa_webhook_orphan_payment_canceled", object_id=object_id)
    await audit.emit(
        session,
        "yookassa_webhook_received",
        actor_user_id=None,
        resource_type="yookassa_webhook",
        resource_id=None,
        audit_correlation_id=None,
        event_type="payment.canceled",
        object_id=object_id,
        idempotency_outcome="orphan",
    )
    return
```

---

### WR-03: `initiate_online_refund` in `service.py` calls `session.rollback()` manually at line 414 inside a session that was not started with `session.begin()`, which is inconsistent with the project's UoW discipline

**File:** `apps/backend/app/modules/online_refunds/service.py:411-417`

**Issue:** The function at line 414 calls `await session.rollback()` explicitly when it catches `IntegrityError` from `session.flush()`. This pattern deviates from the project-standard `async with session.begin():` RAII rollback discipline established in D-32-10. In the project's other services (e.g. memberships/service.py), the session is always entered via `session.begin()` by the router or a higher-level caller; the service layer calls `session.commit()` at the end. Here, the explicit `rollback()` call may conflict with the outer session lifecycle if the router or test fixture wraps the call in its own `session.begin()` — calling `rollback()` inside a nested savepoint context would roll back the entire outer transaction rather than just the inner mutation. Since `initiate_online_refund` calls `session.commit()` at line 440, it implicitly owns the transaction, but the `rollback()` + `raise` pattern at line 414 abandons the session in a potentially inconsistent state for the caller.

**Fix:** Wrap the entire function body (from step 2 guards onwards) in `async with session.begin():` and use the context manager's automatic rollback on exception, removing the explicit `await session.rollback()`:
```python
# Remove line 414: await session.rollback()
# The session.begin() context manager handles rollback on exception.
# Surface the IntegrityError as the domain exception:
except IntegrityError as exc:
    if _is_alive_per_online_payment_conflict(exc):
        raise RefundAlreadyInFlightError("refund_already_in_flight") from exc
    raise
```

---

### WR-04: `circuit_breaker.record_failure` uses `ZREMRANGEBYSCORE ... 0 {cutoff}` instead of `-inf {cutoff}`, leaving open a theoretical correctness gap

**File:** `apps/backend/app/integrations/yookassa/circuit_breaker.py:96`

**Issue:** The `ZREMRANGEBYSCORE` command at line 96 uses `0` as the lower bound:
```python
pipe.zremrangebyscore(window_key, 0, cutoff)
```
The intent is to remove all entries older than the 60-second window. The `cutoff` value is `now_ms - 60000`. Using `0` as the lower bound means any member with a score less than 0 is NOT removed. In this implementation, scores are Unix timestamps in milliseconds (always positive), so no entry can have score < 0 — the `0` lower bound is harmless in practice. However, using `"-inf"` is the semantically correct Redis ZREMRANGEBYSCORE lower bound for "remove all entries with score up to X" and is the idiomatic form that makes the intent clear. More importantly, a Redis client that stringifies `0` as a special value in some library version could behave unexpectedly. This is a low-priority correctness/clarity issue.

**Fix:**
```python
pipe.zremrangebyscore(window_key, "-inf", cutoff)
```

---

### WR-05: `_settle_online_refund` searches for live Membership using `status.in_(("active", "frozen", "expired"))` but `expired` memberships are terminal and should not be refunded

**File:** `apps/backend/app/modules/online_refunds/settle.py:166-171`

**Issue:** The membership lookup at line 169 filters `Membership.status.in_(("active", "frozen", "expired"))`. An `expired` membership has already passed its end date — the `initiate_online_refund` service layer (service.py) allows initiating a refund on an expired membership because `MEMBERSHIP_STATUS_TRANSITIONS` may include `expired → cancelled` (confirmed by the FSM gate at `_assert_refund_can_transition_membership`). If the membership transitioned to `expired` between the time `initiate_online_refund` was called (which ran the FSM gate) and the time the webhook fires settle, the settle correctly finds and cancels the expired row. **However**, including `expired` in the lookup broadens the scope unnecessarily. A more critical issue is that `expired` status in the FSM may or may not permit transition to `cancelled` — if the FSM disallows `expired → cancelled`, the initiate-time guard would have rejected the request. But if a membership expired AFTER the refund was initiated (i.e. after the OnlineRefund row was written in `pending` state), the settle will find the expired row and attempt to cancel it. This is arguably correct behavior. The warning here is that the status filter is brittle: if a membership can be in `renewed` or other states not in this list, the lookup silently returns `None` and raises `RuntimeError`, aborting the settle UoW and leaving the refund payment already written in the ledger but the membership uncancelled. This inconsistency in the settle UoW (partial completion) is a data-integrity risk.

**Fix:** Either broaden the filter to exclude only terminal `cancelled` (i.e. `NOT IN ('cancelled')`) or add a fallback lookup without status restriction that raises a more informative error:
```python
membership_stmt = select(Membership).where(
    Membership.client_id == op.client_id,
    Membership.plan_id == op.membership_plan_id,
    Membership.status != "cancelled",  # exclude already-cancelled
)
```

---

### WR-06: `OnlineRefundRequest.idempotency_key` is typed as `UUID` in the Pydantic schema but `initiate_online_refund` converts it to `str` when passing to `insert_online_refund`, and the replay check also converts to `str` — the type mismatch is silent

**File:** `apps/backend/app/modules/online_refunds/schemas.py:19` and `apps/backend/app/modules/online_refunds/service.py:282, 402`

**Issue:** `OnlineRefundRequest.idempotency_key` is `UUID` (schemas.py:19). In `initiate_online_refund`, the replay check at line 282 converts it via `str(idempotency_key)`, and the insert at line 402 also converts via `str(idempotency_key)`. The `create_refund` call at line 373 passes the UUID directly: `idempotency_key=idempotency_key`. ЮKassa accepts any opaque ASCII string for `Idempotence-Key`, so a UUID's default `str()` format (hyphenated UUID4) is valid. However, `OnlineRefund.idempotency_key` is a `Text` column; the replay-check lookup at line 282 searches by `str(idempotency_key)`, while ЮKassa will use the hyphenated UUID4 string. If a caller passes the idempotency key as a non-hyphenated UUID string via the HTTP layer (which Pydantic normalizes to UUID and back), the DB and ЮKassa will agree on the hyphenated form. This is internally consistent but the code performs the `str()` conversion in two places (lines 282 and 402) when it should be done once at the entry point and passed through as `str`. The redundant conversions add cognitive load.

**Fix:** Normalize to string once at the top of `initiate_online_refund`:
```python
idempotency_key_str = str(idempotency_key)
# Then use idempotency_key_str throughout
```

---

### WR-07: `dispatch_fiscal_receipt` task in `tasks.py` instantiates `YooKassaSettings()` inside the task body (line 298) on every invocation, bypassing the `@lru_cache` factory used by the HTTP layer

**File:** `apps/backend/app/modules/fiscal_receipts/tasks.py:298`

**Issue:** The task body at line 298 calls `YooKassaSettings()` directly, creating a new Pydantic settings object (which reads from environment variables) on every task execution. The HTTP layer uses `get_yookassa_settings` (an `@lru_cache(maxsize=1)` factory) to avoid repeated env reads. The worker startup in `app/workers/__init__.py` already constructs a `YooKassaSettings()` when building `build_yookassa_client` (line 317-318 of workers/__init__.py). The `ctx["yookassa_client"]` already carries a client built from the startup-time settings. Re-reading settings inside the task is wasteful and inconsistent. More importantly, `tax_system_code` and `default_vat_code` are read here directly from the fresh settings object rather than from the already-constructed client. If the env var changes between worker boot and task execution (e.g., in a rolling deploy scenario), the task would use a different tax code than the client was configured with. The `YooKassaClient.create_receipt` method at line 456 of client.py accepts `tax_system_code` as a parameter — this is correctly the `tasks.py` responsibility — but reading it from a freshly instantiated `YooKassaSettings()` rather than from the client's stored `_settings` is inconsistent.

**Fix:** Store `yookassa_settings` in `ctx` during `on_startup` alongside `yookassa_client`, or read `ctx["yookassa_client"]._settings.tax_system_code` (using the already-constructed client's settings):
```python
# In on_startup:
ctx["yookassa_settings"] = yookassa_settings

# In dispatch_fiscal_receipt:
settings = ctx["yookassa_settings"]
```

---

## Info

### IN-01: `mark_canceled` is called then `row.status = STATUS_CANCELED` is redundantly set in `cron.py`

**File:** `apps/backend/app/modules/online_refunds/cron.py:154-155`

**Issue:** Lines 154-155:
```python
refund_repo.mark_canceled(row, canceled_at=datetime.now(UTC))
row.status = STATUS_CANCELED  # defensive — repo helper sets this
```
`mark_canceled` (repository.py:123-128) already sets `row.status = STATUS_CANCELED` and `row.canceled_at`. The redundant assignment on line 155 adds noise and the comment "defensive" implies it was intentional, but setting an attribute to the same value it was just set to is dead code. The comment should either be removed or a unit test should assert the helper sets the status (making the defensive duplication unnecessary).

**Fix:** Remove line 155.

---

### IN-02: `_backoff_with_jitter` in `tasks.py` generates jitter using `random.uniform` — the `# noqa: S311` suppresses the security lint but the comment should explain why non-cryptographic randomness is acceptable

**File:** `apps/backend/app/modules/fiscal_receipts/tasks.py:76`

**Issue:** The `# noqa: S311` at line 76 suppresses the Bandit/ruff `S311` (use of `random` for security-sensitive operations) warning. The docstring and inline comment explain that `random.uniform` is correct here (thundering-herd avoidance, not cryptographic). However, the comment text `# Backoff jitter is a non-cryptographic timing perturbation; stdlib random is the canonical primitive for thundering-herd avoidance.` is on the line above the `# noqa`, making the relationship slightly confusing. The `# noqa: S311` should ideally be on the same line as the suppressed expression with the reason inline.

**Fix:** (style only)
```python
jitter = random.uniform(-0.1, 0.1) * base  # noqa: S311 — non-cryptographic timing jitter
```

---

### IN-03: `OnlineRefundRequest` does not validate `reason` length — an unbounded free-text field lands in both the DB and JSONB audit payload without truncation

**File:** `apps/backend/app/modules/online_refunds/schemas.py:20-21`

**Issue:** `reason: str | None = None` has no length constraint. The DB column `online_refunds.reason` is `Text` (effectively unbounded in PostgreSQL). The field also flows into the `online_refund_initiated` audit JSONB payload. An operator supplying a very long reason string (e.g. 100 KB) would create oversized audit log entries. Other string fields in the project (e.g. `BookingCancelledPayload.cancel_reason`) also lack explicit length constraints, so this is a project-wide convention gap rather than a Phase 51 regression, but worth noting here since this is a new user-facing field.

**Fix:** Add a max-length validator:
```python
from pydantic import Field
reason: str | None = Field(default=None, max_length=500)
```

---

_Reviewed: 2026-05-23T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
