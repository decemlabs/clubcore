# Feature Landscape: v1.7 Online Payments (ЮKassa) + 54-ФЗ Fiscal Receipts

**Domain:** Online payment intake + fiscal compliance for single-gym CRM (РФ/СНГ market)
**Researched:** 2026-05-21
**Milestone context:** Adding ЮKassa payment intake and 54-ФЗ fiscal receipts to existing Sportzal CRM.
  Existing bedrock: v1.4 cash ledger (append-only `payments` table, `payment_recorder` Protocol slot,
  `Idempotency-Key`, full-only refund discipline, atomic audit chain), v1.6 cross-channel notifications
  (Telegram + email with `channel` discriminator idempotency), v1.6 email integration (Yandex Postbox,
  `LOCKED_EMAIL_TEMPLATES`, circuit breaker).

---

## PAYMENT — Online Payment Intake

### PAY-01: Server-side payment creation (redirect confirmation)
- **Category:** Table stake
- **Complexity:** MED
- **Dependency:** v1.4 `payment_recorder` Protocol slot; `Idempotency-Key` discipline already established
- **Description:** `POST /api/v1/memberships/{id}/pay-online` and `POST /api/v1/pt-packages/{id}/pay-online`
  create a ЮKassa payment object via `POST /v3/payments` (HTTP Basic Auth: shop_id + secret_key).
  Confirmation type `redirect` — API returns `confirmation.confirmation_url`; CRM redirects client browser
  there. After client action ЮKassa redirects back to `return_url`. Membership/package is credited ONLY
  on `payment.succeeded` webhook (never on redirect return). `Idempotency-Key` = UUIDv4 stored in local
  `online_payments` row before the ЮKassa call so retry on network error returns same result.
- **ЮKassa states:** `pending` (initial) → `succeeded` (final) or `canceled` (final). Single-stage flow
  skips `waiting_for_capture`.
- **Sources:** HIGH confidence — official yookassa.ru/developers/payment-acceptance/getting-started/payment-process

### PAY-02: Embedded checkout widget
- **Category:** Differentiator
- **Complexity:** MED
- **Dependency:** PAY-01 (requires payment token from server); admin-web must load ЮKassa JS SDK
- **Description:** ЮKassa provides a JS widget (`YooMoneyCheckoutWidget`) that embeds directly on the
  admin-web page or in a modal. Accepts bank cards, Mir Pay, SberPay, T-Pay, СБП, ЮMoney. No page
  redirect — widget handles 3-D Secure internally. On success widget displays 10-second confirmation
  then redirects to `return_url`. Improves UX for reception desk flow where a separate tab redirect is
  disruptive.
  Confirmation type: `embedded` (not `redirect`).
- **Sources:** HIGH confidence — yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/basics

### PAY-03: QR / SBP payment
- **Category:** Differentiator
- **Complexity:** LOW
- **Dependency:** PAY-01; display layer only
- **Description:** Confirmation type `qr` — server returns `confirmation.confirmation_data` (QR payload).
  CRM renders QR code (any library). Client scans with bank app. Fires `payment.succeeded` webhook on
  completion. Useful for mobile-first reception desk (client scans instead of entering card).
- **Sources:** HIGH confidence — ЮKassa `confirmation_type` docs; SBP QR equated to card payment under
  54-ФЗ as of Sept 2025.

### PAY-04: Telegram WebApp native invoice
- **Category:** Anti-feature (v1.7)
- **Complexity:** HIGH
- **Dependency:** Telegram Bot Payments API (separate `sendinvoice` flow); no `waiting_for_capture`
  support; cannot configure payment holds
- **Description:** ЮKassa does support Telegram Bot Payments API (`sendinvoice` → `answerPreCheckoutQuery`
  → `SuccessfulPayment` update). However this flow is entirely separate from the REST payment API:
  no `waiting_for_capture`, no autopayments, no receipt injection via ЮKassa API — receipt must be
  sent separately. The CRM admin panel is a web SPA, not a Telegram Mini App. Reception desk does not
  use Telegram-native invoices for selling memberships.
  DO NOT implement in v1.7. Existing Telegram bot covers check-in and bookings; payment via bot is
  a separate product feature for a later milestone.
