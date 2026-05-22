# Milestone v1.7 Requirements — Online Payments + 54-ФЗ

**Status:** Active
**Phase numbering:** continues from v1.6 → Phase 47 onward
**Source:** `.planning/research/SUMMARY.md` + PROJECT.md "Current Milestone: v1.7"
**Scope confirmation:** All 9 categories in v1.7; PAY-03 (QR/SBP) + NOT-05 (cancellation reason) included as differentiators (2026-05-21)

---

## v1.7 Requirements

### INFRA (Bedrock — Phase 47)

- [ ] **INFRA-34**: `LOCKED_AUDIT_EVENTS` frozenset extended with ~9 new v1.7 event identifiers (`online_payment_initiated`, `yookassa_payment_created`, `online_payment_succeeded`, `online_payment_canceled`, `online_payment_refunded`, `fiscal_receipt_dispatched`, `fiscal_receipt_succeeded`, `fiscal_receipt_failed`, `yookassa_webhook_received`) registered BEFORE any callsite (v1.3 INFRA-15 discipline preserved)
- [ ] **INFRA-35**: `audit_payloads.py` extended with Pydantic v2 `extra='forbid'` schemas for every new event, each carrying `audit_correlation_id: UUID | None`
- [ ] **INFRA-36**: `YooKassaSettings` Pydantic Settings class with `shop_id: int`, `secret_key: SecretStr`, `return_url: HttpUrl`, `tax_system_code: int`, `default_vat_code: int`, `sandbox: bool`; entries in `.env.example` (no real credentials in git)
- [ ] **INFRA-37**: `YOOKASSA_TRUSTED_IPS: frozenset[str]` constant (6 published CIDR ranges) with AST gate rejecting any non-literal `verify_yookassa_ip` callsite (mirror `LOCKED_AUDIT_EVENTS` AST gate pattern)
- [ ] **INFRA-38**: Protocol slot declarations at composition root: `YooKassaClientProvider` (double-wired to FastAPI app + ARQ worker per REG-29-03), `FiscalReceiptDispatcher` (post-commit enqueue)
- [ ] **INFRA-39**: `app/integrations/yookassa/_money.py` with `kopecks_to_yookassa(int) -> str` and `yookassa_to_kopecks(str) -> int` converters + unit tests covering ≥10 edge cases (0, 1, 99, 100, 9999999, rounding, negative, leading zeros)
- [ ] **INFRA-40**: `.importlinter` updated — `app.modules.online_payments` added to `modules-independent` contract; targeted ignore entries for `online_payments → payments.models`, `online_payments → users.display`, `email.dispatcher → online_payments.email_templates`
- [ ] **INFRA-41**: Alembic 0033 adds partial UNIQUE `(lower(email)) WHERE email IS NOT NULL AND deleted_at IS NULL` on the existing `clients.email` column (column already exists since Alembic 0002 per v1.1; 0033 does NOT add or narrow it). Migration runs a pre-flight duplicate check (D-47-05) and aborts with `RuntimeError` listing offenders if any case-insensitive collision exists.

### ADAPTER (ЮKassa integration layer — Phase 48)

- [ ] **ADAPTER-01**: `app/integrations/yookassa/types.py` defines frozen dataclasses (`YooKassaPaymentResult`, `YooKassaRefundResult`, `YooKassaReceiptResult`, `YooKassaWebhookEvent`) with no SDK types crossing the boundary
- [ ] **ADAPTER-02**: `app/integrations/yookassa/client.py` async httpx wrapper exposing `create_payment`, `get_payment`, `create_refund`, `get_refund`; never re-raises; returns `EitherKind`-style result type with success/error variants
- [ ] **ADAPTER-03**: `app/integrations/yookassa/factory.py` boot-time API probe + connection check; logged via structlog at startup; failure is non-fatal (degraded mode)
- [ ] **ADAPTER-04**: `app/integrations/yookassa/receipt.py` builds receipt items with `PaymentSubject` (StrEnum, `service` literal locked), `PaymentMode` (StrEnum, `full_payment`/`full_prepayment` literals locked), `VatCode` (IntEnum from env config)
- [ ] **ADAPTER-05**: `app/integrations/yookassa/webhook_verifier.py` exposes `verify_yookassa_ip` `Depends()` callable; checks `X-Forwarded-For` against `YOOKASSA_TRUSTED_IPS`; sandbox bypass guarded by `YooKassaSettings.sandbox`; runs BEFORE body parse via FastAPI dependency ordering
- [ ] **ADAPTER-06**: `respx` test fixtures in `tests/integrations/yookassa/conftest.py` covering 6 canonical responses (create-success, create-422, get-pending, get-succeeded, refund-success, webhook-payload); used by all downstream adapter + module tests

