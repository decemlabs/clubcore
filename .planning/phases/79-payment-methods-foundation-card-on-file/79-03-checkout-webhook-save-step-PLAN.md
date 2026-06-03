---
phase: 79-payment-methods-foundation-card-on-file
plan: 03
type: execute
wave: 2
depends_on: ["79-01"]
files_modified:
  - apps/backend/app/integrations/yookassa/types.py
  - apps/backend/app/integrations/yookassa/client.py
  - apps/backend/app/modules/client_portal/schemas.py
  - apps/backend/app/modules/online_payments/service.py
  - apps/backend/app/api/v1/_internal/yookassa/handlers.py
  - apps/backend/tests/integration/client_portal/test_payment_method_webhook_save.py
autonomous: true
requirements: [PAYM-01]
must_haves:
  truths:
    - "save_payment_method=true in checkout body is persisted to the online_payments row"
    - "YooKassa create_payment forwards save_payment_method so the token returns in payment.succeeded"
    - "get_payment parses payment_method.type=='bank_card' into YooKassaPaymentMethodInfo (id/last4/card_type/expiry)"
    - "Webhook step 8.5 upserts the saved card token when save_payment_method is true, idempotent on replay"
    - "PAN/CVV are never stored — only token + display fields"
  artifacts:
    - path: "apps/backend/app/integrations/yookassa/types.py"
      provides: "YooKassaPaymentMethodInfo dataclass + payment_method field on YooKassaPaymentResult"
      contains: "class YooKassaPaymentMethodInfo"
    - path: "apps/backend/app/api/v1/_internal/yookassa/handlers.py"
      provides: "Step 8.5 raw-SQL card upsert in handle_payment_succeeded"
      contains: "client_payment_methods"
    - path: "apps/backend/tests/integration/client_portal/test_payment_method_webhook_save.py"
      provides: "Webhook token-save integration test"
      contains: "save_payment_method"
  key_links:
    - from: "apps/backend/app/api/v1/_internal/yookassa/handlers.py"
      to: "client_payment_methods (raw SQL upsert)"
      via: "ON CONFLICT ON CONSTRAINT uq_client_payment_methods_client_id_alive"
      pattern: "uq_client_payment_methods_client_id_alive"
    - from: "apps/backend/app/integrations/yookassa/client.py"
      to: "YooKassaPaymentMethodInfo"
      via: "parse payment_method.type=='bank_card'"
      pattern: "bank_card"
---

<objective>
Wire the save-during-payment path: add an optional `save_payment_method` flag to the client checkout
body and persist it on the `online_payments` row; forward the flag to YooKassa `create_payment`; parse
the returned card token in `get_payment` into a new `YooKassaPaymentMethodInfo`; and add step 8.5 to
`handle_payment_succeeded` that raw-SQL-upserts the saved card token (zero new ignore_imports). Cover it
with a webhook integration test.

Purpose: This is the only legitimate token-capture path (PAYM-01 — token from `payment.succeeded`, NEVER
from the sync create response; PAN/CVV never stored).
Output: extended YooKassa types + client parse, checkout-flag persistence, webhook step 8.5, webhook test.
</objective>

<execution_context>
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/workflows/execute-plan.md
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/79-payment-methods-foundation-card-on-file/79-CONTEXT.md
@.planning/phases/79-payment-methods-foundation-card-on-file/79-PATTERNS.md

<interfaces>
<!-- Contracts the executor builds against. Extracted from codebase. -->
YooKassaPaymentResult (app/integrations/yookassa/types.py lines 51-97) — frozen dataclass; fields end
with error_parameter at line 97. Append `payment_method: "YooKassaPaymentMethodInfo | None" = None`.
YooKassaRefundResult (lines 100-121) is the shape analog for the new companion dataclass.

YooKassaClient.create_payment (app/integrations/yookassa/client.py line 153) — kwargs-only; builds
`body` dict ~lines 222-232. Add a `save_payment_method: bool = False` kwarg; when True set
`body["save_payment_method"] = True`. YooKassaClient.get_payment (line 318) — parses payload; success
return at lines 343-352. Read payload.get("payment_method") and, when its `type == "bank_card"`,
populate the new payment_method field (id, card.last4, card.card_type, card.expiry_month/expiry_year).

