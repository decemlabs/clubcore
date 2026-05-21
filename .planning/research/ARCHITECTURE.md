# Architecture: v1.7 Online Payments (ЮKassa) + 54-ФЗ Fiscal Receipts

**Researched:** 2026-05-21
**Confidence:** HIGH (codebase read + official ЮKassa docs + v1.4–v1.6 pattern precedents)

---

## 1. New Module(s): Sibling vs Extension

**Decision: new sibling `app/modules/online_payments/` alongside existing `app/modules/payments/`.**

Rationale:

The v1.4 `payments/` module is an **append-only ledger**. Its two public surfaces are `record_payment` and `issue_refund`, both decorated `# noqa: SVC001 caller-owns-txn` and intentionally commit-free. The module has AST-enforced append-only discipline (`test_payments_appendonly.py` bans `update(Payment)` / `delete(Payment)` anywhere in the module). Extending it with mutable FSM columns, webhook-state transitions, and ЮKassa-specific status tracking would require lifting that ban or creating two tiers of logic inside one module — architectural debt. The v1.4 CHECK constraints on `payments` (`subject_kind IN ('membership','pt_package','refund')`, signed-amount) would need new subject_kind values OR explicit exceptions, complicating the bedrock invariants.

The sibling pattern keeps `payments/` frozen and purpose-pure: it records the **final committed transaction** (cash or online). `online_payments/` owns the **lifecycle up to commitment** — the pending/captured/succeeded/canceled states live there until `succeeded` triggers a `record_payment` call through the existing Protocol slot.

Concrete boundary:

```
app/modules/online_payments/
  models.py          # OnlinePayment (FSM columns), OnlineRefund
  schemas.py         # create/response Pydantic schemas
  repository.py      # get/insert/update helpers — caller-owns-txn
  service.py         # orchestrator: create_online_payment, capture, handle_webhook_event
  constants.py       # ONLINE_PAYMENT_STATUS_TRANSITIONS, SUBJECT_KIND_* (mirrors payments/constants.py)
  notifications.py   # DM template constants: PAYMENT_SUCCESS_DM, REFUND_ISSUED_DM (mirrors bookings/notifications.py D-39-02)
  email_templates.py # EMAIL_PAYMENT_ONLINE_SUCCESS, EMAIL_ONLINE_REFUND — extends payments/ ladder
  permissions.py     # RBAC gates for online-payment create / refund
  router.py          # /online-payments/* endpoints
```

The `payments/email_templates.py` already has `EMAIL_PAYMENT_RECEIPT_SALE` / `EMAIL_PAYMENT_RECEIPT_REFUND` for cash receipts. Online payments get separate template IDs (`EMAIL_PAYMENT_ONLINE_SUCCESS_SALE`, `EMAIL_PAYMENT_ONLINE_SUCCESS_REFUND`) in a new file inside `online_payments/` — keeping the domain-ownership convention (D-39-02).

**What gets modified in `payments/`:** Zero. The `Payment` ORM model, its CHECK constraints, and `record_payment` / `issue_refund` are untouched. The only cross-module allowance needed (see §10) is `online_payments/service.py → payments/models.py` for writing `PaymentReceipt` rows (same pattern as the Phase 45 `memberships/service.py → payments/models.py` ignore).

---

## 2. New Integration: `app/integrations/yookassa/`

Shape mirrors `app/integrations/email/` exactly: config, client, factory, types.

```
app/integrations/yookassa/
  __init__.py
  types.py          # YooKassaPaymentResult, YooKassaReceiptResult (frozen dataclasses)
  client.py         # YooKassaClient (async httpx), SandboxYooKassaClient
  factory.py        # build_yookassa_client(settings) -> async
  webhook_verifier.py  # verify_yookassa_ip(request) — IP-allowlist check (NOT HMAC, see §3)
```

**What lives in `integrations/yookassa/` vs in `modules/online_payments/`:**

| Concern | Location | Reason |
|---------|----------|--------|
| HTTP transport (POST /payments, POST /refunds, POST /receipts) | `integrations/yookassa/client.py` | Pure I/O adapter, no domain knowledge |
| Sandbox stub | `integrations/yookassa/client.py:SandboxYooKassaClient` | Mirrors `SandboxEmailClient` pattern |
| Boot-time API probe | `integrations/yookassa/factory.py` | Same pattern as email factory D-42-30 |
| IP allowlist verification | `integrations/yookassa/webhook_verifier.py` | Transport-level gate, domain-agnostic |
| FSM state transitions, audit chains | `modules/online_payments/service.py` | Domain logic, must not live at integrations layer |
| ЮKassa payment-object → domain FSM mapping | `modules/online_payments/service.py` | Domain logic |
| 54-ФЗ receipt dispatch orchestration | `modules/online_payments/service.py` | Domain orchestration, not transport |

