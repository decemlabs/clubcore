# Phase 90: Messaging Domain + REST Foundation + WS Scaffold - Pattern Map

**Mapped:** 2026-06-07
**Files analyzed:** 13 (5 new module files, 2 migrations, 5 modified core/api files, 1 importlinter)
**Analogs found:** 12 / 13 (the WS endpoint has NO codebase analog — see "No Analog Found")

The `app/modules/notifications/` module is the canonical analog for the entire new
`app/modules/messaging/` module: same modular-monolith file split, same client-portal `/client`
mount pattern, same caller-owns-txn discipline, same camelCase wire format, same D-54-08 raw-SQL
read discipline. Copy its structure file-for-file. Path prefix for all analog paths below is
`apps/backend/`.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/modules/messaging/__init__.py` | module-doc | n/a | `app/modules/notifications/__init__.py` | exact |
| `app/modules/messaging/models.py` | model (ORM) | CRUD | `app/modules/notifications/models.py` | exact |
| `app/modules/messaging/schemas.py` | schema (Pydantic) | request-response | `app/modules/notifications/schemas.py` | exact |
| `app/modules/messaging/repository.py` | repository | CRUD + cross-module read | `app/modules/notifications/repository.py` | exact |
| `app/modules/messaging/service.py` | service | CRUD + pub-sub publish | `app/modules/notifications/service.py` | role-match (pub/sub publish is novel) |
| `app/modules/messaging/router.py` (REST part) | router/controller | request-response | `app/modules/notifications/router.py` | exact |
| `app/modules/messaging/router.py` (WS endpoint) | router/controller | streaming / event-driven | **NONE** | NO ANALOG — novel |
| `alembic/versions/0064_*.py` (threads) | migration | n/a | `alembic/versions/0060_in_app_notifications.py` | exact |
| `alembic/versions/0065_*.py` (messages) | migration | n/a | `alembic/versions/0060_in_app_notifications.py` | exact |
| `app/api/v1/router.py` (mount) | config/wiring | n/a | self (lines 125-131, notifications mount) | exact |
| `.importlinter` (add module) | config | n/a | self (lines 16-32, modules list) | exact |
| `app/core/audit.py` (`LOCKED_AUDIT_EVENTS`) | config/registry | n/a | self (lines 449-472, v2.0–v2.3 blocks) | exact |
| `app/core/idempotency.py` (reuse) | utility | n/a | self (`verify_idempotency`, `idempotent_execute`) | reuse-as-is |

---

## Pattern Assignments

### `app/modules/messaging/models.py` (model, CRUD)

**Analog:** `app/modules/notifications/models.py`

**Imports + base-mixin pattern** (notifications/models.py lines 10-27):
```python
from __future__ import annotations
from datetime import datetime
from uuid import UUID as UUIDType  # noqa: N811
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base, TimestampMixin, UUIDPkMixin
```

**ORM model pattern** (notifications/models.py lines 47-89). Note: `Base, UUIDPkMixin, TimestampMixin`
gives `id` (gen_random_uuid), `created_at`, `updated_at` for free. FK uses `ondelete="RESTRICT"` +
explicit `name="fk_<table>_<col>_<reftable>"`. CheckConstraint `name=` takes a BARE suffix (the
`ck_%(table_name)s_%(constraint_name)s` template prefixes automatically — see module docstring lines 6-8):
```python
class InAppNotification(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "in_app_notifications"
    client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="RESTRICT",
                   name="fk_in_app_notifications_client_id_clients"),
        nullable=False,
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        CheckConstraint(_KIND_CHECK, name="kind"),   # → ck_in_app_notifications_kind
        Index("ix_in_app_notifications_client_id", "client_id"),
    )
