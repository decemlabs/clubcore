# Architecture Research: v2.5 Chat / Messaging — Client↔Gym

**Domain:** WebSocket real-time messaging integration into an existing FastAPI modular monolith
**Researched:** 2026-06-06
**Confidence:** HIGH (all findings from live codebase inspection; no guesses from training data)

---

## Established Architecture Constraints (DO NOT RE-RESEARCH)

These are locked invariants confirmed by reading `main.py`, `.importlinter`, `telegram_bot.py`, and `client_portal/router.py` directly:

- **Three import-linter contracts** actively enforced:
  1. `core-not-depend-on-modules`: `app.core` must not import `app.modules.*` (source_modules = app.core)
  2. `modules-independent`: all listed modules cannot import each other; cross-module reads use raw SQL `text()`, cross-module writes use Protocol slots registered in `app.core.dependencies`
  3. `integrations-not-depend-on-modules`: `app.integrations` must not import `app.modules.*` (with narrow `ignore_imports` exceptions for `email.dispatcher` importing module-scoped template registries)
- **`app.main` is exempt** from `core-not-depend-on-modules` because `source_modules = app.core`, not `app`. The composition root can do `from app.modules.X import Y` inside `create_app()` body — this is the established carve-out pattern (D-15, D-10, REG-29-03).
- **Telegram bot worker** (`app/workers/telegram_bot.py`) is a separate long-polling process. It is NOT an ARQ task. It opens `db_lifespan_manager()` + `redis_lifespan_manager()` independently, registers its own Protocol slots, builds a `HandlerContext` NamedTuple with module references, and passes that context to every handler function. D-06 allows `workers → app.modules.auth.telegram_service`; D-10 allows `workers → app.modules.visits.service`. Further worker→modules edges follow the same documented-exception pattern.
- **HandlerContext** is a NamedTuple (field order is a stable contract; new fields must be appended at the END). Fields are module references (`visits_service`, `bookings_service`, `schedule_service`, etc.). Handler functions receive the context and dispatch through it — never by importing modules directly (because `integrations ⊥ modules`).
- **`integrations/telegram/handlers.py`** uses `importlib.import_module` for type-only references that would otherwise break the `integrations ⊥ modules` contract. This is the established Option A pattern for that boundary.
- **ClientPrincipal**: the `aud="client"` JWT decoded by `decode_client_token`. Carried in the `cc_client_access` httpOnly cookie. The dependency `require_client()` in `app.core.dependencies` resolves it. No role claim; isolation from staff token by `aud` assertion (CISO-01/02).
- **Client-portal writes** go through Protocol-slot accessors in `app.core.dependencies` only. Direct imports of `app.modules.bookings`, `app.modules.visits`, etc. from `client_portal` are forbidden — evidenced by the 18+ `register_*` calls in `main.py`.
- **Client-portal reads** use raw SQL `text()` cross-module SELECTs in `client_portal/repository.py` (D-54-08 precedent). No ORM model imports from foreign modules.
- **IDOR discipline** (D-20-IDOR): `client_id` derived exclusively from `require_client()` principal, never from path/query/body. Non-owned resources → 404-collapse (anti-oracle). This must apply equally to WebSocket connections.
- **INFRA-15**: all new `LOCKED_AUDIT_EVENTS` entries pre-registered in the frozenset BEFORE any callsite.
- **Last confirmed migration revision**: around `0063` (Phase 88 trainer bio/photo). v2.5 starts at `0064_*`.
- **`unmatched_ignore_imports_alerting = warn`** (not `error`) so pre-registered edges for not-yet-shipped module bodies don't fail CI.

---

## Question 1: Where Does the WebSocket Endpoint Live?

### The Constraint

The WS endpoint needs:
1. Access to `app.modules.messaging` service (to persist messages, record read receipts, etc.)
2. Authentication via `ClientPrincipal` (`require_client()` logic)
3. Redis pub/sub subscriber loop (to receive fan-out events from other workers/requests)

The `modules-independent` contract forbids `messaging` from being imported into `client_portal` directly.

### The Answer: WS Endpoint Lives in `messaging/router.py`, Mounted at `/client` Prefix

**Why NOT `api layer` (e.g. `app/api/v1/_internal/`)**: The `_internal` prefix is reserved for transport-layer webhooks (email, YooKassa). The WS endpoint is a client-facing endpoint that authenticates with `require_client()` — it belongs under `/api/v1/client/`.

**Why NOT `client_portal/router.py`**: The messaging module owns its own data model (threads, messages, receipts, typing indicators). Putting the WS endpoint in `client_portal` would force either a direct `from app.modules.messaging import service` import (violates `modules-independent`), or routing everything through Protocol slots (excessive for a module that is specifically a messaging endpoint). The precedent for separate client-facing routers mounted at `/client` prefix is already established: `loyalty.router`, `gym.router`, `notifications.router`, and `client_auth.router` all mount at `/client` in `api/v1/router.py` (lines 95-131 of the router file).

