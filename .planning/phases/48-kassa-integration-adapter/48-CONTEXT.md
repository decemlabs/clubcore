# Phase 48: ЮKassa Integration Adapter - Context

**Gathered:** 2026-05-21
**Status:** Ready for planning
**Mode:** `--auto` (recommended defaults applied; decisions logged inline)

<domain>
## Phase Boundary

Ship the complete async ЮKassa **integration layer** — typed result DTOs, async httpx client (`create_payment`, `get_payment`, `create_refund`, `get_refund`), boot-time API probe, receipt-item builder, webhook IP verifier body, and shared `respx` test fixtures. **No domain module consumes the adapter yet** — wiring stays empty/no-op until Phase 49 (Online Sales Orchestrator) and Phase 50 (Webhook FSM). The adapter exists, is testable in isolation, and is ready to be plugged into the `YooKassaClientProvider` Protocol slot that Phase 47 declared.

Requirements covered: **ADAPTER-01..ADAPTER-06** (6 reqs).

Phase 47 already shipped the foundations this phase builds on:
- `YOOKASSA_TRUSTED_IPS` frozenset + `verify_yookassa_ip` skeleton (Phase 48 fills the body)
- `YooKassaSettings` (`shop_id`, `secret_key: SecretStr`, `return_url`, `tax_system_code`, `default_vat_code`, `sandbox`)
- `kopecks_to_yookassa` / `yookassa_to_kopecks` converters in `_money.py`
- `YooKassaClientProvider` Protocol slot in `app/core/dependencies.py` (no-op stub)
- 9 v1.7 audit events in `LOCKED_AUDIT_EVENTS` (this phase emits at most `yookassa_webhook_received` on rejected_ip)

</domain>

<decisions>
## Implementation Decisions

### Transport choice — locked by ROADMAP.md
- **D-48-01:** **Pure async `httpx.AsyncClient`** — NOT the official `yookassa` SDK, NOT `aioyookassa`/`async_yookassa`. ROADMAP.md Phase 48 wording ("Pure async httpx wrapper… `respx` test fixtures") is the locked transport choice. Research SUMMARY.md initially recommended the official SDK + `run_in_executor`; the project deliberately diverged because (a) `respx` mocks at the httpx layer cleanly, (b) the email integration already establishes the "raw async client + classified result type" pattern (D-42-01/02), and (c) at < 100 payments/day the SDK adds zero value and one sync surface to bridge.
- **D-48-02:** Re-implement what the SDK would have given for free, in the integration layer:
  - **IP allowlist:** stdlib `ipaddress.ip_address(ip) in ipaddress.ip_network(cidr)`. No `netaddr`, no `SecurityHelper`. Pattern from PITFALLS.md Pitfall 1 prevention §4.
  - **Webhook event parsing:** `YooKassaWebhookEvent` frozen dataclass discriminating on `event` literal (`payment.succeeded` / `payment.canceled` / `refund.succeeded` for v1.7 scope). No SDK `WebhookNotificationFactory`.
  - **Receipt model validation:** explicit StrEnum/IntEnum + dict assembly in `receipt.py`.

### Typed result DTOs (ADAPTER-01)
- **D-48-03:** `app/integrations/yookassa/types.py` exposes **four frozen dataclasses**, all `@dataclass(frozen=True)`, all cloudpickle-safe (primitives + UUID + Decimal only):
  - `YooKassaPaymentResult` — outcome of `create_payment` / `get_payment`
  - `YooKassaRefundResult` — outcome of `create_refund` / `get_refund`
  - `YooKassaReceiptResult` — only present if Phase 51 needs an async `POST /v3/receipts` (not in Phase 48 scope; declared empty/placeholder per ADAPTER-01 wording for forward-compat). Wave-1 contract.
  - `YooKassaWebhookEvent` — parsed webhook body (event literal + object payload dict + correlation hooks). Consumed by Phase 50 webhook handler.
