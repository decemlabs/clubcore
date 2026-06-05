# Phase 79: Payment Methods Foundation + Card-on-File — Pattern Map

**Mapped:** 2026-06-03
**Files analyzed:** 7 (2 new, 5 modified)
**Analogs found:** 7 / 7

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/backend/alembic/versions/0052_*.py` | migration | batch (DDL) | `alembic/versions/0046_promo_codes.py` | exact |
| `app/modules/payment_methods/models.py` | model | CRUD | `app/modules/promo_codes/models.py` | exact |
| `app/modules/payment_methods/repository.py` | repository | CRUD | `app/modules/client_portal/repository.py` | exact |
| `app/modules/payment_methods/schemas.py` | schema | request-response | `app/modules/client_portal/schemas.py` | exact |
| `app/modules/payment_methods/service.py` | service | CRUD | `app/modules/promo_codes/service.py` | exact |
| `app/modules/client_portal/router.py` | controller | request-response | (self — add endpoints) | exact |
| `app/modules/client_portal/schemas.py` | schema | request-response | (self — add schemas) | exact |
| `app/api/v1/_internal/yookassa/handlers.py` | service | event-driven | (self — add step 8.5) | exact |
| `app/integrations/yookassa/types.py` | model | request-response | (self — add field) | exact |
| `apps/backend/.importlinter` | config | — | (self — add contract entry) | exact |

---

## Pattern Assignments

### `apps/backend/alembic/versions/0052_*.py` (migration, DDL)

**Primary analog:** `apps/backend/alembic/versions/0046_promo_codes.py`
**Secondary analog (column-add):** `apps/backend/alembic/versions/0050_clients_notif_prefs.py`

**File header + metadata pattern** (0046, lines 1-32):
```python
"""client_payment_methods table + save_payment_method column on online_payments (Phase 79 PAYM-01..04).

Revision ID: 0052_client_payment_methods
Revises: 0051_seed_fit15_promo
Create Date: 2026-06-03 00:00:00.000000

Ships two DDL changes:
- client_payment_methods: new table with partial UNIQUE on client_id WHERE unlinked_at IS NULL
  (single active card per client, uq_client_payment_methods_client_id_alive).
- online_payments: adds save_payment_method boolean column (intent flag read by webhook step 8.5).

Partial UNIQUE index name (uq_client_payment_methods_client_id_alive) is a LITERAL string —
NOT wrapped in op.f() — per 0034/0037/0046 create_index precedent.
All FK and PK constraint names pass through op.f() (already-expanded names).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import func, text
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0052_client_payment_methods"
down_revision: str | None = "0051_seed_fit15_promo"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**Table creation pattern** (0046, lines 36-90) — copy `op.create_table(...)` shape with `postgresql.UUID(as_uuid=True)` PK, `sa.text("gen_random_uuid()")` server_default, `func.now()` for timestamps, `op.f("pk_...")` / `op.f("fk_...")` constraint names:
```python
def upgrade() -> None:
    # --- client_payment_methods ---
    op.create_table(
        "client_payment_methods",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("yookassa_method_id", sa.Text(), nullable=False),   # plaintext token
        sa.Column("last4", sa.Text(), nullable=False),
        sa.Column("brand", sa.Text(), nullable=False),
        sa.Column("expiry_month", sa.Integer(), nullable=True),
        sa.Column("expiry_year", sa.Integer(), nullable=True),
        sa.Column("autopay_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("consent_recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unlinked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_client_payment_methods")),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            name=op.f("fk_client_payment_methods_client_id_clients"),
            ondelete="RESTRICT",
        ),
    )
    # Partial UNIQUE: single active card per client (literal name, NOT via op.f())
    op.create_index(
        "uq_client_payment_methods_client_id_alive",
        "client_payment_methods",
        ["client_id"],
        unique=True,
        postgresql_where=text("unlinked_at IS NULL"),
    )

    # --- online_payments: add save_payment_method intent column ---
    # ADD COLUMN is metadata-only on Postgres 16 — negligible lock window.
    op.add_column(
        "online_payments",
        sa.Column(
            "save_payment_method",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("online_payments", "save_payment_method")
    op.drop_index("uq_client_payment_methods_client_id_alive", table_name="client_payment_methods")
    op.drop_table("client_payment_methods")
```

Key rules from 0046 and 0050:
- Partial UNIQUE index names are LITERAL strings passed directly (not via `op.f()`) — matches 0034/0037/0046 `create_index` precedent.
- FK and PK constraint names pass through `op.f()`.
- `ADD COLUMN` (0050 pattern) is metadata-only on Postgres 16 — no lock concerns.

---

### `app/modules/payment_methods/models.py` (model, CRUD)

**Analog:** `app/modules/promo_codes/models.py`

**Module docstring + import pattern** (lines 1-50):
```python
"""ClientPaymentMethod ORM model (Phase 79 PAYM-01..04).

