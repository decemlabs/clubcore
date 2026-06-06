# Pitfalls Research

**Domain:** Adding WebSocket real-time chat + photo attachments + Telegram bridge to an existing FastAPI modular monolith (clubcore gym CRM, v2.5)
**Researched:** 2026-06-06
**Confidence:** HIGH (FastAPI docs + Redis docs + codebase analysis + established patterns from prior milestones)

---

## Critical Pitfalls

### Pitfall 1: WS Auth — Token in URL Query Param Leaks Into Logs (CSWSH + IDOR Gateway)

**What goes wrong:**
The browser WebSocket API (`new WebSocket(url)`) cannot send HTTP headers, so developers reach for `?token=<jwt>` in the URL. That token appears in: (a) server access logs, (b) reverse-proxy logs, (c) Referrer headers when the PWA navigates after connect, and (d) browser history. Any attacker with log access has the client's session token. Separately, because `WebSocket` connections do not enforce Same-Origin Policy by default, any page loaded in the client's browser can open a WebSocket to the gym API with the browser's existing cookies — Cross-Site WebSocket Hijacking (CSWSH).

**Why it happens:**
HTTP endpoints already work via `cc_client_*` httpOnly cookies, so the developer copies that pattern into the WS handler without noticing that standard `WebSocket` upgrade requests also carry `Cookie` headers — no URL token is needed. The CSWSH gap is invisible in dev (same origin).

**How to avoid:**
- Use httpOnly cookie auth for WS exactly like HTTP: FastAPI supports `Cookie(...)` in WS `Depends()`. The `cc_client_access` httpOnly cookie is sent automatically on the WS upgrade request to the same origin.
- Add an `Origin` header check (allowlist of known PWA origins) at WS connection time. FastAPI does NOT do this automatically. A `Depends(verify_ws_origin)` that compares `websocket.headers.get("origin")` against `settings.allowed_origins` is the correct gate.
- Never accept `?token=` on the WS endpoint. If the cookie model must change (e.g., cross-origin PWA), use a short-lived one-time token issued by a REST endpoint (`POST /client/ws-ticket` returns a `ws_ticket` valid for 10s, consumed on first connect) — but the existing same-origin cookie model is sufficient for this PWA.
- The existing `require_client()` dependency reads cookies; adapting it for WS context (`WebSocket` instead of `Request`) is a single typed parameter swap.

**Warning signs:**
- Any WS endpoint URL containing `token=`, `access_token=`, or `jwt=` as a query param.
- No `Origin` check in the WS connection handler.
- Access logs showing JWT strings in WS upgrade request lines.

**Phase to address:**
Phase 90 (WebSocket + messaging domain foundation). The `verify_ws_origin` dependency and cookie-based `require_client_ws()` wrapper must be specced in the plan before any WS endpoint is written. LOCKED INVARIANT: this is an IDOR gateway — a missing Origin check means any JS script on any tab can open a WS to the gym API with the logged-in client's session.

---

### Pitfall 2: IDOR Over WebSocket — Missing Per-Client Authorization on Subscribe

**What goes wrong:**
The WS endpoint accepts connection from any authenticated client and subscribes them to a Redis pub/sub channel. If the channel name is derived from a `thread_id` or `client_id` taken from the URL/message body (not from the authenticated principal), client A can subscribe to client B's message channel by guessing or probing the channel name. This is the WS equivalent of the IDOR the D-20-IDOR invariant prevents on HTTP endpoints.

**Why it happens:**
The developer models the WS endpoint as `GET /ws/chat/{thread_id}` and subscribes the connecting socket to channel `chat:{thread_id}`. The `thread_id` is a UUID, "hard to guess," so it feels safe. But the thread ownership check (does this `thread_id` belong to the authenticated `client_id`?) is missing.

**How to avoid:**
- `client_id` comes ONLY from `require_client_ws()` principal — never from path params, query params, or WS message body.
- On WS connect: validate that the channel the client is subscribing to is their own thread. Because there is exactly one 1:1 thread per client, the channel name must be `chat:client:{client_id}` (derived from the principal), never from the URL.
- Reject any WS message that tries to switch channels mid-connection.
- The 404-collapse pattern applies: if the thread does not exist for this client, close the WS with code `1008` (Policy Violation) without indicating whether the thread exists for another client.

**Warning signs:**
- WS endpoint has a `thread_id` path parameter that is used as the channel name without cross-checking against the authenticated `client_id`.
- Redis subscription channel name contains a value from the WebSocket message payload.
- No test asserting that client A cannot receive client B's messages.

**Phase to address:**
Phase 90 (WS + messaging foundation). The channel naming scheme must be locked in the phase plan: `chat:client:{client_id}` derived from principal. LOCKED INVARIANT: breaks D-20-IDOR.

---

### Pitfall 3: SQLAlchemy Async Session Leak Inside Long-Lived WS Handlers (Session-Per-Connection Anti-Pattern)

**What goes wrong:**
A WS handler opens a DB session at connection time and keeps it open for the duration of the connection (potentially minutes or hours). Each concurrent connection holds a DB connection from the pool indefinitely. With 50 concurrent clients, 50 DB connections are held open even if no messages are in flight. Pool exhaustion causes `TimeoutError` on all new connections (HTTP requests and WS connections alike). SQLAlchemy's idle-in-transaction timeout on Postgres will also kill long-held sessions, causing cryptic `InvalidRequestError` mid-message.

**Why it happens:**
The existing `get_db()` dependency yields a session per HTTP request — short-lived. The developer copies `Depends(get_db)` into the WS handler, which keeps the dependency alive until the WS disconnects.

**How to avoid:**
- Never open a DB session at WS connection time. The WS handler manages the connection lifecycle; sessions are opened per-operation (per-message, per-query) using `async with session_factory() as session`.
- Inject `session_factory: async_sessionmaker` (from `app.state.sessionmaker`) into the WS handler as a direct state reference, not via `Depends(get_db)`.
- Pattern: `async with app.state.sessionmaker() as session: await session.execute(...)`  — opened and closed for each message operation, not for the WS lifecycle.
- The `get_db()` dependency (which yields one session per HTTP request and commits on exit) is explicitly the wrong tool for WS.

