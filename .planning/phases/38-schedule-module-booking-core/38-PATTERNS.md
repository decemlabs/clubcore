# Phase 38: Schedule Module + Booking Core — Pattern Map

**Mapped:** 2026-05-17
**Files analyzed:** 24 (13 new + 11 modified)
**Analogs found:** 24 / 24

All Phase 38 files map cleanly onto v1.4 precedents (`pt_packages` + `pt_sessions`) or Phase 37 stubs already on `master`. No analog gaps. The closest-match grade is **exact** for every file because Phase 37 deliberately built the bedrock as a thin tracing-paper overlay of the v1.4 modules: `BOOKING_STATUS_TRANSITIONS` mirrors `PT_PACKAGE_STATUS_TRANSITIONS`, `register_booking_completer` mirrors `register_payment_recorder`, `0015_pt_sessions.py` is the templating source for `0017_bookings.py`, and so on.

---

## File Classification

### Plan 38-01 — schedule-module

| File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `apps/backend/alembic/versions/0016_trainer_availability_slots.py` | migration | DDL | `apps/backend/alembic/versions/0014_pt_packages.py` | exact |
| `apps/backend/app/modules/schedule/models.py` | model | ORM | `apps/backend/app/modules/pt_packages/models.py` (`PtPackage` class) | exact |
| `apps/backend/app/modules/schedule/repository.py` | repository | CRUD + with_for_update | `apps/backend/app/modules/pt_packages/repository.py` | exact |
| `apps/backend/app/modules/schedule/schemas.py` | schema | request-response | `apps/backend/app/modules/pt_packages/schemas.py` | exact |
| `apps/backend/app/modules/schedule/router.py` | router | request-response | `apps/backend/app/modules/pt_packages/router.py` (`pt_packages_router`) | exact |
| `apps/backend/app/modules/schedule/service.py` (replace stubs + add `publish_slot` / `cancel_slot_only` / `list_slots` / `get_slot`) | service | CRUD (write-side UoW) | `apps/backend/app/modules/pt_packages/service.py:create_pt_package` | exact |
| `apps/backend/app/modules/schedule/constants.py` (APPEND `SLOT_BUFFER_MINUTES = 10`) | constants | data | `apps/backend/app/modules/pt_sessions/constants.py:17-20` | exact |

### Plan 38-02 — booking-core-create

| File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `apps/backend/alembic/versions/0017_bookings.py` | migration | DDL + partial UNIQUE | `apps/backend/alembic/versions/0014_pt_packages.py:115-123` (partial UNIQUE block) | exact |
| `apps/backend/app/modules/bookings/models.py` | model | ORM + partial UNIQUE Index | `apps/backend/app/modules/pt_packages/models.py:163-168` (uq_pt_packages_active_per_client) | exact |
| `apps/backend/app/modules/bookings/repository.py` | repository | CRUD | `apps/backend/app/modules/pt_sessions/repository.py:131-168` (`insert_pt_session`) | exact |
| `apps/backend/app/modules/bookings/schemas.py` | schema | request-response | `apps/backend/app/modules/pt_sessions/schemas.py` | exact |
| `apps/backend/app/modules/bookings/router.py` | router | request-response + Idempotency | `apps/backend/app/modules/pt_sessions/router.py:63-157` (`record_pt_session`) | exact |
| `apps/backend/app/modules/bookings/service.py` (replace stub + add `create_booking`) | service | atomic UoW with IntegrityError race translation | `apps/backend/app/modules/pt_sessions/service.py:166-293` (`record_pt_session`) + `pt_packages/service.py:457-616` (`create_pt_package`) | exact |
| `apps/backend/tests/integration/bookings/test_booking_race.py` (NEW) | test | race | `apps/backend/tests/integration/pt_sessions/test_pt_session_record_race.py` | exact |

### Plan 38-03 — booking-cancel-and-list

| File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `apps/backend/app/modules/bookings/service.py` (add `cancel_booking` + `list_bookings` + `get_booking_by_id`) | service | FSM transition + cross-module slot use | `apps/backend/app/modules/pt_sessions/service.py:301-427` (`cancel_pt_session`) | exact |
| `apps/backend/app/modules/schedule/service.py` (extend `cancel_slot` to cascade booked→cancelled) | service | atomic UoW + cascade | `apps/backend/app/modules/pt_packages/service.py:726-813` (`cancel_pt_package`) | role-match (no precedent for cascade, but FSM-guard + audit pattern identical) |
| `apps/backend/app/modules/bookings/constants.py` (APPEND `CANCEL_WINDOW_HOURS_RECEPTION = 24`) | constants | data | `apps/backend/app/modules/pt_sessions/constants.py:18` | exact |

### Plan 38-04 — pt-package-trainer-and-refund-guard

| File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `apps/backend/alembic/versions/0018_pt_packages_trainer_id.py` | migration | DDL ALTER ADD COLUMN + FK | `apps/backend/alembic/versions/0009_renewal.py` (self-FK ADD COLUMN) | exact |
| `apps/backend/app/modules/pt_packages/models.py` (add `trainer_id` column) | model | ORM | `apps/backend/app/modules/pt_packages/models.py:114-122` (`plan_id` FK mapping) | exact |
| `apps/backend/app/modules/pt_packages/schemas.py` (add optional `trainer_id`) | schema | request-response | `apps/backend/app/modules/pt_packages/schemas.py:149-159` (`PtPackageCreateRequest`) | exact |
| `apps/backend/app/modules/pt_packages/service.py` (extend `create_pt_package` trainer guard + `refund_pt_package` cross-module count) | service | cross-module raw SQL | `apps/backend/app/modules/pt_sessions/repository.py:103-128` (`fetch_pt_package_metadata` raw text() + noqa marker) | exact |
| `apps/backend/tests/integration/pt_packages/test_pt_packages_refund_guard.py` (NEW) | test | refund-guard 409 | `apps/backend/tests/integration/pt_packages/test_pt_package_refund.py` | exact |

### Plan 38-05 — pt-session-booking-completion

| File | Role | Data Flow | Closest Analog | Match |
|---|---|---|---|---|
| `apps/backend/alembic/versions/0019_pt_sessions_booking_id.py` | migration | DDL ALTER ADD COLUMN + FK | `apps/backend/alembic/versions/0009_renewal.py` | exact |
| `apps/backend/app/modules/pt_sessions/models.py` (add `booking_id`) | model | ORM | `apps/backend/app/modules/pt_sessions/models.py:52-78` (existing FK columns) | exact |
| `apps/backend/app/modules/pt_sessions/schemas.py` (add optional `booking_id`) | schema | request-response | `apps/backend/app/modules/pt_sessions/schemas.py:33-50` (`PtSessionCreateRequest`) | exact |
| `apps/backend/app/modules/pt_sessions/service.py` (extend `record_pt_session` with SELECT FOR UPDATE + completer slot) | service | cross-module raw SQL FOR UPDATE + Protocol slot use | `apps/backend/app/modules/pt_packages/service.py:560-572` (`get_payment_recorder()(...)` cross-module slot use) + `pt_sessions/repository.py:103-128` (raw text() read) | exact |
| `apps/backend/tests/integration/pt_sessions/test_pt_sessions_booking_completion.py` (NEW) | test | integration | `apps/backend/tests/integration/pt_sessions/test_pt_session_record.py` | exact |

