# Phase 43: Multi-User Admin Module — Pattern Map

**Mapped:** 2026-05-19
**Files analyzed:** 14 new + 5 modified = 19
**Analogs found:** 19 / 19 (100% coverage — all targets have strong in-tree analogs)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/backend/app/modules/users/router.py` | router | request-response (CRUD) | `apps/backend/app/modules/clients/router.py` | exact |
| `apps/backend/app/modules/users/service.py` | service | CRUD + audit + email enqueue | `apps/backend/app/modules/clients/service.py` + `auth/service.py:revoke_all_sessions` | exact-composite |
| `apps/backend/app/modules/users/repository.py` | repository | CRUD (list_alive/get_alive + token table CRUD) | `apps/backend/app/modules/clients/repository.py` | exact |
| `apps/backend/app/modules/users/schemas.py` | schema (Pydantic DTO) | request-response | `apps/backend/app/modules/clients/schemas.py` | exact |
| `apps/backend/app/modules/users/permissions.py` | marker module | constant re-export | (no analog — first marker file) | new pattern |
| `apps/backend/app/modules/users/constants.py` | constants | configuration | `apps/backend/app/integrations/email/types.py` (frozen literals) | role-match |
| `apps/backend/app/modules/users/email_templates.py` | template registry | template render | `apps/backend/app/modules/auth/email_templates.py` | exact |
| `apps/backend/alembic/versions/0030_users_lifecycle_columns.py` | migration | DDL | `0011_trainers.py` (is_active) + `0008_freeze.py` (cross-column CHECK) + `0022_users_soft_delete_partial_unique.py` (FK self-ref + alter user) | role-match composite |
| **MOD** `apps/backend/app/core/models.py` | ORM extension | mapping | self (existing `User`) | exact |
| **MOD** `apps/backend/app/modules/auth/service.py` (`invalidate_all_families_for_user`) | service | event-driven | `auth/service.py:revoke_sessions_on_password_change` (D-20 wrapper) | exact |
| **MOD** `apps/backend/app/modules/auth/service.py` (`rotate_refresh` user SELECT) | service | request-response | self (lines 333+) | exact |
| **MOD** `apps/backend/app/main.py` | composition | wiring | `main.py:209-250` (register_payment_recorder, register_email_dispatcher) | exact |
| **MOD** `apps/backend/app/api/v1/router.py` | router aggregator | wiring | `api/v1/router.py:38-67` (include_router pattern) | exact |
| **MOD** `apps/backend/app/core/audit_payloads.py` (UserInvitedPayload +link_copied) | payload schema | additive field | `audit_payloads.py:513-529` (existing payload) | exact |
| **MOD** `tests/unit/test_locked_email_templates_ast.py` | unit test | AST walk | self (existing EMAIL_OTP_LOGIN assertion) | exact |
| `tests/integration/users/test_users_crud.py` | integration test | CRUD | `tests/integration/clients/test_clients_crud.py` | exact |
| `tests/integration/users/test_users_guards.py` | integration test | RBAC + CSRF | `tests/integration/clients/test_clients_rbac.py` | exact |
| `tests/integration/users/test_users_session_invalidation.py` | integration test | event-driven | `tests/integration/auth/test_logout.py` | role-match |
| `tests/integration/users/test_users_invitation_flow.py` | integration test | email sandbox | Phase 42 sandbox email tests (per CONTEXT.md D-42-03) | role-match |
| `tests/integration/users/test_refresh_account_inactive.py` | integration test | anti-oracle | `tests/integration/auth/test_password_reset_no_oracle.py` | exact-pattern |
| `tests/unit/users/test_email_template_render.py` | unit test | snapshot render | (no in-tree analog — first email template render test) | new pattern |

---

## Pattern Assignments

### `apps/backend/app/modules/users/router.py` (router, request-response CRUD)

**Analog:** `apps/backend/app/modules/clients/router.py:1-145`

**Imports pattern** (lines 30-47):
```python
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission, verify_csrf
from app.core.pagination import PaginatedData
from app.core.permissions import Action, Resource
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.clients import service
from app.modules.clients.schemas import (
    ClientCreateRequest,
    ClientListQuery,
    ClientResponse,
    ClientUpdateRequest,
)

