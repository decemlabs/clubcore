# Phase 88: Trainer Detail / Bio - Pattern Map

**Mapped:** 2026-06-06
**Files analyzed:** 9 new/modified files
**Analogs found:** 9 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/backend/app/modules/trainers/models.py` | model | CRUD | self (extend) | exact |
| `apps/backend/app/modules/trainers/schemas.py` | schema/DTO | request-response | self (extend) | exact |
| `apps/backend/alembic/versions/0062_trainer_profile_fields.py` | migration/DDL | batch | `alembic/versions/0048_client_onboarding_fields.py` | exact |
| `apps/backend/alembic/versions/0063_seed_trainer_profiles.py` | migration/data | batch | `alembic/versions/0059_seed_gym_info.py` | exact |
| `apps/backend/app/modules/client_portal/schemas.py` | schema/DTO | request-response | self (extend: `ClientCatalogTrainerResponse`) | exact |
| `apps/backend/app/modules/client_portal/repository.py` | repository | CRUD | self (extend: `fetch_trainers_catalog`) | exact |
| `apps/backend/app/modules/client_portal/service.py` | service | request-response | self (extend: `list_trainers`) | exact |
| `apps/backend/app/modules/client_portal/router.py` | controller | request-response | self (extend: `client_list_trainers` at line 317) | exact |
| `apps/client-pwa/src/lib/clientQueries.ts` | hook | request-response | `useClientPaymentStatus` (line 568) — by-id path param | exact |
| `apps/client-pwa/src/data/index.js` | config/swap-seam | request-response | self (extend: Phase 86/87 export additions) | exact |
| `apps/client-pwa/src/screens/sheets/TrainerDetailSheet.jsx` | component | request-response | `GymInfoSheet.jsx` | exact |
| `apps/client-pwa/eslint.config.js` | config | — | self (D-71-09 zone, lines 61-109) | exact |

---

## Pattern Assignments

### `apps/backend/app/modules/trainers/models.py` (model — extend existing)

**Analog:** self — `apps/backend/app/modules/trainers/models.py` (current state)

**Existing column pattern** (lines 23-43):
```python
class Trainer(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin):
    """Gym trainer / personal training staff (TRN-01)."""

    __tablename__ = "trainers"

    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
```

**Columns to add** (copy nullable Text pattern from `phone` / `full_name`):
```python
bio: Mapped[str | None] = mapped_column(Text, nullable=True)
specialization: Mapped[str | None] = mapped_column(Text, nullable=True)
photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
```
Import `Text` is already present. No new imports needed. Place the three new columns after `is_active` before `__table_args__`.

---

### `apps/backend/app/modules/trainers/schemas.py` (schema/DTO — extend existing)

**Analog:** self — `apps/backend/app/modules/trainers/schemas.py` (current state)

**TrainerUpdateRequest extension** (lines 44-53 — add three nullable fields):
```python
class TrainerUpdateRequest(BackendSchemaBase):
    """PATCH /api/v1/trainers/{id} body.

    PATCH semantics: omit key to leave unchanged (D-01).
    is_active accepted on PATCH for deactivate/reactivate (D-31-11).
    """

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, pattern=PHONE_REGEX)
    is_active: bool | None = None
    # Phase 88 TRNR-02: add these three fields (owner-write)
    bio: str | None = None
    specialization: str | None = None
    photo_url: str | None = None
```

**TrainerResponse extension** (lines 61-70 — add three nullable read fields):
```python
class TrainerResponse(ResponseData):
    """Single trainer read DTO. `from_attributes=True` inherited via ContractModel."""

    id: UUID
    full_name: str
    phone: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # Phase 88 TRNR-01: new profile fields
    bio: str | None = None
    specialization: str | None = None
    photo_url: str | None = None