- **Sources:** MEDIUM confidence — yookassa.ru/docs/support/payments/onboarding/integration/cms-module/telegram

### PAY-05: Mobile application deep-link confirmation
- **Category:** Anti-feature (v1.7)
- **Complexity:** MED
- **Dependency:** Mobile app not in scope
- **Description:** Confirmation type `mobile_application` redirects to bank app deep-link for
  confirmation. Only relevant for a native mobile client app. Sportzal v1.7 is admin-web SPA only.
  Defer until a client-facing mobile app is built.
- **Sources:** HIGH confidence — ЮKassa confirmation_type docs

---

## WEBHOOK — Payment FSM

### WH-01: Webhook endpoint with IP whitelist + object re-fetch verification
- **Category:** Table stake
- **Complexity:** MED
- **Dependency:** None (new module `app/modules/billing/webhooks.py`)
- **Description:** `POST /api/v1/webhooks/yookassa` receives ЮKassa notifications.
  Security model (two-layer defense-in-depth):
  1. IP source check against ЮKassa published CIDR list:
     `185.71.76.0/27, 185.71.77.0/27, 77.75.153.0/25, 77.75.156.11, 77.75.156.35,
      77.75.154.128/25, 2a02:5180::/32`
  2. Re-fetch payment/refund object from ЮKassa API after receiving webhook and verify status
     matches notification payload (defends against spoofed IP, replay, and stale notifications).
  ЮKassa does NOT provide `Notification-Sign` HMAC header — IP whitelist + re-fetch is the canonical
  ЮKassa security model (confirmed in official webhook docs). Respond HTTP 200 immediately; process
  asynchronously. ЮKassa retries for 24 hours on non-200 response.
  Must be exempt from CSRF middleware (external caller). Must NOT require auth cookie.
- **Sources:** HIGH confidence — yookassa.ru/developers/using-api/webhooks

### WH-02: Payment FSM mapping (`pending` → `succeeded` / `canceled`)
- **Category:** Table stake
- **Complexity:** LOW
- **Dependency:** WH-01, PAY-01, v1.4 `payments` table
- **Description:** Internal `online_payments.status` maps to ЮKassa payment statuses:

  | ЮKassa status          | Internal event               | Action                                          |
  |------------------------|------------------------------|-------------------------------------------------|
  | `pending`              | payment_initiated            | Row created; no ledger entry yet                |
  | `waiting_for_capture`  | payment_awaiting_capture     | Two-stage only (not used in v1.7 single-stage)  |
  | `succeeded`            | payment_online_succeeded     | Call `payment_recorder`; credit membership/pkg  |
  | `canceled`             | payment_online_canceled      | Mark row canceled; no ledger entry              |

  `payment.succeeded` is the ONLY trigger for crediting membership or PT-package.
  Idempotency: UNIQUE constraint on `(yookassa_payment_id)` in `online_payments` table prevents
  double-processing. On duplicate webhook: return 200, skip.
- **Sources:** HIGH confidence — ЮKassa payment-process docs

### WH-03: Refund FSM mapping (`refund.succeeded`)
- **Category:** Table stake
- **Complexity:** LOW
- **Dependency:** WH-01, REFUND-01
- **Description:** ЮKassa refund statuses:
  - `succeeded` (final, positive) → fires `refund.succeeded` webhook
  - `canceled` (final, negative) → fires no webhook; must poll or handle timeout

  Internal mapping:

  | ЮKassa refund status | Internal event            | Action                                               |
  |----------------------|---------------------------|------------------------------------------------------|
  | `succeeded`          | refund_online_succeeded   | Complete v1.4 atomic audit chain (mirrors cash path) |
  | `canceled`           | refund_online_canceled    | Alert operator; membership stays credited            |

  Note: `refund.succeeded` webhook is NOT auto-enabled — must be explicitly subscribed during
  ЮKassa account setup. This is a known pitfall.