**Warning signs:**
- WS handler signature: `async def ws_chat(websocket: WebSocket, session: AsyncSession = Depends(get_db))`.
- DB connection pool saturation visible in Postgres `pg_stat_activity` with long-idle `idle in transaction` rows.
- `TimeoutError: QueuePool limit of size N overflow N reached` in logs under concurrent WS test.

**Phase to address:**
Phase 90 (WS handler scaffold). The session usage pattern must be explicit in the plan. Add a pool-saturation test: open N concurrent WS connections, verify DB pool is not exhausted.

---

### Pitfall 4: Multi-Worker Fan-Out Failure — Works In Dev, Breaks In Production

**What goes wrong:**
In dev, one uvicorn worker handles all connections. A client sends a message; the worker broadcasts it back via in-process state or via the WS connection it holds in memory. In production (gunicorn + multiple uvicorn workers), the message write may arrive on worker A (HTTP POST or bot callback) while the client's WS connection lives on worker B. Worker A's in-process pub/sub or dict delivers to nobody. The message is saved to DB but never pushed to the client in real time.

**Why it happens:**
The developer tests with `uvicorn app.main:app` (single worker) and sees messages arrive. CI passes. Multi-worker production is never tested.

**How to avoid:**
- Redis pub/sub is the correct fan-out mechanism: when a message is saved, publish to `chat:client:{client_id}`. Every worker that holds a WS connection for that client is subscribed to that channel and forwards the message.
- The WS handler must establish a Redis subscription on connect and release it on disconnect — Redis pub/sub is per-subscriber (each worker creates its own subscriber connection).
- Use `redis.asyncio`'s `PubSub` context: `async with redis.pubsub() as pubsub: await pubsub.subscribe(channel)` then `async for message in pubsub.listen()`. The `listen()` loop runs alongside the `receive_text()` loop via `asyncio.gather` or `asyncio.create_task`.
- Test with `--workers 2` or use two separate in-process `asyncio` event loops in integration tests to simulate the cross-worker scenario.

**Warning signs:**
- No Redis pub/sub code anywhere in the WS handler.
- WS handler stores active connections in a module-level `dict` keyed by `client_id`.
- Zero test that sends a message from one context (bot callback / HTTP POST) and verifies it arrives on a WS connection opened in a different test coroutine.

**Phase to address:**
Phase 90 (WS + Redis pub/sub scaffold). The cross-worker fan-out test is mandatory before the phase closes. This is the "passes in dev, breaks in prod" pitfall most likely to be missed.

---

### Pitfall 5: Redis Pub/Sub At-Most-Once Delivery — No Catch-Up On Reconnect

**What goes wrong:**
Redis pub/sub has no persistence and no message retention. If a client's WS connection drops and reconnects (network glitch, mobile background), all messages published during the disconnection are lost. The client's chat history has a gap. Worse, if the reconnect happens in the same `listen()` loop without a DB catch-up fetch, the client sees an inconsistent thread.

**Why it happens:**
The developer sees Redis pub/sub deliver messages reliably in happy-path tests and assumes it is sufficient. Reconnect logic is not tested (network failures are hard to simulate).

**How to avoid:**
- Treat Redis pub/sub as a *notification transport*, not a *message store*. Messages are always written to the DB first (in `chat_messages` table), then a lightweight event is published to Redis: `{"event": "new_message", "message_id": "..."}`.
- On WS connect (and reconnect), the handler always fetches undelivered messages from DB: `SELECT * FROM chat_messages WHERE thread_id = :thread AND id > :last_seen_id ORDER BY id ASC`. The client sends its `last_seen_message_id` in the connect handshake.
- The Redis event is only a push notification that causes the client to re-fetch or confirms a delivery it already received. Messages are never sent *only* via pub/sub without a DB record.
- Include a `last_seen_message_id` in the WS connect handshake (first message from client after upgrade).

**Warning signs:**
- Chat messages are published directly to Redis and never written to a DB table.
- WS handler does not fetch any DB history on connect.
- No test for: disconnect → new messages arrive → reconnect → client receives missed messages.

**Phase to address:**
Phase 90 (messaging foundation + WS design). The DB-first + Redis-notify pattern must be locked as an architectural decision before any code is written. Reconnect test is mandatory.

---

### Pitfall 6: WS Connection Zombie — No Heartbeat / Ping-Pong / Backpressure

**What goes wrong:**
Mobile clients go to background; NAT/firewall silently drops the TCP connection without sending a TCP FIN. The server's WS handler is stuck `await websocket.receive_text()` on a dead connection indefinitely. The worker's DB subscription or Redis pub/sub subscription remains open. Over time, zombie connections accumulate; Redis pub/sub subscriber count grows; memory and Redis connections leak.

**Why it happens:**
FastAPI's WS implementation does not send automatic ping frames unless explicitly configured. The developer tests with a desktop browser (which sends WS ping frames) and never sees the issue.

**How to avoid:**
- Implement application-level ping/pong: the server sends a `{"type": "ping"}` JSON message every 30s. If no pong (or any message) is received within 60s, the server closes the connection with `1001` (Going Away).
- Starlette (which FastAPI builds on) does support WS ping at the protocol level; set `websocket.ping_interval` if the underlying transport supports it — but application-level ping is more portable.
- Use `asyncio.wait_for(websocket.receive_text(), timeout=60.0)` and catch `asyncio.TimeoutError` to detect dead connections.
- The `finally:` block of the WS handler must unconditionally: cancel the Redis pub/sub task, release the Redis subscriber, and close the WS connection.