### PAY (Online sales orchestrator — Phase 49)

- [x] **PAY-01**: Alembic 0034 creates `online_payments` table — UUIDv4 PK, `client_id` FK, `membership_plan_id`/`pt_package_plan_id` FK (XOR via CHECK), `yookassa_payment_id TEXT NOT NULL`, `idempotency_key TEXT NOT NULL`, `amount_kopecks INTEGER NOT NULL`, `status TEXT CHECK ∈ {pending, succeeded, canceled}`, `confirmation_url TEXT`, `initiated_at`/`succeeded_at`/`canceled_at` timestamps, `created_by_user_id` FK NULL (reception/owner initiating sale)
- [x] **PAY-02**: `online_payments` UNIQUE `(yookassa_payment_id)` + UNIQUE `(idempotency_key)` + partial UNIQUE `(client_id, membership_plan_id, DATE(initiated_at)) WHERE status != 'canceled'` (double-tap guard for memberships; analogous for pt_packages)
- [x] **PAY-03**: `POST /api/v1/online-payments/memberships/{plan_id}/sell` (reception + owner) — validates `client_id`, asserts `clients.email IS NOT NULL`, computes deterministic `Idempotency-Key = sha256(f"sell-membership:{plan_id}:{client_id}:{today_iso}")`, calls ЮKassa with embedded receipt items, returns `{ confirmation_url, online_payment_id }`
- [x] **PAY-04**: `POST /api/v1/online-payments/pt-packages/{plan_id}/sell` — analogous to PAY-03 for PT-package sales
- [x] **PAY-05**: `POST /api/v1/online-payments/memberships/{plan_id}/sell-qr` (and pt-packages variant) — `confirmation_type='qr'` differentiator; returns QR payload string; same webhook path (PAY-03 from research SUMMARY)
- [x] **PAY-06**: 422 `client_email_required_for_online_payment` returned when `clients.email IS NULL` (FIS-05 gate — fiscal receipt requires email)
- [x] **PAY-07**: `GET /api/v1/online-payments/return` handler — displays "ожидаем подтверждение" screen ONLY; never displays payment status (anti-oracle); `_constant_time_floor` try/finally on response duration to prevent timing oracle on lookup
- [x] **PAY-08**: Composition root wires `YooKassaClientProvider` + `FiscalReceiptDispatcher` slots; AST test asserts both slots non-None at startup (parity-test pattern from v1.6 USERS)

### WH (Webhook handler + FSM — Phase 50)

- [x] **WH-01**: `POST /api/v1/_internal/yookassa/webhook` route mounted under `_internal` namespace (no CSRF, no auth cookie); IP allowlist `Depends(verify_yookassa_ip)` runs BEFORE body parse (FastAPI dependency ordering enforces this; AST gate test verifies)
- [x] **WH-02**: Webhook handler re-fetches payment via `GET /v3/payments/{id}` BEFORE any DB write (never trusts webhook body as authoritative status)
- [x] **WH-03**: Redis idempotency `SET NX EX 86400 sz:yookassa:webhook:{event_type}:{object_id}` BEFORE DB write (ЮKassa retries up to 24h)
- [x] **WH-04**: Payment FSM `pending → succeeded / canceled` — central `_assert_can_transition` guard + declarative `ONLINE_PAYMENT_STATUS_TRANSITIONS` constant (parallels v1.3 `MEMBERSHIP_STATUS_TRANSITIONS`)
- [x] **WH-05**: On `payment.succeeded`: atomic UoW writes to `online_payments` (status update), calls `payment_recorder.record_payment(method='online')` (v1.4 ledger row), activates membership/PT-package via `MembershipActivator` Protocol slot, INSERTs `fiscal_receipts` row (`status='sent'`), commits, then enqueues notifications post-commit
- [x] **WH-06**: On `payment.canceled`: status update + audit emit; NOT-05 logs `cancellation_details.reason` from webhook payload (differentiator)

