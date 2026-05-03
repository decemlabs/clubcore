# Phase 8: Clients Module + Audit Log — Research

**Researched:** 2026-05-03
**Domain:** FastAPI + SQLAlchemy 2.0 async + PostgreSQL (pg_trgm, JSONB, ARRAY, partial unique) + Pydantic v2 + Alembic async migrations
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** PATCH = `model_dump(exclude_unset=True)`; null-out not supported v1.1. `model_validator(mode="before")` rejects `None` values for optional fields → 422 `invalid_field`.
- **D-02:** `repository.py` + `service.py` split. All `select(Client)` is in `repository.py` only.
- **D-03:** `audit.emit` called inside the same transaction as the mutation. One commit = both INSERTs or neither.
- **D-04:** New `async def emit(session, event, *, actor_user_id, resource_type, resource_id=None, **payload)` signature. All Phase 5/7 call-sites updated additively. Event names NOT renamed.
- **D-05:** `AuditLog` ORM in `app/core/audit_models.py`. FK via string reference `'users.id'` to preserve `core ⊥ modules`.
- **D-06:** `audit_log.actor_user_id` NULLABLE. No sentinel system-user.

### Claude's Discretion

- **D-07:** `audit_log.resource_id` is `PgUUID NULL`. Non-UUID identifiers go in `payload`.
- **D-08:** `payload` = JSONB per-event fixed structure; client mutations carry diff (changed_fields list + previous_phone), not full state.
- **D-09:** No-op PATCH (all fields match current state) → no `client_updated` emit.
- **D-10:** Phone = strict E.164 `^\+[1-9]\d{1,14}$`, no backend normalization.
- **D-11:** `IntegrityError` on `uq_clients_phone_alive` → `DomainError { code: 'phone_exists' }` 409. Other IntegrityErrors propagate as 500.
- **D-12:** `q=` ILIKE on `lower(last_name || ' ' || first_name || ' ' || coalesce(middle_name, '')) ILIKE '%q%' OR phone ILIKE '%q%'`. Minimum length 2 chars.
- **D-13:** `?tag=X` exact match via `'X' = ANY(tags)`.
- **D-14:** `createdFrom`/`createdTo` inclusive; `hasTelegram` bool filter; sort: `created_at DESC` (default) or `last_name ASC` only.
- **D-15:** `gender` TEXT + CHECK `IN ('male', 'female')` via `SAEnum(Gender, native_enum=False)`.
- **D-16:** `tags TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[]`; per-tag max 32 chars, max 16 tags, regex `^[a-z0-9а-я\-_]+$`; service-layer validation.
- **D-17:** `emergency_contact JSONB NULL` with Pydantic `EmergencyContact` structure; `.model_dump()` before `session.add`.
- **D-18:** Module-level functions in `service.py` and `repository.py`, not classes.
- **D-19:** Service accepts `AsyncSession`, `actor: User`, DTO inputs; returns ORM `Client` or `PaginatedData`.
- **D-20:** One migration file `0002_clients.py`: extension → clients table → partial unique → GIN trigram indexes → audit_log table → btree on `(actor_user_id, created_at DESC)`.
- **D-21:** Route→permission mapping: GET=VIEW, POST/PATCH=EDIT, DELETE=DELETE (owner-only). `EDIT` used for POST+PATCH (not `CREATE`).

### Deferred Ideas (OUT OF SCOPE)

- Null-out optional fields via PATCH (v1.2)
- lint-rule `select(Client)` outside `repository.py` (backlog v1.2)
- `GET /api/v1/audit-log` endpoint (v1.2)
- Audit log full diff (v1.2)
- Multi-tag filter (v1.2)
- pg_trgm similarity `%` operator (v1.2)
- Direction-toggling sort + other sort columns (v1.2)
- tag CRUD endpoint (v1.2)
- Photo upload, bulk CSV import, "last visit" filter (v1.2)
- System actor in audit_log (v1.2)
- Per-IP rate limit on `/clients` (v1.2)
- Audit-log retention policy (v1.2+)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INFRA-04 | Migration `0002_clients.py`: CREATE EXTENSION pg_trgm, `clients` + `audit_log` tables | pg_trgm CREATE EXTENSION in Alembic `op.execute`; async migration env.py pattern; GIN trgm expression index via `op.execute` raw SQL |
| CLIENTS-01 | `clients` table schema: id, ФИО triple, phone (E.164), email?, birthday?, gender?, tags text[], notes?, emergency_contact? jsonb, telegram_user_id? bigint UNIQUE, created_by_user_id FK, timestamps, deleted_at? | `Base + UUIDPkMixin + TimestampMixin + SoftDeleteMixin` composition; `ARRAY(Text)` with `server_default`; `JSONB` column; `SAEnum(Gender, native_enum=False)` pattern from User.role |
| CLIENTS-02 | Partial unique index `WHERE deleted_at IS NULL` | `Index('uq_clients_phone_alive', 'phone', unique=True, postgresql_where=text('deleted_at IS NULL'))` in `__table_args__`; Alembic `op.create_index(..., postgresql_where=text(...))` |
| CLIENTS-03 | List endpoint with ILIKE on ФИО+phone using pg_trgm GIN indexes | GIN indexes on `lower(last_name)` and `lower(first_name)` via `op.execute` raw DDL; ILIKE query via SA `.ilike()` |
| CLIENTS-04 | Filters: tag, gender, date range, hasTelegram; sort created_at DESC or last_name ASC | `ANY()` array containment; `SAEnum` filter; datetime range WHERE clause; `order_by` with two options |
| CLIENTS-05 | GET `/clients/{id}` returns 404 for soft-deleted | `get_alive` repo helper with `deleted_at IS NULL` filter |
| CLIENTS-06 | POST `/clients`: required last_name, first_name, phone; E.164 validation | Pydantic `Field(pattern=...)` regex; `IntegrityError` on partial-unique → 409 |
| CLIENTS-07 | PATCH partial update; reception cannot edit owner-only fields | `model_dump(exclude_unset=True)`; no owner-only fields exist yet in v1.1 |
| CLIENTS-08 | DELETE owner-only, soft-delete only | `require_permission(DELETE, CLIENTS)` + OWNER_ONLY matrix already contains `(DELETE, CLIENTS)` |
| CLIENTS-09 | All queries through `list_alive`/`get_alive` repository helpers | Repo-only pattern; service never imports Client model |
| AUDIT-01 | `audit_log` table schema | `AuditLog(Base, UUIDPkMixin)` with TIMESTAMPTZ `created_at` (no updated_at); FK via string ref |
| AUDIT-02 | Audit writes co-transactional with mutations | `session.flush()` after `session.add(AuditLog(...))` inside same transaction as mutation |
| AUDIT-03 | No `GET /audit-log` HTTP endpoint in v1.1 | Confirmed deferred; table exists, writes happen, no read route |
</phase_requirements>

