# Phase 108: Editable Settings — Backend + Wiring - Pattern Map

**Mapped:** 2026-06-14
**Files analyzed:** 14 new/modified files
**Analogs found:** 14 / 14

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/backend/app/modules/settings/models.py` | model | CRUD | `apps/backend/app/modules/gym/models.py` | exact (singleton JSONB) |
| `apps/backend/app/modules/settings/schemas.py` | model | request-response | `apps/backend/app/modules/gym/schemas.py` | exact |
| `apps/backend/app/modules/settings/router.py` | controller | request-response | `apps/backend/app/modules/gym/router.py` | exact |
| `apps/backend/app/modules/settings/service.py` | service | CRUD | `apps/backend/app/modules/gym/service.py` | exact |
| `apps/backend/app/modules/settings/repository.py` | service | CRUD | `apps/backend/app/modules/gym/service.py` (repository layer) | role-match |
| `apps/backend/alembic/versions/0070_settings_tables.py` | migration | CRUD | `apps/backend/alembic/versions/0067_referral_tables.py` | exact |
| `apps/backend/alembic/versions/0071_seed_settings.py` | migration | CRUD | `apps/backend/alembic/versions/0068_seed_referral_config.py` | exact |
| `apps/backend/app/core/audit.py` | config | event-driven | `apps/backend/app/core/audit.py` (extend LOCKED_AUDIT_EVENTS) | self-modify |
| `apps/backend/app/core/permissions.py` | config | request-response | self | self-modify |
| `apps/backend/app/modules/notifications/service.py` | service | event-driven | self (add matrix gate) | self-modify |
| `apps/backend/app/modules/bookings/service.py` | service | CRUD | self (read config table instead of constants) | self-modify |
| `apps/admin-app/src/features/settings/api.ts` | hook | request-response | `apps/admin-app/src/features/schedule/api.ts` | exact |
| `apps/admin-app/src/features/settings/schemas.ts` | model | transform | `apps/admin-app/src/features/schedule/schemas.ts` | exact |
| `apps/admin-app/src/pages/settings/components/SectionsTop.tsx` | component | request-response | `apps/admin-app/src/pages/settings/components/SectionsBottom.tsx` (TeamSection) | exact (lock pattern) |
| `apps/admin-app/src/pages/settings/components/SectionsBottom.tsx` | component | request-response | same file (TeamSection) | exact (lock pattern) |
| `apps/admin-app/src/shared/session/can.ts` | config | request-response | `apps/backend/app/core/permissions.py` | byte-parity mirror |

---

## Pattern Assignments

### `apps/backend/app/modules/settings/models.py` (model, CRUD)

**Analog:** `apps/backend/app/modules/gym/models.py`

**Imports + base pattern** (lines 1-17):
```python
from typing import Any

from sqlalchemy import Boolean, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPkMixin
```

**Singleton model pattern** (lines 20-59):
```python
class GymInfo(Base, UUIDPkMixin, TimestampMixin):
    """Gym facility info singleton (GYM-01).

    One row only — seeded by migration 0059_seed_gym_info with deterministic PK
    00000000-0000-0000-0000-000000000001. The singleton pattern means there is
    no per-row soft-delete; the row is permanent reference data managed by the owner.
    """
    __tablename__ = "gym_info"

    # Scalar text columns
    name: Mapped[str] = mapped_column(Text, nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    # JSONB list columns — server_default '[]'::jsonb ensures a valid empty list
    hours: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
```

**Notes for Phase 108:**
- Three singletons needed: `BookingConfig` (deterministic PK `...0003`), `WorkingHoursConfig` (`...0004`), `NotificationPrefsConfig` (`...0005`). Use the same `UUIDPkMixin + TimestampMixin` base.
- `GymInfo` gains two nullable columns: `latitude: Mapped[float | None]` and `longitude: Mapped[float | None]` — additive migration only.
- `BookingConfig` stores scalar integers/booleans for the CFG-03 fields. Use `Integer`/`Boolean` typed columns (not JSONB) since fields are individually readable by the booking service.
- `WorkingHoursConfig` stores the 7-day schedule + breaks + closures as JSONB arrays (mirrors `GymInfo.hours` pattern — same `server_default='[]'::jsonb`).
- `NotificationPrefsConfig` stores the matrix as a JSONB object (`{}::jsonb` server_default), plus scalar Text `sender_signature`, Text `quiet_hours_start`, Text `quiet_hours_end`.

---

### `apps/backend/app/modules/settings/schemas.py` (model, request-response)

**Analog:** `apps/backend/app/modules/gym/schemas.py`

**Base class imports** (lines 1-13):
```python
from __future__ import annotations

from typing import Any

from pydantic import Field

from app.core.schemas import BackendSchemaBase, ResponseData
```

**Response schema pattern** (lines 29-47):
```python
class GymInfoResponse(ResponseData):
    """GET /client/gym and PUT /gym response payload (GYM-01/GYM-02).

    Wire: camelCase via alias_generator=to_camel on ResponseData base.
    model_validate from ORM (from_attributes=True inherited from ContractModel).
    """
    name: str
    address: str
    hours: list[Any] = Field(default_factory=list)
    amenities: list[Any] = Field(default_factory=list)
```

**Request schema pattern** (lines 49-75):
```python
class GymInfoUpdateRequest(BackendSchemaBase):
    """Owner-only partial upsert request body (GYM-02).

    extra='forbid' (inherited from BackendSchemaBase) rejects unknown keys.
    All fields are optional (partial upsert — exclude_unset semantics in repository).
    """
    name: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=255)
    hours: list[Any] | None = None
