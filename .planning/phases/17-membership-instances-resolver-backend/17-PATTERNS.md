# Phase 17: Membership Instances + Resolver (backend) - Pattern Map

**Mapped:** 2026-05-07
**Files analyzed:** 21 (5 module files extended + 1 migration + 5 wiring/core modifies + 1 module conftest extended + 7 new test files)
**Analogs found:** 21 / 21 (every artifact has a direct existing analog — Phase 16 same-module + clients module + Phase 4 dependencies slot)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/backend/app/modules/memberships/models.py` (extend) | model | request-response (ORM) | `apps/backend/app/modules/clients/models.py` (FK + CheckConstraint + Index in `__table_args__`); same-file `MembershipPlan` | exact (extension) |
| `apps/backend/app/modules/memberships/schemas.py` (extend) | schemas (DTO) | request-response | same-file `MembershipPlanUpdateRequest` (explicit-null guard, max_length, default=None) | exact (extension) |
| `apps/backend/app/modules/memberships/repository.py` (extend) | repository | CRUD + read | same-file plan repo helpers; `apps/backend/app/modules/clients/repository.py` (predicate accumulation, ORDER BY composite) | exact (extension) |
| `apps/backend/app/modules/memberships/service.py` (extend) | service | CRUD + audit + state-machine | same-file `create_plan` / `update_plan` / `soft_delete_plan` (IntegrityError translate, audit emit before flush, commit) | exact (extension) |
| `apps/backend/app/modules/memberships/router.py` (extend) | router (controller) | request-response | same-file `create_plan` route (RBAC-04 ordering); `apps/backend/app/modules/clients/router.py:124-144` (DELETE with CSRF) | exact (extension) |
| `apps/backend/alembic/versions/0005_memberships.py` (new) | migration | DDL | `apps/backend/alembic/versions/0004_membership_plans.py` (revision header + `op.create_table` + `op.execute` for expression index); `apps/backend/alembic/versions/0002_clients.py:101-106` (FK ON DELETE RESTRICT pattern) | exact |
| `apps/backend/app/core/dependencies.py` (extend) | wiring (Protocol + slot) | callback-registration | same-file `register_user_loader` (lines 32-61) — verbatim mirror | exact (parallel slot) |
| `apps/backend/app/main.py` (modify) | wiring (composition root) | startup | same-file `register_user_loader(load_user_by_id)` callsite (line 88) — second loader | exact (parallel call) |
| `apps/backend/app/api/v1/router.py` (modify) | wiring | request-response | same-file existing `include_router(plans_router, ...)` (line 17) | exact (extension) |
| `apps/backend/app/core/exceptions.py` (modify) | exception | n/a | same-file `PlanNameExistsError` / `PlanNotFoundError` block (lines 102-117) | exact (extension) |
| `apps/backend/alembic/env.py` (modify, conditional) | config | n/a | self (existing `_include_object` filter lines 59-67) | partial (only if composite DESC index needs suppression) |
| `apps/backend/tests/integration/memberships/conftest.py` (extend) | test fixture | n/a | same-file `OWNER_EMAIL` / `_seed_user` / `authed_client_owner` (Phase 16) | exact (factory addition) |
| `apps/backend/tests/integration/memberships/test_memberships_crud.py` (new) | test (integration) | request-response | `apps/backend/tests/integration/memberships/test_plans_crud.py` (Phase 16) | exact |
| `apps/backend/tests/integration/memberships/test_memberships_list.py` (new) | test (integration) | request-response | `apps/backend/tests/integration/memberships/test_plans_list.py` (Phase 16) | exact |
| `apps/backend/tests/integration/memberships/test_memberships_rbac.py` (new) | test (integration) | request-response | `apps/backend/tests/integration/memberships/test_plans_rbac.py` (Phase 16) | exact |
| `apps/backend/tests/integration/memberships/test_memberships_audit.py` (new) | test (integration) | request-response + DB read | `apps/backend/tests/integration/memberships/test_audit_writes.py` (Phase 16) | exact |
| `apps/backend/tests/integration/memberships/test_plan_in_use.py` (new) | test (integration) | request-response (FK 409) | clients/test_clients_crud.py "delete frees unique-name slot" (Phase 16 D-15 forward-promise) | role-match |
| `apps/backend/tests/integration/memberships/test_resolver.py` (new) | test (integration) | direct service call | `apps/backend/tests/integration/auth/` direct loader-call test (`get_current_user` with stub registered) | role-match |
| `apps/backend/tests/unit/memberships/test_state_machine.py` (new) | test (unit, parametrized) | n/a | `apps/backend/tests/unit/memberships/test_schemas.py` (Phase 16 unit shape — extend with parametrize matrix) | role-match |
| `apps/backend/tests/unit/memberships/test_schemas.py` (extend) | test (unit) | n/a | same-file Phase 16 schema unit tests | exact (extension) |
| `apps/backend/openapi.json` (regen) | generated artifact | n/a | self (Phase 16 regenerated) | exact |

---

## Pattern Assignments

### `app/modules/memberships/models.py` — add `class Membership` (extension)

**Analogs:**
- Same-file `MembershipPlan` (lines 21-50) — composition pattern.
- `apps/backend/app/modules/clients/models.py:93-111` — FK declaration with `ondelete="RESTRICT"` and composite `__table_args__` block.

**Mixin composition (NO `SoftDeleteMixin`)** — Phase 17 D-12 / CONTEXT.md domain line 12 ("No soft-delete column — lifecycle is purely status-based"):

```python
# memberships/models.py — same file, AFTER class MembershipPlan
class Membership(Base, UUIDPkMixin, TimestampMixin):
    """Membership instance — client X bought plan Y on date Z (MEM-01)."""

    __tablename__ = "memberships"
```

Compare same-file `MembershipPlan` (line 21) which mixes `SoftDeleteMixin` — the new `Membership` class deliberately omits it.

**FK declaration with named constraint + ON DELETE RESTRICT** — copy from `clients/models.py:93-97`:

```python
# clients/models.py:93-97
created_by_user_id: Mapped[UUIDType] = mapped_column(
    PgUUID(as_uuid=True),
    ForeignKey("users.id", ondelete="RESTRICT"),
    nullable=False,
)
```

Phase 17 emits two FKs (CONTEXT.md domain line 12):

```python
client_id: Mapped[UUIDType] = mapped_column(
    PgUUID(as_uuid=True),
    ForeignKey("clients.id", ondelete="RESTRICT", name="fk_memberships_client_id_clients"),
    nullable=False,
)
plan_id: Mapped[UUIDType] = mapped_column(
    PgUUID(as_uuid=True),
    ForeignKey("membership_plans.id", ondelete="RESTRICT", name="fk_memberships_plan_id_membership_plans"),
    nullable=False,
)
```

**Constraint-name pinning**: `fk_memberships_plan_id_membership_plans` is referenced as a literal in `_is_plan_in_use_conflict` (D-05). NAMING_CONVENTION (`core/database.py:28-34`) produces this name deterministically from `fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s`, but pin it explicitly with `name=` for defence against table renames.

**`__table_args__` — CHECK + composite index with DESC** — CONTEXT.md D-20 + CD-04:

```python
__table_args__ = (
    CheckConstraint(
        "status IN ('active', 'expired', 'cancelled')",
        name="status",  # NAMING_CONVENTION expands to ck_memberships_status
    ),
    CheckConstraint(
        "activation_policy = 'purchase_date'",
        name="activation_policy",  # NAMING_CONVENTION expands to ck_memberships_activation_policy
    ),
    Index(
        "ix_memberships_client_id_status_end_date",
        "client_id",
        "status",
        text("end_date DESC"),
    ),
)
```

Compare same-file `MembershipPlan.__table_args__` (lines 33-50) which uses the same `CheckConstraint(name="<short>")` pattern (NAMING_CONVENTION expands the short name to the full prefixed name) and `Index(..., text("lower(name)"), unique=True, postgresql_where=text(...))`. The DESC ordering on `end_date` uses `text("end_date DESC")` — SA represents this as a literal expression in the index column list (verified at the SA-2.0 docs level). If autogenerate flags drift on this index, add it to `env.py:_include_object` (see migration section).

**Resolver-protocol exposure** — `Membership` ORM structurally satisfies `ActiveMembership` Protocol via `id: UUID, client_id: UUID, end_date: date, status: str` (D-18). No DTO conversion at the resolver boundary.

---

### `app/modules/memberships/schemas.py` — add membership DTOs (extension)

**Analogs:**
- Same-file `MembershipPlanCreateRequest` (lines 42-55) — `Field(min_length=, max_length=, ge=, le=)` defence-in-depth pattern.
- Same-file `MembershipPlanUpdateRequest._reject_explicit_null` (lines 74-85) — verbatim port for `MembershipCancelRequest`.

**`MembershipStatus` + `MembershipListSort` StrEnum** — same-file `MembershipPlanSort` (lines 32-36) is the template:

```python
# Phase 16 lines 32-36
class MembershipPlanSort(StrEnum):
    """Membership plan list sort modes (D-08, CD-04)."""
    CREATED_AT_DESC = "created_at_desc"  # default — newest first
    NAME_ASC = "name_asc"
