---
phase: 91-read-receipts-typing-indicators
reviewed: 2026-06-07T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - apps/backend/app/modules/messaging/service.py
  - apps/backend/app/modules/messaging/repository.py
  - apps/backend/app/modules/messaging/schemas.py
findings:
  critical: 0
  warning: 3
  info: 2
  total: 5
status: issues_found
---

# Phase 91: Code Review Report

**Reviewed:** 2026-06-07
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Adversarial review of the Phase 91 delta (read receipts + typing indicators) over
`diff_base 571bd92b`. Scope: `mark_client_messages_read` (repository), reply-as-read
wiring in `record_staff_message`, `publish_read_receipt` / `publish_typing` service fns,
and the new `ReadReceiptEvent` / `TypingEvent` / `StaffMessageResult` schemas.

The five primary correctness/security invariants the prompt called out all hold up under
tracing:

- **Thread-scoped, role='client'-only marking** — `mark_client_messages_read` resolves the
  thread via `get_or_create_thread(client_id)` and filters `WHERE thread_id = :tid AND
  role = 'client' AND read_at IS NULL`. Cross-thread / cross-client marking is impossible
  (repository.py:257-270). VERIFIED.
- **No unread-counter clobber** — `mark_client_messages_read` does NOT touch
  `client_unread_count` (that counter tracks staff→client unread, the inverse direction).
  The Phase-90 `mark_thread_read` recompute hardening (WR-01) is untouched. No concurrent
  clobber path introduced. VERIFIED.
- **Post-commit / DB-first publish** — neither `publish_read_receipt` nor
  `record_staff_message` touches Redis inside the txn; both publish helpers are caller-invoked
  AFTER commit (service.py:78-97; documented contract enforced by the e2e test at
  test_ws_receipts_typing.py:347-368). VERIFIED.
- **Typing is ephemeral & content-free** — `publish_typing` takes no `session` param, does
  no DB work, and `TypingEvent` serializes exactly `{type, actor}` (no body/preview/id),
  asserted by test_messaging_schema_camelcase.py:242-250. VERIFIED.
- **IDOR / principal-derived channel** — both publishers derive the channel solely from the
  `client_id` argument (`cc:messaging:client:{client_id}`); never from payload. Isolation
  proven by test_ws_receipts_typing.py:210-281. VERIFIED. (See IN-01 re: where the
  principal-binding responsibility actually lives.)

`message_sent` and `message_read` are both registered in `LOCKED_AUDIT_EVENTS`
(audit.py:475-476) and absent from `AUDIT_PAYLOAD_SCHEMAS` (free-form payload, pre-v1.4),
so the new `message_read` emit with `client_id=str(...)` payload validates correctly.

No BLOCKER-tier defects found. Three WARNINGs and two INFO items below.

## Warnings

### WR-01: Redundant double `get_or_create_thread` round-trip in `record_staff_message`

**File:** `apps/backend/app/modules/messaging/service.py:218-222`
**Issue:** `record_staff_message` calls `repository.get_or_create_thread(session, client_id)`
on line 218, then immediately calls `repository.mark_client_messages_read(session, client_id)`
on line 222 — and `mark_client_messages_read` internally calls `get_or_create_thread` AGAIN
(repository.py:257). Then `insert_message` is handed the line-218 `thread_id`. So the thread
is resolved twice per staff message via two separate `pg_insert ... ON CONFLICT` +
fallthrough-SELECT round-trips.

This is correctness-neutral today (both calls are idempotent and return the same id), but it
is a latent inconsistency seam: the service holds a `thread_id` resolved by call #1 while the
reply-as-read UPDATE is scoped by a thread_id resolved by call #2. If thread resolution ever
becomes non-idempotent (e.g. a future soft-delete/re-create path), the two ids could diverge
and the staff message would land in a different thread than the one whose client messages were
marked read. Tighten the contract now while it is cheap.

**Fix:** Pass the already-resolved `thread_id` into a thread-scoped variant, or have
`mark_client_messages_read` accept an optional pre-resolved `thread_id`:

```python
async def mark_client_messages_read(
    session: AsyncSession,
    client_id: UUID,
    *,
    thread_id: UUID | None = None,
) -> datetime | None:
    if thread_id is None:
        thread_id = await get_or_create_thread(session, client_id)
    ...

# in record_staff_message:
thread_id = await repository.get_or_create_thread(session, client_id)
reply_read_at = await repository.mark_client_messages_read(
    session, client_id, thread_id=thread_id
)
```

### WR-02: `read_at` field on `ReadReceiptEvent` carries `sent_at` semantics, not a read timestamp