### Plan 38-06 — svc001-and-importlinter-greens

No new files; verification of existing walkers + parallel DEFER-36-04-A sweep. Pattern: zero-net-LOC `git diff` plus running the existing test/lint suite.

---

## Pattern Assignments

### `0016_trainer_availability_slots.py` (migration, DDL)

**Analog:** `apps/backend/alembic/versions/0014_pt_packages.py`

**Header + revision wiring** (lines 28-38):

```python
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision: str = "0014_pt_packages"
down_revision: str | None = "0013_pt_package_plans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

Phase 38 substitutes `revision = "0016_trainer_availability_slots"` and `down_revision = "0015_pt_sessions"`.

**TIMESTAMPTZ + server_default(now()) + UUID PK** (lines 44-77):

```python
sa.Column(
    "id",
    sa.UUID(),
    server_default=sa.text("gen_random_uuid()"),
    nullable=False,
),
sa.Column(
    "created_at",
    sa.DateTime(timezone=True),
    server_default=sa.text("now()"),
    nullable=False,
),
sa.Column(
    "updated_at",
    sa.DateTime(timezone=True),
    server_default=sa.text("now()"),
    nullable=False,
),
```

`start_time` / `end_time` MUST follow the same `sa.DateTime(timezone=True)` shape per Pitfall 6 + D-38 invariant. No `nullable=True` on either.

**Status CHECK + named FK + named PK** (lines 78-114):

```python
sa.CheckConstraint(
    "status IN ('active', 'exhausted', 'expired', 'cancelled')",
    name=op.f("ck_pt_packages_status"),
),
sa.PrimaryKeyConstraint("id", name=op.f("pk_pt_packages")),
sa.ForeignKeyConstraint(
    ["client_id"],
    ["clients.id"],
    name=op.f("fk_pt_packages_client_id_clients"),
    ondelete="RESTRICT",
),
```

Phase 38 substitutes `status IN ('active', 'booked', 'cancelled')` per D-38-03 (NOT `available`). Add CHECK `end_time > start_time` per Pitfall 6. Trainer FK → `trainers(id)` ON DELETE RESTRICT; `created_by_user_id` FK → `users(id)` ON DELETE RESTRICT.

**Indexes** (lines 124-126) — substitute Phase 38 names per CONTEXT.md §Specifics: `ix_trainer_availability_slots_trainer_start_time` (btree) and partial `ix_trainer_availability_slots_active_start_time` WHERE `status = 'active'`.

**Downgrade** (lines 129-134) — straight reverse-order `op.drop_index` + `op.drop_table`.

---

### `0017_bookings.py` (migration, DDL + partial UNIQUE race guard)

**Analog:** `apps/backend/alembic/versions/0014_pt_packages.py`

**Partial UNIQUE — THE critical pattern for Pitfall 1** (lines 115-123):

```python
# Partial UNIQUE — at most one active PT-package per client (PT-05 / D-33-09).
# Constraint name literal-ref'd by service.py:_is_active_pt_package_conflict.
op.create_index(
    "uq_pt_packages_active_per_client",
    "pt_packages",
    ["client_id"],
    unique=True,
    postgresql_where=text("status = 'active'"),
)
```

Phase 38 mirror:

```python
# Partial UNIQUE — at most one confirmed booking per slot (BOOK-01 / C-02 / Pitfall 1).
# Constraint name literal-ref'd by service.py:_is_slot_confirmed_conflict.
op.create_index(
    "uq_bookings_slot_confirmed",
    "bookings",
    ["slot_id"],
    unique=True,
    postgresql_where=text("status = 'confirmed'"),
)
```

CONTEXT.md §Specifics also lists `ix_bookings_client_status` and `ix_bookings_slot_status` btree composites.

`pt_package_id` is NOT NULL FK to `pt_packages(id)` ON DELETE RESTRICT (D-38-02). `slot_id` is NOT NULL FK to `trainer_availability_slots(id)` ON DELETE RESTRICT. `client_id` is NOT NULL FK to `clients(id)` ON DELETE RESTRICT. NO snapshot columns (D-38-08).

---

### `0018_pt_packages_trainer_id.py` (migration, ALTER ADD COLUMN + FK)

**Analog:** `apps/backend/alembic/versions/0009_renewal.py:44-72`

**Three-step ADD COLUMN → create_foreign_key → create_index** (lines 44-72):

```python
def upgrade() -> None:
    # 1) Add nullable self-FK column. Existing rows have no source — NULL is correct.
    op.add_column(
        "memberships",
        sa.Column(
            "previous_membership_id",
            sa.UUID(),
            nullable=True,
        ),
    )

    # 2) Self-FK to memberships.id. ON DELETE SET NULL — orphans the renewal but
    #    keeps it queryable (audit trail integrity vs cascade-delete chain).
    op.create_foreign_key(
        op.f("fk_memberships_previous_membership_id_memberships"),
        "memberships",
        "memberships",
        ["previous_membership_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 3) Index for forensic lookup `WHERE previous_membership_id = ?`. Non-partial
    #    per D-26-02 step 3 / CONTEXT.md Risks/Watchpoints #2; partial deferred.
    op.create_index(
        op.f("ix_memberships_previous_membership_id"),
        "memberships",
        ["previous_membership_id"],
    )
```

Phase 38 substitutes: column name `trainer_id`, table `pt_packages`, target `trainers(id)`, **`ondelete="RESTRICT"`** (NOT `SET NULL` — trainers are soft-deleted via `is_active`, never hard-deleted, so RESTRICT is the safer floor), constraint name `fk_pt_packages_trainer_id_trainers`, index `ix_pt_packages_trainer_id`. Nullable `True` (existing pt_packages rows have no trainer association).

**Downgrade** (lines 75-86) — reverse order: drop_index → drop_constraint(type_="foreignkey") → drop_column.

---

### `0019_pt_sessions_booking_id.py` (migration, ALTER ADD COLUMN + FK)

**Analog:** Same as 0018. Substitute: column `booking_id`, table `pt_sessions`, target `bookings(id)`, `ondelete="RESTRICT"` (D-38-CONTEXT §Specifics — research drafted `SET NULL` but REQUIREMENTS BOOK-01 / D-38 imply RESTRICT for parity), index `ix_pt_sessions_booking_id`. Nullable `True` (walk-in sessions have no booking).

---

### `app/modules/schedule/models.py` (model, ORM)

**Analog:** `apps/backend/app/modules/pt_packages/models.py` (`PtPackage` class, lines 90-172)

**Class composition + tablename + DB-level invariants comment block** (lines 90-103):

```python
class PtPackage(Base, UUIDPkMixin, TimestampMixin):
    """PT-package instance — client X bought plan Y on date Z (Phase 33 PT-04).

    Snapshot pricing is immutable; status drives lifecycle. NO soft-delete
    column (D-33-03 mirror of Phase 17 D-12) — cancelled / expired / exhausted
    rows keep their FK references and block plan deletion (D-33-08).
    """

    __tablename__ = "pt_packages"
```

Phase 38 substitutes `class TrainerAvailabilitySlot(Base, UUIDPkMixin, TimestampMixin)` — **NO `SoftDeleteMixin`** per D-38-04. `__tablename__ = "trainer_availability_slots"`.

**FK column with named constraint** (lines 105-113):

```python
client_id: Mapped[UUIDType] = mapped_column(
    PgUUID(as_uuid=True),
    ForeignKey(
        "clients.id",
        ondelete="RESTRICT",
        name="fk_pt_packages_client_id_clients",
    ),
    nullable=False,
)
```

Phase 38 `trainer_id` + `created_by_user_id` mirror this verbatim.

**TIMESTAMPTZ datetime column** — copy from `pt_sessions/models.py:79-82`:

```python
performed_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    nullable=False,
)
```

Both `start_time` and `end_time` follow this pattern. Pitfall 6 violation if `DateTime()` is used bare.

**Status column + CHECK + Indexes in __table_args__** (lines 128-172):

```python
status: Mapped[str] = mapped_column(
    String(16),
    server_default=text("'active'"),
    nullable=False,
)
# ...
__table_args__ = (
    # NAMING_CONVENTION expands to ck_pt_packages_status
    CheckConstraint(
        "status IN ('active', 'exhausted', 'expired', 'cancelled')",
        name="status",
    ),
    # ...
    Index(
        "uq_pt_packages_active_per_client",
        "client_id",
        unique=True,
        postgresql_where=text("status = 'active'"),
    ),
    Index("ix_pt_packages_client_id", "client_id"),
    Index("ix_pt_packages_status", "status"),
)
```

Phase 38: status CHECK is `('active', 'booked', 'cancelled')` (D-38-03). No partial UNIQUE on the slots table itself (the partial UNIQUE lives on `bookings`). Two index entries per CONTEXT.md §Specifics.

---

### `app/modules/bookings/models.py` (model, ORM with partial UNIQUE)

**Analog:** `apps/backend/app/modules/pt_packages/models.py:163-168` (the `uq_pt_packages_active_per_client` Index entry — see excerpt above) + `apps/backend/app/modules/pt_sessions/models.py:52-78` (FK columns).

The partial UNIQUE Index entry IS the load-bearing pattern. Constraint name `uq_bookings_slot_confirmed` (D-38-15) must match the migration's `op.create_index` name letter-for-letter — the IntegrityError discriminator (`_is_slot_confirmed_conflict`) literal-refs this string.

`__table_args__` should also include:
- `CheckConstraint("status IN ('confirmed', 'cancelled', 'no_show', 'completed')", name="status")` → expands to `ck_bookings_status`
- `Index("ix_bookings_client_status", "client_id", "status")`
- `Index("ix_bookings_slot_status", "slot_id", "status")`

NO snapshot columns (D-38-08). NO `SoftDeleteMixin`. NO `cancelled_at` / `cancel_reason` columns? — REQUIREMENTS BOOK-01 mandates them; mirror `pt_sessions/models.py:92-96`:

```python
cancelled_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True),
    nullable=True,
)
cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Add `no_show_at`, `completed_at` per BOOK-01.

