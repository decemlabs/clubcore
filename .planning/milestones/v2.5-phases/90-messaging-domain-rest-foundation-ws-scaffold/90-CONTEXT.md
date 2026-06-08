# Phase 90: Messaging Domain + REST Foundation + WS Scaffold - Context

**Gathered:** 2026-06-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 90 delivers the messaging foundation for v2.5: a new `app/modules/messaging/` bounded
module (models, repository, service, router, schemas), Alembic migrations for the thread/message
schema, the client-facing REST surface (send / list / mark-read), and the real-time WebSocket
transport with Redis pub/sub fan-out. After this phase a client can send and receive **text**
messages in their single 1:1 thread with the gym in real time, correctly across >1 worker.

Covers requirements MSG-01, MSG-02, MSG-03, MSG-04, RT-01, RT-02, RT-03, RT-04.

**In scope:** DB schema (threads + messages), REST endpoints, WS endpoint + per-connection Redis
pub/sub subscriber, DB-first delivery, import-linter contract update, audit event pre-registration,
WS test convention establishment.

**Out of scope (later phases):** read receipts / typing (Phase 91), attachments (Phase 92),
Telegram bridge (Phase 93), PWA wiring (Phase 94), OpenAPI freeze (Phase 95). Chat is human-only —
no `system_message` sender type; role ENUM is `'client' | 'staff'` only.

</domain>

<decisions>
## Implementation Decisions

### REST API Shape
- `GET /client/messages` uses the established page-based contract `{items,total,page,pageSize}`
  (`PageQuery` + `PaginatedData[T]`, MSG-01) **plus** an optional `?after={messageId}` cursor
  parameter for RT-04 reconnect catch-up (fetch messages newer than last seen).
- Messages ordered **newest-first** on the wire (`ORDER BY sent_at DESC, id DESC`); page 1 = latest.
  PWA reverses for display.
- `unreadCount` is returned as an extra field on the list response data alongside
  `items/total/page/pageSize` (no separate endpoint).
- Mark-read endpoint path is `PATCH /client/messages/read` (explicit sub-resource, research-aligned).

### Send & Persistence Semantics
- Idempotency (MSG-03) reuses the existing `app/core/idempotency.py` infrastructure via the
  `Idempotency-Key` header — no bespoke messaging dedup table.
- Deterministic ordering tiebreak is the composite `(sent_at, id)` — monotonic and collision-safe
  for same-millisecond sends. Same ordering used for catch-up cursor comparison.
- Thread lifecycle: lazy **get-or-create** of the single per-client thread on first send and first
  GET. No pre-creation at client registration.
- Empty / whitespace-only body is rejected with 422 (attachments arrive in Phase 92; until then a
  message must carry non-empty text).

### WebSocket Protocol & Lifecycle
- WS event frames are **minimal, id-only**: `{type:"new_message", messageId}`. The PWA reacts by
  invalidating the messages query and refetching via REST (DB-first; pub/sub is notification-only,
  never carries full payload — avoids at-most-once payload loss, P5).
- Application-level heartbeat: server ping every ~30s with idle-connection cleanup (not reliant on
  TCP/WS keepalive alone).
- Auth / IDOR failure: reject pre-accept with HTTP 401 where possible; otherwise close the socket
  with code `1008` (policy violation) per RT-02. Channel name is
  `cc:messaging:client:{principal.client_id}` derived ONLY from the `require_client()` principal —
  never from path params or WS payload.
- CSWSH guard: a `verify_ws_origin` dependency validates the upgrade Origin against the existing
  CORS allowed-origins config.

### Phase 90 Scope Boundary
- WS event-type enum is defined **extensibly** but only `new_message` is implemented in P90.
  All messaging audit events are pre-registered now per INFRA-15 (before any callsite, including
  Phase 93 bridge events): `("message_sent","message")`, `("message_read","message")`,
  `("attachment_uploaded","message")`, `("chat_staff_reply_sent","message")`.
- No Telegram forwarding in P90 — `POST /client/messages` publishes to Redis pub/sub only and
  leaves a service seam for the Phase 93 bridge.
- Staff messages are created via an internal `record_staff_message()` service function (exercised by
  tests and the future bridge); there is **no** staff-facing endpoint in v2.5 (admin-web frozen → v2.6).