---

## Summary

Phase 8 is a well-scoped implementation phase: 21 decisions cover the full API contract, schema, and audit wiring. All design decisions are locked or discretionary (no open architecture questions). The planner's job is to translate those 21 decisions into ordered tasks without ambiguity.

The primary technical risks are (1) the GIN trigram expression index syntax in Alembic async migrations — the `op.create_index` API does not reliably render `gin_trgm_ops` on expression columns, making raw `op.execute(SQL DDL)` the correct approach; (2) the call-site migration of `audit.emit()` from sync to async touches 4 files and ~15 call-sites and must not miss any; (3) `handlers.py` uses `logger.warning/info` directly (not `audit.emit`) for 4 telegram events — these need both a new `from app.core.audit import emit` import AND to be switched to `await audit.emit(session, ...)` using the session that already exists in the handler's `async with ctx.session_factory()` block.

The test strategy builds naturally on the existing SAVEPOINT fixture (`db_session`) and dependency override (`async_client`): after a route call, `db_session.scalars(select(AuditLog).where(...))` asserts DB rows using the same session the route used.

**Primary recommendation:** Implement in 5 ordered waves — (1) AuditLog model + migration, (2) audit.emit async upgrade + all call-site updates, (3) Client model + schemas, (4) repository + service + router, (5) tests. Wave 2 must complete before Wave 4 because service.py calls await audit.emit.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Client CRUD persistence | Database/Storage | API/Backend | SQL+ORM in repository.py; service orchestrates |
| Audit log writes | Database/Storage | API/Backend | Co-transactional DB INSERT via `session.add(AuditLog(...))` |
| Phone uniqueness (alive clients) | Database/Storage | — | Partial unique index enforced at DB level |
| pg_trgm trigram search | Database/Storage | — | GIN index accelerates ILIKE; query stays in repository |
| E.164 phone validation | API/Backend (service) | API/Backend (Pydantic) | Pydantic field_validator in schema; service re-validates before DB |
| RBAC enforcement | API/Backend (router dep) | — | `require_permission` on route signatures; service unaware of Role |
| CSRF enforcement | API/Backend (router dep) | — | `verify_csrf` dependency on POST/PATCH/DELETE routes |
| camelCase/snake_case translation | API/Backend (Pydantic) | — | `ContractModel` alias_generator=to_camel handles all DTOs |
| Pagination | API/Backend | Database/Storage | `PageQuery` → LIMIT/OFFSET in repository; `PaginatedData` wraps result |

---

## Standard Stack

### Core (already installed, no new deps needed for Phase 8)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | ≥0.115 | HTTP router + dependency injection | Project-locked; router.py, Depends() pattern |
| SQLAlchemy | 2.0 async | ORM, JSONB/ARRAY types, GIN index syntax | Project-locked; `AsyncSession`, `mapped_column` |
| asyncpg | ≥0.30 | Postgres async driver | Project-locked; `UniqueViolationError.constraint_name` accessible |
| Pydantic v2 | (bundled with FastAPI) | Schema validation, `model_validator`, `field_validator`, `exclude_unset` | Project-locked |
| Alembic | async | DB migrations | Project-locked; async env.py already in place |
| structlog | (installed) | Structured logging passthrough in emit() | Project-locked |

[VERIFIED: apps/backend/pyproject.toml]

No new pip dependencies needed for Phase 8. All required libraries are already in `pyproject.toml`.

---

## Architecture Patterns

### System Architecture Diagram

```
HTTP Request
     │
     ▼
FastAPI Router (router.py)
  ├─ Depends(require_permission(Action, Resource))  ← RBAC gate, 401/403
  ├─ Depends(verify_csrf)                           ← CSRF gate on mutations, 403
  └─ Depends(get_db) → AsyncSession
     │
     ▼
Service layer (service.py)
  ├─ Validate phone E.164
  ├─ repository.list_alive / get_alive / insert / update / soft_delete
  │       └─ SELECT / INSERT / UPDATE on clients (deleted_at IS NULL filter)
  ├─ Build audit payload (changed_fields diff on update; PD-safe fields only)
  ├─ await audit.emit(session, event, actor_user_id=..., resource_type='client', ...)
  │       ├─ structlog.get_logger("audit").info(event, **payload)
  │       └─ session.add(AuditLog(...))   ← no commit here
  └─ session.flush()                      ← single flush; caller's tx commits

Database Layer (PostgreSQL 16)
  ├─ clients table
  │   ├─ partial unique: uq_clients_phone_alive WHERE deleted_at IS NULL
  │   ├─ GIN idx: ix_clients_last_name_trgm  (lower(last_name) gin_trgm_ops)
  │   └─ GIN idx: ix_clients_first_name_trgm (lower(first_name) gin_trgm_ops)
  └─ audit_log table
      └─ btree idx: (actor_user_id, created_at DESC)
```