router = APIRouter()
```

**Dependency-order pattern — RBAC-04 (lines 16-19 docstring + lines 92-99):**
> `require_permission` declared BEFORE `verify_csrf` so 401 fires before 403.

```python
@router.post(
    "",
    response_model=ResponseEnvelope[ClientResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_client(
    payload: ClientCreateRequest,
    actor: Annotated[
        CurrentUser, Depends(require_permission(Action.EDIT, Resource.CLIENTS))
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientResponse]:
```

**204 DELETE pattern** (lines 124-144):
```python
@router.delete(
    "/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def soft_delete_client(
    client_id: UUID,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.DELETE, Resource.CLIENTS))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await service.soft_delete_client(session, actor, client_id)
    return None
```

**Users router uses `Action.UPDATE` for deactivate/reactivate/invitation-revoke and `Action.LIST` for GET (per D-41-22) and `Resource.USERS` everywhere.**

---

### `apps/backend/app/modules/users/service.py` (service, CRUD + audit + email enqueue)

**Primary analog (CRUD + audit shape):** `apps/backend/app/modules/clients/service.py:1-244`
**Secondary analog (session invalidation wrap + transaction discipline):** `apps/backend/app/modules/auth/service.py:577-625` (revoke_all_sessions)

**Imports pattern** (clients/service.py lines 44-61):
```python
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.dependencies import CurrentUser
from app.core.exceptions import ClientNotFoundError, PhoneExistsError
from app.core.pagination import PaginatedData
from app.modules.clients import repository
from app.modules.clients.models import Client
from app.modules.clients.schemas import (...)
```
For users service, additionally import `get_user_session_invalidator`, `get_email_dispatcher` from `app.core.dependencies` and `TEMPLATES` from `app.modules.users.email_templates`.

**Create + audit + flush + commit ordering — D-03 / D-11 / Phase 12.1** (lines 109-144):
```python
async def create_client(
    session: AsyncSession,
    actor: CurrentUser,
    data: ClientCreateRequest,
) -> ClientResponse:
    """Order: insert → flush (surface DB constraints) → emit audit on success (D-03)."""
    client = await repository.insert_client(session, actor.id, data)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_phone_conflict(exc):
            raise PhoneExistsError("phone_exists") from exc
        raise

    await audit.emit(
        session,
        "client_created",
        actor_user_id=actor.id,
        resource_type="client",
        resource_id=client.id,
        full_name=_full_name(client),
        phone=client.phone,
        has_email=client.email is not None,
        has_telegram=client.telegram_user_id is not None,
    )
    await session.commit()
    return ClientResponse.model_validate(client)
```

**Soft-delete ordering — capture-before-mutate, emit BEFORE flush** (lines 210-243):
```python
async def soft_delete_client(...) -> None:
    client = await repository.get_alive(session, client_id)
    if client is None:
        raise ClientNotFoundError("client_not_found")

    captured_full_name = _full_name(client)  # capture BEFORE mutation
    captured_phone = client.phone

    await repository.soft_delete_client(session, client)
    await audit.emit(  # emit BEFORE flush — soft-delete only flips deleted_at, no constraint risk
        session,
        "client_soft_deleted",
        actor_user_id=actor.id,
        resource_type="client",
        resource_id=client.id,
        full_name=captured_full_name,
        phone=captured_phone,
    )
    await session.flush()
    await session.commit()
```

**Session-invalidation wrap (model for `invalidate_all_families_for_user`) — `auth/service.py:577-625`:**
```python
async def revoke_all_sessions(
    session: AsyncSession,
    redis: Redis,
    user_id: UUID,
) -> int:
    family_ids_raw = await cast(
        "Awaitable[set[str]]",
        redis.smembers(f"auth:user_sessions:{user_id}"),
    )
    family_count = len(family_ids_raw)

    if family_count > 0:
        pipe = redis.pipeline()
        for fid in family_ids_raw:
            pipe.delete(f"auth:session:{user_id}:{fid}")
        pipe.delete(f"auth:user_sessions:{user_id}")
        await pipe.execute()

    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(tz=UTC))
    )
    # Pitfall 2: emit BEFORE commit so audit row commits atomically with the UPDATE.
    await audit.emit(
        session,
        "session_revoked_all",
        actor_user_id=user_id,
        resource_type="user",
        resource_id=user_id,
        family_count=family_count,
    )
    await session.commit()
    return family_count
```

**Wrapper pattern (model for `invalidate_all_families_for_user`) — D-20 lineage at `auth/service.py:301-325`:**
```python
async def revoke_sessions_on_password_change(
    session: AsyncSession, redis: Redis, user_id: UUID,
) -> int:
    family_count = await revoke_all_sessions(session, redis, user_id)
    await audit.emit(
        session, "password_changed_revokes_sessions",
        actor_user_id=user_id, resource_type="user", resource_id=user_id,
        family_count=family_count,
    )
    await session.commit()
    return family_count
