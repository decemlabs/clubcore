# Phase 87 — Notification Inbox — PATTERNS

> ⚠ **PARTIAL-RECOVERY NOTICE (Phase 87 plan revision).** During a targeted
> revision of `87-03-PLAN.md`, this PATTERNS.md file was accidentally truncated
> by a full-file overwrite before it had been committed to git, so the leading
> sections (roughly the original lines 1–499 and the tail past line ~580) could
> NOT be recovered from disk, git, editor backups, or APFS snapshots. The
> sections preserved below are the ones that were in the reviser's read context
> at the time: the `client_push_tokens` migration DDL fragment, the
> bookings/service.py event-hook section (rewritten to fix the post-commit
> mislabel + reception-cancel gap), and the yookassa handler hook section.
>
> **Action required before executing Phase 87:** regenerate the missing
> sections (re-run the patterns/research step for this phase) OR confirm the
> executor can proceed from the inline `<interfaces>` blocks already embedded in
> each PLAN.md. The booking + yookassa hook guidance below is authoritative and
> corrected; treat the rest of the original PATTERNS.md as MISSING, not as
> "nothing was there."

---

## Migration DDL — `client_push_tokens` (recovered fragment)

```python
    sa.ForeignKeyConstraint(
        ["client_id"], ["clients.id"],
        ondelete="RESTRICT",
        name="fk_client_push_tokens_client_id_clients",
    ),
    sa.PrimaryKeyConstraint("id"),
)
# Partial UNIQUE — must use op.create_index (partial indexes are not expressible
# as sa.UniqueConstraint inside create_table; mirrors migration 0052 pattern for
# uq_client_payment_methods_client_id_alive).
op.create_index(
    "uq_client_push_tokens_client_token_alive",
    "client_push_tokens",
    ["client_id", "token"],
    unique=True,
    postgresql_where=sa.text("unregistered_at IS NULL"),
)
op.create_index("ix_client_push_tokens_client_id", "client_push_tokens", ["client_id"])
```

---

### Event Hook Insertions: bookings/service.py (5 hooks)

**Analog:** self — the file already has inline dispatch calls. Each new `create_notification(...)` call goes beside the existing `_dispatch_booking_lifecycle_notification` / `enqueue_booking_email_fallback` call. Caller-owns-txn: the notifications INSERT MUST happen in the same session as the booking state mutation, **strictly BEFORE `await session.commit()`** (co-transactionally — atomic with the state change). NEVER place the in-app insert in a post-commit / fire-and-forget block: the booking DM dispatch is best-effort, but the inbox row is part of the durable state transition (CONTEXT decision: "insert участвует в caller-owned транзакции"; UNIQUE dedup covers webhook/retry replay).

> NOTE (Phase 87 correctness fix): the in-app inbox insert is NOT the same lifecycle as the Telegram DM. The DM is post-commit fire-and-forget (D-39-09/D-39-10); the inbox insert is **pre-commit co-transactional**. Do not co-locate the inbox insert with the DM dispatch call. Place it before the function's commit, alongside (or just after) the `audit.emit(...)` for that state transition.

There are **five** client-affecting booking events. Cancellation must reach the AFFECTED CLIENT regardless of who triggers it (INBOX-03), so `cancel_booking` — which staff (owner OR reception) use to cancel a client's booking — contributes TWO hooks, one per role branch.

**Hook 1 — booking confirmed** (`create_booking`, beside `audit.emit("booking_created")` ~line 1090–1116, BEFORE the `await session.commit()` at line ~1119):
The hook goes in the co-transactional region with the audit emit, NOT in the post-commit Step 9.5 DM block. `client_id = booking.client_id`, `source_id = booking.id`, `kind="booking_confirmed"`.

```python
# Step 8.5 — Phase 87 INBOX-03 — in-app inbox row (co-transactional, BEFORE commit)
await create_notification(
    session,
    client_id=booking.client_id,
    source_type="booking",
    source_id=booking.id,
    kind="booking_confirmed",
    title=...,  # rendered Russian string
    body=...,   # rendered Russian string
)
# Step 9 — Commit (SVC001 gate).
await session.commit()
```

