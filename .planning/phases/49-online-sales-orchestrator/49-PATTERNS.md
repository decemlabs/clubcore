# Phase 49: Online Sales Orchestrator — Pattern Map

**Mapped:** 2026-05-22
**Files analyzed:** 20 new files + 4 modified files (24 total)
**Analogs found:** 24 / 24 (1 partial — anti-oracle return handler combines two analogs)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/backend/.importlinter` (modify) | config | static | self (lines 13–98) | exact |
| `app/modules/online_payments/__init__.py` (new) | module marker | static | `app/modules/memberships/__init__.py:1` | exact |
| `app/modules/online_payments/constants.py` (new) | constants | static | `app/modules/payments/constants.py` | role+kind match |
| `app/modules/online_payments/models.py` (new) | ORM model | request-response | `app/modules/payments/models.py:44-118` | exact (append-only-ish, partial-UNIQUE indexes) |
| `app/modules/online_payments/repository.py` (new) | repository | CRUD | `app/modules/payments/repository.py:65-99` | exact (caller-owns-txn INSERT + GET) |
| `app/modules/online_payments/schemas.py` (new) | schemas | request-response | `app/modules/payments/schemas.py:63-79` + `app/modules/memberships/schemas.py` (envelope) | exact |
| `app/modules/online_payments/service.py` (new) | service / orchestrator | request-response + integration | `app/modules/memberships/service.py` (sale flow) + `app/modules/payments/service.py:90-140` (record + emit) | role-match (no single analog composes integration adapter + DB insert + 2-event audit chain — but the four primitives are well-precedented separately) |
| `app/modules/online_payments/router.py` (new) | router | request-response | `app/modules/memberships/router.py:280-373` (POST sell w/ Idempotency-Key) + `app/modules/payments/router.py:38-58` (typical RBAC) | exact |
| `app/modules/online_payments/permissions.py` (new, empty) | placeholder | static | `app/modules/payments/permissions.py:1-14` (docstring + module-only marker) | exact |
| `app/modules/online_payments/email_templates.py` (new, empty) | placeholder | static | `app/modules/payments/email_templates.py` | exact (placeholder shape) |
| `alembic/versions/0034_online_payments.py` (new) | migration | DDL | `alembic/versions/0033_clients_email_partial_unique.py` (partial-UNIQUE shape) + `app/modules/payments/models.py:97-118` (`Index(postgresql_where=...)` shape) | exact for partial-UNIQUE; table-create is standard |
| `app/main.py` (modify) | composition root | wiring | `app/main.py:317-327` (Phase 48 YooKassa stub-swap precedent) | exact |
| `app/modules/memberships/service.py` (modify — add stub) | service (Protocol-slot host) | wiring | `app/modules/memberships/service.py:resolve_active_membership_by_client` (Protocol delegate pattern) + `app/integrations/yookassa/_stubs.py:39-48` (stub body shape) | exact |
| `app/modules/pt_packages/service.py` (modify — add stub) | service (Protocol-slot host) | wiring | mirror of memberships above | exact |
| `app/workers/__init__.py` (modify — wire fiscal stub) | worker composition root | wiring | `app/workers/__init__.py:262-292` (Phase 48 yookassa stub double-wire) | exact |
| `tests/integrations/yookassa/conftest.py` (modify — add 2 fixtures) | test fixtures | mock | `tests/integrations/yookassa/conftest.py:39-87` | exact |
| `tests/modules/online_payments/__init__.py` (new) | test package marker | static | (no precedent under `tests/modules/`; create per `tests/integration/payments/__init__.py` shape) | role-match |
| `tests/modules/online_payments/conftest.py` (new) | test fixtures | mock | `tests/integrations/yookassa/conftest.py:49-56` (500/404 respx variant) | exact |
| `tests/modules/online_payments/test_service_sell_membership.py` (new) | integration test | mock + DB | `tests/integration/payments/test_*` (real-Postgres-via-testcontainers) | role+infra match |
| `tests/modules/online_payments/test_router_sell_endpoints.py` (new) | integration test | HTTP (ASGITransport) | router-style integration tests under `tests/integration/<module>/` | role-match |
| `tests/modules/online_payments/test_return_screen.py` (new) | integration test | HTTP + timing | `tests/unit/auth/test_*constant_time*` + perf-counter loop | role-match (combines HTTP + timing assert) |
| `tests/integration/test_v17_protocol_slot_parity.py` (new) | integration test | wiring assert | `tests/unit/test_yookassa_protocol_slot_parity.py:71-90` (Phase 48 4-slot check) + `tests/integration/test_app_wiring.py:58-112` (deps._slot is not None) | exact |
| `tests/integration/test_alembic_0034_online_payments.py` (new) | integration test | DDL introspection | `tests/integration/alembic/test_*` (no precedent for partial-UNIQUE assertion specifically — see `tests/integration/alembic/` for current shapes) | role-match |

---

## Pattern Assignments

### `apps/backend/.importlinter` (modify, D-49-02 + D-49-13)

**Analog:** self — lines 13–98 already enumerate the modules-independent contract + ignores; Phase 49 appends one line + one `ignore_imports` entry.

**Append to `[importlinter:contract:modules-independent] modules =` block** (currently `apps/backend/.importlinter:16-29`; the `# Phase 47 INFRA-40 — Option A deferral` comment on lines 30–39 explicitly documents that Phase 49 ships this append). Place the new entry **alphabetically** between `notifications` (line 25) and `payments` (line 26):

```ini
    app.modules.online_payments
```

**Append to `ignore_imports` list** (`.importlinter:81-91` already has 2 preemptive `online_payments.service` edges; Phase 49 adds **one** new edge for D-49-13). Insert after line 91:

```ini
    # Phase 49 PAY-06 / D-49-13 — client.email gate read; service-layer scoped;
    # no widening to repository. Mirrors Phase 45 NOTIFY-11/12/13 narrow-scope
    # precedent at lines 72-80 above.
    app.modules.online_payments.service -> app.modules.clients.models
```

**No change** to `unmatched_ignore_imports_alerting = warn` (line 98) — Phase 49 INFRA-40 audit confirms `warn` stays until Phase 52 ships `online_payments.email_templates` body.

---

### `app/modules/online_payments/__init__.py` (new, D-49-01)

**Analog:** `app/modules/memberships/__init__.py:1` — single-line module docstring, no re-exports in Phase 49.

```python
"""Online payments module — ЮKassa sales orchestrator (Phase 49 PAY-01..08)."""
```

Phase 49 does NOT re-export anything from `service.py` (unlike `pt_packages/__init__.py:14` which re-exports `resolve_active_pt_package`). The composition root wiring at `app/main.py` performs explicit `from app.modules.online_payments.service import ...` per the Phase 47 D-47-01 pattern.

