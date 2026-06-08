# Phase 93: Telegram Bridge - Pattern Map

**Mapped:** 2026-06-07
**Files analyzed:** 7 new/modified files
**Analogs found:** 7 / 7

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `app/workers/tasks/forward_to_staff.py` | task | event-driven | `app/workers/tasks/dispatch_email.py` | exact |
| `app/integrations/telegram/handlers.py` | handler | request-response | self (append-only edit) | exact |
| `app/workers/telegram_bot.py` | worker entry | event-driven | self (append-only edit) | exact |
| `app/integrations/telegram/sender.py` | integration utility | request-response | self (extend with `send_photo`) | exact |
| `app/core/config.py` | config | n/a | self — `owner_alert_telegram_chat_id` field | exact |
| `app/modules/messaging/service.py` | service | CRUD | self — `send_client_message` seam + `record_staff_message` | exact |
| `app/integrations/storage/s3.py` | integration | streaming | self — `open_stream` async generator | exact |

---

## Pattern Assignments

### `app/workers/tasks/forward_to_staff.py` (task, event-driven)

**Analog:** `app/workers/tasks/dispatch_email.py`

**Imports pattern** (dispatch_email.py lines 51-65):
```python
from __future__ import annotations

from typing import Any, Final
from uuid import UUID

import structlog

from app.core import audit
# NOTE: import ONLY from app.integrations.* — never from app.modules.*
# (workers ⊥ modules contract; D-42-07 / workers/__init__.py:1-21)
from app.integrations.telegram import sender as telegram_sender
from app.integrations.storage.types import Storage

_log: Final = structlog.get_logger("workers.tasks.forward_to_staff")
```

**Task function signature** (dispatch_email.py lines 94-100):
```python
async def forward_to_staff(ctx: dict[str, Any], ...) -> str:
    """Forward a client message to staff DM on Telegram.

    ctx keys required:
      - "redis"       : redis.asyncio.Redis — for chat_forwarding_log SET
      - "sessionmaker": async_sessionmaker[AsyncSession] — for attachment fetch
      - "storage"     : Storage — for photo bytes if attachment present
    Returns 'sent' on ok, 'failed' otherwise (ARQ persists to result store).
    """
    session_factory = ctx["sessionmaker"]
    redis = ctx["redis"]
    storage: Storage = ctx["storage"]
    bot = ctx["bot"]  # telegram.Bot instance — wired in on_startup
    ...
    return "sent" if result.ok else "failed"
```

**ARQ enqueue call shape** (dispatcher.py lines 209-220, workers/__init__.py lines 415-422):
```python
# Enqueued post-commit in messaging/service.py send_client_message seam:
await arq_pool.enqueue_job(
    "forward_to_staff",
    # Primitive kwargs only — cloudpickle-safe per D-42-16
    client_id=str(client_id),
    message_id=str(message_id),
    thread_id=str(thread_id),
    body=body,                   # str — rendered at enqueue time
    client_name=client_name,     # first + last name — PII for single-gym operator
    client_phone=client_phone,   # phone number
    attachment_id=str(attachment_id) if attachment_id else None,
    object_key=object_key if attachment_id else None,
    _max_tries=2,
    _expires=20,                 # mirrors dispatch_email convention (D-42-13)
)
```

**WorkerSettings registration** (workers/__init__.py lines 140-178):
```python
# In WorkerSettings.functions list — add bare callable (no per-function config):
from app.workers.tasks.forward_to_staff import forward_to_staff

functions: ClassVar[list[Any]] = [
    ...,
    dispatch_email,
    forward_to_staff,  # Phase 93 BRDG-01 — post-commit Telegram forward
]
```