**Warning signs:**
- WS handler is `while True: data = await websocket.receive_text()` with no timeout.
- No `try/finally` in the WS handler.
- Redis subscriber count grows proportionally to historical connection count (not current connection count).

**Phase to address:**
Phase 90 (WS handler lifecycle). Heartbeat logic and `finally` cleanup must be in the WS handler scaffold from day one. Add a zombie detection test.

---

### Pitfall 7: Attachment Stored XSS via Content-Type — SVG and HTML Execution

**What goes wrong:**
A client uploads a file with content `<script>alert(1)</script>` or a crafted SVG containing JS. The server stores it and later serves it with `Content-Type: image/svg+xml` (or worse, `Content-Type: text/html` if content-type is derived from the file extension). The receiving staff member (or another client) opens the "photo" in a browser tab; the JS executes in the gym's origin context, stealing session cookies or making API calls as the victim.

**Why it happens:**
The developer uses `python-magic` or `mimetypes.guess_type()` on the filename to set the Content-Type, trusting the client-supplied filename. SVG files are valid images but are also XML with embedded script capability.

**How to avoid:**
- **Allowlist by magic bytes**, not filename extension: read the first 16–512 bytes of the upload and verify the magic signature matches JPEG (`\xff\xd8\xff`), PNG (`\x89PNG\r\n\x1a\n`), GIF (`GIF87a` / `GIF89a`), or WebP (`RIFF...WEBP`). Reject everything else with `422 unsupported_media_type`.
- Explicitly **ban SVG and HTML**: even if the magic bytes are otherwise valid, reject `image/svg+xml` and any `text/*` content types.
- Serve stored files with a **forced Content-Type from the allowlist** (never echo back the client-supplied type) and add `Content-Disposition: attachment` + `X-Content-Type-Options: nosniff`.
- Host files on a **separate domain or path prefix** (`/uploads/` or a separate CDN subdomain) so even if a stored XSS fires, it is not on the gym's cookie-bearing origin. This is the browser's Same-Origin Policy as a defense-in-depth.
- The Phase 88 `photo_url` validator (`http(s)`-only) is a precedent but solves a different problem (SSRF via URL); stored upload XSS requires magic-byte validation at write time.

**Warning signs:**
- Upload handler checks `content_type` from the multipart request headers (client-controlled).
- SVG files pass the file-type check.
- `Content-Type` header on served files is derived from the stored filename or from the upload request.
- No `X-Content-Type-Options: nosniff` header on attachment serve endpoints.

**Phase to address:**
Phase 91 or 92 (attachment upload). Magic-byte validation and Content-Type enforcement must be in the upload handler spec. LOCKED INVARIANT: this is the attachment-XSS guard — missing it violates the stored-XSS discipline established by the Phase 88 `photo_url` validator.

---

### Pitfall 8: Path Traversal and IDOR on Attachment Serving

**What goes wrong:**
Attachments are stored with filenames like `{message_id}_{original_filename}.jpg`. The serve endpoint is `GET /client/attachments/{filename}`. A client crafts `filename=../../etc/passwd` (path traversal) or `filename=other_client_message_uuid.jpg` (IDOR). The server reads an arbitrary file or serves another client's attachment.

**Why it happens:**
The developer builds the file path as `UPLOAD_DIR / filename` and trusts the `filename` path param. Python's `pathlib.Path` resolves `../` automatically, escaping the upload directory.

**How to avoid:**
- **Path traversal:** Use `Path(UPLOAD_DIR / filename).resolve()` and assert that the resolved path `is_relative_to(UPLOAD_DIR)`. Reject if not. Never concatenate user input into file paths without this check.
- **IDOR on serve:** Do not use a guessable filename as the authorization gate. Store files with opaque names (UUID-based) and record the `client_id` owner in the `chat_message_attachments` table. The serve endpoint must look up the file record by ID, verify `owner_client_id == principal.client_id` (D-20-IDOR), then serve. A correctly guessed UUID without an ownership match returns `404`.
- Alternatively, use **pre-signed URLs** with expiry (HMAC-signed URL valid for 60s, generated at message send time) so the serve endpoint verifies the signature, not the session. This decouples attachment serving from session state.
- Do not serve attachments from the same path prefix as API routes (`/api/`). Use `/static/uploads/` or a dedicated subdomain.

**Warning signs:**
- Serve endpoint has `filename: str` as a path param and constructs `UPLOAD_DIR / filename` without `.resolve()` + `is_relative_to()`.
- Stored filename contains the original client-supplied filename (e.g., `user_photo.jpg`).
- No DB lookup in the serve endpoint (authorization is purely the path param).

**Phase to address:**
Phase 91 or 92 (attachment upload + serve). IDOR and path traversal prevention must be in the spec. LOCKED INVARIANT: IDOR on attachments breaks D-20-IDOR.

---

### Pitfall 9: Telegram Bridge Reply Routing to Wrong Client Thread

**What goes wrong:**
Staff member receives client A's message as a Telegram DM from the bot and replies. The reply must be routed to client A's thread. If the routing table (Telegram `chat_id` → `client_id`) is derived from the most recently active thread or from the bot's conversation state (which python-telegram-bot 22 does not persist across restarts), a reply may arrive in client B's thread — who was the last client to message before the restart.

**Why it happens:**
The existing bot `HandlerContext` holds in-memory state per handler invocation, not per-conversation. The Telegram reply from staff arrives as a plain text message to the bot, with no thread context in the message itself (Telegram does not embed a `reply_to_message_id` on staff-initiated messages unless the staff explicitly hits Reply).

