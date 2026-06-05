# Phase 82: Loyalty Foundation — Ledger + Balance + Accrual - Pattern Map

**Mapped:** 2026-06-05
**Files analyzed:** 14 new/modified files
**Analogs found:** 14 / 14

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/backend/app/modules/loyalty/models.py` | model | CRUD | `apps/backend/app/modules/promo_codes/models.py` (`PromoRedemption`) | exact |
| `apps/backend/app/modules/loyalty/service.py` | service | CRUD | `apps/backend/app/modules/promo_codes/service.py` | exact |
| `apps/backend/app/modules/loyalty/repository.py` | service/repository | CRUD | `apps/backend/app/modules/client_portal/repository.py` | role-match |
| `apps/backend/app/modules/loyalty/schemas.py` | model | request-response | `apps/backend/app/modules/client_portal/schemas.py` | role-match |
| `apps/backend/app/modules/loyalty/permissions.py` | middleware | request-response | `apps/backend/app/modules/payments/permissions.py` | exact |
| `apps/backend/app/modules/loyalty/router.py` | controller | request-response | `apps/backend/app/modules/client_portal/router.py` | role-match |
| `apps/backend/app/core/audit.py` (modify) | config | event-driven | self | exact |
| `apps/backend/app/core/audit_payloads.py` (modify) | model | event-driven | `apps/backend/app/core/audit_payloads.py` (`BookingRescheduledPayload`) | exact |
| `apps/backend/app/modules/clients/service.py` (modify) | service | CRUD | self | exact |
| `apps/backend/alembic/versions/0054_loyalty_ledger.py` | migration | CRUD | `apps/backend/alembic/versions/0046_promo_codes.py` | exact |
| `apps/backend/tests/unit/test_loyalty_audit_events.py` | test | event-driven | `apps/backend/tests/unit/test_locked_audit_events.py` | exact |
| `apps/backend/tests/unit/test_audit_taxonomy.py` (modify) | test | event-driven | self | exact |
| `apps/client-pwa/src/screens/sheets/LoyaltySheet.jsx` | component | request-response | `apps/client-pwa/src/screens/sheets/HistorySheets.jsx` + `ProfileExtraSheets.jsx` | role-match |
| `apps/client-pwa/src/lib/clientQueries.ts` (modify) | hook | request-response | self (`useClientWeeklyActivity`, `useClientPaymentMethod`) | exact |

---

## Pattern Assignments

### `apps/backend/app/modules/loyalty/models.py` (model, CRUD)

**Analog:** `apps/backend/app/modules/promo_codes/models.py` — `PromoRedemption` class (lines 91–149)

**Imports pattern** (lines 28–49 of analog):
```python
from __future__ import annotations

from datetime import datetime
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base, UUIDPkMixin
```

**Append-only ledger model pattern** (lines 91–149 of analog):
```python
class PromoRedemption(Base, UUIDPkMixin):
    """Append-only. Composition: Base + UUIDPkMixin ONLY — no TimestampMixin, no SoftDeleteMixin.
    Lifecycle tracked via redeemed_at column (single-temporal-column discipline)."""

    __tablename__ = "promo_redemptions"

    client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "clients.id",
            ondelete="RESTRICT",
            name="fk_promo_redemptions_client_id_clients",
        ),
        nullable=False,
    )
    discount_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    redeemed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "discount_kopecks > 0",
            # NAMING_CONVENTION expands to ck_promo_redemptions_discount_kopecks_positive
            name="discount_kopecks_positive",
        ),
        UniqueConstraint(
            "online_payment_id",
            name="uq_promo_redemptions_online_payment_id",
        ),
    )
