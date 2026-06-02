# Phase 71: Client Checkout + Full PWA Screen Wiring - Pattern Map

**Mapped:** 2026-05-30
**Files analyzed:** 16 new/modified files
**Analogs found:** 16 / 16

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/backend/app/modules/online_payments/service.py` | service | request-response (extract helper) | itself — existing `_sell_subject` body | exact (refactor) |
| `apps/backend/app/modules/client_portal/router.py` | controller | request-response (POST + GET) | `apps/backend/app/modules/client_portal/router.py` (existing) | exact |
| `apps/backend/app/modules/client_portal/service.py` | service | request-response + Protocol-slot write | `apps/backend/app/modules/client_portal/service.py` (existing) | exact |
| `apps/backend/app/modules/client_portal/repository.py` | repository | CRUD (raw-SQL read for status) | `apps/backend/app/modules/client_portal/repository.py` (existing) | exact |
| `apps/backend/app/modules/client_portal/schemas.py` | model | request-response | `apps/backend/app/modules/client_portal/schemas.py` (existing) | exact |
| `apps/backend/app/core/audit.py` | utility | event-driven | itself — `LOCKED_AUDIT_EVENTS` frozenset + `emit()` | exact (extend) |
| `apps/backend/app/core/dependencies.py` | utility | Protocol-slot | itself — `register_client_loader` / `ClientPrincipal` block | exact (extend) |
| `apps/backend/app/main.py` | config | composition-root wiring | itself — existing `register_*` call block | exact (extend) |
| `apps/backend/tests/integration/client_portal/test_checkout.py` (new) | test | request-response | `apps/backend/tests/integration/client_portal/test_idor_sweep.py` + `tests/integration/online_payments/test_idempotency_hardening.py` | role-match |
| `apps/client-pwa/package.json` | config | — | `apps/admin-web/package.json` (React Query dependency) | role-match |
| `apps/client-pwa/src/data/index.js` | utility | CRUD (swap seam) | itself — current mock re-export file | exact (swap) |
| `apps/client-pwa/src/lib/queryClient.ts` (new) | config | — | `apps/admin-web/src/app/queryClient.ts` | exact |
| `apps/client-pwa/src/lib/clientQueries.ts` (new) | hook | request-response | `apps/admin-web/src/features/clients/api/hooks.ts` + `keys.ts` | exact |
| `apps/client-pwa/src/screens/HomeScreen.jsx` | component | request-response | itself + `apps/admin-web/src/features/memberships/api/hooks.ts` | role-match |
| `apps/client-pwa/src/screens/sheets/PlansSheet.jsx` | component | CRUD | itself + new `clientQueries.ts` | role-match |
| `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx` | component | request-response (mutation) | itself + `apps/admin-web/src/features/memberships/api/hooks.ts` (mutation pattern) | role-match |
| `apps/client-pwa/src/screens/sheets/QRSheet.jsx` | component | request-response | itself + `clientQueries.ts` (polling) | role-match |
| `apps/client-pwa/src/screens/ProfileScreen.jsx` | component | request-response | itself + `clientQueries.ts` | role-match |
| `apps/client-pwa/src/screens/BookScreen.jsx` | component | request-response | itself + `clientQueries.ts` | role-match |
| `apps/client-pwa/src/components/ComingSoon.tsx` (new) | component | — | `apps/admin-web/src/shared/ui/` component pattern | role-match |
| `apps/client-pwa/eslint.config.js` | config | — | itself — existing config with no-restricted-paths stub | exact (extend) |

---

## Pattern Assignments

### `apps/backend/app/modules/online_payments/service.py` (service, extract actor-agnostic helper)

**Analog:** itself — `_sell_subject` (L170-330) is the body to extract.

**Key refactor:** pull `_sell_subject` out into a standalone helper that accepts an `actor_user_id: UUID | None` instead of `actor: CurrentUser`. The staff callers (`sell_membership`, `sell_pt_package`) pass `actor_user_id=actor.id`. The new `client_portal` write-slot passes `actor_user_id=None` (client-initiated, D-71-02).

**Imports pattern** (lines 40-84):
```python
from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING, Literal
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.audit_payloads import (
    OnlinePaymentInitiatedPayload,
    YookassaPaymentCreatedPayload,
)
from app.core.exceptions import (
    BadGatewayAppError,
    ClientEmailRequiredForOnlinePaymentError,
    NotFoundError,
    ServiceUnavailableAppError,
    ValidationAppError,
)
from app.integrations.yookassa.receipt import (
    PaymentMode,
    PaymentSubject,
    VatCode,
    build_receipt_item,
)
from app.integrations.yookassa.settings import YooKassaSettings
from app.modules.clients.models import Client
from app.modules.online_payments import repository
from app.modules.online_payments.constants import (
    CONFIRMATION_TYPE_QR,
    STATUS_PENDING,
    ErrorCode,
)
from app.modules.online_payments.schemas import SellResponse
```

**Extracted core helper signature** (derived from lines 170-330):
```python
async def _sell_subject_core(
    session: AsyncSession,
    *,
    subject_kind: Literal["membership", "pt_package"],
    plan_id: UUID,
    client_id: UUID,
    confirmation_type: Literal["redirect", "qr"],
    idempotency_key: str,                # caller-derived (membership) or caller-supplied (PT)
    actor_user_id: UUID | None,          # None for client-initiated (D-71-02)
    yookassa_settings: YooKassaSettings,
) -> SellResponse:
    """Actor-agnostic sell flow. actor_user_id=None when client initiates.

    NO price/amount/description parameter exists (CPAY-03 price authority, D-71-01):
    the core reads price + description server-side from plan_id via
    `_read_membership_plan_or_raise` / `_read_pt_package_plan_or_raise`.
    Callers NEVER supply an amount.
    """
    ...
    # Step 2: server-side price + description read (CPAY-03 — inside the core, never from caller)
    plan = (
        await _read_membership_plan_or_raise(session, plan_id)
        if subject_kind == "membership"
        else await _read_pt_package_plan_or_raise(session, plan_id)
    )
    # Step 3: replay check (unchanged)
    existing = await repository.get_online_payment_by_idempotency_key(session, idempotency_key)
    ...
    # Step 7: INSERT row — created_by_user_id=actor_user_id (None for client-initiated, D-71-02)
    row = await repository.insert_online_payment(
        session,
        ...
        created_by_user_id=actor_user_id,   # nullable column — models.py:103
        audit_correlation_id=correlation_id,
    )
    # Audit ROOT — actor_user_id=None accepted by audit.emit() (D-41-10 system-emit rule)
    await audit.emit(
        session,
        "online_payment_initiated",
        actor_user_id=actor_user_id,   # None for client-initiated
        resource_type="online_payment",
        resource_id=row.id,
        **initiated_payload.model_dump(mode="json"),
    )
    # Audit CHILD — same actor_user_id
    await audit.emit(
        session,
        "yookassa_payment_created",
        actor_user_id=actor_user_id,
        resource_type="online_payment",
        resource_id=row.id,
        **created_payload.model_dump(mode="json"),
    )