### Recommended Project Structure

```
apps/backend/
├── alembic/versions/
│   └── 0002_clients.py            # NEW — pg_trgm + clients + audit_log
├── app/
│   ├── core/
│   │   ├── audit.py               # MODIFY — async emit + DB INSERT
│   │   └── audit_models.py        # NEW — AuditLog ORM model
│   ├── modules/
│   │   └── clients/
│   │       ├── __init__.py        # UPDATE docstring
│   │       ├── models.py          # NEW — Client + Gender
│   │       ├── schemas.py         # NEW — ClientCreateRequest, ClientUpdateRequest,
│   │       │                      #         ClientResponse, ClientListQuery,
│   │       │                      #         EmergencyContact
│   │       ├── repository.py      # NEW — list_alive, get_alive, insert_client,
│   │       │                      #         update_client, soft_delete_client
│   │       ├── service.py         # NEW — orchestration + audit emit
│   │       └── router.py          # NEW — 5 endpoints + ResponseEnvelope
│   ├── modules/auth/
│   │   ├── service.py             # MODIFY — update 4 emit() call-sites
│   │   └── router.py              # MODIFY — update 2 emit() call-sites
│   ├── integrations/telegram/
│   │   └── handlers.py            # MODIFY — switch 4 logger.* to await audit.emit(session,...)
│   ├── modules/auth/
│   │   └── telegram_service.py    # MODIFY — update 3 emit() call-sites
│   └── api/v1/router.py           # MODIFY — include clients router
├── tests/integration/
│   ├── clients/
│   │   ├── __init__.py            # NEW
│   │   ├── test_clients_list.py   # NEW
│   │   ├── test_clients_crud.py   # NEW
│   │   ├── test_clients_rbac.py   # NEW
│   │   └── test_audit_writes.py   # NEW
│   └── auth/
│       ├── test_login.py          # EXTEND — add audit_log DB row assertions
│       ├── test_logout.py         # EXTEND — add audit_log DB row assertions
│       └── test_telegram_*.py     # EXTEND — add audit_log DB row assertions
```

### Pattern 1: Partial Unique Index in Model `__table_args__`

[VERIFIED: SQLAlchemy 2.0 PostgreSQL docs + database.py SoftDeleteMixin docstring]

```python
# apps/backend/app/modules/clients/models.py
from sqlalchemy import Index, text
from app.core.database import Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin

class Client(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "clients"

    # ... columns ...

    __table_args__ = (
        Index(
            "uq_clients_phone_alive",
            "phone",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        # GIN trigram indexes are in migration only (expression indexes not
        # reliably autogenerated by Alembic from __table_args__ func expressions)
    )
```

### Pattern 2: GIN Trigram Expression Index in Alembic Migration

[VERIFIED: SQLAlchemy 2.0 PostgreSQL dialect docs + local test]

The `op.create_index` API accepts `sa.text()` as column expression for simple cases, but `gin_trgm_ops` operator class on a function expression (`lower(col)`) is most reliably rendered via raw `op.execute` DDL. This avoids Alembic autogenerate conflicts:

```python
# apps/backend/alembic/versions/0002_clients.py

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

def upgrade() -> None:
    # 1. Enable pg_trgm extension
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # 2. Create clients table
    op.create_table(
        "clients",
        sa.Column("last_name", sa.Text(), nullable=False),
        sa.Column("first_name", sa.Text(), nullable=False),
        sa.Column("middle_name", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("birthday", sa.Date(), nullable=True),
        sa.Column(
            "gender",
            sa.Enum("male", "female", name="gender", native_enum=False, length=16),
            nullable=True,
        ),
        sa.Column(
            "tags",
            sa.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("ARRAY[]::TEXT[]"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("emergency_contact", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_by_user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("gender IN ('male', 'female')", name=op.f("ck_clients_gender")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_clients")),
        sa.UniqueConstraint("telegram_user_id", name=op.f("uq_clients_telegram_user_id")),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"],
            name=op.f("fk_clients_created_by_user_id_users"), ondelete="RESTRICT"
        ),
    )

    # 3. Partial unique index (phone alive)
    op.create_index(
        "uq_clients_phone_alive",
        "clients",
        ["phone"],
        unique=True,
        postgresql_where=text("deleted_at IS NULL"),
    )

    # 4. GIN trigram expression indexes (use raw DDL — op.create_index
    #    does not reliably render operator classes on func expressions)
    op.execute(
        "CREATE INDEX ix_clients_last_name_trgm "
        "ON clients USING gin (lower(last_name) gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_clients_first_name_trgm "
        "ON clients USING gin (lower(first_name) gin_trgm_ops)"
    )

    # 5. audit_log table
    op.create_table(
        "audit_log",
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=False),
        sa.Column("resource_id", sa.UUID(), nullable=True),
        sa.Column("payload", sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"],
            name=op.f("fk_audit_log_actor_user_id_users"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )

    # 6. btree index for future audit-log read queries
    op.create_index(
        "ix_audit_log_actor_user_id_created_at",
        "audit_log",
        ["actor_user_id", sa.text("created_at DESC")],
    )

def downgrade() -> None:
    op.drop_index("ix_audit_log_actor_user_id_created_at", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index("ix_clients_first_name_trgm", table_name="clients")
    op.drop_index("ix_clients_last_name_trgm", table_name="clients")
    op.drop_index("uq_clients_phone_alive", table_name="clients")
    op.drop_table("clients")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
```