```

The `extra='forbid'` behaviour is inherited from `BackendSchemaBase` — no change needed. `TrainerCreateRequest` does NOT get bio/spec/photo (owner sets those via PATCH per TRNR-02).

---

### `apps/backend/alembic/versions/0062_trainer_profile_fields.py` (DDL migration — add columns)

**Analog:** `apps/backend/alembic/versions/0048_client_onboarding_fields.py` — exact pattern for `op.add_column` on an existing table with nullable columns. No CHECK constraint needed here (free-text fields).

**Full structure to copy** (lines 1-48):
```python
"""trainers: bio, specialization, photo_url columns (Phase 88 TRNR-01).

Revision ID: 0062_trainer_profile_fields
Revises: 0061_client_push_tokens
Create Date: 2026-06-06

Additive migration — three nullable Text columns.
All nullable, no backfill (separate data migration 0063).
ADD COLUMN is metadata-only on Postgres 16 — negligible lock window.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0062_trainer_profile_fields"
down_revision: str | None = "0061_client_push_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("trainers", sa.Column("bio", sa.Text(), nullable=True))
    op.add_column("trainers", sa.Column("specialization", sa.Text(), nullable=True))
    op.add_column("trainers", sa.Column("photo_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("trainers", "photo_url")
    op.drop_column("trainers", "specialization")
    op.drop_column("trainers", "bio")
```

Key details from `0048`:
- `from __future__ import annotations` + `from collections.abc import Sequence` header
- `sa.Column(..., nullable=True)` — no `server_default` for nullable text
- downgrade drops in reverse order

---

### `apps/backend/alembic/versions/0063_seed_trainer_profiles.py` (data migration — backfill)

**Analog:** `apps/backend/alembic/versions/0059_seed_gym_info.py` — idempotent `UPDATE` pattern with `sa.text().bindparams()`.

**Idempotency strategy:** The trainers seeded in production-like environments come from `scripts/seed_v1_4_verification_fixtures.py` (line 211-221) using deterministic `_uuid5(f"trainer:{full_name}")`. The mock PWA trainers (Аня Соколова / Марк Левин / Лиза Орлова / Денис Кравцов / Соня Бек / Игорь Раш from `apps/client-pwa/src/data/trainers.js`) do NOT have entries in the v1.4 fixture (that script seeds "Trainer Alpha/Beta/Gamma"). The backfill must use `UPDATE ... WHERE full_name = :name` for robustness — idempotent because re-setting the same values is a no-op side-effect-wise, and we use explicit `WHERE bio IS NULL OR bio = :bio` only if needed; simpler approach: `UPDATE trainers SET bio=:bio, specialization=:spec, photo_url=:url WHERE full_name=:name AND deleted_at IS NULL` — safe no-op on subsequent runs since values are identical.

**Pattern from 0059** (lines 75-112 — `sa.text().bindparams` + `op.execute`):
```python
def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO gym_info "
            "(...) VALUES (...) "
            "ON CONFLICT (id) DO NOTHING"
        ).bindparams(...)
    )
```

**Adapted pattern for UPDATE backfill:**
```python
import sqlalchemy as sa
from alembic import op

_TRAINER_PROFILES = [
    # (full_name, specialization, bio)
    ("Аня Соколова",   "Силовые, функционал",        "Аня Соколова — силовые и функциональный тренинг, 7 лет опыта. ..."),
    ("Марк Левин",     "Кроссфит, выносливость",     "Марк Левин — кроссфит и развитие выносливости, 5 лет опыта. ..."),
    ("Лиза Орлова",    "Йога, стретчинг",             "Лиза Орлова — йога и стретчинг, 9 лет опыта. ..."),
    ("Денис Кравцов",  "Бокс, ММА",                  "Денис Кравцов — бокс и смешанные единоборства, 11 лет опыта. ..."),
    ("Соня Бек",       "Пилатес, осанка",             "Соня Бек — пилатес и коррекция осанки, 4 года опыта. ..."),
    ("Игорь Раш",      "Бодибилдинг",                "Игорь Раш — бодибилдинг и набор массы, 8 лет опыта. ..."),
]

def upgrade() -> None:
    for full_name, specialization, bio in _TRAINER_PROFILES:
        op.execute(
            sa.text(
                "UPDATE trainers "
                "SET specialization = :spec, bio = :bio, photo_url = NULL "
                "WHERE full_name = :name AND deleted_at IS NULL"
            ).bindparams(name=full_name, spec=specialization, bio=bio)
        )

def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE trainers SET specialization = NULL, bio = NULL, photo_url = NULL "
            "WHERE deleted_at IS NULL"
        )
    )
```

Also note: `photo_url` is left NULL per CONTEXT.md decision (owner sets later via PATCH). The `down_revision` for this file is `"0062_trainer_profile_fields"`.

---

### `apps/backend/app/modules/client_portal/schemas.py` (extend `ClientCatalogTrainerResponse`)

**Analog:** self — `apps/backend/app/modules/client_portal/schemas.py` lines 114-123

**Existing schema** (lines 114-123):
```python
class ClientCatalogTrainerResponse(ResponseData):
    """Active trainer — client-safe projection (CPLAN-03, D-69-05).

    NO rates, NO phone, NO is_active flag, NO audit fields.
    specialization is not present in the Trainer model (reserved for future).
    """

    id: UUID
    full_name: str
```

**New schema to add** (separate class, not replacing the list schema):
```python
class ClientTrainerDetailResponse(ResponseData):
    """Single trainer detail — client-safe projection (TRNR-01, Phase 88).

    Client-safe fields only: id, full_name, photo_url, specialization, bio.
    NO phone, NO is_active, NO rates, NO audit fields (D-20-IDOR / CPLAN convention).
    """

    id: UUID
    full_name: str
    photo_url: str | None = None
    specialization: str | None = None
    bio: str | None = None
```

Update `ClientCatalogTrainerResponse` docstring to remove the "(reserved for future)" note.

---

### `apps/backend/app/modules/client_portal/repository.py` (extend — add `fetch_trainer_detail`)

**Analog:** self — `apps/backend/app/modules/client_portal/repository.py` `fetch_trainers_catalog` function (lines 504-530)

**Existing pattern** (lines 504-530):
```python
async def fetch_trainers_catalog(
    session: AsyncSession,
) -> list[dict[str, object]]:
    """Active trainers catalog — client-safe fields only (CPLAN-03, D-69-05).

    CROSS-MODULE READ — raw SQL text() only; NO ORM import of Trainer.
    ...
    """
    rows = (
        await session.execute(
            text(
                "SELECT id, full_name "
                "FROM trainers "
                "WHERE is_active = true AND deleted_at IS NULL "
                "ORDER BY full_name ASC"
            ),
        )
    ).mappings().all()
    return [dict(r) for r in rows]
```

**New function to add:**
```python
async def fetch_trainer_detail(
    session: AsyncSession,
    trainer_id: UUID,
) -> dict[str, object] | None:
    """Single trainer detail — client-safe fields only (TRNR-01, Phase 88).

    CROSS-MODULE READ — raw SQL text() only; NO ORM import of Trainer.
    Client-safe projection: id, full_name, photo_url, specialization, bio.
    Filters: is_active = true AND deleted_at IS NULL (404 on unknown/inactive/soft-deleted).
    CAST(:trainer_id AS UUID) — asyncpg sends bind params as VARCHAR (same pattern as
    fetch_available_slots in this file).
    """
    row = (
        await session.execute(
            text(
                "SELECT id, full_name, photo_url, specialization, bio "
                "FROM trainers "
                "WHERE id = CAST(:trainer_id AS UUID) "
                "AND is_active = true AND deleted_at IS NULL"
            ).bindparams(trainer_id=str(trainer_id)),
        )
    ).mappings().one_or_none()
    return dict(row) if row is not None else None
```

Add `"fetch_trainer_detail"` to the `__all__` list at the top of the file (mirrors how `"fetch_trainers_catalog"` is listed at line 45).

---

### `apps/backend/app/modules/client_portal/service.py` (extend — add `get_trainer_detail`)

**Analog:** self — `apps/backend/app/modules/client_portal/service.py` `list_trainers` (lines 408-419) + `get_client_me` 404-collapse pattern (lines 148-158)

**Existing list_trainers pattern** (lines 408-419):
```python
async def list_trainers(
    session: AsyncSession,
) -> list[ClientCatalogTrainerResponse]:
    """Active trainers catalog (CPLAN-03, D-69-05)."""
    rows = await repository.fetch_trainers_catalog(session)
    return [
        ClientCatalogTrainerResponse(
            id=cast(Any, r)["id"],
            full_name=str(cast(Any, r)["full_name"]),
        )
        for r in rows
    ]
```

**Existing 404-collapse pattern** (lines 148-158):
```python
row = await repository.fetch_client_me(session, client_id)
r: dict[str, Any] = row
# None → NotFoundError 404-collapse
```

**New function to add:**
```python
async def get_trainer_detail(
    session: AsyncSession,
    trainer_id: UUID,
) -> ClientTrainerDetailResponse:
    """Single trainer detail for client GET (TRNR-01, Phase 88).

    404-collapse on missing/soft-deleted/inactive trainer (D-20-IDOR).
    No try/except — NotFoundError bubbles to _app_error_handler.
    """
    row = await repository.fetch_trainer_detail(session, trainer_id)
    if row is None:
        raise NotFoundError("trainer_not_found")
    r: dict[str, Any] = cast(Any, row)
    return ClientTrainerDetailResponse(
        id=r["id"],
        full_name=str(r["full_name"]),
        photo_url=r.get("photo_url"),
        specialization=r.get("specialization"),
        bio=r.get("bio"),
    )
```

Import `ClientTrainerDetailResponse` from `.schemas` (alongside existing `ClientCatalogTrainerResponse` import). `NotFoundError` is already imported at line 56.

---

### `apps/backend/app/modules/client_portal/router.py` (extend — add `client_get_trainer`)

**Analog:** self — `apps/backend/app/modules/client_portal/router.py` `client_list_trainers` endpoint (lines 317-332)

**Existing list endpoint** (lines 317-332):
```python
@router.get(
    "/trainers",
    response_model=ResponseEnvelope[list[ClientCatalogTrainerResponse]],
    operation_id="client_list_trainers",
    summary="Active trainers catalog for the authenticated client (CPLAN-03)",
)
async def client_list_trainers(
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[list[ClientCatalogTrainerResponse]]:
    """CPLAN-03 — client-safe trainer catalog (name only; no phone, no is_active, no rates).

    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.list_trainers(session)
    return envelope(result)
