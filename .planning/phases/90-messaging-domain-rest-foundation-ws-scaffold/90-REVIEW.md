---
phase: 90-messaging-domain-rest-foundation-ws-scaffold
reviewed: 2026-06-07T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - apps/backend/app/modules/messaging/ws.py
  - apps/backend/app/modules/messaging/router.py
  - apps/backend/app/modules/messaging/service.py
  - apps/backend/app/modules/messaging/repository.py
  - apps/backend/app/modules/messaging/schemas.py
  - apps/backend/app/modules/messaging/models.py
  - apps/backend/app/core/dependencies.py
  - apps/backend/app/core/audit.py
  - apps/backend/app/api/v1/router.py
  - apps/backend/alembic/versions/0064_messaging_threads.py
  - apps/backend/alembic/versions/0065_messaging_messages.py
findings:
  critical: 2
  warning: 6
  info: 4
  total: 12
status: issues_found
---

# Phase 90: Code Review Report

**Reviewed:** 2026-06-07
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Reviewed the messaging foundation: WebSocket connection handler, REST router, service,
raw-SQL repository, schemas, ORM models, two Alembic migrations, plus the touched
`core/dependencies.py` (`verify_ws_origin`, `get_current_client`) and `core/audit.py`
event lock.

The security-critical WS path is broadly sound: cookie auth via `require_client()` over
the upgrade request (no URL token), Origin guard *before* `accept()`, channel derived
from `client.id` (principal) only, a dedicated `redis.pubsub()` subscriber (not the shared
pool), session-per-operation via `app.state.sessionmaker` (no `Depends(get_db)` held for
the connection lifetime), and `finally` teardown with `aclose()`. REST IDOR is correctly
collapsed (client_id from principal, thread auto-create instead of 404 oracle), SQL is
fully parameterised, and idempotency is wired through the shared helper.

However, the RT-04 `after` catch-up cursor is **functionally broken** — the SQL returns
the wrong rows due to a DESC-ordering + cursor-direction contradiction *and* a
lexicographic `id::text` comparison. There is also a genuine **at-least-once / lost-notify
correctness gap** in the publish-outside-the-committed-transaction sequencing. Several
warnings cover unread-count consistency, the WS error-swallow masking real bugs, and a
`response_model` declaration that does not match the actual returned type.

## Critical Issues

### CR-01: RT-04 `after` cursor returns the wrong rows (broken catch-up pagination)

**File:** `apps/backend/app/modules/messaging/repository.py:172-191`

**Issue:** Two independent defects make the `after` cursor return incorrect data:

1. **Ordering/direction contradiction.** The query selects rows *newer* than the cursor
   (`(sent_at, id::text) > (cursor)`) but orders `sent_at DESC, id DESC` with
   `LIMIT :limit OFFSET :offset`. With a `LIMIT`, DESC ordering returns the *newest*
   page of the newer-than-cursor set. A catch-up client that passes its last-seen id
   expects the messages it missed in chronological-forward order; instead it gets the
   newest `page_size` and, combined with `OFFSET`, silently skips an arbitrary middle
   band of messages. RT-04 ("only messages newer than the cursor") is not delivered
   correctly whenever more than one message arrived while disconnected.

2. **Lexicographic UUID tiebreak.** The comparison casts both sides to `id::text` and
   compares as text. UUID text ordering is *not* equivalent to native UUID ordering,
   and more importantly it is unrelated to insertion order (UUIDv4 is random). The
   docstring (line 146) claims "(sent_at, id) > cursor … composite comparison for
   same-millisecond tiebreak safety," but a random-UUID tiebreak does not provide a
   stable monotonic cursor at all — two messages with identical `sent_at` can be
   ordered either way, so the cursor can drop or duplicate a same-timestamp message.

**Fix:** Use a monotonic tiebreak (the cursor must be forward and the result forward-
ordered), or key the cursor on `(sent_at, id)` with native UUID comparison and order
ascending without offset:

```sql
SELECT id, role, body, sent_at, read_at, thread_id
FROM messages
WHERE thread_id = :tid
  AND (sent_at, id) > (SELECT sent_at, id FROM messages WHERE id = :after_id)
ORDER BY sent_at ASC, id ASC
LIMIT :limit
```

Drop `OFFSET` on the cursor path entirely (cursor and offset pagination are mutually
exclusive). If a stable tiebreak across equal `sent_at` is required, add a monotonic
column (e.g. a `bigserial seq`) rather than relying on random UUID text ordering.
Also reconcile the wire-ordering: the non-cursor list is `DESC` (newest-first) but the
catch-up path semantically needs forward delivery — pick one and document it.

### CR-02: Redis notification published outside the committed transaction → lost-notify / phantom-notify

**File:** `apps/backend/app/modules/messaging/service.py:91-94` and `:165-168`;
**caller:** `apps/backend/app/modules/messaging/router.py:164-171`

**Issue:** The module docstring and comments repeatedly assert "DB-first … publish AFTER
the DB write … publish AFTER commit" (service.py:5-9, router.py:156-157). The actual code
does **not** publish after commit. `send_client_message` calls `redis.publish(...)` at the
end of its body (service.py:91), and only *then* does the router's `_runner` call
`session.commit()` (router.py:171) — wait: in `send_client_message` the publish runs
*inside* the service, which runs *before* `await session.commit()`. So the frame is
published while the transaction is still open. Two failure modes result:

- **Phantom notify:** if the commit fails (constraint violation, serialization error,
  connection drop), the WS frame has already been published. The client receives
  `{"type":"new_message","messageId":...}`, issues a REST refetch, and the message does
  not exist — a confusing client state, and a DB-first invariant violation (P5).
- **`record_staff_message` has the same ordering** (service.py:165, publish before the
  caller commits).

The comments claim the publish is "co-located with the commit (publish AFTER commit)" but
the call graph proves the publish precedes the commit. This is a real correctness gap in
the exact invariant the phase was built to guarantee.

**Fix:** Move the publish to strictly after the successful commit. Since the service must
not commit (caller-owns-txn), pass the publish as a post-commit step in the router runner,
e.g.:

```python
async def _runner() -> tuple[int, bytes]:
    result = await service.send_client_message(session, client_id=client_id, payload=payload)
    await session.commit()
    # publish only after the row is durable (DB-first / P5)
    await redis.publish(
        f"cc:messaging:client:{client_id}",
        NewMessageEvent(message_id=result.id).model_dump_json(by_alias=True),
    )
    ...
```

Remove `redis` from the service signature (or have it return the channel/frame so the
caller publishes). Note that publishing after commit makes delivery best-effort
at-most-once (acceptable per the stated P5 design), whereas the current code is
at-least-once-with-phantoms.

## Warnings

### WR-01: `unread_count` reset races against concurrent staff sends (lost increment)

**File:** `apps/backend/app/modules/messaging/repository.py:209-248`

**Issue:** `mark_thread_read` unconditionally sets `client_unread_count = 0` (line 242).
If a staff message arrives between the `UPDATE messages … read_at = now()` (line 226) and
the `client_unread_count = 0` write — or after read but before commit of the mark-read txn
— that new staff message's increment is clobbered to 0, so the client shows 0 unread while
an unread staff message exists. The count and the actual unread row set can diverge.

**Fix:** Either recompute the count from the source of truth rather than blind-zeroing —
`SET client_unread_count = (SELECT COUNT(*) FROM messages WHERE thread_id=:tid AND role='staff' AND read_at IS NULL)` —
or decrement by the number actually marked (`len(updated)`) so concurrent inserts are
preserved. Deriving `unread_count` from the message rows entirely (no denormalised counter)
removes the class of bug.

### WR-02: WS fan-out swallows all send exceptions, masking encoding/logic bugs

**File:** `apps/backend/app/modules/messaging/ws.py:95-103`

