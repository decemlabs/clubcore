# Phase 50: Webhook FSM + Fiscal Foundation - Pattern Map

**Mapped:** 2026-05-22
**Files analyzed:** 18 new/modified files (5 router/handler/module new, 1 alembic new, 4 fiscal_receipts new, 1 ORM model new, 2 service body fills, 2 audit registry edits, 2 constants edits, 4 test files / extensions)
**Analogs found:** 17 / 18 (every new file has a concrete in-repo analog except `_post_commit_enqueue` no-op stub)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `app/api/v1/_internal/yookassa/__init__.py` (new) | package-marker | n/a | `app/api/v1/_internal/email/__init__.py` (if present) / `app/modules/online_payments/__init__.py` | role-match |
| `app/api/v1/_internal/yookassa/router.py` (new) | transport-router | request-response (webhook) | `app/api/v1/_internal/email/router.py` | **exact** (route-level `dependencies=[...]`, anonymous-by-design, structlog naming, single POST `/webhook`) |
| `app/api/v1/_internal/yookassa/handlers.py` (new) | event-dispatcher / FSM-driver | event-driven + DB-transactional UoW | `app/modules/memberships/service.py:cancel_membership` (lines 791-874) for FSM-guard-then-mutate-then-audit; `app/modules/online_payments/service.py:sell_membership` for orchestrator shape | role-match (no exact analog for 8-step UoW; combine 2) |
| `app/api/v1/router.py` (mod) | composition / mount | n/a | existing mount of `email_webhook_router` at lines 83-87 | **exact** |
| `alembic/versions/0035_fiscal_receipts.py` (new) | migration | schema-DDL | `alembic/versions/0034_online_payments.py` | **exact** (op.f() naming, UUID PK pattern, CHECK shapes, IMMUTABLE-safe SQL) |
| `app/modules/fiscal_receipts/__init__.py` (new) | package-marker | n/a | `app/modules/online_payments/__init__.py` | role-match |
| `app/modules/fiscal_receipts/constants.py` (new) | declarative-FSM constant | n/a | `app/modules/memberships/constants.py` (line 22) + `app/modules/online_payments/constants.py` | **exact** |
| `app/modules/fiscal_receipts/models.py` (new) | ORM model | n/a | `app/modules/online_payments/models.py` | **exact** (Base + UUIDPkMixin, NAMING_CONVENTION bare suffixes, single-temporal-column FSM, CHECK shape) |
| `app/modules/fiscal_receipts/repository.py` (new) | repository (caller-owns-txn) | CRUD | `app/modules/online_payments/repository.py` | **exact** |
| `app/modules/online_payments/constants.py` (mod, ADD) | declarative-FSM constant | n/a | `app/modules/memberships/constants.py:22` (MEMBERSHIP_STATUS_TRANSITIONS) | **exact** (byte-for-byte mirror) |
| `app/modules/memberships/service.py:activate_membership_from_webhook` (body fill) | activator (transactional INSERT + audit) | DB-transactional | `app/modules/memberships/service.py:create_membership` (lines 688-788) | **exact** (date computation + insert_membership + flush + audit.emit pattern; the activator skips PaymentRecorder call since the webhook handler already invoked it) |
| `app/modules/pt_packages/service.py:activate_pt_package_from_webhook` (body fill) | activator | DB-transactional | `app/modules/pt_packages/service.py:create_pt_package` (around line 648) | **exact** (mirror of memberships version) |
| `app/core/audit.py:LOCKED_AUDIT_EVENTS` (mod, ADD 2 tuples) | audit registry | n/a | existing v1.7 entries at lines 326-337 | **exact** (append-to-set) |
| `app/core/audit_payloads.py` (mod, ADD 2 payload classes + 2 registry entries) | audit-payload schema | n/a | `OnlinePaymentSucceededPayload` (line 780) + `OnlinePaymentCanceledPayload` (line 799) | **exact** |
| `tests/unit/test_locked_yookassa_constants_ast.py` (mod, ADD WH-02 ordering test) | AST gate | n/a | existing `test_payment_subject_literal_at_callsites` (line 274) + `test_real_callsites_pass` (line 217) — same file | **exact** |
| `tests/integration/webhook_yookassa/conftest.py` (new) | test fixtures | n/a | `tests/integration/online_payments/conftest.py` | **exact** (cookie-jar overrides + respx re-export + structlog reset) |
| `tests/integration/webhook_yookassa/test_webhook_*.py` (new — ~9 files per D-50-43) | E2E integration tests | n/a | `tests/integration/online_payments/test_e2e_sell_flow.py` + Phase 48 `tests/integrations/yookassa/test_client.py` | role-match |
| `tests/integration/test_route_introspection.py` (mod, ADD `/webhook` to EXCLUDED_PATHS) | introspection-gate test | n/a | existing `EXCLUDED_PATHS` at lines 27-47 | **exact** (precedent: `/api/v1/online-payments/return` line 40, Phase 49) |
| `tests/integration/test_alembic_0035_fiscal_receipts.py` (new) | schema-assert test | n/a | `tests/integration/test_alembic_0034_online_payments.py` (assumed extant from Phase 49) | role-match |

---

## Pattern Assignments

### `app/api/v1/_internal/yookassa/router.py` (transport-router, request-response)

