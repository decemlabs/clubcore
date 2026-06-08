# Phase 96: Referral Domain Backend - Pattern Map

**Mapped:** 2026-06-08
**Files analyzed:** 10 new/modified files
**Analogs found:** 10 / 10

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `app/modules/referrals/models.py` | model | CRUD | `app/modules/loyalty/models.py` | exact (append-only + FK RESTRICT pattern) |
| `app/modules/referrals/schemas.py` | model | request-response | `app/modules/loyalty/schemas.py` | exact (ResponseData + BackendSchemaBase) |
| `app/modules/referrals/repository.py` | service | CRUD | `app/modules/gym/repository.py` | role-match (singleton read/upsert) |
| `app/modules/referrals/service.py` | service | CRUD | `app/modules/loyalty/service.py` | exact (caller-owns-txn, pg_insert, RETURNING-gate, audit.emit) |
| `app/modules/referrals/router.py` | controller | request-response | `app/modules/gym/router.py` + `app/modules/loyalty/router.py` | exact (triple-router: public + client + owner) |
| `app/modules/referrals/permissions.py` | middleware | request-response | `app/modules/loyalty/permissions.py` | exact (require_owner_for_* pattern without OWNER_ONLY extension) |
| `alembic/versions/0067_referral_tables.py` | migration | CRUD | `alembic/versions/0054_loyalty_ledger.py` | exact (table + partial-UNIQUE-literal-name) |
| `alembic/versions/0068_seed_referral_config.py` | migration | CRUD | `alembic/versions/0059_seed_gym_info.py` | exact (INSERT ON CONFLICT DO NOTHING seed) |
| `app/core/audit.py` (edit) | config | event-driven | `app/core/audit.py` lines 458-479 | exact (frozenset extension pattern) |
| `app/core/audit_payloads.py` (edit) | config | event-driven | `app/core/audit_payloads.py` lines 1273-1449 | exact (payload class + AUDIT_PAYLOAD_SCHEMAS dict extension) |
| `app/api/v1/router.py` (edit) | config | request-response | `app/api/v1/router.py` lines 105-123 | exact (late import + triple include_router) |

---

## Pattern Assignments

### `app/modules/referrals/models.py` (model, CRUD)

**Analog:** `app/modules/loyalty/models.py`

**Imports pattern** (lines 1-38):
```python
from __future__ import annotations

from datetime import datetime
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base, UUIDPkMixin
```

**Core ORM model pattern — append-only table** (lines 41-113):
```python
class LoyaltyLedger(Base, UUIDPkMixin):
    # Composition: Base + UUIDPkMixin ONLY — no TimestampMixin, no SoftDeleteMixin.
    # Single temporal column created_at (single-temporal-column discipline).
    __tablename__ = "loyalty_ledger"

    client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "clients.id",
            ondelete="RESTRICT",
            name="fk_loyalty_ledger_client_id_clients",
        ),
        nullable=False,
    )
    # ...
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "entry_type IN ('welcome', 'owner_grant', 'redemption')",
            # NAMING_CONVENTION expands to ck_loyalty_ledger_entry_type
            name="entry_type",
        ),
    )
    # Partial UNIQUE index declared in migration (not as ORM Index)
    # — mirrors PromoCode's uq_promo_codes_code_alive partial-index pattern.
```