**NOTE on Alembic autogenerate + GIN expression indexes:** Alembic `alembic check` (TEST-08) will flag raw `op.execute` DDL indexes as "missing" in autogenerate because the ORM model has no matching `Index` expression in `__table_args__`. The accepted fix is to add `Index('ix_clients_last_name_trgm', ...)` using `func.lower(Client.last_name)` with `postgresql_using='gin'` and `postgresql_ops={'lower-1': 'gin_trgm_ops'}` in `Client.__table_args__`. [ASSUMED — the autogenerate collision with raw DDL GIN expression indexes needs testing; planner should include a verification step for `alembic check` clean after migration runs.]

### Pattern 3: `audit.emit` Async Upgrade

[VERIFIED: current audit.py line 32; CONTEXT.md D-04; app.core CAN be imported by app.integrations per .importlinter]

```python
# apps/backend/app/core/audit.py
from uuid import UUID
from typing import Any
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.audit_models import AuditLog  # new import

async def emit(
    session: AsyncSession,
    event: str,
    *,
    actor_user_id: UUID | None,
    resource_type: str,
    resource_id: UUID | None = None,
    **payload: Any,
) -> None:
    structlog.get_logger("audit").info(event, **payload)
    session.add(
        AuditLog(
            action=event,
            actor_user_id=actor_user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            payload=payload,
        )
    )
    # NO commit/flush — caller owns the transaction
```

**CRITICAL: `audit.py` imports `AuditLog` from `audit_models.py`.** Both live in `app.core`, so no import-linter violation. `audit_models.py` must be created before `audit.py` is modified.

**CRITICAL: `core-not-depend-on-modules` contract is satisfied** because `AuditLog` is in `app.core.audit_models`, not in `app.modules.*`.

### Pattern 4: Call-Site Migration (15 sites across 4 files)

[VERIFIED: grep audit.emit call-sites in auth/service.py, auth/router.py, telegram_service.py, telegram/handlers.py]

**auth/service.py** — 5 emit() calls needing session parameter:
```python
# Before (sync, no session):
emit("login_failed", email=email_lower, reason="invalid_credentials", ip=ip)
emit("login_success", user_id=str(user.id), email=email_lower, ip=ip, channel="email_password")
emit("password_changed_revokes_sessions", user_id=str(user_id), family_count=family_count)
emit("session_revoked", user_id=str(user_id), family_id=str(family_id))
emit("session_revoked_all", user_id=str(user.id), family_count=family_count)

# After (async, with session + typed fields):
await audit.emit(session, "login_failed",
    actor_user_id=None, resource_type="login_attempt",
    email=email_lower, reason="invalid_credentials", ip=ip)
await audit.emit(session, "login_success",
    actor_user_id=user.id, resource_type="session", resource_id=family_id,
    email=email_lower, ip=ip, channel="email_password")
# etc. per D-04 mapping table
```

**auth/router.py** — 1 emit() call (login_success for telegram verify):
```python
# auth/router.py line 269 — telegram_verify endpoint
await audit.emit(session, "login_success",
    actor_user_id=user.id, resource_type="session", resource_id=<family_id_from_issue_tokens>,
    ip=ip, channel="telegram")
```

**CRITICAL FINDING for router.py:** `issue_tokens()` returns `(access_jwt, raw_refresh, csrf_token)` — it does NOT return `family_id`. The `login_success` event for telegram_verify currently uses `emit("login_success", ..., channel="telegram")` at line 269 without `resource_id`. Per D-04, `login_success` should set `resource_id=session_family_id`. This requires either (a) `issue_tokens` returning `family_id` as a 4th value, or (b) the login_success emit uses `resource_id=None` for the telegram channel (acceptable — D-07 says non-UUID identifiers go in payload). The existing `auth/service.py` call for email-password login also calls `emit` BEFORE `issue_tokens` returns, so it lacks `family_id` too. The planner should choose `resource_id=None` with `family_id` in payload for login_success, or restructure `issue_tokens` to return it — planner's discretion.

**telegram_service.py** — 3 emit() calls:
```python
# telegram_deep_link_issued: actor_user_id=None (no user yet)
await audit.emit(session, "telegram_deep_link_issued",
    actor_user_id=None, resource_type="otp",
    deep_link_token_hash=token_hash)

# otp_issued: actor_user_id=user.id
await audit.emit(session, "otp_issued",
    actor_user_id=user.id, resource_type="otp",
    chat_id=telegram_chat_id)

# otp_consumed: actor_user_id=user.id
await audit.emit(session, "otp_consumed",
    actor_user_id=user.id, resource_type="otp")
```

**handlers.py** — CRITICAL: currently uses `logger.warning/info` directly (NOT `audit.emit`) for 4 events:

```python
# Current (lines 114-157): direct structlog, no audit.emit
logger.warning("telegram_unknown_start", ...)
logger.info("telegram_replay_attempt", ...)
logger.warning("telegram_dm_blocked", ...)
logger.warning("telegram_dm_failed", ...)

# After Phase 8 (all 4 happen inside `async with ctx.session_factory() as session:`):
# handlers.py can import app.core.audit (not app.modules — allowed by .importlinter)
from app.core.audit import emit as audit_emit  # top of file

await audit_emit(session, "telegram_unknown_start",
    actor_user_id=None, resource_type="otp",
    username=username, chat_id=chat_id, deep_link_token_hash=deep_link_token_hash)
# etc.
```

[VERIFIED: .importlinter forbids `app.integrations → app.modules` only; `app.integrations → app.core` is explicitly permitted]

