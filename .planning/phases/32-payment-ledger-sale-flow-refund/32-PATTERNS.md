# Phase 32: Payment Ledger + Sale Flow + Refund — Pattern Map

**Mapped:** 2026-05-15
**Files analyzed:** 26 (15 CREATE + 11 MODIFY)
**Analogs found:** 26 / 26

This document tells the planner exactly which existing file each new/modified Phase 32 file should copy patterns from, with concrete excerpts and line numbers. The planner consumes these as the "Analog" reference in every plan's action sections.

---

## File Classification

### CREATE

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `apps/backend/alembic/versions/0012_payments.py` | migration | DDL / schema-evolution | `0008_freeze.py` (multi-op: ADD COL + CREATE TABLE + partial UNIQUE) | exact (multi-op shape + partial UNIQUE precedent) |
| `apps/backend/app/core/audit_hash.py` | utility (core helper) | pure function (no I/O) | `apps/backend/app/core/audit_payloads.py` (core, no `app.modules.*` import) | role-match (core boundary discipline) |
| `apps/backend/app/core/idempotency.py` | middleware (per-route Depends) | request-response (header check + Redis cache) | `app/core/dependencies.py:verify_csrf` (per-route header check) + `app/core/redis.py:get_redis` (Redis dep) | exact (verify_csrf shape) |
| `apps/backend/app/modules/payments/router.py` | controller (router) | request-response (3 GET endpoints) | `app/modules/trainers/router.py` (router with VIEW + RBAC + envelope) + `memberships/router.py` (multi-router file pattern) | exact (list+detail GET shape) |
| `apps/backend/app/modules/payments/service.py` | service | CRUD (insert + read; append-only — NO update/delete) | `app/modules/trainers/service.py:create_trainer` (insert+flush+IntegrityError→AppError+audit+commit) + `memberships/service.py:freeze_membership` (orchestrator with status guard) | exact (insert flow); caller-owns-txn variant differs |
| `apps/backend/app/modules/payments/repository.py` | repository | CRUD (insert + list) | `app/modules/memberships/repository.py:insert_membership` + `insert_freeze_period` + `_is_already_frozen_conflict` discriminator | exact (insert + constraint-name 409 mapping) |
| `apps/backend/app/modules/payments/schemas.py` | schema (Pydantic DTO) | wire format (camelCase) | `app/modules/trainers/schemas.py` (Create/Update/Response/ListQuery) + `memberships/schemas.py:MembershipCancelRequest` (reason field) | exact (DTO shape); `extra='forbid'` override is `BackendSchemaBase` default |
| `apps/backend/app/modules/payments/permissions.py` | permissions stub (router-level scoped guards) | request-response (Depends factory) | `app/core/dependencies.py:require_permission` (factory returning `_checker`) | role-match (factory shape) |
| `apps/backend/app/modules/payments/constants.py` | constants | static literals | `app/modules/memberships/constants.py:MEMBERSHIP_STATUS_TRANSITIONS` (`MappingProxyType` + frozensets + tuple) | exact (constants module shape) |
| `apps/backend/tests/integration/test_payments_sale.py` | test (integration) | request-response | `tests/integration/memberships/test_freeze_endpoints.py` (200/409 path coverage via ASGITransport) | exact |
| `apps/backend/tests/integration/test_payments_refund.py` | test (integration) | request-response | `tests/integration/memberships/test_freeze_race.py` (REF-TEST-01 concurrent refund mirror) | exact (race test pattern) |
| `apps/backend/tests/integration/test_payments_list.py` | test (integration) | request-response | `tests/integration/memberships/test_freeze_endpoints.py` (GET endpoint coverage) | exact |
| `apps/backend/tests/integration/test_idempotency.py` | test (integration) | request-response | `tests/integration/memberships/test_freeze_endpoints.py` (header + body assertion shape) | role-match |
| `apps/backend/tests/unit/test_audit_hash.py` | test (unit) | pure function | `tests/unit/test_schemas.py` (pure-function helper assertion shape — by reference) | role-match |
| `apps/backend/tests/integration/test_payments_audit_chain.py` | test (integration) | request-response + DB read-back | `tests/integration/memberships/test_audit_writes.py` (audit_log chain assertion) | exact |

### MODIFY

| Modified File | Role | Change Kind | Closest Analog (for the diff shape) | Match Quality |
|---------------|------|-------------|-------------------------------------|---------------|
| `apps/backend/app/modules/payments/models.py` | model (ORM) | replace stub body | `app/modules/memberships/models.py:Membership` (UUIDPkMixin only + CHECK + Index in `__table_args__`) | exact (UUIDPkMixin without TimestampMixin/SoftDeleteMixin — `Payment` has only `received_at`, no `created_at`/`deleted_at`) |
| `apps/backend/app/modules/payments/__init__.py` | docstring | replace placeholder | `app/modules/trainers/__init__.py` (if exists) — or just rewrite docstring | trivial |
| `apps/backend/app/core/dependencies.py` | composition root (Protocol slots) | append 2 Protocol slots + 2 register fns + 2 get accessor fns | `register_user_loader` lines 52-62 (defensive-raise — `get_current_user` raises `InvalidAccessToken('user_loader_not_registered')`) | exact (defensive-raise variant) |
| `apps/backend/app/main.py` | composition root | append 2 register_*(...) calls in `create_app()` | `app/main.py:122-143` (existing `register_active_membership_resolver` + `register_client_by_telegram_resolver` + `register_trainer_by_id_resolver`) | exact |
| `apps/backend/app/modules/memberships/service.py:create_membership` | service | inject payment_recorder consume call | `memberships/service.py:freeze_membership` lines 688-693 (`repository.insert_freeze_period` + `await session.flush()` pattern) | exact (in-UoW call placement after flush, before audit emit) |
| `apps/backend/app/modules/memberships/service.py` (new `refund_membership`) | service | add orchestrator | `memberships/service.py:freeze_membership` (load → guard → preventive check → repo helper → flush → audit emit → commit) | exact |
| `apps/backend/app/modules/memberships/router.py` | controller | add POST /{id}/refund endpoint | `memberships/router.py:freeze_membership` route lines 327-358 | exact |
| `apps/backend/app/modules/memberships/repository.py` | repository | add `has_renewal_descendants` helper | `memberships/repository.py:get_open_freeze_period` lines 588-605 (single-row query pattern) | exact |
| `apps/backend/app/modules/memberships/constants.py` | constants | add `CANCELLATION_REASON_REFUNDED` | `memberships/constants.py` (existing literal constants like `RENEWAL_STRATEGY_FROM_SOURCE_END_DATE`) | trivial |
| `apps/backend/app/modules/memberships/models.py` | model | add `cancellation_reason` column | `memberships/models.py:Membership.cancel_reason` (Text nullable existing) lines 142 | exact (same `Mapped[str \| None]` shape) |
| `apps/backend/app/modules/memberships/schemas.py` | schema | surface `cancellation_reason` on `MembershipResponse` | `MembershipResponse` (existing optional fields like `cancel_reason: str \| None`) | trivial |
| `apps/backend/alembic/env.py` | composition root | add 1 import line in autodiscovery block | `alembic/env.py:25-29` (`import app.modules.trainers.models  # Phase 31 TRN-01`) | exact |
| `apps/backend/app/api/v1/router.py` | router aggregator | add `v1.include_router(payments_router, prefix='/payments', tags=['payments'])` | `app/api/v1/router.py:18-26` (trainers/visits include_router lines) | exact |
| `apps/backend/openapi.json` | snapshot | byte-stable regen | N/A (mechanical) | N/A |

