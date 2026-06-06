---
phase: 84-real-autopay-charge
reviewed: 2026-06-05T00:00:00Z
depth: deep
files_reviewed: 19
files_reviewed_list:
  - apps/backend/alembic/versions/0056_autopay_charges.py
  - apps/backend/alembic/versions/0057_payment_notifications_widen_kind.py
  - apps/backend/app/api/v1/_internal/yookassa/handlers.py
  - apps/backend/app/core/audit.py
  - apps/backend/app/core/audit_payloads.py
  - apps/backend/app/integrations/yookassa/client.py
  - apps/backend/app/modules/autopay_charges/__init__.py
  - apps/backend/app/modules/autopay_charges/models.py
  - apps/backend/app/modules/autopay_charges/notifications.py
  - apps/backend/app/modules/autopay_charges/repository.py
  - apps/backend/app/modules/autopay_charges/service.py
  - apps/backend/app/modules/autopay_charges/tasks.py
  - apps/backend/app/modules/online_payments/email_templates.py
  - apps/backend/app/modules/online_payments/models.py
  - apps/backend/app/modules/online_payments/tasks.py
  - apps/backend/app/workers/__init__.py
  - apps/backend/app/workers/scheduled/charge_expiring_autopay.py
  - apps/backend/alembic/env.py
  - apps/backend/.importlinter
findings:
  critical: 2
  warning: 2
  info: 1
  total: 5
status: issues_found
---

# Phase 84: Code Review Report — Real Autopay Charge

**Reviewed:** 2026-06-05
**Depth:** deep
**Files Reviewed:** 19
**Status:** issues_found

## Summary

Phase 84 implements off-session recurring autopay charges: a daily cron
(`charge_expiring_autopay`) claims eligible memberships, calls YooKassa with a
saved card token, inserts an `online_payments(confirmation_type='autopay')` row on
success, and relies on the existing `payment.succeeded` webhook to activate the
renewal. The overall architecture is sound — claim-before-charge, deterministic
idempotency key, ФЗ-376 consent enforcement, D-06 webhook-locked activation, and
failure-no-retry are all correctly implemented.

Two critical bugs were found. The first silently drops every autopay success
notification because the webhook handler enqueues the wrong identifier for the
dispatch task. The second permanently blocks retry after transient network errors.
Both require fixes before this code ships to production.

---

## Critical Issues

### CR-01: Autopay success notification is never delivered — wrong ID passed to dispatch task

**File:** `apps/backend/app/api/v1/_internal/yookassa/handlers.py:685`

**Issue:**
`_post_commit_enqueue` is called with `payment_id=ledger_payment_id` for all
cases, including `is_autopay_local=True` (kind='autopay_charge_succeeded'). The
`ledger_payment_id` is `payments.id` — the charge-ledger row inserted by
`get_payment_recorder()`.

However, in `dispatch_payment_notification` (online_payments/tasks.py lines
399–445), when `kind == "autopay_charge_succeeded"`, the task treats `payment_uuid`
as an `online_payments.id` and queries:

```python
_online_payments_tbl.c.id == payment_uuid   # payment_uuid = payments.id — WRONG TABLE
```

Because `payments.id` never matches `online_payments.id`, `op` is always `None`
and the task logs an error and returns `"skipped"`. **Every autopay success
notification is silently dropped.**

Separately, the CLAIM step at tasks.py line 523-529 uses
`online_payment_id=payment_uuid` to insert a `payment_notifications` row — also
keyed on the wrong ID — so the idempotency guard is additionally broken for this
kind.

The integration test `test_autopay_success_dual_channel_then_replay_no_duplicate`
directly calls `dispatch_payment_notification(ctx, payment_id=str(online_payment_id), kind="autopay_charge_succeeded")` with the correct `online_payments.id` — this
test passes, but it does **not** exercise the real enqueue path through the webhook
handler. The production code path always passes the wrong ID.

