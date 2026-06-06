# Feature Research

**Domain:** 1:1 Customer↔Business Chat — live messaging between a gym client (PWA) and gym staff (Telegram bridge)
**Researched:** 2026-06-06
**Confidence:** HIGH — based on codebase inspection of ChatScreen, NotificationsSheet, UIContext, flows.jsx (ChatAttachSheet), clientQueries.ts, telegram_bot.py worker, PROJECT.md v2.5 section, and verified against FastAPI WebSocket docs, python-telegram-bot v22 docs, and industry chat UX standards.

---

## Context

v2.5 adds a live 1:1 chat channel on top of an existing gym CRM PWA. Key prior art inside the codebase:

- **ChatScreen** (`apps/client-pwa/src/screens/ChatScreen.jsx`) — currently a `<ComingSoon>` shell per D-71-08. Props already wired: `initialConv`, `onClearInitial`, `onThreadOpen`. `ui.pendingChat` / `ui.chatThreadOpen` state already lives in `UIContext.jsx`.
- **ChatAttachSheet** (`flows.jsx:1167`) — a four-option bottom sheet (Фото/Камера/Файл/Голосовое) already mocked. Only Фото+Камера are in v2.5 scope; Файл and Голосовое are explicit out-of-scope.
- **NotificationsSheet** — the existing system-notification inbox: paginated REST, `unreadCount`, mark-read/mark-all patterns, optimistic updates, pull-to-refresh. The chat inbox must NOT duplicate this — they serve distinct purposes (system events vs human conversation).
- **Telegram bot worker** (`app/workers/telegram_bot.py`) — already live: long-polling python-telegram-bot v22, DB + Redis pools shared with API process, handler registration pattern established via `HandlerContext`. This is the reuse point for the staff-side bridge.
- **`websockets` package already in uv.lock** — FastAPI ships websockets as a transitive dependency; no new package needed.
- **`require_client()` principal** — all client-facing routes use the `ClientPrincipal` (aud="client") stack from v2.0, distinct from the frozen staff contract. WebSocket auth must extend this, not touch the staff auth.

The milestone explicitly distinguishes the chat domain from the notification inbox:
- Notification inbox = system events (bookings confirmed, payments, autopay failures) — already built in v2.4.
- Chat = human messages between client and gym staff — v2.5.
- System messages must NOT appear in the chat thread. This is a hard product constraint.

---

## Feature Landscape

### Category A: Messaging Core

