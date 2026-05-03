# Phase 8: Clients Module + Audit Log — Pattern Map

**Mapped:** 2026-05-03
**Files analyzed:** 22 (new/modified)
**Analogs found:** 20 / 22

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/core/audit_models.py` | model | CRUD | `app/modules/auth/models.py` (UUIDPkMixin, PgUUID, ForeignKey string ref) | role-match |
| `app/core/audit.py` | cross-cutting infra | event-driven | itself (Phase 5 sync stub) | self-upgrade |
| `app/modules/clients/models.py` | model | CRUD | `app/modules/auth/models.py` (SAEnum, Mapped, TimestampMixin, SoftDeleteMixin) | exact |
| `app/modules/clients/schemas.py` | schema | request-response | `app/modules/auth/schemas.py` + `app/core/pagination.py` | role-match |
| `app/modules/clients/repository.py` | repository | CRUD | `app/modules/auth/service.py` inline `select(User)` patterns | partial-match |
| `app/modules/clients/service.py` | service | CRUD + event-driven | `app/modules/auth/service.py` (module-level async, emit call-sites) | role-match |
| `app/modules/clients/router.py` | router | request-response | `app/modules/auth/router.py` (require_permission, ResponseEnvelope) | exact |
| `app/modules/clients/__init__.py` | config wiring | — | `app/modules/auth/__init__.py` | exact |
| `alembic/versions/0002_clients.py` | migration | batch | `alembic/versions/0001_auth.py` (op.create_table, op.f(), CheckConstraint) | exact |
| `alembic/env.py` | config wiring | — | itself (add model imports) | self-update |
| `app/main.py` | config wiring | — | itself (include_router pattern) | self-update |
| `app/api/v1/router.py` | config wiring | — | itself (include_router pattern) | self-update |
| `app/core/exceptions.py` | cross-cutting infra | — | itself (AppError subclasses) | self-update |
| `app/modules/auth/service.py` | call-site update | event-driven | itself (emit → async emit) | self-update |
| `app/modules/auth/router.py` | call-site update | event-driven | itself (emit → async emit) | self-update |
| `app/modules/auth/telegram_service.py` | call-site update | event-driven | itself (emit → async emit) | self-update |
| `app/integrations/telegram/handlers.py` | call-site update | event-driven | itself (logger.* → audit_emit) | self-update |
| `tests/integration/clients/test_clients_list.py` | test | request-response | `tests/integration/auth/test_login.py` | exact |
| `tests/integration/clients/test_clients_crud.py` | test | CRUD | `tests/integration/auth/test_logout.py` (DB row assertions) | exact |
| `tests/integration/clients/test_clients_rbac.py` | test | request-response | `tests/integration/rbac/test_owner_only.py` | exact |
| `tests/integration/clients/test_audit_writes.py` | test | CRUD | `tests/integration/auth/test_logout.py` (select(Model) after route call) | exact |
| `tests/integration/auth/test_audit_existing_events.py` | test | CRUD | `tests/integration/auth/test_logout.py` | exact |

---

## Pattern Assignments

---

### `app/core/audit_models.py` (model, NEW)

**Analog:** `app/modules/auth/models.py` (lines 1-19, 23-60)

**Imports pattern** (from analog lines 11-19):
```python
from datetime import datetime
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UUIDPkMixin
```

**Core ORM declaration pattern** (from analog lines 23-44):
```python
class User(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    role: Mapped[Role] = mapped_column(
        SAEnum(Role, native_enum=False, length=16, validate_strings=True, ...),
        nullable=False,
    )
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'reception')", name="role"),
    )
```

**Divergence for AuditLog:** Uses ONLY `UUIDPkMixin` (no `TimestampMixin` — `created_at` added manually with `server_default=func.now()`, no `updated_at`). FK to `'users.id'` via string reference preserves `core ⊥ modules` contract. Columns: `actor_user_id PgUUID NULL FK`, `action TEXT NOT NULL`, `resource_type TEXT NOT NULL`, `resource_id PgUUID NULL`, `payload JSONB NOT NULL DEFAULT '{}'::jsonb`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`. Also needs `Index('ix_audit_log_actor_user_id_created_at', 'actor_user_id', 'created_at')` in `__table_args__`.