```

**For messaging:** model the `role ENUM('client'|'staff')` as a `Text` + `CheckConstraint("role IN ('client','staff')", name="role")` — exactly the pattern `ClientPushToken.platform` uses (notifications/models.py lines 123). Add `Index("ix_messages_thread_sent", "thread_id", "sent_at")` with descending order for the (thread_id, sent_at DESC) read index. `body` is `Text` nullable=False (whitespace-only rejected at the schema layer, see schemas below).

---

### `app/modules/messaging/schemas.py` (schema, request-response)

**Analog:** `app/modules/notifications/schemas.py`

**Imports + base classes** (notifications/schemas.py lines 11-19):
```python
from __future__ import annotations
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID
from pydantic import Field
from app.core.schemas import BackendSchemaBase, ResponseData
```

**Wire-format rule (P16 — camelCase):** Response schemas inherit `ResponseData` (which carries
`alias_generator=to_camel`); request schemas inherit `BackendSchemaBase` (`extra='forbid'` + camelCase
inbound). `sent_at` serializes as `sentAt`, `sender`/`role` stays as-is, `thread_id` as `threadId`.
NEVER write a bare `pydantic.BaseModel`.

**List-response-with-extra-field pattern** (notifications/schemas.py lines 22-49) — this is the EXACT
analog for `unreadCount` alongside `items/total/page/pageSize`. `PaginatedData[T]` cannot carry extra
fields, so replicate the page shape manually:
```python
class ClientNotificationItem(ResponseData):
    id: UUID
    kind: str
    ...
    read_at: datetime | None = None
    created_at: datetime

class ClientNotificationsListResponse(ResponseData):
    items: list[ClientNotificationItem]
    total: int
    page: int
    page_size: int          # → pageSize
    unread_count: int       # → unreadCount
```
Copy this verbatim for `MessageListResponse` (rename fields; add `unread_count`).

**Request schema with constraints + Literal enum** (notifications/schemas.py lines 52-64) — the analog
for `SendMessageRequest`. Use `Annotated[str, Field(min_length=1, ...)]` to reject empty/whitespace
bodies at the Pydantic layer (→ 422 before DB):
```python
class ClientPushTokenRegisterRequest(BackendSchemaBase):
    token: Annotated[str, Field(min_length=1, max_length=512)]
    platform: Literal["web", "android", "ios"]
```
For WS event frames define an extensible discriminator: `type: Literal["new_message"]` (only one member
in P90, designed for extension). The minimal frame is `{type, messageId}` — schema serializes `message_id` → `messageId`.

---

### `app/modules/messaging/repository.py` (repository, CRUD + cross-module read)

**Analog:** `app/modules/notifications/repository.py`

**Cross-module read discipline (D-54-08) — the load-bearing pattern** (notifications/repository.py
lines 28-32 imports; lines 84-100 read shape). All cross-module reads (e.g. fetching client name from
the `clients` table) use raw `text()` with `:name` params, UUIDs cast to `str`, `.mappings()`. ZERO
foreign ORM imports:
```python
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.messaging.models import Message, MessageThread   # OWN models only

row = (await session.execute(
    text("SELECT id, kind, ... FROM in_app_notifications "
         "WHERE client_id = :cid ORDER BY created_at DESC LIMIT :limit OFFSET :offset"),
    {"cid": str(client_id), "limit": limit, "offset": offset},
)).mappings().all()
```

**ON CONFLICT DO NOTHING insert (SAVEPOINT-safe, no IntegrityError + rollback)** (notifications/repository.py
lines 55-72) — use for lazy get-or-create of the single per-client thread:
```python
stmt = (pg_insert(MessageThread)
        .values(client_id=client_id)
        .on_conflict_do_nothing(constraint="uq_message_threads_client_id")
        .returning(MessageThread.id))