```

**D-71-02 audit actor finding:** `audit.emit()` already accepts `actor_user_id: UUID | None` (line 495). `actor_user_id=None` is the documented "system emit" path (D-41-10). The `actor_email_snapshot` ContextVar population is conditional on `actor_user_id is not None` (audit.py line 583). No new field needed — pass `actor_user_id=None` and the audit chain records the client_id only in the payload.

**Idempotency key discipline** (D-71-04):
```python
# Memberships: deterministic server-derived key (unchanged)
idem_key = _derive_idempotency_key(subject_kind="membership", plan_id=plan_id, client_id=client_id)

# PT-packages: client-supplied key from Idempotency-Key header (PWA generates UUID per intent)
# The extracted core accepts idem_key as a parameter — membership caller derives it;
# PT-package caller passes the client-supplied header value.
```

---

### `apps/backend/app/modules/client_portal/router.py` (controller, new POST + GET endpoints)

**Analog:** `apps/backend/app/modules/client_portal/router.py` (existing GET endpoints, L38-234)

**Imports pattern** (lines 1-37, extend existing):
```python
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import ClientPrincipal, require_client, verify_client_csrf
from app.core.schemas import ResponseEnvelope, envelope
from app.integrations.yookassa.settings import YooKassaSettings, get_yookassa_settings
from app.modules.client_portal import service
from app.modules.client_portal.schemas import (
    ClientCheckoutRequest,
    ClientCheckoutResponse,
    ClientPaymentStatusResponse,
)
```

**POST checkout endpoint pattern** (modeled on staff router lines 103-154 + client GET pattern):
```python
@router.post(
    "/checkout/memberships/{plan_id}",
    response_model=ResponseEnvelope[ClientCheckoutResponse],
    status_code=status.HTTP_201_CREATED,
    operation_id="client_checkout_membership",
    summary="Client-initiated membership checkout via ЮKassa redirect (CPAY-01)",
)
async def client_checkout_membership(
    plan_id: UUID,
    payload: ClientCheckoutRequest,
    client: Annotated[ClientPrincipal, Depends(require_client())],
    _csrf: Annotated[None, Depends(verify_client_csrf)],   # CSRF on POST (D-68 RBAC-04 ordering)
    session: Annotated[AsyncSession, Depends(get_db)],
    yookassa_settings: Annotated[YooKassaSettings, Depends(get_yookassa_settings)],
) -> ResponseEnvelope[ClientCheckoutResponse]:
    """CPAY-01. No staff Idempotency-Key outer layer for membership — server-derived key (D-71-04)."""
    result = await service.client_checkout_membership(
        session, plan_id=plan_id, client=client, yookassa_settings=yookassa_settings
    )
    return envelope(result)
```

**GET status endpoint pattern** (IDOR discipline mirrors existing GET endpoints):
```python
@router.get(
    "/payments/{payment_id}/status",
    response_model=ResponseEnvelope[ClientPaymentStatusResponse],
    operation_id="client_get_payment_status",
    summary="Coarse payment status for the authenticated client (CPAY-03 anti-oracle)",
)
async def client_get_payment_status(
    payment_id: UUID,
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientPaymentStatusResponse]:
    """CPAY-03 — anti-oracle: returns only 'pending' | 'succeeded' | 'canceled'.
    D-20-IDOR: assert_owns() in repository collapses non-owned payment to 404.
    No try/except — AppError bubbles to _app_error_handler.
    No CSRF — GET is safe.
    """
    result = await service.get_client_payment_status(session, payment_id, client.id)
    return envelope(result)