handle_payment_succeeded (app/api/v1/_internal/yookassa/handlers.py line 345) — re-fetch at line 367
(`result = await yookassa_client.get_payment(object_id)`); single atomic UoW `async with
session.begin():` at line 388; promo redemption block lines 496-528; CHILD audit emit at line 530.
Step 8.5 lands AFTER the promo block (after line 528), BEFORE the CHILD audit. `row` is the
online_payments ORM row (has client_id and, after Plan 01, save_payment_method).

ClientCheckoutRequest lives in app/modules/client_portal/schemas.py (has promo_code field per 999.4).
online_payments record-write happens via the checkout service in app/modules/online_payments/service.py
(create_payment called at lines 342 and 380); the online_payments row insert must set
save_payment_method from the request flag.

Test infra: tests/integration/client_portal/conftest.py + factories; webhook/payment fakes exist under
tests/integration (mirror test_checkout.py + existing webhook tests). httpx ASGITransport + pytest-asyncio.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: YooKassa types + client parse — surface the saved card token</name>
  <files>apps/backend/app/integrations/yookassa/types.py, apps/backend/app/integrations/yookassa/client.py</files>
  <read_first>
    - apps/backend/app/integrations/yookassa/types.py (YooKassaPaymentResult lines 51-97; YooKassaRefundResult lines 100-121 as the companion-dataclass shape analog)
    - apps/backend/app/integrations/yookassa/client.py (create_payment lines 153-264 — body build ~222-232; get_payment lines 318-352)
    - .planning/phases/79-payment-methods-foundation-card-on-file/79-PATTERNS.md (types section lines 579-615)
  </read_first>
  <behavior>
    - YooKassaPaymentMethodInfo is a frozen dataclass with id:str, last4:str, card_type:str,
      expiry_month:int|None=None, expiry_year:int|None=None (primitives only — cloudpickle-safe; no
      app.modules import).
    - YooKassaPaymentResult gains payment_method: YooKassaPaymentMethodInfo | None = None.
    - create_payment(..., save_payment_method: bool = False): when True, body includes
      save_payment_method=True; when False, body is byte-identical to today (no key added).
    - get_payment populates result.payment_method when the response payload has
      payment_method.type == "bank_card" (id from payment_method.id; last4/card_type/expiry from the
      card sub-object); otherwise payment_method stays None.
  </behavior>
  <action>
    In types.py add `@dataclass(frozen=True) class YooKassaPaymentMethodInfo` (fields above; docstring notes
    integrations-layer invariant — MUST NOT import app.modules.*). Append
    `payment_method: "YooKassaPaymentMethodInfo | None" = None` to YooKassaPaymentResult after
    error_parameter (forward-ref string annotation). In client.py: add `save_payment_method: bool = False`
    kwarg to create_payment and set `body["save_payment_method"] = True` only when True (preserve exact
    existing body when False). In get_payment success path (before building the YooKassaPaymentResult at
    ~line 343), read `pm = payload.get("payment_method") or {}`; if `pm.get("type") == "bank_card"`, build
    YooKassaPaymentMethodInfo(id=pm["id"], last4=pm["card"]["last4"], card_type=pm["card"]["card_type"],
    expiry_month=int(pm["card"]["expiry_month"]) if present else None, expiry_year similarly), else None;
    pass it as the new payment_method kwarg. PII discipline: card fields NEVER logged in structlog events
    (do not add them to _log.info).
  </action>
  <verify>
    <automated>cd apps/backend && uv run ruff check app/integrations/yookassa/types.py app/integrations/yookassa/client.py && uv run mypy app/integrations/yookassa/types.py app/integrations/yookassa/client.py && uv run python -c "from app.integrations.yookassa.types import YooKassaPaymentMethodInfo, YooKassaPaymentResult; import dataclasses; assert dataclasses.is_dataclass(YooKassaPaymentMethodInfo); assert 'payment_method' in {f.name for f in dataclasses.fields(YooKassaPaymentResult)}; print('ok')"</automated>
  </verify>
  <acceptance_criteria>
    - Import smoke prints `ok`; ruff + mypy exit 0.
    - grep confirms `bank_card` parse branch in client.py and `save_payment_method` body key.
    - lint-imports still 0 (no app.modules import added to integrations layer).
  </acceptance_criteria>
  <done>Token/card info dataclass added; create_payment forwards the flag; get_payment parses bank_card; types/parse clean.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Checkout flag persistence + webhook step 8.5 card upsert</name>
  <files>apps/backend/app/modules/client_portal/schemas.py, apps/backend/app/modules/online_payments/service.py, apps/backend/app/api/v1/_internal/yookassa/handlers.py</files>
  <read_first>
    - apps/backend/app/modules/client_portal/schemas.py (ClientCheckoutRequest — promo_code field as the addition analog)
    - apps/backend/app/modules/online_payments/service.py (create_payment calls lines 342 + 380; the online_payments row insert that must set save_payment_method)
    - apps/backend/app/api/v1/_internal/yookassa/handlers.py (promo redemption block lines 496-528; CHILD audit at 530; re-fetched result at 367; UoW at 388)
    - .planning/phases/79-payment-methods-foundation-card-on-file/79-PATTERNS.md (handlers step 8.5 section lines 519-575)
  </read_first>
  <behavior>
    - ClientCheckoutRequest accepts optional save_payment_method: bool = False (wire savePaymentMethod).
    - The checkout service writes save_payment_method onto the online_payments row and passes
      save_payment_method=request.save_payment_method to create_payment (both membership + PT call sites).
    - In handle_payment_succeeded, when row.save_payment_method is true AND result.payment_method is not
      None, a raw-SQL INSERT ... ON CONFLICT ON CONSTRAINT uq_client_payment_methods_client_id_alive
      DO UPDATE upserts the card (resetting unlinked_at=NULL, autopay_enabled=false, consent_recorded_at=
      NULL on re-save). yookassa_method_id stores the token (pm.id). The upsert is inside the existing
      async with session.begin() block (atomic with the rest of the UoW) and idempotent on replay.
    - When save_payment_method is false OR result.payment_method is None, no card row is written.
  </behavior>
  <action>
    Add `save_payment_method: bool = False` to ClientCheckoutRequest (both membership + PT bodies if
    separate; mirror the promo_code field). In online_payments/service.py thread the flag: set the column on
    the online_payments insert and pass save_payment_method to BOTH create_payment call sites (lines 342 +
    380). In handlers.py, after the promo redemption block (after line 528) and before the CHILD audit emit
    (line 530), add the step 8.5 block per 79-PATTERNS.md lines 526-566: guard on
    `if row.save_payment_method and result.payment_method is not None:`; raw-SQL INSERT into
    client_payment_methods (client_id, yookassa_method_id, last4, brand, expiry_month, expiry_year,
    autopay_enabled=false) VALUES (...) ON CONFLICT ON CONSTRAINT
    uq_client_payment_methods_client_id_alive DO UPDATE SET token/last4/brand/expiry, unlinked_at=NULL,
    autopay_enabled=false, consent_recorded_at=NULL, updated_at=now(); bind client_id from str(row.client_id),
    method_id from pm.id, brand from pm.card_type. Emit a `payment_method_saved` structlog event with
    client_id + online_payment_id ONLY (no card fields). Use text() raw SQL — no ORM import from the
    integrations layer (zero new ignore_imports per the locked D-decision).
  </action>
  <verify>
    <automated>cd apps/backend && uv run ruff check app/modules/client_portal/schemas.py app/modules/online_payments/service.py app/api/v1/_internal/yookassa/handlers.py && uv run mypy app/modules/client_portal/schemas.py app/modules/online_payments/service.py app/api/v1/_internal/yookassa/handlers.py && uv run lint-imports</automated>
  </verify>
  <acceptance_criteria>
    - ruff + mypy + lint-imports all exit 0 (lint-imports proves zero new integrations-layer edge).
    - grep confirms `save_payment_method` in ClientCheckoutRequest and `uq_client_payment_methods_client_id_alive`
      in handlers.py.
    - grep confirms the step 8.5 guard `row.save_payment_method and result.payment_method is not None` in handlers.py.
    - `payment_method_saved` log event carries no card-detail kwargs (grep — only client_id/online_payment_id).
  </acceptance_criteria>
  <done>Checkout flag persisted + forwarded; webhook step 8.5 upserts the token idempotently; ruff/mypy/imports clean.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Webhook token-save integration test</name>
  <files>apps/backend/tests/integration/client_portal/test_payment_method_webhook_save.py</files>
  <read_first>
    - apps/backend/tests/integration/client_portal/test_checkout.py (checkout + webhook fake wiring, ASGITransport client, factories)
    - apps/backend/tests/integration/client_portal/conftest.py (fixtures: authed client, db session)
    - .planning/phases/79-payment-methods-foundation-card-on-file/79-PATTERNS.md (step 8.5 section for the expected upsert behavior)
  </read_first>
  <behavior>
    - GIVEN a checkout with save_payment_method=true and a faked payment.succeeded carrying
      payment_method.type=='bank_card' (token + last4 + card_type + expiry), WHEN the webhook is handled,
      THEN one client_payment_methods row exists for that client with the token in yookassa_method_id,
      correct last4/brand, autopay_enabled=false, consent_recorded_at NULL.
    - GIVEN save_payment_method=false (or the succeeded payload omits payment_method), WHEN the webhook is
      handled, THEN no client_payment_methods row is created.
    - GIVEN the same payment.succeeded delivered twice (replay), THEN still exactly one active row (upsert
      idempotency on the partial unique constraint).
  </behavior>
  <action>
    Create `tests/integration/client_portal/test_payment_method_webhook_save.py` mirroring the
    test_checkout.py webhook-fake pattern. Stub get_payment to return a YooKassaPaymentResult with a
    populated YooKassaPaymentMethodInfo. Write three tests: (1) save=true -> row saved with token+display
    fields, autopay off, consent null; (2) save=false / no payment_method -> zero rows; (3) duplicate
    webhook delivery -> exactly one active row. Assert yookassa_method_id holds the token (this is the only
    place the test reads it — the client API never does). Use httpx ASGITransport + pytest-asyncio; no real
    network.
  </action>
  <verify>
    <automated>cd apps/backend && uv run pytest tests/integration/client_portal/test_payment_method_webhook_save.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `pytest tests/integration/client_portal/test_payment_method_webhook_save.py` exits 0 with 3 tests passing.
    - The save=true test asserts last4/brand persisted and autopay_enabled is false + consent null.
    - The replay test asserts a single active row (no duplicate).
  </acceptance_criteria>
  <done>Webhook token-save behavior covered by 3 passing integration tests including replay idempotency.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| YooKassa webhook → backend | Inbound webhook body is untrusted; token is captured only from the server-side re-fetch (get_payment), never the webhook body |
