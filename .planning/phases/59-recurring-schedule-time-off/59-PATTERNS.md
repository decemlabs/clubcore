# Phase 59: Recurring Schedule + Time-Off - Pattern Map

**Mapped:** 2026-05-25
**Files analyzed:** 14 (new + modified)
**Analogs found:** 14 / 14 (every file has a strong in-repo analog — this phase EXTENDS `schedule/`, so the closest analog is almost always a sibling in the same module)

> All file paths are under `apps/backend/`. This phase adds NO new module
> (D-59-01); every new symbol lands inside `app/modules/schedule/` or
> alongside existing infra (`core/`, `workers/`, `alembic/`). Line numbers
> below are from the snapshot read on 2026-05-25; re-confirm before editing.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `alembic/versions/0042_*.py` (recurring + time-off tables + slot ALTER) | migration | DDL | `alembic/versions/0041_payroll_foundations.py` | exact |
| `app/modules/schedule/models.py` (+`RecurringSlotTemplate`, +`TrainerTimeOff`, ALTER `created_by_user_id`) | model | n/a | `schedule/models.py` `TrainerAvailabilitySlot` (same file) | exact |
| `app/modules/schedule/constants.py` (recurring/time-off constants) | config | n/a | `schedule/constants.py` `SLOT_STATUS_TRANSITIONS` (same file) | exact |
| `app/modules/schedule/schemas.py` (+recurring/time-off DTOs) | schema | request-response | `schedule/schemas.py` (same file, `MOSCOW_TZ` + `Field(default_factory)`) | exact |
| `app/modules/schedule/repository.py` (+recurring/time-off queries, bulk INSERT) | repository | CRUD + batch | `schedule/repository.py` (same file) | exact |
| `app/modules/schedule/service.py` (+`create_time_off`, +`generate_recurring_slots` helper, +pattern CRUD) | service | CRUD + event-driven + transform | `schedule/service.py` `cancel_slot` (same file, L390-592) | exact |
| `app/modules/schedule/router.py` (+recurring/time-off endpoints) | router | request-response | `schedule/router.py` (same file) | exact |
| `app/workers/scheduled/generate_recurring_slots.py` (NEW cron) | worker | batch / scheduled | `app/workers/scheduled/expire_pt_packages.py` | exact |
| `app/workers/__init__.py` (`functions` + `cron_jobs` + eager-import) | config | n/a | same file (L106-258) | exact |
| `app/core/config.py` (+`recurring_slot_horizon_days`) | config | n/a | `config.py` `gym_hours_start` field (same file) | exact |
| `app/core/audit.py` (+4 `LOCKED_AUDIT_EVENTS`) | config | n/a | `audit.py` Phase 58 payroll block (L395-403) | exact |
| `app/core/audit_payloads.py` (optional new payload schemas) | schema | n/a | `audit_payloads.py` `TrainerCreatedPayload` (L44-77) | exact |
| `tests/integration/schedule/test_*` + `conftest.py` factories | test | n/a | `tests/integration/schedule/{conftest.py,test_slot_cancel_cascade.py}` | exact |
| `tests/unit/workers/test_worker_settings.py` (count bumps) | test | n/a | same file (L70, L122) | exact |

**No file lacks an analog.** "No Analog Found" section below is empty by design.

---

## Pattern Assignments

### `app/workers/scheduled/generate_recurring_slots.py` (worker, batch/scheduled) — NEW

**Analog:** `app/workers/scheduled/expire_pt_packages.py` (read in full, 74 lines) +
service helper `app/modules/pt_packages/service.py:856` `_expire_due_pt_packages`.

**Single-module-import worker rule (D-59-03):** the cron file MAY import
`app.modules.schedule.service` ONLY (Phase 7 D-06 / Phase 18 D-09). NO cross-module
imports. See `app/workers/scheduled/__init__.py` docstring.