---

### `app/core/audit.py` (cross-cutting infra, MODIFY)

**Analog:** itself at `app/core/audit.py` (lines 32-43) — current sync passthrough

**Current body** (lines 32-43):
```python
def emit(event: str, **fields: Any) -> None:
    """Emit an audit event. Phase 5: structlog INFO. Phase 8: structlog INFO + DB INSERT."""
    structlog.get_logger("audit").info(event, **fields)
```

**New signature and body to replace it with:**
```python
# New imports needed at top of file:
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.audit_models import AuditLog

async def emit(
    session: AsyncSession,
    event: str,
    *,
    actor_user_id: UUID | None,
    resource_type: str,
    resource_id: UUID | None = None,
    **payload: Any,
) -> None:
    """Emit an audit event: structlog INFO + co-transactional DB INSERT (D-04).

    NO session.commit() here — caller owns the transaction (D-03).
    """
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
```

**Critical:** `audit_models.py` must be created before this file is modified.

---

### `app/modules/clients/models.py` (model, NEW)

**Analog:** `app/modules/auth/models.py` (entire file — lines 1-144)

**Imports pattern** (from analog lines 11-19, extended for ARRAY/JSONB/SAEnum):
```python
from datetime import datetime
from uuid import UUID as UUIDType  # noqa: N811
from enum import StrEnum

from sqlalchemy import ARRAY, BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Index, Text, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPkMixin, SoftDeleteMixin
```

**SAEnum pattern for gender** (from analog lines 36-45 — User.role is the exact pattern):
```python
# Analog (auth/models.py lines 36-45):
role: Mapped[Role] = mapped_column(
    SAEnum(
        Role,
        native_enum=False,
        length=16,
        validate_strings=True,
        values_callable=lambda enum_cls: [e.value for e in enum_cls],
    ),
    nullable=False,
)
# Corresponding __table_args__ (line 59):
__table_args__ = (
    CheckConstraint("role IN ('owner', 'reception')", name="role"),
)
```

**ARRAY(Text) tags column** (new to Phase 8 — no direct analog in codebase, but SA type is standard):
```python
from sqlalchemy import ARRAY, text

tags: Mapped[list[str]] = mapped_column(
    ARRAY(Text),
    nullable=False,
    server_default=text("ARRAY[]::TEXT[]"),
)
```

**JSONB emergency_contact column** (new to Phase 8):
```python
from sqlalchemy.dialects.postgresql import JSONB

emergency_contact: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

**Partial unique index pattern** — documented in `app/core/database.py` SoftDeleteMixin docstring (lines 84-99):
```python
# SoftDeleteMixin docstring describes exactly this pattern:
__table_args__ = (
    Index(
        "uq_clients_phone_alive", "phone", unique=True,
        postgresql_where=text("deleted_at IS NULL"),
    ),
    # GIN trigram indexes referenced only in migration (not in __table_args__
    # unless needed to suppress alembic check diff — see Pitfall 1 in RESEARCH.md)
)
```

**Divergence:** `Client` mixes all four base classes: `Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin`. `User` does not use `SoftDeleteMixin`. `Gender(StrEnum)` lives in this file. ForeignKey `created_by_user_id` uses `PgUUID(as_uuid=True)` + `ForeignKey("users.id", ondelete="RESTRICT")`.

---

### `app/modules/clients/schemas.py` (schema, NEW)

**Analog 1:** `app/modules/auth/schemas.py` (entire file — lines 1-83)
**Analog 2:** `app/core/pagination.py` (lines 1-44)
**Analog 3:** `app/core/schemas.py` lines 24-73 (ContractModel/RequestContract/ResponseData)

**Base import pattern** (from auth/schemas.py lines 14-19):
```python
from pydantic import EmailStr, Field
from app.core.schemas import RequestContract, ResponseData
```

**For clients schemas, extended base imports:**
```python
from datetime import datetime
from uuid import UUID
from typing import Any
from pydantic import Field, field_validator, model_validator
from app.core.pagination import PageQuery
from app.core.schemas import RequestContract, ResponseData
```

**ResponseData subclass pattern** (auth/schemas.py lines 29-34):
```python
class UserPublic(ResponseData):
    id: UUID
    role: Role
    full_name: str  # → fullName on wire