| client → checkout API | save_payment_method is a client-supplied intent flag; it only enables saving the client's OWN card under their own webhook |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-79-07 | Spoofing | Token capture source | mitigate | Token read ONLY from get_payment re-fetch (PAYM-01), never from the unverified sync create response or webhook body (D-06/D-50-18 webhook-locked) |
| T-79-08 | Information Disclosure | Card details in logs | mitigate | payment_method_saved log emits client_id + online_payment_id only; create_payment/get_payment never log card fields (Task 1+2 grep gates) |
| T-79-09 | Tampering | Webhook replay creating duplicate cards | mitigate | Upsert ON CONFLICT on uq_client_payment_methods_client_id_alive — replay updates the single active row; test 3 asserts idempotency |
| T-79-10 | Information Disclosure | PAN/CVV storage | mitigate | Only token + last4/brand/expiry stored; full PAN/CVV never present in YooKassaPaymentMethodInfo or the upsert (PAYM-01) |
| T-79-SC | Tampering | uv install (supply chain) | accept | No new packages; existing httpx YooKassaClient extended (no aioyookassa/yookassa SDK per REQUIREMENTS out-of-scope) |
</threat_model>

<verification>
- ruff + mypy exit 0 on all modified source.
- lint-imports exits 0 (zero new integrations-layer edge — raw SQL upsert).
- Webhook token-save test (3 cases incl. replay) passes.
</verification>

<success_criteria>
- save_payment_method intent flows checkout body -> online_payments row -> create_payment -> webhook.
- Token captured from get_payment re-fetch (bank_card) and upserted idempotently in step 8.5.
- PAN/CVV never stored; card fields never logged.
</success_criteria>

<output>
Create `.planning/phases/79-payment-methods-foundation-card-on-file/79-03-SUMMARY.md` when done.
</output>
