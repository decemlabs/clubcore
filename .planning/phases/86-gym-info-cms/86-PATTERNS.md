# Phase 86: Gym-Info / CMS - Pattern Map

**Mapped:** 2026-06-06
**Files analyzed:** 11 (new/modified)
**Analogs found:** 11 / 11

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/backend/app/modules/gym/__init__.py` | config | — | `apps/backend/app/modules/loyalty/__init__.py` | exact |
| `apps/backend/app/modules/gym/models.py` | model | CRUD | `apps/backend/app/modules/clients/models.py` (JSONB cols) | exact |
| `apps/backend/app/modules/gym/schemas.py` | model | request-response | `apps/backend/app/modules/loyalty/schemas.py` | exact |
| `apps/backend/app/modules/gym/repository.py` | service | CRUD | `apps/backend/app/modules/trainers/repository.py` | role-match |
| `apps/backend/app/modules/gym/service.py` | service | request-response | `apps/backend/app/modules/loyalty/service.py` | role-match |
| `apps/backend/app/modules/gym/router.py` | controller | request-response | `apps/backend/app/modules/loyalty/router.py` (client GET) + `apps/backend/app/modules/trainers/router.py` (owner PUT) | exact |
| `apps/backend/app/api/v1/router.py` | config | — | self (add `gym_router` include) | exact |
| `apps/backend/alembic/versions/0058_gym_info.py` | migration | CRUD | `apps/backend/alembic/versions/0046_promo_codes.py` (DDL) | role-match |
| `apps/backend/alembic/versions/0059_seed_gym_info.py` | migration | batch | `apps/backend/alembic/versions/0051_seed_fit15_promo.py` | exact |
| `apps/client-pwa/src/lib/clientQueries.ts` | hook | request-response | self (add `useClientGymInfo` following `useClientLoyaltyBalance` pattern) | exact |
| `apps/client-pwa/src/data/index.js` | config | — | self (add `useClientGymInfo` export following `useClientLoyaltyBalance/History` export) | exact |
| `apps/client-pwa/src/screens/sheets/GymInfoSheet.jsx` | component | request-response | `apps/client-pwa/src/screens/sheets/LoyaltySheet.jsx` (BonusHistorySheet) | exact |

---

## Pattern Assignments

### `apps/backend/app/modules/gym/models.py` (model, CRUD)

**Analog:** `apps/backend/app/modules/clients/models.py` (JSONB pattern) + `apps/backend/app/modules/trainers/models.py` (structure)

**Imports pattern** (`clients/models.py` lines 26-50):
```python
from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPkMixin
```

**JSONB column pattern** (`clients/models.py` lines 96-99, 131-134):
```python
emergency_contact: Mapped[dict[str, Any] | None] = mapped_column(
    JSONB,
    nullable=True,
)
# and
notif_prefs: Mapped[dict[str, Any] | None] = mapped_column(
    JSONB,
    nullable=True,
)
```

**Singleton gym model — no soft-delete, no FK, JSONB for lists:**
```python
# gym module is singleton: one row, no UUIDPkMixin needed for PK rotation,
# use Integer PK or keep UUID with a CHECK CONSTRAINT id=1.
# No SoftDeleteMixin (singleton cannot be deleted), no created_by FK.
# Scalar cols: Text nullable=False for name/tagline/address/city/metro/phone/email
# JSONB cols: hours, amenities, rules, social — Mapped[list[Any]]
```

**No soft-delete, no TimestampMixin FK, but keep TimestampMixin** (`trainers/models.py` line 23):
```python
class Trainer(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin):
# For GymInfo: use Base + UUIDPkMixin + TimestampMixin only (no SoftDeleteMixin)
```

---

### `apps/backend/app/modules/gym/schemas.py` (model, request-response)

**Analog:** `apps/backend/app/modules/loyalty/schemas.py` (lines 1-67)

**Imports pattern** (`loyalty/schemas.py` lines 1-15):
```python
from __future__ import annotations