**`types.py` shape:**

```python
@dataclass(frozen=True)
class YooKassaPaymentResult:
    ok: bool
    classification: Literal["ok", "transient_error", "permanent_error"]
    payment_id: str | None = None       # ЮKassa UUID string
    status: str | None = None           # "pending" | "waiting_for_capture" | "succeeded" | "canceled"
    confirmation_url: str | None = None
    error: str | None = None

@dataclass(frozen=True)
class YooKassaReceiptResult:
    ok: bool
    classification: Literal["ok", "transient_error", "permanent_error"]
    receipt_id: str | None = None       # ЮKassa receipt UUID
    status: str | None = None           # "pending" | "succeeded" | "canceled"
    error: str | None = None
```

**`client.py` shape:**

```python
class YooKassaClient:
    """Async httpx adapter for ЮKassa API v3. NEVER re-raises — every outcome is a value."""

    async def create_payment(
        self,
        *,
        idempotency_key: str,           # UUID string, MANDATORY
        amount_kopecks: int,
        description: str,
        return_url: str,
        customer_email: str | None,
        receipt_items: list[dict],       # 54-ФЗ items
        capture: bool = True,
    ) -> YooKassaPaymentResult: ...

    async def capture_payment(
        self,
        *,
        payment_id: str,
        idempotency_key: str,
        amount_kopecks: int,
    ) -> YooKassaPaymentResult: ...

    async def cancel_payment(
        self,
        *,
        payment_id: str,
        idempotency_key: str,
    ) -> YooKassaPaymentResult: ...

    async def create_refund(
        self,
        *,
        idempotency_key: str,
        payment_id: str,
        amount_kopecks: int,
        description: str,
    ) -> YooKassaPaymentResult: ...

    async def create_receipt(
        self,
        *,
        idempotency_key: str,
        payment_id: str,
        customer_email: str | None,
        customer_phone: str | None,
        items: list[dict],
        type: Literal["payment", "refund"],
    ) -> YooKassaReceiptResult: ...
```

**Config (`app/core/config.py` extension — new `YooKassaSettings` nested model):**

```python
class YooKassaSettings(BaseModel):
    shop_id: str
    secret_key: SecretStr
    provider: Literal["yookassa", "sandbox"] = "sandbox"
    sandbox_mode: bool = True
    api_base_url: str = "https://api.yookassa.ru/v3"
    # IP allowlist for webhook verification (from ЮKassa docs — static since 2024)
    webhook_allowed_ips: list[str] = [
        "185.71.76.0/27", "185.71.77.0/27",
        "77.75.153.0/25", "77.75.156.11",
        "77.75.156.35", "77.75.154.128/25",
    ]
```

---

## 3. Webhook Endpoint: Router Location and Signature Verification

**Location:** `app/api/v1/_internal/yookassa/router.py`, mounted at `POST /api/v1/_internal/yookassa/webhook`.

This follows the established `_internal` namespace convention introduced in Phase 42 for the email bounce webhook. The comment in `app/api/v1/router.py` at the email mount explicitly names "ЮKassa, SMS providers, ..." as future inhabitants of `/_internal/*`.

**Verification method — IP allowlist, NOT HMAC.**

ЮKassa's documented security model uses source-IP validation (six published CIDRs). They do not publish a shared-secret HMAC header equivalent to `X-Email-Webhook-Signature`. Attempting to invent an HMAC gate would be security theater — there is no server secret that can be verified against a header ЮKassa does not send.

The project constraint that says "Webhook security: ЮKassa `Notification-Sign` HMAC verification" in PROJECT.md reflects a common misconception from blog posts. The official ЮKassa documentation (verified) confirms IP-based allowlisting as the authentication mechanism.

**Implementation:**

```python
# app/integrations/yookassa/webhook_verifier.py
import ipaddress
from fastapi import Request

_YOOKASSA_CIDRS: frozenset[ipaddress.IPv4Network | ipaddress.IPv6Network] = frozenset({
    ipaddress.ip_network("185.71.76.0/27"),
    ipaddress.ip_network("185.71.77.0/27"),
    ipaddress.ip_network("77.75.153.0/25"),
    ipaddress.ip_network("77.75.156.11/32"),
    ipaddress.ip_network("77.75.156.35/32"),
    ipaddress.ip_network("77.75.154.128/25"),
    ipaddress.ip_network("2a02:5180::/32"),
})

def verify_yookassa_ip(request: Request) -> None:
    """Verify request originated from ЮKassa IP range. Raise HTTPException(401) on fail."""
    # Read X-Forwarded-For if behind a proxy, else request.client.host
    ...
```