**How to avoid:**
- **Require staff to always use Telegram's Reply function** to respond to the bot's forwarded message. The forwarded message contains the client's message as quoted text; the `reply_to_message.message_id` identifies which client message this is a reply to. Store `telegram_message_id → chat_message_id` in the DB when forwarding client messages to the staff Telegram chat.
- Alternative (more robust): Use a **dedicated Telegram group** per gym (not 1:1 DM to the bot). Forward each client message with a thread prefix: `[Иванов И.] Добрый день...`. Staff replies to the forwarded message, which carries `reply_to_message.message_id`. The bot looks up `telegram_message_id` in the `chat_forwarding_log` table to find the originating `client_id`.
- Store a `chat_forwarding_log` table: `(telegram_message_id, chat_message_id, client_id, forwarded_at)`. Indexed on `telegram_message_id`. On any incoming bot message with `reply_to_message.message_id`, do `SELECT client_id FROM chat_forwarding_log WHERE telegram_message_id = :reply_to_id`. If not found (staff sent a non-reply message), log a warning and drop — do not route to last-active thread.
- This follows the D-06 / D-10 worker→modules relaxation: `telegram_bot.py` imports `messaging.service` via the `HandlerContext` pattern already established.

**Warning signs:**
- Bot routing logic reads from an in-memory `dict` or a module-level variable to map the current conversation to a client.
- No `chat_forwarding_log` table in migrations.
- Staff can reply to the bot without using Telegram's native Reply function and still have the message routed.

**Phase to address:**
Phase 93 (Telegram bridge). The `chat_forwarding_log` table and reply-dispatch logic must be specced before implementation. Add a test: staff replies to an old forwarded message → routes to the correct client, not the most recently active one.

---

### Pitfall 10: Telegram Message Loop / Echo Between Bridge and Bot

**What goes wrong:**
Client sends a message → bot forwards to staff Telegram chat → staff replies → bot routes reply back to client → bot also tries to forward the staff reply back to the staff Telegram chat as if it were a new client message → infinite echo loop.

**Why it happens:**
The bot's message handler receives ALL updates in the staff chat, including bot-sent messages. If the handler does not distinguish between "client message forwarded by bot" and "staff reply to bot," it processes bot-forwarded messages as new client messages.

**How to avoid:**
- In the Telegram update handler, check `update.message.from_user.is_bot` — if true, skip (do not process bot-forwarded messages as client messages).
- Additionally, skip any message whose `chat_id` is the staff Telegram group/channel unless it has `reply_to_message.message_id` pointing to a bot-forwarded message (i.e., is a staff reply). Plain staff messages with no reply context are discarded.
- The `chat_forwarding_log` lookup is the natural loop-breaker: a bot-forwarded message will have its own `telegram_message_id` in the log; when the bot receives it as an "update," it finds that ID in the log and skips it (it is already recorded as a forwarded client message, not a new one).
- The existing Redis `cc:bot:update:{update_id}` dedup (D-20-3, Phase 20) already deduplicates update IDs — ensure this covers the staff-chat channel too.

**Warning signs:**
- The Telegram update handler has no `is_bot` check.
- No dedup key that distinguishes bot-sent from user-sent messages.
- Running the bot against a test chat shows messages doubling or tripling.

**Phase to address:**
Phase 93 (Telegram bridge). Loop prevention must be in the bot handler spec. Test: simulate a full round-trip (client → staff Telegram → reply → client) and assert exactly one message appears in each direction.

---

### Pitfall 11: Staff Identity Lost in Telegram Bridge — All Replies Look Like "Зал"

**What goes wrong:**
Multiple staff members (owner + reception) share the same Telegram group and all reply via the bridge. The client sees all replies as coming from "Зал" with no indication of who replied. In a multi-staff gym, this is acceptable for v2.5, but the `actor_*` audit trail (established in every other module) would be absent from chat messages written via the bot — the `sender_type = 'staff'` row has no `user_id`.

**Why it happens:**
The Telegram group context has no reliable way to associate a Telegram user to a `users` table row without explicit staff registration (linking Telegram accounts to staff users). This is a hard constraint.

**How to avoid:**
- Accept the constraint for v2.5: staff messages have `sender_type = 'staff'`, `sender_user_id = NULL`. Document this in the `chat_messages` schema.
- Record `telegram_user_id` and `telegram_username` in the staff reply row as a nullable audit field (even without a FK to `users`). This gives an operator-visible trace without requiring full staff Telegram registration.
- Add a LOCKED audit event `chat_staff_reply_sent` with `payload: {telegram_user_id, telegram_username}` — same INFRA-15 discipline as all other audit events.
- For v2.6 (admin-web chat inbox), the staff identity problem disappears because the reply comes via an authenticated HTTP session.

**Warning signs:**
- No `telegram_user_id` or `telegram_username` column on staff reply rows.
- LOCKED_AUDIT_EVENTS does not include the chat domain events before any chat callsite ships.

**Phase to address:**
Phase 93 (Telegram bridge). Decision must be locked in the phase plan: v2.5 = anonymous staff identity with `telegram_user_id` trace field; full staff identity → v2.6.

---

### Pitfall 12: Telegram Bot Rate Limits Under Message Volume

**What goes wrong:**
The Telegram Bot API enforces: 30 messages per second globally, 1 message per second per chat. If the gym has many concurrent active clients and the bridge forwards every message immediately and synchronously, a burst of incoming messages exhausts the rate limit. Telegram returns `429 Too Many Requests` with `retry_after`. The bot crashes or drops messages silently.

**Why it happens:**
The existing bot uses fire-and-forget `await sender.send_*()` calls (seen in `app/integrations/telegram/sender.py`). Adding a high-frequency chat forwarding path amplifies the request rate.

**How to avoid:**
- Wrap staff-notification sends in the existing ARQ task pattern: the WS handler enqueues an ARQ task `dispatch_chat_notification_to_staff` instead of calling the Telegram API directly. The ARQ worker respects the queue and can implement exponential back-off on `429`.
- Alternatively, python-telegram-bot 22's `Application` class has a `rate_limiter` hook; configure it with the `AIORateLimiter` plugin.
- For the forwarding flow: staff notifications are best-effort (a message in the DB is the truth; Telegram DM is a convenience). Do not make message commit depend on Telegram delivery.