**Correct pattern**: Create `app/modules/messaging/router.py` with a `router = APIRouter(tags=["Messaging"])`. Mount it in `app/api/v1/router.py` with prefix `/client`. The messaging module is its own bounded module, registered in `.importlinter`'s `modules-independent` contract.

### WS Auth: How `require_client()` Applies

FastAPI's `@app.websocket()` decorator accepts `Depends()` in the handler signature just like HTTP routes. However, there are two key constraints:
1. WebSockets carry cookies from the browser's cookie jar automatically — the `cc_client_access` httpOnly cookie is sent on WS handshake.
2. `require_client()` reads `request.cookies.get("cc_client_access")` — this works with `WebSocket` objects as well as `Request` objects because FastAPI's `WebSocket` also exposes `.cookies`.

**Auth flow for WS**:
```
WS GET /api/v1/client/ws/messages
  → Depends(require_client())  [reads cc_client_access cookie]
  → decode_client_token(token) [asserts aud="client"]
  → ClientLoader slot         [loads Client from DB]
  → returns ClientPrincipal
```

If the token is missing/expired, FastAPI raises `InvalidAccessToken` BEFORE the WS handshake completes (during the `Depends` resolution phase). This closes the connection with HTTP 401 (the upgrade never completes). The PWA handles this with a reconnect + redirect to login flow.

**CSRF**: WebSocket connections are not subject to CSRF because the browser cannot send `X-CSRF-Token` headers on the WS handshake. The httpOnly cookie already provides sufficient authentication for the origin-same-site channel. The WS endpoint does NOT add `verify_client_csrf` — this is standard and correct.

### Proposed WS Endpoint Signature

```python
# app/modules/messaging/router.py

@router.websocket("/ws/messages")
async def client_ws_messages(
    websocket: WebSocket,
    client: Annotated[ClientPrincipal, Depends(require_client())],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    # 1. Accept the WS connection
    await websocket.accept()
    # 2. Subscribe to Redis pub/sub channel for this client
    # 3. Start fan-out delivery loop (see Question 2)
```

URL: `GET /api/v1/client/ws/messages` (HTTP → WS upgrade). The mount in `api/v1/router.py`:

```python
from app.modules.messaging.router import router as messaging_router
v1.include_router(messaging_router, prefix="/client")
```

**Import-linter implication**: `app.modules.messaging` must be added to the `modules-independent` contract. The WS router imports `app.modules.messaging.service` directly (not via Protocol slot) because it IS the messaging module. No new `ignore_imports` edges needed — the module is self-contained.

### Dependency on messaging.service from messaging.router

Within the messaging module itself, `messaging/router.py` imports `messaging/service.py` — this is a same-module import, fully permitted. The messaging module does NOT import other modules directly. Cross-module reads (e.g. fetching client name for display) use raw SQL `text()` over the `clients` table (D-54-08 discipline). Cross-module writes (e.g. incrementing notification count in `notifications` module) use Protocol slots registered in `app.core.dependencies`.

---

## Question 2: Redis Pub/Sub Fan-Out — Who Owns the Subscriber Loop?

### The Problem

A message persisted in one HTTP worker (POST /client/messages) must reach a WebSocket connection held by a different uvicorn worker process. Redis pub/sub is the established backbone.

### Architecture: Lifespan Task + Per-Connection Subscriber

**Who publishes**: the HTTP handler `POST /client/messages` (in `messaging/service.py`), after persisting the message to Postgres, publishes to a Redis channel `cc:messaging:thread:{thread_id}` using `redis.publish()`. This is a fire-and-forget publish inside the same request handler after the DB commit.

**Who subscribes**: each WebSocket connection owns its own Redis pub/sub subscriber. FastAPI WS handlers are `async` coroutines. The correct pattern is:

```
For each WS connection:
  1. Subscribe to a per-client Redis channel: cc:messaging:client:{client_id}
  2. Run an async loop: await message from pub/sub → forward to websocket
  3. Simultaneously: receive messages from websocket → process → persist → publish
  4. On disconnect: unsubscribe
```

The loop is an asyncio task spawned inside the WS handler coroutine. No separate "subscriber worker" process is needed.

**Why not a global lifespan subscriber task**: A process-wide subscriber task would need to demultiplex connections across all clients — complex bookkeeping (`client_id → set[WebSocket]`), race conditions on connect/disconnect, harder to test. Per-connection subscribers are simpler, standard for FastAPI WS, and Redis pub/sub handles fan-out natively.

**Channel naming**:
- `cc:messaging:client:{client_id}` — per-client channel. The staff (Telegram bridge) publishes staff-→-client messages here. Multiple WS connections from the same client (multiple browser tabs) all subscribe to this channel and all receive the message (fan-out within a single client is free from Redis pub/sub).
- The HTTP handler for `POST /client/messages` publishes to this channel after DB commit so the WS loop delivers the persisted message to the client's WS connection even when posted from a different uvicorn worker.

**pub/sub is broadcast, not queue**: Redis pub/sub delivers to all current subscribers. If the client's WS is not connected, the message is not delivered (fire-and-forget). This is correct: the REST history endpoint (`GET /client/messages`) serves as the authoritative message source. The WS channel is a delivery optimization, not the source of truth.