This is a `Depends()` callable, usable as `Depends(verify_yookassa_ip)` on the webhook endpoint. There is no AST gate needed (no shared secret constant to enforce — verification is structural/network-layer). In **production** deployments, supplement with network-layer firewall rules. In **dev/test**, the verifier accepts `127.0.0.1` unconditionally via a `settings.yookassa.sandbox_mode` bypass flag.

**Router shape:**

```python
# app/api/v1/_internal/yookassa/router.py
router = APIRouter()

@router.post("/webhook", status_code=200, response_class=Response)
async def yookassa_webhook(
    request: Request,
    _ip: Annotated[None, Depends(verify_yookassa_ip)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """ЮKassa payment lifecycle notifications. IP-verified before parse."""
    ...
```

No `Depends(get_current_user)`, no CSRF — this is a machine-to-machine callback. Response is always 200 (ЮKassa will retry on non-200).

---

## 4. Async Webhook Processing: Synchronous vs Queued

**Decision: synchronous processing (verify + process + 200 in webhook handler).**

Tradeoff analysis:

| Criterion | Sync (verify+process+200) | Queued (verify+200, ARQ processes) |
|-----------|--------------------------|-------------------------------------|
| ЮKassa retry semantics | ЮKassa retries if it gets non-200. If processing fails after enqueue, we already sent 200, so ЮKassa won't retry — we must handle our own retry. | Requires internal retry mechanism for every failure mode that could occur between enqueue and completion. |
| Visibility of failures | Error surfaces immediately in request logs + structlog. Failure → non-200 → ЮKassa retries with backoff. | Error buried in ARQ job logs. ARQ has `max_tries` but retry failure is silent from ЮKassa's perspective. |
| Idempotency surface | One UoW per webhook. DB UNIQUE constraint on `(yookassa_payment_id, event)` rejects duplicate processing at the DB layer — idempotent re-runs are safe. | Adds queue as second idempotency surface; complicates "exactly once" reasoning across Postgres + Redis. |
| Timeout risk | ЮKassa timeout is not published but webhook consumers typically have 5–30 seconds. The webhook handler does: 1 DB write + 1 audit emit + 1 ARQ enqueue for notifications (fast). NOT the ЮKassa outbound call. | No timeout risk for the acknowledgement, but adds queue lag before membership activates. |
| Membership activation latency | Zero extra latency: succeeded → membership activated in the same transaction, then enqueue DM. | Activation delayed by ARQ queue depth (typically seconds, but unpredictable under load). |
| Consistency | Single Postgres commit covers: FSM transition + ledger row (`record_payment`) + `payment_receipt` idempotency row + audit chain. | Decoupled commits — if ARQ job fails after enqueue, the 200 is already sent but activation hasn't happened. Requires compensating saga. |

**Winner: synchronous.** The webhook handler is fast (no outbound HTTP, just DB writes). Failure → non-200 → ЮKassa retries with its own backoff. Idempotency is enforced by DB UNIQUE. The only jobs enqueued inside the webhook handler are non-critical DM/email notifications (fire-and-forget, already the pattern for v1.5 booking notifications).

**Exception:** fiscal receipt dispatch is also enqueued as an ARQ job after commit (same `dispatch_fiscal_receipt` task pattern as `dispatch_email`). The receipt send is best-effort; failure does NOT roll back the payment commit (same decision as v1.6 Phase 45 D-45-08 for `PaymentReceipt` post-commit fanout).

---

## 5. FSM Placement: Where Does the ЮKassa Payment State Live?

**Decision: new `online_payments` table with FK into `payments`, NOT new columns on existing `payments`.**

Rationale:

The `payments` table has a DB-level CHECK: `subject_kind IN ('membership','pt_package','refund')`. Online payment rows during their `pending` / `waiting_for_capture` phase are NOT yet recorded in the ledger — they only become ledger rows on `succeeded`. Adding a `yookassa_payment_id` or `status` column to `payments` would require either:
- Allowing NULL values for cash rows (violates NOT NULL discipline)
- Widening the CHECK to allow a `pending_online` subject_kind (which would then require signed-amount semantics before the amount is confirmed)

Both are wrong. The correct model is:

```
online_payments                    payments (append-only ledger)
─────────────────────            ───────────────────────────────
id (PK, UUID)                    id (PK, UUID)
yookassa_payment_id (TEXT, UNIQUE)
subject_kind TEXT                subject_kind TEXT (CHECK: membership|pt_package|refund)
subject_id UUID                  subject_id UUID
amount_kopecks INT               amount_kopecks INT (signed CHECK)
status TEXT (FSM col)            method TEXT ('online'|'cash')
idempotency_key TEXT (UNIQUE)    received_at TIMESTAMPTZ
created_at TIMESTAMPTZ           received_by_user_id UUID (FK users)
updated_at TIMESTAMPTZ           refund_of UUID (partial UNIQUE)
payment_id UUID (FK payments, NULL until succeeded)
audit_log_id UUID (FK audit_log)
```

The `online_payments.payment_id` FK to `payments` is NULL until `succeeded` — at that point the webhook handler calls `record_payment()` through the existing Protocol slot, commits a `Payment` row, and backfills `online_payments.payment_id`.

**FSM states and transitions (declarative constant, same as `MEMBERSHIP_STATUS_TRANSITIONS`):**

```python
ONLINE_PAYMENT_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending":              frozenset({"waiting_for_capture", "succeeded", "canceled"}),
    "waiting_for_capture":  frozenset({"succeeded", "canceled"}),
    "succeeded":            frozenset(),   # terminal
    "canceled":             frozenset(),   # terminal
}
```

**CHECK constraint on `online_payments.status`:**
`status IN ('pending','waiting_for_capture','succeeded','canceled')`

**v1.4 invariants preserved:** The existing `payments` CHECK constraints, partial UNIQUE on `refund_of`, and audit chain remain untouched. `record_payment(method='online', ...)` creates the ledger row — the only change to `payments/service.py` would be widening the `method` TEXT default from `'cash'` to allow `'online'` (no constraint change, `method` is an unconstrained TEXT column per the model).

---

## 6. Fiscal Receipt Model

**New table: `fiscal_receipts`.**

```sql
CREATE TABLE fiscal_receipts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id UUID NOT NULL REFERENCES payments(id) ON DELETE RESTRICT,
    kind TEXT NOT NULL,         -- 'payment' | 'refund'
    yookassa_receipt_id TEXT,   -- populated after ЮKassa /receipts call
    status TEXT NOT NULL DEFAULT 'pending',  -- FSM: pending→sent→succeeded|failed
    idempotency_key TEXT NOT NULL UNIQUE,    -- deterministic from payment_id + kind
    attempts INT NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_fiscal_receipts_kind CHECK (kind IN ('payment','refund')),
    CONSTRAINT ck_fiscal_receipts_status CHECK (status IN ('pending','sent','succeeded','failed')),
    CONSTRAINT uq_fiscal_receipts_payment_kind UNIQUE (payment_id, kind)
);
```

**Idempotency invariant:** `UNIQUE (payment_id, kind)` — one fiscal receipt per payment per direction. This mirrors the v1.6 `UNIQUE (payment_id, channel)` on `payment_receipts` but is semantically different: `fiscal_receipts` tracks the OFD registration status of the 54-ФЗ fiscal document, not notification delivery.

**FK is to `payments.id`, not `online_payments.id`.** The fiscal receipt is an obligation that attaches to the committed ledger row. This means the `fiscal_receipts` row is created inside the same transaction as `record_payment()` on webhook `succeeded` — atomically. The `online_payments.payment_id` backfill also happens in this commit.

**Status FSM:**

```
pending ──[ARQ dispatch_fiscal_receipt called]──► sent
  sent  ──[ЮKassa webhook receipt.succeeded]────► succeeded  (terminal)
  sent  ──[ЮKassa webhook receipt.canceled / max_tries exceeded]──► failed
```

**Retry policy:** ARQ task `dispatch_fiscal_receipt` with `_max_tries=3, _expires=30`. On transient failure (5xx from ЮKassa) the ARQ retry reschedules. On `failed` terminal state, alert is emitted via structlog WARNING + `fiscal_receipt_failed` audit event. No silent discard.

**Note on ЮKassa ЧеKassa path:** ЮKassa's own `/receipts` API handles the 54-ФЗ obligation if receipt data is included in the original payment creation request. In that case, ЮKassa itself sends the receipt to the OFD and notifies via `receipt.succeeded` / `receipt.canceled` webhook events. The `fiscal_receipts` table tracks the local view of that lifecycle. The receipt is not a second outbound call — it is created as part of the payment creation request (items + customer data). The `sent` → `succeeded` transition is driven by the `receipt.succeeded` webhook event. This means: the `fiscal_receipts` row is created on payment `succeeded`, with `status='sent'` (ЮKassa has already accepted the receipt data in the payment request), and transitions to `succeeded` / `failed` via webhook.

---