```

**Notes for Phase 108:**
- `BookingConfigResponse` / `BookingConfigUpdateRequest` — scalar int/bool fields (schedule_step_minutes, booking_ahead_days, cutoff_minutes, cancel_window_hours, cancel_window_enabled, reschedule_same_day, no_show_penalty_kopecks, no_show_penalty_enabled, group_limit, waitlist_limit, waitlist_auto_transfer, client_self_book, show_trainer_windows).
- `WorkingHoursResponse` / `WorkingHoursUpdateRequest` — `schedule: list[Any]`, `breaks: list[Any]`, `closures: list[Any]`.
- `NotificationPrefsResponse` / `NotificationPrefsUpdateRequest` — `matrix: dict[str, Any]`, `sender_signature: str | None`, `quiet_hours_start: str | None`, `quiet_hours_end: str | None`.
- `GymInfoUpdateRequest` needs two new optional fields: `latitude: float | None = None` and `longitude: float | None = None` (additive change).

---

### `apps/backend/app/modules/settings/router.py` (controller, request-response)

**Analog:** `apps/backend/app/modules/gym/router.py`

**Full router pattern** (lines 1-80):
```python
"""Settings router — owner write endpoints (Phase 108 CFG-02/03/04).

owner_router: PUT /api/v1/settings/hours    — require_permission(EDIT, SETTINGS) + verify_csrf
              PUT /api/v1/settings/booking   — require_permission(EDIT, SETTINGS) + verify_csrf
              PUT /api/v1/settings/notifications — require_permission(EDIT, SETTINGS) + verify_csrf

RBAC-04 ordering: require_permission declared BEFORE verify_csrf so reception fails
at 403 before reaching the CSRF check (mirrors gym/router.py T-86-04).

No try/except — AppError subclasses bubble to _app_error_handler in app/main.py.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission, verify_csrf
from app.core.permissions import Action, Resource
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.settings import service
from app.modules.settings.schemas import (
    BookingConfigResponse, BookingConfigUpdateRequest,
    WorkingHoursResponse, WorkingHoursUpdateRequest,
    NotificationPrefsResponse, NotificationPrefsUpdateRequest,
)

owner_router = APIRouter(tags=["Settings"])


@owner_router.put(
    "/hours",
    response_model=ResponseEnvelope[WorkingHoursResponse],
    operation_id="owner_update_working_hours",
    summary="Update working hours / breaks / closures (owner-only; CFG-02)",
)
async def owner_update_working_hours(
    payload: WorkingHoursUpdateRequest,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.EDIT, Resource.SETTINGS))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[WorkingHoursResponse]:
    result = await service.update_working_hours(session, actor, payload)
    return envelope(result)
```

**Key deviation from gym/router.py:**
- Resource is `Resource.SETTINGS` (new, not `Resource.GYM`).
- Three separate PUT endpoints under `/settings/hours`, `/settings/booking`, `/settings/notifications`.
- Register in `app/main.py` as `app.include_router(settings_router, prefix="/api/v1/settings")`.

---

### `apps/backend/app/modules/settings/service.py` (service, CRUD)

**Analog:** `apps/backend/app/modules/gym/service.py`

**Full service pattern** (lines 1-56):
```python
"""Settings service — orchestration between router and repository (Phase 108 CFG-02/03/04).