inserted_id = (await session.execute(stmt)).scalar_one_or_none()
```

**Mark-read with RETURNING to detect rows (mypy-safe, no `.rowcount`)** (notifications/repository.py
lines 133-157) — direct analog for `PATCH /client/messages/read` reset of `client_unread_count`:
```python
updated_id = (await session.execute(
    text("UPDATE ... SET read_at = now(), updated_at = now() "
         "WHERE id = :id AND client_id = :cid AND read_at IS NULL RETURNING id"),
    {"id": str(...), "cid": str(client_id)},
)).scalar_one_or_none()
return updated_id is not None
```

**INVARIANT (notifications/repository.py docstring lines 9-13):** NO `session.commit()` in the
repository — caller-owns-txn (D-32-10/D-49-19).

**Newest-first ordering for messaging:** the CONTEXT decision is `ORDER BY sent_at DESC, id DESC`
(composite tiebreak). The `?after={messageId}` cursor is a `WHERE (sent_at, id) > (...)` comparison —
add it as an optional clause alongside the LIMIT/OFFSET shape from `list_notifications`.

---

### `app/modules/messaging/service.py` (service, CRUD + pub-sub publish)

**Analog:** `app/modules/notifications/service.py` (CRUD shape) + `app/modules/loyalty/service.py`
(audit.emit callsite shape)

**Imports + caller-owns-txn** (notifications/service.py lines 17-33):
```python
from __future__ import annotations
from uuid import UUID
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import NotFoundError
from app.core.pagination import PageQuery
from app.modules.messaging import repository
from app.modules.messaging.schemas import (...)
_log = structlog.get_logger("modules.messaging.service")
```

**Function signatures (keyword-only, caller-owns-txn, NO commit)** — mirror notifications/service.py
lines 36-110. Maps to MSG functions: `send_client_message`, `list_thread_history` (returns the
unread-count list response, lines 75-110 are the exact analog), `mark_thread_read`,
`record_staff_message` (internal — no endpoint; exercised by tests + Phase 93 bridge).

**audit.emit callsite (system-initiated, no staff actor)** — `app/modules/loyalty/service.py`
lines 119-130 is the closest analog (client-domain, `actor_user_id=None`):
```python
await audit.emit(
    session,
    "message_sent",                  # must be in LOCKED_AUDIT_EVENTS first (see below)
    actor_user_id=None,              # client-initiated; no staff actor
    resource_type="message",
    resource_id=message_id,
    client_id=str(client_id),
)
```
Import is `from app.core import audit`. emit() validates `(event, resource_type) ∈ LOCKED_AUDIT_EVENTS`
at runtime (audit.py lines 587-601) — registering the pair is mandatory BEFORE this callsite.

**Redis pub/sub publish (notification-only, P5 DB-first) — NOVEL, no service analog:** After the DB
write (and after the caller commits, or fire-and-forget post-commit), publish a minimal id-only frame:
```python
await redis.publish(f"cc:messaging:client:{client_id}",
                    json.dumps({"type": "new_message", "messageId": str(message_id)}))
```
Channel name derived ONLY from `client_id` principal. The redis client comes from `get_redis` (see
core/redis.py pattern below). NEVER carry the full message payload over pub/sub (P5 — at-most-once loss).
Leave a clearly-marked service seam (a no-op call or TODO Phase 93) for the Telegram bridge forward.

---

### `app/modules/messaging/router.py` — REST endpoints (controller, request-response)

**Analog:** `app/modules/notifications/router.py`

**Imports + router declaration** (notifications/router.py lines 22-41):
```python
from __future__ import annotations
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import ClientPrincipal, require_client, verify_client_csrf
from app.core.pagination import PageQuery
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.messaging import service
from app.modules.messaging.schemas import (...)

router = APIRouter(tags=["Client-Portal"])   # tag declared on router, D-64-TAG-ORDER
```

**GET (safe, no CSRF) — paginated + unreadCount** (notifications/router.py lines 44-66). Dependency
order: `query → require_client() → get_db`. `client.id` is the ONLY source of `client_id` (D-20-IDOR):
```python
@router.get("/messages", response_model=ResponseEnvelope[MessageListResponse],
            operation_id="client_list_messages", summary="...")