**Issue:** `except Exception: break` (line 102) silences every error from `send_text`,
not just the "WS closed mid-send" case the comment describes. A serialization bug, a
non-str `raw["data"]`, or an unexpected runtime error all silently terminate the fan-out
loop with no log line, leaving the connection alive (heartbeat loop still running) but no
longer forwarding messages — a silent half-dead connection. The accompanying
`_log.debug("ws_frame_sent", data=raw["data"])` on line 97-101 also logs full frame data
at debug level, which for messaging is a minor information-exposure smell.

**Fix:** Narrow the except to the connection-closed cases and log unexpected ones:

```python
except (WebSocketDisconnect, RuntimeError):
    break
except Exception:
    _log.warning("ws_fan_out_send_failed", client_id=str(client_id), exc_info=True)
    break
```

Remove `data=raw["data"]` from the debug log (log the frame size or messageId only).

### WR-03: `response_model` does not match the returned type on POST /messages

**File:** `apps/backend/app/modules/messaging/router.py:125-142`

**Issue:** The route declares `response_model=ResponseEnvelope[MessageResponse]` (line 127)
but the handler returns a raw `starlette Response` produced by `idempotent_execute`
(return type `Response`, idempotency.py:254). When a handler returns a `Response` instance,
FastAPI bypasses `response_model` validation/serialization entirely — so the declared
`response_model` is dead metadata that silently does not enforce the response shape, and the
OpenAPI schema can drift from reality (e.g. if the runner's hand-built JSON at
router.py:172-176 ever diverges from `MessageResponse`). The mark-read route similarly
returns a bare `Response` with `response_model` absent, which is fine, but the POST
mismatch is misleading.

**Fix:** Either keep the `Response` return and drop/replace `response_model` with an
explicit `responses=` OpenAPI doc, or restructure so the success path returns the model
object. At minimum add a comment that `response_model` is documentation-only here because
the idempotency helper returns a pre-serialised `Response`.

### WR-04: `after` cursor subquery silently no-ops on an unknown/foreign message id

**File:** `apps/backend/app/modules/messaging/repository.py:178-191`

**Issue:** The cursor subquery `(SELECT sent_at, id::text FROM messages WHERE id = :after_id)`
is not scoped to the caller's `thread_id`. If `after` references a message id that does not
exist, the subquery returns NULL and the `>` comparison yields no rows (empty page) with no
error — a client passing a stale/garbage cursor gets a silent empty result rather than a
clear signal. More concerning: if `after` references a message id belonging to *another*
client's thread, the subquery still resolves its `sent_at`, and that timestamp is used as
the cursor boundary for *this* client's thread. It does not leak the other thread's rows
(the outer `WHERE thread_id = :tid` still scopes results), but it does let a caller use a
foreign message's timestamp as a probing oracle for relative recency. Low severity but worth
closing.

**Fix:** Scope the cursor subquery to the same thread:
`(SELECT sent_at, id FROM messages WHERE id = :after_id AND thread_id = :tid)`, and decide
explicitly whether an unresolved cursor should 422 or return the full first page.

### WR-05: `role` accepted as untyped `str` into a CHECK-constrained column — fragile contract

**File:** `apps/backend/app/modules/messaging/repository.py:67-126` and
`apps/backend/app/modules/messaging/service.py:65-69, 138-144`

**Issue:** `insert_message(role: str, ...)` takes a free `str` and writes it straight into
the `role` column, which has a DB CHECK `role IN ('client','staff')`. The service callers
pass the correct literals today, but a future caller passing any other string only fails at
the DB round-trip with an `IntegrityError` (and, since this runs inside the caller's UoW,
poisons the surrounding transaction). The branch logic in `insert_message` is also
stringly-typed (`if role == "staff"` / implicit else == client), so a typo like `"sta ff"`
would pass the `else` branch and *attempt* a client insert that then fails the CHECK.

**Fix:** Type the parameter as `Literal["client", "staff"]` and branch on the full set
explicitly (raise on anything else before issuing SQL), so a bad value fails fast in Python
without entering an open transaction.

### WR-06: WS fan-out task cancellation may not fully drain the `pubsub.listen()` generator

**File:** `apps/backend/app/modules/messaging/ws.py:161-172`