## 7. Cross-Channel DM Template Constants

**Pattern: per-module ownership (D-39-02), same as bookings.**

Template IDs live in:
- `app/modules/online_payments/notifications.py` — Telegram DM constants (locked Russian strings)
- `app/modules/online_payments/email_templates.py` — email template registry, added to `LOCKED_EMAIL_TEMPLATES`

These do NOT go into `app/modules/payments/` because they belong to the online payment lifecycle, not the cash ledger. The cash receipt templates (`EMAIL_PAYMENT_RECEIPT_SALE`, `EMAIL_PAYMENT_RECEIPT_REFUND`) in `payments/email_templates.py` remain for cash flows.

New template IDs to add to `LOCKED_EMAIL_TEMPLATES` (frozenset must grow from 15 to accommodate):

```python
# Online payment success
"EMAIL_ONLINE_PAYMENT_SUCCESS"   # "Оплата прошла успешно"
"EMAIL_ONLINE_REFUND_SUCCESS"    # "Возврат оформлен"
# Fiscal receipt confirmation (optional — ЮKassa sends receipt to client directly;
# this template is for an admin-facing audit confirmation, not duplicate receipt)
```

Telegram DM constants in `online_payments/notifications.py`:

```python
PAYMENT_SUCCESS_DM: Final[str] = "..."     # "Оплата прошла. Абонемент активирован."
REFUND_ISSUED_DM: Final[str] = "..."       # "Возврат оформлен."
```

**Dispatcher walker update:** `app/integrations/email/dispatcher.py:_resolve_template()` must get a new `from app.modules.online_payments.email_templates import TEMPLATES as ONLINE_PAYMENTS_TEMPLATES` branch — one new import, one new `if template_id in ONLINE_PAYMENTS_TEMPLATES:` check. New `.importlinter` `ignore_imports` entry required: `app.integrations.email.dispatcher -> app.modules.online_payments.email_templates`.

---

## 8. Protocol Slots at Composition Root

Two new Protocol slots are needed. Both are **defensive-raise** (not silent-None) because their absence is hard misconfiguration.

**Slot 1: `YooKassaClientProvider`**

```python
# app/core/dependencies.py
class YooKassaClientProvider(Protocol):
    async def __call__(self) -> Any: ...  # returns YooKassaClient | SandboxYooKassaClient

_yookassa_client_provider: YooKassaClientProvider | None = None

def register_yookassa_client_provider(provider: YooKassaClientProvider) -> None: ...
def get_yookassa_client() -> YooKassaClientProvider: ...  # defensive raise
```

Wired from `app/main.py:create_app()` AND `app/workers/__init__.py:on_startup` (REG-29-03 double-wire — the ARQ `dispatch_fiscal_receipt` task needs the client in the worker process).

**Slot 2: `FiscalReceiptDispatcher`**

```python
class FiscalReceiptDispatcher(Protocol):
    async def __call__(
        self,
        *,
        payment_id: UUID,
        kind: Literal["payment", "refund"],
        idempotency_key: str,
        audit_correlation_id: UUID | None,
    ) -> None: ...

_fiscal_receipt_dispatcher: FiscalReceiptDispatcher | None = None

def register_fiscal_receipt_dispatcher(impl: FiscalReceiptDispatcher) -> None: ...
def get_fiscal_receipt_dispatcher() -> FiscalReceiptDispatcher: ...  # defensive raise
```

Wired from `app/main.py:create_app()` — the concrete implementation enqueues an ARQ job `dispatch_fiscal_receipt`, mirroring the `enqueue_email_dispatch` pattern.

**Slot 3: `OnlinePaymentCreator` (optional — may live entirely in module scope)**

The `online_payments/service.py` `create_online_payment()` function does not cross module boundaries — it is called from `online_payments/router.py` directly. No cross-module Protocol slot needed unless a future module (e.g., `bookings/`) needs to initiate an online payment without importing `online_payments`. Defer this slot to the phase where the need arises.

**Summary of new composition-root registrations in `app/main.py`:**

```python
# Phase 47+ additions
from app.integrations.yookassa.factory import build_yookassa_client
from app.modules.online_payments.service import enqueue_fiscal_receipt_dispatch

# Lifespan: build client once per process (async factory)
# create_app(): register slots
register_yookassa_client_provider(lambda: yookassa_client)  # client built in lifespan
register_fiscal_receipt_dispatcher(enqueue_fiscal_receipt_dispatch)
```

---

## 9. Migration Order: Alembic Revisions (~0033 onwards)

Current head: `0032_booking_notifications_widen_kind.py`.