- **D-48-04:** Each result class carries a **closed `Literal` `classification`** field — mirrors `EmailSendResult` (D-42-13). Variants: `'ok' | 'validation_error' | 'transient_error' | 'permanent_error'`. Dispatcher / orchestrator code switches on this literal; never on exception type. `classification='ok'` carries the parsed payment/refund payload; failure variants carry `error_code: str | None` + `http_status: int | None`.
- **D-48-05:** **No SDK types cross the boundary.** Module docstring states this explicitly. `mypy [[tool.mypy.overrides]] module = "yookassa.*"` is unnecessary because the SDK is never imported. Pydantic v2 models live in `types.py` only if needed for inbound webhook parse; otherwise plain dataclasses.

### httpx client lifecycle (ADAPTER-02)
- **D-48-06:** **Long-lived `httpx.AsyncClient`** held by `YooKassaClient` for the process lifetime. Constructed once in `app/integrations/yookassa/factory.py:build_yookassa_client` and closed in the FastAPI lifespan teardown (ARQ worker `on_shutdown` mirror — REG-29-03 double-wire). Connection pool reuse matters at TLS-handshake cost; per-call construction would re-handshake every payment.
  - **Divergence from email pattern:** `aioboto3` sessions are factories (D-42-30 calls for fresh per call). `httpx.AsyncClient` is the opposite — designed for reuse. Diverging consciously, documented in factory docstring.
- **D-48-07:** Auth = HTTP Basic with `shop_id` as username, `secret_key.get_secret_value()` as password. Configured via `httpx.BasicAuth` on the client; never present in URLs or query strings; never logged.
- **D-48-08:** Base URL toggled by `YooKassaSettings.sandbox`: production → `https://api.yookassa.ru/v3/`. Sandbox URL: ЮKassa uses the **same base URL** with sandbox credentials (per ЮKassa docs — no separate sandbox host). `sandbox=True` therefore affects ONLY the IP-verifier bypass (D-47-07), NOT the API URL. Documented in client docstring to head off the "what's the sandbox URL?" question.
- **D-48-09:** Default timeout: `httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)`. Pinned via constants in `client.py`; no env override in Phase 48. Read timeout > write because ЮKassa's `POST /payments` can run 2–3s under load.
- **D-48-10:** **Never re-raise SDK / httpx exceptions** (SC1). Every `httpx.RequestError`, `httpx.HTTPStatusError`, `asyncio.TimeoutError`, `json.JSONDecodeError`, `pydantic.ValidationError`, etc. is **caught and classified** into the result variant. Pattern: same shape as `EmailClient.send_email` body — `try/except` chain → return `YooKassaPaymentResult(classification=…)`. No raise leaves the integration layer.

### Idempotency-Key (ADAPTER-02)
- **D-48-11:** Caller passes `idempotency_key: UUID` (or `str` UUIDv4) to `create_payment` / `create_refund`. The adapter does NOT generate it. Rationale: Phase 49 orchestrator must persist the key in `online_payments` BEFORE the HTTP call so retries replay the same key (Pitfall 2 prevention). Generating inside the client makes retries non-idempotent and loses traceability. STACK.md §1 Idempotency-Key (`Idempotence-Key`, one `t` — ЮKassa quirk).
- **D-48-12:** Header name written as `Idempotence-Key` (ЮKassa spelling). Constant `IDEMPOTENCE_KEY_HEADER: Final[str] = "Idempotence-Key"` in `client.py`; AST gate not required (single callsite, locked).

### Boot probe (ADAPTER-03)
- **D-48-13:** **Probe endpoint = `GET /v3/me`**. Lightweight; authenticates the credentials; no side effects. Returns shop metadata. Probe ON SUCCESS logs `yookassa_boot_probe ok=True shop_id=…`; ON FAILURE logs `yookassa_boot_probe ok=False reason=…`. Both via structlog at INFO/WARNING respectively.
- **D-48-14:** **Probe failure is non-fatal** (SC2 — degraded mode). The `build_yookassa_client` factory **still returns the constructed `YooKassaClient`** so request-path code can call it; only the probe result is logged.
  - **Divergence from email factory (D-42-30):** email probe failure raises `RuntimeError` at boot (fail-fast). ЮKassa probe failure is degraded-mode by SC2 requirement — gym still operates offline-cash without ЮKassa, but the operator must see a structured alert. Document this difference in factory docstring.
- **D-48-15:** No retry loop inside the probe — single attempt, single log. Operator runbook entry (Phase 53 deferred): "If `yookassa_boot_probe ok=False` appears in logs, the online-payments endpoints will return `transient_error` until ЮKassa reachability is restored."