---

### `app/modules/schedule/repository.py` and `app/modules/bookings/repository.py` (repository, CRUD)

**Analog:** `apps/backend/app/modules/pt_packages/repository.py`

**Module docstring discipline** (lines 1-23) — copy the structure:

```python
"""PT-packages repository — single point of access to the PT-package ORM (mirror MEM-PLAN-02).

This is the ONLY module in the codebase that imports the PtPackagePlan + PtPackage
ORM models from `pt_packages.models`. The service layer calls these module-level
async helpers and never executes `select(PtPackagePlan)` directly. ...

Transaction control: NO `session.commit()` and NO `session.flush()` calls live here
(mirror memberships D-14). The caller (service) owns the transactional moment so
it can co-write the audit_log row in the same UoW.

`from __future__ import annotations` is required: ...
"""
```

**Single-row read by id** (lines 52-59):

```python
async def get_plan_alive(session: AsyncSession, plan_id: UUID) -> PtPackagePlan | None:
    """Return alive plan by id, or None for missing/soft-deleted (D-33-08)."""
    stmt: Select[tuple[PtPackagePlan]] = select(PtPackagePlan).where(
        PtPackagePlan.id == plan_id,
        PtPackagePlan.deleted_at.is_(None),
    )
    result: PtPackagePlan | None = await session.scalar(stmt)
    return result
```

Phase 38 `schedule.repository.get_slot_by_id` drops the `deleted_at.is_(None)` clause (D-38-04). `bookings.repository.get_booking_by_id` likewise.

**Paginated list with PaginatedData.model_construct** (lines 280-330):

```python
async def list_pt_packages_paginated(
    session: AsyncSession, query: PtPackageListQuery
) -> PaginatedData[PtPackage]:
    predicates: list[Any] = []
    if query.client_id is not None:
        predicates.append(PtPackage.client_id == query.client_id)
    if query.status is not None:
        predicates.append(PtPackage.status == query.status.value)

    where_clause = and_(*predicates) if predicates else None

    total_stmt = select(func.count()).select_from(PtPackage)
    if where_clause is not None:
        total_stmt = total_stmt.where(where_clause)
    total = await session.scalar(total_stmt) or 0

    stmt: Select[tuple[PtPackage]] = select(PtPackage)
    if where_clause is not None:
        stmt = stmt.where(where_clause)
    # ... order_by branches ...
    offset = (query.page - 1) * query.page_size
    stmt = stmt.offset(offset).limit(query.page_size)
    rows = (await session.scalars(stmt)).all()
    return PaginatedData.model_construct(
        items=list(rows),
        total=total,
        page=query.page,
        page_size=query.page_size,
    )
```

**`with_for_update()` for overlap query** (D-38-06) — mirror via `.with_for_update()` chain on the SELECT used inside `publish_slot` (mentioned in CONTEXT.md §D-38-06 but no in-repo precedent for tstzrange overlap; this is a new pattern; the row-lock chain is the established part).

**N+1 prevention via joinedload** (D-38-08, Pitfall 19) — list query must use `options(joinedload(...))`. v1.4 has no in-tree analog with joinedload, but the SQLAlchemy 2.0 idiom is:

```python
from sqlalchemy.orm import joinedload
stmt = (
    select(Booking)
    .options(
        joinedload(Booking.slot).joinedload(TrainerAvailabilitySlot.trainer),
        joinedload(Booking.pt_package),
    )
    .where(...)
)
```

Add a query-count assertion test per D-38-08 last paragraph.

**Insert helper** (lines 231-258):

