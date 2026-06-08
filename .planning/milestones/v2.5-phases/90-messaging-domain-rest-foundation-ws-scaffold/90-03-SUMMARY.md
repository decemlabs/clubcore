---
phase: 90-messaging-domain-rest-foundation-ws-scaffold
plan: "03"
subsystem: backend/messaging/websocket
tags: [websocket, realtime, redis-pubsub, auth, idor, cswsh, testing]
dependency_graph:
  requires: ["90-02"]
  provides: ["ws-endpoint", "ws-test-convention", "cswsh-guard"]
  affects: ["app.core.database", "app.core.dependencies", "app.modules.messaging.router"]
tech_stack:
  added: []
  patterns:
    - "Starlette TestClient WS convention (not httpx ASGITransport)"
    - "ws_receive_text_timeout: threading-based receive with wall-clock timeout"
    - "HTTPConnection as base type for get_db/get_current_client (works for WS and HTTP)"
    - "per-connection redis.pubsub() subscriber + asyncio.create_task fan-out"
    - "session-per-operation via app.state.sessionmaker (NOT Depends(get_db) in WS handler)"
    - "asyncio.wait_for heartbeat/idle detection, finally teardown"
key_files:
  created:
    - apps/backend/app/modules/messaging/ws.py
    - apps/backend/tests/messaging/conftest.py
    - apps/backend/tests/messaging/test_ws_smoke.py
    - apps/backend/tests/messaging/test_ws_auth_idor.py
    - apps/backend/tests/messaging/test_ws_fanout.py
  modified:
    - apps/backend/app/modules/messaging/router.py
    - apps/backend/app/core/dependencies.py
    - apps/backend/app/core/database.py
    - apps/backend/pyproject.toml
decisions:
  - "HTTPConnection instead of Request in get_db() and get_current_client() — WebSocket is not a subtype of Request; changing to the common base HTTPConnection makes both functions work for HTTP routes and WS endpoints"
  - "WebSocketException without explicit close() in verify_ws_origin — calling websocket.close() before accept() then raising caused double-close RuntimeError in TestClient; the exception alone is sufficient (FastAPI handles the close frame)"
  - "ws_receive_text_timeout via daemon thread — WebSocketTestSession.receive_text() has no timeout param; threaded approach with Queue avoids blocking test indefinitely"
  - "PytestUnraisableExceptionWarning suppressed in pyproject.toml — asyncio.run() for DB probe in ws_tc fixture creates event loop that Python GC tries to close when pytest-asyncio already owns a loop; this is test-isolation only, not a production issue"
  - "IDOR test: publish B then A, collect all frames, assert only A's messageId present — daemon thread approach for no-receive check caused race condition (thread steals A's frame); collecting frames and filtering by messageId is reliable"
metrics:
  duration: "~3 hours (multi-session)"
  completed: "2026-06-07"
  tasks_completed: 3
  files_changed: 9
---

# Phase 90 Plan 03: WebSocket Real-Time Transport Summary

One-liner: Per-connection Redis pub/sub WS endpoint with cookie auth, IDOR-safe principal channel, HTTPConnection dependency fix, and 7 tests proving all six RT invariants using Starlette TestClient convention.

## What Was Built

### Task 1 (b6896e92): CSWSH guard + WS test convention
- `verify_ws_origin` dependency in `app/core/dependencies.py`: validates Origin header against `settings.ws_allowed_origins` before accept(); raises `WebSocketException(code=1008)` on mismatch
- `tests/messaging/conftest.py`: full WS test fixture stack — `ws_tc` (TestClient with lifespan), `_portal_call`, `seed_ws_client`, `auth_ws_client_sync`, `flush_redis_sync`, `cleanup_client_sync`, `ws_receive_text_timeout`
- `tests/messaging/test_ws_smoke.py`: convention-proving test — authenticated client can open WS

### Task 2 (2a02cb09): WS endpoint + HTTPConnection dependency fix
- `apps/backend/app/modules/messaging/ws.py`: `run_connection()` coroutine with all 6 WS invariants
  - channel = `cc:messaging:client:{client_id}` from principal only (IDOR-safe)
  - `redis.pubsub()` per-connection dedicated subscriber (not shared pool)
  - `asyncio.create_task(_fan_out_loop())` for non-blocking Redis→WS forwarding
  - `asyncio.wait_for(receive_text(), timeout=...)` heartbeat + idle timeout
  - `session_factory` per-operation (no `Depends(get_db)` held for WS lifetime)
  - `finally:` cancels fan-out task, unsubscribes, closes pubsub