| Revision | Name | Depends On | Content |
|----------|------|-----------|---------|
| 0033 | `yookassa_config_probe` | 0032 | No schema change. Adds `YooKassaSettings` to `app/core/config.py`. Migration is a sentinel to mark the bedrock phase. |
| 0034 | `online_payments` | 0033 | New `online_payments` table: FSM columns, `yookassa_payment_id UNIQUE`, `idempotency_key UNIQUE`, FK to `payments` (nullable until succeeded), `audit_log_id FK`. CHECK on status + subject_kind. Indexes: `(status)`, `(yookassa_payment_id)`, `(subject_kind, subject_id)`. |
| 0035 | `fiscal_receipts` | 0034 | New `fiscal_receipts` table: FK to `payments` (NOT `online_payments` — attaches to the committed ledger row). UNIQUE `(payment_id, kind)`. CHECK on kind + status. Index `(status)` for retry worker query. |
| 0036 | `locked_audit_events_v17` | 0035 | No schema change. Extends `LOCKED_AUDIT_EVENTS` frozenset (new events: `online_payment_created`, `online_payment_succeeded`, `online_payment_canceled`, `online_payment_webhook_received`, `fiscal_receipt_sent`, `fiscal_receipt_succeeded`, `fiscal_receipt_failed`, `online_refund_created`, `online_refund_succeeded`). This is a code-only migration sentinel — the frozenset is in `app/core/audit.py`, not DB. |

**Safe rollout order:**

1. Deploy 0033 (config probe, no schema). Boot-fail-fast validates ЮKassa credentials before any endpoint accepts traffic.
2. Deploy 0034 (`online_payments` table). Safe to run before any route uses it — empty table.
3. Deploy 0035 (`fiscal_receipts` table). Depends on `payments` existing (0012) — safe.
4. Code deploys for `modules/online_payments/`, `integrations/yookassa/`, `_internal/yookassa/` router.
5. Code deploy extends `LOCKED_AUDIT_EVENTS` (must precede any callsite — INFRA-15 discipline).

**Rollback:** Tables 0034+0035 are addable/droppable independently. No modification to existing tables means zero risk to v1.4 ledger integrity.

---

## 10. import-linter Contract Update

New module additions to `.importlinter:contract:modules-independent` (independence list):

```ini
[importlinter:contract:modules-independent]
modules =
    ...existing 13 modules...
    app.modules.online_payments    # NEW
```

New `ignore_imports` entries required:

```ini
# Phase 47 — online_payments orchestrator writes PaymentReceipt rows (fiscal
# receipt idempotency) via payments/models.py, mirroring Phase 45 memberships
# → payments pattern (Plans 45-09 / 45-10). Narrow scope: only
# online_payments/service.py → payments/models.py.
app.modules.online_payments.service -> app.modules.payments.models

# Phase 47 — online_payments/service.py needs format_actor_display for
# notification rendering. Mirrors Phase 45 memberships → users pattern.
app.modules.online_payments.service -> app.modules.users.display

# Phase 47 — email dispatcher walker gains new online_payments template registry.
app.integrations.email.dispatcher -> app.modules.online_payments.email_templates
```

**No new `core-not-depend-on-modules` exemptions.** The new Protocol slots live in `app/core/dependencies.py` (Protocol type only, no import of `app.modules.*`). The concrete implementations wired at `app/main.py` are in the composition root, which is already outside the `source_modules = app.core` scope.

---

## Integration Map: Client Clicks "Оплатить" → DM + Fiscal Receipt