**Implementation sketch** (inside the WS handler coroutine):

```python
async def client_ws_messages(
    websocket: WebSocket,
    client: Annotated[ClientPrincipal, Depends(require_client())],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await websocket.accept()
    channel = f"cc:messaging:client:{client.id}"
    
    # Need a separate Redis connection for pub/sub (blocking subscribe)
    # The request-scoped redis client is a shared pool — do NOT subscribe on it
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    
    async def _fan_out_loop() -> None:
        async for raw in pubsub.listen():
            if raw["type"] != "message":
                continue
            await websocket.send_text(raw["data"])
    
    fan_out_task = asyncio.create_task(_fan_out_loop())
    
    try:
        while True:
            data = await websocket.receive_text()
            # parse + persist + publish (via messaging.service)
            ...
    except WebSocketDisconnect:
        pass
    finally:
        fan_out_task.cancel()
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
```

**Critical nuance**: `redis.asyncio.Redis.pubsub()` creates a NEW internal connection for the pub/sub protocol. The `get_redis()` dependency returns the shared pool client — calling `.pubsub()` on it is safe and creates a dedicated connection for this subscriber. On WS disconnect, `await pubsub.aclose()` must be called to release the connection.

**App lifespan task ownership**: None required. The WS handler coroutine IS the subscriber task. No lifespan modifications needed. The `combined_lifespan` in `main.py` does not change for messaging.

---

## Question 3: Telegram Bridge — How Staff Replies Enter the Messaging Domain

### Bridge Architecture: Worker-to-Messaging via HandlerContext

The Telegram bot worker (`app/workers/telegram_bot.py`) already has a documented exception for importing module service layers (D-06, D-10). The messaging bridge follows the same pattern: the bot worker imports `app.modules.messaging.service` directly, adds it to `HandlerContext`, and calls it from handler functions.

### Data Flow: Staff Reply Path

```
Staff types reply in Telegram (bot DM or group message)
    ↓
telegram_bot.py long-polling receives update
    ↓
reply_handler(update, context, ctx)    # new handler in handlers.py
    ↓
ctx.messaging_service.record_staff_message(
    session_factory, thread_id, text=...
)   # persists to messages table
    ↓
messaging_service.record_staff_message()
    → INSERT into messages (role='staff', ...)
    → UPDATE thread.last_message_at
    → redis.publish(f"cc:messaging:client:{thread_id_owner}", json_payload)
    ↓
PWA WebSocket receives the published payload
    ↓
ChatScreen displays new staff message
```

### Data Flow: Client Message Path (staff receives it)

```
Client sends POST /client/messages
    ↓
messaging/service.send_client_message()
    → INSERT into messages (role='client', ...)
    → UPDATE thread.last_message_at
    → redis.publish("cc:messaging:staff", json_payload)
    ↓
ARQ task (or direct call): enqueue Telegram DM to staff
    ↓
Telegram bot (via integrations/telegram/sender.py):
    send_message(STAFF_TELEGRAM_CHAT_ID, text)
```