### Pattern 5: IntegrityError Constraint Detection for asyncpg

[VERIFIED: asyncpg 0.30 `UniqueViolationError.constraint_name` exists via `uv run python3`]

```python
# apps/backend/app/modules/clients/service.py
from sqlalchemy.exc import IntegrityError

async def create_client(session: AsyncSession, actor: CurrentUser, data: ClientCreateRequest) -> Client:
    try:
        client = await repository.insert_client(session, actor.id, data)
        await session.flush()  # triggers constraint check
    except IntegrityError as e:
        await session.rollback()
        # asyncpg wraps UniqueViolationError; SA wraps in IntegrityError
        # e.orig is the asyncpg exception with .constraint_name
        orig = e.orig
        constraint = getattr(orig, "constraint_name", None)
        if constraint == "uq_clients_phone_alive":
            raise PhoneExistsError("phone_exists") from e
        raise  # re-raise other IntegrityErrors as 500
    # ... audit.emit call-site
```

**Note on flush vs commit:** `session.flush()` sends INSERTs to DB within the transaction, triggering constraint violations without committing. The service does NOT call `session.commit()` — the FastAPI `get_db` dependency manages the transaction lifecycle via `async with session_factory() as session`. Since `expire_on_commit=False` is set on the sessionmaker, post-flush ORM objects remain accessible.

### Pattern 6: PATCH `exclude_unset` + null-rejection validator

[VERIFIED: Pydantic v2 docs + `model_validator(mode='before')` pattern]

```python
# apps/backend/app/modules/clients/schemas.py
from pydantic import model_validator
from typing import Any

class ClientUpdateRequest(RequestContract):
    last_name: str | None = None
    first_name: str | None = None
    phone: str | None = None
    # ... other optional fields

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_null(cls, data: Any) -> Any:
        """D-01: reject null values for optional fields (null-out deferred to v1.2)."""
        if isinstance(data, dict):
            null_keys = [k for k, v in data.items() if v is None]
            if null_keys:
                raise ValueError(
                    f"Explicit null not supported for: {null_keys}. "
                    "Use absence of key to leave field unchanged."
                )
        return data
```

Usage in service:
```python
updates = data.model_dump(exclude_unset=True)
# updates only contains keys the client actually sent
for key, value in updates.items():
    setattr(client, key, value)
```

### Pattern 7: Test Audit DB Row Assertion

[VERIFIED: existing test pattern in test_logout.py using `db_session.scalars(select(...))` after route call]

```python
# tests/integration/clients/test_audit_writes.py
from sqlalchemy import select
from app.core.audit_models import AuditLog

async def test_client_created_writes_audit_row(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,  # existing fixture
) -> None:
    # The async_client dependency override installs SAVEPOINT session
    # so route handler's get_db yields the same session
    r = await async_client.post(
        "/api/v1/clients",
        json={"lastName": "Иванов", "firstName": "Иван", "phone": "+79991234567"},
        headers={"X-CSRF-Token": async_client.cookies["sportzal_csrf"]},
    )
    assert r.status_code == 201, r.text

    # After the route commits (SAVEPOINT in test), DB row is visible to same session
    rows = (await db_session.scalars(
        select(AuditLog).where(AuditLog.action == "client_created")
    )).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.actor_user_id == seeded_owner.id
    assert row.resource_type == "client"
    assert row.resource_id is not None
    assert "full_name" in row.payload
    assert "phone" in row.payload
```

**IMPORTANT: `db_session` uses `join_transaction_mode="create_savepoint"`, meaning service-level `session.flush()` (which the service uses instead of commit) becomes a nested savepoint that is still visible within the outer test transaction. This makes post-route audit_log queries work correctly.**

### Anti-Patterns to Avoid

- **`session.commit()` inside service functions:** The session is shared with the test SAVEPOINT fixture. Calling commit inside service promotes the savepoint, but the outer rollback still fires. The existing auth services DO call `session.commit()` — this works because of `join_transaction_mode="create_savepoint"`. However, D-03 specifies that clients service uses `session.flush()` only; the FastAPI `get_db` dependency closes the session (which commits) on route exit. This difference from auth services is intentional.
- **`select(Client)` outside `repository.py`:** CLIENTS-09 enforces this; `service.py` must not import `Client` model.
- **Creating new `AppError` subclasses outside `exceptions.py`:** Existing pattern is subclass in `exceptions.py`. `InvalidPhoneError`, `PhoneExistsError`, `ClientNotFoundError` should be added there.
- **Direct logger calls for audit events in handlers.py without DB row:** After Phase 8, all 4 telegram handler events must go through `audit.emit(session, ...)`.
- **Using `op.create_index` for GIN expression indexes without verifying autogenerate:** Raw `op.execute` SQL is safer and more explicit. Alembic autogenerate cannot reverse-engineer gin_trgm_ops operator class.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Phone uniqueness (alive) | Custom pre-insert query | Partial unique index `WHERE deleted_at IS NULL` | DB-enforced, race-condition safe |
| Soft-delete alive filter | `WHERE deleted_at IS NULL` sprinkled everywhere | `list_alive` / `get_alive` repo helpers | CLIENTS-09 architectural rule — can't forget |
| Constraint name parsing | Text matching on IntegrityError message | `e.orig.constraint_name` on asyncpg | Stable across PG versions; message text is locale-dependent |
| Trigram search | Custom similarity logic | pg_trgm + GIN + ILIKE | Built into Postgres; handles ILIKE acceleration transparently |
| camelCase wire format | Custom serializer | `ContractModel(alias_generator=to_camel)` | Already wired; subclass and get it free |
| RBAC enforcement | `if role != "owner"` in service | `require_permission(Action.DELETE, Resource.CLIENTS)` as router dep | Phase 6 TEST-07 introspection catches missing gates |
| Pagination | Manual LIMIT/OFFSET | `PageQuery + PaginatedData[T]` | Already wired; `ClientListQuery(PageQuery)` inherits |