```

**For Phase 82 `LoyaltyLedger` — concrete adaptations:**
- Table name: `loyalty_ledger`
- FK naming: `fk_loyalty_ledger_client_id_clients`
- Column `amount_kopecks` (BigInteger, signed — positive accrual, negative redemption), NOT `discount_kopecks`
- Column `entry_type` (String(16)) + CHECK `entry_type IN ('welcome', 'owner_grant', 'redemption')` — bare suffix `"entry_type"` → expanded to `ck_loyalty_ledger_entry_type`
- Column `category` (String(16), nullable=True) — for `owner_grant` rows only
- Column `reason` (String(255), nullable=True) — for `owner_grant` rows only
- Column `created_at` (single temporal column, `server_default=func.now()`) — no `updated_at`, no `deleted_at`
- Partial UNIQUE index `uq_loyalty_ledger_welcome` on `(client_id) WHERE entry_type = 'welcome'` — literal name (NOT via naming convention, mirrors `uq_promo_codes_code_alive` literal)
- Regular Index on `client_id` for balance/history fold efficiency
- NAMING_CONVENTION note: `CheckConstraint(name=...)` takes a BARE suffix only (convention expands `ck_%(table_name)s_%(constraint_name)s`); `Index(...)` uses literal full name; FK `name=` uses full expanded name directly

---

### `apps/backend/app/modules/loyalty/service.py` (service, CRUD)

**Analog:** `apps/backend/app/modules/promo_codes/service.py`

**Imports pattern** (lines 1–37 of analog):
```python
"""Loyalty service (Phase 82 ACCR-01/ACCR-02/LOYL-03).

No session.commit() — caller-owns-txn (D-32-10/D-49-19).
"""
from __future__ import annotations

import structlog
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.exceptions import ValidationAppError, NotFoundError
from app.modules.loyalty.models import LoyaltyLedger

_log = structlog.get_logger("modules.loyalty.service")
```

**Distinct typed error classes pattern** (lines 44–84 of analog):
```python
class LoyaltyClientNotFoundError(NotFoundError):
    """Client not found when attempting loyalty grant."""
    code = "client_not_found"
    status_code = 404

class LoyaltyGrantNegativeError(ValidationAppError):
    """Owner grant amount must be positive."""
    code = "grant_amount_must_be_positive"
    status_code = 422
```

**Module constant** (no analog — new for Phase 82):
```python
WELCOME_BONUS_KOPECKS: int = 50_000  # 500 ₽ welcome bonus
```

**Idempotent insert pattern with `pg_insert`** (lines 393–404 of analog):
```python
stmt = (
    pg_insert(PromoRedemption)
    .values(
        promo_code_id=promo_code_id,
        client_id=client_id,
        ...
    )
    .on_conflict_do_nothing(constraint="uq_promo_redemptions_online_payment_id")
)
await session.execute(stmt)
await session.flush()
```
For welcome accrual: use `on_conflict_do_nothing(constraint="uq_loyalty_ledger_welcome")` — the partial UNIQUE index enforces one welcome row per client even under concurrent creation.

**Raw SQL SUM fold for balance** (mirrors lines 191–218 pattern of analog for COUNT):
```python
row = (
    await session.execute(
        text(
            "SELECT COALESCE(SUM(amount_kopecks), 0) AS balance "
            "FROM loyalty_ledger WHERE client_id = :client_id"
        ),
        {"client_id": str(client_id)},
    )
).mappings().one()
balance = int(row["balance"])
```

**Raw SQL paginated history** (mirrors client_portal/repository.py pattern):
```python
count_row = (
    await session.execute(
        text("SELECT COUNT(*) AS cnt FROM loyalty_ledger WHERE client_id = :client_id"),
        {"client_id": str(client_id)},
    )
).mappings().one()
total = int(count_row["cnt"])