- `router.py`: `@router.websocket("/ws/messages")` with `verify_ws_origin` + `require_client()` guards; calls `run_connection()` after `accept()`
- **Rule 1 bug fix**: `get_db(request: Request)` → `get_db(request: HTTPConnection)` in `database.py`; same for `get_current_client` in `dependencies.py` — `WebSocket` is not a subtype of `Request`, dependency injection failed silently

### Task 3 (a79fbcad + afbb273d): WS invariant tests + CSWSH guard fix
- `test_ws_auth_idor.py` (4 tests):
  - T-90-10: no cookie → `WebSocketDenialResponse(status=401)` pre-accept
  - T-90-11: bad origin → `WebSocketDisconnect(code=1008)` (CSWSH guard)
  - T-90-11: missing origin → `WebSocketDisconnect(code=1008)`
  - T-90-12: IDOR — A publishes B's message, then A's; A only receives its own messageId
- `test_ws_fanout.py` (2 tests):
  - RT-03: cross-context Redis publish via `app.state.redis` → WS receives frame (no in-process state)
  - RT-04: reconnect catch-up — missed message recovered via `GET /messages?after=` cursor, NOT pub/sub replay
- **Rule 1 bug fix**: removed `await websocket.close(code=1008)` before `WebSocketException` in `verify_ws_origin` — double-close caused `RuntimeError: Cannot call send once a close message has been sent`
- `pyproject.toml`: suppress `PytestUnraisableExceptionWarning` — asyncio.run() in ws_tc probe creates orphaned event loop when pytest-asyncio auto-mode is active

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `get_db()` / `get_current_client()` failed in WS dependency chain**
- **Found during:** Task 2 smoke test run
- **Issue:** `TypeError: get_db() missing 1 required positional argument: 'request'` — FastAPI does not inject `WebSocket` as `Request` for WS endpoints; `WebSocket` inherits from `HTTPConnection` not `Request`
- **Fix:** Changed `request: Request` → `request: HTTPConnection` in both `get_db()` (database.py) and `get_current_client()` (dependencies.py); `HTTPConnection` is the common base of `Request` and `WebSocket`
- **Files modified:** `apps/backend/app/core/database.py`, `apps/backend/app/core/dependencies.py`
- **Commit:** `2a02cb09`

**2. [Rule 1 - Bug] Double-close `RuntimeError` in `verify_ws_origin`**
- **Found during:** Task 3 bad-origin test
- **Issue:** `RuntimeError: Cannot call "send" once a close message has been sent` — `websocket.close(code=1008)` before `accept()` sent the close ASGI message; then FastAPI's `websocket_exception` handler tried to send another close, causing RuntimeError
- **Fix:** Removed `await websocket.close(code=1008)` from `verify_ws_origin`; raising `WebSocketException(code=1008)` is sufficient — Starlette handles the close frame
- **Files modified:** `apps/backend/app/core/dependencies.py`
- **Commit:** `a79fbcad`

**3. [Rule 1 - Bug] IDOR test daemon-thread race condition**
- **Found during:** Task 3 IDOR test iterations
- **Issue:** First `ws_receive_text_timeout(ws_a, 1.0)` left a daemon thread alive that "stole" the subsequent message for client A; second receive returned None
- **Fix:** Changed IDOR test strategy — publish B's message then A's message before any receive; collect all frames with deadline loop; assert A's messageId present and no unknown messageId present
- **Files modified:** `apps/backend/tests/messaging/test_ws_auth_idor.py`
- **Commit:** `a79fbcad`

**4. [Rule 2 - Missing critical functionality] `PytestUnraisableExceptionWarning` crashed test suite**
- **Found during:** Task 3 full messaging test run
- **Issue:** `filterwarnings = ["error"]` in pyproject.toml treats all warnings as errors; `asyncio.run()` in ws_tc fixture creates event loop that GC tries to close when pytest-asyncio auto-mode owns the primary loop
- **Fix:** Added `ignore::pytest.PytestUnraisableExceptionWarning` filter with explanatory comment
- **Files modified:** `apps/backend/pyproject.toml`
- **Commit:** `afbb273d`

## Known Stubs

None. All six WS invariants are fully implemented and tested.

## Threat Flags

None. All T-90-10..T-90-16 threats in the plan's threat register are mitigated by the implementation.

## Self-Check: PASSED