```python
async def insert_pt_package(
    session: AsyncSession,
    data: PtPackageCreateRequest,
    *,
    plan: PtPackagePlan,
    start_date: date,
    end_date: date | None,
) -> PtPackage:
    """Insert a PtPackage row. Caller MUST flush + commit (Plan 33-02 / D-33-09)."""
    pt_package = PtPackage(
        client_id=data.client_id,
        plan_id=plan.id,
        # ...snapshot fields...
    )
    session.add(pt_package)
    return pt_package
```

Keyword-only after `*` for field intent (also mirrors `pt_sessions/repository.py:131-168`).

---

### `app/modules/schedule/schemas.py` and `app/modules/bookings/schemas.py` (schema, request-response)

**Analog:** `apps/backend/app/modules/pt_sessions/schemas.py` (simpler) + `pt_packages/schemas.py` (sort enums)

**`BackendSchemaBase` for inputs, `ResponseData` for outputs** (lines 33-50):

```python
class PtSessionCreateRequest(BackendSchemaBase):
    """POST /api/v1/pt-sessions body (PT-15 / D-34-06).

    `extra='forbid'` (inherited) REJECTS unexpected fields with 422.
    ...
    """

    pt_package_id: UUID
    trainer_id: UUID
    performed_at: datetime  # ISO-8601 with offset; backdating window server-side
    notes: str | None = Field(default=None, max_length=500)
```

Phase 38 `SlotCreateRequest` = three fields (`trainer_id`, `start_time`, `end_time`) per D-38-05. `BookingCreateRequest` = `slot_id`, `client_id`, `pt_package_id`. Both use `BackendSchemaBase`, `extra='forbid'` inherited.

**StrEnum status mirror** (lines 42-51 of `pt_packages/schemas.py`):

```python
class PtPackageStatus(StrEnum):
    """PT-package lifecycle status (33-CONTEXT.md domain).

    Values byte-stable with migration 0014_pt_packages CHECK ck_pt_packages_status.
    """

    ACTIVE = "active"
    EXHAUSTED = "exhausted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
```

Phase 38 `SlotStatus = {ACTIVE, BOOKED, CANCELLED}` and `BookingStatus = {CONFIRMED, CANCELLED, NO_SHOW, COMPLETED}`.

**List query with `PageQuery` base + camelCase filters** (lines 192-197):

```python
class PtPackageListQuery(PageQuery):
    """GET /api/v1/pt-packages query parameters."""

    client_id: UUID | None = None
    status: PtPackageStatus | None = None
    sort: PtPackageListSort = PtPackageListSort.CREATED_AT_DESC
```

Phase 38 `SlotListQuery` adds `trainer_id`, `from_time`, `to_time` with `Field(default_factory=...)` for the Moscow-TZ-aware window defaults per CONTEXT.md §Specifics (NOT computed at module import).

---

### `app/modules/schedule/router.py` and `app/modules/bookings/router.py` (router, request-response)

**Analog:** `apps/backend/app/modules/pt_sessions/router.py` (single-router shape closer to schedule/bookings) + `apps/backend/app/modules/pt_packages/router.py` (cancel + Idempotency-Key replay block)

**RBAC-04 ordering: `require_permission` → `verify_csrf` → `verify_idempotency` → `get_db`** (`pt_sessions/router.py:76-87`):

```python
async def record_pt_session(
    payload: PtSessionCreateRequest,
    request: Request,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.PT_SESSIONS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    idempotency_key: Annotated[str, Depends(verify_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
```

**`Depends(verify_idempotency)` — Pitfall 14 + D-38-14** is the single line that closes Pitfall 14. NEVER manual `request.headers.get("idempotency-key")`.

**Two-phase Redis claim + replay block** (`pt_sessions/router.py:116-157`):

```python
incoming_body = await request.body()
incoming_hash = body_sha256(incoming_body)

is_first = await begin_idempotency(redis, idempotency_key)
if not is_first:
    stored = await load_idempotency_response(redis, idempotency_key)
    if stored is None or isinstance(stored, str):
        raise ConflictError("idempotency_in_flight")
    if stored["body_hash"] != incoming_hash:
        raise ValidationAppError("idempotency_key_reuse")
    return Response(
        content=base64.b64decode(stored["body_b64"]),
        status_code=stored["status_code"],
        media_type="application/json",
    )

pt_session = await service.record_pt_session(session, actor, payload)
response_envelope = envelope(pt_session)
body_bytes = json.dumps(
    response_envelope.model_dump(mode="json", by_alias=True),
    separators=(",", ":"),
    ensure_ascii=False,
).encode("utf-8")
envelope_json = json.dumps({
    "status_code": status.HTTP_201_CREATED,
    "body_hash": incoming_hash,
    "body_b64": base64.b64encode(body_bytes).decode("ascii"),
}, separators=(",", ":"), ensure_ascii=False)
await redis.set(
    f"{IDEMPOTENCY_REDIS_PREFIX}{idempotency_key}",
    envelope_json,
    ex=IDEMPOTENCY_TTL_SECONDS,
)
return Response(
    content=body_bytes,
    status_code=status.HTTP_201_CREATED,
    media_type="application/json",
)
```

`POST /bookings` (Plan 38-02) copies this block verbatim. `POST /trainer-slots` and the two cancel endpoints also use it for parity (mirrors PT-packages — the 4 PT-package mutating POSTs all carry Idempotency-Key per D-33-16).

**Read endpoint pattern** (no Idempotency-Key, no CSRF — `pt_sessions/router.py:256-274`):

```python
@pt_sessions_router.get(
    "/{pt_session_id}",
    response_model=ResponseEnvelope[PtSessionResponse],
    summary="Read a single PT-session (reception+owner; 404 pt_session_not_found)",
)
async def get_pt_session(
    pt_session_id: UUID,
    _actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.VIEW, Resource.PT_SESSIONS)),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PtSessionResponse]:
    return envelope(await service.get_pt_session(session, pt_session_id))
```

**RBAC mapping** (Phase 37 D-37-02/03 — already locked):
- `POST /trainer-slots` → `(CREATE, SCHEDULE_SLOTS)` — owner-only via OWNER_ONLY
- `GET /trainer-slots[/{id}]` → `(VIEW, SCHEDULE_SLOTS)` — both roles
- `POST /trainer-slots/{id}/cancel` → `(CANCEL, SCHEDULE_SLOTS)` — owner-only via OWNER_ONLY
- `POST /bookings` → `(CREATE, BOOKINGS)` — both roles
- `POST /bookings/{id}/cancel` → `(CANCEL, BOOKINGS)` — both roles (24h gate in service per D-38-09)
- `GET /bookings[/{id}]` → `(VIEW, BOOKINGS)` — both roles

---

### `app/modules/schedule/service.py` (service, replace stubs + add `publish_slot` / `cancel_slot` / list / get)

**Analog for stub replacement:** `apps/backend/app/modules/schedule/service.py:23-32` (existing stubs — preserve signatures; replace bodies only).

**Analog for `publish_slot`:** `apps/backend/app/modules/pt_packages/service.py:457-616` (`create_pt_package` — 10-step recipe with FK check → validate → INSERT → flush → translate IntegrityError → emit audit → commit).