rows = (
    await session.execute(
        text(
            "SELECT id, entry_type, amount_kopecks, created_at "
            "FROM loyalty_ledger WHERE client_id = :client_id "
            "ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        ),
        {"client_id": str(client_id), "limit": page_size, "offset": (page - 1) * page_size},
    )
).mappings().all()
```

**Audit emit pattern co-transactional** (lines 132–142 of `clients/service.py`):
```python
await audit.emit(
    session,
    "loyalty_accrued",
    actor_user_id=actor_id,          # None for welcome (system); staff UUID for owner_grant
    resource_type="loyalty",
    resource_id=ledger_row_id,
    client_id=str(client_id),
    entry_id=str(ledger_row_id),
    amount_kopecks=amount_kopecks,
    entry_type=entry_type,
    actor=actor_description,          # "welcome" or "owner:<user_id>"
)
```
No `session.commit()` — caller commits. `session.flush()` after `pg_insert` to surface constraint errors.

---

### `apps/backend/app/modules/loyalty/permissions.py` (middleware, request-response)

**Analog:** `apps/backend/app/modules/payments/permissions.py` (lines 1–63) — exact pattern

**Full pattern to copy** (all 63 lines of analog):
```python
"""Loyalty module RBAC factories (Phase 82).

require_owner_for_loyalty_grant() admits ONLY owner on POST /loyalty/grant.
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
    """Return a FastAPI dependency admitting ONLY Role.OWNER on grant endpoint."""

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

Key invariant: `("rbac_forbidden", "rbac")` is already in `LOCKED_AUDIT_EVENTS` — no new pair needed for this emit.

---

### `apps/backend/app/modules/loyalty/router.py` (controller, request-response)

**Analog:** `apps/backend/app/modules/client_portal/router.py` (lines 137–235)

**APIRouter declaration + tags/operationId pattern** (lines 137 of analog):
```python
router = APIRouter(tags=["Client-Portal"])
# All client endpoints: operation_id="client_get_loyalty_balance" prefix
```

**Client-read endpoint pattern — IDOR-safe** (lines 145–163 of analog):
```python
@router.get(
    "/loyalty/balance",
    response_model=ResponseEnvelope[ClientLoyaltyBalanceResponse],
    operation_id="client_get_loyalty_balance",
    summary="Current bonus balance for the authenticated client (LOYL-03; IDOR-safe)",
)
async def client_get_loyalty_balance(
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientLoyaltyBalanceResponse]:
    """D-20-IDOR: client_id sourced from require_client() principal only.
    D-69-03: 200 with { balanceKopecks: 0 } when no rows, never 404.
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.get_client_loyalty_balance(session, client.id)
    return envelope(result)
```

**Paginated history endpoint pattern** (lines 185–211 of analog):
```python
@router.get(
    "/loyalty/history",
    response_model=ResponseEnvelope[PaginatedData[ClientLoyaltyHistoryItem]],
    operation_id="client_list_loyalty_history",
    summary="Paginated loyalty ledger history for the authenticated client",
)
async def client_list_loyalty_history(
    query: Annotated[PageQuery, Depends()],
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[ClientLoyaltyHistoryItem]]:
    """IDOR-safe via require_client() principal — client_id never from URL.
    No try/except — AppError bubbles.
    """
    page = await service.list_client_loyalty_history(session, client.id, query)
    return envelope(page)
```

**Owner-grant staff endpoint** (new pattern using `require_owner_for_loyalty_grant`):
```python
# Mount on the clients router or a new staff loyalty router:
@router.post(
    "/clients/{client_id}/loyalty/grant",
    response_model=ResponseEnvelope[ClientLoyaltyGrantResponse],
    status_code=status.HTTP_201_CREATED,
    operation_id="owner_grant_loyalty",
    summary="Owner-only: manually grant bonus kopecks to a client (ACCR-02)",
)
async def owner_grant_loyalty(
    client_id: UUID,
    payload: LoyaltyGrantRequest,
    actor: Annotated[CurrentUser, Depends(require_owner_for_loyalty_grant())],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientLoyaltyGrantResponse]:
    """Reception → 403 via require_owner_for_loyalty_grant.
    RBAC-04 ordering: auth → custom_perm → verify_csrf → get_db.
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.owner_grant_loyalty(session, actor, client_id, payload)
    await session.commit()
    return envelope(result)
```

---

### `apps/backend/app/modules/loyalty/schemas.py` (model, request-response)

**Analog:** `apps/backend/app/modules/client_portal/schemas.py` — `ResponseData` subclasses

**Imports pattern** (lines 21–22 of analog):
```python
from app.core.schemas import BackendSchemaBase, ResponseData
```

**Client read response schemas** (camelCase via `alias_generator=to_camel` inherited from `ResponseData`):
```python
class ClientLoyaltyBalanceResponse(ResponseData):
    balance_kopecks: int  # wire: balanceKopecks

class ClientLoyaltyHistoryItem(ResponseData):
    id: UUID
    type: str             # entry_type: 'welcome' | 'owner_grant' | 'redemption'
    amount_kopecks: int   # wire: amountKopecks (signed)
    created_at: datetime  # wire: createdAt (ISO-8601 with TZ)

class ClientLoyaltyGrantResponse(ResponseData):
    entry_id: UUID        # wire: entryId
    balance_kopecks: int  # wire: balanceKopecks (new balance after grant)
```

**Owner-grant request body** (strict inbound — use `BackendSchemaBase` with `extra='forbid'`):
```python
class LoyaltyGrantRequest(BackendSchemaBase):
    amount_kopecks: int           # wire: amountKopecks; must be > 0
    reason: str
    category: Literal['promo', 'referral', 'manual']
```

---

### `apps/backend/app/core/audit.py` (modify — add to `LOCKED_AUDIT_EVENTS`)

**Analog:** `apps/backend/app/core/audit.py` — existing frozenset entries (lines 263–447)

**Pattern — add one new pair as a versioned block** (mirror lines 437–446 format):
```python
        # v2.3 (Phase 82 lock — INFRA-15; emitted in Phase 82 loyalty service)
        # Loyalty accrual lifecycle (ACCR-01 welcome + ACCR-02 owner_grant):
        # Pre-registered BEFORE any callsite per INFRA-15 discipline.
        # Single event covers welcome + owner_grant (distinguished by entry_type/actor in payload).
        ("loyalty_accrued", "loyalty"),
```

Current `LOCKED_AUDIT_EVENTS` count is **101** (line 237 of `test_audit_taxonomy.py`). Adding 1 new pair → **102**. The count-guard test must be bumped to 102.

---

### `apps/backend/app/core/audit_payloads.py` (modify — add payload class + registry entry)

**Analog:** `apps/backend/app/core/audit_payloads.py` — `BookingRescheduledPayload` (lines 494–512) for a compact, versioned payload with `Literal` typing.

**New payload class pattern**:
```python
# ---------------------------------------------------------------------------
# v2.3 (Phase 82 lock — emitted in Phase 82 loyalty service)
# ---------------------------------------------------------------------------

class LoyaltyAccruedPayload(BaseModel):
    """Payload schema for ("loyalty_accrued", "loyalty") — Phase 82 ACCR-01/ACCR-02.

    Single event for both welcome accrual and owner_grant (distinguished by
    entry_type and actor fields in payload).
    actor: "welcome" for system-initiated welcome bonus, "owner:<uuid>" for staff grant.
    """

    model_config = ConfigDict(extra="forbid")

    client_id: UUID
    entry_id: UUID
    amount_kopecks: int
    entry_type: Literal["welcome", "owner_grant"]  # 'redemption' not emitted here
    actor: str   # "welcome" | "owner:<user_uuid>"
```

**Registry entry** (append to `AUDIT_PAYLOAD_SCHEMAS` dict at line 1275+):
```python
    # v2.3 (Phase 82 loyalty accrual):
    ("loyalty_accrued", "loyalty"): LoyaltyAccruedPayload,
```

---

### `apps/backend/app/modules/clients/service.py` (modify — welcome accrual callsite)

**Analog:** `apps/backend/app/modules/clients/service.py` lines 109–144 (the `create_client` function where `client_created` audit is emitted co-transactionally)

**Existing pattern to insert into** (lines 121–143):
```python
async def create_client(session, actor, data):
    client = await repository.insert_client(session, actor.id, data)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_phone_conflict(exc):
            raise PhoneExistsError("phone_exists") from exc
        raise

    # D-08 client_created payload
    await audit.emit(session, "client_created", actor_user_id=actor.id,
                     resource_type="client", resource_id=client.id, ...)

    # ← INSERT WELCOME ACCRUAL HERE (after client_created emit, before commit)
    # Import: from app.modules.loyalty import service as loyalty_service
    # (add to .importlinter ignore_imports: clients.service -> loyalty.service)
    await loyalty_service.accrue_welcome_bonus(session, client_id=client.id)

    await session.commit()
    return ClientResponse.model_validate(client)
```

The welcome accrual must occur **before** `session.commit()` in the same UoW. It emits its own `loyalty_accrued` audit row co-transactionally. The idempotent insert (`on_conflict_do_nothing`) ensures replay safety.

**importlinter edge to add** (mirroring lines 192–194 of `.importlinter`):
```ini
    app.modules.clients.service -> app.modules.loyalty.service
```

---

### `apps/backend/alembic/versions/0054_loyalty_ledger.py` (migration, CRUD)

**Analog:** `apps/backend/alembic/versions/0046_promo_codes.py` — specifically the `promo_redemptions` table block (lines 92–138) and partial UNIQUE index pattern (lines 82–90)

**Header pattern** (lines 1–32 of analog):
```python
"""loyalty_ledger append-only table (Phase 82 LOYL-03).

Revision ID: 0054_loyalty_ledger
Revises: 0053_booking_notif_widen_kind_rescheduled
Create Date: 2026-06-05 00:00:00.000000
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
```

**Table creation pattern** (lines 93–138 of analog, adapted):
```python
def upgrade() -> None:
    op.create_table(
        "loyalty_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entry_type", sa.String(16), nullable=False),
        sa.Column("amount_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("category", sa.String(16), nullable=True),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_loyalty_ledger")),
        sa.ForeignKeyConstraint(
            ["client_id"], ["clients.id"],
            name=op.f("fk_loyalty_ledger_client_id_clients"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "entry_type IN ('welcome', 'owner_grant', 'redemption')",
            name=op.f("ck_loyalty_ledger_entry_type"),
        ),
    )
    # Partial UNIQUE: one welcome row per client — literal index name (NOT via op.f())
    # per 0034/0037/0046 create_index precedent.
    op.create_index(
        "uq_loyalty_ledger_welcome",
        "loyalty_ledger",
        ["client_id"],
        unique=True,
        postgresql_where=text("entry_type = 'welcome'"),
    )
    # Plain index on client_id for balance/history fold performance
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

