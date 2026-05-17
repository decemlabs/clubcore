# Architecture Research

**Domain:** PT-slot booking integration — modular monolith (Sportzal v1.5)
**Researched:** 2026-05-17
**Confidence:** HIGH (all decisions derived directly from reading the live codebase)

This file answers: *how do `app/modules/schedule/` and `app/modules/bookings/` plug into the existing v1.4 modular-monolith without breaking the three import-linter contracts, the `LOCKED_AUDIT_EVENTS` gate, or the SVC001/B-01 AST walkers?*

---

## 1. Module Split Decision: Two Modules, Protocol Callbacks Between Them

**Decision: keep `schedule` and `bookings` as two separate modules.**

The `modules-independent` import-linter contract is the deciding constraint. `bookings.service` needs to check whether a slot is still `available` before creating a booking. If `bookings` imports `schedule` directly to do this, the contract breaks. The validated escape — used five times already in v1.1 through v1.4 — is a Protocol slot in `app/core/dependencies.py` registered from the composition root.

The alternative (fold both into a single `bookings` module) avoids one Protocol slot but merges two distinct business concepts: a trainer publishing availability windows (a catalog concern) and a client reserving one of those windows (a transaction concern). The `pt_packages` / `pt_sessions` split in v1.4 is the direct precedent: those two modules are equally entangled at the DB level yet remain separate because the bounded contexts differ. Follow the same discipline.

**Concrete contract consequence:** `bookings` NEVER imports from `schedule`. The runtime bridge is three new Protocol slots in `app/core/dependencies.py`:

| Slot | Consumer | Provider | Failure mode |
|------|----------|----------|--------------|
| `get_slot_by_id` | `bookings.service` (validate slot before booking) | `schedule.service.resolve_slot_by_id` | silent-None (mirrors `ActiveMembership`) |
| `restore_slot_on_cancel` | `bookings.service` (flip slot `booked→available` on cancel) | `schedule.service.restore_slot_to_available` | defensive-raise (slot stranded = misconfiguration) |
| `complete_booking` | `pt_sessions.service` (mark booking `completed` when PT-session recorded) | `bookings.service.complete_booking` | defensive-raise (mirrors `get_payment_recorder`) |

---

## 2. Tables

### `trainer_availability_slots`

```sql
CREATE TABLE trainer_availability_slots (
  id                  UUID PRIMARY KEY,              -- UUIDPkMixin
  trainer_id          UUID NOT NULL REFERENCES trainers(id) ON DELETE RESTRICT,
  start_time          TIMESTAMPTZ NOT NULL,
  end_time            TIMESTAMPTZ NOT NULL,
  status              VARCHAR(16) NOT NULL DEFAULT 'available',
  recurrence_rule     TEXT NULL,                     -- RRULE string; NULL = one-off
  created_by_user_id  UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at          TIMESTAMPTZ NOT NULL,          -- TimestampMixin
  updated_at          TIMESTAMPTZ NOT NULL,
  deleted_at          TIMESTAMPTZ NULL,              -- SoftDeleteMixin
  CONSTRAINT ck_trainer_availability_slots_status
    CHECK (status IN ('available','booked','cancelled'))
);
CREATE INDEX ix_trainer_availability_slots_trainer_id_start_time
  ON trainer_availability_slots (trainer_id, start_time)
  WHERE deleted_at IS NULL;
CREATE INDEX ix_trainer_availability_slots_available
  ON trainer_availability_slots (start_time)
  WHERE status = 'available' AND deleted_at IS NULL;
```

**Soft-delete rationale:** `bookings.slot_id` is `ON DELETE RESTRICT`. A slot cannot be physically deleted while any booking points to it. Soft-delete lets the UI filter `WHERE deleted_at IS NULL` while preserving the FK anchor for audit reads. Mirrors `membership_plans` discipline.