Features without which the ChatScreen is unusable.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Send a text message | Base capability — without this there is no chat | LOW | `POST /api/v1/client/messages` body `{text: string}`. Message persisted to `messages` table with `sender='client'`, `created_at`, `id` (UUID). Returns `MessageItem`. Scoped to the single 1:1 thread for the authenticated client (IDOR: `client_id` from `require_client()`, never from body). |
| Receive messages (history REST) | Client needs to see the conversation when opening the screen | LOW | `GET /api/v1/client/messages?before=<cursor>&limit=30`. Cursor-based pagination (before message UUID + limit, not page numbers) — allows infinite scroll upward and reconnect catch-up without duplicate rows. Returns `{items: MessageItem[], has_more: bool}`. Each `MessageItem`: `{id, sender: 'client'\|'staff', text: string \| null, attachment_url: string \| null, status: 'sent'\|'delivered'\|'read', created_at: ISO8601}`. |
| Message ordering — strict chronological | Users depend on correct order; a scrambled thread is a broken product | LOW | `ORDER BY created_at ASC, id ASC` in the DB query (id tiebreak for same-millisecond inserts). Client renders in ascending order. Never rely on insertion order alone (UUIDs don't sort chronologically). Store `created_at` as `TIMESTAMPTZ` (UTC). Display in Europe/Moscow for the user. |
| Unread counter (thread-level) | Tab badge and home-screen badge are expected in every messaging app; missing it feels like a bug | LOW | `GET /api/v1/client/messages` response envelope includes `unreadCount: int` (messages from `sender='staff'` where `read_at IS NULL` and `id > last_read_id` OR simpler: server computes count of unread staff messages). The ChatScreen tab in TabBar already has a badge slot — see the `CONVERSATIONS` mock badge referenced in App.jsx comment. |
| Mark thread as read | When the client opens the chat, the unread counter must clear | LOW | `PATCH /api/v1/client/messages/read` — marks all staff messages as read (sets `read_at = now()` on all unread staff-sent messages for this client). Returns 204. Called when the ChatScreen becomes visible (not just app-open). Mirror the NotificationsSheet pattern: optimistic update locally, mutate, rollback on error. |
| Unread badge on Chat tab | Standard PWA navigation expectation — a red dot or count on the tab | LOW | Same pattern as the Home screen's bell badge (NotificationsSheet, INBOX-05): poll `unreadCount` on a short interval (30s via React Query `refetchInterval`) OR push via WS event. The badge is the number of unread staff messages. If WS is connected, badge updates in real time via WS event; if not, REST poll fallback. |

### Category B: Real-Time Delivery (WebSocket)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Real-time message push (client receives staff reply without refresh) | Users expect chat to "just update" — having to pull-to-refresh to see a new message is a broken chat UX | MEDIUM | FastAPI `@router.websocket("/api/v1/client/ws")` endpoint. Auth: `Cookie` dependency reads the `cc_client_*` httpOnly access cookie set during login — cookies are sent automatically on the WS upgrade request, same origin. Validate the JWT before `websocket.accept()`. On validation failure: `await websocket.close(code=4001)`. No short-lived WS token needed — httpOnly cookie is the cleanest pattern for same-origin PWA (confirmed: browser sends httpOnly cookies on WS upgrade; custom `Authorization` headers are NOT sent by the browser WS API). |
| Redis pub/sub fan-out | Staff sends a message via Telegram → bot publishes to Redis channel → FastAPI WS subscribers receive it | MEDIUM | Each connected client subscribes to a Redis channel `cc:chat:{client_id}`. When the Telegram bridge receives a staff reply, it calls `redis.publish(f"cc:chat:{client_id}", json.dumps(event))`. The FastAPI WS handler has a listener loop on that channel. Redis 7 (already in stack) supports this natively via `aioredis` / `redis-py asyncio`. No additional infrastructure needed. |
| Reconnect with exponential backoff | PWA clients lose connectivity on mobile (subway, elevator). Chat must recover without user action | MEDIUM | Client-side: `useWebSocket` hook wraps the native `WebSocket` with reconnect logic: initial delay 1s, max delay 30s, jitter ±20%, max attempts before giving up and showing a "переподключение…" badge. On reconnect, the hook re-establishes auth (cookie is still valid) and fetches missed messages via REST (`GET /api/v1/client/messages?before=<last_seen_id>`). |
| Missed message catch-up on reconnect | Messages sent while disconnected must appear in order on reconnect | LOW | On WS reconnect, the client sends a `{type: "sync", last_seen_id: "uuid"}` message. The server responds with all messages after that ID. Alternatively (simpler): on WS connect, client issues a REST `GET /api/v1/client/messages?after=<last_seen_id>` — REST is more reliable than a WS sync message pattern for catch-up. Use REST catch-up, not a custom WS sync protocol. |
| WS connection state indicator | Users in areas with poor signal need to know if the "live" channel is active | LOW | The PWA shows a subtle indicator: "В сети" (green dot) vs "Не в сети" (grey dot, REST fallback active). Not a prominent error — a quiet status. If the WS has been disconnected for >60s and reconnect failed, show a `LoadError`-style inline notice with a "Обновить" button that triggers manual REST fetch. |

### Category C: Read Receipts and Typing Indicator

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| "Delivered" status (message reached server) | Standard in every chat app since iMessage popularized the pattern (2011). Missing it feels like a toy | LOW | "Delivered" = server persisted the message. The `POST /api/v1/client/messages` response returning 200 with the saved `MessageItem` is itself proof of delivery. The client renders a single checkmark (✓) immediately on 200. No separate delivery event needed. If the request fails (network error), the message stays in a "sending" state with a retry button. |
| "Read" status (staff has seen the message in Telegram) | Expected by anyone who has used WhatsApp or iMessage. Without it, users cannot tell if their message was noticed | MEDIUM | When the Telegram bridge delivers a client message to the staff Telegram chat AND the staff views it (Telegram `read_at` is a property of the Telegram message, but Telegram does NOT expose per-message read receipts to bots). **Practical implementation:** "Read" is set when the STAFF REPLIES. When the bot receives a reply from the staff and stores it, it marks all prior client messages for that client as `read_at = now()`. Then publishes a `{type: "read_receipt", client_message_ids: [...]}` event to `cc:chat:{client_id}`. Client renders double checkmark (✓✓) on those messages. This is the WhatsApp pattern: read = recipient replied, not "opened". Simpler, avoids needing Telegram read events (which the bot API doesn't expose). |
| Typing indicator ("Администратор печатает...") | Users expect this when a staff member is composing a reply | MEDIUM | Staff side: the Telegram bot detects `ChatAction.TYPING` from the staff. This is a Telegram API `sendChatAction` event emitted when staff is composing. The bot subscribes to typing updates on the gym's staff Telegram chat. When detected, publishes `{type: "typing", is_typing: true}` to `cc:chat:{client_id}` Redis channel. Expiry: 5-second TTL — if no new typing event within 5s, client auto-dismisses the indicator. This avoids needing an explicit "stop typing" event. The Telegram `sendChatAction` is fired every ~5s while the user types, so the pattern naturally refreshes. |
| Client typing indicator (to staff side) | Staff might want to know the client is composing before sending — reduces "did they read my message?" uncertainty | LOW | Client sends `{type: "typing", is_typing: bool}` via WS when the input field transitions empty→non-empty (start) or non-empty→empty (stop) or after 3s idle debounce (stop). Server relays by publishing `{type: "client_typing"}` to a `cc:chat:staff:{client_id}` Redis channel. The Telegram bridge subscribes and sends `sendChatAction(chat_id, ChatAction.TYPING)` to the staff Telegram chat. **Complexity driver:** The bot worker must subscribe to a separate Redis channel while also handling long-polling — this requires either `asyncio.gather` or `select` pattern inside the bot event loop. |
| "New messages" divider on reconnect | Industry standard (WhatsApp, iMessage): a divider line at the point in history where new messages start | LOW | Client-side only. On reconnect, record the `last_seen_message_id`. Any message with `id > last_seen_id` renders below a "Новые сообщения" divider row. Dismiss the divider on scroll-to-bottom or after 3s. |

**Read receipt implementation decision:** Using reply-as-read is preferred over trying to get Telegram read signals (which are not available to bots). It is accurate enough for single-gym customer support context: if staff replied, they clearly read the message. This is the approach used by most Telegram-bridged customer support tools.

### Category D: Photo Attachments

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Send a photo from the gallery | "Send a photo" is the most common non-text chat action in customer support (show injury, show membership card, show payment receipt). The ChatAttachSheet already has "Фото — Из галереи" as the first option | HIGH | Client: `<input type="file" accept="image/*">` triggered by the ChatAttachSheet "Фото" button. PWA does `multipart/form-data POST /api/v1/client/messages/upload` with the image file. Server: validate MIME type (allowlist: `image/jpeg`, `image/png`, `image/webp`, `image/gif`), enforce size cap (5 MB), store file, return `{attachment_url: string}`. Client then calls `POST /api/v1/client/messages` with `{attachment_url}` (not `text`). Alternatively: single endpoint that accepts both text and file. |
| Take a photo from camera | The ChatAttachSheet "Камера — Сделать снимок" option | LOW | Same flow as gallery, but the `<input>` uses `capture="environment"` attribute. No new backend surface — same upload endpoint. |
| Image thumbnail in the chat bubble | Standard: show a small preview in the message list; tapping opens full-size | MEDIUM | Server stores the original image and generates a thumbnail (or the PWA generates one client-side before upload using Canvas API). Options: (A) server-side thumbnail generation via `Pillow` (already a common Python dep, or add it); (B) client-side canvas resize to 300px width before upload; (C) serve original and use CSS `object-fit: contain` with `max-height: 200px`. Option C is simplest for MVP — no Pillow needed. If images are stored on the filesystem or an object store, serve via a dedicated `GET /api/v1/client/messages/media/{filename}` endpoint with `require_client()` access control (no unauthenticated access to images). |
| Photo access control (no unauthenticated URLs) | Gym photos may contain sensitive content (injury documentation, payment receipts). Public CDN URLs are an IDOR risk | HIGH | The file serving endpoint must be behind `require_client()` and must verify that the requesting client owns the conversation containing the attachment. No permanent public CDN URL. The `attachment_url` stored in the DB is a relative path (`/api/v1/client/messages/media/{filename}`) — the PWA sends the cookie on every fetch, just like REST API calls. |
| Content-type guard (XSS prevention) | Uploading a disguised `.html` file as `image/jpeg` is a stored-XSS vector | HIGH | Server-side MIME sniff: use `python-magic` or Pillow's `Image.verify()` to confirm the file is actually an image, not just checking the `Content-Type` header (which is client-controlled). Set `Content-Type: image/jpeg` (etc.) explicitly on the served response, add `X-Content-Type-Options: nosniff`, and `Content-Disposition: inline` (not attachment). This follows the `photo_url` validator precedent established in Phase 88 (TrainerDetailSheet). |
| File size cap | Without a server-side cap, large photos will cause memory pressure or slow uploads | LOW | 5 MB per attachment. Return 413 with `{code: "attachment_too_large", message: "Максимальный размер файла — 5 МБ"}` if exceeded. Enforce at the FastAPI level (`UploadFile` + content-length check before reading into memory). |
| Storage — local filesystem vs object store | Single-gym pet project at low volume does not need S3/Minio | MEDIUM | Local filesystem is sufficient for v2.5 at single-gym scale. Store under a configurable `MEDIA_ROOT` path (env var). Use UUID-based filenames (`{message_id}_{suffix}.jpg`) to prevent enumeration. Path traversal prevention: validate filename before writing (strip `/`, `..`). Note this decision as a future-migration item if the project scales. |

**Out-of-scope attachments (ChatAttachSheet has these but v2.5 excludes them):**
- "Файл — PDF, doc, до 10 МБ": file types other than images are out of scope per PROJECT.md.
- "Голосовое — Удерживай для записи": voice messages are out of scope.

### Category E: Telegram Bridge (Staff Channel)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Forward client message to staff Telegram | The primary business value of the bridge — staff must see the message | MEDIUM | When `POST /api/v1/client/messages` is called by the client, the messaging service publishes a `cc:chat:new_client_msg:{client_id}` event to Redis. The bot worker subscribes to this channel. On receiving the event, the bot sends a Telegram message to the configured staff chat ID (`TELEGRAM_STAFF_CHAT_ID` env var — a group chat or individual admin's chat). Format: `"[Имя Клиента] написал(а):\n{text}"`. If there's a photo attachment, the bot sends `sendPhoto`. |
| Staff replies via Telegram → stored in DB + pushed to client | Core bridge behavior — staff just uses Telegram normally to reply | MEDIUM | The existing bot long-polling handler adds a new `MessageHandler` that listens to text messages in the staff chat. When a message arrives from a staff user in the staff chat (not a command, plain text or photo): parse the `client_id` from the thread context (stored in a Redis key `cc:chat:telegram_thread:{telegram_message_id}` → `client_id`), create a DB row in `messages` with `sender='staff'`, publish `{type: "new_message", ...}` to `cc:chat:{client_id}`. The WS fan-out then delivers it to the connected PWA. |
| Thread context — linking Telegram messages to client IDs | The bot must know which client a Telegram reply is intended for | MEDIUM | Store the mapping: when the bot forwards a client message to Telegram, Redis stores `cc:chat:telegram_thread:{telegram_message_id} → {client_id, client_name}` with TTL 7 days. Staff replies by replying to that forwarded message in Telegram (using Telegram's "Reply" feature). The incoming `Update.message.reply_to_message.message_id` is used as the lookup key. If staff writes a new (non-reply) message in the staff chat, it is ignored (or treated as a broadcast, which is out of scope). This is the standard Telegram customer-support bridge pattern. |
| Staff photo attachments via Telegram → PWA | Staff may want to send images too (exercise demonstrations, schedule photos) | MEDIUM | When the bot receives a `Photo` message (not text) from staff, download the photo via `Bot.get_file()`, store it to `MEDIA_ROOT` using the same UUID-filename convention, insert a DB message row with `sender='staff'`, `attachment_url` pointing to the file. Then publish the WS event. This reuses the same photo storage infrastructure as client-side uploads. |
| Client name shown in forwarded Telegram message | Staff needs to know who is writing | LOW | Include `{client.full_name} (id: {client_id[:8]})` in the forwarded message header. The messaging service fetches the client name at message-creation time via a raw-SQL read (following D-20-MODULE discipline — no cross-module service import; read client name directly via `SELECT full_name FROM clients WHERE id = :client_id`). |
| Notification to staff (unread indicator) | If staff is not watching the Telegram chat, they need a nudge | LOW | The Telegram forward itself is the notification — Telegram's own notification system alerts the staff chat. No additional push mechanism needed. If the staff chat uses a notification group (no sound), this is an operator configuration concern, not a code concern. |

### Category F: PWA Screen Wiring

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Graduate ChatScreen from ComingSoon | Without this, the entire milestone has no user-visible surface | LOW | Follow the exact graduation pattern from v2.4 (GymInfoSheet Phase 86, NotificationsSheet Phase 87, TrainerDetailSheet Phase 88): de-list from D-71-09 ESLint placeholder zone (3 spots), import data hooks via `@/data` swap seam. The `initialConv`, `onClearInitial`, `onThreadOpen` props are already in `ChatRoute` and `UIContext` — they just need real implementations. |
| Message list with send input | The core chat UI: scrollable message list + text input + send button | MEDIUM | Render ascending chronological list of message bubbles: client messages right-aligned, staff messages left-aligned. Each bubble shows text or photo thumbnail. Show `created_at` time (HH:MM format, Europe/Moscow). Infinite scroll upward (load older messages on scroll-to-top using cursor pagination). Input: `<textarea>` with auto-expand, send on Enter or tap ✈ button, disabled while sending. |
| Send button state (sending / error / sent) | Users need feedback that their message was accepted or failed | LOW | Three states: (1) "sending" — spinner in bubble, no timestamp; (2) "sent" (server 200) — single ✓, show timestamp; (3) "error" — bubble shows red border + "Retry" tap target. Retry = re-send same payload. Maintain a local "pending" queue (array of unsent messages) that clears on 200. |
| Photo picker integration | The ChatAttachSheet is already built but not wired | LOW | The `onOpenChat → __openChatAttach()` flow already exists in `UIContext`. Wire the "Фото" and "Камера" options to `<input type="file">` with the respective `accept` and `capture` attributes. On file selected: show upload progress in the input area, call upload endpoint, then send message with the returned URL. On error: show "Не удалось загрузить фото" inline. |
| Photo preview in message bubble | Tapping a photo in the thread should show it full-size | LOW | Tap on thumbnail → full-screen image viewer. PWA-native pattern: a fullscreen `<div>` overlay with `<img>` at natural size, close on tap or swipe-down. No library needed — match the visual style of the rest of the app. Preload the full image on tap (the thumbnail is already loaded). |
| WS connection in ChatScreen | The real-time layer | MEDIUM | A `useChat` hook: (1) opens a `WebSocket` to `/api/v1/client/ws` on ChatScreen mount (or even on app mount if the chat badge needs real-time updates), (2) handles the reconnect loop with exponential backoff, (3) dispatches incoming events (`new_message`, `typing`, `read_receipt`) to local state, (4) tears down cleanly on unmount / logout. The WS is separate from the React Query poll — REST poll is the fallback when WS is disconnected. |
| Tab badge for unread messages | App-level indicator that new messages arrived | LOW | The Tab Bar's chat tab shows a badge count. The count comes from `unreadCount` in `GET /api/v1/client/messages` (polled every 30s via React Query). When WS is connected, the count is updated in real-time from WS `new_message` events. On WS disconnect, the polling fallback takes over. This is the same bell badge pattern used by Home screen + NotificationsSheet. |
| Remove ChatAttachSheet dead options (Файл, Голосовое) | The existing ChatAttachSheet shows 4 options; only 2 are in scope | LOW | Either: (A) modify the ChatAttachSheet to render only Фото and Камера options; (B) disable/grey-out Файл and Голосовое with a "Скоро" label. Option A is cleaner — remove dead code from the shipped product. No user expects to be shown options that don't work. |

---

## Feature Dependencies

```
New DB module: app/modules/messaging/
  ├── messages table (Alembic migration)
  │   ├── id UUID PK
  │   ├── client_id FK → clients.id (IDOR boundary)
  │   ├── sender ENUM('client', 'staff')
  │   ├── text TEXT nullable
  │   ├── attachment_url TEXT nullable
  │   ├── status ENUM('sent', 'delivered', 'read') default 'sent'
  │   ├── read_at TIMESTAMPTZ nullable
  │   └── created_at TIMESTAMPTZ default now()
  │
  ├── GET /api/v1/client/messages → cursor-based list + unreadCount
  │     └── requires── messages table
  │     └── called by── ChatScreen load + React Query polling
  │
  ├── POST /api/v1/client/messages → create text or attachment message
  │     └── requires── messages table
  │     └── requires── file already uploaded (if attachment)
  │     └── triggers── Redis publish cc:chat:new_client_msg:{client_id}
  │
  ├── POST /api/v1/client/messages/upload → multipart upload, returns attachment_url
  │     └── requires── MEDIA_ROOT filesystem path
  │     └── requires── python-magic or Pillow for MIME validation
  │     └── precedes── POST /api/v1/client/messages (client sends URL, not file)
  │
  ├── GET /api/v1/client/messages/media/{filename} → serve stored file, authed
  │     └── requires── require_client() + ownership check
  │     └── requires── file stored by upload endpoint
  │
  ├── PATCH /api/v1/client/messages/read → mark all staff messages read
  │     └── requires── messages table
  │     └── triggers── publishes read_receipt event to cc:chat:{client_id}
  │
  └── WS /api/v1/client/ws → real-time channel
        └── requires── Redis 7 pub/sub (already in stack)
        └── requires── ClientPrincipal auth via httpOnly cookie (already in stack)
        └── subscribes to── cc:chat:{client_id} Redis channel
        └── pushes── new_message, typing, read_receipt events to PWA

Telegram bridge extension (in app/workers/telegram_bot.py)
  ├── NEW: subscribe to cc:chat:new_client_msg:{client_id} Redis channels
  │     └── requires── asyncio subscription alongside existing long-poll loop
  │     └── forwards── client message to staff Telegram chat (sendMessage/sendPhoto)
  │     └── stores── cc:chat:telegram_thread:{telegram_msg_id} → client_id (Redis TTL 7d)
  │
  ├── NEW: MessageHandler for plain staff text/photo replies
  │     └── triggers── lookup client_id from reply_to_message.message_id
  │     └── inserts── messages row with sender='staff'
  │     └── publishes── new_message event to cc:chat:{client_id}
  │     └── triggers── mark prior client messages as 'read' (reply-as-read receipt)
  │
  └── NEW: ChatAction.TYPING detection → publish typing event to cc:chat:{client_id}

PWA ChatScreen (apps/client-pwa/src/screens/ChatScreen.jsx)
  ├── requires── de-listing from D-71-09 ESLint placeholder zone
  ├── requires── GET /api/v1/client/messages (history REST)
  ├── requires── POST /api/v1/client/messages (send)
  ├── requires── POST /api/v1/client/messages/upload (photo)
  ├── requires── PATCH /api/v1/client/messages/read (mark read on open)
  ├── requires── WS /api/v1/client/ws (real-time push)
  └── uses── existing ChatAttachSheet (flows.jsx, already wired via __openChatAttach)
```

### Dependency Notes

- **WebSocket auth depends on existing ClientPrincipal cookie infrastructure:** The `cc_client_*` httpOnly cookies set at login are sent automatically on WS upgrade. The same `require_client()` dependency logic applies — just adapted for WS (`Cookie` param instead of `Header`). No new auth infrastructure.
- **Telegram bridge depends on a working Redis pub/sub loop alongside long-polling:** The existing bot worker runs an event loop for long-polling. Adding a Redis subscriber requires either a separate asyncio task (via `asyncio.create_task`) or restructuring the main loop to `asyncio.gather([long_poll_task, redis_subscriber_task])`. This is the highest architectural risk in the Telegram bridge.
- **File upload must complete before message send:** The `POST /api/v1/client/messages/upload` → receive URL → `POST /api/v1/client/messages` {attachment_url} is a two-step sequence. If the upload succeeds but the message POST fails, the file is orphaned on disk. MVP accepts this as a minor leakage (low frequency, no sensitive data risk for image files). Cleanup cron is a v2.6 concern.
- **Read receipts depend on Telegram reply-chaining:** The `reply_to_message.message_id` lookup is only available if the staff REPLIES (using Telegram's reply feature) rather than sending a new message. If staff sends a free-standing message in the chat, the bot cannot identify the target client. The operator must be told: always use Telegram reply to respond to client messages.
- **`clientPortalKeys.messages` must be added to `clientQueries.ts`** to maintain the existing key factory pattern.

---

## MVP Definition

### v2.5 Ships With

- [ ] `messages` table (Alembic migration) + `app/modules/messaging/`
- [ ] `GET /api/v1/client/messages` — cursor list + unreadCount
- [ ] `POST /api/v1/client/messages` — send text message
- [ ] `POST /api/v1/client/messages/upload` — photo upload (JPEG/PNG/WebP/GIF, 5 MB cap, MIME validated)
- [ ] `GET /api/v1/client/messages/media/{filename}` — authenticated file serving
- [ ] `PATCH /api/v1/client/messages/read` — mark all read
- [ ] `WS /api/v1/client/ws` — real-time channel with httpOnly cookie auth + Redis pub/sub
- [ ] WS events: `new_message`, `typing` (staff→client), `read_receipt`
- [ ] Telegram bridge: forward client message to staff chat, handle staff reply, store in DB, fan-out via WS
- [ ] Telegram typing detection → relay to PWA
- [ ] ChatScreen wired (de-listed from D-71-09, real API + WS)
- [ ] Message list UI: bubbles, timestamps, photo thumbnails, full-screen viewer
- [ ] Send input: text + photo picker, sending/sent/error states
- [ ] Read receipt display: single ✓ (sent), double ✓✓ (read = staff replied)
- [ ] Typing indicator display ("Администратор печатает…")
- [ ] Reconnect with exponential backoff + REST catch-up
- [ ] Tab badge for unread messages (React Query poll + WS real-time)
- [ ] ChatAttachSheet: Фото + Камера only (remove/disable Файл + Голосовое)
- [ ] OpenAPI handoff: byte-stable regen + `_v25Checks` AssertNonNever + staff drift gate green

### Defer to v2.6+

- [ ] **Client-side typing → staff Telegram**: the asyncio complexity of bidirectional bridge events is deprioritized if it introduces instability. Ship staff→client typing first; add client→staff typing if the bridge loop design allows it cleanly.
- [ ] **Message edit / delete**: no current UI for it; moderate complexity; out of scope.
- [ ] **Message search**: not in mock; out of scope.
- [ ] **Admin-web chat inbox**: frozen; v2.6 milestone.
- [ ] **File attachments (non-photo)**: out of scope per PROJECT.md.
- [ ] **Voice messages**: out of scope per PROJECT.md.
- [ ] **Push notifications for new chat messages**: `client_push_tokens` table exists (v2.4 INBOX-04 storage-only). Real web-push for chat messages = v2.6.
- [ ] **Orphaned file cleanup cron**: low priority at single-gym scale.
- [ ] **Object store migration** (S3/MinIO): local filesystem is correct at single-gym scale.

---

## Anti-Features (Explicitly Out of Scope for Single-Gym Pet-Project Scale)

| Feature | Why Requested | Why It's Wrong Here | What to Do Instead |
|---------|---------------|---------------------|-------------------|
| System messages in the chat thread | "It would be nice to see booking confirmations in the chat" | Hard product constraint from PROJECT.md: system events (bookings, payments) MUST stay in the notification inbox. Mixing system events into the human chat thread creates a cluttered, confusing UX and means two different code paths writing to the same table. | Notification inbox covers system events. Human chat is human-only. Keep strict separation. |
| Group chats or broadcast | "I want to message all clients at once" | Group chat is a different domain (pub/sub to N recipients, permission model, moderation). Adding it here would turn a customer support feature into a broadcast channel. | Broadcast is a marketing feature. Out of scope for v2.5. Future: a separate "announcement" inbox type in v2.6+. |
| Per-message receipt (WhatsApp-style three ticks per message) | "I want to see exactly when each message was read" | Telegram bots have no access to per-message read timestamps from the staff side. Implementing client-side per-message read events (when PWA scrolls past each message) adds a high-frequency event stream that overwhelms the WS pub/sub for no real gain at 1 gym. | Thread-level read (reply-as-read) is accurate enough for a customer support context. |
| Typing indicator: debounce < 1s | "More real-time typing feel" | At <1s debounce, the client sends a typing event on every keystroke. One gym, one client — but still wastes WS bandwidth and Redis publish calls. The perception difference between 1s and 100ms debounce is imperceptible to users. | Debounce at 1–2s on client. Auto-expire at 5s on server. |
| WebSocket horizontal scaling (multi-instance) | "What if we run multiple backend processes?" | Single-gym pet project does not need horizontal scaling. The Redis pub/sub pattern already handles cross-process fanout IF multiple instances are ever needed. But over-engineering for HA clustering adds configuration complexity with zero benefit at 1 gym. | Redis pub/sub is the correct architecture for future scaling. No additional work needed now. |
| End-to-end encryption | "Messages should be encrypted so staff can't see them" | Staff IS the intended reader of messages — the entire feature is client→staff communication. E2E encryption is contradictory here. | Server-side TLS (HTTPS/WSS) is sufficient. |
| Offline message queue with at-least-once delivery | "What if the server is down when I send?" | This requires a local SQLite offline queue in the PWA, conflict resolution, and idempotent message creation. Overkill for a single-gym CRM that runs on a single VPS. | Clear error state with retry button on send failure. "В сети" / "Не в сети" indicator. That's sufficient. |
| Message reactions / emoji responses | "Fun to react to messages" | Adds a new DB table (reactions), new API endpoint, new WS event type, new UI components. Zero business value for customer support. | Not a chat feature — it's a social feature. |
| Read receipt privacy (disable receipts) | "I don't want staff to know when I read their messages" | The product is a gym CRM's customer support channel, not a peer social chat. Privacy settings for read receipts are appropriate for social networks, not support tools. | Skip the privacy toggle entirely. |
| Pinned messages / starred messages | Complexity with no discernible value at single-gym scale | — | Not implemented |
| Multi-device sync (client on web + mobile) | The PWA is the only client surface | Redis pub/sub naturally handles multiple WS connections for the same client_id (both would receive events). But there's no other client surface to sync with in v2.5. | WS fanout to all connections for the same client_id is free with the pub/sub design — no extra work needed. |

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Send/receive text message | HIGH | LOW | P1 |
| Unread counter + tab badge | HIGH | LOW | P1 |
| Mark as read on open | HIGH | LOW | P1 |
| WS real-time delivery | HIGH | MEDIUM | P1 |
| Reconnect + REST catch-up | HIGH | MEDIUM | P1 |
| Telegram bridge: forward client msg to staff | HIGH | MEDIUM | P1 |
| Telegram bridge: staff reply → DB + WS | HIGH | MEDIUM | P1 |
| Thread context (reply-to-message mapping) | HIGH | MEDIUM | P1 |
| Photo upload (gallery) | MEDIUM | HIGH | P1 |
| Photo thumbnail in bubble | MEDIUM | LOW | P1 |
| Content-type guard (XSS prevention) | HIGH (security) | MEDIUM | P1 |
| Authenticated file serving | HIGH (security) | LOW | P1 |
| Read receipt display (reply-as-read) | MEDIUM | LOW | P1 |
| Typing indicator (staff→client) | MEDIUM | MEDIUM | P1 |
| "Delivered" single checkmark on send | MEDIUM | LOW | P1 |
| Take photo with camera | LOW | LOW | P2 |
| Typing indicator (client→staff) | LOW | HIGH | P2 |
| Full-screen photo viewer | MEDIUM | LOW | P2 |
| WS connection state indicator | LOW | LOW | P2 |
| "New messages" divider on reconnect | LOW | LOW | P2 |
| Staff photo via Telegram → PWA | MEDIUM | MEDIUM | P2 |

---

## Implementation Notes: Behavior Specification

### Message Send/Delivery Lifecycle

1. User types text or selects photo, taps send.
2. Message appears in thread immediately with a spinner (optimistic local state). No DB row yet.
3. If photo: upload to `POST /client/messages/upload` first (progress indicator in input area). On upload success, proceed to step 4.
4. `POST /client/messages` — server inserts DB row, responds with `MessageItem` including server-assigned `id` and `created_at`.
5. Local optimistic row replaced with server-confirmed row. Single ✓ (sent) displayed.
6. Redis: server publishes `{type: "new_client_msg", message_id, client_id, text, attachment_url}` to `cc:chat:new_client_msg:{client_id}`.
7. Telegram bridge: bot picks up event, calls `send_message` / `send_photo` to staff chat. Stores `telegram_message_id → client_id` in Redis.
8. When staff REPLIES (Telegram reply to that message): bot stores `sender='staff'` row, marks prior client messages `read_at = now()`, publishes `{type: "new_message", ...}` + `{type: "read_receipt", message_ids: [...]}` to `cc:chat:{client_id}`.
9. WS delivers both events to PWA. Client message bubbles update to double ✓✓. Staff message appears in thread.

### Unread Count Behavior

- `unreadCount` = count of `messages WHERE client_id = ? AND sender = 'staff' AND read_at IS NULL`.
- Computed server-side. Returned in every `GET /api/v1/client/messages` response.
- On WS `new_message` event with `sender='staff'`: increment local unread count by 1.
- On `PATCH /api/v1/client/messages/read` (called when ChatScreen mounts or becomes visible): set local unread count to 0. The tab badge clears.
- On WS `read_receipt` event (triggered by staff reply): unread count is not affected (only client→staff read state is tracked in read receipts; staff messages are marked read when the CLIENT opens the chat).

### Typing Indicator Behavior

- **Staff→client**: Bot detects `Update.message.chat.send_action` typing event from staff. Publishes `{type: "typing", is_typing: true}` to Redis. PWA WS handler shows "Администратор печатает…" bubble. Auto-dismiss after 5s if no new typing event.
- **Client→staff**: Input field onChange: if transitioning from empty to non-empty, send `{type: "typing", is_typing: true}` via WS. If idle >2s or field cleared, send `{type: "typing", is_typing: false}`. Server relays to `cc:chat:staff:{client_id}`, bot sends Telegram `sendChatAction`.
- **Typing state is ephemeral — never stored in DB.**

### Reconnect Catch-Up Behavior

1. WS disconnects (network loss, app backgrounded).
2. Client saves `last_received_message_id` in component state.
3. Reconnect attempt: 1s → 2s → 4s → 8s → 16s → 30s (capped). Jitter ±20%.
4. On successful reconnect: client calls `GET /api/v1/client/messages?after={last_received_message_id}` (a "since" cursor, complement of the "before" history cursor). Server returns all messages created after that ID.
5. Messages merged into the local list (deduplication by `id`). "Новые сообщения" divider inserted before the first catch-up message.
6. If the WS has been down >5 minutes: show "Переподключение…" in the ChatScreen header. On reconnect: show a brief "Обновлено" toast.

---

## Existing Codebase Integration Points

| Existing Part | How v2.5 Connects |
|---------------|-------------------|
| `ChatScreen.jsx` — `ComingSoon` shell | Replace with real component. Props (`initialConv`, `onClearInitial`, `onThreadOpen`) already wired in `ChatRoute`. |
| `UIContext.jsx` — `chatThreadOpen`, `pendingChat`, `chatAttachOpen` | Already defined. `chatAttachOpen` opens the attachment picker. `chatThreadOpen` hides the TabBar. |
| `flows.jsx:ChatAttachSheet` | Already renders Фото/Камера/Файл/Голосовое. Remove Файл + Голосовое options. Wire Фото + Камера to `<input>` triggers. |
| `clientQueries.ts` — `clientPortalKeys` key factory | Add `messages` keys: `messages: (cursor?) => [...all, 'messages', cursor ?? ''] as const`. Add `sendMessage`, `uploadAttachment`, `markRead` hooks. |
| `data/index.js` swap seam | Export new hooks from `@/data` (same pattern as NotificationsSheet). |
| `App.jsx` TabBar chat tab | Already has a badge slot for unread count. Wire `unreadCount` from the messages query. |
| `TabBar.jsx` | Check for existing badge rendering — likely needs a `chatUnread` prop passed from `App.jsx`. |
| `app/workers/telegram_bot.py` | Extend `HandlerContext` with `messaging_service`. Add Redis subscriber loop + new message handler. |
| Redis 7 (already running) | Add pub/sub channels: `cc:chat:{client_id}`, `cc:chat:new_client_msg:{client_id}`, `cc:chat:staff:{client_id}`. |
| `app/modules/client_portal/` | Mount new messaging router under the existing client-portal module or as a sibling module. |
| `LOCKED_AUDIT_EVENTS` frozenset | Add: `message_sent_by_client`, `message_sent_by_staff`, `message_read`. Register before callsites (INFRA-15). |
| D-71-09 ESLint placeholder zone | De-list ChatScreen (3 spots). Follow the v2.4 lesson exactly. |

---

## Sources

- Codebase: `apps/client-pwa/src/screens/ChatScreen.jsx` — current ComingSoon shell + D-71-08 note
- Codebase: `apps/client-pwa/src/context/UIContext.jsx` — `chatThreadOpen`, `pendingChat`, `chatAttachOpen` state
- Codebase: `apps/client-pwa/src/App.jsx` — `ChatRoute`, `__openChatAttach`, `pendingChat` push-tap routing
- Codebase: `apps/client-pwa/src/screens/sheets/flows.jsx:1167` — `ChatAttachSheet` (4 options mock)
- Codebase: `apps/client-pwa/src/screens/sheets/NotificationsSheet.jsx` — reference for unread/mark-read/optimistic patterns
- Codebase: `apps/client-pwa/src/lib/clientQueries.ts` — key factory + query hook patterns
- Codebase: `apps/backend/app/workers/telegram_bot.py` — existing long-poll bot worker + `HandlerContext` pattern
- Codebase: `.planning/PROJECT.md` — v2.5 milestone scope, constraints, out-of-scope list
- FastAPI WebSocket docs — Cookie auth on WS upgrade: https://github.com/tiangolo/fastapi/blob/master/docs/en/docs/advanced/websockets.md
- Industry article — WS auth via httpOnly cookies (same-origin, no custom header needed): https://thecodeforge.io/python/fastapi-websockets/
- Industry article — FastAPI WS + Redis pub/sub + read receipts + typing: https://python.elitedev.in/python/build-real-time-chat-app-with-fastapi-websockets-redis-react-complete-tutorial-f1b42bf1/
- Industry standard — read receipt semantics (delivered vs read vs server ACK): https://trtc.io/blog/details/reliable-chat-sdk-architecture-prevent-message-loss-offline-push-read-receipts-and-message-history-issues
- Industry standard — typing indicator TTL, auto-expire behavior: https://vibe-studio.ai/insights/building-a-realtime-chat-ui-with-typing-indicators-and-read-receipts
- MUI X Chat docs — read events and unreadCount semantics: https://mui.com/x/react-chat/multi-conversation/read-receipts/
- python-telegram-bot v22 — `ReplyParameters`, message handler, ChatAction: https://docs.python-telegram-bot.org/en/stable/telegram.message.html

---

*Feature research for: v2.5 Chat / Messaging — 1:1 client↔gym live chat with Telegram staff bridge*
*Researched: 2026-06-06*