**10-step orchestrator shape** (lines 461-494, docstring):

```python
async def create_pt_package(
    session: AsyncSession,
    actor: CurrentUser,
    data: PtPackageCreateRequest,
) -> PtPackageResponse:
    """Sell a PT-package (Phase 33 PT-07 / D-33-09 / D-33-17 / D-33-16).

    Owns the UoW (await session.commit() at end). 10-step recipe:
      1. Load plan via repository.get_plan_alive (404 ...).
      2. Server-enforced snapshot symmetry (D-33-17) — reject 422 ...
      3. Defensive pre-flight: reject if client already has an active ...
      4. Server-compute dates ...
      5. Insert pt_packages row ...
      6. ``await session.flush()`` — surfaces FK errors ... 409 ...
      7. Record payment in the same UoW via the ``get_payment_recorder()``
         Protocol slot (modules-independent contract — NEVER direct payments
         import). Server derives ``amount_kopecks`` ...
      8. ``audit.emit('pt_package_sold', ...)`` ...
      9. ``await session.commit()`` (SVC001 gate).
      10. Return PtPackageResponse with computed ``is_active`` field.
    """
```

`publish_slot` 10-step recipe:
1. Resolve trainer via `resolve_trainer_by_id` Protocol slot — 404 / 422 if inactive (mirror `pt_sessions/service.py:211-215`)
2. Future-only guard (SLOT-05): reject `start_time < datetime.now(UTC)` → 422 (mirror `pt_sessions/service.py:201-204`)
3. Overlap check via `with_for_update()` tstzrange query (D-38-06) → 409 `slot_overlap`
4. Buffer check at +/-10min (D-38-07) → 409 `slot_too_close`
5. Insert via `schedule.repository.insert_slot`
6. `await session.flush()`
7. Emit `slot_published` with payload matching `SlotPublishedPayload` (5 keys; stringify UUIDs + isoformat datetimes per D-38-17)
8. `await session.commit()`
9. Refresh narrow + return `SlotResponse`

**Replace `resolve_slot_by_id` body** (preserve signature `async def resolve_slot_by_id(session: AsyncSession, slot_id: UUID) -> SlotById | None`):

```python
async def resolve_slot_by_id(session: AsyncSession, slot_id: UUID) -> SlotById | None:
    """Public resolver delegate (D-37-06).

    Phase 38 bookings.service consumes via the ``SlotById`` Protocol slot in
    ``core.dependencies``. Silent-None semantics (mirror
    ``resolve_active_pt_package`` at pt_packages/service.py:439-449).
    """
    return await repository.get_slot_by_id(session, slot_id)
```

(Direct mirror of `pt_packages/service.py:439-449`.)

**Replace `restore_slot_to_active` body** — defensive raw UPDATE with predicate guard `WHERE id=:slot_id AND status='booked'`. Use raw `sa.text()` here (no cross-module concern; just consistency with the FSM predicate-gate pattern from `pt_sessions/repository.py:91-100`):

```python
# pt_sessions/repository.py:90-100 template:
stmt = sa.text(
    """
    UPDATE pt_packages
    SET status = 'exhausted',
        updated_at = now()
    WHERE id = :pt_package_id AND status = 'active'
    RETURNING id
    """,
)
```

Phase 38 variant: `UPDATE trainer_availability_slots SET status = 'active', updated_at = now() WHERE id = :slot_id AND status = 'booked' RETURNING id`. Caller-owns-txn (no commit, no flush — `cancel_booking` is the caller). Annotate `# noqa: SVC001 caller-owns-txn` per `pt_packages/service.py:660`.

**Error classes** — copy the `pt_packages/service.py:76-145` shape with `code` and `status_code` class attributes:

```python
class SlotNotFoundError(NotFoundError):
    code = "slot_not_found"
    status_code = 404

class SlotOverlapError(ConflictError):
    code = "slot_overlap"
    status_code = 409

class SlotTooCloseError(ConflictError):
    code = "slot_too_close"
    status_code = 409

class InvalidSlotTransitionError(ConflictError):
    code = "invalid_transition"
    status_code = 409
```

**`_assert_can_transition` helper** (mirror `pt_packages/service.py:184-197`):

```python
def _assert_can_transition(slot: TrainerAvailabilitySlot, *, target: str) -> None:
    """Central state-machine guard (D-38-10)."""
    allowed = SLOT_STATUS_TRANSITIONS.get(slot.status, frozenset())
    if target not in allowed:
        raise InvalidSlotTransitionError(
            "invalid_transition",
            fields={"from_status": slot.status, "to_status": target},
        )
```

---

### `app/modules/bookings/service.py` (service, atomic UoW with IntegrityError race translation + cross-module slot use)

**Analog for `create_booking`:** `apps/backend/app/modules/pt_sessions/service.py:166-293` (`record_pt_session` — atomic UoW with cross-module slot consume + IntegrityError race translation) + `apps/backend/app/modules/pt_packages/service.py:457-616` (`create_pt_package` — the FK + flush + IntegrityError translate pattern).

**Cross-module slot consume pattern** (`pt_packages/service.py:560-572`):

```python
try:
    payment = await get_payment_recorder()(
        session,
        subject_kind=PAYMENT_SUBJECT_KIND_PT_PACKAGE,
        subject_id=pt_package.id,
        amount_kopecks=pt_package.price_kopecks_snapshot,
        method="cash",
        received_by_user_id=actor.id,
        audit_actor=actor,
    )
except IntegrityError as exc:
    await session.rollback()
    raise ConflictError("payment_recording_failed") from exc
```

Phase 38 `create_booking` uses:
- `get_active_pt_package()` (existing slot, silent-None) — validate package; 409 if expired
- `resolve_slot_by_id()` (Phase 37 slot — Phase 38 replaces body) — validate slot exists; 404
- App-layer `_assert_can_transition(slot, target='booked')` — 409 if slot already booked / cancelled
- App-layer trainer-mismatch check between `pt_package.trainer_id` and `slot.trainer_id` → 409 `trainer_mismatch`
- Validity-window guard (Pitfall 18 / D-38-12): `if pt_package.end_date is not None and pt_package.end_date < slot.start_time.astimezone(MOSCOW_TZ).date(): raise PtPackageExpiredBeforeSlotError(...)` → 409
- INSERT booking + UPDATE slot to `'booked'` in the same UoW
- `await session.flush()` — surfaces `uq_bookings_slot_confirmed` IntegrityError
- Translate via constraint-name discriminator (see Shared Patterns §IntegrityError translation)

**Error classes** — copy `pt_sessions/service.py:73-158` shape:

```python
class BookingNotFoundError(NotFoundError):
    code = "booking_not_found"
    status_code = 404

class SlotAlreadyBookedError(ConflictError):
    code = "slot_already_booked"
    status_code = 409

class TrainerMismatchError(ConflictError):
    code = "trainer_mismatch"
    status_code = 409

class PtPackageExpiredBeforeSlotError(ConflictError):
    code = "pt_package_expired_before_slot"
    status_code = 409

class CancelWindowExpiredError(ForbiddenError):
    code = "cancel_window_expired"
    status_code = 403  # mirror pt_sessions/service.py:151-158

class InvalidBookingTransitionError(ConflictError):
    code = "invalid_transition"
    status_code = 409
```

**Replace `complete_booking` body** (preserve signature `async def complete_booking(session: AsyncSession, booking_id: UUID) -> None`):

```python
async def complete_booking(  # noqa: SVC001 caller-owns-txn
    session: AsyncSession,
    booking_id: UUID,
) -> None:
    """Transition booking confirmed→completed inside caller's UoW (D-38-13 / PKG-05).

    Caller (`pt_sessions.service.record_pt_session`) owns the surrounding
    transaction. We issue a predicate-gated UPDATE here so a concurrent
    cancel (status='cancelled') silently no-ops (FSM forward-only invariant
    `cancelled → ∅` from constants.py); 0-row UPDATE raises
    InvalidBookingTransitionError → 409 (defensive — pt_sessions service
    already validated status='confirmed' under SELECT FOR UPDATE).
    """
    stmt = sa.text(
        """
        UPDATE bookings
        SET status = 'completed',
            completed_at = now(),
            updated_at = now()
        WHERE id = :booking_id AND status = 'confirmed'
        RETURNING id
        """,
    )
    result = await session.execute(stmt, {"booking_id": booking_id})
    if result.first() is None:
        raise InvalidBookingTransitionError(
            "invalid_transition",
            fields={"to_status": "completed"},
        )
    # NO audit emit here — pt_sessions.service.record_pt_session already
    # emits `pt_session_recorded` with booking_id=str(...) per D-37-05.
```

**`_assert_can_transition` helper** — same shape as schedule version (D-38-10). Uses `BOOKING_STATUS_TRANSITIONS`.

**`cancel_booking` 24h window** (D-38-16) — mirror `pt_sessions/service.py:351-355`:

```python
# Step 2 — Cancel-window gate (D-34-07; B-12 from created_at, NOT performed_at).
if actor.role == Role.RECEPTION:
    age = datetime.now(UTC) - pt_session.created_at
    if age > timedelta(hours=CANCEL_WINDOW_HOURS_RECEPTION):
        raise CancelWindowExpiredError("cancel_window_expired")
```

Phase 38 variant compares against `booking.slot.start_time` (NOT `created_at` — D-38-16 spec) using:
```python
if actor.role == Role.RECEPTION:
    if booking.slot.start_time - datetime.now(UTC) < timedelta(hours=CANCEL_WINDOW_HOURS_RECEPTION):
        raise CancelWindowExpiredError("cancel_window_expired")
```

`cancel_booking` also calls `await restore_booking_slot(session, booking.slot_id)` (the Phase 37 BookingSlotRestorer Protocol slot accessor at `dependencies.py:536-547`) to flip slot booked→active in the same UoW.

---

### `app/modules/pt_packages/service.py` extensions (Plan 38-04)

**Analog for trainer-active validation:** `pt_sessions/service.py:210-215`:

```python
# Step 2 — Trainer via TrainerById Protocol slot (D-34-12a).
trainer = await resolve_trainer_by_id(session, data.trainer_id)
if trainer is None:
    raise TrainerNotFoundError("trainer_not_found")
if not trainer.is_active:
    raise TrainerInactiveError("trainer_inactive")
```

Plan 38-04 copies this verbatim into `create_pt_package` (only when `data.trainer_id is not None`).

**Analog for refund-guard cross-module count:** `pt_sessions/repository.py:103-128` (raw `sa.text()` + `# noqa: TABLE_REF` marker):

```python
stmt = sa.text(
    """
    SELECT id, client_id, status, sessions_remaining, end_date
    FROM pt_packages
    WHERE id = :pt_package_id
    """,  # noqa: TABLE_REF cross-module SQL per D-34-04a
)
result = await session.execute(stmt, {"pt_package_id": pt_package_id})
row = result.mappings().first()
return dict(row) if row is not None else None
```

Plan 38-04 implementation in `pt_packages/service.refund_pt_package` (D-38-11):

```python
# Pitfall 4 Option A / D-38-11 — block refund if outstanding confirmed bookings.
result = await session.execute(
    sa.text(
        "SELECT count(*) FROM bookings "
        "WHERE pt_package_id = :pkg_id AND status = 'confirmed'"
    ),  # noqa: TABLE_REF cross-module SQL per D-34-04a / Phase 38 D-38-11
    {"pkg_id": str(pt_package_id)},
)
if result.scalar_one() > 0:
    raise OutstandingBookingsExistError("outstanding_bookings_exist")
```

This MUST land BEFORE the existing `_assert_can_transition(target='cancelled')` call (line 879) so the friendly 409 fires before the FSM guard.

---

### `app/modules/pt_sessions/service.py` extensions (Plan 38-05)

**Analog for SELECT FOR UPDATE booking read** (Pitfall 12 / D-38-11 / D-38-19): `pt_sessions/repository.py:103-128` (existing `fetch_pt_package_metadata` raw text pattern) extended with `FOR UPDATE`:

```python
stmt = sa.text(
    """
    SELECT id, status, pt_package_id, slot_id
    FROM bookings
    WHERE id = :booking_id
    FOR UPDATE
    """,  # noqa: TABLE_REF cross-module SQL per D-34-04a / Phase 38 D-38-11
)
```

The `FOR UPDATE` is the line that defeats the future no-show cron race (D-38-19). Implementation lives in a new helper in `pt_sessions/repository.py` (e.g., `fetch_booking_metadata_for_update`) — keeps the cross-module SQL discipline that `pt_sessions/models.py:14-18` already documents.

**Analog for slot trainer cross-module read** — same raw text() pattern:

```python
stmt = sa.text(
    "SELECT trainer_id FROM trainer_availability_slots WHERE id = :slot_id"
)  # noqa: TABLE_REF cross-module SQL per D-34-04a / Phase 38 D-38-11
```

**Analog for booking completer Protocol slot consume** — `pt_packages/service.py:560-572` (`get_payment_recorder()(...)` cross-module slot use):

```python
# When booking_id provided and validations pass:
from app.core.dependencies import complete_booking_by_pt_session
await complete_booking_by_pt_session(session, booking_id)
```

Silent-None contract per Phase 37 D-37-06; production wiring guarantees registration. This call REPLACES any direct cross-module write — `pt_sessions` never imports from `bookings`.

**Audit emit extension** — extend `pt_sessions/service.py:255-269` (`pt_session_recorded` payload) with optional `booking_id=str(booking_id) if booking_id is not None else None` per D-37-05. The Pydantic schema `PtSessionRecordedPayload` was already extended in Phase 37 to accept `Optional[str]` for this field.

---

### `app/main.py` (composition root extension)