async def client_list_messages(
    query: Annotated[PageQuery, Depends()],
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[MessageListResponse]:
    result = await service.list_thread_history(session, client.id, query)
    return envelope(result)
```
Add `after: UUID | None = None` query param for RT-04 reconnect catch-up.

**Mutation (RBAC-04 ordering: `require_client() → verify_client_csrf → get_db`, explicit commit)**
(notifications/router.py lines 73-92 — the read-all analog; lines 127-153 — the POST analog):
```python
@router.post("/messages", response_model=ResponseEnvelope[MessageResponse],
             operation_id="client_send_message", summary="...")
async def client_send_message(
    payload: SendMessageRequest,
    client: Annotated[ClientPrincipal, Depends(require_client())],
    _csrf: Annotated[None, Depends(verify_client_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[MessageResponse]:
    result = await service.send_client_message(session, client_id=client.id, payload=payload)
    await session.commit()
    return envelope(result)
```

**Idempotency reuse (MSG-03):** add `key: Annotated[str, Depends(verify_idempotency)]` from
`app.core.idempotency` to the POST signature, and run through `idempotent_execute` (idempotency.py
docstring lines 23-25 — "All wired callsites MUST use this"). NO bespoke messaging dedup table.

**Route ordering note** (notifications/router.py lines 69-71): declare literal sub-paths
(`/messages/read`) BEFORE any `/messages/{id}` path-param route so the literal isn't captured.

**Conventions:** `operation_id` on every route (drift-gate / openapi stability); NO `try/except`
(AppError bubbles to `_app_error_handler`); GET has no `session.commit()`.

---

### `alembic/versions/0064_*.py` + `0065_*.py` (migration)

**Analog:** `alembic/versions/0060_in_app_notifications.py` (most recent table-creation migration of
the same shape). Latest revision is `0063_seed_trainer_profiles` → `0064` `down_revision` is `0063...`,
`0065` `down_revision` is `0064...`. Sequential numbering enforced.

**Header + revision chain** (0060 lines 1-23):
```python
from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0064_messaging_threads"
down_revision: str | None = "0063_seed_trainer_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**create_table with mixin columns spelled out + named constraints** (0060 lines 38-101). UUID PK uses
`server_default=sa.text("gen_random_uuid()")`; `created_at`/`updated_at` use `server_default=sa.text("now()")`;
FK uses explicit `name=` and `ondelete="RESTRICT"`; CheckConstraint/Index/UniqueConstraint use the
fully-qualified `ck_/ix_/uq_<table>...` names (migrations spell the FULL name, unlike the ORM which uses
bare suffixes). For the `role` enum on messages: `sa.CheckConstraint("role IN ('client','staff')", name="ck_messages_role")` (Text column + check, matching the `platform` pattern — do NOT use a Postgres native ENUM type).

**downgrade** (0060 lines 104-106): drop index then drop table.

**FK ordering across the two migrations:** `0064` creates `message_threads` first; `0065` creates
`messages` with the `thread_id` FK referencing `message_threads.id` — `0064` MUST run before `0065`
(the down_revision chain guarantees this). Add `Index` on `(thread_id, sent_at)` (DESC) in `0065` per
the CONTEXT spec — use `op.create_index("ix_messages_thread_sent", "messages", [sa.text("thread_id"), sa.text("sent_at DESC")])`.

---

### `app/api/v1/router.py` — mount (config/wiring)

**Analog:** self, lines 125-131 (the notifications mount — newest, exact pattern).

The established pattern for a client-facing module router is a late `noqa: E402` import + `include_router`
at the `/client` prefix (mirrors loyalty lines 109-111, gym 119-123, notifications 129-131):
```python
# Phase 90 MSG-01..04 / RT-01..04 — messaging REST + WS endpoint.
# Mounted at /api/v1/client (same prefix as client_portal_router) to expose
# /api/v1/client/messages and the WS endpoint /api/v1/client/ws/messages.
# Separate router avoids a client_portal→messaging cross-module edge (D-20-MODULE).
from app.modules.messaging.router import router as messaging_router  # noqa: E402

v1.include_router(messaging_router, prefix="/client")
```
Place it after the notifications mount (line 131), before the `/_internal/*` mounts (line 133+).

---

### `.importlinter` — add module (config)

**Analog:** self, lines 16-32 (the `modules =` list inside the `modules-independent` contract).

ONE line added to the `modules =` block (mirrors the loyalty/notifications/payment_methods preemptive
registrations, INFRA-15 discipline):
```ini
    app.modules.messaging
    # Phase 90 MSG-01..04 / RT-01..04 — messaging module registered per INFRA-15.
    # Cross-module reads (clients.name for display) go via raw SQL text() (D-54-08) — ZERO
    # ignore_imports edges. WS endpoint lives INSIDE messaging/router.py (not client_portal)
    # so no client_portal→messaging edge is needed. unmatched_ignore_imports_alerting=warn
    # cushions any timing gap before later-plan bodies land.
```
Per ARCHITECTURE.md + SUMMARY.md: this is the ONLY `.importlinter` change for the entire v2.5 milestone.
The Telegram bridge (Phase 93) needs NO `.importlinter` change (workers are not in any `source_modules`).

---

### `app/core/audit.py` — `LOCKED_AUDIT_EVENTS` (config/registry)

**Analog:** self, lines 449-472 (the v2.0–v2.3 client-domain blocks). emit() validates pairs at runtime
(lines 587-601), so all four messaging events MUST be pre-registered BEFORE any callsite (INFRA-15),
including the Phase 93 bridge events. Append inside the frozenset (before the closing `}` at line 473):
```python
        # v2.5 (Phase 90 lock — INFRA-15; messaging domain. All four events pre-registered
        # BEFORE any callsite, including Phase 93 bridge events.)
        ("message_sent", "message"),
        ("message_read", "message"),
        ("attachment_uploaded", "message"),
        ("chat_staff_reply_sent", "message"),
```
The resource_type string is `"message"` for all four. Follow the exact comment style of the
loyalty/autopay blocks (lines 458-472).

---

## Shared Patterns

### Client authentication / IDOR principal
**Source:** `app/core/dependencies.py` — `ClientPrincipal` (lines 1158-1168), `require_client()`
(lines 1234-1251), `get_current_client` (lines 1191-1231).
**Apply to:** every messaging REST endpoint AND the WS endpoint.
`require_client()` reads the `cc_client_access` httpOnly cookie (line 1210: `request.cookies.get("cc_client_access")`),
decodes with `aud="client"` assertion, loads via the registered `ClientLoader` slot. `client.id` is the
ONLY source of `client_id` — never path/query/body (D-20-IDOR). CONFIRMED for WS: `cc_client_access` is
`SameSite=Lax` (security.py line 519), so cookie-based WS auth works; `WebSocket.cookies` exposes the
same jar as `Request.cookies`. The WS handler reads `websocket.cookies.get("cc_client_access")` (or uses
`Depends(require_client())` directly in the WS signature).

### CSRF on mutations
**Source:** `app/core/dependencies.py` — `verify_client_csrf` (lines 1254-1288). Double-submit
`clubcore_client_csrf` cookie vs `x-csrf-token` header, constant-time compare, short-circuits on safe
methods.
**Apply to:** `POST /client/messages`, `PATCH /client/messages/read` (NOT GET, NOT the WS upgrade — WS
handshake cannot carry the header; cookie auth + Origin check is the WS guard instead).
**Ordering (RBAC-04):** `require_client() → verify_client_csrf → get_db`.

### Pagination contract (D-10)
**Source:** `app/core/pagination.py` — `PageQuery` (lines 20-29, `?page=1&pageSize=20`) + `PaginatedData[T]`
(lines 32-44). Note: messaging uses the manual `*ListResponse` shape (notifications analog) because
`PaginatedData[T]` cannot carry the extra `unreadCount` field.
**Apply to:** `GET /client/messages` query params.

### Response envelope + camelCase
**Source:** `app/core/schemas.py` — `ResponseEnvelope[T]`, `envelope()`, `BackendSchemaBase`, `ResponseData`.
**Apply to:** all REST responses (`return envelope(result)`); all schemas inherit `ResponseData`
(responses) or `BackendSchemaBase` (requests) for camelCase (P16).

### Idempotency (MSG-03)
**Source:** `app/core/idempotency.py` — `verify_idempotency` (lines 75+), `idempotent_execute` (orchestrator,
docstring lines 23-25). User/client-scoped Redis key `cc:idem:{id}:{method}:{path}:{key}`, 24h TTL.
**Apply to:** `POST /client/messages`. No bespoke dedup table.

### Redis client access
**Source:** `app/core/redis.py` — `get_redis(request)` (lines 54-57, returns the `app.state.redis`
singleton); `redis.asyncio.Redis` with `decode_responses=True` (lines 30-34). `.pubsub()` IS available
on this asyncio client (confirmed; creates a dedicated subscriber connection).
**Apply to:** service-layer `redis.publish(...)` and (Phase 91) the WS per-connection
`redis.pubsub()` subscriber. NOTE: for the WS subscriber, call `redis.pubsub()` to get a DEDICATED
connection — never `subscribe()` on the shared pool client (P-AntiPattern-3).

### Caller-owns-txn
**Source:** every service + repository (notifications/service.py + repository.py docstrings).
**Apply to:** messaging service + repository — NO `session.commit()` inside; the router commits after
the service call (notifications/router.py lines 91, 123, 152).

---

## No Analog Found

| File / concern | Role | Data Flow | Reason |
|----------------|------|-----------|--------|
| `app/modules/messaging/router.py` — `@router.websocket("/ws/messages")` endpoint | router | streaming / event-driven | **NO WebSocket endpoint exists anywhere in the codebase** (confirmed: `grep -rln websocket app/` returns zero files). This is genuinely novel. |
| Per-connection Redis pub/sub subscriber loop | service/transport | pub-sub | No existing pub/sub subscriber pattern; `redis.publish` exists nowhere yet either. |
| WS app-level heartbeat / `asyncio.wait_for` idle cleanup | transport | event-driven | Novel. No precedent. |
| WS test using `starlette.testclient.TestClient.websocket_connect()` | test | n/a | No WS test exists; project convention is `httpx ASGITransport` which CANNOT do WS upgrade (P13). New test convention must be established this phase. |

**Planner guidance for the WS endpoint (use RESEARCH.md, not a codebase analog):**
- Endpoint signature, auth flow, and per-connection pub/sub loop sketch: `ARCHITECTURE.md` Question 1
  (lines 69-99) and Question 2 (lines 132-172).
- Six WS invariants (cookie auth, per-principal channel, per-connection pubsub, session-factory
  injection NOT `Depends(get_db)`, app-level heartbeat/cleanup, DB-first delivery): `PITFALLS.md` P1-P6,
  and `SUMMARY.md` "Cross-Cutting Invariants".
- Session usage in the WS handler: inject `session_factory` from `app.state` and open `async with
  session_factory() as session` PER message operation — do NOT use `Depends(get_db)` (P3 pool exhaustion).
  This DIVERGES from the REST analog above (which correctly uses `Depends(get_db)`).
- WS test pattern: `PITFALLS.md` P13 (lines 299-328) — `with TestClient(app) as tc: with
  tc.websocket_connect(...) as ws: ...`.
- The WS endpoint lives INSIDE `messaging/router.py` (NOT `client_portal/router.py`) — ARCHITECTURE.md
  Anti-Pattern 1 (lines 516-520).

---

## Metadata

**Analog search scope:** `apps/backend/app/modules/notifications/` (primary module analog),
`apps/backend/app/modules/loyalty/service.py` (audit.emit callsite), `apps/backend/app/core/`
(dependencies, redis, pagination, idempotency, audit, security), `apps/backend/app/api/v1/router.py`,
`apps/backend/alembic/versions/`, `apps/backend/.importlinter`.
**Files scanned:** ~14 source files read in full or targeted.
**WebSocket search:** `grep -rln websocket apps/backend/app/` → **zero matches** (WS is novel).
**Pattern extraction date:** 2026-06-07