```

Phase 17 adds (CONTEXT.md D-09):

```python
class MembershipStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

class MembershipListSort(StrEnum):
    CREATED_AT_DESC = "created_at_desc"  # default
    END_DATE_DESC = "end_date_desc"
    START_DATE_DESC = "start_date_desc"
```

**`MembershipCreateRequest`** — model after same-file `MembershipPlanCreateRequest` (Phase 16 lines 42-55). CONTEXT.md D-03:

```python
class MembershipCreateRequest(BackendSchemaBase):
    client_id: UUID
    plan_id: UUID
    paid_at: datetime | None = None             # D-03 — omit → DB NULL
    notes: str | None = Field(default=None, max_length=1000)
    # NO start_date / end_date / status / activation_policy — server-computed (D-04)
```

**`MembershipCancelRequest` — verbatim explicit-null guard mirror** — same-file lines 74-85 (Phase 16 D-05):

```python
# Phase 16 schemas.py:74-85 — VERBATIM port target
@model_validator(mode="before")
@classmethod
def _reject_explicit_null(cls, data: Any) -> Any:
    # D-05: explicit null is rejected; omit the key to leave field unchanged.
    if isinstance(data, dict):
        null_keys = [k for k, v in data.items() if v is None]
        if null_keys:
            raise ValueError(
                f"Explicit null not supported for: {sorted(null_keys)}. "
                "Omit the key to leave the field unchanged."
            )
    return data
```

Phase 17 ports verbatim (CONTEXT.md D-11). The error-message text is identical — D-11 explicitly says "mirror of Phase 16 D-05":

```python
class MembershipCancelRequest(BackendSchemaBase):
    """POST /memberships/{id}/cancel body. Reason is optional (D-11)."""
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="before")
    @classmethod
    def _reject_explicit_null(cls, data: Any) -> Any:
        if isinstance(data, dict):
            null_keys = [k for k, v in data.items() if v is None]
            if null_keys:
                raise ValueError(
                    f"Explicit null not supported for: {sorted(null_keys)}. "
                    "Omit the key to leave the field unchanged."
                )
        return data
```

**`MembershipResponse`** — model after same-file `MembershipPlanResponse` (Phase 16 lines 97-108). CONTEXT.md D-10 — exposes ALL snapshot fields:

```python
class MembershipResponse(ResponseData):
    id: UUID
    client_id: UUID
    plan_id: UUID
    plan_name_snapshot: str
    duration_days_snapshot: int
    price_kopecks_snapshot: int
    start_date: date
    end_date: date
    status: MembershipStatus
    cancelled_at: datetime | None
    cancel_reason: str | None
    paid_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
```

**`MembershipListQuery`** — model after same-file `MembershipPlanListQuery` (Phase 16 lines 114-119). CONTEXT.md D-09:

```python
class MembershipListQuery(PageQuery):
    client_id: UUID | None = None                                   # D-09 optional
    status: MembershipStatus | None = None                          # D-09 single-value
    sort: MembershipListSort = MembershipListSort.CREATED_AT_DESC
```

---

### `app/modules/memberships/repository.py` — add membership CRUD (extension)

**Analogs:**
- Same-file `get_alive` / `list_alive` / `insert_plan` / `update_plan` (Phase 16 lines 44-152).
- Use `from __future__ import annotations` already present (line 25) — no change.

**`get_membership(session, membership_id)` — no soft-delete filter** (CONTEXT.md domain line 12). Compare same-file `get_alive` (lines 44-51):

```python
# Phase 16 lines 44-51 — has deleted_at filter
async def get_alive(session: AsyncSession, plan_id: UUID) -> MembershipPlan | None:
    stmt: Select[tuple[MembershipPlan]] = select(MembershipPlan).where(
        MembershipPlan.id == plan_id,
        MembershipPlan.deleted_at.is_(None),
    )
    result: MembershipPlan | None = await session.scalar(stmt)
    return result
```

Phase 17 — drop the deleted_at filter (no soft-delete on memberships):

```python
async def get_membership(session: AsyncSession, membership_id: UUID) -> Membership | None:
    stmt: Select[tuple[Membership]] = select(Membership).where(Membership.id == membership_id)
    return await session.scalar(stmt)
```

**`list_memberships(session, query)` — predicate accumulation** — copy from same-file `list_alive` (Phase 16 lines 54-99):

```python
# Phase 16 lines 68-99 — predicate accumulation pattern (template)
predicates: list[Any] = [MembershipPlan.deleted_at.is_(None)]
if query.active is not None:
    predicates.append(MembershipPlan.active == query.active)
total_stmt = select(func.count()).select_from(MembershipPlan).where(and_(*predicates))
total = await session.scalar(total_stmt) or 0
stmt: Select[tuple[MembershipPlan]] = select(MembershipPlan).where(and_(*predicates))
if query.sort == MembershipPlanSort.NAME_ASC:
    stmt = stmt.order_by(func.lower(MembershipPlan.name).asc(), MembershipPlan.created_at.desc())
else:
    stmt = stmt.order_by(MembershipPlan.created_at.desc(), MembershipPlan.id.desc())
offset = (query.page - 1) * query.page_size
stmt = stmt.offset(offset).limit(query.page_size)
rows = (await session.scalars(stmt)).all()
return PaginatedData.model_construct(items=list(rows), total=total, page=query.page, page_size=query.page_size)
```

Phase 17 mirrors with seed predicate empty (no soft-delete), conditional `client_id`/`status` filters, and three sort branches:

```python
predicates: list[Any] = []   # NO deleted_at filter (no soft-delete on memberships)
if query.client_id is not None:
    predicates.append(Membership.client_id == query.client_id)
if query.status is not None:
    predicates.append(Membership.status == query.status.value)
# ... same total_stmt + stmt + offset/limit + model_construct shape
if query.sort == MembershipListSort.END_DATE_DESC:
    stmt = stmt.order_by(Membership.end_date.desc(), Membership.created_at.desc(), Membership.id.desc())
elif query.sort == MembershipListSort.START_DATE_DESC:
    stmt = stmt.order_by(Membership.start_date.desc(), Membership.created_at.desc(), Membership.id.desc())
else:  # CREATED_AT_DESC
    stmt = stmt.order_by(Membership.created_at.desc(), Membership.id.desc())
