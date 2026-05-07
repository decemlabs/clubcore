# Phase 16: Membership Plans Catalog (backend) - Pattern Map

**Mapped:** 2026-05-07
**Files analyzed:** 17 (5 new module files + 1 module-init replace + 1 migration + 3 wiring modifies + 6 new tests + 1 unit test modify)
**Analogs found:** 17 / 17 (every artifact has a direct clients-module template)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/backend/app/modules/memberships/models.py` | model | request-response (ORM) | `apps/backend/app/modules/clients/models.py` | exact |
| `apps/backend/app/modules/memberships/schemas.py` | schemas (DTO) | request-response | `apps/backend/app/modules/clients/schemas.py` | exact |
| `apps/backend/app/modules/memberships/repository.py` | repository | CRUD | `apps/backend/app/modules/clients/repository.py` | exact |
| `apps/backend/app/modules/memberships/service.py` | service | CRUD + audit | `apps/backend/app/modules/clients/service.py` | exact |
| `apps/backend/app/modules/memberships/router.py` | router (controller) | request-response | `apps/backend/app/modules/clients/router.py` | exact |
| `apps/backend/app/modules/memberships/__init__.py` (replace) | module-init | n/a | `apps/backend/app/modules/clients/__init__.py` | exact |
| `apps/backend/alembic/versions/0004_membership_plans.py` | migration | DDL | `apps/backend/alembic/versions/0002_clients.py` | exact |
| `apps/backend/app/api/v1/router.py` (modify) | wiring | request-response | self (existing `clients_router` include) | exact (extension) |
| `apps/backend/app/core/exceptions.py` (modify) | exception | n/a | self (existing `PhoneExistsError`) | exact (extension) |
| `apps/backend/alembic/env.py` (modify) | config | n/a | self (existing `_include_object` filter) | exact (extension) |
| `apps/backend/tests/unit/test_service_commit_gate.py` (modify) | test (AST gate) | n/a | self (existing `_CLIENTS_SERVICE` constant) | exact (extension) |
| `apps/backend/tests/integration/memberships/conftest.py` | test fixture | n/a | `apps/backend/tests/integration/clients/conftest.py` | exact |
| `apps/backend/tests/integration/memberships/test_plans_crud.py` | test (integration) | request-response | `apps/backend/tests/integration/clients/test_clients_crud.py` | exact |
| `apps/backend/tests/integration/memberships/test_plans_list.py` | test (integration) | request-response | `apps/backend/tests/integration/clients/test_clients_list.py` | exact |
| `apps/backend/tests/integration/memberships/test_plans_rbac.py` | test (integration) | request-response | `apps/backend/tests/integration/clients/test_clients_rbac.py` | exact |
| `apps/backend/tests/integration/memberships/test_audit_writes.py` | test (integration) | request-response + DB read | `apps/backend/tests/integration/clients/test_audit_writes.py` | exact |
| `apps/backend/tests/unit/memberships/test_schemas.py` | test (unit) | n/a | `apps/backend/tests/unit/test_schemas.py` (+ schemas.py validators) | role-match |

---

## Pattern Assignments

### `app/modules/memberships/models.py` (model, ORM)

**Analog:** `apps/backend/app/modules/clients/models.py`

**Imports + module docstring pattern** (lines 1-48): the docstring announces the mixin composition (`Base + UUIDPkMixin + TimestampMixin + SoftDeleteMixin`), enumerates DB-level invariants (CHECK / partial-unique), and documents which indexes are NOT autogenerable (Phase 16's `lower(name) WHERE deleted_at IS NULL` partial-unique is the same class as clients' GIN trgm indexes — declare in `__table_args__` for ORM awareness, install via raw `op.execute(...)` in the migration, suppress in `env.py:_include_object`).

**Mixin composition** (lines 58-61):
```python
class Client(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin):
    """Gym client / member (CLIENTS-01)."""
    __tablename__ = "clients"
```
Phase 16 produces `class MembershipPlan(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin): __tablename__ = "membership_plans"`.

**Column declarations + `__table_args__` partial-unique** (lines 63-111):
```python
last_name: Mapped[str] = mapped_column(Text, nullable=False)
# ...
__table_args__ = (
    CheckConstraint("gender IN ('male', 'female')", name="ck_clients_gender"),
    UniqueConstraint("telegram_user_id", name="uq_clients_telegram_user_id"),
    Index(
        "uq_clients_phone_alive",
        "phone",
        unique=True,
        postgresql_where=text("deleted_at IS NULL"),
    ),
)
```
Phase 16 columns: `name VARCHAR(120) NOT NULL`, `duration_days INT NOT NULL`, `price_kopecks BIGINT NOT NULL`, `active BOOL NOT NULL DEFAULT TRUE`. `__table_args__` carries (a) `CheckConstraint("duration_days > 0", name="ck_membership_plans_duration_days_positive")`, (b) `CheckConstraint("price_kopecks >= 0", name="ck_membership_plans_price_kopecks_nonneg")`, (c) `Index("uq_membership_plans_name_alive", text("lower(name)"), unique=True, postgresql_where=text("deleted_at IS NULL"))` — note this is an EXPRESSION partial unique (`lower(name)`), so SA autogenerate cannot represent it; only the migration's `op.execute(...)` actually installs it (see `env.py` modify below).

---

### `app/modules/memberships/schemas.py` (DTO, request-response)

**Analog:** `apps/backend/app/modules/clients/schemas.py`

**Module-level constants + sort enum** (lines 38-55):
```python
PHONE_REGEX = r"^\+[1-9]\d{1,14}$"  # E.164 (D-10)
# ...
class ClientSort(StrEnum):
    CREATED_AT_DESC = "created_at_desc"
    LAST_NAME_ASC = "last_name_asc"
