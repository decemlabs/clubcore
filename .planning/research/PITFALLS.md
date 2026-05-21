# Domain Pitfalls: v1.7 Online Payments (ЮKassa) + 54-ФЗ Fiscal Receipts

**Domain:** Adding ЮKassa online payment intake + 54-ФЗ fiscal receipts to Sportzal gym CRM (FastAPI / SQLAlchemy 2.0 async / ARQ / Postgres 16 / Redis 7)
**Researched:** 2026-05-21
**Milestone context:** v1.7, continuing from v1.6 (email/webhook HMAC discipline, anti-oracle) and v1.4 (append-only cash ledger, SHA-256 row hash, partial UNIQUE on refund_of)

---

## Critical Pitfalls

### Pitfall 1: Webhook IP-Only Authentication — No HMAC Signature on ЮKassa Notifications

**Severity:** BLOCKER

**What goes wrong:**
Unlike Stripe or Telegram, ЮKassa's webhook security model does NOT include an HMAC signature header (there is no `Notification-Sign` or equivalent). The official documentation recommends two weaker methods only: IP address whitelisting (CIDR ranges: `185.71.76.0/27`, `185.71.77.0/27`, `77.75.153.0/25`, `77.75.156.11`, `77.75.156.35`, `77.75.154.128/25`, `2a02:5180::/32`) and status re-confirmation via GET to the ЮKassa API.

A developer who mirrors the v1.6 email bounce-webhook HMAC discipline (HMAC-SHA256-before-parse) will find no such mechanism exists for ЮKassa. This is not a missing feature to implement — it is the actual ЮKassa security model.

**Why it happens:**
ЮKassa's authentication relies on network-layer IP whitelisting rather than cryptographic message authentication. The IP list is published and stable, but IP spoofing in a proxied environment (reverse proxy, load balancer, CDN) can present `X-Forwarded-For` vectors if not handled correctly.

**Consequences:**
- If IP validation is misconfigured at the proxy layer (trusting `X-Forwarded-For` without `trusted_proxies` or `X-Real-IP` pinning), a forged webhook can trigger membership activation or refund processing.
- Parse-before-validate: if the webhook body is parsed (and business logic is run) before IP is checked, a spoofed request can partially corrupt state even if ultimately rejected.
- Without status re-confirmation (GET `/payments/{id}` from ЮKassa API), there is no cryptographic proof that the webhook is genuine.

**Prevention:**
1. **Validate IP first, parse body second** — middleware extracts `request.client.host` (or trusted proxy header) and rejects with 403 before body parsing. This is structurally parallel to v1.6 "HMAC-before-parse" but at the IP layer. Apply `import-linter` contract if possible, or an AST gate checking that the webhook router calls `validate_yookassa_ip(request)` before any `await request.json()`.
2. **Always re-confirm status** — after receiving a `payment.succeeded` notification, always call `GET /payments/{object.id}` from ЮKassa API and check the returned status before activating memberships. This provides the cryptographic anchor that HMAC would otherwise provide (ЮKassa API authentication is HTTP Basic Auth: shopId + secretKey, not spoofable by a third party).
3. **Register the validation function name as a frozenset constant** (`YOOKASSA_IP_RANGES`) to make it AST-gateable and grep-able. Treat this like the `LOCKED_AUDIT_EVENTS` discipline — pre-register before any callsite.
4. Do NOT use the `yookassa` official Python SDK as the sole webhook handler — its `SecurityHelper.is_ip_trusted()` is the right tool but the SDK uses synchronous `requests` library internally; use `async_yookassa` or a direct `httpx.AsyncClient` wrapper.

**Warning signs:**
- Webhook handler function reads `request.body()` or `request.json()` before any IP check
- No `GET /payments/{id}` re-confirmation before `membership_activated` event
- Reverse proxy passes `X-Forwarded-For` through without stripping/restricting to ЮKassa IP range

**Phase hint:** Bedrock phase (first phase of v1.7). Gate must be in place before any webhook consumer lands.

---

### Pitfall 2: Webhook Idempotency Without Dedup Key — Double Membership Activation

**Severity:** BLOCKER

**What goes wrong:**
ЮKassa retries webhook delivery for 24 hours on any non-200 response. There is no guaranteed single-delivery. The `object.id` field (payment UUID) inside the notification body is the natural dedup key, but ЮKassa does not provide a separate stable "notification ID" — the same `payment.succeeded` event will be resent with the same `object.id`.

If the webhook handler activates a membership, records a payment row, and emits audit events without dedup, the second retry will attempt to activate the same membership twice — creating a second `payments` row, a second `membership_activated` audit event, and potentially a duplicate `membership` row.

**Why it happens:**
Developers unfamiliar with ЮKassa's retry model assume webhooks are delivered once. The `Idempotency-Key` header that governs outgoing API requests (payment creation) is a different concept from incoming webhook dedup.

**Consequences:**
- Double membership activation: client gets two overlapping active memberships
- Double payment row: v1.4 ledger integrity violated (append-only invariant holds structurally, but logical correctness breaks)
- Double audit events: payment audit chain becomes ambiguous