**Hook 2 — booking cancelled_by_owner** (`cancel_booking`, owner case): the role branch that selects `cancelled_by_owner` lives in the POST-commit DM block (~line 1532). Do NOT hook there. Instead, in the CO-TRANSACTIONAL region (after `audit.emit("booking_cancelled")` ~line 1507, before `await session.commit()` at line ~1522), branch on `actor.role`: when `actor.role is Role.OWNER` insert `kind="booking_cancelled_by_owner"`. `client_id = booking.client_id`, `source_id = booking.id`.

**Hook 3 — booking cancelled_by_client (staff/reception cancels client's booking)** (`cancel_booking`, reception case): in the SAME pre-commit branch as Hook 2, when `actor.role is Role.RECEPTION` insert `kind="booking_cancelled_by_client"` (matches the existing email `kind="cancelled_by_client"` semantics for the reception branch). `client_id = booking.client_id`, `source_id = booking.id`. (Hooks 2 and 3 are the two arms of one `if/elif` on `actor.role`, placed before commit — NOT in the post-commit DM dispatch block.)

**Hook 4 — booking cancelled_by_client (client self-cancel)** (`cancel_booking_for_client`, ~line 1652): after `audit.emit("booking_cancelled")` (~line 1652) and BEFORE `await session.commit()` at line ~1668. This function has "Step 8 — NO Telegram DM dispatch" (line ~1664), so the inbox insert is the only notification side-effect; it is co-transactional. `client_id = booking.client_id` (== the passed `client_id`), `source_id = booking.id`, `kind="booking_cancelled_by_client"`.

**Hook 5 — booking rescheduled** (`reschedule_booking_for_client`): insert in the CO-TRANSACTIONAL region — after `audit.emit("booking_rescheduled")` (~line 1868) and BEFORE `await session.commit()` at line ~1895. Do NOT place it in the post-commit fire-and-forget DM `try/except` (~lines 1929–1992): that block's broad `except Exception` would silently swallow an inbox-insert failure, and it runs after commit (NOT atomic). `client_id = client_id`, `source_id = new_booking.id` (the new booking), `kind="booking_rescheduled"`. Capture `new_slot.start_time` + trainer name strings before commit (they are in scope at the audit-emit site).

**Cross-module import pattern** — import `create_notification` at the top of each caller file using a lazy import or top-level import. The existing cross-module call pattern for loyalty is:
```python
# From handlers.py lines 40–48 — deferred module-level imports at top of file
from app.modules.loyalty.service import record_loyalty_redemption
```
For notifications, add at the top of the service file:
```python
from app.modules.notifications.service import create_notification
```

---

### Event Hook Insertion: `app/api/v1/_internal/yookassa/handlers.py` (1 hook)

**Insertion point:** inside `handle_payment_succeeded`, INSIDE the `async with session.begin():` block (co-transactionally), after the existing `record_loyalty_redemption(...)` call (~line 558) and before the block exits (commits). Do NOT place it in the post-commit `_post_commit_enqueue(...)` path (~line 687) — the inbox insert must be atomic with the payment state change. It uses `row.client_id` / `row.id` which are in scope. Pattern mirrors how `record_loyalty_redemption` is called within the same `async with session.begin():` block:

```python
# Phase 87 INBOX-03 — in-app notification for payment_succeeded / autopay_charge_succeeded
# Inside async with session.begin(): block, after record_loyalty_redemption, before block exit
await create_notification(
    session,
    client_id=row.client_id,
    source_type="online_payment",
    source_id=row.id,
    kind="autopay_charge_succeeded" if is_autopay else "payment_succeeded",
    title=...,   # rendered Russian string
    body=...,    # rendered Russian string
)
```

This hook lives ONLY in `handle_payment_succeeded` — `payment_canceled` MUST NOT create a row (anti-oracle D-52-08). Webhook replay is covered by the `UNIQUE(client_id, source_type, source_id, kind)` dedup inside `create_notification`.

---