---

### `apps/backend/tests/unit/test_loyalty_audit_events.py` (test, event-driven)

**Analog:** `apps/backend/tests/unit/test_locked_audit_events.py` (all 143 lines)

**Pattern — three assertion groups**:
```python
"""Phase 82 — LOCKED registry tests for loyalty_accrued audit event.

Mirrors test_locked_audit_events.py discipline (Phase 50 D-50-23).
"""
from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.core.audit import LOCKED_AUDIT_EVENTS
from app.core.audit_payloads import AUDIT_PAYLOAD_SCHEMAS, LoyaltyAccruedPayload

# Group 1: pair is in LOCKED_AUDIT_EVENTS
def test_loyalty_accrued_event_locked():
    assert ("loyalty_accrued", "loyalty") in LOCKED_AUDIT_EVENTS

# Group 2: payload validates + rejects extras
def test_loyalty_accrued_payload_validates():
    payload = LoyaltyAccruedPayload(
        client_id=uuid4(), entry_id=uuid4(),
        amount_kopecks=50000, entry_type="welcome", actor="welcome",
    )
    assert payload.amount_kopecks == 50000

def test_loyalty_accrued_payload_rejects_extra_fields():
    with pytest.raises(ValidationError):
        LoyaltyAccruedPayload(
            client_id=uuid4(), entry_id=uuid4(),
            amount_kopecks=50000, entry_type="welcome", actor="welcome",
            foo="bar",  # type: ignore[call-arg]
        )

# Group 3: AUDIT_PAYLOAD_SCHEMAS maps the pair
def test_audit_payload_schemas_registers_loyalty_accrued():
    assert AUDIT_PAYLOAD_SCHEMAS[("loyalty_accrued", "loyalty")] is LoyaltyAccruedPayload
```