---

## Pattern Assignments

### 1. `apps/backend/alembic/versions/0012_payments.py` (migration, mixed ops)

**Analog:** `apps/backend/alembic/versions/0008_freeze.py` (multi-op: ADD COL + CREATE TABLE + partial UNIQUE). Secondary: `0011_trainers.py` (latest linear chain analog).

**Header pattern** (`0011_trainers.py:1-20`):
```python
"""trainers

Revision ID: 0011_trainers
Revises: 0010_notifications
Create Date: 2026-05-14 00:00:00.000000

Phase 31 TRN-01 — trainers table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision: str = "0011_trainers"
down_revision: str | None = "0010_notifications"
```

**For 0012 use:** `revision = "0012_payments"`, `down_revision = "0011_trainers"`.

**CREATE TABLE shape** (`0011_trainers.py:23-54`) — extend with PAY-01 columns + CHECK + FK + Index. Note `id` placement matches house style (after business columns):
```python
op.create_table(
    "trainers",
    sa.Column("full_name", sa.Text(), nullable=False),
    ...
    sa.Column(
        "id",
        sa.UUID(),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    ),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ...
    sa.PrimaryKeyConstraint("id", name=op.f("pk_trainers")),
)
```

**Partial UNIQUE installation** (`0011_trainers.py:55-62` — autogenerate-stable via `op.create_index(..., unique=True, postgresql_where=text(...))`):
```python
op.create_index(
    "uq_trainers_phone_alive",
    "trainers",
    ["phone"],
    unique=True,
    postgresql_where=text("deleted_at IS NULL AND phone IS NOT NULL"),
)
```

**Mixed-op (ADD COLUMN + CREATE TABLE) shape** (`0008_freeze.py:38-71` + `74-118`) — direct precedent for ADD `cancellation_reason TEXT NULL` on `memberships` alongside CREATE TABLE `payments` in one revision:
```python
op.add_column(
    "membership_plans",
    sa.Column("freeze_days_limit", sa.Integer(), nullable=False, server_default=sa.text("14")),
)
op.alter_column("membership_plans", "freeze_days_limit", server_default=None)
# ... CREATE TABLE membership_freeze_periods immediately after
```

**Partial UNIQUE via raw `op.execute`** (used when expression-where is autogenerate-unstable — see `0008_freeze.py:122-125`):
```python
op.execute(
    "CREATE UNIQUE INDEX uq_membership_freeze_periods_active_per_membership "
    "ON membership_freeze_periods (membership_id) WHERE ended_at IS NULL"
)
```

**For 0012:** `uq_payments_refund_of_alive ON payments (refund_of) WHERE refund_of IS NOT NULL` can use either `op.create_index(..., postgresql_where=...)` (preferred — column-only predicate is autogenerate-stable, mirrors trainers) OR raw `op.execute()` if planner picks paranoid path. Recommended: `op.create_index` (matches `uq_trainers_phone_alive` shape).

**CHECK constraint** — use `op.create_check_constraint(op.f("ck_payments_amount_sign_matches_subject_kind"), "payments", "(subject_kind = 'refund' AND amount_kopecks < 0) OR (subject_kind IN ('membership','pt_package') AND amount_kopecks > 0)")`. Naming convention auto-derives from `op.f()` (see `0008_freeze.py:52-56`).

---

### 2. `apps/backend/app/core/audit_hash.py` (utility, pure function)

**Analog:** `apps/backend/app/core/audit_payloads.py` (core boundary — MUST NOT import `app.modules.*`; pure data shape).

**Module docstring pattern** (`audit_payloads.py:1-31` — explicit architectural boundary statement):
```python
"""Audit payload schemas (INFRA-23 / Phase 30 / D-30-03).
...
Architectural boundary: app.core.audit_payloads MUST NOT import from
app.modules.* (importlinter `core-not-depend-on-modules` contract).
"""
```

**For `audit_hash.py` mirror this discipline** — module-top docstring declares core ⊥ modules; only imports stdlib (`hashlib`, `json`, `datetime`, `uuid`, `collections.abc.Mapping`, `typing.Any`).

**No service-layer analog exists** (this is a brand-new pure helper). Implementation follows D-32-21..D-32-23 verbatim:
```python
import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID


def payment_row_hash(row: Mapping[str, Any]) -> str:
    """SHA-256 canonical-JSON of payment row; pattern '^sha256:[0-9a-f]{64}$'."""
    canonical: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, UUID):
            canonical[key] = str(value)
        elif isinstance(value, datetime):
            # UTC-normalize for host-TZ independence (D-32-22).
            from datetime import UTC
            canonical[key] = value.astimezone(UTC).isoformat()
        else:
            canonical[key] = value
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return f"sha256:{hashlib.sha256(blob.encode('utf-8')).hexdigest()}"
```

---

### 3. `apps/backend/app/core/idempotency.py` (middleware / per-route Depends)

**Analog:** `apps/backend/app/core/dependencies.py:verify_csrf` lines 347-389 (per-route header check, raises typed `AppError`).

**`verify_csrf` shape** (`dependencies.py:347-389`):
```python
async def verify_csrf(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Double-submit CSRF check (D-07). Short-circuits on safe methods (D-06)."""
    if request.method in _SAFE_METHODS:
        return
    cookie_val = request.cookies.get("sportzal_csrf")
    header_val = request.headers.get("x-csrf-token")
    if (cookie_val is None or header_val is None
            or not secrets.compare_digest(cookie_val, header_val)):
        await audit.emit(session, "csrf_mismatch", ...)
        raise CsrfMismatch("csrf_mismatch")
```

**For `verify_idempotency`:** same per-route Depends shape, returns the validated key string. Imports `Depends(get_redis)` from `app.core.redis`.

**`get_redis` consumption pattern** (`app/core/redis.py:54-57`):
```python
def get_redis(request: Request) -> Redis:
    """Per-request Redis client — resolves to the singleton on app.state.redis."""
    client: Redis = request.app.state.redis
    return client
```

**For `verify_idempotency` signature** (per D-32-18):
```python
async def verify_idempotency(
    request: Request,
    redis: Redis = Depends(get_redis),
) -> str:
    key = request.headers.get("idempotency-key")
    if not key:
        raise ValidationAppError("idempotency_key_required")
    if not _is_valid_idempotency_key(key):
        raise ValidationAppError("idempotency_key_invalid_format")
    return key
```

Use `ValidationAppError` (422) for missing/invalid; `ConflictError` (409) for in-flight; new `IdempotencyKeyReuseError(ConflictError)` or `ValidationAppError` for body-hash mismatch (planner picks — D-32-19 says 422; recommend `ValidationAppError('idempotency_key_reuse')`).

---

### 4. `apps/backend/app/modules/payments/router.py` (controller, 3 GET endpoints)

**Analog:** `apps/backend/app/modules/trainers/router.py` (list + read-one + RBAC + envelope shape).

**Module top + router instantiation** (`trainers/router.py:1-40`):
```python
"""Trainers router — /trainers CRUD with RBAC + CSRF gates (Phase 31 TRN-02..07).

Endpoint surface (5 routes):
  - GET    /api/v1/trainers           — list alive trainers (TRN-04, D-31-09)
  ...

Permission mapping:
  - GET (list + read-one) → require_permission(VIEW, TRAINERS) — reception allowed (D-31-09)
  ...
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission, verify_csrf
from app.core.pagination import PaginatedData
from app.core.permissions import Action, Resource
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.trainers import service
from app.modules.trainers.schemas import (
    TrainerCreateRequest, TrainerListQuery, TrainerResponse, TrainerUpdateRequest,
)

router = APIRouter()
```

