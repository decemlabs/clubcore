# Stack Research

**Domain:** Gym CRM — v2.5 Chat / Messaging (real-time 1:1 WebSocket messaging + Redis pub/sub fan-out + photo attachments + Telegram bridge)
**Researched:** 2026-06-06
**Confidence:** HIGH for WebSocket + Redis pub/sub (FastAPI native pattern, well-documented); HIGH for WS auth (query-param JWT, established pattern); HIGH for Telegram bridge (existing PTB 22.7 codebase, MessageHandler patterns confirmed); MEDIUM for attachment storage (Yandex Object Storage vs local volume — ops decision depends on deployment target; both are S3-compatible via aioboto3 already in stack); LOW for httpx-ws version compat (latest 0.9.0 released 2026-03-28, not yet tested in this project)

---

## Executive Summary

v2.5 is the heaviest new-surface milestone in the project. Four genuinely new technical areas:

1. **FastAPI native WebSocket** — zero new framework; Starlette's `WebSocket` class is already part of FastAPI 0.115+. Redis pub/sub fan-out uses the `redis` library (already in `pyproject.toml` at `>=5,<6`) via an async subscribe loop. No new broker dependency.

2. **WS authentication** — query-param JWT is the pragmatic choice for browser WebSocket clients (browsers cannot set `Authorization` headers on WS handshake). The existing `require_client()` / `ClientPrincipal` / PyJWT stack covers this exactly; the only addition is a WS-specific dependency that reads `token` from the query string instead of a cookie.

3. **Photo attachment storage** — `aioboto3` is already in `pyproject.toml` (`>=13.0,<14`) for the Yandex Postbox SES email adapter. The same session pattern covers S3-compatible object storage (Yandex Object Storage endpoint `storage.yandexcloud.net`, region `ru-central1`). For local dev, a self-hosted S3-compatible backend replaces MinIO (which was archived in February 2026). Content-type validation needs one new pure-Python library: `filetype` 1.2.0 (magic-bytes, no C extension, no libmagic dependency).

4. **Telegram bridge** — the existing `python-telegram-bot` 22.7 long-polling worker is extended with a `MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, ...)`. Staff DM → client thread routing uses a Redis key (`cc:chat:tg_to_client:{staff_tg_user_id}` or a thread-id lookup table) to map the Telegram staff user's `chat_id` to the open `messaging_thread_id`. No new Telegram library; the existing `application.add_handler` pattern applies directly.

**PWA side:** A small reconnect-capable WebSocket hook using native browser `WebSocket` + a custom hook (no library needed for a single-endpoint chat; `react-use-websocket` is available as optional if hook complexity grows). Incoming WS events call `queryClient.invalidateQueries` on the messages key to pull fresh data — no separate WS state store.

**Zero heavyweight additions:** No Django Channels, no Socket.IO, no Celery, no separate message broker. Redis 7 already in stack handles pub/sub. FastAPI native WS handles the transport.

---

## New Stack Additions (what changes from v2.4)

### Backend — New Python Packages

| Package | Version to add | Purpose | Why This, Not Alternative |
|---------|---------------|---------|--------------------------|
| `filetype` | `>=1.2.0,<2` | Magic-byte image MIME validation (JPEG/PNG/WebP allowlist) | Pure Python, no C extension, no libmagic system dep — installable in any container without apt-get. `python-magic` requires `libmagic` shared lib which complicates Docker builds. `puremagic` also pure-Python but has a larger footprint; `filetype` is 50 lines for image detection which is all needed here. |
| `httpx-ws` | `>=0.9.0,<1` | WebSocket testing via ASGI transport (dev/test only) | Starlette's `TestClient.websocket_connect` is sync-only; `httpx-ws` provides `AsyncWebSocketSession` + `ASGIWebSocketTransport` compatible with `pytest-asyncio` + `httpx.AsyncClient` already in the test suite. Latest: 0.9.0 (2026-03-28). |