```

For Phase 43 the implementor writes:
```python
async def invalidate_all_families_for_user(
    session: AsyncSession,
    *,
    user_id: UUID,
    reason: Literal["deactivated", "password_reset", "soft_deleted"],
) -> int:
    """Phase 41 D-41-25 UserSessionInvalidator Protocol implementation.
    Wraps revoke_all_sessions; the `reason` is logged via structlog,
    not into the audit emit (the calling site emits `user_deactivated` /
    `user_soft_deleted` carrying `sessions_revoked_count` per D-43-28)."""
    redis: Redis = ...  # closure injected at composition root per D-43-26
    return await revoke_all_sessions(session, redis, user_id)
```

**Audit emit call shape — flat kwargs (NOT nested under `payload=`)** — see clients/service.py:132-142 and Phase 42 CR-01 lesson. Per D-43-04 each `audit.emit` for the 6 user lifecycle events MUST pass exactly the pre-registered Pydantic payload kwargs from `audit_payloads.py:513-598` (extra='forbid').

**Email enqueue at create_user (D-43-24 — render-at-enqueue):**
```python
# Inside create_user, after row inserted + invitation token row inserted + audit emit:
template = TEMPLATES["USER_INVITATION_EMAIL"]
envelope_fields = {
    "subject": template.subject,
    "html": template.html.render(full_name=..., role_ru=..., invitation_url=..., expires_at_human=...),
    "text": template.text.render(full_name=..., role_ru=..., invitation_url=..., expires_at_human=...),
}
await get_email_dispatcher()(
    template_id="USER_INVITATION_EMAIL",  # LITERAL — AST gate enforces (D-41-11)
    to=email_lowercased,
    audit_correlation_id=audit_correlation_uuid,
    **envelope_fields,
)
```

The literal `template_id="USER_INVITATION_EMAIL"` is REQUIRED by the AST walker `tests/unit/test_locked_email_templates_ast.py` (extended per D-43-33 for the new real callsite).

---

### `apps/backend/app/modules/users/repository.py` (repository, CRUD)

**Analog:** `apps/backend/app/modules/clients/repository.py:1-203`

**No-commit/no-flush invariant — D-03** (docstring lines 13-16):
> "NO `session.commit()` and NO `session.flush()` calls live here. The caller (service) owns the transactional moment so it can co-write the audit log row in the same UoW."

**`get_alive` pattern** (lines 47-54):
```python
async def get_alive(session: AsyncSession, client_id: UUID) -> Client | None:
    """Return alive client by id, or None for missing/soft-deleted (CLIENTS-05)."""
    stmt: Select[tuple[Client]] = select(Client).where(
        Client.id == client_id,
        Client.deleted_at.is_(None),
    )
    result: Client | None = await session.scalar(stmt)
    return result
```

**`list_alive` pattern with PaginatedData.model_construct** (lines 57-139, abbreviated):
```python
predicates: list[Any] = [Client.deleted_at.is_(None)]
# filters appended conditionally
total_stmt = select(func.count()).select_from(Client).where(and_(*predicates))
total = await session.scalar(total_stmt) or 0
stmt = select(Client).where(and_(*predicates))
stmt = stmt.order_by(Client.created_at.desc(), Client.id.desc())
offset = (query.page - 1) * query.page_size
stmt = stmt.offset(offset).limit(query.page_size)
rows = (await session.scalars(stmt)).all()
return PaginatedData.model_construct(items=list(rows), total=total, page=query.page, page_size=query.page_size)
```

For users repository: filter on `User.deleted_at.is_(None)`, optional `User.is_active` filter, and LEFT JOIN `PasswordResetToken` (purpose='invitation', consumed_at IS NULL, expires_at > now()) to populate `invitationExpiresAt` for pending rows (per D-43-10).

**Invitation token CRUD** — model imports from `apps.backend.app.modules.auth.password_reset_token_model.PasswordResetToken`. Insert with `purpose='invitation'`, `token_hash=sha256(raw_token)`, `expires_at=now()+INVITATION_TOKEN_TTL`, `audit_correlation_id=...`. Atomic-consume via UPDATE … RETURNING with `WHERE purpose='invitation' AND consumed_at IS NULL` — race-loss → 0 rows returned (handled as 409 by caller per D-43-19 / refresh-token rotation race-loss precedent at `auth/service.py:466-498`).

---

### `apps/backend/app/modules/users/schemas.py` (schema, request-response DTO)

**Analog:** `apps/backend/app/modules/clients/schemas.py:1-263`

**Base class pattern** (lines 105-118):
```python
class ClientCreateRequest(BackendSchemaBase):
    """POST body — extra='forbid' inherited, camelCase wire via to_camel."""
    last_name: str = Field(min_length=1, max_length=128)
    first_name: str = Field(min_length=1, max_length=128)
    ...
```

**Response DTO** (lines 179-201):
```python
class ClientResponse(ResponseData):
    """`from_attributes=True` (inherited) allows ClientResponse.model_validate(orm)."""
    id: UUID
    last_name: str
    ...