**Fix:**
In `handlers.py`, capture `op_row_id` (already available as `row.id` at line 660)
and pass it as `payment_id` when enqueuing for the autopay kind:

```python
# handlers.py — replace lines 675-687
if is_autopay_local:
    notification_kind: str = "autopay_charge_succeeded"
    # For autopay success, the dispatch task expects online_payments.id —
    # not the ledger payments.id (see online_payments/tasks.py:399-445).
    notification_payment_id = op_row_id
else:
    notification_kind = "payment_succeeded"
    notification_payment_id = ledger_payment_id
await _post_commit_enqueue(
    arq_pool,
    online_payment_id=op_row_id,
    subject_kind=subject_kind_local,
    subject_id=subject_id_local,
    fiscal_receipt_id=fiscal_receipt_row_id_local,
    payment_id=notification_payment_id,
    kind=notification_kind,
)
```

---

### CR-02: Transient provider errors permanently suppress autopay retry

**File:** `apps/backend/app/modules/autopay_charges/service.py:338–384`

**Issue:**
When `yookassa_client.create_payment()` returns `classification='transient_error'`
(network timeout, provider 5xx, DNS failure), the service takes the same `else:`
branch as a hard card decline. It sets `status='failed'` on the `autopay_charges`
claim row and records `failure_reason='transient_error'`.

On the next cron tick, `ON CONFLICT (membership_id, period_end) DO NOTHING` on the
`autopay_charges` INSERT fires on the existing `status='failed'` row — the period
is permanently skipped. The membership goes unrenewed for the entire window with no
further attempt, even though the failure was transient (provider temporarily
unavailable) and the client's card may be perfectly valid.

The deterministic `idempotency_key` means a subsequent YooKassa call with the same
key on a recovered provider would be safe — the design explicitly supports crash
recovery. Only the DB claim status prevents the retry.

**Fix — Option A (recommended):** Distinguish transient from permanent failures by
leaving the claim in `status='pending'` on transient errors so the next tick
retries:

```python
# service.py — in the else: branch, before the UPDATE:
is_transient = result.classification == "transient_error"

await session.execute(
    text(
        "UPDATE autopay_charges "
        "SET status = :status, "
        "    failure_reason = :failure_reason, "
        "    updated_at = now() "
        "WHERE id = :claim_id"
    ),
    {
        "status": "pending" if is_transient else "failed",
        "failure_reason": failure_reason,
        "claim_id": str(claim_id),
    },
)

# Only collect declined_charge_ids for permanent failures (not transient).
# A transient 'pending' row will be retried on the next cron tick.
if not is_transient:
    declined_charge_ids.append(claim_id)
```

**Option B:** Add a `status='transient_failed'` to the CHECK constraint and skip
rows with that status differently, but this adds schema complexity. Option A is
simpler and uses the existing pending→retry mechanism.

Note: the failure notification MUST also be skipped on transient errors (as shown
in Option A) since the client's card is not declined — notifying them would be
confusing.

---

## Warnings

### WR-01: Unhandled IntegrityError from double-tap unique index on autopay online_payments INSERT

**File:** `apps/backend/app/modules/autopay_charges/service.py:273–297`

**Issue:**
The `INSERT INTO online_payments ... confirmation_type='autopay'` is executed inside
the batch loop with no try/except. The `online_payments` table has a partial unique
index `uq_online_payments_membership_double_tap` on
`(client_id, membership_plan_id, date(initiated_at)) WHERE status != 'canceled' AND membership_plan_id IS NOT NULL`.

A race condition exists: if a client initiates an interactive checkout for the same
plan on the same day the autopay cron runs (same `client_id + membership_plan_id + date`), the autopay INSERT will raise an `sqlalchemy.exc.IntegrityError`. Since this
is unhandled, it propagates through `_charge_expiring_autopay_memberships` to
`charge_expiring_autopay`, rolls back the entire cron session, and **all other
memberships in the same batch lose their autopay attempt silently** (they were not
committed).