- **Sources:** HIGH confidence — yookassa.ru/developers/using-api/webhooks + refunds docs

### WH-04: Idempotent webhook processing
- **Category:** Table stake
- **Complexity:** LOW
- **Dependency:** WH-01, Redis (already in stack)
- **Description:** Each webhook notification carries a unique `object.id` (payment or refund UUID).
  Processing must be idempotent:
  1. Check Redis key `sz:webhook:{event_type}:{object_id}` (TTL 48h) — if present, return 200 skip.
  2. Process event transactionally.
  3. Set Redis key on success.
  Mirrors `_dedupe_update_id` pattern from v1.2 Telegram bot. Prevents double-credit on webhook
  delivery retry.
- **Sources:** MEDIUM confidence — pattern inference from ЮKassa retry behavior + v1.2 precedent

---

## REFUND — Online Refunds

### REF-01: Online refund initiation (full only, v1.7)
- **Category:** Table stake
- **Complexity:** MED
- **Dependency:** v1.4 `payments` table + `refund_of` partial UNIQUE; WH-03; RBAC (reception+owner)
- **Description:** `POST /api/v1/memberships/{id}/refund` (and pt-packages equivalent) — if the payment
  was made online, routes to ЮKassa Refund API `POST /v3/refunds` with `payment_id` and full `amount`.
  `Idempotency-Key` = new UUIDv4 stored before the API call.
  Flow: CRM creates refund request → ЮKassa processes → `refund.succeeded` webhook arrives →
  CRM completes v1.4 atomic audit chain (`payment_recorded → refund_issued → payment_refunded →
  membership_refunded`) with `payment_row_hash`.
  Payment MUST be in `succeeded` status to initiate refund (enforced by both CRM and ЮKassa API).
  Refund window: up to 3 years (cards); up to 1 year (Sberbank).
- **Sources:** HIGH confidence — yookassa.ru/developers/payment-acceptance/after-the-payment/refunds

### REF-02: Partial online refund
- **Category:** Anti-feature (v1.7)
- **Complexity:** HIGH
- **Dependency:** v1.4 B-02 (partial refund) still deferred
- **Description:** ЮKassa API supports partial refunds (send partial `amount` in refund request).
  However v1.4 deliberately deferred partial refund (B-02) for both cash and online flows. The
  constraint `partial UNIQUE on refund_of` allows only one refund per payment row by design.
  DO NOT implement partial online refund in v1.7 — this would require coordinating amount split
  with membership partial-cancel semantics that are not yet designed. Defer to v1.8+.
- **Sources:** HIGH confidence — v1.4 design doc + ЮKassa refunds API

### REF-03: Refund timeout / cancellation handling
- **Category:** Table stake
- **Complexity:** LOW
- **Dependency:** REF-01
- **Description:** If `refund.succeeded` webhook does not arrive within N minutes (suggest 30 min),
  ARQ task polls ЮKassa `GET /v3/refunds/{refund_id}` to check current status. If `canceled`:
  emit `refund_online_failed` audit event, notify operator via Telegram + email DM.
  Membership/package is NOT revoked — the original sale stands until refund is confirmed.
  This covers the case where ЮKassa rejects the refund (e.g., acquirer refusal >15 months for cards).
- **Sources:** MEDIUM confidence — ЮKassa refund behavior docs + industry pattern

---

## FISCAL — 54-ФЗ Fiscal Receipts