---

### `apps/backend/tests/unit/test_audit_taxonomy.py` (modify — bump count guard)

**Analog:** `apps/backend/tests/unit/test_audit_taxonomy.py` lines 165–242

**The count-guard assertion to modify** (line 237):
```python
# BEFORE:
assert len(LOCKED_AUDIT_EVENTS) == 101, (
    "LOCKED_AUDIT_EVENTS size drifted: expected 101 "
    ...
)
# AFTER:
assert len(LOCKED_AUDIT_EVENTS) == 102, (
    "LOCKED_AUDIT_EVENTS size drifted: expected 102 "
    "(... + 1 v2.3/P82 loyalty_accrued), "
    f"got {len(LOCKED_AUDIT_EVENTS)}"
)
```

The docstring narrative must also be extended with a v2.3 line explaining the Phase 82 +1 addition.

---

### `apps/client-pwa/src/screens/sheets/LoyaltySheet.jsx` (component, request-response)

**Analog 1:** `apps/client-pwa/src/screens/sheets/HistorySheets.jsx` — `VisitHistorySheet` (lines 12–161) for the full-screen sheet skeleton, sheet-up animation, `SubSheetHeader`, `PullToRefresh`, grouped list, empty state, divider pattern.

**Analog 2:** `apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx` — `CardSheet` (lines 324–398) for how a sheet hooks into `useClientPaymentMethod` and renders loading/error states.