```

**`insert_membership(session, data, plan, start_date, end_date)` — caller owns flush**. Same-file `insert_plan` (Phase 16 lines 102-118) is the template (caller owns flush, no `session.flush()` here). Phase 17 also takes a resolved `MembershipPlan` ORM ref so the snapshot copy happens inside this function (D-04: `plan_name_snapshot=plan.name, duration_days_snapshot=plan.duration_days, price_kopecks_snapshot=plan.price_kopecks`).

**`update_membership_status(session, membership, *, status, cancelled_at, cancel_reason)`** — narrower than same-file `update_plan` (no model_dump diff loop). Just sets fields:

```python
membership.status = status
if cancelled_at is not None:
    membership.cancelled_at = cancelled_at
if cancel_reason is not None:
    membership.cancel_reason = cancel_reason
```

**`find_active_for_client(session, client_id)` — resolver query**. CONTEXT.md MEM-04 + D-17 + specifics line 264:

```python
stmt = (
    select(Membership)
    .where(Membership.client_id == client_id, Membership.status == "active")
    .order_by(Membership.end_date.desc(), Membership.created_at.desc())
    .limit(1)
)
return await session.scalar(stmt)
```

The `(client_id, status, end_date DESC)` composite index covers this query (D-20).

---

### `app/modules/memberships/service.py` — add membership service functions + extend `soft_delete_plan` (extension)

**Analogs:**
- Same-file `_is_plan_name_conflict` (Phase 16 lines 58-68) — **VERBATIM template** for `_is_plan_in_use_conflict`.
- Same-file `create_plan` (lines 100-134), `update_plan` (lines 137-190), `soft_delete_plan` (lines 193-221) — write-path orchestration.
- `apps/backend/app/modules/clients/service.py:99-104` — `_is_phone_conflict` peer reference.

**`_is_plan_in_use_conflict` — VERBATIM mirror of `_is_plan_name_conflict`** — CONTEXT.md D-05. Phase 16 lines 58-68:

```python
# memberships/service.py:58-68 — TEMPLATE (Phase 16)
def _is_plan_name_conflict(exc: IntegrityError) -> bool:
    """Return True iff `exc` was caused by `uq_membership_plans_name_alive` (D-02)."""
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "uq_membership_plans_name_alive":
        return True
    return "uq_membership_plans_name_alive" in str(exc.orig)
```

Phase 17 ports verbatim with constraint-name swap:

```python
def _is_plan_in_use_conflict(exc: IntegrityError) -> bool:
    """Return True iff `exc` was caused by `fk_memberships_plan_id_membership_plans` (D-05).

    Direct mirror of `_is_plan_name_conflict` with constraint name swapped to the
    FK name. Different SA error class internally (FK ON DELETE RESTRICT vs UNIQUE)
    but identical translation control flow. asyncpg exposes `constraint_name` for
    both; the `in str(exc.orig)` substring fallback covers drivers that don't.
    """
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "fk_memberships_plan_id_membership_plans":
        return True
    return "fk_memberships_plan_id_membership_plans" in str(exc.orig)
```

**`create_membership` write-path** — CONTEXT.md D-02 + D-04 + D-08 ordering. Template = same-file `create_plan` (Phase 16 lines 100-134):

```python
# memberships/service.py:100-134 — TEMPLATE (Phase 16)
async def create_plan(session, actor, data) -> MembershipPlanResponse:
    plan = await repository.insert_plan(session, data)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_plan_name_conflict(exc):
            raise PlanNameExistsError("plan_name_exists") from exc
        raise
    await audit.emit(
        session,
        "membership_plan_created",
        actor_user_id=actor.id,
        resource_type="membership_plan",
        resource_id=plan.id,
        name=plan.name, duration_days=plan.duration_days, price_kopecks=plan.price_kopecks,
    )
    await session.commit()
    return MembershipPlanResponse.model_validate(plan)
```

Phase 17 `create_membership(session, actor, data)` flow (CONTEXT.md D-02 / D-04):

```python
async def create_membership(session, actor, data) -> MembershipResponse:
    # 1. Resolve plan (404 if missing/soft-deleted; 409 if inactive — D-02)
    plan = await repository.get_alive(session, data.plan_id)
    if plan is None:
        raise PlanNotFoundError("plan_not_found")
    if not plan.active:
        raise PlanInactiveError("plan_inactive")

    # 2. Server-compute dates (D-04 — Europe/Moscow)
    today = datetime.now(ZoneInfo("Europe/Moscow")).date()
    end_date = today + timedelta(days=plan.duration_days - 1)

    # 3. Insert with snapshot (caller owns flush per Phase 16 pattern)
    membership = await repository.insert_membership(
        session, data, plan=plan, start_date=today, end_date=end_date,
    )
    await session.flush()  # surfaces FK errors (client_id missing → IntegrityError)

    # 4. Audit emit BEFORE commit (D-14 co-transactional). MEM-AUDIT-01 payload shape.
    await audit.emit(
        session,
        "membership_created",   # LITERAL — Phase 15 D-11 step 3
        actor_user_id=actor.id,
        resource_type="membership",   # LITERAL — Phase 15 D-11 step 3
        resource_id=membership.id,
        client_id=membership.client_id,
        plan_id=membership.plan_id,
        end_date=membership.end_date.isoformat(),
    )
    await session.commit()
    return MembershipResponse.model_validate(membership)
```

**`cancel_membership` — state-machine guard before mutate, emit before commit** — CONTEXT.md D-12 + D-14 + D-15. Template = same-file `update_plan` (Phase 16 lines 137-190):

```python
async def cancel_membership(session, actor, membership_id, data) -> MembershipResponse:
    membership = await repository.get_membership(session, membership_id)
    if membership is None:
        raise MembershipNotFoundError("membership_not_found")

    # D-15: transition guard BEFORE any mutation (no partial write on rejection)
    _assert_can_cancel(membership)   # raises InvalidTransitionError(from_status, to_status='cancelled')

    # D-12: mutate (status='cancelled', cancelled_at=now(UTC), cancel_reason=...)
    await repository.update_membership_status(
        session, membership,
        status="cancelled",
        cancelled_at=datetime.now(tz=UTC),
        cancel_reason=data.reason,
    )
    await session.flush()

    # D-14: audit payload — omit reason key when None (NOT reason=None)
    kwargs: dict[str, Any] = {} if data.reason is None else {"reason": data.reason}
    await audit.emit(
        session,
        "membership_cancelled",   # LITERAL
        actor_user_id=actor.id,
        resource_type="membership",   # LITERAL
        resource_id=membership.id,
        client_id=membership.client_id,
        **kwargs,
    )
    await session.refresh(membership, attribute_names=["updated_at"])
    await session.commit()
    return MembershipResponse.model_validate(membership)
```

**Note: `session.refresh(membership, attribute_names=["updated_at"])`** — same rationale as Phase 16 `update_plan` (line 188 docstring): SA 2.0 expires attributes after flush; refresh manually before Pydantic serialisation to avoid `MissingGreenlet` on lazy-load.

**`_assert_can_cancel` and `_assert_can_expire` — module-level free functions** (CONTEXT.md CD-03 default). State-machine matrix per D-19:

```python
def _assert_can_cancel(membership: Membership) -> None:
    if membership.status != "active":
        raise InvalidTransitionError(
            "invalid_transition",
            fields={"from_status": membership.status, "to_status": "cancelled"},
        )

def _assert_can_expire(membership: Membership) -> None:
    if membership.status != "active":
        raise InvalidTransitionError(
            "invalid_transition",
            fields={"from_status": membership.status, "to_status": "expired"},
        )