**Analog:** `apps/backend/app/main.py:170-197` (existing block where Phase 37 already registered the 3 Protocol slots). Phase 38 appends two `app.include_router(api)` mounts (or extends an existing API router include) for `schedule.router.router` and `bookings.router.router` BEFORE the final `app.include_router(api)` call. Update the docstring numbered-steps list (line 88 area) to mention the two new module routers.

No change to the 3 Phase 37 `register_*` calls — `register_slot_by_id_resolver(schedule_service.resolve_slot_by_id)` (line 193) still resolves to the same function reference; Phase 38 only replaces the function body.

---

### Tests (Plans 38-02, 38-04, 38-05)

**`tests/integration/bookings/test_booking_race.py` (NEW — BOOK-TEST-01)**

**Analog:** `apps/backend/tests/integration/pt_sessions/test_pt_session_record_race.py` (PTS-TEST-01)

**Race-test scaffolding** (lines 1-67):

```python
"""PTS-TEST-01 — N parallel POST /pt-sessions → 1x201 + (N-1)x409 pt_package_exhausted.

... Uses ``db_session_real_commit`` because SAVEPOINT-isolated ``db_session``
interferes with concurrent UPDATE serialisation.

Per D-34-10 every POST /pt-sessions requires ``Idempotency-Key`` — the race
test uses 2 DISTINCT keys (one per concurrent request) so the idempotency
layer does NOT collapse them into a replay branch; the race we want to
observe is at the DB predicate, NOT at the idempotency cache.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

async def _build_authed_client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://testserver")
    r = await client.post("/api/v1/auth/login", json={...})
    assert r.status_code == 200
    return client
```