```
CLIENT BROWSER                  SPORTZAL BACKEND                    ЮKASSA API
─────────────────               ──────────────────────────────────  ──────────────────

[1] POST /online-payments/memberships/{plan_id}/sell
    {idempotency_key, amount_kopecks, return_url, customer_email}
                         ↓
                 online_payments/router.py
                 → online_payments/service.create_online_payment()
                     ├─ INSERT online_payments (status='pending', idempotency_key)
                     ├─ call yookassa_client.create_payment(
                     │       idempotency_key=...,
                     │       receipt_items=[{membership plan name, amount, vat_code=1}],
                     │       customer={email}
                     │  )  ──────────────────────────────────────────► POST /v3/payments
                     │                                              ◄── {id, status:'pending',
                     │                                                   confirmation_url}
                     ├─ UPDATE online_payments SET yookassa_payment_id=..., status='pending'
                     ├─ audit.emit("online_payment_created", ...)
                     └─ COMMIT
                         ↓
                 return {confirmation_url} → 201

[2] Client browser REDIRECT to confirmation_url (ЮKassa hosted page)
    Client confirms payment on ЮKassa side

[3]             ЮKassa calls POST /api/v1/_internal/yookassa/webhook
                {type:"notification", event:"payment.succeeded", object:{id, status, ...}}
                         ↓
                 _internal/yookassa/router.py
                 → Depends(verify_yookassa_ip)  [IP allowlist gate]
                 → read raw body (already received)
                 → json.loads(body)
                 → online_payments/service.handle_webhook_event(event="payment.succeeded", yookassa_id=...)
                     ├─ SELECT online_payments WHERE yookassa_payment_id=...
                     │       [UPSERT-idempotent: if already 'succeeded', return 200 early]
                     ├─ _assert_can_transition(current='pending', next='succeeded')
                     ├─ call get_payment_recorder()(session, subject_kind='membership',
                     │       subject_id=plan_id, amount_kopecks=..., method='online',
                     │       received_by_user_id=SYSTEM_ACTOR_ID,
                     │       audit_actor=SYSTEM_ACTOR)
                     │   → payments/service.record_payment()  [appends to ledger]
                     │   → audit.emit("payment_recorded", method='online', ...)
                     ├─ UPDATE memberships SET status='active' via memberships Protocol slot
                     │       [OR: service.activate_membership_for_online_payment(session, ...)]
                     ├─ UPDATE online_payments SET status='succeeded', payment_id=<new payment row id>
                     ├─ audit.emit("online_payment_succeeded", ...)
                     ├─ INSERT fiscal_receipts (payment_id=..., kind='payment',
                     │       idempotency_key=f"{payment_id}:payment", status='sent')
                     │   [ЮKassa already has receipt data from step [1] — row captures local view]
                     ├─ INSERT payment_receipts (payment_id, channel='telegram', ...)
                     │   [idempotency row for DM]
                     ├─ INSERT payment_receipts (payment_id, channel='email', ...)
                     │   [idempotency row for email receipt]
                     └─ COMMIT
                              ↓ post-commit fanout (best-effort, payment NOT rolled back on failure)
                     ├─ pool.enqueue_job("dispatch_email", template="EMAIL_ONLINE_PAYMENT_SUCCESS", ...)
                     ├─ Telegram bot DM via PAYMENT_SUCCESS_DM constant
                     └─ return Response(200)   ← ЮKassa sees 200, stops retrying

[4] ARQ worker: dispatch_email task delivers email to client

[5] ЮKassa calls POST /api/v1/_internal/yookassa/webhook
    {event:"receipt.succeeded", object:{id, status:'succeeded', payment_id:...}}
                         ↓
                 → online_payments/service.handle_receipt_webhook(...)
                     ├─ SELECT fiscal_receipts WHERE payment_id=... AND kind='payment'
                     ├─ UPDATE fiscal_receipts SET status='succeeded'
                     ├─ audit.emit("fiscal_receipt_succeeded", ...)
                     └─ COMMIT
                         ↓
                 return Response(200)
```

**Refund flow (abbreviated):**

```
POST /online-payments/{id}/refund
  → online_payments/service.create_online_refund()
      ├─ call yookassa_client.create_refund(payment_id=yookassa_payment_id, ...)
      ├─ call get_payment_refunder()(session, subject_kind='membership', ...)
      │       → payments/service.issue_refund() [appends negative-amount row]
      ├─ INSERT fiscal_receipts (kind='refund', status='sent')
      ├─ audit.emit("online_refund_succeeded", ...)
      └─ COMMIT → DM + email fanout
```

---

## Build Order for Phases 47–53