```

**New endpoint to add** (immediately after `client_list_trainers`):
```python
@router.get(
    "/trainers/{trainer_id}",
    response_model=ResponseEnvelope[ClientTrainerDetailResponse],
    operation_id="client_get_trainer",
    summary=(
        "Single trainer profile for the authenticated client (TRNR-01); "
        "404 trainer_not_found on unknown / soft-deleted / inactive"
    ),
)
async def client_get_trainer(
    trainer_id: UUID,
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientTrainerDetailResponse]:
    """TRNR-01 — client-safe trainer detail (id, name, photo_url, spec, bio).

    404 trainer_not_found for missing/soft-deleted/inactive trainers (D-20-IDOR).
    No try/except — NotFoundError bubbles to _app_error_handler.
    """
    result = await service.get_trainer_detail(session, trainer_id)
    return envelope(result)
```

Add `from uuid import UUID` (already imported at line 36 via `from uuid import UUID`). Add `ClientTrainerDetailResponse` to the schema import block (alongside existing imports at lines 49-65).

---

### `apps/client-pwa/src/lib/clientQueries.ts` (extend — add `useClientTrainerDetail`)

**Analog:** `useClientPaymentStatus` (lines 568-583) — by-id path param query with `enabled` guard + `clientRequest params`; AND `useClientGymInfo` (lines 812-821) — simple GET with `staleTime: 30_000`.

**Path-param pattern from `useClientPaymentStatus`** (lines 568-583):
```typescript
export function useClientPaymentStatus(paymentId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: clientPortalKeys.paymentStatus(paymentId ?? ''),
    queryFn: async () => {
      const res = await clientRequest(
        'get',
        '/api/v1/client/payments/{payment_id}/status',
        { params: { payment_id: paymentId! } },
      )
      return (res as { data: PaymentStatusData }).data
    },
    enabled: enabled && !!paymentId,
    refetchInterval: (query) => (query.state.data?.status === 'pending' ? 3_000 : false),
    staleTime: 0,
  })
}
```

**Key factory entry to add** to `clientPortalKeys` (line 44 area):
```typescript
trainerDetail: (id: string) => [...clientPortalKeys.all, 'trainer-detail', id] as const,
```

**Interface to add:**
```typescript
interface TrainerDetailData {
  id: string
  fullName: string
  photoUrl: string | null
  specialization: string | null
  bio: string | null
}
```

**New hook to add** (after `useClientTrainers`, before `useClientPtPackages`):
```typescript
/** GET /api/v1/client/trainers/{trainer_id} — single trainer detail (TRNR-04, Phase 88) */
export function useClientTrainerDetail(trainerId: string | null) {
  return useQuery({
    queryKey: clientPortalKeys.trainerDetail(trainerId ?? ''),
    queryFn: async () => {
      const res = await clientRequest(
        'get',
        '/api/v1/client/trainers/{trainer_id}',
        { params: { trainer_id: trainerId! } },
      )
      return (res as { data: TrainerDetailData }).data
    },
    enabled: !!trainerId,
    staleTime: 30_000,
  })
}
```

---

### `apps/client-pwa/src/data/index.js` (extend — export `useClientTrainerDetail`)

**Analog:** self — `apps/client-pwa/src/data/index.js` Phase 86/87 export additions (lines 58-63)

**Existing Phase 86/87 export pattern** (lines 58-63):
```javascript
  // Phase-86 GYM-01: gym info hook
  useClientGymInfo,
  // Phase-87 INBOX-05: notifications hooks
  useClientNotifications,
  useMarkNotificationRead,
  useMarkAllNotificationsRead,
} from '../lib/clientQueries'
```

**Addition to make** (append before the closing `} from '../lib/clientQueries'`):
```javascript
  // Phase-88 TRNR-04: trainer detail hook
  useClientTrainerDetail,