**Caller-owns-txn worker body** (copy `expire_pt_packages.py:42-73` verbatim shape):
```python
from app.modules.schedule import service as schedule_service

_log = structlog.get_logger("workers.scheduled.generate_recurring_slots")

async def generate_recurring_slots(ctx: dict[str, Any]) -> int:
    session_factory = ctx["sessionmaker"]
    async with session_factory() as session:
        count = await schedule_service._generate_recurring_slots(session)
        await session.commit()
    # Summary log AFTER commit (Phase 18 CD-03). NOT an audit event.
    _log.info("generate_recurring_slots_complete", count=count)
    return count
```
- Return type `int` (count of newly materialized rows). ARQ writes it to its result store.
- The service helper is the txn-NON-owner; the cron owns the single `session.commit()`.
- The `<job_name>_complete count=N` structlog line is the LOCKED summary-event shape
  for all scheduled jobs (D-59-09 — cron emits NO per-slot audit event).

**Service helper signature** (mirror `pt_packages/service.py:856-911`):
```python
async def _generate_recurring_slots(  # noqa: SVC001 caller-owns-txn
    session: AsyncSession,
    now: datetime | None = None,   # tests pass a fixed UTC instant for determinism
) -> int:
    # default now() → datetime.now(UTC); horizon from get_settings().recurring_slot_horizon_days
    # bulk INSERT ... ON CONFLICT (trainer_id, start_time) DO NOTHING (no commit)
```
Note the `today: date | None = None` test-override precedent at `pt_packages/service.py:858` —
mirror with a `now`/`as_of` param so the DST golden test can pin the instant.

---

### `app/workers/__init__.py` (config) — MODIFIED

**Analog:** same file. Three edits, each with a precedent line:

1. **Import the cron** alongside the existing scheduled imports (L106-113):
   ```python
   from app.workers.scheduled.generate_recurring_slots import generate_recurring_slots
   ```
2. **Add to `functions` list** (L129-152) — append `generate_recurring_slots`.
3. **Add a `cron(...)` entry to `cron_jobs`** (L163-258). Copy the `expire_pt_packages`
   entry shape (L181-187):
   ```python
   cron(
       generate_recurring_slots,
       hour=4,          # 07:00 MSK (container TZ=UTC) — D-59 discretion; pick non-colliding minute
       minute=0,
       unique=True,
       keep_result=60,
   ),
   ```
   The existing cron-ordering comment block (L178-257) documents the slot map
   (memberships 03:05 → notifs 03:15 → pt_packages 03:25 → reminders 03:35 →
   no_show 20:10 → cleanup 00:30 → fiscal/refund). Slot `generate_recurring_slots`
   in a free minute and extend the comment.

**Eager ORM import (REG-29-04 / L78-105):** if the worker namespace touches the new
`recurring_slot_templates` / `trainer_time_off` tables (it does, via the cron), add a
`# noqa: F401` eager import of those models so `Base.metadata` registers them at worker
boot. Mirror `from app.modules.online_payments.models import PaymentNotification` (L99-101).

**The cron-name invariant** (`on_startup`, L273-280): `cron_function_names ⊆ function_names`.
Steps 2+3 above keep it green; step 2 without step 3 (or vice-versa) fails LOUD at boot.

---

### `app/modules/schedule/service.py` :: `create_time_off` (service, event-driven) — NEW

**Analog:** `cancel_slot` in the SAME file (L390-592), read in full. This is the EXACT
template for the time-off conflict cascade (D-59-06). Reuse every discipline:

**1. Cross-module raw-SQL UPDATE on `bookings` (D-38-11 — NO `from app.modules.bookings import`):**
copy `cancel_slot` L454-487. The predicate-gated UPDATE with `RETURNING id`, the 0-row →
`InternalConsistencyError`, and the `# noqa: TABLE_REF` marker:
```python
cascade_stmt = sa.text(
    """
    UPDATE bookings
    SET status='cancelled', cancelled_at=now(),
        cancel_reason=:reason, updated_at=now()
    WHERE slot_id=:sid AND status='confirmed'
    RETURNING id
    """,  # noqa: TABLE_REF cross-module SQL per D-34-04a / Phase 38 D-38-11
)
```
For time-off this becomes a multi-row cascade (all bookings overlapping `[block_start, block_end]`
for the trainer) — JOIN/filter on `trainer_availability_slots` where status='booked', then
UPDATE the paired confirmed bookings with `cancel_reason='trainer_time_off'`.

**2. 409-on-booked-without-force:** raise a typed `ConflictError` (snake_case `error_code`,
e.g. `time_off_booked_conflict`) carrying conflicting booking IDs + slot IDs in the body.
`ConflictError` is imported in `router.py:30` (`from app.core.exceptions import ConflictError`).

**3. Active-slot auto-cancel:** reuse the existing `active → cancelled` transition + the
existing `slot_cancelled` audit event (D-59-09 — NO new event for this leg). Pattern at
`cancel_slot` L489-511 (in-place mutate `status/cancelled_at/cancel_reason`, flush, `audit.emit("slot_cancelled", ...)`).

**4. Audit + commit ordering (SVC001):** flush → emit → single `session.commit()`. Emit
`booking_cancelled` per cascaded booking (L516-527 shape; 4-key `BookingCancelledPayload`),
emit the NEW `trainer_time_off_created` AFTER the INSERT, then ONE commit covering all rows + audits.

**5. Client DM cascade (fire-and-forget, AFTER commit):** copy `cancel_slot` L538-591 EXACTLY —
the `importlib.import_module("app.modules.bookings.service")` indirection (NOT a static import;
grimp/import-linter flags static `from app.modules.bookings`), `_load_booking_with_relationships`
eager-load before DM, and `_dispatch_booking_lifecycle_notification(kind="cancelled_by_owner", ...)`.
The DM helper NEVER raises (see `_dispatch_booking_dm` contract, `bookings/service.py:347-399`).
Loop this per cascaded booking.

**Time-off delete** (`trainer_time_off_cancelled`): forward-only — DELETE the block, emit the
event, commit. Does NOT resurrect cancelled slots (next cron tick re-materializes).

---

### `app/modules/schedule/models.py` (model) — MODIFIED (+2 tables, 1 ALTER)

**Analog:** `TrainerAvailabilitySlot` in the SAME file (read in full, 131 lines).

**Composition:** `class X(Base, UUIDPkMixin, TimestampMixin)` — copy L52.
Imports already present at L37-49 (`CheckConstraint`, `ForeignKey`, `Index`, `String`, `Text`,
`text`, `PgUUID`, `Mapped/mapped_column/relationship`, `Base/TimestampMixin/UUIDPkMixin`).

**FK pattern (ON DELETE RESTRICT, literal name):** copy L57-65:
```python
trainer_id: Mapped[UUIDType] = mapped_column(
    PgUUID(as_uuid=True),
    ForeignKey("trainers.id", ondelete="RESTRICT",
               name="fk_<table>_trainer_id_trainers"),
    nullable=False,
)
```

**`__table_args__` (CHECK + Index)** copy L106-130. CHECK constraint NAME is the literal
tail (e.g. `name="end_after_start"`, `name="status"`) so the alembic check diff is empty.
Partial index uses `postgresql_where=text("...")`.

**ALTER for cron idempotency (D-59-05):** `created_by_user_id` currently NOT NULL (L79-87) —
make it `nullable=True` (cron-generated slots have no human author). Add
`UNIQUE (trainer_id, start_time)`. Verify no NOT-NULL-dependent query exists (CONTEXT specific).

**String-keyed cross-module relationship** (if a `trainer` rel is wanted on the new tables):
copy L94-104 — `relationship("Trainer", foreign_keys=[trainer_id], lazy="select", viewonly=True)`
(NO `from app.modules.trainers` import; SA resolves via shared `Base.registry`).