```

**Auth + CSRF ordering rule** (from existing router docstring lines 6-9):
- GET endpoints: `Depends(require_client())` only. No CSRF dep on GET (safe methods).
- POST endpoints: `Depends(require_client())` first, then `Depends(verify_client_csrf)` after.
- Matches RBAC-04 ordering from staff router.

---

### `apps/backend/app/modules/client_portal/service.py` (service, Protocol-slot write)

**Analog:** `apps/backend/app/modules/client_portal/service.py` (existing, L1-214)

**Module docstring pattern** (existing file lines 1-10):
```python
"""Client-portal service — read-only orchestrator + checkout write-slot (Phase 69/71).

Thin service layer: wires repository functions + checkout Protocol slot to schemas.
No try/except — AppError subclasses bubble to the central _app_error_handler.
No session.commit() — caller-owns-txn (D-32-10 / D-49-19). The checkout write-slot
delegates into the extracted online_payments core via the composition-root Protocol
slot — no direct import of app.modules.online_payments (D-20-MODULE).
"""
```

**Protocol-slot write pattern** (from `app/core/dependencies.py` lines 58-68 + `app/main.py` wiring):
```python
# In app/core/dependencies.py (extend existing file):
CheckoutCoreCallable = Callable[..., Awaitable[SellResponse]]
_client_checkout_core: CheckoutCoreCallable | None = None

def register_client_checkout_core(fn: CheckoutCoreCallable) -> None:
    global _client_checkout_core
    _client_checkout_core = fn

async def invoke_client_checkout_core(...) -> SellResponse:
    if _client_checkout_core is None:
        raise RuntimeError("client_checkout_core slot not registered")
    return await _client_checkout_core(...)
```

```python
# In client_portal/service.py — new checkout write functions:
from app.core.dependencies import invoke_client_checkout_core

async def client_checkout_membership(
    session: AsyncSession,
    *,
    plan_id: UUID,
    client: ClientPrincipal,
    yookassa_settings: YooKassaSettings,
) -> ClientCheckoutResponse:
    """CPAY-01. Delegates into extracted online_payments core via Protocol slot (D-20-MODULE)."""
    # Membership idempotency key: server-derived (D-71-04)
    idem_key = _derive_membership_idempotency_key(plan_id=plan_id, client_id=client.id)
    result = await invoke_client_checkout_core(
        session,
        subject_kind="membership",
        plan_id=plan_id,
        client_id=client.id,
        idempotency_key=idem_key,
        actor_user_id=None,           # D-71-02: client-initiated → NULL
        confirmation_type="redirect",
        yookassa_settings=yookassa_settings,
    )
    return ClientCheckoutResponse(
        online_payment_id=result.online_payment_id,
        confirmation_url=result.confirmation_url,
    )
```

**Read service pattern** (existing lines 145-168 — `list_client_payments` is the precedent for status read):
```python
async def get_client_payment_status(
    session: AsyncSession,
    payment_id: UUID,
    client_id: UUID,
) -> ClientPaymentStatusResponse:
    """CPAY-03. Coarse status only — never activation/membership details."""
    row = await repository.fetch_client_payment_status(session, payment_id, client_id)
    if row is None:
        raise NotFoundError("payment_not_found")  # D-20-IDOR: 404-collapse
    return ClientPaymentStatusResponse(
        id=cast(Any, row)["id"],
        status=str(cast(Any, row)["status"]),   # 'pending' | 'succeeded' | 'canceled'
    )
```

---

### `apps/backend/app/modules/client_portal/repository.py` (repository, raw-SQL read for status)

**Analog:** `apps/backend/app/modules/client_portal/repository.py` (existing, L40-72)

**Cross-module read discipline** (file header lines 1-17):
- `from sqlalchemy import text` only — NEVER import another module's ORM model.
- Bind params via `:name` placeholders + dict; cast UUIDs to `str`.
- `.mappings().one_or_none()` for scalar reads.
- Each reader documents verified columns + source file:line of the foreign table.

**IDOR-safe status read pattern** (modeled on `fetch_client_membership`, lines 40-72):
```python
async def fetch_client_payment_status(
    session: AsyncSession,
    payment_id: UUID,
    client_id: UUID,
) -> dict[str, object] | None:
    """Coarse online payment status for a specific client (CPAY-03, D-20-IDOR).

    CROSS-MODULE READ — raw SQL text() only; NO ORM import of OnlinePayment.
    Verified columns (apps/backend/app/modules/online_payments/models.py:90-112):
      - id           PgUUID
      - client_id    PgUUID NOT NULL (IDOR filter)
      - status       Text NOT NULL ('pending' | 'succeeded' | 'canceled')

    IDOR: mandatory :client_id AND :payment_id bind params — 404-collapse on non-owned rows.
    Anti-oracle (CPAY-03): returns ONLY id + status. Never exposes membership/activation detail.
    """
    row = (
        await session.execute(
            text(
                "SELECT id, status FROM online_payments "
                "WHERE id = :payment_id AND client_id = :client_id"
            ),
            {"payment_id": str(payment_id), "client_id": str(client_id)},
        )
    ).mappings().one_or_none()
    return dict(row) if row else None
```

---

### `apps/backend/app/modules/client_portal/schemas.py` (model, new request/response schemas)

**Analog:** `apps/backend/app/modules/client_portal/schemas.py` (existing, L1-113)

**Imports pattern** (existing lines 1-17):
```python
from __future__ import annotations

from uuid import UUID
from app.core.schemas import ResponseData
```

**New schemas pattern** (modeled on `ClientCatalogPlanResponse`, lines 87-93):
```python
class ClientCheckoutRequest(ResponseData):
    """Request body for client-initiated checkout (CPAY-01/02)."""
    # No fields for membership (plan_id in path); for PT the idempotency_key is
    # supplied via Idempotency-Key header (D-71-04), not body.
    pass

class ClientCheckoutResponse(ResponseData):
    """Checkout response: redirect URL + online_payment_id for status polling (CPAY-03)."""
    online_payment_id: UUID
    confirmation_url: str   # redirect to ЮKassa — never null for redirect flow