### Receipt builder (ADAPTER-04)
- **D-48-16:** `app/integrations/yookassa/receipt.py:build_receipt_item(description, amount_kopecks, vat_code, payment_subject, payment_mode, quantity='1.00')` returns a `dict[str, Any]` shaped per ЮKassa wire format. Returning a dict (not a typed model) is deliberate — the dict is concatenated into a list inside the payment-create body; ЮKassa's receipt nested object accepts dicts directly, and Phase 49 callers will assemble `receipt={items: [...], customer: {email: ...}, tax_system_code: ...}` themselves. STACK.md §Integration Touch Points lines 257–258 confirm dict shape.
- **D-48-17:** **Three enums + AST-gated literals:**
  - `class PaymentSubject(StrEnum): SERVICE = "service"` — single member in v1.7 (gym memberships + PT packages). AST gate `test_locked_yookassa_constants_ast.py` rejects any non-literal `payment_subject=` at any callsite (mirror `LOCKED_EMAIL_TEMPLATES` AST gate from Phase 41 Plan 41-03).
  - `class PaymentMode(StrEnum): FULL_PAYMENT = "full_payment"; FULL_PREPAYMENT = "full_prepayment"` — two members. `full_prepayment` for online membership sales paid before activation (most cases); `full_payment` for at-point-of-consumption (drop-in classes, PT sessions paid at the gym desk). Phase 49 orchestrator picks per sale type.
  - `class VatCode(IntEnum): VAT_NONE = 1; VAT_0 = 2; VAT_10 = 3; VAT_20 = 4; VAT_10_110 = 5; VAT_20_120 = 6` — full 54-ФЗ enumeration from ЮKassa docs. Caller passes the code; defaults to `YooKassaSettings.default_vat_code` if omitted in `build_receipt_item`.
- **D-48-18:** SC3 wording ("AST gate rejects non-literal values") covers `payment_subject` and `payment_mode`. AST gate file: `apps/backend/tests/unit/test_locked_yookassa_constants_ast.py` (new). Co-existing with the AST gate from Phase 47 plan 47-03 (`YOOKASSA_TRUSTED_IPS`) — single new test module, two test functions inside.