from pydantic import Field

from app.core.schemas import BackendSchemaBase, ResponseData
```

**ResponseData read DTO pattern** (`loyalty/schemas.py` lines 18-25):
```python
class ClientLoyaltyBalanceResponse(ResponseData):
    """Wire: camelCase via alias_generator=to_camel on ResponseData base."""

    balance_kopecks: int  # wire: balanceKopecks
```

**BackendSchemaBase write DTO pattern** (`loyalty/schemas.py` lines 54-67):
```python
class LoyaltyGrantRequest(BackendSchemaBase):
    """Owner-only write request body. extra='forbid' rejects unknown keys."""

    amount_kopecks: int = Field(gt=0)
    reason: str = Field(max_length=255)
```

**For gym schemas — three DTOs:**
- `GymInfoResponse(ResponseData)` — read DTO for both client GET and owner PUT response. Fields: `name: str`, `tagline: str`, `address: str`, `city: str`, `metro: str | None`, `phone: str`, `email: str`, `hours: list[Any]`, `amenities: list[Any]`, `rules: list[str]`, `social: list[Any]`. Wire: camelCase (e.g. `hours` → `hours`, `amenities` → `amenities`, `social` → `social`).
- `GymInfoUpdateRequest(BackendSchemaBase)` — owner PUT body. All fields optional (partial upsert). Each field mirrors `GymInfoResponse` but with `| None = None` default.

---

### `apps/backend/app/modules/gym/repository.py` (service, CRUD)

**Analog:** `apps/backend/app/modules/trainers/repository.py` (lines 1-113)

**Module docstring pattern** (`trainers/repository.py` lines 1-16):
```python
"""Trainers repository — single point of access to the `Trainer` ORM (TRN-01, D-31-08).

This is the ONLY module that imports the `Trainer` ORM model.
Transaction control (D-03): NO session.commit() and NO session.flush() here.
Caller (service.py) owns the transactional moment.
"""

from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.trainers.models import Trainer
```

**Simple select pattern** (`trainers/repository.py` lines 33-40):
```python
async def get_alive(session: AsyncSession, trainer_id: UUID) -> Trainer | None:
    stmt: Select[tuple[Trainer]] = select(Trainer).where(
        Trainer.id == trainer_id,
        Trainer.deleted_at.is_(None),
    )
    result: Trainer | None = await session.scalar(stmt)
    return result
```

**For gym repository — two functions:**
```python
async def get_singleton(session: AsyncSession) -> GymInfo | None:
    """Return the single gym row, or None if seed not yet run."""
    stmt = select(GymInfo).limit(1)
    return await session.scalar(stmt)

async def upsert_singleton(session: AsyncSession, data: GymInfoUpdateRequest) -> GymInfo:
    """Update the singleton row. Caller owns flush+commit (D-03)."""
    gym = await get_singleton(session)
    if gym is None:
        # Should not happen after migration — but guard defensively
        gym = GymInfo(...)
        session.add(gym)
    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(gym, key, value)
    return gym
```

---

### `apps/backend/app/modules/gym/service.py` (service, request-response)

**Analog:** `apps/backend/app/modules/loyalty/service.py` (lines 216-227) for the read path; `apps/backend/app/modules/trainers/service.py` (lines 57-87) for the write path with flush+commit.

**Simple read service pattern** (`loyalty/service.py` lines 216-226):
```python
async def get_client_loyalty_balance(
    session: AsyncSession,
    client_id: UUID,
) -> ClientLoyaltyBalanceResponse:
    """D-69-03: empty → 0, never 404."""
    balance_kopecks = await _sum_balance(session, client_id)
    return ClientLoyaltyBalanceResponse(balance_kopecks=balance_kopecks)