### FISCAL (54-ФЗ receipts — Phase 50+51)

- [x] **FISCAL-01**: Alembic 0035 creates `fiscal_receipts` table — UUIDv4 PK, `payment_id` FK to `payments.id` (NOT `online_payments.id` — fiscal obligation attaches to committed ledger row), `kind TEXT CHECK ∈ {payment, refund}`, `status TEXT CHECK ∈ {pending, sent, succeeded, failed}`, `yookassa_receipt_id TEXT NULL`, `customer_email TEXT NOT NULL`, `sent_at`/`succeeded_at`/`failed_at` timestamps, `failure_reason TEXT NULL`
- [x] **FISCAL-02**: UNIQUE `(payment_id, kind)` on `fiscal_receipts` (cross-channel discriminator pattern from v1.6 — same `payment_id` may have both `payment` AND `refund` receipts but not duplicates)
- [x] **FISCAL-03**: Receipt object embedded in `POST /v3/payments` body (Scenario 1) — receipt items composed via `build_receipt_item()` from ADAPTER-04; `customer.email` populated from `clients.email`; `payment_subject="service"` + `payment_mode="full_payment"` as `Literal` constants (AST gate rejects non-literal values)
- [ ] **FISCAL-04**: `handle_receipt_webhook()` processes `receipt.succeeded` and `receipt.canceled` event types (exact strings verified against ЮKassa dashboard in Phase 50); FSM `sent → succeeded / failed`
- [ ] **FISCAL-05**: `dispatch_fiscal_receipt` ARQ task (`max_tries=3`, `timeout=20s`, exponential backoff with jitter); Redis circuit breaker `sz:yookassa:circuit:receipts` (atomic pipeline `record_failure` + TTL 5m); mirrors v1.6 email circuit breaker
- [ ] **FISCAL-06**: ARQ cron `monitor_stale_fiscal_receipts` runs every 15 min Europe/Moscow — scans for `fiscal_receipts.status = 'pending'` rows older than 90s; emits `fiscal_receipt_failed` audit + operator Telegram alert via NOT-04
- [ ] **FISCAL-07**: `YOOKASSA_TAX_SYSTEM_CODE` (1=ОСН, 2=УСН доходы, 3=УСН доходы-расходы, 6=ПСН, etc.) + `YOOKASSA_VAT_CODE` (1=без НДС, 2=НДС 0%, etc.) read from env via `YooKassaSettings`; never hardcoded; deployment-runbook documents how owner sets per-deployment

### REFUND (Online refunds — Phase 51)

- [ ] **REFUND-01**: `POST /api/v1/online-payments/memberships/{id}/refund` (reception + owner) — full refund only (v1.4 B-02 partial-refund still deferred); routes to `client.create_refund()`; returns 202 (refund awaits webhook confirmation); analogous endpoint for pt-packages
- [ ] **REFUND-02**: `handle_refund_webhook()` processes `refund.succeeded` event — atomic UoW: writes refund row to `payments` (signed-amount preserves v1.4 CHECK), updates membership/pt-package status to `refunded`, INSERTs `fiscal_receipts(kind='refund')` row, commits, enqueues NOT-02 DMs post-commit
- [ ] **REFUND-03**: Partial UNIQUE `(refund_of) WHERE refund_of IS NOT NULL` from v1.4 preserved (prevents double-refund); webhook handler returns 200 on `IntegrityError` (idempotent semantics on retry)
- [ ] **REFUND-04**: ARQ task `poll_pending_refunds` runs every 30 min — for any refund row with `status='pending'` older than 30 min, calls `GET /v3/refunds/{id}` and reconciles; covers missing `refund.succeeded` webhook subscription (deployment-runbook entry)

### NOTIFY (Cross-channel mirrors — Phase 52)