Single active card per client: partial UNIQUE uq_client_payment_methods_client_id_alive:
  client_id WHERE unlinked_at IS NULL.
Token yookassa_method_id stored plaintext. NEVER serialized to the client.
Composition: Base + UUIDPkMixin + TimestampMixin (no SoftDeleteMixin — lifecycle
tracked via explicit unlinked_at column, mirrors online_payments/models.py single-
temporal-column discipline).

NAMING_CONVENTION note: CheckConstraint name= takes a BARE suffix.
ck_%(table_name)s_%(constraint_name)s template applies the prefix automatically.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base, TimestampMixin, UUIDPkMixin
```

**ORM class pattern** (promo_codes/models.py lines 52-88):
```python
class ClientPaymentMethod(Base, UUIDPkMixin, TimestampMixin):
    """Payment method (saved card) for a client (Phase 79 PAYM-01..04)."""

    __tablename__ = "client_payment_methods"

    client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "clients.id",
            ondelete="RESTRICT",
            name="fk_client_payment_methods_client_id_clients",
        ),
        nullable=False,
    )
    yookassa_method_id: Mapped[str] = mapped_column(Text, nullable=False)  # plaintext; NEVER wired to client
    last4: Mapped[str] = mapped_column(Text, nullable=False)
    brand: Mapped[str] = mapped_column(Text, nullable=False)
    expiry_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expiry_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    autopay_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    consent_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unlinked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # Partial UNIQUE: single active card per client (literal name, no convention expansion).
        Index(
            "uq_client_payment_methods_client_id_alive",
            "client_id",
            unique=True,
            postgresql_where=text("unlinked_at IS NULL"),
        ),
    )
```

---

### `app/modules/payment_methods/repository.py` (repository, CRUD)

**Analog:** `app/modules/client_portal/repository.py` (raw-SQL D-54-08 discipline)

**Module docstring + import pattern** (client_portal/repository.py lines 1-30):
```python
"""Payment methods repository (app.modules.payment_methods.repository) — raw-SQL + ORM writes.

CROSS-MODULE READ DISCIPLINE (D-54-08 / D-20-MODULE):
  - ``from sqlalchemy import text`` for cross-module reads — NEVER import another module's ORM.
  - Bind params via ``:name`` placeholders + a dict; cast UUIDs to ``str``.
  - ``.mappings().one_or_none()`` for scalar reads.
  - Read-only reads return None if absent (200/null empty-state discipline, D-69-03).

INVARIANTS:
  - ORM model imports from app.modules.*: FORBIDDEN (except this module's own models).
  - ORM model imports from app.core.*: ALLOWED.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payment_methods.models import ClientPaymentMethod
```

**Raw-SQL read pattern** (client_portal/repository.py):
```python
async def fetch_active_payment_method(
    session: AsyncSession,
    client_id: UUID,
) -> dict | None:
    """Fetch the active (unlinked_at IS NULL) card for a client.

    Returns None when no active card exists (200/null empty-state, D-69-03).
    NEVER returns yookassa_method_id — caller must exclude that column from response.
    """
    row = (
        await session.execute(
            text(
                "SELECT id, last4, brand, expiry_month, expiry_year, "
                "autopay_enabled, consent_recorded_at, created_at "
                "FROM client_payment_methods "
                "WHERE client_id = :client_id AND unlinked_at IS NULL"
            ),
            {"client_id": str(client_id)},
        )
    ).mappings().one_or_none()
    return dict(row) if row is not None else None
```

**Upsert pattern** (promo_codes/service.py lines 393-403 — `pg_insert(...).on_conflict_do_update`):
The webhook step 8.5 raw-SQL upsert goes in `handlers.py` directly (not through the repository), per the D-decision: "raw-SQL upsert inside `handle_payment_succeeded` step 8.5, zero new `ignore_imports`". Use `text()` INSERT...ON CONFLICT DO UPDATE directly in the handler.

**Soft-delete write pattern** (ORM mutation — mirrors `row.status = STATUS_CANCELED; row.canceled_at = datetime.now(UTC)` from handlers.py lines 678-679):
```python
async def unlink_payment_method(
    session: AsyncSession,
    client_id: UUID,
) -> bool:
    """Soft-delete the active card row. Returns True if a row was found and unlinked."""
    # Fetch-then-mutate (SELECT → UPDATE in same txn) — caller owns commit.
    row = (
        await session.execute(
            text(
                "SELECT id FROM client_payment_methods "
                "WHERE client_id = :client_id AND unlinked_at IS NULL "
                "FOR UPDATE"
            ),
            {"client_id": str(client_id)},
        )
    ).mappings().one_or_none()
    if row is None:
        return False
    await session.execute(
        text(
            "UPDATE client_payment_methods "
            "SET unlinked_at = now(), autopay_enabled = false "
            "WHERE id = :id"
        ),
        {"id": str(row["id"])},
    )
    return True
```

---

### `app/modules/payment_methods/schemas.py` (schema, request-response)

**Analog:** `app/modules/client_portal/schemas.py`

**Base class + camelCase alias pattern** (schemas.py lines 15-22):
```python
"""Payment method Pydantic schemas (Phase 79 PAYM-02/04).