### FIS-01: Receipt delivery mechanism choice
- **Category:** Table stake (legal requirement)
- **Complexity:** LOW (decision only)
- **Dependency:** None
- **Description:** Two options exist:
  1. **Чеки от ЮKassa** (ЮKassa's built-in receipt service) — ЮKassa acts as the cloud cash register.
     Zero setup cost, included in commission, no separate fiscal accumulator, connects within 1 day.
     Limitation: delivery via EMAIL ONLY (no SMS). Requires client email.
  2. **Third-party cash register** (АТОЛ-Онлайн, Чек.ОФД, etc.) — CRM sends receipt data to ЮKassa
     which relays to the external cash register. More control, supports phone/SMS delivery.

  RECOMMENDATION: Use "Чеки от ЮKassa" for v1.7. Lowest integration complexity, no separate
  fiscal accumulator contract, covers the legally required ОФД path. Accept email-only constraint
  (aligns with v1.6 email integration already in place).
- **Sources:** HIGH confidence — yookassa.ru/54fz/ + yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/basics

### FIS-02: Receipt sent alongside payment (simultaneous scenario)
- **Category:** Table stake (legal requirement)
- **Complexity:** MED
- **Dependency:** FIS-01; PAY-01; client must have email on record
- **Description:** Include `receipt` object in the `POST /v3/payments` creation request.
  ЮKassa registers receipt with ОФД simultaneously with payment authorization.
  This is the simplest and legally safest path: receipt is always tied to the payment event.

  Mandatory receipt fields (confirmed via ЮKassa docs):
  - `customer.email` — client email (REQUIRED for "Чеки от ЮKassa"; no SMS fallback)
  - `items[]` — array of receipt line items, each with:
    - `description` — human-readable name (e.g., "Абонемент Безлимит 30 дней")
    - `quantity` — 1.00 for memberships/packages
    - `amount.value` — price
    - `amount.currency` — "RUB"
    - `vat_code` — 1 (НДС не облагается / без НДС) for ИП on УСН; verify with accountant
    - `payment_subject` — `"service"` for memberships and PT-packages (услуга; confirmed for
      online gym service sales)
    - `payment_mode` — `"full_payment"` when client pays full amount at moment of sale;
      `"full_prepayment"` if the membership hasn't started yet (future start date).
      For standard same-day membership sales: `"full_payment"`. For advance booking: `"full_prepayment"`.
  - `tax_system_code` — matches merchant's tax regime (2 = УСН доходы; 3 = УСН доходы-расходы;
    6 = ПСН; etc.)

  54-ФЗ timing: the law does not specify a hard second/minute limit for online payments.
  "Момент расчёта" is defined by the merchant in their public offer (terms).
  Simultaneous scenario satisfies the legal requirement because ОФД gets the receipt data
  at the time of payment creation — before the client confirms payment.
  The "5-minute rule" is a myth based on misreading a 2013 FNS letter.
- **Sources:** HIGH confidence — ЮKassa receipt docs; MEDIUM confidence on timing rule (kassa.komtet.ru)

### FIS-03: Receipt status FSM + idempotency
- **Category:** Table stake
- **Complexity:** MED
- **Dependency:** FIS-01, FIS-02; mirrors v1.6 `channel` discriminator pattern
- **Description:** Receipt registration tracked in `fiscal_receipts` table (new):
  - UNIQUE `(payment_id, kind)` where `kind` IN `('payment', 'refund')` — mirrors v1.6 cross-channel
    idempotency pattern. Prevents double-send on webhook retry.
  - `status` column: `pending` → `succeeded` | `canceled`
    - `pending`: receipt queued for ОФД registration
    - `succeeded`: ОФД confirmed registration
    - `canceled`: registration failed (ЮKassa gives up; contact support)
  - Check `receipt_registration` field on payment object response — `pending` / `succeeded` / `canceled`
  - If `canceled` after >3 days: trigger alert to operator (structlog ERROR + Telegram DM to owner)
  - Receipt failure must NOT block or rollback payment — payment commit is atomic, fiscal send is
    best-effort (mirrors v1.6 `EMAIL_PAYMENT_RECEIPT_*` pattern already shipping).
- **Sources:** HIGH confidence — ЮKassa receipt status docs (pending/succeeded/canceled confirmed)