---

### `alembic/versions/0042_*.py` (migration, DDL) — NEW

**Analog:** `alembic/versions/0041_payroll_foundations.py` (read in full, 261 lines). Head is `0041`.

- **Revision header** (L27-30): `revision = "0042_..."`, `down_revision = "0041_payroll_foundations"`.
- **`op.create_table`** with `op.f("fk_...")` named FKs, `ondelete="RESTRICT"` (L38-89).
- **PK pattern** (L40-46): `postgresql.UUID(as_uuid=True)`, `server_default=sa.text("gen_random_uuid()")`.
- **CHECK constraints** via `sa.CheckConstraint("...", name=op.f("ck_..."))` (L79-88, L204-213).
  REC-01 needs `day_of_week BETWEEN 0 AND 6` and `end_time > start_time`.
- **UNIQUE indexes** via `op.create_index(..., unique=True, postgresql_where=text(...))` (L219-225).
  REC-01 verbatim: `UNIQUE (trainer_id, day_of_week, start_time, valid_from)`.
  Cron idempotency: `UNIQUE (trainer_id, start_time)` on `trainer_availability_slots` ALTER.
- **ALTER column to nullable:** `op.alter_column("trainer_availability_slots", "created_by_user_id", nullable=True)`.
- **`downgrade()`** drops indexes before tables, FK-safe reverse order (L240-260).
- **Planner discretion (D-59):** 1 combined revision OR split `0042`/`0043`/`0044`.
  Single combined is the precedent (0041 ships two tables atomically — see its docstring L7-8).

---

### `app/modules/schedule/schemas.py` (schema, request-response) — MODIFIED

**Analog:** same file (head read, L1-45). Inputs inherit `BackendSchemaBase`
(camelCase wire ↔ snake_case Python, `extra='forbid'`); responses inherit `ResponseData`.
`MOSCOW_TZ = ZoneInfo("Europe/Moscow")` already defined (L28). Per-request defaults use
`Field(default_factory=...)` (L7 docstring) — never module-import-time `now()`.
`StrEnum` for status values byte-stable with the migration CHECK (L40-46 `SlotStatus`).

---

### `app/modules/schedule/repository.py` (repository, CRUD+batch) — MODIFIED

**Analog:** same file (head read, L1-80). The ONLY module importing the schedule ORM
models. `from __future__ import annotations` required (L27 — PaginatedData generic).
NO `commit`/`flush` here (L14-17 — caller owns txn). Pagination via `PaginatedData`.
List default-window helpers (`resolve_default_from_time`) imported from schemas (L40-44).
New recurring/time-off list queries + the cron's bulk `INSERT ... ON CONFLICT DO NOTHING`
(with `AND NOT EXISTS` time-off-overlap predicate, D-59-05/PITFALL 9) land here as
module-level async helpers.

---

### `app/modules/schedule/router.py` (router, request-response) — MODIFIED

**Analog:** same file (read in full, 253 lines). `schedule_router = APIRouter()` (L51).

**RBAC (D-59-07/08 — NO new pairs):**
- LIST/VIEW endpoints (REC-04, both roles): `Depends(require_permission(Action.LIST, Resource.SCHEDULE_SLOTS))`
  / `(Action.VIEW, ...)` — copy L141-144 / L165-168. NOT in `OWNER_ONLY`.
- WRITE endpoints (pattern create/deactivate, time-off create/delete, force-cascade):
  `(Action.CREATE|EDIT|DELETE|CANCEL, Resource.SCHEDULE_SLOTS)` — all in `OWNER_ONLY`
  (`permissions.py:114-117`). Copy the owner-gate at L67-70.

**RBAC-04 ordering (enforced statically by `test_route_introspection.py`):**
`Depends(require_permission(...))` BEFORE `Depends(verify_csrf)` on every mutation (L67-72).

