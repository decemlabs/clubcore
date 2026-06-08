---
phase: 93-telegram-bridge
reviewed: 2026-06-08T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - apps/backend/app/core/config.py
  - apps/backend/app/integrations/telegram/sender.py
  - apps/backend/app/integrations/telegram/handlers.py
  - apps/backend/app/workers/tasks/forward_to_staff.py
  - apps/backend/app/workers/__init__.py
  - apps/backend/app/workers/telegram_bot.py
  - apps/backend/app/modules/messaging/router.py
  - apps/backend/app/modules/messaging/repository.py
  - apps/backend/tests/integration/telegram_bot/test_forward_to_staff.py
  - apps/backend/tests/integration/telegram_bot/test_staff_reply_handler.py
  - apps/backend/tests/integration/telegram_bot/test_handler_context_shape.py
findings:
  critical: 0
  warning: 5
  info: 4
  total: 9
status: issues_found
---

# Phase 93: Code Review Report

**Reviewed:** 2026-06-08T00:00:00Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Reviewed the Telegram bridge implementation: the `forward_to_staff` ARQ task,
the `staff_reply_handler`, the `send_photo` sender boundary, the HandlerContext
extension, the messaging router enqueue seam, and the repository helper. The
core security spine is solid — I traced and confirmed the high-value invariants
the phase brief flagged:

- **Echo loop guards** — triple guard verified: `is_bot` early-return
  (`handlers.py:744`), `_dedupe_update_id` SET-NX (`:753`), and anchor-presence
  requirement (`:775`). All three are present and correctly ordered relative to
  the persistence path.
- **Anti-misroute** — `client_id`/`thread_id` are sourced **only** from the
  Redis anchor keyed by `reply_to.message_id` (`:774`, `:781`); there is no
  most-recent-thread fallback. A missing anchor drops the message with a hint.
- **IDOR on object_key** — the router re-fetches the object_key via
  `repository.get_owned_attachment(..., client_id=client_id)` (`router.py:306`)
  which is IDOR-gated on the principal's `client_id`, so the path forwarded to
  the worker can never reference a foreign attachment.
- **Post-commit publish/enqueue** — both the router (`router.py:283-322`) and
  the reply handler (`handlers.py:802-819`) commit FIRST, then publish/enqueue.
  DB-first (P5 / CR-02) is honoured.
- **PII in publish frames** — `NewMessageEvent` / `ReadReceiptEvent` carry only
  ids/timestamps (`service.py:79-104`); the message body is never published over
  pub/sub.
- **HandlerContext field-order** — `messaging_service` is appended at the END
  (`handlers.py:99`), construction in the worker matches (`telegram_bot.py:120`),
  and the regression-guard test asserts the 8-field order.
- **Audit event** — `chat_staff_reply_sent` is registered in
  `LOCKED_AUDIT_EVENTS` (`audit.py:478`); the co-transactional emit precedes
  commit.

No blockers found. The findings below are correctness-degradation and
robustness gaps, mostly around Telegram transport limits and a few input-edge
cases that the happy-path tests do not exercise.

## Warnings

### WR-01: Photo-attachment forward silently drops when body exceeds the 1024-char Telegram caption limit

**File:** `apps/backend/app/workers/tasks/forward_to_staff.py:95-106`, `apps/backend/app/integrations/telegram/sender.py:117-132`
**Issue:** `SendMessageRequest.body` allows up to 4000 chars
(`messaging/schemas.py:111`). For an attachment-bearing message, the full
`_render_dm(...)` output (identity header + up to 4000-char body) is passed as
the **caption** to `bot.send_photo`. Telegram caps photo captions at **1024
characters**; a longer caption makes the Bot API reject the call with
`BadRequest("Message caption is too long")`. `send_photo` classifies that as
`ok=False, blocked=False, error=...` (it is neither "chat not found" nor
Forbidden), so `forward_to_staff` returns `"failed"`, writes no anchor, and ARQ
retries `_max_tries=2` then drops permanently. The client's message has already
been committed and acknowledged, so the staff member never sees a message a
client believes was delivered — a silent delivery hole, not a visible error.
**Fix:** When an attachment is present, send the photo with a truncated/short
caption (or no caption) and follow with a separate `send_text_dm` for the full
body, or split bodies > ~1000 chars across a caption + text message. Minimal
guard:
```python
caption = _render_dm(client_name, client_phone, body)
if attachment_id is not None and object_key is not None:
    storage = ctx["storage"]
    ...
    photo_bytes = b"".join(chunks)
    # Telegram photo caption hard-limit is 1024 chars.
    caption_for_photo = caption if len(caption) <= 1024 else caption[:1021] + "…"
    result = await telegram_sender.send_photo(
        bot, staff_chat_id, photo_bytes, caption=caption_for_photo
    )
    # If we truncated, deliver the remainder as a follow-up text DM.
    if len(caption) > 1024:
        await telegram_sender.send_text_dm(bot, staff_chat_id, caption)
```