**Redis chat_forwarding_log SET** (after successful bot.send_message):
```python
# Key: cc:messaging:tg_msg:{tg_message_id} → JSON {"thread_id": ..., "client_id": ...}
# TTL: 7 days (604800 seconds) — pre-locked (STATE.md)
import json
mapping = json.dumps({"thread_id": str(thread_id), "client_id": str(client_id)})
await redis.set(
    f"cc:messaging:tg_msg:{sent_message_id}",
    mapping,
    ex=604800,  # 7 days
)
```

**Sentinel / disabled pattern** (telegram_bot.py lines 88-98):
```python
settings = get_settings()
if settings.staff_telegram_chat_id is None:
    _log.info(
        "telegram_bridge_disabled",
        reason="STAFF_TELEGRAM_CHAT_ID not set — forward_to_staff is a no-op",
    )
    return "skipped"
```

---

### `app/integrations/telegram/handlers.py` — HandlerContext extension (append-only)

**Analog:** `app/integrations/telegram/handlers.py` (self — append field at END)

**Current HandlerContext definition** (handlers.py lines 64-93):
```python
class HandlerContext(NamedTuple):
    """Closure passed to every handler -- D-05.

    Field order is part of the stable contract — positional construction in
    workers/telegram_bot.py:main() depends on it. New fields are APPENDED at
    the END (never inserted in the middle).
    """
    session_factory: async_sessionmaker[AsyncSession]
    telegram_service: ModuleType
    sender: ModuleType
    visits_service: ModuleType
    redis: Redis
    bookings_service: ModuleType  # Phase 40 D-40-04
    schedule_service: ModuleType  # Phase 40 D-40-06
    # Phase 93 — append at END (field-order contract):
    messaging_service: ModuleType  # app.modules.messaging.service
```

**Import to add** (top of handlers.py, alongside existing ModuleType imports):
```python
# No new import needed — messaging_service is typed as ModuleType
# (matches the telegram_service / visits_service / bookings_service / schedule_service pattern)
```

**Staff-reply handler signature** (mirrors checkin_handler pattern, handlers.py lines 290-310):
```python
async def staff_reply_handler(
    update: Any,  # telegram.Update at runtime
    context: Any,  # telegram.ext.CallbackContext at runtime
    ctx: HandlerContext,
) -> None:
    """PTB MessageHandler for staff Telegram Reply on a forwarded message.

    Filters: message in STAFF_TELEGRAM_CHAT_ID + reply_to_message is not None.
    echo-loop guard: is_bot check + chat_forwarding_log lookup.
    Routing: cc:messaging:tg_msg:{reply_to.message_id} → thread_id / client_id.
    Stale/missing mapping (>7d) → DM staff with hint, drop message (SC-2).
    Plain (non-Reply) message → ignore + one-time "use Reply" hint.
    """
    ...
```

**Redis dedup reuse** (handlers.py lines 96-120 — `_dedupe_update_id` helper):
```python
# Reuse the existing module-level helper — no changes needed
if not await _dedupe_update_id(ctx.redis, update_id, chat_id):
    return

# Additional echo-loop guard (is_bot):
effective_user = update.effective_user
if effective_user is None or effective_user.is_bot:
    return
```

**chat_forwarding_log lookup**:
```python
# Key pattern matches forward_to_staff.py SET:
reply_to = update.message.reply_to_message
if reply_to is None:
    # Plain message — ignore + one-time "use Reply" hint
    await ctx.sender.send_text_dm(bot, staff_chat_id, _DM_USE_REPLY_HINT)
    return

raw = await ctx.redis.get(f"cc:messaging:tg_msg:{reply_to.message_id}")
if raw is None:
    # Stale/missing mapping (>7d TTL expired)
    await ctx.sender.send_text_dm(bot, staff_chat_id, _DM_THREAD_NOT_FOUND)
    return

import json
mapping = json.loads(raw)
thread_id = UUID(mapping["thread_id"])
client_id = UUID(mapping["client_id"])
```