**File:** `apps/backend/app/modules/messaging/schemas.py:151-152`,
`apps/backend/app/modules/messaging/repository.py:276`
**Issue:** `mark_client_messages_read` sets `read_at = now()` on the DB rows but RETURNS and
returns `max(sent_at)` (the original client send times), and that value is published as
`ReadReceiptEvent.read_at` (→ wire `readAt`). So the field named `read_at`/`readAt` is
actually a **send-time cutoff**, not the moment the messages were read. The two values differ:
`read_at` (DB) is strictly later than `max(sent_at)`.

The behaviour is intentional and documented (the client marks all its messages with
`sent_at <= readAt` as ✓✓), but the field name actively misleads — a future consumer (Phase 94
PWA, or a Phase 93 bridge author) reading `readAt` will reasonably assume it is the read
timestamp and may render it as "прочитано в HH:MM", which would be wrong. The REST `read_at`
(actual now()) and the WS `readAt` (max sent_at) will visibly disagree for the same message.

**Fix:** Rename the WS field to convey cutoff semantics (e.g. `up_to_sent_at` → wire
`upToSentAt`, or `read_cutoff`), or document the divergence explicitly at the field and update
the consumer contract so the PWA never renders this value as a timestamp:

```python
class ReadReceiptEvent(ResponseData):
    type: Literal["read_receipt"] = "read_receipt"
    # Send-time CUTOFF (max sent_at of marked rows), NOT the read timestamp.
    # Client marks every sent message with sent_at <= this value as ✓✓.
    read_up_to_sent_at: datetime
```

If renaming is too costly given the locked wire contract, at minimum add an inline field
comment so the next reader is not misled.

### WR-03: Reply-as-read can mark a concurrently-arrived client message read without notifying it

**File:** `apps/backend/app/modules/messaging/service.py:222-274`,
`apps/backend/app/modules/messaging/repository.py:260-277`
**Issue:** `mark_client_messages_read` runs `UPDATE ... WHERE role='client' AND read_at IS NULL`
and returns `max(sent_at)` of the rows it touched. The published `readAt` cutoff tells the
client to mark every message with `sent_at <= readAt` as ✓✓. Under the default READ COMMITTED
isolation, a client message that COMMITS after this UPDATE's snapshot but with a `sent_at`
earlier than the computed max would NOT be in `updated` (so `read_at` stays NULL in the DB),
yet it satisfies `sent_at <= readAt` on the client and would be shown ✓✓ — a false read
indication that disagrees with the persisted DB state and with a subsequent REST GET.

This is a thread-level-marker tradeoff the CONTEXT explicitly accepts (91-CONTEXT.md:40-42),
and the window is narrow (requires a same-thread client send interleaving the staff reply
txn), so it is a WARNING, not a BLOCKER. But it should be acknowledged in the contract so a
reviewer does not later "fix" the cutoff into a guarantee it cannot make.

**Fix:** Either (a) accept and explicitly document the eventual-consistency window — the next
REST refetch (triggered by the `new_message` frame) self-heals the display — or (b) drive the
cutoff from the set of actually-updated message ids rather than a `sent_at` watermark if exact
per-message correctness is ever required. Recommend (a) with a one-line note at
repository.py:275 stating the watermark may transiently over-cover a concurrent send and that
REST GET is the source of truth.

## Info

### IN-01: IDOR safety depends entirely on an unwired caller; no enforcement in this delta

**File:** `apps/backend/app/modules/messaging/service.py:78-119`
**Issue:** `publish_read_receipt` and `publish_typing` accept `client_id` as a plain argument
and trust the caller to pass the principal's id. The IDOR docstrings (T-91-IDOR) are correct,
but no router/WS endpoint in the Phase-91 delta actually wires these to a `require_client()`
principal — `router.py` / `ws.py` were not modified. The only live callers are tests calling
the service directly. The seam is sound, but the "channel derived from principal" guarantee is
not yet enforced anywhere in shippable code; it must be honoured when Phase 93/94 wires the
trigger. Flagging so the guarantee is not assumed already-met by downstream phases.
**Fix:** No code change in this delta. When wiring the typing/receipt trigger (Phase 93/94),
derive `client_id` ONLY from `require_client()` (mirror `send_client_message`'s D-20-IDOR
discipline) and add a wiring-level IDOR test, not just the service-level one that exists now.

### IN-02: `TypingEvent.actor` typed as bare `str`, not a `Literal`

**File:** `apps/backend/app/modules/messaging/schemas.py:168`
**Issue:** `actor: str = "staff"`. Phase 91 supports only staff→client typing, and the
discriminator `type` is correctly a `Literal`, but `actor` is an open `str`. A constructor
typo (`TypingEvent(actor="staf")`) or a future client→staff relay sending `actor="client"`
would serialize silently with no validation. Constraining it documents the closed domain and
fails fast.
**Fix:**
```python
actor: Literal["staff"] = "staff"
```
Widen the Literal to `Literal["staff", "client"]` if/when the deferred client→staff relay
lands, keeping it a closed set.

---

_Reviewed: 2026-06-07_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