```

For users:
- `UserCreateRequest(BackendSchemaBase)`: `email: EmailStr`, `full_name: str`, `role: Role`.
- `UserListItemResponse(ResponseData)` with **D-43-10 fields**: `id, email, full_name, role, is_active, status, created_at, deactivated_at, deactivated_by_user_id, invitation_expires_at` + `@computed_field` `is_deactivated`.
- `UserListQuery(PageQuery)` with `active: bool | None`, `deleted: bool = False`.
- NO `email_verified`, `password_hash`, `telegram_chat_id` (D-43-10 explicit exclusions).

**Reference pagination base:** `app/core/pagination.py:20-29` (`PageQuery` with `page: int = Field(default=1, ge=1)`, `page_size: int = Field(default=20, ge=1, le=100)`).

**ResponseEnvelope wrapper:** `app/core/schemas.py:60-82` (`ResponseEnvelope[T]` + `envelope(payload)` helper).

---

### `apps/backend/app/modules/users/email_templates.py` (template registry)

**Analog:** `apps/backend/app/modules/auth/email_templates.py:1-91` (exact shape mirror)

**Module structure** (auth/email_templates.py lines 41-91):
```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Final
from jinja2 import Template
from jinja2.sandbox import SandboxedEnvironment

_ENV: Final[SandboxedEnvironment] = SandboxedEnvironment(autoescape=True)
_ENV_TEXT: Final[SandboxedEnvironment] = SandboxedEnvironment(autoescape=False)


@dataclass(frozen=True)
class EmailTemplate:
    subject: str           # Final[str] — locked literal, no interpolation
    html: Template
    text: Template


TEMPLATES: Final[dict[str, EmailTemplate]] = {
    "EMAIL_OTP_LOGIN": EmailTemplate(  # noqa: RUF001
        subject="Код входа в Sportzal",
        html=_ENV.from_string("<h1>Код входа в Sportzal</h1>..."),
        text=_ENV_TEXT.from_string("Код входа в Sportzal\n\n..."),
    ),
}
```

For users module: identical scaffolding, registry key is `"USER_INVITATION_EMAIL"`, template variables include `{{ full_name }}`, `{{ role_ru }}`, `{{ invitation_url }}`, `{{ expires_at_human }}` (per D-43-23). Subject is `Final[str]` — locked. Russian copy is owner-copy-locked at plan SUMMARY (`D-43-OWNER-COPY-LOCK`).

**Reuse `EmailTemplate` dataclass directly via import** OR redefine in users module — auth precedent declares the dataclass inline (per-module ownership of D-42-06). Recommend: **redefine inline** to maintain `core ⊥ modules` discipline.

---

### `apps/backend/app/modules/users/constants.py` (constants)

**No direct module-level constants analog in modules/ — closest:** `apps/backend/app/integrations/email/types.py` (frozen literal shape).

**Pattern:**
```python
"""Phase 43 users module constants.

INVITATION_TOKEN_TTL (D-43-12 / D-41-04 / RESET-03): 7-day invitation window.
Used at token-row INSERT time in `service.create_user` (expires_at=now()+INVITATION_TOKEN_TTL)
and at SELECT-time predicate (`expires_at > now()`).
"""
from __future__ import annotations
from datetime import timedelta
from typing import Final

INVITATION_TOKEN_TTL: Final[timedelta] = timedelta(days=7)
```

---

### `apps/backend/app/modules/users/permissions.py` (marker module)

**No in-tree analog** — first marker file per D-43-11. Thin re-export:
```python
"""Phase 43 USERS resource marker (D-43-11 — grep-locality only).

Re-exports `Resource.USERS` so callsites can use the local idiom
`from app.modules.users.permissions import USERS_RESOURCE` instead
of dragging the full enum import into router/service.

No new Action verbs (D-41-22 — reuses CREATE/UPDATE/DELETE/LIST).
"""
from app.core.permissions import Resource