### FIS-04: Refund receipt (возврат прихода)
- **Category:** Table stake (legal requirement)
- **Complexity:** LOW
- **Dependency:** FIS-01, REF-01
- **Description:** When a refund succeeds, a refund receipt (возврат прихода) MUST be sent to the client
  and ОФД. For "Чеки от ЮKassa": include `receipt` object in refund creation request (`POST /v3/refunds`)
  with same item structure as payment receipt. Same `customer.email` requirement.
  `kind='refund'` in `fiscal_receipts` table, UNIQUE `(payment_id, 'refund')`.
  Items must mirror the original payment receipt items.
- **Sources:** HIGH confidence — yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/basics

### FIS-05: Client has no email — pre-validation gate
- **Category:** Table stake
- **Complexity:** LOW
- **Dependency:** FIS-01, FIS-02; v1.1 Clients CRUD
- **Description:** "Чеки от ЮKassa" requires `customer.email` in every receipt. If client has no email
  on record, the online payment flow must be blocked at the point of sale (before creating ЮKassa
  payment object), not at receipt generation time.
  Error response: `422 Unprocessable Entity` with `code: "client_email_required_for_online_payment"`.
  Reception must add email to client record first.
  DO NOT use phone as fallback — "Чеки от ЮKassa" does not support SMS delivery (email-only).
  If third-party cash register is adopted later (FIS-01 alternative), phone becomes valid. Flag this
  as a future relaxation point.
- **Sources:** HIGH confidence — ЮKassa receipt docs (email-only for ЮKassa receipts, confirmed)

### FIS-06: VAT code and tax system configuration
- **Category:** Table stake (legal requirement)
- **Complexity:** LOW
- **Dependency:** FIS-02; deployment config
- **Description:** `vat_code` and `tax_system_code` must match the gym's actual tax regime.
  For most small gyms (ИП or ООО) on УСН: `vat_code=1` (без НДС), `tax_system_code=2` (УСН доходы)
  or `tax_system_code=3` (УСН доходы-расходы). From Jan 2025 УСН entities that cross the VAT
  threshold (60M RUB revenue) must indicate 5% or 7% VAT — but a single gym CRM at MVP scale will
  not hit this threshold. Configure as environment variables, NOT hardcoded in source.
  Provide `YOOKASSA_TAX_SYSTEM_CODE` and `YOOKASSA_VAT_CODE` in `.env.example`.
- **Sources:** MEDIUM confidence — search results + ЮKassa parameter-values docs

---

## NOTIFY — Cross-Channel Payment Notifications

### NOT-01: Payment success DM (Telegram + email)
- **Category:** Table stake
- **Complexity:** LOW
- **Dependency:** v1.6 dual-channel notification infrastructure; `LOCKED_EMAIL_TEMPLATES` ladder
- **Description:** On `payment.succeeded` webhook processing: emit Telegram DM + email notification
  to client. Content: payment amount, membership/package name, validity period.
  New locked templates: `PAYMENT_ONLINE_SUCCESS_TG` + `EMAIL_PAYMENT_ONLINE_SUCCESS`.
  Use v1.6 `channel` discriminator on `payment_notifications` idempotency table (new table mirrors
  `membership_notifications` pattern). UNIQUE `(payment_id, channel)`.
  Best-effort: send failure does NOT rollback payment commit (v1.6 discipline).
- **Sources:** HIGH confidence (pattern from v1.6 `EMAIL_PAYMENT_RECEIPT_*`)

### NOT-02: Refund success DM (Telegram + email)
- **Category:** Table stake
- **Complexity:** LOW
- **Dependency:** NOT-01; REF-01; WH-03
- **Description:** On `refund.succeeded` webhook: emit Telegram DM + email to client.
  Content: refunded amount, membership/package name.
  New locked templates: `REFUND_ONLINE_SUCCESS_TG` + `EMAIL_REFUND_ONLINE_SUCCESS`.
  Same `(payment_id, channel)` idempotency row, `kind='refund'`.