**Warning signs:**
- `await telegram_sender.send_message(staff_chat_id, ...)` called synchronously inside the message-write transaction.
- No retry or back-off on `TelegramError` (429) in the forwarding path.
- Bot process crashes under simulated message burst.

**Phase to address:**
Phase 93 (Telegram bridge). The ARQ-mediated forwarding pattern must be in the spec.

---

### Pitfall 13: Testing WebSocket Endpoints with ASGITransport — httpx Does Not Support WS Upgrade

**What goes wrong:**
`httpx.AsyncClient` with `ASGITransport` handles HTTP/1.1 requests but does NOT support the WebSocket upgrade handshake. Attempting `await client.get("ws://...")` or using the WS URL scheme raises `httpx.UnsupportedProtocol`. The developer cannot write ASGITransport-based WS tests using the existing `async_client` fixture pattern.

**Why it happens:**
The CLAUDE.md constraint mandates `httpx ASGITransport` for all backend tests. The developer assumes this covers WS too, discovers it does not, and either (a) skips WS testing entirely, or (b) spins up a real network stack (real port, `async_client` with `base_url="http://..."`) which is slower and requires real process management.

**How to avoid:**
- Use **Starlette's `TestClient`** (synchronous) or **`WebSocketTestSession`** (which Starlette's `TestClient.websocket_connect()` returns) for WS endpoint tests. This is the FastAPI-recommended pattern per official docs. Starlette's `TestClient` uses ASGI directly (no real network) and does support WS upgrade.
- Pattern for an async test suite:
  ```python
  from starlette.testclient import TestClient
  with TestClient(app) as tc:
      with tc.websocket_connect("/ws/chat") as ws:
          ws.send_json({"type": "ping"})
          data = ws.receive_json()
  ```
- Because `TestClient` is synchronous but the test suite uses `pytest-asyncio`, WS tests run in a separate `pytest.mark.asyncio(mode="auto")` exemption or are written as sync tests. Wrap the synchronous `TestClient` context in a `threading.Thread` if mixing with async fixtures is required.
- The WS endpoint itself can still be tested for auth (cookie present/absent), IDOR (wrong client_id), and message routing logic by inspecting what the mock Redis pub/sub delivers — no real Redis needed for unit-level routing tests.
- For multi-worker fan-out integration tests, use two `TestClient` instances sharing the same ASGI app (which shares in-process state) plus a real Redis (docker-compose up redis) to verify cross-subscriber delivery.

**Warning signs:**
- `async_client.get("/ws/...")` in a test (will raise `UnsupportedProtocol` at runtime).
- Zero WS-specific tests in the messaging module test suite.
- Tests only cover the REST endpoints (`POST /client/messages`) but not the WS delivery path.

**Phase to address:**
Phase 90 (WS scaffold). The test pattern must be established in the first WS plan before any endpoint is written. A WS test template (connect, authenticate via cookie, send/receive, disconnect) must be the first deliverable of the phase.

---

### Pitfall 14: OpenAPI Drift — WS Endpoint and Attachments Are Not in openapi.json

**What goes wrong:**
WebSocket endpoints do not appear in FastAPI's generated OpenAPI schema by default. Multipart file upload (`UploadFile`) may produce incorrect schema if not annotated properly. The byte-stable `openapi.json` drift gate (CI job) passes because WS endpoints are simply absent — not because they are correctly documented. The `schema.d.ts` codegen for the PWA has no typed client for the messaging REST endpoints either.

**Why it happens:**
FastAPI's `app.openapi()` generator skips `@app.websocket()` routes. The developer ships the WS endpoint without noticing it is absent from the spec, and the drift gate silently stays green because nothing changed from its perspective.

**How to avoid:**
- WS endpoints require **manual OpenAPI augmentation**: add a `paths["/ws/chat"]["get"]` entry to the `_customize_openapi()` post-processor (Phase 64 pattern) with the correct `101 Switching Protocols` response and `securitySchemes` reference.
- REST endpoints for messaging (`GET /client/messages`, `POST /client/messages`, `POST /client/messages/{id}/attachments`) must appear in `openapi.json` with full request/response schemas and the `Client-Portal` tag.
- Attachment upload endpoint must use `fastapi.UploadFile` with proper `multipart/form-data` annotation so the schema reflects binary upload.
- The `AssertNonNever` forward-guards in `schema.contract.test.ts` must include the v2.5 messaging paths. The `_v25Checks` tuple is the Phase 95 (OpenAPI handoff) deliverable.
- The drift gate CI job must be run against the new `openapi.json` after every plan that adds a new endpoint.

**Warning signs:**
- `openapi.json` does not contain `/client/messages` paths after Phase 90 or 91 ships.
- `_customize_openapi()` in `main.py` has no WS path entry.
- `schema.d.ts` has no `ClientSendMessageRequest` or `ClientMessageResponse` types.

**Phase to address:**
Phase 95 (OpenAPI handoff). But the REST endpoint schemas must be generated correctly from Phase 90 onward — do not hand-stub them. LOCKED INVARIANT: byte-stable `openapi.json` drift gate must remain green throughout.

---

### Pitfall 15: import-linter Violation — messaging Module Importing Other Business Modules

**What goes wrong:**
The `app/modules/messaging/` module needs to know which client a thread belongs to (`clients` table) and possibly query delivery status. If `messaging/service.py` imports `from app.modules.clients.models import Client` or `from app.modules.notifications.service import create_notification`, import-linter's `modules-independent` contract fails immediately. The CI lint gate turns red.

**Why it happens:**
The messaging module legitimately needs cross-module data (client name for Telegram forwarding, in-app notification creation). The developer reaches for direct ORM imports, which is the pattern inside each module but not across module boundaries.