**Idempotency** on mutations: the two-phase Redis claim + replay block (L90-131). Time-off
create/delete are mutations → require `Idempotency-Key` per the same pattern.

**Response envelope:** `ResponseEnvelope[T]` / `envelope(...)`; list returns
`ResponseEnvelope[PaginatedData[T]]` (L134-155).

---

### `app/core/config.py` (config) — MODIFIED

**Analog:** same file, `gym_hours_start: time = time(7, 0)` (L100-103) — the Phase 19
env-field-with-default precedent. Add:
```python
# Phase 59 D-59-04 (REC-02): rolling materialization horizon for the recurring-slot cron.
recurring_slot_horizon_days: int = 56
```
No prefix; raw env var name `RECURRING_SLOT_HORIZON_DAYS` (model_config `extra="ignore"`, L51-55).
Read via `get_settings().recurring_slot_horizon_days` inside the cron service helper.

---

### `app/core/audit.py` (config) — MODIFIED (+4 events)

**Analog:** the Phase 58 payroll block at L395-403 (most recent precedent for INFRA-15
pre-registration). Append to `LOCKED_AUDIT_EVENTS` frozenset (D-59-09), BEFORE any callsite:
```python
# v1.9 (Phase 59 lock — INFRA-15; emitted in Phase 59 service body)
# Recurring-schedule + time-off lifecycle (REC-01..04):
("recurring_slot_template_created", "schedule_slot"),
("recurring_slot_template_cancelled", "schedule_slot"),
("trainer_time_off_created", "trainer"),
("trainer_time_off_cancelled", "trainer"),
```
The AST gate (`tests/unit/test_audit_taxonomy.py`) requires LITERAL event names + resource_type
at every `audit.emit(...)` callsite (see `emit()` L524-529 hard-fail). NO new event for the
active-slot-cancel leg (reuses `slot_cancelled`) or the force-cascade leg (reuses `booking_cancelled`).

---

### `app/core/audit_payloads.py` (schema) — MODIFIED (optional)

**Analog:** `TrainerCreatedPayload` (L44-77). Each schema is plain `pydantic.BaseModel` with
`model_config = ConfigDict(extra="forbid")` — NOT `BackendSchemaBase` (L14-20). Snake_case
fields, UUID/datetime types. Adding `AUDIT_PAYLOAD_SCHEMAS` entries for the 4 new events is
OPTIONAL (v1.4+ events register; pre-v1.4 stay free-form) — planner decides whether to lock
the payload shapes. If added, register in the `AUDIT_PAYLOAD_SCHEMAS` dict keyed by `(event, resource_type)`.

---

### Tests (test) — NEW/MODIFIED

**Analogs:** `tests/integration/schedule/conftest.py` + `test_slot_cancel_cascade.py` (both read).

- **Fixtures/factories** (`schedule/conftest.py`): `make_trainer` factory, `seeded_owner`/`seeded_reception`,
  `_seed_user` + `_login`, `redis_clean` (flush between tests). New recurring-template + time-off
  factories land here. SAVEPOINT isolation comes from the root `tests/conftest.py` `db_session` (L57).
- **Cascade/audit assertions** (`test_slot_cancel_cascade.py`): imports
  `from app.modules.schedule import service as schedule_service`, asserts on `AuditLog` rows
  (`from app.core.audit_models import AuditLog`), raw `text()` for cross-module booking checks.
  The 409/`?force=true`/DM cascade tests mirror this file's structure.
- **DST golden test (PITFALL 7, ACCEPTANCE criterion):**
  `expand(MONDAY, 10:00, from=2026-03-30) == 2026-03-30 07:00:00+00:00` — expand via
  `ZoneInfo("Europe/Moscow")` then `.astimezone(timezone.utc)`; NEVER naive `timedelta`.
- **Idempotency test (PITFALL 8):** run the cron helper twice, assert second run inserts 0 rows
  (`ON CONFLICT (trainer_id, start_time) DO NOTHING`).