- **Sources:** HIGH confidence (pattern from v1.4 + v1.6 precedent)

### NOT-03: Fiscal receipt email (from ЮKassa, not from CRM)
- **Category:** Table stake
- **Complexity:** LOW (configuration, not code)
- **Dependency:** FIS-01, FIS-02
- **Description:** When "Чеки от ЮKassa" is used, ЮKassa itself sends the fiscal receipt to the
  client's email directly from its system. This is separate from the CRM's payment-success email
  (NOT-01). The CRM's email (NOT-01) is a business confirmation; the ЮKassa email is the legal
  fiscal document. No CRM code needed for fiscal email delivery — just ensure `customer.email` is
  passed correctly in the receipt object.
- **Sources:** HIGH confidence — ЮKassa receipts docs

### NOT-04: Operator alert on fiscal receipt failure
- **Category:** Table stake
- **Complexity:** LOW
- **Dependency:** FIS-03; structlog; Telegram bot (owner-only DM)
- **Description:** If `fiscal_receipts.status` transitions to `canceled` (ЮKassa gave up on ОФД
  registration), alert the owner:
  1. structlog ERROR with `payment_id`, `client_id`, `amount`
  2. Telegram DM to owner: "Чек не зарегистрирован в ОФД. Платёж: {amount}. Клиент: {name}."
  This is a legal obligation — merchant must ensure receipt reaches ОФД. Operator must contact
  ЮKassa support to resolve.
- **Sources:** MEDIUM confidence — ЮKassa docs note "contact support if receipt stays pending >3 days"

### NOT-05: Operator alert on payment cancellation
- **Category:** Differentiator
- **Complexity:** LOW
- **Dependency:** WH-02
- **Description:** On `payment.canceled` webhook: log the `cancellation_details.reason` from
  ЮKassa response (e.g., `insufficient_funds`, `card_expired`, `3d_secure_failed`). No DM to client
  (they see the result in the ЮKassa redirect page). Optionally: if initiated by reception, show
  toast in admin-web. Audit event `payment_online_canceled` with cancellation reason in payload.
- **Sources:** MEDIUM confidence — ЮKassa cancellation details docs (inferred from search)

---

## DIFFERENTIATOR FEATURES (Defer)

### DIFF-01: Recurring autopayments (рекуррентные платежи / saved cards)
- **Category:** Differentiator
- **Complexity:** HIGH
- **Dependency:** ЮKassa manager approval required for production; PAY-01; user consent flow
- **Description:** ЮKassa supports saving card via `save_payment_method: true` on first payment.
  Subsequent charges use `payment_method_id`. Merchant must:
  1. Contact ЮKassa manager to enable autopayments on live account
  2. Implement user consent flow (legal requirement under 54-ФЗ + Visa/MC rules)
  3. Build subscription schedule management (when to charge, how to cancel)
  High legal + implementation complexity. v1.7 reception desk sells memberships manually — no
  self-service client portal yet. Defer to v2.0+ when client-facing app exists.
- **Sources:** HIGH confidence — ЮKassa recurring-payments docs

### DIFF-02: Refund without original card (client lost card)
- **Category:** Differentiator
- **Complexity:** MED
- **Dependency:** ЮKassa account configuration; payout module
- **Description:** ЮKassa supports refunds to a different card or bank account via the Payout API,
  but this requires a separate Payout agreement with ЮKassa. Standard refund always goes to
  original payment method. For v1.7, standard refund (to original method) is sufficient.
  Defer card-change refund to later milestone.
- **Sources:** MEDIUM confidence — inferred from ЮKassa refund limitations docs

---

## ANTI-FEATURES (Explicit Exclusions for v1.7)