**record_staff_message call** (via ctx.messaging_service — no static module import):
```python
async with ctx.session_factory() as session:
    result = await ctx.messaging_service.record_staff_message(
        session,
        client_id=client_id,
        body=update.message.text or "",
        telegram_user_id=effective_user.id,
        telegram_username=effective_user.username,
    )
    await session.commit()
    # Post-commit: publish new_message + read_receipt (CR-02 / DB-first / T-91-PHANTOM)
    await ctx.messaging_service.publish_new_message(
        ctx.redis,
        client_id=client_id,
        message_id=result.id,
    )
    if result.reply_read_at is not None:
        await ctx.messaging_service.publish_read_receipt(
            ctx.redis,
            client_id=client_id,
            read_at=result.reply_read_at,
        )
    # audit: chat_staff_reply_sent (pre-registered LOCKED_AUDIT_EVENTS)
    from app.core import audit as _audit
    await _audit.emit(
        session,   # NOTE: session already committed — this is a second write;
                   # if audit must be co-transactional, emit BEFORE commit above
        "chat_staff_reply_sent",
        actor_user_id=None,
        resource_type="message",
        resource_id=result.id,
        client_id=str(client_id),
    )
```

---

### `app/workers/telegram_bot.py` — main() extension (append-only)

**Analog:** `app/workers/telegram_bot.py` (self — add import + HandlerContext field + MessageHandler)

**New module import to add** (alongside existing module imports, lines 46-53):
```python
from app.modules.messaging import service as messaging_service  # Phase 93 D-06 relaxation
```

**HandlerContext construction extension** (telegram_bot.py lines 104-115):
```python
ctx = HandlerContext(
    session_factory=sessionmaker,
    telegram_service=telegram_service,
    sender=telegram_sender,
    visits_service=visits_service,
    redis=redis,
    bookings_service=bookings_service,
    schedule_service=schedule_service,
    # Phase 93 — append at END (field-order contract from handlers.py docstring):
    messaging_service=messaging_service,
)
```

**MessageHandler registration** (mirrors `_book_callback_adapter` pattern, lines 134-142):
```python
# After build_application + the existing CallbackQueryHandler add_handler block:
from telegram.ext import MessageHandler, filters as tg_filters

staff_chat_id = settings.staff_telegram_chat_id
if staff_chat_id is not None:
    async def _staff_reply_adapter(update: Any, context: Any) -> None:
        await staff_reply_handler(update, context, ctx)

    application.add_handler(
        MessageHandler(
            # Filter: message in the staff chat AND is a Reply (reply_to_message present)
            # OR any message in staff chat (handler body handles non-Reply with hint)
            tg_filters.Chat(staff_chat_id) & tg_filters.TEXT,
            callback=_staff_reply_adapter,
        )
    )
else:
    log.info(
        "staff_reply_handler_disabled",
        reason="STAFF_TELEGRAM_CHAT_ID not set",
    )
```

---

### `app/integrations/telegram/sender.py` — add `send_photo`

**Analog:** `app/integrations/telegram/sender.py` (self — extend with new function)

**Existing `send_text_dm` pattern** (sender.py lines 57-90) — copy exactly:
```python
async def send_photo(
    bot: Bot,
    chat_id: int,
    photo: bytes,
    caption: str | None = None,
) -> SendResult:
    """Send a photo (bytes) DM to chat_id with optional caption.

    Same SendResult contract as send_text_dm. Used by forward_to_staff ARQ task
    to forward client image attachments to the staff DM. Never re-raises transport errors.
    """
    try:
        await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=caption,
        )
        return SendResult(ok=True)
    except Forbidden:
        return SendResult(ok=False, blocked=True)
    except BadRequest as exc:
        msg = str(exc).lower()
        if "chat not found" in msg or "chat_id" in msg:
            return SendResult(ok=False, blocked=True)
        return SendResult(ok=False, blocked=False, error=str(exc))
    except Exception as exc:
        return SendResult(ok=False, blocked=False, error=str(exc))
```

---