```

**Write service with flush+commit pattern** (`trainers/service.py` lines 57-87):
```python
async def create_trainer(
    session: AsyncSession,
    actor: CurrentUser,
    data: TrainerCreateRequest,
) -> TrainerResponse:
    trainer = await repository.insert_trainer(session, data)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise
    await audit.emit(session, "trainer_created", actor_user_id=actor.id, ...)
    await session.commit()
    return TrainerResponse.model_validate(trainer)
```

**For gym service — two functions (no audit on singleton upsert, minimal):**
```python
async def get_gym_info(session: AsyncSession) -> GymInfoResponse:
    """Return singleton gym row. 404 if seed missing (GymInfoNotFoundError)."""
    gym = await repository.get_singleton(session)
    if gym is None:
        raise GymInfoNotFoundError("gym_info_not_found")
    return GymInfoResponse.model_validate(gym)

async def update_gym_info(
    session: AsyncSession,
    actor: CurrentUser,
    data: GymInfoUpdateRequest,
) -> GymInfoResponse:
    """Upsert singleton. Caller-owns-txn: flush+commit here (singleton write, D-03)."""
    gym = await repository.upsert_singleton(session, data)
    await session.flush()
    await session.commit()
    return GymInfoResponse.model_validate(gym)
```

---

### `apps/backend/app/modules/gym/router.py` (controller, request-response)

**Analog A (client GET):** `apps/backend/app/modules/loyalty/router.py` (lines 1-54)
**Analog B (owner PUT):** `apps/backend/app/modules/trainers/router.py` (lines 72-87, POST pattern adapted to PUT)

**Router file structure** — two endpoints in one router file, matching loyalty pattern:

**Imports pattern** (`loyalty/router.py` lines 1-34):
```python
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import ClientPrincipal, require_client
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.loyalty import service
from app.modules.loyalty.schemas import ClientLoyaltyBalanceResponse

router = APIRouter(tags=["Client-Portal"])
```

**Client read endpoint pattern** (`loyalty/router.py` lines 37-54):
```python
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
    """D-20-IDOR: client_id from require_client() principal — never from URL.
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.get_client_loyalty_balance(session, client.id)
    return envelope(result)
```

**Owner-only write endpoint pattern** (`trainers/router.py` lines 72-87):
```python
@router.post(
    "",
    response_model=ResponseEnvelope[TrainerResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_trainer(
    payload: TrainerCreateRequest,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.CREATE, Resource.TRAINERS))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[TrainerResponse]:
    """CREATE permission + CSRF required (RBAC-04 ordering)."""
    trainer = await service.create_trainer(session, actor, payload)
    return envelope(trainer)
```

**For gym router — owner PUT uses `require_permission(Action.EDIT, Resource.SETTINGS)` or a new `Resource.GYM` (owner-only pair). RBAC-04 ordering: `require_permission(...)` declared BEFORE `verify_csrf`.**

The gym router hosts BOTH endpoints:
- `GET /gym` — client read path, `require_client()` gate, mounted via `v1.include_router(gym_router, prefix="/client")`
- `PUT /gym` — owner write path, `require_permission(Action.EDIT, Resource.GYM)` + `verify_csrf` gate, mounted via `v1.include_router(gym_owner_router, prefix="/gym")`

Two `APIRouter` instances in one file or one combined router — see v1/router.py inline import pattern at lines 101-111 for two routers from one module.

---

### `apps/backend/app/api/v1/router.py` (config — modification)

**Analog:** `apps/backend/app/api/v1/router.py` lines 101-112 (inline import + include pattern)

**Inline import + include pattern** (lines 101-112):
```python
# Phase 82 LOYL-01/LOYL-02 — loyalty client reads.
# Mounted at /api/v1/client (same prefix as client_portal_router) to expose
# /api/v1/client/loyalty/balance and /api/v1/client/loyalty/history.
# Separate router avoids a client_portal→loyalty cross-module edge (D-20-MODULE).
from app.modules.loyalty.router import router as loyalty_router  # noqa: E402

v1.include_router(loyalty_router, prefix="/client")
```

**For gym — two include_router calls (one per sub-router):**
```python
# Phase 86 GYM-01/GYM-02 — gym-info client read + owner write.
# Client read mounted at /api/v1/client/gym (require_client gate).
# Owner write mounted at /api/v1/gym (require_permission + verify_csrf gate).
from app.modules.gym.router import client_router as gym_client_router  # noqa: E402
from app.modules.gym.router import owner_router as gym_owner_router  # noqa: E402

v1.include_router(gym_client_router, prefix="/client")
v1.include_router(gym_owner_router, prefix="/gym")
```

**New `Resource.GYM` entry in `apps/backend/app/core/permissions.py`:**
Must add `GYM = "gym"` to `Resource` StrEnum and add `(Action.EDIT, Resource.GYM)` to `OWNER_ONLY` (reception → 403).

---

### `apps/backend/alembic/versions/0058_gym_info.py` (migration, DDL)

**Analog:** `apps/backend/alembic/versions/0046_promo_codes.py` (DDL structure)

**Revision header pattern** (`0051_seed_fit15_promo.py` lines 39-43):
```python
revision: str = "0051_seed_fit15_promo"
down_revision: str | None = "0050_clients_notif_prefs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**Chain:** `down_revision = "0057_payment_notifications_widen_kind"` (latest migration as of Phase 86).

**JSONB column DDL pattern** (from `0046_promo_codes.py` + clients migration):
```python
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade() -> None:
    op.create_table(
        "gym_info",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("tagline", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column("metro", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("hours", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("amenities", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("social", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

def downgrade() -> None:
    op.drop_table("gym_info")
```

---

### `apps/backend/alembic/versions/0059_seed_gym_info.py` (migration, batch/seed)

**Analog:** `apps/backend/alembic/versions/0051_seed_fit15_promo.py` (exact match)

**Complete seed migration pattern** (`0051_seed_fit15_promo.py` lines 30-71):
```python
"""Seed gym_info singleton baseline (Phase 86 GYM-03).