Client-safe field projection: NEVER include yookassa_method_id.
camelCase wire via alias_generator=to_camel on ResponseData base.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.core.schemas import ResponseData
```

**Response schema pattern** (mirrors ClientMembershipResponse, lines 24-39):
```python
class ClientPaymentMethodResponse(ResponseData):
    """GET /client/payment-method payload — display fields only (PAYM-02).

    yookassa_method_id is NEVER included (D-decision: token never wired to client).
    expiry_month / expiry_year optional (may be absent for some card types).
    consent_recorded_at: None means autopay has never been enabled.
    """

    id: UUID
    last4: str
    brand: str
    expiry_month: int | None = None  # wire: expiryMonth
    expiry_year: int | None = None   # wire: expiryYear
    autopay_enabled: bool            # wire: autopayEnabled
    consent_recorded_at: datetime | None = None  # wire: consentRecordedAt
```

**Request body schema pattern** (mirrors ClientProfileUpdateRequest, lines 301-319):
```python
class ClientAutopayPatchRequest(ResponseData):
    """PATCH /client/payment-method/autopay body (PAYM-04).

    enable=True requires consent_acknowledged=True (ФЗ-376 gate).
    enable=False is ungated — no consent needed.
    extra='forbid' (inherited from ResponseData) rejects unknown keys.
    """

    enabled: bool
    consent_acknowledged: bool = False  # wire: consentAcknowledged; required when enabled=True
```

---

### `app/modules/payment_methods/service.py` (service, CRUD)

**Analog:** `app/modules/promo_codes/service.py`

**Module docstring + structlog pattern** (promo_codes/service.py lines 1-36):
```python
"""Payment method service (Phase 79 PAYM-02..04).

get_payment_method: returns active card for client (200/null if absent, D-69-03).
unlink_payment_method: soft-delete (idempotent 204 no-op if absent, D-decision).
patch_autopay: enable/disable autopay; enable gates on consent (ФЗ-376, PAYM-04).

Error discipline: distinct AppError subclasses with stable code= attribute.
No try/except — AppError bubbles to _app_error_handler.
No session.commit() — caller-owns-txn (D-32-10/D-49-19).
"""

from __future__ import annotations

import structlog
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.payment_methods import repository
from app.modules.payment_methods.schemas import (
    ClientAutopayPatchRequest,
    ClientPaymentMethodResponse,
)

_log = structlog.get_logger("modules.payment_methods.service")
```

**Service function pattern with 409 guard** (mirrors promo_codes/service.py ConflictError discipline):
```python
async def patch_autopay(
    session: AsyncSession,
    client_id: UUID,
    payload: ClientAutopayPatchRequest,
) -> ClientPaymentMethodResponse:
    """Enable/disable autopay for the client's active card (PAYM-04 / ФЗ-376).

    Enable path: requires active card AND consent_acknowledged=True in the same
    request → server stamps consent_recorded_at=now(). Missing either → 409.
    Disable path: ungated — always succeeds if an active card exists.
    No session.commit() — caller-owns-txn.
    """
    row = await repository.fetch_active_payment_method(session, client_id)
    if row is None:
        raise ConflictError("no_active_payment_method")
    if payload.enabled and not payload.consent_acknowledged:
        raise ConflictError("consent_required")
    # ... mutate ...