The eligibility query's NOT EXISTS clause filters out memberships with an active
renewal, but a pending interactive `online_payments` row does not create a new
membership yet (activation is webhook-locked). So the race window is real.

**Fix:** Wrap the `online_payments` INSERT in a try/except for `IntegrityError` and
treat a double-tap conflict as a skip (the interactive checkout is in progress):

```python
from sqlalchemy.exc import IntegrityError

try:
    await session.execute(
        text("INSERT INTO online_payments ..."),
        {...},
    )
except IntegrityError:
    # Interactive checkout already in flight for same client+plan+day.
    # Skip autopay for this membership — the interactive payment will
    # activate the renewal via webhook.
    await session.rollback()  # or use savepoint
    _log.info(
        "autopay_charge_skipped_double_tap_conflict",
        membership_id=str(membership_id),
        period_end=str(period_end),
    )
    # Also clean up the pending claim row.
    await session.execute(
        text("DELETE FROM autopay_charges WHERE id = :claim_id"),
        {"claim_id": str(claim_id)},
    )
    count -= 1  # undo the count increment not yet made — adjust accordingly
    continue
```

Note: because the service operates in a single session owned by the cron, a
`SAVEPOINT` pattern is preferable to avoid tainting the session on rollback. The
simpler fix is to issue the claim INSERT and the `online_payments` INSERT inside a
nested savepoint per row.

---

### WR-02: Pyright "possibly unbound" variables `chat_id` / `email_addr` in dispatch_payment_notification loop

**File:** `apps/backend/app/modules/online_payments/tasks.py:481,503`

**Issue:**
Inside the `for channel in ("telegram", "email"):` loop, `chat_id` is assigned only
in the `if channel == "telegram":` branch and `email_addr` is assigned only in the
`else:` branch. Pyright reports both as "possibly unbound" because the static
analyser tracks assignments across loop iterations — on the email iteration,
`chat_id` from the telegram iteration is in scope but was assigned under a branch
that may have `continue`'d.

Runtime behaviour is correct: `chat_id` is only referenced inside
`if channel == "telegram":` and `email_addr` only inside `else:`, so neither is
ever actually unread. However, `mypy --strict` (project requirement per CLAUDE.md)
will flag this as an error (`Name 'chat_id' may be undefined`) in non-trivial
configurations.

The same pattern exists in `autopay_charges/tasks.py` lines 213/223 for
`dispatch_autopay_failure_notification`, though that function has separate
if/else branches (not a loop), so it is less ambiguous.

**Fix:** Initialize the variables before the loop to provide a guaranteed binding:

```python
# Before the for loop in dispatch_payment_notification:
chat_id: int = 0           # will always be overwritten before use
email_addr: str = ""       # will always be overwritten before use

for channel in ("telegram", "email"):
    ...
```

Or restructure each channel as a separate helper to eliminate the shared mutable
loop variable pattern entirely.

---

## Info

### IN-01: `assert` statements for provider invariants in production money-movement code

**File:** `apps/backend/app/modules/autopay_charges/service.py:263–264`

**Issue:**
```python
assert result.payment_id is not None  # guaranteed by classification='ok'
assert result.amount_kopecks is not None
```

`assert` statements are removed by the Python interpreter when run with `-O`
(optimize flag). In production, if the YooKassa client ever returns
`classification='ok'` with `payment_id=None` (malformed provider response not
caught by the adapter), this silently becomes `None` and the subsequent INSERT
`"yookassa_payment_id": result.payment_id` would store NULL in a column that is
defined `TEXT` (nullable in the model). The webhook would then never find the row.

This is unlikely given the adapter's classification logic, but for real money
movement, defensive checks should raise explicitly:

```python
if result.payment_id is None or result.amount_kopecks is None:
    raise RuntimeError(
        f"YooKassa returned classification='ok' but payment_id or "
        f"amount_kopecks is None — provider contract violation "
        f"(membership_id={membership_id}, period_end={period_end})"
    )
```

---

_Reviewed: 2026-06-05_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