**How to avoid:**
- Cross-module reads use **raw SQL `text()` SELECT** per D-54-08 (established in v1.8 reports, reinforced in v2.0–v2.4). `messaging/repository.py` reads `clients` columns via `text("SELECT name FROM clients WHERE id = :id")` — no ORM model import.
- Cross-module writes (creating an in-app notification on new message) use a **`ignore_imports` edge** in `.importlinter` following the D-87-03 precedent: `app.modules.messaging.service -> app.modules.notifications.service`. This is the minimum necessary edge; register it before the first callsite (INFRA-15 discipline).
- The `messaging` module must be registered in `.importlinter`'s `modules-independent` contract before any code is written (same INFRA-15 discipline as every prior module).
- Telegram bot imports follow D-06 / D-10: `telegram_bot.py` imports `messaging.service` as a relaxation; `app.integrations.telegram.handlers` does NOT (integrations ⊥ modules contract).

**Warning signs:**
- `from app.modules.clients.models import Client` appears in any file under `app/modules/messaging/`.
- `app.modules.messaging` is not in `.importlinter`'s `modules-independent` contract.
- CI `lint-imports` gate turns red after Phase 90.

**Phase to address:**
Phase 90 (messaging module scaffold). `.importlinter` registration + any needed `ignore_imports` edges must be in the plan before the module body is written. LOCKED INVARIANT: breaks the `modules-independent` architectural constraint.

---

### Pitfall 16: camelCase Wire Format Inconsistency — Messaging Responses Use snake_case

**What goes wrong:**
The existing API contract (`contract-freeze-v1.11.0`) uses camelCase wire format for all JSON responses (enforced by `BackendSchemaBase` with `model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)`). A newly written `MessageResponse` schema that omits `alias_generator` emits `sender_type`, `sent_at`, `thread_id` instead of `senderType`, `sentAt`, `threadId`. The `schema.d.ts` codegen produces the wrong TypeScript field names; the PWA's `clientQueries` mapping breaks.

**Why it happens:**
The developer writes a new Pydantic model for the messaging domain and forgets to inherit from `BackendSchemaBase` or to configure `alias_generator`.

**How to avoid:**
- All new schemas must inherit from `BackendSchemaBase` (established project convention, Phase 15 bedrock).
- All response field names in the OpenAPI spec and `schema.d.ts` must be camelCase. Verify with the drift gate after adding any new schema.
- The PWA already has `clientFetcher` with camelCase mapping — no change needed on the frontend if the backend schema is correct.
- Add a schema-level unit test: `assert MessageResponse.model_fields["sent_at"].alias == "sentAt"`.

**Warning signs:**
- `MessageResponse` or `AttachmentResponse` has fields like `sender_type`, `created_at`, `thread_id` in the serialized JSON (visible in WS `send_json()` payload or REST response body).
- `schema.d.ts` codegen produces snake_case fields for messaging types.

**Phase to address:**
Phase 90 (messaging schema design). Verify camelCase output in the first plan that introduces `MessageResponse`. Check with `ruff` and `mypy --strict` from day one.

---

### Pitfall 17: Unbounded File Size / Missing Size Cap on Attachment Upload

**What goes wrong:**
A client uploads a 100 MB video file labeled as `image/jpeg`. The server streams it entirely into memory (or to disk without a size check), exhausting either the container's memory or disk space. Under concurrent uploads, the server OOMs and restarts.

**Why it happens:**
FastAPI's `UploadFile` streams lazily, but `await file.read()` loads the entire file into memory. If size is checked after `read()`, the damage is already done.

**How to avoid:**
- Set a `MAX_UPLOAD_SIZE_BYTES` constant (recommend 5 MB for gym chat photos).
- Check `Content-Length` header before reading: `if int(request.headers.get("content-length", 0)) > MAX_UPLOAD_SIZE_BYTES: raise HTTPException(413)`. Note: `Content-Length` is client-supplied and can be spoofed; combine with chunked read.
- Read in chunks: `chunk = await file.read(MAX_UPLOAD_SIZE_BYTES + 1)`. If `len(chunk) > MAX_UPLOAD_SIZE_BYTES`, reject with `413 Payload Too Large` and discard.
- Do NOT use `await file.read()` without a size limit.
- Add the size limit constant to `app/core/config.py` (`Settings`) so it is configurable via env var.

**Warning signs:**
- Upload handler calls `data = await file.read()` without any size check.
- No `413` response path in the upload endpoint.
- No `MAX_UPLOAD_SIZE_BYTES` constant defined.