**GET list endpoint pattern** (`trainers/router.py:43-57`):
```python
@router.get(
    "",
    response_model=ResponseEnvelope[PaginatedData[TrainerResponse]],
    summary="List alive trainers with optional is_active filter and pagination",
)
async def list_trainers(
    query: Annotated[TrainerListQuery, Depends()],
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.TRAINERS))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[TrainerResponse]]:
    """List alive trainers (TRN-04). VIEW permission required — reception allowed."""
    page = await service.list_trainers(session, query)
    return envelope(page)
```

**For Phase 32 — 3 GETs in `payments/router.py`** (per `<code_context>` line 294-298 architectural decision: ALL 3 endpoints live in `payments` module, not `clients/router.py` or `memberships/router.py`):
- `GET /api/v1/payments` — owner-only (`(VIEW, PAYMENTS) ∈ OWNER_ONLY`).
- `GET /api/v1/payments/by-client/{client_id}` — reception+owner via router-level scoped Depends (D-32-25 path (a)).
- `GET /api/v1/payments/by-membership/{membership_id}` — reception+owner same way.

**Scoped-view Depends** lives in `payments/permissions.py` (see §8 below); planner imports it here.

---

### 5. `apps/backend/app/modules/payments/service.py` (service, caller-owns-txn)

**Analog:** `apps/backend/app/modules/trainers/service.py:create_trainer` (insert + flush + IntegrityError mapping + audit emit + commit). Note: Phase 32 `record_payment` and `issue_refund` are **caller-owns-txn** variants — drop the trailing `await session.commit()` and mark explicitly.

**`create_trainer` body** (`trainers/service.py:57-87`):
```python
async def create_trainer(
    session: AsyncSession,
    actor: CurrentUser,
    data: TrainerCreateRequest,
) -> TrainerResponse:
    """Create a new trainer (TRN-02).

    Order: insert → flush (surface DB constraints) → emit audit on success.
    """
    trainer = await repository.insert_trainer(session, data)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_phone_conflict(exc):
            raise PhoneExistsError("phone_exists") from exc
        raise

    await audit.emit(
        session,
        "trainer_created",
        actor_user_id=actor.id,
        resource_type="trainer",
        resource_id=trainer.id,
        trainer_id=str(trainer.id),
        full_name=trainer.full_name,
        phone=trainer.phone,
    )
    await session.commit()
    return TrainerResponse.model_validate(trainer)
```

**For `payments.service.record_payment` (caller-owns-txn — D-32-10):**
- INSERT via repository.
- `await session.flush()` (no try/except for sale-side — duplicate sale not a constraint here; in-flight idempotency is a Redis concern).
- Compute `payment_row_hash(row_dict)` from the inserted row.
- `await audit.emit(session, "payment_recorded", ...)` with the 7-field payload per `PaymentRecordedPayload`.
- **NO `await session.commit()`** — caller (`memberships.service.create_membership`) owns the UoW.
- Add `# caller-owns-txn` marker so SVC001 walker accepts.

**For `payments.service.issue_refund` (caller-owns-txn — D-32-10):**
- Load original payment via `repository.get_payment_by_id`; 404 if missing.
- Compute `payment_row_hash(original_row_dict)` over the ORIGINAL payment row's 8 stable columns.
- INSERT negative-amount row via `repository.insert_payment(..., refund_of=original.id)`.
- `await session.flush()` — catch `IntegrityError` → `_is_refund_of_uniqueness_conflict(exc)` → `AlreadyRefundedError("already_refunded")` (mirrors `_is_already_frozen_conflict` discriminator).
- `audit.emit(session, "refund_issued", ...)` with `RefundIssuedPayload` fields including `payment_row_hash`.
- **NO `await session.commit()`**.
- `# caller-owns-txn` marker.

**Constraint-name discriminator pattern** (`memberships/service.py:152-163`):
```python
def _is_already_frozen_conflict(exc: IntegrityError) -> bool:
    """Return True iff `exc` was caused by uq_membership_freeze_periods_active_per_membership."""
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "uq_membership_freeze_periods_active_per_membership":
        return True
    return "uq_membership_freeze_periods_active_per_membership" in str(exc.orig)
```

**For Phase 32:** mirror as `_is_refund_of_uniqueness_conflict` in `payments/repository.py` (per `<established_patterns>` line 283 — helper written upfront, not as TODO).

---

### 6. `apps/backend/app/modules/payments/repository.py` (repository, CRUD)

**Analog:** `apps/backend/app/modules/memberships/repository.py:insert_membership` + `insert_freeze_period` + `get_membership` (single-row read). Plus `_is_already_frozen_conflict` discriminator now relocated to repository (see D-32 plan).

**Module docstring discipline** (`memberships/repository.py:1-23`) — declare:
- Single ORM access point invariant.
- Transaction control (NO flush / NO commit — caller-owns).
- `from __future__ import annotations` for `PaginatedData[Payment]` PEP-563 deferral.

**`insert_freeze_period` body** (`memberships/repository.py:565-585`) — direct shape for `insert_payment`:
```python
async def insert_freeze_period(
    session: AsyncSession,
    *,
    membership_id: UUID,
    started_by: UUID,
    started_at: datetime,
) -> MembershipFreezePeriod:
    """Insert an open freeze period (Phase 25 D-25-16).

    Caller (service) owns flush + commit and handles IntegrityError on the
    partial unique index ``uq_membership_freeze_periods_active_per_membership``.
    """
    period = MembershipFreezePeriod(
        membership_id=membership_id,
        started_by=started_by,
        started_at=started_at,
    )
    session.add(period)
    return period
```

**For `insert_payment`:** same `session.add(Payment(...))` + return ORM; no flush, no commit.

**`get_membership` body** (`memberships/repository.py:241-250`) — shape for `get_payment_by_id`:
```python
async def get_membership(session: AsyncSession, membership_id: UUID) -> Membership | None:
    stmt: Select[tuple[Membership]] = select(Membership).where(Membership.id == membership_id)
    result: Membership | None = await session.scalar(stmt)
    return result
```

**For `list_payments_filtered` / `list_payments_for_client` / `list_payments_for_membership`** — copy the predicates-list + count + offset/limit pattern from `memberships/repository.py:list_memberships` lines 253-340 (subject_kind/subject_id/received_by_user_id/received_at-window filters). Use `PaginatedData.model_construct(...)` to bypass Pydantic validation against ORM generic param (rationale at `memberships/repository.py:104-113`).

**Constraint-name discriminator** — same shape as `memberships/service.py:_is_already_frozen_conflict` lines 152-163 (relocated to repository per Phase 31 lesson `<established_patterns>` line 283-285):
```python
def _is_refund_of_uniqueness_conflict(exc: IntegrityError) -> bool:
    """Return True iff `exc` was caused by uq_payments_refund_of_alive."""
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "uq_payments_refund_of_alive":
        return True
    return "uq_payments_refund_of_alive" in str(exc.orig)
```

---

### 7. `apps/backend/app/modules/payments/schemas.py` (Pydantic DTOs)

**Analog:** `apps/backend/app/modules/trainers/schemas.py` (Create/Response/ListQuery).