| Anti-Feature | Why Avoid | What to Do Instead |
|---|---|---|
| Partial online refund | B-02 still deferred in v1.4; membership partial-cancel semantics undefined | Full refund only in v1.7 |
| Telegram WebApp native invoice | Different API path, no receipt injection, no holds; admin SPA not a Telegram Mini App | Use redirect/widget for reception desk |
| Mobile-app deep-link confirmation | No mobile app in scope | Redirect or widget for web |
| Recurring autopayments | Requires ЮKassa manager activation + client consent flow + portal | Defer to v2.0 client portal |
| Third-party cash register (АТОЛ etc.) | Higher setup complexity; email-only is sufficient for v1.7 | ЮKassa built-in receipts |
| SMS receipt delivery | Not supported by "Чеки от ЮKassa" | Email only (require email on client record) |
| `waiting_for_capture` two-stage flow | Unnecessary complexity for single-stage membership sale | Single-stage `pending → succeeded` |
| Partial VAT (5%/7%) calculation | Only applies when УСН revenue >60M RUB; not relevant for single gym MVP | Simple `vat_code=1` (no VAT) + env var for future change |
| Payout / split payments | Not needed for single-gym, single-merchant model | Standard single-merchant integration |

---

## Feature Dependencies

```
PAY-01 (server payment creation)
  → WH-01 (webhook endpoint)
    → WH-02 (payment FSM)
      → v1.4 payment_recorder (credit membership/pkg)
        → NOT-01 (payment success DM)
    → WH-03 (refund FSM)
      → REF-01 (online refund)
        → NOT-02 (refund DM)
        → FIS-04 (refund receipt)
  → FIS-02 (receipt in payment creation)
    → FIS-01 (receipt mechanism choice — must decide before PAY-01)
    → FIS-05 (client email gate)
    → FIS-06 (VAT/tax config)
    → FIS-03 (receipt status FSM + idempotency)
      → NOT-03 (fiscal email — auto from ЮKassa)
      → NOT-04 (operator alert on failure)

PAY-02 (widget) → PAY-01
PAY-03 (QR/SBP) → PAY-01
```

---

## MVP Recommendation for v1.7

**Must implement (legal + commercial table stakes):**
1. FIS-01: Choose "Чеки от ЮKassa" receipt mechanism
2. FIS-05: Client email validation gate before creating payment
3. FIS-06: Tax system + VAT code environment config
4. PAY-01: Server-side payment creation with redirect confirmation
5. WH-01: Webhook endpoint (IP whitelist + re-fetch verification)
6. WH-02: Payment FSM (pending → succeeded/canceled)
7. WH-03: Refund FSM (refund.succeeded)
8. WH-04: Idempotent webhook processing
9. FIS-02: Receipt sent alongside payment
10. FIS-03: Receipt status FSM + `fiscal_receipts` table
11. FIS-04: Refund receipt
12. REF-01: Online refund (full only)
13. REF-03: Refund timeout/poll fallback
14. NOT-01: Payment success DM (Telegram + email)
15. NOT-02: Refund success DM (Telegram + email)
16. NOT-03: Fiscal receipt email (configuration, not code)
17. NOT-04: Operator alert on fiscal failure

**Implement if time allows (differentiators that are LOW complexity):**
- PAY-03: QR/SBP confirmation type (mostly display-layer work)
- NOT-05: Operator alert on payment cancellation with reason logging

**Defer:**
- PAY-02: Widget (MED complexity, frontend work; can ship with redirect in v1.7)
- DIFF-01: Recurring autopayments (HIGH complexity + external approval)
- DIFF-02: Refund without card (separate payout agreement needed)

---

## Failure Mode Catalogue

### FM-01: Webhook arrives but DB is down
**What happens:** HTTP handler cannot write to Postgres.
**Industry norm:** Return HTTP 503 (non-200). ЮKassa retries for 24 hours with backoff.
**Mitigation:** Respond 503 on DB connection failure; do not swallow exception. Once DB recovers,
next ЮKassa retry delivers the notification. No outbox pattern needed — ЮKassa IS the outbox.
**Risk:** If DB is down >24h, webhook delivery stops. Mitigation: ARQ poll task on `online_payments`
rows stuck in `pending` status for >30 min (re-fetch from ЮKassa API).
**Confidence:** MEDIUM (24h window confirmed in ЮKassa docs; poll fallback is industry pattern)