class ClientPaymentStatusResponse(ResponseData):
    """Coarse payment status (CPAY-03 anti-oracle).

    Only 'pending' | 'succeeded' | 'canceled' — never activation or membership details.
    """
    id: UUID
    status: str  # Literal['pending', 'succeeded', 'canceled'] at runtime
```

---

### `apps/backend/app/core/audit.py` (utility, extend LOCKED_AUDIT_EVENTS)

**Analog:** itself — `LOCKED_AUDIT_EVENTS` frozenset (lines 263-443)

**D-71-02 finding:** `emit()` signature (line 491) already accepts `actor_user_id: UUID | None`. Passing `None` is the documented "system emit" path (D-41-10). No new field or parameter change needed.

**Extension pattern** (to add new client payment events, following the v2.0 Phase 68 block at lines 434-443):
```python
# v2.0 Phase 71 lock — CPAY-01..05 client-initiated checkout events.
# Pre-registered per INFRA-15 discipline — extend BEFORE any callsite.
# online_payment_initiated / yookassa_payment_created already locked (Phase 47 v1.7);
# client checkout REUSES these — no new event names for client-initiated payment start.
```

No new audit event pairs needed for Phase 71. The existing `("online_payment_initiated", "online_payment")` and `("yookassa_payment_created", "online_payment")` pairs from Phase 47 cover the client-initiated flow — they accept `actor_user_id=None` (D-41-10).

---

### `apps/backend/app/core/dependencies.py` (utility, Protocol-slot for checkout)

**Analog:** existing `register_client_loader` / `ClientPrincipal` block (lines 1148-1251)

**Protocol + slot registration pattern** (lines 58-68 for UserLoader, 1178-1188 for ClientLoader):
```python
# Pattern: module-level None + register_* + get_* (invoke_*) triplet
SellSubjectCoreCallable = Callable[..., Awaitable["SellResponse"]]
_client_checkout_core: SellSubjectCoreCallable | None = None

def register_client_checkout_core(fn: SellSubjectCoreCallable) -> None:
    """Composition-root setter — called once by app.main.create_app in Phase 71."""
    global _client_checkout_core
    _client_checkout_core = fn

async def invoke_client_checkout_core(session, **kwargs) -> "SellResponse":
    if _client_checkout_core is None:
        raise RuntimeError("client_checkout_core slot not registered — app.main.create_app must wire it")
    return await _client_checkout_core(session, **kwargs)
```

**D-20-MODULE rationale:** `client_portal` imports `app.core.dependencies.invoke_client_checkout_core` (allowed); `app.core` never imports `app.modules.online_payments` directly (importlinter `core-not-depend-on-modules` contract preserved).

---

### `apps/backend/app/main.py` (config, composition-root wiring)

**Analog:** itself — existing `register_*` block (line 395 area, wiring v1.5 protocol slots)

**Wiring pattern** (modeled on existing slot registrations at lines 395+):
```python
# In create_app(), alongside existing register_* calls:
from app.core.dependencies import register_client_checkout_core
from app.modules.online_payments.service import _sell_subject_core   # the extracted helper