**Full-screen sheet wrapper pattern** (lines 46–50 of `HistorySheets.jsx`):
```jsx
<div style={{
  position: 'absolute', inset: 0, zIndex: 220, background: 'var(--bg)',
  display: 'flex', flexDirection: 'column',
  animation: 'sheet-up 0.32s cubic-bezier(0.32, 0.72, 0.2, 1)',
}}>
  <StatusBar />
  <SubSheetHeader title="История бонусов" onClose={onClose} />
  <PullToRefresh scrollPaddingTop={0} onRefresh={() => refetch()}>
    ...
  </PullToRefresh>
</div>
```

**Grouped card list pattern** (lines 143–157 of `HistorySheets.jsx`):
```jsx
{groups.map(g => (
  <div key={g.label} style={{ padding: '0 16px 14px' }}>
    <div className="t-mini" style={{ color: 'var(--text-3)', padding: '4px 4px 8px' }}>
      {g.label}
    </div>
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      {g.items.map((item, i) => (
        <React.Fragment key={item.id}>
          {i > 0 && <div style={{ height: 0.5, background: 'var(--border)', marginLeft: 44 }} />}
          <BonusRow item={item} />
        </React.Fragment>
      ))}
    </div>
  </div>
))}
```

**Icon container + row pattern** (lines 164–190 of `HistorySheets.jsx` `VisitRow`):
```jsx
function BonusRow({ item }) {
  const isAccrual = item.amountKopecks > 0;
  return (
    <div style={{ padding: '12px 16px', display: 'flex', gap: 12, alignItems: 'center' }}>
      <div style={{
        width: 32, height: 32, borderRadius: 8,
        background: isAccrual ? 'var(--accent-soft)' : 'var(--danger-soft)',
        color: isAccrual ? 'var(--accent-deep)' : 'var(--danger)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
      }}>
        <Icon name={isAccrual ? 'gift' : 'arrowUp'} size={16} color="currentColor" />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="t-small" style={{ color: 'var(--text)', fontWeight: 700 }}>
          {ENTRY_TYPE_LABELS[item.type] ?? item.type}
        </div>
        <div className="t-small" style={{ marginTop: 1, color: 'var(--text-2)' }}>
          {format(parseISO(item.createdAt), 'd MMMM yyyy', { locale: ru })}
        </div>
      </div>
      <div style={{
        fontSize: 13, fontWeight: 700,
        color: isAccrual ? 'var(--accent-deep)' : 'var(--danger)',
      }}>
        {isAccrual ? '+' : '−'}{formatMoney(Math.abs(item.amountKopecks))}
      </div>
    </div>
  );
}
```

**Empty state pattern** (lines 118–139 of `HistorySheets.jsx`):
```jsx
{items.length === 0 && (
  <div style={{ padding: '40px 24px', textAlign: 'center' }}>
    <div style={{
      width: 60, height: 60, borderRadius: 999, margin: '0 auto 16px',
      background: 'var(--surface-2)', color: 'var(--text-3)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <Icon name="gift" size={28} color="currentColor" />
    </div>
    <div className="t-h3" style={{ fontSize: 16 }}>Бонусов пока нет</div>
    <div className="t-small" style={{ marginTop: 6, color: 'var(--text-2)' }}>
      После первой активности здесь появится история начислений.
    </div>
  </div>
)}
```

**Skeleton pattern** (standard `.sk .sk-line` — used in CardSheet and elsewhere):
```jsx
<div className="card" style={{ padding: 16 }}>
  {[80, 60, 70, 50].map((w, i) => (
    <div key={i} className="sk sk-line" style={{ width: `${w}%`, marginBottom: i < 3 ? 12 : 0 }} />
  ))}
</div>
```

**Load-more button pattern** (`.btn.btn-ghost.btn-sm`):
```jsx
{items.length < total && (
  <div style={{ padding: '0 16px 24px', textAlign: 'center' }}>
    <button
      onClick={fetchNextPage}
      className="btn btn-ghost btn-sm press"
      disabled={isFetchingNextPage}
    >
      {isFetchingNextPage ? <span className="ptr-spin" style={{ width: 18, height: 18 }} /> : 'Загрузить ещё'}
    </button>
  </div>
)}
```