| Phase | Deliverable | DB Dependencies | Notes |
|-------|-------------|----------------|-------|
| **47 — Bedrock** | `LOCKED_AUDIT_EVENTS` extended (9+ new events), `YooKassaSettings` config, Protocol slots declared in `core/dependencies.py`, `YooKassaClientProvider` + `FiscalReceiptDispatcher` slots; `app/integrations/yookassa/` skeleton (types + client + factory + webhook_verifier); 0033 sentinel migration | None (no table changes) | AST gate covers new event literals before any callsite; matches INFRA-15 discipline |
| **48 — ЮKassa Integration Adapter** | `integrations/yookassa/client.py` (real + sandbox), `factory.py` boot probe, `webhook_verifier.py` IP gate, tests for each transport path | None | Parallels Phase 42 (email client) |
| **49 — Online Sales Orchestrator** | `modules/online_payments/` full module: models (0034), repository, service `create_online_payment()`, router `POST /online-payments/memberships/{plan_id}/sell` + `POST /online-payments/pt-packages/{plan_id}/sell`; composition root wiring; `import-linter` update | 0034 `online_payments` | `record_payment(method='online')` is the only change to existing code path |
| **50 — Webhook + FSM** | `_internal/yookassa/router.py` with IP-verify Depends; `handle_webhook_event()` FSM; membership activation via new Protocol slot; `fiscal_receipts` table (0035); `fiscal_receipts` INSERT on succeeded; `INSERT payment_receipts` idempotency rows | 0035 `fiscal_receipts` | Fiscal receipt row created here (status='sent') because receipt data was bundled in payment creation |
| **51 — Fiscal Receipt FSM + Receipt Webhook** | `handle_receipt_webhook()` handler; `receipt.succeeded` / `receipt.canceled` event routing; `dispatch_fiscal_receipt` ARQ task with retry; `fiscal_receipt_succeeded` / `fiscal_receipt_failed` audit events | 0035 | ARQ task checks `fiscal_receipts.status` before calling ЮKassa — idempotent |
| **52 — Cross-Channel Notifications + Online Refunds** | `online_payments/notifications.py` Telegram DM constants; `online_payments/email_templates.py` new templates; `LOCKED_EMAIL_TEMPLATES` extended; dispatcher walker updated; `.importlinter` email dispatcher ignore added; `POST /online-payments/{id}/refund` endpoint; `handle_refund_webhook` | None | Mirrors Phase 45 (NOTIFY-11/12/13) pattern; same post-commit best-effort fanout |
| **53 — Milestone Verification** | Phase 36/40/46 discipline: operator runbook (curl + Telegram sandbox + cron sweeps); live-Postgres race tests (concurrent webhook double-delivery, duplicate `succeeded` events); DEFER-46-01 live RU email deliverability probe; DEFER-46-02 owner template countersign | None | Gate: 0/0 inline regressions above hard cap |

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Module boundary (sibling vs extend) | HIGH | Directly derived from existing `payments/` AST gate + CHECK constraints — codebase read |
| Protocol slot pattern | HIGH | 12 prior slots all follow identical pattern — direct code read |
| Webhook security (IP allowlist) | MEDIUM-HIGH | Official ЮKassa docs confirm IP allowlisting; no HMAC header documented. Project constraint in PROJECT.md that says "HMAC" is a common misconception — the constraint should be restated as IP-allowlist enforcement |
| ЮKassa payment FSM states | HIGH | Confirmed from official payment process docs |
| Fiscal receipt FSM | MEDIUM | ЮKassa docs say receipt data is bundled in payment request; exact `receipt.succeeded` / `receipt.canceled` event names need live testing in Phase 53 |
| 54-ФЗ receipt via ЮKassa hosted path | HIGH | ЮKassa handles OFD registration internally when receipt items bundled in payment creation — no separate `/receipts` call needed at payment time |
| ARQ task pattern for receipt dispatch | HIGH | Directly mirrors `dispatch_email` — same per-enqueue `_max_tries` / `_expires` pattern |
| import-linter additions | HIGH | Pattern established in Phase 45 for the same narrow cross-module access |

---

## Open Questions for Phase-Specific Research

1. **ЮKassa webhook IP range stability:** The published CIDRs should be treated as stable but need verification against the live dashboard at Phase 48 time. Storing them in config (not hardcoded) allows updates without code change.

2. **Receipt event names:** `receipt.succeeded` / `receipt.canceled` are inferred from the pattern. Verify exact event strings against ЮKassa webhook subscription docs during Phase 50 implementation.

3. **`SYSTEM_ACTOR_ID` for webhook-triggered `record_payment`:** Online payments have no human operator at `succeeded` time. The `payments` table has `received_by_user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT`. Either: (a) use the owner's user ID as a placeholder system actor (requires a seeded "system" user row), or (b) make `received_by_user_id` nullable for `method='online'` (migration 0034 must include this as a conditional nullable). Option (b) is architecturally cleaner but requires widening the NOT NULL constraint. Recommend option (b): nullable `received_by_user_id` for online-only payments, with a CHECK `(method='cash' AND received_by_user_id IS NOT NULL) OR method='online'`.

4. **Membership activation cross-module call:** The webhook handler in `online_payments/service.py` needs to activate a membership. This requires either a new Protocol slot `MembershipActivator` (wired at composition root) OR the FK back-reference through `online_payments.subject_id` + subject_kind to call the memberships module indirectly. A `MembershipActivator` Protocol slot follows established precedent and keeps the import contract clean.

5. **`DEFER-46-01/02` carry-out in Phase 53:** The v1.6 deferred items (live RU email deliverability probe + owner 15-template countersign) should run as the first task of Phase 53 before the v1.7 operator scenarios, since the email channel is a transport dependency for online payment receipts.