### `app/core/config.py` — add `staff_telegram_chat_id` field

**Analog:** `app/core/config.py` lines 99-100 — `owner_alert_telegram_chat_id: int | None = None`

**Exact declaration pattern to copy** (config.py lines 94-101):
```python
# Phase 52 additions (D-52-09, NOT-04): Owner operator-alert recipients.
# ...
owner_alert_telegram_chat_id: int | None = None
owner_alert_email: str | None = None
```

**New field to add** (append after `owner_alert_email`, before `email:` block):
```python
# Phase 93 BRDG-01 — staff Telegram chat for client message forwarding.
# When absent (None), the Telegram bridge (forward_to_staff ARQ task +
# staff_reply_handler) is disabled with a structured log line.
# Mirrors the owner_alert_telegram_chat_id sentinel pattern (D-52-09).
# Env var: STAFF_TELEGRAM_CHAT_ID (int). Set to the staff DM chat_id or
# group chat_id. Leave unset in dev to keep bridge disabled.
staff_telegram_chat_id: int | None = None
```

---

### `app/modules/messaging/service.py` — fill the Phase 93 forward seam

**Analog:** self — lines 194-197 mark the exact insertion point:
```python
# TODO Phase 93: Telegram bridge forward seam (record + enqueue ARQ DM)
# When the bridge is active, enqueue an ARQ task here to forward the message
# body to STAFF_TELEGRAM_CHAT_ID via bot.send_message(). This is a no-op in
# Phase 90 — the seam is documented here so Phase 93 has a clear insertion point.
```

**Post-commit enqueue pattern** (mirrors main.py lines 709-714, workers/__init__.py lines 415-422):

The seam in `send_client_message` does NOT commit — it is called before commit by the router. The enqueue must happen AFTER commit. Therefore the enqueue must move to the router's `_runner()` closure (router.py lines 276-295), not inside `service.send_client_message`:

```python
# In router.py _runner() — AFTER session.commit() and publish_new_message:
async def _runner() -> tuple[int, bytes]:
    result = await service.send_client_message(session, client_id=client_id, payload=payload)
    await session.commit()
    # CR-02: publish ONLY after commit
    await service.publish_new_message(redis, client_id=client_id, message_id=result.id)
    # Phase 93 BRDG-01: enqueue forward task post-commit (never in-transaction)
    settings = get_settings()
    if settings.staff_telegram_chat_id is not None:
        arq_pool = request.app.state.arq_pool
        await arq_pool.enqueue_job(
            "forward_to_staff",
            client_id=str(client_id),
            message_id=str(result.id),
            thread_id=str(result.thread_id),
            body=result.body,
            attachment_id=str(result.attachment.id) if result.attachment else None,
            object_key=None,  # forward_to_staff fetches from DB by attachment_id
            _max_tries=2,
            _expires=20,
        )
    ...
```

Alternatively, if the seam stays in `service.py`, an `arq_pool` parameter must be threaded in — the router pattern above avoids that coupling and matches the `dispatch_email` precedent (the router/handler owns the enqueue, not the service).

**`record_staff_message` contract** (service.py lines 222-323) — no changes needed; already designed for Phase 93. Key return fields:
```python
# StaffMessageResult — superset of MessageResponse
result.id            # UUID — message_id
result.reply_read_at # datetime | None — for publish_read_receipt post-commit
result.thread_id     # UUID
```

---

### `app/integrations/storage/s3.py` — `open_stream` (read-only reference)

**No changes needed.** The forward task reads photo bytes via:
```python
# open_stream is an async generator (s3.py lines 80-95):
async def open_stream(self, key: str) -> AsyncIterator[bytes]:
    async with self._session.client("s3", ...) as client:
        response = await client.get_object(Bucket=self._bucket, Key=key)
        body = response["Body"]
        async for chunk in body.iter_chunks(_STREAM_CHUNK_SIZE):
            yield chunk
```