**Phase to address:**
Phase 91 or 92 (attachment upload). Size limit must be in the endpoint spec before implementation.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| In-memory connection dict for WS fan-out | Simpler code, no Redis dep | Silent failure in multi-worker prod; zombie connections | Never in this codebase (gunicorn multi-worker) |
| WS session = `Depends(get_db)` (one session per connection) | Familiar pattern | DB pool exhaustion; Postgres idle-in-transaction timeout kills long sessions | Never |
| Token in WS URL query param | Works without cookie changes | Token leaked to logs, CSWSH risk | Never |
| Content-type from client-supplied header | Simpler upload | SVG/HTML stored XSS | Never |
| Send chat messages via Telegram synchronously in transaction | Simpler code | Telegram 429 rate-limit causes transaction rollback or silent drop | Never — always enqueue ARQ task |
| Skip origin check on WS endpoint | Fewer lines | CSWSH (cross-site WS hijacking) | Never |
| Derive attachment serve URL from raw filename | Simpler routing | Path traversal, IDOR | Never |
| Skip `chat_forwarding_log` table | Simpler bridge | Reply routing ambiguity; wrong client receives staff reply | Never |
| Register `app.modules.messaging` in importlinter after code is written | Faster first iteration | lint-imports CI gate turns red; architectural invariant violated | Never — INFRA-15 discipline requires pre-registration |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| FastAPI WebSocket + httpx ASGITransport | `async_client.get("ws://...")` raises UnsupportedProtocol | Use `starlette.testclient.TestClient.websocket_connect()` for WS tests |
| Redis pub/sub + multi-worker | Module-level connection dict for WS fan-out; works in dev | Subscribe per-worker; publish on message write; one subscriber per WS connection |
| Redis pub/sub delivery guarantee | Treat pub/sub as message store | Pub/sub = notification only; messages stored in DB; client fetches history on reconnect |
| Telegram bot reply routing | Read `update.effective_message.text` and route to last active thread | Require staff to use Telegram Reply; look up `chat_forwarding_log` by `reply_to_message.message_id` |
| python-telegram-bot 22 rate limits | Direct `send_message()` in WS handler | Enqueue ARQ task; use `AIORateLimiter` or exponential backoff on 429 |
| File upload + magic bytes | `mimetypes.guess_type(filename)` | Read first 16 bytes; match against JPEG/PNG/GIF/WebP magic signatures |
| SQLAlchemy async + WS | `Depends(get_db)` in WS route (holds session for connection lifetime) | Inject `session_factory`; open session per message operation |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| DB session held for WS connection lifetime | Pool exhaustion; `QueuePool limit reached` | Session per operation, not per connection | At ~pool_size (default 5) concurrent connections |
| Redis pub/sub subscriber per connection without cleanup | Redis memory grows; subscriber count never decreases | `finally:` block unsubscribes and closes pub/sub client on WS disconnect | At ~50 concurrent connections |
| Synchronous Telegram forward in WS message handler | WS handler latency spikes under rate limit; client send appears slow | ARQ task for Telegram delivery; message write confirms separately | At >1 concurrent client message per second |
| `await file.read()` without size limit on attachment upload | Container OOM on large uploads; all workers affected | Chunked read with `MAX_UPLOAD_SIZE_BYTES + 1` limit | On first large file upload |
| `asyncio.gather(receive_loop, pub_sub_loop)` with unhandled exception in one task | Other task continues silently with a dead partner | `asyncio.TaskGroup` (Python 3.11+) or explicit exception propagation in `gather` | Immediately on any WS error |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| No Origin check on WS endpoint | CSWSH: any tab can open WS as the logged-in client | `verify_ws_origin` dependency checking `websocket.headers["origin"]` against allowlist |
| client_id from WS path/query param (not principal) | IDOR: client subscribes to another client's chat channel | Channel name = `chat:client:{principal.client_id}` — never from URL |
| SVG or HTML accepted as photo attachment | Stored XSS: JS executes in gym's origin when "photo" is opened | Magic-byte allowlist; ban SVG; `Content-Disposition: attachment`; `X-Content-Type-Options: nosniff` |
| Filename used as file path without traversal check | Path traversal: reads arbitrary server files | `Path(UPLOAD_DIR / name).resolve().is_relative_to(UPLOAD_DIR)` |
| IDOR on attachment serve (filename = auth gate) | Client reads another client's photo | DB lookup by attachment UUID; verify `owner_client_id == principal.client_id` |
| JWT in WS URL (`?token=...`) | Token leaked to logs, reverse proxies, browser history | httpOnly cookie on WS upgrade (same as HTTP); never URL token |
| `LOCKED_AUDIT_EVENTS` not extended before chat callsites | AST gate fails; silent audit gap | Pre-register all chat events in `LOCKED_AUDIT_EVENTS` before first `audit.emit()` callsite (INFRA-15) |
| `app.modules.messaging` missing from `.importlinter` | `modules-independent` contract fails silently until CI | Register in `.importlinter` before writing any module code (INFRA-15) |

---

## "Looks Done But Isn't" Checklist