---

### `app/modules/online_payments/constants.py` (new, Claude's discretion D-49-?)

**Analog:** `app/modules/payments/constants.py:1-22`.

**Pattern to copy** — flat module-level literals + tuple aggregate + explicit `__all__`:

```python
# apps/backend/app/modules/payments/constants.py:1-22 — full body
"""Payments module literal constants (Phase 32 D-32-09).
...
"""
SUBJECT_KIND_MEMBERSHIP = "membership"
...
SUBJECT_KIND_VALUES: tuple[str, ...] = (
    SUBJECT_KIND_MEMBERSHIP,
    ...
)
__all__ = (
    "SUBJECT_KIND_MEMBERSHIP",
    ...
)
```

**Extension for Phase 49** — also ship the `ErrorCode` StrEnum per CONTEXT.md §Claude's Discretion:

```python
from enum import StrEnum

class ErrorCode(StrEnum):
    CLIENT_EMAIL_REQUIRED = "client_email_required_for_online_payment"
    YOOKASSA_VALIDATION_ERROR = "yookassa_validation_error"
    YOOKASSA_UNAVAILABLE = "yookassa_unavailable"
    YOOKASSA_PERMANENT_ERROR = "yookassa_permanent_error"

STATUS_PENDING = "pending"
STATUS_SUCCEEDED = "succeeded"
STATUS_CANCELED = "canceled"
STATUS_VALUES: tuple[str, ...] = (STATUS_PENDING, STATUS_SUCCEEDED, STATUS_CANCELED)

CONFIRMATION_TYPE_REDIRECT = "redirect"
CONFIRMATION_TYPE_QR = "qr"

SUBJECT_KIND_MEMBERSHIP = "membership"
SUBJECT_KIND_PT_PACKAGE = "pt_package"
```

Mirror discipline from `payments/constants.py:55-64` lineage: literal strings here MUST equal the migration 0034 CHECK constraint values (cross-module pinning enforced by runtime CHECK + both files anchoring on migration literal).

---

### `app/modules/online_payments/models.py` (new, D-49-04)

**Analog:** `app/modules/payments/models.py:44-118` (`Payment` class).

**Imports pattern** (mirror `payments/models.py:21-41` verbatim):

```python
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, Index, Integer, Text,
    UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UUIDPkMixin
```

**Class composition** — `Base + UUIDPkMixin` ONLY (NO `TimestampMixin`, NO `SoftDeleteMixin`); FSM rows track lifecycle via `initiated_at`/`succeeded_at`/`canceled_at` explicit columns per `payments/models.py:46-49` single-temporal-column discipline. Status mutations are written by Phase 50 webhook handler.

**Column shape (D-49-04)** — copy the column declaration style from `payments/models.py:53-95`:

```python
class OnlinePayment(Base, UUIDPkMixin):
    """ЮKassa-side online payment ledger (Phase 49 PAY-01)."""

    __tablename__ = "online_payments"

    client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "clients.id",
            ondelete="RESTRICT",
            name="fk_online_payments_client_id_clients",
        ),
        nullable=False,
    )
    membership_plan_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "membership_plans.id",
            ondelete="RESTRICT",
            name="fk_online_payments_membership_plan_id_membership_plans",
        ),
        nullable=True,
    )
    pt_package_plan_id: Mapped[UUIDType | None] = mapped_column(...)  # mirror
    yookassa_payment_id: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    amount_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    confirmation_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmation_type: Mapped[str] = mapped_column(Text, nullable=False)
    initiated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    succeeded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL", name="fk_online_payments_created_by_user_id_users"),
        nullable=True,
    )
    audit_correlation_id: Mapped[UUIDType] = mapped_column(PgUUID(as_uuid=True), nullable=False)
```

**Table args — CHECK + partial-UNIQUE indexes** — copy the `__table_args__` declaration style from `payments/models.py:97-118` (specifically the `Index(name, ..., unique=True, postgresql_where=text("..."))` shape at line 109-113 for partial-UNIQUE in ORM). All four indexes from D-49-05 live here so `Base.metadata` carries them (autogenerate can be suppressed in `alembic/env.py:_include_object` per `memberships/models.py:1-12` precedent if needed).

```python
__table_args__ = (
    CheckConstraint("amount_kopecks > 0", name="amount_kopecks_positive"),
    CheckConstraint(
        "status IN ('pending','succeeded','canceled')",
        name="status",
    ),
    CheckConstraint(
        "confirmation_type IN ('redirect','qr')",
        name="confirmation_type",
    ),
    # XOR FK guard (D-49-04).
    CheckConstraint(
        "(membership_plan_id IS NOT NULL) <> (pt_package_plan_id IS NOT NULL)",
        name="exactly_one_subject_fk",
    ),
    UniqueConstraint("yookassa_payment_id", name="uq_online_payments_yookassa_payment_id"),
    UniqueConstraint("idempotency_key", name="uq_online_payments_idempotency_key"),
    Index(
        "uq_online_payments_membership_double_tap",
        "client_id", "membership_plan_id", text("DATE(initiated_at)"),
        unique=True,
        postgresql_where=text("status != 'canceled' AND membership_plan_id IS NOT NULL"),
    ),
    Index(
        "uq_online_payments_pt_package_double_tap",
        "client_id", "pt_package_plan_id", text("DATE(initiated_at)"),
        unique=True,
        postgresql_where=text("status != 'canceled' AND pt_package_plan_id IS NOT NULL"),
    ),
)
```

---

### `app/modules/online_payments/repository.py` (new, D-49-07)

**Analog:** `app/modules/payments/repository.py:65-99` (`insert_payment` + `get_payment_by_id`).

**Module top-doc** — copy caller-owns-txn discipline from `payments/repository.py:1-22`:

```python
"""Online payments repository — caller-owns-txn INSERT + GET (Phase 49 PAY-02 / D-49-07).

Caller-owns-txn (D-32-10 lineage): NO ``session.flush()``, NO ``session.commit()``
calls live here. The service layer owns the transactional moment so the audit
rows co-write with the online_payments INSERT in a single UoW.

No UPDATE methods in Phase 49 — status transitions are Phase 50 (webhook FSM).
"""
```

**Insert pattern** — copy `payments/repository.py:65-90` verbatim with field substitution:

```python
async def insert_online_payment(
    session: AsyncSession,
    *,
    client_id: UUID,
    membership_plan_id: UUID | None,
    pt_package_plan_id: UUID | None,
    yookassa_payment_id: str,
    idempotency_key: str,
    amount_kopecks: int,
    status: str,
    confirmation_url: str | None,
    confirmation_type: str,
    created_by_user_id: UUID | None,
    audit_correlation_id: UUID,
) -> OnlinePayment:
    """Insert OnlinePayment row; caller owns flush + audit emit (D-49-07)."""
    row = OnlinePayment(
        client_id=client_id,
        membership_plan_id=membership_plan_id,
        pt_package_plan_id=pt_package_plan_id,
        yookassa_payment_id=yookassa_payment_id,
        idempotency_key=idempotency_key,
        amount_kopecks=amount_kopecks,
        status=status,
        confirmation_url=confirmation_url,
        confirmation_type=confirmation_type,
        created_by_user_id=created_by_user_id,
        audit_correlation_id=audit_correlation_id,
    )
    session.add(row)
    return row
```

**Get-by-id pattern** — copy `payments/repository.py:93-99`:

```python
async def get_online_payment_by_id(
    session: AsyncSession, online_payment_id: UUID,
) -> OnlinePayment | None:
    stmt: Select[tuple[OnlinePayment]] = select(OnlinePayment).where(
        OnlinePayment.id == online_payment_id
    )
    return await session.scalar(stmt)
```

**Get-by-idempotency-key pattern** (D-49-08 replay check):

```python
async def get_online_payment_by_idempotency_key(
    session: AsyncSession, idempotency_key: str,
) -> OnlinePayment | None:
    stmt: Select[tuple[OnlinePayment]] = select(OnlinePayment).where(
        OnlinePayment.idempotency_key == idempotency_key
    )
    return await session.scalar(stmt)
```

---

### `app/modules/online_payments/schemas.py` (new, D-49-14 + Claude's discretion)

**Analog:** `app/modules/payments/schemas.py:1-79` (BackendSchemaBase usage + Field validators) + `app/core/schemas.py:36-82` (`BackendSchemaBase` / `ResponseData` / `envelope`).

**Imports pattern** (mirror `payments/schemas.py:12-21`):

```python
from __future__ import annotations
from uuid import UUID
from pydantic import Field, model_validator
from app.core.schemas import BackendSchemaBase, ResponseData
```

**Request shape**:

```python
class SellRequest(BackendSchemaBase):
    """POST /api/v1/online-payments/.../sell* body (Phase 49 PAY-03..05)."""
    client_id: UUID
```

**Response shape with XOR root validator** (per CONTEXT.md §Specifics):

```python
class SellResponse(ResponseData):
    confirmation_url: str | None = None
    qr_payload: str | None = None
    online_payment_id: UUID

    @model_validator(mode="after")
    def _exactly_one(self) -> "SellResponse":
        if (self.confirmation_url is None) == (self.qr_payload is None):
            raise ValueError("exactly one of confirmation_url / qr_payload must be set")
        return self
```

**Why `ResponseData` not `BackendSchemaBase` for `SellResponse`:** `payments/schemas.py:45` uses `ResponseData` for outbound DTOs. Camelcase alias-generator is inherited transitively from `ContractModel` (see `app/core/schemas.py:36-82`).

---

### `app/modules/online_payments/service.py` (new, D-49-08..20)

**Primary analog:** `app/modules/payments/service.py:90-140` (`record_payment` — orchestrator with audit emit + repo INSERT + caller-owns-txn marker).
**Secondary analog:** `app/modules/memberships/service.py:1-80` (module top-doc + cross-module imports through Protocol slots + service-layer audit-emit ordering).

**Module top-doc** — copy from `payments/service.py:1-24`:

```python
"""Online payments service — sell orchestrator (Phase 49 PAY-03..06 / D-49-08..20).

ORDER OF OPERATIONS (D-49-10):
  1. Validate clients.email present (D-49-12 — raise ClientEmailRequiredForOnlinePaymentError).
  2. Compute deterministic Idempotence-Key (D-49-08).
  3. Replay check via repository.get_online_payment_by_idempotency_key (D-49-09).
  4. Build receipt items via app.integrations.yookassa.receipt.build_receipt_item.
  5. Call YooKassaClient.create_payment (boundary returns YooKassaPaymentResult — never raises).
  6. Switch on result.classification:
     - ok → INSERT row → emit online_payment_initiated (ROOT) → emit yookassa_payment_created (CHILD) → 201
     - validation_error → raise ValidationAppError('yookassa_validation_error') (no DB row)
     - transient_error → raise ServiceUnavailableAppError('yookassa_unavailable') (no DB row)
     - permanent_error → raise BadGatewayAppError('yookassa_permanent_error') (no DB row)

The CALLER (router) owns the commit per caller-owns-txn discipline (D-32-10 / D-49-19).
The service does NOT call session.commit() — FastAPI dependency commits on response.

Cross-module imports (narrow-scope, per .importlinter ignore_imports):
  - app.modules.clients.models — D-49-13, scalar SELECT on Client.email gate.
  - app.modules.payments.models — D-49-29, TYPE_CHECKING only in Phase 49 (Phase 50
    flips to runtime when record_payment(method='online') is called from the webhook).
"""
```

**Imports pattern** (mirror `payments/service.py:26-44` + `memberships/service.py:64-80`):

```python
from __future__ import annotations
import asyncio
import time
from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING, Final, Literal
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.audit_payloads import (
    OnlinePaymentInitiatedPayload,
    YookassaPaymentCreatedPayload,
)
from app.core.dependencies import CurrentUser, get_yookassa_client_provider
from app.core.exceptions import (
    AppError, ConflictError, NotFoundError, ValidationAppError,
)
from app.integrations.yookassa.client import YooKassaClient
from app.integrations.yookassa.receipt import (
    PaymentMode, PaymentSubject, VatCode, build_receipt_item,
)
from app.modules.clients.models import Client  # D-49-13 — narrow ignore_imports
from app.modules.online_payments import repository
from app.modules.online_payments.constants import (
    CONFIRMATION_TYPE_QR, CONFIRMATION_TYPE_REDIRECT,
    ErrorCode, STATUS_PENDING,
    SUBJECT_KIND_MEMBERSHIP, SUBJECT_KIND_PT_PACKAGE,
)
from app.modules.online_payments.models import OnlinePayment

if TYPE_CHECKING:
    # D-49-29 — Phase 49 imports defensively for type discipline; Phase 50
    # flips this to a runtime import when record_payment(method='online') is
    # called from the webhook handler. Keeps grimp's modules-independent
    # contract honest (TYPE_CHECKING imports DO count toward grimp's graph
    # — that's the point: the ignore_imports edge is matched even now).
    from app.modules.payments.models import Payment  # noqa: F401

_log = structlog.get_logger("modules.online_payments.service")
```

**Deterministic-key helper** (D-49-08):

```python
def _derive_idempotency_key(*, subject_kind: str, plan_id: UUID, client_id: UUID) -> str:
    """Deterministic Idempotence-Key per PAY-03 (D-49-08).

    UTC today_iso (NOT Europe/Moscow — wire-protocol key must be stable
    across DST transitions; CLAUDE.md MSK convention applies to user-facing
    dates only).
    """
    today_iso = datetime.now(tz=UTC).date().isoformat()
    raw = f"sell-{subject_kind}:{plan_id}:{client_id}:{today_iso}"
    return sha256(raw.encode("utf-8")).hexdigest()
```