USERS_RESOURCE = Resource.USERS
```

---

### `apps/backend/alembic/versions/0030_users_lifecycle_columns.py` (migration, DDL)

**Composite analogs:**
- **`is_active BOOLEAN NOT NULL DEFAULT true` shape:** `0011_trainers.py:28-33`
- **Cross-column CHECK constraint (correlating two columns):** `0008_freeze.py:52-56` (single-column CHECK) — for two-column CHECK pattern see PostgreSQL `op.create_check_constraint` form (the constraint `(is_active=true AND deactivated_at IS NULL) OR (is_active=false AND deactivated_at IS NOT NULL)` mirrors v1.2 freeze invariant per D-43-06).
- **Altering existing `users` table (add column, drop NOT NULL):** `0022_users_soft_delete_partial_unique.py:46-69` (add_column + drop_constraint + create_index pattern; in-place ALTER on `users`).
- **Self-FK on same table altered:** `0008_freeze.py:106-117` (FK to users.id with `ondelete="SET NULL"`).
- **Round-trip [BLOCKING] discipline:** Phase 42 4-15/4-16 precedent — D-43-36.

**Migration header pattern** (0022 lines 1-39):
```python
"""users.deleted_at + partial-UNIQUE on lower(email) for soft-delete (INFRA-38).

Revision ID: 0022_users_soft_delete_unique
Revises: 0021_bookings_actor_nullable
Create Date: 2026-05-18 18:00:00.000000

Phase 41 INFRA-38 / D-41-15. Schema half of D-41-04/05/07 — enables Phase 43
USERS-05 (soft-delete) + RESET-04 (re-onboard same email after soft-delete).

Three steps:
  1. Add users.deleted_at TIMESTAMPTZ NULL (Pitfall 6: tz-aware).
  ...
"""
from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from sqlalchemy import text
from alembic import op

revision: str = "0022_users_soft_delete_unique"
down_revision: str | None = "0021_bookings_actor_nullable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**For 0030:** `down_revision = "0029_email_send_log_hygiene"` (latest head per `ls alembic/versions`).

**ALTER + DROP NOT NULL pattern (drop `password_hash NOT NULL` per D-43-06):**
```python
op.alter_column("users", "password_hash", nullable=True)
```

**Add CHECK constraint after column adds:**
```python
op.create_check_constraint(
    op.f("ck_users_lifecycle_consistency"),
    "users",
    "(is_active = true AND deactivated_at IS NULL) OR "
    "(is_active = false AND deactivated_at IS NOT NULL)",
)
op.create_check_constraint(
    op.f("ck_users_status"),
    "users",
    "status IN ('active', 'pending_invitation')",
)
```

**Self-FK with ON DELETE SET NULL** (from 0008_freeze.py:113-117 pattern):
```python
op.create_foreign_key(
    op.f("fk_users_deactivated_by_user_id_users"),
    "users",
    "users",  # self-reference
    ["deactivated_by_user_id"],
    ["id"],
    ondelete="SET NULL",
)
```

**Downgrade — strict reverse-order:** drop FK → drop CHECKs → restore `password_hash NOT NULL` (after backfill, but D-43-06 says all-new-rows for invitation are NULL; downgrade is destructive — document) → drop columns.

---

### `apps/backend/app/core/models.py` (MOD — User ORM extension)

**Existing file** (lines 22-64): hoisted User ORM with `email`, `email_verified`, `password_hash: Mapped[str]`, `role`, `full_name`, `telegram_chat_id`, `telegram_username`.

**Extension pattern** (per D-43-08):
```python
from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Text, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from uuid import UUID
from typing import Literal

class User(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))
    # D-43-06: password_hash drops NOT NULL — invited-but-unaccepted rows carry NULL
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[Role] = mapped_column(SAEnum(Role, ...), nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, unique=True)
    telegram_username: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)
    # NEW Phase 43 D-43-08:
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    status: Mapped[Literal["active", "pending_invitation"]] = mapped_column(
        SAEnum("active", "pending_invitation",
               name="user_status",
               native_enum=False, length=32, validate_strings=True),
        nullable=False, server_default=text("'active'"),
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deactivated_by_user_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint("role IN ('owner', 'reception')", name="role"),
        # D-43-06 CHECK is declared at migration level (already in DDL);
        # ORM does not need to redeclare the lifecycle CHECK unless we
        # want alembic check to round-trip it.
    )
```

Also need to add `deleted_at: Mapped[datetime | None]` if not yet on the ORM — verify; migration 0022 added the column to DB, but the ORM Mapped attribute may not be present yet (per RESET test docstring at lines 75-81 it "lands with USERS-02 in Phase 43"). **Confirm during planning whether `deleted_at` Mapped attribute must be added here too.**

---

### `apps/backend/app/modules/auth/service.py` (MOD — rotate_refresh user-row SELECT, line 333+)

**Existing pattern** (lines 372-389):
```python
row = await session.scalar(
    select(RefreshToken)
    .where(RefreshToken.token_hash == presented_hash)
    .with_for_update()
)
if row is None:
    raise InvalidAccessToken("refresh_not_found")

# ---- Branch (A): ACTIVE — rotate ----
if (
    row.revoked_at is None
    and row.replaced_by_id is None
    and row.expires_at > now
):
    user_loaded = await session.get(User, row.user_id)
    if user_loaded is None:
        raise InvalidAccessToken("user_not_found")
```