**LoyaltyBalanceCard** (inline in `ProfileScreen.jsx`, mirrors `PROFILE_FEATURE_FLAGS.weeklyActivity` block at lines 269–301):
```jsx
{PROFILE_FEATURE_FLAGS.clubBonuses && (
  <div style={{ padding: '0 16px 18px' }}>
    <LoyaltyBalanceCard onOpen={onOpenBonusHistory} />
  </div>
)}
```

Card structure mirrors the `.card` pattern at lines 102, 272 of `ProfileScreen.jsx` with padding 16px.

**Imports for `LoyaltySheet.jsx`**:
```jsx
import React from 'react';
import { Icon } from '@/components/Icon.jsx';
import { StatusBar } from '@/components/StatusBar.jsx';
import { PullToRefresh } from '@/components/PullToRefresh.jsx';
import { SubSheetHeader } from '@/screens/sheets/ProfileExtraSheets.jsx';
import { useClientLoyaltyBalance, useClientLoyaltyHistory } from '@/data';
import { formatMoney } from '@/utils/format.js';
import { format, parseISO } from 'date-fns';
import { ru } from 'date-fns/locale/ru';
```

---

### `apps/client-pwa/src/lib/clientQueries.ts` (modify — add 2 hooks + 2 keys)

**Analog:** `apps/client-pwa/src/lib/clientQueries.ts` — `useClientWeeklyActivity` (lines 701–711) and `useClientPaymentMethod` (lines 722–732) — exact shape to mirror.

**Key factory entries to add** (after line 40 in `clientPortalKeys`):
```typescript
  loyaltyBalance: () => [...clientPortalKeys.all, 'loyalty-balance'] as const,
  loyaltyHistory: (page: number) => [...clientPortalKeys.all, 'loyalty-history', page] as const,
```

**Hook pattern** (mirror `useClientWeeklyActivity` lines 701–711):
```typescript
interface LoyaltyBalanceData {
  balanceKopecks: number
}

/** GET /api/v1/client/loyalty/balance — current bonus balance (LOYL-03) */
export function useClientLoyaltyBalance() {
  return useQuery({
    queryKey: clientPortalKeys.loyaltyBalance(),
    queryFn: async () => {
      const res = await clientRequest('get', '/api/v1/client/loyalty/balance')
      return (res as { data: LoyaltyBalanceData }).data
    },
    staleTime: 30_000,
  })
}

interface LoyaltyHistoryItem {
  id: string
  type: 'welcome' | 'owner_grant' | 'redemption'
  amountKopecks: number
  createdAt: string
}

/** GET /api/v1/client/loyalty/history?page=N — paginated bonus history */
export function useClientLoyaltyHistory(page = 1) {
  return useQuery({
    queryKey: clientPortalKeys.loyaltyHistory(page),
    queryFn: async () => {
      const res = await clientRequest('get', `/api/v1/client/loyalty/history?page=${page}`)
      return (res as { data: PaginatedResult<LoyaltyHistoryItem> }).data
    },
    staleTime: 30_000,
  })
}
```

**Export from `apps/client-pwa/src/data/index.js`** (mirror lines 48–50 pattern):
```javascript
  useClientLoyaltyBalance,
  useClientLoyaltyHistory,
```

---

## Shared Patterns

### Caller-owns-transaction (no `session.commit()` in service)
**Source:** `apps/backend/app/modules/promo_codes/service.py` lines 1–22 (module docstring) and line 404
**Apply to:** `loyalty/service.py` — all service functions use only `session.flush()`. The router endpoint owns `session.commit()`.
```python
await session.flush()
_log.info("loyalty_accrued", ...)
# NO session.commit() here — caller commits
```

### Raw SQL text() reads — no cross-module ORM imports
**Source:** `apps/backend/app/modules/client_portal/repository.py` lines 53–80, 173–201
**Apply to:** `loyalty/service.py` or `loyalty/repository.py` for all balance/history reads
```python
# D-54-08: cross-module read via raw SQL text() only — no ORM import of Client
row = (await session.execute(text("SELECT ... FROM loyalty_ledger WHERE client_id = :cid"), {"cid": str(client_id)})).mappings().one_or_none()
```