Caller-owns-txn: flush + commit live HERE (service layer), not in repository.
No audit emit for singleton upserts of configuration content (mirrors gym/service.py rationale).
EXCEPTION: audit.emit() IS required for CFG-02/03/04 per INFRA-15 LOCKED events.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.dependencies import CurrentUser
from app.core.exceptions import NotFoundError
from app.modules.settings import repository
from app.modules.settings.schemas import (
    BookingConfigResponse, BookingConfigUpdateRequest,
    WorkingHoursResponse, WorkingHoursUpdateRequest,
    NotificationPrefsResponse, NotificationPrefsUpdateRequest,
)


class SettingsNotFoundError(NotFoundError):
    code = "settings_not_found"
    status_code = 404


async def update_booking_config(
    session: AsyncSession,
    actor: CurrentUser,
    data: BookingConfigUpdateRequest,
) -> BookingConfigResponse:
    config = await repository.upsert_booking_config(session, data)
    await audit.emit(
        session,
        event="booking_config_updated",
        resource_type="settings",
        actor_id=actor.user_id,
        payload={...},
    )
    await session.flush()
    await session.commit()
    return BookingConfigResponse.model_validate(config)
```

**Notes:**
- Mirrors `gym/service.py` flush+commit pattern exactly.
- UNLIKE gym service, settings mutations DO emit audit events (INFRA-15 LOCKED per CONTEXT decisions). Pre-register `("gym_card_updated", "gym")`, `("working_hours_updated", "settings")`, `("booking_config_updated", "settings")`, `("notification_prefs_updated", "settings")` in `audit.py:LOCKED_AUDIT_EVENTS` BEFORE writing the service callsites.
- GET endpoints return singleton or raise `SettingsNotFoundError(404)`.

---

### Alembic Migration: `0070_settings_tables.py` (migration, CRUD)

**Analog:** `apps/backend/alembic/versions/0067_referral_tables.py`

**File header + metadata pattern** (lines 1-43):
```python
"""settings_tables: booking_config + working_hours_config + notification_prefs_config singletons.

Phase 108 CFG-02/CFG-03/CFG-04.

Revision ID: 0070_settings_tables
Revises: 0069_referral_crediting_columns
Create Date: 2026-06-14

DDL for three settings singletons:
  booking_config           — scalar int/bool booking rules (CFG-03).
  working_hours_config     — JSONB schedule/breaks/closures (CFG-02).
  notification_prefs_config — JSONB matrix + sender_signature + quiet_hours (CFG-04).

Also adds nullable latitude/longitude columns to gym_info (CFG-01 additive).

Singletons follow the gym_info (0059) pattern: deterministic UUID PKs.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import func, text
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0070_settings_tables"
down_revision: str | None = "0069_referral_crediting_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**Table creation pattern** (from `0067_referral_tables.py` lines 46-60):
```python
def upgrade() -> None:
    # ── booking_config ────────────────────────────────────────────────────────
    op.create_table(
        "booking_config",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("schedule_step_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("booking_ahead_days", sa.Integer(), nullable=False, server_default="14"),
        sa.Column("cutoff_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("cancel_window_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("cancel_window_enabled", sa.Boolean(), nullable=False, server_default="true"),
        # ... additional columns ...
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_booking_config")),
    )

    # ── gym_info additive columns (CFG-01) ────────────────────────────────────
    op.add_column("gym_info", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("gym_info", sa.Column("longitude", sa.Float(), nullable=True))
```

**Notes:**
- JSONB columns for `working_hours_config` and `notification_prefs_config` use `server_default=text("'[]'::jsonb")` or `text("'{}'::jsonb")` — mirror `gym_info` pattern.
- `downgrade()` must drop in reverse FK order (no FKs between these tables, so drop in reverse creation order).

---

### Alembic Migration: `0071_seed_settings.py` (migration, CRUD)

**Analog:** `apps/backend/alembic/versions/0068_seed_referral_config.py`

**Seed migration pattern** (lines 1-69):
```python
"""Seed settings singletons baseline (Phase 108 CFG-02/CFG-03/CFG-04).

Revision ID: 0071_seed_settings
Revises: 0070_settings_tables
Create Date: 2026-06-14

Data-only migration: seeds the three settings singletons + updates gym_info.
Idempotency: INSERT ... ON CONFLICT (id) DO NOTHING on all three rows.
asyncpg driver: explicit CAST(:id AS uuid) required (mirrors 0059/0068 pattern).