**`TrainerListQuery` (extends PageQuery)** (`trainers/schemas.py:77-86`):
```python
class TrainerListQuery(PageQuery):
    """GET /api/v1/trainers query params."""
    active: bool | None = None
```

**For `PaymentListQuery`:** extends `PageQuery`, declares optional filters:
```python
class PaymentListQuery(PageQuery):
    subject_kind: str | None = Field(default=None, pattern=r"^(membership|pt_package|refund)$")
    subject_id: UUID | None = None
    received_by_user_id: UUID | None = None
    received_from: date | None = None
    received_to: date | None = None
```
(`Field(pattern=...)` precedent: `trainers/schemas.py:36` `phone: str | None = Field(default=None, pattern=PHONE_REGEX)`.)

**`PaymentResponse` (ResponseData)** — copy `TrainerResponse` shape (`trainers/schemas.py:61-69`):
```python
class TrainerResponse(ResponseData):
    """Single trainer read DTO. `from_attributes=True` inherited via ContractModel."""
    id: UUID
    full_name: str
    ...
```

**`MembershipRefundRequest` (extra='forbid' is inherited; REF-05 reject `amountKopecks`):**
- `BackendSchemaBase` already sets `extra='forbid'` (`app/core/schemas.py:46-53`) — no override needed.
- Shape mirrors `MembershipCancelRequest` (`memberships/schemas.py:198-221`):
```python
class MembershipCancelRequest(BackendSchemaBase):
    """POST /api/v1/memberships/{id}/cancel body (Phase 17 D-11)."""
    reason: str | None = Field(default=None, max_length=500)
```
For refund, `reason` is **required** (REF-06): `reason: str = Field(min_length=1, max_length=200)`.

**`extra='forbid'` enforcement is automatic via `BackendSchemaBase`** (`app/core/schemas.py:36-53`):
```python
class BackendSchemaBase(ContractModel):
    """Inbound request body / query params. Strict on extras (extra='forbid')."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        extra="forbid",
    )
```
**Important:** D-32-13 says "extends BackendSchemaBase НО с `extra='forbid'` override" — that override is redundant (already in base). Test fixture `{"reason":"x","amountKopecks":1000}` → 422 because `extra='forbid'` is inherited from `BackendSchemaBase`. Planner can either omit the explicit override or restate it for clarity.

---

### 8. `apps/backend/app/modules/payments/permissions.py` (scoped Depends factory)

**Analog:** `apps/backend/app/core/dependencies.py:require_permission` factory shape (lines 269-322).

**`require_permission` factory** (`dependencies.py:269-322`):
```python
def require_permission(
    action: Action,
    resource: Resource,
) -> Callable[..., Awaitable[CurrentUser]]:
    async def _checker(
        request: Request,
        user: Annotated[CurrentUser, Depends(get_current_user)],
        session: Annotated[AsyncSession, Depends(get_db)],
    ) -> CurrentUser:
        if not can(user.role, action, resource):
            await audit.emit(session, "rbac_forbidden", ...)
            raise ForbiddenError(f"forbidden:{action.value}:{resource.value}")
        return user
    return _checker
```

**For `payments/permissions.py::require_payments_view_for_subject` (D-32-25 path (a) — router-level scoped Depends):**
- Owner short-circuit → allow.
- Reception → allow ONLY when subject (client_id / membership_id) is part of the URL path (the resource is scope-bound; reception cannot list globally).
- Mirror `_checker` factory closure pattern verbatim.

Planner picks whether this lives in `payments/permissions.py` or stays inline in `payments/router.py` as a thin Depends. Recommendation: `permissions.py` (matches module shape).

---

### 9. `apps/backend/app/modules/payments/constants.py`

**Analog:** `apps/backend/app/modules/memberships/constants.py` (literal constants + `__all__` export list).

**`memberships/constants.py:30-47`**:
```python
RENEWAL_STRATEGY_FROM_SOURCE_END_DATE = "from_source_end_date"
RENEWAL_STRATEGY_FROM_TODAY_EXPIRED_SOURCE = "from_today_expired_source"

EXPIRING_KIND_7D = "expiring_7d"
EXPIRING_KIND_3D = "expiring_3d"
EXPIRING_KIND_1D = "expiring_1d"
EXPIRING_KINDS: tuple[str, ...] = (EXPIRING_KIND_7D, EXPIRING_KIND_3D, EXPIRING_KIND_1D)
```

**For `payments/constants.py`:**
```python
SUBJECT_KIND_MEMBERSHIP = "membership"
SUBJECT_KIND_PT_PACKAGE = "pt_package"
SUBJECT_KIND_REFUND = "refund"
SUBJECT_KIND_VALUES: tuple[str, ...] = (SUBJECT_KIND_MEMBERSHIP, SUBJECT_KIND_PT_PACKAGE, SUBJECT_KIND_REFUND)
```

---

### 10. `apps/backend/app/modules/payments/models.py` (ORM — replace stub)

**Analog:** `apps/backend/app/modules/memberships/models.py:Membership` (line 89-186) — UUIDPkMixin + TimestampMixin (NO SoftDeleteMixin) precedent. For payments, drop **both** TimestampMixin AND SoftDeleteMixin — `received_at` is the only temporal column, no `created_at`/`updated_at`/`deleted_at`.

**Membership model shape** (`memberships/models.py:89-186` — CHECK + Index + FK with named constraints):
```python
class Membership(Base, UUIDPkMixin, TimestampMixin):
    """Membership instance ... NO soft-delete column ..."""

    __tablename__ = "memberships"

    client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="RESTRICT", name="fk_memberships_client_id_clients"),
        nullable=False,
    )
    ...
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ...

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'expired', 'cancelled', 'frozen')",
            name="status",  # NAMING_CONVENTION expands to ck_memberships_status
        ),
        Index(
            "ix_memberships_client_id_status_end_date",
            "client_id", "status", text("end_date DESC"),
        ),
    )
```

**For Phase 32 `Payment` ORM (replace stub at `payments/models.py:25-34`):**
```python
class Payment(Base, UUIDPkMixin):
    """Append-only payment ledger row (B-01). NO TimestampMixin (no created_at/updated_at), NO SoftDeleteMixin."""

    __tablename__ = "payments"

    subject_kind: Mapped[str] = mapped_column(Text, nullable=False)
    subject_id: Mapped[UUIDType] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    amount_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)  # signed
    method: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'cash'"))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    received_by_user_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_payments_received_by_user_id_users"),
        nullable=False,
    )
    refund_of: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="RESTRICT", name="fk_payments_refund_of_payments"),
        nullable=True,
    )
    audit_log_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("audit_log.id", ondelete="SET NULL", name="fk_payments_audit_log_id_audit_log"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "(subject_kind = 'refund' AND amount_kopecks < 0) "
            "OR (subject_kind IN ('membership','pt_package') AND amount_kopecks > 0)",
            name="amount_sign_matches_subject_kind",
        ),
        CheckConstraint(
            "subject_kind IN ('membership','pt_package','refund')",
            name="subject_kind",
        ),
        Index(
            "uq_payments_refund_of_alive",
            "refund_of",
            unique=True,
            postgresql_where=text("refund_of IS NOT NULL"),
        ),
        Index("ix_payments_subject", "subject_kind", "subject_id"),
        Index("ix_payments_received_by_user_id", "received_by_user_id"),
        Index("ix_payments_received_at", text("received_at DESC")),
    )
```