**D-43-20 modification:** replace `session.get(User, row.user_id)` with a SELECT that adds `is_active=true AND deleted_at IS NULL`:
```python
user_loaded = await session.scalar(
    select(User).where(
        User.id == row.user_id,
        User.is_active == True,  # noqa: E712
        User.deleted_at.is_(None),
    )
)
if user_loaded is None:
    # Anti-oracle (D-43-20): same shape as invalid_session — no enumeration
    # of which condition failed. Audit emits `refresh_failed` with
    # reason='account_inactive' (extends RefreshFailedPayload.reason).
    raise InvalidSession("invalid_session")
```

**Audit emit before raise** — see `auth/service.py:477-484` (`family_reuse_detected` emit precedent inside `rotate_refresh`).

---

### `apps/backend/app/main.py` (MOD — register_user_session_invalidator wiring)

**Existing wiring pattern** (lines 244-252):
```python
# Phase 42 D-42-26 / EMAIL-04 — REG-29-03 double-wire of the EmailDispatcher slot.
register_email_dispatcher(enqueue_email_dispatch)

app.include_router(api)
return app
```

**Imports pattern** (lines 55-67):
```python
from app.core.dependencies import (
    register_active_membership_resolver,
    ...
    register_email_dispatcher,
    register_payment_recorder,
    ...
)
```

**For Phase 43 (D-43-26 / D-43-27 — single-wire):**
```python
# at top of file imports:
from app.core.dependencies import (
    ...
    register_user_session_invalidator,
)
from app.modules.auth.service import invalidate_all_families_for_user

# in create_app() body, adjacent to register_email_dispatcher:
# Phase 43 D-43-26/27 — UserSessionInvalidator single-wire (no ARQ consumer).
register_user_session_invalidator(invalidate_all_families_for_user)
```

**NO change to `app.workers/__init__.py`** — D-43-27 single-wire (NOT double-wire); the parity test `test_app_wiring.py::test_user_session_invalidator_registered` asserts only the FastAPI side.

**Router include:** NO change to `main.py` needed — `apps/backend/app/api/v1/router.py` is the aggregator (per main.py:36-41 comment).

---

### `apps/backend/app/api/v1/router.py` (MOD — include users_router)

**Existing pattern** (lines 37-67):
```python
v1 = APIRouter()
v1.include_router(auth_router, prefix="/auth", tags=["auth"])
v1.include_router(clients_router, prefix="/clients", tags=["clients"])
...
v1.include_router(trainers_router, prefix="/trainers", tags=["trainers"])
v1.include_router(visits_router, prefix="/visits", tags=["visits"])
```

**For Phase 43:**
```python
from app.modules.users.router import router as users_router
...
v1.include_router(users_router, prefix="/users", tags=["users"])
```

---

### `apps/backend/app/core/audit_payloads.py` (MOD — UserInvitedPayload.link_copied)

**Existing payload** (lines 513-529):
```python
class UserInvitedPayload(BaseModel):
    """Payload schema for ("user_invited", "user") — Phase 43 USERS-03."""

    model_config = ConfigDict(extra="forbid")

    audit_correlation_id: UUID | None
    invited_user_id: UUID
    invited_email: str
    invited_role: str
    invitation_expires_at: datetime
```

**Additive change (D-43-14):**
```python
class UserInvitedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audit_correlation_id: UUID | None
    invited_user_id: UUID
    invited_email: str
    invited_role: str
    invitation_expires_at: datetime
    # NEW Phase 43 D-43-14 — owner used ?include_invite_link=true escape hatch.
    # URL itself is NOT in the payload (Pitfall 4 — anti-oracle for link bleed).
    link_copied: bool
```

Also need: `RefreshFailedPayload.reason` Literal extension to add `'account_inactive'` (D-43-20 — one-line addition to whichever payload module declares it).

---

### `tests/unit/test_locked_email_templates_ast.py` (MOD — extend with USER_INVITATION_EMAIL callsite)

**Existing file** (lines 1-25 header + 220 total). Imports `LOCKED_EMAIL_TEMPLATES` from `app.core.audit` and AST-walks every `get_email_dispatcher()(template_id=...)` call.

**Extension pattern (D-43-33):** Add one positive assertion that scans `app/modules/users/service.py` for the literal `template_id="USER_INVITATION_EMAIL"` (mirrors Phase 42 4-11 lesson — Wave 4 test extension precedent).

---

### `tests/integration/users/test_users_crud.py` (integration test)

**Analog:** `tests/integration/clients/test_clients_crud.py:1-80`