- **Worker count bumps** (`tests/unit/workers/test_worker_settings.py`): registering the new cron
  bumps `len(WorkerSettings.cron_jobs)` (currently asserts `== 8`, L70) and
  `len(WorkerSettings.functions)` (currently asserts `== 11`, L122). Both literal counts MUST be
  updated in the same change or the unit test fails. Assert on `.coroutine.__name__` (L72), never `.name`.

---

## Shared Patterns

### SVC001 caller-owns-txn
**Source:** `pt_packages/service.py:856` (`# noqa: SVC001 caller-owns-txn`); enforced by an AST walker.
**Apply to:** the cron service helper `_generate_recurring_slots` (commits in the cron, not the helper).
Note: `create_time_off` is the OPPOSITE — it is a request-handler-driven service that OWNS its commit
(no SVC001 noqa), exactly like `cancel_slot` (`schedule/service.py:531`).

### Cross-module write via raw `sa.text()` (D-38-11)
**Source:** `schedule/service.py:454-487`.
**Apply to:** `create_time_off`'s booked→cancelled booking cascade. Predicate-gated UPDATE,
`RETURNING id`, 0-row → `InternalConsistencyError`, `# noqa: TABLE_REF`. NO `from app.modules.bookings`.

### Function-local `importlib` for the DM cascade
**Source:** `schedule/service.py:550-591`.
**Apply to:** the `?force=true` client-DM fan-out. `importlib.import_module("app.modules.bookings.service")`
(grimp-opaque), eager-load via `_load_booking_with_relationships`, fire-and-forget
`_dispatch_booking_lifecycle_notification` (never raises).

### Audit emit (LITERAL event + resource_type, co-transactional)
**Source:** `core/audit.py:451` `emit()`; callsites at `schedule/service.py:361,500,517`.
**Apply to:** all new emits. Caller never commits inside `emit()`; the row enrolls in the
caller's UoW. Event name + resource_type MUST be string literals (AST gate).

### `<job_name>_complete count=N` ops-summary (NOT an audit event)
**Source:** `expire_pt_packages.py:72`.
**Apply to:** `generate_recurring_slots` — emit `_log.info("generate_recurring_slots_complete", count=N)`
AFTER `session.commit()`. High-volume cron emits NO per-slot audit (D-59-09).

### Europe/Moscow `zoneinfo` expansion (PITFALL 7)
**Source:** `pt_packages/service.py:884` (`datetime.now(ZoneInfo("Europe/Moscow"))`); `schemas.py:28` (`MOSCOW_TZ`).
**Apply to:** the cron's `(day_of_week, start_time_local) → UTC` expansion. Expand in Moscow TZ, then
`.astimezone(timezone.utc)`. Store TIMESTAMPTZ only. Golden test mandatory.

### Single-module-import worker rule
**Source:** `app/workers/scheduled/__init__.py` docstring.
**Apply to:** `generate_recurring_slots.py` — imports `app.modules.schedule.service` ONLY.

### RBAC reuse — no new pairs (D-59-07/08)
**Source:** `permissions.py:103` (reception-retained VIEW/LIST), `permissions.py:114-117` (owner-only writes).
**Apply to:** every new endpoint. `SCHEDULE_SLOTS` resource covers all of REC-01..04. No `can.ts`/`registry.ts` edits.

---

## No Analog Found

(none — every file extends an existing module or mirrors an existing infra pattern.)

---

## Metadata

**Analog search scope:** `apps/backend/app/modules/schedule/`, `apps/backend/app/workers/`,
`apps/backend/app/core/`, `apps/backend/alembic/versions/`, `apps/backend/app/modules/{bookings,pt_packages}/`,
`apps/backend/tests/{integration/schedule,unit/workers}/`.
**Files scanned:** ~18 (12 read in full or in targeted ranges + grep probes).
**Pattern extraction date:** 2026-05-25
