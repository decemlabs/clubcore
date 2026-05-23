# Phase 51: Fiscal FSM + Refunds - Pattern Map

**Mapped:** 2026-05-23
**Files analyzed:** 23 new files + ~8 modified files
**Analogs found:** 23 / 23 (every new file has an exact or role-match analog in tree)

> **Important migration number correction**
> CONTEXT.md D-51-06 references `0036_online_refunds`. The repository already
> ships `apps/backend/alembic/versions/0036_payments_received_by_user_id_nullable.py`
> (Phase 50 Plan 50-03 Blocker #2). **Phase 51 migration must be numbered
> `0037_online_refunds.py` with `down_revision = "0036_payments_received_by_user_id_nullable"`**.
> Planner MUST flag this to update CONTEXT.md or accept the renumber inline.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/backend/alembic/versions/0037_online_refunds.py` | migration | schema-DDL | `alembic/versions/0034_online_payments.py` | exact (mirror table + 3 UNIQUEs incl. partial) |
| `apps/backend/app/modules/online_refunds/__init__.py` | module-init | n/a | `app/modules/online_payments/__init__.py` + `fiscal_receipts/__init__.py` | exact |
| `apps/backend/app/modules/online_refunds/constants.py` | constants/FSM | declarative-FSM | `app/modules/online_payments/constants.py` | exact (byte-for-byte mirror) |
| `apps/backend/app/modules/online_refunds/models.py` | ORM model | CRUD | `app/modules/online_payments/models.py` | exact (Base+UUIDPkMixin, bare CHECK names) |
| `apps/backend/app/modules/online_refunds/repository.py` | repository | CRUD | `app/modules/online_payments/repository.py` + `fiscal_receipts/repository.py` | exact (caller-owns-txn) |
| `apps/backend/app/modules/online_refunds/service.py` | service | request-response | `app/modules/online_payments/service.py` + `memberships/service.py:refund_membership` (line 882) | strong (call-then-INSERT D-51-09 + Protocol slot dispatch) |
| `apps/backend/app/modules/fiscal_receipts/tasks.py` | ARQ task | event-driven | `app/workers/tasks/dispatch_email.py` | exact (circuit-breaker check → provider call → audit chain) |
| `apps/backend/app/api/v1/online_payments/__init__.py` | module-init | n/a | `app/api/v1/_internal/yookassa/__init__.py` | exact |
| `apps/backend/app/api/v1/online_payments/router.py` | router | request-response | `app/modules/memberships/router.py:refund_membership` (line 514) + `app/modules/online_payments/router.py` | exact (RBAC + CSRF + Pydantic body) |
| `apps/backend/app/api/v1/online_payments/schemas.py` | schemas | n/a | `app/modules/online_payments/schemas.py` | exact (BackendSchemaBase + ResponseData) |
| `apps/backend/app/integrations/yookassa/circuit_breaker.py` | integration | event-driven | `app/integrations/email/circuit_breaker.py` | exact (D-51-14 copy-and-adapt; ONLY change: key prefixes) |
| `apps/backend/app/integrations/yookassa/client.py::create_receipt` (extension) | integration method | request-response | `client.py:create_refund` (line 350) | exact (header + body + classification taxonomy) |
| `apps/backend/app/integrations/yookassa/types.py::YooKassaReceiptResult` (existing placeholder; promote) | dataclass | n/a | `YooKassaRefundResult` (line 94) | partial (skeleton already exists at line 119; needs field expansion) |
| `apps/backend/app/api/v1/_internal/yookassa/handlers.py::handle_refund_succeeded` | handler | event-driven | `handlers.py:handle_payment_succeeded` (line 200) | exact (MASTER template per D-51-11) |
| `apps/backend/app/api/v1/_internal/yookassa/handlers.py::handle_receipt_succeeded` | handler | event-driven | `handlers.py:handle_payment_canceled` (line 381) | exact (minus re-fetch per D-51-03) |
| `apps/backend/app/api/v1/_internal/yookassa/handlers.py::handle_receipt_canceled` | handler | event-driven | `handlers.py:handle_payment_canceled` (line 381) | exact (mirror of receipt_succeeded with target='failed') |
| `apps/backend/app/api/v1/_internal/yookassa/router.py` (extend event-dispatch chain) | router | request-response | `router.py` (lines 112-120) | exact (3 new `elif` branches) |
| `apps/backend/app/workers/scheduled/monitor_stale_fiscal_receipts.py` | ARQ cron | batch | `app/workers/scheduled/expire_memberships.py` + `send_expiring_notifications.py` | exact (sessionmaker + service helper) |
| `apps/backend/app/workers/scheduled/poll_pending_refunds.py` | ARQ cron | batch | `expire_memberships.py` + `send_booking_reminders.py` | exact (SELECT FOR UPDATE SKIP LOCKED loop) |
| `apps/backend/app/workers/__init__.py` (functions + cron_jobs additions) | config | n/a | `WorkerSettings.functions` (line 122) + `cron_jobs` (line 141) | exact (list extension) |
| `apps/backend/app/core/audit.py` (3 new LOCKED pairs) | constants | n/a | `audit.py:343-360` (Phase 47/50 entries) | exact (append + docstring) |
| `apps/backend/app/core/audit_payloads.py` (3 new Payload classes) | schemas | n/a | `audit_payloads.py:OnlinePaymentSucceededPayload` (line 787) + `MembershipActivatedOnlinePayload` (line 826) | exact (BaseModel + extra='forbid') |
| `apps/backend/app/main.py` (replace `phase49_fiscal_dispatcher_stub` with real impl) | composition root | n/a | `app/main.py:329` + `app/workers/__init__.py:293` | exact (double-wire pattern preserved) |
| `apps/backend/tests/integration/online_refunds/` (new directory) | tests | n/a | `tests/integration/webhook_yookassa/` (Phase 50 plan 50-06) | exact (conftest + per-event test file) |
| `apps/backend/tests/integration/fiscal_receipts/` (new directory) | tests | n/a | `tests/integration/webhook_yookassa/` | exact |
| `apps/backend/tests/integration/webhook_yookassa/test_handle_refund_succeeded.py` | tests | n/a | `tests/integration/webhook_yookassa/test_wh05_succeeded_atomic_uow.py` | exact |
| `apps/backend/tests/integration/webhook_yookassa/test_handle_receipt_*.py` (×2) | tests | n/a | same | exact |
| `apps/backend/tests/integration/webhook_yookassa/test_post_commit_seam.py` (UPDATE) | tests | n/a | (pre-existing — Phase 50 AST gate) | exact (in-place gate flip) |
| `apps/backend/tests/integrations/yookassa/conftest.py` (new fixtures) | tests | n/a | existing `yookassa_create_refund_success` + `yookassa_get_payment_*` | exact |
| `apps/backend/tests/unit/test_yookassa_circuit_breaker.py` | tests | n/a | (existing email-breaker tests + Pitfall 11 atomic-pipeline assertion) | role-match |

---

## Pattern Assignments

### `apps/backend/alembic/versions/0037_online_refunds.py` (migration, schema-DDL)

**Analog:** `apps/backend/alembic/versions/0034_online_payments.py` (full UNIQUEs + 2 partial-UNIQUE double-tap indexes) and `0035_fiscal_receipts.py` (op.f() simple-table shape)

**Header / docstring pattern** (0034 lines 1-29) — copy structure:
```python
"""online_refunds table + UNIQUEs (Phase 51 REFUND-01 / D-51-04 / D-51-06).

Revision ID: 0037_online_refunds
Revises: 0036_payments_received_by_user_id_nullable
Create Date: 2026-05-23 00:00:00.000000

Ships table + UNIQUE(yookassa_refund_id) + UNIQUE(idempotency_key) +
partial UNIQUE(online_payment_id) WHERE status IN ('pending','succeeded')
(D-51-04).

Partial UNIQUE follows the Phase 49 0034 pattern: ``postgresql_where`` with
plain text predicate; index name carries the constraint semantics
(``uq_online_refunds_alive_per_online_payment``). NOT named via ``op.f()``
because Index objects use explicit literal names in this project
(see online_payments/models.py:138).

ORM model lives at app/modules/online_refunds/models.py.
"""
```

**Constraint naming pattern** (0035 lines 64-83) — `op.f()` wrappers on PK / FK / CHECK / UNIQUE; bare-table-name UNIQUE for partial index (see 0034 lines 139-156).

**Imports pattern** (0034 lines 31-39):
```python
from __future__ import annotations

from collections.abc import Sequence
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0037_online_refunds"
down_revision: str | None = "0036_payments_received_by_user_id_nullable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**Table-create pattern** (0034 lines 47-136) — full UNIQUEs via `sa.UniqueConstraint` inside `create_table`; partial UNIQUE via separate `op.create_index(..., unique=True, postgresql_where=text("..."))` AFTER create_table.

**Partial UNIQUE excerpt** (0034 lines 137-156) — direct template for `uq_online_refunds_alive_per_online_payment`:
```python
# IMMUTABLE per-day partition NOT needed for online_refunds (D-51-04 has no per-day partition).
# Partial UNIQUE only filters by status. Predicate is IMMUTABLE-safe (text literal).
op.create_index(
    "uq_online_refunds_alive_per_online_payment",
    "online_refunds",
    ["online_payment_id"],
    unique=True,
    postgresql_where=text(
        "status IN ('pending','succeeded')"
    ),
)
```

**Downgrade pattern** (0034 lines 159-166): drop indexes BEFORE `drop_table` (matches 0035 line 87-93 pattern of dropping partial-UNIQUE artifacts first).

**Delta vs analog:**
- Down-revision points at `0036_payments_received_by_user_id_nullable` (NOT `0035_fiscal_receipts` as CONTEXT D-51-06 claims).
- No `confirmation_url` / `confirmation_type` columns (refund flow is fire-and-poll, no user redirect).
- New: `requested_by_user_id` FK (RBAC actor) + `reason` TEXT NULL + `original_payment_id` FK to `payments.id`.
- `amount_kopecks` CHECK `> 0` (stored positive per D-51-Discretion).
- Status enum `('pending','succeeded','canceled')` — no 'failed' because refund FSM has no failure terminal (D-51-04 / D-51-Discretion).
- ON DELETE RESTRICT on all FKs (matches 0034 + 0035 convention).

---

### `apps/backend/app/modules/online_refunds/constants.py` (constants/FSM)

**Analog:** `apps/backend/app/modules/online_payments/constants.py` (byte-for-byte mirror per D-51-07)

**Imports + StrEnum pattern** (online_payments/constants.py lines 9-23):
```python
from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType


class ErrorCode(StrEnum):
    """Phase 51 service-layer error codes (locked literals)."""

    ORIGINAL_PAYMENT_NOT_FOUND = "original_payment_not_found"
    ONLINE_PAYMENT_NOT_FOUND = "online_payment_not_found"
    YOOKASSA_VALIDATION_ERROR = "yookassa_validation_error"
    YOOKASSA_UNAVAILABLE = "yookassa_unavailable"
    YOOKASSA_PERMANENT_ERROR = "yookassa_permanent_error"
```

**FSM transitions constant** (online_payments/constants.py lines 51-57) — byte-for-byte mirror:
```python
ONLINE_REFUND_STATUS_TRANSITIONS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        STATUS_PENDING: frozenset({STATUS_SUCCEEDED, STATUS_CANCELED}),
        STATUS_SUCCEEDED: frozenset(),  # terminal
        STATUS_CANCELED: frozenset(),   # terminal
    }
)
```

**Status literal constants** (lines 25-28):
```python
STATUS_PENDING = "pending"
STATUS_SUCCEEDED = "succeeded"
STATUS_CANCELED = "canceled"
STATUS_VALUES: tuple[str, ...] = (STATUS_PENDING, STATUS_SUCCEEDED, STATUS_CANCELED)
```

**Delta vs analog:**
- No `CONFIRMATION_TYPE_*` constants (refund has no user-facing redirect).
- No `SUBJECT_KIND_*` constants (refund's subject_kind dispatch derives from the parent OnlinePayment row).
- `ErrorCode` enum members differ — `CLIENT_EMAIL_REQUIRED` not needed (refund inherits email from parent OnlinePayment), but ADD `ORIGINAL_PAYMENT_NOT_FOUND` + `ONLINE_PAYMENT_NOT_FOUND` for D-51-08 steps 5-6 404 guards.

---

### `apps/backend/app/modules/online_refunds/models.py` (ORM, CRUD)

**Analog:** `apps/backend/app/modules/online_payments/models.py` (Base+UUIDPkMixin, BARE CheckConstraint names)

**Class composition + docstring discipline** (online_payments/models.py lines 1-44):
```python
"""OnlineRefund ORM model (Phase 51 REFUND-01 / D-51-04).

Mirrors the 0037_online_refunds migration column-for-column. Class
composition is ``Base + UUIDPkMixin`` ONLY — no TimestampMixin, no
SoftDeleteMixin — because the FSM tracks lifecycle via explicit
``requested_at`` / ``succeeded_at`` / ``canceled_at`` columns
(single-temporal-column discipline mirrors online_payments/models.py:5-7).

CheckConstraints use BARE suffixes — NAMING_CONVENTION expands to
ck_online_refunds_<suffix>. Specifying the full literal would
double-prefix (the bug fixed by Plan 49-01 deviation #2).
"""
```

**ORM body shape** — mirror online_payments/models.py lines 47-158 (PgUUID + Mapped + bare-name CHECKs + UniqueConstraint + Index for partial UNIQUE).

**Critical excerpt — bare-name CHECK constraints** (online_payments/models.py lines 109-129):
```python
__table_args__ = (
    CheckConstraint(
        "amount_kopecks > 0",
        # NAMING_CONVENTION expands to ck_online_refunds_amount_kopecks_positive
        name="amount_kopecks_positive",
    ),
    CheckConstraint(
        "status IN ('pending','succeeded','canceled')",
        # NAMING_CONVENTION expands to ck_online_refunds_status
        name="status",
    ),
    UniqueConstraint(
        "yookassa_refund_id",
        name="uq_online_refunds_yookassa_refund_id",
    ),
    UniqueConstraint(
        "idempotency_key",
        name="uq_online_refunds_idempotency_key",
    ),
    Index(
        "uq_online_refunds_alive_per_online_payment",
        "online_payment_id",
        unique=True,
        postgresql_where=text("status IN ('pending','succeeded')"),
    ),
)
```

**Delta vs analog:**
- No `confirmation_type` CHECK / `<>` XOR CHECK (refund has no subject_kind XOR — `online_payment_id` references one parent that already enforces the XOR).
- Add `original_payment_id` FK to `payments.id` (the v1.4 ledger sale row).
- Add `reason: Text NULL` operator-supplied + `requested_by_user_id: PgUUID FK users.id`.

---

### `apps/backend/app/modules/online_refunds/repository.py` (repository, CRUD)

**Analog:** `apps/backend/app/modules/online_payments/repository.py` (caller-owns-txn discipline; no flush/commit)

**Imports + docstring + insert pattern** (online_payments/repository.py lines 1-51):
```python
"""Online refunds repository — caller-owns-txn INSERT + GET (Phase 51 D-51-07).

Caller-owns-txn (D-32-10 lineage): NO ``session.flush()`` and NO
``session.commit()`` calls live here. The service layer (POST endpoint
flow) and the webhook handler (refund.succeeded UoW) each own their own
transactional moment.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.online_refunds.models import OnlineRefund


async def insert_online_refund(  # noqa: SVC001 caller-owns-txn
    session: AsyncSession,
    *,
    online_payment_id: UUID,
    original_payment_id: UUID,
    client_id: UUID,
    yookassa_refund_id: str,
    idempotency_key: str,
    amount_kopecks: int,
    status: str,
    requested_by_user_id: UUID,
    reason: str | None,
    audit_correlation_id: UUID | None,
) -> OnlineRefund:
    """Insert OnlineRefund row; caller owns flush + commit."""
    row = OnlineRefund(...)
    session.add(row)
    return row
```

**Lookup helpers** — copy pattern from online_payments/repository.py lines 54-73 and `fiscal_receipts/repository.py:get_fiscal_receipt_by_payment_id_and_kind`:
- `get_online_refund_by_id`
- `get_online_refund_by_yookassa_refund_id` (webhook handler entry point)
- `get_online_refund_by_idempotency_key` (replay-check for POST endpoint)
- `select_pending_older_than(session, *, cutoff: datetime, limit: int = 50)` — for D-51-17 cron; **mirror with `SELECT ... WHERE status='pending' AND requested_at < :cutoff FOR UPDATE SKIP LOCKED LIMIT 50`** (Postgres-specific per D-51-Discretion `SELECT FOR UPDATE SKIP LOCKED`).

**Delta vs analog:**
- Add `update_to_succeeded(session, row, *, succeeded_at)` and `update_to_canceled(session, row, *, canceled_at)` mutator helpers (CONTEXT D-51-07 lists `mark_succeeded` / `mark_canceled`). Online_payments/repository.py explicitly notes "No UPDATE methods in Phase 49" — Phase 51 needs them here because the webhook handler + cron both flip status.
- `select_pending_older_than` uses `with_for_update(skip_locked=True)` — see `apps/backend/app/api/v1/_internal/yookassa/handlers.py:_select_for_update_online_payment` (line 124) for the SQLAlchemy `.with_for_update()` shape; add `skip_locked=True` kwarg.

---

### `apps/backend/app/modules/online_refunds/service.py` (service, request-response)

**Analog primary:** `apps/backend/app/modules/memberships/service.py:refund_membership` (line 882) — the BUSINESS-LOGIC mirror for the request-side path (D-51-11 maps almost 1:1 for the completion-side; this is the request side).
**Analog secondary:** `apps/backend/app/modules/online_payments/service.py` for the call-then-INSERT discipline + ErrorCode mapping.

**Imports pattern** (memberships/service.py + online_payments/service.py composite):
```python
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.dependencies import CurrentUser, get_yookassa_client_provider
from app.core.exceptions import (
    BadGatewayAppError,
    NotFoundError,
    ServiceUnavailableAppError,
    ValidationAppError,
)
from app.modules.online_payments.models import OnlinePayment
from app.modules.online_refunds import repository
from app.modules.online_refunds.constants import (
    STATUS_PENDING,
    ErrorCode,
)
from app.modules.online_refunds.schemas import OnlineRefundResponse

_log = structlog.get_logger("modules.online_refunds.service")
```

**Guard-stack pattern** — memberships/service.py:refund_membership lines 927-942 (specific-first guards: `MembershipNotFoundError` → `MustUnfreezeFirstError` (B-08) → `CannotRefundRenewedSourceError` (B-09) → `_assert_can_transition(target='cancelled')`). Mirror this BEFORE any ЮKassa call in the new service.

**Call-then-INSERT (D-51-09 preferred variant)** — adapts `online_payments/service.py` lines 70-78 + memberships/service.py line 949:
```python
async def initiate_online_refund(  # noqa: SVC001 caller-owns-txn
    session: AsyncSession,
    actor: CurrentUser,
    *,
    membership_id: UUID,                    # OR pt_package_id depending on caller
    idempotency_key: UUID,                  # caller-owned (D-51-09 / D-48-11)
    reason: str | None,
) -> OnlineRefundResponse:
    """Phase 51 REFUND-01 initiate path (D-51-08/09).

    Guards (specific-first per D-32-11):
      1. Load membership → 404 membership_not_found
      2. status='frozen' → 409 must_unfreeze_first (B-08)
      3. has_renewal_descendants(...) → 409 cannot_refund_renewed_source (B-09)
      4. _assert_can_transition(target='cancelled') → 409 invalid_transition
      5. Locate OnlinePayment by (client_id, membership_plan_id) → 404 online_payment_not_found
      6. Locate original payments.id → 404 original_payment_not_found
    Then (D-51-09): call yookassa_client.create_refund(...) BEFORE any DB write.
    Classification → exception mapping mirrors online_payments/service.py lines 70-78.
    On 'ok': single `async with session.begin()` INSERTs the OnlineRefund row
    with the real yookassa_refund_id + emits online_refund_initiated audit
    (fresh chain root, audit_correlation_id = fresh uuid4()).
    Return OnlineRefundResponse with status='pending'.
    """
```

**Classification → exception mapping** (online_payments/service.py docstring lines 19-23) — verbatim reuse:
```python
# - ok                → INSERT row → emit audit → 201/202
# - validation_error  → raise ValidationAppError(ErrorCode.YOOKASSA_VALIDATION_ERROR.value)
# - transient_error   → raise ServiceUnavailableAppError(ErrorCode.YOOKASSA_UNAVAILABLE.value)
# - permanent_error   → raise BadGatewayAppError(ErrorCode.YOOKASSA_PERMANENT_ERROR.value)
```

**Audit emit pattern** (memberships/service.py lines 974-984) — UUID kwargs str-cast for JSONB:
```python
await audit.emit(
    session,
    "online_refund_initiated",  # NEW LOCKED event (D-51-19)
    actor_user_id=actor.id,
    resource_type="online_refund",  # NEW RESOURCE TYPE (D-51-19)
    resource_id=online_refund_row.id,
    audit_correlation_id=str(fresh_corr),
    online_refund_id=str(online_refund_row.id),
    online_payment_id=str(online_payment.id),
    original_payment_id=str(original_payment_id),
    amount_kopecks=amount_kopecks,
    requested_by_user_id=str(actor.id),
    reason=reason,
)
```

**Delta vs analog:**
- D-51-09 call-then-INSERT INVERTS memberships/service.py: ЮKassa is called BEFORE the DB writes (memberships/service.py:refund_membership calls the refunder INSIDE the txn). The trade-off is documented in D-51-09 — leaked ЮKassa refunds are reconciled by the D-51-17 cron via the `uq_online_refunds_yookassa_refund_id` UNIQUE.
- The service is the txn owner for the request path. The webhook handler (handlers.py:handle_refund_succeeded) is the txn owner for the completion path. Each owns its own `async with session.begin()`.

---

### `apps/backend/app/modules/fiscal_receipts/tasks.py` (ARQ task, event-driven)

**Analog primary:** `apps/backend/app/workers/tasks/dispatch_email.py` (full structure — ctx unpacking + circuit-breaker head-of-body check + provider call + classification dispatch + audit emit BEFORE commit + return summary string)
**Analog secondary:** `app/integrations/yookassa/client.py:create_refund` for the classification taxonomy disposition (`ok` / `validation_error` / `transient_error` / `permanent_error`)

**Module-level imports + structlog logger** (dispatch_email.py lines 51-66):
```python
from __future__ import annotations

from typing import Any, Final
from uuid import UUID

import structlog

from app.core import audit
from app.integrations.yookassa.circuit_breaker import is_circuit_open, record_failure
from app.integrations.yookassa.receipt import PaymentMode, PaymentSubject, VatCode, build_receipt_item
from app.integrations.yookassa.settings import YooKassaSettings
from app.modules.fiscal_receipts import repository
from app.modules.fiscal_receipts.constants import STATUS_SENT, STATUS_SUCCEEDED, STATUS_FAILED

_log: Final = structlog.get_logger("modules.fiscal_receipts.tasks")
_PROVIDER: Final[str] = "receipts"  # circuit-breaker key suffix → sz:yookassa:circuit:receipts
```

**Task signature + ctx pattern** (dispatch_email.py line 94 + send_expiring_notifications.py line 41):
```python
async def dispatch_fiscal_receipt(ctx: dict[str, Any], fiscal_receipt_id: str) -> str:
    """Phase 51 FISCAL-05 dispatch task. Returns 'sent' | 'failed' | 'skipped'.

    ctx keys required (provided by WorkerSettings.on_startup):
      - sessionmaker: async_sessionmaker[AsyncSession]
      - yookassa_client: YooKassaClient
      - redis: redis.asyncio.Redis
    """
```

**Circuit-breaker head-of-body pattern** (dispatch_email.py lines 118-137):
```python
session_factory = ctx["sessionmaker"]
yookassa_client = ctx["yookassa_client"]
redis = ctx["redis"]

if await is_circuit_open(redis, _PROVIDER):
    _log.warning("yookassa_receipt_circuit_short_circuit", provider=_PROVIDER)
    # Per D-51-13 step 2: raise arq.Retry(defer=300) so ARQ defers without
    # consuming a try-count (mirrors PITFALLS Pitfall 11 step 1).
    from arq import Retry
    raise Retry(defer=300)
```

**Receipt body build pattern** — combine `online_payments/service.py` `build_receipt_item` callsite shape with FiscalReceipt row fields:
```python
async with session_factory() as session:
    fr_row = await repository.get_fiscal_receipt_by_id(session, UUID(fiscal_receipt_id))
    if fr_row is None or fr_row.status != STATUS_SENT:
        _log.info("fiscal_receipt_skip_nonactive", row_id=fiscal_receipt_id, status=fr_row.status if fr_row else None)
        return "skipped"

    settings = YooKassaSettings()
    items = [
        build_receipt_item(
            description="Refund of membership",  # OR derive from parent Payment row
            amount_kopecks=...,
            payment_subject=PaymentSubject.SERVICE,         # FISCAL-03 LOCKED literal
            payment_mode=PaymentMode.FULL_PAYMENT,           # D-51-Discretion: full_payment for refunds
            vat_code=VatCode(int(settings.default_vat_code)),
        ),
    ]
    result = await yookassa_client.create_receipt(
        payment_id=...,  # ЮKassa payment_id from OnlinePayment row
        customer_email=fr_row.customer_email,
        items=items,
        tax_system_code=int(settings.tax_system_code),
        idempotency_key=fr_row.id.hex,                       # deterministic per D-51-20
    )
```

**Classification dispatch** — mirror `client.py:create_refund` error branches + dispatch_email.py audit-reason mapping:
```python
if result.classification == "ok":
    fr_row.yookassa_receipt_id = result.receipt_id
    await audit.emit(
        session,
        "fiscal_receipt_dispatched",   # already in LOCKED_AUDIT_EVENTS (Phase 47)
        actor_user_id=None,
        resource_type="fiscal_receipt",
        resource_id=fr_row.id,
        audit_correlation_id=str(fr_row.audit_correlation_id) if fr_row.audit_correlation_id else None,
        fiscal_receipt_id=str(fr_row.id),
        yookassa_receipt_id=result.receipt_id,
    )
    await session.commit()
    return "sent"
elif result.classification == "transient_error":
    await record_failure(redis, _PROVIDER)
    from arq import Retry
    job_try = int(ctx.get("job_try", 1))
    raise Retry(defer=_backoff_with_jitter(job_try))   # 30 / 120 / 600 + ±10%
elif result.classification in ("validation_error", "permanent_error"):
    fr_row.status = STATUS_FAILED
    fr_row.failed_at = datetime.now(UTC)
    fr_row.failure_reason = f"{result.classification}:{result.http_status or ''}:{result.error_code or ''}"
    await audit.emit(session, "fiscal_receipt_failed", ...)
    await session.commit()
    return "failed"
```

**Error handling pattern** — dispatch_email.py emits `audit.emit BEFORE session.commit` (line 199); same discipline here per D-32-10 / D-49-13.

**Delta vs analog:**
- dispatch_email.py has `EmailEnvelope` reconstructed from cloudpickle-safe kwargs; Phase 51 ARQ task accepts a single `fiscal_receipt_id: str` (the DB row PK) — looks up everything else inside.
- The task ITSELF does NOT flip `status='succeeded'` (the inbound `receipt.succeeded` webhook does — D-51-13 step 5). Task only writes `yookassa_receipt_id` + emits dispatched audit.
- ARQ retry semantics: dispatch_email.py uses `_max_tries=2` per-enqueue; Phase 51 task uses `max_tries=3` (D-51-Discretion + PITFALLS Pitfall 11 step 2) via per-enqueue or `func(max_tries=3, timeout=20)` wrapper.

---

### `apps/backend/app/api/v1/online_payments/router.py` (router, request-response)

**Analog primary:** `apps/backend/app/modules/memberships/router.py:refund_membership` (line 514) — exact RBAC + CSRF + Pydantic body shape for a refund POST
**Analog secondary:** `app/modules/online_payments/router.py` for the prefix mounting + YooKassaSettings DI shape

**Imports pattern** (memberships/router.py + online_payments/router.py composite):
```python
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission, verify_csrf
from app.core.permissions import Action, Resource
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.online_refunds import service as online_refunds_service

from app.api.v1.online_payments.schemas import (
    OnlineRefundRequest,
    OnlineRefundResponse,
)

router = APIRouter()
```

**Endpoint pattern** (memberships/router.py lines 514-563):
```python
@router.post(
    "/memberships/{membership_id}/refund",
    response_model=ResponseEnvelope[OnlineRefundResponse],
    status_code=status.HTTP_202_ACCEPTED,         # 202 per REFUND-01 — completion awaits webhook
    summary=(
        "Initiate online refund of a membership (reception+owner per B-07; "
        "409 must_unfreeze_first / cannot_refund_renewed_source / "
        "invalid_transition / already_refunded)"
    ),
)
async def refund_membership_online(
    membership_id: UUID,
    payload: OnlineRefundRequest,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.REFUND, Resource.MEMBERSHIPS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[OnlineRefundResponse]:
    """Phase 51 REFUND-01. Mirrors memberships/router.py:refund_membership.

    RBAC-04 ordering: auth → require_permission → verify_csrf (D-49-25; enforced
    by tests/integration/test_route_introspection.py).

    NO Idempotency-Key dep — caller passes idempotency_key in body per D-51-09
    (single UUID propagates to ЮKassa Idempotence-Key header).
    """
    resp = await online_refunds_service.initiate_online_refund(
        session,
        actor,
        membership_id=membership_id,
        idempotency_key=payload.idempotency_key,
        reason=payload.reason,
    )
    return envelope(resp)
```

**Mount in `app/api/v1/router.py`** — append after the existing `_internal/yookassa` mount (router.py lines 93-95):
```python
v1.include_router(
    online_payments_endpoint_router,   # NEW — the user-facing refund router
    prefix="/online-payments",
    tags=["online-payments"],
)
```
NOTE: There is already an `online_payments_router` mounted from `app/modules/online_payments/router.py` at the same `/online-payments` prefix (router.py:45-49). The new `app/api/v1/online_payments/router.py` either (a) mounts at a DIFFERENT prefix OR (b) merges into the existing `app/modules/online_payments/router.py` file. Planner MUST resolve: CONTEXT D-51-01 specifies a new package `app/api/v1/online_payments/` but the existing module router already owns `/online-payments`. Recommendation: append the 2 new `POST .../refund` routes to the existing `app/modules/online_payments/router.py` to avoid double-mount (simpler) — OR mount the new package at `/online-payments` with NO conflict because FastAPI merges routes from multiple include_routers at the same prefix as long as path operations differ. Verify before planning.

**Delta vs analog:**
- 202 status (NOT 200 like offline refund) — refund awaits webhook completion.
- Body shape `OnlineRefundRequest { idempotency_key: UUID, reason: str | None }` — see schemas section below.
- No `MembershipRefundRequest`-shaped `amountKopecks` field (REF-05 — full refund only; v1.4 B-02 partial deferred).

---

### `apps/backend/app/api/v1/online_payments/schemas.py` (schemas)

**Analog:** `app/modules/online_payments/schemas.py` (BackendSchemaBase + ResponseData)

**Imports + schema shape** (existing online_payments/schemas.py):
```python
from __future__ import annotations

from uuid import UUID

from app.core.schemas import BackendSchemaBase, ResponseData


class OnlineRefundRequest(BackendSchemaBase):
    """POST /api/v1/online-payments/{kind}/{id}/refund body (Phase 51 REFUND-01)."""

    idempotency_key: UUID
    reason: str | None = None


class OnlineRefundResponse(ResponseData):
    """202 response for either refund endpoint (D-51-08 step 10)."""

    online_refund_id: UUID
    status: str                  # 'pending' on POST; cron may advance to 'succeeded'/'canceled'
    yookassa_refund_id: str
```

**Delta vs analog:** No model_validator XOR check (online_payments has `confirmation_url`/`qr_payload` XOR; refund response has no such alternation).

---

### `apps/backend/app/integrations/yookassa/circuit_breaker.py` (integration, event-driven)

**Analog:** `apps/backend/app/integrations/email/circuit_breaker.py` (D-51-14: copy-and-adapt, NOT generalize)

**Full file pattern** — copy verbatim, change only the key prefixes + logger namespace:

```python
"""Redis sliding-window circuit breaker for ЮKassa /receipts (Phase 51 D-51-14).

Two-key sliding-window-plus-open-marker breaker for the ЮKassa receipts
endpoint (Pitfall 11):

- ``sz:yookassa:circuit_window:<provider>`` — Redis sorted set of recent
  failure timestamps. ZADD/ZREMRANGEBYSCORE/ZCARD inside MULTI/EXEC.
- ``sz:yookassa:circuit:<provider>`` — open-marker key. EXISTS-only check
  via ``is_circuit_open``; TTL expiry is the only closing surface.

D-51-14 LOCKED:
- Threshold: 5 failures / 60s → open
- Open TTL: 300s (5 minutes)
- ``provider`` in v1.7: ``"receipts"`` (key suffix → sz:yookassa:circuit:receipts)
"""

from __future__ import annotations

import time
from typing import Final
from uuid import uuid4

import structlog
from redis.asyncio import Redis

_CIRCUIT_KEY_PREFIX: Final[str] = "sz:yookassa:circuit:"
_WINDOW_KEY_PREFIX: Final[str] = "sz:yookassa:circuit_window:"
_FAILURE_THRESHOLD: Final[int] = 5
_WINDOW_SECONDS: Final[int] = 60
_OPEN_TTL_SECONDS: Final[int] = 300  # 5 minutes (D-51-14)

_log = structlog.get_logger("integrations.yookassa.circuit_breaker")


async def is_circuit_open(redis: Redis, provider: str) -> bool: ...     # mirror lines 46-56
async def record_failure(redis: Redis, provider: str) -> None: ...      # mirror lines 59-110 (atomic pipeline)
```

**Atomic pipeline excerpt** (email/circuit_breaker.py lines 84-104) — copy verbatim:
```python
window_key = f"{_WINDOW_KEY_PREFIX}{provider}"
now_ms = int(time.time() * 1000)
member = f"{now_ms}-{uuid4().hex[:8]}"
cutoff = now_ms - _WINDOW_SECONDS * 1000

async with redis.pipeline(transaction=True) as pipe:
    pipe.zadd(window_key, {member: now_ms})
    pipe.zremrangebyscore(window_key, 0, cutoff)
    pipe.expire(window_key, _WINDOW_SECONDS * 2)
    pipe.zcard(window_key)
    results = await pipe.execute()

count = int(results[3])

if count >= _FAILURE_THRESHOLD:
    await redis.set(
        f"{_CIRCUIT_KEY_PREFIX}{provider}",
        "1",
        ex=_OPEN_TTL_SECONDS,
    )
    _log.warning("circuit_open", provider=provider, failures_in_window=count)
```

**Delta vs analog:**
- ONLY the 2 key prefixes (`sz:email:*` → `sz:yookassa:*`) and the structlog logger name change.
- D-51-14 explicitly chose copy-and-adapt over generalization to keep `integrations-isolated` importlinter contract clean.

---

### `apps/backend/app/integrations/yookassa/client.py::create_receipt` (method extension)

**Analog:** `client.py:create_refund` (line 350) — byte-for-byte mirror per D-51-20

**Full method skeleton** (mirror create_refund lines 350-443):
```python
async def create_receipt(
    self,
    *,
    payment_id: str,
    customer_email: str,
    items: list[dict[str, Any]],
    tax_system_code: int,
    idempotency_key: str,
) -> YooKassaReceiptResult:
    """POST /v3/receipts — 54-ФЗ fiscalization (Phase 51 FISCAL-05 / D-51-20).

    Caller-owned idempotency_key (D-48-11). Mirrors create_refund shape.
    Never re-raises — returns YooKassaReceiptResult with classification.
    """
    body: dict[str, Any] = {
        "type": "payment",                              # OR "refund" depending on fiscal_receipts.kind
        "payment_id": payment_id,                       # OR refund_id for refund receipts
        "customer": {"email": customer_email},
        "items": items,
        "tax_system_code": int(tax_system_code),
        "send": True,                                   # ЮKassa fires receipt.succeeded webhook
    }
    try:
        response = await self._http.post(
            "receipts",
            json=body,
            headers={IDEMPOTENCE_KEY_HEADER: idempotency_key},
        )
        response.raise_for_status()
        payload = response.json()
        _log.info(
            "yookassa_create_receipt_ok",
            receipt_id=payload["id"],
            status=payload.get("status"),
        )
        return YooKassaReceiptResult(
            ok=True,
            classification="ok",
            receipt_id=payload["id"],
        )
    except httpx.HTTPStatusError as exc:
        classification, status, error_code = self._classify_http_status_error(exc)
        _log.warning(f"yookassa_create_receipt_{classification}", http_status=status, error_code=error_code)
        return YooKassaReceiptResult(ok=False, classification=classification, http_status=status, error_code=error_code, error=str(exc))
    except (httpx.TimeoutException, httpx.RequestError) as exc:
        _log.warning("yookassa_create_receipt_transient_error", reason=type(exc).__name__)
        return YooKassaReceiptResult(ok=False, classification="transient_error", error=str(exc))
    except json.JSONDecodeError as exc:
        _log.warning("yookassa_create_receipt_permanent_error", reason="malformed_json")
        return YooKassaReceiptResult(ok=False, classification="permanent_error", error=str(exc))
    except Exception as exc:
        _log.warning("yookassa_create_receipt_transient_error", reason=type(exc).__name__)
        return YooKassaReceiptResult(ok=False, classification="transient_error", error=str(exc))
```

**Delta vs analog (`create_refund`):**
- `body["type"]` discriminator ("payment" vs "refund") replaces refund's `payment_id` + `amount` shape.
- Adds `customer.email` field (mandatory for 54-ФЗ; Pitfall 9).
- `items` is a list of `build_receipt_item()` dicts (same shape as `create_payment` receipt.items).
- No `amount_kopecks` echo on success — receipt is a fiscalization event, not a money movement.
- `YooKassaReceiptResult` (types.py line 119) is the placeholder — Phase 51 expands its fields beyond the current 5 attrs to add `receipt_id` (already present), and add no further fields per D-51-20.

---

### `apps/backend/app/api/v1/_internal/yookassa/handlers.py` — `handle_refund_succeeded` (handler, event-driven)

**Analog:** `handlers.py:handle_payment_succeeded` (line 200) — **MASTER TEMPLATE per D-51-11**

**Full pattern to copy** (lines 200-378 of handlers.py — the entire `handle_payment_succeeded` function):

Critical excerpt 1 — re-fetch + early returns (lines 213-235):
```python
object_obj = body.get("object") or {}
object_id = object_obj.get("id") if isinstance(object_obj, dict) else None
if not isinstance(object_id, str) or not object_id:
    _log.warning("yookassa_webhook_missing_object_id", event="refund.succeeded")
    return

# WH-02 — Re-fetch via get_refund (D-51-11 step 2). Mirrors D-50-12 doctrine.
result = await yookassa_client.get_refund(object_id)
if result.classification != "ok":
    _log.warning("yookassa_refund_refetch_failed", object_id=object_id, classification=result.classification)
    return
if result.status != "succeeded":
    _log.info("yookassa_refund_pending_skip", object_id=object_id, status=result.status)
    return
```

Critical excerpt 2 — atomic UoW open + SELECT-FOR-UPDATE (lines 237-249):
```python
webhook_intake_corr = uuid4()

async with session.begin():
    # mirror _select_for_update_online_payment (line 124); add a sibling helper
    # _select_for_update_online_refund(session, *, yookassa_refund_id=object_id)
    row = await _select_for_update_online_refund(session, yookassa_refund_id=object_id)
    if row is None:
        _log.warning("yookassa_refund_webhook_orphan", object_id=object_id)
        return  # DEFER-51-XX orphan refund reconciliation (Phase 53)
```

Critical excerpt 3 — FSM guard + transition (lines 251-276):
```python
try:
    _assert_can_transition_refund(row, target="succeeded")
except InvalidTransitionError:
    _log.warning("yookassa_refund_illegal_transition", ...)
    await audit.emit(session, "yookassa_webhook_received", ...,
                     event_type="refund.succeeded", object_id=object_id,
                     idempotency_outcome="illegal_transition")
    return

row.status = "succeeded"
row.succeeded_at = datetime.now(UTC)
```

Critical excerpt 4 — ledger write via PaymentRefunder Protocol (mirrors memberships/service.py:refund_membership line 949 + IntegrityError catch per REFUND-03):
```python
# D-51-11 — call PaymentRefunder Protocol slot (Phase 32 D-32-14). The refunder
# INSERTs the signed-negative payments row with refund_of=row.original_payment_id.
from app.core.dependencies import get_payment_refunder
from app.modules.payments.repository import _is_refund_of_uniqueness_conflict
from sqlalchemy.exc import IntegrityError

try:
    refund_payment_row = await get_payment_refunder()(
        session,
        subject_kind="membership" if onlinepayment.membership_plan_id else "pt_package",
        subject_id=onlinepayment.membership_plan_id or onlinepayment.pt_package_plan_id,
        refund_user_id=row.requested_by_user_id,
        reason=row.reason or "online_refund",
        audit_actor=...,                                # synthesize None or system actor
    )
except IntegrityError as exc:
    if _is_refund_of_uniqueness_conflict(exc):
        # REFUND-03 — idempotent replay. Return 200 OK silently.
        _log.warning("yookassa_refund_idempotent_replay", yookassa_refund_id=object_id)
        return
    raise
```

Critical excerpt 5 — subject transition (DIRECTLY via repository, NOT via activator slot per D-51-11):
```python
# D-51-11: do NOT use MembershipActivator (forward-only). Direct repository call.
from app.modules.memberships import repository as memberships_repo
from app.modules.memberships.constants import CANCELLATION_REASON_REFUNDED

await memberships_repo.update_membership_status(
    session,
    membership_row,
    status="cancelled",
    cancelled_at=datetime.now(UTC),
)
membership_row.cancellation_reason = CANCELLATION_REASON_REFUNDED
```

Critical excerpt 6 — fiscal_receipt INSERT (kind='refund') + audit chain (mirrors handlers.py lines 324-366):
```python
await insert_fiscal_receipt(
    session,
    payment_id=refund_payment_row.id,
    kind=KIND_REFUND,                              # 'refund' (vs 'payment' in Phase 50)
    status=STATUS_SENT,
    customer_email=customer_email,
    audit_correlation_id=webhook_intake_corr,
    sent_at=datetime.now(UTC),
)
# 4 audit emits (one ROOT + three CHILD):
await audit.emit(session, "online_payment_refunded", resource_type="online_payment", ...,
                 audit_correlation_id=str(webhook_intake_corr),
                 online_payment_id=str(onlinepayment.id),
                 refund_payment_id=str(refund_payment_row.id),
                 amount_kopecks=row.amount_kopecks)
await audit.emit(session, "membership_refunded", resource_type="membership", ...,    # OR pt_package_refunded
                 audit_correlation_id=str(webhook_intake_corr), ...)
await audit.emit(session, "yookassa_webhook_received", resource_type="yookassa_webhook", ...,
                 event_type="refund.succeeded", object_id=object_id, idempotency_outcome="processed")
```

**Delta vs analog (`handle_payment_succeeded`):**
- Re-fetch is `get_refund` not `get_payment`.
- Lookup is by `yookassa_refund_id` not `yookassa_payment_id`; target row is `OnlineRefund` not `OnlinePayment`.
- Calls `PaymentRefunder` Protocol (existing Phase 32 slot) instead of `PaymentRecorder` (Phase 50 widened).
- Subject transition uses repository **directly** (NOT via activator slot — refund is a backward transition).
- Fiscal receipt `kind='refund'` (not 'payment').
- Three audit emits: `online_payment_refunded` + `membership_refunded`/`pt_package_refunded` + `yookassa_webhook_received` ROOT.
- IntegrityError on `uq_payments_refund_of_alive` → return 200 OK silently (REFUND-03 idempotent semantics per D-51-05).

---

### `apps/backend/app/api/v1/_internal/yookassa/handlers.py` — `handle_receipt_succeeded` (handler, event-driven)

**Analog:** `handlers.py:handle_payment_canceled` (line 381) — same MUCH-SIMPLER mirror (no monetary side-effect)

**Pattern** — copy handle_payment_canceled lines 381-505 with these changes:
- **NO re-fetch** (D-51-03 / D-51-21) — receipt webhook body is authoritative.
- Lookup is `select(FiscalReceipt).where(FiscalReceipt.yookassa_receipt_id == object_id).with_for_update()` — add helper `_select_for_update_fiscal_receipt` analogous to `_select_for_update_online_payment` (line 124).
- FSM guard target='succeeded' against `FISCAL_RECEIPT_STATUS_TRANSITIONS` (Phase 50 constant); add helper `_assert_can_transition_receipt`.
- UPDATE `status='succeeded'`, `succeeded_at=datetime.now(UTC)`.
- Emit `fiscal_receipt_succeeded` audit (CHILD; reuses `fr_row.audit_correlation_id` per D-51-21) + `yookassa_webhook_received` ROOT.

**Signature delta:** `handle_receipt_succeeded(session, *, body: dict) -> None` — no `yookassa_client` parameter (no re-fetch).

---

### `apps/backend/app/api/v1/_internal/yookassa/handlers.py` — `handle_receipt_canceled` (handler, event-driven)

**Analog:** `handle_receipt_succeeded` (above) — direct mirror with target='failed'.

**Delta:**
- Target FSM `'failed'`.
- UPDATE `status='failed'`, `failed_at=datetime.now(UTC)`, `failure_reason=body["object"].get("cancellation_details", {}).get("reason", "yookassa_receipt_canceled")` per D-51-22.
- Emit `fiscal_receipt_failed` audit instead of `fiscal_receipt_succeeded`.

---

### `apps/backend/app/api/v1/_internal/yookassa/router.py` (event-dispatch chain extension)

**Analog:** Lines 112-122 of existing router.py.

**Pattern — append 3 elif branches** (D-51-03):
```python
if event_type == "payment.succeeded":
    await handle_payment_succeeded(session, yookassa_client, body=body)
elif event_type == "payment.canceled":
    await handle_payment_canceled(session, yookassa_client, body=body)
elif event_type == "refund.succeeded":                              # NEW (D-51-11)
    await handle_refund_succeeded(session, yookassa_client, body=body)
elif event_type == "receipt.succeeded":                             # NEW (D-51-21)
    await handle_receipt_succeeded(session, body=body)               # no yookassa_client
elif event_type == "receipt.canceled":                              # NEW (D-51-22)
    await handle_receipt_canceled(session, body=body)
else:
    _log.info("yookassa_webhook_unsupported_event_type", event_type=event_type)
```

**Delta:** Three new branches; Redis dedup already covers them via the existing `sz:yookassa:webhook:{event_type}:{object_id}` formula per D-51-12 (no router code edits beyond the dispatch chain).

---

### `apps/backend/app/workers/scheduled/monitor_stale_fiscal_receipts.py` (ARQ cron, batch)

**Analog primary:** `apps/backend/app/workers/scheduled/expire_memberships.py` (sessionmaker + delegate to service helper + summary log)
**Analog secondary:** `send_expiring_notifications.py` for the `<job_name>_complete count=N` convention

**Full file pattern** (expire_memberships.py lines 1-65 verbatim shape):
```python
"""ARQ scheduled job: flip stale fiscal_receipts pending → failed (Phase 51 FISCAL-06).

Every 15 min Europe/Moscow: SELECT-FOR-UPDATE-SKIP-LOCKED on
fiscal_receipts WHERE status='pending' AND created_at < now() - 90s.
Bulk UPDATE status='failed', failed_at=now(), failure_reason='stale_pending_no_dispatch'.
Emit fiscal_receipt_failed audit per row. Enqueue NOT-04 owner alert
post-commit (Phase 52 NOT-04 fills the body; Phase 51 leaves as no-op).
"""

from __future__ import annotations

from typing import Any

import structlog

from app.modules.fiscal_receipts import service as fiscal_receipts_service  # NEW helper module

_log = structlog.get_logger("workers.scheduled.monitor_stale_fiscal_receipts")


async def monitor_stale_fiscal_receipts(ctx: dict[str, Any]) -> int:
    """Return count of stale rows transitioned. ARQ stores in result store."""
    session_factory = ctx["sessionmaker"]
    count = await fiscal_receipts_service._monitor_stale_fiscal_receipts(session_factory)
    _log.info("monitor_stale_fiscal_receipts_complete", count=count)
    return count
```

**SELECT FOR UPDATE SKIP LOCKED pattern** — service helper uses (mirrors `repository.select_pending_older_than` from online_refunds/repository.py):
```python
stmt = (
    select(FiscalReceipt)
    .where(FiscalReceipt.status == STATUS_PENDING)
    .where(FiscalReceipt.created_at < datetime.now(UTC) - timedelta(seconds=90))
    .limit(50)                                          # loop budget per D-51-17 step 6
    .with_for_update(skip_locked=True)
)
```

**Delta vs analog:** `expire_memberships` flips active→expired with no audit per row; this cron emits `fiscal_receipt_failed` audit per row + may enqueue owner alert. Loop budget 50/tick (matches D-51-17 cap).

---

### `apps/backend/app/workers/scheduled/poll_pending_refunds.py` (ARQ cron, batch)

**Analog:** `expire_memberships.py` for the cron skeleton + `handle_refund_succeeded` for the per-row settle UoW

**Pattern:**
- Top-of-file docstring + structure mirrors expire_memberships.py.
- Per-row body: call `yookassa_client.get_refund(row.yookassa_refund_id)` (added to ctx by `WorkerSettings.on_startup` line 280 already wires `yookassa_client`).
- If `result.status == 'succeeded'`: synthesize the same UoW as `handle_refund_succeeded` (D-51-17 step 3 — see D-51-18 refactor opportunity: extract shared helper `_settle_online_refund(session, *, online_refund_id, chain_root_corr, chain_root_event)`).
- If `result.status == 'canceled'`: UPDATE `status='canceled'`, emit `online_refund_canceled` audit (NEW LOCKED event).
- If `result.classification != 'ok'`: WARN + leave row pending for next tick.

**SELECT-FOR-UPDATE-SKIP-LOCKED loop** — same shape as `monitor_stale_fiscal_receipts` but predicate is `requested_at < now() - interval '30 minutes'`.

**Delta vs analog:** Adds outbound HTTP call per row → use multi-session pattern from `send_booking_reminders.py` / `send_expiring_notifications.py` (multi-session per send) — see `send_expiring_notifications.py` lines 17-23 rationale for not holding a DB connection across HTTPS round-trips.

---

### `apps/backend/app/workers/__init__.py` — `WorkerSettings.functions` + `cron_jobs` (config)

**Analog:** Lines 122-130 (`functions`) and lines 141-211 (`cron_jobs`).

**Functions list extension** (line 122):
```python
from app.workers.tasks.dispatch_email import dispatch_email
from app.modules.fiscal_receipts.tasks import dispatch_fiscal_receipt   # NEW
from app.workers.scheduled.monitor_stale_fiscal_receipts import monitor_stale_fiscal_receipts  # NEW
from app.workers.scheduled.poll_pending_refunds import poll_pending_refunds  # NEW

# ...

functions: ClassVar[list[Any]] = [
    expire_memberships,
    send_expiring_notifications,
    expire_pt_packages,
    send_booking_reminders,
    mark_no_show_bookings,
    dispatch_email,
    cleanup_password_reset_tokens,
    dispatch_fiscal_receipt,                  # NEW (Phase 51 FISCAL-05)
    monitor_stale_fiscal_receipts,            # NEW (Phase 51 FISCAL-06)
    poll_pending_refunds,                     # NEW (Phase 51 REFUND-04)
]
```

**Cron registrations extension** (line 141 cron_jobs list):
```python
cron(
    monitor_stale_fiscal_receipts,
    minute={0, 15, 30, 45},                   # every 15 min per D-51-16
    hour=set(range(24)),
    unique=True,
    keep_result=60,
    run_at_startup=False,
),
cron(
    poll_pending_refunds,
    minute={0, 30},                           # every 30 min per D-51-17
    hour=set(range(24)),
    unique=True,
    keep_result=60,
    run_at_startup=False,
),
```

**Defensive check carry-forward** (on_startup lines 226-233) — `_validate_cron_function_names` will auto-fail at boot if cron registration references a function name NOT in `functions`. Adding cron entries WITHOUT adding the function to `functions` will trip this.

**Delta vs analog:**
- 3 new entries added to `functions` (1 task + 2 crons must also be listed there per the assertion at line 229).
- 2 new entries added to `cron_jobs`.
- ARQ 0.28 — D-51-Discretion notes `func(max_tries=3, timeout=20)` wrapper for `dispatch_fiscal_receipt`. Existing project uses bare callables in `functions` and per-enqueue overrides; need to either use a per-enqueue `_max_tries=3` from `_post_commit_enqueue` OR upgrade to the per-function wrapper.

---

### `apps/backend/app/core/audit.py` — append 3 LOCKED pairs (D-51-19)

**Analog:** Lines 343-360 (Phase 47 + Phase 50 entries).

**Excerpt pattern** (line 343 onward — current end of frozenset):
```python
# v1.7 (Phase 47 lock — emitted in Phases 49/50/51 per INFRA-34)
# Online payment lifecycle (Phase 49 PAY-03..05 / Phase 50 WH-04..06):
("online_payment_initiated", "online_payment"),
("yookassa_payment_created", "online_payment"),
("online_payment_succeeded", "online_payment"),
("online_payment_canceled", "online_payment"),
("online_payment_refunded", "online_payment"),
# Fiscal receipt lifecycle (Phase 50 FISCAL-01 / Phase 51 FISCAL-04..06):
("fiscal_receipt_dispatched", "fiscal_receipt"),
("fiscal_receipt_succeeded", "fiscal_receipt"),
("fiscal_receipt_failed", "fiscal_receipt"),
# Webhook intake audit trail (Phase 50 WH-01):
("yookassa_webhook_received", "yookassa_webhook"),
# Membership / PT-package activation via webhook (Phase 50 WH-05 / D-50-23):
("membership_activated_online", "membership"),
("pt_package_activated_online", "pt_package"),
# Online refund lifecycle (Phase 51 REFUND-01..04 / D-51-19):     # NEW
("online_refund_initiated", "online_refund"),                       # NEW
("online_refund_polled_settled", "online_refund"),                  # NEW
("online_refund_canceled", "online_refund"),                        # NEW
```

**Docstring catalog extension** (audit.py lines 124-198 catalog) — add corresponding entries for the 3 new pairs with payload-field listing.

**Effective count check:** Phase 50 brought to 13; Phase 51 adds 3 → **16 LOCKED events at end of Phase 51** (CONTEXT D-51-19 claims 14; discrepancy because Phase 47 INFRA-35 actually pre-registered more than 11. Planner verifies running count.)

**Delta vs analog:** 3 append-only lines + 3 catalog-docstring entries. AST gate at `tests/unit/test_locked_audit_events.py` (existing) will auto-detect that callsites reference these pairs.

---

### `apps/backend/app/core/audit_payloads.py` — 3 new Payload classes + `AUDIT_PAYLOAD_SCHEMAS` registration

**Analog primary:** `OnlinePaymentSucceededPayload` (line 787) + `MembershipActivatedOnlinePayload` (line 826) — BaseModel + ConfigDict(extra='forbid')

**Pattern for `OnlineRefundInitiatedPayload`** (Phase 51 D-51-19):
```python
class OnlineRefundInitiatedPayload(BaseModel):
    """Payload schema for ("online_refund_initiated", "online_refund") — Phase 51 REFUND-01.

    Emitted from the POST /online-payments/.../refund endpoint inside the
    initiate UoW (D-51-09). Fresh chain root: `audit_correlation_id` is a
    new uuid4 (not a CHILD of any prior chain).
    """

    model_config = ConfigDict(extra="forbid")

    audit_correlation_id: UUID | None
    online_refund_id: UUID
    online_payment_id: UUID
    original_payment_id: UUID
    amount_kopecks: int
    requested_by_user_id: UUID
    reason: str | None
```

**Pattern for `OnlineRefundPolledSettledPayload`** (D-51-19):
```python
class OnlineRefundPolledSettledPayload(BaseModel):
    """Emitted from poll_pending_refunds cron when synthesizing settle UoW after missed webhook (D-51-17)."""

    model_config = ConfigDict(extra="forbid")

    online_refund_id: UUID
    yookassa_refund_id: str
    settled_at: datetime
```

**Pattern for `OnlineRefundCanceledPayload`** (D-51-19):
```python
class OnlineRefundCanceledPayload(BaseModel):
    """Emitted from poll_pending_refunds cron when ЮKassa reports refund canceled (D-51-17 step 4)."""

    model_config = ConfigDict(extra="forbid")

    online_refund_id: UUID
    yookassa_refund_id: str
    cancellation_reason: str | None
```

**`AUDIT_PAYLOAD_SCHEMAS` registry entries** (line 1003) — append 3 lines:
```python
("online_refund_initiated", "online_refund"): OnlineRefundInitiatedPayload,
("online_refund_polled_settled", "online_refund"): OnlineRefundPolledSettledPayload,
("online_refund_canceled", "online_refund"): OnlineRefundCanceledPayload,
```

**Delta vs analog:** New `resource_type='online_refund'` introduced. Add to resource-type catalog docstring (audit.py:124-198).

---

### `apps/backend/app/main.py` — replace `phase49_fiscal_dispatcher_stub` with real impl

**Analog:** Lines 317-329 (Phase 47 / Phase 49 stub wiring).

**Pattern — replace stub with real ARQ enqueue function:**
```python
# Phase 51 FISCAL-05 — real FiscalReceiptDispatcher implementation.
# REG-29-03 double-wire (also wire in app/workers/__init__.py:293).
async def _real_fiscal_receipt_dispatcher(
    *,
    fiscal_receipt_id: UUID,
    audit_correlation_id: UUID | None,
) -> None:
    """Enqueue dispatch_fiscal_receipt ARQ task. Composition-root accessor."""
    arq_pool: ArqRedis = app.state.arq_pool   # set by lifespan; same as email dispatcher
    await arq_pool.enqueue_job(
        "dispatch_fiscal_receipt",
        str(fiscal_receipt_id),
        _max_tries=3,                          # D-51-Discretion / Pitfall 11 step 2
        _expires=60,
    )

register_fiscal_receipt_dispatcher(_real_fiscal_receipt_dispatcher)
```

**Mirror in `app/workers/__init__.py:on_startup`** (line 288-293):
```python
# Phase 51 FISCAL-05 — REG-29-03 mirror.
from app.modules.fiscal_receipts.tasks import _real_fiscal_receipt_dispatcher  # OR inline
register_fiscal_receipt_dispatcher(_real_fiscal_receipt_dispatcher)
```

**Delta vs analog:** `phase49_fiscal_dispatcher_stub` raises `NotImplementedError`; Phase 51 swaps in a real ArqRedis enqueue. Composition-root pattern (Phase 47 INFRA-38) preserved.

---

### `apps/backend/app/api/v1/_internal/yookassa/handlers.py` — `_post_commit_enqueue` signature extension (D-51-15)

**Analog:** Existing `_post_commit_enqueue` lines 169-197.

**Pattern — extend signature with `fiscal_receipt_id` default None + add fiscal dispatch branch:**
```python
async def _post_commit_enqueue(
    arq_pool: Any | None = None,
    *,
    online_payment_id: UUID,
    subject_kind: Literal["membership", "pt_package"],
    subject_id: UUID,
    fiscal_receipt_id: UUID | None = None,   # NEW (D-51-15 / D-51-Discretion)
) -> None:
    """Post-commit enqueue — Phase 51 fills the fiscal-dispatch branch.

    Phase 50 shipped as pure no-op. Phase 51 adds the fiscal_receipt_id branch.
    Phase 52 NOT-04/05 will add the notifications branch.
    """
    _log.info("webhook_post_commit_enqueue_skip", online_payment_id=str(online_payment_id), ...)
    if arq_pool is not None and fiscal_receipt_id is not None:
        await arq_pool.enqueue_job(
            "dispatch_fiscal_receipt",
            str(fiscal_receipt_id),
            _max_tries=3,
            _expires=60,
        )
```

**Callsite update (handlers.py:378)** — pass the just-INSERTed `fiscal_receipt_id`:
```python
# capture inside async with session.begin():
fiscal_receipt_row_id: UUID = fr_row.id   # after insert_fiscal_receipt(...)

# outside the with:
await _post_commit_enqueue(
    arq_pool,                              # NOW non-None (lift app.state.arq_pool)
    online_payment_id=op_row_id,
    subject_kind=subject_kind_local,
    subject_id=subject_id_local,
    fiscal_receipt_id=fiscal_receipt_row_id,   # NEW
)
```

**AST gate update (D-51-15):** `tests/integration/webhook_yookassa/test_post_commit_seam.py` currently asserts the body is ONLY a `_log.info()` call (Phase 50 AST gate). Phase 51 plan 51-06 must FLIP this gate to assert `if arq_pool is not None and fiscal_receipt_id is not None: arq_pool.enqueue_job(...)` is present. **This is a discrete task per CONTEXT D-51-15.**

---

## Shared Patterns

### Authentication / Authorization

**Source:** `app/core/dependencies.py:require_permission` + `verify_csrf`
**Apply to:** `app/api/v1/online_payments/router.py` (new refund endpoint)
**Excerpt** (memberships/router.py lines 528-533):
```python
actor: Annotated[
    CurrentUser,
    Depends(require_permission(Action.REFUND, Resource.MEMBERSHIPS)),
],
_csrf: Annotated[None, Depends(verify_csrf)],
```
- `(Action.REFUND, Resource.MEMBERSHIPS)` and `(Action.REFUND, Resource.PT_PACKAGES)` ALREADY exist (D-51-10 / Phase 32 / Phase 33). No new permission registration needed.
- `_internal/yookassa/webhook` is anonymous-by-design (D-50-39); IP-gate-only. Existing `EXCLUDED_PATHS` in `tests/integration/test_route_introspection.py` covers it.

### Atomic UoW (caller-owns-txn)

**Source:** `apps/backend/app/api/v1/_internal/yookassa/handlers.py:handle_payment_succeeded` (line 200)
**Apply to:** All new webhook handlers (`handle_refund_succeeded`, `handle_receipt_succeeded`, `handle_receipt_canceled`) + `online_refunds/service.py:initiate_online_refund`
**Excerpt** (handlers.py lines 237-378):
```python
webhook_intake_corr = uuid4()

async with session.begin():
    row = await _select_for_update_<X>(session, ...)
    if row is None: return
    try:
        _assert_can_transition_<X>(row, target=...)
    except InvalidTransitionError:
        await audit.emit(session, "yookassa_webhook_received", ..., idempotency_outcome="illegal_transition")
        return
    # MUTATE row
    # CHILD audit emit(s)
    # ROOT audit emit (yookassa_webhook_received) — LAST per D-50-18 step 8
```

### Error Handling (refund-of partial UNIQUE idempotency)

**Source:** `app/modules/payments/repository.py:_is_refund_of_uniqueness_conflict` + `app/modules/memberships/service.py:refund_membership` (line 949)
**Apply to:** `handle_refund_succeeded` (D-51-05)
**Pattern:**
```python
try:
    refund_payment_row = await get_payment_refunder()(...)
except IntegrityError as exc:
    if _is_refund_of_uniqueness_conflict(exc):
        # REFUND-03 idempotent — return 200 silently
        _log.warning("yookassa_refund_idempotent_replay", ...)
        return
    raise
```

### Validation (Pydantic v2 schemas + ConfigDict(extra='forbid'))

**Source:** `app/core/audit_payloads.py` (BaseModel pattern) + `app/core/schemas.py:BackendSchemaBase`
**Apply to:** All new audit payload classes + `OnlineRefundRequest` / `OnlineRefundResponse`
**Excerpt** (audit_payloads.py lines 787-803):
```python
class XxxPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audit_correlation_id: UUID | None
    # ... typed fields
```

### Re-fetch-before-write doctrine (D-50-12 / Pitfall 1)

**Source:** `handlers.py:handle_payment_succeeded` lines 219-235
**Apply to:** ONLY `handle_refund_succeeded` (D-51-11 step 2) — receipt webhooks do NOT re-fetch (D-51-03).
**Excerpt:**
```python
result = await yookassa_client.get_refund(object_id)
if result.classification != "ok":
    _log.warning("yookassa_refund_refetch_failed", ...); return
if result.status != "succeeded":
    _log.info("yookassa_refund_pending_skip", ...); return
```

### Redis dedup (D-50-07 / Pitfall 10)

**Source:** `app/api/v1/_internal/yookassa/router.py` lines 102-110
**Apply to:** Already covers all event types via `sz:yookassa:webhook:{event_type}:{object_id}` formula. **No new code needed** (D-51-12) — the new `refund.succeeded` / `receipt.succeeded` / `receipt.canceled` branches naturally use the existing dedup key prefix.

### Audit emit (LOCKED events) + JSONB UUID str-casting

**Source:** `handlers.py:handle_payment_succeeded` lines 340-366 + `memberships/service.py:refund_membership` lines 974-984
**Apply to:** All new audit emit callsites
**Critical invariant:** **All UUID kwargs MUST be str-cast** (e.g. `str(row.id)`). audit.emit stores payload kwargs directly in a JSONB column; raw UUIDs fail JSON encoder. Phase 32-02 deviation #1 lesson — see comment at memberships/service.py:923-925.

### ARQ task retry + circuit breaker

**Source:** `apps/backend/app/workers/tasks/dispatch_email.py` lines 65-137 + `app/integrations/email/circuit_breaker.py`
**Apply to:** `dispatch_fiscal_receipt` task
**Pattern:** check `is_circuit_open(redis, "receipts")` BEFORE provider call → on transient_error call `record_failure(redis, "receipts")` + raise `arq.Retry(defer=...)` with exponential backoff + jitter (30/120/600s ±10%, D-51-14 / Pitfall 11).

### Composition-root double-wire (REG-29-03)

**Source:** `app/main.py:create_app()` lines 317-329 + `app/workers/__init__.py:on_startup` lines 252-293
**Apply to:** `register_fiscal_receipt_dispatcher(_real_fiscal_receipt_dispatcher)` — MUST be wired in BOTH `main.py` AND `workers/__init__.py` (REG-29-03 double-wire — Phase 47 INFRA-38).

---

## No Analog Found

All new files have at least one strong analog. The patterns are well-established across Phase 32 (offline refunds), Phase 42 (email circuit breaker + ARQ task), Phase 47 (Protocol slots + LOCKED events), Phase 49 (online_payments module), and Phase 50 (webhook handlers + fiscal_receipts module).

The closest things to "no analog" are:

| File | Role | Closest Match | Why "partial" |
|------|------|---------------|---------------|
| `YooKassaReceiptResult` field expansion | dataclass | `YooKassaRefundResult` | The skeleton already exists at `types.py:119` as a placeholder; Phase 51 only needs to confirm shape — current 5 attrs (ok, classification, receipt_id, error_code, http_status, error) are sufficient per D-51-20. **No structural delta — flagging only for awareness.** |
| `unit/test_yookassa_circuit_breaker.py` | tests | (no existing yookassa-breaker test) | A separate `tests/integration/test_email_circuit_breaker.py` or similar may exist; if not, mirror the dispatch_email test fixtures for the breaker atomic-pipeline assertions. **Planner verifies test home before writing.** |

---

## Metadata

**Analog search scope:**
- `apps/backend/app/modules/` (all submodules — focus on online_payments, fiscal_receipts, memberships, pt_packages, payments)
- `apps/backend/app/integrations/email/` + `integrations/yookassa/`
- `apps/backend/app/api/v1/_internal/`
- `apps/backend/app/workers/scheduled/` + `workers/tasks/`
- `apps/backend/alembic/versions/0034*` + `0035*`
- `apps/backend/app/core/audit.py` + `audit_payloads.py` + `dependencies.py`

**Files scanned:** 24 analog files, all read in full or in targeted sections (no re-reads).

**Pattern extraction date:** 2026-05-23

**Key structural observations:**
1. **Migration number conflict** — `0036` is taken; Phase 51 must use `0037` and update `down_revision`. CONTEXT D-51-06 needs an erratum.
2. **Router prefix conflict** — both `app/modules/online_payments/router.py` and the proposed `app/api/v1/online_payments/router.py` mount at `/online-payments`. Planner resolves by either consolidating into the existing router OR confirming FastAPI's multi-include behavior preserves distinct paths.
3. **D-51-15 in-place AST gate flip** — `test_post_commit_enqueue_body_is_only_log_info` becomes `test_post_commit_enqueue_dispatches_fiscal_receipt`. Plan 51-06 MUST atomically ship the body fill + gate update (single PR, single commit) to avoid CI flake.
4. **REG-29-03 double-wire** — replacing `phase49_fiscal_dispatcher_stub` requires SYNCHRONOUS edits to BOTH `app/main.py:329` AND `app/workers/__init__.py:293`.
5. **Activator slot rule** — Phase 51 webhook does NOT use `MembershipActivator`/`PtPackageActivator` for the refund subject transition (those are forward-only per D-51-11); direct repository call is the documented pattern.
6. **Pitfall 12 atomic-UoW** — Phase 51's `handle_refund_succeeded` extends the Phase 50 atomic-UoW shape to 4 simultaneous writes (online_refunds UPDATE + payments INSERT + memberships UPDATE + fiscal_receipts INSERT) inside a single `async with session.begin()` block.