```

---

### MODIFY `app/modules/client_portal/router.py` (controller, request-response)

**Analog:** self (existing endpoints in the same file)

**GET 200/null empty-state pattern** (router.py lines 138-156 — `client_get_membership`):
```python
@router.get(
    "/payment-method",
    response_model=ResponseEnvelope[ClientPaymentMethodResponse | None],
    operation_id="client_get_payment_method",
    summary="Active payment method for the authenticated client (PAYM-02; 200 null if none)",
)
async def client_get_payment_method(
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientPaymentMethodResponse | None]:
    """D-69-03: no active card → 200 with null, not 404.
    D-20-IDOR: client_id injected from cookie principal, not URL param.
    No CSRF dep — GET is safe.
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.get_payment_method(session, client.id)
    return envelope(result)
```

**DELETE 204 idempotent pattern** (mirrors `client_cancel_booking` lines 395-430 — `require_client()` + `verify_client_csrf` + IDOR discipline):
```python
@router.delete(
    "/payment-method",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="client_delete_payment_method",
    summary=(
        "Soft-delete the authenticated client's active payment method (PAYM-03); "
        "204 No Content; idempotent no-op if no active card"
    ),
)
async def client_delete_payment_method(
    client: Annotated[ClientPrincipal, Depends(require_client())],
    _csrf: Annotated[None, Depends(verify_client_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """RBAC-04 ordering: require_client() → verify_client_csrf → get_db.
    IDOR: client_id from principal only — no URL param.
    Idempotent: deleting absent/already-unlinked card is a 204 no-op.
    No try/except — AppError bubbles to _app_error_handler.
    Commit owner: caller-owns-txn (D-32-10/D-49-19).
    """
    await service.unlink_payment_method(session, client.id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

**PATCH pattern** (mirrors `client_update_me` lines 743-780):
```python
@router.patch(
    "/payment-method/autopay",
    response_model=ResponseEnvelope[ClientPaymentMethodResponse],
    status_code=status.HTTP_200_OK,
    operation_id="client_patch_payment_method_autopay",
    summary=(
        "Enable/disable autopay for the authenticated client's active card (PAYM-04); "
        "409 no_active_payment_method if no card; 409 consent_required if enable without consent"
    ),
)
async def client_patch_payment_method_autopay(
    payload: ClientAutopayPatchRequest,
    client: Annotated[ClientPrincipal, Depends(require_client())],
    _csrf: Annotated[None, Depends(verify_client_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientPaymentMethodResponse]:
    """RBAC-04 ordering: require_client() → verify_client_csrf → get_db.
    No try/except — AppError bubbles to _app_error_handler.
    Commit owner: caller-owns-txn (D-32-10/D-49-19); service never commits.
    """
    result = await service.patch_autopay(session, client.id, payload)
    await session.commit()
    return envelope(result)
```

**ruff I001 fold note:** The `from app.modules.client_portal.schemas import (...)` block (lines 49-72) must have its imports alphabetically sorted when adding `ClientAutopayPatchRequest` and `ClientPaymentMethodResponse`.

---

### MODIFY `app/modules/client_portal/schemas.py` (schema, request-response)

**Analog:** self (existing schemas in the same file)

**`save_payment_method` field on checkout body** (mirrors `promo_code` addition at lines 245-253):
```python
class ClientCheckoutRequest(ResponseData):
    """Request body for client-initiated checkout (CPAY-01/02).

    Phase 999.4 D-06: optional promo_code field (wire: promoCode).
    Phase 79 PAYM-01: optional save_payment_method flag (wire: savePaymentMethod).
    """

    promo_code: str | None = None           # wire: promoCode (D-06); None = no promo applied
    save_payment_method: bool = False       # wire: savePaymentMethod (PAYM-01); False = don't save
```

Payment method response schemas are declared in `app/modules/payment_methods/schemas.py` (the new module) and re-exported from there, NOT duplicated in `client_portal/schemas.py`. The router imports them from `payment_methods.schemas` directly (mirrors how `promo_codes.service` is imported from `client_portal.service`).

---

### MODIFY `app/api/v1/_internal/yookassa/handlers.py` — step 8.5 (service, event-driven)

**Analog:** self — the existing promo redemption step (lines 497-528) immediately before the CHILD audit emit

**Where step 8.5 lands:** After the promo redemption block (after line 528), before the `online_payment_succeeded` CHILD audit emit (line 531). The hook checks `row.save_payment_method` (the new column on `online_payments`), then reads the `payment_method` object from `result` (the re-fetched `YooKassaPaymentResult`), and upserts via raw SQL.

**Step 8.5 pattern** (copy promo redemption structure, lines 497-528):
```python
        # PAYM-01 / Phase 79 step 8.5: upsert saved card token if save_payment_method=True.
        # raw-SQL upsert — zero new ignore_imports (D-decision).
        # Token source: result.payment_method (YooKassaPaymentResult field added in this phase).
        # Idempotent: ON CONFLICT DO UPDATE so webhook replay is safe.
        if row.save_payment_method and result.payment_method is not None:
            pm = result.payment_method  # YooKassaPaymentMethodInfo dataclass
            await session.execute(
                text(
                    "INSERT INTO client_payment_methods "
                    "(client_id, yookassa_method_id, last4, brand, "
                    " expiry_month, expiry_year, autopay_enabled) "
                    "VALUES (:client_id, :method_id, :last4, :brand, "
                    "        :expiry_month, :expiry_year, false) "
                    "ON CONFLICT ON CONSTRAINT uq_client_payment_methods_client_id_alive "
                    "DO UPDATE SET "
                    "  yookassa_method_id = EXCLUDED.yookassa_method_id, "
                    "  last4 = EXCLUDED.last4, "
                    "  brand = EXCLUDED.brand, "
                    "  expiry_month = EXCLUDED.expiry_month, "
                    "  expiry_year = EXCLUDED.expiry_year, "
                    "  unlinked_at = NULL, "
                    "  autopay_enabled = false, "
                    "  consent_recorded_at = NULL, "
                    "  updated_at = now()"
                ),
                {
                    "client_id": str(row.client_id),
                    "method_id": pm.id,
                    "last4": pm.last4,
                    "brand": pm.card_type,
                    "expiry_month": pm.expiry_month,
                    "expiry_year": pm.expiry_year,
                },
            )
            _log.info(
                "payment_method_saved",
                client_id=str(row.client_id),
                online_payment_id=str(row.id),
            )
```

**NOTE:** The partial UNIQUE constraint name `uq_client_payment_methods_client_id_alive` is a literal string in the ON CONFLICT clause — matches the migration create_index literal name.

**Save_payment_method column read:** `row.save_payment_method` references the new Boolean column added to `online_payments` by migration 0052. The ORM model (`app/modules/online_payments/models.py`) must also gain this column:
```python
save_payment_method: Mapped[bool] = mapped_column(
    Boolean, nullable=False, server_default=text("false")
)
```

---

### MODIFY `app/integrations/yookassa/types.py` — add `payment_method` field (model, request-response)

**Analog:** self — existing frozen dataclasses in the same file

**Existing `YooKassaPaymentResult` dataclass** (lines 51-97) — append a new optional field following the `error_parameter` field:

**New companion dataclass** (mirrors `YooKassaRefundResult` shape at lines 100-121 — frozen dataclass with primitives only, cloudpickle-safe):
```python
@dataclass(frozen=True)
class YooKassaPaymentMethodInfo:
    """Card display info extracted from payment.succeeded webhook re-fetch (Phase 79 PAYM-01).

    Populated when the ЮKassa ``GET /v3/payments/{id}`` response includes
    ``payment_method.type == 'bank_card'``. ``None`` when the payment used a
    non-card method or the response omits the field.

    cloudpickle-safe: primitives only. Frozen for value-object semantics.
    Layer invariant: integrations layer — MUST NOT import from app.modules.*.
    """

    id: str           # yookassa payment_method.id — the saved token
    last4: str        # last 4 digits of the card
    card_type: str    # e.g. 'MasterCard', 'Visa', 'Mir'
    expiry_month: int | None = None
    expiry_year: int | None = None
```

**Field addition to `YooKassaPaymentResult`** (after `error_parameter` at line 97):
```python
    payment_method: "YooKassaPaymentMethodInfo | None" = None
    # ^ Populated on ok classification when save_payment_method=True was requested
    #   and the response includes payment_method.type='bank_card' (Phase 79 PAYM-01).
    #   Forward reference string annotation avoids ordering dependency if
    #   YooKassaPaymentMethodInfo is defined after YooKassaPaymentResult in the file.
```

**Client extraction pattern** (the `YooKassaClient.get_payment` method in `app/integrations/yookassa/client.py` populates this field when parsing the response JSON — extract `response_data["payment_method"]` if present and `type == "bank_card"`).

---

### MODIFY `apps/backend/.importlinter` — register `app.modules.payment_methods` (config)

**Analog:** self — the existing `modules-independent` contract block

**Where to add** (after `app.modules.client_auth` entry, before the `ignore_imports` block — lines 47-48 in `.importlinter`):

```ini
    app.modules.payment_methods
    # Phase 79 PAYM-01..04 — payment methods module registered per INFRA-15 discipline.
    # Token upsert in handlers.py step 8.5 uses raw SQL (no ORM import from integrations
    # layer). Router endpoints live in client_portal/router.py; service + repository
    # under payment_methods/. Zero new ignore_imports needed: client_portal.service
    # calls payment_methods.service + payment_methods.repository directly, which
    # requires two new ignore edges declared below.
```

**New ignore_imports edges** (after existing `client_portal.service → promo_codes.*` block at lines 186-189):
```ini
    app.modules.client_portal.service -> app.modules.payment_methods.service
    app.modules.client_portal.service -> app.modules.payment_methods.repository
    # Phase 79 PAYM-02..04 — client_portal.service orchestrates payment method reads
    # and writes by calling payment_methods.service. Option B (direct ignore edges)
    # mirrors the existing client_portal.service → promo_codes.service precedent.
```

---

## Shared Patterns

### `require_client()` IDOR discipline
**Source:** `app/modules/client_portal/router.py` lines 144-146, 406-411
**Apply to:** All four new router endpoints
```python
# client_id ALWAYS from principal — NEVER from URL param or request body
client: Annotated[ClientPrincipal, Depends(require_client())],
# Non-owned resource → 404-collapse (anti-oracle), never 403
```

### RBAC-04 dependency ordering
**Source:** `app/modules/client_portal/router.py` lines 406-410 (`client_cancel_booking`)
**Apply to:** DELETE + PATCH endpoints (state-changing methods)
```python
# Correct order: require_client() → verify_client_csrf → get_db
client: Annotated[ClientPrincipal, Depends(require_client())],
_csrf: Annotated[None, Depends(verify_client_csrf)],
session: Annotated[AsyncSession, Depends(get_db)],
```
GET endpoints: NO `verify_client_csrf` dep (safe method).

### Caller-owns-txn (no commit in service)
**Source:** `app/modules/client_portal/router.py` lines 594-595, 637-638
**Apply to:** DELETE + PATCH router handlers
```python
    # service only flushes; router commits
    await service.<mutate>(session, ...)
    await session.commit()
```

### 200/null empty-state (not 404)
**Source:** `app/modules/client_portal/router.py` lines 147-156 (D-69-03)
**Apply to:** `GET /client/payment-method`
```python
response_model=ResponseEnvelope[ClientPaymentMethodResponse | None]
# Returns envelope(None) when no active card — never 404
```

### Raw-SQL cross-module reads (D-54-08)
**Source:** `app/modules/client_portal/repository.py` lines 1-17
**Apply to:** `payment_methods/repository.py`
```python
# from sqlalchemy import text — NEVER import another module's ORM model
# .mappings().one_or_none() for scalar; cast UUIDs to str in bind params
```

### structlog module logger
**Source:** `app/modules/promo_codes/service.py` line 36
**Apply to:** `payment_methods/service.py`
```python
_log = structlog.get_logger("modules.payment_methods.service")
```

### ResponseData base class for schemas
**Source:** `app/modules/client_portal/schemas.py` line 22
**Apply to:** `payment_methods/schemas.py`
```python
from app.core.schemas import ResponseData
# ResponseData provides alias_generator=to_camel + extra='forbid'
```

### Webhook step 8.5 — raw-SQL inside `async with session.begin():`
**Source:** `app/api/v1/_internal/yookassa/handlers.py` lines 388, 497-528
**Apply to:** step 8.5 in `handle_payment_succeeded`
```python
# All DB writes inside the existing `async with session.begin():` block
# Raw SQL text() only — no ORM import from integrations layer (D-54-08)
# Idempotent: ON CONFLICT DO UPDATE — safe on webhook replay
```

---

## No Analog Found

All 7 file targets have strong analogs in the codebase. No entries in this section.

---

## Metadata

**Analog search scope:** `apps/backend/alembic/versions/`, `apps/backend/app/modules/`, `apps/backend/app/api/v1/_internal/yookassa/`, `apps/backend/app/integrations/yookassa/`, `apps/backend/.importlinter`
**Files scanned:** 12
**Pattern extraction date:** 2026-06-03