**Prevention:**
1. **Redis dedup gate** — on receipt of `payment.{event}` webhook, `SET NX EX 86400 sz:wh:event:{event_type}:{object.id}` before any DB write. If the key already exists, return 200 immediately (idempotent). Mirror the v1.2 Telegram `update_id` dedup pattern (`sz:bot:update:{update_id}` TTL 1h), extended to 24h to cover ЮKassa's retry window.
2. **DB-level idempotency guard** — `online_payments` table has `UNIQUE (yookassa_payment_id)`. A second attempt to insert the same ЮKassa payment ID will fail with `IntegrityError` → service returns 200 (dedup, not error). DB wins the race if Redis is unavailable (fail-safe, not fail-open).
3. **State-machine guard** — membership activation is only triggered if `online_payments.status` is currently `pending` or `waiting_for_capture` (transition to `succeeded`). A second webhook on an already-`succeeded` payment is a no-op at the state machine layer even if Redis dedup is bypassed.
4. Dedup key is `(event_type, object.id)` — NOT just `object.id`, because `payment.canceled` and `payment.succeeded` are distinct events for the same payment object.

**Warning signs:**
- Webhook handler has no Redis `SET NX` before DB write
- No `UNIQUE (yookassa_payment_id)` constraint on the payments table
- Membership activation not guarded by status transition check

**Phase hint:** Bedrock phase. UNIQUE constraint is a migration-level requirement; Redis dedup is an integration-phase requirement.

---

### Pitfall 3: Webhook Race — Redirect Arrives Before Webhook, Activating Membership on Redirect

**Severity:** BLOCKER