- [ ] **WS auth:** Cookie-based `require_client_ws()` implemented; `?token=` URL param is absent from all WS URLs; Origin check in WS dependency.
- [ ] **IDOR over WS:** Channel name is `chat:client:{principal.client_id}`; no path param used as channel name; test asserts client A cannot receive client B's WS events.
- [ ] **Multi-worker fan-out:** Redis pub/sub implemented; cross-worker delivery test exists (message written in one context, received on WS in another).
- [ ] **Reconnect catch-up:** WS connect handshake accepts `last_seen_message_id`; server fetches missed messages from DB and delivers them before starting pub/sub listen.
- [ ] **WS heartbeat:** Server sends `{"type": "ping"}` every 30s; connection closed with 1001 if no pong within 60s; `finally:` block cleans up pub/sub subscription.
- [ ] **Attachment magic bytes:** Upload handler rejects non-JPEG/PNG/GIF/WebP by magic signature; SVG/HTML explicitly rejected; test asserts `422` on `<script>` file upload.
- [ ] **Attachment size cap:** Upload returns `413` for files >5 MB; chunked read used (not `await file.read()`).
- [ ] **Attachment IDOR:** Serve endpoint does DB lookup + `owner_client_id == principal.client_id`; test asserts client A cannot fetch client B's attachment by guessing UUID.
- [ ] **Path traversal:** Serve path resolves to within `UPLOAD_DIR`; test asserts `../../etc/passwd` returns `422` or `404`.
- [ ] **Telegram reply routing:** `chat_forwarding_log` table exists; reply route is via `reply_to_message.message_id` lookup; test: reply to old forwarded message routes to correct client.
- [ ] **Telegram echo loop:** `is_bot` check in update handler; bot-forwarded messages not re-processed as client messages.
- [ ] **import-linter:** `app.modules.messaging` in `.importlinter` `modules-independent` contract; `lint-imports` CI gate green after Phase 90.
- [ ] **OpenAPI drift gate:** All messaging REST endpoints in `openapi.json`; WS path manually documented; `schema.d.ts` contains `ClientMessageResponse`, `ClientSendMessageRequest`; drift gate green.
- [ ] **camelCase wire format:** All `MessageResponse` fields are camelCase in serialized JSON; `BackendSchemaBase` inherited.
- [ ] **LOCKED_AUDIT_EVENTS:** All chat/messaging audit events pre-registered before any `audit.emit()` callsite (INFRA-15 discipline).
- [ ] **Session per operation:** WS handler uses `session_factory()` per message, not `Depends(get_db)`.
- [ ] **Starlette TestClient for WS tests:** WS tests use `TestClient.websocket_connect()`; no `async_client.get("ws://...")` calls in test files.

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|-----------------|--------------|
| Token in URL / CSWSH / Origin check missing (P1) | Phase 90 (WS scaffold) | Test: WS connect from wrong origin rejected; no `?token=` in any WS URL |
| IDOR over WS subscribe (P2) | Phase 90 (WS scaffold) | Test: client A cannot receive client B's pub/sub messages; channel = principal.client_id |
| SQLAlchemy session per connection leak (P3) | Phase 90 (WS scaffold) | Load test: 50 concurrent WS connections + DB query; pool not exhausted |
| Multi-worker fan-out failure (P4) | Phase 90 (WS + Redis pub/sub) | Cross-context delivery test: message written via HTTP POST delivered to WS subscriber |
| Redis pub/sub at-most-once / no reconnect catch-up (P5) | Phase 90 (messaging design) | Reconnect test: disconnect → new messages arrive → reconnect → all messages received |
| Zombie connection / no heartbeat (P6) | Phase 90 (WS handler lifecycle) | Timeout test: no message for 60s → server closes connection; finally block fires |
| Attachment stored XSS via content-type (P7) | Phase 91/92 (attachment upload) | Test: SVG with `<script>` → 422; served files have `X-Content-Type-Options: nosniff` |
| Path traversal + IDOR on attachment serve (P8) | Phase 91/92 (attachment serve) | Test: `../etc/passwd` filename → 422/404; client A cannot fetch client B's attachment |
| Telegram reply routing to wrong client (P9) | Phase 93 (Telegram bridge) | Test: staff reply to message A routes to client A, not most-recently-active client |
| Telegram message echo loop (P10) | Phase 93 (Telegram bridge) | Round-trip test: exactly one message in each direction; no duplicates |
| Staff identity lost in Telegram bridge (P11) | Phase 93 (Telegram bridge) | Schema review: `telegram_user_id` column on staff reply rows; LOCKED_AUDIT_EVENTS includes `chat_staff_reply_sent` |
| Telegram rate limit crash (P12) | Phase 93 (Telegram bridge) | Test: burst of 10 messages → all forwarded via ARQ queue (no direct sync Telegram call in handler) |
| httpx ASGITransport does not support WS (P13) | Phase 90 (WS scaffold) | First WS test uses `starlette.testclient.TestClient.websocket_connect()`; no `async_client.get("ws://...")` anywhere |
| OpenAPI drift — WS and attachment endpoints absent (P14) | Phase 95 (OpenAPI handoff) | `openapi.json` contains `/client/messages` paths; WS path manually documented; drift gate green |
| import-linter violation from messaging module (P15) | Phase 90 (messaging scaffold) | `lint-imports` CI gate green after Phase 90; `app.modules.messaging` in `.importlinter` |
| camelCase wire format inconsistency (P16) | Phase 90 (messaging schema) | Schema unit test: `MessageResponse` fields serialized as camelCase; drift gate green |
| Unbounded file size (P17) | Phase 91/92 (attachment upload) | Test: 6 MB upload → 413; chunked read code review |

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Token-in-URL already in production | HIGH | Rotate all client sessions (Redis `cc:client:*` flush); switch to cookie auth; audit logs for token exposure |
| IDOR over WS already in production | HIGH | Deploy hotfix: close all WS connections; add origin + principal channel check; notify affected clients |
| DB pool exhaustion from session-per-connection | MEDIUM | Restart workers; deploy session-per-operation fix; add pool monitoring alert |
| Multi-worker fan-out broken in production | MEDIUM | Roll back to single worker temporarily; deploy Redis pub/sub; restore multi-worker |
| Stored XSS attachment in production | HIGH | Purge all attachments; re-validate with magic-byte scan; deploy Content-Disposition fix; notify affected users |
| Telegram reply routing to wrong client | MEDIUM | Drop `chat_forwarding_log` table, rebuild from message history; deploy routing fix; notify affected clients |
| import-linter violation breaking CI | LOW | Add raw-SQL `text()` read or `ignore_imports` edge; CI green in one plan |
| OpenAPI drift gate breaking CI | LOW | Regenerate `openapi.json`; update `schema.d.ts`; re-run drift gate check |

---

## Sources

- FastAPI WebSocket docs (authentication via Cookie/Header in WS): https://fastapi.tiangolo.com/advanced/websockets/ — HIGH confidence (official, verified via Context7)
- FastAPI WebSocket testing docs (`TestClient.websocket_connect`): https://fastapi.tiangolo.com/advanced/testing-websockets/ — HIGH confidence (official)
- Redis pub/sub delivery semantics (at-most-once, no persistence): https://redis.io/docs/latest/develop/interact/pubsub/ — HIGH confidence (official Redis docs)
- OWASP CSWSH (Cross-Site WebSocket Hijacking): https://owasp.org/www-community/attacks/Cross_Site_WebSocket_Hijacking — HIGH confidence (OWASP)
- OWASP Stored XSS via SVG: https://owasp.org/www-community/xss-filter-evasion-cheatsheet — HIGH confidence (OWASP)
- Python magic bytes / file type detection: https://python-magic.readthedocs.io/ — MEDIUM confidence (library docs)
- Codebase analysis — `app/workers/telegram_bot.py`, `app/integrations/telegram/handlers.py`, `app/modules/client_portal/router.py`, `app/.importlinter`, `apps/backend/tests/conftest.py` — HIGH confidence (direct source)
- Existing patterns from prior milestones — D-20-IDOR, D-06, D-10, D-54-08, INFRA-15, D-87-03, D-20-MODULE — HIGH confidence (proven in production-equivalent test suite)

---
*Pitfalls research for: v2.5 Chat / Messaging — WebSocket + attachments + Telegram bridge added to clubcore modular monolith*
*Researched: 2026-06-06*
