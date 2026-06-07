# Phase 91: Read Receipts + Typing Indicators - Context

**Gathered:** 2026-06-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 91 extends the Phase 90 WebSocket protocol with two new event types delivered over the
existing `cc:messaging:client:{client_id}` Redis pub/sub channel — **read receipts** and **typing
indicators** — plus the service-layer **reply-as-read** semantics. No new database tables and no
migrations: the `messages.read_at` column already exists (migration 0065). Typing is ephemeral
(Redis pub/sub only, never persisted).

Covers requirements RCPT-01 (client sees ✓/✓✓ status of their own messages), RCPT-02 (client sees
"печатает…" from the gym side), RCPT-03 (staff reply marks prior client messages read + WS
read-receipt event).

**In scope:** reply-as-read in `record_staff_message`, thread-level read_receipt WS event,
staff→client typing WS event + `publish_typing()` service fn, extended WS event union, extended
Starlette WS test suite.

**Out of scope:** the actual Telegram-reply / `sendChatAction` triggers (Phase 93 wires them — P91
provides the service seam), client→staff typing relay (deferred — asyncio bridge-loop complexity,
P2 per research), PWA consumption of these events (Phase 94).

**Two distinct read concepts (do not conflate):**
- **Client reads STAFF messages** → `mark_thread_read` sets `read_at` on `role='staff'` rows and
  resets `client_unread_count` (Phase 90, MSG-04 — already done).
- **Staff reads CLIENT messages** (reply-as-read) → sets `read_at` on `role='client'` rows, drives
  the client's ✓✓ display (RCPT-01/03 — NEW in Phase 91).

</domain>

<decisions>
## Implementation Decisions

### Read Receipt Semantics (RCPT-01, RCPT-03)
- A client message becomes "read" via **reply-as-read**: `record_staff_message` sets `read_at=now()`
  on all prior unread `role='client'` messages in the thread before/at recording the staff reply.
- Read-receipt WS event is **thread-level**: `{type:"read_receipt", readAt}`. The client marks all
  its sent messages with `sent_at ≤ readAt` as ✓✓. (Lighter than a per-message id list.)
- REST exposure reuses the existing `MessageItem.readAt` field (present since Phase 90): ✓ =
  persisted/delivered, ✓✓ = `readAt` set.
- Phase 91 implements **service-layer reply-as-read only**, exercised in tests via
  `record_staff_message`. The actual Telegram-reply trigger is wired in Phase 93.

### Typing Indicator (RCPT-02, ephemeral)
- Transport is Redis pub/sub publish only — **never** persisted to DB (typing is ephemeral, P4).
- Auto-dismiss is **client-side** (~5s); the server only publishes the event (no server-side timer/TTL key).
- Phase 91 implements the **staff→client receive path** plus a `publish_typing(client_id)` service
  function; the staff-side trigger (Telegram `sendChatAction` detection) is wired in Phase 93.
- Typing event shape is minimal: `{type:"typing", actor:"staff"}` — no message content/preview.

### WS Protocol & Audit
- **No** new inbound client→server WS frames in Phase 91 — the WS stays receive-only for the client;
  read state still changes via the existing `PATCH /client/messages/read`.
- Reuse the existing `cc:messaging:client:{client_id}` channel; only add new event types to the
  discriminated union (P90 already anticipated `read_receipt` / `typing` placeholders).
- Emit the pre-registered `message_read` audit event when reply-as-read marks client messages.
  Typing is **not** audited (ephemeral — would be noise).
- Extend the WS event discriminated union with `read_receipt` and `typing` variants.

### Scope Boundary
- **Zero** Alembic migrations — `read_at` already exists (0065); typing ephemeral.
- Client→staff typing relay is **deferred** (asyncio bridge-loop complexity; revisit P93/later).
- Keep `mark_thread_read` (client-reads-staff) and reply-as-read (staff-reads-client) as distinct
  paths; document the role split in code.
- Tests: extend the Starlette `TestClient.websocket_connect()` suite with read_receipt + typing
  fan-out + IDOR isolation (client A never receives client B's receipt/typing), plus a service-level
  reply-as-read test.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/modules/messaging/schemas.py` — `NewMessageEvent` uses a `Literal` discriminator; comments
  already anticipate `message_read_receipt` / `typing_indicator` event types extending the union.
  `MessageItem.read_at` (camelCase `readAt`) already serialized.
- `app/modules/messaging/service.py` — `record_staff_message` exists (currently sets `read_at=None`,
  no reply-as-read yet); `publish_new_message` post-commit publish helper (from the P90 review fix);
  `mark_thread_read` (client-reads-staff path).
- `app/modules/messaging/ws.py` — receive loop has explicit placeholder comments for typing/read
  receipts ("Future phases may process … typing indicators here"); per-connection pubsub already set up.
- `app/modules/messaging/repository.py` — raw-SQL update patterns for `read_at`; `mark_thread_read`
  targets `role='staff'` rows — the new reply-as-read targets `role='client'` rows.

### Established Patterns
- DB-first + post-commit publish (P90 review fix CR-02): any new WS event triggered by a DB change
  must publish AFTER `session.commit()` via a post-commit helper, never inside the service body.
- All schemas inherit `BackendSchemaBase` (camelCase wire). WS frames are minimal/id-or-marker only.
- WS tests use Starlette `TestClient.websocket_connect()` — NOT httpx ASGITransport (P6/P13).

### Integration Points
- `cc:messaging:client:{client_id}` channel (P90) — add `read_receipt` + `typing` event types.
- `LOCKED_AUDIT_EVENTS` — `message_read` already pre-registered (P90); reuse for reply-as-read.
- No `.importlinter` change (already added `app.modules.messaging` in P90).

</code_context>

<specifics>
## Specific Ideas

- Reply-as-read repository fn: `UPDATE messages SET read_at=now() WHERE thread_id=:tid AND
  role='client' AND read_at IS NULL` (mirror of the existing staff-targeting mark_thread_read, but
  role='client'); RETURNING the max `sent_at` to drive the thread-level `readAt` in the WS event.
- `publish_typing(client_id, redis)` publishes `{type:"typing", actor:"staff"}` to the principal
  channel — no DB, no commit dependency (ephemeral).
- The read_receipt event is published post-commit (it reflects a committed DB change to read_at),
  consistent with the DB-first discipline.

</specifics>

<deferred>
## Deferred Ideas

- Telegram `sendChatAction` → typing trigger + Telegram-reply → reply-as-read trigger — Phase 93 (bridge).
- Client→staff typing relay (PWA typing → Telegram) — deferred (asyncio bridge-loop complexity, P2).
- PWA display of ✓/✓✓ and "печатает…" indicator — Phase 94 (PWA wiring).
- Per-message (vs thread-level) read receipts — not needed; thread-level marker suffices.

</deferred>