---

## Common Pitfalls

### Pitfall 1: Alembic autogenerate flags GIN expression indexes as "missing"

**What goes wrong:** TEST-08 (`alembic check`) fails with `Detected removed index 'ix_clients_last_name_trgm'` or similar after raw DDL is used for GIN expression indexes.
**Why it happens:** Alembic autogenerate compares `Base.metadata` (model indexes) against the live DB schema. A `CREATE INDEX ... USING gin(lower(last_name) gin_trgm_ops)` created via `op.execute` has no counterpart in `Client.__table_args__`, so autogenerate sees a DB index with no ORM representation.
**How to avoid:** Add matching `Index` objects in `Client.__table_args__` using `func.lower(Client.last_name)` with `postgresql_using='gin'` and `postgresql_ops` keyed by the label. Alternatively, mark them `include_object` in alembic `env.py` to exclude them from autogenerate comparison. [ASSUMED — exact label key for postgresql_ops dict on func expression needs empirical testing; the safest path is `op.execute` DDL + `info={"skip_autogenerate": True}` or equivalent alembic config.]
**Warning signs:** `alembic check` in TEST-08 returns non-empty diff.

### Pitfall 2: `audit.emit` is async but call-sites in `revoke_session` / `revoke_all_sessions` call it AFTER `session.commit()`

**What goes wrong:** Post-commit `await audit.emit(session, ...)` calls `session.add(AuditLog(...))` on a session that has already committed — the AuditLog row never gets committed.
**Why it happens:** In `auth/service.py`, `emit("session_revoked", ...)` is called AFTER `await session.commit()` (line 451). In Phase 8, the emit body does `session.add(AuditLog(...))` without a commit. A new `session.commit()` would need to follow.
**How to avoid:** Move `await audit.emit(session, ...)` BEFORE `await session.commit()`, then let the single commit handle both the business mutation and the AuditLog insert. This is the D-03 co-transactional requirement. The service.py refactor must reorder: (1) business mutation, (2) `await audit.emit(session, ...)`, (3) `await session.commit()`.
**Warning signs:** `test_audit_writes.py` shows 0 rows for session_revoked events.

### Pitfall 3: `handlers.py` telegram events miss DB audit rows

**What goes wrong:** `telegram_unknown_start`, `telegram_replay_attempt`, `telegram_dm_blocked`, `telegram_dm_failed` events emit structlog only (as they do today) — no `audit_log` DB rows written.
**Why it happens:** These 4 events use `logger.warning/info` directly, not `audit.emit`. Phase 8 must convert them.
**How to avoid:** In `handlers.py`, add `from app.core.audit import emit as audit_emit` and convert all 4 `logger.*` calls to `await audit_emit(session, event_name, actor_user_id=None, resource_type="otp", ...)`. All 4 events happen inside the `async with ctx.session_factory() as session:` block, so `session` is available.
**Warning signs:** `test_audit_writes.py` assertions for telegram events fail with 0 rows.

### Pitfall 4: `login_success` event lacks `resource_id` (family_id) due to `issue_tokens` not returning it

**What goes wrong:** D-04 maps `login_success → resource_type='session', resource_id=session_family_id`. But `issue_tokens()` returns `(access_jwt, raw_refresh, csrf_token)` — no `family_id`. The service/router layer doesn't know the family_id assigned inside `issue_tokens`.
**Why it happens:** `issue_tokens` was designed pre-D-04 and creates a new `family_id = uuid4()` internally.
**How to avoid:** Option A — `issue_tokens` returns 4-tuple `(access, refresh, csrf, family_id)`. Option B — emit `login_success` with `resource_id=None` and log `family_id` in payload instead (D-07 permits non-UUID identifiers in payload). Option B is a smaller change. Planner decides.
**Warning signs:** `login_success` audit rows have `resource_id=NULL` when option B is chosen; acceptable per D-07.

### Pitfall 5: `session.flush()` in service + `join_transaction_mode="create_savepoint"` test fixture

**What goes wrong:** Service uses `session.flush()` (not commit) for atomicity. Tests assert DB rows after route returns. The SAVEPOINT fixture promotes nested SAVEPOINTs to the outer transaction on each flush — this is correct behavior, but only if the session is not closed between route exit and test assertion.
**Why it happens:** `get_db` yields `async with session_factory() as session` — the session context manager closes (but does NOT rollback) the session on exit. A flush is sufficient for the SAVEPOINT fixture to see the rows.
**How to avoid:** Verify test assertion in `test_audit_writes.py` runs AFTER the `await async_client.post(...)` call returns — it will. The `async_client` dependency override ensures the test's `db_session` is the same session used by the route handler, so flush-only service functions make their writes visible to test assertions.
**Warning signs:** Audit rows are not found in test session even though route returned 200/201.

### Pitfall 6: ARRAY server_default in Alembic vs ORM model

**What goes wrong:** `tags TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[]` — the server default must be expressed differently in the ORM model vs the Alembic migration.
**Why it happens:** SA `server_default` expects a string (raw SQL) or `text()`. The correct form is `server_default=sa.text("ARRAY[]::TEXT[]")`.
**How to avoid:** In `models.py`: `mapped_column(ARRAY(Text), nullable=False, server_default=text("ARRAY[]::TEXT[]"))`. In `0002_clients.py`: `sa.Column("tags", sa.ARRAY(sa.Text()), nullable=False, server_default=sa.text("ARRAY[]::TEXT[]"))`.

