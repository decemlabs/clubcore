---
phase: 90-messaging-domain-rest-foundation-ws-scaffold
verified: 2026-06-07T12:00:00Z
status: passed
score: 21/21
overrides_applied: 0
re_verification: false
---

# Phase 90: Messaging Domain + REST Foundation + WS Scaffold — Verification Report

**Phase Goal:** Клиент может отправлять и получать текстовые сообщения в режиме реального времени — хранилище в PostgreSQL, доставка через WebSocket, Redis pub/sub fan-out корректен при нескольких worker-процессах
**Verified:** 2026-06-07T12:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Alembic upgrade head creates message_threads and messages tables | VERIFIED | `0064_messaging_threads.py` + `0065_messaging_messages.py` exist; `create_table` confirmed in both; schema test passes |
| 2 | alembic downgrade reverses both migrations cleanly | VERIFIED | downgrade() drops index then table in 0065, drops table in 0064; correct dependency order |
| 3 | lint-imports passes with app.modules.messaging in modules-independent contract | VERIFIED | `.importlinter` line 58: `app.modules.messaging`; `uv run lint-imports` exits 0 — 3 contracts kept, 0 broken |
| 4 | All four messaging audit event pairs are registered in LOCKED_AUDIT_EVENTS | VERIFIED | `audit.py` lines 475-478: `("message_sent","message")`, `("message_read","message")`, `("attachment_uploaded","message")`, `("chat_staff_reply_sent","message")` |
| 5 | Message.role is constrained to 'client' or 'staff' via CheckConstraint | VERIFIED | `0065`: `sa.CheckConstraint("role IN ('client','staff')", name="ck_messages_role")`; `models.py`: `CheckConstraint("role IN ('client','staff')", name="role")` |
| 6 | Client can GET /api/v1/client/messages and receive {items,total,page,pageSize,unreadCount}, newest-first | VERIFIED | `test_get_messages_returns_200_with_pagination_and_unread_count` PASSES; `MessageListResponse` has `unread_count` serializing as `unreadCount`; `ORDER BY sent_at DESC, id DESC` in repository |
| 7 | Client can POST /api/v1/client/messages with non-empty text; message persists and unreadCount logic is correct | VERIFIED | `test_post_message_valid_body_returns_200_and_persists` PASSES; `test_staff_message_increments_unread_count_and_patch_read_clears_it` PASSES |
| 8 | Empty/whitespace-only body returns 422 | VERIFIED | `test_post_message_empty_body_returns_422` + `test_post_message_whitespace_body_returns_422` PASS; `field_validator` strips + rejects |
| 9 | Client can PATCH /api/v1/client/messages/read; next GET returns unreadCount == 0 | VERIFIED | `test_staff_message_increments_unread_count_and_patch_read_clears_it` PASSES; 204 returned; `client_unread_count` reset to 0 in repository |
| 10 | Another client's thread is never visible (IDOR — own thread only, derived from principal) | VERIFIED | `test_idor_client_b_does_not_see_client_a_messages` PASSES; `client_id` from `require_client()` only, never from body/path |
| 11 | POST is idempotent on Idempotency-Key replay (same key+body returns the same message) | VERIFIED | `test_post_message_idempotency_same_key_same_body_replays` + `test_post_message_idempotency_same_key_different_body_returns_422` PASS; `verify_client_idempotency + idempotent_execute` wired |
| 12 | GET ?after={messageId} returns only messages newer than the cursor (RT-04 catch-up) | VERIFIED | `test_get_messages_after_cursor_returns_only_newer_messages` PASSES; composite `(sent_at, id::text) >` comparison in repository |
| 13 | record_staff_message() internal service function creates a role='staff' message | VERIFIED | `service.py` lines 111-177: `insert_message(role='staff', ...)` + increments `client_unread_count`; exercised by IDOR and unread tests |
| 14 | A WS test connects via Starlette TestClient.websocket_connect() — convention established | VERIFIED | `conftest.py` line 10, 34, 44: convention documented; all WS tests use `ws_tc.websocket_connect()`; grep confirms no `async_client.get("ws")` |
| 15 | An authenticated client (cc_client_access cookie) can open WS /api/v1/client/ws/messages and receive a new_message frame | VERIFIED | `test_ws_convention_authenticated_client_connects` PASSES; `test_ws_cross_context_fanout` PASSES (frame received) |
| 16 | A WS upgrade without a valid cc_client_access cookie is rejected before accept (401 / close 1008) | VERIFIED | `test_ws_no_cookie_rejected_401` PASSES — `WebSocketDenialResponse(status_code=401)` |
| 17 | A WS upgrade from a disallowed Origin is rejected (CSWSH guard) | VERIFIED | `test_ws_bad_origin_rejected_1008` + `test_ws_missing_origin_rejected_1008` PASS — `WebSocketDisconnect(code=1008)` |
| 18 | Client A's WS connection never receives client B's new_message events (IDOR over WS) | VERIFIED | `test_ws_idor_client_a_does_not_receive_client_b_messages` PASSES; channel = `cc:messaging:client:{principal.id}` only |
| 19 | A message published from a separate context (simulating worker B) is delivered to a WS held in context A (Redis pub/sub fan-out, RT-03) | VERIFIED | `test_ws_cross_context_fanout` PASSES; published via `app.state.redis.publish` from separate async call (no in-process state) |
| 20 | On reconnect the client uses GET /messages?after= to catch up missed messages (RT-04, REST catch-up) | VERIFIED | `test_ws_reconnect_catchup_via_rest_cursor` PASSES; asserts missed message in REST response AND not in WS replay |
| 21 | The WS handler opens a session per operation via session_factory (NOT Depends(get_db)) and cleans up pubsub in finally | VERIFIED | `ws.py`: `session_factory: async_sessionmaker[AsyncSession]` param; `websocket.app.state.sessionmaker` used in router; `finally:` block cancels fan-out task + `unsubscribe` + `aclose()` |