**`ClientEmailRequiredForOnlinePaymentError` exception** — copy class shape from `app/core/exceptions.py:48-50` + `:108-112` (subclass with locked code):

```python
# Lives in app/core/exceptions.py (D-49-12) — NOT in service.py:
class ClientEmailRequiredForOnlinePaymentError(ValidationAppError):
    """Raised by service.sell_* when clients.email IS NULL (Phase 49 PAY-06 / D-49-12).

    Error code is LOCKED LITERAL per REQUIREMENTS.md PAY-06 + ROADMAP.md
    success-criterion #3: ``client_email_required_for_online_payment``.
    """
    code = "client_email_required_for_online_payment"
    status_code = 422
```

**Email-gate scalar SELECT pattern** (D-49-12):

```python
async def _read_client_email_or_raise(
    session: AsyncSession, client_id: UUID,
) -> str:
    """FIS-05 gate (D-49-12): raise if clients.email IS NULL.

    Scalar SELECT on Client.email — does NOT load full row. The Client ORM
    import is narrow-scoped per D-49-13 ignore_imports.
    """
    email: str | None = await session.scalar(
        select(Client.email).where(Client.id == client_id)
    )
    if email is None:
        raise ClientEmailRequiredForOnlinePaymentError(
            ErrorCode.CLIENT_EMAIL_REQUIRED.value
        )
    return email
```

**Audit chain emission (D-49-19)** — closest precedent is `payments/service.py:126-139` (`audit.emit(... payload kwargs ...)`). Pattern diverges slightly because v1.7 payloads (`OnlinePaymentInitiatedPayload`) are validated Pydantic models, not free-form kwargs — so service must build the model instance first:

```python
# After repository.insert_online_payment(...) succeeds:
# 1. Emit ROOT (audit_correlation_id=None per payload semantics):
initiated_payload = OnlinePaymentInitiatedPayload(
    audit_correlation_id=None,  # chain ROOT marker (D-49-19)
    online_payment_id=row.id,
    client_id=row.client_id,
    amount_kopecks=row.amount_kopecks,
    subject_kind=subject_kind,  # Literal["membership","pt_package"]
    subject_id=row.membership_plan_id or row.pt_package_plan_id,
)
await audit.emit(
    session,
    "online_payment_initiated",
    actor_user_id=actor.id,
    resource_type="online_payment",
    resource_id=row.id,
    **initiated_payload.model_dump(mode="json"),
)

# 2. Emit CHILD (audit_correlation_id=row.audit_correlation_id):
created_payload = YookassaPaymentCreatedPayload(
    audit_correlation_id=row.audit_correlation_id,  # chain link
    online_payment_id=row.id,
    yookassa_payment_id=row.yookassa_payment_id,
    idempotency_key=row.idempotency_key,
    confirmation_type=row.confirmation_type,
)
await audit.emit(
    session,
    "yookassa_payment_created",
    actor_user_id=actor.id,
    resource_type="online_payment",
    resource_id=row.id,
    **created_payload.model_dump(mode="json"),
)
```

**Reference for payload-keyed `audit.emit` call shape:** `app/core/audit.py:381-488` documents that v1.7 events MUST pass through validated payload kwargs (the schema lookup at line 464 enforces this). Compare with `payments/service.py:126-139` which still uses pre-v1.6 free-form kwargs.

**Sell-function skeleton** (memberships variant; mirror for pt_packages):

```python
async def sell_membership(  # noqa: SVC001 caller-owns-txn — router owns UoW
    session: AsyncSession,
    *,
    plan_id: UUID,
    client_id: UUID,
    confirmation_type: Literal["redirect", "qr"],
    actor: CurrentUser,
) -> SellResponse:
    """Sell a membership online (Phase 49 PAY-03/05)."""
    # 1. FIS-05 email gate.
    customer_email = await _read_client_email_or_raise(session, client_id)

    # 2. Deterministic key.
    idem_key = _derive_idempotency_key(
        subject_kind=SUBJECT_KIND_MEMBERSHIP,
        plan_id=plan_id,
        client_id=client_id,
    )

    # 3. Replay check (D-49-09).
    existing = await repository.get_online_payment_by_idempotency_key(session, idem_key)
    if existing is not None and existing.status != "canceled":
        return SellResponse(
            confirmation_url=existing.confirmation_url,
            qr_payload=None,  # Phase 49 stores no qr_payload; recompute path Phase 50+
            online_payment_id=existing.id,
        )

    # 4. Build receipt + 5. call ЮKassa.
    receipt_items = [build_receipt_item(
        description="Абонемент",  # TODO Phase 50: plan-name lookup
        amount_kopecks=...,  # plan.price_kopecks lookup
        payment_subject=PaymentSubject.SERVICE,
        payment_mode=PaymentMode.FULL_PREPAYMENT,
        vat_code=VatCode.VAT_NONE,
    )]
    provider = get_yookassa_client_provider()
    client: YooKassaClient = await provider()
    result = await client.create_payment(
        amount_kopecks=...,
        description="Абонемент",
        receipt_items=receipt_items,
        customer_email=customer_email,
        idempotency_key=UUID(idem_key[:32]),  # NOTE: client expects UUID not sha256 — VERIFY shape, see Wave 1 verifier note
    )

    # 6. Switch on classification.
    if result.classification == "ok":
        row = await repository.insert_online_payment(
            session,
            client_id=client_id,
            membership_plan_id=plan_id,
            pt_package_plan_id=None,
            yookassa_payment_id=result.payment_id,  # type: ignore[arg-type]
            idempotency_key=idem_key,
            amount_kopecks=result.amount_kopecks,  # type: ignore[arg-type]
            status=STATUS_PENDING,
            confirmation_url=result.confirmation_url,
            confirmation_type=confirmation_type,
            created_by_user_id=actor.id,
            audit_correlation_id=uuid4(),
        )
        await session.flush()  # surface FK + CHECK + UNIQUE conflicts before audit
        # ... audit chain emission as shown above ...
        return SellResponse(
            confirmation_url=row.confirmation_url,
            qr_payload=None,  # Phase 49 redirect-only happy path; QR Wave 1 verifier
            online_payment_id=row.id,
        )
    if result.classification == "validation_error":
        raise ValidationAppError(ErrorCode.YOOKASSA_VALIDATION_ERROR.value)
    if result.classification == "transient_error":
        raise _ServiceUnavailableAppError(ErrorCode.YOOKASSA_UNAVAILABLE.value)
    # permanent_error fallthrough:
    raise _BadGatewayAppError(ErrorCode.YOOKASSA_PERMANENT_ERROR.value)
```