```

**RequestContract subclass pattern** (auth/schemas.py lines 22-27):
```python
class LoginRequest(RequestContract):
    email: EmailStr
    password: str = Field(min_length=12)
```

**PageQuery inheritance pattern** (pagination.py lines 19-29):
```python
class PageQuery(RequestContract):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
```
`ClientListQuery` subclasses `PageQuery` and adds `q`, `tag`, `gender`, `created_from`, `created_to`, `has_telegram`, `sort` fields.

**D-01 null-rejection validator** (from RESEARCH.md Pattern 6):
```python
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

**D-16 tag validator** (from RESEARCH.md Code Examples):
```python
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

**Divergence:** `ClientResponse` uses `from_attributes=True` (inherited from `ContractModel`) to construct from ORM `Client` instance. `emergency_contact: EmergencyContact | None = None` relies on Pydantic parsing from a dict (JSONB column).

---

### `app/modules/clients/repository.py` (repository, NEW)

**Analog:** `app/modules/auth/service.py` — specifically the inline `select(User)` patterns (lines 110-112, 252-257, 302-303, 424-426)

**No direct repository-layer analog exists in the codebase.** This is the first module to introduce the explicit repository/service split (D-02). The closest patterns are the service-level DB reads in `auth/service.py`.

**Pattern to follow from auth/service.py (lines 110-112):**
```python
user = await session.scalar(select(User).where(User.email == email_lower))
```

**Pattern for select + filter (analog from auth/service.py lines 424-429):**
```python
row = await session.scalar(
    select(RefreshToken).where(RefreshToken.token_hash == presented_hash)
)
if row is None:
    return
```

**Repository function signatures to produce** (module-level async, D-18):
```python
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.clients.models import Client
from app.modules.clients.schemas import ClientCreateRequest, ClientUpdateRequest

async def get_alive(session: AsyncSession, client_id: UUID) -> Client | None:
    """Return alive (not soft-deleted) client by id, or None."""
    return await session.scalar(
        select(Client).where(Client.id == client_id, Client.deleted_at.is_(None))
    )

async def list_alive(
    session: AsyncSession, query: ClientListQuery
) -> tuple[list[Client], int]:
    """Return (items, total) for paginated alive client list with filters applied."""
    # Build stmt with WHERE deleted_at IS NULL + optional filters + ORDER BY + LIMIT/OFFSET
    ...
```

**ARRAY containment filter pattern** (D-13 — new, no codebase analog):
```python
from sqlalchemy import text
# tag exact match: ANY() containment operator
stmt = stmt.where(text(":tag = ANY(tags)").bindparams(tag=query.tag))
```

**Divergence:** `repository.py` is the ONLY file allowed to import `Client` model (CLIENTS-09). Service layer imports repository functions, not `Client` directly. Pagination uses `func.count()` subquery for total.

---

### `app/modules/clients/service.py` (service, NEW)

**Analog:** `app/modules/auth/service.py` (entire file — lines 1-499)

**Module-level function pattern** (from analog lines 88-139):
```python
async def authenticate(
    session: AsyncSession,
    redis: Redis,
    email: str,
    password: str,
    *,
    ip: str | None = None,
) -> User:
    """..."""
    # ... validation ...
    # ... DB call ...
    # emit at end
    emit("login_success", ...)
    return user
```

**Flush-not-commit pattern for co-transactional writes** (from analog lines 316-318 — `session.flush()` before the emit, within `async with session.begin()`):
```python
# Closest flush analog in auth/service.py lines 316-318:
session.add(new_row)
await session.flush()  # used inside rotate_refresh's session.begin() block
```

**IntegrityError handling** (from RESEARCH.md Pattern 5):
```python
from sqlalchemy.exc import IntegrityError