**Add `uq_payments_refund_of_alive` to the env.py `_include_object` skip list** (`alembic/env.py:60-72`) — mirrors `uq_trainers_phone_alive` line 70 if expression-stability is iffy. With column-only `postgresql_where`, this is autogenerate-stable so the skip-list entry is OPTIONAL.

---

### 11. `apps/backend/app/core/dependencies.py` (Protocol slots — extend)

**Analog (DEFENSIVE RAISE — D-32-14):** `app/core/dependencies.py:register_user_loader` + `get_current_user` raises `InvalidAccessToken('user_loader_not_registered')` when `_user_loader is None` (line 253-257):
```python
if _user_loader is None:
    # Defensive: composition root MUST register before the request flow starts.
    raise InvalidAccessToken("user_loader_not_registered")
```

**NOT the silent-None pattern** of `_active_membership_resolver` (line 117-119) — payments are load-bearing per `<code_context>` line 270 and D-32-14.

**Existing Protocol slot shape** (`dependencies.py:205-229` — trainer slot, latest precedent):
```python
class TrainerById(Protocol):
    """Structural type for alive Trainer lookup result (Phase 31 D-31-13)."""
    id: UUID
    is_active: bool

TrainerByIdResolver = Callable[[AsyncSession, UUID], Awaitable[TrainerById | None]]

_trainer_by_id_resolver: TrainerByIdResolver | None = None

def register_trainer_by_id_resolver(resolver: TrainerByIdResolver) -> None:
    """Composition-root setter — called by app.main.create_app() AND
    app.workers.telegram_bot.main() (defensive double-wiring per REG-29-03)."""
    global _trainer_by_id_resolver
    _trainer_by_id_resolver = resolver

async def resolve_trainer_by_id(session: AsyncSession, trainer_id: UUID) -> TrainerById | None:
    """Consumer entry point — Phase 34 pt_sessions service will call this."""
    if _trainer_by_id_resolver is None:
        return None
    return await _trainer_by_id_resolver(session, trainer_id)
```

**For Phase 32 — 2 new slots with DEFENSIVE-RAISE accessor (D-32-14):**
```python
class PaymentRecorder(Protocol):
    async def __call__(
        self,
        session: AsyncSession,
        *,
        subject_kind: str,
        subject_id: UUID,
        amount_kopecks: int,
        method: str = "cash",
        received_by_user_id: UUID,
        audit_actor: CurrentUser,
    ) -> "Payment": ...

_payment_recorder: PaymentRecorder | None = None

def register_payment_recorder(recorder: PaymentRecorder) -> None:
    """Composition-root setter — called by app.main.create_app() (NOT telegram_bot)."""
    global _payment_recorder
    _payment_recorder = recorder

def get_payment_recorder() -> PaymentRecorder:
    """Defensive accessor (D-32-14) — raises if slot not registered.

    Mirrors `_user_loader` defensive raise (line 253-257), NOT
    `_active_membership_resolver` silent-None (line 117-119).
    """
    if _payment_recorder is None:
        raise RuntimeError("payment_recorder not registered")
    return _payment_recorder
```

Same shape for `PaymentRefunder` + `register_payment_refunder` + `get_payment_refunder`.

**Note on `Payment` forward reference:** Use `"Payment"` string forward-ref OR `TYPE_CHECKING` import block. The `app.core ⊥ app.modules` importlinter contract forbids importing `app.modules.payments.models.Payment` at module level. Recommendation: `if TYPE_CHECKING: from app.modules.payments.models import Payment` (same trick as `memberships/service.py:106-107`).

---

### 12. `apps/backend/app/main.py:create_app()` (composition-root wiring)

**Analog:** `app/main.py:136-143` (Phase 31 `register_trainer_by_id_resolver` block — latest precedent).

**Existing block** (`main.py:136-143`):
```python
# Phase 31 D-31-14: fourth composition-root carve-out — pt_sessions service
# (Phase 34) will validate trainer existence via this Protocol slot.
# Defensive: bot worker also registers (see telegram_bot.py). Idempotent.
from app.modules.trainers import (
    service as trainers_service,
)

register_trainer_by_id_resolver(trainers_service.resolve_trainer_by_id)
```

**For Phase 32 — add AFTER the trainer block, BEFORE `app.include_router(api)`** (D-32-15: position between `register_active_membership_resolver` and `register_client_by_telegram_resolver` per alphabet — but the spec really says "after Phase 31 trainer-slot wiring"; the simplest planner-friendly placement is right after the trainer block, mirroring the chronological pattern):
```python
# Phase 32 D-32-15: fifth + sixth composition-root carve-outs — sale flow
# (memberships.service.create_membership) consumes payment_recorder; refund
# flow (memberships.service.refund_membership) consumes payment_refunder.
# Exclusively wired here (NOT in telegram_bot.py — bot is not a sale/refund
# participant in v1.4). Defensive raise on missing slot (D-32-14).
from app.modules.payments import (
    service as payments_service,
)
register_payment_recorder(payments_service.record_payment)
register_payment_refunder(payments_service.issue_refund)
```

Also import `register_payment_recorder` + `register_payment_refunder` in the top-level `from app.core.dependencies import (...)` block (lines 41-46).

---

### 13. `apps/backend/app/modules/memberships/service.py:create_membership` (modification — PAY-05)

**Analog (the exact insertion point):** `memberships/service.py:freeze_membership` lines 687-714 — pattern of `repository.insert_X(...) → await session.flush() → consume Protocol slot in same UoW → audit.emit → commit`.

**Current `create_membership` flow** (`memberships/service.py:515-545`):
```python
# 4 + 5: insert with snapshot, then flush to surface FK errors
membership = await repository.insert_membership(
    session, data, plan=plan, start_date=start_date, end_date=end_date,
)
await session.flush()

# 6: emit audit BEFORE commit (Phase 16 D-14 co-transactional contract).
await audit.emit(
    session,
    "membership_created",
    actor_user_id=actor.id,
    resource_type="membership",
    resource_id=membership.id,
    client_id=str(membership.client_id),
    plan_id=str(membership.plan_id),
    end_date=membership.end_date.isoformat(),
)
# 7: commit
await session.commit()
```

**Phase 32 Plan 32-02 modification:** insert payment recorder call BETWEEN `await session.flush()` (line 523) and `audit.emit('membership_created', ...)` (lines 529-538):
```python
await session.flush()

# Phase 32 PAY-05: record payment in same UoW (mandatory snapshot symmetry).
# Server derives amount from snapshot — client cannot supply (D-32-16/17).
payment = await get_payment_recorder()(
    session,
    subject_kind=SUBJECT_KIND_MEMBERSHIP,
    subject_id=membership.id,
    amount_kopecks=membership.price_kopecks_snapshot,
    method="cash",
    received_by_user_id=actor.id,
    audit_actor=actor,
)

# 6: emit audit BEFORE commit. Phase 32: payload gains `payment_id` field
# (membership_created is free-form per D-30-02 — no schema mutation).
await audit.emit(
    session,
    "membership_created",
    ...,
    payment_id=str(payment.id),  # Phase 32 PAY-05 addition
)
```

**Note on event-name drift:** Plan 32-02 docs reference `membership_sold`, but the LOCKED event is `membership_created` (see `audit.py:159`). Planner uses `membership_created`; logs the terminology drift in plan SUMMARY (similar to `refund_issued` vs `payment_refunded` typo handling in D-32-12).

**Imports needed:** `from app.core.dependencies import get_payment_recorder` + `from app.modules.payments.constants import SUBJECT_KIND_MEMBERSHIP`.

---