**Wave 1 verifier note (D-49-CL-DISCRETION):** check `app/integrations/yookassa/types.py:51-80` `YooKassaPaymentResult` for a `qr_payload` field. **Current state (verified):** `YooKassaPaymentResult` has `confirmation_url: str | None` but NO `qr_payload` field (`types.py:75`). Wave 1 MUST either (a) extend the dataclass with `qr_payload: str | None = None` AND extend `YooKassaClient.create_payment` to populate it from `confirmation.confirmation_data`, OR (b) flag to the planner that QR sell endpoints are blocked on a Phase 48 patch. Also verify the `create_payment` call signature: line 132-141 takes `idempotency_key: UUID` — NOT a sha256 hex string. The D-49-08 deterministic key is a **sha256 hex digest**; the adapter expects a UUID. Either (i) the adapter signature must change to accept `str`, or (ii) the deterministic key must be deterministic-UUID (sha256→32-byte→UUID). Planner MUST resolve.

**Two new AppError subclasses needed** (place in `app/core/exceptions.py` per `:48` lineage):

```python
class ServiceUnavailableAppError(AppError):
    code = "service_unavailable"
    status_code = 503

class BadGatewayAppError(AppError):
    code = "bad_gateway"
    status_code = 502
```

**Membership-activator stub (D-49-21)** — placed in `app/modules/memberships/service.py`, NOT in online_payments. Signature mirrors `app/integrations/yookassa/_stubs.py:39-48` shape but lives in the OWNING module so the wiring `register_membership_activator(activate_membership_from_webhook)` does not cross modules-independent boundary (the call lives in `app/main.py` which is exempt — see `main.py:11-13`):

```python
# Append to app/modules/memberships/service.py:
async def activate_membership_from_webhook(
    session: AsyncSession,
    *,
    membership_id: UUID,
    audit_correlation_id: UUID | None,
) -> Any:
    """MembershipActivator slot implementation (Phase 49 D-49-21 STUB / Phase 50 WH-05 BODY).

    Phase 49 ships the wiring + signature ONLY; body raises NotImplementedError
    so the success-criterion #6 parity test sees a non-None slot. Phase 50
    fills the body with the real activation logic that runs inside the
    webhook handler's AsyncSession.
    """
    raise NotImplementedError(
        "Phase 50 WH-05 wires the activation body — Phase 49 only registers "
        "the slot so the parity test passes."
    )
```

**Same shape for `activate_pt_package_from_webhook` in `app/modules/pt_packages/service.py`.**

**Phase-49-only fiscal-dispatcher stub** (D-49-22) — lives in `app/modules/online_payments/service.py`:

```python
async def phase49_fiscal_dispatcher_stub(
    *,
    fiscal_receipt_id: UUID,
    audit_correlation_id: UUID | None,
) -> None:
    """Phase-49-only bridge for the FiscalReceiptDispatcher slot (D-49-22).

    Replaces the Phase 47 noop_stub so the parity test passes; Phase 50
    FISCAL-01 swaps this for the real ARQ-enqueue body.
    """
    raise NotImplementedError(
        "Phase 50 FISCAL-01 wires real dispatch — Phase 49 only registers "
        "the slot non-None so the parity test passes."
    )
```

---

### `app/modules/online_payments/router.py` (new, D-49-14..18, D-49-25..26)

**Analog (sell endpoints):** `app/modules/memberships/router.py:280-373` (`create_membership` — POST sell w/ Idempotency-Key + verify_csrf + RBAC-04 ordering).
**Analog (read endpoints / simple GET):** `app/modules/payments/router.py:38-58` (simpler shape without Idempotency-Key).

**Imports pattern** — copy `memberships/router.py:67-102`:

```python
from __future__ import annotations
import asyncio
import time
from typing import Annotated, Final, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission, verify_csrf
from app.core.permissions import Action, Resource
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.online_payments import service
from app.modules.online_payments.schemas import SellRequest, SellResponse

router = APIRouter()
```

**RBAC-04 ordering — the critical invariant** — `memberships/router.py:289-300`:

```python
async def create_membership(
    payload: MembershipCreateRequest,
    request: Request,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.MEMBERSHIPS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    idempotency_key: Annotated[str, Depends(verify_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
```

**Apply this signature ordering verbatim** for all 4 sell endpoints — `require_permission` BEFORE `verify_csrf` BEFORE `verify_idempotency` (the order matters for 401→403→422 ordering enforced by `tests/integration/test_route_introspection.py`).

**Sell endpoint skeleton** (membership-redirect variant — mirror 3 more times):

```python
@router.post(
    "/memberships/{plan_id}/sell",
    response_model=ResponseEnvelope[SellResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Sell a membership online (redirect flow); CSRF + Idempotency-Key required",
)
async def sell_membership_redirect(
    plan_id: UUID,
    payload: SellRequest,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.MEMBERSHIPS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    _idem_key: Annotated[str, Depends(verify_idempotency)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[SellResponse]:
    response = await service.sell_membership(
        session,
        plan_id=plan_id,
        client_id=payload.client_id,
        confirmation_type="redirect",
        actor=actor,
    )
    return envelope(response)
```

**Decision (planner):** Phase 49 router can either reuse `memberships/router.py:280-373` full outer-Redis idempotency dance (D-49-16 two-layer model) OR rely on `verify_idempotency` validation only and skip the SET-NX replay block. CONTEXT.md D-49-16 mandates the full two-layer model; copy the **entire `create_membership` body** at `memberships/router.py:301-373` (the 5-step `begin_idempotency` + `load_idempotency_response` + envelope-cache flow) verbatim with `service.sell_membership` substituted for `service.create_membership`.

**Anti-oracle return handler (D-49-17/18)** — copy CONTEXT.md §Specifics literal:

```python
_RETURN_HTML: Final[str] = (
    "<!doctype html><html lang=\"ru\"><head>"
    "<meta charset=\"utf-8\"><title>Оплата</title>"
    "</head><body>"
    "<h1>Оплата получена</h1>"
    "<p>Ожидаем подтверждение от платёжной системы. "
    "Эту страницу можно закрыть.</p>"
    "</body></html>"
)
_RETURN_FLOOR_SECONDS: Final[float] = 0.050


@router.get(
    "/return",
    include_in_schema=False,  # PAY-07 — not documented
)
async def online_payment_return() -> Response:
    """PAY-07 anonymous-by-design return-URL screen — no auth, no CSRF, no DB.

    Constant-time floor (D-49-18) mirrors auth/service.py:_constant_time_floor
    discipline (anti-oracle uniformity). Body is STATIC HTML — does not branch
    on query params; query params are accepted via request.query_params but
    discarded (D-49-17).
    """
    start = time.perf_counter()
    response = Response(
        content=_RETURN_HTML,
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "no-store, max-age=0"},
    )
    elapsed = time.perf_counter() - start
    await asyncio.sleep(max(0.0, _RETURN_FLOOR_SECONDS - elapsed))
    return response
```