Seed values for booking_config source from the existing constants:
  cancel_window_hours = 24  (was CANCEL_WINDOW_HOURS_RECEPTION in bookings/constants.py)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0071_seed_settings"
down_revision: str | None = "0070_settings_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BOOKING_CONFIG_ID = "00000000-0000-0000-0000-000000000003"
_WORKING_HOURS_CONFIG_ID = "00000000-0000-0000-0000-000000000004"
_NOTIFICATION_PREFS_CONFIG_ID = "00000000-0000-0000-0000-000000000005"


def upgrade() -> None:
    # Seed booking_config — values mirror existing bookings/constants.py defaults
    op.execute(
        sa.text(
            "INSERT INTO booking_config "
            "(id, schedule_step_minutes, booking_ahead_days, cutoff_minutes, "
            " cancel_window_hours, cancel_window_enabled, ...) "
            "VALUES (CAST(:id AS uuid), :step, :ahead, :cutoff, :cancel_hours, :cancel_en, ...) "
            "ON CONFLICT (id) DO NOTHING"
        ).bindparams(
            id=_BOOKING_CONFIG_ID,
            step=60,
            ahead=14,
            cutoff=60,
            cancel_hours=24,   # mirrors CANCEL_WINDOW_HOURS_RECEPTION
            cancel_en=True,
            # ...
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM booking_config WHERE id = CAST(:id AS uuid)")
        .bindparams(id=_BOOKING_CONFIG_ID)
    )
    # ... similar for working_hours_config and notification_prefs_config
```

---

### `apps/backend/app/core/audit.py` — LOCKED_AUDIT_EVENTS extension

**Analog:** Self — extend the existing frozenset at the bottom of `LOCKED_AUDIT_EVENTS` (file lines 479-486 pattern).

**Registration pattern** (lines 479-486):
```python
        # v2.6 (Phase 97 lock — INFRA-15; referral bonus accrual. Pre-registered BEFORE
        # the payment.succeeded webhook callsite per INFRA-15 discipline.)
        ("referral_bonus_accrued", "referral"),
```

**New entries to add (Phase 108 — pre-register BEFORE any service callsite):**
```python
        # v2.7 (Phase 108 lock — INFRA-15; settings domain. Pre-registered BEFORE any callsite.)
        # CFG-01: gym card updated (extends existing gym resource).
        ("gym_card_updated", "gym"),
        # CFG-02: working hours / breaks / closures updated.
        ("working_hours_updated", "settings"),
        # CFG-03: booking rules updated.
        ("booking_config_updated", "settings"),
        # CFG-04: notification matrix / prefs updated.
        ("notification_prefs_updated", "settings"),
```

**Rule:** Add to `LOCKED_AUDIT_EVENTS` frozenset in `audit.py` in the SAME plan/commit that writes the first service callsite. NEVER write the `audit.emit()` callsite before the event is in the frozenset (the AST gate at `tests/unit/test_audit_taxonomy.py` enforces this at CI time).

---

### `apps/backend/app/core/permissions.py` — RBAC extension

**Analog:** Self — additive extension at the bottom of `OWNER_ONLY` frozenset (line 146 pattern).

**Current last entry** (line 146):
```python
        # Phase 86 GYM-02 — gym-info owner-only write (T-86-02 mitigation).
        (Action.EDIT, Resource.GYM),
```

**New entries to add (Phase 108):**
```python
        # Phase 108 CFG-02/03/04 — settings write; owner-only, additive.
        # Resource.SETTINGS already exists in Resource enum (value "settings").
        (Action.EDIT, Resource.SETTINGS),
```

**CRITICAL:** The parity test `test_rbac_parity()` asserts `backend OWNER_ONLY == frontend OWNER_ONLY`. Adding `(Action.EDIT, Resource.SETTINGS)` to `permissions.py` MUST be done atomically with adding `{ action: 'edit', resource: 'settings' }` to `can.ts:OWNER_ONLY`. The existing `(Action.VIEW, Resource.SETTINGS)` is already in OWNER_ONLY (line 70) — only the EDIT pair is new.

---

### `apps/backend/app/modules/notifications/service.py` — matrix gate addition

**Analog:** Self — `create_notification()` function (lines 36-72).

**Current pattern** (lines 36-73):
```python
async def create_notification(
    session: AsyncSession,
    *,
    client_id: UUID,
    source_type: str,
    source_id: UUID,
    kind: str,
    title: str,
    body: str,
) -> None:
    """Insert one in-app inbox row co-transactionally (caller-owns-txn).
    ...
    """
    inserted = await repository.insert_notification(
        session,
        client_id=client_id,
        source_type=source_type,
        source_id=source_id,
        kind=kind,
        title=title,
        body=body,
    )
    if not inserted:
        _log.info("notification_dedup_conflict", ...)
```

**Where to slot in the matrix gate:**

Before calling `repository.insert_notification`, add a channel-suppression check:

```python
async def create_notification(
    session: AsyncSession,
    *,
    client_id: UUID,
    source_type: str,
    source_id: UUID,
    kind: str,
    title: str,
    body: str,
    channel: str = "in_app",   # NEW — caller specifies channel
) -> None:
    # NEW: check notification matrix prefs (CFG-04).
    # Always-on kinds bypass the check (payment/autopay-failure + security).
    _ALWAYS_ON_KINDS = frozenset({"autopay_charge_failed", "payment_failed", ...})
    if kind not in _ALWAYS_ON_KINDS:
        prefs = await repository.get_notification_prefs_singleton(session)
        if prefs and not _channel_enabled(prefs.matrix, kind, channel):
            _log.info("notification_suppressed_by_matrix", kind=kind, channel=channel)
            return
    # ... existing repository.insert_notification call ...
```

**Quiet-hours gate:** Check `prefs.quiet_hours_start` / `prefs.quiet_hours_end` (Europe/Moscow TZ) for non-critical `channel != "in_app"` notifications. If within quiet window, return silently (no queue, per decision).

---

### `apps/backend/app/modules/bookings/service.py` — read config instead of constants

**Analog:** Self — the `cancel_booking` and `reschedule_booking` functions that currently reference `CANCEL_WINDOW_HOURS_RECEPTION` and `CANCEL_WINDOW_HOURS_CLIENT` from constants.

**Current usage** (lines 1550-1552):
```python
    if booking.slot.start_time - now_utc < timedelta(hours=CANCEL_WINDOW_HOURS_RECEPTION):
        raise CancelWindowExpiredError("cancel_window_expired")
```

**Replacement pattern:**
```python
    # Phase 108: read from booking_config singleton (seeded default = 24h, mirrors old constant).
    config = await settings_repository.get_booking_config(session)
    cancel_window_hours = config.cancel_window_hours if config else CANCEL_WINDOW_HOURS_RECEPTION
    if booking.slot.start_time - now_utc < timedelta(hours=cancel_window_hours):
        raise CancelWindowExpiredError("cancel_window_expired")
```

**Import-linter discipline:** `bookings.service` cannot import from `app.modules.settings` directly if settings is a separate module. Use a Protocol slot in `app.core.dependencies` (same pattern as `resolve_slot_by_id`) OR keep settings as a sub-resource of gym module. Plan-phase must decide based on module boundary rules.

---

## Frontend Pattern Assignments

### `apps/admin-app/src/features/settings/api.ts` — new hooks (CFG-01/02/03/04)

**Analog:** `apps/admin-app/src/features/schedule/api.ts` lines 99-120 (`usePublishSlot`)

**Query hook pattern** (lines 46-57, `useSessions` in `features/settings/api.ts`):
```typescript
export function useSessions() {
  return useQuery({
    queryKey: settingsKeys.sessions,
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/auth/sessions');
      return SessionsListResponseSchema.parse(raw).data;
    },
    staleTime: 30_000,
  });
}
```

**Mutation hook pattern** (`usePublishSlot`, `features/schedule/api.ts` lines 99-121):
```typescript
export function usePublishSlot() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: PublishSlotInput) => {
      const raw = await staffRequest('post', '/api/v1/trainer-slots', {
        body,
        headers: { 'Idempotency-Key': crypto.randomUUID() },
      });
      return TrainerSlotSchema.parse((raw as { data: unknown }).data);
    },
    onSuccess: () => {
      toast.success('Слот опубликован');
      void qc.invalidateQueries({ queryKey: scheduleKeys.all });
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : undefined;
      toast.error(msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.');
    },
  });
}
```

**New hooks to add to `features/settings/api.ts`:**
```typescript
// Key factory extension
export const settingsKeys = {
  sessions: ['auth', 'sessions'] as const,
  gymInfo: ['settings', 'gym'] as const,
  workingHours: ['settings', 'hours'] as const,
  bookingConfig: ['settings', 'booking'] as const,
  notificationPrefs: ['settings', 'notifications'] as const,
};