### 14. `apps/backend/app/modules/memberships/service.py::refund_membership` (NEW orchestrator)

**Analog:** `memberships/service.py:freeze_membership` lines 639-719 (full orchestrator template — load → guard → preventive check → repository helper → flush+IntegrityError translation → audit emit → commit).

**Full template** (`memberships/service.py:667-719`):
```python
async def freeze_membership(
    session: AsyncSession,
    actor: CurrentUser,
    membership_id: UUID,
) -> MembershipResponse:
    """Open a freeze period and transition active → frozen (MEM-FRZ-04)."""
    membership = await repository.get_membership(session, membership_id)
    if membership is None:
        raise MembershipNotFoundError("membership_not_found")

    _assert_can_freeze(membership)

    today_msk = datetime.now(ZoneInfo("Europe/Moscow")).date()
    days_used = await repository.compute_freeze_days_used(
        session, membership.id, today_msk=today_msk
    )
    if days_used >= membership.freeze_days_limit_snapshot:
        raise FreezeLimitExceededError("freeze_limit_exceeded", fields={...})

    now_utc = datetime.now(tz=UTC)
    period = await repository.insert_freeze_period(
        session, membership_id=membership.id, started_by=actor.id, started_at=now_utc,
    )
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_already_frozen_conflict(exc):
            raise AlreadyFrozenError("already_frozen") from exc
        raise

    await repository.update_membership_status(session, membership, status="frozen")
    await session.flush()

    await audit.emit(
        session, "membership_frozen", actor_user_id=actor.id,
        resource_type="membership", resource_id=membership.id, ...
    )

    await session.refresh(membership, attribute_names=["updated_at"])
    await session.commit()

    return await _build_membership_response(session, membership)
```

**For `refund_membership` (per D-32-11; status guard ordering: frozen → renewed-source → generic transition):**
```python
async def refund_membership(
    session: AsyncSession,
    actor: CurrentUser,
    membership_id: UUID,
    data: MembershipRefundRequest,
) -> MembershipResponse:
    """Refund a membership (REF-01). Reception+owner per B-07. Owns the UoW."""
    # 1. Load
    membership = await repository.get_membership(session, membership_id)
    if membership is None:
        raise MembershipNotFoundError("membership_not_found")

    # 2. Status guard — frozen-specific FIRST (B-08), then generic transition.
    if membership.status == "frozen":
        raise MustUnfreezeFirstError("must_unfreeze_first")

    # 3. Renewed-source guard (B-09 / REF-04).
    if await repository.has_renewal_descendants(session, membership_id):
        raise CannotRefundRenewedSourceError("cannot_refund_renewed_source")

    # 4. Generic transition guard (catches already-cancelled).
    _assert_can_transition(membership, target="cancelled")

    # 5. Load ORIGINAL payment (membership sale).
    original_payment = await payments_repository.get_original_membership_payment(
        session, membership_id
    )
    if original_payment is None:
        raise LegacyMembershipNoPaymentError("legacy_membership_no_payment")

    # 6. Call refunder Protocol slot (defensive — raises if not registered).
    refund_payment = await get_payment_refunder()(
        session,
        original_payment_id=original_payment.id,
        refund_user_id=actor.id,
        reason=data.reason,
        audit_actor=actor,
    )

    # 7. Transition status → cancelled; set cancellation_reason sentinel.
    await repository.update_membership_status(
        session, membership,
        status="cancelled",
        cancelled_at=datetime.now(tz=UTC),
    )
    membership.cancellation_reason = CANCELLATION_REASON_REFUNDED  # D-32-08

    await session.flush()

    # 8. Audit emit (subject-side; payment-side audit emitted inside issue_refund).
    await audit.emit(
        session, "membership_refunded",
        actor_user_id=actor.id,
        resource_type="membership",
        resource_id=membership.id,
        membership_id=membership.id,
        client_id=membership.client_id,
        refund_payment_id=refund_payment.id,
        reason=data.reason,
    )

    await session.refresh(membership, attribute_names=["updated_at"])
    await session.commit()
    return await _build_membership_response(session, membership)
```

**Cross-module repo import:** `from app.modules.payments import repository as payments_repository` is FORBIDDEN by `modules-independent` contract. Workaround: Add a thin **third Protocol slot** `register_original_payment_loader` OR put `get_original_membership_payment` as a helper on `get_payment_refunder` (signature changes), OR have the refunder service load it internally. Per D-32-10, `issue_refund` already loads the original by `original_payment_id`. Resolution: orchestrator does NOT load the original itself — it passes `subject_id=membership_id` to a new variant of the refunder slot, and the refunder internally loads the original payment via `subject_kind='membership' AND subject_id`. Planner refines the Protocol slot signature (D-32-14 currently passes `original_payment_id` — planner amends to either pre-load via a new helper Protocol or pass `subject_kind/subject_id` instead).

**Recommendation:** Amend `PaymentRefunder.__call__` signature to take `(subject_kind, subject_id)` rather than `original_payment_id`, so the orchestrator never touches `payments` models directly. Planner finalizes.

---

### 15. `apps/backend/app/modules/memberships/router.py` — POST /{id}/refund

**Analog:** `memberships/router.py:freeze_membership` route (lines 327-358) — RBAC + CSRF ordering, 200 status code with body envelope.

**Existing freeze endpoint** (lines 327-358):
```python
@memberships_router.post(
    "/{membership_id}/freeze",
    response_model=ResponseEnvelope[MembershipResponse],
    status_code=status.HTTP_200_OK,
    summary="Freeze membership (...409 freeze_limit_exceeded / already_frozen / invalid_transition)",
)
async def freeze_membership(
    membership_id: UUID,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.MEMBERSHIPS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[MembershipResponse]:
    """Freeze a membership (MEM-FRZ-EP-01). CREATE permission + CSRF required."""
    membership = await service.freeze_membership(session, actor, membership_id)
    return envelope(membership)
```

**For `/refund` endpoint (REF-01 — `(REFUND, MEMBERSHIPS)` not in OWNER_ONLY per B-07):**
```python
@memberships_router.post(
    "/{membership_id}/refund",
    response_model=ResponseEnvelope[MembershipResponse],
    status_code=status.HTTP_200_OK,
    summary=(
        "Refund a membership (reception+owner per B-07; "
        "409 must_unfreeze_first / cannot_refund_renewed_source / invalid_transition / already_refunded)"
    ),
)
async def refund_membership(
    membership_id: UUID,
    payload: MembershipRefundRequest,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.REFUND, Resource.MEMBERSHIPS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[MembershipResponse]:
    """Refund a membership (REF-01). REFUND permission + CSRF required."""
    membership = await service.refund_membership(session, actor, membership_id, payload)
    return envelope(membership)
```

**RBAC-04 ordering** (existing invariant per `memberships/router.py:47-52` docstring): `Depends(require_permission(...))` BEFORE `Depends(verify_csrf)` in signature.

---

### 16. `apps/backend/app/modules/memberships/repository.py::has_renewal_descendants` (NEW helper)

**Analog:** `memberships/repository.py:get_open_freeze_period` lines 588-605 (single-row read pattern).

**Template:**
```python
async def has_renewal_descendants(session: AsyncSession, membership_id: UUID) -> bool:
    """REF-04 / B-09: True iff `membership_id` is the `previous_membership_id`
    of any alive descendant. Used by refund_membership orchestrator to surface
    409 cannot_refund_renewed_source.
    """
    stmt = (
        select(Membership.id)
        .where(Membership.previous_membership_id == membership_id)
        .limit(1)
    )
    result = await session.scalar(stmt)
    return result is not None
```