**Status transitions (declarative constant `SLOT_STATUS_TRANSITIONS`):**
- `available → booked` — set atomically in the same UoW as the booking INSERT
- `available → cancelled` — owner/reception cancels before any booking exists
- `booked → available` — booking cancelled; slot restored for rebooking
- `booked → completed` — terminal; set when associated booking completes

**`recurrence_rule`:** Stores an RRULE string. `schedule.service.publish_slot` expands a recurring rule into individual `trainer_availability_slots` rows up to a configurable horizon (e.g. 60 days). The stored rule is display metadata, not live scheduling logic. This avoids a separate recurrence-expansion service and keeps the query model simple: every API consumer always reads individual slot rows.

---

### `bookings`

```sql
CREATE TABLE bookings (
  id                        UUID PRIMARY KEY,        -- UUIDPkMixin
  slot_id                   UUID NOT NULL REFERENCES trainer_availability_slots(id) ON DELETE RESTRICT,
  client_id                 UUID NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
  pt_package_id             UUID NOT NULL REFERENCES pt_packages(id) ON DELETE RESTRICT,
  status                    VARCHAR(16) NOT NULL DEFAULT 'confirmed',
  cancelled_at              TIMESTAMPTZ NULL,
  cancel_reason             TEXT NULL,
  no_show_at                TIMESTAMPTZ NULL,
  completed_at              TIMESTAMPTZ NULL,
  created_by_user_id        UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at                TIMESTAMPTZ NOT NULL,    -- TimestampMixin
  updated_at                TIMESTAMPTZ NOT NULL,
  -- mandatory snapshot fields (v1.2 discipline: snapshot pricing)
  trainer_name_snapshot     TEXT NOT NULL,
  slot_start_time_snapshot  TIMESTAMPTZ NOT NULL,
  slot_end_time_snapshot    TIMESTAMPTZ NOT NULL,
  CONSTRAINT ck_bookings_status
    CHECK (status IN ('confirmed','cancelled','no_show','completed')),
  CONSTRAINT ck_bookings_cancel_reason_requires_cancelled_at
    CHECK (cancel_reason IS NULL OR cancelled_at IS NOT NULL)
);
-- Race guard: only one confirmed booking per slot
CREATE UNIQUE INDEX uq_bookings_slot_confirmed
  ON bookings (slot_id) WHERE status = 'confirmed';
```

**Partial UNIQUE `(slot_id) WHERE status='confirmed'`** is the DB-level race guard for concurrent booking attempts. Two simultaneous POSTs for the same slot: one wins the INSERT, the other gets `IntegrityError`. The service catches the constraint name `uq_bookings_slot_confirmed` and translates to 409 `slot_already_booked`. This mirrors three prior patterns: `(membership_id) WHERE ended_at IS NULL` (v1.3 freeze), `(client_id) WHERE status='active'` for `pt_packages` (v1.4), and `(refund_of) WHERE refund_of IS NOT NULL` for payments (v1.4).

**Snapshot fields:** captured at booking time from the slot row. `trainer_name_snapshot` ensures historical display integrity if the trainer is later renamed or deactivated. `slot_start/end_time_snapshot` ensures the booking summary remains accurate even if the slot row is soft-deleted. Mirrors `trainer_name_snapshot` in `pt_sessions` (v1.4 B-05).

**No `pt_package` snapshot fields on `bookings`:** the FK to `pt_packages` is sufficient — `pt_packages` already carries its own full snapshot suite from Phase 33. No double-snapshot needed.

---

### `pt_sessions` — ALTER (new `booking_id` column)

```sql
ALTER TABLE pt_sessions
  ADD COLUMN booking_id UUID NULL REFERENCES bookings(id) ON DELETE SET NULL;
```

`ON DELETE SET NULL` rather than RESTRICT: a PT-session recorded as a walk-in (no booking) must still be allowed. `ON DELETE SET NULL` also means that if a booking row is ever cleaned up, historical sessions do not break. This is a non-destructive additive migration.

The `booking_id` field is added to `PtSessionCreateRequest` as `Optional[UUID]`. When non-NULL, `pt_sessions.service.record_pt_session` calls `complete_booking(session, booking_id)` via the Protocol slot after the atomic decrement succeeds, in the same UoW before `await session.commit()`.