// useGymInfo() — GET /api/v1/gym, enabled: can(role,'edit','gym')
// useUpdateGymInfo() — PUT /api/v1/gym, toast.success('Карточка зала обновлена')
// useWorkingHours() — GET /api/v1/settings/hours, enabled: can(role,'edit','settings')
// useUpdateWorkingHours() — PUT /api/v1/settings/hours, toast.success('График работы обновлён')
// useBookingConfig() — GET /api/v1/settings/booking, enabled: can(role,'edit','settings')
// useUpdateBookingConfig() — PUT /api/v1/settings/booking, toast.success('Правила записи обновлены')
// useNotificationPrefs() — GET /api/v1/settings/notifications, enabled: can(role,'edit','settings')
// useUpdateNotificationPrefs() — PUT /api/v1/settings/notifications, toast.success('Настройки уведомлений обновлены')
```

**No `Idempotency-Key` needed** for settings PUT endpoints (they are upserts, not idempotent-key-required operations per schedule slot precedent).

---

### `apps/admin-app/src/features/settings/schemas.ts` — new Zod schemas

**Analog:** `apps/admin-app/src/features/settings/schemas.ts` lines 1-34 (existing `SessionSchema`)

**Current pattern** (lines 1-34):
```typescript
import { z } from 'zod';