**No new packages for:** WebSocket transport (FastAPI/Starlette native), Redis pub/sub (existing `redis>=5` client has async pub/sub), Telegram bridge (existing `python-telegram-bot>=22.7`), S3 uploads (existing `aioboto3>=13`).

### Frontend — New npm Packages

| Package | Version | Purpose | Why |
|---------|---------|---------|-----|
| `react-use-websocket` | `>=4.x` | Optional: managed WS hook with reconnect backoff | If the inline custom WS hook in `ChatScreen.jsx` becomes complex (connection lifecycle, queue-on-close, exponential backoff). Not mandatory — native `WebSocket` with a `useEffect` hook is sufficient for MVP and avoids a dependency. Add only if the custom hook exceeds ~60 lines. |

**MVP recommendation:** Start with a native `useEffect`-managed `WebSocket` hook in `ChatScreen.jsx`. The reconnect pattern (1s → 2s → 4s → cap 30s with jitter) is ~40 lines of TypeScript. Add `react-use-websocket` only if the implementation grows unwieldy.

### Infrastructure — Dev Environment

| Service | Image | Purpose | Notes |
|---------|-------|---------|-------|
| SeaweedFS or Garage | `chrislusf/seaweedfs` or `dxflrs/garage` | S3-compatible local dev object storage | **MinIO Community Edition is archived (Feb 2026, read-only, no security patches).** SeaweedFS is the most production-mature OSS alternative (Apache 2.0, Go, 12+ years). Garage is Rust-based, lighter, designed for self-hosted. For local dev only — prod uses Yandex Object Storage. Either exposes S3 API, so aioboto3 config is endpoint_url + bucket only. |

---

## Existing Stack (no changes — confirmed reuse)

| Technology | Existing Version | Role in v2.5 |
|------------|-----------------|-------------|
| FastAPI | 0.115+ | Native `WebSocket` class + `WebSocketDisconnect` exception |
| Starlette | (bundled with FastAPI) | `WebSocket.accept()`, `.receive_text()`, `.send_text()` |
| SQLAlchemy 2.0 async | 2.0 | `messages`, `message_threads` ORM models; raw-SQL reads in `messaging/repository.py` |
| Alembic async | current | New migrations 0064+ for `message_threads`, `messages` tables |
| Pydantic v2 | 2.11+ | WS message envelope schemas (inbound events + outbound payloads) |
| redis | >=5,<6 | Pub/sub backbone: `await client.publish(channel, payload)` + `pubsub.subscribe()` async listen loop |
| python-telegram-bot | 22.7 | Extend existing long-polling worker with `MessageHandler` for staff DM → thread routing |
| aioboto3 | >=13,<14 (in pyproject.toml) | S3 presigned PUT (client upload) + presigned GET (client download) for photo attachments |
| PyJWT | 2.12.1+ | WS auth — decode `token` query param using existing `aud:"client"` validation logic |
| structlog | 24.0+ | WS connection/disconnection events, pub/sub errors |
| Postgres 16 | 16 | Persist messages, threads, read receipts; `JSONB` for typing events optional |
| ARQ | 0.26+ | Existing job queue — no new tasks for v2.5 core; photo virus-scan deferred |
| httpx | 0.27+ | Not needed for WS; continues to serve YooKassa adapter |

---

## Architecture: WebSocket + Redis Pub/Sub

### Single-process dev (uvicorn with 1 worker)

In-process `ConnectionManager` dict: `client_id → WebSocket`. No Redis pub/sub needed. Messages from the Telegram bridge (which runs in a separate process) reach the API via Redis.

```python
# app/modules/messaging/ws_manager.py
class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, client_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections[client_id] = ws

    async def disconnect(self, client_id: str) -> None:
        self._connections.pop(client_id, None)

    async def send(self, client_id: str, payload: str) -> None:
        ws = self._connections.get(client_id)
        if ws:
            await ws.send_text(payload)
```

### Multi-worker prod (uvicorn with N workers)

Each worker has its own `ConnectionManager`. Worker A may hold the WS for client X; worker B handles the incoming message POST from the Telegram bridge. Fan-out via Redis pub/sub:

```
Telegram bridge writes message → publishes to Redis channel cc:chat:thread:{thread_id}
All API workers subscribe → each checks local ConnectionManager → delivers to connected client
```

The subscriber loop runs as a background task started in the `lifespan`. Pattern:

```python
# Pseudocode — actual implementation in messaging/pubsub.py
async def _subscribe_loop(redis: Redis, manager: ConnectionManager) -> None:
    async with redis.pubsub() as pubsub:
        await pubsub.subscribe("cc:chat:*")  # pattern subscribe
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                data = json.loads(message["data"])
                await manager.send(data["client_id"], json.dumps(data["payload"]))
```

**Key constraint:** The subscriber loop is a long-lived asyncio task. It must be started in the `combined_lifespan` and cancelled on shutdown — same pattern as the ARQ pool (`app.state.arq_pool`).

---

## WS Authentication: Query-Param JWT

**Pattern chosen:** `wss://host/api/v1/client/ws/chat?token=<jwt_access_token>`

**Why query-param, not cookie or subprotocol:**
- Browsers cannot set `Authorization` headers or custom headers on WebSocket handshake. Cookies ARE sent automatically on same-origin WS, but the client PWA's JWT auth uses `cc_client_access` httpOnly cookie — reading httpOnly cookies from JavaScript is impossible by design, making the cookie approach require a separate non-httpOnly WS token.
- The subprotocol hack (`Sec-WebSocket-Protocol` header carrying the base64 token) works but adds complexity in both client and server parsing with no security advantage over query-param.
- **Query-param is the pragmatic standard** for browser WS auth with short-lived JWTs. The token is the existing `aud:"client"` JWT (60-minute expiry). The WS connection lifetime is bounded (client navigates away → browser closes WS). Log scrubbing at the structlog level avoids token leakage into server logs.

**Implementation:**

```python
@router.websocket("/ws/chat")
async def chat_ws(
    websocket: WebSocket,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> None:
    try:
        principal = await verify_client_ws_token(token, db)  # reuses PyJWT + ClientPrincipal logic
    except AuthError:
        await websocket.close(code=1008)  # Policy Violation — standard code for auth failure
        return
    await manager.connect(principal.client_id, websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            # handle typing events, read receipts (lightweight; messages go via HTTP POST)
    except WebSocketDisconnect:
        await manager.disconnect(principal.client_id)
```

**Security notes:**
- Token is validated on connect only. If the token expires mid-session, the WS remains open (acceptable for 60-minute JWT; client re-connects on next page load).
- WS endpoint does NOT accept message sends (client sends messages via `POST /client/messages` — keeps idempotency + audit trail intact). WS is receive-only from the server's perspective for message delivery; client sends small event frames (typing indicators, read receipts).
- `wss://` enforced in production (COOKIE_SECURE gate equivalent for WS).

---

## Telegram Bridge Routing

### Existing bot worker (confirmed from `apps/backend/app/workers/telegram_bot.py`)

Library: `python-telegram-bot` 22.7 (confirmed from `telegram.ext import CallbackQueryHandler` import + pyproject.toml `>=22.7,<23`).

Long-polling, separate process: `python -m app.workers.telegram_bot`. The worker opens its own DB + Redis pools (existing `db_lifespan_manager()` + `redis_lifespan_manager()` pattern).

### New handler: staff DM → thread routing

```python
# In app/workers/telegram_bot.py — add after existing handlers
application.add_handler(
    MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND,
        staff_reply_handler,
    )
)
```

**Routing lookup:** When a staff member sends a DM reply, the bot receives `update.message.from_user.id` (staff Telegram user ID) and `update.message.text`. To know WHICH client thread to route this reply to, a Redis lookup key stores the mapping:

```
cc:chat:active_thread:{staff_tg_user_id} → {thread_id, client_id}  TTL: 24h
```

This key is written when a client sends a message (client → staff DM triggers, sets the key). When staff replies, the handler reads this key to resolve the thread, writes the message to the `messages` table, and publishes to `cc:chat:thread:{thread_id}` for WS fan-out.