**Constant-time-floor analog:** `app/modules/auth/service.py:945-956` (`_constant_time_floor` helper) and `app/modules/auth/password_reset_service.py:117-125`. Both use the same `time.perf_counter()` + `asyncio.sleep(max(0, floor - elapsed))` shape. The Phase 49 implementation **embeds** the floor directly in the handler instead of extracting a helper because there is exactly one callsite. If Phase 50 adds a second callsite, extract to a helper.

**RBAC-04 exemption for `/return`:** the handler MUST be added to `tests/integration/test_route_introspection.py:EXCLUDED_PATHS` (lines 27–42) as `"/api/v1/online-payments/return"`. Document per D-49-26 inline rationale block. ALSO add `verify_yookassa_ip` is NOT applied here — `/return` is hit by user browsers, NOT by ЮKassa's IP-allowlisted callback (that's the Phase 50 webhook).

---

### `app/modules/online_payments/permissions.py` (new, empty per D-49-01)

**Analog:** none exact — empty-placeholder file. Use this content:

```python
"""Online payments permissions placeholder (Phase 49 D-49-01 / D-49-24).

EMPTY by design. PAY endpoints reuse existing (CREATE, MEMBERSHIPS) and
(CREATE, PT_PACKAGES) permission pairs from app.core.permissions — neither
is in OWNER_ONLY (both are reception+owner). No local can-checks needed.

Phase 52 NOTIFY-xx may add notification-channel can-checks here.
"""
```

---

### `app/modules/online_payments/email_templates.py` (new, empty per D-49-01)

**Analog:** none exact — empty-placeholder file. Use this content (this satisfies the existing Phase 47 import-linter ignore at `.importlinter:123`):

```python
"""Online payments email templates placeholder (Phase 49 D-49-01).

EMPTY by design — Phase 52 NOTIFY-xx ships template bodies. This file
exists in Phase 49 SOLELY so the import-linter ignore
``app.integrations.email.dispatcher → app.modules.online_payments.email_templates``
(.importlinter:123) becomes MATCHED, dropping the `warn` for that one edge.

Importing this module from production code in Phase 49 yields an empty
namespace — there are no template identifiers registered until Phase 52.
"""
```

---

### `alembic/versions/0034_online_payments.py` (new, D-49-05/06)

**Analog:** `alembic/versions/0033_clients_email_partial_unique.py` (partial-UNIQUE shape + revision pattern).

**Revision header pattern** (copy from `0033:1-46`):

```python
"""online_payments table + 4 indexes (Phase 49 PAY-01 / PAY-02 / D-49-05).

Revision ID: 0034_online_payments
Revises: 0033_clients_email_partial_unique
Create Date: 2026-05-22 00:00:00.000000

Phase 49 PAY-01/PAY-02 schema. Ships table + 2 full UNIQUEs + 2 partial
UNIQUE double-tap guards in ONE migration (atomic per success-criterion #5).

Partial UNIQUE indexes mirror the Phase 16/30 pattern of one constraint
per subject_kind (membership vs pt_package) instead of a polymorphic
single index. WHERE predicate ``status != 'canceled' AND <fk> IS NOT NULL``
allows retry after explicit cancellation (PITFALLS Pitfall 3).
"""

from __future__ import annotations
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID as PgUUID

from alembic import op

revision: str = "0034_online_payments"
down_revision: str | None = "0033_clients_email_partial_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**Partial-UNIQUE shape** — copy `0033:73-79` verbatim (the `postgresql_where=text("...")` pattern):

```python
op.create_index(
    "uq_online_payments_membership_double_tap",
    "online_payments",
    ["client_id", "membership_plan_id", sa.text("DATE(initiated_at)")],
    unique=True,
    postgresql_where=text(
        "status != 'canceled' AND membership_plan_id IS NOT NULL"
    ),
)
```

**Downgrade pattern** — copy `0033:82-85` (drop_index then drop_table):

```python
def downgrade() -> None:
    op.drop_index("uq_online_payments_pt_package_double_tap", table_name="online_payments")
    op.drop_index("uq_online_payments_membership_double_tap", table_name="online_payments")
    op.drop_index("uq_online_payments_idempotency_key", table_name="online_payments")
    op.drop_index("uq_online_payments_yookassa_payment_id", table_name="online_payments")
    op.drop_table("online_payments")
```

**No pre-flight duplicate check needed** (unlike 0033) — `online_payments` is a NEW table; no live rows to dedup.

**Autogenerate suppression check** — D-49-05 notes that `DATE(initiated_at)` may misclassify in autogenerate. The current `alembic/env.py:_include_object` already suppresses expression indexes for `uq_membership_plans_name_alive` (per `memberships/models.py:1-12`). Wave 1 plan: run `alembic check` after Wave-1 commit; if autogenerate emits noise for the partial indexes, add them to `_include_object` suppression list.

---

### `app/main.py` (modify, D-49-21/22)

**Analog:** `app/main.py:301-327` (Phase 47/48 ЮKassa stub wiring) — Phase 49 swaps the 3 noop stubs to real-but-stub-body functions.

**Diff to apply** at `app/main.py:325-327`:

```python
# REPLACE:
register_fiscal_receipt_dispatcher(fiscal_receipt_dispatcher_noop_stub)
register_membership_activator(membership_activator_noop_stub)
register_pt_package_activator(pt_package_activator_noop_stub)

# WITH:
# Phase 49 D-49-21 — HTTP-only single-wire activators (no ARQ entry path).
from app.modules.memberships.service import activate_membership_from_webhook
from app.modules.pt_packages.service import activate_pt_package_from_webhook
from app.modules.online_payments.service import phase49_fiscal_dispatcher_stub

register_membership_activator(activate_membership_from_webhook)
register_pt_package_activator(activate_pt_package_from_webhook)
# Phase 49 D-49-22 — FiscalReceiptDispatcher Phase-49-only bridge stub
# (REG-29-03 double-wire; mirror in workers/__init__.py). Phase 50 FISCAL-01
# replaces this with the real ARQ-enqueue body.
register_fiscal_receipt_dispatcher(phase49_fiscal_dispatcher_stub)
```

**Remove imports** of 3 noop stubs at `app/main.py:81-85` (the `fiscal_receipt_dispatcher_noop_stub`, `membership_activator_noop_stub`, `pt_package_activator_noop_stub` no longer used). Document the removal inline.

**Local imports inside `create_app()`** (per the precedent at `app/main.py:217-219` for `clients_service` and `:241-243` for `payments_service`) — keeps the composition-root carve-outs visible AND avoids top-level cycle.

---

### `app/workers/__init__.py` (modify, D-49-22 REG-29-03)

**Analog:** `app/workers/__init__.py:262-292` (Phase 48 yookassa stub wiring in `WorkerSettings.on_startup`) — Phase 49 swaps `register_fiscal_receipt_dispatcher(fiscal_receipt_dispatcher_noop_stub)` (line 292) for the Phase-49 bridge stub.

**Diff** at line 292:

```python
# REPLACE:
register_fiscal_receipt_dispatcher(fiscal_receipt_dispatcher_noop_stub)