### FM-02: ЮKassa `/receipts` registration fails after payment succeeded
**What happens:** `receipt_registration = 'canceled'` on payment object.
**Legal risk:** Merchant is in violation of 54-ФЗ if receipt never reaches ОФД.
**Mitigation:** Monitor `fiscal_receipts.status`; if `canceled`, emit structlog ERROR and owner DM
(NOT-04). Operator must manually contact ЮKassa support. Payment is NOT rolled back —
54-ФЗ violation is an administrative issue, not a payment integrity issue.
**Confidence:** HIGH (ЮKassa docs explicitly state "payment unaffected by receipt failure")

### FM-03: Client provides no email
**What happens:** Receipt cannot be sent; "Чеки от ЮKassa" requires email.
**Mitigation:** FIS-05 gate blocks online payment creation at API level with 422.
Reception must update client record before retrying.
**Confidence:** HIGH (email-only confirmed for "Чеки от ЮKassa")

### FM-04: Duplicate `payment.succeeded` webhook
**What happens:** ЮKassa retries webhook if merchant responds non-200 (e.g., during processing).
**Mitigation:** WH-04 Redis dedup key `sz:webhook:payment.succeeded:{payment_id}` (TTL 48h).
DB-level UNIQUE on `(yookassa_payment_id)` in `online_payments` as second guard.
**Confidence:** HIGH (ЮKassa 24h retry + Redis dedup pattern from v1.2)

### FM-05: `refund.succeeded` webhook not received
**What happens:** Refund succeeded at ЮKassa side but CRM never gets the webhook.
**Mitigation:** REF-03 ARQ poll after 30 min on refunds stuck in `pending` status.
**Confidence:** MEDIUM (poll pattern is standard; timing tunable)

### FM-06: ЮKassa API call fails (5xx or network timeout) during payment creation
**What happens:** CRM created `online_payments` row but ЮKassa payment object not created.
**Mitigation:** Same `Idempotency-Key` on retry gives same ЮKassa result if they received it.
If ЮKassa never received it: new attempt with same key is a new request after 24h (ЮKassa TTL).
Store `yookassa_payment_id` as nullable; NULL = creation pending. ARQ cleanup task marks
stuck `pending` rows (no `yookassa_payment_id` after 5 min) as `failed`.
**Confidence:** MEDIUM (idempotency behavior confirmed; cleanup pattern is standard)

---

## Sources

- [ЮKassa Payment Process FSM](https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process) — HIGH confidence
- [ЮKassa Webhooks](https://yookassa.ru/developers/using-api/webhooks) — HIGH confidence
- [ЮKassa Checkout Widget](https://yookassa.ru/developers/payment-acceptance/integration-scenarios/widget/basics) — HIGH confidence
- [ЮKassa Refunds](https://yookassa.ru/developers/payment-acceptance/after-the-payment/refunds) — HIGH confidence
- [ЮKassa Recurring Payments Basics](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments/basics) — HIGH confidence
- [ЮKassa Receipts (ЮKassa's own)](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/basics) — HIGH confidence
- [ЮKassa Receipt Parameters (third-party)](https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/parameters-values) — HIGH confidence
- [ЮKassa 54-ФЗ Solutions](https://yookassa.ru/54fz/) — HIGH confidence
- [ЮKassa API Interaction Format (idempotency)](https://yookassa.ru/developers/using-api/interaction-format) — HIGH confidence
- [54-ФЗ Receipt Timing Myth](https://kassa.komtet.ru/blog/moment-rascheta) — MEDIUM confidence
- [Confirmation Types (redirect/embedded/qr/mobile)](https://yookassa.ru/developers/payment-acceptance/overview) — HIGH confidence (inferred from search snippet)