**Issue:** In the `finally` block the order is: cancel `fan_out_task`, await it, then
`pubsub.unsubscribe()` + `pubsub.aclose()`. The `_fan_out_loop` is blocked in
`async for raw in pubsub.listen()`. Cancelling the task raises `CancelledError` *inside*
the async generator; `pubsub.listen()` holds the dedicated connection. The
`contextlib.suppress(asyncio.CancelledError, Exception)` around the await (line 165) will
swallow the cancellation, but because `Exception` is also suppressed, a genuine failure to
tear down the subscriber connection (e.g. `aclose()` raising) is silently ignored. Under
churny reconnect load this can leak pooled pub/sub connections without any log signal.
Functionally close to correct, but the blanket `Exception` suppression hides the one failure
mode (subscriber-connection leak) the teardown exists to prevent.

**Fix:** Suppress `CancelledError` for the task await, but log (don't silently swallow)
unexpected exceptions from `unsubscribe`/`aclose`:

```python
fan_out_task.cancel()
with contextlib.suppress(asyncio.CancelledError):
    await fan_out_task
for step in (pubsub.unsubscribe(channel), pubsub.aclose()):
    try:
        await step
    except Exception:
        _log.warning("ws_pubsub_teardown_failed", client_id=str(client_id), exc_info=True)
```

## Info

### IN-01: `total` COUNT and history query are two separate round-trips without a snapshot

**File:** `apps/backend/app/modules/messaging/repository.py:153-204`

**Issue:** `get_or_create_thread`, the counts query, and the rows query run as three
separate statements. `total`/`unread_count` can be inconsistent with the returned `items`
if a write commits between them (under READ COMMITTED). For a 1:1 client thread this is
low-impact, but the paginated `total` can momentarily disagree with the page contents.

**Fix:** Acceptable for now; if exactness matters later, run under REPEATABLE READ or fold
the count into the same statement via a window function (`COUNT(*) OVER ()`).

### IN-02: Migration FK uses `ON DELETE RESTRICT` — clients become undeletable once they have a thread

**File:** `apps/backend/alembic/versions/0064_messaging_threads.py:64-69`,
`apps/backend/app/modules/messaging/models.py:48-56`

**Issue:** `message_threads.client_id` FK is `ondelete="RESTRICT"`. A client with any
thread row can no longer be hard-deleted; combined with the existing soft-delete model this
is probably intended, but it silently blocks any future hard-delete/GDPR-erase path. Worth a
deliberate decision record rather than an implicit RESTRICT.

**Fix:** Confirm the intent; if client erasure is ever required, plan a cascade or an
explicit thread-purge step.

### IN-03: `NewMessageEvent.type` discriminator is declared but never used by the WS sender

**File:** `apps/backend/app/modules/messaging/schemas.py:98-113`,
`apps/backend/app/modules/messaging/ws.py:96`

**Issue:** The fan-out forwards `raw["data"]` verbatim (the pre-serialised
`NewMessageEvent` JSON published by the service), so the `type: Literal["new_message"]`
discriminator is only ever set on the publish side and never validated/branched on the WS
side. This is fine for Phase 90 but the "extensible discriminated union" rationale in the
docstring is aspirational — there is no consumer that switches on `type` yet.

**Fix:** None required now; note that future event types will need a parse+dispatch step in
`_fan_out_loop` rather than blind forwarding.

### IN-04: Heartbeat is only sent on idle-timeout, never while the client is actively sending

**File:** `apps/backend/app/modules/messaging/ws.py:114-146`

**Issue:** `heartbeat_elapsed` resets to 0 on every inbound frame (line 124), and the ping
is only emitted in the `TimeoutError` branch. A client that sends any frame more often than
every 30s will never receive a server `ping`. This is harmless for liveness (the inbound
traffic itself keeps the socket warm), but if the client relies on receiving periodic pings
as a server-liveness signal, that contract is not met under chatty clients.

**Fix:** None required for Phase 90 (clients send via REST, not WS); document that pings are
idle-only if a client-side liveness check is later added.

---

_Reviewed: 2026-06-07_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