register_client_checkout_core(_sell_subject_core)
```

This is the ONLY place `app.main` → `app.modules.online_payments` cross-module import is permitted (composition root is exempt from `core-not-depend-on-modules` per the existing pattern).

---

### OpenAPI + schema.d.ts regeneration (config, the type-contract bridge)

**Analog:** `apps/backend/scripts/export_openapi.py` (existing, lifespan-safe `create_app().openapi()` dump) + `packages/api-client/package.json` `codegen` script.

**Why:** the new `/api/v1/client/checkout/*` + `/api/v1/client/payments/{id}/status` endpoints (Plan 02) must appear in `packages/api-client/src/schema.d.ts` BEFORE any PWA typecheck references them. `schema.d.ts` is generated from the committed `apps/backend/openapi.json`, which must itself be regenerated from the FastAPI app after Plan 02 mounts the routes.

**Regen pattern** (two committed artifacts — run from repo root unless noted):
```bash
# 1. Regenerate apps/backend/openapi.json from the live FastAPI surface (canonical script)
cd apps/backend && uv run python -m scripts.export_openapi
#    → writes apps/backend/openapi.json (env-setdefault placeholders; no DB/Redis/Telegram touch)

# 2. Regenerate the typed schema from the refreshed openapi.json
pnpm --filter @clubcore/api-client codegen
#    → openapi-typescript ../../apps/backend/openapi.json --output src/schema.d.ts

# 3. Assert the new client paths landed in the typed schema
grep -q "/api/v1/client/checkout/memberships" packages/api-client/src/schema.d.ts
grep -q "/api/v1/client/payments" packages/api-client/src/schema.d.ts
```

Both `apps/backend/openapi.json` and `packages/api-client/src/schema.d.ts` are committed artifacts and MUST be listed in `files_modified` of whichever plan owns the regen (Plan 04 Task 0). This step gates `clientRequest<P extends keyof paths>` calls in `clientQueries.ts` — without it, TypeScript strict mode rejects every `/api/v1/client/*` path and `pnpm typecheck` fails.

---

### `apps/backend/tests/integration/client_portal/test_checkout.py` (test, new)

**Analog:** `apps/backend/tests/integration/client_portal/test_idor_sweep.py` (auth helper) + `apps/backend/tests/integration/online_payments/test_idempotency_hardening.py` (sell + idempotency pattern)

**Auth helper pattern** (from `test_idor_sweep.py` lines 36-79):
```python
async def _auth_as_client(async_client, db_session, client) -> str:
    """Request OTP → patch code → verify → return access cookie value."""
    req = await async_client.post("/api/v1/client/otp/request", json={"phone": client.phone})
    assert req.status_code == 202
    # patch OtpCode.code_hash via db_session
    ...
    verify = await async_client.post("/api/v1/client/otp/verify", ...)
    return verify.cookies["cc_client_access"]
```

**CSRF + checkout request pattern** (from `test_idempotency_hardening.py` lines 34-42):
```python
def _client_csrf_header(client: AsyncClient) -> str:
    return client.cookies.get("clubcore_client_csrf") or ""

def _checkout_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": _client_csrf_header(client)}
    # PT checkout also passes "Idempotency-Key": uuid4().hex

async def test_client_membership_checkout_returns_confirmation_url(...):
    r = await authed_client_as_member.post(
        f"/api/v1/client/checkout/memberships/{plan.id}",
        headers=_checkout_headers(authed_client_as_member),
        json={},
    )
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["confirmationUrl"].startswith("https://")
    assert "onlinePaymentId" in data
```

**IDOR test pattern** (from `test_idor_sweep.py`): authenticate as client A, attempt to GET `/api/v1/client/payments/{payment_owned_by_client_B}/status` → expect 404.

**Idempotency test pattern** (from `test_idempotency_hardening.py` lines 58-78): same-day repeat membership checkout → 201, returns the same `confirmation_url` (server-side replay check via `_derive_idempotency_key`).

---

### `apps/client-pwa/package.json` (config, add React Query)

**Analog:** `apps/admin-web/package.json` (React Query dependency reference)

```json
{
  "dependencies": {
    "@clubcore/api-client": "workspace:*",
    "@tanstack/react-query": "^5.59.0",
    "react": "18.3.1",
    "react-dom": "18.3.1",
    "react-router-dom": "6.26.2"
  }
}
```

Pin to the same React Query v5 minor as admin-web (`^5.59.0`) per D-71-06 mirror-admin-web-conventions.

---

### `apps/client-pwa/src/lib/queryClient.ts` (config, new file)

**Analog:** `apps/admin-web/src/app/queryClient.ts` (exact)

**Full pattern** (lines 1-17):
```typescript
import { QueryClient, QueryCache, MutationCache } from '@tanstack/react-query'

// Client PWA: session expiry handler redirects to /login (react-router v6 navigate)
function handleSessionExpired(error: unknown): void {
  if (error instanceof ApiError && error.code === 'session_expired') {
    window.location.replace('/login')  // react-router v6: no TanStack Router navigate
  }
}

export const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: handleSessionExpired }),
  mutationCache: new MutationCache({ onError: handleSessionExpired }),
  defaultOptions: {
    queries: {
      staleTime: 30_000,            // mirror admin-web convention (D-71-06)
      refetchOnWindowFocus: false,  // mirror admin-web convention
      retry: 1,
    },
    mutations: {
      retry: 0,
    },
  },
})
```

---

### `apps/client-pwa/src/lib/clientQueries.ts` (hook, new file — per-feature query hooks)

**Analog:** `apps/admin-web/src/features/clients/api/keys.ts` + `hooks.ts`

**Key factory pattern** (from `keys.ts` lines 1-10):
```typescript
// Per-feature key factory — D-71-06 mirror admin-web convention
export const clientPortalKeys = {
  all: ['client-portal'] as const,
  home: () => [...clientPortalKeys.all, 'home'] as const,
  membership: () => [...clientPortalKeys.all, 'membership'] as const,
  plans: () => [...clientPortalKeys.all, 'plans'] as const,
  ptPackages: () => [...clientPortalKeys.all, 'pt-packages'] as const,
  bookings: () => [...clientPortalKeys.all, 'bookings'] as const,
  visitHistory: (page: number) => [...clientPortalKeys.all, 'visits', page] as const,
  ptHistory: (page: number) => [...clientPortalKeys.all, 'pt-sessions', page] as const,
  paymentHistory: (page: number) => [...clientPortalKeys.all, 'payments', page] as const,
  paymentStatus: (id: string) => [...clientPortalKeys.all, 'payment-status', id] as const,
} as const
```

**useQuery hook pattern** (from `hooks.ts` lines 11-16):
```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { clientRequest } from '@/lib/clientFetcher'  // typed transport from Phase 69
import { clientPortalKeys } from './clientQueryKeys'

export function useClientHome() {
  return useQuery({
    queryKey: clientPortalKeys.home(),
    queryFn: async () => {
      const res = await clientRequest('GET', '/api/v1/client/home')
      return (res as { data: ClientHomeData }).data
    },
    staleTime: 30_000,
  })
}

export function useClientPlans() {
  return useQuery({
    queryKey: clientPortalKeys.plans(),
    queryFn: async () => {
      const res = await clientRequest('GET', '/api/v1/client/plans')
      return (res as { data: ClientCatalogPlan[] }).data
    },
    staleTime: 30_000,
  })
}
```

**Paginated history hook pattern** (Phase-69 endpoints — ProfileScreen tabs, replaces PURCHASE_HISTORY/TRAINING_HISTORY/VISIT_HISTORY mocks):
```typescript
// GET /api/v1/client/history/visits — visit-history tab
export function useClientVisitHistory(page = 1) {
  return useQuery({
    queryKey: clientPortalKeys.visitHistory(page),
    queryFn: async () => {
      const res = await clientRequest('GET', '/api/v1/client/history/visits', {
        params: { query: { page } },
      })
      return (res as { data: { items: unknown[]; total: number; page: number; pageSize: number } }).data
    },
    staleTime: 30_000,
  })
}

// GET /api/v1/client/history/pt-sessions — training-history tab
export function useClientPtHistory(page = 1) {
  return useQuery({
    queryKey: clientPortalKeys.ptHistory(page),
    queryFn: async () => {
      const res = await clientRequest('GET', '/api/v1/client/history/pt-sessions', {
        params: { query: { page } },
      })
      return (res as { data: { items: unknown[]; total: number; page: number; pageSize: number } }).data
    },
    staleTime: 30_000,
  })
}

// GET /api/v1/client/history/payments — purchase-history tab
export function useClientPaymentHistory(page = 1) {
  return useQuery({
    queryKey: clientPortalKeys.paymentHistory(page),
    queryFn: async () => {
      const res = await clientRequest('GET', '/api/v1/client/history/payments', {
        params: { query: { page } },
      })
      return (res as { data: { items: unknown[]; total: number; page: number; pageSize: number } }).data
    },
    staleTime: 30_000,
  })
}
```
These three `/api/v1/client/history/*` paths already exist in `schema.d.ts` from Phase 69 — they do NOT depend on the Plan-02 checkout regen.

**useMutation pattern for checkout** (from `memberships/api/hooks.ts` `useCreateMembership`, lines 62-70):
```typescript
export function useClientCheckoutMembership() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ planId }: { planId: string }) => {
      const res = await clientRequest('POST', `/api/v1/client/checkout/memberships/{plan_id}`, {
        params: { plan_id: planId },
        body: {},
      })
      return (res as { data: ClientCheckoutResult }).data
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: clientPortalKeys.membership() })
    },
  })
}
```

**Polling hook for payment status** (D-71-05 return-route polling):
```typescript
export function useClientPaymentStatus(paymentId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: clientPortalKeys.paymentStatus(paymentId ?? ''),
    queryFn: async () => {
      const res = await clientRequest('GET', '/api/v1/client/payments/{id}/status', {
        params: { id: paymentId! },
      })
      return (res as { data: { id: string; status: 'pending' | 'succeeded' | 'canceled' } }).data
    },
    enabled: enabled && !!paymentId,
    refetchInterval: (query) =>
      query.state.data?.status === 'pending' ? 3_000 : false,  // poll every 3s until settled
    staleTime: 0,  // always fresh for polling screen
  })
}
```

---

### `apps/client-pwa/src/data/index.js` (utility, mock seam swap — D-71-07)

**Analog:** itself (current file)

**Current mock pattern** (lines 1-12):
```javascript
export { TRAINERS } from './trainers.js';
export { CALENDAR, TIME_SLOTS, BUSY_SLOTS } from './calendar.js';
// ...etc
```

**Post-swap pattern** (D-71-07 — single swap point):
```javascript
// Phase 71: mock constants replaced by React Query hooks re-exported from the query layer.
// 6 wired screens import useClientHome, useClientPlans, etc. from here.
// Net-new screens import only ComingSoon — import boundary enforced by eslint (D-71-09).
export {
  useClientHome,
  useClientMembership,
  useClientPlans,
  useClientPtPackages,
  useClientBookings,
  useClientVisitHistory,
  useClientPtHistory,
  useClientPaymentHistory,
  useClientPaymentStatus,
  useClientCheckoutMembership,
  useClientCheckoutPtPackage,
} from '../lib/clientQueries'

// Legacy calendar/notifications/conversations mocks retained only if still used
// by coming-soon screen stubs (strip per D-71-08 if safe).
```

---

### `apps/client-pwa/src/screens/HomeScreen.jsx` (component, wire to real data)

**Analog:** itself (existing structure), with `useClientHome` hook replacing `UPCOMING_BOOKING`, `NOTIFICATIONS`, `GYM_INFO` mock constants.

**Import swap pattern** (line 9, before):
```javascript
import { GYM_INFO, NOTIFICATIONS, TRAINER_CANCEL, UPCOMING_BOOKING } from '@/data';
```

**Import swap pattern** (after):
```javascript
import { useClientHome } from '@/data'
// useClientHome() → { membership, next_booking, expiring_soon }
```

**Loading/error guard pattern** (React Query — no existing PWA analog; model on admin-web hooks):
```javascript
export const HomeScreen = ({ tweaks, ...handlers }) => {
  const { data: homeData, isLoading, isError } = useClientHome()
  if (isLoading) return <LoadingSpinner />
  if (isError) return <ErrorCard onRetry={() => refetch()} />
  const sub = toSubInfo(homeData?.membership)   // adapter from API shape to existing subInfo shape
  // ... rest of existing component unchanged
}
```

The `tweaks` / `setTweak` props are demo-only infrastructure; they can remain alongside real data for the demo mode toggle.

---

### `apps/client-pwa/src/screens/ProfileScreen.jsx` (component, wire to real data + history tabs)

**Analog:** itself + `clientQueries.ts` (home membership + the three Phase-69 history hooks).

**Import swap pattern** (before):
```javascript
import { PURCHASE_HISTORY, TRAINING_HISTORY, VISIT_HISTORY } from '@/data';
```

**Import swap pattern** (after):
```javascript
import {
  useClientHome,
  useClientVisitHistory,
  useClientPtHistory,
  useClientPaymentHistory,
} from '@/data'
```

ProfileScreen consumes membership/subscription status from `useClientHome()` and its three history tabs from `useClientVisitHistory` (visits), `useClientPtHistory` (training), `useClientPaymentHistory` (purchases). After wiring, ProfileScreen imports NO `VISIT_HISTORY`/`TRAINING_HISTORY`/`PURCHASE_HISTORY` mock constant (success criterion #4 — mock layer fully replaced for this screen). Each tab renders loading/error guards. The three history endpoints exist from Phase 69 — no checkout-regen dependency.

---

### `apps/client-pwa/src/screens/sheets/PlansSheet.jsx` (component, wire to real catalog)

**Analog:** itself + `useClientPlans` hook.

**Import swap pattern** (line 5, before):
```javascript
import { PLANS, PLAN_FEATURES } from '@/data';
```

**Import swap pattern** (after):
```javascript
import { useClientPlans, useClientPtPackages } from '@/data'
```

The `PlansSheet` renders plan cards from `PLANS`; replace with `plans` from `useClientPlans().data`. The confirmation step (`PlanConfirm` → `onPaid`) wires to `useClientCheckoutMembership()` mutation.

---

### `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx` (component, wire to ЮKassa)

**Analog:** itself (existing stages: `review → paying → done | error`). The mock `startPay` timeout becomes a real mutation call.

**Mutation wire pattern** (modeled on admin-web `useMutation` pattern, memberships/api/hooks.ts lines 62-70):
```javascript
import { useClientCheckoutMembership, useClientCheckoutPtPackage } from '@/data'

export const CheckoutSheet = ({ ctx, onClose, onDone }) => {
  const checkoutMembership = useClientCheckoutMembership()
  const checkoutPtPackage = useClientCheckoutPtPackage()

  const startPay = async () => {
    setStage('paying')
    try {
      const mutation = ctx.kind === 'sub' ? checkoutMembership : checkoutPtPackage
      const result = await mutation.mutateAsync({ planId: ctx.planId, idempotencyKey: ctx.idempotencyKey })
      // Redirect to ЮKassa confirmation_url
      window.location.href = result.confirmationUrl
      // Return-route will handle polling (D-71-05)
    } catch (err) {
      const code = err?.code ?? 'payment'
      setErrorKind(mapApiErrorToKind(code))   // 'payment' | 'offline' | 'slot-busy'
      setStage('error')
    }
  }
}
```

**Error mapping** (D-71-02 discretion — surface ЮKassa errors as inline, not toast):
```javascript
function mapApiErrorToKind(code) {
  if (code === 'client_email_required_for_online_payment') return 'email-required'
  if (code === 'yookassa_unavailable') return 'offline'
  if (code === 'yookassa_permanent_error') return 'payment'
  if (code === 'network_error') return 'offline'
  return 'payment'
}
```

---

### `apps/client-pwa/src/screens/sheets/QRSheet.jsx` (component, wire to real QR data)

**Analog:** itself. The hardcoded QR pattern becomes the client's real QR token from the Phase 70 QR endpoint (Phase 70 dependency).

The existing phase-animation logic (`idle → scanning → success`) is UI-only and remains. Only the data source for the QR content changes: replace the static `QRPattern` with a QR code generated from the Phase 70 `/api/v1/client/qr-token` response.

---

### PWA Return Route (`/payment/return` — new react-router v6 route)

**Analog:** react-router v6 route pattern from existing `App.jsx` or router file. No exact existing analog — closest is a simple screen component.

**Route pattern** (react-router v6, D-20-PWA-ROUTER — no TanStack Router):
```javascript
// New route added to react-router routes:
import { useSearchParams } from 'react-router-dom'
import { useClientPaymentStatus } from '@/data'

export function PaymentReturnScreen() {
  const [params] = useSearchParams()
  const paymentId = params.get('payment_id')
  const { data, isLoading } = useClientPaymentStatus(paymentId, !!paymentId)

  if (isLoading || data?.status === 'pending') {
    return <div>Ожидаем подтверждение...</div>  // criterion #1 — never show "active" prematurely
  }
  if (data?.status === 'succeeded') {
    // Navigate to Home/Profile showing now-active membership
    return <Navigate to="/" replace />
  }
  if (data?.status === 'canceled') {
    return <PaymentCanceledScreen />
  }
  return <div>Ожидаем подтверждение...</div>
}
```

The ЮKassa `return_url` is constructed as:
`${origin}/payment/return?payment_id={online_payment_id}` (for membership).
For PT with client-supplied Idempotency-Key, also pass `?idempotency_key={key}` so the return route can surface the idempotency key if the user navigates back to retry.

---

### `apps/client-pwa/src/components/ComingSoon.tsx` (component, new shared placeholder)

**Analog:** `apps/admin-web/src/shared/ui/` component pattern + PWA `EmptyState.jsx` structure.

**Pattern** (D-71-08 — shared placeholder for Chat, Referral, TrainerDetail, Notifications, GymInfo):
```typescript
// TypeScript (new file — not in the JSX allowJs ramp)
import React from 'react'

/**
 * "В разработке" placeholder (D-71-08).
 * Net-new screens import ONLY this component — no query layer imports (D-71-09).
 */
