# Project Research Summary

**Project:** clubcore v2.5 Chat / Messaging — Client↔Gym
**Domain:** Real-time 1:1 WebSocket messaging + Redis pub/sub fan-out + photo attachments + Telegram bridge
**Researched:** 2026-06-06
**Confidence:** HIGH

---

## Executive Summary

v2.5 is the heaviest new surface in the project to date, introducing four genuinely new technical
areas onto an existing FastAPI modular monolith: native WebSocket transport, Redis pub/sub fan-out,
binary file handling, and bidirectional Telegram bridging. The recommended approach is additive and
zero-new-framework: FastAPI's built-in Starlette WebSocket class handles the transport layer;
redis.asyncio pub/sub covers multi-worker fan-out (Redis 7 is already running); aioboto3 (already
pinned) handles S3-compatible attachment storage; the existing python-telegram-bot 22.7 long-polling
worker gains one new MessageHandler. New Python deps are limited to filetype (pure-Python magic-byte
validation) and httpx-ws (dev/test only). The chat thread is human-only — no system event types —
keeping a hard boundary with the v2.4 notification inbox.

The two highest-density risk areas are Phase 90 (WS scaffold) and Phase 93 (Telegram bridge). Phase 90
carries six simultaneous invariants that must all be correct from day one: cookie-based auth (not URL
token), per-principal channel naming for IDOR safety, per-connection pubsub (not global lifespan task),
session-factory injection (not Depends(get_db)), application-level heartbeat/cleanup, and DB-first
delivery with pub/sub as notification-only transport. All six are silent in dev (single worker, happy
path) but break in production if missed. Phase 93 introduces Telegram reply routing, echo-loop
prevention, and staff identity constraints that must be specced before any bridge code is written.

The overall recommended build order — messaging domain REST + WS scaffold → receipts/typing →
attachments → Telegram bridge → PWA wiring + OpenAPI freeze — reflects hard technical dependencies:
the WS endpoint calls messaging/service functions that must exist first; the bridge publishes to
pub/sub channels that the WS layer must already subscribe to; the PWA cannot be wired until all
backend endpoints are stable and OpenAPI is byte-clean.

---

## Key Findings

### Recommended Stack

v2.5 adds exactly two new Python production dependencies and one dev dependency. Everything else reuses
the existing stack. The new module app/modules/messaging/ is a standard modular-monolith addition
following the established D-20-MODULE / D-20-IDOR / INFRA-15 discipline.

**New dependencies:**
- filetype >=1.2.0,<2 (prod): magic-byte MIME validation — pure Python, no C extension, no libmagic
  system dependency; reads only 261 bytes; allowlist is JPEG/PNG/WebP only; SVG explicitly banned
- httpx-ws >=0.9.0,<1 (dev): async WS testing via ASGI transport; v0.9.0 released 2026-03-28;
  ASGIWebSocketTransport API stable since 0.7.x

**Existing stack reused without changes:**
- FastAPI 0.115+: WebSocket, WebSocketDisconnect, WebSocketException — stable since 0.100+
- redis>=5,<6: redis.asyncio.Redis.pubsub() creates a dedicated connection for subscribe protocol
- python-telegram-bot >=22.7,<23: MessageHandler, filters.ChatType.PRIVATE confirmed in v22+
- aioboto3 >=13.0,<14: S3-compatible presigned PUT/GET for Yandex Object Storage; existing constraint
  works for v2.5 without bumping upper bound
- PyJWT 2.12.1+: existing aud:"client" validation logic; WS auth adapter reads cookie same as HTTP

**Local dev object storage:** MinIO Community Edition was archived February 2026 (read-only, no security
patches). Replacement for local dev: SeaweedFS (chrislusf/seaweedfs, Apache 2.0, actively maintained)
or Garage (dxflrs/garage, Rust, lighter). Production: Yandex Object Storage (confirmed S3-compatible,
RU-domiciled, presigned URLs verified in official Yandex docs).