- [ ] **NOTIFY-01**: `app/modules/online_payments/notifications.py` defines 4 locked Telegram DM templates (`ONLINE_PAYMENT_SUCCEEDED_DM`, `ONLINE_PAYMENT_REFUNDED_DM`, `ONLINE_PAYMENT_CANCELED_DM` — owner-only operator alert, `FISCAL_RECEIPT_FAILED_DM` — owner-only); D-39-02 module-scope copy ownership pattern preserved
- [ ] **NOTIFY-02**: `app/modules/online_payments/email_templates.py` defines 4 corresponding email template identifiers; `LOCKED_EMAIL_TEMPLATES` frozenset extended from 15 → 19; AST gate continues to reject non-literal `template_id` arguments to `get_email_dispatcher()`
- [ ] **NOTIFY-03**: Cross-channel idempotency — extend `payment_notifications` (new table) with UNIQUE `(payment_id, kind, channel)`; channel ∈ {`telegram`, `email`}; mirrors v1.6 `membership_notifications` + `booking_notifications` discriminator pattern
- [ ] **NOTIFY-04**: Operator alert on fiscal failure — when `fiscal_receipts.status → failed`, structlog ERROR + send `FISCAL_RECEIPT_FAILED_DM` to owner's Telegram + send owner email (best-effort, does not roll back payment commit; mirrors v1.6 D-45-08 fire-and-forget)
- [ ] **NOTIFY-05**: Cancellation reason logging differentiator — `payment.canceled` audit payload includes `cancellation_party`, `cancellation_reason` from ЮKassa response; no client DM (operator-visible only via audit log in v1.8)

### CARRY (v1.6 deferrals — Phase 52)

- [ ] **CARRY-01**: **DEFER-46-01** closed — live RU email-deliverability probe executed against yandex.ru + mail.ru + rambler.ru with real Yandex Postbox API key + owner's RU aliases; `Authentication-Results` headers captured to `.planning/handoff/v1.7-email-deliverability-evidence/`; probe script `apps/backend/scripts/verify/v1_6_email_probe.py` extended if needed
- [ ] **CARRY-02**: **DEFER-46-02** closed — owner formally countersigns 15 v1.6 `LOCKED_EMAIL_TEMPLATES` (visual sanity check, no content edits); `signed_off_at` timestamp recorded in `.planning/handoff/v1.6-template-countersign.md`

### VER (Milestone verification gate — Phase 53)

- [ ] **VER-01**: Operator runbook `apps/backend/scripts/verify/v1_7_runbook.sh` — curl scenarios covering: create membership online sale, simulate `payment.succeeded` webhook delivery against sandbox, verify membership activated, verify fiscal_receipt row inserted, refund flow end-to-end, expired idempotency-key replay returns idempotent 200
- [ ] **VER-02**: Race tests (real Postgres, `pytest-postgresql` fixture): concurrent `payment.succeeded` double-delivery (Redis dedup + DB UNIQUE both proven); webhook arrives after Redis restart (DB UNIQUE catches it); concurrent refund webhook + manual refund command (partial UNIQUE on `refund_of` arbitrates); concurrent kopecks↔rubles edge values (Decimal precision proven)
- [ ] **VER-03**: ЮKassa sandbox walkthrough — owner-recorded session driving an end-to-end membership sale + refund through the dashboard; evidence captured to `.planning/handoff/v1.7-yookassa-sandbox-evidence/`
- [ ] **VER-04**: Inline-regression hard cap ≤5 (mirror v1.6 D-46-26); milestone-verification phase blocks at >5 regressions and rolls excess to v1.8 DEFER list
- [ ] **VER-05**: **DEFER-46-03** closed — VER-09 scenario 08 cron-chain circuit-breaker fixture re-run from v1.6 (now that circuit breaker pattern is reused in FISCAL-05, the fixture is naturally exercised; explicit re-test confirms parity)

---

## Future Requirements (deferred to later milestones)

- **v1.8** — Reports + Audit Log read API; Telegram WebApp invoice; reconciliation dashboards for fiscal_receipts; partial-refund design (lifts v1.4 B-02 deferral)
- **v1.9** — API Handoff + Production Hardening; curated Postman collection of online-payment + refund endpoints; `@sportzal/api-client` regen + npm publish
- **v2.0** — Recurring autopayments (saved cards, subscription flows); client-facing self-service portal; embedded ЮKassa checkout widget (PAY-02 from research)

---

## Out of Scope (explicit exclusions with reasoning)