export const SessionSchema = z.object({
  familyId: z.string(),
  createdAt: z.string(),
  // ...
});

export const SessionsListResponseSchema = z.object({
  data: z.object({
    items: z.array(SessionSchema),
    total: z.number(),
    // ...
  }),
});

export type SessionData = z.infer<typeof SessionSchema>;
```

**New schemas to add (same file):**
```typescript
// GymInfo — wire to PUT /api/v1/gym response + BranchSection form validation
export const GymInfoSchema = z.object({
  name: z.string(),
  address: z.string(),
  tagline: z.string().nullable(),
  city: z.string().nullable(),
  phone: z.string().nullable(),
  email: z.string().nullable(),
  latitude: z.number().nullable(),
  longitude: z.number().nullable(),
  hours: z.array(z.unknown()),
  amenities: z.array(z.string()),
  rules: z.array(z.string()),
  social: z.array(z.unknown()),
});

export const GymInfoResponseSchema = z.object({ data: GymInfoSchema });

// BranchSection form schema (Zod seam — same schema validates form + request body)
export const GymInfoUpdateSchema = z.object({
  nameShort: z.string().min(1).max(40),
  name: z.string().min(1).max(120),
  address: z.string().min(1),
  latitude: z.number().min(-90).max(90).nullable().optional(),
  longitude: z.number().min(-180).max(180).nullable().optional(),
  phone: z.string().max(20).nullable().optional(),
  email: z.string().email().nullable().optional(),
  // ...
});

// BookingConfig — wire to PUT /api/v1/settings/booking
export const BookingConfigSchema = z.object({
  scheduleStepMinutes: z.number(),
  bookingAheadDays: z.number(),
  cutoffMinutes: z.number(),
  cancelWindowHours: z.number(),
  cancelWindowEnabled: z.boolean(),
  rescheduleSameDay: z.boolean(),
  noShowPenaltyKopecks: z.number(),
  noShowPenaltyEnabled: z.boolean(),
  groupLimit: z.number(),
  waitlistLimit: z.number(),
  waitlistAutoTransfer: z.boolean(),
  clientSelfBook: z.boolean(),
  showTrainerWindows: z.boolean(),
});