**Frontend:** MVP uses a native useEffect-managed WebSocket hook in ChatScreen.jsx (~40 lines, no new
npm dependency). Pattern: receive WS event -> call queryClient.invalidateQueries on messages key ->
TanStack Query refetches via REST. WS carries only event frames (type + IDs), not full payloads.
react-use-websocket is the named upgrade path if the custom hook exceeds ~60 lines.

### Expected Features

**Must have (P1 — table stakes):**
- GET /api/v1/client/messages — cursor-paginated thread history (before UUID + limit) + unreadCount
- POST /api/v1/client/messages — send text message (IDOR: client_id from principal only)
- PATCH /api/v1/client/messages/read — mark all staff messages read; called on ChatScreen mount
- WS /api/v1/client/ws/messages — real-time channel; events: new_message, typing, read_receipt
- Redis pub/sub fan-out: channel cc:messaging:client:{client_id}, one subscriber per WS connection
- Reconnect with exponential backoff (1s->2s->4s->max 30s with jitter) + REST catch-up on reconnect
- Telegram bridge: forward client message to staff DM; handle staff reply; store in DB; WS fan-out
- POST /api/v1/client/messages/attachments — photo upload (JPEG/PNG/WebP, 5MB cap, magic-byte check)
- GET /api/v1/client/messages/attachments/{id} — authenticated proxy (IDOR-safe, FileResponse)
- Read receipt display: single check (server persisted), double check (staff replied = reply-as-read)
- Typing indicator display: staff->client via Telegram sendChatAction detection, TTL 5s auto-dismiss
- Unread badge on Chat tab (WS real-time + React Query 30s poll fallback)
- ChatScreen graduated from D-71-09 ESLint placeholder zone (de-list 3 spots + @/data import pattern)

**Should have (P2):**
- Camera capture option (same upload endpoint, <input capture="environment">)
- Client->staff typing indicator relay (defer if asyncio bridge loop complexity creates instability)
- Full-screen photo viewer on bubble tap
- WS connection state indicator ("V seti" / "Ne v seti")
- "Novye soobshcheniya" divider on reconnect
- Staff photo attachments via Telegram -> PWA

**Hard out-of-scope for v2.5:**
- System messages in chat thread (stays in v2.4 notification inbox — hard product constraint)
- Group chats, broadcast, channels
- File attachments other than photos; voice messages
- Admin-web chat inbox (frozen; v2.6)
- Message edit/delete, search
- Real web-push for new chat messages (delivery -> v2.6)
- Orphaned file cleanup cron

**Chat is human-only:** No system_message sender type. System events stay in the v2.4 notification
inbox and must never appear in the messaging thread. Hard architectural constraint: role ENUM is
'client' | 'staff', full stop.

### Architecture Approach

The messaging module follows the established modular monolith pattern exactly. app/modules/messaging/
is a new bounded module registered in .importlinter's modules-independent contract (one line added).
Its router (messaging/router.py) mounts at the /client prefix in api/v1/router.py, using the same
pattern as loyalty.router, gym.router, notifications.router. Cross-module reads use raw SQL text() in
messaging/repository.py (D-54-08 discipline, zero new ORM imports from foreign modules). The WS
endpoint lives inside the messaging module, NOT in client_portal/router.py, to avoid a cross-module
import violation. The Telegram bridge worker imports messaging.service directly as a D-06/D-10
documented relaxation (workers are not in source_modules of any import-linter contract — no
.importlinter change required for the bridge). Only one .importlinter change is needed for the entire
milestone: add app.modules.messaging to the modules-independent contract.

**Major components:**

1. app/modules/messaging/ (NEW): ORM models (message_threads, messages, message_attachments),
   repository (raw-SQL cross-module reads), service (send/receive/receipts/pub/sub publish), router
   (REST + WS endpoints), schemas (all inherit BackendSchemaBase for camelCase wire format)