**Referral-specific model notes:**
- `referral_codes` table: `Base + UUIDPkMixin` only (no TimestampMixin). Columns: `client_id` FK→clients RESTRICT (named `fk_referral_codes_client_id_clients`), `code String(16)` UNIQUE. `created_at` server_default=func.now(). No `__table_args__` CheckConstraint needed; plain UNIQUE on `code` declared via migration as `uq_referral_codes_code` (non-partial — codes never deleted).
- `referral_captures` table: `Base + UUIDPkMixin` only. Columns: `referee_client_id` FK→clients RESTRICT, `referrer_client_id` FK→clients RESTRICT, `referral_code_id` FK→referral_codes RESTRICT. `created_at` server_default=func.now(). Partial UNIQUE on `(referee_client_id)` (plain UNIQUE — one capture per referee) declared as `uq_referral_captures_referee_client_id` in migration (literal name, NOT via op.f()).
- `referral_config` table: `Base + UUIDPkMixin` only (singleton like GymInfo but no TimestampMixin — it's config, not event). Columns: `referrer_bonus_kopecks BigInteger`, `referee_welcome_kopecks BigInteger`. Seed row with deterministic PK `00000000-0000-0000-0000-000000000002`.

---

### `app/modules/referrals/schemas.py` (model, request-response)

**Analog:** `app/modules/loyalty/schemas.py` + `app/modules/gym/schemas.py`

**Imports pattern** (loyalty/schemas.py lines 1-15):
```python
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.core.schemas import BackendSchemaBase, ResponseData
```

**Response schema pattern** (loyalty/schemas.py lines 18-51):
```python
class ClientLoyaltyBalanceResponse(ResponseData):
    """Wire: { balanceKopecks: int }"""
    balance_kopecks: int  # wire: balanceKopecks


class ClientLoyaltyGrantResponse(ResponseData):
    """Wire: { entryId, balanceKopecks }"""
    entry_id: UUID     # wire: entryId
    balance_kopecks: int  # wire: balanceKopecks
```

**Request schema pattern** (loyalty/schemas.py lines 54-67):
```python
class LoyaltyGrantRequest(BackendSchemaBase):
    """extra='forbid' (inherited from BackendSchemaBase) rejects unknown keys."""
    amount_kopecks: int = Field(gt=0)  # wire: amountKopecks
    reason: str = Field(max_length=255)
    category: Literal["promo", "referral", "manual"]
```

**Referral-specific schemas to create:**
- `ReferralCodeResponse(ResponseData)` — `{ code: str, shareUrl: str }` (wire: `code`, `shareUrl`)
- `ReferralResolveResponse(ResponseData)` — `{ valid: bool, referrerFirstName: str | None, welcomeBonusKopecks: int }` (wire camelCase)
- `ReferralCaptureRequest(BackendSchemaBase)` — `{ code: str }` only; `extra='forbid'`; `code: str = Field(min_length=1, max_length=16)`
- `ReferralConfigResponse(ResponseData)` — `{ referrerBonusKopecks: int, refereeWelcomeKopecks: int }`
- `ReferralConfigUpdateRequest(BackendSchemaBase)` — `{ referrerBonusKopecks: int = Field(ge=0), refereeWelcomeKopecks: int = Field(ge=0) }`

---

### `app/modules/referrals/repository.py` (service, CRUD)

**Analog:** `app/modules/gym/repository.py`

**Full pattern** (gym/repository.py lines 1-41):
```python
"""..repository — single point of access to the ORM (D-31-08).

Transaction control (D-03): NO session.commit() and NO session.flush() here.
Caller (service.py) owns the transactional moment.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.gym.models import GymInfo
from app.modules.gym.schemas import GymInfoUpdateRequest


async def get_singleton(session: AsyncSession) -> GymInfo | None:
    """Return the single gym row, or None if seed not yet run."""
    stmt = select(GymInfo).limit(1)
    result: GymInfo | None = await session.scalar(stmt)
    return result


async def upsert_singleton(session: AsyncSession, data: GymInfoUpdateRequest) -> GymInfo:
    """Update the singleton row in-place. Caller owns flush+commit (D-03).

    Applies exclude_unset model_dump so partial payloads only touch supplied fields.
    """
    gym = await get_singleton(session)
    if gym is None:
        gym = GymInfo(name="", address="")
        session.add(gym)
    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(gym, key, value)
    return gym
```

**Referral repository methods needed:**
- `get_code_by_client_id(session, client_id) -> ReferralCode | None` — `select(ReferralCode).where(ReferralCode.client_id == client_id)`
- `get_code_by_value(session, code_str) -> ReferralCode | None` — `select(ReferralCode).where(ReferralCode.code == code_str.upper())`
- `get_capture_by_referee(session, referee_client_id) -> ReferralCapture | None` — idempotency check
- `get_config(session) -> ReferralConfig | None` — `select(ReferralConfig).limit(1)`
- `upsert_config(session, data) -> ReferralConfig` — gym upsert pattern with `exclude_unset`

---

### `app/modules/referrals/service.py` (service, CRUD)

**Analog:** `app/modules/loyalty/service.py`

**Module header + logger pattern** (loyalty/service.py lines 1-36):
```python
"""Loyalty service (Phase 82 ACCR-01/ACCR-02/LOYL-01/LOYL-02/LOYL-03).

No session.commit() — caller-owns-txn (D-32-10/D-49-19).
All reads use raw SQL text() — no cross-module ORM import of Client (D-54-08).
"""
from __future__ import annotations

import structlog
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.dependencies import CurrentUser
from app.core.exceptions import NotFoundError, ValidationAppError
from app.modules.loyalty.models import LoyaltyLedger

_log = structlog.get_logger("modules.loyalty.service")

WELCOME_BONUS_KOPECKS: int = 50_000  # 500 ₽ welcome bonus (ACCR-01)
```

**Typed error class pattern** (loyalty/service.py lines 47-63):
```python
class LoyaltyClientNotFoundError(NotFoundError):
    """Client not found when attempting loyalty grant."""
    code = "client_not_found"
    status_code = 404


class LoyaltyGrantNegativeError(ValidationAppError):
    """Owner grant amount must be positive (> 0)."""
    code = "grant_amount_must_be_positive"
    status_code = 422
```

**pg_insert + RETURNING gate + audit.emit pattern** (loyalty/service.py lines 68-136):
```python
async def accrue_welcome_bonus(session: AsyncSession, client_id: UUID) -> None:
    stmt = (
        pg_insert(LoyaltyLedger)
        .values(
            client_id=client_id,
            entry_type="welcome",
            amount_kopecks=WELCOME_BONUS_KOPECKS,
        )
        .on_conflict_do_nothing(
            index_elements=["client_id"],
            # Inline SQL literal (NOT a bound param) so PostgreSQL can match
            # this predicate against the partial UNIQUE INDEX during ON CONFLICT.
            index_where=text("entry_type = 'welcome'"),
        )
        .returning(LoyaltyLedger.id)
    )
    result = await session.execute(stmt)
    inserted_id = result.scalar_one_or_none()

    if inserted_id is None:
        _log.info("loyalty_welcome_conflict", client_id=str(client_id), ...)
        return  # idempotent no-op

    # Real insert — emit co-transactionally.
    await audit.emit(
        session,
        "loyalty_accrued",
        actor_user_id=None,
        resource_type="loyalty",
        resource_id=inserted_id,
        client_id=str(client_id),
        entry_id=str(inserted_id),
        amount_kopecks=WELCOME_BONUS_KOPECKS,
        entry_type="welcome",
        actor="welcome",
    )
```

**Cross-module existence check via raw SQL** (loyalty/service.py lines 157-163):
```python
# Existence check via raw SQL — D-54-08: no ORM import of Client.
exists_row = (
    await session.execute(
        text("SELECT 1 FROM clients WHERE id = :cid AND deleted_at IS NULL LIMIT 1"),
        {"cid": str(client_id)},
    )
).fetchone()
if exists_row is None:
    raise LoyaltyClientNotFoundError("client_not_found")
```

**Referral service functions needed:**
- `get_or_create_referral_code(session, client_id, settings) -> ReferralCodeResponse` — idempotent; reads repository first; if None, generates Crockford-base32 code with bounded retry loop (3 attempts) on UNIQUE violation; commits via `session.flush()`; emits `referral_code_generated` audit event; returns `{code, shareUrl}` where `shareUrl = f"{settings.pwa_base_url}/i/{code}"`
- `resolve_public_code(session, code_str) -> ReferralResolveResponse` — reads referral_code + raw SQL for client first_name; `valid: false` (200) for unknown code, never 404; NO PII beyond first name
- `capture_referral(session, referee_principal, code_str) -> None` — checks referral_capture idempotency (existing capture → no-op 200); resolves code → 404 if unknown; self-referral check → 422; inserts referral_capture; flushes; emits `referral_captured` audit event
- `get_referral_config(session) -> ReferralConfigResponse` — 404 via error if seed missing
- `update_referral_config(session, actor, data) -> ReferralConfigResponse` — upsert singleton; flush + commit (same as gym service — singleton write owns txn)

**Collision retry pattern** (referencing promo_codes and pg_insert discipline):
```python
import secrets

CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # no O/I/L (ambiguous)

async def _generate_unique_code(session: AsyncSession, *, max_attempts: int = 3) -> str:
    for _ in range(max_attempts):
        candidate = "".join(secrets.choice(CROCKFORD_ALPHABET) for _ in range(8))
        result = (
            await session.execute(
                text("SELECT 1 FROM referral_codes WHERE code = :code"),
                {"code": candidate},
            )
        ).fetchone()
        if result is None:
            return candidate
    raise RuntimeError("failed to generate unique referral code after retries")
```

---

### `app/modules/referrals/router.py` (controller, request-response)

**Analog:** `app/modules/gym/router.py` (dual-router) + `app/modules/loyalty/router.py` (client router)

**Full dual-router pattern** (gym/router.py lines 1-81):
```python
"""Gym-info router — client read + owner write endpoints.

Two APIRouter instances in one file:
  client_router: GET /api/v1/client/gym   — require_client gate (GYM-01)
  owner_router:  PUT /api/v1/gym          — require_permission(EDIT, GYM) + verify_csrf (GYM-02)

RBAC-04 ordering: in owner_update_gym_info, require_permission is declared BEFORE
verify_csrf so reception fails at 403 before reaching the CSRF check.

No try/except — AppError subclasses bubble to _app_error_handler in app/main.py.
"""
from __future__ import annotations
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import (
    ClientPrincipal, CurrentUser, require_client,
    require_permission, verify_csrf,
)
from app.core.permissions import Action, Resource
from app.core.schemas import ResponseEnvelope, envelope

client_router = APIRouter(tags=["Client-Portal"])
owner_router = APIRouter(tags=["Gym"])  # ← change tag to "Referral" for referrals

@client_router.get(
    "/gym",
    response_model=ResponseEnvelope[GymInfoResponse],
    operation_id="client_get_gym_info",
    summary="...",
)
async def client_get_gym_info(
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[GymInfoResponse]:
    result = await service.get_gym_info(session)
    return envelope(result)

@owner_router.put(
    "",
    response_model=ResponseEnvelope[GymInfoResponse],
    operation_id="owner_update_gym_info",
    summary="Update gym facility info (owner-only; GYM-02)",
)
async def owner_update_gym_info(
    payload: GymInfoUpdateRequest,
    # RBAC-04: require_permission BEFORE verify_csrf — reception fails 403 first
    actor: Annotated[CurrentUser, Depends(require_permission(Action.EDIT, Resource.GYM))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[GymInfoResponse]:
    result = await service.update_gym_info(session, actor, payload)
    return envelope(result)
```

**Loyalty client router pattern** (loyalty/router.py lines 1-74 — for public router model):
```python
router = APIRouter(tags=["Client-Portal"])

@router.get(
    "/loyalty/balance",
    response_model=ResponseEnvelope[ClientLoyaltyBalanceResponse],
    operation_id="client_get_loyalty_balance",
    summary="...",
)
async def client_get_loyalty_balance(
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientLoyaltyBalanceResponse]:
    result = await service.get_client_loyalty_balance(session, client.id)
    return envelope(result)
```

**Referral router structure** — three routers in one file:
```python
# Public router (NO auth gate — unauthenticated deep-link resolver)
public_router = APIRouter(tags=["Referral"])

@public_router.get(
    "/i/{code}",
    response_model=ResponseEnvelope[ReferralResolveResponse],
    operation_id="public_resolve_referral_code",
    summary="Public deep-link resolver — always 200, valid: false for unknown codes",
)
async def public_resolve_referral_code(
    code: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ReferralResolveResponse]:
    result = await service.resolve_public_code(session, code)
    return envelope(result)


# Client router (require_client gate)
client_router = APIRouter(tags=["Client-Portal"])

@client_router.get("/referral/code", ...)
async def client_get_referral_code(
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ...: ...

@client_router.post("/referral/capture", ...)
async def client_capture_referral(
    payload: ReferralCaptureRequest,
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ...: ...


# Owner router — RBAC-04 ordering: require_permission BEFORE verify_csrf
owner_router = APIRouter(tags=["Referral"])

@owner_router.get("/config", ...)
async def owner_get_referral_config(
    actor: Annotated[CurrentUser, Depends(require_permission(Action.EDIT, Resource.GYM))],
    # NOTE: Resource.GYM is the closest existing resource until REFERRAL is added.
    # Planner: decide whether to add Resource.REFERRAL or reuse Resource.GYM.
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ...: ...

@owner_router.put("/config", ...)
async def owner_update_referral_config(
    payload: ReferralConfigUpdateRequest,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.EDIT, Resource.GYM))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ...: ...
```

---

### `app/modules/referrals/permissions.py` (middleware, request-response)

**Analog:** `app/modules/loyalty/permissions.py`

**Full pattern** (loyalty/permissions.py lines 1-62):
```python
"""Loyalty module RBAC factories (Phase 82 ACCR-02).

Does NOT extend OWNER_ONLY frozenset or add a new Resource — the parity test
(Phase 6 TEST-06) and CISO-01 byte-parity guard stay green without touching
apps/admin-web/src/shared/session/can.ts.
"""
from __future__ import annotations
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user
from app.core.exceptions import ForbiddenError
from app.core.permissions import Role


def require_owner_for_loyalty_grant() -> Callable[..., Awaitable[CurrentUser]]:
    async def _checker(
        request: Request,
        user: Annotated[CurrentUser, Depends(get_current_user)],
        session: Annotated[AsyncSession, Depends(get_db)],
    ) -> CurrentUser:
        if user.role is Role.OWNER:
            return user
        await audit.emit(
            session,
            "rbac_forbidden",
            actor_user_id=user.id,
            resource_type="rbac",
            target_resource="loyalty",
            role=user.role.value,
            action="grant",
            path=request.url.path,
            ip=request.client.host if request.client is not None else None,
        )
        raise ForbiddenError("forbidden:grant:loyalty")
    return _checker
```

**Note:** The referral module uses `require_permission(Action.EDIT, Resource.GYM)` from the core (gym pattern) for owner config GET/PUT — no custom permissions.py needed unless a new `Resource.REFERRAL` is added. The planner must decide whether to add `REFERRAL` to permissions.py and admin-web (breaks byte-parity) or reuse `GYM` permission (no admin-web change needed). This file may be omitted if reusing `require_permission` directly.

---

### `alembic/versions/0067_referral_tables.py` (migration, CRUD)

**Analog:** `alembic/versions/0054_loyalty_ledger.py`

**Full migration pattern** (0054 lines 24-94):
```python
"""loyalty_ledger append-only table (Phase 82 LOYL-03).

Revision ID: 0054_loyalty_ledger
Revises: 0053_booking_notif_widen_kind_rescheduled
...
"""
from __future__ import annotations
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import func, text
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0054_loyalty_ledger"
down_revision: str | None = "0053_booking_notif_widen_kind_rescheduled"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "loyalty_ledger",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        # ...
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_loyalty_ledger")),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            name=op.f("fk_loyalty_ledger_client_id_clients"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "entry_type IN ('welcome', 'owner_grant', 'redemption')",
            name=op.f("ck_loyalty_ledger_entry_type"),
        ),
    )
    # Partial UNIQUE — LITERAL index name (NOT via op.f()) per 0034/0037/0046 precedent
    op.create_index(
        "uq_loyalty_ledger_welcome",    # ← LITERAL name
        "loyalty_ledger",
        ["client_id"],
        unique=True,
        postgresql_where=text("entry_type = 'welcome'"),
    )
    # Plain index via op.f()
    op.create_index(
        op.f("ix_loyalty_ledger_client_id"),
        "loyalty_ledger",
        ["client_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("uq_loyalty_ledger_welcome", table_name="loyalty_ledger")
    op.drop_index(op.f("ix_loyalty_ledger_client_id"), table_name="loyalty_ledger")
    op.drop_table("loyalty_ledger")
```

**Referral migration 0067 contents:**

Three tables: `referral_codes`, `referral_captures`, `referral_config`.

Key naming rules:
- `revision: str = "0067_referral_tables"`, `down_revision: str | None = "0066_message_attachments"`
- All PK constraints: `name=op.f("pk_<table>")` 
- All FK constraints: full literal name `"fk_<table>_<col>_<referred>"` (same as loyalty pattern — NOT `op.f()` for FK)
- Plain unique on `referral_codes.code`: `op.create_index(op.f("uq_referral_codes_code"), "referral_codes", ["code"], unique=True)` — plain (non-partial) so uses `op.f()` 
- Partial UNIQUE on `referral_captures.referee_client_id`: `op.create_index("uq_referral_captures_referee_client_id", "referral_captures", ["referee_client_id"], unique=True)` — LITERAL name (no `op.f()`), no `postgresql_where` needed (the uniqueness is unconditional, not partial)
- Plain index on referral_codes for client lookups: `op.create_index(op.f("ix_referral_codes_client_id"), "referral_codes", ["client_id"], unique=False)`

---

### `alembic/versions/0068_seed_referral_config.py` (migration, CRUD)

**Analog:** `alembic/versions/0059_seed_gym_info.py`

**Full seed migration pattern** (0059 lines 1-113):
```python
"""Seed gym_info singleton baseline (Phase 86 GYM-03).

Revision ID: 0059_seed_gym_info
Revises: 0058_gym_info
...
Idempotency:
- INSERT ... ON CONFLICT (id) DO NOTHING — id is the PK.
- Re-running upgrade() is a verified no-op.
"""
from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0059_seed_gym_info"
down_revision: str | None = "0058_gym_info"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SINGLETON_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    # Use CAST(:param AS type) syntax — asyncpg sends all bind params as VARCHAR;
    # explicit CAST required for uuid and jsonb columns.
    op.execute(
        sa.text(
            "INSERT INTO gym_info (id, name, ...) "
            "VALUES (CAST(:id AS uuid), :name, ...) "
            "ON CONFLICT (id) DO NOTHING"
        ).bindparams(id=_SINGLETON_ID, name="Мой зал · Тверская", ...)
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM gym_info WHERE id = CAST(:id AS uuid)").bindparams(
            id=_SINGLETON_ID
        )
    )
```

**Referral seed migration 0068 specifics:**
- `revision: str = "0068_seed_referral_config"`, `down_revision: str | None = "0067_referral_tables"`
- `_SINGLETON_ID = "00000000-0000-0000-0000-000000000002"` (gym used `...001`)
- Seed values: `referrer_bonus_kopecks=50000` (500 ₽), `referee_welcome_kopecks=30000` (300 ₽)
- `ON CONFLICT (id) DO NOTHING`
- Table: `referral_config`

---

### `app/core/audit.py` (edit — LOCKED_AUDIT_EVENTS extension)

**Analog:** `app/core/audit.py` lines 458-479

**Pattern to replicate** (audit.py lines 472-479):
```python
# v2.5 (Phase 90 lock — INFRA-15; messaging domain. All four events pre-registered
# BEFORE any callsite, including Phase 93 bridge events.)
("message_sent", "message"),
("message_read", "message"),
("attachment_uploaded", "message"),
("chat_staff_reply_sent", "message"),
```

**Two new pairs to add immediately after the messaging block:**
```python
# v2.6 (Phase 96 lock — INFRA-15; referral domain. Pre-registered BEFORE
# any callsite per INFRA-15 discipline.)
("referral_code_generated", "referral"),
("referral_captured", "referral"),
```

**Rule:** Add the comment block first, then the tuple pairs — this is the insertion pattern every prior phase follows (line 458-479 shows the v2.3, v2.3, v2.3 blocks; append v2.6 block after the last entry before the closing `}`).

---

### `app/core/audit_payloads.py` (edit — payload schemas + AUDIT_PAYLOAD_SCHEMAS)

**Analog:** `app/core/audit_payloads.py` lines 1273-1449

**Payload class pattern** (audit_payloads.py lines 1273-1310):
```python
class LoyaltyAccruedPayload(BaseModel):
    """Payload schema for ("loyalty_accrued", "loyalty") — Phase 82 ACCR-01/ACCR-02.

    Pre-registered BEFORE callsite per INFRA-15 discipline.
    """
    model_config = ConfigDict(extra="forbid")

    client_id: UUID
    entry_id: UUID
    amount_kopecks: int
    entry_type: Literal["welcome", "owner_grant"]
    actor: str


class LoyaltyRedeemedPayload(BaseModel):
    """Payload schema for ("loyalty_redeemed", "loyalty") — Phase 83 REDM-02."""
    model_config = ConfigDict(extra="forbid")

    client_id: UUID
    entry_id: UUID
    amount_kopecks: int = Field(lt=0)  # always negative
    online_payment_id: UUID
```

**Registry extension pattern** (audit_payloads.py lines 1446-1449):
```python
("loyalty_accrued", "loyalty"): LoyaltyAccruedPayload,
("loyalty_redeemed", "loyalty"): LoyaltyRedeemedPayload,
```

**Referral payload schemas to add** (add before `AUDIT_PAYLOAD_SCHEMAS` dict):
```python
class ReferralCodeGeneratedPayload(BaseModel):
    """Payload for ("referral_code_generated", "referral") — Phase 96 REFER-01.

    Pre-registered BEFORE any callsite per INFRA-15 discipline.
    """
    model_config = ConfigDict(extra="forbid")

    client_id: UUID
    referral_code_id: UUID
    code: str  # the 8-char Crockford code value


class ReferralCapturedPayload(BaseModel):
    """Payload for ("referral_captured", "referral") — Phase 96 REFER-02.

    Pre-registered BEFORE any callsite per INFRA-15 discipline.
    """
    model_config = ConfigDict(extra="forbid")

    referee_client_id: UUID
    referrer_client_id: UUID
    referral_capture_id: UUID
    referral_code_id: UUID
```

**Add to AUDIT_PAYLOAD_SCHEMAS dict:**
```python
("referral_code_generated", "referral"): ReferralCodeGeneratedPayload,
("referral_captured", "referral"): ReferralCapturedPayload,
```

---

### `app/api/v1/router.py` (edit — router mounting)

**Analog:** `app/api/v1/router.py` lines 105-123

**Triple-router mounting pattern** (router.py lines 113-123):
```python
# Phase 86 GYM-01/GYM-02 — gym-info client read + owner write.
# Client read mounted at /api/v1/client/gym (require_client gate — GYM-01).
# Owner write mounted at /api/v1/gym (require_permission(EDIT, GYM) + verify_csrf — GYM-02).
# Separate routers avoid a cross-module edge and keep the two distinct auth gates clean
# (D-20-MODULE). client_router prefix "/client" → /api/v1/client/gym;
# owner_router prefix "/gym" → /api/v1/gym.
from app.modules.gym.router import client_router as gym_client_router  # noqa: E402
from app.modules.gym.router import owner_router as gym_owner_router  # noqa: E402

v1.include_router(gym_client_router, prefix="/client")
v1.include_router(gym_owner_router, prefix="/gym")
```

**Referral router mounting block** (append after the gym block):
```python
# Phase 96 REFER-01/REFER-02/REFER-03/REFER-07 — referral domain.
# Public resolver mounted at /api/v1 (no prefix — path is /i/{code}).
# Client endpoints mounted at /api/v1/client (same prefix as loyalty — D-20-MODULE).
# Owner config mounted at /api/v1/referral (require_permission + verify_csrf).
from app.modules.referrals.router import client_router as referral_client_router  # noqa: E402
from app.modules.referrals.router import owner_router as referral_owner_router  # noqa: E402
from app.modules.referrals.router import public_router as referral_public_router  # noqa: E402

v1.include_router(referral_public_router)           # /api/v1/i/{code}
v1.include_router(referral_client_router, prefix="/client")  # /api/v1/client/referral/*
v1.include_router(referral_owner_router, prefix="/referral")  # /api/v1/referral/config
```

---

## Shared Patterns

### Authentication Gate — Client
**Source:** `app/core/dependencies.py` lines 1240-1257
**Apply to:** All client endpoints in `referrals/router.py`
```python
client: Annotated[ClientPrincipal, Depends(require_client())]
```
- `client.id` is the ONLY source for `client_id` in service calls — NEVER from URL params or request body (D-20-IDOR).

### Authentication Gate — Owner RBAC-04 Ordering
**Source:** `app/modules/gym/router.py` lines 59-79
**Apply to:** `owner_update_referral_config` endpoint
```python
# RBAC-04: require_permission BEFORE verify_csrf in the parameter list
actor: Annotated[CurrentUser, Depends(require_permission(Action.EDIT, Resource.GYM))],
_csrf: Annotated[None, Depends(verify_csrf)],
```
Reception role → 403 from `require_permission` before the CSRF check is even reached.

### Error Handling — No Try/Except in Routers
**Source:** `app/modules/loyalty/router.py` lines 15, 50, 74
**Apply to:** All referral router functions
```python
# No try/except — AppError subclasses bubble to _app_error_handler in app/main.py.
```
Typed `AppError` subclasses (e.g. `ReferralCodeNotFoundError(NotFoundError)`) are raised in service and caught globally.

### Error Types — D-09 Distinct Per-Reason Codes
**Source:** `app/core/exceptions.py` lines 8-51, `app/modules/loyalty/service.py` lines 47-63
**Apply to:** `referrals/service.py`
```python
class ReferralCodeNotFoundError(NotFoundError):
    code = "referral_code_not_found"
    status_code = 404

class SelfReferralError(ValidationAppError):
    code = "self_referral_not_allowed"
    status_code = 422

class ReferralConfigNotFoundError(NotFoundError):
    code = "referral_config_not_found"
    status_code = 404
```

### Response Envelope
**Source:** `app/core/schemas.py` lines 56-81
**Apply to:** All referral router endpoints
```python
from app.core.schemas import ResponseEnvelope, envelope
# ...
return envelope(result)  # wraps result in ResponseEnvelope[T](data=result)
```

### Caller-Owns-Txn
**Source:** `app/modules/loyalty/service.py` docstring + lines 68-136
**Apply to:** `referrals/service.py` — all write functions except `update_referral_config`
- All service functions except the singleton config upsert: `flush` only, no `commit`.
- `update_referral_config` owns commit (same as `gym.service.update_gym_info` — singleton write D-03).
- `get_or_create_referral_code` and `capture_referral`: `flush` only; router wraps them in a transaction via `get_db` session.

### INFRA-15 Pre-Registration Rule
**Source:** `app/core/audit.py` lines 458-479, `app/core/audit_payloads.py` lines 1358-1449
**Apply to:** `app/core/audit.py` and `app/core/audit_payloads.py` edits
- New `(event, resource_type)` pairs MUST be registered in `LOCKED_AUDIT_EVENTS` AND `AUDIT_PAYLOAD_SCHEMAS` in the same commit that introduces the service callsite — or preferably in a preceding commit. Callsite emitting an unregistered pair causes `AuditEventNotLockedError` (hard fail in dev + prod).

### D-54-08 Cross-Module Raw SQL
**Source:** `app/modules/loyalty/service.py` lines 157-163
**Apply to:** Any place in `referrals/service.py` that needs client data (e.g., first name for `resolve_public_code`)
```python
# D-54-08: no ORM import of Client — raw SQL text() only.
row = (
    await session.execute(
        text("SELECT first_name FROM clients WHERE id = :cid AND deleted_at IS NULL"),
        {"cid": str(referrer_client_id)},
    )
).mappings().one_or_none()
```

### Settings Access for shareUrl
**Source:** `app/core/config.py` line 133
**Apply to:** `get_or_create_referral_code` service function
```python
# Existing setting: frontend_base_url = "http://localhost:5173"
# shareUrl = f"{settings.frontend_base_url}/i/{code}"
# OR: add pwa_base_url: str = "http://localhost:5174" to Settings
# (client-pwa runs on port 5174 per ws_allowed_origins default)
```
The planner must decide: reuse `frontend_base_url` (admin-web dev port 5173) or add `pwa_base_url` (client-pwa dev port 5174). Settings is passed into the service via `Annotated[Settings, Depends(get_settings)]` in the router.

---

## No Analog Found

All files have close analogs. No entries in this section.

---

## Metadata

**Analog search scope:** `apps/backend/app/modules/loyalty/`, `apps/backend/app/modules/gym/`, `apps/backend/app/modules/promo_codes/`, `apps/backend/app/core/`, `apps/backend/app/api/v1/`, `apps/backend/alembic/versions/`
**Files scanned:** 22
**Pattern extraction date:** 2026-06-08