**Imports + helper pattern:**
```python
from __future__ import annotations
from typing import Any
from uuid import UUID
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.audit_models import AuditLog


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf", "")}


async def test_create_happy_returns_201_envelope(authed_client_owner: AsyncClient) -> None:
    r = await authed_client_owner.post(
        "/api/v1/users",
        json={"email": "new@example.com", "fullName": "...", "role": "reception"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert "data" in body
    UUID(body["data"]["id"])
```

**Fixture conventions:** `authed_client_owner` / `authed_client_reception` from `tests/integration/conftest.py`; per-test SAVEPOINT isolation via `db_session` (Phase 41 D-41-18). Audit emits exercised via real `audit.emit()` + `audit_log` SELECT — no mocking (Phase 42 CR-01 lesson, D-43-34).

---

### `tests/integration/users/test_refresh_account_inactive.py` (anti-oracle test)

**Analog:** `tests/integration/auth/test_password_reset_no_oracle.py:1-100`

**Anti-oracle pattern** (from analog docstring lines 7-15):
> For all 4 cases — existing-active / existing-deactivated / owner-account / non-existent — the response MUST be IDENTICAL: status code, byte-for-byte identical body, bounded-equal timing within 100ms tolerance.

**Test shape (D-43-20 mirror):**
```python
import time
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


async def test_refresh_for_deactivated_user_matches_invalid_session(
    db_session: AsyncSession,
    client_with_refresh_for_active_user: AsyncClient,
    client_with_refresh_for_deactivated_user: AsyncClient,
) -> None:
    # Both refresh calls must return 401 with identical body {error: 'invalid_session'}.
    t0 = time.perf_counter()
    r_invalid = await client_with_random_refresh.post("/api/v1/auth/refresh")
    t_invalid = time.perf_counter() - t0

    t1 = time.perf_counter()
    r_deact = await client_with_refresh_for_deactivated_user.post("/api/v1/auth/refresh")
    t_deact = time.perf_counter() - t1

    assert r_invalid.status_code == r_deact.status_code == 401
    assert r_invalid.json() == r_deact.json()
    assert abs(t_invalid - t_deact) < 0.100  # 100ms tolerance
```

---

### `tests/unit/users/test_email_template_render.py` (unit test, snapshot render)

**No in-tree analog (first email template render test).** Per D-43-25, golden-file snapshot pattern (Pitfall 6 mitigation):

```python
from pathlib import Path
from datetime import datetime
from app.modules.users.email_templates import TEMPLATES


def test_user_invitation_email_renders_against_snapshot() -> None:
    template = TEMPLATES["USER_INVITATION_EMAIL"]
    rendered_text = template.text.render(
        full_name="Иван Иванов",
        role_ru="администратор стойки",
        invitation_url="https://localhost:5173/auth/accept-invite#token=test",
        expires_at_human="26 мая 2026 в 12:00",
    )
    snapshot = (Path(__file__).parent.parent / "fixtures" / "email_user_invitation_snapshot.txt").read_text()
    assert rendered_text == snapshot
```

---

## Shared Patterns

### Service-owns-transaction (D-03 / Phase 12.1 / SVC001)

**Source:** `apps/backend/app/modules/clients/service.py:109-144` (create flow)
**Apply to:** Every mutation function in `users/service.py`

```python
# Inside any service mutation:
await audit.emit(session, ...)  # co-transactional
await session.flush()           # surface IntegrityErrors before route exit
await session.commit()          # SVC001 walker requires literal commit() in every public write path
```

Repository emits NO `commit()`/`flush()`. The SVC001 AST walker (Phase 41 D-41-28) requires literal `session.commit()` token in every public write path — `users/service.py` is already in scope.

---

### Audit emit kwargs are FLAT (Phase 42 CR-01 lesson)

**Source:** `apps/backend/app/modules/clients/service.py:132-142` (post-fix)
**Apply to:** All `audit.emit(...)` callsites in users/service.py

```python
# CORRECT — payload kwargs flat:
await audit.emit(
    session,
    "user_deactivated",
    actor_user_id=actor.id,
    resource_type="user",
    resource_id=target_id,
    audit_correlation_id=correlation_id,
    deactivated_user_id=target_id,
    sessions_revoked_count=count,
)

# WRONG — nested under payload= (CR-01 anti-pattern):
# await audit.emit(..., payload={"deactivated_user_id": target_id, ...})
```

Pre-registered payloads in `audit_payloads.py:513-598` use `extra='forbid'` — extra keys raise `pydantic.ValidationError`.

---

### Router dependency-order (RBAC-04)

**Source:** `apps/backend/app/modules/clients/router.py:16-19,92-99`
**Apply to:** All mutation endpoints in `users/router.py`