**Score:** 21/21 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/alembic/versions/0064_messaging_threads.py` | message_threads table with 1:1 client constraint | VERIFIED | `create_table`, `uq_message_threads_client_id`, FK to clients.id, `client_unread_count`, `last_message_at` |
| `apps/backend/alembic/versions/0065_messaging_messages.py` | messages table with role CHECK + composite index | VERIFIED | `create_table`, `ck_messages_role`, `ix_messages_thread_sent`, no `attachment_id` |
| `apps/backend/app/modules/messaging/models.py` | MessageThread + Message ORM models | VERIFIED | Both classes present; column-for-column match with migrations; `CheckConstraint("role IN ('client','staff')")` |
| `apps/backend/app/modules/messaging/__init__.py` | module-doc package marker | VERIFIED | Exists; bounded responsibility docstring present |
| `apps/backend/app/modules/messaging/schemas.py` | MessageItem, MessageListResponse (with unreadCount), SendMessageRequest, MessageResponse, WS event frame schema | VERIFIED | All five classes present; `unread_count` serializes as `unreadCount`; `SendMessageRequest` with strip validator; `NewMessageEvent` with `Literal["new_message"]` |
| `apps/backend/app/modules/messaging/repository.py` | get-or-create thread, list history (newest-first + after cursor), insert message, mark-read, unread count | VERIFIED | `on_conflict_do_nothing` present; `(sent_at, id::text) >` after cursor; RETURNING in mark_thread_read; zero foreign ORM imports |
| `apps/backend/app/modules/messaging/service.py` | send_client_message, list_thread_history, mark_thread_read, record_staff_message, _publish_new_message seam | VERIFIED | All four functions present; `cc:messaging:client:{client_id}` publish after DB write; TODO Phase 93 seam; no `session.commit()` |
| `apps/backend/app/modules/messaging/router.py` | GET/POST/PATCH /messages REST endpoints + @router.websocket | VERIFIED | All three REST operation IDs present; `@router.websocket("/ws/messages")` with `verify_ws_origin + require_client()` deps |
| `apps/backend/app/modules/messaging/ws.py` | per-connection Redis pubsub subscriber loop, heartbeat, session-factory usage, finally cleanup | VERIFIED | `pubsub`, `cc:messaging:client:`, `asyncio.wait_for`, `asyncio.create_task`, `finally:` with `aclose()` |
| `apps/backend/app/core/dependencies.py` | verify_ws_origin CSWSH guard dependency | VERIFIED | `async def verify_ws_origin` at line 1310; validates `settings.ws_allowed_origins`; raises `WebSocketException(code=1008)` |
| `apps/backend/tests/messaging/conftest.py` | Starlette TestClient WS fixture | VERIFIED | `websocket_connect` appears 4 times; top docstring explains ASGITransport divergence |
| `apps/backend/tests/messaging/test_ws_auth_idor.py` | WS auth + IDOR tests | VERIFIED | 4 tests: no-cookie→401, bad-origin→1008, missing-origin→1008, IDOR A≠B |
| `apps/backend/tests/messaging/test_ws_fanout.py` | cross-context fan-out + reconnect catch-up tests | VERIFIED | 2 tests: RT-03 cross-context, RT-04 reconnect via REST cursor |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `apps/backend/.importlinter` | `app.modules.messaging` | modules-independent contract modules list | WIRED | Line 58: `app.modules.messaging` — only v2.5 milestone change |
| `apps/backend/app/core/audit.py` | `LOCKED_AUDIT_EVENTS` | frozenset pair registration | WIRED | Lines 475-478: all four messaging pairs registered |
| `apps/backend/app/api/v1/router.py` | `messaging_router` | `include_router prefix="/client"` | WIRED | Lines 137-139: import + `v1.include_router(messaging_router, prefix="/client")` |
| `apps/backend/app/modules/messaging/service.py` | `audit.emit message_sent` | audit emit callsite | WIRED | Lines 74, 148: `audit.emit(session, "message_sent", ...)` |
| `apps/backend/app/modules/messaging/service.py` | `redis publish cc:messaging:client:` | pub/sub publish seam (notification-only, DB-first) | WIRED | Lines 91-93, 165-167: `await redis.publish(f"cc:messaging:client:{client_id}", ...)` after DB write |
| `apps/backend/app/modules/messaging/router.py` | `require_client()` over WebSocket | cookie-based principal on WS upgrade | WIRED | `client: Annotated[ClientPrincipal, Depends(require_client())]` in `client_ws_messages` |
| `apps/backend/app/modules/messaging/ws.py` | `cc:messaging:client:{client_id}` | redis.pubsub().subscribe on principal-derived channel | WIRED | Line 70: `channel = f"cc:messaging:client:{client_id}"` from parameter only |
| `apps/backend/app/modules/messaging/ws.py` | `app.state.sessionmaker` | session-factory per-operation (not Depends(get_db)) | WIRED | Router line 221: `session_factory=websocket.app.state.sessionmaker`; no `Depends(get_db)` in ws.py |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `router.py GET /messages` | `result` (MessageListResponse) | `service.list_thread_history → repository.list_thread_history` → raw SQL on `messages` + `message_threads` tables | Yes — DB queries confirmed in repository.py lines 155-206 | FLOWING |
| `router.py POST /messages` | persisted `Message` row | `service.send_client_message → repository.insert_message` → `INSERT INTO messages` | Yes — raw SQL INSERT with RETURNING | FLOWING |
| `router.py PATCH /messages/read` | `unread_count` reset | `service.mark_thread_read → repository.mark_thread_read` → `UPDATE messages SET read_at` + `UPDATE message_threads SET client_unread_count=0` | Yes — raw SQL UPDATE with RETURNING | FLOWING |
| `ws.py` WS frame | `raw["data"]` | Redis pub/sub `cc:messaging:client:{client_id}` channel; published after DB write in service | Yes — `redis.publish` called after `insert_message` confirmed in service.py | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 41 messaging tests pass | `uv run pytest tests/messaging/ -q` | `41 passed in 10.63s` | PASS |
| mypy strict on messaging module | `uv run mypy --strict app/modules/messaging/` | `Success: no issues found in 7 source files` | PASS |
| ruff on messaging module | `uv run ruff check app/modules/messaging/` | `All checks passed!` | PASS |
| import-linter contracts | `uv run lint-imports` | `3 contracts kept, 0 broken` | PASS |
| No foreign ORM imports in messaging | `grep -E "from app.modules.(clients|notifications|...)"` | `none — clean` | PASS |
| No `session.commit()` calls in service/repository | `grep -n "session.commit" service.py repository.py` | All occurrences are in docstrings only; no actual calls | PASS |
| No `Depends(get_db)` in ws.py | `grep "Depends(get_db)" ws.py` | `none (clean)` | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| MSG-01 | 90-01, 90-02 | Клиент видит историю своего 1:1-треда (пагинированно, unreadCount) — GET /client/messages | SATISFIED | `test_get_messages_returns_200_with_pagination_and_unread_count` PASSES; `MessageListResponse` with `unreadCount`; `ORDER BY sent_at DESC` |
| MSG-02 | 90-02 | Клиент отправляет текстовое сообщение — POST /client/messages; client_id только из принципала | SATISFIED | `test_post_message_valid_body_returns_200_and_persists` + `test_idor_client_b_does_not_see_client_a_messages` PASS; `require_client()` only source |
| MSG-03 | 90-02 | Сообщения упорядочены детерминированно и идемпотентны на повтор отправки | SATISFIED | `test_post_message_idempotency_same_key_same_body_replays` PASSES; composite tiebreak `(sent_at, id)` in repository |
| MSG-04 | 90-02 | Клиент сбрасывает непрочитанные — PATCH /client/messages | SATISFIED | `test_staff_message_increments_unread_count_and_patch_read_clears_it` PASSES; 204 returned; `client_unread_count = 0` |
| RT-01 | 90-03 | Клиент получает новые сообщения в реальном времени через WebSocket | SATISFIED | `test_ws_convention_authenticated_client_connects` + `test_ws_cross_context_fanout` PASS; frame received on WS within 3s |
| RT-02 | 90-03 | WS аутентифицируется по client-принципалу; подписка на чужой тред невозможна | SATISFIED | `test_ws_no_cookie_rejected_401`, `test_ws_bad_origin_rejected_1008`, `test_ws_idor_client_a_does_not_receive_client_b_messages` all PASS |
| RT-03 | 90-02, 90-03 | Доставка корректна при >1 worker — fan-out через Redis pub/sub | SATISFIED | `test_ws_cross_context_fanout` PASSES; publish from separate async context, no module-level state |
| RT-04 | 90-02, 90-03 | При обрыве PWA переподключается и догружает пропущенные сообщения через REST catch-up | SATISFIED | `test_ws_reconnect_catchup_via_rest_cursor` PASSES; `?after={last_seen_id}` cursor returns missed message; WS does NOT replay |

**All 8 requirements satisfied.**

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/modules/messaging/__init__.py` | 7-9 | `TODO Phase 91/92/93` | Info | Phase-referenced deferred work — acceptable; these are planned phases in the milestone |
| `app/modules/messaging/service.py` | 96 | `TODO Phase 93` | Info | Phase-referenced bridge seam — explicitly planned; no unreferenced debt |

No TBD, FIXME, or XXX markers found. All TODO markers reference specific future phases with explicit scope.

---

### Human Verification Required

None. All behavioral truths are fully verifiable programmatically. The full test suite (41 tests) covers:
- REST contract (11 integration tests)
- Schema validation (17 unit tests)
- ORM metadata (6 unit tests)
- WS smoke (1)
- WS auth + IDOR (4)
- WS fan-out + reconnect (2)

All pass against the real Postgres + Redis stack.

---

### Gaps Summary

No gaps. All 21 must-have truths are VERIFIED. All 8 requirement IDs (MSG-01..04, RT-01..04) are satisfied with passing tests as evidence. All quality gates are green (mypy --strict, ruff, lint-imports). All six WS invariants are enforced in code and proven by tests.

---

_Verified: 2026-06-07T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