### WR-02: Text-only forward can exceed the 4096-char Telegram message limit

**File:** `apps/backend/app/workers/tasks/forward_to_staff.py:95-109`, `apps/backend/app/integrations/telegram/sender.py:84-99`
**Issue:** Same root cause as WR-01 but for the text path. `_render_dm` prepends
a header ("Новое сообщение от клиента\nИмя: {client_name}\nТелефон:
{client_phone}\n\n") to a body that may be 4000 chars. With a long client name
the rendered text exceeds Telegram's 4096-char `sendMessage` limit, producing a
`BadRequest("message is too long")` → `"failed"` → permanent drop after retries,
with the client message already committed. The body cap (4000) was chosen for
the PWA UI, not the Telegram transport, so the header overhead is unaccounted
for.
**Fix:** Truncate the rendered DM to 4096 chars (or chunk it) before calling
`send_text_dm`, e.g. `caption = caption if len(caption) <= 4096 else caption[:4093] + "…"`.

### WR-03: Malformed/partial Redis anchor JSON crashes the reply handler instead of degrading to the stale-anchor hint

**File:** `apps/backend/app/integrations/telegram/handlers.py:780-781`
**Issue:** After confirming the anchor exists, the handler does
`anchor = json.loads(raw_anchor)` then `client_id = UUID(anchor["client_id"])`
with no guard. A corrupted value, a truncated write, a schema drift (e.g. an
anchor missing `client_id`), or a non-UUID value raises `JSONDecodeError` /
`KeyError` / `ValueError`. The exception escapes to `_global_error_handler`,
which logs and drops it — but the staff member receives **no feedback at all**
(neither the routed reply nor the stale-anchor hint), and the update_id has
already been consumed by the dedup SET-NX, so a Telegram re-delivery is silently
suppressed too. The handler treats a present-but-unparseable anchor as a hard
crash rather than the documented "drop with hint" degradation.
**Fix:** Wrap the parse and treat any failure as a stale/invalid anchor:
```python
try:
    anchor = json.loads(raw_anchor)
    client_id = UUID(anchor["client_id"])
except (ValueError, KeyError, TypeError):
    logger.warning("staff_reply_anchor_corrupt", message_id=reply_to.message_id, chat_id=chat_id)
    await ctx.sender.send_text_dm(bot, chat_id, _DM_STAFF_STALE_ANCHOR)
    return
```

### WR-04: `update_id` dedup is consumed before the staff-chat guard, suppressing legitimate later processing

**File:** `apps/backend/app/integrations/telegram/handlers.py:752-764`
**Issue:** `_dedupe_update_id` is called (`:753`) BEFORE the defensive
staff-chat-id check (`:758`). Because the `MessageHandler` filter
(`tg_filters.Chat(staff_chat_id)`) is the real gate, this in-handler check
should never fire in production — but if it ever does (misconfiguration, or the
belt-and-suspenders path the docstring claims to protect), the update_id has
already been burned into `cc:bot:update:{update_id}` with a 1h TTL. Since
Telegram `update_id` is globally unique per bot, this is harmless in practice,
but it inverts the intended order: the cheap, side-effect-free chat-id guard
should run before mutating shared Redis state. More importantly, the ordering
means the "wrong chat" debug log and the dedup key both fire for any update that
slips past the filter, muddying observability.
**Fix:** Move the staff-chat-id guard (`:757-764`) above the `_dedupe_update_id`
call so the dedup key is only written for updates actually destined for the
staff routing path.

### WR-05: Any member of the staff *group* chat is treated as authoritative "staff" — no per-user authorization

**File:** `apps/backend/app/integrations/telegram/handlers.py:784-790`, `apps/backend/app/core/config.py:103-109`
**Issue:** The config comment explicitly supports a **group** chat_id
(`config.py:108` — "Set to the staff DM chat_id or group chat_id"). When
`staff_telegram_chat_id` is a group, the handler routes a reply from **any
non-bot member** of that group to the client as an authoritative `role='staff'`
message (`record_staff_message`), with `telegram_user_id` recorded but never
checked against an allowlist. Anyone added to (or already lurking in) the staff
group can impersonate the gym to clients. The `is_bot` guard only filters the
bot itself; there is no membership/authorization check. This may be an accepted
trust assumption for a single-gym pet project, but it is undocumented at the
callsite and the group-chat option makes the blast radius non-trivial.
**Fix:** Either (a) document the trust model explicitly at the handler ("every
non-bot member of the staff chat is trusted as staff — keep the group
membership tightly controlled"), or (b) gate on an allowlist of authorized
Telegram user_ids when the staff chat is a group. At minimum, record the
`telegram_user_id` in the audit payload (currently only `client_id` is emitted
at `:799`) so impersonation is forensically traceable.

## Info

### IN-01: `forward_to_staff` buffers the entire attachment into memory before sending

**File:** `apps/backend/app/workers/tasks/forward_to_staff.py:100-103`
**Issue:** The task accumulates every chunk from `storage.open_stream` into a
list and `b"".join(chunks)` to build `photo_bytes`. Attachments are capped at
5MB upstream (`router.py:167-171`), so this is bounded and acceptable at
pet-project scale, but the streaming interface is defeated — the whole object is
materialised. Noted for awareness; not a defect given the 5MB cap.
**Fix:** No action required at v1 scale. If attachment caps ever rise, pass the
stream/iterator to `send_photo` directly (PTB accepts file-like inputs).

### IN-02: `_object_key`/`_client_phone` empty-string fallbacks can produce a misleading staff DM

**File:** `apps/backend/app/modules/messaging/router.py:299-309`
**Issue:** When `get_client_display` returns None (client soft-deleted between
send and enqueue, an unlikely race), the DM renders `client_name="Клиент"` and
`client_phone=""`, yielding a "Телефон: " line with no value. Similarly, an
attachment whose `get_owned_attachment` returns None leaves `_object_key=None`,
silently downgrading a photo message to a text-only forward. Both are graceful
degradations rather than crashes, but the empty phone line reads as a render
glitch.
**Fix:** Omit the phone line when empty, or render "Телефон: —". Optional.

### IN-03: Test/prod Redis parity gap — fakeredis returns bytes, prod returns str

**File:** `apps/backend/tests/integration/telegram_bot/test_staff_reply_handler.py:150`, `apps/backend/app/integrations/telegram/handlers.py:780`
**Issue:** Tests use `fakeredis.aioredis.FakeRedis()` without
`decode_responses=True`, so `redis.get(...)` returns `bytes`; the production bot
worker uses `redis_lifespan_manager()` which sets `decode_responses=True` and
returns `str`. `json.loads` happens to accept both, so the tests pass, but they
do not exercise the actual prod type. Combined with WR-03, a corrupt-anchor test
would behave subtly differently between fakeredis and prod.
**Fix:** Construct the fixture as `fakeredis.aioredis.FakeRedis(decode_responses=True)`
to match the prod Redis client contract.

### IN-04: `forward_to_staff` "ok but no message_id" branch returns "sent" while writing no anchor

**File:** `apps/backend/app/workers/tasks/forward_to_staff.py:125-131`
**Issue:** The `elif result.ok:` branch (send succeeded but `message_id is None`)
logs a warning and returns `"sent"` without writing the routing anchor. A staff
reply to such a forwarded message will then hit the stale-anchor path and be
dropped with a hint — the operator cannot reply to that specific client message.
The docstring says this "should not happen with PTB", and `send_photo`/
`send_text_dm` always populate `message_id` on success, so this is effectively
dead defensive code. Returning `"sent"` (vs a distinct status) also conflates it
with the fully-anchored success in any downstream metric.
**Fix:** Either drop the unreachable branch or return a distinct status (e.g.
`"sent_no_anchor"`) so the missing-anchor condition is observable rather than
masquerading as a normal send.

---

_Reviewed: 2026-06-08T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