async def create_client(
    session: AsyncSession, actor: CurrentUser, data: ClientCreateRequest
) -> Client:
    try:
        client = await repository.insert_client(session, actor.id, data)
        await session.flush()
    except IntegrityError as e:
        await session.rollback()
        orig = e.orig
        constraint = getattr(orig, "constraint_name", None)
        if constraint == "uq_clients_phone_alive":
            raise PhoneExistsError("phone_exists") from e
        raise  # re-raise other IntegrityErrors as 500
    await audit.emit(
        session, "client_created",
        actor_user_id=actor.id,
        resource_type="client",
        resource_id=client.id,
        full_name=f"{client.last_name} {client.first_name}",
        phone=client.phone,
        has_email=client.email is not None,
        has_telegram=client.telegram_user_id is not None,
    )
    return client
```

**PATCH exclude_unset pattern** (D-01, from RESEARCH.md Pattern 6):
```python
updates = data.model_dump(exclude_unset=True)
for key, value in updates.items():
    setattr(client, key, value)
```

**D-09 no-op PATCH skip** (service compares old vs new before emitting):
```python
if not updates or all(getattr(client, k) == v for k, v in updates.items()):
    return client  # no-op: no audit emit, no flush
```

**Divergence from auth/service.py:** Clients service uses `session.flush()` not `session.commit()`. The `get_db` dependency's `async with session_factory() as session:` context manager auto-commits on clean route exit. Auth services use `session.commit()` explicitly because they open `async with session.begin():` blocks internally; clients service does NOT open its own `session.begin()` block — it lets the router's `get_db` dependency manage the transaction.

---

### `app/modules/clients/router.py` (router, NEW)

**Analog:** `app/modules/auth/router.py` (entire file — lines 1-271)

**Imports pattern** (from analog lines 22-57):
```python
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission, verify_csrf
from app.core.schemas import ResponseEnvelope, envelope
from app.core.pagination import PaginatedData
from app.core.permissions import Action, Resource
from app.modules.clients import service
from app.modules.clients.schemas import (
    ClientCreateRequest, ClientUpdateRequest, ClientResponse, ClientListQuery
)
```

**Endpoint with require_permission pattern** (from analog lines 115-138, adapted for RBAC):
```python
# Auth analog for mutation with verify_csrf (logout, lines 115-138):
@router.post("/logout", response_model=ResponseEnvelope[None])
async def logout(
    request: Request,
    response: Response,
    _user: Annotated[CurrentUser, Depends(require_authenticated())],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[None]:
    ...

# Clients router pattern for require_permission mutation:
@router.post("", response_model=ResponseEnvelope[ClientResponse], status_code=201)
async def create_client(
    payload: ClientCreateRequest,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.EDIT, Resource.CLIENTS))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientResponse]:
    client = await service.create_client(session, actor, payload)
    return envelope(ClientResponse.model_validate(client))
```

**GET endpoint with require_permission** (D-21: VIEW for all read routes):
```python
@router.get("", response_model=ResponseEnvelope[PaginatedData[ClientResponse]])
async def list_clients(
    query: Annotated[ClientListQuery, Depends()],
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.CLIENTS))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[ClientResponse]]:
    result = await service.list_clients(session, query)
    return envelope(result)