```
Phase 16 declares `class MembershipPlanSort(StrEnum): CREATED_AT_DESC = "created_at_desc"; NAME_ASC = "name_asc"` (D-08, CD-04 — module-local, mirrors `ClientSort`).

**Create DTO + field-level bounds** (lines 105-125):
```python
class ClientCreateRequest(BackendSchemaBase):
    last_name: str = Field(min_length=1, max_length=128)
    # ...
    @field_validator("tags")
    @classmethod
    def _normalise_tags(cls, v: list[str]) -> list[str]:
        return _validate_tags(v)
```
Phase 16 `MembershipPlanCreateRequest(BackendSchemaBase)` carries:
```python
name: str = Field(min_length=1, max_length=120)
duration_days: int = Field(ge=1, le=3650)        # D-06
price_kopecks: int = Field(ge=0, le=10**11)       # D-06
active: bool = Field(default=True)                # D-06

@field_validator("name", mode="before")
@classmethod
def _trim(cls, v: object) -> object:              # D-01: trim only, preserve casing
    return v.strip() if isinstance(v, str) else v
```

**Update DTO + explicit-null reject + extra='forbid' inheritance** (lines 132-171):
```python
class ClientUpdateRequest(BackendSchemaBase):
    last_name: str | None = Field(default=None, min_length=1, max_length=128)
    # ...
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
Phase 16 `MembershipPlanUpdateRequest(BackendSchemaBase)` declares ONLY `name`, `price_kopecks`, `active` (D-04: NO `duration_days` field — `BackendSchemaBase`'s `extra='forbid'` produces a stock 422 for any payload with `durationDays`). Same `_reject_explicit_null` model validator (D-05). Same `_trim` field validator on `name` (D-01).

**Response DTO** (lines 179-201):
```python
class ClientResponse(ResponseData):
    id: UUID
    last_name: str
    # ...
    created_at: datetime
    updated_at: datetime
```
Phase 16 `MembershipPlanResponse(ResponseData)`: `id, name, duration_days, price_kopecks, active, created_at, updated_at`. `deleted_at` deliberately omitted (soft-deleted rows are 404'd at the repository boundary).

**ListQuery DTO inheriting `PageQuery`** (lines 209-262):
```python
class ClientListQuery(PageQuery):
    q: str | None = Field(default=None, max_length=128)
    # ...
    sort: ClientSort = ClientSort.CREATED_AT_DESC
```
Phase 16 `MembershipPlanListQuery(PageQuery)`:
```python
active: bool | None = None                                # D-08: optional filter
sort: MembershipPlanSort = MembershipPlanSort.CREATED_AT_DESC
```
**No `q` field** (D-09). **No `?includeArchived` flag** (D-08).

---

### `app/modules/memberships/repository.py` (repository, CRUD)

**Analog:** `apps/backend/app/modules/clients/repository.py`

**Module docstring + `from __future__ import annotations`** (lines 1-26):
```python
"""Clients repository — single point of access to the `Client` ORM ..."""
from __future__ import annotations
```
Phase 16 inherits the `from __future__ import annotations` requirement verbatim — its `list_alive` returns `PaginatedData[MembershipPlan]` and the same `PydanticSchemaGenerationError` would fire without PEP 563 deferred evaluation (clients/repository.py:18-23 explains the rationale).

**`get_alive` pattern** (lines 47-54):
```python
async def get_alive(session: AsyncSession, client_id: UUID) -> Client | None:
    stmt: Select[tuple[Client]] = select(Client).where(
        Client.id == client_id,
        Client.deleted_at.is_(None),
    )
    result: Client | None = await session.scalar(stmt)
    return result
```
Phase 16 `get_alive(session, plan_id) -> MembershipPlan | None` is identical with `MembershipPlan` substituted.

**`list_alive` pattern (predicate accumulation + PaginatedData.model_construct)** (lines 57-139):
```python
predicates: list[Any] = [Client.deleted_at.is_(None)]
# ... conditional appends ...
total_stmt = select(func.count()).select_from(Client).where(and_(*predicates))
total = await session.scalar(total_stmt) or 0
stmt: Select[tuple[Client]] = select(Client).where(and_(*predicates))
if query.sort == ClientSort.LAST_NAME_ASC:
    stmt = stmt.order_by(Client.last_name.asc(), Client.created_at.desc())
else:  # default CREATED_AT_DESC
    stmt = stmt.order_by(Client.created_at.desc(), Client.id.desc())
offset = (query.page - 1) * query.page_size
stmt = stmt.offset(offset).limit(query.page_size)
rows = (await session.scalars(stmt)).all()
return PaginatedData.model_construct(
    items=list(rows), total=total, page=query.page, page_size=query.page_size,
)
```
Phase 16 mirrors this verbatim. `if query.active is not None: predicates.append(MembershipPlan.active == query.active)` is the only feature filter (D-08). Sort: `NAME_ASC → order_by(func.lower(MembershipPlan.name).asc(), MembershipPlan.created_at.desc())`; default → `order_by(MembershipPlan.created_at.desc(), MembershipPlan.id.desc())`. **No `q` ILIKE branch** (D-09 — drop everything below the predicate-list base append).

**`insert_<entity>` — caller owns flush** (lines 142-165):
```python
async def insert_client(session, actor_user_id, data) -> Client:
    client = Client(last_name=..., ..., created_by_user_id=actor_user_id)
    session.add(client)
    return client
```
Phase 16 `insert_plan(session, data: MembershipPlanCreateRequest) -> MembershipPlan` — note no `actor_user_id` parameter (plans have no `created_by_user_id` per CONTEXT.md `<domain>` MEM-PLAN-01 column list).

**`update_<entity>` returns `changed_previous: dict`** (lines 168-197):
```python
async def update_client(session, client, data) -> dict[str, object]:
    updates = data.model_dump(exclude_unset=True)
    changed: dict[str, object] = {}
    for key, value in updates.items():
        previous = getattr(client, key)
        if previous != value:
            changed[key] = previous
            setattr(client, key, value)
    return changed
```
Phase 16 `update_plan(session, plan, data: MembershipPlanUpdateRequest) -> dict[str, object]` is identical (no `EmergencyContact` JSONB special-case). The keys can only be `name | price_kopecks | active` because `MembershipPlanUpdateRequest` declares no other writable fields.

**`soft_delete_<entity>`** (lines 200-203):
```python
async def soft_delete_client(session: AsyncSession, client: Client) -> Client:
    client.deleted_at = datetime.now(tz=UTC)
    return client
```
Phase 16 `soft_delete_plan(session, plan) -> MembershipPlan` is identical.

---

### `app/modules/memberships/service.py` (service, CRUD + audit + commit)

**Analog:** `apps/backend/app/modules/clients/service.py`

**Module docstring** (lines 1-38) — copy verbatim with substitutions: clients→memberships, phone→plan-name, CLIENTS-09→MEM-PLAN, D-08 audit shapes adjusted to D-11/D-12/D-13 from CONTEXT.md.

**`_is_<conflict>` IntegrityError discriminator** (lines 99-104):
```python
def _is_phone_conflict(exc: IntegrityError) -> bool:
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "uq_clients_phone_alive":
        return True
    return "uq_clients_phone_alive" in str(exc.orig)
```
Phase 16 ports verbatim as `_is_plan_name_conflict(exc)` checking `uq_membership_plans_name_alive` (D-02).

**Create write-path with IntegrityError translation + commit** (lines 107-142):
```python
async def create_client(session, actor, data) -> ClientResponse:
    client = await repository.insert_client(session, actor.id, data)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_phone_conflict(exc):
            raise PhoneExistsError("phone_exists") from exc
        raise
    await audit.emit(
        session, "client_created",
        actor_user_id=actor.id,
        resource_type="client",
        resource_id=client.id,
        full_name=_full_name(client), phone=client.phone,
        has_email=client.email is not None,
        has_telegram=client.telegram_user_id is not None,
    )
    await session.commit()
    return ClientResponse.model_validate(client)
```
Phase 16 `create_plan` flow (D-14):
1. `plan = await repository.insert_plan(session, data)`
2. `try: await session.flush() except IntegrityError as exc: rollback; if _is_plan_name_conflict(exc): raise PlanNameExistsError(...) from exc; raise`
3. `await audit.emit(session, "membership_plan_created", actor_user_id=actor.id, resource_type="membership_plan", resource_id=plan.id, name=plan.name, duration_days=plan.duration_days, price_kopecks=plan.price_kopecks)` (D-11 payload)
4. `await session.commit()`
5. `return MembershipPlanResponse.model_validate(plan)`
**Both event-name string and `resource_type` string MUST be literals** (Phase 15 D-11 step 3 / `tests/unit/test_audit_taxonomy.py`).

**Update write-path with no-op skip + early flush + refresh** (lines 145-200):
```python
async def update_client(session, actor, client_id, data) -> ClientResponse:
    client = await repository.get_alive(session, client_id)
    if client is None:
        raise ClientNotFoundError("client_not_found")
    changed_previous = await repository.update_client(session, client, data)
    if not changed_previous:
        return ClientResponse.model_validate(client)        # D-09 idempotent no-op
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_phone_conflict(exc):
            raise PhoneExistsError("phone_exists") from exc
        raise
    payload: dict[str, object] = {"changed_fields": sorted(changed_previous.keys())}
    if "phone" in changed_previous:
        payload["previous_phone"] = changed_previous["phone"]
    await audit.emit(session, "client_updated", actor_user_id=actor.id,
                     resource_type="client", resource_id=client.id, **payload)
    await session.refresh(client, attribute_names=["updated_at"])
    await session.commit()
    return ClientResponse.model_validate(client)
```
Phase 16 `update_plan`: identical control flow; payload is `{"changed_fields": sorted(changed_previous.keys())}` — **no previous-value capture for any field** (D-12). `PlanNotFoundError` replaces `ClientNotFoundError`. `PlanNameExistsError` replaces `PhoneExistsError`. `await session.refresh(plan, attribute_names=["updated_at"])` retained for the same MissingGreenlet reason.

**Soft-delete write-path with capture-before-mutate + emit-before-flush** (lines 203-236):
```python
async def soft_delete_client(session, actor, client_id) -> None:
    client = await repository.get_alive(session, client_id)
    if client is None:
        raise ClientNotFoundError("client_not_found")
    captured_full_name = _full_name(client)
    captured_phone = client.phone
    await repository.soft_delete_client(session, client)
    await audit.emit(session, "client_soft_deleted", ...,
                     full_name=captured_full_name, phone=captured_phone)
    await session.flush()
    await session.commit()
```
Phase 16 `soft_delete_plan(session, actor, plan_id) -> None` (D-14):
- get → 404 if missing → `await repository.soft_delete_plan(session, plan)` (mutate `deleted_at`) → `await audit.emit(session, "membership_plan_archived", actor_user_id=actor.id, resource_type="membership_plan", resource_id=plan.id)` (D-13: payload only carries `plan_id` via `resource_id`; no extra fields) → `await session.flush()` → `await session.commit()`.
- **NO `_full_name`-style helper** — plans have a single `name` and the audit row's `resource_id` already pins it.

**`list` + `get` read-side stubs** (lines 62-88) — no audit, no commit, just `repository.<fn>` + `model_validate`. Phase 16 `list_plans` and `get_plan` are direct mirrors.

---

### `app/modules/memberships/router.py` (router, request-response)

**Analog:** `apps/backend/app/modules/clients/router.py`

**Imports + RBAC-04 ordering rationale** (lines 1-49) — copy module docstring verbatim with substitutions; the RBAC-04 ordering invariant (`require_permission` BEFORE `verify_csrf`) is mandatory and tested by `tests/integration/test_route_introspection.py`.

**GET list endpoint** (lines 52-66):
```python
@router.get(
    "",
    response_model=ResponseEnvelope[PaginatedData[ClientResponse]],
    summary="List alive clients with filters and pagination",
)
async def list_clients(
    query: Annotated[ClientListQuery, Depends()],
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.CLIENTS))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[ClientResponse]]:
    page = await service.list_clients(session, query)
    return envelope(page)
```
Phase 16: same shape. Substitute `Resource.CLIENTS` → `Resource.MEMBERSHIP_PLANS` (already in `OWNER_ONLY` per Phase 15). Note: GET list is OWNER-only because `(VIEW, MEMBERSHIP_PLANS)` is in `OWNER_ONLY` per CONTEXT.md `<domain>` line 19 — this differs from clients (where VIEW is shared between owner+reception).

**POST create endpoint with CSRF** (lines 86-103):
```python
@router.post(
    "",
    response_model=ResponseEnvelope[ClientResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new client (E.164 phone; 409 phone_exists ...)",
)
async def create_client(
    payload: ClientCreateRequest,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.EDIT, Resource.CLIENTS))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientResponse]:
    client = await service.create_client(session, actor, payload)
    return envelope(client)
```
Phase 16 substitutes `Action.EDIT, Resource.CLIENTS` → `Action.CREATE, Resource.MEMBERSHIP_PLANS` (CONTEXT.md `<domain>` line 19 explicitly lists `CREATE` for plans, distinct from clients which uses `EDIT`).

**PATCH update endpoint** (lines 105-121): same shape. Phase 16 uses `Action.EDIT, Resource.MEMBERSHIP_PLANS`.

**DELETE soft-delete with 204** (lines 124-144):
```python
@router.delete(
    "/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a client (owner-only; sets deleted_at, never hard-deletes)",
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
Phase 16 mirrors verbatim with `Resource.MEMBERSHIP_PLANS` and path param `plan_id`.

---

### `app/modules/memberships/__init__.py` (replace placeholder)

**Analog:** `apps/backend/app/modules/clients/__init__.py`
```python
"""Clients module (Phase 8)."""
```
Phase 16 replaces the existing single-line placeholder docstring with `"""Memberships module — plan catalog (Phase 16)."""`. No imports — module surface is consumed via explicit `from app.modules.memberships.router import router as plans_router` at the wiring site.

---

### `alembic/versions/0004_membership_plans.py` (migration, DDL)

**Analog:** `apps/backend/alembic/versions/0002_clients.py`

**Revision header** (lines 1-34):
```python
"""clients_and_audit_log
Revision ID: 0002_clients
Revises: 0003_telegram_username
Create Date: 2026-05-03 08:45:00.000000
...
"""
revision: str = "0002_clients"
down_revision: str | None = "0003_telegram_username"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```
Phase 16: `revision = "0004_membership_plans"`, `down_revision = "0002_clients"` (CONTEXT.md `<specifics>` line 223 — current head, the `0003_telegram_username` is upstream of `0002_clients` per the existing `0002_clients` `down_revision` field).

**`op.create_table` shape** (lines 42-107) — Phase 16 emits:
```python
op.create_table(
    "membership_plans",
    sa.Column("name", sa.String(length=120), nullable=False),
    sa.Column("duration_days", sa.Integer(), nullable=False),
    sa.Column("price_kopecks", sa.BigInteger(), nullable=False),
    sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("duration_days > 0", name=op.f("ck_membership_plans_duration_days_positive")),
    sa.CheckConstraint("price_kopecks >= 0", name=op.f("ck_membership_plans_price_kopecks_nonneg")),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_membership_plans")),
)
```
**No FK to users** (plans have no `created_by_user_id`). **No `pg_trgm` extension** (D-09 — no name search).

**Partial-unique expression index via raw `op.execute`** (lines 109-127, the GIN trgm precedent):
```python
op.execute(
    "CREATE INDEX ix_clients_last_name_trgm "
    "ON clients USING gin (lower(last_name) gin_trgm_ops)"
)
```
Phase 16 — the partial-unique on `lower(name)` is also an expression index that SA cannot represent, so install via:
```python
op.execute(
    "CREATE UNIQUE INDEX uq_membership_plans_name_alive "
    "ON membership_plans (lower(name)) WHERE deleted_at IS NULL"
)
```
Document the exact name `uq_membership_plans_name_alive` in a comment — `_is_plan_name_conflict` in `service.py` references it as a literal string (CONTEXT.md `<specifics>` line 224).

**`downgrade()`** (lines 171-181): drop the partial-unique by name first (`op.execute("DROP INDEX IF EXISTS uq_membership_plans_name_alive")`), then `op.drop_table("membership_plans")`. NO `DROP EXTENSION` (we never created one).

---

### `app/api/v1/router.py` (modify — wiring)

**Analog:** the existing two-line wiring pattern in the same file (lines 10-15):
```python
from app.modules.auth.router import router as auth_router
from app.modules.clients.router import router as clients_router

v1 = APIRouter()
v1.include_router(auth_router, prefix="/auth", tags=["auth"])
v1.include_router(clients_router, prefix="/clients", tags=["clients"])
```
Phase 16 modify — append:
```python
from app.modules.memberships.router import router as plans_router
# ...
v1.include_router(plans_router, prefix="/membership-plans", tags=["membership-plans"])
```
Prefix is kebab-case `/membership-plans` matching `Resource.MEMBERSHIP_PLANS = "membership-plans"` (CONTEXT.md `<code_context>` line 210).

---

### `app/core/exceptions.py` (modify — add `PlanNameExistsError` + `PlanNotFoundError`)

**Analog:** the existing clients-block in the same file (lines 81-99):
```python
class ClientNotFoundError(NotFoundError):
    code = "client_not_found"
    status_code = 404


class PhoneExistsError(ConflictError):
    code = "phone_exists"
    status_code = 409


class InvalidPhoneError(ValidationAppError):
    code = "invalid_phone"
    status_code = 422
```
Phase 16 modify — append (D-03 + D-14, plus the missing-id 404 path used by `update_plan`/`soft_delete_plan`):
```python
class PlanNotFoundError(NotFoundError):
    """Raised when GET/PATCH/DELETE references a non-existent or soft-deleted plan."""
    code = "plan_not_found"
    status_code = 404


class PlanNameExistsError(ConflictError):
    """Raised on POST/PATCH when name collides with an alive plan (Phase 16 D-02)."""
    code = "plan_name_exists"
    status_code = 409
```
**No `Invalid<X>Error` 422 — Pydantic stock 422 covers all bound violations** (D-04, D-06).

---

### `alembic/env.py` (modify — extend `_include_object` filter)

**Analog:** the existing filter in the same file (lines 41-65):
```python
def _include_object(object_, name, type_, reflected, compare_to) -> bool:
    return not (
        type_ == "index"
        and name in (
            "ix_clients_last_name_trgm",
            "ix_clients_first_name_trgm",
        )
    )
```
Phase 16 extends the tuple by one entry (CONTEXT.md `<code_context>` line 213):
```python
return not (
    type_ == "index"
    and name in (
        "ix_clients_last_name_trgm",
        "ix_clients_first_name_trgm",
        "uq_membership_plans_name_alive",
    )
)
```
Also ADD model registration in the `# Register all ORM models` block (lines 24-28):
```python
import app.modules.memberships.models  # noqa: F401
```

---

### `tests/unit/test_service_commit_gate.py` (modify — extend AST gate scope)

**Analog:** the existing scoping pattern in the same file (lines 167, 180-206):
```python
_CLIENTS_SERVICE = _BACKEND_APP / "modules" / "clients" / "service.py"
# ...
def test_service_commit_gate_against_app_modules() -> None:
    assert _CLIENTS_SERVICE.is_file(), ...
    offenders: list[str] = []
    for func in _iter_functions_in_file(_CLIENTS_SERVICE):
        msg = _check_function(_CLIENTS_SERVICE, func)
        if msg is not None:
            offenders.append(msg)
    assert not offenders, ...
```
Phase 16 modify (CONTEXT.md `<code_context>` line 214) — add `_MEMBERSHIPS_SERVICE = _BACKEND_APP / "modules" / "memberships" / "service.py"` and extend the live test to iterate both files (rename to `_INSPECTED_SERVICES = (_CLIENTS_SERVICE, _MEMBERSHIPS_SERVICE)` and loop). Update the docstring to remove the "narrowed to clients" caveat for these two modules.

---

### `tests/integration/memberships/conftest.py` (new)

**Analog:** `apps/backend/tests/integration/clients/conftest.py`

Copy-port verbatim. Substitute the two test-account email/password constants:
```python
OWNER_EMAIL = "clients-owner@example.com"
OWNER_PASSWORD = "hunter22hunter22"
RECEPTION_EMAIL = "clients-reception@example.com"
RECEPTION_PASSWORD = "hunter22hunter22"
```
Phase 16: `plans-owner@example.com` / `plans-reception@example.com` (or `memberships-...`). Both seeded users go through `_seed_user` + `/api/v1/auth/login` + ASGITransport identical to clients/conftest.py (lines 48-160). The `redis_clean`, `_client_app_overrides`, `authed_client_owner`, `authed_client_reception` fixtures port verbatim.

---

### `tests/integration/memberships/test_plans_crud.py` (new)

**Analog:** `apps/backend/tests/integration/clients/test_clients_crud.py`

**Boilerplate + helpers** (lines 27-50):
```python
def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf", "")}

VALID_CLIENT: dict[str, Any] = {
    "lastName": "Иванов", "firstName": "Иван", "phone": "+79991234567",
}

async def _create(authed_client_owner, **overrides) -> dict[str, Any]:
    payload: dict[str, Any] = {**VALID_CLIENT, **overrides}
    r = await authed_client_owner.post("/api/v1/clients", json=payload, headers=_csrf_headers(authed_client_owner))
    assert r.status_code == 201, r.text
    return r.json()["data"]
```
Phase 16:
```python
VALID_PLAN: dict[str, Any] = {
    "name": "Базовый",
    "durationDays": 30,
    "priceKopecks": 250000,
    "active": True,
}
# _create posts to /api/v1/membership-plans
```

**409 conflict test** (lines 84-97) — port to "duplicate name" 409 `plan_name_exists` (D-02 + CONTEXT.md `<specifics>` lines 230). Pair with the marquee `test_delete_frees_unique_name_slot` (CONTEXT.md `<specifics>` line 230): create "Базовый" → DELETE → re-create "Базовый" → 201.

**Stock 422 for `durationDays` in PATCH** (CONTEXT.md `<specifics>` line 231 + D-04):
```python
r = await authed_client_owner.patch(
    f"/api/v1/membership-plans/{plan_id}",
    json={"durationDays": 90},
    headers=_csrf_headers(authed_client_owner),
)
assert r.status_code == 422
assert "durationDays" in r.text  # Pydantic's stock "Extra inputs are not permitted"
```

**404-after-soft-delete + idempotent no-op PATCH** ports verbatim from clients/test_clients_crud.py.

---

### `tests/integration/memberships/test_plans_list.py` (new)

**Analog:** `apps/backend/tests/integration/clients/test_clients_list.py`

**Envelope shape assertion** (lines 42-58):
```python
r = await authed_client_owner.get("/api/v1/clients")
body = r.json()
assert isinstance(data["items"], list)
assert data["total"] == 3
assert data["page"] == 1
assert data["pageSize"] == 20
```
Phase 16 ports verbatim against `/api/v1/membership-plans`. **Drop all `?q=` / tag / gender / dateRange / hasTelegram tests** (D-09 — none exist on plans). Replace with:
- `?active=true` filter
- `?active=false` filter
- omit `active` → both active and inactive (alive) returned
- sort=`name_asc` orders by `func.lower(name)` (test with mixed-case names verifies the case-insensitive sort)
- sort default = `created_at_desc`
- pagination boundary: page=2 with 21+ items returns the overflow.

---

### `tests/integration/memberships/test_plans_rbac.py` (new)

**Analog:** `apps/backend/tests/integration/clients/test_clients_rbac.py`

**Owner-403 test** (lines 54-65):
```python
async def test_delete_reception_returns_403_forbidden(authed_client_owner, authed_client_reception):
    created = await _create(authed_client_owner, phone="+79990001002")
    r = await authed_client_reception.delete(
        f"/api/v1/clients/{created['id']}",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"
```
Phase 16: ALL FOUR endpoints return 403 for reception (the entire `MEMBERSHIP_PLANS` resource is in `OWNER_ONLY`). Test matrix: GET list, POST, PATCH, DELETE — each as reception → 403 `forbidden`. Plus: unauth canary on each → 401 (RBAC-04 auth-before-rbac ordering invariant).

---

### `tests/integration/memberships/test_audit_writes.py` (new)

**Analog:** `apps/backend/tests/integration/clients/test_audit_writes.py`

**Audit row read pattern** (lines 56-65):
```python
rows = (
    await db_session.scalars(
        select(AuditLog).where(
            AuditLog.action == "client_created",
            AuditLog.resource_id == client_id,
        )
    )
).all()
assert len(rows) == 1
row = rows[0]
assert row.actor_user_id == seeded_owner.id
assert row.resource_type == "client"
```
Phase 16 ports verbatim. Three test cases:
1. POST → `membership_plan_created` row with payload `{name, duration_days, price_kopecks}` (D-11) + `resource_type == "membership_plan"`. Note: `plan_id` lives in `resource_id` column, NOT in payload.
2. PATCH `{priceKopecks: 300000}` → `membership_plan_updated` row with `payload["changed_fields"] == ["price_kopecks"]` and **NO `previous_price_kopecks`** key (D-12 — no before/after values).
3. DELETE → `membership_plan_archived` row with **empty payload** (or `{}` — D-13, only `resource_id` carries the plan id).
4. **No-op PATCH writes ZERO audit rows** (D-14 update step 2 + clients D-09 idempotent no-op test pattern).

---

### `tests/unit/memberships/test_schemas.py` (new)

**Analog:** `apps/backend/tests/unit/test_schemas.py` (general schema unit tests) + the validators in `clients/schemas.py:152-171` are the patterns under test.

Tests Phase 16 must include (CONTEXT.md `<specifics>` line 231):
- `MembershipPlanCreateRequest` accepts trimmed name; rejects post-trim empty (`"   "` → 422 from `min_length=1`).
- `MembershipPlanCreateRequest` rejects `duration_days=0` (D-06: `ge=1`); `duration_days=3651` (D-06: `le=3650`).
- `MembershipPlanCreateRequest` rejects `price_kopecks=-1` (D-06: `ge=0`); `price_kopecks=10**11+1` (D-06: `le=10**11`).
- `MembershipPlanUpdateRequest` rejects `{"durationDays": 90}` with stock 422 "Extra inputs are not permitted" (D-04).
- `MembershipPlanUpdateRequest` rejects `{"name": null}` with the explicit-null guard message (D-05).
- Wire camelCase ↔ Python snake_case alias_generator pair-test (`durationDays ↔ duration_days`, `priceKopecks ↔ price_kopecks`).

---

## Shared Patterns

### Authentication / Authorization
**Source:** `apps/backend/app/core/dependencies.py` — `CurrentUser`, `require_permission`, `verify_csrf`, `get_db`.
**Source pattern (router):** `apps/backend/app/modules/clients/router.py` lines 92-101.
**Apply to:** every endpoint in `app/modules/memberships/router.py`.

```python
actor: Annotated[CurrentUser, Depends(require_permission(Action.<X>, Resource.MEMBERSHIP_PLANS))],
_csrf: Annotated[None, Depends(verify_csrf)],     # only on POST / PATCH / DELETE
session: Annotated[AsyncSession, Depends(get_db)],
```
RBAC-04 ordering: `Depends(require_permission(...))` MUST be declared in the function signature BEFORE `Depends(verify_csrf)` (clients/router.py:18-19 explains; `tests/integration/test_route_introspection.py` enforces).

### IntegrityError → DomainError translation
**Source:** `apps/backend/app/modules/clients/service.py` lines 99-126.
**Apply to:** `service.create_plan` (full IntegrityError path) and `service.update_plan` (only when `name in changed_previous`, mirror clients D-11 early-flush).

```python
def _is_plan_name_conflict(exc: IntegrityError) -> bool:
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "uq_membership_plans_name_alive":
        return True
    return "uq_membership_plans_name_alive" in str(exc.orig)

try:
    await session.flush()
except IntegrityError as exc:
    await session.rollback()
    if _is_plan_name_conflict(exc):
        raise PlanNameExistsError("plan_name_exists") from exc
    raise
```

### Audit emit + commit
**Source:** `apps/backend/app/modules/clients/service.py` lines 130-141, 186-199, 226-236.
**Apply to:** every write path in `service.py`.

- `audit.emit(session, "<event>", actor_user_id=actor.id, resource_type="<resource>", resource_id=<id>, **payload)` — both event-name and resource_type strings MUST be string literals (Phase 15 D-11 step 3 / `tests/unit/test_audit_taxonomy.py` AST walker enforces; typo defence per CONTEXT.md `<specifics>` line 226).
- `await session.commit()` MUST appear at the end of every write path (Phase 15 INFRA-13 AST gate / `tests/unit/test_service_commit_gate.py`).
- Update path: `await session.refresh(entity, attribute_names=["updated_at"])` BEFORE commit so Pydantic serialisation sees the fresh server-side timestamp without a MissingGreenlet lazy-load (clients/service.py:194-198 explains).

### PATCH semantics (omit-key + explicit-null reject)
**Source:** `apps/backend/app/modules/clients/schemas.py` lines 152-163.
**Apply to:** `MembershipPlanUpdateRequest`.
The `model_validator(mode="before")` walks the inbound dict and raises `ValueError(f"Explicit null not supported for: {sorted(null_keys)}. Omit the key to leave the field unchanged.")` if any value is `None` (D-05). FastAPI surfaces this as 422.

### Repository idempotent no-op
**Source:** `apps/backend/app/modules/clients/service.py` lines 162-166.
**Apply to:** `service.update_plan`.
```python
if not changed_previous:
    return MembershipPlanResponse.model_validate(plan)   # skip emit + flush + commit
```

### Soft-delete invariant
**Source:** `apps/backend/app/modules/clients/repository.py` lines 47-54, 200-203.
**Apply to:** every read in `repository.py` (`Client.deleted_at.is_(None)` predicate is FIRST in the predicate list).
- `get_alive` filters `deleted_at IS NULL`.
- `list_alive` seeds `predicates: list[Any] = [MembershipPlan.deleted_at.is_(None)]` BEFORE any conditional filter.
- `soft_delete_plan` is the ONLY mutation that touches `deleted_at`.

### Test fixture chain
**Source:** `apps/backend/tests/integration/conftest.py` (root) + `apps/backend/tests/integration/clients/conftest.py`.
**Apply to:** `tests/integration/memberships/conftest.py`.
- `db_session` SAVEPOINT-mode fixture comes from the root conftest (do not redefine).
- `redis_clean`, `_client_app_overrides`, `seeded_owner`, `seeded_reception`, `authed_client_owner`, `authed_client_reception` are local-to-folder and copy-ported with email substitutions only.
- Cookies: login flow seeds `sz_access`, `sz_refresh`, `sportzal_csrf` — every mutation test reads `client.cookies.get("sportzal_csrf", "")` for the `X-CSRF-Token` header (clients/test_clients_crud.py lines 27-28).

### Migration partial-unique on expression
**Source:** `apps/backend/alembic/versions/0002_clients.py` lines 109-127.
**Apply to:** `alembic/versions/0004_membership_plans.py` AND `alembic/env.py:_include_object`.

| Step | Detail |
|------|--------|
| 1 | Declare in ORM `__table_args__` for type awareness — `Index("uq_membership_plans_name_alive", text("lower(name)"), unique=True, postgresql_where=text("deleted_at IS NULL"))`. |
| 2 | Install in migration via raw `op.execute("CREATE UNIQUE INDEX uq_membership_plans_name_alive ON membership_plans (lower(name)) WHERE deleted_at IS NULL")`. |
| 3 | Suppress autogenerate drift in `env.py:_include_object` by adding `"uq_membership_plans_name_alive"` to the skip-tuple. |

---

## No Analog Found

None. Every Phase 16 file has a direct, exact, or extension-only analog in the existing codebase. The clients module is the canonical template (CONTEXT.md `<code_context>` line 186: "~85% of the file shape transfers directly").

---

## Metadata

**Analog search scope:**
- `apps/backend/app/modules/clients/` (entire module — primary template)
- `apps/backend/app/core/` (exceptions, dependencies, schemas, audit, pagination, database)
- `apps/backend/alembic/versions/` (0001, 0002, 0003)
- `apps/backend/alembic/env.py`
- `apps/backend/tests/integration/clients/` (entire folder — test template)
- `apps/backend/tests/unit/test_service_commit_gate.py` (modify target)
- `apps/backend/app/api/v1/router.py` (wiring target)

**Files scanned:** 17 source/test files read with targeted excerpts; 0 re-reads.
**Pattern extraction date:** 2026-05-07.
**Memberships placeholder confirmed empty:** `apps/backend/app/modules/memberships/__init__.py` is a single-line docstring.