Phase 38 `test_booking_race.py` substitutes: 2 parallel `POST /api/v1/bookings` for the same `slot_id` with **DISTINCT** Idempotency-Keys (per the analog's discipline — distinct keys force the race to the DB partial UNIQUE, not the Redis cache). Expected: 1x201 + 1x409 `slot_already_booked`. Use `db_session_real_commit` fixture.

**`tests/integration/pt_packages/test_pt_packages_refund_guard.py` (NEW or extend)** — mirror `tests/integration/pt_packages/test_pt_package_refund.py` shape. Two scenarios:
1. Sale → create confirmed booking referencing the package → POST `/pt-packages/{id}/refund` → 409 `outstanding_bookings_exist`
2. Sale → create booking → cancel booking → POST refund → 200 OK

**`tests/integration/pt_sessions/test_pt_sessions_booking_completion.py` (NEW)** — mirror `tests/integration/pt_sessions/test_pt_session_record.py`. Scenarios:
1. Happy path: record pt_session with `booking_id` → booking row reaches `status='completed'`
2. PKG-06 no-revert: record session → cancel session → booking remains `completed` (D-38-13)
3. Mismatch: record session with `booking.status='cancelled'` → 409 `booking_not_confirmed` (or whatever code Phase 38 picks)

---

## Shared Patterns

### Shared Pattern: SVC001 caller-owns-txn discipline

**Source:** `apps/backend/app/modules/pt_packages/service.py:7-8` + `pt_packages/service.py:660` (`# noqa: SVC001 caller-owns-txn` marker)

**Apply to:** Every state-mutating function in `schedule/service.py` and `bookings/service.py`.

Every public mutator (`publish_slot`, `cancel_slot`, `create_booking`, `cancel_booking`) MUST end with `await session.commit()`. Private helpers (`_assert_can_transition`, `complete_booking`, `restore_slot_to_active`) MUST carry `# noqa: SVC001 caller-owns-txn` on the `def` line. Phase 37 plan 37-05 already extended the SVC001 walker to target both new files.

---

### Shared Pattern: Audit emit with UUID stringify (REG-36-03 / D-38-17)

**Source:** `apps/backend/app/modules/pt_packages/service.py:585-605` (`pt_package_sold` emit callsite)

**Apply to:** All `audit.emit` callsites in `schedule.service.publish_slot`, `schedule.service.cancel_slot`, `bookings.service.create_booking`, `bookings.service.cancel_booking`.

```python
await audit.emit(
    session,
    "pt_package_sold",  # LITERAL (INFRA-11 AST gate)
    actor_user_id=actor.id,
    resource_type="pt_package",  # LITERAL
    resource_id=pt_package.id,
    pt_package_id=str(pt_package.id),
    client_id=str(pt_package.client_id),
    plan_id=str(pt_package.plan_id),
    plan_name_snapshot=pt_package.plan_name_snapshot,
    # ...
    start_date=pt_package.start_date.isoformat(),
    end_date=(
        pt_package.end_date.isoformat()
        if pt_package.end_date is not None
        else None
    ),
    payment_id=str(payment.id),
)
```

Rules:
- Event + resource_type are LITERAL strings (INFRA-11 AST gate).
- Every UUID value passed as a kwarg is `str(uuid)` (REG-36-03 / Pitfall 13).
- Every datetime value is `.isoformat()`.
- Payload kwargs MUST match the Pydantic `extra='forbid'` schema in `audit_payloads.py:337-424` (e.g. `SlotPublishedPayload` has exactly 5 keys: `slot_id`, `trainer_id`, `start_time`, `end_time`, `created_by_user_id` — extra/missing kwargs raise `ValidationError` at emit time).

---

### Shared Pattern: IntegrityError translation by constraint name

**Source:** `apps/backend/app/modules/pt_packages/service.py:153-176` (`_is_pt_package_plan_name_conflict` / `_is_active_pt_package_conflict`)

**Apply to:** `bookings/service.py` — `_is_slot_confirmed_conflict` for `uq_bookings_slot_confirmed` (D-38-15).

```python
def _is_active_pt_package_conflict(exc: IntegrityError) -> bool:
    """Return True iff `exc` was caused by `uq_pt_packages_active_per_client` (D-33-09)."""
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "uq_pt_packages_active_per_client":
        return True
    return "uq_pt_packages_active_per_client" in str(exc.orig)
```

Used at the flush point per `pt_packages/service.py:538-546`:

```python
try:
    await session.flush()
except IntegrityError as exc:
    await session.rollback()
    if _is_active_pt_package_conflict(exc):
        raise ActivePtPackageAlreadyExistsError(
            "active_pt_package_already_exists"
        ) from exc
    raise
```

Phase 38 `create_booking` substitutes `uq_bookings_slot_confirmed` → `SlotAlreadyBookedError("slot_already_booked")`.

---

### Shared Pattern: Cross-module raw SQL with `# noqa: TABLE_REF` marker (D-34-04a / D-38-11)

**Source:** `apps/backend/app/modules/pt_sessions/repository.py:59-72, 103-128`

**Apply to:** `pt_packages/service.refund_pt_package` (refund guard count), `pt_sessions/service.record_pt_session` (booking SELECT FOR UPDATE + slot trainer SELECT).

```python
stmt = sa.text(
    """
    UPDATE pt_packages
    SET sessions_remaining = sessions_remaining - 1,
        updated_at = now()
    WHERE id = :pt_package_id
      AND sessions_remaining > 0
      AND status = 'active'
    RETURNING sessions_remaining
    """,  # noqa: TABLE_REF cross-module SQL per D-34-04a
)
result = await session.execute(stmt, {"pt_package_id": pt_package_id})
```

Rules:
- ALWAYS named parameters (`:pt_package_id`), never f-string interpolation.
- ALWAYS the `# noqa: TABLE_REF cross-module SQL per D-34-04a` marker (Phase 38 may extend the marker to `per D-34-04a / Phase 38 D-38-11`).
- ALWAYS reach via `sa.text()`, never `from app.modules.bookings.models import Booking`.

---

### Shared Pattern: Protocol slot consume + silent-None contract

**Source:** `apps/backend/app/modules/pt_sessions/service.py:211` (`resolve_trainer_by_id`) and `pt_packages/service.py:561` (`get_payment_recorder()(...)`)

**Apply to:** `bookings/service.create_booking` uses `get_active_pt_package(session, client_id)` (existing slot from Phase 33) and `resolve_slot_by_id(session, slot_id)` (Phase 37 slot, Phase 38 body); `bookings/service.cancel_booking` uses `restore_booking_slot(session, slot_id)`; `pt_sessions/service.record_pt_session` uses `complete_booking_by_pt_session(session, booking_id)` (Phase 37 slot, Phase 38 body).

Silent-None: consumer treats `None` as "no such row" / "feature unavailable" and either raises a domain error or proceeds (per slot semantics in `dependencies.py:482-547`).

```python
trainer = await resolve_trainer_by_id(session, data.trainer_id)
if trainer is None:
    raise TrainerNotFoundError("trainer_not_found")
```

NEVER `from app.modules.schedule.service import resolve_slot_by_id` — always go through `app.core.dependencies` accessors. This is what keeps the `modules-independent` import-linter contract green.

---

### Shared Pattern: `datetime.now(UTC)` (Pitfall 7 / D-38-16)

**Source:** `apps/backend/app/modules/pt_sessions/service.py:201-208, 352-355`

**Apply to:** All time comparisons in `bookings/service.py` and `schedule/service.py`.

```python
from datetime import UTC, datetime, timedelta

now = datetime.now(UTC)
delta = now - data.performed_at
if delta.total_seconds() < 0:
    raise PerformedAtInFutureError("performed_at_in_future")
```

```python
if actor.role == Role.RECEPTION:
    age = datetime.now(UTC) - pt_session.created_at
    if age > timedelta(hours=CANCEL_WINDOW_HOURS_RECEPTION):
        raise CancelWindowExpiredError("cancel_window_expired")
```

NEVER `datetime.utcnow()` (deprecated in 3.12, naive datetimes break TIMESTAMPTZ comparisons). mypy strict will flag any `utcnow()` regression in CI.

---

### Shared Pattern: Moscow-TZ business-date comparison (Pitfall 18 / D-38-12)

**Source:** `apps/backend/app/modules/pt_packages/repository.py:213` (`today = datetime.now(ZoneInfo("Europe/Moscow")).date()`) + `pt_packages/service.py:523` (`start_date = datetime.now(ZoneInfo("Europe/Moscow")).date()`)

**Apply to:** `bookings/service.create_booking` validity-window guard (D-38-12).

```python
from zoneinfo import ZoneInfo

MOSCOW_TZ = ZoneInfo("Europe/Moscow")

if pt_package.end_date is not None and \
   pt_package.end_date < slot.start_time.astimezone(MOSCOW_TZ).date():
    raise PtPackageExpiredBeforeSlotError("pt_package_expired_before_slot")
```

NEVER `.date()` on the bare UTC datetime — Moscow is UTC+3, so a slot at 01:00 Moscow is 22:00 UTC the previous day; date comparison MUST happen in Moscow time. Also see `payments/repository.py:43-47`:

```python
_MOSCOW = ZoneInfo("Europe/Moscow")

def _moscow_midnight_utc(day: date) -> datetime:
    """Return the UTC datetime corresponding to 00:00:00 Europe/Moscow on `day`."""
```

---

### Shared Pattern: `PaginatedData.model_construct` envelope for list endpoints

**Source:** `apps/backend/app/modules/pt_packages/service.py:262-268` + repository helper using `model_construct` per docstring `pt_packages/repository.py:65-71`.

**Apply to:** All Phase 38 list endpoints (3 of them per SC #5): `schedule.service.list_slots`, `bookings.service.list_bookings`, `bookings.service.list_bookings_for_client`.

```python
return PaginatedData.model_construct(
    items=[PtPackagePlanResponse.model_validate(p) for p in page.items],
    total=page.total,
    page=page.page,
    page_size=page.page_size,
)
```

NEVER bare arrays. Always the `{items, total, page, pageSize}` envelope.

---

## No Analog Found

None. Every Phase 38 file maps to an existing v1.4 precedent or a Phase 37 stub. The single genuinely new sub-pattern is the **tstzrange overlap query with `with_for_update()`** in `schedule.service.publish_slot` (D-38-06) — but the components (overlap predicate, row-lock chain) appear individually elsewhere in the codebase and the SQLAlchemy idiom is documented in CONTEXT.md §D-38-06 explicitly. Planner should treat it as new code informed by `pt_sessions/repository.py:84-100` (`with_for_update`-equivalent predicate gate via raw SQL) and the standard SA `tstzrange` + `op("&&")` documented in CONTEXT.md.

---

## Metadata

**Analog search scope:**
- `apps/backend/alembic/versions/` (16 migrations scanned)
- `apps/backend/app/modules/pt_packages/` (full read)
- `apps/backend/app/modules/pt_sessions/` (full read)
- `apps/backend/app/modules/schedule/` (existing stubs)
- `apps/backend/app/modules/bookings/` (existing stubs)
- `apps/backend/app/core/dependencies.py` (Protocol slot wiring patterns)
- `apps/backend/app/core/audit_payloads.py` (v1.5 payload schemas, lines 320-463)
- `apps/backend/app/main.py:170-197` (composition-root extension point)
- `apps/backend/tests/integration/pt_sessions/test_pt_session_record_race.py` (race-test scaffolding)

**Files scanned:** ~15 (each read once; no re-reads).

**Pattern extraction date:** 2026-05-17.

**Phase-37 bedrock relied upon (already on `master`):**
- 3 Protocol slots registered in `dependencies.py:482-599`
- 3 stub bodies in `schedule/service.py` + `bookings/service.py` (signatures pinned)
- `SLOT_STATUS_TRANSITIONS` + `BOOKING_STATUS_TRANSITIONS` constants
- 5 audit payload schemas (`SlotPublishedPayload`, `SlotCancelledPayload`, `BookingCreatedPayload`, `BookingCancelledPayload`, `BookingNoShowPayload`) in `audit_payloads.py:337-424`
- RBAC entries for `SCHEDULE_SLOTS` / `BOOKINGS` Resource enum values
- Composition-root wiring + bot-worker defensive double-wiring of `register_slot_by_id_resolver`

Phase 38 ships pure business code on top of this scaffold; no foundation work is duplicated.