**Usage in forward_to_staff task** — collect all chunks into bytes for `send_photo`:
```python
from app.integrations.storage.types import Storage

storage: Storage = ctx["storage"]  # injected in on_startup
chunks = []
async for chunk in storage.open_stream(object_key):
    chunks.append(chunk)
photo_bytes = b"".join(chunks)
result = await telegram_sender.send_photo(bot, staff_chat_id, photo_bytes, caption=caption)
```

**Storage type** — `app/integrations/storage/types.py` defines the `Storage` Protocol with `put`, `open_stream`, `ensure_bucket`. The ARQ worker's `on_startup` must wire `ctx["storage"]` the same way `app/main.py` wires `app.state.storage` via `build_storage(settings)`.

---

## Shared Patterns

### Redis update_id dedup
**Source:** `app/integrations/telegram/handlers.py` lines 96-120 (`_dedupe_update_id`)
**Apply to:** `staff_reply_handler`
```python
dedup_key = f"cc:bot:update:{update_id}"
set_result: Any = await redis.set(dedup_key, "1", nx=True, ex=3600)
# Returns None on replay → return early (fail-open on Redis errors)
```

### Redis chat_forwarding_log key pattern
**Source:** STATE.md pre-lock + CONTEXT.md decisions
**Apply to:** `forward_to_staff` (SET) and `staff_reply_handler` (GET)
```python
# Key: cc:messaging:tg_msg:{tg_message_id}
# Value: JSON {"thread_id": "<uuid>", "client_id": "<uuid>"}
# TTL: 604800 seconds (7 days)
```

### Sentinel / disabled bridge pattern
**Source:** `app/workers/telegram_bot.py` lines 88-98 (placeholder token check)
**Apply to:** `forward_to_staff` task (early return when `staff_telegram_chat_id` is None), `staff_reply_handler` registration (skip add_handler)
```python
if settings.staff_telegram_chat_id is None:
    _log.info("telegram_bridge_disabled", reason="STAFF_TELEGRAM_CHAT_ID not set")
    return "skipped"
```

### ARQ WorkerSettings functions list registration
**Source:** `app/workers/__init__.py` lines 140-178
**Apply to:** `forward_to_staff` — add bare callable to `functions` list. Also add to `on_startup` if `ctx["storage"]` and `ctx["bot"]` need wiring there.

### Caller-owns-txn (no commit inside service)
**Source:** `app/modules/messaging/service.py` module docstring lines 1-19
**Apply to:** `record_staff_message` call in `staff_reply_handler` — handler calls `session.commit()`, then publishes Redis frames.

### Audit emit pattern
**Source:** `app/modules/messaging/service.py` lines 177-184, `app/workers/tasks/dispatch_email.py` lines 170-198
**Apply to:** `forward_to_staff` (emit `chat_staff_reply_sent` on successful staff DM send), `staff_reply_handler` (after `record_staff_message` + commit)
```python
await audit.emit(
    session,
    "chat_staff_reply_sent",  # pre-registered in LOCKED_AUDIT_EVENTS (INFRA-15)
    actor_user_id=None,
    resource_type="message",
    resource_id=message_id,
    client_id=str(client_id),
)
```

### Structlog naming convention
**Source:** `app/workers/tasks/dispatch_email.py` line 64
```python
_log: Final = structlog.get_logger("workers.tasks.forward_to_staff")
```
For handler: `logger = structlog.get_logger("telegram.handler")` (matches existing handlers.py line 61).

---

## No Analog Found

None — all 7 files/patterns have direct analogs in the codebase.

---

## Metadata

**Analog search scope:** `apps/backend/app/workers/`, `apps/backend/app/integrations/telegram/`, `apps/backend/app/integrations/storage/`, `apps/backend/app/modules/messaging/`, `apps/backend/app/core/`
**Files scanned:** 8 files read in full
**Pattern extraction date:** 2026-06-07