**What goes wrong:**
After a user completes payment on ЮKassa's redirect page, two things happen in parallel:
1. The browser is redirected to `return_url` (arrives in seconds — synchronous from the user's perspective)
2. ЮKassa sends a webhook to your server (asynchronous — may arrive milliseconds or minutes later)

A developer who activates the membership on the `return_url` handler (because "the user has paid") will activate the membership BEFORE the `payment.succeeded` webhook is processed. The redirect only proves the user completed the payment flow on ЮKassa's side — it does not prove the payment actually succeeded (the user could have bookmarked `return_url` and opened it directly, or the payment may still be in `waiting_for_capture` state).

**Why it happens:**
The `return_url` redirect creates a "it worked" UX signal that developers mistake for a "payment succeeded" business signal.

**Consequences:**
- Membership activated for a payment that is actually `waiting_for_capture`, `canceled`, or `pending` — gym gives away membership for free
- Double activation if both redirect AND webhook handler activate the membership

**Prevention:**
1. **return_url handler shows ONLY a "pending" status screen** — "Оплата получена, проверяем платёж..." with a polling endpoint or WebSocket. No membership activation at this layer.
2. **Membership activation is LOCKED to the `payment.succeeded` webhook handler** — single code path, no exceptions. Use an AST gate or import-linter contract: the membership activation function may only be called from the webhook module.
3. **Polling endpoint** — `GET /payments/online/{internal_payment_id}/status` re-confirms against ЮKassa API (status re-confirmation from Pitfall 1 serves double duty here). Returns `pending`, `succeeded`, or `failed`. Frontend polls until terminal state.
4. Register `membership_activated` as a `LOCKED_AUDIT_EVENT` that can ONLY be emitted from the webhook processing path (AST literal-string gate already prevents ad-hoc strings; the callsite constraint is enforced by `import-linter`).

**Warning signs:**
- `return_url` handler calls any membership activation, payment recording, or audit emission function
- Frontend navigates directly to membership detail on redirect without polling

**Phase hint:** Bedrock phase — this constraint shapes the payment FSM design before any integration code lands.

---

### Pitfall 4: Payment-Status Oracle via Redirect URL or Timing

**Severity:** BLOCKER (mirrors v1.6 anti-oracle discipline)

**What goes wrong:**
The `return_url` differentiates between success and failure by including a status parameter (`?status=success` vs `?status=failed`) or by redirecting to different URLs. This leaks the payment decision to the URL (logs, browser history, referrer headers) and creates a timing oracle: the time difference between a fast "already succeeded" vs. a slow "still waiting" response reveals payment state to a passive observer.

**Why it happens:**
Copy-pasting tutorials that use `?payment_id=xxx&status=success` patterns, or implementing separate success/error return URLs.

**Consequences:**
- Payment status in browser history and server access logs
- Timing differential (immediate "success" page vs. "checking..." page) reveals payment outcome to side-channel attackers
- Mirrors the exact anti-oracle concern from v1.6 email OTP: byte-identical responses across verified/unverified

**Prevention:**
1. **Single `return_url`** — one URL regardless of payment outcome: `GET /payments/return?payment_id={internal_id}`. No `status` parameter.
2. **Constant-time floor** — the return URL handler ALWAYS responds with the same "checking payment..." page, regardless of whether payment has already succeeded in the DB. Applies `_constant_time_floor` try/finally pattern from v1.6 email OTP: even if DB lookup takes 0ms (already succeeded) or 200ms (still pending), the response time is floored to a fixed minimum.
3. **Audit both paths** — `payment_return_received` audit event emitted regardless of outcome, with only `payment_id` (not status) in the payload.

**Warning signs:**
- `return_url` contains `?status=` or `?success=`
- Different redirect targets for success vs failure
- Return handler response time is correlated with payment state

**Phase hint:** Bedrock phase. Return URL contract must be defined before frontend integration.

---

### Pitfall 5: Off-by-100 Currency Conversion — Kopecks vs ЮKassa Decimal Format

**Severity:** BLOCKER

**What goes wrong:**
The v1.4 `payments` table stores amounts as `INTEGER` kopecks (e.g., 50000 = 500.00 RUB). ЮKassa API uses a `{"value": "500.00", "currency": "RUB"}` string format for amounts. A developer who passes the kopeck integer directly to ЮKassa sends 50000 RUB instead of 500.00 RUB — charging the client 100× the correct amount.

The reverse is equally dangerous: parsing the ЮKassa `"500.00"` string as an integer for storage yields 500 kopecks (5.00 RUB) instead of 50000 kopecks (500 RUB).

**Why it happens:**
Two separate type systems for money: internal (integer kopecks) vs. ЮKassa (decimal string rubles). The conversion is `kopecks / 100` on send, `Decimal(value) * 100` (rounded) on receive.

**Consequences:**
- 100× overcharge: client is billed 50 000 RUB for a 500 RUB membership — card declines or extreme customer complaint
- 100× underrecord: internal ledger shows 5 RUB received for a 500 RUB payment — revenue tracking catastrophically wrong

**Prevention:**
1. **Dedicated converter functions** — `kopecks_to_yookassa(kopecks: int) -> str` (divides by 100, formats to 2 decimal places) and `yookassa_to_kopecks(value: str) -> int` (parses Decimal, multiplies by 100, rounds to int). No inline conversion — these are the ONLY conversion paths.
2. **Unit tests** — `test_kopecks_to_yookassa`: assert `kopecks_to_yookassa(50000) == "500.00"`, `kopecks_to_yookassa(1) == "0.01"`. `test_yookassa_to_kopecks`: assert `yookassa_to_kopecks("500.00") == 50000`, handling edge case `"0.10"` → 10.
3. **Pydantic validator** on `OnlinePaymentCreate` schema: `amount_kopecks: int` field, validated > 0, and the converter is called in the service layer, never in the schema.
4. **mypy strict** — `kopecks_to_yookassa` has return type `str`, not `int`. Any caller passing the return value to an integer field will fail type-check.
5. Add `KOPECKS_TO_YOOKASSA_CONVERSION` as a named test fixture constant so tests never hardcode raw amounts.

**Warning signs:**
- Inline `amount / 100` or `str(amount)` in payment creation code
- No dedicated conversion module
- Test that asserts `amount == 50000` without checking the ЮKassa-side format

**Phase hint:** Bedrock phase. Converter must exist and be tested before any payment creation code lands.

---

### Pitfall 6: Double-Tap Payment — Parallel Payment Initiations for Same Membership Sale

**Severity:** BLOCKER

**What goes wrong:**
Reception clicks "Оплатить онлайн" twice in rapid succession (double-tap, network lag, browser retry). Two ЮKassa payment objects are created for the same membership sale. Both may succeed independently. The first `payment.succeeded` webhook activates the membership; the second `payment.succeeded` webhook finds the membership already active but still records a second payment — creating an orphaned payment row with no linked membership activation.

**Why it happens:**
No idempotency key discipline on the payment creation API call, or the Idempotency-Key is regenerated on each button click.

**Consequences:**
- Two payment rows for one membership (ledger integrity broken)
- Double charge: client's card debited twice
- Orphaned payment with no membership linkage (reconciliation nightmare)

**Prevention:**
1. **Deterministic Idempotency-Key** on payment creation: `Idempotency-Key = sha256(f"sell-membership:{membership_plan_id}:{client_id}:{today_date}")`. The key is computed from stable business identifiers, not from a per-request UUID. A second creation attempt within 24h returns the same ЮKassa payment object without creating a new charge.
2. **DB partial UNIQUE** — `UNIQUE (client_id, membership_plan_id, DATE(initiated_at))` on `online_payments WHERE status != 'canceled'` — prevents two simultaneous pending payments for the same product. The `WHERE status != 'canceled'` predicate allows a retry after explicit cancellation. This mirrors v1.3 `(membership_id) WHERE ended_at IS NULL` freeze discipline.
3. **Frontend single-submission guard** — the "Оплатить" button is disabled on click until terminal state is reached (standard TanStack Query mutation `isPending`). Backend constraint is the authoritative guard; frontend guard reduces noise.

**Warning signs:**
- `Idempotency-Key: str(uuid4())` generated fresh on each request
- No partial UNIQUE on the online_payments table
- Button remains enabled during payment pending state

**Phase hint:** Bedrock phase (UNIQUE constraint in migration) + integration phase (deterministic key computation in service).

---

## Moderate Pitfalls

### Pitfall 7: 54-ФЗ Fiscal Receipt Timing — Receipt Must Be Issued "At the Moment of Payment"

**Severity:** WARN

**What goes wrong:**
54-ФЗ requires the fiscal receipt to be sent to ФНС via ОФД and to the customer "at the moment of payment" (в момент совершения расчёта) for online transactions with remote interaction. The 5-minute tolerance in the law applies to the fiscal register's clock accuracy, NOT to a 5-minute grace period for receipt issuance. If the ARQ task queue is backlogged or ЮKassa's `/receipts` endpoint is slow, receipts can be delayed significantly — potentially triggering 14.5 КоАП penalties (up to 10 000 RUB per undelivered receipt for legal entities).

**Why it happens:**
Treating the fiscal receipt as a "nice to have" async notification rather than a legally mandated synchronous-equivalent step. The ARQ `dispatch_receipt` task may queue behind other work and not execute immediately.

**Consequences:**
- Receipt delivered minutes or hours after payment — legal violation per 54-ФЗ
- Penalties: up to 10 000 RUB per receipt for юрлицо (Article 14.5 КоАП РФ)
- ОФД rejection if receipt timestamp deviates significantly from payment timestamp

**Prevention:**
1. **Priority queue** — `dispatch_receipt` ARQ task gets higher queue priority than other background tasks. ARQ supports separate queues via `queue_name` parameter; create a `receipts_high_priority` queue with a dedicated worker.
2. **Embed receipt data in payment creation request** — ЮKassa Scenario 1 (simultaneous payment + receipt) is preferred over Scenario 3 (separate `/receipts` call after payment). When receipt data is in the payment creation payload, ЮKassa handles timing synchronously.
3. **Fiscal receipt status monitoring** — `online_receipts` table with `fiscal_status` FSM (`pending → succeeded / failed / canceled`); an ARQ cron scans for `pending` rows older than 90 seconds and alerts (structlog ERROR + Telegram operator DM).
4. **Receipt-failure does NOT rollback payment** — the v1.6 email payment receipt discipline is preserved: "payment commit NOT rolled back on send failure". Receipt failure is an operational problem to fix; revoking an already-settled payment creates a worse legal problem.

**Warning signs:**
- `dispatch_receipt` is enqueued in the same queue as non-urgent background work
- No monitoring for `fiscal_status = 'pending'` receipts older than 2 minutes
- Receipt data not included in the payment creation payload

**Phase hint:** Integration phase. Priority queue and monitoring are post-integration-bedrock concerns.

---

### Pitfall 8: Wrong 54-ФЗ Subject/Method Tags — Voiding the Receipt

**Severity:** WARN (legal consequences if wrong)

**What goes wrong:**
The fiscal receipt must carry correct `payment_subject` (тег 1212, "признак предмета расчёта") and `payment_mode` (тег 1214, "признак способа расчёта"). Using wrong values voids the receipt's legal compliance even if it is technically accepted by ЮKassa.

For Sportzal's services:
- Gym membership (абонемент): `payment_subject = "service"` (услуга), `payment_mode = "full_payment"` (полный расчёт) — the client pays in full for a fixed-duration membership. NOT `"commodity"` (товар).
- PT package (персональные тренировки): also `payment_subject = "service"`, `payment_mode = "full_payment"`. NOT `"full_prepayment"` (предоплата 100%) unless sessions have not yet been scheduled at payment time — in that case `"full_prepayment"` may apply per ФФД 1.05/1.2 rules.
- ЮKassa's "Чеки от ЮKassa" integration only supports `"full_prepayment"` and `"full_payment"` — partial prepayment, advances, and credit are explicitly NOT supported.

**Why it happens:**
Cargo-culting `payment_subject = "commodity"` from e-commerce tutorials, or confusing "предоплата" with "partial advance".

**Consequences:**
- Tax authority can invalidate the receipt → fine per Article 14.5 КоАП
- Client's receipt carries wrong product classification → consumer rights complaints

**Prevention:**
1. **Locked constants** — `RECEIPT_SUBJECT_MEMBERSHIP = "service"`, `RECEIPT_SUBJECT_PT_PACKAGE = "service"`, `RECEIPT_MODE_FULL = "full_payment"` as named constants in `app/modules/billing/constants.py`. These are NOT configurable at runtime.
2. **Pydantic schema validation** — `payment_subject: Literal["service", "commodity", "job", "payment"]`, `payment_mode: Literal["full_payment", "full_prepayment"]` (ЮKassa's supported subset). mypy strict will catch any assignment outside the Literal type.
3. **Owner sign-off row** — like the `D-27-OWNER-COPY-LOCK` mechanism for Telegram copy, create a `D-47-RECEIPT-TAG-LOCK` record in planning artifacts documenting that `service + full_payment` was chosen for memberships and PT packages with the tax rationale.
4. **Verification test** — integration test asserts that the receipt payload sent to ЮKassa mock contains `payment_subject == "service"` and `payment_mode == "full_payment"` for both membership and PT-package sale paths.

**Warning signs:**
- `payment_subject` is a string parameter passed by the caller at runtime
- No Pydantic Literal type narrowing on the field
- Tutorial-derived `"commodity"` value in any fixture or test data

**Phase hint:** Integration phase (receipt creation). Tag values must be decided and locked before the first receipt endpoint is built.

---

### Pitfall 9: Email/Phone Mandatory for Fiscal Receipt — Client Has Neither

**Severity:** WARN

**What goes wrong:**
54-ФЗ requires at least one customer contact (email OR phone) for electronic receipt delivery. ЮKassa delivers receipts only to email (SMS is not available). If a client in the Sportzal `clients` table has neither `email` nor `phone` populated (phone is soft-delete-safe via partial UNIQUE but may be NULL in edge cases; email is not yet a required field), ЮKassa will reject the receipt creation request with a validation error.

**Why it happens:**
v1.1–v1.6 client CRUD did not require email for client records (email was not a client field; only operators/users have email). The payment flow encounters a null-contact client and the receipt API rejects it.

**Consequences:**
- Receipt cannot be issued → 54-ФЗ violation
- Payment succeeds but membership is activated without fiscal compliance
- Either block the payment (client experience) or skip the receipt (legal risk)

**Prevention:**
1. **Gate payment initiation on contact data** — `POST /memberships/{id}/pay-online` validates that the client has at least `phone` or `email` before creating the ЮKassa payment object. Return 422 `client_missing_contact_for_receipt` with a descriptive message.
2. **Fallback policy (documented, NOT automatic)** — the owner may manually provide a contact before initiating. The system does NOT silently fall back to the gym's own email — this would be legally incorrect (the receipt must go to the paying customer, not the business).
3. **`clients` schema addition** — add optional `email` field to the `clients` table in v1.7 (separate from `users.email` which is the operator's email). Gate is enforced at service layer, not schema layer (email remains optional for non-paying clients).
4. **Phone preference** — since ЮKassa sends only to email (not SMS), prefer `client.email` over `client.phone` for receipt delivery. If only phone is available: ЮKassa receipt `customer.phone` field populates the receipt record but ЮKassa will not deliver the email (they note "SMS not available") — still legally valid as long as the phone is provided in the fiscal record.

**Warning signs:**
- Payment creation proceeds when `client.email IS NULL AND client.phone IS NULL`
- Gym's own email appears anywhere in the `customer` object of a receipt payload
- No validation error returned when contact is missing

**Phase hint:** Integration phase. Client schema migration for `email` field is a bedrock-level migration requirement.

---

### Pitfall 10: Refund Webhook Dedup + v1.4 Partial UNIQUE Preservation

**Severity:** WARN

**What goes wrong:**
ЮKassa retries `refund.succeeded` webhooks for 24 hours just like payment webhooks. The v1.4 `payments` table has `partial UNIQUE on refund_of WHERE refund_of IS NOT NULL` — this correctly prevents a second DB-level refund row. However, the webhook handler may run twice and emit two `refund_issued` + `payment_refunded` audit events before the DB constraint fires on the second attempt.

Separately: `refund.succeeded` is NOT automatically enabled when setting up a ЮKassa integration — it must be explicitly subscribed to as a separate webhook event. Missing this subscription means refunds are never confirmed server-side.

**Why it happens:**
Assuming refund webhook subscription is implicit; not applying the same Redis dedup gate to `refund.succeeded` that is applied to `payment.succeeded`.

**Consequences:**
- Double audit events for single refund — audit chain becomes ambiguous
- v1.4 `partial UNIQUE` stops the second DB row but exception handling around the IntegrityError must be clean (not swallowed as a generic 500)
- Missing `refund.succeeded` subscription: refund status never transitions, membership never un-activated, fiscal refund receipt never triggered

**Prevention:**
1. **Explicit `refund.succeeded` subscription** — webhook configuration creates subscriptions for: `payment.succeeded`, `payment.canceled`, `payment.waiting_for_capture`, and `refund.succeeded`. Document this as a deployment checklist item.
2. **Same Redis dedup gate** — `SET NX EX 86400 sz:wh:event:refund.succeeded:{refund_id}`. The dedup key uses the ЮKassa refund object ID, not the payment ID.
3. **v1.4 partial UNIQUE remains the DB-level backstop** — `UNIQUE (refund_of) WHERE refund_of IS NOT NULL` catches any dedup bypass. `IntegrityError` → service returns 200 (idempotent). Do NOT raise a 500; a second identical webhook must be acknowledged with 200 to stop ЮKassa retries.
4. **Fiscal refund receipt is part of the refund flow** — a `refund.succeeded` event must trigger a "возврат прихода" receipt via ЮKassa `/receipts`. For full refunds, ЮKassa uses the original payment data automatically. For partial refunds, the receipt data must be in the refund request payload.

**Warning signs:**
- `refund.succeeded` not in the webhook subscription list
- No Redis dedup on refund webhook handler
- `IntegrityError` on second refund webhook causes a 500 rather than a 200

**Phase hint:** Integration phase. Webhook subscription list is a deployment-configuration requirement documented in operator runbook.

---

### Pitfall 11: ARQ Retry Storm on ЮKassa /receipts Rate Limit

**Severity:** WARN

**What goes wrong:**
ЮKassa `/receipts` API may rate-limit under load (specific limits not published, but standard API rate limits apply). If ARQ's `dispatch_receipt` task fails with a 429 or 500 and retries aggressively (default ARQ retry behavior: immediate retry, `max_tries=5`), multiple concurrent `dispatch_receipt` tasks will hammer the ЮKassa endpoint simultaneously, causing a cascade failure. Each retry schedules another retry, amplifying load.

This mirrors the v1.6 email circuit breaker: `sz:email:circuit:{provider}` TTL 5m with atomic `record_failure` pipeline.

**Why it happens:**
Copying ARQ task configuration from simple fire-and-forget tasks without considering external API backpressure.

**Consequences:**
- ЮKassa may blacklist the shop's IP for repeated abusive retries
- All receipts in the queue fail simultaneously rather than one at a time
- ARQ result store fills with failed jobs, obscuring which receipts need manual recovery

**Prevention:**
1. **Redis circuit breaker** — `sz:yookassa:circuit:receipts` with the same atomic pipeline pattern as v1.6 email: `record_failure` increments counter + sets TTL; `is_open` checks counter against threshold (e.g., 5 failures in 60s → open for 300s). `dispatch_receipt` checks circuit before calling ЮKassa.
2. **Exponential backoff** — ARQ task uses `defer_by` on retry: first retry at 30s, second at 120s, third at 600s. Set `max_tries=3` (not 5+).
3. **Dead letter queue** — after `max_tries` exceeded, insert a `fiscal_failed` row in `online_receipts` table and emit a `LOCKED_AUDIT_EVENT` `fiscal_receipt_permanently_failed`. An operator cron alerts on these rows (structlog ERROR + Telegram DM to owner).
4. **Jitter** — add random jitter (±10%) to retry delays to prevent thundering herd across multiple concurrent receipt tasks.

**Warning signs:**
- `max_tries` > 3 without exponential backoff
- No circuit breaker on ЮKassa API calls
- No dead letter / alert mechanism for permanently failed receipts

**Phase hint:** Integration phase. Circuit breaker is the same pattern as v1.6 email; the implementation can be extracted from `app/integrations/email/circuit_breaker.py` and generalized.

---

### Pitfall 12: Audit-Event Chain Ordering — Atomic Commit Scope for Multi-Step Online Payment Flow

**Severity:** WARN

**What goes wrong:**
The v1.4 audit chain is `payment_recorded → membership_sold → membership_activated`. For online payments, the chain is longer: `payment_initiated → yookassa_payment_created → payment_succeeded_webhook → membership_activated → fiscal_receipt_queued → fiscal_receipt_sent`. Each step involves a separate DB write and/or external API call. If step 4 (`membership_activated`) commits but step 5 (`fiscal_receipt_queued`) fails before commit, the system is in a state where membership is active but no receipt task exists — a silent compliance hole.

**Why it happens:**
Each step is independently committed, not wrapped in a single Unit of Work.

**Consequences:**
- Membership active, no fiscal receipt ever sent → 54-ФЗ violation
- Audit chain has gap: `membership_activated` row exists but no `fiscal_receipt_queued` row
- No operational alert for the gap

**Prevention:**
1. **Atomic Unit of Work** — the webhook handler that processes `payment.succeeded` wraps ALL of these in a single `async with session.begin()`:
   - Insert `online_payments` row with `status = 'succeeded'`
   - Activate membership (status transition)
   - Insert `online_receipts` row with `fiscal_status = 'pending'`
   - Emit all LOCKED audit events (payment_succeeded, membership_activated, fiscal_receipt_queued)
   - Enqueue `dispatch_receipt` ARQ task (via `arq.create_pool().enqueue_job(...)` inside the transaction — ARQ enqueue is Redis-based, not transactional, so enqueue inside the `finally` block AFTER the DB commit to avoid phantom tasks on rollback)
2. **Transactional outbox pattern** — the `online_receipts` table row with `fiscal_status = 'pending'` acts as the outbox. The ARQ cron scans for `pending` receipts not yet picked up by the queue and re-enqueues them. This decouples DB durability from ARQ enqueue reliability.
3. **SVC001 AST commit gate** — extend the existing `BusinessService` commit gate to cover `billing_service.py` and ensure all write paths explicitly `await session.commit()`.

**Warning signs:**
- `dispatch_receipt` ARQ task is enqueued BEFORE `session.commit()`
- No `online_receipts` row inserted in the same transaction as membership activation
- Gap between `membership_activated` and `fiscal_receipt_queued` audit events is not monitored

**Phase hint:** Integration phase. UoW discipline is architectural and must be designed before the first webhook handler is built.

---

### Pitfall 13: Official yookassa-sdk-python is Synchronous — Blocks the Event Loop

**Severity:** WARN

**What goes wrong:**
The official ЮKassa Python SDK (`yookassa` on PyPI, maintained by YooMoney) uses the `requests` library internally — it is synchronous. Calling `Payment.create(...)` from a FastAPI async endpoint or ARQ async task will block the entire event loop for the duration of the HTTP call (typically 50–300ms). Under load, this degrades all concurrent requests/tasks.

**Why it happens:**
The official SDK is the most documented option; developers install it without checking if it is async-compatible with their stack.

**Consequences:**
- Event loop blocked during every ЮKassa API call
- ARQ task throughput degraded proportionally to ЮKassa API latency
- Under high load: starvation of all other async work during payment creation

**Prevention:**
1. **Use `async_yookassa`** (`async_yookassa` on PyPI, `proDreams/async_yookassa`) — unofficial but actively maintained; uses `httpx.AsyncClient` natively; supports Pydantic v2; accepts a custom `AsyncClient` instance (injectable for testing with `respx`).
2. **Alternatively, direct `httpx.AsyncClient`** — implement a thin `YookassaHttpClient` wrapper in `app/integrations/yookassa/` that performs raw HTTP Basic Auth calls using the project's own `httpx.AsyncClient`. This avoids third-party SDK coupling and integrates cleanly with `respx` for unit tests.
3. **Never use `asyncio.to_thread(sdk_call)`** as a workaround — while it unblocks the event loop, it creates thread pool pressure and makes testing harder.
4. **import-linter gate** — add a `integrations/yookassa/` module; ban direct imports of the `yookassa` (synchronous) package from `app/` outside this integration module.

**Warning signs:**
- `import yookassa` (the official sync SDK) in any `service.py` or `router.py`
- `from yookassa import Payment` in ARQ task code
- No `async with YookassaClient() as client:` pattern

**Phase hint:** Bedrock phase. SDK choice shapes the integration module design.

---

### Pitfall 14: ЮKassa Credentials in Git — shopId + secretKey Leakage

**Severity:** WARN

**What goes wrong:**
ЮKassa authentication uses HTTP Basic Auth: `shopId` as username, `secretKey` as password. Both are configured via the `yookassa.Configuration` object or passed as request parameters. If hardcoded or committed to `.env` files checked into git, they provide full access to create payments, issue refunds, and retrieve all transaction data.

The v1.6 email integration established the pattern: `YANDEX_SES_ACCESS_KEY_ID` and `YANDEX_SES_SECRET_ACCESS_KEY` as `SecretStr` fields in `app/core/config.py` (Pydantic BaseSettings). The same discipline applies.

**Why it happens:**
Quick local testing with hardcoded test shop credentials; `.env` accidentally committed.

**Consequences:**
- Full financial access to the ЮKassa shop account
- Unauthorized payment creation, refund issuance, transaction data exfiltration

**Prevention:**
1. **Pydantic Settings `SecretStr`** — `YOOKASSA_SHOP_ID: SecretStr` and `YOOKASSA_SECRET_KEY: SecretStr` in `app/core/config.py`. `SecretStr` prevents value from appearing in `repr()`, logs, or Pydantic validation errors.
2. **`.env.example`** — add placeholder values: `YOOKASSA_SHOP_ID=000000` and `YOOKASSA_SECRET_KEY=test_xxx`. `.env` stays in `.gitignore`.
3. **Test/production separation** — ЮKassa provides test shop credentials (`live=false`) that work against a sandbox. All CI tests use test credentials from environment variables injected by CI, never from committed files.
4. **Webhook endpoint secret** (if a future ЮKassa version adds HMAC signing) — add `YOOKASSA_WEBHOOK_SECRET: SecretStr` as a pre-placeholder now, even if unused, to establish the pattern.

**Warning signs:**
- `shopId = "123456"` literal in any Python file
- `.env` file added to git
- `SecretStr` not used for credential fields

**Phase hint:** Bedrock phase. Config additions in the first migration phase.

---

## Minor Pitfalls

### Pitfall 15: Test Infrastructure — No Official ЮKassa ASGI Fixture

**Severity:** INFO

**What goes wrong:**
ЮKassa has no official ASGI transport-compatible test fixture analogous to the project's existing `httpx ASGITransport` pattern. The official Python SDK uses `requests`; there is no `YooKassaASGITransport`. Tests that call real ЮKassa endpoints in CI break on network unavailability and introduce flakiness.

**Prevention:**
1. **`respx` for outgoing ЮKassa API calls** — `respx.mock` patches `httpx.AsyncClient` at the transport layer without network calls. With `async_yookassa` (which accepts a custom `AsyncClient`), inject a `respx`-mocked client into tests: `async with httpx.AsyncClient(transport=respx.MockTransport(...)) as client: ...`
2. **Webhook delivery in tests** — webhook handler tests use `httpx ASGITransport` (already the project standard) to POST the webhook payload directly to `POST /api/v1/billing/webhooks/yookassa`. Construct the payload manually from ЮKassa's documented structure; no need for a real ЮKassa instance.
3. **FSM tests without external calls** — payment FSM state machine tests run against in-memory state with no HTTP calls at all; isolate the FSM logic from HTTP concerns.
4. **Sandbox for manual verification only** — ЮKassa provides a test shop (`shopId = 100500`, `secretKey = test_...`) for manual operator verification phases. Not for automated CI.

**Warning signs:**
- Tests that call `yookassa.ru` directly
- CI tests that depend on network availability
- No `respx` fixtures for ЮKassa outgoing calls

**Phase hint:** Integration phase. Test fixtures are part of the TDD setup for each ЮKassa integration point.

---

### Pitfall 16: LOCKED_AUDIT_EVENTS Not Pre-Registered Before Callsites — v1.3 INFRA-15 Discipline

**Severity:** INFO

**What goes wrong:**
The v1.3 INFRA-15 discipline requires new `LOCKED_AUDIT_EVENTS` entries to be pre-registered in the frozenset BEFORE any callsite that uses them. For v1.7, online payment events will be: `payment_initiated`, `yookassa_payment_created`, `payment_succeeded`, `payment_failed`, `payment_canceled`, `membership_activated_online`, `refund_initiated`, `yookassa_refund_created`, `refund_succeeded`, `fiscal_receipt_queued`, `fiscal_receipt_sent`, `fiscal_receipt_failed`. At minimum 12 new event strings.

If a developer adds a callsite that uses a new event string before adding it to the frozenset, the AST gate CI check fails and blocks the entire PR chain.

**Prevention:**
1. **First commit of v1.7 bedrock phase** extends `LOCKED_AUDIT_EVENTS` frozenset with all 12+ online-payment event strings — before any callsite exists.
2. **Naming convention** — online payment events use `payment_*` prefix; fiscal events use `fiscal_receipt_*` prefix; no collision with existing `membership_*` events.
3. **Count test** — extend the existing `len(LOCKED_AUDIT_EVENTS) == N` assertion in tests to the new expected count after bedrock phase.

**Warning signs:**
- `audit.emit("payment_succeeded", ...)` callsite in service code before the frozenset includes `"payment_succeeded"`
- CI gate fails with "unknown audit event string" error

**Phase hint:** Bedrock phase, first task.

---

### Pitfall 17: Telegram WebApp Payments — Separate Pitfall Set, Defer to Post-v1.7

**Severity:** INFO (DEFER)

**What goes wrong:**
Telegram WebApp payments (Telegram Stars, TON, or direct card payments via Telegram Pay) use a completely different integration: `initData` verification (HMAC-SHA256 of `window.Telegram.WebApp.initData`), invoice creation via `bot.send_invoice()`, `pre_checkout_query` handling, and `successful_payment` update processing. Currency is in Stars (integer) or kopecks depending on provider. This is an entirely separate integration from ЮKassa redirect/webhook flow.

**Prevention:**
- Defer Telegram WebApp payments to v1.8+ or a separate milestone
- v1.7 scope is strictly ЮKassa redirect flow for the admin panel (reception/owner initiating payment on behalf of client)
- If Telegram self-service payment is needed later, the `initData` HMAC verification pattern is NOT the same as ЮKassa IP validation — document separately

**Warning signs:**
- `successful_payment` update handler added to `telegram_bot.py` in v1.7
- Any `Telegram.WebApp` JavaScript in the admin panel during v1.7

**Phase hint:** DEFER. Not in v1.7 scope.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Bedrock — migrations + event registration | Missing `LOCKED_AUDIT_EVENTS` pre-registration | First commit: extend frozenset before any service code |
| Bedrock — currency converter | Off-by-100 kopecks/rubles conversion | Dedicated converter module + unit tests before payment creation |
| Bedrock — SDK choice | Official sync SDK blocking event loop | Mandate `async_yookassa` or direct `httpx.AsyncClient` wrapper |
| Bedrock — config | Credentials in git | `SecretStr` fields added to `app/core/config.py` in bedrock phase |
| Integration — payment creation | Double-tap parallel payments | Deterministic `Idempotency-Key` + DB partial UNIQUE |
| Integration — webhook handler | IP validation after body parse | IP check middleware runs before `request.json()` — import-linter or AST gate |
| Integration — webhook handler | No Redis dedup | `SET NX EX 86400` on `(event_type, object.id)` before any DB write |
| Integration — return URL | Membership activated on redirect | return_url handler is read-only status screen; activation only on webhook |
| Integration — return URL | Payment status oracle via URL | Single return URL, `_constant_time_floor` pattern, no `?status=` param |
| Integration — receipt | Wrong payment_subject/payment_mode | Locked `Literal` constants; owner sign-off record |
| Integration — receipt | Client missing email/phone | Gate payment initiation on contact data; clear 422 error |
| Integration — receipt | Receipt timing violation | Priority queue + Scenario 1 (embed receipt in payment payload) |
| Integration — refund | Missing `refund.succeeded` subscription | Explicit subscription in deployment runbook |
| Integration — refund | Double audit on refund webhook retry | Same Redis dedup gate; `IntegrityError` → 200 (not 500) |
| Verification | No ЮKassa ASGI fixture | `respx` for outgoing + `ASGITransport` for incoming webhooks |
| Verification | ARQ receipt retry storm | Circuit breaker test with `respx` simulating 429 from ЮKassa |

---

## Sources

- [ЮKassa Webhooks documentation](https://yookassa.ru/developers/using-api/webhooks) — IP ranges, retry behavior, no HMAC (HIGH confidence, official)
- [ЮKassa Interaction Format](https://yookassa.ru/developers/using-api/interaction-format) — Idempotence-Key header, 24h window (HIGH confidence, official)
- [ЮKassa 54-ФЗ receipts (YooMoney path)](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/basics) — receipt API overview (HIGH confidence, official)
- [ЮKassa receipt parameter values](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/parameters-values) — payment_subject, payment_mode values (HIGH confidence, official)
- [ЮKassa third-party receipt basics](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/basics) — timing scenarios, 5-minute window, failure handling (HIGH confidence, official)
- [ЮKassa refund receipts](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/refunds) — возврат прихода, full vs partial refund (HIGH confidence, official)
- [54-ФЗ receipt timing analysis (klerk.ru)](https://www.klerk.ru/buh/articles/476136/) — 5-minute tolerance on clock, not on issuance; "at the moment of payment" (MEDIUM confidence, verified analyst source)
- [Electronic receipt delivery requirements](https://astral.ru/info/operator-fiskalnykh-dannykh/otpravka-elektronnogo-cheka-klientu/) — email/phone mandatory; no gym-email fallback (MEDIUM confidence)
- [async_yookassa (GitHub)](https://github.com/proDreams/async_yookassa) — httpx-based async ЮKassa client (MEDIUM confidence, community-maintained)
- [respx documentation](https://lundberg.github.io/respx/) — httpx mock transport for testing (HIGH confidence, official)
- [ЮKassa Python SDK (official)](https://github.com/yoomoney/yookassa-sdk-python) — synchronous requests-based SDK (HIGH confidence, official)