2. Redis pub/sub subscriber per WS connection (not a global lifespan task): each WS handler spawns
   an asyncio task calling redis.pubsub().subscribe("cc:messaging:client:{client_id}"), cancelled
   in finally: on disconnect with await pubsub.aclose()
3. app/integrations/storage/ (NEW): local filesystem adapter (UUID filenames, magic-bytes check,
   MIME allowlist); swap seam for future S3 migration (one-file change in integrations)
4. Telegram bridge extension in app/workers/telegram_bot.py + app/integrations/telegram/handlers.py:
   new reply_handler, HandlerContext gains messaging_service field appended at END (stability contract),
   chat_forwarding_log in Redis maps telegram_message_id to thread_id (TTL 7d)
5. PWA ChatScreen.jsx wired: useChatSocket hook (native WebSocket, reconnect loop, WS events ->
   queryClient.invalidateQueries), REST history on mount, photo picker wired to attachment upload

**DB schema (migrations 0064+):**
- 0064_messaging_threads: id, client_id FK, created_at, last_message_at, client_unread_count
- 0065_messaging_messages: id, thread_id FK, role ENUM('client'|'staff'), body TEXT nullable,
  attachment_id UUID nullable FK, sent_at TIMESTAMPTZ, read_at TIMESTAMPTZ nullable;
  INDEX (thread_id, sent_at DESC)
- 0066_messaging_attachments: id UUID PK, thread_id FK, client_id FK (IDOR ownership),
  mime_type TEXT, file_path TEXT, size_bytes INT, created_at

**IDOR discipline for WS:** client_id comes ONLY from require_client() principal. Channel name
cc:messaging:client:{client_id} is derived from the principal, never from path params or WS payload.
WS messages from the client never include client_id or thread_id — both resolved server-side.

### Critical Pitfalls

1. **WS auth via URL token (CSWSH + log leakage)** — NEVER use ?token=jwt on WS endpoint. httpOnly
   cookie IS sent automatically on same-origin WS upgrade. Use Cookie-reading require_client_ws().
   Add verify_ws_origin dependency. LOCKED INVARIANT: CSWSH = IDOR gateway. (Phase 90)

2. **IDOR over WS subscribe** — Channel name must equal cc:messaging:client:{principal.client_id}.
   Never derive channel from path param or WS message body. Test: client A cannot receive client B's
   WS events. LOCKED INVARIANT per D-20-IDOR. (Phase 90)

3. **SQLAlchemy session per WS connection** — Depends(get_db) in WS handler holds one DB connection
   per active connection indefinitely. Pool exhaustion at ~pool_size concurrent clients. Fix: inject
   session_factory from app.state; open session per message operation. (Phase 90)

4. **Multi-worker fan-out failure (dev passes, prod breaks)** — Module-level connection dict works only
   with single uvicorn worker. Fix: Redis pub/sub is the ONLY correct mechanism. Test with cross-context
   delivery before Phase 90 closes. (Phase 90)

5. **Redis pub/sub at-most-once delivery** — No persistence. Messages missed during WS disconnect are
   lost. Fix: DB-first architecture + reconnect catch-up via ?after= cursor query. (Phase 90)

6. **httpx ASGITransport does not support WS upgrade** — async_client fixture raises UnsupportedProtocol
   on WS URLs. Fix: use starlette.testclient.TestClient.websocket_connect() for ALL WS tests. Must be
   established in Phase 90 before any WS endpoint is written. (Phase 90)