Revision ID: 0059_seed_gym_info
Revises: 0058_gym_info
...

Idempotency:
- INSERT ... ON CONFLICT (id) DO NOTHING — id is the PK.
- Re-running upgrade() is a verified no-op.

Downgrade hard-deletes the row (no FK references to gym_info).
"""

from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0059_seed_gym_info"
down_revision: str | None = "0058_gym_info"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SINGLETON_ID = "00000000-0000-0000-0000-000000000001"  # deterministic PK

def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO gym_info "
            "(id, name, tagline, address, city, metro, phone, email, "
            " hours, amenities, rules, social) "
            "VALUES (:id, :name, :tagline, :address, :city, :metro, :phone, :email, "
            "        :hours::jsonb, :amenities::jsonb, :rules::jsonb, :social::jsonb) "
            "ON CONFLICT (id) DO NOTHING"
        ).bindparams(
            id=_SINGLETON_ID,
            name="Мой зал · Тверская",
            tagline="Круглосуточный клуб в центре",
            address="Тверская, 18, 3 этаж",
            city="Москва",
            metro="5 мин от м. Пушкинская",
            phone="+7 495 123-45-67",
            email="tverskaya@mygym.ru",
            hours='[{"d":"Пн","open":"07:00","close":"23:00"},...]',
            amenities='[{"icon":"parking","label":"Парковка"},...]',
            rules='["Спортивная форма и сменная обувь обязательны",...]',
            social='[{"kind":"tg","label":"Telegram","handle":"@mygym_tverskaya"},...]',
        )
    )

def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM gym_info WHERE id = :id").bindparams(id=_SINGLETON_ID)
    )
```

**Key difference from FIT15:** conflict target is `(id)` (PK), not a partial unique index, because the gym singleton has a deterministic UUID PK. No `ON CONFLICT (...) WHERE ...` predicate needed.

**Content values** come directly from `apps/client-pwa/src/data/gym.js` (the file as read above — `GYM_INFO` object). Note: `staffToday`, `todayIdx`, `status`, and `photos` are NOT stored in the DB (CONTEXT.md: photos are frontend-only, computed fields are deferred).

---

### `apps/client-pwa/src/lib/clientQueries.ts` (hook, request-response — modification)

**Analog:** `apps/client-pwa/src/lib/clientQueries.ts` lines 22-43 (key factory) and lines 134-144 (`useClientHome` pattern)

**Key factory addition** (lines 22-43 — add `gymInfo` key):
```typescript
export const clientPortalKeys = {
  // ... existing keys ...
  loyaltyBalance: () => [...clientPortalKeys.all, 'loyalty-balance'] as const,
  loyaltyHistory: (page: number) => [...clientPortalKeys.all, 'loyalty-history', page] as const,
  // ADD:
  gymInfo: () => [...clientPortalKeys.all, 'gym-info'] as const,
} as const
```

**Simple GET hook pattern** (lines 135-143, `useClientHome`):
```typescript
/** GET /api/v1/client/gym — gym info */
export function useClientGymInfo() {
  return useQuery({
    queryKey: clientPortalKeys.gymInfo(),
    queryFn: async () => {
      const res = await clientRequest('get', '/api/v1/client/gym')
      return (res as { data: GymInfoData }).data
    },
    staleTime: 30_000,
  })
}
```

**`GymInfoData` interface** mirrors the `GymInfoResponse` schema — add before the hook:
```typescript
interface GymInfoData {
  name: string
  tagline: string | null
  address: string
  city: string | null
  metro: string | null
  phone: string | null
  email: string | null
  hours: Array<{ d: string; open: string; close: string }>
  amenities: Array<{ icon: string; label: string }>
  rules: string[]
  social: Array<{ kind: string; label: string; handle: string }>
}
```

---

### `apps/client-pwa/src/data/index.js` (config — modification)

**Analog:** `apps/client-pwa/src/data/index.js` lines 52-56 (loyalty export block)

**Pattern** (lines 52-56):
```javascript
  // Phase-82 LOYL-01 + LOYL-02: loyalty balance + history hooks
  useClientLoyaltyBalance,
  useClientLoyaltyHistory,
} from '../lib/clientQueries'
```

**Addition — append to the `export { ... } from '../lib/clientQueries'` block:**
```javascript
  // Phase-86 GYM-01: gym info hook
  useClientGymInfo,
```

Note: `GYM_INFO` from `./gym.js` is NOT re-exported here — `index.js` comment at line 13-14 already notes that `GYM_INFO` was removed (`NOTIFICATIONS, GYM_INFO, TRAINER_CANCEL → HomeScreen`). The new `useClientGymInfo` hook replaces `GYM_INFO` entirely for `GymInfoSheet`.

---

### `apps/client-pwa/src/screens/sheets/GymInfoSheet.jsx` (component, request-response — rewrite)

**Analog:** `apps/client-pwa/src/screens/sheets/LoyaltySheet.jsx` (`BonusHistorySheet`, lines 131-end)

**Sheet outer structure pattern** (`LoyaltySheet.jsx` lines 197-206):
```jsx
return (
  <div style={{
    position: 'absolute', inset: 0, zIndex: 220, background: 'var(--bg)',
    display: 'flex', flexDirection: 'column',
    animation: 'sheet-up 0.32s cubic-bezier(0.32, 0.72, 0.2, 1)',
  }}>
    <StatusBar />
    <SubSheetHeader title="История бонусов" onClose={onClose} />

    <PullToRefresh scrollPaddingTop={0} onRefresh={handleRefresh}>
      {/* content */}
    </PullToRefresh>
  </div>
)
```

**Imports pattern** (`LoyaltySheet.jsx` lines 13-21):
```jsx
import React from 'react'
import { Icon } from '@/components/Icon.jsx'
import { StatusBar } from '@/components/StatusBar.jsx'
import { PullToRefresh } from '@/components/PullToRefresh.jsx'
import { SubSheetHeader } from '@/screens/sheets/ProfileExtraSheets.jsx'
import { useClientLoyaltyBalance, useClientLoyaltyHistory } from '@/data'
```

**For GymInfoSheet imports:**
```jsx
import React from 'react'
import { Icon } from '@/components/Icon.jsx'
import { StatusBar } from '@/components/StatusBar.jsx'
import { PullToRefresh } from '@/components/PullToRefresh.jsx'
import { SubSheetHeader } from '@/screens/sheets/ProfileExtraSheets.jsx'
import { useClientGymInfo } from '@/data'
```

**Loading state pattern** (`LoyaltySheet.jsx` lines 215-219):
```jsx
{balanceQuery.isLoading ? (
  <div className="sk sk-line" style={{ width: '35%', marginTop: 8 }} />
) : (
  // content
)}
```

**Error state pattern** (from `LoyaltySheet.jsx` + UI-SPEC.md):
```jsx
// GymInfoSheet uses inline error (UI-SPEC §Error State):
// centered in scroller content area, SubSheetHeader stays visible
{isError && (
  <div style={{ padding: '40px 24px', textAlign: 'center' }}>
    {/* alertCircle icon 40px in danger-soft 64px circle */}
    <div className="t-h3">Не удалось загрузить информацию о зале</div>
    <div className="t-small" style={{ color: 'var(--text-2)', marginTop: 8 }}>
      Потяните вниз, чтобы попробовать снова.
    </div>
  </div>
)}
```

**PullToRefresh with refetch pattern** (`LoyaltySheet.jsx` lines 160-170):
```jsx
const handleRefresh = async () => {
  setPage(1)
  setAllItems([])
  await Promise.all([
    balanceQuery.refetch(),
    queryClient.invalidateQueries({ queryKey: [...clientPortalKeys.all, 'loyalty-history'] }),
  ])
}
// For GymInfoSheet (no pagination, simpler):
const handleRefresh = async () => {
  await gymInfoQuery.refetch()
}
```

**Photos are frontend-only static** — import or inline the `photos` array from the original `gym.js` shape directly in the component (not from the API). Per CONTEXT.md: "décor photos — статика на фронте".

**Open/closed badge derivation** — client-side, per UI-SPEC.md §Hours Section:
```javascript
const now = new Date(new Intl.DateTimeFormat('en', {timeZone: 'Europe/Moscow', ...}).format())
const todayIdx = (now.getDay() + 6) % 7  // Mon=0...Sun=6
const todayRow = data.hours[todayIdx]
```
This logic lives inside the component, not in the backend.

---

## Shared Patterns

### Authentication — client gate
**Source:** `apps/backend/app/modules/loyalty/router.py` lines 43-44
**Apply to:** `gym/router.py` client GET endpoint
```python
client: Annotated[ClientPrincipal, Depends(require_client())],
```

### Authentication — owner gate (reception → 403)
**Source:** `apps/backend/app/modules/trainers/router.py` lines 80-81
**Apply to:** `gym/router.py` owner PUT endpoint
```python
actor: Annotated[CurrentUser, Depends(require_permission(Action.EDIT, Resource.GYM))],
_csrf: Annotated[None, Depends(verify_csrf)],
```
RBAC-04 ordering: `require_permission(...)` declared BEFORE `verify_csrf`. Reception role fails at `require_permission` (403) before reaching `verify_csrf`.

### Response envelope
**Source:** `apps/backend/app/modules/loyalty/router.py` lines 38-54
**Apply to:** both gym router endpoints
```python
from app.core.schemas import ResponseEnvelope, envelope
# ...
return envelope(result)
```

### Error handling — no try/except in router
**Source:** `apps/backend/app/modules/loyalty/router.py` (module docstring line 14) and `client_portal/router.py` (recurring pattern)
**Apply to:** `gym/router.py`
```
No try/except — AppError bubbles to _app_error_handler.
```

### Caller-owns-txn (D-03)
**Source:** `apps/backend/app/modules/trainers/repository.py` lines 9-10
**Apply to:** `gym/repository.py`
```
Transaction control (D-03): NO session.commit() and NO session.flush() here.
Caller (service.py) owns the transactional moment.
```

### camelCase wire (Pydantic v2)
**Source:** `apps/backend/app/core/schemas.py` line 21
**Apply to:** `gym/schemas.py` (via `ResponseData` and `BackendSchemaBase` base classes — inherited automatically)
```python
from pydantic.alias_generators import to_camel
model_config = ConfigDict(alias_generator=to_camel, ...)
```

### Alembic idempotent seed — `ON CONFLICT ... DO NOTHING`
**Source:** `apps/backend/alembic/versions/0051_seed_fit15_promo.py` lines 45-57
**Apply to:** `0059_seed_gym_info.py`
```python
op.execute(
    sa.text(
        "INSERT INTO ... VALUES (...) "
        "ON CONFLICT (id) DO NOTHING"
    )
)
```

### Frontend `.sk .sk-line` skeleton pattern
**Source:** `apps/client-pwa/src/screens/sheets/LoyaltySheet.jsx` lines 215-217
**Apply to:** `GymInfoSheet.jsx` loading state
```jsx
<div className="sk sk-line" style={{ width: '60%', marginTop: 8 }} />
```

### Frontend `SubSheetHeader` + `StatusBar` + `PullToRefresh` composition
**Source:** `apps/client-pwa/src/screens/sheets/LoyaltySheet.jsx` lines 197-207
**Apply to:** `GymInfoSheet.jsx` outer shell — exact copy of this three-component composition.

---

## No Analog Found

All files have close analogs. No entries in this section.

---

## Key Notes for Planner

1. **Two Alembic migrations** (0058 DDL + 0059 seed) because seed references the table, requiring it to exist first. Chain: `0057 → 0058 → 0059`.

2. **Latest migration revision** to chain off: `0057_payment_notifications_widen_kind` (as of 2026-06-06, confirmed from `alembic/versions/` listing).

3. **`Resource.GYM` addition** — must add to both `apps/backend/app/core/permissions.py` (StrEnum + OWNER_ONLY set) AND the frontend parity test checks frontend `can.ts` vs backend OWNER_ONLY. The test at `tests/unit/test_audit_taxonomy.py` (mentioned in `permissions.py` line 6) asserts parity. Planner should note: add `GYM = "gym"` to backend `Resource` StrEnum and `(Action.EDIT, Resource.GYM)` to `OWNER_ONLY`. The frontend `can.ts` OWNER_ONLY array may also need updating (Phase 89 scope — check if parity test would fail).

4. **Two router instances in `gym/router.py`** — follow the Phase 82 pattern (loyalty module): one `APIRouter` for client-facing, one for owner-facing, both registered separately in `v1/router.py` via inline import. Alternatively a single router is acceptable if both paths are in one file and prefixes are set correctly.

5. **JSONB Python type hint** for SQLAlchemy mapped columns: `Mapped[list[Any]]` with `from typing import Any` — see `clients/models.py` line 96 for `dict[str, Any]` pattern, adapt to `list[Any]` for gym JSONB list columns.

6. **GymInfoSheet is a full rewrite** (currently 10 lines of ComingSoon placeholder) — not a modification of existing logic.

7. **`data/gym.js` is NOT deleted** in this phase — CONTEXT.md deferred migrating other `GYM_INFO` references (Home chip, etc.). Only `GymInfoSheet` is wired; `gym.js` stays.

---

## Metadata

**Analog search scope:** `apps/backend/app/modules/`, `apps/backend/alembic/versions/`, `apps/client-pwa/src/`
**Files scanned:** ~35 source files read/grepped
**Pattern extraction date:** 2026-06-06