```python
async def endpoint(
    payload: ...,                              # body / path / query first
    actor: Annotated[CurrentUser, Depends(require_permission(Action.X, Resource.USERS))],  # 401 then 403
    _csrf: Annotated[None, Depends(verify_csrf)],  # 403 after RBAC
    session: Annotated[AsyncSession, Depends(get_db)],  # last
) -> ...:
```

GET endpoints OMIT `verify_csrf` (CSRF only for mutations).

---

### Anti-oracle response equality (D-20-9 / RESET-06 / D-43-20)

**Source:** `apps/backend/tests/integration/auth/test_password_reset_no_oracle.py:1-30` (contract docstring)
**Apply to:** `auth/service.py:rotate_refresh` deactivated-user branch + `tests/integration/users/test_refresh_account_inactive.py`

Identical body + bounded timing across success/failure modes. The miss in `rotate_refresh` user SELECT must raise `InvalidSession("invalid_session")` — same code path as truly-missing user.

---

### Soft-delete-and-recreate via partial-UNIQUE

**Source:** `alembic/versions/0022_users_soft_delete_partial_unique.py:62-69` + `clients/repository.py:200-203`
**Apply to:** `users/service.py:create_user` (D-43-13 fourth bullet — soft-deleted email reclaim path)

INSERT is the only path — never `UPDATE existing.deleted_at TO NULL`. The partial-UNIQUE `(lower(email)) WHERE deleted_at IS NULL` (existing from 0022) automatically permits INSERT when the old row is soft-deleted.

---

### LOCKED_EMAIL_TEMPLATES literal at dispatcher callsite

**Source:** `tests/unit/test_locked_email_templates_ast.py:1-60` (AST walker)
**Apply to:** Every `get_email_dispatcher()(...)` call in `users/service.py`

```python
await get_email_dispatcher()(
    template_id="USER_INVITATION_EMAIL",  # MUST be literal str — AST gate enforces
    to=email_lowercased,
    audit_correlation_id=correlation_uuid,
    **envelope_fields,
)
```

The walker rejects variable / f-string / non-literal values AND any literal not in `LOCKED_EMAIL_TEMPLATES` (Phase 41 D-41-11).

---

### Protocol slot single-wire vs double-wire (REG-29-03)

**Source:** `apps/backend/app/core/dependencies.py:608-744`
**Apply to:** Phase 43 wires `UserSessionInvalidator` SINGLE-WIRE in `main.py` only (D-43-27 — no ARQ consumer).

```python
# In create_app() — single-wire registration:
register_user_session_invalidator(invalidate_all_families_for_user)

# In app/workers/__init__.py — NO registration (worker has zero consumers).
```

Contrast `EmailDispatcher` (double-wired in both main.py + workers/__init__.py per Phase 42 D-42-26). The test `test_app_wiring.py` already asserts EmailDispatcher double-wire; Phase 43 adds single-wire assertion only.

---

### TIMESTAMPTZ + tz-aware datetime discipline

**Source:** `apps/backend/app/modules/auth/service.py:526` (`now = datetime.now(tz=UTC)`)
**Apply to:** All datetime constructions in users service / migration

All `datetime.now()` calls use `tz=UTC`. Migration column types are `DateTime(timezone=True)` / `TIMESTAMPTZ` (per `0022_users_soft_delete_partial_unique.py:50`).

---

## No Analog Found

| File | Role | Data Flow | Reason | Recommendation |
|------|------|-----------|--------|----------------|
| `apps/backend/app/modules/users/permissions.py` | marker re-export | constant | First marker file in modules/ — no precedent | Use D-43-11 minimal shape (3-line module) |
| `tests/unit/users/test_email_template_render.py` | unit snapshot test | render | First email template render test — Phase 42 SandboxEmailClient tests cover transport, not template rendering | Use Pitfall 6 golden-file pattern (D-43-25) |

---

## Metadata

**Analog search scope:**
- `apps/backend/app/modules/clients/` (5 files)
- `apps/backend/app/modules/auth/` (12 files — service.py, email_templates.py, router.py, password_reset_token_model.py focused)
- `apps/backend/app/core/` (audit.py, audit_payloads.py, dependencies.py, models.py, schemas.py, pagination.py, permissions.py)
- `apps/backend/app/api/v1/router.py`
- `apps/backend/alembic/versions/0008_freeze.py`, `0011_trainers.py`, `0022_users_soft_delete_partial_unique.py`, `0025_password_reset_tokens.py`
- `apps/backend/tests/integration/clients/test_clients_crud.py`
- `apps/backend/tests/integration/auth/test_password_reset_no_oracle.py`
- `apps/backend/tests/integration/test_app_wiring.py`
- `apps/backend/tests/unit/test_locked_email_templates_ast.py`

**Files scanned:** ~30
**Pattern extraction date:** 2026-05-19