### Audit emit — literal strings, co-transactional
**Source:** `apps/backend/app/modules/clients/service.py` lines 132–142
**Apply to:** `loyalty/service.py` (both `accrue_welcome_bonus` and `owner_grant_loyalty`)
```python
await audit.emit(
    session,
    "loyalty_accrued",           # MUST be a literal string (AST gate)
    actor_user_id=actor_id,
    resource_type="loyalty",     # MUST be a literal string (AST gate)
    resource_id=entry_id,
    ...
)
```

### structlog logger declaration
**Source:** `apps/backend/app/modules/promo_codes/service.py` line 36
**Apply to:** `loyalty/service.py`
```python
_log = structlog.get_logger("modules.loyalty.service")
```

### camelCase wire schema — `ResponseData` subclass
**Source:** `apps/backend/app/modules/client_portal/schemas.py` lines 21–81
**Apply to:** `loyalty/schemas.py`
```python
from app.core.schemas import ResponseData, BackendSchemaBase
class ClientLoyaltyBalanceResponse(ResponseData):
    balance_kopecks: int  # camelCase alias auto-applied: balanceKopecks
```

### Feature flag gate (PWA)
**Source:** `apps/client-pwa/src/screens/ProfileScreen.jsx` lines 19–31 (`PROFILE_FEATURE_FLAGS`)
**Apply to:** Add `clubBonuses: false` to the same `PROFILE_FEATURE_FLAGS` constant (or `true` when backend is ready). Mirror the `weeklyActivity` / `linkedCard` pattern exactly.
```jsx
const PROFILE_FEATURE_FLAGS = {
  weeklyActivity: true,
  tenureBadge:    false,
  weeksStat:      false,
  linkedCard:     true,
  clubBonuses:    true,   // Phase 82: wired to GET /client/loyalty/balance + history
};
```

### formatMoney — never divide manually
**Source:** `apps/client-pwa/src/utils/format.js` lines 8–15
**Apply to:** `LoyaltySheet.jsx` and `LoyaltyBalanceCard`
```jsx
import { formatMoney } from '@/utils/format.js';
// CORRECT: formatMoney(Math.abs(item.amountKopecks))
// WRONG: `${item.amountKopecks / 100} ₽`
```

### Date formatting (ISO → Russian long date)
**Source:** `apps/client-pwa/src/utils/format.js` lines 29–43 (`formatRuDate`)
**Apply to:** `BonusRow` in `LoyaltySheet.jsx`
```jsx
import { format, parseISO } from 'date-fns';
import { ru } from 'date-fns/locale/ru';
// For ISO datetime strings from the API:
format(parseISO(item.createdAt), 'd MMMM yyyy', { locale: ru })
```

---

## `.importlinter` Additions Required

**Source:** `apps/backend/.importlinter` lines 13–103 (`modules-independent` contract)

Three edits needed:

1. Add `app.modules.loyalty` to the `modules` list (mirrors `app.modules.promo_codes` block at line 42):
```ini
    app.modules.loyalty
    # Phase 82 LOYL-01 — loyalty module registered per INFRA-15 discipline.
    # Welcome accrual accessed by clients.service via ignore_imports edge below.
    # Client read endpoints live in client_portal/router.py referencing loyalty.service.
```

2. Add `ignore_imports` edge for welcome accrual callsite (mirrors lines 192–194):
```ini
    app.modules.clients.service -> app.modules.loyalty.service
```

3. Add `ignore_imports` edge for client portal reading loyalty (if loyalty service is called from `client_portal/service.py`):
```ini
    app.modules.client_portal.service -> app.modules.loyalty.service
```
Alternatively, loyalty endpoints can live in a dedicated `loyalty/router.py` mounted at the app level — this avoids the cross-module edge for client_portal entirely.

---

## No Analog Found

All 14 files have matching analogs. No files lack codebase precedent.

---

## Metadata

**Analog search scope:** `apps/backend/app/modules/`, `apps/backend/app/core/`, `apps/backend/alembic/versions/`, `apps/backend/tests/unit/`, `apps/client-pwa/src/`
**Files scanned:** ~25 source files read
**Pattern extraction date:** 2026-06-05