### IP verifier body (ADAPTER-05)
- **D-48-19:** Fill the Phase 47 skeleton at `apps/backend/app/integrations/yookassa/webhook_verifier.py:verify_yookassa_ip`. Implementation contract (already documented in the skeleton's module docstring):
  1. Read `settings.sandbox` via FastAPI Depends or module-level singleton; if True → return (bypass per D-47-07).
  2. Extract source IP: prefer `request.headers.get("x-forwarded-for")` (first value, comma-split, strip) if a `TRUSTED_PROXY` header config flag is set; otherwise `request.client.host`. The `X-Forwarded-For` trust toggle is a Phase 50 deployment concern; in Phase 48 the verifier reads `request.client.host` directly. Document the `X-Forwarded-For` toggle as a `# TODO Phase 50:` line.
  3. Check membership against `YOOKASSA_TRUSTED_IPS` using `ipaddress.ip_address(ip) in ipaddress.ip_network(cidr)` for each cidr.
  4. On miss: emit `yookassa_webhook_received` audit with `idempotency_outcome="rejected_ip"` payload + raise `HTTPException(status_code=403, detail="forbidden_ip")`.
- **D-48-20:** **AST gate `Depends(verify_yookassa_ip)` callsite contract** is already locked from Phase 47 plan 47-03 (`test_locked_yookassa_constants_ast.py`). Phase 48 only ships the body; the gate test from Phase 47 already enforces the callsite literal.
- **D-48-21:** Verifier runs **before** body parse via FastAPI dependency ordering — `@router.post("/_internal/yookassa/webhook", dependencies=[Depends(verify_yookassa_ip)])` style. Phase 50 owns the actual webhook route; Phase 48 only ships the verifier function.

### `respx` test fixtures (ADAPTER-06)
- **D-48-22:** `apps/backend/tests/integrations/yookassa/conftest.py` exposes **6 canonical pytest fixtures**, each a context manager that mounts respx routes:
  1. `yookassa_create_payment_success` — `POST /v3/payments` → 200 with `pending` status + `confirmation_url`
  2. `yookassa_create_payment_422` — `POST /v3/payments` → 422 validation error (e.g., `invalid_credentials`, `parameter_required`)
  3. `yookassa_get_payment_pending` — `GET /v3/payments/{id}` → 200 with `pending`
  4. `yookassa_get_payment_succeeded` — `GET /v3/payments/{id}` → 200 with `succeeded` + receipt_registration field
  5. `yookassa_create_refund_success` — `POST /v3/refunds` → 200 with `pending`/`succeeded`
  6. `yookassa_webhook_payload` — **NOT a respx route** — pure `dict` fixture returning a canonical `payment.succeeded` webhook body. Phase 50 webhook tests `request.json()` this.
- **D-48-23:** Each fixture loads its response body from `tests/integrations/yookassa/_responses/{name}.json` — real captured ЮKassa response shape (from sandbox, scrubbed of credentials). Keeping the JSON separate from Python code means future docs-driven updates don't churn test code.
- **D-48-24:** Fixtures use the **adapter's own typed parsing path** in tests where possible — i.e., test that `YooKassaClient.create_payment(...)` returns `YooKassaPaymentResult(classification='ok', payment_id=..., status='pending', confirmation_url=...)` after the respx mock fires. End-to-end parse coverage at the adapter boundary.

### Module layout (recap)
```
apps/backend/app/integrations/yookassa/
├── __init__.py                  # exports the public surface (factory + types)
├── _money.py                    # ✅ shipped Phase 47
├── _stubs.py                    # ✅ shipped Phase 47 (no-op Protocol stubs)
├── settings.py                  # ✅ shipped Phase 47
├── webhook_verifier.py          # 🆕 Phase 48 fills the body (skeleton exists)
├── types.py                     # 🆕 Phase 48 — 4 frozen dataclasses (ADAPTER-01)
├── client.py                    # 🆕 Phase 48 — async httpx client (ADAPTER-02)
├── factory.py                   # 🆕 Phase 48 — build_yookassa_client + boot probe (ADAPTER-03)
└── receipt.py                   # 🆕 Phase 48 — build_receipt_item + 3 enums (ADAPTER-04)
```
**No `circuit_breaker.py` in Phase 48.** Circuit breaker for ЮKassa lives on the *fiscal-receipt dispatch* path (Phase 51 FISCAL-05 — `sz:yookassa:circuit:receipts` Redis key). The adapter itself is breaker-less in Phase 48; Phase 49 orchestrator wraps it with retry/breaker semantics for the outbound payment-create path if SUMMARY.md scope demands it.

### Composition-root wiring (Phase 48 vs Phase 49 split)
- **D-48-25:** Phase 48 changes the `YooKassaClientProvider` Protocol slot from the no-op stub (`yookassa_client_provider_noop_stub` in `_stubs.py`) to the **real** `build_yookassa_client`-returned instance. ARQ worker `on_startup` mirror (REG-29-03 double-wire). This is a one-line composition-root edit in `app/main.py` + `app/worker.py`.
- **D-48-26:** The other three Protocol slots (`FiscalReceiptDispatcher`, `MembershipActivator`, `PtPackageActivator`) **stay no-op** through Phase 48. Phase 49 wires `MembershipActivator` + `PtPackageActivator`; Phase 50 wires `FiscalReceiptDispatcher`.

### Claude's Discretion
Downstream agents may settle the following without re-asking:
- **JSON parser:** `httpx.Response.json()` — no need for explicit `orjson` swap. ЮKassa payload sizes are < 4 KB.
- **`User-Agent` header:** `Sportzal/1.7 ЮKassa-Adapter` for outbound calls. Aids ЮKassa-side log forensics.
- **Currency literal:** `"RUB"` hardcoded as `Final[str]` constant in `receipt.py`. No multi-currency in v1.7.
- **Default `quantity`:** `"1.00"` string default in `build_receipt_item`. Caller can override.
- **`return_url` injection:** the client adds `confirmation.type="redirect"` + `confirmation.return_url=settings.return_url` to every `create_payment` call. Phase 49 orchestrator does NOT pass it.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project / milestone scope
- `.planning/PROJECT.md` — milestone v1.7 framing, RF regional constraints, webhook-security correction (IP allowlist, no HMAC)
- `.planning/REQUIREMENTS.md` lines 25–30 — ADAPTER-01..06 full text
- `.planning/ROADMAP.md` lines 152–162 — Phase 48 goal + 5 success criteria
- `.planning/STATE.md` — milestone v1.7 status

### Prior phase context (Phase 47 — Bedrock)
- `.planning/phases/47-bedrock/47-CONTEXT.md` — Phase 47 decisions (D-47-01..09), settings + Protocol slot wiring approach
- `.planning/phases/47-bedrock/47-VERIFICATION.md` — what landed: settings.py, webhook_verifier.py skeleton, `YOOKASSA_TRUSTED_IPS`, `_money.py`, Protocol slots
- `.planning/phases/47-bedrock/47-PATTERNS.md` — pattern map for Phase 47 (email-integration mirror)
- `.planning/phases/47-bedrock/deferred-items.md` — pre-existing E501 + mypy + cron-count drift NOT to fix here

### Research (v1.7 milestone)
- `.planning/research/SUMMARY.md` — milestone synthesis; note SDK-vs-httpx divergence (ROADMAP locks httpx per D-48-01)
- `.planning/research/STACK.md` §1 (lines 1–100) — Idempotence-Key header, webhook IP security
- `.planning/research/STACK.md` §2 (lines 100–170) — 54-ФЗ receipt structure, tag 1212/1214/1199 values
- `.planning/research/STACK.md` §6 lines 252–261 — integration touchpoints table (receipt.py dict return shape)
- `.planning/research/PITFALLS.md` Pitfall 1 — IP allowlist + re-fetch (Phase 50 owns re-fetch; Phase 48 owns IP)
- `.planning/research/PITFALLS.md` Pitfall 2 — idempotency dedup discipline (caller-owned key per D-48-11)

### Codebase contracts to preserve
- `apps/backend/app/integrations/email/types.py` — `EmailEnvelope` + `EmailSendResult` frozen-dataclass + classification pattern (mirror for `YooKassaPaymentResult` etc.)
- `apps/backend/app/integrations/email/client.py` lines 1–80 — classified `try/except` chain shape (mirror for `YooKassaClient.create_payment`)
- `apps/backend/app/integrations/email/factory.py` lines 1–60 — async factory + boot probe shape (mirror BUT D-48-14 diverges to non-fatal)
- `apps/backend/app/integrations/email/circuit_breaker.py` — for reference only; Phase 48 has NO breaker (D-48-24)
- `apps/backend/app/integrations/yookassa/settings.py` — Phase 47 shipped; consumed by factory
- `apps/backend/app/integrations/yookassa/webhook_verifier.py` — Phase 47 skeleton; Phase 48 fills body per module docstring contract
- `apps/backend/app/integrations/yookassa/_money.py` — kopecks ↔ ЮKassa wire converters; consumed by `receipt.py` and `client.py`
- `apps/backend/app/integrations/yookassa/_stubs.py` — Phase 47 no-op Protocol stubs (Phase 48 replaces `yookassa_client_provider_noop_stub` only)
- `apps/backend/app/core/dependencies.py` — `YooKassaClientProvider` Protocol slot; defensive-raise accessor pattern
- `apps/backend/app/core/audit.py` `LOCKED_AUDIT_EVENTS` — `yookassa_webhook_received` (emitted by verifier on rejected_ip)
- `apps/backend/app/core/audit_payloads.py` — `YookassaWebhookReceivedPayload` (Phase 47 shipped)
- `apps/backend/tests/unit/test_locked_yookassa_constants_ast.py` — AST gate from Phase 47 plan 47-03 (extend for `payment_subject` / `payment_mode` per D-48-18)
- `apps/backend/tests/unit/test_locked_email_templates_ast.py` — AST-gate test pattern source

### External specs (ЮKassa / 54-ФЗ)
- https://yookassa.ru/developers/using-api/interaction-format — Idempotence-Key (single `t`), Basic Auth, base URL
- https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process — payment FSM (pending → succeeded / canceled)
- https://yookassa.ru/developers/api?codeLang=python#create_payment — `POST /v3/payments` schema
- https://yookassa.ru/developers/api?codeLang=python#create_refund — `POST /v3/refunds` schema
- https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/parameters-values — `payment_subject`, `payment_mode`, `vat_code`, `tax_system_code` enums
- https://yookassa.ru/developers/using-api/webhooks — 6 trusted CIDRs + webhook event shape
- https://respx.lundberg.dev/ — respx httpx-mocking docs (fixture pattern)
- https://www.python-httpx.org/async_clients/ — httpx `AsyncClient` lifecycle

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`app/integrations/email/types.py`** — `EmailSendResult` frozen dataclass + closed `Literal` classification — direct template for `YooKassaPaymentResult` / `YooKassaRefundResult`. Same shape, same discipline (transport errors are values, not exceptions).
- **`app/integrations/email/client.py`** classified `try/except` chain — direct template for `YooKassaClient.create_payment` body. Replace SES-V2 errors with httpx status / httpx exceptions; same classification semantics (`ok` / `validation_error` (422) / `transient_error` (5xx, network) / `permanent_error` (4xx non-422)).
- **`app/integrations/email/factory.py:build_email_client`** — async factory + boot probe shape. Phase 48 diverges only in failure semantics (degraded vs fail-fast per D-48-14).
- **`apps/backend/app/integrations/yookassa/_money.py`** — `kopecks_to_yookassa(int) -> str` and `yookassa_to_kopecks(str) -> int`. Used inside `receipt.py:build_receipt_item` to render `amount.value="199.00"` and inside `client.py` to parse refund/payment amounts.
- **`apps/backend/app/integrations/yookassa/settings.py`** — instantiated once in factory; passed by reference to `YooKassaClient.__init__`.
- **`SecretStr.get_secret_value()`** — already used by email; same pattern for `httpx.BasicAuth(str(settings.shop_id), settings.secret_key.get_secret_value())`.
- **Phase 47 plan 47-03 AST gate test scaffold** — extend with two test functions for `payment_subject` and `payment_mode` literal enforcement (D-48-18).

### Established Patterns
- **INFRA-15 discipline:** every locked constant has an AST-gate test. Phase 48 extends `test_locked_yookassa_constants_ast.py` to cover `PaymentSubject` / `PaymentMode` (in addition to Phase 47's `YOOKASSA_TRUSTED_IPS`).
- **Transport errors as values, not exceptions** (D-42-13 lineage) — every adapter method returns `*Result(classification=...)`. No `raise` past the integration boundary.
- **Async factory + boot probe** (D-42-30 lineage) — factory is `async def`; probe runs inside lifespan; probe failure semantics diverge (degraded vs fail-fast).
- **Protocol slot at composition root** — `YooKassaClientProvider` already declared; Phase 48 swaps the no-op stub for the real instance.
- **Frozen dataclasses for cross-boundary DTOs** — D-42-16 pattern; cloudpickle-safe for any future ARQ enqueue.

### Integration Points
- `app/integrations/yookassa/types.py` (new) — 4 frozen dataclasses; importable from anywhere; **do not** import from `app.modules.*` (integration-layer invariant).
- `app/integrations/yookassa/client.py` (new) — owns the single `httpx.AsyncClient` instance; consumed by `app/main.py` lifespan + `app/worker.py` `on_startup` (REG-29-03 double-wire).
- `app/integrations/yookassa/factory.py` (new) — single entrypoint `build_yookassa_client`; called from FastAPI lifespan and ARQ worker startup.
- `app/integrations/yookassa/receipt.py` (new) — pure function; consumed by Phase 49 orchestrator + Phase 50 fiscal-receipt dispatcher (the latter via Phase 51 wiring).
- `app/integrations/yookassa/webhook_verifier.py` (existing skeleton) — body filled; FastAPI `Depends()` consumer lives in Phase 50.
- `app/main.py` composition root — one-line edit: replace `yookassa_client_provider_noop_stub` with `await build_yookassa_client(settings=...)`.
- `app/worker.py` (`on_startup`) — mirror the composition-root edit for ARQ.
- `apps/backend/tests/integrations/yookassa/conftest.py` (new) — 6 respx fixtures + 1 dict fixture (ADAPTER-06).
- `apps/backend/tests/integrations/yookassa/_responses/*.json` (new) — captured ЮKassa response bodies.
- `apps/backend/tests/unit/test_locked_yookassa_constants_ast.py` (existing from Phase 47) — extended with 2 new test functions.
- `pyproject.toml` — add `respx` to `[tool.uv]` dev dependencies if not already present (verify with `uv tree | grep respx`).

</code_context>

<specifics>
## Specific Ideas

- **httpx Basic Auth:** `httpx.BasicAuth(username=str(settings.shop_id), password=settings.secret_key.get_secret_value())`. Construct once in factory.
- **`Idempotence-Key` header** is per-request, not per-client. Set via the `extra_headers` arg to `client.post(...)`.
- **Probe call:** `await client.get("/me", timeout=5.0)` with 200 → ok; any other status / exception → not-ok. Capture `shop_id` from response payload to compare against `settings.shop_id` (mismatch is a configuration error worth WARNING-logging).
- **`build_receipt_item` return dict shape (per ЮKassa docs):**
  ```python
  {
      "description": "Месячный абонемент в зал",  # ≤ 128 chars
      "quantity": "1.00",
      "amount": {"value": "1990.00", "currency": "RUB"},
      "vat_code": 1,  # int
      "payment_mode": "full_prepayment",  # Literal
      "payment_subject": "service",  # Literal
  }
  ```
- **Description truncation:** ЮKassa enforces 128 chars on `description`. Caller responsibility, but `build_receipt_item` should `assert len(description) <= 128` to catch in dev / test.
- **respx fixture skeleton:**
  ```python
  @pytest.fixture
  async def yookassa_create_payment_success(respx_mock):
      respx_mock.post("https://api.yookassa.ru/v3/payments").mock(
          return_value=httpx.Response(200, json=load_json("create_payment_success.json"))
      )
      yield respx_mock
  ```
- **Webhook payload canonical fixture** must include `event="payment.succeeded"`, `object.id` (UUID), `object.status="succeeded"`, `object.amount`, `object.receipt_registration="succeeded"`, `object.metadata` (correlation hook for Phase 50).
- **`yookassa_webhook_received` audit emission** from `verify_yookassa_ip` on rejected_ip: payload carries `outcome="rejected_ip"`, `source_ip=<extracted>`, `audit_correlation_id=None` (no upstream correlation on rejected requests).

</specifics>

<deferred>
## Deferred Ideas

- **`X-Forwarded-For` trust toggle** — Phase 48 verifier reads `request.client.host` only. Behind-reverse-proxy support (`TRUSTED_PROXY_HEADER_ENABLED=True`) deferred to **Phase 50** (where the actual webhook route is wired and proxy topology is known). Documented as `# TODO Phase 50:` in `webhook_verifier.py`.
- **`POST /v3/receipts` standalone receipts** — only needed for "payment first, receipt separately" scenario (refunds with delayed receipt). Phase 51 FISCAL-04 may need this; Phase 48 leaves `YooKassaReceiptResult` as a placeholder type with no client method.
- **Adapter-level retry/circuit breaker for outbound payment-create** — not in Phase 48. Phase 49 orchestrator may wrap `create_payment` with ARQ-level retry; the breaker for the fiscal-receipt dispatch path is Phase 51 FISCAL-05 territory (`sz:yookassa:circuit:receipts` Redis key).
- **Streaming response support** — ЮKassa returns small JSON; no streaming needed.
- **Webhook signature verification** — does not exist in ЮKassa API v3 (PITFALLS Pitfall 1). Not deferred; rejected.
- **Sandbox-specific base URL** — ЮKassa uses the same base URL with sandbox credentials. Not deferred; non-existent.
- **`async_yookassa` / `aioyookassa`** — rejected by D-48-01.
- **mypy override for `yookassa.*`** — unnecessary because the SDK is never imported (D-48-05).

### Reviewed Todos (not folded)
*No todos matched Phase 48 in `gsd-sdk query todo.match-phase 48` — section omitted.*

</deferred>

---

*Phase: 48-Kassa-Integration-Adapter*
*Context gathered: 2026-05-21*
*Mode: --auto (recommended defaults applied; deviations from email-integration pattern documented inline)*