```

---

### `apps/client-pwa/src/screens/sheets/TrainerDetailSheet.jsx` (rewrite placeholder)

**Analog:** `apps/client-pwa/src/screens/sheets/GymInfoSheet.jsx` — full-screen sub-sheet with `StatusBar / SubSheetHeader / PullToRefresh / scroller`, loading skeleton, error state, live data from `@/data` hook.

**Top-level shell pattern** (GymInfoSheet.jsx lines 210-227):
```jsx
export function GymInfoSheet({ onClose }) {
  const gymInfoQuery = useClientGymInfo()

  const handleRefresh = async () => {
    await gymInfoQuery.refetch()
  }

  const data = gymInfoQuery.data

  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 220, background: 'var(--bg)',
      display: 'flex', flexDirection: 'column',
      animation: 'sheet-up 0.32s cubic-bezier(0.32, 0.72, 0.2, 1)',
    }}>
      <StatusBar />
      <SubSheetHeader title="Информация о зале" onClose={onClose} />

      <PullToRefresh scrollPaddingTop={0} onRefresh={handleRefresh}>
        {gymInfoQuery.isLoading && <GymInfoSkeleton />}
        {gymInfoQuery.isError && <GymInfoError />}
        {data && ( ... )}
      </PullToRefresh>
    </div>
  )
}
```

**Imports pattern** (GymInfoSheet.jsx lines 16-21):
```jsx
import React from 'react'
import { Icon } from '@/components/Icon.jsx'
import { StatusBar } from '@/components/StatusBar.jsx'
import { PullToRefresh } from '@/components/PullToRefresh.jsx'
import { SubSheetHeader } from '@/screens/sheets/ProfileExtraSheets.jsx'
import { useClientGymInfo } from '@/data'
```
For TrainerDetailSheet: replace `useClientGymInfo` with `useClientTrainerDetail`; add `Avatar` import.

**Feature flag pattern** (NotificationsSheet.jsx lines 24-27):
```jsx
const NOTIFICATIONS_FEATURE_FLAGS = {
  notificationsInbox: true, // INBOX-05 (Phase 87): wired to GET /client/notifications
}
```
For TrainerDetailSheet:
```jsx
const TRAINER_DETAIL_FEATURE_FLAGS = {
  trainerProfile: true, // TRNR-04 (Phase 88): wired to GET /client/trainers/{id}
}
```

**Avatar component API** (`apps/client-pwa/src/components/Avatar.jsx` lines 1-12):
```jsx
export function Avatar({ initials, color = '#1c1917', bg = '#e7e5e4', size = 44, ring = false }) {
  return (
    <div className="avatar" style={{
      width: size, height: size, fontSize: size * 0.36,
      background: bg, color,
      boxShadow: ring ? `0 0 0 2px var(--bg), 0 0 0 3.5px ${color}` : 'none',
    }}>
      {initials}
    </div>
  );
}
```
Call as `<Avatar initials={initials} bg={trainer.bg} color={trainer.color} size={80} />`.

**Error state pattern** (GymInfoSheet.jsx lines 191-207):
```jsx
function GymInfoError() {
  return (
    <div style={{ padding: '40px 24px', textAlign: 'center' }}>
      <div style={{
        width: 64, height: 64, borderRadius: 999, margin: '0 auto 16px',
        background: 'var(--danger-soft)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Icon name="alertCircle" size={40} color="var(--danger)" />
      </div>
      <div className="t-h3">Не удалось загрузить информацию о зале</div>
      <div className="t-small" style={{ color: 'var(--text-2)', marginTop: 8 }}>
        Потяните вниз, чтобы попробовать снова.
      </div>
    </div>
  )
}
```
For TrainerDetailSheet: use `Icon` `size={32}` in a 56×56 circle per UI-SPEC; copy text from 88-UI-SPEC.md "Не удалось загрузить профиль тренера."

**Section label pattern** (GymInfoSheet.jsx lines 98-110):
```jsx
function SectionLabel({ children }) {
  return (
    <div className="t-mini" style={{
      padding: '16px 16px 8px',
      color: 'var(--text-3)',
      fontWeight: 700,
      letterSpacing: 0.5,
      textTransform: 'uppercase',
    }}>
      {children}
    </div>
  )
}
```

**App.jsx wiring** (existing — no changes needed, lines 327-332):
```jsx
<SheetGate open={!!ui.trainerDetail} variant="detail" keyFor={ui.trainerDetail?.id}>
  <TrainerDetailSheet
    trainer={ui.trainerDetail}        // contains { id, ... } from TRAINERS
    onClose={() => ui.setTrainerDetail(null)}
    onBook={() => { ui.setTrainerDetail(null); handleTab('book'); }}
    onCheckout={(ctx) => { ui.setTrainerDetail(null); ui.setCheckoutCtx(ctx); }}
  />
</SheetGate>
```
TrainerDetailSheet receives `trainer` prop (has `.id`). Use `trainer?.id` as the `trainerId` argument to `useClientTrainerDetail`.

**`getInitials` helper** (referenced in UI-SPEC — copy from BookScreen.jsx or inline):
```js
function getInitials(name) {
  const parts = (name ?? '').split(' ')
  return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase()
}
```

---

### `apps/client-pwa/eslint.config.js` (D-71-09 zone — de-list TrainerDetailSheet)

**Analog:** self — Phase 86 (GymInfoSheet removal) + Phase 87 (NotificationsSheet removal) precedent, reflected in the current comments at lines 21-24.

**Three spots to edit:**

1. **ignores negation** (line 29) — remove `'!src/screens/sheets/TrainerDetailSheet.jsx'`:
```javascript
// Before:
'!src/screens/ChatScreen.jsx',
'!src/screens/sheets/ReferralSheet.jsx',
'!src/screens/sheets/TrainerDetailSheet.jsx',

// After:
'!src/screens/ChatScreen.jsx',
'!src/screens/sheets/ReferralSheet.jsx',
```

2. **files list** (line 71) — remove `'src/screens/sheets/TrainerDetailSheet.jsx'`:
```javascript
// Before:
files: [
  'src/screens/ChatScreen.jsx',
  'src/screens/sheets/ReferralSheet.jsx',
  'src/screens/sheets/TrainerDetailSheet.jsx',
],

// After:
files: [
  'src/screens/ChatScreen.jsx',
  'src/screens/sheets/ReferralSheet.jsx',
],
```

3. **no-restricted-paths target** (line 95) — remove `'./src/screens/sheets/TrainerDetailSheet.jsx'`:
```javascript
// Before:
target: [
  './src/screens/ChatScreen.jsx',
  './src/screens/sheets/ReferralSheet.jsx',
  './src/screens/sheets/TrainerDetailSheet.jsx',
],

// After:
target: [
  './src/screens/ChatScreen.jsx',
  './src/screens/sheets/ReferralSheet.jsx',
],
```

Update the comment at lines 21-24 to add a Phase 88 note:
```javascript
// Phase 87 (INBOX-05): the notifications sheet also graduated — removed from
// the placeholder zone, now ignored like other real .jsx screens.
// Phase 88 (TRNR-04): TrainerDetailSheet graduated — wired to GET /client/trainers/{id}.
```

---

## Shared Patterns

### require_client() guard
**Source:** `apps/backend/app/modules/client_portal/router.py` line 41 (import) + lines 323-324 (usage)
**Apply to:** `client_get_trainer` endpoint
```python
from app.core.dependencies import ClientPrincipal, require_client, verify_client_csrf

client: Annotated[ClientPrincipal, Depends(require_client())],
```

### 404-collapse (NotFoundError)
**Source:** `apps/backend/app/modules/client_portal/service.py` lines 52-56 (imports) + line 155 (pattern comment)
```python
from app.core.exceptions import NotFoundError

# None → NotFoundError 404-collapse
if row is None:
    raise NotFoundError("trainer_not_found")
```
**Apply to:** `get_trainer_detail` in service.py

### ResponseEnvelope + envelope()
**Source:** `apps/backend/app/modules/client_portal/router.py` lines 46-47 (imports)
```python
from app.core.schemas import ResponseEnvelope, envelope
```
**Apply to:** `client_get_trainer` endpoint return.

### Cross-module raw SQL (no ORM import)
**Source:** `apps/backend/app/modules/client_portal/repository.py` lines 509-510
```
CROSS-MODULE READ — raw SQL text() only; NO ORM import of Trainer.
```
**Apply to:** `fetch_trainer_detail` in repository.py — must NOT import `Trainer` model from trainers module.

### CAST(:param AS UUID) for asyncpg
**Source:** `apps/backend/app/modules/client_portal/repository.py` lines 131-135
```python
# Use CAST(:trainer_id AS UUID) to avoid `:name::type` cast syntax which
# asyncpg doesn't recognise
"AND s.trainer_id = CAST(:trainer_id AS UUID) "
```
**Apply to:** `fetch_trainer_detail` WHERE clause.

### @/data swap seam export
**Source:** `apps/client-pwa/src/data/index.js` lines 21-64 (React Query hook exports)
**Apply to:** New `useClientTrainerDetail` export in data/index.js

---

## No Analog Found

No files lack analogs. All patterns have direct matches in the existing codebase.

---

## Metadata

**Analog search scope:** `apps/backend/app/modules/trainers/`, `apps/backend/app/modules/client_portal/`, `apps/backend/alembic/versions/`, `apps/client-pwa/src/`
**Files scanned:** ~20
**Pattern extraction date:** 2026-06-06