**No soft-delete filter needed** — memberships have no `deleted_at` per `memberships/models.py:89` docstring. Status-based discrimination only if business requires; D-32-11 says EXISTS without status filter is correct (any descendant blocks).

---

### 17. `apps/backend/app/modules/memberships/constants.py::CANCELLATION_REASON_REFUNDED`

**Analog:** `memberships/constants.py:34-35` (RENEWAL_STRATEGY_* literal constants).

```python
# Phase 32 D-32-08 — refund sentinel for memberships.cancellation_reason column.
CANCELLATION_REASON_REFUNDED = "refunded"
```

Add to `__all__` list (line 49-57).

---

### 18. `apps/backend/app/modules/memberships/models.py::cancellation_reason` (ADD column)

**Analog:** `memberships/models.py:142` (existing `cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)`).

```python
# Phase 32 REF-01 / D-32-07 — column added by migration 0012; sentinel value
# 'refunded' set by refund_membership orchestrator (CANCELLATION_REASON_REFUNDED).
cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
```

**Note:** Two columns coexist — existing `cancel_reason` (operator free-text from cancel endpoint) AND new `cancellation_reason` (sentinel-only for refund). Per D-32-07, planner decides whether admin-cancel populates `cancellation_reason` or leaves NULL (recommendation: leave NULL for v1.4; only refund populates).

---

### 19. `apps/backend/app/modules/memberships/schemas.py::MembershipResponse` (surface field)

**Analog:** `MembershipResponse` ResponseData class (`memberships/schemas.py:227-244`) — existing optional fields like `cancel_reason: str | None`.

Add:
```python
cancellation_reason: str | None = None  # Phase 32 REF-01 — 'refunded' sentinel
```

---

### 20. `apps/backend/alembic/env.py` (autodiscovery import)

**Analog:** `alembic/env.py:25-29` (existing `import app.modules.X.models` block, with the Phase 31 comment style at line 28).

**Current block:**
```python
import app.modules.auth.models
import app.modules.clients.models
import app.modules.memberships.models
import app.modules.trainers.models  # Phase 31 TRN-01
import app.modules.visits.models
```

**For Phase 32:** add one line (alphabetic):
```python
import app.modules.payments.models  # Phase 32 PAY-01
```

**If `uq_payments_refund_of_alive` predicate causes autogen drift,** add to `_include_object` skip list (lines 60-72, mirror line 70 `"uq_trainers_phone_alive"` entry). Test with `alembic check` after migration ships — likely NOT needed because predicate `WHERE refund_of IS NOT NULL` is column-only (autogenerate-stable, same as trainers).

---

### 21. `apps/backend/app/api/v1/router.py` (mount router)

**Analog:** `app/api/v1/router.py:18-26` (existing trainers/visits mount lines).

**Current:**
```python
from app.modules.trainers.router import router as trainers_router
from app.modules.visits.router import router as visits_router

v1 = APIRouter()
v1.include_router(auth_router, prefix="/auth", tags=["auth"])
v1.include_router(clients_router, prefix="/clients", tags=["clients"])
v1.include_router(plans_router, prefix="/membership-plans", tags=["membership-plans"])
v1.include_router(memberships_router, prefix="/memberships", tags=["memberships"])
v1.include_router(trainers_router, prefix="/trainers", tags=["trainers"])
v1.include_router(visits_router, prefix="/visits", tags=["visits"])
```

**For Phase 32:** insert (alphabetic):
```python
from app.modules.payments.router import router as payments_router
...
v1.include_router(payments_router, prefix="/payments", tags=["payments"])
```

Position alphabetically: after `memberships_router`, before `trainers_router` (matches v1 docstring style).

---

### 22. Tests — `tests/integration/test_payments_*.py`

**Analog (sale + refund happy/409 paths):** `tests/integration/memberships/test_freeze_endpoints.py` (200 + 409 coverage via ASGITransport).

**Analog (concurrent refund — REF-TEST-01):** `tests/integration/memberships/test_freeze_race.py` (lines 52-173) — direct mirror with endpoint + constraint name swapped.

**`test_freeze_race.py` race-test shape** (lines 124-145):
```python
async def _post() -> Any:
    return await authed.post(
        f"/api/v1/memberships/{membership_id}/freeze",
        headers=headers,
    )

n_concurrent = 5
responses = await asyncio.gather(*[_post() for _ in range(n_concurrent)])
await authed.aclose()

statuses = sorted(r.status_code for r in responses)
assert statuses == [200] + [409] * (n_concurrent - 1)

bodies_409 = [r.json() for r in responses if r.status_code == 409]
codes = [b.get("code") for b in bodies_409]
assert all(c == "already_frozen" for c in codes)
```

**For Phase 32 REF-TEST-01:** swap endpoint to `/api/v1/memberships/{id}/refund`, swap expected 409 code to `'already_refunded'`, swap audit assertion to `AuditLog.action == "membership_refunded"` count == 1 + `"refund_issued"` count == 1.

**Use `db_session_real_commit` fixture** — SAVEPOINT-isolated `db_session` does not serialize concurrent INSERTs through the partial UNIQUE (commentary `test_freeze_race.py:9-10`).

---

### 23. `tests/integration/test_idempotency.py`

**Analog:** Standard ASGITransport client test pattern from `tests/integration/memberships/test_freeze_endpoints.py` (any single endpoint test).

No exact analog for idempotency exists in the codebase. Planner writes from first principles per D-32-19:
- **First call** with `Idempotency-Key: abc-123` → 201.
- **Replay with same key + same body** → 201, identical response envelope.
- **Replay with same key + different body** → 422 `idempotency_key_reuse`.
- **Missing key** → 400 `idempotency_key_required` (or 422 if `ValidationAppError` path picked).

---

### 24. `tests/unit/test_audit_hash.py`

**Analog:** Conceptually — pure-function unit tests; no direct codebase precedent. Use bare `pytest` + `pytest.mark.parametrize` for determinism / TZ-independence / column-flip cases.

Test matrix (per D-32-23):
- Same row → same hash (determinism).
- Same row with timestamp in different TZs (UTC vs Europe/Moscow) → same hash (UTC normalization).
- Flip any one of the 8 stable columns → different hash.
- Hash format matches `^sha256:[0-9a-f]{64}$`.

---

## Shared Patterns

### Authentication & Authorization
**Source:** `app/core/dependencies.py:269-322` (`require_permission(Action, Resource)` factory).
**Apply to:** All Phase 32 mutation/read endpoints in `payments/router.py` and the new `/refund` route in `memberships/router.py`.

```python
actor: Annotated[
    CurrentUser,
    Depends(require_permission(Action.X, Resource.Y)),
],
```

Permission matrix (already locked in `app/core/permissions.py:55-89`):
- `(VIEW, PAYMENTS)` ∈ OWNER_ONLY → global list owner-only.
- `(REFUND, MEMBERSHIPS)` NOT in OWNER_ONLY → reception+owner.
- `(CREATE, MEMBERSHIPS)` NOT in OWNER_ONLY → reception+owner sale flow.

### CSRF Discipline
**Source:** `app/core/dependencies.py:347-389` (`verify_csrf`).
**Apply to:** All mutation endpoints (POST /refund, POST /memberships sale — already wired).

```python
_csrf: Annotated[None, Depends(verify_csrf)],
```