- WS tests use Starlette's `TestClient.websocket_connect()` (zero new dependency, always works) —
  NOT `httpx`'s `ASGITransport` (cannot do WS upgrade, P6/P13). `httpx-ws` is deferred.

### WS Auth (confirmed fact, not grey area)
- `cc_client_access` cookie is `SameSite=Lax` (verified in `app/core/security.py`) → httpOnly
  cookie-based WS auth works; the WS-ticket fallback is NOT required. `require_client()`-style
  cookie reading works inside `@router.websocket()`.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/modules/notifications/` — closest analog module (service/models/schemas/router/repository),
  models the standard modular-monolith file split to follow for `app/modules/messaging/`.
- `app/core/redis.py` — `redis.asyncio` client; `.pubsub()` confirmed available for per-connection
  subscribe.
- `app/core/idempotency.py` — existing `Idempotency-Key` handling to reuse for MSG-03.
- `app/core/pagination.py` — `PageQuery` + `PaginatedData[T]`, wire form
  `{items,total,page,pageSize}` (D-10); schemas inherit camelCase via `BackendSchemaBase`.
- `app/core/dependencies.py` — `ClientPrincipal`, `require_client()`, cookie reading (reuse for WS).
- `app/core/security.py` — `cc_client_access` cookie set with `samesite="lax"`.

### Established Patterns
- Module router mounts at `/client` prefix in `app/api/v1/router.py` (same as
  `loyalty.router`, `gym.router`, `notifications.router`).
- Cross-module reads use raw SQL `text()` in the module repository (D-54-08) — zero foreign ORM imports.
- All response schemas inherit `BackendSchemaBase` for camelCase wire format (P16 — avoids
  `sender_type` instead of `senderType`).
- Latest Alembic migration is `0063_seed_trainer_profiles` → new migrations are `0064` (threads),
  `0065` (messages). Sequential numbering enforced.

### Integration Points
- `.importlinter` — add `app.modules.messaging` to the `modules-independent` contract (ONE line,
  the only import-linter change for the entire milestone).
- `app/api/v1/router.py` — mount `messaging_router` at `/client` prefix.
- WS endpoint lives **inside** the messaging module (NOT in `client_portal/router.py`) to avoid a
  cross-module import violation.
- `LOCKED_AUDIT_EVENTS` registry — pre-register all four messaging events.

</code_context>

<specifics>
## Specific Ideas

- DB schema (research-confirmed):
  - `0064_messaging_threads`: id, client_id FK, created_at, last_message_at, client_unread_count
  - `0065_messaging_messages`: id, thread_id FK, role ENUM('client'|'staff'), body TEXT,
    sent_at TIMESTAMPTZ, read_at TIMESTAMPTZ nullable; INDEX (thread_id, sent_at DESC).
    (`attachment_id` FK added in Phase 92 migration 0066, not here.)
- Redis pub/sub: per-WS-connection subscriber (NOT a global lifespan task); spawn asyncio task
  subscribing to `cc:messaging:client:{client_id}`; cancel in `finally:` with `await pubsub.aclose()`.
- SQLAlchemy: inject `session_factory` from `app.state` and open a session per message operation —
  NEVER `Depends(get_db)` held for the connection lifetime (P3 pool exhaustion).
- Six WS invariants must all be correct from day one (research P1–P6): cookie auth, per-principal
  channel, per-connection pubsub, session-factory injection, app-level heartbeat/cleanup,
  DB-first delivery.

</specifics>

<deferred>
## Deferred Ideas

- Read receipts (✓/✓✓) and typing indicators — Phase 91 (RCPT-01..03).
- Photo attachments + `attachment_id` FK + storage adapter — Phase 92 (ATT-01..03).
- Telegram bridge (forward + reply routing + echo-loop prevention) — Phase 93 (BRDG-01..03).
- PWA ChatScreen wiring + unread badge — Phase 94 (PWA-01..03).
- OpenAPI byte-stable regen + WS manual documentation — Phase 95 (HND-01).
- `httpx-ws` dev dependency — deferred; revisit only if Starlette TestClient proves insufficient.

</deferred>