---

## 3. Cross-Module Callbacks: Full Protocol Slot Inventory

### Slots that already exist and are reused:

| Slot | Function in `core/dependencies.py` | Used by | Already wired |
|------|-------------------------------------|---------|---------------|
| `get_active_pt_package` | `get_active_pt_package(session, client_id)` | `bookings.service` validates package before booking | Phase 33 — `app/main.py` only (not bot) |
| `resolve_trainer_by_id` | `resolve_trainer_by_id(session, trainer_id)` | `schedule.service` validates trainer on slot publish | Phase 31 — `app/main.py` AND `telegram_bot.py` (double-wired) |

### New slots to add in `app/core/dependencies.py`:

**Slot: `SlotById` / `register_slot_resolver` / `get_slot_by_id`**

```python
class SlotById(Protocol):
    id: UUID
    status: str
    trainer_id: UUID
    start_time: datetime
    end_time: datetime
    trainer_name_snapshot: str   # captured when slot is published

SlotByIdResolver = Callable[[AsyncSession, UUID], Awaitable[SlotById | None]]
```

- Consumer: `bookings.service.create_booking` — checks `slot.status == 'available'`
- Failure mode: silent-None (mirrors `ActiveMembership`). Consumer raises 404 when None.
- Wired from: `app/main.py` composition root AND `telegram_bot.py` (defensive double-wiring per REG-29-03 lesson — the bot's `/book` handler reaches `bookings.service` which calls this slot).

**Slot: `BookingSlotRestorer` / `register_booking_slot_restorer` / `restore_slot_on_cancel`**

```python
BookingSlotRestorer = Callable[[AsyncSession, UUID], Awaitable[None]]
# (session, slot_id) -> None; flips slot status 'booked' → 'available'
```

- Consumer: `bookings.service.cancel_booking` — restores slot after booking cancel
- Failure mode: defensive-raise. A missing restorer when cancelling a booking would permanently strand the slot in `booked` status.
- Wired from: `app/main.py` composition root only (not bot — bot does not cancel bookings in v1.5).

**Slot: `BookingCompleter` / `register_booking_completer` / `complete_booking_by_pt_session`**

```python
BookingCompleter = Callable[[AsyncSession, UUID], Awaitable[None]]
# (session, booking_id) -> None; sets status='completed', completed_at=now()
```

- Consumer: `pt_sessions.service.record_pt_session` — when `booking_id` is provided
- Failure mode: defensive-raise (mirrors `get_payment_recorder`). Recording a PT-session against a non-existent or wrongly-registered completer is a programmer error, not a recoverable state.
- Wired from: `app/main.py` composition root only (not bot — bot does not record PT-sessions).

---

## 4. Composition Root Wiring (`app/main.py`)

Additions follow the established pattern: local imports inside `create_app()` body, after existing Phase 33 pt_packages wiring, before `app.include_router(api)`.

```python
# Phase 38 — schedule module Protocol slots
from app.modules.schedule import service as schedule_service
register_slot_resolver(schedule_service.resolve_slot_by_id)
register_booking_slot_restorer(schedule_service.restore_slot_to_available)

# Phase 39 — bookings module Protocol slot
from app.modules.bookings import service as bookings_service
register_booking_completer(bookings_service.complete_booking)
```

**Order rationale:** `schedule` slots must be registered before `bookings` slot because in tests that override the slot resolver via `create_app()`, the bookings stub may itself call `get_slot_by_id` — so the slot resolver must already be in place when `register_booking_completer` fires.

**Bot worker parity (REG-29-03 discipline):** `app/workers/telegram_bot.py:main()` must also register:

```python
from app.modules.schedule import service as schedule_service
register_slot_resolver(schedule_service.resolve_slot_by_id)
```

The `/book` handler calls `bookings.service` via `HandlerContext.bookings_service`; `bookings.service.create_booking` internally calls `get_slot_by_id` from `core.dependencies`. Without this registration in the bot worker process, every bot `/book` attempt silently returns "slot not found". This is the exact failure mode of REG-29-03 (v1.3): `register_active_membership_resolver` missing in the bot worker made `/checkin` silently fail.

`register_booking_completer` is NOT registered in the bot worker — the bot does not record PT-sessions, so `complete_booking_by_pt_session` is never called in that process. Mirrors the D-32-14 payment-recorder discipline.

**ARQ worker `mark_no_show_bookings`:** add to both `WorkerSettings.functions` and `WorkerSettings.cron_jobs`. The existing `on_startup` cron-resolution invariant assertion (`assert all(c.coroutine.__name__ in function_names for c in cron_jobs)`) will catch any mismatch at worker boot — no separate guard needed.

---

## 5. RBAC Additions

### New `Resource` enum entries:

```python
SCHEDULE_SLOTS = "schedule-slots"   # kebab, mirrors MEMBERSHIP_PLANS / PT_PACKAGES
BOOKINGS = "bookings"
```

Do NOT fold these under `TRAINERS` or `PT_PACKAGES`. Trainers is a catalog; slots and bookings have different access semantics (e.g., reception cannot publish slots but can create bookings).

### `Action` enum: no new values needed

Map to existing:
- Publish slot: `(Action.CREATE, Resource.SCHEDULE_SLOTS)` — owner-only
- View/list slots: `(Action.VIEW, Resource.SCHEDULE_SLOTS)` — both roles (reception needs picker)
- Cancel slot: `(Action.CANCEL, Resource.SCHEDULE_SLOTS)` — owner-only
- Create booking: `(Action.CREATE, Resource.BOOKINGS)` — both roles
- Cancel booking: `(Action.CANCEL, Resource.BOOKINGS)` — both roles, time-window enforced at service layer (reception ≤24h, owner anytime — identical to B-12 PT-sessions pattern; `(CANCEL, BOOKINGS)` is NOT in `OWNER_ONLY`)
- View bookings: `(Action.VIEW, Resource.BOOKINGS)` — both roles

### `OWNER_ONLY` additions:

```python
(Action.CREATE, Resource.SCHEDULE_SLOTS),
(Action.CANCEL, Resource.SCHEDULE_SLOTS),
# (Action.VIEW, Resource.SCHEDULE_SLOTS) is NOT owner-only
# (Action.CANCEL, Resource.BOOKINGS) is NOT owner-only — same as B-12 PT-sessions
```

The `(CANCEL, BOOKINGS)` NOT being in `OWNER_ONLY` mirrors Phase 34 D-34-09a exactly: `(CANCEL, PT_SESSIONS)` was removed from `OWNER_ONLY` because reception has a 24h cancel window. The time gate is enforced in `bookings.service.cancel_booking` via `cancel_window_expired` 403, not via RBAC.

**Three-way parity note:** admin-web is frozen at v1.3. The parity test (`tests/unit/test_rbac_parity.py`) that compares backend `OWNER_ONLY` to `apps/admin-web/src/shared/session/can.ts` must be updated: add a comment documenting that v1.5 RBAC entries have no admin-web mirror (admin-web frozen per 2026-05-15 pivot). The test itself should only assert against the admin-web resources that existed before the freeze. New v1.5 resources (`SCHEDULE_SLOTS`, `BOOKINGS`) are backend-only until v2.0 Frontend Integration.

---

## 6. import-linter Contract Changes

`schedule` and `bookings` are already listed in `.importlinter` under `[importlinter:contract:modules-independent]` (verified in the live `.importlinter` file). No additions are needed mechanically.

Confirm with `uv run lint-imports` after adding module content in Phases 38-39 to verify no accidental direct imports between `schedule` and `bookings`.

No narrative exceptions are needed. The three Protocol slots (`get_slot_by_id`, `restore_slot_on_cancel`, `complete_booking_by_pt_session`) all live in `app.core.dependencies`, which `modules-independent` does not constrain (the contract's `source_modules` is `app.modules.*`, not `app.core`).

---

## 7. OpenAPI Surface

### New URL paths:

```
# Schedule module (trainer_availability_slots)
POST   /api/v1/trainer-slots                        publish slot (owner-only)
GET    /api/v1/trainer-slots                        list slots (both roles; ?trainer_id=, ?from=, ?to=, ?status=)
GET    /api/v1/trainer-slots/{slot_id}              get slot detail (both roles)
POST   /api/v1/trainer-slots/{slot_id}/cancel       cancel slot (owner-only)

# Bookings module
POST   /api/v1/bookings                             create booking (both roles)
GET    /api/v1/bookings                             list bookings (both roles; ?client_id=, ?trainer_id=, ?status=)
GET    /api/v1/bookings/{booking_id}                get booking detail (both roles)
POST   /api/v1/bookings/{booking_id}/cancel         cancel booking (both roles + 24h window)
```

### OpenAPI drift gate (Phase 40):

Same byte-stable regen as Phase 35: `uv run python apps/backend/scripts/export_openapi.py && git diff --exit-code apps/backend/openapi.json`. `packages/api-client/src/schema.d.ts` regenerated. New `AssertNonNever` forward-guard assertions added to `packages/api-client/src/schema.contract.test.ts` for all new paths (v1.4 established 36 guards; v1.5 adds ~8 more for slot + booking paths).

---

## 8. Suggested Phase Decomposition

### Phase 37 — Foundations

**Goal:** extend shared contracts before any module code lands, so all subsequent phases pass CI from their first commit (v1.3 INFRA-15 / v1.4 Phase 30 lesson).

Files modified (no new migrations):
- `app/core/audit.py` — extend `LOCKED_AUDIT_EVENTS` with 5 new `(event, resource_type)` pairs:
  - `("slot_published", "schedule_slot")`
  - `("booking_created", "booking")`
  - `("booking_cancelled", "booking")`
  - `("booking_no_show", "booking")`
  - `("booking_completed", "booking")`
  - Count grows 53 → 58
- `app/core/audit_payloads.py` — add 5 Pydantic schemas: `SlotPublishedPayload`, `BookingCreatedPayload`, `BookingCancelledPayload`, `BookingNoShowPayload`, `BookingCompletedPayload` (all with `model_config = ConfigDict(extra="forbid")`)
- `app/core/permissions.py` — add `Resource.SCHEDULE_SLOTS`, `Resource.BOOKINGS`; extend `OWNER_ONLY` with `(CREATE, SCHEDULE_SLOTS)` + `(CANCEL, SCHEDULE_SLOTS)`
- `app/core/dependencies.py` — add 3 new Protocol types + register/get functions: `SlotById` / `register_slot_resolver` / `get_slot_by_id`, `BookingSlotRestorer` / `register_booking_slot_restorer` / `restore_slot_on_cancel`, `BookingCompleter` / `register_booking_completer` / `complete_booking_by_pt_session`
- `tests/unit/test_audit_taxonomy.py` — bump expected frozenset size from 53 to 58
- `tests/unit/test_rbac_parity.py` — add comment documenting admin-web frozen at v1.3; new resources are backend-only

---

### Phase 38 — Schedule Module

**Goal:** `trainer_availability_slots` table + slot CRUD (publish, list, cancel, get); register `resolve_slot_by_id` and `restore_slot_to_available` into composition root.

Files created:
- `app/modules/schedule/models.py` — `TrainerAvailabilitySlot` ORM (Base + UUIDPkMixin + TimestampMixin + SoftDeleteMixin)
- `app/modules/schedule/schemas.py` — `SlotCreateRequest`, `SlotResponse`, `SlotListQuery` (camelCase via `BackendSchemaBase`)
- `app/modules/schedule/repository.py` — `insert_slot`, `get_slot_by_id`, `list_slots`, `update_slot_status`
- `app/modules/schedule/service.py` — `publish_slot`, `cancel_slot`, `get_slot`, `list_slots`, `resolve_slot_by_id`, `restore_slot_to_available`; `resolve_slot_by_id` is the concrete implementation for the Protocol slot
- `app/modules/schedule/constants.py` — `SLOT_STATUS_TRANSITIONS` declarative map
- `app/modules/schedule/router.py` — 4 endpoints, all with `Depends(require_permission(...))`
- `alembic/versions/0016_trainer_availability_slots.py`

Files modified:
- `app/api/v1/router.py` — add `schedule_router` with prefix `"/trainer-slots"`, tags `["trainer-slots"]`
- `app/main.py` — add `register_slot_resolver` + `register_booking_slot_restorer` calls (Phase 38 carve-out block)
- `app/workers/telegram_bot.py` — add defensive `register_slot_resolver` (REG-29-03 pattern; bot will use it in Phase 40)

Key invariants:
- SVC001 commit-gate must pass: all write paths in `schedule.service` end with `await session.commit()`
- `slot_published` audit event emitted on every successful `publish_slot`
- `resolve_slot_by_id` satisfies the `SlotById` Protocol structurally (no DTO conversion)
- `SLOT_STATUS_TRANSITIONS` is the single source of truth for allowed transitions (mirrors `MEMBERSHIP_STATUS_TRANSITIONS` and `PT_PACKAGE_STATUS_TRANSITIONS`)

---

### Phase 39 — Bookings Module

**Goal:** `bookings` table + book/cancel flow + PT-package linkage + `pt_sessions` ALTER migration; register `complete_booking` into composition root; wire `pt_sessions.service` to call the completer.

Files created:
- `app/modules/bookings/models.py` — `Booking` ORM with partial UNIQUE `(slot_id) WHERE status='confirmed'`
- `app/modules/bookings/schemas.py` — `BookingCreateRequest`, `BookingCancelRequest`, `BookingResponse`, `BookingListQuery`
- `app/modules/bookings/repository.py` — `insert_booking`, `get_booking_by_id`, `list_bookings`, `update_booking_status`
- `app/modules/bookings/service.py` — `create_booking`, `cancel_booking`, `complete_booking`, `get_booking`, `list_bookings`; `complete_booking` is the concrete implementation registered as the Protocol slot
- `app/modules/bookings/constants.py` — `BOOKING_STATUS_TRANSITIONS`, `CANCEL_WINDOW_HOURS_RECEPTION = 24`
- `app/modules/bookings/router.py` — 4 endpoints
- `alembic/versions/0017_bookings.py` — creates `bookings` table
- `alembic/versions/0018_pt_sessions_booking_id.py` — `ALTER TABLE pt_sessions ADD COLUMN booking_id UUID NULL REFERENCES bookings(id) ON DELETE SET NULL`

Files modified:
- `app/api/v1/router.py` — add `bookings_router` with prefix `"/bookings"`, tags `["bookings"]`
- `app/main.py` — add `register_booking_completer(bookings_service.complete_booking)` (Phase 39 carve-out block)
- `app/modules/pt_sessions/schemas.py` — add `booking_id: UUID | None = None` to `PtSessionCreateRequest`
- `app/modules/pt_sessions/service.py` — in `record_pt_session`, after the atomic decrement succeeds: if `payload.booking_id is not None`, call `get_booking_completer()(session, payload.booking_id)` before `await session.commit()`
- `app/modules/pt_sessions/models.py` — add `booking_id: Mapped[UUID | None]` column

Key invariants:
- Atomic slot transition: `bookings.service.create_booking` must INSERT booking AND UPDATE slot to `status='booked'` in a single UoW (single `await session.commit()` at the end) — no two-phase commit
- `get_active_pt_package` Protocol slot consumed: validate `sessions_remaining > 0` before INSERT (no decrement at booking time — decrement remains on PT-session creation)
- Partial UNIQUE race: `IntegrityError` on `uq_bookings_slot_confirmed` → caught by constraint-name discriminator → 409 `slot_already_booked`
- `complete_booking` registered from `app/main.py` only (not bot worker)
- SVC001 commit-gate passes for all `bookings.service` write paths
- `create_booking` emits `("booking_created", "booking")`; `cancel_booking` emits `("booking_cancelled", "booking")`; `complete_booking` emits `("booking_completed", "booking")`

---

### Phase 40 — Telegram `/book` + no-show cron + OpenAPI drift refresh + Milestone Verification

**Goal:** bot integration, automated no-show marking, byte-stable OpenAPI regen, operator sign-off.

Files modified:
- `app/integrations/telegram/handlers.py` — add `book_handler` function; extend `HandlerContext` NamedTuple with `bookings_service: ModuleType` field (mirrors `visits_service: ModuleType` pattern)
- `app/workers/telegram_bot.py` — import `bookings_service`; add `HandlerContext.bookings_service=bookings_service`; register `/book` handler in `build_application` call
- `app/workers/scheduled/mark_no_show_bookings.py` — new ARQ job: `SELECT bookings WHERE status='confirmed' AND slot.end_time < now() - interval '15 minutes'`; UPDATE to `status='no_show'`, emit `("booking_no_show", "booking")` per row; idempotent via the `WHERE status='confirmed'` predicate
- `app/workers/__init__.py` — add `mark_no_show_bookings` to `WorkerSettings.functions` AND `WorkerSettings.cron_jobs` at 06:35 Europe/Moscow (10-min stagger after `expire_pt_packages` at 06:25)
- `apps/backend/openapi.json` — regenerated byte-stably
- `packages/api-client/src/schema.d.ts` — regenerated
- `packages/api-client/src/schema.contract.test.ts` — new `AssertNonNever` forward-guards for all Phase 38-39 paths

Key invariants:
- Bot `/book` handler uses `type(exc).__name__` string-name dispatch for exceptions (integrations ⊥ modules forbids importing exception classes from `app.modules.bookings`)
- No-show cron is idempotent: `WHERE status='confirmed'` is the SQL-level gate; `unique=True` in ARQ is defence-in-depth; mirrors `expire_memberships` pattern
- `on_startup` cron-resolution `assert` catches `mark_no_show_bookings` missing from `functions` at worker boot

---

## Dependency Order Rationale

**Foundations before modules:** audit events and Protocol slot registrations must exist before any callsite lands (v1.3 INFRA-15 / v1.4 Phase 30 lesson — ensures every subsequent phase passes CI from its first commit).

**Schedule before Bookings:** `bookings.service.create_booking` consumes the `get_slot_by_id` Protocol slot; that slot's concrete implementation (`schedule.service.resolve_slot_by_id`) must exist before the bookings service can be tested end-to-end.

**Bookings before Telegram `/book` and no-show cron:** the bot handler and the cron both call into `bookings.service`; the service and its table must exist first.

**OpenAPI drift gate at Phase 40 end:** single atomic regen avoids per-phase drift-gate churn (v1.4 Phase 35 lesson). All new paths land in one regen commit.

---

## Component Boundaries: Integration Points With Existing Architecture

| Existing Component | What Changes in v1.5 |
|--------------------|----------------------|
| `app/core/dependencies.py` | +3 Protocol types, +3 register functions, +3 get/accessor functions |
| `app/core/audit.py` `LOCKED_AUDIT_EVENTS` | +5 `(event, resource_type)` pairs (53 → 58) |
| `app/core/audit_payloads.py` | +5 Pydantic payload schemas; `AUDIT_PAYLOAD_SCHEMAS` registry +5 entries |
| `app/core/permissions.py` | +2 `Resource` enum values; `OWNER_ONLY` +2 entries |
| `app/main.py` | +2 import blocks, +3 `register_*` calls |
| `app/workers/telegram_bot.py` | +1 import, +1 `register_slot_resolver` call, +1 `HandlerContext` field, +1 handler registration |
| `app/workers/__init__.py` | +1 function in `functions`, +1 cron entry |
| `app/modules/pt_sessions/service.py` | `record_pt_session` calls `complete_booking_by_pt_session` when `booking_id` non-NULL |
| `app/modules/pt_sessions/models.py` | +`booking_id` column |
| `app/modules/pt_sessions/schemas.py` | +`booking_id: UUID | None` on `PtSessionCreateRequest` |
| `app/api/v1/router.py` | +2 router includes |

---

## Data Flow: Booking Creation (Happy Path)

```
POST /api/v1/bookings  { slotId, clientId, ptPackageId }
    ↓
bookings.router  →  require_permission(CREATE, BOOKINGS)
    ↓
bookings.service.create_booking(session, actor, payload)
    │
    ├─ 1. get_active_pt_package(session, clientId)       ← core.dependencies Protocol slot
    │      None or sessions_remaining == 0  → 409
    │
    ├─ 2. get_slot_by_id(session, slotId)               ← core.dependencies Protocol slot
    │      None → 404; status != 'available' → 409
    │
    ├─ 3. INSERT booking (status='confirmed',
    │           slot_start_time_snapshot, slot_end_time_snapshot,
    │           trainer_name_snapshot — all from slot row)
    │    + UPDATE trainer_availability_slots SET status='booked' WHERE id=slotId
    │      IntegrityError on uq_bookings_slot_confirmed → 409 slot_already_booked
    │
    ├─ 4. audit.emit("booking_created", "booking", ...)
    │
    └─ 5. await session.commit()   ← single commit owns both writes
    ↓
201 BookingResponse
```

## Data Flow: PT-Session Records a Booking Completion

```
POST /api/v1/pt-sessions  { ptPackageId, trainerId, performedAt, bookingId, ... }
    ↓
pt_sessions.service.record_pt_session(session, actor, payload)
    │
    ├─ ... existing v1.4 flow (validate trainer, validate package, atomic decrement)
    │
    ├─ if payload.booking_id is not None:
    │      completer = get_booking_completer()           ← raises RuntimeError if unregistered
    │      await completer(session, payload.booking_id)  ← bookings.service.complete_booking
    │          UPDATE bookings SET status='completed', completed_at=now()
    │              WHERE id=:id AND status='confirmed'
    │          audit.emit("booking_completed", "booking", ...)
    │          (no separate commit — caller owns txn per D-03)
    │
    └─ await session.commit()   ← single commit owns session + booking + decrement
```

---

## Sources

All findings are HIGH confidence — derived directly from reading live codebase files:

- `apps/backend/app/core/dependencies.py` — Protocol slot pattern (7 existing slots)
- `apps/backend/app/main.py` — composition root wiring order (9 register calls)
- `apps/backend/app/core/audit.py` — `LOCKED_AUDIT_EVENTS` frozenset (53 pairs confirmed)
- `apps/backend/app/core/audit_payloads.py` — `AUDIT_PAYLOAD_SCHEMAS` registry (17 schemas confirmed)
- `apps/backend/app/core/permissions.py` — `OWNER_ONLY` frozenset (25 entries), `Resource`/`Action` enums
- `apps/backend/app/.importlinter` — three contracts; `schedule` and `bookings` already listed in `modules-independent`
- `apps/backend/app/workers/__init__.py` — `WorkerSettings`, cron-resolution invariant assertion
- `apps/backend/app/workers/telegram_bot.py` — `HandlerContext` NamedTuple, REG-29-03 double-wiring
- `apps/backend/app/integrations/telegram/handlers.py` — string-name dispatch pattern, `HandlerContext` usage
- `apps/backend/app/modules/pt_sessions/models.py` — D-34-04a raw SQL cross-module pattern
- `apps/backend/app/modules/pt_sessions/service.py` — `record_pt_session` structure
- `apps/backend/app/modules/pt_packages/models.py` — partial UNIQUE pattern, snapshot field discipline
- `.planning/PROJECT.md` — v1.5 goals, Key Decisions table, architectural constraints
- `.planning/MILESTONES.md` — v1.4 Phase 30–36 foundations + verification patterns