# WITH:
from app.modules.online_payments.service import phase49_fiscal_dispatcher_stub
register_fiscal_receipt_dispatcher(phase49_fiscal_dispatcher_stub)
```

**Worker does NOT register `MembershipActivator` / `PtPackageActivator`** — both are HTTP-only single-wire per `app/core/dependencies.py:1058-1070` and `:1128-1140` docstrings. Phase 49 preserves this asymmetry.

**Worker MUST be regenerated for parity test**:`tests/unit/test_yookassa_protocol_slot_parity.py:71-90` will need an update so that the parity test no longer expects byte-equal `fiscal_receipt_dispatcher_noop_stub`. See test changes below.

---

### `tests/integrations/yookassa/conftest.py` (modify, D-49-27)

**Analog:** self — `conftest.py:39-87` (6 existing respx fixtures).

**Decision (D-49-27):** the 500/404 respx fixtures land in a NEW `tests/modules/online_payments/conftest.py`, NOT in the Phase 48 shared conftest. **No modification to the Phase 48 conftest** in Phase 49.

---

### `tests/modules/online_payments/conftest.py` (new, D-49-27)

**Analog:** `tests/integrations/yookassa/conftest.py:49-56` — copy fixture shape with status-code substitution.

```python
@pytest.fixture
def yookassa_create_payment_500() -> Generator[respx.MockRouter, None, None]:
    """Phase 49 D-49-27 — POST /v3/payments → 500 (transient_error classification)."""
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(return_value=httpx.Response(500, json={"type": "error", "code": "internal"}))
        yield router


@pytest.fixture
def yookassa_create_payment_404() -> Generator[respx.MockRouter, None, None]:
    """Phase 49 D-49-27 — POST /v3/payments → 404 (permanent_error classification)."""
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(return_value=httpx.Response(404, json={"type": "error", "code": "not_found"}))
        yield router
```

---

### `tests/integration/test_v17_protocol_slot_parity.py` (new, D-49-23)

**Analog:** `tests/unit/test_yookassa_protocol_slot_parity.py:71-90` (Phase 48 4-slot check using the accessor functions) + `tests/integration/test_app_wiring.py:58-112` (the deps._slot is not None pattern).

**Skeleton** — combines the accessor-based check (Phase 48 lineage) with the all-slots assert pattern (`test_app_wiring.py:58-112`):

```python
"""Phase 49 D-49-23 — v1.7 Protocol slot parity test (success-criterion #6).

After create_app() + (simulated) WorkerSettings.on_startup, all 4 v1.7
Protocol slot accessors return non-None objects WITHOUT raising
RuntimeError. Mirrors the v1.6 EmailDispatcher / PaymentRecorder parity
tests in tests/integration/test_app_wiring.py.

Phase 49 D-49-22: FiscalReceiptDispatcher is wired to a stub-body callable
(phase49_fiscal_dispatcher_stub), NOT the Phase 47 noop_stub. Test asserts
the closure NAME is not 'fiscal_receipt_dispatcher_noop_stub' (regression
guard — Phase 50 must replace the bridge stub with the real body).
"""

from __future__ import annotations

import app.core.dependencies as deps
from app.core.dependencies import (
    get_fiscal_receipt_dispatcher,
    get_membership_activator,
    get_pt_package_activator,
    get_yookassa_client_provider,
)
from app.main import create_app


def _reset_v17_slots() -> None:
    deps._yookassa_client_provider = None
    deps._fiscal_receipt_dispatcher = None
    deps._membership_activator = None
    deps._pt_package_activator = None


def test_v17_protocol_slots_non_none_after_app_startup() -> None:
    _reset_v17_slots()
    create_app()
    assert get_yookassa_client_provider() is not None
    assert get_fiscal_receipt_dispatcher() is not None
    assert get_membership_activator() is not None
    assert get_pt_package_activator() is not None


def test_fiscal_receipt_dispatcher_is_not_phase47_noop_stub_after_phase49() -> None:
    """D-49-22 regression guard — Phase 49 swap kept."""
    from app.integrations.yookassa._stubs import fiscal_receipt_dispatcher_noop_stub
    _reset_v17_slots()
    create_app()
    assert get_fiscal_receipt_dispatcher() is not fiscal_receipt_dispatcher_noop_stub
```

**Update needed in existing `tests/unit/test_yookassa_protocol_slot_parity.py`:** the byte-equal `is fiscal_receipt_dispatcher_noop_stub` assertion at lines 65-68 + the equivalent Test C body will fail after Phase 49 lands. Decision (planner): EITHER (a) relax that test to structural check (mirror lines 80-89 Phase 48 D-48-25 precedent for YooKassaClientProvider), OR (b) replace the asserted target with `phase49_fiscal_dispatcher_stub`. Recommended: (b) — keeps the byte-equal parity property meaningful.

---

### `tests/integration/test_alembic_0034_online_payments.py` (new)

**Analog:** no direct precedent for partial-UNIQUE assertion under `tests/integration/alembic/` — closest is the `_responses` directory's existing alembic integration tests. Recommend the minimum-viable shape:

```python
"""Phase 49 — assert 0034 ships the 4 indexes (D-49-05)."""

from sqlalchemy import inspect
# ... fixture-based postgres session ...

def test_online_payments_table_has_4_indexes(session) -> None:
    inspector = inspect(session.bind)
    indexes = {ix["name"] for ix in inspector.get_indexes("online_payments")}
    assert "uq_online_payments_yookassa_payment_id" in indexes
    assert "uq_online_payments_idempotency_key" in indexes
    assert "uq_online_payments_membership_double_tap" in indexes
    assert "uq_online_payments_pt_package_double_tap" in indexes
```

Planner to settle exact fixture conventions per the existing alembic test under `tests/integration/test_alembic_clean.py`.

---

## Shared Patterns

### Caller-owns-txn discipline
**Source:** `app/modules/payments/service.py:90-140` + `app/modules/payments/repository.py:1-22`
**Apply to:** `online_payments/repository.py`, `online_payments/service.py`
**Rule:** Repository NEVER calls `session.flush()` or `session.commit()`. Service flushes after INSERT to surface FK/CHECK/UNIQUE conflicts BEFORE audit emit (`payments/service.py:117`). FastAPI dependency (`get_db`) owns the commit.
**Marker:** `# noqa: SVC001 caller-owns-txn — router owns UoW` on service functions that are public Protocol-slot consumers (`payments/service.py:90`).