7. **Attachment stored XSS via SVG/HTML** — Magic-byte allowlist (JPEG/PNG/WebP) is the only ground
   truth. Explicitly reject SVG and all text/* types. Serve with Content-Disposition: attachment +
   X-Content-Type-Options: nosniff. LOCKED INVARIANT. (Phase 92)

8. **Telegram reply routing to wrong client** — Staff must use native Telegram Reply. Bot looks up
   reply_to_message.message_id in chat_forwarding_log. Free-standing messages dropped. (Phase 93)

9. **Telegram echo loop** — Check update.message.from_user.is_bot. chat_forwarding_log is the
   natural loop-breaker. (Phase 93)

10. **camelCase wire format inconsistency** — All schemas must inherit BackendSchemaBase. Forgetting
    produces sender_type instead of senderType. Verify with schema unit test. (Phase 90)

---

## Decisions to Make Before Planning

### CONFLICT 1: WS Authentication Mechanism

The four researchers diverge here and the plan must explicitly resolve this before Phase 90.

**STACK.md position:** Query-param JWT (?token=jwt). Rationale: browsers cannot set Authorization
headers on WS handshake. Recommends token from React session state (not httpOnly cookie). Notes log
scrubbing at structlog level as mitigation.

**FEATURES.md + ARCHITECTURE.md + PITFALLS.md position:** httpOnly cookie (cc_client_access). Browsers
DO send httpOnly cookies automatically on same-origin WS upgrade requests — this is standard HTTP
behavior. require_client() reads request.cookies.get("cc_client_access"); WebSocket objects expose
.cookies identically. PITFALLS.md flags the query-param approach as CSWSH + log leakage (OWASP) and
LOCKED INVARIANT.

**Resolution (recommended):** Use httpOnly cookie auth (majority position, OWASP-aligned, zero new
infrastructure). The cc_client_access cookie is set at login and sent automatically on same-origin
WS upgrade. The require_client() dependency works unchanged inside @router.websocket().

**The gap STACK.md identified is real but misapplied:** Browsers cannot set custom Authorization
HEADERS, but they always send cookies to the same origin. Since the client PWA is same-origin with
the API, the cookie approach is both correct and simpler.

**Fallback path (if cookie model changes):** Issue a short-lived WS ticket via POST /client/ws-ticket
(one-time token valid 10s, consumed on first connect). Add verify_ws_origin dependency regardless of
auth method — this is the CSWSH guard that applies to both approaches.

**Must confirm before Phase 90 plan:** Verify that cc_client_access cookie is set with SameSite=Lax
or Strict. If SameSite=None, the WS-ticket fallback is required.

### OPEN DECISION 2: Attachment Storage Backend

**Option A — Local filesystem (integrations/storage/):** Zero new infrastructure. Files stored under
MEDIA_ROOT volume path. Served via authenticated FileResponse. UUID-based filenames prevent enumeration.
Path traversal protected by Path(...).resolve().is_relative_to(UPLOAD_DIR). Correct for single-gym
single-server deployment. ARCHITECTURE.md and FEATURES.md recommendation for v2.5.

**Option B — S3-compatible from day one (Yandex Object Storage prod / SeaweedFS dev):** Avoids the
swap-later migration. Presigned PUT (client uploads directly) + presigned GET (time-limited URL).
aioboto3 already in stack. Local dev requires SeaweedFS or Garage (MinIO archived Feb 2026). STACK.md
documents this path in detail.

**Recommended for v2.5:** Option A (local filesystem), with integrations/storage/ abstraction in place
so Option B is a later one-file swap. Discuss-phase decision for Phase 92. If the user wants to skip
the migration entirely, take Option B now — both paths are fully documented.

---

## Implications for Roadmap

All four researchers converged on the same 6-phase build order. Phase numbering continues from v2.4
(last phase 89), so v2.5 starts at Phase 90.

### Phase 90: Messaging Domain + REST Foundation + WS Scaffold

**Rationale:** Everything else depends on this phase. Schema, service, and REST endpoints must exist
before WS can call messaging/service functions, before the bridge can call record_staff_message, and
before the PWA can wire REST queries. WS test pattern must be established here to avoid discovering
the httpx/ASGITransport WS incompatibility mid-phase.

**Delivers:**
- Alembic migrations 0064 (message_threads) + 0065 (messages)
- app/modules/messaging/ scaffold: models.py, repository.py, service.py, router.py, schemas.py
- REST: GET /client/messages (cursor + unreadCount), POST /client/messages (text), PATCH /client/messages/read
- WS GET /api/v1/client/ws/messages with cookie auth + per-connection Redis pub/sub subscriber
- POST /client/messages publishes to cc:messaging:client:{client_id} after DB commit
- .importlinter updated: app.modules.messaging added to modules-independent contract
- messaging_router mounted at /client prefix in api/v1/router.py
- LOCKED_AUDIT_EVENTS pre-registered: ("message_sent", "message"), ("message_read", "message"),
  ("attachment_uploaded", "message"), ("chat_staff_reply_sent", "message") — all chat events pre-registered
  here (INFRA-15: before any callsite, even in later phases)
- WS test template using starlette.testclient.TestClient.websocket_connect() established

**Avoids:** P1 (URL token auth), P2 (IDOR over WS), P3 (session per connection), P4 (multi-worker),
P5 (at-most-once delivery), P6 (zombie connection), P13 (httpx WS test), P15 (importlinter), P16 (camelCase)

**Research flag: YES — high priority.** Phase 90 carries the highest pitfall density of any phase in
the milestone. Plan with --research-phase to ensure all six simultaneous WS invariants are explicitly
specced before implementation starts.

### Phase 91: Read Receipts + Typing Indicators

**Rationale:** Pure extension of the WS protocol defined in Phase 90. No new tables required (typing
is ephemeral, never persisted to DB). Depends on Phase 90 WS infrastructure.

**Delivers:**
- Client sends {"type": "read_receipt"} over WS -> persisted to DB + published to staff pub/sub channel
- Client sends {"type": "typing"} over WS -> published to Redis with TTL 5s (NOT stored in DB)
- PATCH /client/messages/read also persists read state (polling fallback when WS disconnected)
- Staff->client typing: bot detects sendChatAction -> publishes typing event -> WS delivers -> 5s auto-dismiss
- Client->staff typing relay (defer if asyncio bridge loop complexity creates instability)

**Avoids:** P4 (typing ephemeral — pub/sub only, no DB writes per keystroke)

**Research flag: No.** Standard WS event extension. Apply Phase 90 patterns.

### Phase 92: Attachments

**Rationale:** Depends on Phase 90 schema (FK from messages.attachment_id to message_attachments).
Migration numbering requires sequential ordering after Phase 91.

**Delivers:**
- Alembic migration 0066 (message_attachments)
- app/integrations/storage/ adapter (local filesystem or S3 — see Open Decision 2)
- POST /api/v1/client/messages/attachments — upload endpoint, returns attachment_id + previewUrl
- GET /api/v1/client/messages/attachments/{id} — authenticated proxy, IDOR-safe, FileResponse
- POST /client/messages extended to accept optional attachment_id
- MIME allowlist (JPEG/PNG/WebP), SVG explicitly banned, 5MB cap, X-Content-Type-Options: nosniff
- Content-Disposition: attachment on serve

**Avoids:** P7 (stored XSS), P8 (path traversal + IDOR), P17 (unbounded file size)

**Decision point:** Storage backend (see Open Decision 2). Discuss in Phase 92 plan.

**Research flag: No.** OWASP attachment patterns well-documented. Include P7/P8/P17 checklist.

### Phase 93: Telegram Bridge

**Rationale:** Requires Phase 90 REST + pub/sub infrastructure (bridge calls record_staff_message
which publishes to the WS fan-out channel). Does not require Phase 91 or 92.

**Delivers:**
- chat_forwarding_log in Redis (TTL 7d): cc:messaging:tg_msg:{tg_message_id} -> thread_id
- New reply_handler in app/integrations/telegram/handlers.py
- HandlerContext NamedTuple: messaging_service field appended at END (stability contract)
- app/workers/telegram_bot.py: imports messaging.service (D-90-BRIDGE documented relaxation),
  registers reply_handler on PTB application
- Client->Staff: POST /client/messages enqueues ARQ task for Telegram DM (NOT synchronous — avoids
  Telegram 429 rate-limit cascade)
- STAFF_TELEGRAM_CHAT_ID: int | None added to Settings (bridge disabled if absent)
- Staff reply row stores telegram_user_id / telegram_username as nullable audit fields

**Avoids:** P9 (reply routing to wrong client), P10 (echo loop), P11 (staff identity), P12 (rate limit)

**Research flag: YES.** Phase 93 has the second-highest pitfall density. Plan with --research-phase.
Key specs to lock: chat_forwarding_log schema, is_bot check, ARQ task for Telegram forwarding,
HandlerContext field order, reply-as-read semantics in service layer.

### Phase 94: PWA ChatScreen Wiring

**Rationale:** Graduate ChatScreen only after ALL backend endpoints (REST + WS + attachments) are
stable. Premature wiring creates churn if endpoint contracts change.

**Delivers:**
- ChatScreen graduated from D-71-09 ESLint placeholder zone (de-list 3 spots + @/data import pattern)
- clientPortalKeys.messages key factory added to clientQueries.ts
- useChatSocket hook: native WebSocket, reconnect backoff, WS events -> queryClient.invalidateQueries
- Message list UI: bubbles (client right/staff left), timestamps (HH:MM Europe/Moscow), photo thumbnails
- Send input: text + photo picker, sending/sent/error states, optimistic local queue
- Read receipt display: single check / double check
- Typing indicator display ("Administrator pechat..." with 5s TTL)
- Tab badge for unread (WS real-time + React Query 30s poll fallback)
- ChatAttachSheet: Foto + Kamera only (remove or disable Fayl + Golosovoe)
- REST catch-up on reconnect via GET /client/messages?after={last_seen_id}

**Research flag: No.** Standard PWA wiring following v2.4 graduation pattern (Phases 86/87/88). Apply
D-71-09 graduation lesson from v2.4 exactly.

### Phase 95: OpenAPI Handoff + Milestone Verification

**Rationale:** Final gate. All backend endpoints stable; OpenAPI can be regenerated byte-stably.

**Delivers:**
- Byte-stable regen openapi.json + schema.d.ts
- WS endpoint manually documented in _customize_openapi() post-processor (FastAPI skips WS routes)
- _v25Checks AssertNonNever tuple + toHaveLength(N) runtime assertion
- Staff drift gate green (all staff paths byte-identical to contract-freeze-v1.11.0)
- Full milestone verification: pytest + mypy --strict + lint-imports + redocly + CISO-01

**Avoids:** P14 (OpenAPI drift — WS endpoint manually documented)

**Research flag: No.** Standard handoff following Phase 89 (v2.4) pattern.

### Phase Ordering Rationale

- Phase 90 before all others: WS + pub/sub scaffold is the prerequisite for everything. The bridge
  cannot publish to a channel that no one subscribes to.
- Phase 91 before 92: Read receipts/typing are pure WS event extensions with no new tables.
  Attachments require a migration and new integrations module — heavier.
- Phase 92 before 93: Migration numbering (0066 before 0067 if any; sequential ordering maintained).
- Phase 93 before 94: PWA wiring needs all backend endpoints stable. Telegram bridge completion
  signals the contract is stable enough to wire.
- Phase 95 last: OpenAPI handoff cannot run until all endpoints exist.

### Research Flags Summary

| Phase | Research Phase Needed | Reason |
|-------|----------------------|--------|
| Phase 90 | YES — high priority | Six simultaneous WS invariants; highest pitfall density; test convention change |
| Phase 91 | No | Standard WS event extension; established patterns from Phase 90 |
| Phase 92 | No | OWASP attachment patterns well-documented; checklist from PITFALLS.md |
| Phase 93 | YES | Telegram bridge routing complexity; echo loop; HandlerContext stability |
| Phase 94 | No | V2.4 graduation pattern proven; D-71-09 lesson documented |
| Phase 95 | No | Standard handoff following Phase 89 pattern |

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All reused packages confirmed in pyproject.toml; filetype + httpx-ws verified on PyPI; Yandex Object Storage S3 compat verified in official docs |
| Features | HIGH | Live codebase inspection of ChatScreen.jsx, UIContext.jsx, flows.jsx, telegram_bot.py, PROJECT.md v2.5 section; feature boundaries confirmed by user-defined out-of-scope list |
| Architecture | HIGH | All findings from direct codebase inspection of main.py, .importlinter, client_portal/router.py, dependencies.py, redis.py, api/v1/router.py, handlers.py; no training-data inference |
| Pitfalls | HIGH | OWASP (CSWSH, stored XSS), Redis official docs (pub/sub semantics), FastAPI docs (WS testing), all confirmed with high-confidence sources; codebase patterns (D-20-IDOR, INFRA-15, D-06/D-10) verified in live files |

**Overall confidence:** HIGH

### Gaps to Address

1. **WS auth mechanism (CONFLICT — must resolve before Phase 90 plan):** Confirm whether cc_client_access
   is set with SameSite=Lax/Strict (cookie auth works) or SameSite=None (need WS-ticket fallback).
   Check app/core/security.py or the cookie-setting call in client_auth/router.py. One-line code read.

2. **Attachment storage backend (OPEN — discuss in Phase 92 plan):** Local filesystem vs S3-compatible
   from day one. Factors: developer preference, docker-compose complexity tolerance, migration timeline.
   Both paths fully documented. Not a blocker for Phase 90/91.

3. **httpx-ws version compat (MEDIUM):** httpx-ws 0.9.0 not yet tested in this project. If
   ASGIWebSocketTransport has compat issues, fallback is Starlette's synchronous TestClient (no new
   dependency, always works). Validate in Phase 90 test setup.

4. **Staff Telegram identity gap:** For v2.5, staff replies carry telegram_user_id as nullable audit
   field but no FK to users table. Acknowledged limitation (PITFALLS.md P11). Resolved in v2.6 when
   admin-web chat inbox ships with authenticated HTTP sessions.

5. **Client->staff typing asyncio complexity:** Relaying typing events from PWA to the Telegram bridge
   requires the bot worker's asyncio loop to handle both long-polling and Redis subscription simultaneously
   (asyncio.gather pattern). P2-priority — defer if bridge loop stability is affected.

---

## Cross-Cutting Invariants (confirmed by all four agents)

- **httpx ASGITransport CANNOT do WS upgrade.** All WS tests use TestClient.websocket_connect() or
  httpx-ws ASGIWebSocketTransport. Overrides the project's "ASGITransport only" test convention for
  WS endpoints. Must be established in Phase 90.

- **Multi-worker fan-out requires Redis pub/sub.** Module-level dicts silently fail with >1 worker.
  No acceptable alternative. Test with cross-context delivery before Phase 90 closes.

- **DB-first, pub/sub as notification only.** Every message written to Postgres before any Redis
  publish. Redis event triggers REST re-fetch or delivers message_id — never full payload. On reconnect,
  client fetches missed messages from DB via ?after= cursor.

- **One .importlinter change for the entire milestone:** Add app.modules.messaging to modules-independent
  contract. No new ignore_imports for the core REST/WS path. No .importlinter change for the bridge
  (workers are not in source_modules).

- **Worker->messaging.service is a D-06/D-10 documented relaxation.** Document in worker module
  docstring (e.g. D-90-BRIDGE). No .importlinter edit required.

- **Chat is human-only.** No system_message sender type. role ENUM is 'client' | 'staff', full stop.

- **Reply-as-read semantics.** "Read" = staff replied (Telegram bots have no per-message read receipt
  API). When bot stores a staff reply, it marks prior client messages read_at = now() and publishes
  read_receipt events.

- **Typing is ephemeral.** Typing events never stored in Postgres. Published to Redis pub/sub only
  with 5s TTL. PWA auto-dismisses after 5s.

- **LOCKED_AUDIT_EVENTS must be pre-registered before any callsite (INFRA-15).** Pre-register ALL
  messaging events in Phase 90 plan, including bridge events planned for Phase 93:
  ("message_sent", "message"), ("message_read", "message"), ("attachment_uploaded", "message"),
  ("chat_staff_reply_sent", "message").

---

## Sources

### Primary (HIGH confidence — official docs + live codebase)
- apps/backend/app/main.py — composition root, lifespan, Protocol slot registration pattern
- apps/backend/app/workers/telegram_bot.py — HandlerContext pattern, D-06/D-10 relaxations
- apps/backend/app/integrations/telegram/handlers.py — HandlerContext NamedTuple stability contract
- apps/backend/app/modules/client_portal/router.py — require_client() on WS routes confirmed
- apps/backend/app/core/dependencies.py — ClientPrincipal, require_client(), cookie reading
- apps/backend/app/core/redis.py — redis.pubsub() availability on asyncio Redis client confirmed
- apps/backend/app/api/v1/router.py — multi-router mount pattern at /client prefix confirmed
- apps/backend/.importlinter — contract text, modules-independent module list, worker exemption
- apps/client-pwa/src/screens/ChatScreen.jsx — ComingSoon shell + D-71-08 marker
- apps/client-pwa/src/context/UIContext.jsx — chatThreadOpen, pendingChat, chatAttachOpen state
- apps/client-pwa/src/screens/sheets/flows.jsx:1167 — ChatAttachSheet (4 options)
- FastAPI WebSocket docs — https://fastapi.tiangolo.com/advanced/websockets/
- FastAPI WS testing docs — https://fastapi.tiangolo.com/advanced/testing-websockets/
- Redis pub/sub official docs — https://redis.io/docs/latest/develop/interact/pubsub/
- OWASP CSWSH — https://owasp.org/www-community/attacks/Cross_Site_WebSocket_Hijacking
- OWASP Stored XSS via SVG — https://owasp.org/www-community/xss-filter-evasion-cheatsheet
- python-telegram-bot v22.7 filters — https://docs.python-telegram-bot.org/en/stable/telegram.ext.filters.html
- Yandex Object Storage presigned URLs — https://yandex.cloud/en/docs/storage/concepts/pre-signed-urls
- filetype PyPI — https://pypi.org/project/filetype/ (v1.2.0, pure Python)
- httpx-ws PyPI — https://pypi.org/project/httpx-ws/ (v0.9.0, 2026-03-28)
- TkDodo blog (TanStack Query maintainer) — https://tkdodo.eu/blog/using-web-sockets-with-react-query

### Secondary (MEDIUM confidence)
- MinIO archived Feb 2026 — https://productimpossible.com/articles/self-hosted-s3-after-minio/
- SeaweedFS/Garage alternatives — https://lowcloud.io/en/blog/minio-alternatives
- Redis pub/sub + FastAPI multi-worker pattern — https://medium.com/@nandagopal05/scaling-websockets-with-pub-sub-using-python-redis-fastapi-b16392ffe291
- aioboto3 CHANGELOG — https://github.com/terricain/aioboto3/blob/main/CHANGELOG.rst

---

*Research completed: 2026-06-06*
*Ready for roadmap: yes*
*Agents: STACK.md (HIGH), FEATURES.md (HIGH), ARCHITECTURE.md (HIGH), PITFALLS.md (HIGH)*
