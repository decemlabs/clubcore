# Phase 93: Telegram Bridge - Context

**Gathered:** 2026-06-07
**Status:** Ready for planning
**Mode:** Smart discuss (autonomous — pre-locked architecture confirmed + 4 open decisions resolved)

<domain>
## Phase Boundary

Bridge the client↔gym chat (built in Phases 90–92) to staff over Telegram, so a single-gym operator can read and answer client messages without an admin UI (admin-web stays frozen until v2.6).

Delivers BRDG-01/02/03:
- **BRDG-01** — A client message (text + photo) is forwarded to staff in Telegram via the existing bot-worker, enqueued through an ARQ task (never synchronously in-transaction).
- **BRDG-02** — A staff member's native Telegram **Reply** is routed to the correct client thread, persisted in Postgres, and delivered to the client's live WS connection.
- **BRDG-03** — Reply routing is anchored in Redis (`tg_message_id → thread/client`); echo-loops and misroutes are impossible (the latter visible only with ≥2 active threads).

Out of scope: admin-web chat inbox (v2.6), staff identity/auth (v2.5 staff is anonymous `role='staff'`), broadcast/group messaging, web-push.
</domain>

<decisions>
## Implementation Decisions

### Pre-locked architecture (from v2.5 research / STATE.md — carried in, not re-litigated)
- **Worker→modules relaxation (D-06/D-10):** `telegram_bot.py` imports `messaging.service` directly; `HandlerContext` gains a `messaging_service` field **appended at END** (NamedTuple field-order contract). No `.importlinter` change required for the bridge.
- **Forwarding via ARQ task, NOT in-transaction:** client message is written to Postgres first (DB-first, P5); after commit, an ARQ job is enqueued to send the staff DM. Avoids 429 rate-limit cascades inside the request path.
- **`chat_forwarding_log` (Redis):** key `cc:messaging:tg_msg:{tg_message_id} → thread_id` (and originating client_id), TTL **7 days**. Set when the bot DMs staff; consumed when a staff reply arrives. This mapping is the routing anchor (SC-2) and a natural echo-loop breaker (SC-3).
- **Anonymous staff (v2.5):** staff messages stored with `role='staff'`; `telegram_user_id` / `telegram_username` captured as nullable audit fields (full staff identity → v2.6). `record_staff_message(...)` already exists in `messaging/service.py` (Phase 90 Plan 02) — the reply handler calls it.
- **`STAFF_TELEGRAM_CHAT_ID`:** new Settings field (`int | None`); the bridge is **disabled** (forward enqueue + reply handler are no-ops) when absent, with a structured log line. Mirrors the existing `owner_alert_telegram_chat_id` precedent.
- **Reply-as-read:** when staff replies, prior client messages in that thread are marked `read_at=now()` and a WS `read_receipt` event is published (Telegram has no per-message read API).
- **Echo-loop guard:** `is_bot` check on incoming updates + `chat_forwarding_log` presence; reuse the existing Redis `update_id` dedup pattern already used by the `/checkin` handler.
- **Audit:** `chat_staff_reply_sent` is already pre-registered in `LOCKED_AUDIT_EVENTS` (INFRA-15).

### Forwarding format (staff-facing) — resolved this discuss
- **DM identity:** forwarded DM includes the client's **first + last name and phone** plus the message body. Single-gym; staff already hold client PII and need to recognize who they're answering.
- **Photo attachments:** forward the **actual image** to staff via Telegram `send_photo` (bytes streamed server-side from the stored S3 object via the storage adapter) so staff see it inline — not just a marker/link.
- **Forward failure (Telegram 429 / down):** ARQ **retry with backoff** (`_max_tries`/`_expires` per the existing dispatch-email task precedent); never blocks the client send (already async/post-commit).

### Reply routing edge cases — resolved this discuss
- **Stale/missing mapping (>7d TTL expired, or no anchor):** the bot **replies to staff** with a "не могу определить тред" hint and the message is **NOT delivered**. Never falls back to most-recent thread (that would violate SC-2's anti-misroute requirement).
- **Plain (non-Reply) staff message in the staff chat:** **ignored** (no thread anchor exists) with a **one-time hint** to use Telegram's native Reply on a forwarded message.

### Claude's Discretion
- Exact wording of the staff-facing DM template and hint messages (Russian; concise).
- ARQ task module placement (`app/workers/tasks/`) and retry constants, following the `dispatch_email.py` pattern.
- python-telegram-bot handler type/registration for catching staff replies (likely a `MessageHandler` filtered to `STAFF_TELEGRAM_CHAT_ID` + `REPLY`), and the `_book_callback_adapter`-style wiring in `telegram_bot.py:main()`.
- Whether photo forwarding re-reads bytes via `storage.open_stream` or a dedicated helper.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/modules/messaging/service.py` — `record_staff_message(session, ..., telegram_user_id, telegram_username)` already exists (Phase 90 Plan 02), exercised by tests, designed for exactly this bridge. Also `send_client_message` (the post-commit forward enqueue hook) and the WS publish path.
- `app/workers/telegram_bot.py` — PTB-based bot with `HandlerContext` (NamedTuple, append-only fields), `CommandHandler`/`CallbackQueryHandler` registration in `main()`, and a `_book_callback_adapter` wiring precedent (Phase 40).
- `app/integrations/telegram/handlers.py` — `HandlerContext` definition (extend by appending `messaging_service`); `sender` module for outbound Telegram calls.
- `app/workers/tasks/dispatch_email.py` — ARQ task + enqueue precedent (`_max_tries=2, _expires=20`); template for the forward task.
- `app/core/config.py` — `owner_alert_telegram_chat_id: int | None` precedent for adding `staff_telegram_chat_id`.
- Existing Redis `update_id` dedup in the `/checkin` handler — reuse for update dedup.
- `app/integrations/storage` adapter (`open_stream`) — source of photo bytes for `send_photo`.

### Established Patterns
- DB-first then Redis/side-effect (P5); caller-owns-transaction; session-per-operation in workers via `session_factory`.
- ARQ for out-of-band side-effects; structured logging (structlog); audit via `app.core.audit.emit` with `LOCKED_AUDIT_EVENTS`.
- Settings sentinel pattern: feature disabled + logged when the chat-id/token is the placeholder/None.

### Integration Points
- `messaging.service.send_client_message` (post-commit) → enqueue forward ARQ task.
- New ARQ task → `sender.send_message` / `send_photo` to `STAFF_TELEGRAM_CHAT_ID`; write `chat_forwarding_log` Redis mapping.
- `telegram_bot.py:main()` → register staff-reply `MessageHandler`; `HandlerContext` += `messaging_service`.
- Staff-reply handler → look up `chat_forwarding_log` → `record_staff_message` → WS publish + reply-as-read.
</code_context>

<specifics>
## Specific Ideas

- Staff DM identity = full name + phone (deliberate PII choice for single-gym operator recognition).
- Photos forwarded as real inline images (`send_photo`), bytes from stored S3 object.
- Stale/missing reply mapping → notify staff + drop, never misroute.
- Non-Reply staff messages → ignore + one-time "use Reply" hint.
</specifics>

<deferred>
## Deferred Ideas

- admin-web chat inbox + staff identity/auth → v2.6 (ADMIN-01/02).
- Web-push to client when PWA is closed → deferred (WS covers foreground; Telegram covers staff side).
- Multiple distinct staff identities / per-staff routing → v2.6 (v2.5 staff chat is a single `STAFF_TELEGRAM_CHAT_ID`, group or DM).
</deferred>