```

**envelope() helper pattern** (auth/router.py line 82):
```python
return envelope(LoginResponse(user=UserPublic.model_validate(user)))
# → for clients:
return envelope(ClientResponse.model_validate(client))
```

**Divergence:** Auth router uses `require_authenticated()` for auth-specific routes; clients router uses `require_permission(action, resource)` for all 5 endpoints (RBAC-02 requires `require_permission` on every business route). DELETE route uses `Action.DELETE, Resource.CLIENTS` which is in `OWNER_ONLY` — no additional code needed, RBAC handles it.

---

### `alembic/versions/0002_clients.py` (migration, NEW)

**Analog:** `alembic/versions/0001_auth.py` (entire file — lines 1-134)

**File header pattern** (from analog lines 1-19):
```python
"""clients_and_audit_log

Revision ID: 0002_clients
Revises: 0001_auth
Create Date: ...
"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0002_clients"
down_revision: str | None = "0001_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**op.create_table with CheckConstraint and op.f() naming** (from analog lines 23-52):
```python
op.create_table(
    "users",
    sa.Column("role",
        sa.Enum("owner", "reception", name="role", native_enum=False, length=16),
        nullable=False,
    ),
    sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.CheckConstraint("role IN ('owner', 'reception')", name=op.f("ck_users_role")),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    sa.UniqueConstraint("email", name=op.f("uq_users_email")),
)
```

**op.create_index pattern** (from analog lines 118-123):
```python
op.create_index(
    "ix_refresh_tokens_user_id_family_id",
    "refresh_tokens",
    ["user_id", "family_id"],
    unique=False,
)
```

**Partial unique index** (new to Phase 8):
```python
from sqlalchemy import text
op.create_index(
    "uq_clients_phone_alive",
    "clients",
    ["phone"],
    unique=True,
    postgresql_where=text("deleted_at IS NULL"),
)
```

**GIN trigram expression index** (use raw DDL — RESEARCH.md Pattern 2 + Pitfall 1):
```python
op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
op.execute(
    "CREATE INDEX ix_clients_last_name_trgm "
    "ON clients USING gin (lower(last_name) gin_trgm_ops)"
)
op.execute(
    "CREATE INDEX ix_clients_first_name_trgm "
    "ON clients USING gin (lower(first_name) gin_trgm_ops)"
)
```

**Downgrade order** (from analog lines 127-133 — reverse of upgrade):
```python
def downgrade() -> None:
    op.drop_index("ix_audit_log_actor_user_id_created_at", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index("ix_clients_first_name_trgm", table_name="clients")
    op.drop_index("ix_clients_last_name_trgm", table_name="clients")
    op.drop_index("uq_clients_phone_alive", table_name="clients")
    op.drop_table("clients")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
```

---

### `alembic/env.py` (config wiring, MODIFY)

**Analog:** itself at lines 23-24 — add model imports after the existing `app.modules.auth.models` import:
```python
# Current (line 24):
import app.modules.auth.models  # noqa: F401

# Add after (Phase 8):
import app.modules.clients.models  # noqa: F401
import app.core.audit_models  # noqa: F401
```

---

### `app/main.py` (config wiring, MODIFY)

**Analog:** itself at lines 82 — add `include_router` call following the existing pattern:
```python
# Current (line 82):
app.include_router(api)

# In app/api/v1/router.py, add (following line 13 pattern):
v1.include_router(clients_router, prefix="/clients", tags=["clients"])
```

---

### `app/core/exceptions.py` (cross-cutting infra, MODIFY)

**Analog:** itself — add three new `AppError` subclasses following the existing pattern (lines 19-78):
```python
# Pattern to follow (existing examples):
class NotFoundError(AppError):
    code = "not_found"
    status_code = 404

class ConflictError(AppError):
    code = "conflict"
    status_code = 409

class ValidationAppError(AppError):
    code = "validation_error"
    status_code = 422

# New subclasses for Phase 8 (add at bottom of file):
class ClientNotFoundError(NotFoundError):
    code = "client_not_found"

class PhoneExistsError(ConflictError):
    code = "phone_exists"

class InvalidPhoneError(ValidationAppError):
    code = "invalid_phone"
```

---

### `app/modules/auth/service.py` (call-site update, MODIFY)

**Analog:** itself — update all 5 `emit(...)` call-sites to `await audit.emit(session, ...)` per D-04 mapping table.

**Before/after per call-site** (lines 118-124, 138, 240, 381, 451, 497):

```python
# Line 118-124 — login_failed (BEFORE):
emit("login_failed", email=email_lower, reason="invalid_credentials", ip=ip)

# AFTER (D-04 mapping: actor_user_id=None, resource_type='login_attempt'):
await audit.emit(session, "login_failed",
    actor_user_id=None, resource_type="login_attempt",
    email=email_lower, reason="invalid_credentials", ip=ip)

# Line 138 — login_success (BEFORE):
emit("login_success", user_id=str(user.id), email=email_lower, ip=ip, channel="email_password")

# AFTER (D-04: actor_user_id=user.id, resource_type='session', resource_id=None per Pitfall 4 Option B):
await audit.emit(session, "login_success",
    actor_user_id=user.id, resource_type="session", resource_id=None,
    email=email_lower, ip=ip, channel="email_password")

# Lines 381 + 451 + 497 — family_reuse / session_revoked / session_revoked_all:
# CRITICAL (Pitfall 2): move emit() call to BEFORE session.commit() in each function
# so the AuditLog INSERT is covered by the same transaction.
```

**Function signatures require `session` parameter.** `authenticate()` already takes `session` (line 89). `revoke_session()` already takes `session` (line 396). `revoke_all_sessions()` already takes `session` (line 459). `revoke_sessions_on_password_change()` already takes `session` (line 224).

---

### `app/modules/auth/router.py` (call-site update, MODIFY)

**Analog:** itself at line 269 — update `emit("login_success", ...)` in `telegram_verify` endpoint:

```python
# Line 269 (BEFORE):
emit("login_success", user_id=str(user.id), ip=ip, channel="telegram")

# AFTER (session already in scope from Depends(get_db)):
await audit.emit(session, "login_success",
    actor_user_id=user.id, resource_type="session", resource_id=None,
    ip=ip, channel="telegram")
```

Also update `emit` import from sync to module reference: `from app.core import audit` (then call `await audit.emit(...)`).

---

### `app/modules/auth/telegram_service.py` (call-site update, MODIFY)

**Analog:** itself — 3 `emit(...)` call-sites at lines 101, 189, 256.

```python
# Line 101 — telegram_deep_link_issued (BEFORE):
emit("telegram_deep_link_issued", deep_link_token_hash=token_hash)

# AFTER (D-04: actor_user_id=None, resource_type='otp'):
await audit.emit(session, "telegram_deep_link_issued",
    actor_user_id=None, resource_type="otp",
    deep_link_token_hash=token_hash)

# Line 189 — otp_issued (BEFORE):
emit("otp_issued", user_id=str(user.id), chat_id=telegram_chat_id)

# AFTER (D-04: actor_user_id=user.id, resource_type='otp'):
await audit.emit(session, "otp_issued",
    actor_user_id=user.id, resource_type="otp",
    chat_id=telegram_chat_id)

# Line 256 — otp_consumed (BEFORE):
emit("otp_consumed", user_id=str(user.id))

# AFTER:
await audit.emit(session, "otp_consumed",
    actor_user_id=user.id, resource_type="otp")
```

Note: `start_deep_link()` (line 80) calls `emit` AFTER `await session.commit()` — Pitfall 2 applies. Move the emit call BEFORE `session.commit()`.

---

### `app/integrations/telegram/handlers.py` (call-site update, MODIFY)

**Analog:** itself — 4 `logger.warning/info` calls at lines 114-119, 128-133, 152-153, 157 that must be replaced with `await audit_emit(...)`.

**Critical:** Add `from app.core.audit import emit as audit_emit` at top of file (import is allowed: `app.integrations → app.core` is permitted per `.importlinter`).

```python
# Add import at top of file:
from app.core.audit import emit as audit_emit

# Line 114-119 — telegram_unknown_start (BEFORE):
logger.warning(
    "telegram_unknown_start",
    username=username, chat_id=chat_id,
    deep_link_token_hash=deep_link_token_hash,
)

# AFTER (inside `async with ctx.session_factory() as session:` block):
await audit_emit(session, "telegram_unknown_start",
    actor_user_id=None, resource_type="otp",
    username=username, chat_id=chat_id,
    deep_link_token_hash=deep_link_token_hash)

# Line 128-133 — telegram_replay_attempt (BEFORE):
logger.info("telegram_replay_attempt", chat_id=chat_id, deep_link_token_hash=deep_link_token_hash)

# AFTER:
await audit_emit(session, "telegram_replay_attempt",
    actor_user_id=None, resource_type="otp",
    chat_id=chat_id, deep_link_token_hash=deep_link_token_hash)

# Line 152-153 — telegram_dm_blocked (BEFORE):
logger.warning("telegram_dm_blocked", chat_id=chat_id)

# AFTER:
await audit_emit(session, "telegram_dm_blocked",
    actor_user_id=None, resource_type="otp", chat_id=chat_id)

# Line 157 — telegram_dm_failed (BEFORE):
logger.warning("telegram_dm_failed", chat_id=chat_id, error=send_result.error)

# AFTER:
await audit_emit(session, "telegram_dm_failed",
    actor_user_id=None, resource_type="otp",
    chat_id=chat_id, error=send_result.error)
```

Note: All 4 events happen inside `async with ctx.session_factory() as session:` (line 104), so `session` is in scope. The `return` statements after `telegram_unknown_start` and `telegram_replay_attempt` must come AFTER the `await audit_emit(...)` call.

---

### Test files (tests/integration/clients/*.py)

**Analog:** `tests/integration/auth/test_login.py` (lines 1-159) and `tests/integration/auth/test_logout.py` (lines 1-238)

**Fixture pattern — seed user + redis_clean** (from test_login.py lines 25-44):
```python
@pytest_asyncio.fixture
async def redis_clean(app: FastAPI) -> Redis:
    client: Redis = app.state.redis
    await client.flushdb()
    return client

@pytest_asyncio.fixture
async def seeded_owner(db_session: AsyncSession, redis_clean: Redis) -> User:
    user = User(
        email=OWNER_EMAIL,
        password_hash=await hash_password(OWNER_PASSWORD),
        role=Role.OWNER,
        full_name="Login Owner",
    )
    db_session.add(user)
    await db_session.commit()
    return user
```

**Test function signature pattern** (from test_login.py lines 47-51):
```python
async def test_login_happy_returns_envelope_and_three_cookies(
    async_client: AsyncClient,
    seeded_owner: User,
) -> None:
    response = await async_client.post("/api/v1/auth/login", json={...})
    assert response.status_code == 200, response.text
    body = response.json()
    assert "data" in body
```

**DB row assertion pattern after route call** (from test_logout.py lines 63-104 — the canonical SAVEPOINT pattern):
```python
# From test_logout.py lines 72-80:
rows_before = (
    await db_session.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == seeded_owner.id,
            RefreshToken.revoked_at.is_(None),
        )
    )
).all()
assert len(rows_before) == 1
```

**For audit_writes.py, apply same pattern with AuditLog:**
```python
from sqlalchemy import select
from app.core.audit_models import AuditLog

rows = (await db_session.scalars(
    select(AuditLog).where(AuditLog.action == "client_created")
)).all()
assert len(rows) == 1
row = rows[0]
assert row.actor_user_id == seeded_owner.id
assert row.resource_type == "client"
assert row.resource_id is not None
```

**RBAC test pattern** (from tests/integration/rbac/test_owner_only.py lines 1-81):
```python
# For test_clients_rbac.py, adapt from:
async def test_reception_forbidden_on_every_owner_only_pair(
    reception_client: AsyncClient,
    action: Action,
    resource: Resource,
) -> None:
    r = await reception_client.get(f"/_t/{action.value}/{resource.value}")
    assert r.status_code == 403, r.text
    body = r.json()
    assert body["code"] == "forbidden"
```

**CSRF header pattern** (from test_logout.py line 87):
```python
headers={"X-CSRF-Token": async_client.cookies["sportzal_csrf"]}
```

**Envelope shape assertion** (from test_login.py lines 58-61):
```python
body = response.json()
assert "data" in body
assert body["data"]["user"]["fullName"] == "Login Owner"
```

**Wire format note:** All response fields are camelCase on wire (`last_name` → `lastName`, `created_at` → `createdAt`, `page_size` → `pageSize`). Test assertions must use camelCase keys.

---

## Shared Patterns

### Authentication / RBAC Gate
**Source:** `app/core/dependencies.py` lines 97-143
**Apply to:** All 5 clients router endpoints
```python
from app.core.dependencies import CurrentUser, require_permission, verify_csrf
from app.core.permissions import Action, Resource

# On every GET:
_actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.CLIENTS))]
# On POST/PATCH:
actor: Annotated[CurrentUser, Depends(require_permission(Action.EDIT, Resource.CLIENTS))]
_csrf: Annotated[None, Depends(verify_csrf)]
# On DELETE:
actor: Annotated[CurrentUser, Depends(require_permission(Action.DELETE, Resource.CLIENTS))]
_csrf: Annotated[None, Depends(verify_csrf)]
```

### CSRF Enforcement on Mutations
**Source:** `app/core/dependencies.py` lines 165-205
**Apply to:** POST /clients, PATCH /clients/{id}, DELETE /clients/{id}
**Pattern:** Declare `_csrf: Annotated[None, Depends(verify_csrf)]` AFTER the `require_permission` dep in the signature so 401 fires before 403 (RBAC-04).

### ResponseEnvelope Wrapping
**Source:** `app/core/schemas.py` lines 51-73 + `envelope()` helper
**Apply to:** All 5 router endpoints
```python
from app.core.schemas import ResponseEnvelope, envelope
return envelope(ClientResponse.model_validate(client))
# For list: return envelope(PaginatedData[ClientResponse](items=..., total=..., page=..., page_size=...))
```

### Error Handling via AppError Hierarchy
**Source:** `app/core/exceptions.py` lines 7-93
**Apply to:** `service.py` (raise) + FastAPI app (register_exception_handlers already in place)
```python
# Raise domain errors in service:
raise ClientNotFoundError("client_not_found")
raise PhoneExistsError("phone_exists")
raise InvalidPhoneError("invalid_phone")
# These ride the existing _app_error_handler → JSONResponse path automatically.
```

### Audit Emission (new co-transactional pattern)
**Source:** `app/core/audit.py` (after Phase 8 modification)
**Apply to:** `service.py` create/update/soft_delete functions; all updated auth call-sites
```python
from app.core import audit
# Always call BEFORE session.flush():
await audit.emit(session, "client_created",
    actor_user_id=actor.id, resource_type="client", resource_id=client.id,
    full_name=..., phone=..., has_email=..., has_telegram=...)
# Then:
await session.flush()  # not session.commit() — get_db manages the transaction
```

### camelCase Wire Format
**Source:** `app/core/schemas.py` lines 24-44 (`ContractModel` with `alias_generator=to_camel`)
**Apply to:** All `ClientCreateRequest`, `ClientUpdateRequest`, `ClientResponse`, `ClientListQuery`
All subclass `RequestContract` or `ResponseData` which inherit from `ContractModel`. Wire format is automatic — no explicit `alias=` needed.

### SAVEPOINT-based Test Fixture
**Source:** `tests/conftest.py` lines 56-143
**Apply to:** All clients test files
```python
# Standard fixture imports for every clients test file:
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import hash_password
from app.modules.auth.models import User
# Use: async_client, db_session fixtures from conftest — they are inherited automatically.
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `app/modules/clients/repository.py` | repository | CRUD | First module to introduce explicit repo/service split; closest analog is inline `select(Model)` calls in auth/service.py |

---

## Critical Divergences and Pitfalls

### Pitfall 2 (from RESEARCH.md): emit() must move BEFORE session.commit()
In `auth/service.py` lines 443-451 (`revoke_session`) and 487-497 (`revoke_all_sessions`), `emit(...)` is called AFTER `await session.commit()`. In Phase 8, `emit` becomes `await audit.emit(session, ...)` which calls `session.add(AuditLog(...))`. If called after commit, the AuditLog INSERT never commits. **Fix: reorder to emit BEFORE commit in each affected function.**

### service.py flush vs commit difference from auth/service.py
Auth service functions call `await session.commit()` explicitly. Clients service uses `await session.flush()` only — the `get_db` dependency's `async with session_factory() as session:` auto-commits on clean route exit. Do not add `session.commit()` inside clients service functions.

### handlers.py audit events need `session` from the existing `async with ctx.session_factory()` block
The `session` variable is already in scope at line 104 inside `start_handler`. The four `logger.warning/info` calls that must become `await audit_emit(session, ...)` are all reached inside this `async with` block, so `session` is available at each call-site.

### Alembic autogenerate and GIN expression indexes (Pitfall 1 from RESEARCH.md)
If raw `op.execute(...)` is used for GIN trgm indexes, `alembic check` (TEST-08) may report a diff. Mitigation: add matching `Index('ix_clients_last_name_trgm', func.lower(Client.last_name), postgresql_using='gin')` objects to `Client.__table_args__`. Verify empirically after migration runs.

---

## Metadata

**Analog search scope:** `apps/backend/app/`, `apps/backend/tests/`, `apps/backend/alembic/`
**Files read:** 22 source files
**Pattern extraction date:** 2026-05-03