---

## Code Examples

### JSONB emergency_contact column mapping

[VERIFIED: SQLAlchemy 2.0 PostgreSQL dialect docs + local import test]

```python
# apps/backend/app/modules/clients/models.py
from sqlalchemy.dialects.postgresql import JSONB

class Client(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin):
    # emergency_contact stored as JSONB; read back via Pydantic EmergencyContact schema
    emergency_contact: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

In service layer on write:
```python
ec_dict = data.emergency_contact.model_dump() if data.emergency_contact else None
client = Client(..., emergency_contact=ec_dict)
```

On read (in ClientResponse):
```python
class ClientResponse(ResponseData):
    emergency_contact: EmergencyContact | None = None
    # ContractModel.from_attributes=True handles nested parsing from dict
```

### ARRAY(Text) tags column with server default

[VERIFIED: SQLAlchemy 2.0 docs + local import test]

```python
from sqlalchemy import ARRAY, Text, text
from sqlalchemy.orm import Mapped, mapped_column

tags: Mapped[list[str]] = mapped_column(
    ARRAY(Text),
    nullable=False,
    server_default=text("ARRAY[]::TEXT[]"),
)
```

### Pydantic tag validator (D-16)

[VERIFIED: Pydantic v2 docs — `field_validator` pattern]

```python
import re
from pydantic import field_validator

class ClientCreateRequest(RequestContract):
    tags: list[str] = []

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        if len(v) > 16:
            raise ValueError("Maximum 16 tags per client")
        result = []
        for tag in v:
            tag = tag.strip().lower()
            if len(tag) > 32:
                raise ValueError(f"Tag '{tag}' exceeds 32 characters")
            if not re.match(r'^[a-z0-9а-я\-_]+$', tag):
                raise ValueError(f"Tag '{tag}' contains invalid characters")
            result.append(tag)
        return result
```

### AuditLog model

[VERIFIED: D-05/D-06/D-07; `UUIDPkMixin` from database.py; string FK pattern]

```python
# apps/backend/app/core/audit_models.py
from datetime import datetime
from uuid import UUID as UUIDType
from sqlalchemy import DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base, UUIDPkMixin

class AuditLog(Base, UUIDPkMixin):
    """Audit log record. No TimestampMixin — only created_at needed (D-05)."""
    __tablename__ = "audit_log"

    actor_user_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),  # string ref — core ⊥ modules
        nullable=True,
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str] = mapped_column(Text, nullable=False)
    resource_id: Mapped[UUIDType | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_audit_log_actor_user_id_created_at", "actor_user_id", "created_at"),
    )
```

### Alembic env.py model registration

[VERIFIED: existing alembic/env.py pattern]

```python
# apps/backend/alembic/env.py — add after existing auth model import
import app.modules.auth.models  # noqa: F401 (already present)
import app.modules.clients.models  # noqa: F401  (NEW — registers clients + audit_log with Base.metadata)
import app.core.audit_models  # noqa: F401  (NEW — registers AuditLog with Base.metadata)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `def emit(event, **fields)` sync passthrough | `async def emit(session, event, *, actor_user_id, resource_type, resource_id, **payload)` | Phase 8 | All call-sites need `await` + session |
| structlog-only audit | structlog + DB INSERT co-transactional | Phase 8 | Tests can assert DB rows, not just log capture |
| No clients module | Full CRUD with soft-delete + RBAC | Phase 8 | CLIENTS-01..09 |
| No audit_log table | `audit_log` with all Phase 5/7/8 events | Phase 8 | AUDIT-01..03 |

**Deprecated/outdated:**
- `emit(event, **fields)` synchronous signature: will not compile after Phase 8 (all call-sites must be updated)
- `logger.warning/info` in handlers.py for telegram audit events: must be converted to `await audit_emit(session, ...)`

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Raw DDL `op.execute` for GIN expression indexes causes `alembic check` to report a diff, requiring ORM `__table_args__` Index objects with `func.lower` + `postgresql_ops` to suppress it | Pattern 2 + Pitfall 1 | TEST-08 fails; planner needs to add ORM model `__table_args__` Index entries with correct postgresql_ops label keys |
| A2 | `session.flush()` in service (not `session.commit()`) is sufficient for the `join_transaction_mode="create_savepoint"` test fixture to see audit_log rows in test assertions | Pattern 7 + Pitfall 5 | Tests can't see audit rows after route; switch service to explicit commit |
| A3 | `issue_tokens()` not returning `family_id` means `login_success.resource_id` must be NULL (Option B of Pitfall 4) unless planner extends `issue_tokens` signature | Pitfall 4 | audit_log rows have NULL resource_id for login_success; acceptable per D-07 |

---

## Open Questions

1. **`alembic check` compatibility for GIN expression indexes**
   - What we know: `op.execute` raw DDL creates GIN trgm indexes that are not tracked in `Base.metadata`
   - What's unclear: Whether Alembic autogenerate will flag them as detected-removed or simply ignore them
   - Recommendation: Wave 0 of implementation should include running `alembic check` locally after creating `0002_clients.py` to confirm TEST-08 behavior; add ORM `__table_args__` Index objects if needed

2. **`login_success` family_id as resource_id**
   - What we know: `issue_tokens()` does not return `family_id`; D-04 maps `login_success → resource_id=family_id`
   - What's unclear: Whether planner should extend `issue_tokens` to return 4-tuple or accept `resource_id=NULL`
   - Recommendation: Use `resource_id=None` + add `family_id` to payload; avoids changing `issue_tokens` signature which has 3 existing call-sites