- **Stripe / PayPal / other non-RF payment processors** — banned by RF regional constraint (CLAUDE.md)
- **Separate АТОЛ-Онлайн / Чек.ОФД adapter** — "Чеки от ЮKassa" managed path covers single-merchant non-split sales; introducing a second fiscal adapter doubles failure modes for no business value at single-gym scale
- **SMS-delivered fiscal receipts** — ЮKassa receipts path supports email only; SMS delivery would require contracting a separate ОФД operator
- **Partial online refund** — v1.4 B-02 still deferred until membership partial-cancel semantics are designed; full-only refund preserves existing CHECK + atomic audit chain
- **Two-stage capture (`waiting_for_capture` hold)** — applies to goods-shipment scenarios; inapplicable to digital membership/PT-package activation
- **Recurring autopayments** — requires ЮKassa manager activation + client consent flow + self-service portal UI; deferred to v2.0
- **Embedded ЮKassa checkout widget (frontend JS SDK)** — admin SPA is reception-facing; client-facing checkout SPA is a v2.0 concern
- **Telegram WebApp Invoice native flow** — separate API path; admin SPA is not a Telegram Mini App
- **Mobile-app deep-link confirmation** — no mobile app in scope
- **Partial VAT rates (5% / 7%)** — applicable only above УСН revenue threshold (60M RUB/year), unreachable at single-gym MVP scale
- **Refund to different card** — requires separate ЮKassa Payout agreement; out of scope for v1.7

---

## Traceability

| REQ-ID | Phase | Status |
|---|---|---|
| INFRA-34 | Phase 47 | Pending |
| INFRA-35 | Phase 47 | Pending |
| INFRA-36 | Phase 47 | Pending |
| INFRA-37 | Phase 47 | Pending |
| INFRA-38 | Phase 47 | Pending |
| INFRA-39 | Phase 47 | Pending |
| INFRA-40 | Phase 47 | Pending |
| INFRA-41 | Phase 47 | Pending |
| ADAPTER-01 | Phase 48 | Pending |
| ADAPTER-02 | Phase 48 | Pending |
| ADAPTER-03 | Phase 48 | Pending |
| ADAPTER-04 | Phase 48 | Pending |
| ADAPTER-05 | Phase 48 | Pending |
| ADAPTER-06 | Phase 48 | Pending |
| PAY-01 | Phase 49 | Complete |
| PAY-02 | Phase 49 | Complete |
| PAY-03 | Phase 49 | Complete |
| PAY-04 | Phase 49 | Complete |
| PAY-05 | Phase 49 | Complete |
| PAY-06 | Phase 49 | Complete |
| PAY-07 | Phase 49 | Complete |
| PAY-08 | Phase 49 | Complete |
| WH-01 | Phase 50 | Complete |
| WH-02 | Phase 50 | Complete |
| WH-03 | Phase 50 | Complete |
| WH-04 | Phase 50 | Complete |
| WH-05 | Phase 50 | Complete |
| WH-06 | Phase 50 | Complete |
| FISCAL-01 | Phase 50 | Complete |
| FISCAL-02 | Phase 50 | Complete |
| FISCAL-03 | Phase 50 | Complete |
| FISCAL-04 | Phase 51 | Pending |
| FISCAL-05 | Phase 51 | Pending |
| FISCAL-06 | Phase 51 | Pending |
| FISCAL-07 | Phase 51 | Pending |
| REFUND-01 | Phase 51 | Pending |
| REFUND-02 | Phase 51 | Pending |
| REFUND-03 | Phase 51 | Pending |
| REFUND-04 | Phase 51 | Pending |
| NOTIFY-01 | Phase 52 | Pending |
| NOTIFY-02 | Phase 52 | Pending |
| NOTIFY-03 | Phase 52 | Pending |
| NOTIFY-04 | Phase 52 | Pending |
| NOTIFY-05 | Phase 52 | Pending |
| CARRY-01 | Phase 52 | Pending |
| CARRY-02 | Phase 52 | Pending |
| VER-01 | Phase 53 | Pending |
| VER-02 | Phase 53 | Pending |
| VER-03 | Phase 53 | Pending |
| VER-04 | Phase 53 | Pending |
| VER-05 | Phase 53 | Pending |