**Limitation acknowledged (MEDIUM confidence):** If a staff member receives DMs from multiple clients simultaneously, only the last active thread is tracked per staff user. For a single-gym pet project this is acceptable — only one owner/receptionist responds at a time. Multi-staff routing is a v2.6+ concern.

**Client → staff DM:** When a client sends `POST /client/messages`, the API:
1. Writes the message to the DB.
2. Publishes to Redis channel for WS fan-out (client's own connection gets immediate echo).
3. Calls `bot.send_message(chat_id=STAFF_TELEGRAM_GROUP_OR_DM_ID, text=...)` — the staff_chat_id is a server-side config constant (`STAFF_TELEGRAM_CHAT_ID` env var), not client-controlled (IDOR-safe).
4. Sets `cc:chat:active_thread:{STAFF_TG_USER_ID}` → `{thread_id, client_id}` in Redis.

The bot's `send_message` call from the API process uses the `_otp_bot` pattern already established in `app/main.py` (a bare `Bot` instance for outbound-only DMs, not the full `Application` long-polling instance).

---

## Photo Attachment Storage

### Storage architecture

**Chosen approach:** S3-compatible object storage via `aioboto3` (already in stack). The API handles:
1. Client requests a presigned PUT URL via `POST /client/messages/upload-url`.
2. Client uploads directly to the bucket (bypassing the API server — no streaming through Python).
3. Client sends `POST /client/messages` with `attachment_key` (the S3 object key, not the full URL).
4. API stores the object key; when serving message history, generates a short-lived presigned GET URL.

**Why presigned URLs, not API proxy:**
- Avoids streaming binary through the FastAPI process (memory + CPU overhead).
- Single-process and multi-worker behave identically (no in-memory upload state).
- Consistent with how modern backend-for-frontend patterns work (PWA → S3 directly).

### Environments

| Environment | Storage Backend | Config |
|-------------|----------------|--------|
| Local dev | SeaweedFS (Docker) — or skip storage, use local filesystem fallback | `AWS_ENDPOINT_URL=http://localhost:8333`, `S3_BUCKET=clubcore-dev` |
| Production | Yandex Object Storage | `AWS_ENDPOINT_URL=https://storage.yandexcloud.net`, region `ru-central1`, `S3_BUCKET=clubcore-prod` |

Yandex Object Storage is confirmed S3-compatible with `boto3`/`aioboto3` via `endpoint_url + region_name='ru-central1' + signature_version='s3v4'`. Presigned URLs confirmed working (official Yandex docs).

**aioboto3 presigned URL pattern (async-safe):**

```python
async def generate_upload_url(key: str) -> str:
    async with aioboto3.Session().client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        region_name="ru-central1",
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    ) as s3:
        # Note: generate_presigned_url is synchronous in aiobotocore — use run_in_executor
        # or use the aiobotocore async variant (aioboto3 >=13 wraps this correctly)
        url = await s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": settings.s3_bucket, "Key": key, "ContentType": "image/jpeg"},
            ExpiresIn=300,
        )
    return url
```

**Note on aioboto3 version:** The existing `pyproject.toml` pins `aioboto3>=13.0,<14`. Current latest is 15.5.0 (Oct 2025). The `<14` upper bound will need relaxing if the project moves to Python 3.13 or needs newer aiobotocore features, but for v2.5 the existing constraint is fine.

### Content-type validation (magic bytes)

```python
import filetype

ALLOWED_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

async def validate_attachment(data: bytes) -> str:
    if len(data) > MAX_SIZE_BYTES:
        raise ValidationError("attachment_too_large")
    kind = filetype.guess(data)
    if kind is None or kind.mime not in ALLOWED_MIME_TYPES:
        raise ValidationError("attachment_type_not_allowed")
    return kind.mime
```

`filetype` reads only the first 261 bytes (magic numbers). Only call `validate_attachment` on the first chunk or the full buffer if the client streams the upload through the API. For the presigned-URL pattern, validation happens on `POST /client/messages` when the client submits `attachment_key` — the API fetches the object header (`HeadObject`) and validates `ContentType` stored by Yandex Object Storage from the original PUT.

**Note on `filetype` maintenance:** The library is at version 1.2.0, last released ~2023. It is lightweight and the magic bytes for JPEG/PNG/WebP are stable. MEDIUM confidence on long-term maintenance — if this becomes a concern, `puremagic` (actively maintained, pure Python) is a drop-in alternative.

---

## PWA WebSocket Client

### Recommended approach: custom hook (no new dependency for MVP)

The PWA uses React 19 + TanStack Query 5 + Vite 6 (no TypeScript strict in client-pwa — it uses JSX with `allowJs`). The pattern for WS integration with TanStack Query is:

1. WS delivers event frames (new message notification, typing indicator, read receipt update).
2. On receiving a `message_new` event, call `queryClient.invalidateQueries({ queryKey: messagesKeys.thread(threadId) })`.
3. TanStack Query refetches the thread via `GET /client/messages` (existing HTTP endpoint).
4. WS does NOT carry the full message payload — only event type + IDs. This keeps WS messages small and avoids a parallel data store.

```javascript
// apps/client-pwa/src/hooks/useChatSocket.js
import { useEffect, useRef, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { messagesKeys } from '@/data/messages'

export function useChatSocket({ token, threadId }) {
  const queryClient = useQueryClient()
  const wsRef = useRef(null)
  const retryDelay = useRef(1000)

  const connect = useCallback(() => {
    const url = `${import.meta.env.VITE_WS_BASE_URL}/api/v1/client/ws/chat?token=${token}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      if (msg.type === 'message_new' || msg.type === 'read_receipt') {
        queryClient.invalidateQueries({ queryKey: messagesKeys.thread(threadId) })
      }
    }

    ws.onclose = () => {
      const delay = Math.min(retryDelay.current, 30_000)
      retryDelay.current = delay * 2 + Math.random() * 500  // jitter
      setTimeout(connect, delay)
    }

    ws.onopen = () => { retryDelay.current = 1000 }  // reset on successful connect
  }, [token, threadId, queryClient])

  useEffect(() => {
    connect()
    return () => { wsRef.current?.close() }
  }, [connect])
}
```

**If hook complexity grows:** Add `react-use-websocket` (maintained, TypeScript-first, built-in exponential backoff). Do NOT add `reconnecting-websocket` (npm package) — last published in 2019, unmaintained. Do NOT add Socket.IO client — incompatible with FastAPI native WS without Socket.IO server adapter.

### Token sourcing for WS

The JWT access token is in an httpOnly cookie — not readable from JavaScript. Two options:

1. **Dedicated WS token endpoint:** `POST /client/ws-token` returns a short-lived (5 min) token whose only claim is WS auth. Avoids exposing the main JWT. Adds one round trip on chat open.
2. **Re-use the OTP flow token pattern:** The client PWA already has access to a `clientToken` in React state (set after OTP verify). Pass this as the WS query param.

**Recommendation:** Option 2 for MVP. The `clientToken` is available in the React session context (set at login). The JWT is short-lived (60 min). Token rotation happens on re-login. For production hardening, upgrade to option 1 (dedicated WS token) in v3.0.

---

## Installation (new packages only)

```bash
# Backend (add to pyproject.toml dependencies)
uv add "filetype>=1.2.0,<2"