// WorkingHoursConfig, NotificationPrefsConfig — similar pattern
```

---

### `apps/admin-app/src/pages/settings/components/SectionsTop.tsx` — wire BranchSection, HoursSection, BookingSection

**Analog:** `SectionsBottom.tsx` — `TeamSection` (lines 696-750)

**Lock card pattern** (lines 717-724):
```typescript
{/* Reception: Lock-EmptyState INSIDE body — zero API calls (T-104-12) */}
{!can(role, 'list', 'users') ? (
  <EmptyState
    icon={Lock}
    title="Недостаточно прав"
    message="Этот раздел доступен только владельцу. Обратитесь к владельцу клуба."
    className="py-12"
  />
) : usersQuery.isPending ? (
  <div className="flex flex-col gap-2 pt-2">
    <Skeleton className="h-[46px] w-full rounded-xl bg-surface-3" />
    ...
  </div>
) : usersQuery.isError ? (
  <div className="py-4 text-[12px] text-fg-muted">
    Не удалось загрузить список сотрудников.{' '}
    <button type="button" onClick={() => void usersQuery.refetch()} className="font-semibold text-fg hover:underline">
      Повторить
    </button>
  </div>
) : (
  /* normal section body */
)}
```

**Mutation + form wiring pattern** (from `SecuritySection`, `SectionsTop.tsx` lines 136-298):
```typescript
export function SecuritySection() {
  const { data: sessionsData, isPending, isError, refetch } = useSessions()
  const revokeSession = useRevokeSession()
  const [revokingId, setRevokingId] = useState<string | null>(null)

  function handleRevoke(familyId: string) {
    setRevokingId(familyId)
    revokeSession.mutate(familyId, {
      onSuccess: () => { toast.success('Сессия завершена') },
      onError: () => { toast.error('Не удалось завершить сессию. Попробуйте ещё раз.') },
      onSettled: () => { setRevokingId(null) },
    })
  }
  // ...
}
```

**Full BranchSection wiring pattern (copy this structure):**
```typescript
export function BranchSection() {
  const session = useSession()
  const role = session.data?.role ?? 'reception'

  // Owner gate — zero API calls for reception (mirrors TeamSection T-104-12)
  const gymQuery = useGymInfo(role)                // enabled: can(role,'edit','gym')
  const updateGymInfo = useUpdateGymInfo()

  const form = useForm<GymInfoUpdateInput>({
    resolver: zodResolver(GymInfoUpdateSchema),
    defaultValues: gymQuery.data ?? {},
  })

  // Reset form when server data arrives (or when Cancel is clicked)
  useEffect(() => {
    if (gymQuery.data) form.reset(gymQuery.data)
  }, [gymQuery.data, form])

  return (
    <SectionCard id={ID_BRANCH} icon={Building2} title="Филиал «Тверская»" ...>
      {!can(role, 'edit', 'gym') ? (
        <EmptyState icon={Lock} title="Недостаточно прав" message="..." className="py-12" />
      ) : gymQuery.isPending ? (
        <>
          <Skeleton className="h-[38px] w-full rounded-[10px] bg-surface-3" />
          <Skeleton className="h-[38px] w-full rounded-[10px] bg-surface-3" />
          <Skeleton className="h-[38px] w-full rounded-[10px] bg-surface-3" />
        </>
      ) : gymQuery.isError ? (
        <div className="text-[12px] text-fg-muted">
          Не удалось загрузить настройки.{' '}
          <button onClick={() => void gymQuery.refetch()} className="font-semibold text-fg hover:underline">Повторить</button>
        </div>
      ) : (
        <form onSubmit={form.handleSubmit((data) => updateGymInfo.mutate(data))}>
          {/* BranchSection stub fields — now controlled by react-hook-form */}
          <SettingRow first label="Название" hint="...">
            <TextField {...form.register('nameShort')} sectionId={ID_BRANCH} />
          </SettingRow>
          {/* ... */}
        </form>
      )}
    </SectionCard>
  )
}
```

**SaveBar integration:**
The existing `SettingsContext.markDirty(id)` is called by shared controls (`controls.tsx`) when `sectionId` is provided. Each section's form `onChange` (via react-hook-form `watch` or `isDirty`) calls `markDirty(ID_BRANCH)`. On SaveBar "Сохранить": `updateGymInfo.mutate(form.getValues())`. On SaveBar "Отменить": `form.reset(gymQuery.data)`.

---

### `apps/admin-app/src/shared/session/can.ts` — RBAC extension (byte-parity)

**Analog:** Self — add after line 78 (last entry, `{ action: 'edit', resource: 'gym' }`).

**Current last entry** (line 78):
```typescript
  // v2.4 (Phase 86 GYM-02 — gym-info owner-only write; mirror permissions.py)
  { action: 'edit', resource: 'gym' },
```

**New entry to add:**
```typescript
  // v2.7 (Phase 108 CFG-02/03/04 — settings write; mirror permissions.py (Action.EDIT, Resource.SETTINGS)).
  // (Action.VIEW, Resource.SETTINGS) already exists at line 17 — only EDIT is new.
  { action: 'edit', resource: 'settings' },