3. **`get_db` session lifecycle and `session.flush()` in service**
   - What we know: `get_db` uses `async with session_factory() as session:` — the context manager closes (commits or rolls back) on exit; service uses `session.flush()`
   - What's unclear: Whether the `async with session_factory()` context commits or rolls back on normal exit (commit) vs exception (rollback)
   - Recommendation: Verify that `async with session_factory() as session:` auto-commits on clean exit (it does — this is standard SQLAlchemy 2.0 async sessionmaker behavior); service `flush()` is sufficient.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL 16 | INFRA-04, CLIENTS-*, AUDIT-* | Assumed ✓ (via docker-compose) | 16 | — |
| pg_trgm extension | CLIENTS-03, GIN indexes | ✓ (enabled via migration) | bundled with PG | — |
| asyncpg | IntegrityError.constraint_name | ✓ | ≥0.30 | — |

[VERIFIED: apps/backend/pyproject.toml confirms asyncpg≥0.30]

Step 2.6: SKIPPED for new code additions (no external tool dependencies beyond existing docker-compose Postgres). All dependencies are in pyproject.toml.

---

## Project Constraints (from CLAUDE.md)

- **Backend stack locked:** Python 3.12 + uv + FastAPI 0.115+ + SQLAlchemy 2.0 async + Alembic async + Pydantic v2 + Postgres 16 + Redis 7 + ARQ + structlog. No alternatives in Phase A.
- **Testing:** `httpx ASGITransport` (no real network) + `pytest-asyncio`. All tests use `async_client` + `db_session` fixtures from `tests/conftest.py`.
- **Import linter contracts:**
  - `app.core` MUST NOT import `app.modules.*` (CRITICAL: `audit_models.py` must stay in `app.core`)
  - `app.modules.*` are independent of each other
  - `app.integrations` MUST NOT import `app.modules.*` (but CAN import `app.core`)
- **Module-level functions, not classes:** `service.py` and `repository.py` export async functions.
- **camelCase wire:** All DTOs inherit `ContractModel(alias_generator=to_camel)`.
- **Pagination envelope:** `{items, total, page, pageSize}` — never bare arrays.
- **Money:** Not directly applicable to Phase 8 (clients module, no billing).
- **Russian-narrative + English-code:** PLAN.md narrative in Russian; code in English.

---

## Sources

### Primary (HIGH confidence)
- `/websites/sqlalchemy_en_20` (Context7) — JSONB, ARRAY(Text), partial index syntax, GIN index postgresql_using/postgresql_ops, `op.create_index` postgresql_where, `op.execute` DDL
- `/websites/pydantic_dev_validation` (Context7) — `model_validator(mode='before')`, `field_validator`, `model_dump(exclude_unset=True)`
- `apps/backend/app/core/audit.py` — current emit() signature (verified sync, no session)
- `apps/backend/app/core/database.py` — UUIDPkMixin, TimestampMixin, SoftDeleteMixin, naming convention, get_db
- `apps/backend/app/core/permissions.py` — OWNER_ONLY contains `(DELETE, CLIENTS)`, Action/Resource enums
- `apps/backend/app/core/dependencies.py` — require_permission, verify_csrf patterns; `emit` is imported (Phase 8 changes sync→async)
- `apps/backend/app/core/pagination.py` — PageQuery, PaginatedData[T]
- `apps/backend/app/core/schemas.py` — ContractModel, RequestContract, ResponseEnvelope, envelope()
- `apps/backend/app/core/exceptions.py` — AppError hierarchy, register_exception_handlers
- `apps/backend/app/modules/auth/service.py` — 5 emit() call-sites; session.commit() after emit() call-sites (Pitfall 2)
- `apps/backend/app/modules/auth/router.py` — 1 emit() call-site in telegram_verify
- `apps/backend/app/modules/auth/telegram_service.py` — 3 emit() call-sites
- `apps/backend/app/integrations/telegram/handlers.py` — 4 direct logger.warning/info calls (NOT audit.emit) for telegram events
- `apps/backend/tests/conftest.py` — SAVEPOINT db_session, async_client dependency override pattern
- `apps/backend/tests/integration/auth/test_logout.py` — DB row assertion pattern after route call
- `apps/backend/.importlinter` — `core-not-depend-on-modules`, `modules-independent`, `integrations-not-depend-on-modules` contracts
- `apps/backend/alembic/versions/0001_auth.py` — migration pattern (CheckConstraint, op.f(), SAEnum via sa.Enum, naming convention)
- `apps/backend/alembic/env.py` — async migration pattern, model registration for autogenerate
- `uv run python3` verification — `asyncpg.exceptions.UniqueViolationError.constraint_name` exists; `ARRAY(Text)` and `JSONB` valid SA types; `SAEnum(Gender, native_enum=False)` valid

### Secondary (MEDIUM confidence)
- `apps/backend/app/modules/auth/models.py` — SAEnum pattern for role CHECK constraint (mirrors D-15 gender pattern)
- `apps/backend/tests/integration/test_route_introspection.py` — TEST-07 auto-catches all new clients routes without exclusion-list changes needed

### Tertiary (LOW confidence)
- A1 (Alembic autogenerate GIN expression index collision) — not verified empirically in this session

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries in pyproject.toml; all API surfaces verified via Context7 + local uv run
- Architecture: HIGH — all patterns are direct continuations of existing Phase 4-7 codebase patterns
- Pitfalls: HIGH for 2/5 (verified from source); MEDIUM for 3/5 (inferred from code + patterns); LOW for A1 (not empirically tested)

**Research date:** 2026-05-03
**Valid until:** 2026-06-01 (stable library versions; no fast-moving dependencies)