For the client→staff direction, the Telegram DM is a fire-and-forget notification (not a pub/sub subscriber loop). This reuses the existing `telegram_sender` pattern. The staff chat ID (owner's Telegram account) must be configurable via `Settings` (e.g. `STAFF_TELEGRAM_CHAT_ID`). This is an environment variable, not a per-client setting.

### HandlerContext Extension

New fields appended at END of `HandlerContext` NamedTuple (preserving field-order stability contract):

```python
class HandlerContext(NamedTuple):
    session_factory: async_sessionmaker[AsyncSession]
    telegram_service: ModuleType
    sender: ModuleType
    visits_service: ModuleType
    redis: Redis
    bookings_service: ModuleType
    schedule_service: ModuleType
    # NEW — appended at end per HandlerContext stability contract:
    messaging_service: ModuleType   # app.modules.messaging.service
```

The bot worker's `main()` function:
1. Imports `from app.modules.messaging import service as messaging_service` (new D-06-style relaxation documented as e.g. D-90-BRIDGE).
2. Adds `messaging_service=messaging_service` to the `HandlerContext` construction.
3. Registers a new PTB command/message handler for staff replies (or simply handles any non-command message DM from the staff account as a reply).

### Reply Threading: Matching Replies to Threads

The bridge must know WHICH client thread a staff reply belongs to. Three approaches:

**Option A (recommended)**: The bot DM to staff includes the `thread_id` (or `client_name + thread_id`) in the message text or as a custom keyboard button. When staff hits "Reply" in Telegram (standard telegram reply-to-message feature), the update carries `message.reply_to_message.message_id`. The bot persists a `telegram_message_id → thread_id` mapping in Redis (`cc:messaging:tg_msg:{tg_message_id}` → `thread_id` with TTL 7 days). When the reply arrives, lookup the thread_id from this mapping.

**Option B (simpler for single-gym v2.5)**: There is only ONE gym, so there is only one active staff member at a time. All staff replies go to the most recently active thread (LIFO). This is fragile if multiple clients write simultaneously — acceptable for MVP if the gym handles one conversation at a time, but breaks immediately with concurrent clients.

**Recommendation**: Option A. The `cc:messaging:tg_msg:{tg_message_id}` Redis key is set when the bot sends the DM to staff, and consumed when the reply arrives. TTL 7 days is sufficient (Telegram messages don't expire that fast). Zero new Postgres tables needed for this — Redis is the mapping store.

### Import-Linter: New Worker→Modules Edge

`app/workers/telegram_bot.py` already has documented exceptions for `auth.telegram_service`, `visits.service`, `bookings.service`, `schedule.service`, `clients.service`, `memberships.service`, `pt_packages.service`, `trainers.service`. Adding `messaging.service` follows the same precedent. No `.importlinter` change needed (workers are NOT in the `source_modules` of any contract — the worker module `app.workers` is not listed as a forbidden-source). The contracts only scope `app.core`, `app.integrations`, and the listed `app.modules.*`. Workers already import freely from modules with the documented exception acknowledgment.

**Verify**: `app.workers` is not listed in `source_modules` of any contract in `.importlinter`. The D-06/D-10 "relaxation" is documented in the module docstring but is NOT enforced by import-linter — it's a team convention. Adding `messaging.service` to the worker requires only updating the module docstring, not `.importlinter`.

---

## Question 4: Attachment Storage — Integrations vs. Module

### Attachment Requirements

- Client uploads an image in ChatScreen → it appears in the message thread
- Image stored server-side, served back via URL
- Content-type allowlist (JPEG, PNG, WebP only — stored-XSS guard)
- Max size cap (e.g. 5 MB)
- XSS-safe serving: correct `Content-Type` response header + `Content-Disposition: attachment` to prevent inline execution

### Where Attachments Live

**Option A — Local filesystem storage in an `integrations/storage/` module**: Simpler for a single-server pet project. Files stored in a volume-mounted directory (e.g. `/app/uploads/`). Served by FastAPI itself with `FileResponse`. Zero external dependencies.

**Option B — S3-compatible storage (e.g. Yandex Object Storage)**: Production-grade, separates storage from compute, enables CDN. Requires a new `app/integrations/object_storage/` adapter.

**Recommendation for v2.5**: Local filesystem storage in `app/integrations/storage/` (Option A). Rationale: this is a pet project on a single server; adding an S3 integration is a separate concern. The integration module provides a clean interface so swapping to S3 later is a 1-file change in `integrations/storage/`. The `messaging` module calls storage through this adapter — it never touches filesystem paths directly.

### Module Placement

`app/integrations/storage/` — NOT a module. Rationale:
- Attachment storage is infrastructure (like `integrations/email/`, `integrations/yookassa/`), not a business domain.
- The `integrations ⊥ modules` contract would be violated if `storage` imported from `messaging`. The dependency direction is correct: `messaging` → calls → `storage` (a downstream integration). But wait — `integrations ⊥ modules` forbids `integrations` from importing `modules`, not the reverse. `messaging` importing `integrations.storage` is fine (modules CAN import integrations — the contracts don't forbid it).

**Confirmed**: `messaging/service.py` can import `app.integrations.storage.save_file` — no import-linter violation. The forbidden direction is `integrations → modules`, not `modules → integrations`.

### Serving Attachments

Two patterns:
1. **Redirect to static URL**: FastAPI serves files via `StaticFiles` mount at `/static/uploads/`. The message `attachment_url` field contains a path like `/static/uploads/{uuid}.jpg`. Simple but exposes upload paths to enumeration.
2. **Authenticated proxy endpoint**: `GET /client/messages/attachments/{attachment_id}` — resolves to the file, checks that the attachment belongs to a thread owned by the requesting client (IDOR), then returns `FileResponse`. More secure; prevents unauthenticated access to uploaded images.

**Recommendation**: Authenticated proxy endpoint. Pattern: `GET /api/v1/client/messages/attachments/{attachment_id}` gated by `require_client()`. The repository layer verifies the attachment's thread `client_id == principal.client_id` before returning the file path. Return `FileResponse(path, media_type=detected_mime, headers={"Content-Disposition": "attachment"})`.

The `Content-Disposition: attachment` header prevents inline browser execution even if a malicious file slips past the type check. The `media_type` is set from the stored allowlisted MIME type (not re-detected from file contents at serve time — the allowlist check is at upload time).

### Upload Endpoint

`POST /api/v1/client/messages/attachments` — multipart form upload. FastAPI `UploadFile`. Returns `attachment_id` + `previewUrl`. The client then references this `attachment_id` in the subsequent `POST /client/messages` body.

Security checks at upload:
1. `UploadFile.content_type` must be in `{"image/jpeg", "image/png", "image/webp"}`.
2. File size: read at most `MAX_ATTACHMENT_BYTES` (5 MB) — reject if `size > limit`.
3. Magic bytes check: read first 12 bytes of the file and verify against known image magic bytes (JPEG: `FF D8 FF`, PNG: `89 50 4E 47`, WebP: `52 49 46 46 ... 57 45 42 50`). This prevents a renamed `.html` file with `Content-Type: image/jpeg` from being stored.
4. Save to disk with a UUID filename (no extension in storage — the MIME type is stored in the `message_attachments` DB row).

---

## Question 5: Dependency-Ordered Build Sequence

### Schema/Migration Decisions

**New tables** (order matters for FK constraints):

```
0064_messaging_threads.py
  — message_threads: id (UUID PK), client_id (FK clients.id), created_at, last_message_at

0065_messaging_messages.py
  — messages: id, thread_id (FK message_threads.id), role ('client'|'staff'),
    body TEXT, attachment_id UUID NULL, sent_at TIMESTAMPTZ,
    read_at TIMESTAMPTZ NULL (staff-reads; staff→client direction)
    INDEX (thread_id, sent_at DESC)

0066_messaging_attachments.py
  — message_attachments: id UUID PK, thread_id FK, client_id FK (IDOR),
    mime_type TEXT, file_path TEXT, size_bytes INT, created_at TIMESTAMPTZ
    (must come BEFORE messages to satisfy FK if attachment_id references this table,
     OR messages.attachment_id can be nullable with FK deferred — use separate table)

0067_messaging_unread.py
  — thread_unread_counts: thread_id FK (1:1), client_unread INT NOT NULL DEFAULT 0
    (maintained by triggers or application logic; tracks messages unread by client)
```

**Note on unread count**: a simpler alternative to a separate table is a GENERATED column or an application-maintained counter. The safest approach for v2.5 is an `INTEGER` column on `message_threads` (`client_unread_count DEFAULT 0`) — incremented by `INSERT INTO messages ... WHERE role='staff'` and reset to 0 by the client mark-read endpoint. This avoids a separate table. The counter is not race-prone at single-gym scale.

### REST Foundation Must Come Before WS

The WS endpoint delivers messages; the REST endpoints persist them. The WS endpoint calling `messaging/service` functions means those functions must exist first.

### Build Order (Phase Numbering Starts at Phase 90)

**Phase 90 — Messaging Schema + REST Send/List**
- Alembic migrations `0064_messaging_threads`, `0065_messaging_messages` (unified or split)
- `app/modules/messaging/` scaffold: `models.py` + `repository.py` + `service.py` + `router.py` + `schemas.py`
- REST endpoints only (NO WS yet):
  - `GET /client/messages` — paginated thread history + `unreadCount`
  - `POST /client/messages` — send text message (no attachments yet)
  - `PATCH /client/messages/read` — mark thread as read (reset `client_unread_count`)
- All under `require_client()` + `verify_client_csrf` on mutations
- IDOR: `thread_id` resolved from `client_id` (principal); 404-collapse on non-owned
- Audit events pre-registered: `("message_sent", "message")`, `("message_read", "message")`
- Register `app.modules.messaging` in `.importlinter` `modules-independent` contract
- Mount `messaging_router` at `/client` prefix in `api/v1/router.py`
- Tests: send message → appears in list; IDOR (other client's thread → 404); unread count increments on staff send, resets on client read
- **No pub/sub yet** — pure Postgres-backed REST

**Phase 91 — WebSocket Transport + Redis Fan-Out**
- WS endpoint `GET /api/v1/client/ws/messages` in `messaging/router.py`
- `require_client()` dependency on WS handshake
- Per-connection Redis pub/sub subscriber loop (see Question 2 above)
- `POST /client/messages` now publishes to `cc:messaging:client:{client_id}` after DB commit
- Message payload format over WS: JSON with `type: "new_message" | "typing" | "read_receipt"`
- PWA WS reconnect strategy: exponential backoff (1s → 2s → 4s → max 30s), reset on successful message receipt
- Tests: ASGI WS test client (`httpx.AsyncClient` does not support WS — use FastAPI's `TestClient` WS mode or `starlette.testclient.TestClient` WS context manager); verify message published via HTTP arrives on WS subscriber
- **Depends on Phase 90**

**Phase 92 — Read Receipts + Typing Indicators**
- Client sends `{"type": "read_receipt", "thread_id": "..."}` over WS → persisted to DB + published to staff pub/sub channel
- Client sends `{"type": "typing"}` over WS → published to pub/sub (NOT persisted to DB — ephemeral signal with 3s TTL)
- Staff-side typing indicator: not yet visible (staff side is Telegram which has its own typing indicator); client-side: if staff sends a typing event via Telegram bot, publish to `cc:messaging:client:{client_id}` with `type: "typing"` — PWA shows "зал набирает..."
- `PATCH /client/messages/read` REST endpoint also persists read state (for polling fallback when WS is disconnected)
- **Depends on Phase 91**

**Phase 93 — Attachments**
- `app/integrations/storage/` adapter (local filesystem, UUID filenames, magic-bytes check)
- Alembic `0066_messaging_attachments`
- `POST /api/v1/client/messages/attachments` — upload endpoint, returns `attachment_id`
- `GET /api/v1/client/messages/attachments/{attachment_id}` — authenticated proxy (IDOR-safe, `FileResponse`)
- `POST /client/messages` extended to accept optional `attachment_id`
- Size cap + content-type allowlist + magic-bytes check enforced at upload
- `Content-Disposition: attachment` on serve
- Tests: upload valid JPEG → GET returns file; upload oversized → 422; upload wrong type → 422; IDOR (another client's attachment → 404)
- **Depends on Phase 90** (schema); **independent from Phases 91-92** in terms of code, but migration numbering requires sequential order

**Phase 94 — Telegram Bridge (Staff-Side)**
- `app/modules/messaging/service.py`: add `record_staff_message(session_factory, thread_id, text)` function
- New handler in `app/integrations/telegram/handlers.py`: `reply_handler` — processes text messages from the staff Telegram account, resolves thread via `cc:messaging:tg_msg:{tg_message_id}` Redis mapping
- Extend `HandlerContext` NamedTuple: append `messaging_service` field at END
- `app/workers/telegram_bot.py`:
  - Import `app.modules.messaging.service as messaging_service` (D-90-BRIDGE documented exception)
  - Add `messaging_service=messaging_service` to `HandlerContext` construction
  - Register the reply handler on PTB application
- Client→Staff: `POST /client/messages` enqueues an ARQ task that sends a Telegram DM to staff (or calls `telegram_sender.send_message(STAFF_TELEGRAM_CHAT_ID, ...)` directly if fire-and-forget)
- Redis mapping: when bot sends DM to staff, store `cc:messaging:tg_msg:{sent_tg_msg_id}` → `{thread_id}` with TTL 7 days
- Settings: new `STAFF_TELEGRAM_CHAT_ID: int` in `app/core/config.py` (optional; Telegram bridge disabled if absent)
- Tests: record_staff_message writes to DB + publishes to pub/sub; reply_handler resolves thread from Redis key; client→staff DM fires (via mock); thread_id mapping round-trip
- **Depends on Phase 90 + Phase 91** (pub/sub publish in record_staff_message)

**Phase 95 — PWA ChatScreen Wiring + OpenAPI Handoff**
- Graduate ChatScreen from `D-71-09` placeholder zone (3 de-list spots + `@/data` import pattern — same lesson as v2.4 Phases 86/87/88)
- Wire `GET /client/messages`, `POST /client/messages`, WS endpoint
- Implement WS reconnect/backoff in PWA
- Byte-stable regen `openapi.json` + `schema.d.ts` + `_v25Checks` `AssertNonNever` forward-guards
- Staff-drift gate green (all staff paths byte-identical to `contract-freeze-v1.11.0`)
- Full milestone verification gate: backend pytest + mypy strict + lint-imports + redocly + CISO-01 guard
- **Depends on all prior phases**

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          apps/client-pwa (PWA)                          │
│  ChatScreen  →  HTTP REST (send/list)                                   │
│              →  WebSocket /api/v1/client/ws/messages (real-time)        │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ HTTP + WS upgrade (cc_client_access cookie)
┌──────────────────────────────────▼──────────────────────────────────────┐
│                   FastAPI app (uvicorn, async)                           │
│  api/v1/router.py  →  messaging/router.py  (prefix="/client")          │
│    REST: GET /client/messages                                            │
│          POST /client/messages                                           │
│          PATCH /client/messages/read                                     │
│          POST /client/messages/attachments                               │
│          GET  /client/messages/attachments/{id}                          │
│    WS:   GET /api/v1/client/ws/messages                                  │
│               ↓ Depends(require_client()) → ClientPrincipal             │
│               ↓ messaging/service.py (same-module import, OK)            │
│               ↓ per-connection pubsub subscriber loop                   │
└──────────────┬────────────────────────────────────────┬─────────────────┘
               │ write                                  │ pub/sub
               ▼                                        ▼
┌──────────────────────────┐         ┌──────────────────────────────────┐
│       Postgres 16        │         │         Redis 7 (existing)        │
│  message_threads         │         │  cc:messaging:client:{id}         │
│  messages                │         │  cc:messaging:tg_msg:{tg_id}      │
│  message_attachments     │         │  (pub/sub channels)               │
└──────────────────────────┘         └──────────────────┬───────────────┘
                                                        │ subscribe / publish
┌───────────────────────────────────────────────────────▼────────────────┐
│              app/workers/telegram_bot.py (long-polling)                 │
│  HandlerContext.messaging_service = app.modules.messaging.service       │
│  reply_handler:                                                          │
│    → read cc:messaging:tg_msg:{tg_msg_id} → thread_id                  │
│    → messaging_service.record_staff_message(thread_id, text)           │
│    → publishes to cc:messaging:client:{client_id}                       │
│  client→staff DM:                                                        │
│    → telegram_sender.send_message(STAFF_TELEGRAM_CHAT_ID, text)        │
│    → SET cc:messaging:tg_msg:{sent_msg_id} → thread_id (TTL 7d)        │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Component Boundaries and Responsibilities

| Component | Status | Responsibility |
|---|---|---|
| `app/modules/messaging/` | **NEW** | Thread + message domain model; REST read/write/receipts; WS endpoint; pub/sub publish |
| `app/modules/messaging/models.py` | **NEW** | `MessageThread`, `Message`, `MessageAttachment` ORM models |
| `app/modules/messaging/repository.py` | **NEW** | Raw SQL reads for cross-module data (client name from `clients` table); ORM writes for owned data |
| `app/modules/messaging/service.py` | **NEW** | `send_client_message`, `record_staff_message`, `mark_thread_read`, `get_thread_history` |
| `app/modules/messaging/router.py` | **NEW** | REST + WS endpoints; `require_client()` dependency; mounts in `api/v1/router.py` at `/client` |
| `app/modules/messaging/schemas.py` | **NEW** | `MessageResponse`, `SendMessageRequest`, `AttachmentResponse`, WS payload types |
| `app/integrations/storage/` | **NEW** | Local filesystem adapter: `save_file`, `get_file_path`, magic-bytes check, MIME allowlist |
| `app/integrations/telegram/handlers.py` | **MODIFIED** | Add `reply_handler`; `HandlerContext` NamedTuple gains `messaging_service` field appended at END |
| `app/workers/telegram_bot.py` | **MODIFIED** | Import `messaging.service`; add to `HandlerContext`; register reply handler on PTB application |
| `app/core/config.py` | **MODIFIED** | Add `STAFF_TELEGRAM_CHAT_ID: int | None` setting |
| `app/core/audit.py` `LOCKED_AUDIT_EVENTS` | **MODIFIED** | Pre-register `("message_sent", "message")`, `("message_read", "message")`, `("attachment_uploaded", "message")` |
| `app/api/v1/router.py` | **MODIFIED** | Mount `messaging_router` at prefix `/client` |
| `apps/backend/.importlinter` | **MODIFIED** | Add `app.modules.messaging` to `modules-independent` contract |
| Alembic migrations `0064–0066` | **NEW** | `message_threads`, `messages`, `message_attachments` tables |
| `apps/client-pwa/` ChatScreen | **MODIFIED** | Graduate from D-71-09 placeholder zone; wire REST + WS |
| `apps/backend/openapi.json` + `schema.d.ts` | **MODIFIED** | Byte-stable regen + `_v25Checks` forward-guards |

---

## Import-Linter: Required Changes

### `.importlinter` Changes

1. **Add `app.modules.messaging` to `modules-independent` contract** (in the `modules =` block).
   - The messaging module does NOT import other modules directly.
   - Cross-module reads (e.g. `clients.first_name` for display): raw SQL `text()` in `messaging/repository.py` (D-54-08 discipline — zero new `ignore_imports`).
   - Cross-module writes: if messaging needs to trigger a notification (e.g. increment `in_app_notifications` unread count when a staff message arrives), this goes through a Protocol slot. Add `register_messaging_notification_hook` to `app.core.dependencies`, wired in `main.py`. OR: keep it simple for v2.5 — no cross-module notification write; the `client_unread_count` on the thread itself is the unread signal.

2. **No new `ignore_imports` edges expected for Phase 90 (REST foundation)**. The messaging module is self-contained. The WS endpoint is inside the messaging module, not in `client_portal` — so no `client_portal → messaging` cross-module edge is needed.

3. **If in-app notifications need to be triggered by messaging** (e.g. push notification when staff sends a message while PWA is closed): this is a Phase-87-style cross-module edge: `app.modules.messaging.service → app.modules.notifications.service`. This follows the Phase-87 `bookings.service → notifications.service` precedent (already in `.importlinter` `ignore_imports`). Declare the `ignore_imports` edge when the feature is built — not preemptively.

### Worker Module (No Import-Linter Change Needed)

`app/workers/telegram_bot.py` is NOT listed as a `source_modules` in any import-linter contract. The contracts scope `app.core`, `app.integrations`, and `app.modules.*`. Workers can import modules freely (with team-convention D-06/D-10 acknowledgment in the module docstring). No `.importlinter` edit required for the bridge.

---

## IDOR and Principal Discipline for WS

The WebSocket endpoint must enforce the same IDOR discipline as all REST endpoints:

1. `client_id` is taken ONLY from `require_client()` principal (the `ClientPrincipal` from the cookie-decoded JWT). Never from a WS message payload.
2. The WS subscriber channel is `cc:messaging:client:{client_id}` — keyed to the principal's `client_id`. A client cannot subscribe to another client's channel.
3. When the client sends a message over WS, the `client_id` is injected from the principal — the PWA payload does not include `client_id`.
4. Staff messages arriving via Telegram bridge carry NO client-supplied `client_id` — the thread_id lookup via the Telegram message reply chain is the only source.
5. The attachment proxy endpoint `GET /client/messages/attachments/{attachment_id}` verifies `message_attachments.client_id == principal.client_id` before returning the file.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: WS Endpoint in `client_portal/router.py`

**What people do**: add the WS endpoint to `client_portal/router.py` because "it's a client endpoint."
**Why it's wrong**: forces `client_portal` to import `messaging.service` directly (violates `modules-independent`) or route everything through Protocol slots (overkill for a module that owns its own data model).
**Do this instead**: the WS endpoint lives in `messaging/router.py`, mounted at `/client` prefix in `api/v1/router.py` — the same pattern as `loyalty.router`, `gym.router`, `notifications.router`.

### Anti-Pattern 2: Global Process-Wide Pub/Sub Subscriber in Lifespan

**What people do**: create a single asyncio task in `combined_lifespan` that subscribes to all channels and dispatches to a `client_id → WebSocket` dict.
**Why it's wrong**: requires thread-safe global state; hard to clean up on disconnect; harder to test; fanout to multiple tabs from a single subscriber requires extra demultiplex logic.
**Do this instead**: per-WS-connection subscriber loop (each WS handler spawns its own asyncio task that subscribes and unsubscribes cleanly on disconnect).

### Anti-Pattern 3: Pub/Sub on the Shared `get_redis()` Pool Client

**What people do**: call `redis.subscribe()` on the same `Redis` object returned by `get_redis()`.
**Why it's wrong**: `redis.asyncio` pub/sub puts the connection into subscribe mode — it can no longer be used for regular commands. The shared pool client would be corrupted for other requests.
**Do this instead**: call `redis.pubsub()` which creates a dedicated internal connection for subscribe protocol. Dispose of it with `await pubsub.aclose()` on WS disconnect.

### Anti-Pattern 4: Storing Typing Indicators in Postgres

**What people do**: INSERT a row into a `typing_events` table on every keystroke.
**Why it's wrong**: typing indicators are ephemeral (3-5s TTL); persisting them is noise that never needs to be read back.
**Do this instead**: publish typing events to Redis pub/sub only (not to Postgres). The WS fan-out delivers them in real time; they are not persisted.

### Anti-Pattern 5: Accepting `thread_id` or `client_id` from WS Payload

**What people do**: let the client send `{"type": "send", "thread_id": "...", "client_id": "..."}` in WS messages.
**Why it's wrong**: breaks IDOR — a client could specify another client's `thread_id` or forge `client_id`.
**Do this instead**: `client_id` and `thread_id` are resolved server-side from the principal (`ClientPrincipal.id`) at WS handshake time. The client never sends ownership identifiers.

### Anti-Pattern 6: Serving Attachments via Static Mount Without Auth

**What people do**: `app.mount("/uploads", StaticFiles(directory="uploads"))` and put the URL in the message.
**Why it's wrong**: uploaded files are accessible to anyone with the URL — no auth, no IDOR check.
**Do this instead**: authenticated proxy endpoint `GET /client/messages/attachments/{id}` that verifies `message_attachments.client_id == principal.client_id` before `FileResponse`.

---

## Scaling Considerations (Single Gym — v2.5 Scope)

| Concern | At 1 gym (v2.5 target) |
|---|---|
| Concurrent WS connections | 1-50 (one gym, few active clients) — no scaling concern |
| Redis pub/sub | Single-node Redis 7 — adequate; fan-out is trivial at this scale |
| Attachment storage | Local filesystem — adequate; single server deployment |
| DB writes per message | 1 INSERT + 1 UPDATE (thread.last_message_at) — trivial |

If this were to scale to multiple gyms (v3.x), the Redis pub/sub channel namespace `cc:messaging:client:{id}` already isolates by client, so horizontal scaling of the FastAPI process is straightforward (all workers subscribe to the same Redis node). Local filesystem storage would need to become shared (NFS or S3) — the `integrations/storage/` adapter makes this a single-file swap.

---

## Sources

All findings are HIGH confidence from direct live codebase inspection:

- `apps/backend/app/main.py` — composition root: Protocol slot registration pattern, lifespan structure, composition-root carve-out precedents
- `apps/backend/app/workers/telegram_bot.py` — HandlerContext pattern, D-06/D-10 relaxations, long-polling process lifecycle, Protocol slot registration in worker
- `apps/backend/app/integrations/telegram/handlers.py` — HandlerContext NamedTuple definition, field order stability contract, importlib pattern for integrations → modules isolation
- `apps/backend/app/modules/client_portal/router.py` — require_client() usage, IDOR enforcement, WebSocket dependency pattern (confirmed FastAPI applies Depends on WS routes)
- `apps/backend/app/core/dependencies.py` — ClientPrincipal Protocol, require_client() implementation reading cc_client_access cookie, Protocol slot registration pattern
- `apps/backend/app/core/redis.py` — Redis singleton pattern, get_redis() per-request dependency, redis.pubsub() availability on asyncio Redis client
- `apps/backend/app/core/security.py` — decode_client_token(), aud="client" assertion, cc_client_access cookie name
- `apps/backend/app/api/v1/router.py` — established pattern of mounting multiple separate routers at `/client` prefix (loyalty, gym, notifications, client_auth, client_portal)
- `apps/backend/.importlinter` — exact contract text, existing ignore_imports edges, modules-independent module list, worker exemption (workers not in source_modules)
- `.planning/PROJECT.md` — v2.5 milestone goal, target features, key constraints, out-of-scope items

---
*Architecture research for: clubcore v2.5 — Chat / Messaging — Client↔Gym*
*Researched: 2026-06-06*