export function ComingSoon({ title = 'Скоро' }: { title?: string }) {
  return (
    <div className="page" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, padding: 32 }}>
      <div className="t-h2">{title}</div>
      <div className="t-small" style={{ color: 'var(--text-3)', textAlign: 'center' }}>
        В разработке
      </div>
    </div>
  )
}
```

---

### `apps/client-pwa/eslint.config.js` (config, add import boundary — D-71-09)

**Analog:** itself (current file, lines 1-51) + `apps/admin-web/eslint.config.js` (import boundary pattern)

**D-71-09 import boundary rule pattern** (modeled on admin-web's `import/no-restricted-paths`):
```javascript
rules: {
  // D-71-09: net-new placeholder screens cannot import the query layer
  'import/no-restricted-paths': [
    'error',
    {
      zones: [
        {
          // ChatScreen, ReferralSheet, TrainerDetailSheet, NotificationsSheet, GymInfoSheet
          // must NOT import clientFetcher, clientQueries, or @tanstack/react-query
          target: [
            './src/screens/ChatScreen.jsx',
            './src/screens/sheets/ReferralSheet.jsx',
            './src/screens/sheets/TrainerDetailSheet.jsx',
            './src/screens/sheets/NotificationsSheet.jsx',
            './src/screens/sheets/GymInfoSheet.jsx',
          ],
          from: [
            './src/lib/clientFetcher.ts',
            './src/lib/clientQueries.ts',
            './src/data/index.js',
          ],
          message: 'Net-new screens are placeholders (D-71-09) — no query layer imports.',
        },
      ],
    },
  ],
},
```

Note: current eslint config ignores `**/*.jsx` (D-69-06 allowJs ramp). The no-restricted-paths rule for `.jsx` screens requires adding them to the `files` pattern or using a dedicated block for the specific files. Planner should determine whether to extend the JSX ignore exception or enforce via a separate rule block targeting only those five files.

---

## Shared Patterns

### Client Authentication Gate
**Source:** `apps/backend/app/core/dependencies.py` lines 1158-1251
**Apply to:** All new `client_portal` router endpoints (POST + GET)
```python
client: Annotated[ClientPrincipal, Depends(require_client())]
```
- GET endpoints: `require_client()` only. No CSRF dep.
- POST endpoints: `require_client()` first, then `verify_client_csrf` after (RBAC-04 ordering).

### IDOR-Safe Raw-SQL Read
**Source:** `apps/backend/app/modules/client_portal/repository.py` lines 40-72
**Apply to:** `fetch_client_payment_status` (new) + any additional payment reads
```python
# Pattern: mandatory :client_id bind param on every owned-resource SELECT
text("SELECT ... FROM online_payments WHERE id = :payment_id AND client_id = :client_id"),
{"payment_id": str(payment_id), "client_id": str(client_id)},
```
404-collapse on None result (service layer raises `NotFoundError`, not a leak).

### Caller-Owns-Transaction
**Source:** `apps/backend/app/modules/online_payments/service.py` module docstring lines 25-27
**Apply to:** All new service functions that write to the DB
```python
# No session.commit() in service or repository — FastAPI dependency commits on response.
await session.flush()  # surface FK + CHECK + UNIQUE conflicts before audit emit
```

### Audit ROOT→CHILD Chain
**Source:** `apps/backend/app/modules/online_payments/service.py` lines 270-303
**Apply to:** Client checkout write path
```python
correlation_id = uuid4()
# ROOT emit (actor_user_id=None for client-initiated)
await audit.emit(session, "online_payment_initiated", actor_user_id=None, ...)
# CHILD emit
await audit.emit(session, "yookassa_payment_created", actor_user_id=None, ...)
```

### OpenAPI → schema.d.ts Regen Bridge
**Source:** `apps/backend/scripts/export_openapi.py` + `packages/api-client/package.json` `codegen`
**Apply to:** Plan 04 Task 0 (runs AFTER Plan 02 mounts the client checkout/status endpoints)
```bash
cd apps/backend && uv run python -m scripts.export_openapi   # → apps/backend/openapi.json
pnpm --filter @clubcore/api-client codegen                   # → packages/api-client/src/schema.d.ts
grep -q "/api/v1/client/checkout/memberships" packages/api-client/src/schema.d.ts  # assert
```
Both artifacts are committed; without this step `clientRequest<P extends keyof paths>` calls in `clientQueries.ts` fail strict-mode typecheck.

### React Query Hook Shape (PWA)
**Source:** `apps/admin-web/src/features/clients/api/hooks.ts` lines 11-16
**Apply to:** All new `clientQueries.ts` hooks
```typescript
// useQuery: staleTime: 30_000, no explicit refetchOnWindowFocus (set globally on QueryClient)
// useMutation: onSettled invalidates related queries
// No optimistic updates for checkout (write-once — no list to patch)
```

### Protocol-Slot Registration
**Source:** `apps/backend/app/core/dependencies.py` lines 58-68 (UserLoader pattern)
**Apply to:** New `client_checkout_core` slot in `dependencies.py` + `main.py` wiring
```python
# Triplet: _slot_var: Type | None = None + register_* + invoke_*(raises if None)
# Only wired in app.main.create_app() — never in workers or tests directly
```

---

## No Analog Found

All files have usable analogs. The following files have no existing PWA analog (planner should use patterns from admin-web and the extracted backend patterns above):

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `apps/client-pwa/src/routes/PaymentReturnScreen.jsx` | component | polling | No existing PWA polling screen — use `useClientPaymentStatus` hook with `refetchInterval` |
| `apps/client-pwa/src/lib/queryClient.ts` | config | — | No existing PWA QueryClient — copy admin-web `queryClient.ts` verbatim with session-expiry handler adjusted for react-router v6 |

---

## Metadata

**Analog search scope:** `apps/backend/app/modules/`, `apps/backend/app/core/`, `apps/backend/tests/integration/`, `apps/admin-web/src/features/`, `apps/client-pwa/src/`
**Files read:** 22
**Pattern extraction date:** 2026-05-30
</content>
</invoke>
