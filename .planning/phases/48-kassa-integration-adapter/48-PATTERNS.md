# Phase 48: ЮKassa Integration Adapter — Pattern Map

**Mapped:** 2026-05-21
**Files analyzed:** 16 (10 new, 6 modified)
**Analogs found:** 16 / 16 (100% — every Phase 48 file has a direct in-repo template)

> Read-only mapping pass. All excerpts below are concrete code-with-line-numbers
> ready for the planner to hand to the executor. Phase 48 is structurally a
> mirror of the v1.6 email integration (Phase 42) with **three** documented
> divergences:
> 1. **Long-lived `httpx.AsyncClient`** vs email's per-call `aioboto3.Session`
>    (D-48-06).
> 2. **Non-fatal boot probe** vs email's fail-fast `RuntimeError`
>    (D-48-14, SC2 — degraded mode).
> 3. **5-variant classification** (`ok | validation_error | transient_error |
>    permanent_error`) vs email's `ok | blocked | transient_error |
>    permanent_error` (D-48-04 — `validation_error` replaces `blocked` because
>    ЮKassa 422 is a separate concern from recipient-block).

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/integrations/yookassa/types.py` (NEW) | DTO module | request-response | `app/integrations/email/types.py` | **exact** |
| `app/integrations/yookassa/client.py` (NEW) | integration client | request-response | `app/integrations/email/client.py` (`EmailClient`) | **exact (role)**, **strong (data flow)** — adjust exception taxonomy |
| `app/integrations/yookassa/factory.py` (NEW) | async factory + boot probe | startup-time RPC | `app/integrations/email/factory.py:build_email_client` | **exact (shape)**, **diverge on failure semantics** (D-48-14) |
| `app/integrations/yookassa/receipt.py` (NEW) | pure helper + enums | transform | `app/integrations/yookassa/_money.py` (module shape) + `app/core/audit_payloads.py` (Literal usage) | role-match (no exact analog for "wire-shape dict builder" — closest is `_money.py` underscore-helper convention) |
| `app/integrations/yookassa/webhook_verifier.py` (MODIFIED — fill body) | request-response middleware | request-response | self (Phase 47 skeleton's own docstring is the locked contract) + `app.core.audit.audit_emit` callers | role-match |
| `app/integrations/yookassa/__init__.py` (MODIFIED — exports) | package barrel | n/a | `app/integrations/email/__init__.py` (if present) — else module docstring of existing `app/integrations/yookassa/__init__.py` | role-match |
| `app/main.py` (MODIFIED — composition root) | composition root | startup wiring | `app/main.py` lines 261–296 (existing yookassa stub wiring + email factory call pattern) | **exact (self-modifying)** |
| `app/workers/__init__.py` (MODIFIED — `on_startup`) | ARQ composition root | startup wiring | `app/workers/__init__.py` lines 240–294 (existing yookassa stub wiring) | **exact (self-modifying)** |
| `tests/integrations/yookassa/conftest.py` (NEW) | test fixture module | test-time mock | `tests/unit/integrations/email/test_client.py` envelope helper (closest) + respx docs (external) | role-match (no respx precedent in repo — Phase 48 introduces it) |
| `tests/integrations/yookassa/_responses/*.json` (NEW × 5) | test fixture data | static data | n/a (first JSON-fixture directory in the project) | no analog — fresh convention |
| `tests/integrations/yookassa/test_client.py` (NEW) | adapter unit tests | test-time | `tests/unit/integrations/email/test_client.py` | **exact** |
| `tests/integrations/yookassa/test_factory.py` (NEW) | factory unit tests | test-time | `tests/unit/integrations/email/test_factory.py` | **exact** |
| `tests/integrations/yookassa/test_receipt.py` (NEW) | pure-helper unit tests | test-time | `tests/unit/integrations/yookassa/test_money.py` (if present; else `_money` test module pattern) | role-match |
| `tests/integrations/yookassa/test_webhook_verifier.py` (NEW) | verifier unit tests | test-time | `tests/unit/test_locked_yookassa_constants_ast.py` (same module) + FastAPI `Request`-mocking precedent in repo | role-match |
| `tests/unit/test_locked_yookassa_constants_ast.py` (MODIFIED — +2 funcs) | AST gate | static analysis | `tests/unit/test_locked_email_templates_ast.py` + same file's existing `test_non_literal_verifier_arg_is_rejected` | **exact (self-extending)** |
| `pyproject.toml` (MODIFIED — add `respx`) | dev dep declaration | n/a | `apps/backend/pyproject.toml` lines 26–35 (existing `[dependency-groups] dev` block) | trivial |

---

## Pattern Assignments

### `app/integrations/yookassa/types.py` (DTO module, request-response)

**Analog:** `app/integrations/email/types.py` (full file, 82 lines — single Read covered it all).

**Module docstring pattern** (email/types.py:1–18):
```python
"""Email transport DTOs — locked at Phase 42 D-42-16 (envelope) + D-42-13 (result classification).

Two frozen dataclasses form the entire typed surface of the email-transport boundary:
...
- ``EmailSendResult`` is the typed outcome the provider adapter returns ...
  ``classification`` is a closed ``Literal`` so downstream code ... can switch on it
  without runtime guards leaking free-form strings into the audit chain (D-42-13).

Shape mirrors ``app.integrations.telegram.sender.SendResult`` ...:
frozen dataclass with classified failure modes; transport errors are values,
not exceptions, so handler atomicity is observable without try/except gymnastics.
"""
```
**Apply:** Same docstring shape for `yookassa/types.py` citing D-48-03, D-48-04, D-48-05.
Must include the explicit "No SDK types cross the boundary" note (D-48-05) and the
"cloudpickle-safe (primitives + UUID + Decimal only)" guarantee for future ARQ enqueue.

**Imports** (email/types.py:20–24) — replicate verbatim (Decimal added for amount field):
```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID
```
Plus `from decimal import Decimal` only if amount fields are stored as Decimal
rather than int kopecks. Per Pitfall 5 + D-48-04 the result amount should be
**stored as int kopecks** (converted via `yookassa_to_kopecks` at parse time);
in that case Decimal is NOT imported here and `int` is used.

**Frozen-dataclass + Literal classification pattern** (email/types.py:56–82) — the
exact shape Phase 48 replicates for all four result classes:
```python
@dataclass(frozen=True)
class EmailSendResult:
    """Outcome of one transport attempt (D-42-13).

    ``classification`` is the closed taxonomy the dispatcher writes to
    ``email_send_log.status`` and that downstream retry / circuit-breaker logic
    switches on:

    - ``ok``: provider accepted the message (2xx). ``provider_message_id`` is
      populated; ``error`` is None.
    - ``blocked``: provider rejected the recipient permanently ... DO NOT retry.
    - ``transient_error``: provider returned 5xx / network failure / 429. ARQ
      should retry per its backoff schedule.
    - ``permanent_error``: provider returned 4xx other than ``blocked`` ...
      DO NOT retry — operator alert.
    """

    ok: bool
    classification: Literal["ok", "blocked", "transient_error", "permanent_error"]
    provider_message_id: str | None = None
    error: str | None = None
```

**Adaptation for `YooKassaPaymentResult` / `YooKassaRefundResult` / `YooKassaReceiptResult`:**
- Replace `Literal["ok", "blocked", "transient_error", "permanent_error"]`
  with `Literal["ok", "validation_error", "transient_error", "permanent_error"]`
  per D-48-04.
- Replace `provider_message_id: str | None` with the success-payload fields
  (`payment_id: str | None`, `status: Literal["pending","succeeded","canceled"] | None`,
  `confirmation_url: str | None`, `amount_kopecks: int | None`, etc.) — all
  defaulted to `None` so failure variants carry only `error_code: str | None`
  + `http_status: int | None`.
- `YooKassaReceiptResult`: per D-48-03 declared empty/placeholder for Phase 48
  (Phase 51 may add `receipt_id` if `POST /v3/receipts` lands).

**Adaptation for `YooKassaWebhookEvent`** (no email-side analog — closest
shape is `EmailEnvelope` itself which lacks `classification`):
- Frozen dataclass — fields: `event: Literal["payment.succeeded","payment.canceled","refund.succeeded"]`,
  `object_id: UUID` (parsed from string), `object_payload: dict[str, Any]`
  (kept as dict because the inner ЮKassa object varies per event type;
  Phase 50 webhook handler does the typed re-fetch), `received_at: datetime`,
  `correlation_id: UUID | None` (caller-supplied if upstream `Idempotence-Key`
  echoes back).
- NO `classification` field — this is an inbound event, not a transport result.

---

### `app/integrations/yookassa/client.py` (integration client, request-response)

**Analog:** `app/integrations/email/client.py` (full file, 195 lines — single Read covered it all).

**Module docstring** (email/client.py:1–26) — adapt with:
- Replace "aioboto3 Yandex Cloud Postbox SES-V2 adapter" with "async httpx ЮKassa REST adapter".
- **Add divergence note**: `httpx.AsyncClient` is **long-lived** (constructed
  once in factory, closed in lifespan teardown) — opposite of `aioboto3.Session`
  per-call factory pattern (D-48-06).
- Add layer invariant verbatim (email/client.py:23–26): `MUST NOT import any
  module under the per-domain modules package (import-linter contract 3)`.

**Imports** (email/client.py:28–38) — Phase 48 adaptation:
```python
# Email pattern (lines 28–38):
from __future__ import annotations

from typing import Any
from uuid import uuid4

import structlog
from botocore.config import Config
from botocore.exceptions import ClientError

from app.integrations.email.types import EmailEnvelope, EmailSendResult
```
**Apply for yookassa/client.py:**
```python
from __future__ import annotations

import json
from typing import Any, Final
from uuid import UUID

import httpx
import structlog

from app.integrations.yookassa._money import kopecks_to_yookassa, yookassa_to_kopecks
from app.integrations.yookassa.settings import YooKassaSettings
from app.integrations.yookassa.types import (
    YooKassaPaymentResult,
    YooKassaRefundResult,
)
```

**Locked header constant** (D-48-12 — no email analog; net-new but lock with
module-level `Final`):
```python
# Per ЮKassa interaction spec: header name has ONE 't' — "Idempotence-Key".
# Do NOT rename to "Idempotency-Key" (the standards-conformant spelling)
# — ЮKassa silently rejects the standard form on POST /v3/payments.
IDEMPOTENCE_KEY_HEADER: Final[str] = "Idempotence-Key"
```

**Constructor pattern — DIVERGE FROM EMAIL** (email/client.py:48–67 holds a
session factory; Phase 48 holds the live AsyncClient + auth + base URL):
```python
# Email pattern (lines 48–67):
class EmailClient:
    def __init__(self, *, session: Any, endpoint_url: str, from_address: str) -> None:
        self._session = session
        self._endpoint_url = endpoint_url
        self._from_address = from_address
```
**Apply for `YooKassaClient.__init__`:**
```python
class YooKassaClient:
    def __init__(
        self,
        *,
        http: httpx.AsyncClient,   # long-lived, owned by factory (D-48-06)
        settings: YooKassaSettings,
    ) -> None:
        self._http = http
        self._settings = settings

    async def aclose(self) -> None:
        """Close the underlying httpx.AsyncClient (FastAPI lifespan teardown)."""
        await self._http.aclose()
```

**Classified try/except chain pattern** (email/client.py:69–171 — the canonical
"never re-raises transport errors" shape Phase 48 replicates):
```python
async def send_email(self, envelope: EmailEnvelope) -> EmailSendResult:
    """Send one envelope. NEVER re-raises — every outcome is a value.

    Classification chain (mirror of ``send_otp_dm`` outbound-boundary
    pattern, expanded for the richer SES-V2 failure surface):

    - ``ClientError`` Code ∈ ``_BLOCKED_ERROR_CODES`` → ``blocked``
    - ``ClientError`` HTTP 5xx → ``transient_error``
    - ``ClientError`` HTTP 4xx (non-blocked) → ``permanent_error``
    - any other ``Exception`` → ``transient_error``
    - success → ``ok`` with ``MessageId`` populated as ``provider_message_id``
    """
    try:
        async with self._session.client(...) as client:
            response = await client.send_email(...)
        ...
        return EmailSendResult(ok=True, classification="ok", provider_message_id=message_id)
    except ClientError as exc:
        # extract code + http_status, then classify
        if code in _BLOCKED_ERROR_CODES:
            return EmailSendResult(ok=False, classification="blocked", error=str(exc))
        if isinstance(http_status, int) and http_status >= 500:
            return EmailSendResult(ok=False, classification="transient_error", error=str(exc))
        return EmailSendResult(ok=False, classification="permanent_error", error=str(exc))
    except Exception as exc:
        return EmailSendResult(ok=False, classification="transient_error", error=str(exc))
```

**Apply for `YooKassaClient.create_payment` (and `get_payment`, `create_refund`,
`get_refund` analogously):**
- Replace `ClientError` chain with: `httpx.HTTPStatusError` → branch on
  `exc.response.status_code` (`422 → validation_error`, `>=500 → transient_error`,
  other 4xx → `permanent_error`).
- Add `httpx.TimeoutException` → `transient_error`.
- Add `httpx.RequestError` (network) → `transient_error`.
- Add `json.JSONDecodeError` → `permanent_error` (malformed body).
- Add catch-all `Exception` → `transient_error` (mirrors email/client.py:159–171).
- `await self._http.post("/payments", json=body, headers={IDEMPOTENCE_KEY_HEADER: str(idempotency_key)})`.
- `response.raise_for_status()` inside the try so 4xx/5xx land in
  `HTTPStatusError`.
- Parse `response.json()` and convert `amount.value` via `yookassa_to_kopecks`
  before constructing `YooKassaPaymentResult(classification="ok", ...)`.

**Structlog event-name pattern** (email/client.py:102–171):
- `email_send_ok` / `email_send_blocked` / `email_send_transient_error` /
  `email_send_permanent_error`.
- Apply: `yookassa_create_payment_ok` / `yookassa_create_payment_validation_error`
  / `yookassa_create_payment_transient_error` / `yookassa_create_payment_permanent_error`
  (one log line per outcome variant; `key=value` structured fields).
  NO secret leakage: never log `idempotency_key`'s body or any
  `settings.secret_key.get_secret_value()` content (mirror email's
  no-credential-logging discipline implicit in the existing code).

**Method signature shape:**
```python
async def create_payment(
    self,
    *,
    amount_kopecks: int,
    description: str,
    receipt_items: list[dict[str, Any]],   # caller assembles via build_receipt_item()
    customer_email: str,
    idempotency_key: UUID,                  # caller-owned per D-48-11
    metadata: dict[str, str] | None = None, # phase 50 correlation hook
) -> YooKassaPaymentResult: ...

async def get_payment(self, payment_id: str) -> YooKassaPaymentResult: ...
async def create_refund(self, *, payment_id: str, amount_kopecks: int,
                        idempotency_key: UUID,
                        receipt_items: list[dict[str, Any]] | None = None,
                        ) -> YooKassaRefundResult: ...
async def get_refund(self, refund_id: str) -> YooKassaRefundResult: ...
```

**Confirmation injection** (Claude's Discretion in CONTEXT.md): `create_payment`
adds `confirmation={"type":"redirect","return_url": str(settings.return_url)}`
to every request body — Phase 49 orchestrator does NOT pass it.

---

### `app/integrations/yookassa/factory.py` (async factory + boot probe)

**Analog:** `app/integrations/email/factory.py` (full file, 112 lines — single Read covered it all).

**Module docstring** (email/factory.py:1–25) — adapt:
- Keep the LOCKED async-signature rationale verbatim (lines 8–18 — the
  "wrapping in a sync-from-async loop driver inside ARQ's `on_startup` raises
  RuntimeError" reasoning applies identically to Phase 48).
- **Add divergence note**: per D-48-06, `httpx.AsyncClient` is **NOT**
  uncached — the factory returns a freshly constructed client that the
  lifespan owns for the process lifetime. This is the OPPOSITE of the
  email factory's "fresh client per call" discipline (email/factory.py:19–22).
- **Add divergence note**: per D-48-14 / SC2, probe failure is **NON-FATAL**
  — the factory still returns the constructed `YooKassaClient`; only the
  probe outcome is logged at INFO/WARNING. This is the OPPOSITE of email's
  `RuntimeError` fail-fast (email/factory.py:96–99).

**Imports** (email/factory.py:27–35) — Phase 48 adaptation:
```python
# Email pattern:
import aioboto3
import structlog
from botocore.config import Config

from app.core.config import EmailProviderSettings
from app.integrations.email.client import EmailClient, SandboxEmailClient
```
**Apply:**
```python
import httpx
import structlog

from app.integrations.yookassa.client import YooKassaClient
from app.integrations.yookassa.settings import YooKassaSettings
```

**Factory body pattern** (email/factory.py:39–111) — the LOCKED shape Phase 48
replicates with the documented divergences:
```python
# Email pattern signature + body skeleton:
async def build_email_client(
    *, settings: EmailProviderSettings
) -> EmailClient | SandboxEmailClient:
    """Construct a fresh email client per call (no caching).

    Sandbox path (D-42-29): when ``settings.provider == 'sandbox'`` ...
    return a ``SandboxEmailClient`` stub ...

    Non-sandbox path (D-42-30): construct an ``aioboto3.Session`` ...
    Boot-time, ALSO call the SES-V2 ``get_email_identity`` endpoint ...
    failure raises ``RuntimeError`` at app boot ...
    """
    if settings.provider == "sandbox" or settings.sandbox_mode:
        _log.info("email_client_built", provider="sandbox", ...)
        return SandboxEmailClient()
    ...
    session = aioboto3.Session(...)
    # D-42-30: boot-time /domains probe. Fails fast on unverified sender domain.
    async with session.client("sesv2", ...) as probe_client:
        resp = await probe_client.get_email_identity(EmailIdentity=settings.from_domain)
    status = resp.get("VerificationStatus") if isinstance(resp, dict) else None
    if status != "Success":
        raise RuntimeError(...)
    _log.info("email_client_built", ...)
    return EmailClient(session=session, ...)
```

**Apply for `build_yookassa_client`** with divergences:
```python
async def build_yookassa_client(
    *, settings: YooKassaSettings,
) -> YooKassaClient:
    """Construct the process-wide YooKassaClient (D-48-06) and run a
    non-fatal /v3/me probe (D-48-13/14).

    DIVERGENCE FROM email factory:
      - The httpx.AsyncClient returned here is LONG-LIVED (not per-call):
        the FastAPI lifespan teardown / ARQ on_shutdown closes it via
        client.aclose() (D-48-06).
      - Probe failure is NON-FATAL (D-48-14, SC2): returns the constructed
        client regardless; only the probe result is logged. Email's
        fail-fast RuntimeError discipline does NOT apply — operator
        runbook covers the degraded-mode signal.
    """
    http = httpx.AsyncClient(
        base_url="https://api.yookassa.ru/v3/",  # D-48-08 — sandbox uses same URL
        auth=httpx.BasicAuth(
            username=str(settings.shop_id),
            password=settings.secret_key.get_secret_value(),
        ),
        timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),  # D-48-09
        headers={"User-Agent": "Sportzal/1.7 ЮKassa-Adapter"},  # Claude's Discretion
    )
    # D-48-13: boot probe via GET /v3/me — single attempt, no retry (D-48-15).
    try:
        resp = await http.get("me", timeout=5.0)
        resp.raise_for_status()
        body = resp.json()
        probe_shop_id = body.get("account_id") if isinstance(body, dict) else None
        if probe_shop_id is not None and str(probe_shop_id) != str(settings.shop_id):
            _log.warning(
                "yookassa_boot_probe",
                ok=False,
                reason="shop_id_mismatch",
                expected=str(settings.shop_id),
                got=str(probe_shop_id),
            )
        else:
            _log.info("yookassa_boot_probe", ok=True, shop_id=str(settings.shop_id))
    except Exception as exc:
        # D-48-14: NON-FATAL — log + continue. Caller still receives a usable client.
        _log.warning(
            "yookassa_boot_probe",
            ok=False,
            reason=type(exc).__name__,
            error=str(exc),
        )
    return YooKassaClient(http=http, settings=settings)
```

**Async-shape lock test** (email/test_factory.py:21–28 — the
`inspect.iscoroutinefunction` test must be replicated):
```python
def test_build_yookassa_client_is_coroutine_function() -> None:
    """LOCKED: factory MUST be ``async def`` so callers can await naturally.
    Sync def + asyncio.run inside ARQ's on_startup ... raises RuntimeError."""
    assert inspect.iscoroutinefunction(build_yookassa_client)
```

---

### `app/integrations/yookassa/receipt.py` (pure helper + 3 enums)

**Analog:** no exact codebase analog for the dict-builder shape. Closest is
`app/integrations/yookassa/_money.py` (module-shape — pure helpers, no class).
For the Literal/StrEnum lock pattern, the analog is `LOCKED_AUDIT_EVENTS`
tuples in `app/core/audit.py` plus the existing `Literal["new", "duplicate_blocked"]`
pattern in `app/core/audit_payloads.py:914`.

**Module docstring** (mirror `_money.py` lines 1–21 — the "Phase X REQ-Y" +
underscore-not-applicable note + invariants list shape):
```python
"""ЮKassa receipt-item builder + 54-ФЗ enum constants.

Phase 48 ADAPTER-04 (D-48-16/17/18). Returns a ``dict[str, Any]`` shaped
per ЮKassa wire format — NOT a typed model — because Phase 49 callers
concatenate items into a list inside the payment-create body, and ЮKassa's
receipt nested object accepts dicts directly (STACK.md §6 lines 252–258).

Three enums lock the 54-ФЗ tag values:
    PaymentSubject (StrEnum) — tag 1212; one member in v1.7 (service).
    PaymentMode (StrEnum)    — tag 1214; two members (full_payment, full_prepayment).
    VatCode (IntEnum)        — tag 1199; six members enumerated from ЮKassa docs.

AST gate (test_locked_yookassa_constants_ast.py — extended in Phase 48 per
D-48-18): every ``build_receipt_item(payment_subject=..., payment_mode=...)``
callsite MUST pass literal enum members, never variables / f-strings.

Layer invariant: lives at integrations layer — MUST NOT import from
app.modules.* (importlinter contract integrations-not-depend-on-modules).
"""
```

**Imports + currency lock:**
```python
from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Any, Final

from app.integrations.yookassa._money import kopecks_to_yookassa

CURRENCY: Final[str] = "RUB"  # Claude's Discretion — no multi-currency in v1.7
_MAX_DESCRIPTION_LEN: Final[int] = 128  # ЮKassa enforces (specifics §)
```

**Enum pattern** — exactly per D-48-17:
```python
class PaymentSubject(StrEnum):
    """ЮKassa тег 1212 — признак предмета расчёта (D-48-17).

    Sportzal v1.7 sells gym memberships and PT-package services only — one
    member. Adding new members requires owner sign-off + AST-gate test
    extension (D-48-18).
    """

    SERVICE = "service"


class PaymentMode(StrEnum):
    """ЮKassa тег 1214 — признак способа расчёта (D-48-17).

    ``FULL_PREPAYMENT`` for online membership sales paid before activation
    (most common). ``FULL_PAYMENT`` for at-point-of-consumption (drop-in
    classes, PT sessions paid at the desk). Phase 49 orchestrator picks
    per sale type.
    """

    FULL_PAYMENT = "full_payment"
    FULL_PREPAYMENT = "full_prepayment"


class VatCode(IntEnum):
    """ЮKassa тег 1199 — ставка НДС (D-48-17). Full 54-ФЗ enumeration.

    Caller passes the code; ``build_receipt_item`` defaults to
    ``YooKassaSettings.default_vat_code`` if omitted.
    """

    VAT_NONE = 1     # без НДС
    VAT_0 = 2        # НДС 0%
    VAT_10 = 3       # НДС 10%
    VAT_20 = 4       # НДС 20%
    VAT_10_110 = 5   # НДС 10/110
    VAT_20_120 = 6   # НДС 20/120
```

**Builder function** (specifics §, lines 211–219 of CONTEXT.md):
```python
def build_receipt_item(
    *,
    description: str,
    amount_kopecks: int,
    payment_subject: PaymentSubject,
    payment_mode: PaymentMode,
    vat_code: VatCode,
    quantity: str = "1.00",
) -> dict[str, Any]:
    """Assemble one 54-ФЗ receipt item per ЮKassa wire format (D-48-16).

    Returns a plain dict (not a typed model) so callers can concatenate
    into ``receipt.items`` lists without unwrap/repack churn.

    Raises:
        ValueError: if description exceeds 128 chars (ЮKassa rejects).
    """
    if len(description) > _MAX_DESCRIPTION_LEN:
        raise ValueError(
            f"description must be ≤ {_MAX_DESCRIPTION_LEN} chars, got {len(description)}"
        )
    return {
        "description": description,
        "quantity": quantity,
        "amount": {"value": kopecks_to_yookassa(amount_kopecks), "currency": CURRENCY},
        "vat_code": int(vat_code),
        "payment_mode": payment_mode.value,
        "payment_subject": payment_subject.value,
    }
```

---

### `app/integrations/yookassa/webhook_verifier.py` (MODIFIED — fill body)

**Analog:** the function's own Phase 47 module docstring is the locked contract
(`webhook_verifier.py:1–25`). For the `audit.emit` callsite shape, see
`app/core/audit_payloads.py:894–914` (`YookassaWebhookReceivedPayload`).

**Existing skeleton to replace** (`webhook_verifier.py:45–59`):
```python
async def verify_yookassa_ip(request: Request) -> None:
    """... Phase 47 skeleton — raises NotImplementedError. Phase 48 fills the
    body per the contract documented in the module docstring above ..."""
    raise NotImplementedError(
        "verify_yookassa_ip impl lands in Phase 48 ADAPTER-05 — ..."
    )
```

**Apply (Phase 48 body)** — per D-48-19 contract steps:
```python
import ipaddress
from typing import Final

from fastapi import HTTPException, Request

from app.core.audit import audit_emit  # use the project's canonical emitter
from app.integrations.yookassa.settings import YooKassaSettings

# Module-level singleton settings instance (mirrors how email/factory reads settings).
# If a DI-injected variant is preferred, Phase 48 can switch to Depends() —
# but the module-level constant matches the way YOOKASSA_TRUSTED_IPS is consumed.

async def verify_yookassa_ip(request: Request) -> None:
    """Webhook IP allowlist check (Phase 48 ADAPTER-05; D-48-19).

    Order of checks:
      1. Sandbox bypass (D-47-07) — return immediately.
      2. Extract source IP from request.client.host. The X-Forwarded-For
         toggle is a Phase 50 concern — TODO marker below.
      3. Compare against YOOKASSA_TRUSTED_IPS via ipaddress.ip_network.
      4. On miss: emit yookassa_webhook_received audit (idempotency_outcome
         = "rejected_ip") + raise HTTPException 403.
    """
    settings = _get_settings()  # YooKassaSettings instance
    if settings.sandbox:
        return  # D-47-07 sandbox bypass

    # TODO Phase 50: when reverse-proxy topology is locked, honour
    # X-Forwarded-For (first hop, comma-split, strip) gated by a
    # TRUSTED_PROXY_HEADER_ENABLED config flag.
    source_host = request.client.host if request.client else None
    if source_host is None:
        await _emit_rejected(request, source_ip="(none)")
        raise HTTPException(status_code=403, detail="forbidden_ip")

    try:
        source_ip = ipaddress.ip_address(source_host)
    except ValueError:
        await _emit_rejected(request, source_ip=source_host)
        raise HTTPException(status_code=403, detail="forbidden_ip")

    for cidr in YOOKASSA_TRUSTED_IPS:
        try:
            if source_ip in ipaddress.ip_network(cidr):
                return
        except ValueError:
            continue  # malformed CIDR — defensive; AST gate already guards literal shape

    await _emit_rejected(request, source_ip=str(source_ip))
    raise HTTPException(status_code=403, detail="forbidden_ip")
```

**Audit emission helper** (use the existing payload class —
`audit_payloads.py:894–914`):
```python
async def _emit_rejected(request: Request, *, source_ip: str) -> None:
    """Audit-emit yookassa_webhook_received with idempotency_outcome rejected_ip."""
    # NOTE: idempotency_outcome Literal in YookassaWebhookReceivedPayload is
    # currently ["new", "duplicate_blocked"]. Phase 48 must extend it to
    # include "rejected_ip" OR the planner picks an alternative shape
    # (e.g., a separate payload class). This is a planning-level decision —
    # the CONTEXT.md D-48-19 text uses "rejected_ip"; the existing payload
    # Literal must be widened to match.
    await audit_emit(
        event="yookassa_webhook_received",
        resource_type="yookassa_webhook",
        payload={
            "audit_correlation_id": None,
            "event_type": "(unknown — body not parsed)",
            "object_id": "(unknown — body not parsed)",
            "idempotency_outcome": "rejected_ip",
        },
    )
```

**Planner note:** The Literal extension on `YookassaWebhookReceivedPayload.idempotency_outcome`
(from `["new", "duplicate_blocked"]` to `["new", "duplicate_blocked", "rejected_ip"]`)
is a Phase 48 sub-task because the verifier emits before any "new" classification
makes sense. Confirm with executor that AST gate test_audit_taxonomy.py does
not reject the widening.

---

### `app/main.py` (MODIFIED — composition root)

**Analog:** the file's own existing Phase 47 wiring at lines 261–296 (read above)
plus the email factory call pattern at workers/__init__.py:272
(`ctx["email_client"] = await build_email_client(settings=settings_local.email)`).

**Existing stub registration to replace** (`app/main.py:293`):
```python
register_yookassa_client_provider(yookassa_client_provider_noop_stub)
```

**Apply — Phase 48 wiring shape:**
```python
# Phase 48 ADAPTER-02 + ADAPTER-03 — replace the no-op stub with the real
# client. The httpx.AsyncClient is long-lived (D-48-06); the FastAPI
# lifespan teardown closes it via yookassa_client.aclose().
from app.integrations.yookassa.factory import build_yookassa_client
from app.integrations.yookassa.settings import YooKassaSettings

# Inside create_app() — replace the Phase 47 no-op stub line:
yookassa_settings = YooKassaSettings()
yookassa_client = await build_yookassa_client(settings=yookassa_settings)
# Wrap the client in a provider callable (Protocol expects ``async __call__() -> Any``):
async def _yookassa_client_provider() -> Any:
    return yookassa_client
register_yookassa_client_provider(_yookassa_client_provider)
```

**Lifespan teardown extension** (`combined_lifespan` at main.py:97–122):
- Add `yookassa_client` to the `yield`-scope so its `aclose()` runs in the
  `finally` block alongside `arq_pool.aclose()`.

**Planner note:** `create_app()` is currently sync (`def`). Because
`build_yookassa_client` is `async def`, the construction must move into
`combined_lifespan` (which IS async) — mirrors how `arq_pool` is created
in the lifespan rather than `create_app`. This is the SAME pattern as
email's `register_arq_pool(arq_pool)` lifespan timing (main.py:117–118).

Concretely: register a callable that *resolves the client lazily* via
`app.state.yookassa_client = await build_yookassa_client(...)` inside the
lifespan, and the provider closure reads from `app.state` at call time.
Mirrors `set_auth_redis_factory(lambda: app.state.redis)` at main.py:279.

---

### `app/workers/__init__.py` (MODIFIED — `on_startup`)

**Analog:** the file's own existing yookassa wiring at lines 240–294 (read above)
plus the email factory await pattern at line 272.

**Existing stub registration to replace** (workers/__init__.py:284):
```python
register_yookassa_client_provider(yookassa_client_provider_noop_stub)
```

**Apply — mirror the email pattern at workers/__init__.py:272:**
```python
from app.integrations.yookassa.factory import build_yookassa_client
from app.integrations.yookassa.settings import YooKassaSettings

settings_local = _get_settings_local()
# REG-29-03 double-wire — same byte-equal symbol pattern as the email
# dispatcher; here it's a closure over the worker-local client instance.
yookassa_settings = YooKassaSettings()
ctx["yookassa_client"] = await build_yookassa_client(settings=yookassa_settings)

async def _yookassa_client_provider() -> Any:
    return ctx["yookassa_client"]

register_yookassa_client_provider(_yookassa_client_provider)
```

**Teardown extension (`on_shutdown` at workers/__init__.py:297+):**
```python
yookassa_client = ctx.get("yookassa_client")
if yookassa_client is not None:
    await yookassa_client.aclose()
```

---

### `tests/integrations/yookassa/conftest.py` (NEW — 6 respx fixtures + 1 dict)

**Analog:** no respx precedent in repo. Closest reference is the
specifics § skeleton in CONTEXT.md lines 221–229. For pytest-fixture
async shape, see `tests/conftest.py:190` and `tests/unit/integrations/email/test_client.py:39–48`
(the `@pytest.mark.asyncio` + envelope helper pattern).

**Apply — pattern Phase 48 ships:**
```python
"""ЮKassa adapter test fixtures — Phase 48 ADAPTER-06 (D-48-22..24).

Six canonical fixtures + one dict fixture covering the wire shapes Phase 48's
test_client / test_factory and all Phase 49/50/51 downstream tests reuse.

JSON response bodies live in `_responses/<name>.json` so docs-driven shape
updates don't churn Python code (D-48-23).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

_RESPONSES_DIR = Path(__file__).parent / "_responses"

def _load(name: str) -> dict[str, Any]:
    return json.loads((_RESPONSES_DIR / f"{name}.json").read_text(encoding="utf-8"))

@pytest.fixture
def yookassa_create_payment_success() -> respx.MockRouter:
    with respx.mock(base_url="https://api.yookassa.ru/v3", assert_all_called=False) as r:
        r.post("/payments").mock(
            return_value=httpx.Response(200, json=_load("create_payment_success"))
        )
        yield r

# ... five more fixtures mirror this shape ...

@pytest.fixture
def yookassa_webhook_payload() -> dict[str, Any]:
    """Canonical payment.succeeded webhook body — NOT a respx route (D-48-22 #6)."""
    return _load("webhook_payment_succeeded")
```

**Required JSON files in `_responses/`** (D-48-23):
- `create_payment_success.json` — 200 + `status:"pending"` + `confirmation.confirmation_url`
- `create_payment_422.json` — 422 + ЮKassa-shaped error body
- `get_payment_pending.json` — 200 + `status:"pending"`
- `get_payment_succeeded.json` — 200 + `status:"succeeded"` + `receipt_registration:"succeeded"`
- `create_refund_success.json` — 200 + refund body
- `webhook_payment_succeeded.json` — `event:"payment.succeeded"` + `object.id` (UUID)
  + `object.status:"succeeded"` + `object.amount` + `object.receipt_registration:"succeeded"`
  + `object.metadata` (Phase 50 correlation hook)

---

### `tests/integrations/yookassa/test_client.py` (NEW)

**Analog:** `tests/unit/integrations/email/test_client.py` lines 1–80 (read above).

**Envelope helper pattern** (email/test_client.py:25–33) — adapt as a payment
input helper:
```python
# Email pattern:
def _envelope() -> EmailEnvelope:
    return EmailEnvelope(
        to="user@example.com", subject="Тема", html="<p>hi</p>",
        text="hi-body-text-with-enough-chars-to-preview",
        template_id="EMAIL_OTP_LOGIN", audit_correlation_id=uuid4(),
    )
```
**Apply for Phase 48:** a `_payment_kwargs()` helper that yields the kwargs
dict for `client.create_payment(...)` — single UUID idempotency key, valid
description, one `build_receipt_item` item.

**Test cases** (mirror email test 39–48 sandbox shape + the classification
chain coverage at email/test_client.py:71+):
```python
async def test_create_payment_ok(yookassa_create_payment_success, yookassa_client):
    result = await yookassa_client.create_payment(**_payment_kwargs())
    assert result.classification == "ok"
    assert result.payment_id is not None
    assert result.confirmation_url.startswith("https://yoomoney.ru/checkout/")

async def test_create_payment_422_classifies_as_validation_error(
    yookassa_create_payment_422, yookassa_client,
):
    result = await yookassa_client.create_payment(**_payment_kwargs())
    assert result.classification == "validation_error"
    assert result.http_status == 422
    # Never re-raises — locked SC1 invariant.

async def test_create_payment_500_classifies_as_transient_error(...): ...
async def test_create_payment_timeout_classifies_as_transient_error(...): ...
async def test_create_payment_malformed_json_classifies_as_permanent_error(...): ...
async def test_create_payment_sets_idempotence_key_header(...): ...
async def test_create_payment_injects_return_url_confirmation(...): ...
```

---

### `tests/integrations/yookassa/test_factory.py` (NEW)

**Analog:** `tests/unit/integrations/email/test_factory.py` (full file, 52 lines).

**Async-shape lock test** (email/test_factory.py:21–28) — replicate verbatim
with name swap (`build_yookassa_client` for `build_email_client`).

**Boot-probe coverage** — Phase 48-specific tests (no email analog because
email probe is fail-fast):
```python
async def test_boot_probe_failure_is_non_fatal(respx_mock):
    """D-48-14 / SC2: probe failure does NOT prevent client construction."""
    respx_mock.get("https://api.yookassa.ru/v3/me").mock(
        return_value=httpx.Response(500)
    )
    client = await build_yookassa_client(settings=_test_settings())
    assert client is not None  # Degraded mode — still returned.
    # And the WARNING log must include reason=...

async def test_boot_probe_success_logs_ok(capsys, respx_mock):
    respx_mock.get("https://api.yookassa.ru/v3/me").mock(
        return_value=httpx.Response(200, json={"account_id": 123, ...})
    )
    await build_yookassa_client(settings=_test_settings(shop_id=123))
    blob = capsys.readouterr().out
    assert "yookassa_boot_probe" in blob and "ok=True" in blob

async def test_boot_probe_shop_id_mismatch_logs_warning(...): ...
```

---

### `tests/integrations/yookassa/test_receipt.py` (NEW)

**Analog:** for the pure-helper test shape, see `_money.py` and (if present)
its test module. For the enum-coverage shape there's no exact analog —
extend the `LOCKED_AUDIT_EVENTS` count-test idea (one `assert
len(VatCode) == 6`).

**Test cases:**
```python
def test_build_receipt_item_shape():
    item = build_receipt_item(
        description="Месячный абонемент в зал",
        amount_kopecks=199_000,
        payment_subject=PaymentSubject.SERVICE,
        payment_mode=PaymentMode.FULL_PREPAYMENT,
        vat_code=VatCode.VAT_NONE,
    )
    assert item == {
        "description": "Месячный абонемент в зал",
        "quantity": "1.00",
        "amount": {"value": "1990.00", "currency": "RUB"},
        "vat_code": 1,
        "payment_mode": "full_prepayment",
        "payment_subject": "service",
    }

def test_build_receipt_item_rejects_description_over_128_chars():
    with pytest.raises(ValueError, match="128"):
        build_receipt_item(description="x" * 129, ...)

def test_payment_subject_has_one_member(): assert len(PaymentSubject) == 1
def test_payment_mode_has_two_members(): assert len(PaymentMode) == 2
def test_vat_code_has_six_members(): assert len(VatCode) == 6
def test_payment_subject_service_value(): assert PaymentSubject.SERVICE.value == "service"
def test_payment_mode_values(): ...
def test_vat_code_values(): assert VatCode.VAT_NONE.value == 1; ...
```

---

### `tests/integrations/yookassa/test_webhook_verifier.py` (NEW)

**Analog:** no direct webhook-verifier test in repo (Phase 47 only tested
the AST gate, not the body — because the body raised `NotImplementedError`).
For FastAPI `Request` mocking, the closest precedent is any middleware
test in `tests/integration/` that uses `httpx ASGITransport` (project
standard — see CLAUDE.md "backend tests use `httpx ASGITransport`").

**Test cases:**
```python
async def test_sandbox_bypass(monkeypatch):
    """D-47-07: settings.sandbox=True short-circuits before any IP check."""
    # ... mock settings with sandbox=True; call verify_yookassa_ip(mock_request)
    # ... assert returns None without raising

async def test_trusted_ip_allowed():
    """Source IP in 185.71.76.0/27 passes."""
    request = _mock_request(client_host="185.71.76.5")
    await verify_yookassa_ip(request)  # no raise

async def test_untrusted_ip_raises_403_and_emits_audit():
    request = _mock_request(client_host="8.8.8.8")
    with pytest.raises(HTTPException) as exc:
        await verify_yookassa_ip(request)
    assert exc.value.status_code == 403
    assert exc.value.detail == "forbidden_ip"
    # ... assert audit_emit called with idempotency_outcome="rejected_ip"

async def test_missing_client_host_raises_403(): ...
async def test_malformed_ip_raises_403(): ...
async def test_ipv6_trusted_range_accepted():
    """2a02:5180::/32 IPv6 CIDR is in the frozenset and must validate."""
    ...
# TODO Phase 50: X-Forwarded-For toggle test — deferred per D-48-19 step 2.
```

---

### `tests/unit/test_locked_yookassa_constants_ast.py` (MODIFIED — extend with 2 functions)

**Analog:** self-extension. The file already contains
`test_real_callsites_pass`, `test_non_literal_verifier_arg_is_rejected`,
and `test_frozenset_has_six_entries` (read in full above).
For the new payment_subject / payment_mode literal-only gate, the
closest analog is `test_locked_email_templates_ast.py:42–73`
(`_resolve_str_literal` + `_is_get_email_dispatcher_call` +
`_iter_dispatcher_calls`) — read in full above.

**Walker helper to add** (mirror `_is_get_email_dispatcher_call` at
test_locked_email_templates_ast.py:49–57):
```python
def _is_build_receipt_item_call(node: ast.Call) -> bool:
    """True iff ``node`` is a direct ``build_receipt_item(...)`` call."""
    return isinstance(node.func, ast.Name) and node.func.id == "build_receipt_item"

def _extract_kwarg(call: ast.Call, name: str) -> ast.expr | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None
```

**Test function 1 — `test_payment_subject_literal_at_callsites`:**
```python
def test_payment_subject_literal_at_callsites() -> None:
    """D-48-18: every ``build_receipt_item(payment_subject=...)`` callsite
    MUST pass an ``ast.Attribute`` ``PaymentSubject.SERVICE`` (enum member),
    not a variable, f-string, or raw str literal. Phase 48 ships ZERO real
    callsites — Phase 49 orchestrator lands the first. Walker collects 0
    violations against the production tree today.
    """
    violations: list[str] = []
    for py in sorted(_BACKEND_APP.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _is_build_receipt_item_call(node):
                arg = _extract_kwarg(node, "payment_subject")
                if arg is None:
                    continue  # missing arg is a type error caught by mypy
                # Acceptable: PaymentSubject.SERVICE (ast.Attribute)
                # Rejected: variable, f-string, raw str
                if not (
                    isinstance(arg, ast.Attribute)
                    and isinstance(arg.value, ast.Name)
                    and arg.value.id == "PaymentSubject"
                ):
                    violations.append(
                        f"{py.relative_to(_REPO_ROOT)}:{node.lineno} — "
                        "payment_subject must be a PaymentSubject.<MEMBER> literal."
                    )
    assert not violations, "\n".join(violations)
```

**Test function 2 — `test_payment_mode_literal_at_callsites`:** identical
shape with `PaymentMode` swap. Same skeleton, copy-paste with name swap.

**Synthetic fixture (D-48-18 — mirror Phase 47's
`fixtures/yookassa_ast_violations/non_literal_verifier_arg.py`):**
- `tests/unit/fixtures/yookassa_ast_violations/non_literal_payment_subject.py`
  — fixture file containing a deliberately-bad
  `build_receipt_item(payment_subject=chosen_subject, ...)` callsite.
- `tests/unit/fixtures/yookassa_ast_violations/non_literal_payment_mode.py`
  — same for `payment_mode`.

---

### `pyproject.toml` (MODIFIED — add respx)

**Analog:** existing `[dependency-groups] dev` block at lines 26–35:
```toml
[dependency-groups]
dev = [
    "ruff>=0.6",
    "mypy>=1.10",
    "import-linter>=2.0",
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "asgi-lifespan>=2.1",
    "fakeredis>=2.35.1",
]
```

**Apply:** add `"respx>=0.21"` to the list (respx tracks httpx versions —
project uses httpx≥0.27 per line 14; respx 0.21 supports httpx 0.27+).
Confirm with `uv tree | grep respx` after `uv lock` to ensure no resolution
conflict.

---

## Shared Patterns

### Pattern S-1: Frozen dataclass + Literal classification (transport errors as values)

**Source:** `app/integrations/email/types.py:56–82`, `app/integrations/email/client.py:69–171`.

**Apply to:** `types.py` (all 4 result classes) AND `client.py` (every
method body).

**Concrete excerpt** (the canonical try/except taxonomy):
```python
try:
    # outbound RPC ...
    return YooKassaPaymentResult(classification="ok", ...)
except httpx.HTTPStatusError as exc:
    status = exc.response.status_code
    if status == 422:
        return YooKassaPaymentResult(classification="validation_error",
                                     http_status=status, error_code=..., ...)
    if status >= 500:
        return YooKassaPaymentResult(classification="transient_error", ...)
    return YooKassaPaymentResult(classification="permanent_error", ...)
except (httpx.TimeoutException, httpx.RequestError) as exc:
    return YooKassaPaymentResult(classification="transient_error", error=str(exc), ...)
except json.JSONDecodeError as exc:
    return YooKassaPaymentResult(classification="permanent_error", error=str(exc), ...)
except Exception as exc:
    return YooKassaPaymentResult(classification="transient_error", error=str(exc), ...)
```

### Pattern S-2: Async factory with LOCKED `async def` signature

**Source:** `app/integrations/email/factory.py:1–25` (the docstring justification)
+ `tests/unit/integrations/email/test_factory.py:21–28` (the lock test).

**Apply to:** `factory.py` (signature) AND `tests/integrations/yookassa/test_factory.py`
(the `inspect.iscoroutinefunction` assertion).

### Pattern S-3: Defensive-raise accessor + Protocol slot replacement at composition root

**Source:** `app/core/dependencies.py:940–988` (`YooKassaClientProvider`,
`register_yookassa_client_provider`, `get_yookassa_client_provider`) +
the existing `register_email_dispatcher(enqueue_email_dispatch)` pattern at
`app/main.py:267` and `app/workers/__init__.py:274`.

**Apply to:** `app/main.py` composition root edit + `app/workers/__init__.py`
`on_startup` edit. Phase 48 only replaces the *value* registered; the slot
declaration, accessor, and Protocol stay as Phase 47 shipped.

**Critical:** the SAME symbol reference (a closure or lambda) must be passed
to both `register_yookassa_client_provider` callsites so the parity test
(`tests/unit/test_yookassa_protocol_slot_parity.py` — already exists from
Phase 47 plan 47-04) continues to see a byte-equal reference.

### Pattern S-4: AST gate test for locked Literal/Enum callsite arguments

**Source:** `tests/unit/test_locked_email_templates_ast.py:42–212` (full
walker + violation-fixture pattern).

**Apply to:** the 2 new functions in `test_locked_yookassa_constants_ast.py`
covering `payment_subject` and `payment_mode`.

### Pattern S-5: Module docstring layer invariant (integration → no module imports)

**Source:** every existing `app/integrations/yookassa/*.py` module already
carries this footer:
> Layer invariant: lives at integrations layer — MUST NOT import from
> app.modules.* (importlinter contract integrations-not-depend-on-modules).

**Apply to:** `types.py`, `client.py`, `factory.py`, `receipt.py` —
verbatim footer paragraph in each module docstring.

### Pattern S-6: Structlog event naming + no-credential discipline

**Source:** `app/integrations/email/client.py:39, 102–171` (event names like
`email_send_ok` / `_blocked` / `_transient_error` / `_permanent_error`; no
credential values ever appear in `_log.info`/`warning` kwargs).

**Apply to:** all `_log.<level>` calls in `client.py` and `factory.py`.
Event names: `yookassa_<method>_<classification>` (e.g.,
`yookassa_create_payment_ok`, `yookassa_boot_probe`). Never log
`settings.secret_key` (SecretStr already redacts; explicit unwrap-and-log
is banned by convention).

---

## No Analog Found

| File | Role | Data Flow | Reason | Mitigation |
|------|------|-----------|--------|------------|
| `tests/integrations/yookassa/_responses/*.json` | static test fixture | none | First JSON-fixture directory in the project — no precedent | Follow the literal shape from STACK.md §1–2 + ЮKassa docs; one JSON per fixture, named to match the conftest fixture name. |
| `tests/integrations/yookassa/conftest.py` (respx usage) | test fixture module | n/a | `respx` is a NEW dev dependency in Phase 48 — no in-repo usage exists yet | Follow the official respx pattern (https://lundberg.github.io/respx/); use `with respx.mock(base_url=..., assert_all_called=False)` context manager. Local convention: prefer `assert_all_called=False` so fixtures can be imported into tests that exercise only a subset of the routes. |
| Webhook-verifier body | request-response middleware | request-response | Phase 47 skeleton is the only template — its docstring IS the contract | The docstring at `webhook_verifier.py:1–25` is the locked behaviour spec; implement step-by-step against it. |

---

## Cross-Reference Index (analog file → Phase 48 consumers)

| Analog file | Lines | Consumed by (Phase 48 file) |
|-------------|-------|------------------------------|
| `app/integrations/email/types.py` | 1–82 | `types.py` |
| `app/integrations/email/client.py` | 1–171 | `client.py` |
| `app/integrations/email/factory.py` | 1–112 | `factory.py` |
| `app/integrations/yookassa/_money.py` | 1–76 | `receipt.py` (uses `kopecks_to_yookassa`); `client.py` (uses both) |
| `app/integrations/yookassa/settings.py` | 1–51 | `factory.py`, `client.py`, `webhook_verifier.py` |
| `app/integrations/yookassa/webhook_verifier.py` | 1–60 | `webhook_verifier.py` (self-modify) |
| `app/integrations/yookassa/_stubs.py` | 21–25 | `app/main.py`, `app/workers/__init__.py` (REPLACE the stub) |
| `app/core/dependencies.py` | 925–988 | `app/main.py`, `app/workers/__init__.py` (register the real provider) |
| `app/core/audit_payloads.py` | 894–914 | `webhook_verifier.py` (audit emission); planner extends Literal |
| `app/main.py` | 261–296 | `app/main.py` (self-modify line 293) |
| `app/workers/__init__.py` | 240–294 | `app/workers/__init__.py` (self-modify line 284) |
| `tests/unit/integrations/email/test_client.py` | 1–80 | `tests/integrations/yookassa/test_client.py` |
| `tests/unit/integrations/email/test_factory.py` | 1–52 | `tests/integrations/yookassa/test_factory.py` |
| `tests/unit/test_locked_email_templates_ast.py` | 42–212 | `tests/unit/test_locked_yookassa_constants_ast.py` (extend with 2 funcs) |
| `tests/unit/test_locked_yookassa_constants_ast.py` | 1–250 | self-extend (Phase 48 adds `test_payment_subject_literal_at_callsites` + `test_payment_mode_literal_at_callsites`) |

---

## Metadata

**Analog search scope:** `apps/backend/app/integrations/`, `apps/backend/app/core/`,
`apps/backend/app/main.py`, `apps/backend/app/workers/__init__.py`,
`apps/backend/tests/unit/integrations/`, `apps/backend/tests/integration/`,
`apps/backend/tests/unit/test_locked_*`, `apps/backend/pyproject.toml`.

**Files scanned:** ~25 (single-pass Reads; no re-reads of any range).

**Pattern extraction date:** 2026-05-21.

**Open planning-level questions surfaced by this mapping** (planner resolves):
1. `YookassaWebhookReceivedPayload.idempotency_outcome` Literal currently
   `["new","duplicate_blocked"]` — must widen to include `"rejected_ip"`
   (or pick an alternative payload class for the rejected-IP audit).
   Audit-taxonomy AST gate may reject the widening; verify before
   committing.
2. `create_app()` is currently sync. Constructing `YooKassaClient` via
   `await build_yookassa_client(...)` requires either (a) moving the
   construction into `combined_lifespan` (mirrors `arq_pool`), or
   (b) making `create_app` async. Recommend (a) — same pattern as
   `arq_pool` already established at main.py:117–118.
3. `respx` version pin: `respx>=0.21` works with httpx 0.27.x. Confirm
   with `uv lock --upgrade-package respx` that no version-conflict
   warning surfaces.
4. `_responses/*.json` body shapes: research/STACK.md provides the
   canonical wire format but executor will need to capture one real
   ЮKassa sandbox response per fixture to scrub credentials and pin
   actual field names. If sandbox access is not available at execution
   time, hand-write the fixtures from the published API schemas.