```

**Parity rule:** This MUST match the new `(Action.EDIT, Resource.SETTINGS)` entry added to `permissions.py:OWNER_ONLY`. The parity test in `tests/unit/test_permissions.py` enforces set equality — if either side is missing, CI fails.

---

## Shared Patterns

### Authentication + CSRF Guard
**Source:** `apps/backend/app/modules/gym/router.py` lines 65-70
**Apply to:** All three new `owner_router` endpoints in `settings/router.py`
```python
actor: Annotated[CurrentUser, Depends(require_permission(Action.EDIT, Resource.SETTINGS))],
_csrf: Annotated[None, Depends(verify_csrf)],
```
**RBAC-04 rule:** `require_permission` MUST be declared before `verify_csrf` in the function signature so reception fails at 403 before reaching the CSRF check.

### Singleton Upsert (caller-owns-txn)
**Source:** `apps/backend/app/modules/gym/service.py` lines 43-56
**Apply to:** All settings service mutating functions
```python
gym = await repository.upsert_singleton(session, data)
await session.flush()
await session.commit()
return GymInfoResponse.model_validate(gym)
```

### Seed Migration (asyncpg CAST pattern)
**Source:** `apps/backend/alembic/versions/0068_seed_referral_config.py` lines 47-61
**Apply to:** `0071_seed_settings.py`
```python
op.execute(
    sa.text(
        "INSERT INTO booking_config (id, ...) VALUES (CAST(:id AS uuid), ...) "
        "ON CONFLICT (id) DO NOTHING"
    ).bindparams(id=_BOOKING_CONFIG_ID, ...)
)
```
asyncpg sends all bind params as VARCHAR — `CAST(:id AS uuid)` is required for UUID columns.

### Frontend Lock Card (owner-gate)
**Source:** `apps/admin-app/src/pages/settings/components/SectionsBottom.tsx` lines 718-724
**Apply to:** All four stub sections (BranchSection uses `can(role,'edit','gym')`; HoursSection/BookingSection/NotificationsSection use `can(role,'edit','settings')`)
```typescript
{!can(role, 'edit', 'settings') ? (
  <EmptyState
    icon={Lock}
    title="Недостаточно прав"
    message="Этот раздел доступен только владельцу. Обратитесь к владельцу клуба."
    className="py-12"
  />
) : /* query pending / error / success */ null}
```

### Frontend Error + Retry
**Source:** `apps/admin-app/src/pages/settings/components/SectionsTop.tsx` lines 224-235 (SecuritySection)
**Apply to:** All four sections' isError branch
```typescript
<div className="py-4 text-[12px] text-fg-muted">
  Не удалось загрузить настройки.{' '}
  <button type="button" onClick={() => void refetch()} className="font-semibold text-fg hover:underline">
    Повторить
  </button>
</div>
```

### Frontend Mutation Toast
**Source:** `apps/admin-app/src/features/schedule/api.ts` lines 110-120
**Apply to:** All `useUpdate*` mutation hooks
```typescript
onSuccess: () => {
  toast.success('График работы обновлён');
  void qc.invalidateQueries({ queryKey: settingsKeys.workingHours });
},
onError: (err) => {
  const msg = err instanceof ApiError ? err.message : undefined;
  toast.error(msg ?? 'Не удалось сохранить изменения. Попробуйте ещё раз.');
},
```

### Zod Schema (wire-seam)
**Source:** `apps/admin-app/src/features/settings/schemas.ts` lines 15-34
**Apply to:** All four new schemas in `schemas.ts`
```typescript
export const SessionSchema = z.object({ familyId: z.string(), ... });
export const SessionsListResponseSchema = z.object({ data: z.object({ items: z.array(SessionSchema), ... }) });
export type SessionData = z.infer<typeof SessionSchema>;
```
Pattern: define wire shape schema → wrap in `ResponseSchema = z.object({ data: WireSchema })` → export inferred type.

---

## No Analog Found

All files have strong analogs. No gaps.

---

## Metadata

**Analog search scope:** `apps/backend/app/modules/gym/`, `apps/backend/app/modules/bookings/`, `apps/backend/app/modules/notifications/`, `apps/backend/app/core/`, `apps/backend/alembic/versions/`, `apps/admin-app/src/features/settings/`, `apps/admin-app/src/features/schedule/`, `apps/admin-app/src/pages/settings/components/`, `apps/admin-app/src/shared/session/`
**Files scanned:** ~20
**Pattern extraction date:** 2026-06-14