### RBAC-04 ordering invariant
**Source:** `app/modules/memberships/router.py:289-300` + statically enforced by `tests/integration/test_route_introspection.py`
**Apply to:** all 4 POST sell endpoints in `online_payments/router.py`
**Rule:** Function signature MUST declare `Depends(require_permission(...))` BEFORE `Depends(verify_csrf)` BEFORE `Depends(verify_idempotency)`. FastAPI resolves signature dependencies in declaration order, so 401 fires before 403 before 422.
**Exception:** `GET /online-payments/return` has NO gate — add path to `tests/integration/test_route_introspection.py:EXCLUDED_PATHS` (D-49-26).

### Locked-event audit emit
**Source:** `app/core/audit.py:381-488` + `app/core/audit_payloads.py:738-777` (Phase 49 payloads already shipped)
**Apply to:** `online_payments/service.py` — `online_payment_initiated` (ROOT, audit_correlation_id=None) + `yookassa_payment_created` (CHILD, audit_correlation_id=row.audit_correlation_id)
**Rule:** Pre-v1.6 events used free-form `**payload` kwargs (`payments/service.py:126-139`); v1.7 events MUST pass through validated `Payload` model — schema lookup at `audit.py:464` enforces this. Build the model first, then unpack via `**payload.model_dump(mode="json")` into `audit.emit(...)`.
**Both emits MUST share the SAME `AsyncSession`** as the `online_payments` INSERT (single UoW per D-49-19 + Phase 4 caller-owns-txn).

### Result classification at integration boundary
**Source:** `app/integrations/yookassa/client.py:132-235` + `app/integrations/yookassa/types.py:51-80`
**Apply to:** `online_payments/service.py:sell_membership` (and pt_package mirror)
**Rule:** `YooKassaClient.create_payment` returns `YooKassaPaymentResult` — NEVER raises across the integration boundary. Service switches on `result.classification` literal (`'ok' | 'validation_error' | 'transient_error' | 'permanent_error'`) — no try/except needed. Map non-`ok` variants to AppError subclasses per D-49-10.

### Protocol slot wiring (REG-29-03 / D-47-01)
**Source:** `app/core/dependencies.py:940-1194` (4 v1.7 slot declarations) + `app/main.py:301-327` (Phase 48 wiring) + `app/workers/__init__.py:262-292` (REG-29-03 mirror)
**Apply to:** `app/main.py` + `app/workers/__init__.py` (D-49-21/22)
**Rule:** Single-wire (HTTP-only) for `MembershipActivator` + `PtPackageActivator`; double-wire (FastAPI + ARQ) for `FiscalReceiptDispatcher`. Idempotent register_* allow test override via `create_app()`.

### Constant-time floor for anti-oracle
**Source:** `app/modules/auth/service.py:945-956` (`_constant_time_floor`) + `app/modules/auth/password_reset_service.py:117-125` (inline variant)
**Apply to:** `online_payments/router.py:online_payment_return` (D-49-18)
**Rule:** `start = time.perf_counter()` → build response → `elapsed = time.perf_counter() - start` → `await asyncio.sleep(max(0.0, FLOOR - elapsed))`. Phase 49 inlines (one callsite); extract to helper if Phase 50+ adds more callsites.

### Cross-module narrow ignore_imports
**Source:** `.importlinter:63-91` (Phase 45 NOTIFY-11/12/13 precedent + Phase 47 INFRA-40 preemptive entries)
**Apply to:** `.importlinter` (D-49-13 adds `online_payments.service → clients.models`)
**Rule:** Always scope at `<module>.service` granularity, NEVER widen to `<module>.repository` or `<module>` (the whole package). Document inline with phase-decision pointer.

### BackendSchemaBase + envelope wire format
**Source:** `app/core/schemas.py:36-82` + `app/modules/payments/schemas.py:1-79`
**Apply to:** `online_payments/schemas.py`, `online_payments/router.py`
**Rule:** Request bodies subclass `BackendSchemaBase` (camelCase via alias_generator; `extra='forbid'`). Response payloads subclass `ResponseData`. Router returns `ResponseEnvelope[T]` via `envelope(payload)` helper.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| (none) | — | — | Every Phase 49 file has at least a role-match analog in the codebase. |

The `GET /online-payments/return` handler is the closest thing to a novel pattern — it combines (a) `Response(content=..., media_type="text/html")` (no existing precedent for explicit text/html in production routes; healthz returns JSON), (b) the constant-time floor (precedent: `auth/service.py:945-956`), and (c) anonymous-by-design (precedent: `tests/integration/test_route_introspection.py:EXCLUDED_PATHS`). Each piece has an analog; only the composition is new.

---

## Metadata

**Analog search scope:** `apps/backend/app/modules/{memberships,payments,pt_packages,auth,clients,users}/`, `apps/backend/app/core/{dependencies,exceptions,audit,audit_payloads,schemas,idempotency}.py`, `apps/backend/app/integrations/yookassa/*.py`, `apps/backend/alembic/versions/00{31..33}_*.py`, `apps/backend/tests/{integration,integrations,unit}/`.

**Files scanned:** 24 source files + 6 test files + 3 config files = 33 distinct files (no re-reads).

**Pattern extraction date:** 2026-05-22.

**Cross-cutting verifier notes for planner:**
1. **`YooKassaPaymentResult.qr_payload`** field does NOT exist in Phase 48 `types.py:51-80`. Wave 1 MUST extend the dataclass OR planner must split QR endpoints into a Phase-49.5 follow-up.
2. **`YooKassaClient.create_payment(idempotency_key=...)`** at `client.py:132-141` expects `UUID`, not the sha256 hex string from D-49-08. Wave 1 MUST settle the type mismatch (change adapter signature OR derive deterministic-UUID from sha256).
3. **Parity test update** at `tests/unit/test_yookassa_protocol_slot_parity.py:65-68` (and Test C body): change byte-equal target from `fiscal_receipt_dispatcher_noop_stub` to `phase49_fiscal_dispatcher_stub`. Plan 49-06 (composition-root wiring) MUST include this test edit or it ships red.
4. **Plan-ordering preview** (D-49-32): Wave 1 (49-01 Alembic, 49-02 module skeleton + import-linter) is sequential and bedrock. Wave 2 (49-03 service, 49-04 router, 49-05 return handler, 49-06 composition root) is parallelizable. Wave 3 (49-07 E2E tests) is sequential and depends on all of Wave 2.