# Backend dev only (add to [dependency-groups] dev)
uv add --dev "httpx-ws>=0.9.0,<1"

# Frontend (add only if custom hook grows unwieldy)
pnpm --filter @clubcore/client-pwa add react-use-websocket
```

---

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Django Channels | Requires Django ORM + separate ASGI layer + channel layers — complete framework swap for a single feature | FastAPI native `WebSocket` (Starlette) + Redis pub/sub |
| Socket.IO (server + client) | Requires `python-socketio` on server; `socket.io-client` on PWA; custom protocol incompatible with native browser `WebSocket`. Adds ~120 kB to PWA bundle. | Native browser `WebSocket` API |
| `fastapi-websocket-pubsub` | Adds opinionated pub/sub abstraction over WS, not over Redis — does not solve the multi-worker fan-out problem. Unmaintained (last release 2022). | Direct `redis.pubsub()` async subscribe loop |
| Celery | Heavy broker-based task queue — ARQ already handles background tasks. Adding Celery for WS fan-out is massive overkill. | Existing ARQ + Redis pub/sub |
| NATS / RabbitMQ | Additional broker infra — Redis 7 is already running and has pub/sub. | `redis.pubsub()` |
| MinIO Community Edition | GitHub repo archived February 2026, read-only, no security patches. | SeaweedFS (`chrislusf/seaweedfs`) or Garage (`dxflrs/garage`) for local dev; Yandex Object Storage for prod |
| `python-magic` | Requires `libmagic` system library — complicates Docker build, not portable. | `filetype` (pure Python) |
| `aioyookassa` community library | Unvetted; existing httpx adapter pattern is sufficient. | Existing `YooKassaClient` |
| `reconnecting-websocket` npm | Last published 2019, unmaintained. | Custom hook or `react-use-websocket` |
| Separate WS auth middleware | FastAPI's `Depends()` works inside `@router.websocket()` — no custom middleware needed. | `token: str = Query(...)` + existing PyJWT validation |
| `anyio` for WS background tasks | `asyncio.create_task()` is sufficient for the pub/sub subscriber loop within the lifespan context. | `asyncio.create_task()` wrapped in lifespan |

---

## Alternatives Considered

| Decision | Recommended | Alternative | Why Alternative Rejected |
|----------|-------------|-------------|--------------------------|
| WS auth | Query-param JWT | Cookie (httpOnly) | httpOnly cookies not readable from JS; cannot inject into WS URL |
| WS auth | Query-param JWT | Subprotocol header hack | Same security profile, more parsing complexity, non-standard |
| WS auth | Query-param JWT | First-message auth | Connection is accepted before auth — allows unauthenticated clients to hold connections briefly; complicates rate limiting |
| Fan-out | Redis pub/sub | In-process broadcast | Fails across multiple uvicorn workers in production |
| Fan-out | Redis pub/sub | Server-Sent Events (SSE) | One-directional; cannot carry typing events from client; separate endpoint needed for client sends anyway |
| Storage | Presigned URLs (S3) | API proxy upload | Streams binary through Python process; memory + CPU pressure; no benefit for this scale |
| Storage | Yandex Object Storage (prod) | AWS S3 | Geo-blocked risk for RU region (political environment); Yandex Object Storage is S3-compatible, RU-domiciled |
| Storage | SeaweedFS (local dev) | MinIO | MinIO Community archived Feb 2026; SeaweedFS Apache 2.0, actively maintained |
| Content-type validation | `filetype` magic bytes | Client Content-Type header | Client header is trivially spoofable; magic bytes are ground truth |
| Telegram bridge routing | Redis key per staff user | DB table lookup | Redis lookup is O(1), avoids a DB read on every staff DM reply; data is ephemeral (TTL 24h) |
| PWA WS client | Custom hook | `react-use-websocket` | Custom hook is ~40 lines for this use case; avoids a dependency; `react-use-websocket` available as upgrade path |

---

## Version Compatibility

| Package | Pinned Constraint | Notes |
|---------|------------------|-------|
| `python-telegram-bot` | `>=22.7,<23` (existing) | v22.7 is current latest; `filters.ChatType.PRIVATE` confirmed available in v22+ |
| `redis` | `>=5,<6` (existing) | Async pub/sub via `redis.asyncio` works in v5+; `aio-pika` pattern NOT needed |
| `aioboto3` | `>=13.0,<14` (existing) | Presigned URL async support confirmed in v13+; upper bound `<14` is conservative — v15.5.0 is current, but constraint works for v2.5 |
| `filetype` | `>=1.2.0,<2` (new) | 1.2.0 is current; no major version churn expected (magic bytes are stable) |
| `httpx-ws` | `>=0.9.0,<1` (new, dev only) | 0.9.0 released 2026-03-28; `ASGIWebSocketTransport` API stable since 0.7.x |
| `fastapi` | `>=0.115` (existing) | `WebSocket`, `WebSocketDisconnect`, `WebSocketException` all stable since 0.100+ |

---

## Sources

- FastAPI docs: WebSocket with Dependencies — [https://fastapi.tiangolo.com/advanced/websockets/](https://fastapi.tiangolo.com/advanced/websockets/) — Cookie/Header/Query deps in WS confirmed (HIGH)
- Redis pub/sub fan-out pattern — [https://medium.com/@nandagopal05/scaling-websockets-with-pub-sub-using-python-redis-fastapi-b16392ffe291](https://medium.com/@nandagopal05/scaling-websockets-with-pub-sub-using-python-redis-fastapi-b16392ffe291) — multi-worker fan-out architecture (MEDIUM, community article, pattern is sound)
- httpx-ws PyPI — [https://pypi.org/project/httpx-ws/](https://pypi.org/project/httpx-ws/) — v0.9.0 (2026-03-28) confirmed, `ASGIWebSocketTransport` (MEDIUM)
- python-telegram-bot v22.7 filters — [https://docs.python-telegram-bot.org/en/stable/telegram.ext.filters.html](https://docs.python-telegram-bot.org/en/stable/telegram.ext.filters.html) — `filters.ChatType.PRIVATE` confirmed (HIGH)
- filetype PyPI — [https://pypi.org/project/filetype/](https://pypi.org/project/filetype/) — v1.2.0, pure Python, no C extension (HIGH)
- Yandex Object Storage presigned URLs — [https://yandex.cloud/en/docs/storage/concepts/pre-signed-urls](https://yandex.cloud/en/docs/storage/concepts/pre-signed-urls) — S3-compatible, `ru-central1`, `signature_version='s3v4'` (HIGH)
- Yandex Object Storage boto3 guide — [https://cloud.yandex.com/en-ru/docs/storage/tools/boto](https://cloud.yandex.com/en-ru/docs/storage/tools/boto) — endpoint `storage.yandexcloud.net` confirmed (HIGH)
- MinIO archived — [https://productimpossible.com/articles/self-hosted-s3-after-minio/](https://productimpossible.com/articles/self-hosted-s3-after-minio/) — archived Feb 2026, SeaweedFS recommended (MEDIUM, secondary source — verify before committing to SeaweedFS in Docker Compose)
- SeaweedFS alternatives — [https://lowcloud.io/en/blog/minio-alternatives](https://lowcloud.io/en/blog/minio-alternatives) — SeaweedFS/Garage/RustFS comparison (MEDIUM)
- TanStack Query + WebSocket integration — [https://tkdodo.eu/blog/using-web-sockets-with-react-query](https://tkdodo.eu/blog/using-web-sockets-with-react-query) — invalidateQueries on WS events pattern (HIGH, TkDodo is TanStack Query maintainer)
- aioboto3 version history — [https://github.com/terricain/aioboto3/blob/main/CHANGELOG.rst](https://github.com/terricain/aioboto3/blob/main/CHANGELOG.rst) — v13.4.0 last in v13 series (HIGH)
- Codebase: `apps/backend/pyproject.toml` — confirmed `python-telegram-bot>=22.7,<23`, `aioboto3>=13.0,<14`, `redis>=5,<6`
- Codebase: `apps/backend/app/workers/telegram_bot.py` — confirmed PTB long-polling pattern, `build_application`, `add_handler`, `CallbackQueryHandler`
- Codebase: `apps/backend/app/main.py` — confirmed `_otp_bot` bare Bot pattern for outbound-only DMs
- Codebase: `apps/backend/alembic/versions/` — last migration is `0063_seed_trainer_profiles.py` → next is `0064`

---

*Stack research for: clubcore v2.5 Chat / Messaging — WebSocket + Redis pub/sub + photo attachments + Telegram bridge*
*Researched: 2026-06-06*