**Analog:** `app/api/v1/_internal/email/router.py` (entire file, 207 lines).

**Imports pattern** (email/router.py:37-52):
```python
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.config import get_settings
from app.core.database import get_db
from app.integrations.email.models import EmailSendLog

_log = structlog.get_logger("api.v1._internal.email")

router = APIRouter()
```

**Phase 50 adaptation:** replace `_log = structlog.get_logger("api.v1._internal.email")` with `_log = structlog.get_logger("api.v1._internal.yookassa")` (D-50 Claude's Discretion line ~254). Import additions:
```python
from redis.asyncio import Redis
from app.core.redis import get_redis
from app.core.dependencies import get_yookassa_client_provider
from app.integrations.yookassa.client import YooKassaClient
from app.integrations.yookassa.webhook_verifier import verify_yookassa_ip
from app.api.v1._internal.yookassa.handlers import (
    handle_payment_succeeded,
    handle_payment_canceled,
)
```

**Route-decorator with dependencies=[...] pattern** (email/router.py:63-71):
```python
@router.post(
    "/webhook",
    status_code=202,
    response_class=Response,
)
async def email_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
```

**Phase 50 adaptation** (D-50-04 — `dependencies=[Depends(verify_yookassa_ip)]` on the decorator, NOT in signature; D-50-08 — 200 not 202; D-50 Claude's Discretion — `text/plain` body):
```python
@router.post(
    "/webhook",
    include_in_schema=False,
    dependencies=[Depends(verify_yookassa_ip)],
)
async def yookassa_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    yookassa_client_provider: Annotated[Any, Depends(get_yookassa_client_provider)],
) -> Response:
    yookassa_client: YooKassaClient = await yookassa_client_provider()
    ...
    return Response(status_code=200, content="ok", media_type="text/plain")
```

**Note on `get_yookassa_client_provider`:** the accessor (core/dependencies.py:974) returns the registered `YooKassaClientProvider` Protocol callable; the actual client is obtained by `await provider()` (see Protocol signature at line 955 — `async def __call__(self) -> Any`). The provider's call site in Phase 49 is `app/modules/online_payments/service.py:174` — extract that pattern when wiring.

**Redis dedup short-circuit** (Phase 50 D-50-08; no in-repo analog, the discretion sketch in CONTEXT.md is canonical). Constants live at the top of `router.py`:
```python
WEBHOOK_DEDUP_KEY_PREFIX: Final[str] = "sz:yookassa:webhook:"
WEBHOOK_DEDUP_TTL_SECONDS: Final[int] = 86400
```

**Anonymous-by-design / no audit emit on hostile rejection** (email/router.py:93-102, lines 78-79 docstring): mirror the discipline — 401/403 paths do NOT emit an audit DB row to avoid amplifying scanner noise. Phase 50 only emits the audit row when control reaches the route body (i.e., IP allow-listed). Captured in D-50-06.

---

### `app/api/v1/_internal/yookassa/handlers.py` (event-dispatcher / FSM-driver, event-driven UoW)

**No single exact analog** — combine three:

**Analog 1 — FSM guard + state mutation + audit (in same UoW):**
`app/modules/memberships/service.py:cancel_membership` (lines 791-874).

**`_assert_can_transition` template** (memberships/service.py:208-224):
```python
def _assert_can_transition(membership: Membership, *, target: str) -> None:
    """Central state-machine guard (INFRA-16, D-24-04)."""
    allowed = MEMBERSHIP_STATUS_TRANSITIONS.get(membership.status, frozenset())
    if target not in allowed:
        raise InvalidTransitionError(
            "invalid_transition",
            fields={"from_status": membership.status, "to_status": target},
        )
```

**Phase 50 adaptation** (D-50-16): mirror byte-for-byte against `OnlinePayment` + `ONLINE_PAYMENT_STATUS_TRANSITIONS`. **IMPORTANT — see Blockers §1**: re-use existing `InvalidTransitionError` (exceptions.py:212) rather than declaring new `IllegalTransitionError`. The CONTEXT.md D-50-16 sketch shows a new class; the repo already ships a compatible class with `code="invalid_transition"` and `fields={"from_status", "to_status"}` shape. Cite both options in the plan; recommend reusing the existing class.

**Analog 2 — SELECT-FOR-UPDATE row lock:**
`app/modules/schedule/repository.py:71-81` (`get_slot_by_id_for_update`):
```python
async def get_slot_by_id_for_update(
    session: AsyncSession, slot_id: UUID
) -> TrainerAvailabilitySlot | None:
    """Row-locked slot read for FSM-guarded transitions (Phase 38 cancel_slot)."""
    stmt: Select[tuple[TrainerAvailabilitySlot]] = (
        select(TrainerAvailabilitySlot)
        .where(TrainerAvailabilitySlot.id == slot_id)
        .with_for_update()
    )
    result: TrainerAvailabilitySlot | None = await session.scalar(stmt)
    return result
```

**Phase 50 adaptation** (D-50-18 step 1):
```python
async def _select_for_update_online_payment(
    session: AsyncSession, *, yookassa_payment_id: str
) -> OnlinePayment | None:
    stmt = (
        select(OnlinePayment)
        .where(OnlinePayment.yookassa_payment_id == yookassa_payment_id)
        .with_for_update()
    )
    return await session.scalar(stmt)
```

**Analog 3 — orchestrator UoW shape (caller-owns-txn + audit emit + commit):**
`app/modules/memberships/service.py:create_membership` (lines 688-788) — the cleanest 5-step UoW analog (resolve → server-compute → INSERT → flush → record_payment → audit emit → commit). Phase 50 handlers borrow:

- **`async with session.begin()` outer block** — Phase 50 uses this explicitly because the handler is the txn owner (router does not commit on webhook). `create_membership` uses bare `await session.commit()` at line 766; Phase 50's pattern is closer to a managed transaction.
- **`get_payment_recorder()` invocation pattern** (memberships/service.py:739-747):
```python
payment = await get_payment_recorder()(
    session,
    subject_kind=PAYMENT_SUBJECT_KIND_MEMBERSHIP,
    subject_id=membership.id,
    amount_kopecks=membership.price_kopecks_snapshot,
    method="cash",
    received_by_user_id=actor.id,
    audit_actor=actor,
)
```
**Phase 50 adaptation** — see Blockers §2 for the `received_by_user_id`/`audit_actor` problem (no user in a webhook context).

- **Audit emit + commit pattern** (memberships/service.py:753-766):
```python
await audit.emit(
    session,
    "membership_created",  # LITERAL
    actor_user_id=actor.id,
    resource_type="membership",  # LITERAL
    resource_id=membership.id,
    client_id=str(membership.client_id),
    plan_id=str(membership.plan_id),
    end_date=membership.end_date.isoformat(),
    payment_id=str(payment.id),
)
await session.commit()
```

**Phase 50 emit ordering** (D-50-18 steps 7-8): emit `online_payment_succeeded` (CHILD) THEN `yookassa_webhook_received` (ROOT) — REVERSE of Phase 49. This is deliberate (CONTEXT.md "webhook intake is emitted LAST so its UUID is the chain root"). Excerpt from `OnlinePaymentSucceededPayload` (audit_payloads.py:780-796) shows the field shape — `audit_correlation_id: UUID | None`, `payment_id: UUID` (the ledger row, not yookassa_payment_id).

---

### `app/modules/memberships/service.py:activate_membership_from_webhook` (body fill)

**Current stub** (memberships/service.py:1814-1830):
```python
async def activate_membership_from_webhook(
    session: AsyncSession,
    *,
    membership_id: UUID,
    audit_correlation_id: UUID | None,
) -> Any:
    raise NotImplementedError(...)
```

**Critical: see Blockers §3** — the Protocol signature takes `membership_id: UUID` but Phase 49 sell flow never creates a Membership row. The activator must either INSERT a fresh Membership (in which case `membership_id` is misnamed — should be plan-id or online-payment-id) OR the Phase 49 sell flow must be retroactively changed to pre-INSERT a `'pending'`-status Membership (impossible — Membership.status CHECK is `('active','expired','cancelled','frozen')`, no 'pending').

**Recommended resolution path (planner decides):** the `membership_id` kwarg is the **OnlinePayment.id** (the inbound webhook handler already knows it and the audit chain wants it). The activator body INSERTs a fresh Membership with `status='active'`. Composition-root signature in `app/main.py:324` does not constrain the kwarg name — Protocol structural typing means kwargs match by name. **Action: rename the Protocol kwarg to `online_payment_id` to remove ambiguity**, OR document that `membership_id` here means the OnlinePayment row id and is the seed for the new Membership.

**Closest body analog** — `create_membership` (lines 712-766):
```python
# Date computation pattern (D-50-22 step 3)
start_date = datetime.now(ZoneInfo("Europe/Moscow")).date()
end_date = start_date + timedelta(days=plan.duration_days - 1)

# Insert pattern (line 724)
membership = await repository.insert_membership(
    session,
    data,  # MembershipCreateRequest
    plan=plan,
    start_date=start_date,
    end_date=end_date,
)
await session.flush()
```

**`insert_membership` repository signature** (memberships/repository.py:228-256):
```python
async def insert_membership(
    session: AsyncSession,
    data: MembershipCreateRequest,
    *,
    plan: MembershipPlan,
    start_date: date,
    end_date: date,
) -> Membership:
    membership = Membership(
        client_id=data.client_id,
        plan_id=plan.id,
        plan_name_snapshot=plan.name,
        duration_days_snapshot=plan.duration_days,
        price_kopecks_snapshot=plan.price_kopecks,
        freeze_days_limit_snapshot=plan.freeze_days_limit,
        start_date=start_date,
        end_date=end_date,
        status="active",
        paid_at=data.paid_at,
        notes=data.notes,
    )
    session.add(membership)
    return membership
```

**Phase 50 adaptation:** the activator constructs `MembershipCreateRequest` internally (using OnlinePayment.client_id + membership_plan_id + paid_at=succeeded_at), then calls `repository.insert_membership`. The new audit emit follows the existing `membership_created` pattern but uses the new locked event `membership_activated_online` (D-50-23):
```python
await audit.emit(
    session,
    "membership_activated_online",  # NEW LOCKED literal (D-50-23)
    actor_user_id=None,  # system emit — webhook has no user (audit.py:414 INFRA-39 system-emits guidance)
    resource_type="membership",
    resource_id=membership.id,
    audit_correlation_id=str(audit_correlation_id) if audit_correlation_id else None,
    client_id=str(membership.client_id),
    online_payment_id=str(online_payment_id),  # the seed
)
```

---

### `app/modules/pt_packages/service.py:activate_pt_package_from_webhook` (body fill)

**Current stub** (pt_packages/service.py:1195-1211) — mirror of memberships stub.

**Analog:** `app/modules/pt_packages/service.py:create_pt_package` (line 648; not fully read in this pass — extract during planning). Same shape as `create_membership`: resolve plan → snapshot fields → INSERT PtPackage with `status='active'` → flush → emit audit.

**PtPackage status CHECK** (`pt_packages/models.py:153`): `status IN ('active', 'exhausted', 'expired', 'cancelled')` — same constraint as Membership; activator INSERTs as `'active'`.

**New audit event** (D-50-23): `("pt_package_activated_online", "pt_package")`.

---

### `app/modules/online_payments/constants.py` (mod, ADD)

**Analog:** `app/modules/memberships/constants.py:22-29` (byte-for-byte mirror per D-50-15):
```python
MEMBERSHIP_STATUS_TRANSITIONS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "active": frozenset({"expired", "cancelled", "frozen"}),
        "expired": frozenset(),  # terminal
        "cancelled": frozenset(),  # terminal
        "frozen": frozenset({"active", "cancelled"}),
    }
)
```

**Phase 50 form** (CONTEXT.md D-50-15) — appended to the EXISTING `online_payments/constants.py` (file already exists; do NOT recreate):
```python
from collections.abc import Mapping
from types import MappingProxyType

ONLINE_PAYMENT_STATUS_TRANSITIONS: Mapping[str, frozenset[str]] = MappingProxyType({
    "pending":   frozenset({"succeeded", "canceled"}),
    "succeeded": frozenset(),  # terminal
    "canceled":  frozenset(),  # terminal
})
```

Add `"ONLINE_PAYMENT_STATUS_TRANSITIONS"` to the existing `__all__` tuple at lines 43-55.

---

### `alembic/versions/0035_fiscal_receipts.py` (new)

**Analog:** `alembic/versions/0034_online_payments.py` (entire file, 167 lines).

**Header pattern** (0034:1-44):
```python
"""<docstring summarising shape + IMMUTABLE / naming conventions>

Revision ID: 0034_online_payments
Revises: 0033_clients_email_partial_unique
Create Date: 2026-05-22 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0034_online_payments"
down_revision: str | None = "0033_clients_email_partial_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**Phase 50:** `revision: str = "0035_fiscal_receipts"`, `down_revision: str | None = "0034_online_payments"` (D-50-31).

**`op.create_table` pattern with `op.f()` constraint names** (0034:47-136) is the byte-for-byte template; CONTEXT.md "specifics" section already has the exact Phase 50 sketch at lines 526-549. Key conventions cited from 0034:
- UUID PK with `server_default=sa.text("gen_random_uuid()")` (line 55).
- FK uses `name=op.f("fk_<table>_<col>_<reftable>")` (lines 63, 73, 83).
- CHECK uses `name=op.f("ck_<table>_<descriptor>")` (lines 114, 118).
- UNIQUE uses `name=op.f("uq_<table>_<col>")` (lines 130, 134).
- `created_at`/`updated_at` not in 0034 — Phase 50's `FiscalReceipt` per D-50-29 also omits them (mirror).

**Downgrade** (0034:159-166): `drop_index` then `drop_table`. Phase 50: `drop_constraint` then `drop_table` (the UNIQUE is a constraint not a separate index).

---

### `app/modules/fiscal_receipts/models.py` (new)

**Analog:** `app/modules/online_payments/models.py` (159 lines, entire file).

**Class composition pattern** (online_payments/models.py:47):
```python
class OnlinePayment(Base, UUIDPkMixin):
    """ЮKassa-side online payment ledger row (Phase 49 PAY-01 / D-49-04)."""

    __tablename__ = "online_payments"
```

**`Base + UUIDPkMixin` only — NO TimestampMixin, NO SoftDeleteMixin** (lines 1-7 docstring) — single-temporal-column discipline. Phase 50 `FiscalReceipt` mirrors: lifecycle tracked by `sent_at` / `succeeded_at` / `failed_at` explicit columns.

**NAMING_CONVENTION expansion gotcha** (online_payments/models.py:9-15 docstring + lines 113, 118, 123, 128):
```python
CheckConstraint(
    "amount_kopecks > 0",
    # NAMING_CONVENTION expands to ck_online_payments_amount_kopecks_positive
    name="amount_kopecks_positive",  # BARE suffix — NOT "ck_online_payments_..."
),
```
**Critical for Phase 50:** the `op.f("ck_fiscal_receipts_kind")` in the Alembic 0035 sketch expects the ORM CHECK to use BARE suffix (`name="kind"`), NOT full name. Otherwise double-prefix bug recurs (online_payments/models.py:11-15 documents this).

**Column declaration pattern with Mapped/mapped_column** (online_payments/models.py:79-107) — straight mirror.

**No relationship to `Client`** (line 52-60) — see Blockers §4. Phase 50 `FiscalReceipt.payment_id` FK does NOT need a relationship either (the handler does a separate `Client.email` SELECT; see D-50-18 step 5 + Blockers §4 resolution).

---

### `app/modules/fiscal_receipts/repository.py` (new)

**Analog:** `app/modules/online_payments/repository.py` (74 lines, entire file).

**Pattern (caller-owns-txn — NO flush, NO commit):**
```python
"""Online payments repository — caller-owns-txn INSERT + GET (Phase 49 D-49-07)."""

from __future__ import annotations
from uuid import UUID
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.online_payments.models import OnlinePayment

async def insert_online_payment(
    session: AsyncSession,
    *,
    client_id: UUID,
    ...
) -> OnlinePayment:
    row = OnlinePayment(...)
    session.add(row)
    return row

async def get_online_payment_by_id(
    session: AsyncSession, online_payment_id: UUID
) -> OnlinePayment | None:
    stmt: Select[tuple[OnlinePayment]] = select(OnlinePayment).where(
        OnlinePayment.id == online_payment_id
    )
    return await session.scalar(stmt)
```

**Phase 50 form** — Per D-50-28 ships 3 functions:
- `insert_fiscal_receipt(session, *, payment_id, kind, status, customer_email, ...) -> FiscalReceipt`
- `get_fiscal_receipt_by_id(session, fiscal_receipt_id) -> FiscalReceipt | None`
- `get_fiscal_receipt_by_payment_id_and_kind(session, *, payment_id, kind) -> FiscalReceipt | None`

---

### `tests/unit/test_locked_yookassa_constants_ast.py` (mod, ADD)

**Analog:** SAME FILE — lines 274-348 already contain `test_payment_subject_literal_at_callsites` + `test_payment_mode_literal_at_callsites` + 2 fixture-rejection tests. **The FISCAL-03 gates already exist (Phase 48 D-48-18 shipped them).** CONTEXT.md D-50-33 reading "add 2 new test functions for payment_subject/payment_mode" is inaccurate — those are already shipped. Phase 50 only needs to add the WH-02 ordering gate.

**WH-02 ordering AST gate** (D-50-14) — closest analog in same file is `test_payment_subject_literal_at_callsites` (lines 274-293):
```python
def test_payment_subject_literal_at_callsites() -> None:
    violations: list[str] = []
    for py in sorted(_BACKEND_APP.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _is_build_receipt_item_call(node):
                arg = _extract_kwarg(node, "payment_subject")
                if arg is None:
                    continue
                if not _is_enum_member_literal(arg, "PaymentSubject"):
                    violations.append(
                        f"{py.relative_to(_REPO_ROOT)}:{node.lineno} — "
                        "payment_subject must be a PaymentSubject.<MEMBER> literal."
                    )
    assert not violations, "\n".join(violations)
```

**Phase 50 adaptation** — D-50-14 sketch (already cited verbatim in CONTEXT.md specifics line 552-569) — find `handle_payment_succeeded` AST, walk in order, assert first `await yookassa_client.get_payment(...)` lineno < first `await session.execute|add|flush|commit` lineno. Scoped to ONE file (`handlers.py`), not the full tree. Note: use `ast.walk` carefully — for ordering checks `ast.walk` returns in BFS order, not source order; iterate `ast.iter_child_nodes` recursively OR use `node.lineno` comparisons.

---

### `tests/integration/webhook_yookassa/conftest.py` (new)

**Analog:** `tests/integration/online_payments/conftest.py` (442 lines, entire file).

**Re-export pattern from upstream conftest** (online_payments/conftest.py:49-55):
```python
from tests.integrations.yookassa.conftest import (  # noqa: F401
    _YOOKASSA_BASE_URL,
    yookassa_create_payment_422,
    yookassa_create_payment_qr_422,
    yookassa_create_payment_qr_success,
    yookassa_create_payment_success,
)
```

**Phase 50 re-exports:** `yookassa_get_payment_pending` (line 162), `yookassa_get_payment_succeeded` (line 173), `yookassa_webhook_payload` (line 193) — all already shipped per the Phase 48 conftest docstring (lines 12-16).

**Structlog autouse reset** (online_payments/conftest.py:70-80) — copy verbatim.

**App-override pattern** (online_payments/conftest.py:196-216) — copy verbatim. **Phase 50 NOTE:** webhook tests are **anonymous** (D-50-39 — no `_login` call, no cookie jar). Drop `authed_client_owner` / `authed_client_reception` fixtures; provide a plain `webhook_client` fixture that issues POSTs with `X-Real-IP` set to a value in `YOOKASSA_TRUSTED_IPS` (or relies on sandbox bypass per D-48-19 / D-50-42).

---

### `tests/integration/test_route_introspection.py` (mod, ADD)

**Analog:** SAME FILE — `EXCLUDED_PATHS` definition at lines 27-47.

**Precedent excerpt** (lines 36-40):
```python
# Phase 49 D-49-26 — PAY-07 anonymous-by-design return-URL screen.
# No auth, no CSRF; reveals no data (static HTML only). The handler
# MUST stay this way — adding any DB lookup or query-param branching
# re-introduces the oracle that Plan 49-05 was designed to eliminate.
"/api/v1/online-payments/return",
```

**Phase 50 adaptation** (D-50-40):
```python
# Phase 50 D-50-39 — WH-01 anonymous-by-design ЮKassa webhook intake.
# IP allowlist (verify_yookassa_ip Depends) is the only auth — not a
# require_permission gate, so the introspection test cannot see it.
# Mounted as the second /_internal/* inhabitant; the EXCLUDED_PREFIXES
# tuple at line 60 already covers /api/v1/_internal/, but explicit
# enumeration here provides the audit-trail diff (D-19).
"/api/v1/_internal/yookassa/webhook",
```

**IMPORTANT:** `EXCLUDED_PREFIXES = ("/api/v1/auth/telegram/", "/api/v1/_internal/")` at line 60-63 ALREADY covers the new webhook route (matches the `/api/v1/_internal/` prefix). **The explicit add to `EXCLUDED_PATHS` is REDUNDANT for the test pass but valuable as audit-trail diff** (per the file's own doc at line 26: "The exclusion list IS the audit trail"). Planner: either omit the explicit add (rely on the prefix) OR add the explicit entry for the diff value — D-50-40 prefers the explicit add.

---

## Shared Patterns

### Audit event addition (LOCKED_AUDIT_EVENTS + AUDIT_PAYLOAD_SCHEMAS)

**Source 1:** `app/core/audit.py:LOCKED_AUDIT_EVENTS` — existing v1.7 entries at lines 326-337:
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
```

**Phase 50 add (D-50-23):** append (preserving comment grouping):
```python
# Membership / PT-package activation via webhook (Phase 50 WH-05):
("membership_activated_online", "membership"),
("pt_package_activated_online", "pt_package"),
```

**Source 2:** `app/core/audit_payloads.py:AUDIT_PAYLOAD_SCHEMAS` — existing entries at lines 985-995. Phase 50 append two new mappings:
```python
("membership_activated_online", "membership"): MembershipActivatedOnlinePayload,
("pt_package_activated_online", "pt_package"): PtPackageActivatedOnlinePayload,
```

**Source 3:** docstring catalog at `app/core/audit.py:16-180` — append entries under v1.7 section so the doc and runtime frozenset stay in sync. Existing v1.7 catalog stub at lines TBD (read during planning).

**Apply to:** all 3 Plan-50 changes touching audit.

### Payload class pattern

**Source:** `app/core/audit_payloads.py:780-816` — `OnlinePaymentSucceededPayload` + `OnlinePaymentCanceledPayload`.
```python
class OnlinePaymentSucceededPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audit_correlation_id: UUID | None
    online_payment_id: UUID
    yookassa_payment_id: str
    amount_kopecks: int
    payment_id: UUID
```

**Phase 50 new payload classes** (D-50-23):
```python
class MembershipActivatedOnlinePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audit_correlation_id: UUID | None
    membership_id: UUID
    client_id: UUID
    online_payment_id: UUID


class PtPackageActivatedOnlinePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audit_correlation_id: UUID | None
    pt_package_id: UUID
    client_id: UUID
    online_payment_id: UUID
```

### Declarative FSM constants

**Source:** `app/modules/memberships/constants.py:22-29` (byte-for-byte mirror per D-50-15 + D-50-32).

**Apply to:** new `ONLINE_PAYMENT_STATUS_TRANSITIONS` (in existing `online_payments/constants.py`) + new `FISCAL_RECEIPT_STATUS_TRANSITIONS` (in new `fiscal_receipts/constants.py`).

### Caller-owns-txn marker

**Source:** `app/modules/payments/service.py:90` — `# noqa: SVC001 caller-owns-txn — sale orchestrator owns UoW` marker. Required for any new function that intentionally skips `session.commit()`.

**Apply to:** new `app/modules/fiscal_receipts/repository.py` functions (only `session.add(...)`, no flush/commit) and the activator body fills if they delegate flush/audit to the caller. The webhook handler itself OWNS the commit (via `async with session.begin()`).

### Structlog logger naming convention

**Source:** `app/api/v1/_internal/email/router.py:54`:
```python
_log = structlog.get_logger("api.v1._internal.email")
```

**Phase 50 form:** `_log = structlog.get_logger("api.v1._internal.yookassa")` (Claude's Discretion section).

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `app/api/v1/_internal/yookassa/handlers.py:_post_commit_enqueue` (no-op stub) | post-commit hook stub | event-driven | Phase 50 lays the seam; Phase 52 NOT-04/05 fills body. No in-repo precedent for an explicit-no-op-with-INFO-log stub. Closest is the FiscalReceiptDispatcher stub registered at `app/main.py:329` (`phase49_fiscal_dispatcher_stub`). Use that pattern: a named function whose body is `_log.info("webhook_post_commit_enqueue_skip", ...)` and `return None`. |

---

## Blockers (Plan Assumptions That Won't Survive Contact With Code)

### §1 — `IllegalTransitionError` vs existing `InvalidTransitionError`

**Issue:** CONTEXT.md D-50-16 and CONTEXT.md "specifics" line 571-577 sketch a NEW exception `IllegalTransitionError(AppError)` with `code="online_payment_illegal_transition"`.

**Codebase fact:** `app/core/exceptions.py:212` already declares `InvalidTransitionError(ConflictError)` with `code="invalid_transition"`, `status_code=409`, and a `fields={"from_status", "to_status"}` constructor shape. Used by Memberships module (`memberships/service.py:208-224`) via `_assert_can_transition`.

**Recommendation:** REUSE `InvalidTransitionError`. The webhook handler does not bubble the exception to an HTTP response anyway (D-50-17: illegal transitions return 200, the exception is caught locally and audit-logged). Adding a new exception class is unnecessary surface. If the planner prefers a discriminated subclass, derive `class OnlinePaymentIllegalTransitionError(InvalidTransitionError): code = "online_payment_illegal_transition"` so the existing 409 handler still works and the discriminator is preserved.

### §2 — `PaymentRecorder` requires `received_by_user_id` and `audit_actor` — webhook has neither

**Issue:** CONTEXT.md D-50-18 step 4 sketches:
```python
ledger_row_id = await payment_recorder(
    session, client_id=row.client_id, amount_kopecks=row.amount_kopecks,
    method="online", audit_correlation_id=webhook_intake_corr,
)
```

**Codebase fact:** `PaymentRecorder.__call__` signature at `app/core/dependencies.py:349-359`:
```python
async def __call__(
    self,
    session: AsyncSession,
    *,
    subject_kind: str,
    subject_id: UUID,
    amount_kopecks: int,
    method: str = "cash",
    received_by_user_id: UUID,    # REQUIRED kwarg
    audit_actor: CurrentUser,     # REQUIRED kwarg
) -> Any:                          # Returns Payment ORM row (not UUID)
```

The actual signature requires `subject_kind` + `subject_id` (NOT `client_id`), `received_by_user_id` (a UUID), and `audit_actor` (a `CurrentUser` Protocol). The sketch in CONTEXT.md does not match the Protocol.

**Cascade impact:**
- `payment_recorded` audit row emitted inside `record_payment` (payments/service.py:126-139) sets `actor_user_id=audit_actor.id` (line 129). Webhook has no user.
- `received_by_user_id` is required and non-null. In Phase 49 sell flow it's `actor.id` (the operator who clicked "sell").

**Recommendation paths (planner picks):**
1. **(a) Synthesize a system actor.** Define a `SYSTEM_USER_ID` constant or a Phase-43 system user row; pass that as `received_by_user_id`. Construct a fake `CurrentUser` for `audit_actor`. Mirror: `audit.emit` already supports `actor_user_id=None` system emits (audit.py:414 INFRA-39).
2. **(b) Widen the `PaymentRecorder` Protocol.** Make `received_by_user_id: UUID | None` and `audit_actor: CurrentUser | None`. Update `record_payment` to write `received_by_user_id=NULL` for online-payment rows and skip the audit emit if `audit_actor is None` (or emit with `actor_user_id=None`). Requires checking `payments` table CHECK on `received_by_user_id` — if NOT NULL, a migration is also needed.
3. **(c) Bypass `PaymentRecorder` for online payments.** The webhook handler inserts the `Payment` row directly via a new `payments/repository.insert_online_payment_row` helper. Loses the Protocol-slot uniformity but avoids retrofitting.

This is a planner decision; the plan must include the chosen path explicitly.

### §3 — Activator Protocol kwarg `membership_id` semantics

**Issue:** Activator Protocol at `app/core/dependencies.py:1089-1095`:
```python
async def __call__(
    self,
    session: AsyncSession,
    *,
    membership_id: UUID,
    audit_correlation_id: UUID | None,
) -> Any:
```

**Codebase fact:** Phase 49 sell flow at `app/modules/online_payments/service.py:174` (`_sell_subject`) INSERTs ONLY an OnlinePayment row. No Membership row exists at webhook-arrival time. There is no `pending`-state Membership row to "activate" — the activator must CREATE the Membership row.

CONTEXT.md D-50-22 ("if a row already exists in pending state, transition to active") is wrong: Membership.status CHECK at `memberships/models.py:171` is `IN ('active', 'expired', 'cancelled', 'frozen')` — no `'pending'` state.

**Recommendation:** plan must explicitly state which UUID `membership_id` carries. Two sane interpretations:
- **(a) It's the OnlinePayment.id** (seed for the new Membership). The Protocol kwarg name is misleading but functionally correct. The activator body INSERTs a Membership.
- **(b) Rename the Protocol kwarg to `online_payment_id`.** Cleaner. Requires touching `app/core/dependencies.py` (1 line in Protocol + 1 line in PtPackageActivator) and the Phase 49 stub bodies (currently raise NotImplementedError — no callsites to update). Composition root at `app/main.py:324-325` is unaffected (passes a function reference, not kwarg names).

Recommend (b). Plan should include the rename as a Wave 1 (or Wave 2) edit.

### §4 — `OnlinePayment.client` relationship does not exist

**Issue:** CONTEXT.md D-50-18 step 5 sketch:
```python
session.add(FiscalReceipt(
    ...
    customer_email=row.client.email,  # Or fetch via separate SELECT
    ...
))
```

**Codebase fact:** `app/modules/online_payments/models.py:47-159` declares the ORM WITHOUT any `relationship(...)` to `Client`. There is no `OnlinePayment.client` attribute. SQLAlchemy will `AttributeError` on `row.client.email`.

**Recommendation:** the handler MUST do a separate read. The pattern is established at `app/modules/online_payments/service.py:102-113`:
```python
async def _read_client_email_or_raise(
    session: AsyncSession, client_id: UUID
) -> str:
    email: str | None = await session.scalar(
        select(Client.email).where(Client.id == client_id)
    )
    if email is None:
        raise ClientEmailRequiredForOnlinePaymentError(...)
    return email
```

Copy this pattern into the webhook handler. **Plan must NOT add `relationship(Client)` to `OnlinePayment`** — would require ORM model touch and an import-linter check on `online_payments → clients` (which is already in the `modules-independent` exclusion list per Phase 49 docs; verify). The narrow-scalar SELECT is the established convention.

### §5 — FISCAL-03 AST gates are ALREADY shipped (Phase 48)

**Issue:** CONTEXT.md D-50-33 reads "Extend `test_locked_yookassa_constants_ast.py` with `test_payment_subject_callsites_use_locked_literal` + `test_payment_mode_callsites_use_locked_literal`".

**Codebase fact:** `tests/unit/test_locked_yookassa_constants_ast.py:274-348` already ships:
- `test_payment_subject_literal_at_callsites` (line 274)
- `test_payment_mode_literal_at_callsites` (line 296)
- `test_non_literal_payment_subject_fixture_is_rejected` (line 317)
- `test_non_literal_payment_mode_fixture_is_rejected` (line 334)

Walker helpers `_is_build_receipt_item_call` (line 71), `_extract_kwarg` (line 76), `_is_enum_member_literal` (line 84) are present.

**Recommendation:** Phase 50's "FISCAL-03 ratification" is a no-op in terms of NEW tests — they already exist and already pass (Phase 49's `service.sell_*` uses enum literals). Phase 50 must ONLY add:
- **WH-02 ordering gate** (D-50-14) — genuinely new — `test_payment_succeeded_handler_calls_get_payment_before_any_db_write` scoped to `handlers.py`.

Update plan scope accordingly. The D-50-14 test is the only AST gate that Phase 50 must add.

### §6 — Activator does not emit `payment_recorded` — that lives inside `record_payment`

**Issue:** D-50-18 step 7 ("Emit `online_payment_succeeded` audit") is fine, but the broader UoW must be aware that `payment_recorder` ALREADY emits `payment_recorded` internally (payments/service.py:126-139). The webhook handler will end up with 4 audit emits per success path: `payment_recorded` (inside recorder) + `membership_activated_online` (inside activator) + `online_payment_succeeded` (handler) + `yookassa_webhook_received` (handler). Plus the activator might emit `membership_created` if it reuses `create_membership`-style code — that would be 5 emits.

**Recommendation:** the activator body fill MUST NOT emit `membership_created`. Use ONLY the new `membership_activated_online` event. Document the audit-chain inventory explicitly in the plan (4 emits per success: 1 from recorder, 1 from activator, 2 from handler). Test `test_wh05_succeeded_atomic_uow_writes_4_rows_in_one_commit` (D-50-43) must be updated to "4 audit rows in one commit boundary".

### §7 — Composition-root no-edit assertion is correct (D-50-36)

**Codebase fact:** `app/main.py:319-329` already calls `register_membership_activator(activate_membership_from_webhook)` + `register_pt_package_activator(activate_pt_package_from_webhook)`. The Phase 49 stub bodies raise `NotImplementedError`; Phase 50 fills bodies, no composition-root edits needed.

**Confirmation:** D-50-36 is accurate. No blocker — just a positive verification.

### §8 — `test_alembic_check_clean` pre-existing failure (D-49-defer)

**Issue:** per CONTEXT.md "deferred" section: `tests/integration/test_alembic_clean.py::test_alembic_check_clean` is failing on master pre-Phase 50.

**Impact on Phase 50:** Phase 50 lands a new migration. The pre-existing failure may mask Phase 50 alembic-introspection issues. Plan should call out a manual `alembic check` step at verification time + document that the test failure is inherited (do not chase as a Phase 50 regression).

---

## Metadata

**Analog search scope:**
- `apps/backend/app/api/v1/_internal/email/` (full directory)
- `apps/backend/app/integrations/yookassa/` (full directory)
- `apps/backend/app/core/` (audit.py, audit_payloads.py, dependencies.py, redis.py, exceptions.py)
- `apps/backend/app/modules/online_payments/` (full module — Phase 49)
- `apps/backend/app/modules/memberships/` (constants.py, models.py, service.py, repository.py)
- `apps/backend/app/modules/pt_packages/` (service.py, models.py)
- `apps/backend/app/modules/payments/` (service.py)
- `apps/backend/app/modules/schedule/repository.py` (with_for_update precedent)
- `apps/backend/alembic/versions/0034_online_payments.py`
- `apps/backend/tests/unit/test_locked_yookassa_constants_ast.py`
- `apps/backend/tests/integration/test_route_introspection.py`
- `apps/backend/tests/integrations/yookassa/conftest.py`
- `apps/backend/tests/integration/online_payments/conftest.py`
- `apps/backend/app/main.py` (composition root verification)

**Files scanned:** 19 source/test files (full read on 13; targeted Grep + offset Read on 6).

**Pattern extraction date:** 2026-05-22.
