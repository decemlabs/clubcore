# Technology Stack: v1.7 Online Payments (ЮKassa + 54-ФЗ)

**Project:** Sportzal
**Milestone:** v1.7 — Online Payments + 54-ФЗ fiscal receipts
**Researched:** 2026-05-21
**Overall confidence:** HIGH for ЮKassa API surface; MEDIUM for SDK async strategy (thread-safety undocumented by vendor)

---

## 1. ЮKassa Payments API Integration

### API Endpoint and Auth

**Base URL:** `https://api.yookassa.ru/v3/`
**Auth:** HTTP Basic Auth — shop ID as username, secret key as password.
**Confidence:** HIGH — sourced from official ЮKassa developer docs (https://yookassa.ru/developers/using-api/interaction-format).

### Payment FSM

Official statuses and their transitions (all verified against https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process):

```
pending → waiting_for_capture → succeeded   (two-stage: capture: false on create)
pending → succeeded                          (one-stage: capture: true, default)
pending → canceled
waiting_for_capture → canceled               (auto-cancel after expires_at)
```

`succeeded` and `canceled` are **terminal** states.

For Sportzal's membership-sale use case: use **one-stage capture** (`capture: true`). Two-stage is for goods-shipment scenarios where you hold funds while verifying stock — not applicable to digital membership activation.

### Idempotency-Key

- Header name: `Idempotence-Key` (ЮKassa spells it with one `t` — do not use `Idempotency-Key`)
- Format: any unique string, max 64 characters; V4 UUID recommended
- Required on all POST and DELETE requests
- Window: 24 hours — same key + same body → original response returned; same key + different body → rejected; different key → new request
- Integration point: `app/integrations/yookassa/client.py` must generate and persist the idempotency key **before** the HTTP call, not after, so retries replay the same key

### Webhook Events

Four events relevant to v1.7 (source: https://yookassa.ru/developers/using-api/webhooks):

| Event | Trigger |
|-------|---------|
| `payment.waiting_for_capture` | Two-stage: funds held, awaiting capture |
| `payment.succeeded` | Payment fully completed (funds settled) |
| `payment.canceled` | Payment rejected or expired |
| `refund.succeeded` | Refund completed |

**Receipt-specific webhook events do not exist.** Receipt status (`receipt_registration: pending / succeeded / canceled`) is a field on the payment object, not a separate event stream. Poll or re-check on `payment.succeeded` if fiscal status is needed asynchronously.

### Webhook Security — Critical Finding

**ЮKassa does NOT use HMAC signature headers.** The milestone context mentions `Notification-Sign HMAC` — this does **not** exist in the current ЮKassa API v3 (confirmed via official docs, nestjs-yookassa community documentation, and Go SDK examples — all consistently document IP-only verification). The `Notification-Sign` header appears in older archived YooMoney B2B payout protocols, not in the current API v3 payment acceptance flow.

**ЮKassa webhook security model (v3 API):**
1. **IP allowlist** — verify source IP against published CIDR ranges:
   - `185.71.76.0/27`, `185.71.77.0/27`
   - `77.75.153.0/25`, `77.75.156.11`, `77.75.156.35`, `77.75.154.128/25`
   - `2a02:5180::/32`
2. **Object re-fetch verification** — after receiving a webhook, re-fetch the payment object via `GET /v3/payments/{id}` and verify status matches the webhook payload. This is the recommended defense against spoofed webhooks that pass IP checks.
3. **HTTPS required** — TLS 1.2+, port 443 or 8443.

**Implementation:** Use `netaddr` (already a dep in the official SDK) or Python stdlib `ipaddress` module to validate the incoming IP. The official SDK ships `yookassa.domain.common.SecurityHelper.is_ip_trusted(ip: str) -> bool` which encapsulates this logic. If using raw httpx, reimplement with `ipaddress.ip_address(ip) in ipaddress.ip_network(cidr)` — no external dep needed.

**REQUIREMENT RESTATEMENT for v1.7:** The milestone context uses the phrase "Notification-Sign HMAC" as a target. Redirect this to the actual ЮKassa security model: IP allowlist check + re-fetch verification + HTTPS enforcement. Name the AST gate `YOOKASSA_TRUSTED_IPS` (frozenset) rather than `Notification-Sign HMAC` to reflect the real API surface.

---

## 2. ЮKassa /receipts (54-ФЗ) Integration

### Path Selection: ЮKassa's Own Receipt Service vs. АТОЛ/Чек.ОФД

**Verdict: Use "Чеки от ЮKassa" (ЮKassa's managed receipt service). Do NOT set up a separate АТОЛ/Чек.ОФД integration.**

Rationale:

| Factor | Чеки от ЮKassa | АТОЛ / Чек.ОФД (third-party) |
|--------|---------------|------------------------------|
| Who owns fiscal hardware | ЮKassa (included in their contract) | You — must separately buy/rent fiscal storage + register with FNS |
| API integration complexity | One field in payment request | Separate API per ОФД vendor |
| When required | Standard payments by companies / IP | Safe Deal or Split Payment scenarios only |
| v1.7 use case fit | Direct gym membership sales — YES | Split/marketplace flows — not applicable |
| Additional contract | None beyond ЮKassa merchant agreement | Separate АТОЛ or Чек.ОФД service contract |

Sportzal's scenario (gym selling memberships directly to clients via online payment) is exactly the "standard payments" case that "Чеки от ЮKassa" was designed for.

Source: https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/basics

### How Fiscal Receipts Work

Receipt data is **embedded in the payment create request** (not a separate POST to `/receipts` in the standard scenario). Flow:

1. Include `receipt` object in `POST /v3/payments` body
2. ЮKassa registers the receipt with their own fiscal infrastructure
3. Receipt is delivered to the client's email (ЮKassa delivers via email only — no SMS direct from their service)
4. `receipt_registration` field on the payment response shows `pending → succeeded / canceled`
5. For refunds: include `receipt` in `POST /v3/refunds` similarly

The standalone `POST /v3/receipts` endpoint exists for the "payment first, receipt separately" scenario — do not use this path for v1.7. The embedded approach (receipt in payment request) is simpler and covers Sportzal's synchronous checkout flow.

### Receipt Item Structure (54-ФЗ Required Fields)

Each item in `receipt.items[]` must contain:

| Field | 54-ФЗ Tag | Type | Required | Notes |
|-------|-----------|------|----------|-------|
| `description` | — | string | YES | Item name, max 128 chars |
| `quantity` | 1023 | decimal string | YES | e.g. `"1.00"` |
| `amount.value` | — | decimal string | YES | Per-item price |
| `amount.currency` | — | string | YES | `"RUB"` |
| `vat_code` | 1199 | integer | YES | See VAT table below |
| `payment_mode` | 1214 | string | YES | See enum below |
| `payment_subject` | 1212 | string | YES | See enum below |

**Tag 1212 (`payment_subject`) values for gym CRM:**
- `service` — for membership subscriptions and PT packages (correct choice for Sportzal)
- `commodity` — for physical goods (not applicable)
- Full enum has 40+ values including `marked`, `job`, `lottery`, etc. — irrelevant for v1.7

**Tag 1214 (`payment_mode`) — only two supported values:**
- `full_payment` — full payment at time of transaction (use for all Sportzal flows)
- `full_prepayment` — full prepayment (not applicable to Sportzal's model)
- Note: partial prepayment, advance, and credit are NOT supported by ЮKassa's own receipt service

**VAT codes (vat_code):**
- `1` — VAT exempt (most likely for a gym selling memberships under упрощёнка)
- `2` — 0% VAT
- `3` — 10% VAT
- `4` — 20% VAT
- `5` — estimated 20/120
- `6` — estimated 10/110
- `7` — 5% VAT (added April 2025)
- `8` — 7% VAT (added April 2025)

Confidence: HIGH for enum values — sourced from https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/parameters-values

**No fiscal tag dictionary helper library is needed.** The enum values are small (8 VAT codes, 2 payment_mode values, ~40 payment_subject values). Define them as Python `Literal` types or `StrEnum` constants in `app/integrations/yookassa/models.py`. A third-party tag-dictionary library for 54-ФЗ would be over-engineering — none exist in the Python ecosystem with meaningful adoption.

---

## 3. Webhook Handling

### FastAPI Route Architecture

New module: `app/api/v1/webhooks/yookassa.py`

Handler requirements:
1. Parse raw body **before** any JSON deserialization (read raw bytes for future integrity reference, even though ЮKassa doesn't use HMAC)
2. Extract `X-Forwarded-For` or real IP — validate against `YOOKASSA_TRUSTED_IPS` frozenset
3. If IP fails: return `400` immediately, emit `yookassa_webhook_rejected_ip` audit event
4. Deserialize JSON to Pydantic model discriminated by `event` field
5. Dispatch to payment FSM handler in `app/modules/payments/`
6. Return `200` with empty body (ЮKassa ignores response body; timeout causes retry)
7. Re-fetch payment from ЮKassa API to verify status matches webhook payload (defense against spoofed webhooks that pass IP check)

**Idempotency for webhook processing:** Use Redis `SET NX EX` on key `sz:webhook:yk:{payment_id}:{event}` to deduplicate. ЮKassa retries unacknowledged webhooks (no 200 within ~10 seconds). Mirror the `sz:bot:update:{update_id}` pattern from v1.2.

**ARQ for retry:** Do NOT dispatch webhook to an ARQ worker. The webhook handler must respond 200 quickly. Heavy processing (membership activation, audit writing) happens inline in the handler within a DB transaction. ARQ retry is only needed if the membership-activation transaction itself fails, which should be handled by the DB transaction rollback — not by re-queueing the webhook.

### Webhook Route Registration

`app/api/v1/webhooks/` is a new sub-router. Register in `app/api/v1/__init__.py` or `app/api/router.py`. The route does NOT go through the CSRF dependency (webhooks are machine-to-machine, not browser-originated).

---

## 4. Library / SDK Choice

### Decision: Use Official `yookassa` SDK v3.x + Thin Async Wrapper

**Verdict: Use the official `yookassa` package from PyPI (v3.10.1), wrapped in `asyncio.get_event_loop().run_in_executor()` calls inside `app/integrations/yookassa/client.py`. Do NOT use any of the third-party async SDK alternatives.**

**Rationale:**

| Criterion | Official `yookassa` v3.x | `aioyookassa` (unofficial) | `async_yookassa` (unofficial) | Raw `httpx` |
|-----------|-------------------------|---------------------------|-------------------------------|-------------|
| Vendor-maintained | YES (YooMoney publishes to PyPI; 3.10.1 released 2026-04-22) | No — community | No — community | N/A |
| Python 3.12 support | YES | YES (aiohttp-based) | YES (requires >=3.12) | YES |
| Type annotations / mypy | Partial — no `py.typed` marker, uses legacy patterns; requires `# type: ignore` on import | Unknown | Unknown | Full control |
| Async support | NO — synchronous `requests` library | YES | YES | YES (native) |
| `SecurityHelper.is_ip_trusted()` | YES — built-in | No | No | Implement manually |
| Receipt API support | YES — `Receipt.create()`, embedded in payment | Partial | Partial | Full control |
| Maintenance risk | LOW — YooMoney publishes quarterly; no CVEs; 38 total versions | HIGH — single-developer community lib | HIGH — community, inactive since late 2024 | N/A |
| Call volume for Sportzal | < 100 payments/day | N/A | N/A | < 100/day |

**The async problem is not a problem at Sportzal's scale.** The gym processes at most tens of payments per day — not thousands per second. Wrapping synchronous `requests` calls with `run_in_executor(None, sync_fn)` blocks a thread pool thread for ~200ms per call, which is completely acceptable. The event loop is not blocked because `run_in_executor` offloads to a thread.

**Why NOT raw httpx despite the project already using httpx (email integration):** The official SDK handles non-obvious details: IP trust list management via `SecurityHelper`, `WebhookNotificationFactory` for parsing multiple event types with correct discriminated union semantics, retry headers, and receipt model validation. Re-implementing these in raw httpx saves a dependency but loses 3+ hours of edge-case work per API surface. The SDK's `requests` dependency is benign — it won't conflict with the project's `httpx`.

**Why NOT `aioyookassa` or `async_yookassa`:** Community-maintained, no type stubs, no `SecurityHelper`, incomplete receipt support. If the official vendor SDK were truly unmaintained (like `yoomoney/yookassa-sdk-python` v2 on GitHub which IS archived), using raw httpx would be the right call. But the PyPI `yookassa` v3.x package (different from the archived GitHub repo) has 8 releases since October 2025 and 0 CVEs — it is the active maintained artifact.

**Mypy strategy:** Add `yookassa` to `[[tool.mypy.overrides]]` in `pyproject.toml` with `ignore_missing_imports = true`. All types from ЮKassa objects that cross module boundaries must be re-typed in Sportzal's own `app/integrations/yookassa/models.py` Pydantic models — SDK objects never leak past the integration layer.

**The async wrapper pattern:**
```python
# app/integrations/yookassa/client.py
import asyncio
from functools import partial
from yookassa import Payment, Refund, Receipt

async def create_payment(params: dict, idempotency_key: str) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        partial(Payment.create, params, idempotency_key)
    )
```

All integration functions in `app/integrations/yookassa/client.py` follow this pattern. The integration layer owns `Configuration.configure()` called once in the FastAPI lifespan.

---

## 5. Versions Table

| Package | Version | Source | Confidence | Notes |
|---------|---------|--------|------------|-------|
| `yookassa` | `3.10.1` | PyPI (2026-04-22) | HIGH | Official SDK; pinned in `uv.lock`; no CVEs |
| `netaddr` | (transitive via `yookassa`) | PyPI | HIGH | Required by SDK's `SecurityHelper`; already a transitive dep |
| `requests` | (transitive via `yookassa`) | PyPI | HIGH | SDK HTTP transport; will not conflict with project's `httpx` |
| Python | `3.12` | project locked | HIGH | SDK classifiers support 3.7–3.12; verified |

**No additional packages required.** All other requirements (async, Pydantic models, httpx, Redis, ARQ, structlog) are already in the production stack.

**Do not add:**
- `aioyookassa` — community, incomplete, no SecurityHelper
- `async_yookassa` — community, stale
- `yookassa_api` — unknown provenance
- Any 54-ФЗ tag-dictionary library — no credible Python options; use Literal/StrEnum constants instead

---

## 6. What NOT to Add

| What | Why |
|------|-----|
| Stripe (any form) | BANNED — RF regional constraint, CLAUDE.md locked |
| `aioyookassa` / `async_yookassa` | Community packages, no type support, incomplete receipt API, no SecurityHelper |
| АТОЛ or Чек.ОФД direct integration | Not needed — "Чеки от ЮKassa" covers all standard payments; separate ОФД adapters only for Safe Deal / Split Payment which Sportzal does not use |
| Separate `POST /v3/receipts` flow | Over-engineering — embedding receipt in payment request is the correct path for synchronous checkout |
| HMAC / Notification-Sign verification | This header does NOT exist in ЮKassa API v3 — implement IP allowlist + re-fetch instead |
| ARQ worker for webhook processing | Webhooks must return 200 fast; heavy work is inline in handler transaction; ARQ retry is handled by DB rollback, not re-queuing |
| Redis-backed idempotency for ЮKassa outbound calls | ЮKassa's own 24-hour idempotency key window is sufficient; do not double-layer with Redis; only Redis dedup for inbound webhook deduplication |
| Paid third-party fiscal receipt proxy (e.g., БИФИТ, МодульКасса) | Not needed if "Чеки от ЮKassa" is connected; adds cost and a second integration surface |
| Webhook retry queue | ЮKassa retries on non-200; app just needs to be idempotent on receipt |

---

## Integration Touch Points

| New Module/File | Purpose |
|----------------|---------|
| `app/integrations/yookassa/__init__.py` | Package init |
| `app/integrations/yookassa/client.py` | Async wrappers over SDK (`create_payment`, `capture_payment`, `cancel_payment`, `create_refund`, `get_payment`) |
| `app/integrations/yookassa/models.py` | Pydantic v2 models for ЮKassa API objects (Payment, Refund, WebhookEvent) — SDK types never cross module boundaries |
| `app/integrations/yookassa/security.py` | `YOOKASSA_TRUSTED_IPS: frozenset[str]` + `is_trusted_ip(ip: str) -> bool` (wraps SDK SecurityHelper or stdlib `ipaddress`) |
| `app/integrations/yookassa/receipt.py` | `build_receipt_item(description, amount_kopecks, vat_code, payment_subject) -> dict` helper; `PaymentSubject` StrEnum; `PaymentMode` StrEnum; `VatCode` IntEnum |
| `app/modules/payments/` | New module: online payment FSM, webhook dispatcher, `payment_recorder` Protocol consumer for online flow |
| `app/api/v1/webhooks/yookassa.py` | FastAPI route `POST /api/v1/webhooks/yookassa` — IP check, parse, dispatch to payments module |

**import-linter contracts to add:**
- `app.integrations.yookassa` must not import from `app.modules.*` (integration layer stays below module layer)
- `app.modules.payments` imports from `app.integrations.yookassa` (allowed, same as email integration pattern)

---

## Sources

- ЮKassa interaction format: https://yookassa.ru/developers/using-api/interaction-format
- ЮKassa payment process: https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process
- ЮKassa webhooks: https://yookassa.ru/developers/using-api/webhooks
- ЮKassa 54-ФЗ basics: https://yookassa.ru/developers/payment-acceptance/receipts/54fz/basics
- Чеки от ЮKassa: https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/basics
- Чеки при платежах: https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/payments
- Receipt parameter values: https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/parameters-values
- ЮKassa API changelog: https://yookassa.ru/developers/using-api/changelog
- `yookassa` PyPI package: https://pypi.org/project/yookassa/
- `yookassa` Snyk security scan: https://security.snyk.io/package/pip/yookassa
- SDK archived GitHub repo: https://github.com/yoomoney/yookassa-sdk-python (archived; v2.x only; the active artifact is the PyPI package v3.x)
- nestjs-yookassa webhook security docs: https://nestjs-yookassa.ru/docs/webhooks/security