```

`InvalidTransitionError` packs `from_status`/`to_status` into the response envelope's `fields` dict (CONTEXT.md D-12 — already supported by `AppError(message, *, fields=...)` in `core/exceptions.py:13-16`).

**`soft_delete_plan` extension — D-08 ordering + FK error translation** — CONTEXT.md D-05 + D-08. Modify same-file `soft_delete_plan` (Phase 16 lines 193-221):

```python
# Phase 16 lines 193-221 — TEMPLATE (current state)
async def soft_delete_plan(session, actor, plan_id) -> None:
    plan = await repository.get_alive(session, plan_id)
    if plan is None:
        raise PlanNotFoundError("plan_not_found")
    await repository.soft_delete_plan(session, plan)
    await audit.emit(
        session,
        "membership_plan_archived",
        actor_user_id=actor.id,
        resource_type="membership_plan",
        resource_id=plan.id,
    )
    await session.flush()
    await session.commit()
```

Phase 17 — wrap the `flush()` in IntegrityError translation (D-05 + D-08: emit-before-flush so FK error rolls back the audit row co-transactionally):

```python
async def soft_delete_plan(session, actor, plan_id) -> None:
    plan = await repository.get_alive(session, plan_id)
    if plan is None:
        raise PlanNotFoundError("plan_not_found")
    await repository.soft_delete_plan(session, plan)
    await audit.emit(
        session,
        "membership_plan_archived",
        actor_user_id=actor.id,
        resource_type="membership_plan",
        resource_id=plan.id,
    )
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()  # rolls back BOTH the soft-delete AND the audit row
        if _is_plan_in_use_conflict(exc):
            raise PlanInUseError("plan_in_use") from exc
        raise
    await session.commit()
```

**Important — D-08 audit-emit-before-flush invariant**: with this ordering, the IntegrityError on the FK rolls back the audit row too (co-transactional contract from Phase 16 D-14). If we emitted AFTER flush we'd never reach the emit on a FK reject — but we'd also never need to roll it back. The current ordering (emit before flush) keeps the rollback contract explicit and matches Phase 16 D-14 for `client_soft_deleted` (where the audit captures pre-deletion state).

**`resolve_active_membership_by_client` — public symbol** — CONTEXT.md CD-06 default + D-16 (plain awaitable, NOT a Depends):

```python
async def resolve_active_membership_by_client(
    session: AsyncSession, client_id: UUID
) -> Membership | None:
    """Return the canonical active membership for `client_id`, or None.

    Implements MEM-04 tiebreak: ORDER BY end_date DESC, created_at DESC LIMIT 1.
    Used by the Phase 4 D-24 slot pattern from `core/dependencies.py`. Returns the
    SA ORM `Membership`; structurally satisfies `ActiveMembership` Protocol (D-18).
    """
    return await repository.find_active_for_client(session, client_id)