**RBAC-04 ordering invariant** (enforced by `tests/integration/test_route_introspection.py`): `Depends(require_permission(...))` BEFORE `Depends(verify_csrf)` BEFORE `Depends(verify_idempotency)` (Phase 32 extends to auth → rbac → csrf → idempotency).

### Caller-owns-txn Discipline
**Source:** `app/modules/memberships/service.py:create_plan` (commits at end) vs `_build_membership_response` (read-only helper). Phase 31 service mostly commits, BUT Phase 32 `payments.service.record_payment` and `issue_refund` deliberately do NOT commit (caller owns).

**SVC001 walker accepts the no-commit variant** when the function carries an inline `# caller-owns-txn` marker or docstring note (per D-32-10). Precedent: `_build_membership_response` line 221 carries `# noqa: SVC001 caller-owns-txn — read-only projection helper`.

For Phase 32, use the same `# noqa: SVC001` form on `record_payment` and `issue_refund`:
```python
async def record_payment(  # noqa: SVC001 caller-owns-txn — sale orchestrator owns UoW
    session: AsyncSession, ...
) -> Payment: ...
```

### Append-only Invariant (B-01 / INFRA-22)
**Source:** `tests/unit/test_payments_appendonly.py` (AST walker) + `app/modules/payments/__init__.py` docstring + `app/modules/payments/service.py:1-11` placeholder warning.

**Apply to:** `app/modules/payments/service.py` and `app/modules/payments/repository.py`.

Forbidden inside these files (walker enforces):
- `update(Payment)`, `delete(Payment)`, `session.execute(update|delete(Payment)...)`.
- `session.delete(<Payment instance>)`.
- `on_conflict_do_update(Payment)`.

Allowed: `session.add(Payment(...))`, `select(Payment)...`, `session.execute(insert(Payment))`.

### Error Translation (IntegrityError → AppError)
**Source:** `memberships/service.py:152-163` (`_is_already_frozen_conflict` discriminator) + `trainers/service.py:41-46` (`_is_phone_conflict`).

**Apply to:** Phase 32 service consume sites for refund — translate `uq_payments_refund_of_alive` IntegrityError → 409 `already_refunded`. Relocate discriminator from service.py to repository.py per Phase 31 lesson (so it's available at the boundary that owns the constraint).

### Audit Emit (LOCKED + payload schema validated)
**Source:** `app/core/audit.py:202-269` (`emit()` signature) + `app/core/audit_payloads.py:82-134` (PaymentRecorded / RefundIssued / MembershipRefunded locked schemas).

**Apply to:** All 3 v1.4 payment audit emits.

```python
await audit.emit(
    session,
    "payment_recorded",  # LITERAL (AST gate enforces)
    actor_user_id=actor.id,
    resource_type="payment",  # LITERAL
    resource_id=payment.id,
    payment_id=payment.id,
    subject_kind=payment.subject_kind,
    subject_id=payment.subject_id,
    amount_kopecks=payment.amount_kopecks,
    method=payment.method,
    received_by_user_id=payment.received_by_user_id,
    payment_row_hash=payment_row_hash(payment_row_dict),
)
```

Pydantic `extra='forbid'` on `PaymentRecordedPayload` rejects any extra kwarg → `ValidationError` propagates (hard-fail per D-09).

### Wire-Format Schemas
**Source:** `app/core/schemas.py:36-53` (`BackendSchemaBase` — `extra='forbid'`, `alias_generator=to_camel`).

**Apply to:** All Phase 32 request/query schemas (`PaymentListQuery`, `MembershipRefundRequest`).

Response DTOs inherit from `ResponseData` (line 56-57) — `from_attributes=True` enables `Model.model_validate(orm_instance)`.

### Pagination
**Source:** `app/core/pagination.py:20-44` (`PageQuery` + `PaginatedData[T]`).

**Apply to:** All 3 GET endpoints in `payments/router.py`.

```python
response_model=ResponseEnvelope[PaginatedData[PaymentResponse]]
```

Repository returns `PaginatedData.model_construct(items=..., total=..., page=..., page_size=...)` (bypasses Pydantic validation on the ORM generic param — see `memberships/repository.py:104-113`).

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `apps/backend/app/core/audit_hash.py` | utility (pure hash) | pure function | First SHA-256 canonical-JSON helper in the codebase; only structural analog is `app/core/audit_payloads.py` (core-boundary discipline). Implementation follows RESEARCH-style algorithm per D-32-23 verbatim. |
| `apps/backend/app/core/idempotency.py` (Redis cache part) | middleware (Depends) | request-response + Redis cache | `verify_csrf` covers the per-route Depends shape; the **Redis SET NX + body-hash compare + cached envelope replay** mechanics are new (no precedent — Phase 27 expiring-soon uses Redis as state cache, but no idempotency-key flow exists yet). Implementation follows D-32-18..D-32-20 from scratch. |
| `tests/integration/test_idempotency.py` | test | request-response | No existing test for idempotency-key replay/conflict — first-of-its-kind. Use standard ASGITransport client setup from `tests/integration/memberships/conftest.py`. |
| `tests/unit/test_audit_hash.py` | test (unit) | pure function | No existing pure-function determinism test analog — write fresh with `@pytest.mark.parametrize`. |

---

## Metadata

**Analog search scope:**
- `apps/backend/app/modules/{memberships,trainers,clients,payments}/`
- `apps/backend/app/core/`
- `apps/backend/alembic/versions/`
- `apps/backend/tests/integration/memberships/`
- `apps/backend/app/api/v1/`
- `apps/backend/app/main.py`

**Files scanned (deep read):** 15
- `memberships/service.py` (1337 lines — scanned lines 1-720 covering `create_membership`, `_assert_can_transition` family, `freeze_membership`, `_is_already_frozen_conflict`).
- `memberships/router.py` (full read — 427 lines).
- `memberships/repository.py` (partial — lines 1-340 + 540-640 covering `insert_membership`, `get_membership`, `insert_freeze_period`, `get_open_freeze_period`).
- `memberships/models.py` (full read — 321 lines).
- `memberships/schemas.py` (lines 1-244 covering `MembershipCancelRequest`, `MembershipCreateRequest`, `MembershipResponse`).
- `memberships/constants.py` (full — 58 lines).
- `trainers/service.py` (full — 225 lines).
- `trainers/router.py` (full — 136 lines).
- `trainers/repository.py` (full — 114 lines).
- `trainers/models.py` (full — 43 lines).
- `trainers/schemas.py` (full — 86 lines).
- `core/dependencies.py` (full — 389 lines).
- `core/audit.py` (lines 1-270 — full).
- `core/audit_payloads.py` (full — 307 lines).
- `core/schemas.py` (full — 82 lines).
- `core/permissions.py` (full — 101 lines).
- `core/pagination.py` (full — 43 lines).
- `core/exceptions.py` (lines 1-130).
- `core/redis.py` (full — 57 lines).
- `core/database.py` (lines 1-80).
- `app/main.py` (full — 146 lines).
- `app/api/v1/router.py` (full — 27 lines).
- `alembic/env.py` (lines 1-80).
- `alembic/versions/0007_status_taxonomy.py` (full — 44 lines).
- `alembic/versions/0008_freeze.py` (full — 144 lines).
- `alembic/versions/0011_trainers.py` (full — 67 lines).
- `tests/integration/memberships/test_freeze_race.py` (full — 173 lines).
- `payments/{models,service,__init__}.py` (placeholder stubs — full).

**Pattern extraction date:** 2026-05-15