```

**`list_memberships` + `get_membership` read-side stubs** — copy same-file `list_plans` (Phase 16 lines 71-86) and `get_plan` (lines 89-97) shape: no audit, no commit, just `repository.<fn>` + `model_validate`.

---

### `app/modules/memberships/router.py` — add 4 endpoints (extension)

**Analogs:**
- Same-file plans endpoints (Phase 16 lines 62-161) — RBAC-04 ordering, `Annotated[CurrentUser, Depends(...)]` shape, `envelope()` wrapping, status codes.
- `apps/backend/app/modules/clients/router.py:124-144` — DELETE with CSRF + 204 status.

**RBAC permission mapping** — CONTEXT.md domain line 19 + permissions.py:42-67:

| Endpoint | Action | Resource | OWNER_ONLY? | CSRF? |
|----------|--------|----------|-------------|-------|
| GET `/memberships` (list) | VIEW | MEMBERSHIPS | NO (reception+owner) | n/a |
| GET `/memberships/{id}` | VIEW | MEMBERSHIPS | NO | n/a |
| POST `/memberships` (sell) | CREATE | MEMBERSHIPS | NO (reception+owner) | YES |
| POST `/memberships/{id}/cancel` | CANCEL | MEMBERSHIPS | YES (owner-only) | YES |

The 2 owner-only pairs `(CANCEL, MEMBERSHIPS)` and `(DELETE, MEMBERSHIPS)` are already in `OWNER_ONLY` (permissions.py:65-66) — `require_permission` dispatches verbatim.

**RBAC-04 ordering** — same-file lines 104-115 (Phase 16 `create_plan`) is the template:

```python
# Phase 16 router.py:104-115 — TEMPLATE (RBAC-04: require_permission BEFORE verify_csrf)
async def create_plan(
    payload: MembershipPlanCreateRequest,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.MEMBERSHIP_PLANS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[MembershipPlanResponse]:
    plan = await service.create_plan(session, actor, payload)
    return envelope(plan)
```

Phase 17 POST sell:

```python
@router.post(
    "",  # mounted at /api/v1/memberships
    response_model=ResponseEnvelope[MembershipResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Sell a membership (reception+owner; 404 plan_not_found, 409 plan_inactive)",
)
async def create_membership(
    payload: MembershipCreateRequest,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.MEMBERSHIPS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[MembershipResponse]:
    membership = await service.create_membership(session, actor, payload)
    return envelope(membership)
```

**POST `/{id}/cancel`** — owner-only via `Action.CANCEL × Resource.MEMBERSHIPS` (in OWNER_ONLY), returns 200 (NOT 204 — body carries the cancelled MembershipResponse). RBAC-04 ordering:

```python
@router.post(
    "/{membership_id}/cancel",
    response_model=ResponseEnvelope[MembershipResponse],
    status_code=status.HTTP_200_OK,
    summary="Cancel a membership (owner-only; 409 invalid_transition for non-active)",
)
async def cancel_membership(
    membership_id: UUID,
    payload: MembershipCancelRequest,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CANCEL, Resource.MEMBERSHIPS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[MembershipResponse]:
    membership = await service.cancel_membership(session, actor, membership_id, payload)
    return envelope(membership)
```

**GET list/single** — copy same-file Phase 16 `list_plans` (lines 67-77) and `get_plan` (lines 85-95) verbatim with substitutions:

```python
@router.get(
    "",
    response_model=ResponseEnvelope[PaginatedData[MembershipResponse]],
    summary="List memberships with filters and pagination",
)
async def list_memberships(
    query: Annotated[MembershipListQuery, Depends()],
    _actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.VIEW, Resource.MEMBERSHIPS)),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[MembershipResponse]]:
    page = await service.list_memberships(session, query)
    return envelope(page)
```

**Router-mount strategy (CD-02 + CONTEXT.md domain line 18)**: prefer SPLIT — keep `app/modules/memberships/router.py` exporting `router` (plans, mounted at `/membership-plans`) AND a new `memberships_router` (instances, mounted at `/memberships`). Two `APIRouter()` instances in the same module file. Less disruptive than renaming the existing export. Wiring file (`app/api/v1/router.py`) imports both.

---

### `app/core/dependencies.py` — add resolver slot (extension; VERBATIM mirror of `register_user_loader`)

**Analog:** same-file `register_user_loader` block (lines 32-61). Phase 17 D-16 / CONTEXT.md MEM-05 / specifics line 269 mandates a "second composition-root carve-out (after register_user_loader, Phase 5 D-15)".

**Phase 4 D-24 slot template** (lines 32-61 verbatim):

```python
# core/dependencies.py:32-61 — TEMPLATE
class CurrentUser(Protocol):
    """Structural type for the authenticated user (D-24)."""
    id: UUID
    role: Role


UserLoader = Callable[[AsyncSession, UUID], Awaitable[CurrentUser | None]]
"""Async callable: (session, user_id) -> CurrentUser | None."""

_user_loader: UserLoader | None = None


def register_user_loader(loader: UserLoader) -> None:
    """Composition-root setter — called once by `app.main.create_app` in Phase 5.

    Idempotent: re-registering replaces the slot (useful in tests that want to inject a
    stub loader). Phase 4 has no caller; Phase 5 wires `load_user_by_id`.
    """
    global _user_loader
    _user_loader = loader
```

Phase 17 adds the parallel block AFTER the existing user-loader code (CONTEXT.md MEM-05):

```python
class ActiveMembership(Protocol):
    """Structural type for the active-membership row (MEM-05).

    Per D-18: only the 4 attributes consumed by Phase 19 visits service. Snapshot
    fields, plan_id, dates other than end_date, audit timestamps are NOT in the
    Protocol (visits doesn't need them). The SA `Membership` ORM structurally
    satisfies this Protocol because all 4 attributes are mapped — no DTO conversion
    at the resolver boundary.
    """
    id: UUID
    client_id: UUID
    end_date: date
    status: str


ActiveMembershipResolver = Callable[
    [AsyncSession, UUID], Awaitable[ActiveMembership | None]
]
"""Async callable: (session, client_id) -> ActiveMembership | None.

Returns None when the client has no active membership (the canonical case the
visits service treats as "no membership"). Tiebreak — when multiple active rows
exist — is the implementation's responsibility (MEM-04 locks: latest end_date,
then created_at DESC).
"""

_active_membership_resolver: ActiveMembershipResolver | None = None


def register_active_membership_resolver(resolver: ActiveMembershipResolver) -> None:
    """Composition-root setter — called once by `app.main.create_app` in Phase 17.

    Second loader slot after `register_user_loader` (Phase 5 D-15). Idempotent:
    re-registering replaces the slot, useful for tests that inject a stub resolver
    via `create_app()`. Phase 17 wires `app.modules.memberships.service.resolve_active_membership_by_client`.
    """
    global _active_membership_resolver
    _active_membership_resolver = resolver


async def resolve_active_membership(
    session: AsyncSession, client_id: UUID
) -> ActiveMembership | None:
    """Consumer entry point — used by `app.modules.visits.service` in Phase 19.

    Per CONTEXT.md `<code_context>` line 224: returns None when the slot is unset
    (production code always registers in `create_app()`; tests can register a stub
    or rely on the default-None behaviour). Differs from `_user_loader` defensive
    raise because the visits service can't distinguish "no resolver registered"
    from "no active membership" — and that's the correct semantic for the
    consumer.
    """
    if _active_membership_resolver is None:
        return None
    return await _active_membership_resolver(session, client_id)
```

**Add `from datetime import date` to imports** (Phase 17 only — `date` not currently imported in this file).

---

### `app/main.py` — register the second loader (modify)

**Analog:** same-file `register_user_loader(load_user_by_id)` callsite (line 88).

**Existing template** (lines 77-88):

```python
# app/main.py:77-88 — TEMPLATE
# D-15: composition root fills the Phase 4 loader slot. This is the ONLY
# place where app.main reaches into app.modules.*. The importlinter
# contract scopes source_modules=app.core, so app.main is intentionally
# outside the scope.
#
# WR-05 (Phase 9 review): register_user_loader is idempotent by design —
# see app/core/dependencies.py:54-61. Re-registering replaces the slot,
# which is intentional so tests can inject a stub loader through
# create_app(). Calling it on every create_app() (per-test, per-export)
# is therefore safe; the export script never enters lifespan and tests
# use the slot to swap in fakes deterministically.
register_user_loader(load_user_by_id)
```

Phase 17 adds (CONTEXT.md domain line 25 / specifics line 269):

```python
# Add to imports near top of file:
from app.core.dependencies import register_active_membership_resolver, register_user_loader
from app.modules.memberships.service import resolve_active_membership_by_client

# AFTER register_user_loader(load_user_by_id), inside create_app():

# Phase 17 MEM-05: second composition-root carve-out (after register_user_loader,
# Phase 5 D-15). Same architectural exception — app.main is NOT in the
# core-not-depend-on-modules importlinter scope. The visits service (Phase 19) will
# call resolve_active_membership() through the slot; production wires the real
# resolver here, tests can override via create_app() because the slot is idempotent.
register_active_membership_resolver(resolve_active_membership_by_client)
```

**Docstring update** (header `Phase 17 additions:` block) — note the second loader call following the existing Phase 5 entry.

---

### `app/api/v1/router.py` — mount memberships under `/memberships` (modify)

**Analog:** same-file existing 3 `include_router` calls (lines 14-17).

**Existing template** (lines 1-17):

```python
# app/api/v1/router.py:10-17 — current state
from app.modules.auth.router import router as auth_router
from app.modules.clients.router import router as clients_router
from app.modules.memberships.router import router as plans_router

v1 = APIRouter()
v1.include_router(auth_router, prefix="/auth", tags=["auth"])
v1.include_router(clients_router, prefix="/clients", tags=["clients"])
v1.include_router(plans_router, prefix="/membership-plans", tags=["membership-plans"])
```

Phase 17 adds — assuming router-split strategy (CD-02 default — two routers in `app.modules.memberships.router`):

```python
from app.modules.memberships.router import (
    memberships_router,
    router as plans_router,
)
# ... existing v1 / include_router calls ...
v1.include_router(memberships_router, prefix="/memberships", tags=["memberships"])
```

**Wire path** = `/memberships` (NOT kebab — the Resource value `Resource.MEMBERSHIPS = "memberships"` is already lowercase per `permissions.py:42`).

---

### `app/core/exceptions.py` — add 4 new errors (modify)

**Analog:** same-file `PlanNameExistsError` / `PlanNotFoundError` block (lines 102-117).

**Existing template** (lines 102-117):

```python
# core/exceptions.py:102-117 — TEMPLATE
class PlanNotFoundError(NotFoundError):
    """Raised when GET/PATCH/DELETE references a non-existent or soft-deleted plan."""
    code = "plan_not_found"
    status_code = 404


class PlanNameExistsError(ConflictError):
    """Raised on POST/PATCH when name collides with an alive plan (Phase 16 D-02)."""
    code = "plan_name_exists"
    status_code = 409
```

Phase 17 appends (CONTEXT.md D-02 + D-05 + D-12 + D-15):

```python
class PlanInactiveError(ConflictError):
    """Raised on POST /memberships when target plan.active=False (Phase 17 D-02).

    Service-layer defence against UI bypass (the reception sell screen filters via
    ?active=true per Phase 16 D-08, but a malformed/replayed POST can still
    reference a deactivated plan).
    """
    code = "plan_inactive"
    status_code = 409


class PlanInUseError(ConflictError):
    """Raised on DELETE /membership-plans when the FK fk_memberships_plan_id_membership_plans
    rejects the delete (Phase 17 D-05).

    Discriminated against IntegrityError by service.py:_is_plan_in_use_conflict
    checking constraint name "fk_memberships_plan_id_membership_plans".
    Per D-06: ANY membership row blocks deletion (including cancelled and expired).
    """
    code = "plan_in_use"
    status_code = 409


class InvalidTransitionError(ConflictError):
    """Raised on POST /memberships/{id}/cancel for non-active source state (Phase 17 D-12).

    Constructor populates `fields={'from_status': ..., 'to_status': ...}` packed
    into the response envelope's fields key (per AppError.__init__ signature).
    """
    code = "invalid_transition"
    status_code = 409


class MembershipNotFoundError(NotFoundError):
    """Raised when GET / POST cancel references a non-existent membership id."""
    code = "membership_not_found"
    status_code = 404
```

CD-01 (message wording) — match existing precedent. The first arg to AppError is `message`; `code` and `status_code` are class attrs (lines 7-16):

```python
# core/exceptions.py:7-16 — AppError signature
class AppError(Exception):
    code: str = "app_error"
    status_code: int = 500
    def __init__(self, message: str = "", *, fields: dict[str, object] | None = None) -> None:
```

`InvalidTransitionError` ctor call shape: `raise InvalidTransitionError("invalid_transition", fields={"from_status": ..., "to_status": ...})`.

---

### `alembic/versions/0005_memberships.py` — create memberships table (new)

**Analogs:**
- `alembic/versions/0004_membership_plans.py` (Phase 16) — revision header, `op.create_table` shape, CHECK + PK constraints, `op.execute` for non-autogenerable index, downgrade pattern.
- `alembic/versions/0002_clients.py:101-106` — FK creation with `ondelete="RESTRICT"` and `name=op.f(...)`.

**Revision header — VERBATIM template** (Phase 16 lines 1-26):

```python
# 0004_membership_plans.py:1-26 — TEMPLATE
"""membership_plans
Revision ID: 0004_membership_plans
Revises: 0002_clients
Create Date: 2026-05-07 12:00:00.000000

Phase 16 / MEM-PLAN-01 — owner-only plan catalog SKU table.

Notes:
- Partial-unique on lower(name) WHERE deleted_at IS NULL is an EXPRESSION index;
  SQLAlchemy autogenerate cannot represent it. Installed via raw op.execute(...).
  Suppressed in alembic/env.py:_include_object to keep autogenerate clean.
- The constraint name "uq_membership_plans_name_alive" is referenced as a literal
  string by app/modules/memberships/service.py:_is_plan_name_conflict (D-02).
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0004_membership_plans"
down_revision: str | None = "0002_clients"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

Phase 17 (CONTEXT.md D-20 + specifics line 260):

```python
"""memberships
Revision ID: 0005_memberships
Revises: 0004_membership_plans
Create Date: 2026-05-07 ..

Phase 17 / MEM-01 — membership instance table + composite resolver index.

Notes:
- Composite index (client_id, status, end_date DESC) is an EXPRESSION-bearing index
  (DESC ordering on end_date); SQLAlchemy autogenerate may flag drift on it.
  Installed via op.execute() to be explicit about the DESC ordering. Suppressed in
  alembic/env.py:_include_object if autogenerate-noisy.
- Constraint name "fk_memberships_plan_id_membership_plans" is referenced as a
  literal string by app/modules/memberships/service.py:_is_plan_in_use_conflict (D-05).
- No soft-delete column — lifecycle is purely status-based (D-12 per CONTEXT.md).
"""
revision: str = "0005_memberships"
down_revision: str | None = "0004_membership_plans"
```

**`op.create_table` with FKs** — Phase 16 lines 30-65 + clients FK pattern (Phase 8 lines 101-106):

```python
# 0002_clients.py:101-106 — FK template
sa.ForeignKeyConstraint(
    ["created_by_user_id"],
    ["users.id"],
    name=op.f("fk_clients_created_by_user_id_users"),
    ondelete="RESTRICT",
),
```

Phase 17 emits:

```python
def upgrade() -> None:
    op.create_table(
        "memberships",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("plan_id", sa.UUID(), nullable=False),
        sa.Column("plan_name_snapshot", sa.String(length=120), nullable=False),
        sa.Column("duration_days_snapshot", sa.Integer(), nullable=False),
        sa.Column("price_kopecks_snapshot", sa.BigInteger(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column(
            "status", sa.String(length=16),
            server_default=sa.text("'active'"), nullable=False,
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "activation_policy", sa.String(length=32),
            server_default=sa.text("'purchase_date'"), nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'expired', 'cancelled')",
            name=op.f("ck_memberships_status"),
        ),
        sa.CheckConstraint(
            "activation_policy = 'purchase_date'",
            name=op.f("ck_memberships_activation_policy"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memberships")),
        sa.ForeignKeyConstraint(
            ["client_id"], ["clients.id"],
            name=op.f("fk_memberships_client_id_clients"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["membership_plans.id"],
            name=op.f("fk_memberships_plan_id_membership_plans"),  # literal-ref'd by service.py
            ondelete="RESTRICT",
        ),
    )
    # Composite resolver index — DESC on end_date requires raw SQL (CD-04 + D-20).
    op.execute(
        "CREATE INDEX ix_memberships_client_id_status_end_date "
        "ON memberships (client_id, status, end_date DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_memberships_client_id_status_end_date")
    op.drop_table("memberships")
```

**No `pg_trgm` extension** (no ILIKE search on memberships). **No partial-unique** (D-01 stacking is allowed).

---

### `alembic/env.py` — possibly extend `_include_object` filter (modify, conditional)

**Analog:** same-file existing filter (lines 59-67):

```python
# alembic/env.py:59-67 — TEMPLATE
return not (
    type_ == "index"
    and name
    in (
        "ix_clients_last_name_trgm",
        "ix_clients_first_name_trgm",
        "uq_membership_plans_name_alive",
    )
)
```

Phase 17 — IF the DESC composite index produces autogenerate drift, add `"ix_memberships_client_id_status_end_date"` to the tuple. Verify post-migration with `alembic check`. CONTEXT.md specifics line 262: "Document in alembic/env.py:_include_object if the index becomes autogenerate-noisy (Phase 8 pattern)." This is conditional — the planner runs `alembic check` after authoring the migration to decide.

**Add model registration** (lines 25-28) — already present:

```python
# alembic/env.py:25-28 — already includes memberships.models
import app.modules.auth.models
import app.modules.clients.models
import app.modules.memberships.models   # Phase 16 already added this
```

The `Membership` class lives in the same `models.py` file, so no additional import needed (Python imports the module — both ORM classes register against `Base.metadata`).

---

### `tests/integration/memberships/conftest.py` — add `make_membership` factory (extend)

**Analog:** same-file Phase 16 fixtures (`OWNER_EMAIL`, `seeded_owner`, `_seed_user`, `authed_client_owner`).

**Existing fixture chain (Phase 16, lines 76-160)** is reused verbatim. Phase 17 adds:

1. **`make_plan` factory** (if not already present from Phase 16) — wraps `MembershipPlan(...)` insert + commit on the SAVEPOINT-mode session. Returns the plan id.
2. **`make_membership` factory** — wraps `Membership(...)` insert + commit. Signature: `make_membership(client_id, plan_id, *, status="active", end_date=None, ...)`. Computes snapshot fields from a fetched plan.

```python
@pytest_asyncio.fixture
async def make_plan(db_session: AsyncSession):
    async def _make(*, name="Базовый", duration_days=30, price_kopecks=250000, active=True):
        plan = MembershipPlan(
            name=name, duration_days=duration_days,
            price_kopecks=price_kopecks, active=active,
        )
        db_session.add(plan)
        await db_session.commit()  # SAVEPOINT — outer fixture rolls back
        return plan
    return _make


@pytest_asyncio.fixture
async def make_membership(db_session: AsyncSession):
    async def _make(*, client_id, plan, status="active", end_date=None, start_date=None):
        today = start_date or date.today()
        end = end_date or (today + timedelta(days=plan.duration_days - 1))
        membership = Membership(
            client_id=client_id, plan_id=plan.id,
            plan_name_snapshot=plan.name,
            duration_days_snapshot=plan.duration_days,
            price_kopecks_snapshot=plan.price_kopecks,
            start_date=today, end_date=end, status=status,
        )
        db_session.add(membership)
        await db_session.commit()
        return membership
    return _make
```

CONTEXT.md domain line 208: `make_plan` exists post-16; `make_membership` is added.

---

### `tests/integration/memberships/test_memberships_*.py` — 5 new integration test files

**Common helper pattern** — `_csrf_headers(client)` from same-folder `test_plans_crud.py` (Phase 16):

```python
# Phase 16 test_plans_crud.py:27-28 — TEMPLATE
def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf", "")}
```

Phase 17 ports verbatim into each test file (or shared `helpers.py`).

#### `test_memberships_crud.py`

- POST happy path (201 with snapshot fields populated, `start_date == today_moscow`, `end_date == start_date + duration_days - 1`).
- POST with `paidAt` ISO timestamp → row has matching `paid_at` (CONTEXT.md specifics line 267).
- POST without `paidAt` → row has `paid_at IS NULL`.
- POST with non-existent `planId` → 404 `plan_not_found`.
- POST with `planId` of `active=false` plan → 409 `plan_inactive` (D-02).
- POST with non-existent `clientId` → IntegrityError on FK → translates? Test the 422/500 surface — D-02 doesn't translate this case, so it surfaces as the generic AppError handler shape.
- POST cancel happy path (200 with `status='cancelled'`, `cancelled_at != null`, `cancel_reason == body`).
- POST cancel with no body → 200 + audit row payload omits `reason` key.
- POST cancel on non-existent id → 404 `membership_not_found`.

#### `test_memberships_list.py`

- Default GET returns active+expired+cancelled (no status filter — D-09).
- `?status=active` filters.
- `?clientId=<uuid>` filters.
- `?sort=end_date_desc` orders correctly.
- Pagination boundaries (page=2 with 21+ items).
- Envelope shape: `{ data: { items, total, page, pageSize } }`.

#### `test_memberships_rbac.py`

- Reception POST sale → 200 (NOT in OWNER_ONLY).
- Reception POST cancel → 403 (CANCEL × MEMBERSHIPS in OWNER_ONLY).
- Owner POST cancel → 200.
- Reception GET list → 200.
- Unauth canary on each → 401.

Pattern: same-folder `test_plans_rbac.py` (Phase 16) lines 54-65 (verbatim port with substitution).

#### `test_memberships_audit.py`

- POST sale → `membership_created` row with payload `{client_id, plan_id, end_date}`.
- POST cancel with reason → `membership_cancelled` row with payload `{client_id, reason}`.
- POST cancel without reason → `membership_cancelled` row with payload `{client_id}` — **no `reason` key** (D-14).
- 422 on POST sale (e.g. malformed body) → audit_log empty (co-transactional rollback).
- 409 `plan_inactive` → audit_log empty.

Pattern: same-folder `test_audit_writes.py` (Phase 16) — copy DB-read shape:

```python
# Phase 16 test_audit_writes.py — TEMPLATE
rows = (
    await db_session.scalars(
        select(AuditLog).where(
            AuditLog.action == "client_created",   # → "membership_created"
            AuditLog.resource_id == client_id,
        )
    )
).all()
```

#### `test_plan_in_use.py`

CONTEXT.md specifics line 265 — three test cases:
1. Create plan → sell membership → DELETE plan → 409 `plan_in_use`.
2. Cancel the membership → DELETE plan → STILL 409 (D-06: cancelled rows also block).
3. Hard-delete the membership row in raw SQL → DELETE plan → 204 success.

Pattern: same-folder `test_plans_crud.py` 409 conflict test (Phase 16 lines ~84-97 per Phase 16 PATTERNS.md).

#### `test_resolver.py`

CONTEXT.md specifics line 263 — direct service call without going through `core/dependencies.py`:

```python
from app.modules.memberships.service import resolve_active_membership_by_client

# Sell membership #1 (90 days) → resolver returns it.
m1 = await make_membership(client_id=cid, plan=plan90, end_date=today + timedelta(89))
got = await resolve_active_membership_by_client(db_session, cid)
assert got.id == m1.id

# Sell membership #2 (180 days, longer end_date) → resolver returns #2 (latest end_date).
m2 = await make_membership(client_id=cid, plan=plan180, end_date=today + timedelta(179))
got = await resolve_active_membership_by_client(db_session, cid)
assert got.id == m2.id

# Cancel #2 → resolver returns #1.
# Cancel #1 → resolver returns None.
```

Plus tests:
- Cancelled-only client → resolver returns None.
- Expired-only client → resolver returns None.
- Never-bought client → resolver returns None.
- Composition-root sanity: registered slot returns the same result as direct service call (one assertion).

CD-06 default — `resolve_active_membership_by_client` is a public symbol so test imports it directly without going through `core/dependencies.py`.

---

### `tests/unit/memberships/test_state_machine.py` — TESTS-10 9-cell matrix (new)

**Analog:** parametrize pattern in unit tests; structure follows pytest parametrize.

CONTEXT.md D-19 — 9 cells (3 source states × 3 actions):

```python
import pytest
from app.core.exceptions import InvalidTransitionError
from app.modules.memberships.service import _assert_can_cancel, _assert_can_expire

@pytest.mark.parametrize("from_status,action,expect", [
    # active row
    ("active",    "cancel", "ok"),
    ("active",    "expire", "ok"),
    ("active",    "create-self", "n/a"),
    # expired row
    ("expired",   "cancel", "invalid_transition"),
    ("expired",   "expire", "invalid_transition"),
    ("expired",   "create-self", "n/a"),
    # cancelled row
    ("cancelled", "cancel", "invalid_transition"),
    ("cancelled", "expire", "invalid_transition"),
    ("cancelled", "create-self", "n/a"),
])
def test_state_machine_matrix(from_status, action, expect):
    if expect == "n/a":
        return  # creation is void → active, not a state-machine cell
    membership = _stub_membership(status=from_status)
    if expect == "ok":
        if action == "cancel":
            _assert_can_cancel(membership)  # no raise
        else:
            _assert_can_expire(membership)
    else:
        with pytest.raises(InvalidTransitionError) as exc_info:
            (_assert_can_cancel if action == "cancel" else _assert_can_expire)(membership)
        assert exc_info.value.fields == {"from_status": from_status, "to_status": "cancelled" if action == "cancel" else "expired"}
```

CD-03 default: free functions in `service.py` (not a separate `_state.py` module).

---

### `tests/unit/memberships/test_schemas.py` — extend with membership DTO tests (extend)

**Analog:** Phase 16 schema unit tests for `MembershipPlanCreateRequest` / `MembershipPlanUpdateRequest`.

Phase 17 adds (CONTEXT.md domain lines 36-37):

- `MembershipCreateRequest` accepts `paidAt` ISO timestamp; `paidAt` omitted → `paid_at is None`.
- `MembershipCreateRequest` rejects `notes` longer than 1000 chars.
- `MembershipCreateRequest` rejects extra keys (e.g. `startDate`) per `extra='forbid'`.
- `MembershipCancelRequest` rejects `{reason: null}` (explicit-null guard, D-11 verbatim mirror).
- `MembershipCancelRequest` rejects `reason` longer than 500 chars (D-11).
- `MembershipCancelRequest` accepts empty body / no fields → `reason is None`.
- Wire camelCase ↔ Python snake_case alias_generator pair test (`paidAt ↔ paid_at`, `clientId ↔ client_id`, `cancelReason ↔ cancel_reason`).
- `MembershipResponse` serialises `planNameSnapshot` as camelCase.

---

## Shared Patterns

### Authentication / Authorization

**Source:** `apps/backend/app/core/dependencies.py` — `CurrentUser`, `require_permission`, `verify_csrf`, `get_db`.
**Source pattern (router):** `apps/backend/app/modules/memberships/router.py:104-115` (Phase 16).
**Apply to:** every endpoint in the new `memberships_router`.

```python
actor: Annotated[CurrentUser, Depends(require_permission(Action.<X>, Resource.MEMBERSHIPS))],
_csrf: Annotated[None, Depends(verify_csrf)],     # only on POST
session: Annotated[AsyncSession, Depends(get_db)],
```

**RBAC-04 ordering invariant**: `Depends(require_permission(...))` MUST be declared BEFORE `Depends(verify_csrf)` in the function signature. `tests/integration/test_route_introspection.py` enforces this.

### IntegrityError → DomainError translation

**Source:** `apps/backend/app/modules/memberships/service.py:58-68` (Phase 16 `_is_plan_name_conflict`).
**Apply to:** Phase 17 `_is_plan_in_use_conflict` in same file (D-05).

```python
def _is_plan_in_use_conflict(exc: IntegrityError) -> bool:
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "fk_memberships_plan_id_membership_plans":
        return True
    return "fk_memberships_plan_id_membership_plans" in str(exc.orig)

try:
    await session.flush()
except IntegrityError as exc:
    await session.rollback()
    if _is_plan_in_use_conflict(exc):
        raise PlanInUseError("plan_in_use") from exc
    raise
```

**Constraint name pinning**: `fk_memberships_plan_id_membership_plans` is the canonical FK name. NAMING_CONVENTION (`core/database.py:32`) produces this deterministically; pin in migration with `name=op.f(...)` AND in the ORM `ForeignKey(name=...)` to defend against renames.

### Audit emit + commit

**Source:** `apps/backend/app/modules/memberships/service.py` Phase 16 callsites.
**Apply to:** `create_membership` and `cancel_membership` write paths (and the extended `soft_delete_plan`).

- `audit.emit(session, "<event>", actor_user_id=actor.id, resource_type="<resource>", resource_id=<id>, **payload)` — both event-name and resource_type strings MUST be string literals (Phase 15 D-11 step 3 / `tests/unit/test_audit_taxonomy.py`).
- `await session.commit()` MUST appear at the end of every write path (Phase 15 INFRA-13 / `tests/unit/test_service_commit_gate.py`). The gate already covers `app.modules.memberships.service` (Phase 16 extended `_INSPECTED_SERVICES`, line 169).
- Update path (`cancel_membership`): `await session.refresh(membership, attribute_names=["updated_at"])` BEFORE commit (same MissingGreenlet rationale as Phase 16 `update_plan` line 188).

**Locked event payload shapes** (Phase 15 LOCKED_AUDIT_EVENTS):
- `("membership_created", "membership")` → `{client_id, plan_id, end_date}` (kwargs to `audit.emit`).
- `("membership_cancelled", "membership")` → `{client_id, reason?}` — D-14 omit-key-when-None: `kwargs = {} if reason is None else {"reason": reason}`.
- `("membership_expired", "membership")` → Phase 18 (NOT this phase).

### Composition-root carve-out (second loader slot)

**Source:** `apps/backend/app/main.py:88` + `apps/backend/app/core/dependencies.py:32-61`.
**Apply to:** Phase 17 `register_active_membership_resolver` (parallel slot in core/dependencies.py) + `app.main.create_app()` callsite.

The `app.main` module is exempt from `core-not-depend-on-modules` because that importlinter contract scopes `source_modules = app.core`, NOT `app`. Phase 17 adds a second cross-import (`from app.modules.memberships.service import resolve_active_membership_by_client`) — same architectural exception. The docstring update should explicitly call out "second composition-root carve-out (after register_user_loader, Phase 5 D-15)".

### State-machine guard before mutation

**Source:** N/A in existing code (Phase 17 introduces).
**Apply to:** `_assert_can_cancel(membership)` and `_assert_can_expire(membership)` in service.py.

Per D-15: transition is checked BEFORE any state change. An invalid transition raises `InvalidTransitionError` and never produces a partial write or stray audit row. The guard is a free function (CD-03) called at the top of `cancel_membership` (and the future Phase 18 `expire_membership`).

### Test fixture chain

**Source:** `apps/backend/tests/integration/conftest.py` (root) + `apps/backend/tests/integration/memberships/conftest.py` (Phase 16).
**Apply to:** Phase 17 extends Phase 16's same-folder conftest with `make_membership` factory.

- `db_session` SAVEPOINT-mode fixture comes from the root conftest (do not redefine).
- `redis_clean`, `_client_app_overrides`, `seeded_owner`, `seeded_reception`, `authed_client_owner`, `authed_client_reception` are already present (Phase 16) — reused verbatim.
- Login flow seeds `sz_access`, `sz_refresh`, `sportzal_csrf` cookies; mutation tests read `client.cookies.get("sportzal_csrf", "")` for the `X-CSRF-Token` header.

### Migration FK + composite-DESC index

**Source:** `apps/backend/alembic/versions/0002_clients.py:101-106` (FK ON DELETE RESTRICT named via `op.f`); `apps/backend/alembic/versions/0004_membership_plans.py:62-65` (`op.execute` for non-autogenerable index).
**Apply to:** `alembic/versions/0005_memberships.py`.

| Step | Detail |
|------|--------|
| 1 | FK declared in ORM via `ForeignKey("clients.id", ondelete="RESTRICT", name="fk_memberships_client_id_clients")` AND in migration via `sa.ForeignKeyConstraint(["client_id"], ["clients.id"], name=op.f("fk_memberships_client_id_clients"), ondelete="RESTRICT")`. |
| 2 | Plan-FK constraint name `fk_memberships_plan_id_membership_plans` is pinned for `_is_plan_in_use_conflict` literal-ref. |
| 3 | Composite resolver index installed via `op.execute("CREATE INDEX ix_memberships_client_id_status_end_date ON memberships (client_id, status, end_date DESC)")` because DESC ordering on a column expression may not autogenerate cleanly via SA. |
| 4 | If `alembic check` reports drift on the composite index, add `"ix_memberships_client_id_status_end_date"` to `env.py:_include_object` skip-tuple. |

---

## No Analog Found

None. Every Phase 17 file has a direct analog — either same-module (Phase 16 plans patterns extended in-place) or sibling-module (clients FK pattern) or core (Phase 4 D-24 register_user_loader slot). The closest "novel" surface is the state-machine guard (no prior in-codebase pattern), but its shape (free function, raises domain error before mutation) matches the existing "validate before mutate" idiom seen in Phase 8 phone validation and Phase 16 PATCH explicit-null guard.

---

## Metadata

**Analog search scope:**
- `apps/backend/app/modules/memberships/` (entire module — primary same-module template)
- `apps/backend/app/modules/clients/` (FK pattern, IntegrityError translation peer)
- `apps/backend/app/core/` (dependencies, exceptions, audit, schemas, pagination, database, permissions)
- `apps/backend/alembic/versions/0002_clients.py` (FK ON DELETE RESTRICT precedent)
- `apps/backend/alembic/versions/0004_membership_plans.py` (migration template)
- `apps/backend/alembic/env.py` (model registration + `_include_object` filter)
- `apps/backend/app/main.py` (composition-root carve-out template)
- `apps/backend/app/api/v1/router.py` (wiring target)
- `apps/backend/tests/integration/memberships/` (Phase 16 test templates + conftest extension target)
- `apps/backend/tests/unit/test_service_commit_gate.py` (Phase 16 already extends `_INSPECTED_SERVICES` to include memberships — no further change needed)

**Files scanned:** 18 source/test files + 4 migrations + 5 core modules + 2 config files. Targeted reads with non-overlapping ranges; 0 re-reads.

**Pattern extraction date:** 2026-05-07.

**Phase 17 EXTENDS the existing memberships module** — Phase 16 shipped plans-only; Phase 17 adds the `Membership` ORM, instance schemas/repo/service, 4 endpoints, the FK migration, and the resolver slot. The clients module is a peer reference (FK + IntegrityError translation); Phase 16 same-module is the primary template (write-path orchestration, DTO patterns, test layout).

**Constraint name registry** (literal-referenced strings — pin in migration):
- `fk_memberships_plan_id_membership_plans` — service.py `_is_plan_in_use_conflict`.
- `fk_memberships_client_id_clients` — not literal-ref'd but pinned for symmetry.
- `ck_memberships_status` — pinned via NAMING_CONVENTION.
- `ck_memberships_activation_policy` — pinned via NAMING_CONVENTION.
- `ix_memberships_client_id_status_end_date` — referenced by name in `op.execute` (and possibly `env.py` skip-tuple).
